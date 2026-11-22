"""Merge one or more Roboflow "YOLOv8" exports into the AniRoute training dataset.

You do NOT need to label anything. Download the datasets from Roboflow Universe in
YOLOv8 format, unzip each into ml/data/raw/<name>/, then run for example:

  python ml/scripts/prepare_dataset.py \
      --source ml/data/raw/potholes --source ml/data/raw/rdd2022 \
      --map pothole=pothole potholes=pothole D40=pothole \
            D00=severe_road_damage D10=severe_road_damage D20=severe_road_damage

What it does
1. Reads each export's data.yaml and maps its class names to ours (unknown classes are
   dropped, e.g. RDD2022 "repair"). Images left with no boxes stay as background images.
2. Drops unreadable images and removes near-duplicates (perceptual hash) from val/test
   when they look like a training image, so the test score cannot be inflated by leakage.
3. Keeps each source's train/valid/test split (or re-splits 70/20/10 with --resplit).
4. Writes ml/data/aniroute/data.yaml, dataset statistics, a class-distribution chart and
   a sample grid for the Dataset slide, and copies a few held-out test images to
   backend/samples/ for the live demo.
"""
from __future__ import annotations

import argparse
import json
import random
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path

import cv2
import numpy as np
import yaml

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "ml"))
from evaluation import plots  # noqa: E402
from evaluation.dataset import IMAGE_SUFFIXES, YoloDataset, label_path_for  # noqa: E402

CLASSES = ["pothole", "severe_road_damage"]
OUT = REPO / "ml" / "data" / "aniroute"
REPORTS = REPO / "ml" / "reports"
SAMPLES = REPO / "backend" / "samples"
SPLIT_ALIASES = {"train": "train", "val": "val", "valid": "val", "test": "test"}


def parse_map(values: list[str]) -> dict[str, str]:
    mapping = {}
    for value in values:
        source, _, target = value.partition("=")
        if target not in CLASSES:
            raise SystemExit(f"--map target '{target}' must be one of {CLASSES}")
        mapping[source.strip().lower()] = target
    return mapping


def phash_bits(path: Path) -> np.ndarray | None:
    image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        return None
    small = cv2.resize(image, (32, 32), interpolation=cv2.INTER_AREA).astype(np.float32)
    dct = cv2.dct(small)[:8, :8]
    return (dct > np.median(dct)).flatten()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", action="append", required=True, help="folder containing a Roboflow data.yaml")
    parser.add_argument("--map", nargs="*", default=[f"{c}={c}" for c in CLASSES],
                        help="source_class=target_class pairs (case-insensitive)")
    parser.add_argument("--out", default=str(OUT))
    parser.add_argument("--resplit", action="store_true", help="ignore source splits; make a 70/20/10 split")
    parser.add_argument("--max-images", type=int, default=None, help="cap images per source (keeps Colab runs short)")
    parser.add_argument("--dedupe-distance", type=int, default=4, help="max Hamming distance treated as duplicate")
    parser.add_argument("--samples", type=int, default=6, help="test images copied to backend/samples for the demo")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    mapping = parse_map(args.map)
    for name in CLASSES:
        mapping.setdefault(name, name)
    out = Path(args.out).resolve()
    if out.exists():
        shutil.rmtree(out)
    rng = random.Random(args.seed)

    records = []   # (split, image_path, [(class, xc, yc, w, h)], source_name)
    dropped_classes: Counter = Counter()
    for source in args.source:
        source_dir = Path(source)
        yaml_path = source_dir / "data.yaml" if source_dir.is_dir() else source_dir
        dataset = YoloDataset.load(yaml_path)
        source_name = yaml_path.parent.name
        names = [str(n) for n in dataset.names]
        print(f"{source_name}: classes {names}; splits {list(dataset.splits)}")
        items = []
        for split, _ in dataset.splits.items():
            target_split = SPLIT_ALIASES.get(split)
            if target_split is None:
                continue
            for image_path in dataset.images(split):
                labels = []
                label_file = label_path_for(image_path)
                if label_file.exists():
                    for line in label_file.read_text(encoding="utf-8").splitlines():
                        values = line.split()
                        if len(values) < 5:
                            continue
                        source_class = names[int(float(values[0]))].lower()
                        target = mapping.get(source_class)
                        if target is None:
                            dropped_classes[f"{source_name}:{source_class}"] += 1
                            continue
                        coords = [float(v) for v in values[1:]]
                        if len(coords) > 4:   # polygon → box
                            xs, ys = coords[0::2], coords[1::2]
                            coords = [(min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, max(xs) - min(xs), max(ys) - min(ys)]
                        labels.append((CLASSES.index(target), *coords[:4]))
                items.append((target_split, image_path, labels, source_name))
        if args.max_images and len(items) > args.max_images:
            rng.shuffle(items)
            items = items[:args.max_images]
        records.extend(items)

    if args.resplit:
        rng.shuffle(records)
        n = len(records)
        records = [("train" if i < 0.7 * n else "val" if i < 0.9 * n else "test", *r[1:]) for i, r in enumerate(records)]

    # Unreadable images + perceptual-hash duplicates (val/test images that look like a train image are dropped).
    print(f"Checking {len(records)} images for corruption and duplicates…")
    hashes, valid = [], []
    for record in records:
        bits = phash_bits(record[1])
        if bits is None:
            continue
        hashes.append(bits)
        valid.append(record)
    dropped_corrupt = len(records) - len(valid)
    hash_matrix = np.array(hashes, dtype=bool)
    train_idx = [i for i, r in enumerate(valid) if r[0] == "train"]
    train_hashes = hash_matrix[train_idx] if train_idx else np.zeros((0, 64), bool)
    keep, dropped_dupes = [], 0
    for i, record in enumerate(valid):
        if record[0] != "train" and len(train_hashes):
            distances = (train_hashes != hash_matrix[i]).sum(axis=1)
            if distances.min() <= args.dedupe_distance:
                dropped_dupes += 1
                continue
        keep.append(record)

    # Write the merged dataset.
    counts = defaultdict(Counter)
    images_per_split = Counter()
    for index, (split, image_path, labels, source_name) in enumerate(keep):
        stem = f"{source_name[:20]}_{index:06d}"
        image_dir, label_dir = out / split / "images", out / split / "labels"
        image_dir.mkdir(parents=True, exist_ok=True)
        label_dir.mkdir(parents=True, exist_ok=True)
        target = image_dir / f"{stem}{image_path.suffix.lower()}"
        shutil.copy2(image_path, target)
        (label_dir / f"{stem}.txt").write_text(
            "".join(f"{c} {xc:.6f} {yc:.6f} {w:.6f} {h:.6f}\n" for c, xc, yc, w, h in labels), encoding="utf-8")
        images_per_split[split] += 1
        for label in labels:
            counts[split][CLASSES[label[0]]] += 1

    config = {"path": str(out), "train": "train/images", "val": "val/images", "test": "test/images",
              "names": {i: name for i, name in enumerate(CLASSES)}}
    local = out.parent / "local_test"
    if (local / "images").exists():
        config["test_local"] = str((local / "images").resolve())
    (out / "data.yaml").write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

    stats = {
        "classes": CLASSES,
        "sources": args.source,
        "class_mapping": mapping,
        "images_per_split": dict(images_per_split),
        "instances_per_split": {split: dict(counter) for split, counter in counts.items()},
        "dropped": {"unreadable_images": dropped_corrupt, "near_duplicates_removed_from_val_test": dropped_dupes,
                    "boxes_of_unmapped_classes": dict(dropped_classes)},
        "split_rule": "70/20/10 re-split, seed 42" if args.resplit else "source train/valid/test splits kept",
    }
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "dataset_stats.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
    print(json.dumps(stats, indent=2))
    for name in CLASSES:
        if counts["train"][name] < 300:
            print(f"WARNING: only {counts['train'][name]} training boxes for '{name}' (target ≥ 300). Mention this in limitations.")

    splits = [s for s in ("train", "val", "test") if images_per_split[s]]
    plots.grouped_bars(splits, {plots.pretty(c): [counts[s][c] for s in splits] for c in CLASSES},
                       REPORTS / "dataset_class_distribution.png", "Labelled boxes per class and split",
                       "Boxes", colors=[plots.CLASS_COLORS[c] for c in CLASSES], ylim=None)
    write_sample_grid(out, rng)
    copy_demo_samples(out, args.samples, rng)
    print(f"\nDataset ready: {out / 'data.yaml'}")


def write_sample_grid(out: Path, rng: random.Random, per_class: int = 4) -> None:
    tiles = []
    for class_id, name in enumerate(CLASSES):
        candidates = []
        for label in sorted((out / "train" / "labels").glob("*.txt")):
            if any(line.startswith(f"{class_id} ") for line in label.read_text(encoding="utf-8").splitlines()):
                candidates.append(label)
        rng.shuffle(candidates)
        row = []
        for label in candidates[:per_class]:
            image_path = next((p for p in (out / "train" / "images").glob(label.stem + ".*") if p.suffix.lower() in IMAGE_SUFFIXES), None)
            image = cv2.imread(str(image_path)) if image_path else None
            if image is None:
                continue
            h, w = image.shape[:2]
            color = tuple(int(plots.CLASS_COLORS[name].lstrip("#")[i:i + 2], 16) for i in (4, 2, 0))
            for line in label.read_text(encoding="utf-8").splitlines():
                c, xc, yc, bw, bh = line.split()[:5]
                if int(c) != class_id:
                    continue
                x1, y1 = int((float(xc) - float(bw) / 2) * w), int((float(yc) - float(bh) / 2) * h)
                x2, y2 = int((float(xc) + float(bw) / 2) * w), int((float(yc) + float(bh) / 2) * h)
                cv2.rectangle(image, (x1, y1), (x2, y2), color, max(2, w // 200))
            tile = cv2.resize(image, (320, 240))
            cv2.putText(tile, plots.pretty(name), (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
            row.append(tile)
        while row and len(row) < per_class:
            row.append(np.full((240, 320, 3), 245, np.uint8))
        if row:
            tiles.append(np.hstack(row))
    if tiles:
        cv2.imwrite(str(REPORTS / "dataset_samples.png"), np.vstack(tiles))
        print("wrote ml/reports/dataset_samples.png")


def copy_demo_samples(out: Path, count: int, rng: random.Random) -> None:
    test_images = sorted((out / "test" / "images").glob("*"))
    labelled = [p for p in test_images if label_path_for(p).exists() and label_path_for(p).read_text(encoding="utf-8").strip()]
    rng.shuffle(labelled)
    SAMPLES.mkdir(parents=True, exist_ok=True)
    captions_path = SAMPLES / "samples.json"
    captions = json.loads(captions_path.read_text(encoding="utf-8")) if captions_path.exists() else {}
    for index, path in enumerate(labelled[:count], 1):
        first_class = int(label_path_for(path).read_text(encoding="utf-8").split()[0])
        name = f"test_{CLASSES[first_class]}_{index:02d}{path.suffix.lower()}"
        shutil.copy2(path, SAMPLES / name)
        captions[name] = {"caption": f"Held-out test image ({plots.pretty(CLASSES[first_class]).lower()})",
                          "source": "AniRoute test split (never used in training)"}
    captions_path.write_text(json.dumps(captions, indent=2), encoding="utf-8")
    print(f"copied {min(count, len(labelled))} held-out test images to backend/samples/")


if __name__ == "__main__":
    main()
