import numpy as np

from auto_modules.features.poe2.live_terrain.experimental.multiframe_localization.models import PositionEstimate
from auto_modules.features.poe2.live_terrain.experimental.multiframe_localization.navigation_adapter import NavigationLocalizationAdapter


def test_only_fresh_confirmed_estimate_is_executable():
    adapter = NavigationLocalizationAdapter(max_age_ms=100)
    estimate = PositionEstimate("confirmed", (1, 2), (0, 0), None, (), "Map:A", 1, 2, True, 0, "test", "", {"captured_at_ms": 1000})
    assert adapter.to_observation(estimate, now_ms=1050).executable
    stale = PositionEstimate("predicted", (1, 2), (0, 0), None, (), "Map:A", 1, 2, False, 200, "test", "stale")
    assert not adapter.to_observation(stale, now_ms=1050).executable


def test_navigation_observation_gates_instance_version_and_expands_safety_radius():
    adapter = NavigationLocalizationAdapter(player_radius=2, uncertainty_factor=3, map_error=1)
    estimate = PositionEstimate("confirmed", (1, 2), (0, 0), np.diag([4, 9]), (), "Map:A", 3, 2, True, 0, "test", "", {"captured_at_ms": 1000})
    result = adapter.to_observation(estimate, now_ms=1000, expected_instance_id="Map:A", expected_registration_version=3)
    assert result.executable
    assert result.safety_radius == 12
    mismatch = adapter.to_observation(estimate, now_ms=1000, expected_instance_id="Map:B")
    assert not mismatch.executable
    assert mismatch.reason == "instance_mismatch"


def test_invalid_diagnostic_timestamp_falls_back_to_typed_estimate_age():
    adapter = NavigationLocalizationAdapter(max_age_ms=100)
    estimate = PositionEstimate(
        "confirmed",
        (1, 2),
        (0, 0),
        None,
        (),
        "Map:A",
        1,
        2,
        True,
        150,
        "test",
        "",
        {"captured_at_ms": "invalid"},
    )

    observation = adapter.to_observation(estimate, now_ms=2000)

    assert not observation.executable
    assert observation.metadata["age_ms"] == 150
