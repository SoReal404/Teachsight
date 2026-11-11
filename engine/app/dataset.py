"""Dataset Intelligence: inspects classification folders, YOLO detection datasets,
detects duplicate/corrupted images, missing/invalid annotations, and class balance.
"""
from __future__ import annotations
import hashlib
from pathlib import Path
import yaml
from PIL import Image

IMG_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
ANN_EXT = {".txt"}
ROLES = ["train", "val", "test", "ignore"]
SPLIT_NAMES = {
    "train": {"train", "training", "training_set", "trainset", "train_set", "images/train", "train/images"},
    "val": {"val", "valid", "validation", "val_set", "valid_set", "validation_set", "dev", "images/val", "val/images"},
    "test": {"test", "testing", "test_set", "testset", "images/test", "test/images"},
}
# Folder names a YOLO dataset may use for each split (checked in this order).
YOLO_SPLIT_DIRS = {
    "train": ("train", "training", "training_set", "trainset", "train_set"),
    "val": ("valid", "val", "validation", "val_set", "valid_set", "validation_set", "dev"),
    "test": ("test", "testing", "test_set", "testset"),
}


def _images(folder: Path) -> list[Path]:
    if not folder.is_dir():
        return []
    return [p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in IMG_EXT]


def _role_for(name: str) -> str | None:
    n = name.lower().replace("-", "_").replace(" ", "_")
    return next((r for r, names in SPLIT_NAMES.items() if n in names), None)


def _class_dirs(folder: Path) -> list[Path]:
    if not folder.is_dir():
        return []
    return sorted(d for d in folder.iterdir() if d.is_dir() and _images(d))


def _entry(d: Path, role: str, class_dirs: list[Path] | None = None) -> dict:
    cds = _class_dirs(d) if class_dirs is None else class_dirs
    classes = {c.name: len(_images(c)) for c in cds}
    samples = {c.name: [str(p) for p in sorted(_images(c))[:5]] for c in cds}
    count = sum(classes.values()) if classes else len(_images(d))
    return {
        "name": d.name,
        "path": str(d),
        "role": role,
        "count": count,
        "classes": classes,
        "samples": samples,
        "loose_samples": [] if classes else [str(p) for p in sorted(_images(d))[:5]],
    }


def _detect_yolo(root: Path) -> dict | None:
    """Checks if folder is a YOLO object detection dataset."""
    yaml_files = list(root.glob("*.yaml")) + list(root.glob("*.yml"))
    data_yaml = yaml_files[0] if yaml_files else None
    
    # Check for images and labels directories
    has_images_dir = (root / "images").is_dir() or any((root / s / "images").is_dir() for s in ("train", "val", "test"))
    has_labels_dir = (root / "labels").is_dir() or any((root / s / "labels").is_dir() for s in ("train", "val", "test"))

    if not data_yaml and not (has_images_dir and has_labels_dir):
        return None

    names = []
    yaml_cfg = {}
    if data_yaml and data_yaml.is_file():
        try:
            yaml_cfg = yaml.safe_load(data_yaml.read_text(encoding="utf-8")) or {}
            raw_names = yaml_cfg.get("names", [])
            if isinstance(raw_names, dict):
                names = [str(raw_names[k]) for k in sorted(raw_names.keys())]
            elif isinstance(raw_names, list):
                names = [str(n) for n in raw_names]
        except Exception:
            pass

    return {
        "data_yaml": str(data_yaml) if data_yaml else None,
        "yaml_cfg": yaml_cfg,
        "class_names": names,
    }


def _find_splits(root: Path) -> dict:
    """Finds the YOLO split folders under a dataset root.

    A split folder holds the pictures and the box files, either as <split>/images + <split>/labels
    or as pictures directly inside <split> with a labels folder next to them.
    """
    out: dict[str, dict] = {}
    if not root.is_dir():
        return out
    children = sorted(d for d in root.iterdir() if d.is_dir())
    for role, names in YOLO_SPLIT_DIRS.items():
        for d in children:
            if d.name.lower() not in names:
                continue
            images_dir = d / "images"
            labels_dir = d / "labels"
            if images_dir.is_dir():
                pass
            elif _images(d):
                images_dir = d
            else:
                continue
            out[role] = {
                "root": str(d),
                "images": str(images_dir),
                "labels": str(labels_dir) if labels_dir.is_dir() else None,
                "count": len(_images(images_dir)),
            }
            break
    return out


def _analyze_yolo(root: Path, yolo_meta: dict) -> dict:
    """Deep analysis of a YOLO detection dataset."""
    all_imgs = _images(root)
    class_names = yolo_meta.get("class_names") or []
    nc = len(class_names)
    
    boxes_per_class: dict[str, int] = {}
    images_per_class: dict[str, int] = {}
    missing_ann = []
    empty_ann = []
    invalid_ann = []
    corrupted_imgs = []
    duplicates = []
    seen_hashes: dict[str, str] = {}

    for img_path in all_imgs:
        # Check image corruption
        try:
            with Image.open(img_path) as im:
                im.verify()
        except Exception:
            corrupted_imgs.append(str(img_path))
            continue

        # Check duplicate
        try:
            h = hashlib.md5(img_path.read_bytes()).hexdigest()
            if h in seen_hashes:
                duplicates.append([seen_hashes[h], str(img_path)])
            else:
                seen_hashes[h] = str(img_path)
        except Exception:
            pass

        # Find corresponding label file
        # Check standard YOLO mappings: .../images/... -> .../labels/... with .txt
        p_str = str(img_path)
        lbl_str = None
        if "/images/" in p_str.replace("\\", "/"):
            lbl_str = p_str.replace("/images/", "/labels/").replace("\\images\\", "\\labels\\")
        elif "\\images\\" in p_str:
            lbl_str = p_str.replace("\\images\\", "\\labels\\")
        else:
            lbl_str = str(img_path.with_suffix(".txt"))

        lbl_path = Path(lbl_str).with_suffix(".txt") if lbl_str else img_path.with_suffix(".txt")
        if not lbl_path.is_file():
            # Also try sibling labels folder
            lbl_alt = img_path.parent.parent / "labels" / f"{img_path.stem}.txt"
            if lbl_alt.is_file():
                lbl_path = lbl_alt

        if not lbl_path.is_file():
            missing_ann.append(str(img_path))
            continue

        # Read annotation
        try:
            lines = lbl_path.read_text(encoding="utf-8").strip().splitlines()
            if not lines:
                empty_ann.append(str(img_path))
                continue
            
            seen_in_this_img = set()
            for line_idx, line in enumerate(lines):
                parts = line.strip().split()
                if len(parts) != 5:
                    invalid_ann.append({"file": str(lbl_path), "line": line_idx + 1, "text": line, "reason": "Expected 5 values (class x y w h)"})
                    continue
                try:
                    cls_id = int(parts[0])
                    x, y, w, h_val = float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])
                    if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0 and 0.0 <= w <= 1.0 and 0.0 <= h_val <= 1.0):
                        invalid_ann.append({"file": str(lbl_path), "line": line_idx + 1, "text": line, "reason": "Coordinates outside [0, 1] range"})
                        continue
                    
                    c_label = class_names[cls_id] if 0 <= cls_id < len(class_names) else f"class_{cls_id}"
                    boxes_per_class[c_label] = boxes_per_class.get(c_label, 0) + 1
                    seen_in_this_img.add(c_label)
                except ValueError:
                    invalid_ann.append({"file": str(lbl_path), "line": line_idx + 1, "text": line, "reason": "Non-numeric values in annotation"})
            
            for c_label in seen_in_this_img:
                images_per_class[c_label] = images_per_class.get(c_label, 0) + 1
        except Exception as e:
            invalid_ann.append({"file": str(lbl_path), "reason": f"Cannot read label file: {e}"})

    labels = list(boxes_per_class.keys())
    if not labels and class_names:
        labels = class_names
    # Every class named in the data file, even when no picture uses it yet.
    for n in class_names:
        if n not in labels:
            labels.append(n)

    splits = _find_splits(root)
    split_counts = {role: s["count"] for role, s in splits.items()}
    folders = []
    for role, s in splits.items():
        pics = sorted(_images(Path(s["images"])))[:5]
        folders.append({
            "name": Path(s["root"]).name, "path": s["root"], "role": role,
            "count": s["count"], "classes": {}, "samples": {}, "loose_samples": [str(p) for p in pics],
        })
    if not folders:
        folders = [_entry(root, "train")]

    # Health score calculation
    total_count = max(len(all_imgs), 1)
    health = 100
    if corrupted_imgs: health -= min(30, int(len(corrupted_imgs) / total_count * 50) + 5)
    if missing_ann: health -= min(25, int(len(missing_ann) / total_count * 40) + 5)
    if invalid_ann: health -= min(25, int(len(invalid_ann) / total_count * 40) + 5)
    if duplicates: health -= min(15, len(duplicates) * 2)
    health = max(0, min(100, health))

    # Problems list with recommendations
    problems = []
    if corrupted_imgs:
        problems.append({
            "type": "corrupted",
            "severity": "high",
            "count": len(corrupted_imgs),
            "samples": corrupted_imgs[:10],
            "title": f"{len(corrupted_imgs)} corrupted image files",
            "description": "These pictures could not be opened and will be automatically skipped during training.",
            "recommendation": "Check the sample list and re-export or delete these broken image files.",
        })
    if missing_ann:
        problems.append({
            "type": "missing_annotations",
            "severity": "high" if len(missing_ann) > 5 else "medium",
            "count": len(missing_ann),
            "samples": missing_ann[:10],
            "title": f"{len(missing_ann)} images missing label files",
            "description": "These images do not have a corresponding .txt box annotation file.",
            "recommendation": "Add bounding box annotations for these images or remove them from the dataset.",
        })
    if invalid_ann:
        problems.append({
            "type": "invalid_annotations",
            "severity": "high",
            "count": len(invalid_ann),
            "samples": [x.get("file", "") for x in invalid_ann[:10]],
            "title": f"{len(invalid_ann)} invalid box annotations",
            "description": "Bounding box coordinates must be normalized between 0.0 and 1.0.",
            "recommendation": "Review the formatting of your annotation text files.",
        })
    if empty_ann:
        problems.append({
            "type": "empty_annotations",
            "severity": "low",
            "count": len(empty_ann),
            "samples": empty_ann[:10],
            "title": f"{len(empty_ann)} images with 0 bounding boxes",
            "description": "These images act as background (negative) samples without objects.",
            "recommendation": "Background samples are healthy in moderate quantities (5-10% of dataset).",
        })
    if duplicates:
        problems.append({
            "type": "duplicates",
            "severity": "medium",
            "count": len(duplicates),
            "samples": [d[1] for d in duplicates[:10]],
            "title": f"{len(duplicates)} duplicate image pairs detected",
            "description": "Exact duplicate images inflate accuracy metrics if split across train and test.",
            "recommendation": "Remove duplicate copies to ensure honest evaluation.",
        })

    return {
        "ok": len(all_imgs) > 0,
        "format": "yolo_detection",
        "task": "detection",
        "root": str(root),
        "total_images": len(all_imgs),
        "labels": labels,
        "counts": boxes_per_class,
        "images_per_class": images_per_class,
        "splits": splits,
        "split_counts": split_counts,
        "health_score": health,
        "corrupted_count": len(corrupted_imgs),
        "corrupted": corrupted_imgs[:20],
        "duplicate_count": len(duplicates),
        "duplicate_pairs": duplicates[:20],
        "missing_annotation_count": len(missing_ann),
        "missing_annotations": missing_ann[:20],
        "invalid_annotation_count": len(invalid_ann),
        "invalid_annotations": invalid_ann[:20],
        "empty_annotation_count": len(empty_ann),
        "problems": problems,
        "folders": folders,
    }


def scan_folder(path: str) -> dict:
    root = Path(path)
    if not root.is_dir():
        return {"ok": False, "error": "folder_not_found", "message": f"I can't find the folder {path}. Can you check the path?"}

    # 1. Check for YOLO detection dataset
    yolo_meta = _detect_yolo(root)
    if yolo_meta:
        return _analyze_yolo(root, yolo_meta)

    # 2. Classification dataset inspection
    subs = [d for d in sorted(root.iterdir()) if d.is_dir()]
    cds = {d: _class_dirs(d) for d in subs}
    split_layout = any(_role_for(d.name) == "train" and len(cds[d]) >= 2 for d in subs)
    folders: list[dict] = []
    if split_layout:
        layout = "split_folders"
        for d in subs:
            r = _role_for(d.name)
            if cds[d] or _images(d):
                folders.append(_entry(d, r if (r and cds[d]) else "ignore", cds[d]))
    else:
        root_cds = [d for d in subs if _images(d)]
        if len(root_cds) >= 2:
            layout, folders = "class_folders", [_entry(root, "train", root_cds)]
        elif _images(root):
            layout = "no_labels"
        else:
            layout = "empty"

    role_by_top = {f["name"]: f["role"] for f in folders}
    broken, seen, dups, cross = [], {}, [], 0
    all_imgs = _images(root)
    for p in all_imgs:
        try:
            with Image.open(p) as im:
                im.verify()
        except Exception:
            broken.append(str(p))
            continue
        try:
            h = hashlib.md5(p.read_bytes()).hexdigest()
            if h in seen:
                dups.append([seen[h], str(p)])
                if split_layout:
                    ta, tb = Path(seen[h]).relative_to(root).parts[0], p.relative_to(root).parts[0]
                    ra, rb = role_by_top.get(ta), role_by_top.get(tb)
                    if ta != tb and ra in ("train", "val", "test") and rb in ("train", "val", "test") and ra != rb:
                        cross += 1
            else:
                seen[h] = str(p)
        except Exception:
            pass

    train = next((f for f in folders if f["role"] == "train"), None)
    counts = dict(train["classes"]) if train else {}
    task = "binary" if len(counts) == 2 else "multiclass" if len(counts) > 2 else "classification"

    # Health calculation
    total_count = max(len(all_imgs), 1)
    health = 100
    if broken: health -= min(30, int(len(broken) / total_count * 50) + 5)
    if dups: health -= min(20, len(dups) * 2)
    if cross > 0: health -= min(20, cross * 4)
    health = max(0, min(100, health))

    problems = []
    if broken:
        problems.append({
            "type": "corrupted",
            "severity": "high",
            "count": len(broken),
            "samples": broken[:10],
            "title": f"{len(broken)} corrupted image files",
            "description": "These pictures could not be opened and will be skipped.",
            "recommendation": "Verify or re-save these files in standard JPEG/PNG format.",
        })
    if dups:
        problems.append({
            "type": "duplicates",
            "severity": "medium",
            "count": len(dups),
            "samples": [d[1] for d in dups[:10]],
            "title": f"{len(dups)} duplicate image pairs",
            "description": f"{len(dups)} images have identical content.{f' {cross} pairs cross between training and test sets.' if cross else ''}",
            "recommendation": "Remove duplicates to avoid training data leaking into test evaluation.",
        })

    return {
        "ok": layout != "empty",
        "format": "classification",
        "layout": layout,
        "root": str(root),
        "suggested_task": task,
        "task": "classification",
        "folders": folders,
        "labels": list(counts),
        "counts": counts,
        "total_images": len(all_imgs),
        "health_score": health,
        "broken": broken[:20],
        "broken_count": len(broken),
        "duplicate_pairs": dups[:20],
        "duplicate_count": len(dups),
        "cross_split_duplicates": cross,
        "problems": problems,
    }


def resolve(scan: dict, roles: dict | None = None) -> dict:
    """Apply folder roles and return normalized paths."""
    if scan.get("format") == "yolo_detection":
        root = scan.get("root", "")
        splits = scan.get("splits", {}) or {}
        counts = scan.get("split_counts", {}) or {}
        problems = [p["title"] for p in scan.get("problems", []) if p.get("type") == "invalid_annotations"]
        return {
            "format": "yolo_detection",
            "task": "detection",
            "folders": scan.get("folders", []),
            "train_dir": root,
            "test_dir": root,
            "val_dir": root,
            "det_splits": splits,
            "split_counts": counts,
            "labels": scan.get("labels", []),
            "counts": scan.get("counts", {}),
            "total_train": counts.get("train", scan.get("total_images", 0)),
            "total_val": counts.get("val", 0),
            "total_test": counts.get("test", 0),
            "problems": problems,
        }

    roles = roles or {}
    folders = [{**f, "role": roles.get(f["name"], f["role"])} for f in scan.get("folders", [])]
    pick = lambda r: [f for f in folders if f["role"] == r]
    train, test, val, problems = pick("train"), pick("test"), pick("val"), []
    if len(train) != 1: problems.append("Choose exactly one folder to teach the AI with.")
    if len(test) > 1: problems.append("Choose only one folder for the final exam.")
    if len(val) > 1: problems.append("Choose only one folder for validation.")
    t = train[0] if len(train) == 1 else None
    labels = sorted(t["classes"]) if t else []
    use = {}
    for name, grp in (("test", test), ("val", val)):
        g = grp[0] if len(grp) == 1 else None
        if g and t and set(g["classes"]) != set(labels):
            problems.append(f"The {name} folder '{g['name']}' has different categories ({', '.join(sorted(g['classes'])) or 'none'}) than the training folder ({', '.join(labels)}).")
            g = None
        use[name] = g
    return {
        "format": "classification",
        "task": "classification",
        "folders": folders,
        "train_dir": t["path"] if t else None,
        "test_dir": use["test"]["path"] if use["test"] else None,
        "val_dir": use["val"]["path"] if use["val"] else None,
        "labels": labels,
        "counts": dict(t["classes"]) if t else {},
        "total_train": t["count"] if t else 0,
        "total_test": use["test"]["count"] if use["test"] else 0,
        "problems": problems,
    }


def analyze_balance(counts: dict[str, int]) -> dict:
    if len(counts) < 2:
        return {"severity": "ok", "ratio": 1.0, "message": "Only one category found, so there is nothing to compare.", "options": []}
    hi = max(counts, key=counts.get)
    lo = min(counts, key=counts.get)
    ratio = counts[hi] / max(counts[lo], 1)
    sev = "ok" if ratio < 1.5 else "mild" if ratio < 3 else "warning" if ratio < 10 else "severe"
    small = counts[lo]
    size_sev = "severe" if small < 20 else "low" if small < 100 else "ok"
    if sev == "ok":
        msg = "Your categories are well balanced."
    else:
        msg = (f"You have {counts[lo]} {lo} samples and {counts[hi]} {hi} samples. "
               f"The AI will see {hi} more often, so it may lean toward predicting '{hi}'. "
               f"It could look accurate overall while being worse at detecting {lo}.")
    if size_sev != "ok":
        msg += f" Also, {lo} has only {small} samples, which is {'very ' if size_sev == 'severe' else ''}few for the AI to learn from."
    if sev == "ok" and size_sev != "ok":
        options = [
            {"id": "continue", "recommended": True, "label": "Continue anyway (recommended)",
             "effect": "Fine for a first try. With so few pictures the score may jump around."},
            {"id": "add_more", "label": "I'll add more pictures", "effect": "Best result, but needs a bit of work from you. I will wait."}
        ]
        return {"severity": sev, "size_severity": size_sev, "ratio": round(ratio, 2), "largest": hi, "smallest": lo, "message": msg, "options": options}
    options = [] if sev == "ok" and size_sev == "ok" else [
        {"id": "balance_auto", "recommended": True, "label": "Balance it for me (recommended)",
         "effect": f"I will show {lo} samples to the AI more often during training so both count equally."},
        {"id": "add_more", "label": f"I'll add more {lo} pictures",
         "effect": "Best result, but needs a bit of work from you. I will wait."},
        {"id": "continue", "label": "Continue as is",
         "effect": "Fine for a quick test. I will report accuracy for each category so you can see any bias."},
    ]
    return {
        "severity": sev,
        "size_severity": size_sev,
        "ratio": round(ratio, 2),
        "largest": hi,
        "smallest": lo,
        "message": msg,
        "options": options,
    }
