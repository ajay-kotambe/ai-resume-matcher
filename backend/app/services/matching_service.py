"""Deterministic matching engine.

The LLM never produces the score. Every number below is computed from the
structured candidate data, the structured job requirements and the embedding
similarity, using fixed rules so results are fully reproducible.

Default weights (configurable in .env):
    skill 40% | experience 25% | education 15% | semantic 10% | evidence 10%
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.core.config import get_settings
from app.services.ai_extraction import education_level_of
from app.services.embedding_service import build_profile_text, semantic_similarity
from app.services.jd_service import required_education_level
from app.utils.text_utils import skills_match, tokenize

logger = logging.getLogger(__name__)

# Skills whose presence in a project/experience blurb implies weaker evidence.
WEAK_SKILL_TOKENS = {
    "machine learning", "deep learning", "artificial intelligence", "data science",
    "ci/cd", "rest api", "test automation",
}


@dataclass
class MatchBreakdown:
    """Deterministic score components for one candidate/job pair."""

    overall_score: float
    skill_score: float
    experience_score: float
    education_score: float
    semantic_score: float
    evidence_score: float

    matching_skills: list[str] = field(default_factory=list)
    partial_skills: list[str] = field(default_factory=list)
    missing_skills: list[str] = field(default_factory=list)
    extra_skills: list[str] = field(default_factory=list)
    evidence: dict = field(default_factory=dict)
    weights: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "overall_score": round(self.overall_score, 2),
            "skill_score": round(self.skill_score, 2),
            "experience_score": round(self.experience_score, 2),
            "education_score": round(self.education_score, 2),
            "semantic_score": round(self.semantic_score, 2),
            "evidence_score": round(self.evidence_score, 2),
            "matching_skills": self.matching_skills,
            "partial_skills": self.partial_skills,
            "missing_skills": self.missing_skills,
            "extra_skills": self.extra_skills,
            "evidence": self.evidence,
            "weights": self.weights,
        }


# ---------------------------------------------------------------------------
# Component scorers
# ---------------------------------------------------------------------------
def score_skills(candidate_skills: list[str], job: dict) -> tuple[float, dict]:
    """Skill score.

    * Every matched required skill          -> full credit
    * A required skill found only in the JD-independent text (weak signal) -> partial
    * Preferred skills                       -> bonus credit, capped at 100
    * A candidate with no listed skills     -> 0 (cannot be credited)
    """

    required = [s for s in (job.get("required_skills") or []) if s]
    preferred = [s for s in (job.get("preferred_skills") or []) if s]
    candidate_skills = [s for s in (candidate_skills or []) if s]

    matched: list[str] = []
    partial: list[str] = []
    missing: list[str] = []
    extra: list[str] = []

    for skill in required:
        if any(skills_match(skill, cs) for cs in candidate_skills):
            matched.append(skill)
        else:
            missing.append(skill)

    # A skill mentioned in the resume body but absent from the extracted list is
    # a *partial* match: present, but not confirmed as a core skill.
    haystack = job.get("_resume_haystack", "")
    for skill in missing:
        if _mentioned_in_text(skill, haystack):
            partial.append(skill)

    required_set = {s.lower() for s in required} | {s.lower() for s in preferred}
    for skill in candidate_skills:
        if not any(skills_match(skill, other) for other in required + preferred):
            extra.append(skill)

    if required:
        base = 85.0 * (len(matched) / len(required))
        base += 15.0 * (len(partial) / len(required))
    else:
        # No explicit requirements: reward breadth instead of penalising.
        base = min(70.0, 25.0 * len(candidate_skills))

    if preferred:
        preferred_matched = sum(
            1 for skill in preferred if any(skills_match(skill, cs) for cs in candidate_skills)
        )
        bonus = 15.0 * (preferred_matched / len(preferred))
    else:
        bonus = 0.0

    score = max(0.0, min(100.0, base + bonus))

    return score, {
        "matching_skills": matched,
        "partial_skills": partial,
        "missing_skills": [s for s in missing if s not in partial],
        "extra_skills": extra,
        "required_total": len(required),
        "required_matched": len(matched),
        "required_partial": len(partial),
        "preferred_total": len(preferred),
    }


def score_experience(candidate_years: float, job: dict) -> tuple[float, dict]:
    """Experience score against the JD's stated minimum years."""

    required_years = float(job.get("minimum_years") or 0.0)
    candidate_years = max(0.0, float(candidate_years or 0.0))

    if required_years <= 0:
        # No minimum stated: award a neutral-but-favourable score that rewards
        # any documented experience without inventing a threshold.
        score = 100.0 if candidate_years >= 1 else (70.0 if candidate_years > 0 else 40.0)
        return score, {
            "candidate_years": candidate_years,
            "required_years": 0.0,
            "basis": "no_minimum_stated",
        }

    ratio = candidate_years / required_years
    if ratio >= 1.0:
        # Meet or exceed: full credit, capped so it never exceeds 100.
        score = 100.0
    else:
        # Linear ramp on the shortfall.
        score = max(0.0, ratio * 100.0)

    return round(score, 2), {
        "candidate_years": candidate_years,
        "required_years": required_years,
        "ratio": round(ratio, 3),
        "basis": "years_ratio",
    }


def score_education(candidate_education: list, job: dict) -> tuple[float, dict]:
    """Education score from the highest level reached vs the level required."""

    candidate_level = education_level_of(candidate_education)
    required_level = required_education_level(job.get("education_requirements") or [])

    if required_level <= 0:
        score = 100.0 if candidate_level >= 3 else (80.0 if candidate_level > 0 else 50.0)
        basis = "no_requirement_stated"
    elif candidate_level >= required_level:
        score = 100.0
        basis = "meets_requirement"
    else:
        gap = required_level - candidate_level
        score = max(0.0, 100.0 - (gap * 45.0))
        basis = "below_requirement"

    return round(score, 2), {
        "candidate_level": candidate_level,
        "required_level": required_level,
        "basis": basis,
    }


def score_evidence(candidate: dict, matched_skills: list[str]) -> tuple[float, dict]:
    """Evidence quality: how well the claimed skills are actually substantiated.

    Rewards skills that appear inside concrete experience/project/education text
    rather than only in a flat skills list. Deterministic, no LLM.
    """

    matched = [s for s in matched_skills if s]
    if not matched:
        return 0.0, {"substantiated": [], "unsubstantiated": [], "basis": "no_matched_skills"}

    body_parts: list[str] = []
    for key in ("experience", "projects", "education", "certifications"):
        for entry in candidate.get(key) or []:
            if isinstance(entry, dict):
                body_parts.extend(str(value) for value in entry.values())
            elif entry:
                body_parts.append(str(entry))
    body = " ".join(body_parts).lower()
    body_tokens = set(tokenize(body))

    summary_text = str(candidate.get("summary") or "").lower()

    substantiated: list[str] = []
    unsubstantiated: list[str] = []
    for skill in matched:
        skill_tokens = set(tokenize(skill))
        if skill_tokens and skill_tokens.issubset(body_tokens):
            substantiated.append(skill)
        elif _mentioned_in_text(skill, body):
            substantiated.append(skill)
        elif _mentioned_in_text(skill, summary_text):
            substantiated.append(skill)
        else:
            unsubstantiated.append(skill)

    if len(substantiated) == len(matched):
        score = 100.0
    else:
        score = 100.0 * (len(substantiated) / len(matched))

    return round(score, 2), {
        "substantiated": substantiated,
        "unsubstantiated": unsubstantiated,
        "basis": "skill_support_ratio",
    }


def _mentioned_in_text(skill: str, haystack: str) -> bool:
    """True when the skill (or a distinctive part of it) appears in the text."""

    if not haystack or not skill:
        return False
    haystack = f" {haystack.lower()} "
    skill = skill.lower()
    if skill in haystack:
        return True
    tokens = [t for t in tokenize(skill) if len(t) > 2 and t not in WEAK_SKILL_TOKENS]
    if not tokens:
        return False
    # Require the distinctive token (e.g. "kubernetes" from "docker kubernetes").
    return all(token in haystack for token in tokens)


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------
def compute_match(candidate: dict, job: dict) -> MatchBreakdown:
    """Compute the full deterministic breakdown for one candidate.

    ``candidate`` expects the keys produced by ``Candidate.as_dict()`` plus an
    optional ``resume_text``. ``job`` expects the keys produced by
    ``JobAnalysisResult.data``.
    """

    settings = get_settings()
    weights = settings.weights

    candidate_skills = list(candidate.get("skills") or [])

    # Resume body is used for partial-skill detection and evidence scoring.
    enriched_job = dict(job)
    enriched_job["_resume_haystack"] = str(candidate.get("resume_text") or "")

    skill_score, skill_detail = score_skills(candidate_skills, enriched_job)
    experience_score, experience_detail = score_experience(
        candidate.get("years_of_experience"), job
    )
    education_score, education_detail = score_education(
        candidate.get("education"), job
    )
    evidence_score, evidence_detail = score_evidence(
        candidate, skill_detail["matching_skills"]
    )

    profile_text = build_profile_text(candidate)
    jd_text = str(job.get("raw_text") or "") or _job_fallback_text(job)
    semantic_score = semantic_similarity(profile_text, jd_text)

    overall = (
        skill_score * weights["skill"]
        + experience_score * weights["experience"]
        + education_score * weights["education"]
        + semantic_score * weights["semantic"]
        + evidence_score * weights["evidence"]
    ) / 100.0

    evidence = {
        "skills": skill_detail,
        "experience": experience_detail,
        "education": education_detail,
        "evidence_quality": evidence_detail,
        "semantic": {
            "candidate_profile_chars": len(profile_text),
            "job_text_chars": len(jd_text),
            "similarity": semantic_score,
        },
    }

    return MatchBreakdown(
        overall_score=round(max(0.0, min(100.0, overall)), 2),
        skill_score=skill_score,
        experience_score=experience_score,
        education_score=education_score,
        semantic_score=semantic_score,
        evidence_score=evidence_score,
        matching_skills=skill_detail["matching_skills"],
        partial_skills=skill_detail["partial_skills"],
        missing_skills=skill_detail["missing_skills"],
        extra_skills=skill_detail["extra_skills"],
        evidence=evidence,
        weights=weights,
    )


def _job_fallback_text(job: dict) -> str:
    """Rebuild a comparable job text when raw_text is unavailable."""

    parts: list[str] = []
    if job.get("job_title"):
        parts.append(str(job["job_title"]))
    required = job.get("required_skills") or []
    if required:
        parts.append("Required skills: " + ", ".join(required))
    preferred = job.get("preferred_skills") or []
    if preferred:
        parts.append("Preferred skills: " + ", ".join(preferred))
    for responsibility in job.get("responsibilities") or []:
        parts.append(str(responsibility))
    return "\n".join(parts)