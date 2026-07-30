"""Unit tests for EPUB filename generation and library path safety."""

import pytest
from fastapi import HTTPException

from app.models import BookMetadata
from app.routes import library
from app.worker import _epub_filename


class TestEpubFilename:
    def test_title_and_author(self) -> None:
        meta = BookMetadata(title="Çalıkuşu", author="Reşat Nuri Güntekin")
        assert _epub_filename(meta, "jobid") == "Çalıkuşu - Reşat Nuri Güntekin.epub"

    def test_title_only(self) -> None:
        meta = BookMetadata(title="Sefiller")
        assert _epub_filename(meta, "jobid") == "Sefiller.epub"

    def test_empty_metadata_falls_back_to_job_id(self) -> None:
        assert _epub_filename(BookMetadata(), "abc123") == "abc123.epub"

    def test_invalid_characters_sanitized(self) -> None:
        meta = BookMetadata(title="Kitap: Bir/Deneme?", author="A<B>C")
        name = _epub_filename(meta, "jobid")
        assert "/" not in name and ":" not in name and "<" not in name
        assert name.endswith(".epub")


class TestResolveEpubSafety:
    def test_rejects_path_traversal(self) -> None:
        for bad in ["../secret.epub", "a/b.epub", "..\\x.epub", ".hidden.epub"]:
            with pytest.raises(HTTPException) as exc:
                library._resolve_epub(bad)
            assert exc.value.status_code == 400

    def test_rejects_non_epub(self, tmp_path, monkeypatch) -> None:
        from app import config

        settings = config.Settings(data_dir=tmp_path)
        settings.output_dir.mkdir(parents=True, exist_ok=True)
        (settings.output_dir / "notes.txt").write_text("x")
        monkeypatch.setattr(library, "get_settings", lambda: settings)
        with pytest.raises(HTTPException) as exc:
            library._resolve_epub("notes.txt")
        assert exc.value.status_code == 400

    def test_accepts_valid_epub(self, tmp_path, monkeypatch) -> None:
        from app import config

        settings = config.Settings(data_dir=tmp_path)
        settings.output_dir.mkdir(parents=True, exist_ok=True)
        target = settings.output_dir / "Kitap - Yazar.epub"
        target.write_bytes(b"PK")
        monkeypatch.setattr(library, "get_settings", lambda: settings)
        assert library._resolve_epub("Kitap%20-%20Yazar.epub") == target.resolve()
