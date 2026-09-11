import numpy as np

from core.localization.map_runtime import MapRuntime


def test_runtime_builds_distance_field_and_metadata():
    walls = np.zeros((20, 30), dtype=np.uint8)
    walls[10, 10] = 255
    runtime = MapRuntime.from_wall_layer(walls, map_id="m1", map_version="v2")
    assert runtime.map_id == "m1"
    assert runtime.map_version == "v2"
    assert runtime.distance_field[10, 10] == 0
    assert runtime.distance_field[10, 11] > 0


def test_tile_is_clipped_and_returns_origin():
    runtime = MapRuntime.from_wall_layer(np.zeros((10, 12), dtype=np.uint8), tile_size=8)
    wall, distance, origin = runtime.tile(0, 0)
    assert wall.shape == distance.shape
    assert origin == (0, 0)
