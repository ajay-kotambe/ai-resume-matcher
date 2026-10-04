"""ORM models for the MVP."""

from app.db.session import Base

__all__ = ["Resume", "Candidate", "JobDescription", "MatchResult"]

from app.models.candidate import Candidate
from app.models.job import JobDescription
from app.models.match_result import MatchResult
from app.models.resume import Resume