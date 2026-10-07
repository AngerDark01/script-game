# CODEBASE

## 0. 当前物理布局与路径解释

Auto Modules 采用 `src` package 布局。本文后续长期积累的算法说明中仍使用部分逻辑简称；这些简称必须按下表解析，不能据此重新创建根级兼容包。

| 文档逻辑简称 | 当前权威物理路径 | 说明 |
| --- | --- | --- |
| `core/...` | `src/auto_modules/core/...` | 纯算法、领域契约、状态机、任务和 intent |
| `gui/...` | `src/auto_modules/ui/...` | PySide6 展示和交互协调 |
| `workflows/...` | `src/auto_modules/application/workflows/...` | 应用用例编排 |
| `features/<game>/...` | `src/auto_modules/features/<game>/...` | 游戏专用业务策略、模型组合和业务诊断 |
| `utils/...` | `tools/probes/...` | 显式执行的验证探针 |
| `debug/...` | `tools/debug/...` 或 `data/diagnostics/...` | 可复用脚本与生成数据分离 |
| `assets/...` | `resources/assets/...` | 只读发布资源 |
| `configs/events/...` | `data/events/...` | 可写事件定义和路由 |
| `map_data/...` | `data/maps/...` | 地图目录；单个地图包文件仍名为 `map_data.npz` |
| `virtual_gamepad/host|launcher|protocol` | `services/virtual_gamepad/...` | 独立 C# 服务 |
| `lan_input_sync/...` | `services/lan_input_sync/...` | 独立 C# LAN 库 |
| `distribution/...`、`installer/...` | `packaging/distribution/...`、`packaging/installer/...` | 离线发布和安装器 |
| `architecture_docs/...` | `docs/architecture/...` | 历史和专题架构资料 |

特殊迁移不使用上述简单前缀映射：

- 原 `core/input` 和 `core/platform` 的具体副作用实现现位于 `src/auto_modules/adapters/input`、`adapters/platform`。
- RapidOCR 实现位于 `adapters/perception`；通用 perception contracts/algorithms 仍在 `core/perception`。
- `EventWorkbenchService` 位于 `application/event_workbench`，Host bridge 位于 `adapters/host`，Win32 hotkeys 位于 `adapters/windows`。
- Torchlight follow 用例、规划器和诊断位于 `features/torchlight/follow`；`SharedPosition` / `SharedEvent` 位于游戏无关的 `core/communication/shared_state.py`，Host wire translation 位于 `adapters/host/follow_transport.py`。
- Torchlight Portal/Loot 定义和识别实现位于 `features/torchlight/{portal,loot}`；`core` 只保留通用事件生命周期、感知、定位、导航任务和动作契约。
- `core/events/automation/action_sequence.py` 是通用动作序列运行时；`features/torchlight/skills/follow_chain.py` 只提供 Torchlight 业务 facade，旧 `core/events/follow_chain.py` 已删除。
- 通用 `ProgramGamepadOutput` 的 Host 协议实现和 Host-compatible clock 位于 `adapters/virtual_gamepad/program_output.py`。
- 根 `main.py` 仅把 `src` 放入导入路径并委托 `auto_modules.bootstrap.main.main()`；完整启动逻辑不再位于根脚本。

当前强制依赖方向为 `core <- application/adapters <- ui/bootstrap`。箭头表示右侧可使用左侧；`core` 不得导入 `application`、`adapters`、`ui` 或 `bootstrap`。所有生产 Python import 使用 `auto_modules.*`。

## 当前补充：PoE2 实时地形预览

自动跟随从启动、冷启动同步、双人视觉帧、目标融合、路径规划、局部脱困、程序输出和全局恢复的完整文字链路见 [`docs/POE2_AUTOFOLLOW_COMPLETE_LOGIC.md`](docs/POE2_AUTOFOLLOW_COMPLETE_LOGIC.md)。该文档以当前源码为准，明确区分 native 坐标、UI 展示坐标和手柄输入坐标，并记录实时跟随、地图点击跟随、双人同目标三种组合及异常状态。

多帧全局定位、滚动局部地图、方案 A/B 及导航消费方案已在 PoE2 数据采集实验台实现，设计与实施基线分别见 `docs/plans/2026-09-23-poe2-multiframe-localization-navigation-design.md` 和 `docs/plans/2026-09-23-poe2-multiframe-localization-navigation-implementation-plan.md`。新链路没有替换正式 `Poe2HybridProductRuntime`：正式页面仍使用一次锚点注册、`visual_f2f` 和有界局部纠偏；只有测试台显式启动多帧 experiment 时才执行新状态机。

### `features/poe2/live_terrain/experimental/multiframe_localization`（verified implementation, real-game calibration pending）

本目录承载多帧全局定位实验：`models.py` 定义只读 `MultiFrameEvidence`、`CandidateRegion`、`PositionEstimate` 和 `MotionState`；`motion_gate.py` 复用通用 canonical wall 与 phase displacement，将相邻帧分类为 moving/stationary/unknown 并决定关键帧准入；`evidence_window.py` 用帧数、时间、累计行程、真实数组字节和 segment 隔离管理有界证据；`rolling_submap.py` 以可逆 wall/observed 权重从保留帧重建有限局部地图；`shape_registration.py` 提供 Huber、异常点裁剪、覆盖率和局部切向一致性联合评分；`strategy_a.py` 在结构阈值后冻结拼图注册，`strategy_b.py` 从 45 度 basin 做粗到细角度/比例精化；`registration_validator.py` 独立执行锚点、轨迹、holdout、margin 与 A/B 冲突门；`local_corrector.py` 在跟踪期做有界局部形状纠偏；`state_estimator.py` 在确认候选内部做位移预测、Mahalanobis 门控和协方差更新；`coordinator.py`、`session.py` 管理收集/注册/跟踪/恢复生命周期；`navigation_adapter.py` 只输出新鲜确认的领域中立 observation；`archive.py` 与 `composition.py` 负责 schema 3 真实回放和 PoE2 测试台组合。

这些模块当前仍是 PoE2 实验契约，待真实多地图回放证明与游戏无关后，才考虑把运动门控、证据窗口、评分和位置估计契约下沉到 `core/localization`。`PositionEstimate` 的 covariance 只读复制；`EvidenceWindow` 对静止、非关键帧或未接受位移不增长版本，segment 断链会清空旧帧并递增版本。注册在一个单 worker 中执行，结果用 `(generation, instance_id, recovery_revision, evidence_version, segment_id)` 栅栏提交；注册期间的可靠位移在确认后补偿，stop/reset 后旧 worker 结果也不能发布。恢复每个 revision 最多读取一次人物内存锚点。reference、锚点、位置、轨迹和导航 observation 始终使用原始 native terrain 坐标；`SimilarityTransform2D` 是局部视觉 `L -> N` 的唯一方向/镜像/比例/平移事实源。配置不再包含用户手工旋转或镜像字段；显示层仅在 estimate 与 coordinator 的 registration version 一致时，把地图、轨迹、候选和人物点作为整体变换。

`src/auto_modules/features/poe2/live_terrain/` 是 PoE2 手动地形采集、监控配置、profile、定位和会话的正式业务边界。`capture_adapter.py` 只调用外部 `D:\ACloud\poe2-map-research\experiments\live-terrain-preview\live_preview.py` 的 `init`/`capture`，校验 `latest.json` 的 `tool=manual-live-terrain-capture`、拒绝 checkpoint 字段，并限制 `native_grid.npz` 路径留在外部 producer 的 output 目录内。成功后由 `native_grid.py` 使用 `allow_pickle=False` 读取 `raw_cells`、`cell_state`、`known_mask`、`wall_layer`、`explored_map` 和 `metadata_json`。
外部 producer 的 `windows_capture.py` 在每次 `init` 读取当前进程可执行文件 PE/.text 指纹。已知指纹保留原 RVA/恢复路径；未知指纹只读扫描 GameState AOB、逐候选验证活动 state/角色元数据/地形指针/行宽与区域实例，再验证描述符五项 guard 和稳定的有界地形样本；通过后仅在本次 session 中记录动态 contract 与已验证 RVA，不写白名单。后续 `capture` 用同一进程身份和 RVA 再验布局、guard 与全量稳定读取；版本、进程或实例变化会拒绝复用。此验证仅覆盖地形采集布局，不能自动证明双人角色组件偏移在新版本仍兼容。

`contracts.py` 定义只读 `TerrainSnapshot` 和 `CaptureMetadata`。快照数组始终保持原生 `height x width` 的 `yx` 方向，数组会复制并关闭写入标志；`cell_state` 只允许 `-1/0/1`。`service.py` 的 `Poe2TerrainService` 管理 `NEW -> READY_TO_CAPTURE -> CAPTURED/ERROR` 生命周期，初始化或捕获失败会清除旧快照；`memory_store.py` 不提供任何文件写入接口。`debug_archive.py` 是显式测试适配器，保存转换后的最新 NPZ 和 manifest 到 `data/poe2_live_terrain_test/`，不参与页面读取。`capture_samples.py` 独立负责同一截图帧的原图、预处理图、匹配特征、可选 wall/fog/raw-gray 诊断层及可选地形预览归档，写入 `data/poe2_live_terrain_test/samples/`；它不改变或替代 NPZ 地图归档。

`src/auto_modules/ui/modes/poe2_live_terrain/` 是 PoE2 业务页面。`presenter.py` 将快照的已知可行走区域转成深灰底面，并从可行走区域边界生成白色轮廓，得到旧绘图地图的黑底/灰面/白线格式；原始数组不被修改。未确认自动注册时展示 native 地图并报告“等待自动校准”；`LocalizationPresentationState` 只在 estimate 和 coordinator registration version 一致时携带 registration。方向校准后的底图通过 `prepare_localization_map()` 只生成一次，位置、轨迹和候选点由 `ScalableMapWidget` 的独立 overlay layer 绘制；旧 `present_localization_overlay()` 仍保留给采集/兼容调用方。`page.py` 处理初始化、手动获取、清空、独立监控配置、实时预览、hybrid 人物定位状态和 marker/轨迹显示，并在构造时立即把 active profile 应用到 runtime；正式页的 `monitor_timer` 是产品定位的唯一 Qt 驱动。PoE2 页面只把 `ScalableMapWidget` 的初始 fit 倍数设为 1.35，定位成功后再以人物位置进行 2.4 倍跟随放大，失败帧使用最后可信位置保持视野。嵌入正式页的 `capture_test_page.py` 另外接收单帧 hybrid factory 和多帧 factory，拥有独立 experiment/session/timer；顶部“开始首帧定位”按钮直接验证内存 anchor + 局部几何匹配，`定位控制`窗口中的 `multiframe_panel.py` 仍提供 A/B 开关、开始/停止/重置/保存、rolling submap、候选和耗时诊断。单帧与多帧启动互斥，不同时消费同一截图源；采集页只用于数据采集和算法诊断，不接管正式 runtime。`capture_monitor_window.py` 自有截图/拼图定时器，同步展示原图、预处理、匹配特征、实际落图 wall mask、当前地形和局部拼图，并浏览历史样本。实验拼图通过 `Poe2StitchingSession` 组合通用 `core.mapping.MapStitcher`；正式混合定位通过 `Poe2HybridProductRuntime` 组合 `experimental/hybrid_localization` 的一次性内存锚点和有界视觉跟踪。`capture/selection_controller.py`、`config_panel.py` 和 `profile_toolbar.py` 是 PoE2 侧独立复刻的监控配置 UI，参考绘图模式的交互但不修改或反向依赖绘图模式；方向控件已完全删除。`MainWindow` 将它追加为独立第 8 个页面，通过 PoE2 composition 注入 terrain service、hybrid 产品 runtime 和采集测试依赖；它不接入路线规划、动态障碍、Xbox 或 LAN。

### `src/auto_modules/features/poe2/live_terrain/movement.py`
职责：保存 PoE2 游戏专用的 native-map 到左摇杆 2x2 输入基底，并明确 canonical native 路线向量在程序输出边界原样通过。该适配属于 PoE2 输入边界，不改变通用 `ProgramGamepadOutput` 默认基底或其他游戏。
关键导出：`POE2_MAP_TO_STICK_BASIS`（`(0.5, -0.5, 0.5, 0.5)` 等距投影基底）、`native_route_vector_for_program_output()`（finite 校验后保持 native 向量）、`native_map_vector_to_local()`（仅供通用几何逆变换）。
对外依赖：`core.localization.displacement.inverse_transform_local_displacement`。
注意事项：registration 的 angle、horizontal reflection、scale 已在 source/display → native 的点变换中使用，不能在 Xbox 输出前再次应用；translation 也不进入向量。固定基底仍需用 native X/Y 两个短程方向实机标定；未经双轴验证不得宣称路线已穿门成功。

### `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_follow/program_output.py`
职责：把领域中立的逐角色跟随观测交给已显式租约的程序手柄输出，并在 PoE2 页面组合层注入当前地图注册向量变换。
关键导出：`ProgramFollowOutput`；构造参数 `vector_transform` 是可选的纯 `(x, y) -> (x, y)` 回调，负责输出边界前的坐标适配。
对外依赖：`multiplayer_follow.models` 的 `FollowObservation`、`FollowState`、`RoleId`；标准库 `Callable`、`Mapping`、`dataclass`。
注意事项：只对非零 `PROGRAM_READY` 向量调用回调；中性帧保持 `(0, 0)`，停止状态仍先中性再释放 lease。回调异常向上抛出，由页面 fail-closed 并停止输出；该模块不认识 PoE2、旋转或地图业务。

### `ui/widgets/scalable_map.py`（verified）

职责：通用 QPixmap 地图显示、滚轮缩放、拖拽平移、源坐标点击和轻量 marker/trail overlay；不拥有地图业务或定位状态。关键导出：`ScalableMapWidget`、`set_image()`、`set_overlay()`、`set_target()`、`clear_overlay()`、`fit_to_view()`、`focus_on_point()`、`zoom_in()`、`zoom_out()`、`reset_zoom()`、`eventFilter()`。对外依赖：PySide6 Qt widgets/gui/core。注意事项：overlay 坐标与当前 `original_pixmap` 坐标一致，组件只在 paint event 中绘制 marker，不复制底图；`set_target()` 只更新目标标记，保留人物/候选/轨迹/路线；`focus_on_point(point, zoom_multiplier)` 的点必须是未缩放源 pixmap 坐标，第一次调用建立跟随基准，后续调用只移动 scrollbar，并跳过未变化的滚动目标，手动缩放会重建基准；`image_label` 的 resize 事件同步 `overlay_label` 几何，避免窗口放大后底图与标记层错位；其他页面默认 fit multiplier 保持 `1.0`。

`focus_on_point()` 在有效源图和有限二维点存在时，必要时先计算当前 fit scale，再乘以正的 zoom multiplier，按缩放后的源坐标设置水平/垂直滚动条，使人物进入视口中心；空图、非法点直接忽略，非正 multiplier 抛 `ValueError`。用户仍可通过拖拽和 Ctrl+滚轮覆盖自动视角。

### `ui/widgets/aspect_preview.py`（verified）

职责：通用等比例图像预览控件，保存原始 `QPixmap` 并在控件 resize 时重新缩放，不改原始截图或视觉数组。关键导出：`AspectPreviewLabel`、`set_source_pixmap()`、`clear_source()`、`resizeEvent()`。对外依赖：PySide6 Qt core/gui/widgets，不依赖 PoE2 业务。注意事项：`QSizePolicy.Ignored` 允许父布局分配面积；`clear_source()` 同时清除原图，防止旧帧在下一次 resize 时重新出现。

### `features/poe2/live_terrain/capture_samples.py`（verified）

职责：定义不可变的单帧视觉证据和 PoE2 手动对比样本归档；不调用截图后端、不拥有 QTimer，也不依赖 UI。
关键导出：`CaptureEvidence`、`CaptureSampleRecord`、`CaptureSampleArchive`。
对外依赖：`TerrainSnapshot`、NumPy、OpenCV 和本地文件系统。
注意事项：原图/预处理/特征及可选 wall/fog/raw-gray 数组在 `CaptureEvidence.__post_init__()` 中复制并设为只读；地形可缺失，但三类基础截图不可缺失。可选层让同一证据同时支持人工对比和绘图模式的 distinct match/save/visibility 契约。Windows 上临时样本目录必须用普通 `Path.mkdir()` 创建以继承 samples 根目录 ACL，不能改回会安装 owner-only DACL 的 `tempfile.mkdtemp()`。

`CaptureSampleArchive.save(evidence: CaptureEvidence, *, terrain: TerrainSnapshot | None = None, player_position: PlayerPositionSample | None = None) -> CaptureSampleRecord` 算法：

1. 验证 evidence 类型，确保 samples 根目录存在，再用随机 token 和普通 `Path.mkdir()` 创建隐藏临时目录；最多重试 100 次名称冲突。该方式在 Windows 上继承父目录 ACL，使不同进程身份仍可读取发布后的样本。
2. 分别 PNG 编码必需的 `raw`、`processed`、`feature`，并在 evidence 存在时编码 `wall_mask`、`fog_mask`、`raw_gray`；每层记录宽高、通道、dtype 和编码后字节 SHA-256。
3. 若有 terrain，直接从原始 native snapshot 生成 `terrain.png`；manifest 记录 preview/native 宽高和 `coordinate_space=native`，不写任何用户方向字段。没有 terrain 时写 `status=missing` 和原因。
4. 若有人物样本，先校验其 area instance 与 terrain 一致，再把同一个 native `grid` 写入 `grid` 和兼容读取字段 `terrain_grid`；缺失时明确写 `status=missing`，不借用旧位置。
5. 写 `sample.json`，包含截图时间、保存时间、完整 monitor config、terrain identity、人物位置和图片元数据。
6. 用 `os.replace()` 将完整临时目录原子发布为时间戳/区域命名的最终目录；任一步骤异常会删除临时目录并传播原异常。

### `features/poe2/live_terrain/stitching_session.py`（verified）

职责：PoE2 截图证据到通用 `MapStitcher` 的业务适配层；拥有独立 idle/running/paused 会话、相对轨迹和只读展示快照，不拥有截图或 Qt 控件。
关键导出：`Poe2StitchingSnapshot`、`Poe2StitchingSession`。
对外依赖：`core.mapping.MapStitcher`、`MapFrameEvidence` 和 `CaptureEvidence`。
注意事项：combined feature 保留原始 uint8 灰度权重用于 phase correlation，wall/fog 分别用于落图和可见区域；不能把三层重新折叠为同一二值 mask。默认 profile 画布为 `5000 x 5000`、draw scale 为 `2.0`；reset 使用当前完整参数创建全新 stitcher，绝不复用正式定位或绘图页状态。

`Poe2StitchingSession.configure(stitcher_params: Mapping[str, Any]) -> Poe2StitchingSnapshot` 会先用 `MapStitcher.default_params()` 补齐完整契约；参数相同不清图，idle/paused 下参数变化会重建 stitcher、清空轨迹并回到 idle，running 下参数变化抛 `RuntimeError`，防止不同画布比例和融合门槛混入同一会话。

`Poe2StitchingSession.consume(evidence: CaptureEvidence) -> Poe2StitchingSnapshot` 算法：

1. 非 running 状态直接返回当前只读 snapshot，不增加底层总帧数。
2. 将 feature、wall、fog、raw-gray 和 profile 人物中心组成 `MapFrameEvidence`；缺少 wall 时回退 feature，缺少 fog 时用零层，缺少 raw-gray 时从 processed 转灰度，缺少人物点时回退帧中心。
3. 记录 stitcher 统计前值，调用公开 `MapStitcher.add_evidence()`，再读取统计后值；底层继续负责首帧落图、关键帧/F2F、跳变拒绝、质量门和加权合并。
4. 首帧成功放置，或 successful matches 增加且 low-quality skips 未增加时，把当前画布位置追加到去重轨迹；失败和低质量帧不写轨迹。
5. 从 `get_enhanced_map(margin=80)` 复制只读展示图和 crop origin，并发布位置、轨迹、统计、draw scale、人物局部点及截图尺寸。

失败行为：错误 evidence 类型抛 `TypeError`；空/错误维度层抛 `ValueError`；未解析人物中心抛 `RuntimeError`；异常传播给窗口，窗口会暂停拼图并记录日志。

### `features/poe2/live_terrain/stitching_archive.py`（verified）

职责：只在用户显式点击保存时，原子归档当前拼图、轨迹、统计和关联截图证据。
关键导出：`Poe2StitchingArchive`、`STITCHING_SCHEMA_VERSION`。
对外依赖：`Poe2StitchingSnapshot`、`CaptureEvidence`、OpenCV 和本地文件系统。
注意事项：运行时不持续写盘；最终目录使用普通 `Path.mkdir()` 的隐藏临时目录以继承 Windows 父 ACL。无已接受轨迹时 fail closed，不发布空实验。

`Poe2StitchingArchive.save(snapshot, evidence) -> Path` 算法：

1. 校验 snapshot/evidence 类型、拼图图像和非空轨迹，再创建 archive 根及继承 ACL 的随机隐藏临时目录。
2. 写 `stitched_map.png`、带相对轨迹/当前位置的 overlay、raw/processed/feature/wall/fog 七张基础 PNG；存在当前 terrain 时再按同一 profile 方向写 `terrain.png`，并记录所有图片宽高、通道和 SHA-256。
3. 写 `session.json`，包含版本、时间、terrain instance identity 或明确 missing、map origin、当前位置、轨迹、统计、draw scale、人物局部点、截图尺寸、profile 配置和图片清单。
4. 用 `os.replace()` 原子发布到时间戳/profile 目录；异常时递归删除临时目录并传播原异常。

### `ui/modes/poe2_live_terrain/capture_monitor_window.py`（verified）

职责：独立的人工截图监控、局部地图拼接、历史样本对比和混合定位状态镜像 UI；只通过注入 provider 读取帧/地形，通过采集页传入的 state 镜像定位，不创建定位 session。
关键导出：`Poe2CaptureMonitorWindow`。
对外依赖：`CaptureEvidence`、`CaptureSampleArchive`、`Poe2StitchingSession`、`Poe2StitchingArchive`、`TerrainOrientation`、`render_global_map_pixmap()`、`present_snapshot()` 和 `frame_pixmap()`。
注意事项：`refresh_frame()` 一次只调用一次截图 provider，所有派生图和拼图消费共享该帧；刷新失败立即清除 evidence 和五块当前预览，禁止保存旧帧。证据/拼图、工作区/历史区使用可拖动 `QSplitter`；预览由 `AspectPreviewLabel` 在窗口放大后按原始帧重缩放。关闭窗口停止定时器并暂停拼图，但不自动保存或 reset。

`Poe2CaptureMonitorWindow.refresh_frame() -> None` 算法：

1. 获取最新 monitor config，并调用一次 `preview_provider(config)`。
2. 对同一 raw frame 调用 `preprocess_image()`、`extract_combined()` 和可用的 `get_raw_gray()`，把 distinct feature/wall/fog/raw-gray 组装为不可变 `CaptureEvidence`。
3. 同帧周期读取测试 service 的当前 terrain snapshot，并按同一 config 的方向渲染预览。
4. 全部成功后才替换当前 evidence/terrain 并启用保存；任一异常进入 `_invalidate_current_frame()`，旧帧不可再保存。
5. 若拼图会话为 running，把同一个 evidence 交给 `Poe2StitchingSession.consume()`；成功后渲染拼图、相对轨迹和统计，异常时暂停拼图、写日志并显示错误。

`Poe2CaptureMonitorWindow.save_current_sample() -> CaptureSampleRecord | None` 只保存当前有效 evidence、该次刷新绑定的 terrain 和注入 `player_position_provider` 返回的页面当前人物样本，不会在点击保存时重新截图或重新读取游戏；成功后重新加载历史列表并选中新样本，失败只显示错误，不产生半成品记录。

`Poe2CaptureMonitorWindow.handle_hybrid_state(state, *, read_count: int = 0) -> None` 只格式化 mode/source/confidence/read count/position，并在当前 terrain pixmap 副本上绘制该 state 的 fresh marker 与确认轨迹；它不调用 session、controller 或 memory provider。

### `ui/modes/poe2_live_terrain/capture_test_page.py`（verified）

职责：PoE2 数据采集与混合定位实验页；拥有唯一 hybrid experiment、唯一 hybrid QTimer 和地图 overlay，仍与正式 `Poe2LocalizationRuntime` 隔离。定位定时器使用 `localization_fps` 计算有效周期，并把旧 `sample_interval_ms` 作为兼容上限；预览使用独立 `preview_fps` 周期。双人首帧在一次内存锚点读取下采集最多三张短间隔截图，对每张独立注册后按接受状态、pair confidence、形状质量和锚点误差选最强候选。关键导出：`Poe2CaptureTestPage`。对外依赖：terrain service/archive、preview/recognizer、可选 hybrid factory、`Poe2CaptureMonitorWindow`、`AspectPreviewLabel` 和 presenter。注意事项：没有 terrain 时开始按钮禁用；重新抓图、reset、shutdown 都先停止实验。实验页主区/侧栏、预览/地图以及三个预览格使用可拖动分隔条；窗口大小变化不改变原始截图、地图坐标或路线。

`start_hybrid_localization()` 校验 snapshot/factory，停止旧 session，按当前 snapshot/config 创建 experiment，注册 listener 并启动 timer，然后立即 tick 一帧；构造或首 tick 异常会停 timer、清 experiment 并显示错误。

`handle_hybrid_state(state)` 显示 mode/source/confidence/read count/revision/reason；注册器提供诊断时追加最佳候选的结构分、前向覆盖率、角度、比例、锚点误差和具体拒绝原因，并把完整 diagnostics 写入日志。`position=None` 时明确显示本帧无可信位置，overlay 仅保留已确认轨迹。只有 mode 为 `recovery_required` 时启用 retry 按钮；窗口存在时把同一 state 镜像过去。副作用仅为日志和 Qt 展示。

### `tools/debug/poe2_live_terrain_localization_probe.py`（verified）

职责：只读已保存 PoE2 样本，在正式 runtime 外重放视觉参数、调用实验包的相似变换搜索，并生成诊断图片/报告。纯数组算法由 `experimental/hybrid_localization/similarity_search.py` 拥有；CLI 只保留兼容 re-export 和文件 I/O。它不截图、不连接游戏、不修改 profile，也不产生输入或网络副作用。
关键导出：`ProbeConfig`、`ProbeSample`、`SearchCandidate`、`clean_feature_mask()`、`local_walkable_region()`、`transform_feature()`、`search_candidates()`、`run_probe()`。
对外依赖：`experimental/hybrid_localization/similarity_search.py`、通用 `HSVRecognizer`、OpenCV、NumPy 和只读 samples 目录；结果仅写 `data/poe2_live_terrain_test/probe_results/`。
注意事项：probe 报告的 `accepted` 仅代表同一样本内得分与首二名差距通过实验门槛，不代表已有独立真实坐标验证；实验角度是“局部 feature 到 native terrain”的 OpenCV 逆时针角度，不能直接当作生产 `TerrainOrientation` 配置值。

`clean_feature_mask(feature: np.ndarray, *, player_position: tuple[float, float], player_clear_radius: int = 22, min_component_area: int = 20, min_component_span: int = 24) -> tuple[np.ndarray, list[dict[str, Any]]]` 算法：

1. 将 combined feature 规范成二值层，并清除人物中心半径内的动态像素。
2. 执行 8 邻域连通分量分析，记录每个分量面积、包围盒和是否触边。
3. 只保留面积至少 20 且触边或最大跨度至少 24 的分量；实样本因此移除蓝色光环、橙色标记和鼠标指针而保留被截图边缘裁断的地图墙线。

`local_walkable_region(feature: np.ndarray, player_position: tuple[float, float]) -> np.ndarray` 将墙线膨胀为 barrier，并把截图四边闭合；在剩余自由空间做连通分量标记，只返回人物种子所在分量。人物种子落在 barrier 时返回全零层，不借用历史位置。

`search_candidates(feature: np.ndarray, terrain_edge: np.ndarray, *, player_position: tuple[float, float], terrain_walkable: np.ndarray | None = None, config: ProbeConfig | None = None) -> list[SearchCandidate]` 算法：

1. 在 `0..315°/45°`、水平镜像和 `0.35..2.45` 比例组合上，把局部 feature 变换到 0.25 倍 terrain 粗网格。
2. 对 terrain edge 距离变换使用 `TM_CCORR` 计算单向 Chamfer 平均距离；若 `ProbeConfig` 提供人物位置 hint/radius，会先在每个变换的粗距离图中屏蔽锚点范围外的 top-left，再提取局部极小值和截断种子，避免重复结构先占满 Top-K。
3. 在原生 terrain 分辨率对每个种子搜索角度 `-4/0/+4°`、比例 `-0.04/0/+0.04` 和附近 48 像素平移；同一 hint/radius 会再次约束细搜距离图。小于 120 个有效边缘像素的模板直接拒绝，避免小模板虚高。
4. 候选分数融合前向边缘覆盖、平均距离指数分、反向边缘覆盖和局部/全局可行走面覆盖；人物点不在可行走区时乘以 0.35 惩罚。
5. 按人物全局位置至少 42 像素去重，返回最多 10 个候选。上层报告要求首选分数至少 0.72、首二名差至少 0.05，否则 fail closed。

`run_probe(sample_directory: str | Path, output_directory: str | Path, *, config: ProbeConfig | None = None, parameter_overrides: Mapping[str, Any] | None = None) -> dict[str, Any]` 读取 manifest/raw/feature/terrain，以 manifest 的 recognizer 参数重建 feature，运行上述清理和搜索，并写 raw/processed/stored/rebuilt/cleaned/local-walkable/terrain layers、Top-K overlay、全图候选图和 `report.json`。任一输入缺失或非法会传播 `OSError`、`JSONDecodeError` 或 `ValueError`，没有静默回退到其他样本；只有 CLI 在未指定样本时会跳过不可读目录选择最新可读样本。

### `tools/debug/poe2_anchor_local_registration_probe.py`（verified）

职责：在正式 runtime 外使用同步保存的人物 native-grid 坐标约束首帧注册，只搜索锚点附近 terrain 小块；组合现有 Chamfer 搜索器恢复旋转、水平镜像、比例和平移，并输出 `anchored_candidate/ambiguous/rejected` 诊断。该文件不连接游戏、不读取实时进程、不修改 profile，也不产生输入或网络副作用。

关键导出：`AnchorLocalProbeInput`、`AnchorLocalProbeConfig`、`AnchoredCandidate`、`AnchorLocalProbeResult`、`load_anchor_probe_input()`、`crop_terrain_around_anchor()`、`prepare_local_feature()`、`match_anchor_local()`、`save_probe_diagnostics()`。

对外依赖：`features/poe2/live_terrain/experimental/hybrid_localization/absolute_registrar.py` 的兼容 DTO/纯匹配函数，以及 localization probe 保留的诊断叠图；OpenCV、NumPy、只读 samples 目录和显式 probe-results 输出目录。算法所有权已从 CLI 移入 feature 实验包，`src` 不反向导入 `tools.debug`。

注意事项：`219°` 等角度是局部 feature 到 native terrain 的 OpenCV 变换角度，水平镜像是同一相似变换的一部分，不能直接写入正式 `TerrainOrientation`。单帧最高状态只能是 `anchored_candidate`，不能宣称跨帧 confirmed。当前 PoE2 实验以 200px 为基准清除顶部 40 行，并按真实 capture size 等比调整；该动态文字/传送点规则尚未推广为通用视觉规则。

`load_anchor_probe_input(sample_directory: str | Path) -> AnchorLocalProbeInput` 算法：

1. 读取唯一指定目录的 `sample.json`，要求 terrain 和 player_position 均为 `available`。
2. 比较 `terrain.instance_id` 与 `player_position.area_instance`，不一致立即抛 `ValueError`，不借用根目录 `latest.npz` 或其他样本。
3. 优先读取 native `player_position.grid`；schema 3 样本中的兼容 `terrain_grid` 也必须与 native grid 同形，绝不从用户方向字段重建坐标。锚点必须有限且位于 terrain 图内，新契约下 manifest native 尺寸必须与图片一致。
4. 优先读取 `wall_mask.png`，缺失时才回退同目录 `feature.png`；从 monitor binding 读取人物局部 marker，缺失时只在实验输入层回退到截图几何中心。非有限或越界 marker 立即拒绝。

失败行为：manifest 或图片缺失分别传播 `OSError`/`JSONDecodeError`/`ValueError`；不扫描其他目录重试。

`crop_terrain_around_anchor(terrain: np.ndarray, anchor: tuple[float, float], radius: int) -> tuple[np.ndarray, tuple[int, int, int, int]]` 把有限锚点四舍五入为 terrain 像素中心，在四边夹紧半径范围并返回独立数组及 `(x0,y0,x1,y1)`；非法图像、半径、非有限锚点或完全越界抛 `ValueError`。

`prepare_local_feature(feature: np.ndarray, local_player: tuple[float, float], *, top_exclusion_rows: int, player_clear_radius: int) -> np.ndarray` 先复制并二值化视觉层，再清零可配置顶部文字带和人物中心圆；不修改归档原数组。当前该函数处理文字与人物 marker，传送点等和墙体相连的结构仍由匹配覆盖率与锚点先验共同容错。

`match_anchor_local(probe_input: AnchorLocalProbeInput, config: AnchorLocalProbeConfig | None = None) -> AnchorLocalProbeResult` 算法：

1. 调用 `prepare_local_feature()` 得到稳定实验层，以 `anchor_grid` 和 `crop_radius` 裁剪粗搜 terrain。
2. 在默认八个方向 basin、镜像开关和 `0.35..2.45` 比例组合上调用既有 `search_candidates()`；人物锚点 hint/radius 在粗距离图生成候选前就生效，再把人物点加回 crop 原点做精确误差校验和先验评分。
3. 对剩余候选计算 `anchored_score = chamfer_score*(1-anchor_weight) + (1-error/max_error)*anchor_weight`，按锚点加权分数和原始结构分数排序。
4. 从与最佳锚点分差不超过 `refine_seed_margin=0.10` 的粗候选中选择最多 4 个角度/镜像 basin，并在每个 basin 内跳过比例距离不超过 `refine_scale_radius` 的冗余种子、保留相互分离的比例峰；以轮询方式选择最多 8 个细化种子，分别在角度 `±12°`、比例 `±0.16`、固定镜像和更小 terrain 上细搜，再合并 basin 候选。这样同一位置的不同方向不会被空间去重吞掉，同一方向的错误比例峰也不会阻止正确比例进入细搜。
5. 原始结构分数、前向覆盖率和合并后首二名锚点加权分差依次通过门槛时发布 `anchored_candidate`；顶部动态残留被排除后仍保留通用 score/coverage 门槛，不通过时发布 `ambiguous` 或 `rejected`，不以人物坐标错误伪造位置。

副作用：纯计算，不写文件。调用关系：called by `main()` 和离线测试；calls `prepare_local_feature()`、`crop_terrain_around_anchor()`、`search_candidates()`、`_anchored_candidates()`、`_result_status()`。

`_probe_config(...) -> ProbeConfig` 把粗搜或细搜的角度/镜像/比例、人物 hint/radius、空间分离和结果上限映射为既有搜索器配置；粗搜用零空间分离保留同位置不同变换，细搜在单一 basin 内用 12 像素分离去除同解邻近参数。非正比例被过滤，空集合由 `ProbeConfig` 抛 `ValueError`。

`_anchored_candidates(...) -> tuple[AnchoredCandidate, ...]` 将 crop 局部人物位置换回完整 terrain 坐标，按欧氏距离执行锚点硬边界，再融合结构分与线性距离先验；函数不改变底层 `SearchCandidate`。

`_float_range(center: float, radius: float, step: float) -> tuple[float, ...]` 生成包含两端附近值的细搜序列；radius 非正时只返回中心。step 由 `AnchorLocalProbeConfig.__post_init__()` 保证为正。

`_result_status(candidates, config) -> tuple[str, str]` 依次验证候选存在、原始结构分、前向覆盖率和首二名 anchored margin；原因字符串直接进入报告，拒绝时不返回伪确认坐标。

`save_probe_diagnostics(probe_input, result, output_directory, *, config) -> Path` 算法：

1. 拒绝覆盖已有输出目录，在同父目录创建随机隐藏临时目录。
2. 写 `local_terrain.png`、`prepared_feature.png`；存在最佳候选时再调用既有叠图器写 `best_overlay.png`。
3. 写包含样本路径、状态、原因、锚点、crop bounds、完整配置、最佳候选和全候选数值的 `report.json`。
4. 用 `os.replace()` 原子发布；任一异常删除临时目录并传播。

`build_argument_parser()` 暴露显式 sample/output、粗/细裁剪半径、顶部排除行数和锚点最大误差；`main(argv)` 只组合加载、匹配和保存，`anchored_candidate/ambiguous` 返回 0，`rejected` 返回 2。

### `features/poe2/live_terrain/hybrid_product_runtime.py`（verified）

职责：正式 PoE2 页面与实验 hybrid 定位域之间的无 Qt 适配层；拥有当前 snapshot/config/experiment 生命周期，但不拥有 timer 或匹配算法。关键导出：`Poe2HybridProductRuntime`、`Poe2HybridProductState`。对外依赖：注入的 experiment factory、session 最近视觉证据和 terrain logger。注意事项：`configure_snapshot()` 会先停止旧 session 再创建新 experiment；未配置地图时 `start/tick/retry_recovery` 抛 `RuntimeError`。正常运行不自行轮询内存，读取时机完全由 controller 的 recovery revision 决定。

`configure_snapshot(snapshot) -> None` 校验非空快照，停止旧 experiment，调用 factory 传入 snapshot 和读取当前 `_config` 的 provider；副作用仅为替换内存对象并写结构化日志。`configure_monitor(config) -> None` 原子替换下个 tick 使用的配置，不重建算法对象。

`tick(*, now_ms: int | None = None) -> Poe2HybridProductState` 计时并委托同一 session tick；把 `HybridLocalizationState` 与 session 的 `last_raw_frame/last_evidence/last_frame` 合并为页面状态，附加 processed frame、wall mask、local player、frame elapsed 和 anchor provider `read_count`。它不修改 mode，不吞异常，不用 `latest_confirmed_position` 伪造本帧 position。

`start()/stop()/retry_recovery()` 只委托当前 session 并记录日志。显式 retry 只调用 controller 的单次恢复入口，不创建后台循环。

### `features/poe2/live_terrain/experimental/__init__.py`（verified）

职责：标记尚未进入正式 runtime 的 PoE2 实验边界。关键导出：无。对外依赖：无。注意事项：实验成功不等于生产承诺，稳定前不得从正式 `core` 反向依赖此包。

### `experimental/hybrid_localization/__init__.py`（verified）

职责：聚合混合定位实验的模型、协议、controller、适配器、session 和 composition。关键导出：`HybridLocalizationController`、`Poe2HybridLocalizationSession`、`Poe2HybridLocalizationExperiment` 及各 DTO/协议。对外依赖：同包模块。注意事项：只提供组合入口，不拥有状态或副作用。

### `experimental/hybrid_localization/models.py`（verified）

职责：定义不可变运行契约。关键导出：`HybridLocalizationMode`、`PositionAnchor`、`SimilarityTransform2D`、`HybridFrame`、`AbsoluteRegistration`、`HybridLocalizationState`。对外依赖：`LocalizationResult`、NumPy。注意事项：帧 mask 被复制并关闭写入；所有坐标/置信度/误差校验有限值；`position` 是本帧新结果，`latest_confirmed_position` 只供诊断，失败时两者不得混用。

`HybridFrame.from_evidence(evidence, *, captured_at_ms: int, frame_id: int | None = None) -> HybridFrame` 先选择 wall mask、缺失时回退同帧 feature，再从 frozen monitor config 读取人物 marker，缺失时才用帧中心；同时保留真实 `capture_size` 诊断，使 PoE2 绝对注册可以按当前截图尺寸同比例调整 terrain 窗口；输出独立只读 mask 和 evidence 时间诊断，非法或空图抛 `ValueError`。

### `experimental/hybrid_localization/contracts.py`（verified）

职责：以 `runtime_checkable Protocol` 定义 `AnchorProvider.read_once()`、带 `last_diagnostics` 的 `AbsoluteRegistrar.register()` 和 `LocalTracker.track()`。关键导出：三个协议。对外依赖：上述 models 和 `TerrainReference`。注意事项：协议只描述能力，不包含 PoE2 内存地址、Qt 或输入设备；绝对注册返回 `None` 时仍可通过只读语义的 diagnostics 解释拒绝原因。

### `experimental/hybrid_localization/recovery.py`（verified）

职责：按 revision 授权一次昂贵恢复。关键导出：`OneShotRecoveryPolicy`。对外依赖：无。注意事项：`begin()` 单调增加 revision；`consume(revision)` 仅在 revision 等于当前且从未消费时返回 true，旧版/重复消费均返回 false。

### `experimental/hybrid_localization/controller.py`（verified）

职责：拥有混合定位状态、前帧、最后确认注册、待配对锚点和有界轨迹；通过协议组合锚点、绝对注册和局部跟踪。关键导出：`HybridLocalizationController`。对外依赖：models/contracts/recovery 和通用 `TrajectoryBuffer`。注意事项：控制器只通过 provider 读取锚点，不实现进程读取或匹配；失败帧的 fresh position 为 `None`。

`HybridLocalizationController.update(frame: HybridFrame) -> HybridLocalizationState` 算法：

1. `STOPPED/RECOVERY_REQUIRED` 只发布状态；`NEED_ABSOLUTE/RECOVERY_PENDING` 进入 `_attempt_absolute()`；其余进入 `_track_local()`。
2. session 在截图前调用 `prepare_capture()`；绝对模式下它消费当前 revision、调用 provider 一次，并以 `(revision, PositionAnchor)` 缓存待配对锚点。读取失败立即进入 `RECOVERY_REQUIRED`；已准备的同 revision 锚点不会重复读取。
3. `_attempt_absolute()` 取出并清空待配对锚点，再用同一 registrar 和可选 prior 注册刚截取的帧；注册异常、缺锚点或实例不一致转为 `RECOVERY_REQUIRED`。注册器返回 `None` 时复制其 `last_diagnostics` 到失败 state，不把结构分不足、覆盖不足和候选歧义压扁成空状态。
4. 局部分支要求前帧与 prior，调用有界 tracker；失败时创建一个新 revision、进入 `RECOVERY_PENDING`，本帧不更新前帧、last confirmed 或轨迹。
5. `_accept()` 只接受有位置且同实例结果，更新前帧/prior，并用 fresh=true 追加轨迹；stop/reset/retry 会清除任何待配对锚点，`retry_recovery()` 只允许从 `RECOVERY_REQUIRED` 开启新 revision。

副作用：仅修改 controller 内存状态；不截图、不读进程、不写文件。失败行为：错误 frame 类型抛 `TypeError`；provider/registrar/tracker 运行错误被转换为带 error type 的失败状态，避免 timer 崩溃。

### `experimental/hybrid_localization/similarity_search.py`（verified）

职责：无文件系统副作用的二维相似变换 Chamfer 搜索；从旧 localization CLI 原样迁移数值逻辑。关键导出：`SimilaritySearchConfig`、`SearchCandidate`、`transform_feature()`、`terrain_edges()`、`terrain_walkable_mask()`、`local_walkable_region()`、`clean_feature_mask()`、`search_candidates()`。对外依赖：OpenCV、NumPy。注意事项：日志只记录搜索统计；不读样本、不写诊断文件。

`search_candidates(...) -> list[SearchCandidate]` 先对每个角度/镜像/比例在降采样 distance field 上产生局部极小值，人物 hint 在 Top-K 前屏蔽范围外候选；若提供 terrain walkable，则在全局 Top-K 截断前按变换后人物点附近是否可行走排序，同一容量内优先保留可行走候选但不硬删除其余候选。之后在原分辨率细化角度/比例/平移，按 `score_weights=(forward, distance, reverse, walkable)` 融合前向/反向 Chamfer、可行走覆盖和人物落点，最后按人物位置分离并截断。通用默认仍是 `(0.42, 0.18, 0.12, 0.28)`；内存锚点 PoE2 组合显式使用形状优先的 `(0.55, 0.25, 0.15, 0.05)`。权重必须为四个非负数且总和为 1；非法尺寸、空特征、非正比例、不配对 hint/radius 或负 walkable 邻域半径抛 `ValueError`。

### `experimental/hybrid_localization/absolute_registrar.py`（verified）

职责：把 memory anchor、局部墙体帧和 `TerrainReference` 组合为 typed absolute registration。关键导出：`AnchoredRegistrationConfig`、`AnchoredAbsoluteRegistrar`、`reference_boundary_layer()`、兼容 probe DTO/函数。对外依赖：models、similarity search、`TerrainReference`、`LocalizationResult`、`core.localization.canonical_wall`。注意事项：视觉匹配使用 canonical 可行走区薄边界，不把整块不可通行区当作墙线；reference/anchor/prior 实例不一致直接返回 `None`。

`AnchoredAbsoluteRegistrar.register(frame, *, reference, anchor, prior=None) -> AbsoluteRegistration | None` 算法：

1. 校验 reference/anchor/prior 实例；`reference_boundary_layer()` 对 known walkable 做 3x3 膨胀/腐蚀并取差，得到两侧薄边界；terrain 将 walkable 编为 60、边界编为 235、其他区域编为 0，避免大面积 blocked 区产生零距离平原。
2. 以 200px 小地图样本标定的 `crop_radius=150/refine_crop_radius=110/top_exclusion_rows=40` 为默认窗口；真实 evidence 带有截图尺寸时，按 wall mask 的实际最大边同比例缩放三个值（例如 320px -> 240/176/64），使搜索范围和顶部动态文字排除范围都与截图覆盖相称；人物 marker 清理半径保持物理像素语义。`prepare_local_feature()` 完成顶部/人物清理后调用 `clean_feature_mask()` 删除孤立紧凑组件，避免扩大截图后把游戏画面纹理和小图标当成墙体。离线/手工 frame 未提供 capture-size 诊断时保留调用方显式值。
3. 无 prior 时使用完整实验角度/镜像/比例空间；有 prior 时先用上一方向/镜像/比例做 translation-only 搜索，失败时在同一次内存锚点下回退完整角度/镜像/比例搜索，避免错误 prior 让恢复永远失败。
4. 调用同一 `match_anchor_local_arrays()` 完成锚点裁剪、粗搜、多 basin/多比例峰细化；比例不是 profile 常量，粗搜覆盖 `0.35..2.45`，精搜在峰值周围以 `0.02` 连续细化，成功后由 registration 作为本 session 的比例事实源。精搜阶段不再按人物位置提前压掉相邻角度/比例候选，而是保留它们到 memory-anchor 联合评分之后；`AnchoredCandidate.basin_scale` 与 coarse angle/reflection 标识独立搜索 basin，歧义 margin 只比较不同 basin，不把同一 basin 的 2° 邻近细化结果误判为竞争方向。随后由 `_prioritize_memory_anchor()` 在 score/coverage/walkable 门内优先选择距内存锚点最近的候选；当前 PoE2 单帧组合显式使用 `anchor_weight=0.65`、`minimum_confidence=0.75`、`minimum_score_when_anchored=0.35` 和 `anchor_disambiguation_gap=1.0`，低于 `0.75` 直接拒绝。普通候选保持 `0.65` forward coverage；人物距内存锚点不超过 `8px` 且落在 walkable terrain 时，允许最低 `0.50` 的窄幅 coverage 容差和显式锚定 score gate；没有显式锚定配置时仍使用通用 `minimum_score=0.50`。无论接受或拒绝，都更新 `last_diagnostics`，包括 status/reason、搜索模式、尝试次数、组合数、候选数、capture size、实际 crop/refine 半径、`top_exclusion_rows/player_clear_radius`、confidence/score/coverage 阈值、锚点半径/消歧间隔及最佳候选的分数、覆盖率、角度、镜像、比例、锚点误差、人物可行走性和最终 `confidence`；非 `anchored_candidate` 返回 `None`。
5. 将 crop-relative top-left 恢复为 reference 全局平移，生成 `SimilarityTransform2D` 和 `LocalizationResult(source="anchored_absolute")`，成功 registration 携带与 `last_diagnostics` 相同的可审计诊断。

`AnchoredAbsoluteRegistrar._config_for_frame(frame, config) -> AnchoredRegistrationConfig` 只对真实采集帧生效：检测 `HybridFrame.diagnostics["capture_size"]` 是否存在，读取 wall mask 的实际最大边长，以 `capture_reference_size` 计算比例并同步缩放粗搜半径、精搜半径和顶部排除行数；没有该诊断时原样返回传入 config。无文件或内存副作用，非法 frame 尺寸由上层 `HybridFrame` 契约拦截。

### `experimental/hybrid_localization/memory_anchor.py`（verified）

职责：把一次 PoE2 人物内存样本适配为当前 reference 坐标锚点。关键导出：`Poe2MemoryAnchorProvider`、`parse_timestamp_ms()`。对外依赖：`Poe2PlayerPositionSource`、`TerrainOrientation`。注意事项：`read_count` 统计尝试次数，包括失败；每次读取仍由 source 重新解析地址并校验实例。

`read_once(expected_instance_id: str) -> PositionAnchor` 先增加诊断计数，再调用 source；将 native grid 通过固定 session orientation/native shape 变换，解析 ISO 时间，缺时间才使用注入 clock。`PlayerPositionError` 和解析错误原样传播，由 controller 转成单次失败状态。

### `experimental/hybrid_localization/local_tracker.py`（verified）

职责：固定已确认角度/镜像/比例，按导航模式优先执行帧间位移预测，并按帧数、预测距离或时间周期调用有界形状 matcher 做漂移校正。关键导出：`VisualLocalTracker`。对外依赖：`core.localization.canonical_wall`、`core.localization.frame_displacement`、`core.localization.displacement`、models、`transform_feature()`、注入 matcher。注意事项：没有全图 matcher；静止帧不会因校正时间门单独触发 matcher；PoE2 composition 给 matcher 注入同一 reference canonical boundary 及实机标定容差，不修改通用 `LocalMapMatcher` 默认值。

`track(frame, *, reference, previous_frame, previous) -> AbsoluteRegistration | None` 先归一化前后 wall mask，再估计 phase 位移并通过 prior 相似变换得到 global delta；当 phase 通过且校正门未到期时，以 `previous_position - global_delta` 发布 `source="visual_f2f"`。当帧数/时间/累计 native 距离达到门限且当前有实际运动时，在 prior translation 附近调用 bounded matcher；成功发布 `source="visual_local"` 并替换累计位置，失败记录 `correction_accepted=false` 后保留本帧短期预测。位移本身被拒绝且 bounded matcher 失败时返回 `None` 交给 controller 恢复。metadata 同时保存 `correction_due`、`correction_distance`、`correction_attempted`、`correction_accepted` 和最近校正锚点。副作用仅为返回 registration/diagnostics，不读内存、不写文件。

### `experimental/hybrid_localization/session.py`（verified）

职责：无 Qt 的 tick/lifecycle/listener 编排，并保证绝对锚点与截图的采样顺序。关键导出：`Poe2HybridLocalizationSession`。对外依赖：`HybridFrame` 和注入 frame source/evidence builder/controller。注意事项：inactive tick 抛 `RuntimeError`，停止后不读锚点、不截图。

`tick(*, now_ms=None) -> HybridLocalizationState` 先调用 controller `prepare_capture()`；首次/恢复模式由此完成一次内存锚点读取，失败状态直接发布且不截图。准备成功后才调用一次 config provider、一次 capture 和一次 evidence build，并在 capture 后记录帧时间；随后递增 frame id，从同帧 evidence 构造 `HybridFrame`，保存 `last_raw_frame/last_evidence/last_frame` 供上层展示，调用 controller 以待配对锚点注册并同步通知 listener。`reset()` 同时清除三个最近视觉值。正常 `LOCAL_TRACKING` 帧的 prepare 是空操作，不读内存。它不拥有线程、QTimer 或磁盘 I/O。

### `experimental/hybrid_localization/composition.py`（verified）

职责：PoE2 适配和实验对象装配。关键导出：`Poe2HybridLocalizationExperiment`、`build_poe2_hybrid_localization_experiment()`。对外依赖：snapshot/reference/orientation、CaptureEvidence、`MapRuntime`、`LocalMapMatcher` 及同包组件。注意事项：factory 自行把当前 profile 的非空 `recognizer_params` 应用到独立识别器；不依赖页面先行配置，也不导入 UI/PySide6、gamepad、Host 或 LAN。

factory 固定当前 profile 方向，构建定向 reference；用 native snapshot shape 配置 memory provider；显式注入 PoE2 首帧实测配置（局部窗口 `150/110`、动态顶部排除 `40`、人物清理 `22`、anchor 权重 `0.65`、最低 confidence `0.80`、消歧间隔 `1.0`、视觉分/覆盖门 `0.50/0.65/0.60`），角度按 45° 粗搜后细化、比例在 `0.35..2.45` 自动搜索；从 `reference_boundary_layer()` 的薄边界缓存 `MapRuntime.distance_field`，并以 PoE2 实测容差装配 tracker；随后装配 controller/session。内部 evidence builder 在同一 raw frame 上生成 processed/feature/wall/fog/raw-gray 和 frozen config。

`src/auto_modules/features/poe2/live_terrain/` 承载正式 PoE2 业务组合：terrain reference、calibration、`orientation.py`、single-player policy、localization runtime、monitor config 和 local profile store。`orientation.py` 只负责把 native 数组、地图点和局部位移变换到 profile 选定的小地图方向，不下沉 PoE2 术语到通用定位引擎。`tools/experiments/poe2_live_terrain/` 不承载生产实现；feature 只组合 `auto_modules.core` 与 PoE2 adapter，不复制通用定位状态机，也不产生输入或网络副作用。

### Torchlight 业务域（verified）

`src/auto_modules/features/torchlight/` 是火炬之光专用业务边界：

- `portal/`：Torchlight 传送门模型、目标证据、交互处理器和完成判定。
- `loot/`：Torchlight 掉落检测、目标投影、拾取移动和完成判定。
- `follow/`：自动跟随配置、角色规划、双会话、工作进程、回放和基准诊断。
- `skills/`：技能/事件链业务 facade；执行算法由通用 `core.events.automation` 提供。
- `composition.py`：注册 Portal/Loot 事件定义的唯一业务组合入口。

`src/auto_modules/ui/modes/torchlight/follow/` 是对应的 Torchlight UI；通用事件
工作台只通过该 UI 的编辑器入口组合，不直接从 `core.events.types.*` 注册业务。

采集边界的每个阶段使用 `logging_utils.py` 写入 `data/logs/poe2_live_terrain.log`，包括按钮动作、producer 命令、manifest 校验、native grid 转换、内存替换、测试归档、渲染和异常。

### PoE2 单人定位与独立监控（verified）

`src/auto_modules/core/spatial/capture_geometry.py` 只定义游戏无关的 `CaptureShape`、
`CaptureGeometry` 和 `build_capture_mask()`。截图始终是矩形数组；`SQUARE` 返回全 true
矩形遮罩，`CIRCLE` 按外接矩形中心和半径返回 bool 遮罩，圆外区域由上层识别器忽略。该
新增底层能力没有修改绘图模式调用方。

### `src/auto_modules/core/spatial/__init__.py`
职责：空间能力的稳定公开入口。关键导出：坐标映射/标定 DTO、`CaptureRect`、`MonitorBinding`、`resize_binding_around_marker()`。对外依赖：同包 `calibration`、`models`、`desktop_mapping`、`monitor_binding`。注意事项：使用 `__all__.extend()` 合并 monitor binding 导出，不能再次赋值覆盖既有坐标 API。

`src/auto_modules/core/spatial/monitor_binding.py` 定义通用的不可变 `CaptureRect`、
`MonitorBinding` 和 `resize_binding_around_marker()`。重设函数先把旧 marker 转为物理桌面锚点，
再围绕同一锚点构造指定宽高的新矩形和居中 marker，同时保留 screen、coordinate-space 和 DPI；
它不认识 PoE2、导航或窗口配置。`core.spatial` 从公开入口导出该能力且不再覆盖既有坐标导出。

`src/auto_modules/features/poe2/live_terrain/monitor_config.py` 定义 `Poe2MonitorConfig`、
兼容的 `Poe2MonitorConfigStore` 和 `Poe2MonitorProfileStore`。profile 额外保存 `profile_id`、
`profile_name`、`selection_mode`、`capture_size`、`shape`、`circle_radius`、完整
`recognizer_params` 和完整 `stitcher_params`。旧 JSON 中的 `map_rotation`、`map_flip_horizontal`、
`map_flip_vertical` 只被忽略，不进入对象或重新保存结果。识别参数按
`HSVRecognizer.get_params()` 契约深复制；拼接参数按无画布分配的 `MapStitcher.default_params()`
契约补齐并深复制。旧 profile 缺 `stitcher_params` 时兼容为 `5000 x 5000`、draw scale `2.0`
及通用融合默认值；识别参数缺字段时由 PoE2 dedicated recognizer 补齐。配置不保存
地形快照、人物位置或运行开关。profile store 使用本地 `profiles.json` 和独立 profile JSON，
原子写入、支持新建/复制/重命名/激活/删除，并在首次读取时兼容旧 `monitor.json`。`Poe2MonitorConfig.__post_init__()` 保证 center 模式的 `capture_size`、binding 矩形和居中 marker 一致；旧 profile 即使保存为 `capture_size=300` 但 binding 仍为 200x200，加载后也会围绕原物理人物点规范为 300x300，region 画框不受影响。`save()`
写临时 JSON、flush/fsync 后 `os.replace()`，非法 JSON fail closed 到默认值。
`monitor_source.py::MonitorFrameSource.capture(binding, shape, radius)` 先按 binding 的矩形
调用注入截图后端；当 shape 为 `circle` 时，对 2D/3D 帧应用矩形布尔遮罩，把圆外像素置零，
再交给 PoE2 识别器。它不读取 `AppContext` 或 `NavConfig`。

`features/poe2/live_terrain/terrain_reference.py::build_reference(snapshot)` 的
算法是：

1. 计算 `known = snapshot.known_mask > 0`；
2. 计算 `walkable_mask = (cell_state == 1) & known`；
3. 生成通用 matcher 墙层（可行走为 0、阻挡/未知为 255）和已知层（已知为 255、未知为 0）；
4. 复制并冻结数组，保留原始 `height x width` 及区域 metadata。

`orientation.py::TerrainOrientation` 在业务适配边界统一变换 reference 的三层数组、
展示 pixmap 的可行走层、全局点坐标和局部位移；顺时针 90°/270° 旋转会交换宽高，
水平/垂直翻转发生在旋转之后。`Poe2MonitorConfig` 只保存该契约的 profile 参数，
缺省保持原始方向。

### 通信层重构（verified）

通信层现在按“设备信任 -> 物理 session -> capability lease -> topic subscription”分层。
`src/auto_modules/core/communication/contracts.py` 定义 `PeerId`、`SessionId`、
`Capability`、`Topic`、`DeliveryMode`，不依赖 Host 或 LAN；`messages.py::MessageEnvelope`
校验 TTL、deadline、sequence 和 versioned-resource 的 manifest/chunk 字段，并提供
`from_shared_position` / `from_shared_event` 构造器；`shared_state.py` 定义位置/事件记录，`qos.py`
把实时 latest、可靠有序和版本资源策略命名化。

`src/auto_modules/application/communication/trust_store.py::FileTrustStore` 使用
`data_root()/communication` 下的 `trusted_peers.json`、`revocations.json` 和
`capability_preferences.json`。`save()` 对证书指纹变化默认 fail closed，所有 JSON 写入
使用临时文件、flush/fsync 和 `os.replace`；`revoke()`、`forget()` 和
`clear_recovery()` 不会把 session key 写入磁盘。

`application/communication/manager.py::CommunicationManager.acquire(peer, capability)`
通过 `PeerSession` registry 保证一个 peer 只有一个 transport connection。lease 的引用计数
使一个业务释放时不影响其他业务；`MessageDispatcher.dispatch()` 对同一 envelope fan-out
给多个 topic subscriber，不再让业务直接 drain Host 队列；`ReconnectController` 用递增
generation 拦截旧 reconnect/message，并提供 1/2/5/15/30 秒退避。

`src/auto_modules/adapters/host/communication_adapter.py::HostCommunicationAdapter` 只持有
一个 `VirtualGamepadClient`，通过 `HostPeerTransport` 将 generic envelope 转成旧的
`sync.share.position/event/catalog` 命令。`CommunicationManager.pump()` 调用适配器一次
`sync.share.drain`，把事件、位置、目录同时放入本地 topic 队列并通知 dispatcher；失效
peer 的消息被隔离，业务订阅回调异常不再由适配器静默吞掉。旧的
`HostEventBridge` 和 `FollowTransport` 在未注入 manager 时保留兼容 client 路径；注入 manager
后只申请能力 lease，不创建或关闭独立 LAN session。

关键数据流：

```text
EventWorkbenchService.tick_once()
  -> CommunicationManager.pump()
  -> HostCommunicationAdapter.pump(manager)
  -> VirtualGamepadClient.request("sync.share.drain")
  -> MessageDispatcher.dispatch(peer, MessageEnvelope)
  -> HostEventBridge.drain_events()/drain_catalogs()
  -> EventExecutionRuntime.start/tick
```

```text
FollowService._network_shared()
  -> manager.acquire(position.subscribe/event.subscribe[/position.publish])
  -> FollowTransport.poll()/publish()
  -> manager.pump()/CapabilityLease.publish(MessageEnvelope)
  -> HostPeerConnection.send()
  -> HostCommunicationAdapter.send_message()
  -> sync.share.*
```

`services/lan_input_sync/src/LanInputSync/SessionCapabilities.cs` 将旧 `DataOnly` 映射为
`input.*`、`position.*`、`event.*`、`catalog.*` 和预留的 `map.*` flags；旧 `start`/
`start-data` 命令仍可用，status 额外返回 `capabilities`。会话内 `capability-update`
携带 `controllers`，接收端校验授权/独占并回 `capability-ack` 的新 grants；拒绝输入升级
返回 `capability-reject`，原数据会话继续运行。当前运行时的权威持久层是 `IdentityStore`
管理的 `trusted.json` 和 `preferences.json`；独立 `PeerTrustStore` 尚未接入 `LanSyncService`。
`ReconnectBackoff` 提供有界退避。正常进程退出保留 mode、接收许可及恢复偏好；普通断线
立刻中立化输入，已信任 peer 重连时才恢复保存的许可；UI 关闭使用 `sync.suspend`
中立化当前会话并仅栅栏当前进程的重连，保留下次启动的恢复偏好；手动 stop/reset/forget/emergency
清除恢复资格。

风险登记：

- P1 `HostCommunicationAdapter.pump()`：旧 Host drain 响应仍依赖 JSON 兼容字段；Host 协议
  字段变化会让位置/事件只进入诊断队列而不触发业务。建议协议 v2 增加显式 envelope 版本和
  contract test。
- P1 `LanSyncService.ReceivePacket()`：兼容期在同一 lane 用 JSON `{` 前缀区分位置和旧
  输入二进制，若未来输入编码允许 `{` 开头会误判。建议后续协议版本分配独立 data lane。
- P2 `FileTrustStore._read_mapping()`：JSON 损坏会 fail closed 并阻断启动；部署层应提供
  诊断提示和人工恢复入口，不能自动删除信任文件。
- P2 `LanSyncService.RunControlsAsync()`：旧版 peer 不理解会话内 capability-update，升级前
  应确认两端协议版本；当前仅首轮 `start/start-data` 保留旧兼容，不能跨版本热增能力。

`calibration.py::Poe2Calibration.local_to_reference(local_position)` 对局部点做有限值校验，
按显式 scale、axis_direction、offset 和可选 Y 翻转映射到参考坐标；禁止零比例、非法轴向、
越界人物 marker。`player_policy.py::select_single_player(frame, min_confidence)` 只在
阈值候选数恰好为 1 时返回候选，多候选/空候选返回 `None`；`select_single_player_frame()`
把选择结果写回通用 `ObservationFrame.selected_index`。

`runtime.py::Poe2LocalizationRuntime.tick()` 是当前 PoE2 业务组合入口。它先按
`selection_mode` 分流：`center` 直接使用 `MonitorBinding.player_marker_position`（没有 marker
时才使用截图中心），`region` 才调用人物图像识别；区域/多人模式默认识别门槛为
`min_confidence=0.60`：

1. `_capture_frame()` 调用注入的 callable 或 `capture/read/get_frame`；
2. `_recognize_or_use_center()` 在 `center` 模式生成 `source="configured-center"` 的单一候选，
   不调用 HSV/轮廓识别；在 `region` 模式调用 `_recognize()`，再规范化为 `ObservationFrame`；
3. 单人策略筛选唯一人物，失败返回 `LocalizationResult(source="failed", reason="player_not_detected")`；
4. `_build_visual_evidence()` 调用 dedicated recognizer 的 `preprocess_image()` 和
   `extract_combined(frame, player_pos)`，形成预处理画面、match/wall/fog mask；
5. 把携带 `Poe2VisualEvidence` 的 `Poe2FrameInput` 交给通用 `MapLocalizer`；
6. 只有有位置的 fresh 结果才追加 `TrajectoryBuffer`，旧确认点只保存在
   `latest_confirmed_position`，不冒充本帧位置；
7. 发布 `Poe2LocalizationState`，包含原始/预处理帧、四种视觉层、候选、局部/全局点、mode/source/confidence、
三段耗时、失败原因和 `recognition_diagnostics`；诊断字段包括候选数、通过数、最大面积、
   最大置信度、mask 像素、HSV 范围、轮廓面积及 `no_contour`/`below_min_area`/
   `below_confidence`/`ambiguous`/`ready`/`center_configured` 原因，并通知显式 listener。

`Poe2LocalizationRuntime.configure_snapshot()` 用 `build_reference()` 构建业务参考并应用当前 `TerrainOrientation`，在
没有外部 localizer 时注入 `_global_match()`/`_local_match()`：全局 matcher 在完整参考层
执行 `cv2.matchTemplate`，局部 matcher 将模板搜索窗口限制在人物预测点的
`search_radius` 内。matcher 优先使用 `Poe2VisualEvidence.match_mask`，因此与绘图模式共享
wall/edge 加权融合、动态高饱和区排除和人物半径擦除；只有兼容旧测试/注入 recognizer 时才
回退 `_wall_mask()`。两者都要求足够特征和置信度阈值，否则返回 `None`。`HSVPlayerObservationRecognizer`
只在 `region` 模式把 HSV 玩家 mask 的轮廓转换为通用候选，并保存本次识别的可审计诊断；中心
模式不经过它；它不写控制设备。

`src/auto_modules/ui/modes/poe2_live_terrain/capture/selection_controller.py::Poe2CaptureSelectionController`
独立管理 PoE2 画框和人物中心点覆盖层，把物理 `MonitorBinding` 返回给 PoE2 profile；它不写
绘图模式 `AppContext`。overlay 的逻辑坐标按 DPI 转成物理位置；capture size 本身遵循
`SquareScreenCapture` 的物理像素契约，不再二次乘 DPI，region 画框也不覆盖 center size。中心模式修改截图大小时，配置面板立即围绕原物理人物点重建 binding 并更新 marker；正式页、测试页和直接 profile 加载都由配置模型再次保证该不变量。
`config_panel.py::Poe2MonitorConfigPanel` 提供正方形/圆形、截图大小、圆形半径、画框/中心点，
并对齐绘图模式的 wall/fog、CLAHE、颜色深化、wall/edge 权重、Canny 和人物擦除半径快捷控件。
全部控件与完整 `recognizer_params` 双向同步，并在任何 selection/config 重建时保留独立
`stitcher_params`。`profile_toolbar.py::Poe2ProfileToolbar` 管理本地
profile 列表及 CRUD。`monitor_dialog.py::Poe2MonitorConfigDialog` 组合上述 PoE2 控件，
复用公共 `ColorPickerDialog` 和 `AdvancedSettingsDialog`，但将结果写回当前 PoE2 profile；
高级窗口保留与第一页相同的 stitcher tab，并按 `HSVRecognizer`/`MapStitcher` 支持键拆分写回两组参数，
未出现在窗口控件中的 canvas/scale/质量门仍原样保留；配置面板位于滚动容器中。
运行时由 `set_editable(False)` 锁定；`page.py` 在构造、切换和保存三个入口统一调用
`_apply_monitor_config()`，通过注入 profile store 管理初始化、地图捕获、
QTimer、预处理画面/实际 match mask 双预览、状态文本和关闭时清理。绘图模式文件没有改动。
`presenter.py::present_localization_overlay()` 在 terrain pixmap 副本上绘制确认轨迹和真实
全局 marker，并在 registration 存在时以 OpenCV 任意角度逆变换整张 pixmap，使方向和
marker/轨迹保持同一坐标系；它不参与定位计算。`MainWindow.setup_ui()` 是组合根，创建独立 store、
`MonitorFrameSource` 和 `Poe2HybridProductRuntime` 后注入页面，保留原有模式索引和关闭顺序。
组合根会把传入的 `HSVRecognizer` 参数复制到 PoE2 专属实例，避免绘图模式与 PoE2 共享可变
识别器状态；另注入接受未保存 config 的 preview capture，供颜色校准直接使用当前选区。

**数据流 F-POE2-CAPTURE-TEST（verified 2026-09-21）：**

1. `MainWindow.setup_ui()` 调用 `build_poe2_live_terrain_composition()`，注入独立的 `capture_test_service`、`capture_test_archive`、`capture_sample_archive`、`capture_stitching_archive`、`capture_stitching_session_factory`、`capture_preview` 和 dedicated recognizer。
2. `Poe2LiveTerrainPage._build_ui()` 创建内部“数据采集测试”tab，并把上述依赖传给 `Poe2CaptureTestPage`；测试 service 的 `MemoryTerrainStore` 与实时定位页隔离。
3. `Poe2CaptureTestPage.open_capture_monitor()` 首次创建唯一 `Poe2CaptureMonitorWindow`，以后只激活同一实例；config provider 始终返回页面最新 profile。
4. 窗口 `QTimer.timeout` 调用 `refresh_frame()`；输入是 `Poe2MonitorConfig`，输出是只读 `CaptureEvidence(raw, processed, feature, wall_mask, fog_mask, raw_gray, captured_at, monitor_config)` 和同周期 terrain 引用，副作用为屏幕读取和 UI pixmap 更新。
5. 地图捕获成功后，`Poe2CaptureTestPage` 只读一次同实例人物位置并保存在页面；用户点击“保存当前对比样本”后，`save_current_sample()` 通过 provider 把现有 evidence、同周期 terrain 和该人物样本交给 `CaptureSampleArchive.save()`。最终目录包含基础/可选视觉层、`terrain.png` 和带实例校验及 native/oriented 双坐标的 `sample.json`；缺人物位置时明确记录 missing。
6. 历史上一个/下一个和图层选择只通过 `CaptureSampleArchive.list_samples()/load()` 读取合法 manifest，可直接比较 wall/fog/raw-gray；旧样本缺少可选层时显示缺层，不会借用其他样本图像。
7. 用户点击“开始绘图”后，窗口先把当前 profile 的 `stitcher_params` 传给 `Poe2StitchingSession.configure()`；参数变化只允许在非 running 状态重建会话，随后当前及后续 evidence 经过 `consume()` -> `MapStitcher.add_evidence()` -> `add_frame_to_stitcher()`。输出为相对拼图、位置、轨迹和统计，仅驻留独立会话内存，不修改 native terrain 或正式定位状态。
8. 用户点击“保存拼图实验”后，`Poe2StitchingArchive.save()` 原子写入 `stitching_sessions/<timestamp-profile>/` 的七张基础 PNG、可选同实例 `terrain.png` 与 `session.json`；没有已接受轨迹时拒绝保存，terrain 缺失时明确记录 missing。
9. `Poe2CaptureTestPage.suspend()/shutdown()` 先停止 follow、dual-target、program-probe、视觉 worker 与相关 timer，释放实验 output，再关闭独立窗口；窗口 `closeEvent()` 停止定时器、暂停拼图并释放当前帧。采集监控链路本身不调用 `Poe2LocalizationRuntime.tick()`，不触碰绘图页面实例或 LAN；只有用户显式启动程序移动/跟随实验时才经过独立 output adapter。

**数据流 F-POE2-DUAL-FIRST-FRAME-PREVIEW（verified）：**

双人测试页预览支链：`run_dual_first_frame_experiment()` 一次只读两个 native anchor，至多截取三张小地图；所选帧的 `extract_combined(..., exclude_player=False, exclude_dynamic=False)[0]` 同时用于 `HybridFrame.wall_mask` 和 `_render_preview()`。后续 `QTimer.timeout -> refresh_preview() -> _render_preview()` 在 `_dual_preview_active` 下保持同一无擦除参数；重新获取地图、清空或启动单人/多帧实验后恢复默认参数。副作用只有只读屏幕/进程采集、日志和 UI 更新，无设备输入或 LAN 同步。

**数据流 F-POE2-DUAL-TARGET-MOVE（verified 2026-10-03）：**

1. `Poe2CaptureTestPage.start_dual_target_experiment()` 接收侧栏 `p1_identity/p2_identity: str`，校验 `TerrainSnapshot.metadata.instance_id: str`、`DualMotionState.players: Mapping[str, Point | None]` 和 `latest_dual_captured_at_ms: int`。输出待命 `SimulatedFollowRuntime`、两个 `RoleId`、`ProgramFollowOutput`；副作用仅创建页面会话与未 arm 的输出对象。
2. `ScalableMapWidget.pixel_clicked(int,int)` 把原 pixmap 坐标交给 `_on_follow_map_click(display_x: float, display_y: float)`；重定位恢复也可传回保存的浮点 source 坐标。`localization_source_point()` 用当前旋转/镜像和地图 source size 输出 `native_point: tuple[float,float]`，不对地图点击再次应用注册用的 scale/translation；页面校验墙层 shape 并保存 source/native/display 三坐标。副作用为目标 overlay 与日志；越界不改原目标。2026-10-03 实机样本：source `(1039,2099)` 在 angle `221`、镜像开启时得到 native `(606.168047,1204.908149)`，往返误差 0；这些数值是该实例观测，不是通用默认。
3. `_on_follow_map_click()` 把 `native_point` 和 `now_ms: int` 交给 `SimulatedFollowRuntime.set_simulated_target()`；该方法输出同实例 `PositionSample`，无设备副作用。首次有效点击启动新场景专属 100ms Qt timer，再次点击覆盖目标。
4. `_tick_dual_target_experiment_impl()` 消费最新 `DualMotionState.players`、实际 `captured_at_ms` 和两名 `RoleId`；分别调用 `update_follower_position(PositionSample)`，再调用 `runtime.tick(now_ms)` 输出 `dict[str, FollowObservation]`，每条观察携带 native 位置、目标、路线、状态和向量。帧龄超 700ms 时先释放输出，不调用 planner；无进度/局部墙接触由各 follower 独立维护。
5. 对每条 `PROGRAM_READY` 观察，`ProgramFollowOutput.arm(role)` 取得对应 controller lease，`apply(observation, elapsed_ms)` 经 `_native_route_vector_for_input()` 和 `ProgramGamepadOutput.write()` 发出控制器 1/2 向量；`ARRIVED/WAITING_POSITION/BLOCKED/MAP_MISMATCH` 先中性再 release 对应 lease。输出异常进入页面统一停止并释放两个 lease，不触碰键鼠或 LAN。
6. `_update_follow_local_contact(runtime,state,role,observation,log_step)` 从同帧 wall mask 和角色 screen marker 调用 `inspect_minimap_contact()`，输出 raw/centerline 墙体与左右空闲度；`runtime.update_local_contact()` 更新角色 contact monitor。diagnostics 请求全局恢复时保存点击 source/两身份/实例，释放全部 lease，并触发有 10 秒冷却的 `_start_dual_motion(recovery=True)`；新鲜同实例 tracking 帧调用 `_maybe_resume_dual_target_after_relocalization()` 重建会话和重放点击。
7. `_render_dual_target_overlay()` 只把规划器实际返回的 native 路线点和人物位置正向转成 display，调用 `ScalableMapWidget.set_overlay(players, target, routes)`；无路线时保留目标标记但不画人物到目标的假直线。页面侧栏分别显示状态/距离并限流记录诊断。停止、换图、清图或关闭调用 `stop_dual_target_experiment()`，终止 timer、清目标并关闭两个输出，无磁盘写入。

**数据流 F-POE2-HYBRID-LOCALIZATION（verified 2026-09-22）：**

1. `Poe2LiveTerrainPage.capture_map()` 把当前 `TerrainSnapshot` 和 monitor config 交给 `Poe2HybridProductRuntime.configure_snapshot/configure_monitor()`；`start_monitoring()` 启动同一 runtime 和页面唯一 `monitor_timer`。嵌入数据采集 tab 接收同一 PoE2 factory，但使用独立 experiment/session/timer，不接管正式 runtime。
2. `build_poe2_hybrid_localization_experiment(snapshot, config_provider, preview_capture, recognizer, player_position_source)` 输出 `Poe2HybridLocalizationExperiment`。它先应用当前 profile 识别参数，按 profile 方向构建 `TerrainReference`，按 native shape 创建 anchor provider，再从可行走区薄边界缓存 `MapRuntime.distance_field`；没有进程读取，直到 controller 请求 anchor。
3. `Poe2HybridLocalizationSession.tick()` 先调用 `HybridLocalizationController.prepare_capture()`。首次/恢复时 controller 消费当前 revision，并让 `Poe2MemoryAnchorProvider.read_once(expected_instance_id)` 调用 `Poe2PlayerPositionSource.read_once()` 一次，输出待配对 `PositionAnchor(position in oriented reference, area_instance, captured_at_ms, source=poe2_memory)`；副作用是一次游戏进程只读和 `read_count += 1`。读取失败直接发布 `RECOVERY_REQUIRED` 且不截图；正常局部帧不读内存。
4. 锚点准备成功后 session 才调用一次 config provider 和一次 preview capture，在 capture 后记录时间；evidence builder 从同一 raw frame 输出 `CaptureEvidence(raw, processed, feature, wall_mask, fog_mask, raw_gray, monitor_config)`，再输出 `HybridFrame(frame_id, captured_at_ms, wall_mask, local_player)`。这避免耗时内存读取发生在截图之后，使移动中的锚点和旧画面错时。
5. `HybridLocalizationController.update(frame)` 根据 mode 分支。首次/恢复时取出同 revision 待配对锚点并清空，再交给 registrar；重复消费、缺少已准备锚点或读取/注册失败均 fail closed，不会自动增加读取次数。
6. `AnchoredAbsoluteRegistrar.register(frame, reference, anchor, prior)` 输出 `AbsoluteRegistration | None`。它先按真实 capture size 缩放 terrain crop 与顶部排除区，删除孤立紧凑噪声，再把 walkable mask 转为薄边界；首次搜索完整 angle/reflection/scale 空间，比例粗搜 `0.35..2.45` 并以 `0.02` 细化。精搜保留同一位置附近的多个角度/比例到 anchor 联合评分，最终只对独立 coarse basin 判歧义；恢复先锁定 prior，失败再自动完整搜索。它只处理内存数组，不写文件；拒绝/歧义输出 None，但同时更新 `last_diagnostics`。
7. 正常帧改走 `VisualLocalTracker.track(frame, reference, previous_frame, previous)`；输出固定 similarity 参数的新 registration 或 None。它调用基于同一薄边界 distance field 的 `LocalMapMatcher.match(origin=previous.translation, radius=96)`，PoE2 组合参数为 `max_error=4.0/min_margin=0.02`；没有整图回退和内存读取。
8. 成功 registration 经 controller `_accept()` 输出 fresh position、latest confirmed、bounded trajectory 和 diagnostics；局部失败输出 `RECOVERY_PENDING/position=None` 并创建一个 revision，不追加轨迹；恢复失败输出 `RECOVERY_REQUIRED`，后续普通 tick 只发布失败状态。
9. `Poe2HybridProductRuntime.tick()` 把 controller state 与 session 最近 raw/processed/wall mask 合成 `Poe2HybridProductState`，附加 anchor read count 和帧耗时；`Poe2LiveTerrainPage.handle_runtime_state()` 更新双预览、mode/source/confidence、本帧位置、最后可信位置、recovery revision/read count，并把方向/镜像变化后的 registered base pixmap 缓存到 `ScalableMapWidget`，只通过独立 overlay 绘制 fresh marker、轨迹和候选。`RECOVERY_REQUIRED` 保持 timer 活动但不再读内存，页面提示需要重新定位；页面关闭/重置会停 timer/session。没有 Xbox、键鼠、Host 或 LAN 副作用。

**混合定位数据契约（verified）：** `SimilarityTransform2D` 显式保存 OpenCV 角度、水平镜像、比例和 reference top-left 平移；运行算法不得从 diagnostics 反推这些字段。`HybridLocalizationState.position` 仅表示本帧成功位置；`latest_confirmed_position` 可以在失败帧保留以便诊断，但 UI 不得把它画成本帧新 marker。状态转换仅为 `NEED_ABSOLUTE -> LOCAL_TRACKING -> RECOVERY_PENDING -> LOCAL_TRACKING/RECOVERY_REQUIRED`，以及显式 retry/stop/reset。

**当前产品/实验装配边界（verified 2026-09-22）：** 正式 `Poe2LiveTerrainPage` 的唯一 `monitor_timer` 已驱动 `Poe2HybridProductRuntime -> Poe2HybridLocalizationSession`；数据采集 tab 现在接收同一 factory，但只创建自己的实验对象和 timer，避免与正式 runtime 共享 session/state。旧 `Poe2LocalizationRuntime` 模块保留给兼容测试/调用方，但不再由 PoE2 正式 composition 注入。算法仍留在 `experimental/hybrid_localization`，产品适配器只处理生命周期和展示 DTO；后续多地图验证前不下沉算法或阈值。

**数据流 F-POE2-LOC（verified）：**

`Poe2ProfileToolbar` 选择 profile -> `Poe2MonitorConfigDialog.save()` ->
`Poe2MonitorProfileStore.save()`/`activate()` -> `Poe2LiveTerrainPage._on_monitor_config_saved()`。
`Poe2LiveTerrainPage.capture_map()` -> `Poe2HybridProductRuntime.configure_snapshot()` 创建当前地图 experiment；
`Poe2LiveTerrainPage.start_monitoring()`（前置为 captured snapshot 和 PoE2 binding）调用 runtime `start()` 并启动唯一 `QTimer`。每次 timeout 调用
`Poe2LiveTerrainPage._tick_runtime()` -> `Poe2HybridProductRuntime.tick()` -> 上述 F-POE2-HYBRID-LOCALIZATION 第 3-8 跳 -> `Poe2HybridProductState` -> `Poe2LiveTerrainPage.handle_runtime_state()`。最终副作用是更新预处理/match 双预览、恢复诊断、定位状态和 `ScalableMapWidget` overlay；除显式 profile 保存外，没有输入、网络或地图文件写入。

**风险登记（P1/P2）：**

- P1，`Poe2LocalizationRuntime._global_match()`：native terrain 与 minimap 的实际比例仍未由
  实机样本确认；旋转/镜像现在可由 profile 显式校准，但最终组合、scale、首帧 confidence
  仍需记录。若要自动候选比较，必须增加对称地图的置信度差阈值，不能盲选。
- P1，`Poe2LocalizationRuntime._global_match()`：combined visual matching、独立 recognizer 参数
  profile、完整快捷/高级参数、颜色校准和实际 match-mask 预览已经接通，但真实 PoE2 样本尚未完成参数校准；若
  `global_match_failed`，应先在页面核对 match mask 的墙体/边缘表达，再判断 scale、方向或阈值，
  不再通过修改中心人物识别逻辑来绕过墙体匹配失败。
- P1，`HSVPlayerObservationRecognizer.__call__()`：仅影响 `region`/多人模式；人物颜色、透明度
  或多角色同时出现时，候选数可能为 0 或大于 1，当前 fail closed 会显示失败而不伪造中心位置。
  当前区域门槛已针对小轮廓校准为 `0.60`，但仍需用页面诊断字段实机确认 HSV/形态学参数，不能
  把“取最大轮廓”下沉为通用引擎规则；`center` 模式不依赖此识别器。
- Resolved 2026-09-24 - `Poe2LiveTerrainPage.handle_runtime_state()` 原来每帧重绘完整大图 pixmap；
  现在 registered base map 只在地图/方向变化时生成，marker/trail 由独立 overlay 绘制。仍需实机
  验证 UI 平均/峰值耗时，若预览本身仍超时，再对两个小图预览做刷新限频。
- P1，`VisualLocalTracker.track()`：接受的 `phaseCorrelate()` 位移会通过
  `previous_position - global_shift` 无限累计；`quality >= 0.20` 只表示相位响应，不能证明
  绝对位置没有系统误差。墙体粗细变化、动态图标和遮挡可造成每帧小偏差，长时间移动后会漂移，且
  只有相位失败/大跳变才触发 `LocalMapMatcher`。建议增加距离/时间门控的局部形状校正，并用校正结果
  周期性替换预测位置；校正失败时应保持上一可信点或进入恢复，而不是继续无限累加。
- P1，`Poe2LiveTerrainPage._tick_runtime()` 与 `handle_runtime_state()`：定位 tick 和同步 UI
  展示共用 Qt 主线程；日志已观察到 runtime 约 `63~73ms/帧`，UI 绘制约 `192~241ms/帧`，超过
  `33ms` 定时器周期。低展示帧率会增大帧间位移并放大相位误差，形成算法与渲染的耦合风险。建议将
  定位采样与 UI 展示解耦，并对预览/overlay 限频。
- Resolved 2026-09-24 - `present_localization_overlay()`、`_apply_inverse_registration_transform()`
  和 `ScalableMapWidget.focus_on_point()` 的整图操作已从正式页位置更新路径移出：方向变换缓存一次，
  overlay 只绘制点/线，跟随只移动滚动条。兼容调用方仍可显式使用旧 presenter；正式 PoE2 页不再每帧调用。
- P1，`VisualLocalTracker` 的 PoE2 校正门 `12 frames / 24 native px / 1500ms` 尚未经过长距离真实移动
  标定；若局部 matcher 在动态墙体上频繁失败，会回退短期 phase 预测并再次等待门限。验收必须记录
  `correction_attempted/accepted`、`correction_distance`、`position_jump`，不能只看 `visual_f2f` confidence。
- P2，`CaptureSampleArchive.save()`：保存时同步 PNG 编码完整 terrain，超大地图可能短暂阻塞 Qt
  线程。当前功能是低频手动测试操作；若样本实测编码明显卡顿，应把已经冻结的 evidence/terrain
  交给专用 worker，并保持最终目录原子发布，不能改成持续每帧写盘。
- P1，`CaptureSampleArchive._create_temporary_directory()`：Windows 的 `tempfile.mkdtemp()` 默认
  owner-only DACL 会随目录重命名保留；当应用和分析会话使用不同身份时，样本会保存成功但无法读取。
  当前实现用父目录下的普通 `Path.mkdir()` 继承 ACL，并由 Windows 回归测试断言 `(I)`；后续不能
  为了复用 tempfile 而恢复 `mkdtemp()`，除非同时显式复制并验证父目录 ACL。
- P1，`Poe2StitchingSession.consume()`：启动局部拼图目前复用绘图模式的关键帧/F2F 和质量门，但没有 native terrain 或独立里程计 ground truth；重复房间仍可能形成一致但错误的累计位姿。触发条件是相邻帧视觉相似、移动过快或动态覆盖较大。实机验证必须观察 overlay 是否重影、轨迹是否连续，并保留整套实验归档；本阶段不得把相对轨迹直接当正式全局坐标。
- P2，`Poe2StitchingSession.__init__()`：默认 profile 与第一页对齐为 `5000 x 5000`，wall/fog/explored/canvas 和 float32 weight 等画布合计约 200 MB。`Poe2CaptureTestPage` 当前只允许一个窗口且关闭后保留会话到页面销毁；若未来支持多窗口/多号，必须改为延迟分配/按需 tile 或显式限制并发，不能共享可变 stitcher 规避内存问题。
- P1，`AnchoredAbsoluteRegistrar.register()`：粗 Top-K 的人物可行走优先级、重复精搜候选去重及“4 个方向盆地/8 个比例分离种子/0.10 粗分差”已用当前 MapFlotsam 失败快照和合成集验证，但顶部文字排除、锚点半径、结构分与 margin 仍缺少多地图证据。触发条件：不同地图墙密度、重复房间、传送门/文字粗块使错误候选通过，或真实锚点误差超过 `8px` 使窄幅 coverage 容差不生效。复现方式：实机记录多地图首次与恢复的 angle/flip/scale/anchor error/candidate margin，并人工核对位置。建议：阈值继续留在 PoE2 实验配置，多地图通过前不得下沉或称为正式可用。
- P1，`HybridLocalizationController._attempt_absolute()`：一次性 gate 防止自动连续读内存，但 UI 的显式 retry 可以产生新 revision。触发条件：上层错误地自动点击/调用 retry，会重新引入高频读取。复现方式：恢复失败后连续 tick 读数应不变；每次显式 retry 恰好加一。建议：retry 只保留人工/明确恢复策略入口，正式化前增加速率上限和审计事件。
- P2，`Poe2HybridLocalizationSession.tick()` 与 `Poe2CaptureTestPage.handle_hybrid_state()`：截图、识别、局部匹配和完整 terrain pixmap 重绘当前都在 Qt timer 线程同步执行。触发条件：2416x2277 地图、高特征帧或首次 similarity 搜索导致 UI 卡顿/掉帧。复现方式：实机记录 tick/注册耗时和 UI 响应。建议：先用日志确定瓶颈，再将冻结帧交给单 worker；仍保持每 revision 单次读取和顺序状态提交。
- P2，`Poe2ProfileToolbar.delete_profile()`：当前只允许删除后仍保留至少一个 profile，
  但 profile 文件和 index 的原子一致性仍依赖同一目录的文件系统语义；若进程在删除后写
  index 前中断，下一次加载会按可读 profile 恢复并选第一个。需要后续增加显式恢复诊断。

## 当前补充：Navigation 首帧定位诊断

2026-06-04 新增独立首帧定位探针：`D:\ACloud\.venv\Scripts\python.exe debug\navigation_localization_probe.py --map-folder "D:\ACloud\minimap_stitcher copy 13\map_data\A" --image "D:\ACloud\minimap_stitcher copy 13\debug\minimap_samples\A\20260604_135548_439_A_minimap.png" --top 10`。探针只用于诊断，不接入正式导航循环；它复用正式 `NavigationCore`、`HSVRecognizer`、`NavConfig` 的识别参数、`map_data.npz` 的 `draw_scale/wall_close_kernel_size`，然后输出 `report.json`、`wall_mask.png`、`match_mask.png`、`wall_mask_scaled.png`、`matched_map_patch.png`、`saved_pos_patch.png` 和 `top_candidates_sheet.png`。

本轮样本最新输出目录：`debug/navigation_localization_probe/20260604_142234_20260604_135548_439_A_minimap/`。结果显示当前生产链路首帧全图匹配最高候选为 `(4211,3272)`，confidence=`0.7745`，`frame_origin_global=(3911,2972)`；`map_data.npz` 保存的 `current_pos=(4792.48,3630.25)` 在同一张 `matchTemplate` 响应图上的分数为 `-0.0208`。配置侧没有发现 `draw_scale` 漂移：`config_draw_scale=3.0`、`map_draw_scale=3.0`、`used_draw_scale=3.0`，模板尺寸为 `600x600`。因此当前证据指向“首帧全局模板匹配根据地图墙体选择了另一块高相似区域”，不是掉落物事件、hook 或异步事件线程修改了人物定位坐标。

状态保留修正：`core/localization/navigation_core/state.py::initialize_runtime_state()` 现在保留 `map_data.npz` 读出的 `drawing_saved_pos/last_pos`，用于 UI 上次位置 marker 和首帧 debug 对比；它不会自动把保存点设为 `current_pos`，也不会把 `is_localized` 设为 true，因此不会改变首帧定位算法。复跑探针确认结果仍为 `(4211,3272)`，但首帧 debug 会打印保存点差异 `dx=-581.48, dy=-358.25`。

运行时坐标诊断同步增强：`core/navigation_tasks/coordinate/localization.py` 每 `localization_sample_interval_ms=500` 记录一条 `localization sample`，字段包含 raw/trusted/control、confidence、invalid_reason、active_task、registration source/conf/player/local/origin，以及 `shift`、`visual_delta_dist`、`template_top_left`、`search_offset`、`forced_global` 等关键 metadata。`core/navigation_tasks/coordinate/log.py` 写入项目根目录 `logs/coordinate_diagnostics.log`，并桥接到当前 event session log，方便实跑后直接对齐事件日志和定位日志。

## 当前补充：Loot 掉落物事件

正式事件类型 `loot` 的实现位于 `features/torchlight/loot/`，正向模板资产在 `resources/games/torchlight/event_templates/loot/minimap/`，人物箭头负样本在 `resources/games/torchlight/event_templates/loot/exclude/player_marker/`，单图/handler 验证入口为 `debug/loot_event_probe.py`，批量正负样本评估入口为 `debug/loot_dataset_eval.py`。`features/torchlight/composition.py` 注册 `PortalEventDefinition()` 和 `LootEventDefinition()`；`MainWindow` 把该工厂注入导航 widget，未注入时 `gui/modes/navigation/event_adapter.py::create_default_event_registry()` 只返回空的通用注册表。`core/events/config_model.py::DEFAULT_EVENT_CONFIG` 的 `events` 为空，Portal/Loot 默认值由各自 definition 提供并通过通用 `apply_registered_event_defaults()` 物化。

2026-06-03 新增数据集回归入口：`D:\ACloud\.venv\Scripts\python.exe debug\loot_dataset_eval.py --dataset-root D:\ACloud\image\sample --map-config map_data\A\event_config.json`。脚本读取 `02_has_loot` / `03_no_loot` 作为正负标签，每张图独立创建 detector，并按 `presence_confirm_frames` 连续喂帧；输出 `summary.json`、`cases.csv` 和 FP/FN overlay，默认关闭 runtime diagnostic 落盘。当前基线输出在 `debug/loot_dataset_eval/20260603_104108/`：77 张样本中 TP=25、FP=52、FN=0、TN=0，precision=0.3247、recall=1.0000、FPR=1.0000，平均检测耗时约 215.747ms。误检分数低于地图 A 的 `weighted_threshold=0.70`，说明后续优化重点是 `detection.scoring.accepted_candidate()` 的强证据直通路径和 accepted 后排除规则，而不是只调高总阈值。

2026-06-03 新增独立 ROI 多特征匹配探针：`D:\ACloud\.venv\Scripts\python.exe debug\loot_feature_match_probe.py --dataset-root D:\ACloud\image\sample --map-config map_data\A\event_config.json --dump-all`。该脚本验证“ROI 内滑窗 + masked template + edge overlap + Chamfer + HOG-lite + 轮廓/Hu + 颜色辅助”的 CNN-like 特征响应定位思路；同一套核心算法已经抽到 `features/torchlight/loot/detection/feature_match/`，并通过 `detector_mode=async_feature_match` 接入正式 runtime。默认只匹配黄钻、红星、金三角三个形状明确的模板，尺度为 `0.75,0.85,1.0`，每模板每 ROI 取 `top_k=2`，并按模板类型施加语义门槛。探针默认和正式默认必须保持一致：`feature_match_threshold=0.64`、`feature_match_collect_threshold=0.38`、`feature_match_top_k_per_template=2`、`feature_match_max_candidates=5`、`feature_match_search_padding=48`、`feature_match_scales="0.75,0.85,1.0"`。最新完整样本输出在 `debug/loot_feature_match_probe/20260603_174004/`：TP=25、FP=0、FN=0、TN=52，precision=1.0000、recall=1.0000、FPR=0.0000，平均耗时约 341.366ms、p95 约 664.686ms。线程并行 `--workers 4` 墙钟略降但单张图延迟显著上升，因此生产接入采用独立 worker 线程，而不是帧内并行。

`loot` 检测主链路：`LootMinimapDetector.detect(tick, config)` 读取 `tick.raw_minimap_frame`，先调用 `detection.pipeline.detect_loot_presence()` 做轻量存在判断。粗检只构造 HSV 金色/暖色/银白/高亮 mask，并在小地图中心按人物箭头负模板确认后挖掉固定玩家区域；小尺寸图标样本会跳过中心遮罩，避免整张模板样本被擦掉。默认 `detector_mode="async_feature_match"`：存在判断连续达到 `presence_confirm_frames=2` 后，`AsyncLootPerception.maybe_submit()` 在独立 worker 线程复制当前帧并调用 `FeatureLootMatcher.detect()`，主线程只读取缓存 detection，不阻塞导航循环。worker 把命中的局部点投影为全局记录，后续帧只用当前 `FrameRegistration` 把缓存记录投回局部 detection；`async_full_scan_interval_ms=1000` 限制全量提交频率，`async_track_refresh_ms=8000` 避免已知目标被反复全量重识别，`async_track_ttl_ms=8000` 和 absence streak 控制消失。`detector_mode="feature_match"` 是同步回归模式，直接调用同一套 feature matcher；`detector_mode="weighted_blob"` 保留旧三路加权后端，调用 `detect_loot_blobs(frame, prepared_templates, config, exclusion_templates, seed_bboxes=...)`。detector 初始化阶段会预先生成正向模板、feature 模板和人物箭头负模板的多尺度灰度图、边缘图、mask，避免每帧重复 resize/Canny。

2026-06-03 17:40 接入一致性验证：生产 `FeatureLootMatcher.detect()` 同步路径在 `D:/ACloud/image/sample` 上跑出 TP=25、FP=0、FN=0、TN=52；生产默认 `LootMinimapDetector(detector_mode="async_feature_match")` 在同一数据集上模拟有效 `FrameRegistration` 并等待 worker 返回，也跑出 TP=25、FP=0、FN=0、TN=52，默认参数打印为 `async_feature_match 0.64 0.38 2 5 48 0.75,0.85,1.0`。因此后续测试异步路径时需要等待 worker 完成，不能把“本帧尚未返回检测”视为算法漏检。

人物处理现在分两层：`detection.roi.apply_player_center_mask()` 先在粗检 mask 层处理固定中心人物位置，只在中心 patch 有足够亮/金/白/蓝像素且负模板命中人物箭头时，按 `player_center_mask_radius=28` 挖空中心人物前景；候选通过模板/外形/颜色评分后，`detection.seed_scan._best_candidate_for_seed()` 和旧区域扫描路径还会只对已接受候选调用 `detection.exclusions.is_player_marker_candidate()` 与 `is_blue_map_artifact_candidate(patch, shape_score)`。后者用蓝/青底比例、金色比例、亮白比例、白色比例和候选外形分数过滤人物底色、蓝白地图装饰、边线等误检；因为只在 accepted 候选出口执行，成本被 seed 粗检和局部复核限制住。当前掉落物模板和人物负样本模板均为带 alpha 的透明 PNG，`detection.images.foreground_mask()` 会优先使用 alpha 作为匹配 mask，避免小地图背景参与模板响应。Loot 调试遮罩由 `ui/modes/torchlight/navigation.py::build_loot_debug_overlays()` 解释业务配置并输出通用 `EventCircleOverlay`；`ui/modes/navigation/presentation/event_overlay.py` 只绘制领域中立图元，圆半径仍按 `player_center_mask_radius * draw_scale` 换算。随后 `detection.clustering.cluster_candidates()` 把堆叠或相邻候选合并成区域级 `LootCluster`。`detection.conversion.clusters_to_detections()` 将 blob center 写入 `EventDetection.local_minimap_pos`，metadata 写入 bbox、候选数、命中模板、三路分数和 `pickup_radius`。

`loot` 执行主链路：`EventCoordinator.observe()` 仍负责 detect -> position stabilize -> memory merge；`NavigationTaskBuilder.build()` 把 loot `EventTask.metadata["pickup_radius"]` 写入 `NavigationTask.radius` 和 `metadata["event_stop_radius"]`；`EventApproachController.update()` 优先使用 per-task `event_stop_radius`，因此 loot 在拾取半径内停稳后释放给 handler。`LootPickupHandler.update(tick, task)` 距离远时返回 `EventAction.move_to(task.global_pos)`，进入 `pickup_radius` 后返回 `EventAction.press_key(pickup_key)`，默认 `a`；按键后等待 `post_pickup_wait_ms`，若 `task.last_seen_ms` 超过 `absence_confirm_frames * absence_frame_ms` 未刷新，则返回 `EventAction.complete()`。

`loot` 事件定位不是全图定位。`EventPositionStabilizer.project_detection()` 只用当前帧 `FrameRegistration.frame_origin_global + detection.local_minimap_pos * draw_scale` 把小地图局部检测点投影到全局坐标，不调用 `NavigationCore` 的模板全图搜索。移动时“像一直重定位”的体感来自另一条链路：掉落物是 blob/区域目标，检测中心会随堆叠、遮挡和小地图运动轻微漂移；旧 `EventTask.mark_seen()` 每次稳定观测都会覆盖 `task.global_pos`，导致 `NavigationTaskBuilder` 生成的新事件目标点变化，`MovementExecutor.ensure_movement_path()` 因目标变化触发 A* 重规划和重复点击。当前通过 `core/events/memory/target_update.py::should_update_task_target()` 增加事件级目标更新策略，loot 默认 `target_update_mode="lock_after_confirm"`：task 确认进入 `PENDING/RUNNING` 后锁定首次目标，只刷新 `last_seen_ms`、`confidence`、`seen_count`、metadata 和 `last_observed_global_pos`，不再拖动导航目标。这样消失确认仍由最新观测时间驱动，但 A* 目标不会被每次 blob center 漂移带着跑。2026-06-09 起 portal 也恢复锁点配置，默认 `target_update_mode="limited_after_confirm"`、`target_update_max_drift=18`，用于拒绝相邻稳定簇之间的大幅跳点，同时允许确认前和小范围内的稳定修正。

关键参数：`priority=60`、`detector_mode="async_feature_match"`、`feature_match_threshold=0.64`、`feature_match_collect_threshold=0.38`、`feature_match_top_k_per_template=2`、`feature_match_max_candidates=5`、`feature_match_search_padding=48`、`feature_match_scales="0.75,0.85,1.0"`、`async_full_scan_interval_ms=1000`、`async_track_refresh_ms=8000`、`async_track_ttl_ms=8000`、`async_known_seed_radius=72`、`weighted_threshold=0.54`、`collect_threshold=0.28`、`detection_interval_ms=450`、`reuse_previous_detections=true`、`presence_confirm_frames=2`、`masked_color_match_enabled=true`、`roi_prefilter_enabled=true`、`roi_min_area=12`、`roi_max_size=150`、`roi_expand=48`、`template_weight=0.46`、`shape_weight=0.42`、`color_weight=0.12`、`player_marker_exclusion_enabled=true`、`player_marker_template_threshold=0.75`、`player_marker_exact_template_threshold=0.96`、`player_marker_blue_ratio_threshold=0.30`、`player_center_mask_enabled=true`、`player_center_mask_overlay_enabled=true`、`player_center_mask_radius=28`、`max_blobs_per_frame=3`、`target_update_mode="lock_after_confirm"`、`target_update_max_drift=0`、`arrival_radius=90`、`pickup_radius=58`、`pickup_key="a"`、`post_pickup_wait_ms=450`、`absence_confirm_frames=2`、`pickup_press_limit=3`、`cooldown_radius=180`。旧地图配置若还没有 `roi_prefilter_enabled` 字段，会自动迁移到新的性能默认，避免旧的 `masked_color_match_enabled=false` 覆盖新召回策略。portal 默认优先级仍为 100，且默认 `target_update_mode="limited_after_confirm"`、`target_update_max_drift=18`，因此默认调度下传送门优先于顺路拾取，并且确认后不会被大幅跳动观测拖走。

单独验证命令：

```powershell
D:\ACloud\.venv\Scripts\python.exe debug\loot_event_probe.py --handler-smoke
```

断言式单图探针：

```powershell
D:\ACloud\.venv\Scripts\python.exe debug\loot_event_probe.py --image D:\ACloud\image\test\1b2a3a7e-34fd-453d-8e4f-ecb7cbe99cc5.png --dump-stages --expect-count 1 --expect-center 173,112 --center-tolerance 8
```

性能探针命令：

```powershell
D:\ACloud\.venv\Scripts\python.exe debug\loot_event_probe.py --benchmark --handler-smoke
```

事件目标漂移探针：

```powershell
D:\ACloud\.venv\Scripts\python.exe debug\loot_event_probe.py --target-jitter-smoke
```

相关中文文档：`architecture_docs/zh-CN/features/torchlight/loot/ARCHITECTURE.md`。

## 1. 项目概览
Python 3.11+、PySide6、OpenCV、NumPy 与 C#/.NET 服务组成的桌面自动化工作台。Python 进程提供建图、定位、路径、事件、跟随、UI 和设备适配；C# Host 提供双虚拟 Xbox 输出，独立 LAN 库提供认证同步。源码开发默认把可写数据放在 `data/`，安装态由 `AUTO_MODULES_DATA_DIR` 指向 `%LOCALAPPDATA%/AutoModules/Workbench`。关键约束：定位截图、地图全局坐标、主画面物理坐标、控制器来源和远端设备会话必须显式区分；真实输入和网络同步只能由专用 adapter/service 在明确启动后执行。

## 2. 目录结构图
```text
main.py - 源码/安装态薄启动器，只委托 bootstrap。
pyproject.toml - `src` package、setuptools 和 pytest 导入/发现配置。
src/auto_modules/paths.py - 统一 repository/resources/data 路径和环境变量覆盖。
src/auto_modules/core/ - 通用算法、状态机、领域模型、任务和 action contracts。
src/auto_modules/application/ - event workbench、follow 和 workflow 应用编排。
src/auto_modules/adapters/ - 输入、Windows、OCR、Host、虚拟手柄和平台实现。
src/auto_modules/ui/ - PySide6 工作台、模式、对话框和独立虚拟手柄 UI。
src/auto_modules/bootstrap/ - 输出、日志、DPI、UAC、单实例和 QApplication 装配。
services/virtual_gamepad/ - C# Host、独立启动器、protocol 和测试。
services/lan_input_sync/ - C# LAN 同步库、协议文档和测试。
resources/assets/ - 事件模板、detector 定义和可选模型资源。
resources/defaults/ - 随包默认模板。
data/events/ - 工作区事件定义与路由。
data/maps/ - 地图包、配置、路线和墙体版本。
data/virtual_gamepad/ - 本机控制器 profile。
data/logs/ - 运行日志。
data/diagnostics/ - 生成的诊断输出。
tools/probes/ - 可复用只读/显式执行探针。
tools/debug/ - 算法调试和数据集评估脚本。
tools/virtual_gamepad/ - Host 构建、启动和真实输入 opt-in 探针。
packaging/distribution/ - 离线 payload builder、smoke check 和第三方声明。
packaging/installer/ - 原生 launcher、Inno Setup 和测试。
docs/ - 当前指南、设计计划、架构材料和历史归档。
tests/ - Python 单元、offscreen UI 和 adapter contract 测试。

# 下列逐文件清单保留逻辑简称；按 §0 映射到当前物理路径。
gui/app_context.py - 从 core 系统包初始化共享服务：SquareScreenCapture、HSVRecognizer、MapStitcher、PlayerTracker、PathFinder。
gui/main_window.py - 创建绘图/导航两个模式并共享 AppContext。
gui/navigation_params.py - 定义 NavConfig、RecognizerParams、NavPreferences，并负责 config.json 序列化契约。
gui/composition/__init__.py - GUI composition helper 包入口。
gui/composition/paths.py - GUI 项目根、map_data、根配置和高级参数目录解析 helper。
gui/composition/services.py - GUI 共享 core service DTO 和默认构造工厂。
architecture_docs/zh-CN/gui/GUI_OPTIMIZATION_PLAN.md - GUI 下一阶段结构化优化规划，按 Shell、Navigation、Mapping、Dialogs 分阶段拆分并保留旧入口兼容。
architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md - GUI 全文件级审计与细化拆分规划，覆盖所有 gui 实现文件并给出每个文件的保留、加深、迁移或拆分动作。
architecture_docs/zh-CN/OPTIMIZATION_EXECUTION_BASELINE.md - core/gui 后续工程化优化执行基准，定义剩余任务、每轮流程、验证命令和阶段结束标准。
gui/dialogs/nav_params_dialog.py - 导航参数 UI，按定位识别/算法/移动/路径/调试分页，使用 widget_map 将控件变化写回 NavConfig。
gui/dialogs/nav_params/__init__.py - 导航参数 helper 包入口。
gui/dialogs/nav_params/field_specs.py - 导航参数可编辑字段规格表，描述控件属性名、配置路径、写入方式和分组。
gui/dialogs/nav_params/config_binding.py - 导航参数 `NavConfig` 字段绑定、文本解析、dataclass replace 和控件回填 helper。
gui/dialogs/nav_params/screen_estimator.py - 根据校准中心点和屏幕物理边界估算安全点击半径。
gui/dialogs/event_manager_dialog.py - 独立事件管理窗口，提供事件配置页和 Hooks 配置页。
gui/dialogs/event_manager/__init__.py - 事件管理弹窗支撑包入口。
gui/dialogs/event_manager/hooks/__init__.py - 事件管理 Hooks 面板包入口。
gui/dialogs/event_manager/hooks/panel.py - Hooks 独立页，编辑可注册 hook 实例、按键和触发时机。
gui/dialogs/advanced_settings_dialog.py - 高级参数弹窗主类，组合图像预处理、特征、参数管理和拼接算法 tabs。
gui/dialogs/advanced_settings/__init__.py - 高级参数弹窗 helper 包入口。
gui/dialogs/advanced_settings/file_io.py - 高级参数 JSON snapshot 保存/加载、文件名清洗和显式配置目录 helper。
gui/dialogs/advanced_settings/params_adapter.py - 高级参数弹窗控件与参数 dict/预设之间的映射 helper。
gui/dialogs/advanced_settings/presets.py - 高级参数预设名称顺序和控件值数据表。
gui/dialogs/color_picker_dialog.py - 交互式 HSV 颜色采样弹窗，负责采样点交互、预览显示和 debug 输出调度。
gui/dialogs/color_picker/__init__.py - 颜色选择弹窗 helper 包入口。
gui/dialogs/color_picker/debug_output.py - 颜色选择预览 debug 图片/日志输出 helper，并通过环境变量控制是否落盘。
gui/dialogs/color_picker/hsv_ranges.py - 颜色选择弹窗 HSV 转换、采样值提取和范围计算 helper。
gui/dialogs/color_picker/image_renderer.py - 颜色选择弹窗 OpenCV 图像转 QPixmap 和采样点 marker 绘制 helper。
gui/dialogs/color_picker/preview.py - 颜色选择弹窗 wall HSV preview mask、形态学处理和统计结果 helper。
gui/widgets/clickable_label.py - 可点击图像标签，负责显示坐标到原始图像坐标的转换。
gui/widgets/scalable_map.py - 可缩放/拖拽地图显示 widget，并在非拖拽点击时 emit 原图坐标 `pixel_clicked`。
gui/widgets/aspect_preview.py - 保存原始 QPixmap、随控件尺寸变化重绘的等比例预览标签。
gui/widgets/collapsible_group.py - 带缩放按钮的可折叠地图组。
gui/modes/navigation/__init__.py - 导航模式包入口，导出新的 canonical `NavigationModeWidget`。
gui/modes/navigation/widget.py - 导航模式 QWidget 组合根和临时 facade，负责创建生命周期对象并调用 UI builder/signal binder；旧长 docstring 已压缩为 wrapper 级说明。
gui/modes/navigation/composition/__init__.py - 导航局部 composition 包入口，导出 lifecycle 初始化函数。
gui/modes/navigation/composition/lifecycles.py - 导航页 lifecycle/controller wiring 组合模块，按顺序创建 display/config/route/events/map/runtime/calibration lifecycle。
gui/modes/navigation/ui/__init__.py - 导航 UI shell 包入口，导出布局构建和信号绑定 helper。
gui/modes/navigation/ui/layout.py - 导航页顶部工具栏、地图 scene/view、状态栏和 route panel 的控件构建 helper。
gui/modes/navigation/ui/signals.py - 导航页按钮、参数弹窗和事件弹窗的信号绑定 helper。
gui/modes/navigation/display/__init__.py - 导航地图显示生命周期包入口。
gui/modes/navigation/display/lifecycle.py - 导航地图 scene item、route/event overlay、监控框/视野框和上次退出点显示的状态写入 lifecycle。
gui/modes/navigation/event_adapter.py - 导航模式与事件系统之间的轻量桥接 helper。
gui/modes/navigation/input/__init__.py - 导航输入 adapter 包入口。
gui/modes/navigation/input/window_mode.py - 自动输入期间主窗口取消置顶、降低和停止后恢复置顶的状态 adapter。
gui/modes/navigation/input/actions.py - 将 `NavigationIntent` 明确翻译为地图移动或通用 primitive action 的导航组合 DTO。
gui/modes/navigation/input/intent_executor.py - 将 typed 导航组合动作分发到地图空间 `MotionController` 或 primitive action compatibility backend。
gui/modes/navigation/hooks/__init__.py - 导航 hook runtime 注册包入口。
gui/modes/navigation/hooks/registration.py - 将 `event_config.hooks.instances` 注册到 `NavigationTaskController.event_hooks`，并经通用 primitive action backend 执行按键 hook。
gui/modes/navigation/config/__init__.py - 导航配置生命周期包入口。
gui/modes/navigation/config/lifecycle.py - 导航配置参数变化、runtime 应用、当前地图保存、默认保存和反馈顺序的状态 facade。
gui/modes/navigation/map/__init__.py - 导航地图/config adapter 包入口。
gui/modes/navigation/map/click_lifecycle.py - 导航地图点击生命周期 facade，编排 hint、route 编辑和手动移动目标三分支。
gui/modes/navigation/map/session.py - 导航地图加载前置 session helper，封装 map folder 解析、NavConfig 读取、NavigationCore 创建和初始物理中心计算。
gui/modes/navigation/map/load_lifecycle.py - 导航地图加载生命周期 facade，编排缺配置提示、配置应用、参数回填、route/event 初始化、地图渲染和加载完成 UI。
gui/modes/navigation/map/config_applier.py - 将 `NavConfig` 应用到 nav_core、PathFinder、MotionController 和 NavigationTaskController。
gui/modes/navigation/map/event_filter.py - Qt scene 鼠标事件解释 helper，转发左键地图点击。
gui/modes/navigation/map/config_store.py - 导航地图目录、NavConfig JSON 读写、默认配置 fallback 和 merge 保存真实实现。
gui/modes/navigation/map/capture_geometry.py - 导航截图 logical/physical 中心换算和 capture rect/player pos 几何真实实现。
gui/modes/navigation/calibration/__init__.py - 导航校准 helper 包入口。
gui/modes/navigation/calibration/lifecycle.py - 屏幕中心校准生命周期 facade，编排选择器启动、物理坐标写回、参数回填、overlay 刷新、配置保存和完成反馈。
gui/modes/navigation/calibration/screen_center.py - 屏幕中心校准选择器生命周期和逻辑坐标到物理坐标转换 helper。
gui/modes/navigation/route/__init__.py - 导航 route editing adapter 包入口。
gui/modes/navigation/route/editor.py - 导航 route click mode 和 route.json 编辑命令 adapter。
gui/modes/navigation/route/lifecycle.py - 导航 route 命令生命周期 facade，同步 route_data、NavigationTaskController、overlay 和状态栏反馈。
gui/modes/navigation/route/panel_controller.py - 导航 route 按钮状态、状态栏文案和 route editor 命令结果 controller。
gui/modes/navigation/events/__init__.py - 导航事件 UI adapter 包入口。
gui/modes/navigation/events/bootstrap.py - 地图加载后的事件系统 runtime 初始化。
gui/modes/navigation/events/dialog_lifecycle.py - 事件管理弹窗创建、接线、刷新和显示切换生命周期。
gui/modes/navigation/events/manual_test_controller.py - 手动事件测试按钮状态控制器。
gui/modes/navigation/events/lifecycle.py - 导航事件生命周期 facade，编排事件配置保存、portal 状态重置和手动事件测试启停。
gui/modes/navigation/events/panel_adapter.py - 事件管理窗口创建、信号重连、上下文刷新和配置摘要 adapter。
gui/modes/navigation/presentation/__init__.py - 导航 presentation helper 包入口。
gui/modes/navigation/presentation/calibration_feedback.py - 初始位置提示、hint mode 和屏幕中心校准完成反馈 helper。
gui/modes/navigation/presentation/config_save_state.py - 导航参数保存/默认配置保存结果的状态标签和 QMessageBox helper。
gui/modes/navigation/presentation/event_management_state.py - 事件管理保存、传送门状态重置和手动测试反馈的状态标签与 QMessageBox helper。
gui/modes/navigation/presentation/navigation_command_state.py - 自动导航和导航启动/停止命令的状态标签与 QMessageBox helper。
gui/modes/navigation/presentation/route_command_state.py - route 命令结果、路线保存失败和移动目标反馈的状态标签与 QMessageBox helper。
gui/modes/navigation/presentation/map_presenter.py - 导航地图 scene item 创建、定位显示、玩家/目标/提示点/视野框更新 presenter。
gui/modes/navigation/presentation/map_load_state.py - 导航地图列表 combo、地图加载成功 UI 状态和地图/overlay 加载反馈 helper。
gui/modes/navigation/presentation/dialog_host.py - 导航 owned dialog 显示、置顶、恢复最小化和重复点击隐藏判定 helper。
gui/modes/navigation/presentation/debug_overlay.py - 导航 debug 幕布窗口的几何写入、隐藏和显示 helper。
gui/modes/navigation/presentation/route_overlay.py - 导航路线、出口、必经点、途经点、当前路径和子目标 overlay 绘制真实实现。
gui/modes/navigation/presentation/event_overlay.py - 导航事件 marker overlay 绘制和事件 overlay item 清理真实实现。
gui/modes/navigation/presentation/status_presenter.py - 导航循环状态栏文案构造、写入和后缀追加 helper。
gui/modes/navigation/presentation/viewport_overlay.py - 导航屏幕幕布、监控绿框、真实主画面橙框的矩形计算真实实现。
gui/modes/navigation/runtime/__init__.py - 导航 runtime helper 包入口。
gui/modes/navigation/runtime/command_lifecycle.py - 导航运行命令生命周期 facade，编排导航启动/停止、自动导航开关、timer/motion/task/input-window 状态和按钮回滚。
gui/modes/navigation/runtime/frame_loop.py - 导航定时器单帧 runtime facade，编排截图定位、事件观测、任务更新、展示刷新和 intent 消费。
gui/modes/navigation/runtime/minimap_sample_capture.py - 小地图监视区域样本采集 helper，保存 PNG 截图和同名 JSON 元数据。
gui/modes/navigation/runtime/models.py - 导航循环定位结果 DTO。
gui/modes/navigation/runtime/intent_consumption.py - 导航 intent 消费编排 helper，串联重定位短路、真实输入执行、手动事件测试停止和终态收束。
gui/modes/navigation/runtime/localization_tick.py - 导航单帧截图、玩家局部坐标解析和定位结果构造 helper。
gui/modes/navigation/runtime/loop_helpers.py - 导航循环 lookahead 和任务运行开关纯 helper。
gui/modes/navigation/runtime/loop.py - 导航循环玩家局部坐标解析、事件观测和 NavigationUpdateContext 组装 helper。
gui/modes/navigation/runtime/relocalization_intent.py - 导航 force-relocalize intent 的全局重定位请求、事件日志和状态展示 helper。
gui/modes/navigation/runtime/terminal_intent.py - 导航终态 intent 收束 helper，封装 ARRIVED/FAILED 的任务停止、输入窗口恢复、按钮复位和终态展示回调顺序。
gui/modes/mapping_widget.py - 绘图模式主 UI、截图建图循环、地图显示和参数控件同步。
gui/modes/mapping/__init__.py - 绘图模式拆分 helper 包入口。
gui/modes/mapping/ui/__init__.py - 绘图模式 UI 构建包入口。
gui/modes/mapping/ui/layout.py - 绘图模式控制面板、显示面板和控件信号连接构建 helper。
gui/modes/mapping/capture/__init__.py - 绘图模式 capture selection 包入口。
gui/modes/mapping/capture/selection_controller.py - 绘图模式区域/中心点选择 overlay 生命周期和 monitor 配置写回 controller。
gui/modes/mapping/runtime/__init__.py - 绘图模式 runtime 包入口。
gui/modes/mapping/runtime/lifecycle.py - 绘图模式监控启动/停止、capture timer 和 monitoring 状态 lifecycle。
gui/modes/mapping/runtime/models.py - 绘图模式单帧 tick 结果 DTO。
gui/modes/mapping/runtime/session.py - 绘图模式单帧 capture-recognize-stitch 主流程 session。
gui/modes/mapping/presentation/__init__.py - 绘图模式 presentation 包入口。
gui/modes/mapping/presentation/map_presenter.py - 绘图模式 capture/global map display 写入 presenter。
gui/modes/mapping/map_renderer.py - 绘图模式 BGR/QPixmap 转换和全局地图 overlay 绘制 helper。
gui/modes/mapping/params/__init__.py - 绘图模式 params binding 包入口。
gui/modes/mapping/params/binding.py - 绘图模式参数控件与 recognizer/stitcher 运行时参数之间的桥接 helper。
gui/modes/mapping/io/__init__.py - 绘图模式 IO helper 包入口。
gui/modes/mapping/io/config_store.py - 绘图模式项目路径、map_data 目录、config.json 读写和 mapping config payload 构造 helper。
gui/modes/mapping/io/config_restore.py - 绘图模式启动配置恢复编排，负责根配置读取、AppContext 写回、capture selection 恢复和 Qt 控件同步。
gui/modes/mapping/io/map_save.py - 绘图模式保存地图包和地图级 config 的 IO 编排 helper。
gui/modes/events/__init__.py - 事件工作台 GUI 包入口，导出 `EventWorkbenchPage`。
gui/modes/events/action_sequence_editor.py - 通用声明式动作序列与并行轨道编辑器，不含 Torchlight 角色策略。
gui/modes/events/workbench.py - 事件定义、路由、运行状态和远程发送的 Qt 展示/编辑适配器；仅依赖 `EventWorkbenchService`，不直接读写 JSON 或访问 Host/LAN。
gui/modes/torchlight/__init__.py - Torchlight UI 模式公共入口。
gui/modes/torchlight/navigation.py - Torchlight 导航 UI 组合，注入事件 registry 工厂、游戏窗口查找器和 Loot 调试 overlay provider。
gui/modes/torchlight/follow/__init__.py - Torchlight Follow 页面入口。
gui/modes/torchlight/follow/editors.py - Torchlight 角色识别/手柄映射编辑器，并重导出通用序列编辑器供 Follow 页面使用。
gui/modes/torchlight/follow/page.py - Torchlight Follow 配置、地图/ROI、角色、事件链和运行诊断页面。
core/routing/__init__.py - 路径规划系统包入口，聚合 obstacles/pathfinder/geometry/anchors/route_repository，并公开 `LaggedTrajectoryTarget`。
core/routing/contact_evidence.py - 游戏无关的命令—位移接触证据与连续无进展恢复门；不读取屏幕、不发送输入。
core/routing/obstacles.py - 从原始 wall_layer 派生 A* 专用的宽容障碍层，不改变定位用墙图。
core/routing/pathfinder/__init__.py - A* pathfinder package 入口，导出 `PathFinder`。
core/routing/pathfinder/runtime.py - `PathFinder` 真实 class，保留构造参数、`find_path()` 和旧私有 helper wrapper；可选 `clearance_radius/clearance_weight/dead_end_weight` 只影响软代价，不改变硬障碍契约。
core/routing/pathfinder/grid.py - 障碍网格构建、explored map 未知区阻挡、安全边距膨胀、起点附近清障和基于 distance transform/邻域度数的清距与窄路代价图。
core/routing/pathfinder/astar.py - 8 邻接 A* 主循环、禁止斜向穿角、与对角移动一致的 octile 启发式、可选软代价和路径回溯。
core/routing/pathfinder/snap.py - 起点/终点落入障碍时的最近可走格搜索。
 core/routing/pathfinder/coordinates.py - map-space/grid-space 坐标转换和 grid path 转全局路径点；网格尺寸使用 ceil 保留非整除地图边界。
core/routing/geometry.py - 路径平滑、投影、插值、出口区域判断兼容工具；新增 `line_min_clearance()` 对原始墙图/缓存 distance map 做线段最小清距校验；投影/累计长度/插值委托 `routing/route_progress`。
core/routing/trajectory_target.py - 从有序位置轨迹按累计距离选择滞后目标点的通用状态对象。
core/routing/route_progress/__init__.py - 统一折线进度算法包入口，导出 `PolylineProjection`、累计长度、投影和插值 helper。
core/routing/route_progress/models.py - `PolylineProjection` DTO，统一表示投影点、累计 progress、segment index 和偏离距离。
core/routing/route_progress/projection.py - 折线累计长度、点到折线投影和按累计距离插值的权威实现。
core/routing/anchors/__init__.py - 可选软锚点路径规划 package 入口，导出旧 `AnchorPathResult`、规划函数和进度 helper。
core/routing/anchors/models.py - `AnchorPathResult` DTO。
core/routing/anchors/utils.py - anchor 路径点整数化和朝锚点 probe 点计算 helper。
core/routing/anchors/progress.py - anchor 去重、进度 map 和旧 helper wrapper；累计距离/折线投影委托 `routing/route_progress`。
core/routing/anchors/corridor.py - 按 start/target progress 选择前方 ordered guide anchors。
core/routing/anchors/planner.py - anchor_step、anchor_probe、planned 三类路径规划主流程。
core/routing/route_repository.py - `route.json` 读写、出口/必经点/途经点编辑和内存缓存。
core/input/__init__.py - 输入系统包入口，聚合 motion mapping、点击执行、点击诊断、屏幕边界和 Win32 输入 adapter。
core/input/motion_mapping.py - 纯地图目标到屏幕点击坐标、近目标精确点击和底部禁点投影策略。
core/input/click_executor.py - 真实鼠标点击发送 helper，封装 Win32 mouse_event 后端、pydirectinput 后端和 confirm click。
core/input/click_diagnostics.py - 点击点窗口、前台窗口、ClipCursor 和 Win32 光标位置诊断 helper。
core/input/click_pipeline.py - `MotionController._execute_click()` 的点击流程编排 helper，维护 bottom guard、clamp、诊断、发送、fallback 顺序。
core/input/screen_bounds.py - 屏幕高度读取和可选点击坐标 clamp helper。
core/input/win32_driver.py - Win32 输入 adapter，封装鼠标移动/点击、窗口描述、前台窗口和光标裁剪查询。
core/actions/__init__.py - 设备无关动作契约和鼠标 adapter 的公共入口。
core/actions/models.py - `ActionKind`、`ActionRequest`、`ActionResult` 不可变动作 DTO。
core/actions/mouse.py - 仅消费物理映射点的鼠标移动/双击 adapter 与最小设备协议。
core/actions/gamepad_motion.py - 与设备和游戏无关的 `StickSlewLimiter`，按最大变化率平滑两轴摇杆目标并支持立即回中；供手柄动作策略组合使用。
virtual_gamepad/host/src/VirtualGamepadHost/Protocol/NamedPipeServer.cs - 当前并行开发中的 Windows 当前用户 JSON-lines 命名管道服务；每个连接独立顺序处理请求，允许 UI 与自动化客户端并存。
virtual_gamepad/host/src/VirtualGamepadHost/Protocol/CommandRouter.cs - 按 controller 1/2 路由主机协议命令、解析 actuator payload，并把格式/参数错误转换成协议失败响应。
virtual_gamepad/host/src/VirtualGamepadHost/State/StateStore.cs - 每手柄独立的线程安全输入源仲裁：按钮 OR、扳机取最大、摇杆取最大绝对值/最新值，并在快照时移除超时源。
virtual_gamepad/host/src/VirtualGamepadHost/State/SafetyController.cs - 每手柄运行/暂停/复位/故障状态机；紧急复位清源并暂停。
virtual_gamepad/host/src/VirtualGamepadHost/Runtime/ControllerRegistry.cs - 强制持有 1、2 两个合法槽位并向 ViGEm XInput backend 提交各自快照；提供全局紧急复位。
virtual_gamepad/host/src/VirtualGamepadHost/Runtime/HostComposition.cs - 组装 ViGEm、两槽位、125Hz report loop、物理输入捕获与管道服务；把物理输入广播给所有 Running 槽位。
virtual_gamepad/client/python/virtual_gamepad_client.py - 命名管道 Python 客户端；以单锁保证一个 client 的请求/响应配对，暴露按 controller 选择的状态、映射和原始手柄命令。
virtual_gamepad/ui/virtual_gamepad_ui/main_window.py - 两个独立 profile 的切换式 PySide 映射编辑器，展示 C1/C2 状态并将开始/暂停操作作用于选中的槽位。
core/input/motion_controller/__init__.py - MotionController helper package 入口，聚合 controls、targets 和 backend helper。
core/input/motion_controller/controls.py - MotionController 参数设置、control enablement、显式屏幕点击和按键 helper。
core/input/motion_controller/targets.py - MotionController 普通移动点击、事件精确地图点击、目标屏幕坐标计算和 bottom guard wrapper。
core/input/motion_controller/backend.py - MotionController lazy InputDriver、screen clamp、pydirectinput 安全调用、点击发送和窗口信息格式化 wrapper。
core/platform/__init__.py - 平台适配包入口。
core/platform/desktop_frame_source.py - Windows 主显示器默认 / 显式虚拟桌面物理几何读取、DPI awareness bootstrap 和显示区域 FrameContext source。
core/platform/screen_capture.py - mss/PIL 屏幕截图 adapter，正式导出 `SquareScreenCapture`。
workflows/__init__.py - 只组合通用模块、不持有具体算法实现的应用 workflow 包入口。
workflows/desktop_ocr_action_proof.py - OCR 文字到映射物理鼠标双击的安全桌面 proof workflow。
utils/run_desktop_ocr_action_proof.py - 可重复执行的 dry-run / live desktop proof CLI，输出完整 JSON 诊断。
core/vision/__init__.py - 图像识别和追踪包入口。
core/vision/hsv_recognizer.py - HSV/wall/fog/player 特征提取器 facade，保留 `HSVRecognizer` 旧类入口。
core/vision/hsv/__init__.py - HSV recognizer 子模块入口，聚合参数、预处理、mask 和 combined pipeline helper。
core/vision/hsv/params.py - `HSVRecognizer` 参数快照和局部应用 helper。
core/vision/hsv/preprocessing.py - wall/fog 预处理、透明地图 score 和 raw gray matching helper。
core/vision/hsv/masks.py - wall/fog/player mask 提取和小连通域过滤 helper。
core/vision/hsv/combined.py - `extract_combined()` 的动态颜色过滤、中心清理和 weighted match mask 组合 helper。
core/vision/player_tracker.py - 玩家局部位置检测和轨迹绘制实现。
core/vision/phase_displacement.py - phase-correlation 位移估计 helper。
core/shared/__init__.py - core 跨系统共享契约包入口。
core/shared/frame_registration.py - 定位和事件系统共享的帧配准契约。
core/shared/diagnostics/__init__.py - 跨系统诊断纯格式化 helper 包入口。
core/shared/diagnostics/formatting.py - 共享 `format_value()`、`format_fields()`，供事件日志和坐标诊断日志复用。
core/mapping/__init__.py - 建图系统包入口，聚合 `MapStitcher`、地图包 IO、帧流程、融合和渲染 helper。
core/mapping/stitcher.py - `MapStitcher` 真实实现，维护 wall/fog/explored/current_pos/keyframe 状态并委托 mapping helper。
core/mapping/package_io.py - `MapStitcher` 的 `map_data.npz` 保存/加载 helper。
core/mapping/performance.py - `MapStitcher` 的性能计时器和 rolling timing 记录 helper。
core/mapping/frame_preparation.py - `MapStitcher` 的帧 mask 缩放、墙体厚度标准化、重复帧相似度和画布边界计算 helper。
core/mapping/frame_pipeline.py - `MapStitcher.add_frame()` 的 keyframe/F2F 配准、低质量跳过、落图和统计更新流程 helper。
core/mapping/weighted_merge.py - `MapStitcher` weighted frame merge helper，更新 wall/fog/explored/canvas layers。
core/mapping/rendering.py - `MapStitcher` cropped/enhanced map display rendering helper。
core/localization/__init__.py - 导航定位系统包入口，聚合 `NavigationCore`、`LocalizationResult` 和定位 helper。
core/localization/bounded_observation.py - 按 identity 独立维护最后可信坐标、观测年龄、不确定性与重现确认的通用纯状态。
core/localization/canonical_wall.py - 通用 wall mask 与 walkable/explored boundary 的二值形状归一化。
core/localization/displacement.py - 通用相似变换位移向量转换，按 OpenCV 图像坐标处理旋转、镜像和比例。
core/localization/frame_displacement.py - 通用 phase-correlation 位移估计结果和质量/跳变门控。
core/localization/navigation_core/__init__.py - NavigationCore 运行时包入口。
core/localization/navigation_core/runtime.py - `NavigationCore` 真实 class，保留旧 tuple `localize()` 并提供 typed `localize_result()` facade。
core/localization/navigation_core/state.py - `NavigationCore` 构造期配置、地图路径和运行态字段初始化 helper。
core/localization/navigation_core/registration.py - `NavigationCore.last_frame_registration` 写回 wrapper。
core/localization/navigation_core/relocalization.py - 初始位置提示、强制全图重定位和模板匹配阈值策略 helper。
core/localization/navigation_core/wall_layer.py - 导航墙层派生、墙体闭运算 kernel 和模板标准化 wrapper。
core/localization/navigation_core/diagnostics.py - 定位模板匹配失败的节流日志 helper。
core/localization/map_package.py - `NavigationCore` 的 `map_data.npz` 加载和缺省字段处理 helper。
core/localization/localize_pipeline.py - `NavigationCore.localize()` 的 F2F、模板匹配、强制重定位和状态写入流程 helper。
core/localization/rendering.py - `NavigationCore.get_map_image()` 的显示地图渲染和 crop offset 写入 helper。
core/localization/frame_registration.py - `NavigationCore.last_frame_registration` 的有效/无效配准对象构建 helper。
core/localization/result.py - 单帧定位的核心 typed outcome；将兼容 tuple 和 FrameRegistration provenance 快照为 GLOBAL_MAP 坐标结果。
core/localization/frame_matcher.py - 导航定位模板匹配的墙体模板缩放、闭运算标准化和局部/全图搜索窗口选择 helper。
core/localization/visual_check.py - F2F 跟踪期间的截图-地图视觉一致性复核 helper。
core/localization/evidence/__init__.py - 定位证据包入口，导出 `LocalizationEvidence`、`VisualCheckEvidence` 和 evidence builder。
core/localization/evidence/models.py - 定位证据 DTO，稳定承载 raw/trusted/control 坐标、confidence、registration 字段和 visual check 证据。
core/localization/evidence/builder.py - 从 `FrameRegistration`、raw/trusted/control 坐标和 confidence 构造 `LocalizationEvidence`。
core/navigation_tasks/__init__.py - 统一导航任务控制器包入口。
core/navigation_tasks/update_context.py - `NavigationTaskController` 的 grouped update context/snapshot 数据结构。
core/navigation_tasks/update_pipeline.py - `NavigationTaskController.update_context()` 的统一调度流程 helper。
core/navigation_tasks/controller_utils.py - 导航任务控制器共享坐标格式化和 forced relocalization 判定 helper。
core/navigation_tasks/static_task_runner.py - required/exit 静态任务 runner。
core/navigation_tasks/event_task_runner.py - event 任务 runner，衔接 event approach、EventCoordinator 和 NavigationIntent。
core/navigation_tasks/intent_factory.py - 将 MovementStep/EventAction 转换为 NavigationIntent 的 helper。
core/navigation_tasks/models.py - required/exit/event 统一任务、移动步骤和动作意图数据模型。
core/navigation_tasks/route_context.py - 用户辅助锚点路线上下文，保留 `RouteContext` API；折线投影和累计进度委托 `routing/route_progress`。
core/navigation_tasks/controller_runtime/__init__.py - NavigationTaskController runtime helper package 入口，聚合生命周期、定位、required progress 和重定位 intent helper。
core/navigation_tasks/controller_runtime/lifecycle.py - `NavigationTaskController` 路线加载、runtime reset、start/stop、route validity 和 intent click 记录 helper。
core/navigation_tasks/controller_runtime/localization.py - `observe_localization()` 的 raw/trusted/control position 更新、jump reject 和 route progress 单调推进 helper。
core/navigation_tasks/controller_runtime/progress.py - required point 下一目标查找、到达判定、完成记录和 movement reset helper。
core/navigation_tasks/controller_runtime/relocalization.py - 坐标诊断恢复请求消费、WAIT intent 构造和 movement reset helper。
core/navigation_tasks/movement_executor.py - 普通路线和事件目标共用移动执行器 facade，保留 `MovementExecutor` 和旧私有方法入口。
core/navigation_tasks/movement/__init__.py - movement 子模块入口，聚合路径维护、规划、恢复和工具函数。
core/navigation_tasks/movement/pipeline.py - `MovementExecutor.step()` 的路径复用、lookahead 子目标、点击节流和卡住恢复编排 helper。
core/navigation_tasks/movement/path_maintenance.py - movement 路径是否重规划、路径状态写入和规划日志 helper。
core/navigation_tasks/movement/path_planner.py - movement A*、guide anchor、fallback probe 路径规划 helper。
core/navigation_tasks/movement/recovery.py - movement 本地探测、卡住判定和恢复探测点计算 helper。
core/navigation_tasks/movement/utils.py - movement 坐标 float/int 标准化 helper。
core/navigation_tasks/task_builder.py - 把 route.json 静态目标和 EventMemory 动态事件任务合并成 NavigationTask 列表。
core/navigation_tasks/scheduler.py - 在 required、exit、event 中选择当前应处理任务。
core/navigation_tasks/controller.py - 统一导航任务控制器，输出 MOVE_MAP/CLICK_SCREEN/PRESS_KEY/ARRIVED/FAILED 意图。
core/navigation_tasks/coordinate/__init__.py - coordinate diagnostics 子模块入口，聚合 `CoordinateDiagnostics`、请求 DTO、日志、定位/导航诊断和重定位生命周期。
core/navigation_tasks/coordinate/diagnostics.py - `CoordinateDiagnostics` 真实 stateful facade，保留旧 public/private 方法并委托 coordinate helper。
core/navigation_tasks/coordinate/models.py - 坐标重定位请求 DTO。
core/navigation_tasks/coordinate/formatting.py - 坐标诊断的 registration 字段提取兼容入口、坐标标准化、距离和日志字段格式化 helper；registration/point 标准化委托 localization evidence，字段/值格式化委托 shared diagnostics。
core/navigation_tasks/coordinate/log.py - `logs/coordinate_diagnostics.log` 文件日志 writer。
core/navigation_tasks/coordinate/localization.py - 定位帧诊断、F2F 来源跟踪和 visual mismatch 证据记录 helper；内部消费 `LocalizationEvidence`，旧 `record_localization_diagnostics()` 签名保留。
core/navigation_tasks/coordinate/navigation.py - 任务目标、路线偏差、到达不一致和近目标停滞诊断 helper。
core/navigation_tasks/coordinate/relocalization.py - 坐标强制重定位请求生成、消费、接受和拒绝生命周期 helper。
core/navigation_tasks/event_approach/__init__.py - 事件靠近/停稳 gate facade package，保留 `EventApproachController` 和旧私有 helper 入口。
core/navigation_tasks/event_approach/models.py - 事件靠近 gate 的配置和结果 DTO。
core/navigation_tasks/event_approach/geometry.py - 事件真实视野判定、路径停靠点计算和坐标标准化 helper。
core/navigation_tasks/event_approach/motion.py - 事件靠近阶段 movement step 到 NavigationIntent 的转换 helper。
core/navigation_tasks/event_approach/settle.py - 事件触发前停稳计时、稳定帧判断和 settling intent helper。
core/navigation_tasks/event_approach/pipeline.py - `EventApproachController.update()` 的 far/approach/settling/ready 主流程 helper。
core/navigation_tasks/debug.py - 将导航任务日志写入事件运行日志。
architecture_docs/zh-CN/core/FACADE_EXTRACTION_METHOD.md - core facade 逐步抽取方法论，说明旧入口保留、分类 helper、pipeline helper 和每轮验证流程。
core/input/controller.py - `MotionController` 正式类入口，拥有输入控制运行态并委托 motion_controller helper 包。
core/input/action_adapter.py - 通用 primitive `ActionCommand` 到现有 `MotionController` 点击/按键策略的兼容 backend adapter。
core/events/automation/__init__.py - 通用动作事件定义、路由和执行能力的稳定导出入口。
core/events/automation/action_sequence.py - 游戏无关的有界声明式动作序列校验和 tick 驱动执行器。
core/events/automation/definitions.py - 本机/远程共用的事件定义解析、稳定身份、revision、owner、tombstone 和目录解析仓库。
core/events/automation/routes.py - 中英文旧路由值规范化、路由文件仓库和无副作用 trigger-to-dispatch 决策。
core/events/automation/execution.py - 按 `(source, controller)` 隔离的本机/远程共享事件执行器，输出完整 XInput 状态帧。
core/runtime/event_service/__init__.py - 事件工作台服务与平台适配器的公共入口。
core/runtime/event_service/models.py - 热键来源、Host bridge Protocol 与不可变工作台状态契约。
core/runtime/event_service/host_bridge.py - 唯一 `event.*` / `sync.share.*` Host/LAN 命令适配器。
core/runtime/event_service/hotkeys.py - 可注入读取器的 Win32 热键按下边沿适配器。
core/runtime/event_service/service.py - 本机触发、A->B/C 广播、远程接收、目录同步、状态输出和生命周期的单一组合根。
core/events/models.py - 事件系统通用数据结构和动作类型。
core/events/config.py - 事件配置兼容 facade，re-export 配置模型、IO 和 TUI 事件选项输出。
core/events/config_model.py - 游戏无关的 `EventSystemConfig`、全局事件运行时默认值和 deep merge；具体事件默认值不在 core。
core/events/config_schema.py - 复制事件配置 schema，并校验/标注通用 `compact`、`summary` 展示提示。
core/events/config_io.py - 地图级 `event_config.json` 路径、加载和保存。
core/events/registry.py - 完整事件包注册表，TUI/Coordinator 只通过它枚举事件。
core/events/hooks/__init__.py - 事件生命周期 hook package 入口，导出 hook 常量、上下文 DTO 和 registry。
core/events/hooks/models.py - `event_visible_target`、`event_completed` 常量、中文标签和 `EventHookContext` payload。
core/events/hooks/registry.py - 同步 no-op-by-default hook registry，支持注册、注销、清空和异常隔离派发。
core/events/hooks/instances/__init__.py - 具体 hook 实例包入口。
core/events/hooks/instances/key_press.py - 可配置按键 hook 实例，接收输入回调并按一次自定义按键。
core/events/coordinator/__init__.py - EventCoordinator 旧路径 package 入口，导出 `EventCoordinator`。
core/events/coordinator/runtime.py - `EventCoordinator` 真实 stateful facade，持有 registry/config/memory/monitor/stabilizer/scheduler/runner。
core/events/coordinator/observation.py - `EventCoordinator.observe()` 的 detect、position stabilize、memory merge 和 display task selection 流程 helper。
core/events/coordinator/task_run.py - `EventCoordinator.run_task()` 的 task 查找、runner 委托和 action 记录 helper。
core/events/coordinator/reset.py - `EventCoordinator.reset_event_type()` 的 handler/memory/cluster/cache 清理 helper。
core/events/coordinator/presentation.py - `EventCoordinator.overlays()` 和 `status_summary()` 的 overlay/status DTO helper。
core/events/coordinator/filters.py - coordinator event enabled 过滤、active/display task 过滤和日志节流 helper。
core/events/memory/__init__.py - 事件实例生命周期 facade package，保留 `EventMemory` public API 和旧私有 helper wrapper。
core/events/memory/merge.py - stable observations 合并为 EventTask、确认帧和创建/seen 日志 helper。
core/events/memory/lookup.py - EventMemory 任务查找、dedupe、出口任务匹配和完成冷却判定 helper。
core/events/memory/completion.py - EventMemory 完成、传送会话、相关任务完成、附近任务抑制和失败重试/忽略 helper。
core/events/memory/utils.py - EventMemory 距离、坐标标准化和日志节流 helper。
core/events/monitor.py - 调用启用事件的 detector，并缓存 detector 避免每帧重载模板。
core/events/scheduler.py - 在 pending/running 事件中选择当前处理任务。
core/events/runner.py - 启动事件 handler 并根据 COMPLETE/FAIL 更新 memory。
core/events/position_stabilizer/__init__.py - 事件位置稳定 package 入口，保留 `EventPositionStabilizer`、`_PositionCluster`、`_PositionSample` 旧导出。
core/events/position_stabilizer/runtime.py - 事件位置稳定 facade，保留 `update()`、`clear_event_type()` 和旧私有 wrapper。
core/events/position_stabilizer/models.py - 事件位置稳定采样和聚类 DTO，并计算加权中心、方差和置信度。
core/events/position_stabilizer/projection.py - 把局部小地图事件候选按帧配准 origin/draw_scale 投影到全局地图坐标。
core/events/position_stabilizer/clusters.py - 事件候选跨帧聚类、同帧隔离、样本裁剪和过期 cluster 清理 helper。
core/events/position_stabilizer/observations.py - 将满足样本数、方差和发射间隔 gate 的 cluster 转成稳定 `EventObservation`。
core/events/debug/__init__.py - 事件诊断日志旧路径 package 入口，导出 `event_log()`、`start_event_log_session()`、`describe_action()` 和 `describe_task()`。
core/events/debug/writer.py - 事件日志 session、`logs/event_runtime.log`、per-run/per-topic 文件写入和 `[Event ... pid=...]` 行构造。
core/events/debug/topics.py - 根据 event/task/message 推断 portal/navigation/localization topic 并清洗 topic 文件名。
core/events/debug/descriptions.py - EventAction/EventTask 的紧凑运行日志描述格式化。
core/events/debug/formatting.py - 事件日志字段和值格式化兼容 helper，委托 shared diagnostics 并保留旧私有函数名。
core/events/capture_provider.py - 为事件 handler 提供小地图/主画面截图来源。
core/events/window_finder.py - Windows 游戏窗口枚举、DPI awareness 和窗口矩形获取。
adapters/windows/window_finder.py - 通用 Win32 窗口发现、进程窗口句柄、前台 PID 门禁；只读查询，不聚焦窗口、不移动鼠标。
core/events/detectors/template_matcher.py - 多模板、多尺度图标匹配通用工具。
core/events/perception_adapter.py - 将 legacy `EventDetection` 与通用 `TargetDetection(MINIMAP)` 纯转换、反向转换和批量归一化；不包含 Portal/Loot 算法或事件策略。
features/__init__.py - 游戏业务域根包，不聚合具体游戏 API。
features/torchlight/__init__.py - Torchlight 业务域根包，避免导入时启动运行时副作用。
features/torchlight/composition.py - Portal/Loot 事件定义的 Torchlight 组合入口，接受已有通用注册表或创建新注册表。
features/torchlight/skills/__init__.py - Torchlight skill facade 公共入口。
features/torchlight/skills/follow_chain.py - 将通用 `ActionSequenceDefinition` 命名为 Torchlight skill/follow chain，不复制执行算法。
features/torchlight/follow/__init__.py - Torchlight 自动跟随公共 API。
features/torchlight/follow/config.py - Torchlight 跟随角色、地图、识别、事件链和快捷键配置与版本存储。
features/torchlight/follow/controller.py - 单角色跟随控制策略，组合目标轨迹、FollowerPlanner 和运动决策。
features/torchlight/follow/planner.py - Torchlight 跟随路径缓存和多尺度 A* 策略；通用 A*/几何仍由 core 提供。
features/torchlight/follow/dual_session.py - A 端多角色跟随/事件抢占会话状态机。
features/torchlight/follow/resources.py - Torchlight follow 地图包读取和通用导航引用构造。
features/torchlight/follow/service.py - Torchlight follow 进程、热键、通信与生命周期组合根。
features/torchlight/follow/workers.py - 每角色视觉、规划和输出 worker；真实设备只在显式启动后连接。
features/torchlight/follow/replay.py - Torchlight follow 录制、离线回放和耗时摘要。
features/torchlight/follow/benchmark.py - Torchlight follow 专用基准入口。
features/torchlight/portal/definition.py - `portal` 完整事件包对外定义。
features/torchlight/portal/minimap_detector.py - 传送门小地图图标 detector facade，持有 `PortalMinimapDetector`、模板缓存、feature signature 和日志节流状态。
features/torchlight/portal/minimap_detection/__init__.py - portal minimap detector helper package 入口，聚合 mode、诊断和 hit 转换 helper。
features/torchlight/portal/minimap_detection/modes.py - portal minimap detector mode 选择、feature template 刷新、template/feature/shape-color 命中调用和 shape-color 参数构造。
features/torchlight/portal/minimap_detection/diagnostics.py - portal minimap detector skipped/no-hit/rejected/best-hit 运行日志 helper，集中维护日志节流写法。
features/torchlight/portal/minimap_detection/conversion.py - portal minimap hit 颜色过滤、EventDetection 构造和 metadata 字段填充 helper。
features/torchlight/portal/minimap_feature_matcher/__init__.py - 传送门小地图蓝色本体特征匹配器 package 入口，保留旧 public/private helper 导出。
features/torchlight/portal/minimap_feature_matcher/models.py - `PortalFeatureTemplate`、`PortalFeatureHit` DTO 和 hit center 计算。
features/torchlight/portal/minimap_feature_matcher/masks.py - HSV 蓝/青色 portal body 二值 mask 提取。
features/torchlight/portal/minimap_feature_matcher/templates.py - 从通用 `TemplateSpec` 构建 portal 蓝色本体 feature templates。
features/torchlight/portal/minimap_feature_matcher/response.py - 多尺度 mask resize 和响应图局部峰值提取 helper。
features/torchlight/portal/minimap_feature_matcher/pipeline.py - portal feature matcher 主流程、候选评分和近邻 hit 合并。
features/torchlight/portal/minimap_hit_filter.py - 传送门小地图 hit 的蓝色像素接受过滤 helper。
features/torchlight/portal/minimap_shape_color/__init__.py - shape-color matcher 子模块入口，聚合 DTO、mask、模板准备、评分和主流程。
features/torchlight/portal/minimap_shape_color/models.py - shape-color matcher 参数、命中、debug mask 和 prepared template DTO。
features/torchlight/portal/minimap_shape_color/masks.py - shape-color matcher 的蓝色核心/外环 mask、缩放和 BGR/HSV 转换 helper。
features/torchlight/portal/minimap_shape_color/templates.py - shape-color matcher 的模板多尺度准备 helper。
features/torchlight/portal/minimap_shape_color/scoring/__init__.py - shape-color scoring package 入口，保留原 scoring 函数导出。
features/torchlight/portal/minimap_shape_color/scoring/response.py - shape-color matcher 的 mask/color 响应图组合和响应峰值提取 helper。
features/torchlight/portal/minimap_shape_color/scoring/color.py - masked HSV 颜色相似度和 color response map helper。
features/torchlight/portal/minimap_shape_color/scoring/overlap.py - blue/outer/shape/edge mask 的 F1-like overlap 分数 helper。
features/torchlight/portal/minimap_shape_color/scoring/candidate.py - shape-color 候选窗口评分、signature boost 和 reject reason 判定 helper。
features/torchlight/portal/minimap_shape_color/pipeline.py - shape-color matcher 主匹配流程和候选去重 helper。
features/torchlight/portal/main_view_confirmer.py - 传送门主画面蓝紫发光实体 confirmer。
features/torchlight/portal/environment_signature.py - portal 交互前后小地图环境签名和差异计算 helper。
features/torchlight/portal/completion_detector.py - portal teleport 完成判定 helper，覆盖已知出口、位置变化和环境变化。
features/torchlight/portal/handler/__init__.py - portal handler package 入口，只导出 `PortalEventHandler`。
features/torchlight/portal/handler/runtime.py - `PortalEventHandler` facade/state owner，保留 `start()`、`update()`、`reset()` 和 completion wrapper。
features/torchlight/portal/handler/movement.py - portal 到达半径、交互半径和 forced repeat movement action helper。
features/torchlight/portal/handler/interaction.py - portal 点强制点击、点击后等待、按 `D` 交互和交互签名采集 helper。
features/torchlight/portal/handler/completion.py - portal `wait_result` 阶段、completion/fail/wait action 和 relocalize request helper。
features/torchlight/portal/handler/diagnostics.py - portal handler 状态变化和节流日志 helper。
resources/games/torchlight/event_templates/portal/minimap/portal_minimap_01.png - Torchlight 传送门小地图图标模板 1。
resources/games/torchlight/event_templates/portal/minimap/portal_minimap_02.png - Torchlight 传送门小地图图标模板 2。
resources/games/torchlight/event_detectors/portal/main_view/blue_glow_detector_v1.json - Torchlight 大画面传送门蓝紫发光检测参数资产。
resources/games/torchlight/event_detectors/portal/main_view/README.md - Torchlight 大画面传送门检测资产说明和复现命令。
utils/event_icon_probe.py - 独立事件图标探针，用原始小地图截图验证多模板匹配。
utils/portal_screen_probe.py - 独立大画面传送门探针，用游戏窗口截图验证蓝紫发光实体识别。
utils/route_context_probe.py - 离线打印 route.json 中辅助锚点、必经点和出口的路线进度。
utils/navigation_task_probe.py - 离线打印统一导航任务列表，确认 required/exit/event 的投影顺序。
features/poe2/live_terrain/experimental/__init__.py - PoE2 未正式发布实验边界入口。
features/poe2/live_terrain/experimental/hybrid_localization/__init__.py - 混合定位模型、协议、组件和 composition 聚合入口。
features/poe2/live_terrain/experimental/hybrid_localization/models.py - 不可变帧、锚点、相似变换、注册结果和状态 DTO。
features/poe2/live_terrain/experimental/hybrid_localization/contracts.py - 锚点、绝对注册和局部跟踪结构协议。
features/poe2/live_terrain/experimental/hybrid_localization/recovery.py - 每个恢复版本最多消费一次的许可门。
features/poe2/live_terrain/experimental/hybrid_localization/controller.py - 首次/局部/恢复状态机和成功轨迹 owner。
features/poe2/live_terrain/experimental/hybrid_localization/similarity_search.py - 纯数组相似变换 Chamfer 搜索。
features/poe2/live_terrain/experimental/hybrid_localization/absolute_registrar.py - 内存锚点约束的绝对注册和 prior 平移恢复。
features/poe2/live_terrain/experimental/hybrid_localization/memory_anchor.py - PoE2 内存人物位置到定向 reference 锚点适配器。
features/poe2/live_terrain/experimental/hybrid_localization/local_tracker.py - 固定方向/镜像/比例的有界视觉平移跟踪。
features/poe2/live_terrain/experimental/hybrid_localization/session.py - 单帧截图/证据/controller 生命周期和 listener 编排。
features/poe2/live_terrain/experimental/hybrid_localization/composition.py - PoE2 snapshot/profile/recognizer/player source 到实验闭环的装配入口。
features/poe2/live_terrain/experimental/multiplayer_localization/__init__.py - 双人首帧与运动实验的导出入口。
features/poe2/live_terrain/experimental/multiplayer_localization/models.py - 双人候选、颜色配置、身份位置和首帧结果的不可变契约。
features/poe2/live_terrain/experimental/multiplayer_localization/marker_candidates.py - 将 PoE2 颜色观测转成未赋身份的双人候选；先按 bbox IoU/中心距离做轮廓非极大值抑制，再保证不同 profile/identity hint 各保留一个代表，避免同一人物的多轮廓挤掉另一名玩家。
features/poe2/live_terrain/experimental/multiplayer_localization/memory_anchors.py - 两名人物只读内存坐标到 native 地图锚点的实验适配器。
features/poe2/live_terrain/experimental/multiplayer_localization/dual_first_frame.py - 双人共同形状、方向、镜像和两锚点首帧注册。
features/poe2/live_terrain/experimental/multiplayer_localization/experiment.py - 一次性内存锚点、截图和注册的 PoE2 实验组合。
features/poe2/live_terrain/experimental/multiplayer_localization/dual_motion.py - 共享墙体视口位移、独立人物识别、有界纠偏和恢复请求的纯视觉实验状态。
features/poe2/live_terrain/experimental/multiplayer_localization/marker_association.py - 无副作用的动态人物候选关联；按时间、屏幕速度、墙体位移和双角色相对距离计算软成本，颜色只作身份提示。
features/poe2/live_terrain/experimental/multiplayer_localization/occlusion_archive.py - 失明状态切换时限量保存原始小地图、颜色 mask、候选及分配诊断。
features/poe2/live_terrain/experimental/multiplayer_localization/minimap_contact_adapter.py - 将 PoE2 当前 wall mask 和人物屏幕点转换为前方墙体、左右清空度等局部接触证据，不修改墙图。
features/poe2/live_terrain/experimental/multiplayer_follow/__init__.py - PoE2 实验跟随的公开契约导出。
features/poe2/live_terrain/experimental/multiplayer_follow/models.py - 角色、地图实例、位置新鲜度、控制模式与跟随观测 DTO。
features/poe2/live_terrain/experimental/multiplayer_follow/runtime.py - PoE2 实验目标、逐角色状态、0/255 墙图多尺度 A*、目标局部投影、路线长度与清距暴露评分、原图穿墙与最小清距校验，以及六向自由空间探针和无进度侧向恢复。
features/poe2/live_terrain/experimental/multiplayer_follow/target_projection.py - 将落入墙栅格但局部邻域仍可走的目标投影到距离、开放比例和 clearance 综合最优的可行走点，并输出投影状态诊断。
features/poe2/live_terrain/experimental/multiplayer_follow/program_output.py - 跟随观测到显式程序手柄 lease 的实验装配；模拟模式不输出真实输入。
features/poe2/live_terrain/experimental/multiplayer_follow/motion_models.py - 游戏中立的运动观测、命令、反馈、校准状态与阶段 DTO，统一 native 坐标和地图版本契约。
features/poe2/live_terrain/experimental/multiplayer_follow/motion_snapshot.py - 每个控制 tick 的只读墙图、距离场、路线和目标快照；复制数组并执行地图版本校验。
features/poe2/live_terrain/experimental/multiplayer_follow/complexity.py - 按 role 维护局部区域复杂度迟滞；组合清距、可见性、未知区域、路线形状、定位质量和 peer risk。
features/poe2/live_terrain/experimental/multiplayer_follow/motion_calibration.py - 按 role 保存有界 stick→native 递归校准模型；拒绝低位移、方向失配和无效反馈。
features/poe2/live_terrain/experimental/multiplayer_follow/sequential_motion.py - 将命令作为预测、视觉/native 位移作为观测的序贯位置/速度更新适配器。
features/poe2/live_terrain/experimental/multiplayer_follow/closed_loop_controller.py - 通过同一快照组合复杂度、局部控制、序贯反馈与校准；开阔/受限/未知策略切换。
features/poe2/live_terrain/experimental/multiplayer_follow/recovery/__init__.py - 导出跟随恢复状态、诊断和策略基础契约。
features/poe2/live_terrain/experimental/multiplayer_follow/recovery/recovery_state.py - 定义视觉降级、局部/内存/全局重锚和动态保持状态及恢复等级。
features/poe2/live_terrain/experimental/multiplayer_follow/recovery/recovery_diagnostics.py - 保存恢复阶段、帧新鲜度、候选数量、各阶段耗时和 generation 诊断。
features/poe2/live_terrain/experimental/multiplayer_follow/recovery/recovery_coordinator.py - 无副作用地选择最新帧视觉、局部视觉、预测或内存恢复动作并执行冷却判断。
features/poe2/live_terrain/experimental/multiplayer_follow/recovery/local_reanchor.py - 提供局部 ROI 半径和局部评分接受门槛契约；尚未包含实际图像匹配。
features/poe2/live_terrain/experimental/multiplayer_follow/recovery/memory_fast_reanchor.py - 一次读取双角色内存样本，校验地图实例并复用既有坐标 transform；带冷却、数量和二维坐标校验。
features/poe2/live_terrain/experimental/multiplayer_follow/tracking/__init__.py - 跟踪数学模块的包入口。
features/poe2/live_terrain/experimental/multiplayer_follow/tracking/prediction_model.py - 提供视觉速度/命令速度预测和预测观测加权融合纯函数。
features/poe2/live_terrain/experimental/multiframe_localization/__init__.py - 多帧定位实验契约、策略、session、归档和导航适配的稳定导出入口。
features/poe2/live_terrain/experimental/multiframe_localization/models.py - 只读多帧证据、候选区域、位置估计和运动状态 DTO。
features/poe2/live_terrain/experimental/multiframe_localization/motion_gate.py - 基于 canonical wall 和有界 phase displacement 的移动/静止/未知分类与关键帧门。
features/poe2/live_terrain/experimental/multiframe_localization/evidence_window.py - 按帧数、时间和 segment 隔离的有界关键帧窗口及 evidence version owner。
features/poe2/live_terrain/experimental/multiframe_localization/rolling_submap.py - 从当前保留证据确定性重建有限 wall/observed 局部地图，裁剪时保留最新视野。
features/poe2/live_terrain/experimental/multiframe_localization/shape_registration.py - 对墙体粗细和未知区稳健的正反向距离场形状评分与相似变换投影；参考几何缓存持有源数组，防止 NumPy 地址复用串用地图距离场。
features/poe2/live_terrain/experimental/multiframe_localization/registration_validator.py - 锚点、轨迹、留出误差、候选 margin 和 A/B 一致性的独立确认门。
features/poe2/live_terrain/experimental/multiframe_localization/local_corrector.py - 跟踪期在预测位置附近执行有界形状校正，不读内存、不做整图搜索。
features/poe2/live_terrain/experimental/multiframe_localization/strategy_a.py - 累计拼图达到结构阈值后注册，并用独立留出帧验证的方案 A。
features/poe2/live_terrain/experimental/multiframe_localization/strategy_b.py - 方向/镜像/比例多候选的多帧联合评分、basin 去重和 margin 确认方案 B。
features/poe2/live_terrain/experimental/multiframe_localization/state_estimator.py - 已确认候选内部的位置/速度预测、Mahalanobis 观测门和协方差更新。
features/poe2/live_terrain/experimental/multiframe_localization/coordinator.py - 全局注册、连续跟踪、降级、一次性恢复和版本栅栏状态机。
features/poe2/live_terrain/experimental/multiframe_localization/session.py - 截图/证据输入、单 worker 注册、旧结果丢弃和 listener 发布编排。
features/poe2/live_terrain/experimental/multiframe_localization/composition.py - native snapshot、独立 recognizer、人物内存锚点与实验组件的 PoE2 组合根。
features/poe2/live_terrain/experimental/multiframe_localization/archive.py - 显式触发的 raw/wall/observed/状态/候选原子实验归档。
features/poe2/live_terrain/experimental/multiframe_localization/navigation_adapter.py - fresh/confirmed/instance/version/age 门后的领域中立导航 observation 和安全半径。
features/poe2/live_terrain/hybrid_product_runtime.py - 正式页面的 hybrid experiment 生命周期与视觉展示状态适配器。
features/poe2/live_terrain/movement.py - PoE2 native 路线经首帧旋转/镜像逆变换后进入左摇杆的等距输入适配。
ui/modes/poe2_live_terrain/multiframe_panel.py - PoE2 测试台多帧 A/B 控制、状态、性能、候选和 rolling submap 诊断面板。
tools/debug/poe2_live_terrain_localization_probe.py - 保存样本/诊断 CLI；纯 Chamfer 算法由实验 similarity_search 提供。
tools/debug/poe2_anchor_local_registration_probe.py - 锚点样本/报告 CLI；纯注册算法由实验 absolute_registrar 提供。
tools/debug/poe2_multiframe_localization_probe.py - 加载 schema 3 evidence/reference/anchor 后真实重跑 A、B 或 A+B 的离线 CLI。
tools/debug/poe2_movement_probe.py - 管理员短时 PoE2 前台摇杆诊断；输入前等待、失焦即停、中性释放并比对同实例人物位置。
tools/debug/poe2_route_probe.py - 当前实例安全路线与 PoE2 等距输入基底的有界门后路线探针。
tools/debug/poe2_follow_readonly_probe.py - 只读实机双人首帧/视觉跟踪/耗时探针；有限保存 terrain、帧和 JSON 报告，绝不发送输入。
tests/poe2_live_terrain/test_multiplayer_follow_runtime.py - 跟随路线、身份、新鲜度与障碍图 0/255 门口回归。
tests/poe2_live_terrain/test_dual_occlusion_archive.py - 失明证据包的原图、颜色 mask、候选及代价归档回归。
tests/test_bounded_role_observation.py - 通用角色观测的独立预算、过期和重现确认回归。
tests/test_poe2_dual_motion_worker.py - latest-only 帧覆盖与黏性恢复 revision、异常隔离回归。
tests/test_poe2_movement_probe.py - 独立摇杆探针的前台、安全时长和停止释放回归。
tools/debug/POE2_LIVE_TERRAIN_LOCALIZATION_PROBE.md - 离线定位探针命令、输出图语义和禁止直接复制到生产 runtime 的边界。
docs/plans/2026-05-22-event-system-design.md - 事件系统模块边界、传送门事件 v1 和探针结果记录。
docs/plans/2026-05-22-event-system-architecture-design.md - 审核通过的事件系统代码结构架构设计。
docs/plans/2026-05-22-event-system-implementation-plan.md - 事件系统 TDD 实现任务拆分计划。
docs/plans/2026-05-23-portal-event-case-study.md - 以传送门为案例固化事件四阶段方法论，并检查当前代码架构的通用化边界。
docs/plans/2026-05-24-navigation-route-progress-option-b-design.md - 导航冲突方案 B 设计：保留现有普通导航和事件移动执行器，新增统一路线进度/锚点消费模型。
docs/plans/2026-05-24-navigation-task-queue-option-c-design.md - 导航冲突方案 C 设计：把必经点、出口和事件抽象成统一 NavigationTask，由统一任务队列状态机调度。
docs/plans/2026-05-24-navigation-task-queue-option-c-implementation-plan.md - 用户选定方案 C 后的详细实施计划，按 RouteContext、MovementExecutor、EventCoordinator 拆分、TaskBuilder/Scheduler/Controller、UI 接入和旧逻辑清理分阶段执行。
docs/plans/2026-09-18-unified-event-runtime-design.md - 统一动作事件定义、路由、执行、Host/LAN 适配与 GUI 边界的批准设计。
docs/plans/2026-09-18-unified-event-runtime-implementation.md - 统一事件运行时的 TDD 实施与删除旧平行实现计划。
docs/plans/2026-09-22-poe2-hybrid-localization-design.md - 已实现于 PoE2 experimental 边界的混合定位模块设计；尚未接正式 runtime 或通过实机验收。
docs/plans/2026-09-22-poe2-hybrid-localization-implementation-plan.md - 已执行的 15 项 TDD 任务计划及验证顺序。
architecture_docs/zh-CN/core/CORE_MODULARIZATION_PLAN.md - core 专项模块化迁移计划，记录对外接口冻结、compatibility wrapper、目标包结构、逐文件迁移映射和阶段实施顺序。
architecture_docs/zh-CN/core/ARCHITECTURE_OPTIMIZATION_RULES.md - core 后续优化判断准则，明确不按固定行数拆分，而按模块深度、依赖方向、复用价值和状态局部性判断。
architecture_docs/zh-CN/core/CORE_OPTIMIZATION_PLAN_V2.md - core 下一阶段优化方案，按规则规划 route progress、localization evidence、diagnostics formatting 和 EventAction/NavigationIntent seam。
tests/test_advanced_settings_file_io.py - 高级设置 JSON snapshot 显式目录、文件名清洗、payload 和加载校验测试。
tests/test_advanced_settings_presets.py - 高级设置预设数据和 adapter 应用测试。
tests/test_navigation_params_compat.py - 导航旧 `nav_preferences` 字段读写兼容测试。
tests/test_nav_params_screen_estimator.py - 导航参数点击半径估算 helper 边界测试。
tests/test_color_picker_debug_output.py - 颜色选择器预览 debug 输出开关测试。
tests/poe2_live_terrain/test_localization_probe.py - 紧凑动态分量清理、人物侧可行走面、旋转镜像比例恢复及可行走证据消歧测试。
tests/test_motion_controller.py - 点击半径夹紧逻辑测试。
tests/test_event_definition_repository.py - 统一定义解析、稳定身份、revision、设备 owner、草稿复制和 tombstone 传播测试。
tests/test_event_routes.py - 路由旧值规范化、持久化和纯 dispatch 测试。
tests/test_event_execution_runtime.py - source/controller 隔离、定义快照与 neutral frame 测试。
tests/test_event_workbench_ui.py - 注入假服务的事件工作台 Qt 边界测试。
core/runtime/tests/test_event_host_bridge.py - Host/LAN 精确命令与 payload 测试。
core/runtime/tests/test_event_hotkeys.py - 热键边沿、支持键名和未知键忽略测试。
core/runtime/tests/test_event_workbench_service.py - 本机/远程统一编排、目录同步、fanout、deadline 和幂等关闭测试。
```

## 3. 架构全景
```text
Level 1
┌──────────────┐       ┌──────────────────────────┐       ┌──────────────┐
│ Game screen  │ ───▶  │ Minimap Stitcher/Nav App │ ───▶  │ Mouse click  │
└──────────────┘       └──────────────────────────┘       └──────────────┘
```

```text
Level 2
┌──────────────┐
│ MainWindow   │
└──────┬───────┘
       ├──▶ MappingWidget ──▶ MapStitcher ──▶ map_data.npz/config.json
       └──▶ NavigationModeWidget ──▶ NavigationCore ──▶ global player pos
                                  ├──▶ EventCoordinator.observe/run_task
                                  ├──▶ NavigationTaskController ──▶ NavigationIntent
                                  └──▶ MotionController ──▶ Win32 mouse_event / key input
```

```text
Level 3: navigation click path
┌──────────────────────┐
│ navigation_loop      │
│ capture minimap      │
│ localize player      │
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ NavigationTaskController │
│ select route/event task  │
│ MovementExecutor -> step │
└──────────┬───────────────┘
           ▼ MOVE_MAP intent
┌────────────────────────────┐
│ MotionController           │
│ normalize map direction    │
│ clamp screen click radius  │
└──────────┬─────────────────┘
           ▼
┌──────────────────────┐
│ Win32 mouse_event    │
└──────────────────────┘
```

```text
Level 3: unified action-event path
┌───────────────────────┐
│ EventWorkbenchPage    │
│ edit / render / toggle│
└───────────┬───────────┘
            ▼ service contract
┌──────────────────────────────┐
│ EventWorkbenchService        │
│ definitions + routes + loop  │
└──────┬──────────┬────────────┘
       │          │
       ▼          ▼
┌────────────┐  ┌─────────────────────┐
│ Hotkey edge│  │ catalog/event inbox │
└──────┬─────┘  └──────────┬──────────┘
       └──────────┬────────┘
                  ▼
       ┌────────────────────────┐
       │ EventExecutionRuntime  │
       │ source × controller    │
       └───────────┬────────────┘
                   ▼ EventStateFrame
       ┌────────────────────────┐
       │ HostEventBridge        │
       │ event.* / sync.share.* │
       └────────────────────────┘
```

## 4. 模块与文件详解
### `src/auto_modules/features/poe2/live_terrain/experimental/multiframe_localization/models.py`
职责：冻结实验层跨模块交换的数据，避免截图数组、候选协方差和版本字段被 UI 或 worker 事后修改。关键导出：`MotionState`、`MultiFrameEvidence`、`CandidateRegion`、`PositionEstimate`。对外依赖：hybrid `HybridFrame`、通用 `FrameDisplacement` 和 NumPy。注意事项：所有数组复制后只读；位置、协方差、时间、版本和 instance 在构造时校验。

### `src/auto_modules/features/poe2/live_terrain/experimental/multiframe_localization/motion_gate.py`
职责：把相邻 wall mask 分类为 moving/stationary/unknown，并只在达到位移阈值时准入关键帧。关键导出：`MotionDecision`、`MotionGate`。对外依赖：`canonical_wall_mask()`、`estimate_bounded_displacement()`。注意事项：低质量或过大帧间隔属于 unknown，不能伪装成 stationary。

### `src/auto_modules/features/poe2/live_terrain/experimental/multiframe_localization/evidence_window.py`
职责：拥有当前 segment 的有界关键帧集合和 evidence version。关键导出：`EvidenceWindow`、`travel_distance`、`estimated_bytes`。对外依赖：`MultiFrameEvidence`。注意事项：静止、非关键帧、未接受位移不增长窗口；segment 改变只清一次旧证据；淘汰同时受帧数、时间、累计行程和实际数组字节预算约束。

### `src/auto_modules/features/poe2/live_terrain/experimental/multiframe_localization/rolling_submap.py`
职责：仅从当前窗口重建有限 wall/observed 地图。关键导出：`SubmapSnapshot`、`RollingSubmap`。对外依赖：`MultiFrameEvidence`、NumPy。注意事项：窗口外保持 unknown；内部累积 `wall_weight/observed_weight/last_frame_id`，淘汰帧后全量重建可移除旧噪声而不是永久 OR；超预算裁剪围绕最新视野。

### `src/auto_modules/features/poe2/live_terrain/experimental/multiframe_localization/shape_registration.py`
职责：以墙体形状而非精确线宽为核心计算候选分数。关键导出：`ShapeScore`、`transform_points()`、`score_shape()`、`SearchLevel`。对外依赖：`SimilarityTransform2D`、OpenCV distance transform。注意事项：使用 Huber 损失和固定比例异常点裁剪，但 coverage 保持原始覆盖率；局部切向误差参与联合分；reference geometry 缓存有明确上限并持有源数组，避免 NumPy 地址复用造成跨地图距离场串用；reverse coverage 只统计投影后 observed 区，圆形截图外不作为空白惩罚。

### `src/auto_modules/features/poe2/live_terrain/experimental/multiframe_localization/registration_validator.py`
职责：把候选生成与候选确认分离，对 A、B 或两者共同输出执行一致的安全门。关键导出：`RegistrationDecision`、`RegistrationValidator`。对外依赖：`AbsoluteRegistration`、`PositionAnchor`、`MultiFrameEvidence`、`transform_points()`。注意事项：依次检查实例、支持帧数、锚点误差、F2F 轨迹误差、holdout、首二名 margin 和 A/B peer 位置/角度/镜像冲突；任一失败返回结构化 reason，不发布候选。

### `src/auto_modules/features/poe2/live_terrain/experimental/multiframe_localization/local_corrector.py`
职责：在已确认 transform 和预测位置附近执行稀疏局部形状纠偏，限制连续视觉位移的漂移。关键导出：`CorrectionPolicy`、`CorrectionResult`、`LocalShapeCorrector`。对外依赖：`HybridFrame`、`AbsoluteRegistration`、`TerrainReference`、`score_shape()`。注意事项：只搜索有界平移/细角度邻域，不做整图搜索、不读取内存；单次失败只让 coordinator 进入 degraded 计数，连续失败才触发恢复。

### `src/auto_modules/features/poe2/live_terrain/experimental/multiframe_localization/strategy_a.py`
职责：方案 A 的结构门、冻结拼图注册和留出验证。关键导出：`StrategyResult`、`SubmapThresholds`、`StitchThenRegister`。对外依赖：`RollingSubmap`、现有 `AnchoredAbsoluteRegistrar`。注意事项：默认至少 `min_frames + 1` 个关键帧，最后一帧作为独立 holdout；结果携带 support/holdout 元数据供统一 validator 使用；同 evidence version 不重复注册，`reset()` 开始新 session 时清除尝试栅栏。

### `src/auto_modules/features/poe2/live_terrain/experimental/multiframe_localization/strategy_b.py`
职责：方案 B 的多方向/镜像/比例共同变换候选累计评分。关键导出：`CandidateHypothesis`、`CandidateSet`、`JointCandidateStrategy`。对外依赖：`score_shape()`、`SearchLevel` 和 hybrid transform DTO。注意事项：local offset 先经候选线性变换再加到 native translation；不同 basin 不会按空间位置误去重；默认 45 度只定义初始 basin，随后按有界 search levels 细化到约 1 度，不把离散 basin 当最终方向；`reset()` 丢弃上一 session 的候选缓存。

### `src/auto_modules/features/poe2/live_terrain/experimental/multiframe_localization/state_estimator.py`
职责：注册确认后的时序位置、速度和协方差估计。关键导出：`PositionStateEstimator`。对外依赖：NumPy。注意事项：只在固定候选内部滤波；跳变观测由 Mahalanobis 门拒绝，不能用滤波跨越方向歧义。

### `src/auto_modules/features/poe2/live_terrain/experimental/multiframe_localization/coordinator.py`
职责：拥有 `IDLE/ANCHORING/COLLECTING/REGISTERING/TRACKING/DEGRADED/RECOVERING/WAITING` 状态和唯一可信 estimate。关键导出：`LocalizationPhase`、`RegistrationRequest`、`GlobalStrategyOutcome`、`MultiframeLocalizationCoordinator`。对外依赖：A/B、窗口、submap、estimator 和 hybrid registration DTO。注意事项：A、B 都必须经过 `RegistrationValidator`；双验证通过时按 validated confidence 选择较优结果；注册结果必须通过 instance/recovery/evidence/segment token；注册期间位移会在确认后补偿；`reset()` 同时清理可重置策略缓存。

### `src/auto_modules/features/poe2/live_terrain/experimental/multiframe_localization/session.py`
职责：驱动采集、证据构建、一次性锚点、后台注册和状态发布。关键导出：`MultiframeLocalizationSession`。对外依赖：注入 frame source/evidence builder/anchor provider 和 coordinator。注意事项：默认 executor 有两个槽位，当前注册使用隔离 coordinator/策略副本；超时任务进入 retired 集合，允许新 evidence version 重试，旧 worker 只记录完成/异常不发布；generation 与 request token 双重栅栏使 `stop/reset/close` 后旧结果失效；新 start/reset 会清理 frame/previous/anchor revision，并调用 evidence builder reset；不执行输入。

### `src/auto_modules/features/poe2/live_terrain/experimental/multiframe_localization/composition.py`
职责：把 native terrain snapshot、独立识别器、人物只读 source 和实验组件装配成 `Poe2MultiframeExperiment`。关键导出：`build_multiframe_experiment()`、`build_poe2_multiframe_experiment()`。对外依赖：PoE2 terrain/monitor/hybrid adapters。注意事项：构造时应用 active profile 的 `recognizer_params`；忽略 profile 手工地图方向，锚点与 reference 均保持 native 坐标；正式 runtime 不导入该 factory。

### `src/auto_modules/features/poe2/live_terrain/experimental/multiframe_localization/archive.py`
职责：仅在显式保存时原子归档原图、wall/observed、位移、完整 native reference、anchor、typed estimate 和 diagnostics，并重建真实离线回放输入。关键导出：`MultiframeReplayBundle`、`MultiframeArchive`、`SCHEMA_VERSION=3`。对外依赖：NumPy、JSON、本地文件系统。注意事项：空 evidence 不能保存；load 会重建 `PositionEstimate`、`CandidateRegion`、`SimilarityTransform2D` 和协方差；只接受 `coordinate_space=native` 的 schema 3；旧 schema 2/手工方向归档直接拒绝；二维位移在加载边界校验；目标存在时拒绝覆盖，失败删除临时目录，运行时默认不落盘。

### `src/auto_modules/features/poe2/live_terrain/experimental/multiframe_localization/navigation_adapter.py`
职责：将实验 estimate 转成 fail-closed 导航 observation。关键导出：`NavigationObservation`、`NavigationLocalizationAdapter`。对外依赖：`PositionEstimate`、NumPy。注意事项：仅 fresh confirmed、age/instance/version 合格才 executable；本模块不规划路线、不执行设备。

### `src/auto_modules/ui/modes/poe2_live_terrain/multiframe_panel.py`
职责：多帧实验的 A/B 选择、生命周期按钮和只读诊断展示。关键导出：`Poe2MultiframePanel`。对外依赖：PySide6、NumPy。注意事项：运行中锁定策略开关；保存按钮只在存在可归档状态时开放。

### `src/auto_modules/features/poe2/live_terrain/monitor_config.py`
职责：定义 PoE2 用户可保存的截图与识别 profile 契约。关键导出：`Poe2MonitorConfig`、`Poe2MonitorConfigStore`、`Poe2MonitorProfileStore`、默认识别/拼图参数。对外依赖：`core.spatial.monitor_binding`、`CaptureShape`、`MapStitcher` 与标准库 JSON/文件原子替换。注意事项：center 模式构造/加载时自动围绕旧 marker 规范 binding 到 `capture_size`，region 模式保留用户画框；不再包含 `map_rotation/map_flip_horizontal/map_flip_vertical`，旧 JSON 键被忽略且重新保存不会写回，方向只能由定位注册产生。

### `src/auto_modules/ui/modes/poe2_live_terrain/presenter.py`
职责：把 native terrain、定位候选、人物点和轨迹转换为一致的 Qt 展示状态。关键导出：`TerrainDisplay`、`LocalizationPresentationState`、`build_localization_presentation()`、`present_localization_overlay()`、`localization_display_point()`。对外依赖：TerrainSnapshot、NumPy、OpenCV、PySide6。注意事项：registration version 不一致时不应用方向；注册版本改变由调用方清空旧轨迹；方向变换只影响 D 显示空间，不修改 N 坐标数据。

### `src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py`
职责：数据采集测试台独立拥有双人首帧、实时定位、跟随/移动、诊断与保存入口。双人 worker 在 GUI 外截图、识别和跟踪，latest-only 图像槽之外独立传递恢复 revision，并把已完成的 `processed` 预处理结果随帧交给 UI；生产 30 FPS 时 Qt drain 使用 33ms，避免无意义双倍唤醒。无法安全复制 recognizer 时退回同步 timer。页面按 identity 的观测年龄与误差预算决定短时失明跟随或立即释放；过期帧只在首次 tick 释放一次，持续 1500ms 才按统一 recovery claim 请求一次重锚，新帧到达后清除边沿。实时角色跟随启动后先进入 `cold_start`（重定位恢复进入 `recovery_sync`），同一 accepted frame 只用于建立 tracker 基线，不发送程序输入；只有捕获时间严格晚于 baseline 的完整双人帧到达后才进入 `tracking` 并启动输出。跟随/双人同目标的 Host diagnostics 最少 5 秒查询一次，控制输出节拍不变。实时跟随程序角色的预测速度以连续有效视觉位移/时间差限幅 EWMA 更新，固定 runtime speed 只作冷启动先验；连续视觉点必须以 `RoleId.key` 和同一捕获时间基线写入/读取，预测偏差小但视觉连续时重基线，异常跳变仍走重定位。停止、换图和关闭会清理 worker 与程序输出；旧 worker 未退出时延迟重新注册，session token 拒绝迟到回调；首帧 accepted 已交付后 cleanup 异常不会覆盖成功终态。关键导出：`Poe2CaptureTestPage`。对外依赖：terrain service、preview/recognizer、双人内存锚点与首帧注册、`DualVisualTracker`、`Poe2DualMotionWorker`、`SimulatedFollowRuntime`、presenter、PySide6 和程序输出适配器。注意事项：双人特征使用 `exclude_player=False, exclude_dynamic=False`，不挖空人物周围墙体；普通视觉帧不读内存，只有首帧/恢复读锚点；单人中心定位及绘图模式不受影响。

当前重定位契约：`_tick_program_move_probe()` 在 `contact_relocalization_required` 时先保存目标、角色和控制器并释放旧输入；`_start_dual_motion(recovery=True)` 强制重新调用 `run_dual_first_frame_experiment(..., force_memory_read=True)`，因此每次 recovery revision 只新增一次双人内存读取。worker 或同步定位收到新的 tracking 帧后，`_maybe_resume_program_probe_after_relocalization()` 才用原目标自动重建程序移动；首帧拒绝或新帧不新鲜时清理 context，保持安全停止。PoE2 页面创建的 runtime 使用 `contact_required_samples=4`，通用默认仍为 `2`。

独立的“双人同目标移动实验”在同页侧栏有专属 P1/P2 身份选择、开始/停止与状态，不共享旧跟随 runtime/timer/output。`_make_follow_runtime()` 给两个场景提供同一组 PoE2 规划与恢复参数；新场景把两名角色作为独立 `PROGRAM` follower 加入同一个 native 墙图 runtime，并为控制器 1/2 分别建立 lease。点击只更新一个共享 native 目标，runtime 按角色生成路线、观测和输入。新场景要求真实视觉帧时间戳且帧龄不超过 700ms；到达、单角色过期与阻塞只释放对应输出，整体定位失效、异常和停止释放全部。实时角色跟随复用这一 runtime/output 链，只把领队视觉点作为 `remote` 目标源、程序角色视觉/命令观测作为 follower 位置源；不应在业务页复制寻路或输出逻辑。小地图墙体证据经 `_update_follow_local_contact()` 按角色送入通用 runtime；接触要求全局恢复时以 10 秒冷却保存目标和身份，释放输出，收到新鲜同实例 tracking 帧后重建并重放目标。路线和人物只在 overlay 绘制，日志仍在侧栏；不修改正式定位页或旧绘图模式。

### 2026-10-06 跟随恢复生命周期更新

`Poe2CaptureTestPage` 的实时跟随恢复已与用户停止生命周期分离。视觉恢复调用 `stop_dual_motion(preserve_follow=True)` 时只切换双人视觉 worker/首帧配准，保留 follow runtime、timer、程序输出、角色目标和 `CommandRoleTracker`；恢复期间继续使用有界命令预测。新鲜双人帧到达后，`_maybe_resume_dual_follow_after_relocalization()` 原地调用 `_sync_live_follow_from_fresh_frame()`，清除 recovery pending 并继续同一 session，不再调用 `start_follow_experiment()`。恢复门槛由 `_recovery_frame_usable()` 统一：tracking 直接通过，墙体可信且角色仍有 available bounded estimate 的 degraded 帧也可以恢复；恢复帧不满足实时启动的 300ms 新鲜度时保留 context 等下一帧，不消费恢复上下文。恢复冷却、首帧拒绝和 worker 异常安排重试；只有显式停止、换图、关闭或地图上下文失效才清理跟随。

### `tests/test_poe2_capture_test_page.py`
职责：用 offscreen Qt、假 terrain service 和假手柄输出验证采集页的点击、定位、恢复与生命周期。关键导出：pytest 用例和 `_dual_target_page()` 假会话构造器。对外依赖：`Poe2CaptureTestPage`、双人 `DualMotionState`、`SimulatedFollowRuntime` DTO、presenter 坐标变换与 PySide6。注意事项：双人同目标用例覆盖待命、双输出、重复点击、独立与先后到达/过期、整体失效、接触证据、受冷却重定位、恢复、异常和互斥；跟随用例额外覆盖 `cold_start/recovery_sync` 必须等待新鲜视觉帧、过期帧单次释放、1500ms 单次 recovery、单帧 overlay、近距离保持和恢复上下文。涉及 700ms 页面帧 TTL 的测试在手动 tick 前显式刷新 `captured_at_ms`，避免测试执行耗时被误判为业务失败。另以一次实机 221 度/镜像样本锁定 source/native 坐标往返，但该样本参数不是产品默认。测试不会连接真实 Host 或游戏。

页面生命周期补充：`suspend()` 和 `shutdown()` 都会停止 follow、dual-target、program-probe、视觉 worker 和相关 timer，释放所有程序输出；`closeEvent()` 还会移除 `_UiLogHandler`。日志 handler 对已销毁的 Qt 对象做有效性检查，后台迟到日志只丢弃不写入 UI。

### `src/auto_modules/ui/modes/poe2_live_terrain/dual_motion_worker.py`
职责：双人实验的有界截图—识别—跟踪 worker；只保留最新完成图像，另存待交付的单调 recovery revision，并在 `DualMotionFrameResult.processed` 中保留已完成预处理。关键导出：`DualMotionFrameResult`、`Poe2DualMotionWorker`、`Poe2DualFirstFrameWorker`。对外依赖：PySide6 信号、`HybridFrame`、HSV marker adapter 和注入的 preview/recognizer/tracker。注意事项：worker 不读内存、不绘图、不发送输入；`frame_failed` 记录单帧异常，连续失败达到 `max_consecutive_failures` 才发出终止信号；GUI 按 generation 丢弃迟到结果，并分别消费 `take_latest()` 与 `take_pending_recovery_revision()`。一次性首帧 worker 在发出 `result_available` 后将终态锁定，thread-local cleanup 失败只作诊断，不再发第二个 `failed`。

命令辅助跟随只通过 `set_prediction_hints(hints, generation=...)` 写入锁保护的最新值邮箱；错误 generation 无效，空映射立即清除。工作线程在同帧 `tracker.tick()` 前复制一次提示，既不跨线程修改 tracker，也不把预测当视觉候选。无提示时调用原双人 tracker 契约。

### `tests/test_poe2_dual_motion_worker.py`
职责：验证双人 worker 的单槽 latest-only、恢复边沿帧覆盖后的 revision 交付、瞬时错误隔离、连续失败阈值、processed 结果保留和首帧 cleanup 终态。关键导出：无（pytest cases）。对外依赖：NumPy、PySide6 worker、双人 tracker 注入协议。注意事项：测试使用注入 provider；不启动真实截图、内存读取或真实输入。

### `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_localization/marker_candidates.py`
职责：把共享观察帧中的颜色轮廓转换为未赋身份的双人候选。关键导出：`detect_saturated_marker_observation()`、`marker_candidates_from_observation()`。对外依赖：通用 `ObservationFrame`/`ObservationCandidate`、OpenCV HSV 与双人 marker DTO。注意事项：检测阶段只负责颜色和几何候选，不把颜色直接当作身份；适配阶段先按 bbox IoU 或中心距离做置信度排序的非极大值抑制，再为不同 profile/identity hint 保留代表，避免轮廓/核心重复占位；没有 bbox 的观察源不执行几何抑制；最终配对和方向必须由 `DualFirstFrameRegistrar` 与内存锚点确认。

### `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_localization/dual_motion.py`
职责：在已接受双人首帧的固定方向、镜像和比例下维护共同视口平移，并把颜色候选映射到 native 地图。关键导出：`DualMotionState`、`DualVisualTracker`。对外依赖：通用 canonical wall、phase displacement、`BoundedRoleObservations`、局部 matcher 协议及首帧点变换。注意事项：不读游戏内存、不发送输入；最多六个候选参加身份/距离赋值；marker 按 identity 的时间/误差预算独立退化，失明估计不是本帧视觉观测；预算耗尽才请求恢复。

`RolePredictionHint(native_position, uncertainty_native, predicted_at_ms)` 仅在实验跟随显式传入。`tick()` 先更新共享墙层变换，再过滤年龄 `0..700ms`、误差 `<=12` 且坐标有限的提示；`inverse_transform_local_point()` 用与首帧正向注册完全相同的仿射几何将 native 提示回投到当前屏幕，供 `_assign()` 的身份/颜色/距离门使用。角色暂不可见时返回该角色的提示 native 点，但 `role_observations.visible=False` 且视觉 `last_seen_at_ms` 不变；有界提示可暂缓旧固定时限的强制恢复。颜色候选重现须通过预测 native 位置门及连续帧确认，失效/过期提示恢复原本的超时重锚；墙层失效不受提示豁免。

### `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_localization/marker_association.py`
职责：在固定变换下把小地图候选关联到稳定角色身份。关键导出：`AssociationResult`、`MarkerAssociator.assign()`。对外依赖：`PlayerMarkerCandidate`；无 Qt、进程、输入或文件副作用。注意事项：`assign()` 用基础距离、角色速度×帧间隔和墙体位移生成有上限 gate，再枚举单人/双人组合；双人组合将观测间距与预测间距误差加入软成本，颜色提示只参与初次筛选，全部拒绝时回退几何关联；诊断保存候选、gate、pair 距离和前四个候选成本。无候选或超过 gate 返回空 assignment，不直接决定全局恢复。

### `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_follow/target_projection.py`
职责：修正 native 目标中心落入单个墙栅格的量化误差。关键导出：`ProjectedTarget`、`WalkableTargetProjector.project()`。对外依赖：NumPy；无 Qt、输入或地图写入副作用。中心可走时原样返回；否则在局部半径内枚举可走格，按目标距离、3×3 开放比例和局部 clearance 计算综合分，选择局部更稳点；没有邻域可走点返回原点并标记 `target_no_walkable_neighbor`。调用方仍需用 runtime 的实际路线安全校验确认可达，投影不会修改墙图。

### `src/auto_modules/core/localization/bounded_observation.py`
职责：为任意可哈希 identity 保存最后可信位置，并将短时失明表示为有时间和误差上限的估计。关键导出：`RoleObservation`、`BoundedRoleObservations`。对外依赖：无内部模块。注意事项：新视觉候选在连续失明后须通过位置门和连续帧确认；估计本身不刷新 `last_seen_at_ms`，时间倒退抛 `ValueError`；不读 PoE 内存，也不产生输入。

`update(..., reacquisition_reference=None, reacquisition_radius=None)` 在调用者提供独立预测参考时允许旧观测预算已过期的角色重新进入连续帧确认；参考只用于候选位置门，未确认时不续视觉时间，也不修改其他 identity。没有参考时保持原本预算/连续帧语义。

### PoE2 命令辅助实验跟随（2026-10-04）
`multiplayer_follow/command_role_tracker.py` 的 `CommandRoleTracker` 按 role/map version 保存最后视觉锚点、协方差、视觉位置/时间及实际成功输出的 `[accepted_at, accepted_at+TTL]` 区间；新输出截断前一输出的重叠尾部。无视觉速度样本时，`estimate()` 用冷启动 `expected_speed`（仅可乘有界校准倍率）重放区间；出现有效视觉位移/时间后，使用限幅 EWMA 的实测速度，避免再次乘 `AdaptiveInputCalibrator.speed_gain` 造成二次缩放。`observe()` 在截图时间重放并用 Mahalanobis 门校正，接受后保留晚于观测时间的输出区间；`rebase_visual()` 仅由调用方确认连续身份/步长后把视觉点设为新锚点并清除旧区间；过时帧拒绝。预测来源不刷新视觉锚点。`reacquisition.py` 在原始墙图上比较有限方向的目标进展、清距、离开旧可见点和反向惩罚，不修改全局墙图。
未显式传入协方差时，`observe()` 使用 `9 native²` 的视觉测量方差，以容纳 Host 回执、截图和游戏模拟之间的启动延迟；调用方显式传入的小协方差仍用于严格异常跳变拒绝。该边界避免正常首个脉冲触发页面的重复重锚。
`arm_visual_phase(role_key, started_at_ms, grace_ms)` 为每个角色建立一次性、有限时长的输出—视觉相位窗口；窗口内未显式指定协方差的观测使用 `visual_phase_variance`（默认 `64 native²`），窗口过期后自动恢复 `9 native²`。该宽限只覆盖 Host 已确认而截图尚未更新的启动/恢复相位，不改变稳态跳变门，也不影响调用方显式传入的严格协方差。
页面 `_tick_follow_experiment_impl()` 只对本帧可见的身份观测做视觉校正；隐藏程序角色用已确认的输出回执积分，隐藏手动领队仅保持最后可信目标。所有程序跟随 tick 先经 PoE2 前台门，后台时一次性释放并等待，不把窗口焦点问题升级成重定位；恢复前台后重新建立视觉基线。每次真实手柄写入成功后记录轴向、接受时间与 TTL，并通过 `_publish_follow_prediction_hints()` 给 worker 下一帧使用；同步测试路径使用同一提示。`SimulatedFollowRuntime` 不让预测样本更新卡墙、速度标定或到达确认，输出短脉冲继续寻找可行方向；估计无界、墙层失效、重现连续拒绝或无安全方向时先释放输入，再走现有一次性重锚与同实例恢复。停止时清空提示和 Host lease。正式页、单人中心定位、双人首帧注册不传提示。

### `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_localization/occlusion_archive.py`
职责：将 PoE2 实验页的失明状态转换帧保存为可离线复核的小证据包。关键导出：`save_dual_occlusion_evidence()`。对外依赖：双人颜色 profile/候选 DTO；NumPy、OpenCV。注意事项：调用方最多保存六组；每组包含 `raw.png`、每个配置颜色的 mask 和 `evidence.json`，后者保留候选与分配代价；写盘只用于实验诊断，不是定位运行时缓存。

### `tests/test_bounded_role_observation.py`
职责：验证任意 identity 的独立可用预算、时间/误差过期和重现连续确认。关键导出：无（pytest cases）。对外依赖：`BoundedRoleObservations`。注意事项：纯状态测试，不需要 PoE 进程或 Qt。

### `tests/poe2_live_terrain/test_dual_occlusion_archive.py`
职责：验证实验失明证据包保留原图、颜色 mask、候选字段与赋值诊断。关键导出：无（pytest cases）。对外依赖：`save_dual_occlusion_evidence()`、NumPy。注意事项：使用 pytest 临时目录，不写真实采集数据。

### PoE2 实验跟随运行时与独立移动探针
`experimental/multiplayer_follow/models.py` 定义角色、地图实例、位置时间戳与状态 DTO；`runtime.py` 的 `SimulatedFollowRuntime` 只维护每角色跟随状态、地图点击目标、多尺度 A* 与纯观测向量，观察结果的 `diagnostics.coordinate_space` 固定为 `reference_native`，同时给出路线点数、端点、候选路线数量、选中路线长度、清距暴露评分、最小清距、无进度和恢复次数。它把任何非零墙体转成 255，保证 `PathFinder` 的 50 阈值与原始网格 `line_is_walkable` 判定一致；PoE2 实验组合启用安全膨胀、distance-transform 清距、窄路软代价和原图最小清距复核，并用 `route_length + clearance_weight * exposure` 在安全候选中择优。每个 follower 在 `add_follower()` 时创建独立 `ContactMonitor(required_samples=contact_required_samples)`；通用默认门为 2，PoE2 页面真实输入组合显式传 4，避免门口短暂无位移过快升级重定位。零向量不会立即释放，而是交给 stalled watchdog 生成左右交替的侧向 waypoint；仍无逃逸路线才进入 `BLOCKED`。该 runtime 不读游戏内存、不向手柄输出；`program_output.py` 只在显式 program 模式持有 Host lease。
`core/routing/contact_evidence.py::ContactMonitor.observe()` 在相同坐标空间比较非零命令与实际位移，计算位移对齐度、连续无进展次数和恢复门；阈值按命令幅度、0.25 native 位移和连续样本数判断，必要时附加局部障碍证据。`runtime.py::update_local_contact()` 只保存 PoE2 适配器的 wall_ahead、wall_distance、free_left/free_right；`SimulatedFollowRuntime._tick_follower()` 在局部墙体且连续无进展时跳过旧的直线路径，按左右清空度排序的局部脱困 waypoint；两次局部脱困仍失败输出 `contact_relocalization_required`，由页面停止输入并进入已有双人恢复入口。人物 footprint 膨胀配置不由此模块改变。
当前 PoE2 移动实验的运行时配置保持 `inflate_collision=False`、`footprint_radius=0`、`safety_margin=0`、`minimum_clearance=0`；局部接触证据用于纠偏和恢复，不把额外身体膨胀当作硬碰撞门。
`experimental/multiplayer_follow/models.py` 定义角色、地图实例、位置时间戳与状态 DTO；`runtime.py` 的 `SimulatedFollowRuntime` 只维护每角色跟随状态、地图点击目标、多尺度 A* 与纯观测向量，观察结果的 `diagnostics.coordinate_space` 固定为 `reference_native`，同时给出路线点数、端点、候选路线数量、选中路线长度、清距暴露评分、最小清距、角色碰撞半径、目标刷新位移、路线偏离、无进度和恢复次数。它把任何非零墙体转成 255，并可按 `footprint_radius` 生成只读膨胀碰撞图；规划、跟踪和模拟步进共用该图，原始墙图仅用于清距证据，保证中心线可行不等于角色身体可以擦墙。PoE2 实验组合启用安全膨胀、distance-transform 清距、窄路软代价和原图最小清距复核，并用 `route_length + clearance_weight * exposure` 在安全候选中择优。额外地，当连续 native 坐标因栅格量化落在墙格时，runtime 会先搜索半径 12 内能到达目标的可行走起点并发出有界 `wall_start_recovery` 脉冲；恢复 episode 固定起点且最多 3 个脉冲，最新小地图确认中心线开放时只允许有限的 `stale_wall_raster_recovery` 过渡，不再无限复用 stale wall cache，`observed_position_metrics` 仍保留原始观测格。目标在刷新带内移动时复用已验证路线，只有目标超出刷新带、人物偏离路线、碰撞失效或 stalled recovery 才局部重规划。零向量不会立即释放，而是交给 stalled watchdog 生成左右交替的侧向 waypoint；仍无逃逸路线才进入 `BLOCKED`。该 runtime 不读游戏内存、不向手柄输出；`program_output.py` 只在显式 program 模式持有 Host lease。

`tools/debug/poe2_movement_probe.py` 的 `run_bounded_output()` 是独立管理员诊断：输入前默认等待 10 秒，验证 PoE2 前台，每 50ms 发一次方向状态，最多 2 秒；失焦或结束进入 finally 发送中性并释放。`main()` 在同地图实例读取前后 P1 坐标并记录 JSONL；`--check-only` 只读。该探针不计算路线，也不启用 LAN、键鼠。路线探针的每个非零路径段保持 reference/native 坐标，直接交给 PoE2 输入基底，registration 不在输入边界重复应用。

实验页真实程序移动在确认后延迟 10 秒切回游戏，并通过 adapters/windows/window_finder.py 只读获取 PoE2 PID/HWND；程序移动探针和跟随输出都在每个控制 tick 检查游戏仍在前台、视觉位置年龄不超过 700ms。前台失败进入等待边沿，只释放一次已有 lease、保留视觉 worker，不把焦点问题升级成重定位；恢复前台后以最新完整帧重置跟随视觉基线。地图运行没有总时长硬停止，长路线持续到目标或显式操作/生命周期边界；视觉帧新鲜度与 Host command TTL 是单次观测安全契约，不是整张地图的运行时限。失焦中性释放和窗口查询均不调用聚焦或鼠标 API。每 5 个 tick 记录 reference/native 当前点、目标点、路线端点、native 向量和局部向量；Host adapter 的低频诊断还记录 basis 后向量、轴值、TTL 和租约状态。
`probe_mixin.py` 独立导入 `QMessageBox`、`find_process_id`、`find_process_window` 和 `is_process_foreground`，程序移动真实入口不依赖旧单体页面的隐式模块全局。
`dual_motion_mixin.py` 显式导入 `MapRuntime`、`LocalMapMatcher`、`DualVisualTracker`、`Poe2DualMotionWorker` 和 registration boundary；`localization_mixin.py`/`page_lifecycle_mixin.py` 显式导入各自的 Qt/position 类型，避免只有实机入口才暴露的拆分后 `NameError`。
`tools/debug/poe2_route_probe.py` 是独立门后路线探针：离线模式通过 `SimulatedFollowRuntime.tick()` 复现页面的墙边起点恢复并输出观测格/规划起点诊断；实机模式先用当前实例 native 起点、当前 NPZ 墙图和原图逐段碰撞校验生成目标路线，再等待 10 秒、检查 PoE2 前台后以 PoE2 专用输入基底发送有界 Xbox 状态。路线段向量保持 reference/native 坐标，由 PoE2 basis 单独投影到摇杆，最后读取同实例人物位置记录位移；地图/进程/权限/焦点任一门禁失败都不发送或立即中性释放。

### `tools/debug/poe2_follow_readonly_probe.py`
职责：在真实 PoE2 进程上有限次数验证双人首帧、视觉跟踪和各阶段耗时，隔离“算法失败”和“权限/捕获/处理过慢”。关键导出：`run_probe()`、`main()`、`_capture_terrain()`。对外依赖：`windows_capture.resolve_poe2_descriptor()`/`capture_descriptor()` 的只读进程和 guarded terrain 读取、`Poe2MonitorProfileStore` 当前 profile、`build_poe2_dual_localization_experiment()` 正式双人定位组合、`SquareScreenCapture`/`MonitorFrameSource`、`HSVRecognizer` 和 `load_native_grid()`。算法步骤：1) 解析一次当前进程指纹/布局并把同一实例 terrain 导出到本地 run 目录；2) 载入绑定和 recognizer 参数，创建双人 session；3) 首次 `session.tick()` 读取一次双人 anchor 并截帧注册；4) 首帧通过后只调用有限视觉 tick，保存状态、帧龄、capture/evidence/localization 分段耗时和最多指定数量的 PNG。副作用仅写 `data/poe2_live_terrain_test/readonly_follow_probes/<run>/` 下的 terrain、frames 和 report；`limits.input_calls`、`network_calls` 固定为 0。失败行为：权限/进程/地图/profile/截图异常写入 `errors` 并停止，不重试内存、不创建 runtime、不触碰 Host；首帧失败后不继续读内存。注意事项：需要管理员只读权限才能访问受保护的游戏进程；该工具不是跟随控制器，也不能证明实机手柄效果。

### `tools/debug/poe2_multiframe_localization_probe.py`
职责：从 schema 3 归档重建真实 evidence、anchor 和 native reference，离线重跑方案 A、方案 B 或两者。关键导出：`build_parser()`、`main()`。对外依赖：`MultiframeArchive`、`StitchThenRegister`、`JointCandidateStrategy`、JSON CLI 输出。注意事项：`--strategy a|b|both` 决定执行策略；它不截图、不连接游戏、不读取进程、不把 manifest 摘要冒充算法回放结果。

### `main.py`
职责：源码 checkout 和安装 payload 共用的最薄启动入口。
关键导出：从 `auto_modules.bootstrap.main` 导入的 `main`。
对外依赖：标准库 `sys/pathlib`、`auto_modules.bootstrap.main`。
注意事项：只把同级 `src` 前置到 `sys.path`；不得重新承载权限、日志、GUI 或业务逻辑。

### `src/auto_modules/paths.py`
职责：统一源码与安装态的 package、仓库、只读资源和可写数据根目录。
关键导出：`package_root()`、`repository_root()`、`resource_root()`、`data_root()`。
对外依赖：标准库 `os/pathlib`。
注意事项：`AUTO_MODULES_RESOURCE_DIR`、`AUTO_MODULES_DATA_DIR` 是显式部署边界；调用方不再根据自身 `__file__` 深度猜根目录。

### `src/auto_modules/adapters/input/keyboard_device.py`
职责：把通用 `KeyboardDevice` contract 适配为 PyDirectInput 的 keyDown/keyUp 调用。
关键导出：`PyDirectInputKeyboardDevice`。
对外依赖：延迟导入第三方 `pydirectinput`。
注意事项：具体桌面输入实现已从 `core.actions.keyboard` 移出；测试可注入 fake module，构造本身不发送按键。

### `src/auto_modules/adapters/virtual_gamepad/program_output.py`
职责：把跟随/事件产生的摇杆和按钮状态适配为 Host `program.acquire/state/release` lease 协议。
关键导出：`host_clock_ms()`、`ProgramGamepadOutput`。
对外依赖：`core.actions.StickSlewLimiter`、Windows `GetTickCount64`、注入的 Host client。
注意事项：`start()` 才获取 lease，`write()` 不会启动 controller mapping，`stop()` 幂等释放；Host 协议和 Windows clock 不再位于 core。PoE2 页面在调用该适配器前必须通过只读前台门，Host accepted 只证明报告被接受，不证明游戏实际消费。

### `src/auto_modules/core/communication/shared_state.py`
职责：定义与设备/协议无关的共享位置和共享事件不可变数据契约。
关键导出：`SharedPosition`、`SharedEvent`。
对外依赖：仅标准库 `dataclasses`。
注意事项：字段使用调用方本地单调时钟语义；Host deadline translation 不属于该模块。

### `src/auto_modules/core/routing/trajectory_target.py`
职责：保存有序二维轨迹，并按累计路径长度返回距离最新点指定距离的滞后目标。
关键导出：`LaggedTrajectoryTarget`。
对外依赖：`core.routing.geometry` 的累计长度、距离和插值函数。
注意事项：拒绝非有限/逆序时间样本，0.5 像素内重复点不追加；不知道角色、游戏、设备或跟随策略。旧 `routing.follow_target` 已删除。

### `src/auto_modules/adapters/host/follow_transport.py`
职责：把 `SharedPosition/SharedEvent` 与 Host `sync.share.*` wire payload 双向转换，并在 IPC 延迟后重新检查 TTL。
关键导出：`FollowTransport`。
对外依赖：`core.communication` contracts、`adapters.virtual_gamepad.host_clock_ms`、注入的 Host client。
注意事项：没有 socket ownership；LAN 会话仍由 Host 拥有。`poll()` 丢弃非法、非有限或过期记录，不把远端单调时间戳当成本机时间。

### `src/auto_modules/application/event_workbench/service.py`
职责：组合通用事件定义/路由/执行、Win32 trigger source 和 Host bridge，拥有本机与远程事件工作台生命周期。
关键导出：`EventWorkbenchService`。
对外依赖：`core.events.automation`、`adapters.host`、`adapters.windows`、`adapters.virtual_gamepad.host_clock_ms`。
注意事项：UI 只消费 service contract；Host clock 和 wire commands 均留在 adapter 边界。

### `src/auto_modules/features/torchlight/follow/service.py`
职责：协调 follow workers、热键边沿、Host share transport 和有界队列。
关键导出：`FollowService`。
对外依赖：`core.communication.SharedEvent`、`adapters.host.FollowTransport`、`adapters.windows.HotkeyTriggerSource`、`adapters.virtual_gamepad`。
注意事项：不再直接读取 Win32 key state；网络 I/O 在线程中运行，真实 worker/Host 连接只有显式 `start()` 后发生。

### `services/virtual_gamepad/launcher/src/VirtualGamepadLauncher/LauncherPaths.cs`
职责：从 `services/virtual_gamepad` 解析 repository、workspace、Python、.NET、Host、UI 和 client 物理路径。
关键导出：`LauncherPaths` 及 candidate/path properties。
对外依赖：.NET `System.IO`、环境变量 `DOTNET_ROOT`。
注意事项：`AutoModulesRoot` 是 `D:/.../auto_modules`，`WorkspaceRoot` 是其父目录；`SourceRoot` 必须从前者构造，`.venv` 和 workspace-local SDK 从后者查找。

### `packaging/distribution/build.py`
职责：从 allowlist 源码、只读资源、锁定 Python wheels、C# publish 输出和签名依赖组装离线 payload。
关键导出：`select_runtime_sources()`、`sanitize_config()`、`dependency_closure()`、`assemble()`。
对外依赖：Python 3.12 x64、.NET SDK、缓存下载物、`packaging/distribution/requirements.lock`。
注意事项：payload 应包含 `app/main.py`、`app/src/auto_modules`、`app/resources`；默认数据写入 payload `defaults/maps` 和 `defaults/virtual_gamepad/configs`，绝不打包本机身份或日志。

### `gui/app_context.py`
职责：作为 GUI 共享服务组合根，创建并持有截图、识别、建图、追踪、寻路对象以及当前监控区域状态。
关键导出：`AppContext`。
对外依赖：`core.platform.SquareScreenCapture`、`core.vision.HSVRecognizer`、`core.vision.PlayerTracker`、`core.mapping.MapStitcher`、`core.routing.PathFinder`。
注意事项：`AppContext` 不再通过 `core.__init__` 聚合入口导入服务对象，改为通过 `gui/composition/services.py` 使用明确 core 系统包入口。初始化顺序是先创建或接收 `CoreServices`，再初始化 monitor 状态；旧的空 `load_global_config()` / `save_global_config()` 占位方法已删除，后续若引入真实全局配置，应避免和每地图 `config.json`、导航参数保存链路混淆。

### `gui/navigation_params.py`
职责：定义导航配置数据模型，并把地图 `config.json` 转换为运行时 `NavConfig`。
关键导出：`NavConfig`、`RecognizerParams`、`NavPreferences`、`_parse_hsv_list`。
对外依赖：无内部模块依赖。
注意事项：`monitor_size`/`draw_scale` 服务定位一致性；`game_view_map_size` 和点击半径参数服务主画面移动控制，不能反向影响定位。`NavPreferences.k_ratio/y_bias` 只保留旧 `config.json` 读写兼容，不再由导航参数面板暴露，也不参与当前 motion 映射。`RecognizerParams` 严格接收当前代码声明的字段，包含绘图页写入的 `player_clear_radius`；未知字段不做静默过滤，配置和代码不一致时应直接暴露。

### `core/input/controller.py`
职责：把 `NavigationTaskController` 输出的地图全局子目标转换为屏幕物理坐标点击，是输入控制系统的正式状态拥有者。
关键导出：`MotionController`。
对外依赖：`core.input.click_pipeline`、`core.input.motion_controller` helper 包。
注意事项：当前不负责寻路、不负责定位，只处理“地图方向 -> 屏幕点击”和真实输入派发。`movement_scale_factor`、普通点击半径夹紧、近目标精确点击和底部 UI 防误点策略已委托 `core.input.motion_mapping`；`_execute_click()` 的流程编排已委托 `core.input.click_pipeline`；真实点击发送委托 `core.input.click_executor`；窗口/光标诊断委托 `core.input.click_diagnostics`；屏幕高度和可选 clamp 委托 `core.input.screen_bounds`。`MotionController` 作为 state owner 保留旧 public/private 方法和 `last_click_info` 写入语义：参数设置、显式屏幕点击和按键在 `core.input.motion_controller.controls`，地图目标点击和坐标计算在 `core.input.motion_controller.targets`，lazy InputDriver、screen clamp、安全 pydirectinput 调用和窗口信息格式化在 `core.input.motion_controller.backend`。事件系统的显式屏幕点击走 `click_screen_position()`，事件按键走 `press_key()`，避免 handler 直接调用私有输入细节。

### `core/input/click_executor.py`
职责：封装真实鼠标点击发送路径。
关键导出：`send_click`、`fallback_pydirect_click`。
对外依赖：`pydirectinput`。
注意事项：`send_click()` 先按 `input_backend` 选择 Win32 driver click，成功时返回 `moved_by_driver=True`；否则走 `pydirectinput.click(x, y)`，并按 `confirm_after_click` 可选追加一次 confirm click。该模块只返回执行 metadata，不直接写 `MotionController.last_click_info`。

### `core/input/click_diagnostics.py`
职责：封装点击点窗口、前台窗口、ClipCursor 和 Win32 光标位置诊断。
关键导出：`collect_window_diagnostics`、`focus_window_at`、`win_cursor_pos`、`format_window_info`。
对外依赖：无固定内部模块依赖；只依赖调用方传入的 driver adapter 能力。
注意事项：所有诊断都是 best-effort；driver 不支持某个方法时返回 `None`，异常由 `MotionController._execute_click()` 捕获并打印。该模块不执行点击，不改变 control enabled 状态。

### `core/input/click_pipeline.py`
职责：承接 `MotionController._execute_click()` 的完整点击流程编排。
关键导出：`execute_click`。
对外依赖：`core.input.click_diagnostics`、`core.input.click_executor`。
注意事项：该模块接收 `MotionController` 实例，按旧顺序执行 bottom guard、可选 clamp、窗口诊断、可选 focus、pydirectinput cursor 诊断、真实点击、点击后 cursor 诊断和 fallback。它仍通过 controller 的兼容 wrapper 写 `last_click_info`，所以公开字段结构不变。

### `core/input/screen_bounds.py`
职责：封装屏幕高度解析和点击坐标 clamp 的纯计算。
关键导出：`screen_height_from_driver_or_size`、`clamp_screen_pos`。
对外依赖：无内部业务模块依赖。
注意事项：`screen_height_from_driver_or_size()` 优先使用 Win32 driver 的 `screen_height`，否则使用 `pydirectinput.size()` 结果。`clamp_screen_pos()` 只在调用方开启 `clamp_to_screen` 时被使用；默认导航仍不强制 clamp，避免坐标系误判时把目标改到屏幕边缘。

### `gui/dialogs/nav_params_dialog.py`
职责：导航参数弹窗主类，负责 tab 构建、控件信号、配置写回、保存信号和屏幕信息适配。
关键导出：`NavParametersDialog`。
对外依赖：`gui.navigation_params`、`gui.dialogs.nav_params.config_binding`、`gui.dialogs.nav_params.screen_estimator`。
注意事项：控件到 `NavConfig` 的字段路径、文本解析、dataclass replace 和控件回填已迁入 `config_binding.py`；`NavParametersDialog` 仍保留旧 public class、Qt signal、tab/layout 构造、状态文案、保存按钮和 Qt 屏幕边界读取。`set_config_to_ui()` 仍在 dialog 层使用 `QSignalBlocker` 阻塞程序化写入时的控件信号。

### `gui/dialogs/nav_params/__init__.py`
职责：导航参数弹窗 helper 包入口，集中 re-export 字段规格和配置绑定 helper。
关键导出：`FieldSpec`、`BOUND_FIELD_SPECS`、`TEXT_FIELD_SPECS`、`VALUE_FIELD_SPECS`、`connect_config_bindings`、`parse_config_text_value`、`replace_config_value`、`write_config_to_widgets`。
对外依赖：`gui.dialogs.nav_params.field_specs`、`gui.dialogs.nav_params.config_binding`。
注意事项：只做包级入口，不直接承载 UI 或配置算法。

### `gui/dialogs/nav_params/field_specs.py`
职责：定义导航参数可编辑字段规格，统一描述 dialog 控件属性名、`NavConfig` 字段路径、字段类别、控件写入方式和分组。
关键导出：`FieldSpec`、`TEXT_FIELD_SPECS`、`VALUE_FIELD_SPECS`、`BOUND_FIELD_SPECS`、`resolve_widget`、`config_value`。
对外依赖：`gui.navigation_params`。
注意事项：当前只覆盖会参与 `parameters_changed` 的可编辑绑定字段；`draw_scale`、`monitor_region`、`game_screen_center` 等只读或格式化显示仍留在 `config_binding.py`，避免规格表过早混入 presentation 文案。

### `gui/dialogs/nav_params/config_binding.py`
职责：承载导航参数对话框的字段绑定规则、信号连接、文本解析、不可变配置替换和控件回填。
关键导出：`value_field_bindings`、`text_field_bindings`、`connect_config_bindings`、`replace_config_value`、`parse_config_text_value`、`write_config_to_widgets`。
对外依赖：`gui.navigation_params`、`gui.dialogs.nav_params.field_specs`。
注意事项：可编辑字段的控件解析、路径解析和回填顺序来自 `field_specs.py`；`QSignalBlocker` 不在这里创建，继续由 dialog 控制程序化回填期间的信号阻断语义。只读显示字段的格式化仍在本模块。

### `gui/dialogs/nav_params/screen_estimator.py`
职责：封装从屏幕中心和物理屏幕边界推导最小/最大点击半径的纯策略。
关键导出：`ClickRadiusEstimate`、`estimate_click_radii`。
对外依赖：无内部业务模块依赖；只使用标准库 typing。
注意事项：函数不依赖 Qt，也不读写控件；中心点不在屏幕边界内时返回 `None`，由 dialog 显示失败状态。

### `gui/dialogs/event_manager_dialog.py`
职责：独立事件管理窗口，用于测试、运行时观察事件系统，并通过 Hooks 页编辑 hook 实例。
关键导出：`EventManagerDialog`。
对外依赖：`core.events.config.build_tui_event_options`、`gui.dialogs.event_manager.hooks.EventHookPanel`。
注意事项：窗口现在使用 `QTabWidget` 分为“事件”和“Hooks”两页。事件选配表只展示 registry 提供的完整事件包，不暴露 detector、confirmer、handler 等内部步骤。任务表从 `EventCoordinator.tasks()` 刷新，展示 ID、事件类型、状态、识别次数、置信度、地图坐标、尝试次数和最近识别时间。Hooks 页编辑 `event_config.hooks.instances`。完整 `refresh()` 会重建事件表、参数控件和 hook 面板；运行中高频更新使用 `refresh_tasks()` 只刷新任务表。选中事件后，参数面板根据 `config_schema()` 自动生成控件，并只按字段级 `compact`/`summary` 元数据决定紧凑视图和摘要；通用 dialog 不维护任何具体游戏参数白名单。`manual_test_requested` 与 `reset_events_requested` 都是领域中立信号。

### `gui/dialogs/event_manager/hooks/panel.py`
职责：事件管理窗口的独立 Hooks 页，编辑 hook 实例配置。
关键导出：`EventHookPanel`。
对外依赖：`core.events.hooks`、`core.events.hooks.instances`。
注意事项：该面板只操作 `EventSystemConfig.hooks["instances"]`，不直接注册 handler、不执行输入、不依赖 `NavigationTaskController`。面板从事件管理窗口传入的完整事件列表动态生成事件绑定列，写入 `event_types`。新增按钮创建一个启用的 key_press 实例，默认按键为 `d`，默认绑定第一个可用事件并挂到 `event_visible_target`；用户可同时勾选多个事件类型，也可同时勾选 `event_visible_target` 和 `event_completed`。未绑定事件类型的实例不会触发。删除按钮移除当前选中实例。所有变化只发出 `hooks_changed`，由外层 dialog 转为 `config_changed`。

### `gui/dialogs/advanced_settings_dialog.py`
职责：高级参数弹窗主类，负责 tab 构建、按钮/文件对话框连接、参数文件选择和 recognizer/stitcher 实时应用时机。
关键导出：`AdvancedSettingsDialog`。
对外依赖：`gui.dialogs.advanced_settings.file_io`、`gui.dialogs.advanced_settings.params_adapter`。
注意事项：`load_current_params()`、`apply_params()`、`reset_to_default()`、`apply_loaded_params()`、`apply_preset()` 原入口保留，内部委托参数映射 helper。`apply_params()` 现在先发出 `apply_params_requested(dict)` command signal；已迁移 owner 可调用 `use_external_apply_handler()` 禁用 dialog 内部 direct runtime mutation。参数 snapshot 的 JSON 格式、文件名清洗、目录创建和读取校验由 `advanced_settings/file_io.py` 维护；本类仍负责打开 `QFileDialog`、更新状态文案，并为未迁移调用方保留 `_apply_params_directly()` fallback。

### `gui/dialogs/advanced_settings/__init__.py`
职责：高级参数弹窗 helper 包标识。
关键导出：无。
对外依赖：无。
注意事项：空包入口只服务内部模块命名空间，不承载业务逻辑。

### `gui/dialogs/advanced_settings/file_io.py`
职责：封装高级参数 JSON snapshot 的保存、加载、展示格式化和默认输出目录。
关键导出：`advanced_settings_output_dir`、`save_params_snapshot`、`load_params_snapshot`、`format_params_for_display`。
对外依赖：无内部业务模块依赖；只使用标准库 `json/pathlib/datetime/re`。
注意事项：默认目录为项目根 `configs/advanced_settings/`，不再写进程当前工作目录。保存文件名使用清洗后的参数名，payload 仍保留用户原始 `name`、ISO `timestamp` 和 `parameters` 字段。加载时要求顶层 JSON 是 object，且 `parameters` 必须是 object；错误向调用方抛出，由 dialog 显示。

### `gui/dialogs/advanced_settings/params_adapter.py`
职责：封装高级参数弹窗控件与参数 dict/预设之间的双向映射。
关键导出：`load_params_to_widgets`、`collect_params_from_widgets`、`reset_widgets_to_default`、`apply_loaded_params_to_widgets`、`apply_preset_to_widgets`。
对外依赖：`gui.dialogs.advanced_settings.presets`。
注意事项：该模块不保存参数文件、不读取 JSON、不调用 recognizer/stitcher。`reset_widgets_to_default()` 保持旧 reset 字段集合，不额外写 `blur_strength_spin`；`load_params_to_widgets()` 仍写入 `blur_strength_spin=3`，保持旧加载当前参数行为。预设名称和值来自 `presets.py`，但写控件仍依赖 dialog attribute names。

### `gui/dialogs/advanced_settings/presets.py`
职责：封装高级参数预设的用户可见顺序和控件赋值数据。
关键导出：`DEFAULT_PRESET_NAME`、`PRESET_NAMES`、`PRESET_VALUES`、`preset_names`、`preset_values`。
对外依赖：无内部业务模块依赖；只使用标准库 `MappingProxyType`。
注意事项：默认预设不在 `PRESET_VALUES` 里，因为它仍代表“完整 reset”，由 `params_adapter.apply_preset_to_widgets()` 委托 `reset_widgets_to_default()`。非默认预设只记录旧实现实际写入的控件值，不额外扩展字段。

### `gui/dialogs/color_picker_dialog.py`
职责：交互式颜色选择弹窗，负责采样点交互、模式切换、HSV 计算流程、预览刷新和结果返回。
关键导出：`ColorPickerDialog`。
对外依赖：`core.vision.HSVRecognizer`、`gui.widgets.clickable_label.ClickableImageLabel`、`gui.dialogs.color_picker.debug_output`、`gui.dialogs.color_picker.hsv_ranges`、`gui.dialogs.color_picker.image_renderer`、`gui.dialogs.color_picker.preview`。
注意事项：`calculate_hsv_ranges()`、`_calculate_range()`、`_show_image()` 原入口保留，内部委托 helper。`update_preview()` 现在调用 `color_picker/preview.py::build_wall_preview()` 获取 mask 和统计结果，本类只负责把 mask 显示到 preview label，并在 `MINIMAP_COLOR_PICKER_DEBUG=1` 时把 preview 结果传给 `debug_output.py` 写入 `debug/color_picker/`。当前 preview 只复刻旧 wall mask 行为，不新增 player mask 预览。

### `gui/dialogs/color_picker/__init__.py`
职责：颜色选择弹窗 helper 包标识。
关键导出：无。
对外依赖：无。
注意事项：空包入口只服务内部模块命名空间，不承载业务逻辑。

### `gui/dialogs/color_picker/debug_output.py`
职责：封装颜色选择预览 debug 图片和文本日志的 opt-in 开关、输出目录与文件写入。
关键导出：`DEBUG_ENV_VAR`、`is_wall_preview_debug_enabled`、`write_wall_preview_debug`。
对外依赖：无内部业务模块依赖；只使用 OpenCV 和标准库 pathlib/os。
注意事项：默认不会生成 `preview_result_*.png`、`preview_before_morph_*.png`、`preview_log_*.txt`；只有 `MINIMAP_COLOR_PICKER_DEBUG` 为 `1/true/yes/on` 时，`ColorPickerDialog.update_preview()` 才调用写入逻辑，输出目录为 `debug/color_picker/`。

### `gui/dialogs/color_picker/hsv_ranges.py`
职责：封装颜色选择弹窗中的 BGR->HSV 转换、采样点 HSV 提取、HSV 范围计算和平均饱和度计算。
关键导出：`bgr_to_hsv`、`hsv_values_at_points`、`calculate_hsv_range`、`mean_saturation`。
对外依赖：无内部业务模块依赖；只使用 OpenCV/Numpy。
注意事项：`calculate_hsv_range()` 保持旧算法：均值、标准差、`max(std*2, [5,20,20])` 容差、HSV 边界 `[0,0,0]` 到 `[179,255,255]`。

### `gui/dialogs/color_picker/image_renderer.py`
职责：封装颜色选择弹窗中的 OpenCV 图像转 QPixmap 和采样 marker 绘制。
关键导出：`pixmap_from_image`、`draw_sample_markers`。
对外依赖：无内部业务模块依赖；只使用 OpenCV 和 PySide6 图像绘制类。
注意事项：灰度图仍使用 `QImage.Format_Grayscale8`，彩色图仍 BGR 转 RGB；marker 颜色、半径、缩放公式和 label 固定尺寸逻辑保持原 `_show_image()` 行为。

### `gui/dialogs/color_picker/preview.py`
职责：构造颜色选择弹窗右侧 wall HSV 二值预览 mask，并返回形态学处理前后统计。
关键导出：`WallPreviewResult`、`build_wall_preview`。
对外依赖：无内部业务模块依赖；使用 OpenCV/Numpy。
注意事项：只实现旧 `update_preview()` 已有的 wall mask 路径：BGR->HSV、`cv2.inRange()`、3x3 close、白色像素统计和 debug 所需字段。不负责 QLabel 显示、不判断 debug env、不写文件。

### `gui/modes/navigation/widget.py`
职责：导航模式 QWidget 组合根和临时 facade，负责持有跨模块运行态、调用 UI builder/signal binder，并委托 composition module 创建 lifecycle/controller。
关键导出：`NavigationModeWidget`。
对外依赖：`MotionController`、`NavigationTaskController`、`RouteManager`、`navigation.composition`、`navigation.event_adapter`、`navigation.presentation`、`navigation.input`、`navigation.map`、`navigation.route`、`navigation.events`、`navigation.ui`。
注意事项：绿色框来自 `capture_rect * draw_scale`，表示小地图截图定位范围；橙色框来自 `game_view_map_size`，表示主游戏画面真实可见/可交互范围。路线编辑分为两类点：`required_points` 是必须按顺序完成的阶段门；`guide_points` 是有序软锚点/辅助走廊，只在 `MovementExecutor` 规划 required、exit 或 event 目标时塑形路线，不作为独立导航目标。route JSON 编辑和 click mode 状态已委托 `navigation/route/editor.py`；route 按钮 checked/enabled、状态栏操作提示和保存/撤销/清空命令结果已委托 `navigation/route/panel_controller.py`；保存/撤销/清空/加载 route 后的 `route_data`、`NavigationTaskController.load_route()`、overlay 刷新、状态栏文案和保存失败 warning 已委托 `navigation/route/lifecycle.py` 的 `NavigationRouteLifecycle`。顶部工具栏、`QGraphicsScene/QGraphicsView`、状态栏和 `RoutePanelController` 构建已委托 `navigation/ui/layout.py`，按钮、参数弹窗和事件弹窗信号绑定已委托 `navigation/ui/signals.py`；小地图样本按钮同样在这里创建和接线，地图加载成功后才启用。地图 item 创建/更新、定位显示更新、地图列表 combo 填充、地图加载成功 UI 写入、地图加载/overlay 配置反馈、导航配置保存结果展示、route/移动目标命令反馈、hint/calibration 反馈、事件管理结果展示、自动导航/导航启动命令反馈、路线/事件 overlay、debug 幕布窗口写入、owned dialog 显示外壳和状态栏文案构造/写入已委托 `navigation/presentation`。地图目录解析、配置读取、`NavigationCore` 创建和初始物理中心计算已通过 `navigation/map/session.py` 包装；地图加载后半段固定顺序已委托 `navigation/map/load_lifecycle.py` 的 `NavigationMapLoadLifecycle`。导航配置生命周期已委托 `navigation/config/lifecycle.py` 的 `NavigationConfigLifecycle`。屏幕中心校准已拆成两层：`navigation/calibration/screen_center.py` 只负责 selector 生命周期、DPR 读取和 logical->physical 坐标转换，`navigation/calibration/lifecycle.py` 负责配置写回、参数弹窗刷新、overlay、保存、完成提示和 selector 关闭。导航运行命令生命周期已委托 `navigation/runtime/command_lifecycle.py` 的 `NavigationRuntimeCommandLifecycle`，整帧循环已委托 `navigation/runtime/frame_loop.py` 的 `NavigationRuntimeFrameLoop`；frame loop 每帧缓存最近小地图 frame/capture_rect/player_pos，`navigation/runtime/minimap_sample_capture.py` 负责把缓存或即时截图保存为 `debug/minimap_samples/<map_name>/` 下的 PNG+JSON 样本。导航事件生命周期已委托 `navigation/events/lifecycle.py` 的 `NavigationEventLifecycle`；事件弹窗创建/接线/刷新已委托 `navigation/events/dialog_lifecycle.py`；地图加载时的事件系统 runtime bootstrap 已委托 `navigation/events/bootstrap.py`，该模块返回 `event_config`、`event_coordinator`、`event_capture_provider` 后由 widget 写回字段。事件观测 helper 返回 `event_tick` 给后续 task update；当前 hook 机制位于 core 侧，外部可通过 `NavigationTaskController.event_hooks.register(...)` 注册处理器。事件被选中后才调用 `EventCoordinator.run_task()` 推进 handler；事件 `MOVE_TO` 与普通目标共用同一个 `MovementExecutor`，事件 `PRESS_KEY/CLICK_SCREEN` 统一委托 `navigation/input/intent_executor.py` 消费。路线 overlay 与事件 overlay 的 QGraphicsItem 创建/清理由 `gui/modes/navigation/presentation/route_overlay.py` 和 `presentation/event_overlay.py` 承担，旧根路径 overlay 模块已删除。本文件不再打印每帧“当前位置/位置来源”调试块；旧长 docstring 已压缩，避免 wrapper 注释继续描述已下沉的内联实现。导航/事件操作过程走 `logs/event_runtime.log`。初始化顺序已调整为先创建 route/config/runtime 状态对象，再调用 UI builder，避免 `RoutePanelController` 依赖未初始化的 `RouteEditor`。
显示链补充：`navigation/display/lifecycle.py::NavigationMapDisplayLifecycle` 现在承接 scene item 引用写回、route/event overlay 清理和渲染、绿色监控框、橙色视野框、上次退出位置 marker；`NavigationModeWidget._render_map()`、`_render_route_overlay()`、`_render_event_overlay()`、`_update_monitor_rect()`、`_update_game_view_rect()`、`_show_last_exit_position()` 等旧方法只保留 wrapper。
组合链补充：`navigation/composition/lifecycles.py` 现在承接 display/config/route/events/map/runtime/calibration lifecycle 的 targets wiring。`NavigationModeWidget.__init__()` 只保留基础字段初始化、`init_ui()`、pre-signal lifecycle 初始化、signal wiring 和 runtime lifecycle 初始化四段顺序。

### `gui/modes/navigation/composition/__init__.py`
职责：导航局部 composition 包入口。
关键导出：`initialize_navigation_pre_signal_lifecycles`、`initialize_navigation_runtime_lifecycles`。
对外依赖：`navigation.composition.lifecycles`。
注意事项：只聚合导出，不承载业务逻辑。
### `gui/modes/navigation/composition/lifecycles.py`
职责：集中导航页 lifecycle/controller 的 wiring 顺序。
关键导出：`initialize_navigation_pre_signal_lifecycles(owner)`、`initialize_navigation_runtime_lifecycles(owner)`。
对外依赖：`PySide6.QtCore.QTimer`、`navigation.calibration`、`navigation.config`、`navigation.display`、`navigation.events`、`navigation.map`、`navigation.route`、`navigation.runtime`。
注意事项：这是 navigation 局部 composition module，不实现算法、不处理用户命令。`initialize_navigation_pre_signal_lifecycles()` 必须在 `_connect_signals()` 前执行，创建 display/event-dialog/route/config/calibration/map-load lifecycle；`initialize_navigation_runtime_lifecycles()` 必须在 `_connect_signals()` 后执行，创建 `QTimer`、通用 manual-event controller、runtime command/event/map-click lifecycle 和 `NavigationRuntimeFrameLoop`。这个模块暂时持有 owner 访问以避免超大构造参数，后续若要增强复用性，应先收窄 owner 依赖。

### `gui/modes/navigation/ui/__init__.py`
职责：导航 UI shell 包导出。
关键导出：`build_navigation_ui`、`connect_navigation_signals`。
对外依赖：`navigation.ui.layout`、`navigation.ui.signals`。
注意事项：只聚合导出，不承载业务逻辑。

### `gui/modes/navigation/ui/layout.py`
职责：构建导航页的 Qt 控件树和初始图形项字段。
关键导出：`build_navigation_ui(owner)`。
对外依赖：`navigation.route.RoutePanelController`。
注意事项：该 helper 只创建 UI 对象并挂回 owner 字段；会调用 `owner.refresh_map_list()` 填充地图下拉框，并创建 `owner.route_panel`。`save_minimap_sample_button` 初始禁用，必须等地图加载成功后由 widget 启用。它不连接信号、不加载地图、不启动导航。

### `gui/modes/navigation/ui/signals.py`
职责：集中绑定导航页按钮、参数弹窗和事件弹窗信号。
关键导出：`connect_navigation_signals(owner)`。
对外依赖：无内部业务模块依赖。
注意事项：绑定目标仍是 `NavigationModeWidget` 的旧 slot/wrapper，保证迁移期外部行为不变；小地图样本按钮连接到 `owner.save_minimap_sample()`；事件弹窗信号通过 `owner._connect_event_dialog_signals()` 复用已有重连逻辑。

### `gui/modes/navigation/display/__init__.py`
职责：导航地图显示生命周期包导出。
关键导出：`NavigationMapDisplayLifecycle`。
对外依赖：`navigation.display.lifecycle`。
注意事项：只聚合导出，不承载业务逻辑。

### `gui/modes/navigation/display/lifecycle.py`
职责：集中管理导航地图 scene item 和 overlay 的 owner 字段写回。
关键导出：`NavigationMapDisplayLifecycle`。
对外依赖：`navigation.presentation`。
注意事项：这是 GUI display lifecycle，不是纯 presentation helper；它串联 `presentation` 里的小绘制函数，并维护 `NavigationModeWidget` 上的 `route_overlay_items`、`event_overlay_items`、`route_path_item`、`map_item`、`player_item`、`monitor_rect_item`、`game_view_rect_item` 等引用。它不加载地图、不定位、不启动导航。
### `gui/modes/navigation/input/__init__.py`
职责：导航输入 adapter 包导出。
关键导出：`GameInputWindowMode`、`NavigationIntentExecutionResult`、`execute_navigation_intent`。
对外依赖：`navigation.input.window_mode`、`navigation.input.intent_executor`。
注意事项：只聚合导出，不承载业务逻辑。
### `gui/modes/navigation/input/window_mode.py`
职责：自动导航或事件输入期间，管理主窗口取消置顶、降低到游戏窗口后方、停止后恢复置顶状态。
关键导出：`GameInputWindowMode`。
对外依赖：无内部业务模块依赖；使用 PySide6 `Qt.WindowStaysOnTopHint`。
注意事项：这是 GUI 专属 input seam；不发送鼠标键盘输入，只维护窗口状态。`set_enabled(True)` 第一次记录原 topmost 状态并 lower 主窗口；`set_enabled(False)` 只在此前启用过时恢复，避免停止命令反复改窗口 flag。
### `gui/modes/navigation/input/intent_executor.py`
职责：把统一导航任务层输出的 `NavigationIntent` 翻译为 typed 导航组合动作，再委托对应 compatibility backend。
关键导出：`NavigationIntentExecutionResult`、`execute_navigation_intent`。
对外依赖：`core.input.MotionControllerActionAdapter`、`navigation.input.actions`。
注意事项：`translate_navigation_intent()` 将 `MOVE_MAP` 保持为 `MapMovementAction`，因此仍会启用游戏输入和 motion control，并按旧分支调用 `click_map_target_once()` 或 `move_to_map_target()`；成功点击后的 `NavigationTaskController.record_intent_click()` 与状态栏半径文本不变。`CLICK_SCREEN` 被显式声明为 `PHYSICAL_SCREEN` identity-mapped `CLICK`，`PRESS_KEY` 被转为一键 `KEY_CHORD`；二者均经 `MotionControllerActionAdapter` 回到历史 control/focus/backend policy。缺少/非法 payload 仍静默 no-op。

### `gui/modes/navigation/input/actions.py`
职责：在 GUI navigation composition 层明确区分 stitched-map movement 和通用设备 primitive，而不让地图坐标伪装成物理鼠标坐标。
关键导出：`MapMovementAction`、`PrimitiveNavigationAction`、`translate_navigation_intent`。
对外依赖：`core.actions`、`core.navigation_tasks.models.NavigationIntentType`、`core.spatial.physical_screen_point`。
注意事项：只接受可执行的 `MOVE_MAP`、`CLICK_SCREEN`、`PRESS_KEY`；`NONE/WAIT`、缺失或无效 payload 返回 `None`。`CLICK_SCREEN` 是唯一在此 legacy edge 被明确声明为已有 `PHYSICAL_SCREEN` 坐标的 intent；未来游戏窗口/viewport 坐标必须先经独立 mapper 进入本层。该模块没有输入副作用。
### `gui/modes/navigation/hooks/__init__.py`
职责：导航 hook runtime 注册包入口。
关键导出：`NavigationHookRuntime`。
对外依赖：`navigation.hooks.registration`。
注意事项：只聚合导出，不承载业务逻辑。
### `gui/modes/navigation/hooks/registration.py`
职责：把 `EventSystemConfig.hooks.instances` 中的 hook 实例注册到 `NavigationTaskController.event_hooks`。
关键导出：`NavigationHookRuntime`。
对外依赖：`core.events.hooks.instances`。
注意事项：该模块是 GUI 组合根与 core hook registry 的 adapter。`apply_event_config()` 会先注销上一轮由本 runtime 注册的 handler，再按当前配置注册 enabled key_press 实例；实例必须同时有 `event_types` 和 `triggers` 才会注册，避免 hook 默认对所有事件生效。一个实例的 `triggers` 可包含 `event_visible_target` 和 `event_completed`，因此同一个按键 hook 可同时挂两个触发点。按键执行通过注入的 `enable_game_input_mode()`、`MotionController.set_control_enabled(True)` 和统一的一键 `ActionCommand → MotionControllerActionAdapter` 完成，不让 core hook 实例直接依赖 GUI 或平台输入。
### `NavigationHookRuntime.apply_event_config(self, event_config) -> int`
行为：根据当前事件配置重建 hook handler 注册。
算法：1. 调用 `clear()` 注销本 runtime 之前注册的所有 handler。2. 读取 `event_config.hooks["instances"]`，忽略非 dict 或未知类型。3. 对 `type="key_press"` 的实例调用 `key_press_settings_from_dict()` 规范化配置。4. 跳过未启用、空 key、无 `event_types` 或无 triggers 的实例。5. 创建 `KeyPressHookInstance(settings, self._press_key_once)`，并对实例的每个 trigger 调用 `navigation_task_controller.event_hooks.register()`。6. 返回本次注册的 trigger 数量。
副作用：修改 `NavigationTaskController.event_hooks` 的 handler 列表；后续 hook 触发时可能通过 `MotionController.press_key()` 发送一次按键。
失败行为：未知实例类型静默忽略；handler 运行时异常由 core `EventHookRegistry.emit()` 捕获。
调用关系：called by `NavigationModeWidget._initialize_event_system()` after map event config load, and `NavigationModeWidget._on_event_config_changed()` after GUI edits hook/event config。
### `gui/modes/navigation/config/__init__.py`
职责：导航配置生命周期包入口。
关键导出：`NavigationConfigLifecycle`、`NavigationConfigLifecycleTargets`。
对外依赖：`navigation.config.lifecycle`。
注意事项：只聚合导出，不承载业务逻辑。
### `gui/modes/navigation/config/lifecycle.py`
职责：集中导航配置生命周期：参数变化、runtime 应用、task controller 同步、当前地图保存、默认配置保存和 UI 反馈顺序。
关键导出：`NavigationConfigLifecycleTargets`、`NavigationConfigLifecycle`。
对外依赖：`navigation.map.config_applier`、`navigation.map.config_store`、`navigation.presentation.config_save_state`。
注意事项：这是比单个 helper 更深的 GUI config module。它通过 targets DTO 接收 parent、source file、状态 label、runtime 对象和 widget 回调，不直接持有 `NavigationModeWidget` 类型；保存/应用/刷新顺序集中在 `NavigationConfigLifecycle`，旧 widget 方法保留 wrapper。
### `gui/modes/navigation/map/__init__.py`
职责：导航地图/config adapter 包导出。
关键导出：`MISSING_MAP_DATA_LABEL`、`NavigationMapClickLifecycle`、`NavigationMapClickLifecycleTargets`、`NavigationMapLoadLifecycle`、`NavigationMapLoadLifecycleTargets`、`NavigationMapLoadSession`、`NavigationMapSettings`、`apply_motion_controller_config`、`apply_navigation_config_to_core`、`build_capture_geometry`、`configure_navigation_task_controller`、`create_navigation_core`、`handle_navigation_map_event_filter`、`initial_capture_center_for_config`、`list_map_names`、`load_navigation_map_settings`、`load_nav_config`、`physical_center_from_logical`、`prepare_navigation_map_load_session`、`resolve_map_folder`、`save_default_nav_config`、`save_nav_config`。
对外依赖：`navigation.map.config_applier`、`navigation.map.config_store`、`navigation.map.capture_geometry`、`navigation.map.session`、`navigation.map.load_lifecycle`、`navigation.map.click_lifecycle`、`navigation.map.event_filter`。
注意事项：只聚合导出，不承载业务逻辑。
### `gui/modes/navigation/map/click_lifecycle.py`
职责：集中导航地图点击生命周期：hint 放置、route 编辑、手动移动目标设置、坐标转换、marker/overlay/status 更新。
关键导出：`NavigationMapClickLifecycleTargets`、`NavigationMapClickLifecycle`。
对外依赖：`navigation.presentation.calibration_feedback`、`navigation.presentation.route_command_state`、`navigation.presentation.map_presenter`。
注意事项：这是 map package 内的交互深模块。它通过 targets DTO 接收 view/scene/button、route editor、motion controller 和 widget 回调，不直接持有 `NavigationModeWidget`；分支顺序保持旧行为：hint mode 优先，其次 route editor click mode，最后才是手动移动目标。手动移动目标必须已经定位，失败只弹 warning，不调用 `MotionController`。
### `gui/modes/navigation/map/session.py`
职责：封装导航地图加载前置 session 操作：解析 map folder、读取导航配置、创建 `NavigationCore` 并计算初始物理中心。
关键导出：`NavigationMapSettings`、`NavigationMapLoadSession`、`load_navigation_map_settings`、`create_navigation_core`、`prepare_navigation_map_load_session`。
对外依赖：`core.localization.NavigationCore`、`navigation.map.config_store.load_nav_config`、`navigation.map.config_store.resolve_map_folder`、`navigation.map.capture_geometry.initial_capture_center_for_config`。
注意事项：该模块刻意不应用配置、不弹 QMessageBox、不刷新参数弹窗、不初始化事件系统、不渲染地图；这些副作用由 `navigation.map.load_lifecycle.NavigationMapLoadLifecycle` 按旧顺序执行。`NavigationMapLoadSession` 只承载 map name/folder、`nav_config`、`config_exists`、`nav_core`、`capture_center_physical` 和参数弹窗需要的 `physical_center`。
### `gui/modes/navigation/map/load_lifecycle.py`
职责：集中导航地图加载生命周期的 GUI 编排：准备 map session、写入 widget runtime 状态、应用配置、回填参数弹窗、加载路线、初始化事件系统、渲染地图/退出点/路线覆盖层并启用加载完成 UI。
关键导出：`NavigationMapLoadLifecycleTargets`、`NavigationMapLoadLifecycle`。
对外依赖：`navigation.map.session.prepare_navigation_map_load_session`、`navigation.presentation.map_load_state`。
注意事项：这是 map package 内的深模块，不是 presentation helper。它通过 targets DTO 接收 widget 回调和 UI 控件引用，隐藏加载后半段的顺序敏感副作用；`NavigationModeWidget.load_map()` 保留旧入口但不再内联缺配置提示、参数回填、route/event/render/UI 启用顺序。该模块不直接 import `NavigationModeWidget` 类型，也不改变 `NavConfig` 应用规则。
### `gui/modes/navigation/map/config_applier.py`
职责：集中执行 `NavConfig` 到导航运行对象的写入规则。
关键导出：`apply_navigation_config_to_core`、`apply_motion_controller_config`、`configure_navigation_task_controller`。
对外依赖：`core.events.debug.event_log`。
注意事项：`map_data.npz` 中的 `map_draw_scale` 仍是定位缩放权威；当 `nav_config.draw_scale` 不一致时记录 `navigation draw_scale config mismatch` 并修正内存配置。该模块负责 recognizer 参数、导航墙层重建、PathFinder start/snap 半径、MotionController 屏幕中心/点击半径、NavigationTaskController movement/event approach/coordinate diagnostics 参数写入，但不弹窗、不改按钮。
### `gui/modes/navigation/map/event_filter.py`
职责：封装导航地图 scene 的 Qt 鼠标事件解释。
关键导出：`handle_navigation_map_event_filter`。
对外依赖：`PySide6.QtCore.QEvent`、`PySide6.QtCore.Qt`。
注意事项：只识别 watched scene 上的左键 `GraphicsSceneMousePress`，把 `event.scenePos()` 交给注入的 `handle_map_click` 回调并返回 `True`；其他事件返回 `False`，由 widget 的 `super().eventFilter()` 继续处理。该 helper 不知道 hint/route/manual move 语义，真实点击优先级仍在 `NavigationMapClickLifecycle`。
### `gui/modes/navigation/route/__init__.py`
职责：导航 route editing adapter 包导出。
关键导出：`MapClickMode`、`RouteEditResult`、`RouteEditor`、`NavigationRouteLifecycle`、`NavigationRouteLifecycleTargets`、`RouteCommandResult`、`RoutePanelController`。
对外依赖：`navigation.route.editor`、`navigation.route.lifecycle`、`navigation.route.panel_controller`。
注意事项：只聚合导出，不承载业务逻辑。
### `gui/modes/navigation/route/editor.py`
职责：集中导航 route click mode 和 `route.json` 编辑命令，使 UI 主类不直接改 route 数据结构。
关键导出：`MapClickMode`、`RouteEditResult`、`RouteEditor`。
对外依赖：无内部业务模块依赖；运行时接收 `RouteManager` 实例。
注意事项：`RouteEditor` 不触碰 Qt 按钮、scene、status label 或 `NavigationTaskController`；它只更新 `RouteManager` 缓存/route.json 数据并返回 `RouteEditResult`。设置出口后会把 click mode 复位为 `NONE`；添加必经点/途经点会保持当前模式，延续连续添加行为。
### `gui/modes/navigation/route/lifecycle.py`
职责：封装导航页 route 命令结果同步生命周期。
关键导出：`NavigationRouteLifecycleTargets`、`NavigationRouteLifecycle`。
对外依赖：`navigation.presentation.show_route_command_status`、`navigation.presentation.warn_route_save_failed`；通过 targets 注入 `RouteEditor`、`RoutePanelController` 和 `NavigationTaskController`。
注意事项：`RoutePanelController` 仍负责按钮/click mode 和 route editor 命令结果；本 lifecycle 只负责把成功结果同步到 `NavigationModeWidget.route_data`、`NavigationTaskController.load_route()`、route overlay 和状态栏。保存失败保持旧 warning；未加载地图时不会弹窗。
### `gui/modes/navigation/route/panel_controller.py`
职责：封装导航 route 相关按钮状态、操作提示文案和 route editor 命令结果。
关键导出：`RouteCommandResult`、`RoutePanelController`。
对外依赖：`navigation.route.editor.MapClickMode`、`RouteEditor`。
注意事项：该 controller 接收具体按钮和 status label 引用，但不弹 QMessageBox、不绘制 overlay、不知道 `NavigationTaskController`。保存失败时只返回 `saved=False`，由 `NavigationRouteLifecycle.save_route()` 继续弹原警告；保存/撤销/清空成功后返回 route_data 和旧状态栏文案，lifecycle 负责同步 controller route 和重绘。
### `gui/modes/navigation/events/__init__.py`
职责：导航事件 UI adapter 包导出。
关键导出：`ManualEventTestController`、`NavigationEventSystemRuntime`、`initialize_navigation_event_system`、`NavigationEventDialogLifecycle`、`NavigationEventDialogLifecycleTargets`、`NavigationEventLifecycle`、`NavigationEventLifecycleTargets`、`summarize_event_config`。
对外依赖：`navigation.events.bootstrap`、`navigation.events.dialog_lifecycle`、`navigation.events.manual_test_controller`、`navigation.events.lifecycle`、`navigation.events.panel_adapter`。
注意事项：只聚合导出，不承载业务逻辑。
### `gui/modes/navigation/events/bootstrap.py`
职责：封装导航地图加载后的事件系统 runtime 初始化。
关键导出：`NavigationEventSystemRuntime`、`initialize_navigation_event_system`。
对外依赖：`core.events.capture_provider.GameWindowCaptureProvider`、`core.events.config.load_event_config`、`core.events.coordinator.EventCoordinator`、`core.events.debug.event_log`、`navigation.events.panel_adapter.summarize_event_config`。
注意事项：这是 map-load 阶段的事件 runtime bootstrap，不触碰路线、timer、输入或 Qt 按钮状态。无 `map_folder_path` 时返回三项空 runtime；有地图时按旧顺序读取 event config、创建 coordinator/capture provider、刷新事件弹窗、写初始化日志，再把三个对象交给 widget 写回。
### `gui/modes/navigation/events/dialog_lifecycle.py`
职责：封装事件管理弹窗创建、信号连接、刷新、显示切换和手动测试按钮同步。
关键导出：`NavigationEventDialogLifecycleTargets`、`NavigationEventDialogLifecycle`。
对外依赖：`navigation.presentation.toggle_owned_dialog`、`navigation.events.panel_adapter.create_event_dialog/connect_event_dialog_signals/refresh_event_dialog`。
注意事项：不保存配置、不重置 portal、不启动手动测试；只持有通过 targets 传入的 dialog getter/setter 和回调。首次创建 dialog 后同步 `ManualEventTestController.button`，避免弹窗延迟创建导致按钮状态丢失。
### `gui/modes/navigation/events/manual_test_controller.py`
职责：维护手动事件测试按钮的 active 状态、文案和 checked 状态。
关键导出：`ManualEventTestController`。
对外依赖：无内部业务模块依赖；只依赖传入 button 对象具备 `setText/isChecked/setChecked`。
注意事项：该控制器不决定事件类型、不启动导航、不调用输入执行器；`button=None` 时仍能维护 active 状态，适合 dialog 尚未创建时使用。
### `gui/modes/navigation/events/lifecycle.py`
职责：集中导航事件生命周期：事件配置保存、portal 状态重置、event move runtime reset、portal 手动测试启动/停止、overlay/dialog 刷新和事件日志。
关键导出：`NavigationEventLifecycleTargets`、`NavigationEventLifecycle`。
对外依赖：`core.events.config.save_event_config`、`core.events.debug.event_log`、`core.events.debug.start_event_log_session`、`navigation.presentation.event_management_state`。
注意事项：这是 events 包内的深模块。它通过 targets DTO 接收 widget/runtime 回调和 UI 对象，不直接 import `NavigationModeWidget`；手动 portal 测试仍复用正式事件 pipeline，只把任务控制器切到 manual-event-only 输入源，真实事件选择和 intent 执行仍在导航循环/task controller/input executor 中。停止手动测试时会重置 movement 与 event approach runtime；若自动导航仍启用，不关闭游戏输入窗口模式。
### `gui/modes/navigation/events/panel_adapter.py`
职责：封装事件管理窗口创建、信号重连、上下文刷新和配置摘要。
关键导出：`create_event_dialog`、`connect_event_dialog_signals`、`refresh_event_dialog`、`summarize_event_config`。
对外依赖：`gui.dialogs.event_manager_dialog.EventManagerDialog`、`navigation.event_adapter.event_config_summary`。
注意事项：该模块不保存 event_config、不重置 portal state、不推进 event handler；它只处理 UI wiring。`connect_event_dialog_signals()` 会先尝试 disconnect 再 connect，避免重复连接导致一次按钮点击触发多次 slot。
### `gui/modes/navigation/presentation/__init__.py`
职责：导航 presentation helper 包导出。
关键导出：`apply_map_loaded_ui`、`populate_map_combo`、`warn_map_config_missing`、`show_map_load_failed`、`warn_overlay_map_config_incomplete`、`show_initial_hint_set`、`show_hint_mode_status`、`show_screen_center_calibrated`、`mark_nav_params_dirty`、`warn_nav_config_missing_map`、`show_nav_config_saved`、`show_nav_config_save_failed`、`warn_default_nav_config_missing`、`show_default_nav_config_saved`、`show_default_nav_config_save_failed`、`warn_event_config_missing`、`show_event_config_saved`、`show_event_config_save_failed`、`warn_event_system_missing`、`warn_manual_event_test_missing_screen_center`、`show_manual_event_test_started`、`show_manual_event_test_stopped`、`warn_auto_navigation_unavailable`、`warn_auto_navigation_invalid_route`、`show_auto_navigation_started`、`show_auto_navigation_stopped`、`warn_navigation_missing_screen_center`、`warn_navigation_map_config_incomplete`、`show_navigation_started`、`show_navigation_paused`、`show_route_command_status`、`warn_route_save_failed`、`warn_move_target_requires_localization`、`show_move_target_set`、`create_map_scene_items`、`update_player_marker`、`update_monitor_rect_item`、`update_game_view_rect_item`、`create_last_position_marker`、`create_initial_hint_marker`、`set_target_marker`、`hide_item`、`show_owned_dialog`、`toggle_owned_dialog`、`update_debug_overlay`、`clear_event_overlay`、`global_to_scene`、`render_event_overlay`、`clear_route_overlay`、`render_route_overlay`、`screen_overlay_geometry`、`build_navigation_status_text`、`show_navigation_runtime_status`、`append_navigation_status_suffix`、`show_navigation_relocalizing`、`show_navigation_arrived`、`show_navigation_failed`。
对外依赖：`navigation.presentation.calibration_feedback`、`navigation.presentation.config_save_state`、`navigation.presentation.event_management_state`、`navigation.presentation.navigation_command_state`、`navigation.presentation.route_command_state`、`navigation.presentation.map_load_state`、`navigation.presentation.map_presenter`、`navigation.presentation.dialog_host`、`navigation.presentation.debug_overlay`、`navigation.presentation.status_presenter`、`navigation.presentation.event_overlay`、`navigation.presentation.route_overlay`、`navigation.presentation.viewport_overlay`。
注意事项：只聚合导出，不承载业务逻辑。
### `gui/modes/navigation/presentation/calibration_feedback.py`
职责：封装初始位置提示、hint mode 状态栏和屏幕中心校准完成弹窗。
关键导出：`show_initial_hint_set`、`show_hint_mode_status`、`show_screen_center_calibrated`。
对外依赖：无内部业务模块依赖；使用 PySide6 `QMessageBox`。
注意事项：该模块不调用 `NavigationCore.set_initial_hint()`、不更新监控/视野框、不写 `NavConfig`、不保存 config、不关闭 selector；只负责旧中文提示。
### `gui/modes/navigation/presentation/config_save_state.py`
职责：封装导航参数保存和默认配置保存后的状态标签与 QMessageBox 文案。
关键导出：`mark_nav_params_dirty`、`warn_nav_config_missing_map`、`show_nav_config_saved`、`show_nav_config_save_failed`、`warn_default_nav_config_missing`、`show_default_nav_config_saved`、`show_default_nav_config_save_failed`。
对外依赖：无内部业务模块依赖；使用 PySide6 `QMessageBox`。
注意事项：该模块不写 config、不调用 `_apply_config_to_core()`、不刷新 overlay；只展示保存链路结果。当前地图配置保存成功文案、失败文案和默认配置保存文案保持旧中文文本。
### `gui/modes/navigation/presentation/event_management_state.py`
职责：封装事件管理保存、事件系统缺失、传送门状态刷新和手动测试启动/停止的状态标签与 QMessageBox 文案。
关键导出：`warn_event_config_missing`、`show_event_config_saved`、`show_event_config_save_failed`、`warn_event_system_missing`、`warn_manual_event_test_missing_screen_center`、`show_manual_event_test_started`、`show_manual_event_test_stopped`。
对外依赖：无内部业务模块依赖；使用 PySide6 `QMessageBox`。
注意事项：该模块不保存 `event_config`、不调用 `EventCoordinator.reset_event_type()`、不启动/停止 `ManualEventTestController`、不修改 motion/input window；只负责旧中文提示与状态栏文案。
### `gui/modes/navigation/presentation/navigation_command_state.py`
职责：封装自动导航和导航启动/停止命令的状态标签与 QMessageBox 文案。
关键导出：`warn_auto_navigation_unavailable`、`warn_auto_navigation_invalid_route`、`show_auto_navigation_started`、`show_auto_navigation_stopped`、`warn_navigation_missing_screen_center`、`warn_navigation_map_config_incomplete`、`show_navigation_started`、`show_navigation_paused`。
对外依赖：无内部业务模块依赖；使用 PySide6 `QMessageBox`。
注意事项：该模块不检查路线、不启动/停止 `NavigationTaskController`、不控制 `nav_timer`、不启用/禁用 `MotionController`；只负责旧中文 warning/status 文案。
### `gui/modes/navigation/presentation/route_command_state.py`
职责：封装 route 命令状态栏、路线保存失败 warning、移动目标定位 guard 和移动目标坐标提示。
关键导出：`show_route_command_status`、`warn_route_save_failed`、`warn_move_target_requires_localization`、`show_move_target_set`。
对外依赖：无内部业务模块依赖；使用 PySide6 `QMessageBox`。
注意事项：该模块不修改 `route_data`、不保存 `route.json`、不重绘 overlay、不调用 `MotionController`；只消费调用方传入的结果文案或 scene pos。
### `gui/modes/navigation/presentation/map_load_state.py`
职责：封装地图列表 combo 填充、地图加载成功 UI 状态，以及缺配置、加载失败、overlay 配置不完整的用户反馈。
关键导出：`populate_map_combo`、`apply_map_loaded_ui`、`warn_map_config_missing`、`show_map_load_failed`、`warn_overlay_map_config_incomplete`。
对外依赖：无内部业务模块依赖；使用 PySide6 `QMessageBox`，并只依赖传入控件具备 `clear/addItems/addItem/setEnabled/setText` 或 route panel 具备 `set_buttons_enabled()`。
注意事项：不读取 `map_data`、不解析路径、不创建 `NavigationCore`、不应用配置；`populate_map_combo()` 保持旧行为：有地图时添加全部名称，无地图时添加缺省提示项。`apply_map_loaded_ui()` 保持旧中文成功文案，并只启用开始/初始位置按钮和 route panel。overlay 配置不完整时，按钮 checked 复位仍由 widget 控制，helper 只弹旧 warning。
### `gui/modes/navigation/presentation/map_presenter.py`
职责：封装导航地图 QGraphics scene 的 item 创建和常见 marker/rect 更新。
关键导出：`create_map_scene_items`、`update_player_marker`、`update_localization_view`、`update_monitor_rect_item`、`update_game_view_rect_item`、`center_view_on_global_position`、`create_last_position_marker`、`create_initial_hint_marker`、`set_target_marker`、`hide_item`。
对外依赖：`navigation.presentation.viewport_overlay.game_view_scene_rect`、`navigation.presentation.viewport_overlay.monitor_scene_rect`。
注意事项：该模块只接收 scene/view/nav_core/nav_config 和坐标，创建或更新 Qt item；不读取 route_data，不启动/停止导航，不调用输入执行器。`create_map_scene_items()` 会清空 scene 并返回 `map/player/target/monitor/game_view` item dict，调用方仍负责清空 route/event overlay 列表。`update_localization_view()` 通过回调调用 widget 的监控框/视野框更新函数，避免 presenter 直接知道 widget 私有状态，并返回新的 `player_item` 供 caller 写回。
### `gui/modes/navigation/presentation/dialog_host.py`
职责：封装导航页持有弹窗的显示、前置、恢复最小化和重复点击隐藏判定。
关键导出：`show_owned_dialog`、`toggle_owned_dialog`。
对外依赖：无内部业务模块依赖；使用 PySide6 `QApplication`、`QWidget` 和 `Qt.WindowMinimized`。
注意事项：该模块只处理 Qt shell 生命周期，不创建具体 dialog、不连接信号、不保存配置。`toggle_owned_dialog()` 在 dialog 已可见且是 active window 时返回 `True`，由旧 caller 决定 hide；否则调用 `show_owned_dialog()` 显示并前置。`show_owned_dialog()` 仅在 dialog 尚未可见且 owner 存在时按 owner frame 左上角偏移 `(80, 80)` 移动弹窗，保持旧行为。
### `gui/modes/navigation/presentation/debug_overlay.py`
职责：封装导航 debug 幕布窗口的几何写入、隐藏和显示。
关键导出：`update_debug_overlay`。
对外依赖：`navigation.presentation.viewport_overlay.screen_overlay_geometry`。
注意事项：该模块不读取按钮状态、不弹配置警告、不构造截图矩形；调用方负责传入 `capture_rect/nav_config/scale`。当 overlay 为空或几何为空时返回 `False`；几何为空会调用 `overlay.hide_overlay()`，几何有效时调用 `overlay.set_rect_and_show()` 并返回 `True`。
### `gui/modes/navigation/presentation/route_overlay.py`
职责：绘制导航路线、出口圈、必经点、途经点、当前路径和当前子目标的 QGraphics overlay。
关键导出：`clear_route_overlay`、`render_route_overlay`。
对外依赖：`navigation.presentation.event_overlay.global_to_scene`。
注意事项：只接收 scene/nav_core/route_data/current path 等输入并创建/移除 QGraphicsItem，不修改 route 数据或导航任务状态。
### `gui/modes/navigation/presentation/event_overlay.py`
职责：封装导航地图事件 marker、可注入圆形调试图元的 QGraphics 绘制、坐标转换和 overlay item 清理。
关键导出：`EventOverlayContext`、`EventCircleOverlay`、`clear_event_overlay`、`global_to_scene`、`render_event_overlay`。
对外依赖：无业务模块依赖；只接收调用方传入的 `scene/nav_core/event_coordinator/items/overlay_providers`。
注意事项：该模块只绘制 `EventCoordinator.overlays()` 产出的任务模型和 provider 返回的领域中立圆形描述，不读取具体事件配置键；`global_to_scene()` 同时被 route overlay 复用，避免 route/event 各自重复裁剪偏移换算。
### `gui/modes/navigation/presentation/status_presenter.py`
职责：构造并写入导航循环状态栏文案，封装运行态后缀追加和终态提示。
关键导出：`build_navigation_status_text`、`show_navigation_runtime_status`、`append_navigation_status_suffix`、`show_navigation_relocalizing`、`show_navigation_arrived`、`show_navigation_failed`。
对外依赖：无内部业务模块依赖。
注意事项：localized 时输出坐标/置信度/监视尺寸，未 localized 时输出定位中；可附加 intent message、path kind 和 event status。`append_navigation_status_suffix()` 保留旧行为：读取当前 label 文本并在末尾追加 ` | suffix`，因此调用顺序由 `NavigationRuntimeFrameLoop` 控制。
### `gui/modes/navigation/presentation/viewport_overlay.py`
职责：计算屏幕调试 overlay 逻辑矩形、地图内监控绿框和真实主画面橙框。
关键导出：`screen_overlay_geometry`、`monitor_scene_rect`、`game_view_scene_rect`。
对外依赖：无内部业务模块依赖。
注意事项：纯几何 helper；输入坐标必须保持物理像素、逻辑像素和地图全局坐标的边界清晰，避免用游戏视野框修正定位。
### `gui/modes/navigation/runtime/__init__.py`
职责：导航 runtime helper 包导出。
关键导出：`NavigationLocalizationResult`、`NavigationIntentConsumptionResult`、`NavigationFrameTick`、`NavigationRuntimeFrameLoop`、`NavigationRuntimeCommandLifecycle`、`NavigationRuntimeCommandLifecycleTargets`、`consume_navigation_intent`、`capture_navigation_localization_tick`、`compute_navigation_lookahead`、`should_run_navigation_tasks`、`resolve_player_local_position`、`update_navigation_task_controller`、`handle_relocalization_navigation_intent`、`handle_terminal_navigation_intent`。
对外依赖：`navigation.runtime.models`、`navigation.runtime.intent_consumption`、`navigation.runtime.localization_tick`、`navigation.runtime.frame_loop`、`navigation.runtime.command_lifecycle`、`navigation.runtime.loop_helpers`、`navigation.runtime.loop`、`navigation.runtime.relocalization_intent`、`navigation.runtime.terminal_intent`。
注意事项：只聚合导出，不承载业务逻辑。

### `gui/modes/navigation/runtime/minimap_sample_capture.py`
职责：保存当前小地图监视区域样本，供事件识别和定位算法诊断使用。
关键导出：`MinimapSampleCaptureResult`、`save_minimap_sample(project_root, map_name, frame, capture_rect, monitor_size, player_local_pos, source, now_ms=None)`、`capture_current_minimap_frame(build_capture_geometry, screen_capture)`。
对外依赖：无内部业务模块依赖；只依赖 `cv2`、`numpy` 和文件系统。
注意事项：`save_minimap_sample()` 不做掉落物/传送门识别，也不做人像遮罩，只把输入帧转成 BGR 后写 PNG，并写同名 JSON 元数据。默认输出路径为 `debug/minimap_samples/<safe_map_name>/`，元数据记录 `capture_rect`、`monitor_size`、`player_local_pos`、`frame_shape` 和 `source`，用于复现实机监视区域。`capture_current_minimap_frame()` 是无缓存时的 fallback，调用方必须传入当前导航页的 `_build_capture_geometry` 和 `screen_capture`。

### `gui/modes/navigation/runtime/command_lifecycle.py`
职责：集中导航运行命令生命周期：普通导航启动/停止、自动导航启动/停止、timer/motion/task controller/input-window 状态转移、按钮回滚和状态栏反馈。
关键导出：`NavigationRuntimeCommandLifecycleTargets`、`NavigationRuntimeCommandLifecycle`。
对外依赖：`core.events.debug.start_event_log_session`、`navigation.presentation.navigation_command_state`。
注意事项：这是 runtime command 深模块。它通过 targets DTO 接收 Qt 按钮、timer、motion controller、task controller、输入窗口模式和 widget 回调，不直接持有 `NavigationModeWidget` 类型；保留旧顺序：启动前 guard，启动时应用 runtime config 和请求全图重定位，自动导航失败要复位按钮并停止 task，停止时要幂等关闭 timer/motion/task/input-window、停止手动事件测试、重绘 route overlay 并恢复按钮/状态栏。
### `gui/modes/navigation/runtime/frame_loop.py`
职责：集中导航定时器的单帧 runtime 编排。
关键导出：`NavigationRuntimeFrameLoop`。
对外依赖：`core.events.debug.event_log`、`navigation.event_adapter.event_status_text`、`navigation.input.execute_navigation_intent`、`navigation.presentation`、`navigation.runtime.intent_consumption`、`navigation.runtime.localization_tick`、`navigation.runtime.loop`、`navigation.runtime.loop_helpers`。
注意事项：这是 GUI navigation runtime facade，不是 core 算法层。它持有 `NavigationModeWidget` owner，只编排一帧顺序：截图定位、缓存最近小地图帧、事件 observe、任务 controller update、定位展示/状态栏刷新、route overlay、intent 消费。真实定位仍由 `NavigationCore.localize()` 完成，任务选择仍由 `NavigationTaskController.update_context()` 完成，真实输入仍由 `execute_navigation_intent()` 下发到 `MotionController`。最近帧缓存只服务 `save_minimap_sample()` 这类诊断采样，不改变事件检测路径。`NavigationModeWidget._navigation_loop_unified()` 现在只调用 `runtime_frame_loop.run()`，保持 Qt timer 入口兼容。
### `gui/modes/navigation/runtime/models.py`
职责：保留旧导航 UI 的定位结果兼容 DTO，避免外部旧调用者直接散落 `global_x/global_y/conf` 判定。
关键导出：`NavigationLocalizationResult`。
对外依赖：`core.localization.LocalizationResult`。
注意事项：实时导航链路已改用 core `LocalizationResult`；本 DTO 暂只服务兼容调用。`from_core_result()` 同时接受旧三元组和新结果对象；`localized_pos` 只有在 x/y 均不为 `None` 时返回 `(x, y)`。
### `gui/modes/navigation/runtime/intent_consumption.py`
职责：封装 `NavigationRuntimeFrameLoop.run()` 中 route overlay 之后的单个 intent 消费顺序。
关键导出：`NavigationIntentConsumptionResult`、`consume_navigation_intent`。
对外依赖：`navigation.runtime.relocalization_intent.handle_relocalization_navigation_intent`、`navigation.runtime.terminal_intent.handle_terminal_navigation_intent`。
注意事项：该 helper 不执行 route overlay，也不直接知道 QWidget；真实输入仍由传入的 `execute_intent` 回调处理。执行顺序保持旧逻辑：先 force-relocalize 短路，再执行输入，再处理手动事件测试 terminal metadata，最后处理 ARRIVED/FAILED 终态。返回 DTO 只告诉 widget 是否跳过本帧剩余逻辑、是否关闭 `auto_navigation_enabled`。
### `gui/modes/navigation/runtime/localization_tick.py`
职责：封装导航循环开头的截图与定位输入段。
关键导出：`NavigationFrameTick`、`capture_navigation_localization_tick`。
对外依赖：`core.localization.LocalizationResult`、`navigation.runtime.loop.resolve_player_local_position`。
注意事项：该 helper 不修改 QWidget 状态；它通过 `build_capture_geometry` callback 获取截图几何，通过 `screen_capture.capture()` 抓屏，调用 `resolve_player_local_position()` 得到玩家局部坐标，再调用 `nav_core.localize_result()` 获取 core-owned `LocalizationResult`。调用方仍负责把返回的 `capture_rect/player_pos` 写回 `_current_capture_rect/_current_player_local_pos`。
### `gui/modes/navigation/runtime/loop_helpers.py`
职责：封装导航循环中纯运行时判定和 lookahead 公式。
关键导出：`should_run_navigation_tasks`、`compute_navigation_lookahead`。
对外依赖：无内部业务模块依赖。
注意事项：`compute_navigation_lookahead()` 保持原公式 `max(36.0, min(capture_width * draw_scale * 0.18, 120.0))`；`should_run_navigation_tasks()` 保持“自动导航或手动事件测试任一启用即运行任务控制器”的规则。
### `gui/modes/navigation/runtime/loop.py`
职责：封装导航循环中仍属于 runtime 编排、但不应留在 QWidget 内的局部步骤。
关键导出：`resolve_player_local_position`、`observe_navigation_events`、`update_navigation_task_controller`。
对外依赖：无内部业务模块依赖；通过参数接收 nav_config、nav_core、tracker、NavigationTaskController、PathFinder 等运行对象。
注意事项：`resolve_player_local_position()` 保持原逻辑：显式 `monitor_region` 模式先用 recognizer/tracker 找玩家局部坐标，失败时回退上一帧局部坐标，再回退截图中心；中心点截图模式直接使用默认玩家坐标。`observe_navigation_events()` 调用传入的 `build_event_tick()`、`EventCoordinator.observe()`、`render_event_overlay()` 和可见 event dialog 的 `refresh_tasks()`，并把 `event_tick` 返回给后续 task update；这是后续接 hook/总线的边界，但当前没有 hook 实现。`update_navigation_task_controller()` 负责构造 `NavigationUpdateContext` 并调用 `navigation_task_controller.update_context()`，不改变任务选择、事件 handler 或输入执行。
### `gui/modes/navigation/runtime/relocalization_intent.py`
职责：封装导航任务返回 force-relocalize intent 后的运行态恢复分支。
关键导出：`handle_relocalization_navigation_intent`。
对外依赖：无内部业务模块依赖；通过回调接收 `NavigationCore.request_global_relocalization()`、`event_log()` 和重新定位状态展示函数。
注意事项：该模块不 import QWidget，也不直接 import `NavigationCore`；它只读取 `intent.metadata.force_relocalize/relocalize_reason/relocalize_score`，保持默认 reason 为 `coordinate_recovery`，并返回 bool 告诉主循环是否应该提前结束本帧。
### `gui/modes/navigation/runtime/terminal_intent.py`
职责：封装导航终态 intent 的运行态收束顺序。
关键导出：`handle_terminal_navigation_intent`。
对外依赖：`core.navigation_tasks.models.NavigationIntentType`。
注意事项：该模块不 import QWidget，不直接知道按钮或 status label；通过回调执行 `NavigationTaskController.stop()`、关闭游戏输入窗口、复位自动导航按钮和显示 ARRIVED/FAILED 文案。非 ARRIVED/FAILED intent 返回 `False` 且不触发任何回调。该 helper 仅处理单个终态 intent 的收束，不停止 `nav_timer`，保持自动导航到达后定位循环继续运行的旧行为。
### `gui/modes/navigation/event_adapter.py`
职责：封装导航模式和事件系统之间的轻量桥接，不推进事件状态机。
关键导出：`create_default_event_registry`、`event_config_summary`、`build_event_tick`、`event_status_text`。
对外依赖：`core.events.models.EventTick`、`core.events.registry.EventRegistry`。
注意事项：该模块只组装事件系统需要的输入和状态文案，不查找具体游戏窗口、不导入业务 definition；事件 handler 由 `NavigationTaskController` 通过 `EventCoordinator.run_task()` 触发，真实输入由 `NavigationRuntimeFrameLoop._execute_navigation_intent()` 统一消费。
### `gui/modes/navigation/map/config_store.py`
职责：封装导航模式地图目录解析、地图列表读取、导航配置 JSON 读写、默认配置 fallback 和 merge 保存。
关键导出：`MISSING_MAP_DATA_LABEL`、`project_root_from_file`、`map_data_dir`、`list_map_names`、`resolve_map_folder`、`load_nav_config`、`save_nav_config`、`default_nav_config_path_from_file`、`default_nav_config_path_from_map_folder`、`save_default_nav_config`。
对外依赖：`gui.navigation_params.NavConfig`。
注意事项：该模块不弹窗、不改按钮、不初始化 `NavigationCore`；调用方仍负责 UI 状态和异常提示。`load_nav_config()` 优先读取当前地图 `config.json`，缺失时读取项目根 `config.json` 作为默认配置但仍返回 `config_exists=False` 供 UI 提示。`save_nav_config()` 和 `save_default_nav_config()` 合并写入已有 JSON，保留绘图模式字段，并把旧 `recognizer_params` 与 `NavConfig.to_dict()` 中的新值合并后写回。项目根、`map_data` 和默认根配置路径已委托 `gui/composition/paths.py`，不再依赖固定 `parents[n]`。
### `gui/modes/navigation/map/capture_geometry.py`
职责：封装导航截图 logical/physical 中心换算和 capture rect/player pos 几何计算。
关键导出：`physical_center_from_logical`、`initial_capture_center_for_config`、`build_capture_geometry`。
对外依赖：`gui.navigation_params.NavConfig`。
注意事项：纯几何 helper，不读写文件、不访问 Qt 控件。`initial_capture_center_for_config()` 现在由 `prepare_navigation_map_load_session()` 使用，用于初始化 `_capture_center_physical` 和参数弹窗展示用物理中心；真正截图矩形仍由 `build_capture_geometry()` 计算。`build_capture_geometry()` 保留旧契约：显式 `monitor_region` 返回矩形且 player_pos 为 `None`，中心点模式返回正方形截图矩形和截图中心 player_pos；缺少配置或中心点时返回空几何，由调用方决定隐藏 overlay 或跳过导航循环。
### `gui/modes/navigation/calibration/__init__.py`
职责：导航校准 helper 包导出。
关键导出：`NavigationScreenCalibrationLifecycle`、`NavigationScreenCalibrationLifecycleTargets`、`ScreenCenterCalibrationController`、`physical_point_from_logical`、`screen_scale`。
对外依赖：`navigation.calibration.lifecycle`、`navigation.calibration.screen_center`。
注意事项：只聚合导出，不承载业务逻辑。
### `gui/modes/navigation/calibration/lifecycle.py`
职责：封装导航页屏幕中心校准的完整 UI/runtime 副作用顺序。
关键导出：`NavigationScreenCalibrationLifecycleTargets`、`NavigationScreenCalibrationLifecycle`。
对外依赖：`navigation.presentation.show_screen_center_calibrated`、`navigation.calibration.screen_center.ScreenCenterCalibrationController`（通过 targets 注入）。
注意事项：该模块负责 `NavConfig.game_screen_center` 写回、参数弹窗回填、overlay 刷新、配置保存、完成提示和 selector 关闭；不负责 DPR 读取或 selector 实例创建细节，这些仍由 `screen_center.py` 的 controller 持有。
### `gui/modes/navigation/calibration/screen_center.py`
职责：封装屏幕中心校准选择器生命周期、DPR 缩放读取和逻辑坐标到物理坐标转换。
关键导出：`ScreenCenterCalibrationController`、`screen_scale`、`physical_point_from_logical`。
对外依赖：`gui.selection.center_selector.CenterPointSelector`。
注意事项：controller 只负责创建/复用/关闭 `CenterPointSelector` 和坐标转换；不写 `NavConfig`、不保存 config、不弹完成提示。`start()` 在选择器已可见时返回 `False` 并避免重复创建，保持旧“重复点击校准按钮不弹多个全屏选择器”的行为。
### `gui/composition/__init__.py`
职责：GUI composition helper 包入口。
关键导出：`CoreServices`、`create_core_services`、`project_root_from_file`、`project_root_from_map_folder`、`map_data_dir_from_file`、`root_config_path_from_file`、`root_config_path_from_map_folder`、`advanced_settings_dir_from_file`。
对外依赖：`gui.composition.paths`、`gui.composition.services`。
注意事项：只聚合导出，不承载业务逻辑；这是正式 package 入口，不是旧兼容壳。
### `gui/composition/services.py`
职责：集中创建 GUI 应用共享的 core service 集合，并提供可注入的 DTO。
关键导出：`CoreServices`、`create_core_services`。
对外依赖：`core.platform.SquareScreenCapture`、`core.vision.HSVRecognizer`、`core.vision.PlayerTracker`、`core.mapping.MapStitcher`、`core.routing.PathFinder`。
注意事项：默认 `create_core_services(canvas_size=5000)` 保持原 `AppContext` 初始化行为；`CoreServices` 是 frozen dataclass，用于未来 smoke/test 或替代 adapter 注入。`ColorPickerDialog` 的临时 `HSVRecognizer` 不在此集中，因为它是对话框局部预览状态，不属于 AppContext 共享服务。
### `gui/composition/paths.py`
职责：集中解析 GUI 层使用的项目根目录、`map_data` 目录、根 `config.json` 和高级参数 snapshot 目录。
关键导出：`project_root_from_file`、`project_root_from_map_folder`、`map_data_dir_from_file`、`root_config_path_from_file`、`root_config_path_from_map_folder`、`advanced_settings_dir_from_file`。
对外依赖：无内部业务模块依赖。
注意事项：`project_root_from_file()` 从传入文件或目录向上查找同时包含 `main.py` 和 `gui/` 的目录，不再依赖固定 `parents[n]`；`project_root_from_map_folder()` 优先识别 `map_data/<map_name>` 结构并返回 `map_data` 父目录。当前替换范围包括 mapping config store、navigation map config store 和 advanced settings file IO；utils/core 中的探针或日志路径暂不纳入 GUI composition。
### `gui/modes/mapping_widget.py`
职责：绘图模式主界面组合根，仍负责路径点击入口、保存时机、参数应用顺序和状态栏更新；UI 控件构建已委托 `mapping/ui/layout.py`，监控启动/停止和 capture timer 已委托 runtime lifecycle，单帧 capture-recognize-stitch 主流程已委托 runtime session，display 写入已委托 presentation presenter，区域/中心点选择已委托 capture controller。
关键导出：`MappingWidget`。
对外依赖：`ColorPickerDialog`、`AdvancedSettingsDialog`、`gui.modes.mapping.capture.MappingCaptureSelectionController`、`gui.modes.mapping.io`、`gui.modes.mapping.map_renderer`、`gui.modes.mapping.params`、`gui.modes.mapping.runtime.MappingRuntimeLifecycle`、`gui.modes.mapping.runtime.MappingSession`、`gui.modes.mapping.ui.build_mapping_ui`。
注意事项：`setup_ui()` 现在只调用 `build_mapping_ui(self)`，原 `create_control_panel()` / `create_display_panel()` 内联布局已删除；控件属性名和 signal 目标仍写回 `MappingWidget`，以保持 config restore、params binding 和外部 slot 不变。`toggle_monitoring()` 与 `stop_runtime()` 作为按钮和 `MainWindow.closeEvent()` 的稳定入口保留，但真实 monitoring flag、QTimer 启停、缺少截图配置 warning 和按钮文案更新已委托 `mapping/runtime/lifecycle.py`。`capture_and_process()` 作为 QTimer tick callback 保留，但现在只检查 monitoring、调用 `MappingSession.tick()`、更新 `last_capture_size/last_player_local_pos`，再刷新 display/stats。`select_region()`、`on_region_selected()`、`select_center_point()`、`on_center_selected()` 和 `update_capture_size()` 仍保留旧 slot/API 名称，但实际 overlay 启动、DPI 转换、`app_context.monitor_region/monitor_logical_center/monitor_size` 写回都委托 `mapping/capture/selection_controller.py`；widget 只负责按钮启用、label 文案和保存配置。`save_map()`、`save_config()`、`load_saved_params()` 作为外部入口保留；路径解析、目录创建、JSON 读写和配置 dict 构造在 `mapping/io/config_store.py`，启动时根配置恢复、AppContext 写回、capture selection restore 和 Qt 控件同步已委托 `mapping/io/config_restore.py`，保存地图包和地图级 config 写入顺序已委托 `mapping/io/map_save.py`。`update_displays()` 入口保留，但 capture label、global map widget 和 `map_crop_offset` 更新已委托 `mapping/presentation/map_presenter.py`；图像转换、全局地图着色、路径线、视野框和当前位置圆点绘制继续由 `mapping/map_renderer.py` 承担。HSV/feature/merge 参数控件读取从 `mapping/params` 导入，旧 `mapping/params_adapter.py` 已删除；本类仍决定何时调用 `recognizer.set_params()`、`stitcher.set_params()` 和 `save_config()`，以保持原副作用顺序。高分辨率绘图参数 `draw_scale`、`canvas_size`、`player_clear_radius`、`wall_close_kernel_size` 已作为绘图页控件暴露；空地图时几何参数可立即重建画布，已有帧时仅保存为下次重置/新地图使用。

### `gui/modes/mapping/__init__.py`
职责：绘图模式 helper 包标识。
关键导出：无。
对外依赖：无。
注意事项：空包入口只服务内部模块命名空间，不承载业务逻辑。
### `gui/modes/mapping/ui/__init__.py`
职责：绘图模式 UI 构建包入口。
关键导出：`build_mapping_ui`。
对外依赖：`mapping.ui.layout`。
注意事项：只聚合导出，不承载业务逻辑。
### `gui/modes/mapping/ui/layout.py`
职责：构建绘图模式控制面板和显示面板，把旧内联控件创建、默认值、信号连接和地图显示 widget 初始化集中到 UI shell 模块。
关键导出：`build_mapping_ui`、`create_mapping_control_panel`、`create_mapping_display_panel`。
对外依赖：`gui.widgets.collapsible_group.CollapsibleMapGroup`。
注意事项：该模块只创建 Qt 控件并挂回 owner 字段，不读取/写入 config 文件、不启动 capture timer、不调用 recognizer/stitcher；它仍有意依赖 `MappingWidget` 的稳定 slot 名称和字段名，因为 config restore、params binding 和 runtime wrapper 仍以这些属性为组合根契约。
### `gui/modes/mapping/capture/__init__.py`
职责：绘图模式 capture selection 包导出。
关键导出：`CaptureSelectionResult`、`MappingCaptureSelectionController`。
对外依赖：`mapping.capture.selection_controller`。
注意事项：只聚合导出，不承载业务逻辑。
### `gui/modes/mapping/capture/selection_controller.py`
职责：封装建图页区域/中心点选择 overlay 生命周期、逻辑像素到物理像素转换、AppContext monitor 字段写回和已保存选择恢复。
关键导出：`CaptureSelectionResult`、`MappingCaptureSelectionController`。
对外依赖：`gui.selection.region_overlay.TransparentOverlay`、`gui.selection.center_selector.CenterPointSelector`。
注意事项：controller 不直接操作建图页按钮、label 或 config 文件；它通过回调把 `CaptureSelectionResult` 交还 widget。`compute_scale`、overlay factory、center selector factory 通过构造参数注入，便于后续多屏/DPR 适配或 smoke 测试替换。
### `gui/modes/mapping/runtime/__init__.py`
职责：绘图模式 runtime 包导出。
关键导出：`MappingRuntimeLifecycle`、`MappingRuntimeLifecycleTargets`、`MappingSession`、`MappingTickResult`。
对外依赖：`mapping.runtime.lifecycle`、`mapping.runtime.models`、`mapping.runtime.session`。
注意事项：只聚合导出，不承载业务逻辑。
### `gui/modes/mapping/runtime/lifecycle.py`
职责：封装绘图模式监控启动/停止命令、capture timer 生命周期、`app_context.monitoring` 状态和开始按钮文案。
关键导出：`MappingRuntimeLifecycleTargets`、`MappingRuntimeLifecycle`。
对外依赖：无内部业务模块依赖；使用 `QTimer` 和 `QMessageBox`。
注意事项：该 lifecycle 不执行单帧建图算法；timer tick 通过 `on_tick` 回调进入 `MappingWidget.capture_and_process()`。`toggle_monitoring()` 保持旧顺序：先翻转 monitoring，若缺少区域/中心点配置则回滚并弹 warning；配置存在时按 `1000 // fps` 启动 timer 并改按钮文案。`stop_runtime()` 是幂等停止入口，供按钮停止分支和主窗口关闭调用。
### `gui/modes/mapping/runtime/models.py`
职责：承载单帧建图 tick 的输出，让 widget 不必了解 session 内部中间变量。
关键导出：`MappingTickResult`。
对外依赖：无内部业务模块依赖。
注意事项：字段包括 `current_image`、`combined_mask`、`player_pos`、`capture_size`；当前用 `object` 承载 OpenCV/Numpy 图像对象，避免 GUI 层引入额外图像类型约束。
### `gui/modes/mapping/runtime/session.py`
职责：执行单帧建图 runtime 流程：截图、玩家局部坐标 fallback、mask 提取、raw gray 提取、构造 `MapFrameEvidence` 并经 typed ingress 交给 stitcher，最后返回预处理图。
关键导出：`MappingSession`。
对外依赖：`core.mapping.MapFrameEvidence`、`mapping.runtime.models.MappingTickResult`。
注意事项：该 session 只通过 `app_context` 调用 `screen_capture/recognizer/tracker/stitcher`，通过回调读取当前物理 monitor center 和上一帧 player pos，不触碰 Qt 控件、不更新 display、不写统计。中心截图模式 player pos 固定为截图中心；区域截图模式检测失败时依次回退上一帧 player pos 和截图中心。它保留旧 HSV 识别和拼图算法不变，只在 composition root 将 image、combined/wall/fog masks、raw gray 和 player position 组成 `MapFrameEvidence`，由 `MapStitcher.add_evidence()` 再兼容委托历史 `add_frame(...)`。
### `gui/modes/mapping/presentation/__init__.py`
职责：绘图模式 presentation 包导出。
关键导出：`MappingDisplayResult`、`update_mapping_displays`。
对外依赖：`mapping.presentation.map_presenter`。
注意事项：只聚合导出，不承载业务逻辑。
### `gui/modes/mapping/presentation/map_presenter.py`
职责：封装绘图模式 capture label 和 global map widget 的显示写入，并返回新的 map crop offset。
关键导出：`MappingDisplayResult`、`update_mapping_displays`。
对外依赖：`mapping.map_renderer.pixmap_from_bgr`、`render_global_map_pixmap`、`unpack_enhanced_map_result`。
注意事项：该 presenter 不调用 `recognizer.extract_combined()` 或 `stitcher.add_frame()`；它只读取 `stitcher.get_enhanced_map()`/`get_current_position()` 生成显示 pixmap。global map 为空时保留旧 crop offset，不触碰 global map widget。

### `gui/modes/mapping/map_renderer.py`
职责：封装绘图模式图像展示相关转换和 OpenCV overlay 绘制。
关键导出：`pixmap_from_bgr`、`unpack_enhanced_map_result`、`render_global_map_pixmap`。
对外依赖：无内部业务模块依赖；只使用 OpenCV/Numpy/PySide6 图像类型。
注意事项：该模块不读取 `app_context`、不调用 stitcher、不设置 Qt 控件；调用方传入已取出的地图图像、裁剪偏移、路径、当前位置、draw_scale、player_pos 和 capture_size。颜色、线宽和 fallback 解包逻辑保持原 `MappingWidget.update_displays()` 行为。

### `gui/modes/mapping/params/__init__.py`
职责：绘图模式 params binding 包导出。
关键导出：`apply_hsv_toggles`、`feature_params_from_widgets`、`apply_merge_weight`、`sync_recognizer_widgets`、`sync_stitcher_widgets`、`sync_geometry_widgets`。
对外依赖：`mapping.params.binding`。
注意事项：只聚合导出，不承载业务逻辑。

### `gui/modes/mapping/params/binding.py`
职责：封装绘图模式参数控件到 recognizer/stitcher 参数字段的轻量映射。
关键导出：`apply_hsv_toggles`、`feature_params_from_widgets`、`apply_merge_weight`、`sync_recognizer_widgets`、`sync_stitcher_widgets`。
对外依赖：无内部业务模块依赖；只使用传入的控件和 recognizer/stitcher 对象。
注意事项：该模块不保存配置、不弹窗、不创建控件、不阻断 Qt 信号。`sync_recognizer_widgets()` 和 `sync_stitcher_widgets()` 保持原 `setChecked()`/`setValue()` 写回顺序和默认值，因此仍可能触发既有信号副作用；这是为保持行为不变而刻意保留。

### `gui/modes/mapping/io/__init__.py`
职责：绘图模式 IO helper 包导出。
关键导出：`project_root_from_file`、`map_data_dir`、`map_folder_for_name`、`ensure_map_folder`、`root_config_path`、`build_mapping_config`、`save_json_config`、`load_json_config`、`save_root_config`、`load_root_config`、`save_map_config`、`MappingConfigRestoreTargets`、`restore_saved_mapping_config`、`save_mapping_map`。
对外依赖：`mapping.io.config_store`、`mapping.io.config_restore`、`mapping.io.map_save`。
注意事项：只聚合导出，不承载业务逻辑。

### `gui/modes/mapping/io/config_store.py`
职责：封装绘图模式项目根目录解析、`map_data` 目录定位、地图目录创建、根级/地图级 `config.json` 读写和配置 dict 构造。
关键导出：`project_root_from_file`、`map_data_dir`、`map_folder_for_name`、`ensure_map_folder`、`root_config_path`、`build_mapping_config`、`save_json_config`、`load_json_config`、`save_root_config`、`load_root_config`、`save_map_config`。
对外依赖：`gui.composition.paths`；通过传入的 `app_context` 读取当前 recognizer/stitcher 参数。
注意事项：该模块不弹窗、不写 Qt 控件、不调用 `stitcher.save_map_package()`；`json.dump(..., indent=4)` 保持旧保存格式，未设置 `ensure_ascii=False` 以避免改变现有输出行为。项目根、`map_data` 和根配置路径已委托 `gui/composition/paths.py`，原 public helper 名称保留给 mapping IO 调用方。

### `gui/modes/mapping/io/config_restore.py`
职责：封装绘图页启动时根配置恢复编排，把 `config.json` 应用到 AppContext、capture selection controller 和 Qt 控件。
关键导出：`MappingConfigRestoreTargets`、`restore_saved_mapping_config`。
对外依赖：`mapping.io.config_store.load_root_config`、`mapping.params.binding`。
注意事项：该模块不是纯存储层；它会写 `app_context.monitor_*`、调用 `recognizer.set_params()` / `stitcher.set_params()`，必要时在空 stitcher 上调用 `reinitialize_canvas()`，并通过 `QSignalBlocker` 同步几何控件。它不弹窗、不显示 warning、不保存配置；错误仍由 `MappingWidget.load_saved_params()` 外层处理。

### `gui/modes/mapping/io/map_save.py`
职责：封装绘图页保存地图包和地图级配置的 IO 编排。
关键导出：`save_mapping_map`。
对外依赖：`mapping.io.config_store.ensure_map_folder`、`mapping.io.config_store.save_map_config`。
注意事项：该模块不弹输入框、不显示成功消息；`MappingWidget.save_map()` 仍负责 `QInputDialog` 和 `QMessageBox`。保存顺序保持旧行为：先确保 `map_data/<map_name>` 目录，再调用 `stitcher.save_map_package(str(map_folder))`，最后写 `map_folder/config.json`。

### `core/navigation_tasks/*`
职责：方案 C 的统一导航任务层，把静态路线目标和动态事件目标放进同一调度与移动执行链路。
关键导出：`NavigationTaskController`、`NavigationTaskScheduler`、`NavigationTaskBuilder`、`MovementExecutor`、`movement_step`、`plan_movement_path`、`ensure_movement_path`、`CoordinateDiagnostics`、`CoordinateRelocalizationRequest`、`RouteContext`、`NavigationTask`、`NavigationIntent`、`NavigationIntentType`。
对外依赖：`core.routing.anchors`、`core.routing.geometry`、`core.events.models.EventActionType`。
注意事项：`NavigationTaskController` 是自动导航和手动事件测试的唯一运行控制器；原普通导航器、事件路径移动器、事件动作执行器三个旧模块已删除。`NavigationTaskController.update_context()` 已委托 `update_pipeline.py`，required/exit 静态任务委托 `static_task_runner.py`，event 任务委托 `event_task_runner.py`，runtime 生命周期/定位/required progress/重定位 intent 已委托 `controller_runtime/` 子包；旧 `update(**kwargs)`、`update_context(context)`、`observe_localization()`、`_consume_relocalization_intent()`、`_update_required_progress()`、`record_intent_click()` 入口仍保留。`RouteContext` 负责 guide_points 折线投影和单调路线进度；`NavigationTaskBuilder` 把未完成 required、exit 和 `EventCoordinator.tasks()` 中可运行事件转成 `NavigationTask`；`NavigationTaskScheduler` 只对 event 持有 active lock，静态 required/exit 每帧重新仲裁以允许新事件抢占；`MovementExecutor` 现在是薄 facade，保留 `step()`、`record_click()`、`_ensure_path()`、`_plan_path()`、`_local_probe()`、`_is_stuck()` 等旧入口，实际流程委托 `movement/pipeline.py`、`movement/path_maintenance.py`、`movement/path_planner.py` 和 `movement/recovery.py`。事件 `MOVE_TO` 和普通 required/exit 都走 `MovementExecutor.step()`，事件 `PRESS_KEY/CLICK_SCREEN` 直接转成 `NavigationIntent` 由 GUI 消费。`CoordinateDiagnostics` 是内部坐标恢复机制，不进入事件系统，不和 portal 等业务事件竞争调度；当前 `CoordinateDiagnostics` facade 保留旧 public 方法和私有 wrapper，定位诊断、导航状态诊断、重定位请求生命周期和日志格式化已拆到 `coordinate/` 子包。

### `core/localization/navigation_core/runtime.py`
职责：读取 `map_data.npz`，用实时小地图截图定位玩家在全局地图中的坐标，并作为定位系统的状态拥有者。
关键导出：`NavigationCore`。
对外依赖：`core.localization.localize_pipeline`、`core.localization.map_package`、`core.localization.rendering`、`core.localization.visual_check`、`core.vision.phase_displacement`、`core.vision.hsv_recognizer`。
注意事项：`NavigationCore` 仍是对外 facade class，GUI/任务层仍可直接读写 `draw_scale`、`nav_wall_layer`、`explored_map`、`crop_offset`、`current_pos`、`last_good_pos`、`drawing_saved_pos`、`last_frame_registration`。`localize()` 主流程委托 `core.localization.localize_pipeline.localize_frame()`，旧公开入口不改。`draw_scale` 必须与建图保持一致；定位运行时以 `map_data.npz` 里的 `draw_scale` 为权威来源，导航配置里的同名字段只作为旧配置/显示兼容。输出坐标是全局地图坐标，不是屏幕点击坐标。原始 `wall_layer` 必须保持不变并继续服务定位、事件配准和地图显示；`nav_wall_layer` 是由原始墙图派生出的 A* 专用障碍层。`request_full_map_localization()` / `request_global_relocalization()` 只用于清空 F2F 状态并强制下一帧走完整 `wall_layer` 模板匹配。

Current typed boundary: `NavigationCore.localize_result()` delegates exactly once to the unchanged tuple-returning `localize()`, snapshots the already-written `last_frame_registration`, and returns `LocalizationResult`. It does not rerun HSV/template/F2F logic, capture frames, interact with GUI, or dispatch actions. `localize()` remains the public compatibility API for tuple consumers.

### `core/localization/navigation_core/state.py`
职责：承接 `NavigationCore.__init__()` 中的 map path/default 参数初始化和运行态字段初始化。
关键导出：`initialize_map_configuration`、`require_map_data_file`、`initialize_runtime_state`。
对外依赖：`core.shared.frame_registration.FrameRegistration`。
注意事项：当前保持旧构造顺序：先加载地图包，再初始化定位运行态字段；因此不修复旧行为中的 `current_pos` 加载后又被运行态重置问题，避免结构整理混入行为变更。

### `core/localization/navigation_core/registration.py`
职责：承接 `NavigationCore._clear_frame_registration()` 和 `_set_frame_registration()` 的状态写回。
关键导出：`clear_navigation_frame_registration`、`set_navigation_frame_registration`。
对外依赖：`core.localization.frame_registration`。
注意事项：该模块写回 `nav_core.last_frame_registration`，旧私有方法名仍在 `NavigationCore` 上作为 wrapper。

### `core/localization/navigation_core/relocalization.py`
职责：承接初始位置提示、强制全图重定位请求、full/local 定位模式判断和模板匹配阈值策略。
关键导出：`set_initial_hint`、`request_full_map_localization`、`is_full_map_localization`、`template_match_required_confidence`。
对外依赖：无内部业务模块依赖。
注意事项：`request_global_relocalization()` 仍是 `NavigationCore` 上的兼容别名。

### `core/localization/navigation_core/wall_layer.py`
职责：承接导航专用墙层派生和墙体模板 wrapper。
关键导出：`rebuild_navigation_wall_layer`、`navigation_wall_close_kernel`、`standardize_navigation_wall_template`。
对外依赖：`core.routing.obstacles`、`core.localization.frame_matcher`。
注意事项：该模块只派生 `nav_wall_layer`，不改变定位用 `wall_layer`。

### `core/localization/navigation_core/diagnostics.py`
职责：承接定位模板匹配失败的节流日志。
关键导出：`log_template_match_failure`。
对外依赖：OpenCV。
注意事项：日志字段保持旧内容，包括置信度、阈值、full_map/forced 状态、raw/scaled mask 尺寸、特征数、搜索区域和闭运算核。

### `core/localization/localize_pipeline.py`
职责：承接 `NavigationCore.localize()` 的完整定位帧处理流程。
关键导出：`localize_frame`。
对外依赖：OpenCV、NumPy、`core.localization.frame_matcher`。
注意事项：该模块接收 `NavigationCore` 实例并写入其定位状态，因为 F2F、模板匹配、forced relocalization、jump rejection、frame registration 属于同一帧生命周期。旧 `NavigationCore.localize()` 保留为公开 facade。

### `core/localization/canonical_wall.py`
职责：把视觉墙体或其他二值 wall-like 数组标准化为单通道 `uint8` 形状，并把可行走/已探索层转换为薄边界；该模块不感知 PoE2、导航页或地图对象。
关键导出：`canonical_wall_mask`、`canonical_boundary_from_walkable`。
对外依赖：OpenCV、NumPy。
注意事项：输入值只按零/非零解释；可选闭运算、开运算和最小连通域过滤不会修改输入数组。explored shape 不一致抛出 `ValueError`。边界表示只用于定位形状，不是 A* 障碍层。

`canonical_wall_mask(value, *, close_kernel_size=3, open_kernel_size=1, min_component_area=0) -> np.ndarray` 算法：先校验二维/三维非空输入并转灰度，再二值化，按配置执行闭运算、开运算和连通域过滤；无效输入抛 `ValueError`，不写文件、不修改调用方数组。

`canonical_boundary_from_walkable(walkable, explored=None, *, close_kernel_size=3) -> np.ndarray` 先校验二维形状和 explored 尺寸，将未知区域清零，再对 known walkable 做归一化并以 3x3 膨胀减腐蚀提取薄边界；形状错误抛 `ValueError`。

### `core/localization/displacement.py`
职责：将小地图局部位移通过已确认的二维相似变换映射到全局参考图坐标，或通过严格逆变换从全局/native 向量还原到局部坐标，供导航兼容跟踪、定位和输入适配复用。
关键导出：`transform_local_displacement`、`inverse_transform_local_displacement`。
对外依赖：标准库 `math`。
注意事项：变换顺序固定为水平镜像、角度旋转、比例缩放；角度矩阵必须与 `similarity_search.transform_feature()` 的 OpenCV 图像坐标一致（x 向右、y 向下）；该函数只转换向量，不负责导航位置的正负号策略。

`transform_local_displacement(shift, *, angle_degrees, reflect_horizontal, scale) -> tuple[float, float]` 校验二元有限输入和正比例，镜像 X 后按 OpenCV 图像坐标矩阵 `[[cos, sin], [-sin, cos]]` 旋转并乘比例；非有限值或非正比例抛 `ValueError`，没有外部副作用。该约定保证 `VisualLocalTracker.track()` 的 `visual_f2f` 位移与首帧 `transform_feature()` 的方向相同。

`inverse_transform_local_displacement(shift, *, angle_degrees, reflect_horizontal, scale) -> tuple[float, float]` 先按 `R(-angle)` 旋回，再执行水平镜像并除以比例，得到正向变换的严格逆；不能用“负角度 + 同一镜像参数”替代，因为反射与旋转不交换。该函数不带 translation，适用于路线方向而非地图点坐标。

### `core/localization/frame_displacement.py`
职责：封装 phase correlation 的逐帧位移结果，并以质量和最大移动距离生成显式可审计的接受/拒绝结果。
关键导出：`FrameDisplacement`、`estimate_bounded_displacement`。
对外依赖：NumPy、`core.vision.phase_displacement.estimate_phase_displacement`。
注意事项：该模块不拥有定位状态，也不读取内存；`accepted` 只代表位移观测通过门控，不代表已写入地图位置。

`estimate_bounded_displacement(previous, current, *, min_quality=0.20, max_shift=40.0, dead_zone=0.2) -> FrameDisplacement` 算法：调用 phase correlation；无 shift 或低质量分别返回 `phase_failed`/`low_quality`；过大且低质量的移动返回 `large_shift`；其余返回 `accepted`。没有文件或网络副作用。

### `core/localization/result.py`
职责：提供定位领域的不可变结果契约，把既有定位三元组和已写入的 `FrameRegistration` 快照为可复用的全局地图位置结果，而不重跑或了解 HSV、模板、F2F 决策。
关键导出：`LocalizationResult`。
对外依赖：`core.perception.models.CoordinateSpace`。
注意事项：`position=None` 表示本帧未定位；`coordinate_space` 固定为 `GLOBAL_MAP`。`from_legacy_tuple()` 只解包一次 `(global_x, global_y, confidence)`，复制 registration 的 `source`、`valid` 和 `metadata`，因此后续 registration metadata 变更不会污染已返回结果。`as_legacy_tuple()` 保留旧消费者需要的三元组形状；它不限制置信度范围，因为 OpenCV 的历史模板分数可以为负。

### `core/localization/frame_registration.py`
职责：集中构建 `NavigationCore.last_frame_registration`，把“定位失败帧”和“已知玩家点的有效帧配准”从 facade 中拆出。
关键导出：`clear_frame_registration`、`build_frame_registration`。
对外依赖：`core.shared.frame_registration.FrameRegistration`。
注意事项：该模块只返回 `FrameRegistration` 对象，不直接写 `nav_core` 状态。有效配准的 `frame_origin_global = player_global_pos - player_local_pos * draw_scale`，`frame_size` 从 OpenCV frame shape 转成 `(width, height)`，metadata 会复制成普通 dict，避免调用方后续修改原 dict 污染已保存配准。

### `core/localization/frame_matcher.py`
职责：封装导航模板匹配前的墙体模板处理和搜索窗口选择。
关键导出：`normalized_wall_close_kernel_size`、`wall_close_kernel`、`standardize_wall_template`、`scaled_template_size`、`scale_wall_template`、`select_template_search_area`。
对外依赖：无内部业务模块依赖；只使用 OpenCV。
注意事项：`scale_wall_template()` 保持旧行为：把实时小地图的 1x `wall_mask` 按 `draw_scale` 放大到地图尺度，再按 `wall_match_close_kernel_size` 做 MORPH_CLOSE。`select_template_search_area()` 保持旧 local/full 语义：全图定位直接返回完整 `wall_layer`；局部定位围绕 `current_pos` 取 `local_search_radius` 窗口，若窗口比放大后的模板小则回退全图搜索。该模块不调用 `cv2.matchTemplate()`，匹配结果解析和状态写入仍留在 `NavigationCore.localize()`。

### `core/localization/visual_check.py`
职责：封装 F2F 跟踪期间的视觉一致性复核，即把当前小地图墙体 mask 放到“当前认为的玩家全局位置附近”重新做局部模板匹配，判断截图最佳贴图位置是否偏离当前跟踪坐标。
关键导出：`visual_check_position`。
对外依赖：`core.localization.frame_matcher.scale_wall_template`。
注意事项：该 helper 仍接收 `nav_core`，因为需要读取 `visual_check_interval_ms`、`visual_check_margin`、`visual_check_min_confidence`、`visual_mismatch_threshold`、`draw_scale`、`wall_layer`，并更新 `_last_visual_check_ms` 节流时间。返回 dict 会被写入 `FrameRegistration.metadata`，包括 `visual_conf`、`visual_expected_score`、`visual_player`、`visual_delta`、`visual_delta_dist`、`visual_mismatch`；异常不会传播，而是返回 `visual_check=failed` 和失败原因。

### `core/routing/pathfinder/runtime.py`
职责：把调用方传入的障碍层结合 `explored_map` 转为低分辨率 A* 网格，并输出全局地图路径点。
关键导出：`PathFinder`。
对外依赖：`core.routing.pathfinder.grid`、`astar`、`snap`、`coordinates`。
注意事项：路径点用于地图导航，不能直接当屏幕点击点。默认 `safety_margin=0`、`wall_shrink_iterations=0`，墙体变薄优先在 `NavigationCore.nav_wall_layer` 派生阶段完成，避免双重侵蚀。`start_clear_radius` 会在 A* 网格上清空玩家当前位置附近的小圆，容忍“定位点落在视觉墙像素内”；`walkable_snap_radius` 控制起终点落障碍时寻找最近可走格的半径。`explored_map==0` 必须视为不可走，否则 A* 会穿过地图外黑区。旧 `_build_obstacle_map()`、`_clear_start_area()`、`_astar()`、`_heuristic()`、`_reconstruct_path()`、`_find_nearest_walkable()` 仍保留为 wrapper。

### `core/routing/pathfinder/grid.py`
职责：构建 A* 使用的降采样障碍网格。
关键导出：`build_obstacle_map`、`apply_explored_obstacles`、`apply_safety_margin`、`build_clearance_cost_map`、`clear_start_area`。
对外依赖：OpenCV、NumPy。
注意事项：先 threshold 原始 wall map，可选 erode 墙体，再 resize 到 grid 尺寸；`explored_map` 中 0 会转成障碍；`safety_margin` 以 map-space 像素传入并转换成 grid 半径。`build_clearance_cost_map()` 使用距离变换把离墙近的可走格赋予软代价，返回 `None` 时保持旧的等价距离 A*。

### `core/routing/pathfinder/astar.py`
职责：执行 8 邻接 A* 搜索。
关键导出：`astar_path`、`diagonal_cuts_corner`、`heuristic`、`reconstruct_path`。
对外依赖：标准库 `heapq`。
注意事项：斜向移动 cost 为 `1.414`，正交为 `1.0`；如果任一相邻正交格被阻挡，则拒绝斜向移动，防止 corner cutting。可选 `cost_map` 只影响可走格的软代价，不改变障碍判定。

### `core/routing/pathfinder/snap.py`
职责：在起点/终点落入障碍时寻找最近可走格。
关键导出：`find_nearest_walkable`、`walkable_snap_grid_radius`。
对外依赖：无内部模块依赖。
注意事项：使用 Manhattan-radius scan，保持旧“找到第一个可走格就返回”的行为。

### `core/routing/pathfinder/coordinates.py`
职责：集中 map-space 与 grid-space 坐标转换。
关键导出：`map_to_grid`、`grid_size_from_map_shape`、`in_grid_bounds`、`grid_path_to_map_path`。
对外依赖：无内部模块依赖。
注意事项：grid path 转 map-space 时返回每个格子的中心点，并按旧行为追加精确 `end_pos`。

### `core/mapping/stitcher.py`
职责：将实时小地图墙层/地面层融合到全局地图，并输出供绘图模式与导航模式共用的地图包。
关键导出：`MapStitcher`。
对外依赖：`core.mapping.package_io`、`core.mapping.performance`、`core.mapping.frame_preparation`、`core.mapping.frame_pipeline`、`core.mapping.weighted_merge`、`core.mapping.rendering`、`core.vision.phase_displacement`。
注意事项：`default_params()` 在不分配大型 NumPy 画布的前提下返回完整参数契约，供 profile/adapter 构造使用；`reset()` 会保留画布、比例、墙体闭运算及融合/质量门参数。`save_map_package()`、`load_map_package()`、`add_frame()`、`get_cropped_map()`、`get_enhanced_map()` 等入口不改。当前版本不再把整块截图矩形无脑写入 `explored_map`；优先使用 `fog_mask` 作为精准可见区域，并同步维护 `fog_layer`，这样生成的地图更接近游戏实际小地图结构。性能工具在 `mapping/performance.py`；帧 mask 缩放、墙体厚度标准化、重复相似度和边界判断在 `mapping/frame_preparation.py`；`add_frame()` 主流程在 `mapping/frame_pipeline.py`，`MapStitcher` 仍统一持有状态。

### `core/mapping/performance.py`
职责：封装建图性能计时工具。
关键导出：`PerformanceMonitor`、`Timer`。
对外依赖：标准库 `time`。
注意事项：`PerformanceMonitor.record()` 按名称保留最近 100 次耗时；旧 no-op `print_report()` 已删除，避免保留无行为兼容钩子。`Timer` 是上下文管理器，退出时把耗时毫秒写入 monitor。

### `core/mapping/frame_preparation.py`
职责：封装 `MapStitcher` 在落图前需要的纯计算 helper。
关键导出：`standardize_wall_thickness`、`prepare_scaled_frame_masks`、`scaled_player_pos`、`is_too_similar`、`bounds_in_canvas`。
对外依赖：OpenCV、NumPy。
注意事项：`prepare_scaled_frame_masks()` 保持旧行为：按 `draw_scale` 放大 `save_mask/fog_mask`，再对 `save_mask` 做 MORPH_CLOSE。`is_too_similar()` 保持旧 IoU 逻辑：重叠像素少于 100 时不视为重复，IoU 大于 0.95 才跳过。该模块不写 `MapStitcher` 状态。

### `core/mapping/frame_pipeline.py`
职责：承接 `MapStitcher.add_frame()` 的建图帧处理流程。
关键导出：`add_frame_to_stitcher`。
对外依赖：OpenCV、NumPy、`core.mapping.frame_preparation`。
注意事项：该模块仍接收 `MapStitcher` 实例并写入其状态，因为 keyframe/F2F 配准、低质量跳过、落图和统计更新属于同一帧生命周期。这样可以让 facade 变薄，同时保留旧 `MapStitcher.add_frame()` 调用面。

### `utils/event_icon_probe.py`
职责：不接入导航主循环，只用于验证“原始小地图截图 + 事件图标模板”能否识别出事件候选。
关键导出：`CaptureGeometry`、`parse_args()`、`load_config()`、`build_capture_geometry()`、`probe_frame()`、`main()`。
对外依赖：`core.platform.SquareScreenCapture`。
注意事项：事件识别必须使用 raw minimap frame，不使用 `HSVRecognizer.extract_combined()` 之后的定位特征图；脚本需要和游戏同权限运行，非管理员权限可能抓到黑帧。`--template` 和 `--image` 均可重复传入；静态图片模式用于验证用户提供截图是否能被当前模板资产识别。默认仍可跑整块模板诊断；加 `--portal-feature-detector` 时改用运行时 portal 蓝色本体特征算法，打印 mask/density 分数和蓝色像素范围，用于区分“背景模板不鲁棒”和“本体特征不可分”的问题；加 `--portal-shape-color-detector` 时改用探针专用形状+颜色联合算法，同时保存蓝色 core mask、白/灰 outer-ring mask、combined shape mask 和 accepted/rejected 候选裁剪，用于确认误报是否来自“只有蓝色相似但外环/轮廓不完整”。

### `gui/dialogs/event_manager_dialog.py`
职责：事件系统的非模态管理窗口，展示 registry 驱动的事件选配、schema 参数、识别任务状态和 hook 实例配置，并发出领域中立的保存、手工测试、刷新状态信号。
关键导出：`EventManagerDialog`。
对外依赖：`core.events.config.build_tui_event_options`、`gui.dialogs.event_manager.hooks.EventHookPanel`。
注意事项：窗口使用 `Qt.Tool` 且 `WA_DeleteOnClose=False`，避免手动传送门测试期间主窗口进入游戏输入模式后，事件面板跟随父窗口层级被隐藏或关闭后无法再次打开。导航页每次打开事件管理时会确保窗口存在、刷新上下文并显式 `show/raise/activate`。Hooks 页只编辑配置，不注册 handler；真实注册由 `gui/modes/navigation/hooks/registration.py` 根据当前事件配置完成。

### `utils/portal_screen_probe.py`
职责：不接入导航主循环，只用于验证主游戏画面里传送门实体是否能被视觉识别。
关键导出：`main()`。
对外依赖：`core.platform.SquareScreenCapture`、`core.events.window_finder`、`features.torchlight.portal.main_view_confirmer`。
注意事项：该探针默认枚举 `UnrealWindow` / `Torchlight` 游戏窗口并抓整块窗口画面；也支持 `--rect` 或 `--full-screen`。探针现在复用 portal 事件包的 main-view confirmer，避免探针算法和运行时算法漂移。

### `core/events/*`
职责：事件系统核心层。`EventCoordinator` 是导航模式唯一事件入口；`EventRegistry` 只注册完整事件包；`EventMemory` 管理事件实例生命周期；`EventRunner` 调用具体事件 handler。
关键导出：`FrameRegistration`、`EventTick`、`EventDetection`、`EventObservation`、`EventTask`、`EventAction`、`EventCoordinator`、`EventRegistry`、`EventSystemConfig`。
对外依赖：标准库；视觉工具依赖 OpenCV/NumPy。
注意事项：事件 handler 不直接操作鼠标键盘，只返回 `EventAction`；TUI/配置层只能看到 `EventDefinition` 级完整事件，例如 `portal`。`EventCoordinator.observe()` 只做检测、事件定位、memory 合并、任务表/overlay 状态更新；`EventCoordinator.run_task(task_id, tick)` 只推进被统一导航调度器选中的事件任务。`EventMonitor.detect()` 现在会把每个 legacy `EventDetection` 经过 `TargetDetection(coordinate_space=MINIMAP)` 再构造独立的 legacy 副本，返回给既有稳定器；同时将通用结果公开在 `last_target_detections`，因此新 UI/debug 或未来通用感知 producer 可观察同一 schema，而 Portal/Loot 的模板、HSV、时序策略和 handler 状态保持原处。旧 UI 层事件允许集合兼容入口已删除，避免重新引入 UI 层事件仲裁。`EventPositionStabilizer` 默认仍会按同一帧隔离聚类，但传送门在 detector conversion 层先用 `minimap_nms_radius` 抑制同一图标的局部重复 hit，再用 `localization_cluster_radius/dedupe_radius` 合并多帧投影抖动；如果实测存在真正相邻双门被合并，应在事件面板把这些半径调小。事件执行抢占规则已迁移到 `NavigationTaskScheduler`，事件本身作为动态必经点参与 required/exit 的统一调度。
`EventPositionStabilizer` 当前是同名 facade package：`runtime.py` 保留类和旧私有 wrapper，`projection.py` 只负责 local->global 投影，`clusters.py` 负责聚类/同帧隔离/过期清理，`observations.py` 负责稳定 gate 和 `EventObservation` 构造，`models.py` 负责 sample/cluster 数据结构。旧 import `from core.events.position_stabilizer import EventPositionStabilizer` 仍可用。
`EventMemory` 当前是 facade package：`merge_observations()` 委托 `memory/merge.py`，任务查找和冷却委托 `memory/lookup.py`，传送会话/失败重试/附近任务抑制委托 `memory/completion.py`，距离和日志节流委托 `memory/utils.py`。旧 `_find_*`、`_completed_cooldown_info()`、`_distance()`、`_int_pos()` 仍保留 wrapper。
`core.events.debug` 当前是同名 package：`writer.py` 保留 event log session 和文件写入副作用，`topics.py` 负责 per-topic log 分流，`descriptions.py` 负责 action/task 描述，`formatting.py` 负责统一字段格式化。旧 import `from core.events.debug import event_log, start_event_log_session, describe_action, describe_task` 仍可用；日志路径仍写到项目根目录 `logs/`，不是 `core/logs/`。
`EventCoordinator.reset_event_type(event_type, now_ms)` 是事件管理 UI 的运行时重置入口；它清理同类型 active handler、memory tasks、position clusters、last detections/observations 和 selected task，不改 `event_config.json`，用于同一地图反复识别/执行某类事件。

### `core/events/hooks/__init__.py`
职责：事件生命周期 hook package 入口，向外导出 hook 常量、`EventHookContext`、`EventHookRegistry` 和 handler 类型。
关键导出：`EVENT_HOOK_VISIBLE_TARGET`、`EVENT_HOOK_COMPLETED`、`EventHookContext`、`EventHookHandler`、`EventHookRegistry`。
对外依赖：`core.events.hooks.models`、`core.events.hooks.registry`。
注意事项：这是 core 内的扩展点入口，不依赖 GUI、具体事件包或输入执行器。默认没有注册 handler 时完全 no-op。
### `core/events/hooks/models.py`
职责：定义当前已落地的两个 hook 名称、展示标签和统一 payload。
关键导出：`EVENT_HOOK_VISIBLE_TARGET="event_visible_target"`、`EVENT_HOOK_COMPLETED="event_completed"`、`EVENT_HOOK_NAMES`、`EVENT_HOOK_LABELS`、`EventHookContext`。
对外依赖：无内部业务模块依赖。
注意事项：`EventHookContext` 携带 hook 名、导航任务 ID、事件任务 ID、事件类型、事件全局坐标、玩家全局坐标、时间戳、reason 和 metadata。payload 只描述事实，不携带控制决策返回值。
### `core/events/hooks/registry.py`
职责：同步派发事件 hook handler，并隔离 handler 异常，避免 hook 破坏导航主循环。
关键导出：`EventHookHandler`、`EventHookRegistry`。
对外依赖：`core.events.debug.event_log`、`core.events.hooks.models.EventHookContext`。
注意事项：`register()` 返回注销函数；`emit()` 返回本次匹配到的 handler 数量。handler 抛异常时只写 `event hook handler failed` 日志，不向上传播，不执行任何默认输入动作。
### `EventHookRegistry.register(self, hook_name: str, handler: EventHookHandler) -> Callable[[], None]`
行为：注册一个同步 hook handler，并返回可调用的注销函数。
算法：1. 把 hook 名转为非空字符串，空名抛 `ValueError`。2. 校验 handler 可调用，不可调用时抛 `TypeError`。3. 追加到 `_handlers[hook_name]` 列表，保留注册顺序。4. 返回闭包，调用时委托 `unregister(hook_name, handler)`。
副作用：修改 `EventHookRegistry._handlers`。
失败行为：hook 名为空或 handler 不可调用时立即抛异常；不写日志。
调用关系：called by 外部组合根、GUI adapter 或后续自定义模块；当前 core 默认不注册 handler。
### `EventHookRegistry.emit(self, context: EventHookContext) -> int`
行为：按 `context.hook_name` 查找所有 handler 并同步调用，返回匹配到的 handler 数量。
算法：1. 调用 `handlers(context.hook_name)` 取快照，避免派发时注册表变化影响本轮迭代。2. 按注册顺序调用每个 handler。3. 捕获 handler 抛出的 `Exception`，写入 `event hook handler failed` 日志，继续派发剩余 handler。4. 返回本轮 handler 数量。
副作用：可能触发外部 handler；handler 异常时写事件日志。
失败行为：handler 异常被吞掉并记录，不向导航/事件主流程传播。
调用关系：called by `core.navigation_tasks.event_task_runner._emit_event_hook()`。
### `core/events/hooks/instances/key_press.py`
职责：定义可配置的按键 hook 实例，当前行为是触发时按一次自定义按键。
关键导出：`KEY_PRESS_HOOK_TYPE`、`DEFAULT_KEY_PRESS_HOOK_KEY`、`KeyPressHookSettings`、`KeyPressHookInstance`、`key_press_settings_from_dict()`、`key_press_settings_to_dict()`、`normalized_key()`。
对外依赖：`core.events.debug.event_log`、`core.events.hooks.models`。
注意事项：该实例不直接 import 或创建 `MotionController`，而是接收 `press_key(key, reason)` 回调，因此 core hook 实例仍不依赖 GUI 或平台输入实现。`KeyPressHookInstance.__call__()` 会检查实例启用状态、当前 hook 是否在实例 `triggers` 中、`context.event_type` 是否在实例 `event_types` 中、按键是否非空，然后调用注入的按键回调并写 `key hook pressed` 日志。`event_types` 为空表示未绑定任何事件，不会触发。
### `KeyPressHookInstance.__call__(self, context: EventHookContext) -> None`
行为：在匹配触发点上执行一次按键 hook。
算法：1. 若实例未启用或 `context.hook_name` 不在实例 triggers 中，直接返回。2. 若实例未绑定事件类型，或 `context.event_type` 不在实例 `event_types` 中，直接返回。3. 规范化 key，空 key 写 `key hook skipped` 日志并返回。4. 构造 reason `hook:<instance_id>:<hook_name>:<event_type>`。5. 调用注入的 `press_key(key, reason)`。6. 写 `key hook pressed` 事件日志。
副作用：通过注入回调触发一次按键；写事件日志。
失败行为：空 key 降级为跳过；回调异常由外层 `EventHookRegistry.emit()` 捕获并写 `event hook handler failed`。
调用关系：called by `EventHookRegistry.emit()` after `NavigationHookRuntime` registers the instance to selected triggers。
### `features/torchlight/portal/*`
职责：传送门完整事件包。对外暴露 `PortalEventDefinition`，内部拆分小地图 detector、主画面 confirmer 和 handler。
关键导出：`PortalEventDefinition`。
对外依赖：`core.events.detectors.template_matcher`、`features.torchlight.portal.minimap_feature_matcher`、`features.torchlight.portal.minimap_shape_color`、`features.torchlight.portal.main_view_confirmer`。
注意事项：小地图 detector 的识别算法由 `PortalEventConfig.detector_mode` 选择：`template` 只走旧灰度/边缘整块模板；`feature` 只走蓝色本体特征；`feature_then_template` 先走蓝色本体特征、无命中再回退整块模板；`shape_color` 走形状+颜色联合匹配，当前默认使用它压低蓝色相似物误识别。旧配置只含 `feature_detector_enabled` 且没有 `detector_mode` 时仍会兼容映射为旧 feature/template 行为。`PortalMinimapDetector` 现在只保留模板缓存、feature signature 和日志节流状态，mode 选择/命中调用在 `minimap_detection/modes.py`，no-hit/rejected/best-hit 日志在 `minimap_detection/diagnostics.py`，hit 颜色过滤、`minimap_nms_radius` 局部重复合并和 `EventDetection` metadata 构造在 `minimap_detection/conversion.py`。`minimap_feature_matcher/` 当前是同名算法 package：models/masks/templates/response/pipeline 分别承接 DTO、HSV 蓝色 mask、模板准备、响应图峰值提取和主匹配/合并流程。shape+color 同时要求蓝色核心、白/灰外环、组合轮廓、边缘和 HSV 颜色一致，适合压住“蓝色相似但不是传送门”的误报。命中后仍必须通过 `minimap_hit_filter.portal_color_check()`，避免白色墙体、圆形地形细节被识别成传送门。2026-06-04 日志审计发现最近运行仍使用 `feature_then_template` 内存配置，而当前 `map_data/A/event_config.json` 已保存为 `shape_color`；同一轮日志中重复 portal task 的稳定坐标相距约 70-85px，旧 `localization_cluster_radius=56`、`dedupe_radius=32` 无法合并，已改为默认 96 并暴露到事件参数面板。当前传送门主流程是靠近后点击映射传送门点、短暂等待、再按 `D`；即使配置残留 `interaction="click"`，`PortalEventHandler` 也会强制按键交互并记录日志，不再要求主画面蓝紫实体确认。按键/点击后 handler 等待位置变化或小地图周边环境变化才判定传送完成，避免固定等待导致误完成；完成动作会携带入口和出口坐标，runner 将出口附近的传送门任务也标记 completed，防止双门来回触发。`PortalEventHandler` 当前是 `handler/` package：`runtime.py` 保留 handler 状态和 public API，movement/interaction/completion/diagnostics helper 分别承接状态机阶段。

### `core/events/automation/__init__.py`
职责：作为动作事件纯能力包的稳定入口，聚合定义、路由、dispatch、执行器和状态帧类型。
关键导出：`EventDefinitionRepository`、`ExecutableEventDefinition`、`parse_event_definition`、`EventRoute`、`EventDispatch`、`EventRouteRepository`、`EventRouter`、`EventExecutionRuntime`、`EventStateFrame`、`ActionSequenceDefinition`、`ActionSequenceHandler`。
对外依赖：`core.events.automation.definitions`、`routes`、`execution`。
注意事项：入口不导出平台适配器，调用方需要真实热键或 Host/LAN 时应显式依赖 `core.runtime.event_service`。

### `core/events/automation/action_sequence.py`
职责：校验并执行与具体游戏无关的声明式顺序动作，支持 wait、button、parallel、condition、retry 和 emit。
关键导出：`ActionSequenceDefinition`、`ActionSequenceHandler`、`button_mask()`、`inputs_mask()`、`BUTTONS`。
对外依赖：通用 `EventDefinition/EventHandler/EventAction`、事件 hook 契约、共享 controller input mask 和并行轨道时间算法。
注意事项：定义最多 128 步、总超时 1-60000ms、单 tick 最多解释 32 条、生命周期最多执行 512 条；模块只返回 `EventAction`，不访问设备。旧 `core.events.follow_chain` 已删除。

### `core/events/config_schema.py`
职责：为任意事件配置 schema 添加领域中立的紧凑视图与摘要视图提示，同时校验提示字段确实存在。
关键导出：`with_display_hints(schema, *, compact=(), summary=())`。
对外依赖：仅标准库 `copy` 与 `collections.abc`。
注意事项：函数深复制输入，不修改 definition 持有的原始字典；未知字段抛 `ValueError`，使业务 definition 的 UI 元数据拼写错误在注册/测试阶段显式失败。

### `features/torchlight/composition.py`
职责：在应用组合根显式注册 Torchlight 的 Portal 与 Loot 业务事件定义。
关键导出：`register_torchlight_events()`、`build_torchlight_feature_registry()`。
对外依赖：通用 `EventRegistry`、`features.torchlight.portal.PortalEventDefinition`、`features.torchlight.loot.LootEventDefinition`。
注意事项：接收已有 registry 时原地追加并返回同一实例；导航 UI 不导入具体事件定义，`MainWindow` 才决定使用该游戏组合。

### `gui/modes/torchlight/navigation.py`
职责：把 Torchlight 事件 registry、窗口识别和 Loot 调试 overlay 组合成可注入通用导航页的 UI 依赖。
关键导出：`TorchlightNavigationComposition`、`build_torchlight_navigation_composition()`、`find_torchlight_window_rect()`、`build_loot_debug_overlays()`。
对外依赖：Windows window-finder adapter、`features.torchlight.composition`、通用 `EventOverlayContext/EventCircleOverlay`。
注意事项：窗口查找异常降级为 `None`；Loot provider 只读取 `loot` 业务配置并返回纯圆形描述，不直接操作 scene。通用导航包不反向导入该模块。

### `features/torchlight/skills/follow_chain.py`
职责：给通用动作序列提供 Torchlight skill/follow 业务名称和公共 facade。
关键导出：`TorchlightSkillChainDefinition`、`SkillChainDefinition`、迁移期 `FollowChainDefinition`。
对外依赖：`core.events.automation.action_sequence`。
注意事项：不覆盖执行算法、不引入输入副作用；Torchlight 配置和 worker 从此入口引用业务类型。

### `core/events/automation/definitions.py`
职责：提供本机和远程事件记录的唯一可执行解析路径，并集中管理稳定 ID、owner、revision、草稿身份剥离、目录 payload 与远程身份解析。
关键导出：`ExecutableEventDefinition`、`parse_event_definition()`、`new_event_draft()`、`EventDefinitionRepository`。
对外依赖：`core.events.action_tracks`、`core.events.event_catalog.EventRecord`、`core.events.event_store.EventStore`。
注意事项：`save_local()` 只在定义内容变化时增加 revision；缺失的旧活动记录被写成同 ID、revision+1 的 tombstone。`set_device_id()` 只重绑本机记录 owner，不改变 ID/revision。返回的执行定义和草稿均深拷贝，避免 GUI 或运行中 session 反向修改持久化记录。

### `core/events/automation/routes.py`
职责：把 `routes.json` 的中英文历史值规范化为类型化路由，并把 trigger 纯转换为本机或远程 `EventDispatch`。
关键导出：`EventRoute`、`EventDispatch`、`EventRouteRepository`、`EventRouter`。
对外依赖：仅标准库 `json`、`dataclasses`、`pathlib`、`typing`。
注意事项：只接受 controller 1/2/1+2 与 local/paired 端点；未知值立即 `ValueError`。该文件不轮询按键、不访问 Host/LAN、也不执行事件。

### `core/events/automation/execution.py`
职责：用现有 `EventSession` 执行规范化定义，并把每个来源和手柄的输出转换为完整 XInput 状态帧。
关键导出：`EventStateFrame`、`EventExecutionRuntime`。
对外依赖：`core.runtime.event_session.EventSession`、`core.events.gamepad_output.state_from_inputs`、`core.events.automation.definitions`。
注意事项：session key 是 `(normalized_source, controller)`；本机/远程互不覆盖。定义替换只更新 session 的 definitions 映射，`EventSession` 已启动 lifecycle 仍持有启动时快照。该模块没有线程循环、文件、GUI、Host 或 LAN 依赖。

### `core/events/event_store.py`
职责：持久化本机可编辑事件和远程只读目录，完成 legacy 记录迁移、revision 比较和 tombstone 可见性过滤。
关键导出：`EventStore`；新增 `local_catalog()` 返回含 tombstone 的完整 owner catalog，`local()` 只返回活动记录。
对外依赖：`core.events.event_catalog.EventRecord`、`migrate_events`。
注意事项：`apply_remote()` 只接受 revision 更高的记录；远程 tombstone 保留在文件中但被 `remote()` 隐藏。目录发布必须调用含 tombstone 的路径，否则删除无法传播。

### `src/auto_modules/application/event_workbench/__init__.py`
职责：作为事件工作台平台服务的公共导出入口。
关键导出：`EventWorkbenchService`、`EventWorkbenchStatus`、`HostEventBridge`、`HotkeyTriggerSource`。
对外依赖：同包 `service`、`models`、`host_bridge`、`hotkeys`。
注意事项：GUI 应从此入口依赖组合服务；纯 core 算法不应从这里反向导入平台能力。

### `src/auto_modules/application/event_workbench/models.py`
职责：定义服务所需的可注入 trigger/Host Protocol 与不可变 UI 状态快照。
关键导出：`EventTriggerSource`、`EventHostBridge`、`EventWorkbenchStatus`。
对外依赖：`core.events.automation.execution.EventStateFrame`。
注意事项：Protocol 使服务测试不需要真实 Windows、Host 或网络；`peer_errors` 独立保存 fanout 的单 peer 错误，不把它升级为整条服务失败。

### `src/auto_modules/adapters/host/event_bridge.py`
职责：把类型化服务调用翻译为现有虚拟手柄 Host/LAN JSON-lines 命令，是事件路径唯一协议字符串所有者。
关键导出：`HostEventBridge`。
对外依赖：`core.events.automation.execution.EventStateFrame`；默认运行时延迟导入 `virtual_gamepad.client.python.VirtualGamepadClient`。
注意事项：事件 inbox 使用 `sync.share.drain`，目录 inbox 单独使用 `sync.share.catalog_drain`，两者不能互相消费；`write_state()` 保留 source/controller/TTL，`close()` 幂等。

### `src/auto_modules/adapters/windows/hotkeys.py`
职责：把 Windows key state 转换为一次按下只发一个 trigger 的边沿事件。
关键导出：`HotkeyTriggerSource`。
对外依赖：默认读取器在 Windows 上延迟导入 `ctypes`；测试可注入 `Callable[[int], bool]`。
注意事项：支持 F1-F12、A-Z、SPACE 和方向键；未知键不调用平台读取器。模块可在非 Windows 环境导入，只有使用默认读取器时才抛 `RuntimeError`。

### `src/auto_modules/application/event_workbench/service.py`
职责：动作事件工作台的唯一组合根和长期 worker owner，统一本机触发、远程 inbox、目录交换、A->B/C fanout、直接发送、执行帧写入与 shutdown 清理。
关键导出：`EventWorkbenchService`、`LOCAL_SOURCE="event:local"`、`REMOTE_SOURCE="event:remote"`。
对外依赖：纯 `core.events.automation` 模块、`HostEventBridge`、`HotkeyTriggerSource`、`EventWorkbenchStatus` 与 Host deadline clock。
注意事项：服务对 UI 暴露深拷贝记录和不可变状态，不暴露 client/runtime 实例。worker 是长期 bridge 的唯一 owner；直接发送使用独立短连接。原 `LocalEventRuntime`、`RemoteEventRuntime`、`EventCatalogRuntime`、`RemoteEventSender` 已删除，不保留兼容壳。

### `gui/modes/events/workbench.py`
职责：渲染事件库、路由表、运行状态、最近日志和直接发送表单，并把用户命令转交注入的 `EventWorkbenchService`。
关键导出：`EventWorkbenchPage`、`KEY_OPTIONS`、`CONTROLLER_SELECTIONS`。
对外依赖：PySide6、`core.runtime_paths.data_root`、`core.runtime.event_service.EventWorkbenchService`、`ChainEditor`。
注意事项：页面不理解事件 ID/revision/owner 的生成规则，不读写事件/路由/日志文件，不创建 Host client。复制事件通过 `service.new_event_draft()` 去除持久化身份；`shutdown()` 停 Qt timer 后只关闭统一服务且可重复调用。

### `gui/modes/events/action_sequence_editor.py`
职责：编辑通用声明式动作序列、独立输入轨道和单步并行动作组，并在接受前调用通用定义校验器。
关键导出：`ChainEditor`、`ParallelGroupEditor`、`spin()`。
对外依赖：PySide6、`core.events.automation.ActionSequenceDefinition`、通用 gamepad input picker。
注意事项：不包含角色识别、Torchlight 跟随策略或设备连接；事件工作台可独立使用。

### `gui/modes/torchlight/follow/editors.py`
职责：编辑 Torchlight follow actor 的识别算法、HSV/template 参数、手柄槽位、跟随距离和坐标变换。
关键导出：`ActorEditor`，以及为 Follow 页面重导出的 `ChainEditor`、`ParallelGroupEditor`、`spin`。
对外依赖：PySide6、`gui.modes.events.action_sequence_editor`。
注意事项：只有 `ActorEditor` 含 Torchlight follow 业务字段；通用动作序列 UI 的实现不在该文件重复。

### `tests/test_event_definition_repository.py`
职责：验证本机/远程统一解析、稳定身份、版本变更、owner 重绑、草稿复制、legacy fallback 与 tombstone 删除传播。
关键导出：pytest 测试函数，无生产导出。
对外依赖：`EventDefinitionRepository`、临时目录 JSON fixture。
注意事项：全程离线，不创建 Host/client；用文件内容验证持久化契约。

### `tests/test_event_routes.py`
职责：验证中英文 route 兼容、controller 组合、纯 dispatch 和非法记录拒绝。
关键导出：pytest 测试函数，无生产导出。
对外依赖：`EventRoute`、`EventRouteRepository`、`EventRouter`。
注意事项：测试明确要求 router 不做 IO side effect。

### `tests/test_event_execution_runtime.py`
职责：验证本机/远程共享执行器、source/controller 隔离、定义快照、neutral cancel frame 和非法 controller 拒绝。
关键导出：pytest 测试函数，无生产导出。
对外依赖：`parse_event_definition`、`EventExecutionRuntime`。
注意事项：使用注入时钟，不发送真实 XInput report。

### `tests/test_event_host_bridge.py`
职责：以假 client 固定 Host/LAN 命令名、payload、数据 peer 过滤、独立 drain 与幂等关闭契约。
关键导出：`FakeClient` 和 pytest 测试函数。
对外依赖：`HostEventBridge`、`EventStateFrame`。
注意事项：不连接命名管道；命令序列断言防止目录 drain 再次偷取消费事件 inbox。

### `tests/test_event_hotkeys.py`
职责：验证按下边沿、松开重装、UI 全部键名和未知键忽略。
关键导出：pytest 测试函数，无生产导出。
对外依赖：`HotkeyTriggerSource`。
注意事项：注入内存 key-state 函数，不调用 Win32。

### `tests/test_event_workbench_service.py`
职责：在假 bridge/trigger 上验证统一服务的本机执行、远程接收、目录更新、fanout 故障隔离、source 清理、直接发送 deadline 与幂等 shutdown。
关键导出：`TriggerSource`、`FakeBridge` 和 pytest 测试函数。
对外依赖：`EventWorkbenchService`。
注意事项：不会启动 service thread 或真实同步；测试直接调用 `tick_once()` 获得确定性。

### `tests/test_event_workbench_ui.py`
职责：验证事件页面是纯服务 adapter，覆盖加载、保存、复制、启停、发送、日志和关闭。
关键导出：`FakeEventWorkbenchService` 和 offscreen Qt 测试。
对外依赖：`EventWorkbenchPage`、`EventWorkbenchStatus`、PySide6 offscreen backend。
注意事项：断言页面没有在临时 root 创建文件，因此 JSON 持久化不能重新泄漏到 GUI。

## 5. 函数索引与算法实现
### `SimulatedFollowRuntime.__init__ / _plan_safe_route / tick`
1. 构造时将非零障碍归一化为 255、空地为 0；若 `footprint_radius>0`，用椭圆核生成只读膨胀碰撞图；建立 8/4/2/1（去重）的多尺度规划器，全部关闭起点清墙和自动吸附。
2. `tick(now_ms)` 对每名 follower 校验目标/人物时间戳及地图实例；在普通规划前检查 native 观测点是否落在墙/空地栅格边界，若局部可行走起点能安全到达目标则输出有界 `wall_start_recovery` 脱困脉冲；路线失效或目标移动时再重规划，真正不可达才进入 `BLOCKED`。
3. `_plan_safe_route(start,end)` 逐尺度调用通用 A*，对实际起点→首节点、每对相邻节点、末节点→目标在膨胀碰撞图上执行 corner-safe 线段校验；再用原始墙图计算每条链的最小清距和暴露量，按 `route_length + clearance_weight * exposure` 选择安全候选，输出不包含设备副作用。跟踪器和模拟步进也使用同一膨胀图，避免规划安全而执行阶段擦墙。
4. `_wall_start_recovery()` 只在观测栅格被判为墙时搜索半径 12 native 内的可行走起点，并要求该起点到真实目标存在安全路线；`update_follower_position()` 在新视觉样本到达时用上一周期 command vector 与 native 位移计算 cosine alignment/夹角，连续三次低于 0.20 会进入左右交替 recovery。

`Poe2CaptureTestPage._localization_interval() -> int` 将配置的 `localization_fps` 转成周期，并以 legacy `sample_interval_ms` 作上限；`_preview_interval()` 单独按 `preview_fps` 计算低优先级预览周期。`run_dual_first_frame_experiment()` 只读取一次双人 native anchors，最多采集三张短间隔截图，对每张调用注册器并按 accepted、pair confidence、shape quality、anchor error 选择候选，避免首张过渡帧决定整次首帧结果。

`Poe2DualMotionWorker._capture_one()` 在 worker 线程中完成一帧截图、预处理、颜色候选和 `DualVisualTracker.tick()`；`_offer()` 以单槽替换语义发布图像，并在覆盖前独立取最大 `recovery_revision` 存入待消费槽。`take_latest()` 清图像通知，`take_pending_recovery_revision()` 单独取出并清零恢复版本，故边沿图像被覆盖仍可恢复。`_run()` 对每帧异常只递增 `failed_frames` 并发出 `frame_failed`，成功帧清零连续失败；达到 `max_consecutive_failures` 才发出 `failed`。页面先消费恢复版本并释放输出，再进行内存重锚；只在 Qt 线程绘制。

### `BoundedRoleObservations.update(identity: Hashable, *, at_ms: int, candidate: tuple[float, float] | None) -> RoleObservation`
1. 校验 identity 已由 `seed()` 初始化且时间不倒退；以最后可信时间计算 `age_ms` 和 `observed_uncertainty + drift_per_second * age_ms / 1000`。
2. 候选存在时，连续失明达到门槛后要求落在 `reappearance_radius + uncertainty` 内；同一位置附近连续达到 `reappearance_frames` 才以该候选重新 `seed()`，使 `visible=True`。
3. 无候选、越门或尚未确认时不续期最后可信时间，只递增 missing 计数并返回估计；超出年龄或误差上限使 `available=False`。
副作用：仅修改实例内按 identity 分隔的字典；无文件/设备操作。失败行为：未初始化身份抛 `KeyError`，时间倒退或非有限坐标抛 `ValueError`。Called by `DualVisualTracker.tick()`。

### `Poe2CaptureTestPage` 双人同目标实验

```python
def _make_follow_runtime(self, reference: Any, map_identity: MapIdentity) -> SimulatedFollowRuntime
def start_dual_target_experiment(self) -> None
def _tick_dual_target_experiment(self) -> None
def _tick_dual_target_experiment_impl(self) -> None
def _render_dual_target_overlay(self) -> None
def stop_dual_target_experiment(self, *, _preserve_recovery: bool = False) -> None
def _save_dual_target_recovery_context(self) -> None
def _maybe_resume_dual_target_after_relocalization(self) -> None
def _update_follow_local_contact(self, runtime: SimulatedFollowRuntime, state: Any, role: RoleId, observation: Any, *, log_step: str, emit_log: bool = True) -> None
```

1. `_make_follow_runtime()` 以只读 native 墙层和地图身份创建每角色独立规划的 runtime；参数保持 8 native 到达半径、700ms 位置 TTL、8/4/2/1 多尺度寻路、零硬膨胀、4 样本接触门，与旧跟随实验相同。构造非法墙图抛 `ValueError`，无文件/设备副作用。
2. `start_dual_target_experiment()` 检查 snapshot、首帧 transform、双人 tracker、真实视觉帧采集时间及两个不同的有效角色；先停止其他输入场景，再绑定控制器 1/2 的输出对象并添加两个 `PROGRAM` follower。只建立待命状态，未点击前不取得 lease、不发输入；factory 异常关闭已建输出并显示错误。
3. `_on_follow_map_click()` 仍统一把 source pixmap 坐标逆变换到 native，校验墙图边界并回投 display；只有新场景活跃时将一次有效点击赋给共享 target。无效越界点击保留上一目标，坐标变换整体失败则停止新会话。`_tick_dual_target_experiment_impl()` 只采用最新真实 `captured_at_ms` 的角色点更新 runtime；先检查 700ms 帧龄、地图身份和 tracker 状态，再由 `runtime.tick()` 分别生成观察。仅 `PROGRAM_READY` 的角色可 arm，随后逐角色 `apply()`；到达/过期/阻塞由输出适配器中性释放。
4. `_update_follow_local_contact()` 把本帧 screen marker 和 native 命令逆变换为屏幕方向，调用 `inspect_minimap_contact()` 的中心线/侧向探针，并把墙前、可逃逸方向和距离交给该角色的 runtime contact monitor。证据读取异常只写 `local_contact_failed`，不冒充 Host 输出失败；新场景日志每 5 tick 限流，旧程序探针行为保持原样。
5. 若任一观察明确要求 `relocalization_requested`，新场景先保存 source 目标、两角色身份和 instance，立即释放两个 lease，再用现有 `_start_dual_motion(recovery=True)` 做一次双人内存锚点和首帧注册；10 秒内重复要求进入恢复冷却，不启动第二次读内存。`_maybe_resume_dual_target_after_relocalization()` 仅在同实例、两个角色可见、新 tracking 帧不超过 700ms 时重建并重放点击；该门与正常启动门保持一致，避免恢复入口消费后又被启动入口拒绝。异常、关闭、清图或用户停止会清掉 context。
6. `_render_dual_target_overlay()` 用同一 registration 把每人的 native 当前位置及规划器实际给出的路线点映射到显示 pixmap；共享目标单独作为标记显示，不把无路径观察伪画成直达线，不更改底图或坐标。`stop_dual_target_experiment()` 停计时器、close 两个输出、清目标与路线；输出异常被记录，Qt tick 的未预期异常统一进入该安全停止。两人均到达时停止计时器，再次点击可重新启动。

副作用：Qt 控件/overlay 和侧栏日志更新；有效点击后经已有 Host 输出适配器向控制器 1/2 发送向量。调用关系：`ScalableMapWidget.pixel_clicked` → `_on_follow_map_click()` → `_tick_dual_target_experiment()` → `SimulatedFollowRuntime.tick()` → `ProgramFollowOutput.apply()`；双人 worker/sync 视觉帧 → `_render_dual_motion_state()` → `_render_dual_target_overlay()`；定位恢复 → `_save_dual_target_recovery_context()` → `_start_dual_motion()` → `_maybe_resume_dual_target_after_relocalization()`。

### `SimulatedFollowRuntime.add_follower()` / `Poe2CaptureTestPage._start_dual_motion()` / `_maybe_resume_program_probe_after_relocalization()`
```python
def add_follower(self, role: RoleId, position: PositionSample, *, mode: ControlMode = ControlMode.PREVIEW) -> None
def _start_dual_motion(self, *, recovery: bool, first_frame_ready: bool = False) -> None
def _maybe_resume_program_probe_after_relocalization(self) -> None
```
1. `add_follower()` 校验角色、地图实例和位置后，为该角色建立独立 `ContactMonitor`，其 `required_samples` 取 runtime 的 `contact_required_samples`；因此多个角色的无进展计数不会共享。
2. `_start_dual_motion(recovery=True, first_frame_ready=False)` 先停止旧 worker/输入但保留 recovery context；未交付首帧时清空旧首帧并调用 `run_dual_first_frame_experiment(render_map=False, force_memory_read=True)`，读取同一 `instance_id` 的双人 native anchors，最多对短间隔截图做注册候选选择，再创建新的 `DualVisualTracker`。异步 worker 已交付 `status=accepted` 时，回调以 `first_frame_ready=True` 进入同一函数，消费 `_apply_dual_first_frame_bundle()` 写入的 accepted 缓存，不能把 recovery 结果重新置空；结果状态、accepted 标志和 has-frame 会写入 `dual_motion.first_frame_context`。
3. 新 worker 结果或同步 tick 更新 `latest_dual_state/latest_dual_captured_at_ms` 后，`_maybe_resume_program_probe_after_relocalization()` 校验状态为 tracking、角色可见且帧龄不超过 700ms；恢复保存的角色/控制器选择，以保存的 native target 调用 `_start_program_move_probe_at(..., _confirmed=True)`。视觉跟随 recovery 由 `_save_dual_follow_recovery_context()` 保存 source 点击和角色模式，在新鲜 tracking 帧后原地同步 tracker/runtime 并重新挂载输出，确保恢复前不发送输入且不会重新丢失 recovery context。重定位失败或选择不存在时清理 context，不申请输入。
副作用：步骤 2 每次 recovery revision 最多读取一次游戏内存、更新 Qt tracker/worker；步骤 3 可能重建一个显式 Host lease；不会发送网络同步。失败行为：首帧拒绝、worker 启动异常、帧过期或角色缺失均记录 `program_probe.relocalization_failed` 并保持中性停止；10 秒冷却阻止重复 recovery。
调用关系：`_tick_program_move_probe()` → `_start_dual_motion(recovery=True)` → `run_dual_first_frame_experiment()`；`_on_dual_worker_result()`/`_tick_dual_motion()` → `_maybe_resume_program_probe_after_relocalization()` → `_start_program_move_probe_at()`。

### `poe2_movement_probe.run_bounded_output`
先检查当前前台 PID 是否为游戏；否则不申请 lease。运行中每次写入前重新检查焦点；无论正常完成或异常都发送中性并停止输出。仅用于有界定向实机诊断，不证明地图方向到摇杆方向已经校准。
### `marker_candidates_from_observation(observation: ObservationFrame, *, max_candidates: int = 2) -> tuple[PlayerMarkerCandidate, ...]`
1. 按候选置信度降序排列，并读取可选 bbox/profile evidence。
2. 对同一 contour 的 outline/core 组合执行 IoU 或中心距离抑制；已保留高置信候选时丢弃重复轮廓。
3. 先为不同 profile/identity hint 保留候选，再按置信度补齐到 `max_candidates`，将 evidence 原样带入 `PlayerMarkerCandidate`。
副作用：仅创建不可变候选，不修改观察帧；失败行为：非 `ObservationFrame` 或非法数量抛 `TypeError/ValueError`。Called by `DualFirstFrameExperiment.register()` and `Poe2CaptureTestPage._tick_dual_motion()`.

### `DualVisualTracker.start(frame: HybridFrame, result: DualFirstFrameResult, initial_candidates: Sequence[PlayerMarkerCandidate] = ()) -> DualMotionState`
1. 要求首帧已接受且有两个身份，否则抛 `ValueError`。
2. 保存固定相似变换、每个身份在首帧的局部坐标；颜色 profile 名互异时建立身份提示。
3. 清零位移失配/纠偏计数，输出两名人物的 native 坐标。
副作用：仅修改此 tracker 实例的内存状态；不读取进程或文件。Called by `Poe2CaptureTestPage._start_dual_motion()`。

### `DualVisualTracker.tick(frame: HybridFrame, candidates: Sequence[PlayerMarkerCandidate]) -> DualMotionState`
1. 用 canonical wall 和 `estimate_bounded_displacement()` 获取静态墙体屏幕位移；把该位移经固定角度/镜像/比例映射到 native，并从共同平移中减去。
2. 位移失败或周期纠偏到期时，把当前墙体按固定形状变换后调用有界 `matcher.match()`；成功则只修正共同平移。相位失败但有界纠偏成功时，对平移差做逆线性变换，恢复人物候选的屏幕预测位移。
3. 最多六个候选按颜色 hint、共同墙层位移后的屏幕预测点和 `max_marker_step` 枚举身份赋值；选择可赋身份数最多、总距离最小的选项，最佳与次佳差不足 `identity_margin` 时判歧义，不猜角色。
4. 每名角色的候选经同一 `transform_local_point()` 转为 native 并交给 `BoundedRoleObservations.update()`；缺失或重现待确认时保留最后可信 native 点，只随观测年龄扩大误差。每角色输出 `visible/available/age_ms/uncertainty_native`，全部候选可信才为 `tracking`，否则为 `degraded`。
5. 墙层位移与有界局部 matcher 均失效，或任一角色时间/误差预算耗尽时触发一次 `recovery_requested` 和单调 revision；之后维持 `recovery_required`。首帧主角色局部锚点供 matcher 使用，不能固定用截图中心。
副作用：仅更新本 tracker 实例的上一可信帧、共同平移和身份预测位置；不读内存、不保存文件。失败行为：未启动抛 `RuntimeError`；墙体失配先 degraded 后请求恢复。Called by `Poe2DualMotionWorker._capture_one()`（生产 profile）或 `Poe2CaptureTestPage._tick_dual_motion()`（同步 dummy/test hook）。

### `Poe2CaptureTestPage._render_preview()` / `refresh_preview()`
```python
def refresh_preview(self) -> None
def _render_preview(self, frame, *, combined=None) -> None
```
算法实现：
1. `refresh_preview()` 从当前 PoE2 monitor config 只截取一帧；空帧或异常清空三块预览并显示错误。
2. `_render_preview()` 总是绘制原图和独立预处理图；调用方传入 `combined` 时直接绘制该帧的 `combined[0]`，保证双人注册和预览是同一份特征。
3. 未传 `combined` 时，读取当前 marker 配置；双人预览状态显式传 `exclude_player=False, exclude_dynamic=False`，其余模式保持识别器默认人物/动态过滤契约。
4. 双人按钮在得到有效同帧特征后设置状态；重新获取地图、清空或启动单人/多帧定位将其复位。
副作用：截图 provider 只读屏幕，更新三个 QLabel pixmap/错误文本与日志；不写文件、不发送输入或网络消息。
失败行为：截图或识别异常由 `refresh_preview()` 捕获并清空旧预览；空图同样拒绝沿用上一帧。
调用关系：`QTimer.timeout -> refresh_preview -> _render_preview -> HSVRecognizer.extract_combined`；双人按钮直接把已提取的 `combined` 交给 `_render_preview()`。

### `MultiframeLocalizationSession.tick() -> PositionEstimate`
```python
def tick(self) -> PositionEstimate
```
行为与算法：
1. 仅在 active 时采集当前 `HybridFrame`，构建带 wall/observed/raw、local offset、segment 和位移的只读 evidence。
2. 首次或恢复 revision 通过 `anchor_once()` 最多读一次 native 人物锚点；失败保持等待/收集，不循环读内存。
3. 调用 coordinator ingest；达到 A/B 门时冻结 request，复制 coordinator 外壳并深复制 A/B 策略后提交隔离 worker，主 tick 继续采集可靠位移。
4. 超时将 active future 转入 retired 集合并释放调度槽；新 evidence version 可以提交新 worker，旧 worker 完成/异常只记录日志。未超时的 worker 完成后先检查 session generation，再检查 token 与当前 instance/recovery/evidence/segment；任一版本不匹配直接丢弃。
5. 注册成功后补偿后台期间累计位移，再发布唯一 `PositionEstimate` 给 listener/UI。
副作用：屏幕读取；恢复 revision 可发生一次游戏进程只读；后台 CPU 注册；无文件写入或输入输出。
失败行为：inactive tick 抛 `RuntimeError`；采集/证据异常传播给页面日志；超时 worker 与 stop/reset 后旧 worker 均 fail closed，retired worker 异常只记录日志。
调用关系：Called by `Poe2CaptureTestPage._tick_multiframe()`；Calls frame source、evidence builder、anchor provider 和 coordinator。

### `MultiframeLocalizationCoordinator.evaluate_registration/apply_registration_outcome`
```python
def evaluate_registration(self, request: RegistrationRequest) -> GlobalStrategyOutcome
def apply_registration_outcome(self, outcome: GlobalStrategyOutcome) -> PositionEstimate
```
行为与算法：
1. 对 frozen window 独立执行已启用的 A/B；A 异常会结构化记录但不阻断 B，反之亦然。
2. A/B 候选统一交给 `RegistrationValidator` 检查锚点、轨迹、holdout、margin 和 peer 冲突；只有 validator 确认的 native `AbsoluteRegistration` 可发布；A 被拒绝时策略状态同步为 rejected。
3. 提交前比较四元 token；任一版本变化都拒绝旧结果。
4. 双候选都通过时按 `LocalizationResult.confidence` 选择较优注册；确认时初始化 estimator、增加 registration version、进入 tracking，并按顺序补偿 pending motion。
5. 无候选时回 collecting；跟踪中的单次局部纠偏失败只进入 degraded，连续失败达到门槛后才开启一个新 recovery revision。
副作用：更新 coordinator 内存状态，不写盘、不读进程。
失败行为：reference 规范化仅对可预期 `ImportError/TypeError/ValueError` 回退；registration 缺 position 时拒绝确认。
调用关系：Called by session worker/result collector；Calls Strategy A/B、`confirm()`、`_predict_registered_shift()`。

### `StitchThenRegister.evaluate()` / `JointCandidateStrategy.update()`
```python
def evaluate(self, window, submap, *, anchor, reference) -> StrategyResult
def update(self, frames: Sequence[MultiFrameEvidence], *, anchor: PositionAnchor, reference_boundary: np.ndarray, evidence_version: int | None = None) -> CandidateSet
```
行为与算法：
1. A 检查关键帧数、墙体像素和移动跨度，用训练帧重建 submap 并调用锚点约束 registrar；返回 support/holdout 元数据，供 coordinator 的统一 validator 复核。
2. A 对保留 holdout 投影，使用 forward error/coverage 验证；未过门返回 rejected，不复用训练证据提高置信度。
3. B 从方向/镜像/比例 basin 起步，以 `translation = anchor - M(local_player + local_offset)` 对每帧建立同一 native 变换，再按 `SearchLevel` 逐级缩小角度、比例和平移步长。
4. B 累计 Huber 正反向距离、原始 coverage 和局部切向误差，按真实 transform basin 去重，保留候选区域；45 度只是粗搜索起点，不是最终方向量化。
5. B 只有帧数、最佳分、margin 和留出误差同时过门时 confirmable。
副作用：仅更新各策略的内存缓存。
失败行为：证据不足返回结构化 insufficient/rejected；数组/锚点契约错误抛显式异常。
调用关系：Called by coordinator worker；Calls rolling submap、shape score 和 hybrid registrar。

### `RegistrationValidator.validate()` / `LocalShapeCorrector.correct()`
```python
def validate(self, candidate: AbsoluteRegistration, *, anchor: PositionAnchor, frames: Sequence[MultiFrameEvidence], support_frames: Sequence[int], holdout_error: float, best_error: float, second_error: float | None = None, peer: AbsoluteRegistration | None = None) -> RegistrationDecision
def correct(self, *, frame: HybridFrame, observed_mask: np.ndarray, predicted_position: tuple[float, float], registration: AbsoluteRegistration, reference: TerrainReference) -> CorrectionResult
```
行为与算法：
1. validator 先拒绝跨实例、支持帧不足或缺帧候选，再把首帧人物局部点经 `L -> N` transform 投影，与内存 anchor 和候选位置共同计算锚点误差。
2. validator 逐对检查 F2F shift 与累计 local offset 的轨迹一致性，然后检查 holdout 上限、首二名 margin；A/B 同时存在时再比较位置、角度和镜像。
3. corrector 只在预测 native 位置附近生成有界平移/细角度候选，用当前 observed mask 和 reference boundary 调用同一 shape score，不进行整图搜索。
4. 最佳局部候选达到分数、coverage 和 margin 门后返回修正位置、transform 与 covariance；否则返回结构化拒绝原因，由 coordinator 计数降级。
副作用：仅更新局部缓存/诊断；不读进程、不写文件、不执行输入。
失败行为：validator 任一门失败返回 `confirmed=False`；缺失 peer 位置返回 `strategy_missing_position`；corrector 证据不足返回 rejected，数组契约错误显式抛出。
调用关系：Called by `MultiframeLocalizationCoordinator.evaluate_registration()` / `_run_tracking()`；Calls `transform_points()`、`score_shape()`。

### `MultiframeArchive.save()` / `MultiframeArchive.load()`
```python
def save(self, directory: str | Path, *, evidence: Sequence[MultiFrameEvidence], anchor: PositionAnchor, instance_id: str, reference: TerrainReference, estimate: PositionEstimate | None = None, diagnostics: Mapping[str, Any] | None = None) -> Path
def load(self, directory: str | Path) -> MultiframeReplayBundle
```
行为与算法：
1. `save()` 校验 instance/anchor/reference，写 schema 3 manifest 与 compressed NPZ，包含完整 native reference 三层、raw/wall/observed、motion、offset、segment、keyframe、estimate 和 diagnostics。
2. 写入隐藏临时目录完成后用原子替换发布；目标已存在或中途失败均不留下可被误读的半归档。
3. `load()` 只接受 schema 3 与 `coordinate_space=native`，用 `allow_pickle=False` 加载数组，重建 typed anchor/reference/evidence/estimate；estimate 内的 candidate region、transform 和 covariance 均重新经过模型边界校验；二维 shift 必须恰有两个有限数。
4. 旧 schema 2 或任何手工方向归档直接拒绝，避免把 oriented-preview 数据混进 native 回放。
副作用：仅显式调用时读写用户指定归档目录；实时循环不自动落盘。
失败行为：缺 manifest/NPZ、版本/坐标错误、实例不一致、数组键或二维字段非法均抛 `ValueError`/底层 I/O 异常；保存失败清理临时目录。
调用关系：Called by capture test page save action and replay probe；`load()` output feeds A/B strategies.

### `build_localization_presentation()`
```python
def build_localization_presentation(estimate, *, registration, coordinator_registration_version: int, trajectory, candidates) -> LocalizationPresentationState
```
行为与算法：
1. 读取 estimate registration version，与 coordinator 当前 version 比较。
2. 仅当版本相同且大于零时把 registration 放入不可变 presentation state，否则置空并标记等待自动校准。
3. position、trajectory 和 candidates 复制为单次 UI tick 快照；调用方在版本变化时清空旧轨迹，避免跨坐标版本连线。
4. presenter 先在 native pixmap 上画候选、轨迹和人物，再对整体应用 registration 逆变换，保证同一 D 空间方向。
副作用：只创建内存状态和 Qt 展示副本，不修改 native 数据。
失败行为：未确认/版本不一致时 fail closed 为 native 展示；空 pixmap 返回空图。
调用关系：Called by `Poe2CaptureTestPage._tick_multiframe()`；Calls `present_localization_overlay()` and display point transform.

### `NavigationLocalizationAdapter.to_observation()`
```python
def to_observation(self, estimate: PositionEstimate, *, now_ms: int, expected_instance_id: str | None = None, expected_registration_version: int | None = None) -> NavigationObservation
```
行为与算法：
1. 同时校验 confirmed、fresh、position、age、instance 和可选 registration version；diagnostics 中时间戳不是有限数时回退 typed `estimate.age_ms`，不让非结构化诊断破坏导航门。
2. 复制只读 position/velocity/covariance/candidate regions；任何门失败仍返回 observation，但 `executable=False` 并携带 reason。
3. 从协方差最大特征值计算 `r_safe = r_player + k*sqrt(lambda_max(P)) + r_map_error`。
副作用：无。
失败行为：非法协方差在 DTO 构造期拒绝；定位不可信不抛异常而 fail closed。
调用关系：当前只由实验/测试消费，尚未接正式导航执行。

### `paths.repository_root() -> Path`
```python
def repository_root() -> Path
```
行为与算法：
1. 从已导入的 `_PACKAGE_ROOT` 开始向父目录遍历。
2. 选择同时存在 `main.py` 与 `src/auto_modules` 的第一个 candidate，兼容源码仓库和安装 payload 的 `app` 目录。
3. 普通 wheel/editable 环境没有 launcher 时回退到 package root 的两级父目录。
副作用：无；只读取目录存在性。
失败行为：无显式异常；极端非标准安装按 deterministic fallback 返回路径。
调用关系：Called by `resource_root()`、`data_root()`、UI composition path helpers。

### `program_output.host_clock_ms() -> int`
```python
def host_clock_ms() -> int
```
行为与算法：
1. Windows 下读取 `kernel32.GetTickCount64`，与 .NET Host `Environment.TickCount64` 使用同一 uptime 时基。
2. 非 Windows 测试环境回退为 `time.monotonic()*1000`。
3. 始终返回整数毫秒。
副作用：只读系统单调时钟，不连接 Host、不发送输入。
失败行为：Windows API 不可用时异常向上传播；调用方可注入 `host_clock_ms_func` 避免平台依赖。
调用关系：Called by `ProgramGamepadOutput.start/write()`、`FollowTransport.publish/send_event()`、application services。

### `ProgramGamepadOutput.start/write/stop/diagnostics`
```python
def start(self, *, requested_at_ms=None)
def write(self, vector, *, elapsed_ms=20, valid_for_ms=None, buttons=0)
def stop(self)
def diagnostics(self) -> dict
```
行为与算法：
1. `start()` 拒绝重复 lease，发送 `program.acquire(controller, requestedAtMs)`，保存返回 token 并重置 slew limiter。
2. `write()` 校验二维有限 vector，经 2x2 basis 转换到摇杆坐标并按向量范数归一化到 XInput `[-32768,32767]`。
3. 非零向量通过 `StickSlewLimiter` 限制变化率；零向量或无效 TTL 立即归零，不能因 slew 延迟安全停止。
4. TTL 被 controller 上限夹紧，发送完整 `program.state` 和 Host clock deadline；先计算请求返回后的剩余 TTL，再记录本次输入 vector、basis 后 vector、最终轴值和 TTL，避免诊断日志在 accepted 路径中先使用未初始化变量。
5. `stop()` 先清本地 token/limiter 和最后命令快照，再在曾获取 lease 时发送 `program.release`；重复 stop 无 wire 副作用。
6. `write()` 测量 `program.state` Host 请求耗时，失败时记录异常和耗时后原样传播；慢请求（≥50ms）输出告警，快照保留 `host_request_ms`。
7. `diagnostics()` 调用 Host status/state，测量两次请求总耗时并返回 `controller`、`acquired`、`basis`、`last_command`、`last_host_request_ms`、`diagnostics_elapsed_ms`，不改变 Host 状态。
副作用：仅通过注入 client 写 Host named-pipe protocol；不会启动 mapping 或安装驱动。
失败行为：未 acquire 写入抛 `RuntimeError`；非法 controller/basis/vector/TTL 抛 `ValueError`；client 异常传播给 application worker 做安全停止。
调用关系：Called by `features.torchlight.follow.workers.actor_worker()`；Calls `StickSlewLimiter`、client `request()`、`host_clock_ms()`。

### `FollowTransport.publish/send_event/poll`
```python
def publish(self, position: SharedPosition) -> bool
def send_event(self, device_id, name, targets, *, host_deadline_ms=None)
def poll(self) -> tuple[tuple[SharedPosition, ...], tuple[SharedEvent, ...]]
```
行为与算法：
1. `publish()` 用 caller local clock 计算观测 age，拒绝负 age 或 `>=500ms` 数据，再把剩余期限转换为 Host clock deadline。
2. `send_event()` 生成或接受 Host deadline，在发送前再次与 Host clock 比较；过期直接返回 `False` 且不触碰 client。
3. 注入 manager 后，`poll()` 调用一次 `manager.pump()`，从本对象的 position/event 订阅 inbox 分别取出消息；兼容模式才由本对象直接调用 `sync.share.drain`。
4. position 必须包含有限 age/x/y/confidence 且 confidence 在 `[0,1]`；用 IPC 开始时间减 age 重建 local timestamp，并在 IPC 返回后再次检查是否过期。
5. event 的 remainingMs 必须在 `(0,500]`，换算 local deadline 后必须仍未过期；非法单条记录被丢弃，其他记录继续。
副作用：manager 路径经 capability lease 发布并由共享 Host adapter 统一 drain；兼容路径直接请求 Host `sync.share.*`；不直接拥有 socket。
失败行为：单条 malformed inbound 捕获 `KeyError/TypeError/ValueError` 并丢弃；client request 异常向上传播。
调用关系：Called by `features.torchlight.follow.service.FollowService._network()`；Calls injected client 和 Host-compatible clock。

### `LanSyncService.RunControlsAsync(Session session, CancellationToken token) -> Task`
```csharp
private async Task RunControlsAsync(Session session, CancellationToken token)
```
算法实现：
1. 为每会话启动唯一 TLS control writer，从 bounded `Session.Controls` 依序发送消息；reader 顺序解析 `type`。
2. 接收端对 `capability-update` 反转 flags、检查 mode/接收许可、手柄范围与独占；失败只排队 `capability-reject`，成功撤销旧 grant 或生成新 grant，再排队含 `controllers/grants` 的 ack。
3. 发送端对 ack 比对 requestId/flags/scope/grants，更新 `Controllers`、`Initialized`、恢复能力并异步持久化；reject 只清理 pending 和记录 peer error，不关闭数据会话。
4. 对共享事件/目录仅在对应 session capability 存在时交给 `ReceiveSharedEventLocked()`；`permissions` 更新变化的 grant 并触发下次输入 baseline。
5. 退出时取消 writer 并等待完成，外层 `StartOutgoingAsync()/AcceptClientAsync()` 负责 `CloseLocked()`。
副作用：写 TLS、更新 `_remote`/`_trusted`/`_recoveryCapabilities` 和 `preferences.json`/`trusted.json`；不直接发送真实手柄输入。
失败行为：授权不成立回 `capability-reject` 并保持原 session；requestId/grants 不匹配抛 `AuthenticationException`，控制链断开并中立化；队列溢出则关闭当前 session。
调用关系：Called by `AcceptClientAsync()`、`StartOutgoingAsync()`；Calls `ValidateIncomingCapabilitiesLocked()`、`SavePreferencesLater()`、`ReceiveSharedEventLocked()`。

### `LanSyncService.Dispose() -> void` and `ScheduleAutoReconnectLocked(string peerId, string reason) -> void`
```csharp
public void Dispose()
private void ScheduleAutoReconnectLocked(string peerId, string reason)
```
算法实现：
1. `Dispose()` 在 gate 中标记停止并同步重置内存输入，关闭每个 session，但不清除磁盘恢复资格；取消网络 worker，等待持久化队列完成后释放 identity。
2. 新实例读取 `Preferences` 的 mode/许可/恢复列表，启动监听；`ConfigureNetwork()` 对每个恢复 peer 请求调度。
3. 调度器拒绝已手动 block、遗忘、已在连接或 generation/startVersion 不匹配的 peer；取有界退避和保存的 capability set，按 input flag 选择 `start` 或 `start-data`。连接失败会再次调度，成功注册会话时重置退避。
4. 延迟结束后再检查 fence，才调用 `StartOutgoingAsync()`；每次连接重新生成 sessionId、密钥与 grant。
副作用：关闭 TLS/UDP 和线程；读取/保留 `preferences.json`、`trusted.json`，重新建立受信 LAN 会话。
失败行为：取消/已停止直接退出；连接异常写 peer error 并由后续断开路径退避，手动 stop/reset/forget/emergency 不再自动调度。
调用关系：Called by Host shutdown / `CloseLocked()` / `ConfigureNetwork()`；Calls `StartOutgoingAsync()` and `ReconnectBackoff.Next()`。

### `with_display_hints(schema: dict, *, compact: Iterable[str] = (), summary: Iterable[str] = ()) -> dict`
行为：为通用事件配置 schema 标注紧凑视图和摘要视图字段。
算法：1. 深复制输入 schema，避免业务 definition 的原始字典被 UI 修改。2. 将两个字段 iterable 转为集合并计算未知字段。3. 存在未知字段时抛 `ValueError`。4. 分别写入 `compact=True` 与 `summary=True` 并返回副本。
副作用：无；只分配并返回新字典。
失败行为：显示提示引用不存在的字段时抛 `ValueError`，不静默忽略业务配置错误。
调用关系：called by Torchlight Portal/Loot `config_schema()`；calls `copy.deepcopy()`。

### `build_torchlight_navigation_composition() -> TorchlightNavigationComposition`
行为：生成供应用组合根注入通用导航页的 Torchlight UI 依赖集合。
算法：1. 选择 `build_torchlight_feature_registry` 作为 registry 工厂。2. 选择 `find_torchlight_window_rect` 作为窗口 adapter。3. 将 `build_loot_debug_overlays` 组成不可变 provider tuple。4. 返回 frozen dataclass。
副作用：无；不会在构造时枚举窗口、加载模型或启动运行时。
失败行为：构造本身不抛业务异常；窗口查找错误只会在 finder 被调用时降级为 `None`。
调用关系：called by `MainWindow.setup_ui()`；其返回字段传给 `NavigationModeWidget.__init__()`。

### `build_loot_debug_overlays(context: EventOverlayContext) -> tuple[EventCircleOverlay, ...]`
行为：把 Torchlight Loot 的人物中心遮罩调试配置转换为通用圆形 overlay 描述。
算法：1. 从 `context.event_config` 读取 `loot` 配置。2. 依次检查配置存在、人物位置存在、事件启用、中心遮罩启用和调试显示启用。3. 规范化半径至少为 1。4. 乘 `draw_scale` 得 scene radius。5. 返回一个蓝色 `EventCircleOverlay`；任一 gate 不满足返回空 tuple。
副作用：无；不访问 QGraphicsScene。
失败行为：缺配置/位置降级为空；非数值半径的转换错误向调用方传播，以暴露无效业务配置。
调用关系：registered by `build_torchlight_navigation_composition()`；called by generic `render_event_overlay()`。

### `render_event_overlay(scene, nav_core, event_coordinator, items: list, *, overlay_providers=()) -> list`
行为：清除旧图元，绘制通用事件任务 marker，并绘制注入 provider 返回的圆形调试图元。
算法：1. 缺少 scene/nav_core/coordinator 时清理或返回空。2. 清除上一帧 items。3. 从 coordinator config、当前位置和 draw scale 构造 `EventOverlayContext`。4. 顺序调用 provider 并把每个 `EventCircleOverlay` 映射到 scene。5. 遍历 `EventCoordinator.overlays()` 绘制任务圆点和 label。6. 返回本帧图元列表供下次清理。
副作用：向传入的 QGraphicsScene 添加/移除 item；不修改事件配置、任务或 provider 状态。
失败行为：被删除的 Qt item 在清理时捕获 `RuntimeError`；provider 异常当前向帧循环传播，便于测试发现错误组合。
调用关系：called by `NavigationMapDisplayLifecycle.render_event_overlay()`；calls injected business overlay providers and `EventCoordinator.overlays()`。

### `ActionSequenceDefinition.__init__()` / `ActionSequenceHandler.update()`
```python
def __init__(self, name, steps, *, hooks=None, timeout_ms=30000, priority=0, resume=False)
def update(self, tick: EventTick, task: EventTask) -> EventAction
```
行为与算法：
1. definition 深拷贝最多 128 个步骤，验证 operation 白名单、0-5000ms 步长、controller input、并行轨道、1-10 次 retry、分支边界和 hook/condition 名称。
2. handler 首 tick 记录单调起点；时钟倒退或达到总超时时返回 `EventAction.fail("chain_timeout")`。
3. 每 tick 最多解释 32 个无等待步骤；累计最多 512 条，阻止条件/重试环形成 busy loop。
4. wait/button/parallel 在持续期内返回 `EventAction.wait()`；button 写合并 bit mask，parallel 使用共享时间线计算当前 inputs，再转换为 mask。
5. condition 从 `task.metadata["conditions"]` 取布尔值，按 then/else 跳转；retry 按步骤索引单独计数并有限回跳。
6. emit 只向注入的 hook registry 发送 `EventHookContext`；序列结束返回 complete，单 tick 解释预算耗尽时返回 1ms wait。
副作用：只有显式 hook registry 的同步 emit；不读写文件、不创建设备、不发送输入。
失败行为：非法定义抛 `ValueError`；运行时超时或指令上限返回失败 action，不抛出到控制 worker。
调用关系：Torchlight `FollowConfig.validate()`/`actor_worker()` 经 skill facade 构造 definition；`EventRunner` 调用生成的 handler。

### `LauncherPaths.LauncherPaths(string moduleRoot)`
```csharp
public LauncherPaths(string moduleRoot)
```
行为与算法：
1. 把 service module root 转为绝对路径。
2. 从 `services/virtual_gamepad` 向上两级得到 Auto Modules repository root。
3. 再向上一级得到共享 workspace root；`.venv` 和 `dotnet-sdk2` 从此层查找。
4. `SourceRoot` 固定从 repository root 拼接 `src`，UI/client 继续从 `src/auto_modules` 定位。
副作用：无；只构造路径。
失败行为：目录层级不足抛 `ArgumentException`；具体 executable 缺失由 `FindExecutable()` 抛 `FileNotFoundException`。
调用关系：Called by launcher `Program.Main()` 和 tests；used by `LauncherCoordinator` 创建 Host/UI 进程参数。

### `memory.merge.merge_event_observations(memory, observations: Iterable[EventObservation], config, now_ms: int) -> None`
行为：把稳定后的 EventObservation 合并进 EventMemory 的任务表，处理 disabled、cooldown、dedupe、创建和确认帧。
算法：
1. 为本帧创建 `touched_task_ids`，防止同一帧多个 observation 复用同一个刚更新 task。
2. 对每个 observation 读取 event-specific config；若事件 disabled，节流记录 `observation skipped disabled` 并跳过。
3. 调用 `memory._completed_cooldown_info()` 检查 type cooldown 和位置 cooldown；命中时节流记录 `observation skipped cooldown` 并跳过。
4. 调用 `memory._find_matching_task()` 在 dedupe 半径内查找同类型、非 completed/ignored、且本帧未被触碰的 task。
5. 命中已有 task 时调用 `task.mark_seen(observation)`，更新位置、confidence、metadata 和 seen_count；必要时记录 `task seen`。
6. 未命中时创建 `EventTask(state=OBSERVED)`，分配 `memory._new_id()`，写入 priority、confidence、metadata，并追加到 `memory._tasks`。
7. 读取 `memory_confirm_frames`；seen_count 达标时 `task.mark_pending()`，并在状态变化时记录 `task confirmed pending`。
8. 仍处于 OBSERVED 时记录 `task waiting confirm`。
副作用：写入 `memory._tasks`、`memory._next_id`、task 状态和 event log。
失败行为：observation.global_pos 为空会在创建新 task 时触发索引错误；上游 `EventPositionStabilizer` 应只产出稳定全局坐标。
调用关系：called by `EventMemory.merge_observations()`；indirectly called by `EventCoordinator.observe()`。

### `memory.lookup.completed_cooldown_info(tasks: list[EventTask], observation: EventObservation, event_config: dict, now_ms: int, dedupe_radius: float) -> dict | None`
行为：判断 observation 是否应被已完成/忽略任务的冷却策略跳过。
算法：
1. 读取 `cooldown_ms` 和 `type_cooldown_ms`；observation 没有 global_pos 时直接返回 None。
2. 遍历同类型 task；completed task 使用 `completed_at_ms`，ignored task 缺失 completed_at 时使用 `last_seen_ms`。
3. 若 `type_cooldown_ms > 0` 且 elapsed 未超过，返回 `cooldown_kind="type"` 和剩余时间。
4. 若位置 cooldown 未启用或 elapsed 已超过 `cooldown_ms`，跳过该 task。
5. 读取 `cooldown_radius`，计算 task.global_pos 到 observation.global_pos 的距离。
6. 距离在半径内时返回 `cooldown_kind="position"`、距离、半径和剩余时间。
7. 所有任务都不命中时返回 None。
副作用：无。
失败行为：坐标不可索引时会在距离计算中抛错；上游应保证 EventTask/Observation 坐标契约。
调用关系：called by `EventMemory._completed_cooldown_info()` and `memory.merge.merge_event_observations()`。

### `memory.completion.complete_teleport_session(memory, entry_task: EventTask, exit_pos: tuple[int, int] | None, now_ms: int, config, exit_task_id: str | None = None, exit_player_pos: tuple[int, int] | None = None) -> tuple[EventTask, EventTask | None]`
行为：完成一次传送会话，把入口传送门和出口附近任务一起标记 completed，避免双门来回触发。
算法：
1. 读取 entry task 对应 event config，并生成 `teleport:{entry_id}:{now_ms}` session id。
2. 优先用显式 `exit_task_id` 找 exit task；没有则按 `exit_pos` 和 `exit_complete_radius/dedupe_radius` 查找同类型最近任务。
3. 标准化 `exit_player_pos` 和 `exit_pos`，并把 session id、role=entry、exit player pos 写入 entry metadata。
4. 标记 entry task completed。
5. 若有 normalized exit pos 但未找到 exit task，创建 synthetic exit task，confidence=1.0，metadata 标记 synthetic 和 complete reason。
6. 若有 exit task，更新 last_seen/global_pos/session metadata/role=exit/complete reason，并标记 completed。
7. 对 entry 和 exit 各调用 `memory.suppress_nearby_pending()`，把附近 active tasks 标记 ignored。
8. 记录 `teleport session completed`，返回 entry 和 exit task。
副作用：写入 `memory._tasks`、entry/exit metadata、状态和日志。
失败行为：config 缺少 event() 时按空配置降级；exit_pos 缺失且找不到 exit task 时只完成 entry。
调用关系：called by `EventMemory.complete_teleport_session()`；indirectly called by `EventRunner.update()` when handler returns COMPLETE with `completion_kind="teleport"`。

### `memory.completion.mark_failed(memory, task: EventTask, now_ms: int, config) -> None`
行为：应用 event handler FAIL 结果，按 retry limit 决定重试或忽略。
算法：
1. 调用 `task.mark_failed(now_ms)`，写入 failed_at_ms。
2. 从 event config 读取 `retry_limit`。
3. 若 `task.attempts >= retry_limit`，把 last_seen/completed_at 设为 now，调用 `task.mark_ignored()`，记录 `task failed ignored`。
4. 否则把 task.state 设回 PENDING，记录 `task failed retry`。
副作用：写入 task 状态、时间戳和 event log。
失败行为：config 缺少 event() 时 retry_limit 视为 0，失败会直接 ignored。
调用关系：called by `EventMemory.mark_failed()`；indirectly called by `EventRunner.update()` when handler returns FAIL。

### `minimap_feature_matcher.portal_blue_mask(image: np.ndarray, *, hue_min: int = 82, hue_max: int = 136, sat_min: int = 55, val_min: int = 95) -> np.ndarray`
行为：从 raw minimap 或模板图中提取传送门蓝/青本体像素，输出 0/255 二值 mask。
算法：
1. 灰度图先转 BGR，彩色图取前三通道。
2. BGR 转 HSV。
3. 按 hue 范围构造颜色 mask，支持 hue 区间跨 0 的情况。
4. 叠加饱和度和亮度下限，输出 uint8 二值图。
副作用：无。
失败行为：输入为空会由 OpenCV 抛出异常，调用方负责不传空帧。

### `minimap_feature_matcher.match_portal_features(frame: np.ndarray, templates: list[PortalFeatureTemplate], scales: list[float], *, top_k: int, threshold: float, hue_min: int = 82, hue_max: int = 136, sat_min: int = 55, val_min: int = 95, min_blue_pixels: int = 36, max_blue_pixels: int = 420) -> list[PortalFeatureHit]`
行为：用传送门蓝色本体特征做多尺度匹配，避免整块模板把背景/墙体当成识别依据。
算法：
1. 调用 `portal_blue_mask()` 从 raw frame 提取二值蓝色特征图。
2. 对每个模板蓝色特征和每个 scale 做最近邻缩放。
3. 用 `cv2.matchTemplate(..., TM_CCOEFF_NORMED)` 在二值特征图上匹配，并清理 NaN/Inf 响应。
4. 以 `threshold - 0.18` 收集候选，再对候选窗口统计蓝色像素数量，过滤过少或过多的蓝色区域。
5. 计算 `density_score`，衡量候选蓝色像素数量与模板蓝色像素数量是否接近。
6. 组合 `score = mask_score * 0.86 + density_score * 0.14`，低于阈值的候选丢弃。
7. 调用 `merge_feature_hits()` 按中心距离去重并返回最高分候选。
副作用：无。
失败行为：无模板或空帧返回空列表；后续 detector 会回退到整块模板兜底。

### `minimap_shape_color.masks.portal_blue_mask(image: np.ndarray, *, hue_min: int = 82, hue_max: int = 136, sat_min: int = 55, val_min: int = 95) -> np.ndarray`
行为：从 raw minimap 或模板图中提取传送门蓝/青核心像素，输出 0/255 二值 mask。
算法：
1. 将灰度输入转 BGR，彩色输入取前三通道。
2. BGR 转 HSV。
3. 按 hue 区间、饱和度下限和亮度下限构造蓝/青核心 mask，支持 hue 区间跨 0。
4. 返回 `uint8` 二值图。
副作用：无。
失败行为：空输入由 OpenCV 抛出异常，调用方负责过滤。
调用关系：called by `minimap_shape_color.pipeline.match_portal_shape_color()` and `minimap_shape_color.templates.prepare_shape_color_template()`。

### `minimap_shape_color.masks.portal_outer_mask(image: np.ndarray, *, sat_max: int = 115, val_min: int = 105, blue_mask: np.ndarray | None = None) -> np.ndarray`
行为：提取传送门图标白/灰外环像素，用于把“只有蓝色相似”的假候选排除。
算法：
1. 将输入转 HSV。
2. 选取低饱和、高亮度像素作为白/灰外环候选。
3. 如果传入 `blue_mask`，从外环候选中排除蓝色核心像素。
4. 返回 `uint8` 二值图。
副作用：无。
失败行为：空输入由 OpenCV 抛出异常。
调用关系：called by `minimap_shape_color.pipeline.match_portal_shape_color()` and `minimap_shape_color.templates.prepare_shape_color_template()`。

### `minimap_shape_color.pipeline.match_portal_shape_color(frame: np.ndarray, templates: list[TemplateSpec], scales: list[float], *, top_k: int, params: PortalShapeColorParams | None = None, collect_threshold: float | None = None) -> tuple[list[PortalShapeColorHit], PortalShapeColorDebug]`
行为：探针专用的传送门小地图联合匹配入口，同时验证蓝色核心、白/灰外环、整体形状、边缘和 masked HSV 颜色相似度。
算法：
1. 从 raw frame 生成 `frame_blue`、`frame_outer`、`frame_shape=blue|outer` 和 Canny 边缘图。
2. 对每个模板和每个 scale，生成对应的蓝色 mask、外环 mask、组合 shape mask、edge mask 和缩放模板图。
3. 分别计算 blue/outer/shape/edge mask 的 `TM_CCORR_NORMED` 响应，以及基于 shape mask 的 BGR masked color response。
4. 将候选响应按 `blue*0.30 + outer*0.24 + shape*0.24 + edge*0.12 + color*0.10` 合成，先以 `threshold - 0.22` 收集宽松候选。
5. 对每个候选窗口计算 blue、outer、shape、edge 的 F1-like score 和 masked HSV color score。
6. 用 `blue*0.31 + outer*0.25 + shape*0.25 + edge*0.11 + color*0.08` 得到最终 score。
7. 依次应用门禁：总分、blue shape、outer shape、combined shape、blue 像素下限/上限、outer 像素下限；失败原因写入 `reject_reasons`。
8. 调用 `merge_shape_color_hits()` 合并重复候选，合并时优先保留 accepted，再按分数排序。
9. 返回候选列表和调试 mask，供 probe 保存可视化图片。
副作用：无；调用方保存 debug 图片。
失败行为：无有效模板特征时跳过对应模板；OpenCV masked color response 不支持时回退为空响应，不中断探针。
调用关系：called by `PortalMinimapDetector._detect_shape_color_hits()` and `utils/event_icon_probe.py`。

### `minimap_shape_color.scoring.evaluate_shape_color_candidate(frame: np.ndarray, frame_blue: np.ndarray, frame_outer: np.ndarray, frame_shape: np.ndarray, frame_edges: np.ndarray, prepared: PreparedShapeColorTemplate, top_left: tuple[int, int], response_score: float, params: PortalShapeColorParams) -> PortalShapeColorHit`
行为：对单个 response peak 做精评分，并给出 accepted/reject_reasons。
算法：
1. 按 prepared template 尺寸从 frame blue/outer/shape/edge mask 和原始 frame 中裁剪候选窗口。
2. 分别用 `f1_score()` 计算 blue、outer、combined shape 和 edge 的 F1-like 分数。
3. 用 `patch_color_score()` 在 shape mask 内计算 HSV 平均距离，并转换成 0-1 颜色相似度。
4. 用 `blue*0.31 + outer*0.25 + shape*0.25 + edge*0.11 + color*0.08` 计算 base score。
5. 若 outer、edge、color 同时超过 signature 阈值，则计算 signature score，并用 `max(base_score, signature_score)` 作为最终分。
6. 依次追加 reject reasons：`score`、`blue_shape`、`outer_shape`、`combined_shape`、`blue_pixels_low`、`blue_pixels_high`、`outer_pixels_low`。
7. 返回 `PortalShapeColorHit`，保留各分项、像素计数、模板信息和 accepted 标记。
副作用：无。
失败行为：候选窗口尺寸不匹配时分数会降为 0；调用方继续保留 rejected 候选供 debug。
调用关系：called by `minimap_shape_color.pipeline.match_portal_shape_color()`。

### `minimap_shape_color.pipeline.merge_shape_color_hits(hits: list[PortalShapeColorHit], top_k: int, center_radius: float = 12.0) -> list[PortalShapeColorHit]`
行为：把多个模板/尺度产生的传送门候选按中心距离去重。
算法：
1. 按 `(accepted, score)` 降序遍历候选，保证通过门禁的候选不会被同位置高分 rejected 候选挤掉。
2. 对每个候选，计算其中心与已保留候选中心的距离。
3. 距离小于动态半径时视为同一图标，只保留先进入的候选。
4. 保留数量达到 `top_k` 后停止。
副作用：无。
失败行为：空输入返回空列表。
调用关系：called by `match_portal_shape_color()` and probe summary flow。

### `PortalMinimapDetector.detect(self, tick, config) -> list[EventDetection]`
行为：传送门小地图事件识别入口，按 `detector_mode` 在 template、feature、feature_then_template、shape_color 四种算法之间选择。
算法：
1. 将外部 config 规范化为 `PortalEventConfig`，并按 HSV feature 参数刷新模板蓝色特征。
2. raw minimap frame 为空或模板缺失时节流记录 skipped 并返回空。
3. `_detector_mode()` 读取 `detector_mode`；值非法时按旧 `feature_detector_enabled` 映射为 `feature_then_template` 或 `template`。
4. `template` 模式直接调用 `match_templates()`。
5. `feature` 模式只调用 `_detect_feature_hits()`。
6. `feature_then_template` 模式先调用 `_detect_feature_hits()`，无命中时调用 `match_templates()` 兜底。
7. `shape_color` 模式调用 `_detect_shape_color_hits()`；该函数只返回 accepted shape+color 候选，并在所有候选都被拒绝时记录 `portal minimap shape-color rejected`。
8. 全部模式无命中时，节流记录 `portal minimap no hits`，包含当前模式、raw frame 蓝色特征像素数量、feature 阈值和 shape 外环阈值。
9. 对候选按 `max_candidates` 截断前，逐个调用 `portal_color_check()` 做最终蓝色比例过滤。
10. 通过 `minimap_nms_radius` 检查 accepted hit 与已输出 detection 的小地图局部中心距离；近距离重复 hit 被跳过，避免同一图标因不同模板/尺度进入两个定位簇。
11. 为每个 accepted hit 输出 local-only `EventDetection`，metadata 记录 detector source、template、mask/density/shape score/blue pixel 等诊断字段。
12. 节流记录 `portal minimap hits`，包含 mode、source 和最佳候选各类分数。
副作用：更新 detector 当前 config、feature template cache 和事件日志。
失败行为：未命中返回空列表；不会直接创建全局事件坐标。

### `MotionController._calculate_target_screen_position(self, player_global_pos: tuple, target_global_pos: tuple) -> tuple[int, int] | None`
行为：把地图全局方向映射到人物屏幕中心附近的真实点击点。
算法：
1. 调用 `calculate_movement_click()`，传入玩家/目标地图坐标、屏幕中心、移动比例和 min/max 半径。
2. helper 计算 map delta、map distance、raw radius、clamped radius、direction 和 screen_pos。
3. 将 helper 返回的 `click_info` 写入 `self.last_click_info`。
4. 返回 helper 的 `screen_pos`；zero delta 时为 `None`。
副作用：更新 `self.last_click_info`。
失败行为：目标距离为 0 时不返回点击点。
调用关系：called by `MotionController.move_to_map_target()`；间接 called by `NavigationModeWidget.navigation_loop()`。

### `calculate_movement_click(*, player_global_pos: tuple, target_global_pos: tuple, game_screen_center: tuple, movement_scale_factor: float, movement_min_click_radius: int, movement_max_click_radius: int) -> ClickMappingResult`
行为：纯计算普通移动点击点和诊断字段。
算法：
1. 计算 `delta_map = target_global_pos - player_global_pos`。
2. 用 `math.hypot` 得到地图距离；若距离接近 0，返回 `screen_pos=None` 和 zero-distance click_info。
3. 计算 `raw_screen_radius = map_distance * movement_scale_factor`。
4. 将半径夹到 `[movement_min_click_radius, movement_max_click_radius]`。
5. 将地图方向归一化为单位向量。
6. 屏幕点击点等于 `game_screen_center + direction * screen_radius`，四舍五入为整数。
7. 返回 `ClickMappingResult(screen_pos, click_info)`。
副作用：无。
失败行为：目标距离为 0 时返回 `screen_pos=None`。
调用关系：called by `MotionController._calculate_target_screen_position()`。

### `calculate_mapped_target_click(*, player_global_pos: tuple, target_global_pos: tuple, game_screen_center: tuple, movement_scale_factor: float, movement_precision_click_max_radius: int, reason: str) -> ClickMappingResult`
行为：纯计算近目标/事件点强制点击位置，不应用普通移动最小半径。
算法：
1. 计算玩家到目标的地图 delta 和距离。
2. 距离大于 0 时归一化方向；距离接近 0 时方向为 `(0, 0)`。
3. 计算 `raw_screen_radius = map_distance * movement_scale_factor`。
4. 将半径夹到 `[0, movement_precision_click_max_radius]`。
5. 投影到 `game_screen_center + direction * screen_radius`。
6. 返回包含 `mapped_target_click=True`、`precision_radius_cap` 和 `reason` 的 click_info。
副作用：无。
失败行为：目标与玩家重合时返回屏幕中心，不抛异常。
调用关系：called by `MotionController._calculate_mapped_target_screen_position()`。

### `MotionController._apply_bottom_click_guard(self, screen_pos: tuple[int, int], driver=None)`
行为：防止自动导航点击落入游戏底部 UI 区域。
算法：
1. 从 `InputDriver.screen_height` 或 `pydirectinput.size()` 获取屏幕高度。
2. 调用 `apply_bottom_click_guard()`，传入 screen_pos、game_screen_center、screen_height、禁点高度和 margin。
3. 返回 helper 计算后的点击点和 `bottom_guard` 诊断信息。
副作用：无直接鼠标副作用；调用方把结果写入 `last_click_info`。
失败行为：无法获取屏幕高度时保持原点并记录 `reason=no_screen_height`。
调用关系：called by `MotionController._execute_click()`。

### `apply_bottom_click_guard(*, screen_pos: tuple[int, int], game_screen_center: tuple | None, screen_height: int | None, bottom_click_guard_pixels: int, bottom_click_guard_margin: int) -> tuple[tuple[int, int], dict]`
行为：纯计算底部 UI 禁点投影。
算法：
1. 若 `bottom_click_guard_pixels <= 0` 或未校准 `game_screen_center`，直接返回原点击点。
2. 若没有 `screen_height`，保持原点并记录 `reason=no_screen_height`。
3. 计算禁点区顶部 `forbidden_top = screen_height - bottom_click_guard_pixels`，安全线 `safe_y = forbidden_top - bottom_click_guard_margin`。
4. 若目标 `y <= safe_y`，不调整。
5. 若目标不在人物中心下方，不调整。
6. 沿 `game_screen_center -> screen_pos` 线段按比例缩短到 `safe_y`。
7. 返回调整后的点击点和 guard 诊断信息。
副作用：无。
失败行为：无法获取屏幕高度时保持原点。
调用关系：called by `MotionController._apply_bottom_click_guard()`。

### `MotionController.press_key(self, key: str, reason: str = "event_key")`
行为：为事件 handler 返回的 `PRESS_KEY` 动作发送键盘输入。
算法：
1. 检查 `control_enabled`，未启用时打印跳过并返回 `None`。
2. 将 key 转为小写字符串并去掉空白。
3. 空 key 直接跳过，避免向输入后端发送无效按键。
4. 调用 `pydirectinput.press(normalized_key)` 发送按键。
5. 返回包含 key/reason 的诊断 dict。
副作用：向当前游戏/前台窗口发送键盘输入。
失败行为：未开启控制或 key 为空时不执行输入；`pydirectinput.press()` 异常不在本函数吞掉。
调用关系：called by `NavigationRuntimeFrameLoop._execute_navigation_intent()` when consuming a `PRESS_KEY` intent.

### `NavigationModeWidget._update_game_view_rect(self, player_pos)`
行为：在地图视图中绘制橙色真实主画面范围框。
算法：
1. 校验 `game_view_rect_item`、`player_pos`、`nav_core`、`nav_config` 是否存在。
2. 读取 `nav_config.game_view_map_size`，小于等于 0 时隐藏橙色框。
3. 用 `nav_core.crop_offset` 将全局地图坐标转换为当前场景坐标。
4. 以玩家位置为中心，绘制边长为 `game_view_map_size` 的正方形。
副作用：更新 QGraphicsRectItem。
调用关系：called by `NavigationModeWidget.navigation_loop()`。

### `NavigationModeWidget._refresh_game_view_rect_from_known_position(self)`
行为：参数变化或保存后，在没有等待下一帧导航循环的情况下刷新橙色真实可见框。
算法：
1. 校验 `nav_core` 是否存在。
2. 按优先级选择 `nav_core.current_pos`、`nav_core.last_good_pos`、`nav_core.drawing_saved_pos`。
3. 找到可用位置后调用 `_update_game_view_rect()`。
副作用：立即更新 QGraphicsRectItem。
调用关系：called by `_on_parameter_changed()` and `_save_nav_config()`。

### `NavigationModeWidget._render_event_overlay(self)`
行为：在导航地图上绘制已识别事件任务 marker。
算法：
1. 调用 `render_event_overlay(scene, nav_core, event_coordinator, event_overlay_items)`。
2. helper 若 scene/nav_core/coordinator 任一不可用，会清空旧事件 marker 后返回空列表。
3. helper 从 `EventCoordinator.overlays()` 读取当前启用事件的 overlay 模型。
4. helper 用 `nav_core.crop_offset` 将全局地图坐标转换为当前裁剪场景坐标。
5. helper 按 overlay 颜色绘制圆点；`running` 状态半径更大，并在圆点旁绘制事件名称和状态文本。
副作用：清空并重建 `event_overlay_items` 中的 QGraphicsItem。
失败行为：坐标为空或无法映射时跳过该 marker。
调用关系：called by `navigation_loop()` and `_render_route_overlay()`。

### `toggle_owned_dialog(dialog: QWidget | None, owner: QWidget | None = None) -> bool`
行为：导航页 owned dialog 的切换判定；已显示且激活时通知调用方隐藏，否则显示并前置。
算法：
1. `dialog is None` 时直接返回 `False`，调用方不需要隐藏。
2. 若 `dialog.isVisible()` 且 `dialog.isActiveWindow()` 同时为真，返回 `True`，保持旧“重复点击当前弹窗按钮则隐藏”的语义。
3. 其他情况调用 `show_owned_dialog(dialog, owner)`，负责显示、恢复最小化和前置。
4. 返回 `False`，表示调用方不应再 hide。
副作用：通常会间接显示和激活 Qt dialog。
失败行为：空 dialog 静默降级；真实 Qt 显示/激活失败由 Qt 平台层处理。
调用关系：called by `NavigationModeWidget._toggle_owned_dialog()`。

### `show_owned_dialog(dialog: QWidget | None, owner: QWidget | None = None) -> None`
行为：显示导航页持有的 child dialog，并尽量放到主窗口附近、恢复最小化、前置和激活。
算法：
1. `dialog is None` 时直接返回。
2. 调用 `_restore_unminimized()`；若 dialog 当前最小化，移除 `Qt.WindowMinimized` 状态。
3. 若传入 `owner` 且 dialog 尚未可见，读取 `owner.frameGeometry()`，把 dialog 移动到 owner 左上角偏移 `(80, 80)` 的位置。
4. 调用 `dialog.show()`。
5. 再次调用 `_restore_unminimized()`，覆盖部分平台 show 后仍保留 minimized state 的情况。
6. 顺序调用 `raise_()`、`activateWindow()`、`QApplication.setActiveWindow(dialog)`。
副作用：修改 Qt dialog 的位置、窗口状态、可见性和 active window。
失败行为：空 dialog 静默降级；不同 Qt 平台对 raise/activate 的实际表现可能不同，但调用顺序保持旧实现。
调用关系：called by `toggle_owned_dialog()` and `NavigationModeWidget._show_owned_dialog()`。

### `NavigationCore.localize_result(self, minimap_img, player_pos=None) -> LocalizationResult`
行为：以兼容方式把一次既有最小地图定位调用转换为 core-owned typed result。
算法：
1. 调用 `self.localize(minimap_img, player_pos=player_pos)` 一次，完整保留历史 F2F、模板匹配、失败分支和 state mutation。
2. 读取该调用已写入的 `self.last_frame_registration`。
3. 调用 `LocalizationResult.from_legacy_tuple(result, registration=...)`，复制全局位置/置信度以及 registration 的 source、validity、metadata。
4. 返回 `GLOBAL_MAP` 坐标空间的结果；未定位时 position 为 `None`，而 `as_legacy_tuple()` 仍可取回原三元组形状。
副作用：仅复用历史 `localize()` 的定位状态写入；自身不抓屏、不执行输入、不修改 GUI。
失败行为：历史 `localize()` 的异常继续向上传播；合法的历史失败三元组会变成 `position=None` 的结果而非异常。
调用关系：called by `capture_navigation_localization_tick()`；calls `NavigationCore.localize()`、`LocalizationResult.from_legacy_tuple()`。

### `capture_navigation_localization_tick(*, build_capture_geometry, screen_capture, nav_config, nav_core, tracker, previous_player_local_pos) -> NavigationFrameTick | None`
行为：执行导航循环开头的截图与定位输入段。
算法：
1. 校验 `nav_config` 存在且至少有 `monitor_logical_center` 或 `monitor_region`。
2. 调用 `build_capture_geometry()` 获取 `capture_rect` 和默认玩家局部坐标；无有效截图几何时返回 `None`。
3. 调用 `screen_capture.capture(left, top, width, height)` 抓取小地图帧；抓屏失败返回 `None`。
4. 调用 `resolve_player_local_position()`：区域截图模式从 player mask/tracker 得到局部坐标，失败回退上一帧或截图中心；中心点截图模式使用默认局部坐标。
5. 调用 `nav_core.localize_result(frame, player_pos=player_pos)`；该 facade 只调用一次历史 `localize()`，再快照 `FrameRegistration` provenance 为 core `LocalizationResult`。
6. 直接使用该 core 结果，不创建 GUI result DTO。
7. 返回 `NavigationFrameTick(capture_rect, default_player_pos, frame, player_pos, localization)`。
副作用：读取屏幕截图；`localize_result()` 内部调用的历史 `nav_core.localize()` 会更新定位核心内部状态。helper 本身不写 QWidget 字段。
失败行为：缺少导航配置、截图几何无效或抓屏失败时返回 `None`；定位异常向上传播，保持原导航循环行为。
调用关系：called by `NavigationRuntimeFrameLoop.run()` before event observation。

### `handle_relocalization_navigation_intent(intent, *, request_global_relocalization, log_event, show_relocalizing) -> bool`
行为：消费带 `metadata.force_relocalize` 的导航 intent，并阻止本帧继续执行移动/点击输入。
算法：
1. 读取 `intent.metadata.get("force_relocalize")`；若为假，返回 `False`，不触发任何回调。
2. 从 `intent.metadata["relocalize_reason"]` 读取重定位原因；缺失时使用旧默认 `"coordinate_recovery"`。
3. 调用 `request_global_relocalization(reason)`，通常是 `NavigationCore.request_global_relocalization()`，让下一帧定位走全图匹配。
4. 调用 `log_event("navigation forced global relocalization", reason=reason, score=..., player=..., task=...)`，保留旧事件日志字段。
5. 调用 `show_relocalizing()`，由调用方绑定到状态栏展示函数。
6. 返回 `True`，通知 `NavigationRuntimeFrameLoop.run()` 立即 `return`，避免执行 `_execute_navigation_intent()`。
副作用：触发全局重定位请求；写入事件运行日志；追加状态栏重新定位提示。
失败行为：intent 缺少 `metadata` 属性时抛出属性错误，开发期暴露；回调异常向上传播，保持旧内联行为。
调用关系：called by `consume_navigation_intent()` before input execution。

### `consume_navigation_intent(intent, *, now_ms: int, request_global_relocalization, log_event, show_relocalizing, execute_intent, is_manual_event_test_active, stop_manual_event_test, stop_navigation_tasks, disable_game_input_mode, reset_auto_navigation_button, show_arrived, show_failed) -> NavigationIntentConsumptionResult`
行为：按固定顺序消费一个导航 intent，并把“本帧是否被重定位短路”和“是否进入导航终态”返回给 widget。
算法：
1. 调用 `handle_relocalization_navigation_intent()`；若返回 `True`，返回 `NavigationIntentConsumptionResult(skip_remaining_frame=True)`，不执行输入、手动测试停止或终态处理。
2. 调用 `execute_intent(intent, now_ms)`，由调用方绑定到 `NavigationRuntimeFrameLoop._execute_navigation_intent()`，真实输入仍留在 input adapter。
3. 若 `intent.metadata["terminal"]` 为真且 `is_manual_event_test_active()` 为真，调用 `stop_manual_event_test(intent.message)`。
4. 调用 `handle_terminal_navigation_intent()` 处理 ARRIVED/FAILED，内部按旧顺序停止任务、关闭游戏输入模式、复位自动导航按钮和展示终态文案。
5. 返回 `NavigationIntentConsumptionResult(terminal_navigation=<terminal helper result>)`。
副作用：可能触发全局重定位请求、真实输入、手动事件测试停止、任务停止、窗口输入模式恢复、按钮复位和状态栏文案更新；具体副作用均由回调承担。
失败行为：intent 缺少 `metadata/type/message` 等字段时抛出属性错误，保持开发期显式失败；回调异常向上传播。
调用关系：called by `NavigationRuntimeFrameLoop.run()` after route overlay render。

### `update_debug_overlay(overlay, *, capture_rect: dict | None, nav_config, scale: tuple[float, float]) -> bool`
行为：把导航截图几何转换为屏幕 debug 幕布窗口的显示矩形，并执行隐藏或显示。
算法：
1. 若 `overlay is None`，直接返回 `False`。
2. 调用 `screen_overlay_geometry(capture_rect, nav_config, scale)`，把物理像素截图矩形转换为 Qt 逻辑像素矩形，并读取可选 anchor。
3. 若返回 rect 为空，调用 `overlay.hide_overlay()` 并返回 `False`。
4. 若 rect 有效，把 `left/top/width/height/anchor` 传给 `overlay.set_rect_and_show()`。
5. 返回 `True`，表示幕布已按有效几何显示。
副作用：可能调用 `OverlayWindow.hide_overlay()` 或 `OverlayWindow.set_rect_and_show()`，改变全屏透明幕布可见性和绘制矩形。
失败行为：空 overlay 静默降级；capture geometry 无效时隐藏幕布。
调用关系：called by `NavigationModeWidget._update_overlay_display()`。

### `load_navigation_map_settings(map_folder_path: str) -> NavigationMapSettings`
行为：读取当前地图目录的导航配置，并保留配置文件是否真实存在的标记。
算法：
1. 调用 `load_nav_config(map_folder_path)`。
2. 接收 `(nav_config, config_exists)`。
3. 构造不可变 `NavigationMapSettings(nav_config=nav_config, config_exists=config_exists)`。
4. 返回该 settings 对象，让 `NavigationModeWidget.load_map()` 决定是否弹缺配置 warning。
副作用：读取 `map_folder_path/config.json`；缺文件时由底层 config store 返回默认配置。
失败行为：JSON 解析或 IO 异常按 `load_nav_config()` 原行为传播，由 `NavigationMapLoadLifecycle.load_selected_map()` 外层 `except` 弹错误框。
调用关系：called by `prepare_navigation_map_load_session()`。

### `create_navigation_core(map_folder_path: str) -> NavigationCore`
行为：创建地图目录对应的导航定位核心实例。
算法：
1. 调用 `NavigationCore(map_folder_path)`。
2. 返回创建完成的 core 实例。
副作用：触发 `NavigationCore` 构造期地图包加载和定位状态初始化。
失败行为：地图包缺失或构造异常向上传播，由 `NavigationMapLoadLifecycle.load_selected_map()` 外层 `except` 弹错误框。
调用关系：called by `prepare_navigation_map_load_session()`。

### `prepare_navigation_map_load_session(*, source_file: str, map_name: str, scale: tuple[float, float]) -> NavigationMapLoadSession`
行为：准备 `NavigationModeWidget.load_map()` 前半段所需的纯地图会话数据。
算法：
1. 调用 `resolve_map_folder(source_file, map_name)` 得到 `map_data/<map_name>` 绝对路径。
2. 调用 `load_navigation_map_settings(map_folder_path)` 读取 `NavConfig` 和 `config_exists`。
3. 调用 `create_navigation_core(map_folder_path)` 构造 `NavigationCore`，加载地图包和定位状态。
4. 调用 `initial_capture_center_for_config(settings.nav_config, scale)`，把逻辑屏幕中心换算为物理坐标，并生成参数弹窗回填用 `physical_center`。
5. 返回不可变 `NavigationMapLoadSession(map_name, map_folder_path, nav_config, config_exists, nav_core, capture_center_physical, physical_center)`。
副作用：读取地图配置 JSON；构造 `NavigationCore` 时读取地图包。
失败行为：map folder/config/map_data 构造异常向上传播，由 `NavigationMapLoadLifecycle.load_selected_map()` 外层 `except` 统一显示加载失败。
调用关系：called by `NavigationMapLoadLifecycle.load_selected_map()` before config application and UI refresh。

### `NavigationMapLoadLifecycle.load_selected_map(self, map_name: str | None) -> bool`
行为：执行用户选择地图后的完整加载生命周期，并保持旧加载失败提示。
算法：
1. 若 `map_name` 为空或等于缺地图占位文案，返回 `False`，保持旧的静默返回。
2. 调用 `prepare_navigation_map_load_session(source_file, map_name, scale)`，其中 scale 来自 targets 注入的 `compute_scale()`。
3. 调用 `apply_loaded_session(session)` 执行加载后半段固定顺序。
4. 成功时返回 `True`。
5. 捕获加载链路异常，调用 `show_map_load_failed(parent, error)`，返回 `False`。
副作用：读取地图配置/地图包；成功时会触发 `apply_loaded_session()` 的 UI、route、event、render 副作用；失败时弹 Qt critical。
失败行为：异常被本方法捕获并转换为旧中文错误弹窗，不继续传播。
调用关系：called by `NavigationModeWidget.load_map()`。

### `NavigationMapLoadLifecycle.apply_loaded_session(self, session: NavigationMapLoadSession) -> None`
行为：接收准备好的 map session，按旧顺序执行地图加载后半段。
算法：
1. 调用 `set_map_session(session)`，由 widget 写入 `map_folder_path/nav_config/nav_core/_capture_center_physical`。
2. 若 `session.config_exists` 为假，调用 `warn_map_config_missing(parent)`。
3. 调用 `apply_config_to_runtime()`，复用 `NavigationConfigLifecycle.apply_to_runtime()`。
4. 若 `session.capture_center_physical` 存在，打印旧调试行。
5. 调用 `params_dialog.set_config_to_ui(session.nav_config)` 回填参数 UI；物理中心只用于 capture cache，不再作为 dialog 兼容参数传入。
6. 依次调用 `load_route_data()`、`initialize_event_system()`、`render_map()`、`show_last_exit_position()`、`render_route_overlay()`。
7. 调用 `apply_map_loaded_ui()` 启用开始/提示按钮、route panel，并写入加载成功状态栏。
副作用：写入 widget runtime 状态、可能弹缺配置 warning、应用 nav config 到 core/path/motion/task controller、读取 route/event 配置、重建 QGraphicsScene、绘制退出点/路线/事件 overlay、启用按钮和状态栏。
失败行为：本方法不捕获异常；由 `load_selected_map()` 统一转换为加载失败弹窗。
调用关系：called by `NavigationMapLoadLifecycle.load_selected_map()`；smoke 通过回调顺序验证。

### `populate_map_combo(combo, map_names: Iterable[str], missing_label: str) -> None`
行为：把地图名称列表写入地图选择下拉框，缺地图时写入占位提示。
算法：
1. 调用 `combo.clear()` 清空旧项。
2. 将 `map_names` 转成列表，避免迭代器被重复消费。
3. 若列表非空，调用 `combo.addItems(names)`。
4. 若列表为空，调用 `combo.addItem(missing_label)`。
副作用：重写 QComboBox 条目。
失败行为：控件缺少相关 Qt 方法时抛出属性错误，由调用方开发期暴露。
调用关系：called by `NavigationModeWidget.refresh_map_list()`。

### `apply_map_loaded_ui(*, start_button, hint_button, route_panel, status_label, map_name: str) -> None`
行为：地图加载成功后启用导航入口按钮和 route panel，并写入成功状态栏文案。
算法：
1. 调用 `start_button.setEnabled(True)`。
2. 调用 `hint_button.setEnabled(True)`。
3. 调用 `route_panel.set_buttons_enabled(True)`，继续复用 route panel controller 的批量启用规则。
4. 调用 `status_label.setText()`，写入旧中文文案 `地图 '<map_name>' 加载成功。请设置初始位置或直接开始导航。`。
副作用：写入按钮 enabled 状态和状态栏文本。
失败行为：控件缺少相关方法时抛出属性错误，由调用方开发期暴露。
调用关系：called by `NavigationMapLoadLifecycle.apply_loaded_session()` after map rendering and overlay refresh.

### `warn_map_config_missing(parent) -> None`
行为：当前地图缺少 `config.json` 时提示用户将使用默认参数继续加载。
算法：
1. 调用 `QMessageBox.warning(parent, "警告", "未找到 config.json，将使用默认参数。")`。
副作用：弹出 Qt 警告框。
失败行为：Qt 弹窗异常向上传播；调用方继续后续地图加载。
调用关系：called by `NavigationMapLoadLifecycle.apply_loaded_session()` when `NavigationMapSettings.config_exists` is false.

### `show_map_load_failed(parent, error: Exception) -> None`
行为：地图加载链路抛出异常时显示旧中文失败提示，并附带异常文本。
算法：
1. 将 `error` 转为字符串。
2. 调用 `QMessageBox.critical(parent, "错误", f"加载地图失败：{str(error)}")`。
副作用：弹出 Qt 错误框。
失败行为：Qt 弹窗异常向上传播；不吞掉或重试加载异常。
调用关系：called by `NavigationMapLoadLifecycle.load_selected_map()` exception branch.

### `warn_overlay_map_config_incomplete(parent) -> None`
行为：debug overlay 勾选时发现缺少监控中心/区域配置，弹出旧中文警告。
算法：
1. 调用 `QMessageBox.warning(parent, "警告", "地图配置不完整，无法显示幕布。")`。
副作用：弹出 Qt 警告框。
失败行为：Qt 弹窗异常向上传播；按钮 checked 复位仍由调用方负责。
调用关系：called by `NavigationModeWidget._toggle_overlay_display()` guard branch.

### `initial_capture_center_for_config(nav_config: NavConfig | None, scale: tuple[float, float]) -> tuple[tuple[int, int] | None, tuple[int, int]]`
行为：根据导航配置中的逻辑中心和 DPR scale，生成加载地图时要缓存的物理截图中心，以及参数弹窗回填用的物理中心。
算法：
1. 若 `nav_config` 为空或没有 `monitor_logical_center`，返回 `(None, (0, 0))`，保持旧 UI 回填缺省值。
2. 调用 `physical_center_from_logical(nav_config.monitor_logical_center, scale)`。
3. 将计算出的物理中心作为第一个返回值，用于 `_capture_center_physical` 缓存。
4. 将同一个物理中心作为第二个返回值；若计算结果为空则回退 `(0, 0)`。
副作用：无。
失败行为：逻辑中心格式不合法时由坐标解包/整数转换抛出异常，沿用旧直接计算行为。
调用关系：called by `prepare_navigation_map_load_session()`。

### `NavigationConfigLifecycle.apply_to_runtime(self) -> bool`
行为：把当前 `NavConfig` 应用到导航 runtime 对象。
算法：
1. 通过 targets 读取 `nav_core` 和 `nav_config`；缺任一对象时返回 `False`。
2. 调用 `reset_capture_center()` 清空物理截图中心缓存。
3. 调用 `apply_navigation_config_to_core()`，把 recognizer、draw_scale、导航障碍层、PathFinder、MotionController 和 NavigationTaskController 参数按旧规则写入 runtime。
4. 返回底层 apply helper 的 bool 结果。
副作用：可能修改 `nav_config.draw_scale`、`nav_core`、PathFinder、MotionController、NavigationTaskController 和 `_capture_center_physical`。
失败行为：底层 apply 过程异常向上传播，保持旧 wrapper 行为。
调用关系：called by `NavigationModeWidget._apply_config_to_core()` and `NavigationConfigLifecycle.save_current_map_config()`。

### `NavigationConfigLifecycle.configure_task_controller(self) -> None`
行为：只同步 NavigationTaskController/coordinate diagnostics/event approach 相关配置。
算法：
1. 从 targets 读取当前 `nav_config` 和 `nav_core`。
2. 调用 `configure_navigation_task_controller()` 写入 movement、coordinate diagnostics 和 event approach 参数。
副作用：修改 `NavigationTaskController` 及其 movement/diagnostics/event approach 子对象；可能写 `nav_core` 视觉诊断参数。
失败行为：底层配置异常向上传播。
调用关系：called by `NavigationModeWidget._configure_navigation_task_controller()` and `NavigationConfigLifecycle.handle_parameter_changed()`。

### `NavigationConfigLifecycle.handle_parameter_changed(self, new_config) -> bool`
行为：处理参数对话框实时变化，并保持“不保存文件但应用部分 runtime 参数”的旧行为。
算法：
1. 若当前没有 `nav_core`，返回 `False`，避免未加载地图时应用参数。
2. 调用 `set_nav_config(new_config)` 更新 widget 持有的 `nav_config`。
3. 调用 `reset_capture_center()` 清空物理中心缓存。
4. 调用 `update_overlay_display()` 刷新 debug overlay。
5. 调用 `apply_motion_controller_config()` 立即同步运动控制参数。
6. 调用 `configure_task_controller()` 同步导航任务控制器参数。
7. 调用 `refresh_game_view_rect_from_known_position()` 刷新橙色真实视野框。
8. 调用 `mark_nav_params_dirty(nav_status_label)` 显示“有未保存的修改”。
9. 返回 `True`。
副作用：更新内存配置、MotionController、NavigationTaskController、overlay、视野框和参数弹窗状态 label；不写 config 文件。
失败行为：回调或底层配置异常向上传播，与旧 `_on_parameter_changed()` 一致。
调用关系：called by `NavigationModeWidget._on_parameter_changed()`。

### `NavigationConfigLifecycle.save_current_map_config(self) -> bool`
行为：保存当前地图的导航配置，并按旧顺序应用配置和刷新 UI。
算法：
1. 读取 `map_folder_path`；为空时调用 `warn_nav_config_missing_map(parent)` 并返回 `False`。
2. 调用 `save_nav_config(map_folder_path, nav_config)` 合并写入地图 `config.json`。
3. 调用 `apply_to_runtime()` 应用完整配置。
4. 调用 `update_overlay_display()` 刷新 debug overlay。
5. 调用 `refresh_game_view_rect_from_known_position()` 刷新橙色真实视野框。
6. 调用 `show_nav_config_saved(parent, nav_status_label)` 展示保存成功。
7. 返回 `True`。
副作用：写 `map_data/<map>/config.json`；修改 runtime 配置、overlay/视野框和状态 label；可能弹成功信息框。
失败行为：写文件或应用异常被捕获，调用 `show_nav_config_save_failed(parent, nav_status_label, error)` 并返回 `False`。
调用关系：called by `NavigationModeWidget._save_nav_config()`。

### `NavigationConfigLifecycle.save_default_config(self) -> bool`
行为：把当前导航参数保存为项目默认配置。
算法：
1. 读取当前 `nav_config`；为空时调用 `warn_default_nav_config_missing(parent)` 并返回 `False`。
2. 调用 `save_default_nav_config(source_file, nav_config)` 合并写入项目根 `config.json`。
3. 调用 `show_default_nav_config_saved(parent, nav_status_label, path)` 展示成功路径。
4. 返回 `True`。
副作用：写项目根默认 `config.json`；更新状态 label 并弹成功信息框。
失败行为：写文件异常被捕获，调用 `show_default_nav_config_save_failed(parent, nav_status_label, error)` 并返回 `False`。
调用关系：called by `NavigationModeWidget._save_nav_default_config()`。

### `show_nav_config_saved(parent, status_label) -> None`
行为：当前地图导航参数保存并应用成功后，更新参数弹窗状态标签并提示用户。
算法：
1. 调用 `status_label.setText("参数已保存并应用")`。
2. 调用 `QMessageBox.information(parent, "成功", "参数已保存并成功应用到当前导航。")`。
副作用：写入 Qt label 文本并弹出信息框。
失败行为：Qt 弹窗异常向上传播；调用点位于保存成功分支末尾。
调用关系：called by `NavigationModeWidget._save_nav_config()` after save/apply/overlay refresh.

### `show_nav_config_save_failed(parent, status_label, error: Exception) -> None`
行为：当前地图导航参数保存失败后，显示错误并标记参数状态。
算法：
1. 调用 `QMessageBox.critical(parent, "保存失败", f"无法写入 config.json: {error}")`。
2. 调用 `status_label.setText("保存失败!")`。
副作用：弹出错误框并写入 Qt label 文本。
失败行为：Qt 弹窗异常向上传播；不吞掉原 error，只把 error 文本展示给用户。
调用关系：called by `NavigationModeWidget._save_nav_config()` exception branch.

### `warn_event_config_missing(parent) -> None`
行为：事件配置保存前发现尚未加载地图或没有事件配置时，弹出旧中文警告。
算法：
1. 调用 `QMessageBox.warning(parent, "事件管理", "未加载地图或事件配置。")`。
副作用：弹出 Qt 警告框。
失败行为：Qt 弹窗异常向上传播；调用方随后直接返回。
调用关系：called by `NavigationEventLifecycle.save_event_config()` guard branch.

### `show_event_config_saved(parent) -> None`
行为：事件配置写入成功后提示用户保存完成。
算法：
1. 调用 `QMessageBox.information(parent, "事件管理", "事件配置已保存。")`。
副作用：弹出 Qt 信息框。
失败行为：Qt 弹窗异常向上传播；调用点在 `_refresh_event_dialog()` 之后。
调用关系：called by `NavigationEventLifecycle.save_event_config()` success branch.

### `show_event_config_save_failed(parent) -> None`
行为：事件配置写入失败后提示用户 `event_config.json` 保存失败。
算法：
1. 调用 `QMessageBox.critical(parent, "事件管理", "保存 event_config.json 失败。")`。
副作用：弹出 Qt 错误框。
失败行为：Qt 弹窗异常向上传播；不重试保存。
调用关系：called by `NavigationEventLifecycle.save_event_config()` failure branch.

### `warn_event_system_missing(parent) -> None`
行为：事件系统尚未初始化时，弹出旧中文警告。
算法：
1. 调用 `QMessageBox.warning(parent, "事件管理", "请先加载地图并初始化事件系统。")`。
副作用：弹出 Qt 警告框。
失败行为：Qt 弹窗异常向上传播；调用方负责 reset 按钮或直接返回。
调用关系：called by `NavigationEventLifecycle.reset_event_state()` and `NavigationEventLifecycle.run_manual_event_test()`.

### `warn_manual_event_test_missing_screen_center(parent) -> None`
行为：启动手工事件流程前发现未校准屏幕中心时弹出警告。
算法：
1. 调用 `QMessageBox.warning(parent, "事件管理", "请先校准屏幕中心。")`。
副作用：弹出 Qt 警告框。
失败行为：Qt 弹窗异常向上传播；调用方已先 reset 手动测试按钮。
调用关系：called by `NavigationEventLifecycle.run_manual_event_test()` guard branch.

### `show_manual_event_test_started(status_label) -> None`
行为：手工事件流程正式启动后写入状态栏提示。
算法：
1. 调用 `status_label.setText("事件流程测试已启动：使用正式事件流程执行")`。
副作用：写入 Qt 状态标签文本。
失败行为：status label 缺少 `setText()` 时抛出属性错误，由开发期暴露。
调用关系：called by `NavigationModeWidget._set_manual_event_test_active(True)`.

### `show_manual_event_test_stopped(status_label) -> None`
行为：手工事件流程停止后写入状态栏提示。
算法：
1. 调用 `status_label.setText("事件流程测试已停止")`。
副作用：写入 Qt 状态标签文本。
失败行为：status label 缺少 `setText()` 时抛出属性错误，由开发期暴露。
调用关系：called by `NavigationModeWidget._set_manual_event_test_active(False)`.

### `warn_auto_navigation_unavailable(parent, message: str) -> None`
行为：自动导航启动 guard 未通过时，用调用方传入的旧原因文案提示用户。
算法：
1. 调用 `QMessageBox.warning(parent, "警告", message)`。
副作用：弹出 Qt 警告框。
失败行为：Qt 弹窗异常向上传播；调用方已先复位自动导航按钮 checked 状态。
调用关系：called by `NavigationRuntimeCommandLifecycle._start_auto_navigation()` guard branch.

### `warn_auto_navigation_invalid_route(parent) -> None`
行为：路线数据无法启动 `NavigationTaskController` 时提示用户。
算法：
1. 调用 `QMessageBox.warning(parent, "警告", "路线数据无效，无法启动自动导航")`。
副作用：弹出 Qt 警告框。
失败行为：Qt 弹窗异常向上传播；调用方已先复位自动导航按钮 checked 状态。
调用关系：called by `NavigationRuntimeCommandLifecycle._start_auto_navigation()` invalid-route branch.

### `show_auto_navigation_started(status_label) -> None`
行为：自动导航成功进入运行态后写入状态栏提示。
算法：
1. 调用 `status_label.setText("自动导航已启动，等待稳定定位")`。
副作用：写入 Qt 状态标签文本。
失败行为：status label 缺少 `setText()` 时抛出属性错误，由开发期暴露。
调用关系：called by `NavigationRuntimeCommandLifecycle._start_auto_navigation()` success branch.

### `show_auto_navigation_stopped(status_label) -> None`
行为：自动导航停止后写入状态栏提示。
算法：
1. 调用 `status_label.setText("自动导航已停止")`。
副作用：写入 Qt 状态标签文本。
失败行为：status label 缺少 `setText()` 时抛出属性错误，由开发期暴露。
调用关系：called by `NavigationRuntimeCommandLifecycle._stop_auto_navigation()` stop branch.

### `warn_navigation_missing_screen_center(parent) -> None`
行为：开始导航前发现尚未校准屏幕中心时弹出旧中文警告。
算法：
1. 调用 `QMessageBox.warning(parent, "警告", "请先点击'校准屏幕中心'进行设置！")`。
副作用：弹出 Qt 警告框。
失败行为：Qt 弹窗异常向上传播；调用方随后复位开始按钮 checked 状态。
调用关系：called by `NavigationRuntimeCommandLifecycle.start_navigation()` guard branch.

### `warn_navigation_map_config_incomplete(parent) -> None`
行为：开始导航前发现监控中心或监控大小缺失时弹出旧中文警告。
算法：
1. 调用 `QMessageBox.warning(parent, "警告", "地图配置不完整，缺少监控中心或大小！")`。
副作用：弹出 Qt 警告框。
失败行为：Qt 弹窗异常向上传播；调用方随后复位开始按钮 checked 状态。
调用关系：called by `NavigationRuntimeCommandLifecycle.start_navigation()` guard branch.

### `show_navigation_started(status_label) -> None`
行为：导航 timer 启动后写入状态栏开始提示。
算法：
1. 调用 `status_label.setText("导航已开始...")`。
副作用：写入 Qt 状态标签文本。
失败行为：status label 缺少 `setText()` 时抛出属性错误，由开发期暴露。
调用关系：called by `NavigationRuntimeCommandLifecycle.start_navigation()` after `nav_timer.start()`.

### `show_navigation_paused(status_label) -> None`
行为：导航 runtime 停止后写入状态栏暂停提示。
算法：
1. 调用 `status_label.setText("导航暂停")`。
副作用：写入 Qt 状态标签文本。
失败行为：status label 缺少 `setText()` 时抛出属性错误，由开发期暴露。
调用关系：called by `NavigationRuntimeCommandLifecycle.stop_runtime()`.

### `show_route_command_status(status_label, status_text: str | None) -> None`
行为：把 route editor/panel controller 产出的命令状态文案写入状态栏。
算法：
1. 若 `status_text` 为空，直接返回，避免覆盖当前状态。
2. 调用 `status_label.setText(status_text)`。
副作用：可能写入 Qt 状态标签文本。
失败行为：status label 缺少 `setText()` 时抛出属性错误，由开发期暴露。
调用关系：called by `NavigationRouteLifecycle._apply_route_command_result()` and `NavigationMapClickLifecycle.handle_map_click()`.

### `warn_route_save_failed(parent) -> None`
行为：路线保存失败后弹出旧中文 warning。
算法：
1. 调用 `QMessageBox.warning(parent, "警告", "保存路线失败")`。
副作用：弹出 Qt 警告框。
失败行为：Qt 弹窗异常向上传播；调用方不更新 route overlay。
调用关系：called by `NavigationRouteLifecycle.save_route()` failure branch.

### `NavigationRouteLifecycle.load_route_data(self) -> dict | None`
行为：加载当前地图 route 数据，并同步给导航任务控制器。
算法：
1. 读取 `get_map_folder_path()`；若为空，调用 `_sync_route_data(None)` 清空内存 route 和任务路线，返回 `None`。
2. 调用 `RouteEditor.load_route_data(map_folder_path, force_reload=True)` 从 `RouteManager` 缓存/route.json 读取路线。
3. 调用 `_sync_route_data(route_data)` 写回 `NavigationModeWidget.route_data` 并加载 main route 到 `NavigationTaskController`。
4. 返回加载得到的 route_data。
副作用：写回导航页 route_data；调用 `NavigationTaskController.load_route()`。
失败行为：`RouteManager.load_route()` 异常向上传播，保持旧行为。
调用关系：called by `NavigationModeWidget.load_route_data()` and map load lifecycle.

### `NavigationRouteLifecycle.save_route(self) -> None`
行为：保存当前 route 并在成功后同步 route runtime 状态。
算法：
1. 调用 `RoutePanelController.save_route(map_folder_path)`，controller 负责委托 `RouteEditor.save_route()`。
2. 若 `result.saved is None`，说明未加载地图，直接返回。
3. 若 `result.saved` 为假，调用 `warn_route_save_failed(parent)`，不刷新 overlay。
4. 保存成功时调用 `_apply_route_command_result(result)`。
副作用：可能写入 route.json；可能写 route_data、task controller、overlay、状态栏；失败时弹 warning。
失败行为：保存异常由 `RoutePanelController/RouteEditor` 传播；保存返回失败时只弹 warning。
调用关系：called by `NavigationModeWidget.save_route()`; calls `RoutePanelController.save_route()` and `_apply_route_command_result()`.

### `NavigationRouteLifecycle.undo_guide_point(self) -> None` / `undo_required_point(self) -> None` / `clear_route(self) -> None`
行为：执行 route 撤销/清空命令，并统一同步结果。
算法：
1. 调用对应的 `RoutePanelController` 方法，得到 `RouteCommandResult`。
2. 调用 `_apply_route_command_result(result)`。
3. `_apply_route_command_result()` 若 route_data 为空则直接返回；否则同步 route_data、加载 main route、重绘 overlay，并写入状态栏文案。
副作用：可能修改 route.json；写回 route_data；调用 `NavigationTaskController.load_route()`；重绘 route overlay；写状态栏。
失败行为：未加载地图时返回空 result，不抛异常；底层 route manager 异常向上传播。
调用关系：called by `NavigationModeWidget.undo_guide_point()`、`undo_required_point()`、`clear_route()`.

### `warn_move_target_requires_localization(parent) -> None`
行为：用户点击移动目标但当前尚未完成定位时弹出旧中文 warning。
算法：
1. 调用 `QMessageBox.warning(parent, "警告", "请先完成定位后再点击移动目标。")`。
副作用：弹出 Qt 警告框。
失败行为：Qt 弹窗异常向上传播；调用方不调用 `MotionController`。
调用关系：called by `NavigationMapClickLifecycle.handle_map_click()` before manual move target.

### `show_move_target_set(status_label, pos) -> None`
行为：手动移动目标设置成功后，把 scene 坐标写入状态栏。
算法：
1. 调用 `pos.x()` 和 `pos.y()`。
2. 按旧格式保留 1 位小数：`移动目标: (<x>, <y>)`。
3. 调用 `status_label.setText(text)`。
副作用：写入 Qt 状态标签文本。
失败行为：pos 缺少 `x/y()` 或 status label 缺少 `setText()` 时抛出异常，由开发期暴露。
调用关系：called by `NavigationMapClickLifecycle.handle_map_click()` after `MotionController.move_to_map_target()`.

### `show_initial_hint_set(status_label, global_x: float, global_y: float) -> None`
行为：初始位置提示写入 `NavigationCore` 并刷新 marker 后，把全局坐标写入状态栏。
算法：
1. 将 `global_x/global_y` 转为 `int`，保持旧显示精度。
2. 格式化 `初始位置提示已设置：(<x>, <y>)。`。
3. 调用 `status_label.setText(text)`。
副作用：写入 Qt 状态标签文本。
失败行为：status label 缺少 `setText()` 时抛出属性错误，由开发期暴露。
调用关系：called by `NavigationMapClickLifecycle.set_initial_hint()`.

### `show_hint_mode_status(status_label, active: bool) -> None`
行为：hint mode 开启/取消时写入状态栏提示。
算法：
1. 若 `active` 为真，写入 `请在地图上点击您当前的大致位置...`。
2. 否则写入 `取消设置初始位置`。
3. 调用 `status_label.setText(text)`。
副作用：写入 Qt 状态标签文本。
失败行为：status label 缺少 `setText()` 时抛出属性错误，由开发期暴露。
调用关系：called by `NavigationMapClickLifecycle.toggle_hint_mode()`.

### `show_screen_center_calibrated(parent, screen_center) -> None`
行为：屏幕中心校准保存完成后弹出旧中文完成提示。
算法：
1. 调用 `QMessageBox.information(parent, "校准完成", f"屏幕中心已校准为：{screen_center}")`。
副作用：弹出 Qt 信息框。
失败行为：Qt 弹窗异常向上传播；调用点位于 `_save_nav_config()` 之后、selector close 之前，保持旧时机。
调用关系：called by `NavigationScreenCalibrationLifecycle.handle_screen_center_click()`.

### `NavigationScreenCalibrationLifecycle.start_screen_center_calibration(self) -> bool`
行为：启动屏幕中心校准选择器，并把 selector 引用同步回导航页兼容字段。
算法：
1. 调用 targets 注入的 `ScreenCenterCalibrationController.start(self.handle_screen_center_click)`。
2. controller 内部若已有可见 selector，则返回 `False` 并避免重复创建；否则创建 `CenterPointSelector`、连接 `point_selected`、全屏显示。
3. 无论是否新建 selector，都调用 `set_center_selector(controller.selector)`，保持旧 `NavigationModeWidget.center_selector` 字段可读。
4. 返回 controller 的启动结果。
副作用：可能创建并全屏显示 Qt selector；写回导航页 `center_selector` 兼容字段。
失败行为：selector 创建或 signal 连接异常向上传播。
调用关系：called by `NavigationModeWidget._calibrate_screen_center()`; calls `ScreenCenterCalibrationController.start()`.

### `NavigationScreenCalibrationLifecycle.handle_screen_center_click(self, x: int | float, y: int | float) -> tuple[int, int] | None`
行为：处理校准点击后的完整副作用链，保持旧“写配置 -> 刷 UI -> 保存 -> 完成提示 -> 关闭 selector”顺序。
算法：
1. 读取当前 `NavConfig`；若缺失，关闭 selector 并返回 `None`。
2. 调用 controller 的 `logical_to_physical(x, y)`，按当前 primary screen DPR 把逻辑坐标转换为物理像素。
3. 将转换结果写入 `nav_config.game_screen_center`。
4. 调用 `params_dialog.set_config_to_ui(nav_config)` 回填只读屏幕中心显示。
5. 调用 `update_overlay_display()`，让绿色监控框和橙色视野框按新屏幕中心刷新。
6. 调用 `save_nav_config()`，走 `NavigationConfigLifecycle.save_current_map_config()` 的当前地图配置 merge 保存和保存反馈。
7. 调用 `show_screen_center_calibrated(parent, screen_center)` 显示完成提示。
8. 调用 controller `close()` 关闭 selector。
副作用：修改内存中的 `NavConfig.game_screen_center`；写参数弹窗控件；可能写入当前地图 `config.json`；弹出 Qt 信息框；关闭 selector。
失败行为：`save_nav_config()` 自身捕获保存异常并展示失败反馈；坐标转换、UI 写入或弹窗异常向上传播。
调用关系：called by `NavigationModeWidget._handle_calibration_click()` and selector `point_selected`; calls `ScreenCenterCalibrationController.logical_to_physical()`、`NavigationConfigLifecycle.save_current_map_config()` wrapper、`show_screen_center_calibrated()`.

### `show_navigation_runtime_status(status_label, *, localized_pos, confidence: float, capture_rect: dict, intent=None, event_status: str = "") -> None`
行为：把当前帧定位、intent 和事件状态构造成基础状态栏文本并写入 label。
算法：
1. 调用 `build_navigation_status_text()`。
2. 传入 `localized_pos/confidence/capture_rect/intent/event_status`。
3. 调用 `status_label.setText(text)`。
副作用：写入 Qt 状态标签文本。
失败行为：`capture_rect` 缺少 `width/height` 或 status label 缺少 `setText()` 时抛出异常，保持旧显式失败。
调用关系：called by `NavigationRuntimeFrameLoop.run()` after marker/viewport refresh.

### `append_navigation_status_suffix(status_label, suffix: str | None) -> None`
行为：在当前状态栏文本末尾追加一个运行态后缀。
算法：
1. 若 `suffix` 为空，直接返回。
2. 调用 `status_label.text()` 读取当前文本。
3. 写入 `当前文本 | <suffix>`。
副作用：写入 Qt 状态标签文本。
失败行为：status label 缺少 `text/setText()` 时抛出异常，保持旧显式失败。
调用关系：called by `show_navigation_relocalizing()` and `NavigationRuntimeFrameLoop._execute_navigation_intent()`.

### `show_navigation_relocalizing(status_label) -> None`
行为：在当前帧状态栏后追加正在重新定位提示。
算法：
1. 调用 `append_navigation_status_suffix(status_label, "正在重新定位")`。
副作用：写入 Qt 状态标签文本。
失败行为：同 `append_navigation_status_suffix()`。
调用关系：called by `handle_relocalization_navigation_intent()` callback from `NavigationRuntimeFrameLoop.run()` force-relocalize branch.

### `show_navigation_arrived(status_label) -> None`
行为：导航终态为到达出口时覆盖状态栏文本。
算法：
1. 调用 `status_label.setText("已到达出口区域")`。
副作用：写入 Qt 状态标签文本。
失败行为：status label 缺少 `setText()` 时抛出异常。
调用关系：called by `NavigationRuntimeFrameLoop.run()` ARRIVED branch.

### `show_navigation_failed(status_label, message: str | None) -> None`
行为：导航终态失败时覆盖状态栏文本。
算法：
1. 若 `message` 非空，使用该消息。
2. 否则使用旧默认文案 `自动导航失败`。
3. 调用 `status_label.setText(text)`。
副作用：写入 Qt 状态标签文本。
失败行为：status label 缺少 `setText()` 时抛出异常。
调用关系：called by `NavigationRuntimeFrameLoop.run()` FAILED branch.

### `update_localization_view(*, scene, view, player_item, nav_core, localization, capture_rect, player_local_pos, update_monitor_rect, update_game_view_rect)`
行为：根据当前帧定位结果更新地图上的玩家 marker、绿色监控框、橙色视野框和视图中心。
算法：
1. 若 `localization.is_localized` 为真：
   1. 调用 `update_player_marker(scene, player_item, nav_core, localization.localized_pos)`，得到新的 `player_item` 和显示坐标。
   2. 调用 `update_monitor_rect(localization.localized_pos, capture_rect=capture_rect, player_local_pos=player_local_pos)`。
   3. 调用 `update_game_view_rect(localization.localized_pos)`。
   4. 调用 `view.centerOn(display_x, display_y)`。
   5. 返回新的 `player_item`。
2. 若未定位：
   1. 从 `nav_core.last_good_pos or nav_core.drawing_saved_pos` 取 fallback。
   2. fallback 存在时调用两个矩形更新回调。
   3. 调用 `hide_item(player_item)` 隐藏玩家 marker。
   4. 返回原 `player_item`。
副作用：更新 QGraphicsItem、QGraphicsView center，并通过回调更新监控框/视野框。
失败行为：scene/view/nav_core/localization 缺少必要属性时显式抛出异常；与原 widget 内联逻辑一致。
调用关系：called by `NavigationRuntimeFrameLoop.run()` after task update and before status write.

### `render_route_overlay(scene, nav_core, route_data, items: list, current_path=None, current_subgoal=None, current_required_index=None, current_guide_index=None, current_target_kind=None)`
行为：根据现有路线数据和自动导航运行态绘制出口、必经点、途经点、当前路径和子目标。
算法：
1. 清空传入的旧 route overlay items。
2. 从 `route_data["routes"]["main"]` 读取 `exit_region`、`required_points`、`guide_points`。
3. 使用 `global_to_scene()` 将全局坐标减去 `nav_core.crop_offset` 得到场景坐标。
4. 绘制出口橙色圆、必经点紫色/灰色 marker、途经点青色 `A1/A2/...` 辅助锚点；途经点不再按当前 target kind 加粗或标记完成。
5. 如传入 `current_path`，构造 `QPainterPath` 绘制黄色路径线。
6. 如传入 `current_subgoal`，绘制洋红色子目标点。
7. 返回新的 item 列表和 route path item。
副作用：向 QGraphicsScene 添加/移除 QGraphicsItem。
失败行为：scene/nav_core 不可用时由调用方早退；单点无法映射时跳过该点。
调用关系：called by `NavigationModeWidget._render_route_overlay()`。

### `render_event_overlay(scene, nav_core, event_coordinator, items: list) -> list`
行为：根据事件系统 overlay 模型绘制事件 marker。
算法：
1. scene/nav_core/event_coordinator 任一不可用时清空旧事件 items 并返回空列表。
2. 清空旧事件 items。
3. 遍历 `event_coordinator.overlays()`，读取每个 overlay 的 `global_pos/color/state/label`。
4. 调用 `global_to_scene()` 转换坐标。
5. 绘制事件圆点和文本 label，running 状态使用更大半径。
副作用：向 QGraphicsScene 添加/移除事件 QGraphicsItem。
失败行为：单个 overlay 坐标无法映射时跳过。
调用关系：called by `NavigationModeWidget._render_event_overlay()`。

### `EventManagerDialog._format_current_values(self, values: dict, schema: dict) -> str`
行为：按业务 definition 在通用 schema 中声明的显示提示构造当前配置摘要。
算法：1. 按 schema 顺序收集 `summary=True` 字段。2. 没有 summary 时退到 `compact=True` 字段。3. 两者都没有时退到前 8 个可编辑字段。4. 只格式化实际存在于 values 的键并以逗号连接。
副作用：无。
失败行为：缺字段静默跳过；非 dict schema 由调用点规范为空 dict。
调用关系：called by `_sync_selected_event_controls()` and `_update_event_summary()`；calls `editable_schema_items()` only for final fallback。

### `EventManagerDialog.refresh(self) -> None`
行为：执行完整刷新，重建事件选配表、参数面板和事件任务表。
算法：
1. 调用 `_refresh_events()` 重建完整事件选配表。
2. 调用 `_refresh_tasks()` 从 coordinator 读取当前任务列表。
3. 当 registry/config 不存在时禁用全局复选框并显示未加载状态。
4. 事件复选框变化通过 `config_changed` 把内存态配置交回导航模式。
5. 保存按钮只发出 `save_requested`，实际路径由导航模式写入当前地图目录。
副作用：重建 QTableWidget 行和状态文案。
失败行为：coordinator 查询异常时 `_current_tasks()` 降级为空列表。
调用关系：called by `EventManagerDialog.set_context()`、刷新按钮、配置勾选变化。

### `EventManagerDialog.refresh_tasks(self) -> None`
行为：只刷新事件任务表和状态摘要，不重建事件选配表、参数面板或按钮。
算法：
1. 调用 `_refresh_tasks()` 从 coordinator 读取当前任务列表。
2. 用现有任务行数据更新 ID、事件类型、状态、识别次数、置信度、地图坐标、尝试次数和最近识别时间。
3. 当 config 存在时更新底部状态摘要。
副作用：重写任务 QTableWidget 行和状态文案；不修改事件选配控件和参数控件。
失败行为：coordinator 查询异常时 `_current_tasks()` 降级为空列表。
调用关系：called by `NavigationModeWidget.navigation_loop()` while the event dialog is visible.

### `ManualEventTestController._sync_button(self) -> None`
行为：使手动事件测试按钮的文字和选中状态与 `active` 一致。
算法：
1. 若没有绑定按钮，直接返回，保留纯状态控制能力。
2. 当 `active=True` 时设置停止文案，否则设置启动文案。
3. 仅在控件 checked 值与 `active` 不一致时调用 `setChecked()`，避免无意义 UI 反复写入。
副作用：写入 Qt 按钮文本和 checked 状态。
失败行为：无绑定按钮时无 UI 副作用且不抛错。
调用关系：called by `__init__()`、`start()`、`stop()`、`reset_button()`。

### `NavigationEventLifecycle.save_event_config(self) -> bool`
行为：保存当前地图的事件配置，并保持旧成功/失败反馈。
算法：
1. 读取 `map_folder_path` 和 `event_config`。
2. 若任一为空，调用 `warn_event_config_missing(parent)` 并返回 `False`。
3. 调用 `save_event_config(map_folder_path, event_config)` 写入当前地图 `event_config.json`。
4. 成功时调用 `refresh_event_dialog()` 刷新事件窗口上下文，再调用 `show_event_config_saved(parent)`，返回 `True`。
5. 失败时调用 `show_event_config_save_failed(parent)`，返回 `False`。
副作用：可能写入 `map_data/<map>/event_config.json`、刷新事件窗口、弹出保存结果提示。
失败行为：底层返回 `False` 时只展示失败提示；缺少地图或配置时展示缺配置 warning。
调用关系：called by `NavigationModeWidget._save_event_config()` wrapper。

### `NavigationEventLifecycle.reset_event_state(self, now_ms: int) -> bool`
行为：重置当前 registry/config 覆盖的全部事件运行态和地图 overlay/dialog 展示。
算法：
1. 若没有 `event_coordinator`，调用 `warn_event_system_missing(parent)` 并返回 `False`。
2. 若手工事件测试 active，调用 `set_manual_event_test_active(False, reason="event state reset")`。
3. 合并 config 事件键与 registry definition 类型并排序。
4. 逐类调用 `event_coordinator.reset_event_type(event_type, now_ms=now_ms)`，累加 removed。
5. 清空 movement/event approach runtime，重绘 overlay，刷新 dialog。
6. 写通用 reset 日志并调用 `show_event_state_reset(status_label, removed_total)`。
副作用：修改 EventCoordinator 中已注册/配置事件状态、停止手工测试、重置 movement runtime、刷新 overlay/dialog 和状态栏。
失败行为：缺少 event coordinator 时只弹 warning 并返回 `False`。
调用关系：called by `NavigationModeWidget._reset_event_state()` wrapper。

### `NavigationEventLifecycle.run_manual_event_test(self) -> bool`
行为：响应事件管理窗口“测试事件流程/停止事件流程测试”命令。
算法：
1. 若手工事件测试已 active，调用 `set_manual_event_test_active(False, reason="button stop")`，返回 `False`。
2. 校验 event coordinator 和 nav core；缺失时 reset 按钮、弹事件系统缺失 warning、返回 `False`。
3. 校验 `NavConfig.game_screen_center`；缺失时 reset 按钮、弹屏幕中心缺失 warning、返回 `False`。
4. 若导航 timer 未运行，则设置开始按钮 checked，调用 `toggle_navigation()` 复用普通导航启动；启动失败时 reset 按钮并返回 `False`。
5. 调用 `set_manual_event_test_active(True, reason="button start")`，返回 `True`。
副作用：可能启动导航 timer、启用输入窗口模式和 motion control、启动 task controller、写事件日志和状态栏。
失败行为：任一前置条件失败会复位按钮并返回 `False`，不启动手动测试。
调用关系：called by `NavigationModeWidget._run_manual_event_test()` wrapper。

### `NavigationEventLifecycle.set_manual_event_test_active(self, active: bool, reason: str = "") -> None`
行为：实际切换通用手工事件测试运行态。
算法：
1. active 为真时，启动 `start_event_log_session("manual_event_test")`。
2. 从 route data 读取 `routes.main`，调用 `NavigationTaskController.load_route(main_route)` 和 `start()`。
3. 调用 `ManualEventTestController.start()` 同步按钮。
4. 打开游戏输入窗口模式，并启用 `MotionController.set_control_enabled(True)`。
5. 写入 `manual event test started` 事件日志和状态栏。
6. active 为假时，调用 `ManualEventTestController.stop()`。
7. 调用 `reset_event_move_runtime()` 重置 movement 和 event approach runtime。
8. 若自动导航未启用，关闭游戏输入窗口模式。
9. 写入 `manual event test stopped` 事件日志和状态栏。
副作用：启动/停止 task controller、按钮状态、输入窗口模式、motion control、movement runtime、日志和状态栏。
失败行为：本方法不做前置校验；调用方负责在启动前检查系统是否就绪。
调用关系：called by `NavigationModeWidget._set_manual_event_test_active()` wrapper、`NavigationEventLifecycle.run_manual_event_test()` and `NavigationEventLifecycle.reset_event_state()`。

### `NavigationMapClickLifecycle.handle_map_click(self, scene_pos) -> bool`
行为：按旧优先级解释地图点击：hint、route 编辑、手动移动目标。
算法：
1. 读取 `nav_core`；若不存在，返回 `False`。
2. 将 scene 坐标加上 `nav_core.crop_offset`，得到 int 全局地图坐标。
3. 若 hint 按钮 checked，调用 `set_initial_hint(scene_pos)`，返回 `True`。
4. 调用 `RouteEditor.handle_click(map_folder_path, global_point)`。
5. 若 route editor 处理了点击，写回 route data；若返回 next mode，则调用 `set_map_click_mode(next_mode)`；随后重绘 route overlay，写入 route 状态栏，返回 `True`。
6. 若当前没有完成定位或没有 `nav_core.current_pos`，弹移动目标需要定位 warning，返回 `False`。
7. 将全局坐标转为 float target，调用 `MotionController.move_to_map_target(current_pos, target)`。
8. 更新 target marker，并写入移动目标状态栏，返回 `True`。
副作用：可能写入 nav core hint、route data、route overlay、target marker、状态栏或触发真实移动点击。
失败行为：无 nav_core 或未定位时不执行移动；route editor 未处理且未定位时只弹 warning。
调用关系：called by `NavigationModeWidget.handle_map_click()` wrapper。

### `NavigationMapClickLifecycle.set_initial_hint(self, scene_pos) -> None`
行为：设置初始定位提示，并刷新 hint marker、监控框、真实视野框和状态栏。
算法：
1. 读取 `nav_core`；若不存在，直接返回。
2. 将 scene 坐标加上 `nav_core.crop_offset` 得到全局 float 坐标。
3. 调用 `nav_core.set_initial_hint((global_x, global_y))`。
4. 调用 `create_initial_hint_marker(scene, old_hint_item, scene_pos)` 并写回 hint item。
5. 调用 `update_monitor_rect((global_x, global_y))` 和 `update_game_view_rect((global_x, global_y))` 提供即时反馈。
6. 打印旧调试信息：scene 坐标、crop offset、全局坐标。
7. 调用 `show_initial_hint_set(status_label, global_x, global_y)`。
8. 取消 hint 按钮 checked，并调用 `toggle_hint_mode()` 恢复拖拽/光标/状态栏。
副作用：写入 `NavigationCore` 初始提示、QGraphics hint item、监控/视野框、按钮 checked、view drag/cursor 和状态栏。
失败行为：无 nav_core 时静默返回，保持旧调用前 guard 语义。
调用关系：called by `NavigationModeWidget.set_initial_hint()` wrapper and `NavigationMapClickLifecycle.handle_map_click()` hint branch。

### `NavigationMapClickLifecycle.toggle_hint_mode(self) -> None`
行为：根据 hint 按钮 checked 状态切换地图视图拖拽模式、光标和状态栏提示。
算法：
1. 读取 `hint_button.isChecked()`。
2. checked 为真时调用 `view.setDragMode(QGraphicsView.NoDrag)`，否则设为 `QGraphicsView.ScrollHandDrag`。
3. checked 为真时设置 `Qt.CrossCursor`，否则设置 `Qt.ArrowCursor`。
4. 调用 `show_hint_mode_status(status_label, is_hint_mode)`。
副作用：写入 QGraphicsView drag mode、cursor 和状态栏。
失败行为：控件缺少相关 Qt 方法时抛出属性错误，由开发期暴露。
调用关系：called by `NavigationModeWidget.toggle_hint_mode()` wrapper and `NavigationMapClickLifecycle.set_initial_hint()`。

### `NavigationRuntimeCommandLifecycle.can_start_auto_navigation(self) -> tuple[bool, str]`
行为：集中自动导航启动前置条件检查，并返回旧中文失败原因。
算法：
1. 若未加载地图或没有 `nav_core`，返回 `(False, "请先加载地图")`。
2. 从 route data 读取 `routes.main`；若没有 `exit_region`，返回 `(False, "请先设置出口")`。
3. 若 `NavConfig.game_screen_center` 为空，返回 `(False, "请先校准屏幕中心")`。
4. 若缺少监控逻辑中心/监控区域或 `monitor_size`，返回 `(False, "缺少监视窗口配置")`。
5. 全部通过时返回 `(True, "")`。
副作用：无，只读取 targets 提供的状态。
失败行为：缺少状态时返回失败原因，不抛异常。
调用关系：called by `NavigationModeWidget._can_start_auto_navigation()` wrapper and `_start_auto_navigation()`。

### `NavigationRuntimeCommandLifecycle.toggle_auto_navigation(self) -> None`
行为：根据自动导航按钮 checked 状态启动或停止自动导航。
算法：
1. 若 `auto_navigation_button.isChecked()` 为真，调用 `_start_auto_navigation()`。
2. 否则调用 `_stop_auto_navigation()`。
副作用：取决于启动/停止分支，可能启动 task controller、导航 timer、输入窗口模式或停止并重绘路线。
失败行为：启动失败时由 `_start_auto_navigation()` 完成按钮回滚和 warning。
调用关系：called by `NavigationModeWidget.toggle_auto_navigation()` wrapper。

### `NavigationRuntimeCommandLifecycle.start_navigation(self) -> bool`
行为：启动普通导航定位循环，并保持旧 guard/初始化/状态栏顺序。
算法：
1. 调用 `use_unified_navigation_loop()`，确保 timer timeout 连接到统一循环。
2. 调用 `start_event_log_session("navigation")`。
3. 检查 `NavConfig.game_screen_center`；缺失时弹缺屏幕中心 warning，复位开始按钮 checked，返回 `False`。
4. 检查监控配置；缺失时弹地图配置 warning，复位开始按钮 checked，返回 `False`。
5. 调用 `apply_config_to_runtime()`，应用最新导航配置。
6. 调用 `set_current_player_local_pos(None)` 清空上一帧局部位置。
7. 若存在 `nav_core`，调用 `request_full_map_localization("navigation_start")` 请求全图重定位。
8. 若存在 tracker，调用 `tracker.reset()`。
9. 按 `1000 // nav_config.fps` 计算 timer interval。
10. 启用 `MotionController.set_control_enabled(True)`，启动 `nav_timer.start(interval)`。
11. 将开始按钮文本改为“停止导航”，写入导航已开始状态栏，返回 `True`。
副作用：连接 timer、写日志 session、应用 config、请求重定位、重置 tracker、启动 timer/motion、写按钮和状态栏。
失败行为：guard 失败只弹 warning、复位按钮并返回 `False`；不启动 timer。
调用关系：called by `NavigationRuntimeCommandLifecycle.toggle_navigation()` and auto-navigation startup fallback。

### `NavigationRuntimeCommandLifecycle.stop_runtime(self) -> None`
行为：幂等停止导航运行副作用，用于停止按钮和主窗口关闭。
算法：
1. 停止 `nav_timer`。
2. 禁用 `MotionController` 控制。
3. 若存在 `nav_core`，复位 `is_first_frame_localized=False`。
4. 设置 `auto_navigation_enabled=False`。
5. 若手动事件测试 active，调用 `stop_manual_event_test("navigation stopped")`。
6. 调用 `NavigationTaskController.stop()`。
7. 关闭游戏输入窗口模式。
8. 复位开始按钮和自动导航按钮 checked。
9. 重绘 route overlay，恢复开始按钮文本为“开始导航”，写入导航暂停状态栏。
副作用：停止 timer/task、禁用真实输入控制、恢复窗口模式、复位按钮和状态栏、可能停止手动事件测试。
失败行为：设计为幂等；缺少 `nav_core` 时跳过 first-frame 复位。
调用关系：called by `NavigationModeWidget.stop_runtime()` wrapper and `NavigationRuntimeCommandLifecycle.toggle_navigation()` stop branch。

### `NavigationModeWidget._run_manual_event_test(self)`
行为：响应“测试事件流程/停止事件流程测试”按钮，以当前已注册事件的正式 pipeline 启停通用手工事件会话。
算法：
1. 若 `manual_test_controller.active` 已为真，停止手动测试并返回。
2. 校验事件协调器、地图定位内核和游戏屏幕中心均已就绪；失败时恢复按钮显示并弹出警告。
3. 若导航定时器未运行，则复用 `toggle_navigation()` 启动定位循环；启动失败时停止继续执行。
4. 调用 `_set_manual_event_test_active(True)`，开启游戏输入模式和运动控制。
5. 后续每帧由 `NavigationRuntimeFrameLoop.run()` 调用 `EventCoordinator.observe()` 识别事件，再构造 `NavigationUpdateContext(events.manual_event_only=True)` 并调用 `NavigationTaskController.update_context()` 选择并执行事件任务。
副作用：可启动导航循环、启用游戏输入、更新按钮/状态栏并记录事件日志。
失败行为：先决条件缺失时只警告并保持测试未启动。
调用关系：called by `EventManagerDialog.manual_test_requested` signal。

### `RouteEditor.handle_click(self, map_folder_path: str | None, global_point) -> RouteEditResult`
行为：按当前 map click mode 处理地图点击，更新 route 数据并返回 UI 所需的状态文本/下一模式。
算法：
1. 若未加载地图或当前 click mode 为 `NONE`，返回 `handled=False`。
2. 将全局坐标标准化为 int `(x, y)`。
3. `SET_EXIT` 调用 `RouteManager.set_exit_region(map_folder_path, (x, y), radius=28)`，随后重新读取 route data，并把内部 click mode 复位为 `NONE`。
4. `ADD_REQUIRED_POINT` 调用 `RouteManager.add_required_point()`，随后重新读取 route data，保持 click mode 便于连续添加。
5. `ADD_GUIDE_POINT` 调用 `RouteManager.add_guide_point()`，随后重新读取 route data，保持 click mode 便于连续添加。
6. 返回 `RouteEditResult`，由 `NavigationModeWidget.handle_map_click()` 决定是否刷新 overlay、按钮和状态栏。
副作用：写入 `RouteManager` 内存缓存中的 route 数据；保存到 `route.json` 仍由 `RouteEditor.save_route()`/`NavigationModeWidget.save_route()` 控制。
失败行为：未知 mode 被 `_coerce_mode()` 降级为 `NONE`；缺少地图路径时不抛异常。
调用关系：called by `NavigationModeWidget.handle_map_click()`。

### `NavigationRuntimeFrameLoop._execute_navigation_intent(self, intent, now_ms: int) -> None`
行为：消费统一导航控制器输出的动作意图，并把地图目标、屏幕点击或按键转换为真实输入。
算法：
1. 从 owner 读取 `MotionController`、`NavigationTaskController` 和启用游戏输入模式的回调，将它们连同 `intent/now_ms` 传给 `execute_navigation_intent()`。
2. `execute_navigation_intent()` 在 `NONE/WAIT` 时不执行输入。
3. `MOVE_MAP` 校验 `player_pos/subgoal`，打开游戏输入模式并启用 `MotionController`。
4. 若 intent metadata 带 `force_click_target`，调用 `MotionController.click_map_target_once()` 点击映射后的事件目标点；否则调用 `MotionController.move_to_map_target()` 做方向移动点击。
5. 真实点击成功后调用 `NavigationTaskController.record_intent_click()`，让 `MovementExecutor` 更新点击冷却和上次子目标，并返回 `click r/raw` 状态栏后缀。
6. `CLICK_SCREEN` 调用 `MotionController.click_screen_position()`；`PRESS_KEY` 调用 `MotionController.press_key()`。
7. frame loop 只负责把状态栏后缀追加到当前 `status_label`。
副作用：可能触发真实鼠标/键盘输入，更新状态栏点击诊断和 controller 点击节流状态。
失败行为：缺少必要坐标或 key 时跳过输入；底层输入异常由 `MotionController`/输入后端处理。
调用关系：called by `NavigationRuntimeFrameLoop.run()` through `consume_navigation_intent()` after `NavigationTaskController.update_context()`。

### `build_event_tick(*, now_ms, frame, player_pos, localized_pos, confidence, nav_core, nav_config, map_name: str, capture_provider) -> EventTick`
行为：把导航循环当前帧状态包装成事件系统统一输入。
算法：
1. 接收导航循环已捕获的 raw minimap frame、玩家局部坐标、定位结果和置信度。
2. 从 `nav_core.draw_scale` 读取当前地图缩放；`nav_core` 不存在时回退 `nav_config.draw_scale`。
3. 从 `nav_core.last_frame_registration` 读取当前帧墙体配准契约；`nav_core` 不存在时为 `None`。
4. 组装 `EventTick`，保留 `capture_provider` 供事件 handler 需要主画面截图时使用；`event_tasks` 初始为空，进入 `EventCoordinator.observe()` 后由 coordinator 写入当前 memory 任务快照。
副作用：无。
失败行为：不验证图像或定位是否有效；由 `EventCoordinator` 和后续模块按字段值决定是否运行。
调用关系：called by `NavigationModeWidget._build_event_tick()`。

### `NavigationRuntimeFrameLoop.run(self) -> None`
行为：当前唯一导航循环，统一完成定位、事件观察、任务调度、overlay/status 更新和动作意图消费。
算法：
1. 调用 `capture_navigation_localization_tick()` 执行配置校验、截图几何构造、抓屏、玩家局部坐标解析和 `NavigationCore.localize_result()`。
2. helper 返回空时直接结束本帧；返回有效 tick 时，widget 写回 `_current_capture_rect/_current_player_local_pos`。
3. 调用 `observe_navigation_events()` 构造 `EventTick`、执行 `EventCoordinator.observe()`、刷新事件 overlay 和可见事件窗口任务表。
4. 自动导航或手动事件测试启用时，计算 lookahead 并调用 `update_navigation_task_controller()`；普通自动导航允许 required/exit/event 统一调度，手动事件测试使用 `manual_event_only=True`。
5. 调用 `update_localization_view()` 更新玩家点、绿色监视框、橙色真实可见框和视图中心。
6. 调用 `show_navigation_runtime_status()` 写入当前帧基础状态栏。
7. 若存在 intent，先重绘 route overlay，再调用 `consume_navigation_intent()` 编排重定位短路、输入执行、手动事件测试停止和 ARRIVED/FAILED 终态处理。
8. 若 consumption result 标记 `skip_remaining_frame`，本帧提前返回；若标记 `terminal_navigation`，关闭 `auto_navigation_enabled`。
9. 无 intent 但存在路线数据时重绘静态 route overlay。
副作用：更新 UI、事件任务表、controller 状态、可能执行真实输入。
失败行为：截图失败、配置缺失或定位低置信时跳过移动，等待下一帧。
调用关系：called by `NavigationModeWidget._navigation_loop_unified()` compatibility entry and QTimer after `_use_unified_navigation_loop()` rewires the timer.

### `capture_geometry.build_capture_geometry(nav_config: NavConfig | None, capture_center_physical)`
行为：根据导航配置生成真实屏幕截图矩形和玩家在截图中的局部坐标。
算法：
1. 配置为空时返回 `(None, None, capture_center_physical)`。
2. 若存在 `monitor_region`，将 `left/top/width/height` 转为 int 后返回，player_pos 为 `None`。
3. 若没有 `monitor_logical_center` 或物理中心尚不可用，返回空几何。
4. 中心点模式下用 `monitor_size // 2` 从物理中心计算正方形截图 rect。
5. 返回 player_pos 为截图中心 `(width // 2, height // 2)`。
副作用：无。
失败行为：缺少中心或配置不完整时返回空几何，由调用方决定是否隐藏 overlay 或跳过导航循环。
调用关系：called by `NavigationModeWidget._build_capture_geometry()`。

### `viewport_overlay.monitor_scene_rect(player_pos, capture_rect, player_local_pos, nav_core)`
行为：计算绿色小地图截图范围框在导航地图场景中的矩形。
算法：
1. 校验 player_pos、capture_rect、player_local_pos 和 nav_core。
2. 读取 `nav_core.crop_offset` 和 `draw_scale`。
3. 将截图宽高乘以 draw_scale 得到地图坐标尺寸。
4. 将玩家局部截图坐标乘以 draw_scale，作为从玩家全局位置回推截图左上角的偏移。
5. 返回 `(rect_x, rect_y, rect_w, rect_h)`。
副作用：无。
失败行为：输入不完整时返回 `None`。
调用关系：called by `NavigationModeWidget._update_monitor_rect()`。

### `viewport_overlay.game_view_scene_rect(player_pos, nav_core, nav_config)`
行为：计算橙色真实主画面可见/可交互范围框在导航地图场景中的矩形。
算法：
1. 校验 player_pos、nav_core、nav_config。
2. 读取 `nav_config.game_view_map_size`；小于等于 0 时返回 `None`。
3. 用 `nav_core.crop_offset` 将玩家全局位置转换到当前地图场景。
4. 以玩家位置为中心，返回边长为 `game_view_map_size` 的正方形矩形。
副作用：无。
失败行为：输入不完整或尺寸无效时返回 `None`，调用方隐藏橙色框。
调用关系：called by `NavigationModeWidget._update_game_view_rect()`。

### `MappingCaptureSelectionController.start_region_selection(self, on_selected: Callable[[CaptureSelectionResult], None]) -> bool`
行为：启动建图区域选择全屏 overlay，并把确认结果交给调用方回调。
算法：
1. 如果 `overlay_active=True`，直接返回 `False`，避免重复创建全屏选择器。
2. 通过 `overlay_factory()` 创建 `TransparentOverlay`，并设置 `WA_DeleteOnClose`，关闭后释放 Qt 对象。
3. 将 overlay 的 `region_selected(x, y, width, height)` 信号连接到 `_handle_region_selected()`，由 controller 先应用坐标转换和 AppContext 写回，再回调调用方。
4. 将 `destroyed` 信号连接到 `_clear_region_overlay()`，关闭或取消时复位 active flag 和 overlay 引用。
5. 记录 overlay 引用、置 `overlay_active=True`，调用 `showFullScreen()`。
副作用：创建并显示全屏 Qt overlay；写入 controller 的 overlay 状态。
失败行为：重复启动时返回 `False`；Qt overlay 创建/显示异常向上传播。
调用关系：called by `MappingWidget.select_region()`。

### `MappingCaptureSelectionController.start_center_selection(self, on_selected: Callable[[CaptureSelectionResult], None]) -> bool`
行为：启动建图中心点选择全屏 overlay，并把确认结果交给调用方回调。
算法：
1. 如果 `center_selector_active=True`，直接返回 `False`。
2. 通过 `center_selector_factory()` 创建 `CenterPointSelector`，设置 `WA_DeleteOnClose`。
3. 将 `point_selected(x, y)` 信号连接到 `_handle_center_selected()`，由 controller 使用当前 `app_context.monitor_size` 应用中心点选择。
4. 将 `selection_cancelled` 和 `destroyed` 都连接到 `_clear_center_selector()`，取消或关闭时复位状态。
5. 记录 selector 引用、置 `center_selector_active=True`，调用 `showFullScreen()`。
副作用：创建并显示全屏 Qt selector；写入 controller 的 selector 状态。
失败行为：重复启动时返回 `False`；Qt selector 创建/显示异常向上传播。
调用关系：called by `MappingWidget.select_center_point()`。

### `MappingCaptureSelectionController.apply_region_selection(self, x: int, y: int, width: int, height: int) -> CaptureSelectionResult`
行为：把 overlay 发出的逻辑像素矩形转换为物理截图区域，并写入 `app_context.monitor_region`。
算法：
1. 调用注入的 `compute_scale()` 获取 `(sx, sy)`，当前由 `MappingWidget._compute_scale()` 基于 primary screen DPR 返回。
2. 用 `int(logical * scale)` 分别计算 `left/top/width/height` 物理像素。
3. 构造 `{"left": px_left, "top": px_top, "width": px_width, "height": px_height}`。
4. 写入 `app_context.monitor_region`，清空 `app_context.monitor_logical_center`，并清空 controller 的 `monitor_center`，表示当前切回区域截图模式。
5. 返回 `CaptureSelectionResult(mode="region", monitor_region=..., label_text=...)`，由 widget 决定 UI label、按钮和保存。
副作用：写入 `app_context.monitor_region` / `monitor_logical_center` 和 controller `monitor_center`。
失败行为：`compute_scale()` 或 AppContext 字段写入异常向上传播；不校验 width/height 是否大于 0，保持旧 overlay 路径语义。
调用关系：called by `_handle_region_selected()` and `MappingWidget.on_region_selected()` compatibility slot。

### `MappingCaptureSelectionController.apply_center_selection(self, x: int, y: int, monitor_size: int) -> CaptureSelectionResult`
行为：把中心点逻辑像素和截图尺寸写入 AppContext，并计算物理中心点供截图使用。
算法：
1. 将 `(x, y)` 和 `monitor_size` 转为 int。
2. 调用 `compute_scale()` 获取 DPR，计算 `physical_center=(int(x*sx), int(y*sy))`。
3. 写入 `app_context.monitor_logical_center=(x, y)`、`app_context.monitor_size=monitor_size`，并清空 `app_context.monitor_region`，表示切回中心点正方形截图模式。
4. 写入 controller `monitor_center=physical_center`。
5. 返回 `CaptureSelectionResult(mode="center", logical_center=..., physical_center=..., monitor_size=..., label_text=...)`。
副作用：写入 AppContext 截图配置和 controller `monitor_center`。
失败行为：`compute_scale()` 或 AppContext 字段写入异常向上传播。
调用关系：called by `_handle_center_selected()`、`update_capture_size()`、`restore_from_context()` and `MappingWidget.on_center_selected()` compatibility slot。

### `MappingCaptureSelectionController.update_capture_size(self, size: int) -> CaptureSelectionResult | None`
行为：更新中心点截图大小；如果当前不是中心点模式，只保存 size，不刷新中心点 label。
算法：
1. 将 `size` 转 int 并写入 `app_context.monitor_size`。
2. 读取 `app_context.monitor_logical_center`；为空说明当前是区域截图模式或尚未选择，返回 `None`。
3. 若存在逻辑中心点，调用 `apply_center_selection()` 重新计算物理中心和 label 结果。
副作用：总是写入 `app_context.monitor_size`；中心点模式下还会刷新 controller `monitor_center`。
失败行为：中心点 tuple 形状非法时在索引处抛出异常，保持原 `on_center_selected(*center)` 路径风险。
调用关系：called by `MappingWidget.update_capture_size()`。

### `MappingCaptureSelectionController.restore_from_context(self) -> CaptureSelectionResult | None`
行为：从已加载的 AppContext 截图配置恢复 label 和物理中心状态。
算法：
1. 若 `app_context.monitor_logical_center` 存在，调用 `apply_center_selection()`，用当前 `monitor_size` 重新计算 physical center。
2. 否则若 `app_context.monitor_region` 存在，构造 region 模式的 `CaptureSelectionResult`，并清空 controller `monitor_center`。
3. 两种配置都不存在时，清空 controller `monitor_center` 并返回 `None`。
副作用：中心点模式下会重写 AppContext 中心点/尺寸/区域字段；区域或空配置会清空 controller 物理中心。
失败行为：保存配置字段缺失必需 key 时会抛出 `KeyError`，由 `MappingWidget.load_saved_params()` 外层现有异常处理覆盖部分格式错误。
调用关系：called by `restore_saved_mapping_config()` after root config monitor fields are loaded into AppContext。

### `build_mapping_ui(owner) -> None`
行为：构建绘图页左右布局并把控件属性写回 `MappingWidget` owner。
算法：
1. 在 owner 上创建根 `QHBoxLayout`。
2. 调用 `create_mapping_control_panel(owner)` 创建左侧控制面板并以 stretch=1 加入布局。
3. 调用 `create_mapping_display_panel(owner)` 创建右侧实时截图/全局地图显示面板并以 stretch=3 加入布局。
副作用：创建 Qt layout/widgets，并写入 owner 的 UI 字段。
失败行为：owner 缺少预期 slot、`app_context` 或 stitcher/recognizer 字段时沿 Qt 构建路径抛异常。
调用关系：called by `MappingWidget.setup_ui()`。

### `create_mapping_control_panel(owner) -> QWidget`
行为：创建建图页左侧控制面板，并连接区域选择、监控控制、几何、融合、HSV、特征和统计控件。
算法：
1. 创建 panel 和垂直布局。
2. 创建监控区域组：区域选择、中心点选择、截图尺寸、颜色选择和区域状态 label，并连接 owner 的 selection/color slots。
3. 创建监控控制组：FPS、开始/停止、重置、保存和置顶控件，并连接 owner 的 runtime/save/topmost slots。
4. 创建高清绘图参数组：draw scale、canvas size、player clear radius 和 wall close kernel spinbox，默认值读取当前 `app_context.stitcher/recognizer`。
5. 创建融合、HSV 和特征参数组，保持旧默认值和 `update_*_params` 信号连接。
6. 创建统计文本框并返回 panel。
副作用：创建 Qt 控件，写入 owner 的控件字段，连接 Qt signals。
失败行为：owner slot 不存在、Qt 控件构造失败或 app_context 缺少参数字段时抛异常。
调用关系：called by `build_mapping_ui()`。

### `create_mapping_display_panel(owner) -> QWidget`
行为：创建建图页右侧实时截图和全局地图显示面板。
算法：
1. 创建 panel 和垂直布局。
2. 创建实时截图 group、`capture_label`，设置居中、最小尺寸和黑色背景。
3. 创建 `CollapsibleMapGroup`，把 `global_map_widget` 写回 owner。
4. 将 `global_map_widget.pixel_clicked` 连接到 `owner.on_map_click`，保持旧地图点击路径预览行为。
5. 返回 panel。
副作用：创建 Qt 控件，写入 owner 的显示字段，连接地图点击 signal。
失败行为：`CollapsibleMapGroup` 构造或 signal 连接异常向上传播。
调用关系：called by `build_mapping_ui()`。

### `MappingRuntimeLifecycle.toggle_monitoring(self) -> None`
行为：响应建图页开始/停止监控按钮，切换 monitoring 状态并启动或停止 capture timer。
算法：
1. 翻转 `app_context.monitoring`。
2. 若新状态为开启，先检查是否存在 `monitor_region` 或 `monitor_logical_center`。
3. 若缺少截图配置，回滚 `monitoring=False`，弹出“请先选择一个监控区域或中心点。”并返回。
4. 若截图配置存在，按 `1000 // get_fps()` 启动 `capture_timer`。
5. 将开始按钮文案改为“⏸️ 停止监控”。
6. 若新状态为关闭，调用 `stop_runtime()`。
副作用：写入 `app_context.monitoring`，启动/停止 QTimer，修改按钮文案，必要时弹出 QMessageBox。
失败行为：`get_fps()` 返回 0 会触发除零异常；当前 FPS spinbox 范围为 1-60，保持 UI 约束。
调用关系：called by `MappingWidget.toggle_monitoring()` wrapper。

### `MappingRuntimeLifecycle.stop_runtime(self) -> None`
行为：幂等停止建图 capture runtime，用于停止按钮分支和主窗口关闭。
算法：
1. 停止 `capture_timer`。
2. 写入 `app_context.monitoring=False`。
3. 将开始按钮文案恢复为“▶️ 开始监控”。
副作用：停止 QTimer、写 AppContext 运行态、修改按钮文案。
失败行为：设计为幂等；timer 未启动时 `stop()` 无额外副作用。
调用关系：called by `MappingWidget.stop_runtime()` wrapper and `MappingRuntimeLifecycle.toggle_monitoring()` stop branch。

### `project_root_from_file(file_path: str | Path) -> Path`
行为：从 GUI 内任意源文件或目录解析项目根目录。
算法：
1. 将 `file_path` 转为绝对 `Path`。
2. 若传入目录则从该目录开始，否则从文件父目录开始。
3. 从起点一路向上遍历父目录。
4. 第一个同时包含 `main.py` 和 `gui/` 的目录即为项目根目录。
5. 如果遍历结束仍未找到，抛出 `FileNotFoundError`。
副作用：读取文件系统元数据，不写文件。
失败行为：不再按固定 `parents[n]` fallback；找不到项目标记时显式失败，避免静默写错路径。
调用关系：called by `gui.composition.paths` sibling helpers, `mapping.io.config_store.project_root_from_file`, and `navigation.map.config_store.project_root_from_file`。

### `project_root_from_map_folder(map_folder_path: str | Path) -> Path`
行为：从 `map_data/<map_name>` 地图目录解析项目根目录。
算法：
1. 将 `map_folder_path` 转为绝对路径。
2. 从当前路径和所有父目录中查找名字为 `map_data` 的目录。
3. 找到后返回该 `map_data` 目录的父目录。
4. 若路径不在 `map_data` 下，回退到 `project_root_from_file()` 的标记查找。
副作用：读取路径结构，不写文件。
失败行为：路径既不在 `map_data` 下也找不到项目标记时由 `project_root_from_file()` 抛出 `FileNotFoundError`。
调用关系：called by `root_config_path_from_map_folder()` and `navigation.map.config_store.default_nav_config_path_from_map_folder()`。

### `map_data_dir_from_file(file_path: str | Path) -> Path`
行为：从源文件或目录解析项目 `map_data` 目录。
算法：
1. 调用 `project_root_from_file(file_path)`。
2. 返回 `project_root / "map_data"`。
副作用：无。
失败行为：项目根无法解析时抛出 `FileNotFoundError`。
调用关系：called by `mapping.io.config_store.map_data_dir()` and `navigation.map.config_store.map_data_dir()`。

### `root_config_path_from_file(file_path: str | Path) -> Path`
行为：从源文件或目录解析项目根 `config.json`。
算法：
1. 调用 `project_root_from_file(file_path)`。
2. 返回 `project_root / "config.json"`。
副作用：无。
失败行为：项目根无法解析时抛出 `FileNotFoundError`。
调用关系：called by `mapping.io.config_store.root_config_path()` and `navigation.map.config_store.default_nav_config_path_from_file()`。

### `advanced_settings_dir_from_file(file_path: str | Path) -> Path`
行为：从源文件或目录解析高级参数 snapshot 目录。
算法：
1. 调用 `project_root_from_file(file_path)`。
2. 返回 `project_root / "configs" / "advanced_settings"`。
副作用：无。
失败行为：项目根无法解析时抛出 `FileNotFoundError`。
调用关系：called by `gui.dialogs.advanced_settings.file_io.DEFAULT_ADVANCED_SETTINGS_DIR` initialization。

### `create_core_services(*, canvas_size: int = 5000) -> CoreServices`
行为：创建 GUI 默认共享 core services。
算法：
1. 创建 `SquareScreenCapture()`。
2. 创建 `HSVRecognizer()`。
3. 创建 `MapStitcher(canvas_size=canvas_size)`，默认 `canvas_size=5000` 保持旧 AppContext 行为。
4. 创建 `PlayerTracker()`。
5. 创建 `PathFinder()`。
6. 将五个对象打包为 frozen `CoreServices` 返回。
副作用：实例化屏幕捕获、识别器、拼接器、tracker 和 pathfinder；`SquareScreenCapture` 可能初始化底层屏幕捕获 backend。
失败行为：任一 core service 构造失败会向上传播，保持启动期显式失败。
调用关系：called by `AppContext.__init__()` when no services DTO is injected。

### `build_mapping_config(app_context, fps: int, *, include_draw_scale: bool = False) -> dict`
行为：把绘图模式当前运行态序列化为旧版 `config.json` 字段字典。
算法：
1. 从 `app_context.monitor_logical_center`、`monitor_size`、`monitor_region` 读取截图配置。
2. 使用传入 `fps` 写入帧率字段，避免 helper 依赖 Qt spinbox。
3. 调用 `app_context.recognizer.get_params()` 和 `app_context.stitcher.get_params()` 获取算法参数。
4. 当 `include_draw_scale=True` 时，在字典前部加入 `draw_scale`，用于地图级配置；根级配置保持旧字段集合。
副作用：读取 recognizer/stitcher 参数，不写文件。
失败行为：若 `app_context` 缺少 recognizer 或 stitcher 参数接口，会按原调用路径抛出异常。
调用关系：called by `MappingWidget.save_map()` and `MappingWidget.save_config()`。

### `MappingWidget._build_mapping_config_with_ui_overrides(self, *, include_draw_scale: bool = False) -> dict`
行为：在通用绘图配置基础上叠加绘图页几何/清晰度控件值。
算法：
1. 调用 `build_mapping_config()` 收集截图、FPS、recognizer 和 stitcher 当前运行参数。
2. 用 UI 控件覆盖 `stitcher_params.draw_scale`、`canvas_size`、`wall_close_kernel_size`。
3. 用 UI 控件覆盖 `recognizer_params.player_clear_radius`。
4. `include_draw_scale=True` 时同步写入顶层 `draw_scale`，供导航模式按地图包坐标体系加载。
副作用：读取 Qt 控件值，不写文件。
失败行为：控件缺失时沿原调用路径抛异常。
调用关系：called by `MappingWidget.save_map()` and `MappingWidget.save_config()`。

### `ensure_map_folder(file_path: str | Path, map_name: str) -> Path`
行为：根据当前源码文件定位项目 `map_data/<map_name>` 目录并确保存在。
算法：
1. 调用 `map_folder_for_name(file_path, map_name)`。
2. `map_folder_for_name()` 通过 `map_data_dir(file_path)` 定位项目 `map_data`，实际项目根解析委托 `gui/composition/paths.py`。
3. 拼接 `map_data/map_name`。
4. 调用 `mkdir(parents=True, exist_ok=True)` 创建目录。
副作用：可能创建 `map_data/<map_name>` 目录。
失败行为：文件系统权限或非法地图名导致 `OSError` 向上传播，保持原保存失败路径不吞异常。
调用关系：called by `MappingWidget.save_map()`。

### `save_mapping_map(file_path, map_name: str, *, stitcher, config_data: dict)`
行为：保存当前建图结果和地图级配置。
算法：
1. 调用 `ensure_map_folder(file_path, map_name)` 定位并创建 `map_data/<map_name>`。
2. 调用 `stitcher.save_map_package(str(map_folder))` 保存 `map_data.npz`。
3. 调用 `save_map_config(map_folder, config_data)` 写入 `config.json`。
4. 返回 `map_folder`，供调用方需要展示或测试路径。
副作用：创建地图目录、写入地图包和地图级配置文件。
失败行为：目录创建、地图包保存或 JSON 写入异常向上传播；当前 GUI 与旧行为一致，不在 `save_map()` 中捕获。
调用关系：called by `MappingWidget.save_map()`。

### `save_root_config(file_path: str | Path, config: dict) -> Path`
行为：把绘图模式全局配置写入项目根目录 `config.json`。
算法：
1. 通过 `root_config_path(file_path)` 定位项目根目录配置文件。
2. 调用 `save_json_config()` 以 UTF-8 和 `indent=4` 写入 JSON。
3. 返回写入路径供调用方需要时使用。
副作用：覆盖项目根目录 `config.json`。
失败行为：JSON 序列化或文件写入异常向上传播。
调用关系：called by `MappingWidget.save_config()`。

### `restore_saved_mapping_config(file_path, *, app_context, capture_selection, handle_capture_selection_result, stitcher_is_empty, targets: MappingConfigRestoreTargets) -> bool`
行为：读取根配置并按旧启动顺序恢复建图页运行态和控件。
算法：
1. 调用 `load_root_config(file_path)`；配置不存在时返回 `False`。
2. 将 `monitor_logical_center`、`monitor_size`、`monitor_region` 写入 `app_context`。
3. 调用 `capture_selection.restore_from_context()`，若返回结果则回调 `handle_capture_selection_result(result, save=False)`，恢复 label、按钮和物理中心状态。
4. 将 `monitor_size` 和 `fps` 写入 size/fps 控件。
5. 若存在 `recognizer_params`，先调用 `app_context.recognizer.set_params()`，再通过 `sync_recognizer_widgets()` 回填 feature 控件。
6. 若存在 `stitcher_params` 且 `stitcher_is_empty()` 为真，先用 `canvas_size/draw_scale/wall_close_kernel_size` 重建空画布；随后调用 `app_context.stitcher.set_params()` 并同步 merge weight 控件。
7. 为 draw scale、canvas size、player clear radius、wall close kernel 控件创建 `QSignalBlocker`，调用 `sync_geometry_widgets()` 回填几何控件，最后释放 blockers。
8. 返回 `True`。
副作用：读取项目根 `config.json`；写入 AppContext、recognizer/stitcher 参数和 Qt 控件；可能重建空 stitcher 画布。
失败行为：JSON 格式错误由 `load_root_config()` 抛出，字段缺失/控件不匹配按原路径抛出；`MappingWidget.load_saved_params()` 捕获 `json.JSONDecodeError` 和 `KeyError`。
调用关系：called by `MappingWidget.load_saved_params()`。

### `load_root_config(file_path: str | Path) -> dict | None`
行为：读取项目根目录 `config.json`，不存在时保持旧行为直接返回空。
算法：
1. 通过 `root_config_path(file_path)` 定位配置文件。
2. 若文件不存在，返回 `None`。
3. 文件存在时调用 `load_json_config()` 读取 dict。
副作用：读取项目根目录 `config.json`。
失败行为：JSON 格式错误会抛出 `json.JSONDecodeError`，由 `MappingWidget.load_saved_params()` 原有 except 处理。
调用关系：called by `restore_saved_mapping_config()`。

### `render_global_map_pixmap(*, global_map, crop_x1: int, crop_y1: int, nav_path, current_position, draw_scale: float, player_pos=None, capture_size=None) -> QPixmap | None`
行为：将 `MapStitcher.get_enhanced_map()` 返回的全局地图图像绘制成可显示的 Qt pixmap。
算法：
1. 空地图直接返回 `None`。
2. 灰度图先转换为 BGR，彩色图复制一份，避免修改原地图数据。
3. 若存在 `nav_path`，将全局路径点减去裁剪偏移，点数超过 1 时用黄色 polyline 绘制。
4. 将 `current_position` 减去裁剪偏移得到当前人物场景坐标。
5. 若 `capture_size` 和 `player_pos` 存在，用 `draw_scale` 计算小地图视野框宽高和人物在截图中的偏移，并绘制绿色矩形。
6. 绘制当前位置绿色实心圆和红色外圈。
7. 调用 `pixmap_from_bgr()` 转为 `QPixmap` 返回。
副作用：无文件或 UI 副作用；只在内部副本上绘制。
失败行为：输入图像 shape 不符合 OpenCV BGR/GRAY 预期时由 OpenCV/PySide 抛错。
调用关系：called by `MappingWidget.update_displays()`。

### `pixmap_from_bgr(image) -> QPixmap | None`
行为：把 OpenCV BGR 图像转换为 Qt `QPixmap`。
算法：
1. 输入为空时返回 `None`。
2. 用 `cv2.cvtColor(..., COLOR_BGR2RGB)` 转为 RGB。
3. 用图像宽高和 `channels * width` 构造 `QImage`。
4. 对 `QImage` copy 后创建 `QPixmap`，避免引用临时 numpy buffer。
副作用：创建 Qt 图像对象。
失败行为：非三通道 BGR 输入会由 OpenCV 或 QImage 构造抛错；当前调用方只传预处理截图或已转为 BGR 的全局图。
调用关系：called by `mapping.presentation.map_presenter.update_mapping_displays()` and `render_global_map_pixmap()`。

### `feature_params_from_widgets(*, clahe_check, deepen_check, wall_weight_spin, edge_weight_spin, gray_weight_spin, canny_low_spin, canny_high_spin) -> dict`
行为：从绘图页 feature 控件读取 recognizer 参数 dict。
算法：
1. 从 CLAHE 和颜色深化复选框读取布尔值。
2. 从墙体、边缘、灰度权重 spinbox 读取整数权重。
3. 从 Canny low/high spinbox 读取边缘阈值。
4. 返回字段名与原 `recognizer.set_params()` 契约一致的 dict。
副作用：无；只读取控件。
失败行为：控件对象缺少 `isChecked()` 或 `value()` 时向上传播 `AttributeError`。
调用关系：called by `MappingWidget.update_feature_params()`。

### `sync_recognizer_widgets(params: dict, *, clahe_check, deepen_check, wall_weight_spin, edge_weight_spin, gray_weight_spin, canny_low_spin, canny_high_spin) -> None`
行为：将已加载 recognizer 参数按旧默认值和旧顺序写回绘图页控件。
算法：
1. 用 `clahe_enabled=True`、`deepen_enabled=True` 写回复选框默认值。
2. 用 `wall_weight=50`、`edge_weight=30`、`gray_weight=20` 写回权重控件默认值。
3. 用 `edge_low=50`、`edge_high=150` 写回 Canny 阈值控件默认值。
4. 不阻断 Qt 信号，保留旧加载配置时可能触发 `update_feature_params()` 的副作用。
副作用：写入 Qt 控件状态，可能触发既有信号。
失败行为：缺少参数键时使用旧默认值；控件写入失败向上传播。
调用关系：called by `MappingWidget.load_saved_params()`。

### `apply_hsv_toggles(recognizer, wall_check, fog_check) -> None`
行为：将绘图页 HSV 开关同步到 recognizer 运行时对象。
算法：
1. 读取墙体识别复选框状态并写入 `recognizer.enable_wall`。
2. 读取迷雾识别复选框状态并写入 `recognizer.enable_fog`。
副作用：修改 recognizer 运行时字段。
失败行为：recognizer 或控件缺少对应属性/方法时向上传播异常。
调用关系：called by `MappingWidget.update_hsv_params()`。

### `collect_params_from_widgets(dialog) -> dict`
行为：从高级参数弹窗全部参数控件采集 recognizer/stitcher 参数 dict。
算法：
1. 读取预处理控件：颜色深化、对比、蓝色增强、Gamma、Tophat、CLAHE。
2. 读取特征控件：Canny 阈值、墙体/边缘/灰度权重。
3. 读取透明模式和饱和度过滤控件。
4. 若拼接器控件存在，读取 `conf_thresh/keyframe_thresh/weight_add/weight_cap`；不存在时使用旧 fallback 默认值。
5. 返回字段名与旧 `AdvancedSettingsDialog.apply_params()` 构造的 dict 一致。
副作用：无；只读取控件。
失败行为：控件不存在或类型不匹配时抛出 `AttributeError`，保持旧直接访问失败路径。
调用关系：called by `AdvancedSettingsDialog.apply_params()`。

### `AdvancedSettingsDialog.apply_params(self)`
行为：采集高级参数并请求 owner 应用；兼容模式下仍直接写 parent recognizer/stitcher。
算法：
1. 调用 `collect_params_from_widgets(self)` 生成参数 dict。
2. 发出 `apply_params_requested(params)`，让 owner 处理运行时写入。
3. 如果 `_direct_runtime_apply_enabled` 为真，调用 `_apply_params_directly(params)` 保持旧调用方兼容。
4. 将 `self.current_params` 更新为本次参数 dict。
5. 打印应用成功日志。
副作用：发出 Qt signal；兼容 fallback 模式下可能调用 recognizer/stitcher 的 `set_params()`。
失败行为：owner slot 或 fallback `set_params()` 抛异常时向上传播，保持旧行为。
调用关系：called by `apply_btn.clicked`；indirectly consumed by `MappingWidget._apply_advanced_settings_params()`。

### `AdvancedSettingsDialog.use_external_apply_handler(self)`
行为：关闭 dialog 内部 direct runtime mutation，使参数应用只通过 command signal 交给 owner。
算法：
1. 将 `_direct_runtime_apply_enabled` 置为 `False`。
2. 后续 `apply_params()` 仍发 signal，但不再调用 `_apply_params_directly()`。
副作用：修改 dialog 内部兼容开关。
失败行为：无。
调用关系：called by `MappingWidget.open_advanced_settings()` after connecting `apply_params_requested`。

### `MappingWidget._apply_advanced_settings_params(self, params: dict, *, save: bool = True)`
行为：作为高级参数 command owner，将参数应用到共享 recognizer/stitcher，并按调用时机决定是否保存配置。
算法：
1. 调用 `self.app_context.recognizer.set_params(params)`。
2. 调用 `self.app_context.stitcher.set_params(params)`。
3. 如果 `save=True`，调用 `save_config()` 写回绘图配置。
副作用：修改运行时 recognizer/stitcher；确认对话框 OK 时保存配置。弹窗内“应用参数”通过 signal 调用本函数时传 `save=False`，保留旧实时应用不立即落盘的语义。
失败行为：核心对象 `set_params()` 抛异常时向上传播。
调用关系：called by `AdvancedSettingsDialog.apply_params_requested` with `save=False` and by `MappingWidget.open_advanced_settings()` on accepted dialog with `save=True`。

### `load_params_to_widgets(dialog, params: dict) -> None`
行为：将当前高级参数 dict 写入弹窗控件。
算法：
1. 固定写入 `blur_strength_spin=3`，保持旧加载当前参数行为。
2. 用各字段旧默认值写入预处理、特征、透明模式、饱和度过滤控件。
3. 若拼接器控件存在，写入拼接器参数默认值。
副作用：写入 Qt 控件状态。
失败行为：缺失参数键使用旧默认值；控件写入异常向上传播。
调用关系：called by `AdvancedSettingsDialog.load_current_params()`。

### `apply_preset_to_widgets(dialog, preset: str) -> bool`
行为：根据高级参数弹窗预设名称写入对应控件值。
算法：
1. `"默认参数"` 调用 `reset_widgets_to_default()`。
2. 调用 `preset_values(preset)` 取得该预设的数据字典。
3. 若无匹配数据，返回 `False`，调用方当前不使用返回值。
4. 遍历数据字典，用 widget attribute name 找到控件并调用 `setValue(value)`。
5. 返回 `True`。
副作用：写入 Qt 控件状态。
失败行为：控件缺失时抛出 `AttributeError`。
调用关系：called by `AdvancedSettingsDialog.apply_preset()`。

### `calculate_hsv_range(hsv_values) -> tuple`
行为：根据颜色选择弹窗采样的 HSV 值计算推荐 HSV 最小/最大范围。
算法：
1. 将采样值列表转换为 numpy array。
2. 沿采样点维度计算 HSV 均值和标准差。
3. 计算容差 `maximum(std * 2, [5, 20, 20])`。
4. 用均值减/加容差得到初始范围。
5. 将范围 clamp 到 HSV 合法边界 `[0,0,0]` 和 `[179,255,255]`。
6. 返回均值、int 最小 HSV、int 最大 HSV。
副作用：无。
失败行为：空采样列表会产生 numpy warning/NaN；调用方仍在 `calculate_hsv_ranges()` 入口检查至少有采样点。
调用关系：called by `ColorPickerDialog._calculate_range()`。

### `pixmap_from_image(image, fallback_image=None) -> QPixmap`
行为：把颜色选择弹窗中的 OpenCV 图像转换为 Qt pixmap。
算法：
1. `image` 不为空时使用它，否则使用 fallback image。
2. 灰度图按 `QImage.Format_Grayscale8` 构造。
3. BGR 彩色图先转 RGB，再按 `QImage.Format_RGB888` 构造。
4. 返回 `QPixmap.fromImage(q_image)`，保持旧实现未 copy 的行为。
副作用：创建 Qt 图像对象。
失败行为：image 和 fallback 都为空或 shape 非预期时抛出异常。
调用关系：called by `ColorPickerDialog._show_image()`。

### `draw_sample_markers(pixmap: QPixmap, *, original_width: int, original_height: int, zoom: float, wall_points, player_points) -> QPixmap`
行为：在缩放后的颜色选择图像上绘制墙体/人物采样 marker。
算法：
1. 按原图宽高和 zoom 计算目标 pixmap 尺寸。
2. 使用 `Qt.KeepAspectRatio` 和 `Qt.SmoothTransformation` 缩放。
3. 计算缩放后显示宽高相对原图的 scale_x/scale_y。
4. 墙体点使用蓝色 pen/brush 绘制外圈半径 5、内点半径 2。
5. 人物点使用绿色 pen/brush 绘制同样尺寸 marker。
6. 结束 painter 并返回缩放后的 pixmap。
副作用：修改缩放后的 pixmap 副本。
失败行为：原图尺寸为 0 会除零；调用方初始化时已来自截图尺寸。
调用关系：called by `ColorPickerDialog._show_image()`。

### `build_wall_preview(image, wall_hsv_range) -> WallPreviewResult | None`
行为：根据颜色选择弹窗当前 wall HSV 范围生成右侧二值预览 mask 和 debug 统计。
算法：
1. `wall_hsv_range` 为空时返回 `None`，保持旧 `update_preview()` 未计算墙体范围时直接返回的行为。
2. 解包 `(min_hsv, max_hsv)`，将预处理后的 BGR 截图转换为 HSV。
3. 调用 `cv2.inRange(hsv, min_hsv, max_hsv)` 得到 wall mask。
4. 统计形态学处理前白色像素数、总像素数和白色比例。
5. 创建 3x3 uint8 kernel，复制一份 `mask_before_morph` 和 `mask_after_close`。
6. 调用 `cv2.morphologyEx(mask, MORPH_CLOSE, kernel)` 执行 close。
7. 统计 close 后白色像素数，并计算旧实现中的 `before_count - after_count` 差值。
8. 返回 `WallPreviewResult`，包含 preview mask、before mask、HSV 图、HSV 范围和所有 debug 统计字段。
副作用：无；不写文件、不触碰 Qt 控件。
失败行为：输入图像 shape 或 HSV 范围类型不合法时由 OpenCV/Numpy 异常向上传播。
调用关系：called by `ColorPickerDialog.update_preview()`。

### `event_detection_to_target_detection(detection: EventDetection) -> TargetDetection`
职责：把一个 legacy 小地图事件转换为通用感知结果，供统一观察、调试和未来通用识别 producer 使用。
算法：1. 深拷贝 detector metadata，避免 generic consumer 改写旧事件或其嵌套诊断数据。2. 验证 `local_minimap_pos` 为两个有限坐标。3. 构造 `TargetDetection(target_type=event_type, center=local_minimap_pos, coordinate_space=MINIMAP)`，保留 source、confidence 和 detected time。4. 若 metadata 中的 `bbox` 是四个有限数值，则额外建立 `BoundingBox`；`text` 存在时额外写入 target text，原 metadata 始终保留。
副作用：无。
失败行为：空/非有限局部坐标抛出 `ValueError`；超出 `TargetDetection` 的 0..1 confidence 契约会抛出 `ValueError`，以免不受支持的旧分数静默进入通用层。
调用关系：called by `normalize_legacy_event_detections()`；indirectly called by `EventMonitor.detect()`。

### `target_detection_to_event_detection(detection: TargetDetection, *, event_type: str) -> EventDetection`
职责：把已明确归类到一个事件定义的通用小地图目标输入原有稳定器、memory 和 handler 链。
算法：1. 拒绝不是 `MINIMAP` 的 detection，防止全屏/窗口/全局坐标被错误投影。2. 验证调用方显式指定的非空 `event_type`。3. 深拷贝 metadata；若原 metadata 没有 bbox/text，则把 generic `BoundingBox`/text 以 legacy metadata 形状补入。4. 将有限中心坐标四舍五入成 legacy 整数小地图像素，保留 source/confidence/time 并返回 `EventDetection`。
副作用：无。
失败行为：非 MINIMAP 空间、空 event type 或非有限中心抛出 `ValueError`；缺少 required keyword `event_type` 由 Python 抛出 `TypeError`。
调用关系：called by `normalize_legacy_event_detections()`；结果被 `EventMonitor.detect()` 返回给 `EventPositionStabilizer.update()`。

### `normalize_legacy_event_detections(detections: Iterable[EventDetection]) -> tuple[tuple[EventDetection, ...], tuple[TargetDetection, ...]]`
职责：在不改变 event 输出顺序、类型或 detector 语义的情况下，让一批旧检测经过共享 schema。
算法：1. 按输入顺序转换每个 legacy detection 为 target detection。2. 用原 event type 显式反向转换该 target。3. 返回独立 metadata 的 reconstructed legacy tuple 和 parallel target tuple。
副作用：无。
失败行为：单条检测违反共享模型契约时立即传播明确的 `ValueError`，不会把不确定空间写入稳定器。
调用关系：called by `EventMonitor.detect()`。

### `EventCoordinator.observe(self, tick) -> None`
行为：运行事件检测、局部到全局定位、任务记忆和显示任务选择，但不推进任何事件 handler。
算法：
1. 全局事件配置关闭时停止/清理 active runner，清空 last action 和 selected task。
2. 调用 `EventMonitor.detect()` 在 raw minimap frame 上产生局部 `EventDetection`；monitor 在此组合接缝先经过 `TargetDetection(MINIMAP)` 并保存 `last_target_detections`，再返回等价的独立 legacy detection 给后续代码。
3. 调用 `EventPositionStabilizer.update()` 使用 `FrameRegistration` 将局部检测投影为稳定全局 `EventObservation`。
4. 调用 `EventMemory.merge_observations()` 合并、确认、去重和冷却任务，并把当前 tasks 写入 `tick.event_tasks`。
5. 用全部启用 active tasks 选择 `display_task`，用于 status/overlay/任务表。
副作用：更新 `last_detections/last_observations/last_selected_task`，修改 `EventMemory` 状态，并写事件日志。
失败行为：检测/定位失败时保留既有 memory；全局关闭时停止 active runner。
调用关系：called by `NavigationRuntimeFrameLoop.run()` before task scheduling.

### `EventCoordinator.run_task(self, task_id: str | None, tick)`
行为：只推进由统一导航调度器选中的事件任务，并返回该 handler 输出的 `EventAction`。
算法：
1. 全局事件配置关闭时停止 active runner 并返回 `None`。
2. `task_id is None` 时调用 `EventRunner.update(None, ...)`，用于清理或 requeue。
3. 在启用 active tasks 中查找指定 `task_id`。
4. 未找到时记录 `coordinator run_task missing`，并调用 runner 空更新。
5. 找到任务后调用 `_run_selected_task()`，由 `EventRunner` 启动/继续 handler 并返回 action。
副作用：更新 `last_action`、`EventRunner.active_task` 和 `EventMemory` 中的任务状态。
失败行为：任务不存在或事件关闭时返回 `None`，不会直接触发输入。
调用关系：called by `NavigationTaskController._update_event_task()`。

### `EventPositionStabilizer.update(self, detections: Iterable[EventDetection], registration: FrameRegistration | None, config, now_ms: int) -> list[EventObservation]`
行为：把 detector 输出的局部小地图候选转换为稳定全局事件 observation，是所有小地图事件共用的定位阶段。
算法：
1. 检查 `registration` 是否存在、`valid=True` 且 `frame_origin_global` 不为空；无效时节流记录 `event localization skipped` 并返回空列表。
2. 遍历每个 `EventDetection`，从 event config 读取该事件类型配置；事件 disabled 时跳过。
3. 调用 `_project()`，把 `local_minimap_pos` 按 `frame_origin_global + local_minimap_pos * draw_scale` 投影成全局浮点坐标。
4. 调用 `_merge_sample()`，按 `localization_cluster_radius` 或 `dedupe_radius` 找同类型最近 cluster；同一 `now_ms` 的 cluster 不合并，避免一帧内相近双事件被吞成一个。
5. 新 cluster 记录 `event localization cluster created`；已有/新 cluster 追加 `PositionSample`，并按 `localization_max_samples` 只保留最近样本。
6. 调用 `_stable_observation()` 计算 cluster 方差；样本数未达到 `stable_frames/localization_samples/confirm_frames` 时返回 None。
7. 方差超过 `stable_variance/localization_max_variance` 时节流记录 unstable 并返回 None。
8. 若距离上次发射未超过 `localization_emit_interval_ms`，返回 None，避免同一稳定位置过高频写入 memory。
9. 通过 gate 后更新 `last_emitted_ms`，用加权中心四舍五入为 `global_pos`，并把 sample count、variance、sources 写入 metadata。
10. 所有 detection 处理后调用 `_expire_old_clusters()`，按 `localization_cluster_ttl_ms` 清除久未出现的 cluster。
副作用：写入 `self._clusters`、`self._last_log_ms`、cluster 样本/发射时间，并写事件日志。
失败行为：无有效帧配准时不会产生 observation；`detection.local_minimap_pos` 为空时该 detection 被跳过；event config 缺省时按默认阈值降级。
调用关系：called by `EventCoordinator.observe()`；delegates to `projection.project_detection()`、`clusters.merge_sample()`、`observations.stable_observation()`、`clusters.expire_old_clusters()`。

### `position_stabilizer.projection.project_detection(detection: EventDetection, registration: FrameRegistration) -> tuple[float, float] | None`
行为：执行事件局部小地图坐标到全局地图坐标的纯投影。
算法：
1. 若 detection 没有 `local_minimap_pos` 或 registration 没有 `frame_origin_global`，返回 None。
2. 读取帧全局 origin、局部 x/y 和 `draw_scale`，draw_scale 缺省时用 1.0。
3. 返回 `(origin_x + local_x * scale, origin_y + local_y * scale)`。
副作用：无。
失败行为：坐标字段不可解包时抛出调用方数据契约错误。
调用关系：called by `EventPositionStabilizer._project()`。

### `position_stabilizer.clusters.merge_sample(clusters: list[PositionCluster], detection: EventDetection, global_pos: tuple[float, float], event_config: dict, now_ms: int, should_log) -> PositionCluster`
行为：把一次事件检测投影结果合并进同类型位置 cluster，并维护样本窗口。
算法：
1. 读取 `localization_cluster_radius`，没有则回退 `dedupe_radius`，再回退 90。
2. 调用 `find_cluster()` 在同类型 cluster 中找距离当前 global_pos 最近且未超过半径的 cluster。
3. `find_cluster()` 会跳过 `last_seen_ms == now_ms` 的 cluster，保证同一帧的多个相近图标不会被合并。
4. 找不到 cluster 时创建 `PositionCluster(event_type=...)` 并追加到 clusters，记录创建日志。
5. 构造 `PositionSample`：保存 global/local 坐标、confidence、detected_at_ms、source 和 metadata 副本。
6. 更新 `cluster.last_seen_ms = now_ms`。
7. 按 `localization_max_samples` 截断，只保留最后 N 个样本，N 最小为 3。
8. 日志节流通过时记录样本数、加权中心、方差和最大置信度。
副作用：原地修改 clusters、cluster.samples 和 cluster.last_seen_ms，并写事件日志。
失败行为：detection local 坐标不可索引会抛出异常；调用方应只传有效 `EventDetection`。
调用关系：called by `EventPositionStabilizer._merge_sample()`。

### `position_stabilizer.observations.stable_observation(cluster: PositionCluster, detection: EventDetection, event_config: dict, now_ms: int, should_log) -> EventObservation | None`
行为：把通过稳定条件的 cluster 转换为可进入 `EventMemory` 的 `EventObservation`。
算法：
1. 读取 required samples：`stable_frames` -> `localization_samples` -> `confirm_frames`，最小为 1。
2. 读取最大方差：`stable_variance` -> `localization_max_variance`，默认 1600。
3. 读取 `localization_emit_interval_ms`，默认 700ms。
4. 样本数不足时返回 None。
5. 方差超限时节流记录 unstable，包括 samples、required、variance、max_variance 和 center，然后返回 None。
6. 上次发射时间存在且未超过发射间隔时返回 None。
7. 更新 `cluster.last_emitted_ms`。
8. 计算加权中心和最新 sample，写 `event localization stable` 日志。
9. 构造 `EventObservation`：global_pos 使用中心四舍五入，local_minimap_pos 使用最新 sample，source 拼接 `+wall_registration`。
10. metadata 合并最新 sample metadata，并追加 localization sample count、variance 和去重排序后的 sources。
副作用：写入 `cluster.last_emitted_ms` 并写事件日志。
失败行为：cluster 无样本时不应被调用；否则 latest sample 访问会失败。
调用关系：called by `EventPositionStabilizer._stable_observation()`。

### `PortalEventHandler.update(self, tick, task) -> EventAction | None`
行为：推进 portal 事件状态机，但只返回通用 `EventAction`，不直接执行鼠标或键盘。
算法：
1. 记录状态变化日志。
2. 如果 `state == "wait_result"`，委托 `handler.completion.wait_result_action()` 处理 post-interact settle、teleport completion、timeout 和 forced relocalize wait。
3. 非等待完成阶段先委托 `handler.movement.approach_action()`；玩家无定位时返回 WAIT，距离大于 `arrival_radius` 时返回普通 MOVE_TO。
4. 距离小于到达半径但仍大于 `interact_radius` 时返回 MOVE_TO，并在 metadata 设置 `force_repeat_click=True`，保证近距离继续推动角色靠近传送门点。
5. 若 movement helper 未返回 action，说明已进入交互半径，委托 `handler.interaction.interaction_action()`。
6. interaction helper 先发出一次 `force_click_target=True` 的 MOVE_TO，让 GUI 通过 `MotionController.click_map_target_once()` 点击映射的 portal 点。
7. 等待 `portal_point_click_wait_ms` 后，记录交互时间、玩家位置和小地图环境签名，再返回 `PRESS_KEY("d")`。
8. 按键后状态进入 `wait_result`，后续 update 只走 completion helper。
副作用：更新 handler `state`、`last_interact_ms`、`interact_pos`、`interact_signature`、`portal_point_click_ms`、`teleport_relocalize_requested` 和日志节流字段。
失败行为：无定位时只 WAIT；handler 不直接失败，只有 wait_result 超过 `teleport_timeout_ms` 才返回 FAIL。
调用关系：called by `EventRunner.update()`；delegates to `handler.movement.approach_action()`、`handler.interaction.interaction_action()`、`handler.completion.wait_result_action()`。

### `portal.handler.movement.approach_action(handler, tick, task) -> tuple[EventAction | None, float | None]`
行为：根据玩家到 portal task 的距离决定是否还需要移动。
算法：
1. 玩家全局定位为空时节流记录 `portal waiting localization`，返回 WAIT 和 `distance=None`。
2. 计算 task.global_pos 到 tick.player_global_pos 的欧氏距离。
3. 距离大于 `arrival_radius` 时设状态为 `move_near_event`，记录 `portal move near`，返回 `EventAction.move_to(task.global_pos)`。
4. 距离在到达半径内但大于 `interact_radius` 时继续设状态为 `move_near_event`，记录 final radius 日志。
5. final radius 分支返回 MOVE_TO，并在 metadata 设置 `force_repeat_click=True`。
6. 距离已经进入交互半径时返回 `(None, distance)`，交给 interaction helper。
副作用：可能更新 handler.state，并写节流日志。
失败行为：坐标不可索引会抛出调用方数据契约错误；无定位按 WAIT 降级。
调用关系：called by `PortalEventHandler.update()`。

### `portal.handler.interaction.interaction_action(handler, tick, task, distance: float) -> EventAction`
行为：处理 portal 点点击、点击后等待和按键交互。
算法：
1. 如果 config 残留非 `key` interaction，节流记录 `portal forcing key interaction`，但仍强制按键路径。
2. 如果上次交互时间存在且还在 `post_interact_wait_ms` 内，切到 `wait_result` 并返回 cooldown WAIT。
3. 如果还没有点击过 portal map point，把状态设为 `align_on_portal`，记录 `portal_point_click_ms` 和日志。
4. 首次点击分支返回 `EventAction.move_to(task.global_pos)`，metadata 标记 `force_click_target=True` 和原因。
5. 如果 portal 点点击后等待时间未达到 `portal_point_click_wait_ms`，继续返回短 WAIT。
6. 等待完成后，把状态短暂设为 `interact`，记录 `last_interact_ms`、`interact_pos` 和小地图环境签名。
7. 状态切到 `wait_result`，记录 `portal interaction key`，返回 `EventAction.press_key("d")`。
8. 若状态已经被外部置为 `wait_result`，返回 WAIT，避免重复发按键。
副作用：更新 handler 交互时间、portal 点点击时间、交互位置、环境签名和状态，并写事件日志。
失败行为：raw minimap frame 或 player local pos 缺失时环境签名可为 None，completion helper 后续仍可用位置变化策略。
调用关系：called by `PortalEventHandler.update()`。

### `portal.handler.completion.wait_result_action(handler, tick, task) -> EventAction`
行为：处理 portal 按键后的等待完成阶段，输出 COMPLETE、FAIL 或 forced relocalize WAIT。
算法：
1. 计算从 `last_interact_ms` 到当前 tick 的 elapsed；若还没过 `post_interact_wait_ms`，返回 settle WAIT。
2. 调用 `handler._teleport_completion()`，实际委托 `completion_detector.detect_teleport_completion()`。
3. completion 命中时记录 `portal teleport completed`，调用 `completion_action()` 构造 COMPLETE。
4. completion metadata 总是包含 `entry_pos`、`entry_task_id` 和 `completion_kind="teleport"`，再合并 known-exit、position-changed 或 environment-changed 结果。
5. elapsed 超过 `teleport_timeout_ms` 时记录 timeout 并返回 FAIL。
6. 未完成且未超时，节流记录 `portal waiting teleport completion`。
7. 第一次进入该分支时设置 `teleport_relocalize_requested=True` 并记录 `portal request full-map localization`。
8. 返回 WAIT，metadata 标记 `force_relocalize=True`、`relocalize_reason="portal_wait_result"`、`relocalize_score="event"`。
副作用：可能更新 `teleport_relocalize_requested` 并写事件日志。
失败行为：completion detector 无命中且超过超时时返回 FAIL；否则持续 WAIT，不直接输入。
调用关系：called by `PortalEventHandler.update()`。

### `plan_path_with_optional_anchors(*, wall_map, pathfinder, start_pos, target_pos, explored_map=None, anchors=None, max_anchors: int = 48, max_anchor_factor: float = 1.8, max_anchor_branching: int = 4, min_progress: float = 24.0, probe_distance: float = 84.0) -> AnchorPathResult | None`
行为：在地图全局坐标上优先按用户添加顺序构建有序锚点走廊，供普通导航和事件移动共用。
算法：
1. 将起点、目标和锚点转为整数地图点。
2. `_ordered_corridor_anchors()` 去重并保留 UI 添加顺序，把当前位置投影到锚点折线得到路线进度。
3. 把当前进度之前的锚点视为已路过；把超过当前主目标投影之后的锚点过滤掉，避免锚点抢过必经点、事件或出口。
4. 如果存在前方锚点，只规划 `当前位置 -> 下一个锚点` 的 A* 段并返回 `path_kind="anchor_step"`。
5. 如果下一个锚点 A* 暂不可达，返回两点 `anchor_probe`，让调用方先朝该锚点做约 84 像素短探测。
6. 只有无前方锚点时才直接 A* 到当前主目标并返回 `path_kind="planned"`。
7. 二者都不可用时返回 `None`。
副作用：无真实输入副作用；只调用 `PathFinder.find_path()` 做路径查询。
失败行为：没有墙图/pathfinder、直接路径和锚点路径都不存在时返回 `None`，由调用方执行局部 fallback。
调用关系：called by `MovementExecutor._plan_path()`。

### `NavParametersDialog._auto_estimate_click_radius(self)`
行为：根据已校准的角色屏幕中心和物理屏幕边界估算点击半径，避免 2K 屏幕下半径配置过小。
算法：
1. 校验当前 `NavConfig` 和 `game_screen_center`。
2. 调用 `_screen_physical_bounds_for_center()` 找到包含该中心点的屏幕物理边界。
3. 调用 `estimate_click_radii(game_screen_center, bounds)` 执行纯半径策略。
4. 如果 helper 返回 `None`，显示中心点不在屏幕边界内并退出。
5. 写入最小/最大点击半径控件，触发配置变更信号。
副作用：更新参数面板控件和 `nav_status_label`。
调用关系：called by `nav_auto_click_radius_btn.clicked`。

### `connect_config_bindings(panel, update_value: Callable[..., None], update_text: Callable[..., None]) -> None`
行为：把导航参数控件连接到 dialog 提供的配置更新槽。
算法：
1. 遍历 `VALUE_FIELD_SPECS`，用 `resolve_widget(panel, spec)` 找到控件。
2. 从 `spec.field_path` 取得 `(sub_config_name, attr_name)`。
3. 当 `spec.writer == "checked"` 时连接 `stateChanged`，handler 设置 `to_bool=True`，保持旧 bool 转换语义。
4. 其他 value 字段连接 `valueChanged`，handler 通过 `functools.partial` 预绑定字段路径。
5. 遍历 `TEXT_FIELD_SPECS`，连接 `textChanged`，handler 预绑定字段路径并交给 dialog 的 `_update_config_text_value()`。
副作用：连接 Qt 控件信号；不修改配置对象。
失败行为：控件 attribute 缺失时由 Python 抛出 `AttributeError`，表示 dialog 构造和绑定规格不一致。
调用关系：called by `NavParametersDialog._connect_signals()`。

### `replace_config_value(config: NavConfig, sub_config_name: str | None, attr_name: str, value) -> NavConfig`
行为：按字段路径返回一个新的 `NavConfig`，保留原有不可变更新风格。
算法：
1. 如果 `sub_config_name` 为空，目标对象就是根 `NavConfig`。
2. 如果 `sub_config_name` 非空，读取 `getattr(config, sub_config_name)` 作为嵌套 dataclass。
3. 调用 `dataclasses.replace(target_obj, **{attr_name: value})` 生成更新后的目标对象。
4. 嵌套字段时再次 `dataclasses.replace(config, **{sub_config_name: new_sub_config})` 写回根配置。
5. 根字段时直接返回第 3 步生成的新 `NavConfig`。
副作用：无；不会原地修改旧配置对象。
失败行为：字段路径不存在或目标对象不是 dataclass 时抛出标准 `AttributeError` / `TypeError`。
调用关系：called by `NavParametersDialog._update_config_value()`。

### `parse_config_text_value(text: str) -> tuple[bool, Any]`
行为：解析 HSV 文本输入框里的 Python 字面量，并保留输入未完成时“不更新配置”的旧行为。
算法：
1. 调用 `ast.literal_eval(text)` 解析文本。
2. 解析成功时返回 `(True, value)`。
3. 捕获 `ValueError` 和 `SyntaxError`，返回 `(False, None)`。
副作用：无。
失败行为：无效或未完成输入不抛出，调用方跳过配置更新。
调用关系：called by `NavParametersDialog._update_config_text_value()`。

### `write_config_to_widgets(panel, config: NavConfig) -> None`
行为：把一个 `NavConfig` 快照写入已创建好的导航参数对话框控件。
算法：
1. 遍历 `TEXT_FIELD_SPECS`，用 `config_value(config, spec)` 取配置值并 `setText(str(value))`。
2. 遍历 `VALUE_FIELD_SPECS`，根据 `spec.writer` 选择 `setChecked(value)` 或 `setValue(value)`。
3. 写入只读地图信息：`draw_scale`、`monitor_region` 或 `monitor_logical_center`、`monitor_size`。
4. 如果存在 `game_screen_center`，拆分写入 X/Y 文本框；否则显示 `N/A`。
副作用：修改 Qt 控件显示值；控件信号是否阻断由调用方负责。
失败行为：控件 attribute 缺失时抛出 `AttributeError`。
调用关系：called by `NavParametersDialog.set_config_to_ui()`。

### `estimate_click_radii(center: tuple[int, int], screen_bounds: tuple[int, int, int, int]) -> ClickRadiusEstimate | None`
行为：从角色屏幕中心点和屏幕物理边界计算建议点击半径。
算法：
1. 拆分 `center` 为 `cx/cy`，拆分 `screen_bounds` 为 `left/top/right/bottom`。
2. 计算中心点到四条边的距离，并取最小值为 `safe_radius`。
3. 如果 `safe_radius <= 0`，说明中心点不在可用屏幕范围内，返回 `None`。
4. 取 `max_radius = max(180, min(900, int(safe_radius * 0.70)))`。
5. 取 `min_radius = max(120, int(max_radius * 0.55))`。
6. 返回 `ClickRadiusEstimate(min_radius, max_radius)`。
副作用：无。
失败行为：屏幕中心越界时返回 `None`，不抛异常。
调用关系：called by `NavParametersDialog._auto_estimate_click_radius()`。

### `derive_navigation_wall_layer(wall_layer, *, erode_iterations: int = 1, threshold: int = 50) -> np.ndarray`
行为：从原始建图墙层派生 A* 专用墙层。
算法：
1. 校验 `wall_layer` 不为空。
2. 将输入转换为 `uint8`。
3. 按 `threshold` 二值化，得到只有墙/非墙的导航源图。
4. 当 `erode_iterations > 0` 时，用 3x3 十字核腐蚀墙像素，使视觉墙体变薄、窄通道变宽。
5. 返回新的 `nav_wall` 数组。
副作用：无；不会修改传入的原始 `wall_layer`。
失败行为：`wall_layer is None` 时抛出 `ValueError`。
调用关系：called by `NavigationCore.__init__()` and `NavigationCore.rebuild_navigation_wall_layer()`。

### `NavigationTaskController.update_context(self, context: NavigationUpdateContext) -> NavigationIntent`
行为：消费当前定位、路线、规划资源和事件 memory 快照，统一输出普通路线或事件动作意图。
算法：
1. 从 `context.localization`、`context.route`、`context.planning`、`context.events` 读取 grouped 输入，避免调用方继续传一串松散 kwargs。
2. 路线对象变化时重新 `load_route()` 并保持 controller active。
3. 未 active 时返回 `NONE` intent；定位为空、置信度过低或低置信大跳变时返回 `WAIT`。
4. `observe_localization()` 维护 `trusted_pos/control_pos` 和单调 `route_progress`；若本帧是强制全局模板重定位成功帧，则硬重置 `control_pos`，不做平滑。
5. `CoordinateDiagnostics.record_localization()` 和 `record_navigation_state()` 记录 raw/trusted/control/target/route deviation/frame registration；只有 `NavigationCore` 视觉校验产生的 `visual_mismatch` 或极端 `raw_jump` 会触发强制重定位，路线偏差和近目标卡住只写诊断日志。
6. 若诊断状态机产出 relocalization request，返回 `WAIT` 且在 metadata 标记 `force_relocalize=True`，本帧不点击。
7. `_update_required_progress()` 用距离或路线进度越过判断已完成必经点，完成后清路径和 active task。
8. `NavigationTaskBuilder.build()` 把未完成 required、exit 和 `EventCoordinator.tasks()` 中 runnable 事件合成任务列表。
9. `NavigationTaskScheduler.pick()` 选择当前任务；事件 active 时持锁，静态目标不持锁，允许新事件动态抢占。
10. 任务切换时记录 `nav task transition` 并重置共享 `MovementExecutor`，避免上一任务路径/点击冷却污染下一任务。
11. static required/exit 走 `_update_static_task()`；event 走 `_update_event_task()` 并调用 `EventCoordinator.run_task()`。
12. 返回 `MOVE_MAP/CLICK_SCREEN/PRESS_KEY/WAIT/ARRIVED/FAILED` 之一，由 GUI 层统一执行输入。
副作用：更新定位平滑状态、已完成必经点集合、active task、共享移动执行器、坐标诊断恢复状态和事件 runner 状态。
失败行为：无路径时返回 `WAIT path unavailable`，不会生成穿墙长直线点击；事件上下文缺失时返回 `WAIT`。
调用关系：called by `NavigationRuntimeFrameLoop.run()`。

### `MovementExecutor.step(self, *, task_id: str, current_pos, target_pos, wall_map, pathfinder, explored_map, now_ms: int, lookahead_distance: float, route_context=None, soft_anchors=None, force_repeat_click: bool = False, click_cooldown_ms: int | None = None) -> MovementStep | None`
行为：为当前 required、exit 或 event 地图目标规划/复用路径，选出本帧 lookahead 子目标和是否应点击。
算法：
1. 标准化当前位置和目标坐标。
2. facade 委托 `movement.pipeline.movement_step()`，再由它调用 `executor._ensure_path()`；旧私有方法保留但实际转发到 `movement.path_maintenance.ensure_movement_path()`。
3. `ensure_movement_path()` 根据目标变化、路径为空、锚点段到达、离路偏差、fallback 过期或强制重规划标记判断是否重规划。
4. 需要规划时，`movement.path_planner.plan_movement_path()` 优先从 `RouteContext.corridor_anchors()` 获取当前位置到当前任务目标之间的前方锚点。
5. 若有前方锚点，调用 `plan_path_with_optional_anchors()` 只规划到下一个锚点；若无锚点则直接 A* 到当前任务目标。
6. 如果 A* 失败，调用 `movement.recovery.local_probe()` 生成玩家附近短距离 `fallback` probe，而不是直接点击远端目标。
7. 将当前位置投影到当前路径，沿累计距离向前插值 `lookahead_distance` 得到 `subgoal`。
8. 如果当前路径终点接近但仍未到达锚点或 planned 目标，切换到 exact path-goal click，设置 `force_click_target=True`，并把有效冷却提升到至少 650ms。
9. 若没有处于 final-goal settle 窗口，调用 `movement.recovery.is_movement_stuck()` 按路径投影进度判断卡住。
10. 卡住且恢复次数未耗尽时，调用 `movement.recovery.recovery_probe()` 朝 active anchor/fallback path goal 生成恢复子目标；恢复次数耗尽时设置 `force_replan=True`。
11. 根据 click cooldown、`force_repeat_click`、active goal pending、上次点击目标距离和离路偏差决定 `should_click`。
12. 返回包含 path、subgoal、path_kind、deviation、force_click_target 的 `MovementStep`。
副作用：更新缓存路径、路径终点、子目标、重规划时间、fallback probe index、进度窗口、恢复次数、final goal settle 状态。
失败行为：路径不可用或投影失败返回 `None`，调用方本帧不输入。
调用关系：called by `NavigationTaskController._update_static_task()` and `_update_event_task()`。

### `movement.path_maintenance.ensure_movement_path(executor, *, task_id: str, current_pos, target_pos, wall_map, pathfinder, explored_map, now_ms: int, route_context=None, soft_anchors=None) -> None`
行为：维护 `MovementExecutor` 的缓存路径，在目标变化、路径失效、偏离路径或 fallback 过期时重规划。
算法：
1. 标准化目标坐标，并用 12px 距离阈值判断目标是否变化。
2. 如果当前路径为空、少于两个点、被 `force_replan` 标记或目标变化，则直接需要规划。
3. 如果是 `anchor_step/anchor_probe/fallback` 且已到达当前 path goal，则需要规划下一段。
4. 把当前位置投影到当前路径；投影失败或 `distance_to_path` 超过 `path_deviation_threshold` 时需要重规划。
5. fallback 路径超过 650ms 仍在使用时需要重规划，避免短探测路径长期卡住。
6. 如果刚规划过且目标未变化，260ms 内跳过，避免每帧重复 A*。
7. 调用 `executor._plan_path()` 获取路径、累计长度和 path kind，并写回 executor 的 path/path_lengths/target/path_goal/path_kind 等状态。
8. 重置 subgoal、progress、recovery、final-goal 状态，并写 `nav movement planned` 日志。
副作用：写入 executor 路径状态和导航日志。
失败行为：无异常抛出；若 planner 返回 fallback，也作为有效路径写入。
调用关系：called by `movement.pipeline.movement_step()` through `MovementExecutor._ensure_path()`。

### `movement.path_planner.plan_movement_path(executor, current_pos, target_pos, wall_map, pathfinder, explored_map, *, route_context=None, soft_anchors=None)`
行为：为 movement executor 生成 anchor-aware A*/fallback 路径。
算法：
1. 把 current/target 转为整数地图点。
2. 调用 `executor._anchors_for_path()`，优先从 `RouteContext.corridor_anchors()` 获取当前到目标之间的前方 guide anchors，否则使用 `soft_anchors`。
3. 如果 `wall_map` 和 `pathfinder` 可用，调用 `plan_path_with_optional_anchors()`，让 routing 层决定 `anchor_step/anchor_probe/planned`。
4. 若 anchor-aware 结果有 path，记录 `executor.path_anchor_points`，删除共线点，单点路径补上真实 target，并返回累计长度。
5. 若没有 anchors 且直接 A* 可用，调用 `pathfinder.find_path()` 规划当前到目标。
6. 直接 A* 成功时清空 anchor points，删除共线点，单点路径补上目标，并返回 `path_kind="planned"`。
7. 全部规划失败时清空 anchor points，调用 `executor._local_probe()` 生成两点 fallback path。
副作用：写入 `executor.path_anchor_points`。
失败行为：不会返回 `None`，最差返回 fallback 两点路径。
调用关系：called by `MovementExecutor._plan_path()`。

### `movement.recovery.is_movement_stuck(executor, current_progress: float, now_ms: int) -> bool`
行为：根据路径投影进度判断 movement 是否卡住。
算法：
1. 如果还没有进度基线，则写入当前 progress/time，返回 `False`。
2. 如果当前进度比基线至少增加 `min_progress_delta`，刷新基线并清零恢复次数，返回 `False`。
3. 如果进度不足且 `now_ms - last_progress_ms >= progress_timeout_ms`，返回 `True`。
副作用：更新 executor 的 progress baseline 和 recover attempts。
失败行为：无异常处理；入参 progress/time 由调用方保证可转数值。
调用关系：called by `movement.pipeline.movement_step()` through `MovementExecutor._is_stuck()`。

### `NavigationTaskScheduler.pick(self, *, tasks: list[NavigationTask], player_pos, route_context, active_task_id: str | None = None, manual_event_only: bool = False) -> NavigationTask | None`
行为：在静态路线目标和动态事件目标中选择当前应处理任务。
算法：
1. 过滤出 `PENDING/MOVING/EXECUTING` 任务；手动事件测试时只保留 event。
2. 如果 active task 是 event 且仍 runnable，直接返回它，保证事件执行到终态。
3. 普通模式先找下一个未完成 required，若没有则选 exit 作为 base target。
4. 计算玩家路线进度与 base target 进度，只把位于两者之间或略靠前的 event 纳入候选。
5. 用“前方路线进度差、priority、欧氏距离、task id”排序，选择最靠近当前前进方向的任务。
6. 任务变化时写 `nav task selected` 日志。
副作用：只维护 `_last_selected_id` 以减少重复日志。
失败行为：无 runnable 任务时返回 `None`。
调用关系：called by `NavigationTaskController.update_context()`。

### `PathFinder._build_obstacle_map(self, wall_map, grid_w, grid_h, explored_map=None)`
行为：把调用方传入的导航障碍层转换为 A* 使用的低分辨率障碍图。
算法：
1. 将输入障碍层转为 `uint8` 并阈值化。
2. 如果 `wall_shrink_iterations > 0`，再次用 `MORPH_CROSS` 腐蚀墙像素；当前默认值为 0，避免和 `nav_wall_layer` 派生阶段重复变薄。
3. 将障碍图 resize 到 A* 网格尺寸。
4. 再阈值化得到 `binary_map`。
5. 如果传入 `explored_map`，把已探索区域 resize 到同一网格，`explored_map==0` 的网格强制设为障碍。
6. 如果 `safety_margin > 0`，按降采样后的半径膨胀障碍；当前默认 0。
副作用：无。
失败行为：输入图形状不合法时 OpenCV resize/threshold 异常向上传播。
调用关系：called by `PathFinder.find_path()`。

### `PathFinder._clear_start_area(self, obstacle_map, start_grid)`
行为：清空 A* 起点附近小圆，容忍玩家定位点压在线条/墙边。
算法：
1. 将 `start_clear_radius` 按 `downsample_factor` 转为网格半径。
2. 半径小于等于 0 时直接返回原障碍图。
3. 复制障碍图，裁剪起点附近局部窗口。
4. 在局部窗口内画圆形 mask，并把 mask 覆盖区域置为可走。
5. 返回清空后的障碍图副本。
副作用：无。
失败行为：窗口越界或空窗口时返回复制后的障碍图。
调用关系：called by `PathFinder.find_path()`。

### `PathFinder._astar(self, grid, start, end)`
行为：在低分辨率障碍图上执行 8 方向 A*。
算法：
1. 从 `start` 开始，用 `g_score + heuristic` 的最小堆扩展节点。
2. 邻居支持上下左右和四个对角方向。
3. 若目标邻居本身是障碍，直接跳过。
4. 若是对角移动，还要额外检查两侧正交相邻格；任一侧是障碍就禁止斜穿角，避免从墙角之间硬挤过去。
5. 使用直行 `1.0`、斜走 `1.414` 的代价累计；若有 clearance cost map，则乘以当前格与邻居格软代价平均值。
6. 直到到达终点或无路可走，返回网格路径或 `None`。

### `MapStitcher._merge_frame_weighted(self, save_mask, fog_mask, h, w, px, py, force=False)`
行为：把当前帧的墙体层与地面/禁区候选层融合进全局地图。
算法：
1. 根据当前全局坐标和玩家在小地图中的相对位置，计算当前帧在画布上的 ROI。
2. 对墙体像素累积 `weight_layer`，权重大于阈值后再写入 `wall_layer`，避免单帧噪声污染地图。
3. 从 `fog_mask` 提取精准可见区域；像素数足够时，将其写入 `fog_layer` 并作为本帧 `explored_map` 的更新依据。
4. 只有当地面/迷雾提取几乎为空时，才回退到旧的“整块截图矩形” explored 逻辑，避免某些地图完全不出背景。
5. 强制把墙体也并入 `explored_map`，保证裁剪和导航不会把边界丢掉。
副作用：更新 `weight_layer`、`wall_layer`、`fog_layer`、`explored_map`、`canvas`。
失败行为：ROI 裁剪为空时返回 `False`；内容太相似且非 force 时跳过并增加 redundant counter。
调用关系：called by `MapStitcher._place_first_frame()` and `mapping.frame_pipeline.add_frame_to_stitcher()`；implemented by `mapping.weighted_merge.merge_frame_weighted()`。

### `MapStitcher.default_params(cls, *, canvas_size=6000, draw_scale=2.0, wall_close_kernel_size=3)`
行为：在不实例化 stitcher、也不分配画布数组的情况下返回完整参数字典。
算法：
1. 写入 frame registration、关键帧、融合权重、落图质量门和精准可见区默认值。
2. 对 `canvas_size`、`draw_scale` 和 `wall_close_kernel_size` 做 int/float/最小值规范化。
3. 返回可由上层复制、覆盖并持久化的全新字典。
副作用：无；不会分配 NumPy 画布。
失败行为：结构参数不能转换为数字时传播 `TypeError`/`ValueError`。
调用关系：called by `Poe2MonitorConfig` defaults、`Poe2StitchingSession` 和 PoE2 高级设置适配器。

### `MapStitcher.reset(self)`
行为：清空地图和帧状态，同时保留完整 stitcher 参数契约。
算法：
1. 先通过 `get_params()` 快照当前结构参数和运行参数。
2. 用当前 canvas size、draw scale 和 wall close kernel 重新初始化数组/状态。
3. 通过 `set_params()` 恢复 conf/keyframe/weight/quality/visibility 参数。
副作用：重新分配全部画布数组，清除地图、当前位置历史和统计。
失败行为：大画布内存不足时传播 NumPy 分配异常。
调用关系：called by mapping lifecycle/reset callers；PoE2 session 使用自己的 `_new_stitcher()` 保持实例隔离。

### `MapStitcher.add_frame(self, img, match_mask, save_mask, fog_mask, raw_gray=None, player_pos=None)`
行为：接收一帧小地图识别结果，执行 keyframe/F2F 配准、低质量过滤和落图。
算法：
1. facade 调用 `mapping.frame_pipeline.add_frame_to_stitcher(self, ...)`，并把自身作为状态拥有者传入。
2. `frame_pipeline` 增加 `stats["total_frames"]`，解析玩家在 minimap 内局部坐标。
3. 首帧时调用 `_place_first_frame()`，把 scaled save/fog masks 放到 canvas 中心，设置 keyframe/prev frame 和当前位置。
4. 非首帧优先用 keyframe mask 和当前 match mask 做 phase displacement。
5. keyframe 匹配质量超过 `keyframe_thresh` 且跳变小于 100px 或质量很高时接受 anchor。
6. anchor 接受时从 keyframe position 和 displacement 更新 `current_x/current_y`。
7. anchor 不接受时 fallback 到 previous frame；F2F 质量低或位移超过 50px 时记失败。
8. F2F 成功且当前 feature count 足够时更新 keyframe；否则只保持 previous frame 链路。
9. 匹配成功但质量低于 `draw_quality_gate` 时只更新 previous frame，不落图，避免污染全局地图。
10. 质量通过后准备 scaled save/fog masks，调用 `_merge_frame_weighted()` 写入 map layers。
11. 更新 previous mask/pos、match quality、successful/failed stats 和 match rate。
副作用：写入 `MapStitcher` 当前坐标、keyframe/prev frame、map layers 和 stats。
失败行为：当前实现通常返回 `True`，即使配准失败也会更新 stats；首帧日志含 emoji，在 GBK stdout 下需要 `PYTHONIOENCODING=utf-8` 才能直接 smoke。
调用关系：called by `gui/modes/mapping_widget.py` through shared `AppContext.stitcher`。

### `MapStitcher.get_enhanced_map(self, margin=500)`
行为：返回绘图模式显示用的彩色全局图。
算法：
1. 以 `explored_map`/`wall_layer` 的非零包围盒为基础自动裁剪。
2. `explored_map` 显示为灰色有效区域。
3. `fog_layer` 继续保存在地图包中，但默认不直接渲染到 UI。
4. `wall_layer` 显示为白色墙体并覆盖在最上层。

### `HSVRecognizer.extract_combined(self, img, player_pos=None)`
行为：提取用于拼接/导航的组合特征。
算法：
1. `HSVRecognizer.extract_combined()` 保留旧入口，内部委托 `hsv.combined.extract_combined_masks()`。
2. 先通过 `extract_walls()` 和 `extract_fog()` 得到保存用 wall/fog mask。
3. 对 wall 预处理图转灰度并用 Canny 生成 edges。
4. 若 `sat_filter_enabled`，`dynamic_color_mask()` 从原始图 HSV 饱和度生成动态彩色区域 mask；`sat_filter_radius > 0` 时只在玩家周围生效。
5. 对 dynamic mask 做一次小核膨胀，并从 wall/fog/edges 中剔除，避免彩色事件图标和玩家技能污染静态地图特征。
6. 按 `player_clear_radius` 在玩家位置或图像中心挖圆，进一步压制玩家脚下和近身特效。
7. `weighted_match_mask()` 按 `wall_weight/edge_weight` 把 `wall_mask` 和 `edges` 融合成配准用 `match_mask`。
8. 返回 `(match_mask.astype(np.uint8), wall_mask, fog_mask)`。
副作用：会原地清理本次生成的 wall/fog/edges mask，不写 recognizer 状态。
调用关系：called by `MappingWidget.capture_and_process()` and `NavigationCore.localize()`。

### `HSVRecognizer.extract_walls(self, img, is_processed=False)`
行为：提取保存/定位共用的二值 wall mask。
算法：
1. facade 委托 `hsv.masks.extract_wall_mask()`。
2. `enable_wall=False` 时返回全零 mask。
3. 非 processed 输入先走 `hsv.preprocessing.preprocess_for_wall()`。
4. `transparent_mode=True` 时，`compute_transparency_score()` 计算 `(V - S * penalty)` 与 TopHat 结构 score 的最小值，再按 `trans_wall_thresh` 二值化。
5. 透明模式下做小核 close，并用 `filter_small_components(min_area=20)` 去掉小噪点。
6. 非透明模式下转 HSV 后按 `wall_hsv_min/max` inRange，随后 close、median blur、Gaussian blur、threshold 和小连通域过滤。
副作用：无持久状态写入。
调用关系：called by `extract_combined_masks()` and color-picker/debug flows。

### `hsv.params.apply_recognizer_params(recognizer, params) -> None`
行为：把 GUI/配置层传入的 HSVRecognizer 参数字典应用到 recognizer 实例。
算法：
1. 逐项检查 `wall_hsv_min/max`、`fog_hsv_min/max`、`player_hsv_min/max` 是否存在，存在时转为 `numpy.array` 写回 recognizer。
2. 逐项应用 wall/fog、CLAHE、deepen、gamma、TopHat、sat filter 等布尔开关；缺失键保持旧值。
3. 更新 `clahe_clip` 时直接调用既有 `_clahe.setClipLimit()`；更新 `clahe_grid` 时重建 `cv2.createCLAHE()`，确保 tile grid 尺寸同步。
4. 应用 deepen、blue boost、gamma、TopHat、transparent、sat filter、player clear radius、权重和 Canny 阈值等数值参数。
5. `player_clear_radius` 强制转为非负整数；`kernel_small_size` 和 `kernel_medium_size` 存在时重建对应全 1 morphology kernel。
副作用：原地写入 `recognizer` 实例字段，并可能重建 `recognizer._clahe`、`kernel_small`、`kernel_medium`。
失败行为：未做类型校验；错误类型会在 `numpy.array`、`int()` 或 OpenCV CLAHE/kernel 后续使用处暴露。
调用关系：called by `HSVRecognizer.set_params()`，间接 called by GUI 参数面板和导航参数加载流程。

### `hsv.preprocessing.preprocess_for_wall(recognizer, img)`
行为：生成 wall mask 提取前的增强 BGR 图，服务透明墙体和普通 HSV 墙体识别。
算法：
1. 若 `gamma_enabled`，构建 0-255 查找表并通过 `cv2.LUT()` 调暗/校正输入图。
2. 对输入做 3x3 Gaussian blur，降低局部噪声对 HSV/TopHat 的影响。
3. 若 `clahe_enabled`，转 LAB，对 L 通道应用 recognizer 当前 `_clahe`，再转回 BGR；否则直接使用 blur 结果。
4. 若 `tophat_enabled`，用 `tophat_kernel_size` 的矩形结构元素对增强图做 MORPH_TOPHAT，并把高亮结构加回图像。
5. 尝试用第 40 和 99 百分位做线性拉伸；若 OpenCV/numpy 输入异常或百分位无有效跨度，保持当前图。
6. 若 `deepen_enabled`，用 `convertScaleAbs(alpha=deepen_factor, beta=-60)` 加深，再按 `blue_boost` 放大 B 通道。
7. 返回增强后的 BGR 图，不修改 recognizer 参数。
副作用：无持久状态写入。
失败行为：百分位计算异常被吞掉并降级为未拉伸图；OpenCV 颜色空间和 LUT 错误会传播。
调用关系：called by `HSVRecognizer._preprocess_for_wall()`、`HSVRecognizer.preprocess_image()`、`hsv.masks.extract_wall_mask()`、`hsv.combined.extract_combined_masks()`。

### `hsv.combined.dynamic_color_mask(recognizer, img, player_pos=None)`
行为：识别运行时彩色动态区域，用于从 wall/fog/edge 配准特征中剔除事件图标、技能光效和玩家周边颜色噪声。
算法：
1. 将原始 BGR 小地图转 HSV，并取 S 通道。
2. 用 `sat_filter_thresh` 生成高饱和度布尔 mask。
3. 若 `sat_filter_radius > 0`，创建同尺寸半径 mask：有 `player_pos` 时以玩家坐标为圆心，否则以图像中心为圆心。
4. 将高饱和度 mask 与半径 mask 相交，把过滤范围限制在玩家周边。
5. 转为 0/255 uint8 后，用 `kernel_small` 膨胀 1 次，扩大动态颜色清理范围。
6. 返回布尔 mask，供调用方原地清除 wall/fog/edges 像素。
副作用：无持久状态写入；调用方会依据返回 mask 修改本帧临时 mask。
失败行为：输入不是 BGR 图像时 OpenCV 转 HSV 抛错；`player_pos` 超出图像范围时圆形 mask 可能为空或部分落在图外。
调用关系：called by `hsv.combined.extract_combined_masks()`。

### `event_icon_probe.match_template(frame: np.ndarray, template: np.ndarray, mask: np.ndarray | None, scales: list[float], top_k: int, threshold: float) -> list[MatchHit]`
行为：对单个事件图标模板执行多尺度匹配，返回超过阈值的候选。
算法：
1. 将原始小地图帧转换为灰度图，并用 Canny 提取边缘。
2. 遍历 `scales`，按比例缩放模板和可选 alpha mask。
3. 对灰度模板执行 `cv2.matchTemplate(..., TM_CCOEFF_NORMED)`。
4. 如果模板边缘足够多，再执行边缘模板匹配，并按 `gray*0.72 + edge*0.28` 合成分数。
5. 如果存在有效 alpha mask，追加 masked `TM_CCORR_NORMED` 响应，并与灰度响应加权后取更高分。
6. 用 `_response_hits()` 按局部抑制半径提取 top-k 候选，避免同一图标重复输出多个相邻峰值。
7. 按 `score` 降序返回候选。
副作用：无。
调用关系：called by `event_icon_probe.main()`。

### `event_icon_probe.merge_hits(hits: list[MatchHit], top_k: int, center_radius: float = 12.0) -> list[MatchHit]`
行为：把多个模板或多个尺度产生的候选按图标中心去重。
算法：
1. 按 `score` 从高到低遍历所有候选。
2. 计算当前候选中心与已保留候选中心的欧氏距离。
3. 若距离小于动态半径，视为同一事件图标，只保留较高分候选。
4. 保留数量达到 `top_k` 后停止。
副作用：无。
调用关系：called by `event_icon_probe.main()`。

### `event_icon_probe.main() -> int`
行为：读取地图配置，抓取 raw minimap frame，加载一个或多个事件模板，输出匹配结果和调试图片。
算法：
1. 解析 `--map-folder`、可重复 `--template`、阈值、尺度、输出目录等参数。
2. 从 `config.json` 读取 `monitor_region` 或 `monitor_logical_center/monitor_size`，结合 DPR 得到物理截图矩形。
3. 用 `SquareScreenCapture.capture()` 抓取原始小地图帧并保存。
4. 若提供模板，对每个模板调用 `match_template()`，再用 `merge_hits()` 去重。
5. 保存带框 debug 图；若没有候选超过阈值，仍打印每个模板的最佳低分候选，区分“阈值过高/图标不在视野”和“截图失败”。
副作用：写入 `debug/event_probe/...` 图片；初始化和关闭屏幕捕获后端。
调用关系：standalone CLI。

### `portal_screen_probe.build_blue_glow_mask(frame: np.ndarray) -> np.ndarray`
行为：从主游戏画面中提取传送门可能使用的蓝/青/紫发光区域。
算法：
1. 将 BGR 帧转换为 HSV。
2. 分别对 cyan、blue、violet 三段 HSV 范围做 `cv2.inRange()`。
3. 合并三段 mask，保留传送门、蓝色 UI、冰蓝怪物高光等全部候选发光区域。
4. 用 3x3 椭圆开运算去孤立噪点。
5. 用 11x11 椭圆闭运算连接被纹理切断的发光弧线，再轻微膨胀。
副作用：无。
调用关系：called by `portal_screen_probe.detect_portal_candidates()`。

### `portal_screen_probe.detect_portal_candidates(frame: np.ndarray, min_area: float, max_area_ratio: float) -> tuple[list[PortalCandidate], np.ndarray]`
行为：把蓝紫发光 mask 转换为候选框并计算传送门相似分。
算法：
1. 调用 `build_blue_glow_mask()` 得到二值 mask。
2. `cv2.findContours()` 查找外轮廓。
3. 过滤面积太小、bbox 占整帧比例太大、宽高太小或宽高比极端的轮廓。
4. 计算轮廓面积、bbox、中心点、发光填充率、圆度和宽高比。
5. 用面积分、发光分、形状分和圆度分加权得到 `score`。
6. 按分数降序返回候选和 mask。
副作用：无。
调用关系：called by `portal_screen_probe.main()`。

### `portal_screen_probe.is_strict_portal_candidate(candidate: PortalCandidate, args: argparse.Namespace) -> bool`
行为：把宽松视觉候选收紧为可执行事件确认候选。
算法：
1. 要求 `score >= threshold`。
2. 要求 bbox 宽高均超过资产阈值，排除 UI 小图标。
3. 要求轮廓面积超过阈值，排除小蓝色亮点。
4. 要求圆度、发光填充率和宽高偏斜满足阈值，排除蓝色机关、怪物冰蓝高光和长条 UI。
副作用：无。
调用关系：called by `portal_screen_probe.draw_candidates()` and `portal_screen_probe.main()`。

### `RapidOcrProvider.__init__(self, *, engine_options: Mapping[str, Any] | None = None, backend_factory: Callable[[], Any] | None = None) -> None`
行为：建立一个可复用但尚未启动的本地 OCR provider。`engine_options` 仅在以后创建实际 ONNX 引擎时使用；`backend_factory` 仅用于应用替换或测试。

算法：
1. 验证可选 `engine_options` 是 mapping，且可选 factory 可调用；不导入 RapidOCR，也不读取模型。
2. 防御性复制 engine 参数，保存 factory，令 `_backend=None`。
3. 创建一个 provider-local `RLock`，保证首次初始化和会改变 RapidOCR 阈值状态的一次调用不会交叉执行。

副作用：仅分配实例内存和锁；不会访问文件、网络、屏幕或 ONNX。

失败行为：非 mapping 配置抛 `TypeError`；非 callable factory 抛 `TypeError`。

调用关系：由应用 composition 创建；随后由 `recognize()` 使用其缓存字段。

### `RapidOcrProvider.recognize(self, frame: FrameContext, parameters: Mapping[str, Any] | None = None) -> tuple[OcrSpan, ...]`
行为：把一张完整帧或指定 ROI 输入缓存的 RapidOCR，并把原始文字四边形规范化为原始帧坐标系中的 `OcrSpan`。

算法：
1. 验证 `frame`，复制 per-call 参数；依次解析 `roi`、语言标签和 `backend_options`，拒绝未声明的参数名。
2. 调用 `_crop_to_roi()`；无 ROI 时保留原图与 `(0,0)` 偏移，存在 ROI 时得到切片、实际裁剪原点和裁剪元数据。
3. 在 provider 锁内调用 `_get_backend_locked()`，随后执行 `backend(image, **backend_options)`；锁避免 RapidOCR 的可变 `text_score/box_thresh` 状态在并发帧间串扰。
4. 通过 `_split_backend_output()` 读取 `(rows, elapsed_seconds)`；`None` rows 表示没有文字。
5. 对每个返回行调用 `_to_ocr_span()`，用 ROI 偏移恢复四边形和 bbox，保留文字、置信度、时间和 provider 元数据。

副作用：首次调用可能导入并初始化 ONNX 模型；随后只调用常驻模型，不执行点击、映射或配置持久化。

失败行为：参数或 ROI 不合法抛 `TypeError`/`ValueError`；缺依赖抛 `ProviderUnavailableError`；推理或返回结构异常抛 `ProviderError`。这些错误由上层 `DetectorRunner` 按算法实例隔离。

调用关系：被 `ProviderBackedOcrDetector.detect()` 间接调用；调用 `_pop_roi()`、`_pop_language()`、`_pop_backend_options()`、`_crop_to_roi()`、`_get_backend_locked()`、`_split_backend_output()` 和 `_to_ocr_span()`。

### `RapidOcrProvider._get_backend_locked(self) -> Any`
行为：在已持有 provider 锁时返回唯一可调用 OCR 引擎。

算法：
1. 若 `_backend` 已存在，直接返回，以避免每帧重新加载模型。
2. 优先调用 injected `backend_factory`，否则调用 `_create_default_backend()`。
3. 验证 factory 返回可调用对象，缓存并返回。

副作用：第一次成功时写入 `_backend`；不重复初始化。

失败行为：factory 结果不可调用时抛 `ProviderUnavailableError`；factory 自身错误保持原始异常语义。

调用关系：仅由 `recognize()` 在锁内调用。

### `RapidOcrProvider._create_default_backend(self) -> Any`
行为：按需导入 optional package 并构建 `rapidocr_onnxruntime.RapidOCR`。

算法：
1. 用动态导入取得 `rapidocr_onnxruntime.RapidOCR`，避免 package import 时成为强制依赖。
2. 缺模块或缺导出时，将 `ImportError`/`AttributeError` 包装为带安装提示的 `ProviderUnavailableError`。
3. 以构造时复制的 `engine_options` 创建模型；初始化异常也包装为 `ProviderUnavailableError`。

副作用：首次路径会加载 OCR/ONNX 运行时及模型资源。

调用关系：由 `_get_backend_locked()` 在没有 injected factory 时调用。

### `rapidocr_models.RapidOcrModelSpec`
行为：不可变的命名 OCR 识别模型清单项，保存稳定 `model_id`、展示文本、ONNX 文件名、下载地址、SHA-256 和推荐的 RapidOCR 构造选项。当前目录只声明 `rapidocr.ppocr-v6-multilingual-small`，用于同时覆盖简体和繁体中文的 PP-OCRv6 small 识别资产。

外部依赖：只依赖 `providers.contracts.ProviderUnavailableError`；不导入 `rapidocr_onnxruntime`、不下载、不创建 ONNX 会话。

注意事项：`file_name` 不能包含目录；SHA-256 在构造期验证为 64 位十六进制。模型二进制不在 Git，资源目录由 `.gitignore` 排除。

### `rapidocr_models.get_rapidocr_model_spec(model_id: str) -> RapidOcrModelSpec`
行为：把非空模型 ID 映射到一项清单。

算法：
1. 拒绝非字符串或空白 ID。
2. 从只读 `_MODEL_SPECS` 取项。
3. 未知 ID 时列出可用 ID 并抛 `ValueError`。

副作用：无 I/O。

失败行为：无效或未知模型是配置错误，抛 `ValueError`；不会退回到默认模型。

调用关系：由 installer 和 `resolve_rapidocr_engine_options()` 调用。

### `rapidocr_models.verify_rapidocr_model_file(spec: RapidOcrModelSpec, model_path: str | Path) -> Path`
行为：仅在局部 ONNX 文件存在、可读取且 SHA-256 与清单一致时，返回绝对路径。

算法：
1. 验证 spec 类型并将输入路径规范为绝对路径。
2. 文件不存在时生成包含 installer 命令的 `ProviderUnavailableError`。
3. 分块读取文件，累积 SHA-256。
4. 与清单摘要比较；不一致时抛明确 checksum 错误，否则返回已验证路径。

副作用：只读模型文件。

失败行为：路径无效时抛 `ValueError`；缺失、无法读取或摘要不符时抛 `ProviderUnavailableError`；没有网络、替换或推理副作用。

调用关系：由 resolver 和 installer 在安装前后调用。

### `rapidocr_models.resolve_rapidocr_engine_options(model_id: str, model_directory: str | Path, *, overrides: Mapping[str, Any] | None = None) -> dict[str, Any]`
行为：把一个命名且完整的本地模型转换为可传给 `RapidOcrProvider` 的独立构造参数字典。

算法：
1. 解析 spec 并复制可选 overrides。
2. 拒绝 `rec_model_path` override，避免调用方绕过所选模型的摘要检查。
3. 用 `model_directory / spec.file_name` 调用 `verify_rapidocr_model_file()`。
4. 复制 spec 推荐线程选项，合并其余 overrides，最后写入验证后的绝对 `rec_model_path`。

副作用：只读模型文件；返回的新字典不共享调用方或清单的 mapping。

失败行为：未知模型、错误 override 类型或试图重写模型路径抛 `ValueError`/`TypeError`；缺文件/损坏文件抛 `ProviderUnavailableError`。不会加载 RapidOCR、文本或游戏配置。

调用关系：由应用 composition 创建 `RapidOcrProvider(engine_options=...)`，也由可选真实模型测试调用。

### `utils.install_perception_ocr_model.install_rapidocr_model(model_id: str, destination: str | Path, *, timeout_seconds: float = 60.0, opener: Callable[..., _ReadableResponse] = urlopen) -> Path`
行为：显式安装一项 OCR 模型资源，确保不完整下载永远不成为推理资源。

算法：
1. 用 `get_rapidocr_model_spec()` 解析模型，验证正 timeout，并建立目标目录。
2. 已存在的最终文件先经 `verify_rapidocr_model_file()` 验证；正确则立即返回，错误文件保留等待安全替换。
3. 在同一目标目录创建 `.part` 临时文件，按 1 MiB 分块从清单 URL 写入。
4. 校验临时文件 SHA-256；通过后用 `os.replace()` 原子替换最终文件，再次验证并返回。
5. 任意异常路径删除仅由本次调用创建的临时文件；旧最终文件未被提前删除。

副作用：显式 CLI/工具调用时创建目录、下载网络字节、创建/删除临时 ONNX 文件并原子替换最终模型。正常 `core.perception` 导入和每帧识别不调用它。

失败行为：无效目标/timeout 抛 `ValueError`；下载、响应数据、摘要或安装路径问题包装或传播为 `ProviderUnavailableError`，没有重试。调用者需要自行重试。

调用关系：由其 `main()` 命令行入口调用；单元测试以注入 in-memory opener 调用。

### `rapidocr._pop_roi(values: dict[str, Any]) -> tuple[float, float, float, float] | None`
行为：从可变 per-call 参数中移除并验证 ROI。

算法：接受 `BoundingBox`、带 `left/top/width/height` 的 mapping 或四项 sequence；转换为有限 float；只接受正宽高。缺字段、错误长度、非数字、无穷值和非正尺寸均被拒绝。

副作用：从传入的临时参数字典删除 `roi`；原 profile 参数不受影响。

失败行为：类型不支持抛 `TypeError`，内容不合法抛 `ValueError`。

调用关系：仅由 `recognize()` 调用，结果交给 `_crop_to_roi()`。

### `rapidocr._pop_language(values: dict[str, Any]) -> str | None` 与 `rapidocr._pop_backend_options(values: dict[str, Any]) -> dict[str, Any]`
行为：提取可选语言结果标签和可安全转发给 RapidOCR 的调用参数。

算法：语言 `None` 保持缺省，其余值转字符串并拒绝空值；`backend_options` 必须是 mapping，并复制后返回，使一次调用不能修改下一次调用或持久 profile。

副作用：从临时参数字典移除对应键。

失败行为：空语言抛 `ValueError`，非 mapping backend options 抛 `TypeError`。

调用关系：仅由 `recognize()` 调用；语言写入 `_to_ocr_span()`，options 传给 backend。

### `rapidocr._crop_to_roi(image: Any, roi: tuple[float, float, float, float] | None) -> tuple[Any, tuple[float, float], dict[str, int] | None]`
行为：为 OCR 截取一个安全、可追溯的局部图像，并返回将局部点恢复到全图的偏移。

算法：无 ROI 时直接返回原图和零偏移；否则从 array `shape` 取得图像边界，以 floor/ceil 将 float ROI 覆盖的像素范围规范化，裁剪到有效图像区域，检查相交面积后用二维切片取图。输出包含实际 `left/top/width/height`，而不是越界的请求值。

副作用：无；切片视图不写回原图。

失败行为：非 array-like 输入、空图、不可切片图像、或不与图像相交的 ROI 抛明确错误。

调用关系：由 `recognize()` 调用；其偏移传递至 `_to_ocr_span()`。

### `rapidocr._split_backend_output(raw_output: Any) -> tuple[Any, tuple[float, ...]]`
行为：验证 RapidOCR 返回的 `(result_rows, elapsed_seconds)` 形状并规范化耗时元数据。

算法：要求二元 tuple；结果 rows 可以为 `None`；耗时可为 `None` 或有限、非负的 numeric sequence，并转成 float tuple。

副作用：无。

失败行为：错误 tuple 结构、非 sequence 耗时、非数值、NaN/无穷/负耗时抛 `ProviderError`。

调用关系：由 `recognize()` 调用；归一化耗时传给 `_to_ocr_span()`。

### `rapidocr._to_ocr_span(raw_item: Any, *, coordinate_space: CoordinateSpace, offset: tuple[float, float], language: str | None, elapsed_seconds: tuple[float, ...], actual_roi: dict[str, int] | None) -> OcrSpan`
行为：把一行 RapidOCR 结果转成无目标语义的 `OcrSpan`。

算法：
1. 要求行包含 polygon、非空 text 和 `0..1` confidence。
2. 调用 `_normalize_polygon()` 得到已经加上 ROI 偏移的有限坐标点。
3. 用 x/y 最小最大值构建 enclosing `BoundingBox`，拒绝零面积。
4. 写入 stable provider id、完整 polygon、分阶段耗时和实际 ROI 元数据，构造 `OcrSpan`。

副作用：无。

失败行为：结果行、文字、置信度或 polygon 结构不符合契约时抛 `ProviderError`。

调用关系：由 `recognize()` 对每行调用；其 `OcrSpan` 由 `ProviderBackedOcrDetector.detect()` 消费。

### `rapidocr._normalize_polygon(raw_polygon: Any, offset: tuple[float, float]) -> tuple[tuple[float, float], ...]`
行为：验证并平移 OCR 文字框的多边形顶点。

算法：要求至少三个点、每点恰有两个有限数值；逐点转为 float 后加 ROI `(offset_x, offset_y)`，保持所有 backend polygon 点而不是假设轴对齐矩形。

副作用：无。

失败行为：点数量、点长度或坐标值不合法时抛 `ProviderError`。

调用关系：仅由 `_to_ocr_span()` 调用。

### `rapidocr._is_sequence(value: Any) -> bool`
行为：区分可遍历 OCR 结构与不应按字符展开的 string/bytes；用于 ROI、backend rows、timings 和 polygon 的结构验证。

副作用与失败行为：无；返回布尔值。

调用关系：由所有 RapidOCR 参数/结果规范化 helpers 调用。

### Flow: Generic OCR text location and target detection
1. Application composition creates a long-lived `RapidOcrProvider(engine_options=...)` and captures it in `PerceptionEngine.algorithm_factories["ocr"]`. The input is a runtime-only provider; the output is a factory that can build `ProviderBackedOcrDetector`. It stores a provider reference only, never a model object in profile JSON.
2. `PerceptionEngine.detect(frame: FrameContext, profile: TargetProfile)` calls `DetectorRunner.run()`, which copies one OCR `AlgorithmProfile.parameters`, injects the profile `target_type`, and calls the runtime factory. The output is a detector aligned to that target or an isolated instance error.
3. `ProviderBackedOcrDetector.detect(frame)` defensively copies `provider_parameters` into `RapidOcrProvider.recognize()`. Its input is a frame image, coordinate space, optional ROI, and backend options; its output is target-agnostic `tuple[OcrSpan, ...]`. This hop never captures a screen, maps coordinates, or performs input.
4. `RapidOcrProvider.recognize()` clips the ROI, invokes the cached ONNX engine, and sends the local polygons, text, confidence, and timings through `_to_ocr_span()`. Its output `OcrSpan` boxes use the original `FrameContext.coordinate_space`; ROI x/y offsets have already been restored. The only possible side effect is first-call model initialization.
5. `ProviderBackedOcrDetector.detect()` applies exact/contains/regex, case, and OCR-confidence rules. Each surviving span becomes `TargetDetection(target_type, center, bbox, coordinate_space, text, evidence)`, which can enter generic selection/fusion without knowing it came from OCR.
6. `PerceptionEngine._run_stages()` applies existing confidence filtering, geometry fusion, temporal confirmation, and selection, then returns `PerceptionRunResult`. A future `CoordinateMapper` and workflow consume the same standard detection contract used by template, shape, and color algorithms.

### `definitions.new_event_draft(source: Mapping | None = None) -> dict`
```python
def new_event_draft(source: Mapping | None = None) -> dict
```
行为：深拷贝事件定义并移除 catalog 身份字段，供新建/复制使用。
算法：1. 把空 source 规范为 `{}`。2. 遍历键值。3. 跳过 `id/owner_device_id/revision/updated_at/deleted/content_hash`。4. 深拷贝其余 definition 字段并返回。
副作用：无。
失败行为：source 无法转换为 dict 时传播 `TypeError`/`ValueError`。
调用关系：called by `EventDefinitionRepository.new_draft()`；经 `EventWorkbenchService.new_event_draft()` 被 GUI 调用。

### `definitions.parse_event_definition(record: Mapping) -> ExecutableEventDefinition`
```python
def parse_event_definition(record: Mapping) -> ExecutableEventDefinition
```
行为：把本机或远程 catalog record 转为唯一可执行快照。
算法：1. 规范化并校验非空名称。2. 逐条调用 `_parse_track()`，把 mode、buttons、hold/interval/end 转成不可变 `ActionTrack`。3. 深拷贝 steps。4. 把可选 max_runs/end_ms 转成 int。5. 复制稳定 ID、owner、revision 和 loop，构造 frozen dataclass。
副作用：无。
失败行为：空名称抛 `ValueError`；未知 `TrackMode` 或非法数值传播 `ValueError`/`TypeError`。
调用关系：called by `EventDefinitionRepository.definitions()`；calls `_parse_track()`。

### `EventDefinitionRepository.set_device_id(self, device_id: str) -> None`
```python
def set_device_id(self, device_id: str) -> None
```
行为：Host 身份可用后，把所有本机 catalog 记录（含 tombstone）绑定到真实设备 owner。
算法：1. 空 ID 规范为 `local`；未变化直接返回。2. 从旧 store 读取含 tombstone 的 `local_catalog()`。3. 用新 device ID 重建 `EventStore`。4. 深拷贝每条记录并替换 owner。5. 覆盖写回，不变更 ID、revision 或 definition。
副作用：设备 ID 变化且存在记录时重写 `<root>/events.json`。
失败行为：文件写入 `OSError` 向上传播；无记录时只切换 store。
调用关系：called by `EventWorkbenchService.tick_once()` after `sync.status`; calls `EventStore.local_catalog()` / `save_local()`。

### `EventDefinitionRepository.save_local(self, records: Iterable[Mapping]) -> list[dict]`
```python
def save_local(self, records: Iterable[Mapping]) -> list[dict]
```
行为：保存本机可见事件，集中分配身份/revision，并为被移除记录生成 tombstone。
算法：1. 从完整本机 catalog 构建 `id -> EventRecord`。2. 对每个 draft 深拷贝并解析 candidate。3. 新 ID 保存 candidate；定义未变保存 previous；定义变化调用 `previous.updated()` 使 revision+1。4. 收集本轮保留 ID 和返回给 GUI 的活动记录。5. 对旧 catalog 中未保留的活动记录调用 `tombstone()`；已有 tombstone 原样保留。6. 将活动记录+tombstone 一次写回。
副作用：覆盖 `<root>/events.json`；新事件生成 UUID/时间戳/hash，修改或删除增加 revision。
失败行为：已删除 ID 被尝试更新时 `EventRecord.updated()` 抛 `ValueError`；非法 revision/字段类型传播转换异常；文件错误传播。
调用关系：called by `EventWorkbenchService.save()`；calls `EventRecord.from_dict()/updated()/tombstone()` and `EventStore.save_local()`。

### `EventDefinitionRepository.resolve_shared_key(self, item: Mapping) -> str | None`
```python
def resolve_shared_key(self, item: Mapping) -> str | None
```
行为：把远程 inbox 的 eventId/name/revision 解析为本机执行器使用的稳定 definition key。
算法：1. 无 eventId 时按 name 做 legacy fallback。2. eventId 可直接命中时返回该 ID。3. 否则按 name 找 fallback。4. 仅当 fallback revision 不低于消息 revision 时返回其 ID。5. 无安全匹配时返回 `None`。
副作用：读取本机+远程目录；legacy 本机读取可能触发 EventStore 一次迁移持久化。
失败行为：非法 revision 的 `int()` 转换异常向上传播；未命中正常返回 `None`。
调用关系：called by `EventWorkbenchService._receive_remote_events()`；calls `by_id()` / `by_name()`。

### `EventRouteRepository.load/save` 与 `EventRouter.dispatches`
```python
def EventRouteRepository.load(self) -> tuple[EventRoute, ...]
def EventRouteRepository.save(self, routes: Iterable[EventRoute | Mapping]) -> None
def EventRouter.dispatches(self, trigger: str, source: str = "local") -> tuple[EventDispatch, ...]
```
行为：负责 route 文件边界和无副作用 dispatch 决策。
算法：1. `load()` 读取 JSON；缺失/无效 JSON 返回空，非 list 抛错；每项经 `EventRoute.from_record()` 规范 source/target/trigger/controller。2. `save()` 先把所有 mapping 规范成 typed route，确保整体有效，再创建目录并写中文兼容 record。3. `dispatches()` 规范 trigger/source，筛选相同 source+trigger 的 route，并把 target 是否 paired 转成 `remote: bool`。
副作用：只有 `save()` 写 `<root>/routes.json`；router 无副作用。
失败行为：未知端点/controller、空 trigger/event 抛 `ValueError`；文件错误传播，读取缺失降级为空。
调用关系：called by `EventWorkbenchService.__init__/save/_reload_configuration/_dispatch_local_triggers()`。

### `EventExecutionRuntime.start/cancel_source/tick`
```python
def start(self, source: str, event_name: str, controllers: Iterable[int], *, instance_id: str | None = None) -> bool
def cancel_source(self, source: str) -> tuple[EventStateFrame, ...]
def tick(self) -> tuple[EventStateFrame, ...]
```
行为：按来源和 controller 隔离执行 `EventSession`，产生完整状态帧。
算法：1. `start()` 规范 source 和 controller 1/2；未知 definition 返回 False；为每个 `(source, controller)` 延迟创建 session 并启动同一 definition。2. `cancel_source()` 删除该 source 的全部 session，并为每个受影响 controller 构造 neutral frame。3. `tick()` 以稳定 key 顺序推进所有 session，将输入集合经 `state_from_inputs()` 转为完整 state dict。
副作用：更新 `_sessions` 和各 `EventSession` 生命周期状态；无设备 IO。
失败行为：空 source 或非法 controller 抛 `ValueError`；未知 definition 返回 False。
调用关系：called by `EventWorkbenchService` dispatch/receive/tick/stop；calls `EventSession.start/tick()` and `state_from_inputs()`。

### `HotkeyTriggerSource.poll(self, keys: Iterable[str]) -> tuple[str, ...]`
```python
def poll(self, keys: Iterable[str]) -> tuple[str, ...]
```
行为：把当前 key state 转为去重的按下边沿 trigger。
算法：1. 大写、去空白并按首次出现顺序去重。2. 跳过未知键。3. 对每个已知 VK 读取 pressed。4. pressed 且不在 `_pressed` 时 emit。5. pressed 加入集合；松开则移除以允许下一次边沿。
副作用：在锁内更新 `_pressed`；默认 Windows 读取器调用 `GetAsyncKeyState`。
失败行为：非 Windows 使用默认读取器抛 `RuntimeError`；注入读取器异常向上传播。
调用关系：called by `EventWorkbenchService._dispatch_local_triggers()`。

### `HostEventBridge.write_state/send_event/publish_catalog/drain_*`
```python
def write_state(self, frame: EventStateFrame, ttl_ms: int = 120) -> dict
def send_event(self, peer_id: str, payload: dict) -> dict
def publish_catalog(self, peer_id: str, catalog: dict) -> dict
def drain_events(self) -> tuple[dict, ...]
def drain_catalogs(self) -> tuple[dict, ...]
```
行为：把服务调用一对一翻译为现有 Host/LAN 协议。
算法：1. 所有方法先经 `_request()` 校验已连接。2. `write_state()` 发送 controller/source/state/ttlMs 到 `event.state`。3. 事件/目录发送分别给 payload 增加 deviceId，调用 `sync.share.event` / `sync.share.catalog`。4. 事件/目录 drain 严格分别调用 `sync.share.drain` / `sync.share.catalog_drain`，只返回 dict 项。
副作用：命名管道请求；Host 可能更新 controller source state 或 LAN inbox/outbox。
失败行为：未连接抛 `RuntimeError`；client 连接/请求异常向上传播；bridge 不重试。
调用关系：called only by `EventWorkbenchService`; calls injected/default client `request()`。

### `EventWorkbenchService.save/send_remote_event/tick_once`
```python
def save(self, events: Iterable[dict], routes: Iterable[dict]) -> list[dict]
def send_remote_event(self, device_id: str, event_name: str, controllers: Iterable[int]) -> dict
def tick_once(self) -> None
```
行为：提供 GUI 命令边界，并推进一次统一目录/触发/远程/输出循环。
算法：1. `save()` 在服务锁内保存 definitions/routes、重建 router、替换执行定义并返回深拷贝版本记录。2. `send_remote_event()` 校验目标/名称/controller，创建独立 bridge，以 2 秒连接 timeout 读取 peer 状态，选择匹配记录，构造 Host-clock `+250ms` payload，发送后必定关闭。3. `tick_once()` 获取长期 bridge 和 status，更新 peer/device owner，依次同步目录、本机触发、远程 inbox、pending clear，最后把所有 execution frame 以 120ms TTL 写入 Host。
副作用：JSON 持久化、命名管道/LAN 请求、服务状态/计数/日志更新和 controller source state 写入。
失败行为：直接发送参数错误抛 `ValueError`，目标不可用抛 `RuntimeError`；bridge 异常由直接调用者接收，worker `_run()` 捕获后写 error、清 bridge 并等待 0.5 秒再试。
调用关系：`save/send_remote_event` called by GUI；`tick_once()` called by worker or deterministic tests；calls repository/router/execution/bridge methods。

### `EventWorkbenchService._sync_catalogs/_dispatch_local_triggers/_broadcast/_receive_remote_events`
```python
def _sync_catalogs(self, bridge: EventHostBridge, peers: tuple[dict, ...]) -> None
def _dispatch_local_triggers(self, bridge: EventHostBridge, peers: tuple[dict, ...]) -> None
def _broadcast(self, bridge: EventHostBridge, peers: tuple[dict, ...], dispatch) -> bool
def _receive_remote_events(self, bridge: EventHostBridge) -> None
```
行为：完成目录交换和本机/远程两条触发路径的统一编排。
算法：1. `_sync_catalogs()` 到 interval 时向每个 data peer 独立发布含 tombstone 目录，随后单独 drain catalogs，按 revision 应用并热替换 definitions。2. `_dispatch_local_triggers()` 轮询 router keys，逐个取得 dispatch；本机目标按 stable local ID 启动 execution，paired 目标进入 `_broadcast()`。3. `_broadcast()` 构造 eventId/revision/targets/Host-clock `+500ms` payload，对每个 peer 先确保 catalog 再发 event；单 peer 异常只写 `peer_errors`，继续后续 peer。4. `_receive_remote_events()` 丢弃 deadline 已过消息，解析 stable key 和 target controllers，以 `event:remote` 启动同一 execution runtime。
副作用：目录/事件 LAN 请求、remote_events.json 更新、execution session 更新、计数/最近事件/peer errors 更新。
失败行为：catalog fanout 单 peer 异常隔离；目录 drain/apply 或 receiver 的非隔离异常传播到 worker 顶层并触发 bridge cleanup/retry。
调用关系：called by `tick_once()`；calls `EventDefinitionRepository`、`EventRouter`、`HotkeyTriggerSource`、`EventExecutionRuntime`、`HostEventBridge`。

### `EventWorkbenchPage._save/_toggle_runtime/_toggle_remote_runtime/shutdown`
```python
def _save(self)
def _toggle_runtime(self)
def _toggle_remote_runtime(self)
def shutdown(self)
```
行为：把 Qt widget 值转换为服务命令，不拥有持久化/线程/协议实现。
算法：1. `_save()` 遍历 route rows，从 combo 读取 source/trigger/event/target/controller，调用 `service.save()` 并用返回的权威版本记录刷新列表。2. toggle 方法读取 `service.status()` 计算目标状态；启用前保存草稿，再调用对应 set 方法并刷新 UI。3. `shutdown()` 用 `_shutdown` 保证幂等，停止两个 Qt timer，只调用 `service.shutdown()`。
副作用：更新 widgets；通过 service 间接保存/启停。页面自身不写文件、不发送协议。
失败行为：service 异常由 Qt 调用栈传播（直接发送单独捕获并显示）；重复 shutdown 静默返回。
调用关系：called by Qt signals and `MainWindow.closeEvent()`；calls only `EventWorkbenchService` public methods。

## 6. 完整数据流链路
### Flow: PoE2 实验安全路径与真实移动边界
1. 当前实例 terrain 墙图和视觉位置进入 PoE2 实验跟随 runtime；点击目标经展示逆变换回到 reference/native 坐标，`FollowObservation.diagnostics.coordinate_space` 固定标记为 `reference_native`，并验证位置/目标属于同一实例。
2. `SimulatedFollowRuntime._plan_safe_route()` 用 0/255 障碍图多尺度搜索，包含起点和终点连接段在内逐段于原图复核；`tick()` 产出 route/vector/状态以及路线点数和端点证据。模拟/预览模式止于观测。
3. 仅独立 program adapter 经显式确认取得 Host lease 后将 reference/native 向量直接交给 PoE2 basis 变成摇杆状态；registration 已在点击/人物/地图进入 native 时使用，不能在输出边界重复应用。焦点、最新视觉位置、限时及正确轴基必须在实机闭环中独立验证；终止时中性并释放。旧图离线找路不能代替当前实例穿门验证。
### Flow: PoE2 双人首帧后的实验运动跟踪
1. 用户点 `Poe2CaptureTestPage.start_dual_motion()`：输入当前 snapshot/profile；停掉同页其他 timer，调用 `run_dual_first_frame_experiment()` 只读一次双人 native anchor 并取得一帧 `HybridFrame`、两个身份及共同变换。首帧拒绝则不启动。
2. `_start_dual_motion()` 先停止同页旧循环，并在任何首帧截图/内存读取前确认 retired worker 已退出；若仍运行则写入 `restart_deferred`，由 `finished` 回调在 session token、closing 和 snapshot 门控通过后恢复。通过后再从当前 oriented terrain 的边界建立 `MapRuntime` 和 `LocalMapMatcher`，用 `DualVisualTracker.start(frame,result,candidates)` 保存会话状态；Qt timer 间隔取 monitor config，地图按方向只构造一次。副作用：仅 Qt 状态和内存 matcher。
3. `Poe2DualMotionWorker._capture_one()` 从 `preview_provider(config)` 得 `uint8[H,W,3]`，以 `exclude_player=False, exclude_dynamic=False` 提取墙体 mask，同帧颜色检测生成最多六个 `PlayerMarkerCandidate`；普通帧无内存读取。测试 hook 的 `_tick_dual_motion()` 执行同等同步链路。
4. `DualVisualTracker.tick(frame,candidates)` 输出 `DualMotionState(players: identity -> native tuple|None, transform, wall_quality, diagnostics, recovery_revision)`；通用 `BoundedRoleObservations.update()` 分角色标记可见/估计/过期，墙层失效或预算耗尽请求恢复。
5. worker `_offer(result)` 覆盖旧图像但独立保存最大待处理 revision；页面 `_drain_dual_motion_worker()` 取最新帧及待处理 revision，按 generation 过滤，先处理恢复并释放程序输出。`_record_dual_observation_evidence()` 仅在状态签名变化时最多调用六次 `save_dual_occlusion_evidence()`，写 `occlusion_diagnostics/raw.png`、颜色 mask 和 JSON；归档失败只记 warning。
6. 非恢复帧由 `_render_dual_motion_state()` 将 native 角色点转换到展示空间；实时跟随 `_tick_follow_experiment_impl()` 只在墙层可信、截图不超过 700ms、参与角色年龄和误差均在预算内时使用 `wall_estimate`，否则调用 program output 的 `release_all()`。领队角色的视觉点直接作为 `remote` 目标；程序角色先由 `CommandRoleTracker` 回放已接受 TTL，并在新视觉点到达时用实际位移/时间更新速度。页面缓存上一视觉点和捕获时间必须按 `RoleId.key` 对齐；连续小步视觉点调用 `rebase_visual()` 清除过时命令区间，异常跳变才进入拒绝/重定位。随后两条场景都调用同一 `SimulatedFollowRuntime.update_follower_position()`、`tick()` 和 `ProgramFollowOutput`。`SimulatedFollowRuntime.update_follower_position()` 和 `_tick_follower()` 不把估计点当速度/无进展/接触恢复证据。正常输出仍由显式 program adapter 掌管。
7. 恢复 revision 触发 `_start_dual_motion(recovery=True)` 的一次新首帧内存读；后台首帧结果经 `_on_dual_first_frame_worker_result()` 应用后，以 `first_frame_ready=True` 消费 accepted 缓存并建立新 tracker，不再把 accepted 结果误判为空。10 秒内再次失败停表并提示手动重启，不形成密集读取循环。换图、主动停止与关闭均停表并释放输出。

### Flow: PoE2 程序移动的小地图接触纠偏
1. `Poe2CaptureTestPage._tick_program_move_probe()` 以最新 `DualMotionState.players[actor_id]` 和真实 `captured_at_ms` 更新 `SimulatedFollowRuntime.update_follower_position()`；不为旧帧重打时间戳，视觉短暂超过 700ms 时进入有界预测保持并记录 observation gap，只有失去可用估计、前台失焦、显式停止或 recovery episode 达到门槛时才中性释放。
2. 上一 tick 的 native route vector 经 `inverse_transform_local_displacement()` 回到小地图局部方向；`inspect_minimap_contact(wall_mask, screen_position, screen_vector)` 只采样人物前方 6/10/14 像素束和左右侧束，返回 `wall_ahead`、首个墙距与 `free_left/free_right`，不清除或修改人物/墙体像素。
3. 页面调用 `runtime.update_local_contact()` 保存这份适配层证据；下一次 `update_follower_position()` 由 `ContactMonitor.observe()` 把命令、native 位移、对齐度和局部障碍合成为 `ContactEvidence`。
4. `_tick_follower()` 发现连续无进展且局部前方有墙时跳过原 global route，调用 `_recovery_waypoints(preferred_side=...)` 优先选择小地图更开的一侧；输出 `contact_recovery` 并保持有限脉冲。PoE2 页面使用四样本接触门；两次局部恢复仍无进展返回 `contact_relocalization_required`，页面保存目标/角色/控制器、neutralize/release，并调用 `_start_dual_motion(recovery=True)` 强制新增一次内存锚点首帧注册。新 tracking 帧到达后 `_maybe_resume_program_probe_after_relocalization()` 自动恢复原目标；全过程不依赖总时长硬停止处理撞墙，也不会在冷却窗口内循环读内存。

### Flow: PoE2 双人首帧特征预览与定时刷新
1. `Poe2CaptureTestPage.run_dual_first_frame_experiment()` 输入 `TerrainSnapshot`、`Poe2MonitorConfig`，只读一次两名人物 native anchor，并从 `preview_provider(config)` 至多获取三张截图；输出选定的 `raw_frame:uint8[H,W,3]`。
2. `HSVRecognizer.extract_combined_with_processed(raw_frame, player_pos=None, exclude_player=False, exclude_dynamic=False)`（兼容 recognizer 没有该方法时回退到 `extract_combined`）输出预处理图与 `(match_mask,wall_mask,fog_mask)`；同帧颜色检测输出双人候选。`match_mask` 进入 `HybridFrame.wall_mask`，预处理图和 combined 由 `_render_preview(raw_frame, processed=processed, combined=combined)` 复用，没有人物半径清零。
3. `QTimer.timeout -> Poe2CaptureTestPage.refresh_preview()` 输入当前 monitor config，获取新帧，再由 `_render_preview(frame)` 读取 `_dual_preview_active` 并沿用无擦除参数；只更新显示，不重新运行双人注册或读取内存。
4. `capture_map()`、`_clear_map_state()`、`start_hybrid_localization()` 或 `start_multiframe_localization()` 将 `_dual_preview_active` 置为 False；后续预览恢复识别器默认策略。所有阶段只读屏幕/进程并更新 UI/日志，不发送设备或网络输入。

### Flow: PoE2 测试台多帧全局定位、连续跟踪和恢复（verified by synthetic replay）
1. `Poe2CaptureTestPage.start_multiframe_localization()` 输入当前 `TerrainSnapshot`、profile provider 和 A/B 开关；调用 multiframe factory 创建独立 experiment，启动 session/timer；启动异常会关闭已创建 session 并恢复控件。副作用仅为实验内存状态和 Qt 控件；正式 runtime 不变。
2. `MultiframeLocalizationSession.tick()` 输入当前截图时刻；frame source 输出 `HybridFrame(frame_id:int,captured_at_ms:int,wall_mask:uint8[H,W],local_player_position:tuple)`，evidence builder 输出 `MultiFrameEvidence`，其 raw/wall/observed 均只读。
3. `anchor_once(recovery_revision:int)` 调用 `Poe2MemoryAnchorProvider.read_once(expected_instance_id)`，输出 native `PositionAnchor(position:tuple[float,float],area_instance:str,captured_at_ms:int)`；同 revision 只调用一次，失败不循环读取；新 session start/reset 会先清理 builder 的累计 offset/segment。
4. `MotionGate.decide()` 输出 `MotionDecision(state,FrameDisplacement,should_capture_keyframe,reason)`；`EvidenceWindow.append()` 仅保存已接受 moving keyframe并更新 version；`RollingSubmap.rebuild()` 输出有限 `SubmapSnapshot(wall_mask,observed_mask,origin,frame_ids)`。
5. coordinator 达到结构门后生成 `RegistrationRequest(instance/recovery/evidence/segment token,frames,anchor,reference)`；session 单 worker 调用 `evaluate_registration()`，A 用拼图+holdout，B 用共同相似变换多帧候选。
6. `apply_registration_outcome()` 只有 token 仍匹配才发布 confirmed native `PositionEstimate`；注册期间可靠位移按 transform 的 OpenCV 图像坐标线性部分转到 terrain，再取负号补偿人物运动。
7. tracking 时 accepted movement 经 estimator 更新；stationary 保持 confirmed 但 `fresh=False`；失败先 DEGRADED，达到阈值才 `begin_recovery()` 增加 revision、断开 segment 并请求下一次单次内存锚点。
8. `Poe2CaptureTestPage._tick_multiframe()` 把 estimate、trajectory、registration transform、submap 和 A/B diagnostics 交给 panel/presenter；地图、轨迹、人物点使用同一 display transform；只有 anchor/reference/evidence 均存在时保存按钮才开放。显式保存调用 `MultiframeArchive.save()` 原子发布 `data/poe2_live_terrain_test/multiframe_sessions/<UTC>/`。
9. `NavigationLocalizationAdapter.to_observation()` 可将结果转为领域中立 observation；只有 fresh confirmed 且 instance/version/age 合格时 executable。本轮没有调用路径规划、Xbox、键鼠、Host 或 LAN。

### Flow: 已信任 LAN 会话内热增/停用输入（verified）
1. `LanSyncService.Handle("sync.start", payload)` 输入 `deviceId:string`、`capabilities:string[]`、`controllers:int[]`；若同 peer 已有发送会话，写入 `Session.Controls` 的 `capability-update(requestId:Guid, capabilities:string[], controllers:int[])`，不另建 TCP/UDP；不改变当前授权或恢复偏好。
2. `LanSyncService.RunControlsAsync(receiver)` 从 TLS 读请求，`SessionCapabilities.Reverse()` 得到接收端 flags；用 `ValidateIncomingCapabilitiesLocked()` 检查 mode/位置/事件许可，再检查 controller 本地保存授权和其他会话占用。失败写 `capability-reject(requestId,error)`，原会话和共享能力不变。
3. 校验成功时接收端为新增输入生成 `grants:uint[2]`，或在移除输入时清零 grants、重置 `_remote[slot]`；更新 `Session.Controllers/Capabilities`，经 TLS 写 `capability-ack(requestId,capabilities,controllers,grants)`。
4. `LanSyncService.RunControlsAsync(sender)` 比对 requestId、flags、controllers、grants；匹配后更换本地授权和 baseline 状态，把 peer scope/恢复能力写入内存并由 `SavePreferencesLater()` 持久化到 `trusted.json`、`preferences.json`。拒绝响应只清除 pending 并写 peer error。
5. `CollectPackets()` 仅对 `InputSend` 的 controllers 发加密输入，对 `PositionPublish` 独立节拍发位置；`ReceivePacket()` 对输入撤销后的旧 datagram 直接丢弃，已认证数据共享仍可继续。最终 `status.peers[].sessionId` 不变，接收侧被撤销输入为 Neutral。

### Flow: LAN 面板按能力更新同一 peer（verified）
1. `SyncPanel.start_peer()` 输入当前选中 peer 的 `deviceId:string` 和手柄范围 `controllers:int[]`；`_selected_capabilities()` 将四个复选状态映射为 `input.send/position.publish/event.publish/catalog.publish`，share 模式不能申请输入。
2. `SyncPanel.peer_command()` 发送 `sync.start(deviceId,controllers,capabilities)` 到 Host；`LanSyncService.Handle()` 对已连接的同 peer 写 `capability-update`，对新 peer 仅建立一个 session；页面只显示当前能力列表，不拥有业务会话。
3. `SyncPanel.shutdown()` 输入无，经 Host 发 `sync.suspend`；`LanSyncService.Handle()` 重置当前接收输入、关闭会话，并把 `_suspendedPeers` 设为进程内栅栏；`preferences.json` 的恢复资格保持。显式停止按钮仍发 `sync.stop`，清除恢复资格。

### Flow: 正常退出、重启恢复和手动停止（verified）
1. `LanSyncService.Dispose()` 输入无；先标记进程关闭、关闭活动 socket/中立化内存输入，不调用 `EmergencyStop()`，磁盘上的信任、mode、接收许可及恢复能力保持原状。
2. 新实例 `LanSyncService(dataDirectory)` 读取 `IdentityStore` 的 `preferences.json` 与 `trusted.json`，恢复 `Mode/ReceivePositions/ReceiveEvents/EnabledControllers/RecoveryCapabilities`；`NetworkLoop()` 建立本地监听，`ConfigureNetwork()` 为恢复 peer 排程退避连接。
3. `ScheduleAutoReconnectLocked()` 在 generation、手动 block、可信 peer 和当前模式许可均成立时，取保存的 capability flags 及 controller scope 调用 `StartOutgoingAsync()`；新 TLS/UDP 会话生成全新 sessionId、密钥和 grants。
4. `CloseLocked()` 对普通断线先重置接收输入并撤销当前输出，再允许信任设备重新协商已保存授权；`Handle("sync.stop"/"sync.reset"/"sync.forget")` 或 `EmergencyStop()` 清除目标的恢复资格并写偏好，后续旧任务受 generation/startVersion 栅栏阻止。
5. `Handle("sync.suspend")` 仅关闭当前进程会话并使用 `_suspendedPeers` 阻止已信任设备在窗口关闭后立即回连；正常 `Dispose()` 不把这一临时栅栏写入磁盘，下次进程启动仍按保存的偏好恢复。

### Flow: 应用注入 Torchlight 事件组合
1. `ui/main_window.py::MainWindow.setup_ui()` 调用 `build_torchlight_navigation_composition()`，取得 registry 工厂、游戏窗口查找器和 Loot overlay provider；不在通用导航包中导入游戏事件类。
2. `ui/modes/navigation/widget.py::NavigationModeWidget.__init__(..., event_registry_factory, game_window_finder, event_overlay_providers)` 保存三个显式注入点；未注入时分别使用空 registry、无窗口和无附加 overlay。
3. `ui/modes/navigation/event_adapter.py::create_default_event_registry()` 只负责 registry 工厂调用；`ui/modes/torchlight/navigation.py` 才解释 Torchlight 窗口和 Loot 调试配置。
4. `features/torchlight/composition.py::build_torchlight_feature_registry()` 创建通用 registry，调用 `register_torchlight_events()`。
5. `register_torchlight_events()` 构造并注册 `PortalEventDefinition` 与 `LootEventDefinition`，输出包含 `portal/loot` 的 registry；模板读取仍延迟到 definition 创建 detector 的阶段。
6. 地图加载时 `initialize_navigation_event_system()` 输入该 registry 和地图事件配置，输出 `EventCoordinator`；后续导航只通过通用 definition/handler contract 运行。

### Flow: Torchlight skill chain 使用通用动作序列
1. `features/torchlight/follow/config.py::FollowConfig.validate()` 输入保存的 chain dict，通过 `features.torchlight.skills.FollowChainDefinition` 验证边界；该 facade 继承 `ActionSequenceDefinition`。
2. `features/torchlight/follow/workers.py::actor_worker()` 对 enabled chain 构造 definition 并注册到通用 `EventRegistry`；输入仅为本机已验证配置。
3. `EventRunner`/`DualFollowSession` 调用 definition 的 `create_handler()`，输出独立 `ActionSequenceHandler`，每个 actor/任务持有自己的 index、retry 和时钟状态。
4. handler `update(EventTick, EventTask)` 输出 WAIT/COMPLETE/FAIL 以及 controller input metadata；不接触 Host 或设备。
5. `DualFollowSession` 把 action metadata 与跟随运动决策合并，交给 `ProgramGamepadOutput`；只有显式启动 worker、连接 Host 并取得 lease 后才产生真实输出。

### Flow: 源码与安装态启动
1. `main.py::<module>` 输入当前脚本绝对路径，输出 `<root>/src` 并前置到 `sys.path`；副作用仅修改当前 Python 进程 import path。
2. `main.py` 导入 `auto_modules.bootstrap.main::main`；输出 callable，不创建 GUI。
3. `bootstrap.main::main()` 执行输出/日志、DPI、UAC、单实例和旧窗口检查；输出启动许可或安全退出，副作用限于 Windows process bootstrap 和 `data_root()/logs/runtime.log`。
4. bootstrap 构造 `QApplication` 和 `ui.main_window.MainWindow`；MainWindow 组合 core capabilities、application services 和 concrete adapters。
5. 安装态 `RuntimeLayout.CreateStartInfo()` 以 bundled `pythonw.exe -I -B app/main.py` 启动，并设置 `AUTO_MODULES_DATA_DIR/HOST_DIR/RESOURCE_DIR`；Python 仍沿用同一根入口。

### Flow: Follow 位置共享与程序手柄输出
1. `features.torchlight.follow.workers::vision_worker()` 输入小地图帧/定位结果，输出 `core.communication.SharedPosition` 到 bounded latest queue；不理解 Host wire payload。
2. `features.torchlight.follow.service::FollowService._network()` 取 local contracts，调用 `adapters.host.follow_transport::publish()`；adapter 输出 `sync.share.position` payload 并转换 local age 到 Host deadline。
3. `_network()` 调用 `FollowTransport.poll()`，输出经过有限值、confidence、TTL 和 IPC-delay 检查的 `SharedPosition/SharedEvent` tuples。
4. `actor_worker()` 输入共享观察和事件，`DualFollowSession/FollowerController` 输出二维 movement vector/buttons。
5. `adapters.virtual_gamepad.program_output::ProgramGamepadOutput.write()` 输入 vector、elapsed、TTL、buttons，输出完整 `program.state`；副作用为 named-pipe Host request。
6. C# Host 校验 lease/token/deadline 后合并到指定 controller report；暂停、TTL、release 或异常 cleanup 使贡献归零。真实 XInput 和 LAN 输出只发生在 Host 已由用户显式启动的情况下。

### Flow: 离线 payload 与默认数据
1. `packaging/distribution/build.py::select_runtime_sources(root)` 输入 repository root，输出 allowlist 中的 `main.py`、`src/auto_modules/**/*.py` 和允许后缀的 `resources` 文件；排除 tests、cache、secret 和 writable data。
2. `assemble()` 输入新 destination、.NET SDK、requirements lock，输出 isolated embedded Python、wheel closure、`app/`、Host、launcher 和 manifest；现有 destination 会被拒绝而非覆盖。
3. workspace `data/config.json`、`data/virtual_gamepad/configs/controller-*.json`、`data/maps/**` 经清洗复制到 payload `defaults/`；credential/display geometry 被移除。
4. installer 把 payload 安装到 `{app}`，`RuntimeLayout.SeedDefaults(defaults, data)` 仅补缺失 config/profile/map directory，已有用户 map 作为整体不被恢复或覆盖。
5. installed smoke 使用临时 `AUTO_MODULES_DATA_DIR`、offscreen Qt 和 fake Host 构造完整 UI；不连接真实 Host、网络或输入钩子。

### Flow: 自动导航移动点击
1. `NavigationRuntimeFrameLoop.run()` 调用 `capture_navigation_localization_tick()` 获取 `capture_rect`、屏幕截图帧、玩家局部坐标和 `localized_pos=(global_x, global_y)`；副作用是更新定位核心状态，后续再更新地图上的玩家点、绿色定位框、橙色真实可见框和事件 marker。
2. `NavigationCore.localize_result()` 输入实时小地图截图和 `player_pos`；内部调用历史 `localize()` 并输出 `LocalizationResult(GLOBAL_MAP)`；副作用仍是更新 `current_pos/last_good_pos/prev_mask` 与 `last_frame_registration`。
3. `EventCoordinator.observe()` 输入 `EventTick(frame, frame_registration, player_global_pos)`；输出 memory 中的 active event tasks；副作用是检测 raw minimap 图标、稳定全局事件坐标、更新事件 overlay，但不推进 handler。
4. GUI runtime 构造 `NavigationUpdateContext` 并调用 `NavigationTaskController.update_context()`；context 内含定位、`route["main"]`、`EventCoordinator.tasks()`、`nav_core.nav_wall_layer`、`explored_map` 和 `PathFinder`；控制器先用 `NavigationTaskBuilder` 构造 required/exit/event 任务，再由 `NavigationTaskScheduler` 选择一个当前任务；输出 `NavigationIntent`。
5. 若 `NavigationIntent.metadata.force_relocalize` 为真，`handle_relocalization_navigation_intent()` 调用 `NavigationCore.request_global_relocalization(reason)`、写 `navigation forced global relocalization` 事件日志、追加“正在重新定位”状态栏后缀，并返回 `True` 让主循环提前结束本帧。
6. 静态 required/exit 或事件 `MOVE_TO` 进入 `MovementExecutor.step()`；该执行器通过 `RouteContext.corridor_anchors()` 和 `plan_path_with_optional_anchors()` 优先按前方 guide 点走廊规划 `anchor_step/anchor_probe`，无前方锚点时才直接规划目标，最后输出地图子目标 `subgoal` 和 `path_kind`。
7. 事件任务被选中时，`NavigationTaskController._update_event_task()` 调用 `EventCoordinator.run_task(event_task_id, tick)` 推进 handler；`MOVE_TO` 复用第 6 步，`PRESS_KEY/CLICK_SCREEN/COMPLETE/FAIL` 转成统一 `NavigationIntent`。
8. `NavigationRuntimeFrameLoop._execute_navigation_intent()` 调用 `navigation/input/intent_executor.execute_navigation_intent()` 消费 `MOVE_MAP/CLICK_SCREEN/PRESS_KEY`；`MOVE_MAP` 调用 `MotionController.move_to_map_target()`，带 `force_click_target` 时调用 `click_map_target_once()`，成功点击后回写 `NavigationTaskController.record_intent_click()` 更新点击节流状态。
9. `MotionController._execute_click()` 输入屏幕物理坐标；先用 `_apply_bottom_click_guard()` 避免落入底部 UI，再通过 `InputDriver.click()` 执行 Win32 `SetCursorPos + mouse_event`，失败时才回退 `pydirectinput.click(x, y)`。

### Flow: 导航参数保存和加载
1. `NavigationModeWidget.load_map()` 读取 `map_data/<map>/config.json`。
2. `NavConfig.from_dict()` 将 dict 转为配置对象；缺失新字段时使用默认值。
3. `NavParametersDialog.set_config_to_ui()` 保存当前配置对象，用 `QSignalBlocker` 包住全部子控件，再调用 `write_config_to_widgets()` 将配置同步到控件。
4. 控件变化触发 `_update_config_value()`；HSV 文本先经 `parse_config_text_value()` 解析，无效/未完成输入直接跳过。
5. `_update_config_value()` 调用 `replace_config_value()` 通过 `dataclasses.replace()` 创建新配置并发出 `parameters_changed`。
6. `NavigationModeWidget._on_parameter_changed()` 保存内存态配置，调用 `apply_motion_controller_config()` 立即更新 `MotionController` 的屏幕中心、移动比例、点击半径和底部禁点区，并通过 `_refresh_game_view_rect_from_known_position()` 重绘橙色框。
7. `_apply_config_to_core()` 作为兼容 wrapper 调用 `apply_navigation_config_to_core()`，该函数调用 `NavigationCore.rebuild_navigation_wall_layer(nav_wall_erode_iterations)`，并把 `path_start_clear_radius`、`path_walkable_snap_radius` 写入共享 `PathFinder`。
8. `configure_navigation_task_controller()` 把点击冷却、重复点击阈值、锚点到达半径、卡住判定间隔、最小进度、恢复次数、路径偏离阈值、事件靠近 gate 和坐标诊断阈值写入 `NavigationTaskController`。
9. 用户保存时 `_save_nav_config()` 调用 `NavConfig.to_dict()` 写回地图配置文件，并再次刷新橙色框。
10. 用户点击“保存为默认配置”时，`_save_nav_default_config()` 调用 `save_default_nav_config(__file__, nav_config)` 合并写入项目根 `config.json`，用于没有地图配置时的默认导航参数。

### Flow: 导航 route 编辑
1. 用户点击“设置出口/添加必经点/添加途经点”按钮，`NavigationModeWidget.toggle_*_mode()` 根据按钮 checked 状态调用 `_set_map_click_mode()`。
2. `_set_map_click_mode()` 调用 `RouteEditor.set_click_mode()` 更新 route 编辑状态，再把非当前模式按钮取消选中。
3. 用户点击地图时，`NavigationModeWidget.handle_map_click()` 作为 wrapper 调用 `NavigationMapClickLifecycle.handle_map_click()`，由 lifecycle 把 scene 坐标加上 `nav_core.crop_offset` 得到全局地图坐标。
4. `RouteEditor.handle_click(map_folder_path, global_point)` 根据 `MapClickMode` 调用 `RouteManager.set_exit_region()`、`add_required_point()` 或 `add_guide_point()` 并返回 `RouteEditResult`。
5. `NavigationMapClickLifecycle.handle_map_click()` 接收结果后通过 targets 写回 `route_data`，必要时通过 `RoutePanelController.set_click_mode()` 复位按钮模式，调用 `_render_route_overlay()` 重绘 route 层，并把返回的 `status_text` 写到状态栏。
6. 用户点击保存/撤销/清空路线时，`NavigationModeWidget` 的旧 slot 调用 `NavigationRouteLifecycle`；lifecycle 调用 `RoutePanelController`，controller 委托 `RouteEditor` 写入或更新 route 数据并返回 `RouteCommandResult`，lifecycle 再同步 `NavigationTaskController.load_route()`、重绘 overlay、写状态栏或弹保存失败警告。

### Flow: 绘图模式地图保存和根配置加载
1. 用户点击绘图页保存地图时，`MappingWidget.save_map()` 读取地图名，并构造 `config_data`。
2. `save_mapping_map(__file__, map_name, stitcher=app_context.stitcher, config_data=config_data)` 调用 `ensure_map_folder()` 创建 `map_data/<map_name>`，再调用 `MapStitcher.save_map_package()` 保存地图包；`MapStitcher.save_map_package()` 会把 `wall_layer`、`explored_map`、`fog_layer`、`current_pos`、`canvas_size` 和 `draw_scale` 写入 `map_data.npz`。
3. `MappingWidget._build_mapping_config_with_ui_overrides(include_draw_scale=True)` 读取截图配置、FPS、recognizer/stitcher 参数，并叠加绘图页 `draw_scale/canvas_size/player_clear_radius/wall_close_kernel_size` 控件值；`MapStitcher.save_map_package()` 同时把 `wall_close_kernel_size` 写入 `map_data.npz` 供导航定位复现墙体模板形态学。
4. `save_mapping_map()` 内部调用 `save_map_config(map_folder, config_data)` 写入 `map_data/<map_name>/config.json`。
5. 绘图页参数变化或区域变化触发 `MappingWidget.save_config()`，它通过 `_build_mapping_config_with_ui_overrides(include_draw_scale=False)` 构造根配置并由 `save_root_config(__file__, config)` 写入项目根目录 `config.json`。
6. `MappingWidget.load_saved_params()` 启动时调用 `restore_saved_mapping_config(__file__, ...)`；helper 先调用 `load_root_config()`，不存在时直接返回，存在时回填 `app_context`、恢复 capture selection、同步 Qt 控件和 recognizer/stitcher 参数；当 stitcher 仍为空地图时，几何参数会立即重建画布。

### Flow: 绘图模式捕获区域/中心点选择
1. 用户点击“选择区域”时，`MappingWidget.select_region()` 调用 `MappingCaptureSelectionController.start_region_selection()` 创建 `TransparentOverlay` 并进入全屏拖框。
2. overlay 确认后发出 `region_selected(x, y, width, height)`，controller 调用 `apply_region_selection()`，按 DPR 把逻辑像素转为物理像素并写入 `app_context.monitor_region`，同时清空 `monitor_logical_center`。
3. controller 返回 `CaptureSelectionResult` 给 `MappingWidget._handle_capture_selection_result()`；widget 更新 label、启用开始/颜色按钮并调用 `save_config()`。
4. 用户点击“选择中心点”时，`MappingWidget.select_center_point()` 调用 `MappingCaptureSelectionController.start_center_selection()` 创建 `CenterPointSelector`。
5. selector 确认后发出 `point_selected(x, y)`，controller 调用 `apply_center_selection()` 写入 `app_context.monitor_logical_center` 和 `monitor_size`，清空 `monitor_region`，并计算物理 `monitor_center`。
6. widget 把返回的 `physical_center` 保存到 `self.monitor_center`，供 `MappingSession.tick()` 和 `open_color_picker()` 调用 `screen_capture.capture_square()`。
7. size spin 变化时，`MappingWidget.update_capture_size()` 调用 controller `update_capture_size()`；区域模式只更新 `monitor_size`，中心点模式会重新计算物理中心和 label。
8. 启动时 `restore_saved_mapping_config()` 写入 AppContext 后调用 `capture_selection.restore_from_context()`，用保存配置恢复 UI label 和物理中心。

### Flow: 点击半径诊断
1. `MotionController._calculate_target_screen_position()` 记录 `raw_screen_radius` 和夹紧后的 `screen_radius`。
2. `NavigationModeWidget.navigation_loop()` 在实际点击后追加显示 `click r:<screen_radius>/raw:<raw_screen_radius>`。
3. 如果 `raw` 明显大于 `r`，说明当前点击被 `movement_max_click_radius` 限制；如果 `raw` 和 `r` 都小，说明路径子目标距离或映射比例过小。

### Flow: 事件图标探针
1. `event_icon_probe.main()` 读取 `map_data/A1/config.json`，按 DPR 将小地图逻辑中心转换为物理截图矩形；如果传入 `--image`，仍加载配置用于输出一致的诊断上下文，但跳过实时截图。
2. 实时模式下 `SquareScreenCapture.capture()` 返回 raw minimap frame；静态模式下 `cv2.imread()` 读取每个 `--image` 指定图片。两种输入都必须是未经过定位特征图后处理的事件图标层。
3. 未传 `--portal-feature-detector` 时，`event_icon_probe.probe_frame()` 对每个 `--template` 调用 `core.events.detectors.template_matcher.match_single_template()`，执行多尺度灰度+边缘匹配。
4. 传入 `--portal-feature-detector` 时，脚本调用 `features.torchlight.portal.minimap_feature_matcher.build_feature_templates()` 从模板中抠出蓝色本体二值特征，再调用 `match_portal_features()` 在 raw frame 的蓝色二值图上匹配。
5. 传入 `--portal-shape-color-detector` 时，脚本调用 `features.torchlight.portal.minimap_shape_color.match_portal_shape_color()`，同时输出蓝色核心、白/灰外环、组合形状 mask、debug 框图和候选裁剪。
6. `core.events.detectors.template_matcher.merge_hits()`、`minimap_feature_matcher.merge_feature_hits()` 或 `minimap_shape_color.merge_shape_color_hits()` 合并不同模板/尺度对同一图标的重复命中。
7. 脚本保存 raw/debug 图片并打印每个 accepted/rejected hit；若无 accepted hit，则打印每个模板的 best candidate、feature detector 空结果或 shape+color reject reasons，用于确认失败发生在背景模板匹配、蓝色本体特征、外环/轮廓过滤、颜色过滤还是后续事件定位层。

### Flow: 大画面传送门探针
1. `portal_screen_probe.main()` 设置 DPI awareness，枚举 `UnrealWindow` / `Torchlight` 窗口或使用手工 `--rect`。
2. `SquareScreenCapture.capture()` 抓取整块主游戏窗口画面。
3. `portal_screen_probe.build_blue_glow_mask()` 提取蓝/青/紫发光区域。
4. `portal_screen_probe.detect_portal_candidates()` 生成宽松候选，并计算面积、发光占比、圆度、宽高比和综合分。
5. `portal_screen_probe.is_strict_portal_candidate()` 将候选收紧为绿色 accepted 传送门实体；非严格候选以橙色框输出，只供调参。
6. 脚本保存 raw/mask/debug 图片和 `last_probe_source.json`，后续事件处理器可复用参数资产。

### Flow: 事件管理 UI 和地图标记
1. `NavigationModeWidget.load_map()` 成功后调用 `_initialize_event_system()`，读取当前地图 `event_config.json`，创建 `EventCoordinator` 和 `GameWindowCaptureProvider`。
2. 用户点击“事件管理”按钮时，`toggle_event_dialog()` 调用 `_refresh_event_dialog()`，把 registry/config/coordinator/map_name 传给 `EventManagerDialog.set_context()`。
3. `EventManagerDialog.refresh()` 调用 `build_tui_event_options()` 枚举完整事件包，并从 `EventCoordinator.tasks()` 读取运行时任务；导航循环中的实时更新改走 `refresh_tasks()`，只读取运行时任务。
4. 用户勾选全局/单个事件时，dialog 更新 `EventSystemConfig` 内存态并发出 `config_changed`。
5. `NavigationModeWidget._on_event_config_changed()` 将配置写回 coordinator，清空旧事件 marker，并打印事件配置日志。
6. 用户点击“测试事件流程”时，`EventManagerDialog.manual_test_requested` 触发 `NavigationModeWidget._run_manual_event_test()`；按钮状态由 `ManualEventTestController` 同步，导航循环未运行时先启动定位循环。
7. 用户点击“刷新事件状态”时，`EventManagerDialog.reset_events_requested` 触发 `NavigationModeWidget._reset_event_state()`；该函数停止手工事件测试，枚举当前配置与 registry 中的事件类型并逐一调用 `EventCoordinator.reset_event_type()`，随后刷新任务表和地图 marker。
8. 导航循环定位成功后构造 `EventTick` 并调用 `EventCoordinator.observe()`；该阶段只检测 raw minimap 图标、合并 memory、把最新任务快照写入 `tick.event_tasks`、选择显示任务，不执行 handler。
9. 自动导航或手动事件测试启用时，UI runtime 构造 `NavigationUpdateContext` 并调用 `NavigationTaskController.update_context()`，控制器从 `EventCoordinator.tasks()` 获取 pending/running event tasks，并把它们作为动态必经点和 required/exit 一起调度；手工测试通过 `manual_event_only=True` 只选择事件任务。
10. 被选中的事件任务通过 `EventCoordinator.run_task(task_id, tick)` 推进 handler；handler 返回 `MOVE_TO` 时复用 `MovementExecutor.step()` 规划事件路径和 subgoal，返回 `PRESS_KEY/CLICK_SCREEN` 时直接转成 `NavigationIntent`。
11. `NavigationRuntimeFrameLoop._execute_navigation_intent()` 统一消费事件和普通导航的移动/点击/按键；终态事件 action 会让手动测试按钮自动停止，自动导航则从下一帧按当前位置重新调度 required/event/exit。
12. `NavigationModeWidget._render_event_overlay()` 从 `EventCoordinator.overlays()` 读取启用事件任务，并让注入的 overlay provider 把业务调试状态转换为 `EventCircleOverlay`；通用 renderer 只绘制事件圆点、状态文本和领域中立图元。
13. 用户点击保存时，`_save_event_config()` 调用 `save_event_config()` 写入当前地图 `event_config.json`。

### Flow: 事件工作台保存与版本化
1. `gui/modes/events/workbench.py::EventWorkbenchPage._save()` 输入 Qt route cells 与 `events: list[dict]`，输出 `routes_data: list[dict]`；副作用仅更新页面 buffer/status。
2. `core/runtime/event_service/service.py::EventWorkbenchService.save(events, routes)` 输入两个 iterable，在 `RLock` 内调用仓库并返回 `list[dict]` 权威版本；副作用写服务日志并热重载 router/definitions。
3. `core/events/automation/definitions.py::EventDefinitionRepository.save_local(records)` 输入 definition drafts，输出活动 versioned records；副作用写 `events.json`，内容变化/删除 revision+1，新记录生成 ID，缺失旧记录写 tombstone。
4. `core/events/automation/routes.py::EventRouteRepository.save(routes)` 输入 mapping/typed routes，输出 `None`；副作用规范化后写 `routes.json`。
5. `service.py::_reload_configuration()` 重新加载 typed routes/definitions；`execution.py::replace_definitions()` 输入 `dict[event_id, ExecutableEventDefinition]`，使下一次启动使用新定义但不改运行中 lifecycle 快照。
6. `EventWorkbenchPage._save()` 接收保存后的 records，替换页面 `events` 并重新渲染版本号。

### Flow: 本机热键到 Host controller state
1. `EventWorkbenchPage._toggle_runtime()` 输入用户按钮命令，保存配置后调用 `service.set_local_running(True)`；输出仅为 UI 状态刷新。
2. worker `EventWorkbenchService._run()` 调用 `tick_once()`；`HostEventBridge.status()` 经 `sync.status` 返回 `{deviceId, peers}`，必要时 `set_device_id()` 重绑本机 owner。
3. `_dispatch_local_triggers()` 把 `EventRouter.triggers(): tuple[str]` 传入 `HotkeyTriggerSource.poll()`；输出一次按下边沿 trigger tuple，副作用仅更新热键 pressed set。
4. `EventRouter.dispatches(trigger)` 输入 normalized trigger，输出 `EventDispatch(event_name, controllers, remote=False)`，无 IO。
5. `EventDefinitionRepository.local_key(event_name)` 输出 stable event ID；`EventExecutionRuntime.start("event:local", id, controllers)` 创建/启动每个 `(source, controller)` session。
6. `EventExecutionRuntime.tick()` 输出 `EventStateFrame(source, controller, state)`；state 包含 buttons、triggers、left/right stick 的完整 neutral-safe 字段。
7. `HostEventBridge.write_state(frame, ttl_ms=120)` 发送 `event.state`；Host 按 controller+source 保存 TTL 状态并合并到 XInput report。

### Flow: A -> B/C 事件目录与广播
1. A 的本机 trigger 经 `EventRouter` 输出 `remote=True` dispatch，进入 `EventWorkbenchService._broadcast()`。
2. `EventDefinitionRepository.local_by_name()` 输出含 `id/revision/owner` 的本机记录；`catalog_payload()` 输出 `{deviceId,catalogRevision,catalogHash,events,definitions}`，definitions 含活动记录和 tombstone。
3. `_broadcast()` 为每个 data-only peer 独立调用 `HostEventBridge.publish_catalog(peer_id, catalog)` -> `sync.share.catalog`，再调用 `send_event(peer_id, payload)` -> `sync.share.event`；payload 字段为 `name,eventId,eventRevision,targets,deadlineMs,deviceId`，deadline 使用 Host 时钟 +500ms。
4. 某个 peer 抛异常时记录 `peer_errors` 并继续后续 peer；至少一个成功则本次 dispatch 返回 True。这个隔离保证 B 失败不阻断 C。
5. B/C 的 `HostEventBridge.drain_catalogs()` 单独调用 `sync.share.catalog_drain`；`EventStore.apply_remote()` 只接受更高 revision，写 `remote_events.json`，tombstone 使旧远程事件不可见。
6. B/C 的 `HostEventBridge.drain_events()` 调用 `sync.share.drain`；`_receive_remote_events()` 校验 `remainingMs>0`，经 `resolve_shared_key()` 获得 stable ID，并以 `event:remote` 启动目标 controller session。
7. 远程 session 与本机 session 汇入同一个 `EventExecutionRuntime.tick()`，但 key 含 source/controller；随后 `event.state` 写 Host，游戏输入效果由既有 Host/XInput 链完成。

### Flow: 事件工作台直接远程发送
1. `EventWorkbenchPage._send_remote_event()` 输入 device text、event text、controller combo，将 combo 转为 `(1,)` / `(2,)` / `(1,2)`。
2. `EventWorkbenchService.send_remote_event()` 校验非空目标/名称和 controller 范围，创建独立 bridge 并以 2 秒 timeout 连接。
3. `HostEventBridge.status()` 返回 peers；服务只接受 connected+syncing+dataOnly 的目标 device ID。
4. 服务从目标 owner 的 remote records、本机同名记录或 visible fallback 中选择 event ID/revision，构造 Host 时钟 +250ms payload。
5. `HostEventBridge.send_event()` 发送 `sync.share.event` 并返回 reply；`finally` 无条件关闭短连接。GUI 捕获异常并渲染成功/失败，不理解协议。

## 7. 外部集成详情
当前物理集成边界：

- Python Host client：`src/auto_modules/adapters/virtual_gamepad/virtual_gamepad_client.py`，默认 named pipe `AutoModules.VirtualGamepad.v1`；具体 action connection 由 `connect_action_adapter(timeout=5.0)` 建立，连接失败抛 `VirtualGamepadError`，不自动启动 Host。
- 程序手柄 lease：`adapters/virtual_gamepad/program_output.py`，TTL 限制 `1..300ms`；client request 无内部重试，worker/application 捕获后进入既有安全停止。
- Follow share wire：`adapters/host/follow_transport.py`；position/event 最大接受窗口 500ms，单条 malformed inbound 丢弃，IPC 失败向上传播。
- Win32 hotkeys：`adapters/windows/hotkeys.py`；具体 `GetAsyncKeyState` 只在 adapter 内，application 只消费按下边沿。
- OCR backend：`adapters/perception/rapidocr.py` 与 `rapidocr_models.py`；core perception 不导入具体 provider。
- 开发资源：`resources/`；开发可写数据：`data/`；安装态资源/data 由 `AUTO_MODULES_RESOURCE_DIR`、`AUTO_MODULES_DATA_DIR` 明确覆盖。
- C# Launcher path：`LauncherPaths` 以 `services/virtual_gamepad` 为 ModuleRoot，以 repository parent 为 WorkspaceRoot；`.venv`、workspace-local .NET、`src` 三者不得混用根层级。
- C# build/test：系统默认 `dotnet` 未配置 SDK；`D:\ACloud\dotnet-sdk2\dotnet.exe` 提供 .NET 8.0.424。LAN/Host 测试用该绝对路径运行，未启动真实 Host 或设备；Launcher/Installer 仍需另行验证。

`src/auto_modules/bootstrap/main.py` 拥有 Windows 启动前置：先配置 UTF-8 输出和 `data_root()/logs/runtime.log`，随后默认 `FreeConsole()`，再设置 DPI awareness、检测管理员权限；若不是管理员，则通过 `ShellExecuteW(..., "runas", pythonw.exe, ...)` 触发 UAC 重新启动根 `main.py` 并退出原进程。管理员进程获取基于 repository path 的 Win32 mutex 单实例锁，并扫描已有 `实时小地图拼接系统` 主窗口。默认 GUI 启动不保留控制台；设置 `MINIMAP_DEBUG_CONSOLE=1` 时保留控制台。真实游戏输入依赖管理员完整性级别。
`data/logs/runtime.log` 每次进程启动都会重建；事件系统另有 `data/logs/event_runtime.log` 和 per-run logs。安装态两者位于 `AUTO_MODULES_DATA_DIR/logs`。

`InputDriver.click(x, y)`：由 `MotionController._execute_click()` 的 `win32_mouse_event` 后端调用，执行 `SetCursorPos(x, y)` 后用 Win32 `mouse_event` 分开发送 left-down/left-up。该路径来自旧脚本 `t2.py` 的可用实现，当前是游戏点击主后端。

`pydirectinput.click(x, y)`：仍作为 `MotionController` 的异常兜底和诊断工具保留。失败风险包括游戏窗口未聚焦、坐标在窗口外、权限/输入钩子被游戏屏蔽。

`pydirectinput.press(key)`：由 `MotionController.press_key()` 在事件 `PRESS_KEY` 动作中调用，目前主要服务传送门事件配置为按键交互时的 `D` 键。它同样依赖管理员权限和正确前台窗口。

`utils/event_icon_probe.py`：独立事件识别探针，依赖 `core.platform.SquareScreenCapture`、OpenCV 模板匹配和 portal 蓝色本体 feature matcher package。真实游戏窗口下需要管理员权限才能可靠捕获 raw minimap；非管理员权限可能返回黑帧，不应误判为识别算法失败。静态 `--image` 模式不依赖截图权限，适合先验证模板资产自身是否覆盖某个用户截图外观；`--portal-feature-detector` 用于验证运行时传送门识别算法。

`utils/portal_screen_probe.py`：独立大画面实体识别探针，依赖 Windows 窗口枚举、DPI awareness、`SquareScreenCapture` 和 OpenCV HSV/轮廓分析。当前只作为传送门事件第二阶段确认技术资产；当传送门实体离开视野或被遮挡时，零 accepted 是正确输出。

`tools/probes/install_perception_ocr_model.py`：显式可执行的可选 OCR 模型安装器。脚本先把项目 `src` 加入 `sys.path`，然后根据 `rapidocr_models` 清单将命名 ONNX 模型下载到指定本地目录；只有临时下载文件的 SHA-256 与清单一致时才通过同目录 `os.replace()` 原子安装。它不会在感知包导入或每帧推理时运行，目标目录 `resources/assets/perception_models/` 不进入 Git。

### Optional integration: `rapidocr-onnxruntime`

`core/perception/providers/rapidocr.py::RapidOcrProvider._create_default_backend()` is the runtime integration point. Dependency configuration is `requirements-ocr.txt`, deliberately separate from `requirements.txt`; package import and ONNX model creation occur lazily on the first `recognize()` call. Recognition models are separate explicit resources: `rapidocr_models.resolve_rapidocr_engine_options()` verifies a named local ONNX file and produces construction options, while `tools/probes/install_perception_ocr_model.py` owns the only download path. Therefore the provider itself has no network request, fixed timeout, retry loop, screen capture, or background service. A missing package, missing `RapidOCR` export, uninstalled/corrupt selected model, or engine initialization failure becomes `ProviderUnavailableError`; a per-frame backend exception or malformed `(rows, timings)` output becomes `ProviderError` and reaches `DetectorRunner`, which records that one algorithm instance's error while allowing others to run. Applications that need a retry policy own it above this pure provider boundary.

The provider's supported call settings come from one OCR profile instance's `provider_parameters`: optional `roi`, result `language` label, and `backend_options` passed to RapidOCR. `language` is not a model-selection command. UI/application composition must intentionally resolve a named model, instantiate `RapidOcrProvider`, and inject it; the catalog descriptor `ocr.rapidocr_onnxruntime` remains `unavailable` by default even if both package and model exist, so importing the generic perception core can never start a model unexpectedly.

### Event Host / LAN integration
连接配置来源：默认 `HostEventBridge` 延迟构造 `VirtualGamepadClient`，使用现有命名管道默认 endpoint；测试/其他组合根可注入 `client_factory`。服务从 `sync.status.status.deviceId` 获得真实 owner，从 `peers` 只选择 `connected && syncing && dataOnly` 会话。
超时与时序：bridge 默认连接 timeout 为 2.0 秒；worker loop 默认 0.02 秒；catalog publish interval 默认 2.0 秒；`event.state` TTL 为 120ms；路由 fanout deadline 为 Host clock +500ms；直接发送为 Host clock +250ms。
命令契约：状态 `sync.status`；目录发送/接收 `sync.share.catalog` / `sync.share.catalog_drain`；事件发送/接收 `sync.share.event` / `sync.share.drain`；controller source 输出/清理 `event.state` / `event.clear`。事件和目录 drain 必须分离。
失败行为：未连接 bridge 抛 `RuntimeError`；client connect/request 异常向上传播。worker 捕获任意 `Exception`，写 `EventWorkbenchStatus.error`，清理 bridge/source，等待 0.5 秒后重试；shutdown 或 stop wait 会中断等待。A->B/C publish/send 单 peer 失败被 `_broadcast()` 捕获并追加 `peer_errors`，不重试该 peer、不阻断后续 peer。直接发送不重试，`finally` 关闭短连接。

### Event configuration persistence
配置来源：`<event-root>/events.json`、`remote_events.json`、`routes.json`；GUI 默认 root 为 workspace data root 下 `configs/events`，测试注入临时 root。
失败行为：events/remote legacy JSON 缺失或解析失败由 `EventStore` 降级为空；`routes.json` 缺失/非法 JSON 降级为空，但顶层不是 list 或 record 字段非法抛 `ValueError`。保存时目录自动创建，写入 `OSError` 向上传播。
版本策略：本机新事件生成 UUID/revision 1；定义内容变化 revision+1；未变化保持原 revision；删除写 tombstone revision+1；远程只应用同 ID 的更高 revision。Host device ID 可用时 owner 重绑不增加 revision。

### Windows hotkey integration
配置来源：route trigger names；支持 F1-F12、A-Z、SPACE、UP/DOWN/LEFT/RIGHT。
失败行为：未知名字忽略且不调用平台；非 Windows 使用默认读取器时抛 `RuntimeError`，worker 捕获后进入 0.5 秒连接/运行重试。测试通过注入 reader 完全绕过 Win32。
重试策略：热键读取本身无独立重试；由 service worker 顶层统一重试。按住只 emit 一次，松开后重新武装。

## 8. 数据模型与契约
### PoE2 multiframe localization contracts

`MultiFrameEvidence` 固定一帧 `HybridFrame`、`FrameDisplacement`、`local_offset:(float,float)`、`is_keyframe:bool`、`segment_id:int`，并可携带同尺寸 `observed_mask:uint8[H,W]` 与 `raw_frame:uint8[H,W,C]`。数组构造后只读；wall 与 observed 坐标均为局部截图像素。

`PositionEstimate` 使用 native terrain 坐标，字段为 `status`、可选 `position/velocity/covariance`、`candidate_regions`、`instance_id`、`registration_version`、`evidence_version`、`fresh`、`age_ms`、`source`、`reason`、`diagnostics`。`status=confirmed` 不自动等于可执行；导航 adapter 还必须检查 fresh、age、instance 和 version。

`RegistrationRequest.token = (instance_id, recovery_revision, evidence_version, segment_id)` 是后台结果提交的完整版本门。任何换图、恢复、窗口更新或断链都会让旧结果失效。

多帧实验唯一交换坐标是原始 native terrain `(x=column,y=row)`；`Poe2MonitorConfig` 不再暴露 `map_rotation/map_flip_*`，旧 JSON 键只被忽略。`SimilarityTransform2D` 只描述视觉局部点到 native terrain 的 `L -> N` 映射，是方向、镜像、比例和平移的唯一事实源；展示层只有在 registration version 栅栏通过时应用其逆方向变换保持地图、marker 和轨迹一致。schema 3 archive 只允许 `coordinate_space=native`。

### LAN persisted preferences and capability update

`Preferences` 除 `Name/BindAddress/Port/Controllers/RateHz` 外保存 `RecoveryPeers:string[]?`、`RecoveryCapabilities:Dictionary<string,string[]>?`、`Mode:string`、`ReceivePositions:bool`、`ReceiveEvents:bool`、`EnabledControllers:int[]?`。旧文件缺省 mode 为 off。配对证书指纹由 `trusted.json` 的 `TrustedPeer.DeviceId` 固定；活跃密钥和 grant 不持久化。`capability-update` 的 `controllers` 与 flags 一起协商，`capability-ack` 必须匹配 requestId/flags/scope 并含两个 grants；`capability-reject` 只保留错误，不改变已授能力。
`sync.suspend` 不写回上述恢复字段，进程内 `_suspendedPeers` 阻止重新接收；显式 `sync.stop` 才删除相应 `RecoveryPeers/RecoveryCapabilities`。

### Repository path contract

`package_root() -> Path` 固定为 imported `auto_modules` package directory。`repository_root() -> Path` 返回源码仓库或安装态 `app` 根。`resource_root()` 优先 `AUTO_MODULES_RESOURCE_DIR`，否则 `<repository>/resources`；`data_root()` 优先 `AUTO_MODULES_DATA_DIR`，否则 `<repository>/data`。环境变量值统一 `resolve()`；业务模块不自行拼用户 profile 或向 resources 写入。

### Follow sharing contracts

`SharedPosition(device_id: str, actor_id: str, map_id: str, map_version: str, position: tuple[float,float], confidence: float, captured_at_ms: int, session_id: str="")` 是 device-neutral immutable observation。`captured_at_ms` 属于当前 Python caller 的 local monotonic clock；adapter 负责 age/deadline translation。

`SharedEvent(device_id: str, event_id: str, name: str, targets: tuple[str,...], deadline_ms: int, session_id: str="")` 是解析后的 local-deadline event。core controller 不接触 Host `remainingMs/deadlineMs` 字段。

`ProgramGamepadOutput` 的 wire contract 是 `program.acquire -> token`、`program.state(controller,token,ttlMs,deadlineMs,state)`、`program.release(controller,token)`。state 总是完整包含 buttons、两个 trigger 和两组 stick；TTL 最大 300ms，Host 是最终失效/归零责任方。

### `RapidOcrProvider` provider contract

`RapidOcrProvider(engine_options: Mapping[str, Any] | None, backend_factory: Callable[[], Any] | None)` is runtime composition state, never profile JSON. `recognize(frame: FrameContext, parameters: Mapping[str, Any] | None) -> tuple[OcrSpan, ...]` accepts only `roi`, `language`, and `backend_options` in `parameters`; all inputs are copied before use. `roi` is a `BoundingBox`, four-number sequence, or mapping with finite `left/top/width/height` and positive width/height. `language` is an optional non-empty string label. `backend_options` is a mapping passed to the backend per invocation.

Each output `OcrSpan` uses `frame.coordinate_space` and has a positive-area `BoundingBox` enclosing its translated polygon. Metadata always contains `provider_id="ocr.rapidocr_onnxruntime"`, `polygon: tuple[tuple[float, float], ...]`, and `elapsed_seconds: tuple[float, ...]`; ROI calls additionally contain actual clipped integer `roi`. Missing runtime package/model is `ProviderUnavailableError`; bad input, crop, backend result, polygon, timing, or confidence has an explicit `TypeError`, `ValueError`, or `ProviderError` boundary.

### `NavConfig`
字段：
`draw_scale: float` - 建图/定位地图缩放。
`monitor_logical_center: tuple[int, int] | None` - 小地图截图中心，服务定位。
`monitor_region: dict | None` - 拉框截图区域，服务定位。
`monitor_size: int` - 正方形截图边长，服务定位。
`fps: int` - 导航循环刷新率。
`game_screen_center: tuple[int, int] | None` - 主游戏画面人物屏幕中心，服务鼠标点击。
`movement_scale_factor: float` - 地图距离到原始屏幕点击半径的比例。
`game_view_map_size: int` - 橙色真实主画面可见/可交互框在地图坐标中的边长。
`movement_min_click_radius: int` - 屏幕点击最小半径，防止点在人物脚下。
`movement_max_click_radius: int` - 屏幕点击最大半径，防止点出真实可交互区域。
`auto_click_cooldown_ms: int` - 自动导航两次真实点击之间的最小间隔，默认 260ms。
`auto_min_click_target_delta: float` - 冷却结束后，子目标至少变化多少地图像素才重复点击，默认 8.0。
`anchor_arrival_radius: int` - 辅助锚点到达/消费半径，默认 26；只影响 guide_points 锚点推进，不改变必经点完成半径。
`movement_progress_timeout_ms: int` - 路径进度不足时触发卡住恢复的时间窗口，默认 1200ms。
`movement_min_progress_delta: float` - 卡住判定窗口内至少需要前进的路径距离，默认 12.0。
`movement_max_recover_attempts: int` - 单次路径上允许的恢复探测次数，默认 2，耗尽后强制重规划。
`movement_path_deviation_threshold: float` - 人物偏离当前规划路径多少地图像素时重规划，默认 96.0。
`bottom_click_guard_pixels: int` - 屏幕底部禁点区高度，默认 300px，设为 0 可关闭；只在点击落入底部 UI 时沿原方向缩短半径。
`nav_wall_erode_iterations: int` - 从原始 `wall_layer` 派生 A* 专用墙图时的腐蚀次数，默认 1；只影响寻路，不影响定位/事件配准。
`path_start_clear_radius: int` - A* 网格构建后清空玩家起点附近障碍的地图像素半径，默认 30。
`path_walkable_snap_radius: int` - A* 起终点落在障碍内时搜索最近可走点的地图像素半径，默认 18。
`coordinate_visual_check_interval_ms: int` - F2F 跟踪时做截图-大地图视觉一致性校验的间隔，默认 800ms；0 表示关闭自动视觉校验。
`coordinate_visual_check_margin: int` - 围绕当前导航人物位置做模板校验的搜索边距，默认 140 地图像素。
`coordinate_visual_match_min_confidence: float` - 视觉校验最佳匹配最低置信度，默认 0.72，低于该值不作为偏移证据。
`coordinate_visual_mismatch_threshold: float` - 视觉最佳贴图位置与当前导航人物点的距离阈值，默认 24 地图像素。
`coordinate_visual_mismatch_frames: int` - 连续多少次视觉校验偏移才触发强制重定位，默认 3。

### `EventSystemConfig`
字段：
`enabled: bool` - 全局事件系统开关。
`profile: str` - 当前事件配置方案名，默认 `default`。
`events: dict` - 每个完整事件包的配置，key 为事件类型，例如 `portal`。
`raw: dict` - 从 `event_config.json` 读取并保留的原始配置，用于保存时保留未知字段。

`portal` 默认配置字段：
`enabled: bool` - 是否启用传送门完整事件。
`priority: int` - 多事件调度优先级。
`interaction: str` - 交互方式，`click` 或 `key`，默认 `key`。
`detector_mode: str` - 小地图传送门识别算法，支持 `template`、`feature`、`feature_then_template`、`shape_color`。当前默认 `shape_color`，用于更严格的形状+颜色联合识别；旧配置缺少 `detector_mode` 但含 `feature_detector_enabled` 时仍兼容旧 feature/template 行为。
`minimap_threshold: float` - 小地图事件识别阈值；portal 当前优先用于蓝色本体 feature score，整块模板兜底也复用该值。
`max_candidates: int` - 单帧最多接受的传送门候选数，默认 2。
`minimap_nms_radius: int` - detector conversion 层的小地图局部命中合并半径，默认 28；用于抑制同一传送门图标的多模板/多尺度重复 hit。
`min_blue_ratio: float` - 模板 bbox 周围必须满足的蓝/青传送门像素比例，过滤白墙误匹配。
`feature_hue_min: int` / `feature_hue_max: int` - portal 本体特征 HSV hue 范围，默认 82..136。
`feature_sat_min: int` / `feature_val_min: int` - portal 本体特征 HSV 饱和度/亮度下限，默认 55/95。
`feature_min_blue_pixels: int` / `feature_max_blue_pixels: int` - portal 候选窗口内蓝色本体像素数量范围，默认 36..420；`feature_max_blue_pixels=0` 表示不设上限。
`shape_outer_sat_max: int` / `shape_outer_val_min: int` - shape_color 模式下白/灰外环 HSV 阈值。
`shape_min_blue_score: float` / `shape_min_outer_score: float` / `shape_min_shape_score: float` - shape_color 模式下蓝色核心、外环和组合形状的最低 F1-like 分数。
`shape_min_outer_pixels: int` - shape_color 模式下候选框内必须包含的最少白/灰外环像素。
`stable_frames: int` - 事件定位稳定帧数，默认 3。
`localization_cluster_radius: int` - 多帧投影稳定簇合并半径，当前默认 96；日志中 70-85px 级别的同门抖动应进入同一簇。
`dedupe_radius: int` - memory 合并同类事件任务的半径，当前默认 96；真实相邻双门被合并时可在事件面板调小。
`arrival_radius: int` - 玩家距离事件点多少地图像素内开始主画面确认。
`interact_radius: int` - 玩家距离传送门地图点多少地图像素内才进入交互阶段；事件管理页下限为 1。
`portal_point_click_wait_ms: int` - 进入交互阶段后，先点击一次映射传送门点，再等待多少毫秒按 `D`。
`retry_limit: int` - 失败后的重试次数。
`cooldown_ms: int` - 完成后的同位置冷却时间。
`cooldown_radius: int` - 完成后屏蔽附近同类传送门的地图半径，防止成对传送门来回触发。
`exit_complete_radius: int` - 传送成功后，将角色新位置附近多少地图像素内的同类传送门标记为出口 completed；handler 也用它判断是否已落在另一个已知传送门附近。
`type_cooldown_ms: int` - 完成后短时间屏蔽所有同类传送门新观察，用于跨门瞬间的稳定期。
`post_interact_wait_ms: int` - 按 D/点击后等待画面稳定的最短时间。
`teleport_timeout_ms: int` - 等待传送完成的最长时间。
`teleport_min_distance: int` - 用地图坐标判断传送成功的最小位置变化距离。
`environment_change_threshold: float` - 用玩家周边小地图截图签名判断传送成功的变化阈值。

### `ExecutableEventDefinition`
`event_id: str` - 稳定 catalog ID，也是 execution definition key。
`name: str` - 用户显示/legacy fallback 名称，必须非空。
`owner_device_id: str` - 定义所有者设备。
`revision: int` - 单 ID 单调版本；内容修改/删除增加，owner 重绑不增加。
`tracks: tuple[ActionTrack, ...]` - 不可变轨道快照。
`steps: tuple[dict, ...]` - 深拷贝的复合步骤快照。
`max_runs: int | None`、`loop: bool`、`end_ms: int | None` - lifecycle 限制。

### Catalog record contract
`id: str`、`name: str`、`owner_device_id: str`、`revision: int>=1`、`updated_at: str`、`deleted: bool`、`content_hash: str` 加 definition 字段。活动读取过滤 `deleted=True`；catalog transport 保留 tombstone 以传播删除。owner 是设备元数据，不属于 definition hash。

### `EventRoute` / `EventDispatch`
`EventRoute.source/target: str` - 规范值仅 `local|paired`。
`trigger: str` - 大写非空边沿名字。
`event_name: str` - 非空业务事件名称。
`controllers: tuple[int, ...]` - 只允许 `(1,)`、`(2,)`、`(1,2)`。
`EventDispatch` 只保留 `event_name/controllers/remote`，不携带 client、peer 或 widget。

### `EventStateFrame`
`source: str` - 规范为 `event:<name>`，当前服务使用 `event:local` / `event:remote`。
`controller: int` - 1 或 2。
`state: dict` - `state_from_inputs()` 生成的完整 XInput 状态，至少包括 buttons、left/right trigger、left/right stick axes；neutral frame 所有值为 0。

### `EventWorkbenchStatus`
`local_running: bool`、`remote_running: bool` - 两个触发入口开关，不代表 service thread 是否存在。
`connected: bool` - 长期 Host bridge 最近一次 tick 是否连接成功。
`peer_count: int` - 当前 connected+syncing+dataOnly peer 数。
`trigger_count: int`、`receive_count: int` - 本机路由成功次数和远程 inbox 成功启动次数。
`last_event: str`、`error: str`、`peer_errors: tuple[str, ...]` - UI 只读状态；单 peer fanout 失败与服务级 error 分离。

### Host event payload contract
`sync.share.event` payload：`deviceId: str`、`name: str`、`eventId: str`、`eventRevision: int`、`targets: list[str]`、`deadlineMs: int`。
`event.state` payload：`controller: int`、`source: str`、`state: dict`、`ttlMs: int`。
`event.clear` payload：`controller: int`、`source: str`。
`sync.share.catalog` payload：`deviceId: str`、`catalog: {deviceId,catalogRevision,catalogHash,events,definitions}`。

## 9. 风险与隐患登记
FollowProbe lifecycle invariant: arm occurs only after runtime, role, and output construction succeeds; invalid follow starts leave the target source disarmed.
审计补充：恢复入口统一接受两类安全帧：完整 `tracking`，或 `degraded` 且 `diagnostics.wall_trusted=True`、所需角色仍有 bounded `players` 估计。实时跟随恢复使用 300ms 新鲜度门；超龄帧只等待下一帧并保留 recovery context，不消费上下文。双人同目标与程序移动恢复使用同一状态判定，避免 marker 短暂重叠造成恢复会话悬挂。
P1 - `Poe2CaptureTestPage.run_dual_first_frame_experiment()` 首帧搜索和 oriented map 构造仍在 GUI 线程；实时双人帧已迁移到 `Poe2DualMotionWorker`，但启动/恢复时的大范围注册仍可能短暂阻塞。触发条件：地图很大、双人近距离首帧需要多候选搜索。建议：后续把首帧/恢复注册也搬到带 generation 的 worker，且保持一次 revision 一次内存读取。

Resolved in experiment 2026-10-04 - `Poe2CaptureTestPage._start_dual_motion()` / `start_follow_experiment()` 现在为每个 live-follow role 装载 750ms 的 `CommandRoleTracker` 输出—视觉相位窗口；窗口内仅放宽未显式指定协方差的观测，过期后恢复 `9 native²` 稳态门。触发条件仍是恢复后第一枚程序脉冲已写入而截图尚未更新；对应 tracker/page 回归已覆盖窗口内接受和窗口外跳变拒绝。

Resolved in experiment 2026-10-04 - `_start_dual_motion()` 的 recovery 失败和 tracker 构造异常统一调用 `_clear_dual_recovery_contexts()`，原子清空 program-probe、dual-follow、dual-target 三类延迟恢复 context；同一地图重启不会消费上一轮失败状态。

Resolved in experiment 2026-10-04 - `start_follow_experiment()` 在构造新 runtime 前检测并停止旧 follow timer/runtime/output，恢复回调、快速重复调用和外部调用均遵守单一输出所有权。

Resolved 2026-10-04 - `Poe2CaptureTestPage._on_dual_first_frame_worker_result()` 收到 accepted 后以 `first_frame_ready=True` 重启 `_start_dual_motion()`，旧逻辑仍因 `recovery=True` 将缓存 result 置空，随后误记 `first_frame_rejected` 并清理 follow recovery context。触发条件：实时跟随首帧视觉失配后进入后台恢复且 worker 成功；实机复现为 `worker_result status=accepted` 紧接 `program_probe.relocalization_failed`。现在 first-frame-ready 路径消费 accepted bundle 缓存，新增状态交接日志和回归测试。

P1 - `Poe2CaptureTestPage._maybe_resume_dual_follow_after_relocalization()` 与 `start_follow_experiment()` 对 live frame 使用不同的新鲜度门（700ms vs 300ms）。触发条件：恢复帧年龄落在 301–700ms；前者进入重建，后者返回 `start_waiting`，随后 recovery context 被误清理。建议统一门限或让恢复等待下一帧，不把等待误报为 runtime rebuild failure。

P1 - `Poe2CaptureTestPage._request_live_follow_reanchor()` 绕过 `_dual_last_recovery_at_ms` 的统一冷却。触发条件：跟随侧视觉拒绝、预测无界、领队失踪或无安全候选直接调用该入口；同一故障可重复触发内存读取与后台首帧注册。建议所有 recovery reason 进入同一个 revision/cooldown 门。

Resolved 2026-10-06 - `_request_live_follow_reanchor()`、`_continue_live_follow_after_dual_failure()` 和双人 worker recovery revision 现在共享实时跟随 session 的 recovery episode 锁。首次失配打开 episode；后续 tick 只保持有界预测并按 25 次节流记录，不再次 claim、释放输出或调度 retry。`_sync_live_follow_from_fresh_frame()`、有效视觉接受/连续性重基线和用户重新启动清除 episode；页面时间冷却继续保留为跨功能预算。回归覆盖同一失配 100 次调用只产生一次 claim/restart，fresh sync 后可再次恢复。

Resolved 2026-10-05 - `Poe2CaptureTestPage._gate_live_follow_foreground()` 统一保护实时角色和地图点击的程序跟随输出。触发条件：工作台按钮点击时 PoE2 不在前台，Host 仍接受 ViGEm 报告而游戏不消费，视觉 marker 不变、command prediction 漂移并触发错误 recovery。现在只释放一次并等待前台恢复，恢复后重置视觉基线；新增页面回归覆盖等待、去重释放和恢复。

Resolved 2026-10-05 - `ProgramGamepadOutput.write()` accepted 日志曾在计算 `remaining_ms` 前使用该局部变量，真实 Host 写入成功后可能抛 `UnboundLocalError` 并让跟随页面停止。现在先计算剩余 TTL 再记录，`tests/test_program_gamepad.py` 7 项通过。

Resolved 2026-10-05 - `SimulatedFollowRuntime._tick_follower()` 预测接近目标路径曾访问控制器不存在的 `command_duration_ms`，在近距离/隐藏 marker 场景触发 tick 异常并释放输出。现在使用公开 `constrained_duration_ms` 并保留 80ms 上限；预测位置仍不确认到达。

Resolved 2026-10-05 - `Poe2CaptureTestPage._sync_live_follow_from_fresh_frame()` 曾用 `actor_id` 写入 `_follow_last_visual_positions`，而 `_tick_follow_experiment_impl()` 用 `RoleId.key` 读取，导致连续视觉步长永远为空、动态速度校正永远不触发并把正常小步计入拒绝次数。现在同步、重基线、领队接受和视觉接受均使用 `RoleId.key`，并保存对应 `captured_at_ms` 作为时间基线；修复后页面跟随回归 83 项通过。

Resolved 2026-10-05 - `CommandRoleTracker.record_output()` 曾在已有视觉速度样本后再次乘 `AdaptiveInputCalibrator.speed_gain`，将同一位移响应重复校准，长期会使命令预测速度偏离实际。现在只有冷启动无视觉样本时使用该倍率；有视觉样本后直接使用限幅 EWMA 实测速度，新增 tracker 回归覆盖 `speed_gain != 1` 的边界。

P1 - `Poe2DualMotionWorker._run()` 只有处理完一帧后才等待 cadence；当 `_capture_one()` 总耗时超过配置 interval 时实际吞吐下降并增加 latest-only 丢帧。触发条件：实机单帧耗时大于 33ms 的 30FPS 配置；可能连锁造成 follow frame-age 门和视觉拒绝。建议先量化各阶段耗时，再做自适应降频/跳帧或缩小处理范围。

Resolved 2026-10-04 - `Poe2DualFirstFrameWorker._run()` 在 `result_available` 后设置 `result_delivered`，cleanup 异常只记录，不再发第二个 `failed`；`Poe2CaptureTestPage._on_dual_first_frame_worker_failed()` 对已摘除 worker 的迟到失败只告警。对应 cleanup 失败回归覆盖 accepted 结果不被遮蔽。

Resolved 2026-10-04 - `Poe2DualMotionWorker._capture_one()` 将 `processed` 写入 `DualMotionFrameResult`，`_drain_dual_motion_worker()` 直接交给 `_render_preview()`，不再重复 preprocess。`ProgramGamepadOutput.write()` 仍是同步 Host 协议调用；`diagnostics()` 已由页面按 5 秒窗口低频调用，并保留 `host_request_ms/diagnostics_elapsed_ms`，后续是否异步化仍需真实耗时证据。

P1 - `Poe2CaptureTestPage.run_dual_first_frame_experiment()` 的首帧/恢复内存读取和注册仍在 GUI 线程；触发条件：地图大、双人近距离首帧候选搜索或 native 读取延迟，单次恢复可能让页面暂时无响应。`stop_dual_motion()` 已改为只发停止并以 `wait(0)` 非阻塞退休，finished 回调负责 deferred restart；后续仍应把首帧/恢复注册搬到带 generation 的后台任务。

P2 - `ProgramGamepadOutput.write()` 在跟随 Qt timer 中仍同步请求 Host；触发条件：Host named-pipe 响应抖动或服务阻塞。adapter 记录 `host_request_ms` 并对 ≥50ms 请求告警，页面把非控制性的 `diagnostics()` 降为首次/每 5 秒一次并记录 `diagnostics_elapsed_ms`；尚未把控制输出异步化或增加协议级超时，后续必须保持每角色 lease、TTL 和停止顺序不变。

Resolved 2026-10-04 - `Poe2CaptureTestPage._tick_follow_experiment_impl()` 的过期帧分支已改为显式边沿状态：首次过期中性释放，连续过期不重复释放/刷 warning，持续 1500ms 只请求一次 `visual_frame_stalled` recovery，新帧恢复后清除状态。对应页面回归覆盖一次释放、一次恢复和重定位触发。

Resolved 2026-10-04 - `Poe2CaptureTestPage._render_dual_motion_state()` 在 follow/dual-target runtime 存在时只走一个 overlay renderer；普通 tracker overlay 不再先绘制后立即覆盖。跟随尚无 observation 时回退显示最新真实人物点。

P1 - `DualVisualTracker._assign()` 在没有互异颜色 profile 时只能按上一帧预测做两人身份分配。触发条件：两人交叉、标记近距离合并或长期遮挡；当前策略会输出 `None` 而不是猜测。复现：合成测试的近距离歧义和颜色交叉案例；建议：实机采集连续原始帧后校准 profile 与最大运动门，不以旧位置冒充新位置。

P1 - `DualVisualTracker.tick()` 的墙体位移和局部纠偏已通过合成回放，尚无同一实例连续双人运动真实样本。触发条件：地图图标动态变化或小地图视口规则与静态平移假设不一致。复现：在实机同时/异步移动两人，记录 `dual_motion.tick` 的质量、状态、可见身份和共同平移；建议：以保存的连续帧做离线重放，校准门槛后再进入正式产品页。

Resolved in experiment - `Poe2DualMotionWorker._offer()` 将 `DualVisualTracker._failed()` 的一次性 revision 独立于 latest-only 图像保存，`Poe2CaptureTestPage._drain_dual_motion_worker()` 消费后先释放输出再重新注册；覆盖边沿帧的假 worker 回归已通过。旧实机会话曾持续 `recovery_required/recovery=False`，但新交付机制尚未经过相同条件实机复验。

P1 - `detect_saturated_marker_observation()` / `DualVisualTracker._assign()` 对与人物同 HSV 的静态小地图标记没有静态/动态消歧。触发条件：蓝色人物与蓝色记录点重叠或靠近，轮廓合并或静态点进入同一颜色 profile；若静态候选持续落在预测门内，仍可能被当成角色。旧实机日志在墙层质量约 `1.0` 时仅分配 P1、P2 缺失；现在有界失明和状态切换证据包只降低瞬时中断并支持诊断，不能证明同色候选已正确识别。建议：实机留存重叠前中后 `occlusion_diagnostics/`，比较原始帧、每 profile mask、候选 bbox/HSV/面积和赋值代价，再评估动态/静态消歧；不要对墙图做人物/地标整块 mask。

Resolved 2026-09-23 - `MultiframeLocalizationCoordinator.evaluate_registration()` 曾让方案 A 在自身 holdout 通过后绕过统一 validator，且 `MultiframeArchive.load()` 曾丢弃 schema 3 estimate；`Poe2CaptureTestPage` 也曾在 evidence 为空时开放保存。现在 A/B 均过统一确认门，archive 可 typed round-trip estimate，UI 与 archive 双层拒绝空证据。对应回归覆盖 anchor/trajectory/holdout、候选选择、archive round-trip 和保存状态。

Resolved 2026-09-23 - 同一多帧 session 重启时曾残留 evidence builder offset/segment 与 A/B 策略缓存，且多帧 composition 未应用 profile recognizer 参数。现在 start/reset 清理会话态和策略态，并在 factory 构造时应用 active profile 参数；实机参数效果仍需按地图采样校准。

P1 - `src/auto_modules/features/poe2/live_terrain/experimental/multiframe_localization/strategy_a.py::StrategyA.evaluate()` 和 `strategy_b.py::StrategyB.update()` 的阈值仍只经合成回放与现有单帧样本间接校准。触发条件：新地图墙体稀疏、对称、线宽差异更大或动态粗块持续遮挡。复现方式：同一实例连续移动后分别运行 A/B，记录错误确认率、native 误差 P50/P95、最佳/次佳 margin 和 holdout error。建议：至少采集多地图真实多帧归档，按调优集/留出集分离校准；实机通过前不替换正式 hybrid runtime。

Resolved in experiment - `StrategyB.update()` 的 45 度方向只作为初始 basin；当前 `SearchLevel` 会在候选周围做有界粗到细角度/比例/平移精化，预计收敛约 1 度。真实多地图精度仍需校准，但不再把方向量化为 45 度。

P2 - `src/auto_modules/features/poe2/live_terrain/experimental/multiframe_localization/state_estimator.py::PositionStateEstimator` 的 covariance 是实验运动模型输出，尚未用真实误差分布统计校准。触发条件：直接用 `safe_radius` 作为导航碰撞保证。复现方式：比较 prediction covariance 与真实 native position residual 的覆盖率。建议：实机标定前只作诊断/保守半径，不宣称概率置信区间。

P2 - `src/auto_modules/features/poe2/live_terrain/experimental/multiframe_localization/session.py::MultiframeLocalizationSession.tick()` 已将注册移到单 worker，但截图、识别和 evidence 构建仍由 Qt timer 同步触发。触发条件：高分辨率小地图或识别预处理超过采样周期。复现方式：记录 frame elapsed 与 UI P50/P95。建议：先用实验面板确认瓶颈，再考虑 latest-frame channel；禁止无界队列积压旧帧。

P2 - `src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py::run_dual_first_frame_experiment()` 的匹配特征仍包含独立圆形地图图标的亮边。触发条件：图标与墙体相接且通用透明度阈值/Canny 将其识别为几何特征。复现方式：比较 `dual_current_raw_after_failure.png` 与同帧无擦除特征图，人物候选约 `(76,155)/(85,148)`，圆环中心约 `(55,155)`。建议：仅在 PoE2 双人实验层建立图标特征验证和像素级过滤，不用人物半径清空，避免误删相连墙体。

已修复 - `DualVisualTracker.tick()` 的无 marker warmup 帧保留墙层静止估计和预测点，但状态改为 `degraded`；实时跟随启动和输出前还拒绝 `warmup_assumed_stationary`。假输出回归验证该帧会释放已取得的控制器，下一可信帧可重新接管；实机时序仍待验收。

已修复 - `stop_dual_motion()` 同时清除状态和 `_latest_dual_captured_at_ms`；重启复用的首帧只初始化 tracker，不携带上一代采集时间。实时跟随仍要求新 worker/同步截图帧的 700ms 时间戳，快速重启回归覆盖该边界。

已修复 - `start_follow_experiment()` 按实际 `selected` 角色校验位置后才创建输出，单人 P2 不再错误地要求 P1；角色初始化纳入输出关闭边界。缺失 P2 与初始化异常的假输出测试均验证没有遗留控制会话。

P2 - `src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py::_tick_dual_target_experiment_impl()` 接受 `degraded` 并允许缺失角色继续沿最后一次预测位置运行，直至对应 `PositionSample` 超过 700ms TTL；`_tick_program_move_probe()` 同样只检查角色点和帧龄，不要求 `tracking`。触发条件：短时 marker 漏检但 tracker 仍保留预测人物点。复现方式：从已 arm 的双人会话送入部分 marker 的 `degraded` 帧并检查输出调用。建议：实机量化 dropout 与运动误差；需要更保守的边界时，对缺失角色立即 neutral/release，另一可见角色保持独立运行。当前链路未实机量化该取舍。

Resolved 2026-09-22 - PoE2 混合定位曾把 `TerrainReference.wall_layer` 的整块 blocked/unknown 区直接交给绝对注册和 `MapRuntime`。触发后 distance field 出现大面积零值，首帧方向多解，局部帧固定得到 `mean_wall_error=0/candidate_margin=0` 并每帧失败，进而周期性消耗内存恢复。现在 `reference_boundary_layer()` 是绝对注册与局部跟踪的共同几何输入；同一实机实例首帧锚点误差降至 `0.66`，后续 11 帧均为 `visual_local`，全程只读内存 1 次。

Resolved 2026-09-22 - `Poe2HybridLocalizationSession.tick()` 过去先截图，再由 `HybridLocalizationController._attempt_absolute()` 执行约 6 秒的内存人物读取。人物移动时，旧截图与读取完成后的新坐标相差约 19 个 terrain grid，恢复候选因此被锚点门拒绝并停在 `RECOVERY_REQUIRED`。现在 session 先调用 `prepare_capture()` 读取并缓存本 revision 锚点，随后立即截图，`update()` 只消费该待配对锚点；正式页面链实机首帧为 `anchored_absolute`，后续 12 帧均为 `visual_local` 且 reads 保持 1。剩余验收边界是实际移动触发后的恢复、多地图和有意遮挡。

Resolved 2026-09-22 - 正式 `Poe2LiveTerrainPage` 曾驱动旧 `Poe2LocalizationRuntime`，而嵌入采集页另持 hybrid timer/session，形成两个位置 owner。现在正式 composition 只注入 `Poe2HybridProductRuntime`，嵌入采集 tab 的 hybrid factory 固定为 `None`，产品窗口内只有 `monitor_timer` 能推进定位。自动测试确认局部视觉失败输出 `RECOVERY_PENDING`，下一 tick 自动增加一次锚点读取并恢复为 `anchored_absolute`；恢复失败后连续 tick 的读取次数保持不变。

Resolved 2026-09-29 - 三条旧寻路测试默认继承 `start_clear_radius=30`，在小图中把待测墙体清掉，属于测试配置与测试意图不符；测试显式设为 0 后，corner-cut、未探索带及薄墙断言通过，通用算法未改。PoE2 跟随 runtime 始终显式设为 0，且墙值改为 0/255。

P1 - PoE2 实验地图点移动页当前点击确认后立即申请 Host lease，且控制 tick 给缓存的 `_latest_dual_state` 重打当前时间戳；若切回游戏耗时或截图停止，可能在错误前台输出或把旧位置当新观测。实机穿门前须加切窗等待、前台/视觉样本新鲜度和总时长门，失效立即中性释放。

P1 - `src/auto_modules/features/poe2/live_terrain/movement.py::POE2_MAP_TO_STICK_BASIS` 仍按一次固定摇杆实测 `(+27.52,-33.04)` 和等距投影假设启用约 45° map→stick 基底；首帧注册逆变换现已在正式页面输出边界接入，但不同相机/地图方向或第二正交方向符号仍可能使基底不适用。复现方式：管理员短时分别输出 native X/Y 方向，读取同实例前后 grid 位移并比较矩阵残差；同时确认日志记录了 registration angle/reflection。建议：完成双轴标定后把基底作为 PoE2 profile 参数；在此之前门后路线只能算离线安全规划，不能报告实机穿门通过。
P1 - `tools/debug/poe2_route_probe.py::main` 仍是独立开环探针，当前只读取 native 起点并使用固定基底，没有接入页面的 `SimilarityTransform2D` 注册结果。触发条件：直接用该脚本测试旋转地图实例并把 `route.finished` 当作到达证明。复现方式：地图方向非 identity 时观察输出向量与页面跟随输出不一致。建议：下次实机探针必须显式加载同一实例的首帧 registration，缺失时拒绝发送；在此之前只用于离线路线/Host 链路检查。
P1 - `tools/debug/poe2_follow_readonly_probe.py::_capture_terrain` 依赖当前终端具备 `PROCESS_VM_READ|PROCESS_QUERY_INFORMATION`；受保护游戏进程在普通权限下会抛 `PermissionError: [WinError 5]`，导致没有任何首帧证据。触发条件：PoE2 以管理员权限运行而探针未提升。复现方式：发现 PID 后执行探针，报告 `errors` 只有 WinError 5、`frames=[]`。建议：由用户明确确认 UAC 后在管理员终端运行；探针继续 fail closed，不绕过权限、不伪造定位成功。

P2 - `tests/test_poe2_capture_test_page.py` 的 9 条断言均通过后，pytest 9.1.1 在 `pytest_unconfigure -> gc_collect_harder` 阶段偶发/当前可复现 Windows heap `0xc0000374`。触发条件：独立运行该 Qt 页面测试文件并在退出时强制收集对象；关闭外部工作台进程后仍复现。建议：作为独立 Qt fixture 生命周期任务检查 QApplication、页面/子窗口 `deleteLater/close` 顺序和 PySide6 ownership；不能把“9 个 PASSED 点”误报为干净测试通过。本风险不经过 hybrid controller/session 运行调用链。

P1 - `presenter.frame_pixmap()` 在 Qt 边界直接消费非连续 NumPy 视图或异常通道数时会触发 `BufferError`/越行读取，旧实时 tick 会把单帧转换问题当成整个双人定位失败；某些 Qt 版本还可能因借用失效内存产生 `Qt6Gui.dll 0xc0000005`。触发条件：截图/预处理结果带负 stride、非 `uint8` dtype（例如 `np.fliplr`）或不是 3/4 通道。复现方式：将 `np.fliplr(np.zeros((24,32,3),uint8)` 或 `(24,32,1)` 传给 `frame_pixmap()`；现已通过 `uint8 + np.ascontiguousarray + 通道门禁 + QImage.copy()` 防护，但仍需实机对照 Application Error 验证原生崩溃是否消失。

Resolved in experiment - `Poe2CaptureTestPage._tick_dual_motion()` 的双人实时截图/识别/跟踪已由 `Poe2DualMotionWorker` 移出 GUI 线程，单槽 latest-only channel 会丢弃旧结果，页面只消费最新状态；worker 日志记录分段耗时、完成帧和丢弃结果。仍需实机确认首帧/恢复搜索和 Qt 原生截图后端线程安全。
P1 - `SimulatedFollowRuntime.update_follower_position()` 的 command/observed alignment 只能在视觉样本产生实际位移后判定输入基底方向失配；触发条件：人物被墙完全挡住、视觉帧过期或实际速度低于 0.5 native px/s。建议：结合 `visual_age_ms`、Host axes 和 native before/after 做短时实机标定，不把无位移样本误报成方向错误。
P1 - `Poe2CaptureTestPage._update_program_probe_local_contact()` 依赖当前双人状态中的屏幕人物候选和同帧 wall mask；触发条件：marker 合并/丢失、combined mask 与 tracker 帧不属于同一 captured_at_ms，或 registration transform 为空。当前行为是跳过局部证据并由视觉新鲜度门保护；建议真实测试记录 `local_contact_failed` 和 `captured_at_ms`，必要时把 raw/combined/state 打包成同帧诊断快照。
Resolved in experiment - `SimulatedFollowRuntime._tick_follower()` 的 `contact_relocalization_required` 仍是安全停止信号，但页面现在保存目标/角色/控制器后调用 `_start_dual_motion(recovery=True)` 强制新增一次双人内存锚点和首帧注册，并在新鲜 tracking 帧到达后自动恢复原目标。剩余风险：内存锚点或首帧注册失败时只能安全停止并要求人工重启；10 秒冷却防止重复读取，实机仍需验证恢复后的 Host lease 和目标续跑。

Resolved 2026-10-02 - `SimulatedFollowRuntime._tick_follower()` 过去把连续 native 坐标四舍五入到墙格后直接交给 A*/局部控制，导致人物站在墙边可行走侧时首个规划返回 `no_safe_route`，随后在距离目标仍约 42.6 native 单位处停止。现在 `_wall_start_recovery_command()` 在首次规划失败前和后续墙格帧均搜索半径 12 内可到目标的可行走起点，输出有界恢复脉冲；`FollowObservation.diagnostics.observed_position_metrics` 保留原始观测格。回归复现地图边界样本通过，移动到自由格后恢复 `route_ready`。

Resolved 2026-10-02 - 实机墙角无进展时，`contact_evidence.recovery_required` 曾被顶部缓存的 `wall_start_recovery` 分支覆盖，导致同一微脉冲无限重复、`recovery_attempts` 不增长且无法进入局部恢复。现在 `_tick_follower()` 在接触恢复门成立时跳过该早期分支；`_contact_recovery_command()` 按小地图左右空闲度在半径 12 native 内选择可行走起点并规划到目标，输出有界侧向脱困向量。新增顺序回归覆盖 `wall_start_recovery → contact_recovery`；两次仍无位移时保留 `contact_relocalization_required`。

Resolved 2026-10-02 - `ContactMonitor` 曾把低 command/displacement alignment 直接当作 `no_progress`，导致输入延迟造成的大位移（本次 `8.729 native`、夹角约 `97°`）被错误升级为撞墙重定位。当前撞墙证据只在非零命令且位移低于 `0.25 native` 时累积；alignment 仍作为方向校准诊断。带小地图墙证据但存在明显位移时，`direction_mismatch_ticks` 不再单独升级墙体恢复；新增正交大位移回归。
Resolved 2026-10-03 - `SimulatedFollowRuntime._tick_follower()` 与 `_wall_start_recovery_command()` 曾在小地图已开放时持续复用 stale native wall cache，并把 `wall_recovery_position` 每 tick 滚动到当前位置，触发条件是人物坐标长期不变且 `local_obstacle_ahead=False`。现在恢复 episode 固定起点、最多三次墙边脉冲；开放小地图只允许有限 `stale_wall_raster_recovery` 过渡，然后交回 stalled/contact/relocalization 链路。Host lease 过期仍由 `ProgramGamepadOutput.write()` 显式失败并安全释放，不做隐式续租。

Resolved 2026-10-03 - `DualVisualTracker` 增加默认 2 帧 marker dropout grace，短时丢失使用共同位移后的预测 native 点；`_tick_program_move_probe()` 只有 tracker 进入 recovery 且超过 grace 才走一次内存重定位，避免单帧抖动释放输入。

Resolved 2026-10-03 - 双人视觉 recovery 前保存点击 source、角色和模式；恢复拿到新鲜 tracking 帧后重建 follow runtime 并重放目标点击，恢复期间不发送输入。程序移动原有 native target/context 续跑逻辑保持不变。

Resolved 2026-10-03 - `_run()` 对单帧异常递增 `failed_frames`、发出 `frame_failed` 并按配置周期重试；默认连续 3 次失败才发出 `failed` 终止 worker，成功帧清零连续失败计数。

Resolved 2026-10-03 - `_start_dual_motion()` 只有得到独立 clone 才创建 worker；不具备 `get_params/set_params` 或 clone 失败时记录原因并回退同步 capture，不再共享 `self.recognizer`。

Resolved 2026-10-03 - stop timeout 后设置 `dual_motion_restart_pending`，`_start_dual_motion()` 不创建并行 worker；旧 worker `finished` 且 retired 列表无运行实例后才通过 Qt 事件队列恢复启动。

Resolved 2026-10-03 - `_start_dual_motion()` 过去在检查 retired worker 前就可能执行新的首帧截图/内存读取；现在所有 retired worker 必须先确认已停止，且 `_on_dual_worker_finished()` 兼容属性或可调用形式的运行状态。页面关闭、清图、换图和主动 stop 通过 closing/session token 取消延迟 restart，避免旧 Qt 回调重新启动定位。

Resolved 2026-10-03 - `DualVisualTracker.start()` 保存首帧主角色 marker 为 local-player hint，`tick()` 在局部 matcher 中优先使用该 hint，并在共同平移或主角色重新观测后更新；worker/sync frame 即使携带截图中心也不会覆盖该语义。

Resolved 2026-10-03 - `DualVisualTracker.tick()` 过去只要任意一个候选可见就清零全局 dropout，并把另一名角色发布为 `None`；现在按 identity 累计 dropout，grace 内保留其预测 native 点并输出 `markers_partial_grace`，超限 diagnostics 会列出 `expired_marker_identities` 后才触发 recovery。

P1 - `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_localization/memory_anchors.py::_identity_for()` 用 metadata 加 entity vector index 生成双人身份，缺少稳定 entity id。触发条件：实体向量重排或两角色 metadata 相同；复现方式：强制两次 `read_many()` 改变顺序，恢复后 `_maybe_resume_program_probe_after_relocalization()` 找不到保存 role。建议：使用稳定实体地址/角色唯一标识，并保留跨恢复的 identity mapping。

P1 - `Poe2CaptureTestPage.start_dual_target_experiment()` 将所选身份按 UI P1/P2 映射到 Host 控制器 1/2；2026-10-03 在 `P2_7:54BE4D92` 同实例已观察到两控制器 acquired 和两个角色向同一目标显著移动，证明该次环境的基本映射有效，但不能推广到设备顺序变化或失焦环境。触发条件：实际 Host 设备顺序与 UI 选择不一致，或点击地图时 PoE2 失焦且游戏不消费背景虚拟手柄。复现方式：换设备/配置后分别观察两个角色的真实位移、Host diagnostics 和页面 native 轨迹；建议先单角色短脉冲校验设备身份及焦点行为，再做双角色同目标长路径测试，失败时立即使用页面停止按钮。页面不会自动把游戏窗口置前。

P2 - `Poe2CaptureTestPage._tick_dual_target_experiment_impl()` 只有两个 `FollowObservation` 在同一 tick 均为 `ARRIVED` 才结束双人任务。实机 `P2_7:54BE4D92` 中两人先后靠近目标，但没有 `dual_target.both_arrived`；P2 最小距离 6.54、最后约 10.09，`recovery_attempts` 累计 41。用户观察两名角色在同一点附近有体积碰撞，并认为本阶段移动实验成功；日志不能单独证明碰撞机制，也不能据此判定定位/寻路故障。触发条件：双人被要求占据同一个很小的目标范围，物理占用可能使其中一人离开到达半径，程序保持活动直到手动停止。复现方式：同点目标附近同时观察游戏人物占位、逐帧 native 位置、两个 `arrived` 状态及 Host lease。当前保留手动停止，不调大到达半径或改坐标参数；只有未来需要无人值守的双人完成判定时，再设计共享目标区域或分配不同停靠点并做实机验收。

P1 - `Poe2CaptureTestPage._tick_follow_experiment_impl()` 的实时角色跟随已通过假手柄与同帧视觉状态回归，但尚未经过真实 PoE2 双角色动态跟随验收。触发条件：手动角色高速位移后视觉身份交换、两角色各自位置虽新鲜但映射到错误身份，或 Host 控制器顺序与 UI P1/P2 不符。复现方式：实机分别测试两个方向的短路径、位移技能与停走滞回，并同时核对 `live_role_follow.target`、native 双人轨迹及 Host lease；若身份或目标异常立即停止。当前安全门在视觉过期、定位失稳或实例/变换变化时释放输出，不宣称这些门能证明实机身份永远正确。

P1 - 双人实时 worker 只在首帧/重定位读取并校验 area instance，正常视觉 tick 不验证当前 PoE2 instance。触发条件：切图、传送或死亡后旧 snapshot 仍可被局部墙形匹配接受；复现方式：保持页面运行切换 area，再观察 runtime 仍使用旧 `MapIdentity`。建议：采用低频、受门控的 instance-only probe，实例变化立即停止/重新捕获地图，不能依赖同一旧 snapshot 的自比较。

Resolved 2026-10-03 - `_update_program_probe_local_contact()` 捕获所有普通 `Exception`，记录异常类型为 `local_contact_failed` 并跳过该帧接触证据；Host 输出异常仍由外层 `program_probe.write_failed` 单独处理。

P2 - `services/virtual_gamepad/launcher/src/VirtualGamepadLauncher/LauncherPaths.cs::LauncherPaths()` 及 C# ProjectReference/installer path 本轮只完成静态审计。触发条件：在装有 .NET SDK 的机器构建 Host、LAN、launcher 或 installer tests。复现方式：当前机器执行 `dotnet --list-sdks` 为空，无法编译验证。建议：在 .NET 8 SDK 环境运行 LAN、Host、Launcher、Installer 四组 tests；重点确认 repository/workspace 两级根目录和 `../../../../lan_input_sync` ProjectReference。

P1 - `tools/debug/poe2_live_terrain_localization_probe.py::run_probe()` 的实样本 `accepted=true` 仍缺少独立真实全局坐标。触发条件：把单帧首选 `(1318.35, 834.10)` 直接视为正确位置或直接复制实验阈值到生产 runtime。复现方式：查看 `20260921-mapflotsam-f6a61e51-walkable/report.json`，它只证明首选分数 0.738、首二名差 0.0567 和参数扰动下候选稳定。建议：采集同图移动多帧和不同地图样本，用位移方向、尺度连续性及人工锚点验证后，再把游戏无关 Chamfer 能力下沉到 core、PoE2 清理/候选策略留在 feature 层。

P1 - `src/auto_modules/features/poe2/live_terrain/experimental/hybrid_localization/absolute_registrar.py::_refine_seeds()` 已修复同一方向下错误比例峰吞掉正确比例的问题，当前参数为最多 4 个方向 basin、8 个比例分离种子和 `refine_seed_margin=0.10`；`similarity_search.py::_coarse_search()` 也在全局 Top-K 前优先保留人物点可行走候选。本轮 MapFlotsam 实时失败帧已从错误的 `327°/no flip/0.29` 恢复为 `215°/flip/0.91`，但这些仍是 PoE2 实验参数。触发条件：把单图首次 `anchored_candidate` 当作跨帧 confirmed，或直接固定到其他地图。复现方式：查看 `current-live-failure` 诊断并运行同实例连续移动、多地图首次/恢复测试。建议：验证共享方向、镜像、比例和候选 margin 后，再决定哪些无游戏语义能力可下沉 core。

P1 - `src/auto_modules/features/poe2/live_terrain/stitching_session.py::Poe2StitchingSession.consume()` 输出的是相对拼图位姿，不是已验证的 native terrain 坐标。触发条件：把无明显重影的局部拼图直接用于导航，或在重复房间/高速移动下忽略累计漂移。复现方式：在 PoE2 数据采集测试窗口开始绘图并走一段折线路径，保存 `stitched_map_overlay.png`，检查墙线重影、轨迹跳跃及统计中的失败/低质量跳过。建议：本阶段只作为方向定位输入；下一阶段用较大局部图与 native terrain 做唯一性和全局闭环校正，低 margin 时 fail closed。

P2 - `src/auto_modules/features/poe2/live_terrain/stitching_session.py::Poe2StitchingSession.__init__()` 默认按与第一页一致的 `5000 x 5000` 参数分配 canvas/wall/fog/explored/float32 weight，单会话约 200 MB。触发条件：同时打开多个采集窗口或为多号各建常驻 session。复现方式：创建多个默认 `Poe2StitchingSession` 并观察进程工作集。建议：当前保持单窗口独立实例；多实例前实现延迟分配或 tile canvas，禁止通过共享可变 stitcher 降低内存。

P2 - `CODEBASE.md` 后续历史章节仍使用 §0 定义的逻辑简称。触发条件：读者把 `core/...`、`gui/...` 当成根目录物理路径执行命令。复现方式：根目录已不存在这些 package。建议：新增/修改条目必须写 `src/auto_modules/...` 物理路径；逐轮维护时把触达的旧条目迁为物理路径，不重新建立 compatibility shell。

P1 - `MotionController._calculate_target_screen_position()` 默认半径未校准。触发条件：游戏实际点击触发距离大于 180px 或可交互范围小于 360px。复现方式：自动导航状态栏显示 `click r`，但人物不移动或点击到不可达点。建议：在参数面板调整最小/最大点击半径，并用橙色框观察真实可见范围。

P1 - `main.py` 的 UAC relaunch 会启动一个新的管理员进程并退出原进程。触发条件：从非管理员 shell/IDE 启动。复现方式：启动后弹出 UAC，授权后 GUI 进程启动；如果用户取消授权，程序退出。建议：测试时查看 `logs/runtime.log` 中的 `Admin: True`；只有设置 `MINIMAP_DEBUG_CONSOLE=1` 时才依赖控制台输出。

P2 - `NavigationModeWidget._render_route_overlay()` 在自动导航每帧清空并重绘路线层。触发条件：高 FPS 或长路径。复现方式：地图视图卡顿或闪烁。建议：后续按路径/subgoal 变化缓存绘制。

P2 - `portal_screen_probe.detect_portal_candidates()` 依赖蓝紫发光外观。触发条件：其他事件或怪物使用大面积蓝紫特效，或传送门被怪物/场景遮挡。复现方式：debug 图中橙色候选很多但绿色 accepted 为 0，或绿色框落在非传送门实体。建议：正式事件系统中把它作为“小地图事件已发现后的二阶段确认”，并要求连续多帧稳定后再点击。

Resolved 2026-09-18 - 旧的平行定义解析、混合 runtime 和 GUI-owned persistence 三项风险已消除。`EventDefinitionRepository`/`EventRouter`/`EventExecutionRuntime` 现在是唯一通用能力，`EventWorkbenchService` 是唯一组合根，`EventWorkbenchPage` 只依赖服务；`LocalEventRuntime`、`RemoteEventRuntime`、`EventCatalogRuntime`、`RemoteEventSender` 及其绑定测试已删除。删除事件也通过 versioned tombstone 传播，不再在远端目录残留旧活动记录。

P2 - `src/auto_modules/application/event_workbench/service.py::EventWorkbenchService.tick_once()` 在持有 `_lock` 时执行 `sync.status`、catalog drain/publish、event drain/send 和 `event.state` 命名管道 IO。触发条件：Host 请求阻塞或 LAN 背压，同时 GUI timer 调用 `status()`、用户保存配置或关闭页面。复现方式：假 bridge 的 request 人为阻塞后，GUI 的 `service.status()`/`save()` 等待同一 `RLock`，页面短时无响应。建议：后续把 bridge IO 移到锁外，以不可变 tick snapshot/command queue 提交配置变更，只在短临界区交换 router/definition/status；在改变 worker ownership 前先增加阻塞 bridge 并发测试。

P2 - `RapidOcrProvider.recognize()` serializes one cached RapidOCR model and performs CPU ONNX inference. Trigger condition: a full-resolution frame is requested every navigation tick, or many OCR profile instances use the same provider with expensive detector settings. Reproduction: provider metadata timings dominate a frame budget or recognition becomes delayed while other algorithms continue. Mitigation: use an instance-specific ROI for fixed text zones, set conservative RapidOCR `backend_options`/confidence thresholds, reuse one provider, and measure the recorded `elapsed_seconds` before adding parallel provider instances. Do not move OCR retries or actions into this module.

P2 - `RapidOcrProvider._crop_to_roi()` clips requested ROI bounds to the actual image and maps the result back using integer crop origin. Trigger condition: a profile ROI lies wholly outside a resized/cropped game frame, or a caller accidentally consumes the local backend polygon as a full-frame point. Reproduction: recognition raises `RapidOCR ROI does not intersect the image`, or a target appears displaced by the ROI origin. Mitigation: configure ROI in the same `FrameContext.coordinate_space`, retain provider metadata `roi`/`polygon` in the workbench, and only pass the normalized `TargetDetection` onward.

P2 - `rapidocr_models.resolve_rapidocr_engine_options()` hashes the entire selected ONNX file before creating a provider. Trigger condition: the application resolves an uninstalled/corrupt model during a latency-sensitive scene transition, or a user expects a per-frame `language` parameter to swap models. Reproduction: `ProviderUnavailableError` names the installer command or inference keeps using the provider's original model. Mitigation: install and validate required model assets during environment setup, construct one long-lived provider per selected model, use `language` only as a result label, and expose composition-time model selection in P6 rather than profile-level hidden behavior.

P1 - `WindowsPrimaryMonitorGeometryProvider` and `WindowsDesktopGeometryProvider` establish process DPI awareness before `InputDriver.__init__()` reads Win32 screen metrics in the process's current awareness context. Trigger condition: a host constructs a DPI-unaware input driver before desktop capture/geometry composition, especially at 125%/150% scaling. Reproduction: a 2560×1600 screenshot/mapper reports a physical point near `(634, 532)`, but a separately DPI-unaware process observes cursor `(423, 355)` and virtualized screen dimensions near 1707×1067. Mitigation: establish DPI awareness once at desktop-host startup before constructing capture or input adapters; preserve that explicit construction order in composition roots and do not silently change legacy navigation driver startup until its callers are audited.

P2 - `DesktopOcrActionProof.run()` uses one exact OCR string and one detection center for this safety proof. Trigger condition: OCR misses/duplicates the label, a dynamic desktop layout shifts after capture, or an application uses the proof outside a fresh single-frame action. Reproduction: report status becomes `not_found`, `ambiguous`, or `rejected`; a stale manual point would otherwise click the wrong target. Mitigation: retain one capture-to-action run, require exactly one match, inspect `DesktopProofReport` in dry-run first, and later add target/window verification and multi-frame stability before automating more consequential workflows.

P1 - `SimulatedFollowRuntime._tick_follower()` 的侧向恢复和 `PathFinder` clearance 参数尚未用真实 PoE2 位移真值校准。触发条件：安全膨胀把唯一窄通道判为不可达，或实际摇杆方向/幅度与 reference/native 速度模型不一致。复现方式：实机执行近墙、窄门和墙后目标，记录 `route_safety_margin`、`route_clearance_radius`、`no_progress_ticks`、`recovery_target` 与 native before/after；建议先以 PREVIEW/日志验证，再做短时、可中止的真实输入标定，不能把“route_walkable=true”当成人物已经移动。

## 10. Input Control Current Notes
`core/input/win32_driver.py` is part of the movement chain. It wraps Win32 `SetCursorPos`, `WindowFromPoint`, `SetForegroundWindow`, `GetForegroundWindow`, `GetClipCursor`, and `mouse_event`; `click()` performs separate down/up events with a short hold instead of a combined instant click.

`core/input/controller.py` owns the `MotionController` class; map-direction to screen-click conversion lives in `core/input/motion_mapping.py` and click backend access lives under `core/input/motion_controller/`. The main project backend is `win32_mouse_event`: the click pipeline calls `InputDriver.click(x, y, button="primary", hold_seconds=0.05, move_delay=0.02)`. `pydirectinput.click(x, y)` is only used as a fallback if the primary backend raises.

`MotionController.click_map_target_once()` is an event-interaction helper, not normal movement guidance. It maps the target map point to screen space with `movement_scale_factor` and `movement_max_click_radius`, but deliberately does not apply `movement_min_click_radius`; if the player and target overlap, it clicks `game_screen_center`. Portal uses this for the pre-`D` mapped portal-point click when `NavigationIntent.metadata.force_click_target` is set.

`core/navigation_tasks/movement_executor.py` is the single map-space movement planner for required points, exit movement, and event `MOVE_TO`. User-defined guide points shape route intent through `RouteContext.corridor_anchors()`: current-position-before anchors are ignored, forward anchors between the player and current selected task are preserved, and movement advances by `anchor_step` or `anchor_probe` before direct target A*. Anchor path-goal arrival uses configurable `anchor_arrival_radius`; while an anchor/fallback path goal is still pending, the executor allows repeat clicks after the normal cooldown even if the subgoal barely changed, so a successful anchor plan cannot stall only because `auto_min_click_target_delta` suppressed the click. Stuck recovery now probes toward the active anchor/fallback path goal instead of the final route target, and exhausted recovery attempts set an explicit force-replan flag for the next frame. Automatic click cadence, target-delta suppression, anchor radius, stuck timeout, min progress, recover count, and deviation threshold are all exposed in the navigation parameter dialog and applied to `NavigationTaskController.movement`.

When the player is close to the current `anchor_step`/`anchor_probe` path goal but still outside `anchor_arrival_radius`, `MovementExecutor` switches from normal movement clicks to an exact path-goal click. The returned `MovementStep.force_click_target=True` is propagated through `NavigationTaskController` into `NavigationIntent.metadata`, so `NavigationRuntimeFrameLoop._execute_navigation_intent()` uses `MotionController.click_map_target_once()` and bypasses `movement_min_click_radius`. This prevents near-anchor map deltas such as 20-40px from being inflated into 299px screen-radius clicks that overshoot the anchor. During this final-anchor settle window, recovery probes are suppressed for about 2.2s; if the anchor is still not reached, normal stuck recovery can resume.

`bottom_click_guard_pixels` protects the game's bottom UI/hotbar/chat region without changing the normal movement mapping. If a computed click lands below the safe line, `MotionController` projects that point back along the same center-to-target vector, effectively clicking slightly closer to the character in the same direction.

`gui/modes/navigation/input/window_mode.py::GameInputWindowMode` prevents the PySide main window from intercepting auto-navigation clicks. `NavigationModeWidget._set_game_input_window_mode()` is now only a compatibility wrapper around that adapter. While auto navigation is active, the main window is removed from `WindowStaysOnTopHint` and lowered; when auto navigation or navigation stops, the previous topmost state is restored. The transparent monitor overlay remains click-through and is not the expected click target.

### 2026-05-20 Correction
The stable movement baseline is the original `pydirectinput.click(x, y)` call. Do not replace it with `moveTo + mouseDown + mouseUp` unless it is separately verified in the target game environment. Window focusing is optional (`focus_before_click=False` by default) because it can interfere with the already-working cursor movement path.

`NavParametersDialog.set_config_to_ui()` now uses `QSignalBlocker` while writing widget values and `_connect_signals()` is one-shot. This avoids PySide `disconnect` RuntimeWarning messages during startup/config refresh.

### 2026-05-20 Click Diagnostics
`MotionController._execute_click()` logs the requested coordinate, final coordinate, whether clamping changed it, `pydirectinput.size()`, pydirectinput cursor position before/after, Win32 cursor position before/after, target window information, foreground window information, current `ClipCursor` rectangle, focus HWND, and confirmation-click state. This is intended to separate coordinate mapping failures from Unreal/Windows mouse capture or "click reached the wrong window" failures during real-game testing.

### Event Move Repeat Click
`MovementExecutor.step(..., force_repeat_click=True)` keeps the normal 260ms click cooldown but bypasses the "subgoal must change by 8px" gate. Portal handler sets this flag only for final approach before `interact_radius`, so repeated same-subgoal clicks continue pushing the character into the exact portal point without weakening the later `D`-press distance check. The same executor state is reset on every selected task transition, preventing a previous required/event click from suppressing the next task.

### 2026-05-20 Standalone Input Probe
`utils/input_probe.py` is a standalone manual probe for testing real game input before changing `MotionController`. It supports `pydi_click_xy`, `pydi_move_click`, `pydi_hold_xy`, `setcursor_pydi_click`, `setcursor_pydi_hold`, and `setcursor_win32_click`. It is diagnostic-only unless launched with `--execute`.

### 2026-05-20 DPI/Input Coordinate Finding
Runtime probe on the user's machine showed `pydirectinput.size() == (1707, 1067)`, `GetSystemMetrics(0/1) == (1707, 1067)`, and Qt `devicePixelRatio() == 1.5`. Therefore screenshot capture can still require physical coordinates, but `MotionController` should feed `pydirectinput` input coordinates consistently. `_clamp_screen_pos()` is now disabled by default; enabling it can still rewrite targets such as `(1987, 569)` or `(1559, 1469)` to screen-edge points, so it should only be used after the coordinate system is proven.

## 11. Event Runtime Diagnostics
`core.events.debug` is the shared logging utility package for the event system. It provides `event_log()`, `start_event_log_session()`, `describe_action()`, and `describe_task()` so event modules print consistent `[Event HH:MM:SS.mmm pid=<pid>] ...` lines instead of ad-hoc debug strings. `writer.py` writes to runtime output, `logs/event_runtime.log`, per-run archives under `logs/event_runs/`, and optional topic logs such as `event_portal.log`; `topics.py` decides portal/navigation/localization topic routing; `descriptions.py` formats actions/tasks; `formatting.py` keeps scalar/tuple/list/dict/Enum values consistent. The PID is intentionally included because multiple GUI processes can otherwise interleave event lines and make a portal bounce look like a single state-machine bug.

`EventMonitor`, `EventMemory`, `EventCoordinator`, `EventRunner`, and `NavigationTaskController` log detector initialization, observation counts, task creation/confirmation, display-task selection, navigation task selection/transition, handler start, action output, action execution, completion, failure, retry, and ignored states. Repeating frame-level logs are throttled, while click/key/complete/fail actions print immediately.

`PortalMinimapDetector`, retained `PortalMainViewConfirmer` probe assets, and `PortalEventHandler` now log the portal-specific chain: minimap template hits, task global position, movement distance to the portal, mapped portal-point click, key interaction, wait-after-interaction, teleport position/environment completion, and timeout failure. Current runtime portal flow is minimap-first and key-based: after arriving near the minimap-derived portal point it clicks that mapped point once, waits briefly, then presses `D`; main-view confirmation is not part of the active default portal loop.

`NavigationModeWidget` logs event-system initialization and unified navigation intent execution, and the status bar now appends a compact event summary from `EventCoordinator.status_summary()`, for example `event:portal running seen=3 act=move_to`. This is intended for live game testing only; it does not change event matching thresholds or navigation movement semantics. The old per-frame localization print block (`当前定位` / `位置来源` / `本帧定位位置`) is intentionally removed so portal/event operation logs remain readable in `logs/runtime.log`.

Event detection and memory updates may run while normal navigation localization is active, but handlers only advance when `NavigationTaskController` selects an event task and calls `EventCoordinator.run_task()`. This avoids a misleading state where an event task could log completion without the unified controller being allowed to move or click.

## 12. Event Manager UI
`gui/dialogs/event_manager_dialog.py` is the independent event-management surface. It is intentionally package-level: the table lists complete events such as `portal`, not the internal minimap detector, main-view confirmer, or handler. The global checkbox toggles `EventSystemConfig.enabled`; each row checkbox toggles `config.events[event_type]["enabled"]`. Selecting a row renders editable controls from the event definition schema; for portal this includes `interact_radius`, which controls how close the player must be before pressing `D` and can now be lowered to 1, plus `portal_point_click_wait_ms`, which controls the pause between the mapped portal-point click and pressing `D`. Portal recognition parameters such as `minimap_threshold`, `max_candidates`, `min_blue_ratio`, `feature_sat_min`, `feature_val_min`, and feature blue-pixel bounds are exposed here rather than being hidden constants.

The runtime task table reads from `EventCoordinator.tasks()` and shows task ID, event type, state, seen count, confidence, global map position, attempts, and last-seen timestamp. This gives live feedback when a minimap icon is detected even before auto navigation executes the event.

`NavigationModeWidget._render_event_overlay()` draws event markers directly on the navigation map from `EventCoordinator.overlays()`. Pending/observed events use orange, running events use green, and completed/ignored events use gray. Disabled event types and global disabled state are filtered by the coordinator so stale markers do not remain visible after config changes.

The save button writes only the current map's `event_config.json`. This keeps per-map event strategy separate from global code and avoids one map's event settings affecting another map.

The generic “测试事件流程” button is not a one-off movement probe. It toggles `ManualEventTestController`, enables handler execution in the normal navigation loop, and runs registered event definitions through the same `detect -> localize -> schedule -> action -> COMPLETE/FAIL` pipeline used by automatic navigation. The button text changes to “停止事件流程测试” while that pipeline is active.

The “刷新事件状态” button is a runtime-only reset. It enumerates event types from the active registry and configuration, clears each type's tasks/cooldown/localization clusters through `EventCoordinator.reset_event_type()`, and does not edit the event configuration file.

## 13. Portal Event Current Behavior
The current portal event is minimap-first. `PortalMinimapDetector` exposes multiple selectable minimap recognition modes in the event manager: `template`, `feature`, `feature_then_template`, and `shape_color`. As of 2026-06-04 the default is `shape_color`, because runtime logs showed the older `feature_then_template` path frequently emitted blue-body matches that could stabilize into nearby duplicate portal tasks. `shape_color` checks the blue/cyan portal body plus the white/gray outer ring, combined shape, edge, and HSV color similarity before the hit becomes a candidate. Every accepted hit still passes `portal_color_check()` before becoming an `EventDetection`; `minimap_nms_radius` then suppresses nearby local duplicate hits before wall-registration projection. The detector emits only local minimap candidates and never creates a trusted global coordinate. `feature_detector_enabled` is retained only for legacy config compatibility; new tuning should use `detector_mode`.

`NavigationCore.localize()` stores `last_frame_registration` whenever player localization succeeds. `EventCoordinator` passes local detections and that registration to `EventPositionStabilizer`, which projects each candidate with `frame_origin_global + local_minimap_pos * draw_scale`, clusters samples by event type and map distance, and emits an `EventObservation` only after `stable_frames` samples stay within `stable_variance`. `EventMemory` only creates/updates tasks from these stable global observations. The frame registration draw scale is the map-package scale, not a user-adjusted offset or stale navigation config value.

When auto navigation or generic manual-event mode selects a Portal task, `PortalEventHandler` moves the character toward the minimap-derived portal point until the player is within `arrival_radius`. The handler returns `EventAction.move_to(global_pos)`; `NavigationTaskController` converts that to a `MOVE_MAP` intent through the shared `MovementExecutor`, so portal movement uses the same A*/guide-anchor/fallback/click-throttle behavior as required points and exit movement. During the final approach where `distance > interact_radius`, the handler marks the action with `metadata.force_repeat_click=True`; `MovementExecutor.step()` then allows another real click after the normal click cooldown even if the subgoal has not changed, preventing a near-target stall such as staying 7px away from a 1px interaction radius. Once the player is within `interact_radius`, the handler first emits one forced mapped portal-point click (`metadata.force_click_target=True`), waits `portal_point_click_wait_ms`, then sends `D` through `MotionController.press_key()` and enters `wait_result`. The forced click goes through `MotionController.click_map_target_once()` so it targets the mapped portal point rather than using movement minimum radius. The schema still has an `interaction="click"` choice, but current handler behavior forces key interaction and treats main-view confirmation as a retained probe/asset path rather than the active portal flow.

After interaction, completion is not a fixed timer. The handler waits at least `post_interact_wait_ms`, then asks navigation for a full-map localization frame while it is waiting for teleport completion; this uses the same full-map template path as navigation start and bypasses normal jump rejection because a portal teleport is an expected large movement. The handler returns a teleport completion if the player has landed within `exit_complete_radius` of another active known portal task and is closer to that task than to the entry portal, if the player's global position changes by at least `teleport_min_distance`, or if the raw minimap patch around the player differs from the pre-interaction patch by at least `environment_change_threshold`. The known-exit branch is checked first because close paired portals can be far below `teleport_min_distance`. If none of these checks pass before `teleport_timeout_ms`, the task fails and may retry.

To prevent paired nearby portals from bouncing the character back, `PortalEventHandler` includes `completion_kind="teleport"`, `entry_task_id`, `entry_pos`, `exit_task_id` when a known exit task is found, `exit_pos`, and `exit_player_pos` metadata in the COMPLETE action. `EventRunner` passes that to `EventMemory.complete_teleport_session()`, which creates a `teleport_session_id`, marks the interacted portal as the entry, prefers the explicit exit task id, otherwise finds an already-known portal task near the post-teleport player position as the exit, and marks both as completed. If no exit task exists, memory creates a synthetic completed exit task at the post-teleport player position so independent-map teleports still close the session. `EventRunner` refuses to start or continue tasks that are already `completed` or `ignored`, which protects the lifecycle boundary if a caller accidentally passes a terminal task back into the runner.

Cooldown still remains as a secondary guard: `EventMemory` uses `cooldown_radius` for completed or ignored portal observations and `type_cooldown_ms` as a short global same-type cooldown. When a teleport session completes, `EventMemory.complete_teleport_session()` suppresses nearby active tasks around both entry and exit, so future minimap observations of the same portal pair are skipped rather than scheduled again. Cooldown skips are logged with the matched task, cooldown kind, remaining time, and position distance when relevant.

## 14. Event Localization Contract
`core/events/models.py::FrameRegistration` records the wall-registration result for one minimap frame: validity, confidence, global origin of the raw minimap frame, draw scale, player global position, player local minimap position, source (`f2f` or `template_match`), frame size, and debug metadata.

`core/events/models.py::EventDetection` is local-only: event type, confidence, detection time, local minimap position, source, and detector metadata. Detectors must not convert this to global map space.

`core/events/models.py::EventObservation` is stable/global: event type, confidence, observation time, global map position, optional latest local minimap position, source, sample count, variance, and stabilization metadata. `EventMemory.merge_observations()` treats this as already localized and stable.

`core/events/models.py::EventTick.event_tasks` is a runtime memory snapshot, not detector output. `build_event_tick()` leaves it empty; `EventCoordinator.observe()` fills it after `EventMemory.merge_observations()`. Handlers use this to compare against already-known tasks without importing memory or scheduler internals.

`core/events/position_stabilizer/runtime.py::EventPositionStabilizer.update()` is the shared localization stage for all future event types. It rejects detections when no valid frame registration exists, projects candidates through the same wall alignment used for player localization, clusters nearby samples, expires stale clusters, and emits stable observations only after the configured sample and variance gates pass. The old import path `core.events.position_stabilizer.EventPositionStabilizer` now resolves to the package facade.

## 15. Event Four-Phase Methodology
`docs/plans/2026-05-23-portal-event-case-study.md` records the project-level event methodology using `portal` as the first concrete case. Future event work should be evaluated through four phases: event recognition/localization, navigation to trigger point and triggering, event-specific execution, and event completion.

Phase 1 is already mostly shared: concrete detectors emit local `EventDetection` values, `EventPositionStabilizer` projects them through wall registration, and `EventMemory` only accepts stable `EventObservation` values. New minimap-based events should normally replace only detector assets/thresholds and event-specific config, not rewrite localization or memory.

Phase 2 is now shared through the unified navigation task layer and the event approach gate. Before an event handler is allowed to execute, `NavigationTaskController` asks `EventApproachController` to move toward the event with normal A* + guide anchors until the event enters the configured real-view box, then switch to short-lookahead A* without route anchors, stop near the event, and wait for stable frames. After the gate releases the task, handlers may still return `EventAction.move_to(global_pos)`, `PRESS_KEY`, `WAIT`, or `COMPLETE`, and `MovementExecutor` remains the shared A*, click throttling, and fallback-probe engine. The remaining coupling is that `NavigationRuntimeFrameLoop` still reaches into the navigation widget owner for capture/localization/UI overlay dependencies and GUI-owned input/status callbacks; future refactors can replace owner access with a narrower targets DTO without changing the task/controller protocol.

Phase 3 remains event-specific by design. Handlers may maintain complex state machines, but they must express side effects through `EventAction` rather than directly calling mouse/keyboard APIs. Portal is simple because triggering and execution are effectively the same: click the mapped portal point, wait briefly, then press `D`.

Phase 4 requires an explicit completion strategy per event. Portal uses a teleport completion strategy: position jump, local minimap environment change, or landing near another known portal. It then marks both entry and exit tasks completed through `EventMemory.complete_teleport_session()` to prevent bounce loops.

## 16. Structural Audit Snapshot
`gui/modes/navigation/widget.py` is now the main navigation UI composition root, and `gui.modes.navigation.NavigationModeWidget` is the canonical entry used by `MainWindow`. The old `gui/modes/navigation_mode.py` compatibility wrapper has been deleted. The widget still owns the navigation page UI, signal wiring, event tick creation, capture geometry, and unified navigation loop skeleton, but route commands, map loading, config save/apply, event lifecycle, screen calibration, map-click interpretation, presentation writes, command lifecycle, and intent consumption are already delegated into `gui/modes/navigation/*` modules. Final `NavigationIntent` consumption is coordinated through `gui/modes/navigation/runtime/intent_consumption.py`, while real input execution remains in `navigation/input/intent_executor.py`.

After the presentation overlay package split, route QGraphics overlay item construction lives in `gui/modes/navigation/presentation/route_overlay.py`, and event marker overlay construction lives in `gui/modes/navigation/presentation/event_overlay.py`. The old root-level `route_overlay.py` / `event_overlay.py` wrappers have been deleted. `NavigationModeWidget` still owns when overlays refresh and still exposes the original private methods, but no longer contains the long per-item drawing loops for route and event markers.

After the event-adapter cleanup, `ui/modes/navigation/event_adapter.py` owns generic event registry construction from an injected factory, config summary strings, `EventTick` construction, and coordinator status text. `MainWindow` expands `ui/modes/torchlight/navigation.py::TorchlightNavigationComposition` into registry/window/overlay dependencies; a standalone navigation widget receives an empty `EventRegistry`, no game window, and no business overlays. The old UI-level event-action helper predicates were removed because implementation references now flow through `NavigationTaskController` and core `EventAction -> NavigationIntent` translation. `NavigationModeWidget` still owns when to initialize the event system and when to call `EventCoordinator.observe()`.

After the navigation map package split, `gui/modes/navigation/map/config_store.py` owns project/map path resolution, map-name listing, `NavConfig` JSON load/save, default-config fallback, and merge saves; `gui/modes/navigation/map/capture_geometry.py` owns logical-to-physical center conversion and capture geometry calculation. The old `gui/modes/navigation/map_runtime.py` compatibility facade has been deleted. Saving navigation config merges into the existing map `config.json` instead of overwriting it, preserving mapping-only fields such as `stitcher_params` that are needed to keep drawing and navigation environments comparable. `NavigationModeWidget` still owns user feedback, `NavigationCore` construction, button enabling, and applying loaded config to runtime services.

After the calibration lifecycle split, `gui/modes/navigation/calibration/screen_center.py` owns primary-screen DPR lookup, logical-to-physical coordinate conversion, and center selector lifecycle, while `gui/modes/navigation/calibration/lifecycle.py::NavigationScreenCalibrationLifecycle` owns the navigation-page side effects after a calibration click: `NavConfig.game_screen_center` write, params dialog refresh, overlay refresh, config save, completion dialog, and selector close. `NavigationModeWidget._calibrate_screen_center()` and `_handle_calibration_click()` remain public UI slot wrappers.

After the presentation overlay package split, `gui/modes/navigation/presentation/viewport_overlay.py` owns screen overlay geometry, monitor green-rectangle geometry, and game-view orange-rectangle geometry; the old `gui/modes/navigation/viewport_overlay.py` wrapper has been deleted. `NavigationModeWidget` still owns actual Qt item creation and visibility updates.

After the dialog-host split, `gui/modes/navigation/presentation/dialog_host.py` owns the shared owned-dialog show/toggle shell behavior: restore minimized state, first-show offset from the main window, raise/activate, and the active-window hide signal. `NavigationModeWidget._toggle_owned_dialog()` and `_show_owned_dialog()` remain compatibility wrappers, so parameter/event dialog buttons keep the same call path while the large widget no longer carries this generic Qt shell code.

After the debug-overlay split, `gui/modes/navigation/presentation/debug_overlay.py` owns transparent debug overlay hide/show writes after capture geometry has been computed. `NavigationModeWidget._toggle_overlay_display()` still owns user-facing validation, checkbox reset, and warning dialog; `_update_overlay_display()` remains the compatibility wrapper that builds capture geometry and delegates the actual overlay window write.

After the navigation map-session split, `gui/modes/navigation/map/session.py` owns the smallest stable part of map loading: reading `NavConfig` with an existence flag and constructing `NavigationCore`. After the deeper map-load lifecycle split, `gui/modes/navigation/map/load_lifecycle.py::NavigationMapLoadLifecycle` owns the ordered GUI side effects that follow: missing-config warning, runtime config application, params dialog fill, route/event initialization, rendering, last-position marker, route/event overlay, loaded UI, and load-failed critical dialog. `NavigationModeWidget.load_map()` remains the compatibility entrypoint and only reads the selected combo text before delegating.

After the map-load UI split, `gui/modes/navigation/presentation/map_load_state.py` owns map combo population, the final loaded-state UI writes, missing-config warning, load-failed critical dialog, and overlay-config warning. `NavigationModeWidget.refresh_map_list()` still decides where map names come from, and `load_map()` still decides when loading is complete; the helper only writes QComboBox/button/status state or emits old user-facing messages. `_toggle_overlay_display()` still owns resetting the overlay button checked state.

After the initial capture-center split, `gui/modes/navigation/map/capture_geometry.py::initial_capture_center_for_config()` owns the pure logical-center-to-physical-center calculation used during map load. `NavigationModeWidget.load_map()` still writes `_capture_center_physical`, prints the debug line, and calls `params_dialog.set_config_to_ui()` at the original point in the load sequence.

After the config lifecycle split, `gui/modes/navigation/config/lifecycle.py::NavigationConfigLifecycle` owns the full navigation config sequence: parameter-change runtime sync, current-map config save, default config save, applying runtime config, refreshing debug overlay/game-view rect callbacks, dirty status, and save result presentation. `gui/modes/navigation/presentation/config_save_state.py` still owns only the concrete status-label/QMessageBox text. `NavigationModeWidget` keeps `_apply_config_to_core()`, `_configure_navigation_task_controller()`, `_save_nav_config()`, and `_save_nav_default_config()` as compatibility wrappers.

After the event-management presentation split, `ui/modes/navigation/presentation/event_management_state.py` owns only user-facing QMessageBox/status-label text for event config save, generic event reset, and manual-event test start/stop. `ui/modes/navigation/events/lifecycle.py::NavigationEventLifecycle` owns event config IO, registry/config-driven `reset_event_type()` calls, manual-test controller state, movement/event-approach reset, motion/input window mode, overlay refresh, dialog task refresh, and event logs. `NavigationModeWidget` keeps `_save_event_config()`, `_reset_event_state()`, `_reset_event_move_runtime()`, `_run_manual_event_test()`, and `_set_manual_event_test_active()` as thin wrappers.

After the event dialog/bootstrap split, `gui/modes/navigation/events/dialog_lifecycle.py::NavigationEventDialogLifecycle` owns event-dialog creation, signal wiring, context refresh, toggle behavior, and manual-test button synchronization. `gui/modes/navigation/events/bootstrap.py::initialize_navigation_event_system()` owns map-load-time event runtime construction: load event config, create `EventCoordinator`, create `GameWindowCaptureProvider`, refresh the event dialog, and log initialization. `NavigationModeWidget._initialize_event_system()` only writes the returned runtime objects back to widget fields.

After the map-click lifecycle split, `gui/modes/navigation/map/click_lifecycle.py::NavigationMapClickLifecycle` owns user map-click interpretation: initial hint placement, route editing command dispatch, manual move target guard/execution, hint/view mode toggling, marker writes, route overlay refresh, and click-related status text. `NavigationModeWidget` keeps `handle_map_click()`, `set_initial_hint()`, and `toggle_hint_mode()` as compatibility wrappers while `eventFilter()` remains the Qt event adapter.

After the map event-filter split, `gui/modes/navigation/map/event_filter.py::handle_navigation_map_event_filter()` owns the narrow Qt scene-click recognition rule: watched object must be the map scene, event type must be `GraphicsSceneMousePress`, and button must be left mouse. It forwards `scenePos()` into the injected map-click callback. `NavigationModeWidget.eventFilter()` now only calls this helper and falls back to `super().eventFilter()`.

After the navigation-command presentation split, `gui/modes/navigation/presentation/navigation_command_state.py` owns only user-facing QMessageBox/status-label text for auto-navigation guard/start/stop and navigation start/pause. `NavigationModeWidget` still owns route validation, `NavigationTaskController` lifecycle, `MotionController` control enablement, `nav_timer` start/stop, and button checked/text state.

After the route lifecycle split, `gui/modes/navigation/route/lifecycle.py::NavigationRouteLifecycle` owns route command result synchronization: load/save/undo/clear results update `route_data`, call `NavigationTaskController.load_route()`, refresh the route overlay, show status text, and preserve the old save-failed warning. `gui/modes/navigation/presentation/route_command_state.py` still owns only route command text/warning presentation, while `NavigationModeWidget` keeps the old route slot names as wrappers.

After the calibration-feedback presentation split, `gui/modes/navigation/presentation/calibration_feedback.py` owns only initial-hint status text, hint-mode status text, and screen-center calibrated completion dialog. After the map-click lifecycle split, `gui/modes/navigation/map/click_lifecycle.py::NavigationMapClickLifecycle` owns initial hint placement (`NavigationCore.set_initial_hint()`, marker/monitor/game-view refresh, hint button reset, view drag/cursor) and the full map-click interpretation order (hint -> route edit -> manual move). Screen-center calibration result handling has moved into `NavigationScreenCalibrationLifecycle`; `NavigationModeWidget` only keeps the old slot names.

After the runtime-status presentation split, `gui/modes/navigation/presentation/status_presenter.py` owns not only status text construction but also writing the current-frame runtime status, appending relocalize/click suffixes, and terminal arrived/failed texts. `NavigationRuntimeFrameLoop` now owns when status writes happen in the navigation frame; relocalize requests, terminal task shutdown, input-mode restoration, and button state changes are ordered through runtime intent helpers.

After the localization-view presentation split, `gui/modes/navigation/presentation/map_presenter.py::update_localization_view()` owns the localized/fallback display branch for player marker, monitor/game-view rect callbacks, player marker hiding, and view centering. `NavigationRuntimeFrameLoop` owns localization-frame orchestration, event observation, task updates, status write timing, and callback wiring.

After the event-observation runtime split, `gui/modes/navigation/runtime/loop.py::observe_navigation_events()` owns the per-frame event observation mini-flow: build tick, observe coordinator, render overlay, refresh visible event dialog tasks, and return `event_tick`. The two currently implemented event hooks live in the core task runner path rather than this GUI helper: `event_visible_target` fires when the selected event target first enters the real-view gate, and `event_completed` fires after the runner has completed memory state.

After the localization result migration, `gui/modes/navigation/runtime/localization_tick.py::capture_navigation_localization_tick()` owns the first navigation-loop segment: capture geometry, screen capture, player local-position resolution, and retrieval of the core-owned `NavigationCore.localize_result()` outcome. `NavigationCore.localize()` remains the source-compatible tuple facade; `NavigationRuntimeFrameLoop` owns writing `_current_capture_rect/_current_player_local_pos`, event observation, task update, presentation refresh, and route overlay timing.

After the minimap sample-capture split, `gui/modes/navigation/runtime/minimap_sample_capture.py` owns detector sample persistence: frame normalization to BGR, safe map-name directory creation, PNG writing through `cv2.imencode().tofile()`, and same-stem JSON metadata. `NavigationRuntimeFrameLoop` now also writes `_latest_minimap_frame/_latest_minimap_capture_rect/_latest_minimap_player_local_pos` immediately after localization capture, so the toolbar action can save the exact latest monitored minimap region without re-running event detection. If no cached frame exists, `NavigationModeWidget.save_minimap_sample()` falls back to one immediate capture using the current navigation monitor geometry.

After the intent-consumption split, `ui/modes/navigation/runtime/intent_consumption.py::consume_navigation_intent()` owns the route-overlay-after intent sequence: force-relocalize short-circuit, real-input execution callback, manual event test terminal stop, and ARRIVED/FAILED terminal shutdown. `NavigationRuntimeFrameLoop` supplies the concrete callbacks (`event_log`, `NavigationCore.request_global_relocalization()`, `_execute_navigation_intent()`, `_set_manual_event_test_active()`, input window mode restore, button reset, and status presentation), so no game-specific hook has been introduced.

After the runtime command lifecycle split, `gui/modes/navigation/runtime/command_lifecycle.py::NavigationRuntimeCommandLifecycle` owns the navigation command state machine around user buttons: start navigation, stop runtime, start/stop auto navigation, guard messages, task-controller route start, timer start, motion control, game-input window mode, button rollback, and paused/started status text. `NavigationModeWidget` keeps the old slots (`toggle_navigation()`, `stop_runtime()`, `toggle_auto_navigation()`, `_can_start_auto_navigation()`, `_set_game_input_window_mode()`) as wrappers so external callers and signal wiring remain stable.

After the mapping IO and composition-path splits, `gui/modes/mapping/io/config_store.py` owns mapping root/map `config.json` read/write, `map_data` folder creation, and mapping config dict construction while delegating project-root/path resolution to `gui/composition/paths.py`. `gui/modes/mapping/io/map_save.py` owns directory creation, `MapStitcher.save_map_package()`, and map-level config writes. The old `gui/modes/mapping/save_load.py` wrapper has been deleted. `MappingWidget` still owns dialog timing, UI control synchronization, recognizer/stitcher parameter application timing, live capture tick delegation, path preview, advanced settings dialog orchestration, and topmost state.

After the sixth split, `gui/modes/mapping/map_renderer.py` owns BGR-to-QPixmap conversion, enhanced-map fallback unpacking, global map coloring, path polyline drawing, green viewport rectangle drawing, and current-position marker drawing. `MappingWidget` still decides when to fetch maps from stitcher and when to set Qt widgets.

After the seventh split, `gui/modes/mapping/params/binding.py` owns feature-parameter dict construction, HSV toggle application, merge-weight application, and loaded recognizer/stitcher parameter widget sync. The old `gui/modes/mapping/params_adapter.py` wrapper has been deleted. `MappingWidget` still decides when to apply runtime params and when to persist config, preserving old side-effect order.

`gui/composition/paths.py` now centralizes GUI project-root, `map_data`, root `config.json`, and advanced-settings directory resolution. Mapping config store, navigation map config store, and advanced-settings snapshot IO all delegate to it, so GUI implementation no longer uses fixed `Path(__file__).parents[n]` for project paths. `gui/composition/services.py` now centralizes the default AppContext core-service construction behind `CoreServices` and `create_core_services()`, preserving `MapStitcher(canvas_size=5000)` while making future injection explicit.

`gui/modes/mapping_widget.py` remains the second GUI page composition root, but it no longer owns capture-region/center-point selection mechanics, inline layout construction, map package persistence, or capture timer command state directly. `gui/modes/mapping/capture/selection_controller.py` owns overlay lifecycle, DPR conversion, AppContext monitor write-back, and restore-from-config selection display data. Mapping IO now lives under `gui/modes/mapping/io/config_store.py` and `map_save.py`; startup config restore now lives under `gui/modes/mapping/io/config_restore.py`; parameter binding now lives under `gui/modes/mapping/params/binding.py`; layout construction now lives under `gui/modes/mapping/ui/layout.py`; monitoring start/stop lives under `gui/modes/mapping/runtime/lifecycle.py`. `MappingWidget` still owns save timing, path preview on map click, advanced settings dialog orchestration, and topmost state. It owns advanced-setting runtime application through `_apply_advanced_settings_params()`: dialog Apply emits a command with `save=False`, accepted dialog applies with `save=True`. The next mapping split should target save-map dialog/presentation only if it reduces ownership ambiguity.

Dialog hotspots are `gui/dialogs/advanced_settings_dialog.py`, `gui/dialogs/nav_params_dialog.py`, and `gui/dialogs/color_picker_dialog.py`. `AdvancedSettingsDialog` combines tab construction, presets, file IO, runtime recognizer/stitcher application, and default parameter dictionaries. `NavParametersDialog` now has functional tabs for positioning recognition, recognition algorithm values, movement click mapping, path/A* controls, and map/debug controls; field mapping, config mutation, text parsing, signal binding, and UI value writes now live in `gui/dialogs/nav_params/config_binding.py`. It still owns widget construction, Qt screen-bound adapter logic, status labels, action buttons, and default-config save signal. Old `k_ratio/y_bias` compatibility fields remain in `NavPreferences` serialization but are no longer visible or editable in this dialog. `ColorPickerDialog` still combines color sampling, HSV range calculation, preview display, marker drawing, and opt-in debug orchestration, but wall-preview mask construction now lives in `gui/dialogs/color_picker/preview.py`. These are mostly low-to-medium risk because they can be split behind unchanged dialog classes.

After the advanced-settings command split, `gui/dialogs/advanced_settings/params_adapter.py` owns advanced-settings widget-to-dict collection, current-param widget loading, default reset values, loaded-param widget sync, and applying preset data to widgets. `gui/dialogs/advanced_settings/file_io.py` owns advanced-settings JSON snapshot save/load, default `configs/advanced_settings/` output directory, filename sanitization, payload validation, and display formatting. `gui/dialogs/advanced_settings/presets.py` owns preset option order and value dictionaries. `AdvancedSettingsDialog` still owns tab layout, file dialogs, status labels, and print messages, but runtime application is now a command signal for migrated owners; direct recognizer/stitcher mutation remains only as compatibility fallback.

After the ninth split, `gui/dialogs/color_picker/hsv_ranges.py` owns HSV conversion/sample/range math and saturation averaging, while `gui/dialogs/color_picker/image_renderer.py` owns OpenCV-to-QPixmap conversion and sample marker drawing. `gui/dialogs/color_picker/debug_output.py` owns preview debug artifact output under `debug/color_picker/`; after the old-debug cleanup it is disabled by default and enabled only by `MINIMAP_COLOR_PICKER_DEBUG`. `gui/dialogs/color_picker/preview.py` now owns wall preview mask generation, 3x3 close morphology, and preview stats. `ColorPickerDialog` still owns point collection, mode/zoom state, result text, preview label display, debug-output timing, and accept/reject flow.

After the nav-params field-spec split, `gui/dialogs/nav_params/field_specs.py` owns editable field metadata: widget attribute name, config path, field kind, widget writer, and functional group. `gui/dialogs/nav_params/config_binding.py` consumes those specs for Qt signal wiring, HSV text parsing, immutable `NavConfig` replacement, and `NavConfig` snapshot writes to controls. `NavParametersDialog` keeps the facade class and UI shell behavior. After the nav-params screen-estimator split, `gui/dialogs/nav_params/screen_estimator.py` owns click-radius math and `NavParametersDialog` only adapts Qt screen geometry to that helper before writing widget values.

Core hotspots are algorithmically sensitive and should be split in small behaviour-preserving slices. The old top-level compatibility files have been removed: `MapStitcher` now lives under `core/mapping/stitcher.py`; `NavigationCore` lives under `core/localization/navigation_core/runtime.py`; routing, input, vision, platform capture, and navigation tasks are imported from their system packages. Map package persistence is in `core/mapping/package_io.py`, weighted fusion in `core/mapping/weighted_merge.py`, display-map generation in `core/mapping/rendering.py`, and keyframe/F2F frame flow in `core/mapping/frame_pipeline.py`. Navigation construction state is in `navigation_core/state.py`, relocalization helpers in `navigation_core/relocalization.py`, frame-registration writeback in `navigation_core/registration.py`, wall-layer wrappers in `navigation_core/wall_layer.py`, diagnostics in `navigation_core/diagnostics.py`, map package loading in `core/localization/map_package.py`, display rendering in `core/localization/rendering.py`, frame registration object construction in `core/localization/frame_registration.py`, wall-template/search-window preparation in `core/localization/frame_matcher.py`, visual consistency checking in `core/localization/visual_check.py`, localization evidence DTOs/builders in `core/localization/evidence/`, and the shared `FrameRegistration` contract in `core/shared/frame_registration.py`. F2F tracking decisions, template-match result acceptance/rejection, forced relocalization flag consumption, and localization state writes remain centralized in `core/localization/localize_pipeline.py`; `NavigationCore.localize()` still returns `(x, y, confidence)`. `core/navigation_tasks/*` is still the shared route/event movement layer; GUI runtime now constructs `NavigationUpdateContext` directly and calls `NavigationTaskController.update_context()`. `core/input/controller.py` is the input-control boundary and combines map-to-screen conversion delegation, Win32 backend access, pydirectinput fallback, keyboard presses, and click diagnostics.

The event system has comparatively clear module boundaries: `EventCoordinator` observes detections and runs only a selected task, `EventMonitor` runs detectors, `EventPositionStabilizer` localizes detections, `EventMemory` owns task lifecycle/cooldown, `EventScheduler` selects display/event-runner work inside the event layer, and `EventRunner` owns handler lifecycle. There is no event-specific action executor now; event actions become `NavigationIntent` through `NavigationTaskController`, then the GUI consumes the same intent path used by normal route navigation.

## 17. Navigation Conflict Design Options
`docs/plans/2026-05-24-navigation-route-progress-option-b-design.md` records the rejected/intermediate option B for historical comparison. It kept normal navigation and event movement as separate executors with shared route progress, but the user selected scheme C instead, so option B is no longer the active implementation direction.

Option B's useful idea, route progress and guide-anchor consumption, was absorbed into `RouteContext`, `NavigationTaskScheduler`, `MovementExecutor`, and `core/routing/anchors/` rather than implemented as two separate executors.

`docs/plans/2026-05-24-navigation-task-queue-option-c-design.md` records the active architecture now implemented in source: UI-level arbitration and dual executors have been replaced with a unified `NavigationTask` queue where required points, exit, and event tasks are scheduled by one `NavigationTaskController`. Shared movement behavior lives in `MovementExecutor`; old movement wrappers and their tests have been deleted.

`docs/plans/2026-05-24-navigation-task-queue-option-c-implementation-plan.md` remains the implementation record. The current source has already passed the planned cleanup boundary: the old ordinary navigator module, old event path mover module, old event action executor module, and their dedicated ordinary-navigator test have been removed; `NavigationModeWidget.navigation_loop()` is only a compatibility wrapper that calls `_navigation_loop_unified()`.

Reusable capabilities already present: `MovementExecutor` is reusable A* + guide-anchor + fallback movement for route and event targets; `core/routing/route_progress/` is now the single reusable route progress/projection implementation used by `RouteContext`, `routing.geometry`, and `routing.anchors.progress`; `RouteContext` remains the navigation-task route runtime context; `core/routing/geometry.py` remains the route math surface; `core/routing/pathfinder/` is reusable A* with grid, snap, coordinates, and search modules separated; `core/routing/anchors/` is reusable guide-anchor planning with progress/corridor/planner modules separated; `core/input/motion_mapping.py` is reusable map-to-screen click math; `core/events/detectors/template_matcher.py` is reusable template matching; `features/torchlight/portal/minimap_feature_matcher/` is a reusable pattern for small minimap icons whose stable feature is a colored body rather than full background pixels; `features/torchlight/portal/minimap_shape_color/` is a stricter reusable probe pattern for icons with colored core plus light outer-ring/shape constraints; `features/torchlight/portal/minimap_hit_filter.py`, `environment_signature.py`, and `completion_detector.py` now hold portal helper logic that used to be embedded in detector/handler files. `core/events/window_finder.py` and `core/input/win32_driver.py` are reusable Windows input/window primitives; `NavConfig` and `EventSystemConfig` are separate runtime configuration contracts. Reusable capabilities now extracted from GUI include route overlay rendering, event overlay rendering, navigation capture geometry, navigation viewport geometry, mapping save/load config IO, mapping display rendering, mapping UI layout construction, mapping parameter control adapters, advanced-settings parameter mapping, color-picker HSV range math, and color-picker image marker rendering. Reusable capabilities still trapped in GUI include larger dialog layout composition and some owner-based composition wrappers.

Recommended refactor order is now: treat the current core/gui cleanup as an acceptance phase. The two GUI composition roots (`gui/modes/navigation/widget.py` and `gui/modes/mapping_widget.py`) are kept as public class entrypoints, and remaining internal wrappers are kept only where they serve Qt signals/timers, lifecycle targets, public slots, or ordering facades. The old top-level compatibility shells have already been removed on both core and GUI sides. Legacy cleanup already completed in this area: color-picker preview artifacts no longer write to CWD, advanced-settings parameter snapshots now write to `configs/advanced_settings/`, the unused `gui/widgets_fixed.py` backup has been removed after reference audit, and old `k_ratio/y_bias` fields are kept for config compatibility but hidden from the navigation parameter UI.

`architecture_docs/zh-CN/core/CORE_MODULARIZATION_PLAN.md` 记录了 core 专项模块化迁移过程。当前实现已越过“保留顶层壳子”阶段：`core.capture`、`core.recognizer_optimized`、`core.stitcher_core`、`core.navigation_core`、`core.pathfinder`、`core.route_manager`、`core.motion_controller`、`core.input_driver` 等旧顶层文件已删除；真实实现进入 `core.routing`、`core.input`、`core.vision`、`core.platform`、`core.mapping`、`core.localization`、`core.shared` 等新包。`MapStitcher` 从 `core.mapping` 导入，`NavigationCore` 从 `core.localization` 导入，`MotionController` 从 `core.input` 导入，屏幕捕获从 `core.platform.SquareScreenCapture` 导入。`NavigationCore.localize()` 仍是定位主链入口，状态写入集中在 `core.localization.localize_pipeline.py`。

`architecture_docs/zh-CN/core/ARCHITECTURE_OPTIMIZATION_RULES.md` 现在是 core 后续优化的规则源：不按固定行数、固定文件数或固定层级机械拆分，而按概念重复、依赖方向、模块深度、状态局部性和真实复用方判断是否值得动。`architecture_docs/zh-CN/core/CORE_OPTIMIZATION_PLAN_V2.md` 是按该规则深读 core 后形成的下一阶段计划：P1 统一 `RouteContext`、`routing.geometry`、`routing.anchors.progress` 中重复的 route progress/projection；该 P1 的第一段已经落地到 `core/routing/route_progress/`，旧 geometry dict、RouteContext dataclass 和 anchors progress float 返回形态保持；P1 第二段已经落地到 `core/localization/evidence/`，coordinate diagnostics 现在内部消费 `LocalizationEvidence`，不再在定位诊断流程里散读 raw registration metadata，同时 `NavigationCore.localize()` 和 `CoordinateDiagnostics.record_localization()` 调用面保持不变；P2 共享日志格式化已落地到 `core/shared/diagnostics/formatting.py`，但 event writer、topic routing 和 coordinate log 文件路径没有改变；P2 固化 `EventAction -> NavigationIntent` 翻译层，保持事件 handler 不直接执行输入。V2 原阶段未包含 hook；当前后续阶段已新增 `core/events/hooks/`，先落地 `event_visible_target` 和 `event_completed` 两个观察型 hook，仍不因文件还有数百行就继续机械拆分；旧兼容壳清理已经单独推进并完成顶层文件删除。

`EventAction -> NavigationIntent` seam 已在中文架构文档中固化：`architecture_docs/zh-CN/core/events/ARCHITECTURE.md` 明确 event handler 只能返回 `EventAction | None`，不能直接依赖 `MotionController`、GUI 或输入执行器；`architecture_docs/zh-CN/core/navigation_tasks/ARCHITECTURE.md` 明确 `core/navigation_tasks/intent_factory.py` 和 `event_task_runner.py` 是唯一翻译链路。当前不拆 `intent_factory.py`，因为它接口窄、语义集中，拆分会降低 locality。

Legacy wrapper cleanup for implementation imports has completed for the top-level core/gui compatibility files listed above. Remaining package `__init__.py` files are kept only where they are canonical system package entrypoints, not legacy file-path shells. The current core/gui cleanup phase has passed two consecutive clean acceptance audits. Public GUI class entrypoints remain stable, justified internal wrappers are retained, and hook/new feature architecture is deferred to the next phase.

## 18. Coordinate Drift Diagnostics
`core/navigation_tasks/coordinate/diagnostics.py` is the dedicated coordinate-mismatch diagnostic and internal relocalization trigger module. The diagnostics system writes file-only records to `logs/coordinate_diagnostics.log` and intentionally does not print to the console or `runtime.log`. `CoordinateDiagnostics.record_localization()` records invalid localization, low confidence, raw-position jumps, large raw-vs-control gaps, long F2F tracking, and visual coordinate mismatch evidence from `FrameRegistration.metadata`. `CoordinateDiagnostics.record_navigation_state()` still records route projection deviation, raw/control arrival disagreement, and "near target but not completed" stalls for the current required/exit/event task, but these are diagnostic-only and no longer trigger forced relocalization. Recovery scoring now has only two primary signals: `visual_mismatch` and `raw_jump`. `visual_mismatch` is produced only after `NavigationCore` locally re-matches the current minimap wall mask near the tracked position and the best visual position stays farther than `coordinate_visual_mismatch_threshold` for `coordinate_visual_mismatch_frames` checks. `raw_jump` remains an emergency trigger for extreme F2F jumps. Route deviation, near-target stall, raw-control smoothing gap, and long F2F duration never force relocalization by themselves.

After the coordinate diagnostics split, `CoordinateDiagnostics` remains the stable stateful facade and is exported from `core.navigation_tasks.coordinate`. `record_localization()` delegates to `coordinate.localization.record_localization_diagnostics()`, `record_navigation_state()` delegates to `coordinate.navigation.record_navigation_diagnostics()`, request consume/accept/reject/scoring delegates to `coordinate/relocalization.py`, and file logging/registration formatting live in `coordinate/log.py` and `coordinate/formatting.py`.

After the event approach split, `EventApproachController` remains the stable navigation-layer facade. `update()` delegates to `event_approach.pipeline.update_event_approach()`, `_move_toward_event()` delegates to `event_approach.motion.move_toward_event()`, `_settle_or_ready()` delegates to `event_approach.settle.settle_or_ready()`, and `_is_event_in_real_view()` / `_approach_target_from_path()` delegate to `event_approach/geometry.py`. The old private helper wrappers remain available, while DTOs live in `event_approach/models.py`.

### `CoordinateDiagnostics.record_localization(self, *, now_ms: int, raw_pos, confidence: float, min_confidence: float, registration, trusted_pos, control_pos, active_task_id: str | None) -> None`
算法：
1. 委托 `record_localization_diagnostics()` 标准化 raw/trusted/control 坐标，并提取 `FrameRegistration` 字段。
2. 更新 registration source tracking：template match 重置 F2F age；F2F 首次出现时记录起点时间。
3. 检查 active relocalization request 是否超时；若 forced global template match 未在 `recovery_timeout_ms` 内成功，则记录 rejected 并清理 active request。
4. raw 缺失或置信度低于 `min_confidence` 时节流写 `localization invalid`，并停止本轮诊断。
5. raw 相对上一帧超过 `raw_jump_threshold` 时写 `raw localization jump`；如果当前 registration 是 F2F，则注册 `raw_jump` 恢复信号。
6. raw/control gap 超过阈值只写诊断日志，不触发重定位。
7. 调用 `record_visual_consistency()` 处理 `FrameRegistration.metadata.visual_*`，只有连续 visual mismatch 达标才注册 `visual_mismatch` 恢复信号。
8. F2F 持续超过 `long_f2f_tracking_ms` 时只写诊断日志。
副作用：更新 raw baseline、F2F age、visual mismatch 计数、recovery signals 和 coordinate diagnostics 日志。
失败行为：输入坐标不可解析时降级为 `None`，不抛异常。
调用关系：called by `update_pipeline.update_controller_context()`。

### `CoordinateDiagnostics.record_navigation_state(self, *, now_ms: int, task_id: str | None, task_kind: str | None, target_pos, raw_pos, trusted_pos, control_pos, confidence: float, route_context, arrival_radius: float, registration) -> None`
算法：
1. 委托 `record_navigation_diagnostics()` 标准化 target/raw/trusted/control；缺 target 或 control 时直接返回。
2. 如果有 `route_context`，把 control 投影到 route，得到 route deviation/progress。
3. route deviation 超过 `route_deviation_threshold` 时写 `route projection deviation`，但不注册恢复信号。
4. raw 已进入 arrival radius 但 control 仍在外部时，写 `arrival mismatch raw inside control outside`。
5. control 位于 `(arrival_radius, arrival_radius + target_near_margin]` 内并持续超过 `target_stall_ms` 时，写 `near target not completed`。
6. 离开 near-target 区间时清理该 task 的 near-target timer。
副作用：更新 `_near_target_since_ms`，写 coordinate diagnostics 日志。
失败行为：缺少关键坐标时静默跳过。
调用关系：called by `update_pipeline.update_controller_context()` after task selection。

`NavigationCore.localize()` now adds a lightweight visual consistency check to the F2F branch. Every `coordinate_visual_check_interval_ms`, it scales the current wall mask to map resolution, searches only a small margin around the current tracked player position, and records `visual_player`, `visual_delta`, `visual_delta_dist`, `visual_conf`, and `visual_expected_score` into the frame registration metadata. This implements the user-facing rule: if the screenshot visually belongs at point A but the navigation point is B, and that difference is stable, then relocalize. It avoids using route shape, anchor state, or A* fallback as evidence of coordinate drift.

`NavigationTaskController.update_context()` now receives `NavigationCore.last_frame_registration` through `NavigationUpdateContext.localization.frame_registration`. The controller uses diagnostics as a navigation-internal recovery event: it returns `WAIT` with `metadata.force_relocalize=True`, resets `MovementExecutor`, and prevents movement clicks during the recovery frame. When a forced global template match succeeds, `observe_localization(..., force_snap=True)` snaps `trusted/control` to the accepted coordinate. Normal coordinate recovery clears the old active task so scheduling replans from the corrected position; portal post-interaction recovery keeps the active event task when `forced_reason="portal_wait_result"` so the same handler can mark the teleport session complete.

`NavigationCore.request_full_map_localization(reason)` is the shared full-map recovery entry point, and `request_global_relocalization(reason)` remains a compatibility alias. It clears `is_localized`, `prev_mask`, and `prev_wall_mask`; the next `localize()` call skips F2F/local search, runs the same full-map `wall_layer` template matching path used on navigation start, uses the base `confidence_threshold` instead of a stricter recovery-only threshold, bypasses normal jump rejection, and tags `FrameRegistration.metadata.forced_global=True`. `NavigationRuntimeFrameLoop` consumes the force-relocalize intent, calls this method, logs `navigation forced global relocalization`, and returns before executing input.

`docs/plans/2026-05-24-coordinate-drift-diagnostics.md` records the current implemented relocalization strategy and the dedicated log events: `coordinate relocalization requested/forced/accepted/rejected`. Fixed global offset parameters remain prohibited.

## 20. Perception Engine Modularization (current foundation)

This section records the current game-agnostic perception seam. Progress belongs in `ITERATION_LOG.md`; this section describes the current code and its contracts.

### C4 Level 1 - System context

```text
+------------------+       +---------------------+       +------------------+
| GUI / Workbench   | ----> | Perception Engine   | ----> | TargetDetection  |
+------------------+       +---------------------+       +------------------+
                                      |
                                      v
                               CoordinateMapper
                                      |
                                      v
                              Workflow / Action
```

### C4 Level 2 - Perception modules

```text
+--------------------+     +-------------------+     +----------------------+
| profiles.py         | --> | registry.py       | --> | engine.py            |
| game/scene/target   |     | descriptor/factory |     | public composition   |
+--------------------+     +-------------------+     +----------------------+
          |                         |                         |
          v                         v                         v
+--------------------+     +-------------------+     +----------------------+
| algorithms/base.py  |     | builtins.py       |     | models.py            |
| parameter metadata  |     | color/template    |     | frame/result/evidence|
+--------------------+     +-------------------+     +----------------------+
          |                         |                         |
          +-------------------------+-------------------------+
                                    v
                    +-----------------------------------+
                    | stages/runner -> fusion           |
                    |        -> confirmation -> selection |
                    +-----------------------------------+
```

### C4 Level 3 - Current call path

```text
PerceptionEngine.detect(frame, profile)
  -> DetectorRunner.run(frame, profile)
  -> runtime factory override or AlgorithmRegistry.create(algorithm_id, copied_parameters)
  -> ColorRegionDetector.detect(frame), TemplateDetector.detect(frame), or a provider-backed adapter
       -> for injected OCR: RapidOcrProvider.recognize(frame, provider_parameters)
       -> OcrSpan(text, full-frame bbox, coordinate_space, confidence)
       -> ProviderBackedOcrDetector.detect(frame)
  -> fuse_candidates(candidates, merge_radius)
  -> ConfirmationTracker.observe(profile_key, candidates, required_frames, match_radius)
  -> select_candidate(candidates, strategy, reference)
  -> PerceptionRunResult(detections, by_algorithm, errors, selected, confirmed)
```

### Directory and file index

`core/perception/__init__.py` - Public exports for generic models, profiles, registry, built-in registry factory, pipeline, run result, and geometry-aware preprocessing contracts. It must not import GUI, input, navigation, or game-specific modules.

`core/perception/models.py` - Data-only coordinate spaces, bounding boxes, frame context, evidence, normalized target detections, and whole-run result. `BoundingBox.center` derives a pixel-space center; `BoundingBox.normalized()` validates positive frame dimensions and returns relative rectangle values; `TargetDetection.__post_init__()` rejects empty target types, invalid centers, or confidence outside 0..1. `PerceptionRunResult` carries confirmed detections, per-instance raw detections, isolated errors, optional final selection, boolean confirmation status, and each current track's frame count without action side effects.

`core/perception/preprocessing/__init__.py` - Public game-agnostic preprocessing surface. It exports image-artifact geometry contracts only; importing it does not acquire a resource, execute OpenCV, inspect a game profile, or import legacy recognizers.

`core/perception/preprocessing/models.py` - `ImageGeometry` validates a source/output extent pair, one existing `CoordinateSpace`, and a 3×3 output-to-source transform. `map_point_to_source()` applies the homogeneous transform and rejects a zero homogeneous denominator; `map_box_to_source()` projects all four corners and returns their source enclosing `BoundingBox`. `ImageArtifact` combines processed pixels, `FrameContext`, geometry, and metadata; it rejects missing image dimensions, output-shape disagreement, source-frame dimension disagreement, or coordinate-space disagreement. It imports only existing generic perception models.

`core/perception/preprocessing/geometry.py` - `crop()`, `resize()`, and `pad()` apply the corresponding pixel operation and construct a new `ImageArtifact`. Each composes a local output-to-previous homogeneous transform with the artifact's output-to-source matrix, so any chain of ROI, resize, and padding operations maps pixels back to the original frame. Invalid artifact types, non-positive dimensions, out-of-bounds crops, and negative padding raise explicit errors; the module has no game, detector, input, or GUI dependency.

`core/perception/preprocessing/image_ops.py` - Game-agnostic, validated OpenCV/NumPy operations: gamma LUT, Gaussian/median blur, L-channel CLAHE, top-hat response/addition, percentile normalization, absolute intensity and per-BGR-channel scale, grayscale/HSV conversion, and Canny. Every operation accepts only a non-empty 2D/3D array and returns an independent or OpenCV-produced `uint8` image; it does not attach wall/fog/player meanings or access a recognizer. Invalid kernels, ranges, image channel shapes, and non-finite parameters fail explicitly.

`core/perception/preprocessing/masks.py` - Game-agnostic binary-mask operations: HSV range and binary threshold, explicit open/close/dilate/erode morphology, 8-connected area filtering, saturation and circle masks, mask exclusion, and normalized weighted fusion. Inputs are mask/image arrays plus caller-supplied parameters; the module neither discovers a player centre nor assigns event or game semantics. Shape/range/operation errors fail before OpenCV dispatch.

`core/perception/profiles.py` - Immutable `AlgorithmProfile` and `TargetProfile` configuration objects. `AlgorithmProfile.__post_init__()` validates identifiers and non-negative weight, then copies parameter/metadata dictionaries. `TargetProfile.__post_init__()` validates hierarchy identifiers, confidence range, confirmation frame count, unique instance IDs, and a normalized selection policy in `confidence|first|nearest`; it copies metadata and converts algorithms to a tuple. `to_dict()`/`from_dict()` preserve schema version and nested metadata; `copy()` deep-copies mutable descendants. `SUPPORTED_SELECTION_STRATEGIES` is the profile-level configuration contract.

`core/perception/profile_store.py` - Versioned JSON persistence. `load_target_profile(path)` reads UTF-8 JSON, requires an object, and delegates validation to `TargetProfile.from_dict()`. `save_target_profile(path, profile)` creates the parent directory, writes an indented UTF-8 temporary file, and atomically replaces the destination.

`core/perception/algorithms/base.py` - `ParameterSpec` and `AlgorithmDescriptor` metadata consumed by future GUI adapters. Parameter construction validates supported kinds, numeric ranges, choice defaults, and unique descriptor parameter names. No image processing occurs here.

`core/perception/algorithms/color.py` - `ColorRegionDetector.detect(frame)` converts grayscale/BGR/BGRA input to HSV, builds normal or hue-wrapping masks, optionally applies odd-sized open/close morphology, extracts external contours, filters area, computes fill-ratio confidence, and returns sorted `TargetDetection` values with area evidence. Invalid or empty frames return an empty list.

`core/perception/algorithms/template.py` - `TemplateDetector` accepts an in-memory array or file path; `_load_template()` directly reads a path with OpenCV, raises `FileNotFoundError` when unreadable, normalizes gray/BGR/BGRA data, and preserves an alpha-derived mask. `detect(frame)` converts input to BGR/gray/edges, iterates configured scales, combines grayscale and edge responses, optionally applies the mask, extracts thresholded top-k hits with spatial suppression, merges duplicate scales, and returns bbox detections with score evidence. Low-texture templates use normalized squared difference to avoid correlation degeneracy. The independent `template_adapter.py` now supplies provider-resolved arrays; this class intentionally retains path compatibility while keeping matching and result normalization here.

`core/perception/algorithms/template_adapter.py` - `ProviderBackedTemplateDetector.__init__(target_type, provider, resource_id, parameters=None)` validates a non-empty resource ID and callable `provider.load`, calls `load(resource_id)` exactly once, requires a `TemplateResource`, stores provider/resource metadata, and constructs the unchanged `TemplateDetector` with only `resource.image`. `detect(frame)` delegates and returns the detector's `TargetDetection` list unchanged, preserving target type, coordinate space, bbox, confidence, source, and evidence. Provider exceptions propagate without path fallback; invalid provider output raises `TypeError`.

`core/perception/algorithms/ocr_adapter.py` - `ProviderBackedOcrDetector.__init__(target_type, provider, parameters=None)` validates callable `recognize`, requires non-empty `text_query`, validates exact/contains/regex matching, confidence bounds, optional result cap, and optional provider-parameter mapping. `detect(frame)` calls the provider once with a fresh parameter copy, rejects invalid raw output, filters `OcrSpan` text and confidence, ranks matches by confidence, and converts them to geometry-preserving `TargetDetection` values with text, language, raw evidence metadata, capture time, and source `ocr`. Provider errors propagate; target selection, coordinate remapping, capture, GUI, and actions remain outside this module.

`core/perception/algorithms/shape.py` - `ShapeDetector.__init__(target_type, parameters=None)` validates generic threshold, morphology, contour-area, polygon-vertex, approximation, circularity, solidity, and result-limit parameters. `detect(frame)` converts a grayscale/BGR/BGRA array to thresholded external contours, optionally removes noise/fills gaps, filters each contour, derives its bounding box and center, ranks candidates by fill/solidity confidence, and returns `TargetDetection` values with numeric shape evidence. Invalid/empty frames return no result; it never consults a template/provider or target-specific legacy logic.

`core/perception/algorithms/__init__.py` - Public algorithm package surface. It re-exports descriptor/parameter metadata, color/template/shape detectors, `ProviderBackedTemplateDetector`, and `ProviderBackedOcrDetector`; importing it does not instantiate a detector or provider.

`core/perception/builtins.py` - `create_default_algorithm_registry()` registers available color/template/shape factories and explicit unavailable feature/OCR descriptors. `_create_color()` and `_create_shape()` copy parameters and inject `target_type`; `_create_template()` remains the no-provider compatibility wrapper. `create_template_detector(parameters, template_provider=None)` strips the target and resource-source fields, enforces exactly one of in-memory `template`, non-empty `template_path`, or `template_resource_id`, requires an explicit provider only for the resource-ID branch, then returns either unchanged `TemplateDetector` or `ProviderBackedTemplateDetector`. `create_ocr_detector(parameters, ocr_provider=None)` requires an explicit runtime provider and constructs `ProviderBackedOcrDetector`; its unavailable default descriptor still publishes editor metadata for query, matching, case sensitivity, confidence, and result cap. The registry itself remains provider-agnostic.

`core/perception/registry.py` - `AlgorithmRegistry` owns descriptor/factory maps. `register()` rejects duplicate IDs and missing factories for available algorithms. `descriptor()` reports unknown IDs. `create()` rejects unavailable or factory-less algorithms and passes a deep-copied parameter mapping to the factory.

`core/perception/pipeline.py` - Source-compatible forwarding shell. `PerceptionPipeline.__init__()` stores the registry and locally imports/creates a default `PerceptionEngine`, avoiding an import cycle. `run(frame, profile, reference=None)` returns `engine.detect(frame, profile, reference=reference)` unchanged and `reset_confirmation(profile=None)` delegates unchanged. `_fuse_candidates()` remains only for old private import callers and wraps the standalone `fuse_candidates()` function; no Pipeline execution path imports or owns detector, fusion, confirmation, or selection state.

`core/perception/stages/__init__.py` - Side-effect-free package surface for engine-owned decision stages. It re-exports `DetectorRunner`/`DetectorRunResult`, `fuse_candidates`, `ConfirmationTracker`/`ConfirmationResult`, and `select_candidate`; importing it neither creates temporal state nor accesses an image, provider, GUI, or action layer.

`core/perception/providers/contracts.py` - Dependency-light raw-provider contracts. `ProviderCapability` identifies frame source, template resource, OCR, and feature back-end roles; `ProviderDescriptor` validates ID/name/capability/status and defensively serializes metadata. `TemplateResource`, `OcrSpan`, and `FeatureMatch` carry asset/text/correspondence evidence without target semantics. `FrameSource`, `TemplateResourceProvider`, `OcrProvider`, and `FeatureBackend` Protocols return these DTOs or `FrameContext`. `ProviderRegistrationError`, `UnknownProviderError`, `ProviderCapabilityMismatchError`, and `ProviderUnavailableError` are disjoint failure categories for the upcoming registry. It imports existing perception models but no OCR, feature, capture, GUI, input, or action implementation.

`core/perception/providers/__init__.py` - Public provider surface. It re-exports raw DTOs, capability enum, Protocols, error taxonomy, `RAPIDOCR_PROVIDER_ID`, `RapidOcrProvider`, and the model-resource API (`RAPIDOCR_PPOCR_V6_MULTILINGUAL_SMALL`, `RapidOcrModelSpec`, catalog lookup, local validation, and engine-option resolver). Importing it loads no optional OCR package, constructs no ONNX model, downloads no resource, and performs no model-file I/O.

`core/perception/providers/rapidocr.py` - Optional local OCR implementation. `RapidOcrProvider` lazily imports and caches one `rapidocr_onnxruntime.RapidOCR` backend, serializes calls that may mutate RapidOCR threshold settings, accepts a whole `FrameContext.image` or a validated/clipped ROI, converts each returned polygon into an original-frame `BoundingBox`, and returns raw `OcrSpan` evidence. Its public per-call controls are `roi`, result-language label, and copied `backend_options`; it neither matches a target text nor accesses capture, GUI, coordinate mapping, input, or game workflows. Missing optional packages and malformed backend data become explicit provider failures.

`core/perception/providers/rapidocr_models.py` - Source-controlled, provider-composition-only catalog for optional RapidOCR recognition assets. `RapidOcrModelSpec` validates manifest metadata; `get_rapidocr_model_spec()` and `list_rapidocr_model_specs()` make model IDs explicit; `verify_rapidocr_model_file()` streams a local ONNX file through SHA-256; and `resolve_rapidocr_engine_options()` returns a new `RapidOcrProvider` option mapping only after a selected model is present and valid. The current entry is PP-OCRv6 multilingual small, chosen for Traditional Chinese coverage. The module imports no RapidOCR runtime, does no network I/O, and contains no target, game, action, or workflow policy. It rejects a caller-provided `rec_model_path` so the resolved model cannot bypass its own integrity check.

`tools/probes/install_perception_ocr_model.py` - Explicit operator-facing installer for the model catalog. The direct CLI bootstrap adds `src` before importing `auto_modules`; `install_rapidocr_model()` returns a valid existing file or writes a same-directory `.part` download, verifies SHA-256, then atomically replaces the final ONNX file. It removes only its own temporary file on failure and never overwrites an old model until the replacement verifies. `resources/assets/perception_models/` is ignored, so this utility is the deliberate asset acquisition boundary rather than an import-time or inference-time side effect.

`core/perception/providers/registry.py` - Capability-safe provider catalog. `ProviderRegistry.register(descriptor, provider)` rejects duplicate IDs, rejects implementations for unavailable descriptors, and rejects missing implementations for available/experimental descriptors; it stores but never invokes an object provider. `descriptor(id)` raises `UnknownProviderError`; `descriptors(capability=None)` preserves registration order and filters by enum capability; `resolve(id, capability=None)` first validates the known descriptor, then expected capability, then availability before returning the identical object. It does not inspect Protocol conformance or transform raw evidence, which remains an adapter responsibility.

`core/perception/providers/builtins.py` - Discovery-only default catalog. `create_default_provider_registry()` registers five stable unavailable descriptors (`frame.screen`, `template.resource`, `ocr.default`, `ocr.rapidocr_onnxruntime`, `feature.default`) with no implementation. The RapidOCR descriptor supplies an install hint only; construction has no filesystem, desktop, network, capture, OCR, ML, or feature-backend side effect. An application must explicitly compose an available implementation before `resolve()` succeeds.

`core/perception/stages/runner.py` - Instance-isolated detector execution. `DetectorRunner.__init__(registry, factory_overrides=None)` stores optional runtime factory overrides without serializing or inspecting them. `run(frame, profile)` skips disabled `AlgorithmProfile` instances; for every enabled instance it copies parameters, overrides `target_type` with the profile target, creates a detector via an override (after descriptor validation) or `AlgorithmRegistry.create()`, normalizes a falsey detector result to an empty tuple, and rejects non-`TargetDetection` output or any detection whose target type differs from the enclosing profile. It returns `DetectorRunResult(candidates, by_algorithm, errors)`: a per-instance exception becomes `"ExceptionType: message"` in `errors` and does not abort later instances. It has no fusion, confirmation, selection, input, or GUI side effect.

`core/perception/stages/fusion.py` - Geometry-only multi-algorithm candidate fusion. `fuse_candidates(candidates, merge_radius)` clamps its radius at zero, sorts candidates by decreasing confidence, and greedily compares a candidate only against already retained candidates. `_find_match()` permits a merge exactly when `target_type` and `coordinate_space` match and Euclidean center distance is within the radius. `_merge_pair()` retains the higher-confidence primary geometry and confidence, uses non-empty primary-or-secondary optional fields, concatenates evidence, and records the distinct non-empty detector sources in `metadata["fused_sources"]`. It has no game-specific semantics; invalid field values are rejected earlier by `TargetDetection` construction.

`core/perception/stages/confirmation.py` - Per-target temporal confirmation state. `ConfirmationTracker.observe(profile_key, detections, required_frames, match_radius)` clears that key and returns all candidates immediately for one-frame confirmation; on an empty frame it clears that key and returns unconfirmed. Otherwise, it uses `_nearest_track()` to match each current candidate once to the closest unused prior track of the same `target_type` and `coordinate_space` within the radius, increments stable counts, starts unmatched tracks at one, persists only this profile key's next tracks, and returns only tracks reaching `required_frames`. `reset(profile_key=None)` clears either one profile's memory or all memory. State is process-local; callers must provide a stable, game/scene/target-scoped key and reset it at an intentional session boundary.

`core/perception/stages/selection.py` - Pure final-candidate policy. `select_candidate(candidates, strategy="confidence", reference=None)` returns `None` for no candidates; otherwise it keeps original upstream order for `first`, chooses minimum Euclidean center distance for `nearest` with a reference point, falls back to maximum confidence for `nearest` without a reference, and chooses maximum confidence for `confidence`. Any other non-empty strategy raises `ValueError`; it never maps coordinates or performs an action.

`core/perception/engine.py` - Stable target-level `PerceptionEngine` core. The default `detect(frame, profile, reference=None)` validates `FrameContext` and `TargetProfile`, then `_run_stages()` invokes `DetectorRunner`, filters by `min_confidence`, fuses by non-negative `metadata.merge_radius` (default 12), confirms by raw `(game_id, scene_id, target_type)`, selects from confirmed detections, and assembles `PerceptionRunResult`. `__init__(registry=None, pipeline=None, algorithm_factories=None)` supports explicit runtime factory overrides (such as provider-backed template or OCR closures) while rejecting overrides combined with a legacy Pipeline; provider objects never enter profile JSON. `detect_target()` resolves a game/scene/target profile first. `register_profile(profile, replace=False)` derives a stripped non-empty key, rejects accidental duplicates unless replacement is explicit, clears that key's confirmation track on a replacement, and stores `profile.copy()`. `unregister_profile()` also clears its track before returning a defensive copy; `resolve_profile()` raises explicit `KeyError` for unknown keys; `profiles()` returns insertion-ordered copies; `descriptors()` exposes the registry catalog. `reset_confirmation(profile=None)` clears direct tracker state; only an explicitly injected legacy Pipeline delegates to that Pipeline. The core keeps GUI, inputs, and workflows out.

`core/spatial/models.py` and `core/spatial/calibration.py` - Explicit coordinate-space DTOs, window rectangles, affine transforms, anchor fitting, and registered mapping. These modules are recognition/action agnostic and currently do not replace `MotionController`.

`core/spatial/desktop_mapping.py` - Pure desktop-capture-to-input geometry adapter. `ScreenGeometry(left, top, width, height, dpi_scale_x=1.0, dpi_scale_y=1.0)` normalizes finite values, requires positive extents/scales, and uses half-open containment so a point on the right/bottom edge cannot pass as an input target. `MappedPoint(source_point, source_space, destination_point, destination_space, metadata)` requires explicit coordinate-space enum values and freezes a copy of transform evidence. `physical_screen_point(x, y)` is the explicit identity constructor for a coordinate already declared to be `PHYSICAL_SCREEN`; it rejects non-finite values and does not imply capture/calibration. `DesktopCoordinateMapper(source_size, destination)` accepts a positive two-pixel source extent, computes `scale_x = destination.width / source_width` and `scale_y = destination.height / source_height`, then stores the corresponding existing `AffineTransform` with desktop origin translation. `map_point(point, source_space)` only accepts finite in-image `FULL_SCREEN` points, maps through that transform, rejects points outside the physical rectangle, and returns `MappedPoint(..., destination_space=PHYSICAL_SCREEN)` with source/destination dimensions, scales, origin, DPI observation, and transform label. It has no capture, OCR, input, window focus, or game policy side effect.

`core/platform/desktop_frame_source.py` - Runtime display-frame/geometry composition. `WindowsPrimaryMonitorGeometryProvider` inherits the Windows-only DPI-awareness bootstrap and returns primary-monitor `ScreenGeometry(left=0, top=0, width=SM_CXSCREEN, height=SM_CYSCREEN)`; it is the `DesktopFrameSource()` default. `WindowsDesktopGeometryProvider` remains the explicit reusable full-virtual-desktop provider, reading Win32 virtual-screen left/top/width/height. Both report the system DPI observation. `DesktopFrameSource.capture()` obtains exactly one geometry, passes it to its injectable capture backend, verifies a non-empty array shape, and produces `FrameContext(image, width, height, coordinate_space=FULL_SCREEN, metadata=physical display region + DPI)` paired with that same geometry. `_capture_desktop()` uses a temporary existing `SquareScreenCapture` for precisely that rectangle and closes it in `finally`. The source never recognizes targets or sends input.

`core/actions/contracts.py` + `core/actions/models.py` - Device-independent action schema. `ActionCommand` validates device targets for `MOVE`, `CLICK`, `DOUBLE_CLICK`, keyboard, and virtual-gamepad primitives; legacy `ActionRequest(kind, point, interval_ms=80)` intentionally remains limited to move/double-click mapped-pointer compatibility. `ActionResult(executed, point, device_id, kind, started_at_ms, completed_at_ms, metadata)` integer-normalizes its executed point, rejects empty device IDs, and freezes result diagnostics. These contracts neither know OCR text nor import a Windows/mouse backend.

`core/actions/mouse.py` - Mouse-specific implementation behind `MouseDevice(move_to, mouse_down, mouse_up)` Protocol. `MouseActionAdapter.execute(request)` rejects non-physical destinations, rounds the already-validated physical float coordinates once at the device boundary, calls `move_to` once, returns a move-only result for `MOVE`, sends one left down/up pair for generic `CLICK`, or sends exactly two pairs separated by `interval_ms` for `DOUBLE_CLICK`. A `False` movement result raises `ActionExecutionError`; device errors propagate. It deliberately does not clamp, focus a window, capture a screen, select OCR candidates, or use navigation's `MotionController` pipeline.

`core/input/action_adapter.py` - `MotionControllerActionAdapter` is the temporary backend bridge for generic primitive commands. It accepts only `CLICK` at an explicit physical mapped point and one-key `KEY_CHORD`, then delegates to `MotionController.click_screen_position()` / `press_key()` so control enablement, click focus, bottom guard and installed backend policy remain authoritative. It returns `executed=False` when the legacy controller deliberately skips disabled input and rejects map movement or other unsupported command kinds before any controller I/O.

`workflows/desktop_ocr_action_proof.py` - Thin, explicit safety composition for a desktop mapping demonstration. `DesktopOcrActionProof.run(target_text, execute=False)` captures once through `DesktopFrameProvider`, builds the existing `ProviderBackedOcrDetector` with an exact case-sensitive configured text predicate and confidence floor, returns `not_found` for zero matches and `ambiguous` for any count other than one, maps the one detection center with `DesktopCoordinateMapper`, and returns `rejected` if the geometry/coordinate contract fails. Otherwise it returns a `dry_run` report; only `execute=True` builds `ActionRequest(DOUBLE_CLICK, mapped_point)` and invokes the injected `MappedActionAdapter`. `DesktopProofReport` retains frame extent, geometry, detection, mapped point, action result, and refusal reason so callers can audit every hop. This is the only module that combines detection, mapping, and action; all target text is workflow/CLI configuration rather than core logic.

`utils/run_desktop_ocr_action_proof.py` - Directly executable proof CLI. It bootstraps the project import path, explicitly resolves the installed PP-OCRv6 model to `RapidOcrProvider` engine options, creates the primary-monitor-default `DesktopFrameSource` before `InputDriver` so Win32 input shares the process's DPI-aware physical space, and injects `MouseActionAdapter` into `DesktopOcrActionProof`. `--text` is required, `--execute` is opt-in, and `report_as_dict()` emits only JSON primitives including source image size, physical bounds, OCR bbox/center/confidence, mapping evidence, and exact action result. Non-successful safety statuses exit `2`; dry-run/executed exits `0`.

### Flow: Desktop OCR target to physical mouse action proof

1. `utils/run_desktop_ocr_action_proof.py::main()` reads configuration (`--text`, confidence, installed model directory, dry-run/execute) and calls `build_live_proof()`. It passes only composition dependencies; no profile JSON stores an OCR engine, screen object, or input driver.
2. `build_live_proof()` calls `DesktopFrameSource()` first. Its default `WindowsPrimaryMonitorGeometryProvider` requests process DPI awareness; later `InputDriver()` uses the same physical coordinate interpretation. `resolve_rapidocr_engine_options()` independently validates the selected ONNX resource and `RapidOcrProvider` remains lazy until frame recognition.
3. `DesktopOcrActionProof.run()` calls `DesktopFrameSource.capture()`. The input is no arguments; its output is `FrameContext` with BGR image, source pixel width/height, `FULL_SCREEN`, timestamp, physical geometry metadata plus the `ScreenGeometry`. `SquareScreenCapture` performs the only screen read in this hop.
4. The workflow constructs `ProviderBackedOcrDetector` and calls `detect(frame)`. The input includes the configured exact text and confidence threshold; `RapidOcrProvider.recognize()` returns `OcrSpan` with a source-frame box, and the adapter output is one or more `TargetDetection` values with center/text/confidence. No mapping or input happens here.
5. The workflow checks candidate cardinality. Zero candidates returns `DesktopProofReport(status="not_found")`; two or more returns `status="ambiguous"`; neither branch creates `ActionRequest` or calls the action adapter.
6. For exactly one `TargetDetection`, `DesktopCoordinateMapper.map_point(Point2D(*detection.center), detection.coordinate_space)` maps source image pixels to `PHYSICAL_SCREEN`. Invalid coordinate space, image bounds, or physical bounds returns `DesktopProofReport(status="rejected")` with the exception reason; it never clamps.
7. In dry-run mode the workflow returns `DesktopProofReport(status="dry_run", detection, mapped_point)` and stops. In execute mode it creates `ActionRequest(DOUBLE_CLICK, mapped_point, interval_ms)` and calls `MouseActionAdapter.execute()`.
8. `MouseActionAdapter` rounds destination physical floats once, invokes `InputDriver.move_to(x, y)`, emits two Win32 mouse down/up pairs, and returns `ActionResult`. The workflow returns `DesktopProofReport(status="executed")`; the CLI serializes the exact input point and action timestamps.

### Reserved flow: device-neutral action to virtual gamepad backend (not wired yet)

1. A future workflow will create a device-neutral `core.actions` request; it must not import `VirtualGamepadClient` or host protocol DTOs.
2. A future `core.actions.VirtualGamepadActionAdapter` will translate that request into a bounded command, source identity, controller slot, and finite TTL, then call `virtual_gamepad.client.python.VirtualGamepadClient`.
3. `VirtualGamepadClient.request()` serializes one JSON-lines request/response pair over its own current-user named-pipe connection; the host can serve this connection concurrently with the UI connection.
4. `NamedPipeServer.ServeClientAsync()` parses the request and `CommandRouter.Handle()` selects `ControllerRegistry.Get(controller)`, then changes that slot's `StateStore` or `SafetyController` only.
5. `ReportLoop.RunAsync()` ticks every 8 ms and calls `ControllerRegistry.SubmitAll()`, which snapshots each independent source merge and submits it to the corresponding ViGEm virtual XInput controller. `EmergencyResetAll()` clears and pauses both slots.

This is an optional execution backend below `core.actions`, not a perception, coordinate-mapping, navigation, or workflow dependency. At the reviewed revision raw host commands can be accepted before a slot is Running and a `set_state` request without TTL persists; adapter integration is blocked on defining and testing the lifecycle/TTL contract.

`gui/dialogs/perception/dialog.py` - PySide6 profile editor and screenshot test bench. It owns editable profile fields, algorithm instance list, generated parameter editor, screenshot loading, engine/pipeline invocation, profile persistence dialogs, and result status. It must remain a GUI adapter and must not become a workflow or input module.

`gui/dialogs/perception/parameter_form.py` - `ParameterEditor` maps `ParameterSpec.kind` to Qt controls and reads values back with explicit bool/choice/int/float/path/text conversions. It contains no core algorithm policy.

`gui/dialogs/perception/preview.py` - `DetectionPreview` paints a pixmap and detection bounding boxes/confidences using source-space to display-space scaling. It does not alter detections or perform coordinate mapping for actions.

### Current risks and next seams

- P2's engine/Pipeline ownership boundary is complete. P3 provider contracts and P4 template/OCR adapters preserve the rule that resource acquisition and backend execution do not leak into stage APIs.
- Legacy-integration boundary (verified 2026-09-04): mapping emits `MapFrameEvidence`, localization exposes `LocalizationResult` while retaining its tuple API, navigation input translates intents to typed map/primitive composition actions, and physical click/key primitives traverse `ActionCommand → MotionControllerActionAdapter`. Portal/Loot retain event-local recognition/preprocessing and return `EventDetection`; `EventMonitor.detect()` now passes each result through the pure `EventDetection ↔ TargetDetection(MINIMAP)` bridge before the unchanged stabilizer/memory/handler chain, retaining generic observations in `last_target_detections`. Map movement remains an explicit stitched-map action handled by `MotionController` projection policy, not a desktop pointer action. Never move Portal/Loot/minimap semantic exclusions into generic perception preprocessing.
- Map-domain reuse boundary (verified 2026-09-04): `core/mapping/MapStitcher` is already a GUI-independent keyframe/frame-registration and weighted-map-merge core, but `gui/modes/mapping/runtime/session.py::MappingSession.tick()` couples capture and `HSVRecognizer.extract_combined()` to it through untyped masks and a local player tuple. Preserve the stitcher and its persisted wall/fog/explored map package; introduce typed visual-evidence and coordinate adapters at this composition edge rather than replacing map stitching with the perception engine.

- Historical full-suite health (2026-09-04): `python -m unittest discover -s tests` ran 170 tests with 166 passing and 2 skipped. The `test_advanced_settings_file_io.py` loose-file relative-import failure was outside typed localization. The three `test_pathfinder.py` failures were later traced to the test's default 30-pixel start clearance and corrected in test setup on 2026-09-29; do not treat that historical result as current suite status.

### Perception regression contracts

`tests/test_perception_stages.py` verifies instance exception isolation, geometry fusion, stable temporal confirmation, pure selection, target-type mismatch isolation, and rejection of invalid profile selection policies.

`tests/test_perception_engine.py` verifies direct detection, profile key lookup, defensive registration, explicit missing keys, replacement confirmation reset, and the P2 ownership contract: a default engine still produces a selected result when `PerceptionPipeline.run()` is deliberately made unavailable.

`tests/test_perception_pipeline.py` verifies current pipeline outcomes and the P2 compatibility contract: a Pipeline delegates the exact `frame`, `profile`, and `reference=None` to its associated Engine and returns the exact Engine result object.

`tests/test_perception_ocr_adapter.py` verifies provider invocation, exact/contains/regex predicates, confidence and result limits, validation/error propagation, factory and package surfaces, descriptor metadata, and runtime Engine composition without provider serialization.

`tests/test_perception_rapidocr_models.py` verifies named PP-OCRv6 multilingual metadata, explicit unknown-ID errors, missing/corrupt-asset rejection, copied overrides with a protected recognition path, direct script execution, checksum-before-atomic-replacement, and preservation of an old asset after a corrupt download using an in-memory downloader.

`tests/test_perception_rapidocr_provider.py` verifies lazy optional-backend initialization, polygon-to-box conversion, provider-parameter isolation, ROI crop plus full-frame coordinate restoration, malformed-output and missing-package errors, default catalog metadata, and the full `RapidOcrProvider -> OcrSpan -> ProviderBackedOcrDetector -> TargetDetection` chain. When the optional package is installed, it recognizes a generated `ENTER MAP` image and asserts a plausible image-space location. When RapidOCR, the explicitly installed PP-OCRv6 multilingual asset, and a Windows Traditional Chinese font are present, it additionally requires exact `開始儀式` and `進入異界地圖` recognition with full-frame locations.

`tests/test_perception_shape_algorithm.py` verifies synthetic circle localization, public/registry availability, rectangle vertex filtering, and invalid geometric-parameter rejection.

- Feature, motion, and ML have descriptors but no concrete implementation/provider adapter. OCR has both a provider-backed adapter and optional RapidOCR implementation; shape is a provider-free contour detector.
- The workbench currently calls the compatibility pipeline directly; P6 must route it through `PerceptionEngine`.
- Runtime screenshot capture, window discovery, anchor calibration, and action mapping are not yet connected to the generic result contract.
- Legacy Portal/Loot/minimap behavior remains outside this package and must be adapted one target at a time with regression tests.

## 19. Event Approach Stabilization
`core/navigation_tasks/event_approach/__init__.py` is the reusable navigation-layer gate for event trigger positioning. `EventApproachConfig` stores the user-tunable movement contract: `enabled`, `game_view_map_size`, `visible_margin`, `approach_lookahead`, `click_cooldown_ms`, `stop_radius`, `settle_ms`, `stable_frames`, and `max_motion_per_frame`. `EventApproachController.update()` returns an `EventApproachResult`; it now also marks `visible` and one-shot `became_visible` when the selected event task first enters the real-view box. It never calls an event handler directly.

Execution order for an event task is now: `NavigationTaskController._update_event_task()` checks `event_approach.is_released(task.id)`; if not released, `EventApproachController.update()` either returns a movement/wait `NavigationIntent` or marks the task ready. When `became_visible=True`, `_update_event_task()` emits `event_visible_target` through `controller.event_hooks` once for that navigation event task. Only after ready does the controller call `event_coordinator.run_task(event_task_id, event_tick)`. If the returned action is `COMPLETE`, `EventRunner` has already updated `EventMemory`; `_update_event_task()` then resets navigation event runtime and emits `event_completed`. This prevents `PortalEventHandler` from pressing `D` before the shared navigation layer has confirmed the event is inside the real-view box and the player has settled near it.

The approach algorithm has two movement phases. In the far phase, the target is the event global position and `MovementExecutor.step()` receives the normal `RouteContext`, so guide anchors still shape the route toward the event. When the event enters the real-view square centered on the player (`game_view_map_size / 2 + visible_margin`), the controller forces a replan, calls `MovementExecutor.step()` with `route_context=None`, a shorter `approach_lookahead`, and a per-call `click_cooldown_ms` override. This keeps the final approach wall-aware without letting old route anchors pull the player past the event.

The settle phase starts once the player is within `event_stop_radius` of either the event point or the path-derived approach point just before the event. During settling, no movement click is emitted. The gate releases only after `event_settle_ms` has elapsed and `event_stable_frames` consecutive frames stay within `event_max_motion_per_frame`. After release, the task id is recorded so the same event handler can continue through `portal_point_click`, `press D`, and `wait_result` without being blocked by the gate again. `COMPLETE`, `FAIL`, controller stop, route runtime reset, or manual event reset clear that released state.

`MovementExecutor.step()` now accepts an optional per-call `click_cooldown_ms`. This is intentionally not stored as global executor state; normal route navigation and anchor movement continue to use `NavConfig.auto_click_cooldown_ms`, while event final approach uses `NavConfig.event_approach_click_cooldown_ms`.

`gui/navigation_params.py::NavConfig` serializes the event approach parameters, and `gui/dialogs/nav_params_dialog.py` exposes them in the “事件靠近” tab. `gui/modes/navigation/map/config_applier.py::configure_navigation_task_controller()` is the single GUI-side bridge that copies those config values into `NavigationTaskController.event_approach`; `NavigationModeWidget._configure_navigation_task_controller()` remains as the old method wrapper.

### `event_approach.pipeline.update_event_approach(approach, *, task, current_pos, wall_map, pathfinder, explored_map, now_ms: int, lookahead_distance: float, route_context, movement) -> EventApproachResult`
行为：执行单帧事件靠近 gate 状态机，决定继续移动、等待定位、停稳，还是释放事件 handler。
算法：
1. 从 task 提取字符串 task id 和 float target；若 gate disabled，直接返回 ready。
2. 若 `current_pos` 或 target 缺失，返回 waiting localization 的 `WAIT` intent，不写释放状态。
3. task id 切换时调用 `approach.reset_active()`，只重置当前活动 gate 状态，不清空已释放集合。
4. 用 `_is_event_in_real_view()` 判断事件目标是否已进入真实主画面范围。
5. 若不可见：清空 settle 状态；当上一阶段不是 `far` 时设置 `movement.force_replan=True`；用 normal lookahead 和 route context 调 `_move_toward_event()` 继续按 route/anchor 靠近；记录 `event approach far`。
6. 若可见且玩家到事件距离小于 `stop_radius`，进入 `_settle_or_ready()`。
7. 若可见但未到停靠半径：必要时强制重规划，改用 `config.approach_lookahead`、禁用 route context，并用 `config.click_cooldown_ms` 控制近距离点击节流。
8. 从 movement step 的 path 中计算距离终点 `stop_radius` 的 approach target；若玩家到事件或 approach target 已足够近，进入 `_settle_or_ready()`。
9. 否则清空 settle 状态，记录 `event approach approach`，返回移动/等待 intent。
副作用：可能写 `approach._task_id`、`movement.force_replan`、settle 状态和 nav log；不调用 event handler。
调用关系：called by `EventApproachController.update()`；indirectly called by `event_task_runner.update_event_task()`。

### `event_approach.motion.move_toward_event(approach, *, task, current, target, wall_map, pathfinder, explored_map, now_ms: int, lookahead_distance: float, route_context, movement, phase: str, click_cooldown_ms: int | None) -> EventApproachResult`
行为：把一次 movement executor 结果转换成 event approach 阶段 intent。
算法：
1. 调用 `movement.step()`，传入 task id、current/target、map/pathfinder/explored、now、lookahead、route context 和可选 per-call click cooldown。
2. 若 movement 返回 `None`，记录 path unavailable，并返回 `WAIT` intent，message 为 `event approach path unavailable`。
3. 若 step 可点击且有 subgoal，intent type 为 `MOVE_MAP`；否则为 `WAIT`。
4. 将 step 的 `subgoal/path/path_kind/deviation/force_click_target` 写入 `NavigationIntent`。
5. 在 intent metadata 中写入 `event_approach_phase`，使 UI/诊断能区分 far/approach。
副作用：调用 movement 可能更新 movement 内部路径、点击节流和恢复状态；本函数自身只记录路径不可用日志。
调用关系：called by `EventApproachController._move_toward_event()` and `event_approach.pipeline.update_event_approach()`。

### `event_approach.settle.settle_or_ready(approach, *, task, current, target, approach_target, now_ms: int, distance: float) -> EventApproachResult`
行为：事件触发前停稳 gate，等待玩家在事件附近稳定若干帧并满足 settle 时间。
算法：
1. 用上一帧 player pos 计算本帧 motion；首帧 motion 视为 0。
2. 若 motion 小于等于 `max_motion_per_frame`，累加 `approach._stable_frames`；否则清零 stable frames，并把 settle 起点重置为当前时间。
3. 若 settle 起点为空，设为当前时间。
4. 计算 `waited_ms`，同时满足 `waited_ms >= settle_ms` 和 `stable_frames >= stable_frames` 时 ready。
5. 记录 `event approach settling/ready` 日志，包含 player、target、approach target、distance、waited_ms、stable_frames、motion。
6. ready 时返回 `EventApproachResult(ready=True, phase="ready")`。
7. 未 ready 时返回 `WAIT` intent，subgoal 为 approach target，path_kind 为 `event_settle`，metadata 写入 wait/stable 信息。
副作用：写入 `approach._last_player_pos`、`_stable_frames`、`_settle_started_ms` 和日志节流状态。
调用关系：called by `EventApproachController._settle_or_ready()` and `event_approach.pipeline.update_event_approach()`。

### `event_approach.geometry.approach_target_from_path(config, path, target) -> tuple[float, float] | None`
行为：根据 movement path 计算靠近事件时应停在终点前的目标点。
算法：
1. path 为空时直接返回 event target。
2. 将 path 全部标准化为 float point；长度小于 2 时返回唯一点。
3. 用 `build_cumulative_lengths()` 计算累计路径长度。
4. stop distance 取 `max(8.0, config.stop_radius)`。
5. 若总路径长度小于 stop distance，返回 path 末点。
6. 否则用 `interpolate_by_distance()` 在总长减 stop distance 处插值得到停靠点，失败时回退 path 末点。
副作用：无。
调用关系：called by `EventApproachController._approach_target_from_path()` and `event_approach.pipeline.update_event_approach()`。

Expected event logs for a good portal run are `event approach far`, `event approach approach`, `event approach settling`, `event approach ready`, `event approach released`, then portal-specific logs such as `portal point click before interaction`, `portal interaction key`, and `portal teleport completed`. If the player never releases, inspect the same log fields for `visible`, `distance`, `waited_ms`, `stable_frames`, and `motion` before changing portal handler logic.

### 2026-09-24 PoE2 首帧置信度门槛

`_poe2_first_frame_registration_config()` 将业务层 `minimum_confidence` 设为 `0.70`。
这是 PoE2 组合策略，不改变通用 `AnchoredRegistrationConfig` 默认值；锚定分数、前向覆盖率和
anchor 半径仍是独立的 fail-closed 质量门。

### PoE2 参数与运行调度

`Poe2MonitorConfig` 还持有 `first_frame_anchored_score`、`first_frame_anchored_coverage`、
`localization_fps` 和 `preview_fps`。独立 PoE2 配置窗口编辑并保存这些字段，默认值为
`0.35/0.45/30/12`，且预览 FPS 不能超过定位 FPS。

正式 `Poe2HybridProductRuntime` 由 `Poe2LocalizationWorker` 串行驱动：worker 只保留一个最新待显示状态，
不会堆积帧；页面通过 generation 丢弃停止或换图后的旧结果。真实 `SquareScreenCapture` 在线程中建立线程本地
MSS 句柄，结束时释放。后台 worker 启动前页面先进入 active 状态，避免极快首帧信号在 UI 连接完成前被忽略；
GUI 位置/轨迹消费最新状态，截图和特征预览按 `preview_fps` 节流。匹配特征预览只有在本帧为空时才显示占位文字，
成功帧的 pixmap 不会再被后续 `setText()` 清除。

`_Poe2EvidenceBuilder` 优先调用 `HSVRecognizer.extract_combined_with_processed()`，将墙体预处理结果复用于
墙体、边缘和 raw gray 输出；旧 recognizer 仍走兼容路径。runtime 日志记录 `capture_ms`、`evidence_ms`、
`localization_ms`、实际定位 FPS、UI 实际 FPS 和被覆盖的显示状态数量。

### PoE2 双人正式定位链路

`Poe2MonitorConfig.tracking_mode` 是正式页的业务策略开关，旧配置缺省为 `single`。
`src/auto_modules/ui/modes/poe2/composition.py` 在组合层按该策略选择单人
`build_poe2_hybrid_localization_experiment()` 或双人
`build_poe2_dual_localization_experiment()`；页面和 worker 不持有算法分支。

双人组合位于 `features/poe2/live_terrain/experimental/multiplayer_localization/`：
`Poe2DualLocalizationSession` 负责截帧、证据构造、首帧/恢复生命周期，
`DualFirstFrameExperiment` 负责双 anchor 与同帧颜色候选注册，`DualVisualTracker` 负责固定
角度/镜像/比例下的共同视口位移、两名候选独立映射和局部纠偏，并输出每名角色的轨迹。session 首帧与恢复只调用一次
`Poe2DualMemoryAnchorProvider.read_once()`；普通视觉帧不读内存。

`Poe2HybridProductState` 向后兼容单人字段，并增加 `dual_players`、`dual_screen_positions`、
`dual_trajectories`、`dual_status` 和 `dual_wall_quality`。正式 page 将这些 native 点通过同一
registration transform 转为显示坐标，`ScalableMapWidget` 的通用 overlay 负责绘制多个 marker，
不理解 PoE2 身份或内存协议。双人 evidence builder 关闭人物/动态擦除，避免人物周围墙体被 mask。

### 实验跟随链路（2026-09-27）

`features/poe2/live_terrain/experimental/multiplayer_follow/` 提供角色/地图实例身份、
新鲜度门控、点击目标、独立 follower 状态和安全路径运行时。`capture_test_page.py` 在
双人视觉首帧成功后创建该运行时；地图点击经 `presenter.localization_source_point()` 逆变换
为 canonical 坐标，路线与目标再经同一 registration transform 绘制到通用地图 overlay。运行时
只使用 `TerrainReference.wall_layer`，对 A* 路线（含起点和终点连接段）和模拟步进做原始网格逐段碰撞校验。
当前实验运行时为每条路线配置可选的 `safety_margin`、clearance distance-transform 软代价，并缓存已验证路线，避免每个高频 tick 重复扫描整条折线。每个 follower 还维护目标距离/位置的 progress watchdog；连续无位移时先生成左右交替的侧向恢复 waypoint，恢复失败才进入 `BLOCKED` 和冷却重试。`FollowObservation.diagnostics` 记录安全参数、无进度 tick、恢复次数与恢复目标，供实机日志区分“路线可行但输入未产生位移”和“路线本身无路”。
墙体输入必须保持 0/255 二值语义：通用寻路器只把大于 50 的像素当墙，原图几何校验把任意非零当墙；曾压成 0/1 导致规划穿墙并在后校验被拒。本轮已在实验 runtime 入参处归一化并用门口样本回归，旧实例离线可得到 26 点无碰撞绕行路线；这不等于当前实例已实机穿门。
`program_output.py` 是显式授权的输出适配器；旧点击目标程序模式首次点击后取得 Host lease，实时角色跟随模式则在用户启动且新鲜视觉目标需要移动时取得 lease。默认模拟和首帧/定位链路不触碰设备或网络。

本轮修复后，测试页要求用户从实时定位身份中分别显式选择 P1/P2；字典遍历顺序不再决定手动控制归属。初始化和换图先停双人定位及跟随计时器，清除会话绑定。跟随 runtime 对不可达路线按角色缓存失败起点、目标和 1 秒重试时间：位置或目标显著变化可立即重试，静止时不逐帧重跑 A*。目标偏离旧路线终点超过到达半径即重规划；即便目标小幅移动仍在旧到达圈内，只要旧路线给出零向量而实际目标未到，也会即时尝试新终点路线；仍无法前进才进入 BLOCKED。双人画面刷新仅复绘上次跟随结果，模拟推进只由跟随计时器执行。以上均局限实验层，正式设备输出仍未接入。
旧点击目标模式启动只创建角色与地图绑定，状态为“等待点击地图”，不启动模拟计时器；第一次有效地图点击经逆变换设置 canonical 目标后才启动计时器并立即计算，后续每次点击直接覆盖共享目标并重算。跟随 overlay 的实心人物标记始终来自 `DualMotionState.players` 的实时视觉定位；程序角色每 tick 将该视觉位置回写 runtime，模拟位置只以虚线候选圈展示，路线和目标独立绘制，不再用预测位置覆盖真实人物。停止跟随后立即恢复双人实时定位 overlay 并清除目标/路线。

### 2026-10-03 实时角色跟随实验链路

1. 用户完成同实例双人首帧/实时定位后，在 `Poe2CaptureTestPage.start_follow_experiment()` 选择 `p1_leads` 或 `p2_leads`；页面校验两名不同身份、`tracking` 状态和不超过 300ms 的启动截图，先用 `stop_program_move_probe()` 释放原定点探针输出和待点击状态，再创建 `SimulatedFollowRuntime(arrival_radius=12, resume_radius=20, footprint_radius=<UI 默认 3>, inflate_collision=False)`。实时角色模式随后进入一次性的 `cold_start`（重定位恢复为 `recovery_sync`）：以 accepted frame 的 `captured_at_ms` 建立 tracker baseline，同帧只计算状态、不申请/写入程序手柄；仅当完整双人帧的捕获时间严格大于 baseline 时才 `sync_ready`、重置 750ms 视觉相位并进入输出。反向启动 `start_program_move_probe()` 也在校验后调用 `stop_follow_experiment()`，释放原跟随输出，避免两个控制 timer/手柄 lease 并存。人物半径只影响已有贴墙 clearance/恢复判定，不膨胀硬碰撞墙图；旧点击/双人同目标运行器仍用原参数。
2. `_tick_follow_experiment_impl()` 从 `DualMotionState.players[leader]` 构建实际身份、实例、`captured_at_ms`、native 点组成的 `PositionSample`，经 `set_target_sample()` 只接受严格更新的截图时间；静止角色的新帧可续期，同一旧帧不能由控制 tick 伪造新时间。跟随者的视觉位置用同一帧时间更新。
3. `SimulatedFollowRuntime._tick_follower()` 先做 follower/target TTL 与实例校验；距离不超过 12 时清路线并 `ARRIVED`，保持态中直到距离达到 20 才重新规划。目标位移技能造成的坐标跳变直接作为新终点，不追历史轨迹；旧路线目标偏离阈值后复用既有多尺度安全规划和局部控制。`command_prediction` 接近目标时不能单独确认到达，而是生成最长 80ms 的 constrained approach pulse，等待视觉样本确认；实时角色 tracker 的预测速度来自视觉 EWMA，runtime 的 80 仅是冷启动先验。
4. 页面只遍历 `program_roles` 调用 `ProgramFollowOutput.arm/apply()`，手动角色只参与观测；`ARRIVED`、过期、定位失稳、markerless warmup、地图变换/实例失效或异常均释放程序手柄。所有程序跟随 tick 先经过 `_gate_live_follow_foreground()`：PoE2 不在前台时仅等待并一次性释放，恢复前台后以最新完整帧重置基线。`_update_follow_local_contact()` 用同帧小地图证据修正跟随角色；运行器请求重定位时先保存方向/角色/半径/地图实例、释放输出，再复用一次新内存锚点和双人首帧恢复。停止双人定位会清空旧采集时间，复用首帧不能冒充本轮实时帧；仅同实例新鲜 `tracking` 帧能重建角色目标，旧点击模式仍回放原点击目标。
5. `_render_follow_overlay()` 把动态目标和规划路线从 native 变到显示坐标；live mode 忽略地图点击，不允许静态 marker 覆盖动态目标。日志记录角色、目标坐标与真实帧年龄、距离、状态、路线和输出诊断；手动/程序角色选项在活动会话中锁定，停止后解锁。

`start_follow_experiment(_sync_phase="cold_start")` 的 live 分支状态步骤：

1. 停止旧 follow timer/runtime/output，并校验双人 tracker、同实例、角色有效、`tracking` 和 `0 <= now_ms - captured_at_ms <= 300`。
2. 为所选角色建立 `PositionSample`、`CommandRoleTracker` 和程序输出，但调用 `_enter_live_follow_sync(phase, now_ms, captured_at_ms)` 记录 baseline；同一 accepted frame 只运行一次观察计算，不调用 `ProgramFollowOutput.start/write`。
3. `_sync_live_follow_from_fresh_frame()` 仅接受 `captured_at_ms > baseline_captured_at_ms` 的完整双人帧；它重新 seed 角色 tracker、启动 750ms visual phase、把 `_follow_sync_phase` 切到 `tracking`，之后才允许正常输出。
4. 重定位恢复通过 `_sync_phase="recovery_sync"` 走同一门控；若新帧仍旧或不完整，保持中性等待而不是累计视觉拒绝或再次重定位。`stop_follow_experiment()` 清理同步字段、预测提示、timer 与 output lease。

副作用：仅在游戏前台、`tracking` 和冷启动/恢复同步门均通过后，才通过注入的 `ProgramGamepadOutput` 产生设备输出；工作台前台时只更新页面状态与日志并释放已有 lease。失败行为：启动帧过期或身份/地图无效时不创建 runtime；前台失败不触发重定位；输出异常由既有停止路径释放 lease。测试 `_complete_live_follow_cold_start()` 通过推进捕获时间显式覆盖新帧边界。

实验页右侧由 `QTabWidget` 分为采集定位、移动跟随和日志，各页独立滚动；左侧截图/大地图及侧栏仍由 splitter 调整大小。标签页外固定的“停止全部程序移动”调用 `stop_all_program_motion()`，无条件走定点移动、实时跟随和双人同目标的停止路径，同时清空三条链的待恢复上下文，不停止双人视觉定位。实时跟随人物半径只在 `p1_leads/p2_leads` 模式可编辑；其它旧实验模式不使用该参数，控件置灰。UI 分组不改变任何 native 坐标或跟随判定。

### 地图点击目标取证（2026-10-01）

`Poe2CaptureTestPage._on_follow_map_click()` 将 `ScalableMapWidget.pixel_clicked` 的原图 pixmap 坐标记录为
`source`，用当前 `SimilarityTransform2D` 逆变换得到 native 目标，边界通过后正向回投为 display 坐标并计算
round-trip error。页面保存三份独立状态，双人/跟随 overlay 使用 display 目标；未启动跟随时只显示目标并等待，
不申请程序手柄。`ScalableMapWidget.set_target()` 是不覆盖其他 marker 的通用窄接口，停止跟随或清空地图时清除。
日志事件 `map_click.received/transformed/accepted/rejected/cleared` 记录模式、角度、镜像、比例、平移、地图尺寸、
边界和坐标链路，便于区分点击映射错误、方向错误和导航 runtime 问题。

### 2026-10-01 移动输入坐标边界修订

跟随 runtime 的路线、墙体、目标和人物均位于 `reference/native` 坐标。首帧 registration
只参与 source/display 与 native 的转换；`native_route_vector_for_program_output()` 在
程序输出边界原样传递该路线向量，`ProgramGamepadOutput` 单独应用
`POE2_MAP_TO_STICK_BASIS`。不要在页面或路线探针中再调用
`native_map_vector_to_local()`，否则会重复旋转/镜像并造成卡墙。该旧函数仍是通用
几何逆变换，不属于 PoE2 程序输入链。

跟随/程序移动 overlay 会把 native 起点、A* 中间点和 native 目标一起映射到 display，
日志同时记录 `route_length`、`route_detour_ratio`、`vector_native`、`vector_input` 以及
Host 的 input/basis/axis magnitude，用于分离路线错误与手柄幅度校准问题。

移动实验还记录 plan context、A* 尝试倍率/接受倍率、原始墙图尺寸与墙体像素、路线链段
碰撞数、视觉帧年龄、Host 释放前最终状态，以及 native 初始/最终位置和位移。程序探针
逐 tick 写入运动证据，跟随实验按固定采样间隔写入，避免依赖单一 UI 状态判断失败原因。

### 2026-10-02 局部控制与双人候选边界

`core/routing/local_controller.py` 提供 `LocalMotionController` 与
`LocalMotionDecision`。它是地图空间的通用短视窗控制能力，不知道 PoE2、Xbox 或角色业务：以全局
路线向量为基准生成有限角度候选，使用 `line_is_walkable()`、距离变换、目标进度、路线偏离和
前一命令变化量评分，并根据视觉估计速度降低摇杆幅度。`SimulatedFollowRuntime` 在输出前调用它，
并在 `FollowObservation.diagnostics` 暴露 observed velocity、speed ratio、预测清距、候选拒绝数等。
全局 A* 仍负责拓扑路线，局部控制只处理手柄速度误差和短时绕障；两者边界不互相依赖。

`SimulatedFollowRuntime._plan_safe_route()` 在原始膨胀碰撞图上先做安全路径简化，再逐段做原生网格
校验；页面的 PoE2 实验参数显式使用 8 tick 无进度恢复、24 native px lookahead、0.25 s 预测窗。
`SimulatedFollowRuntime._wall_start_recovery_command()` 在首次规划失败或普通局部控制发现观测格为墙时，复用
同一局部安全路线发出 120ms 上限的 0.25–0.45 归一化脱困脉冲；若下一帧仍在同一栅格则复用该路线继续脉冲，进入可行走格后才交给 `LocalMotionController`，目标超出刷新带或人物离开边界时才重新搜索。

`marker_candidates._same_marker_component()` 将不同 `profile_index`/identity hint 视为不同人物，避免
双人靠近时被轮廓 NMS 合并。`DualFirstFrameRegistrar` 接受至少两个候选，过滤低置信候选后枚举所有
有序两人组合；页面和产品 session 提供最多 6 个候选，仍由共享变换、内存 anchor 和 assignment margin
决定最终身份。该扩展只增加候选容错，不改变单人中心定位契约。

`SimulatedFollowRuntime._plan_safe_route()` 先按 `minimum_clearance` 选择严格路线；当调用方显式提供
角色 `footprint_radius` 且严格候选为空时，再验证膨胀碰撞图和硬清距下限，必要时选择
`relaxed_clearance` 路线。`FollowObservation.diagnostics` 暴露 `plan_relaxed_candidate_route_count`、
`plan_selected_clearance_mode` 和逐倍率 `relaxed_reason`，PoE2 页面把这些字段写入 `program_probe.motion`
与 `follow_experiment.motion`。闭环控制器生成的 `command_duration_ms` 不受 Qt tick 间隔覆盖。

`SquareScreenCapture.close()` 对未完整初始化、重复关闭和 mss 跨线程 thread-local 释放均保持幂等；
析构阶段不把底层资源清理异常传播到 Qt 主循环。

`Poe2DualMotionWorker.wait()` 为 latest-only 截图线程提供有界 join；`Poe2CaptureTestPage.stop_dual_motion()`
先请求停止再等待，避免页面 QObject 释放后后台线程继续发出结果信号。

## 2026-10-05 跟随启动 6 秒切窗缓冲

`Poe2CaptureTestPage.start_follow_experiment()` 在含程序控制角色的会话建立时设置
`_follow_output_not_before_ms`；`_tick_follow_experiment_impl()` 在前台门通过后检查该时间门。门未到期时只更新状态和日志，绝不调用
`ProgramFollowOutput.arm/apply`，所以不会触发 `ProgramGamepadOutput.start/write` 或 Host lease。倒计时每秒记录
`step=follow_experiment.command_delay_waiting`，到期记录 `command_delay_elapsed`，随后沿原有 runtime→arm→write 链路继续。

`_on_follow_map_click()` 不再直接 arm；它只变换并保存目标、启动 timer，确保首个点击和后续目标替换都经过统一门控。延迟从“开始跟随”时刻计算，连续点击不会反复延长；停止、初始化和清图会清理门状态。测试 seam `_follow_command_arm_delay_ms` 仅用于离线回归置零。

回归覆盖：页面 `80 passed`；程序输出及双人跟随 runtime/tracker 相关 `72 passed`；compileall、git diff check 通过。生产默认延迟为 6000ms，实机仍需用户切回 PoE2 后验证游戏实际消费输入。

### 2026-10-05 手动领队视觉跳变边界

实机曾在 `command_delay_elapsed` 后将手动领队的真实跳变送入 `CommandRoleTracker.observe()`，记录 `visual_rejected` 后触发
`manual_target_unobserved` recovery，表现为跟随立即停止。`_tick_follow_experiment_impl()` 现对 `role == leader` 直接接受视觉点、刷新 tracker anchor 和 remote target；只有
`_follow_program_roles` 保留 innovation rejection/reanchor 语义。大位移记录 `manual_leader_visual_move`，停止记录包含 reason、同步阶段、观察摘要和门状态。

回归：手动领队大位移不触发重定位；页面 81 passed。该规则保持在 PoE2 组合层，通用 `CommandRoleTracker` 仍只表达角色级 command odometry。
## 2026-10-06 — Live-follow automatic recovery is non-terminal

`Poe2CaptureTestPage` keeps an active live-follow runtime, timer, session, role selection and command predictor across recoverable capture/worker/tick/output faults. `_resume_dual_motion_restart()` propagates `preserve_follow`; `_continue_live_follow_after_dual_failure()` releases current output, preserves the session and schedules a fresh visual worker. `_continue_follow_after_runtime_failure()` handles follow tick/output/context faults without calling `stop_follow_experiment()`. `follow_experiment.stopped` is now limited to explicit stop, experiment switching, map reset/instance invalidation and page shutdown. Automatic recovery is diagnosed with `recovery_deferred`/`recovery_transition` and resumes in place after a fresh tracking frame.

### 2026-10-06 同一失配 episode 的恢复去重

`Poe2CaptureTestPage` now owns a live-follow recovery episode edge in
`_follow_recovery_episode_active`, with the originating reason and a suppressed-call counter. The edge is
opened by `_request_live_follow_reanchor`, `_continue_live_follow_after_dual_failure`, or a dual-motion
recovery revision; while active, later follow ticks only keep the bounded prediction and emit a throttled
diagnostic. They do not call `_claim_dual_recovery`, release the program output again, or schedule another
retry (only when the existing retry owner is idle). `_sync_live_follow_from_fresh_frame` and an accepted/rebased visual observation close the episode;
`start_follow_experiment` and `stop_follow_experiment` clear it as session boundaries.

```text
visual innovation rejection / capture failure
  -> begin live-follow recovery episode (once)
  -> claim page recovery budget + release output + schedule worker
  -> repeated ticks: bounded prediction + throttled episode_suppressed log
  -> fresh complete frame -> sync_live_follow_from_fresh_frame
  -> clear episode -> normal follow ticks may request a new independent recovery
```

Risk boundary: if a recovery worker never produces a fresh complete frame, the episode remains active and
suppresses repeated global recovery requests by design; the existing one-second retry path remains the only
retry owner. Regression coverage includes 100 repeated requests in one episode, one claim/restart, and a
second claim after an explicit fresh-sync boundary.
## PoE2 实验模块化增量（verified）

### `features/poe2/live_terrain/experimental/adapters/ports.py`

职责：定义实验截图、内存、前台窗口和手柄的无 Qt/Win32 协议，以及组合用的 `AdapterBundle`。该文件没有设备副作用，具体实现由 UI/Host adapter 注入。

### `features/poe2/live_terrain/experimental/adapters/fakes.py`

职责：提供离线回放使用的 `StaticMemory`、`StaticWindow`、`RecordingGamepad`。内存读取只递增计数，窗口返回固定前台状态，手柄把命令记录到内存列表；不会访问真实进程或发送输入。

### `features/poe2/live_terrain/experimental/application/headless.py`

职责：提供 `HeadlessExperiment` 生命周期 runner。`start()` 建立 RUNNING 会话，`ingest()` 只接受 RUNNING/RECOVERING 状态并记录有序帧事件，`recover()` 转入 RECOVERING，`stop()` 转入 STOPPED；未启动时摄入帧抛出 `RuntimeError`。该 runner 不创建 QApplication、不读取设备。

### `features/poe2/live_terrain/experimental/replay.py`

职责：定义 `ReplayFrame`、`ReplayManifest` 和只读 `ReplaySource`。manifest 提供 replay_id、地图实例、场景、版本和标签；source 在构造时冻结帧序列，`at()` 进行确定性索引访问。

### `features/poe2/live_terrain/experimental/probes/controllers.py`

职责：用 `MoveProbe`、`DualTargetProbe`、`FollowProbe` 管理目标生命周期，不实现路径规划。`select()` 在未 arm 时抛出 `RuntimeError`；双人目标标记为 `shared_target`，跟随源更新标记为 `follow_source`，三者最终都交给共享运动 runtime。

### `features/poe2/live_terrain/experimental/follow/controller.py`

职责：提供 Qt-free `FollowController`，统一目标刷新和 shared runtime tick。`start()`/`stop()` 只改变生命周期，`tick(now_ms)` 在运行时调用 `refresh_simulated_target` 后返回 runtime observations；未启动返回空映射，不访问设备。

### 当前实验重构数据流（verified）

```
地图点击/角色目标
  → capture_test_page._on_follow_map_click(display_x, display_y)
  → localization_source_point(...) 得到 native target
  → composition.move_probe / dual_target_probe / follow_probe 更新目标状态
  → 页面既有 shared follow runtime 计算 route/vector
  → ProgramFollowOutput → 注入的 gamepad adapter
```

```
ReplayFrame → HeadlessExperiment.ingest(captured_at_ms, payload)
  → ExperimentRuntime phase transition
  → EventRecorder DiagnosticEvent sequence
```

### 当前风险登记（verified/partial）

- **P1 `capture_test_page.start_follow_experiment` / `_tick_follow_experiment_impl`**：页面仍直接编排 runtime、窗口前台校验和输出，尚未完全收口到 controller/adapter；触发条件是 UI 页面运行而不是 headless composition。建议 C1 继续把 tick 编排提取为无 Qt controller。
- **P1 `capture_test_page.start_dual_target_experiment`**：输出 factory 和窗口/地图状态仍由页面持有；adapter 契约已存在但尚未替换全部调用。建议 B2 后续把副作用调用改成显式 port。
- **P2 `HeadlessExperiment.ingest`**：当前只验证生命周期和诊断，不执行真实定位/路径算法；它用于确定性状态回放，不能作为实机成功证明。
## Current recovery-chain self-check

The newly added recovery package is currently a tested policy layer, not yet the sole live runtime implementation. `capture_test_page.py` bypasses the legacy retry controller for live retry scheduling, but `_request_live_follow_reanchor()` still has an old global fallback when no local matcher is available. The new coordinator, real local ROI matcher, and warm memory reader must be wired before live-follow acceptance; static/legacy experiments remain intentionally separate.

### Recovery backend boundary (current)

`recovery/global_reanchor.py::GlobalReanchorBackend.start(reason, preserve_follow)` is the sole live-page adapter for the final asynchronous global worker. It records a request and invokes the injected worker starter; static/legacy page paths intentionally remain separate. `memory_anchors.py::Poe2DualPlayerPositionSource.read_many()` caches PID, descriptor, and layout for the current process/slot, invalidating the layout cache when the area instance changes. `_request_live_follow_reanchor()` suppresses repeated requests inside one recovery episode before evaluating policy, so a stale frame cannot repeatedly claim backends or release the follow lease. The remaining boundary is explicit local matcher feedback: `DualVisualTracker` performs the bounded local match on its next frame, while `RecoveryCoordinator` currently receives the policy-level local action rather than a measured local score.
