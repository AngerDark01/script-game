"""Deterministic fusion of visual and bounded command observations."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FusedObservation:
    position: tuple[float, float]
    source: str
    uncertainty_native: float
    captured_at_ms: int


def fuse_observation(
    *,
    visual: FusedObservation | None,
    predicted: FusedObservation | None,
    max_visual_age_ms: int = 700,
    now_ms: int | None = None,
) -> FusedObservation | None:
    """Prefer fresh visual data, otherwise return bounded prediction."""
    if visual is not None and (
        now_ms is None or now_ms - visual.captured_at_ms <= max_visual_age_ms
    ):
        return visual
    return predicted
