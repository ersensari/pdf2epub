"""Unit tests for metadata-based EPUB filenames."""

from app.models import BookMetadata
from app.worker import _epub_filename


def test_title_and_author() -> None:
    meta = BookMetadata(title="Bugün Kalan Hayatımın İlk Günü", author="Maud Ankaoua")
    assert _epub_filename(meta, "jobid") == "Bugün Kalan Hayatımın İlk Günü - Maud Ankaoua.epub"


def test_title_only() -> None:
    meta = BookMetadata(title="Çalıkuşu")
    assert _epub_filename(meta, "jobid") == "Çalıkuşu.epub"


def test_empty_metadata_falls_back_to_job_id() -> None:
    assert _epub_filename(BookMetadata(), "abc123") == "abc123.epub"


def test_dangerous_characters_sanitized() -> None:
    meta = BookMetadata(title="a/b\\c:d", author="x*y?z")
    name = _epub_filename(meta, "jobid")
    assert "/" not in name and "\\" not in name and ":" not in name and "*" not in name
    assert name.endswith(".epub")


def test_very_long_title_truncated() -> None:
    meta = BookMetadata(title="U" * 400, author="Yazar")
    name = _epub_filename(meta, "jobid")
    assert len(name) <= 155  # 150 chars stem + ".epub"
