# AniRoute manual test walkthrough

Use this walkthrough to verify the complete class-presentation flow: application startup, route planning,
recorded-video inference, hazard confirmation, evaluation evidence, and the computer-vision explanation.

## 1. Prepare the computer

You need:

- Python 3.10–3.12;
- Node.js 22.12 or newer;
- an internet connection for location search, routes, and map tiles; and
- a Chromium-based browser with location and camera permissions available.

From the repository root, confirm the tool versions:

```bash
node --version
/opt/homebrew/bin/python3.12 --version
```

On this Mac, create the virtual environment explicitly with Python 3.12 if `.venv` does not exist:

```bash
/opt/homebrew/bin/python3.12 -m venv .venv
```

## 2. Start AniRoute

From the repository root:

```bash
bash scripts/start.sh
```

The first start installs the backend and frontend packages. Keep this terminal open. The application should
open automatically; otherwise visit <http://127.0.0.1:5173>.

Open <http://127.0.0.1:8000/api/health> in a second browser tab. Wait until the response contains:

```json
{
  "status": "ok",
  "live_route_engine": true,
  "live_hazard_detection": true,
  "vision_warming_up": false,
  "supported_hazards": ["pothole", "severe_road_damage"]
}
```

Pass criteria:

- The frontend opens without an error banner.
- The health endpoint reports live hazard detection.
- The terminal does not exit with a model-loading error.

## 3. Test route planning

1. Open **Plan**.
2. Set **How many crop types?** to `1`.
3. Enter `Tomatoes` and `250 kg`.
4. Choose **Small truck**.
5. Search for a nearby pickup point and select an item from the location suggestions.
6. Set **How many delivery points?** to `1`.
7. Search for a nearby destination and select an item from the suggestions.
8. Select **Find routes**.

Use two nearby places that the location search recognizes. Nearby points make route calculation faster and
make it easier to test location-based route updates.

Pass criteria:

- The page displays route options rather than **Route calculation unavailable**.
- Each option shows time, distance, road condition, and crop transport risk.
- Selecting a route highlights its line on the map.
- **Use this route** opens Active Trip.

## 4. Test recorded-drive computer vision

1. On Active Trip, find the **Road camera** card.
2. Confirm it lists **Pothole, Severe road damage** under **Detects now**.
3. Select **Analyse recorded drive**.
4. Watch the video and road-camera status.

Expected sequence:

1. The status changes to **Road analysis active**.
2. Bounding boxes appear over detected road damage.
3. The panel shows class names, confidence values, and frame-analysis timing.
4. After the same class is detected in at least two of three recent frames, a
   **Computer vision detected a road hazard** alert appears.
5. Select the alert to review the annotated road-analysis frame.

The first model call may take longer while ONNX loads. Later frames should process much faster. Do not fail
the test solely because the first frame is slower.

Pass criteria:

- Video playback continues while frames are analysed.
- At least one `severe road damage` alert appears.
- The alert reports that the finding was seen in recent frames.
- The review dialog includes an annotated frame, hazard type, confidence, and location state.

## 5. Test confirmation and route integration

1. In the finding dialog, select **Confirm & upload**.
2. Wait for the save operation and route recheck to finish.
3. Observe the message shown above the Active Trip content.

Pass criteria:

- The dialog closes after a successful confirmation.
- A success message says the road observation was saved.
- Route checking completes without an unhandled error.
- If the browser location is within 75 metres of the selected route, the matching route's road-risk score is
  recalculated and a different route may be recommended.

The computer-vision test still passes if the route score does not change because the browser location was
unavailable or outside the selected route. The interface should explain that condition instead of failing.

## 6. Test the live camera input

This is an additional input-path check. The recorded drive remains the most repeatable way to verify the
complete flow.

1. Select **Use live camera**.
2. Allow camera access when the browser asks.
3. Point the camera at a clear road-damage photograph.
4. Hold the image steady for several frames.

Pass criteria:

- The camera preview opens.
- The application analyses frames without building a request backlog.
- Detected boxes stay aligned with the camera image.
- A water-filled pothole image produces pothole boxes around the reflective road depressions when it fills most of the camera view.
- Denying camera permission produces a clear permission message and does not break the page.

## 7. Test the Evaluation page

Open **Evaluation** from the header.

Verify the headline results load from `ml/reports/`:

- mAP@0.5: approximately `0.278`;
- mAP@0.5:0.95: approximately `0.122`;
- deployed precision: approximately `78.3%`;
- deployed recall: approximately `13.6%`; and
- deployed F1: approximately `0.232`.

The page should also explain that `0.145` is retained as the balanced max-F1 reference, while the running
detector uses the high-confidence threshold `0.40`.

Scroll through and confirm the page displays:

- per-class results for potholes and severe road damage;
- the confusion matrix;
- precision-recall, F1-confidence, and training curves;
- baseline-to-final optimization results;
- the CLAHE before/after comparison;
- runtime speed and temporal-smoothing results;
- false positives, false negatives, and misclassifications; and
- the stated limitations.

Pass criteria:

- No section says its reports are unavailable.
- Charts and error-gallery images load.
- The metrics match the committed evaluation reports.
- The page explains both successful detections and failure cases.

## 8. Test the About page and course coverage

Open **About** and verify that a presenter can explain each required component:

| Course requirement | What to verify in AniRoute |
| --- | --- |
| Image/video/camera input | Recorded drive and live road camera |
| Computer-vision task | YOLO11 object detection |
| Image preprocessing | Orientation correction, 640×640 letterboxing, measured CLAHE option |
| Meaningful result | Road-damage boxes, classes, confidence, and confirmed road finding |
| Result visualization | Camera overlay, annotated evidence frame, and map location |
| Performance evaluation | Precision, recall, F1, mAP, confusion matrix, curves, and error analysis |
| Working-system demonstration | Recorded-drive detection in Active Trip |
| Algorithm explanation | Backbone, neck, detection head, transfer learning, thresholding, and NMS |
| Limitations | Small/distant hazards, lighting, motion blur, dataset location, and route-risk assumptions |
| Real-world application | Road-condition awareness for agricultural transport |

Pass criteria:

- The About page describes the same two classes used by the running detector.
- The preprocessing description agrees with the Evaluation page.
- The limitations are specific and consistent with the error analysis.

## 9. Final acceptance checklist

Before presenting, confirm all of the following:

- [ ] AniRoute starts with `bash scripts/start.sh`.
- [ ] `/api/health` reports live hazard detection.
- [ ] Location search and route calculation work.
- [ ] Active Trip opens from a selected route.
- [ ] The recorded drive displays bounding boxes and confidence.
- [ ] The 2-of-3-frame rule produces a reviewable finding.
- [ ] Confirmation saves the annotated observation.
- [ ] Evaluation metrics, charts, and error examples load.
- [ ] About explains the CV pipeline and limitations.
- [ ] The complete flow can be finished within 10–15 minutes.

## Troubleshooting

### Backend offline

Stop the running command with `Ctrl+C`, then run `bash scripts/start.sh` again. Confirm port `8000` is not
already in use.

### Detector unavailable

Confirm these files exist:

```text
backend/models/aniroute-hazards-v1.pt
backend/models/aniroute-hazards-v1.onnx
```

On Apple Silicon, leave `ANIROUTE_MODEL_FORMAT` unset or set it to `auto`; AniRoute will select ONNX.

### Route calculation unavailable

Confirm the internet connection, choose both locations from the suggestion list, and try two closer points.
The routing service and map tiles are external services.

### No alert from the recorded drive

Wait through several video frames, confirm the panel says **Road analysis active**, and check the terminal for
frame-analysis errors. Restart the application if the model did not finish warming up.

### Evaluation figures are missing

Confirm the backend is running and that `ml/reports/metrics.json`, `ml/reports/confusion_matrix.png`, and the
other committed report files are present.
