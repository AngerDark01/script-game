"""Low-frequency dual-player memory reanchor with transform reuse."""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any, Callable


@dataclass(frozen=True)
class MemoryReanchorResult:
    positions: dict[str, tuple[float, float]]
    area_instance: str
    elapsed_ms: float


class MemoryFastReanchor:
    """Read both roles once and map them without visual registration."""

    def __init__(self, source: Any, *, transform: Callable[[tuple[float, float]], tuple[float, float]], cooldown_ms: int = 8_000, expected_players: int = 2, clock_ms: Callable[[], int] | None = None) -> None:
        self.source = source
        self.transform = transform
        self.cooldown_ms = int(cooldown_ms)
        self.expected_players = int(expected_players)
        if self.expected_players < 1:
            raise ValueError("expected_players must be positive")
        self.clock_ms = clock_ms or (lambda: int(time.monotonic() * 1000.0))
        self._last_read_ms: int | None = None

    def read(self, *, expected_instance_id: str, now_ms: int | None = None) -> MemoryReanchorResult:
        perf_started = time.perf_counter()
        started = self.clock_ms() if now_ms is None else int(now_ms)
        if self._last_read_ms is not None and started - self._last_read_ms < self.cooldown_ms:
            raise RuntimeError("memory reanchor cooldown")
        samples = tuple(self.source.read_many(expected_instance_id))
        if len(samples) != self.expected_players:
            raise RuntimeError(
                f"memory reanchor expected {self.expected_players} players, found {len(samples)}"
            )
        instances = {str(sample.area_instance) for sample in samples}
        if instances != {str(expected_instance_id)}:
            raise RuntimeError("memory reanchor area instance mismatch")
        positions = {}
        for sample in samples:
            point = tuple(float(value) for value in self.transform(sample.grid))
            if len(point) != 2:
                raise RuntimeError("memory reanchor transform must return two coordinates")
            positions[str(sample.identity)] = point
        self._last_read_ms = started
        elapsed_ms = (time.perf_counter() - perf_started) * 1000.0
        return MemoryReanchorResult(positions, str(expected_instance_id), elapsed_ms)


__all__ = ["MemoryFastReanchor", "MemoryReanchorResult"]
