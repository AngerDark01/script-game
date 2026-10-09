"""Non-Qt relay actor for FollowEnginePort.

The relay owns the worker polling clock.  UI callers only read the latest
snapshot through ``FollowEnginePort.poll``; a paused Qt timer therefore cannot
pause Vision→Control→Output→receipt transport.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from collections import deque
from .timing import TimingWindow


class RelayLoop:
    def __init__(self, step: Callable[[], object], *, interval_ms: int = 10,
                 on_error: Callable[[BaseException], None] | None = None) -> None:
        self._step = step
        self._on_error = on_error
        self._interval = max(0.001, int(interval_ms) / 1000.0)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._epoch = 0
        self._last_started = 0.0
        self._last_duration_ms = 0.0
        self._last_entry_gap_ms = 0.0
        self._durations = TimingWindow(256)

    @property
    def epoch(self) -> int:
        return self._epoch

    @property
    def alive(self) -> bool:
        thread = self._thread
        return bool(thread is not None and thread.is_alive())

    def diagnostics(self) -> dict[str, object]:
        timing = self._durations.as_dict("step_")
        return {
            "alive": self.alive,
            "epoch": self._epoch,
            "relay_duration_ms": self._last_duration_ms,
            "step_duration_ms": self._last_duration_ms,
            "entry_gap_ms": self._last_entry_gap_ms,
            **timing,
            "step_p50_ms": timing["step_p50_ms"],
            "step_p95_ms": timing["step_p95_ms"],
            "step_max_ms": timing["step_max_ms"],
            "sample_count": timing["step_sample_count"],
        }

    def start(self, *, epoch: int) -> None:
        if self.alive:
            raise RuntimeError("relay loop is already running")
        self._epoch = int(epoch)
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name=f"poe2-follow-relay-{epoch}", daemon=True)
        self._thread.start()

    def stop(self, *, timeout: float = 2.0) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=max(0.0, float(timeout)))
        self._thread = None

    def _run(self) -> None:
        while not self._stop.is_set():
            started = time.perf_counter()
            started_monotonic = time.monotonic()
            if self._last_started:
                self._last_entry_gap_ms = (started_monotonic - self._last_started) * 1000.0
            self._last_started = started_monotonic
            try:
                self._step()
            except Exception as exc:
                # The owner records the fault and decides whether to rebuild;
                # an actor exception must not silently kill the relay thread.
                if self._on_error is not None:
                    self._on_error(exc)
            self._last_duration_ms = (time.perf_counter() - started) * 1000.0
            self._durations.add(self._last_duration_ms)
            remaining = self._interval - (time.perf_counter() - started)
            self._stop.wait(max(0.001, remaining))


__all__ = ["RelayLoop"]
