import json, time, pytest
from PIL import Image
from fastapi.testclient import TestClient
from app import agent, settings, training
from app.main import app


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("NOCODECV_HOME", str(tmp_path / "home"))
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)


def make(tmp_path, cats, dogs):
    for name, n in (("cats", cats), ("dogs", dogs)):
        d = tmp_path / "data" / name; d.mkdir(parents=True)
        for i in range(n):
            Image.new("RGB", (32, 32), (i * 3 % 255, i * 7 % 255, 100 if name == "cats" else 200)).save(d / f"{i}.png")
    return str(tmp_path / "data")


def scripted(monkeypatch, *steps):
    it = iter(steps)
    def fake(messages):
        s = next(it)
        if isinstance(s, str): return {"choices": [{"message": {"role": "assistant", "content": s}}]}
        name, args = s
        return {"choices": [{"message": {"role": "assistant", "content": None, "tool_calls": [{"id": "c1", "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}]}}]}
    monkeypatch.setattr(agent, "chat_completion", fake)


def test_missing_key_message(tmp_path):
    c = TestClient(app); pid = c.post("/projects", json={}).json()["id"]
    r = c.post(f"/projects/{pid}/agent", json={"message": "hi"})
    assert r.status_code == 400 and r.json()["detail"]["code"] == "no_key"


def test_flow_scan_plan_choice_approve(tmp_path, monkeypatch):
    c = TestClient(app); pid = c.post("/projects", json={}).json()["id"]
    data = make(tmp_path, 30, 50)
    scripted(monkeypatch, ("scan_folder", {"path": data}), "I checked your pictures.")
    r = c.post(f"/projects/{pid}/agent", json={"message": data}).json()
    assert r["ui"][0]["type"] == "scan" and r["ui"][0]["balance"]["options"][0]["recommended"]
    scripted(monkeypatch, ("propose_plan", {"epochs": 5}), "Here is the plan.")
    r = c.post(f"/projects/{pid}/agent", json={"message": "ok plan it"}).json()
    assert r["state"]["plan"]["needs_decision"] is True
    assert c.post(f"/projects/{pid}/approve").status_code == 409          # cannot approve before choosing
    c.post(f"/projects/{pid}/choice", json={"option_id": "balance_auto"})
    assert c.get(f"/projects/{pid}").json()["state"]["plan"]["needs_decision"] is False


def test_agent_cannot_train_in_plan_mode(tmp_path, monkeypatch):
    c = TestClient(app); pid = c.post("/projects", json={}).json()["id"]
    scripted(monkeypatch, ("start_training", {}), "ok")
    r = c.post(f"/projects/{pid}/agent", json={"message": "train now", "mode": "plan"}).json()
    assert r["ui"] == [] and not r["state"].get("job_id")


def test_autopilot_hides_balance_but_logs_it(tmp_path, monkeypatch):
    c = TestClient(app); c.put("/settings", json={"autopilot": True})
    pid = c.post("/projects", json={}).json()["id"]
    scripted(monkeypatch, ("scan_folder", {"path": make(tmp_path, 60, 100)}), "Done.")
    r = c.post(f"/projects/{pid}/agent", json={"message": "x"}).json()
    assert r["ui"][0]["balance"] is None and r["state"]["balance_choice"] == "balance_auto"
    assert r["state"]["decisions"][0]["by"] == "autopilot"


def test_autopilot_still_asks_when_severe(tmp_path, monkeypatch):
    c = TestClient(app); c.put("/settings", json={"autopilot": True})
    pid = c.post("/projects", json={}).json()["id"]
    scripted(monkeypatch, ("scan_folder", {"path": make(tmp_path, 5, 100)}), "Done.")
    r = c.post(f"/projects/{pid}/agent", json={"message": "x"}).json()
    assert r["ui"][0]["balance"]["severity"] == "severe" and r["state"]["balance_choice"] is None


def test_full_job_state_machine_with_fake_trainer(tmp_path, monkeypatch):
    class DL(list): pass
    monkeypatch.setattr(training, "get_device", lambda n: n)
    monkeypatch.setattr(training, "build_loaders", lambda cfg: (DL([1, 2]), DL([1]), ["cats", "dogs"]))
    monkeypatch.setattr(training, "make_model", lambda cfg, n, d: object())
    monkeypatch.setattr(training, "benchmark", lambda *a, **k: 0.01)
    monkeypatch.setattr(training, "train", lambda job, *a, **k: {"overall": 0.9, "per_class": {"cats": 0.85, "dogs": 0.95}})
    c = TestClient(app); pid = c.post("/projects", json={}).json()["id"]
    data = make(tmp_path, 30, 50)
    scripted(monkeypatch, ("scan_folder", {"path": data}), "ok", ("propose_plan", {}), "plan")
    c.post(f"/projects/{pid}/agent", json={"message": "a"}); c.post(f"/projects/{pid}/agent", json={"message": "b"})
    c.post(f"/projects/{pid}/choice", json={"option_id": "balance_auto"})
    job = c.post(f"/projects/{pid}/approve").json()["job"]
    for _ in range(50):
        v = c.get(f"/jobs/{job['id']}").json()
        if v["status"] in ("done", "failed"): break
        time.sleep(0.1)
    assert v["status"] == "done", v
    files = c.get(f"/projects/{pid}/runs/{v['result']['run_id']}/files").json()
    assert "balance_choice: balance_auto" in files["config.yaml"] and "train.py" in files
    assert c.get(f"/projects/{pid}/runs").json()[0]["metrics"]["overall"] == 0.9


BRIEF = {"goal": "Tell my cats from my dogs", "task": "whole", "categories": "cats, dogs, birds", "count": "over_10000",
         "priority": "best", "usage": "phone", "sorted": "unsorted"}


def test_project_with_brief_dashboard_kickoff_delete(tmp_path):
    c = TestClient(app)
    pid = c.post("/projects", json={"name": "Pets", "brief": BRIEF}).json()["id"]
    card = c.get("/projects").json()[0]
    assert card["name"] == "Pets" and card["goal"].startswith("Tell my cats") and card["stage"] == "new"
    chat = c.post(f"/projects/{pid}/kickoff").json()
    assert len(chat) == 1 and "Thanks, I read your answers" in chat[0]["content"] and "Tell my cats from my dogs" in chat[0]["content"]
    assert len(c.post(f"/projects/{pid}/kickoff").json()) == 1              # idempotent
    assert c.delete(f"/projects/{pid}").json()["ok"] and c.get("/projects").json() == []


def test_scan_compares_with_questionnaire_and_plan_uses_priorities(tmp_path, monkeypatch):
    c = TestClient(app)
    pid = c.post("/projects", json={"name": "Pets", "brief": BRIEF}).json()["id"]
    scripted(monkeypatch, ("scan_folder", {"path": make(tmp_path, 40, 40)}), ("propose_plan", {}), "ok")
    r = c.post(f"/projects/{pid}/agent", json={"message": "path"}).json()
    notes = r["ui"][0]["notes"]
    assert any("birds" in n and "did not find" in n for n in notes) and any("expected about over 10,000" in n for n in notes)
    plan = r["ui"][1]["plan"]
    assert plan["model"] == "mobilenet_v3_large" and plan["epochs"] == 20          # phone use, 'best' priority
    assert c.get("/projects").json()[0]["stage"] == "planned"
