"""PoE2-specific movement calibration for the live-terrain experiment.

The generic gamepad adapter accepts a map-space vector and a 2x2 basis.  PoE2
uses an isometric movement projection: a horizontal stick direction changes
both native grid axes.  This basis is intentionally kept at the PoE2 adapter
boundary so other games and the shared gamepad default remain unchanged.
"""

from __future__ import annotations

import math

from auto_modules.core.localization.displacement import inverse_transform_local_displacement

# Map-space (native grid X/Y) to left-stick (X/Y).  The inverse camera
# projection is approximately a 45-degree basis:
#   native (+X, 0) -> stick (+X, +Y)
#   native (0, +Y) -> stick (-X, +Y)
# It is normalized by the output adapter before writing the stick state.
POE2_MAP_TO_STICK_BASIS: tuple[float, float, float, float] = (
    0.5,
    -0.5,
    0.5,
    0.5,
)


def native_map_vector_to_local(
    vector: tuple[float, float],
    *,
    angle_degrees: float,
    reflect_horizontal: bool,
    scale: float,
) -> tuple[float, float]:
    """Convert a native route vector into the current minimap/input frame.

    Routes are planned against the canonical native map.  The first-frame
    registration may rotate, mirror, and scale the captured minimap before it
    is placed on that map.  The gamepad direction must therefore use the
    inverse registration; applying the display transform directly would send
    movement along a different wall.  Translation is deliberately absent: it
    affects points, never displacement vectors.
    """
    return inverse_transform_local_displacement(
        vector,
        angle_degrees=angle_degrees,
        reflect_horizontal=reflect_horizontal,
        scale=scale,
    )


def native_route_vector_for_program_output(
    vector: tuple[float, float],
) -> tuple[float, float]:
    """Return a canonical native/reference route vector unchanged.

    Pathfinding, wall collision, display markers, and targets in the PoE2
    live-terrain runtime all use the registered native/reference map frame.
    ``ProgramGamepadOutput`` is the sole boundary that projects this vector
    into the Xbox stick frame via :data:`POE2_MAP_TO_STICK_BASIS`.  Applying
    the first-frame registration inverse here would rotate or reflect the
    route a second time and send the character toward the wrong wall.
    """
    if len(vector) != 2:
        raise ValueError("native route vector must contain exactly two values")
    x, y = float(vector[0]), float(vector[1])
    if not (math.isfinite(x) and math.isfinite(y)):
        raise ValueError("native route vector must contain finite values")
    return x, y


__all__ = [
    "POE2_MAP_TO_STICK_BASIS",
    "native_map_vector_to_local",
    "native_route_vector_for_program_output",
]
