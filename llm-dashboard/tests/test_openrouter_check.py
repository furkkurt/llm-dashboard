from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend import main
from backend.openrouter_check import run_openrouter_smoke_test


def test_run_openrouter_smoke_test_no_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("backend.openrouter_check.load_dashboard_env", lambda: True)
    monkeypatch.setattr("backend.openrouter_check.openrouter_api_key_line_state", lambda: "missing")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    out = run_openrouter_smoke_test()
    assert out["ok"] is False
    assert out["model"] is None
    assert "not set" in (out.get("error") or "").lower()
    assert out.get("env_file")
    assert isinstance(out.get("env_file_present"), bool)


@patch("backend.openrouter_check.openrouter_chat_completion")
def test_run_openrouter_smoke_test_success(
    mock_chat: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("backend.openrouter_check.load_dashboard_env", lambda: True)
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    monkeypatch.setenv("OPENROUTER_MODEL", "google/gemini-2.0-flash-001")
    mock_chat.return_value = ("OK", "google/gemini-2.0-flash-001")
    out = run_openrouter_smoke_test()
    assert out["ok"] is True
    assert out["error"] is None
    assert out["preview"] == "OK"


def test_health_commentary_endpoint_patched(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        main,
        "run_openrouter_smoke_test",
        lambda: {
            "ok": True,
            "model": "openrouter-test",
            "error": None,
            "preview": "OK",
            "env_file": "/x/.env",
            "env_file_present": True,
            "local_env_file": "/x/local.env",
            "local_env_present": False,
        },
    )
    client = TestClient(main.app)
    r = client.get("/health/commentary")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["model"] == "openrouter-test"


def test_health_gemini_legacy_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        main,
        "run_openrouter_smoke_test",
        lambda: {
            "ok": True,
            "model": "m",
            "error": None,
            "preview": "OK",
            "env_file": "/x/.env",
            "env_file_present": True,
            "local_env_file": "/x/local.env",
            "local_env_present": False,
        },
    )
    client = TestClient(main.app)
    r = client.get("/health/gemini")
    assert r.status_code == 200
    assert r.json()["ok"] is True
