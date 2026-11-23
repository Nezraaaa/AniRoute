"""Find the model's most confident CORRECT detections on the held-out test split, for the Results slide.

  python ml/scripts/select_correct_detections.py [--per-class 3]

A detection counts as correct only if it matches a hand-labelled box of the same class with IoU >= 0.5.
The script runs the deployed detector (same code path and settings as the app) on every test image and
ranks images by their best correct detection. It then saves annotated copies to
ml/reports/correct_detections/:
- green: the model's correct boxes, with their confidence
- white, dashed: the hand-made label each green box matched

It also writes summary.json: how many correct detections reach each confidence level. This shows how
typical the selected examples are. The examples are best cases by design; the Evaluation slide reports
the full test-split numbers.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import cv2
import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
os.environ.setdefault("ANIROUTE_VISION_WARMUP", "false")

from backend.vision.config import VisionSettings  # noqa: E402
from backend.vision.ensemble import HazardDetector  # noqa: E402

TEST = REPO / "ml" / "data" / "aniroute" / "test"
OUT = REPO / "ml" / "reports" / "correct_detections"
CLASSES = {0: "pothole", 1: "severe_road_damage"}
LABEL = {"pothole": "Pothole", "severe_road_damage": "Severe road damage"}


def iou(a, b) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def ground_truth(label_path: Path, w: int, h: int):
    boxes = []
    if label_path.exists():
        for line in label_path.read_text().splitlines():
            parts = line.split()
            if len(parts) != 5:
                continue
            c, cx, cy, bw, bh = int(parts[0]), *map(float, parts[1:])
            boxes.append((CLASSES[c], ((cx - bw / 2) * w, (cy - bh / 2) * h, (cx + bw / 2) * w, (cy + bh / 2) * h)))
    return boxes


def dashed_rect(img, p1, p2, color, thickness=2, dash=12):
    x1, y1 = p1
    x2, y2 = p2
    for x in range(x1, x2, dash * 2):
        cv2.line(img, (x, y1), (min(x + dash, x2), y1), color, thickness)
        cv2.line(img, (x, y2), (min(x + dash, x2), y2), color, thickness)
    for y in range(y1, y2, dash * 2):
        cv2.line(img, (x1, y), (x1, min(y + dash, y2)), color, thickness)
        cv2.line(img, (x2, y), (x2, min(y + dash, y2)), color, thickness)


def annotate(image, matches):
    img = image.copy()
    scale = max(1.0, img.shape[1] / 720)
    for _, _, _, gbox in matches:   # only the human label each detection matched
        x1, y1, x2, y2 = map(int, gbox)
        dashed_rect(img, (x1, y1), (x2, y2), (255, 255, 255), max(2, int(2 * scale)))
    for hazard, conf, box, _ in matches:
        x1, y1, x2, y2 = map(int, box)
        color = (80, 200, 60)
        cv2.rectangle(img, (x1, y1), (x2, y2), color, max(3, int(3 * scale)))
        text = f"{LABEL[hazard]} {conf:.0%}"
        fs = 0.95 * scale
        (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, fs, max(2, int(2 * scale)))
        ty = max(th + 10, y1 - 8)
        cv2.rectangle(img, (x1, ty - th - 10), (x1 + tw + 12, ty + 6), color, -1)
        cv2.putText(img, text, (x1 + 6, ty - 2), cv2.FONT_HERSHEY_SIMPLEX, fs, (255, 255, 255), max(2, int(2 * scale)), cv2.LINE_AA)
    return img


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--per-class", type=int, default=3)
    args = parser.parse_args()
    detector = HazardDetector(VisionSettings(warmup=False))
    if not detector.load():
        raise SystemExit("No model available.")
    threshold = detector.settings.conf_a
    candidates = {c: [] for c in CLASSES.values()}
    all_correct = []
    for path in sorted((TEST / "images").glob("*")):
        image = cv2.imread(str(path))
        if image is None:
            continue
        h, w = image.shape[:2]
        gts = ground_truth(TEST / "labels" / f"{path.stem}.txt", w, h)
        result = detector.detect(image, clahe="off")
        used, matches = set(), []
        for det in sorted(result.detections, key=lambda d: -d.confidence):
            best, best_iou = None, 0.5
            for k, (gclass, gbox) in enumerate(gts):
                if k in used or gclass != det.hazard_type:
                    continue
                v = iou(det.box, gbox)
                if v >= best_iou:
                    best, best_iou = k, v
            if best is not None:
                used.add(best)
                matches.append((det.hazard_type, det.confidence, det.box, gts[best][1]))
                all_correct.append(det.confidence)
        wrong = len(result.detections) - len(matches)
        for hazard in CLASSES.values():
            mine = [m for m in matches if m[0] == hazard]
            if mine and wrong == 0:   # only images with no false alarms, so the example is clean
                candidates[hazard].append((max(m[1] for m in mine), path, matches))
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.jpg"):
        old.unlink()
    picked = []
    for hazard, items in candidates.items():
        for rank, (conf, path, matches) in enumerate(sorted(items, key=lambda x: -x[0])[: args.per_class], 1):
            image = cv2.imread(str(path))
            name = f"{hazard}_{rank}_{int(round(conf * 100))}.jpg"
            cv2.imwrite(str(OUT / name), annotate(image, matches), [cv2.IMWRITE_JPEG_QUALITY, 92])
            picked.append({"file": name, "class": hazard, "best_confidence": round(conf, 3), "source": path.name,
                           "size": [image.shape[1], image.shape[0]],
                           "boxes": [{"class": m[0], "confidence": round(m[1], 3), "box": [round(v, 1) for v in m[2]]} for m in matches]})
    conf = np.array(all_correct)
    summary = {
        "split": "test", "images": len(list((TEST / "images").glob("*"))), "threshold": threshold,
        "correct_detections": int(conf.size),
        "correct_at_or_above": {f"{p}%": int((conf >= p / 100).sum()) for p in (50, 60, 70, 80, 90)},
        "picked": picked,
        "note": "Best-case examples: correct detections (IoU >= 0.5 with a hand-labelled box of the same class) "
                "on images with no false alarms. Overall test metrics are in metrics.json / high_confidence_profile.json.",
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
