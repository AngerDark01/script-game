# PoE2 数据采集测试页实施计划

## Goal

在 PoE2 业务页内部加入一个状态隔离的“数据采集测试”页签，用于反复预览小地图截图、初始化/获取原生地图、显式保存测试归档和查看诊断信息，不改变绘图模式或现有实时定位页行为。

## Architecture Overview

- `Poe2LiveTerrainPage` 保留现有定位页属性和生命周期，并在内部使用 `QTabWidget` 承载“实时地形定位”和“数据采集测试”。
- 新增 `Poe2CaptureTestPage`，只依赖注入的 `Poe2TerrainService`、`TerrainDebugArchive`、监控配置读取器和截图预览回调；不持有定位运行时。
- composition 创建独立的测试 `Poe2TerrainService`/采集适配器和显式归档对象；测试页与定位页不共享可变 `MemoryTerrainStore`。
- 截图预览使用已有 `MonitorFrameSource`/PoE2 monitor profile 配置和 recognizer 预处理能力；地图转换仍由 `Poe2TerrainService` 完成。
- 所有测试页面操作写入现有 `auto_modules.poe2_live_terrain` 日志，失败清理旧预览。

## Tech Stack

- Python 3.12+、PySide6、NumPy、OpenCV。
- pytest、pytest-qt 不要求新增依赖；现有测试使用 `QT_QPA_PLATFORM=offscreen`。
- 页面截图格式使用现有 `frame_pixmap()`；地图显示使用现有 `present_snapshot()`/`ScalableMapWidget`。

## Task 1: Extend Composition With Isolated Capture-Test Dependencies

Files:

- `src/auto_modules/ui/modes/poe2/composition.py`
- `tests/test_poe2_composition.py` (new)

Test first:

1. Add a fake screen capture and recognizer fixture.
2. Assert `build_poe2_live_terrain_composition(... )` exposes `capture_test_service`, `capture_test_archive`, and `capture_preview` in addition to existing fields.
3. Assert the test service is not the same object as `service`, and both service stores start empty.
4. Assert `capture_preview(config)` delegates to the configured binding and returns the backend frame.

Verify the test fails before implementation:

```powershell
$env:PYTHONPATH = 'D:\ACloud\auto_modules\src'
D:\ACloud\.venv\Scripts\python.exe -m pytest tests/test_poe2_composition.py -q
# Expected before implementation: AttributeError/failed assertions for missing test dependencies
```

Implementation:

- Extend `Poe2LiveTerrainComposition` with `capture_test_service`, `capture_test_archive`, and `capture_preview`.
- Create a second `Poe2CaptureAdapter` and `Poe2TerrainService(adapter=..., archive=None)` for the test page.
- Keep the existing runtime capture closure unchanged; expose a read-only preview closure that resolves the active profile and calls `MonitorFrameSource.capture()`.
- Construct one `TerrainDebugArchive` for the test page's explicit save button; do not auto-save test captures through the service.

Verify:

```powershell
$env:PYTHONPATH = 'D:\ACloud\auto_modules\src'
D:\ACloud\.venv\Scripts\python.exe -m pytest tests/test_poe2_composition.py -q
# Expected: all composition tests pass
```

## Task 2: Add The Isolated Capture-Test Page

Files:

- `src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py` (new)
- `tests/test_poe2_capture_test_page.py` (new)
- `src/auto_modules/ui/modes/poe2_live_terrain/__init__.py`

Test first:

- Build a fake service implementing `initialize`, `capture`, `reset`, and `snapshot`.
- Build a fake preview provider returning a small BGR NumPy frame or raising `RuntimeError`.
- Assert the page starts with disabled capture/save controls and no stale previews.
- Assert initialize enables capture, capture renders the map and metadata, and save calls the injected archive with the current snapshot.
- Assert preview success renders the frame and feature preview; preview failure clears both labels and reports the current error.
- Assert reset stops the timer and clears map, screenshot, metadata, and error state.

Verify failure:

```powershell
$env:PYTHONPATH = 'D:\ACloud\auto_modules\src'
$env:QT_QPA_PLATFORM = 'offscreen'
D:\ACloud\.venv\Scripts\python.exe -m pytest tests/test_poe2_capture_test_page.py -q
# Expected before implementation: ModuleNotFoundError for capture_test_page
```

Implementation contract:

```python
class Poe2CaptureTestPage(QWidget):
    def __init__(self, service, *, archive, monitor_config, preview_provider, recognizer=None, parent=None): ...
    def initialize_session(self) -> None: ...
    def capture_map(self) -> None: ...
    def save_map(self) -> None: ...
    def refresh_preview(self) -> None: ...
    def start_preview(self) -> None: ...
    def stop_preview(self) -> None: ...
    def reset_session(self) -> None: ...
    def shutdown(self) -> None: ...
```

UI requirements:

- Controls: `监控配置` (when a dialog provider is supplied), `刷新截图`, `开始截图监控`, `停止截图监控`, `初始化`, `获取当前地图`, `保存当前地图`, `清空测试状态`.
- Preview area: current screenshot, preprocessed/feature preview if recognizer is available, and current terrain map.
- Status area: session state, last preview/capture/save error, archive path, area/instance/size metadata.
- Use a `QTimer` only for screenshot preview. It must never call `runtime.tick()` or localization code.
- On every failure call `clear()`/`set_image(None)` for the affected preview before displaying the new error.
- Log with `step=test_page.preview_*`, `step=test_page.initialize_*`, `step=test_page.capture_*`, `step=test_page.save_*`, and `step=test_page.reset`.

Verify:

```powershell
$env:PYTHONPATH = 'D:\ACloud\auto_modules\src'
$env:QT_QPA_PLATFORM = 'offscreen'
D:\ACloud\.venv\Scripts\python.exe -m pytest tests/test_poe2_capture_test_page.py -q
# Expected: all page state, error cleanup, timer, and save tests pass
```

## Task 3: Embed The Test Page As A PoE2 Tab

Files:

- `src/auto_modules/ui/modes/poe2_live_terrain/page.py`
- `src/auto_modules/ui/main_window.py`
- `tests/test_main_window_poe2_terrain_page.py`
- `tests/test_poe2_live_terrain_page.py`

Test first:

- Assert a page constructed without test dependencies still exposes the existing live widgets and has one live tab, preserving existing unit-test fixtures.
- Assert a page constructed with test dependencies exposes two tabs named `实时地形定位` and `数据采集测试`.
- Assert switching/closing the PoE2 page calls `shutdown()` on the test page and leaves the existing runtime shutdown behavior intact.
- Update the main-window composition fake with optional test fields and assert the PoE2 mode remains at stacked index 7 while the page instance remains `Poe2LiveTerrainPage`.

Verify failure:

```powershell
$env:PYTHONPATH = 'D:\ACloud\auto_modules\src'
$env:QT_QPA_PLATFORM = 'offscreen'
D:\ACloud\.venv\Scripts\python.exe -m pytest tests/test_main_window_poe2_terrain_page.py tests/test_poe2_live_terrain_page.py -q
# Expected before implementation: missing tab/test-page assertions
```

Implementation:

- Add optional constructor arguments to `Poe2LiveTerrainPage` for the test service/archive/preview dependencies.
- Move the existing direct layout into a live-tab widget without changing existing public widget attributes or runtime methods.
- Add a `QTabWidget` as the page's root layout and insert the live tab first and the test page second when dependencies are present.
- In `MainWindow.setup_ui()`, pass the new composition fields with `getattr(..., None)` compatibility so existing composition fakes remain valid.
- In `Poe2LiveTerrainPage.shutdown()` and `stop_runtime()`, stop the test page timer and reset its state only during full shutdown; switching tabs must not reset its captured snapshot.

Verify:

```powershell
$env:PYTHONPATH = 'D:\ACloud\auto_modules\src'
$env:QT_QPA_PLATFORM = 'offscreen'
D:\ACloud\.venv\Scripts\python.exe -m pytest tests/test_main_window_poe2_terrain_page.py tests/test_poe2_live_terrain_page.py -q
# Expected: all existing live-page tests and new tab tests pass
```

## Task 4: Add Configuration Wiring And Regression Coverage

Files:

- `src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py`
- `src/auto_modules/ui/modes/poe2_live_terrain/page.py`
- `tests/test_poe2_capture_test_page.py`
- `tests/test_architecture_boundaries.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

Test first:

- Assert the test page reads the active profile at construction and refreshes it after the monitor dialog emits `config_saved`.
- Assert the test page never imports or instantiates `NavigationCore`, `MapLocalizer`, Host, LAN, virtual-gamepad, keyboard, or mouse execution adapters.
- Assert `Poe2LiveTerrainPage` and the test page can own separate fake services; resetting one does not change the other's state or snapshot.

Verify failure:

```powershell
$env:PYTHONPATH = 'D:\ACloud\auto_modules\src'
$env:QT_QPA_PLATFORM = 'offscreen'
D:\ACloud\.venv\Scripts\python.exe -m pytest tests/test_poe2_capture_test_page.py tests/test_architecture_boundaries.py -q
# Expected before implementation: missing isolation/configuration assertions
```

Implementation:

- Reuse `Poe2MonitorConfigDialog` and `Poe2ProfileToolbar` only through explicit injection or a small local wrapper; do not duplicate profile persistence.
- Keep capture-test profile/config changes scoped to the test page's preview provider. The underlying local profile file remains the shared PoE2 monitor configuration source.
- Update `CODEBASE.md` with the new page and composition symbols and `ITERATION_LOG.md` with the boundary and verification result.

Verify:

```powershell
$env:PYTHONPATH = 'D:\ACloud\auto_modules\src'
$env:QT_QPA_PLATFORM = 'offscreen'
D:\ACloud\.venv\Scripts\python.exe -m pytest tests/test_poe2_capture_test_page.py tests/test_poe2_live_terrain_page.py tests/test_main_window_poe2_terrain_page.py tests/test_architecture_boundaries.py -q
D:\ACloud\.venv\Scripts\python.exe -m compileall -q src
git diff --check
# Expected: focused suite passes; compileall and diff check exit 0
```

## Task 5: Manual Smoke Verification

Files:

- No source changes expected; inspect `data/logs/poe2_live_terrain.log` after the run.

Steps:

1. Start `D:\ACloud\.venv\Scripts\python.exe main.py`.
2. Open `PoE2 地形` and switch to `数据采集测试`.
3. Open monitor configuration, bind the minimap region or center, and click `刷新截图`.
4. Confirm screenshot preview updates and no old frame remains after an intentional invalid binding.
5. With PoE2 running, click `初始化`, then `获取当前地图`, then `保存当前地图`.
6. Confirm map metadata, archive path, and `step=test_page.*` log records.
7. Switch back to `实时地形定位`; confirm its current map/runtime state was not reset.
8. Stop preview and close the application; confirm no test timer continues.

Expected result: the test page can repeatedly collect and inspect screenshots/maps, while no localization or real-input side effects occur.
