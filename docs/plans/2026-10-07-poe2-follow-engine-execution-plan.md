# PoE2 双人跟随双通道引擎执行计划

日期：2026-10-07  
设计基线：`docs/plans/2026-10-07-poe2-follow-engine-multiprocess-design.md`  
代码基线：`ea72667 checkpoint: isolate follow recovery boundaries`  
规划提交：本文件与断点更新一起提交；运行时 evidence 不提交。

## 1. 目标、非目标与完成定义

### 1.1 目标

把当前 PoE2 双人实时跟随从“Qt 页面同步编排 + 视觉线程 + 线程池恢复”迁移为两个长期业务进程：

```text
Qt UI 进程
  ├─ VisionProcess：采集、墙体、人物候选、双人关联、局部 ROI
  └─ FollowControlProcess：预测、融合、路径、恢复、输出调度
                         └─ VirtualGamepad Host
```

必须满足：

1. P1/P2 任一角色视觉暂时丢失时，预测通道继续工作，下一帧优先局部纠偏。
2. 视觉、预测、内存三类来源互相校正，不把任一来源当作永久真值。
3. 内存只做低频快速重锚，全局视觉注册只做最终异步兜底。
4. 动态跟随不能被到达、失配、路径失败、失焦或临时 Host 错误自动停止；只有用户手动停止释放 session。
5. UI 不执行截图、识别、路径规划、内存读取和全局恢复。
6. 每个控制 tick、视觉帧、恢复任务和输出会话都有可追踪耗时与 generation/sequence。

### 1.2 非目标

- 本阶段不把新引擎合并到正式单人绘图/导航底层。
- 不改变首帧已经确认的方向、镜像、比例算法，只复用其 transform。
- 不为每一种异常创建独立进程；恢复任务使用控制进程管理的单次异步任务。
- 不在离线阶段发送真实手柄输入、读取真实游戏内存或启动网络同步。
- 不把运行时 evidence、`data/events/events.json` 的用户数据变更加入代码提交。

### 1.3 完成定义

只有以下条件全部满足才算 C5 完成：

- M0-M6 离线测试和 Windows 进程生命周期测试全部通过。
- M7 实机分级场景全部完成，完整地图运行无时间硬限制。
- `capture_test_page.py` 的 live 跟随不再直接拥有 tracker、路径、memory 或 recovery 可变状态。
- 旧 live recovery 入口调用次数为 0；静态点击导航的兼容入口仍可用。
- 视觉丢失、内存失败、Host session 失效、窗口失焦和地图变化都不会自动释放动态跟随 session。
- P2 漂移回放中，视觉恢复后位置误差重新收敛，不能无限期增长。

## 2. 当前基线和证据

### 2.1 已确认的当前调用链

```text
Poe2CaptureTestPage.start_follow_experiment()
  → _start_dual_motion()/follow timer
  → Poe2DualMotionWorker(thread)
  → capture/recognition/tracker result
  → Qt 页面 tick
  → SimulatedFollowRuntime.tick()
  → ProgramFollowOutput
  → adapters.virtual_gamepad.ProgramGamepadOutput
  → Host
```

恢复分支目前从页面 tick 触发，视觉丢失时曾长期停留在 `occlusion_held` 并继续 `command_prediction`；这会使预测位置与真实位置分离。页面 tick 还可能同步执行重型路径/恢复，造成 Host TTL 过期和 UI 卡顿。

### 2.2 需要保留的现有模块

| 模块 | 处理方式 |
|---|---|
| `experimental/multiplayer_localization/dual_first_frame.py` | 保持首帧算法；只抽取纯输入/输出 DTO |
| `experimental/multiplayer_localization/dual_motion.py` | 迁移其中的视觉处理，不再让 Qt 直接拥有 worker |
| `experimental/multiplayer_follow/runtime.py` | 先作为纯导航/路径组件复用，逐步消除页面依赖 |
| `experimental/multiplayer_follow/command_role_tracker.py` | 抽取为 tracking 组件，保留兼容 facade |
| `experimental/multiplayer_follow/recovery/*` | 将策略与执行 backend 分开；旧入口只保留兼容测试 |
| `adapters/virtual_gamepad/program_output.py` | 作为 Host/lease 适配器，心跳线程与控制 tick 解耦 |
| `ui/modes/poe2_live_terrain/capture_test_page.py` | 最终只保留 UI adapter 和静态点击实验兼容层 |

## 3. 目标目录和依赖方向

新增目录（仅实验功能）：

```text
src/auto_modules/features/poe2/live_terrain/experimental/follow_engine/
├── __init__.py
├── contracts.py              # 跨进程不可变消息
├── generation.py             # session/generation/sequence 校验
├── latest_frame_buffer.py    # 进程内 latest-only
├── shared_frame_ring.py      # 固定槽共享帧
├── process_supervisor.py     # spawn、退出、重启、代际隔离
├── engine.py                 # FollowEnginePort 的实现
├── ui_adapter.py             # Qt 只通过 port 读写
├── vision/
│   ├── __init__.py
│   ├── vision_process.py
│   ├── capture_adapter.py
│   ├── wall_processor.py
│   ├── marker_processor.py
│   ├── local_roi_matcher.py
│   └── dual_association.py
├── tracking/
│   ├── __init__.py
│   ├── command_odometry.py
│   ├── velocity_calibrator.py
│   ├── position_fusion.py
│   └── tracking_state.py
├── recovery/
│   ├── __init__.py
│   ├── recovery_policy.py
│   ├── local_recovery.py
│   ├── memory_recovery.py
│   └── global_recovery.py
└── control/
    ├── __init__.py
    ├── follow_control_process.py
    ├── route_controller.py
    ├── output_scheduler.py
    └── control_diagnostics.py
```

依赖只能向下：

```text
contracts/generation/buffers
        ↓
vision + tracking + recovery policy
        ↓
control process
        ↓
adapters (capture/memory/gamepad)
        ↓
Qt UI adapter / business follow mode
```

`vision` 不得导入 Qt、路径、内存和手柄；`tracking` 不得知道 P1/P2 的业务名称；`control` 不得直接访问 Qt 控件；真实副作用只能出现在 adapter。

## 4. 跨进程契约

### 4.1 通用头

所有消息都必须带：

```python
generation: int
sequence: int
captured_at_ms: int
map_instance: str
```

应用结果前必须检查 generation、sequence 单调性、map_instance 一致性；不一致的迟到结果只能记录为 stale，不能覆盖当前状态。

### 4.2 VisualObservation

```python
VisualObservation(
    generation, sequence, captured_at_ms, map_instance,
    roles: Mapping[str, RoleVisualObservation],
    wall_shift: tuple[float, float] | None,
    wall_quality: float,
    assignment_score: float,
    local_match_score: float | None,
    local_match_radius: float | None,
    source: Literal["visual", "local_roi", "partial", "none"],
    timing: StageTiming,
)
```

角色观测必须包含 `position_native`、`velocity_native`、`confidence`、`uncertainty_native`、`visible`、`last_visual_at_ms` 和 `association_cost`。

### 4.3 PredictionSnapshot / FusionSnapshot

预测快照记录命令、持续时间、校准可信度、视觉年龄和预测年龄；融合快照额外记录恢复状态、目标快照、路线、控制向量和输出意图。UI 只能消费融合快照，不能读取控制进程内部 tracker。

### 4.4 OutputIntent / HostAck

输出闭环至少拆成：

```text
output_submitted → host_acknowledged → game_motion_observed → visual_confirmed
```

Host ack 只能证明报告已接收，不能当作角色已移动。session 失效只触发 output lease rearm，不触发地图恢复或跟随停止。

## 5. 双通道算法和恢复策略

### 5.1 预测通道

```text
v_command = calibrated_speed × input_direction
v_estimated = α × v_visual + β × v_command + γ × v_previous
p_pred(t+Δt) = p_fused(t) + v_estimated × Δt
σ_pred = σ_fused + σ_visual_gap + σ_speed_error×Δt + σ_command_error×output_duration
```

预测通道 30–60Hz 独立推进，不等待视觉 future。超过可信时间/不确定度上限时仍可输出低幅度探索脉冲，但必须把状态降为 `PREDICTING`，不能宣称已到达。

### 5.2 视觉通道

每个新帧只处理最新截图；墙体更新 15–20Hz，人物候选/关联 25–30Hz。角色失配时在预测位置附近按 `80/140/220 native px` 逐级尝试 ROI；局部匹配成功即发布 `source=local_roi`，不读内存、不做全局注册。

双人身份分数由位置连续性、速度方向、颜色相似度、两人相对距离和墙体位移共同构成；颜色只能是软分数。

### 5.3 融合通道

```text
K = σ_pred² / (σ_pred² + σ_visual²)
p_fused = (1-K)×p_pred + K×p_visual
```

视觉新鲜且可信时快速吸收；视觉部分缺失时保留预测连续性；视觉恢复后只用创新距离和双人几何门控吸收，防止错误候选把角色瞬移到 P1 前方。

### 5.4 恢复优先级和量化门槛

| 层级 | 触发条件 | 动作 | 冷却/限制 |
|---|---|---|---|
| L0 视觉降级 | 单帧失配或视觉年龄 ≤600ms | 新帧重试、上一可信状态、短时预测 | 不读内存 |
| L1 局部 ROI | 新帧存在但普通关联失败 | 预测点附近 ROI 匹配 | 每帧最多一次，成功立即回 L0 |
| L2 内存重锚 | 连续 3–5 个有效帧失配，或 σ>40–60，且 transform/实例有效 | warm reader 一次读取双人坐标并套用已有 transform | 单角色最短 5–10s |
| L3 全局异步 | L2 失败/实例变化/transform 失效，且 σ>100–120 或地图证据失效 | 单 generation 一个全局恢复任务 | 不阻塞控制，不释放 session |

所有层失败都保持动态跟随 session；只有用户手动停止才释放 output lease。

## 6. 原子执行任务

每项任务按“先写失败测试 → 验证失败 → 实现 → 通过验证 → 独立提交”执行。任务之间不得跳过验收门槛；若任务失败，先更新断点文档再继续。

### M0：冻结基线和离线回放夹具

#### M0.1 基线索引

- 文件：`docs/POE2_FOLLOW_ROLLBACK_CHECKPOINT.md`、`ITERATION_LOG.md`、`docs/plans/2026-10-07-poe2-follow-engine-execution-plan.md`
- 内容：记录基线提交、未提交 evidence、当前调用链、每组回放目录和预期结果。
- 验证：`git status --short` 只能显示用户运行数据；`git show --stat ea72667` 可追溯源码基线。

#### M0.2 回放 manifest

- 文件：`tests/poe2_live_terrain/fixtures/follow_replays/*.json`、`tests/poe2_live_terrain/test_follow_engine_replays.py`
- 场景：正常双人、单帧失配、P2 短丢失、P2 长丢失、局部恢复、内存恢复、Host session 失效、地图实例变化。
- 验证：离线运行不访问截图 provider、内存 reader、Host 或 Qt；同一 manifest 两次结果一致。

### M1：纯契约、代际和时间模型

#### M1.1 不可变 DTO

- 文件：`follow_engine/contracts.py`、`tests/poe2_live_terrain/test_follow_engine_contracts.py`
- 实现：定义 `FrameSlot`、`VisualObservation`、`PredictionSnapshot`、`FusionSnapshot`、`OutputIntent`、`StageTiming`，构造时校验有限数值、实例和时间戳。
- 验证：非法 generation、NaN 坐标、逆序 sequence、错误 map instance 均被拒绝。

#### M1.2 generation/sequence 校验

- 文件：`follow_engine/generation.py`、`tests/poe2_live_terrain/test_follow_engine_generation.py`
- 实现：实现新会话创建、迟到结果拒绝、停止后消息失效和实例切换。
- 验证：旧进程结果不能覆盖新会话；同序列重复消息幂等。

#### M1.3 预测和融合纯函数

- 文件：`follow_engine/tracking/command_odometry.py`、`velocity_calibrator.py`、`position_fusion.py`、`tracking_state.py`；测试 `test_follow_engine_fusion.py`
- 实现：速度校准、command odometry、不确定度增长、Kalman 风格融合、到达判断必须使用可信/融合位置而非纯预测位置。
- 验证：视觉中断后位置连续；视觉恢复后创新受门控；预测超限不会伪造 `arrived`。

#### M1.4 恢复策略状态机

- 文件：`follow_engine/recovery/recovery_policy.py`、`tests/poe2_live_terrain/test_follow_engine_recovery_policy.py`
- 实现：L0–L3 门槛、冷却、升级/降级、`FOLLOW_HOLD` 和“非用户异常不停止”。
- 验证：单帧失配不读内存；连续失配先局部；内存冷却生效；全局最多一个任务；所有临时故障保留 session。

### M2：VisionProcess 和 latest-only 帧通道

#### M2.1 进程无副作用入口

- 文件：`follow_engine/vision/vision_process.py`、`vision/capture_adapter.py`、`tests/poe2_live_terrain/test_follow_engine_vision_process.py`
- 实现：Windows `spawn` 可导入的独立入口；子进程不导入 Qt、不创建 UI、不读取游戏内存、不发送手柄。
- 验证：fake capture 可启动、停止、异常退出并返回 terminal outcome；主进程重复导入不产生子进程。

#### M2.2 固定槽 latest-only ring

- 文件：`follow_engine/shared_frame_ring.py`、`latest_frame_buffer.py`、`tests/poe2_live_terrain/test_follow_engine_frame_ring.py`
- 实现：容量 2–3 的固定槽；消费者只取最高 sequence；生产者覆盖旧 READY 槽，不允许无界图片队列。
- 验证：处理速度低于采集速度时队列长度仍有界；旧帧 dropped 计数增加；最新帧延迟受控。

#### M2.3 视觉处理拆分

- 文件：`vision/wall_processor.py`、`marker_processor.py`、`dual_association.py`、`local_roi_matcher.py`；测试 `test_follow_engine_vision_processors.py`
- 实现：墙体低频、人物高频、候选软颜色评分、双人几何关联、ROI 逐级重试；输出分段耗时。
- 验证：颜色污染不会交换身份；P2 暂时丢失时发布 partial/none 而不是 stop；局部成功不会触发全局注册。

#### M2.4 视觉进程 supervisor

- 文件：`follow_engine/process_supervisor.py`、`tests/poe2_live_terrain/test_follow_engine_supervisor.py`
- 实现：generation 隔离、停止确认、迟退 worker 忽略、崩溃后有界重启和退避。
- 验证：旧视觉进程晚到结果不能覆盖新会话；连续崩溃不会无限重启。

### M3：FollowControlProcess

#### M3.1 控制进程主循环

- 文件：`control/follow_control_process.py`、`control/control_diagnostics.py`、测试 `test_follow_engine_control_process.py`
- 实现：30–60Hz 轻量 tick；读取最新视觉、目标、Host ack；推进预测、融合、路径和恢复；绝不等待视觉或全局 future。
- 验证：视觉进程暂停时控制 tick 仍稳定；控制 tick 超时只降级输出，不释放 session。

#### M3.2 统一路径与局部避障

- 文件：`control/route_controller.py`、测试 `test_follow_engine_route_controller.py`
- 实现：只接收融合位置；沿用已有地图 transform、目标投影、窄道通行和局部 steering；路径失败进入探索脉冲而不是 stop。
- 验证：目标栅格偏移可投影到邻域可行走点；小路/死路有 clearance/dead-end 评分；墙体接触后方向可切换。

#### M3.3 输出调度器

- 文件：`control/output_scheduler.py`、`adapters/virtual_gamepad/program_output.py`（仅适配接口）；测试 `test_follow_engine_output_scheduler.py`、`tests/test_program_gamepad.py`
- 实现：控制 tick 与 Host heartbeat 解耦；输出提交、ack、重建、租约保活分别记录；session 失效只 rearm 当前 controller。
- 验证：中立帧也维持心跳；过期 token 可退避重建；重建期间不释放跟随 session；心跳失败不刷屏阻塞控制循环。

### M4：内存快速重锚和全局异步恢复

#### M4.1 warm memory reader

- 文件：`recovery/memory_recovery.py`、现有 `experimental/multiplayer_localization/memory_anchors.py`；测试 `test_follow_engine_memory_recovery.py`
- 实现：缓存 PID/descriptor/layout/component 地址；一次批量读取双人坐标；校验 area instance、transform、坐标范围和 generation。
- 验证：warm read 不重复冷启动扫描；实例变化拒绝结果并让策略升级；成功只 seed tracker，不做视觉注册。

#### M4.2 局部恢复 backend

- 文件：`recovery/local_recovery.py`、测试 `test_follow_engine_local_recovery.py`
- 实现：消费最新帧，在预测位置附近做局部视觉匹配；成功返回角色位置和误差；失败只返回 evidence，不停止。
- 验证：局部成功耗时目标 <20ms（离线 fake）；局部失败进入 L2/L3，不调用全局注册。

#### M4.3 全局恢复 backend

- 文件：`recovery/global_recovery.py`、现有 `experimental/multiplayer_follow/recovery/global_reanchor.py`；测试 `test_global_reanchor_backend.py` 扩展 generation/并发用例。
- 实现：单 generation 单任务、异步结果、迟到丢弃、成功原地恢复；期间控制进程保持低幅输出和 session。
- 验证：全局恢复耗时不阻塞控制 tick；同一 generation 不重复提交；地图实例变化时旧结果无效。

### M5：引擎组合和 UI 适配

#### M5.1 FollowEnginePort

- 文件：`follow_engine/engine.py`、`follow_engine/ui_adapter.py`、测试 `test_follow_engine_port.py`
- 实现：公开 `start(config)`、`update_target(target)`、`snapshot()`、`stop(reason="user")`；隐藏进程、tracker、future、adapter 细节。
- 验证：port 可用 fake vision/control/host 启动；用户停止是唯一释放动态输出租约的正常入口。

#### M5.2 页面改为纯 adapter

- 文件：`src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py`、`tests/test_poe2_capture_test_page.py`、`tests/test_poe2_capture_test_page_multiframe.py`
- 实现：页面只发送配置/目标、消费 `FusionSnapshot`、绘制截图/地图/诊断；删除 live 分支对 tracker、memory、global worker 的直接访问。
- 验证：页面线程不调用截图、OpenCV、路径和内存；旧 `RecoveryController.schedule_retry()` live 调用次数为 0。

#### M5.3 静态点击实验兼容

- 文件：`follow_engine/ui_adapter.py`、现有 `experimental/multiplayer_follow/runtime.py`；测试 `test_multiplayer_follow_runtime.py`、`test_follow_engine_click_mode.py`
- 实现：点击目标继续走统一 control engine，但目标来源为 click source；不将 click heartbeat 误判成远端移动。
- 验证：静态目标可持续等待但不释放动态 session；远端坐标更新能替换目标且不会重建进程。

### M6：性能、生命周期和可观测性

#### M6.1 统一分段计时

- 文件：`control/control_diagnostics.py`、`vision/vision_process.py`、`contracts.py`；测试 `test_follow_engine_timing.py`
- 实现：记录 capture、wall、marker、association、local、fusion、route、output、heartbeat、UI drain、total；按采样率降频写日志。
- 验证：每个 tick 有唯一 sequence；日志可计算 p50/p95/p99；诊断开关关闭时不拖慢控制。

#### M6.2 压力和丢帧

- 文件：`tests/poe2_live_terrain/test_follow_engine_stress.py`
- 实现：模拟 30Hz capture、20Hz vision、60Hz control、慢恢复和 Host 延迟；断言无界队列、无死锁和 no-safe-route cooldown 不会停机。
- 验证目标：预测 ≥30Hz，视觉 ≥20Hz，融合 <5ms，普通路径 <15ms，UI 不阻塞；超时只降级。

#### M6.3 Windows spawn/退出/重启

- 文件：`tests/poe2_live_terrain/test_follow_engine_windows_lifecycle.py`、`process_supervisor.py`
- 实现：显式 spawn context、可重复 stop、共享内存 unlink、子进程 traceback、异常退出诊断。
- 验证：启动/停止 100 次无残留进程、句柄或共享内存；子进程崩溃后控制进程仍可预测并最终受控降级。

### M7：离线回放门槛

- 文件：`tests/poe2_live_terrain/test_follow_engine_replays.py`、`docs/POE2_FOLLOW_ROLLBACK_CHECKPOINT.md`
- 顺序：正常双人 → P1 单向 → P1 转向 → P2 短丢失 → P2 长丢失 → 靠近/分离 → 门/窄道 → Host session 失效 → 地图实例变化。
- 每个场景记录：视觉年龄、不确定度、恢复层、融合误差、命令持续时间、Host 状态和是否保持 session。
- 验证：回放不得出现预测无限增长、角色交换、自动释放 session 或全局恢复重复提交。

### M8：实机分级验收和发布前审计

- 文件：`docs/POE2_FOLLOW_ENGINE_ACCEPTANCE.md`（执行阶段创建）、`docs/POE2_FOLLOW_ROLLBACK_CHECKPOINT.md`
- 实机顺序：静止双人、单方向、连续转向、短/长视觉丢失、两人重叠、两人分离、门/窄道、Host 重建、地图变化、完整地图。
- 每次测试前确认：Host 版本支持 `program.heartbeat`、游戏窗口状态、controller ownership、当前 map instance、首帧 transform。
- 通过条件：无时间硬限制；临时异常只进入恢复/保持；最终位置误差和轨迹漂移在验收阈值内；日志和 evidence 可回放。

## 7. 提交、回滚和断点规则

### 7.1 提交粒度

每个 M 子任务一个提交，提交信息格式：

```text
feat(follow-engine): <stage>-<short-purpose>
test(follow-engine): <stage>-<coverage>
refactor(poe2): remove-<old-boundary>
```

不把运行时 evidence、用户事件配置和临时日志加入提交。每次提交后更新 `CODEBASE.md`、`ITERATION_LOG.md` 和 `docs/POE2_FOLLOW_ROLLBACK_CHECKPOINT.md`。

### 7.2 回滚点

- M0–M1：可直接回到 `ea72667`，不影响旧页面。
- M2–M4：通过 feature flag 保留旧 worker，但禁止新旧两个输出链同时拥有 controller。
- M5：只有新 port 离线回放和聚焦页面测试通过后才切换默认入口。
- M6–M8：实机失败只回退 feature flag，不回滚运行时 evidence。

### 7.3 每次上下文压缩后的第一步

1. 读取本文件、`docs/POE2_FOLLOW_ROLLBACK_CHECKPOINT.md`、`ITERATION_LOG.md`。
2. 读取最新提交和工作树状态。
3. 检查当前阶段的“未完成任务/下一步/阻塞证据”。
4. 不重复已经通过的测试，不重新发明已确认的接口。

## 8. 当前决策和下一步

- 当前只完成规划和基线冻结，不开始 M0 实现。
- 代码基线已经提交；用户运行数据保持未提交。
- 下一步在用户确认后从 M0.1/M0.2 开始，先做离线回放夹具，再做 M1 纯逻辑契约。
- 在 M1/M2 离线回归通过前，不迁移真实手柄输入和真实游戏窗口。
