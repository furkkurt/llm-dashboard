import pytest

from backend.env_bootstrap import openrouter_api_key_line_state


def test_openrouter_api_key_line_state_empty(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = tmp_path / ".env"
    env.write_text("FOO=1\nOPENROUTER_API_KEY=\n", encoding="utf-8")
    monkeypatch.setattr("backend.env_bootstrap.DASHBOARD_ROOT", tmp_path)
    assert openrouter_api_key_line_state() == "empty"


def test_openrouter_api_key_line_state_set(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = tmp_path / ".env"
    env.write_text("OPENROUTER_API_KEY=secret-value\n", encoding="utf-8")
    monkeypatch.setattr("backend.env_bootstrap.DASHBOARD_ROOT", tmp_path)
    assert openrouter_api_key_line_state() == "set"


def test_openrouter_api_key_line_last_wins_empty(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = tmp_path / ".env"
    env.write_text("OPENROUTER_API_KEY=first\nOPENROUTER_API_KEY=\n", encoding="utf-8")
    monkeypatch.setattr("backend.env_bootstrap.DASHBOARD_ROOT", tmp_path)
    assert openrouter_api_key_line_state() == "empty"


def test_openrouter_api_key_local_env_overrides(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / ".env").write_text("OPENROUTER_API_KEY=\n", encoding="utf-8")
    (tmp_path / "local.env").write_text("OPENROUTER_API_KEY=from-local\n", encoding="utf-8")
    monkeypatch.setattr("backend.env_bootstrap.DASHBOARD_ROOT", tmp_path)
    assert openrouter_api_key_line_state() == "set"
