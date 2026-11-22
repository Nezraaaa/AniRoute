"""Train Model A (road-surface hazards) by fine-tuning COCO-pretrained YOLO weights.

Each experiment in the optimisation series is one preset. Run them one at a time
(Colab: one cell per experiment) and compare with:

  python ml/evaluate.py compare --runs ml/runs/E0 ml/runs/E1 ml/runs/E2 ml/runs/E3 ml/runs/E4

Examples
  python ml/train.py --experiment E0 --data ml/data/aniroute/data.yaml
  python ml/train.py --experiment E1 --device 0            # GPU on Colab
  python ml/train.py --experiment E0 --device cpu --epochs 30 --imgsz 512 --fraction 0.5   # CPU fallback

How "pretrained" is used: YOLO("yolo11n.pt") loads weights learned on COCO (118k
everyday photos). The backbone and neck keep their general visual features (edges,
textures, shapes); Ultralytics rebuilds the detection head for our 2 classes and
fine-tuning adapts the whole network to road surfaces (transfer learning). E7 trains
the same network from scratch (yolo11n.yaml) to show what pretraining contributes.
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RUNS = REPO / "ml" / "runs"

COMMON = {"imgsz": 640, "batch": 16, "seed": 42, "deterministic": True, "patience": 20, "plots": True}

EXPERIMENTS: dict[str, dict] = {
    "E0": {"title": "Baseline", "model": "yolo11n.pt", "epochs": 50, "patience": 0,
           "change": "COCO-pretrained YOLO11n, default settings, 50 epochs, 640 px"},
    "E1": {"title": "Longer training", "model": "yolo11n.pt", "epochs": 100,
           "change": "100 epochs with early stopping (patience 20)"},
    "E2": {"title": "Bigger model", "model": "yolo11s.pt", "epochs": 100,
           "change": "YOLO11s instead of YOLO11n (≈3× parameters)"},
    "E3": {"title": "Higher resolution", "model": "yolo11n.pt", "epochs": 100, "imgsz": 800,
           "change": "800 px input for small and distant potholes"},
    "E4": {"title": "Augmentation tuning", "model": "yolo11n.pt", "epochs": 100,
           "hsv_v": 0.5, "degrees": 5.0, "mixup": 0.1,
           "change": "Stronger brightness (hsv_v 0.5), ±5° rotation, mixup 0.1 for lighting/rain robustness"},
    "E7": {"title": "From scratch (no pretraining)", "model": "yolo11n.yaml", "epochs": 100, "pretrained": False,
           "change": "Same network, random initial weights: shows the value of transfer learning"},
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--experiment", default="E0", choices=sorted(EXPERIMENTS))
    parser.add_argument("--data", default=str(REPO / "ml" / "data" / "aniroute" / "data.yaml"))
    parser.add_argument("--device", default=None, help="'0' for the first GPU, 'cpu' for CPU (default: auto)")
    parser.add_argument("--epochs", type=int, default=None, help="override the preset (e.g. CPU fallback)")
    parser.add_argument("--imgsz", type=int, default=None)
    parser.add_argument("--batch", type=int, default=None)
    parser.add_argument("--fraction", type=float, default=1.0, help="train on a fraction of the train split")
    parser.add_argument("--base", default=None, help="override the starting model (e.g. yolo11s.pt for E4)")
    parser.add_argument("--project", default=str(RUNS))
    parser.add_argument("--deploy", action="store_true", help="copy best.pt to backend/models/aniroute-hazards-v1.pt")
    args = parser.parse_args()

    from ultralytics import YOLO

    preset = dict(EXPERIMENTS[args.experiment])
    title, change = preset.pop("title"), preset.pop("change")
    model_name = args.base or preset.pop("model")
    preset.pop("model", None)
    options = {**COMMON, **preset}
    for key in ("epochs", "imgsz", "batch"):
        if getattr(args, key) is not None:
            options[key] = getattr(args, key)
    if args.device is not None:
        options["device"] = args.device
    if args.fraction < 1:
        options["fraction"] = args.fraction

    print(f"{args.experiment} · {title}: {change}\n  start from {model_name}  options {options}")
    model = YOLO(model_name)
    model.train(data=args.data, project=args.project, name=args.experiment, exist_ok=True, **options)

    run_dir = Path(args.project) / args.experiment
    meta = {"id": args.experiment, "title": title, "change": change, "model": model_name,
            "epochs": options["epochs"], "imgsz": options["imgsz"], "fraction": args.fraction,
            "device": options.get("device", "auto")}
    (run_dir / "aniroute_experiment.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    best = run_dir / "weights" / "best.pt"
    print(f"\nDone. Best weights: {best}")
    if args.deploy and best.exists():
        target = REPO / "backend" / "models" / "aniroute-hazards-v1.pt"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(best, target)
        print(f"Deployed to {target}")


if __name__ == "__main__":
    main()
