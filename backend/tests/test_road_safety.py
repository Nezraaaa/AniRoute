"""Road-safety score: curves, stop-and-go and confirmed hazards make a road riskier for produce."""
from __future__ import annotations

import math

try:
    from backend import road_safety
except ImportError:  # running from inside backend/
    import road_safety  # type: ignore[no-redef]


def straight_road(km: float = 10, points: int = 50) -> list[list[float]]:
    step = km / 111 / points
    return [[121.0, 14.0 + i * step] for i in range(points + 1)]


def winding_road(km: float = 10, points: int = 200) -> list[list[float]]:
    step = km / 111 / points
    return [[121.0 + 0.002 * math.sin(i / 3), 14.0 + i * step] for i in range(points + 1)]


def steps_with_intersections(count: int) -> dict:
    return {"legs": [{"steps": [{"intersections": [{}] * count}]}]}


def test_winding_road_is_riskier_than_straight_road():
    straight = road_safety.assess(straight_road(), {}, 10, hazard_factor=0)
    winding = road_safety.assess(winding_road(), {}, 10, hazard_factor=0)
    assert straight["curves_deg_per_km"] < 5
    assert winding["curves_deg_per_km"] > straight["curves_deg_per_km"]
    assert winding["safety_risk"] > straight["safety_risk"]


def test_stop_and_go_and_confirmed_hazards_add_risk():
    road = straight_road()
    calm = road_safety.assess(road, steps_with_intersections(5), 10, hazard_factor=0)
    busy = road_safety.assess(road, steps_with_intersections(40), 10, hazard_factor=0)
    hazard = road_safety.assess(road, steps_with_intersections(5), 10, hazard_factor=25)
    assert busy["intersections_per_km"] == 4.0 and busy["safety_risk"] > calm["safety_risk"]
    assert abs(hazard["safety_risk"] - (calm["safety_risk"] + 25)) <= 1   # rounding
