"""SQLAlchemy engine, session factory and FastAPI DB dependency."""

from __future__ import annotations

import logging
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

logger = logging.getLogger(__name__)

_connect_args: dict = {}
if settings.DATABASE_URL.startswith("sqlite"):
    # SQLite + FastAPI's threadpool needs this check disabled.
    _connect_args["check_same_thread"] = False

engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.SQL_ECHO,
    future=True,
    connect_args=_connect_args,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    """Declarative base shared by every ORM model."""


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a request-scoped session."""

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create tables for any imported models (idempotent)."""

    from app import models  # noqa: F401  (ensure models are registered)

    Base.metadata.create_all(bind=engine)
    logger.info("Tables ensured: %s", ", ".join(sorted(Base.metadata.tables)) or "none yet")