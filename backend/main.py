from __future__ import annotations

import base64
import binascii
import json
import os
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, model_validator


DataSource = Literal["demo"]
HazardType = Literal["pothole", "severe_road_damage", "standing_water", "road_obstruction"]

APP_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("ANIROUTE_DATA_DIR", str(APP_DIR / "data")))
GEOCODER_URL = "https://nominatim.openstreetmap.org/search"
GEOCODER_USER_AGENT = os.getenv("ANIROUTE_GEOCODER_USER_AGENT", "AniRoute/1.0 (local demo geocoder proxy)")
_write_lock = threading.Lock()


class TripInput(BaseModel):
    crop: str = Field(min_length=1, max_length=60)
    quantity: float = Field(gt=0, le=100_000)
    unit: Literal["kg"] = "kg"
    vehicle: str = Field(min_length=1, max_length=60)
    origin: str = Field(min_length=1, max_length=180)
    destination: str = Field(min_length=1, max_length=180)


class HazardConfirmation(BaseModel):
    hazard_type: HazardType
    detected_at: datetime
    confidence: float | None = Field(default=None, ge=0, le=1)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    route_id: str = Field(min_length=1, max_length=100)
    road_segment_id: str = Field(min_length=1, max_length=100)
    distance_ahead_km: float | None = Field(default=None, ge=0, le=100)
    simulated: bool = True
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
    frame_data_url: str = Field(min_length=30, max_length=180_000)

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
        if len(raw) > 125_000:
            raise ValueError("Camera frame must be 125 KB or smaller.")
        return self


class RecalculateInput(BaseModel):
    trip: TripInput
    active_route_id: str = Field(min_length=1, max_length=100)
    hazard_type: HazardType
    road_segment_id: str = Field(min_length=1, max_length=100)
    observation_id: str = Field(min_length=1, max_length=100)


def _demo_hazard() -> dict:
    return {
        "id": "demo-standing-water",
        "name": "Standing water",
        "coordinates": {"latitude": 6.428, "longitude": 124.895},
        "note": "Sample road note · demo only",
    }


def _routes(trip: TripInput, affected_route_id: str | None = None) -> list[dict]:
    # Demo geometry is an illustration for one corridor, not a routable road graph.
    lines = {
        "optimal": [[124.957, 6.359], [124.942, 6.382], [124.925, 6.406], [124.904, 6.431], [124.882, 6.463], [124.858, 6.493], [124.852, 6.503]],
        "safer": [[124.957, 6.359], [124.944, 6.378], [124.934, 6.402], [124.915, 6.432], [124.892, 6.462], [124.870, 6.486], [124.852, 6.503]],
        "fastest": [[124.957, 6.359], [124.939, 6.378], [124.922, 6.405], [124.900, 6.431], [124.881, 6.461], [124.862, 6.488], [124.852, 6.503]],
    }
    default_origin = "farm pickup point, tupi"
    default_destination = "koronadal trading post"
    origin = trip.origin.strip().lower()
    destination = trip.destination.strip().lower()
    location_text = f"{origin}|{destination}"
    location_shift = 0 if (origin, destination) == (default_origin, default_destination) else 1 + sum(map(ord, location_text)) % 6
    vehicle_time_shift = -2 if trip.vehicle == "Pickup" else 7 if trip.vehicle == "Medium truck" else 0 if trip.vehicle == "Small truck" else 3
    load_delta = trip.quantity - 250
    load_ratio = load_delta / 250
    rounded_load_steps = int(load_ratio + 0.5) if load_ratio >= 0 else int(load_ratio - 0.5)
    if load_delta and rounded_load_steps == 0:
        rounded_load_steps = 1 if load_delta > 0 else -1
    load_time_shift = max(-4, min(10, rounded_load_steps))
    load_risk_shift = max(0, min(24, rounded_load_steps * 4))
    vehicle_risk_shift = 4 if trip.vehicle == "Medium truck" else 0
    time_shift = vehicle_time_shift + load_time_shift + location_shift * 2
    distance_shift = location_shift * 0.6
    crop_shift = 5 if re.search(r"leafy|lettuce|pechay", trip.crop, re.I) else -2 if re.search(r"banana|mango", trip.crop, re.I) else 0
    def risk_label(score: int) -> str:
        return "higher" if score >= 60 else "moderate" if score >= 35 else "lower"

    data = [
        {
            "route_id": "optimal", "category": "optimal", "geometry": {"type": "LineString", "coordinates": lines["optimal"]},
            "travel_time_minutes": 54 + time_shift, "distance_km": round(32.4 + distance_shift, 1), "road_condition_summary": "Mostly smooth road",
            "weather_flood_summary": "Some rain exposure · no live forecast", "temperature_exposure_summary": "Mild exposure · sample only", "crop_risk_score": 28 + crop_shift + load_risk_shift + vehicle_risk_shift,
            "crop_risk_label": risk_label(28 + crop_shift + load_risk_shift + vehicle_risk_shift), "explanation": "Balances travel time, distance, road condition, sample weather, temperature and crop sensitivity.",
            "recommended": True, "known_hazards": [],
        },
        {
            "route_id": "safer", "category": "safer", "geometry": {"type": "LineString", "coordinates": lines["safer"]},
            "travel_time_minutes": 66 + time_shift, "distance_km": round(37.8 + distance_shift, 1), "road_condition_summary": "Fewer known rough sections",
            "weather_flood_summary": "Lower sample flood exposure", "temperature_exposure_summary": "Lower heat exposure · sample", "crop_risk_score": 18 + crop_shift + load_risk_shift + vehicle_risk_shift,
            "crop_risk_label": risk_label(18 + crop_shift + load_risk_shift + vehicle_risk_shift), "explanation": "Takes longer but has lower known road and flood risk in this sample.",
            "recommended": False, "known_hazards": [],
        },
        {
            "route_id": "fastest", "category": "fastest", "geometry": {"type": "LineString", "coordinates": lines["fastest"]},
            "travel_time_minutes": 43 + time_shift, "distance_km": round(28.7 + distance_shift, 1), "road_condition_summary": "One rough road section",
            "weather_flood_summary": "Standing water noted · sample only", "temperature_exposure_summary": "Higher afternoon heat exposure · sample", "crop_risk_score": min(95, 63 + crop_shift + load_risk_shift + vehicle_risk_shift),
            "crop_risk_label": risk_label(min(95, 63 + crop_shift + load_risk_shift + vehicle_risk_shift)), "explanation": "Shortest estimated drive time, with a sample standing-water concern.",
            "recommended": False, "known_hazards": [_demo_hazard()],
        },
    ]
    if affected_route_id:
        affected = next((route for route in data if route["route_id"] == affected_route_id), None)
        if affected:
            affected["crop_risk_score"] = min(95, affected["crop_risk_score"] + 28)
            affected["crop_risk_label"] = "higher" if affected["crop_risk_score"] >= 60 else "moderate"
            affected["road_condition_summary"] = "New road hazard confirmed · sample update"
            affected["explanation"] = "A confirmed sample road note changed this route’s risk information."
        for route in data:
            route["recommended"] = route["route_id"] == "safer"
        recommendation_id = "optimal" if affected_route_id == "safer" else "safer"
        recommendation = next(route for route in data if route["route_id"] == recommendation_id)
        recommendation["explanation"] = f"Recommended after a confirmed sample hazard changed the {affected_route_id} route conditions."
    return data


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


app = FastAPI(
    title="AniRoute Demo API",
    version="1.0.0",
    description="Runnable demo contract for the AniRoute frontend. Route scores and findings are sample data.",
)

origins = [value.strip() for value in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if value.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Accept"],
)


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "aniroute-demo-api",
        "data_source": "demo",
        "live_route_engine": False,
        "live_hazard_detection": False,
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
    routes = _routes(trip)
    return {
        "routes": routes,
        "data_source": "demo",
        "recommended_route_id": "optimal",
        "message": "Sample route options · road, weather and risk information is not live.",
    }


@app.post("/api/routes/recalculate")
def recalculate_routes(payload: RecalculateInput) -> dict:
    routes = _routes(payload.trip, affected_route_id=payload.active_route_id)
    recommendation_id = "optimal" if payload.active_route_id == "safer" else "safer"
    return {
        "routes": routes,
        "data_source": "demo",
        "recommended_route_id": recommendation_id,
        "changed": payload.active_route_id != recommendation_id,
        "message": "Sample routes checked after the confirmed road finding.",
    }


@app.post("/api/hazards/scanning/start")
def start_scanning(payload: ScanStart) -> dict:
    return {
        "route_id": payload.route_id,
        "mode": "demo",
        "detection_available": False,
        "message": "Camera access is handled in the browser. Live computer vision is not connected; only labelled sample detections are available.",
    }


@app.post("/api/hazards/scanning/stop")
def stop_scanning(payload: ScanStart) -> dict:
    return {"route_id": payload.route_id, "scanning": False, "message": "Demo scanning stopped."}


@app.post("/api/hazards/scan-frame")
def scan_frame(payload: ScanFrame) -> dict:
    return {
        "route_id": payload.route_id,
        "detection_available": False,
        "detection": None,
        "data_source": "demo",
        "frame_stored": False,
        "message": "No live computer-vision model is connected. The demo does not store scan frames.",
    }


@app.post("/api/hazards/confirm")
def confirm_hazard(payload: HazardConfirmation) -> dict:
    observation_id = str(uuid.uuid4())
    evidence_path = _decode_evidence(payload.evidence_frame_data_url, observation_id)
    record = payload.model_dump(mode="json", exclude={"evidence_frame_data_url"})
    record.update({
        "observation_id": observation_id,
        "data_source": "demo",
        "stored_at": datetime.now(timezone.utc).isoformat(),
        "evidence_frame_path": evidence_path,
    })
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with _write_lock:
        with (DATA_DIR / "hazard_observations.jsonl").open("a", encoding="utf-8") as file:
            file.write(json.dumps(record, separators=(",", ":")) + "\n")
    return {
        "observation_id": observation_id,
        "status": "uploaded",
        "data_source": "demo",
        "stored_at": record["stored_at"],
        "evidence_stored": evidence_path is not None,
        "message": "Road update saved to the local demo API. Live road-risk storage is not connected.",
    }
