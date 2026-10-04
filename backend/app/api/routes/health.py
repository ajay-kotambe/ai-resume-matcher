"""Health and readiness probes."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.schemas.mvp import ComponentStatus, HealthResponse, StatusResponse

router = APIRouter()


def _check_database(db: Session) -> ComponentStatus:
    """Ping the database with a trivial query."""

    try:
        db.execute(text("SELECT 1"))
        return ComponentStatus(name="database", status="ok", detail="connection successful")
    except SQLAlchemyError as exc:
        db.rollback()
        return ComponentStatus(name="database", status="degraded", detail=str(exc))


def _check_ai(settings: Settings) -> ComponentStatus:
    """Report AI readiness. Makes no external call."""

    if settings.nvidia_configured:
        return ComponentStatus(
            name="nvidia_nim",
            status="ok",
            detail=f"key configured, model={settings.NVIDIA_MODEL}",
        )
    return ComponentStatus(
        name="nvidia_nim",
        status="degraded",
        detail="NVIDIA_API_KEY not set - using deterministic heuristic extraction",
    )


@router.get("", response_model=HealthResponse, summary="Health check")
@router.get("/", response_model=HealthResponse, include_in_schema=False)
def health(
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[Session, Depends(get_db)],
) -> HealthResponse:
    """Liveness check used by the React frontend and deployment probes."""

    components = [_check_database(db), _check_ai(settings)]
    overall = "ok" if all(c.status == "ok" for c in components) else "degraded"
    return HealthResponse(
        status=overall,
        version=settings.VERSION,
        environment=settings.ENVIRONMENT,
        timestamp=datetime.now(timezone.utc),
        components=components,
    )


@router.get("/status", response_model=StatusResponse, summary="Feature readiness")
def status(settings: Annotated[Settings, Depends(get_settings)]) -> StatusResponse:
    """Report which integrations are configured (no AI calls are made)."""

    return StatusResponse(
        success=True,
        project=settings.PROJECT_NAME,
        version=settings.VERSION,
        environment=settings.ENVIRONMENT,
        integrations={
            "database": {"configured": True, "engine": settings.DATABASE_URL.split(":")[0]},
            "nvidia_nim": {
                "configured": settings.nvidia_configured,
                "base_url": settings.NVIDIA_BASE_URL,
                "model": settings.NVIDIA_MODEL,
                "timeout_s": settings.NVIDIA_TIMEOUT,
            },
            "embeddings": {
                "configured": True,
                "model": settings.EMBEDDING_MODEL,
                "dimension": settings.EMBEDDING_DIMENSION,
                "similarity": "cosine",
            },
            "resume_parsing": {"configured": True, "library": "PyMuPDF"},
            "matching_weights": settings.weights,
            "limits": {
                "max_upload_mb": settings.MAX_UPLOAD_SIZE_MB,
                "min_extractable_chars": settings.MIN_EXTRACTABLE_CHARS,
            },
        },
    )