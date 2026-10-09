"""Stable motion contract shared by click and dynamic follow compositions."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LegacyFollowMotionContract:
    arrival_radius: float = 12.0
    resume_radius: float = 20.0
    speed_units_per_second: float = 80.0
    downsample_factor: int = 8
    local_lookahead: float = 24.0
    prediction_horizon: float = 0.25


DYNAMIC_FOLLOW_CONTRACT = LegacyFollowMotionContract()

__all__ = ["LegacyFollowMotionContract", "DYNAMIC_FOLLOW_CONTRACT"]
