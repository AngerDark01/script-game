# PoE2 跟随双通道与生命周期边界审查（2026-10-09）

## 审查结论

当前架构的“视觉通道”和“控制/预测通道”已经是两个 Windows spawn worker；输出是第三个线程边界。它们不会共享 Qt 控件、截图 provider 或 Host 句柄。前一轮实机暴露的 `queue closed` 属于旧代际 stop/dispose 竞态；当前 generation、ring、rebuild bundle 和页面 lifecycle executor 已有隔离。本轮又修正了跨队列 sequence gate、旧 snapshot target 覆盖、拒绝视觉污染速度模型和 actor watchdog 重启竞态。

本轮仍发现并修复了三个影响体验的边界：

1. 控制运行时已有 `VelocityCalibrator`，但从未接入实际 odometry，导致 fixed `magnitude*100` 把慢于模型的 P2 预测到目标前方，随后真实视觉被创新门拒绝。
2. 页面在控制 snapshot 之后才刷新 leader target，天然增加一个 UI poll 周期；执行回执爆发时，target 还会和回执共享 priority FIFO。
3. Output actor lease 失败会把整个 port 置 inactive，违背持续跟随只能由用户手动停止的契约。

## 1. 双通道互不打架的条件

| 数据 | 唯一写入方 | 消费方 | 门控 |
|---|---|---|---|
| `VisualObservation` | VisionProcess | ControlProcess | generation/map/sequence；latest-only |
| 原始帧 | VisionProcess → SharedFrameRing | Control local ROI | ring lock 50ms；generation/map 校验 |
| target | engine live policy（页面只负责配置 ownership） | ControlProcess | 独立通道；父侧按 role 合并最新值；target 通道 sequence |
| ExecutionReceipt | Output actor | ControlProcess | generation + priority 通道 sequence + role |
| FusionSnapshot | ControlProcess | Engine/Output actor/UI | latest-only；当前 handle/epoch |
| Host write | OutputScheduler 每 role I/O lock | Host adapter | epoch、stopping claim、port identity |

Vision 不读内存和手柄；Control 不直接调用 Qt/Host；Output 不反向修改角色位置。回执只代表 adapter 接受 pulse，不能被当作游戏移动事实。

## 2. 代际和生命周期检查

### 启动

`FollowEnginePort.start()` 为新 session 生成 token，阶段顺序为 control、vision、output。阶段失败时清理所有已尝试资源并保留原始异常。页面在模块化入口先等待旧 stop executor 完成，避免复用正在 dispose 的 composition。

### 正常运行

`poll()` 在不等待 worker 的前提下读取最新 Vision/Control 事件，检查 worker liveness 和 stall。普通视觉缺帧、控制错误、Host lease 错误不会调用用户 stop。worker stall 只在配置 rebuild factory 时替换 worker generation。

### rebuild

rebuild 在单线程 executor 运行。它捕获 `session_epoch`、token 和 cancel event；新 ring/handles 先 detached 构造和启动，只有 epoch、token、active 同时有效才 commit。旧 bundle 和迟到 bundle 都有 dispose 路径。`FollowEngineComposition.stop()` 读取 port 当前 handles，避免仍 dispose 构造时的旧 handles。

### stop → start

显式 stop 先标记 inactive、递增 epoch、取消 rebuild，再停止 Vision、Control、Output。超时 future 进入 retiring 集合；同一 port 下一次 start 在有界时间内等待，无法确认旧 future 退出时拒绝复用。generation/sequence gate 拒绝迟到消息。

## 3. 仍需重点观察的边界

### UI poll 不是实时控制时钟

页面 timer 常用 33ms，但它只是把 worker 最新结果桥接到 engine；控制 worker 自己按 33ms tick。若 Qt UI 被其他绘制或日志阻塞，target 仍会通过独立队列保留最新值，execution receipt 会延后但不会覆盖 target。若 UI 长时间完全不 poll，输出 actor仍会保留最近 snapshot，但回执不能及时回到控制侧；这会降低 odometry 校正速度，因此真实长期运行必须记录 UI drain age。

### Host receipt 与游戏消费边界

`ExecutionReceipt` 不能证明 PoE2 角色移动。Host 断联、controller 绑定错误、窗口焦点错误都可能出现“报告已提交、人物不动”。真实测试必须同时记录 Host ownership、controller id、state heartbeat 和连续游戏视觉位移。

### Recovery 不是业务停止

局部、内存、全局 recovery 的 failure 只进入冷却/退避。`RecoveryPolicy` 的 `keep_session` 对普通异常保持 true；动态跟随的目标变化不能进入一次性 `WAITING_POSITION` 释放逻辑。唯一正常终止入口是页面 stop。

## 4. 本轮修改后的回归边界

- 控制 runtime：只有 fusion 接受的视觉位移会更新每角色速度校准和 accepted anchor；拒绝候选不污染速度、不重复增加 miss。
- Control handle：真实进程使用独立 target queue；未启动 handle 为兼容旧调用者暂存到 priority control plane，正式 started path 始终使用 target channel；子进程按通道独立 sequence。
- Engine：同一轮 Vision observation 先传播 target，再轮询 Control snapshot。
- Output：异步 actor start/lease 失败后保留 active session，按退避重新 start 并重放最后 snapshot。

这些修改没有改变首帧几何匹配、人物半径、地图墙体膨胀或路径地图数据。它们只能改善模型和生命周期，不能在没有真实 Host/游戏证据时保证实际位移。

### 2026-10-09 第二轮复核补充

`DualObservationProcessor` 重新出现角色时使用该角色自己的 last-visible timestamp；native velocity 到 screen association 使用逆线性变换。Control tick 在高负载视觉批次中保留首帧和最新帧，避免首次 seed 被 partial 最新帧吞掉。聚焦离线检查为 47 项 control/port/output、23 项 vision/runtime；真实 Host/game consumption 仍未验证。
