from app.config import Settings
from app.demo import load_seed, maybe_enter_demo_mode
from app.models import Article, Battlecard, Digest
from tests.conftest import FakeGateway


class DeadGateway(FakeGateway):
    def available(self) -> bool:
        return False


def _claim_ids(node) -> list[int]:
    """Collect every article_id inside a nested digest section structure."""
    if isinstance(node, dict):
        ids = [i for i in node.get("article_ids", []) if isinstance(i, int)]
        return ids + [i for v in node.values() for i in _claim_ids(v)]
    if isinstance(node, list):
        return [i for v in node for i in _claim_ids(v)]
    return []


def test_load_seed_inserts_everything(session_factory):
    settings = Settings(_env_file=None)
    n = load_seed(session_factory, settings.demo_seed_path)
    with session_factory() as s:
        assert s.query(Article).count() == n["articles"] >= 3
        assert s.query(Digest).count() >= 1
        assert s.query(Battlecard).count() >= 2
        # Assert the shape the UI depends on, not the contents of one particular seed —
        # the shipped seed is a real pipeline capture and is expected to be re-captured.
        articles = s.query(Article).all()
        assert all(a.status == "enriched" and a.relevant for a in articles)
        assert all(a.summary and a.so_what and a.jfrog_impact for a in articles)
        assert any(a.delta_move and a.delta_strategic_impact for a in articles), \
            "seed should include at least one delta analysis so the Feed tab shows one"
        # every citation in the digest must resolve to a seeded article (the demo must not
        # ship the very dangling-citation state the citation firewall exists to prevent)
        ids = {a.id for a in articles}
        digest = s.query(Digest).first()
        cited = {i for section in digest.sections.values() for i in _claim_ids(section)}
        assert cited and cited <= ids, f"digest cites unseeded articles: {cited - ids}"


def test_load_seed_idempotent(session_factory):
    settings = Settings(_env_file=None)
    load_seed(session_factory, settings.demo_seed_path)
    again = load_seed(session_factory, settings.demo_seed_path)
    assert again["articles"] == 0  # DB non-empty -> no duplicate load


def test_maybe_enter_demo_mode_matrix(session_factory):
    s_on = Settings(_env_file=None, demo_mode="on")
    s_off = Settings(_env_file=None, demo_mode="off")
    s_auto = Settings(_env_file=None, demo_mode="auto")
    assert maybe_enter_demo_mode(session_factory, DeadGateway(), s_on) is True
    assert maybe_enter_demo_mode(session_factory, DeadGateway(), s_off) is False
    assert maybe_enter_demo_mode(session_factory, FakeGateway(), s_auto) is False
    assert maybe_enter_demo_mode(session_factory, DeadGateway(), s_auto) is True
