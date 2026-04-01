"""Smoke test for OpenRouter (same stack as AI commentary)."""

from __future__ import annotations

import json
import os
from typing import Any

from backend.env_bootstrap import (
    dashboard_dotenv_path,
    local_dashboard_env_path,
    load_dashboard_env,
    openrouter_api_key_line_state,
)
from backend.openrouter_client import openrouter_chat_completion


def run_openrouter_smoke_test() -> dict[str, Any]:
    """
    One cheap chat completion. Dict matches CommentaryHealthResponse.

    Uses OPENROUTER_API_KEY, OPENROUTER_MODEL, COMMENTARY_TIMEOUT_SEC (capped at 30s).
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

    key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not key:
        line_state = openrouter_api_key_line_state()
        err = "OPENROUTER_API_KEY not set or empty."
        if not dotenv_present and not local_present:
            err += (
                f" Create `{env_path.name}` or `{local_path.name}` next to `backend/` "
                f"(see `local.env.example`). `setup.sh` does not create either file."
            )
        elif line_state == "empty":
            err += (
                " On disk, OPENROUTER_API_KEY= has no value after '=' in `.env` and/or `local.env`. "
                "Save the file. Prefer putting secrets only in `local.env`."
            )
        elif line_state == "missing":
            err += f" Add OPENROUTER_API_KEY=... to `{local_path.name}` (recommended) or `{env_path.name}`."
        else:
            err += (
                " Check OPENROUTER_API_KEY= in `.env` / `local.env`: no spaces around '='; "
                "no second empty OPENROUTER_API_KEY= line after a good one."
            )
        return {
            "ok": False,
            "model": None,
            "error": err,
            "preview": None,
            **_paths_meta(),
        }

    model_id = os.getenv("OPENROUTER_MODEL", "google/gemini-2.0-flash-001").strip()
    try:
        timeout = float(os.getenv("COMMENTARY_TIMEOUT_SEC", "60"))
    except ValueError:
        timeout = 60.0
    timeout = min(max(timeout, 5.0), 30.0)

    try:
        text, used = openrouter_chat_completion(
            messages=[
                {
                    "role": "user",
                    "content": "Reply with exactly the two letters OK and nothing else.",
                }
            ],
            model=model_id,
            timeout=timeout,
            max_tokens=32,
            temperature=0,
        )
        if not text:
            return {
                "ok": False,
                "model": used,
                "error": "Empty response from model (check API key, model id, credits).",
                "preview": None,
                **_paths_meta(),
            }
        return {
            "ok": True,
            "model": used,
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
    print(json.dumps(run_openrouter_smoke_test(), indent=2))


if __name__ == "__main__":
    main()
