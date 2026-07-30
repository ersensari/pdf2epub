"""PDF extraction: embedded metadata, cover candidate and page rendering.

Pure functions on top of PyMuPDF — no FastAPI or job-state dependencies, so
the module is unit-testable in isolation.
"""

from collections.abc import Iterator
from pathlib import Path

import fitz  # PyMuPDF

from ..models import BookMetadata

# Embedded images smaller than this (in pixels) are ignored as cover
# candidates — they are usually logos or ornaments, not the cover scan.
_MIN_COVER_PIXELS = 100_000


def extract_pdf_metadata(pdf_path: Path) -> BookMetadata:
    """Read embedded PDF metadata. Fields are often empty in old scans."""
    with fitz.open(pdf_path) as doc:
        raw = doc.metadata or {}
    title = (raw.get("title") or "").strip()
    author = (raw.get("author") or "").strip()
    return BookMetadata(
        title=title,
        author=author,
        source="pdf" if (title or author) else "unknown",
    )


def is_metadata_reliable(metadata: BookMetadata) -> bool:
    """Heuristic check for scanner-generated junk metadata.

    Old scans frequently carry titles like "Untitled" or the scanner software
    name; treat those as missing so the LLM fallback kicks in.
    """
    title = metadata.title.lower()
    junk_markers = ("untitled", "scan", ".pdf", ".tif", "microsoft", "image")
    if not metadata.title:
        return False
    if any(marker in title for marker in junk_markers):
        return False
    return True


# How many leading pages are searched for cover candidates.
_COVER_SEARCH_PAGES = 4
# Upper bound on candidates handed to the (slow) LLM cover analysis.
_MAX_COVER_CANDIDATES = 4


def extract_cover_candidates(pdf_path: Path, dpi: int = 300) -> list[bytes]:
    """Return PNG candidates for the cover, best heuristic guess first.

    Candidates are the large, book-shaped embedded images from the first few
    pages (sorted by area, largest first) plus the rendered first page.
    The caller (LLM cover analysis) makes the final pick.

    Layered scans need special care: scanner software often splits a scanned
    cover into several full-page images (washed-out background + foreground
    layers). Any single layer looks broken on its own — only the *rendered*
    page composites them correctly — so in that case the render goes first
    (``pick_best_cover`` favors earlier candidates on equal confidence).
    """
    candidates: list[tuple[int, bytes]] = []

    with fitz.open(pdf_path) as doc:
        if doc.page_count == 0:
            raise ValueError("PDF has no pages")

        # Two or more images each covering most of page 1 = a layered scan
        # (background + foreground split by the scanner software).
        first_page = doc.load_page(0)
        first_page_area = first_page.rect.width * first_page.rect.height
        full_page_layers = 0
        for image_info in first_page.get_images(full=True):
            for rect in first_page.get_image_rects(image_info[0]):
                if first_page_area and (rect.width * rect.height) / first_page_area > 0.5:
                    full_page_layers += 1
                    break
        is_layered_scan = full_page_layers >= 2

        seen_xrefs: set[int] = set()
        for page_idx in range(min(_COVER_SEARCH_PAGES, doc.page_count)):
            page = doc.load_page(page_idx)
            for image_info in page.get_images(full=True):
                xref = image_info[0]
                if xref in seen_xrefs:
                    continue
                seen_xrefs.add(xref)
                pix = fitz.Pixmap(doc, xref)
                if pix.n - pix.alpha >= 4:  # convert CMYK etc. to RGB
                    pix = fitz.Pixmap(fitz.csRGB, pix)
                area = pix.width * pix.height
                # Prefer book-shaped images (covers are usually taller than wide)
                aspect_ratio = max(pix.width, pix.height) / min(pix.width, pix.height)
                if area >= _MIN_COVER_PIXELS and aspect_ratio < 3:
                    candidates.append((area, pix.tobytes("png")))

        candidates.sort(key=lambda item: item[0], reverse=True)
        embedded = [png for _, png in candidates[: _MAX_COVER_CANDIDATES - 1]]
        first_render = _render_page(first_page, dpi)

    if is_layered_scan:
        return ([first_render] + embedded)[:_MAX_COVER_CANDIDATES]
    return (embedded + [first_render])[:_MAX_COVER_CANDIDATES]


def extract_cover(pdf_path: Path, dpi: int = 300) -> bytes:
    """Return PNG bytes for the best heuristic cover candidate.

    Kept for callers that don't run LLM cover analysis; simply the first
    candidate from :func:`extract_cover_candidates`.
    """
    return extract_cover_candidates(pdf_path, dpi)[0]


def render_pages(pdf_path: Path, dpi: int = 300) -> Iterator[tuple[int, bytes]]:
    """Yield ``(page_number, png_bytes)`` for every page, 1-indexed."""
    with fitz.open(pdf_path) as doc:
        for index in range(doc.page_count):
            page = doc.load_page(index)
            yield index + 1, _render_page(page, dpi)


def render_single_page(pdf_path: Path, page_number: int, dpi: int = 300) -> bytes:
    """Render one page (1-indexed) to PNG — used for per-page OCR fallback."""
    with fitz.open(pdf_path) as doc:
        return _render_page(doc.load_page(page_number - 1), dpi)


def page_count(pdf_path: Path) -> int:
    with fitz.open(pdf_path) as doc:
        return doc.page_count


def page_image_flags(pdf_path: Path, min_page_fraction: float = 0.0002) -> list[bool]:
    """Per page (0-indexed list): does it embed a non-trivial image?

    In OCR'd "searchable" PDFs, spots the text layer couldn't represent
    (special glyphs, illustrations) are left as small inline images and the
    surrounding text layer is often garbled. Such pages need the vision model
    to see the actual page render during correction.
    """
    flags: list[bool] = []
    with fitz.open(pdf_path) as doc:
        for index in range(doc.page_count):
            page = doc.load_page(index)
            page_area = page.rect.width * page.rect.height
            has_image = False
            for image_info in page.get_images(full=True):
                for rect in page.get_image_rects(image_info[0]):
                    if page_area and (rect.width * rect.height) / page_area >= min_page_fraction:
                        has_image = True
                        break
                if has_image:
                    break
            flags.append(has_image)
    return flags


def has_extractable_text(pdf_path: Path) -> bool:
    """Check if PDF has selectable text (not scanned)."""
    with fitz.open(pdf_path) as doc:
        for page_num in range(min(3, doc.page_count)):  # Check first 3 pages
            page = doc.load_page(page_num)
            text = page.get_text().strip()
            if len(text) > 100:  # At least 100 chars means it has text
                return True
    return False


def extract_text_pages(pdf_path: Path) -> list[str]:
    """Extract text directly from PDF (for digital PDFs, not scans)."""
    with fitz.open(pdf_path) as doc:
        pages_text = []
        for page_num in range(doc.page_count):
            page = doc.load_page(page_num)
            text = page.get_text()
            pages_text.append(text)
    return pages_text


def _render_page(page: fitz.Page, dpi: int) -> bytes:
    zoom = dpi / 72  # PDF user space is 72 dpi
    matrix = fitz.Matrix(zoom, zoom)
    return page.get_pixmap(matrix=matrix).tobytes("png")
