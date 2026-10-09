from __future__ import annotations

import pickle

import numpy as np

from auto_modules.core.spatial.monitor_binding import CaptureRect, MonitorBinding
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.vision.poe2_monitor_capture import (
    Poe2WallMaskExtractor,
    SpawnSafePoe2MonitorCapture,
)


class FakeBackend:
    def __init__(self):
        self.calls = []
        self.closed = 0

    def capture(self, left, top, width, height):
        self.calls.append((left, top, width, height))
        return np.full((height, width, 3), 200, dtype=np.uint8)

    def close(self):
        self.closed += 1


def _binding():
    return MonitorBinding(CaptureRect(10, 20, 8, 6))


def test_monitor_capture_is_pickle_safe_and_creates_backend_lazily():
    created = []

    def factory():
        backend = FakeBackend()
        created.append(backend)
        return backend

    capture = SpawnSafePoe2MonitorCapture(_binding(), backend_factory=factory)
    # Direct construction remains useful in unit tests; the production default
    # is a top-level factory that is safe to pickle under Windows spawn.
    payload = pickle.dumps(SpawnSafePoe2MonitorCapture(_binding()))
    assert pickle.loads(payload).binding == _binding()
    first = capture()
    second = capture()
    assert first.shape == (6, 8, 3)
    assert second.shape == (6, 8, 3)
    assert len(created) == 1
    assert created[0].calls == [(10, 20, 8, 6), (10, 20, 8, 6)]
    capture.close()
    assert created[0].closed == 1


def test_poe2_wall_extractor_returns_shape_matched_mask_without_marker_clear():
    image = np.zeros((12, 16, 3), dtype=np.uint8)
    image[4:8, 5:11] = 220
    mask = Poe2WallMaskExtractor({"transparent_mode": False})(image)
    assert mask.shape == image.shape[:2]
    assert mask.dtype == np.uint8
    assert set(np.unique(mask)).issubset({0, 255})
