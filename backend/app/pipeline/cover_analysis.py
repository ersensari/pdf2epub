"""LLM-based cover analysis.

The vision model looks at each cover candidate image, decides whether it is a
real book cover, and reads the visible title/author. Same error-tolerance
chain as the other LLM calls: validate with Pydantic → retry once → fall
back to a neutral result. The model name and host are injected — never
hardcoded here.
"""

import base64
from abc import ABC, abstractmethod

from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError

_PROMPT = """Bu resim eski bir Türkçe kitabın kapak adayıdır.

GÖREVİN:
1. Bu gerçek bir kitap kapağı mı? (başlık/yazar/görsel içeren ön kapak = evet;
   boş sayfa, düz metin sayfası, iç sayfa, kütüphane damgası = hayır)
2. Kapakta görünen kitap başlığını oku (görünmüyorsa boş bırak)
3. Kapakta görünen yazar adını oku (görünmüyorsa boş bırak)
4. Karar güvenini 0.0-1.0 arası tahmin et

Değer uydurma — okuyamadığın alanı boş string yap.

Sadece bu JSON formatında cevap ver:
{"is_cover": true/false, "title": "<kapaktaki başlık veya boş>", "author": "<kapaktaki yazar veya boş>", "confidence": <0..1>}"""


class CoverAnalysis(BaseModel):
    """Validation gate for the LLM's cover-analysis JSON."""

    is_cover: bool = False
    title: str = ""
    author: str = ""
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)


class CoverAnalysisBackend(ABC):
    """Interface for cover-analysis backends.

    New backends (another local model, a remote API, ...) subclass this;
    calling code must not change.
    """

    @abstractmethod
    def analyze(self, image_png: bytes) -> CoverAnalysis:
        """Analyze one candidate image. Raises on failure."""


class OpenAICompatibleCoverBackend(CoverAnalysisBackend):
    def __init__(self, host: str, model: str, api_key: str = "") -> None:
        self._model = model
        self._client = OpenAI(base_url=host, api_key=api_key or "not-needed")

    def analyze(self, image_png: bytes) -> CoverAnalysis:
        b64 = base64.b64encode(image_png).decode("ascii")
        response = self._client.chat.completions.create(
            model=self._model,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                        {"type": "text", "text": _PROMPT},
                    ],
                }
            ],
        )
        return CoverAnalysis.model_validate_json(
            response.choices[0].message.content
        )


def analyze_cover(backend: CoverAnalysisBackend, image_png: bytes) -> CoverAnalysis:
    """Analyze one image with the fixed error-tolerance chain.

    Invalid/failed response → one retry → neutral fallback (``is_cover=False``,
    empty fields) instead of failing the job.
    """
    for _ in range(2):  # initial attempt + one retry
        try:
            return backend.analyze(image_png)
        except (ValidationError, ValueError, KeyError, ConnectionError, TimeoutError):
            continue
        except Exception:
            # Ollama client errors don't share a common base; honor the
            # fallback chain rather than killing the whole job.
            continue
    return CoverAnalysis()


def pick_best_cover(
    backend: CoverAnalysisBackend, candidates: list[bytes]
) -> tuple[bytes | None, CoverAnalysis]:
    """Choose the best cover among candidate images.

    Each candidate is analyzed in order (candidates come sorted by heuristic
    quality); the highest-confidence image judged to be a real cover wins.
    If none is judged a cover, the first candidate is kept so the EPUB still
    gets *a* cover image.
    """
    if not candidates:
        return None, CoverAnalysis()

    best: tuple[bytes, CoverAnalysis] | None = None
    for image_png in candidates:
        analysis = analyze_cover(backend, image_png)
        if analysis.is_cover and (best is None or analysis.confidence > best[1].confidence):
            best = (image_png, analysis)

    if best is not None:
        return best

    return candidates[0], CoverAnalysis()
