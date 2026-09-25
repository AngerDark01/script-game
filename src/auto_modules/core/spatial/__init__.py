"""Coordinate spaces, calibration data, and runtime point mapping."""

from .calibration import CoordinateMapper, AffineTransform, fit_affine_transform
from .models import CoordinateAnchor, Point2D, WindowRect
from .desktop_mapping import DesktopCoordinateMapper, MappedPoint, ScreenGeometry, physical_screen_point

__all__ = [
    "AffineTransform",
    "CoordinateAnchor",
    "CoordinateMapper",
    "DesktopCoordinateMapper",
    "MappedPoint",
    "Point2D",
    "ScreenGeometry",
    "WindowRect",
    "fit_affine_transform",
    "physical_screen_point",
]
from .monitor_binding import CaptureRect, MonitorBinding, resize_binding_around_marker

__all__.extend(["CaptureRect", "MonitorBinding", "resize_binding_around_marker"])
