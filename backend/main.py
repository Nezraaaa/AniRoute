from __future__ import annotations

import base64
import binascii
import json
import os
import re
import threading
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, model_validator

try:  # imported as `backend.main` (tests, `uvicorn backend.main:app`)
    from . import hazard_risk, road_safety
    from .vision.config import REPORTS_DIR, SAMPLES_DIR
    from .vision.ensemble import get_detector
    from .vision.preprocess import ImageDecodeError, decode_data_url, encode_jpeg_data_url
    from .vision.annotate import draw_detections
    from .vision.router import get_hazard_filter, router as vision_router, run_detection
except ImportError:  # run from inside backend/ (`uvicorn main:app`)
    import hazard_risk  # type: ignore[no-redef]
    import road_safety  # type: ignore[no-redef]
    from vision.config import REPORTS_DIR, SAMPLES_DIR  # type: ignore[no-redef]
    from vision.ensemble import get_detector  # type: ignore[no-redef]
    from vision.preprocess import ImageDecodeError, decode_data_url, encode_jpeg_data_url  # type: ignore[no-redef]
    from vision.annotate import draw_detections  # type: ignore[no-redef]
    from vision.router import get_hazard_filter, router as vision_router, run_detection  # type: ignore[no-redef]


HazardType = Literal["pothole", "severe_road_damage", "standing_water", "road_obstruction"]

APP_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("ANIROUTE_DATA_DIR", str(APP_DIR / "data")))
GEOCODER_URL = "https://nominatim.openstreetmap.org/search"
ROUTING_URL = os.getenv("ANIROUTE_ROUTING_URL", "https://router.project-osrm.org").rstrip("/")
ROUTING_PROFILE = os.getenv("ANIROUTE_ROUTING_PROFILE", "driving")
GEOCODER_USER_AGENT = os.getenv("ANIROUTE_GEOCODER_USER_AGENT", "AniRoute/1.0 (live route integration)")


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def _env_float(name: str, default: float) -> float:
    try:
        return max(float(os.getenv(name, str(default))), 1.0)
    except ValueError:
        return default


LIVE_ROUTING_ENABLED = _env_bool("ANIROUTE_LIVE_ROUTING_ENABLED", True)
PROVIDER_TIMEOUT_SECONDS = _env_float("ANIROUTE_PROVIDER_TIMEOUT_SECONDS", 18.0)
_write_lock = threading.Lock()


class CropLoad(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    quantity: float = Field(gt=0, le=100_000)


class Coordinates(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class TripInput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    crop: str = Field(min_length=1, max_length=60)
    quantity: float = Field(gt=0, le=100_000)
    unit: Literal["kg"] = "kg"
    vehicle: str = Field(min_length=1, max_length=60)
    origin: str = Field(min_length=1, max_length=180)
    destination: str = Field(min_length=1, max_length=180)
    crop_loads: list[CropLoad] = Field(default_factory=list, alias="cropLoads", max_length=8)
    delivery_points: list[str] = Field(default_factory=list, alias="deliveryPoints", max_length=8)
    origin_coordinates: Coordinates | None = Field(default=None, alias="originCoordinates")
    delivery_point_coordinates: list[Coordinates | None] = Field(default_factory=list, alias="deliveryPointCoordinates", max_length=8)


class HazardConfirmation(BaseModel):
    hazard_type: HazardType
    detected_at: datetime
    confidence: float | None = Field(default=None, ge=0, le=1)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    route_id: str = Field(min_length=1, max_length=100)
    road_segment_id: str = Field(min_length=1, max_length=100)
    distance_ahead_km: float | None = Field(default=None, ge=0, le=100)
    simulated: bool = False
    model: Literal["A", "B", "CV"] | None = None   # CV = the OpenCV water-filled-pothole check
    source_label: str | None = Field(default=None, max_length=60)
    evidence_frame_data_url: str | None = Field(default=None, max_length=1_500_000)

    @model_validator(mode="after")
    def coordinates_must_be_a_pair(self) -> "HazardConfirmation":
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Latitude and longitude must be provided together.")
        return self


class ScanStart(BaseModel):
    route_id: str = Field(min_length=1, max_length=100)


class ScanFrame(BaseModel):
    route_id: str = Field(min_length=1, max_length=100)
    captured_at: datetime
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    frame_data_url: str = Field(min_length=30, max_length=820_000)
    heading_degrees: float | None = Field(default=None, ge=0, le=360)

    @model_validator(mode="after")
    def coordinates_must_be_a_pair(self) -> "ScanFrame":
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Latitude and longitude must be provided together.")
        if not self.frame_data_url.startswith(("data:image/jpeg;base64,", "data:image/png;base64,")):
            raise ValueError("A JPEG or PNG camera frame is required.")
        try:
            raw = base64.b64decode(self.frame_data_url.split(",", 1)[1], validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("Camera frame is not valid base64.") from exc
        if len(raw) > 600_000:
            raise ValueError("Camera frame must be 600 KB or smaller.")
        return self


class RecalculateInput(BaseModel):
    trip: TripInput
    active_route_id: str = Field(min_length=1, max_length=100)
    hazard_type: HazardType
    road_segment_id: str = Field(min_length=1, max_length=100)
    observation_id: str = Field(min_length=1, max_length=100)


def _clamp(value: float, minimum: float = 0, maximum: float = 100) -> int:
    return round(max(minimum, min(maximum, value)))


def _geocoder_queries(query: str) -> list[str]:
    """Return a small set of useful queries for rural/farm landmark text."""
    original = query.strip()
    simplified = re.sub(
        r"\b(?:farm\s+pickup\s+point|farm\s+gate|collection\s+point|consolidation\s+center|trading\s+post|public\s+market)\b",
        "",
        original,
        flags=re.IGNORECASE,
    )
    simplified = re.sub(r"\s{2,}", " ", simplified).strip(" ,")
    candidates: list[str] = []
    for value in (original, simplified):
        if not value:
            continue
        candidate = value if re.search(r"\bphilippines\b", value, re.IGNORECASE) else f"{value}, Philippines"
        if candidate.casefold() not in {item.casefold() for item in candidates}:
            candidates.append(candidate)
    return candidates


def _geocode_route_stop(query: str) -> Coordinates:
    for candidate in _geocoder_queries(query):
        params = {
            "q": candidate,
            "format": "jsonv2",
            "addressdetails": "1",
            "limit": "1",
        }
        try:
            with httpx.Client(
                timeout=PROVIDER_TIMEOUT_SECONDS,
                follow_redirects=True,
                headers={"Accept": "application/json", "Accept-Language": "en", "User-Agent": GEOCODER_USER_AGENT},
            ) as client:
                response = client.get(GEOCODER_URL, params=params)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail="Location search service is unavailable.") from exc

        try:
            results = response.json()
        except ValueError as exc:
            raise HTTPException(status_code=502, detail="Location search returned invalid data.") from exc
        if not isinstance(results, list) or not results:
            continue

        item = results[0]
        if not isinstance(item, dict):
            continue
        try:
            return Coordinates(latitude=float(item["lat"]), longitude=float(item["lon"]))
        except (KeyError, TypeError, ValueError):
            continue

    raise HTTPException(
        status_code=422,
        detail=f"Could not locate route stop '{query}'. Select a location from the search suggestions.",
    )


def _resolve_trip_stops(trip: TripInput) -> list[Coordinates]:
    destination_queries = [point.strip() for point in trip.delivery_points if point.strip()]
    if not destination_queries:
        destination_queries = [trip.destination.strip()]

    provided_destinations = trip.delivery_point_coordinates
    stops: list[Coordinates] = [trip.origin_coordinates or _geocode_route_stop(trip.origin)]
    for index, query in enumerate(destination_queries):
        coordinate = provided_destinations[index] if index < len(provided_destinations) else None
        stops.append(coordinate or _geocode_route_stop(query))
    if len(stops) < 2:
        raise HTTPException(status_code=422, detail="At least one pickup and one delivery point are required.")
    return stops


def _request_routing_routes(stops: list[Coordinates], alternatives: bool = True) -> list[dict]:
    coordinate_path = ";".join(f"{point.longitude:.6f},{point.latitude:.6f}" for point in stops)
    url = f"{ROUTING_URL}/route/v1/{ROUTING_PROFILE}/{coordinate_path}"
    params = {
        "alternatives": "true" if alternatives else "false",
        "overview": "full",
        "geometries": "geojson",
        "steps": "true",   # intersections per step feed the road-safety score
    }
    try:
        with httpx.Client(
            timeout=PROVIDER_TIMEOUT_SECONDS,
            follow_redirects=True,
            headers={"Accept": "application/json", "User-Agent": "AniRoute/1.0 (live routing)"},
        ) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Live route service is unavailable.") from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="Live route service returned invalid data.") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=502, detail="Live route service returned an unexpected response.")
    if payload.get("code") != "Ok":
        provider_message = payload.get("message")
        detail = "No drivable route could be found for the selected locations."
        if isinstance(provider_message, str) and provider_message.strip():
            detail = f"No drivable route could be found: {provider_message.strip()}"
        raise HTTPException(status_code=422, detail=detail)
    raw_routes = payload.get("routes")
    if not isinstance(raw_routes, list) or not raw_routes:
        raise HTTPException(status_code=422, detail="No route options were returned for the selected locations.")
    return [route for route in raw_routes if isinstance(route, dict)]


# OSRM often returns a single route for long trips. To still offer real choices, we also route through a
# detour point on each side of the direct line (fractions of the trip length) and keep only genuinely
# different roads: no out-and-back spurs, little overlap with routes we already have, not absurdly slow.
VIA_OFFSETS = (0.08, -0.08, 0.04, -0.04, -0.15, 0.15, 0.12, -0.12)
MAX_ALTERNATIVE_SLOWDOWN = 1.6
MAX_SHARED_FRACTION = 0.9
TARGET_ROUTES = 5   # score up to five real roads, then offer the best three distinct ones


def _route_points(raw_route: dict) -> list[tuple[float, float]]:
    geometry = raw_route.get("geometry")
    coordinates = geometry.get("coordinates") if isinstance(geometry, dict) else None
    if not isinstance(coordinates, list):
        return []
    return [(round(float(p[0]), 3), round(float(p[1]), 3)) for p in coordinates
            if isinstance(p, (list, tuple)) and len(p) >= 2 and isinstance(p[0], (int, float)) and isinstance(p[1], (int, float))]


def _has_spur(points: list[tuple[float, float]]) -> bool:
    """A detour that drives out to the via point and back retraces the same road: repeated points."""
    path = [point for index, point in enumerate(points) if index == 0 or point != points[index - 1]]
    return len(path) > 10 and (len(path) - len(set(path))) / len(path) > 0.03


def _shared_fraction(points: list[tuple[float, float]], others: list[set]) -> float:
    if not points or not others:
        return 0.0
    unique = set(points)
    return max(len(unique & other) / len(unique) for other in others)


def _with_detour_alternatives(stops: list[Coordinates], raw_routes: list[dict]) -> list[dict]:
    if len(stops) != 2 or len(raw_routes) >= TARGET_ROUTES:
        return raw_routes
    durations = [r["duration"] for r in raw_routes if isinstance(r.get("duration"), (int, float))]
    if not durations:
        return raw_routes
    fastest = min(durations)
    kept = list(raw_routes)
    point_sets = [set(_route_points(r)) for r in kept]
    start, end = stops
    dx, dy = end.longitude - start.longitude, end.latitude - start.latitude
    length = (dx ** 2 + dy ** 2) ** 0.5
    if length < 0.05:   # under ~5 km: detours make no sense
        return raw_routes
    nx, ny = -dy / length, dx / length
    mid_lon, mid_lat = (start.longitude + end.longitude) / 2, (start.latitude + end.latitude) / 2
    for offset in VIA_OFFSETS:
        if len(kept) >= TARGET_ROUTES:
            break
        via = Coordinates(latitude=mid_lat + ny * length * offset, longitude=mid_lon + nx * length * offset)
        try:
            candidates = _request_routing_routes([start, via, end], alternatives=False)
        except HTTPException:
            continue
        for candidate in candidates[:1]:
            points = _route_points(candidate)
            duration = candidate.get("duration")
            if (not isinstance(duration, (int, float)) or duration > fastest * MAX_ALTERNATIVE_SLOWDOWN
                    or _has_spur(points) or _shared_fraction(points, point_sets) > MAX_SHARED_FRACTION):
                continue
            kept.append(candidate)
            point_sets.append(set(points))
    return kept


# Absolute exposure scales for the score breakdown (0-100): 8 h on the road or 500 km = 100.
TIME_EXPOSURE_FULL_MINUTES = 480
DISTANCE_EXPOSURE_FULL_KM = 500


def _crop_fragility(crop: str) -> int:
    """0-100: how easily the crop bruises or wilts in transport (heuristic, not a measured loss rate)."""
    return {12: 90, 8: 65, 4: 30}[_crop_sensitivity(crop)]


def _crop_sensitivity(crop: str) -> int:
    if re.search(r"leafy|lettuce|pechay|spinach|herb", crop, re.IGNORECASE):
        return 12
    if re.search(r"banana|mango|onion|garlic|potato", crop, re.IGNORECASE):
        return 4
    return 8


def _risk_label(score: int) -> str:
    return "higher" if score >= 60 else "moderate" if score >= 35 else "lower"


def _assign_options(routes: list[dict]) -> dict[str, dict]:
    """Three options on three different roads, each labelled truthfully.

    Recommended = best overall. Fastest = least time; if the recommended road is itself the fastest, the
    orange option is the quickest *other* road and is called "Fastest alternative". Safest works the same
    way, using the road-safety risk, among roads not already offered.
    """
    recommended = next(route for route in routes if route["recommended"])
    time = lambda route: route["travel_time_minutes"]                       # noqa: E731
    risk = lambda route: (route["risk_factors"]["safety"], route["travel_time_minutes"])  # noqa: E731
    options = {recommended["route_id"]: {"key": "optimal", "title": "Recommended route",
                                         "note": "Best balance of time, distance, crop and road safety"}}
    others = [route for route in routes if route["route_id"] != recommended["route_id"]]
    if not others:
        return options

    fastest_overall = min(routes, key=time)
    if fastest_overall["route_id"] != recommended["route_id"]:
        fastest, title = fastest_overall, "Fastest route"
        note = f"{time(recommended) - time(fastest)} min quicker than recommended"
    else:
        fastest, title = min(others, key=time), "Fastest alternative"
        note = f"Recommended road is also the fastest · quickest other road, +{time(fastest) - time(recommended)} min"
    options[fastest["route_id"]] = {"key": "fastest", "title": title, "note": note}

    remaining = [route for route in others if route["route_id"] not in options]
    if not remaining:
        return options
    safest_overall = min(routes, key=risk)
    if safest_overall["route_id"] not in options:
        safest, title = safest_overall, "Safest route"
        note = f"Lowest road-safety risk ({risk(safest)[0]} vs {risk(recommended)[0]} recommended)"
    else:
        safest = min(remaining, key=risk)
        title = "Safest alternative"
        best_other = min(others, key=risk)
        note = (f"Lowest-risk other road · safety risk {risk(safest)[0]}"
                if best_other["route_id"] == safest["route_id"]
                else f"Lowest-risk road not shown above · safety risk {risk(safest)[0]}")
    options[safest["route_id"]] = {"key": "safer", "title": title, "note": note}
    return options


def _live_routes(trip: TripInput, keep_route_id: str | None = None) -> dict:
    if not LIVE_ROUTING_ENABLED:
        raise HTTPException(status_code=503, detail="Live route engine is disabled. Set ANIROUTE_LIVE_ROUTING_ENABLED=true.")

    stops = _resolve_trip_stops(trip)
    raw_routes = _with_detour_alternatives(stops, _request_routing_routes(stops))
    candidates: list[dict] = []
    for raw_route in raw_routes[:TARGET_ROUTES]:
        geometry = raw_route.get("geometry")
        coordinates = geometry.get("coordinates") if isinstance(geometry, dict) else None
        duration = raw_route.get("duration")
        distance = raw_route.get("distance")
        if not isinstance(coordinates, list) or len(coordinates) < 2:
            continue
        if not isinstance(duration, (int, float)) or not isinstance(distance, (int, float)):
            continue
        clean_coordinates = [
            [float(point[0]), float(point[1])]
            for point in coordinates
            if isinstance(point, (list, tuple)) and len(point) >= 2
            and isinstance(point[0], (int, float)) and isinstance(point[1], (int, float))
        ]
        if len(clean_coordinates) < 2 or duration <= 0 or distance <= 0:
            continue
        candidates.append({
            "raw": raw_route,
            "coordinates": clean_coordinates,
            "duration_minutes": max(1, float(duration) / 60),
            "distance_km": float(distance) / 1000,
        })

    if not candidates:
        raise HTTPException(status_code=502, detail="Live route service returned no usable route geometry.")

    minimum_duration = min(route["duration_minutes"] for route in candidates)
    minimum_distance = min(route["distance_km"] for route in candidates)
    crop_shift = _crop_sensitivity(trip.crop)
    # Sensitive crops (leafy vegetables, tomatoes) are penalised more by rough or flooded roads.
    crop_road_multiplier = 0.6 + crop_shift / 20
    observations = hazard_risk.load_observations(DATA_DIR / "hazard_observations.jsonl")
    for route in candidates:
        route["road_factor"], route["hazard_pins"] = hazard_risk.assess_route(route["coordinates"], observations)
        # Road safety for produce: curves, stop-and-go and confirmed hazards (road_safety.py).
        route.update(road_safety.assess(route["coordinates"], route["raw"], route["distance_km"], route["road_factor"]))
        route["time_factor"] = _clamp((route["duration_minutes"] / minimum_duration - 1) * 100)
        route["distance_factor"] = _clamp((route["distance_km"] / minimum_distance - 1) * 100)
        # Breakdown shown to the driver: absolute exposure of this trip, so every factor has a real value.
        route["time_exposure"] = _clamp(route["duration_minutes"] / TIME_EXPOSURE_FULL_MINUTES * 100)
        route["distance_exposure"] = _clamp(route["distance_km"] / DISTANCE_EXPOSURE_FULL_KM * 100)
        route["crop_fragility"] = _crop_fragility(trip.crop)
        route["crop_risk_score"] = _clamp(
            route["time_exposure"] * 0.30 + route["distance_exposure"] * 0.15 + route["crop_fragility"] * 0.25
            + route["safety_risk"] * 0.5 * crop_road_multiplier,
        )
        route["combined_score"] = (
            (route["time_factor"] * 0.5) + (route["distance_factor"] * 0.25) + (route["crop_risk_score"] * 0.25)
            + route["safety_risk"] * 0.6 * crop_road_multiplier
        )

    fastest_index = min(range(len(candidates)), key=lambda index: (candidates[index]["duration_minutes"], index))
    safest_index = min(range(len(candidates)), key=lambda index: (candidates[index]["safety_risk"], candidates[index]["duration_minutes"], index))
    optimal_index = min(range(len(candidates)), key=lambda index: (candidates[index]["combined_score"], index))
    # Recommended = best balance of time, distance, crop fragility and road safety; fastest = least time;
    # safest = fewest curves, stops and confirmed hazards. One road can win several (it then carries each label).
    category_indexes = {"optimal": optimal_index, "fastest": fastest_index, "safer": safest_index}
    route_categories: dict[int, list[str]] = {}
    for category, index in category_indexes.items():
        route_categories.setdefault(index, []).append(category)

    route_data: list[dict] = []
    for index, candidate in enumerate(candidates):
        categories = route_categories.get(index, [])
        category = ("optimal" if "optimal" in categories else "fastest" if "fastest" in categories
                    else "safer" if "safer" in categories else "alternative")
        # Stable id per provider route, so the active trip keeps pointing at the same road
        # geometry even when a confirmed hazard changes which route is "optimal".
        route_id = f"route-{index + 1}"
        hazard_summary = hazard_risk.summarize_hazards(candidate["hazard_pins"])
        route_data.append({
            "route_id": route_id,
            "category": category,
            "categories": categories,
            "geometry": {"type": "LineString", "coordinates": candidate["coordinates"]},
            "travel_time_minutes": max(1, round(candidate["duration_minutes"])),
            "distance_km": round(candidate["distance_km"], 1),
            "road_condition_summary": (
                (f"{hazard_summary} (AniRoute camera, driver-confirmed). " if hazard_summary
                 else "No camera-confirmed road hazards yet. ")
                + f"Curves {candidate['curves_deg_per_km']:.0f}°/km · {candidate['intersections_per_km']:.1f} intersections/km."
            ),
            "crop_risk_score": candidate["crop_risk_score"],
            "crop_risk_label": _risk_label(candidate["crop_risk_score"]),
            "risk_factors": {
                "travelTime": candidate["time_exposure"],
                "distance": candidate["distance_exposure"],
                "crop": candidate["crop_fragility"],
                "road": candidate["road_factor"],
                "safety": candidate["safety_risk"],
            },
            "crop_profile_summary": "Score = 30% time on the road + 15% distance + 25% crop fragility + road safety (curves, stop-and-go, confirmed hazards). A transport-risk guide, not a spoilage percentage.",
            "explanation": (
                f"{hazard_summary}. Each confirmed hazard within 75 m of the route raises its road factor."
                if hazard_summary else ""
            ),
            "recommended": index == optimal_index,
            "extra_minutes": max(0, round(candidate["duration_minutes"] - minimum_duration)),
            "known_hazards": candidate["hazard_pins"],
        })

    # Offer three options on three different roads (see _assign_options); every road is still scored, so
    # the choice changes when a confirmed hazard makes a road riskier. The road a driver is already on
    # always stays listed.
    options = _assign_options(route_data)
    for route in route_data:
        route["option"] = options.get(route["route_id"])
    route_data = [route for route in route_data if route["option"] or route["route_id"] == keep_route_id]
    order = {"optimal": 0, "fastest": 1, "safer": 2}
    route_data.sort(key=lambda route: order.get((route["option"] or {}).get("key", ""), 3))
    recommended_route = next(route for route in route_data if route["recommended"])
    return {
        "routes": route_data,
        "data_source": "api",
        "recommended_route_id": recommended_route["route_id"],
        "message": "Live road geometry and ETA from OSRM, scored with camera-confirmed road hazards.",
    }


def _decode_evidence(data_url: str | None, observation_id: str) -> str | None:
    if not data_url:
        return None
    match = re.fullmatch(r"data:image/(jpeg|jpg|png);base64,([A-Za-z0-9+/=]+)", data_url)
    if not match:
        raise HTTPException(status_code=422, detail="Evidence must be a JPEG or PNG camera frame.")
    ext = "jpg" if match.group(1) in {"jpeg", "jpg"} else "png"
    try:
        content = base64.b64decode(match.group(2), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=422, detail="Evidence frame is not valid base64.") from exc
    if len(content) > 1_000_000:
        raise HTTPException(status_code=413, detail="Evidence frame must be 1 MB or smaller.")
    evidence_dir = DATA_DIR / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    file_path = evidence_dir / f"{observation_id}.{ext}"
    file_path.write_bytes(content)
    return str(file_path.relative_to(DATA_DIR))


@asynccontextmanager
async def lifespan(_: FastAPI):
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    detector = get_detector()
    if detector.settings.warmup:
        detector.warmup_async()  # loads both models in the background; API is usable immediately
    yield


app = FastAPI(
    title="AniRoute API",
    version="2.0.0",
    description=(
        "AniRoute crop-aware routing (OSRM) with real-time road-hazard detection: a fine-tuned YOLO "
        "road-surface model and a COCO-pretrained YOLO obstruction model."
    ),
    lifespan=lifespan,
)

origins = [value.strip() for value in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173,http://127.0.0.1:4173").split(",") if value.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Accept", "Range"],
    expose_headers=["Content-Range", "Accept-Ranges", "Content-Length"],
)
app.include_router(vision_router)
# Report images (confusion matrix, curves, error gallery) and sample media (recorded drive for the trip page).
app.mount("/reports", StaticFiles(directory=str(REPORTS_DIR), check_dir=False), name="reports")
app.mount("/samples", StaticFiles(directory=str(SAMPLES_DIR), check_dir=False), name="samples")


@app.get("/api/health")
def health() -> dict:
    detector = get_detector()
    status = detector.status()
    return {
        "status": "ok",
        "service": "aniroute-api",
        "data_source": "api",
        "live_route_engine": LIVE_ROUTING_ENABLED,
        "live_hazard_detection": detector.ready,
        "vision_warming_up": status["warming_up"],
        "supported_hazards": status["supported_hazards"],
    }


@app.get("/api/geocode/search")
async def search_locations(
    q: str = Query(..., min_length=2, max_length=180),
    limit: int = Query(6, ge=1, le=8),
) -> list[dict]:
    query = q.strip()
    if len(query) < 2:
        raise HTTPException(status_code=422, detail="Search for at least two characters.")

    params = {
        "q": query,
        "format": "jsonv2",
        "addressdetails": "1",
        "limit": str(limit),
    }
    try:
        async with httpx.AsyncClient(
            timeout=8.0,
            follow_redirects=True,
            headers={"Accept": "application/json", "Accept-Language": "en", "User-Agent": GEOCODER_USER_AGENT},
        ) as client:
            response = await client.get(GEOCODER_URL, params=params)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Location search service is unavailable.") from exc

    try:
        raw_results = response.json()
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="Location search returned invalid data.") from exc

    if not isinstance(raw_results, list):
        raise HTTPException(status_code=502, detail="Location search returned an unexpected response.")

    results: list[dict] = []
    for item in raw_results:
        if not isinstance(item, dict):
            continue
        display_name = item.get("display_name")
        latitude = item.get("lat")
        longitude = item.get("lon")
        if not display_name or latitude is None or longitude is None:
            continue
        results.append({
            "place_id": item.get("place_id") or item.get("osm_id"),
            "display_name": display_name,
            "lat": latitude,
            "lon": longitude,
            "category": item.get("category", ""),
            "type": item.get("type", ""),
        })
    return results


@app.post("/api/routes/calculate")
def calculate_routes(trip: TripInput) -> dict:
    return _live_routes(trip)


@app.post("/api/routes/recalculate")
def recalculate_routes(payload: RecalculateInput) -> dict:
    result = _live_routes(payload.trip, keep_route_id=payload.active_route_id)
    recommended_id = result["recommended_route_id"]
    result["changed"] = recommended_id != payload.active_route_id
    active = next((route for route in result["routes"] if route["route_id"] == payload.active_route_id), None)
    hazard_name = hazard_risk.HAZARD_NAMES.get(payload.hazard_type, "road hazard").lower()
    if active is None:
        detail = "The active route is no longer offered by the routing service; showing current options."
    elif active["known_hazards"]:
        detail = f"Your route now carries {len(active['known_hazards'])} confirmed hazard(s), including the {hazard_name} you confirmed."
    else:
        detail = (
            f"The confirmed {hazard_name} has no saved location near this route, so it could not change the road-risk score."
        )
    outcome = "A different route is now recommended." if result["changed"] else "Your current route is still the best option."
    result["message"] = f"Route options re-scored after the confirmed {hazard_name}. {detail} {outcome}"
    return result


@app.post("/api/hazards/scanning/start")
def start_scanning(payload: ScanStart) -> dict:
    detector = get_detector()
    ready = detector.load()
    get_hazard_filter().reset(payload.route_id)
    hazards = detector.supported_hazards()
    names = ", ".join(hazard_risk.HAZARD_NAMES[item].lower() for item in hazards)
    return {
        "route_id": payload.route_id,
        "mode": "live",
        "detection_available": ready,
        "supported_hazards": hazards,
        "message": (
            f"Road analysis is running on the AniRoute detector ({names})." if ready
            else "No detection model is loaded on the server. Add trained weights to backend/models/."
        ),
    }


@app.post("/api/hazards/scanning/stop")
def stop_scanning(payload: ScanStart) -> dict:
    get_hazard_filter().reset(payload.route_id)
    return {"route_id": payload.route_id, "scanning": False, "message": "Road analysis stopped."}


def _segment_id(route_id: str, coordinates: tuple[float, float] | None) -> str:
    if coordinates is None:
        return f"{route_id}@unlocated"
    return f"{route_id}@{coordinates[0]:.4f},{coordinates[1]:.4f}"


@app.post("/api/hazards/scan-frame")
def scan_frame(payload: ScanFrame) -> dict:
    """Detect hazards in one camera frame and apply temporal smoothing for the active route.

    `detections` (every box in this frame) drives the live overlay; `detection` is only
    set when a hazard has been seen in enough recent frames to alert the driver.
    Frames are processed in memory and never stored unless the driver confirms.
    """
    detector = get_detector()
    if not detector.load():
        return {
            "route_id": payload.route_id, "detection_available": False, "detection": None, "detections": [],
            "data_source": "api", "frame_stored": False,
            "message": "No detection model is loaded on the server.",
        }
    try:
        frame_bytes = decode_data_url(payload.frame_data_url)
    except ImageDecodeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    result = run_detection(frame_bytes)
    detections = [item.to_dict() for item in result.detections]
    coordinates = (payload.latitude, payload.longitude) if payload.latitude is not None and payload.longitude is not None else None
    confirmed = get_hazard_filter().update(payload.route_id, detections, coordinates)

    detection = None
    evidence = None
    if confirmed:
        detection = {
            "detection_id": confirmed["id"],
            "hazard_type": confirmed["hazard_type"],
            "label": confirmed["label"],
            "source_label": confirmed["source_label"],
            "model": confirmed["model"],
            "detected_at": payload.captured_at.isoformat(),
            "confidence": confirmed["confidence"],
            "latitude": payload.latitude,
            "longitude": payload.longitude,
            "route_id": payload.route_id,
            "road_segment_id": _segment_id(payload.route_id, coordinates),
            "distance_ahead_km": None,
            "frames_seen": confirmed["frames_seen"],
            "window": confirmed["window"],
        }
        evidence = encode_jpeg_data_url(draw_detections(result.pipeline.enhanced, [confirmed]), quality=74, max_side=720)

    return {
        "route_id": payload.route_id,
        "detection_available": True,
        "detections": detections,
        "image": {"width": result.image_width, "height": result.image_height},
        "timings_ms": result.timings_ms,
        "models_used": result.models_used,
        "detection": detection,
        "evidence_frame_data_url": evidence,
        "data_source": "api",
        "frame_stored": False,
        "message": "Hazard confirmed across recent frames." if detection else "Frame analysed.",
    }


@app.post("/api/hazards/confirm")
def confirm_hazard(payload: HazardConfirmation) -> dict:
    observation_id = str(uuid.uuid4())
    evidence_path = _decode_evidence(payload.evidence_frame_data_url, observation_id)
    record = payload.model_dump(mode="json", exclude={"evidence_frame_data_url"})
    record.update({
        "observation_id": observation_id,
        "data_source": "api",
        "stored_at": datetime.now(timezone.utc).isoformat(),
        "evidence_frame_path": evidence_path,
    })
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with _write_lock:
        with (DATA_DIR / "hazard_observations.jsonl").open("a", encoding="utf-8") as file:
            file.write(json.dumps(record, separators=(",", ":")) + "\n")
    located = payload.latitude is not None and payload.longitude is not None
    return {
        "observation_id": observation_id,
        "status": "uploaded",
        "data_source": "api",
        "stored_at": record["stored_at"],
        "evidence_stored": evidence_path is not None,
        "message": (
            "Road hazard saved with its location. Routes passing within 75 m now carry this risk."
            if located and not payload.simulated else
            "Road hazard saved. Without a GPS location it cannot be matched to a route."
            if not located else
            "Test hazard saved (marked simulated); it is excluded from route scoring."
        ),
    }
