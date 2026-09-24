# AniRoute

AniRoute is a crop-aware agricultural transport optimizer prepared as a self-contained hackathon presentation. The Vue application runs entirely in the browser and does not require FastAPI.

## Run the presentation

```sh
cd frontend
npm ci
cp .env.example .env
npm run dev
```

Open the address printed by Vite, usually `http://localhost:5173`.

The opening screen is already populated with a 250 kg tomato shipment from Baguio to Calamba. It presents three routes with travel time, distance, road condition, flood and weather exposure, temperature exposure, a numeric Crop Transport Risk Score, and an explanation tied to the selected crop.

Choose **Use this route** to open the active trip. The road-analysis presentation starts automatically, identifies a road finding, attaches its location, and asks for confirmation. Confirming the observation increases the affected segment's road-risk factor and recalculates the recommendation.

All route, weather, hazard, and risk values are illustrative presentation data. The risk score is interpretable and is not a spoilage percentage or safety guarantee.

## Project areas

| Area | Location |
| --- | --- |
| Presentation scenario and crop profiles | `frontend/src/data/presentation.ts` |
| Route planning | `frontend/src/pages/PlanPage.vue` |
| Active trip and road analysis | `frontend/src/pages/ActiveTripPage.vue` |
| Risk score presentation | `frontend/src/components/routes/RouteOptionCard.vue` |
| Interactive map | `frontend/src/components/routes/RouteMap.vue` |
| Future API contract | `backend/main.py` |

## Automated checks

```sh
cd frontend
npm run typecheck
npm run build
```

Production integrations planned after the hackathon are listed in [frontend/needtoimplement.md](frontend/needtoimplement.md).
