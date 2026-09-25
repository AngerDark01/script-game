from types import SimpleNamespace
from concurrent.futures import Future
import time

import numpy as np

from auto_modules.core.localization.frame_displacement import FrameDisplacement
from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.models import HybridFrame, PositionAnchor
from auto_modules.features.poe2.live_terrain.experimental.multiframe_localization.coordinator import MultiframeLocalizationCoordinator
from auto_modules.features.poe2.live_terrain.experimental.multiframe_localization.models import MultiFrameEvidence
from auto_modules.features.poe2.live_terrain.experimental.multiframe_localization.session import MultiframeLocalizationSession


class Source:
    def capture(self, config): return np.zeros((4, 4), dtype=np.uint8)


class Builder:
    def build(self, raw, config, *, frame_id, previous):
        frame = HybridFrame(frame_id, frame_id * 100, np.eye(4, dtype=np.uint8), (2, 2))
        return MultiFrameEvidence(frame, FrameDisplacement((1, 0), .9, 1, True, "accepted"), (frame_id, 0), True, 1)


class QueueExecutor:
    def __init__(self):
        self.jobs = []

    def submit(self, fn, *args):
        future = Future()
        self.jobs.append((future, fn, args))
        return future

    def shutdown(self, **kwargs):
        del kwargs


class RejectingStrategy:
    minimum_evidence_frames = 1

    def reset(self):
        pass

    def evaluate(self, window, submap, *, anchor, reference):
        del window, submap, anchor, reference
        from auto_modules.features.poe2.live_terrain.experimental.multiframe_localization.strategy_a import StrategyResult

        return StrategyResult.rejected(1, "test_rejected")


def test_session_captures_and_publishes_one_typed_estimate_per_tick():
    coordinator = MultiframeLocalizationCoordinator(instance_id="Map:A")
    session = MultiframeLocalizationSession(
        frame_source=Source(), evidence_builder=Builder(), config_provider=lambda: {}, coordinator=coordinator,
        anchor_provider=SimpleNamespace(read_once=lambda instance: PositionAnchor((1, 1), instance, 1, "memory")), clock_ms=lambda: 100,
    )
    session.start()
    session.anchor_once()
    result = session.tick()
    assert result.status == "collecting"
    assert result.evidence_version > 0


def test_anchor_once_is_idempotent_within_a_recovery_revision():
    coordinator = MultiframeLocalizationCoordinator(instance_id="Map:A")
    reads = []
    session = MultiframeLocalizationSession(
        frame_source=Source(), evidence_builder=Builder(), config_provider=lambda: {}, coordinator=coordinator,
        anchor_provider=SimpleNamespace(read_once=lambda instance: reads.append(instance) or PositionAnchor((1, 1), instance, 1, "memory")), clock_ms=lambda: 100,
    )
    session.start()
    assert session.anchor_once()
    assert not session.anchor_once()
    assert reads == ["Map:A"]


def test_start_reinitializes_capture_state_for_a_fresh_run():
    coordinator = MultiframeLocalizationCoordinator(instance_id="Map:A")
    session = MultiframeLocalizationSession(
        frame_source=Source(), evidence_builder=Builder(), config_provider=lambda: {}, coordinator=coordinator,
        anchor_provider=SimpleNamespace(read_once=lambda instance: PositionAnchor((1, 1), instance, 1, "memory")), clock_ms=lambda: 100,
    )
    session.start()
    session.anchor_once()
    session.tick()
    assert session._frame_id == 1
    session.stop()

    session.start()

    assert session._frame_id == 0
    assert session._previous is None
    assert session.last_estimate is None
    assert coordinator.phase.value == "anchoring"


def test_running_registration_from_old_generation_is_discarded_after_stop():
    coordinator = MultiframeLocalizationCoordinator(instance_id="Map:A")
    applied = []
    coordinator.apply_registration_outcome = lambda outcome: applied.append(outcome)
    session = MultiframeLocalizationSession(
        frame_source=Source(), evidence_builder=Builder(), config_provider=lambda: {}, coordinator=coordinator,
        anchor_provider=SimpleNamespace(read_once=lambda instance: PositionAnchor((1, 1), instance, 1, "memory")), clock_ms=lambda: 100,
    )
    session.start()
    future = Future()
    assert future.set_running_or_notify_cancel()
    session._registration_future = future
    session._registration_generation = session._generation

    session.stop()
    future.set_result(("stale", 1.0))
    session._publish_finished_registration()

    assert applied == []
    assert session._registration_future is None
    session.close()


def test_registration_timeout_detaches_running_worker_and_returns_to_collecting():
    coordinator = MultiframeLocalizationCoordinator(instance_id="Map:A")
    session = MultiframeLocalizationSession(
        frame_source=Source(), evidence_builder=Builder(), config_provider=lambda: {}, coordinator=coordinator,
        anchor_provider=SimpleNamespace(read_once=lambda instance: PositionAnchor((1, 1), instance, 1, "memory")),
        clock_ms=lambda: 100, registration_timeout_ms=1,
    )
    session.start()
    coordinator.phase = coordinator.phase.REGISTERING
    future = Future()
    session._registration_future = future
    session._registration_generation = session._generation
    session._registration_token = ("Map:A", 0, 1, 0)
    session._registration_started_monotonic = time.perf_counter() - 1.0

    session._expire_registration_if_needed()

    assert coordinator.phase.value == "collecting"
    assert session.last_estimate is not None
    assert session.last_estimate.reason == "registration_timeout"
    assert not session.registration_pending
    assert session._registration_future is None
    assert future in session._retired_registration_futures


def test_registration_timeout_releases_slot_for_a_new_registration_request():
    executor = QueueExecutor()
    coordinator = MultiframeLocalizationCoordinator(
        instance_id="Map:A",
        strategy_a=RejectingStrategy(),
        reference=SimpleNamespace(wall_layer=np.ones((8, 8), dtype=np.uint8)),
    )
    session = MultiframeLocalizationSession(
        frame_source=Source(),
        evidence_builder=Builder(),
        config_provider=lambda: {},
        coordinator=coordinator,
        anchor_provider=SimpleNamespace(
            read_once=lambda instance: PositionAnchor((1, 1), instance, 1, "memory")
        ),
        clock_ms=lambda: 100,
        executor=executor,
        registration_timeout_ms=1,
    )
    session.start()
    session.tick()
    assert len(executor.jobs) == 1
    session._registration_started_monotonic = time.perf_counter() - 1.0
    session._expire_registration_if_needed()

    session.tick()

    assert len(executor.jobs) == 2
    assert session._registration_future is executor.jobs[1][0]
    assert session.registration_pending
