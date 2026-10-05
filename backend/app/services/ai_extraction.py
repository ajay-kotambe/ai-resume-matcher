"""AI extraction service: resume text -> structured candidate information.

Primary path: NVIDIA NIM (DeepSeek) with strict JSON output.
Fallback path: deterministic regex heuristics, so the demo still works when no
API key is configured or the provider fails. The method used is always recorded.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from app.core.config import get_settings
from app.core.errors import AIProviderError, AIResponseError, AITimeoutError
from app.services.nvidia_client import AIResult, get_nvidia_client
from app.utils.text_utils import (
    clean_text,
    find_skills,
    pretty_name,
    education_level,
    extract_emails,
    extract_phones,
    extract_years_of_experience,
    normalize_skills,
    truncate,
)

logger = logging.getLogger(__name__)

RESUME_SYSTEM_PROMPT = """You are an expert technical recruiter's assistant.
Extract structured information from the resume text provided by the user.

ABSOLUTE RULES:
1. NEVER invent, guess, or infer information that is not written in the resume.
2. If a field is not present in the resume, return an empty string "" or an empty list [].
3. Preserve evidence: keep the candidate's own wording, do not paraphrase away detail.
4. In the "evidence" object, quote the exact resume line(s) that support each field.
   If a field has no support, use an empty string.
5. Keep "stated" and "inferred" separate. "stated_skills" are skills the candidate
   explicitly claims. "inferred_skills" are only skills strongly implied by the text
   (for example a project description). If you are unsure, put it in stated_skills
   only if it literally appears, otherwise leave inferred empty.
6. Normalize obvious skill variants to a single canonical spelling, for example:
   "JS"/"JavaScript" -> "JavaScript", "ReactJS"/"React.js" -> "React",
   "Postgres"/"PostgreSQL" -> "PostgreSQL", "Node"/"NodeJS" -> "Node.js",
   "K8s" -> "Kubernetes", "ML" -> "Machine Learning", "REST"/"RESTful APIs" -> "REST API".
   Do NOT merge genuinely different skills.
7. For years_of_experience, use only numbers explicitly written in the resume.
   If none are written, return 0.

Return ONLY a JSON object with exactly these keys:
{
  "name": "",
  "email": "",
  "phone": "",
  "location": "",
  "summary": "",
  "skills": [],
  "stated_skills": [],
  "inferred_skills": [],
  "education": [{"degree": "", "institution": "", "year": "", "detail": ""}],
  "experience": [{"title": "", "company": "", "duration": "", "years": 0, "description": "", "responsibilities": []}],
  "projects": [{"name": "", "technologies": [], "description": ""}],
  "certifications": [{"name": "", "issuer": "", "year": ""}],
  "years_of_experience": 0,
  "evidence": {"name": "", "email": "", "phone": "", "skills": "", "experience": "", "education": ""}
}"""

SKILL_SECTION_RE = re.compile(
    r"(?im)^\s*(?:technical\s+skills|core\s+skills|key\s+skills|skills\s*(?:&|and)\s*tools|"
    r"technologies|tech\s*stack|technical proficiencies|areas of expertise)\s*[:\-]?\s*$"
)
SECTION_RE = re.compile(
    r"(?im)^\s*([A-Z][A-Za-z /&\-]{2,40})\s*[:\-]?\s*$"
)


@dataclass
class ExtractionResult:
    """Structured candidate information + provenance."""

    data: dict
    method: str = "ai"  # ai | heuristic
    latency_ms: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    warning: str | None = None
    raw_text: str = ""
    evidence: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def extract_candidate(resume_text: str, *, use_ai: bool = True) -> ExtractionResult:
    """Extract structured candidate information from resume text.

    Tries DeepSeek first; falls back to heuristics when allowed. AI failures
    are surfaced as warnings rather than crashing the whole batch, so one bad
    resume cannot abort a recruiter's upload of 20 files.
    """

    settings = get_settings()
    text = clean_text(resume_text)

    if use_ai and settings.nvidia_configured:
        try:
            data, ai_result = _extract_with_ai(text)
            normalised = _normalise_candidate(data, text)
            return ExtractionResult(
                data=normalised,
                method="ai",
                latency_ms=ai_result.latency_ms,
                prompt_tokens=ai_result.prompt_tokens,
                completion_tokens=ai_result.completion_tokens,
                raw_text=text,
                evidence=normalised.get("evidence", {}),
            )
        except (AITimeoutError, AIProviderError, AIResponseError) as exc:
            logger.warning("AI extraction failed, using heuristic fallback: %s", exc.message)
            if not settings.ALLOW_HEURISTIC_FALLBACK:
                raise
            fallback = extract_candidate(text, use_ai=False)
            fallback.warning = exc.message
            return fallback

    data = _extract_with_heuristics(text)
    return ExtractionResult(
        data=data,
        method="heuristic",
        raw_text=text,
        evidence=data.get("evidence", {}),
    )


# ---------------------------------------------------------------------------
# AI path
# ---------------------------------------------------------------------------
def _extract_with_ai(text: str) -> tuple[dict, AIResult]:
    """Call DeepSeek and validate the structured response."""

    client = get_nvidia_client()
    client.ensure_ready()

    # Long resumes are truncated with a marker so the prompt stays bounded.
    prompt = (
        "Extract the structured candidate information from the resume below.\n"
        "<resume>\n"
        f"{truncate(text, 12000)}\n"
        "</resume>"
    )

    data, result = client.chat_json(
        RESUME_SYSTEM_PROMPT,
        prompt,
        temperature=0.0,
        max_tokens=1000,
    )
    return _validate_ai_payload(data), result


def _validate_ai_payload(data: dict) -> dict:
    """Reject malformed AI output rather than crashing later."""

    if not isinstance(data, dict):
        raise AIResponseError("AI response was not a JSON object.")

    if not any(
        data.get(key) for key in ("name", "email", "skills", "experience", "education")
    ):
        raise AIResponseError(
            "AI response did not contain any recognisable candidate fields.",
            details={"keys": sorted(data.keys())},
        )
    return data


# ---------------------------------------------------------------------------
# Heuristic path (deterministic, offline)
# ---------------------------------------------------------------------------
def _extract_with_heuristics(text: str) -> dict:
    """Regex-based extraction. Used when the AI provider is unavailable."""

    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]

    name = pretty_name(_guess_name(lines))
    emails = extract_emails(text)
    phones = extract_phones(text)

    skills = _guess_skills(text)
    education = _guess_education(lines)
    experience = _guess_experience(lines)
    certifications = _guess_certifications(lines)
    projects = _guess_projects(lines)

    years = extract_years_of_experience(text)
    if not years:
        years = _years_from_date_ranges(text)

    location = _guess_location(lines)

    return {
        "name": name,
        "email": emails[0] if emails else "",
        "phone": phones[0] if phones else "",
        "location": location,
        "summary": truncate(" ".join(lines[:3]), 400),
        "skills": skills,
        "stated_skills": skills,
        "inferred_skills": [],
        "education": education,
        "experience": experience,
        "projects": projects,
        "certifications": certifications,
        "years_of_experience": years,
        "evidence": {
            "name": name,
            "email": emails[0] if emails else "",
            "phone": phones[0] if phones else "",
            "skills": ", ".join(skills[:12]),
            "experience": "; ".join(f"{e.get('title', '')}" for e in experience[:3]),
            "education": "; ".join(e.get("degree", "") for e in education[:3]),
        },
    }


def _guess_name(lines: list[str]) -> str:
    """Pick the most likely candidate name from the first lines."""

    for line in lines[:6]:
        if "@" in line or "linkedin" in line.lower() or line.isdigit():
            continue
        if re.search(r"resume|curriculum|vitae|cv\b", line, re.IGNORECASE):
            continue
        candidate = line.strip(" |-â€“â€”â€¢\t")
        # 2-4 capitalised words, no digits.
        if re.fullmatch(r"[A-Z][A-Za-z'.\-]*(?: [A-Z][A-Za-z'.\-]*){1,3}", candidate):
            return candidate
        if re.fullmatch(r"[A-Za-z][A-Za-z'\-]+ [A-Za-z][A-Za-z'\-]+", candidate):
            words = candidate.split()
            if all(w[:1].isupper() or w.lower() in {"van", "de", "bin"} for w in words):
                return candidate
    return ""


def _guess_skills(text: str) -> list[str]:
    """Detect skills using word-boundary matching (no substring false positives)."""

    return normalize_skills(find_skills(text))


def _section_body(text: str, keywords: list[str]) -> str:
    """Return the lines belonging to the first section whose title matches."""

    lines = text.split("\n")
    for index, line in enumerate(lines):
        title = line.strip().lower().rstrip(":").strip()
        if not title or len(title) > 45:
            continue
        if any(keyword in title for keyword in keywords):
            body: list[str] = []
            for following in lines[index + 1 :]:
                candidate = following.strip()
                if not candidate:
                    if body:
                        break
                    continue
                # A new section header ends the block.
                if SECTION_RE.match(candidate) and len(candidate) < 45:
                    break
                body.append(candidate)
                if len(body) > 25:
                    break
            if body:
                return "\n".join(body)
    return ""


def _split_entries(block: str) -> list[str]:
    """Split a section body into individual entries."""

    entries: list[str] = []
    for line in block.split("\n"):
        clean = line.strip(" \t-*â€¢")
        if not clean:
            continue
        # Entries often start with a capital or a bullet-like token.
        if line.strip().startswith(("-", "*", "â€¢")) or line != line.lstrip():
            entries.append(clean)
        elif not entries:
            entries.append(clean)
        else:
            entries[-1] = f"{entries[-1]} {clean}"
    return entries


DEGREE_RE = re.compile(
    r"\b("
    r"b\.?tech|b\.?tech|b\.?sc|b\.?s\.?c|b\.?com|b\.?ba|b\.?a\b|b\.?e\b|b\.?s\b|b\.?m\b|"
    r"bachelor|b\.?ca|b\.?pharm|b\.?arch|"
    r"m\.?tech|m\.?sc|m\.?s\b|msc|mba|m\.?pharm|master|"
    r"ph\.?d|doctorate|diploma|polytechnic|associate|"
    r"high school|secondary|intermediate|class\s*(?:x|xi|xii)"
    r")\b",
    re.IGNORECASE,
)


def _guess_education(lines: list[str]) -> list[dict]:
    block = _section_body("\n".join(lines), ["education", "academic", "qualification"])
    source = block or "\n".join(lines)
    results: list[dict] = []
    for line in source.split("\n"):
        if DEGREE_RE.search(line):
            year_match = re.search(r"(19|20)\d{2}", line)
            results.append(
                {
                    "degree": truncate(line.strip()[:120], 120),
                    "institution": "",
                    "year": year_match.group(0) if year_match else "",
                    "detail": line.strip(),
                }
            )
        if len(results) >= 5:
            break
    return results


def _years_from_date_ranges(text: str) -> float:
    """Approximate experience from explicit month-year ranges (e.g. 2021 - 2023)."""

    import datetime as _dt

    months = {
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
        "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    }
    now = _dt.datetime.now(_dt.timezone.utc)
    total = 0.0
    for match in re.finditer(
        r"(?i)(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s*'?\s*(20\d{2})\s*"
        r"(?:-|â€“|â€”|to)\s*(present|current|now|(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s*'?\s*(20\d{2}))",
        text,
    ):
        start_month = months[match.group(1)[:3].lower()]
        start_year = int(match.group(2))
        end_token = match.group(3).strip().lower()
        if end_token in {"present", "current", "now"}:
            end_month, end_year = now.month, now.year
        else:
            em = re.match(r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)", end_token)
            ey = re.search(r"(20\d{2})", end_token)
            end_month = months[em.group(1)[:3].lower()] if em else start_month
            end_year = int(ey.group(1)) if ey else start_year
        delta = (end_year - start_year) * 12 + (end_month - start_month)
        if 0 < delta <= 480:
            total += delta / 12

    return round(total, 2)


def _guess_experience(lines: list[str]) -> list[dict]:
    block = _section_body(
        "\n".join(lines), ["experience", "employment", "work history", "internship"]
    )
    results: list[dict] = []
    for entry in _split_entries(block)[:12]:
        results.append(
            {
                "title": truncate(entry, 160),
                "company": "",
                "duration": "",
                "years": 0,
                "description": truncate(entry, 500),
                "responsibilities": [],
            }
        )
    return results


def _guess_certifications(lines: list[str]) -> list[dict]:
    block = _section_body(
        "\n".join(lines), ["certification", "licence", "license", "course"]
    )
    return [{"name": truncate(e, 160), "issuer": "", "year": ""} for e in _split_entries(block)[:10]]


def _guess_projects(lines: list[str]) -> list[dict]:
    block = _section_body("\n".join(lines), ["project"])
    results: list[dict] = []
    for entry in _split_entries(block)[:8]:
        results.append(
            {
                "name": truncate(entry, 120),
                "technologies": [],
                "description": truncate(entry, 400),
            }
        )
    return results


LOCATION_LABEL_RE = re.compile(
    r"(?i)\blocation\s*[:\-\u2013]\s*([A-Za-z][A-Za-z .,'-]{2,40})"
)
CITY_REGION_RE = re.compile(
    r"\b([A-Z][a-z]+(?:[ -][A-Z][a-z]+)*,\s*[A-Z][A-Za-z]*(?:[ -][A-Z][A-Za-z]*)*)\b"
)
PHONE_HINT_RE = re.compile(r"\+?\d[\d\s().-]{6,}\d")


def _guess_location(lines: list[str]) -> str:
    """Find a city/region pair, preferring an explicit ``Location:`` label.

    Scanning every header line would misread a skill list such as
    ``Languages: JavaScript, TypeScript`` as a location, so the fallback only
    considers contact lines (email/phone), which is where resumes put it.
    """

    for line in lines[:10]:
        match = LOCATION_LABEL_RE.search(line)
        if match:
            return match.group(1).strip().rstrip(",")

    for line in lines[:10]:
        if "@" not in line and not PHONE_HINT_RE.search(line):
            continue
        # Split on the usual separators so an email can never be part of a match.
        for chunk in re.split(r"[|;•]|\s{2,}", line):
            match = CITY_REGION_RE.search(chunk)
            if not match:
                continue
            value = match.group(1).strip().rstrip(",")
            if 3 < len(value) <= 60:
                return value
    return ""


# ---------------------------------------------------------------------------
# Normalisation shared by both paths
# ---------------------------------------------------------------------------
def _as_list(value: object) -> list[str]:
    """Coerce a model field into a clean list of non-empty strings."""

    if value is None:
        return []
    if isinstance(value, str):
        parts = [p.strip() for p in re.split(r"[,;\n]| and ", value) if p.strip()]
        return parts
    if isinstance(value, (list, tuple)):
        out: list[str] = []
        for item in value:
            if isinstance(item, str) and item.strip():
                out.append(item.strip())
            elif isinstance(item, (int, float)):
                out.append(str(item))
        return out
    return []


def _as_float(value: object) -> float:
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        match = re.search(r"(\d+(?:\.\d+)?)", str(value or ""))
        return float(match.group(1)) if match else 0.0


def _normalise_candidate(data: dict, raw_text: str) -> dict:
    """Coerce an arbitrary model payload into the canonical candidate shape."""

    raw_skills = _as_list(data.get("skills"))
    stated = normalize_skills(_as_list(data.get("stated_skills")) or raw_skills)
    inferred = normalize_skills(_as_list(data.get("inferred_skills")))

    skills = normalize_skills(stated + inferred)

    emails = extract_emails(raw_text)
    email = str(data.get("email") or "").strip()
    if "@" not in email:
        email = emails[0] if emails else ""
    elif email.lower() not in emails:
        # Trust the resume text over a hallucinated address.
        email = emails[0] if emails else ""

    phones = extract_phones(raw_text)
    phone = str(data.get("phone") or "").strip()
    if not re.search(r"\d{6,}", phone):
        phone = phones[0] if phones else ""

    years = _as_float(data.get("years_of_experience")) or extract_years_of_experience(raw_text)
    if not years:
        years = _years_from_date_ranges(raw_text)

    education = _normalise_list_of_dicts(data.get("education"))
    certifications = _normalise_list_of_dicts(data.get("certifications"))
    projects = _normalise_list_of_dicts(data.get("projects"))
    experience = _normalise_experience(data.get("experience"))

    evidence = data.get("evidence") if isinstance(data.get("evidence"), dict) else {}

    return {
        "name": pretty_name(str(data.get("name") or "")),
        "email": email,
        "phone": phone,
        "location": str(data.get("location") or "").strip()[:255],
        "summary": truncate(str(data.get("summary") or "").strip(), 1200),
        "skills": skills,
        "stated_skills": stated,
        "inferred_skills": inferred,
        "education": education,
        "experience": experience,
        "projects": projects,
        "certifications": certifications,
        "years_of_experience": years,
        "evidence": {str(k): str(v)[:600] for k, v in evidence.items()},
    }


def _normalise_experience(value: object) -> list[dict]:
    """Normalise the experience array, coercing years to float."""

    items = _normalise_list_of_dicts(value)
    for item in items:
        item["years"] = _as_float(item.get("years"))
    return items


def _normalise_list_of_dicts(value: object) -> list[dict]:
    """Accept a list of dicts, a list of strings, or a single string."""

    results: list[dict] = []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple)):
        return results

    for item in value:
        if isinstance(item, dict):
            results.append({str(k): item[k] for k in item if item[k] not in (None, "")})
        elif isinstance(item, str) and item.strip():
            results.append({"detail": item.strip()})
    return results


def education_level_of(education: list) -> int:
    """Highest education level (0-5) across the candidate's education entries."""

    haystack = " ".join(
        " ".join(str(v) for v in entry.values()) for entry in education or []
    )
    return education_level(haystack)
