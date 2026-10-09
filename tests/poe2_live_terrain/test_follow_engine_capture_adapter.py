from __future__ import annotations

import numpy as np
import pytest

from auto_modules.features.poe2.live_terrain.experimental.follow_engine.vision.capture_adapter import (
    EncodedImageCapture,
)
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.vision.dual_observation_processor import (
    decode_image_payload,
)


class _Clock:
    def __init__(self, value: int):
        self.value = value

    def __call__(self) -> int:
        return self.value


class _Provider:
    def __init__(self, image):
        self.image = image

    def __call__(self):
        return self.image


def test_encoded_image_capture_builds_compact_frame_contract():
    image = np.zeros((12, 16, 3), dtype=np.uint8)
    image[2:5, 3:8] = (10, 20, 30)
    capture = EncodedImageCapture(
        _Provider(image), generation=2, map_instance="map-b", clock_ms=_Clock(1234),
    )

    frame = capture.capture()

    assert frame is not None
    assert frame.generation == 2
    assert frame.sequence == 1
    assert frame.captured_at_ms == 1234
    assert frame.map_instance == "map-b"
    decoded = decode_image_payload(frame.payload)
    assert decoded.shape == image.shape
    assert np.array_equal(decoded[3, 4], image[3, 4])


def test_empty_provider_frame_does_not_advance_sequence():
    class EmptyThenImage:
        def __init__(self, image):
            self.image = image
            self.calls = 0

        def __call__(self):
            self.calls += 1
            return None if self.calls == 1 else self.image

    capture = EncodedImageCapture(
        EmptyThenImage(np.zeros((4, 4, 3), dtype=np.uint8)),
        generation=1,
        map_instance="map-a",
        clock_ms=_Clock(1),
    )
    assert capture.capture() is None
    assert capture.capture() is not None
    assert capture.capture().sequence == 2


@pytest.mark.parametrize("image", [np.zeros((0, 4, 3), dtype=np.uint8), np.zeros((4, 4), dtype=np.uint8)])
def test_invalid_provider_image_is_rejected(image):
    capture = EncodedImageCapture(_Provider(image), generation=1, map_instance="map-a")
    with pytest.raises(ValueError, match="non-empty BGR image"):
        capture.capture()


def test_capture_configuration_is_validated():
    with pytest.raises(ValueError, match="image_format"):
        EncodedImageCapture(_Provider(np.zeros((4, 4, 3), dtype=np.uint8)), generation=1, map_instance="map-a", image_format=".bmp")
