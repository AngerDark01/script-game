from __future__ import annotations

import multiprocessing as mp
import time

from auto_modules.features.poe2.live_terrain.experimental.follow_engine.contracts import (
    ObservationSource,
    RoleVisualObservation,
    VisualObservation,
)
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.vision.capture_adapter import CapturedFrame
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.vision.vision_process import VisionProcessHandle


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
        assert handle.process is not None and handle.process.is_alive()
    finally:
        handle.stop()
    assert handle.process is None
