from datetime import datetime, timezone

from sqlalchemy import JSON, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Article(Base):
    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(primary_key=True)
    url: Mapped[str] = mapped_column(unique=True, index=True)
    content_hash: Mapped[str] = mapped_column(unique=True, index=True)
    title: Mapped[str]
    body_excerpt: Mapped[str] = mapped_column(Text, default="")
    source_name: Mapped[str]
    source_type: Mapped[str]  # rss | hackernews | reddit | tavily | demo
    published_at: Mapped[datetime | None]
    fetched_at: Mapped[datetime] = mapped_column(default=utcnow)
    status: Mapped[str] = mapped_column(default="new", index=True)  # new|enriched|irrelevant|failed
    # enrichment
    relevant: Mapped[bool | None]
    competitors: Mapped[list | None] = mapped_column(JSON)
    domain: Mapped[str | None]
    event_type: Mapped[str | None]
    summary: Mapped[str | None] = mapped_column(Text)
    jfrog_impact: Mapped[int | None]
    so_what: Mapped[str | None] = mapped_column(Text)
    enriched_at: Mapped[datetime | None]
    # delta (only when jfrog_impact >= 4)
    delta_move: Mapped[str | None] = mapped_column(Text)
    delta_jfrog_equivalent: Mapped[str | None] = mapped_column(Text)
    delta_strategic_impact: Mapped[str | None]  # high|medium|low
    delta_talking_points: Mapped[list | None] = mapped_column(JSON)


class Digest(Base):
    __tablename__ = "digests"

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[str] = mapped_column(unique=True, index=True)  # YYYY-MM-DD
    exec_summary: Mapped[str] = mapped_column(Text)
    sections: Mapped[dict] = mapped_column(JSON)
    generated_at: Mapped[datetime] = mapped_column(default=utcnow)
    model_used: Mapped[str] = mapped_column(default="")


class Battlecard(Base):
    __tablename__ = "battlecards"

    id: Mapped[int] = mapped_column(primary_key=True)
    competitor_slug: Mapped[str] = mapped_column(unique=True, index=True)
    recent_moves: Mapped[list] = mapped_column(JSON, default=list)
    generated_at: Mapped[datetime] = mapped_column(default=utcnow)


class SourceRun(Base):
    __tablename__ = "source_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[str] = mapped_column(index=True)
    source_name: Mapped[str]
    started_at: Mapped[datetime] = mapped_column(default=utcnow)
    ok: Mapped[bool] = mapped_column(default=True)
    items_found: Mapped[int] = mapped_column(default=0)
    error: Mapped[str | None] = mapped_column(Text)


FTS_STATEMENTS = [
    """CREATE VIRTUAL TABLE IF NOT EXISTS articles_fts USING fts5(
        title, body_excerpt, summary, content='articles', content_rowid='id')""",
    """CREATE TRIGGER IF NOT EXISTS articles_ai AFTER INSERT ON articles BEGIN
        INSERT INTO articles_fts(rowid, title, body_excerpt, summary)
        VALUES (new.id, new.title, coalesce(new.body_excerpt,''), coalesce(new.summary,''));
    END""",
    """CREATE TRIGGER IF NOT EXISTS articles_au AFTER UPDATE ON articles BEGIN
        INSERT INTO articles_fts(articles_fts, rowid, title, body_excerpt, summary)
        VALUES('delete', old.id, old.title, coalesce(old.body_excerpt,''), coalesce(old.summary,''));
        INSERT INTO articles_fts(rowid, title, body_excerpt, summary)
        VALUES (new.id, new.title, coalesce(new.body_excerpt,''), coalesce(new.summary,''));
    END""",
    """CREATE TRIGGER IF NOT EXISTS articles_ad AFTER DELETE ON articles BEGIN
        INSERT INTO articles_fts(articles_fts, rowid, title, body_excerpt, summary)
        VALUES('delete', old.id, old.title, coalesce(old.body_excerpt,''), coalesce(old.summary,''));
    END""",
]


def init_db(engine) -> None:
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        for stmt in FTS_STATEMENTS:
            conn.exec_driver_sql(stmt)
