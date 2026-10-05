# 通用局部接触与脱困实现计划

## Goal

修复人物通过障碍后仍被旧墙体证据判定为撞墙的问题，并将局部接触、可行方向和脱困恢复拆成通用能力。

## Architecture Overview

- PoE2 小地图适配器输出原始射线诊断、中心线阻断和局部方向可行性。
- `core.routing.contact_evidence` 只接收命令、位移、路线进展和阻断语义，维护接触状态与清除条件。
- 跟随 runtime 只在“确认接触且没有可行方向”时进入恢复；发现有效位移或新出口立即清除旧证据。
- 不使用人物膨胀作为硬碰撞约束；墙体距离只作为软代价。

## Tech Stack

Python 3.11、NumPy、OpenCV、pytest、Qt 页面适配器。

### Task 1: 为局部观测增加阻断语义

Files:

- `tests/test_poe2_minimap_contact.py`
- `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_localization/minimap_contact_adapter.py`

先增加测试：模拟 3×3 射线碰到侧边墙、中心线仍为空的场景，要求原始 `wall_ahead=True` 但 `blocking_wall_ahead=False`；模拟中心线真正被墙体占用的场景，要求 `blocking_wall_ahead=True`。

实现 `centerline_wall_distance`、`blocking_wall_ahead`、`narrow_passage` 字段。中心线使用半径 0 的采样；原始 beam 结果保留用于日志，运行时不再把原始 beam 命中直接当成碰撞。

Verify:

`pytest -q tests/test_poe2_minimap_contact.py`

Expected: 原有测试和新增侧墙/中心线测试全部通过。

### Task 2: 为通用接触证据增加状态与脱离条件

Files:

- `tests/test_contact_evidence.py`
- `src/auto_modules/core/routing/contact_evidence.py`

先增加失败测试：人物在两帧无进展后产生有效侧向位移时，接触累计清零；局部有阻断但存在可行出口时不能形成恢复证据；命令为零时不能累计接触。

实现 `ContactState` 和 `ContactMonitor.observe(..., blocking_obstacle_ahead, escape_available, route_progress)`。命令足够大、方向位移不足且连续达到阈值时进入恢复；`escape_available` 保留恢复证据但阻止升级为全局重定位。任何有效位移或路线进展都将状态恢复为 `ESCAPED/CLEAR`。

Verify:

`pytest -q tests/test_contact_evidence.py`

Expected: 原有接触监控测试和新增脱离测试通过。

### Task 3: 让跟随 runtime 使用阻断语义并清除旧证据

Files:

- `tests/poe2_live_terrain/test_multiplayer_follow_runtime.py`
- `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_follow/runtime.py`

先增加回归测试：runtime 在局部射线命中但中心线可通行时继续输出向量；runtime 在恢复后收到有效位移时不再返回 `contact_relocalization_required`；只有没有任何候选方向且持续无进展时才进入恢复。

把 `update_local_contact` 扩展为接收 `blocking_wall_ahead`、`escape_available` 和诊断字段；在 `_tick_follower` 中将接触恢复条件限定为阻断语义，有出口时继续局部脱困、没有出口且多次失败才重定位；在 `update_follower_position` 观察到有效位移或目标距离减少时重置旧的接触证据。恢复阶段仍使用现有局部方向候选，不发送零向量作为第一步恢复动作。

Verify:

`pytest -q tests/poe2_live_terrain/test_multiplayer_follow_runtime.py`

Expected: 新旧 runtime 测试全部通过，窄通道回归不再停止。

### Task 4: 更新 PoE2 适配器日志、断点文档和完整验证

Files:

- `src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py`
- `docs/POE2_LIVE_TERRAIN_CURRENT_STATE.md`
- `ITERATION_LOG.md`

页面调用 runtime 时传入阻断语义而非原始射线语义；日志增加原始射线、中心线阻断、窄道标记、候选方向数量、位移投影、接触状态和恢复原因。断点文档记录根因、状态机和验证结果。

Verify:

`pytest -q tests/test_poe2_minimap_contact.py tests/test_contact_evidence.py tests/poe2_live_terrain/test_multiplayer_follow_runtime.py`

Then run `python -m compileall src tests` and `git diff --check`.

Commit checkpoints are created only if the worktree is otherwise clean; existing user changes are preserved and not reset.
