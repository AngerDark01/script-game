# PoE2 实验跟随稳定性改造计划

## Goal

在 PoE2 实验运行时中，将人物关联、目标坐标投影、虚拟手柄会话恢复和视觉处理背压拆成独立能力，消除“候选存在却误判丢失”“目标落入墙栅格”“手柄 session 失效后停止”和处理积压导致的时序漂移。

## Architecture Overview

- `MarkerAssociationModel`：无 Qt、无游戏副作用；按时间间隔、速度、墙体位移和不确定度生成动态门限，完成单人/双人候选关联。
- `WalkableTargetProjector`：无副作用；把落在墙栅格但邻域可达的目标投影到最近可行走点，并输出量化诊断。
- `ProgramFollowOutput`：只负责输出租约；检测 session 失效后重新 arm 一次并重发最近方向，不触发地图恢复。
- `DualMotionWorker`：保持最新帧优先，丢弃过期排队帧；记录处理耗时和丢帧原因。
- 页面继续作为 composition façade，统一使用上述模块；不复制第二套寻路或恢复逻辑。

## Implementation Tasks

1. 关联模型：先添加无 Qt 的动态 gate/相对几何纯测试，再接入 `dual_motion.py`。
2. 目标投影：先添加墙栅格邻域投影纯测试，再接入 `runtime.py` 的规划入口。
3. 输出会话：先用 fake output 覆盖 session-expired 重启和单次重试，再接入 `ProgramFollowOutput`。
4. 最新帧背压：先覆盖 worker 忙时只消费最新帧，再调整 worker 队列和诊断字段。
5. 集成回归：运行多玩家定位、跟随、页面生命周期测试，编译和 diff 检查，最后进行人工调用链审查。

## Verification

- 聚焦：`pytest -q tests/poe2_live_terrain/test_multiplayer_motion.py tests/poe2_live_terrain/test_multiplayer_follow_runtime.py tests/test_poe2_capture_test_page.py`
- 完整 PoE2：`pytest -q tests/poe2_live_terrain`
- 静态：`python -m compileall -q src`、`git diff --check`
- 实机输入：本阶段只做离线/fake/回放验证；真实输入仍需用户单独授权。

## Risks

- 动态关联门限不能无限放宽；必须受地图实例、墙体质量和不确定度约束。
- 目标投影只允许局部邻域修正，不能把整张墙体变成可行走区域。
- session 重启只能重建输出租约，不得改变当前目标、地图变换或恢复状态。
