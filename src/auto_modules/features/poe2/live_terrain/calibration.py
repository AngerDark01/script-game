"""Explicit PoE2 minimap-to-terrain calibration contract."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


def _point(value, name: str, *, finite: bool = True) -> tuple[float, float]:
    if value is None or len(value) != 2:
        raise ValueError(f"{name} must contain two values")
    result = (float(value[0]), float(value[1]))
    if finite and not all(isfinite(item) for item in result):
        raise ValueError(f"{name} must be finite")
    return result


@dataclass(frozen=True)
class Poe2Calibration:
    """Map a minimap pixel coordinate into a terrain-reference coordinate."""

    minimap_size: tuple[int, int]
    scale: tuple[float, float] = (1.0, 1.0)
    axis_direction: tuple[int, int] = (1, 1)
    invert_y: bool = False
    player_local_position: tuple[float, float] | None = None
    offset: tuple[float, float] = (0.0, 0.0)

    def __post_init__(self) -> None:
        if len(self.minimap_size) != 2 or any(int(item) <= 0 for item in self.minimap_size):
            raise ValueError("minimap_size must contain positive width and height")
        scale = _point(self.scale, "scale")
        if any(item <= 0 for item in scale):
            raise ValueError("scale must be positive")
        if len(self.axis_direction) != 2 or any(int(item) not in (-1, 1) for item in self.axis_direction):
            raise ValueError("axis_direction values must be -1 or 1")
        offset = _point(self.offset, "offset")
        marker = None if self.player_local_position is None else _point(
            self.player_local_position, "player_local_position"
        )
        width, height = int(self.minimap_size[0]), int(self.minimap_size[1])
        if marker is not None and not (0 <= marker[0] < width and 0 <= marker[1] < height):
            raise ValueError("player_local_position must be inside minimap_size")
        object.__setattr__(self, "minimap_size", (width, height))
        object.__setattr__(self, "scale", scale)
        object.__setattr__(self, "axis_direction", (int(self.axis_direction[0]), int(self.axis_direction[1])))
        object.__setattr__(self, "offset", offset)
        object.__setattr__(self, "player_local_position", marker)

    @property
    def scale_x(self) -> float:
        return self.scale[0]

    @property
    def scale_y(self) -> float:
        return self.scale[1]

    @property
    def marker_position(self) -> tuple[float, float] | None:
        return self.player_local_position

    def local_to_reference(self, local_position) -> tuple[float, float]:
        x, y = _point(local_position, "local_position")
        if self.invert_y:
            y = float(self.minimap_size[1] - 1) - y
        return (
            self.offset[0] + x * self.scale[0] * self.axis_direction[0],
            self.offset[1] + y * self.scale[1] * self.axis_direction[1],
        )

    def reference_position_for_player(self) -> tuple[float, float] | None:
        if self.player_local_position is None:
            return None
        return self.local_to_reference(self.player_local_position)


# The shorter name is useful at generic experiment call sites.
MinimapCalibration = Poe2Calibration

__all__ = ["MinimapCalibration", "Poe2Calibration"]
