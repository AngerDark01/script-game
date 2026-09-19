import numpy as np

from auto_modules.features.poe2.live_terrain.contracts import CaptureMetadata, TerrainSnapshot
from auto_modules.features.poe2.live_terrain.terrain_reference import build_reference


def _snapshot(cell_state, known_mask):
    height, width = cell_state.shape
    metadata = CaptureMetadata("Area", "hash", "Area:hash", width, height, "2026-09-19T00:00:00+00:00")
    return TerrainSnapshot(
        metadata,
        np.zeros((height, width), dtype=np.uint8),
        cell_state.astype(np.int8),
        known_mask.astype(np.uint8),
        np.zeros((height, width), dtype=np.uint8),
        np.zeros((height, width), dtype=np.uint8),
    )


def test_reference_separates_walkable_cells_from_unknown_and_blocked_cells():
    reference = build_reference(_snapshot(
        np.array([[1, 0, -1], [1, 1, 0]]),
        np.array([[1, 1, 0], [1, 1, 1]]),
    ))
    assert reference.walkable_mask.tolist() == [[True, False, False], [True, True, False]]
    assert reference.wall_layer.dtype == np.uint8
    assert reference.wall_layer[0, 0] == 0
    assert reference.wall_layer[0, 1] == 255
    assert reference.explored_map[0, 2] == 0


def test_reference_arrays_are_immutable():
    reference = build_reference(_snapshot(np.ones((1, 1)), np.ones((1, 1))))
    assert reference.wall_layer.flags.writeable is False
