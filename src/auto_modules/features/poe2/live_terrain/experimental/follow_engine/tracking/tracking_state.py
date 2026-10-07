"""Immutable role tracking state used by prediction and fusion."""

from __future__ import annotations

import math
from dataclasses import dataclass

from ..contracts import RoleFusedState


@dataclass(frozen=True, slots=True)
class RoleTrackingState:
    role_id: str
    position_native: tuple[float, float]
    velocity_native: tuple[float, float]
    uncertainty_native: float
    last_visual_at_ms: int | None
    updated_at_ms: int
    source: str

    def __post_init__(self) -> None:
        if not str(self.role_id).strip() or int(self.updated_at_ms) < 0:
            raise ValueError("tracking state metadata is invalid")
        object.__setattr__(self, "role_id", str(self.role_id).strip())
        position = (float(self.position_native[0]), float(self.position_native[1]))
        velocity = (float(self.velocity_native[0]), float(self.velocity_native[1]))
        uncertainty = float(self.uncertainty_native)
        if not all(math.isfinite(item) for item in (*position, *velocity, uncertainty)) or uncertainty < 0.0:
            raise ValueError("tracking state values must be finite")
        object.__setattr__(self, "position_native", position)
        object.__setattr__(self, "velocity_native", velocity)
        object.__setattr__(self, "uncertainty_native", uncertainty)
        object.__setattr__(self, "updated_at_ms", int(self.updated_at_ms))
        source = str(self.source).strip()
        if not source:
            raise ValueError("tracking state source is required")
        object.__setattr__(self, "source", source)
        if self.last_visual_at_ms is not None:
            object.__setattr__(self, "last_visual_at_ms", int(self.last_visual_at_ms))

    @property
    def visual_age_ms(self) -> float:
        if self.last_visual_at_ms is None:
            return float("inf")
        return max(0.0, float(self.updated_at_ms - self.last_visual_at_ms))

    def as_fused_state(self) -> RoleFusedState:
        return RoleFusedState(
            role_id=self.role_id,
            position_native=self.position_native,
            velocity_native=self.velocity_native,
            uncertainty_native=self.uncertainty_native,
            source=self.source,
            visual_age_ms=self.visual_age_ms,
        )
