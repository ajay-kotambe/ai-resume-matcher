"""End-to-end MVP tests using TestClient and generated sample resumes.

Covers the full required flow plus the error cases:
  upload -> extract -> job analyse -> match -> rank -> search/filter -> detail
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.db.session import Base, engine
from app.main import app

SAMPLES = Path(__file__).resolve().parent.parent / "samples"

JOB_DESCRIPTION = """
Senior Full Stack Engineer

About the role
We are looking for a Senior Full Stack Engineer to build and scale our
customer-facing web platform.

Required skills
- Strong JavaScript and TypeScript
- React and Redux for frontend development
- Node.js and Express for backend services
- REST API design
- PostgreSQL
- 3+ years of professional experience

Preferred skills
- Docker
- Kubernetes
- AWS
- CI/CD

Minimum qualifications
Bachelor's degree in Computer Science or equivalent.

Responsibilities
- Design and ship features across the full stack
- Review code and mentor junior engineers
- Improve application performance and reliability
"""


@pytest.fixture()
def client() -> TestClient:
    """Fresh database for each test module."""

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as test_client:
        yield test_client
    Base.metadata.drop_all(bind=engine)


def _pdf(name: str) -> bytes:
    return (SAMPLES / name).read_bytes()


def _upload(client: TestClient, *names: str) -> dict:
    files = [
        ("files", (name, _pdf(name), "application/pdf")) for name in names
    ]
    response = client.post("/api/resumes/upload", files=files)
    assert response.status_code == 200, response.text
    return response.json()


def _analyse_job(client: TestClient, text: str = JOB_DESCRIPTION) -> dict:
    response = client.post("/api/jobs/analyze", json={"job_description": text})
    assert response.status_code == 200, response.text
    return response.json()


def _match(client: TestClient) -> dict:
    response = client.post("/api/matching/analyze", json={"use_ai": False})
    assert response.status_code == 200, response.text
    return response.json()


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
def test_health_still_works(client: TestClient) -> None:
    body = client.get("/api/health").json()
    assert body["status"] in {"ok", "degraded"}
    names = {c["name"] for c in body["components"]}
    assert {"database", "nvidia_nim"} <= names


def test_status_reports_weights(client: TestClient) -> None:
    body = client.get("/api/health/status").json()
    weights = body["integrations"]["matching_weights"]
    assert sum(weights.values()) == 100.0
    assert weights["skill"] == 40.0


# ---------------------------------------------------------------------------
# 1-2. Upload + PDF extraction
# ---------------------------------------------------------------------------
def test_upload_multiple_pdfs(client: TestClient) -> None:
    body = _upload(
        client,
        "rahul_sharma_strong.pdf",
        "priya_patil_mid.pdf",
        "amit_joshi_poor.pdf",
        "neha_sharma_minimal.pdf",
    )
    assert body["uploaded"] == 4
    assert body["failed"] == 0
    assert len(body["resumes"]) == 4

    listed = client.get("/api/resumes").json()
    assert listed["total"] == 4
    # Every uploaded resume produced a structured candidate.
    assert all(item["candidate"] for item in listed["resumes"])


def test_extraction_pulls_contact_and_skills(client: TestClient) -> None:
    _upload(client, "rahul_sharma_strong.pdf")
    candidate = client.get("/api/resumes").json()["resumes"][0]["candidate"]

    assert candidate["name"] == "Rahul Sharma"
    assert candidate["email"] == "rahul.sharma@gmail.com"
    assert candidate["phone"] and "98765" in candidate["phone"]
    skills = {s.lower() for s in candidate["skills"]}
    assert {"react", "python", "postgresql", "docker", "kubernetes"} <= skills
    assert candidate["years_of_experience"] >= 5


def test_sparse_resume_keeps_empty_fields_empty(client: TestClient) -> None:
    """The minimal resume must not be padded with invented information."""

    _upload(client, "neha_sharma_minimal.pdf")
    candidate = client.get("/api/resumes").json()["resumes"][0]["candidate"]

    assert candidate["name"] == "Neha Sharma"
    assert candidate["email"] == "neha.sharma@outlook.com"
    assert candidate["phone"] is None  # nothing written -> stays empty
    assert "python" in {s.lower() for s in candidate["skills"]}
    assert candidate["years_of_experience"] == 0.0


def test_multi_page_extraction(tmp_path: Path) -> None:
    """A PDF whose text spans several pages must be read in full."""

    import pymupdf

    from app.services.pdf_parser import parse_resume_upload

    doc = pymupdf.open()
    for page_no in range(4):
        page = doc.new_page()
        page.insert_text(
            (50, 80),
            f"PAGE {page_no + 1} - JavaScript React Node.js PostgreSQL Docker Kubernetes",
            fontsize=11,
        )
    data = doc.tobytes()
    doc.close()

    parsed = parse_resume_upload(data, "multipage.pdf")
    assert parsed.page_count == 4
    for page_no in range(1, 5):
        assert f"PAGE {page_no}" in parsed.text
    assert "Kubernetes" in parsed.text


# ---------------------------------------------------------------------------
# 13. Error handling
# ---------------------------------------------------------------------------
def test_rejects_non_pdf(tmp_path: Path) -> None:
    fake = tmp_path / "resume.pdf"
    fake.write_bytes(b"this is definitely not a pdf file")

    body = client_error = TestClient(app).post(
        "/api/resumes/upload",
        files=[("files", ("resume.pdf", fake.read_bytes(), "application/pdf"))],
    ).json()
    assert body["uploaded"] == 0
    assert body["errors"][0]["error"] == "invalid_file"


def test_rejects_wrong_extension() -> None:
    body = TestClient(app).post(
        "/api/resumes/upload",
        files=[("files", ("notes.docx", b"hello", "application/msword"))],
    ).json()
    assert body["uploaded"] == 0
    assert body["errors"][0]["error"] == "invalid_file"


def test_rejects_corrupt_pdf() -> None:
    corrupt = b"%PDF-1.4\n" + b"\x00\x01\x02 broken trailer " * 20
    body = TestClient(app).post(
        "/api/resumes/upload",
        files=[("files", ("broken.pdf", corrupt, "application/pdf"))],
    ).json()
    assert body["uploaded"] == 0
    assert body["errors"][0]["error"] in {"pdf_extraction_failed", "insufficient_text"}


def test_rejects_pdf_with_no_text_layer() -> None:
    """Scanned-style PDF: valid file, zero extractable text -> clean error."""

    body = TestClient(app).post(
        "/api/resumes/upload",
        files=[("files", ("empty_scan.pdf", _pdf("empty_scan.pdf"), "application/pdf"))],
    ).json()
    assert body["uploaded"] == 0
    assert body["errors"][0]["error"] == "insufficient_text"
    assert "OCR" in body["errors"][0]["message"]


def test_rejects_empty_file() -> None:
    body = TestClient(app).post(
        "/api/resumes/upload",
        files=[("files", ("empty.pdf", b"", "application/pdf"))],
    ).json()
    assert body["uploaded"] == 0
    assert body["errors"][0]["error"] == "empty_file"


def test_rejects_duplicate_upload(client: TestClient) -> None:
    _upload(client, "rahul_sharma_strong.pdf")
    second = client.post(
        "/api/resumes/upload",
        files=[("files", ("rahul_copy.pdf", _pdf("rahul_sharma_strong.pdf"), "application/pdf"))],
    ).json()
    assert second["uploaded"] == 0
    assert second["errors"][0]["error"] == "duplicate_upload"


def test_batch_isolation_one_bad_file_does_not_block_others(client: TestClient) -> None:
    files = [
        ("files", ("rahul_sharma_strong.pdf", _pdf("rahul_sharma_strong.pdf"), "application/pdf")),
        ("files", ("broken.pdf", b"%PDF-1.4\nnot really a pdf", "application/pdf")),
        ("files", ("priya_patil_mid.pdf", _pdf("priya_patil_mid.pdf"), "application/pdf")),
    ]
    body = client.post("/api/resumes/upload", files=files).json()
    assert body["uploaded"] == 2
    assert body["failed"] == 1


def test_empty_job_description_rejected(client: TestClient) -> None:
    # Empty and whitespace-only are both handled by the route -> 400.
    for value in ("", "   \n\t  "):
        response = client.post("/api/jobs/analyze", json={"job_description": value})
        assert response.status_code == 400, value
        assert response.json()["error"] == "empty_job_description"


def test_too_short_job_description_rejected(client: TestClient) -> None:
    response = client.post("/api/jobs/analyze", json={"job_description": "Need a dev."})
    assert response.status_code == 400
    assert response.json()["error"] == "job_description_too_short"


def test_matching_without_resumes_returns_clean_error(client: TestClient) -> None:
    response = client.post("/api/matching/analyze", json={})
    assert response.status_code == 400
    assert response.json()["error"] == "no_resumes_uploaded"


def test_ai_failure_falls_back_and_still_returns_200(client: TestClient, monkeypatch) -> None:
    """A broken NVIDIA endpoint must not break the MVP."""

    from app.core.errors import AIProviderError
    from app.services import ai_extraction, jd_service

    def boom(*_args, **_kwargs):
        raise AIProviderError("NVIDIA NIM is down (simulated).")

    monkeypatch.setattr(ai_extraction, "get_nvidia_client", lambda: type("C", (), {"ensure_ready": staticmethod(lambda: None), "chat_json": staticmethod(boom)})())
    monkeypatch.setattr(ai_extraction, "get_settings", lambda: type("S", (), {"nvidia_configured": True, "ALLOW_HEURISTIC_FALLBACK": True})())

    result = ai_extraction.extract_candidate("RAHUL SHARMA\nrahul@x.com\nPython React Node.js", use_ai=True)
    assert result.method == "heuristic"
    assert result.data["skills"]
    assert "down" in (result.warning or "")


# ---------------------------------------------------------------------------
# 3-5. Job analysis
# ---------------------------------------------------------------------------
def test_job_analysis_extracts_requirements(client: TestClient) -> None:
    body = _analyse_job(client)
    job = body["job"]

    assert job["job_title"]
    required = {s.lower() for s in job["required_skills"]}
    assert {"javascript", "react", "postgresql"} <= required
    assert job["raw_text"].strip().startswith("Senior Full Stack Engineer")


# ---------------------------------------------------------------------------
# 6-7. Matching + ranking
# ---------------------------------------------------------------------------
def test_full_pipeline_ranks_candidates(client: TestClient) -> None:
    _upload(
        client,
        "rahul_sharma_strong.pdf",
        "priya_patil_mid.pdf",
        "amit_joshi_poor.pdf",
        "neha_sharma_minimal.pdf",
    )
    _analyse_job(client)
    body = _match(client)

    candidates = body["candidates"]
    assert len(candidates) == 4

    scores = [c["match"]["overall_score"] for c in candidates]
    assert scores == sorted(scores, reverse=True), "candidates must be ranked by score"
    assert [c["rank"] for c in candidates] == [1, 2, 3, 4]

    top = candidates[0]
    assert "rahul" in top["candidate"]["name"].lower()
    assert top["match"]["overall_score"] >= 60

    bottom = candidates[-1]
    assert "neha" in bottom["candidate"]["name"].lower() or "amit" in bottom["candidate"]["name"].lower()

    assert body["summary"]["total_candidates"] == 4
    assert body["summary"]["average_match"] > 0


def test_score_components_are_present_and_bounded(client: TestClient) -> None:
    _upload(client, "rahul_sharma_strong.pdf", "amit_joshi_poor.pdf")
    _analyse_job(client)
    match = _match(client)["candidates"][0]["match"]

    for key in (
        "overall_score", "skill_score", "experience_score",
        "education_score", "semantic_score", "evidence_score",
    ):
        assert 0 <= match[key] <= 100, key

    # overall must equal the weighted sum of the components
    weights = match["weights"]
    expected = (
        match["skill_score"] * weights["skill"]
        + match["experience_score"] * weights["experience"]
        + match["education_score"] * weights["education"]
        + match["semantic_score"] * weights["semantic"]
        + match["evidence_score"] * weights["evidence"]
    ) / 100
    assert match["overall_score"] == pytest.approx(expected, abs=0.05)


def test_strong_candidate_beats_poor_candidate(client: TestClient) -> None:
    _upload(client, "rahul_sharma_strong.pdf", "amit_joshi_poor.pdf", "priya_patil_mid.pdf")
    _analyse_job(client)
    candidates = _match(client)["candidates"]

    by_name = {c["candidate"]["name"]: c for c in candidates}
    assert (
        by_name["Rahul Sharma"]["match"]["overall_score"]
        > by_name["Amit Joshi"]["match"]["overall_score"]
    )


def test_breakdown_explains_why(client: TestClient) -> None:
    _upload(client, "priya_patil_mid.pdf")
    _analyse_job(client)
    match = _match(client)["candidates"][0]["match"]

    assert match["matching_skills"], "should list matched skills"
    assert match["evidence"]["skills"]["required_matched"] >= 1
    assert match["evidence"]["experience"]["required_years"] == 3
    assert match["evidence"]["education"]["required_level"] >= 3


def test_matching_is_reproducible(client: TestClient) -> None:
    _upload(client, "rahul_sharma_strong.pdf", "priya_patil_mid.pdf")
    _analyse_job(client)
    first = _match(client)["candidates"]
    second = _match(client)["candidates"]
    assert [c["match"]["overall_score"] for c in first] == [
        c["match"]["overall_score"] for c in second
    ]
    assert [c["candidate"]["name"] for c in first] == [c["candidate"]["name"] for c in second]


# ---------------------------------------------------------------------------
# 8. Search and filtering
# ---------------------------------------------------------------------------
def test_search_by_name_email_and_skill(client: TestClient) -> None:
    _upload(client, "rahul_sharma_strong.pdf", "priya_patil_mid.pdf", "amit_joshi_poor.pdf")
    _analyse_job(client)
    _match(client)

    by_name = client.get("/api/candidates", params={"q": "rahul"}).json()
    assert by_name["total"] == 1
    assert by_name["candidates"][0]["candidate"]["name"] == "Rahul Sharma"

    by_email = client.get("/api/candidates", params={"q": "priya.patil"}).json()
    assert by_email["total"] == 1

    by_skill = client.get("/api/candidates", params={"q": "kubernetes"}).json()
    assert by_skill["total"] == 1
    assert "Rahul" in by_skill["candidates"][0]["candidate"]["name"]


def test_filter_by_min_score(client: TestClient) -> None:
    _upload(client, "rahul_sharma_strong.pdf", "priya_patil_mid.pdf", "amit_joshi_poor.pdf")
    _analyse_job(client)
    _match(client)

    body = client.get("/api/candidates", params={"min_score": 50}).json()
    assert body["total"] >= 1
    assert all(c["match"]["overall_score"] >= 50 for c in body["candidates"])


def test_filter_by_skill_experience_and_education(client: TestClient) -> None:
    _upload(client, "rahul_sharma_strong.pdf", "priya_patil_mid.pdf", "amit_joshi_poor.pdf")
    _analyse_job(client)
    _match(client)

    by_skill = client.get("/api/candidates", params={"skills": "docker"}).json()
    assert all("docker" in c["candidate"]["skills"] for c in by_skill["candidates"])

    by_exp = client.get("/api/candidates", params={"min_experience": 4}).json()
    assert all(c["candidate"]["years_of_experience"] >= 4 for c in by_exp["candidates"])

    by_edu = client.get("/api/candidates", params={"education_level": 3}).json()
    assert all(c["candidate"]["education_level"] >= 3 for c in by_edu["candidates"])

    assert "react" in client.get("/api/candidates").json()["available_skills"]


def test_sorting(client: TestClient) -> None:
    _upload(client, "rahul_sharma_strong.pdf", "amit_joshi_poor.pdf")
    _analyse_job(client)
    _match(client)

    by_score = client.get("/api/candidates", params={"sort": "score"}).json()
    scores = [c["match"]["overall_score"] for c in by_score["candidates"]]
    assert scores == sorted(scores, reverse=True)

    by_name = client.get("/api/candidates", params={"sort": "name"}).json()
    names = [c["candidate"]["name"] for c in by_name["candidates"]]
    assert names == sorted(names)


def test_no_match_returns_clean_error(client: TestClient) -> None:
    _upload(client, "rahul_sharma_strong.pdf")
    _analyse_job(client)
    _match(client)

    response = client.get("/api/candidates", params={"q": "zzzzzzzznotacandidate"})
    assert response.status_code == 404
    assert response.json()["error"] == "no_candidates_found"


def test_skill_filter_matches_whole_tokens_only(client: TestClient) -> None:
    """A skill filter must not match skills that merely contain the term.

    ``skills=java`` has to exclude a candidate whose resume lists
    ``javascript``; a bare ``LIKE '%java%'`` would wrongly include them.
    """

    _upload(client, "rahul_sharma_strong.pdf")
    _analyse_job(client)
    _match(client)

    javascript_only = client.get("/api/candidates", params={"skills": "javascript"})
    assert javascript_only.status_code == 200
    assert javascript_only.json()["total"] >= 1

    # "java" is a substring of "javascript" but not a listed skill.
    assert client.get("/api/candidates", params={"skills": "java"}).status_code == 404

    # A near-miss spelling must not match either.
    assert client.get("/api/candidates", params={"skills": "kubernets"}).status_code == 404


def test_multiple_skills_filter_requires_all(client: TestClient) -> None:
    _upload(client, "rahul_sharma_strong.pdf", "amit_joshi_poor.pdf")
    _analyse_job(client)
    _match(client)

    both = client.get("/api/candidates", params={"skills": "javascript,react"})
    assert both.status_code == 200
    assert both.json()["total"] >= 1

    # Amit is a frontend dev: react yes, postgresql no.
    partial = client.get("/api/candidates", params={"skills": "javascript,postgresql"})
    names = [c["candidate"]["name"] for c in partial.json()["candidates"]]
    assert "Rahul Sharma" in names
    assert "Amit Joshi" not in names


def test_location_is_not_confused_with_a_skill_list(client: TestClient) -> None:
    """``Languages: JavaScript, TypeScript`` must not be read as a location."""

    _upload(client, "rahul_sharma_strong.pdf", "neha_sharma_minimal.pdf")
    candidates = {
        c["candidate"]["name"]: c["candidate"]["location"]
        for c in client.get("/api/resumes").json()["resumes"]
        if c["candidate"]
    }

    assert candidates["Rahul Sharma"] == "Bangalore, India"
    # Neha's resume lists no location at all.
    assert not candidates["Neha Sharma"]


def test_education_levels_are_detected() -> None:
    """B.E and B.Com must be recognised, not silently dropped."""

    from app.services.ai_extraction import education_level_of, extract_candidate

    b_e = extract_candidate(
        "PRIYA PATIL\npriya@x.com\nEDUCATION\nB.E Computer Engineering | University of Pune | 2019",
        use_ai=False,
    ).data
    assert b_e["education"], "B.E should be recognised as a degree"
    assert education_level_of(b_e["education"]) == 3

    b_com = extract_candidate(
        "NEHA SHARMA\nneha@x.com\nEDUCATION\nB.Com | University of Rajasthan | 2021",
        use_ai=False,
    ).data
    assert b_com["education"], "B.Com should be recognised as a degree"
    assert education_level_of(b_com["education"]) == 3


# ---------------------------------------------------------------------------
# 9. Explainability
# ---------------------------------------------------------------------------
def test_every_candidate_gets_an_explanation(client: TestClient) -> None:
    _upload(client, "rahul_sharma_strong.pdf", "amit_joshi_poor.pdf")
    _analyse_job(client)
    _match(client)

    for candidate in client.get("/api/candidates").json()["candidates"]:
        explanation = candidate["explanation"]
        assert explanation and len(explanation) > 30
        assert candidate["explanation_method"] in {"template", "ai"}
        assert "*" not in explanation, "explanations are plain prose"


def test_candidate_detail_has_evidence_and_breakdown(client: TestClient) -> None:
    _upload(client, "rahul_sharma_strong.pdf")
    _analyse_job(client)
    _match(client)

    uid = client.get("/api/candidates").json()["candidates"][0]["candidate"]["candidate_uid"]
    body = client.get(f"/api/candidates/{uid}").json()

    assert body["candidate"]["skills"]
    assert body["resume_text"]
    assert body["match"]["overall_score"] > 0
    assert body["explanation"]
    assert body["job"]["required_skills"]
    assert body["match"]["evidence"]["skills"]["required_total"] > 0


def test_candidate_detail_unknown_id(client: TestClient) -> None:
    response = client.get("/api/candidates/does-not-exist")
    assert response.status_code == 404
    assert response.json()["error"] == "not_found"


# ---------------------------------------------------------------------------
# One-shot endpoint used by the dashboard
# ---------------------------------------------------------------------------
def test_analyze_and_upload_single_request(client: TestClient) -> None:
    files = [
        ("files", ("rahul_sharma_strong.pdf", _pdf("rahul_sharma_strong.pdf"), "application/pdf")),
        ("files", ("priya_patil_mid.pdf", _pdf("priya_patil_mid.pdf"), "application/pdf")),
    ]
    response = client.post(
        "/api/matching/analyze-and-upload",
        data={"job_description": JOB_DESCRIPTION, "use_ai": "false"},
        files=files,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["candidates"]) == 2
    assert body["summary"]["average_match"] > 0


def test_one_shot_rejects_empty_job_description(client: TestClient) -> None:
    response = client.post(
        "/api/matching/analyze-and-upload",
        data={"job_description": ""},
        files=[("files", ("rahul_sharma_strong.pdf", _pdf("rahul_sharma_strong.pdf"), "application/pdf"))],
    )
    assert response.status_code == 400


def test_delete_all_resumes(client: TestClient) -> None:
    _upload(client, "rahul_sharma_strong.pdf")
    body = client.delete("/api/resumes").json()
    assert body["deleted"] == 1
    assert client.get("/api/resumes").json()["total"] == 0