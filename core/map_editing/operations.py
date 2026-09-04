from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .models import WallOverrideDocument


@dataclass(frozen=True)
class WallMaskPatch:
    """The changed rectangular subset of one brush stamp for undo/redo."""

    x: int
    y: int
    add_before: np.ndarray
    erase_before: np.ndarray
    add_after: np.ndarray
    erase_after: np.ndarray

    def undo(self, document: WallOverrideDocument) -> None:
        self._apply(document, self.add_before, self.erase_before)

    def redo(self, document: WallOverrideDocument) -> None:
        self._apply(document, self.add_after, self.erase_after)

    def _apply(self, document: WallOverrideDocument, add: np.ndarray, erase: np.ndarray) -> None:
        y_end = self.y + add.shape[0]
        x_end = self.x + add.shape[1]
        document.add_mask[self.y:y_end, self.x:x_end] = add
        document.erase_mask[self.y:y_end, self.x:x_end] = erase


def apply_circular_brush(
    document: WallOverrideDocument,
    *,
    center: tuple[int, int],
    radius: int,
    mode: str,
) -> WallMaskPatch | None:
    """Apply one clipped add/erase circle and capture only its changed rectangle."""
    if mode not in {"add", "erase"}:
        raise ValueError(f"unknown wall brush mode: {mode}")
    if radius < 0:
        raise ValueError("brush radius must be non-negative")
    height, width = document.add_mask.shape
    document.validate_for((height, width))
    center_x, center_y = (int(center[0]), int(center[1]))
    x0 = max(0, center_x - radius)
    x1 = min(width, center_x + radius + 1)
    y0 = max(0, center_y - radius)
    y1 = min(height, center_y + radius + 1)
    if x0 >= x1 or y0 >= y1:
        return None

    local_y, local_x = np.ogrid[y0:y1, x0:x1]
    circle = (local_x - center_x) ** 2 + (local_y - center_y) ** 2 <= radius**2
    add_region = document.add_mask[y0:y1, x0:x1]
    erase_region = document.erase_mask[y0:y1, x0:x1]
    add_before = add_region.copy()
    erase_before = erase_region.copy()
    if mode == "add":
        add_region[circle] = 255
        erase_region[circle] = 0
    else:
        add_region[circle] = 0
        erase_region[circle] = 255

    if np.array_equal(add_before, add_region) and np.array_equal(erase_before, erase_region):
        return None
    return WallMaskPatch(
        x=x0,
        y=y0,
        add_before=add_before,
        erase_before=erase_before,
        add_after=add_region.copy(),
        erase_after=erase_region.copy(),
    )
