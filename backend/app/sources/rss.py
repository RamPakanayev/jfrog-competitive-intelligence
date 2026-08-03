import html
import re
from datetime import UTC, datetime
from urllib.parse import urlencode

import feedparser
import httpx

from app.sources.base import USER_AGENT, RawItem

_TAG_RE = re.compile(r"<[^>]+>")

GOOGLE_NEWS_SEARCH = "https://news.google.com/rss/search"


def google_news_url(query: str) -> str:
    """Build a Google News RSS search URL.

    This is how we get third-party coverage of a competitor rather than only what the
    competitor publishes about itself. It needs no API key and is plain RSS, so the
    adapter below reads it unchanged.
    """
    params = urlencode({"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"})
    return f"{GOOGLE_NEWS_SEARCH}?{params}"


def strip_html(s: str) -> str:
    return " ".join(html.unescape(_TAG_RE.sub(" ", s or "")).split())


def _entry_date(e) -> datetime | None:
    t = e.get("published_parsed") or e.get("updated_parsed")
    return datetime(*t[:6], tzinfo=UTC) if t else None


async def fetch_rss(client: httpx.AsyncClient, name: str, url: str,
                    window_start: datetime, max_items: int | None = None) -> list[RawItem]:
    r = await client.get(url, timeout=20, headers=USER_AGENT, follow_redirects=True)
    r.raise_for_status()
    feed = feedparser.parse(r.content)
    if feed.bozo and not any(feed.entries):
        raise ValueError(f"unparseable feed from {url}: {feed.bozo_exception}")
    items: list[RawItem] = []
    for e in feed.entries:
        published = _entry_date(e)
        if published and published < window_start:
            continue
        items.append(RawItem(
            title=(e.get("title") or "").strip(),
            url=e.get("link") or "",
            body_excerpt=strip_html(e.get("summary", ""))[:1000],
            source_name=name, source_type="rss", published_at=published))
        # News search feeds return ~100 entries; a vendor blog returns a handful. Cap the
        # noisy ones so a single busy search term can't dominate a run's enrichment budget.
        if max_items is not None and len(items) >= max_items:
            break
    return items
