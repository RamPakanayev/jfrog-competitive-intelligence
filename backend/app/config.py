from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    llm_provider: str = "anthropic"  # anthropic | openai | gemini | ollama
    llm_model: str = "claude-haiku-4-5"
    ollama_model: str = "llama3.1:8b"
    anthropic_api_key: SecretStr = SecretStr("")
    openai_api_key: SecretStr = SecretStr("")
    gemini_api_key: SecretStr = SecretStr("")
    ollama_base_url: str = "http://localhost:11434"
    llm_fallback_provider: str = ""  # empty = no fallback
    tavily_api_key: SecretStr = SecretStr("")
    refresh_hour: int = 7
    demo_mode: str = "auto"  # auto | on | off
    enable_scheduler: bool = True
    database_url: str = f"sqlite:///{REPO_ROOT / 'data' / 'ribbit.db'}"
    config_dir: Path = REPO_ROOT / "config"
    demo_seed_path: Path = REPO_ROOT / "data" / "demo" / "seed.json"
    fetch_window_days: int = 2
