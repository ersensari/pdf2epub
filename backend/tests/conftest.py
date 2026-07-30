"""Shared fixtures: a tiny generated PDF so tests need no binary assets."""

from pathlib import Path

import fitz
import pytest


@pytest.fixture
def sample_pdf(tmp_path: Path) -> Path:
    """Three-page PDF with embedded metadata, generated on the fly."""
    pdf_path = tmp_path / "sample.pdf"
    doc = fitz.open()
    doc.set_metadata({"title": "Deneme Kitabı", "author": "Ahmet Yazar"})
    for text in ("BİRİNCİ BÖLÜM", "Sayfa iki metni.", "Sayfa üç metni."):
        page = doc.new_page()
        page.insert_text((72, 72), text)
    doc.save(pdf_path)
    doc.close()
    return pdf_path


@pytest.fixture
def blank_pdf(tmp_path: Path) -> Path:
    """One-page PDF without any metadata."""
    pdf_path = tmp_path / "blank.pdf"
    doc = fitz.open()
    doc.new_page()
    doc.save(pdf_path)
    doc.close()
    return pdf_path
