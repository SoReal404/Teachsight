"""Object detection training for YOLO-style datasets.

A YOLO dataset is a folder per split, each holding the pictures and a box file per picture:
    Cars Detection/
        data.yaml            <- names: [Ambulance, Bus, ...]
        train/images/*.jpg   train/labels/*.txt
        valid/images/*.jpg   valid/labels/*.txt
        test/images/*.jpg    test/labels/*.txt

Each box file holds one line per object: "class x_centre y_centre width height", all normalised
to 0..1. The model is torchvision's SSDLite320, where class 0 is the background, so a picture
object of class 0 becomes label 1 for the model.

Every picture is resized to a square before it reaches the model, and the boxes are resized with
it, so the picture and its boxes always describe the same frame.
"""
from __future__ import annotations
import time
from pathlib import Path

IMG_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
DET_SIZE = 320          # SSDLite320 is built for 320x320 pictures


def read_yolo_labels(path: Path) -> list[tuple[int, float, float, float, float]]:
    """Reads one box file: (class, centre x, centre y, width, height), all normalised."""
    out: list[tuple[int, float, float, float, float]] = []
    if not path.is_file():
        return out
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return out
    for line in text.splitlines():
        parts = line.strip().split()
        if len(parts) != 5:
            continue
        try:
            cls = int(float(parts[0]))
            x, y, w, h = (float(v) for v in parts[1:5])
        except ValueError:
            continue
        if w <= 0 or h <= 0:
            continue
        out.append((cls, x, y, w, h))
    return out


class YoloDetectionDataset:
    """One picture plus its boxes, both in the same square frame."""

    def __init__(self, images_dir: str, labels_dir: str | None, image_size: int = DET_SIZE):
        self.size = image_size
        self.items: list[tuple[Path, Path | None]] = []
        root = Path(images_dir)
        if not root.is_dir():
            return
        for p in sorted(q for q in root.iterdir() if q.is_file() and q.suffix.lower() in IMG_EXT):
            lbl: Path | None = None
            if labels_dir:
                cand = Path(labels_dir) / f"{p.stem}.txt"
                lbl = cand if cand.is_file() else None
            if lbl is None:
                cand = p.with_suffix(".txt")
                lbl = cand if cand.is_file() else None
            self.items.append((p, lbl))

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, i: int):
        import torch
        from PIL import Image
        import torchvision.transforms.functional as TF

        path, lbl = self.items[i]
        with Image.open(path) as im:
            img = TF.to_tensor(im.convert("RGB"))
        img = TF.resize(img, [self.size, self.size])

        boxes: list[list[float]] = []
        labels: list[int] = []
        if lbl is not None:
            for cls, x, y, w, h in read_yolo_labels(lbl):
                x1, y1 = (x - w / 2) * self.size, (y - h / 2) * self.size
                x2, y2 = (x + w / 2) * self.size, (y + h / 2) * self.size
                boxes.append([max(0.0, x1), max(0.0, y1),
                              min(float(self.size), x2), min(float(self.size), y2)])
                labels.append(cls + 1)          # 0 is the background for the model
        target = {
            "boxes": torch.as_tensor(boxes, dtype=torch.float32).reshape(-1, 4),
            "labels": torch.as_tensor(labels, dtype=torch.int64),
        }
        return img, target


def collate(batch):
    """Detection pictures can have different sizes, so they travel as lists."""
    return [b[0] for b in batch], [b[1] for b in batch]


def _split_of(cfg: dict, role: str) -> dict | None:
    return (cfg.get("det_splits") or {}).get(role)


def build_loaders(cfg: dict):
    from torch.utils.data import DataLoader

    splits = cfg.get("det_splits") or {}
    classes = list(cfg.get("labels") or [])
    size = int(cfg.get("image_size", DET_SIZE))
    batch = max(1, int(cfg.get("batch_size", 8)))

    tr = splits.get("train")
    if not tr:
        raise RuntimeError("I could not find the training pictures for this detection dataset.")
    ds_tr = YoloDetectionDataset(tr["images"], tr.get("labels"), classes, size)
    if not len(ds_tr):
        raise RuntimeError("I could not find any pictures to learn from in the training folder.")

    va_split = splits.get("val") or splits.get("test")
    ds_va = YoloDetectionDataset(va_split["images"], va_split.get("labels"), classes, size) if va_split else ds_tr
    if not len(ds_va):
        ds_va = ds_tr

    dl_tr = DataLoader(ds_tr, batch_size=batch, shuffle=True, num_workers=0, collate_fn=collate)
    dl_va = DataLoader(ds_va, batch_size=batch, shuffle=False, num_workers=0, collate_fn=collate)
    return dl_tr, dl_va, classes


def build_test_loader(cfg: dict, split: dict | None):
    from torch.utils.data import DataLoader

    if not split:
        return None
    size = int(cfg.get("image_size", DET_SIZE))
    batch = max(1, int(cfg.get("batch_size", 8)))
    ds = YoloDetectionDataset(split["images"], split.get("labels"), list(cfg.get("labels") or []), size)
    if not len(ds):
        return None
    return DataLoader(ds, batch_size=batch, shuffle=False, num_workers=0, collate_fn=collate)


def _iou(box: list[float], other: list[float]) -> float:
    ix1, iy1 = max(box[0], other[0]), max(box[1], other[1])
    ix2, iy2 = min(box[2], other[2]), min(box[3], other[3])
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    a = max(0.0, box[2] - box[0]) * max(0.0, box[3] - box[1])
    b = max(0.0, other[2] - other[0]) * max(0.0, other[3] - other[1])
    union = a + b - inter
    return inter / union if union > 0 else 0.0


def _average_precision(recalls: list[float], precisions: list[float]) -> float:
    """Area under the precision/recall curve, with the usual flat interpolation."""
    if not recalls:
        return 0.0
    mrec = [0.0] + list(recalls) + [recalls[-1]]
    mpre = [0.0] + list(precisions) + [0.0]
    for i in range(len(mpre) - 2, -1, -1):
        mpre[i] = max(mpre[i], mpre[i + 1])
    ap = 0.0
    for i in range(len(mrec) - 1):
        if mrec[i + 1] != mrec[i]:
            ap += (mrec[i + 1] - mrec[i]) * mpre[i + 1]
    return ap


def evaluate(model, dl, classes: list[str], device, score_threshold: float = 0.05,
             iou_threshold: float = 0.5) -> dict:
    """Average precision at 0.5 (mAP@0.5) per class and overall, plus object counts."""
    import torch

    model.eval()
    n = len(classes)
    gt_by_img: list[dict[int, list[list[float]]]] = []
    preds: list[tuple[int, int, float, list[float]]] = []

    with torch.no_grad():
        for images, targets in dl:
            images = [i.to(device) for i in images]
            outputs = model(images)
            for k, out in enumerate(outputs):
                boxes = out["boxes"].cpu().tolist()
                scores = out["scores"].cpu().tolist()
                labels = out["labels"].cpu().tolist()
                for box, score, label in zip(boxes, scores, labels):
                    if score < score_threshold:
                        continue
                    preds.append((k, max(int(label) - 1, 0), float(score), box))
            for target in targets:
                gt: dict[int, list[list[float]]] = {}
                for box, label in zip(target["boxes"].tolist(), target["labels"].tolist()):
                    gt.setdefault(max(int(label) - 1, 0), []).append(box)
                gt_by_img.append(gt)

    per_class: dict[str, float] = {}
    per_class_ap: dict[str, float] = {}
    objects: dict[str, int] = {}
    aps: list[float] = []

    for ci in range(n):
        truth: dict[int, list[list[float]]] = {}
        total = 0
        for k, gt in enumerate(gt_by_img):
            boxes = gt.get(ci, [])
            if boxes:
                truth[k] = boxes
                total += len(boxes)
        name = classes[ci] if ci < len(classes) else f"class_{ci}"
        objects[name] = total
        if total == 0:
            per_class[name] = 0.0
            per_class_ap[name] = 0.0
            continue
        used = {k: [False] * len(v) for k, v in truth.items()}
        cls_preds = sorted([p for p in preds if p[1] == ci], key=lambda p: -p[2])
        tp: list[int] = []
        fp: list[int] = []
        for k, _, _, box in cls_preds:
            best_iou, best_j = 0.0, -1
            for j, gt_box in enumerate(truth.get(k, [])):
                if used[k][j]:
                    continue
                iou = _iou(box, gt_box)
                if iou > best_iou:
                    best_iou, best_j = iou, j
            if best_j >= 0 and best_iou >= iou_threshold:
                used[k][best_j] = True
                tp.append(1)
                fp.append(0)
            else:
                tp.append(0)
                fp.append(1)
        ctp = cfp = 0
        recalls: list[float] = []
        precisions: list[float] = []
        for t, f in zip(tp, fp):
            ctp += t
            cfp += f
            recalls.append(ctp / total)
            precisions.append(ctp / max(ctp + cfp, 1))
        ap = _average_precision(recalls, precisions)
        aps.append(ap)
        per_class[name] = round(ap, 3)
        per_class_ap[name] = round(ap, 3)

    mean_ap = round(sum(aps) / len(aps), 3) if aps else 0.0
    return {
        "overall": mean_ap,
        "metric_label": "mAP@0.5",
        "loss": None,
        "precision": mean_ap,
        "recall": mean_ap,
        "f1": mean_ap,
        "per_class": per_class,
        "per_class_precision": per_class_ap,
        "per_class_recall": per_class_ap,
        "per_class_f1": per_class_ap,
        "confusion_matrix": None,
        "classes": list(classes),
        "objects_per_class": objects,
        "inference_speed_ms": None,
    }


def train(job, cfg: dict, model, dl_tr, dl_va, classes: list[str], device, run_dir: Path) -> dict:
    """Trains the detector and keeps the best round by average precision."""
    import torch

    epochs = int(cfg.get("epochs", 10))
    total_steps = max(1, epochs * len(dl_tr))
    done_steps = 0
    t0 = time.time()
    best_ap = -1.0
    history: list[dict] = []
    lr = float(cfg.get("learning_rate", 3e-4))
    opt = torch.optim.AdamW(model.parameters(), lr, weight_decay=1e-4)

    for epoch in range(epochs):
        model.train()
        running_loss, batches = 0.0, 0
        for images, targets in dl_tr:
            job.checkpoint()
            images = [i.to(device) for i in images]
            targets = [{k: v.to(device) for k, v in t.items()} for t in targets]
            losses = model(images, targets)
            loss = sum(losses.values())
            opt.zero_grad()
            loss.backward()
            opt.step()

            running_loss += float(loss.item())
            batches += 1
            done_steps += 1
            eta = (time.time() - t0) / done_steps * (total_steps - done_steps)
            job.set_step("Training", "running", (done_steps / total_steps) * 100, eta)
            job.eta_s = eta

        val = evaluate(model, dl_va, classes, device)
        history.append({
            "epoch": epoch + 1,
            "train_loss": round(running_loss / max(batches, 1), 4),
            "val_loss": val.get("loss"),
            "val_acc": val.get("overall"),
        })
        if (val.get("overall") or 0) >= best_ap:
            best_ap = val["overall"]
            torch.save(model.state_dict(), run_dir / "best.pt")

    best_pt = run_dir / "best.pt"
    if best_pt.is_file():
        model.load_state_dict(torch.load(best_pt, map_location=device))
    final = evaluate(model, dl_va, classes, device)
    final["history"] = history
    final["duration_seconds"] = round(time.time() - t0, 1)
    final["loss"] = history[-1]["train_loss"] if history else None
    if best_pt.is_file():
        final["model_size_mb"] = round(best_pt.stat().st_size / (1024 ** 2), 2)
    return final
