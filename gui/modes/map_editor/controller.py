from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from core.map_editing.composition import compose_effective_wall_layer
from core.map_editing.models import WallOverrideDocument
from core.map_editing.operations import WallMaskPatch, apply_circular_brush
from core.map_editing.storage import load_wall_overrides, save_wall_overrides


@dataclass
class MapEditorController:
    """Qt-free editing session for one saved map package."""

    map_folder: Path
    base_wall_layer: np.ndarray
    document: WallOverrideDocument
    _history: list[WallMaskPatch] = field(default_factory=list)
    _cursor: int = 0
    _saved_cursor: int = 0
    _active_stroke: WallMaskPatch | None = field(default=None, init=False, repr=False)
    _stroke_open: bool = field(default=False, init=False, repr=False)

    @classmethod
    def load(cls, map_folder: str | Path) -> "MapEditorController":
        folder = Path(map_folder)
        package_path = folder / "map_data.npz"
        if not package_path.is_file():
            raise FileNotFoundError(f"map package is missing: {package_path}")
        try:
            with np.load(package_path, allow_pickle=False) as package:
                if "wall_layer" not in package:
                    raise ValueError("map package does not contain wall_layer")
                base_wall_layer = package["wall_layer"].copy()
        except ValueError:
            raise
        except Exception as error:
            raise ValueError(f"map package is invalid: {error}") from error
        if base_wall_layer.ndim != 2:
            raise ValueError("map package wall_layer must be two-dimensional")
        document = load_wall_overrides(folder, tuple(base_wall_layer.shape))
        return cls(map_folder=folder, base_wall_layer=base_wall_layer, document=document)

    @property
    def map_shape(self) -> tuple[int, int]:
        return tuple(self.base_wall_layer.shape)

    @property
    def effective_wall_layer(self) -> np.ndarray:
        return compose_effective_wall_layer(self.base_wall_layer, self.document)

    @property
    def is_dirty(self) -> bool:
        return self._active_stroke is not None or self._cursor != self._saved_cursor

    @property
    def can_undo(self) -> bool:
        return self._cursor > 0

    @property
    def can_redo(self) -> bool:
        return self._cursor < len(self._history)

    def apply_brush(self, point: tuple[int, int], *, radius: int, mode: str) -> bool:
        patch = apply_circular_brush(self.document, center=point, radius=radius, mode=mode)
        if patch is None:
            return False
        if self._stroke_open:
            self._active_stroke = (
                patch
                if self._active_stroke is None
                else self._merge_stroke_patch(self._active_stroke, patch)
            )
        else:
            self._record_patch(patch)
        return True

    def begin_stroke(self) -> None:
        """Group a canvas drag into one reversible history action."""
        if self._stroke_open:
            raise RuntimeError("a wall-editor stroke is already active")
        self._stroke_open = True

    def end_stroke(self) -> bool:
        """Commit the current drag to undo history, if it changed any pixels."""
        self._stroke_open = False
        if self._active_stroke is None:
            return False
        patch = self._active_stroke
        self._active_stroke = None
        self._record_patch(patch)
        return True

    def undo(self) -> bool:
        self.end_stroke()
        if not self.can_undo:
            return False
        self._cursor -= 1
        self._history[self._cursor].undo(self.document)
        return True

    def redo(self) -> bool:
        self.end_stroke()
        if not self.can_redo:
            return False
        self._history[self._cursor].redo(self.document)
        self._cursor += 1
        return True

    def discard_changes(self) -> None:
        self.document = load_wall_overrides(self.map_folder, self.map_shape)
        self._history.clear()
        self._cursor = 0
        self._saved_cursor = 0
        self._active_stroke = None
        self._stroke_open = False

    def clear_overrides(self) -> None:
        self.document = WallOverrideDocument.empty(self.map_shape)
        self._history.clear()
        self._cursor = 0
        self._saved_cursor = -1
        self._active_stroke = None
        self._stroke_open = False

    def save(self) -> Path:
        self.end_stroke()
        path = save_wall_overrides(self.map_folder, self.document)
        self._saved_cursor = self._cursor
        return path

    def _record_patch(self, patch: WallMaskPatch) -> None:
        if self._cursor < len(self._history):
            del self._history[self._cursor :]
            if self._saved_cursor > self._cursor:
                self._saved_cursor = -1
        self._history.append(patch)
        self._cursor += 1

    def _merge_stroke_patch(self, previous: WallMaskPatch, current: WallMaskPatch) -> WallMaskPatch:
        """Merge two stamps without cloning the complete map-sized masks."""
        x0 = min(previous.x, current.x)
        y0 = min(previous.y, current.y)
        x1 = max(previous.x + previous.add_before.shape[1], current.x + current.add_before.shape[1])
        y1 = max(previous.y + previous.add_before.shape[0], current.y + current.add_before.shape[0])
        height, width = y1 - y0, x1 - x0

        add_after = self.document.add_mask[y0:y1, x0:x1].copy()
        erase_after = self.document.erase_mask[y0:y1, x0:x1].copy()
        add_before = add_after.copy()
        erase_before = erase_after.copy()

        def place_before(patch: WallMaskPatch) -> None:
            top = patch.y - y0
            left = patch.x - x0
            bottom = top + patch.add_before.shape[0]
            right = left + patch.add_before.shape[1]
            add_before[top:bottom, left:right] = patch.add_before
            erase_before[top:bottom, left:right] = patch.erase_before

        # The first stamp is closest to the pre-stroke state and must win in
        # overlap regions.  Only copy the second stamp outside that rectangle.
        place_before(current)
        place_before(previous)
        return WallMaskPatch(
            x=x0,
            y=y0,
            add_before=add_before,
            erase_before=erase_before,
            add_after=add_after,
            erase_after=erase_after,
        )
