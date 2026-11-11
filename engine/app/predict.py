"""Image and video-frame inference: trained classification/detection models and pretrained fallbacks."""
from __future__ import annotations
import io, json
from pathlib import Path
import yaml

_CACHE: dict = {}


def latest_run(runs_dir: Path) -> Path | None:
    runs = [d for d in runs_dir.iterdir()
            if (d / "labels.json").is_file() and ((d / "best.pt").is_file() or (d / "pretrained.json").is_file())]
    return max(runs, key=lambda d: d.stat().st_mtime) if runs else None


def is_pretrained(run_dir: Path) -> bool:
    """True when the run uses a ready-made model instead of one trained on the user's pictures."""
    if (run_dir / "pretrained.json").is_file():
        return True
    cfg = run_dir / "config.yaml"
    if cfg.is_file():
        try:
            return bool(yaml.safe_load(cfg.read_text(encoding="utf-8")).get("pretrained"))
        except Exception:
            return False
    return False


def _decode(data_b64: str) -> bytes:
    return __import__("base64").b64decode(data_b64.split(",")[-1])


def _trained_model(run_dir: Path):
    import torch
    from torchvision import transforms as T
    from . import training
    key = f"trained:{run_dir}"
    if key not in _CACHE:
        cfg = yaml.safe_load((run_dir / "config.yaml").read_text(encoding="utf-8"))
        classes = json.loads((run_dir / "labels.json").read_text(encoding="utf-8"))
        device = torch.device("cuda" if cfg.get("device") == "cuda" and torch.cuda.is_available() else "cpu")
        model = training.make_model(cfg, len(classes), device, pretrained=False)
        model.load_state_dict(torch.load(run_dir / "best.pt", map_location=device)); model.eval()
        tf = T.Compose([T.Resize((cfg["image_size"], cfg["image_size"])), T.ToTensor(), T.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])])
        _CACHE[key] = (model, classes, tf, device, cfg.get("task", "classification"))
    return _CACHE[key]


def pretrained_labels(task: str) -> list[str]:
    """The names the ready-made model knows, without loading the model."""
    if task == "detection":
        from torchvision.models.detection import SSDLite320_MobileNet_V3_Large_Weights
        return list(SSDLite320_MobileNet_V3_Large_Weights.DEFAULT.meta["categories"])
    from torchvision.models import ResNet18_Weights
    return list(ResNet18_Weights.DEFAULT.meta["categories"])


def _pretrained_model(task: str):
    import torch
    from torchvision import transforms as T
    key = f"pretrained:{task}"
    if key not in _CACHE:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        if task == "detection":
            from torchvision.models.detection import ssdlite320_mobilenet_v3_large, SSDLite320_MobileNet_V3_Large_Weights
            weights = SSDLite320_MobileNet_V3_Large_Weights.DEFAULT
            model = ssdlite320_mobilenet_v3_large(weights=weights).to(device).eval()
            classes = list(weights.meta["categories"])
            tf = weights.transforms()
        else:
            from torchvision.models import resnet18, ResNet18_Weights
            weights = ResNet18_Weights.DEFAULT
            model = resnet18(weights=weights).to(device).eval()
            classes = list(weights.meta["categories"])
            tf = weights.transforms()
        _CACHE[key] = (model, classes, tf, device, task)
    return _CACHE[key]


def _image_tensor(image_bytes: bytes, tf):
    from PIL import Image
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    return tf(img).unsqueeze(0), img.size


def _classify(model, classes, tf, device, image_bytes: bytes, top: int = 3) -> list[dict]:
    import torch
    tensor, _ = _image_tensor(image_bytes, tf)
    with torch.no_grad():
        probs = torch.softmax(model(tensor.to(device)), 1)[0].cpu().tolist()
    order = sorted(range(len(classes)), key=lambda i: -probs[i])[:top]
    return [{"label": classes[i], "probability": round(probs[i], 4)} for i in order]


def _detect(model, classes, tf, device, image_bytes: bytes, top: int = 50, score_threshold: float = 0.30) -> list[dict]:
    import torch
    tensor, size = _image_tensor(image_bytes, tf)
    w, h = size
    with torch.no_grad():
        out = model(tensor.to(device))[0]
    scores = out.get("scores", [])
    out_boxes = out.get("boxes", [])
    labels = out.get("labels", [])
    order = sorted(range(len(scores)), key=lambda i: -float(scores[i]))[:top]
    found = []
    for i in order:
        score = float(scores[i])
        if score < score_threshold:
            continue
        raw_label = int(labels[i]) if len(labels) else 0
        # SSD detection models reserve class 0 for background; custom trained classes are 1-based.
        class_idx = max(raw_label - 1, 0) if len(classes) > 1 else raw_label
        label = classes[class_idx] if 0 <= class_idx < len(classes) else f"class_{raw_label}"
        x1, y1, x2, y2 = [float(x) for x in out_boxes[i].tolist()]
        found.append({
            "label": label,
            "confidence": round(score, 4),
            "box": [round(max(x1, 0) / w, 4), round(max(y1, 0) / h, 4), round(min(x2, w) / w, 4), round(min(y2, h) / h, 4)],
        })
    return found


def predict(run_dir: Path, image_bytes: bytes, top: int = 3) -> dict:
    """Classify one image/frame or detect objects in it. The task is read from the run config."""
    if is_pretrained(run_dir):
        cfg = yaml.safe_load((run_dir / "config.yaml").read_text(encoding="utf-8"))
        task = cfg.get("task", "classification")
        out = predict_pretrained(task, image_bytes, top=top)
        out["pretrained"] = True
        return out
    model, classes, tf, device, task = _trained_model(run_dir)
    if task == "detection":
        return {"task": "detection", "detections": _detect(model, classes, tf, device, image_bytes, top=top)}
    return {"task": "classification", "predictions": _classify(model, classes, tf, device, image_bytes, top=top)}


def predict_pretrained(task: str, image_bytes: bytes, top: int = 3) -> dict:
    """Use torchvision's pretrained ImageNet or COCO model without any user dataset."""
    model, classes, tf, device, _task = _pretrained_model(task)
    if task == "detection":
        return {"task": "detection", "detections": _detect(model, classes, tf, device, image_bytes, top=top)}
    return {"task": "classification", "predictions": _classify(model, classes, tf, device, image_bytes, top=top)}
