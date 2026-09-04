# 通用图像处理底座与旧链路兼容桥设计

## 目标

把当前旧 HSV/小地图链路中已经可复用的图像处理、候选几何和导航投影能力下沉为游戏无关的底层模块；让旧实现逐步委托它们，同时保持所有现有运行入口、参数和业务结果可用。

## 范围

本阶段包含：

- 新建 geometry-aware 的图像 Artifact 与坐标回投契约；
- 提取当前 HSV 链路已经使用的增强、颜色、边缘、形态学、连通域和 mask 融合原语；
- 建立可由 profile/UI 保存和调参的预处理 recipe/pipeline；
- 让旧 `HSVRecognizer` 的预处理、mask 和组合实现委托这些通用原语；
- 新增 `MapFrameEvidence`，并为 `MapStitcher` 提供不破坏 `add_frame(...)` 的 typed ingress；
- 提取“世界地图向量 → 游戏视野目标点”的纯导航投影数学，并保持旧 `motion_mapping` API。

本阶段不包含：

- Portal、Loot、事件状态机或 GUI 的业务重写；
- 新游戏、PoE 工作流、战斗、拾取逻辑；
- 改写 `ActionCommand` / 虚拟手柄协议；
- 窗口模式、多显示器和客户区自动校准；
- 特征点匹配、运动检测和 ML 检测器。

## 分层与依赖

```text
core.perception.preprocessing
  ├─ geometry / artifact / recipe
  └─ pure pixel and mask operations
             ↓
core.mapping.evidence       core.navigation.projection
             ↓                    ↓
legacy HSV facade → MapStitcher  legacy motion_mapping
             ↓                    ↓
legacy mapping / localization / event / GUI composition
```

禁止反向依赖：

```text
preprocessing -/-> HSVRecognizer, GUI, Portal, Loot, events, input
mapping.evidence -/-> GUI, perception algorithms
navigation.projection -/-> mouse, MotionController, game profile
```

## 核心设计决策

### 1. Artifact 保留坐标变换，而不是只传递 ndarray

每次 crop、resize 或 pad 后都必须保存“当前像素坐标回到原始帧坐标”的变换。检测器可在处理后的 ROI 上工作，最终仍能产出源帧坐标的检测框。

```text
FrameContext 原图
  → ImageArtifact(image, geometry)
  → crop / resize / pad
  → algorithm result
  → geometry.map_*_to_source(...)
```

几何契约复用现有 `CoordinateSpace`、`BoundingBox`、`FrameContext`，不另建坐标枚举。

### 2. 通用模块只提供操作，不认识游戏语义

通用层提供：

- gamma、Gaussian/median blur、LAB-CLAHE、top-hat、百分位归一化、通道缩放；
- BGR/灰度/HSV 转换、Canny；
- HSV range mask、阈值、开闭运算、膨胀/腐蚀、连通域过滤；
- 饱和度 mask、圆形 mask、加权 mask fusion；
- crop、resize、pad 与坐标回投。

旧层保留：

- 墙、雾、玩家的 HSV 范围；
- transparency score 作为“墙”策略的选择；
- 小地图中心玩家假设、玩家清除半径、饱和图标排除区；
- wall/edge 权重和阈值；
- 任何 Portal、Loot、游戏画面布局语义。

### 3. 旧 API 是 facade，不是废弃入口

`core/vision/hsv/*.py` 继续接受 `recognizer` 和原有参数，负责读取旧参数并编排业务选择；它们只把具体的 image operation 委托给 `core.perception.preprocessing`。

因此既有的：

```python
recognizer.extract_combined(image, player_pos=...)
stitcher.add_frame(img, match_mask, save_mask, fog_mask, ...)
calculate_movement_click(...)
```

保持可用。

### 4. MapStitcher 通过新增入口升级输入契约

`MapFrameEvidence` 收集 match/save/fog mask、玩家位置、坐标空间和可选原始帧信息。新增：

```python
stitcher.add_evidence(evidence)
```

它只解包 evidence 后调用现有 `add_frame(...)`。拼接、加权合并、关键帧、地图包存储算法不改变。

### 5. 两种映射保持独立

- `ImageGeometry`：处理后图像坐标 → 源截图坐标；
- `DesktopCoordinateMapper`：截图坐标 → 物理屏幕坐标；
- `navigation.projection`：世界地图位移 → 游戏视野中的目标点。

第三种属于导航数学，不与通用 desktop spatial mapping 合并。

## 验收条件

1. 新通用模块没有导入 GUI、legacy recognizer、Portal、Loot、events 或输入控制器。
2. crop/resize/pad 后 point 与 BoundingBox 能精确回投源帧。
3. 旧 HSV 的既有回归测试保持通过；新增代表性帧证明提取后输出相同。
4. `MapStitcher.add_frame(...)` 不变，`add_evidence(...)` 给出同样结果。
5. `calculate_movement_click(...)` 与 `calculate_mapped_target_click(...)` 的既有行为保持，通过新的纯数学投影实现。
6. 完整相关测试、compileall 和 diff 检查通过。

## 迁移后再做的事项

完成本阶段后，Portal/Loot 可各自以 adapter 方式开始复用同一套 Artifact、预处理、模板/NMS 和坐标回投能力；不在本阶段提前迁移。
