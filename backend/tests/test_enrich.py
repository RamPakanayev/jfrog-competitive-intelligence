from app.config import Settings
from app.config_data import AppConfig
from app.llm.schemas import Enrichment
from app.pipeline.enrich import enrich_new_articles
from tests.conftest import FakeGateway, make_article


def appcfg() -> AppConfig:
    return AppConfig.load(Settings(_env_file=None).config_dir)


def test_enrich_applies_fields_and_statuses(session):
    a1 = make_article(session, url="https://a.example/1", title="Snyk price hike")
    a2 = make_article(session, url="https://a.example/2", title="Kittens are cute")
    a3 = make_article(session, url="https://a.example/3", title="LLM broke")
    gw = FakeGateway([
        Enrichment(relevant=True, competitors=["snyk", "not_tracked"], domain="devsecops_scanning",
                   event_type="pricing_change", summary="s", jfrog_impact=4, so_what="w"),
        Enrichment(relevant=False, domain="other", event_type="other",
                   summary="", jfrog_impact=1, so_what=""),
        None,  # gateway failure
    ])
    n = enrich_new_articles(session, gw, appcfg())
    assert n == 2  # two successfully classified (one relevant, one irrelevant)

    session.refresh(a1); session.refresh(a2); session.refresh(a3)
    assert a1.status == "enriched" and a1.relevant is True
    assert a1.competitors == ["snyk"]           # unknown slug filtered out
    assert a1.jfrog_impact == 4 and a1.enriched_at is not None
    assert a2.status == "irrelevant" and a2.relevant is False
    assert a3.status == "failed"


def test_enrich_skips_non_new(session):
    make_article(session, url="https://a.example/4", title="done", status="enriched")
    gw = FakeGateway([])
    assert enrich_new_articles(session, gw, appcfg()) == 0
    assert gw.calls == []


def test_prompt_contains_slugs_and_title(session):
    make_article(session, url="https://a.example/5", title="GitLab ships thing")
    gw = FakeGateway([Enrichment(relevant=True, competitors=["gitlab"], domain="cicd",
                                 event_type="feature_update", summary="s",
                                 jfrog_impact=2, so_what="w")])
    enrich_new_articles(session, gw, appcfg())
    schema_name, system, user = gw.calls[0]
    assert schema_name == "Enrichment"
    assert "sonatype, gitlab, github, docker, snyk" in system
    assert "GitLab ships thing" in user
