"""Correction pipeline tests: happy path, invalid JSON, retry, fallback."""

import json
from typing import Any

import pytest

from app.models import CorrectedBlock
from app.pipeline.correction import (
    CorrectionBackend,
    OpenAICompatibleCorrectionBackend,
    correct_page,
)


class FakeBackend(CorrectionBackend):
    """Scripted backend: pops one response (or exception) per call."""

    def __init__(self, responses: list[CorrectedBlock | Exception]) -> None:
        self.responses = responses
        self.calls = 0

    def correct(self, ocr_text: str, image_png: bytes) -> CorrectedBlock:
        self.calls += 1
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def test_happy_path() -> None:
    backend = FakeBackend(
        [CorrectedBlock(corrected_text="Düzeltilmiş metin.", block_type="paragraph", confidence=0.95)]
    )
    result = correct_page(backend, 1, "Duzeltilmis metin.", b"png")
    assert result.text == "Düzeltilmiş metin."
    assert result.confidence == 0.95
    assert not result.needs_review
    assert not result.used_fallback


def test_low_confidence_flags_review() -> None:
    backend = FakeBackend([CorrectedBlock(corrected_text="ok", confidence=0.4)])
    result = correct_page(backend, 1, "ok", b"png", low_confidence_threshold=0.6)
    assert result.needs_review


def test_retry_once_then_succeed() -> None:
    backend = FakeBackend(
        [ValueError("invalid json"), CorrectedBlock(corrected_text="ikinci deneme", confidence=0.8)]
    )
    result = correct_page(backend, 1, "raw", b"png")
    assert backend.calls == 2
    assert result.text == "ikinci deneme"
    assert not result.used_fallback


def test_fallback_to_raw_ocr_after_two_failures() -> None:
    backend = FakeBackend([ValueError("bad"), ValueError("still bad")])
    result = correct_page(backend, 7, "ham OCR metni", b"png")
    assert backend.calls == 2
    assert result.text == "ham OCR metni"
    assert result.used_fallback
    assert result.needs_review
    assert result.page_number == 7


class _FakeOpenAIResponse:
    """Stands in for openai.ChatCompletionMessage; returns canned message contents."""

    def __init__(self, content: str) -> None:
        self.content = content


class _FakeOpenAICompletion:
    """Stands in for openai.types.chat.chat_completion.ChatCompletion."""

    def __init__(self, contents: list[str]) -> None:
        self._contents = contents

    @property
    def choices(self) -> list[Any]:
        return [_FakeFakeCompletionChoice(_FakeOpenAIResponse(self._contents.pop(0)))]


class _FakeFakeCompletionChoice:
    def __init__(self, message: _FakeOpenAIResponse) -> None:
        self.message = message


def _openai_backend(contents: list[str], monkeypatch: pytest.MonkeyPatch) -> OpenAICompatibleCorrectionBackend:
    from openai import OpenAI

    fake_class = type("_FakeOpenAIClient", (), {
        "chat": type("_FakeChat", (), {
            "completions": type("_FakeCompletions", (), {
                "create": lambda self, **kwargs: _FakeOpenAICompletion(contents)
            })()
        })()
    })
    monkeypatch.setattr("openai.OpenAI", lambda *args, **kwargs: fake_class())
    return OpenAICompatibleCorrectionBackend(host="http://fake:8000", model="fake-model")


def test_openai_backend_valid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = json.dumps(
        {"corrected_text": "Merhaba dünya.", "block_type": "heading", "confidence": 0.9}
    )
    backend = _openai_backend([payload], monkeypatch)
    block = backend.correct("Merhaba dunya.", b"png")
    assert block.corrected_text == "Merhaba dünya."
    assert block.block_type == "heading"


def test_openai_backend_invalid_json_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    """Model returns garbage twice → correct_page must fall back to raw OCR."""
    backend = _openai_backend(["not json at all", '{"wrong_key": 1}'], monkeypatch)
    result = correct_page(backend, 1, "ham metin", b"png")
    assert result.used_fallback
    assert result.text == "ham metin"


@pytest.mark.integration
def test_real_openai_correction() -> None:
    """Needs an OpenAI-compatible API server running with the configured model."""
    from app.config import get_settings

    settings = get_settings()
    backend = OpenAICompatibleCorrectionBackend(
        host=settings.llm_host, model=settings.llm_model, api_key=settings.llm_api_key
    )
    block = backend.correct("Bu bir dene me metnid ir.", b"")
    assert isinstance(block.corrected_text, str)
