from datetime import datetime, timezone

import httpx

from app.sources.base import RawItem

API = "https://api.tavily.com/search"


async def fetch_tavily(client: httpx.AsyncClient, api_key: str, query: str,
                       window_start: datetime) -> list[RawItem]:
    days = max(1, (datetime.now(timezone.utc) - window_start).days)
    r = await client.post(API, json={"api_key": api_key, "query": query, "topic": "news",
                                     "days": days, "max_results": 10}, timeout=30)
    r.raise_for_status()
    items = []
    for res in r.json().get("results", []):
        published = None
        if res.get("published_date"):
            try:
                published = datetime.fromisoformat(res["published_date"]).replace(tzinfo=timezone.utc)
            except ValueError:
                pass
        items.append(RawItem(title=(res.get("title") or "").strip(), url=res.get("url") or "",
                             body_excerpt=(res.get("content") or "")[:1000],
                             source_name="Tavily News", source_type="tavily",
                             published_at=published))
    return items
