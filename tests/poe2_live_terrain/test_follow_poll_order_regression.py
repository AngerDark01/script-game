"""Queued progress must be read before a watchdog replaces its producer."""
from types import SimpleNamespace
from concurrent.futures import Future

from auto_modules.features.poe2.live_terrain.experimental.follow_engine.engine import FollowEnginePort, FollowEngineStart


class Worker:
    def __init__(self):
        self.events = []

    def start(self, **kwargs):
        pass

    def stop(self, **kwargs):
        pass

    def poll_latest(self):
        return self.events.pop(0) if self.events else None

    def send_visual(self, *args, **kwargs):
        pass

    def update_target(self, *args, **kwargs):
        pass


class Output:
    def start(self):
        pass

    def stop(self, **kwargs):
        pass

    def apply(self, snapshot):
        pass


def test_delayed_parent_poll_consumes_queued_progress_before_stall(monkeypatch):
    vision, control = Worker(), Worker()
    engine = FollowEnginePort(vision=vision, control=control, output=Output(), stall_timeout_ms=5000)
    engine.start(FollowEngineStart("map-a", {"p2": 2}))
    engine._last_snapshot = object()
    snapshot = object()
    vision.events.append(SimpleNamespace(kind="observation", observation=object()))
    control.events.append(SimpleNamespace(kind="snapshot", snapshot=snapshot))
    try:
        # RelayLoop is the sole worker-queue consumer.  UI poll must only read
        # the latest relay-owned snapshot, so wait for that publication rather
        # than asserting that this call drains the fake queue synchronously.
        import time
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline and engine.snapshot() is not snapshot:
            engine.poll()
            time.sleep(0.01)
        assert engine.snapshot() is snapshot
        assert engine.poll() is snapshot
        diagnostics = engine.diagnostics()
        assert diagnostics["last_error"] == ""
        assert diagnostics["worker_state"] == {"vision": "running", "control": "running"}
        assert diagnostics["last_parent_event"]["control"] is not None
    finally:
        engine.stop()


def test_completed_rebuild_is_collected_before_capturing_poll_handles():
    old_vision, old_control = Worker(), Worker()
    new_vision, new_control = Worker(), Worker()
    engine = FollowEnginePort(vision=old_vision, control=old_control, output=Output())
    engine.start(FollowEngineStart("map-a", {"p2": 2}))
    snapshot = object()
    new_vision.events.append(SimpleNamespace(kind="observation", observation=object()))
    new_control.events.append(SimpleNamespace(kind="snapshot", snapshot=snapshot))

    def collect():
        engine.vision, engine.control = new_vision, new_control

    engine._collect_rebuild_result = collect
    try:
        assert engine.poll() is snapshot
    finally:
        engine.stop()


def test_pending_rebuild_does_not_poll_retired_queues():
    vision, control = Worker(), Worker()
    engine = FollowEnginePort(vision=vision, control=control, output=Output())
    engine.start(FollowEngineStart("map-a", {"p2": 2}))
    old_snapshot = object()
    engine._last_snapshot = old_snapshot
    engine._rebuild_future = Future()
    engine._rebuild_in_progress = True

    def disposed_queue():
        raise AssertionError("retired queues must not be polled")

    vision.poll_latest = control.poll_latest = disposed_queue
    try:
        assert engine.poll() is old_snapshot
        assert engine.active
    finally:
        engine._rebuild_future = None
        engine._rebuild_in_progress = False
        engine.stop()


def test_original_worker_trace_survives_stall_summary(monkeypatch, caplog):
    now = [100.0]
    monkeypatch.setattr("auto_modules.features.poe2.live_terrain.experimental.follow_engine.engine.time.monotonic", lambda: now[0])
    vision, control = Worker(), Worker()
    engine = FollowEnginePort(vision=vision, control=control, output=Output())
    engine.start(FollowEngineStart("map-a", {"p2": 2}))
    control.events.append(SimpleNamespace(kind="error", error="ValueError: broken input", traceback_text="original worker traceback"))
    try:
        engine.poll()
        now[0] += 11.0
        engine.poll()
        diagnostics = engine.diagnostics()
        assert diagnostics["last_error"].startswith("worker_stall:")
        assert diagnostics["first_fault"]["error"] == "ValueError: broken input"
        assert "original worker traceback" in caplog.text
    finally:
        engine.stop()


def test_control_first_result_does_not_shorten_vision_startup_window(monkeypatch):
    now = [100.0]
    monkeypatch.setattr("auto_modules.features.poe2.live_terrain.experimental.follow_engine.engine.time.monotonic", lambda: now[0])
    vision, control = Worker(), Worker()
    engine = FollowEnginePort(vision=vision, control=control, output=Output())
    engine.start(FollowEngineStart("map-a", {"p2": 2}))
    control.events.append(SimpleNamespace(kind="snapshot", snapshot=object()))
    try:
        engine.poll()
        now[0] += 3.0
        control.events.append(SimpleNamespace(kind="snapshot", snapshot=object()))
        engine.poll()
        assert engine.diagnostics()["worker_state"]["vision"] == "running"
        assert engine.diagnostics()["last_error"] == ""
    finally:
        engine.stop()
