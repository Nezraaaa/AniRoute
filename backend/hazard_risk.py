"""Turns confirmed camera observations into route road-risk.

Each confirmed hazard within `radius_m` of a route polyline adds a severity weight
to that route's road factor (0-100). The weights are heuristic presentation values,
not validated postharvest-loss coefficients; see docs/MODEL_CARD.md limitations.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

SEVERITY = {
    "pothole": 12,
    "standing_water": 20,
    "severe_road_damage": 25,
    "road_obstruction": 30,
}
HAZARD_NAMES = {
    "pothole": "Pothole",
    "severe_road_damage": "Severe road damage",
    "standing_water": "Standing water",
    "road_obstruction": "Road obstruction",
}
EARTH_RADIUS_M = 6_371_000.0
DEFAULT_RADIUS_M = 75.0


def _project(lat: float, lon: float, origin_lat: float, origin_lon: float) -> tuple[float, float]:
    """Equirectangular projection to metres around an origin (accurate at route scale)."""
    x = math.radians(lon - origin_lon) * math.cos(math.radians(origin_lat)) * EARTH_RADIUS_M
    y = math.radians(lat - origin_lat) * EARTH_RADIUS_M
    return x, y


def point_to_segment_m(lat: float, lon: float, a: tuple[float, float], b: tuple[float, float]) -> float:
    """Distance in metres from (lat, lon) to segment a-b, where a and b are (lon, lat)."""
    ax, ay = _project(a[1], a[0], lat, lon)
    bx, by = _project(b[1], b[0], lat, lon)
    dx, dy = bx - ax, by - ay
    length_sq = dx * dx + dy * dy
    t = 0.0 if length_sq == 0 else max(0.0, min(1.0, -(ax * dx + ay * dy) / length_sq))
    px, py = ax + t * dx, ay + t * dy
    return math.hypot(px, py)


def distance_to_polyline_m(lat: float, lon: float, coordinates: list[list[float]]) -> float:
    if not coordinates:
        return math.inf
    if len(coordinates) == 1:
        return point_to_segment_m(lat, lon, tuple(coordinates[0]), tuple(coordinates[0]))
    # Cheap bounding-box rejection: 0.01 deg ≈ 1.1 km, far beyond any hazard radius used.
    margin = 0.01
    best = math.inf
    for start, end in zip(coordinates, coordinates[1:]):
        if (lon < min(start[0], end[0]) - margin or lon > max(start[0], end[0]) + margin
                or lat < min(start[1], end[1]) - margin or lat > max(start[1], end[1]) + margin):
            continue
        best = min(best, point_to_segment_m(lat, lon, (start[0], start[1]), (end[0], end[1])))
    return best


def load_observations(path: Path, *, include_simulated: bool = False) -> list[dict]:
    """Read confirmed observations that carry coordinates. Malformed lines are skipped."""
    observations: list[dict] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return observations
    for line in lines:
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if not isinstance(record, dict) or record.get("hazard_type") not in SEVERITY:
            continue
        if record.get("simulated", False) and not include_simulated:
            continue
        if not isinstance(record.get("latitude"), (int, float)) or not isinstance(record.get("longitude"), (int, float)):
            continue
        observations.append(record)
    return observations


def assess_route(coordinates: list[list[float]], observations: list[dict], radius_m: float = DEFAULT_RADIUS_M) -> tuple[int, list[dict]]:
    """Return (road_factor 0-100, hazard pins near this route)."""
    pins: list[dict] = []
    total = 0
    for record in observations:
        distance = distance_to_polyline_m(record["latitude"], record["longitude"], coordinates)
        if distance > radius_m:
            continue
        total += SEVERITY[record["hazard_type"]]
        confidence = record.get("confidence")
        detail = f"{round(confidence * 100)}% model confidence" if isinstance(confidence, (int, float)) else "driver report"
        pins.append({
            "id": str(record.get("observation_id", f"obs-{len(pins)}")),
            "name": HAZARD_NAMES[record["hazard_type"]],
            "coordinates": {"latitude": record["latitude"], "longitude": record["longitude"]},
            "note": f"Confirmed by driver · {detail} · {round(distance)} m from route",
            "hazard_type": record["hazard_type"],
        })
    return min(100, total), pins


def summarize_hazards(pins: list[dict]) -> str:
    if not pins:
        return ""
    counts: dict[str, int] = {}
    for pin in pins:
        counts[pin["name"]] = counts.get(pin["name"], 0) + 1
    parts = [f"{count} {name.lower()}{'s' if count > 1 and not name.endswith('damage') else ''}" for name, count in counts.items()]
    return "Confirmed on this route: " + ", ".join(parts)
