from __future__ import annotations

import multiprocessing as mp
import time

from auto_modules.features.poe2.live_terrain.experimental.follow_engine.contracts import (
    ObservationSource,
    RoleVisualObservation,
    VisualObservation,
)
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.control.follow_control_process import FollowControlProcessHandle
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.control.follow_control_process import FollowControlRuntime


def _runtime_factory(token, roles):
    return FollowControlRuntime(token, roles)


def _broken_runtime_factory(token, roles):
    raise RuntimeError("runtime composition failed")


def _observation() -> VisualObservation:
    return VisualObservation(
        generation=1,
        sequence=1,
        captured_at_ms=1,
        map_instance="map-a",
        roles={"p2": RoleVisualObservation("p2", (10, 0), confidence=1, uncertainty_native=1, visible=True, last_visual_at_ms=1)},
        source=ObservationSource.VISUAL,
    )


def test_spawned_control_process_consumes_visual_and_publishes_snapshot():
    handle = FollowControlProcessHandle({"p2": 2}, interval_ms=10, context=mp.get_context("spawn"))
    handle.start(generation=1, map_instance="map-a")
    try:
        handle.send_visual(_observation())
        handle.update_target("p2", (100, 0))
        deadline = time.monotonic() + 5.0
        event = None
        while time.monotonic() < deadline and event is None:
            candidate = handle.poll_latest()
            if candidate is not None and candidate.kind == "snapshot":
                event = candidate
            time.sleep(0.01)
        assert event is not None
        assert event.snapshot is not None
        assert event.snapshot.session_active is True
        assert event.snapshot.output_intents[0].controller == 2
    finally:
        handle.stop()


def test_spawned_control_process_accepts_spawn_safe_runtime_factory():
    handle = FollowControlProcessHandle(
        {"p2": 2}, interval_ms=10, context=mp.get_context("spawn"),
        runtime_factory=_runtime_factory,
    )
    handle.start(generation=1, map_instance="map-a")
    try:
        handle.send_visual(_observation())
        deadline = time.monotonic() + 5.0
        event = None
        while time.monotonic() < deadline and event is None:
            candidate = handle.poll_latest()
            if candidate is not None and candidate.kind == "snapshot":
                event = candidate
            time.sleep(0.01)
        assert event is not None
        assert event.snapshot is not None
        assert event.snapshot.session_active is True
    finally:
        handle.stop()


def test_runtime_factory_failure_is_published_as_structured_error():
    handle = FollowControlProcessHandle(
        {"p2": 2}, interval_ms=10, context=mp.get_context("spawn"),
        runtime_factory=_broken_runtime_factory,
    )
    handle.start(generation=1, map_instance="map-a")
    try:
        deadline = time.monotonic() + 5.0
        event = None
        while time.monotonic() < deadline and event is None:
            candidate = handle.poll_latest()
            if candidate is not None and candidate.kind == "error":
                event = candidate
            time.sleep(0.01)
        assert event is not None
        assert "runtime composition failed" in event.error
        assert "RuntimeError" in event.traceback_text
    finally:
        handle.stop()
