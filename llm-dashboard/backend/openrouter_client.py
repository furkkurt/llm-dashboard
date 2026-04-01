"""OpenRouter: OpenAI-compatible chat completions (https://openrouter.ai/docs)."""

from __future__ import annotations

import os
from typing import Any

from openai import OpenAI

from backend.env_bootstrap import load_dashboard_env


def _default_model() -> str:
    return os.getenv("OPENROUTER_MODEL", "google/gemini-2.0-flash-001").strip()


def openrouter_client(*, timeout: float) -> OpenAI:
    load_dashboard_env()
    key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not key:
        raise ValueError("OPENROUTER_API_KEY not set")
    base = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").strip().rstrip("/")
    referer = os.getenv("OPENROUTER_HTTP_REFERER", "").strip() or "http://127.0.0.1"
    title = os.getenv("OPENROUTER_APP_TITLE", "LLM Eval Dashboard").strip()
    return OpenAI(
        api_key=key,
        base_url=base,
        timeout=timeout,
        default_headers={
            "HTTP-Referer": referer,
            "X-OpenRouter-Title": title,
        },
    )


def openrouter_chat_completion(
    *,
    messages: list[dict[str, Any]],
    model: str | None = None,
    timeout: float,
    max_tokens: int = 4096,
    temperature: float = 0.2,
    response_format: dict[str, str] | None = None,
) -> tuple[str, str]:
    """
    Returns (assistant_text, resolved_model_id).
    Raises on HTTP / API errors (OpenAI SDK).
    """
    client = openrouter_client(timeout=timeout)
    mid = (model or _default_model()).strip()
    kwargs: dict[str, Any] = {
        "model": mid,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if response_format is not None:
        kwargs["response_format"] = response_format
    completion = client.chat.completions.create(**kwargs)
    choice = completion.choices[0].message
    text = (choice.content or "").strip()
    used = getattr(completion, "model", None) or mid
    return text, used
