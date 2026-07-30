"""LLM fallback for book metadata.

When the PDF's embedded metadata is missing or unreliable, the corrected text
of the first few pages (title page, colophon) is sent to an OpenAI-compatible
API to infer the title, author and publication year.
"""

from abc import ABC, abstractmethod

from openai import OpenAI
from pydantic import BaseModel, ValidationError

from ..models import BookMetadata

_PROMPT_TEMPLATE = """The following is the text of the first pages of a scanned old Turkish book
(title page, colophon, etc.). Infer the book's title, author and, if visible,
publication year.

Answer with JSON only, exactly this schema:
{{"title": "<book title or empty string>", "author": "<author name or empty string>", "year": "<publication year or null>"}}

Do not invent values — use an empty string / null when the information is not present.

Pages:
---
{pages_text}
---"""


class _InferredMetadata(BaseModel):
    """Validation gate for the LLM's metadata JSON."""

    title: str = ""
    author: str = ""
    year: str | None = None


class MetadataBackend(ABC):
    @abstractmethod
    def infer(self, pages_text: str) -> _InferredMetadata:
        """Infer metadata from the given pages text. Raises on failure."""


class OpenAICompatibleMetadataBackend(MetadataBackend):
    def __init__(self, host: str, model: str, api_key: str = "") -> None:
        self._model = model
        self._client = OpenAI(base_url=host, api_key=api_key or "not-needed")

    def infer(self, pages_text: str) -> _InferredMetadata:
        response = self._client.chat.completions.create(
            model=self._model,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "user",
                    "content": _PROMPT_TEMPLATE.format(pages_text=pages_text),
                }
            ],
        )
        return _InferredMetadata.model_validate_json(
            response.choices[0].message.content
        )


def infer_metadata(backend: MetadataBackend, first_pages: list[str]) -> BookMetadata:
    """Infer book metadata from the first pages' text.

    Same error-tolerance chain as correction: retry once on invalid JSON, then
    fall back to empty metadata instead of failing the job.
    """
    pages_text = "\n\n--- page break ---\n\n".join(first_pages)

    inferred: _InferredMetadata | None = None
    for _ in range(2):  # initial attempt + one retry
        try:
            inferred = backend.infer(pages_text)
            break
        except (ValidationError, ValueError, KeyError, ConnectionError, TimeoutError):
            continue
        except Exception:
            continue

    if inferred is None or not (inferred.title or inferred.author):
        return BookMetadata(source="unknown")

    return BookMetadata(
        title=inferred.title.strip(),
        author=inferred.author.strip(),
        year=inferred.year,
        source="llm",
    )
