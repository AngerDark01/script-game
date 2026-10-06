# PoE2 实验代码 A0→C5 模块化实施计划

## Goal

把 PoE2 实验代码从单体页面迁移为分层实验运行时，同时保持现有定位、跟随、移动探针和恢复行为。

## Architecture Overview

迁移采用兼容 façade → 控制器组合 → 独立实验运行时三步法。页面保留旧方法名，控制器通过显式端口访问截图、内存、窗口和虚拟手柄，纯模块不依赖 Qt 或 Windows API。

## Tech Stack

- Python 3.11+
- PySide6（仅 UI 层）
- pytest
- dataclasses、Protocol、collections.abc
- 现有 PoE2 live terrain 实验模块和 fake/replay 测试设施

## 阶段任务

### A0：盘点与迁移基线

文件：`docs/POE2_EXPERIMENT_REFACTOR_TASK.md`、`docs/plans/2026-10-06-poe2-experiment-module-inventory.md`、`ITERATION_LOG.md`

动作：列出页面方法、状态字段、外部副作用、测试覆盖和调用链；为每个方法标记目标模块、输入、输出和迁移风险。

验证：`python tools/experiments/poe2_live_terrain/audit_page_surface.py`；人工核对 CodeGraph 调用路径；记录基线测试结果。

### A1：状态模型

文件：`experimental/application/models.py`、`experimental/follow/models.py`、`experimental/recovery/models.py`、对应 `tests/poe2_live_terrain/test_experiment_models.py`

动作：把页面中的 session、角色、视觉观测、恢复 episode、输出命令和诊断快照定义为不可变或明确可变的 dataclass；页面字段暂时通过转换函数读写。

验证：先写模型构造、复制、序列化和默认值失败测试；实现后运行 `pytest -q tests/poe2_live_terrain/test_experiment_models.py`。

### A2：恢复控制器

文件：`experimental/recovery/policy.py`、`experimental/recovery/scheduler.py`、`experimental/recovery/foreground_guard.py`、`experimental/recovery/controller.py`、`tests/poe2_live_terrain/test_experiment_recovery_controller.py`

动作：提取 episode 去重、8 秒停滞门、5/10/15 秒退避、明确 recovery evidence 和 250ms 前台缓存；页面旧方法改为调用 controller。

接口草案：

```python
class RecoveryController:
    def observe(self, observation: RecoveryObservation) -> RecoveryDecision: ...
    def schedule_retry(self, reason: str) -> RetryDecision: ...
    def clear(self, reason: str) -> None: ...
```

验证：覆盖同一 episode 一次 claim、progress_observed 不恢复、None evidence 不崩溃、retry 退避和窗口缓存。

### A3：双人视觉运行时

文件：`experimental/multiplayer/worker_runtime.py`、`experimental/multiplayer/frame_router.py`、`experimental/multiplayer/controller.py`、`tests/poe2_live_terrain/test_experiment_dual_motion_controller.py`

动作：提取 worker generation、首帧结果、视觉帧、失败、完成和恢复重启；页面只订阅事件并更新预览。

验证：fake worker 覆盖首帧成功、worker 失败、旧 generation、非前台帧、恢复中保留跟随会话。

### A4：跟随运行时

文件：`experimental/follow/target_sources.py`、`experimental/follow/observation_fusion.py`、`experimental/follow/controller.py`、`tests/poe2_live_terrain/test_experiment_follow_controller.py`

动作：统一点击目标、P1/P2 目标、外部目标和模拟目标；把视觉位置、命令预测、速度估计和到达判断集中到 controller。

验证：同目标和实时跟随走同一底层；视觉丢失后继续有界预测；视觉确认前不进入等待到达；目标更新不重建会话。

### A5：移动探针

文件：`experimental/probes/move_probe.py`、`experimental/probes/dual_target_probe.py`、`experimental/probes/follow_probe.py`、对应测试文件。

动作：提取点击移动、双人同目标和跟随探针；页面保留按钮包装。

验证：目标点击、路径决策、输出命令和停止/恢复状态均通过 fake adapter 回放。

### B1：统一生命周期

文件：`experimental/application/runtime.py`、`session.py`、`events.py`、`tests/poe2_live_terrain/test_experiment_runtime.py`

动作：统一 IDLE/STARTING/RUNNING/RECOVERING/DEGRADED/STOPPING/STOPPED/FAILED 状态和 session token；禁止各功能自建运行标志。

验证：重复启动幂等、恢复不进入终止生命周期、用户停止可终止、过期事件被丢弃。

### B2：统一目标和输出端口

文件：`experimental/motion/ports.py`、`experimental/motion/controller.py`、`experimental/adapters/*.py`、对应契约测试。

动作：定义 `TargetSource`、`CapturePort`、`MemoryPort`、`WindowPort`、`GamepadPort` 和 `MotionDecision`；控制器不再直接访问 Qt/Windows/Host。

验证：fake adapter 完成点击移动、P1 跟随、P2 跟随和双人同目标的相同运动回路。

### B3：统一定位接口

文件：`experimental/localization/global_localization.py`、`local_tracker.py`、`relocalization_service.py`、`models.py`、对应测试。

动作：统一首帧、局部跟踪和重定位输出为 `PositionEstimate`；跟随和移动不再自行判断定位来源。

验证：首帧、局部、预测、视觉纠偏、重定位和 map identity 失效均有状态转换测试。

### B4：统一诊断和性能

文件：`experimental/diagnostics/event_logger.py`、`session_recorder.py`、`performance.py`、`snapshot_archive.py`、对应测试。

动作：统一记录 session、tick、frame、decision、elapsed、reason；支持失败帧和恢复前后快照。

验证：事件顺序、采样限流、性能统计和归档路径稳定；不把临时运行数据加入 Git。

### C1：移除页面算法

文件：`capture_test_page.py`、`ui/modes/poe2_live_terrain/experiment_panel.py`、控制器 composition。

动作：页面方法只做 façade；删除页面内的算法实现和业务状态字段。

验证：旧按钮行为测试、页面装配测试、完整 PoE2 测试。

### C2：composition 和 replay

文件：`experimental/composition.py`、`data/poe2_live_terrain_test/replays/` 的 manifest/schema、replay 测试。

动作：集中装配 controller 和 adapter；建立首帧、跟随、遮挡、恢复、卡墙和前台错误回放。

验证：同一 replay 输出确定性状态序列。

### C3：脱离 Qt

文件：实验核心所有 controller、`tests/poe2_live_terrain/test_experiment_headless.py`。

动作：使用 fake clock、fake capture、fake memory、fake gamepad 运行完整实验链路；Qt 只在 UI adapter 测试出现。

验证：无 QApplication 运行核心回放；无真实输入副作用。

### C4：完整审查

动作：按“初始化→首帧→移动→视觉丢失→预测→恢复→重定位→恢复移动→停止”人工逐步审查调用链，检查线程、状态、日志和资源释放。

验证：全量测试、compileall、diff check、架构依赖扫描、人工审查记录。

### C5：正式底层候选评估

动作：只列出与 PoE2 无关且已经有独立契约/测试的能力候选，例如 `TargetSource`、`RecoveryScheduler`、`PositionEstimate`；不执行迁移。

验证：每个候选都满足无游戏术语、无 UI 依赖、无真实副作用和独立测试。

## 提交策略

每个阶段至少一个提交；A1～A5 可以按模块拆分多个提交。提交前必须更新任务文档和 `ITERATION_LOG.md`。禁止将运行截图、缓存、日志和权限受限的数据目录批量加入提交。

