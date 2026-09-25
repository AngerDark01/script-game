from __future__ import annotations

import math

import pytest

from auto_modules.features.poe2.live_terrain.player_position import PlayerPositionSample


def test_world_position_converts_to_native_grid():
    sample = PlayerPositionSample.from_world(
        world=(250.0, 500.0, -12.0),
        captured_at="2026-09-22T03:27:56+00:00",
        area_instance="MapFlotsam:BB9AA6DE",
    )

    assert sample.grid == (23.0, 46.0)
    assert sample.world == (250.0, 500.0, -12.0)
    assert sample.area_instance == "MapFlotsam:BB9AA6DE"


def test_world_position_rejects_nonfinite_values():
    with pytest.raises(ValueError, match="finite"):
        PlayerPositionSample.from_world(
            world=(math.nan, 1.0, 2.0),
            captured_at="2026-09-22T03:27:56+00:00",
            area_instance="MapFlotsam:BB9AA6DE",
        )
