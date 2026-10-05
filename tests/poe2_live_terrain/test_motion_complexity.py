import numpy as np

from auto_modules.features.poe2.live_terrain.experimental.multiplayer_follow.complexity import (
    ComplexityState,
    LocalComplexityClassifier,
)
from auto_modules.features.poe2.live_terrain.experimental.multiplayer_follow.motion_models import MotionObservation
from auto_modules.features.poe2.live_terrain.experimental.multiplayer_follow.motion_snapshot import build_motion_snapshot


def _snapshot(*, clearance=20.0, route=((20.0, 20.0), (80.0, 20.0)), unknown=None, age=10, confidence=0.95, peer=None):
    walls = np.zeros((100, 100), dtype=np.uint8)
    distances = np.full((100, 100), clearance, dtype=np.float32)
    observation = MotionObservation(
        role_key="device-a:p1",
        position=(20.0, 20.0),
        target=(80.0, 20.0),
        captured_at_ms=1000,
        frame_age_ms=age,
        confidence=confidence,
        map_version="map:v1",
        registration_version=1,
        peer_position=peer,
    )
    return build_motion_snapshot(
        observation=observation,
        wall_map=walls,
        distance_field=distances,
        route=route,
        target=(80.0, 20.0),
        peer_position=peer,
        unknown_mask=unknown,
    )


def test_open_room_is_open_and_exposes_component_scores():
    decision = LocalComplexityClassifier().classify(_snapshot())
    assert decision.state is ComplexityState.OPEN
    assert decision.features.clearance_quality > 0.8
    assert decision.features.visibility_quality > 0.8
    assert 0.0 <= decision.score <= 1.0
    assert "c_p10" in decision.diagnostics


def test_narrow_route_is_constrained_even_if_aggregate_score_is_low():
    decision = LocalComplexityClassifier(hard_clearance=3.0).classify(
        _snapshot(clearance=2.0)
    )
    assert decision.state is ComplexityState.CONSTRAINED
    assert decision.diagnostics["hard_clearance"] is True


def test_stale_or_unknown_observation_is_unknown():
    stale = LocalComplexityClassifier().classify(_snapshot(age=900))
    assert stale.state is ComplexityState.UNKNOWN
    unknown = np.zeros((100, 100), dtype=bool)
    unknown[10:80, 10:80] = True
    decision = LocalComplexityClassifier(unknown_ratio_threshold=0.2).classify(
        _snapshot(unknown=unknown)
    )
    assert decision.state is ComplexityState.UNKNOWN


def test_hysteresis_does_not_toggle_on_one_safe_frame():
    classifier = LocalComplexityClassifier(
        hard_clearance=3.0, enter_constrained_frames=2, leave_constrained_frames=3
    )
    narrow = _snapshot(clearance=2.0)
    open_snapshot = _snapshot(clearance=20.0)
    assert classifier.classify(narrow).state is ComplexityState.CONSTRAINED
    assert classifier.classify(open_snapshot).state is ComplexityState.TRANSITION
    assert classifier.classify(open_snapshot).state is ComplexityState.TRANSITION
    assert classifier.classify(open_snapshot).state is ComplexityState.OPEN
