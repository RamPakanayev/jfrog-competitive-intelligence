import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone

import httpx

from app.config import Settings
from app.config_data import AppConfig
from app.models import SourceRun, utcnow
from app.pipeline.battlecard import refresh_battlecards
from app.pipeline.dedupe import insert_new_items
from app.pipeline.delta import run_delta_analysis
from app.pipeline.digest import generate_digest
from app.pipeline.enrich import enrich_new_articles
from app.sources.hackernews import fetch_hackernews
from app.sources.reddit import fetch_reddit
from app.sources.rss import fetch_rss
from app.sources.tavily import fetch_tavily

log = logging.getLogger("ribbit.pipeline")

REFRESH_STATE: dict = {"running": False, "stage": "idle", "counts": {}, "errors": [],
                       "started_at": None, "finished_at": None}


def _tasks_for(client, settings: Settings, appcfg: AppConfig, window: datetime):
    tasks: list[tuple[str, object]] = []
    for comp in appcfg.competitors:
        src = comp["sources"]
        for url in src.get("rss", []):
            tasks.append((f"{comp['name']} RSS", fetch_rss(client, f"{comp['name']} Blog", url, window)))
        if src.get("hn_query"):
            tasks.append((f"{comp['name']} HackerNews",
                          fetch_hackernews(client, src["hn_query"], window)))
        if src.get("reddit"):
            tasks.append((f"{comp['name']} Reddit",
                          fetch_reddit(client, src["reddit"].get("subreddits", []),
                                       src["reddit"].get("query", comp["name"]), window)))
        tavily_key = settings.tavily_api_key.get_secret_value()
        if tavily_key and src.get("tavily_query"):
            tasks.append((f"{comp['name']} Tavily",
                          fetch_tavily(client, tavily_key, src["tavily_query"], window)))
    for feed in appcfg.industry_feeds:
        tasks.append((feed["name"], fetch_rss(client, feed["name"], feed["url"], window)))
    return tasks


def _llm_stages(session_factory, settings: Settings, appcfg: AppConfig, gateway) -> dict:
    """Run the four LLM stages on their own session. Called via asyncio.to_thread."""
    out = {}
    with session_factory() as s:
        REFRESH_STATE["stage"] = "enriching"
        out["enriched"] = enrich_new_articles(s, gateway, appcfg)
        REFRESH_STATE["stage"] = "delta"
        out["deltas"] = run_delta_analysis(s, gateway, appcfg)
        REFRESH_STATE["stage"] = "digest"
        today = datetime.now(timezone.utc).date().isoformat()
        generate_digest(s, gateway, today,
                        model_label=f"{settings.llm_provider}/{settings.llm_model}")
        REFRESH_STATE["stage"] = "battlecards"
        out["battlecards"] = refresh_battlecards(s, gateway, appcfg)
    return out


async def run_pipeline(session_factory, settings: Settings, appcfg: AppConfig, gateway,
                       transport: httpx.BaseTransport | None = None) -> dict:
    run_id = uuid.uuid4().hex[:8]
    REFRESH_STATE.update(running=True, stage="fetching", counts={}, errors=[],
                         started_at=utcnow().isoformat(), finished_at=None)
    window = datetime.now(timezone.utc) - timedelta(days=settings.fetch_window_days)
    report = {"inserted": 0, "enriched": 0, "deltas": 0, "battlecards": 0}
    try:
        async with httpx.AsyncClient(transport=transport, follow_redirects=True) as client:
            named = _tasks_for(client, settings, appcfg, window)
            results = await asyncio.gather(*(t for _, t in named), return_exceptions=True)
        items = []
        with session_factory() as s:
            for (name, _), res in zip(named, results):
                if isinstance(res, BaseException):
                    s.add(SourceRun(run_id=run_id, source_name=name, ok=False, error=str(res)))
                    REFRESH_STATE["errors"].append(f"{name}: {res}")
                else:
                    s.add(SourceRun(run_id=run_id, source_name=name, ok=True,
                                    items_found=len(res)))
                    items.extend(res)
            s.commit()
            report["inserted"] = insert_new_items(s, items)
            REFRESH_STATE["counts"]["inserted"] = report["inserted"]

        if not gateway.available():
            REFRESH_STATE["errors"].append("LLM unavailable - enrichment skipped")
        else:
            # LiteLLM is synchronous and a full run costs minutes. Running it inline would
            # block the event loop and freeze the API for the whole refresh, so the LLM
            # stages run in a worker thread with their own session.
            report.update(await asyncio.to_thread(
                _llm_stages, session_factory, settings, appcfg, gateway))
        REFRESH_STATE["counts"].update(report)
        REFRESH_STATE["stage"] = "done"
    except Exception as e:  # broad on purpose: never leave state stuck on running
        log.exception("pipeline crashed")
        REFRESH_STATE["errors"].append(str(e))
        REFRESH_STATE["stage"] = "error"
    finally:
        REFRESH_STATE["running"] = False
        REFRESH_STATE["finished_at"] = utcnow().isoformat()
    return report
