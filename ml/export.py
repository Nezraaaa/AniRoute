"""Export models to faster CPU runtimes (deployment optimisation).

  python ml/export.py                          # both models → ONNX (+ OpenVINO if installed)
  python ml/export.py --formats onnx openvino --int8

The backend automatically loads the fastest export that exists next to the .pt file
(OpenVINO → ONNX → PyTorch). Compare speeds with `python ml/evaluate.py latency`.
"""
from __future__ import annotations

import argparse
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MODELS = REPO / "backend" / "models"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--weights", nargs="+", default=[str(MODELS / "aniroute-hazards-v1.pt"), str(MODELS / "yolo11n.pt")])
    parser.add_argument("--formats", nargs="+", default=["onnx"], choices=["onnx", "openvino"])
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--int8", action="store_true", help="OpenVINO INT8 quantisation (needs --data for calibration)")
    parser.add_argument("--data", default=None, help="data.yaml used to calibrate INT8")
    args = parser.parse_args()

    from ultralytics import YOLO

    for weights in map(Path, args.weights):
        if not weights.exists():
            print(f"skip {weights.name}: not found")
            continue
        model = YOLO(str(weights), task="detect")
        for fmt in args.formats:
            options = {"format": fmt, "imgsz": args.imgsz, "dynamic": False}
            if fmt == "onnx":
                options["simplify"] = True
            if fmt == "openvino" and args.int8:
                options.update({"int8": True, "data": args.data})
            print(f"exporting {weights.name} → {fmt}")
            output = model.export(**options)
            print(f"  saved {output}")


if __name__ == "__main__":
    main()
