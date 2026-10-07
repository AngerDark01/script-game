from __future__ import annotations

import threading
from types import SimpleNamespace

import numpy as np
from PySide6.QtCore import Qt

from auto_modules.ui.modes.poe2_live_terrain.dual_motion_worker import (
    Poe2DualFirstFrameWorker,
    Poe2DualMotionWorker,
)


class _Recognizer:
    def extract_combined(self, _raw, **_kwargs):
        return np.zeros((12, 12), dtype=np.uint8)


class _Tracker:
    def tick(self, frame, candidates):
        return SimpleNamespace(
            status="tracking",
            reason="visual",
            players={},
            wall_quality=1.0,
            correction_attempted=False,
            recovery_requested=False,
            recovery_revision=0,
            diagnostics={"frame_id": frame.frame_id, "candidate_count": len(candidates)},
        )


def test_dual_motion_worker_replaces_stale_results_without_queueing():
    worker = Poe2DualMotionWorker(
        tracker=_Tracker(),
        preview_provider=lambda _config: np.zeros((12, 12, 3), dtype=np.uint8),
        recognizer=_Recognizer(),
        monitor_config=SimpleNamespace(dual_marker_profiles=()),
        fps=30,
        generation=7,
    )
    first = worker._capture_one()
    second = worker._capture_one()
    assert first.candidate_ms >= 0.0
    assert first.recognition_wall_mask_ms >= 0.0
    assert first.recognition_marker_observation_ms >= 0.0
    assert first.total_worker_ms >= first.capture_ms
    assert second.total_worker_ms >= second.capture_ms
    worker._offer(first)
    worker._offer(second)

    latest = worker.take_latest()
    assert latest is second
    assert worker.dropped_results == 1
    assert worker.take_latest() is None


def test_dual_motion_worker_keeps_preprocessed_preview_result():
    processed = object()

    class RecognizerWithProcessed(_Recognizer):
        def extract_combined_with_processed(self, _raw, **_kwargs):
            return processed, np.zeros((12, 12), dtype=np.uint8)

    worker = Poe2DualMotionWorker(
        tracker=_Tracker(),
        preview_provider=lambda _config: np.zeros((12, 12, 3), dtype=np.uint8),
        recognizer=RecognizerWithProcessed(),
        monitor_config=SimpleNamespace(dual_marker_profiles=()),
        fps=30,
        generation=7,
    )

    result = worker._capture_one()

    assert result.processed is processed


def test_prediction_mailbox_is_generation_scoped_and_role_isolated():
    class HintTracker(_Tracker):
        def tick(self, frame, candidates, *, prediction_hints=None):
            self.hints = prediction_hints
            return super().tick(frame, candidates)

    tracker = HintTracker()
    worker = Poe2DualMotionWorker(
        tracker=tracker,
        preview_provider=lambda _config: np.zeros((12, 12, 3), dtype=np.uint8),
        recognizer=_Recognizer(), monitor_config=SimpleNamespace(dual_marker_profiles=()),
        fps=30, generation=7,
    )
    worker.set_prediction_hints({"p2": (20.0, 30.0, 2.0, 100)}, generation=6)
    worker._capture_one()
    assert tracker.hints is None
    worker.set_prediction_hints({"p2": (20.0, 30.0, 2.0, 100)}, generation=7)
    worker._capture_one()
    assert set(tracker.hints) == {"p2"}
    worker.set_prediction_hints({}, generation=7)
    worker._capture_one()
    assert tracker.hints is None


def test_recovery_revision_survives_overwritten_frame_until_acknowledged():
    worker = Poe2DualMotionWorker(
        tracker=_Tracker(),
        preview_provider=lambda _config: np.zeros((12, 12, 3), dtype=np.uint8),
        recognizer=_Recognizer(),
        monitor_config=SimpleNamespace(dual_marker_profiles=()),
        fps=30,
        generation=11,
    )
    edge = worker._capture_one()
    edge.state.recovery_requested = True
    edge.state.recovery_revision = 3
    later = worker._capture_one()
    later.state.recovery_revision = 3
    worker._offer(edge)
    worker._offer(later)

    assert worker.take_latest() is later
    assert worker.take_pending_recovery_revision() == 3
    assert worker.take_pending_recovery_revision() == 0


def test_dual_motion_worker_runs_capture_cleanup_on_worker_thread():
    calls = []
    cleanup_threads = []
    worker_ref = {}

    def preview(_config):
        calls.append(threading.get_ident())
        if len(calls) >= 2:
            worker_ref["worker"].stop()
        return np.zeros((12, 12, 3), dtype=np.uint8)

    def cleanup():
        cleanup_threads.append(threading.get_ident())

    worker = Poe2DualMotionWorker(
        tracker=_Tracker(),
        preview_provider=preview,
        recognizer=_Recognizer(),
        monitor_config=SimpleNamespace(dual_marker_profiles=()),
        fps=60,
        generation=8,
        cleanup=cleanup,
    )
    worker_ref["worker"] = worker
    worker.start()

    assert worker.wait(2000)
    assert len(calls) >= 2
    assert cleanup_threads == [calls[0]]


def test_dual_motion_worker_skips_transient_frame_failure_and_continues():
    calls = []
    worker_ref = {}

    def preview(_config):
        calls.append(True)
        if len(calls) == 1:
            raise RuntimeError("temporary capture error")
        worker_ref["worker"].stop()
        return np.zeros((12, 12, 3), dtype=np.uint8)

    worker = Poe2DualMotionWorker(
        tracker=_Tracker(),
        preview_provider=preview,
        recognizer=_Recognizer(),
        monitor_config=SimpleNamespace(dual_marker_profiles=()),
        fps=60,
        generation=9,
    )
    worker_ref["worker"] = worker
    worker.start()

    assert worker.wait(2000)
    assert worker.completed_frames == 1
    assert worker.failed_frames == 1


def test_dual_motion_worker_terminates_after_consecutive_failure_threshold():
    worker = Poe2DualMotionWorker(
        tracker=_Tracker(),
        preview_provider=lambda _config: (_ for _ in ()).throw(RuntimeError("capture down")),
        recognizer=_Recognizer(),
        monitor_config=SimpleNamespace(dual_marker_profiles=()),
        fps=60,
        generation=10,
        max_consecutive_failures=2,
    )
    worker.start()

    assert worker.wait(2000)
    assert worker.completed_frames == 0
    assert worker.failed_frames == 2


def test_dual_first_frame_worker_runs_registration_off_calling_thread():
    caller_thread = threading.get_ident()
    task_thread = []
    task_finished = threading.Event()

    def task():
        task_thread.append(threading.get_ident())
        task_finished.set()
        return SimpleNamespace(status="accepted")

    worker = Poe2DualFirstFrameWorker(task=task, generation=3)
    worker.start()

    assert worker.wait(2000)
    assert task_finished.wait(1.0)
    assert task_thread and task_thread[0] != caller_thread


def test_dual_first_frame_worker_stop_suppresses_late_result():
    started = threading.Event()
    release = threading.Event()
    results = []

    def task():
        started.set()
        release.wait(1.0)
        return SimpleNamespace(status="accepted")

    worker = Poe2DualFirstFrameWorker(task=task, generation=4)
    worker.result_available.connect(lambda *_args: results.append(True))
    worker.start()
    assert started.wait(1.0)
    worker.stop()
    release.set()
    assert worker.wait(2000)
    assert results == []


def test_dual_first_frame_cleanup_failure_does_not_mask_delivered_result():
    results = []
    failures = []

    def cleanup():
        raise RuntimeError("thread-local cleanup failed")

    worker = Poe2DualFirstFrameWorker(
        task=lambda: SimpleNamespace(status="accepted"),
        generation=5,
        cleanup=cleanup,
    )
    worker.result_available.connect(
        lambda *_args: results.append(True), Qt.ConnectionType.DirectConnection,
    )
    worker.failed.connect(
        lambda *_args: failures.append(True), Qt.ConnectionType.DirectConnection,
    )
    worker.start()

    assert worker.wait(2000)
    assert results == [True]
    assert failures == []
