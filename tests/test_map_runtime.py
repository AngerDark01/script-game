import numpy as np
import pytest

from auto_modules.core.localization.map_runtime import MapRuntime


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


def test_npz_uses_existing_active_version_catalog(tmp_path):
    from auto_modules.core.map_editing.version_storage import save_new_wall_version
    walls = np.zeros((16, 16), np.uint8)
    np.savez(tmp_path / 'map_data.npz', wall_layer=walls)
    edited = walls.copy()
    edited[5, 7] = 255
    version = save_new_wall_version(tmp_path, edited, parent_version=None)
    runtime = MapRuntime.from_npz(tmp_path / 'map_data.npz')
    assert runtime.map_version == version.id
    assert runtime.wall_layer[5, 7] == 1
    assert runtime.distance_field[5, 7] == 0


def test_bounds_and_immutable_snapshot():
    runtime = MapRuntime.from_wall_layer(np.zeros((10, 12), np.uint8), tile_size=8)
    with pytest.raises(ValueError):
        runtime.tile(-1, 0)
    with pytest.raises(ValueError):
        runtime.wall_layer[0, 0] = 1
    assert np.isinf(runtime.distance_field).all()
    with pytest.raises(ValueError):
        MapRuntime.from_wall_layer(np.zeros((10, 12)), tile_size=0)
