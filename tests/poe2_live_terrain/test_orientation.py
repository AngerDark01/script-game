import numpy as np

from auto_modules.features.poe2.live_terrain.orientation import TerrainOrientation
from auto_modules.features.poe2.live_terrain.terrain_reference import TerrainReference


def test_clockwise_rotation_matches_numpy_and_point_coordinates() -> None:
    source = np.arange(6, dtype=np.uint8).reshape(2, 3)
    orientation = TerrainOrientation(rotation=90)

    assert np.array_equal(orientation.transform_array(source), np.rot90(source, -1))
    assert orientation.transformed_shape(source.shape) == (3, 2)
    assert orientation.transform_point((0, 0), source.shape) == (1.0, 0.0)
    assert orientation.transform_point((2, 1), source.shape) == (0.0, 2.0)


def test_rotation_and_mirror_transform_local_delta() -> None:
    orientation = TerrainOrientation(rotation=90, flip_horizontal=True)
    assert orientation.transform_delta((3, 4)) == (4.0, 3.0)


def test_reference_layers_and_dimensions_share_one_orientation() -> None:
    reference = TerrainReference(
        walkable_mask=np.array([[True, False, False], [False, True, False]]),
        wall_layer=np.arange(6, dtype=np.uint8).reshape(2, 3),
        explored_map=np.full((2, 3), 255, dtype=np.uint8),
        width=3,
        height=2,
    )
    transformed = TerrainOrientation(rotation=270).transform_reference(reference)

    assert transformed.shape == (3, 2)
    assert np.array_equal(transformed.wall_layer, np.rot90(reference.wall_layer, 1))
    assert transformed.metadata["orientation"]["rotation"] == 270
