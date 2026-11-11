"""Runs one job end to end from one config (also written to config.yaml). Verify first, ask when unsure."""
from __future__ import annotations
import threading, traceback
from pathlib import Path
from . import codegen, dataset, detection, hardware, projects, training
from .jobs import Job, Cancelled, JOBS


def build_config(p: dict, hw: dict, choice: str, res: dict) -> dict:
    rec = hw["recommended"]
    task = res.get("task", "classification")
    default_model = "ssdlite_mobilenet_v3" if task == "detection" else "resnet18"
    cfg = {"task": task, "data_dir": res["train_dir"], "test_dir": res["test_dir"], "val_dir": res["val_dir"],
           "model": p.get("model", default_model), "image_size": rec["image_size"], "batch_size": rec["batch_size"],
           "epochs": p.get("epochs", 10), "learning_rate": 3e-4, "optimizer": "adamw", "balance_choice": choice,
           "val_split": 0.2, "seed": 0, "device": hw["device"]}
    cfg.update(p.get("config") or {})
    cfg["balance_choice"] = choice if "balance_choice" not in (p.get("config") or {}) else cfg["balance_choice"]
    # The pictures decide what can be trained, not the questionnaire.
    cfg["requested_task"] = (p.get("config") or {}).get("task") or p.get("task") or cfg.get("task")
    cfg["task"] = task
    if task == "detection":
        cfg["image_size"] = detection.DET_SIZE
        cfg["det_splits"] = res.get("det_splits") or {}
        cfg["labels"] = res.get("labels") or []
        cfg["batch_size"] = min(int(cfg.get("batch_size", 8)), 16)
    return cfg


def _reset_steps(job: Job):
    for step in job.steps.values():
        step.update(status="waiting", percent=0, eta_s=None)


def start(params: dict) -> Job:
    job = Job(params); JOBS[job.id] = job
    threading.Thread(target=_run, args=(job,), daemon=True).start()
    return job


def _run(job: Job):
    p, decisions = job.params, list(job.params.get("decisions", []))
    try:
        job.set_step("Checking data", "running", 10)
        scan = dataset.scan_folder(p["data_dir"])
        if not scan["ok"] or (scan.get("format") != "yolo_detection" and scan.get("layout") not in ("class_folders", "split_folders")):
            raise RuntimeError(scan.get("message") or "I need one sub-folder for each category (for example cats/ and dogs/).")
        res = dataset.resolve(scan, p.get("roles"))
        if res["problems"]:
            raise RuntimeError(res["problems"][0])
        bal = dataset.analyze_balance(res["counts"])
        choice = p.get("balance_choice")
        if choice is None:
            choice = "continue"
            if bal["options"]:
                choice = job.ask(bal["message"], bal["options"])
                decisions.append({"what": "balance", "choice": choice, "by": "user"})
        if choice == "add_more":
            raise Cancelled()
        job.set_step("Checking data", "done", 100)

        job.set_step("Preparing images", "running", 50)
        hw = hardware.probe(p["data_dir"])
        cfg = build_config(p, hw, choice, res)
        run_dir = Path(p["run_dir"]) if p.get("run_dir") else (
            projects.runs_dir(p["project_id"]) / job.id if p.get("project_id") else Path(p["data_dir"]).parent / "runs" / job.id)
        run_dir.mkdir(parents=True, exist_ok=True)
        codegen.write_run_files(run_dir, cfg, res.get("labels"))
        device = training.get_device(cfg["device"])
        is_det = cfg.get("task") == "detection"

        batch = int(cfg.get("batch_size", 8))
        attempts = 0
        cpu_fallback = False
        while True:
            try:
                _reset_steps(job)
                cfg["batch_size"] = batch
                if is_det:
                    dl_tr, dl_va, classes = detection.build_loaders(cfg)
                else:
                    dl_tr, dl_va, classes = training.build_loaders(cfg)
                job.set_step("Preparing images", "done", 100)

                job.set_step("Choosing model", "running", 50)
                model = training.make_model(cfg, len(classes), device)
                sec = 0.0 if is_det else training.benchmark(cfg, model, dl_tr, device)
                job.eta_s = sec * len(dl_tr) * cfg["epochs"]
                job.set_step("Choosing model", "done", 100)

                job.set_step("Training", "running", 0, job.eta_s)
                val = (detection.train(job, cfg, model, dl_tr, dl_va, classes, device, run_dir) if is_det
                       else training.train(job, cfg, model, dl_tr, dl_va, classes, device, run_dir))
                job.set_step("Training", "done", 100)

                job.set_step("Evaluating", "running", 50)
                metrics = {**val, "source": "validation"}
                if is_det:
                    dl_te = detection.build_test_loader(cfg, (cfg.get("det_splits") or {}).get("test"))
                    if dl_te is not None:
                        exam = detection.evaluate(model, dl_te, classes, device)
                        metrics = {**exam, "source": "exam", "validation": val}
                elif cfg.get("test_dir"):
                    exam = training.evaluate(model, training.build_test_loader(cfg, classes), classes, device)
                    metrics = {**exam, "source": "exam", "validation": val}
                job.set_step("Evaluating", "done", 100)

                job.set_step("Exporting", "running", 50)
                training.export(run_dir, classes, metrics, decisions)
                job.set_step("Exporting", "done", 100)
                job.result, job.status, job.eta_s = {"metrics": metrics, "run_dir": str(run_dir), "run_id": run_dir.name}, "done", 0
                return
            except Exception as e:
                if not training.is_oom(e):
                    raise
                # Out of memory: clear the card and try again with fewer pictures at a time.
                import torch
                if device.type == "cuda":
                    torch.cuda.empty_cache()
                new_batch = max(1, batch // 2)
                if new_batch < batch and attempts < 3:
                    attempts += 1
                    batch = new_batch
                    job.set_step("Training", "running", 0, job.eta_s)
                    continue
                if device.type == "cuda" and not cpu_fallback:
                    # The card cannot hold this model: move to the processor and say so honestly.
                    cpu_fallback = True
                    device = torch.device("cpu")
                    cfg["device"] = "cpu"
                    batch = 4
                    attempts = 0
                    job.set_step("Training", "running", 0, job.eta_s)
                    continue
                raise RuntimeError(
                    "Your computer ran out of memory while training. I lowered the batch size as far as I could "
                    f"(now {batch} pictures at a time). Close other programs and try again, or use a smaller model."
                ) from e
    except Cancelled:
        job.status = "cancelled"
    except Exception as e:
        job.status, job.error = "failed", f"{e}"
        traceback.print_exc()
