from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend import main
from backend.gemini_check import run_gemini_smoke_test


def test_run_gemini_smoke_test_no_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("backend.gemini_check.load_dashboard_env", lambda: True)
    monkeypatch.setattr("backend.gemini_check.google_api_key_line_state", lambda: "missing")
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    out = run_gemini_smoke_test()
    assert out["ok"] is False
    assert out["model"] is None
    assert "not set" in (out.get("error") or "").lower()
    assert out.get("env_file")
    assert isinstance(out.get("env_file_present"), bool)


@patch("google.generativeai.GenerativeModel")
@patch("google.generativeai.configure")
def test_run_gemini_smoke_test_success(
    _mock_configure: MagicMock,
    mock_model_cls: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("backend.gemini_check.load_dashboard_env", lambda: True)
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    monkeypatch.setenv("GOOGLE_MODEL", "gemini-2.0-flash")
    inst = MagicMock()
    inst.generate_content.return_value = MagicMock(text="OK")
    mock_model_cls.return_value = inst
    out = run_gemini_smoke_test()
    assert out["ok"] is True
    assert out["model"] == "gemini-2.0-flash"
    assert out["error"] is None
    assert out["preview"] == "OK"


def test_health_gemini_endpoint_patched(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        main,
        "run_gemini_smoke_test",
        lambda: {
            "ok": True,
            "model": "gemini-test",
            "error": None,
            "preview": "OK",
        },
    )
    client = TestClient(main.app)
    r = client.get("/health/gemini")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["model"] == "gemini-test"
