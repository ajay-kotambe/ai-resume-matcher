"""Shared text utilities: cleaning, normalisation and deterministic helpers.

Everything here is pure and unit-testable. No AI calls.
"""

from __future__ import annotations

import re
import unicodedata

# --- Regexes ---------------------------------------------------------------
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+", re.IGNORECASE)
# A run of digits with optional +, spaces, dots, dashes and one pair of brackets.
PHONE_RE = re.compile(r"(?<![\w.])(?:\+|0)?[\s.-]?\(?\+?\d[\d\s().\-]{7,20}\d(?![\w.])")
URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
DATE_RANGE_RE = re.compile(
    r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s*'?\d{2,4}"
    r"\s*(?:-|–|—|to|until)\s*"
    r"(present|current|now|(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s*'?\d{2,4})",
    re.IGNORECASE,
)
YEARS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)", re.IGNORECASE)

# Skill alias map: obvious variations -> canonical name.
SKILL_ALIASES: dict[str, str] = {
    "js": "javascript",
    "javascript": "javascript",
    "ts": "typescript",
    "typescript": "typescript",
    "py": "python",
    "python": "python",
    "python3": "python",
    "reactjs": "react",
    "react.js": "react",
    "react": "react",
    "nodejs": "node.js",
    "node.js": "node.js",
    "node": "node.js",
    "postgres": "postgresql",
    "postgresql": "postgresql",
    "psql": "postgresql",
    "mongo": "mongodb",
    "mongodb": "mongodb",
    "k8s": "kubernetes",
    "kubernetes": "kubernetes",
    "docker": "docker",
    "rest": "rest api",
    "rest apis": "rest api",
    "restful": "rest api",
    "rest api": "rest api",
    "restful api": "rest api",
    "restful apis": "rest api",
    "api": "api",
    "apis": "api",
    "graphql": "graphql",
    "ml": "machine learning",
    "machine learning": "machine learning",
    "ai": "artificial intelligence",
    "artificial intelligence": "artificial intelligence",
    "dl": "deep learning",
    "deep learning": "deep learning",
    "nlp": "nlp",
    "sql": "sql",
    "nosql": "nosql",
    "aws": "aws",
    "amazon web services": "aws",
    "gcp": "gcp",
    "azure": "azure",
    "ci/cd": "ci/cd",
    "cicd": "ci/cd",
    "git": "git",
    "github": "git",
    "linux": "linux",
    "windows": "windows",
    "tensorflow": "tensorflow",
    "pytorch": "pytorch",
    "torch": "pytorch",
    "pandas": "pandas",
    "numpy": "numpy",
    "scikit learn": "scikit-learn",
    "sklearn": "scikit-learn",
    "power bi": "power bi",
    "tableau": "tableau",
    "excel": "excel",
    "figma": "figma",
    "c++": "c++",
    "java": "java",
    "python/java": "python",
}

# Education level ordering, highest first.
EDUCATION_LEVELS: list[tuple[str, int]] = [
    ("phd", 5),
    ("doctorate", 5),
    ("ph.d", 5),
    ("master", 4),
    ("m.tech", 4),
    ("mtech", 4),
    ("m.s", 4),
    ("msc", 4),
    ("m.sc", 4),
    ("mba", 4),
    ("b.tech", 3),
    ("btech", 3),
    ("bachelor", 3),
    ("b.sc", 3),
    ("bsc", 3),
    ("b.e", 3),
    ("b.s", 3),
    ("b.com", 3),
    ("b.ca", 3),
    ("b.a", 3),
    ("b.pharm", 3),
    ("b.arch", 3),
    ("diploma", 2),
    ("diploma in", 2),
    ("associate", 2),
    ("high school", 1),
    ("secondary", 1),
    ("10th", 1),
    ("12th", 1),
    ("intermediate", 1),
]


def clean_text(raw: str) -> str:
    """Normalise raw PDF text.

    Handles ligatures, soft hyphens, multiple spaces, bullet glyphs and
    repeated blank lines while preserving line structure (important because
    resume sections are line-delimited).
    """

    if not raw:
        return ""

    text = unicodedata.normalize("NFKC", raw)
    # Common ligatures / typography that PDF extraction leaves behind.
    replacements = {
        "\ufb00": "ff",
        "\ufb01": "fi",
        "\ufb02": "fl",
        "\ufb03": "ffi",
        "\ufb04": "ffl",
        "\u00ad": "",
        "\xa0": " ",
        "\u2022": "-",
        "\u2023": "-",
        "\u25aa": "-",
        "\u25cf": "-",
        "\u2028": "\n",
        "\u2029": "\n",
        "\ufeff": "",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)

    # De-hyphenate words split across lines.
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)

    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Collapse horizontal whitespace but keep newlines.
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    # Collapse 3+ blank lines into a single blank line.
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def extract_emails(text: str) -> list[str]:
    """Return unique emails found in ``text``, preserving order."""

    seen: dict[str, None] = {}
    for match in EMAIL_RE.findall(text or ""):
        email = match.strip().strip(".,;:")
        seen.setdefault(email.lower(), None)
    return list(seen.keys())


def extract_phones(text: str) -> list[str]:
    """Return plausible phone numbers found in ``text``.

    A run is accepted when it holds 10-15 digits (enough for national formats
    including a country code) and is not a bare year or a long id.
    """

    results: list[str] = []
    for match in PHONE_RE.finditer(text or ""):
        raw = match.group(0).strip()
        digits = re.sub(r"\D", "", raw)
        if not (10 <= len(digits) <= 15):
            continue
        # Reject degenerate runs such as 0000000000 or 1111111111.
        if len(set(digits)) <= 2:
            continue
        # A plain 4-digit-year-like run never reaches 10 digits, but an
        # 11-digit id would: reject runs with no separator and a year prefix.
        if len(digits) == 11 and digits.startswith("19"):
            continue
        cleaned = raw.strip(" .,;:-")
        # Normalise internal spacing: "+91 98765 43210" -> "+91 98765 43210".
        cleaned = re.sub(r"\s+", " ", cleaned)
        if cleaned and cleaned not in results:
            results.append(cleaned)
    return results


def normalize_skill(skill: str) -> str:
    """Canonicalise a single skill string (lowercase, alias-mapped)."""

    if not skill:
        return ""
    cleaned = re.sub(r"\s+", " ", str(skill)).strip().strip(".,;:|-–—")
    key = cleaned.lower()
    if key in SKILL_ALIASES:
        return SKILL_ALIASES[key]
    # Trailing parenthetical, e.g. "React (Redux)" -> keep whole string
    return key


def normalize_skills(skills: list[str]) -> list[str]:
    """Canonicalise + dedupe a skill list, preserving first-seen order."""

    seen: dict[str, None] = {}
    for skill in skills or []:
        norm = normalize_skill(skill)
        if norm:
            seen.setdefault(norm, None)
    return list(seen.keys())


def skills_match(candidate_skill: str, required_skill: str) -> bool:
    """Loose equality so 'react' matches 'react.js' and 'aws' matches 'aws lambda'."""

    a = normalize_skill(candidate_skill)
    b = normalize_skill(required_skill)
    if not a or not b:
        return False
    if a == b:
        return True
    a_tokens = set(re.split(r"[\s/+#.-]+", a))
    b_tokens = set(re.split(r"[\s/+#.-]+", b))
    if a_tokens & b_tokens:
        return True
    return a in b or b in a


def extract_years_of_experience(text: str) -> float:
    """Best-effort total years of experience from explicit 'X years' mentions."""

    if not text:
        return 0.0
    values = [float(m) for m in YEARS_RE.findall(text)]
    if not values:
        return 0.0
    # Prefer the largest single claim; overlapping bullets inflate the sum.
    return round(max(values), 2)


def education_level(text: str) -> int:
    """Return 0-5 for the highest education level mentioned in ``text``."""

    if not text:
        return 0
    haystack = f" {text.lower()} "
    best = 0
    for keyword, level in EDUCATION_LEVELS:
        if keyword in haystack and level > best:
            best = level
    return best


#: Particles that stay lowercase when title-casing a name.
NAME_PARTICLES = {"van", "von", "de", "del", "della", "der", "da", "di", "du", "la", "le", "bin", "ibn", "al"}


def pretty_name(value: str) -> str:
    """Normalise a person name.

    ``RAHUL SHARMA`` -> ``Rahul Sharma``; ``rahul sharma`` -> ``Rahul Sharma``.
    Mixed-case names are left alone so the candidate's own casing survives.
    """

    if not value:
        return ""
    cleaned = re.sub(r"\s+", " ", str(value)).strip(" |-–—•\t,")
    if not cleaned:
        return ""
    # Only rewrite when the whole name is uppercase or all lowercase.
    letters = [c for c in cleaned if c.isalpha()]
    if not letters:
        return cleaned
    if not (all(c.isupper() for c in letters) or all(c.islower() for c in letters)):
        return cleaned

    words = []
    for index, word in enumerate(cleaned.split(" ")):
        lowered = word.lower()
        if lowered in NAME_PARTICLES and index > 0:
            words.append(lowered)
        else:
            words.append(lowered[:1].upper() + lowered[1:])
    return " ".join(words)


def tokenize(text: str) -> list[str]:
    """Lowercase word tokens, punctuation stripped."""

    return re.findall(r"[a-z0-9+#.]+", (text or "").lower())


def truncate(text: str, limit: int) -> str:
    """Trim text to ``limit`` characters, appending an ellipsis."""

    if not text or len(text) <= limit:
        return text or ""
    return text[:limit].rstrip() + "..."


# ---------------------------------------------------------------------------
# Bulk skill detection (word-boundary aware)
# ---------------------------------------------------------------------------
#: Short/ambiguous tokens need explicit boundaries so "java" never matches
#: inside "javascript" and "go" never matches inside "google".
_SKILL_LOOKUP: dict[str, str] = {}
for _alias, _canonical in SKILL_ALIASES.items():
    _SKILL_LOOKUP[_alias] = _canonical

#: Extra surface forms recognised only during detection (not normalisation).
_DETECTION_ONLY: dict[str, str] = {
    "javascript": "javascript", "typescript": "typescript",
    "python": "python", "java": "java", "golang": "go",
    "c++": "c++", "c#": "c#",
    "react": "react", "vue": "vue", "angular": "angular",
    "svelte": "svelte", "next.js": "next.js", "nextjs": "next.js",
    "html": "html", "css": "css", "sass": "sass", "scss": "sass",
    "tailwind css": "tailwind css", "tailwind": "tailwind css",
    "redux": "redux", "jquery": "jquery", "webpack": "webpack",
    "node.js": "node.js", "nodejs": "node.js", "express": "express",
    "django": "django", "flask": "flask", "fastapi": "fastapi",
    "spring boot": "spring boot", "rest api": "rest api",
    "restful api": "rest api", "restful apis": "rest api",
    "graphql": "graphql", "grpc": "grpc", "microservices": "microservices",
    "sql": "sql", "postgresql": "postgresql", "postgres": "postgresql",
    "mysql": "mysql", "sqlite": "sqlite", "mongodb": "mongodb", "mongo": "mongodb",
    "redis": "redis", "elasticsearch": "elasticsearch", "dynamodb": "dynamodb",
    "oracle": "oracle", "snowflake": "snowflake", "bigquery": "bigquery",
    "kafka": "kafka", "rabbitmq": "rabbitmq", "pandas": "pandas",
    "numpy": "numpy", "scikit-learn": "scikit-learn", "scikit learn": "scikit-learn",
    "sklearn": "scikit-learn", "spark": "spark", "hadoop": "hadoop",
    "airflow": "airflow", "etl": "etl",
    "machine learning": "machine learning", "deep learning": "deep learning",
    "natural language processing": "natural language processing",
    "nlp": "nlp", "computer vision": "computer vision",
    "tensorflow": "tensorflow", "pytorch": "pytorch", "torch": "pytorch",
    "keras": "keras", "transformers": "transformers", "llm": "llm",
    "llms": "llms", "langchain": "langchain", "openai": "openai",
    "hugging face": "hugging face", "xgboost": "xgboost",
    "opencv": "opencv", "artificial intelligence": "artificial intelligence",
    "mlops": "mlops", "generative ai": "generative ai", "rag": "rag",
    "aws": "aws", "azure": "azure", "gcp": "gcp", "google cloud": "google cloud",
    "docker": "docker", "kubernetes": "kubernetes", "k8s": "kubernetes",
    "terraform": "terraform", "ansible": "ansible", "jenkins": "jenkins",
    "ci/cd": "ci/cd", "cicd": "ci/cd", "github actions": "github actions",
    "gitlab": "gitlab", "linux": "linux", "unix": "unix", "nginx": "nginx",
    "serverless": "serverless", "lambda": "lambda",
    "cloudformation": "cloudformation", "prometheus": "prometheus",
    "grafana": "grafana",
    "android": "android", "ios": "ios", "flutter": "flutter",
    "react native": "react native",
    "agile": "agile", "scrum": "scrum", "kanban": "kanban", "jira": "jira",
    "pytest": "pytest", "selenium": "selenium", "cypress": "cypress",
    "tdd": "tdd", "unit testing": "unit testing",
    "system design": "system design", "design patterns": "design patterns",
    "microservice architecture": "microservice architecture",
    "git": "git", "github": "git", "postman": "postman",
    "tableau": "tableau", "power bi": "power bi", "excel": "excel",
    "data engineering": "data engineering",
    "data warehouse": "data warehouse",
}
_SKILL_LOOKBACK: dict[str, str] = dict(_SKILL_LOOKUP)
_SKILL_LOOKBACK.update(_DETECTION_ONLY)

# Longest aliases first so "next.js" wins over "js", "rest api" over "api".
_SKILL_ALIASES_BY_LEN = sorted(_SKILL_LOOKBACK.keys(), key=len, reverse=True)
_SKILL_PATTERN = re.compile(
    r"(?<![\w+#])(" + "|".join(re.escape(a) for a in _SKILL_ALIASES_BY_LEN) + r")(?![\w+#])",
    re.IGNORECASE,
)


def find_skills(text: str) -> list[str]:
    """Extract every recognised skill using word-boundary matching.

    Word boundaries prevent false positives such as ``java`` inside
    ``javascript`` or ``gin`` inside ``engineer``.
    """

    if not text:
        return []
    found: dict[str, None] = {}
    for match in _SKILL_PATTERN.finditer(text):
        canonical = _SKILL_LOOKBACK.get(match.group(1).lower())
        if canonical:
            found.setdefault(canonical, None)
    return list(found.keys())