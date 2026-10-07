from __future__ import annotations

from types import SimpleNamespace

import pytest

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

    def start(self, *, generation, map_instance):
        self.started.append((generation, map_instance))

    def poll_latest(self):
        return self.events.pop(0) if self.events else None

    def stop(self, *, timeout=2.0):
        self.stopped += 1


class FakeControl:
    def __init__(self):
        self.started = []
        self.stopped = 0
        self.visuals = []
        self.targets = []
        self.events = []

    def start(self, *, generation, map_instance):
        self.started.append((generation, map_instance))

    def send_visual(self, observation):
        self.visuals.append(observation)

    def update_target(self, role_id, target):
        self.targets.append((role_id, target))

    def poll_latest(self):
        return self.events.pop(0) if self.events else None

    def stop(self, *, timeout=2.0):
        self.stopped += 1


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
    assert control.visuals == [observation]
    assert output.applied == [snapshot]

    adapter.update_target("p2", (10.0, 20.0))
    assert control.targets == [("p2", (10.0, 20.0))]
    adapter.stop()
    assert engine.active is False
    assert vision.stopped == control.stopped == 1
    assert output.stopped == [True]


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
