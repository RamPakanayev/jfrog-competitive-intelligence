from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from app.models import Article, Digest
from tests.conftest import make_article


def test_tables_created(session):
    session.add(Article(url="https://x.com/a", content_hash="h1", title="Hello Nexus",
                        source_name="t", source_type="rss"))
    session.commit()
    assert session.query(Article).count() == 1


def test_fts_syncs_on_insert_update(session):
    a = Article(url="https://x.com/b", content_hash="h2", title="GitLab ships scanner",
                source_name="t", source_type="rss")
    session.add(a)
    session.commit()
    hits = session.execute(text(
        "SELECT rowid FROM articles_fts WHERE articles_fts MATCH 'gitlab'")).fetchall()
    assert hits and hits[0][0] == a.id

    a.summary = "A brand new SAST engine"
    session.commit()
    hits = session.execute(text(
        "SELECT rowid FROM articles_fts WHERE articles_fts MATCH 'sast'")).fetchall()
    assert hits and hits[0][0] == a.id


def test_digest_unique_date(session):
    session.add(Digest(date="2026-08-03", exec_summary="s", sections={}, model_used="m"))
    session.commit()
    assert session.query(Digest).filter_by(date="2026-08-03").one().exec_summary == "s"


def test_datetimes_round_trip_timezone_aware(session_factory):
    with session_factory() as s:
        a = Article(url="https://x.com/tz", content_hash="tz", title="tz check",
                    source_name="t", source_type="rss")
        s.add(a)
        s.commit()
        article_id = a.id

    with session_factory() as fresh:          # fresh session: forces a real DB read
        loaded = fresh.get(Article, article_id)
        assert loaded.fetched_at.tzinfo is not None
        assert loaded.fetched_at.utcoffset() == timedelta(0)
        # the comparison that would raise TypeError with naive datetimes
        assert loaded.fetched_at <= datetime.now(timezone.utc)
        assert loaded.fetched_at.isoformat().endswith("+00:00")


def test_json_columns_track_in_place_mutation(session_factory):
    with session_factory() as s:
        a = Article(url="https://x.com/json", content_hash="json", title="json check",
                    source_name="t", source_type="rss", competitors=["snyk"])
        s.add(a)
        s.commit()
        article_id = a.id

    with session_factory() as s:
        # Bind the loaded object to a name: SQLAlchemy's identity map holds only a
        # weak reference, so a chained `s.get(...).competitors.append(...)` lets
        # CPython refcount the Article to zero and garbage-collect it immediately
        # after the statement -- before commit() -- silently dropping the queued
        # mutation even though MutableList itself is tracking it correctly.
        loaded = s.get(Article, article_id)
        loaded.competitors.append("gitlab")
        s.commit()

    with session_factory() as fresh:
        assert fresh.get(Article, article_id).competitors == ["snyk", "gitlab"]


def test_make_article_allows_content_hash_override(session):
    a = make_article(session, url="https://x.com/dup", title="dup", content_hash="shared")
    assert a.content_hash == "shared"
