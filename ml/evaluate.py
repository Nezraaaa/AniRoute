"""AniRoute evaluation: every number in the app, docs and slides comes from here.

Sub-commands (run from the repository root with the project virtualenv):

  python ml/evaluate.py test        --weights backend/models/aniroute-hazards-v1.pt --data ml/data/aniroute/data.yaml
  python ml/evaluate.py compare     --runs ml/runs/E0 ml/runs/E1 ... --data ml/data/aniroute/data.yaml
  python ml/evaluate.py latency     --images backend/samples
  python ml/evaluate.py obstruction --data ml/data/obstruction_test/data.yaml
  python ml/evaluate.py smoothing   --video backend/samples/road_demo.mp4

`test` uses the app's own preprocessing (backend/vision/preprocess.py), picks the
operating confidence threshold on the *validation* split (max mean F1) and then
reports the *test* split once, so the test set never influences any choice.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import random
import subprocess
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "ml"))

from backend.vision.annotate import corridor_polygon, draw_detections  # noqa: E402
from backend.vision.config import RoiSettings, VisionSettings  # noqa: E402
from backend.vision.detector import YoloModel  # noqa: E402
from backend.vision.ensemble import HazardDetector  # noqa: E402
from backend.vision.preprocess import luminance_stats, run_pipeline, unletterbox_boxes  # noqa: E402
from backend.vision.smoothing import TemporalHazardFilter  # noqa: E402
from evaluation import plots  # noqa: E402
from evaluation.dataset import YoloDataset, filename_tags, read_labels  # noqa: E402
from evaluation.metrics import ImageBoxes, confusion_and_errors, evaluate, size_bucket  # noqa: E402

REPORTS = Path(os.getenv("ANIROUTE_REPORTS_DIR", str(REPO / "ml" / "reports")))
DEFAULT_WEIGHTS = REPO / "backend" / "models" / "aniroute-hazards-v1.pt"
DEFAULT_DATA = REPO / "ml" / "data" / "aniroute" / "data.yaml"
DARK_LUMA = 95.0
NMS_IOU = 0.6
MAP_CONF = 0.001   # keep low-confidence boxes so the PR curve is complete


# --------------------------------------------------------------------------- helpers
def write_json(name: str, payload: dict) -> Path:
    REPORTS.mkdir(parents=True, exist_ok=True)
    path = REPORTS / name
    path.write_text(json.dumps(payload, indent=2, default=_json_default), encoding="utf-8")
    print(f"  wrote {display(path)}")
    return path


def display(path: Path) -> str:
    try:
        return str(path.relative_to(REPO))
    except ValueError:
        return str(path)


def _json_default(value):
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, Path):
        return str(value)
    raise TypeError(type(value))


def git_commit() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=REPO, text=True,
                                       stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def file_fingerprint(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()[:12]


def machine() -> dict:
    return {"platform": platform.platform(), "processor": platform.processor(), "python": platform.python_version()}


class Predictor:
    """Runs a YOLO model through the app's exact preprocessing pipeline."""

    def __init__(self, weights: Path, dataset_names: list[str], *, imgsz: int = 640, clahe: str = "auto",
                 device: str = "cpu", model_format: str = "pt") -> None:
        self.model = YoloModel("eval", Path(weights), model_format=model_format, device=device, imgsz=imgsz)
        if not self.model.load():
            raise SystemExit(f"Could not load weights {weights}: {self.model.error}")
        self.imgsz = imgsz
        self.clahe = clahe
        self.class_map = {}
        for model_id, name in self.model.class_names.items():
            if name in dataset_names:
                self.class_map[model_id] = dataset_names.index(name)
        if not self.class_map:
            print("  ! model class names do not match the dataset names; assuming identical order")
            self.class_map = {i: i for i in range(len(dataset_names))}

    def __call__(self, image_bgr: np.ndarray, conf: float = MAP_CONF, clahe: str | None = None) -> tuple[ImageBoxes, dict]:
        pipeline = run_pipeline(image_bgr, size=self.imgsz, clahe=clahe or self.clahe)
        raw, inference_ms = self.model.predict(pipeline.model_input, conf=conf, iou=NMS_IOU)
        raw = [box for box in raw if box.class_id in self.class_map]
        boxes = unletterbox_boxes(np.array([box.xyxy for box in raw], dtype=float).reshape(-1, 4), pipeline.letterbox)
        prediction = ImageBoxes(
            boxes, np.array([self.class_map[box.class_id] for box in raw], dtype=int),
            np.array([box.confidence for box in raw], dtype=float),
        )
        return prediction, {"preprocess_ms": pipeline.total_ms, "inference_ms": inference_ms,
                            "clahe_applied": pipeline.clahe_applied}


def collect(dataset: YoloDataset, split: str, predictor: Predictor, clahe: str | None = None,
            limit: int | None = None) -> tuple[list[ImageBoxes], list[ImageBoxes], list[Path]]:
    images = dataset.images(split)
    if limit:
        images = images[:limit]
    if not images:
        raise SystemExit(f"No images found for split '{split}' in {dataset.yaml_path}")
    gts, preds = [], []
    started = time.perf_counter()
    for index, path in enumerate(images, 1):
        image = cv2.imread(str(path))
        if image is None:
            continue
        height, width = image.shape[:2]
        gt = read_labels(path, width, height)
        mean, _ = luminance_stats(image)
        gt.meta = {"path": str(path), "width": width, "height": height, "luma": round(mean, 1),
                   "tags": sorted(filename_tags(path))}
        prediction, timing = predictor(image, clahe=clahe)
        prediction.image_id = gt.image_id
        prediction.meta = timing
        gts.append(gt)
        preds.append(prediction)
        if index % 50 == 0:
            print(f"    {split}: {index}/{len(images)} images ({time.perf_counter() - started:.0f}s)")
    return gts, preds, images


def summarize(gts, preds, names: list[str], conf: float) -> dict:
    ev = evaluate(gts, preds, names)
    cm = confusion_and_errors(gts, preds, len(names), conf)
    per_class = {}
    for class_id, name in enumerate(names):
        per_class[name] = {**ev["per_class"][name], **cm["per_class"][class_id]}
    return {
        "images": len(gts),
        "instances": int(sum(len(g.classes) for g in gts)),
        "map50": ev["map50"],
        "map50_95": ev["map50_95"],
        "precision": cm["overall"]["precision"],
        "recall": cm["overall"]["recall"],
        "f1": cm["overall"]["f1"],
        "tp": cm["overall"]["tp"], "fp": cm["overall"]["fp"], "fn": cm["overall"]["fn"],
        "per_class": per_class,
        "_ev": ev, "_cm": cm,
    }


def public(summary: dict) -> dict:
    return {key: value for key, value in summary.items() if not key.startswith("_")}


# --------------------------------------------------------------------------- error gallery
def write_error_gallery(errors: list[dict], names: list[str], gts: list[ImageBoxes], preds: list[ImageBoxes],
                        conf: float, per_kind: int = 6) -> dict:
    gallery = REPORTS / "error_gallery"
    for kind_dir in ("false_positives", "false_negatives", "misclassified"):
        target = gallery / kind_dir
        target.mkdir(parents=True, exist_ok=True)
        for old in target.glob("*.jpg"):
            old.unlink()
    by_image = {gt.image_id: (gt, pred) for gt, pred in zip(gts, preds)}
    folders = {"false_positive": "false_positives", "false_negative": "false_negatives", "misclassified": "misclassified"}
    captions: dict[str, str] = {}
    rng = random.Random(42)
    grouped = defaultdict(list)
    for error in errors:
        grouped[error["kind"]].append(error)
    for kind, items in grouped.items():
        rng.shuffle(items)
        # Prefer the most confident false positives: they are the most instructive.
        if kind == "false_positive":
            items.sort(key=lambda e: -e.get("score", 0))
        for index, error in enumerate(items[:per_kind], 1):
            gt, pred = by_image[error["image_id"]]
            image = cv2.imread(gt.meta["path"])
            if image is None:
                continue
            canvas = image.copy()
            for box in gt.boxes:   # ground truth in white
                x1, y1, x2, y2 = (int(v) for v in box)
                cv2.rectangle(canvas, (x1, y1), (x2, y2), (255, 255, 255), 2, cv2.LINE_AA)
            keep = pred.scores >= conf
            canvas = draw_detections(canvas, [
                {"box": b.tolist(), "hazard_type": names[c], "label": plots.pretty(names[c]), "confidence": float(s)}
                for b, c, s in zip(pred.boxes[keep], pred.classes[keep], pred.scores[keep])
            ])
            x1, y1, x2, y2 = (int(v) for v in error["box"])
            cv2.rectangle(canvas, (x1 - 4, y1 - 4), (x2 + 4, y2 + 4), (0, 255, 255), 3, cv2.LINE_AA)  # highlighted error
            area = gt.meta["width"] * gt.meta["height"]
            bucket = size_bucket(error["box"], area)
            light = "dark frame" if gt.meta["luma"] < DARK_LUMA else "normal light"
            if kind == "false_negative":
                caption = f"Missed {plots.pretty(names[error['true_class']]).lower()} · {bucket} object · {light}"
            elif kind == "false_positive":
                caption = f"False alarm: {plots.pretty(names[error['pred_class']]).lower()} {error['score']:.0%} · {bucket} box · {light}"
            else:
                caption = (f"{plots.pretty(names[error['true_class']])} predicted as "
                           f"{plots.pretty(names[error['pred_class']]).lower()} {error['score']:.0%} · {light}")
            name = f"{index:02d}_{Path(gt.meta['path']).stem[:40]}.jpg"
            scale = 900 / max(canvas.shape[:2])
            if scale < 1:
                canvas = cv2.resize(canvas, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
            cv2.imwrite(str(gallery / folders[kind] / name), canvas, [cv2.IMWRITE_JPEG_QUALITY, 85])
            captions[f"{folders[kind]}/{name}"] = caption
    (gallery / "captions.json").write_text(json.dumps(captions, indent=2), encoding="utf-8")
    return captions


def error_breakdown(errors: list[dict], gts: list[ImageBoxes], names: list[str]) -> dict:
    """Objective error statistics: miss rate by object size and lighting, false alarms by class."""
    totals_by_size, misses_by_size = Counter(), Counter()
    totals_by_light, misses_by_light = Counter(), Counter()
    for gt in gts:
        area = gt.meta["width"] * gt.meta["height"]
        light = "dark" if gt.meta["luma"] < DARK_LUMA else "normal"
        for box in gt.boxes:
            totals_by_size[size_bucket(box, area)] += 1
            totals_by_light[light] += 1
    image_meta = {gt.image_id: gt.meta for gt in gts}
    for error in errors:
        if error["kind"] != "false_negative":
            continue
        meta = image_meta[error["image_id"]]
        misses_by_size[size_bucket(error["box"], meta["width"] * meta["height"])] += 1
        misses_by_light["dark" if meta["luma"] < DARK_LUMA else "normal"] += 1
    fp_by_class = Counter(names[e["pred_class"]] for e in errors if e["kind"] == "false_positive")
    confusions = Counter(f"{names[e['true_class']]} → {names[e['pred_class']]}" for e in errors if e["kind"] == "misclassified")
    return {
        "miss_rate_by_size": {k: {"objects": totals_by_size[k], "missed": misses_by_size[k],
                                  "miss_rate": round(misses_by_size[k] / totals_by_size[k], 3) if totals_by_size[k] else None}
                              for k in ("small", "medium", "large")},
        "miss_rate_by_lighting": {k: {"objects": totals_by_light[k], "missed": misses_by_light[k],
                                      "miss_rate": round(misses_by_light[k] / totals_by_light[k], 3) if totals_by_light[k] else None}
                                  for k in ("normal", "dark")},
        "false_positives_by_class": dict(fp_by_class),
        "misclassification_pairs": dict(confusions),
    }


def write_error_analysis(breakdown: dict, split: str, conf: float) -> None:
    lines = [
        "# Error analysis (auto-generated)",
        "",
        f"Split: `{split}` · operating confidence {conf:.2f} · IoU 0.5. Regenerate with `python ml/evaluate.py test`.",
        "",
        "## Missed objects by size (fraction of the image area: small < 0.5%, medium < 5%)",
        "",
        "| Size | Objects | Missed | Miss rate |",
        "| --- | --- | --- | --- |",
    ]
    for size, row in breakdown["miss_rate_by_size"].items():
        rate = "–" if row["miss_rate"] is None else f"{row['miss_rate']:.0%}"
        lines.append(f"| {size} | {row['objects']} | {row['missed']} | {rate} |")
    lines += ["", "## Missed objects by lighting (dark = LAB lightness mean < 95)", "",
              "| Lighting | Objects | Missed | Miss rate |", "| --- | --- | --- | --- |"]
    for light, row in breakdown["miss_rate_by_lighting"].items():
        rate = "–" if row["miss_rate"] is None else f"{row['miss_rate']:.0%}"
        lines.append(f"| {light} | {row['objects']} | {row['missed']} | {rate} |")
    lines += ["", "## False alarms by predicted class", ""]
    lines += [f"- {plots.pretty(k)}: {v}" for k, v in breakdown["false_positives_by_class"].items()] or ["- none"]
    lines += ["", "## Class confusions (true → predicted)", ""]
    lines += [f"- {k}: {v}" for k, v in breakdown["misclassification_pairs"].items()] or ["- none"]
    lines += ["", "## Team interpretation", "",
              "_Look through `ml/reports/error_gallery/` and write 3–5 sentences here on why the model fails "
              "(for example faded cracks, wet asphalt that looks like a pothole, motion blur, shadows). "
              "This section is kept when the file is regenerated only if you copy it into docs/EVALUATION.md._", ""]
    (REPORTS / "error_analysis.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"  wrote {display(REPORTS / 'error_analysis.md')}")


# --------------------------------------------------------------------------- sub-commands
def cmd_test(args) -> None:
    dataset = YoloDataset.load(args.data)
    names = dataset.names
    weights = Path(args.weights)
    print(f"Evaluating {weights.name} on {dataset.yaml_path} ({', '.join(names)})")
    predictor = Predictor(weights, names, imgsz=args.imgsz, clahe=args.clahe, device=args.device)

    # 1) choose the operating threshold on validation, never on test
    threshold_split = args.threshold_split if args.threshold_split in dataset.splits else args.split
    if args.conf:
        conf, conf_source = args.conf, "fixed by --conf"
    else:
        print(f"  choosing threshold on '{threshold_split}' (max mean F1)")
        val_gts, val_preds, _ = collect(dataset, threshold_split, predictor, limit=args.limit)
        conf = evaluate(val_gts, val_preds, names)["operating_confidence"]
        conf_source = f"max mean F1 on '{threshold_split}' split"
    print(f"  operating confidence = {conf:.3f} ({conf_source})")

    # 2) report the test split once
    gts, preds, _ = collect(dataset, args.split, predictor, limit=args.limit)
    main = summarize(gts, preds, names, conf)
    ev, cm = main["_ev"], main["_cm"]

    plots.confusion_matrix(cm["matrix"], names, REPORTS / "confusion_matrix.png")
    plots.confusion_matrix(cm["matrix"], names, REPORTS / "confusion_matrix_normalized.png", normalize=True)
    plots.pr_curves(ev["_curves"]["curves"], names, REPORTS / "pr_curve.png")
    plots.f1_curve(ev["_curves"]["conf_grid"], ev["_curves"]["f1_at"], ev["_curves"]["mean_f1"], names, conf,
                   REPORTS / "f1_confidence_curve.png")
    write_error_gallery(cm["errors"], names, gts, preds, conf)
    breakdown = error_breakdown(cm["errors"], gts, names)
    write_error_analysis(breakdown, args.split, conf)

    # 3) robustness subsets (objective lighting buckets + optional filename tags)
    robustness = {}
    subsets = {
        "normal_light": [i for i, g in enumerate(gts) if g.meta["luma"] >= DARK_LUMA],
        "dark": [i for i, g in enumerate(gts) if g.meta["luma"] < DARK_LUMA],
    }
    for tag in ("night", "rain", "blur", "shadow"):
        subsets[tag] = [i for i, g in enumerate(gts) if tag in g.meta["tags"]]
    for subset, indexes in subsets.items():
        if len(indexes) < 5:
            continue
        s = summarize([gts[i] for i in indexes], [preds[i] for i in indexes], names, conf)
        robustness[subset] = {k: s[k] for k in ("images", "instances", "map50", "precision", "recall", "f1")}
    write_json("robustness.json", {"split": args.split, "confidence": conf, "dark_luma_threshold": DARK_LUMA,
                                   "subsets": robustness})

    # 4) preprocessing ablation: the before-vs-after comparison
    ablation = {}
    dark_indexes = subsets["dark"]
    for mode in ("off", "auto", "on"):
        if mode == args.clahe:
            mode_gts, mode_preds = gts, preds
        else:
            print(f"  ablation: CLAHE {mode}")
            mode_gts, mode_preds, _ = collect(dataset, args.split, predictor, clahe=mode, limit=args.limit)
        overall = summarize(mode_gts, mode_preds, names, conf)
        row = {"overall": {k: overall[k] for k in ("map50", "map50_95", "precision", "recall", "f1")}}
        if len(dark_indexes) >= 5:
            dark = summarize([mode_gts[i] for i in dark_indexes], [mode_preds[i] for i in dark_indexes], names, conf)
            row["dark_subset"] = {k: dark[k] for k in ("images", "map50", "precision", "recall", "f1")}
        ablation[mode] = row
    write_json("ablation.json", {"split": args.split, "confidence": conf, "modes": ablation,
                                 "note": "off = no CLAHE, auto = CLAHE on dark/low-contrast frames (app default), on = always"})
    groups = ["All test images"] + (["Dark subset"] if "dark_subset" in ablation["off"] else [])
    series = {f"CLAHE {mode}": [ablation[mode]["overall"]["map50"]] +
              ([ablation[mode]["dark_subset"]["map50"]] if "dark_subset" in ablation[mode] else [])
              for mode in ("off", "auto", "on")}
    plots.grouped_bars(groups, series, REPORTS / "ablation_bar.png", "Preprocessing ablation: CLAHE before vs after", "mAP@0.5")

    # 5) optional extra local test set
    extra = {}
    if "test_local" in dataset.splits and dataset.images("test_local"):
        local_gts, local_preds, _ = collect(dataset, "test_local", predictor)
        extra["test_local"] = public(summarize(local_gts, local_preds, names, conf))

    timings = [p.meta for p in preds]
    metrics = {
        "status": "evaluated",
        "model": {"weights": weights.name, "fingerprint": file_fingerprint(weights), "classes": names,
                  "imgsz": args.imgsz, "architecture": "YOLO (Ultralytics), fine-tuned from COCO-pretrained weights"},
        "dataset": {"yaml": str(Path(args.data)), "split": args.split, "images": main["images"], "instances": main["instances"]},
        "overall": {k: main[k] for k in ("map50", "map50_95", "precision", "recall", "f1", "tp", "fp", "fn")},
        "per_class": main["per_class"],
        "operating_point": {"confidence": conf, "iou": 0.5, "nms_iou": NMS_IOU, "selection": conf_source},
        "preprocessing": {"clahe": args.clahe, "letterbox": args.imgsz},
        "speed_ms": {
            "preprocess_mean": round(float(np.mean([t["preprocess_ms"] for t in timings])), 1),
            "inference_mean": round(float(np.mean([t["inference_ms"] for t in timings])), 1),
            "device": args.device,
        },
        "error_breakdown": breakdown,
        "confusion_matrix": {"labels": names + ["background"], "rows": "true class", "columns": "predicted class",
                             "matrix": cm["matrix"].tolist()},
        "extra_splits": extra,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit(),
        "machine": machine(),
    }
    write_json("metrics.json", metrics)
    if args.run_dir:
        results_png = Path(args.run_dir) / "results.png"
        if results_png.exists():
            (REPORTS / "training_curves.png").write_bytes(results_png.read_bytes())
            print("  copied training curves")
    print(f"\nTest mAP@0.5 {main['map50']:.3f} · mAP@0.5:0.95 {main['map50_95']:.3f} · "
          f"P {main['precision']:.3f} · R {main['recall']:.3f} · F1 {main['f1']:.3f} at conf {conf:.2f}")


def _experiment_meta(run_dir: Path) -> dict:
    meta_path = run_dir / "aniroute_experiment.json"
    if meta_path.exists():
        return json.loads(meta_path.read_text(encoding="utf-8"))
    return {"id": run_dir.name, "title": run_dir.name, "change": ""}


def _time_model(predictor: Predictor, images: list[np.ndarray], runs: int = 20) -> float:
    for image in images[:3]:
        predictor(image, conf=0.25)
    samples = []
    for index in range(runs):
        image = images[index % len(images)]
        started = time.perf_counter()
        predictor(image, conf=0.25)
        samples.append((time.perf_counter() - started) * 1000)
    return float(np.mean(samples))


def cmd_compare(args) -> None:
    dataset = YoloDataset.load(args.data)
    names = dataset.names
    split = args.split if args.split in dataset.splits else "val"
    timing_images = [cv2.imread(str(p)) for p in dataset.images(split)[:10]]
    rows = []
    best_predictor, best_row = None, None
    for run in args.runs:
        run_dir = Path(run)
        weights = run_dir / "weights" / "best.pt"
        if not weights.exists():
            print(f"  skip {run_dir}: no weights/best.pt")
            continue
        meta = _experiment_meta(run_dir)
        imgsz = int(meta.get("imgsz", args.imgsz))
        print(f"  {meta['id']}: {meta.get('title', '')}")
        predictor = Predictor(weights, names, imgsz=imgsz, clahe="auto", device=args.device)
        gts, preds, _ = collect(dataset, split, predictor, limit=args.limit)
        ev = evaluate(gts, preds, names)
        s = summarize(gts, preds, names, ev["operating_confidence"])
        mean_ms = _time_model(predictor, timing_images)
        row = {
            "id": meta["id"], "title": meta.get("title", ""), "change": meta.get("change", ""),
            "kind": "training", "imgsz": imgsz, "model": meta.get("model", ""), "epochs": meta.get("epochs"),
            "map50": s["map50"], "map50_95": s["map50_95"], "precision": s["precision"], "recall": s["recall"],
            "f1": s["f1"], "operating_conf": ev["operating_confidence"],
            "cpu_ms": round(mean_ms, 1), "fps": round(1000 / mean_ms, 1),
        }
        rows.append(row)
        if best_row is None or row["map50"] > best_row["map50"] or (
                row["map50"] == best_row["map50"] and row["cpu_ms"] < best_row["cpu_ms"]):
            best_row, best_predictor, best_cache = row, predictor, (gts, preds)
    if not rows:
        raise SystemExit("No runs with weights found.")

    # Inference-time optimisations applied to the best training run (no retraining):
    gts, preds = best_cache
    default = summarize(gts, preds, names, 0.25)
    tuned = summarize(gts, preds, names, best_row["operating_conf"])
    rows.append({"id": "E5", "title": "Confidence threshold tuned", "kind": "inference",
                 "change": f"{best_row['id']}: conf 0.25 → {best_row['operating_conf']:.2f} (max F1)",
                 "map50": best_row["map50"], "map50_95": best_row["map50_95"],
                 "f1_before": default["f1"], "f1": tuned["f1"], "precision_before": default["precision"],
                 "precision": tuned["precision"], "recall_before": default["recall"], "recall": tuned["recall"],
                 "cpu_ms": best_row["cpu_ms"], "fps": best_row["fps"]})
    off_gts, off_preds, _ = collect(dataset, split, best_predictor, clahe="off", limit=args.limit)
    off = summarize(off_gts, off_preds, names, best_row["operating_conf"])
    rows.append({"id": "E6", "title": "CLAHE preprocessing", "kind": "inference",
                 "change": f"{best_row['id']}: CLAHE off → auto", "map50_before": off["map50"],
                 "map50": best_row["map50"], "f1_before": off["f1"], "f1": best_row["f1"],
                 "cpu_ms": best_row["cpu_ms"], "fps": best_row["fps"]})

    write_json("optimization.json", {"split": split, "selected": best_row["id"], "rows": rows,
                                     "selection_rule": "highest validation mAP@0.5, ties broken by CPU speed",
                                     "evaluated_at": datetime.now(timezone.utc).isoformat()})
    plots.optimization_chart([r for r in rows if r["kind"] == "training"], REPORTS / "optimization_chart.png")
    table = ["| ID | Experiment | Change | mAP@0.5 | mAP@0.5:0.95 | P | R | F1 | CPU ms | FPS |",
             "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for r in rows:
        def fmt(key):
            value = r.get(key)
            return "–" if value is None else f"{value:.3f}" if isinstance(value, float) and value <= 1 else f"{value}"
        before = ""
        if r["kind"] == "inference":
            before = f" (before: F1 {r.get('f1_before', 0):.3f}" + (f", mAP {r['map50_before']:.3f}" if "map50_before" in r else "") + ")"
        table.append(f"| {r['id']}{' ★' if r['id'] == best_row['id'] else ''} | {r.get('title', '')} | {r.get('change', '')}{before} | "
                     f"{fmt('map50')} | {fmt('map50_95')} | {fmt('precision')} | {fmt('recall')} | {fmt('f1')} | "
                     f"{r.get('cpu_ms', '–')} | {r.get('fps', '–')} |")
    (REPORTS / "optimization_table.md").write_text("\n".join(table) + "\n", encoding="utf-8")
    print(f"  wrote {display(REPORTS / 'optimization_table.md')}")
    print(f"\nSelected {best_row['id']} (val mAP@0.5 {best_row['map50']:.3f}). Copy its weights to "
          f"backend/models/aniroute-hazards-v1.pt, then run `python ml/evaluate.py test`.")


def _benchmark(fn, images: list[np.ndarray], runs: int) -> tuple[float, float]:
    for image in images[:3]:
        fn(image)
    samples = []
    for index in range(runs):
        started = time.perf_counter()
        fn(images[index % len(images)])
        samples.append((time.perf_counter() - started) * 1000)
    return float(np.mean(samples)), float(np.percentile(samples, 95))


def cmd_latency(args) -> None:
    image_dir = Path(args.images)
    paths = sorted(p for p in image_dir.rglob("*") if p.suffix.lower() in {".jpg", ".jpeg", ".png"})[:20]
    images = [img for img in (cv2.imread(str(p)) for p in paths) if img is not None]
    if not images:
        raise SystemExit(f"No images in {image_dir}")
    rows = []
    candidates = [("Model A", Path(args.weights)), ("Model B", Path(args.obstruction_weights))]
    for label, weights in candidates:
        if not weights.exists():
            print(f"  skip {label}: {weights} not found")
            continue
        stem = weights.with_suffix("")
        formats = {"pt": weights, "onnx": stem.with_suffix(".onnx"), "openvino": Path(f"{stem}_openvino_model")}
        for fmt, path in formats.items():
            if not path.exists():
                continue
            # Exported ONNX/OpenVINO graphs have a fixed 640 input, so only PyTorch is timed at other sizes.
            for imgsz in (args.imgsz_list if fmt == "pt" else [640]):
                model = YoloModel(label, weights, model_format=fmt, imgsz=imgsz, device=args.device)
                if not model.load():
                    print(f"  skip {label} {fmt}: {model.error}")
                    continue

                def run(image, model=model, imgsz=imgsz):
                    pipeline = run_pipeline(image, size=imgsz)
                    model.predict(pipeline.model_input, conf=0.25, iou=0.5)

                mean, p95 = _benchmark(run, images, args.runs)
                rows.append({"model": label, "format": fmt, "imgsz": imgsz, "mean_ms": round(mean, 1),
                             "p95_ms": round(p95, 1), "fps": round(1000 / mean, 1)})
                print(f"  {label:8s} {fmt:9s} @{imgsz}: {mean:6.1f} ms mean, {p95:6.1f} ms p95, {1000 / mean:5.1f} FPS")

    # End-to-end system: preprocessing once + both models + merge (what the app runs per frame).
    detector = HazardDetector(VisionSettings(warmup=False, model_a_path=Path(args.weights),
                                             model_b_path=Path(args.obstruction_weights), model_format=args.format))
    system = None
    if detector.load():
        mean, p95 = _benchmark(lambda image: detector.detect(image), images, args.runs)
        models = "+".join(m for m, ok in (("A", detector.model_a.loaded), ("B", detector.model_b.loaded)) if ok)
        system = {"models": models, "mean_ms": round(mean, 1), "p95_ms": round(p95, 1), "fps": round(1000 / mean, 1),
                  "runtime_format": args.format}
        rows.append({"model": f"System ({models})", "format": args.format, "imgsz": detector.settings.imgsz, **{
            k: system[k] for k in ("mean_ms", "p95_ms", "fps")}})
        print(f"  System ({models}) end-to-end: {mean:.1f} ms mean → {1000 / mean:.1f} FPS")
    write_json("latency.json", {"rows": rows, "system": system, "images": len(images), "runs": args.runs,
                                "device": args.device, "machine": machine(),
                                "evaluated_at": datetime.now(timezone.utc).isoformat()})
    plots.speed_chart(rows, REPORTS / "speed_chart.png")


def cmd_obstruction(args) -> None:
    """Evaluate Model B (COCO-pretrained, no training) as a road-obstruction detector."""
    dataset = YoloDataset.load(args.data)
    split = args.split if args.split in dataset.splits else next(iter(dataset.splits))
    paths = dataset.images(split)
    if not paths:
        raise SystemExit("Obstruction test set is empty.")
    results = {}
    example_written = False
    for use_roi in (False, True):
        detector = HazardDetector(VisionSettings(warmup=False, model_a_path=REPO / "__no_model_a__.pt",
                                                 model_b_path=Path(args.obstruction_weights)))
        gts, preds = [], []
        for path in paths:
            image = cv2.imread(str(path))
            if image is None:
                continue
            height, width = image.shape[:2]
            gt = read_labels(path, width, height)
            gt.classes = np.zeros(len(gt.classes), dtype=int)   # every labelled box is an obstruction
            result = detector.detect(image, use_roi=use_roi, conf=MAP_CONF if not args.conf else args.conf)
            boxes = np.array([d.box for d in result.detections], dtype=float).reshape(-1, 4)
            preds.append(ImageBoxes(boxes, np.zeros(len(boxes), dtype=int),
                                    np.array([d.confidence for d in result.detections], dtype=float), gt.image_id))
            gts.append(gt)
            if use_roi and not example_written and len(result.detections):
                roi = detector.settings.roi
                canvas = draw_detections(image, [d.to_dict() for d in result.detections],
                                         roi_polygon=corridor_polygon(roi.top, roi.bottom_half_width, roi.top_half_width))
                cv2.imwrite(str(REPORTS / "model_b_roi_example.png"), canvas)
                example_written = True
        conf = detector.settings.conf_b
        s = summarize(gts, preds, ["road_obstruction"], conf)
        results["with_roi" if use_roi else "without_roi"] = {k: s[k] for k in ("images", "instances", "map50", "precision",
                                                                                 "recall", "f1", "tp", "fp", "fn")}
    write_json("model_b.json", {"model": Path(args.obstruction_weights).name, "split": split,
                                "confidence": VisionSettings().conf_b, "roi": vars(RoiSettings()), "results": results,
                                "note": "Model B is COCO-pretrained and used without training; the ROI rule keeps only in-lane objects.",
                                "evaluated_at": datetime.now(timezone.utc).isoformat()})


def cmd_smoothing(args) -> None:
    """Alert volume with vs without 2-of-3 temporal voting on a recorded drive."""
    capture = cv2.VideoCapture(str(args.video))
    if not capture.isOpened():
        raise SystemExit(f"Cannot open video {args.video}")
    fps = capture.get(cv2.CAP_PROP_FPS) or 30
    step = max(1, round(fps / args.sample_fps))
    detector = HazardDetector(VisionSettings(warmup=False))
    if not detector.load():
        raise SystemExit("No model available.")
    s = detector.settings
    smoothed = TemporalHazardFilter(s.smoothing_window, s.smoothing_min_hits, s.cooldown_seconds, s.dedupe_meters)
    naive = TemporalHazardFilter(1, 1, 0.0, 0.0)   # alert on every frame with a detection
    frame_index, analysed = 0, 0
    naive_alerts, smooth_alerts = [], []
    while True:
        ok, frame = capture.read()
        if not ok:
            break
        if frame_index % step == 0:
            t = frame_index / fps
            detections = [d.to_dict() for d in detector.detect(frame).detections]
            if naive.update("video", detections, now=t):
                naive_alerts.append(round(t, 1))
            alert = smoothed.update("video", detections, now=t)
            if alert:
                smooth_alerts.append({"t": round(t, 1), "hazard_type": alert["hazard_type"],
                                      "confidence": round(alert["confidence"], 3), "verdict": "review"})
            analysed += 1
        frame_index += 1
    minutes = max(frame_index / fps / 60, 1e-9)
    write_json("smoothing.json", {
        "video": Path(args.video).name, "duration_s": round(frame_index / fps, 1), "frames_analysed": analysed,
        "sample_fps": args.sample_fps,
        "without_smoothing": {"alerts": len(naive_alerts), "alerts_per_minute": round(len(naive_alerts) / minutes, 1)},
        "with_smoothing": {"alerts": len(smooth_alerts), "alerts_per_minute": round(len(smooth_alerts) / minutes, 1),
                           "window": s.smoothing_window, "min_hits": s.smoothing_min_hits, "cooldown_s": s.cooldown_seconds},
        "alerts_for_review": smooth_alerts,
        "note": "Set each alert's verdict to 'true' or 'false' after watching the video to report false alarms per minute.",
    })


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    test = sub.add_parser("test", help="full evaluation of the deployed Model A")
    test.add_argument("--weights", default=str(DEFAULT_WEIGHTS))
    test.add_argument("--data", default=str(DEFAULT_DATA))
    test.add_argument("--split", default="test")
    test.add_argument("--threshold-split", default="val")
    test.add_argument("--conf", type=float, default=None, help="fix the operating threshold instead of choosing it on val")
    test.add_argument("--clahe", default="auto", choices=["auto", "on", "off"])
    test.add_argument("--imgsz", type=int, default=640)
    test.add_argument("--device", default="cpu")
    test.add_argument("--limit", type=int, default=None, help="evaluate only the first N images (quick check)")
    test.add_argument("--run-dir", default=None, help="training run folder; copies results.png as training curves")
    test.set_defaults(func=cmd_test)

    compare = sub.add_parser("compare", help="optimisation table across training runs (validation split)")
    compare.add_argument("--runs", nargs="+", required=True)
    compare.add_argument("--data", default=str(DEFAULT_DATA))
    compare.add_argument("--split", default="val")
    compare.add_argument("--imgsz", type=int, default=640)
    compare.add_argument("--device", default="cpu")
    compare.add_argument("--limit", type=int, default=None)
    compare.set_defaults(func=cmd_compare)

    latency = sub.add_parser("latency", help="CPU speed per model, runtime format and image size")
    latency.add_argument("--images", default=str(REPO / "backend" / "samples"))
    latency.add_argument("--weights", default=str(DEFAULT_WEIGHTS))
    latency.add_argument("--obstruction-weights", default=str(REPO / "backend" / "models" / "yolo11n.pt"))
    latency.add_argument("--imgsz-list", type=int, nargs="+", default=[640, 480])
    latency.add_argument("--format", default="auto")
    latency.add_argument("--runs", type=int, default=30)
    latency.add_argument("--device", default="cpu")
    latency.set_defaults(func=cmd_latency)

    obstruction = sub.add_parser("obstruction", help="evaluate Model B with and without the driving-corridor rule")
    obstruction.add_argument("--data", required=True)
    obstruction.add_argument("--split", default="test")
    obstruction.add_argument("--obstruction-weights", default=str(REPO / "backend" / "models" / "yolo11n.pt"))
    obstruction.add_argument("--conf", type=float, default=None)
    obstruction.set_defaults(func=cmd_obstruction)

    smoothing = sub.add_parser("smoothing", help="alert volume with vs without temporal voting on a video")
    smoothing.add_argument("--video", required=True)
    smoothing.add_argument("--sample-fps", type=float, default=2.0)
    smoothing.set_defaults(func=cmd_smoothing)

    args = parser.parse_args()
    REPORTS.mkdir(parents=True, exist_ok=True)
    args.func(args)


if __name__ == "__main__":
    main()
