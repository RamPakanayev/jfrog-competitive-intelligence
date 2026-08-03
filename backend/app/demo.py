import json
import logging
from datetime import datetime
from pathlib import Path

from sqlalchemy import select

from app.models import Article, Battlecard, Digest

log = logging.getLogger("ribbit.demo")


def _dt(v: str | None) -> datetime | None:
    return datetime.fromisoformat(v) if v else None


def load_seed(session_factory, seed_path: Path) -> dict:
    counts = {"articles": 0, "digests": 0, "battlecards": 0}
    if not Path(seed_path).exists():
        log.warning("demo seed missing: %s", seed_path)
        return counts
    data = json.loads(Path(seed_path).read_text())
    with session_factory() as s:
        if s.scalar(select(Article.id).limit(1)):
            return counts  # already populated - never double-load
        for a in data.get("articles", []):
            s.add(Article(id=a["id"], url=a["url"], content_hash=f"demo-{a['id']}",
                          title=a["title"], body_excerpt=a.get("body_excerpt", ""),
                          source_name=a["source_name"], source_type=a["source_type"],
                          published_at=_dt(a.get("published_at")),
                          fetched_at=_dt(a.get("fetched_at")), status=a["status"],
                          relevant=a.get("relevant"), competitors=a.get("competitors"),
                          domain=a.get("domain"), event_type=a.get("event_type"),
                          summary=a.get("summary"), jfrog_impact=a.get("jfrog_impact"),
                          so_what=a.get("so_what"), delta_move=a.get("delta_move"),
                          delta_jfrog_equivalent=a.get("delta_jfrog_equivalent"),
                          delta_strategic_impact=a.get("delta_strategic_impact"),
                          delta_talking_points=a.get("delta_talking_points")))
            counts["articles"] += 1
        for d in data.get("digests", []):
            s.add(Digest(date=d["date"], exec_summary=d["exec_summary"],
                         sections=d["sections"], model_used=d.get("model_used", "demo-seed")))
            counts["digests"] += 1
        for b in data.get("battlecards", []):
            s.add(Battlecard(competitor_slug=b["competitor_slug"],
                             recent_moves=b["recent_moves"]))
            counts["battlecards"] += 1
        s.commit()
    log.info("demo seed loaded: %s", counts)
    return counts


def maybe_enter_demo_mode(session_factory, gateway, settings) -> bool:
    if settings.demo_mode == "off":
        return False
    demo = settings.demo_mode == "on" or not gateway.available()
    if demo:
        load_seed(session_factory, settings.demo_seed_path)
    return demo
