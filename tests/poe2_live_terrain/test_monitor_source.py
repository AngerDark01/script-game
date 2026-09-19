import numpy as np

from auto_modules.features.poe2.live_terrain.monitor_source import MonitorFrameSource
from auto_modules.core.spatial.monitor_binding import CaptureRect, MonitorBinding


class FakeCapture:
    def __init__(self):
        self.calls = []

    def capture(self, x, y, width, height):
        self.calls.append((x, y, width, height))
        return np.zeros((height, width, 3), dtype=np.uint8)


def test_capture_uses_poe2_binding_only():
    backend = FakeCapture()
    frame = MonitorFrameSource(backend).capture(MonitorBinding(CaptureRect(5, 7, 32, 24)))
    assert frame.shape == (24, 32, 3)
    assert backend.calls == [(5, 7, 32, 24)]
