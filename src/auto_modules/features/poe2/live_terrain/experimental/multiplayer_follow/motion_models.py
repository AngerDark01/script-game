"""Game-neutral contracts for the experimental closed-loop motion controller."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Mapping

import numpy as np


def _point(value: Any, name: str) -> tuple[float, float]:
    if value is None or len(value) != 2:
        raise ValueError(f"{name} must contain two values")
    point = (float(value[0]), float(value[1]))
    if not all(math.isfinite(item) for item in point):
        raise ValueError(f"{name} must contain finite values")
    return point


class MotionPhase(StrEnum):
    IDLE = "idle"
    SELECT_LOCAL_GOAL = "select_local_goal"
    ISSUE_COMMAND = "issue_command"
    WAIT_FEEDBACK = "wait_feedback"
    ACCEPT_RESPONSE = "accept_response"
    UPDATE_CALIBRATION = "update_calibration"
    REPLAN = "replan"
    RECOVERING = "recovering"
    ARRIVED = "arrived"
    STOPPED = "stopped"


@dataclass(frozen=True, slots=True)
class MotionObservation:
    role_key: str
    position: tuple[float, float]
    target: tuple[float, float]
    captured_at_ms: int
    frame_age_ms: int
    confidence: float
    map_version: str
    registration_version: int
    peer_position: tuple[float, float] | None = None
    covariance: np.ndarray | None = None
    wall_clearance: float | None = None
    command_alignment: float | None = None
    observed_velocity: tuple[float, float] = (0.0, 0.0)
    diagnostics: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        role_key = str(self.role_key).strip()
        map_version = str(self.map_version).strip()
        if not role_key or not map_version:
            raise ValueError("role_key and map_version are required")
        if int(self.captured_at_ms) < 0 or int(self.frame_age_ms) < 0:
            raise ValueError("timestamps must be non-negative")
        confidence = float(self.confidence)
        if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
            raise ValueError("confidence must be between zero and one")
        object.__setattr__(self, "role_key", role_key)
        object.__setattr__(self, "map_version", map_version)
        object.__setattr__(self, "position", _point(self.position, "position"))
        object.__setattr__(self, "target", _point(self.target, "target"))
        object.__setattr__(self, "peer_position", None if self.peer_position is None else _point(self.peer_position, "peer_position"))
        object.__setattr__(self, "observed_velocity", _point(self.observed_velocity, "observed_velocity"))
        object.__setattr__(self, "captured_at_ms", int(self.captured_at_ms))
        object.__setattr__(self, "frame_age_ms", int(self.frame_age_ms))
        object.__setattr__(self, "registration_version", int(self.registration_version))
        object.__setattr__(self, "confidence", confidence)
        clearance = None if self.wall_clearance is None else float(self.wall_clearance)
        if clearance is not None and (not math.isfinite(clearance) or clearance < 0.0):
            raise ValueError("wall_clearance must be finite and non-negative")
        object.__setattr__(self, "wall_clearance", clearance)
        alignment = None if self.command_alignment is None else float(self.command_alignment)
        if alignment is not None and (not math.isfinite(alignment) or not -1.0 <= alignment <= 1.0):
            raise ValueError("command_alignment must be between -1 and 1")
        object.__setattr__(self, "command_alignment", alignment)
        if self.covariance is not None:
            covariance = np.array(self.covariance, dtype=np.float64, copy=True, order="C")
            if covariance.shape != (2, 2) or not np.isfinite(covariance).all():
                raise ValueError("covariance must be a finite 2x2 matrix")
            covariance.setflags(write=False)
            object.__setattr__(self, "covariance", covariance)
        object.__setattr__(self, "diagnostics", MappingProxyType(dict(self.diagnostics)))


@dataclass(frozen=True, slots=True)
class MotionCommand:
    command_id: int
    role_key: str
    desired_native_vector: tuple[float, float]
    stick: tuple[float, float]
    duration_ms: int
    issued_at_ms: int
    map_version: str
    phase: MotionPhase = MotionPhase.ISSUE_COMMAND

    def __post_init__(self) -> None:
        if int(self.command_id) < 0 or int(self.duration_ms) <= 0 or int(self.issued_at_ms) < 0:
            raise ValueError("command id, duration and timestamp are invalid")
        role_key = str(self.role_key).strip()
        map_version = str(self.map_version).strip()
        if not role_key or not map_version:
            raise ValueError("command role and map version are required")
        stick = _point(self.stick, "stick")
        if any(abs(value) > 1.0 for value in stick):
            raise ValueError("stick values must be normalized to -1..1")
        object.__setattr__(self, "command_id", int(self.command_id))
        object.__setattr__(self, "duration_ms", int(self.duration_ms))
        object.__setattr__(self, "issued_at_ms", int(self.issued_at_ms))
        object.__setattr__(self, "role_key", role_key)
        object.__setattr__(self, "map_version", map_version)
        object.__setattr__(self, "desired_native_vector", _point(self.desired_native_vector, "desired_native_vector"))
        object.__setattr__(self, "stick", stick)
        object.__setattr__(self, "phase", MotionPhase(self.phase))


@dataclass(frozen=True, slots=True)
class MotionResponse:
    command_id: int
    displacement: tuple[float, float]
    elapsed_ms: int
    alignment: float
    speed: float
    progress: float
    accepted: bool
    reason: str
    diagnostics: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if int(self.command_id) < 0 or int(self.elapsed_ms) <= 0:
            raise ValueError("response id and elapsed time are invalid")
        alignment = float(self.alignment)
        speed = float(self.speed)
        progress = float(self.progress)
        if not all(math.isfinite(value) for value in (alignment, speed, progress)):
            raise ValueError("response values must be finite")
        if not -1.0 <= alignment <= 1.0 or speed < 0.0:
            raise ValueError("response alignment or speed is invalid")
        object.__setattr__(self, "command_id", int(self.command_id))
        object.__setattr__(self, "elapsed_ms", int(self.elapsed_ms))
        object.__setattr__(self, "displacement", _point(self.displacement, "displacement"))
        object.__setattr__(self, "alignment", alignment)
        object.__setattr__(self, "speed", speed)
        object.__setattr__(self, "progress", progress)
        object.__setattr__(self, "accepted", bool(self.accepted))
        object.__setattr__(self, "reason", str(self.reason))
        object.__setattr__(self, "diagnostics", MappingProxyType(dict(self.diagnostics)))


@dataclass(frozen=True, slots=True)
class MotionCalibrationState:
    role_key: str
    stick_to_native: np.ndarray = field(default_factory=lambda: np.eye(2, dtype=np.float64))
    bias: tuple[float, float] = (0.0, 0.0)
    speed_gain: float = 1.0
    duration_gain: float = 1.0
    input_latency_ms: float = 0.0
    confidence: float = 0.0
    sample_count: int = 0
    last_speed: float = 0.0
    last_alignment: float = 0.0

    def __post_init__(self) -> None:
        role_key = str(self.role_key).strip()
        if not role_key:
            raise ValueError("role_key is required")
        matrix = np.array(self.stick_to_native, dtype=np.float64, copy=True, order="C")
        if matrix.shape != (2, 2) or not np.isfinite(matrix).all():
            raise ValueError("stick_to_native must be a finite 2x2 matrix")
        if not math.isfinite(float(self.speed_gain)) or float(self.speed_gain) <= 0.0:
            raise ValueError("speed_gain must be positive")
        if not math.isfinite(float(self.duration_gain)) or float(self.duration_gain) <= 0.0:
            raise ValueError("duration_gain must be positive")
        if not 0.0 <= float(self.confidence) <= 1.0 or int(self.sample_count) < 0:
            raise ValueError("calibration confidence/sample count is invalid")
        matrix.setflags(write=False)
        object.__setattr__(self, "role_key", role_key)
        object.__setattr__(self, "stick_to_native", matrix)
        object.__setattr__(self, "bias", _point(self.bias, "bias"))
        object.__setattr__(self, "speed_gain", float(self.speed_gain))
        object.__setattr__(self, "duration_gain", float(self.duration_gain))
        object.__setattr__(self, "input_latency_ms", max(0.0, float(self.input_latency_ms)))
        object.__setattr__(self, "confidence", float(self.confidence))
        object.__setattr__(self, "sample_count", int(self.sample_count))
        object.__setattr__(self, "last_speed", max(0.0, float(self.last_speed)))
        object.__setattr__(self, "last_alignment", float(self.last_alignment))


__all__ = [
    "MotionCalibrationState",
    "MotionCommand",
    "MotionObservation",
    "MotionPhase",
    "MotionResponse",
]
