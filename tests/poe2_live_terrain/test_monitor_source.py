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


def test_circle_capture_masks_pixels_outside_effective_radius():
    class OnesCapture(FakeCapture):
        def capture(self, x, y, width, height):
            self.calls.append((x, y, width, height))
            return np.ones((height, width, 3), dtype=np.uint8)

    backend = OnesCapture()
    frame = MonitorFrameSource(backend).capture(
        MonitorBinding(CaptureRect(0, 0, 5, 5)),
        shape="circle",
        radius=2.0,
    )

    assert frame[2, 2].tolist() == [1, 1, 1]
    assert frame[0, 0].tolist() == [0, 0, 0]
