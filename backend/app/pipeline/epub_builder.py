"""EPUB assembly with ebooklib.

Pages are grouped into chapters at ``block_type == "heading"`` boundaries;
the TOC (NCX + Nav) is generated from those headings.
"""

import html
from dataclasses import dataclass, field
from pathlib import Path

from ebooklib import epub

from ..models import BookMetadata, PageResult


@dataclass
class _Chapter:
    title: str
    pages: list[PageResult] = field(default_factory=list)


def split_into_chapters(pages: list[PageResult]) -> list[_Chapter]:
    """Group pages into chapters, starting a new one at each heading page.

    Pages before the first heading go into an implicit front-matter chapter.
    """
    chapters: list[_Chapter] = []
    for page in pages:
        if page.block_type == "heading" or not chapters:
            title = _heading_title(page) if page.block_type == "heading" else "Front matter"
            chapters.append(_Chapter(title=title))
        chapters[-1].pages.append(page)
    return chapters


def build_epub(
    metadata: BookMetadata,
    pages: list[PageResult],
    output_path: Path,
    cover_png: bytes | None = None,
) -> Path:
    """Assemble a valid EPUB and write it to ``output_path``."""
    book = epub.EpubBook()
    book.set_identifier(f"pdf2epub-{abs(hash((metadata.title, metadata.author)))}")
    book.set_language(metadata.language)
    book.set_title(metadata.title or "Untitled")
    if metadata.author:
        book.add_author(metadata.author)
    if metadata.year:
        book.add_metadata("DC", "date", metadata.year)

    if cover_png is not None:
        book.set_cover("cover.png", cover_png)

    chapters = split_into_chapters(pages)
    epub_chapters: list[epub.EpubHtml] = []
    for index, chapter in enumerate(chapters, start=1):
        item = epub.EpubHtml(
            title=chapter.title,
            file_name=f"chapter_{index:03d}.xhtml",
            lang=metadata.language,
        )
        item.content = _chapter_xhtml(chapter)
        book.add_item(item)
        epub_chapters.append(item)

    book.toc = epub_chapters
    book.spine = ["nav", *epub_chapters]
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    output_path.parent.mkdir(parents=True, exist_ok=True)
    epub.write_epub(str(output_path), book)
    return output_path


def _heading_title(page: PageResult) -> str:
    first_line = page.text.strip().splitlines()[0] if page.text.strip() else ""
    return first_line[:120] or f"Page {page.page_number}"


def _chapter_xhtml(chapter: _Chapter) -> str:
    parts: list[str] = [f"<h1>{html.escape(chapter.title)}</h1>"]
    for page in chapter.pages:
        text = page.text.strip()
        if page.block_type == "heading":
            # The heading itself is already the <h1>; keep any remaining lines.
            text = "\n".join(text.splitlines()[1:]).strip()
        for paragraph in _paragraphs(text):
            tag = "aside" if page.block_type == "footnote" else "p"
            parts.append(f"<{tag}>{html.escape(paragraph)}</{tag}>")
    return "\n".join(parts)


def _paragraphs(text: str) -> list[str]:
    if not text:
        return []
    blocks = [block.strip() for block in text.split("\n\n")]
    return [block for block in blocks if block]
