"""Domain-neutral gated observation exposed to navigation consumers."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

import numpy as np

from .models import PositionEstimate


@dataclass(frozen=True)
class NavigationObservation:
    position: tuple[float, float] | None
    velocity: tuple[float, float] | None
    covariance: object | None
    executable: bool
    instance_id: str
    registration_version: int
    safety_radius: float
    reason: str
    metadata: Mapping[str, object] = MappingProxyType({})


class NavigationLocalizationAdapter:
    def __init__(self, *, max_age_ms: int = 500, player_radius: float = 1.0, uncertainty_factor: float = 2.0, map_error: float = 1.0) -> None:
        self.max_age_ms = int(max_age_ms)
        self.player_radius = float(player_radius)
        self.uncertainty_factor = float(uncertainty_factor)
        self.map_error = float(map_error)
        if self.max_age_ms < 0 or min(self.player_radius, self.uncertainty_factor, self.map_error) < 0:
            raise ValueError("navigation localization limits must be non-negative")

    def to_observation(self, estimate: PositionEstimate, *, now_ms: int, expected_instance_id: str | None = None, expected_registration_version: int | None = None) -> NavigationObservation:
        captured_at_ms = estimate.diagnostics.get("captured_at_ms")
        if isinstance(captured_at_ms, (int, float)) and np.isfinite(captured_at_ms):
            diagnostic_age = int(now_ms) - int(captured_at_ms)
        else:
            diagnostic_age = int(estimate.age_ms)
        age = max(int(estimate.age_ms), diagnostic_age)
        instance_matches = expected_instance_id is None or estimate.instance_id == expected_instance_id
        version_matches = expected_registration_version is None or estimate.registration_version == int(expected_registration_version)
        executable = estimate.status == "confirmed" and estimate.fresh and age <= self.max_age_ms and estimate.position is not None and instance_matches and version_matches
        uncertainty = 0.0
        if estimate.covariance is not None:
            uncertainty = float(np.sqrt(max(float(np.max(np.linalg.eigvalsh(estimate.covariance))), 0.0)))
        safety_radius = self.player_radius + self.uncertainty_factor * uncertainty + self.map_error
        if not instance_matches:
            reason = "instance_mismatch"
        elif not version_matches:
            reason = "registration_version_mismatch"
        else:
            reason = "" if executable else estimate.reason or "localization_not_ready"
        return NavigationObservation(
            estimate.position,
            estimate.velocity,
            estimate.covariance,
            executable,
            estimate.instance_id,
            estimate.registration_version,
            safety_radius,
            reason,
            {"age_ms": age, "evidence_version": estimate.evidence_version},
        )


__all__ = ["NavigationLocalizationAdapter", "NavigationObservation"]
