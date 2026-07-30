"""LLM-based OCR correction via OpenAI-compatible API.

For each page the vision model receives the raw OCR text together with the
page image and must answer with structured JSON. The error-tolerance chain is
fixed: validate with Pydantic → retry once on invalid JSON → fall back to the
raw OCR text. Do not weaken it.
"""

import base64
from abc import ABC, abstractmethod

from openai import OpenAI
from pydantic import ValidationError

from ..models import CorrectedBlock, PageResult

_PROMPT_TEMPLATE = """Sen eski bir Türkçe kitabın OCR çıktısını düzeltiyorsun (Latin alfabesi).

Aşağıda ham OCR metni ve sayfa resmi var.
GÖREVİN:
1. OCR hatalarını düzelt (yanlış diyakritikler, bölünmüş/birleşmiş kelimeler, yanlış okunan karakterler)
2. Orijinal ifadeleri sakla — parafraz yapma, dili modernize etme
3. Yazım, noktalama ve gramer hataları düzelt (sadece hata olanlar)
4. Sayfa numarası, tekrarlayan sayfa başlığı/alt bilgisi gibi sayfa düzeni kalıntılarını SİL — bunlar kitap metni değildir
5. Satır sonunda tire ile bölünmüş kelimeleri birleştir
6. Sayfanın ana blok tipini sınıflandır
7. Güven seviyesini tahmin et (0.0-1.0)

ÖNEMLI:
- Hatalı metni düzeltirken orijinal anlamı koru
- Tekrarlanan kelimeler/satırları temizle
- Sayfanın mantığını takip et
- Kitap metnini koru — sadece sayfa düzeni kalıntılarını sil
- Sayfa resmi verildiyse metni resimle karşılaştır: metin katmanında eksik veya
  bozuk geçen kısımları resimden okuyarak tamamla; resimde olmayan çöp
  karakterleri sil

JSON cevap (sadece bu format):
{{"corrected_text": "<tüm sayfa metni, düzeltilmiş>", "block_type": "heading" | "paragraph" | "footnote", "confidence": <float 0..1>}}

Ham OCR metni:
---
{ocr_text}
---"""


class CorrectionBackend(ABC):
    """Interface for OCR-correction backends.

    New backends (another local model, a remote API, ...) subclass this;
    calling code must not change.
    """

    @abstractmethod
    def correct(self, ocr_text: str, image_png: bytes) -> CorrectedBlock:
        """Return the corrected, classified text for one page.

        Raises on failure; retry/fallback policy lives in ``correct_page``.
        """


class OpenAICompatibleCorrectionBackend(CorrectionBackend):
    def __init__(self, host: str, model: str, api_key: str = "") -> None:
        self._model = model
        self._client = OpenAI(base_url=host, api_key=api_key or "not-needed")

    def correct(self, ocr_text: str, image_png: bytes) -> CorrectedBlock:
        # Digital PDFs have no page image; a text-only request is valid and
        # must not send an empty image.
        content: list[dict[str, object]] = [
            {
                "type": "text",
                "text": _PROMPT_TEMPLATE.format(ocr_text=ocr_text),
            }
        ]
        if image_png:
            b64 = base64.b64encode(image_png).decode("ascii")
            content.insert(
                0,
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{b64}"},
                },
            )
        response = self._client.chat.completions.create(
            model=self._model,
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": content}],
        )
        return CorrectedBlock.model_validate_json(
            response.choices[0].message.content
        )


def correct_page(
    backend: CorrectionBackend,
    page_number: int,
    ocr_text: str,
    image_png: bytes,
    *,
    low_confidence_threshold: float = 0.6,
) -> PageResult:
    """Correct one page with the fixed error-tolerance chain.

    Invalid/failed response → one retry → fall back to raw OCR text with
    ``used_fallback=True`` and the page flagged for manual review.
    """
    block: CorrectedBlock | None = None
    for _ in range(2):  # initial attempt + one retry
        try:
            block = backend.correct(ocr_text, image_png)
            break
        except (ValidationError, ValueError, KeyError, ConnectionError, TimeoutError):
            continue
        except Exception:
            # Ollama client errors don't share a common base; still honor
            # the fallback chain rather than killing the whole job.
            continue

    if block is None:
        return PageResult(
            page_number=page_number,
            text=ocr_text,
            confidence=0.0,
            needs_review=True,
            used_fallback=True,
        )

    return PageResult(
        page_number=page_number,
        text=block.corrected_text,
        block_type=block.block_type,
        confidence=block.confidence,
        needs_review=block.confidence < low_confidence_threshold,
    )
