# Backend work still required

This is the backend-only backlog for AniRoute. The frontend demo flow is intentionally usable without these services: it uses local sample routes, hardcoded simulated camera findings, browser-local confirmation, and clearly labeled sample risk information. The FastAPI project provides a runnable contract and demo storage, but it is not yet a production routing, computer-vision, or road-risk platform.

## Current integration boundary

- Demo mode does not require the API for route calculation or simulated hazard confirmation.
- Live route calculation calls the configured API only. The frontend rejects responses marked as demo data and shows an integration error until a real routing engine is connected.
- The active camera demonstrates automatic simulated findings only in Demo mode. Live mode calls the scanner contract without creating sample findings; unavailable or demo-only capability is shown as an error.
- A future non-simulated hazard can use the existing confirmation and recheck adapters once the backend returns real detections and accepts production observations.
- The original frontend/product brief remains in [docs/aniroute_frontend_implementation_spec.md](docs/aniroute_frontend_implementation_spec.md). This file should stay focused on backend implementation and operations.

## Required backend implementation

| Priority | Backend work | Current demo behavior | Required follow-up |
| --- | --- | --- | --- |
| P0 | Road-network route calculation | `makeDemoRoutes` returns three fixed illustrative LineStrings for one corridor; the frontend only repositions them around selected points | Connect OSM/OSMnx or another licensed road graph with NetworkX and Dijkstra/A*. Return real geometry, ETA, distance, road segments, vehicle constraints, source timestamps, and a stable route ID. |
| P0 | Live camera computer vision | Scanner start reports `detection_available: false`; scan-frame returns no detection | Connect YOLO or another validated model. Add confidence thresholds, hazard classes, cooldown/deduplication, event IDs, road-segment matching, timestamps, optional bounding boxes, and model-health tests. |
| P0 | Persistent geospatial road-risk storage | Browser demo confirmations stay local; direct API confirmations append metadata to local JSONL and may save an evidence image under `backend/data/` | Move observations, route segments, and hazard coordinates to PostgreSQL/PostGIS. Add migrations, retention, ownership/access controls, backups, and secure object storage for approved evidence. |
| P1 | Real road-condition and hazard data | Qualitative sample road summaries and sample risk notes | Ingest verified road conditions, closures, obstructions, potholes, and flood-risk records. Store source, observation time, confidence, geometry, and expiry. |
| P1 | Weather, flood, and temperature feeds | Static sample weather/flood/temperature text | Integrate and normalize suitable PAGASA and Philippine flood/hazard sources. Define freshness, provider failures, rate limits, and fallback behavior. |
| P1 | Crop-aware scoring | Small deterministic crop/load adjustments for sample output | Define explainable scoring for travel time, distance, road risk, flood/weather, temperature, crop sensitivity, and load. Validate the weights with agronomy and transport data before presenting operational recommendations. |
| P1 | Route recheck after a confirmed event | Demo logic deterministically changes the recommendation after a simulated confirmation | Recalculate against updated route-segment risk and return changed recommendation, reasons, geometry, current-route usability, and source timestamps. |
| P1 | Production geocoding and address resolution | Demo uses local sample suggestions; Live uses backend-proxied Nominatim suggestions and reports failures | Select a provider or self-hosted service, configure quotas and caching, handle rural landmarks and ambiguous matches, and apply privacy/rate-limit controls. |
| P2 | Live trip progress and turn-by-turn guidance | Active trip shows a sample direction and starting ETA/distance | Match GPS to real route geometry, calculate remaining time/distance, and return validated next-turn instructions. |
| P2 | API security and production deployment | No authentication; CORS defaults to local Vite origins; demo uploads are lightly validated | Deploy over HTTPS, configure strict origins, rate limits, authentication/authorization when needed, upload scanning, consent/privacy retention, secrets management, monitoring, and backups. |
| P2 | Map tile and geocoding operations | Keyed CARTO Voyager tiles and backend-proxied Nominatim are used for local development | Confirm production providers, capacity, attribution, usage terms, domain restrictions, and server-side token handling where required. |
| P2 | Scientific and operational validation | No calibrated spoilage, freshness, or safety claim is made | Run field trials across crops, vehicles, seasons, weather, and road conditions before publishing calibrated loss, freshness, or safety predictions. |

## Implemented demo API contract

- `GET /api/health` reports API availability and explicitly reports unavailable live route/model services.
- `POST /api/routes/calculate` accepts a `TripInput` and returns three route categories plus a recommended route ID. The current response is sample data.
- `POST /api/routes/recalculate` accepts a confirmed hazard reference and returns sample rechecked routes. Replace the deterministic logic when real route-risk data exists.
- `GET /api/geocode/search` proxies OpenStreetMap/Nominatim place suggestions for pickup and delivery fields.
- `POST /api/hazards/scanning/start` returns scanner capability. The demo reports that detection is unavailable.
- `POST /api/hazards/scan-frame` is the future frame-inference contract; the demo returns no detection and does not persist scan frames.
- `POST /api/hazards/scanning/stop` closes the future route-bound scanner session contract.
- `POST /api/hazards/confirm` accepts an explicitly confirmed observation, validates optional coordinate pairs and image size/type, and stores it locally when called.

## Backend acceptance checklist

- Keep the JSON field names consumed by `src/services/routes.ts` and `src/services/hazards.ts`, or update the typed adapters and tests together.
- Route requests already carry the repeatable `cropLoads` and `deliveryPoints` fields; the production route engine must use every delivery point in order and return geometry that covers all stops.
- Return real source and freshness metadata for route, hazard, weather, and risk responses.
- Never report `detection_available: true` until the model service is healthy and returning validated detections.
- Keep confirmation idempotent so retries cannot duplicate the same observation.
- Validate and limit camera-frame payloads before storage or model inference.
- Do not put API secrets in frontend code. Public map configuration may remain in the frontend only when the provider allows it.
