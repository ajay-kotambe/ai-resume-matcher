"""JobDescription: raw text plus structured requirements extracted by AI."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_uid() -> str:
    return uuid.uuid4().hex


class JobDescription(Base):
    __tablename__ = "job_descriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_uid: Mapped[str] = mapped_column(String(64), unique=True, index=True, default=_new_uid)

    job_title: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    company: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Original JD kept verbatim, as required.
    raw_text: Mapped[str] = mapped_column(Text)

    required_skills: Mapped[list] = mapped_column(JSON, default=list)
    preferred_skills: Mapped[list] = mapped_column(JSON, default=list)
    minimum_experience: Mapped[str | None] = mapped_column(String(64), nullable=True)
    minimum_years: Mapped[float] = mapped_column(Float, default=0.0)
    education_requirements: Mapped[list] = mapped_column(JSON, default=list)
    responsibilities: Mapped[list] = mapped_column(JSON, default=list)

    extraction_method: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)