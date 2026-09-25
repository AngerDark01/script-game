# PoE2 自动方向与多帧定位链路补全设计

日期：2026-09-23  
状态：已确认，待实施  
范围：PoE2 实验定位、正式混合定位的方向契约、采集归档、定位展示与回放；不执行 Xbox、键鼠、Host 或网络输入。

## 1. 目标

本次工作一次完成两件事：

1. 彻底取消用户手工旋转、水平镜像和垂直镜像，将方向唯一所有权交给自动注册算法。
2. 对照多帧定位方案补齐当前实现缺口，使“全局定位 -> 连续跟踪 -> 周期纠偏 -> 丢失恢复 -> 统一展示 -> 可回放诊断”形成完整闭环。

旧配置和旧归档中的手工方向不保留兼容。旧配置字段加载时被忽略，旧归档按不支持的坐标契约拒绝回放。

## 2. 坐标与方向所有权

系统只允许以下坐标空间：

| 空间 | 含义 | 所有者 |
|---|---|---|
| `L` | 监控帧和滚动局部拼图坐标 | 视觉证据管线 |
| `N` | 未经页面旋转的 native 地形坐标 | 定位、锚点、轨迹、导航 |
| `D` | 页面显示坐标 | presentation adapter |

局部到 native 的唯一变换为：

```text
T(q) = s * R(theta) * F(f) * q + b
```

其中 `theta`、镜像 `f`、比例 `s` 和平移 `b` 均由自动注册算法输出。内存锚点、参考地图、定位结果、轨迹和导航观察始终位于 `N`。`D` 只用于显示，不参与定位计算。

必须满足以下不变量：

```text
memory anchor belongs to N
localization result belongs to N
navigation observation belongs to N
only an algorithm-confirmed registration maps L to N
map, player, trajectory and candidates in one frame share one registration version
```

配置模型不再定义 `map_rotation`、`map_flip_horizontal` 或 `map_flip_vertical`。旧 JSON 中的同名字段由 `from_dict()` 忽略，下一次保存时自然清除。正式 hybrid composition 与多帧实验 composition 均直接构造 native reference 和 native anchor。

## 3. 自动全局定位

首次定位和丢失恢复调用同一个全局注册组件。首次定位只是证据最少的 recovery revision。

统一输入包括：

- native 参考地图、有效区、边界和距离场；
- 一次内存人物锚点及地图实例、单调时间戳和误差范围；
- 与锚点配对的监控帧；
- 后续移动关键帧、帧间位移和滚动局部拼图。

单人中心模式将人物局部点定义为配置中心，不执行颜色或形状人物识别。

### 3.1 方案 A：拼图后注册

方案 A 在锚点配对帧建立局部片段，人物移动时选择关键帧并构建滚动拼图。达到墙体长度、有效覆盖、移动跨度、方向丰富度和关键帧数量门槛后冻结证据版本，在锚点约束 ROI 内搜索 `theta/f/s/b`。

注册结果必须通过未参与拟合的留出帧。相同证据版本只尝试一次；失败后只有新增关键帧或覆盖达到增量门才重试。

### 3.2 方案 B：多帧联合候选

方案 B 为不同方向、镜像和尺度 basin 保留多个候选。每个候选对所有关键帧使用同一个 `T`，不能逐帧独立平移以掩盖错误方向。

初始搜索使用粗角度采样，随后逐级缩小角度、尺度和平移范围。典型角度层级可为 `45 -> 15 -> 5 -> 1` 度，但实际步长由轮廓半径和允许的远端误差计算。45 度只能生成 basin，不能作为最终方向。

重复种子落入同一 basin 时合并；真正不同的方向或镜像模式必须保留。新关键帧只评价候选对应的局部 ROI，并允许在新增结构明显时补入遗漏的粗候选。

### 3.3 稳健形状目标

联合误差为：

```text
E = lambda_anchor * E_anchor
  + lambda_forward * E_forward
  + lambda_reverse * E_reverse
  + lambda_tangent * E_tangent
  + lambda_motion * E_motion
  + lambda_scale * E_scale
```

- forward/reverse 距离使用真正的 Huber 损失；
- 允许裁掉固定上限比例的极端残差，但保留未裁剪覆盖率；
- reverse 只在双方确实可观察的支持区计算；
- 骨架和距离场吸收墙体粗细差；
- 切向角一致性降低平行墙和重复走廊误配；
- 文字、传送门等粗块降权，不按颜色或粗细整体删除；
- reference ROI、距离场和轮廓按候选区域缓存。

候选只有在实例与时间配对有效、位置/方向/镜像/尺度收敛、结构和覆盖足够、最佳真实模式稳定领先、留出帧通过且 A/B 无显著冲突时才能确认。证据不足保持 `collecting`，不把锚点附近的偶然高分宣布为成功。

## 4. 连续跟踪、纠偏和恢复

确认注册 `T_v` 后，正常帧链为：

```text
capture -> evidence -> frame displacement -> motion gate
        -> native prediction -> state estimator
        -> periodic local shape correction -> publication
```

单人中心模式中，小地图墙体位移为 `d_t`，人物位移为：

```text
delta_p_L = -d_t
delta_p_N = linear(T_v) * delta_p_L
```

旋转、镜像和比例必须作用于人物位移，不能只作用于地图 pixmap。

运动状态区分可靠静止、可靠移动和未知。可靠静止不增加重复关键帧；缓慢移动相对最近可信参考累计；低质量、遮挡、冻结或超时为未知，不能用零位移接链。

即使 F2F 持续成功，也在累计行程、时间、协方差、重投影残差或高信息关键帧达到阈值时执行局部形状纠偏。纠偏只在预测位置附近搜索小范围平移、角度和尺度修正，并通过 Mahalanobis 门与形状门后更新状态和注册。

状态估计维护 `[px, py, vx, vy]` 与协方差。过程噪声随时间、运动质量和注册不确定性增长；观测噪声由墙体残差、覆盖和候选歧义决定。

连续位移拒绝、局部纠偏失败、视觉与预测冲突、配置/实例变化或注册过期会触发：

```text
TRACKING -> DEGRADED -> RECOVERING
         -> one memory anchor per recovery revision
         -> clear stale motion/registration
         -> collect evidence -> global A/B registration
         -> publish one new version -> TRACKING
```

单帧失败不立即恢复。每个 recovery revision 最多一次自动内存读取，不在后台循环读内存或重复全局搜索。

## 5. 有界证据和加权滚动子图

`EvidenceWindow` 同时限制关键帧数、时间跨度、累计行程和实际字节数，任一预算超限即从最旧证据开始淘汰。字节统计覆盖 mask、原图引用、位移边、候选、子图和工作缓存。

滚动子图每格至少保存：

```text
wall_weight
observed_weight
last_frame_id
```

墙体概率为：

```text
P_wall(x) = wall_weight(x) / max(observed_weight(x), epsilon)
```

未知区域不当作空地；单帧贡献有上限；噪声和低质量帧降权。关键帧淘汰或帧位姿修正后，从保留证据重建小子图，禁止不可逆 OR 融合留下永久重影。子图只覆盖最近行程，外部为未分配迷雾；native 参考地图仍按实例共享保留。

## 6. 显示与异步发布

注册前显示 native 地图并标记“等待自动方向校准”。注册成功后，presentation adapter 从确认的 `T_v` 派生显示变换；地图、人物、轨迹、候选和误差范围由同一个不可变 published state 生成。

新注册版本必须原子替换旧版本。旧异步结果、旧证据版本和旧 recovery revision 的结果直接丢弃。UI timer 不执行完整精搜；同一 session 最多一个有界后台注册任务。

用户界面删除手工旋转和镜像控件，改为只读显示自动角度、镜像、尺度、候选差距、注册版本、耗时和拒绝原因。

## 7. 归档与回放

新归档只保存 native 证据和算法注册，不保存手工方向。归档包含截图、wall/observed mask、动态排除区、锚点、时间、读取次数、位移、关键帧决策、A/B 候选、误差分量、精化过程、最终注册、位置、协方差、状态和所有版本号。

回放工具从 manifest 与 `evidence.npz` 重建证据并重新执行 A/B、纠偏和恢复状态机，不启动游戏、不读取内存、不产生输入。旧 schema/旧坐标契约直接返回清晰的不支持错误。

## 8. 导航边界

本阶段只输出领域中立的 `NavigationObservation`。仅 `confirmed + fresh + instance match` 可执行；collecting、ambiguous、超时 degraded、recovering 和 lost 均不可执行。

本次不调用 Xbox、键盘、鼠标、虚拟手柄、Host 或 LAN，也不修改这些模块。

## 9. 验证与完成定义

合成和历史样本测试必须覆盖任意角度、镜像、尺度、墙体厚度差、缺墙、粗块、文字噪声、重复走廊、A/B 冲突、静止、缓慢移动、漂移、局部纠偏、恢复、地图切换、预算淘汰和异步过期结果。

完成必须同时满足：

1. 手工方向从 UI、配置、运行时、采集和新归档彻底移除。
2. 自动方向包含粗搜、精化、候选消歧和留出验证。
3. 方案 A/B 可独立运行并输出完整诊断。
4. 连续跟踪包含周期性局部形状纠偏。
5. 每个恢复版本最多读取一次内存锚点。
6. 证据、子图、候选和后台任务全部有界。
7. 回放工具能真正重跑算法。
8. 地图、人物和轨迹始终共享注册版本。
9. 聚焦回归与完整相关测试通过。
10. 断点文档如实区分合成/样本验证和实机验证。

实机单独记录错误确认率、native 位置误差 P50/P95、自动角度误差、确认时间与移动距离、纠偏频率、恢复成功率、每次恢复内存读取次数、峰值内存和后台任务耗时。实机未完成前不得宣称稳定上线。
