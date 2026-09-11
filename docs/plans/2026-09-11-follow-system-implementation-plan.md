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

### Task 1：建立通用几何与时间类型 ✅

文件：`core/foundation/geometry.py`、`core/foundation/clock.py`、`tests/test_foundation_types.py`

先写失败测试：Point2/Vector2 加减、距离、Transform2D 转换、单调时钟不倒退。

验证：`python -m pytest tests/test_foundation_types.py -q`；先确认失败，再实现并确认通过。

提交：`feat: add foundation geometry and clock types`

状态：已完成。失败测试先因 `core.foundation` 不存在而失败；实现后 `3 passed`。提交号见 Git 历史。

### Task 2：建立地图资源与距离场缓存 ✅

文件：`core/localization/map_runtime.py`、`core/localization/distance_field.py`、`tests/test_map_runtime.py`

实现墙体 mask、distance transform、多分辨率缩略图和 tile 查询；加载结果包含 map_id/map_version。

验证：`python -m pytest tests/test_map_runtime.py -q`。

提交：`feat: add cached map runtime and distance fields`

状态：已完成。复用了现有 `map_package.py`、墙体版本目录和导航墙体层，仅新增 `MapRuntime` 缓存外壳；`2 passed`。

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

- 当前状态：计划已建立，尚未开始 Task 1。
- 回滚点：`6629848 docs: add modular follow system implementation plan`。
- 下一步：Task 3，小地图帧与 ROI 接口。
