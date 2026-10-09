"""Small bounded timing windows shared by follow-engine diagnostics.

The values are monotonic wall-clock measurements. They are observability only;
they never participate in movement or recovery decisions.
"""

from __future__ import annotations

import time
from collections import deque
from threading import Lock
from typing import Iterable


def monotonic_ms() -> float:
    return time.perf_counter() * 1000.0


def percentile(values: Iterable[float], quantile: float) -> float | None:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return None
    index = min(len(ordered) - 1, int(round((len(ordered) - 1) * float(quantile))))
    return ordered[index]


class TimingWindow:
    def __init__(self, size: int = 256) -> None:
        self._size = max(1, int(size))
        self._values: deque[float] = deque(maxlen=self._size)
        self._lock = Lock()

    def __getstate__(self) -> dict[str, object]:
        """Return only data that is safe to cross a Windows spawn boundary.

        TimingWindow is embedded in worker objects (for example the vision
        processor).  Its lock protects parent/worker-local diagnostics but is
        not part of the runtime state and cannot be pickled by multiprocessing.
        A fresh lock is recreated in ``__setstate__`` in the child process.
        """
        with self._lock:
            values = tuple(self._values)
        return {"size": self._size, "values": values}

    def __setstate__(self, state: dict[str, object]) -> None:
        size = max(1, int(state.get("size", 256)))
        self._size = size
        self._values = deque(
            (max(0.0, float(value)) for value in state.get("values", ())),
            maxlen=size,
        )
        self._lock = Lock()

    def add(self, value_ms: float) -> None:
        with self._lock:
            self._values.append(max(0.0, float(value_ms)))

    def as_dict(self, prefix: str = "") -> dict[str, float | int | None]:
        with self._lock:
            values = tuple(self._values)
        return {
            f"{prefix}p50_ms": percentile(values, 0.50),
            f"{prefix}p95_ms": percentile(values, 0.95),
            f"{prefix}max_ms": max(values) if values else None,
            f"{prefix}sample_count": len(values),
        }


__all__ = ["TimingWindow", "monotonic_ms", "percentile"]
