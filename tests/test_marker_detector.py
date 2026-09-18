import numpy as np
from auto_modules.core.perception.models import CoordinateSpace, FrameContext
from auto_modules.core.perception.algorithms.color import ColorRegionDetector
from auto_modules.core.localization.marker_detector import MarkerSetDetector


def detectors():
    return MarkerSetDetector({
        'A1': ColorRegionDetector('player', {'hue_min': 0, 'hue_max': 5, 'saturation_min': 200}),
        'A2': ColorRegionDetector('player', {'hue_min': 55, 'hue_max': 65, 'saturation_min': 200})})


def test_color_identity_survives_crossing():
    detector = detectors()
    for red_x, green_x in [(10, 40), (40, 10)]:
        image = np.zeros((60, 60, 3), np.uint8)
        image[10:15, red_x:red_x+5] = (0, 0, 255)
        image[20:25, green_x:green_x+5] = (0, 255, 0)
        result = detector.detect(FrameContext(image, coordinate_space=CoordinateSpace.MINIMAP))
        assert result['A1'].center[0] == red_x + 2.5
        assert result['A2'].center[0] == green_x + 2.5


def test_ambiguous_same_color_is_missing_not_guessed():
    image = np.zeros((60, 60, 3), np.uint8)
    image[10:15, 10:15] = image[30:35, 30:35] = (0, 0, 255)
    result = detectors().detect(FrameContext(image, coordinate_space=CoordinateSpace.MINIMAP))
    assert result['A1'] is None
    assert result['A2'] is None
