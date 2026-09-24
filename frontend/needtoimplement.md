# Production work after the hackathon

The browser presentation proves the AniRoute interaction and decision model with controlled scenario data. A production deployment requires the following services.

| Priority | Work | Required outcome |
| --- | --- | --- |
| P0 | Road-network routing | Connect OpenStreetMap road graphs through OSMnx or another routing engine, with NetworkX and Dijkstra/A*. Return real route geometry, distance, ETA, road segments, and vehicle constraints. |
| P0 | Computer vision | Connect a validated YOLO-based model for potholes, severe road damage, standing water, and obstructions. Include confidence thresholds, cooldowns, deduplication, and model health reporting. |
| P0 | Geospatial persistence | Store road segments and confirmed observations in PostgreSQL/PostGIS. Add migrations, retention rules, access controls, backups, and secure evidence storage. |
| P1 | Crop profiles | Validate the presentation weights against postharvest literature and field observations for each supported commodity. |
| P1 | Weather and hazards | Integrate PAGASA and suitable GeoRiskPH, HazardHunterPH, UP NOAH, or PhilSA information with source and freshness metadata. |
| P1 | Route recalculation | Match observations to real road segments, update segment risk, and rerun route optimization against current conditions. |
| P1 | Rural geocoding | Support farm landmarks, ambiguous rural addresses, caching, privacy controls, and provider rate limits. |
| P2 | Trip guidance | Match GPS to route geometry and calculate remaining time, distance, and validated next turns. |
| P2 | Operations | Add HTTPS, authentication where required, rate limits, monitoring, backups, and privacy and consent controls. |
| P2 | Validation | Conduct field trials across crops, vehicles, roads, seasons, and weather before publishing operational loss or freshness claims. |

Keep the existing frontend field names or update the adapters and automated checks together. Production responses should include stable identifiers, source metadata, timestamps, and idempotent observation handling.
