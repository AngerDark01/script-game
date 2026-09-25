"""Game-neutral geometry helpers for monitor capture masks."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import hypot, isfinite

import numpy as np


class CaptureShape(StrEnum):
    """The effective shape used inside a rectangular capture frame."""

    SQUARE = "square"
    CIRCLE = "circle"

    @classmethod
    def coerce(cls, value: "CaptureShape | str") -> "CaptureShape":
        if isinstance(value, cls):
            return value
        try:
            return cls(str(value).strip().lower())
        except ValueError as exc:
            raise ValueError(f"unsupported capture shape: {value!r}") from exc


@dataclass(frozen=True)
class CaptureGeometry:
    """Validated shape metadata for one rectangular monitor capture."""

    width: int
    height: int
    shape: CaptureShape = CaptureShape.SQUARE
    radius: float | None = None

    def __post_init__(self) -> None:
        width = int(self.width)
        height = int(self.height)
        if width <= 0 or height <= 0:
            raise ValueError("capture dimensions must be positive")
        shape = CaptureShape.coerce(self.shape)
        radius = self.radius
        if shape is CaptureShape.CIRCLE:
            if radius is None:
                radius = min(width, height) / 2.0
            radius = float(radius)
            if not isfinite(radius) or radius <= 0:
                raise ValueError("circle radius must be positive and finite")
        elif radius is not None:
            radius = float(radius)
            if not isfinite(radius) or radius <= 0:
                raise ValueError("radius must be positive and finite when provided")
        object.__setattr__(self, "width", width)
        object.__setattr__(self, "height", height)
        object.__setattr__(self, "shape", shape)
        object.__setattr__(self, "radius", radius)

    def mask(self) -> np.ndarray:
        return build_capture_mask(
            self.width,
            self.height,
            self.shape,
            radius=self.radius,
        )


def build_capture_mask(
    width: int,
    height: int,
    shape: CaptureShape | str = CaptureShape.SQUARE,
    *,
    radius: float | None = None,
) -> np.ndarray:
    """Return a rectangular boolean mask for the effective capture shape.

    The returned array always has shape ``(height, width)``.  This keeps screen
    capture and image matching rectangular while allowing callers to ignore
    pixels outside a circular effective area.
    """

    geometry = CaptureGeometry(width, height, CaptureShape.coerce(shape), radius)
    if geometry.shape is CaptureShape.SQUARE:
        return np.ones((geometry.height, geometry.width), dtype=np.bool_)

    center_x = (geometry.width - 1) / 2.0
    center_y = (geometry.height - 1) / 2.0
    y_indices, x_indices = np.ogrid[: geometry.height, : geometry.width]
    distances = np.hypot(x_indices - center_x, y_indices - center_y)
    return distances <= float(geometry.radius)


__all__ = ["CaptureGeometry", "CaptureShape", "build_capture_mask"]
