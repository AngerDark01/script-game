# PoE2 导航兼容的混合定位设计

## 状态

已确认采用方案 A：首帧和视觉丢失恢复使用“内存人物锚点 + 局部形状注册”；正常跟踪复用原导航模式的多帧位移预测，局部形状匹配只用于纠偏和备用恢复。

## 目标

让 PoE2 从内存转换得到的完整地图能够支持稳定的实时人物位置跟踪，同时保持与原绘图导航模式一致的正常跟踪语义：

```text
首帧/恢复：一次内存读取 -> 锚点附近形状注册
正常跟踪：上一帧/当前帧位移预测 -> 全局位置更新 -> 局部形状纠偏
视觉丢失：局部纠偏失败 -> 下一恢复版本只读一次内存
```

本阶段只做定位和可视化，不执行 Xbox、键盘、鼠标、Host、LAN、路径规划或自动移动。

## 不变边界

- 不修改第一页绘图模式的业务代码和配置。
- 不把 PoE2 术语放进通用定位、位移预测和墙体归一化能力。
- 不以固定周期读取游戏内存。
- 不在定位失败后重复读取内存或使用过期位置追加轨迹。
- 不改变已经确认的单人中心模式语义；多人 marker 作为后续独立的 `LocalPlayerProvider`。

## 现有链路审计

### 原导航模式

`src/auto_modules/core/localization/localize_pipeline.py` 的正常路径为：

1. `HSVRecognizer.extract_combined()` 产生 `match_mask` 和 `wall_mask`。
2. 已定位且存在上一帧时，调用 `estimate_phase_displacement(prev_wall_mask, wall_mask)`。
3. 通过质量阈值、最大位移和跳变规则验证位移。
4. 使用 `current_pos - shift * draw_scale` 更新全局位置。
5. 位移无效时才进入有限范围的模板墙体匹配。
6. 模板匹配失败后清空连续跟踪状态，下一轮请求全局定位。

### 当前 PoE2 链路

1. `Poe2HybridLocalizationSession` 采集一帧并构建 `HybridFrame`。
2. `HybridLocalizationController` 管理首帧、局部跟踪和恢复状态。
3. `AnchoredAbsoluteRegistrar` 已经以内存人物坐标为中心裁剪局部 terrain，并搜索角度、镜像、比例和平移。
4. `VisualLocalTracker` 当前忽略 `previous_frame`，每帧以旧 translation 为中心做半径 `96px` 的 Chamfer 局部匹配。
5. 当前实现尚未复用原导航模式的帧间位移预测，因此正常移动路径与原导航模式不一致。

## 关键设计

### 1. 统一墙体匹配表示

内存 terrain 当前主要来自可行走区域边界，实时小地图当前来自视觉 `wall_mask`。两者在墙体厚度、边界偏移、比例和噪声方面不保证同构。因此增加领域中立的墙体表示适配层：

```text
visual wall mask
    -> 去人物/文字/图标噪声
    -> 闭运算和小组件清理
    -> 厚度归一化
    -> canonical boundary/distance representation

terrain walkable/explored
    -> boundary extraction
    -> 相同厚度归一化
    -> canonical boundary/distance representation
```

不做颜色平均；匹配依据是轮廓、连接、缺口和转角等形状信息。标准化必须是纯函数，不能读取 UI、游戏进程或业务状态。

### 2. 首帧和恢复

首帧允许一次锚点读取，随后立即截取小地图。以锚点为中心裁剪局部 terrain：

- 首帧：搜索角度、镜像、比例和局部平移。
- 同实例恢复：锁定已确认的角度、镜像和比例，只搜索锚点附近平移。
- 实例变化：清空旧 registration、前帧、轨迹和位置，拒绝使用旧 terrain。

首帧和恢复都调用同一个 `AnchoredAbsoluteRegistrar` 契约，不由控制器实现算法细节。

### 3. 正常跟踪

正常跟踪严格采用原导航模式语义：

1. 保存上一帧 canonical wall representation。
2. 使用 `estimate_phase_displacement()` 计算帧间位移及质量。
3. 依据当前相似变换把 minimap 位移转换为 terrain 全局位移；位移方向必须包含旋转、镜像和比例变换。
4. 对质量、最大位移和位置跳变进行门控。
5. 通过成功的位移预测更新位置和轨迹，来源标记为 `visual_f2f`。
6. 仅在位移质量不足或需要纠偏时，在预测位置附近做小半径 canonical 形状匹配。
7. 位移和局部纠偏都失败才进入 `RECOVERY_PENDING`。

局部 Chamfer 匹配不再作为每一帧的主路径，也不回退全图搜索。

### 4. 状态和内存读取

```text
NEED_ABSOLUTE
  -> 一次 read_once + capture + anchored registration
  -> LOCAL_TRACKING

LOCAL_TRACKING
  -> f2f displacement success: stay LOCAL_TRACKING
  -> f2f/shape failure: RECOVERY_PENDING

RECOVERY_PENDING
  -> 当前 recovery revision 允许一次 read_once
  -> success: LOCAL_TRACKING
  -> failure: RECOVERY_REQUIRED

RECOVERY_REQUIRED
  -> 停止自动截图和内存读取
  -> 只有 retry_recovery() 创建新 revision
```

失败帧不追加旧位置；最后可信位置只用于界面提示。

## 数据契约

新增或扩展的通用数据应保持领域中立：

- `CanonicalWallFrame`：归一化墙体图、局部人物点、帧号、时间戳和诊断。
- `FrameDisplacement`：局部位移、质量、距离、来源和拒绝原因。
- `SimilarityTransform2D`：角度、镜像、比例、平移。
- `AbsoluteRegistration`：全局位置、变换、锚点误差、实例和诊断。

PoE2 适配器只负责：内存坐标读取、terrain reference、监控配置和证据构建。通用算法不感知 PoE2 area instance 或内存地址。

## 调用链

### 首帧

```text
page.start
 -> product_runtime.start
 -> session.tick
 -> controller.prepare_capture
 -> memory_anchor.read_once
 -> frame_source.capture
 -> evidence_builder.build
 -> canonicalize terrain/frame
 -> anchored_registrar.register
 -> controller.accept_absolute
 -> publish state
```

### 正常跟踪

```text
timer.tick
 -> session.capture/build
 -> canonicalize current wall frame
 -> phase_displacement(previous, current)
 -> transform displacement by fixed similarity transform
 -> validate quality/jump
 -> accept visual_f2f
 -> optional local shape correction near predicted origin
 -> publish position/trajectory
```

### 视觉恢复

```text
f2f rejected
 -> bounded local canonical shape correction
 -> failure: RECOVERY_PENDING
 -> next tick consumes one memory read
 -> anchored registrar with prior transform
 -> success/failure state transition
```

## 验证策略

### 纯函数测试

- visual/terrain 厚度不同但拓扑相同的墙体归一化结果可匹配。
- 旋转、镜像、比例和平移后能恢复已知变换。
- 位移符号、旋转和镜像转换正确。
- phase displacement 的低质量、大跳变和异常输入被拒绝。
- 局部形状搜索不会回退全图。

### 状态机测试

- 首帧只读取一次内存。
- 连续成功 f2f 不增加内存读取。
- f2f 失败后最多一次恢复读取。
- 恢复失败后连续 tick 不继续读取。
- 显式 retry 才创建新的 recovery revision。
- 失败帧不追加轨迹。

### 样本回放

使用 `data/poe2_live_terrain_test/samples` 和现有 probe 样本验证：

- 首帧角度和位置；
- 正常移动方向；
- 轨迹连续性；
- 墙体厚度变化；
- 文字、传送门和粗块噪声；
- 局部纠偏；
- 视觉丢失和恢复。

### 实机验收

1. 首帧 `memory_read_count == 1`。
2. 正常移动期间读取次数不增加。
3. 位置主要由 `visual_f2f` 更新，局部形状只做纠偏。
4. 人物移动方向和大地图轨迹方向一致。
5. 视觉丢失最多增加一次内存读取。
6. 恢复失败后不重复读取、不刷屏、不完整重绘造成卡顿。

## 风险和暂不解决的问题

- 如果内存 terrain 本身缺失探索区域，锚点附近也可能不存在足够形状；应返回明确失败，不伪造位置。
- phase correlation 对极少墙体或大面积均匀区域不可靠；需要通过最小特征数和质量门控进入恢复。
- 多人 marker 识别暂不纳入本阶段；单人中心模式优先。
- 当前计划不修改原绘图导航模式，只抽取或复用已经验证的通用位移和墙体标准化能力。
