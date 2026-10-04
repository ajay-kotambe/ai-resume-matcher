"""PDF text extraction with PyMuPDF.

Pipeline:  PDF -> PyMuPDF -> raw text -> clean/normalize -> ExtractedDocument

Handles: multi-page PDFs, empty files, scanned/image-only PDFs (no OCR),
corrupted files, and PDFs with too little extractable text.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from app.core.config import settings
from app.core.errors import (
    EmptyFileError,
    FileTooLargeError,
    InsufficientTextError,
    InvalidFileError,
    PDFExtractionError,
)
from app.utils.text_utils import clean_text

logger = logging.getLogger(__name__)

PDF_MAGIC = b"%PDF"
TEXT_EXTENSIONS = {".txt", ".md"}


@dataclass
class ExtractedDocument:
    """Result of parsing an uploaded resume file."""

    resume_uid: str
    original_filename: str
    stored_path: str | None
    content_hash: str
    text: str
    page_count: int
    file_size: int
    extractor: str = "pymupdf"
    warnings: list[str] = field(default_factory=list)

    @property
    def char_count(self) -> int:
        return len(self.text)


def sha256_of(data: bytes) -> str:
    """Stable content hash used for duplicate detection."""

    return hashlib.sha256(data).hexdigest()


def new_resume_uid() -> str:
    return uuid.uuid4().hex


def validate_extension(filename: str) -> str:
    """Return the validated lowercase extension or raise InvalidFileError."""

    ext = Path(filename or "").suffix.lower()
    allowed = {".pdf", *TEXT_EXTENSIONS}
    if ext not in allowed:
        raise InvalidFileError(
            f"Unsupported file type '{ext or 'unknown'}'. Allowed: PDF, TXT, MD.",
            details={"filename": filename, "allowed": sorted(allowed)},
        )
    return ext


def validate_size(data: bytes, filename: str) -> None:
    """Reject empty files and files above the configured limit."""

    if not data:
        raise EmptyFileError(f"'{filename}' is empty (0 bytes).")
    max_bytes = settings.max_upload_bytes()
    if len(data) > max_bytes:
        raise FileTooLargeError(
            f"'{filename}' is {len(data) / 1024 / 1024:.2f} MB. "
            f"Maximum allowed size is {settings.MAX_UPLOAD_SIZE_MB} MB.",
            details={"size_bytes": len(data), "max_bytes": max_bytes},
        )


def get_upload_dir() -> Path:
    """Create-on-demand upload directory."""

    path = Path(settings.UPLOAD_DIR)
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_upload(data: bytes, filename: str, resume_uid: str) -> Path:
    """Persist the raw upload under ``UPLOAD_DIR/<resume_uid><ext>``."""

    ext = Path(filename).suffix.lower()
    target = get_upload_dir() / f"{resume_uid}{ext}"
    target.write_bytes(data)
    return target


def _looks_like_pdf(data: bytes) -> bool:
    """Sniff the PDF magic bytes to catch renamed/incorrect files early."""

    return data[:1024].lstrip()[:4] == PDF_MAGIC


def extract_text_from_pdf(data: bytes, filename: str) -> tuple[str, int, list[str]]:
    """Extract and clean text from PDF bytes using PyMuPDF.

    Returns ``(text, page_count, warnings)``.
    """

    warnings: list[str] = []

    try:
        import pymupdf  # PyMuPDF >= 1.24 exposes the `pymupdf` name
    except ImportError:  # pragma: no cover - older wheels
        try:
            import fitz as pymupdf  # type: ignore[no-redef]
        except ImportError:  # pragma: no cover
            raise PDFExtractionError(
                "PyMuPDF is not installed. Run: pip install -r requirements.txt"
            ) from None

    if not _looks_like_pdf(data):
        raise InvalidFileError(
            f"'{filename}' is not a valid PDF (missing %PDF header).",
            details={"filename": filename},
        )

    try:
        # `stream` avoids writing user-controlled filenames to disk again.
        document = pymupdf.open(stream=data, filetype="pdf")
    except Exception as exc:  # noqa: BLE001 - fitz raises many types
        logger.warning("PyMuPDF failed to open %s: %s", filename, exc)
        raise PDFExtractionError(
            f"'{filename}' could not be read as a PDF. It may be corrupted.",
            details={"reason": type(exc).__name__},
        ) from exc

    try:
        if getattr(document, "is_encrypted", False) and not document.authenticate(""):
            raise PDFExtractionError(
                f"'{filename}' is password protected. Remove the password and re-upload."
            )

        page_count = document.page_count
        if page_count == 0:
            raise EmptyFileError(f"'{filename}' contains no pages.")

        chunks: list[str] = []
        for page_index in range(page_count):
            try:
                page_text = document.load_page(page_index).get_text("text") or ""
            except Exception as exc:  # noqa: BLE001 - one bad page shouldn't kill the file
                logger.warning("page %s of %s failed: %s", page_index, filename, exc)
                warnings.append(f"page_{page_index + 1}_unreadable")
                continue
            if page_text.strip():
                chunks.append(page_text)

        text = clean_text("\n\n".join(chunks))
        return text, page_count, warnings
    finally:
        document.close()


def extract_text_from_plaintext(data: bytes, filename: str) -> tuple[str, int, list[str]]:
    """Decode a plain-text resume (used for tests and TXT support)."""

    for encoding in ("utf-8", "utf-16", "latin-1"):
        try:
            decoded = data.decode(encoding)
            return clean_text(decoded), 1, []
        except UnicodeDecodeError:
            continue
    raise PDFExtractionError(f"Could not decode '{filename}' as text.")


def parse_resume_upload(data: bytes, filename: str) -> ExtractedDocument:
    """Validate + extract an uploaded resume. The single PDF-parser entrypoint."""

    if not filename or not filename.strip():
        raise InvalidFileError("Filename is missing.")

    validate_size(data, filename)
    ext = validate_extension(filename)

    if ext in TEXT_EXTENSIONS:
        text, pages, warnings = extract_text_from_plaintext(data, filename)
        extractor = "plaintext"
    else:
        text, pages, warnings = extract_text_from_pdf(data, filename)
        extractor = "pymupdf"

    if not text.strip():
        raise InsufficientTextError(
            f"No text could be extracted from '{filename}'. "
            "If it is a scanned image PDF, OCR is required (not supported yet).",
            details={"filename": filename, "page_count": pages},
        )

    if len(text.strip()) < settings.MIN_EXTRACTABLE_CHARS:
        raise InsufficientTextError(
            f"'{filename}' contains too little text "
            f"({len(text.strip())} characters, minimum {settings.MIN_EXTRACTABLE_CHARS}).",
            details={
                "filename": filename,
                "extracted_chars": len(text.strip()),
                "minimum_chars": settings.MIN_EXTRACTABLE_CHARS,
            },
        )

    resume_uid = new_resume_uid()
    stored = save_upload(data, filename, resume_uid)

    return ExtractedDocument(
        resume_uid=resume_uid,
        original_filename=Path(filename).name,
        stored_path=str(stored),
        content_hash=sha256_of(data),
        text=text,
        page_count=pages,
        file_size=len(data),
        extractor=extractor,
        warnings=warnings,
    )