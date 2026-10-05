# PoE2 实时地形与人物定位断点

## 文档用途

这是 PoE2 实时地形任务的唯一阶段断点文档。每次暂停或切换阶段时，更新本文件中的状态、已完成内容、当前假设、未决问题和下一步入口，避免下一次开发重新推断上下文。

最后更新：2026-10-04

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

## 2026-09-25 双人首帧定位实验层

本阶段只新增实验层能力，未修改正式单人中心定位、正式页面、绘图模式或移动/输入链路。

新增目录：

`src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_localization/`

当前调用契约是：

1. `Poe2DualPlayerPositionSource` 在一个只读进程会话中读取当前 area 的实体数组（当前版本实验偏移 `area + 0x5B8`），过滤角色元数据并返回两个带稳定 metadata identity 的 native world/grid 样本。
2. `Poe2DualMemoryAnchorProvider` 将这两个样本通过同一 `TerrainOrientation` 转成两个 `PositionAnchor`；每次调用只增加一次内存读取计数。
3. 上层从同一张小地图帧得到两个 `PlayerMarkerCandidate`。`marker_candidates_from_observation()` 只按候选质量清理额外噪声，不按候选排序推断身份。
4. `DualFirstFrameExperiment` 把 anchor 快照和观察帧交给 `DualFirstFrameRegistrar`；后者对两个候选到两个内存 anchor 的两种排列分别尝试现有 `AnchoredAbsoluteRegistrar`。
5. 首个注册器得到的角度、镜像、比例、平移被 `transform_local_point()` 同时应用于两个候选；只有两个 native anchor 误差都在门内时才接受。
6. 诊断输出保留候选排列、两个 anchor error、pair confidence、注册器诊断和失败原因。

状态含义：

- `accepted`：一个共同变换同时解释两名角色。
- `rejected`：注册失败、共同变换无法解释第二名角色，或 pair confidence 低于门槛。
- `insufficient`：不是两个人物/两名候选，或候选置信度不足。
- `ambiguous`：两个身份排列的结果过于接近，拒绝猜测身份。

默认实验门槛为 `max_anchor_error=12 native px`、`minimum_pair_confidence=0.70`、候选置信度 `0.25`。这些参数只属于双人实验包装器，不会覆盖单人 `AnchoredRegistrationConfig`。

验证：双人首帧与适配器单元测试 `7 passed`；单人 registrar、相似变换和 PoE2 composition 回归 `36 passed`；本轮新增相关测试全部通过。PoE2 实验目录复跑为 `255 passed, 1 failed`，唯一失败是既有 `test_multiframe_shape_registration.py::test_huber_trim_reduces_outlier_error_without_hiding_raw_coverage` 的非确定性基线测试，单独复跑通过，本轮未修改该模块。当前已验证当前运行进程可以读出两名角色：`Metadata/Characters/StrDex/StrDexFourb` 与 `Metadata/Characters/Dex/DexFourb`，实例 `MapFlotsam:73681455`，native grid 约为 `(956.5,430.5)` 与 `(962.5,424.5)`。

## 2026-09-25 双人首帧实验挂接数据采集测试页

双人实验现已挂接到 PoE2 的“数据采集测试”页，新增一次性按钮“**双人首帧实验**”。操作顺序为：

1. 初始化；
2. 获取当前地图；
3. 点击“双人首帧实验”。

按钮只执行一轮流程，不启动定时器，也不影响“开始首帧定位”的单人中心模式：同一轮先通过实验专用只读实体读取器取得两个 native anchor，再抓取一张小地图；墙体匹配复用当前识别器，人物候选使用饱和色紧凑连通块检测；最后由同一个角度、镜像、比例和平移变换解释两个人物，并在页面显示 `accepted/rejected/insufficient/ambiguous`、两个 screen/map 坐标、anchor error、候选置信度、方向和比例。

地图上的两个结果点仅用于实验展示，已经是 orientation 变换后的 native 坐标，不会再次旋转，也不会把第二个人物强制放到中心。失败时保留错误和分阶段日志：`dual_first_frame.started`、`memory_success`、`capture_success`、`observation`、`result` 或 `failed`。

本轮新增饱和色检测器测试、双人页面入口测试和双人结果展示测试；双人实验与页面聚焦回归分别通过（8 tests、11 tests）。检测器仍是实验启发式，当前没有接入正式实时页面，也没有实现两人不同步移动、帧间视觉跟踪、运动模型或设备输入。实机验证时重点检查页面状态是否为 `accepted`，两个误差是否稳定低于门槛，以及一次操作的内存读取次数是否为 1。

本轮补充修正：双人首帧不再调用单人中心定位的默认擦除策略。识别接口新增显式的 `exclude_player` 与 `exclude_dynamic` 选项；双人实验两项均为 `False`，因此完整墙体和边缘特征保留，人物色块只作为独立候选输入，不会把墙体 mask 掉。单人及既有调用不传参数时仍保持原有 `player_clear_radius` 和动态色过滤行为。页面的“匹配特征”预览与实际双人注册使用同一份未擦除特征，避免预览和计算链路不一致。

另外，双人包装器创建的 `AnchoredAbsoluteRegistrar` 已使用独立配置：`player_clear_radius=0`、`top_exclusion_rows=0`。这保证注册器内部的局部特征准备阶段也不会再次擦除人物周边或顶部墙体；传入已有单人 registrar 时仍尊重调用方显式传入的配置。

### 2026-09-25 实机样本 E7645418 诊断

本次页面日志显示内存读取成功 1 次，实例为 `MapFlotsam:E7645418`，两个 anchor 为 `(264.50, 428.50)` 和 `(271.50, 432.50)`；同一帧检测到两个小地图候选 `(79,156)`、`(82,147)`。两种身份排列中只有一组通过共同变换验证：角度 `305°`、比例 `0.190`，映射误差分别为 `5.39` 和 `9.99` native px，说明双人空间配对已经成立。

该次 UI 显示 `rejected` 的直接原因是双人结果置信度取两人较小值，第二名为 `0.659`，低于 `minimum_pair_confidence=0.70`；不是内存读取失败，也不是没有找到候选。反向身份排列的误差为 `13.16`、`11.56`，因此身份排列本身有区分度。日志还显示注册搜索约耗时 `8.7s`，后续需要单独优化搜索速度，但不能把本次 rejected 误判为“没有定位”。本次样本发生在双人注册器关闭内部 feature mask 之前，重新测试时应重点核对注册诊断中的 `player_clear_radius=0`、`top_exclusion_rows=0`。

### 2026-09-25 双人共同几何与颜色配准器实验结果

本轮将双人首帧的默认计算模型改为共同 similarity 初始化：对每个候选身份排列计算两名角色的相对向量，按

```text
scale = |native_delta| / |screen_delta|
angle = angle(screen_delta after optional mirror) - angle(native_delta)
translation = native_anchor_1 - transform(screen_marker_1)
```

得到旋转、比例和平移。默认注册器先用这组参数直接把整帧墙体投影到 native 地图，并用墙体边缘距离场计算形状覆盖率；覆盖率不足时才回退到共同估计附近的局部墙体搜索。两个 anchor 的误差、相对距离误差、墙体覆盖率和候选置信度共同决定 pair confidence，不再允许“第一个人物贴准、第二个人被压缩”的单人变换。

颜色检测新增 `MarkerColorProfile`，每个 profile 可独立配置色相上下界、饱和度、亮度、面积和最大尺寸，并通过 `Poe2MonitorConfig.dual_marker_profiles` 持久化；旧版 `monitor.json` 没有此字段时自动使用“玩家1橙黄、玩家2蓝青”的默认 profile。PoE2 配置面板已增加两个颜色 profile 行，双人实验页会读取保存的 profile；单人中心定位和绘图模式不受影响。

离线真实样本回放结果写入：

- `data/poe2_live_terrain_test/probe_results/dual_joint_first_frame_20260925.json`
- `dual_player_live_20260925`：`accepted`，墙体覆盖率约 `0.8924`，pair confidence `0.8703`，两个 anchor error `0.0`，估计比例 `0.7714`、方向 `45.0°`；一次回放耗时约 `0.60s`。
- 同批次 `dual_player_20260925`：`accepted`，pair confidence `0.8933`，身份排列 margin `0.1633`；颜色 profile 顺序参与身份排列评分后不再误判为 ambiguous。
- 当前运行进程 `MapFlotsam:E7645418`：真实读取两名 native anchor `(264.5,428.5)`、`(296.39,405.40)`，实时截屏候选 `(106,148)`、`(55,155)`，结果 `accepted`，pair confidence `0.8565`，身份排列 margin `0.1665`，两个 anchor error `0.0`，单次计算约 `0.44s`。结果明细写入 `data/poe2_live_terrain_test/probe_results/dual_live_current_e2e_20260925.json`。

相关单元和页面回归：PoE2 相关测试 `278 passed`，编译检查和 diff 检查通过；全仓测试为 `802 passed, 2 skipped, 4 failed`，失败项是环境缺少 `pydirectinput` 和既有 PathFinder 基线，不涉及本轮双人代码。下一步实机测试仍只需要在数据采集测试页执行“初始化 → 获取当前地图 → 双人首帧实验”；页面会显示两个 profile 候选、共同方向/比例、两个误差、覆盖率和拒绝原因。当前仍未接入双人实时移动跟踪，也未发送任何设备输入。

### 2026-09-25 双人近距离基线退化修正

对实机样本 `MapFlotsam:E7645418` 的日志复盘确认：两名候选 `(77,155)`、`(85,148)` 都被独立检测到，内存读取也成功；异常来自两点共同解算的数值条件，而不是人物颜色完全粘连。该帧屏幕基线约 `10.63 px`、native 基线约 `8.57 px`，当前算法若直接用
`scale=|native_delta|/|screen_delta|` 和两向量夹角求旋转，单个像素的轮廓中心误差就会显著放大方向和比例误差。因为变换又会把两个 anchor 强制贴合，所以会出现 `anchor_error=0` 但方向不稳定的“假正确”。

双人实验新增 `minimum_screen_baseline=16`、`minimum_native_baseline=12` 两个仅限实验包装器的稳定性参数。只要任一基线低于门槛，就不再使用双点直接解算，而改用两名候选的屏幕中点与两个内存 anchor 的 native 中点做一次几何注册；墙体形状负责确定旋转/比例，注册后再分别验证两个候选到各自 anchor 的误差。该路径诊断标记为 `pair_mode=midpoint_geometry`；基线足够大时仍使用原有 `pair_mode=direct_pair`，分开场景的行为不变。

新增回归覆盖近距离路由，并通过双人首帧测试 `12 passed`、编译检查和 `git diff --check`。本次尚未重新采集游戏进程的近距离原始帧，因此真实地图上的最终方向稳定性仍需在数据采集页重新执行一次“双人首帧实验”确认；重点查看结果中的 `pair_mode`、两个 anchor error 和方向是否随重复点击保持稳定。

### 2026-09-25 近距离样本重新闭环

上一轮失败样本的根因不是候选检测或内存读取：日志中两个候选为 `(77,155)`、`(85,148)`，屏幕基线 `10.63 px`、native 基线 `8.57 px`，中点局部搜索的最佳前向覆盖只有约 `0.49/0.61`，低于 `0.60` 门槛，因此没有产生 registration。此前代码在近距离模式只依赖中点局部搜索，虽然保留了两种镜像初始化，但本帧可见墙体不足以在窄角度/比例邻域内恢复正确方向。

实验注册器现已调整为：近距离仍以中点作为稳定回退，但先对两点 similarity 的两个镜像分支做一次墙体覆盖验证；只有覆盖达到 anchored 门槛才接受该候选，不能仅凭两个 marker 强制贴合。覆盖不足时才进入中点局部搜索，再保留原有 fallback。单人、远距离双点路径和正式实时页面均未改变。

使用当前运行的 `MapFlotsam:E7645418` 实机进程、同一份 `latest.npz`、同一时刻读取的两个 native anchor `(264.50,428.50)`、`(273.07,428.25)`，以及重新截取的小地图 `(77,155)`、`(85,148)` 做完整后端重放，结果为：

- `status=accepted`，`reason=one transform explains both player markers and memory anchors`；
- `pair_mode=midpoint_geometry`，两个候选均完成 registration，`evaluated_assignment_count=4`；
- 正确颜色排列为 `p1 -> observation-0`、`p2 -> observation-1`，`profile_consistency=1.0`；
- 方向 `222.824°`、比例 `0.8063`，两个 anchor error 均为 `0.0`；
- 墙体覆盖 `0.7681`，pair confidence `0.8492`，身份排列 margin `0.0834`；
- 内存读取 1 次，未发送任何输入。

本轮验证：双人实验单元测试 `12 passed`，真实当前帧后端闭环通过，目标是先让数据采集测试页的“双人首帧实验”在重启后复现该结果；若页面仍失败，应保留新的 `failed_assignments` 和 `joint_shape_coverage`，不再直接调低阈值。

随后按页面相同顺序再次闭环（先读取 anchors，再截屏、识别、注册）得到 `accepted`，候选仍为 `(77,155)`、`(85,148)`，`evaluated_assignment_count=4`，正确颜色排列的 `profile_consistency=1.0`，墙体覆盖 `0.7611`，pair confidence `0.8447`，两个映射误差仍为 `0.0`。这次重放使用当前运行进程和当前 monitor profile，确认修复不是离线伪造结果。

### 2026-09-25 双人颜色观测瞬时空帧修正

用户实机点击时页面出现 `insufficient | exactly two minimap marker candidates are required`。日志显示前两次点击都在同一地图和同一配置下得到两个候选并 `accepted`，第三次只在单帧中得到 `candidates=0`；随后重新截屏立即恢复为 `(85,148)`、`(76,155)` 两个候选。由此确认是游戏小地图动画/刷新时序造成的单帧颜色观测空帧，不是 profile 永久失配，也不是内存坐标问题。

数据采集页的双人按钮现在在一次内存读取之后，最多连续采集 3 帧小地图，每帧重新做颜色候选检测；只要某一帧得到恰好两个候选就使用该帧进入注册，期间不重复读取内存。日志新增 `capture_success attempt=x/3`、`observation attempt=x/3` 和空帧告警，最终失败时仍保留最后一帧和候选数量。这样不会增加游戏内存读取频率，也不会改变单人定位或正式实时链路。

页面与双人测试回归 `23 passed`，编译和差异检查通过；当前后端实机样本仍可达到 `accepted`，墙体覆盖约 `0.76`、pair confidence 约 `0.84`。

补充实测：当前第二名 native anchor 移动到 `(273.50,428.50)` 后，按同一页面链路再次读取 1 次内存并截屏，候选 `(85,148)`、`(76,155)`，仍为 `accepted`，墙体覆盖 `0.6844`、pair confidence `0.7949`、两个 anchor error `0.0`。这说明重试修正同时覆盖了人物距离轻微变化的情况。

### 2026-09-25 双人方向二义性与地图展示修复

最新用户截图对应的远距离 `direct_pair` 日志同时出现两组二点解：`29.334°/无镜像` 与 `223.426°/水平镜像`。合成变换验证证明 `_joint_similarity_estimates()` 的角度公式与 `transform_feature()` 一致；二义性来自“两个点 + 可选水平镜像”本身，而不是简单的角度正负号。旧 direct 实现把 `TerrainReference.wall_layer`（所有非 walkable/unknown 都是 255）直接交给 `terrain_edges()`，结果将大面积 blocked storage 区误当墙体，两个方向的单向覆盖率被错误拉近。

已修复：双人 direct 与 midpoint 注册统一通过 walkable 的 canonical boundary 构建匹配地形，只把真实可行走区域边界作为墙体证据；诊断额外记录 `reference_boundary_pixels`。使用真实 E7645418 截图 `dual_live_screen_20260925.png`、同实例 native 导出和内存 anchors 重放，修复后得到 `accepted`、`pair_mode=direct_pair`、`angle=223.738°`、`reflect_horizontal=true`、`scale=0.76494`、`joint_shape_coverage=0.6983`、两个 anchor error `0.0`。同一份近距离截图仍由 midpoint 分支选出 `221°/水平镜像`，anchor residual 约 `0.25`，没有回退到不稳定的二点角度。

另一个独立问题是页面展示链路：`_render_dual_first_frame_result()` 原先只在 native 地图上叠加两个点，没有使用 `primary_registration.transform`。现已使用与正式定位页相同的逆变换展示地图和两个点，并将视口聚焦点转换到旋转/镜像后的显示坐标；因此方向结果不再只显示在文字中，而会实际作用于地图。

本轮聚焦回归为 `25 passed`，编译检查、运行时错误级 Ruff 检查和 `git diff --check` 通过。PoE2 集合为 `277 passed, 1 failed`；唯一失败仍是既有的非确定性 `test_multiframe_shape_registration.py::test_huber_trim_reduces_outlier_error_without_hiding_raw_coverage`，单独重跑通过，未触及本轮双人代码。Serena 诊断仅剩工作区 Python 环境未配置 `cv2`、`numpy`、`PySide6` 的导入提示；实际项目解释器下测试和编译均通过。

### 2026-09-25 双人近距离 accepted 误判根因

用户再次实测后仍发现结果不正确。对 `17:16:27` 的真实日志逐字段复核：实例、一次内存读取和两个颜色候选均正确，问题发生在注册接受条件。该帧两个候选的屏幕基线为 `11.40 px`、native 基线为 `9.00 px`，已进入 `midpoint_geometry`；但实现仍先生成两点直接 similarity，并在墙体覆盖达到 `0.60` 时直接返回。于是 `joint_angle=322.125°`、`joint_shape_coverage=0.684` 的方向被接受，同时两个 anchor error 被平移强制为 `0`、pair confidence 被相对向量强制为 `1`。这些数值并不是独立证据，不能证明方向正确。

本次根因结论：近距离分支仍把病态的两点向量作为最终方向，且接受分数过度依赖被同一变换强制满足的 anchor/pair 项；不是颜色检测、内存读取或地图实例错配。后续修复必须让近距离方向只由中点周围的墙体形状搜索决定，并在注册后用两个 anchor 的独立残差进行验证；若形状证据不足应返回 `rejected/ambiguous`，不能以 `accepted` 掩盖不确定方向。单人中心定位和远距离双人分支保持不变。

### 2026-09-25 近距离形状搜索修复

近距离分支已改为中点局部形状搜索：先在以 native 中点为中心的局部窗口中遍历粗角度、镜像和由两点距离约束的比例，再对最高候选做角度/比例细化。候选分数由墙体覆盖率和两个 anchor 的独立残差共同组成；不再调用 direct two-point registration，也不会把 `anchor_error=0` 当作方向证据。近距离验收新增 `midpoint_max_anchor_error=6.0`，超过该值直接拒绝。

为避免重复计算，同一近距离帧只执行一次包含两个镜像分支的形状扫描；单人中心和远距离双人路径未改变。离线真实双人样本重放由原先约 `23s` 降至约 `1.25s`，结果为 `accepted`，墙体覆盖约 `0.799`，两个独立 anchor 残差约 `0.06`。双人单元回归目前为 `13 passed`。仍需在用户当前 E7645418 帧重复点击确认方向稳定；若形状覆盖或独立残差不足，应保持拒绝并记录候选，而不是降低门槛。

随后使用当前 E7645418 的真实截图文件 `dual_current_raw_after_failure.png`、同实例 native 导出和日志中的两个内存坐标重放，结果为 `accepted`，墙体覆盖 `0.865`、pair confidence `0.876`、两个独立 anchor 残差约 `0.01`，单次后端计算约 `1.5s`。本次综合变换为 `angle=38°`、`reflect_horizontal=true`、`scale=0.789`；与旧的 `angle=322°` 直接双点结果不同，但方向由局部墙体形状和独立 anchor 残差共同确定。PoE2 聚焦集合为 `262 passed, 1 failed`，失败仍是未修改的 `test_multiframe_shape_registration.py::test_huber_trim_reduces_outlier_error_without_hiding_raw_coverage` 非确定性基线。

### 2026-09-25 双人方向跳变与展示链路根因

用户反馈双人站近或站远时首帧方向仍不正确。对最新日志逐字段复盘确认：远距离 `direct_pair` 同一组 screen/native anchors 会同时生成两组完全满足 anchor 的解，例如 `29.334°/无镜像` 与 `223.426°/水平镜像`；两组的 `anchor_error=0`、`pair_confidence=1` 是由同一个两点变换强制得到的，不能作为方向证据。现有 `_direct_joint_registration()` 只计算单向墙体覆盖率，两个镜像候选覆盖率接近时会随截图像素噪声切换，因此表现为方向或反转不稳定。合成回放已确认角度公式本身与 `transform_feature()` 一致，问题不是简单取反。

同时确认数据采集测试页的 `_render_dual_first_frame_result()` 没有使用 `result.primary_registration.transform` 变换地图：它直接绘制 native 地图，再把两个 native 点叠加。因此即使后端找到了方向，页面也会看起来没有旋转/镜像。修复必须同时覆盖 direct 的独立双向形状评分和页面的逆变换展示；不能只降低阈值或修改方向文本。

### 2026-09-25 双人匹配特征中的圆环取证

用户反馈双人页面“匹配特征”里人物周围仍有一圈 mask。对当前实机样本
`data/poe2_live_terrain_test/probe_results/dual_current_raw_after_failure.png`
逐层复核后，确认该圆环不是人物擦除逻辑：

- 页面双人提取明确传入 `exclude_player=False`、`exclude_dynamic=False`；
- 双人注册器配置 `player_clear_radius=0`、`top_exclusion_rows=0`；
- 当前样本人物候选约为 `(76,155)` 和 `(85,148)`，而圆环中心约在 `(55,155)`，两者并不重合；
- 圆环来自小地图中独立的圆形地图图标/传送门亮边，`transparent_mode` 的亮度阈值和 Canny 边缘把它当成了几何特征，所以在二值“匹配特征”预览中显示为白色环；
- 这不是人物周围墙体被圆形清零。双人链路当前仍保留人物附近的墙体证据。

因此不能重新启用整圈人物半径擦除来消除该视觉现象，否则会重新遮掉人物附近的墙体。后续如需降低图标对匹配的干扰，应在 PoE2 双人实验适配层增加“图标证据过滤”或独立的图标诊断层，只移除被识别为图标的像素/组件，并保留墙体；不得修改通用识别器默认行为，也不得影响单人绘图模式。

同时发现一处真实的预览策略不一致：双人按钮计算时使用无擦除 `combined[0]`，但页面 `preview_timer -> refresh_preview() -> _render_preview()` 原来会按单人默认参数重新提取，覆盖右侧“匹配特征”预览。当前采集页记录双人预览状态，后续手动/定时刷新继续传 `exclude_player=False, exclude_dynamic=False`；重新获取地图、清空或切回单人/多帧实验时恢复原默认参数。页面测试先复现刷新回退，再验证双人刷新和重新获取地图后的单人恢复。这个修复只让预览忠实显示双人特征，不会自动清除圆形地图图标；双人注册计算本身此前已使用无擦除特征。

### 2026-09-25 双人运动定位实验入口

数据采集测试页现在有独立“开始双人实时定位 / 停止双人实时定位”按钮。操作顺序：初始化、获取当前地图、确认双人颜色 profile/监控区域、点击开始。开始按钮自动执行一次现有双人首帧注册；首帧拒绝则不启动 timer。首帧接受后固定方向、镜像和比例，后续仅截取小地图和识别两名颜色候选，以墙体帧间位移更新共同视口变换，再独立映射两人到 native 地图。角色缺失/近距离身份歧义只隐藏该角色，不把上一帧旧坐标显示为实时坐标。地图旋转一次后使用轻量 overlay 实时画两人，不每帧重建大地图，也不遮掉人物周围墙体。

墙体相位位移失败或周期到期先在预测位置附近做固定方向/比例的有界地图纠偏；连续失败达到门槛才发一次恢复请求，重新读一次双人锚点并注册。恢复后 10 秒内再次失配会停表提示人工检查配置，不循环读内存。换图、清空、关闭和切换单人/多帧定位都会停止该 timer。所有路径均不发送游戏输入或 LAN 消息，正式页面和原绘图模式未改。

验证：双人运动、首帧、测试页、多帧页面、单人局部跟踪和地图控件聚焦回归 `46 passed`；新增运动模块 Ruff、编译和 diff 检查通过。合成序列覆盖两人异步移动、遮挡、颜色交叉、近距离歧义、旋转/镜像、局部纠偏与恢复门。当前无 `PathOfExile` 进程；现存双人图片不足以组成带真实位置真值的连续运动序列，因此本次**不能声称实机运动跟踪已稳定**。下一轮应先在数据采集测试页启动双人实时定位，让两人分别移动一段路并保留 `data/logs/poe2_live_terrain.log` 中的 `dual_motion.tick` 日志，再按共同平移和各角色坐标逐帧核对。

### 2026-09-26 双人运动定位正式页接入

双人运动定位已经从数据采集测试页接入正式 PoE2 定位页，仍保持“底层能力复用、PoE2 业务组合”的边界：

- `Poe2MonitorConfig.tracking_mode` 新增 `single`/`dual`，旧配置缺省为 `single`；配置窗口可切换模式，已有双人颜色 profile 继续复用。
- 正式 composition 根据当前 profile 选择单人 `Poe2HybridLocalizationSession` 或双人 `Poe2DualLocalizationSession`；不把双人算法复制进页面，也不改变单人中心定位。
- 双人 session 首帧和恢复在 `Poe2LocalizationWorker` 线程执行：一次读取两个 native anchor、同帧截图和颜色候选配对；普通帧只使用墙体共同视口位移与两名颜色候选，不轮询内存。
- 双人连续失配由 `DualVisualTracker` 发出一次性 recovery request；正式 worker 暂停并等待页面“重新定位”，恢复按钮只开启下一轮一次性读取，避免后台循环读内存。
- `Poe2HybridProductState` 保留旧单人字段，同时增加 `dual_players`、`dual_screen_positions`、`dual_trajectories`、`dual_status` 和 `dual_wall_quality`。正式地图 overlay 使用同一旋转/镜像变换显示两个独立 marker，单人仍使用原 marker/轨迹。
- 双人识别证据明确关闭人物圆形擦除和动态擦除，保留两名角色周围墙体；颜色 profile 只负责候选生成，身份仍由共同几何注册确认。

本轮验证：双人正式 session、runtime adapter、配置、composition、正式页面及既有 PoE2 定位集合共 `300 passed`（其中正式接入聚焦测试 `78 passed`）；compileall 和 `git diff --check` 通过。当前尚未在真实双人移动过程中验证正式页的连续帧耗时、恢复频率和进程内存布局；首次实机测试应确认 profile 为“双人定位”，然后执行“初始化 → 获取当前地图 → 开始定位”，并保留 `data/logs/poe2_live_terrain.log`。

### 2026-09-28 未知 PoE2 版本自动指纹探测

外部 `D:/ACloud/poe2-map-research/windows_capture.py` 已改为每次初始化计算当前进程指纹。已知版本走原快路径；未知版本必须经只读 AOB、唯一地形结构、descriptor/guard 和有界稳定样本校验，通过后仅建立本次动态 session，不追加永久白名单。实际对当前客户端指纹 `3440AC1DBDF822DC8A5F25F0` 初始化成功，随后同一 session 抓取 `MapFlotsam:73DCFC09` 并导出 `3382×1863` native 地图。研究仓库 `38 passed, 20 subtests passed`，正式 PoE2 地形/采集/页面回归 `322 passed`。尚未通过 UI 点击或验证新版本双人角色内存偏移；下一步由用户在正式页测试“初始化 → 获取当前地图”，若双人定位再失败，应单独检查人物锚点适配，不应回退到手工指纹白名单。
## 2026-09-28 双人首帧配置断层修复

实机数据采集页 `P2_7:54BE4D92` 曾出现“双人首帧 rejected | no marker-to-memory
assignment produced a registration”。日志显示内存锚点读取成功、候选数为 2，
但双人近距离中点几何最佳候选的 anchor 平均误差仅约 `0.02`，墙体覆盖率为
`0.5175`，被通用 registrar 默认的 `minimum_forward_coverage_when_anchored=0.60`
挡住。问题是 PoE2 双人入口未复用 PoE2 已校准的锚定门槛，不是坐标或人物识别失败。

现已新增 `build_poe2_dual_first_frame_registrar()`，正式双人定位和数据采集页
都从当前 `Poe2MonitorConfig` 读取 `first_frame_anchored_coverage`（默认 `0.45`）
和锚定评分配置。双人路径仍保持 `player_clear_radius=0`、`top_exclusion_rows=0`，
不会 mask 人物周围墙体。相关回归 `44 passed`，compileall 和 diff check 通过。

### 2026-10-01 路线探针卡墙根因与采集页布局

管理员路线探针在当前实例 `P2_7:54BE4D92` 上完成了路线生成和逐段原图碰撞校验，
但旧输入映射执行后只移动约 `19.55` native 网格，未到 `(630,925)`。此前固定左摇杆
`(1,0)` 的实测位移约为 native `(+27.52,-33.04)`，确认 PoE2 的等距摄像机使摇杆轴
同时影响两个 native 轴；问题不是当前 native 起点 `(529.50,1088.50)` 或墙图坐标偏移。

新增 `features/poe2/live_terrain/movement.py`，定义 PoE2 适配层
`POE2_MAP_TO_STICK_BASIS=(0.5,-0.5,0.5,0.5)`。本节记录的第一版只使用固定基底；后续
已在下方补上首帧 registration 的逆旋转/镜像适配。通用 `ProgramGamepadOutput` 默认基底、
绘图模式和其他游戏没有改变。固定基底仍需用 native X/Y 两个短程方向做第二次实机标定，
当前不能宣称门后路线已经通过。

数据采集测试页已重排为：主区保留截图/预处理/匹配特征和大地图，右侧可滚动侧栏承载
控制、状态、跟随/真实手柄移动实验和日志。离屏 `1600x900` 检查显示主地图约
`1186x562`、预览单格约 `391x220`、侧栏宽 `360`。聚焦回归 `49 passed`，compileall
和 `git diff --check` 通过。

### 2026-10-01 路线方向使用首帧注册变换（历史结论，已修订）

上一版曾认为 `FollowObservation.vector` 在交给 Xbox 输出前需要从 native 坐标逆变换回
首帧小地图局部坐标；该结论现已被实机轴值证据推翻。路线规划仍必须在 canonical native
wall map 上进行，输入边界不得再次应用 registration 的旋转、镜像或比例；否则会把已经
转换完成的路线再转一次，人物会沿错误墙体方向移动并在门/墙前卡住。

通用 `inverse_transform_local_displacement()` 及 `native_map_vector_to_local()` 仍保留为
几何模块能力，但 PoE2 程序移动不再调用它们。`ProgramFollowOutput` 的页面装配和独立
路线探针改用 `native_route_vector_for_program_output()`，由 `ProgramGamepadOutput` 单独
应用 `POE2_MAP_TO_STICK_BASIS`。本节的旧“输入前逆 registration”描述仅用于保留排障历史，
不能作为当前实现契约。

### 2026-10-01 Qt 崩溃与实时页面稳定性排查

实机日志 `data/logs/poe2_live_terrain.log` 显示：双人首帧读取 1 次后接受，随后约
600 帧持续 `tracking`，没有恢复循环、内存读取风暴、Host lease 失败或 Python traceback。
Windows Application Error 事件明确记录 `pythonw.exe -> Qt6Gui.dll -> 0xc0000005`，因此本次
“退出/卡死”不能归因于双人配对失败。

已确认的可复现 Python 风险是 `frame_pixmap()` 直接把 NumPy 非连续视图交给 `QImage`；
`np.fliplr` 视图会触发 `BufferError: underlying buffer is not C-contiguous`，外层实时 tick
会因此停止；异常通道数若误套 BGR 格式还可能让 Qt 读取越行。现已在 Qt 边界先统一 `uint8` 与
C-contiguous，拒绝非 2D/3D、非 3/4 通道图像，再 `QImage.copy()` 脱离源缓冲区。
同时地图跟随跳过未改变的滚动目标，双人帧处理优先调用 `extract_combined_with_processed()`
复用预处理结果，实时日志增加截图、识别、跟踪和总耗时字段。

聚焦回归 `37 passed`，compileall 和 diff check 通过。Qt 原生访问冲突尚未再次实机复现；
下一次测试需保留 `dual_motion.timing` 和 Windows Application Error 时间点，若仍崩溃再沿 Qt
对象生命周期/关闭顺序继续取证，不能把此次 Python 边界修复误报为原生崩溃已彻底消失。

### 2026-10-01 地图点击目标即时显示与详细坐标记录

数据采集测试页的地图点击现在先显示目标，再决定是否进入跟随/程序移动流程。`ScalableMapWidget`
新增 `set_target()`，只更新红色十字目标，不会清掉双人人物、候选、轨迹或路线。点击信号携带的是
未缩放原图 `source_pixmap` 坐标；页面会按当前首帧 `SimilarityTransform2D` 逆变换得到 native 坐标，
做地图边界校验，再正向回投得到 display 坐标并计算 round-trip error。

每次点击都写入 `data/logs/poe2_live_terrain.log` 和页面侧栏日志：
`map_click.received`、`map_click.transformed`、`map_click.accepted`、`map_click.rejected`、
`map_click.cleared`。转换日志包含 source/native/display、模式、角度、水平镜像、比例、平移、
source size、native bounds 和闭环误差；越界或缺少定位上下文会记录明确拒绝原因。未启动跟随时点击
只显示目标并提示等待，不申请手柄租约、不发送输入；启动跟随后目标会在后续实时 overlay 重绘中保持，
停止跟随后清除。离线聚焦回归 `3 passed`，PoE2 页面/采集/地图集合 `31 passed`；本轮没有真实输入或 LAN 副作用。

### 2026-10-01 实机点击与程序移动日志复盘

本次实机日志 `data/logs/poe2_live_terrain.log`（约 21:01—21:14）显示：

- 双人首帧读取内存 1 次，两个 anchor 为 `(529.50,1088.50)`、`(523.50,1082.50)`；首帧 `accepted`，选择的注册为角度 `221°`、水平镜像、比例 `0.863`，两个 anchor error 约 `0.457`，best pair confidence `0.819`。
- 两次地图点击都完成 `map_click.transformed/accepted`，round-trip error 为 `0.0000`；目标 native 分别为约 `(654.19,1045.23)` 和 `(492.86,1102.00)`。日志中的 `map_size=(2784,2093)` 是 native 底图尺寸，旋转后的展示 pixmap 会扩大边界，因此点击 `y>2093` 本身不是越界错误。
- 两次程序移动都成功找到 PoE2 窗口、申请 controller 1，并写入非零左摇杆；随后均发送 neutral 并释放租约，没有 Host、窗口、Python traceback 或输入申请错误。
- 双人实时定位长时间保持 `tracking`、quality 约 `1.000`，只在 frame `1351/1352` 出现两帧 `wall_and_local_match_failed`，随后自动恢复，未触发 recovery 或再次读内存。

当前诊断缺口：`program_probe` 只记录 tick `1/8/16`，停止时没有把停止原因写入日志；`dual_motion.tick` 只记录可见身份和 quality，没有记录两个角色的 native before/after 位置。因此现有日志可以证明“输入链路已执行”，但还不能证明“人物在游戏内实际移动了多少、何时到达或是否被墙阻挡”。此外，30 FPS 定时器的 `dual_motion.timing` 样本平均约 `66.6ms`，绝大多数超过 `33ms`，峰值约 `298.4ms`，这是当前实时绘制偏慢的明确证据，但不是首帧匹配失败。

### 2026-10-01 Xbox 路线与坐标链诊断补充

复核后确认，实验页面的规划坐标契约是同一套 oriented reference/native 网格：地图点击先经展示逆变换得到目标，墙体、A*、碰撞、人物和到达判断都在这套坐标中；旧版本曾把路线向量按首帧 registration 逆变换到局部小地图方向再交给 PoE2 等距摇杆基底，现已确认这会重复旋转/镜像，是卡墙根因。

已修复 `tools/debug/poe2_route_probe.py` 中非零路径段向量计算被缩进到 `continue` 分支的问题。`ProgramGamepadOutput.diagnostics()` 现在保留最后输入向量、basis 后向量、轴值和 TTL；跟随 runtime 的观察结果标记 `coordinate_space=reference_native` 并带路线点数/端点；页面每 5 个 tick 记录当前点、目标点、距离、路线端点、native 向量和局部向量，停止时记录明确原因和 tick 数。上述改动只增加取证字段和探针修复，没有改变 Host 协议或自动发送门禁。

离线验证：PoE2 移动基底、跟随 runtime、Host 输出、页面移动实验共 `45 passed`，`compileall` 通过。下一次实机只需运行一个近距离无障碍目标和一个墙后目标，保留新的 `program_probe.motion`/`follow_experiment.motion` 与 `program_probe.stop` 日志，即可区分路径碰撞、方向映射、输入未生效和视觉位置过期。

### 2026-10-01 坐标边界修正：禁止路线向量二次注册变换

复盘上节的组合变换后发现，路线并不是“native -> local minimap -> stick”所需的输入：
地图点击、人物锚点、墙体、A* 路线、碰撞和到达判断已经全部处于同一套
`reference/native` 坐标。首帧 registration 的旋转、镜像和比例只负责把 source/display
坐标转换到该 canonical 坐标，不能在 Xbox 输出前再做一次逆变换。

实机日志形成了直接证据闭环：实例 `P2_7:54BE4D92` 的 registration 为 `221°`、镜像、
`scale=0.863`；旧链路把路线向量再次逆变换后，第一段输出约为 stick `(0.11, 0.81)`，
与 Host 轴值一致，但同一路线在 native 坐标直接投影到 PoE2 basis 应为约 `(0.59, -0.39)`。
因此人物沿错误方向移动并在墙边停住，根因是输入边界的二次旋转/镜像，不是首帧人物
坐标本身。

现已新增窄接口 `native_route_vector_for_program_output()`：它只校验 finite 二维向量并
原样返回；`ProgramFollowOutput` 的页面组装点和独立路线探针均改用该接口。唯一的
`reference/native -> Xbox stick` 投影仍由 `ProgramGamepadOutput` 应用
`POE2_MAP_TO_STICK_BASIS`。旧的 `native_map_vector_to_local()` 保留为通用几何逆变换，
不再用于 PoE2 程序移动。

新增回归覆盖 221°/镜像/0.863 的二次变换回归；移动基底、跟随 runtime 和采集页聚焦测试
共 `43 passed`。本轮没有重新发送真实输入。下一次实机应先做近距离无障碍目标，再做门/墙后
目标，同时保留 `program_probe.motion`、`program_probe.stop`、Host `last_command` 和
人物 native before/after；只有人物位移和路线绕障均成立后，才能宣称实机移动完成。

整套 `tests/poe2_live_terrain` 本轮结果为 `301 passed, 1 failed`：唯一失败是
`test_multiframe_shape_registration.py::test_huber_trim_reduces_outlier_error_without_hiding_raw_coverage`，
断言 trim 后 forward coverage 仍等于未 trim 值；本轮没有修改 shape registration、Huber
trim 或 coverage 实现，且移动聚焦测试均通过，暂按既有独立失败记录，不归因于路线输入修复。

### 2026-10-01 路线可视化与输入/距离取证

跟随实验和独立程序移动实验现在都会在小地图上绘制完整路线：起点是本 tick 的 native
人物位置，中间是 A* 路线点，终点是 native 目标；绘制前统一通过同一个
`localization_display_point()` 转成展示坐标。这样可以直接区分“路线本身错误”和“路线
正确但手柄输出方向/幅度不对”。目标十字仍独立显示，不会被路线覆盖。

每次运动日志新增 `route_length` 和 `route_detour_ratio`，同时保留 `distance`、
`vector_native`、`vector_input`；程序输出诊断新增 `input_magnitude`、`basis_magnitude`
和 `axis_magnitude`。当前 PoE2 基底系数为 0.5，单位 native 向量经过等距投影后轴幅度约
为 `0.707`，这属于已记录的幅度校准事实，尚未直接改成满幅输出，需先结合路线可视化和
实机人物 before/after 位移确认是否为用户所说的距离不匹配。

聚焦回归当前为 `48 passed`，compileall 和 diff check 通过。本轮没有发送真实输入。

### 2026-10-01 移动测试完整日志边界

移动实验日志现覆盖以下边界：

- `map_click.received/transformed/accepted/rejected`：原始展示坐标、native 目标、回投坐标、
  round-trip error、角度/镜像/比例/平移、地图边界和墙体像素数；另有 `target_context`
  记录当前人物和测试角色。
- `program_probe.plan_context` / `follow_experiment.target_context`：地图实例、角色、起点、
  目标、墙图尺寸、墙体像素、寻路参数和变换参数。
- `program_probe.motion` / `follow_experiment.motion`：每帧（程序探针）或每 5 tick（跟随）
  的 native 当前点、目标点、直线距离、路线长度、绕路比例、路线端点、路线向量、输入向量、
  路线链段碰撞数、路线是否可行、A* 尝试倍率和最终倍率、视觉帧年龄。
- `program_probe.*diagnostics`：Host 租约、控制器状态、输入/基底/轴幅度、轴值和 TTL。
- `program_probe.stop_summary` / `program_probe.stop`：停止原因、tick 数、总时长、初始/最终
  native 位置、native 位移、目标、最终距离/状态/原因；释放前另记录 Host 最终状态。

这样可以把一次失败明确归类为：点击坐标错、路线规划失败、路线穿墙、视觉帧过期、摇杆方向
错误、摇杆幅度不足、Host 租约问题或人物实际没有位移，而不再只看到“移动失败”。

### 2026-10-02 双人首帧评分与闭环路线安全修复

本轮按实机证据拆开处理四类问题。双人首帧的内存锚点和两人相对几何已经可以精确解释候选，
但旧公式把单帧墙体覆盖率作为 65% 的总置信度，导致覆盖率 0.45–0.60 的有效首帧被拒绝。
`DualFirstFrameRegistrar` 现在分别计算 `anchor_quality`、`pair_confidence`、`shape_quality`
和 `profile_consistency`，总分为 `0.45/0.25/0.20/0.10` 加权；候选身份的 anchor error、
assignment margin、midpoint 独立误差门仍保留，所以不是简单降低阈值。新增低覆盖精确锚点回归，
实际 90% 准确率仍需真实双人真值样本统计后才能宣称。

通用 `PathFinder` 新增可选 `build_clearance_cost_map()`：基于障碍距离变换给靠墙网格增加软代价，
同时保留 `safety_margin` 的实体安全膨胀；A* 仍拒绝 diagonal corner cutting。PoE2 实验跟随和
程序移动启用 `safety_margin=8`、`clearance_radius=20`、`clearance_weight=2`，并继续在原始墙图上
逐段复核，窄通道会优先被安全膨胀排除，仍无安全路线才返回 `BLOCKED`。

跟随 runtime 增加闭环 progress watchdog：每个角色保存最近距离、位置和无进度 tick。位置帧新鲜但
连续 3 tick 距离和位移都没有下降时，先尝试左右交替的侧向恢复 waypoint；恢复路线不可行才清空
路线并进入冷却。相同路线的静态逐段碰撞校验由 `VectorPathTracker` 缓存，减少 30 FPS 高频 tick
的重复扫描。`FollowObservation.diagnostics` 新增 `route_safety_margin`、`route_clearance_radius`、
`route_clearance_weight`、`no_progress_ticks`、`recovery_attempts` 和 `recovery_target`。

本轮离线聚焦回归为 `307 passed`，包含双人低 coverage、clearance 代价和 stalled recovery；
未发送新的真实手柄输入，故仍不能把手柄方向/幅度校准或 90% 实机首帧准确率写成已验证结果。

### 2026-10-02 双人首帧与闭环导航补充

双人颜色候选现在先做 bbox IoU/中心距离去重，避免同一人物的轮廓和核心占掉两个候选名额；
不同位置的近距离人物仍交给双人注册器配对。程序移动每个控制 tick 回写的是最后真实视觉帧的
采集时间，视觉停止刷新时会按照 `position_ttl_ms` 进入停止保护，不会把旧位置伪装成新鲜位置。
多尺度路线在硬碰撞与最小清距都通过后，按 `route_length + clearance_weight * exposure` 选择
候选，并记录 `plan_selected_route_score`。

形状注册缓存现在持有参考数组本身，避免 NumPy 内存地址复用后跨地图复用旧距离场；这类错误会
表现为方向、coverage 和首帧接受结果随机变化。聚焦回归为 `69 passed`。以上均为离线验证，
尚未证明真实双人首帧达到 90%，也未证明真实手柄已绕墙或从卡墙状态恢复。

实机复核顺序：双人分开、靠近、重叠各采集多次并保存 `anchor_error`、`assignment_margin`、
`shape_quality`、方向和 scale；然后做无障碍、贴墙、窄门、门后四个短距离目标，观察路线
clearance、`vector_input`、Host axes、视觉帧年龄、`no_progress_ticks` 和 native 位移。

跟随 runtime 现在参考项目中稳定的 bounded local-replanning 做法：目标只在离开 16 native px
（或 `2 * arrival_radius`）刷新带、人物偏离当前路线超过 12 native px、路线碰撞校验失效或
卡墙恢复时触发 A*；小幅目标运动复用原安全路线。日志中的 `planned_target`、
`route_target_shift`、`route_deviation` 和 `plan_selected_route_score` 用于区分路线复用、
局部重规划和实际输入无效。该优化减少连续跟随时的 A* 重复计算，但仍需实机确认视觉位置和
手柄输出的闭环速度。

### 2026-10-02 采样周期、首帧候选与角色碰撞半径

排查发现实验页原先所有定位 timer 都直接使用 legacy sample_interval_ms；默认 100 ms 会把配置的
30 FPS 实际限制为约 10 FPS。现在双人实时、hybrid 和多帧定位使用 localization_fps 计算有效周期，
preview 和截图窗口使用 preview_fps，sample_interval_ms 只作为兼容上限。

双人首帧仍只读取一次 memory anchors，但会在短间隔内保留最多三张截图，对每张分别调用注册器，
按 accepted、pair confidence、shape quality 和 mean anchor error 选择最强候选，避免第一张过渡帧
造成随机拒绝；所有候选失败仍 fail closed。

跟随 runtime 新增 footprint_radius。PoE2 实验页当前使用 6 native px，并生成只读膨胀碰撞图；A*、
VectorPathTracker、模拟步进和路线诊断共用该图，原始 wall map 继续只用于 clearance 证据。它能拒绝
中心线虽然可走、但角色实体会擦墙的窄门。该半径仍需按真实角色和门宽实测调整。

离线聚焦回归为 43 passed；仍未实机确认双人首帧 90% 准确率、手柄方向/幅度、贴墙恢复和门后路线。
下一阶段参考 Nav2 Regulated Pure Pursuit、DWB/DWA、TEB 的短视窗碰撞检查、速度调节和振荡抑制，先
在 offline runtime 验证，再接入真实输出；实验页截图/识别还需要 bounded latest-frame worker，避免
处理超过 30 FPS 周期时消费旧帧。

### 2026-10-02 局部闭环控制与双人候选恢复

本轮完成了可以离线验证的两项补强。全局 A* 路线仍负责拓扑和角色碰撞半径；新增通用
`core.routing.local_controller.LocalMotionController` 在每个控制 tick 评估有限角度的短轨迹，
以目标进度、clearance、路线偏离、转向变化和观察到的 native 速度评分。runtime 从连续视觉样本
计算平滑速度，速度过高时降低命令幅度，未来短窗碰撞时切换侧向候选；所有候选被墙体拒绝时交给
既有的左右交替恢复逻辑。PoE2 实验页显式使用 8 tick 卡墙阈值、24 native px lookahead、0.25 s
prediction horizon，并把局部控制诊断写入运动日志。

双人首帧的颜色候选 NMS 现在区分 profile/identity hint，不会把不同颜色的近距离玩家合并；注册器
允许额外候选，过滤低置信轮廓后枚举所有有序两人组合，正式页面最多提供 6 个候选，避免噪声轮廓
占据前两个名额。新增 profile 近距离和局部绕障回归。

本轮验证：双人首帧/跟随聚焦 41 passed，导航/页面/手柄相关回归 46 passed，`compileall` 通过。
真实双人 90% 首帧率、手柄方向/速度、窄门与门后路线仍必须用实机样本确认；本轮没有发送真实输入。
## 2026-10-02 导航/双人实时稳定性续审

本轮没有宣称实机 90% 或真实手柄通过，只完成了可离线验证的稳定性边界：

- 路径网格尺寸现在向上取整，地图宽高不能整除 downsample factor 时不会丢失边界格。
- 跟随 runtime 继续使用角色 footprint 膨胀、A* 清距软代价、原图逐段清距复核和 DWA 风格局部短视窗；新增上一周期 native command 与下一可信视觉位移的 cosine/夹角诊断。连续三次低于 0.20 会进入既有左右交替恢复，日志字段为 `command_observed_alignment`、`command_observed_angle_degrees`、`direction_mismatch_ticks`。
- 双人实时实验页的生产 profile 已使用 `Poe2DualMotionWorker`。截图、墙体/颜色识别和 `DualVisualTracker.tick()` 在 worker 中处理；Qt 只消费 latest-only 结果，旧帧替换而不排队。日志追加 capture/recognition/tracking 分段耗时、完成帧和 dropped 结果。首帧和恢复注册仍在 GUI 线程，后续单独迁移。

验证：PathFinder、双人跟随、采集页和 worker latest-only 聚焦回归 `64 passed`，`compileall` 通过；未发送真实手柄、鼠标、键盘或 LAN 输入。

实机验收仍必须按顺序记录：双人分开/靠近/重叠首帧真值；开阔/贴墙/窄门/门后路线；`vector_native -> vector_input -> Host axes -> native before/after`；视觉年龄、方向夹角、无进度和恢复次数。只有独立真值统计达到目标后，才能把首帧准确率写成 90%+。

### 2026-10-02 实验路径人物碰撞半径调整

根据实验反馈，PoE2 数据采集页和程序移动探针的显式 `footprint_radius` 从 6.0 调整为
2.0 native px。该值只影响实验页生成的角色碰撞膨胀图；`minimum_clearance=6.0`、
`clearance_radius=20.0`、`safety_margin=2` 和 `arrival_radius=8.0` 保持不变，分别继续表示
最低路线清距、软清距惩罚带、粗网格余量和到达判定距离。底层 runtime 的默认
`footprint_radius=0.0` 以及单元测试专用值未修改。

聚焦回归：PoE2 采集页与双人跟随 runtime `57 passed`。2.0 仍是实验起点，需用无障碍、贴墙、
窄门和门后路线实测确认是否过小；观察 `route_footprint_radius`、路线最小清距、碰撞段和实际
native 位移后再决定最终值。

### 2026-10-02 自适应运动闭环实现与审查

已在 `experimental/multiplayer_follow/` 内完成一版可离线验证的运动闭环组合，运行时按一份
冻结的 `MotionSnapshot` 协同复杂度、状态估计、路线和输入校准模块：

- `LocalComplexityClassifier` 以清距、视线、可行走比例、未知区域、路线曲率/转向、定位质量、
  输入残差和双人距离风险计算 OPEN/TRANSITION/CONSTRAINED/UNKNOWN；迟滞状态按 role 独立，
  不会让 P1 的狭窄区域污染 P2。
- `SequentialMotionEstimator` 将视觉/native 位移作为观测，将上一条命令作为预测；
  `AdaptiveInputCalibrator` 按 role 保存有界 stick→native 模型，只接受方向、位移和地图版本有效的反馈。
- `ClosedLoopMotionController` 在开阔区使用 regulated pursuit，在过渡/受限区复用现有
  `LocalMotionController` 的短视窗候选，未知或过期帧输出 neutral；PoE2 页面仍显式采用
  `footprint_radius=2.0`，不改变绘图模式。
- `SimulatedFollowRuntime` 将真实视觉采集时间传入 `frame_age_ms`，过期帧在闭环层停止；
  `ProgramFollowOutput` 优先采用闭环命令的 `command_duration_ms`，UI timer 只负责调度。

新增 `tests/poe2_live_terrain/test_motion_loop_replay.py`，覆盖开阔区到达、门洞路线无碰撞和过期帧
失败保护。当前离线聚焦回归为 `374 passed`，全仓回归为 `926 passed, 1 skipped, 10 subtests passed`；
本轮未发送真实手柄、键鼠或 LAN 输入。实机仍需
按开阔、贴墙、窄门、门后顺序验证 `native before/after`、方向夹角、速度比和恢复次数，不能把
离线通过等同为真实移动已验证。

### 2026-10-02 移动失败根因复盘与清距回退

实机日志确认了两个独立问题：旧运行进程仍打印 `footprint_radius=6.0`，而当前实验页代码已经是
`2.0`；同时闭环控制器原本会被 UI tick 间隔覆盖，实测出现 `command_duration_ms=667`，导致人物
超过路线目标后贴墙。闭环命令现在保留控制器自己的约 `160–300 ms` 脉冲，只有 legacy 控制器才使用
tick 间隔。

针对同一地图离线复现的 `start=(485.554,1160.694)`、`target=(587.190,1191.154)`，严格清距
`6.0` 会拒绝所有候选，但碰撞膨胀图显示路线没有实体碰撞，原始路线最小清距约 `3.69`。runtime
现在先选严格路线；仅当显式设置了角色 `footprint_radius` 且严格候选为空时，才允许清距不低于
`max(footprint_radius+0.5, 2.0)` 的 physically-safe 回退，并记录 `selected_clearance_mode=relaxed_clearance`、
`relaxed_candidate_route_count` 和每个倍率的 `relaxed_reason`。没有角色半径的通用调用仍保持严格拒绝。

页面 `program_probe.motion` 和 `follow_experiment.motion` 已同时打印起点/目标清距、候选拒绝、严格/回退
候选数、选中的清距模式、路线最小清距、输入脉冲时长、视觉年龄和方向失配。聚焦回归 `64 passed`，
全仓回归 `929 passed, 1 skipped, 10 subtests passed`，`compileall` 与 `git diff --check` 通过。
本轮没有发送新的真实输入；下一次实机必须重启程序，确认日志中的 `footprint_radius=2.0`，先测开阔短距，
再测贴墙/窄门，并保留 `program_probe.plan_context`、`program_probe.motion`、`program_probe.stop_summary`。

### 2026-10-02 本次真实目标离线回放

本次失败日志对应地图 `P2_7:54BE4D92`，人物起点为 `(528.754,1166.560)`，点击目标为
`(615.176,1209.302)`。旧运行结果为 `no_safe_route`，但把相同 `latest.npz`、起终点和
`footprint_radius=2.0` 输入 runtime 后，碰撞膨胀图全程可走；严格清距候选为空时，回退路线为
`(530,1166) -> (582,1194) -> (615.176,1209.302)`，最低墙距 `2.739`，因此已确认原失败是
回退清距阈值 `3.0` 过高，而不是目标坐标或地图旋转错误。阈值现为 `max(radius+0.5,2.0)`。

同一日志还暴露了两个取证问题：`program_probe.plan_context` 的人物半径字段曾硬编码打印 `6.0`
（runtime 实际为 `2.0`），已修正；`SquareScreenCapture.__del__` 在 mss 跨线程销毁时可能抛出
thread-local `bmp` 异常，现改为幂等且吞掉释放阶段异常，避免关闭/恢复过程退出工作台。

双人实时 worker 停止时现在会先发出 stop，再等待后台截图线程退出；若超过 1 秒只记录
`dual_motion.worker_stop_timeout`，不销毁仍在运行的后台对象，减少页面关闭/恢复时的线程竞态。

全仓回归仍为 `929 passed, 1 skipped, 10 subtests passed`。后续实机复测应确认新的
`plan_context` 和 `motion` 都显示 `footprint_radius=2.0`、`selected_clearance_mode=relaxed_clearance`。

### 2026-10-02 真实样本离线探针复核（当前断点）

已将 `tools/debug/poe2_route_probe.py` 增加为纯离线模式。命令：

```powershell
D:\ACloud\.venv\Scripts\python.exe tools\debug\poe2_route_probe.py --offline `
  --start-x 528.7535744729821 --start-y 1166.5596351994875 `
  --target-x 615.17576722695 --target-y 1209.302369075398
```

该模式只加载 `data/poe2_live_terrain_test/latest.npz`，不会读取游戏进程、申请管理员权限或发送
手柄输入。当前样本 `P2_7:54BE4D92` 输出 `route_available=true`，路点为
`(530,1166) -> (582,1194) -> (615.176,1209.302)`，碰撞段为 0，选中
`factor=4 / relaxed_clearance`，最小墙距 `2.739`。探针的实机模式也已与页面统一为
`safety_margin=2`、`minimum_clearance=4`、`footprint_radius=2`，避免调试入口继续使用旧参数产生
`no_safe_route` 假失败。

本次日志中的 Python traceback 主要是“游戏进程变化/内存布局未解析/测试替身主动抛错”等已被页面捕获的
业务错误，并非路径算法崩溃；关闭阶段的 mss thread-local 释放风险和双人后台线程竞态已分别由
`SquareScreenCapture.close()` 幂等保护及 `Poe2DualMotionWorker.wait()` 有界等待处理。真实手柄方向、
速度和游戏进程更新后的指纹仍需重启后实机确认，离线通过不能替代实机验收。

### 2026-10-02 实验清距参数放宽

根据本次离线样本复核，PoE2 实验页和路线探针的首选 `minimum_clearance` 从 `6.0` 调整为
`4.0`；严格候选仍会优先使用。只有严格候选不存在时才进入回退，回退硬下限调整为
`max(footprint_radius, 2.0)`，当前人物半径为 `2.0`。碰撞膨胀图仍是硬约束，路线不能穿过人物实体
占用区域；这次调整只减少额外墙距偏好导致的误拒绝，不改变通用 PathFinder 默认值。

### 2026-10-02 PoE2 窄通道采用中心线碰撞策略

根据窄门实测反馈，PoE2 实验页不再启用人物 footprint 的墙体膨胀，也不再向 PathFinder 注入额外
`safety_margin`。实验参数现在是 `inflate_collision=False`、`footprint_radius=0.0`、
`safety_margin=0`、`minimum_clearance=0.0`；A* 和路线逐段检查使用原始中心线墙体图，软清距代价仍
会优先选择开阔路线，但不会为了偏好清距封死真实窄口。

人物移动过程由 `LocalMotionController` 在短预测窗口内检查候选方向。目标方向被墙体挡住时，会在
候选角度中选择左、右或斜向的无碰撞方向；连续视觉位置没有产生位移时，再由 runtime 的侧向恢复
逻辑处理。新增 `inflate_collision` 只控制实验 runtime 的碰撞图构造，通用 runtime 默认仍保持原有
膨胀能力。当前真实样本离线回放得到 `(529,1167) -> (615.176,1209.302)`，碰撞段为 0。

### 2026-10-02 双人实时定位崩溃排查与线程资源闭环

Windows WER 把工作台的故障分为两类：`pythonw.exe / ntdll.dll / 0xc0000374` 堆损坏，及
`pythonw.exe / Qt6Gui.dll / 0xc0000005` 原生访问冲突。日志对照显示，前者发生在双人实时截图线程连续
运行期间，后者发生在停止或切换后；PoE2 自身的 `PathOfExile.exe` 崩溃是独立事件。业务异常和定位失败
均被页面捕获，不能解释这两类 native 崩溃。

本轮修复了双人 worker 的资源边界：`Poe2DualMotionWorker` 接收线程本地 capture cleanup，并在其
`finally` 中、仍处于截图线程时释放 MSS；页面停止时先发 stop，再等待最多 3 秒，超时 worker 保留在
退休列表中直到 finished 信号到达，避免页面/Qt 对象先销毁而后台仍访问 native 资源。双人 worker 还会
复制 HSV recognizer 参数，避免 GUI 和 capture 线程共享 CLAHE 等 native 状态；结果派发增加渲染异常边界，
预览更新限制为最多 12 FPS。`presenter` 的旋转图像转换改为持有命名的 contiguous NumPy owner，直到
`QImage.copy()` 完成，彻底避免 Qt6Gui 借用临时 buffer。

验证：双人 worker、PoE2 页面和 presenter 聚焦测试 `386 passed`，新增 cleanup 线程归属测试通过，
`compileall` 与 `git diff --check` 通过。WER 转储属于历史证据，当前环境没有可用的命令行 dump
符号器，因此还需要重启程序后做一次真实的双人实时定位/停止循环，确认不再生成新的 `pythonw.exe` 崩溃。

### 2026-10-02 门后提前停止与单人 worker 生命周期修复

最新一次实测可以通过窄门，但在距离目标约 `58.3` native 单位时进入
`stalled_no_escape`。离线使用同一地图 `P2_7:54BE4D92`、起点
`(559.6648703,1183.0890744)`、目标 `(607.2905711,1216.7751075)` 复核，A* 路线仍可用，
因此根因是旧恢复状态机只尝试一个固定侧向点；该点无路时把“局部恢复失败”错误升级成“目标不可达”。

当前 runtime 在卡墙触发后按以下顺序处理：

1. 先以当前位置到真实目标重新规划并尝试输出；
2. 若直接方向仍被局部控制器拒绝，依次尝试多组短距离左右/前向恢复点；
3. 只有全部候选都没有安全路线或没有可用输出时，才返回 `stalled_no_escape`。

诊断新增 `recovery_candidates_checked` 和 `recovery_selected_index`；实验页的
`program_probe.motion` 已记录这些字段，便于区分“重新规划继续移动”和“所有恢复候选失败”。
同一离线回放现在在重复无位移帧下返回 `stalled_replanned`，不会提前进入 blocked。

另外，正式单人 `Poe2LocalizationWorker` 停止路径已补齐：停止时最多等待 3 秒，超时 worker 进入退休列表并
保留到自身 `finished` 信号到达；新的监控启动会阻止与退休 worker 并发使用截图/runtime，页面 shutdown 在仍有后台
worker 时不释放 runtime。这样与双人 worker 的资源生命周期策略一致，降低 `pythonw.exe`/Qt native 崩溃风险。

验证：`tests/poe2_live_terrain/test_multiplayer_follow_runtime.py` 为 `43 passed`；
`tests/test_poe2_live_terrain_monitoring.py tests/test_poe2_localization_worker.py` 为 `6 passed`；
离线路线探针确认 `route_available=true`。本轮没有发送新的真实手柄输入，仍需用户重启后实机确认门后继续移动和 WER 是否不再产生新崩溃。

### 2026-10-02 墙边坐标栅格量化修复（当前断点）

本次“通过门后仍有距离就停”的真实样本已确认不是到达半径：人物到目标仍为 `42.5996` native，
最终原因是 `no_safe_route/stalled_no_escape`。同一帧内存人物坐标为 `(575.748,1178.894)`，
native terrain 栅格按四舍五入落到 `(576,1179)`；该格在 `latest.npz` 中是 `wall=255`，紧邻的
`(576,1180)` 是 `wall=0`。这表示连续人物坐标与离散墙体栅格在边界处不一致，不能据此认定内存人物坐标错误。

PoE2 实验 runtime 现在在首个规划前、以及后续仍处于墙格的视觉帧中，搜索半径 `12` native 内能安全到达
目标的可行走起点，输出 `0.25–0.45` 归一化、`120 ms` 上限的 `wall_start_recovery` 脉冲；人物真实观测位置
不会被改写。相同边界帧复用恢复路线，人物进入可行走格后才交给局部控制器，避免每帧重新跑多级 A*。

日志新增：

- `observed_position_metrics`：内存/视觉人物真实观测格（本样本 `collision=255`）；
- `planning_route_walkable` / `planning_route_collision_segments`：从临时可行走起点开始的路线安全性；
- `local_controller.reason=wall_start_recovery`、`escape_origin`、`escape_distance`。

离线命令已用同一真实样本验证：

```powershell
D:\ACloud\.venv\Scripts\python.exe tools\debug\poe2_route_probe.py --offline `
  --start-x 575.748 --start-y 1178.8943 `
  --target-x 604.3627 --target-y 1210.4526
```

结果为 `route_available=true`、`reason=wall_start_recovery`、恢复起点 `(576,1180)`、非零向量；
跟随 runtime 聚焦回归为 `45 passed`，运动闭环相关聚焦集合为 `48 passed`。本轮未发送新的真实输入，
实机需重启程序后确认人物在墙边继续移动，并保留 `observed_position_metrics` 和
`planning_route_walkable` 日志。
## 2026-10-02 卡墙闭环修复断点

本阶段确认的故障链是：程序输出非零 native 向量 → native 大地图路线仍判定为可走 → 双人视觉状态没有把同帧小地图 wall mask 交给跟随 runtime → 人物实际贴墙但没有有效位移 → 旧逻辑只等 stalled/30 秒保护。因此“路线可走”不能继续作为“人物正在移动”的替代证据。

已完成的实验层实现：

- `core/routing/contact_evidence.py` 提供坐标无关的 `ContactMonitor`/`ContactEvidence`。它比较上一条命令和下一条可信视觉位移，计算 alignment、连续无进展次数和恢复门；默认命令阈值 `0.20`、位移阈值 `0.25 native`、连续 `2` 个样本。
- `features/poe2/live_terrain/experimental/multiplayer_localization/minimap_contact_adapter.py` 提供 `inspect_minimap_contact()`。输入已有 wall mask、人物屏幕坐标和 native→screen 的局部命令方向，沿 `6/10/14 px` 前方束采样，并返回 `wall_ahead`、首个墙距、左右 free score；它不做人物 mask，也不修改墙体。
- `SimulatedFollowRuntime.update_local_contact()` 只保存适配器证据。`update_follower_position()` 生成命令—位移接触证据；`_tick_follower()` 在“局部前方有墙 + 连续无进展”时跳过旧 global route，按左右清空度优先选择局部脱困 waypoint，输出 `contact_recovery`。两次局部恢复仍无进展时输出 `contact_relocalization_required`。
- `Poe2CaptureTestPage` 保存 worker/同步采样的最新 raw/combined 帧；程序移动 tick 在下一次控制周期把上一次输出经 `inverse_transform_local_displacement()` 转回小地图方向，调用 PoE2 接触适配器，并把接触字段写入 `program_probe.motion` 日志。收到 `contact_relocalization_required` 后先中性释放/停止输入，再复用现有双人恢复入口；不会等 30 秒超时。

当前安全边界：`inflate_collision=False`、`footprint_radius=0`、`safety_margin=0`、`minimum_clearance=0` 保持不变；局部墙体证据只用于纠偏和恢复，不引入人物面积膨胀，也不改变绘图模式。尚未完成实机验收：需要记录同一帧的 `program_probe.local_contact`、`program_probe.motion.contact_evidence`、`wall_ahead`、`observed_displacement` 和状态转换，确认贴墙时先出现 `contact_recovery`，局部恢复失败才出现 `contact_relocalization_required`。

### 2026-10-02 墙角接触恢复优先级修复（当前断点）

两次实机日志的共同现象是：Host 已获取 lease 且持续发送非零摇杆值，内存人物坐标完全不变；
`local_obstacle_ahead=true`、`contact_evidence.consecutive_no_progress` 持续增长，但每个 tick 都返回同一条
`wall_start_recovery`，恢复起点与真实人物相距约 `0.85 native`，`recovery_attempts` 一直为 `0`。
因此旧的墙边起点微脉冲分支覆盖了接触恢复分支，后者永远无法执行；这不是 Host、权限或输入 lease 失败。

本轮修复：

- 当接触证据已经达到恢复门时，跳过顶部的缓存 `wall_start_recovery` 微脉冲；
- 对仍落在墙体栅格的观测点，新增 `_contact_recovery_command()`：按小地图左右空闲度在半径 `12 native`
  内寻找可行走起点，从该起点规划到真实目标，再只输出一次有界侧向脱困向量；不修改真实观测位置，
  不启用人物 footprint 膨胀；
- 如果两次局部脱困仍没有可信位移，保持既有 `contact_relocalization_required` 安全停止和重定位入口；
- 新增回归测试覆盖“先 wall_start，再确认小地图接触后必须转为 contact_recovery”的真实故障顺序。

验证：跟随 runtime 聚焦测试 `47 passed`；接触证据、采集页及 PoE2 实验集合 `387 passed`，
`compileall` 通过。实机复测时应在日志中看到 `wall_start_recovery` → `contact_recovery`；若两次恢复仍无位移，
才允许出现 `contact_relocalization_required`，不应再无限重复同一个 `wall_start_recovery` 向量。

### 2026-10-02 大位移被误判为连续撞墙（已修复）

最新实机记录（`P2_7:54BE4D92`）显示，人物从 `(513.771,1153.771)` 移动到
`(514.259,1145.056)`，实际位移 `8.729 native`；这两个点及周边区域在 `latest.npz` 的
`wall_layer` 中均为 `0`，当前位置 clearance 约 `25 native`，因此不是墙体过厚、人物半径过大或碰撞膨胀。

原接触规则把“命令—位移夹角小于阈值”也算作 `no_progress`。本次第 5 tick 的位移明显来自前一条
仍在生效的纵向摇杆命令，而上一 tick 刚切换到横向恢复命令，夹角约 `97°`；该时序错位让真实位移被
错误升级为 `contact_relocalization_required`。

当前规则改为：只有命令非零且观测位移低于 `0.25 native` 才能累积撞墙证据；方向夹角继续记录为
`command_observed_alignment`/`command_observed_angle_degrees`，用于输入基底校准，但不再单独证明人物卡墙。
当小地图已报告墙体、人物却有明显位移时，方向不一致也不会触发墙体重定位；只有重新出现连续无位移，
才会进入局部恢复。新增回归覆盖大位移正交运动，避免延迟输入再次触发假撞墙。
## [CURRENT] 2026-10-03 — 连续撞墙防抖与双人重定位续跑（当前断点）

### 已确认的问题

最新实机日志中，角色已经从起点移动约 `20.52 native` 并通过门；停止前小地图持续给出
`wall_ahead=True / wall_distance=6.0`，但接触监视器只累计了 `consecutive_no_progress=2` 就发布
`contact_relocalization_required`。这两帧不能证明人物已被墙体占用，只能证明输入方向在当前短窗口没有产生足够位移。

原页面收到该信号后释放程序输出并调用双人恢复入口，但 `_start_dual_motion(recovery=True)` 复用了已经接受的
`_last_dual_first_frame_result`，所以没有重新读双人内存锚点，也没有保留点击目标来续跑。

### 当前实现

- `SimulatedFollowRuntime` 新增 `contact_required_samples`，每个 follower 在 `add_follower()` 时拥有独立
  `ContactMonitor`。通用默认值仍是 `2`，PoE2 数据采集页的跟随和程序移动实验显式使用 `4`，即连续四个有效
  无进展样本才允许升级为重定位。
- 程序移动触发重定位时先保存 `target_native`、角色 identity、控制器和 recovery attempt，再中性释放旧 lease。
  10 秒内重复触发只进入冷却停止，避免内存读取循环。
- `_start_dual_motion(recovery=True)` 强制调用
  `run_dual_first_frame_experiment(render_map=False, force_memory_read=True)`，完成一次新的双人内存读取和当前
  小地图首帧几何配准；普通启动继续复用已接受首帧。
- worker 或同步定位收到新的、非 recovery、未过期 tracking 帧后，`_maybe_resume_program_probe_after_relocalization()`
  恢复原角色/控制器选择，自动以原 `target_native` 重新建立程序移动输出。重定位失败则清理上下文并保持安全停止，
  不循环读取或偷偷发送输入。

### 新日志与验收顺序

应看到：

```text
program_probe.local_contact
program_probe.relocalization_requested
program_probe.relocalization_context_saved
program_probe.relocalization_started
dual_first_frame.memory_success          # recovery 新增一次 read_count
program_probe.relocalization_registration_success
program_probe.relocalization_resumed
```

验收时确认原点击目标继续执行，且 `memory_success` 只增加一次。若重定位失败，应看到
`program_probe.relocalization_failed`，程序输入保持中性并等待人工重新启动。

验证：接触证据、双人跟随 runtime、PoE2 采集页共 `75 passed`，`compileall` 与 `git diff --check` 通过。
本断点之后需要实机短路径穿门测试；优先核对同一 `captured_at_ms` 下的接触证据和位移，不再直接调大人物半径或墙体膨胀。

### 2026-10-03 局部接触语义与脱离状态修复（当前断点）

本轮确认的根因不是窄道特殊参数，而是原始小地图射线、当前方向阻断、真实接触和脱离接触被压成了一个布尔值。人物通过障碍后，旧接触证据可能在短暂视觉量化停顿中继续生效，导致再次请求重定位。

当前实现：

- 小地图适配器同时保留 `wall_ahead` 原始射线诊断和 `blocking_wall_ahead` 中心线阻断语义；中心线仍可通行但 beam 碰到侧墙时标记 `narrow_passage=True`，不再把它直接当成碰撞。
- 通用 `ContactMonitor` 新增 `CLEAR`、`APPROACHING`、`CONTACT_CANDIDATE`、`RECOVERY`、`ESCAPED` 状态；有效位移或路线进展会清空连续无进展计数。
- 有出口时仍保留真实接触证据，但 runtime 继续执行局部脱困；只有没有出口且多次局部恢复失败时才允许全局重定位。开放中心线观测不会复用旧的恢复标记。
- PoE2 日志新增原始射线、中心线距离、阻断语义、窄道标记和接触状态，便于区分“靠墙”与“真的卡住”。

验证：小地图适配器 `4 passed`、接触证据 `6 passed`、双人跟随 runtime `51 passed`；相关集合当前 `61 passed`，尚未重新发送真实输入。下一次实机先观察 `raw_wall_ahead` 与 `blocking_wall_ahead` 是否分离，确认人物产生位移后接触状态进入 `escaped/clear`，并确认有出口时持续执行局部脱困而不是重定位。

### 2026-10-03 `wall_start_recovery` 生命周期修复（当前断点）

最新实机日志补充确认：即使小地图的 `local_obstacle_ahead=False`、左右都有可行空间，runtime 仍持续返回
`wall_start_recovery`；原因是墙边恢复缓存每个 tick 都把 `wall_recovery_position` 更新为当前位置，且顶部早期返回先于无进展监视，导致同一微量向量可无限重复。另一次 `program_probe.write_failed` 的真实错误是 Host lease 已过期，属于输入会话边界错误，不是路径规划成功的证据。

本轮实现：

- 墙边恢复位置固定为本次恢复 episode 的起点，不再每 tick 滚动更新；单个 episode 最多发出 3 个有界墙边脉冲，之后让位给 stalled/contact recovery，避免二十多秒重复 `wall_start_recovery`。
- 最新小地图确认中心线开放时，不再新建墙边微脉冲；若此前确实已进入墙格恢复，则最多允许有限的 `stale_wall_raster_recovery` 过渡脉冲，随后回到普通恢复链路。该状态表示“native 栅格滞后于实时小地图”，不是新增墙体判定。
- 新增 runtime 回归：开放小地图不能被旧墙格缓存困住；人物位置长期不变时墙边恢复必须有界。跟随 runtime 聚焦测试当前 `53 passed`。

实机验收关注：日志应从 `wall_start_recovery`（最多三次）转为 `stale_wall_raster_recovery`/`contact_recovery`/`stalled_recovery`，不能无限重复；若仍无位移，才允许进入一次重定位。Host 的 `Program session expired` 仍应记录为会话过期并安全停止，不能隐式重新取得租约。

## 2026-10-03 完整链路复审断点

本轮没有修改业务源代码，也没有发送真实输入；离线相关回归为 `366 passed`。从初始化、双人首帧、实时 worker、坐标转换、点击目标、路线规划、手柄输出、接触恢复到停止清理，新增确认以下待处理风险：

1. 双人 marker 单帧缺失/重叠时，tracker 返回 `tracking/degraded`，但程序移动页在选中角色为 `None` 时立即释放输入；需要页面级短时中性等待和连续失败门，不能把非终态视觉状态当作终态停止。
2. tracker 自己触发 recovery 时，页面没有统一保存 follow 点击目标；`stop_dual_motion()` 会清理 follow runtime/目标。程序接触恢复分支已有上下文保存，但视觉 recovery 分支没有同等保护。
3. worker 的一次截图/识别/OpenCV 异常会结束整个实时线程；clone recognizer 失败还会把 GUI recognizer 交给 worker。停止超时后又可能在旧 worker 未结束时创建新 worker，共享同一截图后端。
4. 实时双人纠偏 frame 的 `local_player` 仍固定为截图中心；首帧 registrar 使用角色 marker，但后续局部 matcher 没有明确复用该锚点。双人偏心视口需要专门的共享视口锚点契约。
5. 内存双人身份由 metadata+entity vector index 生成，实体重排可能导致 recovery 后角色选择失配；正常视觉 tick 也没有低频 area instance 变化探针。
6. 局部接触采集的异常类型覆盖不足，OpenCV/shape/stride 异常会被外层误标成手柄写入失败并停止。

已确认的边界：点击地图的显示坐标到 native 目标的逆变换有 round-trip 日志和测试；`ProgramFollowOutput` 的正常停止顺序是先发中性再释放 lease；Host lease 过期是明确的安全失败，不代表路径规划或碰撞检测成功。

下一步应先补四组离线回归：marker dropout grace、视觉 recovery 保留目标、worker 单帧异常隔离、worker stop timeout 禁止并行；然后再校准双人局部 matcher 的 `local_player` 和 memory identity 稳定键，最后进行实机短路径验证。

## 2026-10-03 异常隔离与资源生命周期修复（当前断点）

本轮已完成上述四组风险的代码修复和回归验证，重点是避免瞬时截图/识别抖动把整条实时链路停掉，也避免 native 截图线程并行导致卡死。

- `Poe2DualMotionWorker` 现在按帧隔离异常：单帧异常发出 `frame_failed` 并按定位周期重试，默认连续 3 次失败才发出 `failed`；成功帧清零连续失败计数。统计字段 `failed_frames`、`consecutive_failures` 与原有 `completed_frames/dropped_results` 一起用于日志诊断。
- `_start_dual_motion()` 只有在识别器能复制配置并得到独立对象时才启用后台 worker；clone 失败或接口缺失会记录 `worker_disabled` 并使用同步路径，不会把 GUI recognizer 传入后台线程。
- worker stop 超时会设置 pending restart，旧 worker 的 `finished` 信号确认且 retired 列表无运行实例后才重新启动；日志为 `dual_motion.restart_deferred` / `dual_motion.restart_resumed`。
- `DualVisualTracker` 保存首帧主角色 marker 作为局部 matcher 的 `local_player` hint，并随共同视口平移/主角色重新观测更新。marker 无候选或身份歧义默认允许 2 帧 grace，输出有界预测位置；超限才请求一次 recovery。
- 视觉 recovery 前保存 follow 的 source 点击、角色和模式；新鲜 tracking 帧到达后再重建跟随 runtime 并重放目标点击，恢复期间不发送输入。局部接触证据的普通异常统一记录为 `local_contact_failed`，不再误报 `program_probe.write_failed`。

验证结果：`101 passed`（worker、双人 tracker、采集页、跟随 runtime、接触证据），PoE2 专项集合 `368 passed`，`compileall` 通过。尚未发送真实手柄、键盘、鼠标或网络输入。

仍需实机观察：`frame_failed` 是否只在截图后端瞬时波动时出现、`markers_missing_grace` 是否能避免误停、恢复后是否出现 `follow_recovery_resumed`，以及长时间运行的内存/CPU 曲线。memory identity 稳定键和低频 area instance probe 留待下一轮，不在本轮混入。

## 2026-10-03 双人实时链路全面复审（当前断点）

本轮补齐了上一断点中暴露的生命周期和部分 marker 状态缺口：

- `_start_dual_motion()` 在任何新的首帧截图或内存读取前检查所有 retired worker；只要有线程仍运行，就只记录 `dual_motion.restart_deferred`，等待旧线程 `finished` 后再恢复。
- 页面新增 dual session token 与 closing 门控。清图、换图、reset、主动停止和 shutdown 都取消 pending restart，延迟 Qt 回调在 session 已变化、地图已清空或页面关闭时直接丢弃。
- 双人 tracker 按 identity 独立累计 marker dropout。只有一个角色可见时，另一角色在 grace 窗口内仍输出共同位移后的预测 native 点，状态为 `markers_partial_grace/degraded`；超过该角色门限后才触发 recovery，并在 diagnostics 中记录过期身份。
- retired worker 状态检查同时兼容属性和可调用方法；可配置较高连续失败阈值时，`frame_failed` 侧栏日志会限流并保留 suppressed 计数，日志控件仍限制 500 行。

验证：新增边界回归后，双人 worker/采集页/tracker/跟随/接触聚焦集合 `105 passed`，`compileall` 通过。尚未发送真实手柄、键盘、鼠标或网络输入。

仍需独立处理的风险：稳定 entity identity、低频 area instance probe、首帧/恢复注册的 GUI 线程耗时，以及真实 Windows native capture 关闭时序；本轮未将这些未经样本验证的假设写成已解决。

补充：页面在 closing 状态下会忽略 worker 的迟到 result/failed/frame_failed 信号；主动停止也会清除 pending restart，避免停止后旧线程结束触发自恢复。

最终验证：PoE2 专项集合 `369 passed`；`compileall`、`git diff --check` 通过。全量测试唯一失败仍为环境缺少 `pydirectinput` 发行元数据的 `tests/test_distribution.py`，不是本轮代码失败。

## 2026-10-03 双人同目标移动实验（当前断点）

在数据采集测试页侧栏新增独立“双人同目标移动实验”，不替代现有跟随和单人移动探针。先完成获取地图、双人首帧、双人实时定位，等待有采集时间戳的新鲜 tracking 帧；侧栏选择不同的 P1/P2 身份，点击“准备双人目标”只建立待命会话，不取得手柄 lease。随后点击大地图一次，两个角色收到同一 native 目标，各自规划路线并分别输出控制器 1/2；再次点击可同时改目标。地图按实际规划结果显示各自路线和双人物位置；无路径时只显示目标标记，不伪画直达线。侧栏分开显示两人的状态/距离。

安全边界：没有实时帧时间戳或帧龄超过 700ms 不输出；单人到达/位置过期只释放该角色，双人同时到达停止控制 timer。定位整体失效、规划/输出异常、停止、清图或关闭释放全部。运行时每角色消费同帧小地图局部墙体证据；明确请求全局重定位时保存目标与身份、释放两个 lease，经 10 秒冷却进行一次内存锚点恢复，只在同实例且双角色新鲜 tracking 后恢复原目标。越界点击保留上一目标与标记。`dual_target.ready/target_changed/motion/state_changed/local_contact/relocalization_requested/output_diagnostics/stopped` 为关键日志。

自动测试使用假手柄，不向游戏发送输入。2026-10-03 已完成一次双手柄实机主链测试，证据如下；其他设备上的 UI 身份与 Host 控制器对应、游戏失焦行为仍需复验。现有工作台不会自动把 PoE2 窗口置前，测试时应先用短路径并准备点“立即停止”。

本轮复审补充：无路径观察不再画人物到目标的假直线；恢复目标使用原始浮点 source 坐标，类型契约与地图点击一致。

### 2026-10-03 17:38-17:41 实机成功基线

证据源：`data/logs/poe2_live_terrain.log`，地图实例 `P2_7:54BE4D92`。同文件 17:32-17:35 的 `Area:hash` 是 pytest 假输出，不得当作实机记录。用户确认本次实验体验成功；日志能证明双人基本控制链有效，但不能证明最终同时稳定停靠。

- 初始化、抓图成功；双人首帧仅一次内存锚点读取。300x300 的三帧都检出两个 marker，三次配准均 accepted，最佳 score `0.890253`。当前地图结果 angle `221°`、水平镜像、scale `0.874`，只属于此地图实例，不能写成全局常量。
- 双人视觉长期 `tracking`、两人可见；点击显示点 `(1039,2099)` 得到 native 目标 `(606.168047,1204.908149)`，往返误差 0。显示地图点击只逆向处理旋转/镜像，不再次乘首帧配准比例。
- P1 和 P2 各自取得过 Host 控制器 1/2 的 program lease，并沿同一目标显著接近：P1 距离 `139.49 -> 最小 1.59`，P2 `147.51 -> 最小 6.54`。P1 到达后控制器 1 已释放，控制器 2 继续运行；最后由用户停止。该时段没有 ERROR/WARNING。
- 验收边界：日志没有 `dual_target.both_arrived`。P2 只短暂一次进入 `arrived`，之后又离开范围，最后记录距离 `10.09`、local `recovery_attempts=41`；P1 最后距离 `3.19` 且维持 `arrived`。用户补充两名角色在同一目标点附近有体积碰撞，认为这不影响本阶段实验成功。把体积碰撞作为用户实机观察，不将其伪称为日志直接证明的根因，也不把末段现象直接归类为定位/寻路错误。本次没有触发全局重定位，仍不能用它验证全局恢复。

防回归：测试新增实机旋转/镜像点击往返样本和双角色先后到达/独立释放用例。双人同目标假输出场景现为 `19 passed`，采集页加 PoE2 专项回归 `418 passed`；没有修改运行时控制参数。下一次调整定位、路线、手柄轴变换或到达判断前，应先重跑这组测试，并与上述实机日志的身份、坐标空间及 lease 顺序对照。

当前结论：双人移动主链按用户实机体验通过；同点体积占用造成的程序终态差异暂列低优先级，不为本阶段改参数。只有后续需要无人值守判断“两人都完成”时，才考虑共享目标区域或给两人分配不同的停靠点。

## 2026-10-04 实时角色跟随近距离启动修复

本轮确认了“入图时 P1/P2 已经很近，点击开始实时跟随后立即卡住/重定位”的根因：底层 `SimulatedFollowRuntime` 已按 `arrival_radius=12`、`resume_radius=20` 实现了到达保持滞回，但页面层把跟随者遮挡时的零向量或 `WAITING_POSITION` 一概解释为“没有安全候选”，并额外把 `target_arrival_unconfirmed` 解释为必须重定位。于是正常的到达保持态被误触发为重定位。

修复内容：

- 页面新增明确的正常保持判定：`within_arrival_radius`、`within_resume_radius`、`arrival_unconfirmed`、`target_arrival_unconfirmed` 以及 `ARRIVED` 都是正常状态，不触发全局重定位；真正的 `BLOCKED`、位置过期、预测无界和连续视觉创新拒绝仍按原链路恢复。
- 删除“隐藏目标到达未确认即重定位”的页面特判；目标暂时不可见时使用已有的最后可信位置/命令预测，直到超过 TTL 或不确定度上限。
- 增加 `live_role_follow.hold_state` 日志，记录保持角色、状态、原因、距离、到达半径和恢复半径；保持态结束时会记录角色集合变化，便于确认何时从等待转入追赶。
- 保持 12/20 native 滞回、人物半径 3、无墙图膨胀和底层路线规划参数不变。

回归测试新增：近距离启动时无 `start`/`write`，目标连续移动越过 20 native 后才进入 `PROGRAM_READY` 并启动跟随；跟随者在到达保持带内暂时遮挡时不触发重定位。聚焦跟随/运行时测试 `24 passed`；`compileall` 通过。整组 PoE2 页面与 `tests/poe2_live_terrain` 回归为 `463 passed`；同时修正了双人同目标重臂测试，使其在整组运行前显式提供新鲜视觉时间戳，不再受测试本身耗时影响。该结果仍是假手柄回归，不能记作本轮实时跟随实机成功。

当前待实机验收：P1/P2 初始相距小于 12 时开始实时跟随，确认无手柄动作；P1 移动使距离超过 20 后 P2 开始追赶；P1 停止后 P2 回到 12 内释放；短暂遮挡不应重定位或退出。观察 `live_role_follow.hold_state`、`target`、`waiting`、`relocalization_requested` 和 `follow_experiment.motion` 日志。

## 2026-10-03 双人实时角色跟随与窗口尺寸（待实机验收）

数据采集页“自动跟随实验”新增 `P1 手动 / P2 实时跟随` 和反向模式。先获取地图、完成双人首帧并启动双人实时定位，侧栏选择 P1/P2 的实际身份，再选跟随方向与“人物半径”（默认 3 native 格，0–12 可调，启动时生效）并点击“开始跟随实验”。此模式不需要地图点击：目标直接来自每张可信双人视觉帧中手动角色的 native 坐标和原始 `captured_at_ms`，只接受新帧，不把控制 tick 当新截图。目标位移跳变直接重新规划，不追历史轨迹。

程序角色复用已验证的定点寻路、局部避障、接触证据和虚拟手柄输出；手动角色只提供位置，不绑定程序输出。程序角色距离目标 ≤12 native 格停止并释放手柄，目标远离到 ≥20 格再追，防止反复启停。人物半径 3 参与贴墙 clearance/恢复判定，`inflate_collision=False`，**没有膨胀墙图**；旧的点击目标和双人同目标参数未改。视觉帧超过 700ms、双人定位失稳、角色丢失、地图实例/变换失效或输出异常时释放程序手柄；重定位只在同实例的新鲜双人帧后恢复角色方向与最新坐标，不回放旧点击目标。

实验页主区/侧栏、三张截图预览、预览/大地图均可拖动分隔条；独立截图监控窗口的证据/拼图和工作区/历史区也可拖动。两个窗口的预览保留原始帧，窗口大小变化时等比例重绘；大地图 overlay 几何随底图控件 resize 同步，避免标记偏移。上述变化只影响显示布局，不修改地图原始数据或人物 native 坐标。

自动测试使用假手柄：采集页、截图窗口、地图控件、跟随运行器、运动回放、多帧页和手柄适配合计 `129 passed`；PoE2 专项集合 `371 passed`。`compileall` 与 `git diff --check` 通过。没有向游戏发送真实手柄、键盘、鼠标或网络输入。**待用户实机测试**：P1 手动/P2 跟随与反向各跑一轮，验证走远开始、靠近停止、再走远重新接管、位移技能后的新坐标追赶以及“立即停止”释放。观察 `live_role_follow.target/waiting/relocalization_requested`、`follow_experiment.motion/program_diagnostics` 日志；不要把此轮假输出测试记作实机成功。

审查补丁：定点移动探针和实时跟随的启动入口现在互斥；通过各自的已有停止路径先释放上一实验的计时器、待点击状态和手柄输出，再进入新实验。双向切换回归测试通过。PoE2 专项与相关采集页/窗口/地图控件合并回归现为 `436 passed`；这仍是假手柄验证，真实跟随效果待用户验收。

## 2026-10-04 实验页 UI 与双人链人工审查

数据采集实验页右侧现为“采集定位 / 移动跟随 / 日志”三标签，各自滚动；停止全部程序移动按钮始终在标签页外。该按钮无条件经过定点探针、实时跟随和双人同目标三个停止路径，包含待恢复目标清理，不会停止双人视觉定位。人物半径控件只在 P1/P2 实时跟随方向可调，旧的模拟/定点模式置灰。左侧预览、地图及整体侧栏的拖动缩放保留。1400×900 Qt 离屏截图检查没有遮挡或压扁；离屏中文字体缺失，需在 Windows 程序窗口确认实际字体。临时截图已清除。

人工逐段核对了双人内存锚点 + marker 首帧配对、墙体位移与 marker 身份维护、worker 代际与结果消费、视觉状态到 native 跟随目标、地图点击逆变换、双角色程序输出及重定位恢复。正常失效路径会释放输出；本轮没有修改定位或运动算法。发现的待处理点：

- 首个实时 warmup 帧即使两名 marker 均漏检，墙层相似时仍可能是 `tracking`；live 跟随没有额外本帧可见性门，可能短暂沿预测位置输出。
- `stop_dual_motion()` 未清除上一轮截图时间；快速复用旧首帧并重启时，首帧状态可能暂时与旧时间戳拼接，通过 700ms 时效门。
- 旧 `single_p2_program` 启动只校验 P1、未校验实际执行的 P2；P2 未选择/缺失时可在创建输出后抛 `KeyError`，未进入清理块。
- 双人同目标允许 `degraded` 下短时沿预测位置运行，缺失角色依赖 700ms TTL 停止；单人移动探针也只按位置和帧龄做门控。此项是容错与保守停机的取舍，需实机量化，不能称为已复现故障。

UI 及相关双人链回归 `443 passed`，`compileall` 和 `git diff --check` 通过；没有发送真实手柄、键盘、鼠标或网络输入。下一步优先补单人 P2 启动校验和首帧/时间戳可见性门，再做实机跟随验收。

## 2026-10-04 双人链审查问题修复（当前断点）

已修复上一轮的前三个明确缺口：

- 双人 tracker 的无 marker warmup 帧仍允许墙层静止估计，但标为 `degraded`，不再把预测人物点当本帧可信观测。实时跟随启动与每次输出另行拒绝 `warmup_assumed_stationary`；运行中遇到该帧释放程序输出，下一可信视觉帧可继续。
- 停止双人定位时同时清除 `_latest_dual_state` 和 `_latest_dual_captured_at_ms`。复用成功首帧只建立地图和 tracker，不再继承上一轮的 700ms 新鲜度；新的 worker/同步截图帧到来前，实时跟随启动会等待。
- 跟随启动先按实际受控角色校验有效位置，单人 P2 模式不再错误依赖 P1；角色加入运行器也进入输出初始化的异常清理边界。

验证先以回归测试复现 `3 failed, 1 passed`，修复后双人/跟随聚焦 `131 passed`、PoE2 专项与采集页/窗口/地图控件合并 `444 passed`，`compileall` 与 `git diff --check` 通过。仅使用假输出，未发送真实手柄、键盘、鼠标或网络输入。双人同目标的 `degraded` 预测宽限和单人探针的位置/帧龄门控保持原策略，仍需实机量化；P1 手动/P2 跟随及反向的真实效果也尚未验收。

## 2026-10-04 蓝色记录点重叠诊断（待修复）

用户反馈实机跟随总体可用，但蓝色人物与蓝色记录点在小地图重叠时失去稳定定位。截图保存时间约 03:03:29。`data/logs/poe2_live_terrain.log` 的同一测试会话始于 02:57:30，03:00:13 启动 P1 手动/P2 实时跟随。03:02:19 的 `markers_partial_grace` 显示墙体质量约 1、仅 P1 被本帧分配、P2 连续缺失，超过 2 帧后变为 `markers_missing/recovery_required`；跟随页面随后进入 `live_role_follow.waiting`，没有证据表明仍持续向 P2 输出。此阶段是人物标记证据失败，不是墙层首次失败。

本地 active monitor profile 未显式保存双人 marker profile，代码加载预置黄色 HSV `5..38`、蓝色 HSV `82..125`。候选检测只用 HSV、面积 `8..55`、最大尺寸 `14`，身份分配使用颜色 hint 和预测距离；蓝色记录点没有被识别为静态地标。截图支持“同色重叠”场景，但当前日志未保存候选 bbox/面积/HSV 与原始 300x300 小地图，不能判定轮廓是合并超限还是静态候选抢占，禁止凭猜测直接改色阈值或挖空墙层。

另有独立且优先级更高的恢复交付缺口：worker 只保留最新帧，tracker 的 `recovery_requested=True` 仅发一个帧；该帧被覆盖时页面会持续看到 `recovery_required/recovery=False` 而不重新锚定。实机日志自 03:00:59 就出现该状态，03:06 仍没有 `dual_motion.recovery`，失效初期已累计丢弃 287 个结果。后续还有 `wall_and_local_match_failed`，应在恢复事件可靠交付后再单独判断，不全归因于蓝色记录点。

下一步先用假 worker 测试覆盖恢复边沿帧，让 `recovery_revision` 黏性传到页面并按 revision 恰好执行一次；再在 marker 失效状态切换时保存有限量的原始局部帧、每色 mask、候选几何/颜色和分配代价。拿到真实重叠前中后样本后，再设计墙层位移补偿的多帧动态/静态消歧与遮挡宽限。诊断轮未改定位、导航、手柄算法，也未发送真实输入。

## 2026-10-04 双人短时视觉失明恢复（离线验证完成，待实机验收）

- 新增身份无关的 `BoundedRoleObservations`：每个角色分别保存最后可信 native 点和观测时间，按 2 秒/10 native 格默认预算限制短时估计；重现候选须通过位置门和连续两帧确认。首帧/恢复共用现有双人锚点，正常帧不增加内存读取。单人中心定位未改。
- `DualVisualTracker` 在墙层可信时保留各角色有界估计，缺失一人不抹掉另一人；预算耗尽或墙层失效才请求重锚。分配最多考虑六个颜色候选，并记录各角色可见性、年龄、误差及候选代价。双人墙体识别仍使用 `exclude_player=False, exclude_dynamic=False`，没有人物周围 mask。
- worker 保持 latest-only 图像槽，但将一次性 `recovery_revision` 独立保存到页面消费；即使边沿图像被覆盖，也不会因丢帧漏掉恢复。页面先处理恢复，再考虑继续跟随。失明期间仅在墙层可信、截图新鲜、所有参与角色均在预算内时有限继续；帧过期/预算耗尽立即中性释放。`wall_estimate` 不作为速度或撞墙校准证据。
- 实验页提供失明宽限和误差上限可调参数。失明状态切换时最多保存 6 组原始小地图、每个配置颜色的 mask、候选几何与赋值诊断到 `occlusion_diagnostics/`，用于下一次实机重叠样本分析；不周期性保存整段视频。

离线验证：PoE2 专项、采集页、worker 和纯状态回归 `448 passed`。人工核对截图→颜色候选/墙体→双人 tracker→worker→页面→跟随运行器→输出/释放链。**未做本轮实机测试，也未发送真实手柄或网络输入。** 目前不能宣称蓝色人物与记录点重叠的具体轮廓原因已查明，更不能宣称实机遮挡恢复已验收。下一次请在实验页分别测试 P1/P2 遮挡与双角色短时遮挡，留存 `occlusion_diagnostics/` 的重叠前、中、后证据，并核对 `live_role_follow.observation`、`dual_motion.recovery` 和手柄释放日志。

## 2026-10-04 命令辅助跟随与视觉重认（当前断点，待实机验收）

实时角色跟随的程序角色现在只按**成功写入 Host 的真实输出区间**积分：每个角色独立保存最后视觉 native 点、地图实例、输出轴、实际接受时间、TTL 和协方差。新视觉帧按其截图时间纠偏；预测样本标记为 `command_prediction`，不作为真实位移、卡墙、速度标定或到达证据。手动领队隐藏时保持最后可信目标 `target_hold`，不臆造其运动。目标和角色身份在现有重锚流程中保留。

此前的缺口是上游 `DualVisualTracker` 仍在图标超过旧 2 秒预算时强制重锚，且只围绕旧屏幕点找回出现的角色。现已在**数据采集页的实时跟随会话**内，把按角色的预测 native 点与误差通过 generation 隔离的 worker 邮箱送回视觉跟踪；按当前旋转/镜像/比例回投到小地图，再用颜色身份、距离门及连续帧确认重现。新鲜预测可暂缓旧时限，但不刷新视觉时间；提示超过 700ms、误差超过 12 native 格、墙层失效或无安全候选，仍按原链路释放输出并重锚。停止跟随清空提示。无提示的独立双人定位保持原行为，单人中心模式与双人首帧未改。

当前自动回归 `478 passed`，`compileall` 和 `git diff --check` 通过；全为假输出/离线几何与页面测试，**没有发送真实游戏输入，也尚未证明蓝色人物与同色记录点长期重叠时的身份唯一性**。下一次实机测试：保持同一地图实例，先分别让 P1/P2 图标短时遮挡并移动，观察角色虚线预测是否连续、可见后是否纠偏；再测蓝色记录点重叠，保存 `occlusion_diagnostics/` 原始帧。对照 `dual_motion.tick` 的 `prediction_hint_identities/role_observations/assignment`、`live_role_follow.prediction/visual_rejected/relocalization_requested` 和 Host 输出回执。若预测明显偏向静态图标或跳错角色，立即停止程序移动并保留证据，不把此次判成成功。

## 2026-10-04 跟随启动卡顿根因修复（当前断点）

最近一次实机日志显示，跟随并非从规划或 Host 申请处卡住：首个 `program_ready` 已生成 160ms 手柄脉冲，但启动后 0.15–0.23 秒的视觉帧仍显示人物旧位置。命令跟踪器默认把视觉观测协方差设为 `1 native²`，将这个正常的输出/截图/游戏模拟延迟判成 `observation_rejected`；页面两次拒绝后触发一次约 13 秒的内存重锚，造成反复释放、重启 worker 和界面停顿。

已将未显式提供的视觉观测协方差保持为 `9 native²`，并新增按角色、按启动/恢复 episode 生效的 `CommandRoleTracker.arm_visual_phase()`：默认 `750ms` 内使用 `64 native²` 的相位宽限，过期后自动恢复稳态门；显式小协方差仍会拒绝远距离跳变。页面拒绝日志继续记录预测点、视觉点、创新距离和估计不确定度。单人中心定位、双人首帧、无提示的独立实时定位和重锚安全边界未改。

恢复失败现在原子清除 program-probe、dual-follow、dual-target 三类延迟上下文；跟随入口在创建新 runtime 前释放旧 timer/runtime/output，避免快速重复启动覆盖租约。`stop_dual_motion()` 不再同步等待最多 3 秒，而是 `wait(0)` 非阻塞退休，由 worker finished 回调继续 deferred restart。`ProgramGamepadOutput` 已为 `program.state`、低频 `status/state` 记录耗时，≥50ms 输出告警，并把耗时放进诊断快照。

离线相关回归现为 `468 passed`（本轮双人/跟随/手柄聚焦为 `88 passed`），`compileall`、`git diff --check` 通过；仍未发送真实手柄。本修复需要下一次实机确认：正常跟随应连续出现 `follow_experiment.motion`/Host 状态，不应在首个脉冲后连续两次 `visual_rejected` 并进入 `live_role_follow.reanchor`。若仍有卡顿，优先查看 `predicted`、`innovation`、`uncertainty`、`host_request_ms` 和 `diagnostics_elapsed_ms` 字段；恢复首帧后台化在下一轮断点中完成。
## 2026-10-04 双人实时跟随执行链人工审查（当前断点）

本轮先依据实机日志完成根因审查，再修复双人跟随执行链；没有发送真实输入。核对链路为：

`双人首帧 → DualMotionWorker 截图/识别 → 页面 drain → start_follow_experiment → _tick_follow_experiment_impl → CommandRoleTracker 预测/视觉纠偏 → SimulatedFollowRuntime.tick → ProgramFollowOutput → ProgramGamepadOutput/Host → 视觉恢复或重锚 → 停止释放`。

### 本轮已修复与剩余风险

1. **已修复：恢复后首个输出的视觉相位门。** 日志 `2026-10-04 11:32:41.721–11:32:54.643` 所示的“Host 已确认、截图仍旧位置”现在由每个 live-follow role 的 `750ms` 相位窗口处理；窗口内只放宽默认观测方差，过期恢复 `9 native²` 稳态门，显式严格协方差仍拒绝跳变。
2. **已修复：worker join 与恢复首帧不再阻塞 GUI。** `stop_dual_motion()` 只发停止并 `wait(0)`，保留退休 worker 到 finished 回调后再恢复；生产配置下 `_start_dual_motion(recovery=True)` 的内存读取和首帧注册已交给独立的一次性 worker。
3. **已修复：恢复失败 context 原子清理。** `_clear_dual_recovery_contexts()` 同时清空 program-probe、dual-follow、dual-target，避免同一地图重启消费上一轮失败状态。
4. **已修复：跟随启动幂等。** `start_follow_experiment()` 进入时先停止旧 runtime/timer/output，再创建新 session，保持单一 Host lease 所有权。
5. **已量化：Host 请求诊断。** `ProgramGamepadOutput` 记录 `program.state` 单次时延、低频 `status/state` 总时延，并在 ≥50ms 时输出告警；协议调用仍同步，是否需要异步化要看下一次实机日志。

### 已确认没有发现的链路错误

- worker 的 generation 检查会丢弃旧会话迟到结果；session token 会取消关闭/清图后的延迟 restart。
- latest-only 图像槽之外独立保存 recovery revision，图像覆盖不会吞掉一次性恢复事件。
- 停止顺序会释放跟随输出、停止 timer、退休 worker；正常路径未发现旧 worker 直接写入新 tracker 或主动停止后自动重启的确定性证据。

### 下一步实施顺序

1. 用真实双人跟随复测：确认首个程序脉冲后不会立即重复 `visual_rejected → reanchor`，并查看 `host_request_ms` / `diagnostics_elapsed_ms`。
2. 若实机仍出现 >100ms GUI 卡顿，再单独检查 Host 请求时延和地图渲染耗时，不回退到同步首帧注册。
3. 若 Host 时延持续 ≥50ms，再单独设计低频 diagnostics 异步化和请求取消，不与定位门限混改。

## 2026-10-04 跟随卡顿与首次视觉拒绝修复（当前断点）

根据 `51ea4f8d-4902-4df9-bb09-b856dc9060c4` 诊断材料，本轮确认卡顿主因不是双人首帧，而是跟随首个 160ms 手柄脉冲后，视觉帧仍处于旧位置，页面过早累计拒绝并触发全局重定位；重定位原先在 Qt 主线程同步执行内存读取、三次截图和候选注册，导致窗口长时间无响应。`worker_stop_timeout` 同时只是旧 worker 非阻塞退休期间的生命周期提示，不是 Python 崩溃。

已完成：

- 跟随启动帧龄从宽泛的 700ms 收紧为 `0–300ms`；旧帧不会创建跟随 runtime 或申请程序输出，日志为 `live_role_follow.start_waiting`。
- 启动/恢复视觉相位内的瞬时拒绝不计入稳定态重定位计数；稳定态现在需要连续 3 次创新拒绝才触发 `repeated_visual_innovation_rejected`。拒绝日志增加 `phase_active`、`rejected_count` 和 `reanchor_after`，可区分延迟帧与真实漂移。
- 新增 `Poe2DualFirstFrameWorker`。生产配置存在 `localization_fps` 时，恢复首帧的内存锚点、三次截图和几何注册在后台线程执行；Qt 线程只接收结果、应用地图/状态并重新建立 tracker，不再同步阻塞界面。后台任务按 generation 丢弃过期结果，停止时不会向页面发送迟到结果。
- 恢复耗时记录为 `dual_first_frame.worker_started/worker_result`，包含 generation、状态和 elapsed；旧 worker 尚未退出时日志降为 `worker_stop_deferred`，明确说明是 native capture 正在返回，不再伪装成致命超时。

验证：新增启动新鲜度、视觉宽限、后台首帧 worker 及迟到结果抑制测试；聚焦页面/运行时/worker 回归 `140 passed`，PoE2 页面、运行时、worker 与架构边界整组回归 `488 passed`，`compileall` 通过。尚未发送真实输入，后台恢复需要下一次实机日志确认 `worker_result elapsed_ms` 与 UI 卡顿是否消失。

实机验收顺序：先完成双人首帧和实时定位，使用 ≤300ms 新鲜帧启动跟随；观察首个输出后 750ms 内的 `visual_rejected phase_active=True` 不触发重定位；若稳定态连续三帧拒绝，确认进入后台恢复而不是窗口假死。重点记录 `live_role_follow.start_waiting`、`visual_rejected`、`dual_first_frame.worker_started/worker_result`、`dual_motion.worker_stop_deferred` 和 `follow_experiment.motion`。

## 2026-10-04 只读实机跟随链探针（当前断点）

本轮新增 `tools/debug/poe2_follow_readonly_probe.py`，用于在真实 PoE2 进程上验证最近的双人首帧、视觉跟踪和性能链路。脚本明确不导入虚拟手柄/Host 输出，不启动跟随运行器，不发送鼠标、键盘、手柄或网络输入；默认最多采集 12 帧、保存 6 张原始小地图，且首帧失败后不重复读取内存。

探针顺序为：

1. 当前进程一次只读指纹/布局解析，并把同一实例的 native terrain 导出到 `data/poe2_live_terrain_test/readonly_follow_probes/<run>/terrain_capture`；
2. 载入当前 PoE2 monitor profile，使用正式双人 localization composition 截取首帧；
3. 记录双人首帧状态、玩家坐标、transform、marker 诊断、截图时间戳和 capture/evidence/localization 分段耗时；
4. 首帧通过后只运行有限视觉帧，不读内存、不创建任何程序输出；所有结果写入 `report.json` 和有限的 `frames/*.png`。

实测边界：当前普通 Python 进程能发现 `PathOfExile.exe`（PID 33984），但打开只读句柄即返回 `PermissionError: [WinError 5] 拒绝访问`，因此本轮没有获得真实地图、人物坐标或视觉帧，不能据此判断算法失败。普通权限报告保存在 `data/poe2_live_terrain_test/readonly_follow_probes/20261004-151403-167/report.json`，其中 `input_calls=0`。尝试用 Windows `Start-Process -Verb RunAs` 提升运行没有产生报告，视为 UAC 未确认，不再自动重试。

管理员终端可复现实验：

```powershell
D:/ACloud/.venv/Scripts/python.exe D:/ACloud/auto_modules/tools/debug/poe2_follow_readonly_probe.py `
  --frames 12 --interval 0.10 --save-frames 6 `
  --out D:/ACloud/auto_modules/data/poe2_live_terrain_test/readonly_follow_probes/live
```

拿到报告后，先看 `errors`、`terrain.instance_id`、首帧 `state.status/reason`、每帧 `timing_ms` 和 `frame_age_ms`；只有这些证据齐全，才继续修改定位或性能参数。该探针未改变正式运行链，也未宣称实机跟随已通过。

## 2026-10-04 异步恢复首帧状态消费修复（待实机复验）

实机日志 `2026-10-04 16:32:09–16:32:27` 已确认本次“开始跟随后马上结束”的直接根因：

1. 双人跟随首个视觉阶段出现三次创新拒绝，按设计触发一次后台重锚；旧 motion worker 被非阻塞退休，首帧 worker 在后台完成一次内存读取、三次截图和三次候选配准。
2. 后台明确输出 `dual_first_frame.result status=accepted`、`worker_result status=accepted`，变换角度 `231.4669°`、镜像为真、比例 `0.8106`、两名玩家 anchor error 均为 `0`、pair confidence `0.8938`。
3. 页面回调随后仍输出 `program_probe.relocalization_failed reason=first_frame_rejected` 并清理恢复上下文。代码审查确认：回调以 `first_frame_ready=True` 调用 `_start_dual_motion(recovery=True, first_frame_ready=True)`，但启动函数原先把 recovery 的 `result` 强制置为 `None`；由于 `first_frame_ready=True` 又跳过了重新计算，成功结果被自身的空值校验误判。

已修复：恢复启动统一消费 `_apply_dual_first_frame_bundle()` 写入的 `_last_dual_first_frame_result`；只有尚未交付首帧时，recovery 才会强制重新读取和配准。新增 `dual_motion.first_frame_context` 日志，记录 `recovery`、`first_frame_ready`、`status`、`accepted`、`has_frame`，worker 日志同时记录 `accepted` 字段；`follow_experiment.stopped` 记录停止时是否仍持有 timer/output，便于区分恢复释放、用户停止和输出异常。新增页面回归覆盖 accepted 异步结果直接建立 tracker/timer，拒绝结果仍保留原失败清理行为。PoE2 双人定位/跟随/手柄整组回归 `473 passed`。

本轮未改首帧阈值、双人候选、方向/比例、跟随速度或手柄协议；没有发送真实输入。实机复验必须看到：

```text
dual_first_frame.worker_result ... status=accepted accepted=True
dual_motion.first_frame_context ... first_frame_ready=True status=accepted accepted=True has_frame=True
dual_motion.started ... recovery=True
dual_motion.tick ...
```

同一 generation 不应再出现 `program_probe.relocalization_failed reason=first_frame_rejected`。如果之后仍停止，按新日志区分 Host 输出异常、地图实例变化、后续视觉失配或真正的 tracker 恢复失败，不再把首帧注册误判为失败。

## 2026-10-04 双人跟随链路人工审查（未改行为）

本轮按真实运行顺序人工模拟：双人首帧 → 双人 motion worker → 跟随启动 → 首次程序脉冲 → 视觉拒绝/预测 → runtime 重定位 → 后台首帧恢复 → tracker 重建 → 跟随恢复 → 停止与旧 worker 退休。结论如下，均为代码推导或已有日志证据，不等同于实机新验收。

### 已确认的正常边界

- `Poe2DualMotionWorker` 只在 worker 线程截图、识别和 tracker tick；页面 generation 检查、latest-only 槽和独立 recovery revision 能阻止旧连续帧污染新 session。
- `start_follow_experiment()` 在 live 模式会校验地图实例、两名不同角色、tracking 状态和帧龄，再只为程序角色申请输出；手动领队不会申请程序 lease。
- 首次程序脉冲后的短暂旧视觉帧由 `CommandRoleTracker.arm_visual_phase()` 的 750ms 宽限吸收；稳定态连续 3 次视觉创新拒绝才请求重锚。
- recovery accepted 结果现在由 `first_frame_ready=True` 消费，不再走空 result 失败分支；主动停止、换图和关闭会停 timer、释放输出并取消 deferred restart。

### 新发现的风险（按优先级）

1. **P1：恢复恢复帧龄门不一致，可能丢失跟随上下文。** `_maybe_resume_dual_follow_after_relocalization()` 允许 live frame 年龄 ≤700ms（`capture_test_page.py:2547`），随后调用 `start_follow_experiment()`，后者要求 ≤300ms（`capture_test_page.py:2844`）。因此年龄在 301–700ms 的恢复帧会先通过 resume 门，再被 start 门拒绝；`_maybe_resume...` 随即把它记录为 `runtime_rebuild_failed` 并清除 recovery context。结果是首帧和 tracker 已成功，但跟随不自动恢复。应统一门限或在等待新鲜帧期间保留 context，不能把“帧稍旧”当作 runtime 构建失败。

2. **P1：跟随侧重定位绕过统一 10 秒冷却。** `Poe2CaptureTestPage._request_live_follow_reanchor()`（`capture_test_page.py:3964`）直接保存 context、释放输出并调用 `_start_dual_motion(recovery=True)`，没有更新/检查 `_dual_last_recovery_at_ms`。10 秒冷却只在 `_drain_dual_motion_worker()`/同步 `_tick_dual_motion()` 看到 `state.recovery_requested` 时生效。若触发原因是 `repeated_visual_innovation_rejected`、`command_prediction_unbounded`、`manual_target_unobserved` 或 `occluded_role_has_no_safe_candidate`，同一根因可以反复读内存、重建 worker，造成卡顿和恢复风暴。应让所有 recovery reason 进入同一个 revision/cooldown 门，而不是按触发入口分叉。

3. **P1：连续 worker 实际处理速度可能低于配置 FPS，导致 latest-only 丢帧和帧龄过期。** `dual_motion_worker.py:157-252` 的循环只有在单帧处理结束后才等待下一个 interval；已有实机日志单帧约 48ms，而配置为 30 FPS（目标 33ms），因此实际约 20 FPS，且出现 `dropped_results`。这会让页面看到的 `captured_at_ms` 变旧，直接触发跟随的 300/700ms 门或视觉失配。需要先把 capture、recognition、tracking、UI drain 的耗时拆开统计，再决定降频、跳帧、缩小特征区域或自适应采样；不能只把帧龄阈值放宽。

4. **P2：首帧 worker 的 `result_available` 与 cleanup 失败信号存在终态竞态。** `Poe2DualFirstFrameWorker._run()` 在发出结果后执行 cleanup；若 cleanup 抛异常，会再发 `failed`。页面的 `_on_dual_first_frame_worker_result()` 已把 worker 置空并可能启动新 tracker，但 `_on_dual_first_frame_worker_failed()` 只按 generation 判断，没有确认该 worker 是否仍是当前 pending worker，可能在 accepted 后清理 recovery context。当前 cleanup 通常不失败，但应建立“终态只消费一次”的标志或让 cleanup 错误只记录而不覆盖已交付结果。

5. **P2：worker 路径重复做预处理。** `Poe2DualMotionWorker._capture_one()` 调用 `extract_combined_with_processed()` 得到 `processed`，但 `DualMotionFrameResult` 不保存它；页面 `_drain_dual_motion_worker()` 再以 `combined` 调用 `_render_preview()`，导致 GUI 线程重新执行 `recognizer.preprocess_image()`。这不会改变定位坐标，但会增加 UI CPU 和卡顿，尤其在 12 FPS 预览时明显。

6. **P2：Host 输出和诊断仍在跟随 Qt 线程同步执行。** 每个程序角色每个 follow tick 都会同步调用 `ProgramGamepadOutput.write()`；每 10 tick 还调用 `diagnostics()` 的 `status()` 与 `state()`。代码只记录 ≥50ms 告警，没有超时隔离或异步队列；双角色时一次 tick 可能串行等待多个 Host 请求，阻塞 UI、延迟 worker drain，并反过来增加帧龄。是否需要异步化必须依据新的 `host_request_ms`/`diagnostics_elapsed_ms` 实测，不应盲改协议顺序。

7. **P1：同一视觉帧在三层使用了不一致的年龄门。** `start_follow_experiment()` 只接受 ≤300ms，页面/运行时的过期门允许到 700ms，而 `LocalComplexityClassifier.max_frame_age_ms` 默认是 500ms。于是一个 501–700ms 的帧会通过页面的“仍可用”判断，却在闭环规划阶段变成 `UNKNOWN`，`ClosedLoopMotionController` 返回 `command=None`，运行时把它表现为 `route_not_progressing`/零向量；而 301–500ms 的帧还可能启动失败或恢复时被清掉。这不是单纯阈值大小问题，而是跨层契约矛盾，必须先统一“采样时间、控制允许时间、规划允许时间”的定义。

8. **已修复（2026-10-04）：视觉帧过期的跟随空转。** `_tick_follow_experiment_impl()` 现在用边沿字段记录首次过期、单次释放和 1500ms 后单次 `visual_frame_stalled` recovery；连续 100ms tick 不重复释放或刷 warning，新鲜帧到达后恢复正常闭环。native capture 若永远阻塞仍受第三方调用不可强制打断的边界约束。

9. **已修复（2026-10-04）：motion worker 的重复 overlay/UI 更新。** `_render_dual_motion_state()` 在 follow/dual-target runtime 存在时只调用对应 renderer；连续 worker drain 改为 33ms 贴合 30 FPS 生产节拍，仍保留 latest-only 语义。预览使用 worker 传来的 `processed`，不在 Qt 线程重复预处理。

本轮实测回归（2026-10-04）：

```text
pytest -q tests/test_poe2_capture_test_page.py tests/test_poe2_dual_motion_worker.py \
  tests/poe2_live_terrain/test_multiplayer_follow_runtime.py \
  tests/poe2_live_terrain/test_command_role_tracker.py
144 passed, 3 failed
```

3 个失败均落在双人同目标实验的“到达/局部接触”断言；日志显示运行时返回 `state=program_ready reason=route_not_progressing vector=(0, 0)`，与上面的 500ms `UNKNOWN` 门一致。此前文档中的 `473 passed` 是更早的聚焦集合，不能覆盖当前工作树这组回归；在统一年龄契约并补充该时间边界测试前，不应宣称跟随链路完整通过。

独立闭环边界探针也复现了同一矛盾：在其他输入完全相同的情况下，`frame_age_ms=500` 返回 `open/command_ready`，`frame_age_ms=501` 立即变为 `unknown/local_observation_unknown`，而页面仍会把 501–700ms 视为未过期。该结果不涉及真实输入，仅验证了年龄契约的分叉。

### 人工模拟结论

当前链路不是单一状态机，而是三个节拍交织：motion worker（目标帧率）、Qt drain（16ms）和 follow timer（localization interval）。状态恢复还同时有双人 tracker recovery、follow runtime recovery、program probe recovery 三个入口。已修复的 accepted 状态错位解决了本次立即结束的直接根因，但上述门限/冷却/节拍问题仍可能让“首帧成功但跟随未恢复”“重复重定位”“界面卡顿”分别出现。下一轮应先补状态机回归和耗时观测，再按 P1→P2 顺序修改，不能继续调匹配阈值。

## 2026-10-04 跟随过期帧空转修复

本轮完成第一步最小修复。`Poe2CaptureTestPage` 现在把“视觉帧过期”当作有边沿的等待状态：

- 第一次超过 `_FOLLOW_RUNTIME_MAX_FRAME_AGE_MS=700` 时释放程序输出并记录一次 `live_role_follow.waiting`；后续 100ms tick 不再重复调用 `release_all()`，也不再刷同一条 warning。
- 从过期开始累计 `_FOLLOW_STALE_RECOVERY_AFTER_MS=1500`。持续无新帧达到该时长时只请求一次 `visual_frame_stalled` 重定位，入口仍经过页面统一的 10 秒 recovery claim。
- 新鲜视觉帧到达后清除等待边沿和单次恢复标志，并记录一次 `visual_frame_resumed`，随后回到正常跟随闭环。
- “markerless warmup” 仍是独立状态：它有新鲜帧但证据尚未可信，不会被误计为 capture stalled。

新增回归覆盖：过期首 tick 只释放一次、连续过期不重复释放、长时间无帧只请求一次恢复，以及新鲜帧恢复后继续跟随。聚焦结果：

```text
pytest -q tests/test_poe2_capture_test_page.py -k "stale_frame"
3 passed

pytest -q tests/test_poe2_capture_test_page.py tests/test_poe2_dual_motion_worker.py \
  tests/poe2_live_terrain/test_multiplayer_follow_runtime.py \
  tests/poe2_live_terrain/test_command_role_tracker.py
156 passed
```

这一步没有改变定位匹配、方向比例、路径规划或真实输入协议；尚未处理的下一项仍是首帧 worker accepted 后 cleanup 失败的终态竞态。

## 2026-10-04 首帧终态与连续帧预处理修复

继续按审查顺序完成两项低风险修复：

1. `Poe2DualFirstFrameWorker` 现在记录是否已经发出 `result_available`。accepted（或其他正常结果）交付后，即使同线程 cleanup 抛异常，也只保留 cleanup 日志，不再发送第二个 `failed` 终态；页面侧同时忽略“当前 worker 已被结果处理器摘除”后的迟到失败回调，避免清掉已保存的跟随恢复上下文。
2. `DualMotionFrameResult` 新增 `processed` 字段。连续 worker 已完成的预处理结果直接交给 Qt drain 的预览渲染，不再在 UI 线程再次调用 `recognizer.preprocess_image()`；同步 fallback 路径保持原有行为。
3. `_render_dual_motion_state()` 在 follow/dual-target runtime 存在时只调用对应 overlay 渲染一次，避免先绘制普通 tracker overlay、再立即覆盖一次的重复 Qt 更新。实时跟随尚无上一份 observation 时保留普通人物位置，避免启动瞬间标记消失。

新增回归覆盖 cleanup 失败不遮蔽已交付结果、worker 保留 processed 结果和每帧单次 overlay。当前 worker 聚焦回归 `10 passed`，页面相关聚焦回归 `2 passed`；下一轮完整聚焦回归和 `compileall/diff --check` 仍需在本轮所有修改结束后统一执行。

连续 worker 的 Qt drain 也从 16ms 调整为 33ms（30 FPS 生产节拍）。它仍然只消费 latest-only 结果，但不再在一个 30 FPS 生产周期内无意义唤醒两次；这只改变页面调度频率，不改变截图、识别、定位或手柄命令节拍。

Host 诊断查询同样改为低频观测：跟随和双人同目标控制 tick 仍按原节拍发送/释放命令，但 `output.diagnostics()` 最少间隔 5 秒调用一次（首次 tick 仍记录一次）。诊断异常也会占用这一观测窗口，不会每 100ms 重试形成 UI 阻塞/日志风暴；adapter 已有的单次 `host_request_ms`、`diagnostics_elapsed_ms` 仍保留。该改动只减少查询，不改变真实输出协议。

### 本轮人工链路复核

按“启动 → 首帧 → worker → 跟随 → 过期 → 恢复 → 停止”的顺序逐段检查：

1. 启动跟随时仍要求同实例、tracking、角色有效和首帧 ≤300ms；近距离到达保持不申请输出。
2. 连续 worker 只生产 `DualMotionFrameResult`，页面 drain 只消费 latest；`processed` 随结果传递，Qt 不重复预处理；代际检查和停止后的旧回调仍在页面边界生效。
3. 跟随 timer 首次看到过期帧只进入等待边沿并中性释放；等待超过 1500ms 才走一次统一 recovery claim。新鲜帧恢复会清掉边沿，避免旧“失明”状态黏住新会话。
4. 首帧 worker accepted 已交付后，cleanup 异常不再产生第二个失败终态；页面也不会用迟到失败清除恢复上下文。
5. recovery 期间输出先释放，旧 worker 退出后才允许新首帧；accepted recovery 通过 `first_frame_ready` 交付，跟随上下文由现有 resume 入口重建。
6. 停止/异常路径仍统一关闭 timer、清空 prediction hints、关闭 output lease；Host diagnostics 低频读取不参与控制状态判断。

未发现新的状态机环路或“同一视觉帧重复推进 runtime”的路径。尚未宣称完全解决的性能边界只有两项：单次 Host `write()` 仍是同步协议调用，真实耗时要靠 `program_output.host_request_ms` 实机日志量化；native capture 本身若长期阻塞，worker 只能等其返回，现有 deferred-stop 会保护旧线程但不能强制打断第三方 native 调用。

## 2026-10-04 实时跟随冷启动回归收口（当前断点）

本轮完成上一断点遗留的测试收口，没有修改双人同目标生产逻辑。三个失败的根因均已通过代码链路和日志复现确认：

1. `test_switching_between_move_probe_and_follow_releases_previous_mode` 仍假定实时跟随启动同一帧立即 `output.start()`；现在启动契约是 `cold_start`，同一 accepted frame 只建立 tracker 基线，不输出，必须收到严格晚于 baseline 的双人视觉帧后才进入 `tracking`。
2. 双人同目标 runtime 异常和 stale-role 测试在手动 tick 前没有刷新页面级 `captured_at_ms`，测试执行时间超过 700ms 后提前走页面 TTL 分支，runtime.tick 根本未被调用。刷新页面时间后，runtime 异常会正确释放两路输出；stale role 会保留 `WAITING_POSITION`，另一角色继续运行。
3. 双人同目标连续点击测试在第二次点击前补充新鲜帧时间，保持 700ms 页面帧契约，不放宽生产 TTL。

当前实时跟随启动/恢复状态机：

```text
accepted frame
  → start_follow_experiment(cold_start/recovery_sync)
  → seed role tracker；同帧不输出
  → captured_at_ms > baseline 的完整双人帧
  → sync_ready；重启 750ms visual phase
  → tracking；ProgramFollowOutput arm/write
  → 连续 3 次稳态视觉拒绝才请求一次 recovery
  → recovery_sync；accepted 后再次等待严格新帧
```

离线验证：

```text
pytest -q tests/test_poe2_capture_test_page.py -k "switching_between_move_probe_and_follow_releases_previous_mode or dual_target_experiment_stops_both_on_runtime_failure or dual_target_experiment_releases_only_stale_role"
3 passed

pytest -q tests/test_poe2_capture_test_page.py
78 passed
```

测试未连接真实 Host 或游戏，也没有发送真实手柄、键盘、鼠标或网络输入。下一步继续执行完整回归、`compileall` 和 `git diff --check`；实机验收仍需观察 `live_role_follow.sync_enter/sync_waiting/sync_ready`、首个 Host 输出和后续视觉纠偏日志。

最终验证结果：PoE2 跟随闭环相关回归 `160 passed`，`python -m compileall -q src` 与 `git diff --check` 均通过。全量 `pytest -q` 为 `1050 passed, 2 skipped, 10 subtests passed, 1 failed`；唯一失败来自环境缺失 `pydirectinput` distribution metadata 的 `tests/test_distribution.py`，不是本轮跟随代码失败。当前仍未做真实 Host/游戏输入验收。

## 2026-10-05 跟随前台消费边界与预测到达回归（当前断点）

### 已确认的实机根因

用户点击工作台按钮时，PoE2 可能仍在后台。日志已经给出直接证据：双人首帧 `status=accepted` 后，在 `2026-10-04 23:51:51` 记录：

```text
step=live_role_follow.waiting_game_foreground
reason=poe2_not_foreground pid=33984 hwnd=134540
```

这解释了“Host 看起来在提交输入，但人物不动”：ViGEm/Host 接收报告不等于游戏窗口实际消费报告。视觉 marker 保持旧位置时，旧链路仍让 `command_prediction` 前进，随后触发连续 `visual_rejected`、`repeated_visual_innovation_rejected` 和自动 recovery，于是界面表现为“已停止→按钮亮起→再次停止”。首帧配准本身在这批日志中是 accepted，不能把该问题归咎为首帧方向/比例失败。

### 本轮实现的边界修复

- `capture_test_page.py::Poe2CaptureTestPage._gate_live_follow_foreground()` 现在是所有程序跟随输出（实时角色和地图点击）的统一前台门。未检测到 PoE2 前台时：只释放一次已有 lease，保留 worker 和跟随状态，等待用户切回游戏；不会把焦点问题误判成定位失败，也不会立即发起全局重定位。PoE2 恢复前台后，以最新完整双人帧重置 tracker 视觉基线，再走 `cold_start/recovery_sync` 的严格新帧门。
- 页面新增 `_follow_foreground_release_sent` 边沿标志，避免 100ms timer 反复 `release_all()` 造成 IPC、日志和状态抖动。
- `program_output.py::ProgramGamepadOutput.write()` 修复 accepted 日志中 `remaining_ms` 先用后赋值的运行时异常；保留 Host 请求耗时、有效 axes、TTL、accepted 时间的证据。
- `multiplayer_follow/runtime.py::SimulatedFollowRuntime._tick_follower()` 的“预测位置靠近目标”分支改用控制器公开的 `constrained_duration_ms`，不再访问不存在的 `command_duration_ms`；预测位置仍不能独立确认到达，必须由视觉样本确认。

### 离线回归

```text
tests/test_program_gamepad.py                         7 passed
tests/test_poe2_capture_test_page.py                 79 passed
tests/poe2_live_terrain/test_multiplayer_follow_runtime.py
tests/poe2_live_terrain/test_command_role_tracker.py  65 passed
```

新增回归覆盖：工作台前台时不 arm、不写入；重复 tick 不重复释放；恢复 PoE2 前台并获得严格更新的双人帧后才发送第一个输出。离线测试通过 override 隔离宿主桌面状态，没有发送真实手柄/键盘/鼠标输入。

### 用户实机验证步骤

1. 保持 PoE2 已进入同一实例并完成双人首帧；不要让工作台或日志窗口覆盖前台。
2. 在工作台点击“开始跟随”，然后按约定切回 PoE2；如果点击时 PoE2 在后台，界面应显示“等待 PoE2 前台窗口”，而不是停止/重定位循环。
3. 切回后观察日志顺序：`foreground_resumed` → `sync_ready` → `program_output.acquired` → `program_output.accepted` → Host axes/TTL → 后续视觉位置变化。
4. 若只有 `program_output.accepted` 而没有视觉位移，需继续核对 controller 绑定和 Host ownership；不能据此宣称游戏已消费输入。

### 当前未闭合风险

- 尚未在用户当前 PoE2 实机上验证切回前台后的真实移动；该验证需要用户明确进行游戏测试。
- Host 的 `program.state` 是同步 IPC 调用，若 `host_request_ms` 持续超过控制周期，仍可能造成 UI/控制节拍抖动；当前仅记录和告警，未擅自改成异步协议。

### 2026-10-05 — 开始跟随后的 6 秒切窗缓冲

用户点击“开始跟随”后，页面为存在程序控制角色的会话建立
`_follow_output_not_before_ms = start_time + 6000ms`。在该时间点之前，跟随计时器可以运行定位/规划状态，但不会调用
`ProgramFollowOutput.arm()`、`apply()` 或底层 `ProgramGamepadOutput.start/write`，因此不会申请 Host lease，也不会提交手柄报告。
等待状态每秒记录一次 `step=follow_experiment.command_delay_waiting`，界面显示剩余秒数并提示切回 PoE2；6 秒到达后记录
`command_delay_elapsed`，再由统一 tick 按“前台门 → 视觉/运行时状态 → arm → write”顺序输出。

地图点击入口不再直接 arm。第一次点击只设置目标并启动跟随计时器，必须经过同一延迟门；之后的连续点击仍覆盖目标，但不会重新开始 6 秒倒计时。
实时跟随和地图点击跟随共用这条边界。停止、重新初始化或清图会清除延迟状态。无程序控制角色的纯模拟会话不受该输出延迟影响。

离线验证：`tests/test_poe2_capture_test_page.py` 80 passed；程序输出、双人 runtime/tracker 相关回归 72 passed；`compileall` 和
`git diff --check` 通过。新增回归确认延迟期间输出调用列表为空，目标点击不能绕过延迟，延迟到期后才出现 `start/write`。

实机测试：在完成双人实时定位后点击“开始跟随”，立即切回 PoE2；等待界面倒计时结束，再观察
`command_delay_elapsed` → `foreground_resumed/sync_ready` → `program_output.acquired/accepted`。本次未自动抢占窗口，也未发送实机输入。

### 2026-10-05 — 修复手动领队跳变误触发重定位

实机日志确认，6 秒等待结束后并不是启动门失败，而是手动领队被错误送入程序角色的创新拒绝门：

```text
command_delay_elapsed
visual_rejected role=<P1 manual> innovation=57.156
reanchor reason=manual_target_unobserved
follow_experiment.stopped
```

实时跟随原先把 `(leader, program_follower)` 一起交给 `CommandRoleTracker.observe()`。领队由用户手动控制，真实位置可以在一帧内发生远大于程序脉冲预测的位移；把这个位移和 follower 的 command odometry 比较会产生错误拒绝，随后进入重定位并释放手柄。

现在领队可见帧直接作为新的目标样本，并刷新该角色 tracker anchor；创新拒绝、连续拒绝计数和跟随重定位只作用于程序控制角色。较大的领队位移会记录为
`step=live_role_follow.manual_leader_visual_move`，并明确标记 `accepted_without_innovation_gate=True`。停止日志同时记录 `reason`、同步阶段、最近角色观察、前台等待和延迟门状态。

新增离线回归覆盖：手动领队发生大位移时跟随 runtime 保持 tracking、目标更新到新位置且不触发 recovery。页面测试现为 81 passed。

### 2026-10-05 — 由 10 月 4 日蓝色重叠反馈回溯出的回归边界

对照 2026-10-04 03:04 前后的实机日志和代码链路，确认重叠兼容改造之后新增的
`CommandRoleTracker` 创新门曾同时作用于手动领队和程序跟随者。03:26 的失败链是：

```text
command_delay_elapsed
→ visual_rejected role=P1 innovation=57.156
→ reanchor reason=manual_target_unobserved
→ follow_experiment.stopped
```

这说明首帧、6 秒前台门、Host 初始化都已经通过，真正的回归是把手动 P1 的视觉变化当成了
程序摇杆预测残差。现在手动领队可见帧直接更新跟随目标并刷新 anchor，只有程序控制角色进入
创新拒绝、连续拒绝计数和重锚；新增 `manual_leader_visual_accept` 日志用于实机核对。

验证测试已把视觉相位宽限设为 0，确保稳定态也覆盖该边界：相关页面聚焦测试 3 passed，
`compileall` 与 `git diff --check` 通过。重启程序后的验收顺序为：
`command_delay_elapsed` → `manual_leader_visual_accept` → `follow_experiment.motion`；
同一代不应再出现 `visual_rejected role=P1`。蓝色记录点重叠仍可能造成角色短时不可见，
此时应进入有限 `target_hold`/程序预测，而不是把领队跳变送入 innovation gate。

## [DIAGNOSTICS] 2026-10-05 — 跟随移动后停止的逐阶段诊断

### 本轮范围

用户反馈跟随开始后移动一段时间又停止，要求先记录完整调用链，再根据同一轮实机日志判断根因。本轮只增加只读诊断，不改变速度、创新阈值、路径规划、坐标变换或恢复策略。

### 现有实机证据

当前日志文件中可用的最近一次完整失败仍是 `2026-10-05 13:26:13`：P1 手动领队已通过 `manual_leader_visual_accept`，P2 输出已 `output_armed` 并连续收到三次 `output_accepted`，随后 P2 的视觉创新约 `14.3~14.5 native px`，连续三次 `visual_rejected` 后触发 `reanchor:repeated_visual_innovation_rejected`。因此这次停止点已经明确在 P2 的预测位置和视觉位置不一致，不能再归因于 P1 手动领队。

恢复阶段从 `13:26:55` 起长期记录 `poe2_not_foreground`，随后出现 `expected one running PoE2 process, found [31192, 22252]`。这说明恢复期间的前台窗口探测还受到多进程歧义影响；它是恢复卡住的独立问题，不能和最初 P2 视觉拒绝混为一个原因。

### 新增诊断边界

- `capture_test_page.py` 为每次跟随 tick 建立 attempt/完成 tick 编号，并记录上下文、双人帧时间戳和年龄、前台门、命令延迟门、同步阶段、运行时状态、目标距离、路线和局部运动诊断、输出决策/回执、异常和停止上下文。
- 每 5 个 tick 记录一次完整 `CommandRoleTracker` 快照（视觉锚点、输出区间、预测点、不确定度和最后视觉时间）；其他 tick 只保留轻量诊断，避免日志处理拖慢 100ms 控制节拍。视觉拒绝、重定位、输出失败和状态切换仍立即记录。
- `CommandRoleTracker.diagnostics()` 提供只读命令区间与预测快照。
- `ProgramGamepadOutput.snapshot()` 与 `ProgramFollowOutput.snapshot()` 提供不发 IPC 的 Host 边界本地状态；原有低频 `diagnostics()` 仍负责 Host status/state 探针。
- 停止日志在清理状态前保存同步阶段、tick/attempt、拒绝计数、遮挡角色、最后视觉点、前台 pid/hwnd、延迟门和输出快照，避免过去清理后只看到 `sync_phase=idle`。

### 验证

```text
pytest -q tests/test_poe2_capture_test_page.py          81 passed
pytest -q tests/poe2_live_terrain/test_command_role_tracker.py tests/test_program_gamepad.py  13 passed
python -m compileall -q src                            passed
git diff --check                                      passed
```

本轮没有发送真实手柄/键盘/鼠标输入，也没有擅自启动游戏。下一次实机测试应保持 PoE2 前台并完成一次“移动一段时间后停止”的复现；重点读取同一 tick 的 `output_result`、tracker 快照、`runtime_decision`、`visual_rejected` 和 `tick_end`，再单独判断预测速度、输入轴方向、Host 已接受但游戏未消费、视觉帧延迟四类假设。

## [CHECKPOINT] 2026-10-05 — 诊断日志策略与上下文续接规则

用户确认并要求长期保留的诊断策略：

- 每个跟随 tick 都记录轻量关键指标：输入帧、帧年龄、角色视觉点、tracker 锚点/预测摘要、运行时状态、路线/速度/无进展、输出向量/TTL、结果和状态转换。
- 完整 diagnostics（tracker 命令区间、预测协方差、路径细节、Host 本地快照）每 5 个 tick 记录一次；视觉拒绝、输出失败、重定位、状态变化和异常立即记录。
- 停止发生时，必须在清理状态前保存调用来源、停止原因、同步阶段、tick/attempt 计数、最后视觉位置、拒绝计数、前台 PID/HWND、输出快照和恢复上下文。
- Host `status/state` 只能低频探针调用，不能每 tick 做同步 IPC；诊断不得改变 100ms 控制节拍或把帧年龄推入 stale 分支。

该规则已经写入仓库 `AGENTS.md` 的 **Mandatory Checkpoint Discipline**。上下文压缩后必须先读取本文件和 `ITERATION_LOG.md` 的最新跟随条目，再继续排查；不得依据聊天摘要重新执行已经完成的日志补齐工作。

### 当前证据锚点（禁止与旧样本混淆）

- `2026-10-05 13:26:13` 是当前可用的最近一轮真实 PoE2 失败样本；后续 `13:50`、`14:04` 的 `role-a/role-b`、`Area:hash`、`900.0` 等记录来自离线页面测试，不能当作实机证据。
- 真实链路为：`sync_ready` → P2 `output_armed` → P2 三次 `output_accepted` → P2 `visual_rejected`（innovation `14.353/14.297/14.517`）→ `repeated_visual_innovation_rejected` → `reanchor` → `follow_experiment.stopped`。
- 该样本中 P1 已走 `manual_leader_visual_accept`，所以不能再把停止归因于 P1 手动领队创新门；首帧双人配准也为 accepted（pair confidence `0.8989`）。
- 恢复阶段另有 `poe2_not_foreground` 和多 PoE2 PID 歧义（`expected one running PoE2 process, found [31192, 22252]`），这是恢复失败的独立问题。

### 当前未闭合问题与下一步

尚未有带新 session id 的用户实机复现来区分：预测速度过高、输入轴/旋转映射错误、Host 已接受但游戏未消费、截图/模拟时序错位。下一步只收集同一个真实 `session_id` 的日志并按以下顺序分析：

`follow_experiment.armed` → `command_delay_elapsed` → `sync_ready` → `manual_leader_visual_accept` → `output_armed/accepted` → `diagnostic_snapshot` → `visual_accepted/rejected` → `tick_end/reanchor/stopped`。

在这条证据链闭合前，不修改速度、创新阈值、路径规划或坐标变换参数。

### 2026-10-06 实机“不移动”根因：重复处理同一失败视觉帧

最新实机 session `1a10da7b8fa-19d3f179850` 已闭合前台与输入边界：

- `waiting_game_foreground` 仅持续约 `1550ms`，随后 `foreground_resumed`；不是持续失焦导致的无输入。
- `04:01:05.012` 起 controller 2 连续出现 `output_accepted`，`acquired=True`、`inputOwner=program`，Host 已接收非零摇杆。
- 角色首个视觉移动点为 `(772.387, 927.987)`，说明视觉链路有变化；但随后页面反复使用相同的 `captured_at_ms=1791230465873` 与点 `(773.853, 931.283)`。
- `CommandRoleTracker` 的 `last_visual_at_ms` 保持 `1791230464108`，同一失败观测每个 100ms tick 都再次调用 `observe()`，`rejected_count` 从 `1` 累加到 `100+`，并触发 `repeated_visual_innovation_rejected` recovery。
- 因此当前首要 bug 是页面没有按“每个角色、每个捕获时间戳”去重失败视觉观测；去重缺失把一帧失败放大成连续失败，导致输出被释放/恢复链占用。

实现边界：增加每角色最近已评估视觉时间戳；相同或更旧时间戳不得再次累计拒绝或触发重定位，应继续使用有界预测并等待新鲜帧。不得修改速度先验、创新阈值、路径规划或重定位阈值。补充“重复失败帧不递增拒绝计数”的页面回归测试，再跑 focused follow/runtime 测试。

实现已完成（2026-10-06）：

- `capture_test_page.py` 增加 `_follow_last_evaluated_visual_at_ms`，在首帧同步、跟随启动、视觉接受/重基线和停止时正确建立/清理。
- 相同或更旧的捕获时间戳现在只走有界命令预测，不再重复调用 tracker、递增拒绝计数或申请 recovery；新增低频 `visual_duplicate_skipped` / `visual_old_frame_skipped` 诊断。
- 视觉连续重基线增加独立的 `continuity_max_gap_ms=3000`，与当前帧新鲜度 `700ms` 分离；当前帧仍新鲜且局部位移连续时，允许跨采集队列延迟进行重基线。
- 新增页面回归：重复失败帧不会二次计数；延迟但新鲜且连续的帧会重基线。

验证：`tests/test_poe2_capture_test_page.py -k live_follow` 21 passed；全页面测试 74 passed；`compileall` 和 `git diff --check` 通过。尚未发送真实输入；下一步由用户重启程序后复测跟随，重点确认日志出现 `visual_continuity_rebase`，不再在同一 `captured_at_ms` 上递增 `visual_rejected`。

### 2026-10-05 日志格式运行时错误确认与修复

混合日志中的离线页面场景在 13:41、13:43、13:46、13:48、13:50 多次触发同一异常；这些行使用
`role-a/role-b` 和 `Area:hash`，不能当作新的实机 PoE2 证据，但它们执行的是真实页面重定位代码路径：

```text
step=dual_motion.recovery_claimed reason=follow:command_prediction_unbounded
step=follow_experiment.tick_failed error=not enough arguments for format string
Traceback ... _request_live_follow_reanchor ... logging.warning ... record.getMessage
step=follow_experiment.stopped reason=tick_exception:TypeError
```

根因是 `_request_live_follow_reanchor()` 的 `reanchor` 日志格式串包含
`last_visual_positions=%s` 和 `output_snapshot=%s` 两个占位符，但调用参数漏传了
`self._follow_last_visual_positions`。进入重定位时，日志格式化本身抛出 `TypeError`，异常离开 tick，
随后统一异常边界以 `tick_exception:TypeError` 停止跟随。因此“进入该重定位分支就停止”在这些样本中是诊断代码的运行时错误，
不是新的速度或定位参数问题。真实 PoE2 的 `13:26:13` 样本仍保持原结论：P2 三次视觉创新拒绝触发重定位；
是否在用户最新实机运行中再次触发该格式错误，必须用新的带 `session_id` 实机日志确认。

已修复：补齐缺失的 `last_visual_positions` 参数；新增页面回归
`test_live_follow_reanchor_diagnostic_cannot_abort_recovery`，验证重定位日志成功写出且仍会执行
`save recovery context → start dual motion(recovery=True)`。聚焦测试 2 passed，`compileall` 和
`git diff --check` 通过。当前修复没有改变重定位条件、速度模型、创新阈值或路径规划。

下一次实机日志必须确认同一 `session_id` 下不再出现 `not enough arguments for format string`；若仍停止，
再分析其后第一条真实 `tick_failed` 或 `reanchor` 原因，不能把本次已闭合的日志格式错误重新当作算法问题。

### 2026-10-05 实机 session 1a10ae45e2c-179a6c1f7a0：预测与视觉速度失配

本次真实 PoE2 session 已闭合了此前的未决假设：

- `sync_ready` 后 P2 至少 9 次输出均被 Host 接收，`controller=2`、`acquired=True`，不是输出租约或 Host 未接收。
- P2 的视觉点持续有变化，最后一段 `observed_displacement=2.2678`、`observed_speed=10.2053`，并且 `command_observed_alignment=0.8524`、方向夹角约 `31.52°`；因此角色确实在移动，且不是纯粹的截图卡帧。
- `CommandRoleTracker(expected_speed=80)` 仍按固定速度回放 TTL 脉冲，最后三帧预测约为 `(508.48,1110.56)`、`(506.25,1114.87)`、`(504.40,1116.29)`，而视觉点约为 `(505.06,1092.75)`、`(506.25,1114.87)`、`(501.61,1096.92)`，创新距离 `18.139/18.??/19.571` 超过当前门限。
- 连续三次 `observation_rejected` 触发 `repeated_visual_innovation_rejected`，随后才进入 recovery；这次没有日志格式异常。
- recovery 首帧本身 accepted（pair confidence 约 `0.8746`），但恢复后的 session 因工作台夺取前台，进入 `poe2_not_foreground` 等待。这是停止后的门控现象，不是本次首个停止原因。

根因判断（verified）：当前跟随把“固定 expected_speed 的命令预测”放在视觉测量之前。只要实际角色速度低于模型，或某个方向分量受到游戏碰撞/输入消费影响，视觉点即使相对上一帧连续且方向合理，也会因相对预测点偏差被拒绝，三帧后错误重定位。当前创新门没有使用“上一可信视觉点的连续性”作为第二证据。

修复边界：不直接放宽全局创新阈值，也不把异常大跳变当成可信；应在 `CommandRoleTracker` 提供显式的连续视觉重基线能力，页面仅在“相对上一可信视觉点的位移处于单帧上限、时间戳新鲜、角色身份仍一致”时采用该能力，保留大跳变进入重定位。每次连续视觉重基线必须记录旧预测、视觉点、位移、输出区间和原因。

### 双人同目标与实时跟随的速度链路差异

已完成代码对比：

- `start_dual_target_experiment()` 只把每个 tick 的 `state.players` 视觉点直接传给 `SimulatedFollowRuntime.update_follower_position()`，没有 `CommandRoleTracker`，也没有用预测点做创新拒绝；因此它看起来稳定，速度由连续视觉帧隐含给出。
- `start_follow_experiment(live_role_follow=True)` 在相同 runtime 之外额外创建 `CommandRoleTracker(expected_speed=runtime.speed_units_per_second)`；`_make_follow_runtime()` 和 `ClosedLoopMotionController()` 当前都硬编码 `80.0`。该 tracker 用 Host 回执的 TTL 和固定速度先预测，再用视觉创新门过滤。
- `AdaptiveInputCalibrator` 虽然能根据 `MotionResponse(displacement, elapsed_ms)` 计算 `speed_gain`，但它只在 runtime 已经收到有效视觉 response 后更新；当前实时跟随的首次视觉拒绝发生在该闭环校准之前，形成“固定预测过快 → 视觉拒绝 → 无法获得校准样本”的闭环。

因此用户指出的速度问题是正确的：双人同目标不是证明 `80` 正确，而是它绕开了这条预测链。修复必须让实时跟随速度从实际视觉位移/时间逐步估计，并在未完成校准时降低预测权重；不能只把 `80` 改成另一个固定常数。

### 2026-10-05 — 两条跟随链路的对照审查（当前工作段）

用户要求先全面对比再改代码。当前已确认：两条链路共用 `SimulatedFollowRuntime`、`PathFinder`、`ClosedLoopMotionController`、`ProgramFollowOutput` 与 Host 输出适配器；区别不应扩散到移动底层，业务层只应替换目标来源。

- 双人同目标：地图点击设置 `runtime.remote`，每个 tick 将 `state.players` 的视觉点直接写回 follower，随后统一 `runtime.tick()` 和输出。
- 实时角色跟随：领队视觉点写入 `runtime.remote`；程序角色先进入 `CommandRoleTracker` 的命令预测、视觉观测和拒绝/重定位状态机，再把 tracker 样本写回同一个 runtime。
- 当前多出的固定速度预测和视觉拒绝层是实时跟随停止问题的主要差异；同目标链路不经过该层，所以同目标成功不能证明实时跟随的速度模型正确。
- 当前连续视觉重基线测试仍未触发，页面只保存 `_follow_last_visual_positions` 坐标而不保存对应捕获时间；下一步先打印 previous point、tracker `last_visual_at_ms`、帧时间差、视觉步长、连续性上限和拒绝原因，确认状态时间基线后再修复。

**工作边界：** 先复用同一 runtime/output，目标源使用显式 adapter；实时跟随只保留程序角色需要的视觉校准，不重复实现移动/寻路。速度必须由有效视觉位移与时间差估计（带限幅和 EWMA），固定值只作为冷启动先验，不作为长期速度。

### 2026-10-05 — 连续视觉校正未触发的确定性根因

离线最小复现确认：`_sync_live_follow_from_fresh_frame()` 将按 `actor_id` 建立的 `points` 直接赋给 `_follow_last_visual_positions`，而实时 tick 按 `RoleId.key` 读取。同步后缓存是 `role-b`，读取查找的是 `local-device:role-b`，因此上一视觉点永远为空，连续视觉步长无法计算，点被错误计入拒绝次数。

已修复为按 `role.key` 写入缓存，并保留 `actor_id` 只用于读取帧。修复没有放宽创新阈值，也没有把速度改成另一个固定常数。验证：连续视觉重基线与 tracker 回归 `8 passed`，页面全量测试 `83 passed`。

**下一步：** 继续检查所有实时跟随状态是否统一使用 `RoleId.key`，补齐每角色视觉时间戳和分支诊断，验证速度估计不会被静止帧压成零、异常跳变仍进入原有重定位，再运行同目标与完整回归。

### 2026-10-05 — 速度模型避免重复校准

对照 `CommandRoleTracker.record_output()` 与 `SimulatedFollowRuntime.update_follower_position()` 后发现第二个边界问题：tracker 的视觉 EWMA 已经由 native 位移/时间得到实测速度，但记录新输出时又乘了 `AdaptiveInputCalibrator.speed_gain`。校准器的倍率来自同一视觉响应，长期会把已测速度二次缩放。

已改为：`speed_samples == 0` 时，`expected_speed` 仅作为冷启动先验并可接受有界校准倍率；有视觉样本后，命令里程计直接使用视觉 EWMA，校准倍率只留给摇杆映射/脉冲时长。新增回归证明实测 10 native/s 在 `speed_gain=0.5` 时仍预测 10 native/s。相关跟随/tracker 页面回归现为 `91 passed`。

### 2026-10-05 — 对照审查与离线验证收口

已按“同一移动引擎、不同目标来源”完成调用链审查：双人同目标和实时角色跟随均经过 `SimulatedFollowRuntime` → `ClosedLoopMotionController`/路径规划 → `ProgramFollowOutput`；实时跟随额外只有领队目标适配、程序角色视觉/命令融合和恢复门，不再把地图点击链复制成另一套移动逻辑。

验证结果：runtime/闭环/tracker/运动回归 `100 passed`；页面、程序输出、双人产品会话回归 `93 passed`；整个 `tests/poe2_live_terrain` 回归 `396 passed`；`python -m compileall -q src` 通过；`git diff --check` 通过。没有发送真实手柄、键盘、鼠标或网络输入。

当前仍需实机验证一件事：同一 session 中 P2 视觉连续移动后，日志应出现 `visual_continuity_check` → `visual_continuity_rebase`，并且后续 tracker `estimated_speed` 应接近实测 native 位移/时间；只有大跳变才应出现 `visual_rejected`/`reanchor`。若实机仍停止，下一步只根据该 session 的第一条 `visual_rejected` 或 `tick_failed` 继续定位，不重复首帧或 Host 已接收的旧结论。

### 2026-10-05 — 实机 session 1a10b5003ed-16b99485a90 后段停止原因

- **已排除固定测试时长：** session 在 17:05:55 进入跟随，实际首次同步和输出发生在 17:07:17；没有总运行时长上限或 timeout stop。`10s` 只用于等待游戏前台，`10000ms` 是双人恢复冷却，均不是跟随总时长。
- **已确认停止链：** `markers_missing_grace`（两名角色同时不可见）→ 连续 3 帧 `wall_and_local_match_failed` → `recovery_required` → `dual_motion.recovery_claimed` → 释放手柄并停止当前跟随，保存恢复上下文。
- **证据：** 首次丢失帧 `1791191238009` 的 `candidates=[]`、两角色 `last_seen_at_ms=1791191237893`，原始截图均值约 `4.99`；此前正常截图均值约 `19.49`。失败帧不是角色正常移动造成的单个候选偏差，而是监控帧整体变暗/不可识别。后续恢复帧为全灰展示图，不能当作游戏截图。
- **当前判断：** 这是视觉采集/识别瞬时失效后，现有丢失宽限和恢复门过快收紧的行为问题；不是跟随时间限制，也不是 Host 输出租约到期。需要进一步确认该暗帧是游戏画面切换、截图后端短帧、监控区域状态变化还是识别阈值问题，并在确认前不要盲目放宽全局匹配阈值。
- **下一步：** 以 `1791191238009` 为入口检查截图源状态、帧序号、前后台状态、原始帧亮度/尺寸和丢帧统计；设计可恢复的短暂采集异常处理，保留预测/上一可信位置并延后恢复，而不是立即释放输出。验证后再修改 `DualVisualTracker` 的恢复门。

### 2026-10-05 — 恢复流程误用“停止”生命周期

- 用户确认真实跟随已经运行并移动了一段距离；上一轮只看到恢复 session 的尾部，不能把尾部 `follow_experiment.stopped` 当成从启动即停止。
- 根因边界：`_on_dual_worker_result()` / `_request_live_follow_reanchor()` 在恢复时调用 `stop_dual_motion()`；该方法无条件调用 `stop_follow_experiment(_preserve_recovery=True)`，清空跟随运行时、释放输出并记录 `follow_experiment.stopped`。这是恢复切换复用了用户停止生命周期。
- 设计约束：恢复期间必须保留跟随会话、目标来源、角色选择和预测上下文，状态显示为“重定位/恢复中”；恢复成功后继续同一跟随会话。用户点击停止、页面关闭或地图实例确实变化才允许进入终止生命周期。
- 当前实现边界：先拆出恢复过渡路径并补回归，避免修改首帧算法和移动底层；同时保证短暂视觉丢失不会把跟随永久置为 stopped。

### 2026-10-06 — 跟随恢复不再进入终止生命周期

- 已确认此前的 `follow_experiment.stopped` 是恢复流程调用 `stop_dual_motion()` 的副作用；真实运行已经移动一段路后才进入该分支。
- 已实现恢复过渡：实时跟随触发视觉恢复时，保留 `_follow_runtime`、`_follow_timer`、程序输出会话、角色选择、目标上下文和 `CommandRoleTracker`；只重建双人视觉 worker/首帧配准。日志改为 `recovery_transition`，不再写入跟随 stopped。
- 新首帧通过后由 `_maybe_resume_dual_follow_after_relocalization()` 调用 `_sync_live_follow_from_fresh_frame()` 原地重置视觉基线，清除 recovery pending，继续原 session；不会再次调用 `start_follow_experiment()`，避免递归走“停止旧会话”入口。
- 恢复冷却、首帧拒绝、恢复 worker 失败时保留命令预测并安排重试，不自动终止跟随。显式停止、页面关闭、地图上下文确实失效仍保留终止入口。
- 回归：`tests/test_poe2_capture_test_page.py` + 双人运动共 `109 passed`；`tests/poe2_live_terrain` `396 passed`；`compileall` 和 `git diff --check` 通过。
- 下一步实机验证：发生短暂视觉丢失时，日志应出现 `recovery_transition` / `recovery_resumed_in_place`，不应出现同一 session 的 `follow_experiment.stopped`；人物应继续用预测位移运行并在新鲜帧到达后校准。

### 2026-10-06 — 自动异常不再结束活动跟随会话

- 用户确认真实跟随已经移动一段路后才出现 `follow_experiment.stopped`；这不是启动失败，也不是测试时长限制。恢复链路之外仍有四个自动终止入口：退休截图线程延迟重启未传递 `preserve_follow`、双人 worker/同步异常直接调用普通 `stop_dual_motion()`、跟随 tick 异常调用 `stop_follow_experiment()`、程序输出异常调用 `stop_follow_experiment()`。
- `Poe2CaptureTestPage._resume_dual_motion_restart()` 现在根据活动实时跟随状态传递 `preserve_follow`；worker 失败、结果分发失败和同步 tick 异常统一走可重试的恢复过渡，释放当前输出但保留 runtime、timer、session、角色和预测上下文。
- `_tick_follow_experiment()`、地图上下文暂时缺失、跟随目标上下文暂时不完整和程序输出异常均改为“保持会话、释放当前输出、下一 tick/恢复 worker 重试”，不再写入 `follow_experiment.stopped`。`stop_follow_experiment()` 只由用户停止、显式实验切换、换图/清图和页面关闭路径调用。
- `_follow_stop_reason` 不再由自动 reanchor 写入，避免用户之后主动停止时把恢复原因伪装成停止原因。新增回归覆盖：延迟恢复保留标志、tick 异常保持 runtime/timer、地图变换暂时失效不清理跟随会话。
- 地图实例暂时不一致时，恢复提示也改为“等待重新定位（会话保留）”，不再显示“已安全停止”；输出仍保持中性，直到有效上下文恢复。
- 验证：`tests/test_poe2_capture_test_page.py` 86 passed；`tests/poe2_live_terrain` 396 passed；`python -m compileall -q src` 和 `git diff --check` 通过。尚未发送真实输入，下一步实机确认同一 session 的自动异常后不再出现 `follow_experiment.stopped`。
### 2026-10-06 — 同一视觉失配 episode 不再重复申请重定位

- 实机日志确认：跟随角色 `Metadata/Characters/Dex/DexFourb` 的同一视觉点约
  `(712.20, 920.85)` 连续被 `CommandRoleTracker` 的 innovation gate 拒绝；连续性检查本身通过，
  但页面每个 follow tick 都再次调用 `_request_live_follow_reanchor()`。
- `10,000ms` 页面冷却只挡住了真正的 worker 重启，没有挡住每次申请前的状态判断、输出释放、
  retry 调度和日志，因此同一 episode 内仍出现几十次 `recovery_cooldown` / `reanchor_rejected`，
  造成移动不丝滑。
- 根因边界：恢复预算是页面级时间冷却，但缺少跟随会话级的“当前恢复 episode 已申请”状态。
- 修复边界：实时跟随首次申请恢复后设置 episode 锁；episode 锁期间只保留预测和一次性节流诊断，
  不再次申请、释放输出或调度重试。新鲜视觉帧成功完成 `sync_live_follow`，或未处于恢复 pending
  时重新接受视觉观测，才清除 episode 锁。用户主动停止/重新启动跟随也清除锁。
- 验证要求：同一失配连续 100 个 tick 最多一次 recovery claim、一次 worker/retry 入口；恢复成功后
  下一次独立失配仍可再次申请。下一步先运行 focused tests，再更新断点记录结果。
- 实现结果：新增 `_follow_recovery_episode_active`、原因和抑制计数；`_request_live_follow_reanchor()`、
  capture/worker failure 及 dual-motion recovery revision 共享该锁。锁内只保留有界预测和节流日志，
  不重复 claim 或释放输出；只有恢复 worker 已失败且 retry owner 空闲时才允许已有 retry 入口排队一次。
  `_sync_live_follow_from_fresh_frame()`、有效视觉接受/连续性
  重基线、重新启动和用户停止清除锁。
- 验证完成：新增的 100 tick 单 episode 回归通过；`tests/test_poe2_capture_test_page.py` 与相关跟随/
  tracker 共 `178 passed`，`tests/poe2_live_terrain` `396 passed`，`compileall` 与 `git diff --check`
  通过。尚未发送真实输入，下一步实机观察同一 session 是否只出现一次 `recovery_episode_started`，
  恢复成功后出现 `recovery_episode_cleared`。
- 追加边界：episode 内如果恢复 worker 失败，仍只通过已有的一秒 retry owner 重新排队一次；
  `_follow_recovery_retry_scheduled` 防止每个 tick 重复排队，episode 锁不会把恢复能力永久吞掉。
- 最新验证：页面 focused suite `87 passed`，相关 PoE2 suite 先前 `396 passed`；新增 retry 保持逻辑的三项
  恢复回归通过，未发送真实输入。
\n+## 2026-10-06 — 实机 session 1a10dbac8d6-15ea0f8d610 重定位取证（只读）\n+\n+本轮没有修改代码，也没有发送真实输入。最新 session 在 04:21:47-04:24:20 期间触发了三次独立恢复 episode：\n+\n+1. 04:22:38 `repeated_visual_innovation_rejected`：跟随角色最后有效视觉帧为\n+   `captured_at_ms=1791231752079`，随后约 6.1 秒没有新鲜位置。新帧仍在\n+   `(625.34,1034.64)` 附近，而命令预测已到 `(642.67,1046.37)`，innovation 约\n+   `20.1-20.6`，连续 3 次拒绝后恢复。日志同时记录 `visual_hold` /\n+   `unchanged_marker_after_output`，因此这是视觉采集停滞或角色图标未更新造成的误恢复，\n+   不是单纯首帧匹配失败。该触发时没有保存同一 `failed_frame_id` 的 raw 快照；恢复完成后的\n+   最近证据帧在 `data/poe2_live_terrain_test/occlusion_diagnostics/1791231778856-1791231778856-5b9997ec`。\n+   恢复耗时约 19.6 秒，`dual_first_frame.worker_result elapsed_ms=19555.6`。\n+\n+2. 04:23:11 `occluded_role_has_no_safe_candidate`：日志中 P1 位置\n+   `(657.55,925.19)` 被地图判为 `wall=255, collision=255, clearance=0`，P2 目标也无可接受路线；\n+   但 `contact_evidence.reason=progress_observed`，并非确认撞墙。该 episode 更像是定位坐标/\n+   地图变换与墙体栅格的边界不一致，导致“角色实际可走”被错误归类为无安全候选。相关证据帧：\n+   `.../1791231791037-1791231791037-70447db5` 和\n+   `.../1791231791137-1791231791137-b55eccff`。第二次恢复耗时约 18.8 秒，\n+   `dual_first_frame.worker_result elapsed_ms=18828.4`。\n+\n+3. 04:24:11 `motion:markers_missing`：失败帧 `1791231851519` 的 `raw.png` 实际内容是\n+   浏览器页面而不是 PoE2 小地图；对应目录为\n+   `.../1791231851519-1791231851519-1886f557`，`mask_0.png` 与 `mask_1.png` 均为空。\n+   这次是截图源/前台窗口边界问题，不能用视觉阈值或重定位参数解决。用户主动停止发生在\n+   恢复完成前，因此这次没有 `worker_result`。\n+\n+当前诊断结论：本 session 的三次恢复分别属于“采集帧停滞”“坐标落在错误墙体栅格”“截图抓到非游戏窗口”，不是同一根因。恢复速度主要由双人首帧全局匹配耗时决定（约 18.8-19.6 秒）；降低频率应先阻止这三类误触发，不能直接放宽统一阈值。后续优化前必须分别验证：新鲜帧时间连续性、坐标/墙体边界一致性、截图前台窗口身份。\n+

补充：第三次 episode 虽只有一次 `recovery_claimed`，但恢复 worker 未出结果时从 04:24:11.662 到 04:24:19.241 约每 1.1 秒再次 `dual_first_frame.compute_started`，共 8 次。说明当前 episode 去重没有覆盖失败重试调度，后续需要单独限制恢复 worker 的重试节奏和并发。
