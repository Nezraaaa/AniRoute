"""Crack-class (severe_road_damage) evaluation figures for the presentation.

  python ml/scripts/crack_report.py

Runs the deployed detector, with the app's settings, on the held-out test split. The app reports cracks
only; see ml/reports/pothole_label_audit.md. A detection is correct if it overlaps a hand-labelled crack
box with IoU >= 0.5 (greedy matching, highest confidence first).

Writes to ml/reports/crack/:
- crack_metrics.json: AP@0.5, and precision / recall / F1 at the app threshold, compared against
  metrics.json and high_confidence_profile.json
- pr_curve.png: precision-recall curve
- threshold_chart.png: precision and recall against the confidence threshold, with the app's 0.40 marked
- result_counts.png: correct alerts, false alarms and misses at 0.40
- miss_rate_by_size.json: same size buckets as ml/evaluation/metrics.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import cv2
import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "ml"))
os.environ.setdefault("ANIROUTE_VISION_WARMUP", "false")

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from backend.vision.config import VisionSettings  # noqa: E402
from backend.vision.ensemble import HazardDetector  # noqa: E402
from evaluation.metrics import average_precision  # noqa: E402

TEST = REPO / "ml" / "data" / "aniroute" / "test"
OUT = REPO / "ml" / "reports" / "crack"
CRACK = 1   # class id of severe_road_damage in data.yaml
GREEN, RED, AMBER, INK = "#1d6548", "#dc2626", "#f5b02e", "#1e241f"


def iou(a, b) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def size_bucket(area: float) -> str:
    return "small" if area < 0.005 else "medium" if area < 0.05 else "large"


def main() -> None:
    settings = VisionSettings(warmup=False)
    threshold = settings.conf_a
    detector = HazardDetector(settings)
    if not detector.load():
        raise SystemExit("No model available.")
    scores, hits = [], []                  # every crack prediction: confidence, matched?
    gt_total = 0
    gt_records = []                        # (size bucket, best confidence that matched it or 0)
    for path in sorted((TEST / "images").glob("*")):
        image = cv2.imread(str(path))
        if image is None:
            continue
        h, w = image.shape[:2]
        gts = []
        label = TEST / "labels" / f"{path.stem}.txt"
        if label.exists():
            for line in label.read_text().splitlines():
                p = line.split()
                if len(p) == 5 and int(p[0]) == CRACK:
                    cx, cy, bw, bh = map(float, p[1:])
                    gts.append(((cx - bw / 2) * w, (cy - bh / 2) * h, (cx + bw / 2) * w, (cy + bh / 2) * h, bw * bh))
        gt_total += len(gts)
        dets = sorted((d for d in detector.detect(image, conf=0.01, clahe="off").detections if d.hazard_type == "severe_road_damage"),
                      key=lambda d: -d.confidence)
        matched_conf = [0.0] * len(gts)
        used = set()
        for d in dets:
            best, best_iou = None, 0.5
            for k, g in enumerate(gts):
                if k in used:
                    continue
                v = iou(d.box, g[:4])
                if v >= best_iou:
                    best, best_iou = k, v
            scores.append(d.confidence)
            hits.append(best is not None)
            if best is not None:
                used.add(best)
                matched_conf[best] = d.confidence
        gt_records += [(size_bucket(g[4]), c) for g, c in zip(gts, matched_conf)]

    order = np.argsort(-np.array(scores))
    s = np.array(scores)[order]
    tp = np.cumsum(np.array(hits)[order])
    fp = np.cumsum(~np.array(hits)[order])
    recall = tp / max(gt_total, 1)
    precision = tp / np.maximum(tp + fp, 1)
    ap50 = average_precision(recall, precision)

    def at(thr):
        k = int((s >= thr).sum())
        t, f = (int(tp[k - 1]), int(fp[k - 1])) if k else (0, 0)
        p, r = (t / (t + f) if t + f else 1.0), t / gt_total
        return {"threshold": thr, "precision": round(p, 4), "recall": round(r, 4),
                "f1": round(2 * p * r / (p + r) if p + r else 0.0, 4), "correct": t, "false_alarms": f, "missed": gt_total - t}

    app = at(threshold)
    sizes = {}
    for bucket in ("small", "medium", "large"):
        rows = [c for b, c in gt_records if b == bucket]
        missed = sum(1 for c in rows if c < threshold)
        sizes[bucket] = {"objects": len(rows), "missed": missed, "miss_rate": round(missed / len(rows), 3) if rows else None}

    OUT.mkdir(parents=True, exist_ok=True)
    reference = json.loads((REPO / "ml" / "reports" / "metrics.json").read_text())["per_class"]["severe_road_damage"]
    deployed_ref = json.loads((REPO / "ml" / "reports" / "high_confidence_profile.json").read_text())["test"]["per_class"]["severe_road_damage"]
    summary = {"class": "severe_road_damage (cracks)", "split": "test", "labelled_cracks": gt_total, "ap50": round(ap50, 4),
               "at_app_threshold": app, "miss_rate_by_size_at_app_threshold": sizes,
               "cross_check": {"metrics.json ap50": reference["ap50"], "metrics.json ap50_95": reference["ap50_95"],
                               "high_confidence_profile precision": deployed_ref["precision"], "recall": deployed_ref["recall"]}}
    (OUT / "crack_metrics.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 12})
    # PR curve
    fig, ax = plt.subplots(figsize=(6.4, 4.6), dpi=160)
    ax.plot(recall, precision, color=GREEN, lw=2.4)
    ax.scatter([app["recall"]], [app["precision"]], s=90, color=AMBER, zorder=5, edgecolor=INK)
    ax.annotate(f"app threshold {threshold:.2f}\nprecision {app['precision']:.0%}", (app["recall"], app["precision"]),
                xytext=(app["recall"] + 0.12, app["precision"] - 0.08), arrowprops=dict(arrowstyle="->", color=INK), fontsize=11)
    ax.set(xlim=(0, 1), ylim=(0, 1.02), xlabel="Recall (cracks found)", ylabel="Precision (alerts that are real)",
           title="Cracks: precision–recall curve")
    ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(OUT / "pr_curve.png"); plt.close(fig)
    # precision & recall vs threshold
    grid = np.linspace(0.05, 0.75, 71)
    pts = [at(float(g)) for g in grid]
    fig, ax = plt.subplots(figsize=(6.4, 4.6), dpi=160)
    ax.plot(grid, [p["precision"] for p in pts], color=GREEN, lw=2.4, label="Precision")
    ax.plot(grid, [p["recall"] for p in pts], color=RED, lw=2.4, label="Recall")
    ax.axvline(threshold, color=AMBER, lw=2, ls="--")
    ax.text(threshold + 0.01, 0.95, f"app: {threshold:.2f}", color=INK, fontsize=11)
    ax.set(xlim=(0.05, 0.75), ylim=(0, 1.02), xlabel="Confidence threshold", ylabel="Score", title="Cracks: choosing the alert threshold")
    ax.legend(loc="center right"); ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(OUT / "threshold_chart.png"); plt.close(fig)
    # counts at the app threshold
    fig, ax = plt.subplots(figsize=(6.4, 3.6), dpi=160)
    labels = ["Correct alerts", "False alarms", "Missed cracks"]
    values = [app["correct"], app["false_alarms"], app["missed"]]
    bars = ax.barh(labels[::-1], values[::-1], color=[RED, AMBER, GREEN][::-1] if False else ["#9aa59c", AMBER, GREEN])
    for bar, v in zip(bars, values[::-1]):
        ax.text(bar.get_width() + 2, bar.get_y() + bar.get_height() / 2, str(v), va="center", fontsize=12)
    ax.set(xlabel=f"Number of cracks / alerts at threshold {threshold:.2f}", title="Cracks on 444 held-out images")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(); fig.savefig(OUT / "result_counts.png"); plt.close(fig)
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
