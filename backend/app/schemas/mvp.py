"""Request/response schemas for the MVP API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


class ComponentStatus(BaseModel):
    name: str
    status: str
    detail: str | None = None


class HealthResponse(BaseModel):
    success: bool = True
    status: str
    version: str
    environment: str
    timestamp: datetime
    components: list[ComponentStatus] = Field(default_factory=list)


class StatusResponse(BaseModel):
    success: bool = True
    project: str
    version: str
    environment: str
    integrations: dict[str, dict[str, Any]] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Resumes
# ---------------------------------------------------------------------------


class ResumeOut(BaseModel):
    resume_uid: str
    original_filename: str
    file_size: int
    page_count: int
    char_count: int
    status: str
    error: str | None = None
    extraction_method: str | None = None
    content_hash: str
    created_at: datetime


class ResumeUploadResponse(BaseModel):
    success: bool = True
    message: str
    uploaded: int = 0
    failed: int = 0
    resumes: list[ResumeOut] = Field(default_factory=list)
    errors: list[dict[str, Any]] = Field(default_factory=list)


class CandidateOut(BaseModel):
    candidate_uid: str
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    skills: list[str] = Field(default_factory=list)
    education: list[dict] = Field(default_factory=list)
    experience: list[dict] = Field(default_factory=list)
    projects: list[dict] = Field(default_factory=list)
    certifications: list[dict] = Field(default_factory=list)
    years_of_experience: float = 0.0
    education_level: int = 0
    summary: str | None = None


class ResumeWithCandidate(BaseModel):
    resume: ResumeOut
    candidate: CandidateOut | None = None


class ResumeListResponse(BaseModel):
    success: bool = True
    total: int
    resumes: list[ResumeWithCandidate] = Field(default_factory=list)


class DeleteResponse(BaseModel):
    success: bool = True
    message: str
    deleted: int


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------


class JobRequirementsOut(BaseModel):
    job_uid: str
    job_title: str | None = None
    company: str | None = None
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    minimum_experience: str | None = None
    minimum_years: float = 0.0
    education_requirements: list[str] = Field(default_factory=list)
    responsibilities: list[str] = Field(default_factory=list)
    location: str | None = None
    raw_text: str
    extraction_method: str | None = None
    warning: str | None = None
    created_at: datetime


class JobAnalyzeResponse(BaseModel):
    success: bool = True
    message: str
    job: JobRequirementsOut


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------


class MatchAnalyzeRequest(BaseModel):
    resume_uids: list[str] | None = Field(
        default=None,
        description="Restrict matching to these resume UIDs. Omit to use every stored resume.",
    )
    use_ai: bool = Field(default=True, description="Disable to force deterministic extraction.")


class ScoreBreakdown(BaseModel):
    overall_score: float
    skill_score: float
    experience_score: float
    education_score: float
    semantic_score: float
    evidence_score: float
    matching_skills: list[str] = Field(default_factory=list)
    partial_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    extra_skills: list[str] = Field(default_factory=list)
    evidence: dict[str, Any] = Field(default_factory=dict)
    weights: dict[str, float] = Field(default_factory=dict)


class MatchedCandidate(BaseModel):
    rank: int
    candidate: CandidateOut
    resume: ResumeOut
    match: ScoreBreakdown
    explanation: str | None = None
    explanation_method: str | None = None


class MatchAnalyzeResponse(BaseModel):
    success: bool = True
    message: str
    job: JobRequirementsOut
    summary: dict[str, Any] = Field(default_factory=dict)
    candidates: list[MatchedCandidate] = Field(default_factory=list)
    processing: dict[str, Any] = Field(default_factory=dict)
    errors: list[dict[str, Any]] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Candidates (search + filter)
# ---------------------------------------------------------------------------


class CandidateListResponse(BaseModel):
    success: bool = True
    total: int
    returned: int
    summary: dict[str, Any] = Field(default_factory=dict)
    filters_applied: dict[str, Any] = Field(default_factory=dict)
    available_skills: list[str] = Field(default_factory=list)
    candidates: list[MatchedCandidate] = Field(default_factory=list)


class CandidateDetailResponse(BaseModel):
    success: bool = True
    candidate: CandidateOut
    resume: ResumeOut
    resume_text: str | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)
    match: ScoreBreakdown | None = None
    explanation: str | None = None
    explanation_method: str | None = None
    job: JobRequirementsOut | None = None