from app.config import Settings
from app.config_data import AppConfig
from app.llm.schemas import Delta
from app.pipeline.delta import run_delta_analysis
from tests.conftest import FakeGateway, make_article


def appcfg() -> AppConfig:
    return AppConfig.load(Settings(_env_file=None).config_dir)


def enriched(session, url, impact, **kw):
    return make_article(session, url=url, title=f"t{impact}", status="enriched",
                        relevant=True, competitors=["snyk"], domain="devsecops_scanning",
                        event_type="product_launch", summary="sum", jfrog_impact=impact,
                        so_what="w", **kw)


def test_delta_only_for_high_impact(session):
    high = enriched(session, "https://d.example/1", 4)
    enriched(session, "https://d.example/2", 3)
    gw = FakeGateway([Delta(competitor_move="m", jfrog_equivalent="Xray contextual analysis",
                            strategic_impact="high", talking_points=["a", "b"])])
    n = run_delta_analysis(session, gw, appcfg())
    assert n == 1 and len(gw.calls) == 1
    session.refresh(high)
    assert high.delta_strategic_impact == "high"
    assert high.delta_talking_points == ["a", "b"]
    _, system, _ = gw.calls[0]
    assert "Xray contextual analysis" in system  # capability sheet injected


def test_delta_idempotent_and_failsoft(session):
    a = enriched(session, "https://d.example/3", 5)
    a.delta_move = "already done"
    session.commit()
    b = enriched(session, "https://d.example/4", 5)
    gw = FakeGateway([None])  # LLM fails
    n = run_delta_analysis(session, gw, appcfg())
    assert n == 0 and len(gw.calls) == 1  # only b attempted, failed softly
    session.refresh(b)
    assert b.delta_move is None and b.status == "enriched"  # article stays usable
