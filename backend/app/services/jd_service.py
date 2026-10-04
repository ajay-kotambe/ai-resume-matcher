"""Job description analysis: raw JD text -> structured requirements.

Primary path: NVIDIA NIM (DeepSeek) with strict JSON output.
Fallback path: deterministic section/bullet parsing (works offline).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from app.core.config import get_settings
from app.core.errors import AIProviderError, AIResponseError, AITimeoutError
from app.services.ai_extraction import (
    _as_float,
    _as_list,
    _normalise_list_of_dicts,
)
from app.services.nvidia_client import AIResult, get_nvidia_client
from app.utils.text_utils import (
    clean_text,
    education_level,
    find_skills,
    normalize_skills,
    truncate,
)

logger = logging.getLogger(__name__)

JOB_SYSTEM_PROMPT = """You are an expert technical recruiter's assistant.
Analyse the job description provided and extract structured requirements.

ABSOLUTE RULES:
1. NEVER invent requirements that are not written in the job description.
2. If something is not stated, return an empty string "" or an empty list [].
3. Put a skill in "required_skills" ONLY if the JD marks it as required
   (e.g. "required", "must have", "minimum qualifications", "you have",
   "requirements", listed under a "Required" heading, or in the minimum
   qualifications section).
4. Put a skill in "preferred_skills" if the JD marks it as nice-to-have
   (e.g. "preferred", "nice to have", "bonus", "plus", "good to have",
   or listed under a "Preferred"/"Nice to have" heading).
5. If you cannot tell, leave the skill out of BOTH lists rather than guessing.
6. Normalize skill variants the same way as a resume: JS -> JavaScript,
   ReactJS -> React, Postgres -> PostgreSQL, K8s -> Kubernetes, etc.
7. For minimum_experience, return the human-readable string exactly as the JD
   phrases it (e.g. "3+ years"). Also return minimum_years as just the number.
8. Preserve the wording of responsibilities by copying the JD bullets closely.

Return ONLY a JSON object with exactly these keys:
{
  "job_title": "",
  "company": "",
  "required_skills": [],
  "preferred_skills": [],
  "minimum_experience": "",
  "minimum_years": 0,
  "education_requirements": [],
  "responsibilities": [],
  "location": "",
  "evidence": {"required_skills": "", "preferred_skills": "", "minimum_experience": ""}
}"""

MIN_YEARS_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*\+?\s*(?:\+\s*)?(?:years?|yrs?)", re.IGNORECASE
)

REQUIRED_MARKERS = (
    "required", "requirement", "must have", "must-have", "minimum qualification",
    "basic qualification", "essential", "you have", "we expect", "you should have",
    "you will have", "you possess", "mandatory", "should have", "need",
)
PREFERRED_MARKERS = (
    "preferred", "nice to have", "nice-to-have", "bonus", "plus", "good to have",
    "desirable", "advantageous", "ideally", "good to see", "a plus", "extra credit",
)


@dataclass
class JobAnalysisResult:
    data: dict
    method: str = "ai"
    latency_ms: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    warning: str | None = None
    raw_text: str = ""
    evidence: dict = field(default_factory=dict)


def analyze_job_description(jd_text: str, *, use_ai: bool = True) -> JobAnalysisResult:
    """Extract structured requirements from a job description."""

    settings = get_settings()
    text = clean_text(jd_text)

    if use_ai and settings.nvidia_configured:
        try:
            data, ai_result = _analyze_with_ai(text)
            return JobAnalysisResult(
                data=_normalise_job(data, text),
                method="ai",
                latency_ms=ai_result.latency_ms,
                prompt_tokens=ai_result.prompt_tokens,
                completion_tokens=ai_result.completion_tokens,
                raw_text=text,
                evidence=data.get("evidence", {}) if isinstance(data.get("evidence"), dict) else {},
            )
        except (AITimeoutError, AIProviderError, AIResponseError) as exc:
            logger.warning("JD analysis failed, using heuristic fallback: %s", exc.message)
            if not settings.ALLOW_HEURISTIC_FALLBACK:
                raise
            fallback = analyze_job_description(text, use_ai=False)
            fallback.warning = exc.message
            return fallback

    data = _analyze_with_heuristics(text)
    return JobAnalysisResult(
        data=data,
        method="heuristic",
        raw_text=text,
        evidence=data.get("evidence", {}),
    )


# ---------------------------------------------------------------------------
# AI path
# ---------------------------------------------------------------------------
def _analyze_with_ai(text: str) -> tuple[dict, AIResult]:
    client = get_nvidia_client()
    client.ensure_ready()

    prompt = (
        "Extract the structured requirements from the job description below.\n"
        "<job_description>\n"
        f"{truncate(text, 12000)}\n"
        "</job_description>"
    )

    data, result = client.chat_json(
        JOB_SYSTEM_PROMPT,
        prompt,
        temperature=0.0,
        max_tokens=3000,
    )
    if not isinstance(data, dict) or not any(
        data.get(key)
        for key in ("job_title", "required_skills", "preferred_skills", "responsibilities")
    ):
        raise AIResponseError(
            "AI response did not contain recognisable job requirements.",
            details={"keys": sorted(data.keys()) if isinstance(data, dict) else None},
        )
    return data, result


# ---------------------------------------------------------------------------
# Heuristic path
# ---------------------------------------------------------------------------
def _analyze_with_heuristics(text: str) -> dict:
    """Split the JD into sections and read required/preferred skills from them."""

    required_block, preferred_block, rest = _split_skill_sections(text)

    required_skills = _skills_in(required_block or rest)
    preferred_skills = _skills_in(preferred_block)

    # Anything preferred that is also required stays required only.
    required_norm = {s.lower() for s in required_skills}
    preferred_skills = [s for s in preferred_skills if s.lower() not in required_norm]

    # If no explicit section markers exist, treat detected skills as required.
    if not required_block and not preferred_block:
        required_skills = _skills_in(text)

    responsibilities = _bullets_in(_section_by_keywords(text, ["responsibilit", "what you will do", "about the role", "the role", "duties"]))
    education_reqs = _bullets_in(_section_by_keywords(text, ["education", "qualification", "degree"]))

    min_years = _max_min_years(text)
    job_title = _guess_job_title(text)
    company = _guess_company(text)
    location = _guess_location(text)

    return {
        "job_title": job_title,
        "company": company,
        "required_skills": required_skills,
        "preferred_skills": preferred_skills,
        "minimum_experience": _experience_phrase(text),
        "minimum_years": min_years,
        "education_requirements": education_reqs,
        "responsibilities": responsibilities,
        "location": location,
        "evidence": {
            "required_skills": ", ".join(required_skills[:15]),
            "preferred_skills": ", ".join(preferred_skills[:15]),
            "minimum_experience": _experience_phrase(text),
        },
    }


def _split_skill_sections(text: str) -> tuple[str, str, str]:
    """Return (required_block, preferred_block, rest_of_text)."""

    lines = text.split("\n")
    required: list[str] = []
    preferred: list[str] = []
    rest: list[str] = []
    current: str | None = None

    header_re = re.compile(r"^(.{2,60}?)\s*[:\-]?\s*$")
    for line in lines:
        value = line.strip()
        if value:
            candidate = header_re.match(value)
            if candidate and len(value) < 60:
                label = value.lower()
                if any(marker in label for marker in PREFERRED_MARKERS):
                    current = "preferred"
                    continue
                if any(marker in label for marker in REQUIRED_MARKERS):
                    current = "required"
                    continue
        if current == "required":
            required.append(value)
        elif current == "preferred":
            preferred.append(value)
        else:
            rest.append(value)

    return "\n".join(required), "\n".join(preferred), "\n".join(rest)


def _section_by_keywords(text: str, keywords: list[str]) -> str:
    """Grab the lines under the first header containing any keyword."""

    lines = text.split("\n")
    for index, line in enumerate(lines):
        value = line.strip().lower().rstrip(":")
        if value and len(value) < 60 and any(keyword in value for keyword in keywords):
            body: list[str] = []
            for following in lines[index + 1 :]:
                candidate = following.strip()
                if not candidate:
                    if body:
                        break
                    continue
                if len(candidate) < 60 and re.match(r"^[A-Z][A-Za-z /&\-]{2,40}\s*:?$", candidate):
                    break
                body.append(candidate)
                if len(body) > 20:
                    break
            if body:
                return "\n".join(body)
    return ""


def _skills_in(text: str) -> list[str]:
    """Detect skills in a block of JD text using word-boundary matching."""

    return normalize_skills(find_skills(text))


def _bullets_in(text: str) -> list[str]:
    """Split a block into bullet-ish lines, dropping the header noise."""

    results: list[str] = []
    for line in text.split("\n"):
        clean = line.strip(" \t-*•\t")
        if len(clean) < 4:
            continue
        results.append(truncate(clean, 300))
        if len(results) >= 20:
            break
    return results


def _max_min_years(text: str) -> float:
    values = [_as_float(v) for v in MIN_YEARS_RE.findall(text)]
    # Ignore noise like "0 years" and absurd values.
    values = [v for v in values if 0 < v <= 25]
    return max(values) if values else 0.0


def _experience_phrase(text: str) -> str:
    for match in re.finditer(
        r"[^\n.]{0,40}?\d+\s*\+?\s*(?:years?|yrs?)[^\n.]{0,40}", text, re.IGNORECASE
    ):
        phrase = match.group(0).strip()
        if any(word in phrase.lower() for word in ("experience", "exp", "background", "work")):
            return truncate(phrase, 64)
    return ""


def _guess_job_title(text: str) -> str:
    for line in text.split("\n")[:5]:
        value = line.strip()
        if not value or len(value) > 90:
            continue
        lowered = value.lower()
        if any(
            marker in lowered
            for marker in ("engineer", "developer", "manager", "scientist", "analyst",
                           "designer", "architect", "lead", "intern", "consultant", "role")
        ):
            return truncate(value, 120)
    return ""


def _guess_company(text: str) -> str:
    for line in text.split("\n")[:6]:
        value = line.strip()
        if not value or len(value) > 80:
            continue
        if re.match(r"(?i)^(about|company|location|job title|position)\s*[:\-]", value):
            return re.sub(r"(?i)^(about|company)\s*[:\-]\s*", "", value).strip()[:120]
        if re.search(r"\b(inc|ltd|llp|pvt|technologies|solutions|labs|software)\b", value, re.IGNORECASE):
            return truncate(value, 120)
    return ""


def _guess_location(text: str) -> str:
    match = re.search(r"(?i)\b(remote|hybrid|on-?site|based in [A-Za-z ,]+)", text)
    if match:
        return truncate(match.group(1).strip(), 120)
    return ""


# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------
def _normalise_job(data: dict, raw_text: str) -> dict:
    """Coerce arbitrary AI output into the canonical job shape."""

    from app.utils.text_utils import normalize_skills

    required = normalize_skills(_as_list(data.get("required_skills")))
    preferred = normalize_skills(_as_list(data.get("preferred_skills")))
    required_set = set(required)
    preferred = [s for s in preferred if s not in required_set]

    min_years = _as_float(data.get("minimum_years"))
    if not min_years:
        min_years = _max_min_years(raw_text)

    phrase = str(data.get("minimum_experience") or "").strip()
    if not phrase:
        phrase = _experience_phrase(raw_text)

    responsibilities_raw = data.get("responsibilities")
    if isinstance(responsibilities_raw, (list, tuple)) and all(
        isinstance(item, str) for item in responsibilities_raw
    ):
        responsibilities = _as_list(responsibilities_raw)
    else:
        responsibilities = _as_list(_normalise_list_of_dicts(responsibilities_raw))

    evidence = data.get("evidence") if isinstance(data.get("evidence"), dict) else {}

    return {
        "job_title": str(data.get("job_title") or "").strip()[:255],
        "company": str(data.get("company") or "").strip()[:255],
        "required_skills": required,
        "preferred_skills": preferred,
        "minimum_experience": truncate(phrase, 64),
        "minimum_years": min_years,
        "education_requirements": _as_list(data.get("education_requirements")),
        "responsibilities": responsibilities,
        "location": str(data.get("location") or "").strip()[:255],
        "evidence": {str(k): truncate(str(v), 600) for k, v in evidence.items()},
    }


def required_education_level(education_requirements: list) -> int:
    """Highest education level (0-5) implied by the JD's education requirements."""

    return education_level(" ".join(str(item) for item in education_requirements or []))