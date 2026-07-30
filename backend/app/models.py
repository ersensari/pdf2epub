"""Shared Pydantic models for jobs, pages and book metadata."""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class JobStatus(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    DONE = "done"
    ERROR = "error"
    CANCELLED = "cancelled"


class Stage(StrEnum):
    EXTRACTING = "extracting"
    OCR = "ocr"
    CORRECTING = "correcting"
    METADATA = "metadata"
    BUILDING_EPUB = "building_epub"


BlockType = Literal["heading", "paragraph", "footnote"]


class CorrectedBlock(BaseModel):
    """Structured output the LLM must return for one page.

    This model is the validation gate for Ollama responses: anything that does
    not parse into it counts as an invalid response.
    """

    corrected_text: str
    block_type: BlockType = "paragraph"
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)


class PageResult(BaseModel):
    """Final result of the pipeline for a single page."""

    page_number: int
    text: str
    block_type: BlockType = "paragraph"
    confidence: float = 0.0
    needs_review: bool = False
    # True when LLM correction failed and we fell back to raw OCR text.
    used_fallback: bool = False


class BookMetadata(BaseModel):
    title: str = ""
    author: str = ""
    year: str | None = None
    language: str = "tr"
    # Where the metadata came from: pdf metadata, cover-image analysis,
    # LLM inference from content, or the user.
    source: Literal["pdf", "cover", "llm", "user", "unknown"] = "unknown"


class MetadataPatch(BaseModel):
    """User-supplied corrections applied before the EPUB is built."""

    title: str | None = None
    author: str | None = None
    year: str | None = None


class Progress(BaseModel):
    current_page: int = 0
    total_pages: int = 0
    stage: Stage | None = None


class JobInfo(BaseModel):
    """Public job representation returned by the REST API."""

    job_id: str
    status: JobStatus
    progress: Progress = Progress()
    metadata: BookMetadata | None = None
    pages_needing_review: list[int] = []
    error: str | None = None
