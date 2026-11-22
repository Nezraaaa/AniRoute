"""Draw detection boxes for evidence frames and the Vision Lab result image."""
from __future__ import annotations

import cv2
import numpy as np

from .config import HAZARD_COLORS


def _hex_to_bgr(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    red, green, blue = (int(value[index:index + 2], 16) for index in (0, 2, 4))
    return blue, green, red


def draw_detections(image_bgr: np.ndarray, detections: list[dict], *, roi_polygon: list[tuple[float, float]] | None = None) -> np.ndarray:
    canvas = image_bgr.copy()
    height, width = canvas.shape[:2]
    thickness = max(2, round(min(height, width) / 240))
    font_scale = max(0.45, min(height, width) / 900)

    if roi_polygon:
        points = np.array([[round(x * width), round(y * height)] for x, y in roi_polygon], dtype=np.int32)
        overlay = canvas.copy()
        cv2.fillPoly(overlay, [points], (124, 58, 237))
        canvas = cv2.addWeighted(overlay, 0.12, canvas, 0.88, 0)
        cv2.polylines(canvas, [points], True, (237, 58, 124), 1, cv2.LINE_AA)

    for item in detections:
        x1, y1, x2, y2 = (int(round(value)) for value in item["box"])
        color = _hex_to_bgr(HAZARD_COLORS.get(item["hazard_type"], "#FFFFFF"))
        cv2.rectangle(canvas, (x1, y1), (x2, y2), color, thickness, cv2.LINE_AA)
        caption = f"{item['label']} {item['confidence'] * 100:.0f}%"
        (text_width, text_height), baseline = cv2.getTextSize(caption, cv2.FONT_HERSHEY_SIMPLEX, font_scale, 1)
        top = max(0, y1 - text_height - baseline - 6)
        cv2.rectangle(canvas, (x1, top), (x1 + text_width + 8, top + text_height + baseline + 6), color, -1)
        cv2.putText(canvas, caption, (x1 + 4, top + text_height + 2), cv2.FONT_HERSHEY_SIMPLEX, font_scale,
                    (255, 255, 255), 1, cv2.LINE_AA)
    return canvas


def corridor_polygon(top: float, bottom_half_width: float, top_half_width: float) -> list[tuple[float, float]]:
    return [
        (0.5 - top_half_width, top), (0.5 + top_half_width, top),
        (0.5 + bottom_half_width, 1.0), (0.5 - bottom_half_width, 1.0),
    ]
