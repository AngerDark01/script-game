"""High-frequency minimap marker extraction adapter."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Sequence

import numpy as np

from auto_modules.features.poe2.live_terrain.experimental.multiplayer_localization.marker_candidates import (
    detect_saturated_marker_observation,
    marker_candidates_from_observation,
)
from auto_modules.features.poe2.live_terrain.experimental.multiplayer_localization.models import (
    MarkerColorProfile,
    PlayerMarkerCandidate,
)


@dataclass(frozen=True, slots=True)
class MarkerObservation:
    candidates: tuple[PlayerMarkerCandidate, ...]
    raw_candidate_count: int
    processing_ms: float
    source: str


def extract_markers(
    image: Any,
    captured_at_ms: int,
    *,
    profiles: Sequence[MarkerColorProfile] | None = None,
    max_candidates: int = 6,
) -> MarkerObservation:
    started = time.perf_counter()
    observation = detect_saturated_marker_observation(
        np.asarray(image),
        int(captured_at_ms),
        profiles=tuple(profiles) if profiles is not None else None,
    )
    candidates = marker_candidates_from_observation(observation, max_candidates=int(max_candidates))
    return MarkerObservation(
        candidates=candidates,
        raw_candidate_count=len(observation.candidates),
        processing_ms=(time.perf_counter() - started) * 1000.0,
        source=observation.source,
    )
