## Goal

在 PoE2 双人实验跟随中实现任意角色的有界视觉失明恢复，同时保证后台丢帧不会吞掉重定位请求。

## Architecture Overview

通用纯状态对象管理每个 identity 的最后观测时间、位置与不确定性；PoE 双人 tracker 组合墙层位移和 marker，实验页只根据新截图及预算决定短步继续或释放。重定位 revision 是独立于最新图像的黏性事件。复用现有路线和手柄适配器，不发送真实输入做自动验收。

## Tech Stack

Python 3、NumPy/OpenCV、PySide6、pytest。现有环境 `D:/ACloud/.venv/Scripts/python.exe`。

### Task 1: 恢复 revision 不能被 latest-only 覆盖

Files: `tests/test_poe2_dual_motion_worker.py`, `src/auto_modules/ui/modes/poe2_live_terrain/dual_motion_worker.py`, `src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py`.

先写边沿状态被下一帧覆盖的失败测试：`_offer(edge); _offer(next); take_latest()` 仍交付 revision；页面只处理同一 revision 一次。执行 `D:/ACloud/.venv/Scripts/python.exe -m pytest tests/test_poe2_dual_motion_worker.py -q` 先见失败，再实现黏性 revision 并见通过。工作树含用户未提交改动，本计划不自动 commit。

### Task 2: 通用角色观测预算

Files: `tests/test_bounded_role_observation.py`, `src/auto_modules/core/localization/bounded_observation.py`, `src/auto_modules/core/localization/__init__.py`.

先测新观测、同帧不可续期、时间/误差耗尽、重现必须连续两帧以及 identity 相互独立；确认失败后实现纯状态对象。验证 `D:/ACloud/.venv/Scripts/python.exe -m pytest tests/test_bounded_role_observation.py -q`。

### Task 3: 双人 tracker 接入角色观测

Files: `tests/poe2_live_terrain/test_multiplayer_motion.py`, `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_localization/dual_motion.py`.

先测一名/两名角色 marker 丢失但墙层可信时不立即全局恢复；预算耗尽后只发一次 revision；候选重现经连续帧和预测范围后才更新身份。确认失败后接入通用对象，保留 `visible_identities`、`missing_identities`、误差与时间诊断。验证该文件测试。

### Task 4: 实验页跟随门与短脉冲

Files: `tests/test_poe2_capture_test_page.py`, `src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py`.

先测双向角色选择、任一角色失明时有限继续、墙层失败/帧过期/预算耗尽立即释放以及恢复后只从新可信截图续期。实现页面状态门与 `elapsed_ms <= 150` 的失明输出上限；输出仍经现有 adapter。验证采集页与跟随运行器聚焦测试。

### Task 5: 诊断、全链与断点同步

Files: `docs/POE2_LIVE_TERRAIN_CURRENT_STATE.md`, `CODEBASE.md`, `ITERATION_LOG.md` 及必要的聚焦测试。

在状态转换时限量保存原始局部帧/颜色 mask/候选特征及分配代价；不周期性保存全部帧。运行 PoE2 专项、采集页、worker、纯状态测试，`compileall` 和 `git diff --check`。逐跳人工复核截图→墙/marker→tracker→worker→页面→跟随→输出/释放，并在断点中区分离线验证与待用户实机验收。
