"""Runtime settings for the AniRoute computer-vision service.

Every value can be overridden with an environment variable so experiments and
deployments do not need code changes.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent
MODELS_DIR = Path(os.getenv("ANIROUTE_MODELS_DIR", str(BACKEND_DIR / "models")))
SAMPLES_DIR = Path(os.getenv("ANIROUTE_SAMPLES_DIR", str(BACKEND_DIR / "samples")))
REPORTS_DIR = Path(os.getenv("ANIROUTE_REPORTS_DIR", str(REPO_ROOT / "ml" / "reports")))

HAZARD_TYPES = ("pothole", "severe_road_damage", "standing_water", "road_obstruction")
HAZARD_LABELS = {
    "pothole": "Pothole",
    "severe_road_damage": "Severe road damage",
    "standing_water": "Standing water",
    "road_obstruction": "Road obstruction",
}
# Shared with the frontend overlay, map pins and report charts (hex, RGB order).
HAZARD_COLORS = {
    "pothole": "#F59E0B",
    "severe_road_damage": "#DC2626",
    "standing_water": "#2563EB",
    "road_obstruction": "#7C3AED",
}

# COCO classes that count as a road obstruction when they are inside the driving corridor.
COCO_OBSTRUCTION_CLASSES = (
    "person", "bicycle", "car", "motorcycle", "bus", "truck", "dog", "horse", "sheep", "cow",
)


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def evaluated_operating_threshold(reports_dir: Path = REPORTS_DIR) -> float | None:
    """Return the max-F1 confidence threshold chosen by ml/evaluate.py, if it exists."""
    try:
        metrics = json.loads((reports_dir / "metrics.json").read_text(encoding="utf-8"))
        value = float(metrics["operating_point"]["confidence"])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return value if 0 < value < 1 else None


@dataclass(frozen=True)
class RoiSettings:
    """Trapezoid 'driving corridor' used to decide whether a COCO object blocks the road.

    All values are fractions of the frame size. The corridor spans the bottom part of the
    frame and narrows toward the horizon, like the lane in front of a dashcam.
    """

    top: float = 0.40            # corridor starts this far down the frame (horizon)
    bottom_half_width: float = 0.25   # half-width at the bottom edge (0.25 → central 50%)
    top_half_width: float = 0.10      # half-width at the horizon line
    min_height: float = 0.12     # box must be at least this tall (close enough to matter)


@dataclass(frozen=True)
class VisionSettings:
    model_a_path: Path = field(default_factory=lambda: Path(os.getenv(
        "ANIROUTE_MODEL_PATH", str(MODELS_DIR / "aniroute-hazards-v1.pt"))))
    model_b_path: Path = field(default_factory=lambda: Path(os.getenv(
        "ANIROUTE_OBSTRUCTION_MODEL_PATH", str(MODELS_DIR / "yolo11n.pt"))))
    model_format: str = field(default_factory=lambda: os.getenv("ANIROUTE_MODEL_FORMAT", "auto").lower())
    enable_model_b: bool = field(default_factory=lambda: _env_bool("ANIROUTE_ENABLE_OBSTRUCTION_MODEL", True))
    imgsz: int = field(default_factory=lambda: _env_int("ANIROUTE_IMGSZ", 640))
    conf_a: float = field(default_factory=lambda: _env_float(
        "ANIROUTE_CONF_THRESHOLD", evaluated_operating_threshold() or 0.35))
    conf_b: float = field(default_factory=lambda: _env_float("ANIROUTE_OBSTRUCTION_CONF_THRESHOLD", 0.45))
    iou: float = field(default_factory=lambda: _env_float("ANIROUTE_NMS_IOU", 0.5))
    device: str = field(default_factory=lambda: os.getenv("ANIROUTE_DEVICE", "cpu"))
    # Preprocessing. Default CLAHE mode "off": the validation ablation (ml/reports/optimization.json, E6)
    # showed CLAHE lowers mAP on our road images, so it is opt-in ("auto"/"on") per request.
    clahe_mode: str = field(default_factory=lambda: os.getenv("ANIROUTE_CLAHE", "off"))
    clahe_clip_limit: float = field(default_factory=lambda: _env_float("ANIROUTE_CLAHE_CLIP", 2.0))
    clahe_tile: int = field(default_factory=lambda: _env_int("ANIROUTE_CLAHE_TILE", 8))
    dark_luma_threshold: float = field(default_factory=lambda: _env_float("ANIROUTE_DARK_LUMA", 95.0))
    low_contrast_threshold: float = field(default_factory=lambda: _env_float("ANIROUTE_LOW_CONTRAST", 38.0))
    # Temporal smoothing for active trips
    smoothing_window: int = field(default_factory=lambda: _env_int("ANIROUTE_SMOOTHING_WINDOW", 3))
    smoothing_min_hits: int = field(default_factory=lambda: _env_int("ANIROUTE_SMOOTHING_MIN_HITS", 2))
    cooldown_seconds: float = field(default_factory=lambda: _env_float("ANIROUTE_HAZARD_COOLDOWN_S", 20.0))
    dedupe_meters: float = field(default_factory=lambda: _env_float("ANIROUTE_HAZARD_DEDUPE_M", 50.0))
    roi: RoiSettings = field(default_factory=lambda: RoiSettings(
        top=_env_float("ANIROUTE_ROI_TOP", 0.40),
        bottom_half_width=_env_float("ANIROUTE_ROI_BOTTOM_HALF_WIDTH", 0.25),
        top_half_width=_env_float("ANIROUTE_ROI_TOP_HALF_WIDTH", 0.10),
        min_height=_env_float("ANIROUTE_ROI_MIN_HEIGHT", 0.12),
    ))
    warmup: bool = field(default_factory=lambda: _env_bool("ANIROUTE_VISION_WARMUP", True))
