| ID | Experiment | Change | mAP@0.5 | mAP@0.5:0.95 | P | R | F1 | CPU ms | FPS |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| E0 | Baseline | COCO-pretrained YOLO11n, default settings, 20 epochs, 640 px | 0.289 | 0.117 | 0.380 | 0.350 | 0.364 | 45.0 | 22.2 |
| E1 ★ | Longer training | 40 epochs with early stopping (patience 20) | 0.334 | 0.137 | 0.485 | 0.381 | 0.427 | 45.8 | 21.8 |
| E5 | Confidence threshold tuned | E1: conf 0.25 → 0.14 (max F1) (before: F1 0.378) | 0.334 | 0.137 | 0.485 | 0.381 | 0.427 | 45.8 | 21.8 |
| E6 | CLAHE preprocessing | E1: CLAHE auto vs off → off kept (higher val mAP) (before: F1 0.427, mAP 0.334) | 0.339 | – | – | – | 0.430 | 45.8 | 21.8 |
