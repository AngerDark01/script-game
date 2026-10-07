from __future__ import annotations

from auto_modules.features.poe2.live_terrain.experimental.follow_engine.contracts import (
    ObservationSource,
    RoleVisualObservation,
    VisualObservation,
)
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.control.follow_control_process import FollowControlRuntime
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.generation import GenerationClock
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.latest_frame_buffer import LatestFrameBuffer


def _visual(sequence: int, captured_at_ms: int, position=(0.0, 0.0)) -> VisualObservation:
    return VisualObservation(
        generation=1,
        sequence=sequence,
        captured_at_ms=captured_at_ms,
        map_instance="map-a",
        roles={
            "p2": RoleVisualObservation(
                "p2", position, confidence=1.0, uncertainty_native=1.0,
                visible=True, last_visual_at_ms=captured_at_ms,
            ),
        },
        source=ObservationSource.VISUAL,
    )


def test_latest_only_stress_drops_old_frames_without_queue_growth():
    buffer = LatestFrameBuffer[int]()
    consumed = []
    for sequence in range(1, 301):
        assert buffer.publish(sequence, sequence) is True
        if sequence % 6 == 0:
            item = buffer.take(after_sequence=consumed[-1] if consumed else -1)
            if item is not None:
                consumed.append(item.sequence)
    latest = buffer.take(after_sequence=299)
    assert latest is not None and latest.sequence == 300
    assert buffer.dropped_count >= 200
    assert len(consumed) <= 51


def test_control_tick_remains_bounded_under_30hz_visual_and_60hz_control_load():
    token = GenerationClock().begin("map-a")
    runtime = FollowControlRuntime(token, {"p2": 2})
    runtime.update_target("p2", (100.0, 20.0))
    timings = []
    for tick in range(1, 181):
        now_ms = tick * 16
        if tick % 2 == 0:
            runtime.apply_visual(_visual(tick, now_ms, (tick * 0.2, 0.0)))
        snapshot = runtime.tick(now_ms=now_ms)
        timings.append(snapshot.timing.total_ms)
    assert max(timings) < 100.0
    assert runtime.session_active is True
    assert runtime.snapshot() is not None
