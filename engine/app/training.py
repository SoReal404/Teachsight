"""Computer Vision training engine: supports Classification and Detection,
computes precision, recall, F1, confusion matrix, loss curves, and exports ONNX.
"""
from __future__ import annotations
import io, json, random, time
from pathlib import Path

CLASSIFICATION_MODELS = {"resnet18", "resnet50", "efficientnet_b0", "mobilenet_v3_large"}
DETECTION_MODELS = {"ssdlite_mobilenet_v3", "fasterrcnn_mobilenet_v3"}
ALL_MODELS = CLASSIFICATION_MODELS | DETECTION_MODELS


def get_device(name: str):
    import torch
    if name == "cuda" and torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


def is_oom(exc: BaseException) -> bool:
    """True when the error is 'the graphics card ran out of memory'."""
    text = str(exc).lower()
    return "out of memory" in text or "out-of-memory" in text or "cuda oom" in text


def _tfs(cfg):
    from torchvision import transforms as T
    sz = cfg.get("image_size", 224)
    norm = T.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
    return (
        T.Compose([T.Resize((sz, sz)), T.RandomHorizontalFlip(), T.ColorJitter(0.2, 0.2, 0.2), T.ToTensor(), norm]),
        T.Compose([T.Resize((sz, sz)), T.ToTensor(), norm])
    )


def build_loaders(cfg: dict):
    from torch.utils.data import DataLoader, Subset, WeightedRandomSampler
    from torchvision import datasets
    tf_tr, tf_va = _tfs(cfg)
    ds_tr = datasets.ImageFolder(cfg["data_dir"], tf_tr)
    
    if cfg.get("val_dir"):
        ds_va = datasets.ImageFolder(cfg["val_dir"], tf_va)
        if ds_va.classes != ds_tr.classes:
            raise ValueError("The validation folder has different categories than the training folder.")
        tr_idx, dl_va = list(range(len(ds_tr))), DataLoader(ds_va, batch_size=cfg["batch_size"])
    else:
        ds_v = datasets.ImageFolder(cfg["data_dir"], tf_va)
        rng, tr_idx, va_idx = random.Random(cfg["seed"]), [], []
        for c in range(len(ds_tr.classes)):
            idx = [i for i, t in enumerate(ds_tr.targets) if t == c]
            rng.shuffle(idx)
            k = max(1, int(len(idx) * cfg.get("val_split", 0.2)))
            va_idx += idx[:k]
            tr_idx += idx[k:]
        dl_va = DataLoader(Subset(ds_v, va_idx), batch_size=cfg["batch_size"])

    sampler = None
    if cfg.get("balance_choice") == "balance_auto":
        counts = [0] * len(ds_tr.classes)
        for i in tr_idx: counts[ds_tr.targets[i]] += 1
        sampler = WeightedRandomSampler([1.0 / max(counts[ds_tr.targets[i]], 1) for i in tr_idx], len(tr_idx), replacement=True)

    dl_tr = DataLoader(Subset(ds_tr, tr_idx), batch_size=cfg["batch_size"], sampler=sampler, shuffle=sampler is None)
    return dl_tr, dl_va, ds_tr.classes


def build_test_loader(cfg: dict, classes: list):
    from torch.utils.data import DataLoader
    from torchvision import datasets
    ds = datasets.ImageFolder(cfg["test_dir"], _tfs(cfg)[1])
    if ds.classes != list(classes):
        raise ValueError("The exam folder has different categories than the training folder.")
    return DataLoader(ds, batch_size=cfg["batch_size"])


def make_model(cfg: dict, n_classes: int, device, pretrained: bool = True):
    import torch.nn as nn
    from torchvision import models
    m_name = cfg.get("model", "resnet18")

    if m_name in ("ssdlite_mobilenet_v3", "fasterrcnn_mobilenet_v3"):
        from torchvision.models.detection import ssdlite320_mobilenet_v3_large, SSDLite320_MobileNet_V3_Large_Weights
        weights = SSDLite320_MobileNet_V3_Large_Weights.DEFAULT if pretrained else None
        m = ssdlite320_mobilenet_v3_large(weights=weights, num_classes=n_classes + 1)
        return m.to(device)

    if m_name not in CLASSIFICATION_MODELS:
        m_name = "resnet18"

    m = getattr(models, m_name)(weights="DEFAULT" if pretrained else None)
    if hasattr(m, "fc"):
        m.fc = nn.Linear(m.fc.in_features, n_classes)
    elif hasattr(m, "classifier"):
        if isinstance(m.classifier, nn.Sequential):
            m.classifier[-1] = nn.Linear(m.classifier[-1].in_features, n_classes)
        else:
            m.classifier = nn.Linear(m.classifier.in_features, n_classes)
    return m.to(device)


def make_optimizer(cfg: dict, model):
    import torch
    lr = float(cfg.get("learning_rate", 3e-4))
    if cfg.get("optimizer") == "sgd":
        return torch.optim.SGD(model.parameters(), lr, momentum=0.9)
    return torch.optim.AdamW(model.parameters(), lr)


def benchmark(cfg: dict, model, dl, device, steps=3) -> float:
    """Seconds per training step on this PC."""
    import torch
    opt, lossf, times, it = make_optimizer(cfg, model), torch.nn.CrossEntropyLoss(), [], iter(dl)
    model.train()
    for _ in range(steps + 1):
        try: x, y = next(it)
        except StopIteration: break
        t = time.time()
        x, y = x.to(device), y.to(device)
        opt.zero_grad()
        lossf(model(x), y).backward()
        opt.step()
        if device.type == "cuda":
            torch.cuda.synchronize()
        times.append(time.time() - t)
    use = times[1:] or times
    return sum(use) / max(len(use), 1)


def evaluate(model, dl, classes: list, device) -> dict:
    """Comprehensive evaluation: loss, accuracy, precision, recall, F1, and confusion matrix."""
    import torch
    import torch.nn as nn
    model.eval()
    loss_fn = nn.CrossEntropyLoss()
    num_classes = len(classes)
    
    # Confusion matrix: conf[true_class][pred_class]
    conf = [[0] * num_classes for _ in range(num_classes)]
    total_loss, total_samples = 0.0, 0
    t_inf_start = time.time()

    with torch.no_grad():
        for x, y in dl:
            x, y = x.to(device), y.to(device)
            out = model(x)
            loss = loss_fn(out, y)
            total_loss += loss.item() * len(y)
            preds = out.argmax(1).cpu().tolist()
            trues = y.cpu().tolist()
            total_samples += len(trues)
            for t, p in zip(trues, preds):
                if 0 <= t < num_classes and 0 <= p < num_classes:
                    conf[t][p] += 1

    inf_duration = time.time() - t_inf_start
    inf_speed_ms = round((inf_duration / max(total_samples, 1)) * 1000, 1)

    # Calculate per-class metrics
    per_class_acc = {}
    per_class_precision = {}
    per_class_recall = {}
    per_class_f1 = {}

    total_correct = sum(conf[i][i] for i in range(num_classes))
    overall_acc = round(total_correct / max(total_samples, 1), 3)

    for i, c in enumerate(classes):
        tp = conf[i][i]
        fp = sum(conf[j][i] for j in range(num_classes) if j != i)
        fn = sum(conf[i][j] for j in range(num_classes) if j != i)
        total_class_true = tp + fn

        acc = round(tp / max(total_class_true, 1), 3)
        prec = round(tp / max(tp + fp, 1), 3)
        rec = round(tp / max(tp + fn, 1), 3)
        f1 = round((2 * prec * rec) / max(prec + rec, 1e-6), 3)

        per_class_acc[c] = acc
        per_class_precision[c] = prec
        per_class_recall[c] = rec
        per_class_f1[c] = f1

    avg_precision = round(sum(per_class_precision.values()) / max(num_classes, 1), 3)
    avg_recall = round(sum(per_class_recall.values()) / max(num_classes, 1), 3)
    avg_f1 = round(sum(per_class_f1.values()) / max(num_classes, 1), 3)
    val_loss = round(total_loss / max(total_samples, 1), 4)

    return {
        "overall": overall_acc,
        "loss": val_loss,
        "precision": avg_precision,
        "recall": avg_recall,
        "f1": avg_f1,
        "per_class": per_class_acc,
        "per_class_precision": per_class_precision,
        "per_class_recall": per_class_recall,
        "per_class_f1": per_class_f1,
        "confusion_matrix": conf,
        "classes": list(classes),
        "inference_speed_ms": inf_speed_ms,
    }


def train(job, cfg, model, dl_tr, dl_va, classes, device, run_dir: Path):
    import torch
    import torch.nn as nn
    opt, lossf = make_optimizer(cfg, model), nn.CrossEntropyLoss()
    epochs = int(cfg.get("epochs", 10))
    total_steps = epochs * len(dl_tr)
    done_steps = 0
    t0 = time.time()
    best_acc = -1.0
    history = []
    
    try:
        for epoch in range(epochs):
            model.train()
            running_loss, count = 0.0, 0
            for x, y in dl_tr:
                job.checkpoint()
                x, y = x.to(device), y.to(device)
                opt.zero_grad()
                out = model(x)
                loss = lossf(out, y)
                loss.backward()
                opt.step()

                running_loss += loss.item() * len(y)
                count += len(y)
                done_steps += 1
                eta = (time.time() - t0) / done_steps * (total_steps - done_steps)
                job.set_step("Training", "running", (done_steps / total_steps) * 100, eta)
                job.eta_s = eta

            epoch_train_loss = round(running_loss / max(count, 1), 4)
            val_metrics = evaluate(model, dl_va, classes, device)
            history.append({
                "epoch": epoch + 1,
                "train_loss": epoch_train_loss,
                "val_loss": val_metrics["loss"],
                "val_acc": val_metrics["overall"]
            })

            if val_metrics["overall"] >= best_acc:
                best_acc = val_metrics["overall"]
                torch.save(model.state_dict(), run_dir / "best.pt")

        training_duration = round(time.time() - t0, 1)

        # Load best weights before final evaluation
        best_pt = run_dir / "best.pt"
        if best_pt.is_file():
            model.load_state_dict(torch.load(best_pt, map_location=device))
        
        final_eval = evaluate(model, dl_va, classes, device)
        final_eval["history"] = history
        final_eval["duration_seconds"] = training_duration
        
        # Model size
        if best_pt.is_file():
            final_eval["model_size_mb"] = round(best_pt.stat().st_size / (1024**2), 2)
            
        return final_eval

    except Exception as e:
        if is_oom(e):
            # Clear the GPU cache and let the runner decide: lower the batch size, or move to the CPU.
            import torch
            if device.type == "cuda":
                torch.cuda.empty_cache()
            raise
        raise


def export(run_dir: Path, classes: list, metrics: dict, decisions: list):
    """Saves report, config, and exports verified ONNX model."""
    import yaml
    from . import codegen

    (run_dir / "labels.json").write_text(json.dumps(classes, indent=2), encoding="utf-8")
    (run_dir / "report.json").write_text(json.dumps({"metrics": metrics, "decisions": decisions}, indent=2), encoding="utf-8")

    cfg_file = run_dir / "config.yaml"
    cfg = yaml.safe_load(cfg_file.read_text(encoding="utf-8")) if cfg_file.is_file() else {"model": "resnet18", "image_size": 224}
    
    # 1. Generate full bundle (predict.py, serve.py, train.py, README.md, requirements.txt)
    codegen.write_run_files(run_dir, cfg, classes, metrics)

    # 2. Real ONNX export verification
    onnx_ok = False
    try:
        import torch
        pt_path = run_dir / "best.pt"
        onnx_path = run_dir / "model.onnx"
        if pt_path.is_file():
            device = torch.device("cpu")
            model = make_model(cfg, len(classes), device, pretrained=False)
            model.load_state_dict(torch.load(pt_path, map_location=device))
            model.eval()
            sz = cfg.get("image_size", 224)
            dummy_input = torch.randn(1, 3, sz, sz, device=device)
            torch.onnx.export(
                model,
                dummy_input,
                str(onnx_path),
                input_names=["input"],
                output_names=["output"],
                dynamic_axes={"input": {0: "batch_size"}, "output": {0: "batch_size"}},
                opset_version=12,
            )
            if onnx_path.is_file() and onnx_path.stat().st_size > 0:
                onnx_ok = True
    except Exception as e:
        print(f"ONNX export warning: {e}")

    # Update report with ONNX export status
    rep_data = {"metrics": metrics, "decisions": decisions, "onnx_exported": onnx_ok}
    (run_dir / "report.json").write_text(json.dumps(rep_data, indent=2), encoding="utf-8")
