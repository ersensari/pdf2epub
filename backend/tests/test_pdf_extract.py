from pathlib import Path

import fitz

from app.models import BookMetadata
from app.pipeline import pdf_extract


def _solid_png(width: int, height: int, rgb: tuple[int, int, int]) -> bytes:
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, width, height))
    pix.set_rect(pix.irect, rgb)
    return pix.tobytes("png")


def test_extract_pdf_metadata(sample_pdf: Path) -> None:
    metadata = pdf_extract.extract_pdf_metadata(sample_pdf)
    assert metadata.title == "Deneme Kitabı"
    assert metadata.author == "Ahmet Yazar"
    assert metadata.source == "pdf"


def test_extract_pdf_metadata_empty(blank_pdf: Path) -> None:
    metadata = pdf_extract.extract_pdf_metadata(blank_pdf)
    assert metadata.title == ""
    assert metadata.source == "unknown"


def test_is_metadata_reliable() -> None:
    assert pdf_extract.is_metadata_reliable(BookMetadata(title="Çalıkuşu", author="R. N. Güntekin"))
    assert not pdf_extract.is_metadata_reliable(BookMetadata(title=""))
    assert not pdf_extract.is_metadata_reliable(BookMetadata(title="Untitled"))
    assert not pdf_extract.is_metadata_reliable(BookMetadata(title="scan_0001.pdf"))


def test_page_count_and_render(sample_pdf: Path) -> None:
    assert pdf_extract.page_count(sample_pdf) == 3
    pages = list(pdf_extract.render_pages(sample_pdf, dpi=72))
    assert [number for number, _ in pages] == [1, 2, 3]
    # PNG magic bytes
    assert all(png.startswith(b"\x89PNG") for _, png in pages)


def test_extract_cover_falls_back_to_first_page(sample_pdf: Path) -> None:
    # The generated PDF has no embedded images, so the first page render is used.
    cover = pdf_extract.extract_cover(sample_pdf, dpi=72)
    assert cover.startswith(b"\x89PNG")


def test_layered_scan_puts_render_first(tmp_path: Path) -> None:
    """Two full-page image layers on page 1 → the composited render must be
    the first cover candidate, not any single (broken-looking) layer."""
    pdf_path = tmp_path / "layered.pdf"
    doc = fitz.open()
    page = doc.new_page(width=400, height=600)
    page.insert_image(page.rect, stream=_solid_png(400, 600, (250, 200, 200)))
    page.insert_image(fitz.Rect(20, 30, 380, 570), stream=_solid_png(360, 540, (30, 60, 90)))
    doc.save(pdf_path)
    doc.close()

    candidates = pdf_extract.extract_cover_candidates(pdf_path, dpi=72)
    # The render at 72 dpi has the page's own pixel size (400x600); embedded
    # layers keep their source sizes — identify the render by its dimensions.
    first = fitz.Pixmap(candidates[0])
    assert (first.width, first.height) == (400, 600)


def test_digital_pdf_keeps_embedded_image_first(tmp_path: Path) -> None:
    """A single large embedded image (real digital cover) stays first."""
    pdf_path = tmp_path / "digital.pdf"
    doc = fitz.open()
    page = doc.new_page(width=400, height=600)
    page.insert_image(fitz.Rect(0, 0, 400, 600), stream=_solid_png(500, 750, (10, 120, 60)))
    doc.save(pdf_path)
    doc.close()

    candidates = pdf_extract.extract_cover_candidates(pdf_path, dpi=72)
    first = fitz.Pixmap(candidates[0])
    assert (first.width, first.height) == (500, 750)


def test_page_image_flags(tmp_path: Path) -> None:
    pdf_path = tmp_path / "mixed.pdf"
    doc = fitz.open()
    page1 = doc.new_page(width=400, height=600)
    page1.insert_text((72, 72), "Metinli sayfa, küçük gömülü resimli.")
    page1.insert_image(fitz.Rect(100, 100, 130, 130), stream=_solid_png(30, 30, (0, 0, 0)))
    page2 = doc.new_page(width=400, height=600)
    page2.insert_text((72, 72), "Sadece metin.")
    doc.save(pdf_path)
    doc.close()

    assert pdf_extract.page_image_flags(pdf_path) == [True, False]
