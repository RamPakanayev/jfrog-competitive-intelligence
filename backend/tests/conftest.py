from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models import Article, init_db


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
                published_at=kw.pop("published_at", datetime(2026, 8, 3, 9, tzinfo=timezone.utc)),
                status=status, **kw)
    session.add(a)
    session.commit()
    return a


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
