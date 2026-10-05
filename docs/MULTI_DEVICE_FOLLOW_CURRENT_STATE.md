# Multi-device Follow Current State

## Scope

This document defines the first implementation contract for generic multi-role
follow testing. It does not authorize real game input. The initial test layer
must support preview and simulated output before an explicit hardware-control
test is enabled.

## Fixed assumptions

- Every target and follower is identified by `(device_id, actor_id)`.
- All roles participating in one follow session must report the same
  `map_id` and `map_version` (the map instance identity). A mismatch pauses
  the affected task; it must not be silently transformed or followed.
- Shared positions are exchanged in the canonical map coordinate system. Map
  rotation and zoom are presentation-only and never enter the wire contract.
- A remote target does not need to be visible in the local minimap. The local
  device only needs a reliable position for each local follower and a fresh
  remote position message for the target.
- Manual control always wins for that actor. Acquiring manual control releases
  only that actor's program output; other actors continue independently.

## Test modes

### Go-to-target

1. The user clicks a point on the displayed canonical map.
2. The map widget emits the source-map coordinate, not a screen coordinate.
3. The session validates that the point is inside the current map and that the
   current instance is unchanged.
4. Each local actor is assigned one of `manual`, `preview`, `simulated`, or
   `program` control modes.
5. The planner creates an independent route from that actor's current position
   to the clicked target (or an arrival circle around it).
6. `manual` produces no program output. `preview` renders the route only.
   `simulated` advances a deterministic fake actor without touching a device.
   `program` is gated behind an explicit output lease and safety checks.

This covers both “program controls P1 and P2 to the clicked point” and “the
user controls P1 while the program drives P2 to the clicked point”.

For local development without a second device, the clicked point may be
published into the same position contract as a `simulated` remote role, for
example `(device_id="simulated-device", actor_id="remote-leader")`. This is a
test source only: it must not be confused with the local memory/vision
position, and it must not open a network session.

### Follow-role

1. A target role is selected by `(device_id, actor_id)`; it may be local or
   remote.
2. Each local follower independently subscribes to the target's latest valid
   position and plans toward a lag/arrival band rather than the target's exact
   current pixel.
3. P1 can remain manual while P2 is `program`; the target can be P1 or a role
   on another device.
4. If the target position expires, the follower stops and enters
   `waiting_target`; it must not continue on stale prediction.

In the no-second-device test, the user first clicks a map point to seed the
simulated remote role, then selects that role as the follow target. A later
click replaces the simulated target with a newer timestamp; optional playback
can turn a sequence of clicks into a deterministic target trajectory.

## Position contract

```text
RoleId       = { device_id: str, actor_id: str }
MapIdentity  = { map_id: str, map_version: str }
Position     = {
  role: RoleId,
  map: MapIdentity,
  x: float, y: float,
  captured_at_ms: int,
  confidence: float,
  source: "visual" | "memory" | "fused" | "simulated"
}
```

Freshness, confidence, and map identity are checked before a position becomes a
planner input. A position from another instance is rejected, not transformed.

## Control and safety state

Each local actor owns a separate state machine:

```text
IDLE
  -> PREVIEWING       target selected, route only
  -> SIMULATING       deterministic fake output
  -> ARMING_PROGRAM   explicit user action, lease not acquired yet
  -> PROGRAM          lease held and fresh local position
  -> ARRIVED          within arrival radius, neutral output
  -> WAITING_POSITION  local/target position stale
  -> BLOCKED           no safe route or no progress
  -> MANUAL           manual ownership; program output released
```

`PROGRAM`, `SIMULATING`, and `PREVIEWING` are actor-scoped. A P1 transition to
`MANUAL` cannot stop P2's task.

## Planning and correction

- Route planning uses the shared wall layer and the existing generic path
  planner. The goal is an arrival region, not an exact point:
  `distance(follower, goal) <= arrival_radius`.
- A target update or route deviation above threshold triggers a replan. The
  route is validated segment-by-segment against walls before it is accepted.
- A short control prediction may estimate
  `p_pred(t+dt) = p(t) + B * u(t) * dt`, but prediction is only a bridge
  between observations. Visual/memory position remains authoritative.
- If predicted and observed positions diverge beyond the configured correction
  gate, output becomes neutral, the route is cleared, and the actor returns to
  local-position validation before moving again.
- A moving target is sampled into a short trajectory buffer; followers pursue a
  lagged reachable target, not an unreachable historical position.

## UI test contract

The formal PoE2 page will expose:

- a map-click target marker;
- per-actor control mode selectors (`手动`, `预览`, `模拟`, `程序`);
- a target-role selector for follow-role mode;
- a simulated remote-role selector and map-click seed/update action for
  single-device testing;
- route preview, simulation start/stop, and a separately guarded program-arm
  action;
- per-actor status: position age, confidence, map identity, route state,
  distance to target, correction count, and stop reason.

The page must keep the existing live minimap and localization overlays. Route
and target overlays are presentation-only and use the same transform as player
positions.

## Implementation order

1. Extract generic role/map/position/task contracts and pure validation.
2. Add click-to-map-target conversion and route overlay without control output.
3. Add deterministic simulated followers for one and two local actors.
4. Add remote position subscription with instance/freshness fencing.
5. Connect per-actor program output leases, preserving manual ownership rules.
6. Run focused unit/integration tests; real controller tests remain opt-in.

## Open validation points

- Calibrate the map-coordinate unit to stick-speed response before enabling
  program mode.
- Confirm how a remote device publishes `map_id/map_version` for the same game
  instance and how reconnect/session changes fence stale positions.
- Validate temporary obstacles through no-progress detection before claiming
  complete obstacle perception.

## 2026-09-27 Experimental implementation checkpoint

Implemented in the PoE2 capture experiment only:

- `multiplayer_follow.models` and `runtime` hold role/map identity, freshness,
  independent actor modes, click-backed target heartbeats, deterministic
  simulation, and fail-closed map checks.
- Routes use the shared `wall_layer`, a small downsample fallback ladder, and
  segment-by-segment `corner_safe` validation before a vector is returned.
  Simulated steps are checked again before advancing, so the fake actor cannot
  cross a blocked cell.
- The capture page now exposes a follow experiment group. After dual visual
  localization is running, clicking the displayed (possibly rotated) map is
  inverse-transformed into canonical map coordinates. The target marker and
  per-actor routes are drawn through the generic `ScalableMapWidget` overlay.
  The two test modes are `P1 + P2 simulated` and `P1 manual / P2 simulated`.
- `ProgramFollowOutput` is an explicit adapter for a later hardware binding:
  it requires per-role arming and neutralizes/releases on stale, blocked,
  manual, map-mismatch, or arrived states. No real controller is connected
  by this experiment checkpoint.

Focused verification: `34 passed` for follow runtime, presenter inverse
mapping, capture page, and dual motion; `7 passed` for program-gamepad,
scalable-map, and follow-navigation regressions; compileall passed. The
remaining open validation is an opt-in real-device run after the user reviews
the click-to-target experiment.

## 2026-09-27 Review-fix checkpoint

- Follow experiment now requires explicit P1/P2 role-ID selection from live dual-localization identities. Both selections must be different and currently localized; capture/initialize clears old assignments. Dictionary insertion order no longer grants manual control.
- Initialize, map replacement, and reset stop both dual-localization and follow timers before clearing the map. A visual redraw only paints cached follow observations; the 100 ms follow timer is the sole simulation tick.
- Each follower caches an unreachable start/goal for a one-second cooldown. A start or target move beyond the arrival radius invalidates that cooldown immediately. This removes repeated full A* fallback searches on every unchanged frame.
- A cached path is invalid when its endpoint falls outside the new target arrival circle. If a smaller shift leaves the endpoint inside that circle but produces a zero vector short of the actual target, the runtime tries one exact-goal replan before entering BLOCKED; it never claims `route_ready` while stopped short.
- Regression coverage includes reversed identity order, absent/duplicate role selection, initialize while timers run, changed-map role reset, unreachable cooldown and retries, large and small target shifts at an old endpoint, and no double simulation tick. Related PoE2/UI/map/adapter suite: `321 passed`.
- **Not yet verified in-game:** actor-ID selection against the two visible characters, real movement over time, and first-attempt planning latency on a full native map. No controller or LAN output was enabled.

## 2026-09-28 Click-to-follow overlay checkpoint

- The follow experiment is armed after explicit P1/P2 selection, but remains idle with a visible “等待点击地图” prompt. The first valid map click starts the 100 ms simulation timer; each later click replaces the simulated remote target and recomputes the current observation. Invalid/out-of-map clicks do not start the timer.
- Solid player markers now always represent current dual visual-localization positions. Simulated follower predictions appear as separate dotted rings, so they cannot overwrite the game actors on the large map. Target and route still use the same canonical/display transform. Stopping the experiment restores the live localization markers and clears the simulated target/route.
- Regression: `326 passed` across PoE2 terrain, dual localization/follow, collection/formal pages, composition, and main-window integration. This was an isolated Qt/runtime test run, not a real in-game visual confirmation. No virtual controller, keyboard, mouse, or LAN output was sent.

## 2026-09-28 Dual realtime and program-output handoff checkpoint

### Verified fixes

- Starting dual realtime now reuses an accepted manual first-frame result. If
  tracker/reference construction fails, the accepted frame is preserved for a
  retry instead of being cleared and recaptured from a transient minimap
  frame. Explicit stop/reset still clears it.
- The follow page still waits for the first valid map click. The default modes
  are explicitly labelled as simulation and do not send a controller report;
  the single-P1, single-P2 and dual program modes are labelled as real-device
  control and arm only after the first target click.
- `ProgramGamepadOutput.start()` pauses the selected controller before asking
  the Host for a program lease, matching the Host contract. Program output
  failures are caught at the map-click boundary, shown in the page status and
  logged; every bound client is released and closed on stop.
- Program-controlled followers receive their current visual position on every
  follow tick, so arrival and blocked gates are evaluated against the actual
  actor instead of the initial seed; reaching the arrival band neutralizes and
  releases the program lease.
- A later click re-arms any role whose previous target ended in `ARRIVED` or
  `BLOCKED`, even when the follow timer is still active, so consecutive target
  clicks continue to drive the selected single or dual controller.
- Follow logs now record role arming and periodic state/vector observations,
  allowing a real test to distinguish route planning, lease acquisition and
  report delivery.

### Verification

- Focused Python regression: `15 passed` program adapter/runtime,
  `21 passed` capture page (including single-controller and dual-controller
  program output); compileall and diff check passed.
- VirtualGamepadHost C# contract regression: `57 passed` with the bundled
  .NET 8 SDK, including program lease/pause/release behavior.
- Full real Host probe was attempted without sending a controller state. The
  probe shell was non-elevated while the workbench/Host runs elevated, so it
  could not open the
  `\\.\\pipe\\AutoModules.VirtualGamepad.v1` pipe. This is an environment
  boundary, not evidence that the lease protocol is broken; real movement
  still needs one run from the elevated workbench with the virtual driver
  connected. The UI reports Host connection failures explicitly instead of
  silently doing nothing.

### Test sequence after Host is ready

1. Initialize and capture the current map.
2. Run `双人首帧实验` and confirm `accepted`.
3. Start `双人实时定位`; it must reuse the accepted frame and show
   `memory_reads=1` in the log.
4. Select explicit role IDs and choose `单人 P1 程序控制（真实手柄）`,
   `单人 P2 程序控制（真实手柄）`, or
   `P1 + P2 程序控制（真实手柄）`.
5. Click a nearby walkable point. The log must show `program_armed`, then a
   `PROGRAM_READY/route_ready` vector and Host `program.state` traffic.
6. Click another point to replace the target; arrival, blocked, stale or stop
   paths must send neutral output and `program.release`.

### 2026-09-28 真实手柄短脉冲探针边界

新增 `tools/debug/program_input_probe.py` 作为受控的真实 Host 输出探针。它
只对指定控制器执行一次 `pause -> program.acquire -> 120ms 左摇杆脉冲 ->
中性 -> program.release`，不经过键盘映射，不启用 LAN，也不持续控制人物。

本次在 Codex 非管理员终端实际运行控制器 1，连接阶段得到明确错误：
`WinError 5 拒绝访问`（无法打开 `\\.\pipe\AutoModules.VirtualGamepad.v1`）。
随后尝试从当前会话启动管理员子进程，但没有产生探针进程或新的日志记录，说明
当前会话不能代替用户完成 UAC 提权。因此本次**没有发送任何真实手柄状态**，也
不能宣称游戏内人物已经移动；这与 `program.acquire/state/release` 的 C# 合约
测试通过是两个不同层级的结论。

真实短脉冲必须在与工作台/Host 相同的管理员完整性级别下执行。请在管理员
PowerShell 或管理员工作台终端中运行：

```powershell
D:\ACloud\.venv\Scripts\python.exe D:\ACloud\auto_modules\tools\debug\program_input_probe.py 1
D:\ACloud\.venv\Scripts\python.exe D:\ACloud\auto_modules\tools\debug\program_input_probe.py 2
```

成功判据是 `data/logs/program_input_probe.jsonl` 依次包含
`connect.success`、`status.before`、`program.acquire.success`、
`program.state.direction`、`program.state.neutral`、`program.release.success`
和 `status.after`；若失败，必须以 `failed` 的具体 Host 错误为准，不能只依据
页面没有报错来判断输入已送达。

### 2026-09-28 双人首帧拒绝修复

实机页面样本 `P2_7:54BE4D92` 的失败日志确认：内存读取成功 1 次，识别到
两个 marker（例如 `(74,149)`、`(88,154)`），两种身份排列均进入双人近距离
中点几何路径；最佳排列的两个 anchor 平均误差约 `0.02`，但该页面实际使用了
通用 `AnchoredRegistrationConfig` 的 `minimum_forward_coverage_when_anchored=0.60`，
最佳墙体覆盖率约 `0.5175`，因此在注册阶段被拒绝。根因是 PoE2 双人入口没有
传入 PoE2 单人首帧已经校准的锚定策略，并非人物内存坐标读取失败。

新增 `build_poe2_dual_first_frame_registrar()`，正式双人组合和数据采集页统一
使用 `first_frame_anchored_coverage`（当前默认 `0.45`）及同一锚定评分策略；双人
专用配置仍明确保持 `player_clear_radius=0`、`top_exclusion_rows=0`，不会遮掉
两名人物周围墙体。相关回归为 `44 passed`，compileall 和 diff check 通过。

### 2026-09-28 程序移动实验的 Host 毫秒竞态修复

实机点击地图后，双人实时日志仍持续 `tracking / wall quality=1.00`；失败发生在
`ProgramGamepadOutput.start()` 的 `program.acquire`，Host 返回
`Start request is stale or predates a local stop`。根因是适配器先发送 `pause`，
Host 在当前毫秒记录本地 stop，随后立即用相同毫秒的 `requestedAtMs` 申请租约；
Host 的防重放条件按相等时间戳拒绝了这个实际上发生在 pause 响应之后的请求。失败
发生在 lease 建立前，因此当次没有发送摇杆状态。

现已在通用 `ProgramGamepadOutput` 中等待 Host 时钟严格进入 pause 之后的下一毫秒
再发送 `program.acquire`，并增加回归测试。程序移动实验仍沿用现有地图点击链路：
选择单人 P1/P2 程序控制，点击监控范围外附近的可行走点，先验证 lease、短 TTL
摇杆状态、中性和 release，再观察人物是否移动；默认模拟模式不发送真实输入。
## 2026-09-28 移动输出排查断点

当前实机跟随实验的定位和路线规划链路已经持续输出 `program_ready`，目标距离与方向也有值。通过读取 Host 诊断日志确认，程序输出并非停在规划层：

- `program.state` 产生后，Host 的 `ReportLoop` 持续提交非零轴值；
- `ViGEm SubmitReport controller=1` 连续出现，`backendConnected=True`；
- 因此当前“人物不移动”的故障点不在首帧定位、双人视觉跟踪或路线规划，也不在 Host 租约时间戳竞态。

仍需在页面上显式展示输出边界状态，并提供一个短时、固定方向的真实手柄移动实验，将以下链路单独验证：

`程序租约 -> program.state -> Host get_state/report -> ViGEm -> 游戏输入`

本断点的下一步：

1. 在 `ProgramGamepadOutput` 暴露只读诊断（控制器、租约、Host status/state），并在首次/周期性输出时记录；
2. PoE2 实验页增加独立地图点移动实验，确认后持续写入左摇杆，到达/阻塞/停止时自动中性和释放；
3. 将 PoE2 日志接入右侧栏，截图和大地图保持左侧空间；
4. 只有独立移动实验确认游戏实际移动后，才继续调整跟随方向、轴基和到点策略。

本轮已完成页面侧实现：

- `ProgramGamepadOutput.diagnostics()` 读取 Host `status/state`，不改变控制状态；
- 跟随每 10 个 tick 记录一次输出边界诊断，输出异常会停止并中性释放；
- PoE2 实验页新增独立“地图点移动实验（真实手柄）”：先选择角色和控制器，
  再点击大地图目标；用户确认后以 50ms 周期持续规划并写入摇杆，直到到达、
  阻塞、位置失效或用户停止，随后自动中性、释放并关闭客户端；
- 页面改为左侧截图/地图工作区 + 右侧最多 500 行会话日志栏，不再用日志挤压地图。

验证：Python 相关回归 `46 passed`，全量 `compileall` 和 `git diff --check` 通过；
Host C# 回归 `57 passed`。该移动实验与自动跟随完全分离，只有它在真实游戏中确认
能移动到地图点后，才把同一输出链路接回跟随。真实游戏测试仍必须由用户在管理员
工作台中点击目标并确认输入；当前普通终端因 Host 管道权限返回 WinError 5，不能
代替 UAC。

## 2026-09-29 实机移动与穿门断点

独立管理员 P1 探针在 10 秒切窗后，持续写入左摇杆 24 帧约 1.2 秒；同一地图实例人物从 `(529.50,1088.50)` 到 `(557.02,1055.46)`，约 43 native 网格。用户画面确认真实移动。这仅验证 Host→手柄→游戏的固定方向输入，不验证路线执行。

离线规划发现实验跟随把墙体 `255` 压成 `1`，与通用 A* 的 `>50` 墙体阈值不一致。现已保留 0/255，连同起点及终点连接段做原图碰撞复核；旧实例路线 26 节点、全部段安全。当前电脑重启后的存档仍是旧实例；管理员只读 UAC 取消，所以当前人物位置、当前地图实例、门后落点和地图→摇杆双轴关系尚未验证。**未发送本轮穿门输入，也不能宣称避障实机通过。**

恢复实机实验时，先刷新当前实例地图并核对视觉/内存位置，再做短时两轴标定与有界短程闭环，最后测试门后的安全落点；失焦、视觉帧过期、实例变化及超时都必须停止并中性释放。
