"""Application configuration, read from environment variables / .env."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings.

    The LLM backend is reached via an OpenAI-compatible API (e.g. LiteLLM).
    Neither the host URL nor the model name may be hardcoded anywhere else in
    the codebase.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    llm_host: str = "https://llm.ersensari.com"
    llm_model: str = "gpt-4o"
    llm_api_key: str = ""

    ocr_engine: Literal["paddle", "tesseract"] = "paddle"
    ocr_language: str = "tr"

    render_dpi: int = 300

    # Pages whose LLM confidence falls below this are flagged for manual review.
    low_confidence_threshold: float = 0.6

    # How many leading pages to feed the LLM when PDF metadata is missing.
    metadata_pages: int = 3

    data_dir: Path = Path("data")

    @property
    def upload_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def output_dir(self) -> Path:
        return self.data_dir / "epubs"


@lru_cache
def get_settings() -> Settings:
    return Settings()
