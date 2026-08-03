from datetime import datetime, timezone

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import Article
from app.pipeline.dedupe import canonical_url, content_hash, insert_new_items
from app.sources.base import RawItem


def item(url: str, title: str = "Snyk raises prices") -> RawItem:
    return RawItem(title=title, url=url, body_excerpt="body", source_name="Feed",
                   source_type="rss", published_at=datetime(2026, 8, 3, tzinfo=timezone.utc))


def test_canonical_url_strips_tracking_and_normalizes():
    u = "HTTPS://Snyk.io/Blog/Post/?utm_source=x&utm_medium=y&fbclid=z&keep=1#frag"
    assert canonical_url(u) == "https://snyk.io/Blog/Post?keep=1"


def test_content_hash_stable_and_case_insensitive():
    assert content_hash("Title A", "body") == content_hash("  title a ", "body")
    assert content_hash("Title A", "body") != content_hash("Title B", "body")


def test_insert_new_items_dedupes(session):
    items = [
        item("https://snyk.io/blog/p1?utm_source=rss"),
        item("https://snyk.io/blog/p1"),                      # same after canonicalization
        item("https://other.com/mirror", title="Snyk raises prices"),  # identical title+excerpt
    ]
    inserted = insert_new_items(session, items)
    # p1 dedupes to one; mirror has identical title+excerpt -> identical hash -> also deduped
    assert inserted == 1
    inserted_again = insert_new_items(session, items)
    assert inserted_again == 0


def test_failed_commit_does_not_abort_remaining_items(session, monkeypatch):
    """A lost race (IntegrityError on commit) must cost one item, not the batch."""
    first = item("https://snyk.io/blog/one", title="First story")
    second = item("https://snyk.io/blog/two", title="Second story")

    real_commit = session.commit
    calls = {"n": 0}

    def flaky_commit():
        calls["n"] += 1
        if calls["n"] == 1:                      # simulate another writer winning
            raise IntegrityError("INSERT INTO articles", {}, Exception("UNIQUE constraint failed"))
        return real_commit()

    monkeypatch.setattr(session, "commit", flaky_commit)
    inserted = insert_new_items(session, [first, second])
    monkeypatch.undo()

    assert inserted == 1
    assert {a.title for a in session.scalars(select(Article))} == {"Second story"}


def test_blank_and_whitespace_items_are_skipped(session):
    items = [
        item("https://snyk.io/blog/ok", title="Real story"),
        item("https://snyk.io/blog/blank", title="   "),
        item("   ", title="Missing url"),
        item("\t\n ", title="Also missing url"),
    ]
    assert insert_new_items(session, items) == 1
    assert {a.title for a in session.scalars(select(Article))} == {"Real story"}


def test_raw_item_rejects_unknown_source_type():
    with pytest.raises(ValidationError):
        RawItem(title="t", url="https://x.example/1", source_name="s", source_type="carrier-pigeon")
