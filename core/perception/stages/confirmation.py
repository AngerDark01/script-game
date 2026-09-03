from __future__ import annotations

from dataclasses import dataclass, field
from typing import Hashable, Iterable

import numpy as np

from ..models import TargetDetection


@dataclass(frozen=True)
class ConfirmationResult:
    """Confirmed detections and the state of the current profile frame."""

    detections: tuple[TargetDetection, ...]
    confirmed: bool
    counts: tuple[int, ...] = ()


@dataclass
class _Track:
    detection: TargetDetection
    count: int


class ConfirmationTracker:
    """Track spatially stable candidates independently for each target profile."""

    def __init__(self) -> None:
        self._tracks: dict[Hashable, list[_Track]] = {}

    def observe(
        self,
        profile_key: Hashable,
        detections: Iterable[TargetDetection],
        *,
        required_frames: int,
        match_radius: float,
    ) -> ConfirmationResult:
        required = max(1, int(required_frames))
        current = tuple(detections)
        if required == 1:
            self._tracks.pop(profile_key, None)
            return ConfirmationResult(current, bool(current), tuple(1 for _ in current))
        if not current:
            self._tracks.pop(profile_key, None)
            return ConfirmationResult((), False, ())

        previous = self._tracks.get(profile_key, [])
        next_tracks: list[_Track] = []
        used: set[int] = set()
        for detection in current:
            match_index = _nearest_track(previous, detection, float(match_radius), used)
            if match_index is None:
                next_tracks.append(_Track(detection, 1))
                continue
            used.add(match_index)
            next_tracks.append(_Track(detection, previous[match_index].count + 1))
        self._tracks[profile_key] = next_tracks
        confirmed_tracks = tuple(track for track in next_tracks if track.count >= required)
        return ConfirmationResult(
            detections=tuple(track.detection for track in confirmed_tracks),
            confirmed=bool(confirmed_tracks),
            counts=tuple(track.count for track in next_tracks),
        )

    def reset(self, profile_key: Hashable | None = None) -> None:
        if profile_key is None:
            self._tracks.clear()
        else:
            self._tracks.pop(profile_key, None)


def _nearest_track(
    tracks: list[_Track],
    detection: TargetDetection,
    radius: float,
    used: set[int],
) -> int | None:
    best_index = None
    best_distance = None
    for index, track in enumerate(tracks):
        if index in used:
            continue
        previous = track.detection
        if previous.target_type != detection.target_type or previous.coordinate_space != detection.coordinate_space:
            continue
        distance = float(np.hypot(previous.center[0] - detection.center[0], previous.center[1] - detection.center[1]))
        if distance <= radius and (best_distance is None or distance < best_distance):
            best_index = index
            best_distance = distance
    return best_index
