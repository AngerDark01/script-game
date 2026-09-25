# PoE2 实时地形与人物定位断点

## 文档用途

这是 PoE2 实时地形任务的唯一阶段断点文档。每次暂停或切换阶段时，更新本文件中的状态、已完成内容、当前假设、未决问题和下一步入口，避免下一次开发重新推断上下文。

最后更新：2026-09-23

当前状态：**PoE2 单帧内存锚点 + 局部几何配准已在一份真实首帧上达到 0.818 置信度并接入页面工厂；等待第二份真实地图样本做稳定性验收**

## 当前阶段目标

本阶段只验证真实 PoE2 小地图中的单人人物定位和轨迹显示：

```text
打开 PoE2 并进入异界
  -> 初始化 PoE2 会话
  -> 手动获取当前异界地形
  -> 配置并监控游戏内小地图区域
  -> 识别当前人物在小地图中的真实局部位置
  -> 首帧在完整地形中进行全局匹配
  -> 后续使用帧间位移和局部范围匹配
  -> 在完整地图上显示人物真实位置和移动轨迹
```

本阶段的核心验收不是地图能否规划路线，而是人物 marker 是否随着真实人物移动，在完整地图上保持正确位置和方向。

## 明确排除的内容

以下内容属于后续跟随阶段，本阶段不实现：

- 目标点选择；
- A* 或其他导航路线计算；
- 路线显示；
- 自动跟随；
- Xbox、键盘、鼠标或其他真实输入；
- 局域网同步；
- 多人角色区分；
- 动态障碍处理。

帧间位移、局部匹配和轨迹更新可以使用，因为它们是“定位人物移动”的算法，不是“控制人物移动”的算法。

## 关键设计修正

### 单人中心模式与多人/区域模式分离

PoE2 的监控配置 `selection_mode` 决定人物局部坐标来源：

- `center`：不执行 HSV、轮廓或颜色识别，直接使用配置绑定中的
  `player_marker_position`；旧配置没有 marker 时才使用当前截图几何中心。这个模式用于单人
  且人物中心已由用户配置的场景。
- `region`：执行 HSV/形状候选识别，保留 0..N 个候选；多人场景需要在业务层进一步选择当前
  角色，当前单人策略仍要求唯一高置信候选，否则 fail closed。

两种模式只共享后续的地图全局匹配、局部跟踪和轨迹状态机；识别来源不混用。

### 不再在区域/多人模式使用小地图中心作为人物位置

旧导航逻辑可以在某些场景下把小地图中心当成玩家局部坐标。PoE2 不能采用这个假设：

- 人物在小地图中不一定位于中心；
- 多开或多人场景下，小地图可能同时出现多个角色；
- 中心位置只能是截图几何信息，不能代表被跟踪人物。

区域/多人模式必须真正识别人物图标。单人中心模式是明确例外：中心点是用户配置契约，不能再额外要求图像识别。

### 单人先做，多人预留契约

当前业务策略只选择一个人物，但引擎结果不能设计成永远只有一个坐标：

```text
引擎输出：0..N 个实体候选及其观测证据
PoE2 单人业务：选中唯一可信候选
PoE2 多人业务：以后增加当前控制角色选择策略
```

多人识别策略暂不实现，但候选列表、置信度、观测时间和 tracking id 等字段应在通用契约中预留。

## 分层规则

### PoE2 业务层

`src/auto_modules/features/poe2/live_terrain/` 负责正式业务组合和 PoE2 规则：

- native terrain 快照如何转换成 PoE2 定位参考图；
- PoE2 小地图的监控配置；
- PoE2 人物图标的颜色、形状或模板策略；
- 单人业务如何选择当前人物候选；
- 初始化、抓取、开始监控、停止监控的实验流程；
- PoE2 页面如何显示实时小地图、人物 marker、轨迹和诊断信息；
- 实机日志和样本归档。

`tools/experiments/poe2_live_terrain/` 只保留兼容导出，生产代码和正式测试均以
`features/poe2/live_terrain/` 为入口。PoE2 业务只能组合引擎能力，不能复制定位或截图引擎。

### 引擎层

引擎负责不带 PoE2 术语的稳定能力：

- 监控区域和截图帧来源；
- 地图参考数据契约；
- 全局地图匹配；
- 预测位置后的局部匹配；
- 定位状态和恢复状态；
- 多候选实体观测；
- 轨迹缓冲；
- 坐标转换；
- `FrameRegistration`、`LocalizationResult` 等结果契约。

如果实验中发现引擎缺少能力，先判断它是否脱离 PoE2 术语后仍然有稳定语义。只有满足可复用契约的能力才下沉到 `src/auto_modules/core/`；PoE2 的规则和策略留在实验业务层。

## 已完成内容

### 2026-09-19 本阶段开发批次 1-2

已完成计划 Task 1-3，代码只进入通用引擎层，尚未接入 PoE2 或 UI：

- `core/localization/observations.py`：新增 `ObservationCandidate` 和 `ObservationFrame`，支持 0..N 个候选实体和显式选中候选；
- `core/localization/map_localizer.py`：新增 `NEED_GLOBAL -> LOCAL_TRACKING -> RECOVERY_REQUIRED -> STOPPED` 状态机，首帧全局匹配，后续局部匹配失败后下一帧才全局恢复；
- `core/localization/trajectory.py`：新增 `TrajectoryBuffer`，只记录 fresh/confirmed 位置，不把 stale 坐标追加到轨迹；
- `core/localization/__init__.py`：导出上述通用契约；
- 计划测试矛盾已修正：局部匹配失败测试现在提供相位预测，并明确验证调用顺序为 `global -> local -> global`。

本批次验证结果：

```text
13 passed
compileall passed
Serena diagnostics: no diagnostics
```

本批次没有修改 `NavigationCore`、导航页、输入或网络代码。

批次 2 已完成 PoE2 实验组合和独立监控边界：

- `terrain_reference.py`：从 `TerrainSnapshot` 原生数组构建不可变的定位参考层；未知区域不会被当作可行走区域，展示 pixmap 不参与定位；
- `calibration.py`：显式保存小地图尺寸、比例、轴向、Y 翻转、偏移和人物局部 marker；
- `player_policy.py`：单人业务只接受唯一的高置信度候选，多候选高置信度时 fail closed；
- `runtime.py`：按 `selection_mode` 选择配置中心或 HSV 人物候选，再组合首帧全局 matcher、后续局部 matcher、恢复状态和确认轨迹；中心模式不调用图像识别，区域/多人模式没有候选时不调用定位、不使用几何中心；
- `core/spatial/monitor_binding.py`：通用屏幕矩形契约；
- `features/poe2/live_terrain/monitor_config.py`、`profile_store.py`、`monitor_source.py`：PoE2 独立配置、多个本地 profile 和区域截图适配，不读取 `NavConfig`；
- `ui/modes/poe2_live_terrain/capture/selection_controller.py`、`config_panel.py`、`monitor_dialog.py`、`profile_toolbar.py`：参考绘图模式实现的 PoE2 独立画框/中心点/截图大小/正方形或圆形配置，监控运行期间锁定；
- `page.py` / `presenter.py`：按绘图模式风格左右分栏，展示实时监控小地图、当前在线获取地图、人物 marker、定位状态和确认轨迹；
- `main_window.py`：在组合根注入 PoE2 runtime 和独立配置存储，保持现有页面索引与手柄/LAN 生命周期。

批次 2 验证结果：

```text
50 passed
compileall passed
Serena diagnostics: 新增 Python 业务/引擎文件无诊断；PySide6、numpy、cv2 的缺失提示来自 Serena 当前语言服务器环境，运行时测试已通过。
```

完整回归补充：`448 passed, 2 skipped, 4 failed, 10 subtests passed`。失败项均为
本工作区既有问题，与本阶段 PoE2 代码无调用关系：

- `tests/test_distribution.py::test_dependency_selection_excludes_unrelated_editable_project`
  因当前 Python 环境缺少 `pydirectinput` distribution metadata；
- `tests/test_pathfinder.py` 的三个角点穿越、未探索区和细墙行为断言失败，涉及既有
  `PathFinder` 实现，本阶段没有修改 `core.routing` 或路径规划代码。

### 实时地形采集和展示

- 外部采集器位于 `D:\ACloud\poe2-map-research\experiments\live-terrain-preview\live_preview.py`。
- 正式业务适配器、配置和 runtime 位于 `src/auto_modules/features/poe2/live_terrain/`。
- 当前流程是 `initialize -> capture -> manifest/NPZ 校验 -> TerrainSnapshot -> 内存保存 -> 地图展示`。
- 当前地图快照保存在内存；测试阶段可以由 `TerrainDebugArchive` 显式归档。
- `data/maps` 不作为 PoE2 实时地图写入目标。
- `tools/experiments/poe2_live_terrain/` 不承载正式实现；绘图模式仍保持原实现，不接入 PoE2 profile 或圆形遮罩。

### 当前 UI

- 主窗口已有“PoE2 地形”页面。
- 页面支持初始化、手动获取地图、清空地图、独立监控配置、开始/停止监控和地图展示。
- 监控循环并列显示预处理小地图和定位器实际使用的 match mask，同时显示候选定位来源、置信度、局部/全局坐标、帧耗时、完整地图人物 marker 和确认轨迹。
- 监控循环同时显示候选数、通过门槛数、最大轮廓面积、最大置信度、mask 像素数和失败原因；日志会记录 HSV 范围与轮廓面积，能够区分无颜色命中、面积过滤、置信度不足和多人歧义。
- 运行时使用真实截图前仍需在“监控配置”中绑定小地图矩形，并通过实机确认比例、轴向和人物识别阈值。
- 主窗口仍保留开发工作台页面，以及正式的手柄和局域网页面。

### 当前验证

- PoE2 地形采集、监控配置、定位运行时和 UI 的 focused tests 已通过。
- 现有地形样本尺寸为 `2416 x 2277`。
- 圆形模式采用矩形截图加圆形有效区域遮罩，底层数组和坐标契约保持不变。
- PoE2 runtime 的区域/多人识别默认门槛为 `0.60`；这是针对实机小地图人物轮廓通常只有约 10 像素面积的业务校准，不修改公共 `HSVRecognizer` 默认参数，也不放宽多人歧义策略。中心模式不经过该门槛。
- PoE2 composition 会复制 HSV 参数到独立 recognizer，避免绘图模式运行期间修改共享可变识别器而影响 PoE2 定位。
- 每个 PoE2 profile 独立保存完整 `HSVRecognizer` 参数；颜色校准和高级视觉参数复用绘图模式成熟对话框，但不修改绘图模式配置或 recognizer 实例。
- `MonitorFrameSource` 已将 profile 的 `shape/circle_radius` 接入识别前采集链路；圆外像素置零，正方形仍保持原始帧。
- 本地 profile 位于 `data/poe2_live_terrain/monitor_profiles/`，只保存监控和识别参数，不保存地图快照或运行状态。
- 地图显示规则已经确认：可行走区域深灰、可行走边界白色、未知/区域外黑色。
- 该显示规则只用于展示，不能直接当作定位或寻路契约。

## 可复用的引擎能力

优先复用并通过接口组合：

- `SquareScreenCapture`：桌面区域截图后端；
- `HSVRecognizer`：可注入的小地图和人物识别能力；
- `PlayerTracker`：基础人物候选检测和轨迹存储，需要补充“本帧是否新识别”的结果区分；
- `MapRuntime`：从二值地图构建距离场和局部地图视图；
- `LocalMapMatcher`：有边界的局部地图匹配；
- `phase_tracker`：帧间位移预测；
- `FrameRegistration`：每帧配准来源、置信度和坐标；
- `LocalizationResult`：定位结果的 typed outcome；
- `CoordinateMapper`：显式坐标空间转换；
- `ScalableMapWidget.pixel_clicked`：以后可用于地图交互，但本阶段不需要路线目标。

现有 `NavigationCore` 不作为 PoE2 入口直接复用，因为它包含旧地图包、导航配置、旧缩放和导航页生命周期假设。应复用其中已经抽出的通用模块，必要时新增更窄的引擎接口。

## 本阶段计划新增的引擎能力

候选名称和职责如下，最终命名以实现前的接口设计为准：

- `EntityObservation`：承载 0..N 个候选实体、置信度、局部坐标、时间戳和证据；
- `MapLocalizer`：提供 `NEED_GLOBAL -> LOCAL_TRACKING -> RECOVERY_REQUIRED` 的通用状态机；
- `TrajectoryBuffer`：保存确认后的全局位置轨迹，不把 stale 位置伪装成新检测；
- 通用 minimap frame/coordinate contract：明确截图坐标、地图坐标、比例和方向；
- 通用局部匹配恢复契约：局部失败必须显式进入恢复状态，不在同一帧静默全图 fallback。

这些模块不能导入 PoE2、导航页或游戏对象名称。

## PoE2 正式业务域

当前正式入口：

- `features/poe2/live_terrain/terrain_reference.py`：把 `TerrainSnapshot` 转成定位用参考数据，不从 `QPixmap` 反推；
- `features/poe2/live_terrain/calibration.py`：保存小地图像素到地图参考像素的比例、方向和偏移；
- `features/poe2/live_terrain/player_policy.py`：单人场景选择唯一可信人物候选；
- `features/poe2/live_terrain/runtime.py`：组合截图、识别、全局/局部定位、轨迹和日志；
- `src/auto_modules/ui/modes/poe2_live_terrain/page.py`：增加实时小地图预览、开始/停止监控、定位状态和人物显示；
- PoE2 页面关闭时停止截图循环并释放帧缓存。

PoE2 UI 通过 feature composition 注入 service、runtime 和 local profile store；PoE2 侧独立复刻绘图模式的监控配置交互，不修改绘图模式，也不在通用 navigation UI 中写 PoE2 定位算法。

## 坐标和校准风险

必须在真实小地图样本上确认：

- 小地图截图实际尺寸；
- 人物图标的颜色/形状/像素范围；
- native terrain 与小地图墙体之间的比例；
- X/Y 方向是否一致；
- 是否存在 Y 轴翻转；
- 地图边缘和区域外背景如何进入匹配参考图；
- 识别失败时如何区分“没有人物”和“沿用上一次确认位置”。

不能默认使用旧导航的 `draw_scale=2.0`，也不能把小地图中心当作人物坐标。

## 单人实机验收步骤

1. 启动当前主窗口并进入 PoE2 页面。
2. 打开 PoE2 自己的监控配置窗口，选择小地图区域并确认截图预览。
3. 打开 PoE2，进入异界地图。
4. 执行初始化和手动地形获取。
5. 启动实时监控。
6. 确认实时小地图画面和日志中的截图尺寸正确。
7. 单人中心模式确认识别诊断为 `center_configured` 且不调用 HSV；区域/多人模式确认候选数、人物 marker 和识别来源正确，再确认首帧全局匹配。
8. 在游戏中移动人物，确认 marker 和轨迹随人物移动，方向和相对距离一致。
9. 暂时遮挡或离开可识别区域，确认 UI 显示定位失败/恢复状态，不伪造中心坐标。
10. 停止监控并确认截图循环退出、配置窗口恢复可编辑。

真实 PoE2、桌面截图和人物移动只在明确的手动验收阶段执行；默认单元测试使用合成帧和 fake capture，不发送真实输入。

## 实机验收入口

代码入口已经完成。下一次直接按“单人实机验收步骤”执行，优先记录识别诊断中的 HSV 范围、mask 像素、候选位置/面积/置信度；只有确认人物候选唯一且稳定后，再记录地图/小地图比例、首帧全局置信度、局部跟踪耗时和失败恢复行为。实机验收不发送 Xbox、键盘、鼠标或网络输入。

本文件在以下事件后必须更新：引擎契约确认、实验目录职责变化、真实样本校准完成、首帧定位验证、轨迹验证、定位失败规则变化或阶段范围变化。

## 2026-09-22 一次性读取人物位置接入

本阶段已按方案 A 完成页面链路：

```text
数据采集测试 -> 初始化 -> 获取当前地图
  -> 校验地图实例 ID
  -> 只读读取本地玩家 Render 世界坐标
  -> world * 23 / 250 转为 native terrain grid
  -> 在当前地图 pixmap 上叠加绿色人物点
```

新增和接入内容：

- `features/poe2/live_terrain/player_position.py` 提供独立的只读人物位置契约和 PoE2 内存适配器；组件地址通过运行时组件表解析，不硬编码 `Render` 地址。
- `Poe2CaptureTestPage` 在地图成功获取后只读取一次人物位置；读取失败不会清除地图，页面会保留地图、显示“人物定位错误（地图仍已获取）”并记录 `player_position_start/success/failed` 日志。
- `present_snapshot` 支持可选人物位置，在地图展示上绘制绿色 marker，并显示网格坐标；人物样本不写入 `TerrainSnapshot` 数组。
- composition、PoE 页面和主窗口已完成依赖注入；未提供位置源的旧测试/简化 composition 仍可运行。

验证结果：

```text
位置契约、presenter、采集页、PoE composition、主窗口回归：15 passed
compileall：passed
```

已验证的实机只读数据仍为 `MapFlotsam:BB9AA6DE`、地形 `3382 x 1863`、世界坐标
`(4190.2173, 4635.8696, -594.7950)`、native grid `(385.50, 426.50)`。下一次实机验证只需打开 PoE2 页面，在“数据采集测试”中执行初始化和获取当前地图，确认绿色人物点与页面坐标；本阶段仍不启动持续跟踪、方向匹配、路线规划或任何 Xbox/键盘/鼠标/LAN 输入。

## 2026-09-21 数据采集测试页

已按方案 A 在 PoE2 页面内部增加独立的“数据采集测试”页签，用于反复验证真实小地图截图与在线地形获取链路。该页不修改绘图模式，也不复用实时定位页的可变运行状态。

入口：

```text
主窗口 -> PoE2 地形 -> 数据采集测试
```

当前支持的手动流程：

1. 打开独立的监控配置，选择小地图矩形或中心点，并配置正方形/圆形有效区域。
2. 手动刷新截图，或启动/停止截图预览定时器。
3. 查看原始截图、预处理画面和匹配特征，确认采集区域与视觉参数。
4. 初始化当前 PoE2 会话。
5. 获取当前异界地图到内存，并查看地图尺寸、区域、实例 ID 和保存路径。
6. 测试阶段可显式保存当前地图到 `data/poe2_live_terrain_test/latest.npz` 与 `latest.json`。
7. 清空测试状态；失败时同时清除旧截图、旧预览和旧地图，避免把过期结果当成当前结果。

该页拥有独立的 `Poe2TerrainService`、`Poe2CaptureAdapter`、`MemoryTerrainStore` 和预览定时器。它不会调用实时定位 runtime，不执行 `MapLocalizer`，也不会发送键盘、鼠标、Xbox、Host 或 LAN 输入。测试页的获取、保存和清空不会影响“实时地形定位”页。

本批次验证结果：

```text
PoE2 focused suite: 76 passed
页面/composition/MainWindow 回归: 11 passed
compileall: passed
git diff --check: passed
```

历史采集阶段曾未实现、也未在本页假装实现的能力：45° 方向候选搜索、自动角度校准、首帧全局定位、后续局部重定位和人物轨迹。该段已被后续多帧实验闭环取代；当前实现位于 `experimental/multiframe_localization`，但仍保持测试台隔离，尚未切正式 runtime，也没有路线执行。

### 2026-09-21 实机样本检查

本次获得了新样本 `MapFlotsam:C121287D`，归档尺寸为 `3382 x 1863`。manifest、NPZ 时间戳和实例标识一致，主体地形轮廓连续，五个数组层形状与类型均通过当前契约校验；该结果不是旧缓存。

但本次样本不能标记为完全正确，发现两个独立问题：

- “刷新截图”当前只把原图、预处理图和匹配特征显示在页面 `QLabel` 中，没有保存对应数组或图像文件；“保存当前地图”只归档 `TerrainSnapshot`。PoE 关闭后无法回看用户点击截图时的证据帧，因此不能根据关闭游戏后的重新截图判断原配置是否正确。此前基于关闭游戏后复抓出的黑屏判断已撤回。
- `raw_cells` 最右一列共 1863 个单元全部固定为值 `5`，倒数第二列和最左列全部为 `0`；历史实机样本也有同样的固定尾列。结合 `packed_u4_low_first` 和 `row_stride_bytes=1691`，该列高度疑似每行最后一个字节的高半字节填充/尾标记被误解成有效单元。问题已经存在于上游 producer 的 `native_grid.npz`，不是 auto_modules 归档时产生。修正前不得让该尾列参与地图边界或定位匹配。

已逐数组对比上游 `output/latest.npz` 与 auto_modules 调试归档：`raw_cells`、`cell_state`、`known_mask`、`wall_layer`、`explored_map` 的形状、类型和字节哈希全部相同。归档只在 `metadata_json` 中补充了 `tool: manual-live-terrain-capture`，未修改地形数组。因此地图归档写盘不是固定尾列的来源。

此外 producer 元数据仍明确标记 `completeness: unverified`、`atomic_snapshot: false` 和 `production_auto_mode_ready: false`。因此目前可以确认“当前实例的主体地形已成功读取和转换”，不能确认“完整地图边界和生产采集契约已经最终验证”。

### 截图监控与对比样本窗口

“数据采集测试”页已增加“打开截图监控窗口”按钮。独立窗口打开后自动持续刷新，同步展示：

- 原始小地图截图；
- 预处理画面；
- matcher 实际使用的匹配特征；
- 当前测试 service 内存中的完整地形。

点击“保存当前对比样本”会把当前有效帧保存到：

```text
data/poe2_live_terrain_test/samples/<时间-区域-哈希>/
  raw.png
  processed.png
  feature.png
  terrain.png        # 当前有地形时
  sample.json
```

三类小地图图片严格来自同一次截图调用；保存按钮不会重新抓帧。`sample.json` 包含截图/保存时间、完整 profile 参数、截图 binding、方向、地形实例和每张 PNG 的尺寸、dtype、通道及 SHA-256。没有当前地形时允许保存三类小地图，但明确记录缺失；没有当前有效截图时拒绝保存。全部文件先写入隐藏临时目录，完成后原子发布，失败不保留可见半成品。

窗口支持打开样本目录、上一个/下一个历史样本，以及按原图、预处理、特征或地形图层并排比较当前样本和上一个样本。重复点击入口只激活同一窗口；关闭窗口或主应用 shutdown 时停止窗口定时器并释放未保存帧。

本功能不调用定位 runtime，不执行方向搜索、人物定位、路径规划或任何输入/网络副作用。下一次实机测试应在 PoE2 开启且小地图可见时保存至少两套对比样本，再根据落盘的原图/特征/地形判断颜色、比例和方向问题。

### 2026-09-21 对比样本 ACL 修复与首份视觉证据

首轮连续保存生成四份 `MapFlotsam:F6A61E51` 样本。最早一份可读且五个文件完整，后三份虽然发布成功，但普通工作区会话无法进入目录。根因不是 PNG 或 manifest 写入失败，而是旧实现使用 `tempfile.mkdtemp()`：Windows 为临时目录安装 owner-only DACL，`os.replace()` 重命名后仍保留该 ACL；当应用与分析会话身份不同时即出现 `Access is denied`。

归档现改为在 samples 根目录下用随机名称和普通 `Path.mkdir()` 创建隐藏临时目录，使其继承父目录 ACL；完整写入后的 `os.replace()` 原子发布和失败清理保持不变。Windows 回归测试通过 `icacls` 断言最终目录包含继承标志 `(I)`。旧的三份受限目录未接管、未改 ACL、未删除；必须关闭并重新启动旧应用进程，之后的新保存才会加载修复。

可读样本：

```text
data/poe2_live_terrain_test/samples/20260921-075556-840709-MapFlotsam-F6A61E51/
```

证据确认：raw、processed 和 feature 来自同一 `200 x 200` 帧；terrain 为同一地图实例 `MapFlotsam:F6A61E51` 的 `1864 x 2829` 预览；图片 SHA-256 与 manifest 一致。原图能看到当前房间黄色边界、人物蓝色光环、橙色标记和鼠标指针；feature 已提取主要边界，但人物光环、标记和指针也形成了非地形特征。profile 仍记录 `map_rotation=0` 且无镜像，这只是未校准配置，不是自动方向识别结果。下一阶段应在离线探针中对 feature 做动态标记清理，并联合搜索旋转、镜像和比例；在候选行为通过样本验证前，不接入实时定位循环。

### 2026-09-21 离线定位实验结果

已新增只读实验入口：

```powershell
& D:/ACloud/.venv/Scripts/python.exe D:/ACloud/auto_modules/tools/debug/poe2_live_terrain_localization_probe.py
```

探针会重放样本 manifest 中完整的 `HSVRecognizer` 参数。实样本重建后的 feature 非零支撑与保存的 `feature.png` 完全一致，说明保存链和重放链没有特征位置漂移；强度值因探针二值化而不同。当前 `1339` 个 feature 像素经过人物半径和连通分量清理后保留 `1113` 个，蓝色光环、橙色标记和鼠标指针被移除，触边地图轮廓保留。

生产 runtime 当前失败的根因已明确：`_global_match()` 只用当前人工方向和原始比例执行一次 `TM_CCOEFF_NORMED`，没有处理本样本实际存在的旋转/镜像和约 `0.35` 比例差。实验探针改用两阶段搜索：45° 旋转、水平镜像和多比例粗搜索，随后在原生分辨率做小角度、小比例和平移细化；评分融合双向 Chamfer 边缘覆盖及人物侧可行走面一致性。

`MapFlotsam:F6A61E51` 当前首选实验结果：

```text
feature -> terrain angle: 225° counter-clockwise
horizontal reflection: true
scale: 0.35
template top-left: (1269, 785)
candidate player: (1318.35, 834.10)
score: 0.738386
second score: 0.681727
margin: 0.056659
forward edge coverage: 0.829268
reverse edge coverage: 0.526405
walkable coverage: 0.809882
player on walkable: true
```

默认实验门槛是 `score >= 0.72`、`margin >= 0.05`、变换后有效边缘至少 `120`，因此该样本为 `accepted=true`。这只表示样本内首选具有足够显著性，不能等同于真实坐标已经验证；目前没有独立的游戏全局坐标作为 ground truth，正式 runtime 尚未修改。

参数敏感性检查：分量跨度阈值 `18/24/30` 都返回相同变换与约 1 像素内的位置；人物清理半径 `16/22` 完全一致。半径 `30` 会切掉有效墙线，分数降为 `0.599810`、margin 降为 `0.001638` 并被拒绝。因此当前实验建议保持 `player_clear_radius=22`、`min_component_span=24`，主要修复应是几何清理、可行走约束和多方向多尺度匹配，不需要继续盲调 HSV。

主要结果目录：

```text
data/poe2_live_terrain_test/probe_results/20260921-mapflotsam-f6a61e51-walkable/
  report.json
  cleaned_feature.png
  local_walkable.png
  candidate_01_overlay.png
  candidates_sheet.png
  candidate_map.png
```

下一验证门槛是同一地图人物移动后的多帧：首帧应反复落在同一变换和比例附近，后续人物坐标位移方向必须与游戏移动一致，局部搜索不能跳到其他相似房间；随后还要在不同地图复现。通过这些验证后，游戏无关的 Chamfer/多尺度候选能力可以下沉到 core，PoE2 动态特征清理、阈值和方向策略保留在 feature 层。

本轮探针算法和 PoE2 focused 回归为 `77 passed`，全项目为 `552 passed, 1 skipped, 3 failed, 10 subtests passed`；3 个失败仍为未修改的既有 PathFinder 行为测试。正式 PoE2 runtime、绘图模式和任何输入/网络适配器均未修改。

## 2026-09-20 方向校准与地图展示状态

本阶段已增加 PoE2 专属 `TerrainOrientation` 适配层。profile 现在可以保存：

- 原始方向、顺时针 90°、180°、逆时针 90°；
- 旋转后的水平翻转、垂直翻转。

同一个方向契约同时用于 native snapshot 的展示 pixmap、定位 reference、人物局部位移以及轨迹/人物 overlay，90°/270° 时会正确交换地图宽高。旧 profile 没有这些字段时保持 0°、不翻转。方向选项位于 PoE2 自己的监控配置窗口，不会修改绘图模式。

PoE2 页面初始地图适配视图使用 `1.35` 倍 fit multiplier；定位仍使用完整 native reference，当前没有做裁剪或改变坐标原点。通用 `ScalableMapWidget` 默认倍数仍为 `1.0`，因此其他页面行为不变。

### 尚未完成的实机确认

当前方向是人工 profile 选择，尚未根据真实 PoE2 小地图确定最终组合。实机测试时应先保持地图静止，分别比较小地图墙体与展示地图的主通道/房间朝向，记录正确的旋转和镜像组合；确认后保存到对应 profile。自动尝试多个方向暂不启用，以免对称地图产生错误高置信匹配。

## 2026-09-21 视觉校准与匹配链路对齐

本轮修正了此前“只复刻绘图模式外壳、未复刻实际视觉链路”的问题：

- PoE2 监控配置新增颜色校准和高级视觉参数入口；颜色校准使用当前对话框里尚未保存的选区立即抓图，支持墙体/人物 HSV 采样和墙体 mask 预览。
- `recognizer_params` 随每个 PoE2 profile 独立持久化，旧 profile 仍可读取；绘图模式代码和配置未修改。
- 定位 runtime 在中心/区域两种人物策略完成后，统一调用 `preprocess_image()` 与 `extract_combined(frame, player_pos)`，得到和绘图模式一致的 wall/edge 加权匹配层、动态高饱和区域排除和人物半径擦除。
- center 模式仍直接使用用户选定的中心点，不执行 HSV 人物识别；“不识别人形”和“需要生成墙体匹配特征”是两个独立步骤。
- 页面新增“预处理画面”和“匹配特征”双预览，后者就是全局/局部 matcher 实际消费的 mask，不再只展示 raw frame。

本轮 focused/UI/architecture 测试结果为 `68 passed`，源码编译和差异格式检查通过。真实游戏仍需完成三项校准：颜色特征是否完整、native terrain 与小地图的比例、最终旋转/镜像组合。自动方向识别尚未实现；只有这些实机证据稳定后，才进入自动方向候选比较。

## 2026-09-21 全量对齐审计结果

已按绘图模式完整调用链逐项审计，而不是只比较页面外观：

| 能力 | 对齐状态 | PoE2 当前实现 |
|---|---|---|
| 画框和中心点选择 | 已对齐 | 共用 overlay/center selector；位置按 DPI 转物理坐标，截图边长按物理像素，不重复缩放 |
| 正方形截图 | 已对齐 | 使用相同截图后端与物理矩形契约 |
| 圆形有效区域 | PoE2 扩展 | 保持矩形帧/坐标不变，只清零圆外像素 |
| 颜色校准 | 已对齐 | 复用同一 `ColorPickerDialog`、预处理图采样、墙体/人物 HSV 和 wall-mask 预览 |
| 视觉快捷参数 | 已对齐 | wall/fog、CLAHE、颜色深化、wall/edge 权重、Canny、人物擦除半径均在 PoE2 配置可调 |
| 高级视觉参数 | 已对齐 | 复用同一高级窗口；隐藏 PoE2 不适用的 stitcher 页 |
| 参数持久化 | 已对齐且独立 | 32 个 recognizer 字段完整随每个 PoE2 profile 保存，不读写绘图模式配置 |
| combined 特征 | 已对齐 | 同一 `extract_combined(frame, player_pos)`，保留灰度权重、动态色排除和人物擦除 |
| 实时预览 | 已对齐并增强 | 同时展示预处理画面和 matcher 实际消费的 match mask |
| 失败诊断 | 已增强 | 人物未识别时仍发布视觉层，但不调用 localizer；无新帧时清除陈旧预览 |
| profile 切换 | 已对齐业务需求 | binding、形状、方向、时间、阈值和视觉参数同时切换；空 profile 恢复 dedicated 默认值 |

正式地形与正式定位仍不依赖绘图业务的 stitcher、离线地图保存或点击导航点。数据采集测试窗口现已按新验证方案显式复用通用 `core.mapping.MapStitcher`：它把连续小地图帧拼成一块启动局部地图，供后续方向、比例和全局位置实验使用；该实验地图不替代 native terrain，也不写入正式定位 runtime。人物策略仍有意不同：单人 center 使用用户配置点，region/多人候选失败时 fail closed，不复制绘图模式的中心/last-known fallback。

## 2026-09-21 启动局部地图拼接采集

“数据采集测试 -> 打开截图监控窗口”现包含独立绘图实验区。用户点击“开始绘图”后，窗口仍然只截取一帧，并从同一帧生成 raw、processed、combined feature、wall mask、fog mask 和 raw gray；PoE2 拼图会话把这些 typed evidence 交给通用 `MapStitcher`，保持绘图模式的关键帧、F2F、跳变拒绝、质量门和加权合并路径。单人位置使用当前 profile 的 `player_marker_position`，缺失时才回退帧中心，不做人形识别。

实验区支持开始、暂停、重置和显式保存。运行时拼图、相对人物轨迹和统计只保存在内存；保存后写入：

```text
data/poe2_live_terrain_test/stitching_sessions/<timestamp-profile>/
  stitched_map.png
  stitched_map_overlay.png
  raw.png
  processed.png
  feature.png
  wall_mask.png
  fog_mask.png
  terrain.png
  session.json
```

`terrain.png` 在当前测试 service 已有同地图快照时保存；否则 `session.json` 显式记录 terrain missing，不会借用旧实例。`session.json` 包含 terrain instance ID、map origin、当前相对位置、完整轨迹、draw scale、截图尺寸、profile 配置和 stitcher 统计。目录先在 samples 同级根下用普通 `Path.mkdir()` 写入隐藏临时目录，再原子发布，保持 Windows ACL 继承。关闭窗口会停止截图并暂停拼图，但不会自动保存或清空已拼接结果。

当前阶段仅验证局部拼图是否稳定且无重影；尚未把拼图交给离线方向探针，也尚未实现启动局部图到 native terrain 的方向/镜像/比例/平移联合匹配。

实现验证：PoE2、mapping、UI 与架构 focused 回归 `104 passed`；全项目 `559 passed, 1 skipped, 3 failed, 10 subtests passed`，3 个失败仍是未修改的既有 PathFinder 行为测试。源码编译和差异格式检查通过；离屏窗口布局检查未发现控件重叠。下一步需要实机走图验证相对拼图质量。

本次对齐 focused 回归为 `76 passed`，参数集合机器校验无未归类字段。全项目回归为 `532 passed, 1 skipped, 3 failed, 10 subtests passed`；3 个失败均为未修改的既有 `PathFinder` 行为测试，与本功能没有调用关系。接下来剩余的不是代码链路对齐，而是实机数据校准：颜色样本、native terrain/小地图比例、旋转/镜像组合和匹配阈值。

## 2026-09-21 PoE2 绘图完整参数与诊断层对齐

本轮确认 PoE2 内部绘图效果与第一页仍有差异的根因不是某一种墙体颜色，而是运行契约不完整：PoE profile 只保存 recognizer 参数，实验 session 用硬编码 `3000 x 3000` stitcher；active profile 在页面首次构造时也未立即应用。旧样本的单参数消融进一步确认 `deepen_enabled=true/false` 会显著改变 combined match feature，即使最终 wall mask 仍高度重合。

现已完成：

- `Poe2MonitorConfig` 同时保存完整 `recognizer_params` 与完整 `stitcher_params`；旧 profile 缺拼接字段时自动补成与第一页同规格的 `5000 x 5000`、draw scale `2.0` 及通用融合默认值。
- `MapStitcher.default_params()` 可在不分配画布的情况下提供完整参数契约；`reset()` 不再丢失 wall-close、融合权重或质量门。
- `Poe2StitchingSession.configure()` 在开始绘图前应用当前 profile。相同参数保留现图；非运行状态的参数变化会显式重建并清图；运行中变化会拒绝，避免混用坐标尺度。
- PoE 高级视觉窗口保留“拼接算法”页，并把识别和拼接字段分别写回当前 PoE profile；不会读写第一页配置。
- 截图监控窗口新增“实际落图墙体”预览；手动样本同时保存可用的 `wall_mask.png`、`fog_mask.png` 和 `raw_gray.png`，历史图层可直接切换对比，旧三层样本继续兼容。
- 页面构造时立即应用 active profile，切换与保存复用同一应用入口。

当前用户已把游戏地图墙体改为蓝色。蓝色不写死在底层算法中，应在 PoE 当前 profile 里重新执行颜色校准；新 wall HSV、透明模式、颜色深化和蓝色通道增强都只属于该 profile。下一次实机验证先看“实际落图墙体”是否连续完整，再看“匹配特征”是否稳定，最后观察拼接地图是否重影。若 wall 层正确而 feature/拼图错误，继续查预处理或位移匹配，不再误判为颜色采样问题。

验证结果：相关 PoE2/mapping/UI/architecture 回归 `113 passed`；全项目 `567 passed, 1 skipped, 3 failed, 10 subtests passed`。3 个失败仍为既有 `PathFinder` 穿角、未探索区和细墙语义。源码编译、差异格式检查通过；1500×920 离屏界面检查未见控件重叠或裁切。本轮未连接游戏，也未发送 Xbox、键鼠、Host 或 LAN 输入。

## 2026-09-21 蓝墙实机拼图样本审计

本轮分析的最新会话为：

```text
data/poe2_live_terrain_test/stitching_sessions/20260921-121018-260622-a6ccb4c6767e/
```

20:10:16 至 20:10:18 共保存了 8 个目录。它们不是 8 次独立走图：`stitched_map.png` 与 `stitched_map_overlay.png` 的 SHA-256 在 8 个目录中完全一致，只是暂停后连续保存时 raw/processed/feature/wall_mask 仍取了不同的最新监控帧。因此后续实验只把最新目录视为一个拼图样本，不能把 8 个目录用于重复性统计。

蓝墙识别已经达到可用状态。最新 `200 x 200` 帧中：

```text
wall_mask nonzero: 1435 (3.59%), 4 个连通分量
feature nonzero: 2562 (6.41%), 5 个连通分量
feature 位于 wall_mask 一像素邻域内: 96.25%
fog_mask nonzero: 0（当前 profile 已关闭 fog）
```

`wall_mask` 连续覆盖当前画面中的蓝色墙线，人物中心的橙色标记未进入实际落图墙体；`feature` 比 wall 层稍宽，符合 combined edge 支撑预期。最新帧按 `draw_scale=2.0` 和保存的 current position 回投到拼图后，frame-to-stitch 覆盖为 `100%`，说明保存时坐标、人物中心和缩放契约一致。

拼图主体轮廓肉眼连续，没有大面积平行双墙；统计为 `217` 帧、`216` 次成功、`0` 次显式失败、平均质量 `0.737722`、`4` 次关键帧切换、`9` 次低质量跳过、`107` 个轨迹点。但不能据此宣称几何完全正确，当前发现：

- 轨迹中有两次异常大步长：`44.82 px` 和 `57.07 px`；其余步长中位数为 `13.47 px`、P95 为 `21.02 px`。保存格式目前没有逐轨迹点时间戳和对应帧编号，无法区分真实漏采与错误位移。
- 拼图在裁剪坐标约 `(298, 505)` 处存在一个约 `70 x 21` 的粗白块。该区域贡献 `1207` 个内部半径大于 5 像素的墙体像素；当前帧墙线 P95 内部半径为 `3.0`，整图则为 `6.397`。这不是正常墙线厚度，应在进入全局配准前作为瞬态特征或融合污染处理。
- `statistics.exploration` 与 `avg_displacement` 仍为 `0.0`，与已生成的大幅拼图和轨迹不符；这两个字段当前不能作为实机质量指标。

本会话 `terrain.status=missing`，原因是初始化成功后没有在同一测试 service 中执行“获取当前地图”。不过最新蓝墙 raw 与历史 `MapFlotsam:5C048CD0` 样本的房间外轮廓、右下环形结构和人物位置完全一致，可将历史 terrain 用作候选算法实验，不能替代正式的同会话实例契约。

把整幅拼图墙线直接输入现有离线 Chamfer 搜索后，首选仅为：

```text
score: 0.462466（低于 0.72 接受门槛）
angle: 94°
horizontal reflection: false
scale: 0.16
forward coverage: 0.586745
reverse coverage: 0.234677
```

该候选叠图不能形成可信几何对齐。按历史单帧候选换算的预期组合 `angle=4° / horizontal reflection=true / scale=0.175` 也只有 `0.436836`。因此当前结论是：颜色识别已经解决，拼图足以支持下一轮算法开发，但“整张累计拼图作为一个刚性模板”尚不能正确完成方向和全局定位。

下一阶段按以下顺序推进：

1. 为拼图保存逐关键帧位姿、质量、时间戳和 frame id，并显式标注 keyframe switch/跳变，保证异常可以追溯。
2. 在通用 mapping 层增加时间一致性和线宽/形态异常门，阻止粗白块等瞬态特征进入稳定墙图；PoE 颜色与动态标记策略仍留在 feature 层。
3. 方向、镜像和比例不再只对最终拼图做一次全量刚性匹配。使用多个相隔较远且质量合格的关键帧联合投票，先求共享方向/镜像/比例，再以局部块估计平移；对累计漂移使用鲁棒损失或分段子图，而不是要求全部墙线同时重合。
4. 候选变换确定后，用轨迹的连续位移方向做第二证据，拒绝虽然局部墙线相似但运动方向不一致的房间。
5. 下一次正式采集必须在开始绘图前依次执行“初始化”和“获取当前地图”，使 stitching session 自带 terrain instance ID 与 `terrain.png`；不要用连续点击保存制造伪重复样本。

本轮只读取和分析样本、运行离线匹配探针并更新断点文档，没有修改正式 runtime、绘图模式、控制器或网络链路，也没有发送任何游戏输入。

## 2026-09-21 形状配准实验方案确认

已确认下一阶段不继续扩展现有 `matchTemplate` 方向探针，也不要求用户人工设置地图方向。先在 `tools/debug` 实验台实现“局部拼图到完整地形”的二维相似变换恢复：两边墙体先骨架化为厚度无关的形状，使用 OpenCV `GeneralizedHoughGuil` 产生位置、旋转、比例和镜像候选，再用允许固定比例离群点的对称 trimmed Chamfer 验证。正确候选的旋转即地图方向，同一变换直接给出人物全局位置。

实验代码不得修改 `src/` 或正式定位 runtime。广义霍夫只负责产生候选，必须经过形状覆盖、候选分差和多块一致性验证；重复或对称区域必须返回 ambiguous，不能猜测。当前环境 OpenCV `4.13.0` 已提供 `createGeneralizedHoughGuil`、`estimateAffinePartial2D`、`distanceTransform` 和 `findTransformECC`，不需要先增加点云依赖。

已落盘文档：

```text
docs/plans/2026-09-21-poe2-partial-map-registration-design.md
docs/plans/2026-09-21-poe2-partial-map-registration-implementation-plan.md
```

当前状态是设计和 TDD 实施计划已完成，实验代码尚未开始；此前 `94° / score 0.462` 仍只是被拒绝的旧探针候选，不是已确认方向。

## 2026-09-22 首帧局部定位样本契约

定位实验已收敛为：用内存读取的人物初始 native-grid 坐标作为锚点，只从完整 terrain 裁剪锚点附近的小块，再让第一帧小地图与该局部块进行旋转、比例和平移匹配；不再先做整张地图搜索。

“保存当前对比样本”现在会在 `sample.json` 中同步保存 `player_position`：区域实例、采样时间、世界坐标和 native-grid 坐标。归档会校验人物位置与 terrain 的实例 ID 一致，避免用错误地图做离线局部实验。原始截图、预处理图、特征图、墙体层和 terrain 图的保存方式保持不变。

验证结果：样本归档、监控窗口、采集页、composition 和主窗口相关回归 `21 passed`；源码编译与差异格式检查通过。下一步只需采集一个包含 `terrain.status=available` 和 `player_position.status=available` 的首帧样本，然后在实验代码中验证锚点局部匹配。

### 首帧局部匹配实验结果

已使用样本 `20260922-043532-966126-MapFlotsam-1E44BF94` 完成第一次单帧实验。数据契约完整：terrain 与人物位置实例均为 `MapFlotsam:1E44BF94`，地图为 `2416 x 2277`，人物内存锚点为 `(300.4346, 400.9862)`，截图和视觉层为 `200 x 200`。

实验只裁剪锚点附近的局部 terrain，不搜索完整地图。第一轮半径 420 的搜索中，全局最高分候选离锚点 `274.52 px`，而第二候选离锚点 `44.75 px`，证明内存坐标必须参与候选约束。把局部半径收紧到 180 后，该候选成为第一名。进一步发现 `wall_mask` 顶部“记录点”文字被旧连通域清理规则保留；去掉顶部文字后，候选直接落到锚点附近。

围绕该候选细化后的结果：

```text
rotation: 219 degrees
horizontal reflection: true
scale: 0.85
predicted player grid: (307.4878, 401.8273)
memory anchor grid: (300.4346, 400.9862)
anchor error: 7.1032 terrain pixels
forward coverage: 0.783843
reverse coverage: 0.384615
score: 0.571715
```

叠图中左侧转角、上方长边界和下方凹口形成连续重合，证明“内存锚点 + 小范围旋转/比例/平移匹配”可行。当前仍标记为实验候选而非正式 accepted：单帧包含传送点圆环和局部可见性差异，旧 `0.72` 全局接受阈值也没有建模锚点先验。后续应把锚点距离纳入候选评分，并为文字、传送点等非稳定粗块增加结构清理，再用第二帧验证方向和比例是否保持稳定。

输出位于：

```text
data/poe2_live_terrain_test/probe_results/first-frame-local-20260922/
  report.json
  refined_best_overlay.png
  local-terrain-crop.png
  no_text_wall.png
```

### 2026-09-22 内存锚点局部注册实现完成

实验实现已落在 `tools/debug/poe2_anchor_local_registration_probe.py`，没有接入正式 runtime 或 `core`。同步样本会保存人物区域实例、世界坐标、原生 `grid`，以及与旋转/翻转后的 `terrain.png` 严格对齐的 `terrain_grid`；terrain manifest 同时记录 preview/native 尺寸和坐标空间。terrain 与人物实例不一致、坐标非有限/越界或新契约尺寸不一致时均 fail closed。

匹配流程现为：锚点小范围 terrain 裁剪 -> 顶部文字/人物中心清理 -> 锚点约束下的 Chamfer 粗搜 -> 多个接近的角度/镜像 basin 分别细搜 -> 合并候选判 `anchored_candidate/ambiguous/rejected`。锚点 hint/radius 已进入粗、细距离图，在 Top-K 截断前屏蔽范围外位置；不会再让重复房间先挤掉锚点附近真解。对称方向不会按人物位置去重成单候选，合成对称方形会稳定返回 `ambiguous`。

代码审查发现并修复了三项问题：同位置不同方向候选被吞、非默认 orientation 下 terrain/人物坐标错位、锚点约束晚于候选截断。新增覆盖包含 16 种旋转/水平翻转/垂直翻转坐标组合、对称方向判歧义、25 个重复结构下锚点前置约束、实例不一致和非法 marker。

真实样本 `20260922-043532-966126-MapFlotsam-1E44BF94` 修正后复跑结果保持一致：`anchored_candidate`，最佳 `219° / horizontal reflection=true / scale=0.85`，预测人物 `(307.4878, 401.8273)`，锚点误差 `7.1032`，结构分 `0.571715`，锚点加权分 `0.656589`。报告和叠图位于：

```text
data/poe2_live_terrain_test/probe_results/anchor-local-v2/
  report.json
  local_terrain.png
  prepared_feature.png
  best_overlay.png
```

当前边界：`anchored_candidate` 不等于跨帧确认；实时修复后最多选择 4 个方向 basin，并在 basin 内轮询保留最多 8 个相互分离的比例种子，粗分差窗口为 `0.10`。这些仍是待多地图校准的实验启发式。下一步应采集同实例连续移动帧，用首帧共享方向/镜像/比例只搜索局部平移，并验证轨迹连续性后，才讨论抽取通用能力和接入正式定位。

验证：核心实验/归档测试 `32 passed`，PoE2 terrain、采集窗口、composition 和主窗口相关回归 `136 passed`；目标源码语法编译和差异格式检查通过。未启动正式 runtime，未发送 Xbox、键鼠、Host 或 LAN 输入。

## 2026-09-22 混合实时定位设计已批准

用户确认先打磨混合模式：正常期间使用连续小地图视觉局部跟踪；首次进入和视觉跟踪丢失时读取一次人物内存坐标，以该坐标为锚点执行局部绝对注册。这里的“全局定位”指恢复可信绝对地图坐标，不再等同于搜索整张 terrain。

首次定位和丢失恢复共用同一个 `AnchoredAbsoluteRegistrar`。首次无 prior 时搜索方向、镜像、比例和平移；同地图恢复时锁定已确认方向、镜像和比例，只在新内存锚点附近细化平移。每个 recovery revision 最多读取一次内存；恢复失败后保持 `RECOVERY_REQUIRED`，未显式重试时不得在后续帧继续读取。

设计和 TDD 实施计划已落盘：

```text
docs/plans/2026-09-22-poe2-hybrid-localization-design.md
docs/plans/2026-09-22-poe2-hybrid-localization-implementation-plan.md
```

## 2026-09-22 混合实时定位实验实现完成

已按批准设计在 `features/poe2/live_terrain/experimental/hybrid_localization/` 完成实验闭环，仍未接入正式 `Poe2LocalizationRuntime`：

- `models/contracts` 定义只读帧、内存锚点、二维相似变换、绝对注册结果、运行状态及三个可替换协议。
- `OneShotRecoveryPolicy + HybridLocalizationController` 实现 `NEED_ABSOLUTE -> LOCAL_TRACKING -> RECOVERY_PENDING -> RECOVERY_REQUIRED`；每个恢复版本最多调用一次内存读取，失败后必须显式“重新恢复一次”。
- `similarity_search/absolute_registrar` 接管原 debug CLI 的纯算法；首次搜索方向/镜像/比例/平移，同实例恢复锁定前三项只细化平移。CLI 只保留样本与诊断 I/O，不再拥有算法实现。
- `Poe2MemoryAnchorProvider` 每次重新校验实例并把 native grid 变换到当前 reference 方向；`VisualLocalTracker` 只调用有界 `LocalMapMatcher`，没有整图回退。
- `Poe2HybridLocalizationSession` 每 tick 只截图一次、构建一次 evidence；Qt 定时器由数据采集测试页唯一持有。独立截图监控窗口只镜像同一状态，不会创建第二套内存读取。

数据采集测试页新增“开始混合定位 / 停止 / 重新恢复一次”。必须先初始化并获取当前地图；运行时显示当前 mode、来源、置信度、位置、内存读取次数和恢复版本，并在 terrain 上显示确认轨迹。失败帧 `position=None`，不会用旧确认点冒充本帧位置，也不会追加轨迹；绝对注册失败时会额外显示候选分数、覆盖率、角度、比例、锚点误差和具体拒绝原因，并写入同一日志状态行。

调用链：

```text
QTimer
 -> Poe2HybridLocalizationSession.tick()
 -> 同帧 capture + evidence
 -> HybridLocalizationController.update()
 -> 首次/恢复：OneShotRecoveryPolicy.consume()
    -> Poe2MemoryAnchorProvider.read_once()
    -> AnchoredAbsoluteRegistrar.register()
 -> 正常：VisualLocalTracker.track()
    -> LocalMapMatcher.match(radius=96)
 -> HybridLocalizationState
 -> 采集页 + 独立监控窗口 overlay/log
```

自动验证：五帧序列 `absolute -> local -> failed -> absolute -> local` 只读两次内存并产生四个轨迹点；恢复失败后连续十帧不增加读取次数，显式 retry 后只增加一次。相关完整回归 `187 passed`，语法与差异检查通过。历史真实样本重跑仍为 `219° / horizontal reflection=true / scale=0.85`、锚点误差 `7.1032`。

### 2026-09-22 实机首次注册漏解修复

实机首次启动稳定出现 `absolute_registration_failed`。日志和实时只读复跑确认地图实例、人物内存锚点、`200 x 200` 小地图截图及墙体 mask 都有效；默认搜索却选择 `327° / no flip / scale=0.29` 的不可行走低分候选并在精细搜索前淘汰正确比例。锁定历史已确认的 `219° / horizontal reflection=true / scale=0.85` 后，同一失败帧可得到结构分 `0.616`、锚点误差 `3.69`，证明根因位于候选剪枝而非数据采集。

修复包含两层：`similarity_search` 在粗 Top-K 前优先保留变换后人物点落在 terrain walkable 的候选，但容量允许时仍保留其他候选供歧义诊断；`absolute_registrar._refine_seeds()` 不再把同一方向下所有比例折叠成一个种子，而是在最多 4 个方向盆地内跳过重叠比例、轮询保留最多 8 个相互分离的比例峰。实时失败帧修复后得到 `215° / horizontal reflection=true / scale=0.91`、结构分 `0.650`、锚点误差 `4.26`，首二名锚点分差 `0.040`。

完整真实链路 `capture -> evidence -> one-shot memory anchor -> absolute registrar -> controller state` 已实机执行一次，结果为 `mode=local_tracking`、`source=anchored_absolute`、confidence `0.724`、position `(312.60, 400.86)`，内存读取恰好 1 次。相关 PoE2、UI、composition 与架构回归 `197 passed`。

当前边界：首次绝对注册已在当前 MapFlotsam 实机通过，但连续移动的 `visual_local`、真实丢失恢复、不同地图参数泛化和 UI 长时间性能仍未验证，因此仍只能称为实验实现。下一次实机验收应观察日志字段 `mode/source/confidence/position/reads/revision/reason/diagnostics`，确认正常移动只出现 `visual_local`、视觉失败后恰好增加一次 `reads`、恢复失败时读数保持不变。通过多地图和多次恢复后，才评估把不含 PoE2 语义的模型、controller 和 recovery gate 下沉 `core`。
## 2026-09-22 17:20 实机整链路修复断点

- 当前实例：`MapFlotsam:1E44BF94`，native terrain 为 `2416 x 2277`；本轮只读取截图、地图和人物锚点，没有发送键鼠、Xbox、Host 或 LAN 输入。
- 根因一：独立创建 hybrid experiment 时没有保证当前 profile 的 `recognizer_params` 已应用。独立实验的默认识别器只得到 348 个 wall pixels，并报 `cleaned feature contains fewer than 8 edge pixels`。factory 现会应用当前非空 profile 参数，不再依赖页面初始化顺序。
- 根因二：绝对注册和局部 matcher 曾直接消费“blocked/unknown 全填充”的 `TerrainReference.wall_layer`。这不是视觉墙线；它会形成大面积零距离区域，导致方向偶然重合、局部匹配 `mean_wall_error=0/candidate_margin=0` 并在首帧后立即失败。
- 修复：`reference_boundary_layer()` 从 known walkable mask 的 3x3 膨胀/腐蚀差生成薄边界；首帧和局部 matcher 共用该层。PoE2 composition 只在实验组合层注入实测局部容差 `max_error=4.0/min_margin=0.02`，通用 `LocalMapMatcher` 默认行为未改。
- 同一现场验证：首帧自动得到 `221° / 水平镜像 / 0.79`，人物锚点误差 `0.6635`；修复后的正式 factory 连跑 12 帧，首帧来源 `anchored_absolute`，后 11 帧来源全部为 `visual_local`，成功 `12/12`，内存读取总数 `1`，静止抖动不超过 1 像素。
- 证据目录：`data/poe2_live_terrain_test/probe_results/live-chain-20260922-170100/`、`live-boundary-chain-20260922-171317/`、`live-local-tracker-20260922-171100/`、`live-fixed-chain-20260922-171832/`。
- 自动验证：相关 PoE2/混合定位/UI/架构回归 `197 passed`，`compileall`、`git diff --check` 通过；Serena 对改动 composition 无诊断。语言服务器缺少虚拟环境时仍会把既有 `cv2/numpy/pytest` 标为 unresolved，这不是运行失败。
- 下一验收：保持当前实现不再调阈值，启动新版 GUI 后由用户实际移动人物，确认轨迹连续；随后测试遮挡或故意丢帧只触发一次恢复，以及换图后新的随机方向。

## 2026-09-22 18:12 GUI 恢复错时修复断点

- 用户截图对应日志并非“从未定位成功”：`17:54:19` 首帧已得到 `221° / 水平镜像 / 0.79`，之后约 5.6 秒持续为 `visual_local`，内存读取保持 1 次。`17:54:25` 局部匹配丢失后才进入恢复。
- 失败根因不是当前 profile 颜色参数。恢复旧顺序为“先截图 -> 再耗时读取人物内存坐标 -> 用新坐标匹配旧截图”；该次读取约 6 秒，人物移动后两者错时，最佳恢复候选锚点误差为 `19.05`，因此被正确拒绝。
- 修复后 `Poe2HybridLocalizationSession.tick()` 先让 controller `prepare_capture()` 消费一次性许可并缓存人物锚点，再立即截图；`update()` 复用该锚点，不做第二次读取。stop/reset/retry 都会清除未消费锚点，正常视觉帧完全不读内存。
- 当前 profile `a6ccb4c6767e` 未修改：正式页面 composition + `Poe2LiveTerrainPage/Poe2CaptureTestPage` 实机链重新初始化、抓图并启动成功，首帧自动为 `219° / 水平镜像 / 0.75`、锚点误差 `2.13`；随后 12 帧全部为 `visual_local`，位置 `(278.43, 397.85)`，reads 始终为 1。
- 自动验证：新增测试先复现“截图发生在锚点准备之前”和“prepared anchor 被重复读取”两个失败，再修复为 `11 passed`；本轮第一次 PoE2 相关回归 `170 passed`，`compileall`、`git diff --check` 通过。全项目断言结果为 `662 passed, 1 skipped, 10 subtests passed`，另有 3 个既有 `tests/test_pathfinder.py` 策略失败。复跑独立 UI 页面测试时 9 条断言均通过，但 pytest 在最终 Qt 垃圾回收阶段触发 Windows heap `0xc0000374`；这是单列测试清理风险，不能计作干净退出，与本次 controller/session 调用链无关。
- 程序已以 18:07 后的新进程启动并保持可见。下一步仍需用户实际移动以触发一次局部丢失，确认新顺序能恢复回 `anchored_absolute -> visual_local`；随后换图验证随机方向。

## 2026-09-22 正式页面实时视觉定位接入完成

正式 `PoE2 实时地形` 页面已从旧 `Poe2LocalizationRuntime` 切换为 `Poe2HybridProductRuntime`。正式页自己的 `monitor_timer` 是产品定位唯一驱动；获取地图时创建当前 snapshot 对应的 hybrid experiment，开始监控后由同一 timer 连续执行 session。嵌入的“数据采集测试”tab 现在接收同一 hybrid factory，但只创建独立 experiment/session/timer，不共享正式 runtime 的状态或内存读取计数。

当前正式调用链：

```text
获取当前地图
 -> Poe2HybridProductRuntime.configure_snapshot()
开始监控
 -> 首帧单次内存锚点
 -> 立即截图并绝对注册
 -> anchored_absolute / LOCAL_TRACKING
 -> 后续每帧纯视觉 VisualLocalTracker
 -> visual_local + 大地图位置/轨迹
 -> 视觉失败：RECOVERY_PENDING
 -> 下一 tick 自动读取一次内存锚点
 -> 成功回到 anchored_absolute -> visual_local
 -> 失败进入 RECOVERY_REQUIRED，后续 tick 不再读取
```

产品状态同时携带最近 raw/processed/wall mask、本帧位置、最后可信位置、轨迹、恢复版本、内存读取次数和帧耗时。正式页面显示这些字段并复用现有 `present_localization_overlay()`；失败帧的 `position=None`，不会拿最后可信位置冒充新轨迹点。

自动恢复触发已由真实 controller + session + 产品 runtime 组合测试固定：五帧来源严格为 `anchored_absolute -> visual_local -> failed -> anchored_absolute -> visual_local`，第三帧 mode 为 `RECOVERY_PENDING`，第四帧自动恢复为 `LOCAL_TRACKING`，锚点总读取次数为 2。另一测试让自动恢复失败，随后连续 5 个 tick 均保持 `RECOVERY_REQUIRED`，读取次数仍为 2。

监控配置弹窗继续使用 composition 独立注入的 `capture_preview` 和专用 recognizer 参数接口，不再依赖旧 runtime 私有字段。验证：PoE2 terrain、hybrid、composition、正式页面、配置弹窗、presenter、主窗口和架构边界回归 `199 passed`；`compileall`、`git diff --check` 通过；Serena 对产品运行时、session、composition 无源码诊断，页面仅有其语言服务器环境缺少 PySide6 的外部包提示。本轮没有启动真实输入、Host 或 LAN，也没有进行新的实机丢失恢复；下一次 GUI 实机验收应观察状态栏和日志中的 `mode/source/recovery_revision/memory_read_count/reason`。

## 2026-09-22 导航兼容连续跟踪实现

已确认并实现方案 A：PoE2 的首帧和恢复继续使用“内存人物锚点 + 锚点附近局部形状注册”；正常移动不再每帧以旧位置执行 Chamfer 搜索，而是复用导航模式的帧间位移预测。

新增通用能力：

- `core/localization/canonical_wall.py`：统一视觉 wall mask 与内存 walkable boundary 的二值形状表示；
- `core/localization/displacement.py`：将 minimap 位移经过旋转、镜像和比例变换到 terrain 坐标；
- `core/localization/frame_displacement.py`：phase displacement 的质量、最大位移和失败原因门控。

`VisualLocalTracker` 当前调用顺序：

```text
canonical previous/current wall mask
 -> estimate_bounded_displacement
 -> accepted: source=visual_f2f, position=previous-position - global-shift
 -> rejected: bounded LocalMapMatcher, source=visual_local
 -> both failed: controller enters recovery
```

本轮 focused 验证：相关 canonical/displacement/tracker/registrar 测试 `21 passed`，连续 tracker 回放 `5 passed`；PoE2 terrain、hybrid、composition、UI 和架构回归 `204 passed`。尚未做真实连续移动和真实视觉丢失恢复验收，下一阶段必须记录 `shift`、`quality`、`global_shift`、`source`、`position` 和 `memory_read_count`，确认位移坐标方向与内存读取频率。

详细断点见：

```text
docs/POE2_NAVIGATION_COMPATIBLE_TRACKING_CURRENT_STATE.md
docs/plans/2026-09-22-poe2-navigation-compatible-tracking-design.md
docs/plans/2026-09-22-poe2-navigation-compatible-tracking-implementation-plan.md
```

## 2026-09-22 首帧重复候选导致误判修复

实机失败快照复盘确认：同一恢复版本内只执行一次绝对注册；`RECOVERY_REQUIRED` 后页面停止 timer，日志中的多次尝试来自显式重试。真正的匹配缺陷是多个 refine seed 产出了相同的 `angle/flip/scale/position`，原状态门把重复项当作第二名，造成 `margin=0` 的假 `ambiguous`。

`absolute_registrar` 现先按同镜像、角度差 `<=0.5°`、比例差 `<=0.01`、人物位置差 `<=2px` 去重，仍保留不同方向 basin 的候选。另针对可靠内存锚点增加窄幅 coverage 容差：人物距锚点 `<=8px`、位于 walkable terrain 且 forward coverage `>=0.60` 时，允许略低于普通 `0.65` 门槛；普通候选仍按原门槛拒绝。diagnostics 同步输出两级 coverage 阈值和锚点接受半径。

最新失败快照以接近真实锚点复测结果为 `anchored_candidate`，最佳 `219° / horizontal reflection=true / scale=0.81`，锚点误差约 `3.14px`，原始 `forward_coverage=0.6336`；匹配单元回归 `14 passed`。下一次实机应确认实际锚点下不再出现重复候选和假歧义，再观察人物移动跟踪。

## 2026-09-22 全局恢复与方向自动展示修复

当前全局注册链路已补上两个实机稳定性保护：

- 恢复先沿用 prior 方向做快速搜索；失败时自动使用同一内存锚点进行完整方向/镜像/比例搜索，避免 prior 锁死导致每次恢复都报错。
- 候选在满足结构分、coverage 和 walkable 门后按内存人物锚点距离优先消歧；`8px` 内且与次近锚点相差 `2px` 以上时接受最近候选，不再把视觉分差小误判为 ambiguous。

展示层现在在首次/恢复 registration 成功后，将地图、marker 和轨迹整体按 registration 的逆角度与镜像变换到小地图方向，支持非 90° 角度；元数据显示自动校准角度。数据采集测试页已重新注入 hybrid factory，可独立启动同一实验链路。

离线 MapFlotsam 失败样本复测已由 `ambiguous` 变为 `anchored_candidate`（最佳锚点误差 `2.40px`）；PoE2 相关回归通过。仍待实机确认移动、视觉丢失恢复和多地图随机方向。

## 2026-09-23 首帧 terrain 匹配窗口校准

本轮确认“缩小范围”是缩小首帧/恢复使用的内存 terrain 匹配集合，不是缩放页面上的地图展示。当前 `200 x 200` 小地图样本以人物内存锚点为中心复测：`180/130` 可用但锚点误差 `7.10px`；`150/110` 仍为 `anchored_candidate` 且误差 `0.18px`；`140/100` 开始因裁切墙体而低于接受分数，`130/96`、`120/90` 同样失败。因此 PoE2 实验默认改为粗搜/精搜 `150/110`。

正式混合帧会从 evidence 保存实际 `capture_size`，registrar 按 wall mask 实际边长与 `capture_reference_size=200` 的比例缩放两个窗口；例如 `320 x 320` 截图使用 `240/176`。离线探针仍允许显式传入半径。registrar diagnostics 现在记录 `capture_size/crop_radius/refine_crop_radius`，便于从日志验证截图覆盖范围和 terrain 搜索范围是否匹配。

## 2026-09-23 地图显示放大与人物跟随

完整 native 地图按画布 fit 时，黑色未探索区域参与缩放，导致有效地形和人物过小。现已在通用 `ScalableMapWidget` 增加 `focus_on_point()`：输入未缩放源 pixmap 坐标，按当前 fit scale 放大并滚动到人物位置；PoE2 正式页和数据采集页默认使用 `2.4x` 跟随放大。本帧定位失败时使用 `latest_confirmed_position`，保持上一次可信区域，不跳回全图。

`presenter.localization_display_point()` 与地图逆旋转/镜像使用同一变换矩阵，保证任意角度校准后视口中心仍对应人物。人物 overlay 最小半径提高到 `9px` 并增加半透明填充，便于观察。用户仍可拖拽地图或使用 Ctrl+滚轮调整视角；该改动只影响显示，不改变地图坐标、匹配算法或定位状态机。

## 2026-09-23 连续轨迹坐标方向修复

用户反馈地图方向已经旋转正确，但人物移动后的轨迹没有跟随地图方向。根因已确认：首帧 `transform_feature()` 使用 OpenCV 图像坐标的正角度，连续帧 `transform_local_displacement()` 旧实现却使用笛卡尔坐标的正角度，导致同一角度下 `visual_f2f` 的 `global_shift` 在 y 轴反向。UI 将地图和轨迹一起逆变换并不能修复错误的全局位置。

现已统一 `core/localization/displacement.py` 与首帧匹配的 OpenCV 图像坐标约定，仍保持水平镜像 -> 旋转 -> 比例的顺序。回归测试验证 90° 向量方向以及任意角度/镜像/比例下与 `transform_feature()` 的两点差值完全一致；focused 共 `15 passed`。本修复不改变地图展示、内存读取次数或输入控制链路，实机下一步只需移动验证轨迹是否沿真实通道同步。

## 2026-09-23 首帧定位参数回归修复

用户实机反馈上一轮后首帧再次无法定位。失败归档显示：匹配范围仍然是 `capture_size=200`、`crop_radius=150`、`refine_crop_radius=110`，所以“按小地图范围缩小 terrain 搜索集合”的逻辑没有回退；真正失败点是当前帧顶部动态文字/传送点粗块残留在 wall mask 中，最佳候选落到 `angle=227°、scale=0.31`，`score=0.492`、`forward_coverage=0.609`，被正确拒绝。

对同一失败帧做参数复放：把 `top_exclusion_rows` 从 `25` 提高到 `35~40` 后，候选恢复到稳定的 `angle=219~221°、水平镜像、scale≈0.75`，`score≈0.55`、`forward_coverage≈0.75`，并且此前成功样本在 40 行下仍保持 `anchored_candidate` 和原锚点误差。已将 PoE2 实验默认顶部动态带调整为 `40`，没有降低通用 score 门槛，也没有放宽普通候选；diagnostics 新增 `top_exclusion_rows` 和 `player_clear_radius`，下次可以直接核对参数是否生效。

验证：PoE2/混合定位/UI/位移相关回归 `190 passed`，`compileall` 通过。实机重启后首帧应重点确认日志出现 `crop_radius=150/refine_crop_radius=110/top_exclusion_rows=40`，并观察候选角度、比例是否回到约 `219°/0.75`；本轮仍未发送任何输入或网络同步。

## 2026-09-23 多帧全局定位与导航定位完整方案

本轮只完成逻辑设计，没有新增实现。方案文件为：

`docs/plans/2026-09-23-poe2-multiframe-localization-navigation-design.md`

设计明确首帧与恢复都属于全局注册：一次内存人物锚点只用于限制 native terrain 搜索范围和校验人物位置；旋转、镜像、比例、平移仍必须由墙体形状证据确认。首帧墙体不足时，实验台收集移动关键帧，分别验证：

- 方案 A：按帧间位移拼接有界局部墙体，达到结构阈值后冻结拼图并注册；
- 方案 B：保留多个方向/镜像/比例候选，用共同变换和多帧墙体误差逐步淘汰。

A/B 共用同一采集帧，不能把两个结果当成独立测量重复提高置信度。图片所示的“预测、观测、物理门控、统计门控、滤波”放在候选已经确定之后，用于正常移动跟踪和短暂预测；不能用滤波掩盖错误方向或多峰歧义。

方案还规定 native 参考地形、视觉滚动拼图、截图/关键帧缓存分开管理。视觉拼图采用有界块和环形关键帧，窗口外为 unknown，不创建全图黑色缓存；native 参考地形仍保留一份供恢复和路线计算。正常跟踪沿用 `visual_f2f -> 有界局部形状纠偏 -> 单次恢复`，并输出位置、速度、协方差/候选区域、时效、证据版本和恢复版本给导航。

历史快照：当时仍未实现多帧策略，不能据此宣称首帧已稳定。该阶段后来已由下方 P1-P4、完整实施和最终自动方向收口条目替代；当前实验台已具备 A/B 和 schema 3 回放，但真实实机精度仍未验证。

## 2026-09-23 P0 多帧证据基础实现

已新增实验目录 `src/auto_modules/features/poe2/live_terrain/experimental/multiframe_localization/` 的前三个基础模块：

- `models.py`：不可变的多帧证据、候选区域、位置估计和运动状态契约；数组复制后只读，版本、时间、实例和坐标点有边界校验。
- `motion_gate.py`：复用 `canonical_wall_mask()` 与 `estimate_bounded_displacement()`，将相邻帧分为移动、静止、未知；低质量、过大时间间隔和 phase 失败不会被误判为静止。
- `evidence_window.py`：只接收已接受位移的关键帧，按最大帧数/时间窗口有界保存；静止不增长，segment 断链清空旧帧并递增 evidence version。

新增回归 `tests/poe2_live_terrain/test_multiframe_{models,motion_gate,evidence_window}.py`，与既有位移门控/变换回归合计 `18 passed`；实验目录 `compileall` 和 `git diff --check` 通过。另修正 segment 切换：新 segment 只清除一次旧窗口，后续同 segment 帧可连续进入。本阶段尚未实现方案 A/B、滚动拼图、全局注册或页面接入，正式 PoE2 页面和绘图模式未改变。

下一入口：实现有界 rolling submap，并用保留关键帧重建验证淘汰帧不会留下重影；随后再实现稳健形状评分和方案 A/B。

## 2026-09-23 P1-P4 多帧定位链路实现

已继续完成实验链路的主要模块：

- `rolling_submap.py`：从保留关键帧重建有限局部 wall/observed mask；淘汰帧不会残留，未知区域不写成墙。
- `shape_registration.py`：提供变换点投影、距离场和厚度容忍的 forward coverage/robust error 评分。
- `strategy_a.py`：满足关键帧、墙体像素和移动跨度后冻结 evidence version，调用 submap 注册，并拒绝同版本重复计算和留出验证失败。
- `strategy_b.py`：按方向/镜像/比例维护候选，累计多帧形状误差并去重；不同镜像或真实方向 basin 不会被平均成中间点。
- `state_estimator.py`：在已确认注册内部执行位移预测、Mahalanobis 观测门控和协方差更新；跳变观测被拒绝。
- `coordinator.py`、`session.py`：实现 anchor -> collecting -> tracking/degraded/recovering 的实验状态和单次 session tick 发布。
- `navigation_adapter.py`：只把 fresh、confirmed、未过期、有实例的位置转换成导航 observation；ambiguous/predicted/lost 不可执行。
- `archive.py`、`composition.py`：支持显式 evidence NPZ/manifest 归档、离线探针和 PoE2 测试台 factory 注入。
- `capture_test_page.py` 已增加“多帧全局定位实验”控制区；正式 PoE2 页面仍使用原 hybrid runtime。

历史快照：当时回归为 `54 passed`，A/B 的真实 native reference 回放尚未完成。该结论已被后续 schema 3 archive、registration validator、local corrector 和自动方向版本门实现替代；真实多地图校准仍是当前验收边界。

下一入口：补齐 A/B 的真实 terrain reference 注册适配、端到端样本回放、实机收集和性能/内存指标；没有这些证据前，不把新链路切换为正式定位默认实现。

## 2026-09-23 多帧定位完整实施断点

已按批准方案完成 PoE2 数据采集实验台的多帧全局定位闭环，正式 PoE2 hybrid runtime 和第一页绘图模式未替换。

已完成能力：

- 状态机覆盖 `IDLE -> ANCHORING -> COLLECTING -> REGISTERING -> TRACKING -> DEGRADED -> RECOVERING/WAITING`。
- 方案 A 使用有限 rolling submap、结构阈值和独立留出帧；方案 B 使用方向/镜像/比例多候选、多帧共同形状评分和 basin 去重。
- 正反向距离场评分容忍墙体粗细差异，reverse coverage 只统计实际 observed 区，圆形截图外不作为空白。
- 注册在单 worker 执行；instance/recovery/evidence/segment 四元版本门拒绝旧结果，注册期间的可靠位移会在确认后补偿。
- 正常移动使用视觉 F2F 位移；静止不增长证据也不触发失败；连续失败达到门槛才进入恢复，每个恢复 revision 最多读取一次内存锚点。
- 多帧锚点、reference 和最终位置统一使用原始 native terrain 坐标，不再叠加 profile 的手工旋转/镜像；自动 transform 只在展示层统一旋转地图、轨迹和人物点。
- 导航 adapter 仅在 `confirmed + fresh + age/instance/version` 全部合格时输出 `executable=true`，并计算协方差安全半径；没有接入自动移动或任何输入。
- 实验页已有 A/B 独立开关、开始/停止/重置/显式保存、rolling submap、候选/耗时/版本/内存读取诊断。归档原子保存 raw、wall、observed、位移、关键帧、候选、estimate 和 diagnostics。

最终聚焦验证：PoE2 定位、实验 UI、composition、位移、架构边界和全部 `tests/poe2_live_terrain` 回归共 `282 passed`；本轮新增 typed-boundary 回归包含在内，`compileall` 和 `git diff --check` 通过。Serena 代码诊断除未加载项目虚拟环境产生的 `numpy/cv2/PySide6` missing-import 外无新增问题。全仓 `pytest -q` 为 `744 passed, 2 skipped, 4 failed`：失败项是既有 `PathFinder` 行为冲突 3 项，以及当前环境缺少 `pydirectinput` distribution metadata 1 项，不属于本轮 PoE2 链路。

验收边界：合成端到端回放已经覆盖首次确认、旋转后移动、静止、degraded/recovery、每 revision 单次内存读取、后台注册位移补偿和旧结果丢弃。现有历史 samples 是单帧归档，缺少新协议的逐帧 motion/segment/version 数据，不能伪装成真实多帧回放。A/B 在真实 PoE2 多地图上的错误确认率、native 误差 P50/P95、确认距离/耗时、长期内存和恢复读取次数仍需下一次实机采集校准；在这些数据完成前，新链路保持测试台实验功能，不切正式默认定位。
验收边界：合成端到端回放已经覆盖首次确认、旋转后移动、静止、degraded/recovery、每 revision 单次内存读取、后台注册位移补偿和旧结果丢弃；schema 3 归档可重建 native reference、anchor、evidence 并由离线 probe 真实重跑 A/B。现有历史 samples 是单帧归档，缺少新协议的逐帧 motion/segment/version 数据，不能伪装成真实多帧回放。A/B 在真实 PoE2 多地图上的错误确认率、native 误差 P50/P95、确认距离/耗时、长期内存和恢复读取次数仍需下一次实机采集校准；在这些数据完成前，新链路保持测试台实验功能，不切正式默认定位。

## 2026-09-23 自动方向与多帧链路收口

本轮已完成方向所有权迁移和此前方案缺口补齐：

- `Poe2MonitorConfig` 删除用户手工旋转/水平镜像/垂直镜像字段；旧 profile JSON 仅忽略这些键，重新保存不再写回。采集、hybrid、正式页和 probe 均使用 native identity 输入。
- `SimilarityTransform2D` 是 `L -> N` 唯一方向事实源。`LocalizationPresentationState` 用 registration version 门保护地图、候选、人物和轨迹；版本变化会清空旧轨迹，未确认时显示 native 地图并等待自动校准。
- evidence window 受帧数、时间、累计行程和实际数组字节预算约束；rolling submap 使用可逆 wall/observed 权重，淘汰后重建可以去除旧噪声。
- shape registration 加入 Huber 损失、异常点裁剪、原始 coverage 和切向一致性；方案 B 从 45 度 basin 做有界粗到细精化，方向不再被量化为 45 度。
- `RegistrationValidator` 统一锚点、F2F 轨迹、holdout、margin 和 A/B 冲突门；`LocalShapeCorrector` 只在局部预测窗口纠偏，连续失败才恢复；coordinator A/B 异常隔离，session generation 防止旧 worker 发布。
- `MultiframeArchive` schema 3 只接受 `coordinate_space=native`，保存完整 native reference/anchor/evidence/estimate/diagnostics，旧 schema 2 或手工方向归档直接拒绝；`poe2_multiframe_localization_probe.py --strategy a|b|both` 会真实重跑策略。

仍未完成：没有实机重新采集 schema 3 多帧数据，不能宣称真实地图的错误确认率、位置误差和性能已达标；没有接入路线规划、Xbox、键鼠、Host 或 LAN 输入。

## 2026-09-23 完整性审查修复

本轮按真实操作顺序重新人工梳理了测试页、session、coordinator、A/B、展示和归档链路，确认并修复了四类此前被合成测试掩盖的边界：

- 方案 A 不再绕过统一确认门。A 的拼图/留出帧通过后，仍必须经过 native 实例、锚点误差、F2F 轨迹和 validator 条件；A/B 都通过时按已验证 confidence 选择较优结果，A 被 validator 拒绝会在面板状态中显示 rejected。
- schema 3 的 `estimate` 已真正可回放。`MultiframeReplayBundle` 现在重建 `PositionEstimate`、候选区域、二维相似变换、协方差、registration/evidence version、时效和 diagnostics，而不是只保存不读取。
- “保存实验”只有在 session 已有 anchor、reference 和非空 evidence 时才开放；archive 层也拒绝空 evidence。启动异常会关闭已创建的 session，避免后台 worker 泄漏。
- session 重启/重置会清空 frame id、previous evidence、anchor revision、证据 builder 的累计 offset/segment，以及 A/B 策略缓存；因此同一 experiment 被复用时不会把上一轮坐标或候选带入下一轮。
- 多帧 PoE2 composition 在构造实验时应用当前 profile 的 `recognizer_params`，与 hybrid composition 的识别参数契约保持一致。profile 手工旋转/镜像仍不参与 native 匹配，方向事实只来自注册 transform。

本轮新增回归覆盖 A validator fail-closed、A/B 质量选择、archive estimate round-trip、空 evidence、session restart、strategy reset、profile recognizer params 和 UI 保存门。聚焦多帧/PoE2 测试通过；`compileall` 和 `git diff --check` 仍是发布前必做门。

人工流程复核结论：从测试页开始，到一次内存锚点、运动门控、有界证据、A/B 后台注册、token 版本发布、F2F/局部纠偏、degraded/recovery、统一地图/轨迹/人物展示、显式 schema 3 保存和离线重放，链路均有明确输入、输出和失败状态。当前仍只在实验台，不切正式 runtime，也不执行路线、Xbox、键鼠、Host 或 LAN 输入。真实多地图错误确认率、native 误差、确认距离/耗时、恢复读次数和 UI 采集耗时仍需用户实机数据验收。
## 2026-09-23 启动接线与定位控制弹窗断点

本轮确认并修复了一个 UI 装配根因：`Poe2LiveTerrainComposition` 已有多帧工厂，但 `MainWindow` 未将 `multiframe_localization_factory` 传给 PoE2 页面，导致页面在地图已获取后仍提示“请先获取地图并注入多帧实验工厂”。主窗口现已完成传递，并由回归测试覆盖。

数据采集页的混合定位和多帧控制区已从可见布局移除。页面保留截图、预处理画面、匹配特征、当前地图和人物状态；新增非模态“定位控制”窗口承载 A/B 复选框、启动/停止/重置/保存和诊断。A、B 默认同时启用，关闭弹窗不停止 session。

实机只读验证：当前 `latest.npz`、默认监控框、实际屏幕采集和内存锚点可以创建并启动 A+B session，内存读取 1 次；人物静止时 6 帧均为 `collecting`，没有错误，也没有触发注册。后续用户测试步骤是打开定位控制窗口、确认 A/B 均勾选、点击开始，然后移动人物产生关键帧，观察注册结果和地图人物位置。

## 2026-09-23 实机 A/B 多帧运行结果与性能断点

本轮对用户分别执行的方案 A、方案 B 运行日志做了事实核对：

- 方案 A（约 `19:47:56`~`19:48:54`）达到 `required_frames=5`，实际多次提交 5~9 个关键帧的注册任务；每次都完成后台计算，但结果为 `source=none`、`has_registration=False`、`strategy_a_status=rejected`，随后发布为 `status=collecting` / `global_registration_ambiguous`。没有进入 `TRACKING`，没有可信人物位置，因此 A 本次未成功导航定位。
- 方案 B（约 `19:52:52`~`19:53:29`）达到 3 个关键帧并提交。第一次注册耗时约 `8142.77ms`，计算期间证据切换到新 segment，发布时被版本门判为 `stale_registration_result`；后续任务耗时约 `6554.61ms`、`8778.61ms`，均产生 `strategy_b_candidates=12`，但最终仍为 `global_registration_ambiguous`，没有进入 `TRACKING`。因此 B 本次也未成功导航定位；“有 12 个候选”只表示搜索产生结果，不表示方向/位置已确认。
- A/B 日志没有记录完整 validator 数值（anchor error、holdout error、candidate margin 等），当前能确认的是最终没有 registration；不能把这两次运行解释为“位置已确认但 UI 没显示”。

性能分层：

- 普通多帧 tick 的 `tick_ms` 在剔除首次初始化帧后，A 为约 `21.42~60.76ms`、平均 `37.25ms`、P95 `48.57ms`；B 为约 `16.94~48.92ms`、平均 `34.69ms`、P95 `44.43ms`。这相当于约 20~45 FPS，不能归因于截图帧提取完全跑不动。
- A 首帧约 `4420.83ms`，B 首帧约 `4362.18ms`，属于首次采集/识别初始化尖峰。
- 真正的体感慢点是全局注册：A 每次约 `3.26~8.90s`，B 每次约 `6.55~8.78s`。注册期间 UI 仍持续采集、重建证据和刷新地图；注册失败后只要 evidence version 继续变化，又会提交下一次昂贵搜索。
- 绘图模式的默认采样是 `10 FPS`，本轮多帧实验实际 `interval_ms=33`（约 30 FPS），且每帧执行多帧证据构建、位移门控和实验面板/地图刷新。因此“绘图速度比原绘图模式慢”的主要嫌疑是完整识别 + UI 刷新 + 后台注册竞争，而不是定时器没有按时取帧。

当前验收状态：A/B 两个真实实机方案均未通过全局定位确认门；下一步应先补充注册候选/validator 诊断（尤其 A 的 rejected 原因、B 的 12 个候选误差/holdout/margin），并限制失败后重复提交的证据增益，再讨论降采样或采样频率调整。尚未发送任何 Xbox、键鼠、Host、LAN 或自动移动输入。

## 2026-09-23 首次多帧注册卡住根因与修复

用户实机日志显示 session 并非没有启动，而是在只有 1 个关键帧时就进入了 `registering`：`pending=True` 持续存在，既没有 `registration_complete` 也没有 `registration_failed`。调用链复核确认 `prepare_registration_request()` 原先只检查 evidence 非空，没有检查启用策略的最小证据量；因此 Strategy B 过早在完整 `2416x2277` native 地图上启动方向/镜像/比例搜索，后台 worker 长时间占用，页面看起来像“第一步卡死”。

本轮修复：

- 内置 Strategy A 暴露 `minimum_evidence_frames = min_frames + holdout`，内置 Strategy B 暴露 `minimum_evidence_frames = min_support_frames`；协调器按启用策略取最大值，证据不足时只继续收集，不提交注册。A+B 默认组合因此至少等待 5 个关键帧（A 的 4 个训练帧 + 1 个留出帧）。旧自定义策略未实现该可选契约时保持兼容，默认按 1 帧处理。
- Strategy B 只在内存锚点附近建立有界 native reference crop，并通过 `reference_origin` 将候选变换恢复为绝对 native 坐标，不再对整张黑色/未探索地图重复计算距离场。
- Strategy B 的后台粗搜不计算切向近邻和反向栅格化；这些高成本指标保留给最终 validator，粗搜使用前向形状误差和 coverage。这样保持方向/比例候选搜索的职责，同时把计算限制在局部证据范围。
- session 增加注册任务提交、开始、完成、发布、异常、超时和丢弃日志；默认后台注册超时为 10 秒。超时后状态回到 `collecting`，旧 worker 仍被版本门隔离，完成结果不会覆盖当前状态，也不会再显示无期限的“后台注册中”。

验证：多帧 coordinator/session/shape/strategy/end-to-end 聚焦测试通过；实样本基准中 Strategy B 从完整地图搜索改为锚点局部 crop，单次评估从无法在 30 秒内返回降至约 6.3 秒；A+B 五帧合成评估约 8.1 秒。下一次实机应先确认日志出现 `registration_deferred ... required_frames=5`，移动积累足够关键帧后再观察 `registration_started/finished/published` 或明确的 `registration_timeout`。本轮没有发送输入、Host、LAN 或自动移动指令。

## 2026-09-23 全链路审查：启动卡住与生命周期修复

本轮按用户实际操作顺序复核：打开 PoE2 页面 → 初始化 → 获取地图/一次内存人物锚点 → 打开定位控制 → 启用 A/B → 启动多帧 → 定时采集截图/识别 → 关键帧门控 → 后台注册 → 发布到地图/人物/轨迹 → 停止/重启/恢复。静态回归之外增加了 fake capture/fake anchor 的状态流仿真，并先写失败测试再修复。

确认的真实缺口：

- 注册超时虽然把 coordinator 退回 `collecting`，但仍占用 `_registration_future`；后续调度入口直接返回，长时间运行的旧搜索会让页面持续像“卡住”。
- 超时 worker 原来共享当前 coordinator 和 A/B 策略实例；即使旧结果不发布，旧线程仍可能改写候选缓存或策略 attempt version，存在 stop/start 污染新运行的风险。
- 多帧页面停止后保留已关闭 experiment 引用，保存/状态刷新仍可能访问旧 session。
- 启动多帧没有检查小地图绑定，错误延迟到第一帧截图才抛出，用户看不到明确的前置原因。
- 普通截图预览和多帧定位可以同时启动；页面和独立截图监控窗口会重复调用同一个 capture/recognizer，增加卡顿和帧竞争。

修复后的链路：

1. session 在提交注册时复制 coordinator 外壳并深复制策略 A/B；worker 只操作隔离副本和冻结 request。
2. 超过注册超时后，active future 立即转入 retired 集合，当前 session 回到 `collecting` 并可在新 evidence version 上重新提交；旧 worker 完成只记录 retired 日志，不发布结果。
3. 页面启动前检查 `monitor_config.binding`；多帧运行会停止同页 preview 和独立截图监控 timer，保证一份截图源只有一个采样循环。
4. 页面停止多帧会关闭 session、清空 experiment/轨迹/状态，并关闭保存门；重新启动只能创建新的 experiment。

验证状态：session/page/end-to-end/composition 相关 `14 passed`，PoE2 全聚焦集合 `264 passed`。fake composition smoke 已验证内存锚点、截图、证据构建和状态推进；相同墙体/静止帧没有关键帧属于 MotionGate 预期行为。真实游戏移动、多帧 A/B 注册成功率、超时重试效果和 native 位置精度仍未在本轮实机确认，因此不能宣称定位已经稳定。

全仓回归为 `759 passed, 1 skipped, 3 failed`；三项失败均为既有 `PathFinder` 路径策略冲突（阻塞角、未探索区域、细墙），本轮未修改路径规划模块。`compileall` 和 `git diff --check` 通过。

合成完整状态流也已单独跑通：第 1~4 帧累积关键帧并保持 `collecting`，第 5 帧达到 A/B 门并进入 `registering`；强制超时后 active future 释放并进入 retired，下一帧可提交新的注册任务。该结果证明生命周期链路已闭合，但不等价于真实地图匹配成功。
## 2026-09-23 单帧锚点几何配准实机校准

本阶段首帧定位主线已收口为：一次内存人物 native-grid anchor 与同一时刻的小地图截图配对，只在 anchor 周边 native 局部区域做几何相似变换搜索；视觉只负责角度、镜像、尺度和形状一致性，内存 anchor 负责绝对位置消歧。后续移动帧由帧间位移/局部跟踪处理，只有视觉丢失才重新读内存并再次执行局部恢复。

已使用真实运行中的 `PathOfExile` 进程完成样本校准，样本目录为：

`data/poe2_live_terrain_test/samples/20260923-125356-431876-MapFlotsam-14A7A83E`

对应报告：

`data/poe2_live_terrain_test/probe_results/single-frame-20260923-tuned/report.json`

实机样本事实：地图实例为 `MapFlotsam:14A7A83E`，native 地图 `2968x2277`，小地图首帧 `200x200`，人物内存 anchor 为 `(285.49999, 418.50000)`。最佳候选为 `angle=219°`、`reflect_horizontal=true`、`scale=0.75`、anchor error `3.225 native px`、forward coverage `0.7973`、最终 anchored confidence `0.8182775`，状态为 `anchored_candidate`。

PoE2 实际 factory 已显式注入该校准配置，不再依赖隐式类默认值：

- 局部 native crop/refine：`150 / 110`（真实截图按 `capture_reference_size=200` 等比缩放）。
- 顶部动态文字/传送点排除：`40px`；人物区域清除半径：`22px`。
- anchor 权重：`0.65`；anchor 接受半径：`8px`；候选消歧间隔：`1.0px`。
- 最低接受置信度：`0.80`；低于此门槛的候选直接拒绝，不发布为可信人物位置。
- 视觉最低分：`0.50`；普通 forward coverage：`0.65`；可信 anchor 下的最低 coverage：`0.60`。
- 角度先按 `45°` 粗搜，再以 `2°` 细化；比例在 `0.35..2.45` 粗搜，再以 `0.02` 细化，避免把方向量化成固定 45°。

registrar diagnostics 现在同时输出 `best_score`、`best_anchored_score`、`confidence`、`best_forward_coverage`、`best_angle`、`best_reflection`、`best_scale` 和 `best_anchor_error`，页面现有状态日志会记录这些字段。当前证据只证明这一真实地图首帧达到 `0.818`，不外推为多地图生产准确率；下一步验收应收集至少第二张地图或同图第二次进图样本，检查比例和方向稳定性。

验证：单帧 registrar、PoE2 composition、hybrid 集成和 probe 聚焦测试 `28 passed`；新增低于 0.80 的拒绝回归；`compileall`、`git diff --check` 通过。没有发送键鼠、Xbox、Host、LAN 或自动移动输入。

## 数据采集测试页操作入口

数据采集测试页现在提供独立的“开始首帧定位”按钮，直接调用 PoE2 hybrid 单帧链路；“定位控制”窗口中的 A/B 仍然是旧的多帧实验，不用于本次首帧参数验收。启动单帧定位时，页面会停止普通截图预览、独立截图监控和 A/B 多帧 session，确保一个截图源只有一个采样循环。

测试顺序：

1. 在 PoE2 页面进入“数据采集测试”。
2. 点击“初始化”。
3. 点击“获取当前地图”，确认人物内存坐标已显示。
4. 确认监控配置已经绑定小地图区域。
5. 点击“开始首帧定位”。
6. 观察页面的首帧状态、截图、匹配特征和地图人物 marker；首帧成功时状态应显示 `local_tracking`、`source=anchored_absolute`、`confidence>=0.750`，并显示自动角度/镜像/比例。
7. 后续移动由视觉局部跟踪处理；只有丢失才会进入恢复状态并重新读取一次内存 anchor。

如果只想做 A/B 多帧实验，仍然通过“定位控制”窗口进入；不要同时启动两个定位入口。

### 2026-09-23 首次页面实机验收

用户已在数据采集测试页完成一次真实运行。首帧通过同实例内存 anchor 和小地图几何匹配得到 `angle=219°`、`reflect_horizontal=true`、`scale=0.75`、`anchor_error=1.961`、`confidence=0.822475`，高于生产门 `0.80`，随后状态进入 `local_tracking / visual_f2f`。整个运行期间内存读取计数保持为 `1`，没有失败或恢复重读。

截图显示的当前 `confidence=0.965` 是后续 `visual_f2f` 帧间位移质量；首帧 absolute confidence 是日志中的 `0.822`，两者不是同一个指标。本轮人物未产生可观测移动，因此逐帧诊断均为 `shift=(0,0)`，人物位置保持 `(287.4304, 418.8476)` 属于正常静止状态。下一轮只验证人物移动后的 marker/轨迹，不需要重新调首帧参数。

### 正式页接入状态

"实时地形定位”正式页使用同一个 `Poe2HybridProductRuntime` 和同一个 `build_poe2_hybrid_localization_experiment()`，不是另一套旧算法。正式页现在会显示首帧 `confidence`、最佳几何分、自动角度、自动比例、anchor 误差和覆盖率；正式 runtime 使用 PoE2 业务门槛 `minimum_confidence=0.75`，并在可信 anchor 下使用显式的 `minimum_score_when_anchored=0.35` 与 `minimum_forward_coverage_when_anchored=0.50`；通用默认值仍保持不变。数据采集页仅作为可重复实验入口，A/B 多帧仍是独立实验，不会接管正式页。

## 2026-09-24 截图尺寸 300 与自动比例标定

根因已经确认：active profile 曾同时保存 `capture_size=300`、`binding.rect=200x200`、`player_marker=(100,100)`；配置面板改动数值时没有重建 center binding，因此后端实际一直截 200x200。这不是比例搜索失效。现在 `Poe2MonitorConfig` 在任何加载入口都保证 center 模式不变量：保持原物理人物锚点不动，将 binding 规范为 `capture_size x capture_size` 并把 marker 置于新中心。当前 profile 加载结果为 `300x300`、marker `(150,150)`；region 画框不被自动改动。

300px 扩大视野后会引入顶部文字和底部游戏画面纹理。首帧链路现在按 `actual_size / 200` 同步缩放 crop、refine crop 和顶部排除行数，调用已有 component cleaner 删除孤立紧凑噪声；锚点注册使用形状优先权重 `(forward=0.55, distance=0.25, reverse=0.15, walkable=0.05)`，因为局部开口墙体无法稳定形成完整 walkable 填充。精搜不再在 memory-anchor 评分前按位置删除相邻角度/比例；独立 coarse angle/reflection/scale basin 才参与歧义 margin。

真实进程端到端结果：实际截图 `(300,300,3)`，自动角度 `221°`、水平镜像 `true`、自动比例 `0.77`、anchor error `1.951`、shape score `0.5075`、forward coverage `0.6410`、最终 confidence `0.81177`，状态进入 `local_tracking / anchored_absolute`。门槛仍为 `0.80`，没有通过降阈值放行。比例仍由每个新 session 的 `0.35..2.45` 粗搜和 `0.02` 细化自动确定，成功后跟踪固定本次 registration 比例；不按电脑写死 `0.77`。

当前结论只覆盖同一 `MapFlotsam:35DE728A` 的真实 300px 首帧以及此前 `MapFlotsam:14A7A83E` 的 200px 首帧。换电脑/分辨率的设计链路已闭合，但仍需积累不同 UI scale 和不同地图的回放样本校准搜索范围与权重；失败时应记录 scale response、独立 basin margin、anchor error 和清理后像素数，不要直接降低 confidence 门。

验证：PoE2 实验包、监控配置、截图选择、正式 composition 与相关页面回归 `263 passed`；`compileall`、`git diff --check` 通过。Serena 诊断未发现内部类型错误，其语言服务器环境仍未解析已由测试环境正常加载的 `cv2/numpy/PySide6`。本轮仅执行游戏进程只读地图/人物信息与屏幕截图，没有发送任何输入或启动网络同步。

## 2026-09-24 首帧 75% 锚定门槛实机复验

用户反馈最新一次 300px 首帧定位失败。先读取失败快照而不是直接降阈值，确认失败候选仍具有可信空间锚点：`anchor_error=0.325`、`player_on_walkable=true`、`angle=225°`、`reflect_horizontal=true`、`scale=0.77`、`best_anchored_score=0.7860`；被拒绝原因是旧的 `minimum_confidence=0.80`，同时该帧的图像分数 `0.396` 和 forward coverage `0.509` 低于原先为更强视觉样本设置的 `0.50/0.60`。

本轮只在 PoE2 业务组合调整首帧门槛，通用 registrar 默认值不变：`minimum_confidence=0.75`；只有人物锚点在 `8px` 内且候选落在可行走区域时，才启用 `minimum_score_when_anchored=0.35`；同一可信锚定条件下 `minimum_forward_coverage_when_anchored=0.50`，普通候选仍要求 `0.65`。诊断日志新增 `minimum_score_when_anchored`。

真实复验使用当前运行中的 `PathOfExile.exe`，重新初始化、读取 `MapFlotsam:35DE728A` 地图、读取一次人物内存位置并截取当前 300x300 小地图。结果：状态 `local_tracking`，来源 `anchored_absolute`，位置约 `(352.24, 671.70)`，角度 `225°`，水平镜像 `true`，比例 `0.77`，anchor error `0.325`，shape score `0.3956`，forward coverage `0.5089`，最终 confidence `0.7858`，成功通过 75% 门槛并发布位置。没有发送键鼠、Xbox、Host、LAN 或自动移动输入。

验证：PoE2 composition 与 registrar 聚焦回归 `25 passed`；真实端到端脚本成功；后续仍需用不同地图/不同 UI scale 样本验证 75% 门槛不会放行错误方向，不能把单张地图结果等同于生产准确率。

## 2026-09-24 后续跟踪漂移与性能根因排查

本轮仅做取证，没有修改定位参数或运行逻辑。当前正式页的后续帧链路是：

`VisualLocalTracker.track()` 对上一帧/当前帧 `wall_mask` 做 `canonical_wall_mask()`，调用 `cv2.phaseCorrelate()` 估计帧间位移；只要 `quality >= 0.20` 且位移未超限，就执行 `transform_local_displacement()`，并将结果按 `previous_position - global_shift` 累加。只有相位相关失败或跳变超限，才调用 `LocalMapMatcher.match()` 做局部形状匹配；局部匹配失败才进入恢复并重新读内存。

因此“前几步准确、移动一段时间后漂移”的首要结构性原因是：相位相关的微小系统误差会被无限累加，当前没有按距离/时间周期执行局部形状校正，也没有用校正结果替换累计位置。`displacement_quality` 是相位相关响应值，不等同于绝对位置可信度；当前 `visual_f2f` 的 `confidence` 直接使用该响应值，不能作为长期定位准确率指标。墙体粗细变化、动态文字/传送门和局部遮挡都会让二值墙体帧间位移出现小偏差，即使每帧都被 `accepted` 也会积累成漂移。

性能证据来自 `data/logs/poe2_live_terrain.log`：

- 首帧绝对匹配约 `6251~12979ms`，属于预期的全局/局部相似变换搜索开销。
- 后续 runtime 计算约 `63.1~73.0ms/帧`，峰值约 `140.6ms`。
- UI 绘制平均约 `192.4~240.9ms/帧`，峰值约 `402.9ms`，明显高于 `33ms` 定时器周期，实际展示帧率低于目标。

UI 热点已确认在 `Poe2LiveTerrainPage.handle_runtime_state()`：每帧转换并缩放两个预览、复制整张地图、重画轨迹/人物、按 registration 对整张地图做 OpenCV 逆旋转，再调用 `ScalableMapWidget.focus_on_point()`；后者每帧 `set_scale()`，而 `_apply_scale()` 每次都会对整张约 `3244x1725` 的 pixmap 重新 `QPixmap.scaled()`。绘图模式没有这组整图旋转/缩放/跟随操作，因此更流畅。

本轮结论：首帧内存锚点、方向和比例不是当前漂移的主要证据；必须先把后续链路改为“帧间位移只做短期预测 + 按距离/时间局部形状校正”，并将 UI 展示与定位计算解耦、缓存旋转/缩放地图后再优化参数。下一次实机取证需要记录连续运动帧的 `shift/global_shift/position_jump/displacement_quality`，以量化累计误差和校正触发情况；在此之前不应继续降低阈值或增加内存读取频率。

## 2026-09-24 跟踪校正与地图展示优化实施

本轮已完成第一版结构性优化，未改变首帧方向/比例搜索和内存读取策略。

### 后续定位

`VisualLocalTracker` 新增三个独立校正门：

- `correction_frame_interval`：累计帧数达到阈值；
- `correction_distance`：距上次局部校正的预测 native 距离达到阈值；
- `correction_interval_ms`：距上次校正的时间达到阈值。

只有当前帧确实有移动（phase displacement 距离超过 dead-zone）时，帧数/时间门才会触发局部匹配；静止画面不会周期性做昂贵校正。校正使用原有 bounded `LocalMapMatcher`，成功后以形状匹配位置替换累计预测，并写入 `correction_attempted/correction_accepted/last_correction_*` 诊断。校正失败时保留本帧相位预测，同时记录 `bounded_match_failed`；若相位位移本身不通过原有门控，仍保持 fail-closed 并进入恢复，不增加内存读取。

PoE2 factory 当前显式使用：`correction_frame_interval=12`、`correction_distance=24 native px`、`correction_interval_ms=1500`。这组值是第一版稳定性配置，不代表已完成多地图实机标定；后续必须用移动回放确认校正频率和 matcher 耗时。

### 地图展示与资源

`ScalableMapWidget` 新增独立 marker/trail overlay layer。正式页只在地图、方向或镜像变化时调用 `prepare_localization_map()` 旋转底图；人物、轨迹和候选区域通过 overlay 绘制，不再因位置变化复制/旋转整张 native pixmap。`focus_on_point()` 固定一次跟随基准缩放，重复跟随只移动滚动条，不再每帧把当前缩放再次乘以跟随倍率；手动缩放会重新建立跟随基准。地图重建或方向变化会清空并重建缓存，保证显示坐标和定位坐标分离。

### 验证与边界

新增 tracker 周期校正/静止帧不校正/校正失败降级回归；PoE2 相关集合首轮为 `258 passed, 1 failed`，失败是未修改的多帧形状评分测试，单独复跑通过；本轮新增和受影响测试全部通过，`compileall` 与 `git diff --check` 通过。尚未在真实游戏中完成长距离移动验证，因此当前不能宣称漂移已完全消除；下一步应让人物连续移动一段距离，核对日志中的 `correction_accepted`、`correction_distance`、`position_jump` 和 UI `average_render_ms`，再决定是否调整校正门或进一步降低预览刷新频率。

## 2026-09-24 首帧置信度门槛调整为 70%

PoE2 实时地形业务组合的 `minimum_confidence` 已从 `0.75` 调整为 `0.70`，仅影响
`_poe2_first_frame_registration_config()`，通用 registrar 默认值、绘图模式和其他业务不变。
锚定候选仍必须满足 `minimum_score_when_anchored=0.35`、
`minimum_forward_coverage_when_anchored=0.50` 以及 `anchor_acceptance_radius=8.0`；因此
置信度降低并不等于放弃形状覆盖率校验。若 `forward coverage=0.49`，仍会因为独立覆盖率门失败。

已同步 PoE2 composition 回归断言，并通过聚焦测试。当前没有新增不同地图/不同 UI scale 的真实样本，
所以该调整只证明业务门槛生效，不宣称跨地图定位准确率已经完成标定。

## 2026-09-24 参数调节、预处理复用与后台定位

PoE2 配置弹窗新增独立定位与性能参数：首帧置信度默认 `0.70`、锚定形状分默认 `0.35`、锚定覆盖率默认
`0.45`、定位目标 FPS 默认 `30`、截图预览 FPS 默认 `12`。参数保存在现有 profile JSON；旧 profile 自动补默认值，
运行中不能修改。通用 registrar、绘图模式和导航模式不读取这些 PoE2 字段。

正式 hybrid 定位已改为串行 `Poe2LocalizationWorker`。worker 按定位 FPS 捕获和处理，最多保留一帧待显示状态；
页面只消费最新状态，位置/轨迹跟随定位结果，截图和匹配特征预览按预览 FPS 更新。worker 为真实 MSS 捕获器在线程内
创建独立句柄，停止、恢复和地图会话切换通过 generation 丢弃旧结果，不并发调用同一个 session。

同帧证据生成增加一次墙体预处理复用，避免原先预览、墙体/边缘和 raw gray 各自重复处理。旧输出等价测试通过，
保存样本的本地基准从 200px 约 `42ms` 降到 `11ms`，300px 压力样本从约 `73ms` 降到 `24ms`。日志现在拆分
`capture_ms`、`evidence_ms`、`localization_ms`，并记录实际定位 FPS、UI FPS 和被覆盖显示状态数。

验证：配置、页面、worker、composition、hybrid session/runtime、识别器相关回归 `89 passed`。仍需在真实游戏中
连续移动确认 30 FPS 上限下的实际定位速率、首帧稳定性、周期校正和长距离漂移；当前没有将线程测试等同于实机准确率。

## 2026-09-24 后台定位链路收尾修正

页面层修正了两个实际运行边界：

- `Poe2LiveTerrainPage.start_monitoring()` 在启动正式后台 worker 前先设置 active 状态，避免 worker 极快完成首帧并发出 queued signal 时被页面误判为非活动而丢弃。
- `_update_frame_previews()` 只在 `match_mask` 为空时显示“本帧无匹配特征”；成功匹配帧保留 pixmap，不再被无条件的 `setText()` 清除。

验证：PoE2 监控/worker 回归 `6 passed`；性能相关聚焦集合 `272 passed`；架构边界 `22 passed`；`compileall` 和 `git diff --check` 通过。
全仓回归为 `789 passed, 1 skipped, 10 subtests passed, 3 failed`，失败均来自本轮未修改的既有 `tests/test_pathfinder.py` 路径规划断言，已作为独立基线问题记录。

当前实机启动阻塞不是 PoE2 定位链路：`bootstrap/main.py` 在 Windows 非管理员进程启动时会请求 UAC，因提权未获批准而退出；本轮没有绕过权限、发送键鼠/Xbox/Host/LAN 输入或启动自动移动。要做真实窗口验收，需要用户以管理员权限启动工作台，或后续明确要求增加只读开发启动模式。
