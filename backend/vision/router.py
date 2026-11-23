"""HTTP endpoints for the computer-vision service (detection, model info, reports)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from .annotate import corridor_polygon, draw_detections
from .config import HAZARD_COLORS, HAZARD_LABELS, REPORTS_DIR, SAMPLES_DIR
from .ensemble import DetectionResult, get_detector
from .preprocess import ImageDecodeError, decode_data_url, decode_image, encode_jpeg_data_url
from .smoothing import TemporalHazardFilter

router = APIRouter()

MAX_UPLOAD_BYTES = 8 * 1024 * 1024
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov"}
REPORT_JSON_FILES = (
    "metrics", "optimization", "ablation", "latency", "robustness", "dataset_stats",
    "smoothing", "model_b", "system", "high_confidence_profile",
)
REPORT_IMAGES = (
    "confusion_matrix.png", "confusion_matrix_normalized.png", "pr_curve.png", "f1_confidence_curve.png",
    "training_curves.png", "optimization_chart.png", "ablation_bar.png", "speed_chart.png",
    "preprocessing_before_after.png", "dataset_class_distribution.png", "dataset_samples.png",
    "model_b_roi_example.png",
)

_hazard_filter: TemporalHazardFilter | None = None


def get_hazard_filter() -> TemporalHazardFilter:
    global _hazard_filter
    if _hazard_filter is None:
        s = get_detector().settings
        _hazard_filter = TemporalHazardFilter(
            window=s.smoothing_window, min_hits=s.smoothing_min_hits,
            cooldown_s=s.cooldown_seconds, dedupe_m=s.dedupe_meters,
        )
    return _hazard_filter


def set_hazard_filter(value: TemporalHazardFilter | None) -> None:
    global _hazard_filter
    _hazard_filter = value


def run_detection(image_bytes: bytes, *, conf: float | None = None, clahe: str | None = None,
                  keep_stage_images: bool = False) -> DetectionResult:
    try:
        image = decode_image(image_bytes)
    except ImageDecodeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    detector = get_detector()
    try:
        return detector.detect(image, conf=conf, clahe=clahe, keep_stage_images=keep_stage_images)  # type: ignore[arg-type]
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def detection_payload(result: DetectionResult, *, return_stages: bool = False, annotate: bool = False) -> dict:
    detections = [item.to_dict() for item in result.detections]
    payload: dict = {
        "detections": detections,
        "image": {"width": result.image_width, "height": result.image_height},
        "timings_ms": result.timings_ms,
        "models_used": result.models_used,
        "roi_rejected": result.roi_rejected,
        "preprocessing": {
            "clahe_applied": result.pipeline.clahe_applied,
            "luminance_mean": round(result.pipeline.luminance_mean, 1),
            "luminance_std": round(result.pipeline.luminance_std, 1),
        },
        "data_source": "api",
    }
    if annotate:
        roi = get_detector().settings.roi
        polygon = corridor_polygon(roi.top, roi.bottom_half_width, roi.top_half_width) if "B" in result.models_used else None
        payload["annotated_image"] = encode_jpeg_data_url(draw_detections(result.pipeline.enhanced, detections, roi_polygon=polygon))
    if return_stages:
        payload["stages"] = [
            {
                "name": stage.name,
                "description": stage.description,
                "applied": stage.applied,
                "ms": round(stage.ms, 2),
                "image": encode_jpeg_data_url(stage.image, quality=78, max_side=720) if stage.image is not None else None,
            }
            for stage in result.pipeline.stages
        ]
    return payload


class FrameRequest(BaseModel):
    frame_data_url: str = Field(min_length=30, max_length=3_000_000)
    conf: float | None = Field(default=None, ge=0.01, le=0.99)
    clahe: Literal["auto", "on", "off"] | None = None   # None = server default (ANIROUTE_CLAHE)
    return_stages: bool = False
    annotate: bool = False


@router.get("/api/model/info")
def model_info() -> dict:
    detector = get_detector()
    return {
        **detector.status(),
        "hazard_labels": HAZARD_LABELS,
        "hazard_colors": HAZARD_COLORS,
        "evaluated": (REPORTS_DIR / "metrics.json").exists(),
    }


@router.post("/api/vision/detect")
def detect_upload(
    file: UploadFile = File(...),
    conf: float | None = Form(default=None, ge=0.01, le=0.99),
    clahe: Literal["auto", "on", "off"] | None = Form(default=None),
    return_stages: bool = Form(default=True),
) -> dict:
    if file.content_type and not file.content_type.startswith("image/"):
        raise HTTPException(status_code=415, detail="Upload a JPEG, PNG or WebP image.")
    data = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Image must be 8 MB or smaller.")
    if not data:
        raise HTTPException(status_code=422, detail="The uploaded file is empty.")
    result = run_detection(data, conf=conf, clahe=clahe, keep_stage_images=return_stages)
    return {**detection_payload(result, return_stages=return_stages, annotate=True), "filename": file.filename}


@router.post("/api/vision/detect-frame")
def detect_frame(payload: FrameRequest) -> dict:
    try:
        data = decode_data_url(payload.frame_data_url)
    except ImageDecodeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if len(data) > 2_000_000:
        raise HTTPException(status_code=413, detail="Frame must be 2 MB or smaller.")
    result = run_detection(data, conf=payload.conf, clahe=payload.clahe, keep_stage_images=payload.return_stages)
    return detection_payload(result, return_stages=payload.return_stages, annotate=payload.annotate)


def _read_json(path: Path) -> dict | list | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


@router.get("/api/model/metrics")
def model_metrics() -> dict:
    reports = {name: _read_json(REPORTS_DIR / f"{name}.json") for name in REPORT_JSON_FILES}
    images = {name: f"/reports/{name}" for name in REPORT_IMAGES if (REPORTS_DIR / name).exists()}
    gallery: dict[str, list[dict]] = {}
    gallery_dir = REPORTS_DIR / "error_gallery"
    if gallery_dir.is_dir():
        captions = _read_json(gallery_dir / "captions.json") or {}
        for category in sorted(path for path in gallery_dir.iterdir() if path.is_dir()):
            gallery[category.name] = [
                {"url": f"/reports/error_gallery/{category.name}/{item.name}",
                 "caption": captions.get(f"{category.name}/{item.name}", "") if isinstance(captions, dict) else ""}
                for item in sorted(category.iterdir()) if item.suffix.lower() in IMAGE_EXTENSIONS
            ][:12]
    error_analysis = None
    try:
        error_analysis = (REPORTS_DIR / "error_analysis.md").read_text(encoding="utf-8")
    except OSError:
        pass
    return {
        "status": "evaluated" if reports.get("metrics") else "pending",
        "reports": {key: value for key, value in reports.items() if value is not None},
        "images": images,
        "error_gallery": gallery,
        "error_analysis": error_analysis,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/api/samples")
def list_samples() -> list[dict]:
    if not SAMPLES_DIR.is_dir():
        return []
    captions = _read_json(SAMPLES_DIR / "samples.json") or {}
    items = []
    for path in sorted(SAMPLES_DIR.iterdir()):
        suffix = path.suffix.lower()
        kind = "image" if suffix in IMAGE_EXTENSIONS else "video" if suffix in VIDEO_EXTENSIONS else None
        if kind is None or not path.is_file():
            continue
        meta = captions.get(path.name, {}) if isinstance(captions, dict) else {}
        items.append({
            "name": path.name,
            "kind": kind,
            "url": f"/samples/{path.name}",
            "bytes": path.stat().st_size,
            "caption": meta.get("caption", "") if isinstance(meta, dict) else "",
            "source": meta.get("source", "") if isinstance(meta, dict) else "",
            "demo": bool(meta.get("demo", False)) if isinstance(meta, dict) else False,
        })
    return items
