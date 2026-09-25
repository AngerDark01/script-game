"""Coordinate-neutral displacement transforms."""

from __future__ import annotations

import math


def transform_local_displacement(
    shift: tuple[float, float],
    *,
    angle_degrees: float,
    reflect_horizontal: bool,
    scale: float,
) -> tuple[float, float]:
    """Map a local image-frame displacement through a similarity transform.

    Coordinates use the image convention (x right, y down), matching the
    OpenCV affine transform used by visual feature registration.  Therefore a
    positive angle rotates a rightward vector toward negative y.  Reflection
    remains part of the local-frame transform and is applied before rotation.
    """
    if len(shift) != 2:
        raise ValueError("shift must contain two values")
    x, y = float(shift[0]), float(shift[1])
    angle = float(angle_degrees)
    scale = float(scale)
    if not all(math.isfinite(value) for value in (x, y, angle, scale)):
        raise ValueError("displacement values must be finite")
    if scale <= 0:
        raise ValueError("scale must be positive")
    if reflect_horizontal:
        x = -x
    radians = math.radians(angle)
    cosine, sine = math.cos(radians), math.sin(radians)
    return (
        scale * (cosine * x + sine * y),
        scale * (-sine * x + cosine * y),
    )


__all__ = ["transform_local_displacement"]
