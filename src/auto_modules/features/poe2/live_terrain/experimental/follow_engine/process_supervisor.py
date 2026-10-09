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
            # A native/OS failure can terminate a multiprocessing worker
            # before it can enqueue the structured ``error`` event.  Do not
            # leave the supervisor in RUNNING forever in that case.  Fake
            # handles without a process attribute remain compatible.
            process = getattr(self.handle, "process", None)
            is_alive = getattr(process, "is_alive", None)
            if process is not None and callable(is_alive) and not bool(is_alive()):
                self._schedule_restart("worker_exited_without_event", now)
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
        handle = self.factory()
        try:
            handle.start(generation=self.token.generation, map_instance=self.token.map_instance)
        except BaseException as exc:
            # A failed start must not leave an allocated handle attached to a
            # stopped supervisor.  Best-effort cleanup is isolated so the
            # original spawn/pickle error remains the one callers see.
            try:
                handle.stop()
            except Exception:
                pass
            self.handle = None
            self._state = SupervisorState.STOPPED
            self._next_restart_at_ms = None
            self._last_error = f"start_failed: {type(exc).__name__}: {exc}"
            self.token = None
            raise
        self.handle = handle
        self._state = SupervisorState.RUNNING
        self._next_restart_at_ms = None

    def _schedule_restart(self, error: str, now_ms: int) -> None:
        handle = self.handle
        self.handle = None
        stop_error = None
        if handle is not None:
            try:
                handle.stop()
            except Exception as exc:
                # A broken worker must not prevent the supervisor from
                # entering a bounded backoff/failed state.
                stop_error = exc
        self._last_error = str(error)
        if stop_error is not None:
            self._last_error = f"{self._last_error}; stop_failed: {type(stop_error).__name__}: {stop_error}"
        self._restart_count += 1
        if self._restart_count > self.max_restarts:
            self._state = SupervisorState.FAILED
            self._next_restart_at_ms = None
            return
        delay = self.backoff_ms[min(self._restart_count - 1, len(self.backoff_ms) - 1)]
        self._next_restart_at_ms = int(now_ms) + delay
        self._state = SupervisorState.BACKOFF


__all__ = ["ProcessSupervisor", "SupervisorState", "SupervisorStatus"]
