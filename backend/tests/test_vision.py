"""Vision service tests. They use a fake model, so no trained weights are needed."""
from __future__ import annotations

import base64
import io

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend import main
from backend.vision import ensemble, router as vision_router
from backend.vision.config import RoiSettings, VisionSettings
from backend.vision.detector import RawBox, resolve_weights
from backend.vision.ensemble import HazardDetector, in_driving_corridor, map_model_a_label
from backend.vision.preprocess import (
    decode_data_url, decode_image, enhance_contrast_clahe, letterbox, luminance_stats, run_pipeline,
    unletterbox_boxes,
)
from backend.vision.smoothing import TemporalHazardFilter


def png_bytes(image: np.ndarray) -> bytes:
    ok, buffer = cv2.imencode(".png", image)
    assert ok
    return buffer.tobytes()


def jpeg_data_url(image: np.ndarray) -> str:
    ok, buffer = cv2.imencode(".jpg", image)
    assert ok
    return "data:image/jpeg;base64," + base64.b64encode(buffer.tobytes()).decode()


def road_image(width: int = 1280, height: int = 720, brightness: int = 150) -> np.ndarray:
    rng = np.random.default_rng(7)
    image = np.clip(rng.normal(brightness, 30, (height, width, 3)), 0, 255).astype(np.uint8)
    return image


# --------------------------------------------------------------------------- preprocessing
def test_letterbox_keeps_aspect_ratio_and_maps_boxes_back():
    image = road_image(1280, 720)
    boxed, info = letterbox(image, 640)
    assert boxed.shape == (640, 640, 3)
    assert info.scale == pytest.approx(0.5)
    assert info.pad_y == pytest.approx(140)
    # A box drawn on the letterboxed image maps back to original pixels.
    original = np.array([[100.0, 200.0, 300.0, 400.0]])
    on_boxed = original * info.scale + np.array([info.pad_x, info.pad_y, info.pad_x, info.pad_y])
    np.testing.assert_allclose(unletterbox_boxes(on_boxed, info), original, atol=1e-6)


def test_letterbox_handles_odd_padding():
    boxed, info = letterbox(road_image(641, 359), 640)
    assert boxed.shape == (640, 640, 3)
    assert info.original_width == 641 and info.original_height == 359


def well_exposed_image() -> np.ndarray:
    """Bright scene with real structure (sky-to-road gradient), like a daytime dashcam frame."""
    gradient = np.linspace(250, 80, 720, dtype=np.float32)[:, None, None]
    return np.repeat(np.repeat(gradient, 1280, axis=1), 3, axis=2).astype(np.uint8)


def test_clahe_brightens_dark_frames_but_auto_mode_skips_bright_ones():
    dark = road_image(brightness=40)
    enhanced = enhance_contrast_clahe(dark)
    assert enhanced.shape == dark.shape and enhanced.dtype == np.uint8
    assert luminance_stats(enhanced)[1] > luminance_stats(dark)[1]  # more contrast

    dark_result = run_pipeline(dark, clahe="auto")
    bright_result = run_pipeline(well_exposed_image(), clahe="auto")
    assert dark_result.clahe_applied is True
    assert bright_result.clahe_applied is False
    assert run_pipeline(well_exposed_image(), clahe="on").clahe_applied is True
    assert run_pipeline(dark, clahe="off").clahe_applied is False


def test_pipeline_records_stages_for_before_after_view():
    result = run_pipeline(road_image(), clahe="on", keep_stage_images=True)
    assert [stage.name for stage in result.stages] == ["original", "clahe", "letterbox"]
    assert result.stages[-1].image.shape == (640, 640, 3)
    assert result.model_input.shape == (640, 640, 3)


def test_decode_image_and_data_url_validation():
    image = road_image(64, 48)
    decoded = decode_image(png_bytes(image))
    assert decoded.shape == (48, 64, 3)
    assert decode_data_url(jpeg_data_url(image))[:2] == b"\xff\xd8"
    with pytest.raises(ValueError):
        decode_data_url("data:text/plain;base64,aGVsbG8=")
    with pytest.raises(ValueError):
        decode_image(b"not an image")


# --------------------------------------------------------------------------- integration rules
def test_model_a_labels_map_to_app_hazard_types():
    assert map_model_a_label("pothole") == "pothole"
    assert map_model_a_label("D40") == "pothole"
    assert map_model_a_label("D20") == "severe_road_damage"
    assert map_model_a_label("severe_road_damage") == "severe_road_damage"
    assert map_model_a_label("traffic light") is None


def test_driving_corridor_keeps_in_lane_objects_only():
    roi = RoiSettings()
    width, height = 1000, 1000
    assert in_driving_corridor((420, 500, 580, 900), width, height, roi)        # cow in front of the vehicle
    assert not in_driving_corridor((20, 500, 150, 900), width, height, roi)     # parked at the roadside
    assert not in_driving_corridor((480, 100, 520, 200), width, height, roi)    # far away above horizon
    assert not in_driving_corridor((480, 860, 520, 900), width, height, roi)    # too small / far


class FakeModel:
    """Stands in for YoloModel; returns boxes in model-input (letterboxed) pixels."""

    def __init__(self, name: str, boxes: list[RawBox], class_names: dict[int, str]):
        self.name = name
        self.boxes = boxes
        self.class_names = class_names
        self.loaded = True
        self.calls = 0

    def load(self) -> bool:
        return True

    def predict(self, image, *, conf, iou, classes=None):
        self.calls += 1
        return [box for box in self.boxes if box.confidence >= conf], 1.5

    def class_ids_for(self, labels):
        return [key for key, value in self.class_names.items() if value in labels]

    def status(self):
        return {"name": self.name, "loaded": True, "available": True, "classes": list(self.class_names.values()),
                "weights": "fake.pt", "loaded_from": "fake.pt", "runtime_format": "pt", "load_ms": 0, "error": None}


def fake_detector() -> HazardDetector:
    detector = HazardDetector(VisionSettings(warmup=False, conf_a=0.35, enable_model_b=True))
    # 1280x720 → letterbox 640: scale 0.5, pad_y 140.
    detector.model_a = FakeModel("A", [  # type: ignore[assignment]
        RawBox(0, "pothole", 0.91, (300, 400, 380, 440)),
        RawBox(1, "severe_road_damage", 0.20, (100, 300, 200, 340)),   # below threshold
    ], {0: "pothole", 1: "severe_road_damage"})
    detector.model_b = FakeModel("B", [  # type: ignore[assignment]
        RawBox(19, "cow", 0.88, (290, 300, 350, 470)),     # in lane, tall → obstruction
        RawBox(2, "car", 0.90, (5, 330, 60, 400)),          # roadside → rejected by ROI
    ], {2: "car", 19: "cow", 9: "traffic light"})
    return detector


def test_ensemble_merges_both_models_into_hazard_types():
    detector = fake_detector()
    result = detector.detect(road_image(), clahe="off")
    kinds = [(item.hazard_type, item.model, item.source_label) for item in result.detections]
    assert ("pothole", "A", "pothole") in kinds
    assert ("road_obstruction", "B", "cow") in kinds
    assert all(item.hazard_type != "severe_road_damage" for item in result.detections)
    assert result.roi_rejected == 1
    assert result.models_used == ["A", "B"]
    pothole = next(item for item in result.detections if item.hazard_type == "pothole")
    assert pothole.box == pytest.approx((600, 520, 760, 600))   # mapped back to 1280x720 pixels
    assert detector.model_a.calls == 1 and detector.model_b.calls == 1  # type: ignore[attr-defined]


# --------------------------------------------------------------------------- smoothing
def test_smoothing_requires_two_of_three_frames():
    hazard = [{"hazard_type": "pothole", "confidence": 0.8}]
    smoother = TemporalHazardFilter(window=3, min_hits=2, cooldown_s=20)
    assert smoother.update("r", hazard, now=0) is None
    alert = smoother.update("r", hazard, now=1)
    assert alert is not None and alert["hazard_type"] == "pothole" and alert["frames_seen"] == 2
    # A one-frame flicker of another class never alerts.
    assert smoother.update("r", [{"hazard_type": "standing_water", "confidence": 0.9}], now=2) is None
    assert smoother.update("r", [], now=3) is None


def test_smoothing_cooldown_and_dedupe():
    hazard = [{"hazard_type": "pothole", "confidence": 0.8}]
    smoother = TemporalHazardFilter(window=3, min_hits=2, cooldown_s=20, dedupe_m=50)
    here = (14.2, 121.1)
    smoother.update("r", hazard, here, now=0)
    assert smoother.update("r", hazard, here, now=1) is not None
    smoother.update("r", hazard, here, now=5)
    assert smoother.update("r", hazard, here, now=6) is None          # cooldown
    assert smoother.update("r", hazard, here, now=40) is None         # same spot → duplicate
    assert smoother.update("r", hazard, here, now=41) is None
    far = (14.21, 121.1)                                              # ~1.1 km further on
    assert smoother.update("r", hazard, far, now=42) is not None      # streak continues → new alert
    assert smoother.stats["suppressed_duplicate"] == 2


# --------------------------------------------------------------------------- endpoints
@pytest.fixture()
def client(monkeypatch, tmp_path):
    detector = fake_detector()
    monkeypatch.setattr(ensemble, "_detector", detector)
    monkeypatch.setattr(main, "DATA_DIR", tmp_path)
    vision_router.set_hazard_filter(None)
    yield TestClient(main.app)
    vision_router.set_hazard_filter(None)


def test_detect_upload_returns_boxes_annotated_image_and_stages(client):
    response = client.post("/api/vision/detect", files={"file": ("road.png", png_bytes(road_image()), "image/png")},
                           data={"clahe": "on", "return_stages": "true"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert {item["hazard_type"] for item in body["detections"]} == {"pothole", "road_obstruction"}
    assert body["annotated_image"].startswith("data:image/jpeg;base64,")
    assert [stage["name"] for stage in body["stages"]] == ["original", "clahe", "letterbox"]
    assert body["preprocessing"]["clahe_applied"] is True
    assert body["image"] == {"width": 1280, "height": 720}


def test_detect_rejects_non_images(client):
    response = client.post("/api/vision/detect", files={"file": ("notes.txt", b"hello", "text/plain")})
    assert response.status_code == 415
    response = client.post("/api/vision/detect", files={"file": ("bad.png", b"garbage", "image/png")})
    assert response.status_code == 422


def test_detect_returns_503_without_any_model(monkeypatch):
    detector = HazardDetector(VisionSettings(warmup=False, conf_a=0.35, enable_model_b=True))
    detector.model_a.load = lambda: False
    detector.model_b.load = lambda: False
    monkeypatch.setattr(ensemble, "_detector", detector)
    response = TestClient(main.app).post("/api/vision/detect", files={"file": ("road.png", png_bytes(road_image(64, 64)), "image/png")})
    assert response.status_code == 503


def test_scan_frame_alerts_after_two_frames_and_returns_overlay_boxes(client):
    frame = jpeg_data_url(road_image(640, 360))
    body = {"route_id": "route-1", "captured_at": "2026-11-22T10:00:00Z", "latitude": 14.2, "longitude": 121.1, "frame_data_url": frame}
    first = client.post("/api/hazards/scan-frame", json=body).json()
    assert first["data_source"] == "api"
    assert first["detection"] is None and len(first["detections"]) >= 1
    second = client.post("/api/hazards/scan-frame", json=body).json()
    assert second["detection"]["hazard_type"] in {"pothole", "road_obstruction"}
    assert second["detection"]["road_segment_id"] == "route-1@14.2000,121.1000"
    assert second["evidence_frame_data_url"].startswith("data:image/jpeg")


def test_model_info_and_metrics_pending(client, monkeypatch, tmp_path):
    monkeypatch.setattr(vision_router, "REPORTS_DIR", tmp_path)
    info = client.get("/api/model/info").json()
    assert info["supported_hazards"] == ["pothole", "severe_road_damage", "road_obstruction"]
    assert "standing_water" in info["manual_only_hazards"]
    metrics = client.get("/api/model/metrics").json()
    assert metrics["status"] == "pending"
    (tmp_path / "metrics.json").write_text('{"overall": {"map50": 0.5}}', encoding="utf-8")
    assert client.get("/api/model/metrics").json()["status"] == "evaluated"


def test_resolve_weights_prefers_exported_formats(tmp_path):
    weights = tmp_path / "model.pt"
    weights.write_bytes(b"x")
    assert resolve_weights(weights, "auto") == weights
    (tmp_path / "model.onnx").write_bytes(b"x")
    assert resolve_weights(weights, "auto").suffix == ".onnx"
    (tmp_path / "model_openvino_model").mkdir()
    assert resolve_weights(weights, "auto").name == "model_openvino_model"
    assert resolve_weights(weights, "pt") == weights


def test_png_helper_roundtrip():
    assert decode_image(io.BytesIO(png_bytes(road_image(32, 32))).getvalue()).shape == (32, 32, 3)
