"""OpenCV detector for reflective, water-filled potholes.

The trained road-damage model can miss potholes when standing water hides the
surface texture it learned. This detector looks for a smooth, bright water
surface enclosed by a much darker, horizontally elongated road depression.
Its results still pass through the application's temporal confirmation step.
"""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(frozen=True)
class WaterPotholeCandidate:
    box: tuple[float, float, float, float]
    confidence: float


def _odd_kernel(value: float, minimum: int) -> int:
    size = max(minimum, int(round(value)))
    return size if size % 2 else size + 1


def detect_water_filled_potholes(image_bgr: np.ndarray) -> list[WaterPotholeCandidate]:
    """Find bright, low-texture water pools surrounded by a dark road rim."""
    if image_bgr.ndim != 3 or image_bgr.shape[2] != 3:
        return []
    height, width = image_bgr.shape[:2]
    if height < 80 or width < 80:
        return []

    minimum_side = min(height, width)
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)

    local_window = _odd_kernel(minimum_side * 0.028, 9)
    gray_float = gray.astype(np.float32)
    local_mean = cv2.blur(gray_float, (local_window, local_window))
    local_square_mean = cv2.blur(gray_float * gray_float, (local_window, local_window))
    local_std = np.sqrt(np.maximum(local_square_mean - local_mean * local_mean, 0))

    # Water reflecting an overcast sky is usually brighter, smoother and less
    # saturated than the broken asphalt around it.
    mask = ((gray > 120) & (hsv[:, :, 1] < 75) & (local_std < 20)).astype(np.uint8) * 255
    mask[: int(height * 0.20)] = 0  # Ignore sky, snowbanks and the distant horizon.

    open_size = _odd_kernel(minimum_side * 0.009, 3)
    close_size = _odd_kernel(minimum_side * 0.032, 9)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (open_size, open_size)))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (close_size, close_size)))

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    image_area = float(width * height)
    candidates: list[WaterPotholeCandidate] = []

    for contour in contours:
        area = float(cv2.contourArea(contour))
        area_ratio = area / image_area
        if not 0.003 <= area_ratio <= 0.12:
            continue

        x, y, box_width, box_height = cv2.boundingRect(contour)
        if box_height <= 0:
            continue
        aspect = box_width / box_height
        fill_ratio = area / max(float(box_width * box_height), 1.0)
        if not 1.7 <= aspect <= 7.0 or fill_ratio < 0.35 or box_width < width * 0.12:
            continue
        if y + box_height / 2 < height * 0.30:
            continue

        contour_mask = np.zeros((height, width), dtype=np.uint8)
        cv2.drawContours(contour_mask, [contour], -1, 255, thickness=-1)
        ring_size = _odd_kernel(minimum_side * 0.08, 15)
        surrounding = cv2.dilate(contour_mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (ring_size, ring_size)))
        surrounding = cv2.subtract(surrounding, contour_mask)
        inside_luma = float(cv2.mean(gray, mask=contour_mask)[0])
        surrounding_luma = float(cv2.mean(gray, mask=surrounding)[0])
        rim_contrast = inside_luma - surrounding_luma
        if rim_contrast < 35:
            continue

        # Expand from the water surface to include the broken asphalt rim.
        left = max(0.0, x - box_width * 0.25)
        top = max(0.0, y - box_height * 0.75)
        right = min(float(width), x + box_width * 1.25)
        bottom = min(float(height), y + box_height * 2.20)
        confidence = min(
            0.68,
            0.42
            + min(area_ratio * 2.0, 0.08)
            + min(max(rim_contrast - 35, 0) / 400, 0.12)
            + min(fill_ratio * 0.08, 0.06),
        )
        candidates.append(WaterPotholeCandidate((left, top, right, bottom), confidence))

    return sorted(candidates, key=lambda item: item.confidence, reverse=True)[:3]
