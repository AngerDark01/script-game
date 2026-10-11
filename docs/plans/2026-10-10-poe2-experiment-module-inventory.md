# PoE2 实验定位与跟随：模块功能拆解和复用盘点

状态：设计盘点，2026-10-10。基线代码 `65dff05`，成功会话记录 `5607475`。本文件只描述当前源码和候选边界，不代表已经迁移。

## 1. 范围和术语

范围为双人首帧定位成功后，两个角色的实时定位、P1/P2 任一方跟随另一方、两人同目标导航，以及截图、共享地图、程序手柄、局部和内存纠偏之间的运行链。当前控制角色可为一个或两个；观察角色集合可以比控制角色集合大。地图统一使用 PoE2 `native` 坐标；屏幕小地图、内存原始坐标和手柄轴是三个不同坐标域。

“通用”表示功能契约不包含 PoE2、P1/P2、颜色配置、控制器编号和具体恢复阈值，且存在稳定复用场景；“PoE2 适配”表示必须知道 PoE2 的地图、图色、内存或手柄轴变换；“业务策略”表示连续跟随、目标来源、到达保持和恢复升级规则。先确认这些边界，再决定是否移动文件。

## 2. 当前真实执行链

```text
实验页 start_follow_experiment
  → follow_engine_page_composition.build_follow_seed_from_dual_result
  → build_poe2_follow_engine_page_adapter
      → PoE2 monitor capture / wall extractor / marker profiles
      → LegacyDynamicFollowRouteController + map
      → optional dual-player memory source + native transform
      → SnapshotOutputAdapter → AsyncSnapshotOutput → ProgramGamepadOutput
  → follow_engine.composition.build_follow_engine_composition
      → SharedFrameRing + VisionProcessHandle + FollowControlProcessHandle
      → FollowEnginePort + parent relay
  → Vision: screenshot → same-frame wall shift + marker candidates + association
  → Control: generation/sequence gate → visual/receipt fusion → recovery → target → route → OutputIntent
  → parent: output apply/transport receipt → Control; preview/status → UI
```

关键事实：动态目标在 Control 内由已接受的 leader 位置刷新，不必经过 UI timer；`ExecutionReceipt` 只证明输出传输被接收，下一视觉位移才提供实际运动观测；重建后必须携带最新位置和变换，不能复用首帧屏幕锚点。上述可由 `follow_engine/composition.py`、`engine.py::_poll_once_unlocked`、`control/follow_control_process.py::apply_visual/tick`、`ui/modes/poe2_live_terrain/follow_engine_page_composition.py` 核对。

## 3. 功能单元和目标归属

| 当前单元 | 已承担的职责 | 已有正式能力 / 差异 | 建议归属与处理 |
| --- | --- | --- | --- |
| `multiplayer_localization/dual_first_frame.py`、`memory_anchors.py` | 双角色首帧候选、地图配准和原始内存锚点 | `core.localization` 有单/多标记定位接口，但当前 PoE2 相似变换和内存契约特有 | PoE2 feature 保留配准编排和读取 adapter；点/变换数学可复用 `core.localization` |
| `follow_engine/composition.py::FollowSeedBundle` | 验证实例、观察/受控角色、native/screen位置、变换、颜色配置 | 含 PoE2 类型 `SimilarityTransform2D`、`MarkerColorProfile` | 拆成通用 session seed + PoE2 marker/transform seed；构造归 PoE2 feature composition |
| `vision/capture_adapter.py`、`vision/vision_process.py` | 带时戳帧、捕获协议、独立 Vision worker、最新帧输出 | `core.spatial`/platform capture已有屏幕几何和截图；缺连续流协议 | 帧元数据、最新帧队列/worker 可升为 application 运行时；截图实现留 adapters |
| `vision/poe2_monitor_capture.py` | PoE2 监控区域、HSV墙体提取 | 已调用正式 `SquareScreenCapture`、`MonitorBinding`、`HSVRecognizer` | 保留 PoE2 capture adapter/配置，不下沉游戏图色参数 |
| `vision/wall_processor.py` | 同帧墙体位移和质量估计 | `core.localization.estimate_bounded_displacement` 已存在 | 使用已有 core 原语；PoE2 墙体门限/掩码解释留 feature |
| `vision/marker_processor.py`、`multiplayer_localization/marker_candidates.py` | 颜色候选提取、面积/身份属性 | `core.perception` 有 detector/profile，但目前 PoE2 色标是具体配置 | 可将无游戏名的候选模型/几何过滤复用；颜色阈值、面积48等留PoE2配置 |
| `marker_association.py`、`vision/dual_association.py` | 动态门限、颜色软评分、双角色几何、二帧远点确认 | `core.localization.MultiMarkerLocalizer` 有同帧位置组合，但没有这些连续身份规则 | 先保留 PoE2 实现；若第二真实调用方需要，抽成“多目标时序关联”core算法，PoE2提供评分参数 |
| `vision/dual_observation_processor.py` | 同一帧墙体、屏幕/native变换、角色候选、耗时 | `core.localization` 有配准和位移工具 | 作为 PoE2 视觉 pipeline 组合现有 core；不把颜色/角色规则塞入 core |
| `vision/local_roi_search.py`、`local_roi_matcher.py` | 丢失后利用当前帧和预测位置局部找回 | 局部搜索概念可复用，像素面积/身份筛选有业务约束 | 抽通用局部搜索接口；PoE2 提供候选生成与身份策略，禁止 ROI 绕过二帧确认 |
| `tracking/position_fusion.py`、`command_odometry.py`、`velocity_calibrator.py` | 数学预测、创新门、命令积分、不确定度和实测速度 | `core.localization` 有部分观测/位移，但无 receipt 驱动闭环 | 纯数学和 DTO 候选下沉 `core.localization/tracking`；参数从上层注入；需双调用方或明确导航复用 |
| `tracking/tracking_state.py` | 单角色可信位置、视觉年龄、来源 | 正式 `LocalizationResult` 非持续多源状态 | 通用 `TrackedPosition` 契约可进入 core；运行时实例状态放 application |
| `control/follow_control_process.py::FollowControlRuntime` | 接受视觉、回放回执、融合、速度学习、目标刷新、恢复协调、逐角色路径输出 | 同时包含通用估计器和跟随策略；这是状态中心 | 拆出应用级 per-agent tracking runtime 与 navigation task orchestration；PoE2 follow strategy 只提供 leader→target、阈值和配置。迁移前不改既有行为 |
| `control/route_controller.py` | 旧实验导航适配、地图路线缓存、降级方向、停近规则 | `core.routing.PathFinder`、Torchlight `FollowerPlanner` 已复用 A* | 底层只保留 `PathFinder`/几何；通用 navigation task 可接收 planner/controller；PoE2 路由策略与现参数留 feature。当前实际 UI 使用 `LegacyDynamicFollowRouteController`，非仅 `MapAwareRouteController` |
| `multiplayer_follow/runtime.py` 及 `closed_loop_controller.py` | 历史但仍被 legacy adapter 调用的跟随导航和避障 | Torchlight follow有独立业务控制器 | 逐函数对比，不可因名为 legacy 就删除；先用等价契约接管唯一实际调用，再移除旧接口 |
| `recovery/recovery_policy.py` | L0视觉、L1局部、L2内存、L3全局的升级与 hold/continue | 正式项目有导航恢复，但阈值/持续跟随语义并不一致 | 通用恢复动作/任务调度可入 application；具体升级条件和禁止自动停止属PoE2跟随策略 |
| `recovery/local_recovery.py`、`memory_recovery.py`、`global_recovery.py` | 异步恢复 backend、结果和冷却 | 内存读取与地图配准是PoE2特有 | 通用异步恢复端口/一次性 in-flight 机制可入 application；具体 backend 留 PoE2/adapters；未装配的 global 不能写成已可用 |
| `shared_frame_ring.py`、`latest_frame_buffer.py`、`relay.py`、`process_supervisor.py`、`generation.py`、`worker_lifecycle.py` | 共享帧、最新值、worker代际、父进程队列和重启 | 跨业务可复用，须避免携带 `FusionSnapshot`/角色术语 | application/concurrency候选；进程退出、队列关闭、代际交接集中一个owner；UI不直接操作worker |
| `contracts.py`、`execution_feedback.py` | Frame/Visual/Prediction/Fusion/Intent/Receipt typed DTO，实例、时戳、序号 | 正式 `core.localization`/`core.spatial` 有一些坐标与结果DTO | 去重而非平移整文件：通用 frame/position/intent/receipt 契约入 core/application；PoE2扩展保留feature；版本化和显式坐标系 |
| `control/output_scheduler.py`、`snapshot_output.py`、`async_output.py` | 每角色lease、neutral、heartbeat、Host重arm、异步最新intent、回执 | 正式 `adapters.virtual_gamepad.ProgramGamepadOutput`已有Host会话和心跳 | application 层通用多控制器状态调度；adapter只执行Host I/O。`OutputScheduler.apply(FusionSnapshot)`须解耦为通用intent批次 |
| `diagnostic_events.py`、`timing.py`、`replay.py` | 有界事件日志、stage计时、回放 | 正式项目已有日志和采样工具但非全同 | 先保留有界采样；通用事件/耗时契约可被多runtime复用，PoE2日志字段留业务装配 |
| `ui/modes/poe2_live_terrain/follow_engine_page_composition.py`、`follow_engine_adapter.py`、`capture_test_page.py` | 构建真实依赖、按钮生命周期、预览/日志/地图 | 正式PoE2 `page.py` 已有产品定位，当前实验页含运行装配 | 将装配移到 PoE2 feature composition/application factory；UI仅发 start/stop/target 和消费 read-only view model；实验控件最后迁移 |

## 4. 应保护的成功行为与未验证边界

2026-10-09 22:06–22:09 前台实测通过：Vision与Control持续推进，P1已接受视觉位置在Control同tick成为P2目标；22:07:33 seq1294确认P2远点，Control把约69 native单位的位置差纠回；真实跟随体验由用户确认。首帧与图色的具体门限、PoE2输出基底、路径参数、heartbeat/neutral行为都应保留为迁移对照。用户说明末尾先切到别的窗口；22:09:15 worker stall/rebuild 是“切走后场景”，不能当作前台成功段的失败率，也不能因此忽略后台生命周期测试。

仍须区分：Host接受report ≠ 游戏已消费，视觉位移是独立证据；有GlobalRecoveryBackend类 ≠ 已装配。运行日志样本不是逐帧全量，性能/异常率只能以明确采样范围陈述。

## 5. 决策原则

1. 已有正式能力先复用或加窄接口；不新建第二套A*、截图或虚拟手柄协议。
2. 纯数学可先提取；状态拥有者与进程生命周期晚于契约确定；业务策略最后切换。
3. 相似名称不代表相同语义：PoE2跟随“当前leader位置”、Torchlight“滞后轨迹目标”、同目标导航“鼠标固定目标”共用导航任务机制，但目标策略不同。
4. 当某能力只有PoE2一个真正调用方，先保留在PoE2并写端口。仅为“看起来通用”而移动文件会增大依赖成本。
5. 方案、下一次实现和验收见另外两份文档。
