"""Integrates the two detectors into one hazard list.

Model A - our fine-tuned road-surface model (pothole, severe_road_damage).
Model B - the COCO-pretrained YOLO model used as-is; selected COCO classes become
          `road_obstruction` only when they sit inside the driving corridor.

Both models see the same preprocessed, letterboxed frame, so preprocessing runs once.
"""
from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field

import numpy as np

from .config import COCO_OBSTRUCTION_CLASSES, HAZARD_LABELS, HAZARD_TYPES, RoiSettings, VisionSettings
from .detector import RawBox, YoloModel
from .preprocess import ClaheMode, PipelineResult, run_pipeline, unletterbox_boxes
from .water_potholes import detect_water_filled_potholes

# Model A label aliases, so weights trained with raw dataset names still map correctly.
MODEL_A_ALIASES = {
    "pothole": "pothole", "potholes": "pothole", "d40": "pothole",
    "severe_road_damage": "severe_road_damage", "crack": "severe_road_damage", "cracks": "severe_road_damage",
    "d00": "severe_road_damage", "d10": "severe_road_damage", "d20": "severe_road_damage",
    "alligator crack": "severe_road_damage", "longitudinal crack": "severe_road_damage",
    "transverse crack": "severe_road_damage",
    "standing_water": "standing_water", "puddle": "standing_water", "flood": "standing_water",
    "road_obstruction": "road_obstruction",
}


def map_model_a_label(label: str) -> str | None:
    return MODEL_A_ALIASES.get(label.strip().lower())


def in_driving_corridor(box: tuple[float, float, float, float], width: int, height: int, roi: RoiSettings) -> bool:
    """True when the box's bottom-centre (its contact point with the road) is inside the
    trapezoid in front of the vehicle and the box is tall enough to be close."""
    x1, y1, x2, y2 = box
    if width <= 0 or height <= 0:
        return False
    if (y2 - y1) / height < roi.min_height:
        return False
    foot_x, foot_y = (x1 + x2) / 2 / width, y2 / height
    if foot_y < roi.top:
        return False
    # Linear interpolation of the corridor half-width between horizon and bottom edge.
    progress = (foot_y - roi.top) / max(1e-6, 1 - roi.top)
    half_width = roi.top_half_width + (roi.bottom_half_width - roi.top_half_width) * min(1.0, progress)
    return abs(foot_x - 0.5) <= half_width


@dataclass
class Detection:
    hazard_type: str
    label: str
    source_label: str
    confidence: float
    box: tuple[float, float, float, float]
    box_norm: tuple[float, float, float, float]
    model: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "hazard_type": self.hazard_type,
            "label": self.label,
            "source_label": self.source_label,
            "confidence": round(self.confidence, 4),
            "box": [round(value, 1) for value in self.box],
            "box_norm": [round(value, 5) for value in self.box_norm],
            "model": self.model,
        }


@dataclass
class DetectionResult:
    detections: list[Detection]
    pipeline: PipelineResult
    image_width: int
    image_height: int
    timings_ms: dict[str, float]
    models_used: list[str]
    roi_rejected: int = 0


def _to_detections(raw: list[RawBox], pipeline: PipelineResult, model: str, roi: RoiSettings | None) -> tuple[list[Detection], int]:
    info = pipeline.letterbox
    if not raw:
        return [], 0
    boxes = unletterbox_boxes(np.array([box.xyxy for box in raw], dtype=float), info)
    width, height = info.original_width, info.original_height
    detections: list[Detection] = []
    rejected = 0
    for item, box in zip(raw, boxes):
        xyxy = (float(box[0]), float(box[1]), float(box[2]), float(box[3]))
        if model == "A":
            hazard_type = map_model_a_label(item.label)
            if hazard_type is None:
                continue
        else:
            if item.label not in COCO_OBSTRUCTION_CLASSES:
                continue
            if roi is not None and not in_driving_corridor(xyxy, width, height, roi):
                rejected += 1
                continue
            hazard_type = "road_obstruction"
        detections.append(Detection(
            hazard_type=hazard_type,
            label=HAZARD_LABELS[hazard_type] if model == "A" else f"{HAZARD_LABELS[hazard_type]} ({item.label})",
            source_label=item.label,
            confidence=item.confidence,
            box=xyxy,
            box_norm=(xyxy[0] / width, xyxy[1] / height, xyxy[2] / width, xyxy[3] / height),
            model=model,
        ))
    return detections, rejected


class HazardDetector:
    def __init__(self, settings: VisionSettings | None = None) -> None:
        self.settings = settings or VisionSettings()
        s = self.settings
        self.model_a = YoloModel("Road-surface model (A, fine-tuned)", s.model_a_path,
                                 model_format=s.model_format, device=s.device, imgsz=s.imgsz)
        self.model_b = YoloModel("Obstruction model (B, COCO-pretrained)", s.model_b_path,
                                 model_format=s.model_format, device=s.device, imgsz=s.imgsz,
                                 allow_download=s.model_b_path.name in {"yolo11n.pt", "yolo11s.pt", "yolov8n.pt"})
        self._warmup_started = False
        self._warmup_lock = threading.Lock()
        self.warming_up = False

    # ------------------------------------------------------------------ lifecycle
    def load(self) -> bool:
        a_ok = self.model_a.load()
        b_ok = self.settings.enable_model_b and self.model_b.load()
        return a_ok or b_ok

    @property
    def ready(self) -> bool:
        return self.model_a.loaded or (self.settings.enable_model_b and self.model_b.loaded)

    def warmup_async(self) -> None:
        with self._warmup_lock:
            if self._warmup_started:
                return
            self._warmup_started = True
            self.warming_up = True

        def _run() -> None:
            try:
                if self.load():
                    dummy = np.full((self.settings.imgsz, self.settings.imgsz, 3), 114, dtype=np.uint8)
                    self.detect(dummy, clahe="off")
            finally:
                self.warming_up = False

        threading.Thread(target=_run, name="aniroute-vision-warmup", daemon=True).start()

    def supported_hazards(self) -> list[str]:
        hazards: list[str] = []
        if self.model_a.loaded:
            hazards.extend(sorted({h for label in self.model_a.class_names.values() if (h := map_model_a_label(label))},
                                  key=HAZARD_TYPES.index))
        if self.settings.enable_model_b and self.model_b.loaded:
            hazards.append("road_obstruction")
        return hazards

    def status(self) -> dict:
        s = self.settings
        return {
            "ready": self.ready,
            "warming_up": self.warming_up,
            "supported_hazards": self.supported_hazards(),
            "manual_only_hazards": [h for h in HAZARD_TYPES if h not in self.supported_hazards()],
            "models": {"A": self.model_a.status(), "B": {**self.model_b.status(), "enabled": s.enable_model_b}},
            "thresholds": {"model_a_confidence": s.conf_a, "model_b_confidence": s.conf_b, "nms_iou": s.iou},
            "imgsz": s.imgsz,
            "device": s.device,
            "preprocessing": {
                "clahe": "auto", "clahe_clip_limit": s.clahe_clip_limit, "clahe_tile": s.clahe_tile,
                "dark_luma_threshold": s.dark_luma_threshold, "low_contrast_threshold": s.low_contrast_threshold,
            },
            "roi": vars(s.roi),
            "smoothing": {
                "window": s.smoothing_window, "min_hits": s.smoothing_min_hits,
                "cooldown_seconds": s.cooldown_seconds, "dedupe_meters": s.dedupe_meters,
            },
        }

    # ------------------------------------------------------------------ inference
    def detect(self, image_bgr: np.ndarray, *, conf: float | None = None, clahe: ClaheMode | None = None,
               keep_stage_images: bool = False, use_roi: bool = True) -> DetectionResult:
        s = self.settings
        started = time.perf_counter()
        pipeline = run_pipeline(
            image_bgr, size=s.imgsz, clahe=clahe or s.clahe_mode, clip_limit=s.clahe_clip_limit, tile=s.clahe_tile,
            dark_threshold=s.dark_luma_threshold, contrast_threshold=s.low_contrast_threshold,
            keep_stage_images=keep_stage_images,
        )
        timings = {"preprocess": pipeline.total_ms}
        detections: list[Detection] = []
        models_used: list[str] = []
        rejected = 0

        if self.model_a.load():
            raw, elapsed = self.model_a.predict(pipeline.model_input, conf=conf if conf is not None else s.conf_a, iou=s.iou)
            found, _ = _to_detections(raw, pipeline, "A", None)
            detections.extend(found)
            timings["model_a"] = elapsed
            models_used.append("A")

        if s.enable_model_b and self.model_b.load():
            class_filter = self.model_b.class_ids_for(COCO_OBSTRUCTION_CLASSES) or None
            raw, elapsed = self.model_b.predict(pipeline.model_input, conf=conf if conf is not None else s.conf_b,
                                                iou=s.iou, classes=class_filter)
            found, rejected = _to_detections(raw, pipeline, "B", s.roi if use_roi else None)
            detections.extend(found)
            timings["model_b"] = elapsed
            models_used.append("B")

        if s.enable_water_pothole_detector and not any(item.hazard_type == "pothole" for item in detections):
            water_threshold = conf if conf is not None else s.conf_a
            water_candidates = [
                candidate for candidate in detect_water_filled_potholes(pipeline.enhanced)
                if candidate.confidence >= water_threshold
            ]
            for candidate in water_candidates:
                x1, y1, x2, y2 = candidate.box
                detections.append(Detection(
                    hazard_type="pothole",
                    label=HAZARD_LABELS["pothole"],
                    source_label="water-filled pothole",
                    confidence=candidate.confidence,
                    box=candidate.box,
                    box_norm=(x1 / pipeline.letterbox.original_width, y1 / pipeline.letterbox.original_height,
                              x2 / pipeline.letterbox.original_width, y2 / pipeline.letterbox.original_height),
                    model="CV",
                ))
            if water_candidates:
                models_used.append("CV")

        if not models_used:
            raise RuntimeError("No detection model is available. Add trained weights to backend/models/.")

        detections.sort(key=lambda item: item.confidence, reverse=True)
        timings["total"] = (time.perf_counter() - started) * 1000
        return DetectionResult(
            detections=detections, pipeline=pipeline,
            image_width=pipeline.letterbox.original_width, image_height=pipeline.letterbox.original_height,
            timings_ms={key: round(value, 1) for key, value in timings.items()},
            models_used=models_used, roi_rejected=rejected,
        )


_detector: HazardDetector | None = None
_detector_lock = threading.Lock()


def get_detector() -> HazardDetector:
    global _detector
    if _detector is None:
        with _detector_lock:
            if _detector is None:
                _detector = HazardDetector()
    return _detector


def set_detector(detector: HazardDetector | None) -> None:
    """Test hook: replace the process-wide detector."""
    global _detector
    _detector = detector
