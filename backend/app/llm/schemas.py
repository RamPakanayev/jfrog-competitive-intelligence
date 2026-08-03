from typing import Literal

from pydantic import BaseModel, Field

Domain = Literal["artifact_management", "container_registry", "devsecops_scanning",
                 "cicd", "sbom_supply_chain", "other"]
EventType = Literal["product_launch", "feature_update", "security_advisory",
                    "pricing_change", "funding_ma", "partnership", "other"]


class Enrichment(BaseModel):
    relevant: bool
    competitors: list[str] = Field(default_factory=list)
    domain: Domain = "other"
    event_type: EventType = "other"
    summary: str = ""
    jfrog_impact: int = Field(1, ge=1, le=5)
    so_what: str = ""


class Delta(BaseModel):
    competitor_move: str
    jfrog_equivalent: str
    strategic_impact: Literal["high", "medium", "low"]
    talking_points: list[str] = Field(default_factory=list, max_length=3)


class Claim(BaseModel):
    text: str
    article_ids: list[int] = Field(default_factory=list)


class CompetitorSection(BaseModel):
    competitor: str
    highlights: list[Claim] = Field(default_factory=list)


class TypedClaim(Claim):
    kind: Literal["threat", "opportunity"]


class DigestSchema(BaseModel):
    exec_summary: str
    top_developments: list[Claim] = Field(default_factory=list)
    by_competitor: list[CompetitorSection] = Field(default_factory=list)
    threats_opportunities: list[TypedClaim] = Field(default_factory=list)


class BattlecardGen(BaseModel):
    recent_moves: list[Claim] = Field(default_factory=list)


class ChatAnswer(BaseModel):
    answer: str
    citation_ids: list[int] = Field(default_factory=list)


def _clean_claims(claims: list, valid_ids: set[int]) -> list:
    """Strip unknown article_ids; drop claims left with none. The hallucination firewall."""
    cleaned = []
    for c in claims:
        ids = [i for i in c.article_ids if i in valid_ids]
        if ids:
            cleaned.append(c.model_copy(update={"article_ids": ids}))
    return cleaned


def enforce_digest_citations(d: DigestSchema, valid_ids: set[int]) -> DigestSchema:
    return d.model_copy(update={
        "top_developments": _clean_claims(d.top_developments, valid_ids),
        "by_competitor": [s.model_copy(update={"highlights": _clean_claims(s.highlights, valid_ids)})
                          for s in d.by_competitor
                          if _clean_claims(s.highlights, valid_ids)],
        "threats_opportunities": _clean_claims(d.threats_opportunities, valid_ids),
    })


def enforce_battlecard_citations(moves: list[Claim], valid_ids: set[int]) -> list[Claim]:
    return _clean_claims(moves, valid_ids)
