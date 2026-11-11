import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import pytest
from fastapi.testclient import TestClient
import app as proxy


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "t.db")); monkeypatch.setenv("ADMIN_TOKEN", "adm")
    seen = []
    def fake(payload):
        seen.append(payload)
        return 200, {"choices": [{"message": {"content": "hi"}}], "usage": {"prompt_tokens": 1000, "completion_tokens": 200, "cost": 0.08}}
    monkeypatch.setattr(proxy, "forward", fake)
    c = TestClient(proxy.app); c.seen = seen
    return c


def lic(c, plan="free"):
    return c.post("/admin/licenses", json={"plan": plan}, headers={"X-Admin-Token": "adm"}).json()["license_key"]


def test_requires_license_and_admin(client):
    assert client.post("/v1/chat/completions", json={}, headers={"Authorization": "Bearer nope"}).status_code == 401
    assert client.post("/admin/licenses", json={"plan": "free"}).status_code == 403


def test_forces_model_caps_tokens_and_meters(client):
    h = {"Authorization": f"Bearer {lic(client)}"}
    assert client.post("/v1/chat/completions", json={"model": "expensive/model", "max_tokens": 99999, "messages": []}, headers=h).status_code == 200
    sent = client.seen[0]
    assert sent["model"] == "openai/gpt-4o-mini" and sent["max_tokens"] == 700
    assert client.get("/v1/usage", headers=h).json()["spent_usd"] == 0.08


def test_budget_blocks_after_limit(client):
    h = {"Authorization": f"Bearer {lic(client)}"}          # free budget 0.15, each call costs 0.08
    codes = [client.post("/v1/chat/completions", json={"messages": []}, headers=h).status_code for _ in range(3)]
    assert codes == [200, 200, 402]
