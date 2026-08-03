from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config_data import AppConfig
from app.llm.prompts import ENRICH_SYSTEM, ENRICH_USER
from app.llm.schemas import Enrichment
from app.models import Article, utcnow


def enrich_new_articles(session: Session, gateway, appcfg: AppConfig, limit: int = 200) -> int:
    system = ENRICH_SYSTEM.format(slugs=", ".join(appcfg.slugs()))
    known = set(appcfg.slugs())
    done = 0
    articles = session.scalars(
        select(Article).where(Article.status == "new").order_by(Article.id).limit(limit)).all()
    for a in articles:
        user = ENRICH_USER.format(title=a.title, source_name=a.source_name,
                                  source_type=a.source_type,
                                  published_at=a.published_at or "unknown",
                                  excerpt=a.body_excerpt[:800])
        enr: Enrichment | None = gateway.complete_json(system, user, Enrichment)
        if enr is None:
            a.status = "failed"
            continue
        a.relevant = enr.relevant
        if not enr.relevant:
            a.status = "irrelevant"
        else:
            a.competitors = [s for s in enr.competitors if s in known]
            a.domain = enr.domain
            a.event_type = enr.event_type
            a.summary = enr.summary
            a.jfrog_impact = enr.jfrog_impact
            a.so_what = enr.so_what
            a.status = "enriched"
            a.enriched_at = utcnow()
        done += 1
    session.commit()
    return done
