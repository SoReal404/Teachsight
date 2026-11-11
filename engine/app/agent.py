"""The chat AI (spec 4.3). It plans and explains; the engine executes. Talks to OpenRouter (own key) or our proxy (paid plans)."""
from __future__ import annotations
import json
from pathlib import Path
import httpx
import yaml
from . import codegen, flow, hardware, improve, jobs, predict, projects, providers, runner, settings


class AgentError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message); self.code, self.message = code, message


SYSTEM = """You are the AI assistant inside Teachsight NoCode CV, an interactive desktop app that trains and deploys computer vision models on the user's PC.

OPERATING MODES:
1. PLAN MODE:
   - Focus on planning, dataset advice, architecture selection, and explaining machine learning concepts in plain English.
   - Guide the user through inspecting folders, handling category imbalances, and approving a training plan.
2. CODE MODE (FULL ACCESS & PERMISSIONS):
   - You have FULL ACCESS and PERMISSIONS on everything in the project:
     * Inspect and explain Python training scripts (train.py), inference scripts (predict.py), web server (serve.py), and config (config.yaml).
     * Adjust hyperparameters (learning rate, epochs, batch size, model architecture, optimizer) using update_hyperparameters.
     * Retrain or start training using start_training.
     * Explain model metrics, confusion, per-class accuracy, and run deep diagnosis using get_diagnosis.
     * Provide ready-to-run code snippets for websites (HTML/JS fetch, React, Vue), REST APIs, Node.js, Python, or mobile apps.
     * Provide exact local paths to the trained model and weights, and open the folder in Windows Explorer using open_model_folder.

CRITICAL RULES:
- If CURRENT STATE shows 'trained': true and a 'latest_run' with 'model_export_dir':
  THE MODEL IS ALREADY TRAINED AND READY!
  NEVER claim the model does not exist or that approval is still needed. Immediately inform the user that their model is ready, tell them where it is stored on disk (model_export_dir), and explain how to use best.pt, predict.py, serve.py, and README.md.
- When asked how to integrate with a website:
  Explain that serve.py provides a full REST API with CORS enabled. Running `python serve.py` starts a web server at http://localhost:8000 with a `/predict` endpoint, interactive browser demo, and ready-to-copy JavaScript code.
- If the user asks to open the folder or find the files, call open_model_folder.
- In Code Mode, if the user asks to retrain, change epochs, or improve the model, use update_hyperparameters and start_training.
- Always use plain, friendly, clear language. Do not invent numbers; rely on the tool results and CURRENT STATE.
"""

TOOLS = [
    {"type": "function", "function": {"name": "probe_hardware", "description": "GPU, memory, CPU and disk of this PC.", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "scan_folder", "description": "Inspect an image folder (one sub-folder per category). Also checks balance.",
                                      "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "propose_plan", "description": "Create the training plan card for the user to approve.",
                                      "parameters": {"type": "object", "properties": {"epochs": {"type": "integer", "description": "Training rounds, 5 to 30"}}}}},
    {"type": "function", "function": {"name": "start_training", "description": "Code mode or approved plan: starts training or retraining.",
                                      "parameters": {"type": "object", "properties": {"epochs": {"type": "integer", "description": "Number of epochs to train"}}}}},
    {"type": "function", "function": {"name": "get_job_status", "description": "Progress of the current training job.", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "get_model_export_info", "description": "Get file paths and developer assets for the trained model (best.pt, README.md, predict.py, serve.py, etc.).",
                                      "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "open_model_folder", "description": "Open the folder containing the trained model weights and scripts in Windows File Explorer.",
                                      "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "read_project_code", "description": "Read one of the project files: 'train.py', 'predict.py', 'serve.py', 'config.yaml', 'README.md', 'labels.json', or 'report.json'.",
                                      "parameters": {"type": "object", "properties": {"filename": {"type": "string", "enum": ["train.py", "predict.py", "serve.py", "config.yaml", "README.md", "labels.json", "report.json"]}}, "required": ["filename"]}}},
    {"type": "function", "function": {"name": "update_hyperparameters", "description": "Code mode only: update training settings (epochs, learning_rate, batch_size, model, optimizer).",
                                      "parameters": {"type": "object", "properties": {
                                          "epochs": {"type": "integer"},
                                          "learning_rate": {"type": "number"},
                                          "batch_size": {"type": "integer"},
                                          "model": {"type": "string", "enum": ["resnet18", "resnet50", "mobilenet_v3_large", "efficientnet_b0"]},
                                          "optimizer": {"type": "string", "enum": ["adamw", "sgd"]}
                                      }}}},
    {"type": "function", "function": {"name": "get_diagnosis", "description": "Get deep diagnosis of the trained model, per-class weaknesses, and recommended actions.", "parameters": {"type": "object", "properties": {}}}},
]


def _model_for(provider: str, s: dict) -> str:
    """Which model to use for the active provider. OpenRouter keeps the old settings 'model'."""
    if provider == "openrouter":
        return s.get("model") or providers.PROVIDERS["openrouter"]["default_model"]
    return s.get("provider_model") or providers.PROVIDERS.get(provider, {}).get("default_model", "")


def chat_completion(messages: list[dict]) -> dict:
    s = settings.load()
    if s["ai_mode"] == "account":
        if not (s["proxy_url"] and s["license_key"]):
            raise AgentError("no_account", "Sign in with your license key in Settings first.")
        url, key = s["proxy_url"].rstrip("/") + "/v1/chat/completions", s["license_key"]
        try:
            r = httpx.post(url, headers={"Authorization": f"Bearer {key}", "HTTP-Referer": "https://nocodecv.app", "X-Title": "NoCode CV"},
                           json={"model": s["model"], "messages": messages, "tools": TOOLS, "max_tokens": 1200}, timeout=90)
        except httpx.HTTPError:
            raise AgentError("network", "I can't reach the AI service. Check your internet connection.")
        if r.status_code == 401: raise AgentError("bad_key", "The AI service did not accept the key. Check it in Settings.")
        if r.status_code == 402: raise AgentError("no_credit", "You are out of AI credits.")
        if r.status_code == 429: raise AgentError("rate", "The AI service is busy. Try again in a moment.")
        if r.status_code != 200: raise AgentError("provider", f"The AI service returned an error ({r.status_code}).")
        return r.json()
    provider = settings.active_provider()
    if not providers.get_key(provider):
        others = [p for p in providers.PROVIDERS if p != provider and providers.get_key(p)]
        label = providers.PROVIDERS.get(provider, {}).get("label", provider)
        if others:
            other_label = providers.PROVIDERS[others[0]]["label"]
            raise AgentError("no_key", f"Your {label} key is missing. You already have a {other_label} key saved on this PC — "
                                       f"choose {other_label} in Settings, or add your {label} key.")
        raise AgentError("no_key", f"Add your {label} key in Settings so I can chat.")
    base_url = (s.get("custom_base_url") or None) if provider == "custom" else None
    try:
        return providers.chat_completion(provider, _model_for(provider, s), messages, TOOLS, base_url)
    except providers.ProviderError as e:
        raise AgentError(e.code, e.message)
    except ValueError as e:
        raise AgentError("provider", str(e))


def _llm_state(state: dict) -> dict:
    pid = state.get("_pid", "")
    res, bal = state.get("resolved") or {}, state.get("balance") or {}
    
    # Check runs on disk
    latest_run = None
    runs_summary = []
    if pid and projects.exists(pid):
        latest = projects.latest_run_dir(pid)
        if latest:
            rep_path = latest / "report.json"
            cfg_path = latest / "config.yaml"
            metrics = None
            if rep_path.is_file():
                try: metrics = json.loads(rep_path.read_text(encoding="utf-8")).get("metrics")
                except Exception: pass
            cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) if cfg_path.is_file() else {}
            latest_run = {
                "run_id": latest.name,
                "metrics": metrics,
                "model_export_dir": str(latest.resolve()),
                "model_files": [f.name for f in latest.iterdir() if f.is_file()],
                "config": cfg,
            }
        for d in sorted(projects.runs_dir(pid).iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
            if d.is_dir() and (d / "report.json").is_file():
                try:
                    m = json.loads((d / "report.json").read_text(encoding="utf-8")).get("metrics")
                    runs_summary.append({"id": d.name, "overall_accuracy": m.get("overall") if m else None})
                except Exception: pass

    active_job = None
    if state.get("job_id"):
        j = jobs.JOBS.get(state["job_id"])
        if j: active_job = j.view()

    return {
        "brief": state.get("brief"),
        "mode": state.get("mode", "plan"),
        "stage": state.get("stage"),
        "data_dir": state.get("data_dir"),
        "labels": res.get("labels"),
        "counts": res.get("counts"),
        "exam_folder": bool(res.get("test_dir")),
        "broken_files": (state.get("scan") or {}).get("broken_count"),
        "duplicate_pairs": (state.get("scan") or {}).get("duplicate_count"),
        "notes": state.get("notes"),
        "balance_severity": bal.get("severity"),
        "balance_choice": state.get("balance_choice"),
        "balance_note": state.get("balance_note"),
        "plan": state.get("plan"),
        "approved": state.get("approved", False) or bool(latest_run),
        "trained": bool(latest_run),
        "latest_run": latest_run,
        "runs": runs_summary,
        "active_job": active_job,
    }


def kickoff_text(b: dict) -> str:
    """Opening message for the Ask AI panel (no AI call needed)."""
    goal = (b.get("goal") or "").strip()
    return "Thanks, I read your answers." + (f" You want to: {goal}" if goal else "") + " Ask me anything about your pictures, your model, or deployment to websites."


def _dispatch(state: dict, name: str, args: dict, ui: list) -> dict:
    pid = state.get("_pid", "")
    mode = state.get("mode", "plan")

    if name == "probe_hardware":
        return hardware.probe()

    if name == "scan_folder":
        r = flow.ingest(state, args.get("path", ""))
        if not r["ok"]:
            return {"ok": False, "problem": r["problem"]}
        scan, res, bal = state["scan"], state["resolved"], state["balance"]
        if res["problems"]:
            return {"ok": False, "problem": res["problems"][0]}
        silent = flow.autopilot(state, settings.load()["autopilot"])
        state["stage"] = "checked"
        ui.append({"type": "scan", "scan": scan, "balance": None if silent else bal, "notes": state["notes"], "resolved": res})
        return {"ok": True, "labels": res["labels"], "counts": res["counts"], "suggested_task": scan["suggested_task"], "exam_folder": bool(res["test_dir"]),
                "broken_files": scan["broken_count"], "duplicate_pairs": scan["duplicate_count"], "notes_vs_user_answers": state["notes"],
                "balance": None if silent else {"severity": bal["severity"], "size_severity": bal.get("size_severity"), "message": bal["message"]},
                "note": state["balance_note"]}

    if name == "propose_plan":
        if not state.get("resolved"):
            return {"error": "Scan the folder first."}
        plan = state["plan"] = flow.make_plan(state, args.get("epochs"))
        state["stage"] = "planned"
        ui.append({"type": "plan", "plan": plan})
        return {"plan": plan, "note": "The user must press Approve. You cannot approve for them."}

    if name == "start_training":
        # In Code Mode or if already approved, user can trigger training
        plan = state.get("plan")
        if not plan and pid:
            # Check if there's a previous run config to clone
            latest = projects.latest_run_dir(pid)
            if latest and (latest / "config.yaml").is_file():
                prev_cfg = yaml.safe_load((latest / "config.yaml").read_text(encoding="utf-8"))
                epochs = args.get("epochs") or prev_cfg.get("epochs", 10)
                prev_cfg["epochs"] = epochs
                job = runner.start({"project_id": pid, "data_dir": prev_cfg["data_dir"], "epochs": epochs,
                                    "model": prev_cfg.get("model", "resnet18"), "balance_choice": prev_cfg.get("balance_choice", "continue"), "config": prev_cfg})
                state["job_id"] = job.id
                state["stage"] = "training"
                ui.append({"type": "job", "job_id": job.id})
                return {"started": True, "job_id": job.id, "epochs": epochs}
        if not state.get("data_dir"):
            return {"error": "Cannot start training: no data folder selected yet."}
        epochs = args.get("epochs") or (plan["epochs"] if plan else 10)
        model_name = (plan.get("model") if plan else "resnet18")
        job = runner.start({"project_id": pid, "data_dir": state["data_dir"], "epochs": epochs, "model": model_name,
                            "balance_choice": state.get("balance_choice", "continue"), "decisions": state.get("decisions", []), "roles": state.get("roles")})
        state["job_id"] = job.id
        state["stage"] = "training"
        state["approved"] = True
        ui.append({"type": "job", "job_id": job.id})
        return {"started": True, "job_id": job.id, "epochs": epochs, "model": model_name}

    if name == "get_job_status":
        j = jobs.JOBS.get(state.get("job_id", ""))
        return j.view() if j else {"error": "No active training job."}

    if name == "get_model_export_info":
        if not pid: return {"error": "No project selected."}
        latest = projects.latest_run_dir(pid)
        if not latest: return {"error": "No model trained yet for this project."}
        files = [f.name for f in latest.iterdir() if f.is_file()]
        rep = json.loads((latest / "report.json").read_text(encoding="utf-8")) if (latest / "report.json").is_file() else {}
        cfg = yaml.safe_load((latest / "config.yaml").read_text(encoding="utf-8")) if (latest / "config.yaml").is_file() else {}
        if predict.is_pretrained(latest):
            return {
                "status": "ready_made",
                "run_id": latest.name,
                "export_directory": str(latest.resolve()),
                "files": files,
                "weights": None,
                "task": cfg.get("task"),
                "quick_start": "This project uses a ready-made model that already knows everyday objects. "
                               "Add your own pictures and train to get a model of your own.",
            }
        return {
            "status": "ready",
            "run_id": latest.name,
            "export_directory": str(latest.resolve()),
            "files": files,
            "weights": str((latest / "best.pt").resolve()),
            "metrics": rep.get("metrics"),
            "model_architecture": cfg.get("model"),
            "quick_start": "Run `python serve.py` inside this folder to launch the REST API and web demo at http://localhost:8000.",
            "python_cli": f"python predict.py <path_to_image>"
        }

    if name == "open_model_folder":
        if not pid: return {"error": "No project selected."}
        latest = projects.latest_run_dir(pid)
        if not latest: return {"error": "No trained model folder found."}
        ok = projects.open_folder(latest)
        return {"opened": ok, "path": str(latest.resolve())}

    if name == "read_project_code":
        filename = args.get("filename", "")
        if not pid: return {"error": "No project selected."}
        latest = projects.latest_run_dir(pid)
        if not latest: return {"error": "No run folder found."}
        fpath = latest / filename
        if not fpath.is_file(): return {"error": f"File {filename} not found in model package."}
        content = fpath.read_text(encoding="utf-8")
        return {"filename": filename, "content": content[:6000]}

    if name == "update_hyperparameters":
        if mode != "code":
            return {"error": "Hyperparameter adjustments require Code mode."}
        if not pid: return {"error": "No project selected."}
        latest = projects.latest_run_dir(pid)
        cfg_file = latest / "config.yaml" if latest else None
        cfg = yaml.safe_load(cfg_file.read_text(encoding="utf-8")) if cfg_file and cfg_file.is_file() else {}
        for k in ("epochs", "learning_rate", "batch_size", "model", "optimizer"):
            if k in args and args[k] is not None:
                cfg[k] = args[k]
        if cfg_file:
            cfg_file.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
            codegen.ensure_export_bundle(latest)
        if state.get("plan"):
            if "epochs" in args: state["plan"]["epochs"] = args["epochs"]
            if "model" in args: state["plan"]["model"] = args["model"]
        return {"updated": True, "config": cfg}

    if name == "get_diagnosis":
        if not pid: return {"error": "No project selected."}
        latest = projects.latest_run_dir(pid)
        if not latest or not (latest / "report.json").is_file():
            return {"error": "Train a model first to get diagnostic metrics."}
        rep = yaml.safe_load((latest / "report.json").read_text(encoding="utf-8"))
        cfg = yaml.safe_load((latest / "config.yaml").read_text(encoding="utf-8"))
        res = (state.get("resolved") or {}).get("counts") or {}
        diag = improve.diagnose(rep["metrics"], cfg, res)
        return {"diagnosis": diag}

    return {"error": f"Unknown tool {name}"}


def run_turn(pid: str, user_text: str, mode: str) -> dict:
    chat, state = projects.load(pid, "chat"), projects.load(pid, "state")
    state["mode"], state["_pid"] = mode, pid
    if not chat and projects.load(pid, "project")["name"] == "New project":
        projects.rename(pid, user_text.strip()[:40] or "New project")
    chat.append({"role": "user", "content": user_text, "mode": mode})

    # Ensure export bundle exists if there's any run
    if projects.exists(pid):
        projects.latest_run_dir(pid)

    llm_context = _llm_state(state)
    msgs = [{"role": "system", "content": SYSTEM + "\nCURRENT STATE:\n" + json.dumps(llm_context, default=str)}] + \
           [{"role": m["role"], "content": m["content"]} for m in chat[-20:]]
    ui: list = []
    text = "I got stuck on that one. Could you say it a different way?"
    try:
        for _ in range(6):
            msg = chat_completion(msgs)["choices"][0]["message"]
            calls = msg.get("tool_calls")
            if not calls:
                text = (msg.get("content") or "").strip() or text
                break
            msgs.append(msg)
            for c in calls:
                try: args = json.loads(c["function"].get("arguments") or "{}")
                except json.JSONDecodeError: args = {}
                out = _dispatch(state, c["function"]["name"], args, ui)
                msgs.append({"role": "tool", "tool_call_id": c["id"], "content": json.dumps(out, default=str)[:4000]})
    finally:
        state.pop("_pid", None)
        projects.save(pid, "state", state)
    chat.append({"role": "assistant", "content": text, "ui": ui, "mode": mode})
    projects.save(pid, "chat", chat)
    return {"reply": text, "ui": ui, "state": state}
