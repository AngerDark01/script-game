# PoE2 双人跟随重构偏差修复总规范

> 当前实施补充见 `docs/plans/2026-10-09-follow-evidence-completion.md`（E1–E6）。下文§2的父UI poll阻塞等为历史问题；当前独立Relay已经脱离UI timer。本批补齐父日志汇聚、输出关联与双角色确认，离线证据已记录，实机长跑仍待验收。不要根据历史状态重复架构改造。

版本：1.0
建立日期：2026-10-09  参与范围：双人实时定位、单人/双人动态跟随、移动输出、Vision/Control 双通道

## 0. 文档用途

本文是本任务后续修复、审查、测试和验收的总基线。后续任何代码修改必须先对照本文确定所属问题、边界和验收证据；没有完成本文定义的验收门槛，不得声明“修复完成”“可以正式测试”或“链路已稳定”。

每次上下文压缩、会话恢复或任务重新开始时，第一步必须阅读本文、`docs/POE2_FOLLOW_ROLLBACK_CHECKPOINT.md` 和 `ITERATION_LOG.md`，再继续工作。聊天记录不能替代本文。

## 1. 原计划与不变契约

原始设计文件：

- `docs/POE2_EXPERIMENT_REFACTOR_TASK.md`
- `docs/plans/2026-10-07-poe2-follow-engine-multiprocess-design.md`
- `docs/plans/2026-10-07-poe2-follow-engine-execution-plan.md`

目标运行结构：

```text
Qt UI
  ├── 配置、显示、生命周期
  ├── 不截图、不识别、不规划、不读内存
  └── 不决定 worker 健康

VisionProcess
  └── 截图、墙体、人物候选、双人关联、局部视觉纠偏

FollowControlProcess
  └── 预测、融合、速度、路径、恢复、目标保持、OutputIntent

Output actor
  └── Host lease、心跳、rearm、执行回执
```

不变契约：

1. 单人跟随、双人跟随、点击移动和双人同目标共享同一移动底层，只替换目标源。
2. 动态跟随是持续 session；只有用户手动停止、页面关闭或确认地图实例变化才释放 session。
3. 单帧视觉失配、局部匹配失败、内存失败、路径失败、Host 临时失败、预测到达都不能自动停止跟随。
4. Vision 暂时不可用时，Control 使用上一可信位置、命令回执、速度和地图位置继续运行，并等待下一帧纠偏。
5. 预测只能产生估计，不能替代视觉/内存确认成为永久真值。
6. 所有跨进程消息必须带 generation、sequence、captured_at_ms、map_instance；迟到结果不能覆盖当前会话。
7. 恢复任务必须有界、低频、可取消，不能阻塞 Control tick，也不能重复启动全局恢复。
8. 不允许 Vision、Control、Output 或旧 legacy worker 同时拥有同一资源或 controller lease。

## 2. 当前已确认的偏差

### P0：父侧 poll 仍是运行时单点

文件：`follow_engine/engine.py::FollowEnginePort.poll`。当前顺序是先 watchdog，再由父侧读取 Vision/Control 队列并转发。Vision observation 由父侧送入 Control，Control snapshot 由父侧送入 Output。原计划要求 Control 和 Output 在 UI 轮询暂时停顿时仍能独立运行。

### P0：watchdog 把父侧消费延迟当成子进程故障

文件：`engine.py::_refresh_worker_liveness`、`engine.py::_check_worker_stall`。`_last_progress_monotonic` 只在父侧成功消费 observation/snapshot 时更新，2 秒 running deadline 会把 UI/Queue 空窗误判为 worker stall，并触发 Vision/Control dispose/rebuild。03:17 日志已观察到反复 `vision_dispose → vision_start`。

### P0：旧 worker 到新 worker 的交接证据不足

文件：`capture_test_page.py::_start_modular_follow_experiment`、`stop_dual_motion`、异步 lifecycle 回调。旧 capture 仍可能处于 returning 状态时，新 Vision 已启动；当前没有持久记录资源所有权、旧 worker 完成时间、capture provider 状态和新代首次稳定 tick。

### P1：目标、观测和输出回执的端到端连续性不足

当前可以证明 Control 收到过首个 snapshot，也可以证明 Host 接受过部分报告，但缺少每个 generation 的 target sequence、control tick sequence、output receipt 和游戏实际位移的连续链。P2 因此可能没有跟随、延迟跟随或被重建打断，而日志无法立即区分。

### P1：Control tick 预算没有独立证据

局部 ROI、恢复、地图路径规划可能占用 Control tick。必须记录每个 tick 的 visual drain、prediction、recovery、route、output intent、queue wait 和 total；不能用父侧“没有新 snapshot”推断 Control 已停止。

### P1：文档和验收状态曾高估完成度

离线 fake、spawn 和生命周期测试通过，不等于真实 Qt timer、multiprocessing Queue、旧 worker 交接、Host 消费和游戏位移已通过。后续报告必须明确标注 `offline_verified`、`runtime_observed`、`game_consumed` 三种证据等级。

## 3. 修复阶段

### R0：建立证据链（不得改算法）

目标：让一次失败能定位到 Vision、Control、Output、UI poll、Queue、Host 或游戏消费边界。

必须新增结构化日志：

- session/generation/composition id、worker pid、resource owner；
- child heartbeat/tick sequence/last tick time；
- parent poll sequence、poll gap、queue age、drain count；
- watchdog stale worker、判定输入、触发 reason；
- rebuild begin/old worker stop/new worker ready/commit；
- 每次 target 更新、control snapshot、OutputIntent、ExecutionReceipt；
- Host lease/session/controller ownership；
- 页面 timer active、interval、callback duration；
- 所有 worker 原始 traceback 和 exit code。

R0 未完成前不得修改 watchdog 阈值或恢复策略来掩盖问题。

### R1：修复双通道运行边界

目标：Control 不依赖 UI poll 才能推进；Output heartbeat 不依赖 snapshot poll；父侧只做最新状态观察和有界转发。

要求：

1. worker 自己产生 heartbeat/progress，父侧读取 heartbeat 作为健康证据；
2. watchdog 同时检查 child alive、child heartbeat age、队列状态和父侧 poll gap；
3. 父侧 poll gap 不能直接触发 worker rebuild；
4. Control 继续使用最近观测和命令回执运行；
5. Output actor 独立维持 lease/heartbeat；
6. UI 隐藏或短暂阻塞时不能自动释放 dynamic follow session。

### R2：修复生命周期和资源交接

目标：旧 legacy worker 完全退出后才创建新 capture；stop/start/rebuild 不互相销毁资源。

要求：

1. 旧 worker stop 必须有明确完成事件和超时结果；
2. capture、frame ring、controller lease 必须有唯一 owner；
3. 新 generation 启动前验证旧 generation 已失效；
4. stale lifecycle completion 不得重新启用旧 timer 或旧 adapter；
5. rebuild 只替换故障组件，不无证据地销毁整个 follow session；
6. rebuild 需要保留最新 target、视觉 transform、预测状态和输出 lease。

### R3：修复跟随连续性和目标传播

目标：P1/P2 使用统一移动底层，目标来源不同不改变执行逻辑。

要求：

1. 点击目标、双人同目标、P1→P2、P2→P1 都进入同一 Control target contract；
2. dynamic follow 禁止使用一次性 `WAITING_POSITION` 释放 session；
3. 已在距离范围内时只输出 neutral/hold，目标移动后重新规划；
4. target sequence 必须和 control tick 绑定，不能被旧页面 snapshot 覆盖；
5. 视觉暂失时继续 prediction，下一帧优先 local ROI correction；
6. 只有确认新的视觉/内存位置后才收敛 odometry，不把计划向量当作事实位移。

### R4：性能和恢复预算

目标：保持 25–30Hz 有效人物处理，避免恢复和路径阻塞控制。

要求：

- Vision 使用 latest-only，旧帧不排队；
- 墙体处理和人物候选分频；
- 每个 Control tick 最多一次受预算约束的重规划；
- 局部 ROI、内存和全局恢复异步/低频且 single-flight；
- 每个阶段耗时有 EMA、p95、max；
- 任何单次阶段超过预算只降级，不自动停止。

### R5：分层验收

按顺序验证：

1. 离线纯模块契约；
2. Windows spawn 和真实 Queue；
3. Qt timer/poll 空窗模拟；
4. legacy→modular 资源交接；
5. fake Host receipt/heartbeat；
6. 用户授权后的 R1 静止双人；
7. 单方向移动、转向、视觉暂失、颜色污染、门/窄道、Host rearm；
8. 完整地图长时间运行，无时间硬限制。

## 4. 验收证据标准

每个阶段必须提供：

- 代码文件和函数范围；
- 失败场景或回归测试；
- 日志样本和关键字段；
- 阶段耗时与处理频率；
- 未覆盖边界；
- 是否连接真实游戏/内存/Host/输入。

证据等级：

- `offline_verified`：纯函数、fake、replay 或离线 spawn 通过；
- `runtime_observed`：真实页面/进程/Queue/Host 运行中观察到；
- `game_consumed`：日志、截图或内存共同证明游戏角色实际移动。

只有 `game_consumed` 覆盖 R1–R8 后，才允许说“可以开始完整地图测试”。

禁止使用以下表述替代证据：

- “测试全通过，所以实机没问题”；
- “Host 收到报告，所以人物一定移动”；
- “首个 snapshot 正常，所以跟随链正常”；
- “没有看到 traceback，所以 worker 没有错误”；
- “离线重建通过，所以真实重建安全”。

## 5. 每次工作和上下文恢复规则

开始工作前：

1. 阅读本文；
2. 阅读 `POE2_FOLLOW_ROLLBACK_CHECKPOINT.md`；
3. 阅读 `ITERATION_LOG.md` 最新条目；
4. 查看当前 git 状态和最近检查点；
5. 明确本轮只处理一个根因边界。

每个重要发现、代码边界、失败实验、用户决策和验证结果必须立即更新：

- 本文的阶段状态或问题清单；
- `POE2_FOLLOW_ROLLBACK_CHECKPOINT.md`；
- `ITERATION_LOG.md`。

每次代码修改后必须：

1. 做 codebase ontology SYNC；
2. 跑对应 focused tests；
3. 跑 compileall 和 diff check；
4. 更新本文验收状态；
5. 明确仍未验证的真实边界。

## 6. 当前状态

状态：`R1_FAULT_BOUNDARY_OFFLINE`。  
已完成：FollowEngine parent poll 周期/间隔/进度年龄、watchdog stale 输入、父侧最后事件、Vision child 每 30 帧进度、Control child 每 30 tick 进度和 pid 日志已加入；compileall、diff check 通过，相关端口/控制/视觉测试 `29 passed`。  
新增完成：03:44 确认 Vision contract fault（wall_quality raw response 越界）；wall adapter 已归一化，重复相同 fault 的 rebuild 已受抑制，Control decision 日志已补齐。  
未完成：尚未证明旧版移动策略与新版等价；尚未完成真实页面/Host/game-consumed 验证，尚未进入完整 R1。  
当前禁止：继续调识别阈值、继续增加恢复分支、声明新版已修复或要求用户进行完整地图测试。  
下一动作：用新增日志做一次真实/离线父子进度对照；若证明父侧 poll gap 被误判，进入 R1 修复 watchdog 健康判定和独立心跳。

补充：FollowEnginePort 已引入 session-epoch `RelayLoop`，UI poll 改为只读最新快照；离线 fake-port relay 测试验证 UI 暂停 3 秒时 Control/Output 仍推进。真实 child rebuild、Qt/Host/game 消费仍未验收。

### 2026-10-09 replay batch update

新增六项离线 replay/process 回归并全部通过；它们直接覆盖局部纠偏、receipt 时间融合、memory 单飞/cooldown、代际/重复消息拒绝及 child progress/stall。J04/J05 仍未达到 Qt 端到端 relay 解耦证据，J02 仍为 contract-equivalent，真实游戏/Host/内存边界继续保持未验证。
## J01–J17 final audit snapshot (2026-10-09)

The current implementation has offline evidence for all functional boundaries except J16's real throughput evidence. Legacy movement is restored through `SimulatedFollowRuntime`; the new architecture changes evidence/fusion and process transport only. `106` minimal focused tests passed with compileall/diff-check. Remaining blockers are explicitly runtime-only: real Host/game consumption, forced child rebuild, map-scroll handover, long-run P2 overshoot, and production IPC/GIL/Qt throughput. These must remain marked unverified until a controlled user test supplies evidence.
