"""Projects = local folders (spec section 12): project.json, chat.json, state.json, runs/."""
from __future__ import annotations
import json, time, uuid
from pathlib import Path
from . import settings


def root() -> Path:
    p = settings.app_dir() / "projects"; p.mkdir(parents=True, exist_ok=True)
    return p


def exists(pid: str) -> bool:
    return pid.isalnum() and (root() / pid).is_dir()


def _w(path: Path, data):
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def create(name: str = "New project", brief: dict | None = None) -> dict:
    brief = brief or {}
    pid = uuid.uuid4().hex[:8]; d = root() / pid; (d / "runs").mkdir(parents=True)
    meta = {"id": pid, "name": name or "New project", "goal": (brief.get("goal") or "")[:160], "created": time.time(), "updated": time.time()}
    _w(d / "project.json", meta); _w(d / "chat.json", []); _w(d / "state.json", {"mode": "plan", "brief": brief, "stage": "new"})
    return meta


def best_accuracy(pid: str):
    best = None
    for rep in runs_dir(pid).glob("*/report.json"):
        try: v = json.loads(rep.read_text(encoding="utf-8"))["metrics"]["overall"]
        except Exception: continue
        best = v if best is None else max(best, v)
    return best


def delete(pid: str):
    import shutil
    shutil.rmtree(root() / pid)


def list_projects() -> list[dict]:
    out = [json.loads((d / "project.json").read_text(encoding="utf-8")) for d in root().iterdir() if (d / "project.json").is_file()]
    return sorted(out, key=lambda m: m["updated"], reverse=True)


def load(pid: str, what: str):
    return json.loads((root() / pid / f"{what}.json").read_text(encoding="utf-8"))


def save(pid: str, what: str, data):
    _w(root() / pid / f"{what}.json", data)
    meta = load(pid, "project"); meta["updated"] = time.time(); _w(root() / pid / "project.json", meta)


def rename(pid: str, name: str):
    meta = load(pid, "project"); meta["name"] = name; _w(root() / pid / "project.json", meta)


def runs_dir(pid: str) -> Path:
    return root() / pid / "runs"


def latest_run_dir(pid: str) -> Path | None:
    from . import codegen
    r_dir = runs_dir(pid)
    if not r_dir.is_dir():
        return None
    runs = [d for d in r_dir.iterdir() if d.is_dir() and ((d / "best.pt").is_file() or (d / "pretrained.json").is_file())]
    if not runs:
        return None
    latest = max(runs, key=lambda d: d.stat().st_mtime)
    codegen.ensure_export_bundle(latest)
    return latest


def open_folder(path: Path | str) -> bool:
    import os, subprocess
    p = str(Path(path).resolve())
    if os.name == "nt":
        subprocess.Popen(["explorer.exe", p])
        return True
    return False


def create_sample_project() -> dict:
    from PIL import Image, ImageDraw
    import random
    from . import flow

    sample_dir = settings.app_dir() / "sample_datasets" / "shapes"
    c_dir, s_dir = sample_dir / "circles", sample_dir / "squares"
    c_dir.mkdir(parents=True, exist_ok=True)
    s_dir.mkdir(parents=True, exist_ok=True)

    rng = random.Random(42)
    # Generate 25 circles and 25 squares if not already generated
    if len(list(c_dir.glob("*.png"))) < 20:
        for i in range(25):
            im = Image.new("RGB", (128, 128), color=(20, 24, 28))
            draw = ImageDraw.Draw(im)
            r = rng.randint(20, 45)
            x, y = rng.randint(r + 5, 128 - r - 5), rng.randint(r + 5, 128 - r - 5)
            col = (rng.randint(70, 255), rng.randint(180, 255), rng.randint(180, 255))
            draw.ellipse([x - r, y - r, x + r, y + r], fill=col)
            im.save(c_dir / f"circle_{i+1:02d}.png")

    if len(list(s_dir.glob("*.png"))) < 20:
        for i in range(25):
            im = Image.new("RGB", (128, 128), color=(20, 24, 28))
            draw = ImageDraw.Draw(im)
            w = rng.randint(25, 55)
            x, y = rng.randint(10, 128 - w - 10), rng.randint(10, 128 - w - 10)
            col = (rng.randint(200, 255), rng.randint(100, 200), rng.randint(70, 150))
            draw.rectangle([x, y, x + w, y + w], fill=col)
            im.save(s_dir / f"square_{i+1:02d}.png")

    meta = create("Sample Demo: Shapes", {
        "name": "Sample Demo: Shapes",
        "type": "classification",
        "goal": "Quick sample project (clearly identified as demo data) to test local training on your PC.",
        "categories": "circles, squares",
        "count": "under_100",
        "priority": "fast",
    })
    
    st = load(meta["id"], "state")
    flow.ingest(st, str(sample_dir))
    flow.make_plan(st, 5)
    st["stage"] = "planned"
    st["data_confirmed"] = True
    save(meta["id"], "state", st)
    return meta


