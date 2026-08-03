from datetime import datetime
from typing import Literal

from pydantic import BaseModel

USER_AGENT = {"User-Agent": "RibbitCI/0.1 (competitive-intel demo; contact: repo README)"}


class RawItem(BaseModel):
    title: str
    url: str
    body_excerpt: str = ""
    source_name: str
    source_type: Literal["rss", "hackernews", "reddit", "tavily"]
    published_at: datetime | None = None
