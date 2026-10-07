# PoE2 双人跟随双通道引擎重构方案

日期：2026-10-07  
基线提交：`ea72667 checkpoint: isolate follow recovery boundaries`

## 1. 目标与边界

本次重构解决三个已经被实机日志确认的问题：

1. P2 视觉标记失配后进入 `occlusion_held`，没有及时做局部重定位。
2. 预测位置和视觉位置分属不同口径，命令预测可以在错误位置上持续累积。
3. 截图、视觉处理、预测、路径、输出和恢复共享 Qt 控制链，任何重型阶段都会拖慢控制节拍。

目标运行模型是两个长期运行的业务进程、一个 Qt UI 进程和已有的 Host 进程：

```text
Qt UI process
    ├── user commands / map rendering / diagnostics
    ├── VisionProcess     ← latest-only frame input
    └── FollowControlProcess
          ├── prediction
          ├── visual/prediction fusion
          ├── path planning
          ├── recovery state machine
          ├── memory fast reanchor (one low-frequency task)
          └── output scheduler → VirtualGamepadHost
```

本次不把每一种异常拆成独立进程。预测和融合属于同一控制域，放在 `FollowControlProcess` 内；内存和全局恢复属于单次低频任务，受同一进程的恢复预算管理。

动态跟随的停止条件保持为用户手动停止、地图实例确实变化或页面关闭。视觉丢失、局部匹配失败、内存失败、路径失败和 Host session 失效都只能进入恢复或保持状态，不能自动释放跟随 session。

## 2. 当前代码到目标模块的映射

| 当前位置 | 当前职责 | 目标位置 |
|---|---|---|
| `ui/modes/poe2_live_terrain/dual_motion_worker.py` | 截图、墙体、人物候选、DualVisualTracker | `follow_engine/vision/vision_process.py` 及其 processor |
| `ui/modes/poe2_live_terrain/capture_test_page.py` 的视觉 drain | 读取最新 worker 结果并更新页面状态 | `follow_engine/ui_adapter.py` 只读取快照 |
| `capture_test_page.py` 的 `_current_follow_prediction_hints`、预测分支 | 命令位移预测 | `follow_engine/tracking/command_odometry.py` |
| `multiplayer_follow/command_role_tracker.py` | 视觉速度、命令预测、观测估计 | `follow_engine/tracking/`，保留通用角色 tracker 接口 |
| `capture_test_page.py` 的跟随 tick | 目标、路径、输出、恢复编排 | `follow_engine/control/follow_control_runtime.py` |
| `multiplayer_follow/runtime.py` | 角色目标和路径观察 | 作为 control runtime 的纯领域组件继续复用 |
| `recovery/recovery_coordinator.py` | 恢复动作策略 | `follow_engine/recovery/recovery_policy.py` |
| `recovery/memory_fast_reanchor.py` | 单次内存快速锚定 | `follow_engine/recovery/memory_recovery.py` |
| `recovery/global_reanchor.py` | 最终全局 worker 适配 | `follow_engine/recovery/global_recovery.py` |
| `multiplayer_localization/memory_anchors.py` | PoE2 内存读取 | `adapters/poe2/memory_position_source.py`，保留只读适配器边界 |
| `adapters/virtual_gamepad/program_output.py` | Host program session、heartbeat、输出 | control process 中的 `output_scheduler.py` + 现有 adapter |
| `capture_test_page.py` | Qt UI 和业务编排混合 | `follow_engine/ui_adapter.py`，页面只负责组合和显示 |

迁移期间旧模块保持兼容，采用 feature flag/generation 切换；新引擎通过同一 `FollowEnginePort` 接口接入页面，旧页面编排在新链路验收后删除。

## 3. 进程职责

### 3.1 VisionProcess

唯一负责截图和视觉处理，拥有自己的截图 provider、OpenCV/PIL 状态和视觉 tracker。它不访问 Qt 控件、虚拟手柄、游戏内存或路径规划器。

每轮处理顺序：

1. 从 `FrameRing` 取最新截图；旧 sequence 直接丢弃。
2. 使用固定首帧 transform 把局部画面映射到 reference-native 空间。
3. 更新墙体位移；墙体完整重处理按 15–20Hz 节流。
4. 提取 P1/P2 候选并按位置连续性、颜色、速度方向和双人相对几何关联身份。
5. 如果某个角色视觉失配，在该角色预测位置附近尝试 ROI 半径 `80/140/220` native px。
6. 发布 `VisualObservation`；不因为候选失败而发布停止命令。

建议频率：截图 30Hz，人物候选 25–30Hz，局部 ROI 按新帧尝试，预览 10–15Hz，证据归档降频。

### 3.2 FollowControlProcess

控制进程以 30–60Hz 运行轻量循环，独立于视觉处理速度。它接收最新视觉观测、目标快照、Host 输出确认和地图快照，连续运行：

1. 读取最新视觉结果和最新手柄输出记录。
2. 推进每个角色的 command odometry 和速度估计。
3. 计算视觉位置与预测位置的融合结果。
4. 以融合位置执行局部路径规划和运动控制。
5. 根据恢复状态机决定正常输出、短脉冲、局部纠偏、内存任务或全局任务。
6. 将 `OutputIntent` 交给 output scheduler，并发布 `FollowSnapshot` 给 UI。

视觉进程不响应时，控制进程仍然以预测状态运行；控制进程不等待视觉 future，不等待全局注册完成。

### 3.3 Qt UI process

UI 只负责：

- 启动/停止引擎；
- 设置 P1/P2、目标和参数；
- 显示地图、截图、轨迹和阶段耗时；
- 显示恢复状态及其原因；
- 转发手动停止命令。

UI 不再直接调用截图、tracker、路径规划、内存读取或 `_start_dual_motion(recovery=True)`。

## 4. 进程间数据契约

所有消息都必须包含 `generation`、`sequence`、`captured_at_ms` 和 `map_instance`。结果应用前必须校验四者，迟到结果只能记录，不能覆盖当前会话。

### 4.1 FrameSlot

截图使用固定大小的共享内存 ring，容量 2 或 3。slot 字段：

```text
sequence: uint64
generation: uint32
captured_at_ms: int64
map_instance: str
height: int
width: int
raw_offset / raw_size
status: EMPTY | WRITING | READY | READING
```

生产者始终写入最新空 slot；消费者只读取最高 sequence。禁止无界 `multiprocessing.Queue` 堆积完整图片。

### 4.2 VisualObservation

```text
generation
sequence
captured_at_ms
map_instance
roles: {role_id: RoleVisualObservation}
wall_shift
wall_quality
assignment_score
local_match_score
local_match_radius
source: visual | local_roi | partial | none
processing_ms: capture / wall / marker / local / total
```

`RoleVisualObservation` 包含：

```text
identity
position_native
velocity_native
confidence
uncertainty_native
visible
last_visual_at_ms
association_cost
```

### 4.3 PredictionSnapshot

```text
generation
tick_sequence
created_at_ms
roles: {role_id: RolePrediction}
last_command
command_duration_ms
calibration_confidence
```

每个角色的预测记录：

```text
position_native
velocity_native
uncertainty_native
source: visual_seed | command_prediction | fused
visual_age_ms
prediction_age_ms
```

### 4.4 FusionSnapshot

```text
generation
created_at_ms
roles: {role_id: RoleFusedState}
target_snapshot
recovery_state
recovery_reason
route
control_vector
output_intent
```

UI 只消费这个快照和阶段耗时，不读取进程内部可变对象。

## 5. 双通道定位与融合算法

### 5.1 预测

```text
v_command = calibrated_speed × input_direction
v_estimated = α × v_visual + β × v_command + γ × v_previous
p_pred(t+Δt) = p_fused(t) + v_estimated × Δt
```

不确定度：

```text
σ_pred(t+Δt) = σ_fused
              + σ_visual_gap
              + σ_speed_error × Δt
              + σ_command_error × output_duration
```

预测必须设置时间和距离上限。超过上限时继续输出低幅度纠偏脉冲，但不能继续把预测当作高可信当前位置。

### 5.2 视觉融合

```text
K = σ_pred² / (σ_pred² + σ_visual²)
p_fused = (1-K) × p_pred + K × p_visual
```

视觉新鲜且可信时快速吸收；视觉模糊或只有部分候选时保留预测连续性。

### 5.3 双人几何约束

持续记录：

```text
d_observed = distance(P1_visual, P2_visual)
d_predicted = distance(P1_fused, P2_fused)
```

当两者差异超过动态容错时降低关联置信度：

```text
dynamic_tolerance = marker_error
                  + max_speed × frame_gap
                  + processing_latency_error
```

身份评分由位置连续性、速度方向、颜色相似度、双人相对距离和墙体位移共同决定。颜色不能单独决定身份。

## 6. 恢复状态机

每个角色拥有独立恢复状态；动态跟随拥有一个共享 session。状态：

```text
VISUAL_TRACKING
VISUAL_DEGRADED
PREDICTING
LOCAL_REANCHORING
MEMORY_REANCHORING
GLOBAL_REANCHORING
FOLLOW_HOLD
FOLLOW_REARMING
```

转移规则：

```text
新鲜视觉成功              → VISUAL_TRACKING
单帧视觉失败              → VISUAL_DEGRADED + 预测继续
视觉年龄 > 600ms          → LOCAL_REANCHORING
局部匹配成功              → VISUAL_TRACKING
局部连续失败/σ > 50       → MEMORY_REANCHORING
内存成功                  → VISUAL_TRACKING（seed + 融合）
内存失败                  → PREDICTING + GLOBAL_REANCHORING pending
全局成功                  → VISUAL_TRACKING
任意临时异常              → 保持 follow session
用户手动停止              → 释放 output lease
```

初始门槛：视觉年龄 `250ms/600ms/1500ms/3000ms` 四级，预测不确定度 `20/50/100` native px 三级；这些都是配置项，必须通过离线回放和实机样本校准。

`occlusion_held` 的语义改为“保持 session 和低幅输出”，同时触发局部纠偏。它不能阻止恢复策略，也不能无限期使用 command prediction。

## 7. 内存与全局恢复

内存快速重锚作为控制进程内的单次异步任务：

1. 检查冷却、地图实例和 transform。
2. 一次读取双人位置。
3. 映射到 reference-native。
4. 校验 generation、实例、角色数量和坐标范围。
5. seed tracker，重置预测不确定度。
6. 继续当前目标和 session。

全局恢复作为最终异步任务：

- 每个 generation 最多一个；
- 由独立 worker 执行；
- 期间继续预测和低幅输出；
- 成功后发布完整视觉锚点；
- 失败后保留 session，等待下一次局部/内存机会。

## 8. 手柄输出闭环

输出诊断拆成四层：

```text
output_submitted
host_acknowledged
game_motion_observed
visual_position_confirmed
```

`controller=2 acquired=True` 只代表 Host 接收，不能当作游戏位移证据。速度校准只使用可信视觉或内存的实际位移：

```text
v_observed = distance(p_new, p_old) / elapsed_visual_time
v_calibrated = λ × v_observed + (1-λ) × v_previous
```

Host heartbeat 由 output scheduler 独立维护，不能依赖重型视觉/恢复 tick；session 失效时只重建输出 lease，不触发地图级恢复。

## 9. 源码拆分目标

目标目录：

```text
features/poe2/live_terrain/follow_engine/
├── contracts.py
├── generation.py
├── latest_frame_buffer.py
├── shared_frame_ring.py
├── process_supervisor.py
├── vision/
│   ├── vision_process.py
│   ├── capture_adapter.py
│   ├── wall_processor.py
│   ├── marker_processor.py
│   ├── local_roi_matcher.py
│   └── dual_association.py
├── tracking/
│   ├── command_odometry.py
│   ├── velocity_calibrator.py
│   ├── position_fusion.py
│   └── tracking_state.py
├── recovery/
│   ├── recovery_policy.py
│   ├── local_recovery.py
│   ├── memory_recovery.py
│   └── global_recovery.py
└── control/
    ├── follow_control_runtime.py
    ├── route_controller.py
    ├── output_scheduler.py
    └── control_diagnostics.py
```

页面目标只调用：

```text
engine.start(config)
engine.update_target(target)
engine.snapshot()
engine.stop(reason="user")
```

## 10. 分阶段小目标

### M0：冻结基线和回放夹具

- 保存当前提交和最新实机 evidence 索引。
- 建立单角色、双角色、P2 视觉丢失、恢复成功、Host session 失效五组回放。
- 把每个回放的预期状态和位置误差写成验收数据。

验收：回放可重复；不发送真实输入；同一输入得到同一融合结果。

### M1：抽离纯逻辑契约

- 新建 `contracts.py`、`tracking_state.py`、`position_fusion.py`、`recovery_policy.py`。
- 将预测、置信度、视觉年龄和恢复状态从页面移出。
- 保留旧页面作为 adapter，行为保持不变。

验收：纯 Python 单元测试覆盖视觉正常、单帧失配、长时间失配、预测超限、内存成功/失败。

### M2：实现 VisionProcess

- 把 `Poe2DualMotionWorker` 的截图和识别逻辑迁移到独立进程。
- 引入 latest-only ring；禁止无界队列。
- 实现局部 ROI 的真实候选输出。
- 添加 process generation、退出、异常和重启协议。

验收：视觉进程处理延迟稳定；旧帧不会堆积；UI 线程不执行图像识别。

### M3：实现 FollowControlProcess

- 将页面中的预测分支、融合、路径和恢复编排迁移到控制进程。
- 预测与视觉订阅独立运行。
- 恢复动作只由控制进程状态机决定。
- 输出 scheduler 接管 Host session、heartbeat 和输出节拍。

验收：视觉进程暂停时预测仍运行；视觉恢复后能吸收；异常不会自动停止 session。

### M4：接入内存和全局恢复

- 将 warm memory source 接入控制进程。
- memory 结果带 generation/instance/transform 校验。
- global recovery 变成最终异步 backend。
- 删除 live 页面直接调用旧恢复入口。

验收：局部成功不读内存；内存成功不全局注册；内存失败才全局；迟到结果被丢弃。

### M5：UI 适配和旧链路下线

- 新建 `follow_engine/ui_adapter.py`。
- 页面只做配置、按钮、地图和诊断展示。
- 删除页面内直接访问 tracker、memory provider 和 global worker 的代码。
- 保留静态点击导航的独立 adapter。

验收：live 跟随调用旧 `RecoveryController` 次数为 0；页面不持有视觉/预测可变状态。

### M6：性能与异常压力测试

- 视觉进程 CPU、内存、帧延迟和丢帧测试。
- 控制进程 30/60Hz 稳定性测试。
- 内存读取冷却、进程崩溃、Host session 失效、窗口失焦和地图变化测试。
- Windows spawn/退出/重启测试。

验收目标：预测 ≥30Hz，视觉 ≥20Hz，局部 ROI <20ms，融合 <5ms，普通路径 <15ms，UI tick 不被重型任务阻塞。

### M7：实机分级验收

1. 静止双人。
2. P1 单方向移动。
3. P1 连续转向。
4. P2 短时视觉丢失。
5. P2 长时视觉丢失。
6. 两人靠近和分离。
7. 经过门和窄道。
8. Host session 重建。
9. 地图实例变化。
10. 完整地图运行，不设置时间上限。

## 11. 风险与防护

| 风险 | 防护 |
|---|---|
| Windows multiprocessing spawn 重复初始化 Qt | 子进程入口放在独立模块，禁止 import UI，使用显式 `if __name__ == "__main__"` |
| 共享帧复制造成性能下降 | 固定大小 shared memory ring，只传 slot 元数据 |
| 旧结果覆盖新会话 | 每个结果校验 generation、sequence、map instance |
| 视觉进程崩溃 | supervisor 重启视觉进程，控制进程继续预测并降低输出 |
| 控制进程崩溃 | UI 收到进程退出，释放 Host lease，禁止自动发送旧命令 |
| Host session 失效 | heartbeat 独立，rearm 有退避，输出和地图恢复解耦 |
| 局部匹配误吸收 | 使用 score、创新距离、双人几何和连续帧确认 |
| 预测长期漂移 | 时间/距离/不确定度上限，超限进入局部或内存恢复 |
| 调试困难 | 每条消息记录 generation、sequence、时间戳、source 和阶段耗时 |

## 12. 最终验收标准

- P2 视觉丢失后仍持续移动，但不会无限期相信命令预测。
- 下一帧局部 ROI 能优先纠偏，不等待撞墙事件。
- 局部纠偏成功不会触发内存或全局定位。
- 内存快速重锚只在低频异常条件下触发。
- 全局恢复异步执行，不阻塞控制输出。
- P1/P2 位置、相对距离和身份不会因为单帧颜色干扰交换。
- 动态跟随只有用户手动停止才释放 session。
- UI 不执行截图、识别、路径和内存读取。
- 旧 live recovery 入口调用次数为 0。
- 离线回放、进程生命周期、性能和实机分级测试全部通过。
