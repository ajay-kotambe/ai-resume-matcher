"""Candidate search, filtering and detail retrieval.

Search and filters run in SQL against the processed candidate/match data, not on
frontend text.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import NoCandidatesError, NotFoundError
from app.db.session import get_db
from app.models.candidate import Candidate
from app.models.job import JobDescription
from app.models.match_result import MatchResult
from app.models.resume import Resume
from app.schemas.mvp import (
    CandidateDetailResponse,
    CandidateListResponse,
    CandidateOut,
    JobRequirementsOut,
    MatchedCandidate,
    ResumeOut,
    ScoreBreakdown,
)
from app.services.pipeline import candidate_payload, job_to_payload, resume_payload
from app.services.ranking_service import summarize

router = APIRouter()


@router.get("", response_model=CandidateListResponse, summary="Search and filter candidates")
@router.get("/", response_model=CandidateListResponse, include_in_schema=False)
def list_candidates(
    db: Annotated[Session, Depends(get_db)],
    q: Annotated[str | None, Query(description="Search name, skill or email")] = None,
    min_score: Annotated[float | None, Query(ge=0, le=100)] = None,
    max_score: Annotated[float | None, Query(ge=0, le=100)] = None,
    skills: Annotated[str | None, Query(description="Comma-separated skills; ALL must match")] = None,
    min_experience: Annotated[float | None, Query(ge=0)] = None,
    education_level: Annotated[int | None, Query(ge=0, le=5)] = None,
    sort: Annotated[str, Query(pattern="^(score|name|experience)$")] = "score",
    order: Annotated[str, Query(pattern="^(asc|desc)$")] = "desc",
    job_uid: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> CandidateListResponse:
    """Return ranked candidates with optional search and filters."""

    job = _latest_job(db, job_uid)

    statement = (
        select(Candidate, Resume, MatchResult)
        .join(Resume, Resume.id == Candidate.resume_id)
        .outerjoin(MatchResult, MatchResult.candidate_id == Candidate.id)
    )

    if job is not None:
        statement = statement.where(MatchResult.job_id == job.id)

    # -- text search: name / email / skill ---------------------------
    if q and q.strip():
        needle = f"%{q.strip().lower()}%"
        statement = statement.where(
            or_(
                func.lower(Candidate.name).like(needle),
                func.lower(Candidate.email).like(needle),
                func.lower(Candidate.skills_flat).like(needle),
            )
        )

    # -- skill filter (all requested skills must be present) --------
    # ``skills_flat`` is a lowercase space-joined token list, so match on
    # padded boundaries. A bare LIKE '%java%' would wrongly match
    # "javascript".
    padded_skills = Candidate.skills_flat + " "
    if skills and skills.strip():
        for skill in [s.strip().lower() for s in skills.split(",") if s.strip()]:
            statement = statement.where(padded_skills.like(f"% {skill} %"))

    # -- numeric / level filters -------------------------------------
    if min_experience is not None:
        statement = statement.where(Candidate.years_of_experience >= min_experience)
    if education_level is not None:
        statement = statement.where(Candidate.education_level >= education_level)
    if min_score is not None:
        statement = statement.where(MatchResult.overall_score >= min_score)
    if max_score is not None:
        statement = statement.where(MatchResult.overall_score <= max_score)

    rows = db.execute(statement).all()

    pairs: list[tuple[Candidate, Resume, MatchResult | None]] = []
    for candidate, resume, match in rows:
        pairs.append((candidate, resume, match))

    if not pairs:
        raise NoCandidatesError(
            "No candidates matched your search and filters.",
            details={
                "q": q,
                "skills": skills,
                "min_score": min_score,
                "min_experience": min_experience,
                "education_level": education_level,
            },
        )

    # -- sorting -------------------------------------------------------
    key_map = {
        "score": lambda p: (p[2].overall_score if p[2] else -1.0),
        "name": lambda p: (p[0].name or "zzz").lower(),
        "experience": lambda p: (p[0].years_of_experience or 0.0),
    }
    reverse = order == "desc"
    if sort == "name":
        # Names read best A->Z even when "desc" is requested for scores.
        pairs.sort(key=lambda p: (p[0].name or "zzz").lower())
    else:
        pairs.sort(key=key_map[sort], reverse=reverse)

    total = len(pairs)
    page = pairs[offset : offset + limit]

    payloads: list[MatchedCandidate] = []
    for index, (candidate, resume, match) in enumerate(page, start=offset + 1):
        match_dict = (
            match.as_dict()
            if match
            else ScoreBreakdown(
                overall_score=0, skill_score=0, experience_score=0,
                education_score=0, semantic_score=0, evidence_score=0,
            ).model_dump()
        )
        payloads.append(
            MatchedCandidate(
                rank=index,
                candidate=candidate_payload(candidate),
                resume=resume_payload(resume),
                match=ScoreBreakdown(**match_dict),
                explanation=match.explanation if match else None,
                explanation_method=match.explanation_method if match else None,
            )
        )

    scored = [
        (index, _ScoreShim(match.overall_score if match else 0.0))
        for index, (candidate, resume, match) in enumerate(pairs, start=1)
    ]

    return CandidateListResponse(
        total=total,
        returned=len(payloads),
        summary=summarize(scored),
        filters_applied={
            "q": q,
            "min_score": min_score,
            "max_score": max_score,
            "skills": skills,
            "min_experience": min_experience,
            "education_level": education_level,
            "sort": sort,
            "order": order,
            "job_uid": job_uid,
        },
        available_skills=_available_skills(db),
        candidates=payloads,
    )


@router.get(
    "/{candidate_uid}",
    response_model=CandidateDetailResponse,
    summary="Candidate detail with evidence and explanation",
)
def get_candidate(
    candidate_uid: str,
    db: Annotated[Session, Depends(get_db)],
    job_uid: Annotated[str | None, Query()] = None,
) -> CandidateDetailResponse:
    candidate = db.execute(
        select(Candidate).where(Candidate.candidate_uid == candidate_uid)
    ).scalar_one_or_none()
    if candidate is None:
        raise NotFoundError(f"Candidate '{candidate_uid}' was not found.")

    resume = db.execute(
        select(Resume).where(Resume.id == candidate.resume_id)
    ).scalar_one()

    match_statement = select(MatchResult).where(MatchResult.candidate_id == candidate.id)
    job = _latest_job(db, job_uid)
    if job is not None:
        match_statement = match_statement.where(MatchResult.job_id == job.id)
    match = db.execute(
        match_statement.order_by(MatchResult.created_at.desc()).limit(1)
    ).scalar_one_or_none()

    return CandidateDetailResponse(
        candidate=CandidateOut(**candidate_payload(candidate)),
        resume=ResumeOut(**resume_payload(resume)),
        resume_text=resume.raw_text,
        evidence={"extraction_method": resume.extraction_method, "content_hash": resume.content_hash},
        match=ScoreBreakdown(**match.as_dict()) if match else None,
        explanation=match.explanation if match else None,
        explanation_method=match.explanation_method if match else None,
        job=JobRequirementsOut(**job_to_payload(job)) if job else None,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
class _ScoreShim:
    """Minimal object exposing ``overall_score`` for ``summarize``."""

    __slots__ = ("overall_score", "skill_score", "semantic_score", "evidence_score")

    def __init__(self, score: float) -> None:
        self.overall_score = score
        self.skill_score = 0.0
        self.semantic_score = 0.0
        self.evidence_score = 0.0


def _latest_job(db: Session, job_uid: str | None) -> JobDescription | None:
    if job_uid:
        return db.execute(
            select(JobDescription).where(JobDescription.job_uid == job_uid)
        ).scalar_one_or_none()
    return db.execute(
        select(JobDescription).order_by(JobDescription.created_at.desc()).limit(1)
    ).scalar_one_or_none()


def _available_skills(db: Session) -> list[str]:
    """Distinct skills across all candidates, for the filter dropdown."""

    counts: dict[str, int] = {}
    for (skills_flat,) in db.execute(select(Candidate.skills_flat)).all():
        for skill in (skills_flat or "").split():
            if skill:
                counts[skill] = counts.get(skill, 0) + 1
    return [skill for skill, _count in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]