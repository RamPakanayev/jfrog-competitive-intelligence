import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.models import Battlecard, Digest
from tests.conftest import FakeGateway, make_article


@pytest.fixture()
def client(tmp_path, session_factory, engine):
    settings = Settings(_env_file=None, database_url=f"sqlite:///{tmp_path}/api.db",
                        demo_mode="off", enable_scheduler=False)
    app = create_app(settings)
    app.state.session_factory = session_factory   # inject test DB
    app.state.gateway = FakeGateway()
    with TestClient(app) as c:
        yield c


def seed(session):
    a = make_article(session, url="https://s.example/1", title="Snyk pricing move",
                     status="enriched", relevant=True, competitors=["snyk"],
                     domain="devsecops_scanning", event_type="pricing_change",
                     summary="Snyk raised prices.", jfrog_impact=4, so_what="displacement window",
                     delta_move="m", delta_jfrog_equivalent="Xray", delta_strategic_impact="high",
                     delta_talking_points=["t1"])
    make_article(session, url="https://s.example/2", title="GitLab minor", status="enriched",
                 relevant=True, competitors=["gitlab"], domain="cicd",
                 event_type="feature_update", summary="s", jfrog_impact=2, so_what="w")
    session.add(Digest(date="2026-08-03", exec_summary="busy",
                       sections={"top_developments": [{"text": "c", "article_ids": [a.id]}],
                                 "by_competitor": [], "threats_opportunities": []},
                       model_used="test"))
    session.add(Battlecard(competitor_slug="snyk",
                           recent_moves=[{"text": "mv", "article_ids": [a.id]}]))
    session.commit()
    return a


def test_articles_filters(client, session):
    seed(session)
    r = client.get("/api/articles", params={"competitor": "snyk", "min_impact": 3})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    art = body["items"][0]
    assert art["title"] == "Snyk pricing move"
    assert art["delta"]["strategic_impact"] == "high"

    assert client.get("/api/articles", params={"event_type": "feature_update"}).json()["total"] == 1
    assert client.get("/api/articles", params={"q": "pricing"}).json()["total"] == 1


def test_digest_with_resolved_articles(client, session):
    a = seed(session)
    r = client.get("/api/digest")
    assert r.status_code == 200
    d = r.json()
    assert d["date"] == "2026-08-03" and d["exec_summary"] == "busy"
    assert d["articles"][str(a.id)]["url"] == "https://s.example/1"
    assert client.get("/api/digest/dates").json() == ["2026-08-03"]
    assert client.get("/api/digest", params={"date": "1999-01-01"}).status_code == 404


def test_competitors_and_battlecard(client, session):
    a = seed(session)
    comps = client.get("/api/competitors").json()
    snyk = next(c for c in comps if c["slug"] == "snyk")
    assert snyk["article_count"] == 1 and snyk["high_impact_count"] == 1
    card = client.get("/api/competitors/snyk/battlecard").json()
    assert card["base"]["strengths"] and card["recent_moves"][0]["text"] == "mv"
    assert card["articles"][str(a.id)]["title"] == "Snyk pricing move"
    assert client.get("/api/competitors/nope/battlecard").status_code == 404


def test_matrix_meta_sources(client, session):
    m = client.get("/api/matrix").json()
    assert m["vendors"][0] == "jfrog" and len(m["rows"]) >= 6
    meta = client.get("/api/meta").json()
    assert meta["demo_mode"] is False and "provider" in meta
    assert client.get("/api/sources/health").json() == []
