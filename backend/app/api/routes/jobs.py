"""Job description analysis."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import EmptyJobDescriptionError, JobDescriptionTooShortError, NotFoundError
from app.db.session import get_db
from app.models.job import JobDescription
from app.schemas.mvp import JobAnalyzeResponse, JobRequirementsOut
from app.services.pipeline import create_job, job_to_payload

router = APIRouter()

MIN_JD_CHARS = 40


class JobAnalyzeRequest(BaseModel):
    job_description: str = Field(
        default="",
        description="Full job description text pasted by the recruiter.",
    )
    use_ai: bool = Field(default=True, description="Disable to force heuristic extraction.")


@router.post("/analyze", response_model=JobAnalyzeResponse, summary="Analyse a job description")
def analyze_job(
    payload: JobAnalyzeRequest,
    db: Annotated[Session, Depends(get_db)],
) -> JobAnalyzeResponse:
    """Extract structured requirements from a job description.

    The original text is always stored verbatim so nothing is lost.
    """

    text = payload.job_description.strip()
    if not text:
        raise EmptyJobDescriptionError(
            "Job description cannot be empty. Paste the full role description."
        )
    if len(text) < MIN_JD_CHARS:
        raise JobDescriptionTooShortError(
            f"Job description is only {len(text)} characters. "
            f"Please provide at least {MIN_JD_CHARS} so requirements can be extracted.",
            details={"length": len(text), "minimum": MIN_JD_CHARS},
        )

    job, analysis = create_job(db, text, use_ai=payload.use_ai)
    db.commit()
    db.refresh(job)

    return JobAnalyzeResponse(
        message=(
            f"Extracted {len(job.required_skills or [])} required and "
            f"{len(job.preferred_skills or [])} preferred skills."
        ),
        job=JobRequirementsOut(**job_to_payload(job, warning=analysis.warning)),
    )


@router.get("", response_model=JobAnalyzeResponse, summary="List analysed jobs")
@router.get("/", response_model=JobAnalyzeResponse, include_in_schema=False)
def list_jobs(
    db: Annotated[Session, Depends(get_db)],
    limit: int = 20,
) -> JobAnalyzeResponse:
    jobs = db.execute(select(JobDescription).order_by(JobDescription.created_at.desc()).limit(limit)).scalars().all()
    if not jobs:
        raise NotFoundError("No job descriptions have been analysed yet.")
    latest = jobs[0]
    return JobAnalyzeResponse(
        message=f"{len(jobs)} job description(s) stored.",
        job=JobRequirementsOut(**job_to_payload(latest)),
    )


@router.get("/{job_uid}", response_model=JobAnalyzeResponse, summary="Fetch one analysed job")
def get_job(job_uid: str, db: Annotated[Session, Depends(get_db)]) -> JobAnalyzeResponse:
    job = db.execute(
        select(JobDescription).where(JobDescription.job_uid == job_uid)
    ).scalar_one_or_none()
    if job is None:
        raise NotFoundError(f"Job '{job_uid}' was not found.")
    return JobAnalyzeResponse(message="Job description retrieved.", job=JobRequirementsOut(**job_to_payload(job)))