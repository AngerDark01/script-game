from types import SimpleNamespace

import numpy as np

from auto_modules.core.localization import LocalizationResult
from auto_modules.core.localization.frame_displacement import FrameDisplacement
from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.models import AbsoluteRegistration, HybridFrame, PositionAnchor, SimilarityTransform2D
from auto_modules.features.poe2.live_terrain.experimental.multiframe_localization.coordinator import LocalCorrectionPolicy, LocalizationPhase, MultiframeLocalizationCoordinator
from auto_modules.features.poe2.live_terrain.experimental.multiframe_localization.local_corrector import LocalCorrection, SearchBounds
from auto_modules.features.poe2.live_terrain.experimental.multiframe_localization.models import MultiFrameEvidence
from auto_modules.features.poe2.live_terrain.experimental.multiframe_localization.registration_validator import RegistrationValidator
from auto_modules.features.poe2.live_terrain.experimental.multiframe_localization.strategy_a import StrategyResult
from auto_modules.features.poe2.live_terrain.experimental.multiframe_localization.strategy_a import StitchThenRegister, SubmapThresholds
from auto_modules.features.poe2.live_terrain.experimental.multiframe_localization.strategy_b import JointCandidateStrategy


def _evidence(frame_id=1, segment=1):
    frame = HybridFrame(frame_id, frame_id * 100, np.eye(8, dtype=np.uint8), (4, 4))
    return MultiFrameEvidence(frame, FrameDisplacement((2, 0), .9, 2, True, "accepted"), (frame_id, 0), True, segment)


def test_coordinator_accepts_one_anchor_then_confirms_and_tracks():
    coordinator = MultiframeLocalizationCoordinator(instance_id="Map:A")
    coordinator.start()
    coordinator.accept_anchor(PositionAnchor((10, 10), "Map:A", 100, "memory"))
    assert coordinator.phase is LocalizationPhase.COLLECTING
    coordinator.ingest(_evidence())
    result = coordinator.confirm(SimpleNamespace(), (10, 10))
    assert result.status == "confirmed"
    assert coordinator.phase is LocalizationPhase.TRACKING
    tracked = coordinator.ingest(_evidence(2))
    assert tracked.status == "confirmed"


def test_coordinator_rejects_wrong_anchor_instance():
    coordinator = MultiframeLocalizationCoordinator(instance_id="Map:A")
    coordinator.start()
    try:
        coordinator.accept_anchor(PositionAnchor((1, 1), "Map:B", 1, "memory"))
    except ValueError:
        pass
    assert coordinator.phase is LocalizationPhase.WAITING


def test_strategy_b_can_confirm_without_strategy_a():
    candidate = SimpleNamespace(
        position=(12.0, 14.0),
        transform=SimpleNamespace(angle_degrees=0.0, reflect_horizontal=False, scale=1.0, translation=(0.0, 0.0)),
        error=0.1,
        score=0.9,
        support_frames=(1, 2, 3),
        holdout_error=1.0,
        region=lambda: None,
    )
    candidate_set = SimpleNamespace(candidates=(candidate,), best=candidate, evidence_version=3)
    strategy_b = SimpleNamespace(update=lambda *args, **kwargs: candidate_set, confirmable=lambda result: True)
    coordinator = MultiframeLocalizationCoordinator(
        instance_id="Map:A",
        strategy_b=strategy_b,
        reference=SimpleNamespace(wall_layer=np.ones((16, 16), dtype=np.uint8)),
    )
    coordinator.start()
    coordinator.accept_anchor(PositionAnchor((10, 10), "Map:A", 100, "memory"))
    result = coordinator.ingest(_evidence())
    assert result.status == "confirmed"
    assert result.source == "multiframe_strategy_b"


def test_builtin_strategies_do_not_register_until_their_multi_frame_contract_is_ready():
    coordinator = MultiframeLocalizationCoordinator(
        instance_id="Map:A",
        strategy_a=StitchThenRegister(
            SimpleNamespace(),
            thresholds=SubmapThresholds(min_frames=4),
        ),
        strategy_b=JointCandidateStrategy(min_support_frames=3),
        reference=SimpleNamespace(wall_layer=np.ones((16, 16), dtype=np.uint8)),
    )

    coordinator.start()
    coordinator.accept_anchor(PositionAnchor((10, 10), "Map:A", 100, "memory"))
    coordinator.ingest(_evidence(1), defer_registration=True)

    assert coordinator.minimum_registration_frames == 5
    assert coordinator.prepare_registration_request() is None


def test_strategy_a_also_passes_through_registration_validator():
    candidate = AbsoluteRegistration(
        LocalizationResult((100.0, 100.0), 0.9, source="strategy_a", registration_valid=True),
        SimilarityTransform2D(0.0, False, 1.0, (96.0, 96.0)),
        0.0,
        "Map:A",
    )
    strategy_a = SimpleNamespace(
        evaluate=lambda *args, **kwargs: StrategyResult.confirmed(1, candidate),
    )
    coordinator = MultiframeLocalizationCoordinator(
        instance_id="Map:A",
        strategy_a=strategy_a,
        reference=SimpleNamespace(wall_layer=np.ones((16, 16), dtype=np.uint8)),
        registration_validator=RegistrationValidator(min_support_frames=1),
    )
    coordinator.start()
    coordinator.accept_anchor(PositionAnchor((10, 10), "Map:A", 100, "memory"))

    result = coordinator.ingest(_evidence())

    assert result.status == "collecting"
    assert result.reason == "anchor_uncertainty"
    assert coordinator.registration is None


def test_ab_selection_prefers_the_higher_confidence_valid_registration():
    candidate_a = AbsoluteRegistration(
        LocalizationResult((10.0, 10.0), 0.70, source="strategy_a", registration_valid=True),
        SimilarityTransform2D(0.0, False, 1.0, (6.0, 6.0)),
        0.0,
        "Map:A",
    )
    candidate_b = SimpleNamespace(
        position=(10.5, 10.5),
        transform=SimilarityTransform2D(0.0, False, 1.0, (6.5, 6.5)),
        error=0.1,
        score=0.95,
        support_frames=(1,),
        holdout_error=1.0,
        region=lambda: None,
    )
    strategy_a = SimpleNamespace(evaluate=lambda *args, **kwargs: StrategyResult.confirmed(1, candidate_a))
    strategy_b = SimpleNamespace(
        update=lambda *args, **kwargs: SimpleNamespace(candidates=(candidate_b,), best=candidate_b, evidence_version=1),
        confirmable=lambda result: True,
    )
    coordinator = MultiframeLocalizationCoordinator(
        instance_id="Map:A",
        strategy_a=strategy_a,
        strategy_b=strategy_b,
        reference=SimpleNamespace(wall_layer=np.ones((16, 16), dtype=np.uint8)),
        registration_validator=RegistrationValidator(min_support_frames=1),
    )
    coordinator.start()
    coordinator.accept_anchor(PositionAnchor((10, 10), "Map:A", 100, "memory"))

    result = coordinator.ingest(_evidence())

    assert result.status == "confirmed"
    assert result.source == "multiframe_strategy_b"


def _registration(position=(10.0, 10.0)):
    return AbsoluteRegistration(
        LocalizationResult(position, 0.9, source="global", registration_valid=True),
        SimilarityTransform2D(0.0, False, 1.0, (6.0, 6.0)),
        0.0,
        "Map:A",
    )


def test_tracking_runs_periodic_local_correction_even_when_f2f_succeeds():
    calls = []

    class Corrector:
        def correct(self, **kwargs):
            calls.append(kwargs)
            return LocalCorrection(
                True,
                (12.0, 10.0),
                SimilarityTransform2D(0.0, False, 1.0, (8.0, 6.0)),
                np.eye(2),
                None,
                "corrected",
                SearchBounds(3, 3),
                {"objective": 0.2},
            )

    coordinator = MultiframeLocalizationCoordinator(
        instance_id="Map:A",
        reference=np.ones((20, 20), dtype=np.uint8),
        local_corrector=Corrector(),
        correction_policy=LocalCorrectionPolicy(min_distance=0.1, max_interval_ms=10_000),
    )
    coordinator.start()
    coordinator.accept_anchor(PositionAnchor((10, 10), "Map:A", 100, "memory"))
    coordinator.confirm(_registration(), (10, 10), now_ms=100)

    result = coordinator.ingest(_evidence(2))

    assert calls
    assert result.source == "visual_local_correction"
    assert result.status == "confirmed"
    assert coordinator.registration_version == 2


def test_local_correction_failures_degrade_before_starting_recovery():
    class RejectingCorrector:
        def correct(self, **kwargs):
            return LocalCorrection(
                False,
                None,
                None,
                None,
                None,
                "shape_quality",
                SearchBounds(3, 3),
                {},
            )

    coordinator = MultiframeLocalizationCoordinator(
        instance_id="Map:A",
        reference=np.ones((20, 20), dtype=np.uint8),
        local_corrector=RejectingCorrector(),
        correction_policy=LocalCorrectionPolicy(min_distance=0.1, max_interval_ms=10_000),
        max_correction_failures=2,
    )
    coordinator.start()
    coordinator.accept_anchor(PositionAnchor((10, 10), "Map:A", 100, "memory"))
    coordinator.confirm(_registration(), (10, 10), now_ms=100)

    first = coordinator.ingest(_evidence(2))
    second = coordinator.ingest(_evidence(3))

    assert first.status == "predicted"
    assert second.status == "recovering"
    assert coordinator.phase is LocalizationPhase.RECOVERING
    assert coordinator.recovery_revision == 1
