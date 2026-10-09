# PoE2 双人定位与自动跟随：修改后全链路审查结论

日期：2026-10-09  
范围：2026-10-07 17:21 断点之后的模块化双人定位/自动跟随链路  
验证边界：本轮只做源码推导、离线故障契约和聚焦回归；没有启动 PoE2、读取实时内存、连接 Host/LAN 或发送真实手柄输入。

历史可见性：历史接口返回了 10 月 7 日 17:21:19（北京时间）的 turn `01a115aa-d30d-7bc0-a552-451dcad07eda`，但其 `items=[]`。时间和状态可查，正文不可恢复。本报告结合相邻可见对话、任务计划、断点、Git 差异与当前源码，不声称读到了缺失的完整正文。18:32 的可见答复明确当时完成的是离线模块，页面/真实输出尚未接入。

## 结论

本次滞后的结构性原因有两项：

1. 动态跟随的 leader target 原先由父进程 `FollowEnginePort.poll()` 经 UI timer 再写入 Control target queue。Vision 和 Control 已经分进程，但目标刷新仍绕回 UI，造成一拍或多拍延迟；旧 target 还可能覆盖新视觉。
2. Control tick 内对两个失配角色串行执行 local ROI，并对需要重规划的角色同步执行 A*。即使 cadence 改成 start-to-start，单次 tick 过长仍会延迟新 target、snapshot 和 output receipt。

当前实现把动态 target ownership 下沉到 Control runtime，并对恢复/重规划做了每 tick 的工作预算。续读又复现并修复了三处遗漏：正常运行的 local ROI 没有逐帧同步 transform、ring 覆盖后把新图像配上旧变换、leader 恢复位置没有传播给 follower target。该设计解决的是消息时序、坐标一致性和双角色串行阻塞；真实 P2 是否按期消费输入仍需实机证据。

## 修改后的项目结构

```text
src/auto_modules/features/poe2/live_terrain/experimental/follow_engine/
├── contracts.py              # VisualObservation/FusionSnapshot/StageTiming/OutputIntent
├── generation.py             # generation token、sequence gate、clock
├── engine.py                 # UI 无关端口、代际、worker watchdog、output 生命周期
├── composition.py            # seed、ring、Vision/Control/Output 组合与 rebuild bundle
├── shared_frame_ring.py      # Vision -> Control 的 latest frame 共享环
├── execution_feedback.py     # Host accepted pulse 的不可变 receipt
├── control/
│   ├── follow_control_process.py # Control runtime、队列、预测、target、恢复、snapshot
│   ├── route_controller.py       # 直线/地图 A*、target 投影、缓存和单 tick replan budget
│   ├── output_scheduler.py       # role lease、heartbeat、rearm、stop epoch
│   ├── async_output.py           # latest-only writer actor 与 I/O watchdog
│   └── snapshot_output.py        # FusionSnapshot -> OutputIntent -> receipt
├── vision/
│   ├── vision_process.py         # capture/process start-to-start worker
│   ├── dual_observation_processor.py # wall、marker、双角色关联、transform
│   ├── dual_association.py       # 位置/速度/相对几何/颜色软评分
│   ├── marker_processor.py       # profile 候选提取
│   ├── wall_processor.py         # 墙体位移与质量
│   ├── local_roi_search.py       # 局部 marker 重捕获
│   └── capture_adapter.py        # spawn-safe 编码截图
├── tracking/
│   ├── command_odometry.py       # accepted lease overlap 积分
│   ├── position_fusion.py        # innovation gate
│   ├── tracking_state.py         # role state
│   └── velocity_calibrator.py    # trusted visual displacement 校速
└── recovery/
    ├── recovery_policy.py        # L0-L3 状态与量化升级
    ├── local_recovery.py         # bounded ROI
    ├── memory_recovery.py        # single-flight warm memory
    └── global_recovery.py        # generation/map guard + backoff

src/auto_modules/ui/modes/poe2_live_terrain/
├── follow_engine_page_composition.py # PoE2 capture/memory/Host adapter 注入
├── follow_engine_adapter.py          # Qt page bridge；正式动态 target relay 关闭
└── capture_test_page.py              # accepted seed、按钮、非阻塞 timer/lifecycle executor
```

## 正常执行链

### 1. 首帧和组合

`Poe2CaptureTestPage._ensure_modular_follow_adapter()` 只接受已通过的双人首帧，构造 `FollowSeedBundle`，包含：map instance、role/controller 映射、所有 observation role 的 native seed、screen seed、首帧 similarity transform 和 marker profile。

`build_poe2_follow_engine_page_adapter()` 创建 spawn-safe screenshot provider、编码 capture、wall extractor、`MapAwareRouteController`、可选 `Poe2DualPlayerPositionSource` factory 和 `AsyncSnapshotOutput`。此时不建立 Host lease。

### 2. 启动

`Poe2FollowEnginePageAdapter.start()` → `FollowEngineUiAdapter.start()` → `FollowEnginePort.start()`：

1. `FollowControlProcessHandle.start()`：绑定 generation/map 到 ring 后 spawn Control。
2. `VisionProcessHandle.start()`：重绑 processor/capture 会话后 spawn Vision。
3. `AsyncSnapshotOutput.start()`：启动writer actor；`SnapshotOutputAdapter`的10000ms arm gate尚未允许非零输出，但首个role intent到达后会prime零输入租约并保活。页面持续显示切回游戏倒计时，不因首snapshot隐藏。
4. Control runtime 如果配置 source/target policy，直接以 leader seed 预置 follower target。

启动阶段记录每个 `step=follow_engine.start_stage` 的耗时。worker watchdog 启动窗口为 10s；它只标记 worker fault/rebuild，不是跟随任务的时间限制。

### 3. Vision worker

`vision_process_entry()` 每轮：

1. 记录 start 时间并从 capture 取 `CapturedFrame(generation, sequence, captured_at_ms, payload)`。
2. `DualObservationProcessor.process()` 解码、提取 wall、估计 wall shift、提取颜色 marker、通过动态关联器分配 p1/p2，再把 screen 点变 native。
3. 有 ring 时 payload 写入 `SharedFrameRing.publish()`，队列事件只保留 observation/header。
4. 发送 latest-only observation；等待 `interval - processing_elapsed`，保持 start-to-start cadence。

30 FPS 默认约 33ms；处理超时会自然使周期变长，但不会再叠加一个完整 33ms。

### 4. Control worker：定位、target 和预测

`control_process_entry()` 每轮先按独立通道有限消费：target latest-by-role、priority FIFO、visual 首帧+最新帧。然后：

1. 父进程 `FollowEnginePort.poll()` 转发最新 observation 到 Control visual queue；`FollowControlRuntime.apply_visual()` 用 generation/sequence gate 接受 observation。事件传输仍依赖父侧轮询，消除的是旧 snapshot 再回写 target 的环路，不是消除了全部 UI 调度延迟。
2. 对每个 visible role 做 innovation fusion；只有 accepted 候选才能刷新 evidence、速度校准、odometry anchor。
3. 如果是动态跟随 source，accepted source 的融合 native 点立即写入 follower target。这一步与当前视觉在同一 Control 进程、同一 tick 内完成；父 UI 不再 relay。
4. 对没有 accepted evidence 的 role，保留 command odometry 预测；规划位置不被当成执行证据，只有 `ExecutionReceipt` 的有效时间段才积分。
5. `EncodedMarkerRoiSearch.bind_observation()` 同步该帧 transform。`_resolve_frame()` 精确读取相同 generation/map/sequence/captured_at 的图像；slot 已覆盖时不使用另一帧图像代替，跳过本次 ROI、维持 session，等待下一 observation。普通离线 callable 仍可使用不带 header 的显式 frame。

### 5. 恢复和路线

每个 tick 先 poll memory/global future，再进入 role 循环：

- 新视觉 frame 且 role 尚未尝试：按轮转索引只选一个 role 运行 `LocalRecoveryBackend.match()`；其它失配 role 继续预测并输出上一条有效方向。
- local 失败后仍保持 `session_active=True`，按 `RecoveryPolicy` 判断是否进入 prediction、memory 或 global。
- memory/global 的常量不是独立触发器，必须先经过下文的策略优先级。memory single-flight/cooldown 默认 8000ms；memory miss≥3、uncertainty≥50、age≥1500ms 是后段分支条件。
- global 策略有 age≥3000ms、uncertainty≥100、实例/transform 无效等条件；通用 runtime 支持注入 backend，但当前 concrete `SpawnSafeFollowRuntimeFactory` 没有装配 global backend。策略出现 global pending 不等于真实全局注册任务已启动。
- `MapAwareRouteController.plan()` 先判断 arrival radius=12；target 变化 ≥16、位置推进 ≥12 或偏离缓存走廊 ≥12 才需要 replan。每 tick 最多一个 controller 允许 `allow_replan=True`，其他 controller 使用缓存或 direct fallback。
- route 到达但没有新 visual/recovery 确认时，使用 `corrective_vector()` 继续短脉冲，不发送一次性业务停止。

### 6. Output 和回执

`FusionSnapshot.output_intents` → `AsyncSnapshotOutput.apply()`（只保留最新 snapshot）→ `SnapshotOutputAdapter` → `OutputScheduler`：

- arm gate 期间只 `prime_neutral()`，不写非零输入、不生成移动 odometry evidence。
- role output 在 gate 内即可懒建并 prime neutral；gate 结束后才提交移动向量，每次正常 Host write 成功生成 `ExecutionReceipt`。
- heartbeat 独立于 Control cadence；Host session 失效只触发 role rearm，不释放跟随 session。
- output actor I/O 超过 1.5s 由 watchdog 请求 cancellation；慢 I/O 不阻塞 UI poll。

父侧 `FollowEnginePort.poll()` 只回收最新 receipt 并发送 priority envelope；Control runtime 用 accepted_at/valid_for 的未消费时间重叠积分预测。

## 异常链和处理顺序

```text
候选存在但 fusion reject
  -> 不刷新 anchor/target/evidence
  -> 下一帧优先视觉/局部 ROI
  -> 预测继续输出

marker 暂时丢失
  -> visual_degraded/predicting
  -> 每 tick 最多一个 role local ROI
  -> memory cooldown 到期才 warm read
  -> global 仅在 backend 已注入且策略允许时提交（当前 concrete 未注入）

Host write/heartbeat 失败
  -> neutralize 当前输出
  -> role session rearm/backoff
  -> 保留 Vision/Control/target/session

worker 无进展/queue closed
  -> diagnostics 标记 stalled
  -> rebuild executor 退避构造 detached bundle
  -> session epoch/token 有效才 commit
  -> 迟到 bundle dispose；不把 worker fault 当用户 stop

用户点击停止
  -> page lifecycle serial
  -> FollowEnginePort session epoch++/cancel rebuild
  -> stop worker/output、清空 token、unlink ring
```

## 当前关键风险和验证边界

1. 单次局部 ROI 或 A* 自身若超过 33ms，仍会令当前 tick 超时；现在消除了双角色串行叠加，但没有中断一个已经运行的 Python/OpenCV 调用。需从 `StageTiming.local_ms/route_ms/total_ms` 真实记录确认。
2. `ExecutionReceipt` 只证明 Host 接受了输入，不能证明游戏窗口焦点正确、controller 已绑定 P2 或角色实际移动。
3. transform handover 与正常运行逐帧 ROI transform 都已补齐；rebuild 用最新 native seed + transform 重建 Vision/Control ROI，并清空旧 screen anchor。仍需实机验证地图滚动后重建的连续性。
4. 上一阶段 PoE2 专项 `600 passed` 是历史基线，不是续读修改后的全量结果。本次按用户要求不重跑全量：新增失败场景修复后及直接相关检查 `28 passed in 0.55s`；离线结果不等于真实 PoE2 验收。

## 2026-10-09 人工全链路复核收口

### 当前实际模块关系

```text
Qt 页面 timer（只轮询/显示）
  -> Poe2FollowEnginePageAdapter
  -> FollowEngineUiAdapter
  -> FollowEnginePort（session epoch、代际、worker watchdog）
       ├─ VisionProcess（独立进程）
       │    capture -> encode -> wall shift -> marker association
       │    -> VisualObservation(native roles + current transform)
       │    -> SharedFrameRing / latest-only event -> parent poll relay
       ├─ ControlProcess（独立进程）
       │    visual/target/priority 三通道
       │    -> accepted fusion -> source target same tick
       │    -> command odometry -> bounded recovery -> route
       │    -> FusionSnapshot / OutputIntent
       └─ AsyncSnapshotOutput（父进程 writer actor）
            -> SnapshotOutputAdapter -> OutputScheduler -> Host adapter
            -> ExecutionReceipt -> Control priority channel
```

### 当前正常时序和量化标准

1. 首帧只建立一次 `FollowSeedBundle`；包含 map instance、角色/控制器映射、native/screen seed、首帧 transform 和颜色 profile。运行阶段不重复做全图首帧注册。
2. Vision 和 Control 默认 start-to-start 约 33ms（30 FPS）；处理时间已经包含在周期内。Vision 队列 latest-only，Control 每轮最多保留视觉首帧和最新帧。
3. accepted source 视觉在 `FollowControlRuntime.apply_visual()` 内立即刷新 follower target；正式组合 `control_owns_live_targets=True`，页面不会再 relay 同一目标。
4. 新帧失配优先当前帧 bounded local ROI，每个 Control tick 只处理一个 role 并轮转。250/600/1500/3000ms 的含义和分支先后见下文，不能单凭常量推断调用了 backend。
5. 路由到达半径为 12 native 单位；目标变化≥16、位置推进≥12、走廊偏离≥12 才允许缓存路线失效；每 tick 最多一次 A* replan，其余角色使用缓存走廊或 bounded direct fallback。预测到达未被视觉确认时继续输出 corrective pulse，不释放跟随。
6. Concrete PoE2 output有10000ms arm gate，只禁止非零Host写入，不暂停Vision/Control；闸门内建立neutral lease，成功非零write才形成位移证据。输出I/O watchdog为1.5s；每个worker独立采用首次结果前10s、首次结果后2s门。poll先收集完成重建、读队列后判stall；重建期间不读旧队列。原始worker异常与重建原因落盘，first_fault保留到session结束。这些是组件恢复边界，不是跟随总时长限制。

### 本轮修复的重构后退化

- target relay 从 UI 下沉 Control，消除了 P1 observation 经过 UI timer 才到 P2 的额外一拍。
- Control cadence 改为 start-to-start，局部 ROI 与 A* 使用每 tick 配额，避免双角色异常时同步串行阻塞 target/output。
- accepted-only fusion/velocity calibration、execution receipt overlap odometry 和 predicted-arrival corrective pulse 避免错误候选或计划位移把 P2 推到 P1 前面。
- session epoch、独立通道序号、detached rebuild bundle、逐角色 output I/O lock 和 latest-only output actor 防止 stop/rebuild/heartbeat 互相污染。
- 本轮补齐 transform handover：动态墙体校正 transform 随 observation 交接；replacement Vision 与 local ROI 使用同一 transform，重建不再拿首帧 screen anchor 覆盖后段坐标。
- 续读修复：正常运行每次 accepted observation 也更新 local ROI transform；精确帧已覆盖则跳过该次局部搜索。local/memory/global 位置回填通过 `_refresh_live_target()` 更新 leader 的 follower 目标，不改静态点击目标。

### 仍须保留的边界

- receipt 证明的是 adapter/Host 接受了报告，不证明 PoE2 绑定了 controller 2 或角色实际位移；P2 是否消费输入必须通过用户授权的短距离实测确认。
- 单次 OpenCV ROI/A* 仍可能超过 33ms，只能从实机 `StageTiming` 判定是否需要进一步拆到独立 worker；不能用离线通过推断实时帧率。
- 真实 Windows spawn、PoE2 窗口焦点、暖内存 reader 独占性、地图滚动后 rebuild 连续性尚未在本轮执行。

## 重构前后差异与证据等级

| 环节 | 早期/重构过程的问题 | 当前实现 | 能证明的边界 |
| --- | --- | --- | --- |
| 模块接入 | 10月7日18:32仍是离线引擎，默认页面未接入 | 主窗口注入 concrete composition | 接入源码；不是游戏移动验收 |
| 采样/控制节拍 | 处理完再等完整 interval，30ms工作+33ms等待≈63ms周期 | 等待 max(0, interval−本轮耗时) | 源码确定；真实吞吐仍取决于处理耗时 |
| 动态目标 | UI 从旧 snapshot 再写 target queue | Control 接受 source visual 后立即更新 follower target | 消除旧快照回写；事件本身仍经过 parent poll |
| 双角色异常 | 同 tick 两次 ROI、多个 A* 同步叠加 | 每 tick 一个 ROI，最多一次 A* | 限制次数，不是33ms硬实时保证 |
| 预测 | 计划输入或错误候选可推动位置/速度 | receipt lease overlap积分，accepted视觉才校速 | receipt仍不证明游戏实际移动 |
| 生命周期 | disposed composition 被复用，旧 queue 被新 timer继续读取 | 串行页面生命周期、新资源、epoch/generation和迟到dispose | 离线竞态证据 |
| 地图滚动 | rebuild和正常ROI可能仍套首帧transform | rebuild交接+每帧bind_observation+exact frame绑定 | 离线平移样例从错误(30,40)改回(130,70) |
| leader恢复 | 角色位置更新，但 follower target停留原地 | 所有accepted恢复位置走_refresh_live_target | 正反P1/P2与三类恢复位置回填均验证 |

## 恢复策略的真实优先级

`recovery_policy.py::RecoveryPolicy.decide()` 按以下顺序首个命中即返回，不能把后面的常量理解为独立中断器：

1. 显式 user_stop 返回 STOP；session inactive 返回 HOLD；Host session异常返回 REARM_OUTPUT。
2. 本tick local/memory/global任一恢复成功，返回 TRACKING。
3. global或memory任务仍在执行，返回对应恢复中状态、保留session。HOLD是策略状态，不会令本tick路由自动释放输出。
4. 实例/transform无效，要求global；backend不存在时不会凭空启动任务。
5. 当前视觉被融合接受且证据年龄≤600ms，返回TRACKING。
6. 有观测且当前角色尚未尝试该sequence，要求LOCAL_RETRY；runtime轮转决定谁实际执行，不重复处理同一角色同一帧。
7. 有观测、年龄≤1500ms且本tick无memory失败，返回PREDICTING；这一分支优先于后面的miss/uncertainty门。
8. memory冷却就绪且不在执行，miss≥3、uncertainty≥50、age≥1500ms任一成立，并且本tickmemory没有失败，要求MEMORY_REANCHOR。
9. global失败、age≥3000ms、uncertainty≥100，或memory失败且冷却未就绪，要求GLOBAL_REANCHOR；实际提交仍要求已注入backend、single-flight空闲、退避结束。
10. 其余age>250ms或有miss返回VISUAL_DEGRADED，否则TRACKING。

`local_trigger_ms=600` 是配置字段，但当前新帧优先分支没有等待它；有新观测失配会立即请求局部搜索。`misses` 是控制tick未确认次数，不能等同于独立截图失败帧数。策略的 `frame_available` 当前指有VisualObservation；exact图像slot丢失会使局部搜索本轮返回未成功，然后进入下一策略分支，而不是把另一帧拿来配旧transform。

当前具体装配有local marker ROI、可选warm memory；没有接入全局注册backend。这里的ROI是预测位置附近的颜色候选搜索，并不等同于完整墙体几何重新配准。文档不能将这些通用能力写成全部已经在页面运行。

## 人工时序推演记录

### 正常与短暂失配

1. P1新截图seq=N进入Vision，当前墙体滚动生成T_N，角色关联生成native点。
2. parent poll转发N；Control序号门接受，绑定T_N。source视觉通过fusion即更新P2目标，不再等下一次UI target回写。
3. P2正常可见时纠正自身anchor；P2失配时按轮转，用图像N与T_N搜索。若N已被ring覆盖，不搜索图像N+2，等待其完整观测到达。
4. ROI恢复P1时，同步更新P2 target；ROI恢复P2时，只更新P2自身定位。反向跟随完全对称。若source排在本轮已规划follower之后，其新目标从下一Control tick用于规划，不承诺零延迟。
5. 输出actor只拿最新snapshot；成功写入后产生receipt，parent下次poll送priority queue；Control按有效区间推进预测。视觉恢复重设anchor，不把预测当观测。

### 停止、重建与资源交接

1. stop先使epoch失效并取消rebuild。角色输出锁串行化write/neutral/stop；迟到write必须重查epoch与port身份。
2. rebuild构造detached bundle，继承同代最新native与transform；只有当前epoch/token还有效才commit。
3. stop(A)未结束时，页面延后start(B)，不对已dispose的A handle重新start；迟到A回调不能覆盖B的页面引用。
4. 旧图像、旧恢复结果、旧snapshot不跨generation使用。关闭queue是worker fault，不能每33ms向Qt冒泡同一异常。

## 耗时的真实含义与现有记录

配置周期不是实测耗时。当前不能保证30FPS，也不能从计时字段默认0推断某个步骤免费。

| 数值/字段 | 当前实际含义 | 使用限制 |
| --- | --- | --- |
| 旧链路20:55处理EMA约31–35ms、有效约21.8FPS | 历史日志实测 | 不能当作修改后数据 |
| control启动699.192ms、vision启动73.178ms、整体774.342ms | 20:55历史接管日志 | 不包括完整游戏消费延迟 |
| arm_delay_ms=10000 | 测试切回游戏的10秒非零输出等待 | 零租约/心跳可提前建立；持续倒计时；不是跟随总时长限制 |
| interval≈33ms | Vision/Control目标start-to-start周期 | 超预算时周期会增长，不补跑积压帧 |
| observation.timing.capture_ms | processor内图像解码耗时 | 当前不是操作系统截图+编码的完整耗时 |
| wall_ms | 墙体提取与位移匹配 | 与marker/association为不同分段 |
| marker_ms / association_ms | 颜色候选提取 / 双角色关联 | 不包含消息排队 |
| snapshot.local_ms / prediction_ms / route_ms | Control tick内局部搜索 / receipt积分 / 路由 | 可用于识别同步重工作 |
| recovery_ms | poll backends耗时+local_ms | 与local_ms重叠，不能重复相加 |
| memory_ms / global_ms | 刚完成后台任务报告的耗时 | 异步任务时间，不等于当前tick阻塞时间 |
| fusion_ms / total_ms | 当前两者均填Control tick总耗时 | fusion_ms尚不是apply_visual的独立计时，不应误读为融合算法慢 |
| 输出I/O watchdog=1.5s | 超时取消请求门槛 | 不是正常写入耗时承诺 |

完整端到端延迟仍包括：截图/编码+Vision处理+等待parent poll+Control排队/处理+等待parent poll+Output排队/Host写入+游戏响应。target下沉只去除了多余的目标反馈环，未取消这些必要交接。下一次真实日志需按generation/sequence关联这些边界才能给出P50/P95/P99，当前没有修改后的实机分位数。

## 结构索引补充

上文目录图聚焦主链；其余实际文件如下，避免将辅助模块误认为都在热路径：

| 文件 | 责任 |
| --- | --- |
| `__init__.py` | 引擎公共导出 |
| `control/__init__.py` | 控制/输出类型导出 |
| `vision/__init__.py` | 视觉组件导出 |
| `tracking/__init__.py` | 定位状态/预测能力导出 |
| `recovery/__init__.py` | 恢复策略/backend导出 |
| `process_supervisor.py` | worker generation/watchdog状态 |
| `worker_lifecycle.py` | 有界worker停止和queue关闭 |
| `latest_frame_buffer.py` | latest-only缓冲辅助契约 |
| `replay.py` | 离线事件回放，不负责实机输出 |
| `ui_adapter.py` | 无Qt的页面命令/快照桥 |
| `control/control_diagnostics.py` | 控制阶段诊断聚合 |
| `vision/local_roi_matcher.py` | 80/140/220半径、0.55接受分的有限搜索 |
| `vision/poe2_monitor_capture.py` | 子进程内创建与关闭真实截图backend |

源码完整入口：`src/auto_modules/features/poe2/live_terrain/experimental/follow_engine/`。上述路径均相对此入口，UI的三个组合文件则见前面的独立目录。
