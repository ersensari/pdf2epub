"""OCR engine abstraction (Strategy pattern).

``PaddleOCREngine`` is the primary engine, ``TesseractEngine`` the fallback.
Both are lazy-loaded so importing this module never pulls heavy dependencies,
and both work on raw PNG bytes so callers stay decoupled from the engines.
"""

from abc import ABC, abstractmethod
from typing import Any


class OCREngine(ABC):
    """Interface every OCR engine must implement.

    To add a new engine, subclass this and register it in ``create_engine`` —
    do not modify calling code.
    """

    @abstractmethod
    def recognize(self, image_png: bytes) -> str:
        """Run OCR on a PNG image and return the recognized plain text."""


class PaddleOCREngine(OCREngine):
    def __init__(self, language: str = "tr") -> None:
        self._language = language
        self._ocr: Any = None  # created on first use; model load is expensive

    def _get_ocr(self) -> Any:
        if self._ocr is None:
            from paddleocr import PaddleOCR

            self._ocr = PaddleOCR(lang=self._language, use_angle_cls=True)
        return self._ocr

    def recognize(self, image_png: bytes) -> str:
        import io

        import numpy as np
        from PIL import Image

        image = np.array(Image.open(io.BytesIO(image_png)).convert("RGB"))
        result = self._get_ocr().ocr(image)
        lines: list[str] = []
        for page in result or []:
            for detection in page or []:
                # Each detection is [box, (text, confidence)]
                lines.append(detection[1][0])
        return "\n".join(lines)


class TesseractEngine(OCREngine):
    def __init__(self, language: str = "tur") -> None:
        self._language = language

    def recognize(self, image_png: bytes) -> str:
        import io

        import pytesseract
        from PIL import Image

        image = Image.open(io.BytesIO(image_png))
        return pytesseract.image_to_string(image, lang=self._language).strip()


def create_engine(name: str, language: str = "tr") -> OCREngine:
    """Factory keyed by the ``OCR_ENGINE`` config value."""
    if name == "paddle":
        return PaddleOCREngine(language=language)
    if name == "tesseract":
        # Tesseract uses ISO 639-2 codes ("tur"), Paddle uses "tr".
        return TesseractEngine(language="tur" if language == "tr" else language)
    raise ValueError(f"Unknown OCR engine: {name!r} (expected 'paddle' or 'tesseract')")
