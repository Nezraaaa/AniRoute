"""Read YOLO-format datasets (the format Roboflow exports as "YOLOv8").

Layout:  <root>/<split>/images/*.jpg  and  <root>/<split>/labels/*.txt
Label line: `class x_center y_center width height` (all normalised to 0-1).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import yaml
from PIL import Image

from .metrics import ImageBoxes

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


@dataclass
class YoloDataset:
    yaml_path: Path
    root: Path
    names: list[str]
    splits: dict[str, Path]          # split → images directory

    @classmethod
    def load(cls, yaml_path: str | Path) -> "YoloDataset":
        yaml_path = Path(yaml_path).resolve()
        config = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        root = Path(config.get("path") or yaml_path.parent)
        if not root.is_absolute():
            root = (yaml_path.parent / root).resolve()
        names = config["names"]
        if isinstance(names, dict):
            names = [names[key] for key in sorted(names, key=int)]
        splits = {}
        for split in ("train", "val", "test", "test_local"):
            value = config.get(split)
            if not value:
                continue
            path = Path(value)
            path = path if path.is_absolute() else (root / path)
            # Roboflow sometimes writes "../train/images"; resolve relative to the yaml too.
            if not path.exists():
                alternative = (yaml_path.parent / value).resolve()
                path = alternative if alternative.exists() else path
            splits[split] = path.resolve()
        return cls(yaml_path, root, list(names), splits)

    def images(self, split: str) -> list[Path]:
        directory = self.splits.get(split)
        if directory is None or not directory.exists():
            return []
        return sorted(p for p in directory.rglob("*") if p.suffix.lower() in IMAGE_SUFFIXES)


def label_path_for(image_path: Path) -> Path:
    parts = list(image_path.parts)
    for index in range(len(parts) - 1, -1, -1):
        if parts[index] == "images":
            parts[index] = "labels"
            break
    return Path(*parts).with_suffix(".txt")


def read_labels(image_path: Path, width: int, height: int) -> ImageBoxes:
    path = label_path_for(image_path)
    boxes, classes = [], []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            values = line.split()
            if len(values) < 5:
                continue
            class_id = int(float(values[0]))
            coords = [float(v) for v in values[1:]]
            if len(coords) > 4:   # polygon (segmentation export) → bounding box
                xs, ys = coords[0::2], coords[1::2]
                x1, x2, y1, y2 = min(xs), max(xs), min(ys), max(ys)
            else:
                xc, yc, w, h = coords
                x1, y1, x2, y2 = xc - w / 2, yc - h / 2, xc + w / 2, yc + h / 2
            boxes.append([x1 * width, y1 * height, x2 * width, y2 * height])
            classes.append(class_id)
    return ImageBoxes(np.array(boxes, dtype=float).reshape(-1, 4), np.array(classes, dtype=int),
                      None, image_path.name)


def image_size(path: Path) -> tuple[int, int]:
    with Image.open(path) as image:
        return image.size


def filename_tags(path: Path) -> set[str]:
    """Optional condition tags embedded in file names, e.g. `night_rain_0042.jpg`."""
    name = path.stem.lower()
    return {tag for tag in ("night", "day", "rain", "blur", "dusk", "shadow", "local") if tag in name}
