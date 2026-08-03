from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.models import Article, init_db

_SECRET_ENV_VARS = ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY", "TAVILY_API_KEY")


@pytest.fixture(autouse=True)
def _isolate_settings_from_real_credentials(monkeypatch):
    """Keep the suite from ever seeing a developer's real API keys.

    `Settings(_env_file=None)` does NOT reliably disable dotenv loading, so tests were
    picking up the real key from the repo-root `.env`. That made results depend on whether
    a developer happened to have credentials configured, and put the suite one careless
    line away from issuing live, billed API calls.
    """
    monkeypatch.setattr(Settings, "model_config", {**Settings.model_config, "env_file": None})
    for var in _SECRET_ENV_VARS:
        monkeypatch.delenv(var, raising=False)


@pytest.fixture()
def engine(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path}/test.db")
    init_db(eng)
    return eng


@pytest.fixture()
def session_factory(engine):
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture()
def session(session_factory):
    with session_factory() as s:
        yield s


def make_article(session: Session, *, url: str, title: str, status: str = "new", **kw) -> Article:
    a = Article(url=url, content_hash=kw.pop("content_hash", f"hash-{url}"), title=title,
                source_name=kw.pop("source_name", "Test Feed"),
                source_type=kw.pop("source_type", "rss"),
                published_at=kw.pop("published_at", datetime(2026, 8, 3, 9, tzinfo=UTC)),
                status=status, **kw)
    session.add(a)
    session.commit()
    return a


@pytest.fixture(autouse=True)
def _reset_refresh_state():
    from app.pipeline.run import REFRESH_STATE
    REFRESH_STATE.update(running=False, stage="idle", counts={}, errors=[],
                         started_at=None, finished_at=None)
    yield


class FakeGateway:
    """Queue of canned responses; records every call. None = simulated LLM failure."""

    def __init__(self, responses: list | None = None):
        self.responses = list(responses or [])
        self.calls: list[tuple[str, str, str]] = []  # (schema_name, system, user)

    def complete_json(self, system: str, user: str, schema, temperature: float = 0.2):
        self.calls.append((schema.__name__, system, user))
        return self.responses.pop(0) if self.responses else None

    def available(self) -> bool:
        return True
