import cv2
import numpy as np
from auto_modules.core.localization.phase_tracker import track_scroll


def test_reuses_displacement_with_correct_origin_sign():
    image = np.random.default_rng(4).integers(0, 255, (128, 128), dtype=np.uint8)
    shifted = cv2.warpAffine(image, np.float32([[1, 0, 4], [0, 1, -3]]), (128, 128))
    result = track_scroll(image, shifted, origin=(100, 100), scale=2)
    assert result.valid
    assert np.allclose(result.frame_origin_global, (92, 106), atol=1)


def test_blank_or_mismatched_frames_fail_closed():
    blank = np.zeros((64, 64), np.uint8)
    assert not track_scroll(blank, blank, origin=(0, 0)).valid
    assert not track_scroll(blank, blank[:32], origin=(0, 0)).valid
