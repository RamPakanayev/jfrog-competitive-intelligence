from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select, text
from sqlalchemy.exc import OperationalError

from app.api.deps import get_appcfg, get_session_factory, get_settings
from app.models import Article, Battlecard, Digest, SourceRun
from app.pipeline.run import REFRESH_STATE

router = APIRouter(prefix="/api")


def _article_dict(a: Article) -> dict:
    d = {"id": a.id, "title": a.title, "url": a.url, "source_name": a.source_name,
         "source_type": a.source_type,
         "published_at": a.published_at.isoformat() if a.published_at else None,
         "fetched_at": a.fetched_at.isoformat() if a.fetched_at else None,
         "competitors": a.competitors or [], "domain": a.domain, "event_type": a.event_type,
         "summary": a.summary, "jfrog_impact": a.jfrog_impact, "so_what": a.so_what,
         "delta": None}
    if a.delta_move:
        d["delta"] = {"move": a.delta_move, "jfrog_equivalent": a.delta_jfrog_equivalent,
                      "strategic_impact": a.delta_strategic_impact,
                      "talking_points": a.delta_talking_points or []}
    return d


def _ref(a: Article) -> dict:
    return {"id": a.id, "title": a.title, "url": a.url,
            "published_at": a.published_at.isoformat() if a.published_at else None,
            "source_name": a.source_name}


def _resolve(session, sections: dict | list) -> dict:
    ids: set[int] = set()

    def walk(node):
        if isinstance(node, dict):
            raw = node.get("article_ids")
            if isinstance(raw, list):
                ids.update(i for i in raw if isinstance(i, int) and not isinstance(i, bool))
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
    walk(sections)
    if not ids:
        return {}
    rows = session.scalars(select(Article).where(Article.id.in_(ids))).all()
    return {str(a.id): _ref(a) for a in rows}


@router.get("/articles")
def list_articles(competitor: str | None = None, domain: str | None = None,
                  event_type: str | None = None, min_impact: int = 1,
                  q: str | None = None, page: int = 1, page_size: int = Query(20, le=100),
                  sf=Depends(get_session_factory)):
    with sf() as session:
        stmt = select(Article).where(Article.status == "enriched", Article.relevant.is_(True))
        if domain:
            stmt = stmt.where(Article.domain == domain)
        if event_type:
            stmt = stmt.where(Article.event_type == event_type)
        if min_impact > 1:
            stmt = stmt.where(Article.jfrog_impact >= min_impact)
        if q and q.strip():
            escaped = q.replace('"', '""')
            fts = text("SELECT rowid FROM articles_fts WHERE articles_fts MATCH :q")
            try:
                hit_ids = [r[0] for r in session.execute(fts, {"q": f'"{escaped}"'})]
            except OperationalError:
                hit_ids = []          # malformed query -> no matches, not a 500
            stmt = stmt.where(Article.id.in_(hit_ids or [-1]))
        rows = list(session.scalars(stmt.order_by(desc(Article.fetched_at))))
        if competitor:
            rows = [a for a in rows if competitor in (a.competitors or [])]
        total = len(rows)
        rows = rows[(page - 1) * page_size: page * page_size]
        return {"items": [_article_dict(a) for a in rows], "total": total,
                "page": page, "page_size": page_size}


@router.get("/digest")
def get_digest(date: str | None = None, sf=Depends(get_session_factory)):
    with sf() as session:
        stmt = select(Digest)
        stmt = stmt.where(Digest.date == date) if date else stmt.order_by(desc(Digest.date))
        row = session.scalars(stmt).first()
        if row is None:
            raise HTTPException(404, "no digest for that date")
        return {"date": row.date, "exec_summary": row.exec_summary, "sections": row.sections,
                "generated_at": row.generated_at.isoformat(), "model_used": row.model_used,
                "articles": _resolve(session, row.sections)}


@router.get("/digest/dates")
def digest_dates(sf=Depends(get_session_factory)):
    with sf() as session:
        return [d for (d,) in session.execute(select(Digest.date).order_by(desc(Digest.date)))]


@router.get("/competitors")
def competitors(sf=Depends(get_session_factory), appcfg=Depends(get_appcfg)):
    with sf() as session:
        rows = session.scalars(select(Article).where(
            Article.status == "enriched", Article.relevant.is_(True))).all()
        out = []
        for c in appcfg.competitors:
            mine = [a for a in rows if c["slug"] in (a.competitors or [])]
            last = max((a.fetched_at for a in mine), default=None)
            out.append({"slug": c["slug"], "name": c["name"], "color": c["color"],
                        "article_count": len(mine),
                        "high_impact_count": sum(1 for a in mine if (a.jfrog_impact or 0) >= 4),
                        "last_activity": last.isoformat() if last else None})
        return out


@router.get("/competitors/{slug}/battlecard")
def battlecard(slug: str, sf=Depends(get_session_factory), appcfg=Depends(get_appcfg)):
    comp = appcfg.competitor_by_slug(slug)
    if comp is None:
        raise HTTPException(404, "unknown competitor")
    with sf() as session:
        card = session.scalar(select(Battlecard).where(Battlecard.competitor_slug == slug))
        moves = card.recent_moves if card else []
        return {"slug": slug, "name": comp["name"], "color": comp["color"],
                "base": comp["battlecard_base"], "recent_moves": moves,
                "generated_at": card.generated_at.isoformat() if card else None,
                "articles": _resolve(session, moves)}


@router.get("/matrix")
def matrix(appcfg=Depends(get_appcfg)):
    return appcfg.matrix


@router.get("/meta")
def meta(request_settings=Depends(get_settings), sf=Depends(get_session_factory),
         appcfg=Depends(get_appcfg)):
    from app.main import DEMO_FLAG
    with sf() as session:
        last = session.scalar(select(SourceRun.started_at).order_by(desc(SourceRun.started_at)))
    return {"provider": request_settings.llm_provider, "model": request_settings.llm_model,
            "demo_mode": DEMO_FLAG["on"], "refresh_hour": request_settings.refresh_hour,
            "last_refresh": last.isoformat() if last else None,
            "competitors": len(appcfg.competitors), "version": "0.1.0",
            "refresh_state": REFRESH_STATE}


@router.get("/sources/health")
def sources_health(sf=Depends(get_session_factory)):
    with sf() as session:
        rows = session.scalars(select(SourceRun).order_by(desc(SourceRun.id)).limit(200)).all()
        latest: dict[str, SourceRun] = {}
        for r in rows:
            latest.setdefault(r.source_name, r)
        return [{"source_name": r.source_name, "ok": r.ok, "items_found": r.items_found,
                 "error": r.error, "started_at": r.started_at.isoformat()}
                for r in latest.values()]
