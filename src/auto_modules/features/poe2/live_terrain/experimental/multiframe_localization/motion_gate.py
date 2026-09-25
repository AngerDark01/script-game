"""Motion and key-frame admission policy for multi-frame capture."""

from __future__ import annotations

from dataclasses import dataclass

from auto_modules.core.localization import canonical_wall_mask, estimate_bounded_displacement
from auto_modules.core.localization.frame_displacement import FrameDisplacement
from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.models import HybridFrame

from .models import MotionState


@dataclass(frozen=True)
class MotionDecision:
    state: MotionState
    displacement: FrameDisplacement
    should_capture_keyframe: bool
    reason: str


class MotionGate:
    def __init__(
        self,
        *,
        min_quality: float = 0.20,
        max_shift: float = 40.0,
        movement_dead_zone: float = 1.0,
        keyframe_distance: float = 2.0,
        max_frame_gap_ms: int = 500,
    ) -> None:
        if min_quality < 0 or max_shift <= 0 or movement_dead_zone < 0 or keyframe_distance <= 0:
            raise ValueError("invalid motion gate thresholds")
        if max_frame_gap_ms <= 0:
            raise ValueError("max_frame_gap_ms must be positive")
        self.min_quality = float(min_quality)
        self.max_shift = float(max_shift)
        self.movement_dead_zone = float(movement_dead_zone)
        self.keyframe_distance = float(keyframe_distance)
        self.max_frame_gap_ms = int(max_frame_gap_ms)

    def decide(
        self,
        previous: HybridFrame,
        current: HybridFrame,
        *,
        elapsed_ms: int,
    ) -> MotionDecision:
        if not isinstance(previous, HybridFrame) or not isinstance(current, HybridFrame):
            raise TypeError("motion gate requires HybridFrame values")
        displacement = estimate_bounded_displacement(
            canonical_wall_mask(previous.wall_mask),
            canonical_wall_mask(current.wall_mask),
            min_quality=self.min_quality,
            max_shift=self.max_shift,
        )
        if int(elapsed_ms) < 0 or int(elapsed_ms) > self.max_frame_gap_ms:
            return MotionDecision(MotionState.UNKNOWN, displacement, False, "frame_gap_invalid")
        if not displacement.accepted:
            return MotionDecision(MotionState.UNKNOWN, displacement, False, displacement.reason)
        if displacement.distance < self.movement_dead_zone:
            return MotionDecision(MotionState.STATIONARY, displacement, False, "stationary")
        return MotionDecision(
            MotionState.MOVING,
            displacement,
            displacement.distance >= self.keyframe_distance,
            "moving",
        )


__all__ = ["MotionDecision", "MotionGate"]
