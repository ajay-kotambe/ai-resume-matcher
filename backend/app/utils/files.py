"""Filesystem helpers."""

from __future__ import annotations

from pathlib import Path

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}


def ensure_upload_dir(directory: str | Path | None = None) -> Path:
    """Create and return the uploads directory."""

    if directory is None:
        from app.core.config import settings

        directory = settings.UPLOAD_DIR

    path = Path(directory)
    path.mkdir(parents=True, exist_ok=True)
    return path


def is_allowed_file(filename: str, allowed: set[str] | None = None) -> bool:
    """Return True when the file extension is in the allow-list."""

    allowed = allowed or ALLOWED_EXTENSIONS
    return Path(filename).suffix.lower() in allowed