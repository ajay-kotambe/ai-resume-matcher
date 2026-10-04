"""Typed application errors mapped to clean HTTP responses.

Every error carries a machine-readable ``code`` and a user-safe ``message``.
Stack traces and API keys are never surfaced to the frontend.
"""

from __future__ import annotations


class AppError(Exception):
    """Base class for all expected application errors."""

    status_code: int = 400
    code: str = "bad_request"

    def __init__(
        self,
        message: str,
        *,
        details: object | None = None,
        code: str | None = None,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details
        if code:
            self.code = code
        if status_code:
            self.status_code = status_code

    def to_dict(self) -> dict:
        return {
            "success": False,
            "error": self.code,
            "message": self.message,
            "details": self.details,
        }


# --- Resume / PDF ----------------------------------------------------------
class InvalidFileError(AppError):
    status_code = 400
    code = "invalid_file"


class FileTooLargeError(AppError):
    status_code = 413
    code = "file_too_large"


class EmptyFileError(AppError):
    status_code = 400
    code = "empty_file"


class PDFExtractionError(AppError):
    status_code = 422
    code = "pdf_extraction_failed"


class InsufficientTextError(AppError):
    status_code = 422
    code = "insufficient_text"


class NoResumesUploadedError(AppError):
    status_code = 400
    code = "no_resumes_uploaded"


class DuplicateUploadError(AppError):
    status_code = 409
    code = "duplicate_upload"


# --- Job description -------------------------------------------------------
class EmptyJobDescriptionError(AppError):
    status_code = 400
    code = "empty_job_description"


class JobDescriptionTooShortError(AppError):
    status_code = 400
    code = "job_description_too_short"


# --- AI provider -----------------------------------------------------------
class AIProviderError(AppError):
    status_code = 502
    code = "ai_provider_error"


class AITimeoutError(AppError):
    status_code = 504
    code = "ai_timeout"


class AIResponseError(AppError):
    status_code = 502
    code = "ai_invalid_response"


class AIKeyMissingError(AppError):
    status_code = 503
    code = "ai_key_missing"


# --- Embeddings / matching -------------------------------------------------
class EmbeddingError(AppError):
    status_code = 500
    code = "embedding_failed"


class NoCandidatesError(AppError):
    status_code = 404
    code = "no_candidates_found"


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"