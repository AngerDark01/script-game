from __future__ import annotations

import multiprocessing as mp
import time

from auto_modules.features.poe2.live_terrain.experimental.follow_engine.contracts import (
    ObservationSource,
    RoleVisualObservation,
    VisualObservation,
)
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.control.follow_control_process import (
    FollowControlProcessHandle,
    FollowControlRuntime,
    _cadence_wait_seconds,
)
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.recovery.local_recovery import LocalRecoveryBackend
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.shared_frame_ring import SharedFrameRecord, SharedFrameRing
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.vision.local_roi_matcher import RoiMatch
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.execution_feedback import ExecutionReceipt


def _runtime_factory(token, roles):
    return FollowControlRuntime(token, roles)


def _broken_runtime_factory(token, roles):
    raise RuntimeError("runtime composition failed")


def _ring_search(_frame, point, radius):
    return RoiMatch(True, (point[0] + 1.0, point[1]), 0.95, radius, "accepted")


def _ring_runtime_factory(token, roles):
    return FollowControlRuntime(
        token,
        roles,
        local_recovery=LocalRecoveryBackend(),
        local_search=_ring_search,
    )


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


def test_spawned_control_runtime_factory_reads_shared_ring_for_local_recovery():
    ring = SharedFrameRing(capacity=2, slot_size=128, map_instance="map-a")
    handle = FollowControlProcessHandle(
        {"p2": 2}, interval_ms=10, context=mp.get_context("spawn"),
        runtime_factory=_ring_runtime_factory, frame_ring=ring,
    )
    handle.start(generation=1, map_instance="map-a")
    try:
        handle.send_visual(_observation())
        ring.publish(SharedFrameRecord(1, 2, 66, "map-a", b"new-frame"))
        handle.send_visual(
            VisualObservation(
                generation=1,
                sequence=2,
                captured_at_ms=66,
                map_instance="map-a",
                roles={"p2": RoleVisualObservation("p2", None, visible=False)},
                source=ObservationSource.PARTIAL,
            )
        )
        deadline = time.monotonic() + 5.0
        recovered = None
        while time.monotonic() < deadline and recovered is None:
            candidate = handle.poll_latest()
            if candidate is not None and candidate.kind == "snapshot" and candidate.snapshot is not None:
                if candidate.snapshot.recovery_reason == "local_recovered":
                    recovered = candidate.snapshot
            time.sleep(0.01)
        assert recovered is not None
        assert recovered.roles["p2"].source == "local_roi"
    finally:
        handle.stop()
        ring.close(unlink=True)


def test_priority_target_is_not_evicted_by_visual_flood():
    handle = FollowControlProcessHandle({"p2": 2}, context=mp.get_context("spawn"))
    handle._command_generation = 1
    handle.update_target("p2", (99.0, 101.0))
    for _ in range(100):
        handle.send_visual(_observation())
    priority = []
    while True:
        try:
            priority.append(handle.priority_commands.get_nowait())
        except Exception:
            break
    assert any(item.get("kind") == "target" for item in priority)
    handle.dispose()


class _BoundedPriorityQueue:
    """Deterministic queue double for control-plane saturation tests."""

    def __init__(self, capacity: int):
        self.capacity = int(capacity)
        self.items = []

    def put_nowait(self, item):
        if len(self.items) >= self.capacity:
            raise __import__("queue").Full
        self.items.append(item)

    def get_nowait(self):
        if not self.items:
            raise __import__("queue").Empty
        return self.items.pop(0)

    def cancel_join_thread(self):
        return None

    def close(self):
        return None


def test_latest_target_survives_priority_saturation_and_flushes_after_receipt_drain():
    """A burst of execution receipts must not erase the live follow target."""
    handle = FollowControlProcessHandle({"p2": 2})
    handle._command_generation = 1
    bounded = _BoundedPriorityQueue(1)
    handle.priority_commands = bounded
    bounded.put_nowait({"kind": "blocker"})
    receipt = ExecutionReceipt(1, 1, "p2", (0.5, 0.0), 1000, 80)
    handle.send_execution(receipt)
    handle.update_target("p2", (99.0, 101.0))
    assert not any(item.get("kind") == "target" for item in bounded.items)
    bounded.get_nowait()
    # A normal parent poll is the first safe point after the Host receipt has
    # been drained; the newest target must be flushed then.
    handle.poll_latest()
    assert bounded.items[0]["kind"] == "execution"
    bounded.get_nowait()
    handle.poll_latest()
    assert any(item.get("kind") == "target" and item.get("target") == (99.0, 101.0) for item in bounded.items)
    handle.dispose()


def test_execution_receipt_is_deferred_and_flushed_fifo_after_priority_saturation():
    handle = FollowControlProcessHandle({"p2": 2})
    handle._command_generation = 1
    bounded = _BoundedPriorityQueue(1)
    handle.priority_commands = bounded
    bounded.put_nowait({"kind": "blocker"})
    first = ExecutionReceipt(1, 1, "p2", (0.5, 0.0), 1000, 40)
    second = ExecutionReceipt(1, 2, "p2", (0.0, 0.5), 1040, 40)
    handle.send_execution(first)
    handle.send_execution(second)
    assert [item["receipt"].sequence for item in handle._pending_executions] == [1, 2]
    bounded.get_nowait()
    handle.poll_latest()
    assert [item["receipt"].sequence for item in bounded.items] == [1]
    bounded.get_nowait()
    handle.poll_latest()
    assert [item["receipt"].sequence for item in bounded.items] == [2]
    handle.dispose()


def test_priority_fifo_does_not_bypass_pending_receipt_when_slot_opens():
    handle = FollowControlProcessHandle({"p2": 2})
    handle._command_generation = 1
    bounded = _BoundedPriorityQueue(1)
    handle.priority_commands = bounded
    bounded.put_nowait({"kind": "blocker"})
    first = ExecutionReceipt(1, 1, "p2", (0.5, 0.0), 1000, 40)
    second = ExecutionReceipt(1, 2, "p2", (0.0, 0.5), 1040, 40)
    handle.send_execution(first)
    # Simulate the consumer freeing a slot between two parent calls.  The
    # older pending receipt must still block direct insertion of sequence 2.
    bounded.get_nowait()
    handle.send_execution(second)
    assert [item["receipt"].sequence for item in bounded.items] == [1]
    assert [item["receipt"].sequence for item in handle._pending_executions] == [2]
    handle.poll_latest()
    assert [item["receipt"].sequence for item in bounded.items] == [1]
    bounded.get_nowait()
    handle.poll_latest()
    assert [item["receipt"].sequence for item in bounded.items] == [2]
    handle.dispose()


def test_recovery_signal_joins_pending_priority_fifo():
    handle = FollowControlProcessHandle({"p2": 2})
    handle._command_generation = 1
    bounded = _BoundedPriorityQueue(1)
    handle.priority_commands = bounded
    bounded.put_nowait({"kind": "blocker"})
    first = ExecutionReceipt(1, 1, "p2", (0.5, 0.0), 1000, 40)
    handle.send_execution(first)
    bounded.get_nowait()
    handle.send_recovery_signal("transform_invalid")
    assert bounded.items[0]["kind"] == "execution"
    assert [item["kind"] for item in handle._pending_executions] == ["recovery_signal"]
    handle.poll_latest()
    assert bounded.items[0]["kind"] == "execution"
    handle.dispose()


def test_execution_gap_rejects_unknown_role_and_zero_sequence_without_state_change():
    from auto_modules.features.poe2.live_terrain.experimental.follow_engine.generation import GenerationToken
    runtime = FollowControlRuntime(GenerationToken(1, "map-a"), {"p2": 2})
    runtime.seed_position("p2", (10.0, 10.0), captured_at_ms=100)
    before = runtime._roles["p2"].state
    runtime.signal_execution_gap("p2", sequence=0)
    runtime.signal_execution_gap("missing", sequence=1)
    after = runtime._roles["p2"].state
    assert after == before


def test_execution_receipt_duplicate_and_wrong_generation_do_not_double_integrate():
    from auto_modules.features.poe2.live_terrain.experimental.follow_engine.generation import GenerationToken
    runtime = FollowControlRuntime(GenerationToken(1, "map-a"), {"p2": 2})
    runtime.seed_position("p2", (10.0, 10.0), captured_at_ms=100)
    receipt = ExecutionReceipt(1, 1, "p2", (1.0, 0.0), 100, 80)
    stale = ExecutionReceipt(2, 2, "p2", (1.0, 0.0), 100, 80)
    assert runtime.record_execution(receipt) is True
    assert runtime.record_execution(receipt) is False
    assert runtime.record_execution(stale) is False
    assert len(runtime._roles["p2"].execution_receipts) == 1


def test_delayed_visual_rewinds_receipt_segments_before_fusion():
    from auto_modules.features.poe2.live_terrain.experimental.follow_engine.generation import GenerationToken
    runtime = FollowControlRuntime(GenerationToken(1, "map-a"), {"p2": 2})
    runtime.seed_position("p2", (10.0, 10.0), captured_at_ms=100)
    runtime.record_execution(ExecutionReceipt(1, 1, "p2", (1.0, 0.0), 100, 100))
    role = runtime._roles["p2"]
    role.state = role.state.__class__("p2", (18.0, 10.0), (80.0, 0.0), 1.0, 100, 200, "command_prediction")
    accepted = runtime.apply_visual(VisualObservation(
        generation=1, sequence=2, captured_at_ms=100, map_instance="map-a",
        roles={"p2": RoleVisualObservation("p2", (10.0, 10.0), confidence=1, uncertainty_native=1, visible=True, last_visual_at_ms=100)},
        source=ObservationSource.VISUAL,
    ))
    assert accepted is True
    assert runtime._roles["p2"].state.position_native[0] <= 11.0


def test_visual_frame_metadata_mismatch_is_rejected_for_local_recovery():
    from auto_modules.features.poe2.live_terrain.experimental.follow_engine.generation import GenerationToken
    runtime = FollowControlRuntime(GenerationToken(1, "map-a"), {"p2": 2})
    runtime.seed_position("p2", (10.0, 10.0), captured_at_ms=100)
    class WrongFrame:
        sequence = 99
        generation = 1
        map_instance = "map-a"
        captured_at_ms = 100
    observation = VisualObservation(
        generation=1, sequence=1, captured_at_ms=100, map_instance="map-a",
        roles={"p2": RoleVisualObservation("p2", None, visible=False)},
        source=ObservationSource.PARTIAL,
    )
    assert runtime.apply_visual(observation, frame=WrongFrame()) is True
    assert runtime._latest_frame is None


def test_control_cadence_wait_excludes_tick_processing_time():
    """Control cadence is start-to-start, matching the vision worker."""

    assert 0.012 <= _cadence_wait_seconds(
        started=10.0, interval_ms=33, now=10.020
    ) <= 0.014
    assert _cadence_wait_seconds(
        started=10.0, interval_ms=33, now=10.040
    ) == 0.001
