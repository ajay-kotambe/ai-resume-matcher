"""Explanation service: natural-language "why this score".

The LLM receives only the deterministic breakdown and may only *describe* it.
The score is never passed back for modification and is re-asserted from the
computed value afterwards. Falls back to a deterministic template builder when
the AI provider is unavailable, so every candidate always has an explanation.
"""

from __future__ import annotations

import logging

from app.core.config import get_settings
from app.core.errors import AIProviderError, AIResponseError, AITimeoutError
from app.services.nvidia_client import get_nvidia_client
from app.utils.text_utils import truncate

logger = logging.getLogger(__name__)

EXPLANATION_SYSTEM_PROMPT = """You are a technical recruiter's assistant.
You explain a candidate's match score to a recruiter.

ABSOLUTE RULES:
1. You MUST NOT recalculate, adjust, question or contradict the score. The score
   is final and was computed by a deterministic engine.
2. Use ONLY the data provided. Never invent skills, experience or education.
3. If a required skill is in "missing_skills", state plainly that it is not found
   in the resume.
4. Mention the strongest matches first, then any gaps, in 2-4 short sentences.
5. Do not use markdown headings, bullet lists or asterisks. Plain prose only.
6. Do not mention percentages you were not given.

Return ONLY a JSON object:
{"explanation": "2-4 sentences of plain prose"}"""


def generate_explanation(
    candidate: dict,
    job: dict,
    breakdown: dict,
    *,
    use_ai: bool = True,
) -> tuple[str, str]:
    """Return ``(explanation_text, method)`` for one candidate.

    ``method`` is ``"ai"`` or ``"template"``.
    """

    settings = get_settings()
    breakdown = breakdown or {}

    if use_ai and settings.nvidia_configured:
        try:
            text = _explain_with_ai(candidate, job, breakdown)
            if text:
                return text, "ai"
        except (AITimeoutError, AIProviderError, AIResponseError) as exc:
            logger.warning("Explanation generation failed: %s", exc.message)
            if not settings.ALLOW_HEURISTIC_FALLBACK:
                raise

    return build_template_explanation(candidate, job, breakdown), "template"


# ---------------------------------------------------------------------------
# AI path
# ---------------------------------------------------------------------------
def _explain_with_ai(candidate: dict, job: dict, breakdown: dict) -> str:
    client = get_nvidia_client()
    client.ensure_ready()

    prompt = _build_prompt(candidate, job, breakdown)
    data, _result = client.chat_json(
        EXPLANATION_SYSTEM_PROMPT, prompt, temperature=0.2, max_tokens=500
    )
    text = str(data.get("explanation") or "").strip()
    # Guard against a model that echoes instructions or returns nonsense.
    if len(text) < 15 or len(text) > 1200:
        raise AIResponseError("Explanation response was out of range.")
    return text


def _build_prompt(candidate: dict, job: dict, breakdown: dict) -> str:
    score = breakdown.get("overall_score", 0)
    parts = [
        "Here is the final, already-calculated match result. Explain it.",
        "",
        f"Candidate: {candidate.get('name') or 'Unknown'}",
        f"Candidate years of experience: {candidate.get('years_of_experience', 0)}",
        f"Candidate skills: {', '.join(candidate.get('skills') or []) or 'none extracted'}",
        "",
        f"Job title: {job.get('job_title') or 'Not specified'}",
        f"Required skills: {', '.join(job.get('required_skills') or []) or 'none stated'}",
        f"Preferred skills: {', '.join(job.get('preferred_skills') or []) or 'none stated'}",
        f"Minimum experience: {job.get('minimum_experience') or 'not stated'}",
        "",
        f"FINAL SCORE (do not change): {score}",
        f"skill_score: {breakdown.get('skill_score', 0)}",
        f"experience_score: {breakdown.get('experience_score', 0)}",
        f"education_score: {breakdown.get('education_score', 0)}",
        f"semantic_score: {breakdown.get('semantic_score', 0)}",
        f"evidence_score: {breakdown.get('evidence_score', 0)}",
        f"matched_skills: {', '.join(breakdown.get('matching_skills') or []) or 'none'}",
        f"partial_skills: {', '.join(breakdown.get('partial_skills') or []) or 'none'}",
        f"missing_skills: {', '.join(breakdown.get('missing_skills') or []) or 'none'}",
        f"substantiated_skills: "
        f"{', '.join((breakdown.get('evidence') or {}).get('evidence_quality', {}).get('substantiated') or []) or 'none'}",
    ]
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Deterministic fallback
# ---------------------------------------------------------------------------
def build_template_explanation(candidate: dict, job: dict, breakdown: dict) -> str:
    """Compose a plain-prose explanation from the breakdown alone."""

    score = round(float(breakdown.get("overall_score") or 0))
    matched = breakdown.get("matching_skills") or []
    partial = breakdown.get("partial_skills") or []
    missing = breakdown.get("missing_skills") or []
    name = candidate.get("name") or "This candidate"

    exp_detail = (breakdown.get("evidence") or {}).get("experience") or {}
    edu_detail = (breakdown.get("evidence") or {}).get("education") or {}
    cand_years = exp_detail.get("candidate_years", 0)
    req_years = exp_detail.get("required_years", 0)

    sentences: list[str] = []

    if score >= 80:
        opener = f"{name} is a strong match with a final score of {score}%"
    elif score >= 60:
        opener = f"{name} is a reasonable match with a final score of {score}%"
    elif score >= 40:
        opener = f"{name} is a partial match with a final score of {score}%"
    else:
        opener = f"{name} is a weak match with a final score of {score}%"

    if matched:
        sentences.append(
            f"{opener}. The resume evidences "
            f"{_natural_list([truncate(m, 40) for m in matched[:6]])}, "
            f"which align with the job's stated requirements."
        )
    else:
        sentences.append(
            f"{opener}. None of the job's required skills could be confirmed in the resume."
        )

    if partial:
        sentences.append(
            f"{_natural_list([truncate(p, 40) for p in partial[:4]])} "
            f"{'are' if len(partial) > 1 else 'is'} mentioned but lack supporting detail."
        )

    if missing:
        sentences.append(
            f"{_natural_list([truncate(m, 40) for m in missing[:5]])} "
            f"{'are' if len(missing) > 1 else 'is'} not found in the resume."
        )
    else:
        sentences.append("No required skills are missing.")

    if req_years:
        if cand_years >= req_years:
            sentences.append(
                f"The candidate has {cand_years} years of experience, meeting the "
                f"{req_years}-year minimum."
            )
        else:
            sentences.append(
                f"The candidate has {cand_years} years of documented experience against a "
                f"{req_years}-year minimum, a shortfall of "
                f"{round(req_years - cand_years, 1)} years."
            )

    if edu_detail.get("required_level"):
        sentences.append(_education_sentence(edu_detail))

    return " ".join(sentences)


def _education_sentence(detail: dict) -> str:
    levels = {
        0: "no formal education",
        1: "secondary education",
        2: "a diploma",
        3: "a bachelor's degree",
        4: "a master's degree",
        5: "a doctorate",
    }
    required = levels.get(detail.get("required_level", 0), "the required education level")
    candidate = levels.get(detail.get("candidate_level", 0), "an unlisted qualification")
    basis = detail.get("basis")
    if basis == "meets_requirement":
        return f"The candidate's education ({candidate}) meets the {required} requirement."
    return f"The candidate's education ({candidate}) is below the {required} requirement."


def _natural_list(items: list[str]) -> str:
    """Render a list as prose: 'a', 'a and b', 'a, b and c'."""

    cleaned = [item for item in items if item]
    if not cleaned:
        return ""
    if len(cleaned) == 1:
        return cleaned[0]
    if len(cleaned) == 2:
        return f"{cleaned[0]} and {cleaned[1]}"
    return ", ".join(cleaned[:-1]) + f" and {cleaned[-1]}"