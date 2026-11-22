# Problem, objectives and significance

## The real-world problem

Perishable crops in the Philippines lose much of their value between farm and market.

- A JICA study of Philippine food value chains estimates postharvest losses of **5–48% for fruits and
  16–40% for vegetables**, and names handling and distribution as a major cause.
  Source: JICA, *Data collection survey on the food value chain* —
  <https://openjicareport.jica.go.jp/pdf/1000035809.pdf>
- Extension literature on Philippine postharvest handling cites losses of **10–50% for horticultural
  perishables** (Bautista & Maunahan, 2007), as summarised in the *Asian Journal of Agriculture and
  Development* — <https://ageconsearch.umn.edu/record/258979/files/AJAD_Extension%20Delivery_Postharvest%20Handling.pdf>
- Rural roads are often rough, potholed, dusty in summer and muddy in the monsoon, which makes moving farm
  produce slow and risky — World Bank feature on Mindanao rural roads:
  <https://www.worldbank.org/en/news/feature/2013/04/12/philippines-rural-roads-lead-to-safer-faster-travel-in-mindanao>

> **Check before presenting.** These figures are ranges from different years, crops and methods. Quote
> them as ranges with the source on the slide, and do not claim AniRoute reduces losses by a specific
> percentage — that needs field trials (see Limitations).

**The gap:** drivers find potholes, damaged pavement and obstructions only when they reach them, and
route planners rank roads by time and distance alone. Nothing combines *what the road looks like today*
with *how fragile the cargo is*.

## What AniRoute does

A phone or dashcam on the delivery vehicle runs a computer-vision detector. Hazards seen in several
consecutive frames are shown to the driver, who confirms them with a tap or by voice. Confirmed hazards
are geotagged and raise the road-risk score of every route that passes within 75 m, weighted by how
sensitive the crop is. The app then recommends a different route if that is now safer for the cargo.

## Objectives (measurable)

1. **Detect** potholes and severe road damage (fine-tuned YOLO, Model A) and road obstructions
   (pretrained COCO YOLO, Model B) in images, recorded video and live camera frames.
2. **Improve robustness in poor light** with CLAHE preprocessing, and measure the effect with an
   ablation (CLAHE off / auto / on) on the test split.
3. **Optimise** the detector through documented experiments (E0 baseline → E7) and faster CPU runtimes
   (ONNX/OpenVINO), reporting accuracy *and* speed.
4. **Limit false alarms** with a driving-corridor rule for obstructions and 2-of-3 frame confirmation.
5. **Turn detections into decisions**: confirmed hazards re-rank delivery routes by crop-spoilage risk.
6. **Prove it** with precision, recall, F1, mAP@0.5, mAP@0.5:0.95, a confusion matrix and an error
   analysis on images the model never trained on.

## Significance — who benefits

| Beneficiary | Benefit |
| --- | --- |
| Smallholder farmers | Fewer bruised and spoiled harvests on the way to market |
| Haulers and drivers | Early warning of hazards; smoother, safer routes |
| Cooperatives and traders | Route choice that weighs crop sensitivity, not just travel time |
| LGU road maintenance | Geotagged, photo-verified reports of damage on farm-to-market roads |

## Scope

In scope: road-surface hazard detection (pothole, severe road damage), obstruction detection, driver
confirmation, crop-aware route re-ranking, evaluation. Out of scope for this MVP: automatic standing-water
detection (driver-reported), weather/flood feeds, accounts and multi-user storage, field trials.
