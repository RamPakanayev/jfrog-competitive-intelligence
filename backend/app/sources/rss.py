import html
import re
from datetime import datetime, timezone

import feedparser
import httpx

from app.sources.base import USER_AGENT, RawItem

_TAG_RE = re.compile(r"<[^>]+>")


def strip_html(s: str) -> str:
    return " ".join(html.unescape(_TAG_RE.sub(" ", s or "")).split())


def _entry_date(e) -> datetime | None:
    t = e.get("published_parsed") or e.get("updated_parsed")
    return datetime(*t[:6], tzinfo=timezone.utc) if t else None


async def fetch_rss(client: httpx.AsyncClient, name: str, url: str,
                    window_start: datetime) -> list[RawItem]:
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
    return items
