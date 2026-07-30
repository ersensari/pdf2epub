"""Metadata inference tests: happy path + invalid JSON fallback."""

from app.pipeline.metadata_llm import MetadataBackend, OpenAICompatibleMetadataBackend, _InferredMetadata, infer_metadata


class FakeBackend(MetadataBackend):
    def __init__(self, responses: list[_InferredMetadata | Exception]) -> None:
        self.responses = responses

    def infer(self, pages_text: str) -> _InferredMetadata:
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def test_happy_path() -> None:
    backend = FakeBackend(
        [_InferredMetadata(title="Çalıkuşu", author="Reşat Nuri Güntekin", year="1922")]
    )
    metadata = infer_metadata(backend, ["ÇALIKUŞU", "Reşat Nuri Güntekin", "İstanbul 1922"])
    assert metadata.title == "Çalıkuşu"
    assert metadata.author == "Reşat Nuri Güntekin"
    assert metadata.year == "1922"
    assert metadata.source == "llm"


def test_invalid_json_twice_falls_back_to_empty() -> None:
    backend = FakeBackend([ValueError("bad json"), ValueError("bad json again")])
    metadata = infer_metadata(backend, ["sayfa metni"])
    assert metadata.title == ""
    assert metadata.author == ""
    assert metadata.source == "unknown"


def test_retry_once_then_succeed() -> None:
    backend = FakeBackend([ValueError("bad"), _InferredMetadata(title="Kitap", author="Yazar")])
    metadata = infer_metadata(backend, ["sayfa"])
    assert metadata.title == "Kitap"
    assert metadata.source == "llm"
