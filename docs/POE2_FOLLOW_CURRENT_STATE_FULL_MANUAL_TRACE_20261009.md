# PoE2 跟随当前状态：完整人工运行推导（2026-10-09）

本文只做源码事实和运行时序推导，不修改运行代码，不启动游戏，不读取内存，不连接 Host，不发送手柄输入。目的不是证明系统可用，而是回答：用户点击开始跟随后，当前代码实际上会走哪条链，旧代码在哪里仍存在，正常帧和异常帧是否形成闭环。

## 1. 先给结论

当前代码不是“旧版和新版同时驱动人物”，也不是“旧 worker 残留后台进程”。模块化入口启动时会主动停止页面内的旧 `Poe2DualMotionWorker`，随后由 Vision 子进程、Control 子进程和 Output actor 接管。这个停止动作是为了避免两个视觉/输出所有者同时工作。

但当前也没有达到“旧版运行链已不存在”的目标。旧入口、旧 worker、旧首帧线程、旧 timer、旧页面状态和兼容 fallback 仍然编译在页面中；部分 target relay 仍保留兼容路径；模块化 UI 预览仍没有从 SharedFrameRing 接回页面。因此当前状态应准确描述为：

> 新的运行编排已经存在，稳定算法积木部分被新 Control adapter 复用；旧页面运行入口和兼容边界仍存在，真实游戏闭环尚未被证明。

这也解释了两个看似矛盾的现象：日志里会出现“停止旧 dual_motion worker”，但这不表示它是残留进程；模块化 worker 显示 running，也不表示 P2 已经移动。

## 2. 当前入口和前置条件

实际点击路径是：

```text
Qt 点击 start_follow_button
  -> capture_test_page.start_follow_experiment()
  -> _start_modular_follow_experiment()
  -> _ensure_modular_follow_adapter()
  -> build_follow_seed_from_dual_result()
  -> build_poe2_follow_engine_page_adapter()
  -> FollowEngineUiAdapter / FollowEnginePort
```

模块化启动前必须已经有：

1. 有效地图实例 `map_instance`。
2. 已接受的双人首帧结果，包含 P1/P2 的 native 坐标、screen 坐标和 similarity transform。
3. 页面选定控制角色。`p1_leads` 表示 P1 是 source、P2 是 follower；反向模式相反。
4. 有效的 PoE2 monitor binding、wall map 和 program output factory。
5. Control 能够使用 seed 构造局部搜索、旧路线/运动 adapter，以及可选内存恢复 source。

首帧并不只是 UI 图片。`FollowSeedBundle` 会把地图实例、角色 controller、观察角色、native/screen seed、transform、marker profile 和 identity hint 作为跨进程可序列化配置传给新 worker。首帧定位本身仍由页面的旧双人识别入口产生，这是当前新旧边界尚未完全清理的第一处。

## 3. “停止旧 dual_motion worker”到底是什么

`Poe2DualMotionWorker` 位于 `ui/modes/poe2_live_terrain/dual_motion_worker.py`，是 Qt 页面创建的旧版工作对象，内部用线程采集截图并做旧双人识别。它不是上一次运行遗留的 Python 子进程，也不是新 Vision 子进程。

模块化接管时的顺序是：

```text
发现 _dual_motion_worker 或旧 timer 仍活动
  -> 记录 modular_takeover
  -> stop_dual_motion(clear_first_frame=False, preserve_follow=True)
  -> 释放旧采集/识别 timer 和旧 tracker 的活动所有权
  -> 保留已接受的首帧 seed
  -> 启动新的 Vision/Control/Output 链
```

必须停止它的原因是同一块小地图不能同时由两个所有者采集和写 tracker：旧 worker 会继续产生旧识别结果，新的 Vision 又会产生新 observation；如果两者都继续写 target、preview 或 output，就会出现代际混用、坐标覆盖和重复输入。停止旧 worker 是所有权切换，不是兼容旧算法的运行步骤。

当前问题在于：停止动作只是运行时接管，旧类和旧入口仍然存在，页面仍能通过 `start_dual_motion()`、`_tick_dual_motion()`、`stop_dual_motion()` 和旧首帧 worker 进入旧链路。新架构若要真正“只用新的东西”，最终应把这些入口限制为首帧 seed producer 或明确的离线工具，而不能再让它们成为跟随 session 的可选运行驱动。

## 4. 启动时序：实际发生什么

### 4.1 页面和端口

`_start_modular_follow_experiment()` 先设置 live policy，再创建 `FollowEngineStart`。如果发现旧 output 或旧 runtime 仍活动，会先提交旧 follow stop；如果旧 dual-motion worker/timer 活跃，则调用上面的 takeover stop。

`FollowEnginePort.start()` 创建新的 generation 和 session epoch，然后按以下顺序启动：

```text
ControlProcessHandle.start()
  -> Windows spawn Control child
VisionProcessHandle.start()
  -> Windows spawn Vision child
OutputPort.start()
  -> SnapshotOutputAdapter / AsyncSnapshotOutput actor
RelayLoop.start()
  -> 父进程内部的 transport consumer
Qt follow timer.start()
  -> 页面只读 FollowUiState
```

每个 stage 都有 begin/completed 日志。spawn 阶段会 pickle runtime factory 和 DTO；历史上 `TimingWindow._lock` 没有 spawn-safe 序列化，曾直接触发 `cannot pickle '_thread.lock' object`。这说明 Python spawn 边界曾有对象契约错误，但单凭这一处不能证明 multiprocessing 技术本身必须更换。

### 4.2 10 秒前台交接闸门

PoE2 页面和 `SnapshotOutputAdapter` 当前默认 `arm_delay_ms=10_000`。闸门期间 Vision/Control 继续工作，Output actor 建立 neutral lease、发送/保持 heartbeat，所有非零 intent 被压制。10 秒结束后才允许真正的非零 output。该闸门是切回 PoE2 的前台交接时间，不是跟随总时长。

这里有一个文档风险：较早的链路文档仍写过 6000ms；当前页面常量和具体 PoE composition 是 10000ms，应以源码为准，旧文档中的 6000ms 不能继续作为当前参数。

## 5. 正常运行：一帧的完整时序

以下假设 P1 为 leader、P2 为 follower，且已过 10 秒闸门。

### 5.1 Vision 线

```text
Vision child capture
  -> SpawnSafePoe2MonitorCapture 获取新截图
  -> EncodedImageCapture 编码
  -> SharedFrameRing 写入最新帧
  -> DualObservationProcessor 解码、墙体/地图位移、marker 候选、角色关联
  -> 生成 VisualObservation(sequence, captured_at, generation, map, roles, transform)
  -> VisionProcessEvent 放入 latest-only event queue
```

Vision 只拥有采集、识别和 observation；它不应该直接写手柄，也不应该拥有 follower 的路线状态。SharedFrameRing 是帧数据通道，event 通道主要传 observation 元数据。

### 5.2 Control 线

Control child 每轮从三条独立通道读取：visual、target、priority。visual 是可替换状态，target 按角色合并最新值，priority 保留 execution/recovery/stop 等有顺序语义的消息。每通道有自己的 generation/sequence gate，不能把三者当成一个全局 FIFO。

在正式动态跟随 composition 中，runtime factory 把 `live_target_source=P1` 和 `live_target_roles=(P2,)` 传给 `FollowControlRuntime`。当 P1 的 observation 被 Control 接受后，`apply_visual()` 内部直接调用 `_refresh_live_target()`，把接受的 P1 native position 写入 P2 target。这是预期的实时主路径。

父端 `FollowEnginePort` 仍保留 `_forward_live_target_observation()` 和 `update_target()` fallback。composition 同时设置 `control_owns_live_targets=True`，因此正式动态路径应跳过父侧 relay；但旧 adapter 或其他 composition 仍可能走 fallback。若要满足“新架构不依赖旧兼容入口”，必须把正式动态 path 的 ownership 变成不可配置的单一契约，并让 fallback 只存在于显式 legacy test adapter。

### 5.3 Fusion、预测和恢复

Control 接受 observation 后按角色执行：

1. 用 generation、sequence、map 和 transform 过滤迟到帧。
2. 对 accepted visual 与上一可信 anchor 做 innovation/fusion；被拒绝候选不能刷新速度校准或健康时钟。
3. 积分已接受的 execution receipt；迟到 observation 会先回退 captured_at 之后的 receipt 段，再由后续 tick 重新推进，避免重复积分。
4. 视觉成功时刷新角色位置、uncertainty、velocity、odometry 和 P1→P2 target。
5. 视觉暂时失配时保持 session，使用上一可信状态和预测；下一帧优先局部 ROI search。局部搜索使用与 Vision 同代 transform 和最新 frame，不应永久复用旧 screen anchor。
6. local 失败后才按角色 cooldown 使用 memory source；两条线仍不能恢复，才进入 global/rebuild。memory 不是每 tick 读取的主路径。
7. `LegacyDynamicFollowRouteController` 只应负责把融合后的 position/target 交给已有 `SimulatedFollowRuntime`、PathFinder、VectorPathTracker、LocalMotionController 和 closed-loop 运动组件。它不应复制一套新的固定 pulse 公式。当前源码已经改成薄 adapter，但完整 a3070ea 独立 checkout 的逐 tick 等价仍未证明。
8. runtime 生成 `FusionSnapshot` 和 `OutputIntent`。动态跟随是持续 session；接近预测 arrival 只能进入 hold/纠偏，不能因为某一个目标到达而进入全局 `WAITING_POSITION` 或停止整个 session。

### 5.4 Output、Host 和游戏

```text
FusionSnapshot
  -> FollowEnginePort / AsyncSnapshotOutput latest snapshot
  -> SnapshotOutputAdapter
  -> OutputScheduler lease + heartbeat + rearm
  -> ProgramGamepadOutput.write()
  -> Host/virtual gamepad
  -> ExecutionReceipt
  -> parent receipt forward
  -> Control priority queue
  -> CommandOdometry
```

Output actor 是父进程中的独立线程，并且应是唯一真实 Host I/O 写者。receipt 只证明 Host/adapter 接收了 pulse，不能证明 PoE2 游戏窗口获得焦点，也不能证明 P2 已经移动。当前日志曾有 `first_output_apply`，但缺少逐 tick 的 write、receipt、Host state 和游戏画面位移关联，因此“worker running”或“first output apply”都不等于闭环成立。

## 6. 异常时序的人工推导

### 6.1 spawn/pickle 失败

如果 spawn 在 child entry 前失败，Vision/Control 不会产生 first progress。父端应记录 start stage、原始 traceback，逆序停止已创建 component，关闭 ring 和 output。历史 `TimingWindow._lock` 错误已在工作树修复并有离线 spawn 回归；仍需真实启动日志确认当前 GUI 已加载新代码。

### 6.2 Vision capture 或 processor 失败

Vision 发布 error/stopped，父端记录 worker fault。Control 不应继续把旧 observation 当成新事实无限运行；应进入有界 prediction，随后 local-first，必要时 memory cooldown，再决定 rebuild。对同一 worker/epoch/generation/signature 只允许 single-flight rebuild，不能因为持久 first_fault 抑制所有后续可恢复故障。

### 6.3 单帧视觉失配或丢失

正确链路应是：

```text
新帧可用但角色失配
  -> 立即用该新帧做局部 ROI search
  -> local 成功：校正 native position/target/odometry
  -> local 失败：短时预测维持 session
  -> 达到 memory cooldown：一次内存 anchor
  -> 仍失败：global/rebuild
```

失败一次不能停止持续跟随，也不能永久盲预测。当前 local/memory/rebuild 契约已有离线 fixture，但“真实 Vision 新帧到 Control、局部成功、继续输出”的完整游戏运行证据尚不存在。

### 6.4 Control tick 超预算

Control 内的 local recovery、A*/route plan、fusion、output intent 目前仍在同一 child tick 的同步上下文中。虽然 cadence 已改为 start-to-start，单次 ROI 或 A* 超过 33ms 仍会延迟下一次 target 消费、snapshot 和 output。timing 已有 p50/p95/max 结构，但没有真实 Host/PoE2 场景的预算证据。这个问题不能仅靠 heartbeat 判断已解决。

### 6.5 Output/virtual gamepad 失败

Output actor 失败时应 neutralize 当前 lease，按退避重启并重放最近 snapshot；Control session 可以保留。heartbeat/rearm 必须持续，即使当前 intent 为 neutral。若 Host 接收成功但游戏未消费，receipt 会看起来正常，故必须额外记录窗口焦点/controller ownership 和游戏内位置。

### 6.6 Control/Vision child 退出、stall、rebuild

父端使用 startup/running stall watchdog。rebuild 必须：取消旧代、停止旧 handle、保存最新可信 native position 和最新 transform、创建新 ring/worker、校验 session epoch/generation、原子 commit，最后 retire 旧资源。迟到 bundle 不能覆盖新 session。当前这些边界有离线生命周期测试；真实 child 被杀、重建、P2 连续移动仍未实证。

### 6.7 Qt UI 暂停

当前已加入 RelayLoop，UI `poll()` 应是只读快照，不再作为 worker queue 的唯一消费者。因此 Qt 页面暂时卡顿不应停止 Vision/Control。可是这仍需真实窗口阻塞场景验证，且 UI preview 目前未从 SharedFrameRing 接回，页面截图不变不代表 Vision 不动。

### 6.8 手动停止

只有用户停止按钮、页面关闭或明确 lifecycle shutdown 才能结束持续跟随。停止顺序应是：停止接收新 output → neutral/release lease → 停止 relay → 停止 Vision/Control → 关闭 queues/ring → 清理 composition/UI timer。重复 stop 必须幂等，旧 generation 的迟到事件不能改变新 session。

## 7. 新旧边界：哪些该保留，哪些不该运行

| 类别 | 当前状态 | 新架构目标 |
|---|---|---|
| PathFinder、VectorPathTracker、LocalMotionController、SimulatedFollowRuntime | 作为 route adapter 复用 | 保留功能、参数和策略，只通过 spawn-safe DTO/adapter 被 Control 调用 |
| 首帧识别算法 | 页面旧入口产生 seed | 可保留为 seed producer，但不能让旧实时 worker继续拥有跟随 session |
| `Poe2DualMotionWorker` | 页面中仍存在，模块化接管时主动停止 | 从正式跟随运行图移除；最多保留显式 legacy/diagnostic 模式 |
| `DualMotionMixin`、旧 dual timer、旧 preview | 仍参与页面生命周期和兼容分支 | 不得驱动模块化 session 的 target、output 或恢复 |
| `FollowEnginePort` relay | 正式动态 target 设计为 Control-owned，仍保留 fallback | 主路径单一；fallback 必须显式隔离，不能静默参与 |
| SharedFrameRing | 新 Vision 写入 | 页面如需预览，增加只读 preview bridge，不改变 Control ownership |
| OutputScheduler/ProgramGamepadOutput | 新 Output actor 使用 | 保留现有 lease、heartbeat、neutral、receipt 语义 |

因此“旧模块能复用”和“旧版运行链继续存在”是两件事。积木可以是旧的，搭积木的入口、所有权和时序必须是新的。

## 8. 当前证据等级

| 链路 | 当前证据 | 能否称为真实跟随成功 |
|---|---|---|
| Windows spawn、generation、queue、ring | 源码 + 离线 focused tests | 不能 |
| Vision wall/marker/transform DTO | 源码 + 离线 processor tests | 不能 |
| Control fusion、预测、local/memory/rebuild 契约 | 源码 + 离线 replay/fixture | 不能 |
| 旧运动积木 adapter | 源码 + equal-input fixture；无独立 a3070ea checkout byte replay | 不能 |
| Output actor、neutral、heartbeat、receipt FIFO | 源码 + fake output tests | 不能证明游戏消费 |
| 页面启动、first snapshot、first vision | 有历史真实日志 | 只能证明 child 有进展 |
| 页面实时预览 | 当前模块化路径缺少 ring→UI bridge | 当前截图不具备诊断意义 |
| Host 接收后的 PoE2 位移 | 未记录 | 完全未证实 |
| P1 移动后 P2 跟随连续性 | 未记录完整 target→intent→receipt→位移链 | 完全未证实 |

## 9. 当前必须承认的阻断

1. 旧页面入口和旧 worker 仍存在，正式架构边界没有物理收口。
2. UI 预览没有接入新 Vision 帧，左侧截图不变不能直接判断 Vision 是否停止。
3. 真实输出 write、receipt、Host heartbeat、游戏消费和 P2 位移没有一条可关联证据链。
4. 父进程仍持有 relay/fallback 复杂度，虽然正式动态 composition 设置 Control ownership，但其他入口容易重新走 fallback。
5. local-first→memory cooldown→global/rebuild 只有离线推导和 fixture，没有真实 child/游戏连续运行证明。
6. Control 同步恢复/A* 仍可能挤占 33ms tick，性能预算尚未以真实场景闭合。
7. 启动 pickle 修复只证明当前对象可序列化，不能证明所有未来 runtime factory 都满足 spawn-safe 契约。
8. “进程 running”“heartbeat 存在”“页面状态 tracking”都不是跟随闭环成功条件。

## 10. 最终判断

如果要求“新架构只运行新入口，旧版接口不再参与实际跟随”，当前代码还没有完全达到。当前实际更准确的状态是：新 Vision/Control/Output 编排已搭起，旧算法积木已有一层 adapter，正式动态 target 已有 Control-owned 设计；但旧页面兼容入口仍在，真实 Host/游戏闭环和异常连续性仍未证明。

因此现在可以做的是基于这份状态继续决定边界收口方案；不能把当前状态报告成“已经可稳定实测”。任何下一步修改都应先保持旧算法功能和参数不变，只收口运行所有权、DTO/adapter 边界、可观测证据和异常时序。

## 11. 本轮已实施修复后的再推导

本轮已经完成一项正式入口修复：页面 `start_follow_experiment()` 在没有模块化 adapter/factory 时现在 fail-closed，不再落入旧版页面 runtime。由此，点击正式跟随按钮的入口分支变为：

```text
有 modular adapter
  -> 停止可能存在的旧 session/旧 dual-motion 所有权
  -> 创建新 seed/新 composition
  -> 启动新 Vision/Control/Output/Relay

无 modular adapter
  -> 记录 adapter_unavailable
  -> 显示“旧版跟随已禁用”
  -> 不创建旧 runtime、不启动旧 follow timer、不写旧 output
```

这消除了“新架构初始化失败后悄悄回退旧逻辑”的确定性错误。离线 page/adapter/port/control 回归为 44 passed，扩展 follow focused collection 为 83 passed，compileall 和 diff-check 通过。

再次从按钮开始模拟时，正式入口不会再出现旧 runtime 与新 runtime 竞争的分支；但旧首帧 seed producer、旧算法 adapter 和页面旧类本身仍在代码树中。下一步仍需把旧实时 worker 明确限制为 seed/diagnostic producer，并补齐模块化 SharedFrameRing 的只读 preview bridge。上述离线结果不等于真实 Host/game/P2 movement 已验收。
