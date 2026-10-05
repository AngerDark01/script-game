# PoE2 双人实时角色跟随实施计划

## Goal

在 PoE2 数据采集实验页完成 P1 手动/P2 程序跟随及反向模式，用最新双人视觉坐标作动态目标，并保留已验证的地图点击定点移动。

## Architecture Overview

遵循同日 `2026-10-03-poe2-live-role-follow-design.md`。页面把双人定位帧适配为带原始采集时间和角色身份的 `PositionSample`；实验运行器只规划，不输出设备输入；`ProgramFollowOutput` 仅绑定选中的程序角色。通用到达滞回放在跟随运行器，角色来源、模式选择与状态显示留在 PoE2 实验页。不得改定点移动的现有寻路参数。

## Tech Stack

Python 3、PySide6、NumPy、OpenCV、pytest；虚拟手柄经现有 `ProgramFollowOutput` 适配。使用 `D:/ACloud/.venv/Scripts/python.exe` 运行测试。当前工作树已有大量用户改动，执行时仅暂存本计划直接修改的文件，逐任务提交前核对暂存差异，不覆盖或清理其他改动。

## Task 1：接受真实角色目标样本

Files:
- `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_follow/runtime.py`
- `tests/poe2_live_terrain/test_multiplayer_follow_runtime.py`

先加失败测试，覆盖目标身份、地图实例、时间戳和旧样本拒绝：

```python
def test_live_target_keeps_observed_role_and_capture_time():
    runtime, map_identity = _runtime()
    leader = RoleId("local-device", "p1")
    sample = PositionSample(leader, map_identity, (20.0, 30.0), 1000, 1.0, "visual")
    assert runtime.set_target_sample(sample) == sample
    assert runtime.remote.position == sample
    assert runtime.set_target_sample(PositionSample(leader, map_identity, (99.0, 99.0), 999, 1.0, "visual")) is None
    assert runtime.remote.position == sample
```

再在 `SimulatedFollowRuntime` 中加入与静态点击 API 并列的入口（按现有 `_runtime` 测试 fixture 调整构造返回值）：

```python
def set_target_sample(self, sample: PositionSample) -> PositionSample | None:
    if sample.map_identity != self.map_identity:
        raise ValueError("target map identity does not match runtime")
    previous = self.remote.position
    if previous is not None and sample.captured_at_ms <= previous.captured_at_ms:
        return None
    self.remote.position = sample
    return sample
```

`set_simulated_target` / `refresh_simulated_target` 不改变。另测跨地图抛 `ValueError`、旧帧不续期、`FollowObservation.target` 为实际 leader 身份。

Verify: `D:/ACloud/.venv/Scripts/python.exe -m pytest -q tests/poe2_live_terrain/test_multiplayer_follow_runtime.py -k live_target`。预期先失败（缺少 API），再通过。

## Task 2：跟随距离滞回

Files:
- `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_follow/runtime.py`
- `tests/poe2_live_terrain/test_multiplayer_follow_runtime.py`

先测距离 11 → 15 → 21 时状态为 `ARRIVED`、`ARRIVED`、可重新规划；现有定点运行器未传恢复半径时保持旧行为。最小实现：

```python
# _Follower 新字段
arrival_hold: bool = False

# SimulatedFollowRuntime.__init__ 新参数，默认 None 保持旧调用行为
resume_radius: float | None = None
self.resume_radius = float(arrival_radius if resume_radius is None else resume_radius)
if self.resume_radius < self.arrival_radius:
    raise ValueError("resume_radius must be at least arrival_radius")

# _tick_follower 的位置/目标/地图时效校验之后、规划之前
if follower.arrival_hold and distance < self.resume_radius:
    follower.state = FollowState.ARRIVED
    return self._observation(follower, target, distance=distance, reason="within_resume_radius")
follower.arrival_hold = False
if distance <= self.arrival_radius:
    follower.arrival_hold = True
    follower.route = ()
    follower.planned_target = None
    follower.state = FollowState.ARRIVED
    self._clear_failed_plan(follower)
    return self._observation(follower, target, distance=distance, reason="within_arrival_radius")
```

`set_mode(..., MANUAL)` 清除 `arrival_hold`。失效位置仍必须先走时效检查，不能因保持状态绕过安全门。角色跟随实例用 12/20；`_make_follow_runtime` 的默认 8 保持不变，可为角色模式增加可选参数。

Verify: `D:/ACloud/.venv/Scripts/python.exe -m pytest -q tests/poe2_live_terrain/test_multiplayer_follow_runtime.py -k 'arrival or resume_radius'`。预期新增测试先失败再通过，旧 arrival 测试通过。

## Task 3：实验页双向角色模式与独立输出绑定

Files:
- `src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py`
- `tests/test_poe2_capture_test_page.py`

先测 P1 手动/P2 程序、P2 手动/P1 程序两种组合各只调用一次对应 controller factory，并要求不同且有效的两个角色。现有静态点击模式继续用原标识。UI 增加：

```python
self.follow_mode_combo.addItem("P1 手动 / P2 实时跟随", "p1_leads")
self.follow_mode_combo.addItem("P2 手动 / P1 实时跟随", "p2_leads")
```

`start_follow_experiment` 对两个新模式明确映射：

```python
live_mode = mode in {"p1_leads", "p2_leads"}
if live_mode:
    leader_identity = p1_identity if mode == "p1_leads" else p2_identity
    program_identity = p2_identity if mode == "p1_leads" else p1_identity
    selected = ((leader_identity, ControlMode.MANUAL), (program_identity, ControlMode.PROGRAM))
else:
    # 保留原有静态点击/模拟模式映射
    ...
```

只有 `program_identity` 对应的 controller 通过 `program_output_factory(1/2)` 创建输出。两个角色都加入运行器用于观测，但只把 `ControlMode.PROGRAM` 角色交给 `ProgramFollowOutput`。页面存储 leader/program role 与目标来源类型，停止时清空。启动前核对 `state.status == "tracking"`、无 recovery、同地图和帧年龄 ≤700 ms；尚未获得新目标时不发送手柄输入。

Verify: `D:/ACloud/.venv/Scripts/python.exe -m pytest -q tests/test_poe2_capture_test_page.py -k live_role_follow_start`。预期先失败再通过。

## Task 4：用新视觉帧发布目标，不伪造心跳

Files:
- `src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py`
- `tests/test_poe2_capture_test_page.py`

先测同一 `captured_at_ms` 的重复控制 tick 不更新目标时间，新帧即使位置不变也更新，leader 坐标跳变直接替换目标。只在 live mode 运行如下逻辑：

```python
captured_at_ms = self._latest_dual_captured_at_ms
leader_point = state.players.get(self._follow_leader_role.actor_id)
if captured_at_ms is not None and leader_point is not None:
    runtime.set_target_sample(PositionSample(
        self._follow_leader_role, runtime.map_identity, leader_point,
        int(captured_at_ms), 1.0, "visual",
    ))
```

程序角色位置也用相同的真实 `captured_at_ms` 更新。live mode 不调用 `refresh_simulated_target()`；旧点击模式继续调用它。live mode 启动后启动 100 ms 控制 timer，地图点击不得覆盖 live target。日志至少含 leader/follower role、目标坐标、`captured_at_ms`、年龄、距离、状态和路线重规划原因。

Verify: `D:/ACloud/.venv/Scripts/python.exe -m pytest -q tests/test_poe2_capture_test_page.py -k live_role_follow_target`。预期先失败再通过。

## Task 5：输出只处理程序角色且可重新接管

Files:
- `src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py`
- `tests/test_poe2_capture_test_page.py`

先测手动角色永不传给 `ProgramFollowOutput.apply`；跟随者到达释放，leader 离开恢复半径后重新 `arm`；停止、过期、地图变化立即释放。替换 `_tick_follow_experiment` 的输出遍历：

```python
for role in self._follow_program_roles:
    observation = observations[role.key]
    if observation.state is FollowState.PROGRAM_READY and not output.is_armed(role):
        output.arm(role)
    output.apply(observation, elapsed_ms=self._follow_timer.interval())
    self._update_follow_local_contact(
        runtime, state, role, observation, log_step="live_role_follow",
        emit_log=self._follow_tick_count == 1 or self._follow_tick_count % 5 == 0,
    )
```

加与 `_tick_dual_target_experiment_impl` 相同的定位状态、地图实例、帧年龄检查，并给 timer 回调加异常捕获；任何异常调用 `stop_follow_experiment()` 释放。每次处理 `relocalization_requested` 时先 `release_all()`，不能继续写摇杆。失效后须等真正的新可信帧，不能用 tick 时间重建目标。

Verify: `D:/ACloud/.venv/Scripts/python.exe -m pytest -q tests/test_poe2_capture_test_page.py -k 'live_role_follow_output or live_role_follow_stale'`。预期先失败再通过。

## Task 6：重定位恢复与坐标可视化

Files:
- `src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py`
- `tests/test_poe2_capture_test_page.py`

先测恢复时不回放旧地图点击目标；同地图实例出现新双人可信帧后恢复角色跟随；实例变化则保持停止。live mode 保存 `(mode, p1, p2, instance_id)`，不保存过期 leader 坐标；旧点击模式继续保存 click source。恢复时选回角色，重建运行器后由新帧填目标。显示目标使用 `runtime.remote.position` 的 native→display 变换；live mode 不使用 `_clicked_target_display` 覆盖它。状态文案明确“追赶/保持/等待新帧/重定位”，日志记录恢复前后实例与角色。

Verify: `D:/ACloud/.venv/Scripts/python.exe -m pytest -q tests/test_poe2_capture_test_page.py -k 'live_role_follow_recovery or live_role_follow_overlay'`。预期先失败再通过。

## Task 7：回归与文档同步

Files:
- `docs/POE2_LIVE_TERRAIN_CURRENT_STATE.md`
- `CODEBASE.md`
- `ITERATION_LOG.md`
- `ARCHITECTURE_ITERATION_LOG.md`（仅当现有架构记录契约受影响）

先核对已有双人同目标成功基线及静态点击实验测试；然后运行：

```powershell
& D:/ACloud/.venv/Scripts/python.exe -m pytest -q tests/poe2_live_terrain/test_multiplayer_follow_runtime.py tests/test_poe2_capture_test_page.py tests/poe2_live_terrain/test_motion_loop_replay.py
& D:/ACloud/.venv/Scripts/python.exe -m compileall -q src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_follow src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py
git diff --check
```

预期全部退出码 0；若离线样本或硬件条件不足，应写明未验证项，不把自动化测试称为实机通过。按 `codebase-ontology` 的 SYNC 顺序更新现有架构文档和断点，记录手动/程序角色边界、样本 TTL 与恢复链路。提交时仅暂存本计划涉及的源文件、测试与文档，并再次检查暂存差异；不得包含用户已有的其他未提交改动。

## 实机验收顺序

用户在游戏窗口启动双人定位 → 选择 P1 手动/P2 跟随 → 启动实验 → P1 走开、停下、位移、再走开 → 确认 P2 追近后中性、远离后再追 → 停止 → 反向重复。实机输出仅由用户在页面明确启动后发生；计划编写与自动测试阶段不发送真实输入。
