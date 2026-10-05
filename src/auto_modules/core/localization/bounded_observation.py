"""Identity-independent bounds for temporarily missing position observations."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Hashable


@dataclass(frozen=True)
class RoleObservation:
    position: tuple[float, float]
    last_seen_at_ms: int
    age_ms: int
    uncertainty: float
    visible: bool
    available: bool


class BoundedRoleObservations:
    def __init__(
        self,
        *,
        max_age_ms: int = 2000,
        max_uncertainty: float = 10.0,
        drift_per_second: float = 4.5,
        observed_uncertainty: float = 0.5,
        reappearance_frames: int = 2,
        reappearance_after_missing: int = 2,
        reappearance_radius: float = 8.0,
    ) -> None:
        if (max_age_ms < 1 or max_uncertainty <= 0 or drift_per_second < 0
                or observed_uncertainty < 0 or reappearance_frames < 1
                or reappearance_after_missing < 0 or reappearance_radius < 0):
            raise ValueError("invalid observation bounds")
        self.max_age_ms = int(max_age_ms)
        self.max_uncertainty = float(max_uncertainty)
        self.drift_per_second = float(drift_per_second)
        self.observed_uncertainty = float(observed_uncertainty)
        self.reappearance_frames = int(reappearance_frames)
        self.reappearance_after_missing = int(reappearance_after_missing)
        self.reappearance_radius = float(reappearance_radius)
        self._positions: dict[Hashable, tuple[float, float]] = {}
        self._last_seen: dict[Hashable, int] = {}
        self._missing: dict[Hashable, int] = {}
        self._pending: dict[Hashable, tuple[tuple[float, float], int]] = {}

    def seed(self, identity: Hashable, position: tuple[float, float], *, at_ms: int) -> None:
        self._positions[identity] = self._point(position)
        self._last_seen[identity] = int(at_ms)
        self._missing[identity] = 0
        self._pending.pop(identity, None)

    def update(
        self,
        identity: Hashable,
        *,
        at_ms: int,
        candidate: tuple[float, float] | None,
        reacquisition_reference: tuple[float, float] | None = None,
        reacquisition_radius: float | None = None,
    ) -> RoleObservation:
        if identity not in self._positions:
            raise KeyError(identity)
        now = int(at_ms)
        if now < self._last_seen[identity]:
            raise ValueError("observation time must not move backwards")
        estimate = self._snapshot(identity, now, visible=False)
        if candidate is not None:
            point = self._point(candidate)
            needs_confirmation = (
                self._missing[identity] >= self.reappearance_after_missing
                or (self._missing[identity] > 0 and reacquisition_reference is not None)
            )
            reference = (
                self._point(reacquisition_reference)
                if reacquisition_reference is not None and self._missing[identity] > 0
                else estimate.position
            )
            radius = (
                self.reappearance_radius
                if reacquisition_radius is None else float(reacquisition_radius)
            )
            if not math.isfinite(radius) or radius < 0:
                raise ValueError("reacquisition radius must be finite and nonnegative")
            within_gate = (
                not needs_confirmation
                or math.dist(point, reference) <= radius + (
                    0.0 if reacquisition_reference is not None else estimate.uncertainty
                )
            )
            can_reacquire = estimate.available or reacquisition_reference is not None
            if needs_confirmation and within_gate and can_reacquire:
                pending = self._pending.get(identity)
                count = pending[1] + 1 if pending and math.dist(point, pending[0]) <= self.reappearance_radius else 1
                self._pending[identity] = (point, count)
                needs_confirmation = count < self.reappearance_frames
            if within_gate and can_reacquire and not needs_confirmation:
                self.seed(identity, point, at_ms=now)
                return self._snapshot(identity, now, visible=True)
            if not within_gate:
                self._pending.pop(identity, None)
        else:
            self._pending.pop(identity, None)
        self._missing[identity] += 1
        return self._snapshot(identity, now, visible=False)

    def _snapshot(self, identity: Hashable, now: int, *, visible: bool) -> RoleObservation:
        age = max(0, now - self._last_seen[identity])
        uncertainty = self.observed_uncertainty + self.drift_per_second * age / 1000.0
        return RoleObservation(
            self._positions[identity], self._last_seen[identity], age, uncertainty,
            visible, age <= self.max_age_ms and uncertainty <= self.max_uncertainty,
        )

    @staticmethod
    def _point(value: tuple[float, float]) -> tuple[float, float]:
        point = (float(value[0]), float(value[1]))
        if not all(math.isfinite(component) for component in point):
            raise ValueError("position must be finite")
        return point


__all__ = ["RoleObservation", "BoundedRoleObservations"]
