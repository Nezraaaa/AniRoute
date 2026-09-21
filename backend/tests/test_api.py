import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend import main


@pytest.fixture()
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(main, "DATA_DIR", tmp_path)
    return tmp_path


def trip_input(**overrides):
    values = dict(
        crop="Tomatoes", quantity=250, unit="kg", vehicle="Small truck",
        origin="Farm pickup point, Tupi", destination="Koronadal trading post",
    )
    values.update(overrides)
    return main.TripInput(**values)


def test_health_reports_demo_capabilities():
    assert main.health() == {
        "status": "ok",
        "service": "aniroute-demo-api",
        "data_source": "demo",
        "live_route_engine": False,
        "live_hazard_detection": False,
    }


def test_calculate_returns_three_explained_categories():
    result = main.calculate_routes(trip_input())
    assert {route["category"] for route in result["routes"]} == {"optimal", "safer", "fastest"}
    assert result["recommended_route_id"] == "optimal"
    assert next(route for route in result["routes"] if route["category"] == "optimal")["recommended"] is True
    for route in result["routes"]:
        assert route["geometry"]["type"] == "LineString"
        assert route["travel_time_minutes"] > 0
        assert route["distance_km"] > 0
        assert route["road_condition_summary"]
        assert route["weather_flood_summary"]
        assert route["temperature_exposure_summary"]
        assert route["crop_risk_label"] in {"lower", "moderate", "higher"}
        assert route["explanation"]
    assert result["data_source"] == "demo"


def test_demo_estimates_reflect_trip_edits_but_keep_the_illustrative_corridor():
    baseline = main.calculate_routes(trip_input())["routes"]
    edited = main.calculate_routes(trip_input(
        crop="Leafy vegetables", quantity=500, vehicle="Medium truck",
        origin="Polomolok farm gate", destination="General Santos public market",
    ))["routes"]
    optimal_before = next(route for route in baseline if route["category"] == "optimal")
    optimal_after = next(route for route in edited if route["category"] == "optimal")
    assert optimal_after["travel_time_minutes"] > optimal_before["travel_time_minutes"]
    assert optimal_after["distance_km"] > optimal_before["distance_km"]
    assert optimal_after["crop_risk_score"] > optimal_before["crop_risk_score"]
    assert optimal_after["geometry"] == optimal_before["geometry"]


def test_invalid_trip_is_rejected():
    with pytest.raises(ValidationError):
        trip_input(quantity=0)


def test_trip_accepts_multiple_delivery_points_and_crop_loads():
    trip = trip_input(
        cropLoads=[{"name": "Tomatoes", "quantity": 125}, {"name": "Mangoes", "quantity": 80}],
        deliveryPoints=["Koronadal trading post", "General Santos public market"],
    )

    assert [crop.name for crop in trip.crop_loads] == ["Tomatoes", "Mangoes"]
    assert trip.delivery_points == ["Koronadal trading post", "General Santos public market"]


def test_scanner_does_not_claim_live_detection():
    result = main.start_scanning(main.ScanStart(route_id="optimal"))
    assert result["mode"] == "demo"
    assert result["detection_available"] is False
    frame = "data:image/jpeg;base64,/9j/AA=="
    scan = main.scan_frame(main.ScanFrame(route_id="optimal", captured_at="2026-09-20T12:30:00Z", frame_data_url=frame))
    assert scan["detection"] is None
    assert scan["frame_stored"] is False
    assert main.stop_scanning(main.ScanStart(route_id="optimal"))["scanning"] is False


def test_confirmed_hazard_stores_geotag_and_evidence(data_dir: Path):
    payload = main.HazardConfirmation(
        hazard_type="pothole", detected_at="2026-09-20T12:30:00Z",
        latitude=6.42, longitude=124.89, route_id="optimal",
        road_segment_id="optimal-segment-2", distance_ahead_km=0.4,
        simulated=True, evidence_frame_data_url="data:image/jpeg;base64,aGVsbG8=",
    )
    result = main.confirm_hazard(payload)
    saved = json.loads((data_dir / "hazard_observations.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert result["status"] == "uploaded"
    assert result["data_source"] == "demo"
    assert result["evidence_stored"] is True
    assert saved["latitude"] == 6.42
    assert saved["longitude"] == 124.89
    assert saved["route_id"] == "optimal"
    assert saved["road_segment_id"] == "optimal-segment-2"
    assert "evidence_frame_data_url" not in saved
    assert (data_dir / saved["evidence_frame_path"]).read_bytes() == b"hello"


def test_hazard_requires_both_coordinates_or_neither():
    with pytest.raises(ValidationError):
        main.HazardConfirmation(
            hazard_type="standing_water", detected_at="2026-09-20T12:30:00Z",
            latitude=6.42, route_id="fastest", road_segment_id="fastest-segment-2",
        )


def test_recalculation_can_recommend_a_safer_alternative():
    payload = main.RecalculateInput(
        trip=trip_input(), active_route_id="optimal", hazard_type="pothole",
        road_segment_id="optimal-segment-2", observation_id="demo-observation-1",
    )
    result = main.recalculate_routes(payload)
    assert result["changed"] is True
    assert result["recommended_route_id"] == "safer"
    safer = next(route for route in result["routes"] if route["route_id"] == "safer")
    assert safer["recommended"] is True
