"""Render the before/after preprocessing figure for the Preprocessing slide.

  python ml/scripts/preprocess_demo.py                       # uses backend/samples + dataset test images
  python ml/scripts/preprocess_demo.py --images a.jpg b.jpg  # pick your own hard cases (night, glare, rain)

Each row: original · CLAHE-enhanced · letterboxed model input, with the luminance
statistics that decided whether CLAHE was applied automatically.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from backend.vision.preprocess import enhance_contrast_clahe, letterbox, luminance_stats, run_pipeline  # noqa: E402

OUT = REPO / "ml" / "reports" / "preprocessing_before_after.png"


def label(image: np.ndarray, text: str) -> np.ndarray:
    canvas = image.copy()
    cv2.rectangle(canvas, (0, 0), (canvas.shape[1], 34), (30, 36, 31), -1)
    cv2.putText(canvas, text, (10, 23), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)
    return canvas


def pick_images(limit: int) -> list[Path]:
    candidates = []
    for folder in (REPO / "ml" / "data" / "aniroute" / "test" / "images", REPO / "backend" / "samples"):
        if folder.is_dir():
            candidates += [p for p in folder.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"}]
    # Darkest images first: they show the effect of CLAHE best.
    scored = []
    for path in candidates[:400]:
        image = cv2.imread(str(path))
        if image is not None:
            scored.append((luminance_stats(image)[0], path))
    return [path for _, path in sorted(scored)[:limit]]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--images", nargs="*", default=None)
    parser.add_argument("--count", type=int, default=4)
    args = parser.parse_args()
    paths = [Path(p) for p in args.images] if args.images else pick_images(args.count)
    if not paths:
        raise SystemExit("No images found. Pass --images or add files to backend/samples/.")
    rows = []
    for path in paths:
        image = cv2.imread(str(path))
        if image is None:
            continue
        mean, std = luminance_stats(image)
        auto = run_pipeline(image, clahe="auto")
        enhanced = enhance_contrast_clahe(image)
        e_mean, e_std = luminance_stats(enhanced)
        boxed, _ = letterbox(enhanced if auto.clahe_applied else image, 640)
        tile_h = 300

        def fit(img):
            return cv2.resize(img, (round(img.shape[1] * tile_h / img.shape[0]), tile_h))

        row = np.hstack([
            label(fit(image), f"Original  L mean {mean:.0f} / contrast {std:.0f}"),
            label(fit(enhanced), f"CLAHE  L mean {e_mean:.0f} / contrast {e_std:.0f}"),
            label(fit(boxed), f"Model input 640x640 · auto CLAHE {'ON' if auto.clahe_applied else 'off'}"),
        ])
        rows.append(row)
    width = max(r.shape[1] for r in rows)
    rows = [np.hstack([r, np.full((r.shape[0], width - r.shape[1], 3), 255, np.uint8)]) for r in rows]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(OUT), np.vstack(rows))
    print(f"wrote {OUT.relative_to(REPO)}")


if __name__ == "__main__":
    main()
