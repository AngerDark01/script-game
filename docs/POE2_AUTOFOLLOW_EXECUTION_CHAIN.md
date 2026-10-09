# PoE2 自动跟随完整执行链

> 2026-10-09 更新：双人定位/自动跟随模块化链路的当前权威结构、周期、阈值和生命周期以 [POE2_FOLLOW_RUNTIME_CHAIN_AUDIT_20261009.md](POE2_FOLLOW_RUNTIME_CHAIN_AUDIT_20261009.md) 为准。本文保留历史问题背景；其中描述 UI relay、首帧 transform 未交接或预测到达后释放的段落只表示修复前行为。

> 文档状态：链路梳理与持续跟随语义已实现（2026-10-07）  
> 适用范围：实验页的单人实时跟随、双人实时跟随、双人同目标实验，以及与正式定位/导航共用的定位、路径和输出边界。  
> 本文描述“当前代码实际行为”，并在差异处注明理想语义和风险；本轮不修改运行代码、不发送真实输入。

## 1. 结论摘要

自动跟随实际上由两条角色链路组成：

```text
P1（手动领导者）
用户输入/游戏内移动
  -> 游戏状态
  -> 小地图视觉帧 + 地图坐标估计
  -> P1 目标位置

P2（程序跟随者）
P1 目标位置 + P2 最近可信位置
  -> 预测/视觉融合
  -> 局部路径规划
  -> 局部控制器
  -> 坐标/方向变换
  -> ProgramFollowOutput
  -> VirtualGamepad Host / ViGEm
  -> 游戏 P2 移动
  -> 下一帧视觉校准
```

本次实机异常的核心不是“按钮未启动”或“路线没有生成”，而是：

```text
动态跟随目标暂时保持不变
  -> P2 的 command_prediction 进入 arrival_radius
  -> runtime 误用静态目标的 WAITING_POSITION 语义
  -> ProgramFollowOutput.release()
  -> controller=2 变为中立/停止
```

触发证据为 `target_arrival_unconfirmed`。当时预测位置进入 12 native px 的到达半径，但最近一次可信 P2 视觉位置仍是旧位置，视觉没有确认到达。动态跟随不应仅凭预测距离进入释放状态。

另外，`Program session expired or was revoked` 是独立的输出会话短暂失效；它会造成约 1 秒级输入空档，但不等同于地图恢复。`poe2_not_foreground` 是窗口焦点门控，也不应被当成到达或定位失败。

## 2. 角色和模式定义

### 2.1 P1：手动领导者

- `mode=p1_leads` 时，P1 是领导者。
- P1 不由跟随程序发送移动脉冲；用户的键盘/手柄输入由游戏消费。
- 程序从新鲜视觉帧中识别 P1，并将其地图坐标发布为跟随目标。
- P1 位置短时不可见时，目标源可能退化为 `target_hold`，即沿用最后可信目标。

### 2.2 P2：程序跟随者

- P2 的当前状态来自视觉观测、上一帧状态、命令预测三者的融合。
- P2 的目标是 P1 的最新位置，或目标源为 `target_hold` 时的最后目标。
- P2 才会生成手柄脉冲；输入经 `ProgramFollowOutput` 交给虚拟手柄 Host。
- P2 的实际位移必须在后续视觉帧中重新吸收，不能把命令预测当成已确认事实。

### 2.3 静态目标与动态跟随目标

| 模式 | 目标来源 | 到达语义 |
|---|---|---|
| 双人同目标 | 鼠标点击的固定地图点 | 目标稳定且视觉确认后可进入 `ARRIVED/HOLD` |
| 实时跟随 | P1 阶段性视觉位置 | 目标可能继续移动；预测进入半径不能单独释放输出 |
| 目标暂时不可见 | `target_hold` + 预测 | 保持跟随、低幅校正或短时预测，等待新观测 |

当前代码已将动态 runtime 的近距离保持与静态到达语义分开：动态 runtime 返回 `FOLLOW_HOLD`，静态 runtime 仍使用 `ARRIVED/WAITING_POSITION`。此前的交叉链路和实机证据仍保留在下文，作为回归背景。

## 3. 组件关系和职责

### 页面与生命周期

- `capture_test_page.py:start_follow_experiment`（约 1469）：创建跟随 runtime、角色映射、输出适配器、计时器和会话边界。
- `_tick_follow_experiment`（约 2343）：定时入口，先处理页面生命周期、前台窗口和恢复，再进入实现体。
- `_tick_follow_experiment_impl`（约 2591）：消费最新帧/状态，更新角色、调用 runtime、应用输出和诊断。
- `_enter_live_follow_sync`（约 3660）：实时跟随冷启动同步。
- `_sync_live_follow_from_fresh_frame`（约 3682）：将新鲜双人视觉结果应用到跟随状态。
- `_request_live_follow_reanchor`（约 3760）：申请局部/全局重新锚定。

### 运行时与跟踪

- `runtime.py:tick`（约 451）：每个控制 tick 计算 follower observation。
- `runtime.py:_tick_follower`（约 459）：选择视觉位置、预测位置、目标、路线和局部控制状态。
- `runtime.py` 约 1042：闭环控制器，使用观察位移/速度反馈调整方向和脉冲时长。
- `runtime.py` 约 1118：命令预测相关逻辑。
- `command_role_tracker.py`：`seed` 初始化、`record_output` 记录手柄指令、`observe` 吸收视觉、`rebase_visual` 重锚、`estimate`/`_project` 预测。

### 输出

- `program_output.py:arm`：启动某个角色的输出会话。
- `program_output.py:apply`：对 observation 进行向量变换并写入输出；必要时重建过期 Host session。
- `program_output.py:release`：停止该角色输出并清除 armed 状态。
- `program_output.py:_STOP_STATES` 当前包含 `ARRIVED`、`WAITING_POSITION`、`BLOCKED`、`MAP_MISMATCH`、`MANUAL`。

### 正式页面可借鉴的边界

- 绘图页 `MappingSession.tick`：采集、识别、拼接一次完成；人物识别失败回退上一帧/中心，不让 UI 逻辑阻塞控制帧。
- 导航页 `NavigationRuntimeFrameLoop`：capture → local position → localize → task update → render；事件识别异步，定位主帧保持轻量。
- 实验页目前仍在同一实时处理路径中混合候选提取、墙体处理、tracker、证据归档和 UI drain，实际有效频率曾降至约 14.4 FPS。

## 4. 启动和冷启动时序

```text
用户点击“开始实时跟随”
  1. start_follow_experiment()
  2. 检查已有 session/timer/output，防止重复租约
  3. 创建 live follow runtime
  4. 设置 leader=P1、program_roles=(P2)
  5. 清理旧点击目标，保存 session_id/generation
  6. 设置 output_not_before_ms（若配置了冷启动延迟）
  7. 启动 follow timer
  8. 立即执行一次 _tick_follow_experiment()
  9. _enter_live_follow_sync 等待新的双人视觉帧
 10. 接收首个有效 bundle 后校验 map instance、transform、两角色上下文
 11. sync_ready，进入 tracking
 12. P2 program output arm；只有到达输出允许时间且游戏在前台才写入脉冲
```

冷启动延迟只解决“给用户切回游戏窗口”的时间问题，不会解决预测/视觉语义冲突。窗口失焦时应保持 runtime 上下文，暂缓输入并记录 `poe2_not_foreground`，不能触发地图重定位。

## 5. P1 位置产生链路

### 正常链路

```text
用户按键/手柄移动 P1
  -> 游戏更新 P1
  -> capture 获取小地图帧
  -> 墙体/人物候选提取
  -> 双人角色关联（颜色 + 位置 + 相对几何）
  -> 结合全局 transform 投影到 native 坐标
  -> P1 visual sample
  -> runtime.remote.position 更新
```

P1 的位置事件通常记录为 `manual_leader_visual_move` 和 `live_role_follow.target`。程序不为 P1 生成跟随脉冲；它只把 P1 的观测作为 P2 的目标。

### P1 暂时失配

候选存在但颜色受干扰、两个角色重叠、帧处理延迟或遮挡时：

1. 先用动态预测门限和上一帧身份关联；
2. 用双人相对距离/相对方向约束辅助身份；
3. 仍无可靠候选时保留最后可信 P1 点，并进入 `target_hold`；
4. 在有界预测窗口内继续运行；
5. 只有地图实例、transform 或不确定度真正越界才请求局部/全局恢复。

不能将单帧 P1 视觉丢失直接解释为“P1 到达”或“P2 应停止”。

## 6. P2 位置、预测和融合链路

### 6.1 视觉可用

P2 位置优先使用最新有效视觉观测，保存采集时间戳，不以控制 tick 时间覆盖旧帧时间。跟踪器同步更新速度、上一位置和角色身份。

### 6.2 视觉暂时不可用

命令跟踪器使用：

```text
p̂(k+1) = p(k) + (α·v_visual + β·u_command·v_command)·Δt
σ(k+1) = σ(k) + σ_process·Δt + σ_visual_gap
```

其中 `u_command` 是已发送手柄方向，`v_command` 是速度估计。预测只用于短时保持和继续输出，不能直接作为“视觉已确认到达”。

### 6.3 视觉恢复

新观测 `z` 到达时，避免一帧颜色噪声造成跳变，可使用：

```text
p = (1-K)·p̂ + K·z
K = σ_prediction² / (σ_prediction² + σ_observation²)
```

融合后重新 `rebase_visual`，恢复 `VISUAL_TRACKING`；不应重置整个跟随 session。

## 7. 单个跟随 tick 的完整时序

```text
QTimer / latest-result 回调
  ↓
生命周期门控
  - 页面是否仍可见
  - session/generation 是否当前
  - 游戏是否前台
  - 是否处于冷启动等待
  ↓
取得最新结果
  - 旧帧丢弃，不排队追赶
  - 记录 captured_at_ms
  ↓
视觉阶段
  - 墙体位移/transform（可低频）
  - P1/P2 候选提取（高频）
  - 颜色软评分、位置预测、双人相对几何关联
  ↓
状态吸收
  - 有效视觉：更新位置/速度/身份
  - 暂时失配：沿用上一可信状态并增加 prediction_age
  - 地图失效：提出 reanchor 请求
  ↓
runtime.tick(now_ms)
  - 取目标 P1 或 target_hold
  - 取 P2 visual/command_prediction
  - 计算距离、方向、路线、局部控制状态
  - 生成 FollowObservation
  ↓
输出层
  - arm/rearm（必要时恢复 Host session）
  - 检查 output_not_before、foreground、状态
  - transform 后写入 controller=2 向量和持续时间
  - 记录 report/result/ack
  ↓
下一帧
  - 用实际视觉位移校准速度和预测
  - 更新 route progress、no-progress、recovery 计数
  - UI overlay/evidence 低频渲染，不阻塞控制路径
```

## 8. 正常跟随时序

```text
P1 移动
  -> 新 P1 visual sample
  -> target 更新
  -> P2 当前点与目标计算路线
  -> 局部控制器选方向/脉冲时长
  -> ProgramFollowOutput.apply
  -> Host/ViGEm 接收 controller=2
  -> P2 游戏内移动
  -> 新帧观察到位移
  -> 更新 observed_displacement/observed_speed
  -> 缩短或延长下一次脉冲
```

当 P1 停下且 P2 已在跟随半径内，动态跟随的正确行为是：保持短时低幅校正或中立保持，但保留 session 和跟随循环；P1 再次移动后立即恢复输出。不能把一次预测距离命中直接变成永久 release。

## 9. 路径规划、门和贴墙处理

1. 目标 native 坐标先做局部可行走投影：中心栅格不可走时检查 3×3/5×5 邻域，选择距离目标近且局部可达的点。
2. 路径规划优先短路，但对贴墙、死路和局部自由空间增加代价；不能依靠过大的人物膨胀半径把窄门全部封死。
3. `no_safe_route` 只能表示本轮规划未找到路线，不代表现实中无路；允许短脉冲探索并在下一帧重规划。
4. 实际游戏中人物可贴墙但不会“陷入墙体”；地图坐标和视觉坐标重合时，应优先视为投影/栅格误差，结合小地图和实际位移纠偏。
5. 连续无进展时改变局部方向、降低脉冲时长、重新规划；不要直接释放输出。

## 10. 到达、保持和当前异常链路

### 10.1 静态目标的合理到达条件

建议的语义是：

```text
目标稳定窗口
  + 至少一次新的可信视觉确认
  + 连续 N 个 tick 距离 <= arrival_radius
  -> ARRIVED/HOLD
```

### 10.2 当前实际异常（重点）

日志证据：

```text
目标=(960.3059, 974.3315)
P2 current/predicted=(957.8049, 981.7013)
distance=7.7826 <= arrival_radius=12.0
current.source=command_prediction
target.source=target_hold
最近可信 P2 视觉位置=(900.0785, 1070.1693)
```

实际调用链：

```text
P1 新视觉暂时不可用
  -> remote target source=target_hold
P2 仍未被新视觉吸收
  -> command_prediction 继续推进
预测距离进入 12px
  -> runtime.py 近距离分支返回 arrival_unconfirmed
  -> FollowState.WAITING_POSITION
  -> ProgramFollowOutput.apply 命中 _STOP_STATES
  -> release() / stop()
  -> controller=2 变为中立，P2 不再移动
```

历史上的 `target_arrival_unconfirmed` 不是无害诊断，而是实际停止输出的状态转换。根因是把动态跟随的 `target_hold` 和静态目标的到达分支混用，同时没有要求新的视觉确认。当前实现已将该分支改为 `FOLLOW_HOLD`，并由连续角色输出适配器保持租约；这个历史链路仍必须保留为回归用例。

### 10.3 与本次相邻的两个独立异常

**输出 session 过期**

```text
Program session expired or was revoked
  -> VirtualGamepadClient 拒绝 write
  -> 约 1.1 秒后 output_armed
  -> Host 继续接受 controller=2
```

这是输出适配层异常，应在该层重建 session、重发最近一次有效方向；不应触发地图级恢复或清除目标。

**游戏窗口失焦**

```text
poe2_not_foreground
  -> 暂缓消费真实输入并发送中立帧，保持连续角色租约
  -> 等待游戏重新前台
```

这是输入门控，不是首帧失败、路径失败或到达确认。需单独记录前台句柄、等待开始/结束时间。

## 11. 视觉异常与恢复层级

```text
VISUAL_TRACKING
  ├─ 新帧有效 -> 更新观测/速度
  └─ 单帧异常 -> PREDICTIVE_HOLD

PREDICTIVE_HOLD
  ├─ 新帧恢复 -> 融合 -> VISUAL_TRACKING
  ├─ 预测窗口内仍异常 -> 继续输出短脉冲
  └─ 不确定度/地图有效性越界 -> LOCAL_REANCHOR

LOCAL_REANCHOR
  ├─ 局部匹配成功 -> rebase -> PREDICTIVE_HOLD/VISUAL_TRACKING
  └─ 局部地图失效或实例变化 -> GLOBAL_RECOVERY

GLOBAL_RECOVERY
  -> 重新获得首帧/变换
  -> 校验 instance、角色 bundle、generation
  -> 恢复原跟随目标和输出 session
```

升级条件必须基于连续异常、预测不确定度、地图实例/变换有效性，而不是单个颜色候选缺失。恢复期间要保留目标、最后可信位置和输出上下文；迟到 worker signal 只能丢弃，不能覆盖新 generation。

## 12. 性能和帧处理链

当前实时 worker 的有效数据曾为：

```text
effective_fps ≈ 14.4
processing_ema_ms ≈ 58.5ms
dropped_results ≈ 225
```

因此“请求 30 FPS”不等于“有效处理 30 FPS”。控制链应采用：

- capture latest-only：只保留最新原始帧；
- 人物候选/关联高频；
- 墙体 mask、预览、overlay、evidence 低频；
- 旧帧直接丢弃，不让延迟帧参与身份关联；
- 每帧记录 capture、recognition、candidate、tracking、total 时间；
- 当处理时间超过周期时优先降低非控制工作，而不是堆积队列。

日志字段至少应覆盖 `session_id`、`generation`、`captured_at_ms`、`processed_at_ms`、`candidate_count`、`prediction_active`、`prediction_age_ms`、`target_source`、`current_source`、`distance`、`state`、`reason`、`controller`、`axes`、`inputOwner`、`rearm_count`、`foreground` 和 `dropped_results`。

## 13. 状态和参数基线

```text
arrival_radius                 = 12.0（live follow）
resume_radius                  = 20.0
speed_units_per_second         = 80.0
closed_loop expected_speed     = 80.0
footprint_radius               = 3.0
inflate_collision              = False
stalled_ticks                  = 8
contact_required_samples       = 4
local_lookahead                = 24.0
prediction_horizon             = 0.25s
visual_phase_grace_ms          = 750
FOLLOW_RUNTIME_MAX_FRAME_AGE_MS= 700
```

这些数值是当前基线，不代表所有场景都应固定使用。尤其 `speed_units_per_second` 必须由实际视觉位移和脉冲时长持续校准；`arrival_radius` 必须区分静态定点和动态跟随；`visual_phase_grace_ms` 应与首次有效输出时刻对齐，而不是只从按钮点击时刻开始。

## 14. 诊断时序模板

### 正常

```text
sync_ready
 -> output_armed
 -> program_ready/route_ready
 -> command_written
 -> visual_observed
 -> observed_displacement/observed_speed
 -> next command
```

### 暂时失配

```text
candidate_missing/rejected
 -> prediction_active=true
 -> command_prediction
 -> command_written（不停止）
 -> next visual frame
 -> visual_recovered + rebase_visual
```

### 输出会话异常

```text
write_failed: session_expired
 -> host_online check
 -> output rearm
 -> first_successful_report
 -> continue same target/prediction
```

### 当前 target arrival 异常

```text
target_hold
 -> predicted distance <= arrival_radius
 -> target_arrival_unconfirmed
 -> WAITING_POSITION
 -> release()
```

这条历史链应作为回归用例重点锁定：动态跟随不能仅凭这三个条件释放 P2 输出。当前实现的对应链路是 `target_hold -> FOLLOW_HOLD -> neutral/低幅控制 -> 保留 session`。

## 15. 动态跟随的停止语义（最高优先级）

实时跟随是持续性动作。启动后，跟随 session 只能由以下人工动作结束：

```text
用户点击“停止跟随”
用户主动切换到手动控制
用户关闭页面/程序
```

目标接近、目标静止、目标暂时不可见、P2 视觉失配、路径规划失败、贴墙、窗口失焦、手柄 session 过期和局部/全局重定位，都不能结束跟随 session。它们只能改变当前 tick 的控制策略。

动态跟随中不再使用“到达后释放输出”的语义：

```text
距离进入跟随半径
  -> 保持 session
  -> 当前 tick 可输出中立或低幅校正
  -> 继续监听 P1
  -> P1 位置变化后恢复正常移动
```

这里的中立帧只表示当前时刻不需要加大位移，不表示调用 `release()`，也不表示停止计时器、清除目标、销毁 runtime 或进入最终状态。输出适配器对连续角色的 `release_all()` 只发送中立帧并保留租约；中立帧和移动脉冲都经过统一的 Host session 重建边界；只有 `close_all()` 内部的强制释放路径才真正释放。

静态双人同目标实验仍可以有 `ARRIVED`，但它必须留在静态目标 runtime 内；不能让静态目标的 `WAITING_POSITION`、`ARRIVED` 或 `BLOCKED` 直接成为动态跟随输出层的停止依据。

## 16. 待处理问题清单

### P0：任何普通异常都可能结束动态跟随

当前风险链是：

```text
runtime 状态被判定为 WAITING_POSITION / BLOCKED / MAP_MISMATCH
  -> ProgramFollowOutput._STOP_STATES
  -> release()
  -> P2 输出停止
```

需要把动态跟随的控制状态和静态导航的终止状态分开。动态跟随应有一个持续 session 状态集合，例如：

```text
FOLLOWING
FOLLOW_HOLD
FOLLOW_PREDICTING
FOLLOW_REPLANNING
FOLLOW_RELOCATING
FOLLOW_REARMING
```

这些状态都保持同一个 session、目标、角色上下文和 timer。只有显式用户停止才执行最终 `stop_follow_experiment` 和 `release_all`。

### P1：预测位置命中半径被误认为到达

`target_hold + command_prediction + distance <= arrival_radius` 仍可能触发 `target_arrival_unconfirmed`。这条分支在动态跟随中必须改为 `FOLLOW_HOLD` 或低幅校正，不能产生 `WAITING_POSITION`，也不能调用 `release()`。

动态跟随保持时仍要保存：

- P1 最后可信位置和目标时间戳；
- P2 最后可信视觉位置；
- 命令预测位置、速度和不确定度；
- 最近一次输出方向和脉冲时间；
- 当前 session/generation。

### P1：P1 目标暂时失配时目标状态不清晰

需要区分：

```text
target_visual_fresh       新鲜 P1 观测
target_visual_degraded    P1 暂时失配，短时沿用/预测
target_hold               最后可信目标保持
target_relocalizing       正在局部或全局恢复
```

`target_hold` 只表示目标暂时没有新观测，不能表示 P1 已经到达或跟随任务结束。P1 恢复后应更新目标并继续同一 session。

### P1：P2 视觉失配时不应停止移动

P2 marker 丢失、颜色被干扰、两个人物重叠或处理帧过旧时，应按“上一可信位置 + 视觉速度 + 已发送手柄方向 + 时间间隔”继续短时预测。预测窗口内保持输出；超过窗口时进入 `FOLLOW_RELOCATING`，恢复成功后回到跟随，而不是停止整个 runtime。

恢复时需要防止一帧错误颜色把 P2 拉到错误位置，应使用观测置信度融合并记录 `prediction_age_ms`、`uncertainty` 和 `rebase_reason`。

### P1：路径规划失败不能成为自动停止

`no_safe_route` 只说明当前地图、当前坐标或当前局部规划没有给出可行路线。它不等价于现实中没有道路。

处理顺序应为：

```text
当前路线失败
  -> 检查目标邻域投影
  -> 使用局部自由空间重新规划
  -> 调整方向/缩短脉冲探索
  -> 下一帧结合实际位移重规划
  -> 必要时局部重锚
```

`no_safe_route_cooldown` 只能抑制重复规划频率，不能抑制跟随输出，更不能调用 session stop。除非用户停止，否则必须保持探索、重规划或恢复状态。

### P1：撞墙/无进展判断可能把贴墙误判成终止

人物可以贴近墙体或穿过窄门，native 栅格与视觉中心也可能有偏移。连续无进展只能触发：改变局部方向、缩短脉冲、重新投影目标、局部重定位。不能因为 `BLOCKED` 或 `contact` 计数达到阈值就释放动态跟随输出。

判定应同时参考：

- 小地图人物相对墙体的位置；
- 实际视觉位移；
- 手柄方向和脉冲持续时间；
- 目标方向及局部自由空间；
- 最近几帧的位姿变化。

### P1：输出 session 失效需要留在跟随 session 内恢复

`Program session expired or was revoked` 的处理链应是：

```text
write_failed
  -> 检查 Host 是否在线
  -> 重建 program session
  -> 重新 arm controller
  -> 重发最近一次有效方向或安全中立帧
  -> 继续当前 follow session
```

不能清除目标、重建整个地图 runtime 或把该错误映射成 `MAP_MISMATCH`/`STOP`。只有 Host 明确永久断开且多次重建失败，才进入需要人工处理的故障状态；即使如此，也要保留 session 上下文，不能静默自动结束。

### P1：游戏窗口失焦只能暂停输入消费

`poe2_not_foreground` 的正确处理是：记录焦点状态，暂缓真实手柄写入，继续保留目标、预测和跟随 timer；窗口回到前台后重新校准并恢复输出。失焦期间不能触发 target arrival、地图恢复或自动停止。

### P2：重定位必须是跟随内部的恢复阶段

局部/全局重定位要保存并恢复：

- 原跟随 session_id/generation；
- P1 最后目标及其来源；
- P2 最后可信位置和预测状态；
- 当前路线和局部控制状态；
- 输出角色和 Host controller 绑定。

重定位成功后回到 `FOLLOWING` 或 `FOLLOW_PREDICTING`。重定位失败时继续按照有限预测和局部探索运行，并提高诊断级别；不能因为恢复耗时或单次失败就自动结束跟随。

### P2：实时处理过载会放大所有上层异常

当前约 `14.4 FPS` 有效处理、`processing_ema≈58.5ms`、大量 dropped results，会使 P1 目标变旧、P2 视觉确认延迟、命令预测偏离，最终放大误到达和误判无进展。

处理优先级应固定为：

```text
最新帧采集
  -> P1/P2 候选与关联
  -> runtime 控制决策
  -> 手柄输出
  -> 墙体重处理、overlay、evidence、详细日志低频执行
```

任何性能优化都必须保证控制链不因预览、截图保存或详细日志阻塞。需要用阶段耗时判断瓶颈，再决定是否拆分流水线或迁移单一热函数。

### P2：会话和状态生命周期需要单一所有者

页面 timer、实时 worker、重定位 worker、输出对象和迟到 signal 之间存在交叉风险。每个跟随 session 必须有 generation；旧 generation 的结果只能记录，不能修改当前 session。所有结束动作都必须经过唯一的人工停止/页面关闭路径，避免某个异常分支私自调用 `release_all`。

## 17. 新的动态跟随验收链

后续实现必须满足以下行为：

```text
点击开始
  -> session 建立
  -> P1/P2 首帧完成
  -> P2 持续跟随

P1 停止且 P2 接近
  -> P2 保持/低幅校正
  -> session 仍存在

P1 再移动
  -> P2 自动恢复追赶

P1 暂时不可见
  -> target_hold/预测
  -> P2 继续有限移动

P2 暂时不可见
  -> command_prediction
  -> 继续跟随
  -> 新帧恢复后融合

路径失败、贴墙、无进展
  -> 探索/重规划/重定位
  -> session 不结束

Host session 失效
  -> rearm
  -> session 不结束

窗口失焦
  -> 暂停输入消费
  -> 回到前台后恢复

只有用户点击停止
  -> release 输出
  -> 停止 timer/worker
  -> 结束跟随 session
```

## 18. 待讨论的设计问题

1. `FOLLOW_HOLD` 是否允许发送低幅校正，还是只发送中立帧并等待 P1 位移？
2. P1/P2 暂时失配时，预测窗口和不确定度上限如何由实机速度标定？
3. 输出 session 失效时，Host 在线的自动重建次数和重建超时如何设置？
4. 局部重定位失败后，允许预测和探索持续多久才提示人工处理？提示不能自动结束跟随。
5. 14.4 FPS 的瓶颈最终来自哪一段：候选、墙体、tracker、UI 还是日志？应先用阶段耗时决定是否升级到三级流水线或 C/Cython，而不是先迁移语言。
6. 正式导航页与实验页应共享的底层接口应是“观测→状态→意图→输出命令”，业务页不应复制识别、预测和手柄会话逻辑。

## 16. 相关代码和证据

- `src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py`
  - `start_follow_experiment` 约 1469
  - `_tick_follow_experiment` 约 2343
  - `_tick_follow_experiment_impl` 约 2591
  - `_enter_live_follow_sync` 约 3660
  - `_sync_live_follow_from_fresh_frame` 约 3682
  - `_request_live_follow_reanchor` 约 3760
- `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_follow/runtime.py`
  - `tick` 约 451
  - `_tick_follower` 约 459
  - `target_hold/command_prediction` 到达分支约 498
  - 闭环控制约 1042，预测约 1118
- `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_follow/command_role_tracker.py`
- `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_follow/program_output.py`
- `data/logs/poe2_live_terrain.log`
- `C:/Users/12074/AppData/Local/AutoModules/Workbench/logs/virtual-gamepad-host.log`
- `docs/POE2_FOLLOW_ROLLBACK_CHECKPOINT.md`
