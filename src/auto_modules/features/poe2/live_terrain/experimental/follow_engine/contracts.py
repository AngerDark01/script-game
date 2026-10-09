"""Immutable, process-safe contracts for the follow-engine boundary."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping


class _FrozenMapping(dict):
    """Pickle-safe read-only mapping for multiprocessing messages."""

    def __readonly(self, *args, **kwargs):
        raise TypeError("mapping is read-only")

    __setitem__ = __readonly
    __delitem__ = __readonly
    clear = __readonly
    pop = __readonly
    popitem = __readonly
    setdefault = __readonly
    update = __readonly
    __ior__ = __readonly

    def __reduce__(self):
        return (_restore_frozen_mapping, (dict(self),))


def _restore_frozen_mapping(values: Mapping[str, Any]) -> _FrozenMapping:
    restored = dict.__new__(_FrozenMapping)
    dict.update(restored, values)
    return restored


def _number(value: Any, field_name: str, *, minimum: float | None = None) -> float:
    result = float(value)
    if not math.isfinite(result) or minimum is not None and result < minimum:
        raise ValueError(f"{field_name} must be finite and >= {minimum}")
    return result


def _point(value: Any, field_name: str) -> tuple[float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError(f"{field_name} must contain two values")
    point = (float(value[0]), float(value[1]))
    if not all(math.isfinite(item) for item in point):
        raise ValueError(f"{field_name} must contain finite values")
    return point


def _role_map(value: Mapping[str, Any], field_name: str) -> _FrozenMapping:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be a mapping")
    normalized: dict[str, Any] = {}
    for role, item in value.items():
        key = str(role).strip()
        if not key:
            raise ValueError(f"{field_name} contains an empty role")
        normalized[key] = item
    return _restore_frozen_mapping(normalized)


class FrameSlotStatus(StrEnum):
    EMPTY = "empty"
    WRITING = "writing"
    READY = "ready"
    READING = "reading"


class ObservationSource(StrEnum):
    VISUAL = "visual"
    LOCAL_ROI = "local_roi"
    PARTIAL = "partial"
    NONE = "none"


@dataclass(frozen=True, slots=True)
class StageTiming:
    capture_ms: float = 0.0
    wall_ms: float = 0.0
    marker_ms: float = 0.0
    association_ms: float = 0.0
    local_ms: float = 0.0
    prediction_ms: float = 0.0
    recovery_ms: float = 0.0
    memory_ms: float = 0.0
    global_ms: float = 0.0
    fusion_ms: float = 0.0
    route_ms: float = 0.0
    output_ms: float = 0.0
    heartbeat_ms: float = 0.0
    ui_drain_ms: float = 0.0
    total_ms: float = 0.0

    def __post_init__(self) -> None:
        for name in self.__dataclass_fields__:
            object.__setattr__(self, name, _number(getattr(self, name), name, minimum=0.0))

    def as_dict(self) -> dict[str, float]:
        return {name: float(getattr(self, name)) for name in self.__dataclass_fields__}


@dataclass(frozen=True, slots=True)
class FrameSlot:
    generation: int
    sequence: int
    captured_at_ms: int
    map_instance: str
    width: int
    height: int
    raw_offset: int
    raw_size: int
    status: FrameSlotStatus = FrameSlotStatus.EMPTY

    def __post_init__(self) -> None:
        generation = int(self.generation)
        sequence = int(self.sequence)
        captured = int(self.captured_at_ms)
        width = int(self.width)
        height = int(self.height)
        offset = int(self.raw_offset)
        size = int(self.raw_size)
        instance = str(self.map_instance).strip()
        if generation < 0 or sequence < 0 or captured < 0:
            raise ValueError("frame generation, sequence and timestamp must be non-negative")
        if width <= 0 or height <= 0 or offset < 0 or size < 0 or not instance:
            raise ValueError("frame dimensions, payload and map instance are invalid")
        object.__setattr__(self, "generation", generation)
        object.__setattr__(self, "sequence", sequence)
        object.__setattr__(self, "captured_at_ms", captured)
        object.__setattr__(self, "map_instance", instance)
        object.__setattr__(self, "width", width)
        object.__setattr__(self, "height", height)
        object.__setattr__(self, "raw_offset", offset)
        object.__setattr__(self, "raw_size", size)
        object.__setattr__(self, "status", FrameSlotStatus(self.status))


@dataclass(frozen=True, slots=True)
class RoleVisualObservation:
    role_id: str
    position_native: tuple[float, float] | None
    velocity_native: tuple[float, float] = (0.0, 0.0)
    confidence: float = 0.0
    uncertainty_native: float = 0.0
    visible: bool = False
    last_visual_at_ms: int | None = None
    association_cost: float = 0.0

    def __post_init__(self) -> None:
        role = str(self.role_id).strip()
        if not role:
            raise ValueError("role_id is required")
        if self.position_native is not None:
            object.__setattr__(self, "position_native", _point(self.position_native, "position_native"))
        object.__setattr__(self, "velocity_native", _point(self.velocity_native, "velocity_native"))
        object.__setattr__(self, "confidence", _number(self.confidence, "confidence", minimum=0.0))
        if self.confidence > 1.0:
            raise ValueError("confidence must be <= 1")
        object.__setattr__(self, "uncertainty_native", _number(self.uncertainty_native, "uncertainty_native", minimum=0.0))
        if self.last_visual_at_ms is not None:
            timestamp = int(self.last_visual_at_ms)
            if timestamp < 0:
                raise ValueError("last_visual_at_ms must be non-negative")
            object.__setattr__(self, "last_visual_at_ms", timestamp)
        object.__setattr__(self, "association_cost", _number(self.association_cost, "association_cost", minimum=0.0))
        object.__setattr__(self, "role_id", role)
        object.__setattr__(self, "visible", bool(self.visible))


@dataclass(frozen=True, slots=True)
class VisualObservation:
    generation: int
    sequence: int
    captured_at_ms: int
    map_instance: str
    roles: Mapping[str, RoleVisualObservation]
    wall_shift: tuple[float, float] | None = None
    wall_quality: float = 0.0
    assignment_score: float = 0.0
    association_diagnostics: Mapping[str, Any] = field(default_factory=dict)
    local_match_score: float | None = None
    local_match_radius: float | None = None
    source: ObservationSource = ObservationSource.NONE
    timing: StageTiming = field(default_factory=StageTiming)
    # Optional registration state carried across a worker handover.  The
    # concrete vision adapter stores its immutable SimilarityTransform2D here;
    # keeping the contract opaque avoids coupling the generic runtime to the
    # PoE2 transform implementation while preserving a pickle-safe DTO.
    transform: Any | None = None

    def __post_init__(self) -> None:
        _validate_header(self.generation, self.sequence, self.captured_at_ms, self.map_instance)
        roles = _role_map(self.roles, "roles")
        for key, value in roles.items():
            if not isinstance(value, RoleVisualObservation) or value.role_id != key:
                raise ValueError("roles must map keys to matching RoleVisualObservation values")
        object.__setattr__(self, "roles", roles)
        if self.wall_shift is not None:
            object.__setattr__(self, "wall_shift", _point(self.wall_shift, "wall_shift"))
        object.__setattr__(self, "wall_quality", _bounded_score(self.wall_quality, "wall_quality"))
        object.__setattr__(self, "assignment_score", _bounded_score(self.assignment_score, "assignment_score"))
        object.__setattr__(self, "association_diagnostics", _restore_frozen_mapping(self.association_diagnostics))
        if self.local_match_score is not None:
            object.__setattr__(self, "local_match_score", _bounded_score(self.local_match_score, "local_match_score"))
        if self.local_match_radius is not None:
            object.__setattr__(self, "local_match_radius", _number(self.local_match_radius, "local_match_radius", minimum=0.0))
        object.__setattr__(self, "source", ObservationSource(self.source))
        if not isinstance(self.timing, StageTiming):
            raise ValueError("timing must be StageTiming")


@dataclass(frozen=True, slots=True)
class RolePrediction:
    role_id: str
    position_native: tuple[float, float]
    velocity_native: tuple[float, float]
    uncertainty_native: float
    source: str
    visual_age_ms: float
    prediction_age_ms: float

    def __post_init__(self) -> None:
        role = str(self.role_id).strip()
        if not role:
            raise ValueError("role_id is required")
        object.__setattr__(self, "role_id", role)
        object.__setattr__(self, "position_native", _point(self.position_native, "position_native"))
        object.__setattr__(self, "velocity_native", _point(self.velocity_native, "velocity_native"))
        object.__setattr__(self, "uncertainty_native", _number(self.uncertainty_native, "uncertainty_native", minimum=0.0))
        object.__setattr__(self, "visual_age_ms", _number(self.visual_age_ms, "visual_age_ms", minimum=0.0))
        object.__setattr__(self, "prediction_age_ms", _number(self.prediction_age_ms, "prediction_age_ms", minimum=0.0))
        source = str(self.source).strip()
        if not source:
            raise ValueError("prediction source is required")
        object.__setattr__(self, "source", source)


@dataclass(frozen=True, slots=True)
class PredictionSnapshot:
    generation: int
    tick_sequence: int
    created_at_ms: int
    roles: Mapping[str, RolePrediction]
    calibration_confidence: float = 0.0

    def __post_init__(self) -> None:
        _validate_header(self.generation, self.tick_sequence, self.created_at_ms, "prediction")
        roles = _role_map(self.roles, "roles")
        for key, value in roles.items():
            if not isinstance(value, RolePrediction) or value.role_id != key:
                raise ValueError("roles must map keys to matching RolePrediction values")
        object.__setattr__(self, "roles", roles)
        object.__setattr__(self, "calibration_confidence", _bounded_score(self.calibration_confidence, "calibration_confidence"))


@dataclass(frozen=True, slots=True)
class OutputIntent:
    role_id: str
    controller: int
    vector: tuple[float, float]
    duration_ms: int
    neutral: bool = False
    control_tick: int = 0
    target_revision: int = 0
    visual_sequence: int = -1

    def __post_init__(self) -> None:
        role = str(self.role_id).strip()
        controller = int(self.controller)
        duration = int(self.duration_ms)
        if not role or controller < 1 or duration < 0:
            raise ValueError("output intent metadata is invalid")
        vector = _point(self.vector, "vector")
        if any(abs(item) > 1.0 for item in vector):
            raise ValueError("output vector must be normalized to [-1, 1]")
        object.__setattr__(self, "role_id", role)
        object.__setattr__(self, "controller", controller)
        object.__setattr__(self, "vector", vector)
        object.__setattr__(self, "duration_ms", duration)
        object.__setattr__(self, "neutral", bool(self.neutral))


@dataclass(frozen=True, slots=True)
class RoleFusedState:
    role_id: str
    position_native: tuple[float, float]
    velocity_native: tuple[float, float]
    uncertainty_native: float
    source: str
    visual_age_ms: float

    def __post_init__(self) -> None:
        role = str(self.role_id).strip()
        if not role:
            raise ValueError("role_id is required")
        object.__setattr__(self, "role_id", role)
        object.__setattr__(self, "position_native", _point(self.position_native, "position_native"))
        object.__setattr__(self, "velocity_native", _point(self.velocity_native, "velocity_native"))
        object.__setattr__(self, "uncertainty_native", _number(self.uncertainty_native, "uncertainty_native", minimum=0.0))
        object.__setattr__(self, "visual_age_ms", _number(self.visual_age_ms, "visual_age_ms", minimum=0.0))
        source = str(self.source).strip()
        if not source:
            raise ValueError("fusion source is required")
        object.__setattr__(self, "source", source)


@dataclass(frozen=True, slots=True)
class FusionSnapshot:
    generation: int
    created_at_ms: int
    roles: Mapping[str, RoleFusedState]
    recovery_state: str
    recovery_reason: str
    route: tuple[tuple[float, float], ...] = ()
    control_vectors: Mapping[str, tuple[float, float]] = field(default_factory=dict)
    output_intents: tuple[OutputIntent, ...] = ()
    session_active: bool = True
    timing: StageTiming = field(default_factory=StageTiming)

    def __post_init__(self) -> None:
        _validate_header(self.generation, 0, self.created_at_ms, "fusion")
        roles = _role_map(self.roles, "roles")
        for key, value in roles.items():
            if not isinstance(value, RoleFusedState) or value.role_id != key:
                raise ValueError("roles must map keys to matching RoleFusedState values")
        object.__setattr__(self, "roles", roles)
        state = str(self.recovery_state).strip()
        reason = str(self.recovery_reason).strip()
        if not state:
            raise ValueError("recovery_state is required")
        object.__setattr__(self, "recovery_state", state)
        object.__setattr__(self, "recovery_reason", reason)
        object.__setattr__(self, "route", tuple(_point(point, "route point") for point in self.route))
        vectors = _role_map(self.control_vectors, "control_vectors")
        object.__setattr__(self, "control_vectors", _restore_frozen_mapping({key: _point(value, "control vector") for key, value in vectors.items()}))
        object.__setattr__(self, "output_intents", tuple(self.output_intents))
        if any(not isinstance(item, OutputIntent) for item in self.output_intents):
            raise ValueError("output_intents must contain OutputIntent values")
        if not isinstance(self.timing, StageTiming):
            raise ValueError("timing must be StageTiming")
        object.__setattr__(self, "session_active", bool(self.session_active))


def _validate_header(generation: int, sequence: int, captured_at_ms: int, map_instance: str) -> None:
    if int(generation) < 0 or int(sequence) < 0 or int(captured_at_ms) < 0:
        raise ValueError("message generation, sequence and timestamp must be non-negative")
    if not str(map_instance).strip():
        raise ValueError("map_instance is required")


def _bounded_score(value: Any, field_name: str) -> float:
    score = _number(value, field_name, minimum=0.0)
    if score > 1.0:
        raise ValueError(f"{field_name} must be <= 1")
    return score


__all__ = [
    "FrameSlot",
    "FrameSlotStatus",
    "FusionSnapshot",
    "ObservationSource",
    "OutputIntent",
    "PredictionSnapshot",
    "RoleFusedState",
    "RolePrediction",
    "RoleVisualObservation",
    "StageTiming",
    "VisualObservation",
]
