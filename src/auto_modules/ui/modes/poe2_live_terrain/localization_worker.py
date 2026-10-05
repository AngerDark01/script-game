"""Serial PoE2 localization loop with a bounded, queue-free frame cadence."""

from __future__ import annotations

import threading
import time
from typing import Any, Callable

from PySide6.QtCore import QObject, Signal


class Poe2LocalizationWorker(QObject):
    state_available = Signal(int)
    failed = Signal(int, object)
    finished = Signal(int)

    def __init__(
        self,
        runtime: Any,
        *,
        generation: int,
        fps: int,
        cleanup: Callable[[], None] | None = None,
    ) -> None:
        super().__init__()
        if not 1 <= int(fps) <= 60:
            raise ValueError("fps must be between 1 and 60")
        self.runtime = runtime
        self.generation = int(generation)
        self.fps = int(fps)
        self._cleanup = cleanup
        self._stop_event = threading.Event()
        self._retry_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._state_lock = threading.Lock()
        self._latest_state: Any | None = None
        self._notification_pending = False
        self.skipped_display_states = 0

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self._thread is not None:
            raise RuntimeError("localization worker can only be started once")
        self._thread = threading.Thread(
            target=self._run,
            name=f"poe2-localization-{self.generation}",
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._retry_event.set()

    def wait(self, timeout_ms: int = 3000) -> bool:
        """Join the capture thread before its page/runtime is released."""
        thread = self._thread
        if thread is None or thread is threading.current_thread():
            return True
        thread.join(max(0.0, int(timeout_ms)) / 1000.0)
        return not thread.is_alive()

    def retry_recovery(self) -> None:
        self._retry_event.set()

    def take_latest_state(self) -> Any | None:
        with self._state_lock:
            result = self._latest_state
            self._latest_state = None
            self._notification_pending = False
            return result

    def _offer_state(self, state: Any) -> None:
        with self._state_lock:
            if self._latest_state is not None:
                self.skipped_display_states += 1
            self._latest_state = state
            notify = not self._notification_pending
            self._notification_pending = True
        if notify:
            self.state_available.emit(self.generation)

    def _run(self) -> None:
        started = False
        interval = 1.0 / self.fps
        try:
            if self._stop_event.is_set():
                return
            self.runtime.start()
            started = True
            while not self._stop_event.is_set():
                frame_started = time.perf_counter()
                state = self.runtime.tick()
                if self._stop_event.is_set():
                    break
                self._offer_state(state)
                mode = getattr(getattr(state, "mode", None), "value", getattr(state, "mode", None))
                if mode == "recovery_required":
                    self._retry_event.wait()
                    self._retry_event.clear()
                    if self._stop_event.is_set():
                        break
                    self.runtime.retry_recovery()
                    continue
                self._stop_event.wait(max(0.0, frame_started + interval - time.perf_counter()))
        except Exception as exc:
            if not self._stop_event.is_set():
                self.failed.emit(self.generation, exc)
        finally:
            if started:
                try:
                    self.runtime.stop()
                except Exception as exc:
                    if not self._stop_event.is_set():
                        self.failed.emit(self.generation, exc)
            if self._cleanup is not None:
                try:
                    self._cleanup()
                except Exception as exc:
                    if not self._stop_event.is_set():
                        self.failed.emit(self.generation, exc)
            self.finished.emit(self.generation)


__all__ = ["Poe2LocalizationWorker"]
