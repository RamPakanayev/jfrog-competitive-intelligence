import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from app.sources.hackernews import fetch_hackernews
from app.sources.reddit import fetch_reddit
from app.sources.rss import fetch_rss
from app.sources.tavily import fetch_tavily

FIX = Path(__file__).parent / "fixtures"
WINDOW = datetime(2026, 8, 1, tzinfo=UTC)


def client_returning(content: bytes, content_type: str) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=content, headers={"content-type": content_type})
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_rss_parses_strips_html_and_windows():
    client = client_returning((FIX / "rss_sample.xml").read_bytes(), "application/rss+xml")
    items = await fetch_rss(client, "Sonatype Blog", "https://vendor.example/rss", WINDOW)
    assert len(items) == 1  # old post filtered by window
    it = items[0]
    assert it.title == "Nexus Repository 3.99 adds SBOM export"
    assert "<" not in it.body_excerpt and "SBOM export" in it.body_excerpt
    assert it.source_type == "rss" and it.published_at.year == 2026


async def test_hackernews_uses_hn_permalink_when_no_url():
    client = client_returning((FIX / "hn_sample.json").read_bytes(), "application/json")
    items = await fetch_hackernews(client, "snyk", WINDOW)
    assert len(items) == 2
    assert items[0].url == "https://news.example/snyk-layoffs"
    assert items[1].url == "https://news.ycombinator.com/item?id=41002"
    assert all(i.source_type == "hackernews" for i in items)


async def test_reddit_builds_permalink():
    client = client_returning((FIX / "reddit_sample.json").read_bytes(), "application/json")
    items = await fetch_reddit(client, ["devops"], "gitlab", WINDOW)
    assert items[0].url == "https://www.reddit.com/r/devops/comments/x1/glab"
    assert items[0].source_name == "Reddit r/devops"


async def test_tavily_posts_key_and_parses():
    captured = {}
    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(200, json={"results": [
            {"title": "Docker updates pricing", "url": "https://t.example/d",
             "content": "Docker changed Hub pricing tiers.", "published_date": "2026-08-02"}]})
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    items = await fetch_tavily(client, "key123", "Docker Hub news", WINDOW)
    assert captured["api_key"] == "key123" and captured["topic"] == "news"
    assert items[0].source_type == "tavily" and items[0].title.startswith("Docker")


async def test_adapter_error_propagates():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        await fetch_rss(client, "X", "https://x.example/rss", WINDOW)
        raised = False
    except httpx.HTTPStatusError:
        raised = True
    assert raised  # orchestrator is responsible for isolation


async def test_rss_raises_on_unparseable_feed():
    client = client_returning(b"<rss><channel><item><title>trunc", "application/rss+xml")
    with pytest.raises(ValueError, match="unparseable feed"):
        await fetch_rss(client, "Broken", "https://broken.example/rss", WINDOW)


async def test_rss_tolerates_bozo_feed_that_still_parses():
    # Unescaped ampersand: feedparser sets bozo=1 but still yields the entry.
    body = (b'<?xml version="1.0"?><rss version="2.0"><channel><title>T</title><item>'
            b'<title>Docker & friends ship registry</title>'
            b'<link>https://vendor.example/amp</link><description>d</description>'
            b'<pubDate>Mon, 03 Aug 2026 08:00:00 GMT</pubDate></item></channel></rss>')
    client = client_returning(body, "application/rss+xml")
    items = await fetch_rss(client, "Amp", "https://vendor.example/rss", WINDOW)
    assert len(items) == 1


async def test_reddit_skips_items_without_permalink():
    payload = json.dumps({"data": {"children": [
        {"data": {"title": "No permalink", "selftext": "x",
                  "created_utc": 1785744000, "over_18": False}},
        {"data": {"title": "Has permalink", "permalink": "/r/devops/comments/x2/ok/",
                  "selftext": "y", "created_utc": 1785744000, "over_18": False}},
    ]}}).encode()
    client = client_returning(payload, "application/json")
    items = await fetch_reddit(client, ["devops"], "q", WINDOW)
    assert [i.title for i in items] == ["Has permalink"]


async def test_tavily_converts_offset_dates_instead_of_relabelling():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"results": [
            {"title": "Offset date", "url": "https://t.example/o", "content": "c",
             "published_date": "2026-08-02T10:00:00+02:00"}]})
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    items = await fetch_tavily(client, "k", "q", WINDOW)
    assert items[0].published_at == datetime(2026, 8, 2, 8, 0, tzinfo=UTC)


async def test_reddit_time_filter_follows_the_window():
    captured = {}
    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(dict(request.url.params))
        return httpx.Response(200, json={"data": {"children": []}})
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    await fetch_reddit(client, ["devops"], "q", datetime.now(UTC) - timedelta(days=30))
    assert captured["t"] == "month"


async def test_hackernews_skips_malformed_hits_without_losing_the_batch():
    payload = json.dumps({"hits": [
        {"title": "Good", "url": "https://n.example/g", "objectID": "1",
         "created_at_i": 1785744000},
        {"title": "No timestamp", "url": "https://n.example/b", "objectID": "2"},
        {"title": "Self post, no id", "url": None, "created_at_i": 1785744000},
    ]}).encode()
    client = client_returning(payload, "application/json")
    items = await fetch_hackernews(client, "q", WINDOW)
    assert [i.title for i in items] == ["Good"]
