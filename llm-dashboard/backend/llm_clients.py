import os
import re

import anthropic

from openai import OpenAI

from backend.llm_prompts import build_system_instruction
from backend.models import GenerateRequest, GenerateResponse, TargetLanguage


def _timeout_sec() -> float:
    try:
        return float(os.getenv("LLM_REQUEST_TIMEOUT_SEC", "120"))
    except ValueError:
        return 120.0


def _extract_fenced_code(text: str, target_language: TargetLanguage) -> str:
    lang = "kotlin" if target_language == "Kotlin" else "dart"
    patterns = [
        rf"```{lang}\s*\n(.*?)```",
        r"```(?:kotlin|dart)\s*\n(.*?)```",
        r"```\s*\n(.*?)```",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.DOTALL | re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return ""


def _openai_generate(req: GenerateRequest, system: str, timeout: float) -> str:
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        raise ValueError("OpenAI API key not configured.")
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()
    client = OpenAI(api_key=key, timeout=timeout)
    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": req.prompt},
        ],
    )
    choice = completion.choices[0].message
    return (choice.content or "").strip()


def _anthropic_generate(req: GenerateRequest, system: str, timeout: float) -> str:
    key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not key:
        raise ValueError("Anthropic API key not configured.")
    model = os.getenv("ANTHROPIC_MODEL", "claude-3-5-haiku-20241022").strip()
    client = anthropic.Anthropic(api_key=key, timeout=timeout)
    msg = client.messages.create(
        model=model,
        max_tokens=8192,
        system=system,
        messages=[{"role": "user", "content": req.prompt}],
    )
    parts: list[str] = []
    for block in msg.content:
        if hasattr(block, "text"):
            parts.append(block.text)
    return "".join(parts).strip()


def _gemini_generate(req: GenerateRequest, system: str, timeout: float) -> str:
    """UI label 'Gemini': routed via OpenRouter (same key as commentary)."""
    from backend.openrouter_client import openrouter_chat_completion

    key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not key:
        raise ValueError("OpenRouter API key not configured (OPENROUTER_API_KEY).")
    model_id = os.getenv("OPENROUTER_MODEL", "google/gemini-2.0-flash-001").strip()
    text, _used = openrouter_chat_completion(
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": req.prompt},
        ],
        model=model_id,
        timeout=timeout,
        max_tokens=8192,
        temperature=0.3,
    )
    return text


def run_generation(req: GenerateRequest) -> GenerateResponse:
    timeout = _timeout_sec()
    system = build_system_instruction(target_language=req.target_language)
    try:
        if req.llm_source == "ChatGPT":
            raw = _openai_generate(req, system, timeout)
        elif req.llm_source == "Claude":
            raw = _anthropic_generate(req, system, timeout)
        else:
            raw = _gemini_generate(req, system, timeout)
    except ValueError as e:
        return GenerateResponse(status="error", detail=str(e))
    except Exception as e:
        msg = str(e).strip() or type(e).__name__
        low = msg.lower()
        if "rate" in low or "429" in msg:
            msg = "Provider rate limit or quota exceeded. Try again later."
        elif "401" in msg or "403" in msg:
            msg = "Provider rejected the API key or request."
        return GenerateResponse(status="error", detail=msg)

    if not raw:
        return GenerateResponse(
            status="error",
            detail="The model returned an empty response.",
        )

    suggestion = _extract_fenced_code(raw, req.target_language)
    return GenerateResponse(
        status="success",
        generated_text=raw,
        code_suggestion=suggestion,
    )
