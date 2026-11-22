# AniRoute frontend

Vue 3 + Vite + TypeScript web app for AniRoute: crop-aware route planning with real-time road-hazard
detection. Start the backend first (`uvicorn backend.main:app` from the repository root, or
`scripts/start.ps1`).

```sh
npm ci
cp .env.example .env
npm run dev
```

Pages:

- **Plan** — trip details (crops, load, vehicle, pickup and delivery points with OpenStreetMap search);
  live route options from OSRM scored for crop sensitivity and camera-confirmed road hazards.
- **Active trip** — the camera (or a recorded drive) is analysed by the backend detector; hazards seen in
  2 of 3 frames are shown to the driver, confirmed with GPS and evidence, and routes are re-scored.
- **Vision Lab** — run the detector on images, video and the webcam; preprocessing stages; threshold and
  CLAHE controls.
- **Evaluation** — metrics, confusion matrix, curves, optimisation table and error analysis from
  `ml/reports/`.
- **About** — problem, objectives, architecture, how the detector works, limitations.

All data comes from the backend; route planning needs an internet connection. Risk scores are a guide,
not turn-by-turn directions, safety advice or calibrated spoilage predictions.

Checks:

```sh
npm run typecheck
npm test
npm run build
npm run test:integration   # backend running
npm run screenshots        # backend + dev server running
```
