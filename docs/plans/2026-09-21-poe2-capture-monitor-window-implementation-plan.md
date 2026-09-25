# PoE2 截图监控与对比样本窗口实施计划

## Goal

为 PoE2 数据采集测试页增加独立截图监控窗口，并把同一帧的原图、预处理图、匹配特征和当前地形作为可追溯、不可覆盖的对比样本原子保存。

## Architecture Overview

新增 PoE2 业务层 `CaptureEvidence` 与 `CaptureSampleArchive`，负责不可变证据帧、PNG 编码、manifest、哈希、原子目录发布和历史读取。新增 UI 层 `Poe2CaptureMonitorWindow`，只组合现有截图 provider、recognizer、monitor config 和 terrain snapshot provider。测试页只管理窗口单例与退出清理，不承担归档细节，也不修改绘图模式。

## Tech Stack

Python 3.11、NumPy、OpenCV、PySide6、pytest。

### Task 1: 定义不可变截图证据帧

Files:

- `src/auto_modules/features/poe2/live_terrain/capture_samples.py`
- `tests/poe2_live_terrain/test_capture_samples.py`

步骤：

1. 先写测试，验证原图、预处理图和特征图会被复制并设为只读，时间戳和配置 payload 被固定。
2. 运行 `D:\ACloud\.venv\Scripts\python.exe -m pytest tests/poe2_live_terrain/test_capture_samples.py -q`，预期首次失败于模块不存在。
3. 实现 `CaptureEvidence` frozen dataclass，字段为 `captured_at`、`raw`、`processed`、`feature` 和 `monitor_config`；在 `__post_init__` 中复制数组、拒绝空数组并设置只读。
4. 重跑测试，预期通过。

### Task 2: 实现原子样本归档和历史读取

Files:

- `src/auto_modules/features/poe2/live_terrain/capture_samples.py`
- `src/auto_modules/features/poe2/live_terrain/__init__.py`
- `tests/poe2_live_terrain/test_capture_samples.py`

步骤：

1. 先写测试覆盖四图保存、无地形时三图保存、manifest 哈希、唯一目录、失败不发布半成品、历史列表与加载。
2. 实现 `CaptureSampleArchive.save/list_samples/load`，使用同级临时目录写完全部 PNG 和 `sample.json` 后再 `os.replace`，目录冲突使用递增后缀。
3. 运行同一测试文件，预期全部通过。

### Task 3: 新增独立监控窗口及当前帧失效规则

Files:

- `src/auto_modules/ui/modes/poe2_live_terrain/capture_monitor_window.py`
- `tests/test_poe2_capture_monitor_window.py`

步骤：

1. 先写 Qt 测试覆盖打开自动刷新、一次刷新只截图一次、三类图来自同一帧、刷新失败清空 evidence、无 evidence 拒绝保存、关闭停止定时器。
2. 实现 `Poe2CaptureMonitorWindow`，注入 `preview_provider`、`recognizer`、`monitor_config_provider`、`terrain_snapshot_provider` 和 `sample_archive`。
3. 窗口提供开始、停止、刷新、保存、打开目录按钮，以及原图、预处理、特征、地形四个视图。
4. 运行窗口测试，预期通过。

### Task 4: 增加历史样本切换和相邻对比

Files:

- `src/auto_modules/ui/modes/poe2_live_terrain/capture_monitor_window.py`
- `tests/test_poe2_capture_monitor_window.py`

步骤：

1. 先写测试覆盖上一个/下一个边界、图层切换、缺失地形占位和当前/上一个并排显示。
2. 增加历史索引、图层选择 `QComboBox` 和两个对比视图。
3. 运行窗口测试，预期通过。

### Task 5: 接入数据采集测试页并保证窗口单例

Files:

- `src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py`
- `src/auto_modules/ui/modes/poe2_live_terrain/__init__.py`
- `src/auto_modules/ui/modes/poe2/composition.py`
- `tests/test_poe2_capture_test_page.py`
- `tests/test_poe2_composition.py`

步骤：

1. 先写测试覆盖按钮存在、重复打开复用同一窗口、配置变化使用最新值、shutdown 关闭窗口。
2. composition 注入 `CaptureSampleArchive(root / "poe2_live_terrain_test" / "samples")`。
3. 测试页添加“打开截图监控窗口”按钮并管理 `_capture_monitor_window`。
4. 运行相关测试，预期通过。

### Task 6: 更新断点与代码地图并完成回归

Files:

- `docs/POE2_LIVE_TERRAIN_CURRENT_STATE.md`
- `CODEBASE.md`
- `ITERATION_LOG.md`

验证命令：

```powershell
D:\ACloud\.venv\Scripts\python.exe -m pytest tests/poe2_live_terrain tests/test_poe2_capture_test_page.py tests/test_poe2_capture_monitor_window.py tests/test_poe2_composition.py tests/test_poe2_live_terrain_page.py tests/test_main_window_poe2_terrain_page.py -q
D:\ACloud\.venv\Scripts\python.exe -m compileall -q src tests
git diff --check
```

预期所有相关测试通过、编译通过、无差异格式错误。最后启动主应用，人工确认窗口打开、监控停止、样本保存和历史切换。

