# PoE2 双人定位与自动跟随：当前真实运行链（2026-10-09）

> 历史版本归档：本文件的target relay、控制步骤顺序和恢复装配描述已被后续修正。阅读当前代码请直接使用 [最终源码审查与执行链](POE2_FOLLOW_RUNTIME_CHAIN_AUDIT_20261009.md)，其中包含正常运行逐帧ROI变换、恢复target回填、具体backend装配和真实计时字段含义。不要用本文件的旧描述指导修改。

本文按当前源码描述模块化跟随入口。它记录的是实际执行边界，不把离线 fake 输出当作游戏已经消费输入的证明。

## 1. 组成与职责

| 层 | 当前模块 | 责任 | 运行边界 |
|---|---|---|---|
| 页面 | `capture_test_page.py`、`follow_engine_page_composition.py` | 校验已接受的双人首帧、选择 leader/follower、创建和停止 composition、更新 UI | Qt 线程只提交生命周期和轮询，不执行 Host I/O |
| 页面桥 | `follow_engine_adapter.py`、`experimental/follow_engine/ui_adapter.py` | 把点击、开始、轮询、停止翻译为 engine 调用；配置通用 source-role → target-role 流 | 不识别图像、不规划路线、不持有手柄 |
| 端口 | `experimental/follow_engine/engine.py` | 管理 generation、Vision/Control/Output 三个 worker、最新事件、target 传播、回执转发、重建 | 无 PoE 业务规则；异常保持 session |
| VisionProcess | `vision/vision_process.py`、`dual_observation_processor.py` | 截图、墙体位移、候选提取、双人关联、局部观察 | Windows spawn 子进程；start-to-start cadence；事件队列容量 1 |
| ControlProcess | `control/follow_control_process.py` | 融合视觉、执行回执里程计、速度校准、恢复策略、路径和输出意图 | Windows spawn 子进程；控制 tick 默认 33ms |
| Output actor | `control/async_output.py`、`snapshot_output.py`、`output_scheduler.py` | latest-only 写入、Host lease、心跳、rearm、执行回执 | 独立线程；不阻塞页面和控制 tick |
| 共用基础 | `shared_frame_ring.py`、`generation.py`、`tracking/*`、`recovery/*` | 帧共享、代际/序列门控、里程计、融合、局部/内存/全局恢复 | 只接收显式 DTO 和 adapter |

当前 PoE composition 的实际装配顺序为：`SpawnSafePoe2MonitorCapture` → `EncodedImageCapture` → `DualObservationProcessor` → `VisionProcessHandle`；`MapAwareRouteController`、可选 `Poe2DualPlayerPositionSource` → `FollowControlProcessHandle`；`SnapshotOutputAdapter` → `AsyncSnapshotOutput` → `FollowEnginePort`。

## 2. 正常启动时序

1. 双人首帧页面先确认 map instance、两个 native seed、screen seed 和 similarity transform。未接受首帧时，模块化跟随不创建 worker。
2. 页面根据模式确定控制角色。`p1_leads` 的 source 是 P1，target 是 P2；`p2_leads` 相反。双人同目标模式没有 live source。
3. 页面先调用 `configure_live_follow()`，把 source role、target roles 和首帧位置写进 engine 的通用 target policy。
4. `FollowEnginePort.start()` 创建新的 `GenerationToken`，按 `control → vision → output` 记录 stage begin/completed 和耗时。每个组件失败都会逆序清理，原始异常保留。
5. Control 子进程建立 runtime 和角色状态；Vision 子进程建立 capture/processor 并开始采样；Output actor 只在线程中启动，不在页面线程等待 Host。
6. Vision 每帧按 `capture → process → publish` 执行。目标周期为 `max(16ms, round(1000/localization_fps))`，等待采用 start-to-start：本次处理耗时会占用周期，不再额外再等一个完整 interval。
7. `FollowEnginePort.poll()` 先取最新 Vision 事件，把 observation/共享帧送到 Control；同一轮立即从 observation 的 source role 提取最新 target，再轮询 Control snapshot。这样目标传播不再固定晚一个页面轮询周期。
8. Control 在一个 tick 开始时分别消费 visual、target、priority 三条通道：各通道使用自己的 sequence gate；target 按 role 合并最新值，visual 批次保留首帧和最新帧，priority 只按自身 FIFO 有界消费。随后一次性应用并生成一个最新 snapshot。target 通道不与 stop/recovery/execution 共用 FIFO。
9. Output actor 只保留最新 snapshot。`SnapshotOutputAdapter` 在 `arm_delay_ms=6000` 内创建并 prime 中立 lease，禁止非零输出；闸门结束后才写非零向量。六秒是用户切回 PoE2 的前台交接时间，不是地图运行时间限制。
10. 成功 Host write 产生 `ExecutionReceipt`。回执只证明 Host/adapter 接受了 pulse，不能证明游戏角色已经移动；下一轮 `FollowEnginePort.poll()` 转发给 Control 做里程计积分。

## 3. Control tick 的实际计算顺序

对每个观察角色执行：

1. 先轮询 memory/global future。成功只重置 role position/odometry/visual anchor，不释放目标和 session；失败进入冷却，避免每 tick 重复提交。
2. 消费尚未积分的 `ExecutionReceipt` lease。仅按 accepted time 与本 tick 的时间区间重叠积分，planned vector、无回执 pulse、arm gate 内中立 lease 都不会推进人物位置。
3. 处理最新视觉 observation。颜色只是候选辅助；角色位置、速度和双人相对几何由 Vision 关联器提供。
4. 对已关联且有足够置信度的位移更新 `VelocityCalibrator`。初始标量速度与 route controller 当前 magnitude 对齐；静止帧不把速度拖到零；真实位移会逐帧调整速度。
5. 视觉融合使用固定基础门 `20 native px`、当前 uncertainty 门和运动预算门三者最大值。运动预算约为 `calibrated_speed × visual_gap / 1000`，再加保护余量；因此低速实际人物不会因旧固定速度造成连续视觉拒绝。
6. 根据 `RecoveryPolicy` 依次走最新帧局部校正、短时 prediction、冷却内存锚点和低频全局锚点。所有这些状态都 `keep_session=True`。
7. 使用每角色独立的 route controller 规划。`MapAwareRouteController` 使用投影目标和地图路径；A* 无路时仍产生有界 direct pulse，让下一帧或局部恢复纠正，不把规划 miss 转换成停止。
8. 如果预测位置进入 arrival radius 但没有新的视觉/恢复确认，输出短幅 corrective pulse，状态保持 `FOLLOW_HOLD`/预测态；不能仅凭预测进入释放输出的 `WAITING_POSITION`。
9. 为受控角色生成 `OutputIntent`；观察-only leader 只进入 `roles`，不生成手柄 intent。

## 4. 异常和恢复链

### 视觉暂时失配

`frame available → local ROI retry → command prediction`。最后可信位置、速度、执行回执和不确定度继续工作；视觉失败不停止跟随。角色视觉年龄超过 memory/global 门槛时才异步提交相应锚点。下一帧重新接受后，odometry 和视觉 anchor 一起重置。

### P2 预测跑在实际位置前面

当前处理顺序是：真实视觉被关联 → 用实际位移更新速度 → 动态创新门吸收位置 → 重置 odometry。若仍未接受，uncertainty 会增长并进入局部/内存恢复，而不是无限使用固定速度继续前进。最终是否真实移动仍需游戏画面或内存事实验收。

### 输出/Host 租约失败

`AsyncSnapshotOutput` actor 记录失败并退出；engine 保持 Vision、Control、目标和恢复 session，按 250ms、500ms、1s、2s、4s、5s 上限退避重启 output actor，并重放最近 snapshot。只有用户显式 stop 才清理整个 follow session。

### worker queue closed、silent exit 或 stall

端口把关闭队列分类为 worker fault，记录 generation/worker state；2s running stall 或 10s startup stall 才触发有界 rebuild。rebuild 捕获 session epoch 和 cancel event，先停止旧 worker，再构造 detached bundle，校验仍属当前 session 后原子替换；迟到 bundle 只能自我 dispose。

### stop → start

`FollowEnginePort` 先取消 rebuild 并等待 retiring future；旧 generation 失效，旧 queue/ring/handle 不允许被新 session 复用。页面 lifecycle executor 串行化 start/stop，stale completion 不改变当前 UI 引用。

## 5. 当前参数和时间边界

| 参数 | 当前值/来源 | 作用 |
|---|---:|---|
| Vision/Control interval | `max(16ms, round(1000/localization_fps))`，常用 33ms | 目标采样和控制周期 |
| Vision event queue | 1 | 只保留最新 observation |
| Shared frame ring | capacity 3，slot 4 MiB | 共享原始图像，局部 ROI 读取 |
| Control visual queue | 16 | 视觉可替换；满时丢旧帧 |
| Control target queue | 至少角色数 | 父侧按 role 合并；正式 started path 独立于 priority 回执队列 |
| Control priority queue | 8 | execution/recovery/stop，不能被 target 驱逐 |
| Output heartbeat | 100ms | Host lease 心跳；按角色 I/O lock |
| Arm gate | 6000ms | 前台切换和中立 lease，不限制跟随时长 |
| Local ROI | `80/140/220` 逐级半径（现有 search） | 新帧优先的局部纠偏 |
| Memory recovery cooldown | 8000ms | 同一角色/会话低频内存锚点 |
| Startup stall | 10000ms | worker 首个进展 watchdog |
| Running stall | 2000ms | worker 无新进展 watchdog |
| Dynamic follow arrival | route controller arrival radius，当前 map controller 默认 12 | 预测到达只进入保持/纠偏，不释放 session |
| Speed calibration | 初始 `magnitude × 100`，仅 accepted visual 位移 EWMA，范围 1–500 | 纠正手柄实际速度与模型差异；拒绝候选不更新 |

## 6. 证据边界

已用 fake capture、离线 Windows spawn、recording output 和单元/组合回归验证消息代际、队列、动态速度、目标同轮传播、输出重试和资源回收。没有把这些结果当成 PoE2 已消费虚拟手柄的证明。真实验收仍要关联 `generation`、`first_vision_observation`、`first_control_snapshot`、`first_output_apply`、`ExecutionReceipt`、Host state heartbeat 与游戏内人物位移；没有这些证据时，不能把 P2 的实际滞后归因给单一算法参数。
# 当前文档状态

2026-10-09 的最终人工审查、模块结构、双进程边界、阈值和 transform handover 以 [POE2_FOLLOW_RUNTIME_CHAIN_AUDIT_20261009.md](POE2_FOLLOW_RUNTIME_CHAIN_AUDIT_20261009.md) 为准。本文件中的历史链路只用于解释重构前后的差异，不应作为当前实现的单独依据。
