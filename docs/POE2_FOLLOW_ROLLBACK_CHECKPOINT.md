# PoE2 跟随优化回退断点（2026-10-07）

## 2026-10-09 E1–E6 当前执行位置（优先续读）

- Git 备份：用户要求保存当前版本；提交累计源码、测试、文档（含 E1–E6），不纳入 data 下运行截图/诊断产物，不推送远端。此为实测前检查点，不代表实机验收通过。下一步用户测试新会话并分析证据日志。

- 用户要求重启工作台：旧工作台已退出，未清理不相关 spawn_main。2026-10-09 21:10:08 新实例 PID=12420，窗口“auto_modules · 实时小地图拼接系统”Responding=True，runtime.log 确认 Admin=True、单实例锁成功、主窗口已启动。未自动开启跟随或发送游戏输入。下一步由用户实测，按新会话日志核对 E1–E6。

- `(latest)` E1–E6本批已实现和同步CODEBASE；111组合通过，新增pending不得经ROI绕过及重复/长间隔不得两帧确认后33相关通过。未重启/未连接Host/未发送游戏输入。按计划文档“下次日志检索”采集新会话；不要拿18:39旧日志验收新增代码。
- `(correction)` 上轮“都已实现”过强：本批确实发现并修复了确认后confidence=0、全图单候选范围错误、ROI过滤绕过。父Relay脱离UI已经实现，不需要为日志问题重新改为进程直连。测试替身缺方法也不证明实机崩溃。

- 任务目标与验收：`docs/plans/2026-10-09-follow-evidence-completion.md`。E1 页面显示异常隔离与正确 frame/tick 字段已完成，12 passed。旧 SimpleNamespace 缺方法只证明测试替身过时；新增坏渲染用例才证明状态更新被阻断。
- E2/E3：新增 `follow_engine/diagnostic_events.py`，容量 32/48 的采样事件历史随 VisionProcessEvent/Control diagnostics 传回父 Relay，按 stream/epoch/generation/id 去重，历史溢出报 diagnostic_gap。fusion 接受/拒绝、local 冲突、memory submit/completion/failure、recovery 实际配置均有证据。无需依赖 spawn child 的 logger handler。
- E4：OutputIntent/ExecutionReceipt 增加 control_tick/target_revision/visual_sequence，SnapshotOutputAdapter 记录 transport_only 回执，Control 记录 receipt_consumed 与后续 observed_motion；中立回执裁剪保留元数据。相关 22 passed；尚待最终组合验证。
- E5 新发现并修复：原单候选只统计全图，双角色各一个候选不会确认；确认远点在 _build_roles 被降为 confidence=0，再被 Control 拒绝；角色级 ROI 仍有0.82软惩罚且绕过48面积过滤。现在按唯一角色颜色分组连续确认，pending 禁止 geometry fallback 抢走角色，确认位置用 visual_confirmed 修正且不训练跳变速度，ROI 过滤48以上和其他身份。
- E5 验证：双角色交换预测用例修前失败修后通过；确认→DTO→Control→leader target 与速度不污染通过；ROI 大色块/另一角色/正确点用例通过。相关最新 26 passed，未发真实输入。下一步复核确认的时间连续性/日志成本，运行最终 focused 集合，同步 CODEBASE 和任务状态。

## 2026-10-09 最新实测截图/日志只读核对（本轮不改代码）

- `(confirmed)` 截图 1 的实验页三个预览仍是首帧：传送点和两角色在起点附近；截图 2 的 PoE2 小地图已经滚动到另一片区域，P1/P2 仍在同一视野且相距很近。两张图证明 **UI 预览显示没有跟随模块化运行更新**，不能单独证明 Vision 没有处理帧。
- `(confirmed)` 同一会话 `16:53:43.779` 模块化 FollowEngine 启动；`16:53:44.567` 已收到首个 Vision observation；随后 parent poll 每约 15–16ms，`progress_age_ms.vision` 大多 15–79ms，worker_state 始终 running。Vision/Control 子进程没有在 terrain 主日志中输出逐帧 decision，子进程日志配置/汇聚仍不足。
- `(confirmed)` `dual_motion` 旧页面预览线程在 `16:53:42.732` 被停止并延迟退休；模块化 Vision 写 SharedFrameRing、Control 消费 observation，但 `FollowUiState` 只有 snapshot/diagnostics，`_poll_modular_follow_engine()` 不读取 ring/新 frame，不更新三个预览面板。因此面板冻结是已确认的 UI bridge 缺失。
- `(confirmed)` 模块化 Output 在 `16:53:54` 至 `16:54:50` 持续向 controller=2 提交非零轴；Host 日志 `backendConnected=True`。这证明控制意图至少到达 ViGEm/Host，不证明游戏消费或 P2 实际位移。
- `(confirmed)` `16:54:51.425` 起页面 output diagnostics 的 `last_command` 连续为 `(0,0)`，`acquired=True`、heartbeat_failures=0、session_expired=False；不是 Host 断联。当前 terrain 日志没有 child `control_decision`/`snapshot reason`，无法仅凭主日志判定这是合法 `FOLLOW_HOLD`、错误 arrival、目标未更新，还是游戏未消费输入。
- `(confirmed)` 最终 `16:55:12.410 stop_requested` 的 caller 是 `suspend <- hideEvent`，停止由页面隐藏/关闭触发，不是日志中的算法自动 stop；Control 在 `16:55:14.578` 强制终止，说明退出仍未完全优雅，但不是本次前期卡住的直接证据。
- `(source-confirmed)` `FollowEnginePort._poll_once_unlocked()` 的顺序是 Vision observation → `control.send_visual()` → live target forwarding → Control snapshot → output.apply；Control `apply_visual()` 接受 leader 后同 tick `_refresh_live_target()` 更新 follower target。`FusionSnapshot` 没有 `tick_sequence` 字段，页面日志中的 `snapshot_tick=None` 是诊断字段契约错位，不是帧没推进证据。
- `(root-cause boundary)` 本次已能确定两层问题：① UI 预览冻结造成“仍在首帧”的假象；② 后期 P2 中性输出的确存在，但缺少 Control 决策理由和视觉→融合→intent 的可追踪证据，暂不能把它归因于视觉未参与。下一步应只读补齐 child progress/decision 与 snapshot tick/sequence 证据，再判断后期 hold/arrival/目标刷新链路。
- `(next exact)` 在任何代码修改前，补查 `control_process_entry` 的 child logging 配置、`FusionSnapshot`/ControlProcessEvent 的序列字段、Output intent→Host receipt 时间轴，并对比 `16:54:50–16:55:05` 的最后非零→中性切换；不改阈值、不改运动策略。

## 2026-10-09 P2 后期中性诊断日志补强

- `(finding-correction)` 复核 Host 原始日志后，`16:54:51` 页面采样到零向量并不等于之后一直为零；Host 在 `16:54:53–16:54:54` 仍出现 controller=2 非零报告。因此原先“51 秒后持续 neutral”的表述过强，必须以同一 tick/receipt 时间轴判断。
- `(implemented)` ControlProcessEvent 新增 `tick_sequence` 和有界 `diagnostics` DTO；每个 Control snapshot 携带最新 control decision 摘要，父端只在 tick=1、每 30 tick 或决策签名改变时记录 `control_decision_observed`，避免每帧刷日志。
- `(implemented)` 诊断摘要包含：latest/accepted visual sequence、角色 visual accepted/visible/position、accepted evidence age、融合 position/source/uncertainty/misses、P1→P2 target、recovery state/reason、intent vector/duration/neutral、tick/recovery/route timing。
- `(implemented)` FollowEngine diagnostics 暴露 `last_control_diagnostics`，并用 ControlEvent.tick_sequence 填充 `last_parent_event.control`；不修改路径、脉冲、速度、到达半径或输出策略。
- `(verified-offline)` `py_compile` 通过；follow control/process/port/runtime focused collection `46 passed`。未启动游戏、未连接 Host、未发送真实输入。
- `(next exact)` 用户进行一次完整跟随测试，手动停止前保持运行；复制包含 `control_decision_observed` 的 terrain 日志，并同时提供 Host 日志同一时间段。重点查看最后一次 `neutral=false` 到 `neutral=true` 的 tick、P2 source/position、P1 target、visual accepted 和 recovery_reason。

## 2026-10-09 当前完整状态人工推导（只读）

- `(scope)` 本轮没有修改运行代码、没有启动游戏/Host、没有发送真实输入；目标是按用户新要求推导“点击开始→正常逐帧→异常恢复→手动停止”的真实链路，并区分新运行链、旧算法积木和旧页面兼容入口。
- `(confirmed)` 模块化入口会在启动新 Vision/Control/Output 前调用 `stop_dual_motion(clear_first_frame=False, preserve_follow=True)`；`Poe2DualMotionWorker` 是页面旧线程，不是残留后台 Python 子进程。停止它是避免双视觉/双 tracker/双 output 所有权冲突。
- `(confirmed)` 旧 `DualMotionMixin`、旧 worker、旧首帧线程、旧 timer、旧 preview 和 fallback 入口仍在页面代码中；因此运行时接管是新的，架构物理边界尚未收口，不能声称旧版已不存在。
- `(confirmed)` 正式 PoE composition 将 live target policy 传入 Control runtime，并设置 `control_owns_live_targets=True`；accepted source observation 在 Control `apply_visual()` 内更新 follower target。`FollowEnginePort` 的 parent relay/fallback 仍保留，其他 adapter 可能重新使用它，需继续隔离。
- `(confirmed)` 当前页面/PoE composition 的输出 arm gate 为 10000ms；旧链路文档中的 6000ms 已过时，以源码为准。闸门只禁止非零 output，Vision/Control 仍应继续运行。
- `(confirmed)` 当前完整人工推导文档已写入 `docs/POE2_FOLLOW_CURRENT_STATE_FULL_MANUAL_TRACE_20261009.md`，包含启动、逐帧、异常、旧新边界、证据等级和阻断项。
- `(blocking)` 仍无真实 Host write→receipt→PoE2 游戏消费→P2 位移的关联证据；无真实 child kill/rebuild/map-scroll 连续性证据；模块化 Vision→UI preview bridge 缺失；Control 同步 recovery/A* 的真实 33ms 预算未闭合。
- `(next exact)` 任何实现前先以该文档为基线，审查正式跟随入口是否能排除旧 runtime/worker/fallback；只保留旧算法模块作为 Control adapter，不能改变其功能、参数和运动策略。

## 2026-10-09 正式入口旧版 fallback 封口

- `(fixed)` `capture_test_page.start_follow_experiment()` 现在是 modular-only；缺少 page adapter/factory 时直接记录 `adapter_unavailable` 并拒绝启动，不再构造页面内旧 `SimulatedFollowRuntime`、旧 timer 或旧 program output。
- `(boundary)` 旧算法类仍由 Control 子进程的 `LegacyDynamicFollowRouteController` 复用；本次只封掉页面正式按钮对旧运行时的 fallback，没有修改路径、局部避障、pulse、arrival/hold 或手柄参数。
- `(verified)` page startup/adapter/port/control focused collection `44 passed`，`py_compile` 通过；未启动游戏、Host、内存或真实输入。
- `(next exact)` 继续补齐 modular Vision frame 的只读 UI preview bridge 和完整生命周期模拟；preview 不能重新启用旧 capture worker，也不能让 UI poll 成为 Control transport owner。

## 2026-10-09 生命周期/退出清理修复（本轮）

- `(root-cause)` 页面关闭原先调用 `stop_follow_experiment()` 后立即对 lifecycle executor `shutdown(wait=False)`；若 stop 任务尚未完成，Qt/Host 管理器会先继续退出，导致模块化 Vision/Control 或输出 lease 残留。`Poe2LiveTerrainPage.shutdown()` 在监控 worker 超时也直接 return，进一步跳过跟随清理。
- `(fixed)` capture page 保存 lifecycle future；shutdown 对已提交的 start/stop 生命周期任务等待最多 4 秒，并以 `wait=True` 关闭 executor；terrain page 即使定位 worker 超时也继续进入 capture page 的终止清理。
- `(fixed)` `ProgramGamepadOutput.stop()` 在仍有非零摇杆时按 `neutral -> release -> client close` 顺序发送零状态；已是零状态时记录 `neutral_skipped`，仍保持 heartbeat 语义。
- `(observability)` Vision/Control 记录 child PID、stop 请求、强制终止、退出和 queue close；engine/composition/ring、output actor/scheduler、Host neutral/release 均记录结构化生命周期事件。engine diagnostics 暴露 `worker_pids`，页面每 30 次 poll 将 worker/output 状态写入 UI 日志。
- `(ui)` 日志页新增“复制日志”按钮，直接复制当前最多 500 行 session log。
- `(verified-offline)` program gamepad + modular startup/composition/port/output focused `58 passed`；compileall 与 diff-check 通过。未启动游戏、未读取内存、未连接真实 Host、未发送真实输入。
- `(next exact)` 用户实测：开始跟随→运行至少数秒→手动停止→关闭程序；复制 UI 日志，重点检查 `output_actor_stopped`、`program_output.neutral/released`、`vision/control_process_stopped`、`queue_closed`、`lifecycle_shutdown_finished`，并确认游戏不再保持手柄状态。
- `(race-fixed)` 页面隐藏/主窗口关闭可能先后调用 `suspend()` 与 `shutdown()`；重复 stop 现在被 `stop_coalesced` 合并，避免对同一已关闭 ring/queue 二次 dispose。
- `(verified-offline)` 页面启动 + gamepad 回归 `21 passed`，compileall/diff-check 通过。

## 2026-10-09 新架构完整人工运行推导（本轮，不改代码）

- `(source-confirmed)` 按“点击开始跟随→spawn→首帧→Control tick→Output actor/Host→视觉暂失→rebuild→手动停止→程序关闭”完整模拟后，当前仍是过渡架构：新 Vision/Control/Output 进程边界存在，但页面仍保留 legacy runtime/dual motion/probe/target 分支；正式 PoE2 composition 还通过 `LegacyDynamicFollowRouteController` 调用旧 `SimulatedFollowRuntime`/旧 routing primitives。
- `(source-confirmed)` Dynamic follow 的正式 composition 已设置 `control_owns_live_targets=True`，Control `apply_visual()` 接受 leader 后同 tick 刷新 follower target；页面 relay 只应是兼容 fallback。该边界与“目标来源替换、移动策略不变”的积木契约一致，但必须禁止 legacy 页面 runtime 参与同一 session。
- `(architecture-gap)` 当前不能宣称“旧版已完全不存在”：旧接口和兼容路径仍可被构造；需要先完成 modular-only ownership map 和策略 adapter contract，再清理入口，而不是继续调算法。
- `(evidence-gap)` 离线 58 passed 只证明 spawn/queue/cleanup contract；仍没有 game-consumed 证据链 `button→generation→visual→control→intent→Host accepted→receipt→P2 movement`。
- `(documentation)` 新增 `docs/POE2_FOLLOW_NEW_ARCH_MANUAL_RUNTIME_AUDIT_20261009.md`，记录完整时序、所有权矩阵、实际新旧边界、异常链路、证据等级和并行修改同步规则；任何并行工作必须先阅读该文档和 master/checkpoint/iteration。
- `(next exact)` 不改算法，先列出正式 modular-only 必须隔离的 legacy symbols/callers，定义旧运动策略只作为 domain-neutral adapter 的边界；随后做一次受控实机事件表验证。

## 2026-10-09 并行进程最新状态复核

- `(reviewed)` 指定线程最新结果是最终审计/文档收口和 `106 passed` 离线集合，并未完成新的实机运行闭环；其 automation 已暂停，线程结论明确为“可受控实测，实机未验收”。
- `(confirmed-open)` 仍未解决/证明：modular-only 入口收口、旧页面生命周期隔离、真实 Vision/Control child stop/rebuild、真实 Qt pause、Host receipt 到游戏 P2 位移、P2 长距离越过 P1、地图滚动 handover、真实吞吐。
- `(confirmed-open)` J02 仍是 `contract_equivalent`，不是独立旧版 checkout 的完整动作序列等价；J16 仍为 partial。不能把 `106 passed` 或子进程心跳日志当作完整跟随已修复。
- `(decision)` 本轮不改代码；下一动作是先建立 modular-only ownership 清单和真实 session event table，再决定是否进入受控实机测试或继续修复。

## 2026-10-09 首批实施：J17 execution receipt FIFO spill

- `(implemented)` `FollowControlProcessHandle` now keeps a bounded FIFO spill (`_pending_executions`, 256) when the priority queue is full; execution receipts are retried on send/poll and are no longer silently returned/dropped. Overflow emits structured `execution_receipt_overflow` with generation/count/pending.
- `(boundary)` This preserves receipt message order but does not yet aggregate turn segments; each receipt remains an individual execution evidence item, so vector changes are not collapsed into `last_vector`.
- `(verified-offline)` control process + port focused checks `25 passed`, compileall passed. No game/Host/input.
- `(remaining)` J02 old movement strategy adapter not implemented; J06 fault suppression still needs epoch-scoped reset/re-enable; J07 fusion timing audit remains.
- `(next exact)` Add deterministic queue test asserting deferred execution is eventually flushed FIFO, then design J02 adapter around actual dynamic `_make_follow_runtime` configuration without copying formulas.

## 2026-10-09 J17 FIFO race correction

- `(fixed)` When a priority spill is non-empty, later execution/recovery envelopes are forced into the same spill FIFO; they cannot bypass an older receipt after a queue slot opens between flush and put. Recovery signals now share this ordering boundary.
- `(fixed)` Overflow no longer silently evicts the deque's oldest item: new overflow is rejected with `_priority_overflow=True` and structured `priority_command_overflow`; debug-level deferred logs avoid one warning per receipt.
- `(verified-offline)` Added saturation interleaving, turn/neutral receipt ordering, recovery-signal ordering tests; control-process focused suite `10 passed`, compileall/diff-check passed.
- `(remaining)` J17 still needs a higher-level fault/evidence contract when overflow occurs; J02 legacy motion adapter and J06/J07 remain open. No game/Host/input.

## 2026-10-09 J17 overflow evidence consumption

- `(implemented)` Priority spill overflow now creates an explicit `execution_gap` envelope containing generation/role/sequence; the Control process consumes it through `FollowControlRuntime.signal_execution_gap()` and raises that role's uncertainty/source to `execution_gap` without stopping the session.
- `(boundary)` This is an evidence-gap signal, not fabricated displacement and not a stop/recovery command. The existing per-receipt FIFO remains ordered; overflow state is visible to Control.
- `(verified-offline)` Control process focused suite `10 passed`, compileall passed. No Host/game/input.
- `(remaining)` J02 old motion adapter, J06 epoch-scoped fault recovery and J07 timestamp fusion remain open.

## 2026-10-09 J02 legacy motion adapter

- `(implemented)` Added `LegacyDynamicFollowRouteController` in `follow_engine/control/route_controller.py`. It calls existing `PathFinder`, `VectorPathTracker` and `LocalMotionController`; no movement formula was copied into the adapter.
- `(config)` Concrete page composition now injects the adapter with dynamic-follow baseline: arrival 12, resume 20 (held as contract), speed 80, downsample 8, local lookahead 24, prediction horizon 0.25. Target refresh replans after 16 native units.
- `(integration)` `follow_engine_page_composition.py` now uses this adapter instead of modular fixed-magnitude `MapAwareRouteController`, so fused position/target are the only new inputs to the old motion stack.
- `(verified-offline)` control/runtime/page-composition focused checks `26 passed`; compileall passed. No replay equivalence matrix yet, no game/Host/input.
- `(remaining)` Need add old/new action-sequence replay tests for hold, leader movement, turn/door, role swap; review J06/J07 before claiming J02 closed.

## 2026-10-09 J17/J02 evidence batch

- `(fixed)` `signal_execution_gap()` rejects unknown roles, missing state and sequence < 1 with an explicit diagnostic; invalid evidence cannot alter fusion state.
- `(verified-offline)` J17 gap validation plus FIFO tests and J02 adapter contract tests `13 passed`; compileall/diff-check pending final batch.
- `(evidence-limit)` J02 tests prove adapter calls legacy components and preserves dynamic hold/80ms bounded output, but do not yet replay old `a3070ea` full route/local steering matrix for doors, turns or role swap.
- `(open)` J06 still uses first-fault suppression path requiring epoch/current-worker reset review; J07 captured-at fusion and duplicate execution integration still require focused timing cases.

## 2026-10-09 J02/J06/J07 evidence follow-up

- `(verified-offline)` Added receipt duplicate/wrong-generation test; stale or duplicate execution cannot double-integrate. Combined J17/J02 focused batch `14 passed`, compileall passed.
- `(verified-source)` Control already gates visual frames by generation/sequence and exact captured frame slot; `record_execution` gates generation and monotonic sequence. This covers duplicate receipt and stale generation boundaries.
- `(open-blocker)` J06 suppression still keys from persistent `_first_fault` text and `_rebuild_fault_signatures`; no explicit repair_pending clear on a fresh observation was added in this batch. J07 full delayed captured-at replay remains unproven.
- `(evidence-limit)` J02 remains contract-level adapter evidence; complete old `a3070ea` route/local action replay for doors/turns/role swap is not yet available.

## 2026-10-09 J06/J02 focused batch

- `(fixed)` rebuild suppression key now includes stale worker identity, session epoch, generation and fault signature; a valid Vision observation marks that worker ready, clears its reported fault/signatures, and permits a later repair attempt.
- `(verified-offline)` Added executable dynamic-follow fixture matrix for hold, leader movement, turn, door/role-swap inputs and per-role independence; adapter tests `3 passed`, combined focused control/port/adapter `33 passed`, compileall passed.
- `(evidence-limit)` Matrix is a contract fixture, not an import of a separate `a3070ea` checkout; it proves adapter composition and per-role determinism, not byte-for-byte old runtime equivalence. J07 delayed captured-at replay and first-new-frame local ROI recovery remain open.

## 2026-10-09 03:44 fault boundary and first repair

- `(confirmed)` 最新会话首帧 accepted、legacy vision 正常；`03:44:21.744` Vision 子进程因 `VisualObservation` 合约拒绝 `wall_quality > 1` 退出。raw OpenCV phase-correlation response 被 wall adapter 原样导出。
- `(fixed-offline)` `vision/wall_processor.py::process_wall` 在 adapter 边界将导出 quality 归一化到 `[0,1]`，保留 accepted/rejection 由原始 displacement gate 决定；新增 raw-response 回归测试。
- `(fixed-offline)` `FollowEnginePort` 对同一 worker fault signature 的重复 rebuild 做 single-flight 抑制，避免确定性 contract fault 无限重建、持续 neutralize 和覆盖首个 traceback；session 不因该 fault 自动释放。
- `(observability)` Control child 每 30 tick 记录 role、recovery、vector、duration、neutral，补齐 P2 overshoot 所需的逐阶段证据。
- `(verified)` focused vision/port/control tests `32 passed`；compileall 通过。尚未启动游戏、读取内存、连接 Host 或发送输入。
- `(remaining)` P2 越过 P1 仍需对照 `a3070ea` 的 LocalMotionController/VectorPathTracker、速度/脉冲/到达策略；不能把本次 Vision fault 当作唯一 overshoot 根因。
- `(confirmed-diff)` 旧版 `runtime.py` 使用 `LocalMotionController(expected_speed=80, prediction_horizon=0.22)` 与 `VectorPathTracker(arrival_radius=8)`，并有逐步减速/局部候选避障；当前 modular `MapAwareRouteController` 使用 `magnitude=0.65`, `duration_ms=80`, `arrival_radius=12`, `downsample_factor=4`, target projection radius 8，`FollowControlRuntime` 直接采用其 vector，未调用旧 `LocalMotionController`/`VectorPathTracker`。这证明重构边界已经改变了规划/输出策略，不能把 P2 overshoot 归为纯定位问题。
- `(next exact)` 将旧版规划/脉冲策略与新版定位来源解耦：保留旧 route/vector/duration/arrival 行为，只替换 position/target evidence；先写离线不变量回归，再接入模块化 Control。
- `(next exact)` 做旧版与当前 route/output/prediction 不变量对照，确认重构是否改变移动策略；再决定是否恢复旧策略适配，避免误改规划和手柄层。

## 2026-10-09 续点：重建后的坐标变换交接（已完成离线验证）

- `(confirmed/source)` 在实现前确认：`VisualObservation` 只预留 opaque `transform` 字段，processor 没有填充，port 也没有保存最新 observation；rebuild 只能继承 native position，地图滚动后的 screen/native 变换会丢失。
- `(fixed)` `DualObservationProcessor.process()` 每帧写入当前墙体校正 transform；`FollowEnginePort` 只保存当前 generation/map 有效的最新 observation；start/stop/failure 会清理 handover 状态。
- `(fixed)` `composition.make_workers()` 在重建时继承最新 native position 和 transform；replacement Vision 与 Control 的 `EncodedMarkerRoiSearch` 使用同一 transform；已有 native seed 时不复用旧 screen anchors，而由当前 transform 重新反算。legacy observation 无 transform 时回退 seed transform。
- `(verified-offline)` composition/processor/port 定向回归 `31 passed`，compileall 与 diff check 通过；未启动 PoE2、未读取内存、未连接 Host/LAN、未发送手柄输入。
- `(remaining-risk)` 仍需用户授权后的地图滚动、worker rebuild 后局部重定位和 P2 连续性实测；离线结果不能证明游戏实际消费输入。
- `(next exact)` 完成最终人工全链路文档，明确双进程所有权、周期、恢复阈值、输出代际和实机验证边界。

## 2026-10-09 人工全链路审查收口

- `(reviewed)` 已按 Vision capture/transform/association、Control visual/target/priority 队列、fusion/odometry/recovery/route、OutputScheduler/AsyncSnapshotOutput、UI lifecycle 和 worker rebuild 逐段对照源码；正式动态跟随只有 Control runtime 写 source→follower target，页面 relay 仅保留 legacy/fake 兼容路径。
- `(reviewed)` 双进程不共享可变 tracker：Vision 只产出 immutable observation/ring frame，Control 只拥有 target/prediction/recovery/route；输出 actor 是父进程唯一 Host I/O 写者，receipt 通过 priority 回 Control。每 tick local ROI 一角色、A* 一次预算，避免两个角色互相串行阻塞。
- `(reviewed)` 生命周期代际由 session epoch + generation token + rebuild cancel 保护；迟到 rebuild bundle 不 commit，旧 ring/worker/output lease 会隔离清理；heartbeat/write/rearm 与 stop 使用角色 I/O lock 二次校验。
- `(reviewed)` 仍需实机关注的量化边界只有：单次 ROI/A* 是否超过 33ms、Host receipt 到游戏实际位移的消费差、PoE2 窗口/controller ownership、地图滚动后 rebuild 连续性。它们不能靠离线测试证明。
- `(verified-offline)` 2026-10-09 最终 PoE2 专项 `600 passed in 34.62s`；compileall、diff check 通过。无真实游戏、内存、Host/LAN、手柄输入。
- `(next exact)` 用户授权后先做静止双人 6 秒闸门观察，再做短距离单方向移动；必须关联 generation、first observation、first snapshot、first output apply、receipt、StageTiming 和实际 P2 位移，发现异常先保留证据，不直接调阈值。

## 当前人工全链路审查续点（2026-10-09）

### Transform handover（2026-10-09，子任务）

- `(root-cause)` `DualObservationProcessor` 每帧会根据墙体位移更新
  `self._transform`，但返回的 `VisualObservation` 没有携带该最新变换；
  worker rebuild 因而只能回到首帧 `seed.transform`。局部 ROI search 也会继续使用
  首帧变换，导致地图滚动后 native/screen 坐标闭环不一致。
- `(fixed/offline)` observation 现在携带当前 `transform`；`FollowEnginePort`
  保存同一 generation/map 的最新 observation，并暴露只读
  `latest_visual_observation` 供 rebuild handover。composition rebuild 从该 DTO
  继承最新 native role positions 与 transform，replacement Vision 和 Control 的
  `EncodedMarkerRoiSearch` 使用同一变换；handover 时不复用旧 screen anchors，改由
  native seed + 最新变换重新反算。
- `(verified)` transform processor/engine/rebuild 链路专项回归通过；未启动游戏、
  读取内存、连接 Host/LAN 或发送真实手柄输入。
- `(next exact)` 父任务继续做完整文档同步与离线专项回归；实机仍需授权后验证
  地图滚动/worker rebuild 时 P2 坐标连续性。

### 2026-10-09 全链路审查续点：P2 滞后的两个结构性根因

- `(source-confirmed/P1)` 当前动态跟随目标的唯一实时转发点仍在父进程 `FollowEnginePort.poll()`：Vision 事件先跨进程到父侧，父侧再调用 `_forward_live_target_observation()` 写入 Control 的 target queue。Control 进程虽然在同一轮接收视觉，但没有在 `apply_visual()` 内根据 source/target policy 直接更新 follower target。UI timer 延迟、输出健康检查或 worker watchdog 都会把 leader target 推迟至少一个 poll 周期，队列积压时会更久；这解释了“P1 已经跑远，P2 过一会才开始追”的时序差异。
- `(source-confirmed/P1)` `FollowControlRuntime.tick()` 在单个 Control worker 内对每个失配 role 同步调用 `_run_local_recovery()`，随后对需要重规划的 role 同步调用 `RouteController.plan()`/A*。双人同时失配时两个 ROI 串行；目标连续变化或位置偏离缓存阈值时 A* 也会挤占同一个 tick。虽然 cadence 已改为 start-to-start，但处理时间超过周期时仍会造成 target 消费、snapshot 和 output receipt 延迟。
- `(comparison)` 旧链路的目标更新与移动 tick 在同一页面运行时同步发生；新链路把视觉、控制、输出拆成进程后，实时 target 仍绕回 UI relay，反而恢复了跨边界等待。目标策略应作为通用 observation-to-target policy 下沉到 Control runtime，父侧 relay 仅保留为兼容兜底，不能成为动态跟随的主路径。
- `(boundary)` 以上是源码调用链推导，不是 10 月 9 日实机消费证据；当前没有启动游戏、读取内存、连接 Host/LAN 或发送真实输入。真实 P2 位移仍需后续授权实测。
- `(next exact)` 增加 Control runtime 的 source/target policy，使一帧视觉在 Control 内直接更新目标；增加每个 tick 的恢复/规划预算与结构化超预算标记，避免双人恢复串行阻塞。修改后补齐 composition/port/runtime 文档和离线回归。

### 2026-10-09 17:21 之后人工全链路复核：新增性能根因

- `(source-confirmed)` 当前 `vision_process_entry()` 使用 start-to-start cadence；`control_process_entry()` 在每次 `runtime.tick()` 结束后仍无条件 `stop_event.wait(interval_ms)`。因此 control 实际周期为 `tick_cost + interval_ms`，不是配置的 interval。若局部 ROI/A*/恢复耗时 20–70ms，P2 的 target、输出和回执会额外滞后一个完整周期。
- `(source-confirmed)` `FollowControlRuntime.tick()` 在 control worker 内同步执行 `_run_local_recovery()`，每个缺失角色一次；双人同时失配时会串行执行两次 ROI 搜索，阻塞同一进程的预测、target 消费和输出意图生成。该路径没有改变 session 语义，但会造成“视觉异常后 P2 过一会才动”。
- `(source-confirmed)` `MapAwareRouteController.plan()` 在 target 刷新或路线偏离时可能同步调用 A*；它与上述 recovery 共用 control tick，当前没有预算/耗时门。必须记录并限制单 tick 的计算预算，不能让恢复或规划无限挤占控制周期。
- `(documentation)` `docs/POE2_FOLLOW_RUNTIME_CHAIN_CURRENT.md` 第 8 步仍写“按全局 sequence 排序”，与当前独立 `visual/target/priority` 通道实现不一致；需要在本轮同步更正。
- `(boundary)` 当前仍只有离线源码和聚焦验证，没有 10 月 9 日实机长跑证据；本轮修复只能证明时序/预算契约，不能宣称 PoE2 实际消费手柄后 P2 延迟已验收。
- `(next exact)` 先把 control cadence 改成 start-to-start，并新增回归证明 tick 处理耗时不会再叠加完整 interval；随后把恢复/规划耗时纳入结构化 timing 和预算审查，再决定是否需要异步恢复线程。

### 第二轮复核前置结论（2026-10-09）

- `(audit-required)` 上一轮把“速度校准、独立 target 队列、输出自动重试”写成已修复，但当前源码复核发现三处实现边界仍不成立：target 可能被同一轮旧 fused snapshot 覆盖；独立队列仍共享全局 sequence gate；输出恢复没有完整的 session epoch/stop 竞态保护。此处以源码为准，旧的“已完成”表述降级为待复核。
- `(audit-required)` 速度校准当前在视觉接受前更新，且候选速度又乘一次摇杆 magnitude，存在把被拒绝帧和单位混用写入模型的风险；这可能放大视觉创新门并延迟漂移发现。下一步必须只用可信视觉、实际执行回执时长和统一 native 单位校准。
- `(audit-required)` 当前重构后的“预测通道”和“视觉纠偏通道”尚未证明互相独立：engine/UI 仍可能在同一 poll 中先推送新 raw target，再用旧 snapshot target 覆盖；control 还可能无界排空队列导致 tick 饥饿。需先核对调用顺序、队列契约和生命周期，再修改。
- `(boundary)` 本轮只做源码、离线数据和聚焦验证，不启动游戏、不读取内存、不连接 Host/LAN、不发送真实输入。所有“实时延迟/游戏实际消费”结论必须标记为未验证。
- `(next exact)` 先用 CodeGraph 追踪 `engine.poll → target/visual/receipt → control_process → runtime.tick → output actor`，再逐个修复 target 单写者、队列 coalesce/序号、可信速度校准、输出恢复竞态；每个材料结论立即更新本断点和 ITERATION_LOG。
- `(fixed/verified-offline)` 上述五项已完成：target 单写者与 page relay ownership、通道独立序号/按角色 coalesce、accepted-only 速度校准与 miss 计数、watchdog 独立事件、output restart epoch lock；聚焦 47+23 项通过。另补充 rebuild 时把最近 `FusionSnapshot.roles[*].position_native` 作为新的 Vision seed，避免 worker 重建回到地图首帧位置。
- `(remaining-audit)` 仍需人工复核局部 ROI 在 transform/shape 变化时的坐标闭环，以及 rebuild 时最新 transform 本身的 handover；当前只 handover native role seed，不能宣称完整 transform 继承。
- `(fixed/verified-offline)` 复核双人 recovery 分支后，memory/global 成功状态已按 role 记录；一个角色重锚成功不会把另一个角色错误标成 recovered。
- `(verified)` 最终聚焦验证 72 passed / 11.92s，compileall、diff check 通过；无全仓回归、无真实 Host/内存/游戏输入。

- `(restored)` 本轮从 2026-10-07 17:21 附近的任务记录、断点文档和当前工作树恢复；未把聊天摘要当作唯一依据。历史 `20:55` 实机会话属于旧代际，不能当作当前代码的实机验证，但它确认了 `6s arm gate`、旧 queue dispose 和首个 Host report 之间的时序差异。
- `(confirmed/current source)` 当前 VisionProcess 已改为 start-to-start cadence；ControlProcess 已批量消费当前队列，target 满队列时保留 latest-only pending。两项修复降低了旧 backlog 根因，但它们没有解决速度模型和 target 传播时序。
- `(new root cause)` `FollowControlRuntime.tick()` 仍用 `route_controller.magnitude * 100` 作为所有角色的固定位移速度；已有 `tracking/velocity_calibrator.py` 没有接入新控制运行时。视觉丢失或实际手柄速度低于模型时，P2 预测位置会先跑到 P1 目标附近，之后创新门拒绝真实视觉，漂移会继续累积。
- `(new timing boundary)` `Poe2FollowEnginePageAdapter.poll()` 先调用 `engine.poll()` 取得控制快照，再用快照中的 leader 位置调用 `update_target()`；因此 leader 最新观测至少晚一个 UI poll 传播。`_forward_execution_receipts()` 也只在 `FollowEnginePort.poll()` 内转发，UI 抖动时 target/receipt 会一起堆积在 priority channel。
- `(repair boundary)` 本轮修复只增加通用跟踪能力：每个受控角色维护闭环速度估计；可信视觉接受前后更新速度模型并扩大与视觉年龄相称的创新门；engine 在把控制快照交给 output 前先传播本轮最新 leader observation；target 使用独立 latest-only 通道/批次语义，不驱逐 stop、recovery 或 receipt。不会改变人物半径、地图膨胀或首帧算法。
- `(verification boundary)` 新增离线回归覆盖：低实际速度不再因固定预测造成连续视觉拒绝；leader observation 与 follower target 在同一 poll 进入控制批次；priority receipt burst 不会让最新 target 等待旧回执；完整 follow focused suite、compileall 和 diff check。仍不连接真实 Host、内存、LAN 或发送真实输入。
- `(next exact)` 修复完成后更新 `CODEBASE.md`、`ITERATION_LOG.md` 和三份当前链路文档；最终报告明确离线证据与尚未由真实游戏消费验证的边界。

### 2026-10-08 follow lag lifecycle hardening completed

- `(fixed)` `OutputScheduler` now uses a session epoch and per-role I/O locks; force stop claims every role before external I/O, stale apply/heartbeat/rearm cannot write, and stale writes do not emit execution receipts. `prime_neutral()` establishes a neutral Host lease during the configured 6s focus handoff without recording movement.
- `(fixed)` `GlobalRecoveryBackend` now checks map instance as well as generation and uses the control tick time domain for bounded exponential failure cooldown. Unknown `program.heartbeat` is probed once and then replaced by `program.state` heartbeat.
- `(fixed)` `FollowEnginePort`/composition rebuild now uses detached `RebuildBundle` atomic commit/retire. Stop-timeout futures are retained as `retiring`; a same-port start waits for them and refuses handle reuse if the bounded wait expires.
- `(verified)` `tests/poe2_live_terrain`: 586 passed / 29.74s; extended PoE2/bootstrap/page/program suite `711 passed / 79.09s`. Output/snapshot/recovery/program focused: 34 passed. Compileall and diff check passed. CODEBASE and ITERATION_LOG were synchronized.
- `(boundary)` No live game, memory, Host, LAN, or real input was used. The available 20:55 log predates this repair generation. The 6s handoff gate remains intentional; only post-gate Host startup latency was removed offline.
- `(next exact)` User restarts the workbench and performs R1: static two-player session, then short movement. Correlate `generation`, `first_vision_observation`, `first_control_snapshot`, `first_output_apply`, `execution receipt`, `program_output.state_heartbeat`, worker stall/rebuild, and actual in-game response before further parameter changes.

## 当前有效状态：2026-10-08 启动挂起修复完成（优先续读）

### 2026-10-08 follow lag investigation (current)

- `(evidence)` 最新可用实机会话 `20:55:19.136–20:58:29.495` 仍来自修复前代际：模块化接管在 `20:55:27.748`，组合启动完成 `20:55:28.524`，首次 `Vision queue closed` `20:55:35.559`，首次 controller=2 Host report `20:55:36.940`。旧日志随后每约 33–50ms 轮询已关闭 queue，并持续出现 `program.heartbeat invalid_argument: Unknown program command`。
- `(root cause confirmed)` P2 延迟由三项叠加：旧 stop/dispose 与新 composition 交错导致视觉队列提前关闭；输出 adapter 的 6s arm gate 从 engine start 开始但 gate 内不创建/启动 role output，gate 后还要付出 Host session 建立时间；Host 不支持 `program.heartbeat` 导致 heartbeat/rearm 错误风暴。旧日志不能证明当前修复后的实机会话，下一次测试需按 generation/阶段日志关联。
- `(current repair boundary)` 已完成 queue closed 分类、模块化 start 延迟到旧 stop 完成、state heartbeat fallback、阶段耗时日志和离线回归；本轮继续处理审查发现的 rebuild future 与 stop/restart 竞态、OutputScheduler 停止/心跳竞态，并补齐“arm gate 内预置中立 lease”以消除 gate 后额外启动延迟。
- `(safety)` 本轮不启动游戏、不读取实时内存、不连接真实 Host、不发送真实输入；验证只用 fake output、离线 spawn、单元/组合回归。
- `(next exact)` 等待 scheduler/engine 两组隔离修复完成后，执行 follow 全量回归、Codebase SYNC，再由用户重启工作台做一次短距离 R1 实测；重点记录 `first_output_apply`、`arm_gate_remaining_ms`、`first execution receipt`、worker generation/rebuild 和 Host state heartbeat。

### 2026-10-08 repair continuation (R2/R3 partial)

- `(partial)` 已新增 `execution_feedback.py`、`control/async_output.py`，并让 `SnapshotOutputAdapter` 记录成功写入回执；这些改动尚未接入 control runtime、engine port 或实际页面组合，当前不能宣称执行回执已经驱动位置预测。
- `(evidence)` R1 生命周期修复仍由 13 项聚焦回归覆盖；本轮尚未运行 R2/R3 测试。下一步先把回执命令贯通 control process → `FollowEnginePort.poll` → runtime，再把实际页面输出包装为 latest-only 异步 actor。
- `(boundary)` 保持无真实游戏/Host/LAN/内存/输入；只使用 fake output、离线回放和单元/组合测试。持续跟随不能因组件超时终止，组件恢复只替换故障代际。
- `(next exact)` 完成 R3 的 receipt generation/sequence 校验和 odometry overlap 积分；修复后运行 `test_follow_execution_feedback.py` 及 control/port/output 相关回归，再进入 R4。

### 2026-10-08 repair continuation (R2–R5 completed offline)

- `(R3 fixed)` `ExecutionReceipt` 已从成功 output write 贯通至 control runtime；generation/全局 sequence/role 过滤，按 accepted lease 与未消费游标的时间重叠积分，视觉/recovery anchor 会推进游标，zero lease 截断旧脉冲。arm gate、write failure、无回执均不推进位置。
- `(R2 fixed)` concrete PoE2 page 使用 `AsyncSnapshotOutput`；writer actor 独占同步 adapter，watchdog 可取消慢 I/O。OutputScheduler 改为每角色 I/O lock，heartbeat/write/rearm 不再持有全局锁，UI diagnostics/stop 不会被其它角色慢请求拖住。
- `(R4 fixed)` FollowEnginePort 增加 spawned/stalled 诊断（startup 10s、running 2s）；composition 提供 rebuild factory，停滞时 neutralize、停止旧 worker、替换 ring/handles、重放目标并继续同一 session。ProcessSupervisor start/restart 异常回滚 handle/token。
- `(R5 fixed)` concrete modular page 的 process start/stop 通过单线程 lifecycle executor；Qt timer 仅轮询和更新状态，stale completion 由 serial 丢弃。离线 fake page 仍走同步契约。
- `(verified)` follow suite 562 passed / 20.18s；page file 107 passed、startup 6 passed、page/composition/port/supervisor/output/receipt 聚焦 125 passed；compileall 通过；lifecycle audit probe 七场景均在 watchdog 内退出，arm-delay position 保持 `(0,0)`。真实 root-entry 离线组合 p1/p2 两方向分别 startup 764.4ms/836.6ms、各 5 个完整 snapshot。
- `(boundary)` 以上只是假输出、离线进程和回放；未连接真实 Host、未读取 PoE2 内存、未发送真实输入。下一步是 CODEBASE/文档同步后再做实际测试，不得把离线通过当作游戏消费输入已验收。
- `(next exact)` 用户可以重启工作台做一次实际位置测试；先观察 `follow_engine.modular_start...`、`execution receipt`、worker stall/rebuild 和 output diagnostics，再决定是否调参数。

### 当前执行：同类生命周期隐患修复（优先于下方历史审查）

- `(authorized)` 用户要求开始修复审查报告中的问题；按报告分批完成，不重跑已确认的旧 blocked 根因探针。
- `(plan)` R1 bounded ring lock + 构造/未启动 process 清理；R2 output 逐资源回收/异步 I/O；R3 generation/sequence 执行反馈驱动 odometry；R4 ready/stall 与整代 worker/ring 重建；R5 UI 非阻塞 start/stop；R6 故障回归、实际 root-entry 离线组合、文档同步。
- `(boundary)` 保留连续跟随、角色映射和6s arm gate；无任务硬时间限制。timeout 仅限制底层等待/恢复。禁止真实输入、Host/LAN/内存实验；不覆盖用户工作树，不做 git reset。
- `(next exact)` 阅读所需技能、CodeGraph 核对受影响接口，逐批写失败用例后实现并更新断点。
- `(R1 verified)` 四个新增失败回归先 4 failed，再实现 bounded/poisoned ring、构造 ExitStack、未启动 Process pid guard 与逐 output stop/close；相关 ring/composition/repeated Windows lifecycle 共13 passed。新增 worker_lifecycle 为两个handle共用，owner dispose queues；旧定位参数未改。
- `(next exact R2/R3)` live output 改为 latest-only 后台执行边界（离线同步adapter兼容保留）；添加 execution receipt 的 generation/sequence/实际向量/提交时间/有效持续时间，用于控制积分。UI 不再等待 Host heartbeat/diagnostics/start/write/stop。

### 当前追加任务：同类启动/生命周期隐患审查

- `(requested)` 用户要求再检查类似错误是否存在于其他地方。本轮检查入口导入副作用、multiprocessing spawn/队列/停止、失败资源回收、Qt 回调阻塞和反复恢复风险。
- `(boundary)` 先只读源码和离线聚焦检查，不修改运行算法、不启动游戏/Host/LAN、不发送输入；已修复根因不重新复现 blocked 探针。
- `(next)` CodeGraph 定位所有进程启动/退出入口和 follow lifecycle 调用路径，按已确认缺陷/潜在风险/已保护三类记录证据。
- `(audit finding)` follow 的 ring `publish/read/rebind_session` 使用无超时 multiprocessing Lock；worker stop 可以 terminate。若进程持锁时被终止，后续 rebind/read 可永久等待，需离线故障注入确认。另 composition 在 ring 创建后再校验 memory factory，构造失败没有 finally 回收；worker start 失败后 stop 对未启动 Process 直接 join，可能抛二次 AssertionError。
- `(audit boundary)` 用户本轮请求检查，不修改运行源码；下一步为上述边界做可退出的离线检查，并核对其他入口/torchlight 的同类路径。Serena 项目已激活，initial_instructions 工具仍不可用。
- `(audit scope update)` 新发现 OutputScheduler 在 RLock 内调用 heartbeat/write/rearm/stop/diagnostics；SnapshotOutputAdapter.stop 没有 finally，scheduler.stop 抛错可跳过 close 全部 output。新增只用于本轮检查的 `tools/debug/follow_lifecycle_audit_probe.py`，所有输出 fake，外层每个子用例 15s watchdog，清理诊断资源，不改运行代码。
- `(audit reproduced)` 六个故障注入均正常退出：持锁 child terminate 后锁 200ms 内不可获取；非法 memory 参数构造失败仍留 1 个 open ring；不可 pickle factory start 报错后 stop 再报 `can only join a started process` 且 process 引用仍在；第一个 output.stop 抛错导致第二个未 stop、两个均未 close；fake heartbeat 阻塞期间 diagnostics 等待 309.92ms；supervisor.start 部分失败仍保留 handle/token，状态却为 stopped。均为离线可复现缺陷，不代表已经发生于最新实机。
- `(next audit)` 检查实际组合是否使用 supervisor、worker 是否有 ready/stall 检测、其他入口 guard，再跑相关现有回归，输出分优先级审查文档。运行代码保持不变。
- `(audit reproduced critical)` 补充第七项：6s arm gate 下，3s 模拟视觉缺帧时 output_factory 创建数=0，但 control 的 command_prediction 已到 (101.4, 0)，剩余 gate=3000ms。控制按计划而非执行确认推进，属于真实代码边界矛盾；未证明发生在最新实机截图。
- `(audit verified)` 现有 bootstrap/port/supervisor/ring/Windows lifecycle/vision/control/output/page-startup/torchlight-service/UAC 专项 45 passed / 23.04s，日志隔离到 `data/diagnostics/20261008_follow_lifecycle_audit`。这些测试未覆盖新故障注入，不能证明无其他隐患。实际 composition 直接装配 handles，无 ProcessSupervisor；port 仅报告 exit，中立输出但无自动重建，活着却无新结果也未做 stall deadline。
- `(audit complete)` 审查报告已写入 `docs/POE2_FOLLOW_LIFECYCLE_AUDIT_20261008.md`；新增诊断脚本编译、文档 diff check 通过。共七项离线故障注入正常退出，其他 ready/stall/UI 同步等待为源码确认风险，未做实机归因。本轮运行源码未改。下一步按报告先处理锁中毒和完整资源回收，再执行反馈、输出异步、worker ready/stall/rebuild；需用户后续修复指令，不重复已完成调查。

- `(confirmed/fixed)` 根因不是已证明的业务恢复循环，而是 Windows spawn 重导入根 `main.py` 后执行 bootstrap 的 GUI 初始化，误命中父 GUI 的单实例 mutex 并退出；父 Qt 线程阻塞在 `Process.start → reduction.dump` 发送大地图 payload。实机 14:31:59 takeover、14:32:00 单实例拒绝、14:32:45 AppHangB1 与离线复现吻合。
- `(implemented)` `bootstrap/main.py` 导入仅定义；日志、DPI、UAC、mutex、Qt 导入都移到显式 `main() -> int`，首步 freeze_support；根 main 传递退出码。GUI 锁保留，runtime.log 追加并记录 PID，不再截断旧证据。
- `(implemented)` `FollowEnginePort.start` 增加 control/vision/output 分阶段日志和耗时；部分启动失败也清理，清理异常不遮蔽原错。页面失败回收 owned composition/shared ring 并允许重建。模块化角色选择修复为 p1_leads 控制 P2、p2_leads 控制 P1。
- `(verified)` 相关全套 `python -m pytest -q tests/poe2_live_terrain tests/test_bootstrap_spawn.py tests/test_poe2_capture_test_page.py -k 'not no_extra_filter'`：667 passed / 132.22s；补充初始化顺序/UAC 回归后，bootstrap + port + page_startup 专项：21 passed / 10.02s。两次测试重叠，不能相加成独立测试总数。目标 compileall 与 diff check 通过。
- `(verified)` 实际根入口离线组合：父持真实 GUI mutex，2093×2784 地图，真实 Windows spawn，fake capture/recording-only output；p1 leader 启动 1046.1ms，p2 leader 启动 1012.6ms，均取得 ≥5 个完整双角色 snapshot，非零输出仅属于 follower，退出回收成功。记录目录 `data/diagnostics/20261008_follow_bootstrap_repair`。
- `(boundary)` 本轮未启动游戏、未读取真实内存、未连接 Host/LAN、未发送真实输入。尚不能宣称真实游戏消费输入、漂移与长跑稳定性已验收。Process.start 仍同步序列化，此样本约 1s；未实现通用可取消启动超时。
- `(next exact)` 用户重启工作台后执行 `docs/POE2_FOLLOW_ENGINE_ACCEPTANCE.md` 的 R1，保留原有 6s 输入等待；检查 start_stage/control/vision/output、首个完整 snapshot、Host 输出和真实角色响应。没有新实机证据之前，不重复旧 synthetic blocked 探针、不重调定位阈值。

## 以下为历史调查/开发记录（保留证据，不代表当前待办）

历史条目中的“未修复”“下一步调查”“回归进行中”已被上方当前有效状态覆盖；用于追溯当时决策，不得据此重启已完成任务。

### 历史调查：2026-10-08 14:31 启动挂起

- `(verified root-entry integration)` 新增 `tools/debug/follow_root_entry_probe.py`：actual main.py 作为子进程准备入口、持有 GUI mutex、2093×2784 地图、静态测试小地图、recording-only 输出。p1/p2 两种 leader 都达到 ≥5 个双角色控制快照且仅 follower 非零输出；Windows 子进程正常停止并回收 ring，bootstrap 实机入口相关 5 passed。探针首轮断言误把空暖机快照当完整快照、误用不存在 sequence 字段，已修正测试为等待完整 roles 并用 created_at_ms 区分快照；不是运行源码新故障。
- `(fixed current)` 页面 adapter.start 抛错时原来保留 owned composition/ring 且 inactive stop 不回收，已显式 adapter/owner 清理并清空引用，允许下一次重建；失败回归先失败后通过。当前 11 项页组合/启动/入口专项已通过，全目录回归进行中。

- `(confirmed/fixed)` 新增回归确认模块化 p1_leads/p2_leads 把受控角色反选，已修正为 leader 手动、follower 程序；target roles 与 output roles 五种模式一致。FollowEnginePort.start 部分组件失败原来未 stop，清理失败可打断逆序回收；已纳入 attempted component 逆序清理，保留原始异常并清空 token/state。控制/视觉/输出每阶段 begin/completed 和总耗时已埋点，日志继承页面 terrain logger。
- `(verified)` bootstrap + port + 页面角色选择专项 15 passed；下一步增加实际 root-entry 带大地图的完整 spawn 组合验证，检查首个视觉/控制 snapshot 与 fake follower 输出，再完整 PoE2 回归。Serena Python LS 初始化失败，本轮用 CodeGraph 源码/影响查询继续执行。

- `(fixed/verified current)` bootstrap 所有 GUI 初始化及 Qt imports 已移入显式 `main()`，首步 freeze_support；根入口传递 main 的退出码。runtime.log 追加且含 pid、重复配置幂等。新增 import-purity 回归先失败后通过；真实 root main.py 的 Windows spawn + 6MiB payload + 父持有实际 GUI mutex 测试通过（3 passed），无游戏/Host/输入。
- `(next current)` 审查 FollowEnginePort.start 的阶段日志、部分启动异常与清理异常是否遮蔽原错，然后跑启动、页面组合和 PoE2 回归；最终覆盖同步 CODEBASE 与验收状态。

- `(started repair)` 用户已明确要求开始修复。本轮执行：导入无副作用 → GUI 启动时显式初始化且保护日志 → 实际根入口 Windows spawn 大地图参数回归 → 启动阶段诊断/回滚核对；不接真实游戏输入。当前根因复现已有，无需重跑 synthetic blocked 模式。
- `(next)` 先读 bootstrap 与启动调用者，写 import-purity 失败回归，再修复入口并跑真实 root-entry spawn。每阶段追加此处状态。

- `(confirmed root cause)` `bootstrap/main.py` 在 import 阶段执行 configure_runtime_output、提权、单实例检查（115–116、252–267）；Windows spawn 重导入根 main.py，继而导入 bootstrap，命中父 GUI 已持有的 mutex，sys.exit(0)，尚未读入 Process payload。与 14:32:00 runtime.log 重写+单实例拒绝完全吻合。
- `(reproduced)` `tools/debug/spawn_import_exit_probe.py` 模拟同一 import-time exit，Windows Python 3.12、6MiB payload 下父线程卡在 reduction.dump → popen_spawn_win32.Popen.__init__ → Process.start；2s faulthandler 栈确认，6s watchdog 终止诊断父进程。clean 对照同 payload 正常 target_reached、exit=0。无游戏/Host/输入。
- `(correction)` 本次不是已证实的“自动重启循环”，而是 UI 主线程同步 Process.start 阻塞。旧 capture 延退仍需单独 lifecycle 检查，但不是当前证据支持的第一根因。548 项离线测试不经过实际工作台 bootstrap，不能证明真实入口 spawn 安全。
- `(current status)` 根因调查完成，运行源码未修复；只新增离线复现脚本与文档。本轮用户请求排查，未扩大为重构或启动实机。
- `(next exact fix)` 将日志/FreeConsole/DPI/UAC/mutex/window 检查和 Qt UI imports 移入显式 main 启动路径；真正入口在需要时先 freeze_support；新增 import-purity + 实际入口 Windows spawn 大 payload 回归，保持单实例锁保护主 GUI，不允许简单删除锁。另将 duplicate instance 日志与主日志隔离/避免截断；UI 同步 startup 需异步/有界 stage diagnostics 与 ready/failure 结果，作为独立实现边界验证。

- `(verified)` 最新真实业务日志止于 14:31:59.174；此前首帧 accepted=0.9099，实时 128 帧正常。没有 modular_started，也没有后续 traceback，不得将凌晨 pytest 写入同一日志的 synthetic errors 当作实机错误。
- `(verified)` Windows Application Hang 1002 / WER 1001 于 14:32:45 记录 pythonw.exe AppHangB1；目前证据是主窗口无响应后关闭，不是已证实 native crash。
- `(verified)` runtime.log 被重写为 14:32:00 新 session，仅有 `Another auto_modules instance is already running; exiting this instance.`；Host 尾部在 14:31:17，没有跟随启动后的输入记录。
- `(hypothesis)` 子进程启动误进入应用入口/单实例锁，可能阻断父进程 spawn 序列化；旧 worker stop_deferred 只是伴随日志，尚未证明 capture 竞争。
- `(boundary)` 本轮尚未修改运行代码、未启动游戏/Host/实时输入。Serena 项目已激活；initial_instructions 工具不可用。
- `(next)` 核对 bootstrap/main、实际启动器、multiprocessing executable 与 Windows spawn；建立无游戏、无输入的最小复现。确认前不调视觉参数或重写 worker。

## 本轮规划任务（2026-10-07）

- `(requested)` 用户要求先冻结当前代码提交，再制定双通道/多进程跟随的完整实施方案，并拆成可独立验收的小目标。
- `(confirmed)` 当前基线提交为 `ea72667`；设计提交为 `2eaeb38`。工作树中的 `data/events/events.json` 和 `data/poe2_live_terrain_test/occlusion_diagnostics/` 属于运行时用户数据，不加入本轮规划提交。
- `(designed)` 详细执行计划已写入 `docs/plans/2026-10-07-poe2-follow-engine-execution-plan.md`，覆盖 M0–M8、文件边界、跨进程契约、测试命令、性能门槛、回滚点和实机验收。
- `(decision)` 本轮只完成规划和基线冻结，不开始新架构实现；用户确认后从 M0.1/M0.2 回放夹具开始。
- `(next)` 先建立离线回放 manifest 与不可发送真实输入的 harness；随后实现 M1 纯逻辑契约，再迁移 VisionProcess 和 FollowControlProcess。

## 开发启动（2026-10-07）

- `(started)` 用户已授权按执行计划开始开发，当前从 M0 离线回放夹具和 M1 纯逻辑契约开始。
- `(boundary)` 本轮首先只新增无副作用 DTO、代际校验、预测/融合和恢复策略；不启动真实游戏、不读取实时内存、不发送手柄输入。
- `(next)` 先提交 M0 回放 manifest 与离线 harness；随后提交 M1.1–M1.4，每一组都有独立测试和提交。

## 最新测试异常调查（进行中）

- 用户请求只读定位最新异常日志与图片，先分析原因，不改运行代码、不发送输入。
- 最新日志截至 14:14:01，末段出现 `Program session expired or was revoked`，重复发生于 foreground 中立写入；需要追溯第一次异常而非把失焦后的重复错误当首因。
- 下一步：核对最新 session 首次错误、重定位/视觉证据以及图片时间戳，记录完整时间线。

### 只读结论（2026-10-07 14:xx 会话）

- `(confirmed)` 最新异常的首个实际错误是 `14:13:40.199` 的 `VirtualGamepadError: invalid_argument: Program session expired or was revoked. Explicit start is required.`；之后每约 0.1–0.3 秒在 foreground 中立帧路径重复失败，属于同一失效 session 的连锁噪声，不是多个独立根因。
- `(confirmed)` 此前 worker 已长时间处于 `recovery_required / markers_missing`：P2（DexFourb）最后可信视觉时间 `1791353608746`，到 `14:13:40` 视觉年龄约 11.5 秒；P1 仍可见。六张 evidence raw 显示 P1/P2 标记仍在附近/可见，但候选配对的相对距离从预测约 84 native px 与观测约 74 px 偏离，P2 候选持续无法通过身份/几何关联，随后进入恢复状态。
- `(confirmed)` 视觉恢复期间 `dual_motion.worker_stop_deferred` 与 `restart_deferred` 表明旧 native capture worker 尚未退出；同时跟随 tick 出现 `runtime_tick_ms=472–926ms`、总 tick `486–1073ms`，说明恢复/路径计算阻塞了 UI 控制节拍。
- `(confirmed)` 首帧恢复本身耗时显著：`memory_ms=2796–6267ms`，`registration_ms` 约 10s，`total_ms=5.4–16.5s`。因此本次表现是“P2 标记失配→恢复升级→运行时/worker 拥塞→Host session 过期后中立写入也失败”，不是单纯截图颜色瞬时丢失。
- `(boundary)` 最新 evidence 图片已保存于 `data/poe2_live_terrain_test/occlusion_diagnostics/1791353605141-...` 至 `1791353611275-...`，当前未修改代码；下一步需用户确认是否先修复“过期 session 中立帧重建”和“恢复期间 runtime tick 阻塞”两条边界。

## 当前基线

- 代码已明确回退到 Git `a3070ea checkpoint: stabilize poe2 experimental follow runtime`。
- 已撤销 `a618207`、`333d1d8`、`0e887e9` 三批后续优化，保留回退前运行时日志和 evidence 文件。
- 本断点之后只做只读审查，未经新的根因证据和回归测试，不继续修改首帧、双人 worker 或采样参数。

## 已确认的负面回归

- 连通域候选提取改动使首帧候选数量增多，放大双人首帧排列和形状搜索。
- 首帧候选上限调整与实时运动候选逻辑混杂，导致首帧耗时异常；实机日志出现单次候选结果间隔约 70 秒。
- 用户反馈双人实时定位点击后崩溃/退出；现有日志未捕获稳定 Python traceback，需对照正式页面的线程、帧槽和生命周期边界继续审查。

## 当前待查链路

1. 正式绘图页：截图频率、预处理复用、绘制节流和 UI 更新边界。
2. 正式导航页：定位帧输入、局部跟踪、运动预测、输出节拍和恢复边界。
3. 实验双人页：首帧注册、实时 worker、latest-only、Qt drain、首帧 accepted 门和异常清理。
4. 只读性能对照：capture、recognition、tracking、render、logging 各阶段耗时。

## 后续动作

- 先完成正式/实验链路对照和问题分类。
- 再检索成熟的 latest-frame、ROI、异步流水线和视觉跟踪方案，记录来源与适用边界。
- 只有形成单一可验证假设后，才建立回归用例并修改代码。

## 只读对照结论（2026-10-07）

### 确认的首帧阻塞根因

- 手动按钮 `dual_first_frame_button.clicked` 直接调用
  `run_dual_first_frame_experiment()`。
- 该方法在 Qt GUI 线程内同步执行 `_compute_dual_first_frame()`：一次内存锚点读取、3 次截图、每次预处理/墙体提取/HSV 候选提取、每次完整 `DualFirstFrameRegistrar.register()`，最后才回到 Qt 应用。
- 当前 `experiment.py` 和页面入口都把候选上限设为 6；注册器会遍历长度为 2 的有序排列，候选数为 6 时是 `6P2=30` 组，每组还可能执行 midpoint geometry 或 joint similarity 搜索。因而首帧出现几十秒至约 70 秒的空转/无响应是可推导的，不是单纯 FPS 参数问题。
- `start_dual_motion()` 要求 `_last_dual_first_frame_result.accepted`、`_dual_initial_frame` 和 tracker 上下文同时存在；同步首帧未完成、被拒绝或在 UI 阻塞期间状态未应用时，实时入口只能显示“首帧配准未通过/启动失败”。

### 正式页面可复用的边界

1. 绘图：`MappingRuntimeLifecycle` 只调度定时器；`MappingSession.tick()` 一次采集一次识别一次 stitch，人物识别失败回退上一帧/中心。
2. 导航：`NavigationRuntimeFrameLoop` 每帧按 capture→player local position→localize→task update→render；`resolve_player_local_position()` 回退上一帧位置，事件识别异步，不阻塞主定位帧。
3. 实验双人：连续 worker 已有 latest-only 槽，但首帧注册仍是同步入口；实时 worker 同一帧还做 combined wall mask、HSV profiles、候选排序、双角色 tracker、证据归档和 UI drain，未像正式导航那样把重型非必要工作隔离到低频/异步路径。

### 当前不应做的改动

- 不直接把候选数、面积阈值、置信度或 FPS 再次“调一把”。这些参数改变无法解决 GUI 同步注册和 `6P2` 搜索的结构性耗时，且已造成过负面回归。
- 不把正式导航的单人中心模式直接套到双人；双人必须保留两个绝对锚点和无中心假设。
- 不在没有 traceback/阶段耗时的情况下把“点击后崩溃”归因于 Qt、MSS 或虚拟手柄。当前证据足以确认 UI 长阻塞，但还不足以确认 native 崩溃。

## 后续改造边界（待用户确认后实现）

### A. 首帧生命周期

- 将手动首帧和恢复首帧统一为一次性后台任务；GUI 线程只负责提交任务、显示阶段状态、应用 bundle。
- 任务内部保留“读锚点→截图→候选→注册→选择”的纯数据边界，禁止访问 Qt 控件。
- 首帧候选先按 profile/几何 NMS 保证每个角色至少一个候选，再用绝对锚点做有界筛选；注册器不接受无界排列。正常双人场景最多保留每角色 2 个候选，只有证据不足才扩大上限。
- 每个阶段记录 `capture_ms/recognition_ms/candidate_ms/registration_ms/total_ms/candidate_count/assignment_count/status`。

### B. 实时帧处理

- 采集与追踪保持 latest-only；旧帧直接丢弃，不排队。
- 墙体/combined mask 与人物候选分开计时；墙体位移低频更新，人物候选和关联高频更新。
- 预览、证据归档和详细日志降频，不得与控制帧共享同步路径。
- 暂时失配沿用上一帧角色状态和有界预测；只有地图变换失效/实例变化/预测不确定度越界才申请重定位。

### C. 生命周期安全

- 首帧 worker、实时 worker、retired worker 必须有 generation、terminal outcome 和 cleanup 记录；迟到 signal 只能被忽略，不能应用到新会话。
- 启动双人实时前验证首帧 bundle 的 instance、transform、两角色上下文；验证失败只结束本次启动，不释放已有地图/跟随上下文。
- 补充稳定 Python traceback、线程名、worker generation 和 Qt 回调阶段日志，区分“GUI 长阻塞”与真正 native 崩溃。

## 成熟方案参考（只读）

- OpenCV 视频跟踪文档：<https://docs.opencv.org/4.x/dc/d6b/group__video__track.html>。可用于 Lucas–Kanade/Pyramidal optical flow 和 Kalman 状态估计；只作为短时 marker 预测补充，不能替代绝对首帧锚点。
- ROS 2 `image_transport`：<https://docs.ros.org/en/rolling/p/image_transport/>。其 transport/plugin 边界说明了采集、传输、处理解耦；本项目可借鉴“帧源与处理器接口分离”，不直接引入 ROS。
- ROS 2 `image_pipeline`：<https://github.com/ros-perception/image_pipeline>。可借鉴分阶段 image_proc、低频重处理与诊断统计；不照搬其相机标定假设。
- OpenCV connected components/contour 文档：<https://docs.opencv.org/4.x/d3/dc0/group__imgproc__shape.html>。候选面积必须统一使用 contour area 或显式像素面积，不能在同一阈值下混用；这正是上次噪声候选暴增的教训。

## 当前状态

### 视觉组合器实现前边界（2026-10-07）

- `(confirmed)` `CapturedFrame.payload` 是 `bytes`，VisionProcess 负责把它交给 processor；当前 processor 只有 Echo/fake，真实 wall/marker/association 组件尚未组合成 `VisualObservation`。
- `(decision)` 组合器在视觉进程内解码图像，并通过可注入 wall extractor 生成单通道 wall mask；不跨进程传 NumPy，不引入 Qt、内存或手柄副作用。
- `(decision)` 复用首帧 `SimilarityTransform2D`：墙体位移只修正 transform translation，候选关联后再转换为 native 坐标；短时失配保留上一可信位置并输出 `PARTIAL`/`NONE`，不得输出 stop。
- `(next)` 新增 `follow_engine/vision/dual_observation_processor.py`，补充 PNG 离线回放测试；之后再决定是否把它注入 VisionProcess，当前不切页面默认入口。

### 视觉组合器完成（2026-10-07）

- `(implemented)` 新增 `follow_engine/vision/dual_observation_processor.py`：在 VisionProcess 内解码 `CapturedFrame.payload`，调用 wall/marker/association 组件，沿用首帧 `SimilarityTransform2D` 修正墙体 translation，并输出 native `VisualObservation`。
- `(implemented)` 组合器严格校验 generation、map instance、单调 sequence；缺失角色保留最近可信 native 坐标，输出 `PARTIAL`/`NONE` 和不确定度，不产生 stop 或恢复副作用。
- `(verified)` 新增组合器回归覆盖 PNG 首帧、墙体平移、标记短时缺失、坏 payload、代际/地图/序列门控；专项 17 passed，PoE2 全目录 516 passed，compileall/diff check 通过。
- `(boundary)` 组合器尚未接入真实 PoE2 capture、warm memory、Host 或页面默认入口；当前仍为可注入的离线/视觉进程组件，未发送真实输入。
- `(next)` 增加显式 capture→processor factory 的离线组合测试，再决定接入新 `FollowEnginePort`；保持旧页面默认链路可回滚。

### 视觉 worker 错误事件保护（2026-10-07）

- `(confirmed)` VisionProcess 的 latest-only event 队列会在 `error` 后被 `finally` 的 `stopped` 清空，导致父层只能看到停止而丢失真实 traceback。
- `(fixed)` `vision_process_entry()` 增加 `terminal_error` 门控；capture/processor 异常后保留结构化 error，正常显式 stop 仍发布 stopped。
- `(verified)` 新增 spawn 回归；组合器+视觉进程专项 8 passed。该修复只影响离线 worker 生命周期，不接触真实输入。
- `(next)` 执行 PoE2 全目录回归和最终工作树审计。

### 本轮最终验证（2026-10-07）

- `(verified)` `pytest -q tests/poe2_live_terrain`：`518 passed`；`python -m compileall -q src tests` 通过；`git diff --check` 通过。
- `(confirmed)` 本轮只改 follow-engine vision 组合器、VisionProcess 错误事件门控、对应测试和文档；`data/events/events.json` 与 `occlusion_diagnostics/` 仍保持用户运行数据状态，未纳入提交。
- `(boundary)` 离线 VisionProcess 已能实际运行 `DualObservationProcessor` 并发布标准 `VisualObservation`；真实 PoE2 capture、warm memory、Host output 和页面默认入口仍未接入，下一轮继续从此边界推进。

### 编码截图 capture adapter（2026-10-07）

- `(implemented)` 新增 `vision/capture_adapter.py::EncodedImageCapture`，把注入的 BGR provider 在 capture 侧编码为 PNG/JPEG bytes，维护严格 sequence，空帧不推进序列；默认时钟为模块级函数，满足 Windows spawn pickle。
- `(verified)` `test_follow_engine_capture_adapter.py` 与组合器/视觉进程专项共 13 passed；`CODEBASE.md` 已同步。
- `(boundary)` 尚未把页面现有 `preview_provider(config)` 和真实 MSS/PoE2 capture 直接接入新 port；当前仍是显式通用 adapter，旧页面默认链路不变。
- `(next)` 全目录回归后继续设计 warm memory source 的显式 factory，保持恢复与视觉进程隔离。

### Capture adapter 最终验证（2026-10-07）

- `(verified)` `pytest -q tests/poe2_live_terrain`：`523 passed`；compileall 与 diff check 通过。
- `(confirmed)` `EncodedImageCapture` 仅新增通用 BGR→PNG/JPEG bytes 边界；用户运行数据未写入/提交。
- `(boundary)` 真实 PoE2 screenshot provider、warm memory source、Host output 和页面默认入口仍未接入；不能把当前离线组合视为实机迁移完成。
- `(next)` 下一轮先复读本 checkpoint/ITERATION_LOG，再设计 warm memory source 的显式 factory 和离线控制组合。

## 快速内存重锚耗时核对（2026-10-07，本轮只读）

- `(confirmed)` 实机双人首帧日志 `14:46:12`：`memory_ms=3594.331`、`registration_ms=7405.446`、`total_ms=11151.526`；`14:52:45`：`memory_ms=3671.729`、`registration_ms=4131.939`、`total_ms=7964.704`。因此当前完整重定位约 `8–11s`，其中内存锚点读取约 `3.6s`，视觉注册约 `4.1–7.4s`。
- `(confirmed)` 当前 `Poe2PlayerPositionSource.read_once/read_many` 每次都会重新找 PID、解析 descriptor/layout、创建 `ProcessReader`、扫描 entity/component 表并读取 Render 坐标；双人 `read_many` 一次 reader 可得到两个角色，但仍重复承担上述冷启动/扫描成本。
- `(confirmed)` 旋转/镜像/比例已在首帧确定后，单点 `TerrainOrientation.transform_point` 与 reference-native 映射是纯内存计算，理论上为亚毫秒级；因此跟随异常时不应重新做视觉注册。
- `(decision)` 采用分层恢复：L0 使用上一可信点+速度预测继续跟随；L1 在冷却后读取一次内存并套用已有 transform，只更新角色位置；L2 仅在 L1 失败或局部冲突时做局部视觉校正；L3 仅在实例变化/transform 失效时做全局视觉注册。
- `(constraint)` L1 必须校验 `area_instance` 与首帧实例一致，并设置最短触发间隔（建议初始 `5–10s`）和连续异常门槛（建议 `3–5` 帧）；失败时继续预测而不是结束跟随。
- `(next)` 在不触碰真实输入的前提下，新增可注入的 warm-reader/transform-only 基准与回归：验证缓存 descriptor/layout/component 地址后，暖读只读取 area/player 坐标；确认 instance 变化拒绝快速路径，且快速路径不调用视觉注册。

## 异常恢复分层方案草案（2026-10-07，待用户确认）

- `(design)` 恢复优先级：A 视觉短时容错/最新帧重试 → B 运动预测继续跟随 → C 内存快速重锚并复用首帧 transform → D 局部视觉校正 → E 全局视觉重定位。任何普通异常都不自动结束动态跟随。
- `(design)` A 层只处理单帧或短暂失配：候选存在但关联失败时使用动态门限、双人相对几何和上一帧身份；下一帧成功即恢复，不读内存、不重定位。
- `(design)` B 层使用 `p_pred=p_last+v_est*dt`，不确定度按视觉年龄、速度误差和处理延迟增长；预测只在有界时间/不确定度内生效，持续输出或低幅探索，不释放 session。
- `(design)` C 层仅在连续失配或不确定度越界后触发，要求首帧 transform 有效且 area instance 未变；一次读取双人内存坐标，转换到 reference-native，只更新位置/速度滤波，不重新做方向/比例/视觉注册。建议初始门槛：连续 3–5 个有效处理帧失配，或预测不确定度 > 40–60 native px；同一角色最短冷却 5–10s。
- `(design)` D 层仅在内存失败、实例校验失败或内存点与预测冲突 > 30–50 native px 时触发；只在人物附近 ROI 做局部匹配，固定 transform，不做全图搜索；成功后回到 A/B，不成功继续预测并等待下一次 C。
- `(design)` E 层只允许在地图实例变化、首帧 transform 失效、C/D 连续失败且不确定度 > 100–120 native px，或地图/玩家证据同时失效时触发；必须异步执行，跟随 session 保持，完成后原地恢复。
- `(design)` 所有层均有成功/失败、冷却、升级和降级规则；失败不等于停止，只有用户手动停止才关闭动态跟随 session。
- `(next)` 先实现状态机和指标埋点，再实现 C 层 warm reader；随后补 D/E 异步边界和离线回放，最后才在实机开启快速内存兜底。

## 最新测试与分层方案对照（2026-10-07，本轮只读）

- `(confirmed)` 最新日志末段不是单一异常：P1 `StrDexFourb` 最后可信视觉时间距当前约 `25s`，`identity_dropout_failures≈293`，预测不确定度已升至 `114.6 native px`；P2 仍可见，双人 assignment 的观测间距约 `87px`、预测间距约 `1.5px`，因此现有双人关联无法恢复 P1。
- `(confirmed)` 按拟议门槛，这一会话应在连续 `3–5` 帧失配或不确定度超过 `50px` 时进入 L1 内存快速重锚，而不是继续把 `recovery_required/markers_missing` 重复输出到 `114px`。
- `(confirmed)` 同段还存在独立的 `poe2_not_foreground`（截图被忽略约数秒）和旧 Host 对 `program.heartbeat` 返回未知命令；前者是输入/采集门控，后者是 program lease 保活问题，不能由内存重锚方案单独解决。
- `(conclusion)` 分层方案能够直接覆盖“人物视觉长期失配导致预测漂移、全局视觉重定位过慢”这一主因；不能单独覆盖窗口失焦、旧 Host 心跳协议、worker 迟退等运行时问题，需并列修复并保持跟随 session。

## 恢复优先级修正（2026-10-07，用户确认方向）

- `(decision)` 只要采集到了新帧，恢复优先使用新帧做视觉匹配；上一帧失败不能直接跳到内存读取。
- `(decision)` 新帧存在时的顺序改为：最新帧候选重提取 → 动态关联/双人几何匹配 → 预测位置附近局部视觉匹配 → 仍失败才考虑内存快速重锚。内存不是新帧失败的第一反应，而是视觉证据不足或预测失控时的兜底。
- `(design)` 局部视觉匹配固定复用首帧 transform，只在预测/内存位置附近做 ROI 搜索，不重新估计方向、比例或全图注册；优先 ROI 半径 `80 native px`，必要时扩大到 `140/220 px`。
- `(design)` 若新帧为空、被前台门控丢弃、帧年龄超过阈值或连续局部匹配失败，才进入内存快速重锚；成功的视觉局部匹配应直接回到正常跟踪，不触发内存读取。
- `(next)` 实现恢复调度器时增加 `frame_available/frame_age/visual_attempt/local_attempt/memory_attempt` 诊断，分别测量新帧视觉、局部匹配和内存兜底耗时，避免误把“视觉候选关联失败”和“没有新帧”混为一种异常。

## 15:26 之后对话综合计划（2026-10-07，待确认）

- `(scope)` 本轮对话没有发现 15:26 之后的新运行日志；计划依据用户连续确认的设计决策和现有 14:46–14:53 实机证据整理，不把对话结论误当成新的实机验证。
- `(decision)` 恢复顺序最终确定为：新帧视觉全局候选/身份关联 → 新帧局部 ROI 视觉匹配 → 短时预测继续跟随 → 内存快速重锚 → 局部/全局异步恢复。上一帧失败不应直接触发内存读取。
- `(problem-set)` 待解决问题统一分为：P1/P2 暂时失配与双人关联漂移；P1 target stale/target_hold 过期；预测位置提前命中导致误到达；内存读取冷启动过慢；局部/全局重定位阻塞；Host program heartbeat 旧协议；前台门控；worker generation/迟退；实时帧处理过载；动态跟随错误释放 session。
- `(implementation-order)` 阶段 1 先做恢复调度器和详细状态/耗时诊断；阶段 2 做最新帧优先和局部 ROI；阶段 3 做 warm memory reader；阶段 4 接入 L0/L1/L2/L3 状态机；阶段 5 修复 Host/worker 生命周期；阶段 6 离线回放和实机验证；未经阶段 1–5 回归，不调整阈值或切换 C/Cython。
- `(acceptance)` 新帧存在时不得直接读内存；局部匹配成功不得触发全局恢复；内存失败不得停止跟随；全局恢复异步且保留 session；只有用户停止才释放动态跟随输出。

## 实施进度（2026-10-07，进行中）

### M4 backend single-flight 修复（2026-10-07）

- `(fixed)` `follow_engine/recovery/global_recovery.py::GlobalRecoveryBackend.in_flight` 现在把“future 已完成但尚未 poll 消费”视为仍占用 single-flight；修复快速 worker 在控制 tick 之间被重复 submit 的竞态。
- `(verified)` `tests/poe2_live_terrain/test_follow_engine_recovery_backends.py` 新增 completed-unpolled 回归；backend 聚焦测试 `4 passed`。
- `(boundary)` M4 backend 仍未接入 `FollowControlRuntime`；当前 control process 只调用策略，不提交/轮询 memory/local/global backend。
- `(next)` 扩展 memory backend 为异步 submit/poll，接入 runtime 的局部 ROI、内存快速重锚和全局异步恢复；恢复成功只 seed 角色状态并保持 session。

### M4 backend 接入控制 runtime（2026-10-07）

- `(implemented)` `MemoryRecoveryBackend` 增加单线程异步 `submit/poll`、generation 校验、冷却查询和结构化 error；`MemoryFastReanchor.cooldown_ready()` 只读检查冷却，不触发进程读取。
- `(implemented)` `FollowControlRuntime` 接入 local/memory/global backend：最新帧先按角色执行 bounded ROI；内存/全局只异步提交，后续 tick 轮询并以已有 transform/结果 seed tracker 与 odometry；恢复不清除目标、不释放 session。
- `(implemented)` `StageTiming.local_ms` 记录局部恢复耗时；局部/内存/全局失败仍交给 `RecoveryPolicy`，不会转成用户停止。
- `(verified)` runtime/backend 聚焦测试 `12 passed`；PoE2 全目录回归 `496 passed`；compileall 与 diff check 通过。
- `(boundary)` 当前 `FollowControlProcessHandle` 仍使用默认无 backend runtime，页面/真实 VisionProcess 尚未通过 M5 port 注入 backend；真实内存 source 尚未接入 warm reader。
- `(next)` M5 建立 `FollowEnginePort` 与 UI adapter，禁止页面直接持有 tracker/backend/future；随后将 fake vision/control/host 组合跑离线回放。

### M5.1 FollowEnginePort 与 UI adapter（2026-10-07）

- `(implemented)` 新增 `follow_engine/engine.py`：`FollowEngineStart`、`FollowEnginePort` 与三类端口协议，统一 generation、control/vision/output 启停、latest poll、target 更新和显式 user stop。
- `(implemented)` 新增 `follow_engine/ui_adapter.py`：页面只消费 `FollowUiState`，不直接管理 process/future/tracker。
- `(verified)` `test_follow_engine_port.py` 覆盖 latest 事件转发、输出快照、启动失败逆序回滚、多角色 target 显式 role；聚焦 `4 passed`。
- `(boundary)` `capture_test_page.py` 尚未切换到该 port；现有页面仍保留旧业务编排，下一阶段只接 adapter，不改静态/正式定位链。
- `(next)` M5.2 建立页面适配层的构造与轮询接口，先以 fake composition 验证再考虑替换 live follow 入口。

- `(implemented)` 已建立 `recovery_state.py`、`recovery_diagnostics.py`，显式定义视觉降级、局部/内存/全局重锚和动态保持状态；新增状态诊断回归，`2 passed`。
- `(implemented)` 已建立纯策略 `recovery_coordinator.py`：新帧优先视觉/局部，帧过期或无帧且预测超限才允许内存，冷却期间继续预测；新增策略回归，累计相关测试 `5 passed`。
- `(implemented)` 已建立 `memory_fast_reanchor.py` 封装双人一次读取、实例校验、transform 复用和冷却；新增注入 reader 回归 `2 passed`。当前仍未把 reader/layout 缓存接入真实 `Poe2DualPlayerPositionSource`，实机 3.6s 冷读成本尚未下降。
- `(next)` 将恢复调度器接入 live runtime/页面前，先补局部 ROI 匹配契约和 prediction/fusion 回归；随后接入真实 source 缓存并做离线回放。当前没有发送真实输入。

## 自检结果（2026-10-07）

- `(fixed)` 自检发现 `MemoryFastReanchor` 未注入时默认时钟固定为 0，会使无显式时间参数时冷却失效；已改为 `time.monotonic()` 毫秒时钟并复跑测试。
- `(confirmed)` 当前新增模块均可导入，恢复基础测试 `9 passed`、compileall、diff check 通过。
- `(gap)` `RecoveryCoordinator`、`MemoryFastReanchor` 和预测函数目前仍是独立纯模块，尚未接入 `capture_test_page.py` 的实时 tick；页面当前仍主要使用旧的 `RecoveryController`/`_request_live_follow_reanchor` 链。
- `(gap)` `local_reanchor.py` 目前只有 ROI 半径和 score 契约，尚未执行真实候选提取/局部墙体匹配；真实 `Poe2DualPlayerPositionSource` 仍未缓存 descriptor/layout/component 地址，3.6s 冷读实测未改变。
- `(next)` 先完成兼容适配层和局部 ROI 实际调用，再改 warm reader；没有完成这两步前不能让用户进行实机验收。

## 实时恢复旧链隔离（2026-10-07）

- `(implemented)` `capture_test_page.py` 的 live-follow retry 已改为 frame-first 分支，不再调用旧 `RecoveryController.schedule_retry()`；静态/legacy 实验仍保留旧 controller。
- `(verified)` 页面恢复相关聚焦测试 `9 passed`。
- `(boundary)` `_request_live_follow_reanchor()` 在缺少现有 local matcher 时仍有旧全局恢复 fallback；在完成真实局部 ROI 和内存快速重锚接入前，不能宣称旧 live recovery 已全部移除。
- `(next)` 将把 live `_request_live_follow_reanchor` 的 fallback 替换为新 `RecoveryCoordinator` → memory/local/global async 链，并增加测试断言旧 controller 在 live 模式零调用。

## 新策略接入 live reanchor（2026-10-07，进行中）

- `(implemented)` `_request_live_follow_reanchor()` 在 live 模式先调用 `RecoveryCoordinator`；根据最新帧年龄、失配持续时间和预测不确定度选择预测保持、局部视觉或升级恢复，并记录 `recovery_decision`。
- `(implemented)` live retry 仍绕过旧 `RecoveryController.schedule_retry()`；静态路径不变。
- `(boundary)` 当前 memory/global 的实际执行 backend 仍暂时复用旧 `_start_dual_motion(recovery=True)` worker，日志显式标记 `backend=legacy_global_worker replacement_pending=True`；这不是最终接管状态。
- `(next)` 把 memory fast reanchor 作为异步 backend 接入 decision=memory，成功后直接更新 tracker；再将旧 global worker 降为 decision=global 的唯一异步兜底并删除旧直接入口。

## 异步内存重锚接入（2026-10-07，进行中）

- `(implemented)` live decision=`memory` 现在提交到单线程 `ThreadPoolExecutor`，后台调用双人 `Poe2DualMemoryAnchorProvider.read_once()`；控制 tick 不同步等待。
- `(implemented)` tick 轮询 future 完成后校验 tracker/runtime，按角色匹配 anchor，seed tracker、更新最后可信位置并清除 recovery pending；失败才进入全局异步兜底。
- `(implemented)` 页面 suspend/shutdown 会取消 future，shutdown 释放 executor；内存重锚时间写入 started/elapsed 日志。
- `(boundary)` 真实 reader/layout/component 仍未缓存，因此当前后台读取仍可能承担约 3.6s 冷读；旧 global worker 仍是 memory 失败后的最终 backend，但不再由旧 controller 直接升级。
- `(next)` 为异步 memory success/failure 增加注入测试，随后实现 source warm cache，最后移除旧 global backend 的直接调用并改成新 `global_reanchor` 适配器。

## Program session 心跳修复（2026-10-07，实施中）

- `(confirmed)` Host 的普通 `heartbeat` 只更新 `StateStore` source lease，不会更新 `ProgramOutputLease.Deadline`；不能续租 `program.acquire` token。
- `(confirmed)` program lease 当前只有 `program.state` 会更新 `Deadline=now+1000ms`；实际输出 TTL 约 220ms，慢 tick 会先让 output 过期，再在下一次状态写入时发现 program token 已被 Host 删除。
- `(confirmed)` Host 尚无 `program.heartbeat` 命令；Python 输出层也没有独立 heartbeat 调度，所有续租依赖跟随 runtime tick。
- `(boundary)` 客户端请求本身有 `_request_lock`，可以安全地由独立心跳线程与控制线程复用同一客户端；但 token 读取、stop/close、rearm 必须用输出层锁和 generation 保护。
- `(next)` 先为 Host 增加 token 校验的 `program.heartbeat`，再为 `ProgramGamepadOutput` 增加独立保活线程/手动 heartbeat 接口；随后新增“控制 tick 阻塞超过 TTL 仍保持 program lease”的回归测试，并改造失效 session 的可重复 rearm 与旧 token 写入保护。

### 实施结果（2026-10-07）

- `(implemented)` Host 新增 `program.heartbeat`：校验 controller/token，只续 `ProgramOutputLease.Deadline`，不改变 `StateStore` 当前摇杆状态或 output TTL；普通 source heartbeat 仍不能续 program token。
- `(implemented)` `ProgramGamepadOutput` 在 `start()` 后启动独立 daemon heartbeat 线程，默认周期为 `min(250ms, max(50ms, ttl/3))`；`stop()/close()` 会先停止线程再释放 token。
- `(implemented)` heartbeat 发现 token 失效时进入 rearm；即使主控制 tick 没有任何输入/被重型计算阻塞，也会独立恢复 program lease。输出层增加心跳计数、失败数、耗时和 session 状态诊断。
- `(implemented)` `ProgramFollowOutput` 去除“每角色永久只允许一次 rearm”的限制，增加 500ms 退避；重建失败不再把失效 token 持续写入或立即炸掉跟随链。
- `(verified)` Python 聚焦回归 `74 passed`，`compileall` 和 `git diff --check` 通过；完整页面套件单独运行 5 个历史 timing-sensitive 用例 `5 passed`。完整并行套件出现 5 个既有时序 flaky 用例，单独复跑均通过。
- `(blocked)` 当前环境没有 .NET SDK，Host C# 测试无法执行；已补充 `ProgramHeartbeatRenewsOwnershipWithoutChangingOutput` 回归测试，待具备 SDK/Host 构建环境后运行。
- `(next)` 在用户明确授权实机测试前不启动游戏/不发送输入；实机观察重点为 `program_output.heartbeat`、`heartbeat_failures=0`、`session_expired=false`，以及控制 tick 阻塞时 controller=2 不再出现 session expired。

## 最新实机日志核对（2026-10-07 14:46–14:53，只读）

- `(confirmed)` Python 输出层已启动独立心跳，但运行中的 Host 返回 `invalid_argument: Unknown program command.`；`heartbeat_count=0`、`heartbeat_failures` 持续增长到 460，说明当前 Host 可执行文件尚未加载新增的 `program.heartbeat` 协议。不是 token 被撤销，也不是心跳线程没有运行；需要重启/更新 Host 后才能验证保活修复。
- `(confirmed)` 最新会话未出现新的 `Program session expired or was revoked`；controller=2 仍为 `acquired=True`、`inputOwner=program`，但心跳实际上没有续租旧 Host 的 program lease，当前依赖控制帧续租，仍有过期风险。
- `(confirmed)` `follow_hold_target_unconfirmed` 的触发条件是 `target.source == target_hold` 且距离不超过 `arrival_radius=12`；它表示 P1 目标视觉样本超过 `position_ttl_ms` 后正在沿用最后目标，不表示 P2 本身无法到达。此次 P2 距离约 1–2 native px，输出为中立帧，连续 session 仍保持 `armed=True`。
- `(confirmed)` 同一会话 P1 在约 14:53:27 后长时间没有新的有效视觉位置，worker 将 P1 标为 `markers_missing/recovery_required`；P2 已在目标附近，因此进入 hold 是符合当前状态机的，但原因命名容易让人误解为“目标到达未确认”。若 P1 此时实际继续移动而视觉持续失配，P2 会继续守在旧 target_hold 点，属于需要后续处理的定位失配边界。
- `(next)` 先重启/更新 Host 并复测心跳；随后单独处理动态跟随中的 stale target：区分“目标样本过期但目标未移动”和“目标已移动但视觉丢失”，必要时用 P1 的运动预测推进 target，而不是直接长期 hold 在旧点。

## 分段耗时与剩余风险（2026-10-07）

- `(implemented)` 双人实时 worker 现在分别记录 `capture_ms`、`recognition_wall_mask_ms`、`recognition_marker_observation_ms`、`candidate_ms`、`tracking_ms` 和 `total_worker_ms`；仍使用 latest-only，不增加帧队列。
- `(implemented)` 页面跟随 tick 在正常路径和提前返回路径统一记录：`context_ms`、`foreground_gate_ms`、`command_delay_gate_ms`、`live_context_ms`、`visual_state_ms`、`target_update_ms`、`prediction_update_ms`、`runtime_tick_ms`、`output_apply_ms`、`local_contact_ms`、`overlay_render_ms`、`total_tick_ms`。每 tick debug，首两次及每 10 次 info，避免诊断反过来拖慢控制。
- `(implemented)` 首帧日志补充内存锚点读取、截图/识别、候选注册和总耗时；局部/全局重锚日志补充请求耗时。
- `(implemented)` `ProgramFollowOutput` 暴露 `arm_ms/write_ms/neutral_write_ms/rearm_ms/release_ms`，并继续保持连续角色的输出租约；session 失效只走 rearm，不结束跟随。
- `(implemented)` worker drain 日志补充 evidence、preview、overlay、drain 总耗时，用于区分识别慢、Qt 绘制慢和控制页 drain 慢。
- `(verified)` worker、页面、动态 runtime 和虚拟手柄聚焦回归 `187 passed`；`compileall` 与 `git diff --check` 通过。
- `(audit)` 未发现动态跟随 tick 内仍会调用 `stop_follow_experiment()` 的路径；运行时异常、失焦、视觉丢帧、重定位和 Host session 失效均保持连续 session。`stop_dual_motion()` 仅保留给非连续/显式关闭边界。
- `(next)` 用户实机测试时查看 `step=dual_motion.timing`、`step=follow_experiment.timing`、`program_output` 日志；根据最大耗时段再决定是否做 ROI/低频墙体或更深流水线优化。本轮未发送真实输入。

## 跟随完整执行链文档（2026-10-07）

- `(documented)` 已建立 `docs/POE2_AUTOFOLLOW_EXECUTION_CHAIN.md`，按当前代码梳理 P1 手动位置采集、P2 预测/视觉融合、路径规划、局部控制、ProgramFollowOutput/Host 输出、逐 tick 时序、正常/异常/恢复链路。
- `(highlighted)` 特别记录 `target_arrival_unconfirmed` 的真实链路：`target_hold + command_prediction` 进入 `arrival_radius` → `WAITING_POSITION` → `ProgramFollowOutput.release()`，以及相邻的 `Program session expired` 和 `poe2_not_foreground` 独立分支。
- `(documented)` 文档区分静态同目标实验与动态实时跟随的到达语义，记录当前 `arrival_radius=12`、`resume_radius=20`、`effective_fps≈14.4` 等参数和性能边界。
- `(boundary)` 本轮只完成文档审查，没有修改运行代码、没有发送真实输入；后续若修改动态到达语义，应先为文档中标记的异常链补最小回归用例，再实现并验证。

## 动态跟随停止语义重新确认（2026-10-07）

- `(decision)` 用户明确确认：实时跟随是持续性动作，不能由目标接近、目标静止、视觉失配、路径失败、贴墙、窗口失焦、输出 session 失效或重定位自动结束；跟随只能由用户手动停止。
- `(confirmed-risk)` 当前 `runtime state -> ProgramFollowOutput._STOP_STATES -> release()` 是最高风险边界；动态跟随不能把 `WAITING_POSITION`、`ARRIVED`、`BLOCKED` 或 `MAP_MISMATCH` 直接映射为释放输出。
- `(required)` 动态跟随需要独立的持续状态集合：`FOLLOWING`、`FOLLOW_HOLD`、`FOLLOW_PREDICTING`、`FOLLOW_REPLANNING`、`FOLLOW_RELOCATING`、`FOLLOW_REARMING`；这些状态都保留 session、目标、timer、worker 和输出上下文。
- `(required)` `target_hold + command_prediction + distance<=arrival_radius` 必须转为保持/低幅校正，不能产生 `target_arrival_unconfirmed -> WAITING_POSITION -> release()`。
- `(required)` no-safe-route、撞墙、失焦和 Host session 失效只能进入探索、重规划、输入门控或 rearm；重定位也必须在原 session 内恢复。
- `(next)` 实现前先补“普通异常不结束动态跟随”的状态和输出回归用例，再改 runtime/output 边界；静态双人同目标的到达语义保持隔离。

## 动态跟随持续语义首轮实现（2026-10-07）

- `(implemented)` `FollowState` 增加 `FOLLOW_HOLD`、`FOLLOW_PREDICTING`、`FOLLOW_RELOCATING`、`FOLLOW_REARMING`。
- `(implemented)` `SimulatedFollowRuntime(continuous_follow=True)` 用于实时角色跟随；目标接近、`target_hold` 接近、目标/角色暂时缺失和 map mismatch 均不再使用静态终止状态作为动态语义。
- `(implemented)` `ProgramFollowOutput` 增加 `continuous_roles`；连续角色即使收到 `WAITING_POSITION`、`BLOCKED` 或 `MAP_MISMATCH` 等普通异常状态，也不会自动 `release()`，仍由跟随 session 持有输出租约。
- `(implemented)` 实时页面把 live program roles 注册为 continuous roles；静态点击目标和双人同目标不受影响。
- `(verified)` `tests/poe2_live_terrain` 439 passed；`tests/test_poe2_capture_test_page.py` 105 passed。
- `(verified)` 新增回归覆盖：动态目标接近、动态 target_hold 接近、FOLLOW_HOLD 输出保持租约；静态 runtime 到达测试仍通过。
- `(next)` 继续补齐动态异常状态（路径失败、重定位、Host rearm、失焦）的“不结束 session”集成回归，再做 compileall/diff check 和人工链路审查。

## 连续角色异常期间保留输出租约（2026-10-07）

- `(implemented)` `ProgramFollowOutput.release_all(force=False)` 对 `continuous_roles` 发送中立帧并保留 armed/session；`close_all()` 内部使用 `force=True`，只用于明确结束跟随时释放。
- `(implemented)` 页面现有失焦、等待视觉帧、地图上下文缺失、重定位和临时异常路径继续可以中立化输入，但不会撤销动态跟随的输出租约。
- `(verified)` 原有静态输出测试仍通过；实时页面回归已调整为验证中立帧而非 `stop`，`tests/test_poe2_capture_test_page.py` 105 passed。
- `(next)` 继续补动态异常状态的集成断言，确保恢复后同一 armed session 能继续写入方向；再完成 compileall、diff check 和人工链路审查。

## 连续跟随中立帧的 Host session 重建（2026-10-07）

- `(implemented)` `ProgramFollowOutput._write()` 统一处理移动脉冲和中立帧；中立保持期间发生 `Program session expired or was revoked` 也会只重建当前输出 session，不结束跟随。
- `(verified)` 新增中立帧 session 失效回归；`tests/poe2_live_terrain` 440 passed，`tests/test_poe2_capture_test_page.py` 105 passed。
- `(next)` 完成 compileall/diff check 后，人工复核所有动态错误分支是否都保留 follow session；再决定是否进入实机测试。

- 运行代码基于 `a3070ea`；本轮已完成首个结构性改动：手动/后台双人首帧只采集一次并注册一次，没有发送真实输入。
- 首帧回归测试已验证：`tests/test_poe2_capture_test_page.py -k dual_first_frame_experiment_renders_two_players_without_timer` 通过。
- 纯双人 tracker 已增加短时预测保持：静止/暂时不可测墙体复用上一变换，marker 失配和墙体异常时返回最后可信角色位置，并输出预测诊断；地图失效仍保留原有恢复边界。
- 纯 tracker 回归测试已通过：`tests/poe2_live_terrain/test_multiplayer_motion.py`（25 passed）。
- live worker 已增加 `candidate_ms`、`total_worker_ms`、processing EMA、自适应间隔和 effective FPS 诊断；latest-only 机制未改变。
- worker 回归测试已通过：`tests/test_poe2_dual_motion_worker.py`（10 passed）；页面双人专项（13 passed）。
- 预览/地图 overlay 已限制到 12Hz，控制状态仍消费每个 latest result；旧 worker 测试 fake 对象保持兼容。
- 离线回放已覆盖一帧 marker 缺失和一帧空墙体后恢复；下一步执行完整专项回归和 compileall。
- 专项全量回归已通过：`tests/poe2_live_terrain` + PoE2 页面/worker 共 548 passed；`compileall` 和 `git diff --check` 通过。
- 当前提交序列为 `c879d64`、`c34a170`、`416604a`、`92c316c`、`e20ffad`，均建立在 `a3070ea` 之上。
- 生产配置的手动首帧入口已改为复用 `Poe2DualFirstFrameWorker`；测试/最小配置仍保留同步钩子。首帧实验候选预算独立限制为 4，实时 worker 仍为 6。
- 后续专项回归（页面、worker、首帧、tracker、replay）共 `162 passed`；compileall 与 diff check 通过。
- 当前实现仍未做实机输入验证；需要用户下一轮启动程序后观察后台首帧状态、首帧耗时和实时 timing 日志。
- 部分角色可见、另一角色预测保持时，`prediction_active` 现在也会正确标记为 true；tracker/replay 回归 27 passed。
- 未跟踪的 `data/poe2_live_terrain_test/occlusion_diagnostics/` 是既有运行 evidence，本轮未删除或纳入代码提交。
- 仍未进行真实游戏窗口/手柄测试；下一步需在用户明确测试时观察首帧耗时、worker timing 和异常帧 prediction diagnostics。

## 用户确认的设计方向（2026-10-07）

- `(decision)` 首帧人物静止，连续三次截图没有收益；首帧改为一次采集、一次注册、一次应用结果。首帧失败时报告失败原因，不通过重复采样掩盖问题。
- `(decision)` 实时跟随优先提高有效处理频率，而不是提高请求 FPS 后让处理队列积压。采集/处理使用 latest-only；旧帧直接丢弃。
- `(decision)` 单帧人物候选异常、颜色干扰或暂时失配时，先沿用上一帧可信角色位置/地图变换，结合最近速度与手柄输出做短时预测，继续跟随；下一帧恢复后将视觉观测重新吸收，回到正常视觉轨道。
- `(constraint)` 单帧异常不能直接停止跟随，也不能立即触发全局重定位；只有连续异常超过有界预测窗口、地图变换失效或地图实例变化才升级恢复。

### 推荐状态机

```text
VISUAL_TRACKING
  ├─ 有效新帧 → 更新角色/速度/地图变换
  ├─ 单帧异常 → PREDICTIVE_HOLD
  └─ 连续异常且不确定度未越界 → PREDICTIVE_HOLD

PREDICTIVE_HOLD
  ├─ 新帧恢复 → VISUAL_TRACKING（融合，不重置轨迹）
  ├─ 仍异常但预测窗口未到 → 继续输出预测位移
  └─ 预测窗口/地图有效性越界 → LOCAL_REANCHOR；必要时才 GLOBAL_RECOVERY
```

预测使用上一帧可信位置 `p_k`、速度 `v_k`、输出方向 `u_k` 和帧间隔 `Δt`：

```text
p̂(k+1) = p_k + (α v_k + β u_k v_command) Δt
σ(k+1) = σ_k + σ_process Δt + σ_visual_gap
```

视觉恢复时不硬替换预测位置，而是按观测置信度融合：

```text
p(k+1) = (1-K) p̂(k+1) + K z(k+1)
K = σ_prediction² / (σ_prediction² + σ_observation²)
```

其中 `K` 只用于恢复过渡，避免一帧颜色噪声把人物位置突然拉走。

### 备选实现边界

**方案 A：单线程固定节拍 + latest-only（推荐第一步）**

- 采集线程只保留最新 raw frame；处理器每次取最新帧。
- 首帧任务单独一次执行，不进入实时循环。
- 识别阶段只做 ROI/候选提取和轻量 tracker；墙体 mask、预览和 evidence 低频处理。
- 优点是改动小、容易对照正式导航页、最容易回归；缺点是 Python 单帧仍需通过 profiling 找出最慢阶段。

**方案 B：采集、识别、跟踪三级流水线**

- capture producer、marker/ROI worker、tracking/output consumer 分离，各级 latest-only。
- 识别只发布结构化候选，不复制完整图像；预览另走低频通道。
- 优点是更容易把处理频率提高到有效 25–30Hz；缺点是生命周期、时间戳和跨线程退出复杂，必须先有 A 的阶段耗时基线。

当前建议先做方案 A，确认 `capture/recognition/candidate/tracking/render` 各段均低于目标周期后，再决定是否拆成方案 B。不能先上多进程或 C/Cython；只有 profiling 证明 Python 代码占主耗时，才考虑把单一热函数迁移到 NumPy/OpenCV/Cython。

## 离线证据核查（2026-10-07，本轮）

- `(confirmed)` `occlusion_diagnostics` 当前共有 83 个 `evidence.json`，其中 45 个 `recovery_required`、38 个 `degraded`；这些文件各自只有单帧 `candidates/diagnostics`，没有同一 session 的上一帧和恢复帧，因此不能单独证明连续跟随恢复或有效 FPS。
- `(confirmed)` 历史 evidence 的恢复原因主要为 `markers_missing`、`markers_partial_grace`、`markers_missing_grace` 和 `wall_and_local_match_failed`；部分旧 evidence 仍包含角色观察年龄已经超过 `max_age_ms` 的信息，不能把它们当作当前实现的实时输出。
- `(usable)` `data/poe2_live_terrain_test/samples/dual_player_20260925/raw.png` 与 `memory_probes/dual_player_20260925_probe/player-memory-probe-latest.json` 同属 `MapFlotsam:73681455`，图片为 300×300，探针提供双角色 native 网格 `(956.5,430.5)`、`(962.5,424.5)`；这是当前唯一可直接做“真实 raw + 同实例双锚点”离线首帧候选实验的历史样本。
- `(boundary)` `latest.npz` 和 `dual-debug-current` 探针属于其他地图实例，不能与 `dual_player_20260925/raw.png` 拼接验证注册；`multiframe_sessions` 及部分旧 sample 目录存在 Windows ACL 拒绝，不能假设其中有可读连续帧。
- `(next)` 先用同实例双人 raw 做低日志候选/注册耗时回放，再用现有合成 replay 验证“正常→单帧异常→恢复”；若要实证真实连续帧处理频率，需要用户补采最小连续序列。
- `(implemented)` 新增 `tests/poe2_live_terrain/test_historical_dual_replay.py`：直接读取已归档的 `dual_player_20260925/raw.png`、`wall.png` 和配置颜色，执行一次首帧注册以及真实 wall/raw 的跟踪恢复回放；测试不写应用日志。
- `(verified)` 历史 raw 回归 2 passed：首帧结果 `accepted`，最佳 pair confidence ≥ 0.90、shape quality ≥ 0.85；`tracking → degraded(prediction_active) → tracking` 恢复链通过；worker 路径连续 5 次最大耗时 < 33ms，`dropped_results=0`。
- `(boundary)` 该首帧注册使用同一张历史墙体图构造受控几何夹具，避免把不同实例的 native terrain 拼在一起；它验证真实图像上的单次注册流程和候选质量，不证明真实 native 全图配准耗时。
- `(diagnostic)` 对 83 张历史异常 raw 使用 evidence 自带颜色配置做无日志批量检测，平均检测耗时约 0.82ms；56/83 张仍提取到至少两个候选，23/83 张没有候选。后者属于输入确实缺失，不能靠提高采样频率单帧修复，只能由上一帧预测/后续恢复帧处理。

## 最新实机跟随异常核对（2026-10-07）

- `(confirmed)` 最新日志中的 `target_arrival_unconfirmed` 出现在 `12:18:11~12:18:39`，目标从约 `(950,982)` 后稳定在 `(960.3059,974.3315)`；不是目标继续移动造成的瞬时追赶误判。
- `(confirmed)` 触发时 P2 的当前估计来源为 `command_prediction`，位置 `(957.8049,981.7013)`，距离目标 `7.7826`，到达半径 `12.0`；最近一次视觉位置仍停在更早的 `(900.0785,1070.1693)`，所以视觉没有确认到达。
- `(confirmed)` `runtime.py` 在 `current.source == "command_prediction" and distance <= arrival_radius` 分支返回 `reason="arrival_unconfirmed"` 并生成短脉冲；但下一次页面诊断把状态显示为 `waiting_position`、`vector=(0,0)`、`acquired=False`，输出层释放了手柄。这是一次预测到达与实际输出状态不一致，而不是首帧或路径规划失败。
- `(confirmed)` 这次会话之后还出现 `step=live_role_follow.waiting_game_foreground reason=poe2_not_foreground`，约 12:18:39~12:18:44，最终是用户请求停止；窗口失焦是独立的后段异常，不能和 `target_arrival_unconfirmed` 混为一个根因。
- `(confirmed)` 同一会话实时目标前段确实连续变化，12:17:22~12:18:11 从约 `(1068,1066)` 移到 `(960,974)`；12:18:11 后目标保持不变。因此本次异常更接近“动态跟随目标停止后，P2 未被视觉重新吸收，预测到达分支未形成稳定 hold”而非持续移动目标策略本身。
- `(boundary)` 当前证据还不能证明游戏实际没有移动：日志只能证明虚拟手柄输出在 `waiting_position` 快照时已被释放，且视觉最后观测很旧；需要下一轮保留输出层每 tick 的 `program_ready → arrival_unconfirmed → released` 时序和游戏前台状态，区分“视觉未更新”与“角色未移动”。

## 本轮讨论结论（未改代码）

### 补充证据：输出会话与性能

- `(confirmed)` `12:18:12.467` 发生独立的 `VirtualGamepadError: Program session expired or was revoked`，约 1.1 秒后重新 `output_armed`；Host 随后继续接受 controller=2 报告。这是输入会话短暂失效，不是路径规划失败，但会放大视觉滞后。
- `(confirmed)` `12:18:15.123` 左右开始出现 `target_arrival_unconfirmed` 后，Host 的 controller=2 报告停止，页面持续显示 `waiting_position/vector=(0,0)/acquired=False`；因此这次 target arrival 实际释放了输出。
- `(confirmed)` 同段 worker 有效频率约 14.4 FPS、`processing_ema_ms≈58.5ms`、`dropped_results≈225`，P2 视觉年龄从约 8 秒增长到 34 秒，属于长期预测未重新吸收的背景异常。
- `(decision pending)` 输出会话过期需要和跟随状态解耦：输出适配层应记录“失效→重建→首个成功报告”，而不是让一次会话失效与视觉到达状态叠加成停顿。

- 跟随和静态定点不能共用同一个“预测进入半径即等待视觉确认”的终止语义。动态跟随应在目标新鲜或目标刚停止时保持低幅度校正，不应因单次预测距离小于半径而释放输出。
- 只有满足“目标稳定窗口 + 至少一次新的可信视觉确认 + 连续若干 tick 在半径内”才可进入 `ARRIVED/HOLD`；否则继续跟随或进入有界预测保持。
- `poe2_not_foreground` 需作为独立输入门控记录与处理，不应触发地图重定位，也不应伪装成 target arrival 异常。
- 下一步先补最小回归测试和更细的输出时序诊断，再讨论只对动态跟随放宽到达分支，避免破坏双人定点寻路。
- `(confirmed)` 这不是 ViGEm 驱动或 Host 进程断联：Host 日志在同一时间仍显示 `backendConnected=True`，controller=1 持续收到 report；失效的是 controller=2 的 program session token。
- `(confirmed)` controller=2 的 TTL 为 `220ms`，而异常会话中页面 `runtime_tick_ms` 达 `472–926ms`、总 tick 达约 `1s`；一次 `program.state` 续租前已超过 Host TTL，Host 合法撤销 token 并返回 `session expired or was revoked`。
- `(confirmed)` 失效后 `ProgramFollowOutput._write()` 每角色只允许一次 rearm；rearm 未形成稳定成功边沿后，后续移动帧和 foreground 中立帧继续使用失效 session，造成重复错误。`release_all()` 在失焦门控中被高频调用，放大了错误日志。
- `(inferred)` 基础问题是控制 tick 与 Host TTL 没有隔离：重型 runtime/恢复计算运行在 GUI 控制链中，输出 session 依赖同一条慢链路续租；不是单纯虚拟手柄硬件故障。
- `(next)` 优先修复顺序：输出租约独立保活/续租 → session 失效可重复 rearm 且有退避 → 失效 token 不再重复写中立帧 → 再把 recovery/runtime 重计算移出控制 tick。

## 当前实现进展（2026-10-07）

### 页面迁移审查（2026-10-07，本轮）

- `(confirmed)` 新 `FollowEnginePort`、`FollowEngineUiAdapter` 和 `Poe2FollowEnginePageAdapter` 只由独立离线测试使用；`capture_test_page.py` 没有注入或调用它们。
- `(confirmed)` 页面跟随入口仍由 `start_follow_experiment()` 直接创建旧 `SimulatedFollowRuntime`/`ProgramFollowOutput`，由 `_follow_timer` 调用旧 `_tick_follow_experiment_impl()`，停止时直接释放旧 output；页面还同时拥有旧双人视觉 worker 和恢复 future。
- `(confirmed)` 直接把页面切到新 port 目前不安全：`FollowEngineStart` 没有初始角色 seed/视觉发布接口，现有新视觉进程也没有真实 PoE2 capture/processor 组合，真实内存和 Host adapter 未注入。
- `(decision)` 本轮先实现可选、显式、互斥的页面 adapter 桥接：默认保持旧入口；只有调用方注入新 `Poe2FollowEnginePageAdapter` 并打开 flag 时走新入口。新入口失败只回滚本次 port，不触碰旧 runtime；旧入口 active 时拒绝启动新 port，禁止两个链路同时持有 controller lease。
- `(next)` 补页面桥接单元测试、fake adapter 生命周期测试和文档；离线通过后再考虑真实 capture/memory/Host composition。

### 页面迁移桥接与控制 factory（2026-10-07，本轮完成）

- `(implemented)` `capture_test_page.py` 接受可选 `follow_engine_page_adapter`；注入后按钮、timer、目标点击和停止只访问模块化 adapter，默认 `None` 仍走旧链路。
- `(implemented)` 模块化入口先停旧 probe/双人目标/旧跟随，再启动 `FollowEngineStart(map_instance, roles)`；启动失败不回退创建旧 runtime，poll 异常保持模块化会话。
- `(implemented)` `FollowControlProcessHandle` 支持 spawn-safe `runtime_factory`，可将 warm memory/local/global backend 组合注入控制子进程；未注入时兼容原纯 runtime。
- `(verified)` `pytest -q tests/poe2_live_terrain tests/test_poe2_capture_test_page.py`：`617 passed`；compileall、diff check 通过。
- `(boundary)` 真实 PoE2 capture/processor、warm memory source、Host output 尚未组合；新入口仍是显式 opt-in，不能据此宣称实机可用或已默认切换。
- `(next)` 下一阶段只在用户明确授权实机测试后，构造 spawn-safe 真实 composition，并先完成 R1 静止双人验收；期间保留旧入口回滚开关。
- `(committed)` 本轮提交为 `0039495 feat(follow-engine): add reversible page bridge`；提交未包含 `data/events/events.json` 或运行 evidence。

### runtime factory 错误边界加固（2026-10-07）

- `(fixed)` `control_process_entry` 已将 token/runtime factory 构造纳入结构化异常捕获；spawn-safe factory 失败会发布 `ControlProcessEvent(kind="error", error, traceback_text)`，而不是静默子进程退出。
- `(verified)` `tests/poe2_live_terrain/test_follow_engine_control_process.py`：`3 passed`。
- `(next)` 完整套件通过后提交该独立修复，并更新最终测试计数。

- `(found)` 全量回归暴露 latest-only 控制事件队列会用正常 stopped marker 覆盖同一 turn 的 factory error；3 个同时出现的旧 Qt/时间敏感失败单独重跑均通过。
- `(fixed)` 增加 `terminal_error` 门控，结构化 error 保持可见；factory failure 单测和 3 个旧页面用例单独通过。
- `(next)` 重新执行完整套件；若稳定通过，再提交错误边界修复。
- `(verified)` 完整套件重新执行：`618 passed in 82.81s`；compileall 与 diff check 通过。
- `(committed)` 错误边界修复提交为 `10a5407 fix(follow-engine): preserve control startup errors`；用户事件配置和运行 evidence 未纳入提交。

- `(implemented)` live 全局恢复统一通过 `recovery/global_reanchor.py::GlobalReanchorBackend`，页面 live 分支不再直接调用旧 worker。
- `(implemented)` 双人内存 source 缓存 layout，并在地图实例变化时失效重解析。
- `(implemented)` recovery episode 在策略决策前去重；聚焦页面/恢复/内存测试 `111 passed`，新增 backend 契约测试。
- `(remaining)` 局部 ROI 模块仍是契约层，真实匹配由 `DualVisualTracker` 下一帧执行，尚未把 score 显式反馈给 coordinator。
- `(next)` 运行完整套件、compileall、diff check 后再安排实机验收。

## 当前实现进展（2026-10-07）

- `(implemented)` live 全局恢复统一通过 `recovery/global_reanchor.py::GlobalReanchorBackend`，页面 live 分支不再直接调用旧 worker。
- `(implemented)` 双人内存 source 缓存 layout，并在地图实例变化时失效重解析。
- `(implemented)` recovery episode 在策略决策前去重；聚焦页面/恢复/内存及 backend 契约测试 `111 passed`。
- `(verified)` 局部 ROI 真实执行由 `DualVisualTracker.request_local_correction()` 在下一帧完成；页面不会把局部请求直接升级为全局恢复，只有内存失败才进入显式 global backend。
- `(verified)` 完整 PoE2/页面/worker/gamepad 套件 `576 passed`，compileall 与 diff check 通过。
- `(boundary)` 本轮未发送真实输入，Host 心跳协议仍需在更新后的 Host 重启后实机确认。
- `(next)` 重启程序和 Host 后进行一次完整双人跟随测试，重点观察 `recovery_decision`、`memory_reanchor_*`、`reanchor_backend backend=global_async` 和 `program.heartbeat` 日志。

## 架构修正结论（2026-10-07）

- `(decision)` 预测与视觉纠偏必须是两个独立、latest-only 的处理通道；当前实现仍是视觉 worker 产出状态后，由页面 tick 在视觉失配时退化到 `command_prediction`，不是持续并行的视觉/预测融合。
- `(confirmed)` 当前 P2 视觉丢失后没有使用下一帧/上一可信帧做局部 ROI 重定位，而是被 `occlusion_held` 保持并继续命令预测；这是本次漂移的结构性根因。
- `(design)` 新链路：预测通道按手柄输出和速度模型连续推进；视觉通道按最新帧做全局候选/局部 ROI 纠偏；融合器按观测新鲜度和置信度吸收视觉，不允许任一来源永久独占。
- `(design)` 视觉暂时不可信时保留预测输出但立即启动局部纠偏；局部纠偏失败才允许低频内存快速重锚；内存失败才进入异步全局恢复。异常不释放动态跟随 session。

## 双通道执行模型（用户确认方向，2026-10-07）

- `(confirmed)` 当前实现不是全链路多进程：`Poe2DualMotionWorker` 是 Python `threading.Thread`，内存重锚使用 `ThreadPoolExecutor`，融合/路径/输出在 Qt 控制线程；因此视觉丢失后的预测与局部纠偏没有真正独立运行。
- `(decision)` 采用“预测进程/视觉进程/控制融合线程”三段式，而不是为每种异常创建进程。预测进程保持 30–60Hz，小状态输入；视觉进程 latest-only 处理截图和局部 ROI；融合线程负责时间戳、置信度、输出与状态机。
- `(design)` 内存快速重锚作为独立低频任务（一次读取、冷却、结果带 generation/instance 校验）；全局恢复仍异步且低频，不能阻塞控制输出。
- `(constraint)` 不直接把现有 Qt worker 改成进程：截图 provider、Qt signal 和 Windows 句柄不可直接跨进程复用；需要先定义共享内存/序列化快照契约和退出协议。

## 最新实机异常（2026-10-07 17:19，会话只读分析）

- `(confirmed)` P1 `StrDexFourb` 持续有视觉接受，例如 `17:19:34.503` native `(945.45,654.33)`；P2 `DexFourb` 的最后可信视觉时间为 `17:18:48.559` 左右，至 `17:19:34` 已失配约 `45.9s`。
- `(confirmed)` P2 在 `17:19:20~17:19:34` 反复出现 `dual_motion.tick ... markers_partial_grace/markers_missing`，但页面每次都记录 `live_role_follow.occlusion_held reason=no_recovery_evidence`，没有进入 `recovery_decision`、`memory_reanchor` 或局部/全局重锚。
- `(confirmed)` P2 位置完全由 `command_prediction` 维持，页面估计从约 `(933,827)` 推进到 `(922.9,774.2)`；同段 tracker 的 `uncertainty_native` 已从约 `102` 增长到 `206`，超过现有观察边界，但跟随层使用了另一套约 `10~12` 的预测不确定度，形成了错误的“仍可继续预测”判断。
- `(confirmed)` P2 输出持续为非零手柄脉冲，`observed_speed≈15.82`、每次 `command_duration_ms=80`；这证明预测器把“命令已发送”当成了“角色已按预期位移”，而没有新的视觉/内存事实校正，因此可能把 P2 推到 P1 前方。
- `(confirmed)` 目标点本身不断来自 P1 的视觉位置，P2 路径目标随 P1 变化；问题不在目标源停止刷新，而在 P2 自身位置源已经过期仍被用于路径规划。
- `(confirmed)` 当前 Host 心跳仍是旧协议表现：`heartbeat_count=0`、`heartbeat_failures>1000`；本段没有 session expired，但不能把 `controller=2 armed` 当作游戏真实移动已确认。
- `(conclusion)` 首要根因是“P2 长期视觉失配被 occlusion-held 抑制恢复 + 命令预测继续累积”，不是单纯方向反转。需要把双人跟随的恢复触发从“是否检测到墙体接触”改为“角色观测年龄/不确定度/预测-视觉一致性”联合门控；P2 超过短时预测窗口后必须重新使用最新帧局部匹配或低频内存锚点，不能因 `no_recovery_evidence` 永久保持。
- `(boundary)` 当前截图只能证明 UI 估计的 P1/P2 标记和目标叠加关系，不能单独证明游戏内实际 P2 已超过 P1；需下一次记录内存锚点或连续视觉恢复帧作为最终事实。

## 双通道引擎重构计划（2026-10-07）

- `(checkpoint)` 已将此前恢复链和 Host/session 改动提交为 `ea72667 checkpoint: isolate follow recovery boundaries`；未提交 evidence 数据。
- `(design)` 完整设计已写入 `docs/plans/2026-10-07-poe2-follow-engine-multiprocess-design.md`。
- `(decision)` 采用两个长期业务进程：`VisionProcess` 负责截图/墙体/人物/局部 ROI，`FollowControlProcess` 负责预测/融合/路径/恢复/输出；Qt 只做 UI，Host 保持独立。
- `(design)` 内存快速重锚和全局恢复作为控制进程内的低频单次任务，不为每种异常创建独立进程；进程间使用 latest-only shared frame ring 和带 generation/sequence/instance 的结构化快照。
- `(next)` M0 先冻结回放和纯逻辑契约，随后按 M1→M7 迁移；在 M1/M2 离线回归通过前不迁移实机输入。

## M0 离线回放夹具完成（2026-10-07）

- `(implemented)` 新增 `experimental/follow_engine/replay.py`，提供无副作用的 `ReplayEvent`、`ReplayManifest` 和 manifest 加载/稳定签名。
- `(implemented)` 新增 `tests/poe2_live_terrain/fixtures/follow_replays/scenarios.json`，覆盖正常双人、单帧失配、短/长视觉丢失、局部恢复、内存恢复、Host session 失效和地图变化。
- `(verified)` `tests/poe2_live_terrain/test_follow_engine_replays.py`：`2 passed`；回放明确 `real_input_allowed=false`，不连接游戏、内存或 Host。
- `(next)` 进入 M1.1：实现跨进程不可变 DTO 和输入校验；完成后再实现 generation/sequence 门控。

## M1.1 纯契约完成（2026-10-07）

- `(implemented)` 新增 `follow_engine/contracts.py`：`FrameSlot`、`VisualObservation`、`PredictionSnapshot`、`FusionSnapshot`、`OutputIntent`、角色状态 DTO 和 `StageTiming`。
- `(boundary)` 所有 DTO 都是 frozen/slots，不包含 Qt、游戏内存、截图 provider 或手柄副作用；角色映射和消息头在构造时校验。
- `(verified)` `tests/poe2_live_terrain/test_follow_engine_contracts.py`：`7 passed`，覆盖不可变映射、有限数值、归一化输出、错误角色和非法帧元数据。
- `(next)` M1.2 实现 generation/sequence/map instance 门控，确保迟到进程结果不能覆盖新会话。

## M1.2 代际与序列门控完成（2026-10-07）

- `(implemented)` 新增 `follow_engine/generation.py`：`GenerationClock` 创建单调 session generation，`SequenceGate` 校验 generation、map instance 和严格递增 sequence。
- `(verified)` `tests/poe2_live_terrain/test_follow_engine_generation.py`：`2 passed`；覆盖停止/重启代际、重复帧、逆序帧、旧代际和地图实例不一致。
- `(boundary)` 门控只处理消息生命周期，不改变人物预测、视觉算法或输出行为。
- `(next)` M1.3 实现 command odometry、速度校准、位置融合和预测不确定度增长。

## M1.3/M1.4 预测融合与恢复策略完成（2026-10-07）

- `(implemented)` 新增 `follow_engine/tracking/`：命令里程计、实际速度校准、预测/观测融合、创新门控、不确定度增长和角色跟踪状态。
- `(implemented)` 新增 `follow_engine/recovery/recovery_policy.py`：L0–L3 恢复决策、局部优先、内存冷却、全局单次异步语义、Host rearm 分支和动态 session 保持。
- `(verified)` `test_follow_engine_fusion.py`：`7 passed`；`test_follow_engine_recovery_policy.py`：`7 passed`。
- `(fixed)` odometry 发现并修复负数/NaN pulse duration 会被静默截断的问题；tracking state 同步拒绝非有限位置、速度和不确定度。
- `(next)` 运行 M0/M1 聚焦全套并提交本批次；之后进入 M2 latest-only 帧环和 VisionProcess。

## M2.1/M2.2 latest-only 帧通道与视觉进程骨架（2026-10-07）

- `(implemented)` 新增 `follow_engine/latest_frame_buffer.py` 和 `shared_frame_ring.py`；固定容量、最高 sequence 优先、旧帧丢弃，不使用无界图片队列。
- `(implemented)` 新增 `follow_engine/vision/capture_adapter.py` 与 `vision_process.py`；VisionProcess 使用 Windows spawn-safe 入口、bounded event queue、显式 stop/join/terminate 和 generation/map instance 校验。
- `(fixed)` 首次跨进程测试发现 `mappingproxy` 无法 pickle；DTO 已改为 pickle-safe 的只读字典，契约测试和 spawn 视觉进程测试均覆盖此边界。
- `(verified)` 帧环、视觉进程、契约聚焦测试：`10 passed`。
- `(boundary)` 当前视觉进程只验证 capture/processor 生命周期和消息传输，尚未接入 PoE2 墙体、人物候选、局部 ROI 算法。
- `(next)` M2.3 拆出 wall processor、marker processor、双人关联和 local ROI matcher，保持视觉进程不访问 Qt、内存和手柄。

## M2.3 视觉处理组件完成（2026-10-07）

- `(implemented)` 新增 `vision/wall_processor.py`：墙体位移低频处理和质量/形状门控。
- `(implemented)` 新增 `vision/marker_processor.py`：复用现有 HSV profile 候选提取，单独记录候选数和处理耗时。
- `(implemented)` 新增 `vision/dual_association.py`：位置、速度、双人相对几何为主；颜色冲突造成部分匹配时自动进行无颜色几何回退。
- `(implemented)` 新增 `vision/local_roi_matcher.py`：按 `80/140/220` 半径逐级局部匹配，失败只返回结果，不产生停止动作。
- `(verified)` `test_follow_engine_vision_processors.py`：`4 passed`；覆盖墙体位移、颜色候选、双人颜色污染和 ROI 扩展。
- `(boundary)` 这些组件已具备独立契约，但还未把 PoE2 现有 `DualVisualTracker` 全量搬进 VisionProcess；下一步接入控制进程前先建立组合处理器。
- `(next)` M2 阶段收尾：增加视觉处理组合器，把最新帧→墙体→人物→关联→局部 ROI 输出为 `VisualObservation`。

## M3.1–M3.3 控制进程与输出调度器（2026-10-07）

- `(implemented)` 新增 `control/follow_control_process.py`：纯 `FollowControlRuntime` 和 spawn-safe `FollowControlProcessHandle`；父进程只发送视觉/目标消息，子进程发布最新融合快照。
- `(implemented)` 新增 `control/route_controller.py`：输出有界方向和 `FOLLOW_HOLD` 语义；目标进入半径只发中立意图，不释放 session。
- `(implemented)` 新增 `control/output_scheduler.py`：输出提交、连续角色租约、Host heartbeat、session 过期 rearm 分开处理。
- `(verified)` 控制运行时 `3 passed`、spawn 控制进程 `1 passed`、输出调度 `2 passed`。
- `(boundary)` 当前 route controller 是可替换的直线路由骨架，尚未接入现有地图 PathFinder/局部 steering；输出 scheduler 尚未绑定真实 Host。
- `(next)` M4 实现 memory fast reanchor/global async backend 的新 port，并为控制进程接入恢复结果。

### M7 offline replay runner（2026-10-07）

- `(implemented)` `follow_engine/replay.py` 新增 scenario loader、`OfflineReplayRunner` 和 `ReplayRunResult`；M0 fixture 的 8 个场景均构造真实 control observations 并运行 tick。
- `(implemented)` `FollowControlRuntime.signal_recovery()` 与 spawn command `recovery_signal` 支持 Host session expired、map changed、transform invalid；信号只改变恢复状态，不释放动态 session。
- `(verified)` replay/control 聚焦测试 `9 passed`；未连接真实游戏/内存/Host。
- `(boundary)` replay runner 使用 fake observations，memory/global worker 仍需在 M8 前用注入 fake backend 单独验证；页面旧入口尚未切换。
- `(next)` 创建 M8 acceptance 文档，明确离线门槛、真实输入 opt-in 检查和当前迁移开关；完成最终全量回归与文档审计。

### M8 离线验收与发布前审计（2026-10-07）

- `(implemented)` 新增 `docs/POE2_FOLLOW_ENGINE_ACCEPTANCE.md`，记录 M0–M7 交付边界、离线门槛、真实输入 opt-in、R1–R10 实机顺序和回滚边界。
- `(verified)` 当前 M0–M7 代码提交链连续存在：`57b850a`→`394b9a5`→`0cabe65`→`366b975`→`4e8155d`→`cdfa2f4`→`527d946`→`f858d84`→`f830537`→`3d656d1`→`791e68c`→`82f204e`；用户运行数据未加入提交。
- `(boundary)` 旧 `capture_test_page.py` 默认入口仍未切换，真实内存/Host/游戏窗口未连接；因此本阶段结论是离线引擎完成，不是实机发布完成。
- `(next)` 如继续执行，应单独安排页面入口迁移和用户明确授权的 R1 实机测试；在此之前保持新 port 离线可用且不发送真实输入。

### M2.4 VisionProcess supervisor 补齐（2026-10-07）

- `(implemented)` 新增 `follow_engine/process_supervisor.py`：当前 generation 事件过滤、异常/意外停止识别、有界重启、退避和 FAILED 终态；显式 stop 后不会自动重启。
- `(verified)` supervisor 聚焦测试 `2 passed`；不连接真实 VisionProcess 或游戏。
- `(boundary)` supervisor 尚未替换页面旧 worker 的直接生命周期管理，需在页面 port 迁移时装配。
- `(next)` 最终全量回归后提交该补齐阶段；实机页面迁移仍单独 opt-in。

### final lifecycle cleanup hardening（2026-10-07）

- `(fixed)` `FollowEnginePort.stop()` 和 `ProcessSupervisor.stop()` 现在在 adapter/worker stop 抛异常时仍清空 active、generation/token 和 restart 状态，避免页面被陈旧会话锁死。
- `(verified)` 新增端口/supervisor stop-failure 回归；下一步执行最终全量测试并提交。

### M5.2/M6.1 页面 adapter 与阶段计时（2026-10-07）

- `(implemented)` 新增 `ui/modes/poe2_live_terrain/follow_engine_adapter.py`，页面侧只暴露 start、target_clicked、poll、stop 和状态回调，不复制控制/恢复逻辑。
- `(implemented)` `StageTiming` 新增 prediction/recovery/memory/global 字段；控制 runtime 记录预测、ROI、恢复轮询、内存/全局 future、路线和总 tick 耗时。
- `(verified)` page adapter、contracts、runtime 聚焦测试 `15 passed`，compileall 通过。
- `(boundary)` 该 adapter 尚未替换现有 `capture_test_page.py` 的默认旧跟随入口；实际页面切换需要先完成压力和生命周期回归。
- `(next)` 实现 M6.2 latest-only/控制压力回放和 M6.3 spawn 启停回归；之后再决定页面默认入口的迁移点。

### M6.2/M6.3 压力与生命周期回归（2026-10-07）

- `(implemented)` 新增 latest-only 压力回归：模拟 300 帧高速发布，槽只保留最新值，旧帧有界丢弃；控制 runtime 模拟 30Hz 视觉/60Hz tick，检查 session 保持与 tick 总耗时。
- `(implemented)` 新增 spawn 控制进程重复启停回归，覆盖 5 轮 generation，确认 stop 后没有残留 process 引用。
- `(verified)` `pytest -q tests/poe2_live_terrain` 为 `503 passed`；compileall 通过；未发送真实输入。
- `(boundary)` 压力门槛是离线结构/耗时门，不代表真实 PoE2 图像识别耗时；实机验收仍需在 M8 分级执行。
- `(next)` 补离线 replay runner，把 M0 场景接到新 port，验证 visual miss/local/memory/global/host-expired 不释放 session；随后再评估旧页面入口迁移。
- `(P0/P1)` 新 port 的 `VisualObservation` 没有携带原始帧，`FollowEnginePort.poll()` 也没有传 frame；真实 spawned control 里的局部 ROI recovery 无法拿到图像，只能使用测试里手动注入的 `new-frame`。
- `(P1)` VisionProcess stale sequence 分支会 `continue` 跳过 interval wait，重复 sequence 可导致忙循环；handle stop 也没有关闭 capture/processor 资源。
- `(P1)` Vision/Control handle 复用重启不清理命令/事件队列和 processor 状态；旧 generation/sequence/error 可能污染新会话。
- `(P1)` Control command queue 满时 `_send()` 单次丢旧后再次 `put_nowait()` 仍可能抛 `queue.Full`；控制进程 stop 只标记 session，不关闭 memory/global executor。
- `(P1)` Output heartbeat 失败只计数不 rearm；FollowEnginePort 对 worker error/stopped 只记录/忽略，active 仍保持 true。
- `(P0)` 新引擎真实 capture、首帧 seed、warm memory、Host output 尚未接入；路线控制仍是无地图的直线骨架，正式避障/窄道验收未完成。
- `(P1)` control command 缺 generation/sequence，未知或缺字段命令可能直接杀死 control process；默认 wall extractor 也尚未接入 PoE2 combined wall mask。
- `(verified)` `pyproject.toml` 已声明 Python >=3.11、OpenCV、NumPy、PySide6、MSS；需继续做全仓导入、完整测试和 Windows spawn 复核。
- `(next)` 完成全仓静态导入/测试证据后，再按 P0/P1 优先级提出修复批次；本轮审查不直接修改运行源码。

### 全面审查补充证据（2026-10-07）

- `(corrected)` 依赖声明此前记录有误：`pyproject.toml` 只声明 `requires-python >=3.11`，没有声明 OpenCV/NumPy/PySide6/MSS；这些位于根 `requirements.txt`。打包专用运行时另由 `packaging/distribution/requirements.lock` 提供 `PyDirectInput` 和 OCR 等依赖。
- `(verified)` 全仓 `auto_modules` 静态导入枚举 541 个模块，无导入异常；`pip check` 通过，但当前环境缺少 `pydirectinput`，所以 `tests/test_distribution.py::test_dependency_selection_excludes_unrelated_editable_project` 失败一次，属于打包测试环境依赖缺口，不代表新 follow-engine 模块导入失败。该用例单独重跑通过（环境状态存在时间敏感性），最终套件结果仍需按“全绿/非全绿”报告。
- `(confirmed)` 视觉拒绝后健康状态误判：`FollowControlRuntime.apply_visual()` 在创新被拒绝时保留旧 evidence 时间，但 `tick()` 仅依据当前 `visual_item.visible` 和旧 evidence age 判定 `visible`，因此同一帧的 rejected candidate 仍可清零 misses、进入 `tracking`。离线复现：远跳帧被 `fuse_observation` 拒绝，下一 tick 仍为 `tracking/visual_match`，`misses=0`。
- `(confirmed)` 预测提前到达：`tick()` 以固定 `magnitude * 100` 推进行程，`StraightLineRouteController` 随即按预测位置判断 `distance <= arrival_radius` 并发中立意图；离线复现目标 `(15,0)`、实际位置 `(0,0)` 时第二 tick 即中立，视觉未确认也不会继续输出。
- `(confirmed)` Vision stale sequence 分支位于 `vision_process.py:64-67`，`continue` 跳过 `stop_event.wait()`；重复序列 provider 会让视觉进程忙循环。`EncodedImageCapture` 正常递增序列，因此这是自定义/真实采集重复序列时的边界风险。
- `(confirmed)` 新 port 的局部恢复仍缺真实帧：`engine.py:116-120` 只转发 `VisualObservation`，控制侧 `apply_visual()` 没有收到原始 payload/frame；现有局部恢复测试通过手工 `frame="new-frame"`，无法证明 spawned 真实链路可用。
- `(confirmed)` 资源和重启边界未闭合：`VisionProcessHandle.stop()` 不调用 capture/processor close；`FollowControlRuntime.stop()` 不关闭 memory/global executor；同一 handle 重启不清空 command/event 队列和 processor/runtime 状态。Supervisor 新建 handle 可绕过部分污染，但页面直接复用仍存在风险。
- `(confirmed)` 控制命令缺 generation/sequence，`control_process_entry()` 对缺字段 visual/target 直接抛异常并终止 worker；`_send()` 满队列丢一次后再次 `put_nowait()` 仍可能 `queue.Full` 抛回 UI，且 visual/target/stop 共用一条队列。
- `(confirmed)` 输出心跳把 `heartbeat()` 返回 `False` 当作成功，异常只计数不 rearm；`FollowEnginePort.poll()` 对 worker error/stopped 只记录，`active` 仍为真，页面可能继续使用旧 snapshot。控制 tick 与 Host lease 的慢任务隔离尚未完成。
- `(confirmed)` 新路线仍为 `StraightLineRouteController`，没有地图墙体、门、窄道、局部 steering；新引擎的正式避障/导航能力尚未实现。
- `(boundary)` 仍未把真实 PoE2 capture、首帧 seed、warm memory、Host output 装配到新 port；旧 `capture_test_page.py` 默认仍走 legacy 跟随入口。M0–M8 离线通过不等于实机迁移完成。
- `(next)` 审查报告写入 `docs/POE2_FOLLOW_ENGINE_AUDIT_20261007.md`；下一动作按 P0→P1 批次修复，并先补上述回归测试，再安排用户明确授权的 R1 实机验收。

### 审查验证收口（2026-10-07）

- `(verified)` `pytest -q tests/poe2_live_terrain`：`523 passed in 18.24s`。
- `(verified)` 全仓静态导入：541 个 `auto_modules` 模块，无导入异常；`python -m compileall -q src tests` 与 `git diff --check` 通过。
- `(confirmed)` 打包闭包用例仍因当前解释器未安装 `pydirectinput` 失败：`tests/test_distribution.py::...dependency_selection...` 抛 `PackageNotFoundError`。未安装依赖以改变结果；应在发布隔离环境按 lock 安装后验证。
- `(boundary)` 523 个 PoE2 测试是离线契约/回放/进程骨架验证，不覆盖真实截图、游戏消费手柄、内存锚点或地图避障；本轮没有宣称实机完成。
- `(next)` 修复前先按审查报告批次 A 补测试：rejected visual 不得恢复健康、动态 follow 不得预测到达即中立、消息 generation/sequence 校验；随后才进入生命周期和真实组合改造。

### 批次 A/B 首轮修复（2026-10-07）

- `(fixed)` `FollowControlRuntime` 增加 accepted visual sequence；只有 fusion 接受的序列才能刷新角色健康状态。被拒绝的远跳候选继续进入 degraded/recovery，不会清零 misses。
- `(fixed)` 预测状态进入 arrival radius 但没有新视觉确认时，路线继续使用上一有效脉冲；已确认视觉到达的静态 hold 行为保留，动态跟随不再因预测单独中立。
- `(fixed)` 未确认到达脉冲改为按当前预测点到目标的方向衰减，避免长期复用旧方向导致越过目标后继续向前；预测恰好落在目标点时才使用上一方向的低幅 fallback。
- `(fixed)` `FollowControlProcessHandle` 发送的 visual/target/recovery/stop 命令带 generation/sequence；control worker 丢弃旧/重复命令，非法命令发布 `command_error`，队列饱和不再向 UI 抛 `queue.Full`。
- `(fixed)` Vision stale sequence 保持采样节拍；Vision handle 重启前清空事件并调用可选 `rebind_session`；Encoded capture 和 DualObservationProcessor 可重置 generation/map/sequence/时序状态。
- `(fixed)` vision worker finally 尝试关闭 capture/processor，control runtime stop/close 关闭 memory/global recovery backend；heartbeat 返回 false 时记录失败并尝试 rearm。
- `(fixed)` VisionProcessEvent 现在携带同一 sequence 的 `CapturedFrame`，FollowEnginePort 和 control command 会将该帧传给 `FollowControlRuntime.apply_visual(frame=...)`；无 frame 的旧 fake adapter 仍兼容。局部 ROI 已具备真实帧传输契约，但尚未接入 PoE2 实际 local search。
- `(fixed)` `FollowEnginePort` 增加 vision/control worker_state 诊断：vision worker error 不会伪装成用户停止，control worker error/stopped 时不再重复把旧 snapshot 提交给 output；动态 session 仍只由显式 stop 释放。
- `(verified)` 新增 rejected visual、predicted arrival 和 false heartbeat 回归；`pytest -q tests/poe2_live_terrain`：`526 passed`；控制/视觉/输出专项 `22 passed`；compileall、541 模块静态导入、diff check 通过。
- `(verified)` frame forwarding 和 worker_state 回归加入后，`pytest -q tests/poe2_live_terrain`：`528 passed`；port 专项 `6 passed`；compileall、diff check 通过。
- `(boundary)` 本批仍未解决真实局部 ROI frame 跨进程传递、地图 PathFinder、真实 Host/memory composition、FollowEnginePort worker error/stopped 状态升级；默认页面入口保持 legacy。
- `(next)` 下一批补 stop 独立可靠通道、worker 状态机和共享帧/ROI contract，然后做真实组合的离线回放验收；未经用户明确授权不发送实机输入。

## 共享帧环接入与局部恢复帧闭环（2026-10-08）

- `(root-cause)` 旧链路虽然已有 `SharedFrameRing`，但 `VisionProcess` 没有写入、`FollowControlProcess` 也没有读取；`CapturedFrame.payload` 仍经 multiprocessing queue 复制，局部恢复在真实 spawned 链路中无法稳定取得对应新帧。
- `(root-cause)` 会话重启时 capture sequence 会从 1 重新开始。若旧 ring 槽未清空，单调 sequence 门会拒绝新帧，导致隐式回退到完整 payload 传输或读取旧数据。
- `(implemented)` `SharedFrameRing.publish()` 现在校验 generation/sequence/timestamp/map instance/slot size；增加精确 `read(sequence)`、latest fallback、`clear()`、`rebind_session()` 和幂等 `close(unlink=True)`。
- `(implemented)` `VisionProcessHandle(frame_ring=...)` 在 start 时重置 ring 会话；子进程把编码帧写入共享 slot，`VisionProcessEvent` 仅标记 `frame_in_ring=True`，写入失败才保留兼容 `frame` payload。
- `(implemented)` `FollowControlProcessHandle(frame_ring=...)` 把 ring 传给 spawned control；`FollowControlRuntime.apply_visual()` 在没有 command frame 时按 observation sequence 读精确 slot，槽已覆盖才读更新 slot，并校验 generation/map instance。
- `(verified)` 新增/扩展 frame-ring、vision spawn、control local-recovery 回归；专项 15 passed，PoE2 全目录 531 passed（最终 close 幂等修正后专项再次 15 passed）。未启动游戏、未读实时内存、未发送真实输入。
- `(boundary)` 这是 opt-in 底层传输能力，尚未把真实 PoE2 screenshot provider、真实局部 ROI decoder/marker matcher、warm memory、Host 或页面默认入口接入；不能把离线 ring 回归当成实机完成。
- `(next)` 先补一个 spawn-safe 自定义 runtime factory + shared ring 的端到端离线组合测试，再实现可注入的 PoE2 local ROI decoder/combined wall mask；之后才评估新 port 的真实 composition 和页面迁移。
- `(verified)` 已补 Windows spawn 端到端回归：自定义 `runtime_factory(token, roles)` 通过 `attach_frame_ring()` 接收共享环，控制子进程在 metadata-only visual command 下完成 local ROI recovery；控制/视觉/帧环专项共 10 passed。

## 编码人物标记局部 ROI 适配器（2026-10-08）

- `(confirmed)` 现有 `marker_processor.extract_markers()` 已经复用用户校准的颜色 profile，并给候选提供 `identity_hint`/confidence；首帧的 `SimilarityTransform2D` 是唯一可信的 local→native 变换来源。
- `(implemented)` 新增 `vision/local_roi_search.py::EncodedMarkerRoiSearch`：接受 `CapturedFrame` 或 `SharedFrameRecord` 的 encoded payload，按预测 native 点逆变换到截图局部坐标，裁剪有限 ROI，调用现有 marker extractor，按距离/置信度/软颜色身份评分，并把候选转换回 native 坐标。返回 `RoiMatch` 和耗时，不触发停止、不读内存、不发送输入。
- `(implemented)` 通过 `vision.__init__` 导出适配器，但没有让 recovery policy 依赖 PoE2 术语；真实 composition 仍由上层显式注入 `LocalRecoveryBackend.local_search`。
- `(verified)` 编码标记 ROI、控制 runtime 和现有视觉处理专项共 15 passed。
- `(boundary)` 尚未自动接入 legacy page，也没有把真实 PoE2 marker profile/首帧 bundle 工厂接入新 port；下一步先做离线 seed bundle composition 和分段耗时基准，再决定真实 opt-in。

## 本轮验证收口（2026-10-08）

- `(verified)` `pytest -q tests/poe2_live_terrain`：`534 passed in 29.23s`。
- `(verified)` `python -m compileall -q src tests`、`git diff --check` 通过；静态导入扫描 570 个源码模块，`bad=0`。
- `(boundary)` 本轮没有启动游戏、读取实时内存、建立 Host/LAN 同步或发送真实手柄输入；用户运行数据未删除、清理或覆盖。
- `(fixed)` 由于 `FollowEnginePort.start()` 的顺序是 control→vision，`FollowControlProcessHandle.start()` 现在在 spawn 前先 rebind ring；地图实例变化会被控制子进程收到，而不是只改变父进程 spec。控制/帧环专项仍为 10 passed。

## Supervisor silent-exit 防护（2026-10-08）

- `(root-cause)` `ProcessSupervisor.poll()` 原先在 `poll_latest()` 没有事件时直接返回；如果 worker 在发布 error/stopped 前崩溃，状态会永久保持 `RUNNING`，页面无法获知控制/视觉 worker 已死亡。
- `(implemented)` 当 handle 暴露 `process.is_alive()` 且返回 false 时，supervisor 现在以 `worker_exited_without_event` 进入同一 bounded restart/backoff 逻辑；没有 process 属性的 fake handle 保持旧兼容行为。
- `(verified)` supervisor 专项 4 passed；未启动真实 worker 或发送输入。

## 当前批次最终验证（2026-10-08）

- `(verified)` `pytest -q tests/poe2_live_terrain`：`535 passed in 31.35s`。
- `(verified)` `python -m compileall -q src tests` 和 `git diff --check` 通过。
- `(boundary)` 新 ring、ROI adapter、supervisor silent-exit 均仍是 opt-in/离线能力；真实截图 provider、内存 source、Host、地图路径规划和页面默认入口尚未切换，不能进行实机完成度汇报。

## 新跟随 port 的离线真实组合边界（2026-10-08）

- `(root-cause)` 之前只有分散的 Vision/Control/Output 原语，没有一个统一 builder 校验首帧 seed 并把同一个 ring、transform、角色集合和 spawn-safe factory 交给两个 worker；调用方可能在组合时产生实例或角色不一致。
- `(implemented)` 新增 `follow_engine/composition.py`：`FollowSeedBundle` 校验地图、控制器、native/screen seed；`build_follow_engine_composition()` 构造 `DualObservationProcessor`、`EncodedMarkerRoiSearch`、共享帧环、vision/control handles 和 `FollowEnginePort`；`FollowEngineComposition.stop()` 负责 owner ring 的幂等 unlink。
- `(implemented)` `SpawnSafeFollowRuntimeFactory` 保持旧 `(token, roles)` 工厂签名，通过 runtime 的 `attach_frame_ring()` 接收共享帧源，不把 Qt/Host/内存 reader带入控制子进程契约。
- `(verified)` 离线端到端夹具已经跑通：静态截图 provider → 编码帧 → 双人视觉观察 → SharedFrameRing → 控制融合 → output snapshot；组合专项 2 passed。
- `(boundary)` builder 仍是 opt-in，capture/output 由调用方注入；真实 PoE2 screenshot provider、首帧内存 seed、warm memory、Host/gamepad、combined wall mask、地图 PathFinder 和 legacy page 迁移尚未完成。

## 组合批次验证收口（2026-10-08）

## Warm memory 与地图路由组合批次（2026-10-08）

- `(finding)` 新组合 builder 目前只装配局部 ROI，memory/global backend 和 map-aware route controller 仍需调用方手工创建；新引擎尚未能通过单一 composition 直接启用快速内存重锚或正式 A* 路由。
- `(boundary)` 真实 PoE2 reader、wall map 与 Host 仍不在本轮接入；只新增显式注入参数，避免旧页面默认链路和真实输入行为变化。
- `(next)` 扩展 spawn-safe runtime factory：可选 warm memory source+transform、可选 route controller；新增 `MapAwareRouteController`，复用 `PathFinder` 与 walkable target projection，路径失败时保留有界 direct-steering，不产生 stop。

- `(implemented)` `SpawnSafeFollowRuntimeFactory` 已支持可选 `memory_source`+`memory_transform`、cooldown、角色数量和 route controller；backend 在控制子进程创建，读取结果按 generation/instance/角色数量校验，异常不释放跟随 session。
- `(implemented)` 新增 `MapAwareRouteController`：目标先做局部可行走投影，再用共享 `PathFinder` 生成 waypoint；A* 无路、地图快照不可行或目标投影失败时返回 bounded direct-steering，不返回 stop。
- `(verified)` 新增组合回归覆盖 fake warm-memory 与地图路线注入；本轮中间回归 PoE2 专项 `539 passed`，`compileall`、`git diff --check` 通过。
- `(implemented)` `MapAwareRouteController` 增加路线缓存：同一目标和走廊内复用上次 A* 结果，只有目标移动、当前位置推进或偏离走廊超过阈值才重规划；无路结果缓存单点 fallback，避免每个 control tick 重复 A*。
- `(verified)` 路线缓存专项 `4 passed`；完整 PoE2 回归仍需在本轮最终修改后重跑。
- `(verified)` 最终全量回归 `540 passed in 24.08s`；未启动游戏、未读取实时内存、未连接 Host/LAN、未发送真实输入；用户运行数据未删除或清理。
- `(status)` 本批代码与文档同步完成；真实 PoE2/page opt-in、spawn-safe reader 独占性和地图版本绑定仍是后续独立验收，不在本轮伪装成已完成。
- `(implemented)` warm memory 组合增加 `memory_source_factory` 选项，reader 可在控制子进程内部创建，避免把持有 OS/process handle 的实例跨 Windows spawn pickle；`memory_source` 与 factory 互斥且必须同时提供 transform。
- `(implemented)` 带 `map_instance` 的路线控制器在 builder 中与 `FollowSeedBundle.map_instance` 做构造期一致性校验；不匹配立即 `ValueError`，不启动 worker。
- `(verified)` 组合边界专项 `5 passed`；真实 reader/page 仍未接入。
- `(boundary)` 仍未把真实 PoE2 reader、真实 wall snapshot、Host/gamepad 或 legacy page 默认入口接入；本批只完成显式组合能力和离线契约，实机仍需用户明确授权后的单独迁移验收。
- `(next)` 若继续推进，先做真实适配器的 spawn-pickle/独占 reader 合同检查与地图快照版本校验，再安排页面 opt-in；不要直接修改 legacy 默认入口。

- `(verified)` `pytest -q tests/poe2_live_terrain`：`537 passed in 34.56s`。
- `(verified)` `python -m compileall -q src tests` 与 `git diff --check` 通过。
- `(boundary)` 组合测试使用静态 capture 和 recording output，仅验证进程、ring、视觉、控制和输出契约；没有启动真实游戏、读取内存、连接 Host/LAN 或发送手柄输入。

## 模块化实机测试前收尾（2026-10-08）

- `(root-cause)` 新页面入口虽然已经装配真实截图、双人 seed、地图路由、warm memory factory 和 Host output，但沿用了模块化输出“首个 snapshot 立即建租约”的默认行为；旧链路已有 6 秒切回 PoE2 保护，新链路没有继承，工作台仍在前台时可能过早提交手柄状态。
- `(fixed)` `SnapshotOutputAdapter` 增加 `arm_delay_ms`/`clock_ms` 输出闸门：延迟期间视觉与控制继续运行，只跳过 Host output 创建和写入；延迟结束后使用最新 snapshot 建立租约。诊断增加剩余闸门时间。
- `(fixed)` PoE2 页面 concrete builder 默认使用 6000ms 输出闸门，并允许离线夹具注入 0ms；模块化页面轮询改为按 `localization_fps`（默认 30Hz，最新帧优先）而不是固定 100ms，停止/异常后恢复旧定时器。
- `(verified)` 新增 `test_snapshot_adapter_gates_host_lease_until_arm_delay_without_blocking_control`；新增 concrete page composition 的 Windows-spawn 风格离线夹具，验证真实 capture adapter→VisionProcess→shared frame/control→leader target refresh→output intent 链路，聚焦测试 `5 passed`。
- `(boundary)` 仍未启动真实 PoE2、读取实时内存、连接 Host 或发送真实手柄；本轮只证明真实适配器组合在离线 spawn 夹具中可运行。实机测试前必须由用户确认游戏窗口、Host、控制器 ownership 和安全位置。
- `(next)` 运行完整 PoE2 回归、compileall、静态导入和 diff check；随后做一次人工链路审查并给出 R1 实机测试步骤。若实机首帧或 Host 失败，先保留日志/evidence，不回退到旧链路偷偷混跑。
## 模块化 R1 实机测试前最终审查（2026-10-08）

> 本节是当前有效结论；此前各批次中的“尚未接入”均为当时的历史边界，不应覆盖本节状态。

- `(confirmed)` 主窗口 `build_poe2_live_terrain_composition()` 已显式注入 `follow_engine_page_adapter_factory`；因此正常 PoE2 页面点击跟随时进入模块化 port，未注入该工厂的独立测试页才保留旧链路。两条链路在启动前互斥清理，不共享旧双人 motion worker 或 output lease。
- `(confirmed)` accepted 双人首帧的 `players`、`primary_registration.transform` 和地图 `instance_id` 由 `build_follow_seed_from_dual_result()` 固化；seed 覆盖所有观测角色，受控角色可以是其子集，leader/follower 不依赖字典顺序。
- `(confirmed)` concrete builder 装配 `SpawnSafePoe2MonitorCapture`、`EncodedImageCapture`、`DualObservationProcessor`、`SharedFrameRing`、`FollowControlProcessHandle`、`MapAwareRouteController`、`Poe2DualPlayerPositionSource` factory 和 `SnapshotOutputAdapter`。视觉/控制 worker 使用同一 generation、map instance 和 frame ring；控制进程内创建暖内存 reader，父页面内创建 Host output。
- `(confirmed)` live-follow 每次页面 poll 先消费最新 control snapshot，再由 `Poe2FollowEnginePageAdapter._refresh_live_targets()` 将 leader 最新 native 位置写入 follower target；没有新视觉时回退首帧初始位置，不会把 leader 和 follower 合并成一个角色。
- `(confirmed)` `SnapshotOutputAdapter` 默认 6000ms 只闸住 Host lease 创建与写入，不阻塞视觉、预测和路线计算；闸门结束后使用最新 snapshot 建租约。`OutputScheduler` 负责持续角色 heartbeat、session rearm 和 neutralize；只有显式 `stop(reason="user")` 才释放输出。
- `(confirmed)` `FollowEnginePort` 启动顺序为 control→vision→output，任一步失败逆序清理；轮询只取 latest-only 事件，不等待 worker；control/vision error、silent exit、局部/内存/全局恢复失败均不伪装成用户停止。组合 stop 最终 unlink shared ring。
- `(verified)` `pytest -q tests/poe2_live_terrain`：`548 passed`；`python -m compileall -q src tests`、`git diff --check` 均通过。当前未启动游戏、未读取实时内存、未连接 Host/LAN、未发送真实手柄。
- `(boundary)` R1 之前仍需用户确认 PoE2 窗口、双人首帧 accepted、Host/controller ownership 和安全位置。离线通过不能证明游戏实际消费 controller 报告；R1 失败时保留日志/evidence，不回退或混跑旧链路。

## 全面审查第 2 轮结果（2026-10-08）

- `(confirmed/P1)` 注入 `AsyncSnapshotOutput.adapter.start()` 异常后，actor diagnostics 已记录失败，但 `FollowEnginePort.active` 仍为真、worker_state 仍 running；没有输出却可能继续显示跟随运行。
- `(confirmed/P1)` 注入慢 Host stop 后，`OutputScheduler.diagnostics()` 被外层锁阻塞约 1906ms；stop/neutralize 仍需把外部 I/O 移到锁外。
- `(confirmed/P1)` global worker 连续失败时，runtime 每 10ms tick 可重复 submit；50ms 观察到 6 次调用，没有失败退避。
- `(confirmed/P1)` 无事件 worker 在 100ms stall 门槛后，每次 120ms poll 都触发同步 rebuild；5 次 poll 得到 5 次 rebuild，没有 supervisor 预算/退避。
- `(confirmed/P1)` 异步页面 start failure 回调只复位 active/UI，不清空 owned adapter/composition；同步失败路径与异步路径不一致。
- `(confirmed/P1)` 高频 visual 可覆盖 target：100 个 visual 后 maxsize=16 队列不再含 target；stop_event 可退出，但 target/execution 无可靠优先级通道。
- `(verified)` `pytest -q tests/poe2_live_terrain`：562 passed in 24.88s；compileall 和 diff check 通过。
- `(boundary)` 本轮没有修改运行源码，也没有启动游戏、读取内存、连接 Host/LAN 或发送真实输入。下一步必须先补失败测试，再逐项最小修复。

## 全面审查第 3 轮：历史运行证据（2026-10-08）

- `(confirmed)` `data/logs/poe2_live_terrain.log` 历史段在 18:08:28 出现 `step=dual_target.output_failed error=host failed`，证明 Host 写失败并非纯注入场景；该段是旧 dual-target/legacy 诊断，不能直接代表新 modular port。
- `(confirmed)` 同一日志在 18:07:46、18:08:04 出现 `live_role_follow.visual_rejected`，innovation 分别约 `895`、`160.527`，`reanchor_after=3`；历史视觉拒绝确实发生过。
- `(confirmed)` 历史日志还出现 `follow_engine.start_failed` 与 `start_cleanup_failed` 多次启动重试；当前没有 `output_actor_start_failed` 的实机段，所以异步 actor 失败仍需离线故障测试覆盖。
- `(boundary)` 最新日志尾部已进入 pytest/session fixture 记录，没有新的模块化实机长跑证据；未把 legacy 日志当作新引擎验收。
- `(verified)` 静态、注入、历史资料三轮审查已完成；本轮未改运行源码，离线回归保持 `562 passed`。下一步是按 P1 顺序补失败测试和最小修复。

### 最终人工执行链审查

1. 首帧 accepted：页面检查 snapshot、transform、reference、instance；seed builder 校验角色和坐标，失败只拒绝本次启动。
2. 启动：页面停旧实验与旧 motion worker，创建 concrete composition；control 先 spawn 并绑定 ring，vision 再 spawn，output scheduler 启动但 6 秒内不建 Host lease。
3. 运行：vision 采集/编码/处理，按 sequence 写 ring；port 将 observation 转给 control；control 融合视觉、预测、局部恢复、暖内存和地图路线，发布 FusionSnapshot。
4. 目标：page adapter 从 leader snapshot 刷新 follower target；点击目标模式则只更新指定 role，动态跟随不会进入一次性 `WAITING_POSITION` 停止语义。
5. 输出：闸门后 SnapshotOutputAdapter 按 intent 懒建 ProgramGamepadOutput，scheduler 写入有界脉冲并持续 heartbeat；session 失效只走 rearm/neutralize。
6. 异常：视觉短失配优先新帧/局部 ROI，预测继续；连续越界才异步暖内存；实例/变换失效才升级全局恢复。任何异常都保持跟随 session，除非用户显式停止。
7. 停止：页面 stop 调 adapter.stop，再由 composition.stop 停 worker、关闭 output、清空状态并 unlink ring；定时器恢复默认周期，旧 worker 不再消费新帧。

### R1 下一步

用户可以开始第一次实际位置测试，但必须先确认游戏窗口和 Host 已在安全状态；建议从“双人静止、角色分离、只观察 6 秒闸门和首帧状态”开始，再进行短距离单方向移动。不要直接做完整地图或窄门测试。

## 全面审查第 2 轮：离线故障注入与资源边界（2026-10-08）

- `(started)` 本轮按第 1 轮发现逐项注入故障：output actor 启动失败、慢 stop/neutralize、worker silent stall/rebuild、global recovery 失败循环、异步页面启动失败重试、命令队列饱和；不启动真实 PoE2、不连接 Host/LAN、不读取实时内存、不发送真实输入。
- `(next)` 每个场景先记录 active/session/output/UI 阻塞/资源释放证据，再决定是否补失败测试和最小修复；禁止把多个根因一次性打包修改。

## 修复批次 A 后最终边界复核（2026-10-08）

- `(confirmed/P1)` `FollowEnginePort._rebuild_components()` 在后台 future 中会先做 active/token 检查，随后无锁写回 `self.vision/control`；stop→start 与旧 future 交错时，迟到的旧代际可能替换新会话句柄。composition 的 rebuild factory 还会直接替换 owner ring/handles，旧句柄只 stop 不 dispose，存在队列/共享内存资源泄漏风险。
- `(confirmed/P1)` `OutputScheduler.apply()` 在读取 `armed` 后释放 scheduler 锁，stop/neutralize 可在其后完成；迟到 apply 仍可能 start/write 已停止 role。heartbeat 对已快照的 port 也存在 stop 后迟到 heartbeat/rearm 窗口。
- `(confirmed/P1)` `GlobalRecoveryBackend` 异常 future 的 `poll()` 使用 monotonic 默认时钟调用 `record_failure()`，而 control tick 的 cooldown/空结果路径传入 epoch `time.time()`；两套时基混用会使异常退避立即失效并高频重试。
- `(verified)` 修复前聚焦专项 35 passed；这些并发边界尚无失败回归。下一步先补三组最小失败测试：旧 rebuild 不能污染新 session 且 stale handles 被 dispose、stop 后 apply/heartbeat 不得写入、异常 global recovery 退避使用同一时基；再逐项实现并跑 PoE2 全套。

## 修复批次 A+：并发与代际边界完成（2026-10-08）

- `(fixed)` `FollowEnginePort` 增加 session epoch/cancel event；worker rebuild 使用 detached `RebuildBundle`，只有 epoch/token 仍有效时才 commit。composition 的 replacement ring/handles 在 commit 后替换，迟到或取消的 bundle 会 dispose；旧 worker 在重建前 stop+dispose，避免 stop→start 后污染新会话。
- `(fixed)` rebuild 的 neutralize 回到 poll 线程，后台 future 不再和 output apply 并发操作；poll 在发送视觉和应用快照前快照当前 handles，并在 output apply 前复核 epoch/handle 身份。
- `(fixed)` `OutputScheduler` 对 apply 的 armed/stopping/port 身份二次校验，heartbeat 丢弃 stop 后 stale port，stop 按角色 claim 后在角色锁内做外部 I/O；慢角色不会持有全局 scheduler 锁，也不会被迟到 apply 重启。
- `(fixed)` `GlobalRecoveryBackend.poll(token, now_ms=...)` 同时校验 generation/map instance；control tick 传入统一时间戳，异常/空结果退避不会因 monotonic 与 epoch 混用而立即失效。
- `(fixed)` stop command 进入 control worker 后立即清空 pending batch，且 stop_event 在 tick 前再次检查；priority 队列满时不再任意淘汰生命周期/恢复/执行命令。
- `(verified)` 新增竞态/时钟/代际失败回归后，聚焦 34 passed；补充 map instance 回灌回归后，PoE2 专项为 `575 passed`；`compileall`、`git diff --check` 通过。全仓此前 `1269 passed, 2 skipped, 1 failed`，唯一失败为环境缺少 `pydirectinput` 的 distribution 测试（`PackageNotFoundError`），与本批代码无关。
- `(boundary)` 未启动真实 PoE2、未连接 Host/LAN、未读取实时内存、未发送真实手柄输入；离线代际、锁和退避回归不等于游戏消费输入验收。
- `(next exact)` 用户授权实机前，先重启工作台，按 acceptance 文档执行 R1 静止双人首帧→6 秒闸门→短距离单方向；保留 `follow_engine`、output actor、worker rebuild 和 recovery timing 日志。若出现异常，先保留日志/evidence，不直接调阈值。

### 最终静态收尾（2026-10-08）

- `(verified)` 最终 PoE2 专项：`575 passed in 36.12s`；聚焦并发/代际/恢复/队列：`35 passed in 8.41s`；`python -m compileall -q src tests` 与 `git diff --check` 通过。
- `(verified)` `tools/debug/follow_lifecycle_audit_probe.py` 七场景均在 watchdog 内结束；heartbeat contention `0.02ms`，失败组合无遗留 ring，输出清理逐角色完成，arm delay 期间预测位置保持零位移。
- `(boundary)` 全仓上一轮 `1269 passed, 2 skipped, 1 failed`，唯一失败为当前 Python 环境缺少 `pydirectinput` distribution；本批不改依赖。工作树包含历史用户运行 evidence 和前序修改，未 reset/删除。
- `(status)` 本批离线修复和文档同步完成，可以进入用户授权的 R1 实机位置测试；没有真实输入、Host、LAN、内存或游戏消费证据，因此不宣称实机完成。

## 最新跟随滞后会话只读调查（2026-10-08 20:55）

- `(confirmed)` 旧双人视觉在 `20:55:19.136` 启动，`20:55:20.568` 已完成第 30 帧，识别两名角色均可见，处理 EMA 约 31–35ms、有效帧率约 21.8FPS，首帧/旧视觉链没有出现初始识别积压。
- `(confirmed)` 用户在 `20:55:27.748` 切换模块化跟随；control 启动耗时 `699.192ms`，vision `73.178ms`，总启动 `774.342ms`，`20:55:28.525` 开始 UI 轮询。
- `(confirmed)` 模块化组合默认 `arm_delay_ms=6000`（`follow_engine_page_composition.py:104`）。Host 日志中 controller=2 第一条 `ViGEm SubmitReport` 是 `20:55:36.940`，距接管 `9.192s`；约 6 秒是显式闸门，剩余约 3.2 秒属于首个控制快照/输出 actor/调度链路，现有日志无法继续拆分。
- `(confirmed/P1)` `20:55:35.559` 首次轮询异常为 `VisionProcessHandle.events` 已关闭（`ValueError: Queue ... is closed`），随后每约 33–50ms 重复到 `20:55:43.011`。页面 timer 没有停止，持续轮询已 dispose 的 queue，形成异常风暴和额外 UI/日志开销。
- `(confirmed)` 同一窗口没有正常 snapshot/receipt 日志，但 Host 在 `20:55:36.940–20:55:59.993` 仍收到 controller=2 报告（787 条 `SubmitReport` 及对应提交记录），说明输出报告与视觉生命周期已分裂。
- `(high-confidence hypothesis)` 页面隐藏/停止使用异步 lifecycle executor；旧 stop action 可能在新 start action 后迟到完成，或已关闭 adapter/composition 被复用。`_submit_modular_lifecycle` 的 serial 只能丢弃完成回调，不能取消已经运行的旧 cleanup；`_ensure_modular_follow_adapter` 在 adapter 非空时直接复用。若旧 cleanup 在新会话启动后调用 `FollowEngineComposition.stop()`，会关闭新会话使用的 vision queue，符合本次时序。当前还缺 lifecycle serial、composition identity、queue owner 和 dispose 调用点日志，暂不把假设写成最终根因。
- `(separate confirmed issue)` `runtime.log`/Host 日志存在 controller=2 长期 `Unknown program command` heartbeat 失败及 session expired（失败计数超过 5000）；这是输出会话健康问题，必须和 vision queue 生命周期分开处理。本时间窗没有带时间戳 Host diagnostics，不能证明它是本次延迟的第一触发点。

### 当前结论与下一步

- 这次 P1 先跑、P2 后行动的可量化部分是 6 秒显式输出闸门加首个控制快照链路约 3.2 秒；更严重的并发缺陷是旧/新 composition 生命周期可能交叉，导致新 vision queue 被关闭，视觉纠偏随后失效。
- 下一步先做离线失败回归：`start(A) → async stop(A) 未完成 → start(B) → late stop(A)`，断言 B 的 queue、process、output lease 不被 A dispose；同时增加 lifecycle serial、composition id、queue state、首个 snapshot、首个 output receipt 的时间埋点。确认失败用例后再实施单根因修复。

## 最新一次跟随滞后复核与修复批次（2026-10-08）

- `(confirmed)` 20:55 会话中旧双人视觉在 `20:55:27.433` 仍正常；模块化接管完成于 `20:55:28.524`。从 `20:55:35.559` 起页面连续轮询已关闭的 `VisionProcessHandle.events`，没有任何模块化 snapshot/receipt/target 日志；这不是视觉处理慢，而是会话资源已经被 dispose 后仍被轮询。
- `(confirmed)` Host 的 P2 首个 `SubmitReport` 为 `20:55:36.940`，晚于模块化启动 8.416 秒，且发生在 queue closed 之后，当前缺少 generation/session/receipt 关联，不能把它当作当前有效模块化会话的首写；P1 controller=1 在 `20:55:33.226` 已有输入，表面上形成 P1 先跑、P2 后动。
- `(confirmed)` 模块化组合默认 `arm_delay_ms=6000`；该延迟是实际输出闸门，会让控制/预测先运行而 Host lease 延后。它解释至少 6 秒滞后，但不能解释 queue closed；两者必须分别处理。
- `(root cause)` 启动入口先调用异步 `stop_follow_experiment`，随后 `_ensure_modular_follow_adapter` 看到非空 adapter 直接复用已进入 stop/dispose 的 composition；同一个 lifecycle executor 随后先关闭旧 queue，再对已 dispose 的 `VisionProcessHandle` 重新 start。`_submit_modular_lifecycle` 的 serial 只丢弃完成回调，不能阻止资源复用。
- `(repair plan)` 先补两个失败回归：启动请求遇到 stop pending 时必须延后构造/启动并在 stop 完成后新建 composition；vision/control queue closed 必须被 engine 分类为可恢复 worker fault，不得冒泡到 Qt timer 形成异常风暴。修复后再补首个 snapshot、target update、output intent、Host receipt 的阶段日志，拆解 6 秒之外的额外延迟。

## 当前有效结论（2026-10-09，最终续读位置）

### 2026-10-09 最新用户实测复核：P2 越过 P1 与 Vision 子进程退出

- `(evidence)` 当前 `data/logs/poe2_live_terrain.log` 可见会话 `03:44:02` 首帧 accepted；`03:44:03.302` 双人运动启动，随后旧 dual-motion 视觉链在 120 帧内均识别两角色，处理 EMA 约 26–33ms、effective FPS 约 20–22。
- `(confirmed)` `03:44:08.916` 发生 `dual_motion`→modular takeover，`03:44:09.461` 新 composition 启动完成；10 秒 focus gate 在 `03:44:19.494` 结束。该阶段没有记录 P2 实际游戏位移或 Host 消费证据，不能把输出报告当成角色已移动。
- `(confirmed)` `03:44:21.744` Vision 子进程因 `ValueError: wall_quality must be <= 1` 退出，之后 parent 每约 47ms 重复 `worker_stall_evidence`，Vision progress age 达 7.6s，Control 仍运行；这会使后续定位纠偏失效并放大预测漂移。该日志对应修复前/旧运行产物，需用重启后的新日志确认归一化修复已加载。
- `(source-confirmed)` 新版 Control 已装配 `LegacyDynamicFollowRouteController`，但其动态配置仍把 `self.magnitude=1.0`、`duration_ms=80` 直接交给 `LocalMotionController` 的 vector；需对照 `a3070ea` 的实际输出脉冲与 magnitude 语义，确认没有把 native 距离向量再次当作单位摇杆输入。新版只改变定位来源的前提尚未被动作序列证据证明。
- `(source-confirmed)` P2 越过 P1 的第一优先排查点是 target/role/output 关联：Control 的 `live_target_source` 以角色 identity 绑定，controller 映射由页面选择生成；必须从同一 generation 逐 tick 关联 `leader accepted position → follower target → route decision → OutputIntent(role/controller/vector,duration) → receipt`。当前日志只记录了 Vision/worker 状态，缺少这条完整证据，不能把越过归因到单一算法。
- `(boundary)` 本轮只做日志和源码对照，未启动游戏、未读取内存、未连接 Host/LAN、未发送输入，也未修改运行代码。
- `(next exact)` 对照 `a3070ea` 的旧 `LocalMotionController/VectorPathTracker` 输出契约，补离线回归：相同 position/target/route 输入下，旧版与适配器的 vector、duration、arrival/hold、角色/controller 映射必须一致；同时增加 P2 overshoot 关联日志和 Vision fault 修复后 fresh-process 验证。

### 2026-10-09 离线 replay 实施批次

- `(implemented)` 新增 `tests/poe2_live_terrain/test_follow_engine_replay_contracts.py`：直接驱动 `FollowControlRuntime`、`RecoveryPolicy`、`LocalRecoveryBackend` 和 `MemoryRecoveryBackend`，覆盖视觉失配→下一帧局部 ROI、captured_at receipt rewind/replay、连续 local miss→memory 单飞/cooldown、坏 generation/重复 receipt。
- `(verified-offline)` 新 replay 6 项通过。local replay 断言首帧 rotation/scale 与当前帧 transform 一起绑定到 search；成功后 source=`local_roi`、miss 清零、session 保持 active；memory 场景确认不会在下一 tick 重复读取。
- `(implemented-boundary)` 新增真实 `spawn` + `multiprocessing.Queue` fixture：父侧暂停约 3 秒时 child 仍持续推进序列；child 主动停止后父侧可观察到终止。该 fixture 证明 child health 与 parent drain 可分别观察，但不冒充 Qt 端到端 relay 已解耦；当前最小 relay ownership 改造仍开放。
- `(implemented)` J02 新增 `LegacyDynamicFollowRouteController` contract invariant 测试：arrival=12 返回 neutral/0ms，非 arrival 使用 80ms、旧组件 route、bounded vector，并断言 expected_speed=80；由于当前进程不能导入独立旧 checkout，证据等级仍为 contract_equivalent，不是 byte replay。
- `(boundary)` 本批没有修改旧 PathFinder/VectorPathTracker/LocalMotionController、动态参数或真实输入链；没有游戏/Host/内存证据。

### 2026-10-09 J04/J05 RelayLoop 实施

- `(implemented)` 新增 `follow_engine/relay.py::RelayLoop`。`FollowEnginePort.start()` 为当前 `session_epoch` 启动独立 relay thread；relay 调用内部 `_poll_once()` 持续 drain Vision/Control/receipt 并执行 Output，UI `poll()` 现在只返回最新 snapshot，不再作为 worker transport clock。
- `(lifecycle)` `FollowEnginePort.stop()` 与 output failure deactivation 先停止 relay，再停止 Vision/Control/Output；relay 由 epoch 绑定，旧 session 不会继续驱动新 session。
- `(verified-offline)` 新增端到端 fake-port relay test：故意不调用 UI `poll()` 约 3 秒，Control tick 与 Output apply 仍各自前进 100+ 次，恢复 poll 后可见最新 snapshot；replay/process 集合 7 passed，组合 focused 集合 42 passed。
- `(boundary)` 当前 relay test 使用 spawn-safe fake ports，证明父侧 UI pause 不再阻塞 port 内部 relay；真实 Qt、Host、游戏消费以及 child 真停后的自动 rebuild 仍未验收。worker stall/rebuild 仍需下一批补真实 process handle 场景。

### 2026-10-09 Relay 竞态修复

- `(fixed)` `_poll_once()` 现在是唯一非重入入口，使用 `_poll_lock` 串行化 relay 与兼容调用；UI `poll()` 首次读取只等待 `_snapshot_event`，不再并发消费 worker 队列。
- `(verified-offline)` 增加 8 个并发 UI reader 与 relay 同时运行的测试，断言 producer tick 单调、每个 snapshot 只由 relay 应用一次、无 relay_error；port/replay focused `26 passed`，compileall/diff-check 通过。
- `(boundary)` stop 不等待 UI reader；旧 relay 仍由 session epoch/active 检查阻止写新代。真实 child rebuild、Qt/Host/game 消费仍未验证。

### 2026-10-09 测试收尾时序修正

- `(fixed-test)` 并发 reader 测试不再要求 reader 观察到 relay 最后一个 tick；停止前记录 `produced_ticks`，断言 `max(seen) <= produced_ticks`，并保留 `output.applies == control.tick` 与无 relay_error 约束。
- `(verified-offline)` 该竞态测试连续独立运行 5 次全部通过；port/replay 集合 26 passed，compileall/diff-check 通过。运行代码未再修改。

### 2026-10-09 J10 统一跟随契约

- `(inventory)` 模块化动态跟随、single program、双人 program 入口走 `FollowEnginePort → LegacyDynamicFollowRouteController → SnapshotOutputAdapter/OutputScheduler`；leader target 由 accepted observation 在 Control 内更新，click target 走同一 `update_target` 接口。
- `(inventory)` 旧 click-to-move/program probe 与双人同目标入口仍使用 `SimulatedFollowRuntime`，但其 route 链仍是 `PathFinder → VectorPathTracker → LocalMotionController → ProgramFollowOutput`；它们不是模块化 FollowEnginePort，属于兼容旧页面路径。
- `(implemented)` 新增 `experimental/follow_contract.py::DYNAMIC_FOLLOW_CONTRACT`，click、single、dual target 和 dynamic composition 共用 `12/20/80/8/24/.25` 契约；没有复制或修改 steering/避障/脉冲算法。
- `(verified-offline)` 新增契约常量测试；legacy adapter、page composition、replay focused `14 passed`，compileall/diff-check 通过。角色互换和每角色状态隔离由现有 adapter fixture 覆盖。
- `(boundary)` 旧页面路径尚未迁移到 FollowEnginePort；真实 Qt/Host/game 消费与完整角色互换实机仍未验收。
- `(review)` 现有 `test_worker_stall_rebuild_is_async_and_budgeted`、`test_rebuild_bundle_commit_is_atomic_and_retire_old_handles`、`test_stale_rebuild_future_isolated_from_stop_restart_session` 已覆盖真实 `FollowEnginePort` rebuild future/old handle 交接；本批没有把裸 Queue fixture 冒充 child-handle 验收。真实 PoE2 child/Host/Qt 仍未验收。

上面 2026-10-08 的 queue/lifecycle 内容是历史根因和修复前证据；当前实现已完成其离线修复，并额外完成 transform handover。以本节及 `docs/POE2_FOLLOW_RUNTIME_CHAIN_AUDIT_20261009.md` 为准：Control 拥有正式动态 target，Vision/Control/Output 代际隔离，rebuild 继承最新 native 位置与当前 transform，最终专项回归 600 passed。未完成的是授权后的真实 PoE2 消费、窗口焦点/controller ownership、33ms 预算实测和地图滚动重建连续性；不得将离线结果表述为实机已验收。

### 续读发现：正常运行的 ROI 变换与恢复目标还未闭环

- `(confirmed)` `FollowControlRuntime.apply_visual()` 保存 observation，但未将每帧 transform 交给 `EncodedMarkerRoiSearch`；后者仍使用创建/rebuild 时变换。地图滚动后 ROI 可搜索错误区域并回填错误 native 坐标。重建交接通过不能证明正常运行每帧交接正确。
- `(confirmed)` `_resolve_frame()` 在 exact ring slot 被覆盖时取更新的 frame，但 observation.transform 仍属于旧帧，二者不能混用。
- `(confirmed)` `_apply_recovery_positions()` 只改 source role 状态，未更新 follower target；leader 经 local/memory 恢复后，follower 仍追旧目标，直到下一次正常视觉接受。
- `(doc-conflict)` 文档中“Vision 直接到 Control”“闸门结束才建租约”不准确：事件仍由父侧 poll 转发；闸门内 prime_neutral 已建立零输入租约。恢复阈值须记录策略分支优先级，不能只列常量。
- `(next)` 用离线定向场景验证同帧 transform/图像绑定、过期 slot 跳过局部搜索但保持 session、恢复 source 更新 target；修复并同步当前链路文档。不重复全量回归。

- `(verified/fixed)` 续读定向实验先复现 8 项失败：平移场景将应为 `(130,70)` 的坐标错填 `(30,40)` 且报告 local success；过期 slot 配到了另一帧；三类 recovery 在正反 leader 配置下均未刷新目标。已修复每帧 `bind_observation`、exact frame/时间戳绑定、统一 `_refresh_live_target`。新增场景与直接相关 runtime/vision 检查共 `28 passed in 0.55s`，没有重跑全量。
- `(history)` read_thread 找到当前聊天 `poe2跟随脚本 (2)` 的 2026-10-07 17:21:19（北京时间）turn `01a115aa-d30d-7bc0-a552-451dcad07eda`，但返回 `items=[]`；可恢复该轮时间/状态，不能声称找到了其完整正文。18:32 的完成消息明确当时只是离线引擎，页面与真实输出尚未接入。本文结合这部分可见历史与仓库断点，不补造缺失对话。

### 当前最终续读位置（本次补查后）

### 2026-10-09 19:16+ 方案与日志覆盖审查（本轮不改代码）

- `(confirmed-source)` 19:16 后提出的核心识别方案已落在源码：Vision 每帧同时处理双角色；`MarkerAssociator` 有动态 gate、单候选两帧确认、多候选按预测距离、48 px² 大面积干扰过滤；`DualObservationProcessor` 将 association diagnostics 与 StageTiming 放入 observation。
- `(confirmed-source)` Control 已记录每角色的 target、position/source/uncertainty、visual_position、latest/accepted sequence、misses、intent vector/duration/neutral、recovery decision、local/recovery/route/total timing；local ROI 与同帧可见候选冲突会打印 `step=follow_engine.local_recovery_rejected`，不会清除 miss/uncertainty 或刷新 target。
- `(confirmed-source)` 生命周期与输出日志已覆盖 generation、PID、start/stop/forced、queue/ring close、parent poll gap、child progress age、rebuild timing、Host acquired/session_expired/heartbeat/rearm、Output apply/receipt timing；Vision child 低频打印 `vision_child_progress`，Control child 低频打印 `control_child_progress`/`control_decision`，父 relay 打印 `control_decision_observed`。
- `(confirmed-gap)` 关键日志仍不是完整端到端证据：`control_decision_observed` 可看到 intent 与融合状态，但没有把单个 target sequence → control tick → OutputIntent → ExecutionReceipt → Host receipt/game 位移绑定成同一条可检索事件；Host receipt 也不能证明游戏实际消费。`vision_child_progress` 的 association 字段只有在真实 child logger 汇聚到 terrain 日志时才可用，当前尚无 19:16 后实机日志验证。
- `(confirmed-gap)` 当前 `data/logs/poe2_live_terrain.log` 可用最新运行仍止于 2026-10-09 18:39:24 的旧会话；19:16 后新增实现没有实机日志证据。因此不能把源码埋点等同于本轮真实日志已打印。
- `(regression-found)` 焦点回归 `91 passed, 1 failed`：`tests/poe2_live_terrain/test_follow_engine_page_startup.py::test_modular_countdown_is_not_hidden_by_control_snapshot` 因 `_poll_modular_follow_engine()` 无条件调用 `_render_modular_follow_frame()`，而旧/轻量 page double 没有该方法，返回 `modular_poll_failed`，倒计时断言失败。该失败说明 UI preview bridge 改动破坏了既有轮询调用契约，需修复或明确更新 fixture 后才能宣称焦点回归全绿。
- `(boundary)` 本轮只读审查、运行焦点测试；没有启动 PoE2/Host、读取内存、发送真实手柄或修改运行算法。下一步应先修复/验证 UI bridge 兼容性，再做一次新 generation 的实机日志采集，重点核对 `single_candidate_*`、`local_recovery_rejected`、`control_decision_observed`、`ExecutionReceipt` 和 Host 状态是否同 session 出现。

### 用户请求重启工作台（2026-10-09）

- `(authorized)` 用户明确要求重启程序，仅重启本项目工作台，不自动开始跟随实验。
- `(observed)` 初次进程枚举没有找到工作台 main.py/AutoModules 进程；发现Serena、语言服务和旧pytest，均不作为工作台关闭目标。
- `(next)` 核对main.py启动链和现存窗口，用README指定解释器启动，并检查新PID、窗口和启动日志；记录是否产生UAC请求。
- `(completed)` 用 `D:/ACloud/.venv/Scripts/python.exe main.py` 发起启动，UAC已成功；实际GUI PID `38484`（pythonw），窗口 `auto_modules · 实时小地图拼接系统`、Responding=True。runtime.log当前session记录Admin=True与“主窗口已启动”。未发现旧工作台所以无需强制终止；未关闭Serena/语言服务/pytest。用户可手动进入PoE2页面测试，未自动开始跟随。

### 2026-10-09 03:07–03:08 两次失败测试：只读诊断

### 后续请求：10秒测试闸门与Git差异溯源

- `(request)` 用户要求确认10秒冷启动等待、人工逐段推导运行链，并利用Git成功版本/修改记录查退化来源。可以修明确的10秒等待/UI提示缺口；不发真实输入，不自动重启或跟随。
- `(next exact)` 对照a3070ea与当前未提交修改，精读页面异步启动、snapshot输出闸门、engine poll/watchdog与Control恢复分支；已确认的日志缺口和worker重建不是最终根因。离线模拟真实DTO/时序，不以全量回归代替推导。

- `(reproduced)` 两个新离线场景均失败：parent暂停3秒但两个队列已有结果，poll仍先写worker_stall:vision,control；completed rebuild更换句柄后poll仍读先前捕获的旧句柄，返回None。测试test_follow_poll_order_regression.py，2 failed。实际03:07会话首因仍缺日志，不能把复现等同于实机因果证明。
- `(confirmed/git)` a3070ea保留6秒旧闸门；当前新增模块化路径仍6秒，但async start提示下一次poll被snapshot状态覆盖。HEAD→工作树engine从轻量poll新增watchdog/rebuild，错误执行顺序发生在这批尚未提交修改，不能归因到一个已提交SHA。
- `(next exact)` 修poll顺序：先收集完成重建，捕获有效句柄，重建期间不读被关闭队列，读取结果后再检查stall；补原始worker错误/重建状态日志。统一10秒闸门并持续UI倒计时。只验证相关场景。

- `(reproduced/fixed)` 追加第三个失败场景：Control首结果提前使Vision启动门从10s变成2s；修为每worker独立ready状态。三处明确时序缺陷已修：collect-before-handle、drain-before-watchdog、rebuild pending不轮询退休queue；正常数据/启动/重建分别更新ready。
- `(fixed)` 页面常量与factory默认10,000ms，页面显式传入同一delay；异步/同步启动都设置持续倒计时，fault状态优先于旧snapshot。输出侧真实闸门保持，9999ms禁止非零输出/位移receipt，10000ms放行；不使用阻塞sleep。
- `(fixed/observability)` worker error原文、traceback、PID/exitcode/epoch落盘并保留first_fault，后续stall不丢原始原因；stall记录每worker年龄/门限，重建begin/completed记录attempt/epoch/身份；正常状态与按秒倒计时采样，避免30Hz异常日志刷屏。
- `(verified)` 相关时序/page启动/output边界/port/composition合计38 passed in4.91s，py_compile和限定文件diff-check通过。源码三处缺陷已验证，但两次实机最初故障仍无历史调用栈，不宣称完全实机修好；运行中的GUI尚需重启加载，本轮未重启/输入/读内存。
- `(docs/next)` CODEBASE与当前链路文档已同步；Git对照和修后时序见docs/POE2_FOLLOW_GIT_REGRESSION_AND_STARTUP_20261009.md。下一步实测必须用新日志同session关联first_fault→stall→rebuild与实际输出；不重复定位/阈值猜测。用户若要求重启，仅重启工作台，不自动开始跟随。

- `(request)` 用户要求先看最近两次测试日志，解释发生了什么；本轮不修改运行代码，不发真实输入。
- `(observed)` 双人首帧03:07:45 accepted，score=0.9099，误差0.3407native；接管前旧实时视觉约21.8–22.1FPS且两角色可见。新会话一03:07:53.211启动，03:07:57.714/03:08:00.994/03:08:07.791依次dispose/rebuild Vision，03:08:21结束。会话二03:08:31.879启动，03:08:40.308又dispose/rebuild，03:08:45结束。
- `(next)` 沿engine worker fault/rebuild触发路径查明dispose原因，查找此次session的output/receipt/worker error与诊断文件。runtime.log旧5100次heartbeat错误在新session之前，不能当作本次故障证据。记录明确证据与缺失日志边界。

- `(confirmed/log-gap)` engine.poll收到Vision/Control error事件只写内存last_error，未持久记录event.traceback_text；_check_worker_stall在首snapshot后采用2秒无进展门，覆盖last_error并重建两个worker。正常rebuild也未记录原因/进展年龄/exitcode。因此Vision dispose不能证明Vision是起因，当前两次故障的原始异常尚不可恢复。
- `(confirmed/timing)` 会话一首snapshot约188ms、首vision约563ms，随后三轮rebuild；会话二首snapshot约140ms、首vision约515ms，随后一轮rebuild。first_output_apply只证明提交actor，不能证明非零Host写入/游戏移动。
- `(boundary)` 尚未找到这两次会话的异常截图；occlusion_diagnostics最后更新10月7日，latest.json/npz为9月旧数据。调查期间有新GUI/测试活动，不干预，仍锁定03:07与03:08两次会话。
- `(next exact)` 核对页面state callback是否只显示last_error而未落盘；补查这两次runtime/Host日志。报告确定的启动→进展中断→输出neutralize→重建链，与无法确认的首个worker故障分开。本轮不改运行代码。

- `(confirmed/output)` Host限定时窗统计：第一次P2非零SubmitReport=0；第二次157条，03:08:37.883至03:08:40.353（完成40.354），约2.47秒，backendConnected=True；六秒闸门后实际有输出，随worker重建中断。Host源码仅打印非零buttons/left axes，因此不能把缺记录解释为没有零输入/lease。
- `(confirmed/UI)` 页面poll有snapshot时优先展示其recovery状态，仅无snapshot时展示last_error；last_error/worker trace未落盘。三轮重建已用满默认max_attempts=3，后续若再stall可预算耗尽，但此次没有记录该分支，不声明其发生。
- `(completed diagnosis)` 诊断报告为docs/POE2_FOLLOW_FAILED_RUNS_20261009_0307.md。准确根因尚未确定：首个异常/停滞worker缺持久证据。确定的是运行阶段worker watchdog→回中→两worker重建循环，并非首帧失败。本轮仅新增/维护文档，不改运行代码。
- `(next exact)` 如用户要求修复，先补状态改变级first_fault/traceback、worker进展年龄与阶段、rebuild原因、Host receipt关联日志；常态耗时抽样。然后区分子进程异常/长计算/IPC或parent relay停滞，不直接调定位阈值、不复用旧session错误。

- `(verified)` 加入旧sequence/显式frame错配检查和组合边界后，直接相关检查最终 `35 passed in 1.53s`。修改文件py_compile通过；不以历史600项结果代表本次代码。
- `(confirmed-boundary)` 当前concrete factory未装配GlobalRecoveryBackend，local ROI是marker搜索，不是完整墙体几何注册；文档已明确区分能力与实际装配。visual事件仍经parent poll；仅移除了旧snapshot-to-target反馈环。33ms为目标周期，不是已验证吞吐。
- `(docs)` 最终报告 `docs/POE2_FOLLOW_RUNTIME_CHAIN_AUDIT_20261009.md` 含历史可见性、重构对照、结构、精确策略顺序、手工时序、参数、日志耗时口径和未验证边界；时序/生命周期草稿、CODEBASE、迭代记录同步。旧CURRENT/MANUAL文档置顶标记为历史材料。
- `(next exact)` 用户测试前重启以加载当前源码；之后按同一generation/sequence关联Vision→parent relay→Control→Output→receipt，检查首次非零输出、地图滚动ROI、leader失配恢复后的target变化。尚无修改后真实P2位移/30FPS证明，不自动启动游戏、Host、内存或输入。不要再重复已经完成的cadence、epoch、target下沉和transform交接修复。
## 2026-10-09 J07 delayed observation correction

- `(implemented)` `FollowControlRuntime.apply_visual()` now rewinds accepted execution receipt segments occurring after the observation's `captured_at_ms` before fusion; subsequent tick replay advances them once to now. This prevents delayed visual observations from double-integrating command motion.
- `(verified-offline)` Added delayed visual/receipt replay test plus existing duplicate/wrong-generation checks; control focused `13 passed`, compileall passed.
- `(remaining)` Full transform rejection and next-frame local ROI success/recovery sequence still needs replay coverage; J02 remains fixture-level rather than separate-checkout equivalence.
## 2026-10-09 J07 final boundary evidence

- `(verified-offline)` Added mismatched frame metadata test: wrong sequence/generation/map/timestamp resolves to no local frame and cannot feed local recovery. Combined control/adapter focused batch `17 passed`, compileall passed.
- `(verified-source)` Local ROI matcher already uses the fused predicted native point and current bound observation transform; accepted local recovery clears role misses through `_apply_recovery_positions`; recovery policy schedules local before memory. Full degraded→next-frame-local→memory escalation replay remains not fully covered.
- `(J02 status)` LegacyDynamicFollowRouteController directly calls existing PathFinder, VectorPathTracker and LocalMotionController with dynamic config. Six-scenario fixture is `contract_equivalent`; no separate checkout byte replay is available in-process.

### Remaining checklist status

- J01 fixed/offline verified; real Vision recurrence unverified.
- J02 contract-equivalent fixture verified; old checkout byte replay and real game unverified.
- J03 root cause evidence/overshoot strategy correction incomplete.
- J04 parent poll relay decoupling open.
- J05 child heartbeat/watchdog semantics partially instrumented; real pause test open.
- J06 worker/epoch/signature suppression and valid-observation clearing fixed offline; repair end-to-end unverified.
- J07 delayed captured-at rewind and duplicate/generation gates verified offline; full local-first escalation open.
- J08 transform handover/exact slot offline fixed; map-scroll runtime open.
- J09 lifecycle owner/rebuild protections offline; real handover open.
- J10 unified target/runtime contract incomplete for all modes.
- J11 queue/recovery budget evidence partial; real p95 open.
- J12 diagnostics improved; runtime metric validation open.
- J13 Host heartbeat/rearm offline; Host/game consumption open.
- J14 local-first/memory cooldown source exists; escalation replay open.
- J15 hold/cold-start semantics offline; real 10s gate open.
- J16 concurrency choice not finalized; requires measured IPC/GIL/runtime data.
## 2026-10-09 J04/J05 evidence boundary

- `(implemented)` `FollowEnginePort.diagnostics()` now exposes parent poll count/gap, child progress age, ready state, last consumed Vision sequence/Control tick, and an explicit note that current IPC age is parent-consumption age.
- `(boundary)` This separates parent scheduling evidence from child business progress in diagnostics, but does not yet remove Vision→Control/Output→receipt relay from parent poll. A true Qt pause end-to-end test remains open.
- `(verified-offline)` Port focused suite `18 passed`, compileall passed. No real Qt/Host/game evidence.
\n+## 2026-10-09 latest run audit: P2 overshoot and old/new strategy divergence
\n+- `(confirmed-source)` Current `LegacyDynamicFollowRouteController` is only a thin adapter: it calls `PathFinder`, `VectorPathTracker`, and `LocalMotionController`, but hard-codes `duration_ms=80`, `magnitude=1.0`, `arrival_radius=12`, `clearance_radius=20`, and does not carry the old runtime's contact/recovery/progress state machine. The old runtime's command duration was elapsed control time when no closed-loop controller was present, and its route decision included local contact, stalled-route, recovery probes, and per-follower state. Therefore the refactor changed the movement/output contract even though it reused class names.
- `(confirmed-source)` New control integrates each `ExecutionReceipt.valid_for_ms` using a fixed/calibrated speed and emits another pulse from the predicted position. A receipt proves transport acceptance only, not game movement. If the Host/game consumes a pulse late or at a different speed, predicted P2 can advance ahead of its visual position; this can generate a direction/arrival decision that drives P2 past the leader. The current architecture has no hard cap tying target-follow pulse duration to the measured control cadence.
- `(confirmed-source)` Dynamic leader target refresh is now inside `FollowControlRuntime.apply_visual`, but the actual target may still be delayed by the Vision→Control queue and visual acceptance gate. The parent relay is no longer the intended writer, yet the follower route is evaluated against the latest accepted source position only; if source frames are rejected or stale, the follower continues toward the last accepted target while command odometry advances.
- `(boundary)` The latest `poe2_live_terrain.log` in the workspace ends at the historical 03:45 session and contains no new user-run evidence. The following conclusions are source-confirmed, not real-game consumption proof. No game/Host/memory/input was started in this audit.
- `(root-cause hypothesis, requires focused replay)` The most likely direct cause of “P2 triggers once, runs far past P1” is the changed pulse contract: fixed 80 ms full-magnitude intents plus receipt-based prediction, combined with incomplete legacy contact/arrival state. It is not safe to fix by tuning visual confidence first.
- `(next exact)` Build an offline old/new action-sequence replay using identical positions, moving targets, turn/door and delayed-visual cases. Assert vector magnitude, duration, arrival hold, target refresh, and predicted displacement equivalence before changing runtime behavior. Then restore the old motion strategy behind a process-safe adapter, leaving only localization evidence/fusion in the new Control process.
- `(implemented)` `LegacyDynamicFollowRouteController` now delegates to the complete existing `SimulatedFollowRuntime` instead of duplicating only PathFinder/VectorPathTracker/LocalMotionController calls. The legacy runtime owns per-role route, pulse, arrival/continuous-follow hold, progress, contact, wall/door recovery, and target refresh state.
- `(removed)` The adapter no longer forces an 80 ms pulse or 1.0 magnitude. It returns the legacy runtime's per-tick vector and `command_duration_ms`; process Control passes the fused position source and control timestamp into the adapter.
- `(verified-offline)` Updated adapter contract tests and ran route/control/page focused suite: `19 passed`. This proves the adapter no longer has the fixed-pulse behavior and nearby continuous-follow is a non-terminal hold with neutral output. It does not prove game input consumption.
- `(remaining)` A complete old-checkout byte-for-byte replay is still unavailable because the historical checkout is not importable as a second package in-process. The current legacy runtime file is unchanged and is the reference implementation; add a scenario matrix for leader movement, turns, doors, no-progress, and visual miss/prediction before claiming J02/J03 complete.
- `(boundary)` No game, Host, memory, network, or real controller input was started.
- `(replay)` Added an equal-input adapter/reference replay covering nearby hold, leader movement, turn, long corridor and command-prediction position. Each tick compares vector, duration, arrival classification and recovery reason against a direct `SimulatedFollowRuntime` instance; adapter test file now reports `4 passed`.
- `(fixed-contract-test)` Updated the remaining J02/J10 fixture in `test_follow_engine_replay_contracts.py`: nearby continuous follow is `follow_hold_within_radius` with neutral output and session retained; duration is bounded by the supplied tick and compared to the legacy runtime, never fixed at 80ms. Added leader move→pulse→return-to-hold assertions.
- `(verified-offline)` Independent replay/port collection: `65 passed, 572 deselected`. No implementation difference was found after the contract correction; only stale fixed-arrival/fixed-duration assertions remained.
- `(J11/J12 implemented-offline)` Added bounded monotonic timing windows and diagnostics for Vision processing, Control ticks, Relay entry gap/duration, Output apply/heartbeat, receipt age, and latest-only frame queue depth/drop/age. Relay now exposes separate `entry_gap_ms` and `relay_duration_ms` while retaining compatibility aliases.
- `(J11/J12 verified-offline)` Fixed fixture benchmark reports p50/p95/max for control timing and queue age/drop; replay/output/vision collection `34 passed`. These are offline measurements only and do not prove real 25–30Hz, Host consumption, or game performance.
- `(remaining)` Recovery and rebuild durations still need to be surfaced from their backend/engine diagnostics with the same percentile window; current snapshots retain per-tick `memory_ms/global_ms` and lifecycle counters, but no aggregate recovery/rebuild p95 yet.
- `(J11/J12 completed-offline)` Added bounded aggregate timing for local ROI, memory backend, global backend, whole recovery chain, and rebuild attempt/commit/retire. Backend durations come from backend result timing; child progress/heartbeat is not treated as recovery completion.
- `(verified-offline)` Recovery/control/output/vision focused set passed `52` tests after timing additions; one pre-existing relay scheduling test (`test_delayed_parent_poll_consumes_queued_progress_before_stall`) remains sensitive to the asynchronous relay consuming its fixture before the direct poll assertion. No behavior or strategy change was made for that unrelated boundary.
- `(boundary)` Recovery timing windows sample only completed backend results, so cooldown/single-flight behavior is unchanged and timing collection does not block the control tick. Real recovery/rebuild p95 remains unverified.
- `(fixed-test-contract)` `test_delayed_parent_poll_consumes_queued_progress_before_stall` now treats RelayLoop as the only worker-queue consumer. It waits for relay-owned snapshot publication, then asserts UI poll is read-only, worker states remain running, control progress is present, and no false stall is reported.
- `(verified-offline)` The corrected test passed 10 consecutive isolated runs. J11/J12 related collection passed `57 tests`; compileall and diff-check passed. No runtime rollback, relay shutdown, or real input was used.
- `(J13 verified-offline)` Existing ProgramGamepadOutput heartbeat keeps the lease for neutral/no-input states; session-expired heartbeat clears only the current controller token and `rearm()` reacquires that controller. Added regression coverage for expired-token recovery, controller isolation, neutral command retention, heartbeat and local diagnostics.
- `(J15 verified-offline)` Existing SnapshotOutputAdapter arm gate test confirms a 10,000ms gate: the first snapshot can establish a neutral lease, subsequent snapshots remain neutral until the exact deadline, and only then can a nonzero intent be written. Control/runtime tests confirm nearby dynamic follow emits neutral `FOLLOW_HOLD` while retaining session, and moving the leader beyond the resume band resumes a pulse; only explicit stop releases the session.
- `(focused)` J13/J15 focused collection passed `51 tests`; no Host/game/input was started and no movement/threshold parameters changed.
- `(final-audit-2026-10-09)` J01 wall-quality adapter + stale-fault evidence: `offline_verified`; old historical Vision fault is separated from current worker health, real recurrence unverified.
- `(final-audit-2026-10-09)` J02/J03 legacy motion: `offline_verified/contract_equivalent`; adapter delegates complete `SimulatedFollowRuntime`, fixed 80ms/full-magnitude drift removed, replay matches reference. P2-over-P1 real game log and Host-consumption proof remain absent.
- `(final-audit-2026-10-09)` J04/J05 relay/lifecycle: `offline_verified`; relay single consumer, lock, stale generation and rebuild lifecycle tests pass. Forced real child stop/rebuild and Qt/Host boundary remain unverified.
- `(final-audit-2026-10-09)` J06/J07/J14: `offline_verified` for fault suppression, captured-at rewind, receipt de-duplication, local-first and memory cooldown/single-flight. Full real degraded→local→memory escalation remains unverified.
- `(final-audit-2026-10-09)` J08/J09: `offline_verified` for transform/generation/map handover contracts; real map-scroll and replacement-worker continuity remain unverified.
- `(final-audit-2026-10-09)` J10: `offline_verified` for shared motion contract and dynamic adapter; full lifecycle unification with old SimulatedFollowRuntime is intentionally not claimed.
- `(final-audit-2026-10-09)` J11/J12: `offline_verified` for per-stage and recovery/rebuild p50/p95/max/count, queue age/drop and relay gap/duration. No real throughput or 25–30Hz claim.
- `(final-audit-2026-10-09)` J13/J15: `offline_verified` for heartbeat/rearm, neutral lease, 10s gate and continuous hold/resume. Real Host lease and game movement remain unverified.
- `(final-audit-2026-10-09)` J16: `partial/offline`; relay/control cadence and timing fixtures exist, but no real IPC/GIL/Qt/Host/game throughput evidence. This is the primary performance blocker for a game-consumed claim.
- `(final-audit-2026-10-09)` Minimal combined collection: `106 passed`; compileall and diff-check passed. No real game, Host, memory, network or controller input.
- `(final-audit-blockers)` The project is ready for a controlled user test only, not a claim of full-map stability. Blocking evidence still includes real child rebuild, real Host/game receipt-to-motion correlation, P2 overshoot long run, map-scroll handover, and J16 real throughput.
# 2026-10-09 modular startup pickle failure (fixed)

## 2026-10-09 latest live run: modular follow stopped before tracking

- `(confirmed/log)` Session `14:04:45.224` started successfully: Control completed at `14:04:45.868`, Vision at `14:04:45.965`, Output at `14:04:45.968`, first Control snapshot at `14:04:46.184`, first Vision observation at `14:04:46.772`.
- `(confirmed/log)` The same session submitted `stop` at `14:04:47.148` and finished at `14:04:47.323`, about 1.9 seconds after start. No `worker_fault`, `worker_stall`, Vision error, Control error, route failure, or startup pickle error occurred. It never reached a meaningful follow interval or the 10-second arm gate.
- `(confirmed/source gap)` The stop log records lifecycle operation but not the initiating caller/stack or UI event. The next diagnosis must instrument every `stop_follow_experiment` caller and lifecycle reason before changing runtime behavior.
- `(confirmed/source gap)` Legacy `dual_motion` is stopped during modular takeover, while modular `VisionProcessEvent.frame` is consumed by Control and not published to the page preview state. The visible minimap screenshot therefore remains the pre-takeover frame even while the Vision worker may be sampling.
- `(process correction)` Offline component tests did not cover page lifecycle, stop provenance, or Vision-frame-to-UI preview handover. Previous “人工全链路审查” claims are downgraded for these boundaries; no feature readiness claim is valid until the page integration is traced and verified.
- `(next exact)` Trace all stop callers and add structured caller/reason/serial logs; then define a latest-frame UI preview handover that does not reintroduce legacy capture ownership or block Control. Re-run page startup/stop integration tests before any real follow test.
- `(implemented-diagnostics)` `capture_test_page.py` now logs stop caller chain, lifecycle caller/state, modular poll count, snapshot tick/roles, worker states, consumed visual/control sequence diagnostics and arm-gate status. This is observability only; it does not change stop semantics or movement.
- `(verified-offline)` Page/lifecycle focused collection `22 passed`; compileall and diff-check passed. User must run one normal session and manually stop it so the exact stop caller can be identified.

- `(confirmed)` Latest modular startup failed before Vision child entry, at Windows `spawn` serialization in `VisionProcessHandle.start`; traceback showed `TypeError: cannot pickle '_thread.lock' object`.
- `(root-cause)` `DualObservationProcessor` is passed as a Vision process argument and owns `TimingWindow._lock`. The lock is diagnostics-only but was serialized with the processor. Control had already started; no capture, route, Host, memory, or game input was reached.
- `(fixed)` `follow_engine/timing.py::TimingWindow` now serializes only bounded numeric samples and size, then recreates a fresh process-local lock on unpickle. This keeps worker state spawn-safe without passing UI/runtime locks across processes.

## 2026-10-09 startup failure follow-up diagnosis

- `(confirmed)` The attached UI error is the Windows `spawn` serialization failure and occurs before Vision child entry; it is not a map, vision, route, Host, or virtual-gamepad failure.
- `(confirmed-source)` The failing object in the captured run was `DualObservationProcessor._processing_timing`, whose `TimingWindow` contained a `threading.Lock`. The parent passed the processor directly through `VisionProcessHandle(... Process(args=...))`.
- `(current-tree)` The working tree contains the `TimingWindow.__getstate__/__setstate__` boundary fix and the focused spawn/composition/page checks pass (`20 passed`). This is offline evidence only; the already-running GUI process would retain pre-fix imports until restarted.
- `(boundary)` A direct pickle of complete process handles is not a valid check because multiprocessing queues/events are intentionally shareable only through process spawning. The relevant child arguments are covered by the real spawn-focused tests; no second lock failure was reproduced in the current tree.
- `(conclusion)` This evidence does not justify abandoning Python multiprocessing. It identifies a concrete spawn-safe boundary violation in diagnostics state. A technology change would only be justified after a clean restart still reproduces a new child-argument serialization failure.

## 2026-10-09 latest run: modular preview and output evidence diagnosis

- `(confirmed-log)` The latest session started modular follow at `13:57:22.427`; Vision and Control workers reached `running`, first Control snapshot at `13:57:23.520`, first Vision observation at `13:57:23.845`, and parent polling continued roughly every 15–16 ms until the explicit stop at `14:00:03.167`.
- `(confirmed-source)` During modular takeover, `capture_test_page._start_modular_follow_experiment()` stops the legacy dual-motion worker. `_poll_modular_follow_engine()` only polls/publishes `FollowUiState`; it never calls `_render_preview()` or receives a Vision frame/processed mask. The modular Vision event normally has `frame=None` because encoded frames are placed in `SharedFrameRing`. Therefore the three screenshot panels remain the last legacy/first-frame image by design, even while the child capture loop continues.
- `(confirmed-source)` `FollowEngineUiAdapter`/`Poe2FollowEnginePageAdapter` expose only snapshot and diagnostics, with no preview-frame channel. This is a UI observability boundary defect, not proof that capture stopped.
- `(evidence-gap)` The run log contains only `first_output_apply`; it has no persisted per-tick control decisions, output writes, receipts, or game-consumption evidence for `13:57–14:00`. Parent worker progress ages show fresh Vision/Control events, but they cannot prove non-zero P2 input was accepted or moved the game character.
- `(conclusion)` The screenshot's unchanged minimap is explained by the missing modular preview bridge. Whether P2 actually failed to move is a separate output/Host evidence gap; it cannot be attributed to visual capture from this log alone. No runtime code changed during this diagnosis.
- `(verified-offline)` Windows-spawn composition regression and port checks: `24 passed`; no game/Host/memory/input started. `compileall -q src tests` and `git diff --check` passed.
- `(next exact)` Restart the workbench so the updated module is loaded, then retry modular startup once. If it fails again, retain the new traceback; do not infer a movement/vision cause from a pre-worker startup error.

## 2026-10-09 18:38 latest run: local ROI false association causes follower hold (read-only)

- `(confirmed-log)` The session ran normally from `18:38:29.301` through the user's manual stop at `18:39:24.701`. Vision/Control workers stayed `running`; Host output remained `acquired=True`, `heartbeat_failures=0`, `session_expired=False`, and stop cleanup completed successfully. This is not a process stop or virtual-gamepad disconnect.
- `(confirmed-log)` P2 initially emitted non-zero intents and followed. At tick `1401` it entered the intended near-target hold; after P1 moved, non-zero intents resumed (for example tick `1452`). `FOLLOW_HOLD` is therefore not a permanent-stop root cause.
- `(root-cause)` Starting at the local recovery around ticks `2054–2057`, P1's accepted control `position` diverged from its current observation `visual_position`: about 31 px, then 44 px, and later a stable 86–97 px. Example late state: P1 `source=local_roi`, `position=(965.277,643.078)`, `visual_position=(1053.209,639.625)`, `visual_accepted=True`.
- `(root-cause)` The wrong P1 position is exactly near P2's fused position. The local recovery result is written by `_apply_recovery_positions(..., source="local_roi")`, then `_refresh_live_target()` propagates that wrong position as P1's target. P2 consequently reports the same position as its target and emits `vector=(0,0), neutral=True` for the remainder of the run. This explains the apparent late P2 stop without blaming route/output.
- `(source-confirmed)` `FollowControlRuntime._run_local_recovery()` accepts any `LocalRoiBackend.match()` candidate that clears the generic score threshold. `EncodedMarkerRoiSearch` chooses the highest-scoring marker in the ROI and applies only a soft identity factor; the modular seed currently does not pass `identity_hints` into `FollowSeedBundle`, and local search has no exclusion/consistency check against the other role. In a crowded/overlapping two-player frame, a P2 or interference marker can therefore be accepted as P1.
- `(source-confirmed)` Main-frame `visual_position` and local-recovery `position_native` are produced by different candidate paths. The transform is rebound from the same observation, so the persistent 88 px gap is evidence of candidate misassociation, not merely a stale transform. The local result is incorrectly promoted to accepted evidence (`_last_accepted_visual_sequence`), so it masks the real visual mismatch on following ticks.
- `(boundary)` No algorithm or threshold was changed in this diagnosis. The exact fix boundary is: local ROI must be role-aware and cross-validated before `_apply_recovery_positions` can mark evidence accepted; a local candidate that conflicts with the current multi-role assignment/geometry must remain degraded/predicted, not refresh the live leader target. Preserve existing route, pulse, speed, and output policies.
- `(next exact)` Before editing, add focused replay evidence for a two-role crowded frame: assert that local recovery cannot assign P1 to P2/interference, that accepted local position and observation position stay within a bounded consistency gate, and that a rejected local candidate does not refresh P2's live target. Then implement one isolated fix and rerun the focused suite.

## 2026-10-09 latest run: frame fan-out and memory-reanchor trigger clarification

- `(source-confirmed)` Each accepted Vision observation contains both role candidates and `FollowControlRuntime.apply_visual()` iterates both roles in the same call. The new frame therefore does process P1 and P2 together at the Vision/Control boundary.
- `(important-boundary)` Simultaneous frame processing is not the same as simultaneous correction. If P1's candidate fails the innovation/fusion gate, `apply_visual()` does not update P1's accepted anchor. The control tick can then perform at most one local ROI attempt per tick, selected round-robin across missed roles. A local result is currently promoted independently and is not compared with the other role's candidate before refreshing the live target.
- `(confirmed-log)` In the latest run, the P1 frame candidate remained far from the accepted `local_roi` position, but the local result was marked accepted and refreshed P1→P2. This is why the new frame did not immediately correct the drift: it was observed, but its P1 candidate was rejected/overridden by an unvalidated local candidate.
- `(source-confirmed)` Default `RecoveryPolicyConfig`: visual healthy 250 ms; visual degraded/local trigger 600 ms; memory trigger 1500 ms; global trigger 3000 ms; memory uncertainty 50 native units; global uncertainty 100; memory miss count 3.
- `(memory-trigger)` Per role, memory is eligible only after a fresh frame has been exhausted by local retry: if a frame is available and its age is ≤1500 ms, policy continues bounded prediction. A memory request is emitted when `memory_cooldown_ready` is true and any of `consecutive_misses >= 3`, `prediction_uncertainty >= 50`, or `frame_age >= 1500 ms` is true, provided the backend has not already failed in that tick.
- `(memory-backend)` The backend is single-flight (`in_flight` blocks another submit), runs the read asynchronously in one thread, and the concrete page composition defaults to an 8000 ms memory cooldown unless overridden. Its result is consumed on a later control tick and is generation-checked before positions are applied.
- `(escalation)` Global recovery is separate: it becomes due on a failed memory attempt, age ≥3000 ms, uncertainty ≥100, or a memory failure while cooldown is unavailable. These thresholds currently keep the session alive; they do not directly stop follow.
- `(next exact)` Add the missing frame-vs-local cross-check before changing memory thresholds. Otherwise lowering memory cooldown would only make a wrong local association recover faster, not correct the root cause.

## 2026-10-09 visual-prediction mutual constraint decision

- `(user-decision)` For each role on a fresh frame: if there is exactly one valid role candidate and its confidence is high, treat that candidate as strong visual evidence and correct the native/map position toward it; if there are multiple valid candidates, choose the candidate nearest the predicted position. Visual evidence and command prediction are mutual constraints, not competing independent recovery paths.
- `(source-gap)` Current implementation does not express this rule as one shared association contract. Normal frame association runs through `DualRoleAssociator`, while local ROI independently selects the highest-scoring marker and can promote it without comparing it to the per-role candidate set or the other role.
- `(boundary)` The rule must be applied per role/profile, not to a single global marker list: one candidate total cannot be assigned to both roles. Candidate validity must include role color/profile compatibility and finite coordinates; multi-candidate selection must use native-space distance to the command-predicted position, with confidence as a tie-break/validity gate.
- `(next exact)` Implement the rule in the common observation/ROI association layer, then add replay tests for: one high-confidence candidate correcting map position; multiple candidates selecting nearest prediction; one candidate near the other role being rejected for the wrong role; and rejected/ambiguous candidates preserving prediction/miss evidence so memory fallback can still trigger.

## 2026-10-09 two-frame single-candidate confirmation decision

- `(user-decision)` When processing cadence is fast enough, a single high-confidence candidate should preferably be confirmed across two consecutive frames before declaring a prediction/map-position drift. This makes visual correction a short temporal consensus rather than trusting one isolated contour.
- `(rule)` For the same role, frame N and N+1 must each have exactly one valid candidate, compatible identity/profile, high confidence, finite native coordinates, and a bounded inter-frame displacement consistent with elapsed time/wall shift. If both frames satisfy this, accept the candidate sequence and correct the fused/native position toward the newest candidate, even when the old prediction is far away.
- `(rule)` If the two candidates are not temporally consistent, keep command prediction and miss evidence; do not refresh the live target from either ambiguous candidate. A later frame can restart the two-frame confirmation.
- `(boundary)` Two-frame confirmation must not add a full-frame blocking wait: frame N remains usable for bounded prediction/output, while frame N+1 confirms or rejects asynchronously at the next control tick. This preserves follow responsiveness.
- `(next exact)` Add replay cases for stable single-candidate correction, moving single-candidate correction, candidate swap between frames, and a static interference marker. Verify that only the first two correct the map anchor and live target; the latter two preserve prediction and allow the existing memory thresholds to accumulate.

## 2026-10-09 implementation: temporal single-candidate association and local conflict guard

- `(implemented)` `MarkerAssociator` now holds one high-confidence candidate outside the normal innovation gate for one frame and confirms it on the next frame when the candidate remains spatially consistent; after confirmation it can re-anchor the role instead of rejecting the map correction. Existing in-gate single-candidate behavior is unchanged.
- `(implemented)` `EncodedMarkerRoiSearch` now selects the nearest candidate to the predicted screen point when multiple candidates exist; confidence is a tie-breaker rather than the primary selector. A single candidate remains the strongest correction candidate.
- `(implemented)` Control local recovery now rejects a local ROI result that conflicts materially with a visible candidate from the same frame, preserving miss/uncertainty evidence instead of overwriting the live-follow target.
- `(verified-offline)` Marker association + vision processor + control runtime focused set: `27 passed`; `compileall -q src tests` and `git diff --check` passed. No game/Host/input was started.
- `(remaining)` The common association layer still needs a full per-role/profile candidate partition in the production seed (identity hints are not yet populated by `build_follow_seed_from_dual_result`), plus replay coverage for real two-role color-collision frames. This is the next implementation boundary before real testing.

## 2026-10-09 implementation: first-frame identity hints wired into modular follow

- `(implemented)` `build_follow_seed_from_dual_result()` now accepts the first-frame candidates retained by the page, derives distinct role→identity hints from the accepted candidate IDs, and carries them in `FollowSeedBundle` when the hints are complete and unique.
- `(implemented)` Modular composition creates role-specific `EncodedMarkerRoiSearch` instances when identity hints are available; Control accepts a role→search mapping and binds/executes the matching search for each role. Legacy single-search compatibility remains when hints are absent.
- `(verified-offline)` Page seed/composition, control, marker association and vision focused collection: `36 passed`; no real game/Host/input.
- `(remaining)` Real crowded-color replay still needs validation; if calibration yields incomplete/non-unique hints, the compatibility single-search path remains intentionally active and relies on distance/consistency guards.

## 2026-10-09 implementation: large-area color-interference rejection

- `(evidence)` Historical occlusion diagnostic evidence contained 430 accepted contour-area samples: p50≈32.5 px², p90≈36 px², p99≈38.5 px², maximum≈40 px². The configured detector ceiling remains 55 px², leaving room for same-color large blobs to enter candidate ranking.
- `(implemented)` `MarkerAssociator` now rejects candidate areas above a conservative 48 px² soft ceiling (area=0 remains unknown/compatible with synthetic and legacy candidates) before role assignment, and exposes filtered candidate IDs in diagnostics. This is a second-line guard; profile `min_area/max_area` filtering remains unchanged.
- `(verified-offline)` Marker association, vision, control and page focused set: `31 passed`; no game/Host/input.
- `(risk)` The 48 px² value is evidence-based from historical accepted samples but remains a tunable safety parameter; real visual scale changes must be checked before lowering it further.
