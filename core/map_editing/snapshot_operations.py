"""Brush operations for one final wall-layer draft or immutable snapshot."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class WallLayerPatch:
    """One changed rectangular subset of a complete wall layer."""

    x: int
    y: int
    before: np.ndarray
    after: np.ndarray

    def undo(self, wall_layer: np.ndarray) -> None:
        self._apply(wall_layer, self.before)

    def redo(self, wall_layer: np.ndarray) -> None:
        self._apply(wall_layer, self.after)

    def _apply(self, wall_layer: np.ndarray, values: np.ndarray) -> None:
        _validate_wall_layer(wall_layer)
        wall_layer[self.y:self.y + values.shape[0], self.x:self.x + values.shape[1]] = values


def apply_wall_brush(
    wall_layer: np.ndarray,
    *,
    center: tuple[int, int],
    radius: int,
    mode: str,
) -> WallLayerPatch | None:
    """Paint one add/erase circle into the final displayed wall layer."""
    _validate_wall_layer(wall_layer)
    if mode not in {"add", "erase"}:
        raise ValueError(f"unknown wall brush mode: {mode}")
    if radius < 0:
        raise ValueError("brush radius must be non-negative")

    height, width = wall_layer.shape
    center_x, center_y = int(center[0]), int(center[1])
    x0, x1 = max(0, center_x - radius), min(width, center_x + radius + 1)
    y0, y1 = max(0, center_y - radius), min(height, center_y + radius + 1)
    if x0 >= x1 or y0 >= y1:
        return None

    local_y, local_x = np.ogrid[y0:y1, x0:x1]
    circle = (local_x - center_x) ** 2 + (local_y - center_y) ** 2 <= radius**2
    region = wall_layer[y0:y1, x0:x1]
    before = region.copy()
    region[circle] = 255 if mode == "add" else 0
    if np.array_equal(before, region):
        return None
    return WallLayerPatch(x=x0, y=y0, before=before, after=region.copy())


def _validate_wall_layer(wall_layer: np.ndarray) -> None:
    if wall_layer.ndim != 2:
        raise ValueError("wall layer must be two-dimensional")
