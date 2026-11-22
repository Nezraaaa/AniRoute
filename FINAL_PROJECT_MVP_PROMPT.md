# AniRoute: CSST 106 Final Project MVP Build Prompt

> **How to use this file:** paste the whole file into Claude Code (or tell it: *"Read `FINAL_PROJECT_MVP_PROMPT.md` and execute it phase by phase"*), opened in the root of this repository. Steps marked **👤 HUMAN TASK** need you, for example training on Google Colab, taking photos, or recording a video. The agent should stop and tell you when it reaches one.

---

## 0. Role and mission

You are a senior computer-vision and full-stack engineer finishing **AniRoute** as the CSST 106 Final Project, *"Real-World Perception and Computer Vision System"*. The grading guide is `CSST 106 – Final Project - Real-World Perception and Computer Vision System.pdf` in the repo root. Read it first.

The goal is a **working, demonstrable, honestly evaluated** computer-vision system inside the existing AniRoute web app. It must satisfy every one of the 10 minimum requirements and give clear evidence for each rubric line, so a panel can grade it at full marks.

**One-sentence pitch to keep in mind:**
> AniRoute uses a dashcam or phone camera on a farm-produce vehicle to **detect road hazards in real time** with two models working together. One is a **YOLO model we fine-tuned from pretrained weights** to find potholes and severe road damage. The other is a **pretrained COCO YOLO model used as-is** to find obstructions such as livestock, people and stalled vehicles in the driving lane. AniRoute then pins each confirmed hazard to the map and **re-ranks delivery routes by crop-spoilage risk**, so perishable harvests reach market with less damage and delay.

### Model strategy (decided, do not re-litigate)
**"Train with pretrained integration, then optimize":**

| Model | Origin | Classes | Training |
| --- | --- | --- | --- |
| **A: Road-surface model** | YOLO11n **initialized from COCO-pretrained weights**, fine-tuned by us (transfer learning) | `0 pothole`, `1 severe_road_damage` | Yes, on public labelled datasets (Roboflow Universe pothole set + an RDD2022 subset) |
| **B: Obstruction model** | **COCO-pretrained YOLO11n used as-is** | COCO `person, bicycle, car, motorcycle, bus, truck, dog, horse, sheep, cow` → mapped to `road_obstruction` | None. Only rules: the box must sit in the driving-lane region of interest (ROI) and be large or close enough |
| `standing_water` | Not detected by a model in the MVP | — | Manual driver report only; listed under Limitations |

- **Integration:** both models run on the **same preprocessed frame**. Their outputs are merged into one detection list in the app's `HazardType` vocabulary, then the same smoothing and confirm flow applies.
- **Optimization:** a documented baseline → optimized experiment series (§5.4) with a before/after table, plus inference optimization for CPU (ONNX/OpenVINO).
- **Optional baseline comparison:** a community pothole model from Hugging Face, evaluated on *our* test set, as a "downloaded model vs. our fine-tuned model" slide. Caveat: its training data may overlap our test set, so say so on the slide.

### Non-negotiable rules
1. **No fabricated numbers.** Every metric shown in the app, README, docs or slides must come from a file produced by `ml/evaluate.py` on a held-out test set. If a number does not exist yet, show "pending evaluation", never a placeholder value.
2. **No fake detections in the graded path.** The current Demo mode shows scripted findings (`presentationVisionFindings` in `frontend/src/pages/ActiveTripPage.vue`). Replace them with real model inference on a bundled sample road video. A scripted fallback may exist only when the backend is offline, and it must be visibly labelled "Offline sample, not model output".
3. **Keep what works.** Route planning, the map, crop risk scoring, geocoding and the existing tests must keep working. Keep existing field names (`HazardType` = `pothole | severe_road_damage | standing_water | road_obstruction`) or update adapters and tests together.
4. **Work on a branch** (`feat/cv-final-project`) and commit after each phase with a clear message. Never commit `.env`, `node_modules/`, `dist/`, `backend/data/evidence/` or `backend/data/hazard_observations.jsonl`. Add them to `.gitignore`; right now they are untracked and unignored.
5. After every phase, run the checks in §9 and fix failures before moving on.

---

## 1. Current state (verified, so don't re-discover it)

| Area | State |
| --- | --- |
| Frontend | Vue 3 + Vite + TypeScript + Tailwind v4 + shadcn-vue + MapLibre. Pages: `PlanPage.vue` (`/`) and `ActiveTripPage.vue` (`/trip/active`). Header toggle switches between **Demo** (`mode: 'presentation'`) and **Live** (`mode: 'live'`). |
| Backend | One file, `backend/main.py` (FastAPI). Live routing via OSRM (`alternatives=true`) and geocoding via Nominatim work. |
| Computer vision | **None.** `/api/hazards/scan-frame` always returns `detection_available: False`, `/api/health` reports `live_hazard_detection: False`, and `requirements.txt` has no CV libraries. |
| Camera | `useCamera.ts` opens the rear camera. `CameraPreview.vue` exposes `captureFrame(maxWidth=320, quality=0.38)`, which is too small for reliable detection. In Live mode, **`ActiveTripPage.vue` never calls `scanCameraFrame()`**, so no frame loop exists. |
| Contract bugs | The backend returns `data_source: "demo"` from `/scanning/start`, `/scan-frame` and `/hazards/confirm`. `frontend/src/services/hazards.ts` throws unless `data_source === 'api'`, so **Live hazard confirmation is broken today**. `ScanFrame` caps frames at 125 KB and 180 000 data-URL characters. |
| Re-ranking | `/api/routes/recalculate` ignores the confirmed hazard ("Hazard-specific route re-ranking is not connected yet"). |
| Machine | Windows 11, Python 3.12, Node 24, **no NVIDIA GPU, no torch/opencv/ultralytics installed**. Train on Google Colab (free T4 GPU) and run inference on CPU locally. |
| Remote | `origin` = GitHub repo `Nezraaaa/AniRoute`. |

---

## 2. Rubric → evidence map (build to this table)

| Rubric line (weight) | What must exist | Evidence artifact |
| --- | --- | --- |
| Real-World Relevance & Problem (25%) | Problem, objectives, beneficiaries and justification, backed by cited Philippine sources on postharvest losses and farm-to-market road conditions. Never invent statistics; cite the real source and URL. | `docs/PROBLEM_AND_OBJECTIVES.md`, in-app **About** page |
| Computer Vision System (30%) | Real-time YOLO object detection, an explicit preprocessing pipeline, image, video and webcam inputs, annotated output, temporal smoothing, and a link from detections to route risk | `ml/`, `backend/vision/`, **Vision Lab** page, Live trip scanning |
| Evaluation, Testing & Demo (20%) | Precision, recall, F1, mAP@0.5, mAP@0.5:0.95 per class, confusion matrix, PR and F1 curves, preprocessing ablation (before vs after), CPU latency/FPS, error analysis gallery, robustness subsets | `ml/reports/*`, **Evaluation** page, `docs/EVALUATION.md` |
| Presentation & Delivery (10%) | A visual-heavy deck with 14–16 slides, diagrams, before/after images and charts | `presentation/AniRoute_CSST106.pptx` + `docs/PRESENTATION_OUTLINE.md` |
| Defense & Understanding (10%) | A plain-language explanation of YOLO, preprocessing, metrics and limitations, plus likely panel Q&A | `docs/MODEL_CARD.md`, `docs/DEFENSE_QA.md` |
| Accuracy & Completeness (5%) | All 10 minimum requirements met; reproducible results; tests pass | §8 checklist, README "Reproduce results" section |

### The 10 minimum requirements → where each is satisfied
1. **Accepts image, video, webcam or dataset:** the Vision Lab has *Image* (single and batch), *Video* and *Webcam* tabs; `ml/evaluate.py` runs on the dataset.
2. **Performs a CV task:** object detection with two integrated YOLO models (fine-tuned road-surface model + pretrained obstruction model), with real-time video detection.
3. **Appropriate preprocessing:** EXIF orientation, letterbox resize to 640, CLAHE contrast enhancement, optional denoise and gamma correction, normalization. Training-time augmentation is documented separately.
4. **Meaningful result:** hazard boxes with class and confidence. A confirmed hazard is geotagged, raises route road-risk, and **changes the recommended route**.
5. **Display and visualize:** bounding-box overlays on images, video and live camera; hazard pins on the map; before/after preprocessing views.
6. **Evaluate performance:** the Evaluation page and `ml/reports/metrics.json`.
7. **Demonstrate:** `docs/DEMO_SCRIPT.md` (5–10 minutes), a one-command start, and a bundled sample video so the demo works offline from the internet.
8. **Explain the algorithm:** `docs/MODEL_CARD.md`, the About page, and the CV Method slides.
9. **Limitations:** a section on the Evaluation page, `docs/MODEL_CARD.md`, and a slide.
10. **Real-world application:** the About page, `docs/PROBLEM_AND_OBJECTIVES.md`, and a slide.

---

## 3. Target architecture

```
ml/                              # training + evaluation (not imported by the app)
  data/                          # gitignored raw/processed datasets (README explains how to fetch)
  configs/aniroute_hazards.yaml  # Model A data config: 0 pothole, 1 severe_road_damage
  scripts/
    prepare_dataset.py           # download/merge/remap classes, dedupe, stratified split, stats
    preprocess_demo.py           # renders before/after preprocessing figures for slides
  notebooks/train_colab.ipynb    # 👤 run on Colab GPU
  train.py                       # same as notebook, runnable locally (CPU fallback, small epochs)
  evaluate.py                    # metrics, confusion matrix, curves, ablation, latency, error gallery
  reports/                       # committed outputs: metrics.json, *.png, error_gallery/, ablation.json
backend/
  main.py                        # keep; mount new routers; fix data_source contract
  vision/
    __init__.py
    config.py                    # thresholds, model path, imgsz, device from env
    preprocess.py                # pure functions, each returns ndarray; pipeline returns stages
    detector.py                  # lazy singleton, thread lock, warmup, predict() -> Detections
    smoothing.py                 # per-route temporal voting + cooldown + dedupe
    annotate.py                  # draw boxes/labels → JPEG base64
    router.py                    # FastAPI APIRouter with /api/vision/* and /api/model/*
  hazard_risk.py                 # point-to-polyline distance + road-risk adjustment
  models/aniroute-hazards-v1.pt  # Model A: our fine-tuned weights (YOLO nano ≈ 6 MB, OK to commit) + .onnx/openvino
  models/yolo11n.pt              # Model B: COCO-pretrained, used as-is (auto-downloaded by setup script)
  vision/ensemble.py             # runs A + B on one frame, maps classes, applies ROI rule, merges
  samples/                       # 6–10 test images + 1 short road video (≤ 20 MB) for demo
  tests/test_vision.py, test_hazard_risk.py
frontend/src/
  pages/VisionLabPage.vue        # /vision : image | video | webcam tabs
  pages/EvaluationPage.vue       # /evaluation
  pages/AboutPage.vue            # /about : problem, objectives, beneficiaries, architecture, limits
  components/vision/DetectionOverlay.vue   # canvas boxes over <img>/<video>
  components/vision/PreprocessStages.vue   # original → CLAHE → letterboxed side by side
  components/vision/MetricsCards.vue, ConfusionMatrix.vue, PerClassTable.vue, ErrorGallery.vue
  composables/useFrameScanner.ts # shared capture→detect loop for webcam + video
  services/vision.ts             # typed API client
docs/  PROBLEM_AND_OBJECTIVES.md  SYSTEM_OVERVIEW.md  DATASET.md  MODEL_CARD.md
       EVALUATION.md  DEMO_SCRIPT.md  PRESENTATION_OUTLINE.md  DEFENSE_QA.md
presentation/AniRoute_CSST106.pptx + presentation/build_deck.py
scripts/start.ps1, scripts/start.sh     # one command: backend + frontend
```

Draw these two diagrams as **Mermaid** in `docs/SYSTEM_OVERVIEW.md` and export them as PNG for the slides:
- **System architecture:** Camera/Video/Image → Browser (Vue) → FastAPI → Preprocess → YOLO → Smoothing → Confirm dialog → Observation store → Route risk re-rank → Map.
- **Detection flowchart:** frame captured → preprocess → infer → filter by confidence/NMS → vote across N frames → cooldown/dedupe → show alert → driver confirms or dismisses → store + re-rank.

---

## 4. Phase 1: Dataset (👤 mostly human, about 1 hour in a web browser, no labelling)

The team has no dataset experience, so use **already-labelled public data** and write `docs/DATASET.md` as a beginner-friendly guide:
- what a YOLO dataset is: `images/` + one `labels/*.txt` per image, each line `class x_center y_center width height`, normalized to 0–1, plus `data.yaml`
- what train, val and test splits are, and why the test split is never used in training

1. **Model A classes, fixed order** (index = position): `0 pothole, 1 severe_road_damage`. Model B uses COCO classes mapped to `road_obstruction` in code (see Model strategy).
2. **👤 Build the dataset in Roboflow** (free account, GUI only). Write these steps into `docs/DATASET.md` with screenshots placeholders:
   1. Roboflow Universe → fork **one pothole dataset** in YOLOv8 format into your workspace, e.g. `universe.roboflow.com/vg2024/potholedetectionyolov8-tz4cy` (CC BY 4.0, about 1.4k images) or `universe.roboflow.com/yoloteam/potholedetectionyolov8-11c1w` (665 images).
   2. Fork **one RDD2022 copy** with classes `D00 D10 D20 D40`, e.g. `universe.roboflow.com/rdd2022/road-damage-iztzn`. Official source: `github.com/sekilab/RoadDamageDetector`, paper arXiv:2209.08538.
   3. Merge both into one project and **remap classes**: `D40 → pothole`; `D00, D10, D20 → severe_road_damage` (cracking); the pothole dataset's class → `pothole`.
   4. Limit RDD2022 to a **subset of about 2,000–3,000 images** so free Colab training stays under about 40 minutes per run. Prefer road scenes similar to the Philippines; the India and Japan subsets are good candidates.
   5. Generate a version: **70/20/10 split**, preprocessing = auto-orient only (keep the resize in our own pipeline), **no Roboflow augmentation** (Ultralytics augments during training). Export as **YOLOv8** and download the zip into `ml/data/` (gitignored).
   6. Record the exact URLs, licenses, image counts and the remap rule in `docs/DATASET.md`.
3. **👤 Optional but strong for the 25% relevance line:** 30–50 local Philippine road photos labelled in Roboflow (about 1 hour), used **only** as an extra test set `test_local`. Never train on it.
4. **Obstruction test set (Model B):** Model B isn't trained, but it must still be evaluated. Fork a small labelled "animals/vehicles on road" set from Roboflow Universe (or label about 50 images with `road_obstruction` boxes) → `ml/data/obstruction_test/`.
5. `ml/scripts/prepare_dataset.py` (runs on the downloaded zip, no manual work):
   - Verifies `data.yaml` and the class order, drops corrupt or empty images, and removes near-duplicates across splits (perceptual hash) to prevent train/test leakage.
   - Writes `ml/reports/dataset_stats.json`, `dataset_class_distribution.png` (instances per class per split) and a `dataset_samples.png` grid (4 examples per class) for the Dataset slide.
   - Warns if any class has **< 300 training instances**.

**Acceptance:** `ml/data/aniroute/data.yaml` validates, stats and sample PNGs exist, and `DATASET.md` lists every source with its license and explains the dataset in plain language.

---

## 5. Phase 2: Preprocessing, training and evaluation (`ml/`)

### 5.1 Preprocessing (shared by the app and the evaluation)
Put the implementation in `backend/vision/preprocess.py` and import it from `ml/` so training-time evaluation and the app use **identical** code:
- `fix_orientation` (EXIF) → `enhance_contrast_clahe` (LAB L-channel, `clipLimit=2.0`, `tileGridSize=8×8`, applied only when mean luminance < threshold or contrast is low; log whether it ran) → optional `denoise` (bilateral) → `letterbox(640)` → normalize (handled by Ultralytics).
- `run_pipeline(img) -> {final, stages: [{name, image, applied: bool, ms}]}`. The stages feed the before/after UI.
- `ml/scripts/preprocess_demo.py` renders `ml/reports/preprocessing_before_after.png` (original | CLAHE | letterboxed) for 4 hard cases: night, shadow, glare and rain.

### 5.2 Training Model A: transfer learning from pretrained weights (👤 run on Colab)
- `ml/notebooks/train_colab.ipynb`: a beginner-proof notebook. Every cell has a one-line markdown explanation, and the cells run top to bottom:
  1. Check the GPU (`Runtime → Change runtime type → T4 GPU`).
  2. `pip install` pinned versions.
  3. Upload or unzip the Roboflow export (or pull it with the Roboflow API key).
  4. Run the experiments in §5.4.
  5. Zip `runs/` + `best.pt` for download.

  `ml/train.py` is the same logic as a CLI.
- **How "pretrained" is used:** `YOLO("yolo11n.pt")` loads COCO-pretrained weights. The backbone and neck keep what they learned (edges, textures, shapes). Ultralytics rebuilds the detection head for our 2 classes, and fine-tuning adapts the whole network to road surfaces. Explain this in `docs/MODEL_CARD.md` with a simple diagram (pretrained layers → new head), and contrast it with training from scratch (`yolo11n.yaml`). The optional ablation run E7 in §5.4 proves the benefit.
- Common settings: `imgsz=640`, `patience=20`, `batch=16`, `seed=42`, `deterministic=True`. Use the default augmentation (mosaic, HSV, flip, scale) and document it as *training augmentation*, which is distinct from inference preprocessing.
- Pin versions in `ml/requirements.txt` (`ultralytics`, `opencv-python-headless`, `numpy`, `pandas`, `matplotlib`, `scikit-learn`, `imagehash`, `onnx`, `openvino`).
- Export the **winning** run's `best.pt` → `backend/models/aniroute-hazards-v1.pt`. Save its `results.png` → `ml/reports/training_curves.png`.
- **Fallback if Colab is unavailable:** `python ml/train.py --epochs 30 --imgsz 512 --device cpu --fraction 0.5`. Document the reduced settings honestly.

### 5.3a Model B: pretrained obstruction model, used as-is (no training)
- `YOLO("yolo11n.pt")` (COCO). Keep only `person, bicycle, car, motorcycle, bus, truck, dog, horse, sheep, cow`.
- **ROI rule** (`backend/vision/ensemble.py`): keep a box only if its bottom-center lies inside a trapezoid "driving corridor" (bottom 60% of the frame, central 50% at the bottom narrowing toward the horizon), **and** its height is at least 12% of the frame height (close enough to matter), **and** its confidence is at or above Model B's threshold. Make every parameter configurable.
- Map the kept boxes → `road_obstruction` and keep the COCO label as `source_label` (for example "cow") so the UI can say "Road obstruction (cow)".
- Known limitation to document: COCO has no carabao, goat, fallen-tree or landslide class. Carabaos may be detected as `cow`; test this on a few images and report the result honestly.

### 5.3 Evaluation: `ml/evaluate.py` (runs on CPU and is fully reproducible)
Run on **test** and **test_local**, and write everything to `ml/reports/`:
- `metrics.json`: overall and per-class **precision, recall, F1, mAP@0.5, mAP@0.5:0.95**, chosen confidence threshold, IoU threshold, image and instance counts, model version, git commit and timestamp.
- `confusion_matrix.png` and `confusion_matrix_normalized.png` (including the background row and column).
- `pr_curve.png`, `f1_confidence_curve.png`. Choose the operating confidence threshold at the max-F1 point and save it to `metrics.json`; the backend reads it.
- **Detection counts:** TP, FP and FN per class (the "correct/incorrect detections" requirement).
- **Ablation, before vs after preprocessing:** the same model evaluated with and without CLAHE, overall and on the low-light subset. Save to `ablation.json` and `ablation_bar.png`. Report the result truthfully, even if CLAHE does not help.
- **Robustness subsets:** day/night/rain/blur where tagged (use filename or tag metadata). Save to `robustness.json`.
- **Speed:** mean and p95 latency and FPS on this laptop's CPU at 640 and 480, for both PT and ONNX. Save to `latency.json`.
- **Error gallery:** `error_gallery/{false_positives,false_negatives,misclassified}/` with about 6 annotated examples each, plus `error_analysis.md` summarizing the causes (small or distant potholes, wet road vs puddle, shadows, motion blur, and so on).

- **Model B evaluation:** on `obstruction_test`, report precision, recall and F1 for `road_obstruction` **with and without the ROI rule**. This shows how the rule removes false alarms from parked or oncoming traffic.
- **Integrated system evaluation:** run A+B together on the combined test images and report per-hazard metrics and end-to-end latency (both models + preprocessing) → `metrics.json["system"]`.

**Acceptance:** `python ml/evaluate.py --weights backend/models/aniroute-hazards-v1.pt` regenerates every report file from scratch, and `docs/EVALUATION.md` embeds the PNGs and explains each metric in one plain sentence.

### 5.4 Optimization: baseline → optimized (the core "we optimized it" evidence)
Run these as separate Colab runs. Name them `E0`…`E7` under `runs/` and evaluate each on the **same val split** with `ml/evaluate.py --compare runs/*`. The script writes `ml/reports/optimization_table.md`, `optimization.json` and `optimization_chart.png` (mAP@0.5 and CPU FPS per experiment). Choose the final model on **val**, then report its **test** numbers once. Never pick the model on test.

| ID | Experiment | Change vs previous best | What it demonstrates |
| --- | --- | --- | --- |
| E0 | **Baseline** | YOLO11n, COCO-pretrained, defaults, `epochs=50`, `imgsz=640` | Starting point |
| E1 | Longer training | `epochs=100`, `patience=20` (early stopping) | Effect of training time; check the curves for over- or under-fitting |
| E2 | Bigger model | YOLO11s instead of n | Accuracy vs speed trade-off (CPU FPS matters for real time) |
| E3 | Higher resolution | `imgsz=800` (keep only if mAP gain > 2 points and FPS is acceptable) | Small or distant potholes |
| E4 | Augmentation tuning | e.g. `hsv_v=0.5` (lighting), `degrees=5`, `mixup=0.1` | Robustness to Philippine lighting and rain |
| E5 | Confidence threshold | Choose the max-F1 threshold from the F1 curve instead of the default 0.25 | Free precision/recall gain, no retraining |
| E6 | Preprocessing | CLAHE on vs off at inference (§5.1) | The guide's "before vs after" comparison |
| E7 *(optional)* | Pretrained vs from scratch | `yolo11n.yaml`, no pretrained weights, same epochs | Proves why transfer learning was used |

**Inference optimization (deployment speed, laptop CPU):** export the final model and Model B to **ONNX** and **OpenVINO** (`model.export(format="openvino")`; FP32, and INT8 if accuracy drops < 1 point). Measure mean and p95 latency and FPS for PyTorch vs ONNX vs OpenVINO → `latency.json` + `speed_chart.png`. The backend loads the fastest format that loads successfully (env `ANIROUTE_MODEL_FORMAT`, falling back to `.pt`).

**System-level optimization:** evaluate the 2-of-3 frame voting (§6.3) on the bundled sample video. Report false alarms per minute **with vs without** smoothing → `smoothing.json`.

Do **not** use `model.tune()` (genetic hyperparameter search). It needs hundreds of runs, which is beyond free Colab; say so in the limitations as "future work".

---

## 6. Phase 3: Backend computer-vision service

1. **Dependencies.** Add `ultralytics`, `opencv-python-headless`, `numpy`, `python-multipart` and `pillow` to `backend/requirements.txt` with pinned versions. Use CPU torch; the README gives the CPU wheel install command.
2. **`backend/vision/detector.py` + `ensemble.py`.** Load **Model A** (env `ANIROUTE_MODEL_PATH`) and **Model B** (env `ANIROUTE_OBSTRUCTION_MODEL_PATH`, default `yolo11n.pt`) once each. Preprocess the frame **once** and run both models on it. Map A's classes and B's COCO classes (with the ROI rule) into `HazardType`, and merge. Each detection carries `model: "A" | "B"` and `source_label`. If only one model loads, serve that model's classes and report the other as unavailable in `/api/model/info`. Lazy-load, warm up on startup in a background thread, and guard `predict` with a lock. It returns `[{class_id, hazard_type, label, confidence, box_xyxy (original-image pixels), box_norm}]`, `inference_ms`, `preprocess_ms` and `model_version`. Take the confidence threshold from `ml/reports/metrics.json` (env override `ANIROUTE_CONF_THRESHOLD`), with IoU=0.5 for NMS. If the weights are missing, the service still starts, `/api/health` says `live_hazard_detection: false`, and vision endpoints return **503** with a clear message.
3. **`backend/vision/smoothing.py`.** A detection is *confirmed* for the driver only when the same class appears in **≥ 2 of the last 3 frames** for that route. Add a per-class **cooldown** (default 20 s) and **dedupe** (same class within 50 m of an existing pending or confirmed hazard). Make all of these configurable via env and unit-tested.
4. **Endpoints** (new `APIRouter`, mounted in `main.py`):

   | Method & path | Purpose |
   | --- | --- |
   | `GET /api/model/info` | classes, model version, thresholds, imgsz, loaded flag, device |
   | `GET /api/model/metrics` | contents of `metrics.json`, `ablation.json`, `latency.json`, `robustness.json`, `dataset_stats.json` + URLs of report images |
   | `GET /reports/*` | `StaticFiles` mount of `ml/reports` (read-only) |
   | `POST /api/vision/detect` | multipart `file` (JPEG/PNG ≤ 8 MB) + optional `conf`, `apply_clahe`, `return_stages`. Returns detections, `annotated_image` (data URL), optional preprocessing `stages` (data URLs), and timings |
   | `POST /api/vision/detect-frame` | JSON data-URL frame (for webcam/video sampling, no smoothing); returns detections + timings (frontend draws boxes itself) |
   | `POST /api/hazards/scan-frame` | **Real detection** + smoothing for an active trip; returns raw `detections` (for the overlay) **and** `detection` (a confirmed hazard or `null`) in the shape `hazards.ts` already expects, with `data_source: "api"` |
   | `GET /api/samples` | list bundled sample images/video for the demo |

5. **Fix the contract bugs.**
   - `ScanFrame` size limit: raise to about 600 KB decoded so 640 px frames at quality 0.7 fit.
   - `/scanning/start` returns `mode: "live"` and `detection_available: <model loaded>`.
   - `/hazards/confirm` returns `data_source: "api"`, stores the model confidence and model version, and marks `simulated` correctly.
   - `/api/health` returns `live_hazard_detection: <model loaded>` and `model_version`.
6. **Make the confirmed hazard change the route** (`backend/hazard_risk.py`):
   - Keep confirmed observations, read from `hazard_observations.jsonl` (keep JSONL; no database needed for the MVP).
   - For each candidate route, find observations within **75 m** of the route polyline using a haversine point-to-segment distance.
   - Raise that route's `riskFactors.road` by severity weights (`severe_road_damage 25, road_obstruction 30, standing_water 20, pothole 12`, capped at 100) and scale by the existing `_crop_sensitivity`. Recompute `cropRiskScore` and label, attach the hazards as `knownHazards` pins, and **re-rank**.
   - `/api/routes/recalculate` must now say what changed, for example "Route A now crosses 1 confirmed standing-water hazard; Route B recommended."
   - Apply the same logic to Demo-mode recalculation so the presentation flow is consistent.
7. **Tests** (`pytest`, **no real weights needed**; monkeypatch a fake detector):
   - Preprocessing shapes and dtypes, and CLAHE not applied to bright images.
   - Ensemble: COCO→`road_obstruction` mapping, the ROI rule keeping in-lane boxes and dropping roadside or small ones, and merging A+B outputs.
   - Letterbox box un-mapping back to original coordinates.
   - Smoothing: 2-of-3 voting, cooldown and dedupe.
   - `/api/vision/detect` with a generated PNG, and the 503 when no model is loaded.
   - Size and format validation.
   - Hazard-to-route distance (known geometry) and re-ranking that changes the recommendation.
   - Update the existing `test_api.py` expectations for the new `health()` fields.

**Acceptance:** `python -m pytest -q backend/tests` passes, and `curl -F file=@backend/samples/pothole_01.jpg localhost:8000/api/vision/detect` returns boxes and an annotated image.

---

## 7. Phase 4: Frontend

Follow the existing design language (`style.css`, shadcn-vue components, Lucide icons). The layout must work at phone width, since the app is used in a vehicle. Add header navigation: **Plan · Vision Lab · Evaluation · About**.

1. **`services/vision.ts` + types** in `types/aniRoute.ts`: `Detection`, `DetectResult`, `PreprocessStage`, `ModelInfo` and `ModelMetrics`, with snake_case to camelCase adapters like the existing services.
2. **`DetectionOverlay.vue`**: a canvas positioned over an `<img>` or `<video>`. Draws boxes in a class colour, plus label and confidence, and rescales with `ResizeObserver`. Class colours are consistent everywhere (overlay, map pins, charts).
3. **`useFrameScanner.ts`**: given a video element, captures a frame at **640 px wide, JPEG quality 0.7** every `intervalMs` (default 600). Skips a tick if a request is still in flight (no backpressure pile-up). Exposes `detections`, `fps`, `latencyMs`, `start`, `stop`, and pauses when the tab is hidden. It is used by both the webcam and the video tab.
4. **Vision Lab page (`/vision`)**, which is the main CV demo surface:
   - **Image tab:** drag-and-drop or pick one or more images, or click a bundled sample. Shows **Original | Preprocessed stages | Detections** side by side, a detections table (class, confidence, box), latency, a confidence-threshold slider and a CLAHE on/off toggle (re-runs inference so the before/after effect is live).
   - **Video tab:** upload a video or pick the bundled sample road video. Plays with a live overlay through `useFrameScanner`, plus a running per-class count and a timeline strip of detections.
   - **Webcam tab:** live camera with overlay, FPS and latency badge.
   - Show a clear empty state when the backend or model is unavailable (from `/api/model/info`).
5. **Active trip, Live mode:** when the camera is on, run `useFrameScanner` against `/api/hazards/scan-frame` with GPS coordinates. Draw raw detections on `CameraPreview` through the overlay. When the response contains a confirmed `detection`, open the existing `HazardConfirmation` dialog with the **annotated evidence frame**. On confirm, call the existing upload and recalculation path, which now re-ranks for real, and show the new hazard pin on `RouteMap`.
6. **Active trip, Demo mode:** replace the scripted `presentationVisionFindings` timer. Play the **bundled sample road video** inside `CameraPreview` and run the same real scanner on it, so the presentation demo shows genuine model output on a controlled clip. Keep the scripted path only as the labelled offline fallback (rule 2).
7. **Evaluation page (`/evaluation`)**, filled from `/api/model/metrics`:
   - Headline cards: mAP@0.5, precision, recall, F1, CPU FPS.
   - Per-class table, confusion matrix (rendered from JSON as an accessible heat-grid, with the PNG as a fallback), PR and F1 curves, training curves.
   - **Before vs after preprocessing** ablation chart and image, robustness table, latency table.
   - **Error gallery** with captions, plus dataset stats and samples.
   - A **Limitations** section.
   - Every number shows its source (`metrics.json`, the test split name and the evaluation date).
8. **About page (`/about`)**: problem, objectives, beneficiaries (smallholder farmers, haulers, cooperatives, LGU road maintenance teams), the architecture diagram image, a one-paragraph plain-language "How YOLO works", real-world deployment use, limitations and ethics/privacy (frames are processed and discarded unless the driver confirms; faces and plates are not stored beyond the evidence frame).
9. **Vitest:** `DetectionOverlay` coordinate scaling; `useFrameScanner` in-flight skipping; `vision.ts` adapters; and `hazards.ts` now accepting `data_source: 'api'` detections. Update `frontend/tests/integration/api.integration.mjs` for the new endpoints.

**Acceptance:**
- `npm run typecheck`, `npm run test` and `npm run build` pass.
- The manual flow works end to end with the backend running: Vision Lab image → boxes; video → live boxes; Plan → Use route → camera or sample video → hazard detected → confirm → pin on map → recommendation changes; Evaluation page shows real metrics.

---

## 8. Phase 5: Deliverables for submission and panel

1. **README.md rewrite** (keep it scannable):
   - What and why; a screenshot or GIF.
   - **Quick start** (one command: `scripts/start.ps1` on Windows, `scripts/start.sh` on macOS/Linux) that creates a venv, installs requirements, starts uvicorn and Vite, and opens the browser.
   - "Reproduce results" (prepare → train → evaluate commands).
   - Project structure, tech stack, model download note, and credits/licenses (Ultralytics AGPL-3.0, dataset licenses, OSM/OSRM attribution).
2. **`docs/`:** all files listed in §3.
   - `MODEL_CARD.md` covers intended use, YOLO explained step by step (backbone → neck → detection head → NMS; one-stage vs two-stage; why the nano model for CPU and mobile), training data, metrics, thresholds, limitations and failure modes.
   - `DEMO_SCRIPT.md` is a timed 5–10 minute script with a backup plan (offline sample video if the internet or camera fails).
3. **`docs/DEFENSE_QA.md`:** 25+ likely panel questions with short, honest answers. Examples:
   - Why YOLO and not classification or segmentation?
   - What does "pretrained" mean, and what exactly did *you* train? Why two models instead of one?
   - How did you optimize? Walk through the E0→final table.
   - What is IoU, mAP@0.5 vs mAP@0.5:0.95?
   - Precision vs recall: which matters more here, and why?
   - How did you choose the confidence threshold?
   - What does CLAHE do mathematically?
   - How do you avoid train/test leakage?
   - Why does it confuse wet road with standing water?
   - How does a detection change the route?
   - What happens at night or in rain?
   - Can it run on a phone?
   - Privacy?
   - What would you do with more time?
4. **Presentation** (`presentation/build_deck.py` using `python-pptx` → `presentation/AniRoute_CSST106.pptx`). Visual-first, ≤ 25 words of body text per slide, speaker notes carrying the detail. Use the recommended structure from the guide:
   1. Title  2. Problem (photo + one cited stat)  3. Objectives  4. Significance/Beneficiaries  5. System Overview (architecture PNG)  6. Dataset (sample grid + class distribution)  7. Preprocessing (before/after)  8. CV Method (YOLO diagram + detection flowchart)  9. System Implementation (screenshots of Vision Lab + Active Trip)  10. Results (annotated detections)  11. Evaluation (metric cards + confusion matrix + PR curve)  12. Before vs after ablation + error analysis  13. Demonstration (live)  14. Limitations  15. Real-world application & future work  16. Thank you / Q&A.

   Capture the screenshots with a Playwright script (`frontend/scripts/capture-screenshots.mjs`). This follows the pattern of the existing `record-preview.mjs`.
5. **`.gitignore`:** add `.env`, `node_modules/`, `dist/`, `ml/data/`, `backend/data/evidence/`, `backend/data/*.jsonl` and `ml/runs/`.

---

## 9. Verification (run after every phase; all must pass before declaring done)

```sh
# backend
python -m pytest -q backend/tests
# frontend
cd frontend && npm run typecheck && npm run test && npm run build
# evaluation reproducibility (after weights exist)
python ml/evaluate.py --weights backend/models/aniroute-hazards-v1.pt --split test
# smoke
python -m uvicorn backend.main:app --port 8000 &   # then:
curl localhost:8000/api/health            # live_hazard_detection: true
curl -F file=@backend/samples/<sample>.jpg localhost:8000/api/vision/detect
```

Then drive the app in a browser and confirm every item:

- [ ] Image upload → original / preprocessed / annotated shown; slider and CLAHE toggle change the result
- [ ] Sample video plays with live boxes; FPS and latency visible
- [ ] Webcam tab shows live boxes (or a clear permission message)
- [ ] Active trip (Demo): the sample video produces a *real* detection → confirm → map pin → recommendation re-checked and changes when the hazard is on the active route
- [ ] Active trip (Live): the camera frame loop runs; confirm works (no `data_source` error)
- [ ] The Evaluation page shows only numbers that exist in `ml/reports/*.json`
- [ ] About page and all `docs/*` complete; the deck builds; README quick start works on a clean clone
- [ ] Backend offline → every page shows a clear, non-crashing message

---

## 10. Execution order and reporting

1. Create the branch. Fix `.gitignore` and the `data_source` contract bugs first; they are small and unblock everything.
2. Phase 3 backend vision service with a **stub detector**, then Phase 4 frontend against the stub. All UI work can proceed before the model is trained.
3. Phase 1 dataset scripts → **pause for 👤 dataset labelling and Colab training** → drop the weights in → Phase 2 evaluation → swap the stub for the real model.
4. Phase 5 deliverables last, because they consume the real metrics and screenshots.
5. After each phase, report in under 10 lines: what was built, the check results (pass/fail with output), what is next, and any 👤 human task needed.

Remember: **honest, reproducible metrics plus a live demo that clearly shows real detections changing a real route** are what score the 30% + 20% + 10% defense lines. Polish comes second.
