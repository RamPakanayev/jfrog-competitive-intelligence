from datetime import UTC, datetime

from app.llm.schemas import Claim, CompetitorSection, DigestSchema, TypedClaim
from app.models import Digest
from app.pipeline.digest import generate_digest
from tests.conftest import FakeGateway, make_article


def test_no_items_writes_quiet_digest_without_llm(session):
    gw = FakeGateway([])
    d = generate_digest(session, gw, date="2026-08-03")
    assert d.exec_summary.startswith("No significant")
    assert gw.calls == []
    assert session.query(Digest).filter_by(date="2026-08-03").count() == 1


def test_digest_enforces_citations_and_upserts(session):
    a = make_article(session, url="https://g.example/1", title="A", status="enriched",
                     relevant=True, competitors=["snyk"], jfrog_impact=4, summary="s",
                     domain="devsecops_scanning", event_type="product_launch", so_what="w",
                     fetched_at=datetime(2026, 8, 3, 10, tzinfo=UTC))
    raw = DigestSchema(
        exec_summary="Busy day.",
        top_developments=[Claim(text="real", article_ids=[a.id]),
                          Claim(text="hallucinated", article_ids=[999])],
        by_competitor=[CompetitorSection(competitor="snyk",
                                         highlights=[Claim(text="h", article_ids=[a.id])])],
        threats_opportunities=[TypedClaim(kind="threat", text="t", article_ids=[999])])
    gw = FakeGateway([raw])
    generate_digest(session, gw, date="2026-08-03")

    row = session.query(Digest).filter_by(date="2026-08-03").one()
    assert [c["text"] for c in row.sections["top_developments"]] == ["real"]
    assert row.sections["threats_opportunities"] == []
    _, system, user = gw.calls[0]
    assert f"[{a.id}]" in user and "CITATION RULE" in system

    # regeneration same date replaces, not duplicates
    gw2 = FakeGateway([raw])
    generate_digest(session, gw2, date="2026-08-03")
    assert session.query(Digest).filter_by(date="2026-08-03").count() == 1


def test_llm_failure_keeps_old_digest(session):
    make_article(session, url="https://g.example/2", title="B", status="enriched",
                 relevant=True, competitors=["gitlab"], jfrog_impact=3, summary="s",
                 domain="cicd", event_type="feature_update", so_what="w",
                 fetched_at=datetime(2026, 8, 3, 11, tzinfo=UTC))
    gw = FakeGateway([None])
    d = generate_digest(session, gw, date="2026-08-03")
    assert d is None  # failed, nothing written
    assert session.query(Digest).count() == 0
