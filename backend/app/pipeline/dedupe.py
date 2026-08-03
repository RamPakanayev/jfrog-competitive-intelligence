import hashlib
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Article
from app.sources.base import RawItem

# Attribution/tracking params that never select different content on the sources we read
# (vendor blogs, HN, Reddit, news search). Revisit if a catalog-style source is added,
# where ?ref=/?source= can genuinely address different pages.
_DROP_PARAMS = {"fbclid", "gclid", "ref", "mc_cid", "mc_eid", "source"}


def canonical_url(url: str) -> str:
    p = urlsplit(url.strip())
    query = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
             if not k.lower().startswith("utm_") and k.lower() not in _DROP_PARAMS]
    path = p.path.rstrip("/") if p.path not in ("", "/") else "/"
    return urlunsplit((p.scheme.lower() or "https", p.netloc.lower(), path,
                       urlencode(query), ""))


def content_hash(title: str, excerpt: str) -> str:
    basis = f"{title.strip().lower()}|{excerpt.strip().lower()[:500]}"
    return hashlib.sha256(basis.encode()).hexdigest()


def insert_new_items(session: Session, items: list[RawItem]) -> int:
    inserted = 0
    seen_urls: set[str] = set()
    seen_hashes: set[str] = set()
    for it in items:
        if not it.url or not it.title:
            continue
        url = canonical_url(it.url)
        h = content_hash(it.title, it.body_excerpt)
        if url in seen_urls or h in seen_hashes:
            continue
        exists = session.scalar(select(Article.id).where(
            (Article.url == url) | (Article.content_hash == h)))
        if exists:
            continue
        session.add(Article(url=url, content_hash=h, title=it.title.strip(),
                            body_excerpt=it.body_excerpt, source_name=it.source_name,
                            source_type=it.source_type, published_at=it.published_at))
        try:
            session.commit()
        except IntegrityError:
            # Another writer inserted this item between our check and our commit.
            # Skipping one duplicate is correct; losing the rest of the batch is not.
            session.rollback()
            continue
        seen_urls.add(url)
        seen_hashes.add(h)
        inserted += 1
    return inserted
