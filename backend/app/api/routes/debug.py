# Temporary diagnostic routes.
from __future__ import annotations

import logging
import time
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/nvidia", summary="Minimal NVIDIA NIM diagnostic (temporary)")
def debug_nvidia(
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Make a single minimal inference request to verify connectivity."""

    url = f"{settings.NVIDIA_BASE_URL.rstrip('/')}/chat/completions"
    payload = {
        "model": settings.NVIDIA_MODEL,
        "messages": [
            {"role": "system", "content": "Reply with the exact requested string."},
            {"role": "user", "content": "Reply with exactly: OK"},
        ],
        "temperature": 0,
        "max_tokens": 16,
        "stream": False,
    }
    headers = {
        "Authorization": f"Bearer {settings.NVIDIA_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    started = time.perf_counter()
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(url, headers=headers, json=payload)
        response_time_ms = int((time.perf_counter() - started) * 1000)
        http_status = response.status_code
        error_type = None
        error_message = None
        success = http_status < 400

        try:
            data = response.json()
        except Exception:
            data = {"text_preview": (response.text or "")[:200]}

        if not success:
            try:
                body = response.json()
            except Exception:
                body = None
            if isinstance(body, dict):
                err = body.get("error")
                if isinstance(err, dict):
                    error_message = str(err.get("message") or err)
                    error_type = str(err.get("type") or "error")
                else:
                    error_message = str(body)[:200]
                    error_type = "error"
            else:
                error_message = (response.text or "")[:200] or response.reason_phrase
                error_type = "http_error"

        return {
            "success": success,
            "http_status": http_status,
            "response_time_ms": response_time_ms,
            "model": settings.NVIDIA_MODEL,
            "error_type": error_type,
            "error_message": error_message,
            "response": data if success else None,
        }
    except httpx.TimeoutException as exc:
        response_time_ms = int((time.perf_counter() - started) * 1000)
        return {
            "success": False,
            "http_status": None,
            "response_time_ms": response_time_ms,
            "model": settings.NVIDIA_MODEL,
            "error_type": "timeout",
            "error_message": str(exc) or "request timed out",
            "response": None,
        }
    except httpx.HTTPError as exc:
        response_time_ms = int((time.perf_counter() - started) * 1000)
        return {
            "success": False,
            "http_status": None,
            "response_time_ms": response_time_ms,
            "model": settings.NVIDIA_MODEL,
            "error_type": type(exc).__name__,
            "error_message": str(exc) or "network error",
            "response": None,
        }
    except Exception as exc:
        response_time_ms = int((time.perf_counter() - started) * 1000)
        return {
            "success": False,
            "http_status": None,
            "response_time_ms": response_time_ms,
            "model": settings.NVIDIA_MODEL,
            "error_type": type(exc).__name__,
            "error_message": str(exc) or "unexpected error",
            "response": None,
        }
