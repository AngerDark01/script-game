"""In-process latest-only buffer used by capture and processing loops."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from typing import Generic, TypeVar
import time


T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class LatestFrame(Generic[T]):
    sequence: int
    value: T


class LatestFrameBuffer(Generic[T]):
    def __init__(self) -> None:
        self._lock = Lock()
        self._latest: LatestFrame[T] | None = None
        self._dropped = 0

    @property
    def dropped_count(self) -> int:
        with self._lock:
            return self._dropped

    def publish(self, sequence: int, value: T) -> bool:
        sequence = int(sequence)
        if sequence < 0:
            raise ValueError("sequence must be non-negative")
        with self._lock:
            if self._latest is not None and sequence <= self._latest.sequence:
                self._dropped += 1
                return False
            if self._latest is not None:
                self._dropped += 1
            self._latest = LatestFrame(sequence, value)
            return True

    def take(self, *, after_sequence: int = -1) -> LatestFrame[T] | None:
        with self._lock:
            latest = self._latest
            if latest is None or latest.sequence <= int(after_sequence):
                return None
            return latest

    def clear(self) -> None:
        with self._lock:
            self._latest = None

    def diagnostics(self, *, now_ms: float | None = None) -> dict[str, float | int | None]:
        with self._lock:
            latest = self._latest
            dropped = self._dropped
        captured = getattr(latest.value, "captured_at_ms", None) if latest is not None else None
        now = time.monotonic() * 1000.0 if now_ms is None else float(now_ms)
        return {
            "queue_depth": 0 if latest is None else 1,
            "latest_sequence": None if latest is None else latest.sequence,
            "latest_only_dropped_count": dropped,
            "queue_age_ms": None if captured is None else max(0.0, now - float(captured)),
        }
