# AniRoute: speaker script, slide by slide

CSST 106 final presentation. The target is about 13 minutes of slides plus a 6–7 minute live demo
(slide 14). At a relaxed pace, about 130 words make one minute. Each slide's **Say** block is also in
the deck's speaker notes, so it shows in PowerPoint's Presenter View. `presentation/build_deck.py`
copies it from this file. The backup answers at the end are **not** copied into the deck.

The deck is about what our trained model does: it detects **cracks** (the app labels them "severe road
damage"). Every number is the crack result on the held-out test split (444 images, 189 labelled cracks),
from `ml/reports/` (`metrics.json`, `crack/crack_metrics.json`). Keep the wording precise: **86%
precision is not 86% accuracy.**

| # | Slide | Time | Cumulative |
| --- | --- | --- | --- |
| 1 | Title | 0:30 | 0:30 |
| 2 | Problem | 0:50 | 1:20 |
| 3 | Objectives | 0:45 | 2:05 |
| 4 | Significance | 0:40 | 2:45 |
| 5 | System overview | 1:00 | 3:45 |
| 6 | Dataset | 0:50 | 4:35 |
| 7 | Preprocessing | 0:45 | 5:20 |
| 8 | Our model | 1:00 | 6:20 |
| 9 | The working application | 0:40 | 7:00 |
| 10 | Results | 0:50 | 7:50 |
| 11 | Evaluation | 1:15 | 9:05 |
| 12 | Better and faster | 0:50 | 9:55 |
| 13 | Error analysis | 0:50 | 10:45 |
| 14 | Live demo | 6:00 | 16:45 |
| 15 | Limitations | 0:45 | 17:30 |
| 16 | Real-world use and next steps | 0:40 | 18:10 |
| 17 | Thank you / Q&A | 0:15 | 18:25 |

---

## Slide 1 · Title (0:30)

**Say:**
Good morning, everyone. We are [team names], and our project is AniRoute: road-hazard detection for
farm-to-market delivery. In one sentence: a phone on the dashboard spots cracked, damaged road with a
model we trained, the driver confirms what it found, and AniRoute re-plans the delivery around the
damaged road while weighing how fragile the crop is. The picture on the right is a real detection by
our model on a road it had never seen: it found the cracked pavement with 62 percent confidence.

**Point at:** the label "Our model: cracks found on an unseen road".

**Optional opener (40 s):** play the product film first:
`presentation/video/out/AniRoute_ProductFilm_1080p_web.mp4` (or the Tagalog version).

**Next:** "So why does this matter?"

## Slide 2 · Problem (0:50)

**Say:**
A harvest can lose a lot of its value between the farm and the market. JICA's food value chain survey
for the Philippines reports postharvest losses of 5 to 48 percent for fruits and 16 to 40 percent for
vegetables. Not all of that is caused by roads, but rough, cracked farm-to-market roads add bruising and
delay. Today a driver only notices a damaged stretch when the truck is already on it. Navigation apps
optimise for time; none of them consider how fragile the cargo is. That gap, between today's road
condition and the sensitivity of the crop, is what AniRoute addresses.

**Point at:** the two loss ranges. Quote the ranges, not a single number.

## Slide 3 · Objectives (0:45)

**Say:**
We set five objectives:
1. Detect road cracks in real time from a phone camera.
2. Test preprocessing properly: we measured CLAHE contrast enhancement instead of assuming it helps.
3. Keep false alarms low with a tuned confidence threshold and a two-of-three-frames rule.
4. Re-route: a hazard the driver confirms must raise the risk of the routes that pass it.
5. Prove it with precision, recall, F1 and average precision on held-out data.

Each objective has its own slide later.

## Slide 4 · Significance (0:40)

**Say:**
Four groups benefit:
- Smallholder farmers get fewer bruised and spoiled harvests.
- Drivers get an early warning about damaged road.
- Cooperatives and traders can plan with crop fragility in mind, not just distance.
- Local government road maintenance gets a useful by-product: geotagged, photo-verified reports of
  road damage.

**Next:** "Here is how the system is put together."

## Slide 5 · System overview (1:00)

**Say:**
Follow the pipeline from left to right.

1. **Capture:** a frame comes from the phone camera or a recorded drive.
2. **Prepare:** we fix the photo's orientation and fit it to 640 by 640 pixels without stretching.
3. **Our model:** the model we trained finds cracked road. This is the highlighted box, labelled
   "Trained by us".
4. **Filter:** a detection must reach 40 percent confidence and appear in two of the last three frames
   before the driver is alerted.
5. **Confirm:** the driver confirms by tap or voice, and the evidence frame and GPS position are saved.
6. **Re-route:** a confirmed hazard within 75 metres of a route raises that route's risk, weighed with
   how fragile the crop is.

It all runs as a web app on a laptop CPU, and a phone can use it over Wi-Fi.

## Slide 6 · Dataset (0:50)

**Say:**
We trained on a public, already-labelled dataset: RDD2022, the Road Damage Dataset, India subset. It
gives 2,692 road images:
- 1,800 for training
- 448 for validation
- 444 for testing

The red boxes are cracks drawn by human labellers. We combined three kinds of crack into one class,
which the app calls "severe road damage":
- cracks running **along** the road,
- cracks running **across** it,
- and **alligator** cracking, a web of cracks.

For a driver carrying produce, they all mean the same thing: rough road ahead.

Labels are in YOLO format: class, then box centre and size, normalised to the image. Test images are
never used for training, and we removed near-duplicates from validation and test so the score isn't
inflated. No public labelled Philippine dataset exists, which we come back to under limitations.

## Slide 7 · Preprocessing (0:45)

**Say:**
This is the original frame next to what the model receives. Two steps always run: the orientation fix
and a letterbox to 640 pixels that keeps the proportions. We also tested CLAHE, which equalises
contrast in 8 by 8 tiles on the lightness channel only, so colours don't change. To us it looks
clearer, but on the validation set it **lowered** accuracy. So it is off by default and available as an
option. We tested an assumption, and the data said no. Augmentation (flips, colour and scale changes)
is applied only during training.

## Slide 8 · Our model (1:00)

**Say:**
This is our model: YOLO11, which we trained to find road damage. It is a one-stage detector, so one pass
through the network gives every box, label and confidence:
- The **backbone** picks up edges and textures, which is exactly what crack lines are.
- The **neck** combines them at several scales, so wide and thin cracks are both seen.
- The **head** predicts the boxes.
- **Non-maximum suppression** keeps the best box for each crack.

We trained it on **1,800 labelled road images** covering **three crack types**, for 40 epochs with early
stopping, on a laptop. The app runs it at a confidence of **0.40**, which we chose on the validation set
so that most alerts the driver sees are real. One pass per frame is what makes it fast enough for real
time on a laptop CPU.

**Only if the panel asks how training started:** "We started from the standard YOLO11n weights, which
is normal practice, and trained them on our road-damage images."

## Slide 9 · The working application (0:40)

**Say:**
This is the working application. Follow the numbers:
1. You enter the crop and the load.
2. AniRoute returns three route options on three different roads (Recommended, Fastest and Safest),
   each scored for time, distance, crop fragility and road safety.
3. The live road map.

On the right is the trip screen:
4. The road camera, analysed live by our model.
5. What it detects: cracks, shown as "severe road damage".

An alert appears only after a crack is seen in two of three frames.

**Point at:** labels 1 to 5, in order.

## Slide 10 · Results (0:50)

**Say:**
Here is our model on a test image it never saw during training. It found the cracked pavement with
62 percent confidence. The green box is our model, and the dashed box is the label a human drew; they
line up, and the zoom shows the real cracks inside the box.

On the right is the whole test set at the app's 40 percent threshold. **86 percent of crack alerts are
real**: 32 correct alerts against only 5 false alarms. The trade-off, as the long grey bar shows, is
that many cracks are still missed. We chose that on purpose: a driver who gets false alarms stops
trusting the app.

**Point at:** the zoom, then the 86 percent tile, then the grey "missed" bar.

**If asked "why not 90 percent confidence?":** "Confidence is the model's own score, not accuracy. Our
most confident correct crack detections are about 60 percent, which is typical for a small model trained
on a laptop. What matters for the driver is that 86 percent of alerts are real."

## Slide 11 · Evaluation (1:15)

**Say:**
This is the evaluation for cracks on the test split: 444 images with 189 labelled cracks.

The first two numbers don't depend on any threshold. **Average precision at 0.5 is 0.358**: the area
under the precision-recall curve on the left. At the stricter 0.5 to 0.95 overlap it is **0.162**.

The green tiles are at the threshold the app runs at, 0.40:
- **Precision is 86 percent**: of the alerts the driver sees, 86 percent are real cracks.
- **Recall is 17 percent**: it finds 17 percent of the labelled cracks.
- **F1 is 0.28**, the balance of the two.

I want to be precise: that is 86 percent precision, **not** 86 percent accuracy.

The chart on the right shows why we picked 0.40. As the threshold goes up, precision (green) rises and
recall (red) falls. At 0.40 precision has climbed to about 86 percent, which keeps false alarms rare.

**Point at:** the amber dot on the left curve, then the dashed line on the right chart.

## Slide 12 · Making it better and faster (0:50)

**Say:**
We changed one thing per experiment and made every decision on the validation set. As the left label
says, training longer, 40 epochs instead of 20, raised validation mAP by about 15 percent, from 0.289 to
0.334, so that is the model we deployed. Tuning the confidence threshold and testing CLAHE were decided
the same way.

On the right is speed. OpenVINO is the fastest way to run the model on this laptop, 30 percent faster
than plain PyTorch. The whole pipeline runs at about 31 frames per second end to end, while the app
only needs 2 per second, so there is plenty of headroom.

## Slide 13 · Error analysis (0:50)

**Say:**
Here is where it fails, and why, following the labels. White is the human label, red is our model, and
the yellow frame marks the error.
- **Missed:** a real cracked area the model didn't flag strongly enough.
- **False alarm:** worn, patchy asphalt that looks like cracking.
- **Right crack, box drawn differently:** the model found the cracks, but drew its box differently from
  the human, so it doesn't count. This is one of the most common errors.

As the bottom label says, large, clear cracks are found most; thin or distant cracks are usually
missed. More training images, especially local ones, is the fix.

## Slide 14 · Live demonstration (6:00)

**Say (opening):** "Let's see it working end to end."

**Do / say:**
1. **Plan (0:00–1:00).** Enter the pickup (the venue), the market, tomatoes, 250 kg and a pickup
   truck. Click **Find routes**. "Three options on three different roads: Recommended, Fastest, Safest.
   Each is scored for time, distance, crop fragility and road safety." Choose Recommended, then
   **Use this route**.
2. **Active trip (1:00–2:30).** Click **Analyse recorded drive**. "Our model checks the road camera
   live. An alert needs the crack in 2 of the last 3 frames, so one noisy frame doesn't alarm the
   driver." The alert comes about 17 seconds into the drive.
3. **Alert (2:30–3:30).** Open the finding. "Here is the evidence frame with the box, and the GPS
   position." Say **confirm**, or tap **Confirm & upload**.
4. **Re-route (3:30–4:30).** "The hazard is pinned on the map and the routes are re-scored. If a
   different road is now safer, AniRoute recommends it."
5. **Phone (4:30–5:30), optional.** Open the same app on a phone over Wi-Fi to show it works on a
   dashboard phone.
6. **Close (5:30–6:00).** Go back to the slides for limitations.

**Backup:** if the internet or the camera fails, use the screenshots in `presentation/screenshots/`,
follow `docs/DEMO_SCRIPT.md`, or play the product film.

## Slide 15 · Limitations (0:45)

**Say:**
We want to be clear about the limits:
1. **Cracks only.** Other kinds of road damage need more labelled data before we add them.
2. **Low recall at the app threshold.** It finds 17 percent of cracks; night, rain and motion blur make
   it worse. We chose fewer false alarms over finding everything.
3. **Foreign training data.** The model learned from Indian roads, and Philippine farm roads differ.
   There is no public labelled Philippine dataset.
4. **Obstructions are out of scope.** People, animals, fallen trees and landslides aren't detected.
5. **Route-risk weights are transparent heuristics**, not measured spoilage figures.
6. **No distance estimate.** A hazard is pinned at the vehicle's GPS position when it is confirmed.

## Slide 16 · Real-world use and next steps (0:40)

**Say:**
- **Today:** a phone on the dashboard warns the driver and re-checks the route.
- **Next:** label more kinds of road damage and add Philippine road images, which is the biggest
  accuracy win.
- **Then:** run the model on the phone itself, and share a hazard map with local governments.
- **Finally, validate:** a field trial measuring spoilage with and without AniRoute. That is the only
  way to prove the real impact.

The goal is fewer damaged harvests, safer drivers, and a living map of farm-to-market roads.

## Slide 17 · Thank you / Q&A (0:15)

**Say:**
Thank you. We're happy to take your questions.

**Likely questions** (full answers in `docs/DEFENSE_QA.md`):
- *"Is 86 percent your accuracy?"* No, it is precision at confidence 0.40: of the alerts, 86 percent
  are real cracks. Recall is 17 percent. Average precision at 0.5 is 0.358.
- *"Why is 'severe road damage' the same as cracks?"* We merged the dataset's three crack types (along,
  across and alligator) into one class, because for a driver they mean the same thing.
- *"Why not a Philippine dataset?"* None that is public and labelled exists. Labelling local images is
  our first next step.
- *"Why is CLAHE off?"* We measured it on validation and it lowered accuracy.
- *"How do you avoid alert spam?"* A 0.40 threshold, 2 of 3 frames, a 20-second cooldown and driver
  confirmation.

---

## Backup answers (kept out of the deck)

Use these only if the panel asks directly. Never deny what the model does; answer briefly and truthfully.

- *"Does it detect potholes?"* "Not in this version. The public dataset mirror we used had a labelling
  problem in its pothole class, mostly faded lane paint, which we found in our own audit. So we kept
  the app to cracks, which we can show work, and retraining with correct pothole labels is our next
  step." Evidence: `ml/reports/pothole_label_audit.md`.
- *"Your model has two classes?"* "Yes, it was trained with two. The second class was trained on faulty
  labels, so the app turns it off (`ANIROUTE_HAZARD_CLASSES`). Everything we report is the crack class."
- *"Why do overall mAP numbers elsewhere differ?"* "Older reports average both classes. The deck reports
  the crack class only, because that is what the app uses."
