"""Image preprocessing used by both the live app and ml/evaluate.py.

Keeping one implementation guarantees that the evaluation numbers describe exactly
what the running system does.

Pipeline (each step is recorded as a stage for the before/after UI):
1. decode + EXIF orientation fix      (phone photos are often stored rotated)
2. CLAHE contrast enhancement          (only when the frame is dark or low-contrast)
3. optional bilateral denoise          (edge-preserving noise reduction)
4. letterbox to a square model input   (keeps aspect ratio, pads with grey)
Normalisation to 0-1 floats happens inside the YOLO runtime.
"""
from __future__ import annotations

import base64
import binascii
import io
import re
import time
from dataclasses import dataclass, field
from typing import Literal

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

ClaheMode = Literal["auto", "on", "off"]
_DATA_URL = re.compile(r"data:image/(jpeg|jpg|png|webp);base64,([A-Za-z0-9+/=\s]+)")


class ImageDecodeError(ValueError):
    pass


def decode_data_url(data_url: str) -> bytes:
    match = _DATA_URL.fullmatch(data_url.strip())
    if not match:
        raise ImageDecodeError("Expected a JPEG, PNG or WebP data URL.")
    try:
        return base64.b64decode(match.group(2), validate=False)
    except (binascii.Error, ValueError) as exc:
        raise ImageDecodeError("Image data is not valid base64.") from exc


def decode_image(data: bytes) -> np.ndarray:
    """Decode bytes into a BGR uint8 array with EXIF orientation applied."""
    try:
        with Image.open(io.BytesIO(data)) as image:
            image = ImageOps.exif_transpose(image)
            rgb = np.asarray(image.convert("RGB"))
    except (UnidentifiedImageError, OSError) as exc:
        raise ImageDecodeError("The file is not a readable image.") from exc
    if rgb.ndim != 3 or rgb.shape[0] < 8 or rgb.shape[1] < 8:
        raise ImageDecodeError("The image is too small.")
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def luminance_stats(image_bgr: np.ndarray) -> tuple[float, float]:
    """Mean and standard deviation of perceptual lightness (LAB L channel, 0-255)."""
    lightness = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2LAB)[:, :, 0]
    return float(lightness.mean()), float(lightness.std())


def needs_enhancement(image_bgr: np.ndarray, dark_threshold: float, contrast_threshold: float) -> bool:
    mean, std = luminance_stats(image_bgr)
    return mean < dark_threshold or std < contrast_threshold


def enhance_contrast_clahe(image_bgr: np.ndarray, clip_limit: float = 2.0, tile: int = 8) -> np.ndarray:
    """Contrast Limited Adaptive Histogram Equalisation on the L channel only.

    Equalising lightness (not colour) brightens shadows and night frames without
    shifting hues, so water stays blue-grey and asphalt stays grey.
    """
    lab = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2LAB)
    lightness, a_channel, b_channel = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(tile, tile))
    merged = cv2.merge((clahe.apply(lightness), a_channel, b_channel))
    return cv2.cvtColor(merged, cv2.COLOR_LAB2BGR)


def denoise(image_bgr: np.ndarray) -> np.ndarray:
    return cv2.bilateralFilter(image_bgr, d=5, sigmaColor=50, sigmaSpace=50)


@dataclass(frozen=True)
class LetterboxInfo:
    scale: float
    pad_x: float
    pad_y: float
    size: int
    original_width: int
    original_height: int


def letterbox(image_bgr: np.ndarray, size: int = 640, color: tuple[int, int, int] = (114, 114, 114)) -> tuple[np.ndarray, LetterboxInfo]:
    height, width = image_bgr.shape[:2]
    scale = min(size / width, size / height)
    new_width, new_height = round(width * scale), round(height * scale)
    resized = cv2.resize(image_bgr, (new_width, new_height), interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR)
    pad_x, pad_y = (size - new_width) / 2, (size - new_height) / 2
    top, bottom = int(round(pad_y - 0.1)), int(round(pad_y + 0.1))
    left, right = int(round(pad_x - 0.1)), int(round(pad_x + 0.1))
    boxed = cv2.copyMakeBorder(resized, top, bottom, left, right, cv2.BORDER_CONSTANT, value=color)
    boxed = cv2.resize(boxed, (size, size)) if boxed.shape[:2] != (size, size) else boxed
    return boxed, LetterboxInfo(scale, float(left), float(top), size, width, height)


def unletterbox_boxes(boxes_xyxy: np.ndarray, info: LetterboxInfo) -> np.ndarray:
    """Map boxes predicted on the letterboxed image back to original pixel coordinates."""
    if boxes_xyxy.size == 0:
        return boxes_xyxy.reshape(0, 4).astype(float)
    boxes = boxes_xyxy.astype(float).copy()
    boxes[:, [0, 2]] = (boxes[:, [0, 2]] - info.pad_x) / info.scale
    boxes[:, [1, 3]] = (boxes[:, [1, 3]] - info.pad_y) / info.scale
    boxes[:, [0, 2]] = boxes[:, [0, 2]].clip(0, info.original_width)
    boxes[:, [1, 3]] = boxes[:, [1, 3]].clip(0, info.original_height)
    return boxes


@dataclass
class Stage:
    name: str
    description: str
    applied: bool
    ms: float
    image: np.ndarray | None = None


@dataclass
class PipelineResult:
    enhanced: np.ndarray          # original size, after enhancement (used for display/evidence)
    model_input: np.ndarray       # letterboxed square passed to YOLO
    letterbox: LetterboxInfo
    clahe_applied: bool
    luminance_mean: float
    luminance_std: float
    stages: list[Stage] = field(default_factory=list)
    total_ms: float = 0.0


def run_pipeline(
    image_bgr: np.ndarray,
    *,
    size: int = 640,
    clahe: ClaheMode = "auto",
    clip_limit: float = 2.0,
    tile: int = 8,
    dark_threshold: float = 95.0,
    contrast_threshold: float = 38.0,
    apply_denoise: bool = False,
    keep_stage_images: bool = False,
) -> PipelineResult:
    started = time.perf_counter()
    stages: list[Stage] = []
    current = image_bgr
    stages.append(Stage("original", "Decoded frame, orientation corrected", True, 0.0, current if keep_stage_images else None))

    t0 = time.perf_counter()
    mean, std = luminance_stats(current)
    should_enhance = clahe == "on" or (clahe == "auto" and (mean < dark_threshold or std < contrast_threshold))
    if should_enhance:
        current = enhance_contrast_clahe(current, clip_limit, tile)
    reason = (
        "forced on" if clahe == "on" else "disabled" if clahe == "off"
        else f"dark/low-contrast frame (L mean {mean:.0f}, std {std:.0f})" if should_enhance
        else f"skipped: frame already well exposed (L mean {mean:.0f}, std {std:.0f})"
    )
    stages.append(Stage("clahe", f"CLAHE contrast enhancement · {reason}", should_enhance,
                        (time.perf_counter() - t0) * 1000, current if keep_stage_images else None))

    if apply_denoise:
        t0 = time.perf_counter()
        current = denoise(current)
        stages.append(Stage("denoise", "Bilateral edge-preserving denoise", True,
                            (time.perf_counter() - t0) * 1000, current if keep_stage_images else None))

    t0 = time.perf_counter()
    boxed, info = letterbox(current, size)
    stages.append(Stage("letterbox", f"Letterbox resize to {size}×{size} (aspect ratio kept, grey padding)", True,
                        (time.perf_counter() - t0) * 1000, boxed if keep_stage_images else None))

    return PipelineResult(
        enhanced=current, model_input=boxed, letterbox=info, clahe_applied=should_enhance,
        luminance_mean=mean, luminance_std=std, stages=stages,
        total_ms=(time.perf_counter() - started) * 1000,
    )


def encode_jpeg_data_url(image_bgr: np.ndarray, quality: int = 82, max_side: int | None = 960) -> str:
    image = image_bgr
    if max_side:
        height, width = image.shape[:2]
        scale = max_side / max(height, width)
        if scale < 1:
            image = cv2.resize(image, (round(width * scale), round(height * scale)), interpolation=cv2.INTER_AREA)
    ok, buffer = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not ok:
        raise ValueError("Could not encode image.")
    return "data:image/jpeg;base64," + base64.b64encode(buffer.tobytes()).decode("ascii")
