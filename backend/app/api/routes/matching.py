"""Matching orchestration: score + rank + explain every candidate."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import EmptyJobDescriptionError, NoResumesUploadedError, NotFoundError
from app.db.session import get_db
from app.models.job import JobDescription
from app.models.resume import Resume
from app.schemas.mvp import (
    JobRequirementsOut,
    MatchAnalyzeRequest,
    MatchAnalyzeResponse,
    MatchedCandidate,
    ScoreBreakdown,
)
from app.services.pipeline import (
    candidate_payload,
    create_job,
    job_to_payload,
    resume_payload,
    run_matching,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/analyze",
    response_model=MatchAnalyzeResponse,
    summary="Match all stored resumes against a job description",
)
def analyze_matching(
    payload: MatchAnalyzeRequest,
    db: Annotated[Session, Depends(get_db)],
    job_uid: Annotated[str | None, Query(description="Analyse a previously stored job.")] = None,
) -> MatchAnalyzeResponse:
    """Score, rank, persist and explain candidates for a job.

    Requires that resumes have already been uploaded via
    ``POST /api/resumes/upload``.
    """

    settings = get_settings()

    resumes = _select_resumes(db, payload.resume_uids)
    if not resumes:
        raise NoResumesUploadedError(
            "No resumes found. Upload at least one resume before running matching."
        )

    job = _resolve_job(db, job_uid)
    results, summary, timings = run_matching(
        db, job, resumes, use_ai=payload.use_ai
    )
    db.commit()

    candidates_payload = []
    for rank, match, candidate in results:
        db.refresh(match)
        resume = db.execute(
            select(Resume).where(Resume.id == candidate.resume_id)
        ).scalar_one()
        candidates_payload.append(
            MatchedCandidate(
                rank=rank,
                candidate=candidate_payload(candidate),
                resume=resume_payload(resume),
                match=ScoreBreakdown(**match.as_dict()),
                explanation=match.explanation,
                explanation_method=match.explanation_method,
            )
        )

    return MatchAnalyzeResponse(
        message=f"Analysed {len(resumes)} resume(s) against '{job.job_title or 'the job description'}'.",
        job=JobRequirementsOut(**job_to_payload(job)),
        summary=summary,
        candidates=candidates_payload,
        processing={
            "timings_ms": timings,
            "weights": settings.weights,
            "ai_configured": settings.nvidia_configured,
            "embedding_model": settings.EMBEDDING_MODEL,
        },
    )


@router.post(
    "/analyze-and-upload",
    response_model=MatchAnalyzeResponse,
    summary="Upload resumes + job description in one request",
)
async def analyze_with_upload(
    job_description: Annotated[str, Form(description="Full job description text")],
    files: Annotated[list[UploadFile], File(description="PDF resumes")],
    db: Annotated[Session, Depends(get_db)],
    use_ai: Annotated[bool, Form()] = True,
) -> MatchAnalyzeResponse:
    """One-shot flow used by the dashboard: upload and match in a single call.

    Per-file failures are reported in ``errors`` without aborting the request.
    """

    from app.api.routes.resumes import _ingest_files  # reuse the upload logic

    settings = get_settings()

    text = (job_description or "").strip()
    if not text:
        raise EmptyJobDescriptionError(
            "Job description cannot be empty. Paste the full role description."
        )

    resumes, upload_errors = await _ingest_files(db, files)
    if not resumes:
        # Re-submitting the same files (the normal case when a demo is run
        # twice) hits content-hash duplicate detection. Reuse the stored copies
        # instead of failing the whole batch, so the flow stays repeatable.
        duplicates = [e for e in upload_errors if e.get("error") == "duplicate_upload"]
        resumes = _select_resumes(db, None) if duplicates else []
    if not resumes:
        raise NoResumesUploadedError(
            "None of the uploaded files could be processed.",
            details={"errors": upload_errors},
        )

    job, _analysis = create_job(db, text, use_ai=use_ai)
    results, summary, timings = run_matching(db, job, resumes, use_ai=use_ai)
    db.commit()

    candidates_payload = []
    for rank, match, candidate in results:
        db.refresh(match)
        resume = db.execute(
            select(Resume).where(Resume.id == candidate.resume_id)
        ).scalar_one()
        candidates_payload.append(
            MatchedCandidate(
                rank=rank,
                candidate=candidate_payload(candidate),
                resume=resume_payload(resume),
                match=ScoreBreakdown(**match.as_dict()),
                explanation=match.explanation,
                explanation_method=match.explanation_method,
            )
        )

    return MatchAnalyzeResponse(
        message=f"Matched {len(resumes)} resume(s).",
        job=JobRequirementsOut(**job_to_payload(job)),
        summary=summary,
        candidates=candidates_payload,
        processing={
            "timings_ms": timings,
            "weights": settings.weights,
            "ai_configured": settings.nvidia_configured,
            "embedding_model": settings.EMBEDDING_MODEL,
            "upload_errors": upload_errors,
        },
        errors=upload_errors,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _select_resumes(db: Session, resume_uids: list[str] | None) -> list[Resume]:
    statement = select(Resume).order_by(Resume.created_at.asc())
    if resume_uids:
        statement = statement.where(Resume.resume_uid.in_(resume_uids))
    return list(db.execute(statement).scalars().all())


def _resolve_job(db: Session, job_uid: str | None) -> JobDescription:
    """Fetch the requested job, or create one from stored text if absent."""

    if job_uid:
        job = db.execute(
            select(JobDescription).where(JobDescription.job_uid == job_uid)
        ).scalar_one_or_none()
        if job is None:
            raise NotFoundError(f"Job '{job_uid}' was not found.")
        return job

    latest = db.execute(
        select(JobDescription).order_by(JobDescription.created_at.desc()).limit(1)
    ).scalar_one_or_none()
    if latest is None:
        raise NotFoundError(
            "No job description found. POST to /api/jobs/analyze first."
        )
    return latest