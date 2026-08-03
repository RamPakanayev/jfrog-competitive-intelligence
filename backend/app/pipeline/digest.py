from datetime import UTC, datetime, time
from datetime import date as date_cls

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.llm.prompts import DIGEST_SYSTEM, DIGEST_USER
from app.llm.schemas import DigestSchema, enforce_digest_citations
from app.models import Article, Digest, utcnow


def _items_for(session: Session, date: str) -> list[Article]:
    day = date_cls.fromisoformat(date)
    start = datetime.combine(day, time.min, tzinfo=UTC)
    end = datetime.combine(day, time.max, tzinfo=UTC)
    return list(session.scalars(select(Article).where(
        Article.status == "enriched", Article.relevant.is_(True),
        Article.fetched_at >= start, Article.fetched_at <= end)
        .order_by(Article.jfrog_impact.desc())))


def _upsert(session: Session, date: str, exec_summary: str, sections: dict, model: str) -> Digest:
    row = session.scalar(select(Digest).where(Digest.date == date))
    if row is None:
        row = Digest(date=date, exec_summary=exec_summary, sections=sections, model_used=model)
        session.add(row)
    else:
        row.exec_summary, row.sections, row.model_used = exec_summary, sections, model
        row.generated_at = utcnow()
    session.commit()
    return row


def generate_digest(session: Session, gateway, date: str, model_label: str = "") -> Digest | None:
    items = _items_for(session, date)
    if not items:
        return _upsert(session, date,
                       "No significant competitive developments detected today.",
                       {"top_developments": [], "by_competitor": [], "threats_opportunities": []},
                       model_label)
    lines = [f"[{a.id}] ({', '.join(a.competitors or [])} | {a.domain} | {a.event_type} "
             f"| impact {a.jfrog_impact}) {a.summary} SO-WHAT: {a.so_what}" for a in items]
    raw: DigestSchema | None = gateway.complete_json(
        DIGEST_SYSTEM, DIGEST_USER.format(date=date, items="\n".join(lines)), DigestSchema)
    if raw is None:
        return None
    clean = enforce_digest_citations(raw, valid_ids={a.id for a in items})
    return _upsert(session, date, clean.exec_summary,
                   clean.model_dump(exclude={"exec_summary"}), model_label)
