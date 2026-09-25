from concurrent.futures import Future
from types import SimpleNamespace

import numpy as np

from auto_modules.core.localization import LocalizationResult
from auto_modules.core.localization.frame_displacement import FrameDisplacement
from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.models import (
    AbsoluteRegistration,
    HybridFrame,
    PositionAnchor,
    SimilarityTransform2D,
)
from auto_modules.features.poe2.live_terrain.experimental.multiframe_localization.coordinator import (
    LocalizationPhase,
    MultiframeLocalizationCoordinator,
)
from auto_modules.features.poe2.live_terrain.experimental.multiframe_localization.models import MultiFrameEvidence
from auto_modules.features.poe2.live_terrain.experimental.multiframe_localization.registration_validator import RegistrationValidator
from auto_modules.features.poe2.live_terrain.experimental.multiframe_localization.session import MultiframeLocalizationSession
from auto_modules.features.poe2.live_terrain.experimental.multiframe_localization.strategy_a import StrategyResult


AREA = "Map:EndToEnd"


def _evidence(frame_id, *, shift=(2.0, 0.0), accepted=True, keyframe=True, segment=0):
    mask = np.zeros((16, 16), dtype=np.uint8)
    mask[3:13, 5] = 255
    frame = HybridFrame(frame_id, frame_id * 100, mask, (8.0, 8.0))
    distance = float(np.hypot(*shift))
    motion = FrameDisplacement(shift, 0.9 if accepted else 0.0, distance, accepted, "accepted" if accepted else "low_quality")
    return MultiFrameEvidence(frame, motion, (-frame_id * shift[0], -frame_id * shift[1]), keyframe, segment)


def _registration(position=(100.0, 100.0), *, angle=90.0):
    return AbsoluteRegistration(
        LocalizationResult(position, 0.9, source="test", registration_valid=True),
        SimilarityTransform2D(angle, False, 1.0, (position[0] - 8.0, position[1] + 8.0)),
        0.0,
        AREA,
    )


class ConfirmingStrategy:
    def __init__(self):
        self.calls = 0

    def evaluate(self, window, submap, *, anchor, reference):
        del window, submap, anchor, reference
        self.calls += 1
        return StrategyResult.confirmed(self.calls, _registration())


def test_global_tracking_stationary_degraded_and_recovery_are_one_chain():
    strategy = ConfirmingStrategy()
    coordinator = MultiframeLocalizationCoordinator(
        instance_id=AREA,
        strategy_a=strategy,
        reference=SimpleNamespace(wall_layer=np.ones((32, 32), dtype=np.uint8)),
        registration_validator=RegistrationValidator(min_support_frames=1),
        max_tracking_failures=2,
    )
    coordinator.start()
    coordinator.accept_anchor(PositionAnchor((100.0, 100.0), AREA, 0, "memory"))

    confirmed = coordinator.ingest(_evidence(1))
    assert confirmed.status == "confirmed"
    assert coordinator.phase is LocalizationPhase.TRACKING

    # A wall shift to the right means the player moved left in local image space.
    # At +90 image rotation that becomes +native Y.
    moved = coordinator.ingest(_evidence(2, shift=(2.0, 0.0)))
    assert moved.position == (100.0, 102.0)
    assert moved.fresh

    stationary = coordinator.ingest(_evidence(3, shift=(0.0, 0.0), keyframe=False))
    assert coordinator.phase is LocalizationPhase.TRACKING
    assert stationary.status == "confirmed"
    assert not stationary.fresh

    first_failure = coordinator.ingest(_evidence(4, accepted=False, keyframe=False))
    assert first_failure.status == "predicted"
    assert coordinator.phase is LocalizationPhase.DEGRADED

    coordinator.ingest(_evidence(5, accepted=False, keyframe=False, segment=1))
    assert coordinator.phase is LocalizationPhase.RECOVERING
    assert coordinator.recovery_revision == 1


class QueueExecutor:
    def __init__(self):
        self.jobs = []

    def submit(self, fn, *args):
        future = Future()
        self.jobs.append((future, fn, args))
        return future

    def run_next(self):
        future, fn, args = self.jobs.pop(0)
        future.set_result(fn(*args))

    def shutdown(self, **kwargs):
        del kwargs


class Source:
    def capture(self, config):
        del config
        return object()


class Builder:
    def build(self, raw, config, *, frame_id, previous):
        del raw, config, previous
        return _evidence(frame_id)


class Anchors:
    def __init__(self):
        self.read_count = 0

    def read_once(self, instance):
        self.read_count += 1
        return PositionAnchor((100.0, 100.0), instance, self.read_count, "memory")


def test_session_reads_one_anchor_per_revision_and_tracks_motion_during_async_registration():
    executor = QueueExecutor()
    anchors = Anchors()
    strategy = ConfirmingStrategy()
    coordinator = MultiframeLocalizationCoordinator(
        instance_id=AREA,
        strategy_a=strategy,
        reference=SimpleNamespace(wall_layer=np.ones((32, 32), dtype=np.uint8)),
        registration_validator=RegistrationValidator(min_support_frames=1),
    )
    session = MultiframeLocalizationSession(
        frame_source=Source(),
        evidence_builder=Builder(),
        config_provider=lambda: object(),
        coordinator=coordinator,
        anchor_provider=anchors,
        clock_ms=lambda: 0,
        executor=executor,
    )
    session.start()
    session.tick()
    session.tick()  # evidence advances while the first immutable registration is pending
    assert anchors.read_count == 1
    assert len(executor.jobs) == 1
    executor.run_next()
    result = session.tick()
    assert result.status == "confirmed"
    assert coordinator.registration_version == 1
    assert result.position != (100.0, 100.0)

    coordinator.begin_recovery("lost")
    session.tick()
    session.tick()
    assert anchors.read_count == 2


def test_registration_from_an_old_recovery_revision_is_discarded():
    strategy = ConfirmingStrategy()
    coordinator = MultiframeLocalizationCoordinator(
        instance_id=AREA,
        strategy_a=strategy,
        reference=SimpleNamespace(wall_layer=np.ones((32, 32), dtype=np.uint8)),
        registration_validator=RegistrationValidator(min_support_frames=1),
    )
    coordinator.start()
    coordinator.accept_anchor(PositionAnchor((100.0, 100.0), AREA, 0, "memory"))
    coordinator.ingest(_evidence(1), defer_registration=True)
    request = coordinator.prepare_registration_request()
    assert request is not None
    outcome = coordinator.evaluate_registration(request)
    coordinator.begin_recovery("new_revision")
    stale = coordinator.apply_registration_outcome(outcome)
    assert stale.reason == "stale_registration_result"
    assert coordinator.registration_version == 0
