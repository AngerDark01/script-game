import unittest

import numpy as np

from core.perception.models import CoordinateSpace
from core.platform.desktop_frame_source import DesktopFrameSource
from core.spatial import ScreenGeometry


class _StaticGeometryProvider:
    def __init__(self, geometry):
        self.geometry = geometry

    def current_geometry(self):
        return self.geometry


class DesktopFrameSourceTests(unittest.TestCase):
    def test_capture_builds_full_screen_frame_with_observed_physical_geometry(self):
        geometry = ScreenGeometry(left=-1920, top=0, width=3840, height=2160, dpi_scale_x=1.5, dpi_scale_y=1.5)
        captured_geometries = []

        def capture_backend(observed_geometry):
            captured_geometries.append(observed_geometry)
            return np.zeros((1080, 1920, 3), dtype=np.uint8)

        source = DesktopFrameSource(
            geometry_provider=_StaticGeometryProvider(geometry),
            capture_backend=capture_backend,
        )

        frame, observed_geometry = source.capture()

        self.assertEqual([geometry], captured_geometries)
        self.assertEqual(geometry, observed_geometry)
        self.assertEqual(CoordinateSpace.FULL_SCREEN, frame.coordinate_space)
        self.assertEqual((1920, 1080), frame.size)
        self.assertEqual("desktop_frame_source", frame.source)
        self.assertIsNotNone(frame.captured_at_ms)
        self.assertEqual(
            {"left": -1920.0, "top": 0.0, "width": 3840.0, "height": 2160.0},
            frame.metadata["physical_desktop"],
        )


if __name__ == "__main__":
    unittest.main()
