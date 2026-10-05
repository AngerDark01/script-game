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


def inverse_transform_local_displacement(
    shift: tuple[float, float],
    *,
    angle_degrees: float,
    reflect_horizontal: bool,
    scale: float,
) -> tuple[float, float]:
    """Map a native-map displacement back into the captured local frame.

    ``transform_local_displacement`` represents the registration used by the
    feature matcher: reflection is applied in the local image frame and the
    result is then rotated/scaled into native-map coordinates.  Movement
    planning runs in native coordinates, while game input follows the local
    minimap frame, so the inverse must rotate first and reflect second.  This
    is intentionally a separate function instead of negating the angle: with
    a reflection those operations do not commute.
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
    radians = math.radians(angle)
    cosine, sine = math.cos(radians), math.sin(radians)
    # R(-angle) in the image-axis convention, followed by F when the
    # registration reflected the local frame: inverse(T) = F * R(-angle).
    local_x = cosine * x - sine * y
    local_y = sine * x + cosine * y
    if reflect_horizontal:
        local_x = -local_x
    return local_x / scale, local_y / scale


__all__ = ["inverse_transform_local_displacement", "transform_local_displacement"]
