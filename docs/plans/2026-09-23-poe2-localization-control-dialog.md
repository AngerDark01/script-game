# PoE2 定位控制弹窗与 A/B 实验接线

## Goal

修复 PoE2 多帧 A/B 实验工厂未注入导致的启动失败，并将方案 A/B 的控制项从主页面移到独立非模态窗口，让主页面只展示截图、特征、地图和人物位置。

## Architecture Overview

- 保留 `Poe2LiveTerrainPage` 作为展示页：初始化、获取地图、监控配置、截图预览、匹配特征、地图和人物定位状态。
- 新增独立非模态 `Poe2LocalizationControlDialog`，复用现有 `Poe2CaptureTestPage` 的 A/B session/factory，不复制定位算法。
- `MainWindow` 将 composition 中已有的 `multiframe_localization_factory` 正确传入页面；这是当前“请先获取地图并注入多帧实验工厂”的根因修复。
- 控制弹窗持有当前地图快照和监控配置的引用，通过页面回调消费实时 `PositionEstimate`/诊断；关闭弹窗不停止定位，停止按钮才停止 session。
- 主页面通过 typed presentation state 更新地图叠加和人物位置；不在主页面暴露混合定位控件或多帧策略细节。
- 默认方案 A、B 均开启；启动按钮只在地图已获取、两个工厂已注入且监控配置有效时可用。

## Tech Stack

Python 3.11+, PySide6, NumPy, existing PoE2 live-terrain session/coordinator and pytest Qt offscreen tests.

## Tasks

### Task 1: Reproduce and lock the missing factory wiring

Files: `tests/test_main_window_poe2_terrain_page.py`, `src/auto_modules/ui/main_window.py`.

Add a composition stub exposing `multiframe_localization_factory` and assert the created page forwards it to `capture_test_page`. The test must fail before the wiring fix, then pass after adding the constructor argument. Also preserve existing page indices and do not alter input/gamepad wiring.

Verify: `pytest -q tests/test_main_window_poe2_terrain_page.py`.

### Task 2: Extract a non-modal localization control dialog

Files: `src/auto_modules/ui/modes/poe2_live_terrain/localization_control_dialog.py`, `tests/test_poe2_localization_control_dialog.py`.

Create a QDialog with default-enabled A/B checkboxes, start/stop/reset/retry controls, status/position/diagnostics labels, and signals for configuration and lifecycle actions. It must be non-modal (`show`, not `exec`) and expose `set_snapshot`, `set_monitor_config`, `set_experiment_factories`, `set_state`, and `stop`. Use the existing capture-page session factories; no recognition or matching logic belongs in the dialog.

Verify: Qt offscreen tests cover default A/B enabled, start disabled before snapshot/factory, start enabled after both are present, stop/reset state transitions, and close without implicit stop.

### Task 3: Move A/B runtime ownership behind the dialog

Files: `src/auto_modules/ui/modes/poe2_live_terrain/page.py`, `src/auto_modules/ui/modes/poe2_live_terrain/localization_control_dialog.py`, `tests/test_poe2_live_terrain_page.py`.

Add one `定位控制` button to the display page. Remove the embedded hybrid/multiframe control groups from the main display page, keep only display labels and previews, and open one reusable non-modal dialog. Wire the current snapshot/config/factories into it after map capture and config changes. Forward accepted A/B state to the same presentation overlay used by the page; stopping or resetting clears the overlay but does not clear the captured map unless the map reset button is used.

Verify: page layout no longer contains hybrid control widgets, dialog receives both factories, captured map enables dialog start, and the display page still renders current frame and map.

### Task 4: Close the full runtime chain and verify with the current sample

Files: `src/auto_modules/ui/main_window.py`, `src/auto_modules/ui/modes/poe2/composition.py`, `docs/POE2_LIVE_TERRAIN_CURRENT_STATE.md`, `ITERATION_LOG.md`.

Run focused tests, compile checks, and the existing offline localization probe against the current native sample. Start the application, initialize, capture the map, open the control dialog, confirm A and B are enabled, and start the experiment. Record the actual startup result and any remaining matcher rejection in the breakpoint documents; do not claim visual localization success unless a position is confirmed.

Verify: focused PoE2/UI tests pass, `compileall` passes, `git diff --check` passes, and the live log contains factory injection plus A/B session start entries.
