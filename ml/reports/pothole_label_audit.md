# Pothole class audit (found during final checks)

## Finding

The "pothole" class in the public RDD2022 mirror we trained on (Hugging Face `dronefreak/RDD2022`, India
subset, class 3 = "pothole") is **mostly faded white lane markings, not potholes**.

## Evidence

1. **Training labels.** We inspected 32 randomly chosen "pothole" boxes from our training split (seed 7)
   up close. About 27 of 32 frame worn or faded lane paint; only a handful show road-surface damage.
   The dataset has 491 "pothole" boxes in total. This pattern matches RDD's separate "white line blur"
   class (D44), which looks merged into the pothole index in this mirror.
2. **Model behaviour on our data.** Every correct "pothole" detection we found on the held-out
   validation and test splits (IoU ≥ 0.5 with a label) is on a faded lane marking.
3. **Real potholes.** We ran the deployed model, at the app's settings and also at a low 15% confidence,
   on 14 photos of real potholes from Wikimedia Commons (CC0, public domain and CC BY-SA). It returned
   **no detections at all**.

## What it means

- **Cracks:** genuine. The "severe road damage" class (longitudinal, transverse and alligator cracks)
  shows real cracked pavement, and its correct detections are real cracks.
- **Potholes:** the reported AP@0.5 of 0.197 measures agreement with these lane-marking labels, not the
  ability to find real potholes. The app should not be described as detecting potholes reliably.

## Fix (future work)

Rebuild the pothole class from correctly labelled pothole images and retrain:
- Verify labels visually before training.
- Keep a small set of real-pothole photos as a sanity test, like the one above.
