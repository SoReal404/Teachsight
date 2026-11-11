import base64, io, json, uuid
from pathlib import Path
import yaml
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from . import agent, dataset, flow, hardware, improve, predict, projects, providers, runner, settings
from .jobs import JOBS

app = FastAPI(title="NoCode CV engine")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class PathIn(BaseModel): path: str
class JobIn(BaseModel):
    data_dir: str
    epochs: int = 10
    balance_choice: str | None = None
class AnswerIn(BaseModel): answer: str
class ProjectIn(BaseModel):
    name: str = "New project"
    brief: dict | None = None
class MsgIn(BaseModel):
    message: str
    mode: str = "plan"
class ChoiceIn(BaseModel): option_id: str
class DataIn(BaseModel): path: str
class RolesIn(BaseModel): roles: dict[str, str]
class ImageIn(BaseModel): image_b64: str
class CorrectIn(BaseModel):
    image_b64: str
    label: str
class ImproveIn(BaseModel): action: str
class KeyIn(BaseModel): key: str
class ProviderKeyIn(BaseModel):
    provider: str
    key: str
class ProviderIn(BaseModel):
    provider: str
    model: str | None = None
    base_url: str | None = None
class TestKeyIn(BaseModel):
    provider: str
    key: str | None = None
    base_url: str | None = None
    model: str | None = None
class RerunIn(BaseModel): config_yaml: str
class SettingsIn(BaseModel):
    ai_mode: str | None = None
    model: str | None = None
    provider: str | None = None
    provider_model: str | None = None
    custom_base_url: str | None = None
    spend_cap_usd: float | None = None
    proxy_url: str | None = None
    license_key: str | None = None
    send_thumbnails: bool | None = None
    autopilot: bool | None = None
    notifications: bool | None = None


@app.get("/health")
def health(): return {"ok": True}


@app.get("/hardware")
def hw(): return hardware.probe()


@app.post("/scan")
def scan(body: PathIn):
    res = dataset.scan_folder(body.path)
    res["balance"] = dataset.analyze_balance(res["counts"]) if res.get("counts") else None
    return res


# ---- settings (the API key is write-only) ----
@app.get("/settings")
def get_settings():
    s = settings.load()
    s["has_api_key"] = bool(settings.get_api_key())
    s["active_provider"] = settings.active_provider()
    s["providers"] = providers.list_providers()
    return s


@app.put("/settings")
def put_settings(body: SettingsIn):
    s = settings.save(body.model_dump(exclude_none=True)); s["has_api_key"] = bool(settings.get_api_key())
    s["active_provider"] = settings.active_provider(); s["providers"] = providers.list_providers()
    return s


@app.put("/settings/api-key")
def put_key(body: KeyIn):
    """Kept for the OpenRouter key (the old single-key route)."""
    if not body.key.strip(): raise HTTPException(400, "Empty key")
    try: providers.set_key("openrouter", body.key)
    except Exception as e: raise HTTPException(500, f"Could not store the key in the Windows keychain: {e}")
    return {"has_api_key": True, "providers": providers.list_providers()}


@app.delete("/settings/api-key")
def del_key():
    providers.delete_key("openrouter")
    return {"has_api_key": bool(settings.get_api_key()), "providers": providers.list_providers()}


@app.put("/settings/provider-key")
def put_provider_key(body: ProviderKeyIn):
    """Stores the key for one AI provider in the Windows keychain (never as plain text)."""
    if body.provider not in providers.PROVIDERS: raise HTTPException(400, "Unknown AI provider.")
    if not body.key.strip(): raise HTTPException(400, "Empty key")
    try: providers.set_key(body.provider, body.key)
    except Exception as e: raise HTTPException(500, f"Could not store the key in the Windows keychain: {e}")
    return {"ok": True, "providers": providers.list_providers()}


@app.delete("/settings/provider-key")
def del_provider_key(provider: str):
    if provider not in providers.PROVIDERS: raise HTTPException(400, "Unknown AI provider.")
    providers.delete_key(provider)
    return {"ok": True, "providers": providers.list_providers()}


@app.post("/settings/test-key")
def test_provider_key(body: TestKeyIn):
    """Checks a provider key with one tiny real call and returns a plain-language answer."""
    if body.provider not in providers.PROVIDERS: raise HTTPException(400, "Unknown AI provider.")
    s = settings.load()
    base = body.base_url if body.base_url is not None else (s.get("custom_base_url") or None)
    model = body.model or (s.get("provider_model") if s.get("provider") == body.provider else None)
    return providers.test_key(body.provider, body.key, base, model)


# ---- projects and chat ----
def _p(pid: str):
    if not projects.exists(pid): raise HTTPException(404, "project not found")


@app.get("/projects")
def list_projects():
    """Dashboard cards: each project with its stage and best accuracy so far."""
    out = []
    for m in projects.list_projects():
        st, acc = projects.load(m["id"], "state"), projects.best_accuracy(m["id"])
        stage = st.get("stage", "new")
        if stage == "training" and acc is None and st.get("job_id") not in JOBS: stage = "planned"
        out.append({**m, "type": (st.get("brief") or {}).get("type"), "stage": "trained" if acc is not None else stage, "best_accuracy": acc})
    return out


@app.post("/projects")
def new_project(body: ProjectIn): return projects.create(body.name, body.brief)


@app.post("/projects/sample")
def sample_project():
    return projects.create_sample_project()


@app.delete("/projects/{pid}")
def remove_project(pid: str):
    _p(pid); projects.delete(pid); return {"ok": True}


@app.post("/projects/{pid}/kickoff")
def kickoff(pid: str):
    """Adds the first assistant message (from the questionnaire) if the chat is empty."""
    _p(pid); chat = projects.load(pid, "chat")
    if not chat:
        brief = projects.load(pid, "state").get("brief") or {}
        chat.append({"role": "assistant", "content": agent.kickoff_text(brief), "ui": []}); projects.save(pid, "chat", chat)
    return chat


@app.get("/projects/{pid}")
def get_project(pid: str):
    _p(pid); return {"meta": projects.load(pid, "project"), "chat": projects.load(pid, "chat"), "state": projects.load(pid, "state")}


@app.post("/projects/{pid}/agent")
def talk(pid: str, body: MsgIn):
    _p(pid)
    try: return agent.run_turn(pid, body.message, body.mode if body.mode in ("plan", "code") else "plan")
    except agent.AgentError as e: raise HTTPException(400, {"code": e.code, "message": e.message})


@app.post("/projects/{pid}/choice")
def choose(pid: str, body: ChoiceIn):
    _p(pid); st = projects.load(pid, "state")
    st["balance_choice"] = body.option_id
    st.setdefault("decisions", []).append({"what": "balance", "choice": body.option_id, "by": "user"})
    if st.get("plan"): st["plan"].update(balance_choice=body.option_id, needs_decision=False)
    projects.save(pid, "state", st); return st


@app.post("/projects/{pid}/pretrained")
def use_pretrained(pid: str):
    """Lets someone start without any pictures of their own: it uses a ready-made model that already knows everyday objects."""
    _p(pid); st = projects.load(pid, "state")
    brief = st.get("brief") or {}
    task = "detection" if brief.get("type") == "detection" else "classification"
    labels = predict.pretrained_labels(task)
    run_dir = projects.runs_dir(pid) / "pretrained"
    run_dir.mkdir(parents=True, exist_ok=True)
    model_name = "ssdlite320_mobilenet_v3" if task == "detection" else "resnet18"
    cfg = {"task": task, "pretrained": True, "model": model_name,
           "image_size": 320 if task == "detection" else 224,
           "labels": labels, "source": "ready-made model"}
    (run_dir / "config.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    (run_dir / "labels.json").write_text(json.dumps(labels, indent=2), encoding="utf-8")
    (run_dir / "pretrained.json").write_text(json.dumps({"task": task, "model": model_name}, indent=2), encoding="utf-8")
    (run_dir / "report.json").write_text(json.dumps({"metrics": {}, "pretrained": True,
                                                     "decisions": [{"what": "model", "choice": "ready-made", "by": "user"}]}, indent=2), encoding="utf-8")
    st.update(stage="ready", pretrained=True, pretrained_task=task)
    projects.save(pid, "state", st)
    return {"run_id": "pretrained", "task": task, "labels": labels[:12], "state": st}


@app.post("/projects/{pid}/approve")
def approve(pid: str):
    """Step 7 of the pre-flight check: only the user can approve. Approving switches to Code mode and starts."""
    _p(pid); st = projects.load(pid, "state"); plan = st.get("plan")
    if not plan: raise HTTPException(409, "There is no plan to approve yet.")
    if plan.get("needs_decision"): raise HTTPException(409, "Please choose how to handle the unbalanced pictures first.")
    st.update(approved=True, mode="code", stage="training")
    job = runner.start({"project_id": pid, "data_dir": st["data_dir"], "epochs": plan["epochs"], "model": plan.get("model", "resnet18"),
                        "task": plan.get("task"), "balance_choice": plan["balance_choice"],
                        "decisions": st.get("decisions", []), "roles": st.get("roles")})
    st["job_id"] = job.id; projects.save(pid, "state", st)
    return {"job": job.view(), "state": st}


# ---- guided flow (no chat needed) ----
def _bad(code: str, message: str): raise HTTPException(400, {"code": code, "message": message})


@app.post("/projects/{pid}/data")
def set_data(pid: str, body: DataIn):
    _p(pid); st = projects.load(pid, "state"); r = flow.ingest(st, body.path)
    if not r["ok"]: _bad("bad_folder", r["problem"])
    projects.save(pid, "state", st); return st


@app.put("/projects/{pid}/roles")
def set_roles(pid: str, body: RolesIn):
    _p(pid); st = projects.load(pid, "state")
    if not st.get("scan"): _bad("no_data", "Choose your folder first.")
    flow.set_roles(st, body.roles); projects.save(pid, "state", st); return st


@app.post("/projects/{pid}/confirm")
def confirm_data(pid: str):
    _p(pid); st = projects.load(pid, "state")
    if not st.get("resolved") or st["resolved"]["problems"]: _bad("problems", (st.get("resolved") or {"problems": ["Choose your folder first."]})["problems"][0])
    st["data_confirmed"], st["stage"] = True, "checked"
    if not flow.autopilot(st, settings.load()["autopilot"]) and not (st.get("balance") or {}).get("options"):
        st["balance_choice"] = "continue"                 # nothing to decide: balanced data
    projects.save(pid, "state", st); return st


@app.post("/projects/{pid}/plan")
def make_plan(pid: str):
    _p(pid); st = projects.load(pid, "state")
    if not st.get("data_confirmed") or not st.get("balance_choice"): _bad("not_ready", "Finish the data check first.")
    if st["balance_choice"] == "add_more": _bad("not_ready", "Add your pictures, then check your data again.")
    st["plan"] = flow.make_plan(st, None); st["stage"] = "planned"
    projects.save(pid, "state", st); return st


@app.get("/projects/{pid}/thumb")
def thumb(pid: str, path: str, size: int = 96):
    _p(pid); root = (projects.load(pid, "state").get("data_dir") or "")
    p = Path(path).resolve()
    if not root or not p.is_relative_to(Path(root).resolve()) or p.suffix.lower() not in dataset.IMG_EXT or not p.is_file(): raise HTTPException(404, "not found")
    from PIL import Image
    with Image.open(p) as im:
        im = im.convert("RGB"); im.thumbnail((max(16, min(size, 400)),) * 2)
        buf = io.BytesIO(); im.save(buf, "JPEG", quality=80)
    return Response(buf.getvalue(), media_type="image/jpeg", headers={"Cache-Control": "max-age=3600"})


@app.post("/projects/{pid}/predict")
def predict_image(pid: str, body: ImageIn):
    _p(pid); run = predict.latest_run(projects.runs_dir(pid))
    if not run: _bad("no_model", "Train a model first.")
    try: return {"run_id": run.name, "predictions": predict.predict(run, base64.b64decode(body.image_b64.split(",")[-1]))}
    except Exception as e: _bad("predict_failed", f"I could not read that picture: {e}")


@app.post("/projects/{pid}/correct")
def correct(pid: str, body: CorrectIn):
    """'That's wrong': the user saw the picture and chose its category. Saved for the next improvement round."""
    _p(pid)
    if not body.label.replace("_", "").replace("-", "").replace(" ", "").isalnum(): _bad("bad_label", "Unknown category.")
    d = projects.root() / pid / "corrections" / body.label; d.mkdir(parents=True, exist_ok=True)
    (d / f"{uuid.uuid4().hex[:8]}.jpg").write_bytes(base64.b64decode(body.image_b64.split(",")[-1]))
    return {"saved": sum(1 for _ in (projects.root() / pid / "corrections").rglob("*.jpg"))}


def _last_run(pid: str):
    runs = sorted((d for d in projects.runs_dir(pid).iterdir() if (d / "report.json").is_file()), key=lambda d: d.stat().st_mtime)
    return runs[-1] if runs else None


@app.get("/projects/{pid}/diagnosis")
def diagnosis(pid: str):
    _p(pid); run = _last_run(pid)
    if not run: return {}
    rep, cfg = yaml.safe_load((run / "report.json").read_text(encoding="utf-8")), yaml.safe_load((run / "config.yaml").read_text(encoding="utf-8"))
    return improve.diagnose(rep["metrics"], cfg, (projects.load(pid, "state").get("resolved") or {}).get("counts") or {})


@app.post("/projects/{pid}/improve")
def improve_run(pid: str, body: ImproveIn):
    _p(pid); run = _last_run(pid)
    if not run: _bad("no_run", "Train a model first.")
    try: cfg = improve.apply(body.action, yaml.safe_load((run / "config.yaml").read_text(encoding="utf-8")))
    except ValueError: _bad("bad_action", "Unknown improvement.")
    job = runner.start({"project_id": pid, "data_dir": cfg["data_dir"], "epochs": cfg["epochs"], "balance_choice": cfg["balance_choice"], "config": cfg})
    st = projects.load(pid, "state"); st.update(job_id=job.id, stage="training"); projects.save(pid, "state", st)
    return job.view()


# ---- Advanced mode: run files, config as the single source of truth ----
@app.get("/projects/{pid}/runs")
def list_runs(pid: str):
    _p(pid); out = []
    for d in sorted(projects.runs_dir(pid).iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        rep = d / "report.json"
        out.append({"id": d.name, "has_config": (d / "config.yaml").is_file(),
                    "metrics": yaml.safe_load(rep.read_text(encoding="utf-8")).get("metrics") if rep.is_file() else None})
    return out


@app.get("/projects/{pid}/runs/{rid}/files")
def run_files(pid: str, rid: str):
    _p(pid); d = projects.runs_dir(pid) / rid
    if not rid.isalnum() or not d.is_dir(): raise HTTPException(404, "run not found")
    from . import codegen
    codegen.ensure_export_bundle(d)
    allowed = ("config.yaml", "train.py", "predict.py", "serve.py", "README.md", "labels.json", "requirements.txt")
    return {n: (d / n).read_text(encoding="utf-8") for n in allowed if (d / n).is_file()}


@app.post("/projects/{pid}/runs/{rid}/rerun")
def rerun(pid: str, rid: str, body: RerunIn):
    _p(pid)
    try: cfg = yaml.safe_load(body.config_yaml)
    except yaml.YAMLError as e: raise HTTPException(400, f"The settings text is not valid: {e}")
    need = {"data_dir", "model", "epochs", "image_size", "batch_size", "learning_rate", "optimizer", "balance_choice", "val_split", "seed", "device"}
    if not isinstance(cfg, dict) or need - cfg.keys(): raise HTTPException(400, f"Missing settings: {sorted(need - set(cfg or {}))}")
    job = runner.start({"project_id": pid, "data_dir": cfg["data_dir"], "epochs": cfg["epochs"], "balance_choice": cfg["balance_choice"], "config": cfg})
    return job.view()


@app.get("/projects/{pid}/model-info")
def model_info(pid: str):
    _p(pid)
    latest = projects.latest_run_dir(pid)
    if not latest:
        return {"has_model": False}
    files = [f.name for f in latest.iterdir() if f.is_file()]
    rep = {}
    if (latest / "report.json").is_file():
        try: rep = yaml.safe_load((latest / "report.json").read_text(encoding="utf-8"))
        except Exception: pass
    cfg = {}
    if (latest / "config.yaml").is_file():
        try: cfg = yaml.safe_load((latest / "config.yaml").read_text(encoding="utf-8"))
        except Exception: pass
    return {
        "has_model": True,
        "run_id": latest.name,
        "path": str(latest.resolve()),
        "files": sorted(files),
        "metrics": rep.get("metrics"),
        "config": cfg,
    }


@app.post("/projects/{pid}/open-folder")
def open_folder(pid: str):
    _p(pid)
    latest = projects.latest_run_dir(pid)
    target = latest if latest else projects.runs_dir(pid)
    ok = projects.open_folder(target)
    return {"opened": ok, "path": str(target.resolve())}


@app.get("/projects/{pid}/export-zip")
def export_zip(pid: str, rid: str | None = None):
    _p(pid)
    import zipfile
    run_dir = (projects.runs_dir(pid) / rid) if rid else projects.latest_run_dir(pid)
    if not run_dir or not run_dir.is_dir():
        raise HTTPException(404, "Run folder not found")
    from . import codegen
    codegen.ensure_export_bundle(run_dir)
    
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in run_dir.iterdir():
            if f.is_file():
                zf.write(f, arcname=f.name)
    buf.seek(0)
    return Response(
        buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=model_{pid}_{run_dir.name}.zip"}
    )


# ---- jobs ----
@app.post("/jobs")
def create_job(body: JobIn): return runner.start(body.model_dump(exclude_none=True)).view()


def _job(job_id: str):
    if job_id not in JOBS: raise HTTPException(404, "job not found")
    return JOBS[job_id]


@app.get("/jobs/{job_id}")
def get_job(job_id: str): return _job(job_id).view()


@app.post("/jobs/{job_id}/answer")
def answer(job_id: str, body: AnswerIn):
    _job(job_id).answer(body.answer); return {"ok": True}


@app.post("/jobs/{job_id}/{action}")
def control(job_id: str, action: str):
    j = _job(job_id)
    if action not in ("pause", "resume", "cancel"): raise HTTPException(400, "unknown action")
    getattr(j, action)(); return j.view()
