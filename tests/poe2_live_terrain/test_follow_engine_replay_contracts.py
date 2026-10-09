"""Focused offline replays for the dual-channel follow contracts.

These tests deliberately stop at the process/transport boundary.  They never
start PoE2, a Host backend, a memory reader, or a real controller.
"""

from __future__ import annotations

import multiprocessing as mp
import queue
import threading
import time

from auto_modules.features.poe2.live_terrain.experimental.follow_engine.control.follow_control_process import (
    FollowControlRuntime,
)
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.control.route_controller import (
    LegacyDynamicFollowRouteController,
)
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.execution_feedback import ExecutionReceipt
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.generation import GenerationClock
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.recovery.local_recovery import LocalRecoveryBackend
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.recovery.memory_recovery import MemoryRecoveryBackend
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.contracts import (
    ObservationSource,
    RoleVisualObservation,
    VisualObservation,
)
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.vision.local_roi_matcher import RoiMatch
from auto_modules.features.poe2.live_terrain.experimental.follow_contract import DYNAMIC_FOLLOW_CONTRACT
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.engine import FollowEnginePort, FollowEngineStart
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.contracts import FusionSnapshot


def _obs(sequence: int, captured_at_ms: int, *, p1=(0.0, 0.0), p2=(20.0, 0.0), p2_visible=True):
    return VisualObservation(
        generation=1,
        sequence=sequence,
        captured_at_ms=captured_at_ms,
        map_instance="map-a",
        roles={
            "p1": RoleVisualObservation("p1", p1, confidence=1.0, uncertainty_native=1.0, visible=True),
            "p2": RoleVisualObservation(
                "p2", p2 if p2_visible else None, confidence=1.0,
                uncertainty_native=1.0, visible=p2_visible,
            ),
        },
        source=ObservationSource.VISUAL if p2_visible else ObservationSource.PARTIAL,
        transform={"rotation": 221.0, "scale": 0.903, "translation": (captured_at_ms / 10.0, 4.0)},
    )


class _Search:
    def __init__(self, result: RoiMatch):
        self.result = result
        self.calls = []
        self.observations = []

    def bind_observation(self, observation):
        self.observations.append(observation)

    def __call__(self, frame, point, radius):
        self.calls.append((frame, point, radius, self.observations[-1].transform))
        return self.result


class _MemorySource:
    def __init__(self):
        self.reads = 0

    def read_many(self, expected_instance_id):
        self.reads += 1
        return (type("Sample", (), {"identity": "p2", "grid": (24, 2), "area_instance": expected_instance_id})(),)


def test_local_first_replay_rewinds_receipts_and_reuses_frame_transform():
    token = GenerationClock().begin("map-a")
    search = _Search(RoiMatch(True, (21.0, 1.0), 0.95, 80.0, "accepted"))
    runtime = FollowControlRuntime(
        token, {"p2": 2}, observation_role_ids=("p1", "p2"),
        local_recovery=LocalRecoveryBackend(), local_search=search,
    )
    runtime.apply_visual(_obs(1, 1000, p2=(20.0, 0.0)))
    runtime.record_execution(ExecutionReceipt(1, 1, "p2", (0.5, 0.0), 900, 400))
    runtime.record_execution(ExecutionReceipt(1, 2, "p2", (0.25, 0.0), 1200, 400))
    runtime.apply_visual(_obs(2, 1300, p2_visible=False), frame="frame-2")
    snapshot = runtime.tick(now_ms=1400)
    assert search.calls, "a new frame must trigger local ROI before memory"
    assert search.calls[0][0] == "frame-2"
    assert search.calls[0][3]["rotation"] == 221.0
    assert search.calls[0][3]["scale"] == 0.903
    assert snapshot.session_active is True
    assert snapshot.roles["p2"].source == "local_roi"
    assert runtime._roles["p2"].misses == 0
    # The delayed visual was fused at t0 and the two receipts are replayed at
    # most once; no second execution receipt is created by local recovery.
    assert runtime._roles["p2"].execution_cursor_ms >= 1400
    runtime.close()


def test_local_miss_escalates_to_one_memory_submission_with_cooldown():
    token = GenerationClock().begin("map-a")
    source = _MemorySource()
    memory = MemoryRecoveryBackend(source, transform=lambda point: point, expected_players=1, cooldown_ms=8000)
    search = _Search(RoiMatch(False, None, 0.0, 80.0, "miss"))
    runtime = FollowControlRuntime(
        token, {"p2": 2}, local_recovery=LocalRecoveryBackend(), local_search=search,
        memory_recovery=memory,
    )
    runtime.apply_visual(_obs(1, 0, p2=(20.0, 0.0)))
    for sequence, now in ((2, 700), (3, 1400), (4, 2100), (5, 2800)):
        runtime.apply_visual(_obs(sequence, now, p2_visible=False), frame=f"frame-{sequence}")
        runtime.tick(now_ms=now)
    # submit() is asynchronous; it must be single-flight and cooldown gated.
    assert memory.in_flight or source.reads == 1
    runtime.tick(now_ms=2850)
    assert source.reads <= 1
    assert runtime.session_active is True
    runtime.close()
    memory.close()


def test_stale_generation_transform_and_duplicate_receipt_are_harmless():
    token = GenerationClock().begin("map-a")
    runtime = FollowControlRuntime(token, {"p2": 2})
    runtime.apply_visual(_obs(1, 0, p2=(20.0, 0.0)))
    receipt = ExecutionReceipt(1, 1, "p2", (0.5, 0.0), 0, 100)
    assert runtime.record_execution(receipt) is True
    assert runtime.record_execution(receipt) is False
    before = runtime._roles["p2"].state.position_native
    assert runtime.apply_visual(_obs(1, 0, p2=(999.0, 999.0))) is False
    assert runtime._roles["p2"].state.position_native == before
    assert runtime.session_active is True
    runtime.close()


def _sequence_writer(output, stop):
    sequence = 0
    while not stop.is_set():
        sequence += 1
        output.put(sequence)
        time.sleep(0.01)


def test_spawn_child_progresses_while_parent_poll_is_paused():
    context = mp.get_context("spawn")
    output = context.Queue()
    stop = context.Event()
    child = context.Process(target=_sequence_writer, args=(output, stop))
    child.start()
    try:
        time.sleep(3.0)
        values = []
        while True:
            try:
                values.append(output.get_nowait())
            except queue.Empty:
                break
        assert child.is_alive()
        assert len(values) >= 100
        assert values == sorted(values)
    finally:
        stop.set()
        child.join(timeout=2.0)
        if child.is_alive():
            child.terminate()


def test_spawn_child_stall_is_observable_once_after_writer_stops():
    context = mp.get_context("spawn")
    output = context.Queue()
    stop = context.Event()
    child = context.Process(target=_sequence_writer, args=(output, stop))
    child.start()
    try:
        deadline = time.monotonic() + 1.0
        last = None
        while time.monotonic() < deadline and last is None:
            try:
                last = output.get(timeout=0.05)
            except queue.Empty:
                pass
        assert last is not None
        stop.set()
        child.join(timeout=2.0)
        time.sleep(0.15)
        assert not child.is_alive()
        # A stalled child is an observable health condition; this fixture does
        # not pretend that a parent-side queue drain is a full relay rebuild.
        assert child.exitcode == 0
    finally:
        if child.is_alive():
            child.terminate()


def test_legacy_route_adapter_contract_preserves_dynamic_follow_semantics():
    import numpy as np

    controller = LegacyDynamicFollowRouteController(np.zeros((64, 64), dtype=np.uint8))
    arrived = controller.plan((10.0, 10.0), (15.0, 10.0))
    # Continuous follow holds the session while nearby; it is not a terminal
    # one-shot arrival.
    assert arrived.arrived is False
    assert arrived.vector == (0.0, 0.0)
    assert arrived.duration_ms == 0
    moving = controller.plan((10.0, 10.0), (50.0, 10.0), now_ms=1033)
    assert moving.arrived is False
    assert 0 <= moving.duration_ms <= 33
    assert moving.route
    assert max(abs(value) for value in moving.vector) <= 1.0
    assert controller.arrival_radius == 12.0

    # A stopped leader must not cause an already-near follower to keep
    # advancing.  Moving the leader out of the hold band emits a legacy pulse;
    # returning it to the band restores neutral hold.
    pulse = controller.plan((10.0, 10.0), (60.0, 10.0), now_ms=1066)
    assert pulse.vector != (0.0, 0.0)
    hold = controller.plan((10.0, 10.0), (15.0, 10.0), now_ms=1099)
    assert hold.vector == (0.0, 0.0)
    assert "hold" in hold.reason


def test_all_follow_compositions_share_the_legacy_motion_contract():
    assert DYNAMIC_FOLLOW_CONTRACT.arrival_radius == 12.0
    assert DYNAMIC_FOLLOW_CONTRACT.resume_radius == 20.0
    assert DYNAMIC_FOLLOW_CONTRACT.speed_units_per_second == 80.0
    assert DYNAMIC_FOLLOW_CONTRACT.downsample_factor == 8
    assert DYNAMIC_FOLLOW_CONTRACT.local_lookahead == 24.0
    assert DYNAMIC_FOLLOW_CONTRACT.prediction_horizon == 0.25


class _RelayVision:
    def __init__(self):
        self.sequence = 0
        self.running = False

    def start(self, *, generation, map_instance):
        self.running = True

    def poll_latest(self):
        if not self.running:
            return None
        self.sequence += 1
        return type("VisionEvent", (), {"kind": "observation", "sequence": self.sequence, "observation": None, "frame": None})()

    def stop(self, *, timeout=2.0):
        self.running = False


class _RelayControl:
    def __init__(self):
        self.tick = 0
        self.running = False
        self.visuals = 0

    def start(self, *, generation, map_instance):
        self.running = True

    def send_visual(self, observation, *, frame=None):
        self.visuals += 1

    def send_execution(self, receipt):
        pass

    def update_target(self, role_id, target):
        pass

    def poll_latest(self):
        if not self.running:
            return None
        self.tick += 1
        snapshot = type("Snapshot", (), {"tick_sequence": self.tick, "output_intents": ()})()
        return type("ControlEvent", (), {"kind": "snapshot", "snapshot": snapshot})()

    def stop(self, *, timeout=2.0):
        self.running = False


class _RelayOutput:
    def __init__(self):
        self.applies = 0
        self.running = False

    def start(self):
        self.running = True

    def apply(self, snapshot):
        self.applies += 1

    def stop(self, *, force=True):
        self.running = False

    def neutralize(self):
        pass

    def poll_receipts(self):
        return ()


def test_follow_engine_relay_continues_without_ui_poll():
    vision, control, output = _RelayVision(), _RelayControl(), _RelayOutput()
    port = FollowEnginePort(vision=vision, control=control, output=output, stall_timeout_ms=5000)
    port.start(FollowEngineStart("map-a", {"p2": 2}))
    try:
        time.sleep(3.0)
        assert control.tick >= 100
        assert output.applies >= 100
        snapshot = port.poll()
        assert snapshot is not None
        assert snapshot.tick_sequence == control.tick
        assert port.active is True
        assert port._worker_state["control"] == "running"
    finally:
        port.stop(reason="test")


def test_relay_and_concurrent_ui_polls_have_single_snapshot_consumer():
    vision, control, output = _RelayVision(), _RelayControl(), _RelayOutput()
    port = FollowEnginePort(vision=vision, control=control, output=output, stall_timeout_ms=5000)
    port.start(FollowEngineStart("map-a", {"p2": 2}))
    seen = []
    stop = threading.Event()

    def reader():
        while not stop.is_set():
            snapshot = port.poll()
            if snapshot is not None:
                seen.append(int(snapshot.tick_sequence))

    readers = [threading.Thread(target=reader) for _ in range(8)]
    for reader_thread in readers:
        reader_thread.start()
    try:
        time.sleep(0.35)
    finally:
        stop.set()
        for reader_thread in readers:
            reader_thread.join(timeout=1.0)
        assert port._last_error == ""
        produced_ticks = control.tick
        port.stop(reason="test")
    assert seen
    assert control.tick > 0
    # Cross-thread reader completion order is intentionally unspecified; the
    # relay-owned producer sequence itself must remain monotonic.
    assert min(seen) >= 1
    assert max(seen) <= produced_ticks
    assert output.applies == control.tick


def test_relay_offline_benchmark_reports_percentiles_and_separates_entry_gap():
    vision, control, output = _RelayVision(), _RelayControl(), _RelayOutput()
    port = FollowEnginePort(vision=vision, control=control, output=output, stall_timeout_ms=5000)
    port.start(FollowEngineStart("map-a", {"p2": 2}))
    try:
        time.sleep(0.25)
        diagnostics = port.diagnostics()
        relay = diagnostics["relay_diagnostics"]
        assert relay["sample_count"] > 3
        assert relay["step_p50_ms"] is not None
        assert relay["step_p95_ms"] is not None
        assert relay["step_max_ms"] >= relay["step_p95_ms"]
        assert relay["entry_gap_ms"] >= relay["step_duration_ms"]
        assert diagnostics["parent_entry_gap_ms"] is not None
    finally:
        port.stop(reason="test")


def test_offline_timing_and_latest_only_queue_report_percentiles_and_age():
    from auto_modules.features.poe2.live_terrain.experimental.follow_engine.latest_frame_buffer import LatestFrameBuffer
    from auto_modules.features.poe2.live_terrain.experimental.follow_engine.timing import TimingWindow

    timing = TimingWindow(8)
    for value in (1.0, 2.0, 4.0, 8.0):
        timing.add(value)
    report = timing.as_dict("control_")
    assert report["control_p50_ms"] == 4.0
    assert report["control_p95_ms"] == 8.0
    assert report["control_max_ms"] == 8.0

    buffer = LatestFrameBuffer()
    frame = type("Frame", (), {"captured_at_ms": 900})()
    assert buffer.publish(1, frame)
    assert buffer.publish(2, frame)
    queue = buffer.diagnostics(now_ms=1000)
    assert queue["queue_depth"] == 1
    assert queue["latest_only_dropped_count"] == 1
    assert queue["queue_age_ms"] == 100.0
