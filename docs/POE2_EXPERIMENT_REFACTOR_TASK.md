# PoE2 实验代码模块化重构总任务

## 任务目标

在不并入正式底层引擎、不改变已验证实验行为的前提下，将 PoE2 实验页从单体页面逐步重构为分层、可测试、可回放的实验运行时。最终完成 A0 到 C5，并保留每阶段可回滚的 Git 检查点。

## 不变约束

- 实验代码继续属于 PoE2 实验域；不直接覆盖 `core`、`application` 或正式 PoE2 运行时。
- UI 只负责交互、展示、信号连接和页面生命周期。
- 截图、内存、窗口、虚拟手柄等副作用集中在显式 adapter。
- 纯模型、策略和状态机不得导入 PySide、Windows API 或 Host。
- 单人跟随、双人跟随、点击移动和双人同目标必须共享同一移动底层，只替换目标源。
- 不发送真实游戏输入；真实输入测试必须由用户单独明确授权。
- 每个阶段都必须有聚焦测试、完整 PoE2 测试、`compileall`、`git diff --check` 和人工链路审查。

## 阶段状态

| 阶段 | 目标 | 状态 | 检查点 |
| --- | --- | --- | --- |
| A0 | 建立文档库、模块盘点、调用链和迁移映射 | 已完成 | `c2465c0` |
| A1 | 提取状态模型和配置模型 | 已完成 | `7cd0750` |
| A2 | 提取恢复、前台保护和重试调度 | 已完成 | `7cd0750` |
| A3 | 提取双人视觉 worker 和帧路由 | 已完成（首轮） | `6690a6e` |
| A4 | 提取跟随控制器和目标源 | 已完成（首轮） | `6690a6e` |
| A5 | 提取移动探针与双人同目标实验 | 已完成（首轮） | 待提交 |
| B1 | 统一实验生命周期和会话上下文 | 已完成（首轮） | `6690a6e` |
| B2 | 统一目标源、运动决策和输出边界 | 已完成 | 待提交 |
| B3 | 统一定位、局部跟踪和重定位接口 | 已完成（首轮） | `6690a6e` |
| B4 | 统一日志、快照和性能统计 | 已完成（首轮） | `6690a6e` |
| C1 | 移除页面内算法实现 | 已完成（首轮边界） | 待提交 |
| C2 | 建立 composition 和离线 replay | 已完成（首轮） | 待提交 |
| C3 | 让实验核心脱离 Qt 运行 | 已完成（首轮） | 待提交 |
| C4 | 完整人工链路审查、回归和实机边界审查 | 已完成 | 待提交 |
| C5 | 评估可迁移到正式底层的通用能力 | 已完成（仅评估） | 待提交 |

## 当前基线

- 重构前基线提交：`8002892`。
- 最近恢复修复提交：`a64b6f1`。
- 核心实验页面：`src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py`，约 6227 行。
- 当前验证基线：页面及跟随聚焦测试 `172 passed`；`tests/poe2_live_terrain` `396 passed`；编译和差异检查通过。
- 当前页面同时包含 UI、双人 worker、首帧定位、跟随、恢复、移动探针、多帧实验和日志。

## 2026-10-07 — 跟随稳定性方案收口（本轮）

- `(implemented)` 动态 marker 关联加入双角色 pair geometry 软评分：候选总成本同时考虑各角色预测距离和两角色间距误差；颜色仍为软提示，仍保留单角色/无颜色回退。诊断新增 `predicted_pair_distance`、`observed_pair_distance`、`pair_distance_error`、`pair_geometry_score`。
- `(implemented)` 目标投影不再只按最近 walkable cell 选择；在局部邻域内同时考虑目标距离、3×3 开放比例和局部 clearance，诊断明确区分 `target_walkable`、`target_projected`、`target_no_walkable_neighbor`。
- `(implemented)` `no_safe_route` / `no_safe_route_cooldown` / stalled probe 统一使用目标方向、左右前方、左右侧和后方六向短脉冲评分；评分包含目标接近量、可行走性、局部 clearance、自由空间提示和方向连续性，输出 `probe_candidates`、`selected_probe_score`、`selected_probe_angle`。
- `(verified)` 新增 pair association 和 target projection 回归；核心跟随/双人运动/关联/投影测试 `90 passed`，PoE2 专项 `431 passed`，页面专项单独运行 `105 passed`。页面专项全量组合仍有 4 个既有 Qt 时序波动用例，四个用例单独重跑 `4 passed`；未发现稳定回归。
- `(verified)` `python -m compileall -q src` 和 `git diff --check` 通过；未发送真实输入。
- `(reviewed)` 长时间 marker 丢失继续沿用大地图命令预测；marker-only recovery 由页面延后全局恢复并优先请求局部 matcher，地图/墙体失效才升级全局；输出 session 重建与视觉恢复边界保持分离。worker 仍是 latest-result 优先，并按处理 EMA 自适应节流。
- `(next)` 实机验证仍需用户明确启动测试；重点观察 pair geometry 诊断、目标投影状态、probe 候选评分、session rearm 和 dropped_results/processing_ema_ms。

## 2026-10-07 — 最终人工链路审查

初始化/首帧：地图实例和 accepted transform 建立后才创建 tracker；正常运动不读内存。\
worker/帧路由：采集线程 latest-only，UI 按 generation 取最新结果，处理 EMA 超周期时自适应降频，旧帧不参与关联。\
人物关联：候选提取 → 动态 gate → pair geometry/颜色软评分 → 单角色回退 → bounded observation；候选暂时失配不会直接释放跟随。\
预测/重锚：命令位移形成 prediction hint；marker-only 降级继续预测并优先局部 matcher，墙层/实例失效才进入全局 recovery；恢复 revision 有边沿去重。\
规划/输出：目标先做局部 walkable projection，再执行多尺度 A* 与 native 安全校验；规划失败、冷却、无进度统一发六向短探针，输出 session 失效只 rearm 当前租约。\
生命周期：显式停止、失焦、地图实例变化、页面关闭仍释放输入；到达是唯一正常完成边界，未设置地图级总时长停止。\

审查结论：本轮没有发现第二套寻路、重复全局恢复或“视觉一丢失就停止”的新分支；仍需真实 PoE2 环境验证输入消费和长时间帧率，离线链路已完成。

## 2026-10-07 — 最新实机测试异常审计（只读）

- `(confirmed)` 本次会话首帧和前段跟随正常：`01:27:19` 双人首帧 accepted，pair confidence `0.894`、anchor quality `~1.0`；前 120 帧两角色均 tracking，pair geometry score `1.0`。
- `(confirmed)` 前台切换造成短暂采集空窗：`01:27:31` 开始跟随后连续约 59 次 `dual_motion.capture_frame_ignored reason=poe2_not_foreground`，随后自动恢复 tracking；这是前台保护触发，不是定位算法失败。
- `(confirmed)` 最新证据 `occlusion_diagnostics/1791307748207.../evidence.json` 中两个颜色候选都存在且质量高，但 Dex 候选距离预测 `33.38px`、pair distance error `36.12px`，最终 Dex 连续 51 次 dropout、age `5639ms`、uncertainty `25.88`，说明仍有“候选存在但动态关联拒绝”的异常。对应 raw：`1791307748207.../raw.png`。
- `(confirmed)` 后续 `01:29:38–01:29:48` 中 StrDex marker 长时不可见，`recovery_required` 每帧重复输出但 `recovery=False`，uncertainty 从约 `134` 增至 `178` native px；页面以 `occlusion_held/no_recovery_evidence` 继续运行，没有重复全局重定位。这是状态诊断噪声和预测漂移风险，不是停机。
- `(confirmed)` 跟随角色在目标附近多次进入 `target_arrival_unconfirmed`/`waiting_position`：距离约 `4.36`，但 native start/target 栅格均显示 `wall=255/collision=255`，A* 四个尺度均 `no_path`，随后发出的六向 probe 候选全部 `walkable=false`。这说明局部 native 栅格与实际可行走区域仍存在偏移，虽然输出没有直接停止。
- `(confirmed)` 本次 worker 处理仍有 `38–75ms`，高于 `33ms` 目标周期，累计 `dropped_results=129`；会产生视觉延迟和关联误差，但 latest-only 已避免旧帧排队。
- `(not observed)` 本次 `01:27–01:29` 未发现新的 program session expired、异常堆栈或全局 recovery 启动；结束时 `worker_stop_deferred` 与页面隐藏一致，属于生命周期清理。
- `(scope)` 本轮只读日志、evidence.json 和 raw.png，未修改代码、未发送真实输入。下一步先讨论：动态关联是否允许 pair geometry 失配时保留单角色局部关联；目标栅格偏移是否需扩大投影邻域但保持小人物半径；以及 recovery_required 的重复日志降频。

## 2026-10-07 — 用户决策：暂时失配与采样性能方案讨论

- `(decision)` 用户确认：候选暂时失配需要继续运行；监控小地图存在干扰颜色，不能把单帧颜色结果当作绝对身份。
- `(finding)` 当前单帧采集链真实耗时 `38–75ms`，所以直接提高采样频率会让 worker 更频繁积压；必须先把人物识别和墙体处理拆成不同频率，并保持 latest-frame 优先。
- `(proposal)` 关联层采用“单角色保留 + 双人几何降级”：pair geometry 只做评分/置信度，不作为单帧硬拒绝；一名角色候选可靠时先接受，另一名沿最后可信位置和命令预测；连续 2/3 帧确认后再恢复完整双人关联。
- `(proposal)` 颜色干扰使用时间滞回、运动连续性、候选置信度和两角色相对几何综合评分；短暂冲突进入 `degraded`，不触发全局恢复。
- `(proposal)` 性能目标先设为人物候选处理稳定低于 `25–30ms`；墙体位移约 `10–15Hz`，marker 候选约 `25–30Hz`，局部重锚按需执行。
- `(decision_pending)` 是否将热路径迁移到 C/Cython 需先做分段 profiling。OpenCV 的 HSV/连通域本身已在 C++ 执行，优先优化 ROI、数组复制、重复预处理和日志序列化；只有确认 Python 循环是主要瓶颈时才迁移 Cython/C++ 扩展。

## 2026-10-07 — 用户批准 Git 检查点并开始优化

- `(decision)` 先提交当前已验证版本，再开始跟随稳定性和性能优化。
- `(boundary)` 检查点提交代码、测试和任务文档；运行时生成的日志、截图和 evidence 目录不纳入提交。
- `(next)` 优化顺序：统一动态关联与重新出现确认门 → 单角色保留/双人降级 → 重复 recovery 诊断降频 → 分段 profiling 后再决定是否迁移 Cython/C++。

## 2026-10-07 — 用户决策：暂时失配保留单角色、扩大目标投影、评估高频采样

- `(decision)` 双人暂时 pair geometry 失配时，允许已经通过位置/颜色/运动连续性验证的单角色继续关联；不因另一角色的 pair error 直接让整组 assignment 失败。
- `(decision)` 目标投影允许扩大局部邻域搜索范围，但不扩大人物半径、不膨胀墙体；仍需局部可达性和 clearance 评分，避免把真实墙体投影成目标。
- `(discussion)` 图色候选考虑提高采样频率，但前提是处理延迟低于采样间隔；本次日志的 `38–75ms` worker 耗时和 `33ms` 目标周期表明需要先拆分/优化识别链路，再提高采样频率。
- `(next)` 设计并验证“单角色保留 + pair 迟滞确认”“局部投影扩大但可达性约束”“最新帧高频采样与处理预算”三部分方案。
- 物理拆分后页面约 4687 行；定位、生命周期、探针、双人运动已迁移到独立 mixin，保留旧方法名作为兼容 façade。

## 当前断点（2026-10-06）

- 物理拆分后的首轮回归曾因 mixin 缺失 `QTimer`、`terrain_pixmap`、`prepare_localization_map` 导入失败，已补齐。
- `tests/test_poe2_capture_test_page.py` 当前 `89 passed`；下一步必须提交该拆分检查点，再开始 A5 的探针控制器接入。
- 未解决边界：探针页面仍直接拥有路径 runtime、窗口查询和 gamepad 输出；A5/B2 需要把这些调用通过显式 adapter/port 收口。

## 2026-10-06 — 全链路回归取证（当前断点）

- 聚焦运行结果：PoE2 页面/实验测试在并行或全量事件循环下出现时序性失败；恢复测试单独运行可通过，说明不是稳定的首帧匹配失败。
- 根因证据 1：`_maybe_resume_dual_follow_after_relocalization()` 在 `_sync_live_follow_from_fresh_frame()` 成功后只清理恢复状态，没有立即进入一次跟随 tick，因此 tracker 已恢复但 `ProgramFollowOutput` 仍未重新 `start/arm`。
- 根因证据 2：`_tick_follow_experiment_impl()` 的 `frame_is_stale` 分支在视觉帧超过 700ms 时直接 `release_all()` 并返回；这绕过了 `CommandRoleTracker` 的命令预测和 `SimulatedFollowRuntime` 的接触/无进度证据，造成视觉短暂延迟即停顿，再触发昂贵重定位。
- 根因证据 3：双人同目标入口和 tick 都要求 `_latest_dual_captured_at_ms` 新鲜；替换 `DualMotionState` 而不更新时间戳会被正确拒绝。调用边界应通过同一帧事件原子更新状态和时间戳，不能放宽 TTL 伪造新鲜帧。
- 影响链路：恢复→输出重新挂载、视觉丢帧→预测保持、双人目标帧新鲜度、页面 timer/worker 生命周期。
- 当前下一步：先补恢复后的单次受控 tick；再让视觉过期进入预测保持（恢复证据仍独立累计），增加回归测试；随后审查 `shutdown()` 对跟随 timer、recovery `singleShot` 和 retired worker 的清理。

## 2026-10-06 — 视觉间隙与恢复输出修复

- 修改 `capture_test_page.py`：视觉帧超过 700ms 时不再立即 `release_all()`/返回；将当前帧标记为 observation gap，按 `CommandRoleTracker` 的 `target_hold`/`command_prediction` 样本继续进入共享 runtime。累计达到视觉停滞阈值后仍只触发一次 recovery episode，避免无限重定位。
- 对 `captured_at_ms=None` 增加仅限本次 tick 的单调本地时间兜底；`frame_is_stale` 仍保持为真，不能绕过新鲜帧和冷启动门槛。
- 修改 `probe_mixin.py`：恢复同步成功后立即调用一次 `_tick_follow_experiment()`，让输出在恢复边界重新 arm/write，而不是等待下一个 Qt timer tick。
- 冷启动遇到“新鲜墙体帧但某个 marker 暂时缺失”时，若所有角色已有首帧 seed 且墙体可信，进入 `sync_degraded` 预测模式；缺失角色继续使用 bounded estimate，不再把完整双人 marker 同帧作为唯一启动条件。
- 页面生命周期：新增 `Poe2CaptureTestPage.suspend()`；宿主 `Poe2LiveTerrainPage.hideEvent()` 和延迟 shutdown 分支会释放实验副作用但保留页面可复用，终止关闭仍使用 `shutdown()`。
- 独立顶层页面的各类 Qt timer 通过回调保护：真实 timer 触发且页面无 parent、未显示时自动 `suspend()`；手动调用 tick 不受影响，避免实验 harness 的后台 timer 串扰其他页面。
- 回归测试更新为新契约：视觉间隙保持预测、不释放输出；缺失时间戳仍可继续预测；创新拒绝测试关闭启动 grace，避免把时序延迟误判成创新逻辑。
- 已验证：相关恢复、视觉丢帧、缺失时间戳、目标重置测试通过；继续运行全套 PoE2、虚拟手柄和全仓测试。
- A5 首轮：`MoveProbe`、`DualTargetProbe`、`FollowProbe` 已成为目标生命周期控制器；页面点击和启动/停止 façade 已接入，三种目标源仍共享原有运动 runtime。
- B2：新增 `experimental/adapters` 的 capture/memory/window/gamepad 端口和无副作用 fake；composition 接受 `AdapterBundle`，页面仍通过兼容 façade 装配。
- C2/C3 首轮：`ReplayManifest`、可索引 `ReplaySource` 和 `HeadlessExperiment` 已建立；生命周期、帧摄入、恢复和停止可在无 Qt 环境回放。
- C1 首轮边界：新增 `FollowController`，把目标刷新和 runtime tick 形成 Qt-free 契约；页面旧入口继续作为 façade，未复制第二套路径算法。

## 2026-10-06 — 04:25–04:30 跟随恢复链路复核（未修复）

- 对应日志：`data/logs/poe2_live_terrain.log` 的 `2026-10-04 03:04:10–03:04:40`。
- 首个持续故障：`frame=5943` 起 `reason=markers_missing`，随后转为 `wall_and_local_match_failed`；`DexFourb` 的 `identity_dropout_failures` 已超过 1500，画面 `quality` 多次为 `0.999–1.000`，所以不是整帧墙体质量坏掉。
- 页面证据：故障期间只有 `dual_motion.tick status=recovery_required recovery=False` 和 `live_role_follow.waiting`，没有 `dual_motion.recovery`、`recovery_claimed`、`dual_first_frame`、worker 结果或 fresh resume。
- 代码边界：`DualVisualTracker._failed()` 只在 `_recovery_emitted=False` 时把 `recovery_requested=True`；`Poe2DualMotionWorker._offer()` 仅把该边沿写入 pending revision；UI 的 `_drain_dual_motion_worker()` 只有收到 pending revision/`recovery_requested` 才调用恢复。持续的 `recovery_required` 状态本身不会再次触发恢复。
- 当前结论：已确认“角色身份长期丢失 + recovery_required 边沿没有形成可消费的 recovery 闭环”是本会话的根因候选；尚未修改代码。下一步对照成功 session 并添加最小回放测试，验证 pending revision、worker generation 和 tracker reset 顺序。
- 最小修复：页面按当前 tracker generation 保存 `_dual_last_handled_recovery_revision`；worker pending revision 和 `state.status == recovery_required` 的更高 revision 合并为一次恢复事件。新 tracker 启动时清零，重复状态不会重复重定位。
- 回归：新增“边沿字段被覆盖但持续 recovery_required 仍触发一次恢复”的页面测试；页面/PoE2 全部聚焦回归 `524 passed`，`compileall` 与 `git diff --check` 通过。待做：实机确认恢复后 fresh frame 是否继续跟随。

## C4 人工链路审查

```text
initialize_session/capture_map
  → 首帧 worker 读取地图与人物锚点
  → DualMotionController/router 按 generation 接受视觉帧
  → start_follow_experiment / start_dual_target_experiment
  → probe lifecycle arm + target source update
  → shared SimulatedFollowRuntime.tick
  → FollowObservation → ProgramFollowOutput / preview
  → stale/occlusion/contact evidence → RecoveryController episode
  → fresh frame/relocalization → runtime resume
  → explicit stop/shutdown → neutral + release + timer cleanup
```

人工逐步核对结果：初始化缺地图时不启动；旧 worker generation 被丢弃；目标点击先做 source→native round-trip 和边界校验；未 arm 探针不会接受目标；runtime 只在有效帧/恢复阶段 tick；恢复是非终止状态，成功 fresh frame 后重新进入 tracking；显式停止才释放输出和清理 timer。页面仍存在重型编排，这是 C1 后续拆分风险，但不产生第二套算法。

## C5 候选下沉评估（不执行迁移）

满足无 PoE2 术语、无 Qt/Win32、无真实副作用且已有独立测试的候选：`TargetSource`/`FollowController`、`RecoveryController` 的 episode/backoff、`PositionEstimate`、`ReplaySource`/`HeadlessExperiment`、`DiagnosticEvent`/`EventRecorder`。`DualMotionController`、地图变换、PoE2 movement basis、marker 颜色和页面 façade 暂不下沉。

## 文档补充断点（2026-10-06）

- 用户指出自动跟随文档缺少算法原理、公式以及“观测如何变成输出”的说明。
- 已在 `docs/POE2_AUTOFOLLOW_COMPLETE_LOGIC.md` 增加“10A. 算法原理详解：从观测到手柄输出”。
- 覆盖首帧相似变换、墙体位移、marker assignment、命令/视觉融合、A* 多尺度、局部控制评分、接触证据、到达与 TTL、恢复状态机、速度校准和参数耦合。
- 本轮仅修改文档，不修改运行代码、不发送真实输入。
- 已完成 `git diff --check`；文档内容和迭代记录一致。

## C4 补充审计结论（2026-10-06）

- 发现：恢复后的第一帧可能是墙体已可信、角色仍有 bounded estimate、但 marker 暂时缺失的 `degraded` 状态。原恢复入口只接受 `tracking`，会保留恢复上下文而不重建或重新挂载跟随。
- 修复：新增 `_recovery_frame_usable()` 作为恢复状态门槛；`tracking` 直接通过，`degraded` 只有在 `wall_trusted=True` 且所需角色均有位置估计时通过。跟随同步阶段将 `available=True` 的有界角色估计作为恢复锚点使用，继续沿用同一运动 runtime。
- 覆盖：单人/双人实时跟随的原地重锚与恢复重建各增加回归测试；没有放宽 `recovery_required`、地图实例或时间新鲜度校验。
- 追加：实时恢复的可消费帧门统一为 300ms；301–700ms 的帧只保留恢复上下文并等待下一帧，避免恢复入口与跟随启动入口门限不一致而丢失会话。
- 生命周期：跟随目标 probe 现在在 runtime、角色和输出全部构造成功后才 arm；无定位上下文的启动尝试不会留下 stale armed 状态。
- 当前风险：真实 PoE2 输入仍未在本轮自动发送；全仓测试的 `pydirectinput` distribution metadata 缺失和虚拟手柄 Qt 跨套件时序失败属于环境/隔离问题，需要单独处理。

## C4/C5 全链路回归收口（2026-10-06）

- 修复 `tests/test_poe2_capture_test_page.py` 中新增关闭生命周期测试的函数边界错误；监控窗口关闭断言归回原测试，日志 handler 测试只验证页面关闭后的 handler 脱离。
- 已验证 Qt logger 生命周期：`Poe2CaptureTestPage.closeEvent()` 调用 `shutdown()`，`_UiLogHandler.emit()` 和 `_append_session_log()` 在 Qt 对象销毁/无效时安全返回；后台 worker 迟到日志不会再写入已销毁的 `QPlainTextEdit`。
- 页面隐藏与进程关闭经过同一安全边界：`suspend()`/`shutdown()` 会停止 follow、dual-target、program-probe、视觉 worker 和 timer，释放程序输出；页面重新显示时只能从新的显式启动入口恢复。
- `shutdown()`、`suspend()`、监控窗口关闭、follow/dual-target/program-probe 停止、recovery singleShot 回调均经过回归；关闭后 timer 停止、Host output 释放、recovery callback 不会重启页面。
- 程序移动探针完全移除总时长限制；长路线持续到目标或显式操作/生命周期边界。视觉帧新鲜度与 Host command TTL 仍作为单次观测安全契约，视觉短暂过期使用命令预测保持，接触/失焦/显式停止仍保留安全释放边界。
- 双人同目标恢复复核：恢复帧门统一为 `_FOLLOW_RUNTIME_MAX_FRAME_AGE_MS`（700ms），启动失败会释放已创建 output、不会留下 armed probe；重复启动先清理旧 runtime/timer/output。
- 回归结果：`tests/test_poe2_capture_test_page.py` 为 `104 passed`（含 suspend/shutdown 生命周期）；`tests/poe2_live_terrain` 为 `422 passed`；目录外 PoE2 UI/worker/探针为 `167 passed`；`python -m compileall -q src` 和 `git diff --check` 通过。未发送真实游戏输入。
- 人工链路复核覆盖：初始化→地图/首帧→双人 worker→单人/双人跟随→双人同目标→点击移动→输出 arm/apply/release→stale/degraded/occlusion→局部接触恢复→全局重定位→fresh resume→hide/close/shutdown→日志 handler 脱离。当前未发现第二套寻路或恢复实现；剩余风险仅是未经本轮实机输入验收，以及全仓历史环境依赖失败。

## 地图完整运行契约补充（2026-10-06）

- 程序移动探针不再接受任何总运行时长配置；旧 `_program_probe_max_duration_ms` 即使被注入也不会截断地图运行。长路线持续到目标或显式操作/生命周期边界。
- 视觉帧龄、Host command TTL、恢复冷却和 worker join timeout 仍保留，它们分别保护单帧观测、单次输入租约、重定位频率和线程清理，不是地图总时长限制。
- 补齐 `probe_mixin.py` 的真实入口依赖导入，避免程序移动首次运行时因拆分后的隐式全局符号产生 `NameError`。
- 回归结果：capture page `105 passed`；`tests/poe2_live_terrain` `422 passed`；`compileall` 与 `git diff --check` 通过；长运行回归模拟 24 小时旧运行时间仍不停止。
- 模块级静态检查：`ruff check --select F821 src/auto_modules/ui/modes/poe2_live_terrain` 通过，补齐拆分 mixin 的真实入口依赖。

### 最终审计验证（2026-10-06）

- PoE2 页面与实验聚焦回归：`519 passed`。
- 虚拟手柄 UI 独立回归：`47 passed, 1 subtest passed`。
- 全仓 pytest：`1101 passed, 2 skipped, 2 failed`；一项是环境缺少 `pydirectinput` distribution metadata，另一项是虚拟手柄 Qt backoff 跨套件时序波动（单独重跑该用例通过），均未出现在 PoE2 专项或页面生命周期回归中。
- `python -m compileall -q src`、`git diff --check`：通过。

## 迁移原则

1. 先复制职责边界，不复制第二套业务逻辑。
2. 先抽取纯模型，再抽取控制器，最后移动副作用适配器。
3. 旧页面方法先变成薄包装，测试稳定后再删除内部实现。
4. 每次迁移保持同一输入、同一输出、同一状态转移。
5. 每完成一个阶段立即更新本文件、`ITERATION_LOG.md` 和阶段设计文档。
6. 上下文压缩后，第一步必须读取本文件和 `ITERATION_LOG.md` 最近条目。

## 模块目标结构

```text
src/auto_modules/features/poe2/live_terrain/experimental/
├── application/       # 实验生命周期、会话和事件
├── localization/      # 首帧、局部跟踪、重定位
├── motion/             # 运动决策、路径跟随、碰撞恢复
├── follow/             # 跟随控制器、目标源、观察融合
├── multiplayer/        # 双人角色和双人视觉会话
├── recovery/           # 恢复策略、退避、前台保护
├── probes/             # 点击移动、双人同目标、跟随探针
├── adapters/           # 实验截图、内存、窗口、手柄端口
├── diagnostics/        # 日志、快照、性能、回放记录
└── composition.py      # 实验对象装配
```

## 风险和回滚

- 风险：旧页面测试通过但实机状态顺序改变。措施：保留旧入口、事件日志和 session token，对关键状态做回放测试。
- 风险：控制器之间共享可变状态。措施：所有状态放在 session/context，控制器只通过端口读写。
- 风险：重构过程中产生新旧两套逻辑。措施：迁移后旧方法只调用新控制器，禁止复制算法。
- 风险：UI 线程执行重型任务。措施：worker 和 controller 通过事件传递，页面不执行全局匹配。
- 回滚：每个阶段单独提交；失败时回退到最近阶段提交，不回退用户数据和运行截图。

## 完成定义

只有以下条件全部满足，才标记 C5 完成：

- 页面代码约 500～800 行，职责仅为 UI 和装配。
- 实验核心可在无 Qt、无真实 PoE2、无真实手柄下离线运行。
- 单人/双人跟随和移动实验共享目标源、定位、运动、恢复和诊断接口。
- 所有真实副作用集中在 adapter。
- replay 能重现首帧、视觉丢失、重定位、卡墙和前台错误。
- 正式项目没有反向依赖实验模块。
- 完整测试、编译、差异检查和人工链路审查通过。
- 已记录可候选下沉到正式底层的通用能力，但本任务不执行下沉。

## 地图完整运行契约复核（2026-10-06）

- CodeGraph 与源码搜索复核确认：`_tick_program_move_probe()` 不读取任何总时长/最大时长配置；`_program_probe_started_at_ms` 只用于 `stop_summary` 诊断。
- 未发现第二个地图级 elapsed-time stop。10 秒等待仅发生在真实输入确认后等待用户切回 PoE2 的启动前阶段；视觉帧龄、Host command TTL、恢复冷却和 worker join timeout 仍是单次观测/资源安全边界。
- 回归结果：capture page `105 passed`；`tests/poe2_live_terrain` `422 passed`；`compileall`、`ruff F821`、`git diff --check` 通过。
- 结论：完整地图运行不会因总运行时间自动停止；实际停止仍只由到达/明确阻塞、前台失焦、地图或定位上下文失效、输出异常、用户操作及页面生命周期触发。

## 自动跟随说明与实现对照（2026-10-06）

- `docs/POE2_AUTOFOLLOW_COMPLETE_LOGIC.md` 已与当前实现重新对照。
- 修正了实时跟随和独立程序移动探针的终止语义：前者在恢复/视觉暂缺时保留会话，后者在明确的 `blocked`、`waiting_position`、`map_mismatch` 状态结束本次探针；两者都没有地图级总时长限制。
- 分开记录 6 秒跟随输出等待、10 秒程序探针前台确认和 10 秒全局恢复 cooldown，避免时间参数含义混淆。

## 文档能否暴露历史 bug：复核断点（2026-10-06）

- 用户问题：从自动跟随逻辑文档能否推断出之前修复的 bug。
- 当前动作：对照状态门、时间门、恢复事件与输出生命周期，区分文档可推导的矛盾、实现遗漏和未验证推测。
- 本轮只做证据审查和记录，不修改运行代码、不发送真实输入。

### 复核结论

- 可由文档直接推断的 bug 类别：恢复边沿丢失、恢复入口与启动入口的新鲜度门不一致、恢复后输出未重新 arm、短暂视觉丢失被错误当成终止、`degraded` 恢复帧被错误拒绝、校验失败后留下 stale probe。
- 只能提示、不能单凭文档定根因的类别：Qt worker 迟到回调导致页面对象失效、具体线程/GUI 崩溃点、mixin 隐式导入错误。
- 文档本身无法发现的实现事实：旧的 30 秒地图级硬停止，除非把“无总时长限制”的契约与源码审查结合起来。
- 总结：文档可以作为状态契约和调用边界的审查基线，但仍必须结合源码调用链、日志和离线回放完成根因确认。

### 本轮修正

- 文档已与当前代码重新对齐：`degraded` 恢复帧、预测 hint 门槛、8 秒视觉停滞恢复、实时会话与独立探针终止边界均已明确。
- 当前工作树未发现这些历史问题仍有未修复的运行时代码分支；后续若改变这些边界，必须先补回归测试再改文档。
## 22:50 后两次真实跟随会话异常审计（2026-10-06）

### 审计范围

- 日志范围：真实会话 `1a111b130f6-26a052afb30`（约 22:49:47 启动）和 `1a111b2dcd4-26a053bf500`（约 22:51:37 启动），重点分析 22:50:02–22:53:10。
- 过滤规则：22:53 之后出现的 `MapIdentity('Area')`、`role-a/role-b`、host failed 等为回归测试桩数据，未纳入实机结论。
- 共同上下文：地图实例 `P2_7:54BE4D92`，角色身份为 `Metadata/Characters/StrDex/StrDexFourb` 与 `Metadata/Characters/Dex/DexFourb`。

### 异常分类和结果

| 类别 | 证据 | 处理 | 耗时/结果 |
|---|---|---|---|
| 局部路线异常 | `blocked/no_safe_route_cooldown`、`no_safe_route`、`route_not_progressing`；距离约 27–73 native px | 局部路线冷却、重新评估；没有触发全局重定位 | 每次约 1.8–2.9 秒回到 `program_ready/route_ready` |
| 短视觉遮挡（会话 1） | 22:50:27 `markers_partial_grace`；P2 age 216 ms、uncertainty 1.472、P1 可见，`wall_trusted=true` | marker hold/预测提示，保持 tracking | 约 2.58 秒恢复，无全局重定位 |
| 长时间丢失（会话 1） | 22:50:49 `recovery_required/markers_missing`；P2 age 16,399 ms、uncertainty 74.30、dropout 378，连续墙体失败 3 次 | recovery edge → 保存上下文 → 保留 session/output/timer → 三次首帧共识重定位 | worker 14.337 秒；recovery 到 fresh tracking 约 16.47 秒；角度 221.1785°、镜像、scale 0.9546 注册成功。用户 22:50:53 请求停止，发生在 worker 完成前，非自动停止 |
| 短视觉遮挡（会话 1） | 22:51:06、22:51:25 `markers_missing_grace`；age 33/50 ms、uncertainty <0.73 | 保持预测/等待视觉恢复 | 分别约 1.22 秒、1.08 秒 |
| 长时间丢失（会话 2） | 22:51:45 起 P2 缺失；22:51:48 仍缺失 3,529 ms、uncertainty 16.38 | `recovery_required` → 保留会话和输出 → 三次首帧共识 | worker 22.457 秒；约 23.43 秒后 `fresh_sync`，候选约 0.910、shape_quality 约 0.551，成功 |
| 角色交换/交替遮挡（会话 2） | 22:52:28 P2 缺失，22:52:31 变为 P1 缺失；22:52:33 P1 age 2,900 ms、uncertainty 13.55、dropout 48 | 触发 recovery；三次首帧候选均 ambiguous（score 约 0.877、shape_quality 约 0.386） | 截止用户 22:53:10 请求停止仍未得到可信 reanchor；异步 worker 后续日志不能视为会话继续运行 |

### 当前量化门槛

- `marker_dropout_grace=2`：少量连续帧缺失先标记 `degraded`，不立刻恢复。
- `max_failures=3`：失败累计到 3 次才进入 `recovery_required`；恢复边沿只触发一次并递增 revision。
- marker hold：最多约 2,000 ms，且 `uncertainty_native <= 10.0`；超出后该角色 `available=false`。
- 角色分配：`max_marker_step=45 px`；候选代价差小于 `identity_margin=2.0` 时判 ambiguous。
- recovery cooldown：10,000 ms，避免同一丢失事件重复启动全局恢复。
- 墙体质量与角色可用性独立：多次 `wall_trusted=true`、`consecutive_wall_failures=0`，但角色标记仍会因遮挡/颜色候选丢失进入恢复。
- 恢复链路：`dual_motion.tick → degraded/recovery_required → recovery_episode_started → recovery_claimed → 保存上下文 → 保留 session/output/timer → 首帧内存读取+截图+三候选共识 → accepted/ambiguous → fresh_sync`。
- `waiting_position/arrival_unconfirmed` 是预测/路线进入目标半径后的等待确认状态，不等同于地图级自动停止；本批没有发现总运行时长触发。

### 证据文件

- 会话 1 短遮挡：[1791298227260 raw.png](D:/ACloud/auto_modules/data/poe2_live_terrain_test/occlusion_diagnostics/1791298227260-1791298227260-3a8e4e7a/raw.png)，[evidence.json](D:/ACloud/auto_modules/data/poe2_live_terrain_test/occlusion_diagnostics/1791298227260-1791298227260-3a8e4e7a/evidence.json)
- 会话 1 长丢失：[1791298249305 raw.png](D:/ACloud/auto_modules/data/poe2_live_terrain_test/occlusion_diagnostics/1791298249305-1791298249305-a7615911/raw.png)，[evidence.json](D:/ACloud/auto_modules/data/poe2_live_terrain_test/occlusion_diagnostics/1791298249305-1791298249305-a7615911/evidence.json)
- 会话 2 初次长丢失：[1791298305005 evidence.json](D:/ACloud/auto_modules/data/poe2_live_terrain_test/occlusion_diagnostics/1791298305005-1791298305005-71c04262/evidence.json)
- 会话 2 交替遮挡：[1791298347953 raw.png](D:/ACloud/auto_modules/data/poe2_live_terrain_test/occlusion_diagnostics/1791298347953-1791298347953-2e06acdc/raw.png)、[1791298351351 evidence.json](D:/ACloud/auto_modules/data/poe2_live_terrain_test/occlusion_diagnostics/1791298351351-1791298351351-8b0640ac/evidence.json)、[1791298353582 raw.png](D:/ACloud/auto_modules/data/poe2_live_terrain_test/occlusion_diagnostics/1791298353582-1791298353582-4f8d211b/raw.png)

### 结论和后续

- 主因不是整张地图或墙体匹配失败，而是角色标记在遮挡、颜色候选干扰或交替可见时超过 hold/uncertainty 门槛；全局恢复是正确兜底，但成本很高。
- 会话 1 的用户停止与恢复 worker 重叠，后续需审查异步 worker 回调与 session token 生命周期；本轮只记录，不修改运行代码。
- 会话 2 最后一次恢复候选持续 ambiguous，不能把 shape_quality 约 0.386 的结果当作可信定位。
- 本轮只做日志/证据审计，没有发送真实输入、没有修改运行时代码。

## 视觉丢失不应中止跟随：实现边界（2026-10-06）

- 用户决策：小地图人物图色只是观测源。图色短暂失准时，必须继续使用最后可信大地图坐标、手柄输出区间和速度模型预测；异常观测不能直接停止跟随。
- 根因确认：页面已有 `CommandRoleTracker` 预测，但 `DualVisualTracker` 在 marker 过期后仍发出 `recovery_required`，`Poe2DualMotionMixin` 随即重启首帧 worker，导致预测尚未消费就进入 14–23 秒全局重定位。
- 已实现：新增 `_is_marker_only_recovery_state()`；当 reason 属于 `markers_missing/markers_ambiguous/markers_missing_grace/markers_partial_grace` 且 `wall_trusted=true` 时，双人实时跟随延后全局恢复，保留 motion worker、session、output 和 command odometry。
- 边界修正：`recovery_required` 由 `_failed()` 生成时可能没有显式 `wall_trusted` 字段；现在同时接受带 `role_observations` 的 marker-only 诊断，只有显式 `wall_trusted=false` 才拒绝预测续行，避免真实长丢失事件仍误进入全局恢复。
- 已实现局部重锚入口：实时跟随触发 reanchor 时优先调用 `DualVisualTracker.request_local_correction()`，下一帧使用已确定方向/比例和预测位置附近的 `LocalMapMatcher`；不读内存、不重做方向、不启动全局首帧。只有局部 matcher 明确失败，才允许升级到全局恢复。
- 验证：新增“显式局部重锚在周期校正间隔之前执行”用例；双人运动与跟随恢复相关测试 `27 passed`，`compileall` 与 `git diff --check` 通过。
- 已实现：跟随 tick 对上述 marker-only 状态允许继续使用 `RoleTracker.estimate()`；只有墙体/地图跟踪失效或运动层明确给出恢复证据，才进入全局 reanchor。
- 设计边界：这不是无限相信视觉预测。地图实例变化、墙体失效、运动层持续无进展或显式生命周期停止仍可触发恢复；图标恢复后立即通过视觉样本更新速度和位置锚点。
- 验证：`tests/test_poe2_capture_test_page.py` 与 `tests/poe2_live_terrain/test_multiplayer_motion.py` 共 128 个用例中 127 次通过；1 个既有双人同目标时序用例在组合运行中波动，单独重跑通过。待继续运行 compileall、专项测试和 diff check。

## `no_safe_route_cooldown` 处理修正（2026-10-06）

- 根因：`SimulatedFollowRuntime._failed_plan_on_cooldown()` 命中时原逻辑直接返回 `BLOCKED`，释放输出；这只是上一次 A* 失败的短缓存，不等于现实人物无路可走。
- 已实现：冷却期间改为 `no_safe_route_probe`，根据目标方向、最近命令和小地图左右空闲信息生成 100ms 的有界侧向/前向探索脉冲；下一帧继续重规划。不会把人物停在原地。
- 设计边界：探索脉冲不把碰撞栅格当硬约束，因为当前坐标可能只是贴墙/栅格误差；脉冲幅度和持续时间受限，真实墙体仍由下一帧位移和接触证据纠正。
- 验证：`tests/poe2_live_terrain/test_multiplayer_follow_runtime.py` `60 passed`；新增用例覆盖失败路线冷却期间仍保持非零输出。

## 人物不动路径全量审查（2026-10-07）

### 已发现并调整的异常分支

- 首次 `no_safe_route`：原来直接 `BLOCKED`；现在进入 `no_safe_route_probe`，发送有界探索脉冲并保留下一帧重规划。
- `no_safe_route_cooldown`：原来冷却期间直接 `BLOCKED`；现在继续 `no_safe_route_probe`。
- `stalled_no_escape`：原来恢复候选全部失败后停住；现在使用交替侧向/前向脉冲，保持输出。
- `contact_relocalization_required`：原来先变成 `BLOCKED`，页面还没来得及局部重锚就释放输出；现在返回 `contact_relocalization_probe`，先保持移动。
- 路线存在但 `_local_command()` 返回零向量：原来只发中性帧；现在发 `route_not_progressing_probe`，避免单个零向量造成停顿。
- follower 位置短暂过期：原来 `WAITING_POSITION`；现在以最后可信坐标生成低置信 `command_prediction`。
- target 位置短暂过期：原来 `WAITING_POSITION`；现在以最后目标坐标生成 `target_hold`，等待新目标更新。

### 仍保留的合法停止边界

- 目标尚未初始化（`follower_position_unseeded/target_not_seeded`）。
- 地图实例不一致（必须等待新地图初始化，避免跨地图输入）。
- 已确认进入到达半径（目标未移动时不需要继续走）。
- 用户停止、页面关闭、游戏窗口失焦等生命周期/前台安全边界。

### 验证

- `tests/poe2_live_terrain/test_multiplayer_follow_runtime.py`：`60 passed`。
- `tests/poe2_live_terrain/test_multiplayer_motion.py`：`25 passed`。
- capture page 组合回归：除一个原有双人同目标重启动作的时序波动外其余通过；该用例单独重跑通过。
- `compileall` 与 `git diff --check`：通过。
## 2026-10-07 00:22–00:23 实机异常取证（只读，未修复）

- `(confirmed)` 输出链路异常：`00:22:12.285` 发生 `VirtualGamepadError: invalid_argument: Program session expired or was revoked. Explicit start is required.`；此前 `00:22:11.149–11.352` Host 仍持续提交 controller=2 非零报告，页面诊断也显示 `acquired=True/inputOwner=program`。本次停止/恢复的直接触发是虚拟手柄 program session 被 Host 撤销或过期。
- `(confirmed)` 视觉关联异常：`00:22:05.245` frame=1020 仍为 `tracking/visual`；`00:22:08.198` frame=1027 起变为 `markers_missing_grace`，`00:22:09.822` frame=1035 进入 `recovery_required`。对应 raw 截图中青色和橙色两个角色标记都清楚可见，但 `assignment.options=()`，说明候选检测到了、关联门限拒绝了。证据：`occlusion_diagnostics/1791303729713.../raw.png`。
- `(strong hypothesis)` 关联拒绝与 `max_marker_step=45` 和手动角色没有运动提示有关：frame=1020 的最佳 assignment cost 已为 `43.83`，随后 manual 角色 `speed_samples=0`，实际标记继续移动后超出 45 px 门限，候选虽在图上仍存在却被全部拒绝；下一次实验需记录逐候选距离验证。
- `(confirmed)` 路径规划异常：`00:22:08–00:22:11` P2 多次 `reason=no_safe_route_probe`，四个放宽因子全部 `no_path`/`collision_segment`；`plan_target_metrics.wall=255, collision=255, clearance=0`，目标 native `(935.659,1128.084)` 被栅格判为墙/碰撞。属于目标坐标与墙体栅格不一致或目标确实落在不可通行栅格的异常，不能直接等同于真实卡墙。
- `(confirmed)` 性能/时序异常：同一段 worker `total_worker_ms` 多次 40–70ms，而 `interval_ms=33`；`dropped_results` 从 196 增至 237，视觉结果滞后并扩大关联误差。00:23 会话仍有 28–50ms 超周期帧。
- `(confirmed)` 输出异常后恢复链路保留 session/output/timer 并启动首帧恢复；`00:22:12.369–00:22:25.302` 用时约 12.9s，期间前台检查连续等待 `poe2_not_foreground`。恢复完成后候选 score=0.893、shape_quality=0.465，首帧定位接受。
- `(confirmed)` 00:23 会话中两角色自 `00:22:37.155` 起同时不可见，至 `00:23:01.314` age=24.126s、uncertainty=109.067，候选始终只能形成一个 Dex assignment；quality=1.000，故不是整张墙体质量坏掉。
- `(scope)` 本轮只读日志、Host 日志、evidence.json 和 raw.png；没有修改运行代码、没有发送真实输入。下一步用一次可复现实验补记录逐候选距离、session 生命周期/撤销来源和目标栅格周边截图。

## 2026-10-07 — 跟随稳定性模块化实现（首批）

- `(implemented)` 新增 `multiplayer_localization/marker_association.py`，用时间间隔、角色屏幕速度、墙体位移和上限生成动态关联 gate；`DualVisualTracker` 保存每个角色的屏幕速度/最近关联时间，并把 gate/距离/options 写入诊断。候选存在但超过固定 45px 的情况不再直接归为不可见。
- `(implemented)` 颜色身份改为软约束：颜色提示过滤掉全部候选时，关联器会在同一动态几何 gate 内回退到相对位置/运动连续性，并记录 `identity_hint_fallback`。
- `(implemented)` 新增 `multiplayer_follow/target_projection.py`，将落在墙栅格但局部邻域存在可行走点的目标投影到最近可走点；规划诊断同时保留原始目标、规划目标和投影距离，不膨胀人物碰撞体。
- `(implemented)` `ProgramGamepadOutput.rearm()` 和 `ProgramFollowOutput` 单次 session-expired 重试：只重建输出租约并重发当前向量，不触发地图重定位；重复失败仍向上报告。
- `(implemented)` 双人 worker 保持最新结果优先，并按处理耗时自适应降低采样节奏，避免 33ms 周期下持续积压；保留 dropped_results/处理耗时诊断。
- `(verified)` 新增关联与目标投影纯测试；关联、投影、跟随 runtime、双人 motion、虚拟手柄共 `89 + 68` 个聚焦用例通过。页面两个时序用例组合运行波动，单独重跑均通过；未发送真实输入。
- `(next)` 继续补齐关联失败时的相对双人几何回退、目标投影邻域截图诊断和 worker 自适应节流回放测试，再跑完整 PoE2 回归。
- `(verified)` 更新 stale-frame replay 契约为“视觉过期时保持有界预测输出”；`tests/poe2_live_terrain` 全量 `429 passed`，`compileall` 和 `git diff --check` 通过。
