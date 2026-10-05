"""Immutable contracts for the experimental two-player first-frame path."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping


def _point(value: Any, name: str) -> tuple[float, float]:
    if len(value) != 2:
        raise ValueError(f"{name} must contain two values")
    result = (float(value[0]), float(value[1]))
    if not all(math.isfinite(item) for item in result):
        raise ValueError(f"{name} must contain finite values")
    return result


@dataclass(frozen=True)
class MarkerColorProfile:
    """User-calibrated HSV profile for one minimap player marker."""

    name: str
    hue_min: int = 0
    hue_max: int = 179
    saturation_min: int = 150
    value_min: int = 150
    min_area: float = 8.0
    max_area: float = 55.0
    max_dimension: int = 14
    enabled: bool = True

    def __post_init__(self) -> None:
        name = str(self.name).strip()
        if not name:
            raise ValueError("marker color profile name is required")
        hue_min, hue_max = int(self.hue_min), int(self.hue_max)
        if not 0 <= hue_min <= 179 or not 0 <= hue_max <= 179:
            raise ValueError("marker hue bounds must be between 0 and 179")
        saturation, value = int(self.saturation_min), int(self.value_min)
        if not 0 <= saturation <= 255 or not 0 <= value <= 255:
            raise ValueError("marker saturation/value thresholds must be between 0 and 255")
        min_area, max_area = float(self.min_area), float(self.max_area)
        if min_area < 0 or max_area < min_area or not math.isfinite(min_area + max_area):
            raise ValueError("marker area bounds are invalid")
        if int(self.max_dimension) < 1:
            raise ValueError("marker max_dimension must be positive")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "hue_min", hue_min)
        object.__setattr__(self, "hue_max", hue_max)
        object.__setattr__(self, "saturation_min", saturation)
        object.__setattr__(self, "value_min", value)
        object.__setattr__(self, "min_area", min_area)
        object.__setattr__(self, "max_area", max_area)
        object.__setattr__(self, "max_dimension", int(self.max_dimension))
        object.__setattr__(self, "enabled", bool(self.enabled))

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "hue_min": self.hue_min,
            "hue_max": self.hue_max,
            "saturation_min": self.saturation_min,
            "value_min": self.value_min,
            "min_area": self.min_area,
            "max_area": self.max_area,
            "max_dimension": self.max_dimension,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "MarkerColorProfile":
        if not isinstance(payload, Mapping):
            raise TypeError("marker color profile must be a mapping")
        return cls(**dict(payload))


@dataclass(frozen=True)
class PlayerMarkerCandidate:
    """One possible character marker detected in the captured minimap."""

    candidate_id: str
    local_position: tuple[float, float]
    confidence: float = 1.0
    area: float = 0.0
    bbox: tuple[int, int, int, int] | None = None
    color_features: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.candidate_id):
            raise ValueError("candidate_id is required")
        object.__setattr__(self, "candidate_id", str(self.candidate_id))
        object.__setattr__(
            self,
            "local_position",
            _point(self.local_position, "local_position"),
        )
        confidence = float(self.confidence)
        area = float(self.area)
        if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
            raise ValueError("confidence must be finite and between 0 and 1")
        if not math.isfinite(area) or area < 0.0:
            raise ValueError("area must be finite and non-negative")
        object.__setattr__(self, "confidence", confidence)
        object.__setattr__(self, "area", area)
        if self.bbox is not None:
            if len(self.bbox) != 4:
                raise ValueError("bbox must contain x, y, width and height")
            bbox = tuple(int(value) for value in self.bbox)
            if bbox[2] < 0 or bbox[3] < 0:
                raise ValueError("bbox dimensions must be non-negative")
            object.__setattr__(self, "bbox", bbox)
        object.__setattr__(
            self,
            "color_features",
            MappingProxyType(dict(self.color_features)),
        )


@dataclass(frozen=True)
class PlayerLocalization:
    """One identity's paired screen/native/map result."""

    identity: str
    candidate_id: str
    screen_position: tuple[float, float]
    memory_position: tuple[float, float]
    mapped_position: tuple[float, float]
    anchor_error: float
    confidence: float
    accepted: bool

    def __post_init__(self) -> None:
        for name in ("identity", "candidate_id"):
            if not str(getattr(self, name)):
                raise ValueError(f"{name} is required")
            object.__setattr__(self, name, str(getattr(self, name)))
        for name in ("screen_position", "memory_position", "mapped_position"):
            object.__setattr__(self, name, _point(getattr(self, name), name))
        anchor_error = float(self.anchor_error)
        confidence = float(self.confidence)
        if not math.isfinite(anchor_error) or anchor_error < 0.0:
            raise ValueError("anchor_error must be finite and non-negative")
        if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
            raise ValueError("confidence must be finite and between 0 and 1")
        object.__setattr__(self, "anchor_error", anchor_error)
        object.__setattr__(self, "confidence", confidence)
        object.__setattr__(self, "accepted", bool(self.accepted))


@dataclass(frozen=True)
class DualFirstFrameResult:
    """Outcome of a two-marker, one-transform first-frame registration."""

    status: str
    reason: str
    primary_registration: Any | None
    players: Mapping[str, PlayerLocalization] = field(default_factory=dict)
    diagnostics: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        status = str(self.status)
        if status not in {"accepted", "rejected", "insufficient", "ambiguous"}:
            raise ValueError(f"unsupported dual first-frame status: {status}")
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "reason", str(self.reason))
        object.__setattr__(self, "players", MappingProxyType(dict(self.players)))
        object.__setattr__(self, "diagnostics", MappingProxyType(dict(self.diagnostics)))

    @property
    def accepted(self) -> bool:
        return self.status == "accepted"

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "reason": self.reason,
            "players": {
                identity: {
                    "identity": player.identity,
                    "candidate_id": player.candidate_id,
                    "screen_position": list(player.screen_position),
                    "memory_position": list(player.memory_position),
                    "mapped_position": list(player.mapped_position),
                    "anchor_error": player.anchor_error,
                    "confidence": player.confidence,
                    "accepted": player.accepted,
                }
                for identity, player in self.players.items()
            },
            "diagnostics": dict(self.diagnostics),
        }


__all__ = [
    "DualFirstFrameResult",
    "MarkerColorProfile",
    "PlayerLocalization",
    "PlayerMarkerCandidate",
]
