# PoE2 跟随重构同行审查（2026-10-09）

## 复核修订（授权会话补充）

- 动态 follow 的旧版真实配置已按 `_make_follow_runtime(live_role_follow=True)` 修正为 arrival 12、resume 20、prediction horizon 0.25、downsample 8；不再把非 live 模式的 arrival 8 当作恢复目标。
- 新增确认：priority queue 满时 execution/recovery 命令可能静默丢失；receipt 必须采用可靠 FIFO 或可验证的累计执行区间语义，并记录溢出。
- fault suppression 必须按 worker/epoch/signature，而非持久 first fault；新 worker ready/新 observation 后清除。
- local ROI recovery 的优先级高于 uncertainty 超限：一次失配后的下一张新帧就应优先局部纠偏，memory 只在连续局部恢复失败后限频兜底。
- Host receipt 仅证明 Host 接受/应用报告，不证明游戏角色真实位移；真实位移仍需视觉或内存证据。

本审查只读源码与已有日志，不启动游戏、不读取内存、不连接 Host、不发送输入。审查边界是：重构只改变定位/视觉/预测/内存的编排与并发，不改变旧版已经验证的路径、局部避障、脉冲和手柄输出策略。

## 1. 结论摘要

当前新版已经有 Vision、Control、Output 三个运行单元，但消息桥和健康判断仍部分依赖父侧 `FollowEnginePort.poll()`。这满足“计算拆分”，还没有完全满足“UI 不参与闭环”。Control tick 和 Output heartbeat 可以独立推进；Vision observation、Control snapshot、ExecutionReceipt 的关键交接仍由父侧 poll 完成，因此页面卡顿时闭环连续性仍需验证。

最新 03:44 会话的首个确定故障是 Vision contract 输入越界：`DualObservationProcessor.process()` 将 OpenCV phase response 直接作为 `wall_quality`，`VisualObservation` 拒绝大于 1 的值并退出 Vision。该问题已在 wall adapter 边界修复。重复同一确定性故障的 rebuild 保护也已加入，但它只能防止重建循环，不能替代视觉恢复策略；必须保留预测运行、局部纠偏和明确的重新启用出口。

另一个独立的架构偏差已经确认：旧版动态 follow 的真实调用方 `_make_follow_runtime(live_role_follow=True)` 使用 `arrival_radius=12`、`resume_radius=20`、`speed_units_per_second=80`、`downsample_factor=8`、`local_lookahead=24`、`prediction_horizon=0.25`，并注入 `ClosedLoopMotionController(expected_speed=80, arrival_radius=12)`。因此不能把“12→8”当作动态 follow 的恢复要求；8 是旧版非 live 模式的配置。当前模块化 Control 仍绕过旧版 `LocalMotionController`/`VectorPathTracker` 组合，使用新的 RouteController 直接输出固定幅度/时长，仍是需要修复的策略边界偏差。

## 2. 旧版到新版调用链

### 旧版成功链（a3070ea）

```text
页面 timer
  → dual_motion / multiplayer_follow runtime tick
  → source target PositionSample
  → follower 当前可信位置（视觉、保持或命令估计）
  → PathFinder 多级规划与原图段验证
  → VectorPathTracker 投影/前视/到达判断
  → LocalMotionController 局部候选方向、速度和墙体安全评分
  → FollowObservation(command_duration_ms)
  → ProgramOutput.apply()
  → ProgramGamepadOutput.write(vector, elapsed_ms)
  → Host/ViGEm
```

旧版核心参数和行为：

| 能力 | 旧版事实 | 重构边界判断 |
|---|---|---|
| 期望速度 | `speed_units_per_second=80` | 保留；只允许由实际回执校准预测速度 |
| 预测视野 | 动态 follow 实际为 `prediction_horizon=0.25` | 保留；不能用固定新公式替换局部 steering |
| Tracker/到达 | 动态 follow 为 `arrival_radius=12`、`resume_radius=20`；非 live 模式才是 8 | 必须按调用方区分，不能混用配置 |
| 局部 steering | `LocalMotionController`，多角度候选、clearance、progress、turn、oscillation、observed velocity | 必须保留 |
| 脉冲时长 | 由旧 runtime 的 `command_duration_ms` 决定，常见 80，接近/恢复分支有受限时长 | 不得统一成新版固定时长 |
| 路径安全 | PathFinder 多 factor 及原始墙体段验证 | 保留；目标投影只能作为输入适配，不得改成强膨胀 |
| 输出重连 | `ProgramOutput` 处理 session expired 后 rearm 并重发当前脉冲 | 保留；不能让 Host 临时失败释放动态跟随 |

### 当前新版链

```text
页面 timer
  → FollowEnginePort.poll()
  → Vision.poll_latest()
  → parent 转发 VisualObservation/frame
  → FollowControlProcessHandle.send_visual()
  → ControlRuntime.apply_visual()
  → command odometry / recovery / RouteController.plan()
  → FusionSnapshot(OutputIntent)
  → parent poll()
  → AsyncSnapshotOutput
  → SnapshotOutputAdapter / Host
```

当前实际 `MapAwareRouteController` 默认使用：`arrival_radius=12`、`magnitude=0.65`、`duration_ms=80`、`downsample_factor=4`、目标投影半径 8；`FollowControlRuntime.tick()` 直接使用 `RouteDecision.vector`。它没有调用旧版 `LocalMotionController` 或 `VectorPathTracker`。因此新版改变了规划和脉冲策略，而不是只替换定位来源。

### 必须恢复/保留的边界

Control 应继续拥有融合后位置和目标，但输出决策必须调用一个保持旧行为的不变量适配器：输入为融合位置、可信度、观测速度、旧路径状态和目标；输出为旧格式的 route、vector、duration、arrival/recovery reason。定位层只能改变输入 evidence，不得重写该适配器的策略。

## 3. 并发和消息审查

### 当前消息类型

- `visual`：Vision observation，带 generation、sequence、captured_at、map instance，latest-only。
- `target`：目标位置，latest-only，Control 侧可拥有动态 target。
- `execution`：Host 执行回执，按 generation/sequence/role 过滤。
- `recovery_signal`：Host/map/transform 边界信号，priority channel。
- `stop`：priority channel，同时由 stop event 兜底。
- `snapshot`：Control 到父侧的最新融合快照，latest-only。
- `ExecutionReceipt`：Output 到 Control 的实际应用结果。

### 当前所有权

| 状态 | 唯一 owner | 其他模块权限 |
|---|---|---|
| 角色融合位置/不确定度 | Control runtime | Vision 只发布 observation，Memory/Local 只返回结果 |
| 动态目标 | 正式组合应为 Control | 页面不得用旧 snapshot 回写覆盖新目标 |
| Host controller lease | Output actor / scheduler | Control 只能产生 intent |
| Frame ring | composition owner | Vision 写入，Control 按 sequence 读，重建时交接 |
| generation/session epoch | FollowEnginePort | 子进程只能接受当前代消息 |
| 路径内部状态 | 规划适配器所在 Control | Vision/页面不能直接改写 |

### 丢弃和排序规则

- Vision 帧：保留首个有效 seed 和最新帧，中间帧可丢弃；不能用旧帧覆盖新 transform。
- Target：按 role latest-only；目标 sequence/captured_at 必须单调，迟到目标不能覆盖当前目标。
- Execution receipt：按 generation、role、tick/lease 过滤；没有真实回执时不能把 planned vector 当成事实位移。
- Snapshot：父侧只消费最新快照；旧快照不能覆盖新目标或新的 generation。
- Transform：首帧 rotation/scale 固定复用；每个 observation 携带同帧 wall translation，局部 ROI 必须绑定同帧 transform。

#### 新发现：priority receipt 不能 latest-only 静默丢失

`FollowControlProcessHandle._send()` 的 priority queue 容量为 8；队列满时，`execution`、`recovery_signal` 等非 target 命令可能直接 return。对 `execution` 而言，这与“command odometry 只由实际 receipt 推进”的契约冲突。候选修复是可靠 FIFO、独立 relay actor，或合并为带 `first_tick/last_tick` 的分段执行区间。累计回执不能只保存总时长和最后 vector：区间内发生转向时必须保留按 vector/时长切分的 segments，或保存可验证的累计控制积分、幂等边界和 sequence 范围。队列满必须记录 drop reason、role、generation 和累计计数，不能静默丢失。worker 直连不是唯一方案，应以延迟、丢失率和页面暂停实测选择。

### UI 无响应时的缺口

Control tick 与 Output heartbeat 理论上可以继续运行，但 Vision→Control、Control→Output、Output receipt→Control 仍依赖父侧 poll。若 UI timer 停止，Control 可能继续使用旧观测和预测，Output 可能继续发送旧 intent，但新视觉和执行回执不能及时进入闭环。R1 的目标应是把这三个桥改成子进程/actor 间直接的有界通道，父侧只观察快照和日志；在此之前不能宣称无 UI 闭环已完成。

## 4. 生命周期与恢复时序

### 正常 start

1. 页面确认 accepted 首帧、地图实例、唯一 controller owner。
2. Port 创建 generation/session epoch。
3. Control、Vision、Output 按明确顺序启动；每个阶段记录 PID、句柄、耗时和 ready。
4. Output 建立 neutral lease；arm gate 期间禁止非零输入但允许 heartbeat。
5. Vision 发布首 observation；Control 应用 seed 后开始 tick；Output 只应用当前代 snapshot。

### stop/rebuild

1. 显式 stop 才释放动态跟随 session。
2. rebuild 只能替换故障组件，不清除 target、transform、可信位置、预测状态或 Output lease。
3. 旧 worker 必须有完成事件；新 generation 不能与旧资源共享 ring、capture 或 controller lease。
4. detached bundle 只有 session epoch/token/owner 校验通过才 commit；迟到 bundle 必须 dispose。
5. rebuild 失败不能把页面 timer、Control 或 Output 留在半活跃状态。

### Fault suppression 的正确出口

重复相同 contract fault 时不应无限 rebuild。但“抑制重建”不能等于永久相信错误预测。当前按持久 `first_fault` 字符串抑制还可能让旧 epoch 错误影响新 worker；应改成当前 worker/epoch/fault signature 去重，并在新 worker ready 或新 observation 成功后清除。正确出口是：

```text
确定性 fault
  → 保留 session + prediction/receipt 运行
  → 标记 vision_degraded
  → 等待新 generation 或明确的显式 worker repair
  → 新 Vision 成功发布 observation 后清除 degraded
  → 下一张新帧优先 local ROI correction
  → 连续新帧无法视觉/局部纠偏后才限频 memory recovery
```

需要增加一个明确的 `repair_pending` / `degraded` 状态和单次重新启用条件，否则视觉会永久停用而 Control 继续漂移。

## 5. 典型场景人工推导

### 正常跟随

P1/P2 在 hold radius 内时，Control 输出 neutral/hold，保留 session；leader 新位置到达后产生新 target sequence，旧路径失效并调用旧局部 steering。不能因为一次 arrival 进入终态。

### 人物贴近或颜色重叠

颜色候选失配时，先用上一可信位置、观测速度、实际执行回执做 prediction；下一帧在预测区域用固定首帧 rotation/scale 做 local ROI；双人关联利用相对距离和运动方向；不可因为 assignment 空集释放 session。

### 延迟/旧帧

按 captured_at/sequence 丢弃迟到帧；不得把旧视觉写入当前 transform 或 target。若只有旧帧，Control 使用 bounded uncertainty 预测并保持旧脉冲节奏。

### 越过目标

必须由旧 LocalMotionController 的 slowdown/overshoot/observed velocity 逻辑处理；只靠 `distance <= arrival_radius` 或固定 `magnitude` 会在目标附近冲过头。输出日志必须能看到 position、target、distance、velocity、vector、duration、receipt displacement。

### Host 失效

Output scheduler 保持 heartbeat；session expired 只触发 rearm/retry 当前 controller lease，不能清空 target 或触发地图级 recovery。只有用户停止、Host 明确不可用且重试预算耗尽，才标记输出故障；动态 session 仍需可观察。

### 页面卡顿

当前实现：Control/Output 可能继续，但视觉和 receipt 桥延迟。预期实现：页面仅订阅 latest snapshot/diagnostics；子进程间通道继续传递 latest visual、target、receipt，页面恢复后只读取当前代状态。验收必须同时确认新视觉进入 Control、新输出方向进入 Output、execution receipt 返回 Control；仅看到子进程 tick/heartbeat 不能证明闭环。

## 6. 性能证据与缺口

已知真实日志：legacy 接管前约 20–22 FPS；新模块化页面 poll 间隔约 47ms；03:44 Vision fault 后 progress age 持续增长，Control progress 仍在约 47–235ms 范围。该数据证明 watchdog 能观察到 Vision 停止，但不能证明游戏消费了 Control 输出。即使有 Host receipt，也只能证明 Host 接受/应用报告，不能证明角色真实位移；真实位移仍需视觉或内存校准。

已有离线证据：wall/port/control focused tests 32 passed，compileall 和 diff check 通过。缺少：真实 Control tick p95、Vision processing p95、queue age、Host write/receipt p95、游戏实际移动位移、页面卡顿时子进程闭环、重建后局部纠偏。

性能验收必须记录：Vision capture/decode/wall/marker/association/total；Control visual drain/prediction/local recovery/route/output/total；Output write/heartbeat/rearm；每个阶段 p50/p95/max；dropped latest frames；receipt displacement 与 command displacement 的误差。

## 7. 优先级待办

### P0：恢复旧移动策略边界

- 文件/符号：`follow_engine/control/route_controller.py`、`follow_engine/control/follow_control_process.py`、旧 `multiplayer_follow/runtime.py`、`core/routing/local_controller.py`、`core/routing/vector_tracker.py`。
- 动作：建立旧策略不变量适配器；只替换 position/target evidence，不改变 route/vector/duration/arrival/局部 steering。
- 证据：旧版与新版同一 replay 输入产生相同 route/vector/duration/arrival 序列；覆盖近目标、转向、门、贴墙和目标移动。

### P0：补充 Visual degraded 的恢复出口

- 文件/符号：`engine.py::_check_worker_stall`、`vision_process.py`、`recovery_policy.py`。
- 动作：同 fault 只 single-flight；新 Vision 成功 observation 后自动清除 degraded；一次失配后的下一张新帧立即优先 local ROI，连续局部纠偏失败后才限频 memory recovery。
- 证据：重复 contract fault 不循环 rebuild；修复后的 Vision 可重新 ready；Control 不停止、不永久依赖旧预测。

### P1：解除父侧 poll 对闭环的依赖

- 文件/符号：`engine.py::poll`、`FollowControlProcessHandle`、`OutputScheduler`/`AsyncSnapshotOutput`。
- 动作：Vision→Control 和 receipt→Control 使用独立有界通道；父侧只做观察与生命周期；保留 generation/sequence/transform 过滤。
- 证据：暂停 Qt timer 3 秒，Control/Output 仍产生连续 tick/heartbeat；同时必须验证新视觉进入 Control、新输出方向进入 Output、分段 execution receipt 返回 Control，恢复后没有旧帧覆盖。

### P1：统一双人同目标与动态跟随行为契约

- 文件/符号：旧 `multiplayer_follow/runtime.py`、`follow_engine` composition。
- 动作：两者共享同一规划/输出适配器，目标源只是 click 或 leader observation。
- 证据：相同 target replay 下两路径产生相同移动 intent；动态跟随永不进入一次性终态。

### P2：真实性能和游戏消费验收

- 证据：真实 PoE2 长跑，包含视觉污染、局部丢失、门、地图滚动、Host rearm、页面卡顿和完整地图；必须同时有日志、截图/内存位置和 Host receipt。

## 8. 当前明确未完成

- 未证明 P2 overshoot 的唯一底层原因；已确认规划/局部 steering 策略被新版绕过，是高优先级候选。
- 未证明 Python multiprocessing 是瓶颈；应先测量 IPC、OpenCV/GIL、队列和 Host I/O，再决定线程、进程或原生扩展。
- 未证明当前 fault suppression 后视觉能重新启用；需要明确 repair/restart 出口。
- 未完成真实游戏消费证据，不能宣称新版可完整地图测试。

## 2026-10-09 replay evidence

- Added six focused offline replay/process tests. They directly exercise runtime recovery and receipt fusion; all passed.
- The multiprocessing fixtures separate child progress from parent queue draining, but do not claim end-to-end Qt relay decoupling.
- `FollowEnginePort` now owns a session-epoch `RelayLoop`; UI `poll()` is read-only for the latest snapshot. Offline fake-port relay coverage confirms a three-second UI pause does not stop Control/Output progress.
- Real child termination/rebuild and real Qt/Host/game consumption remain unverified.
- Relay/UI concurrent polling is now serialized by `_poll_lock`; first-result compatibility waits on an event instead of entering the worker drain path. Focused port/replay checks: 26 passed.
- J10 review: shared `DYNAMIC_FOLLOW_CONTRACT` now centralizes `12/20/80/8/24/.25`; modular and legacy page paths are explicitly inventoried. Legacy paths still use SimulatedFollowRuntime for compatibility, while route/steering/output components remain the same.
- Legacy route evidence is contract-equivalent only; no independent old-checkout byte replay is available in-process.
## Final audit disposition (2026-10-09)

Source and focused evidence is sufficient to proceed to a controlled user test, with the following evidence labels: J01/J02/J03/J04/J05/J06/J07/J08/J09/J10/J11/J12/J13/J14/J15 are offline verified or contract-equivalent; J16 remains partial because runtime throughput has no real IPC/GIL/Host measurement. No strategy, threshold or movement changes were made in this audit. Full-map and game-consumed claims remain blocked by real Host/game, child rebuild, map-scroll and long-run overshoot evidence.
