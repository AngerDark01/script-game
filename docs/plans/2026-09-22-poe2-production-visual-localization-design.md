# PoE2 正式实时视觉定位设计

## 目标

把已经在数据采集测试页和实机链路中验证通过的 PoE2 混合定位能力接入正式 `PoE2 实时地形` 页面，使完整地图能够持续显示人物真实位置与轨迹。

本阶段只负责定位和可视化，不执行 Xbox、键盘、鼠标、Host、LAN、路径规划或自动移动。

## 核心决策

采用“参考导航模式状态流、保留 PoE2 全局定位实现”的方案：

```text
导航模式语义                 PoE2 实现
NEED_GLOBAL             -> 读取一次人物内存锚点并立即截图
global match            -> 锚点约束的方向/镜像/比例/平移注册
LOCAL_TRACKING          -> 连续小地图视觉局部匹配
RECOVERY_REQUIRED       -> 下一帧允许一次内存锚点恢复
```

不直接依赖导航页面、`NavigationCore` 或导航业务任务。PoE2 继续使用已验证的 hybrid controller/session，因为它还负责两个导航状态机没有的必要约束：

1. 内存锚点必须先读取，截图必须紧跟其后，不能拿新坐标匹配旧截图。
2. 每个恢复 revision 最多读取一次内存；恢复失败后不能每帧重复读取。

## 运行流程

```text
用户获取完整地图
  -> 正式运行时绑定 TerrainSnapshot 和当前监控配置
  -> 用户点击“开始监控”
  -> NEED_ABSOLUTE
  -> 单次读取内存锚点
  -> 立即截图并构建视觉证据
  -> 绝对注册成功
  -> LOCAL_TRACKING
  -> 每帧截图并执行纯视觉局部定位
  -> 在完整地图上更新当前位置和轨迹
  -> 局部视觉失败
  -> RECOVERY_PENDING
  -> 下一 tick 单次读取内存锚点并立即截图
  -> 成功：回到 LOCAL_TRACKING
  -> 失败：进入 RECOVERY_REQUIRED，停止自动内存读取
```

`RECOVERY_REQUIRED` 下保留显式“重新定位”能力。用户触发后只开放一个新的恢复 revision，而不是启动连续内存轮询。

## 模块边界

### 通用底层能力

- `core/localization`：定位结果、局部匹配等通用能力。
- `core/vision`：识别和视觉证据。
- `core/spatial`：截图区域与坐标几何。
- 这些模块不感知 PoE2、地图实例、内存接口或正式页面。

### PoE2 hybrid 定位域

- `HybridLocalizationController`：导航式状态流、轨迹、恢复 revision。
- `Poe2HybridLocalizationSession`：锚点准备、截图、证据构建和 controller 更新顺序。
- `Poe2MemoryAnchorProvider`：一次性读取人物锚点。
- `AnchoredAbsoluteRegistrar`：锚点约束的绝对注册。
- `VisualLocalTracker`：固定方向、镜像、比例后的局部视觉跟踪。

### 产品运行时适配层

增加一个薄的 PoE2 产品运行时，职责仅为：

- 保存当前 `TerrainSnapshot` 和监控配置。
- 创建、停止和替换 hybrid experiment。
- 把 session 输出与最近一帧视觉证据合并为正式页面可消费的状态。
- 暴露 `start/stop/tick/retry_recovery/configure_snapshot/configure_monitor`。

它不实现匹配算法，也不持有 Qt timer。

### 正式页面

`Poe2LiveTerrainPage` 是唯一产品定位 owner：

- 唯一 `monitor_timer` 驱动产品运行时。
- 获取地图后调用 `configure_snapshot()`。
- 开始监控后显示首帧全局定位状态。
- 每 tick 更新小地图预览、匹配特征、定位状态、大地图人物点和轨迹。
- 显示来源、置信度、恢复 revision、失败原因和内存读取次数。

数据采集页继续用于截图、样本、拼图和算法诊断，但正式页面装配时不再让它持有另一套活动的 hybrid session/timer。

## 状态与错误规则

| 状态 | 内存读取 | 截图 | 页面行为 |
|---|---:|---:|---|
| `NEED_ABSOLUTE` | 单次 | 锚点后立即截图 | 显示“正在首帧定位” |
| `LOCAL_TRACKING` | 否 | 每帧 | 更新位置和轨迹 |
| `RECOVERY_PENDING` | 单次 | 锚点后立即截图 | 显示“正在恢复定位” |
| `RECOVERY_REQUIRED` | 否 | 否 | 保留最后可信位置，提示重新定位 |
| `STOPPED` | 否 | 否 | 停止 timer，清理即时预览 |

任何失败帧都不能向轨迹追加过期位置。最后可信位置只用于界面说明，不伪装成本帧新位置。

## 页面展示

- 完整地图继续复用 `present_localization_overlay()`，不复制渲染算法。
- 当前可信位置绘制人物标记，历史可信位置绘制轨迹。
- 小地图区域展示最近截图或处理后帧。
- 匹配区域展示最近 wall mask/特征图。
- 状态栏显示模式、来源、置信度、当前位置、恢复版本、读取次数和失败原因。

## 日志

每个关键步骤使用结构化字段记录：

- `step=product_localization.configured`
- `step=product_localization.started`
- `step=product_localization.state`
- `mode/source/confidence/position/recovery_revision/read_count/reason`
- `step=product_localization.stopped`

日志不得包含连续原始内存数据，只记录读取次数、实例标识和结果状态。

## 验证

1. 产品运行时单元测试：配置、启动、tick、停止、替换 snapshot、显式重试。
2. session 测试：严格验证 `anchor -> capture -> update` 顺序。
3. controller 测试：局部失败自动进入一次性恢复；恢复失败后不连续读取。
4. 正式页面测试：唯一 timer、状态展示、大地图 overlay、停止行为。
5. composition 测试：正式页注入 hybrid 产品运行时；不依赖输入或网络模块。
6. PoE2 聚焦回归、`compileall`、`git diff --check`。

实机验收应看到：首帧 `anchored_absolute`、后续连续 `visual_local`；正常视觉帧中内存读取次数不增加；制造视觉丢失后最多增加一次读取并恢复。
