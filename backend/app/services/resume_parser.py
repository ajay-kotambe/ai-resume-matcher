"""Resume text extraction placeholder (PyMuPDF).

PHASE 1 (setup only)
--------------------
Uploads directory is created and validated, but PDFs are **not** parsed.
Phase 2 will implement ``extract_text`` with ``fitz`` / ``pymupdf``.
"""

from __future__ import annotations

from pathlib import Path

from app.core.config import settings

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}
TEXT_EXTENSIONS = {".txt", ".md"}


def get_upload_dir() -> Path:
    """Return (and create) the configured upload directory."""

    path = Path(settings.UPLOAD_DIR)
    path.mkdir(parents=True, exist_ok=True)
    return path


def is_allowed(filename: str) -> bool:
    """Check the extension against the allow-list."""

    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS


def extract_text(file_path: str | Path) -> str:
    """Extract raw text from a resume file. Implemented in Phase 2."""

    raise NotImplementedError("PDF/DOCX text extraction is implemented in Phase 2.")