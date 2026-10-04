"""Analysis pipeline orchestrator.

    PDF Parser -> AI Extraction -> Embedding -> Matching -> Ranking -> Explanation

This is the only module that knows the whole order. Individual steps stay in
their own services so each can be tested and replaced independently.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.core.errors import NoCandidatesError
from app.models.candidate import Candidate
from app.models.job import JobDescription
from app.models.match_result import MatchResult
from app.models.resume import Resume
from app.services.ai_extraction import (
    ExtractionResult,
    education_level_of,
    extract_candidate,
)
from app.services.embedding_service import build_profile_text
from app.services.explanation_service import generate_explanation
from app.services.jd_service import JobAnalysisResult, analyze_job_description
from app.services.matching_service import compute_match
from app.services.ranking_service import rank_breakdowns, summarize
from app.utils.text_utils import normalize_skills

logger = logging.getLogger(__name__)


@dataclass
class PipelineTimings:
    stages: dict[str, int] = field(default_factory=dict)

    def record(self, name: str, started: float) -> None:
        self.stages[name] = int((time.perf_counter() - started) * 1000)

    def as_dict(self) -> dict:
        return dict(self.stages)


# ---------------------------------------------------------------------------
# Resume ingestion
# ---------------------------------------------------------------------------
def build_candidate_from_extraction(
    resume: Resume, extraction: ExtractionResult
) -> Candidate:
    """Create (or refresh) the Candidate row for a resume."""

    data = extraction.data
    skills = normalize_skills(data.get("skills") or [])
    education = data.get("education") or []

    candidate = Candidate(
        candidate_uid=resume.resume_uid.replace("r", "c", 1),
        resume_id=resume.id,
        name=data.get("name") or None,
        email=data.get("email") or None,
        phone=data.get("phone") or None,
        location=data.get("location") or None,
        skills=skills,
        education=education,
        experience=data.get("experience") or [],
        projects=data.get("projects") or [],
        certifications=data.get("certifications") or [],
        skills_flat=Candidate.flat_skills(skills),
        years_of_experience=float(data.get("years_of_experience") or 0.0),
        education_level=education_level_of(education),
        summary=data.get("summary") or None,
        stated_excerpt="; ".join(data.get("stated_skills") or []) or None,
    )
    return candidate


def extract_and_store_candidate(
    db: Session, resume: Resume, *, use_ai: bool = True
) -> tuple[Candidate, ExtractionResult]:
    """Run structured extraction for one resume and persist the candidate."""

    extraction = extract_candidate(resume.raw_text, use_ai=use_ai)

    candidate = (
        db.query(Candidate).filter(Candidate.resume_id == resume.id).one_or_none()
    )
    if candidate is None:
        candidate = build_candidate_from_extraction(resume, extraction)
        db.add(candidate)
    else:
        _update_candidate(candidate, extraction)

    resume.status = "extracted"
    resume.extraction_method = extraction.method
    resume.extraction_latency_ms = extraction.latency_ms
    resume.extraction_cost_tokens = extraction.prompt_tokens + extraction.completion_tokens
    resume.error = extraction.warning

    db.flush()
    return candidate, extraction


def _update_candidate(candidate: Candidate, extraction: ExtractionResult) -> None:
    data = extraction.data
    skills = normalize_skills(data.get("skills") or [])
    education = data.get("education") or []

    candidate.name = data.get("name") or candidate.name
    candidate.email = data.get("email") or candidate.email
    candidate.phone = data.get("phone") or candidate.phone
    candidate.location = data.get("location") or candidate.location
    candidate.skills = skills
    candidate.education = education
    candidate.experience = data.get("experience") or []
    candidate.projects = data.get("projects") or []
    candidate.certifications = data.get("certifications") or []
    candidate.skills_flat = Candidate.flat_skills(skills)
    candidate.years_of_experience = float(data.get("years_of_experience") or 0.0)
    candidate.education_level = education_level_of(education)
    candidate.summary = data.get("summary") or candidate.summary
    candidate.stated_excerpt = "; ".join(data.get("stated_skills") or []) or candidate.stated_excerpt


# ---------------------------------------------------------------------------
# Job analysis
# ---------------------------------------------------------------------------
def create_job(db: Session, jd_text: str, *, use_ai: bool = True) -> tuple[JobDescription, JobAnalysisResult]:
    """Analyse a job description and persist it."""

    analysis = analyze_job_description(jd_text, use_ai=use_ai)
    data = analysis.data

    job = JobDescription(
        raw_text=analysis.raw_text,
        job_title=data.get("job_title") or None,
        company=data.get("company") or None,
        required_skills=data.get("required_skills") or [],
        preferred_skills=data.get("preferred_skills") or [],
        minimum_experience=data.get("minimum_experience") or None,
        minimum_years=float(data.get("minimum_years") or 0.0),
        education_requirements=data.get("education_requirements") or [],
        responsibilities=data.get("responsibilities") or [],
        extraction_method=analysis.method,
        status="analyzed",
    )
    db.add(job)
    db.flush()
    return job, analysis


def job_to_payload(job: JobDescription, warning: str | None = None) -> dict:
    """Serialise a JobDescription row to the API shape."""

    return {
        "job_uid": job.job_uid,
        "job_title": job.job_title,
        "company": job.company,
        "required_skills": job.required_skills or [],
        "preferred_skills": job.preferred_skills or [],
        "minimum_experience": job.minimum_experience,
        "minimum_years": job.minimum_years or 0.0,
        "education_requirements": job.education_requirements or [],
        "responsibilities": job.responsibilities or [],
        "location": None,
        "raw_text": job.raw_text,
        "extraction_method": job.extraction_method,
        "warning": warning,
        "created_at": job.created_at,
    }


# ---------------------------------------------------------------------------
# Matching pipeline
# ---------------------------------------------------------------------------
def run_matching(
    db: Session,
    job: JobDescription,
    resumes: list[Resume],
    *,
    use_ai: bool = True,
    generate_explanations: bool = True,
    reset: bool = True,
) -> tuple[list[tuple[int, MatchResult, Candidate]], dict, dict]:
    """Score, rank, persist and explain. Returns ranked rows + summary + timings."""

    if not resumes:
        raise NoCandidatesError("There are no resumes to match against this job.")

    timings = PipelineTimings()
    job_payload = job_to_payload(job)

    # Remove previous results for this job so re-running is idempotent.
    if reset:
        db.query(MatchResult).filter(MatchResult.job_id == job.id).delete(synchronize_session=False)

    breakdowns = []
    candidates: list[Candidate] = []

    started = time.perf_counter()
    for resume in resumes:
        candidate = (
            db.query(Candidate).filter(Candidate.resume_id == resume.id).one_or_none()
        )
        if candidate is None:
            # Extract on demand for resumes uploaded before this endpoint existed.
            candidate, _ = extract_and_store_candidate(db, resume, use_ai=use_ai)

        candidate_payload = candidate.as_dict()
        candidate_payload["resume_text"] = resume.raw_text

        breakdown = compute_match(candidate_payload, {**job_payload, "raw_text": job.raw_text})
        breakdowns.append((candidate, breakdown))
        candidates.append(candidate)
    timings.record("matching", started)

    # -- rank ---------------------------------------------------------
    started = time.perf_counter()
    ordered = sorted(
        breakdowns,
        key=lambda pair: (
            -pair[1].overall_score,
            -pair[1].skill_score,
            -pair[1].semantic_score,
        ),
    )
    timings.record("ranking", started)

    results: list[tuple[int, MatchResult, Candidate]] = []
    for rank, (candidate, breakdown) in enumerate(ordered, start=1):
        match = MatchResult(
            candidate_id=candidate.id,
            job_id=job.id,
            rank=rank,
            **breakdown.to_dict(),
        )
        db.add(match)
        results.append((rank, match, candidate))

    db.flush()

    # -- explanations --------------------------------------------------
    if generate_explanations:
        started = time.perf_counter()
        for _rank, match, candidate in results:
            try:
                text, method = generate_explanation(
                    candidate.as_dict(),
                    job_payload,
                    match.as_dict(),
                    use_ai=use_ai,
                )
            except Exception as exc:  # noqa: BLE001 - never fail the batch on prose
                logger.warning("Explanation skipped for %s: %s", candidate.candidate_uid, exc)
                text, method = None, "error"
            match.explanation = text
            match.explanation_method = method
        timings.record("explanations", started)

    summary = summarize([(rank, _as_breakdown(m)) for rank, m, _c in results])

    return results, summary, timings.as_dict()


def _as_breakdown(match: MatchResult):
    """Adapt a persisted MatchResult to the shape ``summarize`` expects."""

    class _Shim:
        def __init__(self, m: MatchResult) -> None:
            self.overall_score = m.overall_score
            self.skill_score = m.skill_score
            self.semantic_score = m.semantic_score
            self.evidence_score = m.evidence_score

    return _Shim(match)


def candidate_payload(candidate: Candidate) -> dict:
    """Serialise a Candidate row to the API shape."""

    return {
        "candidate_uid": candidate.candidate_uid,
        "name": candidate.name,
        "email": candidate.email,
        "phone": candidate.phone,
        "location": candidate.location,
        "skills": candidate.skills or [],
        "education": candidate.education or [],
        "experience": candidate.experience or [],
        "projects": candidate.projects or [],
        "certifications": candidate.certifications or [],
        "years_of_experience": candidate.years_of_experience or 0.0,
        "education_level": candidate.education_level or 0,
        "summary": candidate.summary,
    }


def resume_payload(resume: Resume) -> dict:
    """Serialise a Resume row to the API shape."""

    return {
        "resume_uid": resume.resume_uid,
        "original_filename": resume.original_filename,
        "file_size": resume.file_size,
        "page_count": resume.page_count,
        "char_count": resume.char_count,
        "status": resume.status,
        "error": resume.error,
        "extraction_method": resume.extraction_method,
        "content_hash": resume.content_hash,
        "created_at": resume.created_at,
    }


def candidate_profile_text(candidate: Candidate) -> str:
    """Reconstruct the text used for semantic comparison (for the detail view)."""

    return build_profile_text(candidate.as_dict())