import json
from pathlib import Path

import pytest

from backend import hazard_risk


def test_point_to_polyline_distance_in_metres():
    line = [[121.0, 14.0], [121.0, 14.01]]          # ~1.1 km north-south segment
    assert hazard_risk.distance_to_polyline_m(14.005, 121.0, line) == pytest.approx(0, abs=0.5)
    # 0.0005 deg of longitude at 14°N ≈ 54 m
    assert hazard_risk.distance_to_polyline_m(14.005, 121.0005, line) == pytest.approx(54, abs=2)
    # Beyond the segment end the distance is measured to the endpoint.
    assert hazard_risk.distance_to_polyline_m(14.02, 121.0, line) == pytest.approx(1112, rel=0.01)


def test_assess_route_sums_severity_within_radius_and_caps_at_100():
    line = [[121.0, 14.0], [121.0, 14.01]]
    near = {"hazard_type": "road_obstruction", "latitude": 14.004, "longitude": 121.0003, "observation_id": "a", "confidence": 0.9}
    far = {"hazard_type": "pothole", "latitude": 14.004, "longitude": 121.01, "observation_id": "b"}
    factor, pins = hazard_risk.assess_route(line, [near, far])
    assert factor == 30
    assert [pin["id"] for pin in pins] == ["a"]
    assert "90% model confidence" in pins[0]["note"]
    many = [dict(near, observation_id=str(index)) for index in range(5)]
    assert hazard_risk.assess_route(line, many)[0] == 100


def test_load_observations_skips_simulated_and_malformed(tmp_path: Path):
    path = tmp_path / "obs.jsonl"
    rows = [
        {"hazard_type": "pothole", "latitude": 14.0, "longitude": 121.0, "simulated": False},
        {"hazard_type": "pothole", "latitude": 14.0, "longitude": 121.0, "simulated": True},
        {"hazard_type": "unknown", "latitude": 14.0, "longitude": 121.0},
        {"hazard_type": "pothole", "latitude": None, "longitude": None},
    ]
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\nnot json\n", encoding="utf-8")
    assert len(hazard_risk.load_observations(path)) == 1
    assert len(hazard_risk.load_observations(path, include_simulated=True)) == 2
    assert hazard_risk.load_observations(tmp_path / "missing.jsonl") == []


def test_summary_text():
    pins = [{"name": "Pothole"}, {"name": "Pothole"}, {"name": "Severe road damage"}]
    assert hazard_risk.summarize_hazards(pins) == "Confirmed on this route: 2 potholes, 1 severe road damage"
    assert hazard_risk.summarize_hazards([]) == ""
