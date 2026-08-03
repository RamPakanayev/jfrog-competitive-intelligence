from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config_data import AppConfig
from app.llm.prompts import DELTA_SYSTEM, DELTA_USER
from app.llm.schemas import Delta
from app.models import Article

DELTA_THRESHOLD = 4


def run_delta_analysis(session: Session, gateway, appcfg: AppConfig, limit: int = 25) -> int:
    system = DELTA_SYSTEM.format(capabilities=appcfg.capabilities_text())
    articles = session.scalars(
        select(Article).where(Article.status == "enriched",
                              Article.jfrog_impact >= DELTA_THRESHOLD,
                              Article.delta_move.is_(None))
        .order_by(Article.id).limit(limit)).all()
    done = 0
    for a in articles:
        user = DELTA_USER.format(competitors=", ".join(a.competitors or []),
                                 event_type=a.event_type, domain=a.domain,
                                 title=a.title, summary=a.summary or "")
        d: Delta | None = gateway.complete_json(system, user, Delta)
        if d is None:
            continue
        a.delta_move = d.competitor_move
        a.delta_jfrog_equivalent = d.jfrog_equivalent
        a.delta_strategic_impact = d.strategic_impact
        a.delta_talking_points = d.talking_points
        done += 1
    session.commit()
    return done
