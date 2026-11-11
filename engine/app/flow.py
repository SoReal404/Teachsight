"""The guided flow (no chat needed): ingest a folder, apply roles, compare with the questionnaire, build the plan."""
from __future__ import annotations
import re
from . import dataset, hardware


def _norm(w: str) -> str:
    w = w.strip().lower()
    return w[:-1] if w.endswith("s") and len(w) > 3 else w


COUNT_RANGES = {"under_100": (0, 100, "under 100"), "100_1000": (100, 1000, "100 to 1,000"),
                "1000_10000": (1000, 10000, "1,000 to 10,000"), "over_10000": (10000, 10**9, "over 10,000")}


def brief_checks(brief: dict, labels: list[str], total: int) -> list[str]:
    """Plain-language differences between the questionnaire and what the folder really contains."""
    notes = []
    expected = [x for x in re.split(r"[,;\n]|\band\b", brief.get("categories") or "") if x.strip()]
    if expected:
        found = {_norm(l): l for l in labels}; want = {_norm(x): x.strip() for x in expected}
        notes += [f"You mentioned '{v}', but I did not find a folder for it." for k, v in want.items() if k not in found]
        notes += [f"I found a folder called '{v}' that you did not mention." for k, v in found.items() if k not in want]
    rng = COUNT_RANGES.get(brief.get("count") or "")
    if rng and (total < rng[0] * 0.5 or total > rng[1] * 2):
        notes.append(f"You expected about {rng[2]} pictures, but I found {total}.")
    return notes


def refresh(state: dict):
    res = dataset.resolve(state["scan"], state.get("roles"))
    state["resolved"] = res
    state["balance"] = dataset.analyze_balance(res["counts"]) if res["counts"] else None
    notes = brief_checks(state.get("brief") or {}, res["labels"], res["total_train"] + res["total_test"])
    cross = state["scan"].get("cross_split_duplicates", 0)
    if cross:
        notes.append(f"{cross} pictures appear in both the training and the exam folders, so the score would look better than it really is.")
    notes += [f"'{f['name']}' has no category folders inside, so I will ignore it." for f in res["folders"] if f["role"] == "ignore" and not f["classes"]]
    if res.get("format") == "yolo_detection":
        counts = res.get("split_counts") or {}
        if counts:
            notes.append("I will teach the AI on " + ", check it on " + ", and grade it on ".join(
                f"{n} pictures ({k})" for k, n in counts.items() if n) + ".")
        missing = state["scan"].get("missing_annotation_count", 0)
        if missing:
            notes.append(f"{missing} pictures have no box file. I will treat them as pictures with nothing to detect.")
    state["notes"] = notes + res["problems"]


def ingest(state: dict, path: str) -> dict:
    path = path.strip().strip('"').strip("'")          # Windows "Copy as path" adds quotes
    scan = dataset.scan_folder(path)
    if not scan["ok"]:
        return {"ok": False, "problem": scan.get("message") or "I could not find any pictures there."}
    if scan.get("format") != "yolo_detection" and scan.get("layout") not in ("class_folders", "split_folders"):
        return {"ok": False, "problem": "I need one sub-folder for each category (e.g. cats/ and dogs/) or a YOLO detection dataset (data.yaml with images and labels)."}
    state.update(data_dir=path, scan=scan, roles={}, approved=False, plan=None, job_id=None, balance_choice=None,
                 balance_note=None, data_confirmed=False, stage="data")
    refresh(state)
    return {"ok": True}


def set_roles(state: dict, roles: dict):
    state["roles"] = {k: v for k, v in roles.items() if v in dataset.ROLES}
    state.update(plan=None, approved=False, balance_choice=None, data_confirmed=False)
    refresh(state)


def autopilot(state: dict, enabled: bool) -> bool:
    """Autopilot picks the recommended fix silently for small and medium problems. Returns True if it did."""
    bal = state.get("balance") or {}
    if enabled and bal.get("options") and bal["severity"] != "severe" and bal.get("size_severity") != "severe":
        state["balance_choice"] = bal["options"][0]["id"]      # the recommended option is always first
        state.setdefault("decisions", []).append({"what": "balance", "choice": state["balance_choice"], "by": "autopilot"})
        state["balance_note"] = "Handled silently by the user's autopilot setting. Do not mention it."
        return True
    return False


def make_plan(state: dict, epochs: int | None) -> dict:
    res, bal, brief = state["resolved"], state.get("balance") or {}, state.get("brief") or {}
    choice = state.get("balance_choice") or (None if bal.get("options") else "continue")
    hw, pri = hardware.probe(), brief.get("priority", "balanced")

    # The pictures decide what can be trained. The questionnaire only says what the user hoped for.
    task = res.get("task", "classification")
    asked = brief.get("type")
    notes = []
    if task == "detection" and asked and asked != "detection":
        notes.append("Your folder holds box files, so I will train a detector that finds and boxes each object.")
    elif task == "classification" and asked == "detection":
        notes.append("Your pictures are sorted into category folders and have no boxes drawn around the objects, "
                     "so I will train a classifier (one answer per picture). To find and box each object instead, "
                     "add a box file next to every picture and I will switch automatically.")
    elif task == "classification" and asked and asked not in ("classification", "detection"):
        notes.append(f"You asked for {asked}, but your pictures are sorted into category folders with one answer per picture, "
                     "so I will train a classifier on them.")

    if task == "detection":
        model = "ssdlite_mobilenet_v3"
        why = "a fast, efficient object detection model"
    else:
        model = "mobilenet_v3_large" if brief.get("usage") == "phone" else ("resnet50" if pri == "best" and hw["device"] == "cuda" else "resnet18")
        why = {"mobilenet_v3_large": "a small, fast model that suits phones", "resnet50": "a larger model for the best accuracy",
               "resnet18": "a reliable, quick model"}[model]
    if state["scan"].get("broken_count"):
        notes.append(f"{state['scan'].get('broken_count', 0)} broken pictures will be skipped.")
    total = res.get("total_train", 0) + res.get("total_test", 0)
    return {"task": task, "requested_task": asked or task, "labels": res["labels"], "counts": res["counts"],
            "total_images": total, "exam_images": res.get("total_test", 0),
            "val_images": res.get("total_val", 0),
            "epochs": max(3, min(int(epochs or {"fast": 5, "balanced": 10, "best": 20}.get(pri, 10)), 50)), "model": model, "model_note": why,
            "device": hw["device"], "hardware": hw, "balance_choice": choice, "needs_decision": choice is None, "notes": notes}
