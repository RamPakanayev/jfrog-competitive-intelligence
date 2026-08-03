from types import SimpleNamespace

from app.config import Settings
from app.llm.gateway import LLMGateway, _extract_json
from app.llm.schemas import Enrichment

GOOD = ('{"relevant": true, "competitors": ["snyk"], "domain": "devsecops_scanning",'
        ' "event_type": "pricing_change", "summary": "s", "jfrog_impact": 4, "so_what": "w"}')


def fake_completion(replies: list[str], calls: list[dict]):
    def _fake(**kwargs):
        calls.append(kwargs)
        text = replies.pop(0)
        if text == "RAISE":
            raise RuntimeError("provider down")
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])
    return _fake


def settings(**kw) -> Settings:
    return Settings(_env_file=None, anthropic_api_key="k", **kw)


def test_extract_json_strips_fences_and_prose():
    assert _extract_json("Sure!\n```json\n{\"a\": 1}\n```\nDone.") == '{"a": 1}'
    assert _extract_json('{"a": 1}') == '{"a": 1}'


def test_complete_json_happy_path(monkeypatch):
    calls: list[dict] = []
    monkeypatch.setattr("app.llm.gateway.litellm.completion", fake_completion([GOOD], calls))
    gw = LLMGateway(settings())
    out = gw.complete_json("sys", "user", Enrichment)
    assert out and out.jfrog_impact == 4
    assert calls[0]["model"] == "anthropic/claude-haiku-4-5"


def test_repair_retry_on_invalid_json(monkeypatch):
    calls: list[dict] = []
    monkeypatch.setattr("app.llm.gateway.litellm.completion",
                        fake_completion(["not json at all", GOOD], calls))
    gw = LLMGateway(settings())
    out = gw.complete_json("sys", "user", Enrichment)
    assert out and out.relevant is True
    assert len(calls) == 2 and "previous output was invalid" in calls[1]["messages"][-1]["content"]


def test_fallback_provider_on_error(monkeypatch):
    calls: list[dict] = []
    monkeypatch.setattr("app.llm.gateway.litellm.completion",
                        fake_completion(["RAISE", GOOD], calls))
    gw = LLMGateway(settings(llm_fallback_provider="ollama"))
    out = gw.complete_json("sys", "user", Enrichment)
    assert out is not None
    assert calls[1]["model"] == "ollama/llama3.1:8b"


def test_gives_up_returns_none(monkeypatch):
    monkeypatch.setattr("app.llm.gateway.litellm.completion",
                        fake_completion(["nope", "still nope"], []))
    gw = LLMGateway(settings())
    assert gw.complete_json("sys", "user", Enrichment) is None


def test_available_by_key():
    assert LLMGateway(settings()).available() is True
    s = Settings(_env_file=None)  # no keys
    assert LLMGateway(s)._has_key("anthropic") is False
