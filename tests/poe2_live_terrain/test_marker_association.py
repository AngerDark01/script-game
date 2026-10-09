from auto_modules.features.poe2.live_terrain.experimental.multiplayer_localization.marker_association import MarkerAssociator
from auto_modules.features.poe2.live_terrain.experimental.multiplayer_localization.models import PlayerMarkerCandidate


def _candidate(name, x, y, hint):
    return PlayerMarkerCandidate(name, (x, y), confidence=1.0, color_features={"identity_hint": hint})


def test_delayed_frame_expands_gate_using_velocity():
    associator = MarkerAssociator(base_gate=45, max_gate=180)
    result = associator.assign(
        [_candidate("p1", 100, 0, "orange")],
        {"role": (0, 0)},
        identity_hints={"role": "orange"},
        velocities={"role": (30, 0)},
        elapsed_ms={"role": 2000},
    )
    assert result.assignment == {"role": (100.0, 0.0)}
    assert result.diagnostics["gates"]["role"] == 105.0


def test_identity_hint_falls_back_to_geometry_when_it_is_the_only_candidate():
    associator = MarkerAssociator(base_gate=45)
    result = associator.assign(
        [_candidate("p1", 1, 1, "blue")],
        {"role": (0, 0)},
        identity_hints={"role": "orange"},
    )
    assert result.assignment == {"role": (1.0, 1.0)}
    assert not result.ambiguous
    assert result.diagnostics["identity_hint_fallback"]


def test_pair_geometry_prefers_assignment_that_preserves_role_spacing():
    associator = MarkerAssociator(base_gate=30, max_gate=100, margin=0.1)
    # Both candidates are individually plausible for both roles.  The pair
    # spacing identifies the stable assignment even when colour hints collide.
    result = associator.assign(
        [_candidate("left", 10, 0, "same"), _candidate("right", 30, 0, "same")],
        {"p1": (10, 0), "p2": (30, 0)},
        identity_hints={"p1": "orange", "p2": "orange"},
        pair_geometry=True,
    )
    assert result.assignment == {"p1": (10.0, 0.0), "p2": (30.0, 0.0)}
    option = result.diagnostics["options"][0]
    assert option["pair_distance_error"] == 0.0
    assert option["pair_geometry_score"] == 1.0


def test_single_high_confidence_far_candidate_requires_two_frames_then_reanchors():
    associator = MarkerAssociator(base_gate=20, max_gate=40)
    candidate = _candidate("p1", 100, 0, "orange")
    first = associator.assign(
        [candidate], {"role": (0, 0)}, identity_hints={"role": "orange"}
    )
    assert first.assignment == {}
    assert first.diagnostics["single_candidate_pending"] is True
    second = associator.assign(
        [_candidate("p1-next", 101, 0, "orange")],
        {"role": (0, 0)}, identity_hints={"role": "orange"},
    )
    assert second.assignment == {"role": (101.0, 0.0)}
    assert second.diagnostics["single_candidate_confirmed"] is True


def test_large_area_candidate_is_rejected_as_color_interference():
    associator = MarkerAssociator(base_gate=20, large_marker_area=48)
    large = PlayerMarkerCandidate(
        "noise", (1, 1), confidence=1.0, area=80.0,
        color_features={"identity_hint": "orange"},
    )
    result = associator.assign([large], {"role": (1, 1)}, identity_hints={"role": "orange"})
    assert result.assignment == {}
    assert result.diagnostics["filtered_large_area_ids"] == ("noise",)


def test_two_roles_confirm_their_own_far_candidates_without_identity_swap():
    associator = MarkerAssociator(base_gate=20, max_gate=40)
    candidates = [_candidate("orange", 100, 0, "orange"), _candidate("blue", 200, 0, "blue")]
    predicted = {"p1": (200, 0), "p2": (100, 0)}
    hints = {"p1": "orange", "p2": "blue"}
    first = associator.assign(candidates, predicted, identity_hints=hints)
    assert first.assignment == {}
    second = associator.assign(candidates, predicted, identity_hints=hints)
    assert second.assignment == {"p1": (100, 0), "p2": (200, 0)}
    assert set(second.diagnostics["confirmed_roles"]) == {"p1", "p2"}
