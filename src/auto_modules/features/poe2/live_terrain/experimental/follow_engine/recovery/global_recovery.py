"""Single-flight asynchronous global recovery backend."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
import time
from typing import Any, Callable

from ..generation import GenerationToken


@dataclass(frozen=True, slots=True)
class GlobalRecoveryResult:
    generation: int
    map_instance: str
    value: Any = None
    error: str = ""
    elapsed_ms: float = 0.0


class GlobalRecoveryBackend:
    def __init__(
        self,
        worker: Callable[..., Any],
        *,
        executor: ThreadPoolExecutor | None = None,
        failure_cooldown_ms: int = 1000,
        max_failure_cooldown_ms: int = 10_000,
        clock_ms: Callable[[], int] | None = None,
    ) -> None:
        if int(failure_cooldown_ms) < 0 or int(max_failure_cooldown_ms) < int(failure_cooldown_ms):
            raise ValueError("global recovery cooldown bounds are invalid")
        self._worker = worker
        self._executor = executor or ThreadPoolExecutor(max_workers=1, thread_name_prefix="follow-global-recovery")
        self._owns_executor = executor is None
        self._future: Future | None = None
        self._generation: int | None = None
        self._map_instance: str | None = None
        self._submitted_at: float | None = None
        self._failure_cooldown_ms = int(failure_cooldown_ms)
        self._max_failure_cooldown_ms = int(max_failure_cooldown_ms)
        self._clock_ms = clock_ms or (lambda: int(time.monotonic() * 1000.0))
        self._failure_count = 0
        self._next_submit_at_ms = 0

    @property
    def in_flight(self) -> bool:
        """Return whether this generation still owns an unconsumed task.

        A completed future remains in-flight from the backend contract's point
        of view until ``poll`` consumes it.  Treating a completed-but-unpolled
        future as available allows a fast worker to be submitted twice before
        the control tick has observed the first result.
        """
        return self._future is not None

    def cooldown_ready(self, *, now_ms: int | None = None) -> bool:
        current = int(self._clock_ms() if now_ms is None else now_ms)
        return current >= self._next_submit_at_ms

    def record_failure(self, *, now_ms: int | None = None) -> None:
        """Back off after a completed task produced no usable recovery value."""
        self._failure_count += 1
        delay = min(
            self._max_failure_cooldown_ms,
            self._failure_cooldown_ms * (2 ** max(0, self._failure_count - 1)),
        )
        current = int(self._clock_ms() if now_ms is None else now_ms)
        self._next_submit_at_ms = current + delay

    def submit(self, token: GenerationToken, *, now_ms: int | None = None, **kwargs: Any) -> bool:
        # Single-flight is defined by submission/consumption, not by executor
        # execution state.  The caller must poll the completed result before a
        # new global registration may be submitted for the same or new token.
        if self.in_flight or not self.cooldown_ready(now_ms=now_ms):
            return False
        self._generation = token.generation
        self._map_instance = token.map_instance
        self._submitted_at = time.perf_counter()
        self._future = self._executor.submit(self._worker, **kwargs)
        return True

    def poll(self, token: GenerationToken, *, now_ms: int | None = None) -> GlobalRecoveryResult | None:
        future = self._future
        if future is None or not future.done():
            return None
        self._future = None
        started = self._submitted_at or time.perf_counter()
        self._submitted_at = None
        if self._generation != token.generation or self._map_instance != token.map_instance:
            return GlobalRecoveryResult(token.generation, token.map_instance, error="stale_global_result", elapsed_ms=0.0)
        try:
            value = future.result()
            self._failure_count = 0
            self._next_submit_at_ms = 0
            return GlobalRecoveryResult(
                token.generation,
                token.map_instance,
                value=value,
                elapsed_ms=(time.perf_counter() - started) * 1000.0,
            )
        except Exception as exc:
            self.record_failure(now_ms=now_ms)
            return GlobalRecoveryResult(
                token.generation,
                token.map_instance,
                error=f"{type(exc).__name__}: {exc}",
                elapsed_ms=(time.perf_counter() - started) * 1000.0,
            )

    def close(self) -> None:
        if self._owns_executor:
            self._executor.shutdown(wait=False, cancel_futures=True)
