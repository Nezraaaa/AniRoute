#!/usr/bin/env bash
# Full CPU pipeline used for the submitted results (no GPU available):
# train E0 baseline + E1 longer training, pick the best on validation, evaluate once on test,
# export faster runtimes, measure speed, build the demo video and the slide deck.
#   bash ml/run_cpu_pipeline.sh            (from the repository root; takes ~7 hours on a laptop CPU)
set -euo pipefail
cd "$(dirname "$0")/.."
PY=.venv/Scripts/python.exe; [ -x "$PY" ] || PY=.venv/bin/python
export ANIROUTE_VISION_WARMUP=false
log() { echo "[$(date '+%H:%M:%S')] $*"; }

# A finished run has aniroute_experiment.json; an interrupted one (reboot, sleep) resumes from last.pt.
train() {
  if [ -f "ml/runs/$1/aniroute_experiment.json" ]; then log "$1 already trained, skipping"; return; fi
  log "$1 $2"; "$PY" ml/train.py --experiment "$1" --device cpu --epochs "$3" --resume
}
train E0 "baseline (20 epochs)" 20
train E1 "longer training (40 epochs, early stopping)" 40
log "compare on validation";     "$PY" ml/evaluate.py compare --runs ml/runs/E0 ml/runs/E1
SELECTED=$("$PY" -c "import json;print(json.load(open('ml/reports/optimization.json'))['selected'])")
cp "ml/runs/$SELECTED/weights/best.pt" backend/models/aniroute-hazards-v1.pt
log "deployed $SELECTED; evaluating once on test"
"$PY" ml/evaluate.py test --run-dir "ml/runs/$SELECTED"
"$PY" ml/scripts/preprocess_demo.py
log "export + speed";            "$PY" ml/export.py --weights backend/models/aniroute-hazards-v1.pt --formats onnx openvino
"$PY" ml/evaluate.py latency --images backend/samples
log "demo video from held-out test images"
"$PY" ml/scripts/make_demo_video.py --images ml/data/aniroute/test/images --count 24 --caption "Held-out test road images (RDD2022 India)"
"$PY" ml/evaluate.py smoothing --video backend/samples/demo_drive.webm
"$PY" presentation/build_deck.py
log "PIPELINE DONE"
