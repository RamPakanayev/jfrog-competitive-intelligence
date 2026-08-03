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


def test_config_dir_is_path():
    s = Settings(_env_file=None)
    assert isinstance(s.config_dir, Path)


def test_api_keys_are_masked_in_repr(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-super-secret-value")
    s = Settings(_env_file=None)
    assert s.anthropic_api_key.get_secret_value() == "sk-super-secret-value"
    assert "sk-super-secret-value" not in repr(s)
    assert "sk-super-secret-value" not in str(s.anthropic_api_key)
