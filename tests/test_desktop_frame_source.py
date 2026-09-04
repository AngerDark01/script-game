import unittest
from unittest import mock

import numpy as np

from core.perception.models import CoordinateSpace
from core.platform.desktop_frame_source import DesktopFrameSource, WindowsPrimaryMonitorGeometryProvider
from core.spatial import ScreenGeometry


class _StaticGeometryProvider:
    def __init__(self, geometry):
        self.geometry = geometry

    def current_geometry(self):
        return self.geometry


class _FakeDpiGetter:
    def __init__(self, dpi):
        self.dpi = dpi
        self.restype = None

    def __call__(self):
        return self.dpi


class _FakeUser32:
    def __init__(self, metrics, dpi):
        self.metrics = dict(metrics)
        self.requested_metrics = []
        self.GetDpiForSystem = _FakeDpiGetter(dpi)

    def GetSystemMetrics(self, metric):
        self.requested_metrics.append(metric)
        return self.metrics[metric]


class DesktopFrameSourceTests(unittest.TestCase):
    def test_primary_monitor_provider_reads_primary_extent_at_desktop_origin(self):
        provider = object.__new__(WindowsPrimaryMonitorGeometryProvider)
        fake_user32 = _FakeUser32({0: 2560, 1: 1440}, dpi=144)
        provider._user32 = fake_user32

        geometry = provider.current_geometry()

        self.assertEqual([0, 1], fake_user32.requested_metrics)
        self.assertEqual(ScreenGeometry(left=0, top=0, width=2560, height=1440, dpi_scale_x=1.5, dpi_scale_y=1.5), geometry)

    def test_default_capture_uses_primary_monitor_geometry_provider(self):
        """The no-argument composition must not silently capture other monitors."""
        geometry = ScreenGeometry(left=0, top=0, width=2560, height=1440, dpi_scale_x=1.5, dpi_scale_y=1.5)
        captured_geometries = []

        def capture_backend(observed_geometry):
            captured_geometries.append(observed_geometry)
            return np.zeros((1440, 2560, 3), dtype=np.uint8)

        with mock.patch(
            "core.platform.desktop_frame_source.WindowsPrimaryMonitorGeometryProvider"
        ) as primary_provider_type:
            primary_provider_type.return_value.current_geometry.return_value = geometry
            source = DesktopFrameSource(capture_backend=capture_backend)
            frame, observed_geometry = source.capture()

        primary_provider_type.assert_called_once_with()
        self.assertEqual([geometry], captured_geometries)
        self.assertEqual(geometry, observed_geometry)
        self.assertEqual((2560, 1440), frame.size)

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
