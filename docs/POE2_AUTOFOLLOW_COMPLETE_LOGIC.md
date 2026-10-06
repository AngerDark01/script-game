# PoE2 自动跟随完整执行逻辑

## 1. 文档目的与范围

本文描述当前 PoE2 实验页中“自动跟随”的实际处理逻辑。文档按 `CODEBASE.md` 的方式从触发入口开始，沿着定位、目标生成、运动规划、手柄输出、视觉校正和异常恢复逐层展开。

本文描述的是处理原理和状态流转，不复述 Python 实现。范围包括：

- 单人程序跟随：一个角色由程序控制，目标来自地图点击或实时角色位置。
- 双人实时跟随：一个角色由用户手动控制，另一个角色由程序控制。
- 双人同目标移动：两个程序角色共同前往同一个地图目标。它和实时跟随共享运动底层，但目标源不同。
- 双人视觉定位、首帧定位、局部跟踪和全局重定位，因为自动跟随依赖这些结果。
- 输入前台保护、冷启动、视觉丢失、预测、撞墙、路径失败、恢复和退出。

不包括正式产品运行时的完整导航业务；本文针对 PoE2 实验页当前组合。

## 2. 参与模块和职责边界

### 页面与生命周期

- `ui/modes/poe2_live_terrain/capture_test_page.py`
  - 接收按钮和地图点击。
  - 校验地图、实例、人物角色和新鲜帧。
  - 创建跟随运行时、角色观测器和程序输出。
  - 把视觉状态转换成运行时位置样本。
  - 管理定时器、前台窗口、恢复上下文和 UI 状态。
- `ui/modes/poe2_live_terrain/dual_motion_mixin.py`
  - 启动和停止双人视觉 worker。
  - 接收 latest-only 视觉帧。
  - 路由 worker generation，丢弃旧 worker 的结果。
  - 处理双人视觉 tracker 的恢复请求。

### 双人视觉定位

- `experimental/multiplayer_localization/dual_first_frame_experiment.py`
  - 读取内存人物锚点，抓取首帧小地图，寻找两个角色标记。
  - 计算共同旋转、缩放、平移和角色 assignment。
- `experimental/multiplayer_localization/dual_motion.py`
  - 以首帧变换为初始状态。
  - 对后续帧进行墙体位移匹配和人物标记匹配。
  - 对角色 marker 使用保持时间、年龄和不确定度。
  - 产生 `tracking`、`degraded`、`recovery_required` 三类状态。
- `ui/modes/poe2_live_terrain/dual_motion_worker.py`
  - 在后台线程抓取截图、处理墙体、识别角色、运行 tracker。
  - 只保留最新完成帧，避免 GUI 队列堆积。
  - 单独保存 recovery revision，避免恢复边沿被覆盖后丢失。

### 运动运行时

- `experimental/multiplayer_follow/runtime.py`：维护目标、角色位置、路径、速度、到达状态、停滞证据和脱困状态。
- `core/routing/path_finder.py` 及几何辅助：提供 A* 路径和线段可行性检查。
- `core/routing/local_controller.py`：在全局路线基础上生成短视窗方向，处理局部障碍、速度和方向平滑。
- `experimental/motion/closed_loop.py` 相关控制器：根据实际视觉位移反馈调整命令幅度和脉冲时长。
- `experimental/multiplayer_follow/command_role_tracker.py`：把手柄输出转成短期位移预测，再用视觉位置校正。

### 输入适配器

- `experimental/multiplayer_follow/program_output.py`：管理每个角色的输出 lease、arm、写入和释放。
- Host/ViGEm adapter：真正提交虚拟手柄报告。页面和通用运动运行时不直接操作 Windows 输入设备。

## 3. 坐标、时间和数据契约

### 坐标空间

自动跟随的路径、墙体、人物位置和目标全部使用同一套 `reference/native` 地图坐标。首帧配准得到的旋转、镜像、缩放和平移只用于：

1. 把截图中的人物点转换到 native 地图；
2. 把 native 路线和人物点转换回 UI 展示坐标；
3. 在最终输入适配器边界把 native 路线方向转换成手柄轴方向。

同一向量不能在页面、运行时和输出适配器重复旋转。重复转换会造成“地图显示方向正确，但人物实际移动方向错误”。

### 时间契约

- 视觉位置使用截图自己的 `captured_at_ms`，不能用 GUI tick 时间伪造新鲜度。
- 同一个截图时间只能消费一次；旧帧不能覆盖新帧。
- 实时跟随启动最多接受 300 ms 内的完整双人帧。
- 运行时位置和目标默认 700 ms 过期。
- 视觉角色保持默认约 2000 ms，但程序输出角色有更严格的预测不确定度限制。
- worker 按配置帧率运行，页面约每 33 ms 消费一次 latest-only 结果；页面渲染和视觉 worker 分离。
- 地图级运行没有总时长上限；程序移动不会因为 elapsed time 达到某个值而结束。`elapsed_ms` 只在停止摘要中记录实际运行时长。视觉帧龄、Host command TTL、恢复冷却和 worker join timeout 只约束单次观测、单次输入或线程清理。

### 关键位置样本

每个 `PositionSample` 至少包含：角色身份、地图实例、native 坐标、捕获时间、置信度和来源。来源用于区分：

- `visual`：当前截图明确识别到的人物；
- `command_prediction`：根据程序刚刚发出的手柄脉冲推算的位置；
- `target_hold`：手动领队暂时不可见时保留的上一次位置；
- `wall_estimate`：墙体位移和局部地图仍可信时的估计位置；
- `simulated`：离线模拟角色的位置。

## 4. 总体执行链路

```text
用户点击“开始跟随”
        │
        ├─ 校验双人首帧、地图实例、角色选择、截图新鲜度
        │
        ├─ 创建 SimulatedFollowRuntime
        │      ├─ 目标源：地图点击 / 实时领队
        │      ├─ 角色模式：MANUAL / PROGRAM / SIMULATED
        │      └─ 创建路径规划、局部控制、闭环校准器
        │
        ├─ 创建 CommandRoleTracker（实时跟随才创建）
        ├─ 创建 ProgramFollowOutput（有程序角色才创建）
        ├─ 进入冷启动同步
        │
        └─ 跟随定时器循环
               ├─ 前台窗口门控
               ├─ 消费最新双人视觉帧
               ├─ 领队/跟随者视觉与预测融合
               ├─ 写入 runtime 的当前角色和目标
               ├─ runtime.tick()
               ├─ 处理到达、路线、局部脱困和重定位证据
               └─ 只有 PROGRAM_READY 才写入手柄
```

## 5. 启动前置条件

自动跟随不是独立启动的。必须先完成：

1. 初始化当前地图快照。
2. 读取当前地图实例和地图墙体。
3. 读取两个角色的 native 内存锚点。
4. 抓取同一时刻的小地图截图。
5. 完成双人首帧配准，得到两个角色的屏幕点、内存点、共同变换和身份 assignment。
6. 启动双人实时定位，使 `_latest_dual_state` 有持续更新。

如果没有地图、变换、tracker 或有效人物位置，跟随入口只更新 UI 提示，不创建 runtime，也不会申请手柄。

实时跟随还要求：

- P1/P2 必须选择两个不同身份；
- 领队和程序角色都必须在当前状态中有位置；
- 最新帧状态必须是 `tracking`，或墙体可信且所需角色有 bounded estimate 的 `degraded` 恢复帧；
- 帧年龄不超过 300 ms；
- 不能是首帧 warmup 的静止假设帧；
- 地图实例必须与 runtime 的 `MapIdentity` 一致。

## 6. 三种跟随模式

### 6.1 实时角色跟随

`p1_leads` 表示 P1 是手动领队、P2 是程序角色；`p2_leads` 相反。领队只产生观测，不申请程序输出。跟随者才创建 `ProgramFollowOutput`。

领队的位置来自当前双人视觉帧。领队视觉跳变被直接接受，因为它反映用户的实际移动，不能拿程序角色的手柄运动模型去拒绝。领队短暂消失时使用 `target_hold` 或有限时间内的预测；超出允许年龄或不确定度后才请求重定位。

### 6.2 单程序角色跟随

单程序模式只有一个 PROGRAM 角色，目标可以来自地图点击或外部阶段性位置。它仍然使用相同的 `SimulatedFollowRuntime`、路径规划和 `ProgramFollowOutput`，只是目标源不是另一个本地角色。

### 6.3 双人同目标

两个角色都可以设置为 PROGRAM，共享一个地图目标。目标通过地图点击获得，先从 display 坐标逆变换到 native 坐标，再做边界和 round-trip 校验。两个角色分别执行自己的路线、到达和恢复状态，但使用同一个目标源和同一个运动运行时。

## 7. 启动阶段的详细顺序

### 7.1 清理旧会话

入口具有幂等性。如果已有 runtime、跟随定时器或程序输出，先关闭旧会话、释放旧 lease、停止旧 timer，再创建新会话。这样可以防止“旧输出 + 新输出”同时写手柄。

### 7.2 选择角色和模式

页面根据双人视觉状态同步 P1/P2 选择框。实时跟随确定一个 MANUAL 角色和一个 PROGRAM 角色；单程序模式确定一个 PROGRAM 角色；双人同目标确定两个角色的控制模式。

### 7.3 创建运行时

当前实时跟随默认参数为：

| 参数 | 当前值 | 作用 |
| --- | ---: | --- |
| 到达半径 | 12 native px | 进入目标附近后认为到达 |
| 恢复半径 | 20 native px | 已到达后，目标离开该范围才重新追踪 |
| 速度先验 | 80 native units/s | 冷启动和闭环校准的初始速度 |
| 位置 TTL | 700 ms | 超时位置不能直接驱动路线 |
| A* 降采样 | 8，失败回退 4/2/1 | 速度与精度的平衡 |
| clearance radius | 20 | 路线安全评分使用的墙距参考 |
| clearance weight | 2.0 | 在可行路线中偏好更开阔路线 |
| dead-end weight | 0.75 | 避免死路的评分权重 |
| footprint radius | UI 当前角色半径 | 只参与实时跟随的碰撞策略 |
| collision inflation | 当前关闭 | 避免把窄门因额外膨胀判成不可走 |
| 停滞 tick 数 | 8 | 连续无进度后进入局部恢复 |
| 接触证据样本数 | 4 | 小地图确认撞墙所需的连续证据 |
| 局部 lookahead | 24 | 局部控制观察前方距离 |
| prediction horizon | 0.25 s | 局部运动预测窗口 |

这些参数属于实验组合层。通用 runtime 支持更宽的配置，但 PoE 页面使用上述组合。

### 7.4 创建输出和角色历史

每个程序角色绑定一个对应 controller 的输出对象，并由 `ProgramFollowOutput` 统一管理。实时跟随同时创建 `CommandRoleTracker`，以 runtime 的速度先验为初始值，为每个角色保存：

- 最近可信视觉位置；
- 最近视觉时间；
- 输出脉冲历史；
- 估计速度和不确定度；
- 当前视觉相位是否仍在冷启动/恢复宽限期。

### 7.5 六秒跟随输入延迟

实时跟随和点击目标跟随启动后默认等待 6 秒。这个延迟从点击“开始跟随”时计算，给用户切回 PoE2 窗口。延迟期间：

- 跟随 timer 可以运行；
- 视觉和目标状态可以更新；
- 不会 arm 程序输出；
- 不会取得 Host lease；
- 不会提交手柄报告。

这 6 秒是跟随输出的启动前等待，不是地图运行时限。独立程序移动探针还有一个单独的 10 秒前台确认等待，用于点击目标后切回 PoE2；恢复重定位的 10 秒值是页面级 recovery cooldown。三者都不限制地图可以运行多久。

## 8. 冷启动和恢复同步

实时跟随不会直接把首帧当成第一条运动证据。启动时把已接受首帧的 `captured_at_ms` 记录为 baseline，进入 `cold_start`。

只有同时满足以下条件才进入 `tracking`：

1. 收到严格更新的截图时间，不能等于 baseline；
2. 领队和程序角色都存在；
3. 角色观察状态允许使用；
4. 新帧仍属于同一地图实例。

通过后，对所有角色重新 seed `CommandRoleTracker`，重新启动视觉宽限期，清空旧的 innovation rejection 计数和恢复 episode。之后才允许正常输出。

重定位成功后使用同样的流程，但 phase 为 `recovery_sync`。如果恢复首帧仍旧、缺角色或不完整，保持中性等待，不把它计为新的视觉拒绝，也不立刻再次重定位。

## 9. 双人视觉定位循环

### 9.1 worker 采集

后台 worker 按帧率执行：

1. 截取 PoE2 监控区域。
2. 生成墙体 mask 和处理图。
3. 运行颜色 marker 检测，保留最多六个候选。
4. 读取页面发布的角色预测 hint；hint 包含 native 位置、不确定度和时间。
5. 调用 `DualVisualTracker.tick()`。
6. 将结果放入 latest-only 槽位，并通知 GUI。

如果 GUI 来不及消费，旧结果被丢弃，计入 `dropped_results`；但 recovery revision 会独立保存。

### 9.2 墙体位移匹配

tracker 使用上一次变换作为当前帧的预测变换。根据相邻墙体帧计算位移；在需要校正的帧上，以预测平移为中心，在有限半径内做局部墙体形状匹配。

- 匹配成功：更新变换和平移，重置墙体失败计数。
- 没有位移但仍在首帧 warmup：保留原变换。
- 需要校正但匹配失败：进入失败计数。
- 首次失败不会立即全局重定位，只有达到 tracker 的失败阈值才进入 `recovery_required`。

### 9.3 双角色 marker assignment

候选 marker 按颜色特征和位置组成有序 assignment。tracker 会把候选点经过当前变换映射到 native 坐标，并交给每个角色的 bounded observation：

- marker 可见且误差允许：接受视觉位置；
- marker 暂时不可见：在保持时间和不确定度范围内保留上一位置；
- 超出年龄、不确定度或身份约束：角色变成 expired；
- 任一角色长期 expired：状态转为 `recovery_required`。

墙体质量高并不代表人物识别成功。当前日志中 `quality≈1.0` 同时出现 `DexFourb` 长时间丢失，就是“墙体可靠、角色身份不可用”的典型情况。

### 9.4 状态含义

- `tracking`：墙体和角色观察都可用，允许跟随逻辑消费。
- `degraded`：部分角色暂时不可见，但仍有保持或预测，运行时可继续短时工作。
- `recovery_required`：墙体局部匹配失败、角色长期丢失或 tracker 无法保持可信变换，需要全局重定位。

恢复请求有两个字段：

- `recovery_requested`：一次性边沿事件；
- `recovery_revision`：本 tracker 生命周期内递增的恢复版本。

页面现在同时消费边沿和更高版本的持续 `recovery_required`，避免 latest-only worker 覆盖边沿后永远不恢复。

## 10. 跟随 tick 的详细逻辑

每次 GUI 跟随 timer 到期，入口先记录 attempt，再执行以下顺序。

### 10.1 上下文检查

缺少 runtime、地图尺寸或变换时，不结束会话。程序输出释放为中性，标记恢复待处理，并等待后台重建。

### 10.2 游戏前台门控

页面查询 PoE2 进程和窗口，并短时间缓存结果。只有 PoE2 窗口在前台才允许输出。

- 查找失败、窗口不存在或 PoE2 不在前台：释放输出，保持视觉 worker 和跟随 timer，等待恢复；
- 前台重新获得：以最新完整双人帧重新建立视觉 baseline；
- 前台问题本身不会触发全局重定位。

### 10.3 消费双人视觉状态

页面从 `_latest_dual_state` 读取当前双人位置。实时跟随会为领队和程序角色分别生成 `PositionSample`。

#### 领队可见

领队位置直接接受，不经过程序手柄 innovation rejection。大位移被视为用户移动或位移技能，不触发跟随者的方向错误判断。

#### 程序角色可见

程序角色的位置交给 `CommandRoleTracker.observe()`：

1. 根据上一视觉锚点和已发送输出预测当前位置；
2. 计算视觉点和预测点的创新误差；
3. 在视觉宽限期内使用较宽的方差；
4. 宽限期外用正常视觉方差判断是否接受；
5. 接受则更新速度、锚点和历史输出；
6. 拒绝则检查视觉连续性：如果帧间位移小、时间间隔有限且没有跳变，允许 rebase；
7. 连续三次真正的 innovation rejection 才请求全局重定位。

#### 角色不可见

不可见不等于立即停止：

- 领队使用 `target_hold` 继续作为目标源；超过约 3 秒后不再把该估计发布为视觉 worker 的预测 hint，但页面仍等待下一帧或恢复证据；
- 程序角色如果有输出历史，使用 `command_prediction`；
- 预测不确定度超过 12 native px 或视觉年龄超过 700 ms 时，只降低预测 hint 的可信度并记录诊断，不单独触发全局重定位；
- 视觉帧持续停滞达到约 8 秒、墙体/身份状态失效、连续 innovation rejection 或局部接触恢复失败时，才进入恢复路径；
- 被遮挡期间只要年龄和不确定度仍在 hint 门槛内，就会把预测 hint 发布给视觉 worker，帮助下一帧重新分配 marker；超过门槛时保留页面侧预测，但不再向 worker 提供过期 hint。

### 10.4 更新目标

实时跟随把领队的位置作为目标 sample。只有截图时间严格大于上一次目标时间才接受，避免旧帧倒灌。

地图点击模式则调用静态目标源 heartbeat，使点击目标持续保持新鲜，不需要每帧重新规划。

### 10.5 更新 follower 当前位置

runtime 的每个 follower 位置都用同一套 native 坐标更新：

- 当前视觉点优先级最高；
- 短暂不可见时使用 bounded prediction 或 wall estimate；
- 不能用 GUI tick 时间冒充视觉时间；
- 更新时计算相邻视觉位移、速度、命令方向夹角和接触证据。

### 10.6 调用运动运行时

runtime 对每个 follower 独立执行 `tick()`，但目标源、地图实例和路径算法相同。每个角色返回一个 observation，包含状态、距离、目标、路线、方向向量、命令时长和诊断数据。

## 10A. 算法原理详解：从观测到手柄输出

这一节解释“为什么能定位、为什么能走、什么时候认为撞墙或丢失”，以及每个算法的输入和输出。所有公式中的坐标都指 native 地图坐标；屏幕坐标只在首帧配准和 marker 检测阶段出现。

### 10A.1 双人首帧：用一个相似变换解释两个人

**目的：** 用同一张小地图截图中的两个 marker 和内存读出的两个 native 锚点，求出截图到地图的旋转、镜像、比例和平移。这样不是“分别把两个人放到最近位置”，而是要求两个点同时被同一个几何变换解释。

设截图中的两个角色点为 `s1, s2`，内存锚点为 `n1, n2`：

```text
ds = s2 - s1
dn = n2 - n1
scale = |dn| / |ds|
angle = atan2(dn.y, dn.x) - atan2(ds.y, ds.x)
```

对每个候选镜像状态 `m ∈ {不镜像, 水平镜像}`，先对屏幕点应用镜像，再旋转和缩放：

```text
T(s) = scale · R(angle) · M(m) · s + translation
translation = n1 - scale · R(angle) · M(m) · s1
```

再把 `s2` 代入 `T`，得到第二个 anchor 的误差：

```text
anchor_error = (|T(s1)-n1| + |T(s2)-n2|) / 2
```

候选还必须通过 marker 颜色/形状置信度、地图实例一致性和尺度上下界。最终选择误差小且与第二名有足够间隔的候选；如果两者几乎一样，则返回 ambiguous，而不是随机选一个方向。输出是 `SimilarityTransform2D` 和两个角色的 identity assignment。

**边界：** 两个 marker 太近时，`|ds|` 很小，角度和比例对像素噪声极敏感；此时应依赖墙体形状或等待角色分开，不能把一个不稳定的角度当成真值。

### 10A.2 墙体位移：用形状而不是颜色追踪地图运动

每帧先把墙体转换为统一的二值/灰度 canonical mask，再和上一帧在一个有限窗口内做平移搜索。对候选位移 `u=(dx,dy)`，比较重叠区域的形状相似度；候选必须满足最低覆盖率、质量和最大位移约束。得到的小地图位移 `u_screen` 通过首帧变换转换到 native：

```text
u_native = scale · R(angle) · M(m) · u_screen
position_next = position_previous - u_native
```

这里使用减号是因为“地图纹理向右滚动”代表人物在地图坐标向左移动。若跳变超过 `max_global_jump`、重叠质量不足或连续校正条件触发，则不采纳该位移，转入局部保持或恢复，而不是把错误平移累积到轨迹中。

墙体位移的价值是：人物 marker 暂时被文字、传送门或另一名角色遮住时，仍能提供短期运动信息；它不是全局定位，不能无限期替代人物观测。

### 10A.3 多 marker assignment：先预测，再做最小代价匹配

一帧最多保留若干候选 marker。对每个角色，根据上一帧位置、墙体位移和命令预测得到 `p̂_i`。对候选 marker `q_j` 枚举可行排列，代价为：

```text
cost(π) = Σ_i ||p̂_i - q_{π(i)}||₂
```

先过滤单步距离超过 `max_marker_step` 的排列，再取总代价最小者。若最小代价和次小代价的差小于 `identity_margin`，说明身份无法可靠区分，返回 ambiguous；只有明显领先的排列才更新角色位置。这样可避免两个人靠近或颜色相似时交换身份。

marker 置信度、年龄和保持时间会共同决定观测来源：当前清晰 marker 是 `visual`，短暂不可见可退化为 `wall_estimate` 或 `command_prediction`，超过保持上限才进入 `recovery_required`。

### 10A.4 视觉与命令预测融合：不是盲目累加位移

程序每次实际提交手柄命令都记录 `(v_k, t_start, t_end)`。短期预测是所有已确认命令区间的积分：

```text
delta_prediction = Σ_k v_k · (t_end_k - t_start_k)
position_prediction = anchor_position + delta_prediction
```

视觉观测到达后，`PositionStateEstimator` 计算创新：

```text
innovation = z - x̂
S = P̂ + R
mahalanobis² = innovationᵀ · S⁻¹ · innovation
```

其中 `z` 是视觉位置，`x̂/P̂` 是预测位置和协方差，`R` 是注册/识别误差。创新在阈值内时，用增益校正位置和协方差：

```text
K = P̂ · S⁻¹
x = x̂ + K · innovation
P = (I-K)P̂(I-K)ᵀ + K·R·Kᵀ
```

接受的相邻视觉样本还用 EWMA 更新速度：

```text
v_new = 0.7 · v_old + 0.3 · (z_t-z_prev)/(t-t_prev)
```

创新被拒绝时不把异常视觉点硬写入地图，只增加不确定度；连续拒绝或协方差超过上限才触发恢复。**预测位置只能保持运动和产生下一步候选，不能单独证明已经到达目标。**

### 10A.5 A* 多尺度路径：先可行，再在可行路线中选安全路线

墙体 mask 是 A* 的碰撞图。为平衡速度和窄门精度，按降采样因子 `8→4→2→1` 尝试。每个尺度的路径都要回到原始 native 墙体上逐段验证；降采样只用于搜索加速，不能改变最终碰撞事实。

路线候选的评分不是单纯最短距离：

```text
route_score = length(path)
             + clearance_weight · safety_cost(path)
             + dead_end_weight · dead_end_risk(path)
```

`safety_cost` 由墙距不足和低 clearance 段比例构成；`dead_end_risk` 依据前方可扩展空间和候选出口数量估计。选择最低分的严格可行路线。只有严格路线完全不存在且配置允许，才使用 relaxed 候选；当前不对整张地图做硬性 footprint 膨胀，以免窄门被误判不可通行。

### 10A.6 局部控制：短视窗候选方向的多目标评分

全局路径只给出拓扑方向。局部控制器围绕 base direction 枚举有限角度偏移 `θ_j`，并把每个候选前推一个短 horizon。对每个候选计算：

```text
score_j =  w_p · progress_j
        + w_c · clearance_j
        - w_d · path_deviation_j
        - w_t · turn_change_j
        - w_o · oscillation_j
        - w_x · overshoot_j
        + w_g · near_goal_j
```

其中 `progress` 是朝目标的距离下降，`clearance` 是前推线段的最小墙距，`path_deviation` 是偏离全局路线的距离。若当前在 approach band 内且直达线可行，则缩短 lookahead、降低幅度并直接朝目标，防止在目标附近左右摆动或冲过目标。最高分候选输出 native 方向和幅度，最后才通过 input basis 转成手柄轴。

### 10A.7 撞墙判定：多证据累积，而不是“一帧没动就是墙”

`ContactMonitor` 每个样本同时看：命令幅度 `|c|`、实际位移 `|d|`、命令与位移夹角以及局部障碍证据。方向一致性用余弦表示：

```text
alignment = (c · d) / (|c| · |d|)
```

只有当命令明显非零、实际位移低于阈值、局部前方存在障碍，并且连续达到 `required_samples`，才累计为 contact。单帧 marker 丢失、人物贴墙、墙格栅误差或角色暂时停顿都不会直接触发撞墙。确认 contact 后优先寻找左右自由空间和短脱困方向；恢复失败才提高 blocked/relocalization 证据等级。

### 10A.8 到达、目标刷新和数据新鲜度

到达使用视觉/有界估计与目标的欧氏距离：

```text
d_goal = ||position - target||₂
```

`d_goal ≤ arrival_radius` 只在视觉或可信估计确认时进入 `ARRIVED`；预测距离只能触发受限 approach pulse。目标仍在 `recovery_radius` 内时保持到达，离开后重新规划。目标样本和人物样本都有 TTL；过期意味着“当前观测不可直接驱动路线”，不是“整个会话停止”。

### 10A.9 恢复 episode：把昂贵重定位变成受控状态机

恢复由“原因 + session + tracker generation + revision”组成。第一次满足触发条件时创建 episode，保存上下文并释放为中性；同一 episode 后续只累计诊断，不重复启动全局定位。成功的 fresh/degraded 安全帧通过统一门槛后重建 tracker baseline、重新 arm 输出并执行一次受控 tick。cooldown 限制全局重定位频率，revision 防止 latest-only worker 覆盖 recovery 边沿后页面永远收不到事件。

状态转移可概括为：

```text
TRACKING → PREDICTION_HOLD → LOCAL_RECOVERY → RECOVERY_EPISODE
         → FRESH_REANCHOR → TRACKING
```

对实时跟随会话而言，只有显式停止、页面隐藏或关闭才是终止状态；视觉短暂失败、局部撞墙和全局重定位都不是用户停止。独立程序移动探针的明确结束状态见第 18 节。

### 10A.10 速度校准和手柄脉冲：闭环调节而非固定时长

期望速度只是冷启动先验。每次视觉确认后，用实际位移和命令持续时间估计速度：

```text
v_measured = displacement / command_duration
v_estimate ← (1-α)·v_estimate + α·v_measured
```

下一次脉冲时长近似为：

```text
duration = clamp(distance_to_local_target / v_estimate,
                 min_pulse_ms, max_pulse_ms)
```

接近目标、观测不确定度升高或速度比先验过快时，降低轴幅度和脉冲上限；连续无进度时先改变方向/重规划，不盲目延长同一方向的按压。这样把“手柄持续按住多久”纳入反馈闭环，适应不同机器、帧率和游戏移动速度。

### 10A.11 关键参数之间的耦合

- `scale/angle/anchor_error` 决定人物和墙体是否在同一 native 坐标；首帧错了，后续所有路径都会错。
- `marker_step/identity_margin/hold_ms` 决定两个人靠近时是接受、保持还是恢复；放宽 step 会增加错配风险，放宽 margin 会增加身份交换风险。
- `arrival_radius/approach_band/pulse 上限` 共同决定是否提前停在目标附近；不能只降低 arrival threshold 而不限制 approach pulse。
- `lookahead/clearance_weight/dead_end_weight` 决定“短而直”与“远离墙/不进死路”的权衡。
- `contact thresholds/required_samples` 决定贴墙时的敏感度；过低会把正常窄道当撞墙，过高会让真正卡墙持续太久。
- `visual TTL/prediction covariance/recovery cooldown` 决定流畅度与重定位成本；TTL 太短会频繁恢复，太长会让错误预测漂移。

调参顺序应是：先验证坐标变换和首帧 anchor，再验证视觉/命令时间戳，再调路径安全权重，最后调输出幅度和脉冲时长。不能用输出参数掩盖坐标或身份匹配错误。

## 11. 路径规划原理

### 11.1 地图和碰撞

墙体被归一化为二值地图：非零是墙，零是可走。当前 PoE 实时跟随组合关闭额外 collision inflation，原因是地图原生墙体已经较厚，额外膨胀会封死窄门。

这意味着：

- 全局路线不会主动穿过原始墙体；
- 人物靠近墙时由局部控制和接触恢复处理；
- footprint 半径仍参与部分路线安全和恢复判断，但不会把整张地图硬膨胀到不可走。

### 11.2 多尺度 A*

路线按降采样因子 8、4、2、1 依次尝试。每次得到候选路线后：

1. 在碰撞地图上做安全路径简化；
2. 在原始 native 墙体上逐段检查线段可行性；
3. 检查墙距、低 clearance 比例和碰撞段；
4. 计算路线长度加墙体暴露惩罚的 score；
5. 在严格路线中选择最低 score；
6. 严格路线全失败且角色半径有效时，才考虑 relaxed clearance 候选。

目标小幅移动不会每个 tick 重跑 A*。只有目标离开刷新带、人物偏离当前路线、路线碰撞验证失败或局部恢复要求时才重规划。

### 11.3 局部控制

全局路径只提供拓扑方向。局部控制器在路线方向附近生成有限角度候选，综合：

- 前方墙距和可行性；
- 到目标的进度；
- 路线偏离；
- 目标距离；
- 先前命令变化；
- 当前观测速度与期望速度比例；
- 局部区域复杂度和同伴位置风险。

选择结果是 native 方向向量，而非直接的屏幕方向。输入适配器在最后一步才应用地图到手柄轴的固定 basis。

## 12. 到达、保持和目标刷新

### 12.1 视觉确认到达

实时跟随的到达半径为 12，恢复半径为 20。

- 视觉位置进入 12 内：状态为 `ARRIVED`，清除路线，释放程序输出；
- 目标仍在 20 内：保持 `ARRIVED`，不重新规划；
- 领队离开 20：退出保持，重新规划。

程序预测位置进入到达半径不能单独确认到达。此时输出最多 80 ms 的受限 approach pulse，等待视觉位置确认。

### 12.2 目标不存在或过期

- 没有目标：`WAITING_POSITION`，不写方向输入；
- follower 位置过期：`WAITING_POSITION`；
- target 位置过期：`WAITING_POSITION`；
- 地图实例不一致：`MAP_MISMATCH`，不写移动输入。

这些是当前 observation 状态，不等于整个跟随 session 必须停止。实时模式由页面保留 timer 和恢复上下文。

## 13. 手柄输出逻辑

### 13.1 arm

只有同时满足以下条件才 arm 某个角色：

- 游戏在前台；
- 六秒输入延迟已结束；
- 冷启动/恢复同步已完成；
- observation 状态为 `PROGRAM_READY`；
- 方向向量非零；
- 角色尚未 arm。

arm 会取得对应输出 lease，但不会把手动角色变成程序角色。

### 13.2 apply

`ProgramFollowOutput` 对每个程序角色逐个处理：

- `PROGRAM_READY` 且向量非零：应用 native→input basis 后写手柄；
- observation 带有闭环命令时，使用命令自身的时长，范围限制在 1–300 ms；
- 没有可行命令或处于等待/到达/阻塞：先写中性帧，再按状态决定是否释放；
- 一个角色释放不会覆盖另一个角色的 lease。

### 13.3 释放

发生前台丢失、视觉恢复、地图重置、显式停止、页面关闭或输出异常时，先写中性帧，再释放 lease。关闭会话时关闭该 session 创建的输出对象，避免残留输入。

## 14. 运动异常和局部恢复

### 14.1 视觉位置在墙格

native 配准存在栅格误差时，人物可能落在墙格，但小地图实际显示旁边有空地。运行时不直接改写人物位置，而是：

1. 在人物附近有限半径内寻找可走网格；
2. 从候选网格规划到目标；
3. 选择距离近、clearance 较好且朝目标的候选；
4. 发出 0.25–0.45 范围的短脱困脉冲；
5. 等下一帧视觉确认离开边界后回到普通路线。

### 14.2 小地图确认撞墙

只有同时具备“连续无进度”和“小地图局部障碍/接触证据”时，才把它视为可靠撞墙。小地图提供：前方是否有阻挡、左右自由空间、墙距和捕获时间。

确认接触后优先向自由空间较大的一侧搜索 1–12 px 环形候选，生成局部恢复路线。一次失败不会终止原路线；会尝试直接重规划和多个左右/前向候选。

### 14.3 无进度和方向不一致

每次可信视觉更新计算：

- 目标距离是否下降；
- 人物实际位移是否超过 progress epsilon；
- 已发命令与实际位移的夹角；
- 实际速度与估计速度的比例。

连续 8 个 tick 没有进度，或连续 3 个可信样本方向夹角明显不一致，就触发局部恢复。恢复顺序是：短 wall escape、直接重规划、左右交替和前向探针。

### 14.4 BLOCKED 与全局重定位

`BLOCKED` 是当前 follower 的局部状态，不应被解释为用户点击了停止。只有在局部候选全部失败，或两次小地图接触恢复仍无可行出口时，observation 才带有 `relocalization_requested`，页面才请求全局重定位。

上述语义针对实时跟随和双人同目标运行时。独立程序移动探针的页面入口会把 `arrived`、`blocked`、`waiting_position`、`map_mismatch` 作为本次探针的明确结束状态并释放输出；这仍然不是按总运行时间停止。若需要继续尝试，应由重定位恢复上下文或用户重新设置目标启动下一次探针。

## 15. 视觉丢失、预测和全局重定位

### 15.1 轻度丢失

只要角色仍在 marker hold 时间和不确定度范围内，tracker 保持上一位置；如果程序角色刚刚有输出，`CommandRoleTracker` 继续外推。页面继续让 runtime 运行，而不是把一次不可见直接变成停止。

### 15.2 触发重定位的条件

常见触发源有：

- 墙体局部匹配连续失败；
- 某个角色 marker 长时间 expired；
- 程序角色连续三次视觉 innovation rejection；
- 视觉帧持续停滞达到恢复阈值，或预测与局部运动证据共同表明当前位置不可继续；单独的预测不确定度超过 12 native px 不触发全局重定位；
- 角色接触恢复两次失败且没有安全出口；
- 运行时明确报告 `relocalization_requested`。

### 15.3 recovery episode

一次异常只打开一个 recovery episode：

1. 记录原因和 session id；
2. 释放当前程序输出为中性；
3. 保存角色、目标、实例、变换和半径等恢复上下文；
4. 通过 10 秒页面级 cooldown 限制昂贵全局定位频率；
5. 启动后台双人首帧 worker；
6. 成功后以 `recovery_sync` 重新建立 tracker baseline；
7. 收到新鲜完整帧后清除 episode，恢复正常跟随。

同一 episode 后续 tick 只记录 suppressed 次数和继续预测，不重复启动全局定位。恢复失败不会把跟随永久改成用户停止；它会按退避重新尝试。

### 15.4 recovery revision 丢失保护

视觉 worker 使用 latest-only 槽位，恢复边沿帧可能被覆盖。页面现在同时检查：

- worker 保存的 pending revision；
- 当前状态的 `recovery_requested`；
- 当前状态的 `recovery_required + recovery_revision` 是否高于本 generation 已处理版本。

同一 revision 只处理一次；新 tracker generation 清零版本。这样可以避免“状态已经 recovery_required，但页面永远只等待”的故障。

## 16. worker、GUI 和异常边界

### worker 内异常

截图为空、识别异常、mask 为空等会被 worker 捕获并计数。连续失败达到 worker 上限才发出终止信号；短暂失败按帧率退避后继续。

### GUI 分发异常

页面收到 worker result 后，如果渲染或状态分发异常：

- 实时跟随保留 runtime 和 session；
- 释放当前输出；
- 调度恢复重试；
- 不调用普通用户停止路径。

### 旧 worker 结果

每次启动都会递增 generation。结果 generation 不等于当前 generation 时直接丢弃，避免旧线程覆盖新地图或新角色状态。

### worker 停止

页面先设置停止事件，再进行有界等待。未及时退出的 worker 放入 retired 列表，等待 finished 信号后释放引用，避免 native 截图后端跨线程析构导致 GUI 崩溃。

## 17. 状态流转

```text
IDLE
  └─ start_follow_experiment → ARMED
                              │
                              ├─ live mode → COLD_START / RECOVERY_SYNC
                              │                 │
                              │                 ├─ 新鲜完整帧 → TRACKING
                              │                 └─ 缺帧/旧帧 → 继续等待
                              │
                              └─ click mode → WAITING_TARGET

TRACKING
  ├─ 目标在到达半径内 → ARRIVED/HOLD
  ├─ 目标离开恢复半径 → PLANNING
  ├─ 正常路线 → PROGRAM_READY
  ├─ 角色短暂不可见 → PREDICTED/DEGRADED
  ├─ 无进度/撞墙 → LOCAL_RECOVERY
  ├─ 视觉或地图无法信任 → RECOVERY_EPISODE
  └─ 显式停止/换模式/关页 → STOPPED

LOCAL_RECOVERY
  ├─ 找到局部出口 → PROGRAM_READY
  ├─ 直接路线成功 → PROGRAM_READY
  ├─ 多个候选失败 → BLOCKED + relocalization evidence
  └─ 全局恢复请求 → RECOVERY_EPISODE

RECOVERY_EPISODE
  ├─ cooldown 未到 → 继续有界预测/等待
  ├─ 首帧恢复失败 → 退避重试
  ├─ 首帧恢复成功但帧不新鲜 → RECOVERY_SYNC 继续等待
  └─ 新鲜完整帧 → TRACKING
```

这张状态图描述的是实时跟随会话。独立程序移动探针共享同一运动运行时，但在页面层有额外的“本次探针结束”边界：到达或明确的 `blocked`/`waiting_position`/`map_mismatch` 会释放该探针的输出；它没有任何地图级总时长分支。

## 18. “停止”在当前实现中的真实含义

需要区分三种情况：

1. **显式停止**：用户点击停止、切换实验、重置地图或页面关闭。会销毁 runtime、timer、输出和恢复上下文。
2. **输出释放**：视觉失效、前台丢失、等待到达或恢复时只释放手柄 lease；实时跟随 session 可以继续存在。
3. **状态性零向量**：`WAITING_POSITION`、`ARRIVED`、`BLOCKED` 等 observation 可能返回零向量，但这不必然意味着整个跟随实验已经停止。

如果 UI 显示“已停止”，必须结合 `follow_experiment.stopped` 或 `program_probe.stop_summary` 的 `reason`、`preserve_recovery`、timer 状态和 output snapshot 判断：实时跟随中的恢复/失焦可能只是释放输出并保留会话，而独立程序移动探针的明确状态结束会终止本次探针。两种模式都不会因为总运行时间字段而停止。

## 19. 日志如何阅读

建议按以下顺序查看：

1. `follow_experiment.armed`：确认角色、模式、程序角色、冷启动参数。
2. `live_role_follow.sync_enter/sync_ready`：确认同步屏障是否完成。
3. `live_role_follow.foreground_*`：确认游戏窗口是否实际获得输入。
4. `live_role_follow.output_armed/output_decision`：确认是否真正申请和写入输出。
5. `follow_experiment.runtime_decision`：确认目标、距离、状态、向量和路线。
6. `live_role_follow.tracker_state`：确认视觉年龄、不确定度、预测来源和输出历史。
7. `dual_motion.tick/timing`：确认墙体质量、人物可见性、worker 丢帧和耗时。
8. `dual_motion.recovery_edge_recovered/recovery_claimed`：确认恢复是否被页面消费。
9. `dual_first_frame.*`：确认全局重定位是否启动、成功或失败。
10. `live_role_follow.recovery_episode_cleared` 和 `sync_ready`：确认恢复是否真正闭环。
11. `follow_experiment.stopped`：只在最后判断是否是显式停止或生命周期销毁。

## 20. 当前已知边界和审查重点

### P1：视觉质量和角色可见性是两个独立条件

墙体 quality 高不能证明两个 marker 都有效。一个角色长期丢失时，必须看 `expired_marker_identities`、`identity_dropout_failures` 和 `role_observations`，不能只看 quality。

### P1：预测位置不是到达证明

预测进入到达半径时仍会发受限 approach pulse，只有新的视觉样本才能确认到达。任何把预测直接当 ARRIVED 的路径都会重现“程序以为到了，但人物还在原地”的问题。

### P1：输入提交不等于游戏消费

Host/ViGEm 日志只能证明虚拟手柄报告提交成功。还要结合前台窗口、controller 绑定、角色实际视觉位移、命令-位移 alignment 判断游戏是否真正消费了输入。

### P1：全局重定位昂贵，必须由 episode 和 cooldown 限制

同一失配不能每帧重定位。若日志里连续出现 `recovery_required` 却没有一次 `recovery_claimed`，优先检查 revision 消费和 worker generation，而不是先调匹配阈值。

### P2：墙格与实际人物位置可能有栅格误差

人物落在 native 墙格不代表真实人物被墙包围。应同时看小地图局部接触、左右自由空间和实际位移；不能只按大地图单个像素判定停止。

### P2：UI timer 是调度节拍，不是手柄脉冲时长

闭环控制器给出的 `command_duration_ms` 优先级高于 GUI timer 间隔。把 timer 周期直接当作手柄持续时间会导致速度漂移和穿墙/撞墙。

## 21. 一次完整会话的人工审查清单

- [ ] 地图实例、墙体和双人首帧都存在。
- [ ] 两个角色身份不同且 assignment 稳定。
- [ ] 启动帧年龄不超过 300 ms，未处于 warmup 假设。
- [ ] `sync_enter` 后确实收到更晚的完整帧并记录 `sync_ready`。
- [ ] 六秒延迟期间没有 Host lease 或手柄报告。
- [ ] PoE2 窗口成为前台后才出现 `output_armed`。
- [ ] runtime 使用 native 坐标，UI 旋转只影响展示。
- [ ] 路线经过原始墙体逐段验证，窄门没有被额外膨胀封死。
- [ ] 角色进入到达半径时，日志能区分视觉到达和预测接近。
- [ ] 角色短暂不可见时有 bounded prediction，而不是立即 stop。
- [ ] 无进度时先局部重规划和侧向脱困。
- [ ] 只有可靠接触证据或多次恢复失败才请求全局重定位。
- [ ] 每次全局重定位都有 `recovery_claimed`、首帧 worker 和 fresh sync。
- [ ] 恢复失败时是退避重试，不能形成每帧重定位风暴。
- [ ] 真正停止时 `follow_experiment.stopped.reason` 明确，且输出已中性释放。
- [ ] 长路线运行超过常规测试时长后仍不会出现 elapsed/max-duration 停止；若停止，应能在日志中对应到明确的安全或状态边界。

## 22. 参考源码入口

- 页面入口和跟随 tick：`src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py`
- 双人 worker 和恢复路由：`src/auto_modules/ui/modes/poe2_live_terrain/dual_motion_mixin.py`
- 双人视觉 tracker：`src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_localization/dual_motion.py`
- 双人首帧：`src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_localization/dual_first_frame_experiment.py`
- 跟随运行时：`src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_follow/runtime.py`
- 命令预测：`src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_follow/command_role_tracker.py`
- 手柄输出边界：`src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_follow/program_output.py`
- 通用局部控制：`src/auto_modules/core/routing/local_controller.py`
