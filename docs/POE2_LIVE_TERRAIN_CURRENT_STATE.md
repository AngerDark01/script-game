# PoE2 实时地形与人物定位断点

## 文档用途

这是 PoE2 实时地形任务的唯一阶段断点文档。每次暂停或切换阶段时，更新本文件中的状态、已完成内容、当前假设、未决问题和下一步入口，避免下一次开发重新推断上下文。

最后更新：2026-09-19

当前状态：**引擎批次 1 已完成，等待继续 PoE2 实验接入**

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

### 不再使用小地图中心作为人物位置

旧导航逻辑可以在某些场景下把小地图中心当成玩家局部坐标。PoE2 不能采用这个假设：

- 人物在小地图中不一定位于中心；
- 多开或多人场景下，小地图可能同时出现多个角色；
- 中心位置只能是截图几何信息，不能代表被跟踪人物。

当前单人版本也必须真正识别人物图标。即使人物恰好接近中心，也必须由识别结果得到该坐标，而不是由默认中心生成。

### 单人先做，多人预留契约

当前业务策略只选择一个人物，但引擎结果不能设计成永远只有一个坐标：

```text
引擎输出：0..N 个实体候选及其观测证据
PoE2 单人业务：选中唯一可信候选
PoE2 多人业务：以后增加当前控制角色选择策略
```

多人识别策略暂不实现，但候选列表、置信度、观测时间和 tracking id 等字段应在通用契约中预留。

## 分层规则

### 实验室/业务层

PoE2 实验目录负责业务组合和 PoE2 规则：

- native terrain 快照如何转换成 PoE2 定位参考图；
- PoE2 小地图的监控配置；
- PoE2 人物图标的颜色、形状或模板策略；
- 单人业务如何选择当前人物候选；
- 初始化、抓取、开始监控、停止监控的实验流程；
- PoE2 页面如何显示实时小地图、人物 marker、轨迹和诊断信息；
- 实机日志和样本归档。

实验代码暂放在 `tools/experiments/poe2_live_terrain/`。它只能组合引擎能力，不能复制一套定位或截图引擎。

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

### 2026-09-19 本阶段开发批次 1

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

本批次没有修改 `NavigationCore`、导航页、PoE2 页面、输入或网络代码。

### 实时地形采集和展示

- 外部采集器位于 `D:\ACloud\poe2-map-research\experiments\live-terrain-preview\live_preview.py`。
- 现有适配器位于 `src/auto_modules/adapters/poe2_live_terrain/`。
- 当前流程是 `initialize -> capture -> manifest/NPZ 校验 -> TerrainSnapshot -> 内存保存 -> 地图展示`。
- 当前地图快照保存在内存；测试阶段可以由 `TerrainDebugArchive` 显式归档。
- `data/maps` 不作为 PoE2 实时地图写入目标。
- `tools/experiments/poe2_live_terrain/` 当前只是源码试验导出边界，不应与正式适配器形成第二套采集实现。

### 当前 UI

- 主窗口已有“PoE2 地形”页面。
- 页面目前支持初始化、手动获取地图、清空地图和地图展示。
- 当前页面还没有真实小地图监控循环、人物定位、轨迹显示或定位状态机。
- 主窗口仍保留开发工作台页面，以及正式的手柄和局域网页面。

### 当前验证

- PoE2 地形采集和展示的 focused tests 已通过。
- 现有地形样本尺寸为 `2416 x 2277`。
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

## 本阶段的 PoE2 实验业务

计划新增或调整：

- `tools/experiments/poe2_live_terrain/terrain_reference.py`：把 `TerrainSnapshot` 转成定位用参考数据，不从 `QPixmap` 反推；
- `tools/experiments/poe2_live_terrain/calibration.py`：保存小地图像素到地图参考像素的比例、方向和偏移；
- `tools/experiments/poe2_live_terrain/player_policy.py`：单人场景选择唯一可信人物候选；
- `tools/experiments/poe2_live_terrain/runtime.py`：组合截图、识别、全局/局部定位、轨迹和日志；
- `src/auto_modules/ui/modes/poe2_live_terrain/page.py`：增加实时小地图预览、开始/停止监控、定位状态和人物显示；
- PoE2 页面关闭时停止截图循环并释放帧缓存。

UI 通过注入协议使用实验 runtime，不在通用 UI 组件中写 PoE2 定位算法。

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
7. 确认首帧定位来源为全局匹配，地图上的人物 marker 落在实际人物位置。
8. 在游戏中移动人物，确认 marker 和轨迹随人物移动，方向和相对距离一致。
9. 暂时遮挡或离开可识别区域，确认 UI 显示定位失败/恢复状态，不伪造中心坐标。
10. 停止监控并确认截图循环退出、配置窗口恢复可编辑。

真实 PoE2、桌面截图和人物移动只在明确的手动验收阶段执行；默认单元测试使用合成帧和 fake capture，不发送真实输入。

## 下一次继续入口

从 [2026-09-19-poe2-single-player-localization-implementation-plan.md](plans/2026-09-19-poe2-single-player-localization-implementation-plan.md) 的 Task 4 开始：先实现 PoE2 terrain reference，再实现单人候选选择与校准，然后接入实验 runtime 和页面监控显示。

本文件在以下事件后必须更新：引擎契约确认、实验目录职责变化、真实样本校准完成、首帧定位验证、轨迹验证、定位失败规则变化或阶段范围变化。
