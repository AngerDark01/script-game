import numpy as np

from auto_modules.features.poe2.live_terrain.experimental.multiplayer_localization import (
    inspect_minimap_contact,
)


def test_minimap_contact_reports_wall_ahead_and_open_lateral_side():
    mask = np.zeros((40, 40), dtype=np.uint8)
    mask[20, 18:25] = 255

    result = inspect_minimap_contact(mask, (10, 20), (1, 0))

    assert result.wall_ahead is True
    assert result.wall_distance == 10.0
    assert result.free_left > 0.5
    assert result.free_right > 0.5


def test_minimap_contact_is_neutral_for_zero_command():
    result = inspect_minimap_contact(np.zeros((20, 20), dtype=np.uint8), (10, 10), (0, 0))

    assert result.wall_ahead is False
    assert result.wall_distance is None
    assert result.sampled_pixels == 0


def test_side_wall_beam_is_not_a_blocking_contact_when_centerline_is_open():
    mask = np.zeros((40, 40), dtype=np.uint8)
    # The 3x3 beam around the first lookahead point sees the side wall,
    # while the exact centreline remains free.
    mask[19:22, 15] = 255

    result = inspect_minimap_contact(mask, (10, 20), (1, 0))

    assert result.wall_ahead is True
    assert result.wall_distance == 6.0
    assert result.centerline_wall_distance is None
    assert result.blocking_wall_ahead is False
    assert result.narrow_passage is True


def test_centerline_wall_is_a_blocking_contact():
    mask = np.zeros((40, 40), dtype=np.uint8)
    mask[20, 16:25] = 255

    result = inspect_minimap_contact(mask, (10, 20), (1, 0))

    assert result.blocking_wall_ahead is True
    assert result.centerline_wall_distance == 6.0
    assert result.narrow_passage is False
