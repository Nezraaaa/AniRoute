"""How safe a road is for a load of fresh produce, from the route geometry OSRM returns.

Three things bruise produce or cause accidents on farm-to-market roads, and all three can be measured
for every candidate road before the trip:

* curves      - total heading change per km (mountain switchbacks shift and bruise the load),
* stop-and-go - intersections per km (each one means braking and accelerating),
* hazards     - potholes, damage and obstructions confirmed by AniRoute drivers (hazard_risk.py).

The weights are transparent heuristics, not measured accident rates; they rank roads against each other.
"""
from __future__ import annotations

import math

# Heading change below this (degrees per km) is a normal, gently winding road and adds no risk.
CURVE_BASELINE_DEG_PER_KM = 15.0
CURVE_POINTS_PER_DEG = 0.4         # 100 at 265 deg/km (continuous mountain switchbacks)
STOP_POINTS_PER_INTERSECTION_KM = 10.0
RESAMPLE_KM = 0.05                 # measure bends every 50 m, so point density does not change the result


def _haversine_km(a: list[float], b: list[float]) -> float:
    lon1, lat1, lon2, lat2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(h))


def _bearing(a: list[float], b: list[float]) -> float:
    lon1, lat1, lon2, lat2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    y = math.sin(lon2 - lon1) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(lon2 - lon1)
    return math.degrees(math.atan2(y, x))


def _resample(coordinates: list[list[float]], spacing_km: float) -> list[list[float]]:
    """Points every `spacing_km` along the polyline (linear interpolation between vertices)."""
    if len(coordinates) < 2:
        return list(coordinates)
    out = [coordinates[0]]
    carried = 0.0
    for a, b in zip(coordinates, coordinates[1:]):
        segment = _haversine_km(a, b)
        if segment <= 0:
            continue
        position = spacing_km - carried
        while position <= segment:
            f = position / segment
            out.append([a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f])
            position += spacing_km
        carried = segment - (position - spacing_km)
    return out


def curve_degrees_per_km(coordinates: list[list[float]], distance_km: float) -> float:
    """Sum of heading changes along the road, per km driven, measured every 50 m."""
    points = _resample(coordinates, RESAMPLE_KM)
    total = 0.0
    for i in range(1, len(points) - 1):
        turn = (_bearing(points[i], points[i + 1]) - _bearing(points[i - 1], points[i]) + 180) % 360 - 180
        total += abs(turn)
    return total / distance_km if distance_km > 0 else 0.0


def intersections_per_km(raw_route: dict, distance_km: float) -> float:
    count = 0
    for leg in raw_route.get("legs") or []:
        for step in (leg.get("steps") or []) if isinstance(leg, dict) else []:
            if isinstance(step, dict):
                count += len(step.get("intersections") or [])
    return count / distance_km if distance_km > 0 else 0.0


def _clamp(value: float) -> int:
    return round(max(0.0, min(100.0, value)))


def assess(coordinates: list[list[float]], raw_route: dict, distance_km: float, hazard_factor: int) -> dict:
    """Road-safety risk 0-100 (lower is safer) and its parts, for one candidate road."""
    curves = curve_degrees_per_km(coordinates, distance_km)
    stops = intersections_per_km(raw_route, distance_km)
    curve_score = _clamp((curves - CURVE_BASELINE_DEG_PER_KM) * CURVE_POINTS_PER_DEG)
    stop_score = _clamp(stops * STOP_POINTS_PER_INTERSECTION_KM)
    risk = _clamp(0.5 * curve_score + 0.3 * stop_score + hazard_factor)
    return {
        "safety_risk": risk,
        "curve_score": curve_score,
        "stop_score": stop_score,
        "curves_deg_per_km": round(curves, 1),
        "intersections_per_km": round(stops, 2),
    }
