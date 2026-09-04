"""Coordinate spaces, calibration data, and runtime point mapping."""

from .calibration import CoordinateMapper, AffineTransform, fit_affine_transform
from .models import CoordinateAnchor, Point2D, WindowRect
from .desktop_mapping import DesktopCoordinateMapper, MappedPoint, ScreenGeometry

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
]
