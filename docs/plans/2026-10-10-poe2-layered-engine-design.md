# PoE2 定位与导航能力逐层组合方案

状态：待用户审阅的设计稿；未改动源码。依据：`ARCHITECTURE_GUIDE.md`、当前 `core/localization`、`core/routing`、`adapters/virtual_gamepad`、Torchlight 跟随源码和实验链。现状盘点见同日 `poe2-experiment-module-inventory.md`。

## 1. 设计目标

把已经成功的 PoE2 双人实时定位和跟随整理为能组合的能力：固定点导航、P1→P2/P2→P1、两人同目标和将来另一设备传来的共享地图位置，共用一个“可信位置→导航任务→控制意图→输出反馈”闭环。业务只改变目标来源、受控角色集合和会话策略。视觉、预测和内存各提供证据，不由 UI 决定谁是真实位置。

本轮只定义目标，源码在方案确认后另行逐阶段迁移。现有 `65dff05` 保持可启动、可切回；不利用设计工作顺带调半径、阈值、摇杆持续时间、地图坐标或输出节奏。

## 2. 分层与依赖

```text
features/poe2/live_terrain/{localization,follow,navigation,composition}
  双人颜色与身份、初始配准、同实例地图、leader target策略、
  PoE2 native↔屏幕/内存/手柄映射、具体恢复阈值、角色映射
                     ↓
application/{tracking,navigation,worker_runtime,controller_output}
  多源位置状态、持续导航任务、回执归因、恢复请求/结果编排、
  worker生命周期、最新帧与代际交接、输出租约调度
                     ↓
core/{perception,localization,routing,mapping,spatial,shared}
  纯候选/关联数学、位移/融合、路径/自由空间/几何、
  坐标系和不可变DTO；不导入游戏/Host/UI

adapters/{platform,virtual_gamepad,poe2_live_terrain}
  实际截图、内存读取、Host命名管道和手柄状态写入

ui/modes/poe2_live_terrain → PoE2 composition 的 start/stop/target/status
bootstrap → 只装配进程、权限、日志和单实例
```

`application` 消费 `core` 提供的纯接口，并通过注入的端口调用 `adapters`。PoE2 feature是最高层业务组合者，依赖这些稳定接口。`core` 与 `application` 不反向导入 `features`。已存在的 `core.routing.PathFinder`/几何、`core.localization` 位移与注册、`ProgramGamepadOutput` 直接复用，不另造相同功能。

## 3. 建议的稳定契约

以下名称是接口草案，不表示源码里已经存在；实际迁移前检查与现有DTO/公开API重合。

| 契约 | 最小字段/方法 | 状态owner/禁止事项 |
| --- | --- | --- |
| `SessionIdentity` | `session_id`, `map_instance`, `generation`, `coordinate_frame_id` | application session owner 生成；旧代结果不得混入新地图 |
| `FrameEvidence` | `sequence`, `captured_at_ms`, `map_instance`, `coordinate_frame_id`, immutable image handle | Vision worker产生；图像/注册/角色候选必须来自同帧 |
| `PositionEvidence` | `role_id`, `position`, `coordinate_space`, `captured_at_ms`, `uncertainty`, `confidence`, `source`, `sequence` | Vision/Memory/Execution各自产证据，不直接写最终坐标 |
| `TrackedPosition` | `position_native`, `velocity`, `uncertainty`, `last_visual_at_ms`, `updated_at_ms`, `source`, `accepted_evidence_id` | 每角色一个 tracking runtime owner；UI和目标策略只读 |
| `NavigationTarget` | `position_native`, `map_instance`, `revision`, `source_id`, `updated_at_ms`, `policy_id` | 目标策略提供；leader、鼠标、远端设备只差 provider；revision只在内容变化时增加 |
| `MotionIntent` | `role_id`, `controller_id`, `vector`, `duration_ms`, `ttl_ms`, `control_tick`, `target_revision`, `visual_sequence`, `generation` | 控制层产出；不能调用Host；坐标域明确为 native vector |
| `ExecutionReceipt` | intent关联键、`accepted_at_ms`, `valid_for_ms`, `transport_status`, `sequence` | 输出adapter回报transport事实；不得直接宣称游戏移动 |
| `RecoveryRequest/Result` | `kind`, `role_ids`, `generation`, `map_instance`, `frame_sequence`, `deadline`, 结果/耗时 | application协调一次in-flight；backend可为局部视觉/内存/全局；没有配置时明确`unavailable` |
| `RuntimeHealth` | worker进度年龄、队列深度、帧年龄、Host租约状态、最后错误与重建代次 | 单一监督者判定；UI只展示 |

坐标域和时间戳要从名称与类型上可区分。`capture_at_ms`用于视觉物理时刻，`accepted_at_ms`用于Host写入时刻，`now_ms`用于控制tick；不得用UI接收时间替代图像采样时间。注册变换版本必须随worker handover刷新，局部ROI不能拿新帧配旧transform。

## 4. 基础能力如何抽取

### 4.1 帧、地图和视觉

正式 `core.spatial`/`core.localization` 已定义截图几何、配准与位移；保留这些入口。新增的纯能力只覆盖当前缺口：有界多目标候选关联、时间连续性、同帧变换校验。PoE2 feature注入色彩profile、候选面积约束、身份hint、墙体mask与配准变换。`48px²`和二帧`24px`阈值先作为 PoE2 profile，而非Core默认；缩放变化通过profile标定。

Vision工作进程只生成 `FrameEvidence + PositionEvidence[] + MapRegistrationEvidence`。它不能决定手柄方向、到达状态或内存读取时机。局部ROI是接收“新帧 + 预测位置 + 角色身份”的查询能力；它必须服从候选身份确认状态。只有一帧异常时使用下一帧重试，不能把旧帧与新变换混合。

### 4.2 预测、融合和状态

`core.localization`候选纯函数：`integrate_command`、`predict_position`、`fuse_observation`、`grow_uncertainty`。application的 `TrackedRoleRuntime` 独占每个角色的速度标定、receipt窗口、最后可信视觉锚点和位置估计。融合顺序固定为：先验证session/序号，再把预测状态倒推到视觉采样时刻，再对候选做创新门和二帧确认，再接受观测并重放之后的执行回执。被拒绝的颜色候选不能更新anchor或速度；确认纠偏大跳变不能被学成真实高速运动。

视觉与预测是独立的数据生产链，但最终状态只有一个 owner；不建立两套互相覆盖的“当前人物位置”。Memory只在策略要求时提供新锚点，带来源/置信/代次；局部视觉优先于内存兜底。多设备目标的位置也是目标证据，绝不写成角色自身定位。

### 4.3 导航和持续目标

`core.routing`拥有 A*、路线几何、局部自由空间，不知“P1跟P2”。application导航任务接收 `TrackedPosition`、`NavigationTarget` 和地图视图，返回 `MotionIntent` 或 `FOLLOW_HOLD`。相同导航内核处理“一个受控角色到点击点”、“两角色到点击点”、“一个受控角色跟随持续变化目标”。目标provider分别为 `StaticMapClickTarget`、`LeaderPositionTarget`、未来 `RemotePeerPositionTarget`；后者要求同实例地图ID与新鲜度，并通过正式 `application.communication`传输。

“到目标附近”在持续跟随里只产生 neutral/hold，保留session、心跳、目标订阅与状态；只有用户stop或明确实例失效的产品级操作结束会话。路线输入必须是已旋转的native坐标；native vector经PoE2输入基底一次性映射到手柄轴，不再次套用屏幕角度。

### 4.4 恢复与输出

通用恢复调度器只负责请求去重、并发限制、超时、取消、代次隔离和结果交付。PoE2跟随策略保持现有L0/L1/L2/L3条件：视觉丢失→新帧局部尝试→继续预测→约1500ms或miss/不确定度达阈值时可请求内存→约3000ms/高不确定度时请求全局。实际阈值见 `RecoveryPolicyConfig`，这些数值不能被低层泛化。后台失焦处理单列策略，不以切走后的stall否定前台成功链。

application controller output接受 `MotionIntent` 批次，拥有每控制器lease、neutral、心跳和rearm状态；adapters.virtual_gamepad继续负责实际Host I/O。移除 `OutputScheduler` 对 `FusionSnapshot` 的直接依赖，避免输出底层知道融合细节。会话恢复只重建对应层，Host session过期不自动触发地图全局重定位。每个角色/控制器拥有自己的缓存与锁；一个角色慢I/O不能阻塞另一个角色或UI状态读取。

## 5. 目标装配方式

### 建议包布局（规划，不是已创建目录）

| 建议位置 | 放入能力 | 现有文件迁移关系 |
| --- | --- | --- |
| `core/localization/tracking/` | 纯预测、融合、命令位移积分、不确定度计算及其只读结果 | 从实验 `tracking/position_fusion.py`、`command_odometry.py` 选纯逻辑，先对齐 `core.localization` 已有接口 |
| `core/perception/association/` | 不含PoE2颜色阈值的时序多候选关联原语 | 从 `marker_association.py` 仅提炼几何/时间与评分算法，成立条件是确认第二调用方 |
| `application/tracking/` | 每角色单owner的持续位置状态、视觉/receipt归并与纠偏 | 分解 `FollowControlRuntime.apply_visual`、`record_execution` 中的状态段 |
| `application/navigation/` | 持续目标任务、路线刷新、意图生成、保持而不停止 | 组合现有 `core.routing` 与目标provider接口；从Control中分离任务编排 |
| `application/worker_runtime/` | 帧transport、worker代际、进度监督与交接 | `SharedFrameRing`、`process_supervisor`、`relay` 的通用部分 |
| `application/controller_output/` | 按控制器租约、心跳、中性、回执与异步输出 | `OutputScheduler`、`AsyncSnapshotOutput` 的通用部分，改为只接意图批次 |
| `features/poe2/live_terrain/{localization,follow,navigation}/` | PoE2颜色/双人配准、目标策略、墙体/门路由参数、恢复阈值 | 当前实验 `dual_observation_processor`、`DualRoleAssociator`、`RecoveryPolicyConfig` 等PoE2组合 |
| `features/poe2/live_terrain/composition.py` | PoE2运行组合和真实适配器注入 | 取代UI侧 `follow_engine_page_composition.py` 的装配责任 |
| `adapters/poe2_live_terrain/`、`adapters/virtual_gamepad/` | 游戏内存读取、屏幕截图、Host I/O与输入基底适配 | 复用现有adapter，缺口新增窄接口，不移动业务策略 |
| `ui/modes/poe2_live_terrain/` | 开始/停止/目标点击、状态和预览 | 保留UI，删去运行时构造和直接worker所有权 |

这是一张功能归属图，不是逐文件机械搬运清单。例如`FollowControlRuntime`横跨 tracking/navigation/recovery，必须先找出唯一状态owner再切分；`MarkerAssociator`若只有PoE2实用调用方就继续留在feature。

```text
PoE2FollowComposition(config, first_frame_result, map_snapshot,
                      capture_adapter, memory_adapter?, controller_adapter)
  ├─ Vision pipeline(PoE2 profiles, same-frame registration)
  ├─ TrackedRoleRuntime[P1], TrackedRoleRuntime[P2]
  ├─ NavigationTask[controlled role] + injected shared routing primitives
  ├─ TargetProvider(leader / click / remote peer)
  ├─ RecoveryCoordinator + PoE2 policy + optional backends
  ├─ WorkerRuntime(Vision worker, Control worker, frame transport)
  └─ ControllerOutput(lease, heartbeat, neutral, receipt)

UI → start(config) / update_target(point) / stop()
UI ← StatusSnapshot + PreviewSnapshot + DiagnosticEvents
```

装配工厂应放在 `features/poe2/live_terrain`，PoE2 UI通过应用facade调用；实验页可以先沿用旧入口作为调用方，正式定位页待后续阶段接入。没有用户显式开始跟随时，构造工厂不能触发截图、内存或手柄写入。

## 6. 可讨论的三个路线

| 路线 | 内容 | 取舍 |
| --- | --- | --- |
| A：整体搬迁 | 把 `experimental/follow_engine` 多数文件移到 application/core | 文件位置最快变“正式”，但业务术语、PoE2类型和大状态对象污染下层；回归风险最高，不推荐 |
| B：契约先行的纵向切片（推荐） | 先明确DTO/端口/owner，再复用已有Core；每次迁移一个完整能力切片并双路离线对照，最后切入口 | 过程较长，但每一步可证行为等价、可回退；最适合当前刚得到的成功基线 |
| C：只在PoE2内整理 | 先把实验页/大文件拆开，功能仍全留PoE2 | 短期风险低，不能解决跨业务重复，未来还要二次迁移；可作为B的初段但不作为终点 |

推荐 B。重要限制：方案中的目录和DTO是目标设计，不要求第一阶段全部创建；只有证明稳定复用和依赖方向正确时才下沉。具体阶段与验收见迁移计划。
