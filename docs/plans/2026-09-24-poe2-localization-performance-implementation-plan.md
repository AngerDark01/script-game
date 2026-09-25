# PoE2 定位参数与帧率实施计划

## Goal

提供可保存的 PoE2 首帧质量门与帧率设置，并让正式定位在后台串行运行，减少重复图像处理并保持界面响应。

## Architecture Overview

参数归 `Poe2MonitorConfig`；通用 HSV 识别提供一次预处理的证据接口；PoE2 session 在 worker 中独占运行；GUI 只消费当前会话最新状态，地图底图沿用现有缓存。

## Tech Stack

Python 3、PySide6、OpenCV、NumPy、pytest；PoE2 参数随现有 JSON profile 保存。

### Task 1: 配置契约

Files: `src/auto_modules/features/poe2/live_terrain/monitor_config.py`, `tests/poe2_live_terrain/test_monitor_config_profiles.py`。

先写旧 JSON 默认值、新字段 round-trip 和非法范围测试，确认失败；再加五个 dataclass 字段及 `as_dict`/`from_dict`。验证：`D:/ACloud/.venv/Scripts/python.exe -m pytest tests/poe2_live_terrain/test_monitor_config_profiles.py -q`。

### Task 2: PoE2 组合注入

Files: `src/auto_modules/features/poe2/live_terrain/experimental/hybrid_localization/composition.py`, `tests/test_poe2_composition.py`。

先断言业务配置传入 registrar，然后让 `_poe2_first_frame_registration_config(config)` 注入质量门，保持通用默认值。验证：`D:/ACloud/.venv/Scripts/python.exe -m pytest tests/test_poe2_composition.py -q`。

### Task 3: 设置窗口

Files: `src/auto_modules/ui/modes/poe2_live_terrain/config_panel.py`, `src/auto_modules/ui/modes/poe2_live_terrain/monitor_dialog.py`, `tests/poe2_live_terrain/test_config_panel.py`, `tests/test_poe2_monitor_dialog.py`。

先测新字段回显、保存、恢复默认值；然后在现有 PoE2 弹窗中添加“定位与性能”区，使用数字步进控件，监控运行中沿用现有禁用策略。验证：`D:/ACloud/.venv/Scripts/python.exe -m pytest tests/poe2_live_terrain/test_config_panel.py tests/test_poe2_monitor_dialog.py -q`。

### Task 4: 一次预处理证据

Files: `src/auto_modules/core/vision/hsv/combined.py`, `src/auto_modules/core/vision/hsv_recognizer.py`, `src/auto_modules/features/poe2/live_terrain/experimental/hybrid_localization/composition.py`, `tests/test_recognizer_optimized.py`, `tests/test_poe2_composition.py`。

先加同帧输出等价与预处理次数测试；再让组合证据共用一次墙体预处理，兼容测试中的非 HSV recognizer。验证：`D:/ACloud/.venv/Scripts/python.exe -m pytest tests/test_recognizer_optimized.py tests/test_poe2_composition.py -q`。

### Task 5: 后台串行运行与线程本地捕获

Files: `src/auto_modules/ui/modes/poe2_live_terrain/localization_worker.py`, `src/auto_modules/ui/modes/poe2_live_terrain/page.py`, `src/auto_modules/ui/modes/poe2/composition.py`, `tests/test_poe2_live_terrain_monitoring.py`, `tests/test_poe2_composition.py`。

先测耗时 tick 不阻塞 UI、停止/换图丢弃旧结果、worker 无重入、worker 建立独立 MSS 句柄；再接入 worker。测试假 runtime 继续支持同步调用，正式 `Poe2HybridProductRuntime` 使用后台调度。验证：`D:/ACloud/.venv/Scripts/python.exe -m pytest tests/test_poe2_live_terrain_monitoring.py tests/test_poe2_composition.py -q`。

### Task 6: 显示节流与性能诊断

Files: `src/auto_modules/ui/modes/poe2_live_terrain/page.py`, `src/auto_modules/features/poe2/live_terrain/hybrid_product_runtime.py`, `src/auto_modules/features/poe2/live_terrain/experimental/hybrid_localization/session.py`, `tests/test_poe2_live_terrain_page.py`, `tests/poe2_live_terrain/test_hybrid_product_runtime.py`。

先测位置刷新上限、预览刷新上限及实际 FPS 计数；再加入分段耗时、日志和最新状态覆盖策略。验证：`D:/ACloud/.venv/Scripts/python.exe -m pytest tests/test_poe2_live_terrain_page.py tests/poe2_live_terrain/test_hybrid_product_runtime.py -q`。

### Task 7: 集成与断点

Files: `docs/POE2_LIVE_TERRAIN_CURRENT_STATE.md`, `CODEBASE.md`, `ITERATION_LOG.md` 以及上述受影响测试。

运行 PoE2 定位、配置、正式页面回归，`compileall` 和 `git diff --check`；人工沿初始化、取图、开始、首帧、移动、恢复、停止、换图链路检查所有权和状态门。记录真实游戏尚未验证的项目。
