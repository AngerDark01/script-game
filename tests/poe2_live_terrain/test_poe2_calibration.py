import pytest

from auto_modules.features.poe2.live_terrain.calibration import Poe2Calibration


def test_calibration_maps_local_position_with_scale_offset_and_y_flip():
    calibration = Poe2Calibration(
        minimap_size=(100, 80), scale=(2, 3), offset=(10, 20), invert_y=True
    )
    assert calibration.local_to_reference((4, 5)) == (18.0, 242.0)


def test_calibration_rejects_invalid_geometry():
    with pytest.raises(ValueError):
        Poe2Calibration(minimap_size=(0, 10))
    with pytest.raises(ValueError):
        Poe2Calibration(minimap_size=(10, 10), scale=(0, 1))
