import pytest

from app.pipeline.ocr import OCREngine, PaddleOCREngine, TesseractEngine, create_engine


def test_create_engine_factory() -> None:
    assert isinstance(create_engine("paddle"), PaddleOCREngine)
    assert isinstance(create_engine("tesseract"), TesseractEngine)


def test_create_engine_unknown_name() -> None:
    with pytest.raises(ValueError, match="Unknown OCR engine"):
        create_engine("easyocr")


def test_engine_is_abstract() -> None:
    with pytest.raises(TypeError):
        OCREngine()  # type: ignore[abstract]


def test_custom_engine_via_interface() -> None:
    """New engines only need to implement recognize() — Strategy pattern."""

    class FakeEngine(OCREngine):
        def recognize(self, image_png: bytes) -> str:
            return "merhaba dünya"

    engine: OCREngine = FakeEngine()
    assert engine.recognize(b"") == "merhaba dünya"
