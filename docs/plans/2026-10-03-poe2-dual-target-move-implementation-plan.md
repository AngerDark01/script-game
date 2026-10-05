# PoE2 双人同目标移动实验实施计划

## Goal
在 PoE2 数据采集测试页提供独立的双人同目标真实手柄移动实验，保持已有跟随和单人探针行为不变。

## Architecture Overview
场景编排留在实验页；定位、坐标变换、规划、恢复及手柄输出复用已有模块。新会话使用独立状态、计时器和输出对象。地图点击统一转换一次，再按当前活动场景分发。

## Tech Stack
Python 3、PySide6、NumPy、pytest；现有 PoE2 双人视觉定位、`SimulatedFollowRuntime` 和 `ProgramFollowOutput`。

### Task 1: 待命与互斥

Files: `tests/test_poe2_capture_test_page.py`, `src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py`.

先加失败测试：双人定位与两个身份有效时，点击新“开始”按钮仅创建待命会话；假输出对象未 `start/write`；启动已有跟随或单人探针时先停止新会话并关闭两个输出。再增加独立按钮、状态字段、timer 和互斥入口。状态断言示例：

```python
page.start_dual_target_experiment()
assert page._dual_target_runtime is not None
assert page._dual_target_timer.isActive() is False
assert all(output.calls == [] for output in outputs.values())
```

Verify: `D:/ACloud/.venv/Scripts/python.exe -m pytest tests/test_poe2_capture_test_page.py -k dual_target -q`，实现前新增测试应失败；实现后通过。

### Task 2: 点击与双输出

Files: `tests/test_poe2_capture_test_page.py`, `src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py`.

先加失败测试：点击一次共享地图目标后两个 fake controller 分别 `start/write`，目标 native 坐标相同而两条路线各自起于角色位置；再次点击两人目标一起更新。实现点击场景分发及按角色的 tick。关键调用契约：

```python
runtime.set_simulated_target(native_point, now_ms=now_ms)
for role in program_roles:
    if not output.is_armed(role):
        output.arm(role)
for observation in runtime.tick(now_ms=now_ms).values():
    output.apply(observation, elapsed_ms=timer.interval())
```

Verify: 同 Task 1；两个 fake 输出各有写入，新点击后两人的观察目标均为新 native 坐标。

### Task 3: 独立释放、恢复与展示

Files: `tests/test_poe2_capture_test_page.py`, `src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py`.

先加失败测试：P1 到达或位置过期时只释放 P1，P2 继续；整体定位失效、手柄异常、停止或关闭时释放全部；重定位时保留点击目标但不输出，可信同实例双人位置恢复后重新规划。实现独立状态标签、两条路线 overlay、限流的双角色 tick 诊断与恢复生命周期。

```python
assert page._dual_target_observations[p1.key].state is FollowState.ARRIVED
assert outputs[1].calls[-1] == "stop"
assert outputs[2].calls[-1] != "stop"
page.stop_dual_target_experiment()
assert outputs[2].calls[-1] == "stop"
```

Verify: 同 Task 1；`D:/ACloud/.venv/Scripts/python.exe -m pytest tests/poe2_live_terrain/test_multiplayer_follow_runtime.py -q`。

### Task 4: 全链路回归与文档同步

Files: `CODEBASE.md`, `ITERATION_LOG.md`, `docs/POE2_LIVE_TERRAIN_CURRENT_STATE.md`.

核对 UI 点击 -> native 变换 -> 双角色视觉样本 -> 双路线 -> 双输出 -> 到达/异常释放的每一跳及侧栏可见性；按 codebase-ontology SYNC 规则更新架构与断点。

Verify: `D:/ACloud/.venv/Scripts/python.exe -m pytest tests/test_poe2_capture_test_page.py tests/poe2_live_terrain/test_multiplayer_follow_runtime.py -q`、`D:/ACloud/.venv/Scripts/python.exe -m compileall -q src/auto_modules/ui/modes/poe2_live_terrain`、`git diff --check`。测试不发送真实游戏输入。
