# PoE2 双人运动定位实验计划

## Goal

在数据采集测试页连续显示两名角色的 native 地图位置，正常帧仅使用视觉证据；墙体跟踪失效时先局部纠偏，仍失败才对同一恢复轮次读取一次内存并重新做双人首帧配准。

## Architecture Overview

- 首帧保留现有 `DualFirstFrameExperiment` 的身份、角度、镜像、尺度和共同平移；双人运动层不引入人物中心假设或人物圆形 mask。
- `DualVisualTracker` 每帧只更新共同视口平移 `b_t = b_(t-1) - A d_t`，再以 `N_i = A p_i + b_t` 映射两名独立标记。标记缺失时只隐藏该身份；不发布陈旧坐标。
- 墙体失配时沿用有界地图匹配，在固定角度、镜像、比例下纠正平移。连续失配才进入恢复状态；一次恢复轮次只允许一次内存读取。
- UI 只组合截帧、识别、实验状态与绘制；正式定位页、单人定位、游戏输入和 LAN 不改动。

## Tech Stack

Python 3.11+、NumPy、OpenCV、PySide6、pytest。

## Tasks

### Task 1: 双人运动契约与纯视觉跟踪

Files: `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_localization/dual_motion.py`, `tests/poe2_live_terrain/test_multiplayer_motion.py`.

先写失败测试，覆盖共同墙体移动、两人不同步运动、标记缺失、身份歧义、旋转/镜像和突跳。然后实现不可变帧结果与有状态跟踪器。关键计算复用 `estimate_bounded_displacement`、`transform_local_displacement`、`transform_local_point`。

Verify: `D:/ACloud/.venv/Scripts/python.exe -m pytest -q tests/poe2_live_terrain/test_multiplayer_motion.py`，先看到新测试失败，实施后全部通过。

### Task 2: 局部纠偏与恢复门

Files: 同 Task 1；`src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_localization/__init__.py`。

先补失败测试：墙体位移失败后只做有界匹配；连续失败才请求恢复；同一 revision 不重复请求；纠偏成功不读取内存。接入现有 `LocalMapMatcher` 和固定变换，不做全图视觉搜索。

Verify: 同 Task 1，并运行 `tests/poe2_live_terrain/test_multiplayer_first_frame.py`。

### Task 3: 数据采集测试页实时入口

Files: `src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py`, `tests/test_poe2_capture_test_page.py`。

先写失败 UI 测试：启动后首帧只读一次双人锚点，后续帧不读；停止和换图清空跟踪状态；失效轮次最多触发一次双人重配准。实施独立计时器、按钮、日志与两人叠加显示，不影响单人计时器。

Verify: `D:/ACloud/.venv/Scripts/python.exe -m pytest -q tests/test_poe2_capture_test_page.py tests/poe2_live_terrain/test_multiplayer_motion.py`。

### Task 4: 验证和断点

Files: `docs/POE2_LIVE_TERRAIN_CURRENT_STATE.md`, `CODEBASE.md`, `ARCHITECTURE_ITERATION_LOG.md`。

回放可用连续样本，检查首帧及运动阶段的方向、比例、坐标和耗时日志；运行聚焦回归、Ruff、编译和 `git diff --check`。明确记录实机尚未验证的部分，不能把合成序列通过写成实机通过。
