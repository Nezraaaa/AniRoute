# Demonstration script (8 minutes, with backups)

## Before the panel (15 minutes earlier)

- [ ] Laptop on power, notifications off, browser zoom 100%, close other heavy apps.
- [ ] `scripts/start.ps1` running; open <http://127.0.0.1:5173>. Wait until **Vision Lab** shows
      Model A and Model B as *loaded*.
- [ ] Header badge says **Detector online**. `backend/samples/demo_drive.webm` exists (see "Demo video" below).
- [ ] **Internet is on** (route planning uses OSRM and OpenStreetMap search; map tiles load online).
- [ ] **Allow location** in the browser and check that the trip page says *Vehicle GPS is pinned*.
- [ ] **Plan the demo trip from the venue**: set the pickup point to the school/building you present in,
      so the laptop's GPS position lies on the route. A confirmed hazard only changes route scores when
      its GPS position is within 75 m of a route. Do a full rehearsal at the venue beforehand.
- [ ] Open tabs: Plan, Vision Lab, Evaluation, About. Pre-load one sample image in Vision Lab.
- [ ] Backup: `presentation/screenshots/` and a screen recording of this script on a USB stick.

## Script

| Time | Screen | Say / do |
| --- | --- | --- |
| 0:00 | **Vision Lab → Image** | "This is the detector on its own." Click a held-out **test** image. Point at boxes, class, confidence, and the *Model A / Model B* column. |
| 0:45 | same | Drag the **confidence slider** down then up: "the threshold trades false alarms for misses — we chose ours at the F1 peak on the validation set." |
| 1:15 | same, scroll | **Preprocessing step by step**: original → CLAHE → 640×640 model input. Switch CLAHE **Off → Auto → On** on a dark image: it looks brighter to us, but the ablation showed the model does worse, which is why it is off by default. |
| 2:00 | **Vision Lab → Video** | Play the demo drive. Boxes follow the road; per-class counts and the timeline fill in; the badge shows real analysed FPS. |
| 3:00 | **Vision Lab → Webcam** *(optional)* | Point the webcam at a printed pothole photo or a person walking in front: obstruction box appears only inside the purple driving corridor. |
| 3:30 | **Plan** | Pickup = the venue, delivery = a nearby market; tomatoes, 250 kg, small truck. Live route options with crop-risk scores. Choose the recommended route → **Use this route**. |
| 4:15 | **Active trip** | Click **Analyse recorded drive** (or point the webcam at a person or a printed road photo). Boxes appear on the road camera panel. Wait for "Computer vision detected a road hazard — seen in 2 recent frames". Explain smoothing. |
| 5:00 | dialog | Show the annotated evidence frame and GPS; say "confirm" (voice) or click **Confirm & upload**. |
| 5:30 | Active trip | Banner: route re-scored; the affected route's road risk rose; **Switch route** if a different one is recommended. Hazard pin on the map. |
| 6:15 | **Evaluation** | Headline metrics, confusion matrix (diagonal = correct), optimisation table E0 → ★, CLAHE ablation, speed chart, error gallery. |
| 7:30 | **Evaluation → Limitations** | Name two failure cases from the gallery honestly. End. |

## If something fails

| Problem | Do this |
| --- | --- |
| Backend not reachable | Pages say so clearly; restart `scripts/start.ps1`. Meanwhile present screenshots. |
| Recorded drive missing | Use the webcam in the trip (a person walking in front of it is an obstruction), or show the Vision Lab video tab. |
| Webcam blocked | Use **Analyse recorded drive**; the Vision Lab video tab shows the same detector. |
| No internet | Route planning is unavailable. Show the Vision Lab (works offline) and the Evaluation page, then the trip from screenshots. |
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
