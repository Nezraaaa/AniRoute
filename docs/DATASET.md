# Dataset guide (no labelling required)

## What an object-detection dataset is

A YOLO dataset is a folder of images plus **one text file per image** listing its boxes:

```
train/images/road_0001.jpg      train/labels/road_0001.txt
                                 0 0.512 0.640 0.120 0.085     ← class x_center y_center width height
                                 1 0.300 0.710 0.400 0.060       (all values are 0–1, relative to the image)
```

plus a `data.yaml` that names the classes and the folders. Images are split into:

- **train** — the model learns from these;
- **val** (validation) — used during training and to choose settings/thresholds;
- **test** — used **once** at the end to report the final numbers. Never trained or tuned on.

## Our classes (Model A)

| ID | Class | Includes |
| --- | --- | --- |
| 0 | `pothole` | potholes (RDD2022 `D40`) |
| 1 | `severe_road_damage` | alligator, longitudinal and transverse cracking (RDD2022 `D20`, `D00`, `D10`) |

`road_obstruction` comes from Model B (COCO, no training). `standing_water` is driver-reported only.

## Sources — fill in the exact versions you used

| Dataset | Link | License | Images used | Class mapping |
| --- | --- | --- | --- | --- |
| Pothole dataset (Roboflow Universe) | e.g. <https://universe.roboflow.com/vg2024/potholedetectionyolov8-tz4cy> (CC BY 4.0, ≈1.4k images) or <https://universe.roboflow.com/yoloteam/potholedetectionyolov8-11c1w/dataset/1> (665 images) | _check page_ | _fill in_ | its pothole class → `pothole` |
| RDD2022 — Crowdsensing-based Road Damage Detection Challenge 2022 | paper <https://arxiv.org/abs/2209.08538> · official <https://github.com/sekilab/RoadDamageDetector> · YOLO copy e.g. <https://universe.roboflow.com/rdd2022/road-damage-iztzn> | _check page_ | _fill in (subset)_ | D40 → pothole; D00, D10, D20 → severe_road_damage; others dropped |
| Local Philippine photos (optional, test only) | own photos | own | _fill in_ | labelled in Roboflow |
| Obstruction test set (Model B evaluation) | e.g. a Roboflow "animals/vehicles on road" set, or ~50 own labelled photos | _check_ | _fill in_ | every box = obstruction |

`ml/reports/dataset_stats.json` records the final counts automatically.

## Step by step (about one hour in a browser)

1. Create a free account at <https://roboflow.com>.
2. Open the pothole dataset page on Roboflow Universe → **Fork Dataset** (copies it to your workspace).
3. Open an RDD2022 copy with classes `D00 D10 D20 D40` → **Fork Dataset**.
   RDD2022 is large; in your fork you can delete countries you do not need, or let
   `prepare_dataset.py --max-images 2500` take a random subset.
4. For each fork: **Versions → Generate**. Preprocessing: *Auto-Orient only* (our app does its own
   resizing). Augmentation: *none* (Ultralytics augments during training). Keep the 70/20/10 split.
5. **Download Dataset → YOLOv8** → either *Download zip* or *Show download code* (copy workspace,
   project and version into the Colab notebook).
6. Run `ml/notebooks/train_colab.ipynb` (steps 5–6 merge and check the data for you):

```bash
python ml/scripts/prepare_dataset.py \
    --source ml/data/raw/potholes --source ml/data/raw/rdd2022 \
    --map pothole=pothole potholes=pothole D40=pothole \
          D00=severe_road_damage D10=severe_road_damage D20=severe_road_damage \
    --max-images 2500
```

## What `prepare_dataset.py` guarantees

- Unknown classes are dropped and counted (`dataset_stats.json → dropped`).
- Unreadable images are removed.
- **Leakage check:** a validation/test image whose perceptual hash is within 4 bits of a training image
  is removed, so near-identical frames cannot inflate the test score.
- Warns when a class has fewer than 300 training boxes (mention it in the limitations).
- Writes `dataset_class_distribution.png` and `dataset_samples.png` for the Dataset slide and copies six
  held-out test images to `backend/samples/` for the live demo.

## Optional local test set

Put 30–50 labelled photos of Philippine farm-to-market roads in `ml/data/local_test/images` and
`ml/data/local_test/labels` (same class IDs) before running `prepare_dataset.py`; it is added to
`data.yaml` as `test_local` and `evaluate.py test` reports it separately. Name files with `night`, `rain`
or `blur` to get those robustness subsets.
