"""Resume: the uploaded file plus its extracted raw text."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Resume(Base):
    __tablename__ = "resumes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    resume_uid: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    original_filename: Mapped[str] = mapped_column(String(255))
    stored_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)

    file_size: Mapped[int] = mapped_column(Integer, default=0)
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    char_count: Mapped[int] = mapped_column(Integer, default=0)

    # Raw extracted + cleaned text, stored verbatim as the evidence source.
    raw_text: Mapped[str] = mapped_column(Text, default="")

    # Extraction status: uploaded | extracted | failed
    status: Mapped[str] = mapped_column(String(32), default="uploaded", index=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # how | heuristic  -> provenance of the structured extraction
    extraction_method: Mapped[str | None] = mapped_column(String(32), nullable=True)
    extraction_latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    extraction_cost_tokens: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)