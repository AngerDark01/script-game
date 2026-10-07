from __future__ import annotations

import multiprocessing as mp
import time

from auto_modules.features.poe2.live_terrain.experimental.follow_engine.contracts import (
    ObservationSource,
    RoleVisualObservation,
    VisualObservation,
)
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.control.follow_control_process import FollowControlProcessHandle


def _observation(generation: int) -> VisualObservation:
    return VisualObservation(
        generation=generation,
        sequence=1,
        captured_at_ms=1,
        map_instance="map-a",
        roles={"p2": RoleVisualObservation("p2", (10.0, 0.0), confidence=1.0, uncertainty_native=1.0, visible=True, last_visual_at_ms=1)},
        source=ObservationSource.VISUAL,
    )


def test_spawn_control_process_can_start_and_stop_repeatedly_without_residual_process():
    handle = FollowControlProcessHandle({"p2": 2}, interval_ms=5, context=mp.get_context("spawn"))
    for generation in range(1, 6):
        handle.start(generation=generation, map_instance="map-a")
        handle.send_visual(_observation(generation))
        deadline = time.monotonic() + 2.0
        event = None
        while time.monotonic() < deadline and event is None:
            event = handle.poll_latest()
            time.sleep(0.01)
        assert event is not None
        handle.stop(timeout=1.0)
        assert handle.process is None
