# 墙体完整快照版本库实施计划

## Goal

将地图墙体编辑器改为基于完整快照的版本库：编辑当前导航版本的草稿，确认后保存为新版本，导航直接加载选定版本的一张最终墙体图。

## Architecture Overview

```text
原始 map_data.npz.wall_layer (永不改写)
        │
        ├─ 无版本 → 原始墙体直接作为导航输入
        │
        └─ config.json.wall_versions.active_version
               │
               └─ wall_versions/vNNNN.npz.wall_layer
                       ├─ 编辑器 working_wall_layer 草稿
                       ├─ 定位模板
                       └─ derive_navigation_wall_layer → 寻路障碍
```

- `core.map_editing.snapshot_operations`：只操作单张最终墙体数组，提供局部撤销补丁；
- `core.map_editing.version_storage`：版本目录、索引、原子读写、激活与旧掩码迁移；
- `gui.modes.map_editor.controller`：检出 active 版本到草稿并协调撤销、保存、切换版本；
- `gui.modes.map_editor.canvas`：只显示草稿最终墙体；
- `core.localization.map_package`：直接加载 active 快照，不再组合掩码。

## Tech Stack

- Python 3.12、NumPy、OpenCV
- PySide6
- `unittest` 与 `QT_QPA_PLATFORM=offscreen`
- `.npz` + UTF-8 JSON，临时文件后原子替换

## Task 1: Add direct wall-layer brush operations with reversible patches

**Files**

- Create `core/map_editing/snapshot_operations.py`
- Create `tests/test_wall_snapshot_operations.py`
- Modify `core/map_editing/__init__.py`

**Test first**

```python
def test_erase_changes_the_final_layer_to_black_and_patch_restores_it(self):
    layer = np.zeros((20, 20), dtype=np.uint8)
    layer[10, 10] = 255
    patch = apply_wall_brush(layer, center=(10, 10), radius=1, mode="erase")
    self.assertEqual(0, layer[10, 10])
    patch.undo(layer)
    self.assertEqual(255, layer[10, 10])
```

Run before implementation:

```powershell
$env:PYTHONPATH = 'D:\ACloud\auto_modules'
D:\ACloud\.venv\Scripts\python.exe -m unittest tests.test_wall_snapshot_operations
# Expected: ImportError / ModuleNotFoundError
```

**Implementation**

```python
@dataclass(frozen=True)
class WallLayerPatch:
    x: int
    y: int
    before: np.ndarray
    after: np.ndarray

    def undo(self, wall_layer: np.ndarray) -> None:
        wall_layer[self.y:self.y + self.before.shape[0], self.x:self.x + self.before.shape[1]] = self.before

    def redo(self, wall_layer: np.ndarray) -> None:
        wall_layer[self.y:self.y + self.after.shape[0], self.x:self.x + self.after.shape[1]] = self.after

def apply_wall_brush(wall_layer, *, center, radius, mode) -> WallLayerPatch | None:
    # Validate a two-dimensional uint8-compatible layer and a non-negative radius.
    # Clip the filled circular brush to edges, assign 255 for add / 0 for erase,
    # and return only the affected rectangular before/after subset.
```

**Verify**

```powershell
D:\ACloud\.venv\Scripts\python.exe -m unittest tests.test_wall_snapshot_operations
# Expected: Ran ... tests ... OK
```

**Commit**

`feat: add reversible final-wall brush operations`

## Task 2: Add read-only wall-version catalog loading

**Files**

- Create `core/map_editing/version_storage.py`
- Create `tests/test_wall_version_storage.py`
- Modify `core/map_editing/__init__.py`

**Test first**

```python
def test_no_version_metadata_uses_the_original_wall_layer(self):
    base = np.zeros((3, 4), dtype=np.uint8)
    with tempfile.TemporaryDirectory() as root:
        catalog = load_wall_version_catalog(Path(root), base)
    self.assertIsNone(catalog.active_version)
    np.testing.assert_array_equal(base, catalog.active_wall_layer)
```

```python
def test_active_version_loads_one_complete_snapshot_and_rejects_bad_shape(self):
    # Write config wall_versions active_version=v0001 and a valid 4x5 snapshot.
    # Assert catalog.active_wall_layer is the snapshot.  Then rewrite it as 3x5
    # and assert ValueError without modifying config or snapshot.
```

**Implementation**

```python
VERSION_DIRNAME = "wall_versions"
VERSION_CONFIG_KEY = "wall_versions"
VERSION_FORMAT = 1

@dataclass(frozen=True)
class WallVersion:
    id: str
    file: str
    created_at: str
    parent_version: str | None

@dataclass(frozen=True)
class WallVersionCatalog:
    versions: tuple[WallVersion, ...]
    active_version: str | None
    active_wall_layer: np.ndarray

def load_wall_version_catalog(map_folder: str | Path, base_wall_layer: np.ndarray) -> WallVersionCatalog:
    # Return a copy of base_wall_layer when config has no version catalog.
    # Otherwise validate manifest paths, active id, npz key and shape, and return
    # the active complete snapshot.  Never consult legacy masks here.
```

**Verify**

```powershell
D:\ACloud\.venv\Scripts\python.exe -m unittest tests.test_wall_version_storage
# Expected: raw-map and valid/invalid snapshot cases pass
```

**Commit**

`feat: load complete wall snapshot versions`

## Task 3: Atomically save, activate, and migrate wall versions

**Files**

- Modify `core/map_editing/version_storage.py`
- Modify `tests/test_wall_version_storage.py`

**Test first**

```python
def test_save_new_version_keeps_prior_snapshot_and_makes_the_new_version_active(self):
    # Save v0001, save a changed layer, assert v0002 is active, v0001 bytes are
    # unchanged, parent_version is v0001, and config keeps unrelated fields.
```

```python
def test_migrate_legacy_masks_creates_v0001_without_changing_base_or_legacy_files(self):
    # Save old add/erase masks, migrate, assert v0001 equals composed result,
    # map_data.npz-equivalent base array and wall_overrides.npz bytes remain intact.
```

**Implementation**

```python
def save_new_wall_version(
    map_folder: str | Path,
    wall_layer: np.ndarray,
    *,
    parent_version: str | None,
) -> WallVersion:
    """Write wall_versions/vNNNN.npz and atomically update active_version."""

def activate_wall_version(map_folder: str | Path, version_id: str, shape: tuple[int, int]) -> WallVersion:
    """Validate an existing complete snapshot, then atomically update only active_version."""

def migrate_legacy_wall_overrides(map_folder: str | Path, base_wall_layer: np.ndarray) -> WallVersion | None:
    """Create v0001 from old effective walls only if no version catalog exists."""
```

All `.npz` and `config.json` changes must use the existing temporary-file-and-replace helpers. Paths stored in metadata must remain beneath `wall_versions/` and ids must match `v[0-9]{4,}`.

**Verify**

```powershell
D:\ACloud\.venv\Scripts\python.exe -m unittest tests.test_wall_version_storage
# Expected: version sequencing, activation, atomic metadata merge, and migration pass
```

**Commit**

`feat: persist and migrate wall snapshot versions`

## Task 4: Make navigation load the active complete version directly

**Files**

- Modify `core/localization/map_package.py`
- Create `tests/test_navigation_wall_version_loading.py`
- Modify `tests/test_navigation_wall_override_loading.py`

**Test first**

```python
def test_navigation_uses_the_active_complete_snapshot_without_applying_legacy_masks(self):
    # Base says wall at (1, 1); legacy mask says erase; active v0002 says wall.
    # NavigationCore must expose v0002's wall at (1, 1), proving only the active
    # snapshot is the navigation input.
```

**Implementation**

```python
with np.load(nav_core.map_data_path, allow_pickle=False) as data:
    base_wall_layer = data["wall_layer"]
    catalog = load_wall_version_catalog(Path(nav_core.map_data_path).parent, base_wall_layer)
    nav_core.wall_layer = catalog.active_wall_layer
    nav_core.nav_wall_layer = derive_navigation_wall_layer(
        nav_core.wall_layer,
        erode_iterations=nav_core.nav_wall_erode_iterations,
    )
```

Keep a narrowly-scoped legacy compatibility fallback only while a map lacks a version catalog; it must not execute when `wall_versions.active_version` exists.

**Verify**

```powershell
D:\ACloud\.venv\Scripts\python.exe -m unittest tests.test_navigation_wall_version_loading tests.test_navigation_core
# Expected: selected snapshot drives localization and obstacle wall layers
```

**Commit**

`feat: load active wall version in navigation`

## Task 5: Replace mask-based editor state with a checked-out wall draft

**Files**

- Modify `gui/modes/map_editor/controller.py`
- Create `tests/test_wall_version_editor_controller.py`
- Keep `tests/test_map_editor_controller.py` only for obsolete compatibility behavior or replace it explicitly

**Test first**

```python
def test_controller_checks_out_active_version_and_erasing_updates_preview_wall_directly(self):
    controller = MapEditorController.load(folder)
    controller.apply_brush((10, 10), radius=2, mode="erase")
    self.assertEqual(0, controller.working_wall_layer[10, 10])
    self.assertFalse(np.any(controller.erase_mask))  # removed API/state
```

```python
def test_confirm_save_creates_new_active_version_without_mutating_the_checked_out_version(self):
    # v0001 is active, edit and save, assert v0002 is active and v0001 content is unchanged.
```

**Implementation**

```python
@dataclass
class MapEditorController:
    map_folder: Path
    source_version_id: str | None
    working_wall_layer: np.ndarray
    versions: tuple[WallVersion, ...]
    active_version_id: str | None

    @property
    def preview_wall_layer(self) -> np.ndarray:
        return self.working_wall_layer

    def confirm_as_new_version(self) -> WallVersion:
        self._finish_active_stroke()
        version = save_new_wall_version(
            self.map_folder,
            self.working_wall_layer,
            parent_version=self.source_version_id,
        )
        self.source_version_id = self.active_version_id = version.id
        self._saved_snapshot = self.working_wall_layer.copy()
        return version
```

Switching a checked-out version with dirty changes must require an explicit discard decision in the widget; controller exposes a non-mutating `checkout_version(version_id)` after that decision.

**Verify**

```powershell
D:\ACloud\.venv\Scripts\python.exe -m unittest tests.test_wall_version_editor_controller
# Expected: direct erase appearance, undo/redo, save-as-new, checkout, and legacy migration pass
```

**Commit**

`refactor: edit complete wall version drafts`

## Task 6: Replace overlay-centric controls with version-centric UI

**Files**

- Modify `gui/modes/map_editor/widget.py`
- Modify `gui/modes/map_editor/canvas.py`
- Modify `tests/test_map_editor_canvas.py`
- Create `tests/test_wall_version_editor_widget.py`

**Test first**

```python
def test_erased_preview_pixel_is_black_and_has_no_cyan_overlay(self):
    # Load a wall, erase a point through the controller/widget, then inspect the
    # canvas layer references: it has the final preview wall and no erase mask.
```

```python
def test_save_button_creates_a_new_version_and_version_picker_can_activate_an_old_one(self):
    # Assert the version combo lists v0001/v0002, saving selects v0002, and
    # activating v0001 updates config without changing either snapshot file.
```

**Implementation UI contract**

```text
版本
  当前导航版本：v0002
  [v0001 / v0002 / 原始地图 ▼] [作为编辑基线]
  [设为导航版本]

编辑操作
  [撤销] [重做]
  [放弃草稿]
  [确认并保存为新版本]
```

- Pass only `working_wall_layer` to `WallEditorCanvas.set_wall_layer(...)`.
- Remove red/cyan operation overlays and update the legend to “白色：当前版本的墙体；黑色：空白区域”。
- Preserve the existing right/middle/Space/Shift panning behavior and ordinary-left-click brush drawing.
- Use a confirmation dialog only at version creation/dirty checkout boundaries, not for every brush stamp.

**Verify**

```powershell
$env:QT_QPA_PLATFORM = 'offscreen'
D:\ACloud\.venv\Scripts\python.exe -m unittest tests.test_map_editor_canvas tests.test_wall_version_editor_widget tests.test_map_editor_page_in_main_window
# Expected: direct final-wall preview and version controls pass
```

**Commit**

`feat: add versioned wall editor workflow`

## Task 7: Run integrated compatibility and real-map validation

**Files**

- Modify affected tests only if an integration failure identifies a gap.

**Verification**

```powershell
$env:PYTHONPATH = 'D:\ACloud\auto_modules;D:\ACloud\auto_modules\virtual_gamepad\ui;D:\ACloud\auto_modules\virtual_gamepad\client\python'
$env:QT_QPA_PLATFORM = 'offscreen'
D:\ACloud\.venv\Scripts\python.exe -m unittest `
  tests.test_wall_snapshot_operations `
  tests.test_wall_version_storage `
  tests.test_navigation_wall_version_loading `
  tests.test_wall_version_editor_controller `
  tests.test_wall_version_editor_widget `
  tests.test_map_editor_canvas `
  tests.test_map_editor_page_in_main_window `
  tests.test_navigation_core `
  tests.test_navigation_ui_layout `
  tests.test_gamepad_page_in_main_window
```

Then use a copy of `map_data/poe2/` to:

1. migrate the old masks to `v0001`;
2. erase a visible wall and verify the preview pixel is black;
3. save `v0002` and verify `v0001` byte hash remains unchanged;
4. activate `v0001`, create `NavigationCore`, and verify it reads `v0001` directly;
5. verify the copied `map_data.npz` byte hash is unchanged.

**Commit**

`test: verify wall snapshot version workflow`
