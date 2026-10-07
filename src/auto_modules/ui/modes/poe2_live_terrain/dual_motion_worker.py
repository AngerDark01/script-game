"""Bounded latest-frame worker for the PoE2 dual-player experiment.

The worker owns capture, recognition and tracking for one dual-motion session.
It never queues frames: if the UI is busy, the newest completed result replaces
the previous one.  This keeps the control/visual stream close to real time
without changing the single-threaded Qt rendering contract.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Callable

from PySide6.QtCore import QObject, Signal

from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.models import HybridFrame
from auto_modules.features.poe2.live_terrain.experimental.multiplayer_localization import (
    MarkerColorProfile,
    detect_saturated_marker_observation,
    marker_candidates_from_observation,
)
from auto_modules.features.poe2.live_terrain.experimental.multiplayer_localization.dual_motion import (
    RolePredictionHint,
)


@dataclass(frozen=True)
class DualMotionFrameResult:
    state: Any
    captured_at_ms: int
    raw: Any | None
    combined: Any | None
    capture_ms: float
    recognition_ms: float
    tracking_ms: float
    candidate_ms: float = 0.0
    total_worker_ms: float = 0.0
    recognition_wall_mask_ms: float = 0.0
    recognition_marker_observation_ms: float = 0.0
    processed: Any | None = None
    candidates: tuple[Any, ...] = ()


class Poe2DualMotionWorker(QObject):
    """Run one bounded dual capture/recognition loop off the GUI thread."""

    result_available = Signal(int)
    frame_failed = Signal(int, object, int)
    failed = Signal(int, object)
    finished = Signal(int)

    def __init__(
        self,
        *,
        tracker: Any,
        preview_provider: Callable[[Any], Any],
        recognizer: Any,
        monitor_config: Any,
        fps: int,
        generation: int,
        cleanup: Callable[[], None] | None = None,
        max_consecutive_failures: int = 3,
    ) -> None:
        super().__init__()
        if not 1 <= int(fps) <= 60:
            raise ValueError("fps must be between 1 and 60")
        if int(max_consecutive_failures) < 1:
            raise ValueError("max_consecutive_failures must be positive")
        self.tracker = tracker
        self.preview_provider = preview_provider
        self.recognizer = recognizer
        self.monitor_config = monitor_config
        self.fps = int(fps)
        self.generation = int(generation)
        self.max_consecutive_failures = int(max_consecutive_failures)
        # The preview provider owns a thread-local MSS/PIL backend.  Cleanup
        # must run on this same worker thread; letting the thread-local value
        # fall out of scope during Qt shutdown can invoke a native destructor
        # from the wrong thread and corrupt the Windows heap.
        self._cleanup = cleanup
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._latest: DualMotionFrameResult | None = None
        self._prediction_hints: dict[str, RolePredictionHint] = {}
        self._pending_recovery_revision = 0
        self._notification_pending = False
        self._thread: threading.Thread | None = None
        self.completed_frames = 0
        self.dropped_results = 0
        self.failed_frames = 0
        self.consecutive_failures = 0
        self.processing_ema_ms = 0.0
        self.adaptive_interval_ms = 1000.0 / self.fps
        self._started_at: float | None = None

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self._thread is not None:
            raise RuntimeError("dual motion worker can only be started once")
        self._thread = threading.Thread(
            target=self._run,
            name=f"poe2-dual-motion-{self.generation}",
            daemon=True,
        )
        self._started_at = time.perf_counter()
        self._thread.start()

    @property
    def effective_fps(self) -> float:
        """Return completed frame rate since this worker started."""
        if self._started_at is None:
            return 0.0
        elapsed = max(1e-6, time.perf_counter() - self._started_at)
        return float(self.completed_frames) / elapsed

    def stop(self) -> None:
        self._stop_event.set()

    def wait(self, timeout_ms: int = 1000) -> bool:
        """Join the capture thread before its QObject owner is torn down."""
        thread = self._thread
        if thread is None or thread is threading.current_thread():
            return True
        thread.join(max(0.0, int(timeout_ms)) / 1000.0)
        return not thread.is_alive()

    def take_latest(self) -> DualMotionFrameResult | None:
        with self._lock:
            result = self._latest
            self._latest = None
            self._notification_pending = False
            return result

    def take_pending_recovery_revision(self) -> int:
        with self._lock:
            revision = self._pending_recovery_revision
            self._pending_recovery_revision = 0
            return revision

    def set_prediction_hints(
        self, hints: dict[str, tuple[float, float, float, int]], *, generation: int,
    ) -> None:
        if generation != self.generation:
            return
        validated = {
            str(identity): RolePredictionHint(
                (float(value[0]), float(value[1])), float(value[2]), int(value[3]),
            )
            for identity, value in hints.items()
        }
        with self._lock:
            self._prediction_hints = validated

    def _offer(self, result: DualMotionFrameResult) -> None:
        with self._lock:
            if bool(getattr(result.state, "recovery_requested", False)):
                self._pending_recovery_revision = max(
                    self._pending_recovery_revision,
                    int(getattr(result.state, "recovery_revision", 0)),
                )
            if self._latest is not None:
                self.dropped_results += 1
            self._latest = result
            notify = not self._notification_pending
            self._notification_pending = True
        if notify:
            self.result_available.emit(self.generation)

    def _capture_one(self) -> DualMotionFrameResult:
        started = time.perf_counter()
        raw = self.preview_provider(self.monitor_config)
        if raw is None:
            raise RuntimeError("截图后端返回空帧")
        capture_ms = (time.perf_counter() - started) * 1000.0
        captured_at_ms = int(time.time() * 1000)
        recognition_started = time.perf_counter()
        extract = getattr(self.recognizer, "extract_combined_with_processed", None)
        if callable(extract):
            processed, combined = extract(
                raw, player_pos=None, exclude_player=False, exclude_dynamic=False,
            )
        else:
            processed = None
            combined = self.recognizer.extract_combined(
                raw, player_pos=None, exclude_player=False, exclude_dynamic=False,
            )
        recognition_wall_mask_ms = (time.perf_counter() - recognition_started) * 1000.0
        mask = combined[0] if isinstance(combined, (tuple, list)) else combined
        profiles = tuple(
            MarkerColorProfile.from_dict(item)
            for item in getattr(self.monitor_config, "dual_marker_profiles", ())
        )
        marker_started = time.perf_counter()
        observation = detect_saturated_marker_observation(
            raw, captured_at_ms, profiles=profiles or None,
        )
        recognition_marker_observation_ms = (time.perf_counter() - marker_started) * 1000.0
        recognition_ms = (time.perf_counter() - recognition_started) * 1000.0
        shape = getattr(mask, "shape", None)
        if shape is None or len(shape) != 2 or min(int(value) for value in shape) <= 0:
            raise RuntimeError("双人实时识别返回空墙体掩码")
        frame = HybridFrame(
            captured_at_ms,
            captured_at_ms,
            mask,
            (float(shape[1]) / 2.0, float(shape[0]) / 2.0),
        )
        candidate_started = time.perf_counter()
        candidates = marker_candidates_from_observation(observation, max_candidates=6)
        candidate_ms = (time.perf_counter() - candidate_started) * 1000.0
        tracking_started = time.perf_counter()
        with self._lock:
            hints = dict(self._prediction_hints)
        state = (
            self.tracker.tick(frame, candidates, prediction_hints=hints)
            if hints else self.tracker.tick(frame, candidates)
        )
        tracking_ms = (time.perf_counter() - tracking_started) * 1000.0
        total_worker_ms = (time.perf_counter() - started) * 1000.0
        return DualMotionFrameResult(
            state=state,
            captured_at_ms=captured_at_ms,
            raw=raw,
            combined=combined,
            capture_ms=capture_ms,
            recognition_ms=recognition_ms,
            tracking_ms=tracking_ms,
            candidate_ms=candidate_ms,
            total_worker_ms=total_worker_ms,
            recognition_wall_mask_ms=recognition_wall_mask_ms,
            recognition_marker_observation_ms=recognition_marker_observation_ms,
            processed=processed,
            candidates=candidates,
        )

    def _run(self) -> None:
        interval = 1.0 / self.fps
        try:
            while not self._stop_event.is_set():
                started = time.perf_counter()
                try:
                    result = self._capture_one()
                except Exception as exc:
                    if self._stop_event.is_set():
                        break
                    self.failed_frames += 1
                    self.consecutive_failures += 1
                    self.frame_failed.emit(
                        self.generation, exc, self.consecutive_failures,
                    )
                    if self.consecutive_failures >= self.max_consecutive_failures:
                        self.failed.emit(self.generation, exc)
                        break
                    # Do not spin at full speed while a native capture backend
                    # is temporarily unavailable.  The next attempt still
                    # follows the configured cadence and can recover without
                    # tearing down the entire session.
                    self._stop_event.wait(
                        max(0.0, started + interval - time.perf_counter())
                    )
                    continue
                self.completed_frames += 1
                self.consecutive_failures = 0
                processing_ms = (time.perf_counter() - started) * 1000.0
                self.processing_ema_ms = (
                    processing_ms if self.processing_ema_ms <= 0.0
                    else self.processing_ema_ms * 0.8 + processing_ms * 0.2
                )
                # Keep the latest-frame queue responsive under load.  When
                # recognition is slower than the requested cadence, back off
                # capture rather than building stale work and repeatedly
                # dropping results.  The cadence never falls below 10Hz.
                self.adaptive_interval_ms = max(
                    1000.0 / self.fps,
                    min(100.0, self.processing_ema_ms * 1.15),
                )
                self._offer(result)
                self._stop_event.wait(
                    max(0.0, started + self.adaptive_interval_ms / 1000.0 - time.perf_counter())
                )
        except Exception as exc:
            if not self._stop_event.is_set():
                self.failed.emit(self.generation, exc)
        finally:
            if self._cleanup is not None:
                try:
                    self._cleanup()
                except Exception as exc:
                    # Cleanup must never mask the worker's terminal signal.
                    # The page records the worker lifecycle separately.
                    if not self._stop_event.is_set():
                        self.failed.emit(self.generation, exc)
            self.finished.emit(self.generation)


class Poe2DualFirstFrameWorker(QObject):
    """Run the expensive dual first-frame registration off the Qt thread.

    The task must be side-effect free with respect to Qt widgets.  The page
    applies the returned bundle only from ``result_available`` on the GUI
    thread.  This worker is intentionally separate from the continuous motion
    worker because a recovery registration has a bounded, one-shot lifecycle.
    """

    result_available = Signal(int, object)
    failed = Signal(int, object)
    finished = Signal(int)

    def __init__(
        self,
        *,
        task: Callable[[], Any],
        generation: int,
        cleanup: Callable[[], None] | None = None,
    ) -> None:
        super().__init__()
        if not callable(task):
            raise TypeError("task must be callable")
        self.task = task
        self.generation = int(generation)
        self._cleanup = cleanup
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self._thread is not None:
            raise RuntimeError("dual first-frame worker can only be started once")
        self._thread = threading.Thread(
            target=self._run,
            name=f"poe2-dual-first-frame-{self.generation}",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()

    def wait(self, timeout_ms: int = 1000) -> bool:
        thread = self._thread
        if thread is None or thread is threading.current_thread():
            return True
        thread.join(max(0.0, int(timeout_ms)) / 1000.0)
        return not thread.is_alive()

    def _run(self) -> None:
        result_delivered = False
        try:
            if not self._stop_event.is_set():
                result = self.task()
                if not self._stop_event.is_set():
                    # ``result_available`` is the terminal success outcome
                    # for this one-shot worker.  Cleanup is best-effort and
                    # must never emit a second terminal ``failed`` outcome
                    # after the page has already consumed this result.
                    result_delivered = True
                    self.result_available.emit(self.generation, result)
        except Exception as exc:
            if not self._stop_event.is_set():
                self.failed.emit(self.generation, exc)
        finally:
            if self._cleanup is not None:
                try:
                    self._cleanup()
                except Exception as exc:
                    if not self._stop_event.is_set() and not result_delivered:
                        self.failed.emit(self.generation, exc)
            self.finished.emit(self.generation)


__all__ = [
    "DualMotionFrameResult",
    "Poe2DualFirstFrameWorker",
    "Poe2DualMotionWorker",
]
