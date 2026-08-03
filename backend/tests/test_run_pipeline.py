import httpx

from app.config import Settings
from app.config_data import AppConfig
from app.llm.schemas import BattlecardGen, Claim, Delta, DigestSchema, Enrichment
from app.models import Article, SourceRun
from app.pipeline.run import REFRESH_STATE, run_pipeline
from tests.conftest import FakeGateway

RSS = (b'<?xml version="1.0"?><rss version="2.0"><channel><title>T</title>'
       b'<item><title>Sonatype ships SBOM thing</title>'
       b'<link>https://vendor.example/p1</link><description>d</description>'
       b'<pubDate>Mon, 03 Aug 2026 08:00:00 GMT</pubDate></item></channel></rss>')


def make_transport():
    def handler(request: httpx.Request) -> httpx.Response:
        host = request.url.host
        if host == "hn.algolia.com":
            return httpx.Response(500)  # one failing source must not kill the run
        return httpx.Response(200, content=RSS,
                              headers={"content-type": "application/rss+xml"})
    return httpx.MockTransport(handler)


def one_competitor_cfg() -> AppConfig:
    cfg = AppConfig.load(Settings(_env_file=None).config_dir)
    cfg.competitors = [c for c in cfg.competitors if c["slug"] == "sonatype"]
    cfg.industry_feeds = []
    return cfg


async def test_pipeline_end_to_end_with_isolation(session_factory):
    enr = Enrichment(relevant=True, competitors=["sonatype"], domain="artifact_management",
                     event_type="product_launch", summary="s", jfrog_impact=4, so_what="w")
    gw = FakeGateway([
        enr,
        Delta(competitor_move="m", jfrog_equivalent="Artifactory universal repository",
              strategic_impact="high", talking_points=["t"]),
        DigestSchema(exec_summary="day", top_developments=[Claim(text="c", article_ids=[1])],
                     by_competitor=[], threats_opportunities=[]),
        BattlecardGen(recent_moves=[Claim(text="mv", article_ids=[1])]),
    ])
    report = await run_pipeline(session_factory, Settings(_env_file=None), one_competitor_cfg(),
                                gw, transport=make_transport())
    assert report["inserted"] == 1 and report["enriched"] == 1
    assert REFRESH_STATE["running"] is False and REFRESH_STATE["stage"] == "done"

    with session_factory() as s:
        assert s.query(Article).count() == 1
        runs = s.query(SourceRun).all()
        assert any(not r.ok and "hackernews" in r.source_name.lower() for r in runs)
        assert any(r.ok and r.items_found == 1 for r in runs)


async def test_pipeline_skips_llm_stages_without_gateway_availability(session_factory):
    class DeadGateway(FakeGateway):
        def available(self) -> bool:
            return False
    report = await run_pipeline(session_factory, Settings(_env_file=None), one_competitor_cfg(),
                                DeadGateway(), transport=make_transport())
    assert report["inserted"] == 1 and report["enriched"] == 0
    assert "LLM unavailable" in " ".join(REFRESH_STATE["errors"])


async def test_overlapping_run_is_skipped_not_interleaved(session_factory):
    REFRESH_STATE["running"] = True
    try:
        report = await run_pipeline(session_factory, Settings(_env_file=None),
                                    one_competitor_cfg(), FakeGateway(),
                                    transport=make_transport())
    finally:
        REFRESH_STATE["running"] = False
    assert report["skipped"] is True
    assert report["inserted"] == 0
    with session_factory() as s:
        assert s.query(Article).count() == 0, "a skipped run must not touch the database"
