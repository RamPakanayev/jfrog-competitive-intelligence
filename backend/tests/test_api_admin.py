import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.pipeline.run import REFRESH_STATE
from tests.conftest import FakeGateway


@pytest.fixture()
def client(tmp_path, session_factory):
    settings = Settings(_env_file=None, database_url=f"sqlite:///{tmp_path}/adm.db",
                        demo_mode="off", enable_scheduler=False)
    app = create_app(settings)
    app.state.session_factory = session_factory
    app.state.gateway = FakeGateway()
    with TestClient(app) as c:
        yield c


def test_refresh_status_reflects_state(client):
    REFRESH_STATE.update(running=False, stage="idle", errors=[])
    r = client.get("/api/refresh/status")
    assert r.status_code == 200 and r.json()["stage"] == "idle"


def test_refresh_conflict_while_running(client):
    REFRESH_STATE["running"] = True
    try:
        assert client.post("/api/refresh").status_code == 409
    finally:
        REFRESH_STATE["running"] = False


def test_refresh_starts_background_run(client, monkeypatch):
    called = {}

    async def fake_run(sf, settings, appcfg, gateway):
        called["yes"] = True
        return {"inserted": 0}
    monkeypatch.setattr("app.api.routes_admin.run_pipeline", fake_run)
    r = client.post("/api/refresh")
    assert r.status_code == 202 and r.json()["started"] is True
    assert called.get("yes") is True  # TestClient runs background tasks on response


def test_refresh_blocked_in_demo_mode(client):
    from app.main import DEMO_FLAG
    DEMO_FLAG["on"] = True
    try:
        r = client.post("/api/refresh")
        assert r.status_code == 409 and "demo" in r.json()["detail"].lower()
    finally:
        DEMO_FLAG["on"] = False
