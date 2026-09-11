# 自动跟随系统模块化开发任务计划

## Goal

按“底层能力 → 组合服务 → 运行时 → 工作台”的顺序实现局域网位置共享、双角色定位、跟随寻路和 Xbox 控制，并让每个阶段可独立测试、回滚和继续。

## Architecture Overview

底层模块不依赖游戏业务；定位只输出坐标，规划只消费地图和目标，控制只输出设备无关平面向量，Xbox适配器负责Controller1/2。A1/A2共享同一帧小地图和地图配准，但拥有独立跟踪、路径、恢复状态。常态采用增量滚动估计和局部模糊范围匹配，不隐式全局搜索，丢失后由用户调整圈选范围。

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
| 8–10 目标/寻路/运动/恢复 | 已接独立进程，现场待验 | 复用PathFinder、route_progress、line_is_walkable；粗网格优先+细化/缓存，严格墙角检查，轨迹后置目标、平面向量跟踪、400ms进度检测与有限脱困 |
| 11 LAN 位置/事件 | 数据通道已实现 | 用户已批准 share 模式；复用 TLS/LiteNetLib 配对，不占手柄；独立位置/事件权限、500ms保守有效期、急停撤销权限；Python bridge已接 |
| 12 事件链/运行时 | 基础版实现并验证 | 复用EventDefinition/Handler/Action/Registry/hooks；按钮/等待/条件/有限重试/钩子，优先级抢占、有效期、会话取消。一个视觉进程+每角色一个控制进程+网络线程；spawn联调通过 |
| 13 工作台 | 页面已接入 | gui/modes/follow，第5页；配置版本、角色/设备/地图/ROI/局部圈选、事件开关链、快捷键、诊断。沿用原主题/画布，不自动启动 |
| 14 回放/实测 | 离线完成，真实游戏待验 | 可选有界录制、无设备回放、合成基准；不宣称双机、真实游戏定位或脱困已通过 |

复用约束：跟随控制为上帝视角平面向量，不照搬差速机器人转向角速度；地图向量到 Xbox 轴仍要配置坐标基变换。定位参考墙与导航编辑墙应分别标识，现有加载行为本轮不改变。自动化命令必须有期限，陈旧坐标不能无限续期旧摇杆。

已验证命令（项目目录执行）：

```powershell
python -m pytest tests/test_foundation_types.py tests/test_map_runtime.py tests/test_minimap_frames.py tests/test_phase_tracker.py tests/test_local_matcher.py tests/test_marker_detector.py tests/test_dual_localizer.py tests/test_phase_displacement.py tests/test_perception_preprocessing.py tests/test_navigation_wall_version_loading.py tests/test_wall_version_storage.py tests/test_localization_result.py tests/test_navigation_localization_tick.py -q
```

结果：38 passed（新增合成测试 + 原有定位/墙体版本/图像处理回归）；不等同游戏验证。

审查闭环：独立代码审查复现“旧标记被重新打时间戳”和“小搜索窗无第二候选仍报告高置信度”，均已添加失败测试后修复；另加滚动连续帧验证并将整图有效性检查移到 matcher 初始化，避免每帧扫描全图。

提交断点：44e2b5a（缓存纠错）、c31fde6（ROI）、876dde2（相位适配）、6cd0dfa（局部匹配）、e4b25a8（标记组合）、a30eb10（定位组合）。

已解决的架构选择：用户确认新增 share 数据专用模式；原 send/receive 保留。位置和行为事件共享配对身份，但不获得控制器所有权。程序输出另用短期令牌，绝不通过开启物理键鼠映射实现自动跟随。

### 2026-09-11 第二批断点

- LAN：`LanSyncService.SharedData.cs` + 原 SyncPanel 新增模式/权限。20 项 LAN 测试通过（本机双实例 TLS/UDP，不等于双电脑实测）；UI 10 项已通过。
- 代码审查修复：急停后隐式重连、延迟包寿命延长、非法 JSON/数字异常影响其他会话、同时连接覆盖会话。数字异常补用 TryGetInt64；多对端恶意包端到端测试仍待补。
- 寻路：`follow_target.py`、`follower_planner.py`、`vector_tracker.py`、`stuck_recovery.py`，4 项合成测试通过。穿墙的旧路径直接回中，不能继续沿旧路径靠墙移动。
- 程序输出：`ControllerRegistry.Program.cs` 在已有宿主增加 acquire/state/release；每帧 TTL 最多300ms，租约1秒，暂停/F7/F8/F9撤销令牌。原始键鼠模式保持暂停。Python `ProgramGamepadOutput` 复用现有客户端与 StickSlewLimiter，不启动第二个手柄实现。宿主51项通过，Python桥接/输出2项通过。
- 未进行驱动安装、生产宿主替换、实际游戏移动；后续必须验证真实配置。

### 2026-09-11 第三批断点（当前）

- 程序输出令牌复用已有宿主。新增Windows绝对期限，管道延迟不能延长陈旧命令；启动请求带原始时间，急停前排队的启动不得重开。释放旧令牌幂等，不能撤销新持有者。
- LAN位置/事件发布也带本机绝对期限；事件从工作台排队开始计时，到网络、接收队列、角色执行均不刷新寿命。接收事件携带会话ID，换会话取消旧链。
- 颜色配置拒绝无限定范围/整个小地图，两个ID匹配到同一点时拒绝双重身份。A端UI可指定B端自定义角色ID，B端可自定义事件目标角色。
- 复用原A*并缓存静态网格，先粗后细；合成1024地图长绕墙重算中位从307ms降至18ms左右。小地图定位中位1.58ms，40/40合成帧成功，不等于游戏精度。
- 原始定位墙与活动导航墙显式分开；双方校验墙体内容摘要。旧导航加载行为不改。
- 工作台UI渲染截图检查通过；真实双规划进程spawn测试通过，输出使用记录器，未操控游戏。Release宿主构建通过（开发目录，下次启动使用；没有自动启动宿主）。
- Git断点：dcdcf6e（LAN share）、c0f1bf1（寻路基础）、5f77026（程序输出初版）；后续纠错/运行时/UI/验收各独立提交，见git log。
- 详细配置、实测数字与全项目旧失败说明见 `2026-09-11-follow-system-verification.md`。

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

实际文件：`core/routing/vector_tracker.py`、`core/actions/program_gamepad.py`、`tests/test_follow_navigation.py`、`tests/test_program_gamepad.py`。

实际实现上帝视角平面预瞄向量，拒绝穿墙/切角，接近终点与低置信度减速；接入现有StickSlewLimiter，不实现差速机器人转向角速度。

验证：`python -m pytest tests/test_follow_navigation.py tests/test_program_gamepad.py -q`。

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

- 当前状态：Task1–13基础功能已组装；Task14离线回放/合成性能/多进程测试完成，真实游戏和双电脑验收尚未执行。金字塔/ORB等可选优化未实现，不以算法名称冒充完成。
- 起始回滚点：`a155446`；本轮各模块提交号见上方实际进度表。
- 当前没有待确认架构冲突，用户已批准 share；按要求连续开发。
- 下一断点：按verification文档在工作台配置双方真实小地图/颜色或ID/地图与回城链，先仅监视验证，再手动授权A1/A2输出。当前缺少这些真实场景配置，不能猜测后直接驱动游戏。旧项目全量测试失败单独记录，不扩大修改范围。
