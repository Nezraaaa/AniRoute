"""Thin, lazily loaded wrapper around an Ultralytics YOLO model.

The wrapper hides the runtime format (PyTorch .pt, ONNX or OpenVINO) and returns
plain Python data so the rest of the backend never imports ultralytics directly.
That keeps the API importable (and testable) even when the CV runtime is missing.
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

logger = logging.getLogger("aniroute.vision")


@dataclass(frozen=True)
class RawBox:
    class_id: int
    label: str
    confidence: float
    xyxy: tuple[float, float, float, float]   # pixels in the model-input image


def resolve_weights(path: Path, model_format: str) -> Path:
    """Pick the fastest exported format that exists next to the .pt weights.

    auto: OpenVINO dir → ONNX file → .pt. An explicit format falls back to .pt when missing.
    """
    stem = path.with_suffix("")
    candidates = {
        "openvino": Path(f"{stem}_openvino_model"),
        "onnx": stem.with_suffix(".onnx"),
        "pt": path,
    }
    order = ["openvino", "onnx", "pt"] if model_format == "auto" else [model_format, "pt"]
    for key in order:
        candidate = candidates.get(key)
        if candidate is not None and candidate.exists():
            return candidate
    return path


class YoloModel:
    def __init__(self, name: str, weights: Path, *, model_format: str = "auto", device: str = "cpu",
                 imgsz: int = 640, allow_download: bool = False) -> None:
        self.name = name
        self.weights = weights
        self.model_format = model_format
        self.device = device
        self.imgsz = imgsz
        self.allow_download = allow_download
        self._model = None
        self._lock = threading.Lock()
        self.class_names: dict[int, str] = {}
        self.loaded_from: Path | None = None
        self.error: str | None = None
        self.load_ms: float | None = None

    @property
    def loaded(self) -> bool:
        return self._model is not None

    def weights_available(self) -> bool:
        return resolve_weights(self.weights, self.model_format).exists() or self.allow_download

    def load(self) -> bool:
        if self._model is not None:
            return True
        with self._lock:
            if self._model is not None:
                return True
            target = resolve_weights(self.weights, self.model_format)
            if not target.exists() and not self.allow_download:
                self.error = f"Weights not found: {self.weights.name}"
                return False
            started = time.perf_counter()
            try:
                from ultralytics import YOLO  # imported lazily: heavy dependency

                if not target.exists():
                    target.parent.mkdir(parents=True, exist_ok=True)
                model = YOLO(str(target), task="detect")
                names = model.names if isinstance(model.names, dict) else dict(enumerate(model.names))
                self.class_names = {int(key): str(value) for key, value in names.items()}
                self._model = model
                self.loaded_from = target
                self.error = None
                self.load_ms = (time.perf_counter() - started) * 1000
                logger.info("Loaded %s from %s in %.0f ms", self.name, target, self.load_ms)
                return True
            except Exception as exc:  # noqa: BLE001 - any runtime failure must degrade gracefully
                self.error = f"{type(exc).__name__}: {exc}"
                logger.warning("Could not load %s: %s", self.name, self.error)
                return False

    def predict(self, image_bgr: np.ndarray, *, conf: float, iou: float,
                classes: list[int] | None = None) -> tuple[list[RawBox], float]:
        if not self.load():
            raise RuntimeError(self.error or f"{self.name} is unavailable.")
        started = time.perf_counter()
        with self._lock:
            results = self._model.predict(
                image_bgr, imgsz=self.imgsz, conf=conf, iou=iou, device=self.device,
                classes=classes, verbose=False,
            )
        elapsed = (time.perf_counter() - started) * 1000
        boxes: list[RawBox] = []
        if not results:
            return boxes, elapsed
        result = results[0]
        if result.boxes is None or len(result.boxes) == 0:
            return boxes, elapsed
        xyxy = result.boxes.xyxy.cpu().numpy()
        confidences = result.boxes.conf.cpu().numpy()
        class_ids = result.boxes.cls.cpu().numpy().astype(int)
        for box, confidence, class_id in zip(xyxy, confidences, class_ids):
            boxes.append(RawBox(
                class_id=int(class_id),
                label=self.class_names.get(int(class_id), str(class_id)),
                confidence=float(confidence),
                xyxy=(float(box[0]), float(box[1]), float(box[2]), float(box[3])),
            ))
        return boxes, elapsed

    def class_ids_for(self, labels: tuple[str, ...]) -> list[int]:
        wanted = set(labels)
        return [class_id for class_id, label in self.class_names.items() if label in wanted]

    def status(self) -> dict:
        return {
            "name": self.name,
            "weights": self.weights.name,
            "loaded": self.loaded,
            "loaded_from": self.loaded_from.name if self.loaded_from else None,
            "runtime_format": (
                "openvino" if self.loaded_from and self.loaded_from.name.endswith("_openvino_model")
                else self.loaded_from.suffix.lstrip(".") if self.loaded_from else None
            ),
            "available": self.loaded or self.weights_available(),
            "classes": list(self.class_names.values()),
            "load_ms": round(self.load_ms, 1) if self.load_ms is not None else None,
            "error": self.error,
        }
