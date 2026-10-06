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
