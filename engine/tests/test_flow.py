import base64, io, time
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from app import dataset, flow, predict, training
from app.main import app


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("NOCODECV_HOME", str(tmp_path / "home"))


def img(path, color):
    path.parent.mkdir(parents=True, exist_ok=True); Image.new("RGB", (24, 24), color).save(path)


def kaggle(tmp_path, dup=False):
    """training_set/{cats,dogs}, test_set/{cats,dogs}, single_prediction/ (loose pictures): the layout from the screenshot."""
    root = tmp_path / "Pets"
    for split, n in (("training_set", 6), ("test_set", 3)):
        for ci, c in enumerate(("cats", "dogs")):
            for i in range(n + (6 if (split == "training_set" and c == "dogs") else 0)):
                img(root / split / c / f"{i}.png", (i * 9 + ci * 90, 10 + len(split), 40 + 20 * ci + i % 7))
    img(root / "single_prediction" / "cat_or_dog_1.png", (1, 2, 3)); img(root / "single_prediction" / "cat_or_dog_2.png", (3, 2, 1))
    if dup:
        (root / "test_set" / "cats" / "copy.png").write_bytes((root / "training_set" / "cats" / "0.png").read_bytes())
    return root


def test_split_layout_is_detected_not_treated_as_categories(tmp_path):
    s = dataset.scan_folder(str(kaggle(tmp_path)))
    assert s["layout"] == "split_folders"
    assert {f["name"]: f["role"] for f in s["folders"]} == {"single_prediction": "ignore", "test_set": "test", "training_set": "train"}
    r = dataset.resolve(s)
    assert r["labels"] == ["cats", "dogs"] and r["counts"] == {"cats": 6, "dogs": 12} and r["total_test"] == 6 and r["problems"] == []
    assert r["train_dir"].endswith("training_set") and r["test_dir"].endswith("test_set")


def test_cross_split_duplicates_and_extras_notes(tmp_path):
    st = {}
    assert flow.ingest(st, f'"{kaggle(tmp_path, dup=True)}"')["ok"]          # quotes from Windows "Copy as path" are stripped
    assert any("appear in both" in n for n in st["notes"]) and any("single_prediction" in n and "ignore" in n for n in st["notes"])


def test_role_changes_and_problems(tmp_path):
    st = {}; flow.ingest(st, str(kaggle(tmp_path)))
    flow.set_roles(st, {"test_set": "ignore"}); assert st["resolved"]["test_dir"] is None and st["resolved"]["problems"] == []
    flow.set_roles(st, {"single_prediction": "train"}); assert any("exactly one" in p for p in st["resolved"]["problems"])
    flow.set_roles(st, {"training_set": "test", "test_set": "train"}); assert st["resolved"]["problems"] == []      # swapped, still valid


def test_guided_api_flow_to_plan_and_thumbnail(tmp_path):
    c = TestClient(app); pid = c.post("/projects", json={"name": "Pets", "brief": {"priority": "fast"}}).json()["id"]
    assert c.post(f"/projects/{pid}/data", json={"path": str(tmp_path / "nope")}).status_code == 400
    st = c.post(f"/projects/{pid}/data", json={"path": str(kaggle(tmp_path))}).json()
    assert st["resolved"]["labels"] == ["cats", "dogs"] and st["balance"]["severity"] == "mild" and not st["data_confirmed"]
    assert c.post(f"/projects/{pid}/plan").status_code == 400                     # cannot plan before confirming
    st = c.post(f"/projects/{pid}/confirm").json()
    assert st["data_confirmed"] and st["balance_choice"] is None                  # mild imbalance: user must choose
    c.post(f"/projects/{pid}/choice", json={"option_id": "balance_auto"})
    plan = c.post(f"/projects/{pid}/plan").json()["plan"]
    assert plan["epochs"] == 5 and plan["exam_images"] == 6 and plan["balance_choice"] == "balance_auto"
    sample = st["resolved"]["folders"][0]
    path = next(iter(sample["samples"].values()))[0] if sample["samples"] else sample["loose_samples"][0]
    r = c.get(f"/projects/{pid}/thumb", params={"path": path, "size": 48}); assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"
    assert c.get(f"/projects/{pid}/thumb", params={"path": str(tmp_path / "home" / "settings.json")}).status_code == 404   # outside the data folder


def test_balanced_data_needs_no_decision(tmp_path):
    c = TestClient(app); pid = c.post("/projects", json={"name": "x", "brief": {}}).json()["id"]
    for n in ("a", "b"):
        for i in range(100): img(tmp_path / "d" / n / f"{i}.png", (i * 2, 5, 5 if n == "a" else 99))
    c.post(f"/projects/{pid}/data", json={"path": str(tmp_path / "d")})
    st = c.post(f"/projects/{pid}/confirm").json(); assert st["balance_choice"] == "continue"


def test_exam_training_predict_correct_and_improve(tmp_path, monkeypatch):
    class DL(list): pass
    monkeypatch.setattr(training, "get_device", lambda n: n)
    monkeypatch.setattr(training, "build_loaders", lambda cfg: (DL([1, 2]), DL([1]), ["cats", "dogs"]))
    monkeypatch.setattr(training, "build_test_loader", lambda cfg, classes: DL([1]))
    monkeypatch.setattr(training, "make_model", lambda cfg, n, d, pretrained=True: object())
    monkeypatch.setattr(training, "benchmark", lambda *a, **k: 0.01)
    monkeypatch.setattr(training, "train", lambda job, *a, **k: {"overall": 0.9, "per_class": {"cats": 0.95, "dogs": 0.85}})
    monkeypatch.setattr(training, "evaluate", lambda *a, **k: {"overall": 0.8, "per_class": {"cats": 0.65, "dogs": 0.95}})
    c = TestClient(app); pid = c.post("/projects", json={"name": "Pets", "brief": {}}).json()["id"]
    c.post(f"/projects/{pid}/data", json={"path": str(kaggle(tmp_path))}); c.post(f"/projects/{pid}/confirm")
    c.post(f"/projects/{pid}/choice", json={"option_id": "continue"}); c.post(f"/projects/{pid}/plan")
    def wait(j):
        for _ in range(80):
            v = c.get(f"/jobs/{j}").json()
            if v["status"] in ("done", "failed"): return v
            time.sleep(0.1)
    v = wait(c.post(f"/projects/{pid}/approve").json()["job"]["id"])
    assert v["status"] == "done", v
    m = v["result"]["metrics"]; assert m["source"] == "exam" and m["overall"] == 0.8 and m["validation"]["overall"] == 0.9   # graded on the exam folder
    cfg = c.get(f"/projects/{pid}/runs/{v['result']['run_id']}/files").json()["config.yaml"]
    assert "training_set" in cfg and "test_set" in cfg
    d = c.get(f"/projects/{pid}/diagnosis").json()
    assert d["weakest"] == "cats" and d["source"] == "exam pictures"
    assert any(o["id"] == "add_pictures" for o in d["options"])
    monkeypatch.setattr(predict, "predict", lambda run, b, top=3: [{"label": "dogs", "probability": 0.97}])
    runs_dir = __import__("app.projects", fromlist=["x"]).runs_dir(pid)
    (runs_dir / v["result"]["run_id"] / "best.pt").write_bytes(b"x")      # the fake trainer saves no weights
    b64 = base64.b64encode(b"jpeg").decode()
    assert c.post(f"/projects/{pid}/predict", json={"image_b64": b64}).json()["predictions"][0]["label"] == "dogs"
    assert c.post(f"/projects/{pid}/correct", json={"image_b64": b64, "label": "cats"}).json()["saved"] == 1
    assert c.post(f"/projects/{pid}/correct", json={"image_b64": b64, "label": "../x"}).status_code == 400
    j2 = c.post(f"/projects/{pid}/improve", json={"action": "longer"}).json()
    v2 = wait(j2["id"]); assert v2["status"] == "done"
    assert "epochs: 15" in c.get(f"/projects/{pid}/runs/{v2['result']['run_id']}/files").json()["config.yaml"]    # 10 -> 15
    assert c.post(f"/projects/{pid}/improve", json={"action": "nope"}).status_code == 400
