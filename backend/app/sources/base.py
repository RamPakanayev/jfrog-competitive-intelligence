from datetime import datetime

from pydantic import BaseModel

USER_AGENT = {"User-Agent": "RibbitCI/0.1 (competitive-intel demo; contact: repo README)"}


class RawItem(BaseModel):
    title: str
    url: str
    body_excerpt: str = ""
    source_name: str
    source_type: str  # rss | hackernews | reddit | tavily
    published_at: datetime | None = None
