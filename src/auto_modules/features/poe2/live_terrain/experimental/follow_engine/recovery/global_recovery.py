"""Single-flight asynchronous global recovery backend."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Callable

from ..generation import GenerationToken


@dataclass(frozen=True, slots=True)
class GlobalRecoveryResult:
    generation: int
    map_instance: str
    value: Any = None
    error: str = ""


class GlobalRecoveryBackend:
    def __init__(self, worker: Callable[..., Any], *, executor: ThreadPoolExecutor | None = None) -> None:
        self._worker = worker
        self._executor = executor or ThreadPoolExecutor(max_workers=1, thread_name_prefix="follow-global-recovery")
        self._owns_executor = executor is None
        self._future: Future | None = None
        self._generation: int | None = None

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
        self._future = self._executor.submit(self._worker, **kwargs)
        return True

    def poll(self, token: GenerationToken) -> GlobalRecoveryResult | None:
        future = self._future
        if future is None or not future.done():
            return None
        self._future = None
        if self._generation != token.generation:
            return GlobalRecoveryResult(token.generation, token.map_instance, error="stale_global_result")
        try:
            return GlobalRecoveryResult(token.generation, token.map_instance, value=future.result())
        except Exception as exc:
            return GlobalRecoveryResult(token.generation, token.map_instance, error=f"{type(exc).__name__}: {exc}")

    def close(self) -> None:
        if self._owns_executor:
            self._executor.shutdown(wait=False, cancel_futures=True)
