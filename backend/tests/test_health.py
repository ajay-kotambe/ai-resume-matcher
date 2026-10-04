"""Smoke tests for the Phase 1 setup.

Run:  pytest -q      (from the backend/ directory)
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root_endpoint() -> None:
    response = client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert "version" in body


def test_health_endpoint() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] in {"ok", "degraded"}
    assert any(c["name"] == "database" for c in body["components"])


def test_status_endpoint() -> None:
    response = client.get("/api/health/status")
    assert response.status_code == 200
    integrations = response.json()["integrations"]
    assert "nvidia_nim" in integrations
    assert "embeddings" in integrations


def test_openapi_schema() -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert "/api/health" in response.json()["paths"]


def test_cors_preflight() -> None:
    response = client.options(
        "/api/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"