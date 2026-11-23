"""Run the deployed detector (same code path as the app) on the sample images and save annotated copies.

  python ml/scripts/annotate_samples.py

Writes ml/reports/sample_detections/<name>.jpg (boxes, class, confidence, Model B driving corridor) and
captions.json, used by the Results slide and the README. Test images were never used in training.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import cv2

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
os.environ.setdefault("ANIROUTE_VISION_WARMUP", "false")

from backend.vision.annotate import corridor_polygon, draw_detections  # noqa: E402
from backend.vision.config import VisionSettings  # noqa: E402
from backend.vision.ensemble import HazardDetector  # noqa: E402

SAMPLES = REPO / "backend" / "samples"
OUT = REPO / "ml" / "reports" / "sample_detections"


def main() -> None:
    detector = HazardDetector(VisionSettings(warmup=False))
    if not detector.load():
        raise SystemExit("No model available.")
    roi = detector.settings.roi
    OUT.mkdir(parents=True, exist_ok=True)
    captions = {}
    for path in sorted(SAMPLES.glob("*.jpg")):
        image = cv2.imread(str(path))
        if image is None:
            continue
        result = detector.detect(image)
        detections = [item.to_dict() for item in result.detections]
        polygon = corridor_polygon(roi.top, roi.bottom_half_width, roi.top_half_width) if "B" in result.models_used else None
        cv2.imwrite(str(OUT / path.name), draw_detections(result.pipeline.enhanced, detections, roi_polygon=polygon))
        found = ", ".join(f"{d['hazard_type'].replace('_', ' ')} {d['confidence']:.0%}" for d in detections) or "nothing detected"
        captions[path.name] = found
        print(f"{path.name}: {found}")
    (OUT / "captions.json").write_text(json.dumps(captions, indent=2), encoding="utf-8")
    print(f"wrote {len(captions)} images to {OUT.relative_to(REPO)}")


if __name__ == "__main__":
    main()
