# AniRoute

AniRoute is a mobile-first farm-to-market delivery planner for farmers, cooperatives, traders, and agricultural transporters. It opens directly into trip planning and route comparison. There is no landing, login, or marketing page.

The frontend is implemented with Vue 3, TypeScript, Vite, Tailwind CSS, shadcn-vue style local components backed by Reka UI, Vue Router, Lucide icons, and MapLibre GL. The included FastAPI service provides a runnable demo API so the route and hazard flows can be exercised end to end.

> **Demo data:** the included routes, map lines, road notes, weather/flood information, and risk levels are sample data. They are not real turn-by-turn directions or safety advice, and risk levels are not spoilage predictions.

## Requirements

- Node.js 22.12 or newer and npm
- Python 3.10 or newer
- A modern browser. Camera and location permission require `localhost` or HTTPS.

## Install and run

From the extracted project root:

```bash
npm ci
cp .env.example .env
```

Start the FastAPI demo in one terminal:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

On Windows PowerShell, use the Python launcher and the virtual environment directly:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

If `python3` opens the Microsoft Store or says Python was not found, Windows is resolving the disabled App Execution Alias. Use `py -3`, `python`, or the explicit `.venv\Scripts\python.exe` commands above instead. Copy the settings file with `Copy-Item .env.example .env` before starting the frontend.

Start the frontend in another terminal:

```bash
npm run dev
```

Open the Vite address shown in the terminal, usually `http://localhost:5173`. The API health check and interactive API docs are at `http://127.0.0.1:8000/api/health` and `http://127.0.0.1:8000/docs`.

Use the **Demo / Live** switch in the header to choose the integration boundary. Demo mode uses local mock routes, local location suggestions, automatic hardcoded camera findings, and browser-only confirmations without making backend requests. Live mode calls the configured backend only; if a service is unavailable or still returns demo data, the UI shows an explicit integration error and does not fall back to mock data.

## Configure the backend and map

Copy `.env.example` to `.env` and edit the public frontend settings:

| Variable | Purpose |
| --- | --- |
| `VITE_API_BASE_URL` | FastAPI base URL, default `http://127.0.0.1:8000` |
| `VITE_CARTO_BASEMAP_KEY` | Public CARTO basemap key used for Voyager raster tiles; `NEXT_PUBLIC_CARTO_BASEMAP_KEY` is also accepted |
| `VITE_MAP_STYLE_URL` | Optional public MapLibre style URL; blank uses the keyed CARTO Voyager raster basemap with OpenStreetMap attribution |
| `VITE_API_ROUTES_PATH` | Route calculation endpoint path |
| `VITE_API_RECALCULATE_PATH` | Route recheck endpoint path |
| `VITE_API_SCAN_START_PATH` | Start hazard scanner endpoint path |
| `VITE_API_SCAN_STOP_PATH` | Stop hazard scanner endpoint path |
| `VITE_API_SCAN_FRAME_PATH` | Submit a compressed camera frame for model inference while active |
| `VITE_API_HAZARD_CONFIRM_PATH` | Confirm and save a road finding endpoint path |
| `VITE_API_HEALTH_PATH` | API health endpoint path |
| `VITE_API_GEOCODE_PATH` | Location suggestion endpoint path |

The CARTO basemap key is intended for browser tile requests; keep private tokens and credentials on a backend. The empty map uses a keyed CARTO Voyager raster basemap centered over the Philippines with a tilted 3D presentation, visible CARTO and OpenStreetMap contributor attribution, and no invented pickup/delivery points. After a location is selected, draggable route overlays are positioned around the selected coordinates. A custom vector style can still be supplied through `VITE_MAP_STYLE_URL`. For deployment, restrict the public key to the app's domains in CARTO and configure a tile/geocoding provider suitable for expected traffic.

The API accepts `CORS_ORIGINS` as a comma-separated environment variable. Its default allows Vite on `localhost:5173` and `127.0.0.1:5173`. Set `ANIROUTE_DATA_DIR` on the API process to change where the demo JSONL records and evidence frames are saved.

## Try the main flow

1. The planner opens with zero crop types and delivery points plus a selectable vehicle, including Motorcycle / Habal-habal. Enter `2` crop types to get two crop-name/quantity rows, then enter the number of delivery points to get one searchable field per stop.
2. In Demo mode, type a pickup farm or delivery point and choose a local sample suggestion. In Live mode, suggestions come from the backend and an unavailable service is shown as an error. Select **Find routes** to refresh the route estimates; Demo uses illustrative lines, while Live requires a real routing response. With multiple stops, the map labels the pickup A and deliveries B, C, D, and so on.
3. Compare **Optimal**, **Safer**, and **Fastest** choices. Select a card to highlight it on the map, then choose **Use this route**.
4. On the active route, allow camera and location access if available. Camera access is requested only after the route starts. The app says clearly when either permission is unavailable.
5. In Demo mode, the camera automatically shows a simulated finding; click it to review the captured frame. **Not now** dismisses it without sending anything. **Confirm & upload** saves the simulated finding locally in the browser and asks the local demo route logic to recheck the route. In Live mode, the camera can request the real scanner contract, but no sample finding is shown; unavailable or demo-only backend capabilities are shown as errors.
6. If the recheck changes the recommendation, choose whether to switch routes. **End route** stops the camera stream and geolocation watcher.

No location is guessed when the browser cannot provide GPS. A confirmed finding may then be saved without coordinates, with the missing location shown in the confirmation.

## API connection

The frontend calls these configurable paths by default:

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/health` | Demo API and capability status |
| `GET` | `/api/geocode/search` | Proxy location suggestions through the backend |
| `POST` | `/api/routes/calculate` | Return the three route categories for a trip |
| `POST` | `/api/routes/recalculate` | Recheck options after a confirmed hazard |
| `POST` | `/api/hazards/scanning/start` | Start the route-bound detection session contract |
| `POST` | `/api/hazards/scan-frame` | Future contract for sending a compressed still to an available model |
| `POST` | `/api/hazards/confirm` | Save a user-confirmed finding and optional evidence frame |
| `POST` | `/api/hazards/scanning/stop` | Stop a route-bound detection session |

The demo API deliberately returns `detection_available: false`; the active trip displays that live computer vision is not connected. The current automatic camera finding is frontend-only. Scanner adapters and live confirmation paths are kept ready for the backend work listed in [needtoimplement.md](needtoimplement.md).

## Tests and production build

```bash
npm run typecheck
npm test
source .venv/bin/activate
npm run test:api
npm run build
```

In Windows PowerShell, run backend tests with `& .\.venv\Scripts\python.exe -m pytest -q backend/tests`, or activate with `.venv\Scripts\Activate.ps1` first. To target an API on a different address for the HTTP integration test, set `ANIROUTE_API_URL` before running `npm run test:integration`.

For the HTTP integration test, keep the FastAPI server running in another terminal, then run:

```bash
npm run test:integration
```

The integration test exercises route generation, scanner state, confirmed hazard storage, and route recalculation over HTTP. The production files are generated in `dist/` by `npm run build`.

## Project structure

```text
src/                Vue screens, components, typed API adapters, and demo data
backend/            FastAPI demo backend and API tests
tests/integration/  HTTP integration check for a running API
docs/               Copy of the implementation brief used for the requirement audit
features.md         Implemented frontend features and spec audit
needtoimplement.md  Backend and production work still required
```
"# AniRoute" 
