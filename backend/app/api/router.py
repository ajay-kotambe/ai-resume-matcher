"""Aggregated API router (mounted under ``/api``)."""

from fastapi import APIRouter

from app.api.routes import candidates, debug, health, jobs, matching, resumes

api_router = APIRouter()

api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(debug.router, prefix="/debug", tags=["debug"])
api_router.include_router(resumes.router, prefix="/resumes", tags=["resumes"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
api_router.include_router(matching.router, prefix="/matching", tags=["matching"])
api_router.include_router(candidates.router, prefix="/candidates", tags=["candidates"])

__all__ = ["api_router"]