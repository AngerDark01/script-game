from __future__ import annotations

from types import SimpleNamespace
import threading
import time

import pytest

from auto_modules.features.poe2.live_terrain.experimental.follow_engine.contracts import (
    FusionSnapshot,
    ObservationSource,
    RoleFusedState,
    RoleVisualObservation,
    VisualObservation,
)

from auto_modules.features.poe2.live_terrain.experimental.follow_engine.engine import (
    FollowEnginePort,
    FollowEngineStart,
)
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.ui_adapter import FollowEngineUiAdapter


class FakeVision:
    def __init__(self):
        self.started = []
        self.stopped = 0
        self.events = []
        self.disposed = 0

    def start(self, *, generation, map_instance):
        self.started.append((generation, map_instance))

    def poll_latest(self):
        return self.events.pop(0) if self.events else None

    def stop(self, *, timeout=2.0):
        self.stopped += 1

    def dispose(self):
        self.disposed += 1


class FakeControl:
    def __init__(self):
        self.started = []
        self.stopped = 0
        self.visuals = []
        self.targets = []
        self.events = []
        self.disposed = 0

    def start(self, *, generation, map_instance):
        self.started.append((generation, map_instance))

    def send_visual(self, observation, *, frame=None):
        self.visuals.append((observation, frame))

    def update_target(self, role_id, target):
        self.targets.append((role_id, target))

    def poll_latest(self):
        return self.events.pop(0) if self.events else None

    def stop(self, *, timeout=2.0):
        self.stopped += 1

    def dispose(self):
        self.disposed += 1


class FakeOutput:
    def __init__(self):
        self.started = 0
        self.applied = []
        self.stopped = []

    def start(self):
        self.started += 1

    def apply(self, snapshot):
        self.applied.append(snapshot)

    def stop(self, *, force=True):
        self.stopped.append(force)


def test_port_drains_latest_events_and_only_ui_adapter_owns_targets():
    vision, control, output = FakeVision(), FakeControl(), FakeOutput()
    engine = FollowEnginePort(vision=vision, control=control, output=output)
    adapter = FollowEngineUiAdapter(engine)
    config = FollowEngineStart("map-a", {"p2": 2})
    state = adapter.start(config)
    assert state.active is True
    assert vision.started == [(1, "map-a")]
    assert control.started == [(1, "map-a")]

    observation = object()
    snapshot = object()
    vision.events.append(SimpleNamespace(kind="observation", observation=observation))
    control.events.append(SimpleNamespace(kind="snapshot", snapshot=snapshot))
    assert adapter.poll().snapshot is snapshot
    assert control.visuals == [(observation, None)]
    assert output.applied == [snapshot]
    adapter.update_target("p2", (10.0, 20.0))
    assert control.targets == [("p2", (10.0, 20.0))]
    adapter.stop()
    assert engine.active is False
    assert vision.stopped == control.stopped == 1
    assert output.stopped == [True]


def test_port_forwards_latest_frame_when_vision_provides_one():
    vision, control, output = FakeVision(), FakeControl(), FakeOutput()
    engine = FollowEnginePort(vision=vision, control=control, output=output)
    engine.start(FollowEngineStart("map-a", {"p2": 2}))
    try:
        observation = object()
        frame = object()
        vision.events.append(SimpleNamespace(kind="observation", observation=observation, frame=frame))
        engine.poll()
        assert control.visuals == [(observation, frame)]
    finally:
        engine.stop()


def test_port_retains_latest_generation_valid_visual_observation_for_handover():
    vision, control, output = FakeVision(), FakeControl(), FakeOutput()
    engine = FollowEnginePort(vision=vision, control=control, output=output)
    engine.start(FollowEngineStart("map-a", {"p2": 2}))
    observation = VisualObservation(
        generation=1,
        sequence=3,
        captured_at_ms=99,
        map_instance="map-a",
        roles={},
        source=ObservationSource.NONE,
    )
    vision.events.append(SimpleNamespace(kind="observation", observation=observation))
    try:
        engine.poll()
        assert engine.latest_visual_observation is observation
    finally:
        engine.stop()
    assert engine.latest_visual_observation is None


def test_live_target_observation_reaches_control_before_snapshot_poll():
    vision, control, output = FakeVision(), FakeControl(), FakeOutput()
    engine = FollowEnginePort(vision=vision, control=control, output=output)
    engine.start(FollowEngineStart("map-a", {"p2": 2}))
    engine.configure_live_target_policy(
        source_role="p1", target_roles=("p2",), initial_position=(0.0, 0.0)
    )
    observation = VisualObservation(
        generation=1,
        sequence=1,
        captured_at_ms=33,
        map_instance="map-a",
        roles={
            "p1": RoleVisualObservation(
                "p1", (12.0, 14.0), confidence=1.0,
                uncertainty_native=1.0, visible=True, last_visual_at_ms=33,
            ),
        },
        source=ObservationSource.VISUAL,
    )
    vision.events.append(SimpleNamespace(kind="observation", observation=observation))
    control.events.append(SimpleNamespace(kind="snapshot", snapshot=object()))
    try:
        engine.poll()
        assert control.targets[-1] == ("p2", (12.0, 14.0))
        assert control.targets[0] == ("p2", (0.0, 0.0))
    finally:
        engine.stop()


def test_live_target_accepts_associated_low_confidence_marker():
    """A valid geometry assignment must still refresh a moving leader target."""

    vision, control, output = FakeVision(), FakeControl(), FakeOutput()
    engine = FollowEnginePort(
        vision=vision, control=control, output=output,
        live_target_min_confidence=0.2,
    )
    engine.start(FollowEngineStart("map-a", {"p2": 2}))
    engine.configure_live_target_policy(source_role="p1", target_roles=("p2",))
    observation = VisualObservation(
        generation=1,
        sequence=1,
        captured_at_ms=33,
        map_instance="map-a",
        roles={
            "p1": RoleVisualObservation(
                "p1", (90.0, 80.0), confidence=0.25,
                uncertainty_native=3.0, visible=True, last_visual_at_ms=33,
            ),
        },
        source=ObservationSource.VISUAL,
    )
    vision.events.append(SimpleNamespace(kind="observation", observation=observation))
    control.events.append(SimpleNamespace(kind="snapshot", snapshot=object()))
    try:
        engine.poll()
        assert control.targets[-1] == ("p2", (90.0, 80.0))
    finally:
        engine.stop()


def test_control_owned_live_target_policy_does_not_relay_stale_parent_target():
    vision, control, output = FakeVision(), FakeControl(), FakeOutput()
    engine = FollowEnginePort(
        vision=vision, control=control, output=output,
        control_owns_live_targets=True,
    )
    engine.start(FollowEngineStart("map-a", {"p2": 2}))
    engine.configure_live_target_policy(source_role="p1", target_roles=("p2",), initial_position=(0.0, 0.0))
    observation = VisualObservation(
        generation=1,
        sequence=1,
        captured_at_ms=33,
        map_instance="map-a",
        roles={"p1": RoleVisualObservation("p1", (90.0, 80.0), confidence=1.0, visible=True)},
        source=ObservationSource.VISUAL,
    )
    vision.events.append(SimpleNamespace(kind="observation", observation=observation))
    try:
        engine.poll()
        assert control.targets == []
    finally:
        engine.stop()


def test_closed_vision_queue_is_classified_without_poll_exception():
    """A disposed worker queue must enter recovery diagnostics, not flood Qt."""
    class ClosedVision(FakeVision):
        def poll_latest(self):
            raise ValueError("Queue <multiprocessing.queues.Queue> is closed")

    vision, control, output = ClosedVision(), FakeControl(), FakeOutput()
    engine = FollowEnginePort(vision=vision, control=control, output=output)
    engine.start(FollowEngineStart("map-a", {"p2": 2}))
    try:
        assert engine.poll() is None
        diagnostics = engine.diagnostics()
        assert diagnostics["worker_state"]["vision"] == "stalled"
        assert "vision_queue_closed" in diagnostics["last_error"]
    finally:
        engine.stop()


def test_worker_error_is_visible_without_reapplying_stale_snapshot():
    vision, control, output = FakeVision(), FakeControl(), FakeOutput()
    engine = FollowEnginePort(vision=vision, control=control, output=output)
    engine.start(FollowEngineStart("map-a", {"p2": 2}))
    try:
        control.events.append(SimpleNamespace(kind="error", error="control crashed"))
        assert engine.poll() is None
        diagnostics = engine.diagnostics()
        assert diagnostics["worker_state"] == {"vision": "running", "control": "error"}
        assert diagnostics["last_error"] == "control crashed"
        assert output.applied == []
    finally:
        engine.stop()


def test_port_start_failure_rolls_back_started_components():
    vision, control, output = FakeVision(), FakeControl(), FakeOutput()

    def failing_start():
        raise RuntimeError("output unavailable")

    output.start = failing_start
    engine = FollowEnginePort(vision=vision, control=control, output=output)
    with pytest.raises(RuntimeError, match="output unavailable"):
        engine.start(FollowEngineStart("map-a", {"p2": 2}))
    assert engine.active is False
    assert vision.stopped == control.stopped == 1
    assert output.stopped == [True]


def test_partial_start_and_cleanup_error_preserve_original_failure_and_allow_retry():
    vision, control, output = FakeVision(), FakeControl(), FakeOutput()
    engine = FollowEnginePort(vision=vision, control=control, output=output)
    original_start, original_stop = vision.start, vision.stop

    def partial_start(**kwargs):
        original_start(**kwargs)
        raise RuntimeError("vision preparation failed")

    def cleanup_error(**kwargs):
        original_stop(**kwargs)
        raise RuntimeError("vision cleanup failed")

    vision.start, vision.stop = partial_start, cleanup_error
    with pytest.raises(RuntimeError, match="vision preparation failed"):
        engine.start(FollowEngineStart("map-a", {"p2": 2}))
    assert vision.stopped == control.stopped == 1
    assert output.stopped == [True]
    assert engine.active is False and engine.token is None
    assert engine.diagnostics()["worker_state"] == {"vision": "stopped", "control": "stopped"}
    vision.start, vision.stop = original_start, original_stop
    engine.start(FollowEngineStart("map-a", {"p2": 2}))
    engine.stop()


def test_port_requires_explicit_role_for_multi_role_target():
    engine = FollowEnginePort(vision=FakeVision(), control=FakeControl(), output=FakeOutput())
    engine.start(FollowEngineStart("map-a", {"p1": 1, "p2": 2}))
    try:
        with pytest.raises(ValueError, match="role_id"):
            engine.update_target((1.0, 2.0))
    finally:
        engine.stop()


def test_port_clears_active_state_even_when_output_stop_reports_error():
    vision, control, output = FakeVision(), FakeControl(), FakeOutput()
    engine = FollowEnginePort(vision=vision, control=control, output=output)
    engine.start(FollowEngineStart("map-a", {"p2": 2}))

    def failing_stop(*, force=True):
        raise RuntimeError("output stop failed")

    output.stop = failing_stop
    with pytest.raises(RuntimeError, match="output stop failed"):
        engine.stop()
    assert engine.active is False
    assert engine.token is None


def test_worker_stall_rebuild_is_async_and_budgeted():
    created = []

    def factory():
        vision, control = FakeVision(), FakeControl()
        created.append((vision, control))
        return vision, control

    engine = FollowEnginePort(
        vision=FakeVision(),
        control=FakeControl(),
        output=FakeOutput(),
        rebuild_factory=factory,
        startup_timeout_ms=100,
        stall_timeout_ms=100,
        rebuild_backoff_ms=20,
        max_rebuild_attempts=2,
    )
    engine.start(FollowEngineStart("map-a", {"p2": 2}))
    try:
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline and engine.diagnostics()["rebuild_count"] < 1:
            time.sleep(0.12)
            started = time.monotonic()
            engine.poll()
            # poll must not wait for a worker stop/start operation.
            assert time.monotonic() - started < 0.1
        assert engine.diagnostics()["rebuild_count"] >= 1
        # A silent replacement is allowed a bounded second attempt, but not
        # an unbounded rebuild loop on every UI poll.
        for _ in range(5):
            time.sleep(0.12)
            engine.poll()
        assert engine.diagnostics()["rebuild_attempts"] == 2
        assert "budget_exhausted" in engine.diagnostics()["last_error"]
    finally:
        engine.stop()


def test_stale_rebuild_future_isolated_from_stop_restart_session():
    """A late rebuild must only dispose its detached bundle after restart."""
    from auto_modules.features.poe2.live_terrain.experimental.follow_engine.engine import RebuildBundle

    factory_started = threading.Event()
    release_factory = threading.Event()
    committed = []
    disposed = []

    def factory():
        factory_started.set()
        assert release_factory.wait(5.0)
        replacement = (FakeVision(), FakeControl())
        return RebuildBundle(
            *replacement,
            commit=lambda: committed.append(replacement),
            dispose=lambda: disposed.append(replacement),
        )

    vision, control, output = FakeVision(), FakeControl(), FakeOutput()
    engine = FollowEnginePort(
        vision=vision,
        control=control,
        output=output,
        rebuild_factory=factory,
        startup_timeout_ms=100,
        stall_timeout_ms=100,
        rebuild_backoff_ms=0,
    )
    config = FollowEngineStart("map-a", {"p2": 2})
    engine.start(config)
    try:
        # Force the watchdog to submit a rebuild without sleeping in the test.
        engine._last_progress_monotonic = {"vision": 0.0, "control": 0.0}
        engine._check_worker_stall()
        assert factory_started.wait(1.0)

        # A new session starts while the old future is still inside its
        # factory. Its detached bundle must not be committed into this
        # session or close resources owned by it.
        stop_started = time.monotonic()
        engine.stop()
        assert time.monotonic() - stop_started < 1.0
        release_factory.set()
        engine.start(config)
        engine._last_progress_monotonic = {
            "vision": time.monotonic(),
            "control": time.monotonic(),
        }
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline and not disposed:
            engine.poll()
            time.sleep(0.01)

        assert committed == []
        assert len(disposed) == 1
        assert engine.active is True
        assert engine.vision is vision
        assert engine.control is control
    finally:
        release_factory.set()
        engine.stop()


def test_rebuild_bundle_commit_is_atomic_and_retire_old_handles():
    """A current replacement commits once and retires old handles safely."""
    from auto_modules.features.poe2.live_terrain.experimental.follow_engine.engine import RebuildBundle

    committed = []
    disposed = []
    replacement = (FakeVision(), FakeControl())

    def factory():
        return RebuildBundle(
            *replacement,
            commit=lambda: committed.append(True),
            dispose=lambda: disposed.append(True),
        )

    vision, control, output = FakeVision(), FakeControl(), FakeOutput()
    engine = FollowEnginePort(
        vision=vision,
        control=control,
        output=output,
        rebuild_factory=factory,
        startup_timeout_ms=100,
        stall_timeout_ms=100,
        rebuild_backoff_ms=0,
    )
    engine.start(FollowEngineStart("map-a", {"p2": 2}))
    try:
        engine._last_progress_monotonic = {"vision": 0.0, "control": 0.0}
        engine._check_worker_stall()
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline and engine.diagnostics()["rebuild_count"] < 1:
            engine.poll()
            time.sleep(0.01)
        assert engine.diagnostics()["rebuild_count"] == 1
        assert committed == [True]
        assert disposed == []
        assert engine.vision is replacement[0]
        assert engine.control is replacement[1]
        assert vision.stopped == control.stopped == 1
    finally:
        engine.stop()


def test_control_owned_live_target_is_replayed_from_last_snapshot_after_rebuild():
    from auto_modules.features.poe2.live_terrain.experimental.follow_engine.engine import RebuildBundle

    replacement = (FakeVision(), FakeControl())
    engine = FollowEnginePort(
        vision=FakeVision(),
        control=FakeControl(),
        output=FakeOutput(),
        control_owns_live_targets=True,
        rebuild_factory=lambda: RebuildBundle(*replacement),
    )
    config = FollowEngineStart("map-a", {"p2": 2})
    engine.start(config)
    try:
        engine.configure_live_target_policy(source_role="p1", target_roles=("p2",), initial_position=(1.0, 1.0))
        engine._last_snapshot = FusionSnapshot(
            generation=1,
            created_at_ms=100,
            roles={
                "p1": RoleFusedState("p1", (50.0, 60.0), (0.0, 0.0), 1.0, "visual_fused", 0.0),
            },
            recovery_state="tracking",
            recovery_reason="visual_match",
        )
        engine._rebuild_components(
            "test_handover",
            engine._session_epoch,
            engine.token,
            threading.Event(),
        )
        assert replacement[1].targets == [("p2", (50.0, 60.0))]
    finally:
        engine.stop()


def test_async_output_actor_start_failure_keeps_session_and_retries_output():
    """A transient lease failure must not terminate continuous follow."""
    from auto_modules.features.poe2.live_terrain.experimental.follow_engine.control.async_output import (
        AsyncSnapshotOutput,
    )

    applied = []

    class FailingAdapter:
        attempts = 0

        def start(self):
            self.attempts += 1
            if self.attempts == 1:
                raise RuntimeError("host lease unavailable")

        def apply(self, snapshot):
            applied.append(snapshot)

        def neutralize(self):
            return None

        def diagnostics(self):
            return {"started": True}

        def poll_receipts(self):
            return ()

        def stop(self):
            return None

        def cancel_pending_io(self):
            return None

    vision, control = FakeVision(), FakeControl()
    output = AsyncSnapshotOutput(FailingAdapter())
    engine = FollowEnginePort(vision=vision, control=control, output=output)
    engine.start(FollowEngineStart("map-a", {"p2": 2}))
    try:
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline:
            engine.poll()
            if output.adapter.attempts >= 2:
                break
            time.sleep(0.05)
        assert engine.active is True
        assert output.adapter.attempts >= 2
        diagnostics = engine.diagnostics()
        assert diagnostics["output_state"] in {"restarting", "running"}

        # A control event arriving after the first actor failure remains part
        # of the same follow session and can be applied after rearm.
        control.events.append(SimpleNamespace(kind="snapshot", snapshot=object()))
        engine.poll()
        assert engine.active is True
    finally:
        engine.stop()


def test_stale_rebuild_disposes_replacement_after_stop_and_restart():
    factory_started = threading.Event()
    release_factory = threading.Event()
    created = []

    def factory():
        factory_started.set()
        release_factory.wait(timeout=2.0)
        pair = (FakeVision(), FakeControl())
        created.append(pair)
        return pair

    engine = FollowEnginePort(
        vision=FakeVision(), control=FakeControl(), output=FakeOutput(),
        rebuild_factory=factory, startup_timeout_ms=50, stall_timeout_ms=50,
        rebuild_backoff_ms=0, max_rebuild_attempts=1,
    )
    engine.start(FollowEngineStart("map-a", {"p2": 2}))
    time.sleep(0.12)
    engine.poll()
    assert factory_started.wait(timeout=1.0)
    engine.stop()
    engine.start(FollowEngineStart("map-b", {"p2": 2}))
    release_factory.set()
    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline and not created:
        time.sleep(0.01)
        engine.poll()
    try:
        assert created
        replacement_vision, replacement_control = created[0]
        assert replacement_vision.disposed == 1
        assert replacement_control.disposed == 1
        assert engine.vision is not replacement_vision
        assert engine.token is not None and engine.token.map_instance == "map-b"
    finally:
        engine.stop()
