"""Snapshot the current DB into data/demo/seed.json (run after a real refresh)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from sqlalchemy import create_engine, select          # noqa: E402
from sqlalchemy.orm import sessionmaker               # noqa: E402

from app.config import Settings                        # noqa: E402
from app.models import Article, Battlecard, Digest     # noqa: E402

settings = Settings()
engine = create_engine(settings.database_url)
S = sessionmaker(bind=engine)

with S() as s:
    articles = s.scalars(select(Article).where(Article.status == "enriched",
                                               Article.relevant.is_(True))
                         .order_by(Article.id)).all()
    out = {
        "articles": [{
            "id": a.id, "url": a.url, "title": a.title, "body_excerpt": a.body_excerpt[:400],
            "source_name": a.source_name, "source_type": a.source_type,
            "published_at": a.published_at.isoformat() if a.published_at else None,
            "fetched_at": a.fetched_at.isoformat() if a.fetched_at else None,
            "status": a.status, "relevant": a.relevant, "competitors": a.competitors,
            "domain": a.domain, "event_type": a.event_type, "summary": a.summary,
            "jfrog_impact": a.jfrog_impact, "so_what": a.so_what,
            "delta_move": a.delta_move, "delta_jfrog_equivalent": a.delta_jfrog_equivalent,
            "delta_strategic_impact": a.delta_strategic_impact,
            "delta_talking_points": a.delta_talking_points} for a in articles],
        "digests": [{"date": d.date, "exec_summary": d.exec_summary, "sections": d.sections,
                     "model_used": d.model_used}
                    for d in s.scalars(select(Digest)).all()],
        "battlecards": [{"competitor_slug": b.competitor_slug, "recent_moves": b.recent_moves}
                        for b in s.scalars(select(Battlecard)).all()],
    }

dest = Path(__file__).resolve().parents[1] / "data" / "demo" / "seed.json"
dest.write_text(json.dumps(out, indent=1))
print(f"wrote {dest}: {len(out['articles'])} articles, {len(out['digests'])} digests, "
      f"{len(out['battlecards'])} battlecards")
