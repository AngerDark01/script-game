# PoE2 双通道跟随引擎验收清单

更新时间：2026-10-09
当前代码状态：工作台入口 spawn 卡死、执行回执漂移、慢 Host I/O、worker 停滞、页面同步启停、动态 target relay 滞后和 rebuild transform 丢失已修复并通过离线回归；尚未完成修复后 R1 实机输入验收。

## 1. 当前交付边界

本阶段已经完成 M0–M8 的离线引擎基础设施，并完成了真实 PoE2 adapter 的 opt-in 组合：

- latest-only 视觉帧通道和 Windows spawn-safe VisionProcess；
- worker supervisor 的 generation 隔离、有界重启和退避终态；
- 独立控制进程、预测/融合、路径输出和 Host heartbeat 调度；
- 新帧优先的局部 ROI 恢复；
- 带 generation、地图实例和冷却的异步内存快速重锚；
- 单 generation 全局恢复 single-flight；
- 动态跟随异常只进入预测/保持/恢复，不自动释放 session；
- `FollowEnginePort`、页面 adapter、阶段耗时和离线 replay runner；
- 页面 adapter 的显式迁移桥接和控制进程 `runtime_factory` 注入；
- spawn-safe PoE2 小地图截图、双人首帧 seed、地图感知路线、暖内存快速重锚和 Host 输出工厂；
- SnapshotOutputAdapter 的 6 秒输出闸门；切回游戏前只建立中立 Host lease，不发送移动输入；
- 页面按 `localization_fps`（默认 30Hz）轮询 latest-only 结果；
- 当前 follow-engine 专项测试 `600 passed`；compileall 与 diff check 通过；尚未进行真实 PoE2/Host/内存/手柄消费验收。

当前明确的边界：

1. 模块化入口只在主窗口注入 `follow_engine_page_adapter_factory` 时启用；没有该注入时仍保留旧实验链路，避免两个 runtime 同时拥有 lease；
2. 真实 PoE2 capture、内存 reader 和 VirtualGamepad/Host 已有 opt-in 装配，但尚未在当前机器上完成 R1 实机验收；
3. 离线测试不能证明游戏实际消费了 controller 1/2 的报告，也不能替代门、窄道和完整地图测试；
4. 本文之外不允许把离线通过或“已接入”描述成“实机已通过”。

## 2. 离线验收门槛

每次提交后必须执行：

```text
pytest -q tests/poe2_live_terrain
python -m compileall -q src/auto_modules/features/poe2/live_terrain/experimental/follow_engine
git diff --check
```

必须满足：

- 全部测试通过；
- latest-only 槽容量固定，无无界图片队列；
- 视觉暂失、局部失败、内存失败、全局失败、Host session 失效和地图变化均不自动 stop；
- 只有显式 `FollowEnginePort.stop(reason="user")` 释放动态输出租约；
- 迟到 generation、逆序 sequence、旧 map instance 结果不能覆盖新会话；
- 全局恢复同一 generation 在结果被 poll 前最多一个任务；
- `StageTiming` 的所有阶段值有限、非负，且控制 tick 不等待 memory/global future；
- replay manifest `real_input_allowed=false`，离线 runner 不连接游戏、内存或 Host。

## 3. 真实输入 opt-in 前检查

真实 PoE2 测试必须由用户明确开启，并逐项确认：

1. 游戏窗口和 controller ownership 已确认；
2. Host 支持当前 `program.heartbeat` 和 session rearm 协议；
3. 当前地图实例、首帧 transform、角色身份均已记录；
4. 新旧输出链只有一个拥有 controller lease；
5. 页面 adapter 已由 fake 和 concrete spawn-style composition 通过；主窗口已注入真实 PoE2 composition 工厂，且旧入口与新入口互斥；
6. 日志包含 capture、wall、marker、association、local、prediction、memory、global、route、output、heartbeat、UI drain、total 各阶段耗时；
7. 用户知道测试期间可能发送手柄输入，并在游戏内准备安全位置。

## 4. 实机分级顺序

不允许直接从完整地图开始。按以下顺序逐级通过：

| 级别 | 场景 | 通过条件 |
|---|---|---|
| R1 | 双人静止、角色分离 | 首帧身份/地图一致，session 保持 |
| R2 | P1 单方向移动 | P2 跟随，视觉正常时不触发恢复 |
| R3 | P1 转向、短暂停留 | 目标变化不释放 session，进入范围只中立保持 |
| R4 | 单帧/短时视觉失配 | 最新帧局部重捕获优先，下一帧恢复 |
| R5 | 颜色污染/角色靠近 | 几何关联不交换身份，预测只作短时补充 |
| R6 | 内存快速重锚 | 只读一次双人位置，复用 transform，控制 tick 不阻塞 |
| R7 | Host session 失效 | heartbeat/rearm 恢复当前 controller，不重新创建跟随任务 |
| R8 | 门/窄道/复杂墙体 | 路径不因单次 `no_safe_route` 停机，能进入恢复/探索 |
| R9 | 地图实例变化 | 旧结果丢弃，异步全局恢复单飞，完成后原地恢复 |
| R10 | 完整地图 | 无时间硬限制；只有用户停止才结束 |

每一级都要保存：session id、generation、map instance、阶段耗时、恢复层级、视觉年龄、不确定度、Host 状态和 evidence 图片。

## 5. 回滚边界

- M0–M3：回滚到 `527d946` 不影响旧页面；
- M4：回滚到 `f858d84` 可去掉恢复 backend 接入，但保留旧策略测试；
- M5：默认页面切换前必须保留 feature flag，旧页面和新 port 不得同时拥有 output lease；
- M6–M7：只回滚代码，不删除用户运行 evidence；
- 任何真实输入异常先停止用户侧实验，再保留日志和 evidence，禁止用运行时文件覆盖代码判断。

## 6. 本次审计结论

模块化链路已经具备开始 R1 位置测试的条件：首帧 accepted 后由页面构造 seed，capture/vision/control 使用同一 generation、map instance 和 shared frame ring，leader 位置会持续刷新 follower target，控制快照先经过 6 秒输出闸门；首个 gated snapshot 会由 scheduler 建立中立 Host lease，闸门结束后直接发送最新移动意图并保持 heartbeat。worker、视觉、路径、内存和输出异常都不会把动态跟随误当作用户停止；只有显式停止按钮释放 session。

R1 仍必须由用户明确启动，并在安全位置验证真实截图、真实内存读取、Host ownership、controller 消费和首帧/静止双人状态。若 R1 失败，先保留日志/evidence 和 generation/session 信息，不回退或混跑旧链路。
## 7. 2026-10-08 实机启动故障修复与验收边界

14:31 会话首帧和旧双人实时正常，模块化启动后 GUI AppHangB1。根因是 bootstrap import-time 单实例退出破坏 Windows spawn，父线程阻塞在 Process.start/reduction.dump。已把日志/UAC/mutex/DPI/Qt 初始化移入显式 main，保留主 GUI 单实例保护；runtime.log 改为追加。

同时修复模块化双向跟随的受控角色反选、部分启动组件清理缺失与页面启动失败保留 ring；三个启动阶段记录耗时和错误，清理失败不遮蔽原始启动异常。

新增验证通过：真实 root main.py 的 Windows spawn 在 GUI mutex 已持有时接收 6MiB 参数；2093×2784 地图的两种 leader 模式均运行 capture→vision→ring→control→leader target→recording follower output，达到至少五个完整控制快照。本机两个方向 startup 约 1046ms/1013ms（单次离线测量，非持续性能保证）。这些测试使用静态截图及 recording output，无游戏/内存/Host 输入。

最新 PoE2 专项为 `600 passed`；最终入口、port、页面启动和 transform handover 均有离线覆盖。可重新开始 R1，必须重新启动工作台加载新入口；真实游戏消费、视觉漂移、地图滚动后 rebuild 连续性仍由后续实机证据验收。

## 8. 2026-10-08 生命周期修复边界

执行反馈、异步输出和 worker rebuild 已在 fake/offline 链路完成：计划方向不会单独推进位置，只有成功写入的带代际回执才会积分；输出 actor 与 heartbeat 不阻塞 Qt；worker startup/stall 仅触发组件重建，不终止跟随 session；页面 concrete modular start/stop 在 lifecycle executor 中执行。`tools/debug/follow_lifecycle_audit_probe.py` 的七项故障场景均在 watchdog 内完成，arm gate 场景位置保持不变。

这些结果不等同于真实 Host 消费 controller 报告。用户实际测试时仍按 R1→R10 逐级进行，若发生异常保留最新 session/generation、阶段耗时、worker rebuild 和 Host diagnostics；没有用户明确停止不会因业务地图耗时结束。

## 9. 2026-10-08 并发边界修复结果

本批补齐了最终静态审查发现的三类边界：

- worker 重建带 session epoch/cancel event，composition 返回 detached `RebuildBundle`，旧代际不会在 stop→start 后覆盖新 worker/ring；迟到 bundle 会 dispose。
- scheduler 对 apply、heartbeat、stop 做角色级锁与停止后二次状态校验，慢角色不会阻塞全局诊断，迟到输出不会重新 arm 已停止角色。
- global recovery 的 poll 校验 generation/map instance，并沿 control tick 传递统一 `now_ms`，异常退避不会因为时钟来源不同而失效。

新增竞态回归与原有测试合计：`pytest -q tests/poe2_live_terrain` 在补充 map instance 回灌回归前为 `574 passed`，补充后为 `575 passed`；compileall 和 diff check 通过。全仓上一轮为 `1269 passed, 2 skipped, 1 failed`，唯一失败是测试环境没有安装 `pydirectinput` 的 distribution 依赖检查。仍未进行真实 PoE2、Host、内存或手柄验收。
