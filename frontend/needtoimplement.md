# Production work after the hackathon

The browser presentation proves the AniRoute interaction and decision model with controlled scenario data. A production deployment requires the following services.

| Priority | Work | Required outcome |
| --- | --- | --- |
| P0 | Road-network routing | Implemented baseline: FastAPI resolves stops and calls a configurable OSRM-compatible service for real route geometry, distance and ETA. Production still needs a managed/self-hosted provider, vehicle constraints, road-segment identifiers and service-level monitoring. |
| P0 | Computer vision | Connect a validated YOLO-based model for potholes, severe road damage, standing water, and obstructions. Include confidence thresholds, cooldowns, deduplication, and model health reporting. |
| P0 | Geospatial persistence | Store road segments and confirmed observations in PostgreSQL/PostGIS. Add migrations, retention rules, access controls, backups, and secure evidence storage. |
| P1 | Crop profiles | Validate the presentation weights against postharvest literature and field observations for each supported commodity. |
| P1 | Weather and hazards | Integrate PAGASA and suitable GeoRiskPH, HazardHunterPH, UP NOAH, or PhilSA information with source and freshness metadata. |
| P1 | Route recalculation | Live geometry/ETA recalculation is implemented; match observations to real road segments, update segment risk, and rerank routes after connected road/weather feeds are available. |
| P1 | Rural geocoding | Support farm landmarks, ambiguous rural addresses, caching, privacy controls, and provider rate limits. |
| P2 | Trip guidance | Match GPS to route geometry and calculate remaining time, distance, and validated next turns. |
| P2 | Operations | Add HTTPS, authentication where required, rate limits, monitoring, backups, and privacy and consent controls. |
| P2 | Validation | Conduct field trials across crops, vehicles, roads, seasons, and weather before publishing operational loss or freshness claims. |

Keep the existing frontend field names or update the adapters and automated checks together. Production responses should include stable identifiers, source metadata, timestamps, and idempotent observation handling.
