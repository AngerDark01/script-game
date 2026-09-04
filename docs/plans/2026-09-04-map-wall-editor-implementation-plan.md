# 地图墙体编辑器实施计划

> **执行方式：** 当前会话、测试先行。设计见 `2026-09-04-map-wall-editor-design.md`。

## Goal

在总工作台增加可编辑已保存地图墙体的正式页面，以非破坏性修正层保存人工加墙/擦墙，并让导航定位与寻路加载同一份合成后的最终墙体图。

## Architecture Overview

```text
map_data/<name>/map_data.npz (base wall_layer)
       + wall_overrides.npz (add_mask / erase_mask)
       + config.json.wall_overrides metadata
       ↓
core.map_editing.compose_effective_wall_layer(...)
       ↓
NavigationCore.wall_layer → localization and derived nav_wall_layer

gui.modes.map_editor
       ↓ Qt mouse/zoom actions
core.map_editing operations/storage
```

- `core.map_editing` is Qt-free and owns wall override shape validation, composition, brush patch commands, and persistence.
- `gui.modes.map_editor` owns page widgets, preview painting, zoom/pan, pointer-to-map conversion, undo/redo, and user feedback.
- `core.localization.map_package` remains the one authoritative navigation map load boundary; it composes overrides immediately after reading the base map wall layer.
- Existing maps with no `wall_overrides` metadata behave exactly as before.

## Tech Stack

- Python 3 / NumPy / OpenCV
- PySide6
- `unittest` with `QT_QPA_PLATFORM=offscreen`
- Existing map package format: compressed `.npz` and UTF-8 JSON configuration

## Task 1: Add typed wall-override document and effective-wall composition

**Files**

- Create `core/map_editing/__init__.py`
- Create `core/map_editing/models.py`
- Create `core/map_editing/composition.py`
- Create `tests/test_wall_override_composition.py`

**Test first**

```python
import unittest
import numpy as np

from core.map_editing.composition import compose_effective_wall_layer
from core.map_editing.models import WallOverrideDocument


class WallOverrideCompositionTests(unittest.TestCase):
    def test_erase_then_add_masks_override_the_base_wall_without_mutating_it(self):
        base = np.array([[0, 255], [255, 0]], dtype=np.uint8)
        overrides = WallOverrideDocument.empty(base.shape)
        overrides.erase_mask[1, 0] = 255
        overrides.add_mask[1, 1] = 255

        effective = compose_effective_wall_layer(base, overrides)

        np.testing.assert_array_equal(base, [[0, 255], [255, 0]])
        np.testing.assert_array_equal(effective, [[0, 255], [0, 255]])

    def test_mismatched_override_shape_is_rejected(self):
        base = np.zeros((4, 4), dtype=np.uint8)
        overrides = WallOverrideDocument.empty((3, 4))
        with self.assertRaisesRegex(ValueError, "shape"):
            compose_effective_wall_layer(base, overrides)
```

Run and expect `ModuleNotFoundError` before implementation:

```powershell
$env:PYTHONPATH = 'D:\ACloud\auto_modules'
D:\ACloud\.venv\Scripts\python.exe -m unittest tests.test_wall_override_composition
```

**Implementation**

`core/map_editing/models.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
import numpy as np


@dataclass
class WallOverrideDocument:
    add_mask: np.ndarray
    erase_mask: np.ndarray

    @classmethod
    def empty(cls, shape: tuple[int, int]) -> "WallOverrideDocument":
        if len(shape) != 2 or min(shape) <= 0:
            raise ValueError("wall override shape must be a positive two-dimensional shape")
        return cls(
            add_mask=np.zeros(shape, dtype=np.uint8),
            erase_mask=np.zeros(shape, dtype=np.uint8),
        )

    def validate_for(self, shape: tuple[int, int]) -> None:
        if self.add_mask.shape != shape or self.erase_mask.shape != shape:
            raise ValueError(f"wall override shape must match base wall shape {shape}")
        if self.add_mask.ndim != 2 or self.erase_mask.ndim != 2:
            raise ValueError("wall override masks must be two-dimensional")
```

`core/map_editing/composition.py`:

```python
from __future__ import annotations

import numpy as np
from .models import WallOverrideDocument


def compose_effective_wall_layer(base_wall: np.ndarray, overrides: WallOverrideDocument) -> np.ndarray:
    if base_wall.ndim != 2:
        raise ValueError("base wall layer must be two-dimensional")
    overrides.validate_for(tuple(base_wall.shape))
    effective = base_wall.copy()
    effective[overrides.erase_mask > 0] = 0
    effective[overrides.add_mask > 0] = 255
    return effective
```

**Verify**

```powershell
D:\ACloud\.venv\Scripts\python.exe -m unittest tests.test_wall_override_composition
# Expected: Ran 2 tests ... OK
```

**Commit**

`feat: add composable wall override model`

## Task 2: Implement bounded add/erase brush operations and reversible patches

**Files**

- Create `core/map_editing/operations.py`
- Create `tests/test_wall_override_operations.py`

**Test first**

```python
def test_erase_clears_add_mask_at_the_same_pixels_and_returns_a_reversible_patch(self):
    document = WallOverrideDocument.empty((20, 20))
    add_patch = apply_circular_brush(document, center=(10, 10), radius=2, mode="add")
    erase_patch = apply_circular_brush(document, center=(10, 10), radius=2, mode="erase")

    self.assertTrue(np.any(document.erase_mask))
    self.assertFalse(np.any(document.add_mask))
    erase_patch.undo(document)
    self.assertTrue(np.any(document.add_mask))
    add_patch.undo(document)
    self.assertFalse(np.any(document.add_mask))
```

**Implementation contract**

```python
@dataclass(frozen=True)
class WallMaskPatch:
    x: int
    y: int
    add_before: np.ndarray
    erase_before: np.ndarray
    add_after: np.ndarray
    erase_after: np.ndarray

    def undo(self, document: WallOverrideDocument) -> None: ...
    def redo(self, document: WallOverrideDocument) -> None: ...

def apply_circular_brush(
    document: WallOverrideDocument,
    *, center: tuple[int, int], radius: int, mode: str,
) -> WallMaskPatch | None: ...
```

`apply_circular_brush` must clip at map edges, reject unknown modes, use a filled circle, and return `None` when a stamp makes no state change. The UI will interpolate pointer motion at no more than half a brush radius, so repeated stamps form a solid line.

**Verify**

```powershell
D:\ACloud\.venv\Scripts\python.exe -m unittest tests.test_wall_override_operations
# Expected: Ran ... tests ... OK
```

**Commit**

`feat: add reversible wall brush operations`

## Task 3: Add atomic per-map override storage and config metadata merge

**Files**

- Create `core/map_editing/storage.py`
- Create `tests/test_wall_override_storage.py`

**Test first**

```python
def test_save_round_trips_masks_and_preserves_unrelated_config_fields(self):
    with tempfile.TemporaryDirectory() as root:
        folder = Path(root)
        (folder / "config.json").write_text('{"fps": 30, "recognizer_params": {"enable_wall": true}}', encoding="utf-8")
        document = WallOverrideDocument.empty((4, 5))
        document.add_mask[1, 2] = 255

        save_wall_overrides(folder, document)
        saved_config = json.loads((folder / "config.json").read_text(encoding="utf-8"))
        loaded = load_wall_overrides(folder, (4, 5))

        self.assertEqual(saved_config["fps"], 30)
        self.assertTrue(saved_config["wall_overrides"]["enabled"])
        np.testing.assert_array_equal(loaded.add_mask, document.add_mask)
```

**Implementation contract**

```python
OVERRIDE_FILENAME = "wall_overrides.npz"
OVERRIDE_CONFIG_KEY = "wall_overrides"
FORMAT_VERSION = 1

def load_wall_overrides(map_folder: str | Path, shape: tuple[int, int]) -> WallOverrideDocument: ...
def save_wall_overrides(map_folder: str | Path, document: WallOverrideDocument) -> Path: ...
def clear_wall_overrides(map_folder: str | Path, shape: tuple[int, int]) -> WallOverrideDocument: ...
```

Use `tempfile.NamedTemporaryFile(delete=False, dir=folder, suffix=".npz")`, then `Path.replace()` only after successful `np.savez_compressed`. JSON metadata must use the same temporary-file-and-replace discipline. If metadata is absent, loading returns an empty document; if it declares a missing/corrupt/mismatched override file, raise `ValueError` without changing files.

**Verify**

```powershell
D:\ACloud\.venv\Scripts\python.exe -m unittest tests.test_wall_override_storage
# Expected: every round-trip and corrupt-file safety test passes
```

**Commit**

`feat: persist map wall overrides safely`

## Task 4: Make navigation map loading consume effective walls

**Files**

- Modify `core/localization/map_package.py`
- Create `tests/test_navigation_wall_override_loading.py`

**Test first**

```python
def test_navigation_package_composes_persisted_overrides_before_deriving_nav_wall(self):
    # Build a temporary map_data.npz with a 5x5 base wall and an override that
    # erases one base wall and adds one new wall. Construct NavigationCore on
    # the folder, then assert both effective wall values and nav wall values.
    ...
```

**Implementation**

Replace the direct assignment in `load_navigation_map_package` with:

```python
from core.map_editing.composition import compose_effective_wall_layer
from core.map_editing.storage import load_wall_overrides

base_wall_layer = data["wall_layer"]
overrides = load_wall_overrides(Path(nav_core.map_data_path).parent, tuple(base_wall_layer.shape))
nav_core.wall_layer = compose_effective_wall_layer(base_wall_layer, overrides)
```

Add `from pathlib import Path`. Preserve the existing `nav_wall_layer` compatibility branch: if an override is active, always derive it from `nav_core.wall_layer`; otherwise preserve the existing package-provided `nav_wall_layer` fallback semantics.

**Verify**

```powershell
D:\ACloud\.venv\Scripts\python.exe -m unittest tests.test_navigation_wall_override_loading tests.test_navigation_core
# Expected: overrides are present in both localization and obstacle inputs
```

**Commit**

`feat: apply wall overrides when loading navigation maps`

## Task 5: Create the map-editor controller with undo, redo, dirty state, and map package loading

**Files**

- Create `gui/modes/map_editor/__init__.py`
- Create `gui/modes/map_editor/controller.py`
- Create `tests/test_map_editor_controller.py`

**Test first**

```python
def test_controller_tracks_dirty_state_and_restores_masks_across_undo_and_redo(self):
    controller = MapEditorController.load(folder)
    controller.apply_brush((8, 8), radius=3, mode="add")
    self.assertTrue(controller.is_dirty)
    controller.undo()
    self.assertFalse(np.any(controller.document.add_mask))
    controller.redo()
    self.assertTrue(np.any(controller.document.add_mask))
```

**Implementation contract**

```python
class MapEditorController:
    @classmethod
    def load(cls, map_folder: str | Path) -> "MapEditorController": ...
    @property
    def effective_wall_layer(self) -> np.ndarray: ...
    @property
    def is_dirty(self) -> bool: ...
    def apply_brush(self, point: tuple[int, int], *, radius: int, mode: str) -> bool: ...
    def undo(self) -> bool: ...
    def redo(self) -> bool: ...
    def discard_changes(self) -> None: ...
    def clear_overrides(self) -> None: ...
    def save(self) -> Path: ...
```

`load()` opens `map_data.npz` with `allow_pickle=False`, requires a two-dimensional `wall_layer`, and does not load unrelated map arrays into memory. `save()` persists only the override document through Task 3 storage; it never writes `map_data.npz`.

**Verify**

```powershell
$env:QT_QPA_PLATFORM = 'offscreen'
D:\ACloud\.venv\Scripts\python.exe -m unittest tests.test_map_editor_controller
# Expected: load/save/discard/undo/redo behavior passes without Qt widgets
```

**Commit**

`feat: add map editor state controller`

## Task 6: Build an interactive Qt canvas with correct map-coordinate conversion

**Files**

- Create `gui/modes/map_editor/canvas.py`
- Create `tests/test_map_editor_canvas.py`

**Test first**

```python
def test_canvas_maps_pointer_positions_back_to_original_map_coordinates_after_zoom(self):
    canvas = WallEditorCanvas()
    canvas.set_map_layers(base, add_mask, erase_mask)
    canvas.resize(800, 600)
    canvas.set_zoom(2.0)
    canvas.set_pan_offset(QPointF(30, 40))
    assert canvas.map_point_from_view(QPointF(...)) == (expected_x, expected_y)
```

**Implementation contract**

```python
class WallEditorCanvas(QWidget):
    stroke_started = Signal(tuple)
    stroke_extended = Signal(tuple)
    stroke_finished = Signal()

    def set_map_layers(self, base_wall, add_mask, erase_mask) -> None: ...
    def set_tool(self, mode: str, radius: int) -> None: ...
    def fit_map(self) -> None: ...
    def map_point_from_view(self, point: QPointF) -> tuple[int, int] | None: ...
```

Use `QPainter` to draw a downscaled grayscale base image and coloured alpha overlays. Wheel zoom centers around the cursor; middle-button drag pans; left-button drag emits interpolated map points spaced no farther than `max(1, radius // 2)`. The canvas never writes files or mutates controller state itself.

**Verify**

```powershell
$env:PYTHONPATH = 'D:\ACloud\auto_modules'
$env:QT_QPA_PLATFORM = 'offscreen'
D:\ACloud\.venv\Scripts\python.exe -m unittest tests.test_map_editor_canvas
# Expected: pointer transform and interpolated-stroke tests pass
```

**Commit**

`feat: add zoomable wall editor canvas`

## Task 7: Compose the Map Editor page and add it to the total workbench

**Files**

- Create `gui/modes/map_editor/widget.py`
- Modify `gui/main_window.py`
- Create `tests/test_map_editor_page_in_main_window.py`

**Test first**

```python
def test_main_window_exposes_map_editor_as_fourth_embedded_mode(self):
    window = MainWindow(gamepad_host_manager=FakeGamepadHostManager())
    assert window.mode_btn_map_editor.isCheckable()
    window.switch_mode(3)
    assert window.stacked_widget.currentWidget() is window.map_editor_widget
```

**Implementation contract**

```python
class MapEditorWidget(QWidget):
    map_saved = Signal(str)

    def refresh_map_list(self) -> None: ...
    def load_selected_map(self) -> bool: ...
    def save_current_map(self) -> bool: ...
```

The page includes the confirmed map selector, add/erase tool buttons, brush radius spinbox, zoom controls, undo/redo, reload, clear overrides, save, status text, and `WallEditorCanvas`.

In `MainWindow`:

```python
self.mode_btn_map_editor = QPushButton("🧱 地图编辑")
self.mode_btn_map_editor.setProperty("role", "mode")
self.mode_btn_map_editor.setCheckable(True)
self.mode_btn_map_editor.clicked.connect(lambda: self.switch_mode(3))
self.mode_buttons.append(self.mode_btn_map_editor)

self.map_editor_widget = MapEditorWidget(source_file=__file__, parent=self)
self.stacked_widget.addWidget(self.map_editor_widget)
```

When switching to index 3, call `refresh_map_list()`. On save, show a non-blocking message stating that navigation must reload the map before the change affects an already-loaded navigation session.

**Verify**

```powershell
$env:PYTHONPATH = 'D:\ACloud\auto_modules;D:\ACloud\auto_modules\virtual_gamepad\ui;D:\ACloud\auto_modules\virtual_gamepad\client\python'
$env:QT_QPA_PLATFORM = 'offscreen'
D:\ACloud\.venv\Scripts\python.exe -m unittest tests.test_map_editor_page_in_main_window tests.test_navigation_ui_layout tests.test_gamepad_page_in_main_window
# Expected: new fourth page works and existing three pages remain intact
```

**Commit**

`feat: add wall map editor workbench page`

## Task 8: Run the focused suite and manually validate a real saved map

**Files**

- No production changes unless a failure is found.

**Verification**

```powershell
$env:PYTHONPATH = 'D:\ACloud\auto_modules;D:\ACloud\auto_modules\virtual_gamepad\ui;D:\ACloud\auto_modules\virtual_gamepad\client\python'
$env:QT_QPA_PLATFORM = 'offscreen'
D:\ACloud\.venv\Scripts\python.exe -m unittest `
  tests.test_wall_override_composition `
  tests.test_wall_override_operations `
  tests.test_wall_override_storage `
  tests.test_navigation_wall_override_loading `
  tests.test_map_editor_controller `
  tests.test_map_editor_canvas `
  tests.test_map_editor_page_in_main_window
```

Then launch the total workbench, open `🧱 地图编辑`, load one existing map, add and erase visible wall cells, save, re-open it, and reload it in navigation mode. Confirm that no `map_data.npz` file was rewritten and that `wall_overrides.npz` and configuration metadata are present.

**Commit**

`test: verify map wall editor workflow`
