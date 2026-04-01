"""Minimal Gemini API smoke test (same env vars as AI commentary)."""

from __future__ import annotations

import json
import os
from typing import Any

from backend.env_bootstrap import (
    dashboard_dotenv_path,
    google_api_key_line_state,
    load_dashboard_env,
    local_dashboard_env_path,
)


def _response_text(response: Any) -> str:
    text = getattr(response, "text", None) or ""
    if not text and getattr(response, "candidates", None):
        cand = response.candidates[0]
        content = getattr(cand, "content", None)
        if content and getattr(content, "parts", None):
            text = "".join(getattr(p, "text", "") for p in content.parts)
    return (text or "").strip()


def run_gemini_smoke_test() -> dict[str, Any]:
    """
    One cheap generateContent call. Returns a dict suitable for JSON / GeminiHealthResponse.

    Uses GOOGLE_API_KEY, GOOGLE_MODEL, COMMENTARY_TIMEOUT_SEC (capped at 30s for this check).
    """
    env_path = dashboard_dotenv_path()
    local_path = local_dashboard_env_path()
    dotenv_present = env_path.is_file()
    local_present = local_path.is_file()
    load_dashboard_env()

    def _paths_meta() -> dict[str, Any]:
        return {
            "env_file": str(env_path),
            "env_file_present": dotenv_present,
            "local_env_file": str(local_path),
            "local_env_present": local_present,
        }

    key = os.getenv("GOOGLE_API_KEY", "").strip()
    if not key:
        line_state = google_api_key_line_state()
        err = "GOOGLE_API_KEY not set or empty."
        if not dotenv_present and not local_present:
            err += (
                f" Create `{env_path.name}` or `{local_path.name}` next to `backend/` "
                f"(see `local.env.example`). `setup.sh` does not create either file."
            )
        elif line_state == "empty":
            err += (
                " On disk, GOOGLE_API_KEY= has no value after '=' in `.env` and/or `local.env`. "
                "Save the file. Prefer putting secrets only in `local.env` so a reset `.env` cannot wipe keys."
            )
        elif line_state == "missing":
            err += f" Add GOOGLE_API_KEY=... to `{local_path.name}` (recommended) or `{env_path.name}`."
        else:
            err += (
                " Check GOOGLE_API_KEY= in `.env` / `local.env`: no spaces around '='; "
                "no second empty GOOGLE_API_KEY= line after a good one."
            )
        return {
            "ok": False,
            "model": None,
            "error": err,
            "preview": None,
            **_paths_meta(),
        }

    model_id = os.getenv("GOOGLE_MODEL", "gemini-2.0-flash").strip()
    try:
        timeout = float(os.getenv("COMMENTARY_TIMEOUT_SEC", "60"))
    except ValueError:
        timeout = 60.0
    timeout = min(max(timeout, 5.0), 30.0)

    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)
        import google.generativeai as genai

    genai.configure(api_key=key)
    model = genai.GenerativeModel(model_id)
    prompt = 'Reply with exactly the two letters OK and nothing else.'
    try:
        try:
            response = model.generate_content(
                prompt,
                request_options={"timeout": timeout},
            )
        except TypeError:
            response = model.generate_content(prompt)
        text = _response_text(response)
        if not text:
            return {
                "ok": False,
                "model": model_id,
                "error": "Empty response from model (check API key, model id, quota).",
                "preview": None,
                **_paths_meta(),
            }
        return {
            "ok": True,
            "model": model_id,
            "error": None,
            "preview": text[:200],
            **_paths_meta(),
        }
    except Exception as e:
        msg = str(e).strip() or type(e).__name__
        return {
            "ok": False,
            "model": model_id,
            "error": msg[:500],
            "preview": None,
            **_paths_meta(),
        }


def main() -> None:
    load_dashboard_env()
    print(json.dumps(run_gemini_smoke_test(), indent=2))


if __name__ == "__main__":
    main()
