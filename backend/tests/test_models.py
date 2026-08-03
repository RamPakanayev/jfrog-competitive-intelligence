from sqlalchemy import text

from app.models import Article, Digest


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
