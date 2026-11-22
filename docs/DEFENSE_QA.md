# Defense — likely panel questions and honest answers

Replace every *[number]* with the value from `ml/reports/` before the defense.

## Problem and relevance

**1. Why is this a real problem?**
Perishable crops lose a large share of value between farm and market — JICA estimates 5–48% for fruits
and 16–40% for vegetables in the Philippines — and rough, potholed farm-to-market roads add bruising and
delay. Drivers discover hazards only when they hit them, and route planners ignore crop fragility.

**2. Who uses it?**
Drivers and haulers of produce (alerts, safer route), farmers and cooperatives (less spoilage), and LGUs
(geotagged, photo-verified road-damage reports).

**3. Why not just use Google Maps?**
Navigation apps rank by time and traffic. They do not see road-surface damage, and they do not weigh how
sensitive the cargo is. AniRoute adds both.

## Computer vision method

**4. Which CV task is this and why object detection?**
Object detection: we need *where* the hazard is (a box) and *what* it is. Classification would only say
"this frame has a pothole somewhere"; segmentation needs pixel masks, which are far more expensive to
label and slower to run, and the boxes are enough to alert a driver.

**5. Why YOLO?**
One-stage, real-time on a CPU, strong accuracy, simple transfer learning, and export to ONNX/OpenVINO for
phones and edge devices. Two-stage detectors like Faster R-CNN can be more accurate on tiny objects but are
much slower.

**6. What does "pretrained" mean, and what exactly did you train?**
Model A starts from YOLO11 weights trained on COCO (118k photos). We fine-tuned it on labelled pothole and
road-damage images so its head predicts our two classes — that training is ours (runs E0–E7). Model B is
the COCO model used without training, plus our driving-corridor rule.

**7. Why two models instead of one?**
COCO already recognises people, animals and vehicles very well — retraining that would need thousands of
new labels for no gain. Road damage is not in COCO, so it needs fine-tuning. Running both on the same
preprocessed frame costs *[system ms]* ms per frame on the laptop CPU.

**8. Explain the YOLO pipeline in 30 seconds.**
Backbone extracts features; neck merges them at several scales; head predicts boxes, class scores and
confidence; we drop boxes under the threshold; non-maximum suppression removes duplicates.

**9. What preprocessing do you do and why?**
EXIF orientation fix; CLAHE on the lightness channel only when the frame is dark or low-contrast; letterbox
to 640×640 keeping the aspect ratio. Training also uses augmentation (mosaic, colour jitter, flips) — that
is separate from preprocessing.

**10. What is CLAHE, mathematically?**
Histogram equalisation spreads pixel intensities so the cumulative distribution becomes roughly linear.
CLAHE does it per 8×8 tile (adaptive) and clips each tile's histogram at a limit (2.0) before equalising,
redistributing the clipped counts, so noise is not over-amplified; tiles are blended bilinearly.

**11. Did CLAHE actually help?**
*[From ablation.json: mAP with CLAHE off / auto / on, overall and on dark images.]* If it helps only on
dark images, that is why the app applies it automatically only to dark frames.

**12. How does the driving-corridor rule work?**
A trapezoid in front of the vehicle (from 40% down the frame to the bottom, widening from 20% to 50% of the
width). A COCO object counts as an obstruction only if the bottom-centre of its box — where it touches
the road — is inside, and the box is at least 12% of the frame height (close). Parked cars at the
roadside are ignored. *[model_b.json: precision with vs without the rule.]*

**13. Why 2 of 3 frames?**
A single frame can show a shadow or wet patch as a pothole. Requiring the same hazard in 2 of the last 3
analysed frames (~1.2 s) removes most one-frame false alarms for a small delay. *[smoothing.json]*

## Evaluation

**14. What is IoU and why 0.5?**
Intersection over union of predicted and true boxes. 0.5 is the standard (PASCAL VOC/COCO) threshold for a
"correct" box; mAP@0.5:0.95 also rewards tighter boxes.

**15. mAP@0.5 vs mAP@0.5:0.95?**
The first averages precision over recall at IoU 0.5; the second repeats that for IoU 0.50 to 0.95 and
averages — it is stricter and always lower.

**16. Precision or recall — which matters more here?**
For a driver, too many false alarms make them ignore the app (precision); missed potholes cause damage
(recall). We choose the threshold at maximum F1 on validation, and the driver confirmation step catches
remaining false alarms, so we can afford a slightly lower threshold for better recall.

**17. How did you choose the confidence threshold?**
The F1-vs-confidence curve on the validation split; we took the peak (*[value]*), then reported test
results at that fixed threshold.

**18. How do you know the test score is not inflated?**
Test images are never trained on or used for choices; near-duplicates of training images are removed from
val/test by perceptual hashing; the threshold and best run are chosen on validation.

**19. Read the confusion matrix for us.**
Rows are the true class, columns the prediction. Diagonal = correct. The last column is missed objects,
the last row false alarms. *[Point at the largest off-diagonal cell and explain it.]*

**20. What were your optimisation steps and what helped most?**
E0 baseline → E1 longer training → E2 bigger model → E3 higher resolution → E4 augmentation; E5 threshold
tuning; E6 CLAHE; plus ONNX/OpenVINO export for speed. *[Best gain and selected run from
optimization_table.md; OpenVINO vs PyTorch speed from latency.json.]*

**21. Why didn't you use automatic hyperparameter tuning?**
Ultralytics' genetic tuner needs hundreds of training runs — beyond free Colab. We ran controlled,
one-change-at-a-time experiments instead, which are also easier to explain.

**22. How fast is it?**
*[latency.json: end-to-end ms and FPS on this laptop.]* The app analyses about 1–2 frames per second during
a trip, which is enough because hazards stay in view for several seconds.

## Errors, limitations, future work

**23. Where does it fail?**
Small/distant potholes and faint cracks (miss rate by size in error_analysis.md), wet asphalt and shadows
(false alarms), night and motion blur. Show two images from the error gallery.

**24. Why doesn't it detect standing water or landslides?**
Public labelled data for flooded roads and landslides is small and inconsistent; COCO has no such classes.
Drivers report standing water manually. Future work: collect and label local images.

**25. Will it work on Philippine roads?**
Training data is mostly foreign (RDD2022: Japan, India, Czech Republic, Norway, USA, China). *[If you have
test_local: "On our N local photos the mAP@0.5 was X, lower than the public test set — expected domain
shift."]* Fine-tuning on local images is the most important next step.

**26. How does a detection change the route?**
A confirmed hazard is saved with GPS. Every route that passes within 75 m gets a road-risk increase
(pothole 12, standing water 20, severe damage 25, obstruction 30, capped at 100), multiplied by crop
sensitivity, and routes are re-ranked. These weights are heuristics, not validated loss values.

**27. Privacy?**
Frames are processed in memory and discarded; only the frame the driver confirms is stored with GPS. In a
real deployment, evidence should be encrypted, access-controlled and deleted after a set period.

**28. Can it run on a phone?**
The browser already uses the phone camera and sends frames to the server. For on-device inference, the
nano model exported to ONNX/TFLite would run on recent phones; we measured *[X]* ms on a laptop CPU.

**29. What would you do with more time?**
Local Philippine dataset and labels; standing-water and landslide classes; distance-to-hazard estimation;
on-device inference; shared hazard map with LGUs; field trial to measure actual spoilage reduction.

**30. What was the hardest part?**
*[Your honest answer — e.g. merging datasets with different class names, or false alarms from shadows.]*
