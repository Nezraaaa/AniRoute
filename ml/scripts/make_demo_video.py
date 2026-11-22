"""Create the browser-playable recorded drive used in the trip page and the Vision Lab.

  # Best: your own phone/dashcam recording of a local road (trimmed to ~30 s)
  python ml/scripts/make_demo_video.py --video my_drive.mp4 --start 5 --duration 30

  # Without a recording: a slideshow of held-out TEST images (never used in training)
  python ml/scripts/make_demo_video.py --images ml/data/aniroute/test/images --count 20

The result is a VP8 WebM in backend/samples/ (plays in every browser) and an entry in
backend/samples/samples.json marking it as the demo drive, with its source.
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

import cv2
import numpy as np

REPO = Path(__file__).resolve().parents[2]
SAMPLES = REPO / "backend" / "samples"
SIZE = (1280, 720)


def fit(frame: np.ndarray) -> np.ndarray:
    """Letterbox any frame into 1280x720 without distortion."""
    h, w = frame.shape[:2]
    scale = min(SIZE[0] / w, SIZE[1] / h)
    resized = cv2.resize(frame, (round(w * scale), round(h * scale)), interpolation=cv2.INTER_AREA)
    canvas = np.zeros((SIZE[1], SIZE[0], 3), np.uint8)
    y, x = (SIZE[1] - resized.shape[0]) // 2, (SIZE[0] - resized.shape[1]) // 2
    canvas[y:y + resized.shape[0], x:x + resized.shape[1]] = resized
    return canvas


def writer(path: Path, fps: float) -> cv2.VideoWriter:
    out = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"VP80"), fps, SIZE)
    if not out.isOpened():
        raise SystemExit("OpenCV could not open a VP8 WebM writer.")
    return out


def from_video(args) -> tuple[int, str]:
    capture = cv2.VideoCapture(str(args.video))
    if not capture.isOpened():
        raise SystemExit(f"Cannot open {args.video}")
    source_fps = capture.get(cv2.CAP_PROP_FPS) or 30
    step = max(1, round(source_fps / args.fps))
    capture.set(cv2.CAP_PROP_POS_MSEC, args.start * 1000)
    out = writer(args.output, source_fps / step)
    frames, index = 0, 0
    limit = args.duration * source_fps if args.duration else float("inf")
    while index < limit:
        ok, frame = capture.read()
        if not ok:
            break
        if index % step == 0:
            out.write(fit(frame))
            frames += 1
        index += 1
    out.release()
    return frames, f"Recorded drive: {Path(args.video).name}"


def from_images(args) -> tuple[int, str]:
    paths = sorted(p for p in Path(args.images).iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"})
    random.Random(42).shuffle(paths)
    paths = paths[:args.count]
    if not paths:
        raise SystemExit(f"No images in {args.images}")
    out = writer(args.output, args.fps)
    frames = 0
    for path in paths:
        image = cv2.imread(str(path))
        if image is None:
            continue
        frame = fit(image)
        for _ in range(round(args.seconds_per_image * args.fps)):
            out.write(frame)
            frames += 1
    out.release()
    return frames, f"Slideshow of {len(paths)} held-out test images"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--video", type=Path)
    source.add_argument("--images", type=Path)
    parser.add_argument("--output", type=Path, default=SAMPLES / "demo_drive.webm")
    parser.add_argument("--fps", type=float, default=10)
    parser.add_argument("--start", type=float, default=0, help="seconds to skip at the start of --video")
    parser.add_argument("--duration", type=float, default=30, help="seconds to keep from --video (0 = all)")
    parser.add_argument("--count", type=int, default=20, help="images in the slideshow")
    parser.add_argument("--seconds-per-image", type=float, default=1.5)
    parser.add_argument("--caption", default=None)
    args = parser.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    frames, default_caption = from_video(args) if args.video else from_images(args)
    captions_path = SAMPLES / "samples.json"
    captions = json.loads(captions_path.read_text(encoding="utf-8")) if captions_path.exists() else {}
    for meta in captions.values():
        if isinstance(meta, dict):
            meta["demo"] = False
    captions[args.output.name] = {
        "caption": args.caption or default_caption,
        "source": str(args.video.name if args.video else args.images),
        "demo": True,
    }
    captions_path.write_text(json.dumps(captions, indent=2), encoding="utf-8")
    size_mb = args.output.stat().st_size / 1e6
    print(f"wrote {args.output} ({frames} frames, {size_mb:.1f} MB) and marked it as the demo drive")
    if size_mb > 40:
        print("warning: large file; consider --duration 20 or a lower --fps")


if __name__ == "__main__":
    main()
