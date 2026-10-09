# PoE2 双人跟随时序与性能审查草稿（2026-10-09）

这份草稿只记录从源码推导出的时序和预算，真实游戏输入、Host 消费和实际角色位移仍未在本轮验证。

## 进程和所有权

```text
Vision process
  capture -> PNG encode -> wall/marker/association -> VisualObservation
       │ latest-only observation event
       ▼
Parent poll relay -> Control visual queue
       ▼
Control process
  apply_visual -> accepted fusion -> source target update
  tick -> odometry -> recovery policy -> route -> OutputIntent
       │ latest-only FusionSnapshot
       ▼
Parent/UI poll
  output actor -> Host adapter -> ExecutionReceipt -> Control priority queue
```

正式动态跟随的目标所有权在 Control process。父侧仍然可以保存 target cache 和显示诊断，但不会把同一条 source observation 再写入 target queue。这样 P1 的 accepted native 位置和 P2 的 target 在同一个 Control tick 内产生。

## 周期和量化边界

| 环节 | 当前周期/阈值 | 处理规则 |
| --- | --- | --- |
| Vision capture | `max(16, round(1000/localization_fps))`，30 FPS 时约 33ms | start-to-start；处理耗时已包含在周期内 |
| Control tick | 与 Vision 使用相同 `interval_ms` | start-to-start；不再在 tick 后额外等待完整 interval |
| UI poll | 与 localization FPS 同步，30 FPS 时约 33ms | 转发visual/snapshot/receipt；消除的是snapshot再回写target的环，不是全部parent relay |
| visual freshness | `RecoveryPolicy.visual_degraded_ms=600ms` | 超过后进入预测/恢复判定，仍保持 session |
| local ROI | 新帧失配立即优先；80/140/220 半径 | 每tick最多一个role；图像必须对应该observation的transform；slot覆盖时跳过该次搜索 |
| memory reanchor | `1500ms`、连续 miss `3` 或 uncertainty `50`，cooldown 默认 `8000ms` | single-flight，异步 submit/poll |
| global reanchor | `3000ms` 或 uncertainty `100`等策略条件 | 通用backend能力；当前concrete factory未装配，pending不能当成已启动任务 |
| route replan | target 变化 `16`、位置推进 `12` 或走廊偏离 `12` | 每 tick 最多一个 MapAware controller 允许 A*；其它 role 使用缓存/直线 fallback |
| output arm gate | concrete page 默认 `6000ms` | gate 期间只建立 neutral lease，不积分 odometry |
| output actor watchdog | `1.5s` I/O 超时 | 只调用 adapter cancellation，不释放 follow session |
| worker watchdog | 启动 `10s`、运行 `2s` 无 progress | 有 rebuild factory 时退避重建；不是业务停止条件 |

## 关键延迟推导

### P1 位置到 P2 target

1. Vision worker 完成一帧，发送 `VisualObservation(sequence, captured_at_ms, roles)`。
2. Control worker 收到 visual envelope，在 `apply_visual()` 中先做 `SequenceGate`，再做 fusion。
3. source role 被接受时，立即把融合后的 native point 写到 follower `_RoleControl.target`。
4. 当前 tick 的 `route_controller.plan()` 直接使用新 target，输出下一脉冲。

因此移除了旧snapshot回写target的反馈环；Vision事件、Control快照和receipt仍经parent poll转发，UI阻塞仍会延迟这些通道。不能把目标下沉等同于Control直接读取Vision事件队列。

### 视觉短失配

1. accepted anchor 保留不变，拒绝候选不刷新速度或 evidence。
2. 新帧只为一个 role 执行 local ROI；未轮到的 role 使用 command odometry + 上一次输出继续运行。
3. local 失败后策略进入 prediction；达到 memory/global 阈值才异步提交低频恢复。
4. 任一恢复结果只更新返回位置对应的 role；空或不完整结果记录失败并退避。

## 本轮识别出的性能回归差异

旧链路在页面内同步完成“视觉位置 → 目标 → tick”，而重构后的早期版本把 target relay 放在 UI poll，导致双进程存在但目标传播仍依赖 UI。另一个退化点是双角色失配时在一个 Control tick 串行跑两个 ROI，A* 也可能在每个 role 上同步重规划。当前修复下沉 target ownership，并加入恢复轮转和单 tick A* budget。

## Transform handover（2026-10-09 收口）

每个 `VisualObservation` 现在携带生成该帧的当前相似变换。`FollowEnginePort` 只保留同 generation/map 的最新 observation；worker rebuild 取该 DTO 的 transform 与最新 native snapshot，replacement Vision 和 Control 的 local ROI 使用同一份变换，并根据 native seed 重新反算 screen anchor。这样 rebuild 不会把地图滚动后的坐标重新套回首帧 transform。

## 未验证边界

- `ExecutionReceipt` 只表示 Host/adapter 接受了脉冲，不代表 PoE2 已消费输入或人物已移动。
- 单次 ROI 或 A* 若自身超过 33ms，仍会使该 tick 变慢；现在只限制双人串行叠加，必须用 `StageTiming.local_ms/route_ms/total_ms` 的实机日志继续测量。
- Windows spawn、共享帧环、Host lease 和真实游戏窗口焦点需要用户授权后的短距离实测确认。
- 地图滚动期间触发 worker rebuild 后的真实 P2 连续性仍需实机确认；离线 handover 回归只证明 DTO、代际和坐标变换的一致性。

续读验证：正常运行ROI逐帧transform、exact frame绑定和恢复source目标传播已修复；直接相关35项检查通过。详细策略先后顺序、当前capture_ms/fusion_ms字段含义与历史实测边界，见最终审查文档对应章节，不把33ms配置写成实测耗时。
