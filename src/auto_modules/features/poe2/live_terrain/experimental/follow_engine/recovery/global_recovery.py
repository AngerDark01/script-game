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
    def __init__(self, worker: Callable[..., Any], *, executor: ThreadPoolExecutor | None = None) -> None:
        self._worker = worker
        self._executor = executor or ThreadPoolExecutor(max_workers=1, thread_name_prefix="follow-global-recovery")
        self._owns_executor = executor is None
        self._future: Future | None = None
        self._generation: int | None = None
        self._submitted_at: float | None = None

    @property
    def in_flight(self) -> bool:
        """Return whether this generation still owns an unconsumed task.

        A completed future remains in-flight from the backend contract's point
        of view until ``poll`` consumes it.  Treating a completed-but-unpolled
        future as available allows a fast worker to be submitted twice before
        the control tick has observed the first result.
        """
        return self._future is not None

    def submit(self, token: GenerationToken, **kwargs: Any) -> bool:
        # Single-flight is defined by submission/consumption, not by executor
        # execution state.  The caller must poll the completed result before a
        # new global registration may be submitted for the same or new token.
        if self.in_flight:
            return False
        self._generation = token.generation
        self._submitted_at = time.perf_counter()
        self._future = self._executor.submit(self._worker, **kwargs)
        return True

    def poll(self, token: GenerationToken) -> GlobalRecoveryResult | None:
        future = self._future
        if future is None or not future.done():
            return None
        self._future = None
        started = self._submitted_at or time.perf_counter()
        self._submitted_at = None
        if self._generation != token.generation:
            return GlobalRecoveryResult(token.generation, token.map_instance, error="stale_global_result", elapsed_ms=0.0)
        try:
            value = future.result()
            return GlobalRecoveryResult(
                token.generation,
                token.map_instance,
                value=value,
                elapsed_ms=(time.perf_counter() - started) * 1000.0,
            )
        except Exception as exc:
            return GlobalRecoveryResult(
                token.generation,
                token.map_instance,
                error=f"{type(exc).__name__}: {exc}",
                elapsed_ms=(time.perf_counter() - started) * 1000.0,
            )

    def close(self) -> None:
        if self._owns_executor:
            self._executor.shutdown(wait=False, cancel_futures=True)
