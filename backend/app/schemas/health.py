"""Pydantic schemas for health/status responses."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ComponentStatus(BaseModel):
    """Status of a single infrastructure component."""

    name: str
    status: str = Field(description="ok | degraded | down")
    detail: str | None = None


class HealthResponse(BaseModel):
    """Payload returned by ``GET /api/health``."""

    success: bool = True
    status: str = Field(description="ok | degraded | down")
    version: str
    environment: str
    timestamp: datetime
    components: list[ComponentStatus] = Field(default_factory=list)


class StatusResponse(BaseModel):
    """Payload returned by ``GET /api/health/status``."""

    success: bool = True
    project: str
    version: str
    environment: str
    integrations: dict[str, dict[str, Any]] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    """Uniform error envelope."""

    success: bool = False
    error: str
    message: str
    details: Any | None = None