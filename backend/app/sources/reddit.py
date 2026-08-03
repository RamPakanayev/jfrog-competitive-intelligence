from datetime import datetime, timezone

import httpx

from app.sources.base import USER_AGENT, RawItem


async def fetch_reddit(client: httpx.AsyncClient, subreddits: list[str], query: str,
                       window_start: datetime) -> list[RawItem]:
    items: list[RawItem] = []
    for sub in subreddits:
        url = f"https://www.reddit.com/r/{sub}/search.json"
        params = {"q": query, "sort": "new", "t": "week", "limit": 25, "restrict_sr": 1}
        r = await client.get(url, params=params, timeout=20, headers=USER_AGENT)
        r.raise_for_status()
        for child in r.json().get("data", {}).get("children", []):
            d = child.get("data", {})
            if d.get("over_18"):
                continue
            permalink = (d.get("permalink") or "").rstrip("/")
            if not permalink:
                continue
            published = datetime.fromtimestamp(d.get("created_utc", 0), tz=timezone.utc)
            if published < window_start:
                continue
            items.append(RawItem(
                title=(d.get("title") or "").strip(),
                url=f"https://www.reddit.com{permalink}",
                body_excerpt=(d.get("selftext") or "")[:1000],
                source_name=f"Reddit r/{sub}", source_type="reddit", published_at=published))
    return items
