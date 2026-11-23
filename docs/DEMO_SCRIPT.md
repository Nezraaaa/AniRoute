# Demonstration script (7 minutes, with backups)

## Before the panel (15 minutes earlier)

- [ ] Laptop on power, notifications off, browser zoom 100%, close other heavy apps.
- [ ] `scripts/start.ps1` running; open <http://127.0.0.1:5173>. Wait until the header badge
      says **Detector online** (model loaded). `backend/samples/demo_drive.webm` exists (see "Demo video" below).
- [ ] **Internet is on** (route planning uses OSRM and OpenStreetMap search; map tiles load online).
- [ ] **Allow location** in the browser and check that the trip page says *Vehicle GPS is pinned*.
- [ ] **Plan the demo trip from the venue**: set the pickup point to the school/building you present in,
      so the laptop's GPS position lies on the route. A confirmed hazard only changes route scores when
      its GPS position is within 75 m of a route. Do a full rehearsal at the venue beforehand.
- [ ] Open tabs: Plan, Evaluation, About. Have the slides open on the Results slide (annotated detections).
- [ ] Backup: `presentation/screenshots/` and a screen recording of this script on a USB stick.

## Script

| Time | Screen | Say / do |
| --- | --- | --- |
| 0:00 | **Slides → Results** | "This is the detector on its own": annotated held-out **test** images. Point at boxes, class (pothole or severe road damage / cracks) and confidence. |
| 0:45 | **Slides → Preprocessing** | Original vs model input; "CLAHE looks brighter to us, but the ablation showed the model does worse, so it is off by default." |
| 1:30 | **Plan** | Pickup = the venue, delivery = a nearby market; tomatoes, 250 kg, small truck. Live route options with crop-risk scores. Choose the recommended route → **Use this route**. |
| 2:30 | **Active trip** | Click **Analyse recorded drive** (or point the webcam at a person or a printed road photo). Boxes appear on the road camera panel. Wait for "Computer vision detected a road hazard — seen in 2 recent frames". Explain smoothing. |
| 3:30 | dialog | Show the annotated evidence frame and GPS; say "confirm" (voice) or click **Confirm & upload**. |
| 4:00 | Active trip | Banner: route re-scored; the affected route's road risk rose; **Switch route** if a different one is recommended. Hazard pin on the map. |
| 4:45 | **Evaluation** | Headline metrics, confusion matrix (diagonal = correct), optimisation table E0 → ★, CLAHE ablation, speed chart, error gallery. |
| 6:15 | **Evaluation → Limitations** | Name two failure cases from the gallery honestly. End. |

## If something fails

| Problem | Do this |
| --- | --- |
| Backend not reachable | Pages say so clearly; restart `scripts/start.ps1`. Meanwhile present screenshots. |
| Recorded drive missing | Use the webcam in the trip and point it at a printed pothole photo. |
| Webcam blocked | Use **Analyse recorded drive**; it runs the same detector. |
| No internet | Route planning is unavailable. Show the Results slide and the Evaluation page (works offline), then the trip from screenshots. |
| Hazard confirmed but routes unchanged | The GPS position is not within 75 m of the route (or location was blocked). Say so honestly; the message on screen explains it. |

## Demo video

Best: record 20–40 s of a local road with a phone held at dashboard height (landscape), then

```bash
python ml/scripts/make_demo_video.py --video my_drive.mp4 --start 3 --duration 30
```

Without a recording, make a slideshow from held-out **test** images (never used in training):

```bash
python ml/scripts/make_demo_video.py --images ml/data/aniroute/test/images --count 20
```

Free stock road footage (for example from Pexels, whose licence allows free use) also works; note the
source in `backend/samples/samples.json` (the script writes the file name for you).
