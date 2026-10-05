## Goal

让 PoE2 实时跟随在启动和全局重定位恢复后先完成视觉同步，再发送稳定的程序输入，避免因输入延迟造成的旧帧被误判为定位失败。

## Architecture Overview

- 仅修改 PoE2 实验业务层的实时跟随状态机；双人同目标实验保持原有链路。
- 增加显式的 `cold_start` / `recovery_sync` 阶段，不用固定 sleep 代替状态判断。
- 冷启动阶段等待新的双人视觉帧，允许有限的瞬时视觉误差，不累计重定位计数。
- 首次有效新帧到达后才进入正常 `tracking`；恢复成功后禁止直接重新发出完整输入。
- 以捕获时间和单调递增帧序号判断新鲜度，并记录启动、恢复、宽限和实际位移证据。

## Tech Stack

Python 3、PySide Qt 定时器、pytest、现有 `CommandRoleTracker` 和 `SimulatedFollowRuntime`。

## Implementation Tasks

### Task 1: Add failing cold-start regression tests

Files: `tests/test_poe2_capture_test_page.py`

- 覆盖实时跟随启动后旧视觉帧不会触发重定位。
- 覆盖恢复后第一轮没有新视觉帧时不重新发送完整输入。
- 覆盖收到新鲜帧后才退出同步阶段并恢复输出。

Verify: `pytest -q tests/test_poe2_capture_test_page.py -k "cold_start or recovery_sync"`，先确认新增断言失败。

### Task 2: Implement explicit live-follow sync state

File: `src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py`

- 增加实时跟随同步状态和帧基线字段。
- `start_follow_experiment()` 初始化冷启动状态，不立即把旧帧作为稳定视觉证据。
- `_tick_follow_experiment_impl()` 在同步阶段抑制重定位计数，等待新鲜帧并限制首次输出。
- `_maybe_resume_dual_follow_after_relocalization()` 进入恢复同步而不是直接恢复正常跟随。
- 记录 `armed_at_ms`、`captured_at_ms`、`frame_age_ms`、同步状态和实际视觉位移。

Verify: 运行 Task 1 测试和 PoE2 跟随相关回归测试。

### Task 3: Verify and document

Files: `docs/POE2_LIVE_TERRAIN_CURRENT_STATE.md`, `CODEBASE.md`, `ITERATION_LOG.md`

- 记录冷启动状态机、停止循环根因和验证结果。
- 运行 `compileall`、`git diff --check` 及相关 pytest。

