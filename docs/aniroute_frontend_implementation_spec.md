# AniRoute Frontend Implementation Instructions

## Implementation brief

Build a working, mobile-first frontend MVP for **AniRoute**, an AI-powered, crop-aware farm-to-market transport planner. Use the supplied **ARCgriculture - NextGen Agri Hackathon Concept Note.pdf** as the product source and follow the approved farmer-focused AniRoute UI/UX direction.

The interface is for farmers, cooperative staff, agricultural transporters, traders, and dispatchers. Many users may be unfamiliar with technical software. Keep the app calm, practical, readable outdoors, and easy to operate with one hand.

This brief covers the **frontend only**. Keep backend, route calculation, weather ingestion, database, and computer-vision model work behind clear mockable service interfaces. The current deliverable is this implementation brief; do not create a ZIP until requested separately.

## Product purpose and scope

AniRoute helps a user choose a route that protects a specific crop while balancing travel time and distance. The suggested route should explain its recommendation in plain language, such as: “This route is 8 minutes longer, but avoids the damaged road and has lower flood risk for tomatoes.”

Build only the functional MVP flow:

1. Enter or review a delivery: crop, load quantity, vehicle, origin, and market destination.
2. Generate possible routes and compare their travel time, distance, road condition, weather, flood risk, temperature exposure, and crop sensitivity.
3. Show a crop-aware recommendation and a short reason for it.
4. Let the user choose a route and start an active trip.
5. Keep the mounted smartphone camera scanning for road hazards while that route is active.
6. Ask for a quick confirmation when computer vision detects a possible hazard. Upload the confirmed hazard and its GPS location automatically after confirmation.
7. Recheck the route recommendation when the road-risk information changes.

Do not build a landing page, login, sign-up, pricing page, marketing page, generic analytics dashboard, fleet-management suite, or admin portal. Do not create a separate manual “Report road problem” flow with a photo picker, issue-type form, map-pin form, or second submit step. **The active-route camera detection and confirmation flow replaces the earlier manual report interaction.**

## Frontend technology stack

The Concept Note names Vue.js for the web interface and Leaflet or MapLibre for interactive maps. Use this compatible stack:

| Area | Use | Role |
|---|---|---|
| App framework | Vue 3 with TypeScript and Single-File Components | Build the responsive interface and view state. Use Composition API with `<script setup>`. |
| Dev/build tool | Vite | Run the frontend locally and create the production build. |
| UI components | shadcn-vue | Use shadcn-style, accessible, editable components for buttons, cards, dialogs, selects, badges, sheets, and alerts. Keep the visual system consistent and customize components as needed. |
| Styling | Tailwind CSS | Define spacing, type sizes, colors, responsive layouts, and states. |
| Maps | MapLibre GL JS with an OpenStreetMap-compatible map style | Render the route, start/end points, risk segments, and hazard pins. Keep map-style configuration outside components and show map attribution. Leaflet is an acceptable simpler substitute if the selected map provider requires it. |
| Navigation | Vue Router | Move between route planning/results and active-trip views without a full page reload. |
| Backend integration | Typed frontend service adapters for the planned Python/FastAPI API | Keep route generation, weather/flood data, road-risk data, and YOLO detection behind replaceable calls. Use clearly labelled sample data until endpoints are available. |
| Icons | Lucide Vue icons, paired with visible text labels | Provide familiar visual cues without icon-only actions. |

The Concept Note lists OSMnx/NetworkX and Dijkstra or A* for road routing, PostgreSQL + PostGIS for geospatial storage, YOLO-based computer vision, PAGASA weather information, and GeoRiskPH/HazardHunterPH, UP NOAH, or available PhilSA flood products. Those are service/data-layer responsibilities; do not recreate those systems in the browser. The frontend should display their results through the API adapter.

## Audience and visual direction

- Use plain English, short labels, familiar icons with words, and clear next steps.
- Make primary controls large and easy to tap. Target at least 44 by 44 CSS pixels for touch actions.
- Use readable type, strong text/background contrast, and generous spacing. Avoid dense data tables, long technical explanations, tiny map controls, and unexplained acronyms.
- Use a restrained farm-friendly palette: deep greens for primary actions, warm neutral backgrounds, and amber/red only for hazard attention. Keep the screen clean and practical; avoid ornamental gradients, excessive cards, and decorative dashboards.
- Make the app responsive and mobile-first. At phone widths, stack route details, map, and route cards vertically; keep the main action easy to reach. At wider widths, allow the map and route choices to sit side by side.
- **Do not rotate or crop the whole app into a portrait poster.** The app should reflow naturally for a phone screen. In a wide desktop layout, keep the overall route UI landscape. Only the mounted phone’s camera preview must use a portrait 9:16 frame.
- Keep the map legible at small sizes. Pair every colored route or hazard marker with a text label or an accessible legend so users do not have to infer meaning from color alone.

## Main screens and interactions

### 1. Route planning and results

Open directly into the useful route-planning state. For the demo, prefill an example delivery so the user can see a complete route comparison immediately, while still allowing them to edit the trip.

Provide these inputs:

- Crop type, initially tomatoes for the demo.
- Load quantity and unit, initially 250 kg for the demo.
- Vehicle type.
- Origin, such as the farm or current location.
- Destination, such as a trading post, consolidation center, or market.
- A clear **Find routes** action.

Use simple selects, numeric inputs, and location search. Validate missing or invalid values with short messages next to the relevant field. Do not require precise crop-risk configuration from the user.

After route generation, show:

- An interactive map with origin, destination, the available route lines, and known hazard/risk locations.
- Three selectable route categories in the demo: **Optimal route**, **Safer route**, and **Fastest route**. Show them together on the same results screen, like common map apps show a recommended path and alternative paths. Do not hide alternatives behind another page or make the user search for them.
- Preselect the **Optimal route** and mark it **Optimal · Best balance** or **Recommended for this load**. Explain that it balances travel time, distance, road condition, flood/weather and temperature risk, and the selected crop's sensitivity.
- Describe the **Safer route** as the option with lower known road/flood/hazard risk than the alternatives. It may be longer or slower. Do not imply that any route is completely safe.
- Describe the **Fastest route** as the option with the shortest estimated travel time. Show its known road, flood, or weather risks clearly so the user can make an informed choice.
- For every option, show estimated travel time, distance, a short road-condition summary, weather/flood concern, crop transport-risk result, and a plain-language reason for the category.
- Show every route on the map with a readable category label and legend. When the user selects a route card, highlight that route line and update the selected state. Keep all alternatives accessible on mobile; stack the cards vertically instead of hiding options in a cramped horizontal strip.
- Give every option a large **Use this route** action. Let the user choose an alternative even when it is not the system's recommendation.
- Keep an **Edit trip** action that returns to the delivery details.

For example, the demo might show:

| Option | Plain-language description |
|---|---|
| **Optimal · Best balance** | Recommended for this crop and load; balances time, distance, and transport risks. |
| **Safer route** | Lower known road and flood risks; may take longer. |
| **Fastest route** | Shortest estimated travel time; may include a higher-risk road segment. |

Treat these as route goals, not fixed guarantees. Use the category and score returned by the backend when available. If two categories resolve to the same route geometry, do not show duplicate lines/cards; show the relevant category badges on the single route option instead. Do not add toll-road choices or filters unless the backend and map data actually support them.

The Concept Note describes this cost model:

```text
Route Cost = Travel Time + Distance + Road Risk + Flood/Weather Risk
             + Temperature Risk + Crop Sensitivity
```

Use backend-provided route scores when available. For mock data, label the score as demo/sample data. Do not invent a calibrated spoilage percentage, guaranteed freshness claim, or precise loss reduction. The Concept Note says crop-risk profiles are initially manual and that scientifically calibrated spoilage prediction is future work. Explain risk in everyday terms, for example “lower road and flood risk for tomatoes.”

### 2. Active route

After **Use this route**, show a focused trip screen with:

- The selected route on the map, current location, destination, next direction, and estimated time/distance remaining.
- A compact trip summary with crop and load.
- A visible camera status: **Camera is on** / **Scanning during this route** when permission is granted.
- A small road-condition or weather summary only when it helps the current trip.
- A clear way to end the route. Ending the route stops the camera stream and hazard scanning.

Start camera access only after the user starts an active route and grants browser permission. If access is denied or unavailable, keep route navigation usable and show a simple camera status with a retry permission action. Do not imply that scanning is active when it is not.

### 3. Automatic camera hazard detection and confirmation

The smartphone mounted in the vehicle acts as a road sensor. During an active route, the camera stays active and the computer-vision service checks for these visible hazards:

- Potholes.
- Severe road damage.
- Standing water.
- Road obstructions.

When a possible hazard is detected, open a short confirmation dialog or sheet over the active route. Keep it direct and easy to understand:

- Show the detected hazard name, such as **Pothole detected ahead**.
- Show the **portrait 9:16 live camera preview** with the detected area outlined. Keep this preview portrait in both desktop and phone layouts; do not make the entire route interface portrait just to achieve this.
- Show the pinned location, route name or nearby destination, and approximate distance ahead when available.
- Ask one clear question, such as **Is this a pothole?**
- Provide two actions: **Not now** and **Confirm & upload**.
- State briefly that confirming uploads the hazard and location automatically.

On **Confirm & upload**, immediately send the confirmed hazard observation, GPS location, timestamp, active route/road-segment identifier, and any approved evidence frame to the road-risk service. Do not open another form or require a second upload button. Show a simple success message such as **Road update sent. Route checked.** If the new road-risk data changes the recommended route, show the new option and let the user choose whether to switch routes.

On **Not now**, close the confirmation without uploading that detection and continue scanning while the route remains active. Do not add a manual road-problem report button elsewhere. A road update is submitted only after the user confirms a camera finding.

Represent the camera flow with explicit frontend states, for example:

```text
inactive → permission needed → scanning → confirmation needed
                                      ↘ not confirmed → scanning
confirmation needed → uploading → uploaded → route checked
```

Keep continuous camera/video handling separate from road-report submission. The frontend must not claim it has detected a hazard if the model service is unavailable. In demo mode, use a clearly labelled simulated detection event so the confirmation and upload states can be demonstrated without pretending a real model is running.

## Data and integration boundaries

Create typed frontend models for the data needed by the views:

- `TripInput`: crop, quantity, unit, vehicle, origin, destination.
- `RouteOption`: route ID, category (`optimal`, `safer`, or `fastest`), geometry, travel time, distance, road-condition summary, weather/flood summary, crop-risk score, explanation, and recommendation status.
- `DetectedHazard`: hazard type, detection time, confidence if supplied by the model, GPS coordinates, active route/road segment, distance ahead, and optional evidence-frame reference.
- `UploadStatus`: idle, uploading, uploaded, or failed, with a user-readable message.

Place API calls behind small service functions, for example `calculateRoutes`, `startHazardScanning`, `confirmHazard`, and `recalculateRoute`. Keep exact URL paths configurable to match the FastAPI service. Do not put API keys or secrets in the frontend. Include mock service responses for a one-corridor demo and make the source of demo data visible in the code and UI.

Use the browser camera and geolocation only in the active-route flow, with permission handled clearly. If geolocation is unavailable, show that the location could not be pinned and do not report a made-up coordinate. Keep OSM attribution visible on the map. Configure a real tile/style provider through environment settings; do not hardcode private tokens.

## Suggested component and project structure

Keep components small and named for the job they perform. A reasonable starting point is:

```text
src/
  app/
    App.vue
    router.ts
  components/
    delivery/DeliveryForm.vue
    routes/RouteMap.vue
    routes/RouteOptionCard.vue
    routes/RiskSummary.vue
    active/ActiveRouteHeader.vue
    active/CameraStatus.vue
    active/PortraitCameraPreview.vue
    active/HazardConfirmation.vue
    shared/PermissionNotice.vue
    shared/UploadStatus.vue
    ui/                         # shadcn-vue components
  composables/
    useGeolocation.ts
    useCamera.ts
    useRouteFlow.ts
  services/
    routes.ts
    hazards.ts
    weather.ts
  types/
    trip.ts
    route.ts
    hazard.ts
  data/
    demoTrip.ts
    demoRoutes.ts
  assets/
  styles/
    main.css
```

Do not add a store library unless multiple views need shared state. If needed, keep trip, selected route, active-route state, and current hazard event in one small store.

## Functional demo behavior

The frontend should remain useful before the backend is connected:

- The prefilled demo trip can generate deterministic **Optimal**, **Safer**, and **Fastest** sample route options.
- The Optimal option is clearly marked as the default recommendation, while Safer and Fastest remain visible, selectable alternatives.
- Selecting any route option highlights its matching map line and keeps that choice available to **Use this route**.
- The map shows the sample route geometry and hazard markers, with demo data clearly identified.
- Route cards update when the user edits the crop, load, vehicle, origin, or destination and presses **Find routes**.
- Selecting **Use this route** enters the active-route state and activates the camera permission/scanning flow.
- A simulated camera event demonstrates each confirmation state. Confirming updates the mock road-risk data and shows the success/recalculation feedback; **Not now** dismisses the event without upload.
- The layout includes useful loading, empty, permission-denied, map-unavailable, and upload-failed messages. Do not leave controls that appear functional but have no behavior.

## Definition of done

- The app starts on the route planning/results experience without a landing page, login, or sign-up.
- A nontechnical farmer can enter a delivery, compare route choices, understand the recommendation, and start a route.
- The results screen shows an Optimal recommendation plus selectable Safer and Fastest alternatives, with the trade-offs explained in plain language.
- The mobile layout works without horizontal scrolling; the wide layout shows a readable map and route comparison.
- The active-route camera state is visible and scanning is tied to the active trip.
- Hazard detection prompts for one confirmation; only a confirmed finding is automatically uploaded with its geotag. There is no separate manual report form.
- The camera preview stays portrait 9:16 while the rest of the interface follows its responsive layout.
- Risk explanations do not claim scientifically calibrated spoilage or exact saved-loss percentages.
- Keyboard focus, labels, error states, and text contrast are usable. Buttons and selects have visible labels; icons are not the only way to identify an action.
- The project has a README with setup/run instructions and a `.env.example` for public configuration such as the map style URL. No secrets are included.

## Source notes

Product scope and domain requirements are taken from **ARCgriculture - NextGen Agri Hackathon Concept Note.pdf**, especially its “Proposed Solution & Value Proposition” and “Prototype & Technical Execution Strategy” sections. The Concept Note proposes Vue.js, OSM, Leaflet or MapLibre, a Python/FastAPI service, PostGIS, YOLO-based hazard detection, smartphone camera/GPS, and external weather/flood sources. The later user clarification in this conversation is authoritative for the camera UX: scanning runs during an active route; the user confirms a detected hazard; then its hazard details and location upload automatically.

Frontend reference documentation:

- [Vue 3 Guide](https://vuejs.org/guide/introduction.html)
- [Vite Guide](https://vite.dev/guide/)
- [shadcn-vue Introduction](https://www.shadcn-vue.com/docs/introduction)
- [Tailwind CSS with Vite](https://tailwindcss.com/docs/installation/using-vite)
- [MapLibre GL JS Documentation](https://maplibre.org/maplibre-gl-js/docs/)
- [Vue Router Guide](https://router.vuejs.org/guide/)
