# Presentation outline (12–14 minutes + demo)

`python presentation/build_deck.py` generates `presentation/AniRoute_CSST106.pptx` from this structure,
pulling the latest screenshots and figures from `presentation/screenshots/` and `ml/reports/`.
Slides with pending results show a clearly marked placeholder until evaluation is run.

| # | Slide | Visual | On-slide text (≤ 25 words) | Speaker notes (key points) |
| --- | --- | --- | --- | --- |
| 1 | Title | Logo, app screenshot | AniRoute — real-time road-hazard detection for crop-aware delivery routing | Team, course, one-line pitch |
| 2 | Problem | Loss-range bars (fruits 5–48%, vegetables 16–40%) + road photo | Produce loses value between farm and market; rough roads add damage | Cite JICA; drivers find hazards only when they hit them |
| 3 | Objectives | 5 icons | Detect · improve in poor light · reduce false alarms · re-route · prove it | Each objective maps to a later slide |
| 4 | Significance | 4 beneficiary tiles | Farmers · haulers · cooperatives · LGUs | Concrete benefit per group |
| 5 | System overview | Architecture diagram (shapes) | Camera → preprocess → 2 YOLO models → smoothing → confirm → re-route | Browser, FastAPI, OSRM |
| 6 | Dataset | `dataset_samples.png` + `dataset_class_distribution.png` | Public labelled data: RDD2022 India subset (2,692 images) | Source splits kept, leakage check, class mapping |
| 7 | Preprocessing | `preprocessing_before_after.png` | Orientation fix · letterbox 640 · CLAHE measured and turned off | We tested an assumption and the data said no |
| 8 | CV method | Pipeline diagram + transfer-learning table | YOLO11: COCO-pretrained, fine-tuned on road damage | Backbone/neck/head/NMS; transfer learning |
| 9 | Implementation | Plan + Active Trip screenshots | Web app: route planning, live camera / recorded drive | Stack: Vue, FastAPI, Ultralytics, OpenCV |
| 10 | Results | Annotated detections (`ml/reports/sample_detections/`) | Real detections on unseen test images | Point at classes and confidence |
| 11 | Evaluation | Metric tiles + confusion matrix + PR curve | mAP@0.5 · precision · recall · F1 on the test split | Threshold chosen on validation |
| 12 | Optimisation | `optimization_chart.png` + speed chart | Baseline E0 → selected ★; OpenVINO speed-up | One change per experiment; E5, E6 |
| 13 | Error analysis | 3 gallery images + miss rate by size | Where it fails and why | Small potholes, shadows, night |
| 14 | Demonstration | "Live demo" divider | — | Follow docs/DEMO_SCRIPT.md |
| 15 | Limitations | Icon list | Foreign training data · no standing-water model · heuristic risk weights | Be specific and honest |
| 16 | Real-world use & future work | Roadmap | Local dataset · on-device · LGU hazard map · field trial | Close with the impact |
| 17 | Thank you / Q&A | Logo | Questions | — |

**Timing:** slides 1–4 (3 min), 5–9 (4 min), 10–13 (4 min), demo (6–8 min), 15–17 (2 min).
