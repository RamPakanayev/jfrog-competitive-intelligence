import pytest
from pydantic import ValidationError

from app.llm.schemas import (
    Claim,
    DigestSchema,
    Enrichment,
    enforce_battlecard_citations,
    enforce_digest_citations,
)


def test_enrichment_validates_bounds():
    e = Enrichment(relevant=True, competitors=["snyk"], domain="devsecops_scanning",
                   event_type="pricing_change", summary="s", jfrog_impact=4, so_what="w")
    assert e.jfrog_impact == 4
    with pytest.raises(ValidationError):
        Enrichment(relevant=True, domain="devsecops_scanning", event_type="other",
                   summary="s", jfrog_impact=9, so_what="w")
    with pytest.raises(ValidationError):
        Enrichment(relevant=True, domain="not_a_domain", event_type="other",
                   summary="s", jfrog_impact=3, so_what="w")


def _digest() -> DigestSchema:
    return DigestSchema(
        exec_summary="day summary",
        top_developments=[Claim(text="valid claim", article_ids=[1, 99]),
                          Claim(text="orphan claim", article_ids=[99])],
        by_competitor=[{"competitor": "snyk",
                        "highlights": [{"text": "h", "article_ids": [2]}]}],
        threats_opportunities=[{"kind": "threat", "text": "t", "article_ids": [1]},
                               {"kind": "opportunity", "text": "o", "article_ids": []}],
    )


def test_enforce_digest_citations_drops_invalid():
    cleaned = enforce_digest_citations(_digest(), valid_ids={1, 2})
    assert [c.text for c in cleaned.top_developments] == ["valid claim"]
    assert cleaned.top_developments[0].article_ids == [1]          # 99 stripped
    assert cleaned.by_competitor[0].highlights[0].article_ids == [2]
    kinds = [t.kind for t in cleaned.threats_opportunities]
    assert kinds == ["threat"]                                     # uncited opportunity dropped


def test_enforce_battlecard_citations():
    moves = [Claim(text="cited", article_ids=[5]), Claim(text="uncited", article_ids=[42])]
    assert [m.text for m in enforce_battlecard_citations(moves, {5})] == ["cited"]


def test_duplicate_citations_collapse_preserving_order():
    claims = [Claim(text="repeated", article_ids=[3, 1, 3, 99, 1])]
    assert enforce_battlecard_citations(claims, {1, 3})[0].article_ids == [3, 1]
