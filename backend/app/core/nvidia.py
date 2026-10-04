"""NVIDIA NIM configuration (no network access here).

Add the key to ``backend/.env`` (copy ``.env.example``):

    NVIDIA_API_KEY=nvapi-...
    NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
    NVIDIA_MODEL=deepseek-ai/deepseek-v4.1-flash
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from app.core.config import Settings, get_settings


@dataclass(frozen=True)
class NvidiaNIMConfig:
    """Immutable snapshot of the NVIDIA NIM settings."""

    api_key: str
    base_url: str
    chat_model: str
    embedding_model: str
    timeout: int
    max_retries: int

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key.strip())

    @property
    def chat_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/chat/completions"

    @property
    def embeddings_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/embeddings"

    def headers(self) -> dict[str, str]:
        """OpenAI-compatible auth headers."""

        if not self.is_configured:
            raise RuntimeError("NVIDIA_API_KEY is not set. Add it to backend/.env.")
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }


@lru_cache
def get_nvidia_config() -> NvidiaNIMConfig:
    """Build (and cache) the NIM configuration from environment settings."""

    settings: Settings = get_settings()
    return NvidiaNIMConfig(
        api_key=settings.NVIDIA_API_KEY,
        base_url=settings.NVIDIA_BASE_URL,
        chat_model=settings.NVIDIA_MODEL,
        embedding_model=settings.NVIDIA_EMBEDDING_MODEL,
        timeout=settings.NVIDIA_TIMEOUT,
        max_retries=settings.NVIDIA_MAX_RETRIES,
    )