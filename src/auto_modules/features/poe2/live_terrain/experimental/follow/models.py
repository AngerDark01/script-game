"""Qt-free models for visual/predicted follow observations."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Mapping


@dataclass(frozen=True, slots=True)
class VisualRoleObservation:
    role_key: str
    position: tuple[float, float]
    captured_at_ms: int
    visible: bool
    source: str
    uncertainty_native: float = 0.0


@dataclass(frozen=True, slots=True)
class FollowSessionState:
    session_id: str | None = None
    observations: Mapping[str, VisualRoleObservation] = field(default_factory=dict)
    target: tuple[float, float] | None = None
    output_armed: bool = False

    def with_observation(self, observation: VisualRoleObservation) -> "FollowSessionState":
        updated = dict(self.observations)
        updated[observation.role_key] = observation
        return replace(self, observations=updated)
