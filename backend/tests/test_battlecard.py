from app.config import Settings
from app.config_data import AppConfig
from app.llm.schemas import BattlecardGen, Claim
from app.models import Battlecard
from app.pipeline.battlecard import refresh_battlecards
from tests.conftest import FakeGateway, make_article


def appcfg() -> AppConfig:
    return AppConfig.load(Settings(_env_file=None).config_dir)


def test_refresh_only_competitors_with_news(session):
    a = make_article(session, url="https://b.example/1", title="Snyk news", status="enriched",
                     relevant=True, competitors=["snyk"], jfrog_impact=3, summary="s",
                     domain="devsecops_scanning", event_type="feature_update", so_what="w")
    gw = FakeGateway([BattlecardGen(recent_moves=[
        Claim(text="cited move", article_ids=[a.id]),
        Claim(text="uncited move", article_ids=[777])])])
    n = refresh_battlecards(session, gw, appcfg())
    assert n == 1 and len(gw.calls) == 1  # only snyk had items
    card = session.query(Battlecard).filter_by(competitor_slug="snyk").one()
    assert [m["text"] for m in card.recent_moves] == ["cited move"]


def test_refresh_upserts_and_failsoft(session):
    make_article(session, url="https://b.example/2", title="GitLab news", status="enriched",
                 relevant=True, competitors=["gitlab"], jfrog_impact=2, summary="s",
                 domain="cicd", event_type="feature_update", so_what="w")
    session.add(Battlecard(competitor_slug="gitlab",
                           recent_moves=[{"text": "old", "article_ids": [1]}]))
    session.commit()
    gw = FakeGateway([None])  # LLM fails
    n = refresh_battlecards(session, gw, appcfg())
    assert n == 0
    card = session.query(Battlecard).filter_by(competitor_slug="gitlab").one()
    assert card.recent_moves[0]["text"] == "old"  # untouched on failure


def test_noisy_competitor_does_not_starve_others(session):
    for i in range(30):
        make_article(session, url=f"https://b.example/noise{i}", title=f"Snyk {i}",
                     status="enriched", relevant=True, competitors=["snyk"], jfrog_impact=5,
                     summary="s", domain="devsecops_scanning", event_type="feature_update",
                     so_what="w")
    make_article(session, url="https://b.example/quiet", title="GitLab quiet news",
                 status="enriched", relevant=True, competitors=["gitlab"], jfrog_impact=1,
                 summary="s", domain="cicd", event_type="feature_update", so_what="w")

    gw = FakeGateway([BattlecardGen(recent_moves=[Claim(text="m", article_ids=[1])]),
                      BattlecardGen(recent_moves=[Claim(text="m", article_ids=[31])])])
    refresh_battlecards(session, gw, appcfg())

    refreshed = {c.competitor_slug for c in session.query(Battlecard)}
    assert "gitlab" in refreshed, "low-impact competitor starved by a noisy one"
