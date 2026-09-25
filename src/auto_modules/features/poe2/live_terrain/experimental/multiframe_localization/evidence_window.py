"""Bounded, segment-aware key-frame evidence storage."""

from __future__ import annotations

from collections import deque
import math

from .models import MultiFrameEvidence


class EvidenceWindow:
    def __init__(
        self,
        *,
        max_keyframes: int = 24,
        max_window_ms: int = 30_000,
        max_travel_distance: float = 1024.0,
        max_bytes: int = 64 * 1024 * 1024,
    ) -> None:
        if (
            max_keyframes < 1
            or max_window_ms < 1
            or max_travel_distance <= 0
            or max_bytes < 1
        ):
            raise ValueError("evidence window limits must be positive")
        self.max_keyframes = int(max_keyframes)
        self.max_window_ms = int(max_window_ms)
        self.max_travel_distance = float(max_travel_distance)
        self.max_bytes = int(max_bytes)
        self._frames: deque[MultiFrameEvidence] = deque()
        self._segment_id = 0
        self._version = 0
        self.last_break_reason = ""

    @property
    def version(self) -> int:
        return self._version

    @property
    def segment_id(self) -> int:
        return self._segment_id

    @property
    def travel_distance(self) -> float:
        frames = tuple(self._frames)
        return float(
            sum(
                math.dist(previous.local_offset, current.local_offset)
                for previous, current in zip(frames, frames[1:])
            )
        )

    @property
    def estimated_bytes(self) -> int:
        total = 0
        for item in self._frames:
            for value in (item.frame.wall_mask, item.observed_mask, item.raw_frame):
                if value is not None:
                    total += int(value.nbytes)
        return total

    def append(self, evidence: MultiFrameEvidence) -> bool:
        if not isinstance(evidence, MultiFrameEvidence):
            raise TypeError("evidence must be MultiFrameEvidence")
        if evidence.segment_id < self._segment_id:
            return False
        if evidence.segment_id > self._segment_id:
            self._segment_id = evidence.segment_id
            self._frames.clear()
            self._version += 1
            self.last_break_reason = "segment_changed"
        if not evidence.is_keyframe or not evidence.motion.accepted or evidence.motion.distance <= 0:
            return False
        self._frames.append(evidence)
        self._trim()
        self._version += 1
        return True

    def _trim(self) -> None:
        self._trim_by_time()
        while len(self._frames) > self.max_keyframes:
            self._frames.popleft()
        while len(self._frames) > 1 and (
            self.travel_distance > self.max_travel_distance
            or self.estimated_bytes > self.max_bytes
        ):
            self._frames.popleft()

    def _trim_by_time(self) -> None:
        if not self._frames:
            return
        newest = self._frames[-1].frame.captured_at_ms
        while self._frames and newest - self._frames[0].frame.captured_at_ms > self.max_window_ms:
            self._frames.popleft()

    def break_segment(self, reason: str) -> int:
        self._segment_id += 1
        self._frames.clear()
        self._version += 1
        self.last_break_reason = str(reason)
        return self._segment_id

    def clear(self, reason: str, *, reset_segment: bool = False) -> None:
        self._frames.clear()
        if reset_segment:
            self._segment_id = 0
        self._version += 1
        self.last_break_reason = str(reason)

    def snapshot(self) -> tuple[MultiFrameEvidence, ...]:
        return tuple(self._frames)


__all__ = ["EvidenceWindow"]
