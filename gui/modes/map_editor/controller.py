"""Qt-free checkout, draft, history, and version actions for wall editing."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from core.map_editing.snapshot_operations import WallLayerPatch, apply_wall_brush
from core.map_editing.version_storage import (
    WallVersion,
    activate_wall_version,
    load_wall_version,
    load_wall_version_catalog,
    migrate_legacy_wall_overrides,
    save_new_wall_version,
)


@dataclass
class MapEditorController:
    """One wall draft checked out from the current active map version."""

    map_folder: Path
    original_wall_layer: np.ndarray
    source_version_id: str | None
    active_version_id: str | None
    working_wall_layer: np.ndarray
    versions: tuple[WallVersion, ...]
    _source_wall_layer: np.ndarray
    _history: list[WallLayerPatch] = field(default_factory=list)
    _cursor: int = 0
    _saved_cursor: int = 0
    _active_stroke: WallLayerPatch | None = field(default=None, init=False, repr=False)
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
                original_wall_layer = _binary_wall_layer(package["wall_layer"])
        except ValueError:
            raise
        except Exception as error:
            raise ValueError(f"map package is invalid: {error}") from error

        # A legacy add/erase document becomes the first immutable snapshot as
        # soon as its map reaches this editor.  The old files are preserved.
        migrate_legacy_wall_overrides(folder, original_wall_layer)
        catalog = load_wall_version_catalog(folder, original_wall_layer)
        source_wall_layer = catalog.active_wall_layer.copy()
        return cls(
            map_folder=folder,
            original_wall_layer=original_wall_layer,
            source_version_id=catalog.active_version,
            active_version_id=catalog.active_version,
            working_wall_layer=source_wall_layer.copy(),
            versions=catalog.versions,
            _source_wall_layer=source_wall_layer,
        )

    @property
    def map_shape(self) -> tuple[int, int]:
        return tuple(self.working_wall_layer.shape)

    @property
    def preview_wall_layer(self) -> np.ndarray:
        """The exact black/white wall layer currently visible in the canvas."""
        return self.working_wall_layer

    @property
    def is_dirty(self) -> bool:
        return self._active_stroke is not None or self._cursor != self._saved_cursor

    @property
    def can_undo(self) -> bool:
        return self._cursor > 0

    @property
    def can_redo(self) -> bool:
        return self._cursor < len(self._history)

    @property
    def checked_out_label(self) -> str:
        return self.source_version_id or "原始地图"

    def apply_brush(self, point: tuple[int, int], *, radius: int, mode: str) -> bool:
        patch = apply_wall_brush(self.working_wall_layer, center=point, radius=radius, mode=mode)
        if patch is None:
            return False
        if self._stroke_open:
            self._active_stroke = patch if self._active_stroke is None else self._merge_stroke_patch(self._active_stroke, patch)
        else:
            self._record_patch(patch)
        return True

    def begin_stroke(self) -> None:
        if self._stroke_open:
            raise RuntimeError("a wall-editor stroke is already active")
        self._stroke_open = True

    def end_stroke(self) -> bool:
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
        self._history[self._cursor].undo(self.working_wall_layer)
        return True

    def redo(self) -> bool:
        self.end_stroke()
        if not self.can_redo:
            return False
        self._history[self._cursor].redo(self.working_wall_layer)
        self._cursor += 1
        return True

    def discard_changes(self) -> None:
        self.working_wall_layer = self._source_wall_layer.copy()
        self._reset_history()

    def checkout_version(self, version_id: str | None) -> None:
        """Replace the draft with a selected immutable version or raw baseline."""
        if version_id is None:
            source_wall_layer = self.original_wall_layer.copy()
        else:
            _version, source_wall_layer = load_wall_version(self.map_folder, version_id, self.map_shape)
        catalog = load_wall_version_catalog(self.map_folder, self.original_wall_layer)
        self.source_version_id = version_id
        self.active_version_id = catalog.active_version
        self.versions = catalog.versions
        self._source_wall_layer = source_wall_layer.copy()
        self.working_wall_layer = source_wall_layer.copy()
        self._reset_history()

    def confirm_as_new_version(self) -> WallVersion:
        """Commit the explicit user-confirmed draft as the next active snapshot."""
        self.end_stroke()
        version = save_new_wall_version(
            self.map_folder,
            self.working_wall_layer,
            parent_version=self.source_version_id,
        )
        catalog = load_wall_version_catalog(self.map_folder, self.original_wall_layer)
        self.source_version_id = version.id
        self.active_version_id = version.id
        self.versions = catalog.versions
        self._source_wall_layer = self.working_wall_layer.copy()
        self._reset_history()
        return version

    def activate_checked_out_version(self) -> WallVersion:
        if self.source_version_id is None:
            raise ValueError("the original map is an editing baseline, not a saved navigation version")
        version = activate_wall_version(self.map_folder, self.source_version_id, self.map_shape)
        self.active_version_id = version.id
        return version

    def _record_patch(self, patch: WallLayerPatch) -> None:
        if self._cursor < len(self._history):
            del self._history[self._cursor:]
            if self._saved_cursor > self._cursor:
                self._saved_cursor = -1
        self._history.append(patch)
        self._cursor += 1

    def _reset_history(self) -> None:
        self._history.clear()
        self._cursor = 0
        self._saved_cursor = 0
        self._active_stroke = None
        self._stroke_open = False

    def _merge_stroke_patch(self, previous: WallLayerPatch, current: WallLayerPatch) -> WallLayerPatch:
        x0 = min(previous.x, current.x)
        y0 = min(previous.y, current.y)
        x1 = max(previous.x + previous.before.shape[1], current.x + current.before.shape[1])
        y1 = max(previous.y + previous.before.shape[0], current.y + current.before.shape[0])
        after = self.working_wall_layer[y0:y1, x0:x1].copy()
        before = after.copy()

        def place_before(patch: WallLayerPatch) -> None:
            top, left = patch.y - y0, patch.x - x0
            before[top:top + patch.before.shape[0], left:left + patch.before.shape[1]] = patch.before

        place_before(current)
        place_before(previous)
        return WallLayerPatch(x=x0, y=y0, before=before, after=after)


def _binary_wall_layer(wall_layer: np.ndarray) -> np.ndarray:
    if wall_layer.ndim != 2:
        raise ValueError("map package wall_layer must be two-dimensional")
    return np.where(wall_layer > 0, 255, 0).astype(np.uint8, copy=True)
