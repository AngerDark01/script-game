from types import SimpleNamespace

import cv2
import numpy as np

from auto_modules.core.localization import LocalizationResult
from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.models import (
    AbsoluteRegistration,
    HybridFrame,
    SimilarityTransform2D,
)
from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.similarity_search import (
    inverse_transform_local_point, transform_local_point,
)
from auto_modules.features.poe2.live_terrain.experimental.multiplayer_localization.dual_motion import (
    DualVisualTracker, RolePredictionHint,
)
from auto_modules.features.poe2.live_terrain.experimental.multiplayer_localization.models import (
    DualFirstFrameResult,
    PlayerLocalization,
    PlayerMarkerCandidate,
)


def _walls():
    image = np.zeros((96, 96), dtype=np.uint8)
    cv2.line(image, (12, 15), (12, 75), 255, 2)
    cv2.line(image, (12, 75), (80, 75), 255, 2)
    cv2.line(image, (45, 25), (73, 25), 255, 2)
    return image


def _frame(walls, number):
    return HybridFrame(number, number * 33, walls, (48, 48))


def _candidate(name, x, y):
    return PlayerMarkerCandidate(name, (x, y), confidence=0.9)


def _registered(walls, *, angle=0, reflect=False):
    transform = SimilarityTransform2D(angle, reflect, 1.0, (200.0, 300.0))
    registration = AbsoluteRegistration(
        LocalizationResult((225.0, 330.0), 0.9), transform, 1.0, "instance-1"
    )
    players = {
        name: PlayerLocalization(name, name, point, point, point, 0.0, 0.9, True)
        for name, point in {"a": (25.0, 30.0), "b": (65.0, 55.0)}.items()
    }
    return _frame(walls, 1), DualFirstFrameResult("accepted", "ok", registration, players)


def test_shared_viewport_motion_and_independent_player_motion():
    walls = _walls()
    initial, result = _registered(walls)
    tracker = DualVisualTracker()
    tracker.start(initial, result)
    shifted = cv2.warpAffine(walls, np.float32([[1, 0, 5], [0, 1, -3]]), (96, 96))
    state = tracker.tick(_frame(shifted, 2), (_candidate("x", 30, 27), _candidate("y", 74, 52)))
    assert state.status == "tracking"
    assert np.allclose(state.players["a"], (225, 330), atol=1.5)
    assert np.allclose(state.players["b"], (269, 355), atol=1.5)
    assert state.recovery_requested is False


def test_first_live_frame_refreshes_stale_registration_when_both_markers_match():
    initial, result = _registered(_walls())
    tracker = DualVisualTracker(marker_hold_ms=2000)
    tracker.start(initial, result)

    state = tracker.tick(
        _frame(_walls(), 350),
        (_candidate("a", 25, 30), _candidate("b", 65, 55)),
    )

    assert state.status == "tracking"
    assert not state.recovery_requested
    assert all(item["visible"] and item["age_ms"] == 0
               for item in state.diagnostics["role_observations"].values())


def test_stale_registration_without_live_markers_still_requests_recovery():
    initial, result = _registered(_walls())
    tracker = DualVisualTracker(marker_hold_ms=2000)
    tracker.start(initial, result)

    state = tracker.tick(_frame(_walls(), 350), ())

    assert state.status == "recovery_required"
    assert state.recovery_requested


def test_one_missing_marker_keeps_predicted_position_during_identity_grace():
    initial, result = _registered(_walls())
    tracker = DualVisualTracker()
    tracker.start(initial, result)
    state = tracker.tick(_frame(_walls(), 2), (_candidate("only-a", 27, 30),))
    assert state.status == "degraded"
    assert state.players["a"] is not None
    assert state.players["b"] is not None
    assert state.recovery_requested is False


def test_one_missing_marker_eventually_requests_recovery_independently():
    initial, result = _registered(_walls())
    tracker = DualVisualTracker(marker_dropout_grace=2, marker_hold_ms=70, max_failures=2)
    tracker.start(initial, result)

    first = tracker.tick(_frame(_walls(), 2), (_candidate("only-a", 27, 30),))
    second = tracker.tick(_frame(_walls(), 3), (_candidate("only-a", 27, 30),))
    third = tracker.tick(_frame(_walls(), 4), (_candidate("only-a", 27, 30),))

    assert first.players["b"] is not None
    assert second.players["b"] is not None
    assert third.status == "recovery_required"
    assert third.recovery_requested


def test_first_nonempty_refresh_frame_gets_stationary_warmup(monkeypatch):
    initial, result = _registered(_walls())
    tracker = DualVisualTracker(matcher=SimpleNamespace(match=lambda *args, **kwargs: SimpleNamespace(valid=False)))
    tracker.start(initial, result)
    monkeypatch.setattr(
        "auto_modules.features.poe2.live_terrain.experimental.multiplayer_localization.dual_motion.estimate_bounded_displacement",
        lambda *_args, **_kwargs: SimpleNamespace(accepted=False, shift=None, quality=0.0, reason="transient"),
    )
    state = tracker.tick(_frame(_walls(), 2), ())
    assert state.status == "degraded"
    assert state.diagnostics["warmup_assumed_stationary"] is True


def test_blank_first_refresh_frame_does_not_bypass_recovery():
    initial, result = _registered(_walls())
    tracker = DualVisualTracker(matcher=SimpleNamespace(match=lambda *args, **kwargs: SimpleNamespace(valid=False)), max_failures=2)
    tracker.start(initial, result)
    state = tracker.tick(_frame(np.zeros_like(_walls()), 2), ())
    assert state.status == "degraded"
    assert state.diagnostics.get("warmup_assumed_stationary") is not True


def test_wall_failure_uses_bounded_correction_before_one_shot_recovery():
    initial, result = _registered(_walls())
    matcher = SimpleNamespace(match=lambda *args, **kwargs: SimpleNamespace(valid=False))
    tracker = DualVisualTracker(matcher=matcher, max_failures=2)
    tracker.start(initial, result)
    blank = np.zeros((96, 96), dtype=np.uint8)
    first = tracker.tick(_frame(blank, 2), ())
    second = tracker.tick(_frame(blank, 3), ())
    third = tracker.tick(_frame(blank, 4), ())
    assert first.status == "degraded"
    assert first.players == {"a": None, "b": None}
    assert second.status == "recovery_required" and second.recovery_requested
    assert third.status == "recovery_required" and not third.recovery_requested


def test_reflected_rotation_uses_first_frame_transform_for_both_players():
    initial, result = _registered(_walls(), angle=90, reflect=True)
    tracker = DualVisualTracker()
    tracker.start(initial, result)
    state = tracker.tick(_frame(_walls(), 2), (_candidate("x", 25, 30), _candidate("y", 65, 55)))
    assert state.status == "tracking"
    assert state.players["a"] != state.players["b"]
    assert not np.allclose(state.players["a"], (225, 330), atol=1.5)


def test_prediction_hint_inverse_matches_registration_geometry():
    for angle in (0, 45, 137, 270):
        for reflect in (False, True):
            kwargs = dict(angle=angle, reflect_horizontal=reflect, scale=0.75,
                          translation=(200.0, 300.0))
            native = transform_local_point((96, 96), (28.5, 62.25), **kwargs)
            local = inverse_transform_local_point((96, 96), native, **kwargs)
            np.testing.assert_allclose(local, (28.5, 62.25), atol=1e-8)


def test_local_correction_can_recover_wall_shift_without_memory_read():
    initial, result = _registered(_walls())
    calls = []

    def match(_walls, **kwargs):
        calls.append(kwargs)
        return SimpleNamespace(valid=True, frame_origin_global=(204.0, 297.0))

    tracker = DualVisualTracker(matcher=SimpleNamespace(match=match), correction_frame_interval=1)
    tracker.start(initial, result)
    state = tracker.tick(_frame(_walls(), 2), (_candidate("a", 25, 30), _candidate("b", 65, 55)))
    assert state.status == "tracking"
    assert state.correction_attempted
    assert state.transform.translation == (204.0, 297.0)
    assert len(calls) == 1
    assert calls[0]["radius"] == 48.0


def test_local_correction_uses_first_player_anchor_instead_of_frame_center(monkeypatch):
    initial, result = _registered(_walls())
    calls = []

    def transform_feature_probe(mask, local_player, **kwargs):
        calls.append(local_player)
        return SimpleNamespace(mask=mask)

    monkeypatch.setattr(
        "auto_modules.features.poe2.live_terrain.experimental.multiplayer_localization.dual_motion.transform_feature",
        transform_feature_probe,
    )
    tracker = DualVisualTracker(
        matcher=SimpleNamespace(
            match=lambda *_args, **_kwargs: SimpleNamespace(
                valid=True, frame_origin_global=(200.0, 300.0),
            )
        ),
        correction_frame_interval=1,
    )
    tracker.start(initial, result)
    tracker.tick(
        _frame(_walls(), 2),
        (_candidate("a", 25, 30), _candidate("b", 65, 55)),
    )

    assert calls == [(25.0, 30.0)]


def test_close_markers_do_not_force_an_unreliable_identity_assignment():
    initial, result = _registered(_walls())
    tracker = DualVisualTracker(max_marker_step=70, identity_margin=5)
    tracker.start(initial, result)
    state = tracker.tick(_frame(_walls(), 2), (_candidate("left", 45, 42), _candidate("right", 45, 43)))
    assert state.reason == "markers_ambiguous"
    assert state.status == "degraded"
    assert all(point is not None for point in state.players.values())
    assert state.diagnostics["marker_dropout_failures"] == 1
    assert not state.recovery_requested


def test_marker_dropout_grace_is_bounded_and_then_requests_recovery():
    initial, result = _registered(_walls())
    tracker = DualVisualTracker(marker_dropout_grace=2, marker_hold_ms=70, max_failures=2)
    tracker.start(initial, result)

    first = tracker.tick(_frame(_walls(), 2), ())
    second = tracker.tick(_frame(_walls(), 3), ())
    third = tracker.tick(_frame(_walls(), 4), ())

    assert first.status == "degraded"
    assert second.status == "degraded"
    assert third.status == "recovery_required"
    assert third.recovery_requested


def test_marker_loss_uses_per_role_time_budget_when_walls_are_tracked():
    initial, result = _registered(_walls())
    tracker = DualVisualTracker()
    tracker.start(initial, result)
    for number in (2, 3, 4):
        state = tracker.tick(_frame(_walls(), number), (_candidate("a", 25, 30),))
    assert state.status == "degraded"
    assert not state.recovery_requested
    assert state.diagnostics["role_observations"]["a"]["visible"]
    assert not state.diagnostics["role_observations"]["b"]["visible"]
    assert state.diagnostics["role_observations"]["b"]["available"]

    expired = tracker.tick(_frame(_walls(), 70), (_candidate("a", 25, 30),))
    assert expired.status == "recovery_required"
    assert expired.recovery_requested and expired.recovery_revision == 1


def test_command_hint_keeps_hidden_role_alive_and_reacquires_after_motion():
    initial, result = _registered(_walls())
    tracker = DualVisualTracker(marker_hold_ms=70, max_failures=2)
    tracker.start(initial, result)
    native_b = (285.0, 355.0)
    hint = lambda at: {"b": RolePredictionHint(native_b, 3.0, at)}
    for number in (2, 3, 4):
        state = tracker.tick(
            _frame(_walls(), number), (_candidate("a", 25, 30),),
            prediction_hints=hint(number * 33),
        )
    assert state.status == "degraded" and not state.recovery_requested
    assert state.players["b"] == native_b
    assert not state.diagnostics["role_observations"]["b"]["visible"]
    first = tracker.tick(
        _frame(_walls(), 5), (_candidate("a", 25, 30), _candidate("b", 85, 55)),
        prediction_hints=hint(165),
    )
    assert first.status == "degraded"
    second = tracker.tick(
        _frame(_walls(), 6), (_candidate("a", 25, 30), _candidate("b", 85, 55)),
        prediction_hints=hint(198),
    )
    assert second.status == "tracking"
    assert second.diagnostics["role_observations"]["b"]["visible"]


def test_command_hint_does_not_accept_unrelated_marker_single_frame():
    initial, result = _registered(_walls())
    tracker = DualVisualTracker(marker_hold_ms=70, max_failures=2)
    tracker.start(initial, result)
    for number in (2, 3, 4):
        tracker.tick(_frame(_walls(), number), (_candidate("a", 25, 30),),
                     prediction_hints={"b": RolePredictionHint((285, 355), 3, number * 33)})
    state = tracker.tick(
        _frame(_walls(), 5), (_candidate("a", 25, 30), _candidate("landmark", 85, 55)),
        prediction_hints={"b": RolePredictionHint((285, 355), 3, 165)},
    )
    assert not state.diagnostics["role_observations"]["b"]["visible"]


def test_stale_or_unbounded_prediction_hint_cannot_suppress_recovery():
    initial, result = _registered(_walls())
    tracker = DualVisualTracker(marker_hold_ms=70, max_failures=2)
    tracker.start(initial, result)
    state = tracker.tick(
        _frame(_walls(), 4), (_candidate("a", 25, 30),),
        prediction_hints={"b": RolePredictionHint((285, 355), 3, -1000)},
    )
    assert state.recovery_requested

    tracker = DualVisualTracker(marker_hold_ms=70, max_failures=2)
    tracker.start(initial, result)
    state = tracker.tick(
        _frame(_walls(), 4), (_candidate("a", 25, 30),),
        prediction_hints={"b": RolePredictionHint((285, 355), 13, 132)},
    )
    assert state.recovery_requested


def test_command_hint_never_overrides_failed_wall_registration(monkeypatch):
    initial, result = _registered(_walls())
    tracker = DualVisualTracker(max_failures=2)
    tracker.start(initial, result)
    monkeypatch.setattr(
        "auto_modules.features.poe2.live_terrain.experimental.multiplayer_localization.dual_motion.estimate_bounded_displacement",
        lambda *_args, **_kwargs: SimpleNamespace(
            accepted=False, shift=None, quality=0.0, reason="wall_missing",
        ),
    )
    blank = _frame(np.zeros_like(_walls()), 2)
    hint = {"b": RolePredictionHint((265, 355), 2, blank.captured_at_ms)}
    first = tracker.tick(blank, (), prediction_hints=hint)
    second = tracker.tick(_frame(np.zeros_like(_walls()), 3), (), prediction_hints={
        "b": RolePredictionHint((265, 355), 2, 99),
    })
    assert first.status == "degraded"
    assert second.recovery_requested


def test_marker_reappearance_needs_consecutive_frames_after_dropout():
    initial, result = _registered(_walls())
    tracker = DualVisualTracker()
    tracker.start(initial, result)
    for number in (2, 3, 4):
        tracker.tick(_frame(_walls(), number), (_candidate("a", 25, 30),))

    first = tracker.tick(_frame(_walls(), 5), (_candidate("a", 25, 30), _candidate("b", 66, 55)))
    assert first.status == "degraded"
    assert not first.diagnostics["role_observations"]["b"]["visible"]
    second = tracker.tick(_frame(_walls(), 6), (_candidate("a", 25, 30), _candidate("b", 66, 55)))
    assert second.status == "tracking"
    assert second.diagnostics["role_observations"]["b"]["visible"]


def test_hidden_marker_accumulates_viewport_motion_before_reappearing():
    walls = _walls()
    initial, result = _registered(walls)
    tracker = DualVisualTracker()
    tracker.start(initial, result)
    one_shift = cv2.warpAffine(walls, np.float32([[1, 0, 5], [0, 1, -3]]), (96, 96))
    two_shifts = cv2.warpAffine(walls, np.float32([[1, 0, 10], [0, 1, -6]]), (96, 96))
    tracker.tick(_frame(one_shift, 2), (_candidate("a", 30, 27),))
    state = tracker.tick(_frame(two_shifts, 3), (_candidate("a", 35, 24), _candidate("b", 75, 49)))
    assert np.allclose(state.players["b"], (265, 355), atol=1.5)


def test_extra_high_confidence_same_color_candidate_does_not_hide_other_role():
    initial, result = _registered(_walls())
    tracker = DualVisualTracker()
    tracker.start(initial, result, (
        PlayerMarkerCandidate("a", (25, 30), color_features={"identity_hint": "red"}),
        PlayerMarkerCandidate("b", (65, 55), color_features={"identity_hint": "blue"}),
    ))
    state = tracker.tick(_frame(_walls(), 2), (
        PlayerMarkerCandidate("blue-noise", (10, 10), confidence=0.99,
                              color_features={"identity_hint": "blue"}),
        PlayerMarkerCandidate("blue-real", (65, 55), confidence=0.90,
                              color_features={"identity_hint": "blue"}),
        PlayerMarkerCandidate("red-real", (25, 30), confidence=0.70,
                              color_features={"identity_hint": "red"}),
    ))
    assert state.status == "tracking"
    assert state.diagnostics["visible_identities"] == ("a", "b")


def test_distinct_color_profiles_preserve_identity_during_crossing():
    initial, result = _registered(_walls())
    tracker = DualVisualTracker(max_marker_step=70)
    tracker.start(
        initial, result,
        (
            PlayerMarkerCandidate("a", (25, 30), color_features={"identity_hint": "red"}),
            PlayerMarkerCandidate("b", (65, 55), color_features={"identity_hint": "blue"}),
        ),
    )
    state = tracker.tick(
        _frame(_walls(), 2),
        (
            PlayerMarkerCandidate("new-blue", (30, 30), color_features={"identity_hint": "blue"}),
            PlayerMarkerCandidate("new-red", (58, 55), color_features={"identity_hint": "red"}),
        ),
    )
    assert state.players["a"] == (258.0, 355.0)
    assert state.players["b"] == (230.0, 330.0)


def test_local_correction_reconstructs_screen_motion_for_marker_association():
    initial, result = _registered(_walls())
    matcher = SimpleNamespace(match=lambda *args, **kwargs: SimpleNamespace(
        valid=True, frame_origin_global=(204.0, 297.0),
    ))
    tracker = DualVisualTracker(matcher=matcher)
    tracker.start(initial, result)
    state = tracker.tick(
        _frame(np.zeros((96, 96), dtype=np.uint8), 2),
        (_candidate("a", 21, 33), _candidate("b", 61, 58)),
    )
    assert state.status == "tracking"
    assert state.correction_attempted
    assert state.players["a"] == (225.0, 330.0)
    assert state.players["b"] == (265.0, 355.0)
