# PoE2 淘汰代码清理审计断点

## 范围与约束
- 2026-10-12：用户要求先完整识别、标记旧逻辑和兼容接口，不删除源码。范围为实验页面、双人定位、自动跟随及其组合入口。
- 禁止以 legacy 命名或文本命中作为删除依据。必须检查真实入口、回调、初始化、生命周期和模块依赖。
- 新架构复用的路径、避障、脉冲和手柄策略不因历史来源而删除；仍开放的实验功能不等于淘汰功能。
- 本次只写审计文档，不运行游戏输入、不启动 Host。

## 当前状态
- 已读取总断点和 ITERATION_LOG；已启用 codebase-ontology 技能进行分轮审计。
- 下一步：读取页面入口/组合根及 Control 路由适配器，再追踪旧页面 tick/recovery/probe/dual-motion 的可达性。
- 输出：删除候选清单、保留清单、需先解除依赖清单、逐文件覆盖和未确认边界。

## A1 发现
- 正式页面 composition 实际实例化 LegacyDynamicFollowRouteController，其 plan 调用 SimulatedFollowRuntime.tick；不能删除 multiplayer_follow/runtime 或旧算法 adapter。
- capture_test_page.start_follow_experiment 在 modular start 后 return，后面的完整旧启动分支为确定不可达代码；但旧 tick/恢复 helper 还从 timer、dual worker、地图点击和 shutdown 被引用，不能只删启动分支就认为边界已清理。
- dual_motion_mixin._start_dual_motion 仍是独立“双人实时定位”按钮的实现，并非全文件废弃。其同步 fallback 包含 recognizer 克隆失败后的真实运行路径，不是纯测试替身。
- 阅读进度：page 初始化及部分旧 tick 已读；dual_motion_mixin 输出有截断，标 partial，需补读缺段。Serena 已激活；initial_instructions 不在当前 active tools，已记录限制。
- 下一轮：补齐旧页面启动尾段、所有恢复方法与 close/suspend；检查 engine relay/fallback 是否仍有实际调用。

## A2 发现
- 已完整读取旧启动尾段、旧同步/内存/重试/全局恢复、suspend/shutdown 和 probe 中旧 follow 保存/恢复方法。旧 `_follow_runtime` 的正常创建只有 return 后启动块；但 timer else 和地图点击尾段仍挂旧 tick，属于需一起摘除的旧执行簇。
- `_maybe_resume_dual_follow_after_relocalization` 还调用当前 modular-only start 后检查 `_follow_runtime` 是否创建；这两个契约互相矛盾，证明历史恢复桥未完成迁移。正常新会话不该经此恢复桥。
- 页面无条件创建 `_live_memory_executor`、RecoveryCoordinator、GlobalReanchorBackend 和旧 follow 状态；新会话有自己 Control memory/local/global backend。shutdown 仍等待旧 memory executor，是实际生命周期负担，不是算法保留理由。
- 页面 adapter `_refresh_live_targets` 是旧 engine 不支持 configure_live_follow 时的 fallback；正式 engine 支持，因此该 fallback 正式链路被挡住。engine 还有 control_owns_live_targets=False 时的父端 relay，正式 composition 为 True；需分别标记，不能删整个 RelayLoop。
- 下一轮：审查无输出的 experimental/application、follow、probes scaffolding 和模块 re-export；追踪独立实验实际调用，完成清理依赖图。

## 当前淘汰候选分级（未删除）

### D0：确定不可达，可在测试迁移后删除
- `capture_test_page.py::Poe2CaptureTestPage.start_follow_experiment` 中模块化启动后的 `return` 之后至 `start_dual_target_experiment` 前的旧页面跟随启动分支。新入口无法到达该分支；现有旧测试仍 monkeypatch `_make_follow_runtime`，删除前需迁移或删除这些测试契约。

### D1：旧桥/重复所有权，需先收口后删除
- `probe_mixin.py::_maybe_resume_dual_follow_after_relocalization` 的 live 分支及其 `_dual_recovery_follow_*` 状态：它试图用旧页面 `_follow_runtime` 恢复模块化会话，和 modular-only 入口不一致；但 `dual_motion_mixin` 仍可调用它，不能直接删除。
- `capture_test_page.py` 中 `_live_memory_executor`、`_request_live_follow_reanchor`、`_start_live_memory_reanchor`、`_poll_live_memory_reanchor`、`_live_global_reanchor`：正式模块化跟随由 FollowEngine composition 的 recovery backend 负责；这些仍被旧双人 worker/旧页面 tick 使用，应先解除旧 worker 对它们的引用。
- `capture_test_page.py` 中 `_follow_runtime`、`_follow_program_output`、`_follow_timer` 及旧 `_tick_follow_experiment_impl`：不是新 modular engine 的 owner，但仍服务旧点击跟随/测试入口和旧恢复路径；必须先完成按钮/测试迁移，再删除整簇，不能逐个删属性。

### K：必须保留（不是淘汰代码）
- `follow_engine/control/route_controller.py::LegacyDynamicFollowRouteController`：名称含 Legacy，但当前正式 composition 明确实例化它；它是共享路径、避障、脉冲和 arrival 策略的适配器，删除会改变运动策略。
- `follow_engine_page_composition.py` 中该 route adapter 的导入和构造：当前新 engine 仍依赖它。
- `experimental/probes/controllers.py` 的 MoveProbe/DualTargetProbe/FollowProbe：页面仍有地图移动、双人同目标和跟随按钮调用；它们只管理目标生命周期，不拥有旧运动算法。
- `dual_motion_mixin.py`：当前双人首帧/实时定位按钮仍调用；其中 worker capture/tracker 是过渡架构，但没有替代首帧与 UI 事件接线前不能删除。

### U：需要进一步确认
- `experimental/application/ExperimentRuntime` 与 `experimental/composition.Poe2ExperimentComposition`：被移动探针、双人目标和 follow probe 使用；需要按功能是否继续保留实验按钮决定，不能凭 `experimental` 删除。
- `follow_engine_page_adapter._refresh_live_targets`：正式 engine 的 `configure_live_follow` 会令其短路，但它仍是 adapter 的兼容协议；如果新 engine 接口强制存在，才可删除该 fallback 及对应测试。

## 删除前必须满足
1. 新 modular 页面完成双人首帧、实时帧、地图点击实验和手动停止的唯一入口；
2. `dual_motion_mixin` 不再承担 modular follow 的 capture/恢复所有权；
3. 迁移或删除引用旧 `_follow_runtime` 的测试；
4. 用 Serena 引用分析和 focused tests 确认 D0/D1 符号无生产调用；
5. 每批删除后更新 CODEBASE、ITERATION_LOG，并单独提交 git，保留可回退点。
