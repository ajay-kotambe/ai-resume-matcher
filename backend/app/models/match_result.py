"""MatchResult: deterministic score breakdown + generated explanation."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MatchResult(Base):
    __tablename__ = "match_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("candidates.id", ondelete="CASCADE"), index=True
    )
    job_id: Mapped[int] = mapped_column(
        ForeignKey("job_descriptions.id", ondelete="CASCADE"), index=True
    )

    # --- deterministic component scores (0-100 each) ---
    overall_score: Mapped[float] = mapped_column(Float, index=True)
    skill_score: Mapped[float] = mapped_column(Float, default=0.0)
    experience_score: Mapped[float] = mapped_column(Float, default=0.0)
    education_score: Mapped[float] = mapped_column(Float, default=0.0)
    semantic_score: Mapped[float] = mapped_column(Float, default=0.0)
    evidence_score: Mapped[float] = mapped_column(Float, default=0.0)

    # --- explainability payload ---
    matching_skills: Mapped[list] = mapped_column(JSON, default=list)
    partial_skills: Mapped[list] = mapped_column(JSON, default=list)
    missing_skills: Mapped[list] = mapped_column(JSON, default=list)
    extra_skills: Mapped[list] = mapped_column(JSON, default=list)
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    weights: Mapped[dict] = mapped_column(JSON, default=dict)

    # --- LLM explanation (never alters the score) ---
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    explanation_method: Mapped[str | None] = mapped_column(String(32), nullable=True)

    rank: Mapped[int] = mapped_column(Integer, default=0, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    def as_dict(self) -> dict:
        return {
            "candidate_id": self.candidate_id,
            "job_id": self.job_id,
            "overall_score": round(self.overall_score, 2),
            "skill_score": round(self.skill_score, 2),
            "experience_score": round(self.experience_score, 2),
            "education_score": round(self.education_score, 2),
            "semantic_score": round(self.semantic_score, 2),
            "evidence_score": round(self.evidence_score, 2),
            "matching_skills": self.matching_skills or [],
            "partial_skills": self.partial_skills or [],
            "missing_skills": self.missing_skills or [],
            "extra_skills": self.extra_skills or [],
            "evidence": self.evidence or {},
            "weights": self.weights or {},
            "explanation": self.explanation,
            "explanation_method": self.explanation_method,
            "rank": self.rank,
        }