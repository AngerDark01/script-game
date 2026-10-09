# PoE2 双人定位与自动跟随：10 月 7 日 17:21 后人工全链路审查

> 本文保留早期审查过程和当时的实现描述，含已被后续修改替代的target relay等链路。当前源码的最终结论、正常运行ROI变换修复和真实装配边界以 [POE2_FOLLOW_RUNTIME_CHAIN_AUDIT_20261009.md](POE2_FOLLOW_RUNTIME_CHAIN_AUDIT_20261009.md) 为准。历史接口只返回17:21那轮元数据、没有正文，不代表已恢复缺失聊天。

审查时间：2026-10-09。审查起点：`docs/POE2_FOLLOW_ROLLBACK_CHECKPOINT.md`、`ITERATION_LOG.md` 中 10 月 7 日 17:21 之后的记录，以及当前工作树源码。审查只使用源码、离线 fake/回放和聚焦契约检查，没有启动游戏、读取实时内存、连接 Host/LAN 或发送真实输入。

## 结论

这次 P2 滞后/漂移不能归结为单一“帧率太低”。重构后的链路有四个会叠加的时序风险：目标更新被旧 UI 快照覆盖，三条 multiprocessing 队列共用全局序号导致合法消息被丢弃，预测速度在视觉拒绝前被污染，以及输出 actor 重启与停止可能交叉。当前已修复这四个边界，并保留连续跟随语义：动态跟随没有业务时间上限，只有用户显式停止才能结束会话。

仍然需要实机确认两件事：Host 接受的回执不等于 PoE2 实际移动；以及当前地图路线、局部 ROI 和重建 worker 是否在真实截图尺度下保持坐标一致。

## 1. 当前项目结构

```text
src/auto_modules/features/poe2/live_terrain/experimental/follow_engine/
├── contracts.py                 # VisualObservation/FusionSnapshot/OutputIntent/计时 DTO
├── generation.py                # generation + map instance + 观察序号门控
├── engine.py                    # 父侧生命周期、poll、target policy、output/rebuild epoch
├── composition.py               # seed、SharedFrameRing、Vision/Control worker 组合
├── shared_frame_ring.py         # 原始截图跨进程 latest slot
├── worker_lifecycle.py          # 有界 stop、队列关闭、资源回收
├── vision/
│   ├── capture_adapter.py       # 捕获帧契约
│   ├── vision_process.py        # 30 FPS 左右 start-to-start 采集 worker
│   ├── dual_observation_processor.py # 墙体位移、marker 候选、双角色关联、坐标变换
│   ├── dual_association.py      # 位置/速度/几何优先、颜色软提示
│   ├── wall_processor.py        # 墙体位移估计
│   └── local_roi_search.py      # 预测 native 点附近的局部 marker 重锚
├── control/
│   ├── follow_control_process.py # Control worker、视觉融合、odometry、恢复、路线、target transport
│   ├── route_controller.py      # 直线控制器与可选 map-aware A* adapter
│   ├── command_odometry.py      # 只按执行回执积分位置预测
│   ├── position_fusion.py       # innovation gate 与视觉融合
│   ├── output_scheduler.py      # 每角色 Host lease/heartbeat/rearm/stop epoch
│   ├── snapshot_output.py       # FusionSnapshot 到 OutputIntent/ExecutionReceipt
│   └── async_output.py          # Host I/O actor 与 watchdog
├── tracking/                    # 角色状态、速度校准、预测状态
└── recovery/                    # local ROI、memory、global recovery 与 RecoveryPolicy

src/auto_modules/ui/modes/poe2_live_terrain/
├── capture_test_page.py         # 页面入口、timer、按钮和 concrete factory 注入
├── follow_engine_adapter.py     # 页面与 engine 的薄桥接；配置 live policy 后不再回写旧 snapshot target
└── follow_engine_page_composition.py # 真实 capture/Host/memory 的组合适配
```

依赖方向是 `vision/control/recovery/output foundation → FollowEnginePort → page adapter → Qt page`。Control 不导入 Qt，Vision 不导入 Host，Output 不写角色位置；唯一正常结束点是 page 的显式 stop。

## 2. 正常跟随时序

### 启动

1. 页面校验地图实例、双人首帧 native 位置、transform、marker profile 和角色/控制器映射。
2. `build_follow_engine_composition()` 创建同一地图实例的 SharedFrameRing、VisionProcessHandle、FollowControlProcessHandle 和 Output adapter。
3. `FollowEnginePort.start()` 生成 `GenerationToken(generation,map_instance)`，按 `control → vision → output` 启动并记录各阶段耗时；失败时逐项回收，保留原始异常。
4. Output adapter 在配置的 6 秒 arm gate 内建立 neutral lease；gate 只让程序等待用户切回游戏，不限制跟随总时长。
5. 页面 timer 周期由 `localization_fps` 推导，通常为 33ms；它只调用非阻塞 `engine.poll()`。

### 每个视觉周期

1. Vision worker 捕获 `CapturedFrame(generation,sequence,captured_at_ms,map_instance,payload)`。
2. `DualObservationProcessor.process()` 解码、提取墙体、估计 wall shift、更新 transform、提取 marker 候选，并以预测 screen 位置、速度、两角色几何和颜色软提示做关联。
3. 完整 payload 发布到 SharedFrameRing；事件队列只保留最新 observation/header，避免大图在 queue 中积压。
4. 父侧 `FollowEnginePort.poll()` 取最新 Vision event，向 Control 发送 visual；若配置 live policy，同一 observation 的可信 leader 位置在读取 Control snapshot 前唯一地写入 follower target。
5. 页面 adapter 在 engine policy 已绑定时不再从旧 `FusionSnapshot` 重写 target；这消除了一个 UI 周期的旧目标覆盖。

### 每个控制周期

1. Control worker 分别读取 visual、target、priority 三条队列。三条队列有独立序号门；target 按角色合并，visual 在一批消息中保留首帧和最新帧，priority 有限量消费。
2. 首次可信 visual 为每角色 seed；后续候选先经过 innovation gate。只有 accepted visual 才刷新 evidence、角色可见时间和速度校准 anchor。
3. 执行回执按 `accepted_at_ms + valid_for_ms` 的有效重叠区间积分 command odometry；计划中的向量、arm gate 中的 neutral、写入失败都不推进位置。
4. 视觉缺失时使用最后可信位置、执行回执、速度和不确定度继续预测；缺帧不会释放动态 follow session。
5. RecoveryPolicy 按 `visual → local ROI → memory → global` 的门槛决定纠偏；memory/global 成功结果按 role 绑定，只有实际返回 native 坐标的角色进入 recovered 分支；失败只进入 cooldown/backoff，不能把动态跟随转成一次性 arrived/stop。
6. RouteController 根据融合位置和最新 target 产生 waypoint/短脉冲。预测位置落入 arrival radius 而未被新鲜视觉或 recovery 确认时，发送低幅 corrective vector，不能中立结束。
7. Control 发布最新 FusionSnapshot；Output actor 只消费最新 snapshot。

## 3. 异常链路与量化边界

| 异常 | 触发证据 | 处理链 | 会否结束跟随 |
|---|---|---|---|
| marker 暂时丢失 | 当前 role 无可信候选；evidence age 增加 | 保留预测；下一帧继续关联；必要时 local ROI | 否 |
| 候选跳变/颜色污染 | innovation 超门或置信度低 | 不刷新 accepted anchor；保留旧位置；local ROI 等下一帧 | 否 |
| control/visual worker 无进展 | startup 10s 或 running 2s watchdog | 标记 stalled；若有 rebuild factory， detached 新代际并在 token/epoch 有效时 commit | 否，除非用户 stop |
| Host session expired/revoked | write/heartbeat 明确 session 错误 | 每 role I/O lock 内 rearm；engine output restart 由 epoch lock 串行，重放最新 snapshot | 否 |
| local ROI 无结果 | `RoiMatch.valid=False` | 记录耗时/原因，等待下一新帧；随后按 cooldown 进入 memory/global | 否 |
| memory/global 失败 | backend 返回 error/空角色结果 | 标记本 tick failed，记录 cooldown；预测和输出继续 | 否 |
| 预测到达但未确认 | `route.arrived=True` 且 state source 为 command | corrective pulse，等 accepted visual/recovery | 否 |
| 用户停止 | page stop button / window shutdown | epoch++、取消 rebuild、停 vision/control/output、unlink ring | 是 |

当前关键数值：Vision/Control 常用 33ms；Vision event queue=1；SharedFrameRing 默认 capacity=3、slot=4MiB；Control priority queue=8；target queue容量至少为角色数且按 role latest；Host heartbeat=100ms；arm gate=6000ms；memory cooldown 常用 8000ms；startup/stall watchdog=10000/2000ms。实际参数以 concrete factory 和页面配置为准。

## 4. 本轮修复的源码差异

1. `follow_control_process.py` 删除跨队列全局序号判断，改为 `visual/priority/target` 独立 sequence；target 在 parent 侧按 role 合并，Control tick 有限排空，保留首帧+最新视觉。
2. `engine.py` 增加 live target capture timestamp/confidence 门，output restart 与 stop 共用锁并检查 session epoch。
3. `follow_engine_adapter.py` 增加 engine policy ownership，避免旧 UI snapshot 覆盖新 target。
4. `FollowControlRuntime.apply_visual()` 只在 accepted 后更新速度校准和视觉 anchor，并删除重复 miss 计数。
5. `dual_observation_processor.py` 角色重现速度使用该角色 last-visible timestamp；native velocity 到 screen association 使用逆线性变换。
6. `async_output.py` 每个 actor 使用独立 watchdog stop event，避免快速重启时旧 watchdog 控制新 actor。

## 5. 已知未决问题与实机验证边界

- 回执只证明 Host adapter 接受了 pulse，不能证明 P2 在 PoE2 中实际移动；必须同时关联 Host ownership/controller、heartbeat、accepted receipt 和连续 minimap 位移。
- Worker rebuild 当前从初始 seed 重新构造 processor；若重建发生在地图已移动后，最新 transform/native anchor 的 handover 仍需补齐，否则可能产生重建后跳变。
- `EncodedMarkerRoiSearch` 当前以颜色候选为主，局部墙体几何校验仍有限；复杂颜色干扰需要真实帧回放确认。
- Control worker 内部仍顺序执行融合、recovery、route；这是为了避免共享状态打架，不应继续拆成多个进程，除非先定义不可变 observation/snapshot 契约和资源预算。
- 当前离线聚焦检查已通过 47 项 follow control/port/output 检查和 23 项 vision/runtime 检查；没有据此宣称真实游戏长图稳定。
