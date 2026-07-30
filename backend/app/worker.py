"""Background job orchestration: runs the pipeline for one uploaded PDF.

This is the only place where pipeline modules and job state meet; the
pipeline modules themselves stay pure and FastAPI-free.

Pipeline order:
  1. extract PDF metadata + pick the cover via LLM analysis of candidates
  2. get page texts (direct extraction for digital PDFs, OCR for scans,
     per-page OCR fallback for mixed PDFs)
  3. cleanup: strip page numbers / running headers, drop front-matter pages
  4. LLM correction per page
  5. metadata merge (user > cover > content LLM > PDF) and EPUB assembly
"""

import asyncio
import logging
from typing import Literal

from .config import Settings
from .job_manager import Job, JobManager
from .models import BookMetadata, JobStatus, PageResult, Stage
from .pipeline import (
    cleanup,
    correction,
    cover_analysis,
    epub_builder,
    metadata_llm,
    ocr,
    pdf_extract,
)

logger = logging.getLogger(__name__)

# A "text" page shorter than this is treated as scanned and sent to OCR
# (mixed PDFs: digital body with scanned cover/plates).
_MIN_TEXT_CHARS_PER_PAGE = 50


async def process_job(job: Job, manager: JobManager, settings: Settings) -> None:
    try:
        await _run_pipeline(job, manager, settings)
        manager.finish(job)
    except asyncio.CancelledError:
        # User pressed stop — a deliberate outcome, not an error.
        logger.info("Job %s cancelled by user", job.job_id)
        manager.finish(job, cancelled=True)
    except Exception as exc:  # a failed job must not crash the server
        logger.exception("Job %s failed", job.job_id)
        manager.finish(job, error=str(exc))
    finally:
        # The uploaded PDF is only needed during processing — free the space.
        job.pdf_path.unlink(missing_ok=True)


async def _run_pipeline(job: Job, manager: JobManager, settings: Settings) -> None:
    job.status = JobStatus.PROCESSING

    # 1. PDF extraction: metadata, cover candidates, page count
    manager.update_progress(job, stage=Stage.EXTRACTING)
    total_pages = await asyncio.to_thread(pdf_extract.page_count, job.pdf_path)
    manager.update_progress(job, stage=Stage.EXTRACTING, total_pages=total_pages)
    pdf_meta = await asyncio.to_thread(pdf_extract.extract_pdf_metadata, job.pdf_path)

    # Cover: heuristic candidates from the first pages, LLM picks the real one
    # and reads title/author off it when visible.
    cover_candidates = await asyncio.to_thread(
        pdf_extract.extract_cover_candidates, job.pdf_path, settings.render_dpi
    )
    cover_backend = cover_analysis.OpenAICompatibleCoverBackend(
        host=settings.llm_host, model=settings.llm_model, api_key=settings.llm_api_key
    )
    job.cover_png, cover_meta = await asyncio.to_thread(
        cover_analysis.pick_best_cover, cover_backend, cover_candidates
    )
    logger.info(
        "Cover picked: is_cover=%s title=%r author=%r confidence=%.2f",
        cover_meta.is_cover, cover_meta.title, cover_meta.author, cover_meta.confidence,
    )

    # 2. Page texts: direct extraction when possible, OCR otherwise.
    is_text_pdf = await asyncio.to_thread(pdf_extract.has_extractable_text, job.pdf_path)
    ocr_engine = ocr.create_engine(settings.ocr_engine, settings.ocr_language)

    # (page_number, raw_text, needs_image) per page — images are re-rendered
    # lazily during correction to avoid holding every 300-DPI PNG in memory.
    raw_pages: list[tuple[int, str, bool]] = []

    if is_text_pdf:
        logger.info("PDF has extractable text — direct extraction with per-page OCR fallback")
        text_pages = await asyncio.to_thread(pdf_extract.extract_text_pages, job.pdf_path)
        # OCR'd "searchable" PDFs leave inline images where the text layer is
        # incomplete/garbled — those pages need the vision model to see the
        # actual page render during correction.
        image_flags = await asyncio.to_thread(pdf_extract.page_image_flags, job.pdf_path)
        for page_number, text in enumerate(text_pages, start=1):
            if len(text.strip()) >= _MIN_TEXT_CHARS_PER_PAGE:
                raw_pages.append((page_number, text, image_flags[page_number - 1]))
                continue
            # Mixed PDF: this page is likely a scan — OCR just this page.
            manager.update_progress(
                job, stage=Stage.OCR, current_page=page_number, total_pages=total_pages
            )
            try:
                image_png = await asyncio.to_thread(
                    pdf_extract.render_single_page, job.pdf_path, page_number, settings.render_dpi
                )
                ocr_text = await asyncio.to_thread(ocr_engine.recognize, image_png)
                raw_pages.append((page_number, ocr_text, True))
            except Exception:
                # One unreadable page in an otherwise digital book must not
                # kill the job — keep whatever text extraction produced.
                logger.exception("Per-page OCR fallback failed on page %d", page_number)
                raw_pages.append((page_number, text, False))
    else:
        logger.info("PDF is scanned — full OCR pass")
        # One page image in memory at a time; progress events stay on the
        # event loop (asyncio queues are not thread-safe).
        for page_number in range(1, total_pages + 1):
            manager.update_progress(
                job, stage=Stage.OCR, current_page=page_number, total_pages=total_pages
            )
            image_png = await asyncio.to_thread(
                pdf_extract.render_single_page, job.pdf_path, page_number, settings.render_dpi
            )
            text = await asyncio.to_thread(ocr_engine.recognize, image_png)
            raw_pages.append((page_number, text, True))

    # 3. Cleanup: strip page numbers + running headers, then drop front matter.
    cleaned_texts = await asyncio.to_thread(
        cleanup.clean_pages, [text for _, text, _ in raw_pages]
    )
    keep_flags = [not cleanup.is_intro_page(text) for text in cleaned_texts]
    removed = [raw_pages[i][0] for i, keep in enumerate(keep_flags) if not keep]
    if removed:
        logger.info("Dropped %d front-matter page(s): %s", len(removed), removed)
    content_pages = [
        (raw_pages[i][0], cleaned_texts[i], raw_pages[i][2])
        for i, keep in enumerate(keep_flags)
        if keep
    ]
    if not content_pages:
        # Over-aggressive filtering must never produce an empty book.
        logger.warning("Front-matter filter removed every page — keeping all pages")
        content_pages = [
            (raw_pages[i][0], cleaned_texts[i], raw_pages[i][2])
            for i in range(len(raw_pages))
        ]

    # 4. LLM correction page by page.
    correction_backend = correction.OpenAICompatibleCorrectionBackend(
        host=settings.llm_host, model=settings.llm_model, api_key=settings.llm_api_key
    )
    job.pages = []
    for index, (page_number, raw_text, needs_image) in enumerate(content_pages, start=1):
        manager.update_progress(
            job, stage=Stage.CORRECTING, current_page=index, total_pages=len(content_pages)
        )
        image_png = b""
        if needs_image:
            image_png = await asyncio.to_thread(
                pdf_extract.render_single_page, job.pdf_path, page_number, settings.render_dpi
            )
        result: PageResult = await asyncio.to_thread(
            correction.correct_page,
            correction_backend,
            page_number,
            raw_text,
            image_png,
            low_confidence_threshold=settings.low_confidence_threshold,
        )
        job.pages.append(result)
        manager.publish(
            job, {"type": "page", "page_number": index, "total_pages": len(content_pages)}
        )

    # 5. Metadata merge: PDF (if reliable) < content LLM < cover analysis.
    manager.update_progress(job, stage=Stage.METADATA)
    job.metadata = await _resolve_metadata(job, pdf_meta, cover_meta, settings)
    manager.publish(
        job,
        {"type": "metadata", "metadata": job.metadata.model_dump() if job.metadata else None},
    )

    # 6. EPUB assembly
    manager.update_progress(job, stage=Stage.BUILDING_EPUB)
    await build_epub_for_job(job, settings)


async def _resolve_metadata(
    job: Job,
    pdf_meta: BookMetadata,
    cover_meta: cover_analysis.CoverAnalysis,
    settings: Settings,
) -> BookMetadata:
    """Merge metadata sources by trustworthiness.

    Priority per field: cover analysis (the cover states the title/author
    verbatim) > content LLM inference > embedded PDF metadata. The PDF value
    is used as the base only when it looks reliable.
    """
    base = pdf_meta if pdf_extract.is_metadata_reliable(pdf_meta) else BookMetadata()

    title = cover_meta.title.strip() or base.title
    author = cover_meta.author.strip() or base.author
    year = base.year

    if not (title and author):
        # Still missing fields — infer from the first content pages.
        metadata_backend = metadata_llm.OpenAICompatibleMetadataBackend(
            host=settings.llm_host, model=settings.llm_model, api_key=settings.llm_api_key
        )
        first_pages = [p.text for p in job.pages[: settings.metadata_pages]]
        inferred = await asyncio.to_thread(
            metadata_llm.infer_metadata, metadata_backend, first_pages
        )
        title = title or inferred.title
        author = author or inferred.author
        year = year or inferred.year

    source: Literal["pdf", "cover", "llm", "user", "unknown"]
    if cover_meta.title or cover_meta.author:
        source = "cover"
    elif base.title or base.author:
        source = "pdf"
    elif title or author:
        source = "llm"
    else:
        source = "unknown"

    return BookMetadata(
        title=title, author=author, year=year, language=pdf_meta.language, source=source
    )


def _epub_filename(metadata: BookMetadata, fallback: str) -> str:
    """Human-readable EPUB filename from metadata: "Title - Author.epub"."""
    title = metadata.title.strip()
    author = metadata.author.strip()
    stem = " - ".join(part for part in (title, author) if part) or fallback
    stem = "".join(c if c.isalnum() or c in " .,'-" else "_" for c in stem).strip()
    return f"{stem[:150]}.epub"


async def build_epub_for_job(job: Job, settings: Settings) -> None:
    """Build (or rebuild, after a metadata PATCH) the EPUB for a job."""
    assert job.metadata is not None
    output_path = settings.output_dir / _epub_filename(job.metadata, job.job_id)
    # A rebuild after a metadata PATCH may rename the file — drop the old one.
    if job.epub_path is not None and job.epub_path != output_path:
        job.epub_path.unlink(missing_ok=True)
    job.epub_path = await asyncio.to_thread(
        epub_builder.build_epub,
        job.metadata,
        job.pages,
        output_path,
        job.cover_png,
    )
