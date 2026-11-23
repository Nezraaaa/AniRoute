# AniRoute — project audit

CSST 106 Final Project · Real-World Perception and Computer Vision System
Audit date: 2026-11-23 · Branch: `feat/cv-final-project`

Everything below was checked on the presentation laptop on the audit date (tests run, servers started,
every API endpoint and page exercised), not taken from memory.

## Summary

The system is complete and working end to end: a fine-tuned YOLO11 detector for **cracks** (severe road damage)
(its pothole class is unreliable, see below), real-time scanning in the web app, driver confirmation, and crop-aware route
planning with three route options. All automated tests pass. What remains is small housekeeping and
presentation preparation, listed under **Not done yet**.

## Verification

| Check | Result |
| --- | --- |
| Backend + ML unit tests (`pytest backend/tests ml/tests`) | 42 / 42 pass |
| Frontend unit tests (`vitest`) | 29 / 29 pass |
| Integration tests against the live API | 2 / 2 pass |
| Type-check (`vue-tsc`) and production build | clean |
| All pages loaded in a real browser | no console errors |
| Live API: health, model info, metrics, detect (image and frame), scan-frame smoothing, routes, geocoding, report images, demo video | all pass |

## Done

### Computer vision

- **Detector:** YOLO11n pretrained on COCO, fine-tuned by us on 1,800 road images (RDD2022, India subset,
  CC BY-SA 4.0). Classes: `pothole`, `severe_road_damage` (cracks). Runs on OpenVINO (ONNX / PyTorch
  fallback), auto-selected.
- **Evaluation on 444 held-out test images** (choices fixed on validation first):
  mAP@0.5 **0.278**, mAP@0.5:0.95 0.122, precision 41%, recall 31%, F1 0.355.
  Per class: pothole AP@0.5 0.197, severe road damage 0.358.
- **Pothole label audit (final checks):** most "pothole" boxes in the public mirror are faded lane paint, so
  the pothole AP measures agreement with faulty labels; the model found 0 of 14 real pothole photos.
  Cracks are genuine (86% of crack alerts match a label). See `ml/reports/pothole_label_audit.md`.
- **Optimisation series (validation):** E0 baseline 0.289 → E1 longer training **0.334** (+16%, deployed);
  confidence threshold tuned 0.25 → 0.145 (F1 0.378 → 0.427); OpenVINO 30% faster than PyTorch.
- **Preprocessing:** EXIF orientation fix, 640 × 640 letterbox. CLAHE implemented and ablated: it lowered
  mAP, so it is off by default (decided on validation, confirmed on test).
- **Speed:** 32 ms per frame end to end, about 31 FPS on the laptop CPU.
- **Water-filled pothole check (teammate's OpenCV rule):** kept in the code but **off by default**. It has no labelled
  test set, and on the demo drive it boxed dry road (48 of 54 detections). `ANIROUTE_ENABLE_WATER_POTHOLE_DETECTOR=true` turns it on.
- **False-alarm control:** hazard must appear in 2 of 3 frames, 20 s cooldown; on the 36 s demo drive,
  alerts drop from 6 to 1 (deployed settings: confidence 0.40).
- **Error analysis:** error gallery (false alarms, misses, wrong class), miss rate by object size and
  lighting, confusion matrix, written interpretation in `docs/EVALUATION.md`.
- **Reproducible pipeline:** `ml/scripts/download_rdd2022.py`, `prepare_dataset.py` (leakage check),
  `ml/train.py` (with `--resume`), `ml/evaluate.py`, `ml/export.py`, `ml/run_cpu_pipeline.sh`,
  `ml/scripts/annotate_samples.py`. Every number lives in `ml/reports/`.

### Web application

- **Plan page:** starts empty; OpenStreetMap place search; live road geometry from OSRM.
  Three options on three different roads: **Recommended** (green), **Fastest** (orange), **Safest** (blue),
  titled "… alternative" when the recommended road itself wins that category. Safest uses a road-safety
  score from the route geometry (bends per km, intersections per km, confirmed hazards). Each option shows
  a real score breakdown (time, distance, crop fragility, road safety). Default map shows the whole
  Philippines.
- **Trip page:** live camera or recorded drive analysed by the detector; boxes drawn on the video;
  hazard alert with annotated evidence frame and GPS; confirm by tap or voice; routes re-scored and a
  new recommendation offered when a confirmed hazard lies within 75 m of a route. Map has a Google-Maps
  style **3D follow** camera on the route (not the device location) and an **Overview** toggle.
- **Evaluation page:** headline metrics, per-class table, confusion matrix, PR and F1 curves,
  optimisation table and chart, CLAHE ablation, speed table, smoothing, error gallery, dataset, limitations.
- **About page:** problem, objectives, beneficiaries, how the detector works, privacy.
- Header badge shows detector status (online / starting / no model / backend offline).

### Deliverables

- 17-slide deck `presentation/AniRoute_CSST106.pptx` (built by `presentation/build_deck.py` from the
  reports and screenshots).
- Documentation in `docs/`: problem and objectives, system overview, dataset, model card, evaluation,
  demo script, defense Q&A, presentation outline. `README.md` with setup and reproduction steps.
- Screenshots in `presentation/screenshots/` (desktop and mobile).
- Also in the repository: the dataset (`ml/data/raw` as downloaded, `ml/data/aniroute` as prepared for
  training), the training runs `ml/runs/E0` and `ml/runs/E1` (weights, logs, curves), the exported
  ONNX/OpenVINO models in `backend/models/`, the COCO base weights `yolo11n.pt`, and the course guide PDF.
  Not in the repository: `.env` files, `.venv`, `node_modules`, caches, logs and local runtime data
  (`backend/data/`).

## Removed or switched off (by decision)

| Item | Status | Why |
| --- | --- | --- |
| Demo / presentation mode with fake data | removed | everything in the app is live |
| Vision Lab page | removed | detection is shown in the trip page, slides and Evaluation page |
| Obstruction detection (COCO-pretrained second model) | off by default (`ANIROUTE_ENABLE_OBSTRUCTION_MODEL=true` re-enables) | project focuses on road damage; no test set to measure it |
| Weather, flood and temperature feeds | not connected, placeholders removed | no data source |
| CLAHE preprocessing | implemented, off by default | ablation showed it lowers accuracy |

## Not done yet

| Item | Owner | Effort |
| --- | --- | --- |
| Defense Q&A Q30: replace the drafted answer and "[Adjust to your own words.]" | team | 2 min |
| Watch the demo video and mark the 2 remaining alerts `true`/`false` in `ml/reports/smoothing.json` | team | 2 min |
| Clear the 16 simulated test hazards in `backend/data/hazard_observations.jsonl` (ignored by route scoring; not in git) | developer | 1 min |
| `npm audit fix`: 6 high-severity advisories, all in build and dev-server tooling (Vite, Stylus), not in app runtime code | developer | 2 min |
| `FINAL_PROJECT_MVP_PROMPT.md` (original planning prompt) still describes the Vision Lab: delete or keep as history | team | — |
| Rehearse at the venue: internet on, location allowed, Windows Update paused, sleep set to Never; plan the demo trip from the venue | team | — |
| Upload the deck to Google Classroom | team | — |

## Known limitations (stated in the docs and slides)

- Accuracy is modest: nano model, 1,800 training images, CPU-only training (40 epochs). Many errors are
  boxes drawn differently from the annotators' boxes (see the error gallery).
- No Philippine test data: no public labelled Philippine road-damage dataset exists; training data is
  from Indian roads.
- Obstructions, standing water, fallen trees and landslides are not detected automatically.
- Route-risk and road-safety weights are transparent heuristics, not measured spoilage or accident rates.
- Long trips (e.g. Baguio → Calamba) take about 10–15 s to plan because extra candidate roads are scored.
- Distance to a hazard is not estimated; hazards are pinned at the vehicle's GPS position when confirmed.

## How to run

```bash
scripts/start.ps1          # Windows: backend on :8000, frontend on :5173
# or
uvicorn backend.main:app --port 8000
cd frontend && npm run dev
```

Tests: `python -m pytest -q backend/tests ml/tests` · `cd frontend && npm run typecheck && npm test && npm run build`
