# POE2 跟随最新测试诊断（2026-10-09 16:53--16:55）

> 范围：只读诊断。没有修改运行代码、没有重启、没有发送输入。

## 1. 结论摘要

本次不能下结论说“视觉没有运行、完全只靠预测”。日志明确显示 Vision 子进程从 16:53:43 启动后持续运行，父端 `parent_poll` 持续消费，`progress_age_ms` 通常为 15--63ms；因此帧采集/处理链没有整体卡死。

但用户看到的工作台三个预览面板停在首帧，是确定的 UI 观测链缺失：模块化页面 `_poll_modular_follow_engine()` 只取快照和 diagnostics，不从 `SharedFrameRing` 读取新图，也不调用 `_render_preview()`；`FollowEngineUiAdapter` 只暴露 snapshot/diagnostics。因此“预览不动”不能用来判断 Vision 是否处理新帧。

本次后段确实出现了“输出仍在写、但连续写零向量”的状态。16:54:45 左右仍有小幅非零向量，16:54:51.425 后到页面隐藏前约 20.7 秒采样均为 `(0.0, 0.0)`。Virtual gamepad 没有断联证据：`controller=2`、`acquired=True`、`heartbeat_failures=0`、`session_expired=False`、`rearm_count=0`。这更像 Control/融合决策进入保持或没有产生新非零 intent，而不是输出设备断开；具体原因被当前日志缺失的“每 tick 控制决策/已接受视觉位置/目标位置”遮住，不能臆断为单一视觉或预测故障。

最后的停止不是跟随算法自主停止：16:55:12.410 明确记录 `suspend <- hideEvent`，随后 Vision 正常停止，Control 在 2 秒超时后 `forced=True` 被终止。页面隐藏触发了生命周期停止；这与此前连续零向量是两个事件。

## 2. 截图证据

- `codex-clipboard-800d48f5-dd48-4258-95de-167e7df08641.png`：工作台显示首帧附近的地图/标记，状态为 `tracking (visual_match)`。
- `codex-clipboard-8774dfa9-f805-4cc9-959a-8d4b08780e9a.png`：PoE2 实时小地图已在另一位置，P1/P2 仍在同一较远区域。
- 两张图证明“工作台预览与游戏画面不同步”，不能单独证明视觉进程没有处理；源码已确认模块化预览没有 ring→UI bridge，所以首帧冻结是预期缺陷。

## 3. 关键时序

| 时间 | 证据 | 解释 |
|---|---|---|
| 16:53:20.936--31.416 | 首帧捕获、识别、内存锚点、变换接受 | 首帧注册成功；耗时约 5.086s |
| 16:53:42.732 | `modular_takeover stopping_legacy_dual_motion=True` | 页面线程旧 dual worker 被停止以交出 session 所有权；不是遗留 OS 进程 |
| 16:53:43.680--43.776 | Control PID 24020、Vision PID 35108 启动 | 新架构两个 child 已进入 running |
| 16:53:44.115 / 44.567 | first Control snapshot / first Vision observation | 两条新链路都产生过首个事件 |
| 16:53:45--55 | 10 秒 arm gate，输出主要为零，随后出现非零 | 冷启动门生效，不是断联 |
| 16:53:55--16:54:50 | `write_count` 持续增加，非零/零交替 | Output actor 持续收到并写入 intent |
| 16:54:51.425--16:55:11.149 | 采样的 `last_command.input_vector` 持续 `(0,0)` | 进入持续 neutral/hold 或控制没有产生新的非零命令；当前日志无法再细分 |
| 16:55:10.285--12.151 | Control progress age 94--250ms，Vision 仍 15--63ms | Control 有间歇性停顿，Vision 未停止；不能称全局死锁 |
| 16:55:12.410 | `stop_requested ... suspend <- hideEvent` | 页面隐藏触发生命周期 stop |
| 16:55:14.578 | `control_process_stopped ... forced=True` | Control 未在 2s 内退出，被强制终止；这是关闭阶段问题 |

## 4. 源码链路与根因边界

### 4.1 视觉实际上做了什么

`vision_process_entry` 按固定 cadence 调用 capture→`DualObservationProcessor.process()`→写事件；`DualObservationProcessor.process()` 会解码、提取 wall、提取 markers、更新 transform、做双角色 association，并将结果写入 `SharedFrameRing`。父端 `poll_latest()` 只取最新事件。

本次 `parent_poll` 持续且 Vision progress age 新鲜，足以证明 child 循环仍在推进。由于 child 日志没有可靠回传每个 accepted/rejected observation，不能证明每一帧都被 Control 接受，也不能证明位置估计准确。

### 4.2 为什么截图一直是首帧

`capture_test_page._poll_modular_follow_engine()` 只调用 adapter.poll() 并更新 label/diagnostics；`FollowEngineUiAdapter.state()` 只有 `snapshot` 与 `diagnostics`。Vision 的 frame payload 进入 ring，Control 可读取，但 UI 没有读取/渲染通道。因此截图冻结是已确认的显示链缺陷，不是 Vision 无输出的证据。

### 4.3 为什么后段可能卡住

Control 的 `apply_visual()` 先过 acceptance gate；通过的视觉才更新 `_latest_visual`、角色位置和 live target。随后 `tick()` 根据角色状态、回执 odometry、预测/恢复状态产生 output intents。若新视觉被拒绝、目标仍是上一 accepted target、或 follower 已进入 continuous-follow hold，OutputScheduler 仍会按节拍写 `(0,0)` 并保持 heartbeat。当前 page_poll 没有 `accepted_visual_sequence`、角色位置、target、intent reason、arrival/hold 状态，故无法从这次日志选择上述哪一条。

### 4.4 Control 停顿与最终停止

`Control` 的一次 tick 包含视觉融合、route/runtime、必要的恢复轮询和输出提交；日志显示 547ms、1015ms 等年龄峰值，说明 tick/relay 发生过延迟。最终 Control `forced=True` 发生在页面隐藏后的 stop timeout，不应倒推为跟随算法先主动停止。

## 5. 已确认、未确认、不能混淆的事项

### 已确认

1. Vision child、Control child、父 relay 在主要测试区间都运行过。
2. UI 预览没有模块化新帧桥接，首帧冻结是源码确定行为。
3. Output 有大量写入；后段连续零向量；heartbeat/lease 健康。
4. 页面隐藏触发 stop；Control 关闭阶段被强制终止。

### 未确认

1. 后段零向量究竟是 `FOLLOW_HOLD`、arrival/resume 判断、视觉长期被拒绝，还是 Control tick 延迟后的旧 snapshot。
2. Vision 的 accepted/rejected 位置、P1 target 更新时间、P2 实际位置，以及 Host receipt 是否对应游戏位移。
3. 截图时刻与日志采样点的精确对应关系。

### 不能据此声称

- 不能声称“视觉完全没用上”。
- 不能声称“只用预测导致卡住”。
- 不能声称“虚拟手柄断联”。本次健康指标反而不支持断联。
- 不能声称“Control 自主停止”；日志支持的是 page hide→suspend→forced stop。

## 6. 当前最直接的诊断根因

对用户可见的“监控截图停在首帧”，根因已经确定是 **模块化 Vision→UI preview bridge 缺失**。

对“P1/P2 走远后后段停止/卡住”，当前能确定的是 **控制决策证据不完整 + Control 出现长尾停顿 + 输出转为持续 neutral**。这不是一个已经被日志证明的单一视觉/预测根因；需要下一次不改策略的诊断运行至少记录：Vision sequence/source/acceptance、每角色 accepted position、live target、Control tick/intent reason、output intent→receipt 对应关系，并把 page hide 的调用者单独标记为用户生命周期事件。

## 7. 本轮边界

本轮没有修改运行代码，没有启动 PoE2/Host，没有发送真实手柄输入。结论仅基于两张截图、`data/logs/poe2_live_terrain.log` 的 16:53:20--16:55:14 区间和当前源码。

## 8. 后续显示修复（2026-10-09）

用户要求先修复监视帧和大地图不更新。已完成最小显示层接线：

- `FollowEnginePort` 在父端 relay 已消费 Vision observation 后，从 `SharedFrameRing` 取最新 encoded payload，保存为只读 preview frame；不把 ring record 作为新的 Control 输入。
- `FollowUiState` 增加可选 `preview_frame`，旧调用方仍可用前三个字段。
- 页面模块化 poll 将 encoded payload 解码为 `QPixmap`，更新当前截图面板；processed/feature 面板不再显示旧版残留图，而显示“处理结果在子进程”的明确状态。
- 页面模块化 poll 将最新 `FusionSnapshot.roles[*].position_native` 按首帧 map transform 投影到大地图 overlay，更新角色标记。

验证：`py_compile` 通过；follow page adapter/port/page composition focused tests `21 passed`；`git diff --check` 通过。尚未启动真实 PoE2/Host，也未发送输入。该修复只改变 UI 观测，不改变 Vision、Control、route、output 或阈值。
## 9. 最新 18:37--18:39 运行的根因收敛（只读）

本次详细 `control_decision_observed` 日志将后段卡住与 P1 大地图丢失收敛到同一条控制链：

- P1（`Metadata/Characters/StrDex/StrDexFourb`）在视觉仍可见且 `visual_accepted=True`、序列持续增长时，`state.position` 长时间为 `source=local_roi` 的 `(965.277,643.078)`；同一 tick 的 `visual_position` 却约为 `(1053.209,639.625)`，相差约 88.0 native units。
- P2 的 `target` 被持续刷新为该错误 P1 state，P2 的 `source=visual_fused` 也被融合到同一点；输出意图连续为 `(0,0)`、`neutral=True`、`duration_ms=1271`。
- 手柄健康仍为 `acquired=True`、`heartbeat_failures=0`、`session_expired=False`，因此本次没有虚拟手柄断联证据。

源码链路已核实：`tick()` 在当前 accepted visual 仍 fresh 时仍允许对角色做 local retry；`_run_local_recovery()` 将 ROI 结果无条件交给 `_apply_recovery_positions()`；后者直接覆盖 role state、`last_visual_position`，并通过 `_refresh_live_target()` 改写 P1→P2 target。`EncodedMarkerRoiSearch` 没有按 role 传入 `identity_hint`，只对候选做可选的弱 0.82 惩罚；因此 P1/P2 可能互相匹配，且 recovery 结果没有与同帧 accepted visual 做一致性校验。

另一个重要细节是：local recovery 成功后，`tick()` 会把该帧的 `_last_accepted_visual_sequence` 直接设为当前视觉序列。于是日志里的 `visual_accepted=True` 不能证明这次位置通过了 `apply_visual()` 的 innovation/fusion gate；它可能只表示“local ROI 成功后被标记为已处理”。这正是为什么同一条记录可以同时出现 `source=local_roi`、`visual_accepted=True`、但 `state.position` 与 `visual_position` 相差约 88 的原因。

这解释了两个用户症状：P1 在地图上被错误 recovery 坐标覆盖而看似丢失，P2 被判定已到达错误 target 后进入长时间 neutral。Vision 本身没有停止；停止时 `18:39:24.701 stop_requested reason=requested caller=main`，两个子进程均正常退出。

本节仍是诊断，不包含算法修改；下一步应先独立确认 local retry 的触发条件与 marker identity 数据，再设计最小修复边界。

## 10. 关于“新帧同时校正 P1/P2”的判断（只读）

用户提出的思路是正确的：每个新监视帧应同时产出 P1/P2 的候选位置；Control 将其与当前预测/执行积分状态比较，若不一致，应优先用同一新帧做局部纠偏或可信视觉融合，而不是让错误 recovery 继续传播。该机制可以解决本次“P1 错误位置刷新 P2 target”的问题类别，但前提是视觉候选、局部恢复候选和 live target 更新必须有明确优先级与身份校验。

当前代码实际上会对同一帧同时提取并关联两个角色，但流程不是安全的“视觉优先纠偏”：`apply_visual()` 先尝试全帧融合；随后 `tick()` 可对未被判定为 fresh 的角色执行 local retry。local retry 成功后直接覆盖 state，并把序列标记为 accepted，导致后续日志看起来像视觉已接受，实际却可能是 ROI 结果接管。也就是说，新帧中的 P1 候选并非没有产生，而是没有在最终状态中保持最高可信优先级。

安全的目标时序应为：新帧双角色关联 → 各角色分别与预测状态比较 → 可信视觉直接纠偏；不一致时同帧/下一帧局部 ROI 只作为角色限定的候选 → 候选通过身份、距离、置信度和双角色一致性后才提交 → 单一融合 owner 决定是否刷新 P1 live target → P2 使用该可信 target 持续跟随。任何候选失败都只能保留预测并等待下一帧，不能把错误候选写成正式位置。
