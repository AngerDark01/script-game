# PoE2 新架构跟随：完整运行链人工推导审查

日期：2026-10-09  
范围：只审查“点击开始跟随”后的真实运行语义；本轮不改代码、不发送真实输入。

## 1. 审查结论先行

当前实现不是纯粹的新架构，而是“新双进程 + 旧页面入口/旧运动策略适配 + 兼容 fallback”的过渡态：

```text
Qt 页面入口（仍包含大量 legacy 状态和 stop/start 分支）
  -> Poe2FollowEnginePageAdapter
  -> FollowEngineUiAdapter
  -> FollowEnginePort
  -> RelayLoop（父进程线程，10ms 观察/转发）
  -> VisionProcess + FollowControlProcess
  -> AsyncSnapshotOutput
  -> SnapshotOutputAdapter
  -> LegacyDynamicFollowRouteController
  -> SimulatedFollowRuntime / 旧 PathFinder、VectorPathTracker、LocalMotionController
  -> ProgramGamepadOutput / Host
```

因此：

1. Vision/Control/Output 的资源所有权已经主要按新架构拆开；
2. 动态目标策略在正式 PoE2 composition 中已经下沉到 Control，不再依赖 UI relay；
3. 但“旧版不应存在”的要求尚未达到：旧 legacy 页面运行时仍存在，旧运动策略通过 adapter 继续被调用，页面仍保留旧入口和兼容分支；
4. 离线测试只证明消息和生命周期契约，不能证明真实 Host 消费或游戏内 P2 移动；
5. 当前最需要修正的是架构边界和验收证据，不是继续调阈值。

## 2. 真实点击后的时序模拟

### T-1：点击前

前置条件：双人首帧已 accepted，页面拥有 map snapshot、wall map、SimilarityTransform、两个角色 native seed 和 marker profiles。

页面仍可能同时持有 legacy 对象：`_dual_motion_worker`、`_dual_motion_timer`、`_follow_runtime`、`_follow_program_output`、legacy recovery controller。模块化入口必须先停止这些资源，否则会出现同一 capture/controller 双 owner。

### T0：点击 `start_follow_experiment`

调用链：

```text
Poe2CaptureTestPage.start_follow_experiment
  -> stop_program_move_probe
  -> stop_dual_target_experiment
  -> stop_follow_experiment(reason=modular_restart)
  -> _start_modular_follow_experiment
  -> _ensure_modular_follow_adapter
  -> build_follow_seed_from_dual_result
  -> build_poe2_follow_engine_page_adapter
```

实际状态判断：

- 如果已有 modular stop pending，会延迟 start；
- 如果已有 modular start pending，会忽略重复点击；
- 如果 legacy worker 仍在运行，会请求停止它，但新架构没有在此处同步等待旧 capture 完成；必须依赖 stop 的实际完成证据；
- adapter 构造本身不应连接 Host，但会构造 capture、wall extractor、route adapter、output actor 和 composition。

风险：页面入口仍把 legacy 和 modular 生命周期混在一个 5k 行页面中；“请求停止”不等于“旧 worker 已经释放 capture/controller”。

### T1：后台 lifecycle start

`_submit_modular_lifecycle("start", ...)` 在线程池中串行执行：

```text
Poe2FollowEnginePageAdapter.start
  -> FollowEngineUiAdapter.start
  -> FollowEnginePort.start
     -> await previous rebuild retirement
     -> GenerationClock.begin(map_instance)
     -> ControlProcessHandle.start
     -> VisionProcessHandle.start
     -> AsyncSnapshotOutput.start
     -> engine active=True
     -> RelayLoop.start(epoch)
```

注意：Control 和 Vision 是 Windows spawn 子进程；Output actor 是父进程线程；RelayLoop 也是父进程线程；Qt 页面不是 worker 的时钟。

成功条件不是“`Process.start()` 返回”，而是后续必须分别看到：

```text
control_process_started(pid)
vision_process_started(pid)
output_actor_started
first visual observation
first control snapshot
first output apply
```

### T2：首帧和双通道运行

VisionProcess：

```text
capture.capture
  -> DualObservationProcessor.process
  -> publish SharedFrameRing
  -> VisionProcessEvent(observation, sequence, captured_at_ms)
```

ControlProcess 每个周期：

```text
drain target latest-by-role
drain priority FIFO（execution/recovery/stop）
drain visual（保留首个和最新）
apply_visual
update_target
runtime.tick
publish FusionSnapshot
```

当前正式 PoE2 dynamic follow 中，`control_owns_live_targets=True`：

```text
Control.apply_visual(leader accepted)
  -> _refresh_live_target
  -> follower role.target 更新
  -> 同一 Control tick 规划 follower
```

所以动态跟随不应依赖 UI timer 传播 P1 位置。页面侧 relay 仍是 legacy/fallback 兼容路径，不应在正式 composition 中生效。

### T3：输出链

```text
FusionSnapshot.output_intents
  -> FollowEnginePort relay
  -> AsyncSnapshotOutput.apply（latest-only）
  -> SnapshotOutputAdapter.apply
  -> OutputScheduler.apply
  -> ProgramGamepadOutput.start/write/heartbeat
  -> Host program.acquire/program.state
```

arm gate 期间必须保持 neutral lease；arm gate 后才允许非零 state。持续跟随没有业务时间上限，只有用户 stop、页面关闭或 map instance 确认变化可以释放 session。

重要边界：Host accepted 只证明 Host 接收，不证明 PoE2 消费；必须额外有 controller ownership、前台窗口和游戏内 P2 位移证据。

### T4：视觉暂失/异常

预期链路：

```text
视觉候选暂失或被拒
  -> Control 保留 last accepted visual
  -> CommandOdometry + velocity + execution receipts 预测
  -> 继续产生 OutputIntent，不释放 session
  -> 下一帧优先 local ROI correction
  -> correction accepted 后更新 fused position/uncertainty
```

如果 Vision 子进程 fault/stall：

```text
child heartbeat/exit evidence
  -> bounded rebuild（single-flight、generation/epoch 校验）
  -> 旧 worker stop/dispose
  -> 新 worker 继承最新 native position + transform + target
  -> 新 worker first observation/first snapshot 后 commit
```

如果 Output/Host lease 暂时失败：

```text
output actor neutralize
  -> bounded rearm/retry
  -> 保留 Control session/target/prediction
  -> rearmed 后继续输出
```

不能把视觉暂失、单次路径失败、Host 临时失败转换成业务 stop。

### T5：手动停止

```text
用户点击停止
  -> page stop_requested（记录 caller/reason/serial）
  -> lifecycle stop 串行执行
  -> FollowEnginePort.stop
     -> RelayLoop.stop
     -> VisionProcess.stop/join/terminate if needed
     -> ControlProcess.stop/join/terminate if needed
     -> Output.stop
        -> neutral（若上次 axes 非零）
        -> program.release
        -> Host client close
     -> ring/queue close
  -> UI timer stop、adapter/composition 引用清理
```

### T6：关闭整个程序

现在页面关闭会等待 lifecycle future；定位 worker 超时也不再跳过 follow cleanup。重复 stop 会合并。最终必须看到：

```text
program_output.neutral 或 neutral_skipped
program_output.released / release_failed
output_actor_stopped
vision_process_stopped
control_process_stopped
vision/control_queue_closed
ring_closed
lifecycle_shutdown_finished
```

## 3. 新旧边界现状矩阵

| 层 | 当前实际实现 | 是否纯新架构 | 结论 |
|---|---|---:|---|
| 页面入口 | `capture_test_page.py` 同时保留 legacy 和 modular 分支 | 否 | 需要最终收口为单一 modular 入口，legacy 只能留在独立回归模块 |
| 截图/识别 | VisionProcess + `DualObservationProcessor` | 基本是 | 需要真实 child heartbeat/退出证据 |
| 控制 | FollowControlProcess + runtime fusion | 是 | 目标策略已下沉，但要证明不被旧 relay 覆盖 |
| 目标源 | dynamic composition 为 Control-owned；fallback adapter 仍存在 | 部分 | 正式模式禁用 fallback，保留显式测试 adapter |
| 路径/移动 | `LegacyDynamicFollowRouteController` 调旧 `SimulatedFollowRuntime` | 否 | 这是策略适配，不是新底层；需明确“旧策略内核、 新接口壳”的最终边界 |
| 输出 | AsyncSnapshotOutput + SnapshotOutputAdapter + OutputScheduler | 基本是 | Host I/O 单 owner，需实机消费证据 |
| 手柄底层 | `ProgramGamepadOutput` / Host 协议 | 旧协议适配 | 参数不应变，接口可适配；不能再被页面 legacy output 同时创建 |
| UI 轮询 | 页面 timer 只读 relay snapshot | 是 | 但页面仍保留大量旧状态和旧 stop 调用 |
| 恢复 | Control 内 local/memory/global + worker rebuild | 部分 | 恢复预算和真实 child 交接仍未 game-consumed 验收 |

## 4. 当前可以确认和不能确认的事情

### 可以确认（`offline_verified` / `source_confirmed`）

- 新进程可以按 spawn-safe 合约构造；
- Visual/target/priority 通道分离；
- dynamic follow 的正式 composition 配置为 Control-owned target；
- 输出 actor 与 Control 解耦；
- stop/shutdown 已有 bounded cleanup 和 neutral-before-release；
- generation/epoch 可拒绝迟到结果；
- 离线 focused tests、compileall、diff-check 已通过。

### 不能确认（必须实机证据）

- PoE2 是否真的消费 controller 2 的 state；
- P2 实际位移是否跟随 control snapshot；
- Qt 页面隐藏/主窗口关闭时 child 是否总能在真实 Host 延迟下退出；
- Vision 暂失后的预测误差和 local ROI 修正速度；
- map scroll/rebuild 后 P2 是否保持连续；
- 长时间完整地图运行是否无漂移、无残留、无手柄锁定。

## 5. 本轮发现的架构偏差（不修改代码）

1. **新旧入口未完全隔离**：正式页面仍包含 legacy follow、dual motion、probe、target experiment 的状态与停止函数；这是资源所有权和执行链混乱的主要来源。
2. **旧运动策略通过 `LegacyDynamicFollowRouteController` 继续运行**：这可以满足“模块功能和参数不改”，但必须被明确命名为“策略内核适配器”，不能再让旧页面 runtime 参与正式 modular session。
3. **Fallback target relay 仍可被构造**：正式 composition 已关闭它，但接口仍允许旧 adapter 路径；如果配置错误，可能产生父侧 target 覆盖风险。
4. **父 RelayLoop 仍承担 worker queue 消费和 Output apply**：UI 不再是时钟，但父线程仍是 Control→Output 的运输边界；这不违反双进程，但必须把它定义为“session supervisor/transport relay”，而不是第三个业务控制器。
5. **当前验收日志覆盖生命周期，但还没有统一 session receipt**：启动、snapshot、output apply、Host accepted、游戏位移尚未用一个 session/generation/sequence 链串起来。
6. **当前“测试通过”不能代表新架构完成**：现有 58 项是离线边界，不是真实运行闭环。

## 6. 交给并行工作的同步协议

任何并行修改必须先阅读：

- 本文；
- `docs/POE2_FOLLOW_REPAIR_MASTER_PLAN.md`；
- `docs/POE2_FOLLOW_ROLLBACK_CHECKPOINT.md`；
- `ITERATION_LOG.md`。

并行工作不得：

- 修改定位/寻路参数来掩盖生命周期问题；
- 同时启用 legacy capture/output 和 modular capture/output；
- 把 Host accepted 当作游戏移动证据；
- 把离线测试通过写成实机完成；
- 删除旧策略前没有先建立新接口等价回归。

并行工作必须在同一断点中记录：文件、符号、所有权、generation/sequence、证据等级、测试结果和未验证边界。

## 7. 下一阶段（仍然不直接调算法）

1. 画出正式 modular-only 的资源所有权图，列出页面中必须被隔离/删除的 legacy runtime 字段和调用点；
2. 为旧运动策略 adapter 建立明确的 domain-neutral contract，证明只复用策略，不复用旧 session/lifecycle；
3. 为一次真实会话建立统一事件表：button → lifecycle → child → visual → control → intent → Host → receipt → game movement → stop；
4. 之后才允许做一次用户实测，并按该事件表判断是生命周期、视觉、控制、输出还是游戏消费边界失败。
