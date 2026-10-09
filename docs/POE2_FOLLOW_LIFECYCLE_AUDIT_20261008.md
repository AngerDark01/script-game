# PoE2 跟随同类启动与生命周期隐患审查

## 范围与结论

用户要求在修复 Windows spawn 入口挂起后，检查其他地方是否还有类似错误。本轮只检查和离线复现，不修改运行源码、不启动游戏/Host/LAN、不发送真实输入。

旧根因已修复：根 `main.py` 导入 bootstrap 不再执行日志截断、UAC、mutex、Qt 初始化。项目 runtime multiprocessing 集中在 PoE2 follow 的 vision/control handles，以及 torchlight follow service/workers。源码检查未找到第二处与旧 bootstrap 相同的“spawn 导入时执行单实例锁并退出”。独立手柄 `main.py` 的 UAC/GUI 在显式 main 内；package `__main__.py` 是直接执行 shim，Windows multiprocessing 对 package.__main__ 的特殊处理不能混同于旧 root bootstrap 副作用。

但存在其他能导致卡住、停在恢复状态、预测漂移、清理不完整的边界。以下“已复现”均指离线故障注入，不代表已经确认发生于最新实机。优先级 P1 为应在下一轮实机前优先处理，P2 为后续完善。

## 1. P1：终止持锁 worker 后，共享帧锁永久不可用

- 位置：`shared_frame_ring.py::SharedFrameRing.publish/read/read_latest/clear/rebind_session`；`VisionProcessHandle.stop`、`FollowControlProcessHandle.stop`。
- 条件：vision/control 正在持有 multiprocessing Lock 时，被 terminate 或异常结束。
- 机制：所有 ring 方法用无超时 `with self._lock`；非健壮进程锁不会因 Windows 进程退出自动恢复。stop 的超时只能终止 worker，不能修复锁。
- 离线结果：持锁 child 被 terminate 后，锁 200ms 内仍无法取得。生产的 rebind/read 没有超时，因此可能永久等待。探针不在主线程执行无界 read。
- 影响：读取帧的控制进程挂住；复用 ring 重新 start 时，父 UI 在 rebind_session 等锁而挂住。
- 修复方向：锁获取必须有界；失败转成结构化 transport fault。持锁进程死亡后应使整个 ring 代际失效，停止同代所有使用者，分配新 ring/lock 后重新绑定；不能盲目强制 release 并继续使用可能写坏的数据。

## 2. P1：输出资源清理仍可能只做一半

- 位置：`output_scheduler.py::OutputScheduler._stop_all_locked/stop`；`snapshot_output.py::SnapshotOutputAdapter.stop`。
- 条件：任一 output.stop 抛异常，比如 Host 断开/会话清理失败。
- 机制：_stop_all_locked 中单个 port.stop 的异常退出整个循环；SnapshotOutputAdapter.stop 没有 finally，scheduler.stop 报错后跳过 _close_all_outputs 和 _outputs.clear。上层 port 的 finally 只能重置自己的状态，无法保证下层释放。
- 离线结果：第一个 output.stop 抛错后，第二个 stop 次数=0，两个 close 次数=0；adapter.started=False，但仍保留 p1/p2 输出引用。
- 影响：界面看似已停止，输出连接/角色资源未完整回收，之后重启可能遇到重复资源或旧会话。
- 修复方向：每角色独立 try/finally，尝试所有 stop/close，最终清空状态，并汇总首个错误/错误列表；原始错误保留。不得以“遇错即退出循环”清理。

## 3. P1：输入等待/发送失败时，预测仍按未执行指令推进

- 位置：`follow_control_process.py::FollowControlRuntime.tick`（last_vector/last_duration_ms 与 odometry.step）；`snapshot_output.py::SnapshotOutputAdapter.apply`（arm gate 直接 return）；`engine.py::FollowEnginePort.poll`。
- 条件：6 秒输入等待内已有非零计划，同时视觉暂时缺帧；类似问题也可能在 Host 输出失败时出现。
- 机制：控制 tick 把计划向量存为 last_vector，下个 tick 按它积分；输出层是否实际写入/被 gate 拦截没有回传控制层。计划不等于执行，Host 提交也不等于游戏实际位移。
- 离线结果：初始 (0,0)，目标 (1000,0)，3 秒无后续视觉、6 秒 arm gate；Host 输出创建数=0，预测为 (101.4,0)，source=command_prediction，gate 仍剩 3000ms。
- 影响：预启动阶段虚假位移、视觉创新拒绝、到达误判/额外恢复；不能靠延长等待修复。
- 修复方向：增加带 generation/role/command sequence 的执行反馈。只有实际已提交的指令和持续时间用于 command odometry；gate/失败/中立为零控制积分。视觉继续纠偏并量化真实速度；不能将“已提交”冒充“游戏已移动”。

## 4. P1：慢心跳可持锁拖住界面轮询/停止

- 位置：`output_scheduler.py::OutputScheduler._heartbeat_loop/apply/diagnostics/stop`；页面 `_poll_modular_follow_engine`。
- 条件：Host heartbeat/rearm/start/write 请求响应较慢。
- 机制：所有 I/O 都在同一个 RLock 内执行，UI 的 apply/diagnostics 也取同锁。心跳独立线程不代表 UI 不会等待。stop 的 thread.join 虽有超时，随后获取该锁仍无界。
- 离线结果：fake heartbeat 持锁，diagnostics 等待 309.92ms 后返回。
- 影响：UI 33ms 定时器失去实时性、采样/显示延迟上升；若底层 I/O 真无界，UI 可持续挂住。
- 修复方向：UI 只交付 latest intent、读取不可变诊断快照；输出线程独占 I/O，短锁只交换状态，不在锁内等待 Host。I/O 设 deadline；分角色/代际处理 rearm，不丢目标，不终止动态 session。

## 5. P1/P2：进程存活不代表 ready；退出后没有接入自动恢复

- 位置：`composition.py::build_follow_engine_composition`、`engine.py::FollowEnginePort.start/poll/_refresh_worker_liveness`、`process_supervisor.py::ProcessSupervisor`。
- 源码确认：composition 直接装配 VisionProcessHandle 与 FollowControlProcessHandle，未装配已有 supervisor。start_stage completed 仅证明 Process.start 返回，不证明 capture/runtime 初始化完成或已收到首个有效帧。
- 源码确认：port 报告 worker error/exited，控制退出会中立输出，session 保留；没有 worker 自动重建。进程 is_alive=True 但长期不产生新 snapshot 的 stall 也没有 deadline。
- 影响：可能出现“已启动/等待恢复，但后面永远没有新位置”；不是业务跟随到达停止，而是底层 worker 无法继续。
- 修复方向：区分 spawned/ready/degraded/restarting；ready/stall deadline 只用于组件恢复，不作为跟随任务时间限制。自动重建有退避和错误证据，ring 损坏时整代替换，目标/session 保留；明确可重试和不可重试错误，避免无限快速重启。
- supervisor 独立缺陷（离线已复现）：_start_handle 调 start 抛错后仍保留 handle/token，状态为 stopped；下一次 start 可覆盖旧 handle。_schedule_restart 的 handle.stop 抛错也可中断退避状态设置。当前正式组合未接入该 supervisor，因此不能把此缺陷当当前实机根因；接入前必须先修复。

## 6. P2：构造失败在 start 回滚之前泄漏 ring

- 位置：`composition.py::build_follow_engine_composition`。
- 条件：ring 已创建，后续 processor/runtime factory 构造失败，例如 memory_source/transform 未成对、间隔非法。
- 离线结果：非法 memory pair 抛 ValueError 后，已分配 1 个 ring，open ring 数仍为 1；探针 finally 自行回收。
- 影响：尚未生成完整 composition，页面拿不到 owner；上一轮修复的 start 失败回滚覆盖不到此路径，重复失败可能残留资源。
- 修复方向：纯参数校验前置；构造资源用退出栈/try-finally，任何构造异常都回收已经创建的 ring/handles/outputs，再保留原错。

## 7. P2：未真正启动的 Process 仍被 join，清理再次报错

- 位置：`follow_control_process.py::FollowControlProcessHandle.start/stop`，vision 对应 handle 同结构。
- 条件：Process 对象已创建，但 start 因不可 pickle 的注入工厂等原因失败。
- 离线结果：local lambda factory 导致 start AttributeError，pid=None；stop 抛 AssertionError `can only join a started process`，process 引用仍保留。
- 影响：二次清理错误/残留引用；上层当前已保留原始启动异常，但 handle 自身生命周期仍不完整。不可 pickle factory 是注入扩展触发条件，不代表当前标准 factory 无法 pickle。
- 修复方向：显式 allocated/started 状态，pid/popen 存在才 join/terminate；finally 清空引用，资源 close 和 queue dispose 与正常可复用 stop 区分。

## 8. P2：UI 启动与停止仍同步等待

- 位置：页面 `_start_modular_follow_experiment/stop_follow_experiment` → port.start/stop → 两个 process handle。
- 源码确认：start 同步序列化大 payload（上一轮约 1s）；stop 默认每进程 join 2s，再 terminate 后 join 1s，串行两个 worker 合计可等待约 6s，随后还有输出 I/O/锁等待。不代表整个 stop 有严格 6s 上界。
- 修复方向：后台生命周期任务完成回调，UI 只显示阶段，按钮用明确状态管理；先安排输出中立，再清理 worker。不得强杀 Qt/UI 线程，不能仅用 sleep 掩盖。

## 已有保护与其他模块检查

- root main guard 与 bootstrap import purity/append 日志/退出码已有回归。
- port 启动失败尝试所有已进入 start 的组件，清理异常不遮蔽原始启动异常。
- 页面 owned start 失败会回收组合和 ring，角色选择已经修正。
- Vision/Control 的 structured error 不再被同次 stopped 覆盖；generation/sequence 与 latest-only 有回归。
- torchlight FollowService.stop 先检查 pid，未启动 process 不 join；还明确 cancel_join_thread/close queues，比 PoE2 handles 更完整。其 workers 有 parent_alive，PoE2 workers 当前未同样显式检查父存活。此项为生命周期完善建议，尚未做硬杀父进程实验。
- memory/global future.result 只有完成后 poll 调用，不是“每 tick 等待读内存”。这类代码不能仅看到 result 就认定阻塞。

## 验证与推荐顺序

离线故障注入：`python tools/debug/follow_lifecycle_audit_probe.py`。每场景独立子进程，外层 15s watchdog；所有输出为 fake，清理自身资源。第七个输入等待场景也可单独执行 `--scenario unexecuted_command_prediction`。这些是暴露现状的诊断，不是声称问题已修复的验收测试。

现有专项：bootstrap、port、supervisor、ring、Windows lifecycle、vision/control process、snapshot output、output scheduler、page startup、torchlight service、UAC：**45 passed / 23.04s**。日志隔离在 `data/diagnostics/20261008_follow_lifecycle_audit`。通过说明既有保护有效，不能覆盖本轮新增故障边界。

后续建议分批：

1. 锁中毒/资源完整回收：第 1、2、6、7 项；先故障回归，再改实现。
2. 实际执行反馈：第 3 项；覆盖 arm gate、Host 写入失败、恢复中立和视觉丢帧组合。
3. 输出与 UI 解耦：第 4、8 项；验证慢 I/O 不拖住 GUI，双角色隔离。
4. ready/stall/worker 重建：第 5 项；先修 supervisor 自身异常边界，再装配，保留连续 session，避免恢复循环。

本轮只有诊断脚本与文档变更。以上未修复项须明确保留，不能把此前“启动挂起根因修复”扩展为“所有跟随生命周期已无问题”。

## 修复状态（2026-10-08，离线验证）

本报告中的待办已按 R1–R5 实施；上文保留的是审查时的原始证据，不再表示这些条目仍未处理：

1. **R1 ring/资源回收：已修复。** ring 锁获取有 50ms 上限并在失败时标记 allocation broken；强制终止后的恢复必须替换整 ring。构造失败、未启动 Process、output stop/close 均采用有界/逐资源回收。原始七场景探针现全部可退出，`failed_composition` 的 open ring 为 0，`failed_process_start` 不保留 process，双 output 都 stop/close。
2. **R2 输出隔离：已修复。** `AsyncSnapshotOutput` 的 actor 独占同步 adapter，watchdog 可取消慢 Host I/O；scheduler 的 heartbeat/write/rearm 不再持有全局锁执行，按角色串行。arm gate 内没有 output receipt。
3. **R3 执行反馈：已修复。** `ExecutionReceipt` 经 output → `FollowEnginePort` → control process → runtime；只有成功 write 的 lease overlap 才积分位置。离线 6s arm gate/3s 缺帧场景输出创建数为 0 且位置保持 `(0, 0)`。
4. **R4 worker ready/stall/rebuild：已修复。** port 有启动 10s、运行 2s 的组件进展诊断；组合提供 rebuild factory 时会 neutralize、停止旧 worker、替换共享 ring 和 worker 并重放 target，session 不转为用户停止。`ProcessSupervisor` 的 start/stop/restart 异常也会清除失效 handle/token 并继续有界退避。
5. **R5 UI lifecycle：已修复。** concrete modular page 的 process start/stop 通过单线程 lifecycle executor 执行；Qt 线程只切换按钮/状态和轮询，不等待 Windows spawn/join/Host cleanup。fake/injected page 的同步契约保留用于离线测试。

### 本轮验证

- `python -m pytest -q tests/poe2_live_terrain`：562 passed。
- 页面/启动相关：`tests/test_poe2_capture_test_page.py` 107 passed，`test_follow_engine_page_startup.py` 6 passed；组合/端口/输出/回执聚焦共 125 passed。
- `python -m compileall -q src/auto_modules/features/poe2/live_terrain/experimental/follow_engine src/auto_modules/ui/modes/poe2_live_terrain`：通过。
- `python tools/debug/follow_lifecycle_audit_probe.py`：七场景均在 watchdog 内退出；arm-delay 场景 `host_outputs_created=0`、`predicted_position_during_arm_delay=[0.0,0.0]`。
- `tools/debug/follow_root_entry_probe.py --leader p1/p2`：两方向各 5 个完整 snapshot，startup 764.4ms/836.6ms；fake capture/recording output，无真实输入。

以上均为 fake/offline 验证，未启动 PoE2、未连接 Host/LAN、未读取真实内存、未发送真实手柄输入；真实游戏消费输入、长跑漂移和地图障碍仍需用户显式测试。
