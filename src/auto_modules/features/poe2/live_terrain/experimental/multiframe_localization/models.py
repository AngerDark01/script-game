"""Immutable contracts shared by the multi-frame localization strategies."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Mapping

import numpy as np

from auto_modules.core.localization.frame_displacement import FrameDisplacement
from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.models import (
    HybridFrame,
    SimilarityTransform2D,
)


def _point(value, name: str) -> tuple[float, float]:
    if len(value) != 2 or not all(math.isfinite(float(v)) for v in value):
        raise ValueError(f"{name} must contain two finite values")
    return float(value[0]), float(value[1])


def _covariance(value, name: str = "covariance") -> np.ndarray | None:
    if value is None:
        return None
    matrix = np.array(value, dtype=np.float64, copy=True, order="C")
    if matrix.shape != (2, 2) or not np.isfinite(matrix).all():
        raise ValueError(f"{name} must be a finite 2x2 matrix")
    if not np.allclose(matrix, matrix.T, atol=1e-9):
        raise ValueError(f"{name} must be symmetric")
    matrix.setflags(write=False)
    return matrix


class MotionState(StrEnum):
    STATIONARY = "stationary"
    MOVING = "moving"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class MultiFrameEvidence:
    frame: HybridFrame
    motion: FrameDisplacement
    local_offset: tuple[float, float]
    is_keyframe: bool
    segment_id: int
    observed_mask: np.ndarray | None = None
    raw_frame: np.ndarray | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.frame, HybridFrame):
            raise TypeError("frame must be HybridFrame")
        if not isinstance(self.motion, FrameDisplacement):
            raise TypeError("motion must be FrameDisplacement")
        if int(self.segment_id) < 0:
            raise ValueError("segment_id must be non-negative")
        object.__setattr__(self, "local_offset", _point(self.local_offset, "local_offset"))
        object.__setattr__(self, "segment_id", int(self.segment_id))
        object.__setattr__(self, "is_keyframe", bool(self.is_keyframe))
        observed = self.observed_mask
        if observed is None:
            observed = np.full(self.frame.wall_mask.shape, 255, dtype=np.uint8)
        else:
            observed = np.where(np.asarray(observed) > 0, 255, 0).astype(np.uint8)
            if observed.shape != self.frame.wall_mask.shape:
                raise ValueError("observed_mask must match wall_mask shape")
        observed = np.array(observed, copy=True, order="C")
        observed.setflags(write=False)
        object.__setattr__(self, "observed_mask", observed)
        if self.raw_frame is not None:
            raw = np.array(self.raw_frame, copy=True, order="C")
            if raw.ndim not in (2, 3) or raw.size == 0:
                raise ValueError("raw_frame must be a non-empty 2-D or 3-D array")
            raw.setflags(write=False)
            object.__setattr__(self, "raw_frame", raw)


@dataclass(frozen=True)
class CandidateRegion:
    transform: SimilarityTransform2D
    position: tuple[float, float]
    covariance: np.ndarray | None
    score: float
    support_frames: tuple[int, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.transform, SimilarityTransform2D):
            raise TypeError("transform must be SimilarityTransform2D")
        score = float(self.score)
        if not math.isfinite(score):
            raise ValueError("score must be finite")
        if any(int(frame_id) < 0 for frame_id in self.support_frames):
            raise ValueError("support frame ids must be non-negative")
        object.__setattr__(self, "position", _point(self.position, "position"))
        object.__setattr__(self, "covariance", _covariance(self.covariance))
        object.__setattr__(self, "score", score)
        object.__setattr__(self, "support_frames", tuple(int(v) for v in self.support_frames))


@dataclass(frozen=True)
class PositionEstimate:
    status: str
    position: tuple[float, float] | None
    velocity: tuple[float, float] | None
    covariance: np.ndarray | None
    candidate_regions: tuple[CandidateRegion, ...]
    instance_id: str
    registration_version: int
    evidence_version: int
    fresh: bool
    age_ms: int
    source: str
    reason: str
    diagnostics: Mapping[str, object] = MappingProxyType({})

    def __post_init__(self) -> None:
        if not self.instance_id:
            raise ValueError("instance_id is required")
        if int(self.registration_version) < 0 or int(self.evidence_version) < 0:
            raise ValueError("versions must be non-negative")
        if int(self.age_ms) < 0:
            raise ValueError("age_ms must be non-negative")
        object.__setattr__(self, "position", None if self.position is None else _point(self.position, "position"))
        object.__setattr__(self, "velocity", None if self.velocity is None else _point(self.velocity, "velocity"))
        object.__setattr__(self, "covariance", _covariance(self.covariance))
        object.__setattr__(self, "candidate_regions", tuple(self.candidate_regions))
        object.__setattr__(self, "registration_version", int(self.registration_version))
        object.__setattr__(self, "evidence_version", int(self.evidence_version))
        object.__setattr__(self, "age_ms", int(self.age_ms))
        object.__setattr__(self, "fresh", bool(self.fresh))
        object.__setattr__(self, "diagnostics", MappingProxyType(dict(self.diagnostics)))


__all__ = ["CandidateRegion", "MotionState", "MultiFrameEvidence", "PositionEstimate"]
