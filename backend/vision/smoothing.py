"""Temporal smoothing that turns per-frame detections into driver alerts.

A single frame can contain a false positive (shadow, wet patch, motion blur). The
driver is only alerted when the same hazard class appears in at least `min_hits`
of the last `window` frames. After an alert the class is muted for `cooldown`
seconds, and a new alert of the same class within `dedupe_m` metres of an earlier
one is suppressed.
"""
from __future__ import annotations

import math
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Callable


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6_371_000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi, d_lambda = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(min(1.0, a)))


@dataclass
class _RouteState:
    frames: deque = field(default_factory=deque)
    last_alert_at: dict[str, float] = field(default_factory=dict)
    alert_locations: dict[str, list[tuple[float, float]]] = field(default_factory=dict)


class TemporalHazardFilter:
    def __init__(self, window: int = 3, min_hits: int = 2, cooldown_s: float = 20.0, dedupe_m: float = 50.0,
                 clock: Callable[[], float] = time.monotonic) -> None:
        if window < 1 or not 1 <= min_hits <= window:
            raise ValueError("Require 1 <= min_hits <= window.")
        self.window = window
        self.min_hits = min_hits
        self.cooldown_s = cooldown_s
        self.dedupe_m = dedupe_m
        self.clock = clock
        self._routes: dict[str, _RouteState] = {}
        self._lock = threading.Lock()
        self.stats = {"frames": 0, "frames_with_detections": 0, "alerts": 0, "suppressed_cooldown": 0, "suppressed_duplicate": 0}

    def reset(self, route_id: str | None = None) -> None:
        with self._lock:
            if route_id is None:
                self._routes.clear()
            else:
                self._routes.pop(route_id, None)

    def update(self, route_id: str, detections: list[dict], coordinates: tuple[float, float] | None = None,
               now: float | None = None) -> dict | None:
        """Feed one frame's detections; return the detection to alert on, or None.

        `detections` are dicts with at least `hazard_type` and `confidence`.
        """
        now = self.clock() if now is None else now
        with self._lock:
            state = self._routes.setdefault(route_id, _RouteState(frames=deque(maxlen=self.window)))
            best_per_type: dict[str, dict] = {}
            for item in detections:
                current = best_per_type.get(item["hazard_type"])
                if current is None or item["confidence"] > current["confidence"]:
                    best_per_type[item["hazard_type"]] = item
            state.frames.append(set(best_per_type))
            self.stats["frames"] += 1
            if best_per_type:
                self.stats["frames_with_detections"] += 1

            for hazard_type, item in sorted(best_per_type.items(), key=lambda pair: pair[1]["confidence"], reverse=True):
                hits = sum(1 for frame in state.frames if hazard_type in frame)
                if hits < self.min_hits:
                    continue
                last = state.last_alert_at.get(hazard_type)
                if last is not None and now - last < self.cooldown_s:
                    self.stats["suppressed_cooldown"] += 1
                    continue
                if coordinates is not None and any(
                    haversine_m(coordinates[0], coordinates[1], lat, lon) <= self.dedupe_m
                    for lat, lon in state.alert_locations.get(hazard_type, [])
                ):
                    self.stats["suppressed_duplicate"] += 1
                    continue
                state.last_alert_at[hazard_type] = now
                if coordinates is not None:
                    state.alert_locations.setdefault(hazard_type, []).append(coordinates)
                # Remove this class from the window so the same streak cannot alert twice.
                for frame in state.frames:
                    frame.discard(hazard_type)
                self.stats["alerts"] += 1
                return {**item, "frames_seen": hits, "window": self.window}
            return None
