# AniRoute frontend features

This is the current frontend implementation record for AniRoute. It describes what is in `src/` today, while the approved product requirements remain in [docs/aniroute_frontend_implementation_spec.md](docs/aniroute_frontend_implementation_spec.md).

Source-of-truth boundaries:

- Current behavior is defined by the Vue/TypeScript source and its tests.
- This file records the implemented frontend behavior; it does not replace the original product brief.
- Backend work that is still required is tracked in [needtoimplement.md](needtoimplement.md).
- There is no `PRODUCT.md` in this project. Creating one is optional documentation work, not a prerequisite for the current implementation.

## Product shell and branding

- The app opens directly on the route-planning screen. There is no landing page, login, sign-up, pricing, marketing, analytics, fleet, or admin page.
- The header includes the horizontal AniRoute logo lockup and a Demo/Live data-mode switch.
- The icon-only AniRoute mark is used as the browser favicon in `public/aniroute-icon.png`.
- Browser titles are route-aware: `AniRoute | Plan a delivery` and `AniRoute | Active trip`.
- The default mode is Demo. Live mode is a separate frontend path for future or available API integration.

## Delivery planning

- The planner starts with zero crop types and zero delivery points plus a selectable vehicle. Entering a crop count creates one crop-name and quantity row per crop; entering a delivery-point count creates one searchable location row per stop.
- Crop rows, vehicle, pickup, and delivery fields have visible labels and inline validation. The current crop and destination summaries are derived from the repeatable rows before the route adapter is called.
- Pickup and delivery search provides debounced location suggestions through the backend geocoding adapter, with local sample fallbacks for the demo.
- Selecting a location stores its coordinates and places a draggable A/B pin on the map. Clearing a field also clears its map coordinate.
- **Find routes** validates the trip and calls the typed route adapter. Demo mode uses deterministic local sample routes only; Live mode calls the configured API only and shows an explicit error when the backend is unavailable or returns demo data.
- **Edit trip** returns focus to the delivery details.

## Route comparison and map

- Optimal, Safer, and Fastest options are shown together. Optimal is initially recommended; alternatives remain selectable.
- Route cards show sample time, distance, road condition, weather/flood note, temperature exposure, relative crop transport risk, and a plain-language explanation.
- Each route has a large **Use this route** action. Selecting a card highlights its line on the map.
- Duplicate route geometry is grouped into one displayed option with category badges.
- MapLibre uses the keyed CARTO Voyager raster basemap with CARTO and OpenStreetMap attribution. The empty state is centered over the Philippines with a pitched 3D presentation so the Luzon-Visayas-Mindanao region is visible.
- The map no longer defaults to Mindanao, creates A/B pins, or draws the sample route corridor before a pickup or delivery coordinate is selected.
- Once a location is selected, the illustrative route lines are repositioned around the selected coordinate pair. The A/B pins can be dragged to update the endpoints.
- The map header has no CARTO Voyager badge. The Ctrl+scroll cooperative-gesture prompt is disabled.
- The map displays route line colors, navigation controls, selected-route emphasis, a clean empty state, and a map-unavailable fallback. Sample road-note pins and the road-note legend item are not rendered on the map.
- Route geometry and risk values remain illustrative until a real road-routing and risk service is connected.

## Active route and road camera

- Starting a route opens an active-trip view with the route map, trip summary, estimate, sample next direction, road/weather summary, and **End route** action.
- Camera and geolocation are requested only after a route starts. Ending or leaving the active route stops camera tracks and geolocation watching.
- Camera states cover permission needed, active, denied, unavailable, and retry. Navigation remains usable when permissions are unavailable.
- The camera preview reflows for desktop and mobile layouts. The surrounding app remains responsive instead of becoming a full-screen portrait layout.
- Current GPS is displayed only when supplied by the browser. No location is guessed when GPS is unavailable.
- The current computer-vision flow is frontend-only and hardcoded for demonstration. In Demo mode, a sample finding appears automatically; in Live mode, no sample finding is created and the backend scanner status is shown.
- Clicking a finding captures the current frame for the confirmation dialog while keeping the live camera component mounted. After **Not now** or a successful confirmation, the next sample detection is scheduled automatically so the camera does not freeze.

## Confirmation and upload flow

- A finding opens one responsive confirmation dialog with the hazard name, captured evidence frame, detected location when available, nearby destination, and approximate sample distance.
- The dialog provides **Not now** and **Confirm & upload**. It does not add another upload form or a second submit step.
- For the current simulated finding, confirmation stays in the browser through the local demo service path and does not call the backend.
- A future non-simulated finding can pass through the Live hazard-confirmation adapter with its type, timestamp, confidence, GPS, route/segment IDs, and captured frame.
- Successful confirmation triggers the route recheck flow. Demo confirmation and recheck stay local; Live confirmation/recheck call the backend only and report unavailable integration instead of falling back.
- Failed uploads keep the dialog open with a retry action.
- The modal and camera status clearly identify simulated computer vision and the fact that live model inference is not connected.

## Interface and accessibility

- Mobile-first layout: delivery details, map, and route choices stack vertically on phones; wider screens place map and route choices side by side.
- The form, route cards, map pins, camera prompt, modal, and mode switch are touch-safe and keyboard-operable.
- Labels, focus indicators, readable contrast, live status messages, and semantic headings are included throughout the main flow.
- Route colors are paired with visible text labels. Map route notes are intentionally omitted from the map surface.
- Local UI components use the existing shadcn-vue/Reka UI style system, with Lucide icons and the project typography tokens.
- Covered states include loading, invalid fields, empty routes, map unavailable, permission denied/unavailable, missing GPS, backend offline, upload failure, and route-recheck feedback.

## Frontend integration boundary

- Typed adapters exist for `calculateRoutes`, `recalculateRoute`, `startHazardScanning`, `scanCameraFrame`, `confirmHazard`, and `stopHazardScanning`.
- API base URL and endpoint paths are configurable through `.env.example`; no API key or secret is shipped in frontend code.
- Demo route generation, simulated camera findings, simulated confirmation, and sample route rechecks are intentionally local.
- Live location search, route calculation, scanner, hazard confirmation, and route recheck use backend adapter paths only. The current bundled API identifies route/hazard outputs as demo data, so Live surfaces an integration error until production services replace them.

## Brief requirement audit

| Requirement | Status | Implementation |
| --- | --- | --- |
| Open directly to route planning | Complete | `src/router.ts`, `src/pages/PlanPage.vue` |
| Editable crop, load, vehicle, pickup, and delivery | Complete for the demo | `src/components/delivery/DeliveryForm.vue`, `src/components/delivery/LocationSearch.vue` |
| Dynamic location suggestions and draggable map points | Complete for the demo | `src/services/geocoding.ts`, `src/components/routes/RouteMap.vue` |
| Optimal, Safer, and Fastest choices together | Complete with sample route data | `src/pages/PlanPage.vue`, `src/components/routes/RouteOptionCard.vue`, `src/data/demo.ts` |
| Responsive map, route cards, and active trip | Complete | `src/components/routes/RouteMap.vue`, `src/style.css`, `src/pages/ActiveTripPage.vue` |
| Philippines-centered 3D empty map with CARTO attribution | Complete | `src/components/routes/RouteMap.vue` |
| Active-route camera and geolocation lifecycle | Complete for the demo | `src/composables/useCamera.ts`, `src/composables/useGeolocation.ts` |
| Automatic simulated detection and one confirmation | Complete for the demo | `src/pages/ActiveTripPage.vue`, `src/components/active/HazardConfirmation.vue` |
| Live model inference and real road-risk updates | Not included; backend work remains | [needtoimplement.md](needtoimplement.md) |
| Setup docs, environment template, and tests | Complete | `README.md`, `.env.example`, `backend/tests/`, `tests/integration/` |
