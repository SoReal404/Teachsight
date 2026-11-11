from PIL import Image
from fastapi.testclient import TestClient
from app.main import app
from app import dataset


def make(tmp_path, cats, dogs):
    for name, n in (("cats", cats), ("dogs", dogs)):
        d = tmp_path / name; d.mkdir()
        for i in range(n):
            Image.new("RGB", (32, 32), (i * 3 % 255, (i * 7) % 255, 100 if name == "cats" else 200)).save(d / f"{i}.png")
    return tmp_path


def test_scan_and_mild_imbalance(tmp_path):
    r = dataset.scan_folder(str(make(tmp_path, 30, 50)))
    assert r["ok"] and r["suggested_task"] == "binary" and r["counts"] == {"cats": 30, "dogs": 50}
    b = dataset.analyze_balance(r["counts"])
    assert b["severity"] == "mild" and b["size_severity"] == "low" and len(b["options"]) == 3


def test_severity_levels():
    assert dataset.analyze_balance({"a": 100, "b": 100})["severity"] == "ok"
    assert dataset.analyze_balance({"a": 100, "b": 20})["severity"] == "warning"
    assert dataset.analyze_balance({"a": 500, "b": 10})["severity"] == "severe"


def test_broken_and_missing(tmp_path):
    make(tmp_path, 3, 3)
    (tmp_path / "cats" / "bad.jpg").write_bytes(b"not an image")
    assert dataset.scan_folder(str(tmp_path))["broken_count"] == 1
    assert dataset.scan_folder(str(tmp_path / "nope"))["error"] == "folder_not_found"


def test_api(tmp_path):
    c = TestClient(app)
    assert c.get("/health").json()["ok"]
    assert "recommended" in c.get("/hardware").json()
    assert c.post("/scan", json={"path": str(make(tmp_path, 5, 5))}).json()["balance"]["severity"] == "ok"


def test_job_pauses_and_asks_then_cancels(tmp_path):
    import time
    c = TestClient(app)
    j = c.post("/jobs", json={"data_dir": str(make(tmp_path, 30, 50))}).json()
    for _ in range(50):
        v = c.get(f"/jobs/{j['id']}").json()
        if v["status"] == "asking":
            break
        time.sleep(0.1)
    assert v["status"] == "asking" and len(v["question"]["options"]) == 3
    c.post(f"/jobs/{j['id']}/answer", json={"answer": "add_more"})
    time.sleep(0.5)
    assert c.get(f"/jobs/{j['id']}").json()["status"] == "cancelled"
