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


def test_health_reports_live_route_and_vision_capabilities():
    health = main.health()
    assert health["status"] == "ok"
    assert health["data_source"] == "api"
    assert health["live_route_engine"] is True
    assert isinstance(health["live_hazard_detection"], bool)
    assert isinstance(health["supported_hazards"], list)


def live_provider_routes():
    return [
        {
            "duration": 3_600,
            "distance": 90_000,
            "geometry": {"type": "LineString", "coordinates": [[120.6, 16.4], [121.0, 15.4], [121.16, 14.21]]},
        },
        {
            "duration": 4_200,
            "distance": 82_000,
            "geometry": {"type": "LineString", "coordinates": [[120.6, 16.4], [120.82, 15.55], [121.16, 14.21]]},
        },
        {
            "duration": 4_800,
            "distance": 105_000,
            "geometry": {"type": "LineString", "coordinates": [[120.6, 16.4], [121.22, 15.1], [121.16, 14.21]]},
        },
    ]


def test_live_calculation_returns_provider_geometry_and_api_source(monkeypatch: pytest.MonkeyPatch, data_dir: Path):
    stops = [
        main.Coordinates(latitude=16.402, longitude=120.596),
        main.Coordinates(latitude=14.2117, longitude=121.1653),
    ]
    monkeypatch.setattr(main, "_resolve_trip_stops", lambda trip: stops)
    monkeypatch.setattr(main, "_request_routing_routes", lambda resolved_stops, alternatives=True: live_provider_routes())

    result = main.calculate_routes(trip_input(
        originCoordinates={"latitude": 16.402, "longitude": 120.596},
        deliveryPointCoordinates=[{"latitude": 14.2117, "longitude": 121.1653}],
    ))

    assert result["data_source"] == "api"
    assert result["recommended_route_id"] == "route-1"
    assert next(route for route in result["routes"] if route["recommended"])["category"] == "optimal"
    assert result["routes"]
    assert all(route["category"] in {"optimal", "fastest", "safer", "alternative"} for route in result["routes"])
    assert result["routes"][0]["geometry"]["coordinates"] == live_provider_routes()[0]["geometry"]["coordinates"]
    assert result["routes"][0]["travel_time_minutes"] == 60
    assert result["routes"][0]["distance_km"] == 90
    assert result["routes"][0]["risk_factors"]["road"] == 0
    factors = result["routes"][0]["risk_factors"]
    assert set(factors) == {"travelTime", "distance", "crop", "road", "safety"}
    assert factors["travelTime"] > 0 and factors["distance"] > 0 and factors["crop"] > 0   # real values, never placeholders


def test_live_recalculation_keeps_live_source(monkeypatch: pytest.MonkeyPatch, data_dir: Path):
    monkeypatch.setattr(main, "_resolve_trip_stops", lambda trip: [
        main.Coordinates(latitude=16.402, longitude=120.596),
        main.Coordinates(latitude=14.2117, longitude=121.1653),
    ])
    monkeypatch.setattr(main, "_request_routing_routes", lambda resolved_stops, alternatives=True: live_provider_routes())
    payload = main.RecalculateInput(
        trip=trip_input(), active_route_id="route-2", hazard_type="pothole",
        road_segment_id="route-2@unlocated", observation_id="observation-1",
    )

    result = main.recalculate_routes(payload)

    assert result["data_source"] == "api"
    assert result["changed"] is True
    assert "re-scored after the confirmed pothole" in result["message"]


def test_confirmed_hazard_on_active_route_changes_live_recommendation(monkeypatch: pytest.MonkeyPatch, data_dir: Path):
    monkeypatch.setattr(main, "_resolve_trip_stops", lambda trip: [
        main.Coordinates(latitude=16.402, longitude=120.596),
        main.Coordinates(latitude=14.2117, longitude=121.1653),
    ])
    monkeypatch.setattr(main, "_request_routing_routes", lambda resolved_stops, alternatives=True: live_provider_routes())
    before = main.calculate_routes(trip_input())
    assert before["recommended_route_id"] == "route-1"

    # Driver confirms severe road damage on route-1's middle vertex (121.0, 15.4).
    main.confirm_hazard(main.HazardConfirmation(
        hazard_type="severe_road_damage", detected_at="2026-11-22T10:00:00Z", confidence=0.83,
        latitude=15.4, longitude=121.0, route_id="route-1", road_segment_id="route-1@15.4000,121.0000",
    ))
    result = main.recalculate_routes(main.RecalculateInput(
        trip=trip_input(), active_route_id="route-1", hazard_type="severe_road_damage",
        road_segment_id="route-1@15.4000,121.0000", observation_id="x",
    ))
    route_1 = next(route for route in result["routes"] if route["route_id"] == "route-1")
    assert route_1["risk_factors"]["road"] == 25
    assert route_1["known_hazards"][0]["name"] == "Severe road damage"
    assert result["recommended_route_id"] != "route-1"
    assert result["changed"] is True
    assert "different route is now recommended" in result["message"]


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


def test_scanner_reports_unavailable_detection_honestly_without_models(monkeypatch: pytest.MonkeyPatch):
    from backend.vision import ensemble
    from backend.vision.config import VisionSettings

    detector = ensemble.HazardDetector(VisionSettings(warmup=False))
    detector.model_a.load = lambda: False
    detector.model_b.load = lambda: False
    monkeypatch.setattr(ensemble, "_detector", detector)
    result = main.start_scanning(main.ScanStart(route_id="optimal"))
    assert result["mode"] == "live"
    assert result["detection_available"] is False
    frame = "data:image/jpeg;base64,/9j/AA=="
    scan = main.scan_frame(main.ScanFrame(route_id="optimal", captured_at="2026-09-20T12:30:00Z", frame_data_url=frame))
    assert scan["detection"] is None
    assert scan["data_source"] == "api"
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
    assert result["data_source"] == "api"
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


def test_detour_alternatives_keep_real_roads_and_reject_spurs(monkeypatch: pytest.MonkeyPatch):
    start = main.Coordinates(latitude=16.40, longitude=120.60)
    end = main.Coordinates(latitude=14.21, longitude=121.16)
    direct = {"duration": 3_600, "distance": 90_000,
              "geometry": {"coordinates": [[120.60 + i * 0.056, 16.40 - i * 0.219] for i in range(11)]}}
    west = {"duration": 4_000, "distance": 95_000,
            "geometry": {"coordinates": [[120.50 + i * 0.066, 16.40 - i * 0.219] for i in range(11)]}}
    # Drives out to the via point and back the same way: a spur, not a real alternative.
    spur_path = [[120.60 + i * 0.01, 15.30] for i in range(12)]
    spur = {"duration": 4_100, "distance": 99_000, "geometry": {"coordinates": spur_path + spur_path[::-1] + spur_path}}
    too_slow = {"duration": 9_000, "distance": 200_000,
                "geometry": {"coordinates": [[121.30 + i * 0.01, 16.0 - i * 0.2] for i in range(11)]}}
    replies = iter([[spur], [west], [too_slow], [west]])
    monkeypatch.setattr(main, "_request_routing_routes", lambda stops, alternatives=True: next(replies, []))

    routes = main._with_detour_alternatives([start, end], [direct])

    assert routes[0] is direct
    assert west in routes and spur not in routes and too_slow not in routes
    assert routes.count(west) == 1   # the same road found twice is kept once


def test_three_options_use_three_different_roads_with_truthful_titles():
    def road(route_id, minutes, safety, recommended=False):
        return {"route_id": route_id, "travel_time_minutes": minutes, "recommended": recommended,
                "risk_factors": {"safety": safety}}

    # The recommended road is also the fastest and the safest: the other two options must still be
    # different roads, and their titles must say they are alternatives.
    options = main._assign_options([road("r1", 281, 10, True), road("r2", 318, 20), road("r3", 347, 30)])
    assert {key: value["key"] for key, value in options.items()} == {"r1": "optimal", "r2": "fastest", "r3": "safer"}
    assert options["r2"]["title"] == "Fastest alternative" and options["r3"]["title"] == "Safest alternative"

    # When different roads really win, they get the plain titles.
    options = main._assign_options([road("r1", 40, 30, True), road("r2", 35, 40), road("r3", 45, 10)])
    assert options["r2"]["title"] == "Fastest route" and options["r3"]["title"] == "Safest route"


def test_driver_route_stays_listed_after_recalculation(monkeypatch: pytest.MonkeyPatch, data_dir: Path):
    stops = [main.Coordinates(latitude=16.402, longitude=120.596), main.Coordinates(latitude=14.2117, longitude=121.1653)]
    monkeypatch.setattr(main, "_resolve_trip_stops", lambda trip: stops)
    monkeypatch.setattr(main, "_request_routing_routes", lambda resolved_stops, alternatives=True: live_provider_routes())
    trip = main.TripInput(**{"crop": "Tomatoes", "quantity": 250, "vehicle": "Small truck",
                             "origin": "Baguio City", "destination": "Calamba"})

    listed = main._live_routes(trip)["routes"]
    assert len({route["route_id"] for route in listed}) == len(listed) == 3
    assert [route["option"]["key"] for route in listed] == ["optimal", "fastest", "safer"]
    assert main._live_routes(trip, keep_route_id="route-3")["routes"]
