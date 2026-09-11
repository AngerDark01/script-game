# 自动跟随系统模块化开发任务计划

## Goal

按“底层能力 → 组合服务 → 运行时 → 工作台”的顺序实现局域网位置共享、双角色定位、跟随寻路和 Xbox 控制，并让每个阶段可独立测试、回滚和继续。

## Architecture Overview

底层模块不依赖游戏业务；定位只输出坐标，规划只消费地图和目标，控制只输出设备无关的 `MoveVector`，Xbox 适配器负责 Controller 1/2。A1/A2 共享同一帧小地图和地图配准，但拥有独立跟踪、路径、恢复状态。常态采用增量滚动估计和局部模糊范围匹配，全局定位只作兜底。

## Tech Stack

- Python 3.11+、pytest、dataclasses/typing
- NumPy、OpenCV（phase correlation、距离变换、颜色/ID 检测）
- 现有 `core/localization`、`core/routing/pathfinder`、`core/actions/gamepad`、`virtual_gamepad`
- 现有 LiteNetLib/TLS/设备码配对通道

## 断点记录规则

每个任务完成后更新本文件的任务状态、测试结果、提交号和下一断点；禁止使用 `git add -A` 覆盖无关用户改动。每个任务至少一个独立 commit。

## 任务顺序

### 2026-09-11 复用审计与执行断点（优先于下方早期任务草案）

本轮按 executing-plans 执行；用户要求持续开发，因此正常批次不等待确认。
仅在新需求与已有权限模型冲突时暂停。以下是实际状态，不代表整个系统已交付。

| 任务 | 实际状态 | 已有能力复用 / 剩余工作 |
| --- | --- | --- |
| 1 基础类型 | 早期提交保留 | 已发现 `core/spatial/models.py`、`calibration.py`；新模块直接复用 Point2D/AffineTransform，不再扩展重复基础类型 |
| 2 地图缓存 | 基础版 + 纠错 | `from_npz` 现在实际调用 `load_wall_version_catalog`；多分辨率金字塔和 tile 索引尚未实现，不能称为已完成 |
| 3 帧与 ROI | 底层完成 | 复用 FrameContext、ImageArtifact、crop；增加 LatestFrame，同时间戳/旧帧拒绝；真实采集工作进程待接入 |
| 4 滚动估计 | 底层完成 | 复用 `estimate_phase_displacement`；验证空图、低纹理、超限、滚动符号，不再实现第二套 phaseCorrelate |
| 5 局部墙体匹配 | 基础版完成 | OpenCV 计算硬边界内 Chamfer 候选，拒绝歧义；未实现金字塔/ORB/自动扩大搜索，绝不暗中全图兜底 |
| 6 多角色检测 | 组合接口完成 | 复用现有 ColorRegionDetector / 可注入同协议模板 detector；实图 ID 样本、遮挡跟踪调参未验证 |
| 7 定位会话 | 离线组合完成 | 同一帧配准与颜色观测、旧帧拒绝、单标记缺失隔离；每帧相位预测后局部地图校验防漂移，未接真实游戏 |
| 8–10 目标/寻路/运动/恢复 | 未实现 | 复用 PathFinder、route_progress、line_is_walkable、StickSlewLimiter、VirtualGamepadActionAdapter；禁止照草案另写 A* |
| 11 LAN 位置/事件 | 暂停待确认架构冲突 | 旧 receive 模式占用控制器；需要独立数据权限模式，而不是启用旧 receive 来收位置 |
| 12 事件链/运行时 | 未实现 | 已有 core/events 的 registry/runner/hooks，需要适配复用，不能另造平行业务事件体系 |
| 13 工作台 | 未实现 | 配置/状态页面应继续统一到已有 gui，不能另建 workbench 根目录 |
| 14 回放/实测 | 未实现 | 仅执行了合成图单测和现有模块回归；双机、实图、后台采集、速度精度验收尚未完成 |

复用约束：跟随控制为上帝视角平面向量，不照搬差速机器人转向角速度；地图向量到 Xbox 轴仍要配置坐标基变换。定位参考墙与导航编辑墙应分别标识，现有加载行为本轮不改变。自动化命令必须有期限，陈旧坐标不能无限续期旧摇杆。

已验证命令（项目目录执行）：

```powershell
python -m pytest tests/test_foundation_types.py tests/test_map_runtime.py tests/test_minimap_frames.py tests/test_phase_tracker.py tests/test_local_matcher.py tests/test_marker_detector.py tests/test_dual_localizer.py tests/test_phase_displacement.py tests/test_perception_preprocessing.py tests/test_navigation_wall_version_loading.py tests/test_wall_version_storage.py tests/test_localization_result.py tests/test_navigation_localization_tick.py -q
```

结果：38 passed（新增合成测试 + 原有定位/墙体版本/图像处理回归）；不等同游戏验证。

审查闭环：独立代码审查复现“旧标记被重新打时间戳”和“小搜索窗无第二候选仍报告高置信度”，均已添加失败测试后修复；另加滚动连续帧验证并将整图有效性检查移到 matcher 初始化，避免每帧扫描全图。

提交断点：44e2b5a（缓存纠错）、c31fde6（ROI）、876dde2（相位适配）、6cd0dfa（局部匹配）、e4b25a8（标记组合）、a30eb10（定位组合）。

待确认冲突：`LanSyncService.OwnsController` 在 receive 模式占用所选槽位，`ControllerRegistry.ExecuteLocal` 因此抛出 RemoteOwnershipException。自动跟随 A 端必须本地控制手柄，不能直接沿用旧接收模式。建议保留原输入同步，增加“只共享位置/事件”的数据通道和独立接收权限；共享配对身份，不占用手柄。确认后再展开任务 8–14 的联调实现。

### Task 1：建立通用几何与时间类型 ✅

文件：`core/foundation/geometry.py`、`core/foundation/clock.py`、`tests/test_foundation_types.py`

先写失败测试：Point2/Vector2 加减、距离、Transform2D 转换、单调时钟不倒退。

验证：`python -m pytest tests/test_foundation_types.py -q`；先确认失败，再实现并确认通过。

提交：`feat: add foundation geometry and clock types`

状态：已完成。失败测试先因 `core.foundation` 不存在而失败；实现后 `3 passed`。提交号见 Git 历史。

### Task 2：建立地图资源与距离场缓存（基础版，优化待测）

文件：`core/localization/map_runtime.py`、`core/localization/distance_field.py`、`tests/test_map_runtime.py`

实现墙体 mask、distance transform、多分辨率缩略图和 tile 查询；加载结果包含 map_id/map_version。

验证：`python -m pytest tests/test_map_runtime.py -q`。

提交：`feat: add cached map runtime and distance fields`

状态：原先“复用版本系统”的记录不准确，44e2b5a 已补接活动版本目录并验证；金字塔未实现。见上方实际进度表。

### Task 3：实现小地图帧与 ROI 接口

文件：`core/localization/minimap_frames.py`、`core/localization/roi.py`、`tests/test_minimap_frames.py`

实现带时间戳的 ImageFrame、ROI 裁剪、最新帧缓存和无效 ROI 校验；不接入真实屏幕采集。

验证：`python -m pytest tests/test_minimap_frames.py -q`。

提交：`feat: add minimap frame and roi primitives`

### Task 4：实现帧间滚动估计

文件：`core/localization/phase_tracker.py`、`core/localization/scroll_estimator.py`、`tests/test_phase_tracker.py`

封装 OpenCV phaseCorrelate；输出 dx/dy/confidence，并在空帧、低纹理和超限位移时返回不可用结果。

验证：`python -m pytest tests/test_phase_tracker.py -q`，使用合成平移图像断言误差小于 1 像素。

提交：`feat: add minimap phase correlation tracker`

### Task 5：实现局部距离场/Chamfer 匹配

文件：`core/localization/local_matcher.py`、`core/localization/search_window.py`、`tests/test_local_matcher.py`

在预测 origin 的搜索半径内进行粗到细候选搜索；输出最佳变换、分数、耗时和搜索范围。支持逐级扩大半径。

验证：`python -m pytest tests/test_local_matcher.py -q`，合成偏移地图必须找回已知偏移。

提交：`feat: add bounded local map registration`

### Task 6：实现颜色/ID 双角色检测

文件：`core/localization/marker_detector.py`、`core/localization/player_track.py`、`tests/test_marker_detector.py`

按 A1/A2 的颜色或 ID 直接检测标记，完成连通域、尺寸、置信度和短暂丢失处理；同一帧输出两个带 player_id 的观测。

验证：`python -m pytest tests/test_marker_detector.py -q`，测试交叉移动不会交换 ID。

提交：`feat: add dual player marker detection`

### Task 7：组合双角色定位会话

文件：`core/localization/dual_localizer.py`、`core/localization/localization_session.py`、`tests/test_dual_localizer.py`

组合一次小地图采集、共享地图配准和 A1/A2 独立坐标转换；实现正常跟踪、局部重定位、置信度和全局兜底状态机。

验证：`python -m pytest tests/test_dual_localizer.py -q`。

提交：`feat: add dual player localization session`

### Task 8：实现跟随目标与路径规划组合

文件：`core/routing/follow_target.py`、`core/routing/follower_planner.py`、`tests/test_follow_target.py`、`tests/test_follower_planner.py`

根据 B 位置和移动方向生成 A1/A2 后方目标；复用现有 A*，加入目标变化阈值、路径缓存和路径有效性检查。

验证：`python -m pytest tests/test_follow_target.py tests/test_follower_planner.py -q`。

提交：`feat: add independent follow targets and planners`

### Task 9：实现局部路径跟踪与摇杆命令

文件：`core/routing/pure_pursuit.py`、`core/actions/move_vector.py`、`tests/test_pure_pursuit.py`

实现 Regulated Pure Pursuit、预瞄点、转弯/墙体/置信度减速，并输出设备无关 MoveVector；接入现有 StickSlewLimiter。

验证：`python -m pytest tests/test_pure_pursuit.py -q`。

提交：`feat: add regulated path tracking and move vectors`

### Task 10：实现卡住检测与双控制器恢复

文件：`core/routing/stuck_recovery.py`、`core/runtime/follower_controller.py`、`tests/test_stuck_recovery.py`

实现 300–500ms 无有效位移判定、回中、左右脱困、局部重规划和单角色故障隔离；A1/A2 分别绑定 Controller 1/2。

验证：`python -m pytest tests/test_stuck_recovery.py -q`。

提交：`feat: add independent stuck recovery controllers`

### Task 11：接入局域网位置和事件

文件：`core/lan_follow/position_messages.py`、`core/lan_follow/event_messages.py`、`core/lan_follow/follow_transport.py`、`tests/test_follow_transport.py`

复用现有配对和传输层，增加位置 TTL、序号去重、地图版本校验和行为事件接收；不得把位置同步替换为键鼠输入同步。

验证：`python -m pytest tests/test_follow_transport.py -q`。

提交：`feat: add lan position and behavior event transport`

### Task 12：事件链与跟随运行时

文件：`core/events/follow_chain.py`、`core/runtime/dual_follow_session.py`、`tests/test_follow_chain.py`、`tests/test_dual_follow_session.py`

实现 start/pause/resume/return_home/emergency_stop、等待/条件/分支/重试节点，以及 A1/A2 独立状态机和安全 watchdog。

验证：`python -m pytest tests/test_follow_chain.py tests/test_dual_follow_session.py -q`。

提交：`feat: add dual follow runtime and event chains`

### Task 13：工作台配置与运行监控

文件：`gui/modes/follow/` 下的配置模型、页面和状态适配器；`tests/test_follow_config.py`

提供角色、地图、A1/A2 颜色/ID、搜索半径、跟随参数、设备配对、事件开关和事件链编辑；所有配置通过工作台保存和版本化。

验证：`python -m pytest tests/test_follow_config.py -q`，再运行现有工作台 smoke check。

提交：`feat: add follow configuration workbench page`

### Task 14：回放、性能和真实环境验证

文件：`core/diagnostics/follow_replay.py`、`tests/test_follow_replay.py`、`docs/plans/2026-09-11-follow-system-verification.md`

支持录制/回放小地图、位置、路径、事件和 Xbox 命令；测量定位耗时、局部匹配耗时、丢失率、网络延迟和卡住恢复时间。

验证：单元测试、离线回放、双机局域网测试、游戏窗口聚焦测试；确认启用态吞键、暂停/关闭释放输入和 A1/A2 独立输出。

提交：`feat: add follow replay and verification tooling`

## 当前断点

- 当前状态：底层定位组合已推进到 Task 7，尚未接入真实游戏、网络、手柄输出和 UI。
- 起始回滚点：`a155446`；本轮各模块提交号见上方实际进度表。
- 当前暂停原因：新位置共享模式与旧 LAN 手柄接管权限冲突，等待用户确认数据专用模式。
- 下一步：确认后复用现有寻路与动作模块推进 Task 8–10，再接数据专用 LAN 和事件链；不要跳过输出权限与超时保护。
