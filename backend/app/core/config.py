"""Application configuration loaded from environment variables.

All secrets (e.g. NVIDIA_API_KEY) are read from a ``.env`` file or the process
environment. Never hardcode credentials in source control.
"""

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central application settings."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Application ---------------------------------------------------
    PROJECT_NAME: str = "AI Resume & Job Matching System"
    VERSION: str = "0.1.0"
    DESCRIPTION: str = (
        "Hackathon MVP: parse resumes, embed job descriptions and match "
        "candidates to roles using NVIDIA NIM + sentence-transformers."
    )
    API_V1_PREFIX: str = "/api"
    ENVIRONMENT: str = Field(default="development")
    DEBUG: bool = Field(default=True)

    # --- Server --------------------------------------------------------
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    RELOAD: bool = True

    # --- CORS ----------------------------------------------------------
    # Comma-separated list of allowed origins (parsed by cors_origins_list).
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    # --- Database ------------------------------------------------------
    DATABASE_URL: str = "sqlite:///./app.db"
    SQL_ECHO: bool = False

    # --- NVIDIA NIM (OpenAI-compatible) --------------------------------
    NVIDIA_API_KEY: str = ""
    NVIDIA_BASE_URL: str = "https://integrate.api.nvidia.com/v1"
    NVIDIA_MODEL: str = "deepseek-ai/deepseek-v4.1-flash"
    NVIDIA_EMBEDDING_MODEL: str = "nvidia/nv-embedqa-e5-v5"
    NVIDIA_TIMEOUT: int = 300
    NVIDIA_MAX_RETRIES: int = 3

    # When no API key is configured the extraction service falls back to the
    # deterministic regex heuristic so the demo keeps working offline.
    ALLOW_HEURISTIC_FALLBACK: bool = True

    # --- Embeddings (sentence-transformers, local) ---------------------
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_DIMENSION: int = 384

    # --- Resume processing ---------------------------------------------
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE_MB: int = 10
    MIN_EXTRACTABLE_CHARS: int = 50

    # --- Matching weights (must sum to 100) -----------------------------
    # Kept in config so scoring is transparent and tunable, never hardcoded.
    WEIGHT_SKILL: float = 40.0
    WEIGHT_EXPERIENCE: float = 25.0
    WEIGHT_EDUCATION: float = 15.0
    WEIGHT_SEMANTIC: float = 10.0
    WEIGHT_EVIDENCE: float = 10.0

    @field_validator("DEBUG", "RELOAD", "SQL_ECHO", mode="before")
    @classmethod
    def _as_bool(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return value

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse ``CORS_ORIGINS`` into a list of allowed origins."""

        if isinstance(self.CORS_ORIGINS, str):
            return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]
        return list(self.CORS_ORIGINS)

    @property
    def nvidia_configured(self) -> bool:
        """True when an NVIDIA NIM API key is present."""
        return bool(self.NVIDIA_API_KEY.strip())

    def nvidia_chat_url(self) -> str:
        return f"{self.NVIDIA_BASE_URL.rstrip('/')}/chat/completions"

    @property
    def weights(self) -> dict[str, float]:
        """Scoring weights as a name -> percentage mapping."""

        return {
            "skill": self.WEIGHT_SKILL,
            "experience": self.WEIGHT_EXPERIENCE,
            "education": self.WEIGHT_EDUCATION,
            "semantic": self.WEIGHT_SEMANTIC,
            "evidence": self.WEIGHT_EVIDENCE,
        }

    def max_upload_bytes(self) -> int:
        """Maximum accepted upload size in bytes."""

        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (FastAPI dependency)."""

    return Settings()


settings = get_settings()