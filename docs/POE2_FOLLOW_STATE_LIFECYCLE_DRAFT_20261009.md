# PoE2 双人跟随状态与生命周期审查草稿（2026-10-09）

## 状态所有权

| 状态 | 唯一写入者 | 读取者 | 失效条件 |
| --- | --- | --- | --- |
| `VisualObservation` | Vision process | Control process、port diagnostics | generation/map/sequence 不匹配 |
| source/follower target | Control runtime（正式动态模式） | route controller、snapshot | accepted source visual/recovery、显式 target 更新 |
| predicted position | Control runtime 的 `CommandOdometry` | fusion、route、recovery policy | accepted visual/recovery anchor |
| output lease | OutputScheduler/ProgramGamepadOutput | output actor、diagnostics | 用户 stop、Host lease 失效后 rearm |
| session epoch | FollowEnginePort | rebuild/output guard | stop/start、新 generation |
| shared frame ring | FollowEngineComposition owner | Vision/Control worker | composition stop、代际替换 |
| latest visual handover DTO | FollowEnginePort（当前 generation/map） | composition rebuild | stop/start、代际或地图实例变化 |

## 正常启动

1. 页面确认 accepted 双人首帧、map instance、native seed 和 transform。
2. concrete composition 构造 shared ring、Vision processor、Control handle、MapAware route 和 Async output；此阶段不连接 Host。
3. `FollowEnginePort.start()` 按 `control → vision → output` 启动，记录每一阶段耗时；6 秒 arm gate 内 output actor 只建立 neutral lease。
4. Control runtime 用 seed 初始化两个 role；如果配置动态跟随，则把 leader seed 写入 follower target。
5. Vision图像写ring，observation事件经parent poll转到Control；accepted source位置同tick更新follower target。Control局部搜索绑定该帧transform，不混用更新图像和旧元数据。
6. Control 发布 snapshot，output actor 只消费 latest snapshot；成功 Host write 才生成 `ExecutionReceipt`。
7. 父侧下一次 poll 转发 receipt，Control 只对 accepted lease 的有效时间做 odometry 积分。

## 持续运行

```text
Visual frame
  ├─ accepted source -> same-tick follower target
  ├─ accepted follower -> own anchor/velocity calibration
  └─ missing/rejected -> prediction + at most one local ROI this tick
Control tick
  ├─ poll memory/global futures
  ├─ integrate execution receipt overlap
  ├─ recovery policy (keep session)
  ├─ route (one A* replan budget)
  └─ output intent (never business-stop)
Output actor
  ├─ latest-only apply
  ├─ heartbeat independent of control cadence
  └─ session rearm on transport failure
```

## 异常状态和转换

- `TRACKING`：source/follower 有 accepted visual，按正常路线输出。
- `VISUAL_DEGRADED`：frame age 超过 250ms 或出现 miss；继续预测和输出。
- `LOCAL_REANCHOR_PENDING`：新帧存在且当前 role 尚未尝试 local ROI；轮到该 role 时运行一次。
- `PREDICTING`：local 失败或暂时无可靠候选；command odometry 加不确定度继续输出。
- `MEMORY_REANCHOR_PENDING`：达到 1500ms/3 miss/50 uncertainty 且 cooldown 已到；异步读内存。
- `GLOBAL_REANCHOR_PENDING`：达到 3000ms/100 uncertainty、实例/transform 失效或 memory 失败退避条件；异步全局恢复。
- 上述global是通用策略能力：当前concrete factory未注入global backend，不能把pending状态视作任务已提交；精确分支优先级见最终审查文档。
- `FOLLOW_REARMING`：Host session 失效；OutputScheduler 独立重建 lease，Control session 保留。
- `FOLLOW_HOLD`：只表示当前 route 需要 neutral pulse 或等待恢复，不释放 session；动态跟随只有用户 stop 才结束。

## 生命周期竞态保护

`FollowEnginePort.stop()` 先递增 session epoch、设置 rebuild cancel，再停止 worker/output。后台 rebuild 只有 epoch/token 仍有效才 commit；迟到 bundle 直接 dispose。OutputScheduler 在 role I/O lock 内二次检查 epoch/stopping/port identity，阻止 stop 后幽灵 write/heartbeat/rearm。页面 lifecycle executor 的 stale completion 只能更新当前 serial 的 UI 状态。

worker rebuild 还从 port 保存的最新 `VisualObservation` 交接当前墙体校正 transform，并把最新 native seed 与该 transform 同时提供给 replacement Vision 和 local ROI；已有 native seed 时不复用旧 screen anchor。旧 observation 没有 transform 时回退 session seed transform。

正常运行同样通过 `EncodedMarkerRoiSearch.bind_observation` 同步每帧变换；ring已覆盖时只跳过该次ROI，保持session等待下一完整观测。local/memory/global accepted位置回填均调用 `_refresh_live_target`，确保leader恢复后follower目标同步变化；follower自身恢复不修改目标。

## 仍需用户实测观察

需要记录同一 generation 的 `first_vision_observation`、`first_control_snapshot`、`first_output_apply`、`ExecutionReceipt`、`program_output.state_heartbeat`、`worker_stall/rebuild` 和实际 P2 位移。任何一项 Host receipt 都不能单独证明游戏内角色已移动。
