# AI Resume & Job Matching System

Upload a batch of resumes plus a job description, get a ranked shortlist where every
score is **deterministic and explainable**, and every candidate has a written
justification for their rank.

The AI model is deliberately kept out of the scoring path. It can help extract
structure and write prose, but it can never influence a score — so the same input
always produces the same ranking.

---

## Contents

- [What it does](#what-it-does)
- [Tech stack](#tech-stack)
- [Quick start](#quick-start)
- [How scoring works](#how-scoring-works)
- [API reference](#api-reference)
- [Project structure](#project-structure)
- [Design decisions](#design-decisions)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)

---

## What it does

1. **Parse** — PDF / TXT / MD resumes are read with PyMuPDF and reduced to clean text.
2. **Extract** — names, contact details, skills, education, experience and projects
   are pulled out by a deterministic heuristic, optionally assisted by an LLM.
3. **Analyse the role** — the job description is normalised into required skills,
   preferred skills, minimum experience, education requirements and responsibilities.
4. **Score** — five weighted components produce a 0-100 score with a full breakdown.
5. **Rank and explain** — candidates are ordered, and each gets a written
   explanation plus an explicit list of missing skills.

---

## Tech stack

| Layer      | Technology                                                          |
| ---------- | ------------------------------------------------------------------- |
| Frontend   | React 18, Vite 6, Tailwind CSS 3, Axios, React Router 6              |
| Backend    | Python 3.10+, FastAPI, Uvicorn, Pydantic v2, pydantic-settings        |
| Database   | SQLite (MVP), SQLAlchemy 2                                          |
| Scoring    | Deterministic Python — no model in the scoring path                 |
| Embeddings | sentence-transformers `all-MiniLM-L6-v2` (local, 384-dim)           |
| AI (opt.)  | NVIDIA NIM, OpenAI-compatible chat completions                      |
| Files      | PyMuPDF                                                            |

---

## Quick start

### 1. Backend

```bash
cd backend
python -m venv .venv
.\.venv\Scripts\activate        # Windows
# source .venv/bin/activate     # macOS / Linux

pip install -r requirements.txt
copy .env.example .env          # Windows  (cp .env.example .env elsewhere)

uvicorn app.main:app --reload --port 8000
```

`requirements.txt` pulls in PyTorch via `sentence-transformers`, so the first
install is large. It is a hard dependency because the semantic component of every
match score needs an embedding.

Interactive API docs: <http://127.0.0.1:8000/docs>

The database tables are created on first request, and the embedding model is
downloaded once on first use, so the very first `/api/health` call can take a while.

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open <http://127.0.0.1:5173>. The Vite dev server proxies `/api` to
`http://127.0.0.1:8000`, so the browser never makes a cross-origin request.

### 3. Try it

Open the dashboard, drop in the bundled sample resumes, and press **Load sample JD**:

```text
backend/samples/rahul_sharma_strong.pdf    strong full-stack match
backend/samples/priya_patil_mid.pdf        good, but missing Redux
backend/samples/amit_joshi_poor.pdf        frontend-only, large skill gap
backend/samples/neha_sharma_minimal.pdf    sparse resume, low score
```

Expected ranking against `backend/scripts/jd_sample.txt`:

| Rank | Candidate     | Score  | Note                                  |
| ---- | ------------- | ------ | ------------------------------------- |
| 1    | Rahul Sharma  | 96.8%  | matches all 8 required skills         |
| 2    | Priya Patil   | 87.8%  | missing Redux                         |
| 3    | Amit Joshi    | 65.3%  | frontend only                         |
| 4    | Neha Sharma   | 21.9%  | sparse resume, no required skills     |

### NVIDIA NIM (optional)

The app is fully functional with no NVIDIA API key — extraction and explanations fall
back to deterministic heuristics. To enable LLM-assisted extraction and richer
explanations, get a key from <https://build.nvidia.com> and set it in
`backend/.env`:

```dotenv
NVIDIA_API_KEY=nvapi-...
```

`GET /api/health` reports `degraded` while the key is missing, and `ok` once set.
Note that scores are unaffected either way — only explanation quality changes.

---

## How scoring works

The overall score is a weighted sum of five components. Weights live in
`backend/app/core/config.py` (override via `.env`) and must total 100.

| Component      | Default | What it measures                                              |
| -------------- | ------- | ------------------------------------------------------------- |
| Skills         | 40%     | Share of required skills evidenced in the resume              |
| Experience     | 25%     | Years of experience against the role's stated minimum         |
| Education      | 15%     | Highest qualification against the role's education requirement |
| Semantic       | 10%     | Embedding cosine similarity of resume text vs job description |
| Evidence       | 10%     | How well the claimed skills are substantiated by resume text  |

Every candidate response carries the full breakdown:

```json
{
  "overall_score": 96.81,
  "skill_score": 100.0,
  "experience_score": 100.0,
  "education_score": 100.0,
  "semantic_score": 80.57,
  "evidence_score": 87.5,
  "matching_skills": ["javascript", "typescript", "react", "..."],
  "missing_skills": [],
  "partial_skills": [],
  "weights": { "skill": 40.0, "experience": 25.0, "education": 15.0, "semantic": 10.0, "evidence": 10.0 }
}
```

The UI renders this as bars and skill chips, so a recruiter can see exactly why
someone scored what they scored.

### Skill matching is word-boundary exact

Skill detection matches whole tokens with an alias table, never raw substrings.
This matters more than it sounds:

| Input                | Correct      | Naive substring match |
| -------------------- | ------------ | --------------------- |
| `JavaScript`         | `javascript` | also wrongly `java`  |
| `Our engineers ...`  | —            | also wrongly `gin`   |
| `REST API design`    | `rest api`   | —                     |

The same discipline applies to the SQL skill filter: `?skills=java` returns no
results rather than every JavaScript developer. See `find_skills()` in
`backend/app/utils/text_utils.py`.

---

## API reference

All routes are prefixed with `/api`. Interactive docs at `/docs`.

### Health

| Method | Path             | Description                                       |
| ------ | ---------------- | ------------------------------------------------- |
| GET    | `/api/health`    | Liveness plus component status (db, NVIDIA, AI)   |
| GET    | `/api/health/status` | Integration/feature readiness                  |

### Resumes

| Method | Path                 | Description                                        |
| ------ | -------------------- | -------------------------------------------------- |
| POST   | `/api/resumes/upload` | Upload many resumes at once (`multipart/form-data`) |
| GET    | `/api/resumes`        | List resumes with their extracted candidates       |
| DELETE | `/api/resumes`        | Clear all resumes, candidates and match results    |

A single bad file never fails the batch — per-file errors come back in `errors`
while the good files still process.

### Jobs

| Method | Path              | Description                                    |
| ------ | ----------------- | ---------------------------------------------- |
| POST   | `/api/jobs/analyze` | Extract structured requirements from a JD     |
| GET    | `/api/jobs`         | Most recently analysed job                     |
| GET    | `/api/jobs/{uid}`   | Fetch one analysed job                         |

### Matching

| Method | Path                                | Description                                    |
| ------ | ----------------------------------- | ---------------------------------------------- |
| POST   | `/api/matching/analyze`              | Score stored resumes against the latest job    |
| POST   | `/api/matching/analyze-and-upload`   | Upload resumes + JD + score in one request     |

`use_ai=false` forces deterministic extraction. That is the default in the UI.

### Candidates

| Method | Path                      | Description                                    |
| ------ | ------------------------- | ---------------------------------------------- |
| GET    | `/api/candidates`         | Search, filter, sort and paginate              |
| GET    | `/api/candidates/{uid}`   | Full profile, evidence, breakdown, resume text |

Query parameters: `q`, `skills` (comma-separated, ALL must match), `min_score`,
`max_score`, `min_experience`, `education_level`, `sort` (`score`/`name`/`experience`),
`order`, `job_uid`, `limit`, `offset`.

Search and filtering run in SQL against the processed data — never in the browser.

---

## Project structure

```text
ai-resume-matcher/
|-- backend/
|   |-- app/
|   |   |-- api/
|   |   |   |-- routes/            # health, resumes, jobs, matching, candidates
|   |   |   |-- middleware.py      # request logging
|   |   |   `-- router.py          # aggregated v1 router
|   |   |-- core/
|   |   |   |-- config.py          # pydantic-settings, weights, limits
|   |   |   `-- errors.py          # typed errors -> clean HTTP responses
|   |   |-- db/session.py         # engine, SessionLocal, get_db
|   |   |-- models/               # Resume, Candidate, JobDescription, MatchResult
|   |   |-- schemas/mvp.py        # request/response models
|   |   |-- services/
|   |   |   |-- pdf_parser.py     # PyMuPDF extraction + validation
|   |   |   |-- text_utils.py     # skill aliases, find_skills, education levels
|   |   |   |-- ai_extraction.py  # resume parsing (heuristic + AI)
|   |   |   |-- jd_service.py     # job description parsing
|   |   |   |-- embedding_service.py
|   |   |   |-- matching_service.py   # the deterministic scorer
|   |   |   |-- ranking_service.py    # ordering + summary stats
|   |   |   |-- explanation_service.py
|   |   |   `-- nvidia_client.py
|   |   `-- main.py
|   |-- samples/                 # 4 sample resume PDFs
|   |-- scripts/jd_sample.txt    # sample job description
|   `-- tests/                   # 43 tests
|-- frontend/
|   |-- src/
|   |   |-- components/          # uploader, filters, score ring, cards
|   |   |-- hooks/               # useApiHealth, useCandidateSearch, useMatchingPipeline
|   |   |-- pages/               # Dashboard, Resumes, Jobs, Matches, CandidateDetail
|   |   |-- services/            # axios client + typed API functions
|   |   `-- utils/                # cn, scoring vocabulary
`-- README.md
```

---

## Design decisions

**Scoring never touches the LLM.** Explanations are generated *after* the score is
fixed and are explicitly prevented from changing it. A model that is slow, rate
limited or unavailable degrades the writing, never the ranking. This also makes
runs reproducible — there is a test for it.

**Heuristic extraction is the default, not a fallback of last resort.** A regex and
alias-table parser is predictable, instant and auditable. The LLM path is opt-in via
`use_ai`, because silently changing behaviour based on whether an API key happens to
be configured makes results impossible to reason about.

**Skill matching uses word boundaries plus an alias table.** Substring matching is
the single easiest way to produce confidently wrong output (`java` inside
`javascript`). Aliases let `JS`/`JavaScript` and `Postgres`/`PostgreSQL` collapse to
one canonical skill without reintroducing the false positives.

**Filtering happens in SQL.** `Candidate.skills_flat` is a denormalised token list so
search stays a single indexed query. Filters are exact-token matched against it.

**Resumes are stored with their extracted text.** Every score can be traced back to
the exact text it was derived from, which is what makes the evidence score and the
explainability claim meaningful rather than decorative.

**Failed uploads are isolated.** One unreadable PDF in a batch of 25 returns an error
for that file and processes the rest.

---

## Testing

```bash
cd backend
.\.venv\Scripts\python.exe -m pytest tests\ -q -o addopts=""
```

43 tests covering the health surface, upload and validation, JD analysis, the
scoring breakdown, ranking order, reproducibility, search/filtering, explainability
and error contracts. Includes regression tests for the substring-skill bug and for
location/education mis-parsing.

Frontend:

```bash
cd frontend
npm run lint
npm run build
```

---

## Troubleshooting

**`GET /api/health` returns `degraded`** — expected without `NVIDIA_API_KEY`. The
app runs fully offline; set the key to enable LLM assistance.

**First request is slow** — the embedding model downloads on first use. After that
it is cached.

**Frontend shows "API offline"** — the backend is not running on port 8000, or
`VITE_BACKEND_URL` in `frontend/.env` points elsewhere. Check
<http://127.0.0.1:8000/api/health>.

**`422 pdf_extraction_failed`** — the file is likely a scanned image with no text
layer. OCR is not implemented.

**Scores look too low across the board** — the JD parser reads requirements
literally. Make sure the description states required skills and the minimum
experience explicitly, then re-check the extracted requirements on the Jobs page
before trusting the ranking.

**Need a clean slate** — `DELETE /api/resumes` clears resumes, candidates and match
results, or delete `backend/app.db`.
