"""Resume upload and management."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import (
    AppError,
    DuplicateUploadError,
    EmptyFileError,
    NoResumesUploadedError,
)
from app.db.session import get_db
from app.models.candidate import Candidate
from app.models.resume import Resume
from app.schemas.mvp import (
    DeleteResponse,
    ResumeListResponse,
    ResumeUploadResponse,
    ResumeWithCandidate,
)
from app.services.pipeline import (
    candidate_payload,
    extract_and_store_candidate,
    resume_payload,
)
from app.services.pdf_parser import parse_resume_upload

logger = logging.getLogger(__name__)
router = APIRouter()

ALLOWED_SUFFIXES = {".pdf", ".txt", ".md"}


@router.post(
    "/upload",
    response_model=ResumeUploadResponse,
    summary="Upload one or more resumes",
)
async def upload_resumes(
    files: Annotated[list[UploadFile], File(description="PDF resumes (.pdf, .txt, .md)")],
    db: Annotated[Session, Depends(get_db)],
) -> ResumeUploadResponse:
    """Accept a batch of resumes, extract text, and store structured candidates.

    A single bad file never fails the whole batch: per-file errors are returned
    in ``errors`` while the successful files are still processed.
    """

    if not files:
        raise NoResumesUploadedError("No files were received. Attach at least one resume.")

    stored, errors = await _ingest_files(db, files)
    db.commit()

    message = (
        f"Processed {len(stored)} resume{'s' if len(stored) != 1 else ''}."
        if stored
        else "No resumes could be processed."
    )

    return ResumeUploadResponse(
        message=message,
        uploaded=len(stored),
        failed=len(errors),
        resumes=[resume_payload(resume) for resume in stored],
        errors=errors,
    )


async def _ingest_files(
    db: Session, files: list[UploadFile]
) -> tuple[list[Resume], list[dict]]:
    """Validate, extract and persist each file.

    Returns ``(resume_rows, errors)``. Shared by the upload endpoint and the
    one-shot matching endpoint so both behave identically.
    """

    stored: list[Resume] = []
    errors: list[dict] = []

    for upload in files:
        filename = upload.filename or "unnamed"
        try:
            data = await upload.read()
            if not data:
                raise EmptyFileError(f"'{filename}' is empty (0 bytes).")

            document = parse_resume_upload(data, filename)

            # Duplicate detection on content hash, not filename.
            existing = db.execute(
                select(Resume).where(Resume.content_hash == document.content_hash)
            ).scalar_one_or_none()
            if existing is not None:
                raise DuplicateUploadError(
                    f"'{filename}' has already been uploaded "
                    f"(resume {existing.resume_uid[:8]}).",
                    details={"existing_resume_uid": existing.resume_uid},
                )

            resume = Resume(
                resume_uid=document.resume_uid,
                original_filename=document.original_filename,
                stored_path=document.stored_path,
                content_hash=document.content_hash,
                file_size=document.file_size,
                page_count=document.page_count,
                char_count=document.char_count,
                raw_text=document.text,
                status="extracted",
            )
            db.add(resume)
            db.flush()

            # Extract structured info now so the candidate is immediately usable.
            extract_and_store_candidate(db, resume)
            db.flush()

            stored.append(resume)
            logger.info(
                "Uploaded %s (%s pages, %s chars)",
                document.original_filename,
                document.page_count,
                document.char_count,
            )

        except AppError as exc:
            db.rollback()
            errors.append({"filename": filename, **exc.to_dict()})
            logger.info("Rejected %s: %s", filename, exc.message)
        except Exception as exc:  # noqa: BLE001 - isolate unexpected per-file failures
            db.rollback()
            logger.exception("Unexpected error processing %s", filename)
            errors.append(
                {
                    "filename": filename,
                    "success": False,
                    "error": "processing_failed",
                    "message": f"Could not process '{filename}'.",
                    "details": {"reason": type(exc).__name__},
                }
            )
        finally:
            await upload.close()

    return stored, errors


@router.get("", response_model=ResumeListResponse, summary="List stored resumes")
@router.get("/", response_model=ResumeListResponse, include_in_schema=False)
def list_resumes(
    db: Annotated[Session, Depends(get_db)],
    limit: int = 200,
    offset: int = 0,
) -> ResumeListResponse:
    resumes = (
        db.execute(select(Resume).order_by(Resume.created_at.desc()).offset(offset).limit(limit))
        .scalars()
        .all()
    )

    payload: list[ResumeWithCandidate] = []
    for resume in resumes:
        candidate = db.execute(
            select(Candidate).where(Candidate.resume_id == resume.id)
        ).scalar_one_or_none()
        payload.append(
            ResumeWithCandidate(
                resume=resume_payload(resume),
                candidate=candidate_payload(candidate) if candidate else None,
            )
        )

    total = db.execute(select(Resume.id)).scalars().all()
    return ResumeListResponse(total=len(total), resumes=payload)


@router.delete("", response_model=DeleteResponse, summary="Clear all stored resumes")
@router.delete("/", response_model=DeleteResponse, include_in_schema=False)
def delete_all_resumes(db: Annotated[Session, Depends(get_db)]) -> DeleteResponse:
    count = len(db.execute(select(Resume.id)).scalars().all())
    # MatchResult/Candidate rows cascade via the ForeignKey definitions.
    db.query(Candidate).delete(synchronize_session=False)
    db.query(Resume).delete(synchronize_session=False)
    db.commit()
    return DeleteResponse(message=f"Deleted {count} resume(s).", deleted=count)