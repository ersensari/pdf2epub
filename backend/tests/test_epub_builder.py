import zipfile
from pathlib import Path

from app.models import BookMetadata, PageResult
from app.pipeline.epub_builder import build_epub, split_into_chapters


def _page(number: int, text: str, block_type: str = "paragraph") -> PageResult:
    return PageResult(page_number=number, text=text, block_type=block_type)  # type: ignore[arg-type]


def test_split_into_chapters_by_headings() -> None:
    pages = [
        _page(1, "Önsöz metni"),
        _page(2, "BİRİNCİ BÖLÜM", "heading"),
        _page(3, "Bölüm bir metni"),
        _page(4, "İKİNCİ BÖLÜM", "heading"),
        _page(5, "Bölüm iki metni"),
    ]
    chapters = split_into_chapters(pages)
    assert [c.title for c in chapters] == ["Front matter", "BİRİNCİ BÖLÜM", "İKİNCİ BÖLÜM"]
    assert [len(c.pages) for c in chapters] == [1, 2, 2]


def test_build_epub_produces_valid_archive(tmp_path: Path) -> None:
    metadata = BookMetadata(title="Deneme", author="Ahmet Yazar", year="1950")
    pages = [
        _page(1, "BAŞLIK", "heading"),
        _page(2, "Birinci paragraf.\n\nİkinci paragraf."),
        _page(3, "Dipnot metni", "footnote"),
    ]
    output = build_epub(metadata, pages, tmp_path / "out.epub", cover_png=_tiny_png())

    assert output.exists()
    with zipfile.ZipFile(output) as archive:
        names = archive.namelist()
        # EPUB essentials: mimetype, container, nav, our chapter, the cover
        assert "mimetype" in names
        assert "META-INF/container.xml" in names
        assert any(name.endswith("nav.xhtml") for name in names)
        assert any("chapter_001" in name for name in names)
        assert any("cover" in name.lower() for name in names)
        chapter = next(name for name in names if "chapter_001" in name)
        content = archive.read(chapter).decode("utf-8")
        assert "BAŞLIK" in content


def test_build_epub_without_cover(tmp_path: Path) -> None:
    output = build_epub(BookMetadata(title="Kapaksız"), [_page(1, "metin")], tmp_path / "no_cover.epub")
    assert output.exists()


def _tiny_png() -> bytes:
    """1×1 white PNG, generated with Pillow to avoid a binary fixture."""
    import io

    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (1, 1), "white").save(buffer, format="PNG")
    return buffer.getvalue()
