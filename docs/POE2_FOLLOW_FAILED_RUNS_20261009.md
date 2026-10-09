# 2026-10-09 跟随退化：最新实测只读诊断

用户反馈：修改后P2从开始就无法正常跟随，要求解释多次测试时间线、出错代码及为何此前审查漏掉。

本轮边界：只读运行日志、代码与Git差异；不修改运行代码、不启动程序、不连接Host或读取内存、不发送真实输入。

已恢复背景：总断点已有03:07与03:08两轮的初查，确认首帧accepted、旧视觉正常、新会话有首个snapshot/vision，随后多次dispose/rebuild。原始worker错误未持久落盘，不能从Vision被dispose就断言Vision是首因。最新日志已到03:12:29，需将新增会话一起分段。

下一步：按session边界提取03:07至03:12日志；核对engine watchdog/重建、Control tick路线与ROI、输出闸门和Host输入证据，区分确定事实与缺失数据。

## 03:17 最新失败会话（只读诊断）

## 03:44 最新失败会话（确定性 Vision 崩溃）

- `03:44:00.865` memory seed 成功，`03:44:01.987` 首帧 accepted（score 0.909898）；接管前 legacy dual motion 约 20--22 FPS、双角色可见。
- `03:44:21.744` Vision 子进程抛出 `ValueError: wall_quality must be <= 1`，来源为 `DualObservationProcessor.process()` 将 `process_wall(...).quality` 原样写入 `VisualObservation`，而 phase correlation 的 raw response 没有在 wall adapter 边界归一化。
- 该错误使 Vision 不再发布新 observation；Control 仍运行。约 2 秒后 watchdog 看到 Vision failed/stalled，随后重复 rebuild（同一确定性错误会再次触发），形成恢复循环。
- 本次不是首帧失败，也不是父侧 poll 停止；但它会切断视觉纠偏，使 Control 继续使用旧观测/预测，足以放大 P2 越过 P1 的风险。
- P2 overshoot 的精确输出/预测差异仍需旧版 `a3070ea` 对照 control tick、pulse duration、magnitude、arrival 和 prediction update；本次日志缺少逐 tick target/vector/receipt，不能把 overshoot 单独归因于路径算法。

下一步边界：先修复 wall quality 的来源归一化并增加回归，再处理“重复同一确定性 fault 不应无限 rebuild”；随后完成旧版移动策略不变量对照。不得以 contract 层静默 clamp 掩盖来源。

事实：03:17:30--03:17:36 旧 `dual_motion` 连续 120 帧双角色均 `status=tracking`，`visible` 两个角色、`wall_trusted=True`、`dropped_results=0`，有效帧率约 21.5--21.9 FPS；这证明首帧/旧视觉/地图实例在接管前是正常的。

事实：03:17:37.278 开始 modular takeover；03:17:37.977 新 FollowEngine start 完成，03:17:38.123 收到首个 control snapshot，03:17:38.449 收到首个 vision observation。之后 03:17:40.562 dispose，新 Vision 在 03:17:41.210 重建；随后 03:17:43.794、03:17:44.697、03:17:47.544、03:17:48.219 重复 dispose/start。页面隐藏时 03:18:03 才最终 stop。该周期与 `worker_stall` watchdog 的 2 秒 running deadline 相符，但当前日志没有持久记录触发时的原始错误、worker progress、rebuild reason。

事实：03:17 旧视觉统计不是失败原因；新模块化会话至少完成首个 control/vision 事件，但未形成可观测的稳定连续链。Host/输入消费仍不能由这些日志证明。

高概率根因（尚未最终证实）：`FollowEnginePort._last_progress_monotonic` 只在父线程 `poll()` 成功取到最新事件时更新，而 `_check_worker_stall()` 在同一个 `poll()` 的最前面执行。只要 Qt timer 没有持续调用、事件队列暂时没有被父侧消费、或 Control tick/route 阻塞超过 2 秒，父侧 watchdog 就会把正常子进程判为 stalled，调用 `_rebuild_components()`，造成 Vision 反复 dispose/start；这直接切断 P2 的连续目标/输出链。该判定不是基于子进程自身心跳，因此存在假阳性。

已确认的回归来源：模块化接管是当前版本新增边界（`capture_test_page._start_modular_follow_experiment` → `FollowEnginePort.start/poll` → 新 Vision/Control），旧链路在同一会话接管前稳定。另一个独立退化是 Concrete builder 的 `arm_delay_ms=6000`，会使首个非零 P2 输入至少延迟约 6 秒，但它不能解释 2 秒后 Vision 被重建。

关键缺失证据：03:17 没有持久化的 `worker_stall` 触发日志、Control 每 tick sequence/耗时、Vision/Control 子进程 traceback、父侧 poll 次数/间隔、重建 reason。下一步应先补齐这些边界日志并离线复现 watchdog 假阳性，再决定单一修复；当前不应宣称已找到唯一最终根因。

## 代码对照结论（03:17）

`FollowEnginePort.poll()` 当前顺序是：`_refresh_worker_liveness()` → `_check_worker_stall()` → 才调用 `vision.poll_latest()` / `control.poll_latest()`（`engine.py:358-437`）。进度时间戳只在父侧读到 `observation` 或 `snapshot` 时更新（`engine.py:381-383`, `436-437`）。因此 watchdog 的“进程无进展”实际测量的是“父侧最近一次消费事件的时间”，不是子进程心跳或最后一次 tick 时间。

一旦超过 2 秒，`_check_worker_stall()` 将 `_last_error` 覆盖为 `worker_stall:*`，随后提交 `_rebuild_components()`；重建先 stop/dispose 当前 Vision/Control，再创建新代。这正好对应 03:17 的 dispose/start 周期。当前实现没有在该分支记录 stale worker、now、last_progress、child `is_alive`、queue age、control tick sequence 或 traceback，所以日志只能看到后果。

页面的异步 start 完成后才在 `_on_follow_lifecycle_finished()` 设置 `_modular_follow_active=True` 并启动 33ms Qt timer（`capture_test_page.py:1705-1722`）；旧链路停止和新链路启动又共享页面线程、native capture 与生命周期状态（`capture_test_page.py:1777-1808`）。这使“旧 worker 尚未完全退出/页面 poll 暂停/新 worker 已启动”的窗口成为真实链路特有风险。

为什么离线审查没发现：聚焦测试只验证了伪造事件可被 `poll_latest()` 消费、重建和代际保护，未验证真实 Qt timer 的连续调用、multiprocessing Queue 的事件到达延迟、父侧 poll 间隔与 2 秒 watchdog 的关系；也没有把 watchdog 触发上下文持久化。因此“44/600 passed”只能证明契约样例，不足以证明实机连续跟随。

## 旧版、重构目标与当前实现的边界

旧版 `dual_motion` 是一个页面驱动的单链路：Qt/页面触发截图 worker，页面 drain 视觉结果，页面同时做目标转发、预测、路径、恢复和输出。优点是视觉结果和跟随 tick 在同一旧 timer/状态上下文里，至少不会出现“新引擎已启动但父侧没消费事件”的独立生命周期；缺点是重型识别、恢复、路径会阻塞页面，视觉暂失容易把业务状态推入 recovery。

重构计划要求：VisionProcess 独立采样并只发布最新观测；FollowControlProcess 独立以固定频率推进预测、融合、路径和恢复；Output actor 独立写 Host；Qt 只负责生命周期、目标配置、轮询快照和显示。Vision 暂停时 Control 仍应继续用 command odometry 输出，局部/内存/全局恢复不能释放 dynamic follow session。计划还明确要求 UI 不参与截图、tracker、路径和恢复编排。

当前实现已经完成了不少底层拆分：Vision/Control/Output 有独立对象和 generation，Control 内有 prediction/fusion/recovery，target policy 已下沉到 Control，输出有 heartbeat/rearm，队列和 frame ring 是 latest-only/有界的。但它仍不是完全脱离 UI 的双通道：`FollowEnginePort.poll()` 仍是父侧把 Vision observation 转给 Control、把 Control snapshot 转给 Output 的关键桥；父侧 poll 的事件时间戳又被 watchdog 当作 worker progress；页面还负责旧 dual_motion 停止、新 composition 异步 start 和 33ms timer。换言之，计算已经拆进进程，消息消费、输出提交和故障判断仍有一个强 UI/父侧耦合点。

因此这次退化不是“重构计划本身错了”，而是当前实现只完成了进程/模块拆分的一部分，却把父侧桥接和父侧 watchdog 当成了可靠心跳。旧版没有这个独立重建边界，所以不会以同样方式反复销毁 Vision；新版新增了该边界，却没有在真实 Qt/Queue/旧 worker 交接条件下验证。
`FollowEnginePort` 当前的实现偏离了原双通道计划：Control 虽独立进程化，但父侧 poll 仍是 Vision→Control 和 Control→Output 的关键桥，watchdog 又用父侧事件消费时间作为 worker progress。03:17 日志证明该偏差可触发 Vision 反复 dispose/start。此前离线测试和人工审查未覆盖真实 Qt timer、multiprocessing queue、旧 worker 交接和 watchdog 假阳性，因此验收结论过度乐观。

R0 instrumentation 已加入：父侧每次/每30次 poll 的间隔和进度年龄、watchdog stale 输入与最后父侧事件、Vision 子进程每30帧进度、Control 子进程每30 tick 进度及 pid。离线 compileall、diff check 和相关测试 29 passed；这只是证据链完成，不代表运行根因已修复。
