import numpy as np
from auto_modules.core.localization.map_runtime import MapRuntime
from auto_modules.core.localization.local_matcher import LocalMapMatcher


def test_bounded_chamfer_recovers_origin():
    walls = np.zeros((100, 120), np.uint8)
    walls[30:46, 40] = 255
    walls[45, 40:55] = 255
    walls[32:40, 51] = 255
    template = walls[25:50, 35:60]
    matcher = LocalMapMatcher(MapRuntime.from_wall_layer(walls))
    result = matcher.match(template, origin=(30, 23), radius=12)
    assert result.valid
    assert result.frame_origin_global == (35., 25.)


def test_failed_local_search_never_falls_back_to_full_map():
    walls = np.zeros((100, 120), np.uint8)
    walls[80:90, 80:90] = 255
    matcher = LocalMapMatcher(MapRuntime.from_wall_layer(walls))
    assert not matcher.match(np.ones((10, 10), np.uint8), origin=(0, 0), radius=3).valid
    assert not matcher.match(np.zeros((10, 10), np.uint8), origin=(0, 0), radius=3).valid


def test_identical_candidate_regions_are_rejected():
    walls = np.zeros((70, 90), np.uint8)
    walls[20:30, 20] = walls[29, 20:30] = 255
    walls[20:30, 50] = walls[29, 50:60] = 255
    matcher = LocalMapMatcher(MapRuntime.from_wall_layer(walls))
    assert not matcher.match(walls[15:35, 15:35], origin=(30, 15), radius=20).valid


def test_tiny_uniform_search_cannot_claim_unique_match():
    matcher = LocalMapMatcher(MapRuntime.from_wall_layer(np.ones((20, 20), np.uint8)))
    for radius in (0, 1, 2):
        assert not matcher.match(np.ones((5, 5), np.uint8), origin=(7, 7), radius=radius).valid
