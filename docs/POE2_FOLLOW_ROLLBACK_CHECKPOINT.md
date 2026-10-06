# PoE2 跟随优化回退断点（2026-10-07）

## 当前基线

- 代码已明确回退到 Git `a3070ea checkpoint: stabilize poe2 experimental follow runtime`。
- 已撤销 `a618207`、`333d1d8`、`0e887e9` 三批后续优化，保留回退前运行时日志和 evidence 文件。
- 本断点之后只做只读审查，未经新的根因证据和回归测试，不继续修改首帧、双人 worker 或采样参数。

## 已确认的负面回归

- 连通域候选提取改动使首帧候选数量增多，放大双人首帧排列和形状搜索。
- 首帧候选上限调整与实时运动候选逻辑混杂，导致首帧耗时异常；实机日志出现单次候选结果间隔约 70 秒。
- 用户反馈双人实时定位点击后崩溃/退出；现有日志未捕获稳定 Python traceback，需对照正式页面的线程、帧槽和生命周期边界继续审查。

## 当前待查链路

1. 正式绘图页：截图频率、预处理复用、绘制节流和 UI 更新边界。
2. 正式导航页：定位帧输入、局部跟踪、运动预测、输出节拍和恢复边界。
3. 实验双人页：首帧注册、实时 worker、latest-only、Qt drain、首帧 accepted 门和异常清理。
4. 只读性能对照：capture、recognition、tracking、render、logging 各阶段耗时。

## 后续动作

- 先完成正式/实验链路对照和问题分类。
- 再检索成熟的 latest-frame、ROI、异步流水线和视觉跟踪方案，记录来源与适用边界。
- 只有形成单一可验证假设后，才建立回归用例并修改代码。

## 只读对照结论（2026-10-07）

### 确认的首帧阻塞根因

- 手动按钮 `dual_first_frame_button.clicked` 直接调用
  `run_dual_first_frame_experiment()`。
- 该方法在 Qt GUI 线程内同步执行 `_compute_dual_first_frame()`：一次内存锚点读取、3 次截图、每次预处理/墙体提取/HSV 候选提取、每次完整 `DualFirstFrameRegistrar.register()`，最后才回到 Qt 应用。
- 当前 `experiment.py` 和页面入口都把候选上限设为 6；注册器会遍历长度为 2 的有序排列，候选数为 6 时是 `6P2=30` 组，每组还可能执行 midpoint geometry 或 joint similarity 搜索。因而首帧出现几十秒至约 70 秒的空转/无响应是可推导的，不是单纯 FPS 参数问题。
- `start_dual_motion()` 要求 `_last_dual_first_frame_result.accepted`、`_dual_initial_frame` 和 tracker 上下文同时存在；同步首帧未完成、被拒绝或在 UI 阻塞期间状态未应用时，实时入口只能显示“首帧配准未通过/启动失败”。

### 正式页面可复用的边界

1. 绘图：`MappingRuntimeLifecycle` 只调度定时器；`MappingSession.tick()` 一次采集一次识别一次 stitch，人物识别失败回退上一帧/中心。
2. 导航：`NavigationRuntimeFrameLoop` 每帧按 capture→player local position→localize→task update→render；`resolve_player_local_position()` 回退上一帧位置，事件识别异步，不阻塞主定位帧。
3. 实验双人：连续 worker 已有 latest-only 槽，但首帧注册仍是同步入口；实时 worker 同一帧还做 combined wall mask、HSV profiles、候选排序、双角色 tracker、证据归档和 UI drain，未像正式导航那样把重型非必要工作隔离到低频/异步路径。

### 当前不应做的改动

- 不直接把候选数、面积阈值、置信度或 FPS 再次“调一把”。这些参数改变无法解决 GUI 同步注册和 `6P2` 搜索的结构性耗时，且已造成过负面回归。
- 不把正式导航的单人中心模式直接套到双人；双人必须保留两个绝对锚点和无中心假设。
- 不在没有 traceback/阶段耗时的情况下把“点击后崩溃”归因于 Qt、MSS 或虚拟手柄。当前证据足以确认 UI 长阻塞，但还不足以确认 native 崩溃。

## 后续改造边界（待用户确认后实现）

### A. 首帧生命周期

- 将手动首帧和恢复首帧统一为一次性后台任务；GUI 线程只负责提交任务、显示阶段状态、应用 bundle。
- 任务内部保留“读锚点→截图→候选→注册→选择”的纯数据边界，禁止访问 Qt 控件。
- 首帧候选先按 profile/几何 NMS 保证每个角色至少一个候选，再用绝对锚点做有界筛选；注册器不接受无界排列。正常双人场景最多保留每角色 2 个候选，只有证据不足才扩大上限。
- 每个阶段记录 `capture_ms/recognition_ms/candidate_ms/registration_ms/total_ms/candidate_count/assignment_count/status`。

### B. 实时帧处理

- 采集与追踪保持 latest-only；旧帧直接丢弃，不排队。
- 墙体/combined mask 与人物候选分开计时；墙体位移低频更新，人物候选和关联高频更新。
- 预览、证据归档和详细日志降频，不得与控制帧共享同步路径。
- 暂时失配沿用上一帧角色状态和有界预测；只有地图变换失效/实例变化/预测不确定度越界才申请重定位。

### C. 生命周期安全

- 首帧 worker、实时 worker、retired worker 必须有 generation、terminal outcome 和 cleanup 记录；迟到 signal 只能被忽略，不能应用到新会话。
- 启动双人实时前验证首帧 bundle 的 instance、transform、两角色上下文；验证失败只结束本次启动，不释放已有地图/跟随上下文。
- 补充稳定 Python traceback、线程名、worker generation 和 Qt 回调阶段日志，区分“GUI 长阻塞”与真正 native 崩溃。

## 成熟方案参考（只读）

- OpenCV 视频跟踪文档：<https://docs.opencv.org/4.x/dc/d6b/group__video__track.html>。可用于 Lucas–Kanade/Pyramidal optical flow 和 Kalman 状态估计；只作为短时 marker 预测补充，不能替代绝对首帧锚点。
- ROS 2 `image_transport`：<https://docs.ros.org/en/rolling/p/image_transport/>。其 transport/plugin 边界说明了采集、传输、处理解耦；本项目可借鉴“帧源与处理器接口分离”，不直接引入 ROS。
- ROS 2 `image_pipeline`：<https://github.com/ros-perception/image_pipeline>。可借鉴分阶段 image_proc、低频重处理与诊断统计；不照搬其相机标定假设。
- OpenCV connected components/contour 文档：<https://docs.opencv.org/4.x/d3/dc0/group__imgproc__shape.html>。候选面积必须统一使用 contour area 或显式像素面积，不能在同一阈值下混用；这正是上次噪声候选暴增的教训。

## 当前状态

- 运行代码基于 `a3070ea`；本轮已完成首个结构性改动：手动/后台双人首帧只采集一次并注册一次，没有发送真实输入。
- 首帧回归测试已验证：`tests/test_poe2_capture_test_page.py -k dual_first_frame_experiment_renders_two_players_without_timer` 通过。
- 纯双人 tracker 已增加短时预测保持：静止/暂时不可测墙体复用上一变换，marker 失配和墙体异常时返回最后可信角色位置，并输出预测诊断；地图失效仍保留原有恢复边界。
- 纯 tracker 回归测试已通过：`tests/poe2_live_terrain/test_multiplayer_motion.py`（25 passed）。
- live worker 已增加 `candidate_ms`、`total_worker_ms`、processing EMA、自适应间隔和 effective FPS 诊断；latest-only 机制未改变。
- worker 回归测试已通过：`tests/test_poe2_dual_motion_worker.py`（10 passed）；页面双人专项（13 passed）。
- 预览/地图 overlay 已限制到 12Hz，控制状态仍消费每个 latest result；旧 worker 测试 fake 对象保持兼容。
- 离线回放已覆盖一帧 marker 缺失和一帧空墙体后恢复；下一步执行完整专项回归和 compileall。
- 专项全量回归已通过：`tests/poe2_live_terrain` + PoE2 页面/worker 共 548 passed；`compileall` 和 `git diff --check` 通过。
- 当前提交序列为 `c879d64`、`c34a170`、`416604a`、`92c316c`、`e20ffad`，均建立在 `a3070ea` 之上。
- 生产配置的手动首帧入口已改为复用 `Poe2DualFirstFrameWorker`；测试/最小配置仍保留同步钩子。首帧实验候选预算独立限制为 4，实时 worker 仍为 6。
- 后续专项回归（页面、worker、首帧、tracker、replay）共 `162 passed`；compileall 与 diff check 通过。
- 当前实现仍未做实机输入验证；需要用户下一轮启动程序后观察后台首帧状态、首帧耗时和实时 timing 日志。
- 未跟踪的 `data/poe2_live_terrain_test/occlusion_diagnostics/` 是既有运行 evidence，本轮未删除或纳入代码提交。
- 仍未进行真实游戏窗口/手柄测试；下一步需在用户明确测试时观察首帧耗时、worker timing 和异常帧 prediction diagnostics。

## 用户确认的设计方向（2026-10-07）

- `(decision)` 首帧人物静止，连续三次截图没有收益；首帧改为一次采集、一次注册、一次应用结果。首帧失败时报告失败原因，不通过重复采样掩盖问题。
- `(decision)` 实时跟随优先提高有效处理频率，而不是提高请求 FPS 后让处理队列积压。采集/处理使用 latest-only；旧帧直接丢弃。
- `(decision)` 单帧人物候选异常、颜色干扰或暂时失配时，先沿用上一帧可信角色位置/地图变换，结合最近速度与手柄输出做短时预测，继续跟随；下一帧恢复后将视觉观测重新吸收，回到正常视觉轨道。
- `(constraint)` 单帧异常不能直接停止跟随，也不能立即触发全局重定位；只有连续异常超过有界预测窗口、地图变换失效或地图实例变化才升级恢复。

### 推荐状态机

```text
VISUAL_TRACKING
  ├─ 有效新帧 → 更新角色/速度/地图变换
  ├─ 单帧异常 → PREDICTIVE_HOLD
  └─ 连续异常且不确定度未越界 → PREDICTIVE_HOLD

PREDICTIVE_HOLD
  ├─ 新帧恢复 → VISUAL_TRACKING（融合，不重置轨迹）
  ├─ 仍异常但预测窗口未到 → 继续输出预测位移
  └─ 预测窗口/地图有效性越界 → LOCAL_REANCHOR；必要时才 GLOBAL_RECOVERY
```

预测使用上一帧可信位置 `p_k`、速度 `v_k`、输出方向 `u_k` 和帧间隔 `Δt`：

```text
p̂(k+1) = p_k + (α v_k + β u_k v_command) Δt
σ(k+1) = σ_k + σ_process Δt + σ_visual_gap
```

视觉恢复时不硬替换预测位置，而是按观测置信度融合：

```text
p(k+1) = (1-K) p̂(k+1) + K z(k+1)
K = σ_prediction² / (σ_prediction² + σ_observation²)
```

其中 `K` 只用于恢复过渡，避免一帧颜色噪声把人物位置突然拉走。

### 备选实现边界

**方案 A：单线程固定节拍 + latest-only（推荐第一步）**

- 采集线程只保留最新 raw frame；处理器每次取最新帧。
- 首帧任务单独一次执行，不进入实时循环。
- 识别阶段只做 ROI/候选提取和轻量 tracker；墙体 mask、预览和 evidence 低频处理。
- 优点是改动小、容易对照正式导航页、最容易回归；缺点是 Python 单帧仍需通过 profiling 找出最慢阶段。

**方案 B：采集、识别、跟踪三级流水线**

- capture producer、marker/ROI worker、tracking/output consumer 分离，各级 latest-only。
- 识别只发布结构化候选，不复制完整图像；预览另走低频通道。
- 优点是更容易把处理频率提高到有效 25–30Hz；缺点是生命周期、时间戳和跨线程退出复杂，必须先有 A 的阶段耗时基线。

当前建议先做方案 A，确认 `capture/recognition/candidate/tracking/render` 各段均低于目标周期后，再决定是否拆成方案 B。不能先上多进程或 C/Cython；只有 profiling 证明 Python 代码占主耗时，才考虑把单一热函数迁移到 NumPy/OpenCV/Cython。
