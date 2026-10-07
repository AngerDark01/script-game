"""Bounded restart and generation isolation for long-lived worker handles."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Callable

from .generation import GenerationToken


class SupervisorState(StrEnum):
    STOPPED = "stopped"
    RUNNING = "running"
    BACKOFF = "backoff"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class SupervisorStatus:
    state: SupervisorState
    generation: int | None
    restart_count: int
    next_restart_at_ms: int | None
    last_error: str = ""


class ProcessSupervisor:
    """Own one injected worker handle and restart it at most N times per token."""

    def __init__(
        self,
        factory: Callable[[], Any],
        *,
        max_restarts: int = 3,
        backoff_ms: tuple[int, ...] = (100, 500, 2_000),
        clock_ms: Callable[[], int] | None = None,
    ) -> None:
        if int(max_restarts) < 0 or not backoff_ms or any(int(value) < 0 for value in backoff_ms):
            raise ValueError("supervisor restart policy is invalid")
        self.factory = factory
        self.max_restarts = int(max_restarts)
        self.backoff_ms = tuple(int(value) for value in backoff_ms)
        self.clock_ms = clock_ms or (lambda: 0)
        self.handle: Any | None = None
        self.token: GenerationToken | None = None
        self._restart_count = 0
        self._next_restart_at_ms: int | None = None
        self._state = SupervisorState.STOPPED
        self._last_error = ""
        self._stop_requested = False

    @property
    def status(self) -> SupervisorStatus:
        return SupervisorStatus(
            self._state,
            self.token.generation if self.token is not None else None,
            self._restart_count,
            self._next_restart_at_ms,
            self._last_error,
        )

    def start(self, token: GenerationToken, *, now_ms: int | None = None) -> None:
        if self._state is not SupervisorState.STOPPED:
            raise RuntimeError("worker supervisor is already active")
        self.token = token
        self._restart_count = 0
        self._next_restart_at_ms = None
        self._last_error = ""
        self._stop_requested = False
        self._start_handle()

    def poll(self, *, now_ms: int | None = None) -> Any | None:
        now = int(self.clock_ms() if now_ms is None else now_ms)
        if self._state is SupervisorState.BACKOFF:
            if self._next_restart_at_ms is not None and now >= self._next_restart_at_ms:
                self._start_handle()
            else:
                return None
        if self._state is not SupervisorState.RUNNING or self.handle is None:
            return None
        event = self.handle.poll_latest()
        if event is None:
            return None
        kind = str(getattr(event, "kind", ""))
        generation = getattr(event, "generation", None)
        if self.token is None or generation is None or int(generation) != self.token.generation:
            return None
        if kind == "error":
            self._schedule_restart(str(getattr(event, "error", "worker_error")), now)
        elif kind == "stopped" and not self._stop_requested:
            self._schedule_restart("unexpected_worker_stop", now)
        return event

    def stop(self) -> None:
        self._stop_requested = True
        handle = self.handle
        self.handle = None
        self._state = SupervisorState.STOPPED
        self._next_restart_at_ms = None
        try:
            if handle is not None:
                handle.stop()
        finally:
            self.token = None

    def _start_handle(self) -> None:
        if self.token is None:
            raise RuntimeError("worker token is missing")
        self.handle = self.factory()
        self.handle.start(generation=self.token.generation, map_instance=self.token.map_instance)
        self._state = SupervisorState.RUNNING
        self._next_restart_at_ms = None

    def _schedule_restart(self, error: str, now_ms: int) -> None:
        handle = self.handle
        self.handle = None
        if handle is not None:
            handle.stop()
        self._last_error = str(error)
        self._restart_count += 1
        if self._restart_count > self.max_restarts:
            self._state = SupervisorState.FAILED
            self._next_restart_at_ms = None
            return
        delay = self.backoff_ms[min(self._restart_count - 1, len(self.backoff_ms) - 1)]
        self._next_restart_at_ms = int(now_ms) + delay
        self._state = SupervisorState.BACKOFF


__all__ = ["ProcessSupervisor", "SupervisorState", "SupervisorStatus"]
