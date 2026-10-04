"""FastAPI application entrypoint.

Run locally with:

    uvicorn app.main:app --reload
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.router import api_router
from app.core.config import settings
from app.core.errors import AppError
from app.db.session import engine, init_db

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Create database tables on startup and dispose the engine on shutdown."""

    try:
        init_db()
        logger.info("Database ready: %s", _safe_db_target())
    except Exception:  # noqa: BLE001 - never block startup on DB issues
        logger.exception("Database initialisation failed; continuing anyway")

    logger.info("%s v%s started (env=%s)", settings.PROJECT_NAME, settings.VERSION, settings.ENVIRONMENT)
    yield

    engine.dispose()
    logger.info("Shutdown complete")


def _safe_db_target() -> str:
    """Return the database URL without leaking credentials."""

    url = settings.DATABASE_URL
    if "@" in url:
        return url.split("@")[-1]
    return url


app = FastAPI(
    title=settings.PROJECT_NAME,
    description=settings.DESCRIPTION,
    version=settings.VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Process-Time"],
)


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Attach a simple timing header to every response."""

    import time

    started = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Process-Time"] = f"{(time.perf_counter() - started) * 1000:.2f}ms"
    return response


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    """Return a consistent 422 payload for request validation errors."""

    # Pydantic error payloads can contain non-serialisable ctx objects.
    safe_errors = [
        {key: value for key, value in item.items() if key in {"type", "loc", "msg"}}
        for item in exc.errors()
    ]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "error": "validation_error",
            "message": "Request payload failed validation.",
            "details": safe_errors,
        },
    )


@app.exception_handler(AppError)
async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    """Map every expected application error to a clean JSON response."""

    logger.info("%s: %s", exc.code, exc.message)
    return JSONResponse(status_code=exc.status_code, content=exc.to_dict())


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    """Catch-all handler so the API never returns an empty HTML error page.

    Stack traces are logged server-side only; the client gets a generic message
    so internals (and secrets) are never leaked.
    """

    logger.exception("Unhandled error: %s", exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": "internal_server_error",
            "message": "An unexpected error occurred. Please check the server logs.",
        },
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/", tags=["root"], summary="Service status")
async def root() -> dict:
    """Root endpoint: quick service identity and health summary."""

    return {
        "success": True,
        "message": f"{settings.PROJECT_NAME} backend is running.",
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "docs": "/docs",
        "api_prefix": settings.API_V1_PREFIX,
        "links": {
            "health": f"{settings.API_V1_PREFIX}/health",
            "status": f"{settings.API_V1_PREFIX}/status",
        },
    }


@app.get("/health", tags=["root"], include_in_schema=False)
async def root_health() -> dict:
    """Alias of ``/api/health`` for infrastructure probes."""

    return {
        "success": True,
        "status": "ok",
        "version": settings.VERSION,
    }