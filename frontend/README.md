# AniRoute presentation frontend

This Vue 3 application presents the complete AniRoute hackathon story without requiring a backend service.

```sh
npm ci
cp .env.example .env
npm run dev
```

The presentation opens with a tomato shipment already configured. The optimal route is expanded so judges can immediately see:

- three alternative farm-to-market routes;
- time, distance, road, flood, weather, and temperature information;
- a numeric Crop Transport Risk Score and its contributing factors;
- a crop-sensitivity explanation;
- an automatic road-camera finding;
- confirmation with a GPS position;
- segment-risk updating and route recalculation.

Changing the crop changes the scoring weights. Tomatoes and leafy vegetables prioritize road, delay, flood, and heat exposure. Durable crops place more weight on time and distance.

The map uses MapLibre with CARTO and OpenStreetMap attribution. Route geometry and all operational values are illustrative for the hackathon presentation. They are not turn-by-turn directions, safety advice, or scientifically calibrated spoilage predictions.

Run the automated checks with:

```sh
npm run typecheck
npm test
npm run build
```
