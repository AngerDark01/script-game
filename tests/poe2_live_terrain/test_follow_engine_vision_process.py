from __future__ import annotations

import multiprocessing as mp
import time

from auto_modules.features.poe2.live_terrain.experimental.follow_engine.contracts import (
    ObservationSource,
    RoleVisualObservation,
    VisualObservation,
)
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.vision.capture_adapter import CapturedFrame
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.vision.vision_process import (
    VisionProcessHandle,
    _cadence_wait_seconds,
)
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.shared_frame_ring import SharedFrameRing


class CountingCapture:
    def __init__(self):
        self.sequence = 0

    def capture(self):
        self.sequence += 1
        return CapturedFrame(1, self.sequence, self.sequence * 33, "map-a", b"frame")


class EchoProcessor:
    def process(self, frame):
        return VisualObservation(
            generation=frame.generation,
            sequence=frame.sequence,
            captured_at_ms=frame.captured_at_ms,
            map_instance=frame.map_instance,
            roles={
                "p1": RoleVisualObservation("p1", (float(frame.sequence), 0), confidence=1, visible=True),
            },
            source=ObservationSource.VISUAL,
        )


class FailingCapture:
    def capture(self):
        raise RuntimeError("capture boom")


def test_spawned_vision_process_publishes_newest_observation_and_stops():
    handle = VisionProcessHandle(CountingCapture(), EchoProcessor(), interval_ms=5, context=mp.get_context("spawn"))
    handle.start(generation=1, map_instance="map-a")
    deadline = time.monotonic() + 5.0
    event = None
    while time.monotonic() < deadline and event is None:
        candidate = handle.poll_latest()
        if candidate is not None and candidate.kind == "observation":
            event = candidate
        time.sleep(0.01)
    try:
        assert event is not None
        assert event.observation is not None
        assert event.observation.map_instance == "map-a"
        assert event.observation.sequence >= 1
        assert event.diagnostic_events
        assert event.diagnostic_events[-1]["stage"] == "vision"
        assert "timing" in event.diagnostic_events[-1]["details"]
        assert event.frame is not None
        assert event.frame.sequence == event.observation.sequence
        assert handle.process is not None and handle.process.is_alive()
    finally:
        handle.stop()
    assert handle.process is None


def test_vision_worker_error_is_not_overwritten_by_stopped_marker():
    handle = VisionProcessHandle(FailingCapture(), EchoProcessor(), interval_ms=5, context=mp.get_context("spawn"))
    handle.start(generation=1, map_instance="map-a")
    deadline = time.monotonic() + 5.0
    error = None
    while time.monotonic() < deadline and error is None:
        event = handle.poll_latest()
        if event is not None and event.kind == "error":
            error = event
        time.sleep(0.01)
    try:
        assert error is not None
        assert "capture boom" in error.error
        assert "RuntimeError" in error.traceback_text
    finally:
        handle.stop()


def test_spawned_vision_process_publishes_payload_to_shared_ring():
    ring = SharedFrameRing(capacity=2, slot_size=1024, map_instance="map-a")
    handle = VisionProcessHandle(
        CountingCapture(), EchoProcessor(), interval_ms=5,
        context=mp.get_context("spawn"), frame_ring=ring,
    )
    handle.start(generation=1, map_instance="map-a")
    event = None
    deadline = time.monotonic() + 5.0
    try:
        while time.monotonic() < deadline and event is None:
            candidate = handle.poll_latest()
            if candidate is not None and candidate.kind == "observation":
                event = candidate
            time.sleep(0.01)
        assert event is not None
        assert event.frame is None
        assert event.frame_in_ring is True
        record = ring.read(event.sequence)
        assert record is not None
        assert record.generation == event.generation
        assert record.payload == b"frame"
    finally:
        handle.stop()
        ring.close(unlink=True)


def test_vision_cadence_wait_excludes_processing_time():
    """A 33ms cadence must not become processing time plus another 33ms."""
    assert 0.012 <= _cadence_wait_seconds(started=10.0, interval_ms=33, now=10.020) <= 0.014
    assert _cadence_wait_seconds(started=10.0, interval_ms=33, now=10.040) == 0.001
