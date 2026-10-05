"""Stable contracts for experimental multi-device follow tests."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Mapping


def _point(value: Any, name: str) -> tuple[float, float]:
    if value is None or len(value) != 2:
        raise ValueError(f"{name} must contain two values")
    point = (float(value[0]), float(value[1]))
    if not all(math.isfinite(item) for item in point):
        raise ValueError(f"{name} must contain finite values")
    return point


@dataclass(frozen=True, slots=True)
class RoleId:
    device_id: str
    actor_id: str

    def __post_init__(self) -> None:
        device = str(self.device_id).strip()
        actor = str(self.actor_id).strip()
        if not device or not actor or len(device) > 64 or len(actor) > 64:
            raise ValueError("role identity must contain bounded non-empty strings")
        object.__setattr__(self, "device_id", device)
        object.__setattr__(self, "actor_id", actor)

    @property
    def key(self) -> str:
        return f"{self.device_id}:{self.actor_id}"


@dataclass(frozen=True, slots=True)
class MapIdentity:
    map_id: str
    map_version: str

    def __post_init__(self) -> None:
        map_id = str(self.map_id).strip()
        version = str(self.map_version).strip()
        if not map_id or not version:
            raise ValueError("map identity requires map_id and map_version")
        object.__setattr__(self, "map_id", map_id)
        object.__setattr__(self, "map_version", version)


class ControlMode(StrEnum):
    MANUAL = "manual"
    PREVIEW = "preview"
    SIMULATED = "simulated"
    PROGRAM = "program"


class FollowState(StrEnum):
    IDLE = "idle"
    PREVIEWING = "previewing"
    SIMULATING = "simulating"
    PROGRAM_READY = "program_ready"
    ARRIVED = "arrived"
    WAITING_POSITION = "waiting_position"
    BLOCKED = "blocked"
    MANUAL = "manual"
    MAP_MISMATCH = "map_mismatch"


@dataclass(frozen=True, slots=True)
class PositionSample:
    role: RoleId
    map_identity: MapIdentity
    position: tuple[float, float]
    captured_at_ms: int
    confidence: float
    source: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "position", _point(self.position, "position"))
        captured_at = int(self.captured_at_ms)
        confidence = float(self.confidence)
        source = str(self.source).strip()
        if captured_at < 0 or not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
            raise ValueError("position timestamp/confidence is invalid")
        if not source:
            raise ValueError("position source is required")
        object.__setattr__(self, "captured_at_ms", captured_at)
        object.__setattr__(self, "confidence", confidence)
        object.__setattr__(self, "source", source)


@dataclass(frozen=True, slots=True)
class FollowObservation:
    state: FollowState
    follower: RoleId
    target: RoleId
    position: tuple[float, float] | None = None
    target_position: tuple[float, float] | None = None
    route: tuple[tuple[float, float], ...] = ()
    vector: tuple[float, float] = (0.0, 0.0)
    distance: float | None = None
    reason: str = ""
    diagnostics: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.position is not None:
            object.__setattr__(self, "position", _point(self.position, "position"))
        if self.target_position is not None:
            object.__setattr__(self, "target_position", _point(self.target_position, "target_position"))
        object.__setattr__(self, "vector", _point(self.vector, "vector"))
        object.__setattr__(self, "route", tuple(_point(point, "route point") for point in self.route))
        object.__setattr__(self, "diagnostics", MappingProxyType(dict(self.diagnostics)))


__all__ = [
    "ControlMode",
    "FollowObservation",
    "FollowState",
    "MapIdentity",
    "PositionSample",
    "RoleId",
]
