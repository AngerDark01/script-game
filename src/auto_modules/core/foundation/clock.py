"""Clock abstraction for deterministic runtime timing."""

from __future__ import annotations

import time


class MonotonicClock:
    def now(self) -> float:
        return time.monotonic()
