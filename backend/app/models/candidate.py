"""Candidate: structured information extracted from a resume."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Candidate(Base):
    __tablename__ = "candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    candidate_uid: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    resume_id: Mapped[int] = mapped_column(
        ForeignKey("resumes.id", ondelete="CASCADE"), unique=True, index=True
    )

    name: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # JSON columns keep the MVP schema-free; structured text is still indexed
    # through ``skills_flat`` for SQL-side search/filtering.
    skills: Mapped[list] = mapped_column(JSON, default=list)
    education: Mapped[list] = mapped_column(JSON, default=list)
    experience: Mapped[list] = mapped_column(JSON, default=list)
    projects: Mapped[list] = mapped_column(JSON, default=list)
    certifications: Mapped[list] = mapped_column(JSON, default=list)

    # Denormalised lowercase skills for fast SQL LIKE filtering.
    skills_flat: Mapped[str] = mapped_column(Text, default="", index=True)
    years_of_experience: Mapped[float] = mapped_column(Float, default=0.0, index=True)
    education_level: Mapped[int] = mapped_column(Integer, default=0, index=True)

    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Explicitly stated vs inferred - kept separate as required.
    stated_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    @staticmethod
    def flat_skills(skills: list[str]) -> str:
        """Space-joined skills for SQL ``LIKE`` searches."""

        return " ".join(sorted({s.lower() for s in skills if s}))

    def as_dict(self) -> dict:
        return {
            "candidate_uid": self.candidate_uid,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "location": self.location,
            "skills": self.skills or [],
            "education": self.education or [],
            "experience": self.experience or [],
            "projects": self.projects or [],
            "certifications": self.certifications or [],
            "years_of_experience": self.years_of_experience,
            "education_level": self.education_level,
            "summary": self.summary,
        }