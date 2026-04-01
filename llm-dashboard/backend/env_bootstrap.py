"""Resolve and load dashboard env files regardless of process cwd."""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

# This file lives in backend/; dashboard root is one level up.
DASHBOARD_ROOT = Path(__file__).resolve().parent.parent


def dashboard_dotenv_path() -> Path:
    return DASHBOARD_ROOT / ".env"


def local_dashboard_env_path() -> Path:
    """Optional second file: gitignored, not referenced by setup.sh — put API keys here."""
    return DASHBOARD_ROOT / "local.env"


def load_dashboard_env() -> bool:
    """
    Load `.env` then `local.env` (each override=True, second file wins on duplicate keys).
    Neither file is read or written by setup.sh.
    """
    p = dashboard_dotenv_path()
    l = local_dashboard_env_path()
    a = load_dotenv(p, override=True, encoding="utf-8-sig")
    b = load_dotenv(l, override=True, encoding="utf-8-sig") if l.is_file() else False
    return a or b


def _merged_env_text() -> str:
    chunks: list[str] = []
    for path in (dashboard_dotenv_path(), local_dashboard_env_path()):
        if not path.is_file():
            continue
        try:
            chunks.append(path.read_text(encoding="utf-8-sig"))
        except OSError:
            pass
    return "\n".join(chunks)


def openrouter_api_key_line_state() -> str:
    """
    Inspect `.env` + `local.env` for OPENROUTER_API_KEY= ... 'set' | 'empty' | 'missing' | 'unreadable'.
    Last assignment wins across both files (same order as load_dashboard_env).
    Does not return the secret.
    """
    text = _merged_env_text()
    if not text.strip():
        for path in (dashboard_dotenv_path(), local_dashboard_env_path()):
            if path.is_file():
                try:
                    path.read_text(encoding="utf-8-sig")
                except OSError:
                    return "unreadable"
        return "missing"

    last_nonempty = False
    last_was_empty = False
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if line.startswith("OPENROUTER_API_KEY="):
            val = line.split("=", 1)[1].strip().strip('"').strip("'")
            if val:
                last_nonempty = True
                last_was_empty = False
            else:
                last_was_empty = True
                last_nonempty = False
    if last_nonempty:
        return "set"
    if last_was_empty:
        return "empty"
    return "missing"
