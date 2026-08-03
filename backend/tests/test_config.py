from pathlib import Path

from app.config import Settings


def test_defaults_load_without_env():
    s = Settings(_env_file=None)
    assert s.llm_provider == "anthropic"
    assert s.demo_mode == "auto"
    assert s.refresh_hour == 7
    assert s.database_url.startswith("sqlite:///")
    assert s.config_dir.name == "config"


def test_env_overrides(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("REFRESH_HOUR", "5")
    s = Settings(_env_file=None)
    assert s.llm_provider == "ollama"
    assert s.refresh_hour == 5


def test_config_dir_exists():
    s = Settings(_env_file=None)
    assert isinstance(s.config_dir, Path)
