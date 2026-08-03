from datetime import datetime, timezone

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
