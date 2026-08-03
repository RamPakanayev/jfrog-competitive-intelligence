from datetime import datetime, timezone

import httpx

from app.sources.base import USER_AGENT, RawItem

API = "https://hn.algolia.com/api/v1/search_by_date"


async def fetch_hackernews(client: httpx.AsyncClient, query: str,
                           window_start: datetime) -> list[RawItem]:
    params = {"query": query, "tags": "story",
              "numericFilters": f"created_at_i>{int(window_start.timestamp())}",
              "hitsPerPage": 30}
    r = await client.get(API, params=params, timeout=20, headers=USER_AGENT)
    r.raise_for_status()
    items = []
    for h in r.json().get("hits", []):
        created = h.get("created_at_i")
        object_id = h.get("objectID")
        if created is None or not (h.get("url") or object_id):
            continue
        url = h.get("url") or f"https://news.ycombinator.com/item?id={object_id}"
        items.append(RawItem(
            title=(h.get("title") or "").strip(), url=url,
            body_excerpt="", source_name="Hacker News", source_type="hackernews",
            published_at=datetime.fromtimestamp(created, tz=timezone.utc)))
    return items
