# Evaluation

All numbers come from `ml/evaluate.py`, which runs the **app's own preprocessing** (not a separate
pipeline) on images the model never trained on and writes everything to `ml/reports/`. The in-app
**Evaluation** page reads the same files. Re-run any time:

```bash
python ml/evaluate.py test      --data ml/data/aniroute/data.yaml --run-dir ml/runs/<selected>
python ml/evaluate.py compare   --runs ml/runs/E0 ml/runs/E1
python ml/evaluate.py latency
python ml/evaluate.py smoothing --video backend/samples/demo_drive.webm
python ml/scripts/preprocess_demo.py
```

## Protocol (how we avoid fooling ourselves)

1. Train on **train**; choose the best experiment and all confidence thresholds on **val**.
2. Report **test** once with those choices fixed.
3. Near-duplicate images are removed from val/test before training (`prepare_dataset.py`).
4. The selected model (E1), balanced threshold (0.145), deployed high-confidence threshold (0.40), and
   preprocessing (CLAHE off) were fixed on validation before their test results were reported.

## Metrics in one sentence each

| Metric | Meaning |
| --- | --- |
| IoU | Overlap of a predicted box and a true box (intersection ÷ union); ≥ 0.5 counts as a match |
| Precision | Of the hazards the system reported, the share that were real |
| Recall | Of the real hazards, the share the system found |
| F1 | Harmonic mean of precision and recall at the operating threshold |
| AP / mAP@0.5 | Area under the precision-recall curve (101-point COCO method), averaged over classes, at IoU 0.5 |
| mAP@0.5:0.95 | Same, averaged over IoU thresholds 0.50, 0.55 … 0.95 (rewards tight boxes) |
| Confusion matrix | Rows = true class, columns = predicted class; background = missed object or false alarm |
| TP / FP / FN | Correct detections / false alarms / missed hazards |

Our implementation (`ml/evaluation/metrics.py`) is unit-tested against hand-computed cases
(`ml/tests/test_metrics.py`).

## Results

### Model A on the test split (444 held-out images, 264 labelled objects)

Balanced reference: selected run **E1**, confidence **0.145** (max F1 on validation), CLAHE off, IoU 0.5.

| Class | Objects | AP@0.5 | AP@0.5:0.95 | Precision | Recall | F1 | TP / FP / FN |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| pothole | 75 | 0.197 | 0.083 | 0.32 | 0.23 | 0.27 | 17 / 36 / 58 |
| severe_road_damage | 189 | 0.358 | 0.162 | 0.44 | 0.35 | 0.39 | 66 / 85 / 123 |
| **overall** | **264** | **0.278** | **0.122** | **0.41** | **0.31** | **0.35** | 83 / 121 / 181 |

### Deployed high-confidence profile

The running application uses confidence **0.40**, selected on validation to target 70–80% precision.

| Class | Objects | Precision | Recall | F1 | TP / FP / FN |
| --- | ---: | ---: | ---: | ---: | --- |
| pothole | 75 | 0.44 | 0.05 | 0.10 | 4 / 5 / 71 |
| severe_road_damage | 189 | 0.86 | 0.17 | 0.28 | 32 / 5 / 157 |
| **overall** | **264** | **0.783** | **0.136** | **0.232** | 36 / 10 / 228 |

This profile makes displayed alerts more trustworthy but misses substantially more hazards. It must be
reported as **78.3% precision**, not 78.3% accuracy. The threshold-independent mAP values remain unchanged.
The complete profile is stored in `ml/reports/high_confidence_profile.json`.

Confusion matrix (rows = true, columns = predicted): the two classes are almost never confused with each
other (3 of 264); nearly all errors are against *background*: missed objects (181) or false alarms (121).

The confusion matrix below was generated for the balanced 0.145 reference.

![Confusion matrix](../ml/reports/confusion_matrix.png)
![Precision-recall](../ml/reports/pr_curve.png)

**How good is this?** Modest, and expected for the setup: a nano model (2.6 M parameters), 1,800 training
images, 40 epochs on a laptop CPU. RDD2022 is a hard benchmark: crack boxes are long, thin and labelled
inconsistently (see the error analysis below). The test score is
close to the validation score (0.339), so the model is not overfitting the validation choices.

### Optimisation series (validation split, 448 images)

| Step | Change | mAP@0.5 | mAP@0.5:0.95 | F1 | CPU ms |
| --- | --- | ---: | ---: | ---: | ---: |
| E0 | Baseline: COCO-pretrained YOLO11n, 20 epochs | 0.289 | 0.117 | 0.364 | 45 |
| **E1 ★** | Longer training: 40 epochs, early stopping | **0.334** | **0.137** | 0.427 | 46 |
| E5 | Confidence threshold 0.25 → 0.145 (max F1) | 0.334 | 0.137 | 0.378 → **0.427** | 46 |
| E6 | CLAHE auto → **off** | 0.334 → **0.339** | – | 0.427 → 0.430 | 46 |

Longer training gave the biggest gain (+16% relative mAP@0.5); tuning the threshold raised F1 by 13%
at no cost. Full table: `ml/reports/optimization_table.md`; chart: `optimization_chart.png`.

### Preprocessing before vs after (CLAHE ablation, test split)

| CLAHE | mAP@0.5 all | F1 all | mAP@0.5 dark images (13) |
| --- | ---: | ---: | ---: |
| **off (app default)** | **0.278** | **0.355** | **0.435** |
| auto (dark/low-contrast only) | 0.265 | 0.348 | 0.284 |
| always on | 0.196 | 0.252 | 0.284 |

CLAHE made the model **worse**, even on dark images. Our explanation: the model was trained on
un-enhanced images, so CLAHE shifts the input away from what it learned, and it amplifies asphalt texture
that then looks like cracks. The decision was made on validation (E6) and confirmed on test, so the app
keeps CLAHE **off** by default (it stays available through the API and `ANIROUTE_CLAHE`). The dark subset is small (13
images), so that column is indicative only. `ablation_bar.png`, `preprocessing_before_after.png`.

### Speed on the presentation laptop (AMD Ryzen, CPU only)

| Model | PyTorch 640 | ONNX 640 | OpenVINO 640 |
| --- | ---: | ---: | ---: |
| Pothole and crack detector | 50.8 ms | 39.3 ms | **37.7 ms** |

End to end (preprocessing + detection, auto-selected OpenVINO): **33.2 ms per frame ≈ 30 FPS** (95th
percentile 41 ms). OpenVINO is 26% faster than PyTorch on the same CPU. The app only needs 2 frames per
second during a trip, so there is ample headroom.
Re-run `python ml/evaluate.py latency` on the laptop you present with. `latency.json`, `speed_chart.png`.

![Speed](../ml/reports/speed_chart.png)

### Temporal smoothing (36 s demo drive, 72 analysed frames)

| | Alerts | Alerts per minute |
| --- | ---: | ---: |
| Every frame with a detection | 18 | 30 |
| **2-of-3 frames + 20 s cooldown** | **2** | **3.3** |

Smoothing cut alerts by 89%, the difference between an app a driver ignores and one they can use.
`smoothing.json` lists the 2 remaining alerts; watch the video and mark each `true`/`false` to report false
alarms per minute.

### Error analysis

`error_gallery/` (false alarms, misses, wrong class, with captions) and `error_analysis.md`.

| Object size (share of image) | Objects | Missed |
| --- | ---: | ---: |
| small (< 0.5%) | 16 | 88% |
| medium (0.5–5%) | 148 | 80% |
| large (> 5%) | 100 | 45% |

> **Interpretation.** Most errors are not the model failing to see damage but a mismatch with how it was
> labelled. On cracked road, the model often draws one large box where the annotator drew several small
> ones (or the reverse); at IoU 0.5 that single detection counts as one false alarm *and* several misses.
> Many "false alarms" are real-looking damage that was simply not labelled: broken road edges, gravel
> shoulders, patched asphalt. Genuine misses are mostly small or distant potholes (88% of small objects
> missed), which a 640-pixel nano model resolves poorly. The fixes are more training images, a larger
> model or higher input resolution (presets E2–E3, need a GPU), and labels from Philippine roads.
