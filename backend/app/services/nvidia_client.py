"""NVIDIA NIM client (OpenAI-compatible API).

Used for:
  * structured resume extraction   (DeepSeek)
  * structured JD analysis         (DeepSeek)
  * natural-language explanations  (DeepSeek)

The API key is only ever read from settings/.env - never logged or returned.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass

import httpx

from app.core.config import Settings, get_settings
from app.core.errors import (
    AIKeyMissingError,
    AIProviderError,
    AIResponseError,
    AITimeoutError,
)

logger = logging.getLogger(__name__)


@dataclass
class AIResult:
    """Normalised result of a chat completion."""

    content: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: int = 0
    raw: dict | None = None


class NvidiaNIMClient:
    """Thin HTTP wrapper around NVIDIA's ``/chat/completions`` endpoint."""

    def __init__(self, config: Settings | None = None) -> None:
        self.config = config or get_settings()

    # -- guards ---------------------------------------------------------
    @property
    def is_configured(self) -> bool:
        return bool(self.config.NVIDIA_API_KEY.strip())

    def ensure_ready(self) -> None:
        """Raise a clear, actionable error when the key is missing."""

        if not self.is_configured:
            raise AIKeyMissingError(
                "NVIDIA_API_KEY is not configured. Add it to backend/.env "
                "(copy from .env.example) to enable AI extraction."
            )

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.config.NVIDIA_API_KEY}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _url(self) -> str:
        return f"{self.config.NVIDIA_BASE_URL.rstrip('/')}/chat/completions"

    # -- main call ------------------------------------------------------
    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.0,
        max_tokens: int = 2048,
        response_format: dict | None = None,
        model: str | None = None,
    ) -> AIResult:
        """Call the chat endpoint with retry/backoff.

        Raises ``AITimeoutError`` on timeout and ``AIProviderError`` on any
        other upstream failure. Never leaks the key or a stack trace.
        """

        self.ensure_ready()
        model_name = model or self.config.NVIDIA_MODEL

        payload: dict = {
            "model": model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if response_format:
            payload["response_format"] = response_format

        attempts = max(1, self.config.NVIDIA_MAX_RETRIES + 1)
        last_exc: Exception | None = None

        for attempt in range(1, attempts + 1):
            started = time.perf_counter()
            try:
                with httpx.Client(timeout=self.config.NVIDIA_TIMEOUT) as client:
                    response = client.post(self._url(), headers=self._headers(), json=payload)

                if response.status_code >= 400:
                    detail = _safe_error_detail(response)
                    # 4xx other than 429 will not improve on retry.
                    if response.status_code < 500 and response.status_code != 429:
                        raise AIProviderError(
                            f"NVIDIA NIM rejected the request ({response.status_code}): {detail}",
                            details={"status_code": response.status_code, "model": model_name},
                        )
                    raise AIProviderError(
                        f"NVIDIA NIM temporarily unavailable ({response.status_code}): {detail}",
                        details={"status_code": response.status_code},
                    )

                data = response.json()
                latency_ms = int((time.perf_counter() - started) * 1000)

                content = _extract_content(data)
                usage = data.get("usage") or {}
                logger.info(
                    "NVIDIA NIM ok model=%s latency=%sms tokens=%s/%s",
                    model_name,
                    latency_ms,
                    usage.get("prompt_tokens", 0),
                    usage.get("completion_tokens", 0),
                )
                return AIResult(
                    content=content,
                    model=model_name,
                    prompt_tokens=int(usage.get("prompt_tokens") or 0),
                    completion_tokens=int(usage.get("completion_tokens") or 0),
                    latency_ms=latency_ms,
                    raw=data,
                )

            except httpx.TimeoutException as exc:
                last_exc = exc
                logger.warning("NVIDIA NIM timeout (attempt %s/%s)", attempt, attempts)
            except httpx.HTTPError as exc:
                last_exc = exc
                logger.warning("NVIDIA NIM network error (attempt %s/%s): %s", attempt, attempts, exc)
            except (AIProviderError, AIResponseError):
                raise
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                logger.exception("Unexpected NVIDIA NIM failure")

            if attempt < attempts:
                time.sleep(min(2**attempt, 8))

        raise AITimeoutError(
            "The AI provider did not respond in time. "
            "Please retry, or continue without AI extraction.",
            details={"attempts": attempts, "last_error": type(last_exc).__name__ if last_exc else None},
        )

    # -- structured JSON helper ----------------------------------------
    def chat_json(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> tuple[dict, AIResult]:
        """Call the model and parse a strict JSON object out of the reply."""

        result = self.chat(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )
        return parse_json_object(result.content), result


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------
def _extract_content(data: dict) -> str:
    """Pull the assistant message text out of an OpenAI-compatible payload."""

    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise AIResponseError(
            "AI provider returned an unexpected response shape.",
            details={"keys": sorted(data.keys()) if isinstance(data, dict) else None},
        ) from exc

    if isinstance(content, list):  # some providers return content parts
        content = "".join(
            part.get("text", "") for part in content if isinstance(part, dict)
        )
    if not isinstance(content, str) or not content.strip():
        raise AIResponseError("AI provider returned an empty completion.")
    return content.strip()


def _safe_error_detail(response: httpx.Response) -> str:
    """Extract a short, non-sensitive error message from an upstream error."""

    try:
        body = response.json()
    except Exception:  # noqa: BLE001
        return (response.text or "")[:200] or response.reason_phrase

    err = body.get("error") if isinstance(body, dict) else None
    if isinstance(err, dict):
        return str(err.get("message") or err)[:200]
    if isinstance(err, str):
        return err[:200]
    return str(body)[:200]


def parse_json_object(content: str) -> dict:
    """Parse JSON from a model reply, tolerating markdown fences/prose.

    Raises ``AIResponseError`` when no JSON object can be recovered.
    """

    if not content or not content.strip():
        raise AIResponseError("AI provider returned an empty response.")

    text = content.strip()

    # Strip ```json fences.
    fence = re.search(r"```(?:json)?\s*(.+?)\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()

    candidates = [text]

    # Extract the outermost {...} block.
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        candidates.append(text[start : end + 1])

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed

    raise AIResponseError(
        "Could not parse JSON from the AI response.",
        details={"preview": text[:200]},
    )


_client: NvidiaNIMClient | None = None


def get_nvidia_client() -> NvidiaNIMClient:
    """Shared client instance."""

    global _client
    if _client is None:
        _client = NvidiaNIMClient()
    return _client