"""Frozen local map snapshot shared by the experimental motion stages."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from .motion_models import MotionObservation, _point


@dataclass(frozen=True, slots=True)
class MotionSnapshot:
    observation: MotionObservation
    wall_map: np.ndarray
    distance_field: np.ndarray
    route: tuple[tuple[float, float], ...]
    target: tuple[float, float]
    peer_position: tuple[float, float] | None
    unknown_mask: np.ndarray | None = None

    def __post_init__(self) -> None:
        wall_map = np.array(self.wall_map, dtype=np.uint8, copy=True, order="C")
        distance_field = np.array(self.distance_field, dtype=np.float32, copy=True, order="C")
        if wall_map.ndim != 2 or wall_map.size == 0:
            raise ValueError("wall_map must be a non-empty 2-D array")
        if distance_field.shape != wall_map.shape or not np.isfinite(distance_field).all():
            raise ValueError("distance_field must match wall_map and be finite")
        wall_map.setflags(write=False)
        distance_field.setflags(write=False)
        object.__setattr__(self, "wall_map", wall_map)
        object.__setattr__(self, "distance_field", distance_field)
        object.__setattr__(self, "route", tuple(_point(point, "route point") for point in self.route))
        object.__setattr__(self, "target", _point(self.target, "target"))
        object.__setattr__(self, "peer_position", None if self.peer_position is None else _point(self.peer_position, "peer_position"))
        if self.target != self.observation.target:
            raise ValueError("snapshot target does not match observation")
        if self.peer_position != self.observation.peer_position:
            raise ValueError("snapshot peer position does not match observation")
        if self.unknown_mask is not None:
            unknown_mask = np.asarray(self.unknown_mask, dtype=bool)
            if unknown_mask.shape != wall_map.shape:
                raise ValueError("unknown_mask must match wall_map")
            unknown_mask = np.array(unknown_mask, copy=True, order="C")
            unknown_mask.setflags(write=False)
            object.__setattr__(self, "unknown_mask", unknown_mask)


def build_motion_snapshot(
    *,
    observation: MotionObservation,
    wall_map: Any,
    distance_field: Any,
    route: tuple[tuple[float, float], ...] | list[tuple[float, float]],
    target: tuple[float, float],
    peer_position: tuple[float, float] | None,
    map_version: str | None = None,
    unknown_mask: Any | None = None,
) -> MotionSnapshot:
    """Build one version-fenced snapshot for all motion decisions in a tick."""
    if not isinstance(observation, MotionObservation):
        raise TypeError("observation must be MotionObservation")
    if map_version is not None and str(map_version).strip() != observation.map_version:
        raise ValueError("motion snapshot map version does not match observation")
    if _point(target, "target") != observation.target:
        raise ValueError("snapshot target does not match observation")
    normalized_peer = None if peer_position is None else _point(peer_position, "peer_position")
    if normalized_peer != observation.peer_position:
        raise ValueError("peer position does not match observation")
    return MotionSnapshot(
        observation=observation,
        wall_map=wall_map,
        distance_field=distance_field,
        route=tuple(route),
        target=target,
        peer_position=normalized_peer,
        unknown_mask=unknown_mask,
    )


__all__ = ["MotionSnapshot", "build_motion_snapshot"]
