from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config_data import AppConfig
from app.llm.prompts import BATTLECARD_SYSTEM, BATTLECARD_USER
from app.llm.schemas import BattlecardGen, enforce_battlecard_citations
from app.models import Article, Battlecard, utcnow

LOOKBACK_DAYS = 14
MAX_ITEMS = 15


def refresh_battlecards(session: Session, gateway, appcfg: AppConfig) -> int:
    since = utcnow() - timedelta(days=LOOKBACK_DAYS)
    recent = list(session.scalars(select(Article).where(
        Article.status == "enriched", Article.relevant.is_(True),
        Article.fetched_at >= since)
        .order_by(Article.jfrog_impact.desc())))
    updated = 0
    for comp in appcfg.competitors:
        slug, name = comp["slug"], comp["name"]
        items = [a for a in recent if slug in (a.competitors or [])][:MAX_ITEMS]
        if not items:
            continue
        lines = [f"[{a.id}] ({a.event_type}, impact {a.jfrog_impact}) {a.summary}" for a in items]
        gen: BattlecardGen | None = gateway.complete_json(
            BATTLECARD_SYSTEM.format(name=name),
            BATTLECARD_USER.format(name=name, items="\n".join(lines)), BattlecardGen)
        if gen is None:
            continue
        moves = enforce_battlecard_citations(gen.recent_moves, {a.id for a in items})
        card = session.scalar(select(Battlecard).where(Battlecard.competitor_slug == slug))
        if card is None:
            card = Battlecard(competitor_slug=slug)
            session.add(card)
        card.recent_moves = [m.model_dump() for m in moves]
        card.generated_at = utcnow()
        updated += 1
    session.commit()
    return updated
