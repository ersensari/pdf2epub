"""Permanent EPUB library: list, download and delete generated books.

The library is simply the contents of the output directory — EPUBs are
stored under their human-readable "Title - Author.epub" names, so no extra
bookkeeping/database is needed.
"""

from pathlib import Path
from urllib.parse import unquote

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ..config import get_settings

router = APIRouter()


class EpubEntry(BaseModel):
    filename: str
    size: int
    modified_at: float  # unix timestamp


def _resolve_epub(filename: str) -> Path:
    """Resolve a library filename safely inside the output directory."""
    settings = get_settings()
    name = unquote(filename)
    if "/" in name or "\\" in name or name.startswith("."):
        raise HTTPException(status_code=400, detail="Invalid filename")
    path = (settings.output_dir / name).resolve()
    if path.parent != settings.output_dir.resolve() or path.suffix != ".epub":
        raise HTTPException(status_code=400, detail="Invalid filename")
    if not path.is_file():
        raise HTTPException(status_code=404, detail="EPUB not found")
    return path


@router.get("/api/epubs")
async def list_epubs() -> dict[str, list[EpubEntry]]:
    settings = get_settings()
    entries = [
        EpubEntry(
            filename=path.name,
            size=path.stat().st_size,
            modified_at=path.stat().st_mtime,
        )
        for path in sorted(
            settings.output_dir.glob("*.epub"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
    ]
    return {"epubs": entries}


@router.get("/api/epubs/{filename}")
async def download_epub(filename: str) -> FileResponse:
    path = _resolve_epub(filename)
    return FileResponse(path=path, media_type="application/epub+zip", filename=path.name)


@router.delete("/api/epubs/{filename}")
async def delete_epub(filename: str) -> dict[str, str]:
    path = _resolve_epub(filename)
    path.unlink()
    return {"status": "deleted", "filename": path.name}
