# PoE2 跟随优化回退断点（2026-10-07）

## 本轮规划任务（2026-10-07）

- `(requested)` 用户要求先冻结当前代码提交，再制定双通道/多进程跟随的完整实施方案，并拆成可独立验收的小目标。
- `(confirmed)` 当前基线提交为 `ea72667`；设计提交为 `2eaeb38`。工作树中的 `data/events/events.json` 和 `data/poe2_live_terrain_test/occlusion_diagnostics/` 属于运行时用户数据，不加入本轮规划提交。
- `(designed)` 详细执行计划已写入 `docs/plans/2026-10-07-poe2-follow-engine-execution-plan.md`，覆盖 M0–M8、文件边界、跨进程契约、测试命令、性能门槛、回滚点和实机验收。
- `(decision)` 本轮只完成规划和基线冻结，不开始新架构实现；用户确认后从 M0.1/M0.2 回放夹具开始。
- `(next)` 先建立离线回放 manifest 与不可发送真实输入的 harness；随后实现 M1 纯逻辑契约，再迁移 VisionProcess 和 FollowControlProcess。

## 开发启动（2026-10-07）

- `(started)` 用户已授权按执行计划开始开发，当前从 M0 离线回放夹具和 M1 纯逻辑契约开始。
- `(boundary)` 本轮首先只新增无副作用 DTO、代际校验、预测/融合和恢复策略；不启动真实游戏、不读取实时内存、不发送手柄输入。
- `(next)` 先提交 M0 回放 manifest 与离线 harness；随后提交 M1.1–M1.4，每一组都有独立测试和提交。

## 最新测试异常调查（进行中）

- 用户请求只读定位最新异常日志与图片，先分析原因，不改运行代码、不发送输入。
- 最新日志截至 14:14:01，末段出现 `Program session expired or was revoked`，重复发生于 foreground 中立写入；需要追溯第一次异常而非把失焦后的重复错误当首因。
- 下一步：核对最新 session 首次错误、重定位/视觉证据以及图片时间戳，记录完整时间线。

### 只读结论（2026-10-07 14:xx 会话）

- `(confirmed)` 最新异常的首个实际错误是 `14:13:40.199` 的 `VirtualGamepadError: invalid_argument: Program session expired or was revoked. Explicit start is required.`；之后每约 0.1–0.3 秒在 foreground 中立帧路径重复失败，属于同一失效 session 的连锁噪声，不是多个独立根因。
- `(confirmed)` 此前 worker 已长时间处于 `recovery_required / markers_missing`：P2（DexFourb）最后可信视觉时间 `1791353608746`，到 `14:13:40` 视觉年龄约 11.5 秒；P1 仍可见。六张 evidence raw 显示 P1/P2 标记仍在附近/可见，但候选配对的相对距离从预测约 84 native px 与观测约 74 px 偏离，P2 候选持续无法通过身份/几何关联，随后进入恢复状态。
- `(confirmed)` 视觉恢复期间 `dual_motion.worker_stop_deferred` 与 `restart_deferred` 表明旧 native capture worker 尚未退出；同时跟随 tick 出现 `runtime_tick_ms=472–926ms`、总 tick `486–1073ms`，说明恢复/路径计算阻塞了 UI 控制节拍。
- `(confirmed)` 首帧恢复本身耗时显著：`memory_ms=2796–6267ms`，`registration_ms` 约 10s，`total_ms=5.4–16.5s`。因此本次表现是“P2 标记失配→恢复升级→运行时/worker 拥塞→Host session 过期后中立写入也失败”，不是单纯截图颜色瞬时丢失。
- `(boundary)` 最新 evidence 图片已保存于 `data/poe2_live_terrain_test/occlusion_diagnostics/1791353605141-...` 至 `1791353611275-...`，当前未修改代码；下一步需用户确认是否先修复“过期 session 中立帧重建”和“恢复期间 runtime tick 阻塞”两条边界。

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

## 快速内存重锚耗时核对（2026-10-07，本轮只读）

- `(confirmed)` 实机双人首帧日志 `14:46:12`：`memory_ms=3594.331`、`registration_ms=7405.446`、`total_ms=11151.526`；`14:52:45`：`memory_ms=3671.729`、`registration_ms=4131.939`、`total_ms=7964.704`。因此当前完整重定位约 `8–11s`，其中内存锚点读取约 `3.6s`，视觉注册约 `4.1–7.4s`。
- `(confirmed)` 当前 `Poe2PlayerPositionSource.read_once/read_many` 每次都会重新找 PID、解析 descriptor/layout、创建 `ProcessReader`、扫描 entity/component 表并读取 Render 坐标；双人 `read_many` 一次 reader 可得到两个角色，但仍重复承担上述冷启动/扫描成本。
- `(confirmed)` 旋转/镜像/比例已在首帧确定后，单点 `TerrainOrientation.transform_point` 与 reference-native 映射是纯内存计算，理论上为亚毫秒级；因此跟随异常时不应重新做视觉注册。
- `(decision)` 采用分层恢复：L0 使用上一可信点+速度预测继续跟随；L1 在冷却后读取一次内存并套用已有 transform，只更新角色位置；L2 仅在 L1 失败或局部冲突时做局部视觉校正；L3 仅在实例变化/transform 失效时做全局视觉注册。
- `(constraint)` L1 必须校验 `area_instance` 与首帧实例一致，并设置最短触发间隔（建议初始 `5–10s`）和连续异常门槛（建议 `3–5` 帧）；失败时继续预测而不是结束跟随。
- `(next)` 在不触碰真实输入的前提下，新增可注入的 warm-reader/transform-only 基准与回归：验证缓存 descriptor/layout/component 地址后，暖读只读取 area/player 坐标；确认 instance 变化拒绝快速路径，且快速路径不调用视觉注册。

## 异常恢复分层方案草案（2026-10-07，待用户确认）

- `(design)` 恢复优先级：A 视觉短时容错/最新帧重试 → B 运动预测继续跟随 → C 内存快速重锚并复用首帧 transform → D 局部视觉校正 → E 全局视觉重定位。任何普通异常都不自动结束动态跟随。
- `(design)` A 层只处理单帧或短暂失配：候选存在但关联失败时使用动态门限、双人相对几何和上一帧身份；下一帧成功即恢复，不读内存、不重定位。
- `(design)` B 层使用 `p_pred=p_last+v_est*dt`，不确定度按视觉年龄、速度误差和处理延迟增长；预测只在有界时间/不确定度内生效，持续输出或低幅探索，不释放 session。
- `(design)` C 层仅在连续失配或不确定度越界后触发，要求首帧 transform 有效且 area instance 未变；一次读取双人内存坐标，转换到 reference-native，只更新位置/速度滤波，不重新做方向/比例/视觉注册。建议初始门槛：连续 3–5 个有效处理帧失配，或预测不确定度 > 40–60 native px；同一角色最短冷却 5–10s。
- `(design)` D 层仅在内存失败、实例校验失败或内存点与预测冲突 > 30–50 native px 时触发；只在人物附近 ROI 做局部匹配，固定 transform，不做全图搜索；成功后回到 A/B，不成功继续预测并等待下一次 C。
- `(design)` E 层只允许在地图实例变化、首帧 transform 失效、C/D 连续失败且不确定度 > 100–120 native px，或地图/玩家证据同时失效时触发；必须异步执行，跟随 session 保持，完成后原地恢复。
- `(design)` 所有层均有成功/失败、冷却、升级和降级规则；失败不等于停止，只有用户手动停止才关闭动态跟随 session。
- `(next)` 先实现状态机和指标埋点，再实现 C 层 warm reader；随后补 D/E 异步边界和离线回放，最后才在实机开启快速内存兜底。

## 最新测试与分层方案对照（2026-10-07，本轮只读）

- `(confirmed)` 最新日志末段不是单一异常：P1 `StrDexFourb` 最后可信视觉时间距当前约 `25s`，`identity_dropout_failures≈293`，预测不确定度已升至 `114.6 native px`；P2 仍可见，双人 assignment 的观测间距约 `87px`、预测间距约 `1.5px`，因此现有双人关联无法恢复 P1。
- `(confirmed)` 按拟议门槛，这一会话应在连续 `3–5` 帧失配或不确定度超过 `50px` 时进入 L1 内存快速重锚，而不是继续把 `recovery_required/markers_missing` 重复输出到 `114px`。
- `(confirmed)` 同段还存在独立的 `poe2_not_foreground`（截图被忽略约数秒）和旧 Host 对 `program.heartbeat` 返回未知命令；前者是输入/采集门控，后者是 program lease 保活问题，不能由内存重锚方案单独解决。
- `(conclusion)` 分层方案能够直接覆盖“人物视觉长期失配导致预测漂移、全局视觉重定位过慢”这一主因；不能单独覆盖窗口失焦、旧 Host 心跳协议、worker 迟退等运行时问题，需并列修复并保持跟随 session。

## 恢复优先级修正（2026-10-07，用户确认方向）

- `(decision)` 只要采集到了新帧，恢复优先使用新帧做视觉匹配；上一帧失败不能直接跳到内存读取。
- `(decision)` 新帧存在时的顺序改为：最新帧候选重提取 → 动态关联/双人几何匹配 → 预测位置附近局部视觉匹配 → 仍失败才考虑内存快速重锚。内存不是新帧失败的第一反应，而是视觉证据不足或预测失控时的兜底。
- `(design)` 局部视觉匹配固定复用首帧 transform，只在预测/内存位置附近做 ROI 搜索，不重新估计方向、比例或全图注册；优先 ROI 半径 `80 native px`，必要时扩大到 `140/220 px`。
- `(design)` 若新帧为空、被前台门控丢弃、帧年龄超过阈值或连续局部匹配失败，才进入内存快速重锚；成功的视觉局部匹配应直接回到正常跟踪，不触发内存读取。
- `(next)` 实现恢复调度器时增加 `frame_available/frame_age/visual_attempt/local_attempt/memory_attempt` 诊断，分别测量新帧视觉、局部匹配和内存兜底耗时，避免误把“视觉候选关联失败”和“没有新帧”混为一种异常。

## 15:26 之后对话综合计划（2026-10-07，待确认）

- `(scope)` 本轮对话没有发现 15:26 之后的新运行日志；计划依据用户连续确认的设计决策和现有 14:46–14:53 实机证据整理，不把对话结论误当成新的实机验证。
- `(decision)` 恢复顺序最终确定为：新帧视觉全局候选/身份关联 → 新帧局部 ROI 视觉匹配 → 短时预测继续跟随 → 内存快速重锚 → 局部/全局异步恢复。上一帧失败不应直接触发内存读取。
- `(problem-set)` 待解决问题统一分为：P1/P2 暂时失配与双人关联漂移；P1 target stale/target_hold 过期；预测位置提前命中导致误到达；内存读取冷启动过慢；局部/全局重定位阻塞；Host program heartbeat 旧协议；前台门控；worker generation/迟退；实时帧处理过载；动态跟随错误释放 session。
- `(implementation-order)` 阶段 1 先做恢复调度器和详细状态/耗时诊断；阶段 2 做最新帧优先和局部 ROI；阶段 3 做 warm memory reader；阶段 4 接入 L0/L1/L2/L3 状态机；阶段 5 修复 Host/worker 生命周期；阶段 6 离线回放和实机验证；未经阶段 1–5 回归，不调整阈值或切换 C/Cython。
- `(acceptance)` 新帧存在时不得直接读内存；局部匹配成功不得触发全局恢复；内存失败不得停止跟随；全局恢复异步且保留 session；只有用户停止才释放动态跟随输出。

## 实施进度（2026-10-07，进行中）

### M4 backend single-flight 修复（2026-10-07）

- `(fixed)` `follow_engine/recovery/global_recovery.py::GlobalRecoveryBackend.in_flight` 现在把“future 已完成但尚未 poll 消费”视为仍占用 single-flight；修复快速 worker 在控制 tick 之间被重复 submit 的竞态。
- `(verified)` `tests/poe2_live_terrain/test_follow_engine_recovery_backends.py` 新增 completed-unpolled 回归；backend 聚焦测试 `4 passed`。
- `(boundary)` M4 backend 仍未接入 `FollowControlRuntime`；当前 control process 只调用策略，不提交/轮询 memory/local/global backend。
- `(next)` 扩展 memory backend 为异步 submit/poll，接入 runtime 的局部 ROI、内存快速重锚和全局异步恢复；恢复成功只 seed 角色状态并保持 session。

### M4 backend 接入控制 runtime（2026-10-07）

- `(implemented)` `MemoryRecoveryBackend` 增加单线程异步 `submit/poll`、generation 校验、冷却查询和结构化 error；`MemoryFastReanchor.cooldown_ready()` 只读检查冷却，不触发进程读取。
- `(implemented)` `FollowControlRuntime` 接入 local/memory/global backend：最新帧先按角色执行 bounded ROI；内存/全局只异步提交，后续 tick 轮询并以已有 transform/结果 seed tracker 与 odometry；恢复不清除目标、不释放 session。
- `(implemented)` `StageTiming.local_ms` 记录局部恢复耗时；局部/内存/全局失败仍交给 `RecoveryPolicy`，不会转成用户停止。
- `(verified)` runtime/backend 聚焦测试 `12 passed`；PoE2 全目录回归 `496 passed`；compileall 与 diff check 通过。
- `(boundary)` 当前 `FollowControlProcessHandle` 仍使用默认无 backend runtime，页面/真实 VisionProcess 尚未通过 M5 port 注入 backend；真实内存 source 尚未接入 warm reader。
- `(next)` M5 建立 `FollowEnginePort` 与 UI adapter，禁止页面直接持有 tracker/backend/future；随后将 fake vision/control/host 组合跑离线回放。

### M5.1 FollowEnginePort 与 UI adapter（2026-10-07）

- `(implemented)` 新增 `follow_engine/engine.py`：`FollowEngineStart`、`FollowEnginePort` 与三类端口协议，统一 generation、control/vision/output 启停、latest poll、target 更新和显式 user stop。
- `(implemented)` 新增 `follow_engine/ui_adapter.py`：页面只消费 `FollowUiState`，不直接管理 process/future/tracker。
- `(verified)` `test_follow_engine_port.py` 覆盖 latest 事件转发、输出快照、启动失败逆序回滚、多角色 target 显式 role；聚焦 `4 passed`。
- `(boundary)` `capture_test_page.py` 尚未切换到该 port；现有页面仍保留旧业务编排，下一阶段只接 adapter，不改静态/正式定位链。
- `(next)` M5.2 建立页面适配层的构造与轮询接口，先以 fake composition 验证再考虑替换 live follow 入口。

- `(implemented)` 已建立 `recovery_state.py`、`recovery_diagnostics.py`，显式定义视觉降级、局部/内存/全局重锚和动态保持状态；新增状态诊断回归，`2 passed`。
- `(implemented)` 已建立纯策略 `recovery_coordinator.py`：新帧优先视觉/局部，帧过期或无帧且预测超限才允许内存，冷却期间继续预测；新增策略回归，累计相关测试 `5 passed`。
- `(implemented)` 已建立 `memory_fast_reanchor.py` 封装双人一次读取、实例校验、transform 复用和冷却；新增注入 reader 回归 `2 passed`。当前仍未把 reader/layout 缓存接入真实 `Poe2DualPlayerPositionSource`，实机 3.6s 冷读成本尚未下降。
- `(next)` 将恢复调度器接入 live runtime/页面前，先补局部 ROI 匹配契约和 prediction/fusion 回归；随后接入真实 source 缓存并做离线回放。当前没有发送真实输入。

## 自检结果（2026-10-07）

- `(fixed)` 自检发现 `MemoryFastReanchor` 未注入时默认时钟固定为 0，会使无显式时间参数时冷却失效；已改为 `time.monotonic()` 毫秒时钟并复跑测试。
- `(confirmed)` 当前新增模块均可导入，恢复基础测试 `9 passed`、compileall、diff check 通过。
- `(gap)` `RecoveryCoordinator`、`MemoryFastReanchor` 和预测函数目前仍是独立纯模块，尚未接入 `capture_test_page.py` 的实时 tick；页面当前仍主要使用旧的 `RecoveryController`/`_request_live_follow_reanchor` 链。
- `(gap)` `local_reanchor.py` 目前只有 ROI 半径和 score 契约，尚未执行真实候选提取/局部墙体匹配；真实 `Poe2DualPlayerPositionSource` 仍未缓存 descriptor/layout/component 地址，3.6s 冷读实测未改变。
- `(next)` 先完成兼容适配层和局部 ROI 实际调用，再改 warm reader；没有完成这两步前不能让用户进行实机验收。

## 实时恢复旧链隔离（2026-10-07）

- `(implemented)` `capture_test_page.py` 的 live-follow retry 已改为 frame-first 分支，不再调用旧 `RecoveryController.schedule_retry()`；静态/legacy 实验仍保留旧 controller。
- `(verified)` 页面恢复相关聚焦测试 `9 passed`。
- `(boundary)` `_request_live_follow_reanchor()` 在缺少现有 local matcher 时仍有旧全局恢复 fallback；在完成真实局部 ROI 和内存快速重锚接入前，不能宣称旧 live recovery 已全部移除。
- `(next)` 将把 live `_request_live_follow_reanchor` 的 fallback 替换为新 `RecoveryCoordinator` → memory/local/global async 链，并增加测试断言旧 controller 在 live 模式零调用。

## 新策略接入 live reanchor（2026-10-07，进行中）

- `(implemented)` `_request_live_follow_reanchor()` 在 live 模式先调用 `RecoveryCoordinator`；根据最新帧年龄、失配持续时间和预测不确定度选择预测保持、局部视觉或升级恢复，并记录 `recovery_decision`。
- `(implemented)` live retry 仍绕过旧 `RecoveryController.schedule_retry()`；静态路径不变。
- `(boundary)` 当前 memory/global 的实际执行 backend 仍暂时复用旧 `_start_dual_motion(recovery=True)` worker，日志显式标记 `backend=legacy_global_worker replacement_pending=True`；这不是最终接管状态。
- `(next)` 把 memory fast reanchor 作为异步 backend 接入 decision=memory，成功后直接更新 tracker；再将旧 global worker 降为 decision=global 的唯一异步兜底并删除旧直接入口。

## 异步内存重锚接入（2026-10-07，进行中）

- `(implemented)` live decision=`memory` 现在提交到单线程 `ThreadPoolExecutor`，后台调用双人 `Poe2DualMemoryAnchorProvider.read_once()`；控制 tick 不同步等待。
- `(implemented)` tick 轮询 future 完成后校验 tracker/runtime，按角色匹配 anchor，seed tracker、更新最后可信位置并清除 recovery pending；失败才进入全局异步兜底。
- `(implemented)` 页面 suspend/shutdown 会取消 future，shutdown 释放 executor；内存重锚时间写入 started/elapsed 日志。
- `(boundary)` 真实 reader/layout/component 仍未缓存，因此当前后台读取仍可能承担约 3.6s 冷读；旧 global worker 仍是 memory 失败后的最终 backend，但不再由旧 controller 直接升级。
- `(next)` 为异步 memory success/failure 增加注入测试，随后实现 source warm cache，最后移除旧 global backend 的直接调用并改成新 `global_reanchor` 适配器。

## Program session 心跳修复（2026-10-07，实施中）

- `(confirmed)` Host 的普通 `heartbeat` 只更新 `StateStore` source lease，不会更新 `ProgramOutputLease.Deadline`；不能续租 `program.acquire` token。
- `(confirmed)` program lease 当前只有 `program.state` 会更新 `Deadline=now+1000ms`；实际输出 TTL 约 220ms，慢 tick 会先让 output 过期，再在下一次状态写入时发现 program token 已被 Host 删除。
- `(confirmed)` Host 尚无 `program.heartbeat` 命令；Python 输出层也没有独立 heartbeat 调度，所有续租依赖跟随 runtime tick。
- `(boundary)` 客户端请求本身有 `_request_lock`，可以安全地由独立心跳线程与控制线程复用同一客户端；但 token 读取、stop/close、rearm 必须用输出层锁和 generation 保护。
- `(next)` 先为 Host 增加 token 校验的 `program.heartbeat`，再为 `ProgramGamepadOutput` 增加独立保活线程/手动 heartbeat 接口；随后新增“控制 tick 阻塞超过 TTL 仍保持 program lease”的回归测试，并改造失效 session 的可重复 rearm 与旧 token 写入保护。

### 实施结果（2026-10-07）

- `(implemented)` Host 新增 `program.heartbeat`：校验 controller/token，只续 `ProgramOutputLease.Deadline`，不改变 `StateStore` 当前摇杆状态或 output TTL；普通 source heartbeat 仍不能续 program token。
- `(implemented)` `ProgramGamepadOutput` 在 `start()` 后启动独立 daemon heartbeat 线程，默认周期为 `min(250ms, max(50ms, ttl/3))`；`stop()/close()` 会先停止线程再释放 token。
- `(implemented)` heartbeat 发现 token 失效时进入 rearm；即使主控制 tick 没有任何输入/被重型计算阻塞，也会独立恢复 program lease。输出层增加心跳计数、失败数、耗时和 session 状态诊断。
- `(implemented)` `ProgramFollowOutput` 去除“每角色永久只允许一次 rearm”的限制，增加 500ms 退避；重建失败不再把失效 token 持续写入或立即炸掉跟随链。
- `(verified)` Python 聚焦回归 `74 passed`，`compileall` 和 `git diff --check` 通过；完整页面套件单独运行 5 个历史 timing-sensitive 用例 `5 passed`。完整并行套件出现 5 个既有时序 flaky 用例，单独复跑均通过。
- `(blocked)` 当前环境没有 .NET SDK，Host C# 测试无法执行；已补充 `ProgramHeartbeatRenewsOwnershipWithoutChangingOutput` 回归测试，待具备 SDK/Host 构建环境后运行。
- `(next)` 在用户明确授权实机测试前不启动游戏/不发送输入；实机观察重点为 `program_output.heartbeat`、`heartbeat_failures=0`、`session_expired=false`，以及控制 tick 阻塞时 controller=2 不再出现 session expired。

## 最新实机日志核对（2026-10-07 14:46–14:53，只读）

- `(confirmed)` Python 输出层已启动独立心跳，但运行中的 Host 返回 `invalid_argument: Unknown program command.`；`heartbeat_count=0`、`heartbeat_failures` 持续增长到 460，说明当前 Host 可执行文件尚未加载新增的 `program.heartbeat` 协议。不是 token 被撤销，也不是心跳线程没有运行；需要重启/更新 Host 后才能验证保活修复。
- `(confirmed)` 最新会话未出现新的 `Program session expired or was revoked`；controller=2 仍为 `acquired=True`、`inputOwner=program`，但心跳实际上没有续租旧 Host 的 program lease，当前依赖控制帧续租，仍有过期风险。
- `(confirmed)` `follow_hold_target_unconfirmed` 的触发条件是 `target.source == target_hold` 且距离不超过 `arrival_radius=12`；它表示 P1 目标视觉样本超过 `position_ttl_ms` 后正在沿用最后目标，不表示 P2 本身无法到达。此次 P2 距离约 1–2 native px，输出为中立帧，连续 session 仍保持 `armed=True`。
- `(confirmed)` 同一会话 P1 在约 14:53:27 后长时间没有新的有效视觉位置，worker 将 P1 标为 `markers_missing/recovery_required`；P2 已在目标附近，因此进入 hold 是符合当前状态机的，但原因命名容易让人误解为“目标到达未确认”。若 P1 此时实际继续移动而视觉持续失配，P2 会继续守在旧 target_hold 点，属于需要后续处理的定位失配边界。
- `(next)` 先重启/更新 Host 并复测心跳；随后单独处理动态跟随中的 stale target：区分“目标样本过期但目标未移动”和“目标已移动但视觉丢失”，必要时用 P1 的运动预测推进 target，而不是直接长期 hold 在旧点。

## 分段耗时与剩余风险（2026-10-07）

- `(implemented)` 双人实时 worker 现在分别记录 `capture_ms`、`recognition_wall_mask_ms`、`recognition_marker_observation_ms`、`candidate_ms`、`tracking_ms` 和 `total_worker_ms`；仍使用 latest-only，不增加帧队列。
- `(implemented)` 页面跟随 tick 在正常路径和提前返回路径统一记录：`context_ms`、`foreground_gate_ms`、`command_delay_gate_ms`、`live_context_ms`、`visual_state_ms`、`target_update_ms`、`prediction_update_ms`、`runtime_tick_ms`、`output_apply_ms`、`local_contact_ms`、`overlay_render_ms`、`total_tick_ms`。每 tick debug，首两次及每 10 次 info，避免诊断反过来拖慢控制。
- `(implemented)` 首帧日志补充内存锚点读取、截图/识别、候选注册和总耗时；局部/全局重锚日志补充请求耗时。
- `(implemented)` `ProgramFollowOutput` 暴露 `arm_ms/write_ms/neutral_write_ms/rearm_ms/release_ms`，并继续保持连续角色的输出租约；session 失效只走 rearm，不结束跟随。
- `(implemented)` worker drain 日志补充 evidence、preview、overlay、drain 总耗时，用于区分识别慢、Qt 绘制慢和控制页 drain 慢。
- `(verified)` worker、页面、动态 runtime 和虚拟手柄聚焦回归 `187 passed`；`compileall` 与 `git diff --check` 通过。
- `(audit)` 未发现动态跟随 tick 内仍会调用 `stop_follow_experiment()` 的路径；运行时异常、失焦、视觉丢帧、重定位和 Host session 失效均保持连续 session。`stop_dual_motion()` 仅保留给非连续/显式关闭边界。
- `(next)` 用户实机测试时查看 `step=dual_motion.timing`、`step=follow_experiment.timing`、`program_output` 日志；根据最大耗时段再决定是否做 ROI/低频墙体或更深流水线优化。本轮未发送真实输入。

## 跟随完整执行链文档（2026-10-07）

- `(documented)` 已建立 `docs/POE2_AUTOFOLLOW_EXECUTION_CHAIN.md`，按当前代码梳理 P1 手动位置采集、P2 预测/视觉融合、路径规划、局部控制、ProgramFollowOutput/Host 输出、逐 tick 时序、正常/异常/恢复链路。
- `(highlighted)` 特别记录 `target_arrival_unconfirmed` 的真实链路：`target_hold + command_prediction` 进入 `arrival_radius` → `WAITING_POSITION` → `ProgramFollowOutput.release()`，以及相邻的 `Program session expired` 和 `poe2_not_foreground` 独立分支。
- `(documented)` 文档区分静态同目标实验与动态实时跟随的到达语义，记录当前 `arrival_radius=12`、`resume_radius=20`、`effective_fps≈14.4` 等参数和性能边界。
- `(boundary)` 本轮只完成文档审查，没有修改运行代码、没有发送真实输入；后续若修改动态到达语义，应先为文档中标记的异常链补最小回归用例，再实现并验证。

## 动态跟随停止语义重新确认（2026-10-07）

- `(decision)` 用户明确确认：实时跟随是持续性动作，不能由目标接近、目标静止、视觉失配、路径失败、贴墙、窗口失焦、输出 session 失效或重定位自动结束；跟随只能由用户手动停止。
- `(confirmed-risk)` 当前 `runtime state -> ProgramFollowOutput._STOP_STATES -> release()` 是最高风险边界；动态跟随不能把 `WAITING_POSITION`、`ARRIVED`、`BLOCKED` 或 `MAP_MISMATCH` 直接映射为释放输出。
- `(required)` 动态跟随需要独立的持续状态集合：`FOLLOWING`、`FOLLOW_HOLD`、`FOLLOW_PREDICTING`、`FOLLOW_REPLANNING`、`FOLLOW_RELOCATING`、`FOLLOW_REARMING`；这些状态都保留 session、目标、timer、worker 和输出上下文。
- `(required)` `target_hold + command_prediction + distance<=arrival_radius` 必须转为保持/低幅校正，不能产生 `target_arrival_unconfirmed -> WAITING_POSITION -> release()`。
- `(required)` no-safe-route、撞墙、失焦和 Host session 失效只能进入探索、重规划、输入门控或 rearm；重定位也必须在原 session 内恢复。
- `(next)` 实现前先补“普通异常不结束动态跟随”的状态和输出回归用例，再改 runtime/output 边界；静态双人同目标的到达语义保持隔离。

## 动态跟随持续语义首轮实现（2026-10-07）

- `(implemented)` `FollowState` 增加 `FOLLOW_HOLD`、`FOLLOW_PREDICTING`、`FOLLOW_RELOCATING`、`FOLLOW_REARMING`。
- `(implemented)` `SimulatedFollowRuntime(continuous_follow=True)` 用于实时角色跟随；目标接近、`target_hold` 接近、目标/角色暂时缺失和 map mismatch 均不再使用静态终止状态作为动态语义。
- `(implemented)` `ProgramFollowOutput` 增加 `continuous_roles`；连续角色即使收到 `WAITING_POSITION`、`BLOCKED` 或 `MAP_MISMATCH` 等普通异常状态，也不会自动 `release()`，仍由跟随 session 持有输出租约。
- `(implemented)` 实时页面把 live program roles 注册为 continuous roles；静态点击目标和双人同目标不受影响。
- `(verified)` `tests/poe2_live_terrain` 439 passed；`tests/test_poe2_capture_test_page.py` 105 passed。
- `(verified)` 新增回归覆盖：动态目标接近、动态 target_hold 接近、FOLLOW_HOLD 输出保持租约；静态 runtime 到达测试仍通过。
- `(next)` 继续补齐动态异常状态（路径失败、重定位、Host rearm、失焦）的“不结束 session”集成回归，再做 compileall/diff check 和人工链路审查。

## 连续角色异常期间保留输出租约（2026-10-07）

- `(implemented)` `ProgramFollowOutput.release_all(force=False)` 对 `continuous_roles` 发送中立帧并保留 armed/session；`close_all()` 内部使用 `force=True`，只用于明确结束跟随时释放。
- `(implemented)` 页面现有失焦、等待视觉帧、地图上下文缺失、重定位和临时异常路径继续可以中立化输入，但不会撤销动态跟随的输出租约。
- `(verified)` 原有静态输出测试仍通过；实时页面回归已调整为验证中立帧而非 `stop`，`tests/test_poe2_capture_test_page.py` 105 passed。
- `(next)` 继续补动态异常状态的集成断言，确保恢复后同一 armed session 能继续写入方向；再完成 compileall、diff check 和人工链路审查。

## 连续跟随中立帧的 Host session 重建（2026-10-07）

- `(implemented)` `ProgramFollowOutput._write()` 统一处理移动脉冲和中立帧；中立保持期间发生 `Program session expired or was revoked` 也会只重建当前输出 session，不结束跟随。
- `(verified)` 新增中立帧 session 失效回归；`tests/poe2_live_terrain` 440 passed，`tests/test_poe2_capture_test_page.py` 105 passed。
- `(next)` 完成 compileall/diff check 后，人工复核所有动态错误分支是否都保留 follow session；再决定是否进入实机测试。

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
- 部分角色可见、另一角色预测保持时，`prediction_active` 现在也会正确标记为 true；tracker/replay 回归 27 passed。
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

## 离线证据核查（2026-10-07，本轮）

- `(confirmed)` `occlusion_diagnostics` 当前共有 83 个 `evidence.json`，其中 45 个 `recovery_required`、38 个 `degraded`；这些文件各自只有单帧 `candidates/diagnostics`，没有同一 session 的上一帧和恢复帧，因此不能单独证明连续跟随恢复或有效 FPS。
- `(confirmed)` 历史 evidence 的恢复原因主要为 `markers_missing`、`markers_partial_grace`、`markers_missing_grace` 和 `wall_and_local_match_failed`；部分旧 evidence 仍包含角色观察年龄已经超过 `max_age_ms` 的信息，不能把它们当作当前实现的实时输出。
- `(usable)` `data/poe2_live_terrain_test/samples/dual_player_20260925/raw.png` 与 `memory_probes/dual_player_20260925_probe/player-memory-probe-latest.json` 同属 `MapFlotsam:73681455`，图片为 300×300，探针提供双角色 native 网格 `(956.5,430.5)`、`(962.5,424.5)`；这是当前唯一可直接做“真实 raw + 同实例双锚点”离线首帧候选实验的历史样本。
- `(boundary)` `latest.npz` 和 `dual-debug-current` 探针属于其他地图实例，不能与 `dual_player_20260925/raw.png` 拼接验证注册；`multiframe_sessions` 及部分旧 sample 目录存在 Windows ACL 拒绝，不能假设其中有可读连续帧。
- `(next)` 先用同实例双人 raw 做低日志候选/注册耗时回放，再用现有合成 replay 验证“正常→单帧异常→恢复”；若要实证真实连续帧处理频率，需要用户补采最小连续序列。
- `(implemented)` 新增 `tests/poe2_live_terrain/test_historical_dual_replay.py`：直接读取已归档的 `dual_player_20260925/raw.png`、`wall.png` 和配置颜色，执行一次首帧注册以及真实 wall/raw 的跟踪恢复回放；测试不写应用日志。
- `(verified)` 历史 raw 回归 2 passed：首帧结果 `accepted`，最佳 pair confidence ≥ 0.90、shape quality ≥ 0.85；`tracking → degraded(prediction_active) → tracking` 恢复链通过；worker 路径连续 5 次最大耗时 < 33ms，`dropped_results=0`。
- `(boundary)` 该首帧注册使用同一张历史墙体图构造受控几何夹具，避免把不同实例的 native terrain 拼在一起；它验证真实图像上的单次注册流程和候选质量，不证明真实 native 全图配准耗时。
- `(diagnostic)` 对 83 张历史异常 raw 使用 evidence 自带颜色配置做无日志批量检测，平均检测耗时约 0.82ms；56/83 张仍提取到至少两个候选，23/83 张没有候选。后者属于输入确实缺失，不能靠提高采样频率单帧修复，只能由上一帧预测/后续恢复帧处理。

## 最新实机跟随异常核对（2026-10-07）

- `(confirmed)` 最新日志中的 `target_arrival_unconfirmed` 出现在 `12:18:11~12:18:39`，目标从约 `(950,982)` 后稳定在 `(960.3059,974.3315)`；不是目标继续移动造成的瞬时追赶误判。
- `(confirmed)` 触发时 P2 的当前估计来源为 `command_prediction`，位置 `(957.8049,981.7013)`，距离目标 `7.7826`，到达半径 `12.0`；最近一次视觉位置仍停在更早的 `(900.0785,1070.1693)`，所以视觉没有确认到达。
- `(confirmed)` `runtime.py` 在 `current.source == "command_prediction" and distance <= arrival_radius` 分支返回 `reason="arrival_unconfirmed"` 并生成短脉冲；但下一次页面诊断把状态显示为 `waiting_position`、`vector=(0,0)`、`acquired=False`，输出层释放了手柄。这是一次预测到达与实际输出状态不一致，而不是首帧或路径规划失败。
- `(confirmed)` 这次会话之后还出现 `step=live_role_follow.waiting_game_foreground reason=poe2_not_foreground`，约 12:18:39~12:18:44，最终是用户请求停止；窗口失焦是独立的后段异常，不能和 `target_arrival_unconfirmed` 混为一个根因。
- `(confirmed)` 同一会话实时目标前段确实连续变化，12:17:22~12:18:11 从约 `(1068,1066)` 移到 `(960,974)`；12:18:11 后目标保持不变。因此本次异常更接近“动态跟随目标停止后，P2 未被视觉重新吸收，预测到达分支未形成稳定 hold”而非持续移动目标策略本身。
- `(boundary)` 当前证据还不能证明游戏实际没有移动：日志只能证明虚拟手柄输出在 `waiting_position` 快照时已被释放，且视觉最后观测很旧；需要下一轮保留输出层每 tick 的 `program_ready → arrival_unconfirmed → released` 时序和游戏前台状态，区分“视觉未更新”与“角色未移动”。

## 本轮讨论结论（未改代码）

### 补充证据：输出会话与性能

- `(confirmed)` `12:18:12.467` 发生独立的 `VirtualGamepadError: Program session expired or was revoked`，约 1.1 秒后重新 `output_armed`；Host 随后继续接受 controller=2 报告。这是输入会话短暂失效，不是路径规划失败，但会放大视觉滞后。
- `(confirmed)` `12:18:15.123` 左右开始出现 `target_arrival_unconfirmed` 后，Host 的 controller=2 报告停止，页面持续显示 `waiting_position/vector=(0,0)/acquired=False`；因此这次 target arrival 实际释放了输出。
- `(confirmed)` 同段 worker 有效频率约 14.4 FPS、`processing_ema_ms≈58.5ms`、`dropped_results≈225`，P2 视觉年龄从约 8 秒增长到 34 秒，属于长期预测未重新吸收的背景异常。
- `(decision pending)` 输出会话过期需要和跟随状态解耦：输出适配层应记录“失效→重建→首个成功报告”，而不是让一次会话失效与视觉到达状态叠加成停顿。

- 跟随和静态定点不能共用同一个“预测进入半径即等待视觉确认”的终止语义。动态跟随应在目标新鲜或目标刚停止时保持低幅度校正，不应因单次预测距离小于半径而释放输出。
- 只有满足“目标稳定窗口 + 至少一次新的可信视觉确认 + 连续若干 tick 在半径内”才可进入 `ARRIVED/HOLD`；否则继续跟随或进入有界预测保持。
- `poe2_not_foreground` 需作为独立输入门控记录与处理，不应触发地图重定位，也不应伪装成 target arrival 异常。
- 下一步先补最小回归测试和更细的输出时序诊断，再讨论只对动态跟随放宽到达分支，避免破坏双人定点寻路。
- `(confirmed)` 这不是 ViGEm 驱动或 Host 进程断联：Host 日志在同一时间仍显示 `backendConnected=True`，controller=1 持续收到 report；失效的是 controller=2 的 program session token。
- `(confirmed)` controller=2 的 TTL 为 `220ms`，而异常会话中页面 `runtime_tick_ms` 达 `472–926ms`、总 tick 达约 `1s`；一次 `program.state` 续租前已超过 Host TTL，Host 合法撤销 token 并返回 `session expired or was revoked`。
- `(confirmed)` 失效后 `ProgramFollowOutput._write()` 每角色只允许一次 rearm；rearm 未形成稳定成功边沿后，后续移动帧和 foreground 中立帧继续使用失效 session，造成重复错误。`release_all()` 在失焦门控中被高频调用，放大了错误日志。
- `(inferred)` 基础问题是控制 tick 与 Host TTL 没有隔离：重型 runtime/恢复计算运行在 GUI 控制链中，输出 session 依赖同一条慢链路续租；不是单纯虚拟手柄硬件故障。
- `(next)` 优先修复顺序：输出租约独立保活/续租 → session 失效可重复 rearm 且有退避 → 失效 token 不再重复写中立帧 → 再把 recovery/runtime 重计算移出控制 tick。

## 当前实现进展（2026-10-07）

- `(implemented)` live 全局恢复统一通过 `recovery/global_reanchor.py::GlobalReanchorBackend`，页面 live 分支不再直接调用旧 worker。
- `(implemented)` 双人内存 source 缓存 layout，并在地图实例变化时失效重解析。
- `(implemented)` recovery episode 在策略决策前去重；聚焦页面/恢复/内存测试 `111 passed`，新增 backend 契约测试。
- `(remaining)` 局部 ROI 模块仍是契约层，真实匹配由 `DualVisualTracker` 下一帧执行，尚未把 score 显式反馈给 coordinator。
- `(next)` 运行完整套件、compileall、diff check 后再安排实机验收。

## 当前实现进展（2026-10-07）

- `(implemented)` live 全局恢复统一通过 `recovery/global_reanchor.py::GlobalReanchorBackend`，页面 live 分支不再直接调用旧 worker。
- `(implemented)` 双人内存 source 缓存 layout，并在地图实例变化时失效重解析。
- `(implemented)` recovery episode 在策略决策前去重；聚焦页面/恢复/内存及 backend 契约测试 `111 passed`。
- `(verified)` 局部 ROI 真实执行由 `DualVisualTracker.request_local_correction()` 在下一帧完成；页面不会把局部请求直接升级为全局恢复，只有内存失败才进入显式 global backend。
- `(verified)` 完整 PoE2/页面/worker/gamepad 套件 `576 passed`，compileall 与 diff check 通过。
- `(boundary)` 本轮未发送真实输入，Host 心跳协议仍需在更新后的 Host 重启后实机确认。
- `(next)` 重启程序和 Host 后进行一次完整双人跟随测试，重点观察 `recovery_decision`、`memory_reanchor_*`、`reanchor_backend backend=global_async` 和 `program.heartbeat` 日志。

## 架构修正结论（2026-10-07）

- `(decision)` 预测与视觉纠偏必须是两个独立、latest-only 的处理通道；当前实现仍是视觉 worker 产出状态后，由页面 tick 在视觉失配时退化到 `command_prediction`，不是持续并行的视觉/预测融合。
- `(confirmed)` 当前 P2 视觉丢失后没有使用下一帧/上一可信帧做局部 ROI 重定位，而是被 `occlusion_held` 保持并继续命令预测；这是本次漂移的结构性根因。
- `(design)` 新链路：预测通道按手柄输出和速度模型连续推进；视觉通道按最新帧做全局候选/局部 ROI 纠偏；融合器按观测新鲜度和置信度吸收视觉，不允许任一来源永久独占。
- `(design)` 视觉暂时不可信时保留预测输出但立即启动局部纠偏；局部纠偏失败才允许低频内存快速重锚；内存失败才进入异步全局恢复。异常不释放动态跟随 session。

## 双通道执行模型（用户确认方向，2026-10-07）

- `(confirmed)` 当前实现不是全链路多进程：`Poe2DualMotionWorker` 是 Python `threading.Thread`，内存重锚使用 `ThreadPoolExecutor`，融合/路径/输出在 Qt 控制线程；因此视觉丢失后的预测与局部纠偏没有真正独立运行。
- `(decision)` 采用“预测进程/视觉进程/控制融合线程”三段式，而不是为每种异常创建进程。预测进程保持 30–60Hz，小状态输入；视觉进程 latest-only 处理截图和局部 ROI；融合线程负责时间戳、置信度、输出与状态机。
- `(design)` 内存快速重锚作为独立低频任务（一次读取、冷却、结果带 generation/instance 校验）；全局恢复仍异步且低频，不能阻塞控制输出。
- `(constraint)` 不直接把现有 Qt worker 改成进程：截图 provider、Qt signal 和 Windows 句柄不可直接跨进程复用；需要先定义共享内存/序列化快照契约和退出协议。

## 最新实机异常（2026-10-07 17:19，会话只读分析）

- `(confirmed)` P1 `StrDexFourb` 持续有视觉接受，例如 `17:19:34.503` native `(945.45,654.33)`；P2 `DexFourb` 的最后可信视觉时间为 `17:18:48.559` 左右，至 `17:19:34` 已失配约 `45.9s`。
- `(confirmed)` P2 在 `17:19:20~17:19:34` 反复出现 `dual_motion.tick ... markers_partial_grace/markers_missing`，但页面每次都记录 `live_role_follow.occlusion_held reason=no_recovery_evidence`，没有进入 `recovery_decision`、`memory_reanchor` 或局部/全局重锚。
- `(confirmed)` P2 位置完全由 `command_prediction` 维持，页面估计从约 `(933,827)` 推进到 `(922.9,774.2)`；同段 tracker 的 `uncertainty_native` 已从约 `102` 增长到 `206`，超过现有观察边界，但跟随层使用了另一套约 `10~12` 的预测不确定度，形成了错误的“仍可继续预测”判断。
- `(confirmed)` P2 输出持续为非零手柄脉冲，`observed_speed≈15.82`、每次 `command_duration_ms=80`；这证明预测器把“命令已发送”当成了“角色已按预期位移”，而没有新的视觉/内存事实校正，因此可能把 P2 推到 P1 前方。
- `(confirmed)` 目标点本身不断来自 P1 的视觉位置，P2 路径目标随 P1 变化；问题不在目标源停止刷新，而在 P2 自身位置源已经过期仍被用于路径规划。
- `(confirmed)` 当前 Host 心跳仍是旧协议表现：`heartbeat_count=0`、`heartbeat_failures>1000`；本段没有 session expired，但不能把 `controller=2 armed` 当作游戏真实移动已确认。
- `(conclusion)` 首要根因是“P2 长期视觉失配被 occlusion-held 抑制恢复 + 命令预测继续累积”，不是单纯方向反转。需要把双人跟随的恢复触发从“是否检测到墙体接触”改为“角色观测年龄/不确定度/预测-视觉一致性”联合门控；P2 超过短时预测窗口后必须重新使用最新帧局部匹配或低频内存锚点，不能因 `no_recovery_evidence` 永久保持。
- `(boundary)` 当前截图只能证明 UI 估计的 P1/P2 标记和目标叠加关系，不能单独证明游戏内实际 P2 已超过 P1；需下一次记录内存锚点或连续视觉恢复帧作为最终事实。

## 双通道引擎重构计划（2026-10-07）

- `(checkpoint)` 已将此前恢复链和 Host/session 改动提交为 `ea72667 checkpoint: isolate follow recovery boundaries`；未提交 evidence 数据。
- `(design)` 完整设计已写入 `docs/plans/2026-10-07-poe2-follow-engine-multiprocess-design.md`。
- `(decision)` 采用两个长期业务进程：`VisionProcess` 负责截图/墙体/人物/局部 ROI，`FollowControlProcess` 负责预测/融合/路径/恢复/输出；Qt 只做 UI，Host 保持独立。
- `(design)` 内存快速重锚和全局恢复作为控制进程内的低频单次任务，不为每种异常创建独立进程；进程间使用 latest-only shared frame ring 和带 generation/sequence/instance 的结构化快照。
- `(next)` M0 先冻结回放和纯逻辑契约，随后按 M1→M7 迁移；在 M1/M2 离线回归通过前不迁移实机输入。

## M0 离线回放夹具完成（2026-10-07）

- `(implemented)` 新增 `experimental/follow_engine/replay.py`，提供无副作用的 `ReplayEvent`、`ReplayManifest` 和 manifest 加载/稳定签名。
- `(implemented)` 新增 `tests/poe2_live_terrain/fixtures/follow_replays/scenarios.json`，覆盖正常双人、单帧失配、短/长视觉丢失、局部恢复、内存恢复、Host session 失效和地图变化。
- `(verified)` `tests/poe2_live_terrain/test_follow_engine_replays.py`：`2 passed`；回放明确 `real_input_allowed=false`，不连接游戏、内存或 Host。
- `(next)` 进入 M1.1：实现跨进程不可变 DTO 和输入校验；完成后再实现 generation/sequence 门控。

## M1.1 纯契约完成（2026-10-07）

- `(implemented)` 新增 `follow_engine/contracts.py`：`FrameSlot`、`VisualObservation`、`PredictionSnapshot`、`FusionSnapshot`、`OutputIntent`、角色状态 DTO 和 `StageTiming`。
- `(boundary)` 所有 DTO 都是 frozen/slots，不包含 Qt、游戏内存、截图 provider 或手柄副作用；角色映射和消息头在构造时校验。
- `(verified)` `tests/poe2_live_terrain/test_follow_engine_contracts.py`：`7 passed`，覆盖不可变映射、有限数值、归一化输出、错误角色和非法帧元数据。
- `(next)` M1.2 实现 generation/sequence/map instance 门控，确保迟到进程结果不能覆盖新会话。

## M1.2 代际与序列门控完成（2026-10-07）

- `(implemented)` 新增 `follow_engine/generation.py`：`GenerationClock` 创建单调 session generation，`SequenceGate` 校验 generation、map instance 和严格递增 sequence。
- `(verified)` `tests/poe2_live_terrain/test_follow_engine_generation.py`：`2 passed`；覆盖停止/重启代际、重复帧、逆序帧、旧代际和地图实例不一致。
- `(boundary)` 门控只处理消息生命周期，不改变人物预测、视觉算法或输出行为。
- `(next)` M1.3 实现 command odometry、速度校准、位置融合和预测不确定度增长。

## M1.3/M1.4 预测融合与恢复策略完成（2026-10-07）

- `(implemented)` 新增 `follow_engine/tracking/`：命令里程计、实际速度校准、预测/观测融合、创新门控、不确定度增长和角色跟踪状态。
- `(implemented)` 新增 `follow_engine/recovery/recovery_policy.py`：L0–L3 恢复决策、局部优先、内存冷却、全局单次异步语义、Host rearm 分支和动态 session 保持。
- `(verified)` `test_follow_engine_fusion.py`：`7 passed`；`test_follow_engine_recovery_policy.py`：`7 passed`。
- `(fixed)` odometry 发现并修复负数/NaN pulse duration 会被静默截断的问题；tracking state 同步拒绝非有限位置、速度和不确定度。
- `(next)` 运行 M0/M1 聚焦全套并提交本批次；之后进入 M2 latest-only 帧环和 VisionProcess。

## M2.1/M2.2 latest-only 帧通道与视觉进程骨架（2026-10-07）

- `(implemented)` 新增 `follow_engine/latest_frame_buffer.py` 和 `shared_frame_ring.py`；固定容量、最高 sequence 优先、旧帧丢弃，不使用无界图片队列。
- `(implemented)` 新增 `follow_engine/vision/capture_adapter.py` 与 `vision_process.py`；VisionProcess 使用 Windows spawn-safe 入口、bounded event queue、显式 stop/join/terminate 和 generation/map instance 校验。
- `(fixed)` 首次跨进程测试发现 `mappingproxy` 无法 pickle；DTO 已改为 pickle-safe 的只读字典，契约测试和 spawn 视觉进程测试均覆盖此边界。
- `(verified)` 帧环、视觉进程、契约聚焦测试：`10 passed`。
- `(boundary)` 当前视觉进程只验证 capture/processor 生命周期和消息传输，尚未接入 PoE2 墙体、人物候选、局部 ROI 算法。
- `(next)` M2.3 拆出 wall processor、marker processor、双人关联和 local ROI matcher，保持视觉进程不访问 Qt、内存和手柄。

## M2.3 视觉处理组件完成（2026-10-07）

- `(implemented)` 新增 `vision/wall_processor.py`：墙体位移低频处理和质量/形状门控。
- `(implemented)` 新增 `vision/marker_processor.py`：复用现有 HSV profile 候选提取，单独记录候选数和处理耗时。
- `(implemented)` 新增 `vision/dual_association.py`：位置、速度、双人相对几何为主；颜色冲突造成部分匹配时自动进行无颜色几何回退。
- `(implemented)` 新增 `vision/local_roi_matcher.py`：按 `80/140/220` 半径逐级局部匹配，失败只返回结果，不产生停止动作。
- `(verified)` `test_follow_engine_vision_processors.py`：`4 passed`；覆盖墙体位移、颜色候选、双人颜色污染和 ROI 扩展。
- `(boundary)` 这些组件已具备独立契约，但还未把 PoE2 现有 `DualVisualTracker` 全量搬进 VisionProcess；下一步接入控制进程前先建立组合处理器。
- `(next)` M2 阶段收尾：增加视觉处理组合器，把最新帧→墙体→人物→关联→局部 ROI 输出为 `VisualObservation`。

## M3.1–M3.3 控制进程与输出调度器（2026-10-07）

- `(implemented)` 新增 `control/follow_control_process.py`：纯 `FollowControlRuntime` 和 spawn-safe `FollowControlProcessHandle`；父进程只发送视觉/目标消息，子进程发布最新融合快照。
- `(implemented)` 新增 `control/route_controller.py`：输出有界方向和 `FOLLOW_HOLD` 语义；目标进入半径只发中立意图，不释放 session。
- `(implemented)` 新增 `control/output_scheduler.py`：输出提交、连续角色租约、Host heartbeat、session 过期 rearm 分开处理。
- `(verified)` 控制运行时 `3 passed`、spawn 控制进程 `1 passed`、输出调度 `2 passed`。
- `(boundary)` 当前 route controller 是可替换的直线路由骨架，尚未接入现有地图 PathFinder/局部 steering；输出 scheduler 尚未绑定真实 Host。
- `(next)` M4 实现 memory fast reanchor/global async backend 的新 port，并为控制进程接入恢复结果。

### M5.2/M6.1 页面 adapter 与阶段计时（2026-10-07）

- `(implemented)` 新增 `ui/modes/poe2_live_terrain/follow_engine_adapter.py`，页面侧只暴露 start、target_clicked、poll、stop 和状态回调，不复制控制/恢复逻辑。
- `(implemented)` `StageTiming` 新增 prediction/recovery/memory/global 字段；控制 runtime 记录预测、ROI、恢复轮询、内存/全局 future、路线和总 tick 耗时。
- `(verified)` page adapter、contracts、runtime 聚焦测试 `15 passed`，compileall 通过。
- `(boundary)` 该 adapter 尚未替换现有 `capture_test_page.py` 的默认旧跟随入口；实际页面切换需要先完成压力和生命周期回归。
- `(next)` 实现 M6.2 latest-only/控制压力回放和 M6.3 spawn 启停回归；之后再决定页面默认入口的迁移点。

### M6.2/M6.3 压力与生命周期回归（2026-10-07）

- `(implemented)` 新增 latest-only 压力回归：模拟 300 帧高速发布，槽只保留最新值，旧帧有界丢弃；控制 runtime 模拟 30Hz 视觉/60Hz tick，检查 session 保持与 tick 总耗时。
- `(implemented)` 新增 spawn 控制进程重复启停回归，覆盖 5 轮 generation，确认 stop 后没有残留 process 引用。
- `(verified)` `pytest -q tests/poe2_live_terrain` 为 `503 passed`；compileall 通过；未发送真实输入。
- `(boundary)` 压力门槛是离线结构/耗时门，不代表真实 PoE2 图像识别耗时；实机验收仍需在 M8 分级执行。
- `(next)` 补离线 replay runner，把 M0 场景接到新 port，验证 visual miss/local/memory/global/host-expired 不释放 session；随后再评估旧页面入口迁移。
