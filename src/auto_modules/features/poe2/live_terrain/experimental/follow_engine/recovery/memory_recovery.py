"""Generation-checked adapter around the low-frequency memory reanchor."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Callable

from ...multiplayer_follow.recovery.memory_fast_reanchor import MemoryFastReanchor
from ..generation import GenerationToken


@dataclass(frozen=True, slots=True)
class MemoryRecoveryResult:
    generation: int
    map_instance: str
    positions: dict[str, tuple[float, float]]
    elapsed_ms: float
    source: str = "memory_transform"
    error: str = ""


class MemoryRecoveryBackend:
    def __init__(
        self,
        source: Any,
        *,
        transform: Callable[[tuple[float, float]], tuple[float, float]],
        cooldown_ms: int = 8_000,
        expected_players: int = 2,
        clock_ms: Callable[[], int] | None = None,
        executor: ThreadPoolExecutor | None = None,
    ) -> None:
        self._reader = MemoryFastReanchor(
            source,
            transform=transform,
            cooldown_ms=cooldown_ms,
            expected_players=expected_players,
            clock_ms=clock_ms,
        )
        self._executor = executor or ThreadPoolExecutor(max_workers=1, thread_name_prefix="follow-memory-recovery")
        self._owns_executor = executor is None
        self._future: Future | None = None
        self._generation: int | None = None

    @property
    def in_flight(self) -> bool:
        """Return whether a submitted read still awaits control-tick consumption."""
        return self._future is not None

    def cooldown_ready(self, *, now_ms: int | None = None) -> bool:
        return self._reader.cooldown_ready(now_ms=now_ms)

    def read(self, token: GenerationToken, *, now_ms: int | None = None) -> MemoryRecoveryResult:
        result = self._reader.read(expected_instance_id=token.map_instance, now_ms=now_ms)
        return MemoryRecoveryResult(token.generation, token.map_instance, result.positions, result.elapsed_ms)

    def submit(self, token: GenerationToken, *, now_ms: int | None = None) -> bool:
        """Submit at most one warm read until its result is polled."""
        if self._future is not None:
            return False
        self._generation = token.generation
        self._future = self._executor.submit(self.read, token, now_ms=now_ms)
        return True

    def poll(self, token: GenerationToken) -> MemoryRecoveryResult | None:
        future = self._future
        if future is None or not future.done():
            return None
        self._future = None
        generation = self._generation
        self._generation = None
        if generation != token.generation:
            return MemoryRecoveryResult(token.generation, token.map_instance, {}, 0.0, error="stale_memory_result")
        try:
            result = future.result()
        except Exception as exc:
            return MemoryRecoveryResult(
                token.generation,
                token.map_instance,
                {},
                0.0,
                error=f"{type(exc).__name__}: {exc}",
            )
        return result

    def close(self) -> None:
        if self._owns_executor:
            self._executor.shutdown(wait=False, cancel_futures=True)
