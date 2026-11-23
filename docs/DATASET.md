# Dataset

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

## Source actually used

| Dataset | Link | License | Images used | Class mapping |
| --- | --- | --- | --- | --- |
| RDD2022 (Crowdsensing-based Road Damage Detection Challenge 2022), India subset | paper <https://arxiv.org/abs/2209.08538> · official <https://github.com/sekilab/RoadDamageDetector> · YOLO-format mirror <https://huggingface.co/datasets/dronefreak/RDD2022> | CC BY-SA 4.0 | 2,692 (seeded random sample, seed 42) | D40 pothole → `pothole`; D00, D10, D20 cracks → `severe_road_damage` |

India was chosen because its roads (mixed asphalt, narrow provincial roads, roadside obstacles) are the closest
RDD2022 match to Philippine farm-to-market roads. The official RDD2022 download link was offline, so the public
Hugging Face mirror (same images and labels, already in YOLO format) was used. No account or manual labelling was needed.

### Final counts (`ml/reports/dataset_stats.json`)

| Split | Images | `pothole` boxes | `severe_road_damage` boxes |
| --- | ---: | ---: | ---: |
| train | 1,800 | 339 | 889 |
| val | 448 | 77 | 180 |
| test | 444 | 75 | 189 |

8 validation/test images were removed by the leakage check (near-duplicates of training images). The source
train/valid/test splits were kept. `pothole` is the minority class (339 training boxes vs 889),
which is a stated limitation (see `MODEL_CARD.md`).

## Reproduce it (about 10 minutes, no account)

```bash
python ml/scripts/download_rdd2022.py --country India --train 1800 --valid 450 --test 450
python ml/scripts/prepare_dataset.py --source ml/data/raw/rdd2022_hf/data     --map pothole=pothole longitudinal_crack=severe_road_damage           transverse_crack=severe_road_damage alligator_crack=severe_road_damage
bash ml/run_cpu_pipeline.sh     # train, select, evaluate, export, demo video, slides (~7 h on a laptop CPU)
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
