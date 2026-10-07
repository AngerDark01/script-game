# PoE2 跟随恢复链路实施计划

## Goal

实现“最新帧视觉优先、局部视觉次之、预测保持、内存快速重锚、全局异步恢复”的双人动态跟随恢复链，并确保任何普通异常不会自动结束跟随 session。

## Architecture Overview

- `RecoveryCoordinator` 统一选择视觉重试、局部 ROI、预测、内存重锚和全局恢复。
- 新帧存在时禁止直接进入内存重锚；内存只作为视觉证据不足或预测失控后的兜底。
- 首帧确认的 orientation/transform 只复用，不在跟随恢复中重新估计。
- 内存快速重锚一次读取双人，校验 area instance，并融合到预测状态。
- 全局恢复异步执行，保留 follow session、目标、输出租约和 generation。
- 所有恢复步骤输出阶段耗时和原因，旧 generation 结果不能覆盖当前 session。

## Tech Stack

Python 3、PySide/Qt 页面、NumPy/OpenCV 视觉处理、现有 PoE2 ProcessReader/Host 协议、pytest。

## Tasks

### Task 1: 建立恢复状态与诊断契约

Files:

- `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_follow/recovery/recovery_state.py`
- `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_follow/recovery/recovery_diagnostics.py`
- `tests/poe2_live_terrain/test_follow_recovery_state.py`

先写失败测试，覆盖状态枚举、恢复层级、冷却和诊断字段；再实现不可变状态/事件模型。验证：

```powershell
pytest -q tests/poe2_live_terrain/test_follow_recovery_state.py
python -m compileall src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_follow/recovery
```

### Task 2: 实现最新帧优先和局部 ROI 调度器

Files:

- `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_follow/recovery/recovery_coordinator.py`
- `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_follow/recovery/visual_recovery.py`
- `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_follow/recovery/local_reanchor.py`
- `tests/poe2_live_terrain/test_follow_recovery_coordinator.py`

先写测试验证：有新帧时先视觉、局部成功不读内存、无新帧才允许预测/内存候选；再实现 ROI 80/140/220 的短路搜索和 score 门槛。验证：

```powershell
pytest -q tests/poe2_live_terrain/test_follow_recovery_coordinator.py
```

### Task 3: 实现可缓存的双人内存快速重锚

Files:

- `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_localization/memory_anchors.py`
- `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_follow/recovery/memory_fast_reanchor.py`
- `tests/poe2_live_terrain/test_memory_fast_reanchor.py`
- `tests/poe2_live_terrain/test_multiplayer_first_frame.py`

先写注入 reader 测试验证 warm read 不重复解析、一次读取返回两角色、实例不一致拒绝、transform 不调用视觉注册；再实现 descriptor/layout/component 地址缓存和失败失效。验证：

```powershell
pytest -q tests/poe2_live_terrain/test_memory_fast_reanchor.py tests/poe2_live_terrain/test_multiplayer_first_frame.py
```

### Task 4: 接入预测融合、冷却和恢复升级

Files:

- `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_follow/recovery/recovery_policy.py`
- `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_follow/tracking/prediction_model.py`
- `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_follow/tracking/position_fusion.py`
- `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_follow/runtime.py`
- `tests/poe2_live_terrain/test_follow_recovery_policy.py`

先写测试覆盖 4 帧失配、50px 不确定度、8s 内存冷却、内存失败继续预测、动态跟随不进入 release；再接入 runtime。验证：

```powershell
pytest -q tests/poe2_live_terrain/test_follow_recovery_policy.py tests/poe2_live_terrain/test_multiplayer_follow_runtime.py
```

### Task 5: 接入页面 latest-only、异步全局恢复与 generation

Files:

- `src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py`
- `src/auto_modules/ui/modes/poe2_live_terrain/dual_motion_mixin.py`
- `src/auto_modules/ui/modes/poe2_live_terrain/dual_motion_worker.py`
- `tests/test_poe2_capture_test_page.py`
- `tests/test_poe2_dual_motion_worker.py`

先写页面/worker 生命周期测试，确认旧 generation 结果被丢弃、恢复任务不阻塞控制 tick、全局恢复期间 session 保留；再替换页面中的直接恢复分支。验证：

```powershell
pytest -q tests/test_poe2_capture_test_page.py tests/test_poe2_dual_motion_worker.py
```

### Task 6: Host 心跳、输出会话和性能验收

Files:

- `services/virtual_gamepad/host/src/VirtualGamepadHost/Runtime/ControllerRegistry.Program.cs`
- `src/auto_modules/adapters/virtual_gamepad/program_output.py`
- `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_follow/program_output.py`
- `tests/test_program_gamepad.py`
- `services/virtual_gamepad/host/tests/VirtualGamepadHost.Tests/ProgramOutputTests.cs`

先验证 session 失效只 rearm、不停止 follow；补充 warm read、ROI、runtime、output、全局恢复分段耗时日志。验证：

```powershell
pytest -q tests/test_program_gamepad.py tests/poe2_live_terrain
python -m compileall src
git diff --check
```

Host C# 测试需在具备 .NET SDK 的环境运行；当前环境若无 SDK，只记录阻塞，不绕过验证。

## Acceptance Criteria

- 有新帧时不会直接读内存。
- 局部视觉成功不会触发全局恢复。
- 内存快速重锚只在冷却和异常门槛满足时触发。
- 内存读取一次返回双人位置并复用首帧 transform。
- 普通异常不释放动态跟随 session。
- 全局恢复不阻塞控制 tick。
- Host session 失效可独立 rearm。
- 每个恢复阶段都有耗时、原因、结果和 generation 日志。
