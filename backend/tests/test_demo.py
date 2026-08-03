from app.config import Settings
from app.demo import load_seed, maybe_enter_demo_mode
from app.models import Article, Battlecard, Digest
from tests.conftest import FakeGateway


class DeadGateway(FakeGateway):
    def available(self) -> bool:
        return False


def test_load_seed_inserts_everything(session_factory):
    settings = Settings(_env_file=None)
    n = load_seed(session_factory, settings.demo_seed_path)
    with session_factory() as s:
        assert s.query(Article).count() == n["articles"] >= 3
        assert s.query(Digest).count() >= 1
        assert s.query(Battlecard).count() >= 2
        a = s.get(Article, 1)
        assert a.source_type == "demo" and a.delta_strategic_impact == "medium"


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
