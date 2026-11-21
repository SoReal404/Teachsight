import copy

METRICS = {"overall": 0.82, "per_class": {"cats": 0.9, "dogs": 0.74}, "source": "exam", "confusion": [[9, 1], [2, 8]]}
RUNS = [{"id": "run-1", "status": "done", "metrics": METRICS, "progress": {"epoch": 7, "overall_percent": 100}, "config": {"batch_size": 16}}, {"id": "run-2", "status": "failed", "progress": {"epoch": 2}, "error": "CUDA out of memory"}]
FILES = {"config.yaml": "model: resnet18\nbatch_size: 16\nepochs: 7", "train.py": "print('train')", "predict.py": "print('predict')", "serve.py": "print('serve')", "README.md": "Run documentation"}
SETTINGS = {"notifications": False, "providers": {}, "provider": "custom", "ai_mode": "own_key", "autopilot": False}
PROJECT = {"meta": {"name": "Browser test project"}, "stage": "trained", "chat": [], "state": {"data_dir": "/pictures", "brief": {"type": "classification"}, "data_confirmed": True, "balance_choice": "keep", "notes": [], "scan": {"root": "/pictures", "cross_split_duplicates": [], "broken_count": 0, "duplicate_count": 0}, "resolved": {"labels": ["cats", "dogs"], "counts": {"cats": 20, "dogs": 20}, "folders": [], "problems": [], "total_test": 20}, "plan": {"task": "classification", "model": "resnet18", "model_note": "baseline", "epochs": 7, "total_images": 60, "exam_images": 20, "val_images": 10, "device": "cpu", "notes": []}}}

def job(status="running", percent=35):
    return {"id": "job-1", "status": status, "overall_percent": percent, "steps": {"Training": {"percent": percent, "status": "running" if status == "running" else status}}, "result": {"metrics": METRICS, "run_id": "run-1"}, "error": "CUDA out of memory" if status == "failed" else None}

def project(with_job=False):
    result = copy.deepcopy(PROJECT)
    if with_job: result["state"]["job_id"] = "job-1"
    return result