"""Model Doctor: comprehensive evaluation diagnostics, overfitting detection,
confusion pair identification, and actionable recommendation ladder.
"""
from __future__ import annotations


def diagnose(metrics: dict, cfg: dict, counts: dict) -> dict:
    if not metrics:
        return {"headline": "No evaluation metrics available yet.", "detail": "Train a model first to run diagnosis.", "options": []}

    per_acc = metrics.get("per_class") or {}
    per_prec = metrics.get("per_class_precision") or {}
    per_rec = metrics.get("per_class_recall") or {}
    per_f1 = metrics.get("per_class_f1") or {}
    overall = float(metrics.get("overall", 0.0))
    conf_matrix = metrics.get("confusion_matrix")
    classes = metrics.get("classes") or list(per_acc.keys())
    history = metrics.get("history") or []
    
    confirmed_problems = []
    possible_explanations = []
    options = []

    # 1. Overfitting check (from loss curve history)
    if len(history) >= 2:
        first_val_loss = history[0].get("val_loss", 0.0)
        last_val_loss = history[-1].get("val_loss", 0.0)
        first_tr_loss = history[0].get("train_loss", 0.0)
        last_tr_loss = history[-1].get("train_loss", 0.0)
        
        # If train loss dropped significantly but validation loss increased
        if last_tr_loss < first_tr_loss * 0.7 and last_val_loss > first_val_loss * 1.15:
            confirmed_problems.append(
                "Overfitting detected: training loss decreased while validation loss increased. The model memorized pictures instead of learning general patterns."
            )
            options.append({
                "id": "regularize",
                "title": "Add stronger regularization",
                "tag": "Fix overfitting",
                "effect": "Reduces learning rate and applies gentle data jitter to encourage generalization.",
                "recommended": True,
            })

    # 2. Weakest class & Confusion analysis
    weakest = min(per_acc, key=per_acc.get) if per_acc else None
    weakest_score = per_acc.get(weakest, 1.0) if weakest else 1.0
    
    if weakest and weakest_score < overall - 0.05:
        prec = per_prec.get(weakest, 0.0)
        rec = per_rec.get(weakest, 0.0)
        
        if rec < prec:
            confirmed_problems.append(
                f"Low Recall on '{weakest}' ({int(rec * 100)}%): the model frequently misses real {weakest} pictures."
            )
        elif prec < rec:
            confirmed_problems.append(
                f"Low Precision on '{weakest}' ({int(prec * 100)}%): the model produces false alarms by mislabeling other things as '{weakest}'."
            )
        else:
            confirmed_problems.append(
                f"'{weakest}' has noticeably lower accuracy ({int(weakest_score * 100)}%) than the overall average ({int(overall * 100)}%)."
            )

    # 3. Confused class pairs (from confusion matrix)
    confused_pair = None
    if conf_matrix and len(classes) >= 2:
        max_error = 0
        for i in range(len(classes)):
            for j in range(len(classes)):
                if i != j and conf_matrix[i][j] > max_error:
                    max_error = conf_matrix[i][j]
                    confused_pair = (classes[i], classes[j], max_error)
        
        if confused_pair and confused_pair[2] >= 3:
            confirmed_problems.append(
                f"Confusion between '{confused_pair[0]}' and '{confused_pair[1]}': {confused_pair[2]} pictures of '{confused_pair[0]}' were misclassified as '{confused_pair[1]}'."
            )

    # 4. Dataset size and balance impact
    total_samples = sum(counts.values()) if counts else 0
    big = max(counts.values()) if counts else 0
    small = min(counts.values()) if counts else 0
    
    if weakest and counts.get(weakest, big) < 0.6 * big:
        possible_explanations.append(
            f"Class imbalance: you have {counts[weakest]} '{weakest}' images vs {big} in the largest category. The AI has less exposure to '{weakest}'."
        )
        if cfg.get("balance_choice") != "balance_auto":
            options.append({
                "id": "balance",
                "title": "Enable automatic class balancing",
                "tag": "Quick win",
                "effect": f"Weights the training loss so '{weakest}' samples contribute equally to gradient updates.",
                "recommended": not options,
            })
        options.append({
            "id": "add_pictures",
            "title": f"Add more '{weakest}' pictures",
            "tag": "Best data fix",
            "effect": f"Adding 20-50 more diverse {weakest} photos is the most direct way to resolve this.",
            "recommended": False,
        })

    if total_samples > 0 and total_samples < 150:
        possible_explanations.append(
            f"Small dataset ({total_samples} total images): deep neural networks benefit substantially from larger sample diversity."
        )

    # 5. Model capacity options
    if overall < 0.90 and cfg.get("model") in ("resnet18", "mobilenet_v3_large"):
        options.append({
            "id": "bigger",
            "title": "Switch to ResNet-50",
            "tag": "Higher capacity",
            "effect": "A larger model with higher representational capacity. Takes slightly longer to train.",
            "recommended": not options,
        })

    if overall < 0.94:
        options.append({
            "id": "longer",
            "title": "Train for 5 more epochs",
            "tag": "Fine-tune",
            "effect": "Allows the optimizer to settle into lower loss minima without changing architecture.",
            "recommended": not options,
        })

    # Compose headline
    if overall >= 0.96:
        headline = f"Excellent model performance ({int(overall * 100)}% overall accuracy)."
    elif weakest and weakest_score < overall - 0.05:
        headline = f"Model struggles primarily with '{weakest}' ({int(weakest_score * 100)}% vs {int(overall * 100)}% average)."
    elif confirmed_problems:
        headline = "A few specific performance bottlenecks were identified."
    else:
        headline = f"Solid baseline performance ({int(overall * 100)}% accuracy)."

    detail_parts = []
    if confirmed_problems:
        detail_parts.append("Confirmed issues: " + "; ".join(confirmed_problems))
    if possible_explanations:
        detail_parts.append("Contributing factors: " + "; ".join(possible_explanations))
    if not detail_parts:
        detail_parts.append("The model performs evenly across all evaluated categories.")

    return {
        "headline": headline,
        "overall": overall,
        "source": "exam pictures" if metrics.get("source") == "exam" else "validation pictures",
        "weakest": weakest,
        "loss": metrics.get("loss"),
        "precision": metrics.get("precision"),
        "recall": metrics.get("recall"),
        "f1": metrics.get("f1"),
        "duration_seconds": metrics.get("duration_seconds"),
        "inference_speed_ms": metrics.get("inference_speed_ms"),
        "model_size_mb": metrics.get("model_size_mb"),
        "confirmed_problems": confirmed_problems,
        "possible_explanations": possible_explanations,
        "confusion_matrix": conf_matrix,
        "classes": classes,
        "detail": " ".join(detail_parts),
        "options": options,
    }


def apply(action: str, cfg: dict) -> dict:
    cfg = dict(cfg)
    if action == "longer":
        cfg["epochs"] = min(50, max(cfg.get("epochs", 10) + 5, int(cfg.get("epochs", 10) * 1.5)))
    elif action == "bigger":
        cfg["model"] = "resnet50"
    elif action == "balance":
        cfg["balance_choice"] = "balance_auto"
    elif action == "regularize":
        cfg["learning_rate"] = float(cfg.get("learning_rate", 3e-4)) * 0.5
    else:
        raise ValueError(f"Unknown action {action}")
    return cfg
