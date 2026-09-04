"""Pure mapping from captured desktop-image pixels to physical-screen points."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
from types import MappingProxyType
from typing import Any, Mapping

from core.perception.models import CoordinateSpace

from .calibration import AffineTransform
from .models import Point2D


@dataclass(frozen=True)
class ScreenGeometry:
    """One physical desktop rectangle observed by an input/capture host."""

    left: float
    top: float
    width: float
    height: float
    dpi_scale_x: float = 1.0
    dpi_scale_y: float = 1.0

    def __post_init__(self) -> None:
        for name in ("left", "top", "width", "height", "dpi_scale_x", "dpi_scale_y"):
            value = float(getattr(self, name))
            if not isfinite(value):
                raise ValueError(f"ScreenGeometry {name} must be finite")
            object.__setattr__(self, name, value)
        if self.width <= 0 or self.height <= 0:
            raise ValueError("ScreenGeometry width and height must be positive")
        if self.dpi_scale_x <= 0 or self.dpi_scale_y <= 0:
            raise ValueError("ScreenGeometry DPI scales must be positive")

    def contains(self, point: Point2D) -> bool:
        """Return whether a point lies in the half-open physical desktop rectangle."""
        return (
            self.left <= point.x < self.left + self.width
            and self.top <= point.y < self.top + self.height
        )


@dataclass(frozen=True)
class MappedPoint:
    """A validated source point translated into an explicit destination space."""

    source_point: Point2D
    source_space: CoordinateSpace
    destination_point: Point2D
    destination_space: CoordinateSpace
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.source_space, CoordinateSpace):
            raise TypeError("source_space must be a CoordinateSpace")
        if not isinstance(self.destination_space, CoordinateSpace):
            raise TypeError("destination_space must be a CoordinateSpace")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


class DesktopCoordinateMapper:
    """Map one full-desktop capture's pixel plane into physical desktop coordinates."""

    def __init__(
        self,
        *,
        source_size: tuple[int, int],
        destination: ScreenGeometry,
    ) -> None:
        if not isinstance(destination, ScreenGeometry):
            raise TypeError("destination must be a ScreenGeometry")
        if not isinstance(source_size, tuple) or len(source_size) != 2:
            raise TypeError("source_size must be a two-item tuple")
        try:
            source_width, source_height = (int(value) for value in source_size)
        except (TypeError, ValueError) as exc:
            raise ValueError("source_size values must be integers") from exc
        if source_width <= 0 or source_height <= 0:
            raise ValueError("source_size values must be positive")

        self._source_size = (source_width, source_height)
        self._destination = destination
        self._scale_x = destination.width / source_width
        self._scale_y = destination.height / source_height
        self._transform = AffineTransform(
            self._scale_x,
            0.0,
            destination.left,
            0.0,
            self._scale_y,
            destination.top,
        )

    def map_point(self, point: Point2D, source_space: CoordinateSpace) -> MappedPoint:
        """Map a finite in-image point and reject invalid coordinate transitions."""
        if source_space is not CoordinateSpace.FULL_SCREEN:
            raise ValueError(
                "DesktopCoordinateMapper accepts only CoordinateSpace.FULL_SCREEN source points"
            )
        if not isinstance(point, Point2D):
            raise TypeError("point must be a Point2D")
        if not isfinite(point.x) or not isfinite(point.y):
            raise ValueError("point coordinates must be finite")
        source_width, source_height = self._source_size
        if not (0.0 <= point.x < source_width and 0.0 <= point.y < source_height):
            raise ValueError("point lies outside the captured desktop image")

        destination_point = self._transform.map_point(point)
        if not self._destination.contains(destination_point):
            raise ValueError("mapped point lies outside the physical desktop geometry")
        return MappedPoint(
            source_point=point,
            source_space=source_space,
            destination_point=destination_point,
            destination_space=CoordinateSpace.PHYSICAL_SCREEN,
            metadata={
                "transform": "scale_offset",
                "scale_x": self._scale_x,
                "scale_y": self._scale_y,
                "source_width": source_width,
                "source_height": source_height,
                "destination_left": self._destination.left,
                "destination_top": self._destination.top,
                "destination_width": self._destination.width,
                "destination_height": self._destination.height,
                "dpi_scale_x": self._destination.dpi_scale_x,
                "dpi_scale_y": self._destination.dpi_scale_y,
            },
        )
