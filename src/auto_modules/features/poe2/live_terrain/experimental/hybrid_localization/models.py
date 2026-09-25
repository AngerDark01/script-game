"""Immutable contracts for the PoE2 hybrid-localization experiment."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Mapping

import numpy as np

from auto_modules.core.localization import LocalizationResult


def _finite_point(value, name: str) -> tuple[float, float]:
    if len(value) != 2 or not all(math.isfinite(float(item)) for item in value):
        raise ValueError(f"{name} must contain two finite values")
    return float(value[0]), float(value[1])


def _readonly_mask(value, name: str) -> np.ndarray:
    mask = np.array(value, copy=True, order="C")
    if mask.ndim != 2 or mask.size == 0:
        raise ValueError(f"{name} must be a non-empty 2-D array")
    if mask.dtype != np.uint8:
        mask = np.clip(mask, 0, 255).astype(np.uint8)
    mask.setflags(write=False)
    return mask


class HybridLocalizationMode(StrEnum):
    NEED_ABSOLUTE = "need_absolute"
    LOCAL_TRACKING = "local_tracking"
    RECOVERY_PENDING = "recovery_pending"
    RECOVERY_REQUIRED = "recovery_required"
    STOPPED = "stopped"


@dataclass(frozen=True)
class PositionAnchor:
    position: tuple[float, float]
    area_instance: str
    captured_at_ms: int
    source: str
    confidence: float = 1.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "position", _finite_point(self.position, "anchor position"))
        if not self.area_instance:
            raise ValueError("area_instance is required")
        if int(self.captured_at_ms) < 0:
            raise ValueError("captured_at_ms must be non-negative")
        if not math.isfinite(float(self.confidence)) or not 0.0 <= float(self.confidence) <= 1.0:
            raise ValueError("confidence must be finite and between 0 and 1")
        object.__setattr__(self, "captured_at_ms", int(self.captured_at_ms))
        object.__setattr__(self, "source", str(self.source))
        object.__setattr__(self, "confidence", float(self.confidence))


@dataclass(frozen=True)
class SimilarityTransform2D:
    angle_degrees: float
    reflect_horizontal: bool
    scale: float
    translation: tuple[float, float]

    def __post_init__(self) -> None:
        angle = float(self.angle_degrees)
        scale = float(self.scale)
        translation = _finite_point(self.translation, "translation")
        if not math.isfinite(angle) or not math.isfinite(scale) or scale <= 0:
            raise ValueError("transform values must be finite and scale must be positive")
        object.__setattr__(self, "angle_degrees", angle % 360.0)
        object.__setattr__(self, "reflect_horizontal", bool(self.reflect_horizontal))
        object.__setattr__(self, "scale", scale)
        object.__setattr__(self, "translation", translation)


@dataclass(frozen=True)
class HybridFrame:
    """One immutable visual frame in local minimap coordinates."""

    frame_id: int
    captured_at_ms: int
    wall_mask: np.ndarray
    local_player: tuple[float, float]
    diagnostics: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_evidence(
        cls,
        evidence: Any,
        *,
        captured_at_ms: int,
        frame_id: int | None = None,
    ) -> "HybridFrame":
        wall_mask = getattr(evidence, "wall_mask", None)
        if wall_mask is None:
            wall_mask = getattr(evidence, "feature", None)
        if wall_mask is None:
            raise ValueError("evidence must provide wall_mask or feature")
        mask = np.asarray(wall_mask)
        config = dict(getattr(evidence, "monitor_config", {}) or {})
        binding = config.get("binding")
        binding = dict(binding) if isinstance(binding, Mapping) else {}
        marker = binding.get("player_marker_position")
        if not isinstance(marker, (list, tuple)) or len(marker) != 2:
            marker = (mask.shape[1] / 2.0, mask.shape[0] / 2.0)
        diagnostics = {
            "evidence_captured_at": str(getattr(evidence, "captured_at", "")),
        }
        if config.get("capture_size") is not None:
            diagnostics["capture_size"] = int(config["capture_size"])
        return cls(
            frame_id=int(captured_at_ms if frame_id is None else frame_id),
            captured_at_ms=int(captured_at_ms),
            wall_mask=mask,
            local_player=(float(marker[0]), float(marker[1])),
            diagnostics=diagnostics,
        )

    def __post_init__(self) -> None:
        if int(self.frame_id) < 0:
            raise ValueError("frame_id must be non-negative")
        if int(self.captured_at_ms) < 0:
            raise ValueError("captured_at_ms must be non-negative")
        object.__setattr__(self, "frame_id", int(self.frame_id))
        object.__setattr__(self, "captured_at_ms", int(self.captured_at_ms))
        object.__setattr__(self, "wall_mask", _readonly_mask(self.wall_mask, "wall_mask"))
        object.__setattr__(self, "local_player", _finite_point(self.local_player, "local_player"))
        object.__setattr__(self, "diagnostics", MappingProxyType(dict(self.diagnostics)))


@dataclass(frozen=True)
class AbsoluteRegistration:
    result: LocalizationResult
    transform: SimilarityTransform2D
    anchor_error: float
    area_instance: str
    diagnostics: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.result, LocalizationResult) or not self.result.is_localized:
            raise ValueError("result must be a localized LocalizationResult")
        anchor_error = float(self.anchor_error)
        if not math.isfinite(anchor_error) or anchor_error < 0:
            raise ValueError("anchor_error must be finite and non-negative")
        if not self.area_instance:
            raise ValueError("area_instance is required")
        object.__setattr__(self, "anchor_error", anchor_error)
        object.__setattr__(self, "diagnostics", MappingProxyType(dict(self.diagnostics)))


@dataclass(frozen=True)
class HybridLocalizationState:
    mode: HybridLocalizationMode
    position: tuple[float, float] | None
    latest_confirmed_position: tuple[float, float] | None
    trajectory: tuple[tuple[float, float], ...]
    registration: AbsoluteRegistration | None
    source: str
    confidence: float
    reason: str
    recovery_revision: int
    diagnostics: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.position is not None:
            object.__setattr__(self, "position", _finite_point(self.position, "position"))
        if self.latest_confirmed_position is not None:
            object.__setattr__(
                self,
                "latest_confirmed_position",
                _finite_point(self.latest_confirmed_position, "latest_confirmed_position"),
            )
        object.__setattr__(
            self,
            "trajectory",
            tuple(_finite_point(point, "trajectory point") for point in self.trajectory),
        )
        confidence = float(self.confidence)
        if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
            raise ValueError("confidence must be finite and between 0 and 1")
        if int(self.recovery_revision) < 0:
            raise ValueError("recovery_revision must be non-negative")
        object.__setattr__(self, "confidence", confidence)
        object.__setattr__(self, "recovery_revision", int(self.recovery_revision))
        object.__setattr__(self, "diagnostics", MappingProxyType(dict(self.diagnostics)))


__all__ = [
    "AbsoluteRegistration",
    "HybridFrame",
    "HybridLocalizationMode",
    "HybridLocalizationState",
    "PositionAnchor",
    "SimilarityTransform2D",
]
