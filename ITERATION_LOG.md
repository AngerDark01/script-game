# Iteration Log

## [第 2026-10-06-7 轮] 2026-10-06 — 文档推导历史缺陷

### A. 阅读前声明

- 目标：`POE2_AUTOFOLLOW_COMPLETE_LOGIC.md` 的启动、同步、恢复、停止描述与历史修复证据对照。
- 核查：300/700ms 门槛、tracking/degraded、latest-only/revision、到达预测、恢复后输出、页面隐藏/关闭；区分文档逻辑矛盾与源码实现遗漏。
- 仅记录审查结论，不改运行代码，不发送真实输入。

### C. 对照结果与修正

- `(verified)` 前面列出的运行时代码缺陷在当前工作树已有对应实现和回归覆盖：recovery revision、恢复后的受控 tick、视觉 gap prediction、degraded 恢复门、probe 延后 arm、地图总时长门移除。
- `(fixed)` 文档修正了三处落后实现的描述：`degraded` 墙体可信帧可作为恢复入口；单独的预测不确定度/700ms 视觉年龄不会直接触发全局重定位；8 秒持续视觉停滞或结合运动证据才进入恢复。
- `(fixed)` 文档补充了 hint 的年龄/不确定度门槛：遮挡时只有 bounded hint 才发布给 worker，超过门槛仍保留页面侧预测但不发布过期 hint。
- `(fixed)` 文档把“只有显式停止才终止”的表述限定为实时跟随，并明确独立程序移动探针的状态性结束边界。
- `(verified)` 本轮未修改运行代码、未发送真实输入；`git diff --check` 通过。后续若修改运行逻辑，必须为对应契约增加离线回归，不以文档替代测试。

### D. 当前结论

本轮没有发现需要再次修改的运行时代码缺陷；剩余差异属于文档曾经把实时跟随和独立程序探针、预测质量和恢复触发条件混写，现已修正。

### C. 对照结论

- `(verified)` 文档中的 `recovery_requested` 边沿、`recovery_revision` 持续状态和 latest-only 丢帧保护，能够直接暴露“恢复边沿被覆盖后页面永远等待”的 bug 类别；这正对应历史 recovery revision 修复。
- `(verified)` 文档中的 300ms 启动帧门、700ms 运行 TTL 和恢复后 fresh sync 能暴露“恢复入口消费 301–700ms 帧、随后启动入口又拒绝同一帧”的门槛不一致风险；但要确认根因仍需沿调用链对照代码。
- `(verified)` 文档要求恢复成功后重新 seed、重新 arm 输出并执行受控 tick，能够暴露“tracker 已恢复但 ProgramFollowOutput 没有重新挂载/没有再次写入”的 bug。
- `(verified)` 文档要求视觉短暂丢失进入 bounded prediction、局部接触由运动证据决定，能够直接暴露旧代码“视觉帧超过 700ms 就释放输出并触发停止/重定位”的矛盾。
- `(verified)` 文档要求墙体可信的 `degraded` bounded estimate 可以恢复，能够暴露旧代码只接受 `tracking`、导致恢复上下文长期悬挂的问题。
- `(verified)` 文档的“只有运行时/角色/输出校验成功后才 arm”可暴露旧入口先 arm probe、后校验失败而留下 stale 状态的问题。
- `(partial)` 文档可以提示 Qt worker 迟到回调、页面隐藏/关闭后仍写 UI 的生命周期风险，但无法单凭文字确定 `QPointer`/`shiboken6` 对象失效或具体崩溃位置；这必须结合线程和 Qt 回调代码。
- `(not inferable)` 30 秒地图总时长硬停止、mixin 隐式导入 `NameError` 等实现级缺陷，旧文档没有足够事实直接推出，只能在“无地图总时长限制”的契约与源码对照时发现。

### D. 结论

文档更适合作为“契约矛盾检测器”：它能暴露状态机、时间门、恢复闭环和输出生命周期的违反项；不能替代源码调用链、日志和回放来定位所有实现级 bug。当前自动跟随文档已包含上述历史修复后的契约和边界。

## [第 2026-10-06-3 轮] 2026-10-06 — 全链路回归收口

### A. 本轮目标

完成上一轮已定位修复后的实验页回归，并排查除 `recovery_required` 边沿问题外的生命周期、输出、预测保持、重定位恢复和 Qt 日志崩溃风险；不发送真实游戏输入。

### C. 结果与证据

- `(fixed)` 新增关闭生命周期测试插入位置错误：原监控窗口测试的 `first.preview_timer`/可见性断言已归回原函数，日志 handler 测试不再引用跨函数变量。
- `(verified)` `Poe2CaptureTestPage.closeEvent()` → `shutdown()` 会停止实验 timer、释放 output、关闭监控窗口并移除 `_UiLogHandler`；handler 和 `_append_session_log()` 在页面或 `QPlainTextEdit` Qt 对象无效时直接返回，后台迟到日志不会触发 Qt abort。
- `(verified)` 双人同目标启动/恢复使用统一 700ms frame-age 门；启动异常会 stop 已创建 output，probe 只在 runtime/角色/output 全部成功后 arm；重复启动先释放旧 runtime/timer/output。
- `(verified)` 程序移动探针删除所有总时长硬停止；视觉短暂过期进入有界预测保持，接触恢复、失焦、显式停止和页面关闭仍可释放输出。
- `(verified)` 专项回归：capture page `104 passed`（含 suspend/shutdown 生命周期）；`tests/poe2_live_terrain` `422 passed`；目录外 PoE2 UI/worker/探针 `167 passed`；`python -m compileall -q src` 通过；`git diff --check` 通过（仅有 CRLF 转换提示）。
- `(verified)` 人工链路复核覆盖初始化、地图/首帧、双人 worker、单人/双人跟随、双人同目标、点击移动、输出租约、stale/degraded/occlusion、局部接触恢复、全局重定位、fresh resume、hide/close/shutdown 和日志 handler 脱离。未发现第二套运动/寻路实现或新的稳定性缺陷。
- `(fixed)` 追加人工对照时发现点击目标跟随 recovery 仍使用 `1000ms`，而恢复后实际 `start/tick` 使用 `700ms` runtime TTL；已统一为 `_FOLLOW_RUNTIME_MAX_FRAME_AGE_MS`，并新增 700–1000ms 边界测试，防止恢复消费后下一 tick 再拒绝同一帧。
- `(fixed)` 生命周期审查发现 `suspend()`/`shutdown()` 原先只停止视觉 worker 和程序移动，未显式停止 follow/dual-target timer 与 output；现已统一在隐藏页和关闭页释放所有程序输出，补充 suspend/shutdown 回归。

### D. 文档同步

- `CODEBASE.md` 已修正双人同目标/点击跟随恢复门、程序探针时长策略、视觉 gap 保持和 logger 生命周期描述。
- `docs/POE2_EXPERIMENT_REFACTOR_TASK.md` 已追加 C4/C5 收口证据、测试结果和未决实机边界。

### E. 未决风险与下一步

- 本轮没有发送真实手柄/游戏输入，因此不能把离线回归表述为实机移动验收。
- 全仓历史失败仍需单独运行环境隔离处理：`pydirectinput` distribution metadata 缺失，以及虚拟手柄 Qt 跨套件 backoff 时序波动；两者不在 PoE2 专项套件内。
- 全仓实测为 `1101 passed, 2 skipped, 2 failed`；虚拟手柄 backoff 用例单独重跑通过，判定为跨套件时序波动；另一失败为环境缺少 `pydirectinput` distribution metadata。
- 若用户后续明确授权实机测试，先采集启动后 Host ownership、首次非零输出、游戏前台状态和视觉实际位移，再针对输入消费边界做最小实验。

## [第 2026-10-06-4 轮] 2026-10-06 — 地图运行取消总时长限制

### A. 本轮目标

用户要求完整跑完一张地图，不能因总运行时长停止。检查 PoE2 程序移动/跟随链路中的总时长硬门，并保持每帧新鲜度、前台、地图实例、显式停止和输出异常等操作安全边界。

### C. 发现与修复

- `(fixed)` `_tick_program_move_probe()` 的旧实现曾保留可注入 `_program_probe_max_duration_ms` 时长门。该门即使默认未设置，也允许外部配置把整张地图运行按时间截断；现在完全移除。程序移动仅在到达/明确状态、失焦、地图/重定位失败、显式停止或页面生命周期结束时退出。
- `(fixed)` 物理拆分后的 `probe_mixin.py` 真实程序移动入口缺少 `QMessageBox`、`find_process_id`、`find_process_window`、`is_process_foreground` 的模块级导入；离线测试未覆盖到真实入口时会隐藏 `NameError`。已补齐显式依赖。
- `(verified)` 新增长时运行回归：将程序探针起始时间设为 24 小时前，并注入遗留 duration 属性，tick 仍正常 apply，不调用 release/stop。
- 保留的时间值均为局部安全契约：视觉帧龄 TTL、Host command TTL、恢复冷却和 worker join timeout 不限制整张地图运行时长；它们只控制单帧有效性、单次恢复和线程清理。

### D. 验证状态

- `(verified)` capture page `105 passed`；`tests/poe2_live_terrain` `422 passed`；`python -m compileall -q src` 通过；`git diff --check` 通过（仅 CRLF 转换提示）。
- `(verified)` 24 小时旧起始时间 + 遗留 duration 属性的长运行回归仍保持 output apply，未触发 elapsed stop；未发送真实游戏输入。
- `(fixed)` 模块级 `F821` 审查发现 mixin 拆分后的真实入口仍依赖旧页面隐式导入；已为 `probe_mixin`、`dual_motion_mixin`、`localization_mixin`、`page_lifecycle_mixin` 补齐运行时/Qt/窗口/类型依赖。
- `(verified)` `ruff check --select F821 src/auto_modules/ui/modes/poe2_live_terrain` 通过；顺序执行 capture page `105 passed`、PoE2 专项 `422 passed`、`compileall` 和 `git diff --check` 均通过。

## [第 2026-10-06-2 轮] 2026-10-06

### A. 本轮目标（阅读前声明）
**目标文件：**
- `src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py`（审查所有实验入口、tick、停止和异常边界）
- `src/auto_modules/ui/modes/poe2_live_terrain/probe_mixin.py`（审查恢复、重定位、worker/timer 生命周期）
- `src/auto_modules/ui/modes/poe2_live_terrain/dual_motion_mixin.py`（审查双人帧路由、generation、恢复边界）
- `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_follow/runtime.py`（审查目标、到达、路径和卡墙状态）
- `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_follow/command_role_tracker.py`（审查预测、视觉创新和速度融合）
- `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_follow/program_output.py`（审查输出和资源释放）

**本轮想弄清楚：** 除已修复的 `recovery_required` 边沿、degraded 恢复和 300ms 新鲜度问题外，是否仍存在会导致功能不可用、频繁停止/重定位、状态错乱、异常退出、输入未释放或性能退化的链路缺陷；先用代码、测试和离线回放确认，不发送真实游戏输入。

### C. 本轮发现（第一批）

- `(verified)` `probe_mixin._maybe_resume_dual_target_after_relocalization()` 使用 1000ms 恢复帧门，而 `capture_test_page.start_dual_target_experiment()` 使用 700ms 启动门；在 301–1000ms 的窗口内会清空恢复上下文后启动失败，双人同目标无法恢复。
- `(verified)` `start_dual_target_experiment()` 在地图/角色/输出校验后立即 arm `dual_target_probe`，但输出绑定和 `runtime.add_follower()` 仍可能抛异常；失败路径没有统一 stop probe，残留 armed 状态会污染下一次点击。
- `(verified)` `start_dual_target_experiment()` 没有像 `start_follow_experiment()` 一样清理已有 runtime/timer/output；重复启动或恢复回调重入会覆盖旧 output 引用并留下旧租约。
- `(verified)` `probe_mixin._tick_program_move_probe()` 仍有 30 秒硬停止，以及视觉帧过期/角色位置暂时为空即终止的分支；这与“短暂丢帧靠预测/重定位保持会话”的运动契约不一致，下一批单独验证其恢复能力。

**修订的旧结论：** 先前人工链路审查只覆盖了普通跟随的启动/恢复顺序，未覆盖双人同目标的启动异常、重入和恢复时间门，也未把程序移动探针的硬超时纳入“非终止恢复”契约。

**下一步：** 为前三项新增最小回归测试，修复启动清理和统一恢复新鲜度；随后单独审查程序移动探针的丢帧、重定位冷却和超时行为。

## [2026-09-24] PoE2 首帧 75% 锚定门槛实机复验

- 根因：最新 300px 首帧候选的内存锚点误差仅 0.325px、人物在可行走区域、方向 225°/比例 0.77 正常，但综合 confidence 0.786 被 PoE2 业务门槛 0.80 拒绝；图像分数 0.396、forward coverage 0.509 也被原视觉质量门槛拦截。
- 修复：PoE2 组合将 `minimum_confidence` 调为 0.75；新增可选 `minimum_score_when_anchored`，仅在锚点 <= 8px 且人物在 walkable 时使用 0.35；可信锚点 coverage 门槛调为 0.50。通用 registrar 默认值没有改变。
- 实机复验：当前 PathOfExile 进程重新初始化/取图/取内存锚点后返回 `local_tracking/anchored_absolute`，position=(352.24,671.70)，confidence=0.7858，angle=225°，reflection=true，scale=0.77，anchor_error=0.325，forward_coverage=0.5089。
- 验证：`25 passed`（composition + absolute registrar），端到端真实脚本通过；无任何输入或网络副作用。

## [SYNC] 2026-09-23 — 单帧定位接入正式 PoE2 页面

### A. SYNC 范围声明

**触发任务：** 用户确认数据采集页实机首帧成功，要求将同一套参数和定位链路正式接入 PoE2 实时地形定位页面。
**直接变更文件：** `src/auto_modules/ui/modes/poe2_live_terrain/page.py`、`tests/test_poe2_composition.py`。
**预计连带影响：** 正式页 runtime 状态诊断展示、PoE2 composition factory 的实测参数契约；不接入 A/B 多帧、输入设备或网络。

### C. SYNC 结果

- `(verified)` 正式页原本已经通过 `Poe2HybridProductRuntime` 调用 `build_poe2_hybrid_localization_experiment()`；本轮增加正式 runtime 回归，直接构造 snapshot 并断言 registrar 使用 `minimum_confidence=0.80`、`anchor_weight=0.65`、`anchor_disambiguation_gap=1.0`、45° 粗角度和 `0.35..2.45` 比例范围。
- `(verified)` 正式页识别诊断现在显示最佳 `confidence`、几何分、角度、比例、anchor 误差和覆盖率，不再只显示候选数/角度；数据采集页和正式页使用同一诊断字段。
- `(verified)` 正式页、composition、主窗口相关聚焦测试 `16 passed`；之前数据采集页单帧入口测试 `22 passed` 保持通过。

**修订旧结论：** 单帧算法并非只停留在数据采集页；正式页已使用同一 factory。本轮补充了正式 runtime 的参数契约回归和完整诊断展示，防止后续装配回退。

**覆盖进度更新：** `page.py` 的 capture/configure/start/tick/render 链路与 `composition.py` 的正式 factory 注入已复核；正式页仍只做定位和可视化，不执行路线、Xbox、键鼠、Host 或 LAN 输入。

## [实机验收] 2026-09-23 — 数据采集页单帧定位首轮运行

### 运行证据

- 地图实例：`MapFlotsam:14A7A83E`；内存人物坐标：`(285.50, 418.50)`。
- 首帧 absolute registration：`status=anchored_candidate`、`angle=219°`、`reflect=true`、`scale=0.75`、`anchor_error=1.961`、`best_anchored_score/confidence=0.822475`，通过 `minimum_confidence=0.80`。
- 后续状态：`source=visual_f2f`、`mode=local_tracking`、内存读取次数始终为 `1`；没有 `absolute_registration_failed`、`recovery_required` 或重复全局搜索。
- 本次采样期间 `shift=(0,0)`、`global_shift=(0,-0)`，说明人物未产生可观测移动；marker 保持在 `(287.4304, 418.8476)` 是预期行为，不代表跟踪卡死。
- 视觉帧间质量大多为 `0.956~1.000`，页面截图中的 `0.965` 是当前帧质量，不是首帧绝对置信度；首帧置信度已在日志中单独记录为 `0.822`。

### 结论

本轮已证明真实页面链路为“内存 anchor 首帧配准 → visual_f2f 局部跟踪”，方向/镜像/比例与人物位置一致，未发生多余内存读取。下一次只需在保持同一 session 的情况下移动人物，观察 `shift/global_shift`、地图 marker 和 trajectory 是否变化；无需再次调整首帧参数。

## [SYNC] 2026-09-23 — 数据采集页开放单帧首帧定位入口

### A. SYNC 范围声明

**触发任务：** 用户需要在“数据采集测试”页面直接验证已校准的首帧内存锚点 + 局部几何匹配，而不是误启动旧的 A/B 多帧实验。
**直接变更文件：** `src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py`、`tests/test_poe2_capture_test_page.py`（行为由现有回归覆盖）。
**预计连带影响：** 数据采集页按钮布局、hybrid session 与多帧 session 的互斥采样、首帧状态/位置展示；正式 PoE2 页面和绘图模式不变。

### C. SYNC 结果

- `(verified)` 数据采集页顶部新增“开始首帧定位”和“停止首帧定位”按钮，直接调用现有 `start_hybrid_localization()` / `stop_hybrid_localization()`；按钮状态随地图、session 和 timer 生命周期同步。
- `(verified)` 首帧定位启动时会停止采集页预览、独立截图监控和 A/B 多帧 session，避免同一截图源被多个 timer 同时消费；A/B 入口仍保留在“定位控制”窗口，二者不会混用。
- `(verified)` 页面新增可见首帧状态文本，实时显示 mode、source、confidence、内存读取次数、角度、比例、coverage、anchor error 和失败原因；地图 overlay 使用同一 hybrid registration transform。
- `(verified)` 22 个数据采集页/监控窗口/定位控制/PoE2 composition 测试通过。

**修订旧结论：** 原先“可以在数据采集页测试”容易造成误解：可见的“定位控制”实际是 A/B 多帧；本轮补上了明确的单帧按钮，之后测试入口和用户目标一致。

**覆盖进度更新：** `capture_test_page.py` 的单帧启动、停止、状态展示和互斥采样链路已复核；单帧算法仍由 PoE2 hybrid factory 注入，页面不复制匹配逻辑。

## [SYNC] 2026-09-23 — PoE2 单帧锚点几何参数显式接线

### A. SYNC 范围声明

**触发任务：** 用户要求直接使用当前 PoE2 首帧样本完成实验，并把达到 80% 以上置信度的比例、几何匹配权重和局部搜索参数接入实际实验链路。
**直接变更文件：** `src/auto_modules/features/poe2/live_terrain/experimental/hybrid_localization/composition.py`、`src/auto_modules/features/poe2/live_terrain/experimental/hybrid_localization/absolute_registrar.py`、`tests/test_poe2_composition.py`。
**预计连带影响：** PoE2 正式页的 hybrid factory、单帧 registrar diagnostics、首帧定位回归测试；不影响绘图模式、A/B 多帧首帧策略、输入设备或网络。

### C. SYNC 结果

- `(verified)` 真实样本 `20260923-125356-431876-MapFlotsam-14A7A83E` 的内存 anchor 为 `(285.49999, 418.50000)`，截图为 `200x200`，同实例 native 地图为 `2968x2277`。
- `(verified)` 实验报告 `data/poe2_live_terrain_test/probe_results/single-frame-20260923-tuned/report.json` 选择 `219° / reflect=true / scale=0.75`，anchor error `3.225`，forward coverage `0.7973`，anchored confidence `0.8182775`，状态为 `anchored_candidate`。
- `(verified)` PoE2 composition 不再依赖 registrar 类默认值，`build_poe2_hybrid_localization_experiment()` 显式注入经过该真实样本校准的 `AnchoredRegistrationConfig`：局部窗口 `150/110`、顶部动态区排除 `40`、人物清理半径 `22`、anchor 权重 `0.65`、anchor 消歧间隔 `1.0`、最小视觉分 `0.50`、普通/锚定覆盖门 `0.65/0.60`，比例和角度仍由 `0.35..2.45`、45° 粗搜后细化自动搜索。
- `(verified)` registrar diagnostics 增加 `confidence` 字段，与 `best_anchored_score` 使用同一数值；页面现有 runtime 日志会输出该置信度及角度、比例、anchor error 等诊断。
- `(verified)` PoE2 composition 额外启用 `minimum_confidence=0.80`；低于 0.80 的候选直接返回 `rejected`，不会把“看起来有候选”发布成可信人物位置。通用 registrar 默认保持 `0.0`，不破坏合成/单元几何夹具。
- `(verified)` composition 回归新增显式参数断言，并增加低于 0.80 的拒绝测试；PoE2 单帧、hybrid 集成和探针测试 `28 passed`，未发送任何输入或网络同步。

**修订旧结论：** 之前只能证明探针默认参数通过；现在确认实际 PoE2 页面工厂也使用同一组参数，避免页面运行时悄悄回到未校准默认值。

**覆盖进度更新：** `experimental/hybrid_localization/composition.py`、`absolute_registrar.py` 和 `tests/test_poe2_composition.py` 已重读并同步到 CODEBASE；当前真实证据仍是单地图单首帧，不外推为跨地图 80% 生产准确率。

## [IMPLEMENTATION] 2026-09-21 — PoE2 数据采集测试页

### 范围

用户批准方案 A：在 PoE2 页面内部增加独立“数据采集测试”页签，用于反复查看小地图截图、初始化/获取原生地图并显式保存测试数据。此页不启动定位、不执行输入，不修改绘图模式。

### 完成内容

- `ui/modes/poe2/composition.py` 新增独立采集测试 service、归档对象、截图预览回调和专属 recognizer 注入；实时定位 service 保持独立。
- 新增 `ui/modes/poe2_live_terrain/capture_test_page.py`，提供截图刷新/定时预览、初始化、获取、显式保存、清空和错误清理。
- `Poe2LiveTerrainPage` 内部增加 `实时地形定位` 与 `数据采集测试` 两个页签；没有测试依赖的旧注入场景仍保持单页兼容。
- `MainWindow` 只在 composition 提供测试依赖时注入第二页签；关闭和隐藏时停止测试页定时器。
- 更新 `CODEBASE.md`、设计文档和实施计划，记录状态隔离与后续方向校准扩展点。

### 验证

```text
10 个页面/composition/MainWindow 回归测试通过
PoE2 live-terrain 套件和架构边界：75 passed
```

### 后续断点

下一阶段在此测试页上接入方向/尺度诊断：使用保存的截图与当前 `TerrainSnapshot`，先做 45° 粗搜索，再做角度与比例细化；不得把 PoE2 方向策略下沉到通用定位状态机。

## [SYNC] 2026-09-21 — PoE2 与绘图模式视觉能力全量对齐审计

### A. SYNC 范围声明

**触发任务：** 用户要求确保 PoE2 当前阶段与绘图模式相关能力全部对齐，不能只补颜色校准入口而遗漏参数、截图、预览或运行时细节。
**第一轮目标文件：** `ui/modes/mapping_widget.py`、`ui/modes/mapping/ui/layout.py`、`ui/modes/mapping/runtime/session.py`、`ui/dialogs/color_picker_dialog.py`、`ui/modes/poe2_live_terrain/config_panel.py`、`ui/modes/poe2_live_terrain/monitor_dialog.py`。
**本轮想弄清楚：** 两个业务在选区、截图模式、颜色采样、HSV/高级参数、参数即时应用、预览内容和持久化语义上还存在哪些逐项差异；哪些差异是 PoE2 业务边界允许的，哪些会改变视觉匹配结果。
**预计连带影响：** `Poe2MonitorConfig` profile 契约、composition preview provider、`Poe2LocalizationRuntime` visual evidence、页面双预览和 focused tests；原绘图模式保持只读。

### C. 第一轮发现

**关键发现：**

- `(verified)` 颜色采样主体已经复用同一个 `ColorPickerDialog`，PoE2 也把当前完整 recognizer 参数传入，所以预处理图、墙体/人物采样、HSV 范围和墙体 mask 预览算法一致。
- `(verified)` 绘图模式主面板除高级窗口外，还直接暴露 `enable_wall`、`enable_fog`、`clahe_enabled`、`deepen_enabled`、`wall_weight`、`edge_weight`、`edge_low`、`edge_high` 和 `player_clear_radius`；PoE2 当前只暴露高级窗口，而该窗口是否覆盖全部字段尚需下一轮逐项核对。
- `(verified)` 绘图模式只有完成区域/中心选择后才启用颜色按钮；PoE2 当前无 binding 时仍允许点击，之后才用错误弹窗拒绝，交互状态没有对齐。
- `(verified)` 绘图模式 center 和 region 的人物定位存在旧式 fallback；PoE2 center 几何契约、region 多候选 fail-closed 是已审核的业务差异，不能为了表面对齐而复制旧 fallback。
- `(verified)` 绘图模式的 stitcher merge、canvas、draw scale、保存地图和导航点属于离线建图业务；PoE2 使用在线 native terrain reference，这些控件不应复制到 PoE2 profile。

**修订旧结论：** “已有颜色校准和高级参数入口即表示视觉配置完全对齐”不成立；还必须核对高级窗口未覆盖的直接参数和控件启用条件。

**覆盖进度更新：** `mapping_widget.py`、`mapping/ui/layout.py`、`mapping/runtime/session.py`、`color_picker_dialog.py` 已完整核对本任务相关函数；`poe2_live_terrain/config_panel.py`、`monitor_dialog.py` 已完整核对当前配置流。`mapping/io/config_store.py`、`config_restore.py` 连带确认了完整 recognizer 参数持久化与 UI 回填语义。

### A. 第二轮目标（阅读前声明）

**目标文件：** `ui/dialogs/advanced_settings_dialog.py`、`ui/dialogs/advanced_settings/params_adapter.py`、`ui/dialogs/advanced_settings/tabs.py`、`core/vision/hsv/params.py`、`features/poe2/live_terrain/runtime.py`、`ui/modes/poe2_live_terrain/page.py`。
**本轮想弄清楚：** 高级窗口究竟覆盖哪些 recognizer 字段、哪些字段只能由绘图主面板控制；PoE2 保存的字段是否全部在运行时生效；页面展示是否与 matcher 消费的数组完全同源。

### C. 第二轮发现

**关键发现：**

- `(verified)` `AdvancedSettingsDialog` 覆盖 deepen/gamma/tophat/CLAHE、透明模式、饱和度过滤、Canny、wall/edge 权重；它不覆盖 `enable_wall`、`enable_fog` 或 `player_clear_radius`。因此 PoE2 虽保存完整参数字典，但用户无法在自己的页面调整这三个会直接改变 combined mask 的字段。
- `(verified)` `HSVRecognizer.get_params()/set_params()` 对 wall/fog/player HSV、上述三个缺失字段以及其余预处理参数均对称；缺口位于 PoE2 UI 组合，不在底层 recognizer。
- `(verified)` `Poe2LocalizationRuntime.configure_monitor()` 会在每次 profile 保存/选择/开始监控时应用 profile 参数；空 profile 恢复 dedicated recognizer 初始快照，不会继承上一 profile。
- `(verified)` 成功选中人物后，页面展示的 `state.match_mask` 与 `_global_match()`/`_local_match()` 消费的 `Poe2FrameInput.visual.match_mask` 同源且保留灰度权重。
- `(conflict)` 区域模式人物识别失败时 `tick()` 在生成 visual evidence 之前返回，因此 raw frame 虽可见，预处理图和 match mask 均为空；这与“配置时能看见真正匹配特征”的诊断目标冲突。定位应继续 fail closed，但视觉证据应先生成并随失败状态发布。

**修订旧结论：** 运行时成功路径已对齐不等于诊断路径已对齐；识别失败恰恰是最需要显示预处理和 match mask 的场景。

**覆盖进度更新：** `advanced_settings_dialog.py`、`advanced_settings/params_adapter.py`、`advanced_settings/tabs.py` 已核对全部参数读写；`core/vision/hsv/params.py` 已核对完整字段集合；`Poe2LocalizationRuntime.tick/configure_monitor/_build_visual_evidence` 和 `Poe2LiveTerrainPage.handle_runtime_state` 已深读本任务分支。

**实现假设：** 根因是 PoE2 配置组合只接入了高级对话框，且 visual evidence 构建时机错误。最小修复为：在 PoE2 面板补齐绘图模式有效的直接视觉控件与 binding 启用规则；将视觉证据生成提前到人物策略结果之后、失败返回之前，未选中人物时用 `player_pos=None` 生成可诊断特征，但绝不调用 localizer。

### C. 第二轮实现验证

- `(verified)` PoE2 面板已补齐 wall/fog 开关、CLAHE、颜色深化、wall/edge 权重、Canny 高低阈值和人物动态擦除半径；这些控件与完整 profile 参数双向同步，高级窗口应用后也会回填。
- `(verified)` 颜色校准按钮仅在存在 binding 且配置可编辑时启用；高级视觉参数仍可在绑定前配置。
- `(verified)` `Poe2LocalizationRuntime.tick()` 现在先生成 visual evidence，再判断人物策略是否失败；`player_not_detected` 状态包含可诊断的 processed/match/wall/fog 层，同时 `MapLocalizer.update()` 调用次数保持为零。
- `(verified)` 新增失败测试复现三个缺口，修复后配置面板、runtime 和颜色对话框相关测试 `16 passed`。

### A. 第三轮目标（阅读前声明）

**目标文件：** `ui/modes/mapping/capture/selection_controller.py`、`ui/modes/poe2_live_terrain/capture/selection_controller.py`、`features/poe2/live_terrain/monitor_source.py`、`ui/modes/poe2/composition.py`、`features/poe2/live_terrain/monitor_config.py`、`ui/modes/poe2_live_terrain/profile_toolbar.py`、`ui/modes/poe2_live_terrain/presenter.py`。
**本轮想弄清楚：** 画框和中心点的坐标/DPI 契约是否真正等价，圆形遮罩是否只影响视觉帧而不改坐标，profile 切换是否完整同步 runtime/UI，以及预览缓存是否在失败/停止时正确更新。

### C. 第三轮发现

**关键发现：**

- `(conflict)` `SquareScreenCapture.capture_square()` 和绘图模式都把 size 定义为物理像素；PoE2 中心选择却把 size 再乘 `devicePixelRatio`。在 125%/150% DPI 下，配置 320 会抓取 400/480 像素，而 `circle_radius` 仍为 160，造成截图、圆形遮罩和 profile `capture_size` 不一致。
- `(conflict)` PoE2 region 选择会把 profile `capture_size` 改为矩形短边；绘图模式 region 选择不改中心截图大小。用户从 region 切回 center 时会意外使用旧矩形短边。
- `(verified)` 左上角和中心点本身都按逻辑坐标乘 DPI 转成物理坐标；`MonitorBinding.player_marker_position` 使用截图局部物理坐标，方向正确。
- `(verified)` `MonitorFrameSource` 的圆形模式保持矩形数组尺寸与坐标原点，只把圆外像素清零；square 模式不复制/改写帧。
- `(verified)` profile 选择会同步 page、dialog、timer 和 runtime；composition 的实时抓图读取 active profile，校准抓图优先使用对话框当前未保存 config。
- `(conflict)` `Poe2LiveTerrainPage.handle_runtime_state()` 在新 state 没有 processed/match frame 时不清理 QLabel，因此视觉处理或捕获失败后会残留上一帧图像，诊断界面与当前状态不一致。
- `(partial)` 通用高级窗口仍显示“拼接算法”页，但 PoE2 没有 stitcher 且会过滤这些字段；应在 PoE2 组合层隐藏该无效页，避免用户修改不会生效的控件。

**修订旧结论：** 选区控制器复用了同一 overlay 并不代表 DPI 契约一致；截图 size 的单位必须沿调用链核对到 `SquareScreenCapture`。

**实现假设：** 将 PoE2 中心截图边长保持为用户输入的物理像素、region 选择保留既有 center size、无视觉数组时主动清空对应预览，并隐藏 PoE2 不适用的 stitcher tab，可消除当前剩余的行为差异而不改变定位策略。

### C. 第三轮实现与最终审计结果

- `(verified)` 修正高 DPI 中心截图：逻辑点击位置仍乘 DPI 转换为物理中心，但用户输入的 capture size 按截图后端契约保持物理像素，不再二次放大；新增 150% DPI 回归测试。
- `(verified)` region 画框不再覆盖 center capture size；两种选择模式切换时各自语义独立。
- `(verified)` 页面收到无视觉数组的失败 state 时主动清除上一帧预处理/match 画面，避免陈旧诊断。
- `(verified)` PoE2 高级参数窗口隐藏无效的“拼接算法”页；profile 仍只接受 `HSVRecognizer.get_params()` 支持的字段。
- `(verified)` 配置窗加入滚动容器并设置 560x760 初始尺寸，补齐参数后在 768p 屏幕仍能访问保存/取消按钮；行为与绘图模式滚动控制栏一致。
- `(verified)` 机器校验 32 个 recognizer 持久化字段无未归类项：高级窗口 21 项，PoE2 快捷控件 9 项，颜色采样 4 项（集合有交叉）；fog HSV 与 morphology kernel 参数完整保留，当前和绘图模式一样不作为主面板采样项。
- `(verified)` 圆形遮罩、profile 激活、未保存配置预览、runtime 参数应用、双预览数组来源和停止清理链路均已核对，无剩余实现缺口。

**有意保留的业务差异：** PoE2 不复制绘图模式的 stitcher merge/canvas/draw-scale/保存地图/导航点能力；PoE2 native terrain 已由外部程序提供。PoE2 region 人物策略保持多候选 fail-closed，不复制绘图模式的 last-known/中心 fallback。上述差异符合已审核的业务和安全边界，不是遗漏。

**验证结果：** 首轮缺口由 3 个失败测试复现，末轮 DPI/尺寸/缓存/无效 tab 由 4 个失败测试复现；修复后完整 PoE2、页面、presenter、main-window monitoring 和 architecture focused suite `76 passed`，`compileall` 与 `git diff --check` 通过。全项目结果为 `532 passed, 1 skipped, 3 failed, 10 subtests passed`；3 项失败全部位于未修改的 `tests/test_pathfinder.py`，分别是对角穿角、未探索区域和细墙语义的既有失败，与 PoE2/视觉/UI 调用链无关。Serena 只报告语言服务器未加载项目 venv 的 PySide6/numpy/cv2 missing-import，无新增代码诊断。

**CODEBASE.md 更新内容：** 更新 PoE2 配置模块、视觉参数应用算法、F-POE2-LOC 失败诊断跳和 P1 风险状态；`docs/POE2_LIVE_TERRAIN_CURRENT_STATE.md` 增加最终对齐矩阵与实机剩余项。

**覆盖进度更新：** 本轮声明的 selection controller、monitor source、composition、monitor config/profile toolbar、presenter 均已完成本任务调用链深读；受影响的 config panel、monitor dialog、runtime、page 已按修改后源码复核。

## [SYNC] 2026-09-19 — 通信层重构任务 1-9

### A. SYNC 范围声明
**触发任务：** 按已审核通信层设计落地通用契约、共享 Host session、持久信任、能力集合和地图扩展点。
**直接变更文件：** `src/auto_modules/core/communication/*`、`src/auto_modules/application/communication/*`、`src/auto_modules/adapters/host/*`、`src/auto_modules/features/torchlight/follow/service.py`、`src/auto_modules/application/event_workbench/service.py`、`services/lan_input_sync/src/LanInputSync/*`、通信测试和协议文档。
**预计连带影响：** Follow/Event Workbench 的 Host 生命周期、`sync.share.*` drain 消费路径、C# LAN `Session` 能力授权、重连 fencing、CODEBASE 架构和协议说明。

### C. SYNC 结果
**连带重读文件：** `core/communication/*`、`application/communication/*`、`adapters/host/*`、
`application/event_workbench/service.py`、`features/torchlight/follow/service.py`、
`services/lan_input_sync/src/LanInputSync/{IdentityStore,PeerTrustStore,SessionCapabilities,LanSyncService*}.cs`。
**CODEBASE.md 更新内容：** 新增通信运行时模块职责、Follow/Event 数据流、C# 能力集合和风险登记。
**ARCHITECTURE_GUIDE.md / README.md / protocol-v1.md 更新内容：** 明确一个 peer 一个物理
session、多 capability 复用、持久信任/自动恢复 fence、旧命令兼容期和 map 扩展点边界。
**覆盖进度更新：** 本轮新增通信文件已完成针对性深读；C# 生产编译因当前机器无 .NET SDK
保持 `(partial)`，已通过源码审查和 Python fake/loopback 测试替代验证。
**修订的旧结论：** 原来 `DataOnly` 被视为 session 类型；现在确认它只是 capability 集合
在兼容期的派生视图，输入、位置和事件可以共享同一物理 session。
**新增 Finding：** P1 风险已记录在 CODEBASE.md：Host drain 字段兼容和 C# lane 前缀复用
需要后续协议版本收敛。

**本轮收尾复核（2026-09-19）：** 补读 `LanSyncService.Control.cs::RunControlsAsync`、
`LanSyncService.cs::Handle/ConfigureLocked/CloseLocked/Dispose`、`LanSyncService.Transport.cs::ReceivePacket`、
`IdentityStore.cs::Preferences`、`communication_adapter.py::pump/ensure_connected` 和对应 loopback/fake tests。
已修订“无 .NET SDK”的旧结论：系统默认 `dotnet` 不可用，但 `D:\ACloud\dotnet-sdk2\dotnet.exe`
可用，LAN 31 项和 Host 57 项全部通过。数据会话可在不换 sessionId 的情况下增加/移除输入；
无接收授权时返回拒绝并保留数据会话。正常进程重启恢复已信任 session，手动 stop 不恢复；
首轮恢复连接失败后继续退避，远端重新上线后自动连回；旧输入 watchdog 断线中立化契约
仍由全套 LAN 测试验证。权威 LAN 信任文件为
`trusted.json`/`preferences.json`，不是尚未接入运行时的 `PeerTrustStore`。
通信 Python 聚焦测试通过；全量 pytest 492 passed、2 skipped、4 failed，失败为缺少
`pydirectinput` 发布依赖和 3 项独立 Pathfinder 测试，不纳入本轮通信变更。
**覆盖状态：** 本轮上述函数体和失败分支已深读；未重读的项目其余文件仍保持原有覆盖状态。


## [SYNC] 2026-09-19 19:32 — 离线可信节点持续重连

### A. SYNC 范围声明
**触发任务：** 通信线程完成后遗留的离线可信节点重连修复收尾。
**直接变更文件：** `LanSyncService.Control.cs`、`LanSyncService.cs`、`LoopbackTests.cs`、`CODEBASE.md`。
**预计连带影响：** 出站连接失败后的退避调度、成功连接后的退避复位、可信节点恢复 Flow 及 LAN loopback 测试。

### C. SYNC 结果
**连带重读文件：** `LanSyncService.Control.cs`、`LanSyncService.cs`、`LoopbackTests.cs`、`CODEBASE.md`。
**CODEBASE.md 更新内容：** §5 补全 `RunControlsAsync()` 与持续重连算法、失败行为和副作用；可信节点恢复 Flow 明确失败重调度与成功复位退避。
**覆盖进度更新：** 上述变更函数和新增 loopback 测试已重读；LAN 测试使用私有 .NET 8 SDK 验证为 `31 passed`。
**新增 Finding：** 离线节点首次重连失败后必须保留恢复资格并再次进入有界退避；延迟回调还需以 generation、startVersion 和 `_connecting` 三重栅栏防止过期连接复活。

## [SYNC] 2026-09-19 — UI 正常关闭与能力组合

### A. SYNC 范围声明
**触发任务：** 检查通信重构的 GUI 关闭/启动路径，避免把正常退出误当手动停止，并暴露同会话能力组合。
**直接变更文件：** `SyncPanel`、`LanSyncService`、`ControllerRegistry`、对应 UI/Host/LAN 测试和协议说明。
**预计连带影响：** UI 关闭回调、Host `sync.*` 路由、接收端进程内暂停栅栏、持久化恢复和能力协商 Flow。

### C. SYNC 结果
**连带重读文件：** `GamepadPage.shutdown()`、`LanPage.shutdown()`、`SyncPanel._Request/start_peer/start_all_events/render/shutdown()`、`LanSyncService.Handle/ConfigureLocked/ValidateIncomingCapabilitiesLocked()`。
**CODEBASE.md 更新内容：** 通信状态、LAN 面板能力组合与 suspend Flow；协议文档新增 `sync.suspend`。
**覆盖进度更新：** 上述调用链和新增测试已深读；LAN 32 项、Host 57 项、UI 14 项通过。
**修订的旧结论：** 原认为 `Dispose()` 保留偏好即可恢复；现确认 GUI 在其之前调用 `sync.stop` 清除偏好，已改用进程内 `sync.suspend`。普通配置仍应允许接收，所以暂停栅栏与 `_autoReconnectBlocked` 分离。

## [Round 1] 2026-05-19

### A. 本轮目标（阅读前声明）
**目标文件：**
- `README.md`（原因：确认项目运行方式和整体目标）
- `main.py`（原因：确认应用入口、共享上下文初始化）
- `gui/app_context.py`（原因：确认跨模块共享服务，尤其 PathFinder、截图、追踪器）
- `gui/main_window.py`（原因：确认模式切换入口）
- `gui/navigation_params.py`（原因：确认导航参数模型，后续移动映射参数需要落在这里）
- `gui/dialogs/nav_params_dialog.py`（原因：确认参数 UI 如何读写 NavConfig）
- `gui/modes/navigation_mode.py`（原因：当前自动导航、监控框、点击触发主链路所在文件）
- `core/auto_navigator.py`（原因：确认自动导航何时请求移动点击）
- `core/motion_controller.py`（原因：当前地图向量到屏幕点击坐标的转换实现）
- `core/navigation_core.py`（原因：确认定位输出坐标和 draw_scale/crop_offset 关系）
- `core/pathfinder.py`（原因：确认 A* 输出路径坐标体系）
- `core/stitcher_core.py`（原因：确认建图 draw_scale/坐标体系来源）

**本轮想弄清楚：**
- 自动导航点击链路中，哪些坐标是地图全局坐标，哪些坐标是屏幕物理像素。
- 当前“地图距离线性映射到屏幕点击距离”的参数来源，以及为什么会导致点击距离太短。
- 新增“人物真实可见/可交互范围框”和点击半径参数应放在哪些模块，避免污染定位一致性。

### Coverage
| 文件 | 状态 | 阅读次数 | 备注 |
|------|------|---------|------|
| `README.md` | PENDING | 0 | 项目概览与运行方式待确认 |
| `main.py` | PENDING | 0 | 应用入口待确认 |
| `gui/app_context.py` | PENDING | 0 | 共享上下文待确认 |
| `gui/main_window.py` | PENDING | 0 | 模式切换待确认 |
| `gui/navigation_params.py` | PENDING | 0 | 导航参数模型待确认 |
| `gui/dialogs/nav_params_dialog.py` | PENDING | 0 | 参数 UI 待读 |
| `gui/modes/navigation_mode.py` | PENDING | 0 | 导航主链路待读 |
| `gui/modes/mapping_widget.py` | PENDING | 0 | 建图 UI 后续如需对齐时再读 |
| `core/auto_navigator.py` | PENDING | 0 | 自动导航状态机待读 |
| `core/motion_controller.py` | PENDING | 0 | 鼠标点击映射待读 |
| `core/navigation_core.py` | PENDING | 0 | 定位坐标系待读 |
| `core/pathfinder.py` | PENDING | 0 | 路径输出坐标系待读 |
| `core/stitcher_core.py` | PENDING | 0 | 建图坐标系待读 |
| `core/path_utils.py` | PENDING | 0 | 路径平滑/投影工具后续如需再读 |
| `core/route_manager.py` | PENDING | 0 | 路线持久化后续如需再读 |
| `tests/test_auto_navigator.py` | PENDING | 0 | 自动导航测试后续同步 |
| `tests/test_path_utils.py` | PENDING | 0 | 路径工具测试后续同步 |
| `tests/test_route_manager.py` | PENDING | 0 | 路线管理测试后续同步 |

### C. 本轮发现
**关键发现：** (verified) 导航系统有三套必须分离的坐标概念：小地图截图范围用于定位，地图全局坐标用于路线/A*，真实主画面点击范围用于鼠标控制。原 `MotionController._calculate_target_screen_position()` 直接执行 `screen_delta = map_delta * movement_scale_factor`，当自动导航子目标较近时会把点击落在人物脚下附近，导致“点击了但不走”或移动过短。

**修订的旧结论：** 原来把 `movement_scale_factor` 当作唯一移动映射参数；现在确认它不足以同时表达“方向”和“最低点击触发距离”。新增最小/最大点击半径后，`movement_scale_factor` 只负责原始距离估算，最终屏幕点击距离会被夹到可交互半径范围内。

**新疑问：** (partial) 默认 `game_view_map_size=520`、`movement_min_click_radius=180`、`movement_max_click_radius=360` 需要用户在真实游戏内通过橙色框和日志 `click r` 校准。

**更新了 CODEBASE.md：** §1、§2、§3、§4、§5、§6、§8、§9。

**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `README.md` | PENDING | 浅读 | 1 | 确认项目是 PySide6 + OpenCV 小地图拼接/导航工具，README 文字存在编码显示问题 |
| `main.py` | PENDING | 浅读 | 1 | 确认入口仅创建 QApplication 和 MainWindow |
| `gui/app_context.py` | PENDING | 浅读 | 1 | 确认共享 ScreenCapture、MapStitcher、PlayerTracker、PathFinder |
| `gui/main_window.py` | PENDING | 浅读 | 1 | 确认 MappingWidget 与 NavigationModeWidget 共享 AppContext |
| `gui/navigation_params.py` | PENDING | 深度完整 | 1 | 确认 NavConfig 是地图 config.json 的导航契约，已新增真实可见框和点击半径参数 |
| `gui/dialogs/nav_params_dialog.py` | PENDING | (partial) | 1 | 确认参数 UI 的 widget_map/dataclasses.replace 流程，已接入新增参数；全量 UI 细节未覆盖 |
| `gui/modes/navigation_mode.py` | PENDING | (partial) | 1 | 确认自动导航主循环、监控框、鼠标点击触发链路，已新增橙色真实可见框；文件很大仍需后续继续清理编码文本 |
| `core/auto_navigator.py` | PENDING | 深度完整 | 1 | 确认状态机只输出 map-space 子目标和 issued_click，不直接处理屏幕点击距离 |
| `core/motion_controller.py` | PENDING | 深度完整 | 1 | 已从线性距离映射改为方向归一化 + 最小/最大屏幕点击半径夹紧 |
| `core/navigation_core.py` | PENDING | (partial) | 1 | 确认定位输出为 draw_scale 下的地图全局坐标，定位逻辑不应承担主画面点击映射 |
| `core/pathfinder.py` | PENDING | 深度完整 | 1 | 确认 A* 输入输出都是地图全局坐标 |
| `core/stitcher_core.py` | PENDING | (partial) | 1 | 确认建图保存 wall_layer/current_pos/canvas_size，draw_scale 是地图坐标基准 |
| `core/path_utils.py` | PENDING | 浅读 | 1 | 确认路径投影/插值用于 AutoNavigator 子目标选择 |
| `tests/test_auto_navigator.py` | PENDING | 浅读 | 1 | 确认 issued_click/cooldown 行为已有测试 |
| `tests/test_motion_controller.py` | 新增 | 深度完整 | 1 | 新增点击半径夹紧测试，覆盖短距离、长距离、零距离 |

**下一轮计划：** 如果真实测试仍出现“点了不走”，下一轮优先读取 `core/input_driver.py` 和 `pydirectinput` 调用环境，判断是点击坐标问题还是游戏窗口未接收点击。

## [SYNC] 2026-05-19 - 自动导航点击映射和真实可见框

### A. SYNC 范围声明
**触发任务：** 用户指出自动导航鼠标点击映射太短，需要整体理解项目后正确修改。

**直接变更文件：**
- `gui/navigation_params.py`
- `gui/dialogs/nav_params_dialog.py`
- `gui/modes/navigation_mode.py`
- `core/motion_controller.py`
- `tests/test_motion_controller.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：** `NavigationModeWidget._apply_config_to_core()` 将新增参数传入 `MotionController.set_params()`；`navigation_loop()` 每次定位后更新绿色小地图截图框和橙色真实可见框；`MotionController.move_to_map_target()` 的点击坐标从线性短距离映射变为方向点击半径夹紧。

### C. SYNC 结果
**连带重读文件：** `gui/navigation_params.py`、`gui/dialogs/nav_params_dialog.py`、`gui/modes/navigation_mode.py`、`core/motion_controller.py`、`core/auto_navigator.py`。

**CODEBASE.md 更新内容：** 补充导航/移动控制架构、关键函数算法、数据流、NavConfig 新契约和风险登记。

**覆盖进度更新：** `core/motion_controller.py`、`gui/navigation_params.py`、`tests/test_motion_controller.py` 达到本任务深度完整；`navigation_mode.py` 和参数对话框为本次影响范围完整、全文件仍标 partial。

**新增 Finding：** P1 风险 `MotionController._calculate_target_screen_position()` 的半径默认值需要真实游戏校准，否则可能仍点得过近或过远。

## [SYNC] 2026-05-19 - 橙色真实可见框即时刷新

### A. SYNC 范围声明
**触发任务：** 用户反馈修改 `真实可见范围(地图像素)` 后导航页面橙色框没有马上变化，仍显示旧的 520。

**直接变更文件：**
- `gui/modes/navigation_mode.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：** 参数面板发出 `parameters_changed` 后，导航页不仅更新内存配置和幕布，还会立即刷新橙色真实可见框；保存配置后也会刷新橙色框，避免重新应用配置后显示旧尺寸。

### C. SYNC 结果
**连带重读文件：** `gui/modes/navigation_mode.py`、`gui/dialogs/nav_params_dialog.py`、`gui/navigation_params.py`。

**CODEBASE.md 更新内容：** 补充 `_refresh_game_view_rect_from_known_position()` 的即时刷新职责；更新参数保存/加载 Flow。

**覆盖进度更新：** `gui/modes/navigation_mode.py` 对橙色框刷新链路已深读，整文件仍保持 partial。

**修订的旧结论：** 原以为调参不生效可能是配置字段未更新；现在确认字段会进入内存配置，但旧代码只在导航循环中刷新橙色框，因此导航未跑或下一帧未到时会停在旧矩形。

## [SYNC] 2026-05-19 - 自动估算点击半径

### A. SYNC 范围声明
**触发任务：** 用户反馈 2K 屏幕下 `movement_scale_factor=10` 仍然点击很短，需要自动检测/对比大小。

**直接变更文件：**
- `gui/dialogs/nav_params_dialog.py`
- `gui/modes/navigation_mode.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：** 参数面板新增“自动估算点击半径”按钮；根据已校准的 `game_screen_center` 和所在屏幕物理边界估算最小/最大点击半径。自动导航状态栏显示 `click r/raw`，便于判断点击是否被最大半径夹住。

### C. SYNC 结果
**连带重读文件：** `gui/dialogs/nav_params_dialog.py`、`gui/modes/navigation_mode.py`、`gui/navigation_params.py`。

**CODEBASE.md 更新内容：** 补充 `NavParametersDialog._auto_estimate_click_radius()` 和状态栏 click radius 诊断。

**覆盖进度更新：** `gui/dialogs/nav_params_dialog.py` 对运动控制参数区域已深读；全文件仍保持 partial。

**修订的旧结论：** 运动映射系数调到 10 仍很小不是比例没生效，而是 `movement_max_click_radius=120` 把最终点击半径限制住了。

## [SYNC] 2026-05-19 - 自动导航点击窗口焦点修复

### A. SYNC 范围声明
**触发任务：** 用户观察到鼠标已经移动/点击，但鼠标图标是普通系统光标，说明点击落在工具窗口或非游戏窗口，而不是游戏窗口。
**直接变更文件：**
- `core/input_driver.py`
- `core/motion_controller.py`
- `gui/modes/navigation_mode.py`
- `tests/test_motion_controller.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：** 自动导航点击前主窗口不再保持置顶并会下沉；运动控制优先使用 Win32 输入驱动激活点击坐标下的窗口并执行按下/抬起点击；点击坐标会被夹到物理屏幕范围内。

### C. SYNC 结果
**连带重读文件：** `core/input_driver.py`、`core/motion_controller.py`、`gui/main_window.py`、`gui/selection/indicator_overlay.py`、`gui/modes/navigation_mode.py`。
**CODEBASE.md 更新内容：** 新增 Input Control Current Notes，记录 `InputDriver`、`MotionController` 和 `_set_game_input_window_mode()` 当前职责。
**覆盖进度更新：** `core/input_driver.py` 已纳入自动导航点击链路；`core/motion_controller.py` 增加屏幕边界夹取、窗口聚焦和 InputDriver 优先点击；`gui/modes/navigation_mode.py` 增加自动导航期间主窗口取消置顶/下沉/恢复逻辑。
**修订的旧结论：** 之前认为“点击无效”主要可能是点击后端不被游戏接收；现在根据鼠标图标证据确认关键根因还包括 PySide 主窗口 `WindowStaysOnTopHint` 遮挡游戏窗口，导致点击目标窗口错误。

## [SYNC] 2026-05-20 - 点击后端回归修正

### A. SYNC 范围声明
**触发任务：** 用户反馈上一版修改后鼠标不再移动，说明把真实点击主后端切到 `InputDriver` 引入了新回归。
**直接变更文件：**
- `core/motion_controller.py`
- `gui/modes/navigation_mode.py`
- `tests/test_motion_controller.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：** 恢复 `pydirectinput` 为主移动/点击后端；`InputDriver` 只负责窗口聚焦、屏幕尺寸读取和失败后的兜底点击；自动导航只在启停时调整主窗口置顶状态，不再每次点击前重复下沉主窗口。

### C. SYNC 结果
**连带重读文件：** `core/motion_controller.py`、`tests/test_motion_controller.py`、`gui/modes/navigation_mode.py`。
**CODEBASE.md 更新内容：** 修正 Input Control Current Notes，明确 `pydirectinput` 是主后端，`InputDriver.click()` 只作为 fallback。
**覆盖进度更新：** `core/motion_controller.py` 的真实点击链路已恢复到已验证可移动鼠标的后端；测试改为断言 `InputDriver` 只聚焦窗口、不执行主点击。
**修订的旧结论：** 上一轮把“点击不在游戏窗口”的修复和“替换点击后端”绑定在一起是错误耦合；当前方案拆开处理：后端保持已验证可移动，窗口遮挡另行处理。

## [SYNC] 2026-05-20 - 恢复原始 pydirectinput 点击与信号警告修复

### A. SYNC 范围声明
**触发任务：** 用户反馈手动地图点击和自动寻路都不再移动鼠标，同时启动日志出现 PySide `disconnect` RuntimeWarning。
**直接变更文件：**
- `core/motion_controller.py`
- `tests/test_motion_controller.py`
- `gui/dialogs/nav_params_dialog.py`
- `ITERATION_LOG.md`

**预计连带影响：** 鼠标执行链路恢复为原始 `pydirectinput.click(x, y)`；窗口聚焦默认关闭，仅保留为可选能力；参数面板信号连接只建立一次，程序写 UI 值时用 `QSignalBlocker` 阻断信号，避免无效 disconnect 警告。

### C. SYNC 结果
**连带重读文件：** `core/motion_controller.py`、`tests/test_motion_controller.py`、`gui/dialogs/nav_params_dialog.py`。
**CODEBASE.md 更新内容：** 上一轮已记录 Input Control Current Notes；本轮以迭代日志修正：真实点击执行必须保持 `pydirectinput.click(x, y)`，不要替换为 moveTo/down/up 组合。
**覆盖进度更新：** `tests/test_motion_controller.py` 增加默认不聚焦窗口、可选聚焦窗口两个分支；`nav_params_dialog.py` 的重复 set_config_to_ui 已用 RuntimeWarning-as-error 脚本验证。
**修订的旧结论：** `pydirectinput.moveTo + mouseDown/mouseUp` 在用户环境中不能等价替代 `pydirectinput.click(x, y)`；恢复原始调用是当前稳定基线。

## [SYNC] 2026-05-20 - 运动点击确认阶段

### A. SYNC 范围声明
**触发任务：** 用户反馈鼠标能移动、图层正确，但游戏没有执行点击移动。
**直接变更文件：**
- `core/motion_controller.py`
- `tests/test_motion_controller.py`
- `ITERATION_LOG.md`

**预计连带影响：** 保留原始 `pydirectinput.click(x, y)` 作为第一阶段移动/点击，随后在当前鼠标位置补一次 `mouseDown/mouseUp` 确认点击；不改变地图到屏幕的映射算法。

### C. SYNC 结果
**连带重读文件：** `core/motion_controller.py`、`tests/test_motion_controller.py`。
**CODEBASE.md 更新内容：** 本轮以迭代日志补充：运动点击现在是两阶段，第一阶段定位到屏幕点，第二阶段确认按下/抬起。
**覆盖进度更新：** `tests/test_motion_controller.py` 覆盖默认确认点击和可选聚焦窗口两个分支。
**新发现：** 当前问题不在坐标映射，而在点击事件被游戏接收的可靠性；确认点击是最小侵入修复。
## [Investigation] 2026-05-20 - 鼠标移动/点击回归根因审查

### A. 本轮目标声明
**目标文件：**
- `core/motion_controller.py`：确认地图目标到屏幕点击的最终执行链路。
- `core/input_driver.py`：确认屏幕尺寸、窗口聚焦、Win32 点击是否影响坐标和鼠标移动。
- `gui/modes/navigation_mode.py`：确认手动地图点击和自动寻路如何触发 `MotionController`。
- `core/auto_navigator.py`：确认自动寻路是否真的发出 `issued_click=True`。
- `gui/navigation_params.py` 与地图 `config.json`：确认坐标参数、点击半径、屏幕中心是否存在逻辑/物理像素混用。
- `gui/dialogs/nav_params_dialog.py`：确认参数 UI 是否把移动参数实时写入运行时配置。

**本轮想弄清楚：**
- 为什么“原来鼠标会移动”变成“现在不移动/不点击”。
- 当前实现里是否存在 DPI 缩放、屏幕尺寸夹取、窗口下沉、自动导航状态、点击后端之间的矛盾。
- 联网核对 `pydirectinput` 和 Windows 输入/焦点的关键细节后，再给出修复方案。

### C. 本轮发现
**关键发现：** (verified) 当前进程里 `pydirectinput.size()`、`GetSystemMetrics(0/1)` 和 Qt 主屏幕逻辑尺寸均为 `1707x1067`，但 Qt `devicePixelRatio()` 为 `1.5`。这说明导航 UI/输入层看到的是逻辑坐标，截图层仍需要物理坐标。

**关键发现：** (verified/conflict) `NavigationModeWidget._on_screen_center_selected()` 把中心选择器返回的 Qt 逻辑坐标乘以 DPR 后保存到 `NavConfig.game_screen_center`，而 `MotionController._execute_click()` 又把该值直接传给 `pydirectinput.click(x, y)`。`pydirectinput` 内部用 `GetSystemMetrics()` 的逻辑尺寸把坐标归一化到 `SendInput`，因此当前链路存在“物理中心坐标传入逻辑输入 API”的坐标系冲突。

**关键发现：** (verified/conflict) `MotionController._clamp_screen_pos()` 用 `InputDriver.screen_width/screen_height` 把点击点夹到 `1707x1067` 内；但此前用户日志中已出现 `screen=(1987, 1476)` 这类超过逻辑边界的目标点。新增 clamp 会把这类点强行压到屏幕边缘，例如 `(1987,569)->(1704,569)`、`(1559,1469)->(1559,1064)`，改变原有鼠标移动轨迹。

**关键发现：** (verified) 自动寻路链路已经通过 `issued_click=True` 限制重复点击，手动地图点击和自动点击最终都调用同一个 `MotionController.move_to_map_target()`。因此“手动点击不移动”和“自动寻路不移动”的共同故障点在 `MotionController`/输入坐标层，不在 `AutoNavigator` 规划层。

**关键发现：** (verified) `pydirectinput.click(x, y)` 的实现是先 `moveTo(x,y)`，再发 `SendInput` 点击事件；`moveTo` 内部使用 `size()` 做绝对坐标归一化。后来新增的 `confirm_after_click` 只是补一次当前位置 down/up，不能修正坐标系错误；如果第一次移动位置错误，确认点击只会强化错误位置。

**修订的旧结论：** 之前把问题判断为“点击事件被游戏接收不可靠”不完整。当前更准确的结论是：先有坐标系/边界夹取回归导致移动目标错误或被夹到边缘；在此基础上再讨论窗口焦点和双击确认才有意义。

**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/motion_controller.py` | (partial) | (conflict) | 2 | 已确认 clamp、confirm、pydirectinput 坐标归一化之间存在冲突。 |
| `gui/modes/navigation_mode.py` | (partial) | (conflict) | 2 | 已确认校准中心保存为物理坐标，但点击执行使用逻辑输入 API。 |
| `gui/dialogs/nav_params_dialog.py` | (partial) | (conflict) | 1 | 自动估算点击半径当前按物理边界推导，不适合直接服务 `pydirectinput` 输入坐标。 |
| `core/input_driver.py` | (partial) | (conflict) | 1 | `GetSystemMetrics` 返回当前进程逻辑屏幕尺寸，被用于 clamp 后会改变物理/逻辑混用坐标。 |

**下一轮计划：** 修复顺序应先恢复单一坐标系和最小点击基线：`pydirectinput` 输入坐标统一使用 Qt 逻辑坐标；截图坐标继续使用物理坐标；禁用或重写 clamp/确认点击，等鼠标移动恢复后再处理游戏窗口焦点与点击接收。

## [SYNC] 2026-05-20 - 恢复鼠标移动基线并增加点击诊断

### A. SYNC 范围声明
**触发任务：** 用户要求先恢复正确鼠标移动，同时允许在点击链路打印诊断信息用于后续 debug。
**直接变更文件：**
- `core/motion_controller.py`
- `core/input_driver.py`
- `tests/test_motion_controller.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：** 默认执行链路恢复为单次 `pydirectinput.click(x, y)`，不再默认进行屏幕边界夹取和确认点击；保留可选 clamp/focus/confirm 能力；点击前后输出 pydirectinput 屏幕尺寸、鼠标位置、目标窗口信息和是否发生坐标夹取。

### C. SYNC 结果
**连带重读文件：** `core/motion_controller.py`、`core/input_driver.py`、`tests/test_motion_controller.py`。
**CODEBASE.md 更新内容：** 更新 Input Control Current Notes，明确默认移动基线是单次 `pydirectinput.click(x, y)`；clamp/focus/confirm 仅保留为显式调试开关；新增点击诊断日志说明。
**覆盖进度更新：** `core/motion_controller.py` 默认关闭 `clamp_to_screen` 和 `confirm_after_click`；`core/input_driver.py` 新增 `describe_window_at()` 输出 hwnd/pid/class/title；`tests/test_motion_controller.py` 覆盖默认不夹取、显式夹取、可选聚焦三条路径。
**验证：** `python -m py_compile core\motion_controller.py core\input_driver.py gui\modes\navigation_mode.py` 通过；`python -m unittest tests.test_route_manager tests.test_path_utils tests.test_auto_navigator tests.test_motion_controller` 通过，18 个测试成功。
**修订的旧结论：** 点击问题需要在移动基线恢复后再判断。当前代码不再默认改变目标坐标，也不默认追加第二次点击，因此下一次真实测试日志可以直接区分坐标映射问题和窗口接收问题。

## [SYNC] 2026-05-20 - 游戏窗口激活态鼠标捕获诊断

### A. SYNC 范围声明
**触发任务：** 用户日志显示目标点下方已经是 UnrealWindow，但 `cursor_after` 没有到达 `screen`，且点击切换到游戏窗口后移动/点击失效。
**直接变更文件：**
- `core/input_driver.py`
- `core/motion_controller.py`
- `tests/test_motion_controller.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：** 点击链路从 `pydirectinput.click(x, y)` 改为“Win32 `SetCursorPos` 放置鼠标 + `pydirectinput.click()` 当前点点击”；诊断日志增加前台窗口、ClipCursor 限制矩形、Win32 光标前后位置，用于判断 Unreal 激活后是否捕获/锁定鼠标。

### C. SYNC 结果
**连带重读文件：** `core/input_driver.py`、`core/motion_controller.py`、`tests/test_motion_controller.py`。
**CODEBASE.md 更新内容：** 更新 Input Control Current Notes，记录当前后端为 `setcursor+pydirectinput`，并记录新增 foreground/ClipCursor/Win32 cursor 诊断。
**覆盖进度更新：** `core/input_driver.py` 新增 `cursor_pos()`、`clip_cursor_rect()`、`foreground_window()`、`describe_window()`；`core/motion_controller.py` 先用 `InputDriver.move_to()` 放置鼠标，再用 `pydirectinput.click()` 当前点点击；`tests/test_motion_controller.py` 更新为断言 Win32 放置和当前点点击。
**验证：** `python -m py_compile core\motion_controller.py core\input_driver.py gui\modes\navigation_mode.py` 通过；`python -m unittest tests.test_route_manager tests.test_path_utils tests.test_auto_navigator tests.test_motion_controller` 通过，18 个测试成功。
**修订的旧结论：** 仅恢复单次 `pydirectinput.click(x, y)` 不足以诊断游戏激活态问题；当 UnrealWindow 成为目标/前台后，需要区分 `pydirectinput` 绝对移动失败、Win32 `SetCursorPos` 被 ClipCursor/游戏捕获改写、以及点击事件被游戏忽略三种情况。

## [SYNC] 2026-05-20 - 独立输入探针替代主流程试验

### A. SYNC 范围声明
**触发任务：** 用户指出应先用探针确认点击能真实作用到游戏，再修改项目主流程。
**直接变更文件：**
- `core/motion_controller.py`
- `core/input_driver.py`
- `tests/test_motion_controller.py`
- `utils/input_probe.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：** 主流程恢复为保守的 `pydirectinput.click(x, y)` 基线；新增 `utils/input_probe.py` 用于独立测试 `pydirectinput`、`SetCursorPos`、Win32 click、hold click 等策略。探针默认 dry-run，只有带 `--execute` 才会真实移动/点击。

### C. SYNC 结果
**连带重读文件：** `core/motion_controller.py`、`core/input_driver.py`、`utils/input_probe.py`、`tests/test_motion_controller.py`。
**CODEBASE.md 更新内容：** 修正主流程 backend 说明为 `pydirectinput.click(x, y)`；新增 Standalone Input Probe 章节。
**覆盖进度更新：** `core/motion_controller.py` 不再默认使用 `SetCursorPos`；`utils/input_probe.py` 提供 6 种可手动执行的输入策略；`core/input_driver.py` 保留窗口/ClipCursor/前台窗口诊断能力。
**验证：** `python -m py_compile core\motion_controller.py core\input_driver.py utils\input_probe.py tests\test_motion_controller.py` 通过；`python utils\input_probe.py --list-modes` 通过；`python utils\input_probe.py --x 100 --y 100` dry-run 通过；`python -m unittest tests.test_motion_controller` 通过。
**修订的旧结论：** `setcursor+pydirectinput` 不应直接进入主流程；它现在只是探针模式之一，等真实游戏验证后再决定是否集成。

## [SYNC] 2026-05-20 - 导航主程序管理员提权与 Win32 点击后端

### A. SYNC 范围声明
**触发任务：** 用户确认旧脚本必须管理员模式才可以真实点击游戏窗口，要求导航模式自动提权后执行点击。
**直接变更文件：**
- `main.py`
- `core/motion_controller.py`
- `tests/test_motion_controller.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：** 程序启动时先设置 DPI awareness；Windows 下非管理员启动会通过 UAC 重新拉起当前 Python/脚本并退出原进程；运动控制主后端切为旧脚本验证过的 Win32 `SetCursorPos + mouse_event`，`pydirectinput` 只作为失败兜底。

### C. SYNC 结果
**连带重读文件：** `main.py`、`core/motion_controller.py`、`tests/test_motion_controller.py`。
**CODEBASE.md 更新内容：** 更新外部集成和 Input Control Current Notes，记录管理员提权、DPI awareness、`win32_mouse_event` 主后端。
**覆盖进度更新：** `main.py` 新增启动前 DPI awareness 和 UAC relaunch；`core/motion_controller.py` 默认 `input_backend="win32_mouse_event"` 并调用 `InputDriver.click()`；`tests/test_motion_controller.py` 改为断言 Win32 driver click 是主路径。
**验证：** `python -m py_compile main.py core\motion_controller.py core\input_driver.py gui\modes\navigation_mode.py tests\test_motion_controller.py utils\input_probe.py` 通过；`python -m unittest tests.test_route_manager tests.test_path_utils tests.test_auto_navigator tests.test_motion_controller` 通过，18 个测试成功。
**修订的旧结论：** 主流程不再使用 `pydirectinput.click(x, y)` 作为首选真实点击；根据用户实测，管理员进程 + Win32 `mouse_event` 是当前应集成的点击基线。

## [SYNC] 2026-05-20 - A* 障碍失败时仍直接点击目标方向

### A. SYNC 范围声明
**触发任务：** 用户反馈 `[PathFinder] 起点在障碍物内` 不应阻止自动导航；游戏自身会越过/绕过障碍，只要程序持续点击正确方向即可。
**直接变更文件：**
- `core/auto_navigator.py`
- `tests/test_auto_navigator.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：** `AutoNavigator._plan_segment()` 在 A* 缺失/失败时不再进入 `FAILED`，而是构造 `[control_pos, segment_target]` 的直线路径继续 `FOLLOW_SEGMENT`；后续 `MotionController` 仍负责把直线子目标转为游戏画面点击半径。

### C. SYNC 结果
**连带重读文件：** `core/auto_navigator.py`、`tests/test_auto_navigator.py`。
**CODEBASE.md 更新内容：** 更新 `AutoNavigator.update()` 算法步骤，记录 A* 失败时直线点击引导 fallback。
**覆盖进度更新：** `core/auto_navigator.py` 的 `_plan_segment()` 不再因 `pathfinder.find_path()` 返回空而失败；`tests/test_auto_navigator.py` 新增 A* 失败时保持 active、进入 FOLLOW_SEGMENT、随后发出 move click 的覆盖。
**验证：** `python -m py_compile core\auto_navigator.py gui\modes\navigation_mode.py core\motion_controller.py main.py` 通过；`python -m unittest tests.test_route_manager tests.test_path_utils tests.test_auto_navigator tests.test_motion_controller` 通过，19 个测试成功。
**修订的旧结论：** 障碍物图层不能作为自动导航的硬失败条件；当前阶段以“持续点击正确方向”为主，A* 只作为路径辅助。

## [SYNC] 2026-05-20 - 提高自动导航点击频率并默认直线分段

### A. SYNC 范围声明
**触发任务：** 用户反馈自动导航点击频率不够快，同时窄路会被错误障碍图误判；阶段 1 应优先保证无干扰时稳定走到出口。
**直接变更文件：**
- `core/auto_navigator.py`
- `core/motion_controller.py`
- `gui/navigation_params.py`
- `gui/dialogs/nav_params_dialog.py`
- `gui/modes/navigation_mode.py`
- `tests/test_auto_navigator.py`
- `tests/test_motion_controller.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：** 自动导航默认不再调用 A* 规划，直接按当前位置到途经点/出口构造直线段；点击冷却默认从 550ms 降到 260ms，目标变化阈值从 24 降到 8；Win32 点击 hold/move delay 从 0.08/0.05 缩短为 0.05/0.02。

### C. SYNC 结果
**连带重读文件：** `core/auto_navigator.py`、`core/motion_controller.py`、`gui/navigation_params.py`、`gui/dialogs/nav_params_dialog.py`、`gui/modes/navigation_mode.py`、`tests/test_auto_navigator.py`、`tests/test_motion_controller.py`。
**CODEBASE.md 更新内容：** 更新架构图、自动导航算法、自动导航点击数据流、`NavConfig` 契约、Input Control Current Notes。
**覆盖进度更新：** `AutoNavigator.configure()` 新增运行时点击节奏配置；`AutoNavigator._plan_segment()` 默认 `prefer_direct_guidance=True` 时跳过 `PathFinder`；参数面板新增自动点击冷却和目标变化阈值控件；导航模式在配置应用/参数变化时调用 `auto_navigator.configure()`。
**验证：** `python -m py_compile core\auto_navigator.py core\motion_controller.py gui\navigation_params.py gui\dialogs\nav_params_dialog.py gui\modes\navigation_mode.py tests\test_auto_navigator.py tests\test_motion_controller.py` 通过；`python -m unittest tests.test_route_manager tests.test_path_utils tests.test_auto_navigator tests.test_motion_controller` 通过，21 个测试成功。
**修订的旧结论：** 当前慢速主要不是计算瓶颈，而是主动限频和点击执行延迟；第一阶段将障碍图从默认规划链路移除，点击频率通过配置项控制。

## [SYNC] 2026-05-20 - 底部 UI 禁点区安全回退

### A. SYNC 范围声明
**触发任务：** 用户截图指出屏幕下方技能栏/聊天区域容易被自动移动点击误触；要求不要直接改坐标参数，而是在触碰该区域时回退一点或采取遮罩方案。
**直接变更文件：**
- `core/motion_controller.py`
- `gui/navigation_params.py`
- `gui/dialogs/nav_params_dialog.py`
- `gui/modes/navigation_mode.py`
- `tests/test_motion_controller.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：** 运动控制仍先按现有比例和半径计算屏幕点击点；若最终点进入底部禁点区，则沿人物中心到目标点的方向缩短到安全线，不改变 `movement_scale_factor`、最小/最大点击半径等正常映射参数。

### C. SYNC 结果
**连带重读文件：** `core/motion_controller.py`、`gui/navigation_params.py`、`gui/dialogs/nav_params_dialog.py`、`gui/modes/navigation_mode.py`、`tests/test_motion_controller.py`。
**CODEBASE.md 更新内容：** 新增 `MotionController._apply_bottom_click_guard()` 算法说明，更新自动导航点击流和 `NavConfig.bottom_click_guard_pixels` 契约。
**覆盖进度更新：** `NavConfig` 新增 `bottom_click_guard_pixels`，参数面板新增“底部禁点区域(px)”；`NavigationModeWidget` 将该配置传入 `MotionController.set_params()`；`MotionController._execute_click()` 在 clamp 和真实点击前执行底部安全回退，并记录 `bottom_guard` 诊断信息。
**验证：** `python -m py_compile core\motion_controller.py gui\navigation_params.py gui\dialogs\nav_params_dialog.py gui\modes\navigation_mode.py tests\test_motion_controller.py` 通过；`python -m unittest tests.test_motion_controller tests.test_auto_navigator tests.test_route_manager tests.test_path_utils` 通过，22 个测试成功。
**修订的旧结论：** 底部 UI 误触不应通过缩小全局点击半径解决；它是屏幕安全区问题，应在最终点击落点层做条件性回退。

## [SYNC] 2026-05-21 - A* 规划优先并让墙体变薄

### A. SYNC 范围声明
**触发任务：** 用户指出障碍处理不应长期走直线；正确逻辑应该能沿地图通路规划，墙体可以适当变薄，人工锚点只是辅助，不应导致跨障碍直线。
**直接变更文件：**
- `core/pathfinder.py`
- `core/auto_navigator.py`
- `gui/modes/navigation_mode.py`
- `tests/test_auto_navigator.py`
- `tests/test_pathfinder.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：** 自动导航默认回到 A* 规划优先；`PathFinder` 默认先腐蚀墙体、取消安全膨胀，减少窄路被误封；`AutoNavigator` 启动后按当前位置跳过已在身后的途经点，避免从 6 附近启动却回点 1；直线点击只保留为 A* 失败兜底或显式 direct 模式。

### C. SYNC 结果
**连带重读文件：** `core/pathfinder.py`、`core/auto_navigator.py`、`gui/modes/navigation_mode.py`、`tests/test_auto_navigator.py`。
**CODEBASE.md 更新内容：** 更新 `AutoNavigator.update()` 算法、`PathFinder._build_obstacle_map()` 算法、自动导航点击数据流和 Input Control Current Notes。
**覆盖进度更新：** `PathFinder.__init__()` 新增 `safety_margin=0`、`wall_shrink_iterations=1` 默认；`PathFinder.find_path()` 改为经 `_build_obstacle_map()` 使用变薄墙图；`AutoNavigator.prefer_direct_guidance` 默认恢复为 `False`；导航模式配置应用时传入 `prefer_direct_guidance=False`；新增路线进度对齐和绕障试探点击测试；新增 `tests/test_pathfinder.py` 验证薄墙误判被消除。
**验证：** `python -m py_compile core\pathfinder.py core\auto_navigator.py gui\modes\navigation_mode.py tests\test_auto_navigator.py tests\test_pathfinder.py` 通过；`python -m unittest tests.test_pathfinder tests.test_auto_navigator tests.test_path_utils tests.test_route_manager tests.test_motion_controller` 通过，25 个测试成功。
**修订的旧结论：** “默认直线分段”只能作为短期止血；正确的一阶段策略是规划优先、墙图软化、失败才 fallback。

## [SYNC] 2026-05-21 - A* 失败 fallback 改为局部脱困点

### A. SYNC 范围声明
**触发任务：** 用户指出“直线点击”不应走向下一个目标，而应该只靠近下一个目标方向、越过当前障碍后重新规划。
**直接变更文件：**
- `core/auto_navigator.py`
- `tests/test_auto_navigator.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：** A* 失败时不再构造 `[control_pos, segment_target]` 的长直线路径；改为生成当前人物附近的短距离局部脱困点，点击后进入 `local_fallback` 路径，抵达临时点或无进展时回到 `PLAN_SEGMENT` 重新 A*。

### C. SYNC 结果
**连带重读文件：** `core/auto_navigator.py`、`tests/test_auto_navigator.py`。
**CODEBASE.md 更新内容：** 更新 `AutoNavigator.update()` 算法步骤，新增 `_set_local_fallback_path()` 说明，并修正自动导航点击数据流和 Input Control Current Notes。
**覆盖进度更新：** `AutoNavigator` 新增 `direct_fallback_distance`、`direct_fallback_side_distance`、`current_path_kind`、`direct_fallback_attempts`；`_plan_segment()` 在 A* 失败时调用 `_set_local_fallback_path()`；`_follow_segment()` 对 `local_fallback` 到达/无进展后重新规划；`tests/test_auto_navigator.py` 验证 fallback 终点不是 segment target，且到达临时点后回到 PLAN_SEGMENT。
**验证：** `python -m py_compile core\auto_navigator.py tests\test_auto_navigator.py` 通过；`python -m unittest tests.test_auto_navigator tests.test_pathfinder tests.test_path_utils tests.test_route_manager tests.test_motion_controller` 通过，25 个测试成功。
**修订的旧结论：** “A* 失败后直线到下一目标”仍可能穿墙卡住；fallback 的职责只应是局部脱困，不应替代全局路径规划。

## [SYNC] 2026-05-21 - A* 禁止穿过未探索黑区

### A. SYNC 范围声明
**触发任务：** 用户截图显示黄色规划线穿过地图外/未探索黑区，说明 A* 把没有墙像素的未知区域当成可走区域。
**直接变更文件：**
- `core/pathfinder.py`
- `core/auto_navigator.py`
- `gui/modes/navigation_mode.py`
- `tests/test_pathfinder.py`
- `tests/test_auto_navigator.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：** `PathFinder` 不再只看 `wall_layer`，而是把 `explored_map==0` 当作不可走区域；`NavigationModeWidget.navigation_loop()` 将 `nav_core.explored_map` 传给自动导航；自动导航规划路径不再用只看墙图的 shortcut 平滑，避免后处理把路径重新拉直穿过未知区域。

### C. SYNC 结果
**连带重读文件：** `core/pathfinder.py`、`core/auto_navigator.py`、`gui/modes/navigation_mode.py`、`tests/test_pathfinder.py`。
**CODEBASE.md 更新内容：** 更新 `PathFinder` 职责、`_build_obstacle_map()` 算法、`AutoNavigator.update()` 算法和自动导航点击数据流。
**覆盖进度更新：** `PathFinder.find_path()` 新增 `explored_map=None` 参数；`_build_obstacle_map()` 将未知区域并入障碍图；`AutoNavigator.update()` 新增 `explored_map` 参数并传给 `_plan_segment()`；规划路径后处理从 `smooth_path(wall_map, raw_path)` 改为 `remove_collinear_points(raw_path)`，避免只基于墙图跨 unknown 捷径；新增 pathfinder 测试验证未知区域不可走。
**验证：** `python -m py_compile core\pathfinder.py core\auto_navigator.py gui\modes\navigation_mode.py tests\test_pathfinder.py tests\test_auto_navigator.py` 通过；`python -m unittest tests.test_pathfinder tests.test_auto_navigator tests.test_path_utils tests.test_route_manager tests.test_motion_controller` 通过，26 个测试成功。
**修订的旧结论：** “墙体变薄”只解决窄路误封；A* 的可走域必须由 `explored_map` 限定，否则地图外黑区会被误判为空地。

## [SYNC] 2026-05-21 - 自动导航按最近标记点接入路线

### A. SYNC 范围声明
**触发任务：** 用户指出自动移动时应该追寻最近的标记点并继续往终点走，而不是每次都从第一个标记点开始。
**直接变更文件：**
- `core/auto_navigator.py`
- `tests/test_auto_navigator.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：** 自动导航启动或重定位后的第一次规划会在 `guide_points + exit` 中选择离当前位置最近的标记作为当前目标；如果已经贴近该标记，则直接推进到下一个标记。之后仍按路线顺序往出口走。

### C. SYNC 结果
**连带重读文件：** `core/auto_navigator.py`、`tests/test_auto_navigator.py`。
**CODEBASE.md 更新内容：** 更新 `AutoNavigator.update()` 算法步骤，并新增 `_align_route_to_current_position()` 算法说明。
**覆盖进度更新：** `_align_route_to_current_position()` 从线段投影对齐改为最近标记点对齐；新增 `route_marker_arrival_factor` 控制贴近标记时是否跳到下一个；删除未使用的旧线段投影对齐函数；新增测试覆盖“远离路线线段但最近某个标记”和“已经贴近某标记应追踪下一个标记”。
**验证：** `python -m py_compile core\auto_navigator.py tests\test_auto_navigator.py` 通过；`python -m unittest tests.test_auto_navigator tests.test_pathfinder tests.test_path_utils tests.test_route_manager tests.test_motion_controller` 通过，28 个测试成功。
**修订的旧结论：** 自动导航的路线接入不应依赖“起点是第一个标记”的假设；应从当前定位动态接入最近的路线标记，再沿标记序列向出口推进。

## [SYNC] 2026-05-21 - 路线附近按线段方向接入下一标记

### A. SYNC 范围声明
**触发任务：** 继续完善最近标记点逻辑，避免人在两个标记之间时因为离上一个点更近而回头。
**直接变更文件：**
- `core/auto_navigator.py`
- `tests/test_auto_navigator.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：** 自动导航启动时如果当前位置贴近某条路线段，会接入该线段并追踪下一个标记；只有偏离路线较远时才单纯按最近标记点接入。

### C. SYNC 结果
**连带重读文件：** `core/auto_navigator.py`、`tests/test_auto_navigator.py`。
**CODEBASE.md 更新内容：** 更新 `_align_route_to_current_position()` 算法说明，新增 `_candidate_index_from_nearest_route_segment()` 说明。
**覆盖进度更新：** `_align_route_to_current_position()` 现在先计算最近标记，再用路线段投影覆盖候选目标；新增测试验证人在第 1 和第 2 标记之间且更靠近第 1 标记时，仍追踪第 2 标记。
**验证：** `python -m py_compile core\auto_navigator.py tests\test_auto_navigator.py` 通过；`python -m unittest tests.test_auto_navigator tests.test_pathfinder tests.test_path_utils tests.test_route_manager tests.test_motion_controller` 通过，29 个测试成功。
**修订的旧结论：** “最近标记点”不能机械地选欧氏距离最近点；在路线附近时应按路线方向追下一个标记，才能保证持续往出口走。

## [SYNC] 2026-05-21 - 新增严格顺序的必经点

### A. SYNC 范围声明
**触发任务：** 用户要求把路线点拆成两种机制：`required_points` 必须按顺序先完成，`guide_points` 作为普通辅助点；并且完成过的必经点不能被再次追踪。
**直接变更文件：**
- `core/auto_navigator.py`
- `gui/modes/navigation_mode.py`
- `tests/test_auto_navigator.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：** 自动导航在存在未完成 `required_points` 时，不再执行“最近路线点接入”来跳过它们；地图编辑 UI 新增“添加/撤销必经点”；路线覆盖层用独立颜色和 `R1/R2/...` 标签区分必经点与普通途经点。

### C. SYNC 结果
**连带重读文件：** `core/auto_navigator.py`、`gui/modes/navigation_mode.py`、`tests/test_auto_navigator.py`、`core/route_manager.py`。
**CODEBASE.md 更新内容：** 更新项目概览、`NavigationModeWidget`/`RouteManager`/`AutoNavigator` 模块职责，并修正 `AutoNavigator.update()`、`_align_route_to_current_position()` 的算法描述。
**覆盖进度更新：** `AutoNavigator` 新增 `required_index`、`required_points()`、`has_pending_required_points()`；`current_segment_target()` 和 `_advance_segment()` 现在先处理必经点，再处理普通途经点/出口；`navigation_mode.py` 新增必经点编辑按钮、点击模式和紫色 `R*` 覆盖层标记；新增测试覆盖“必经点优先”“必经点不可被路线接入跳过”“完成必经点后恢复 guide 对齐”。
**验证：** `python -m py_compile core\route_manager.py core\auto_navigator.py gui\modes\navigation_mode.py tests\test_route_manager.py tests\test_auto_navigator.py` 通过；`python -m unittest tests.test_route_manager tests.test_auto_navigator tests.test_pathfinder tests.test_path_utils tests.test_motion_controller` 通过，34 个测试成功。
**修订的旧结论：** 之前把所有路线点都放进同一套“最近路线点接入”逻辑，会导致严格 checkpoint 被自动跳过；必经点必须在状态机层与普通途经点分治。

## [SYNC] 2026-05-21 - 禁止 A* 斜向穿角

### A. SYNC 范围声明
**触发任务：** 用户反馈自动导航会进入地图禁区。排查后确认 `PathFinder` 的 8 方向 A* 允许从两个障碍角之间斜着挤过去，这会制造“明明有墙但路径还是穿进去”的假象。
**直接变更文件：**
- `core/pathfinder.py`
- `tests/test_pathfinder.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：** A* 仍然保留 8 方向移动，但任何对角步在执行前都必须检查两侧正交邻格；只要有一侧是障碍，就禁止该对角步，避免 corner cutting。

### C. SYNC 结果
**连带重读文件：** `core/pathfinder.py`、`core/stitcher_core.py`、`tests/test_pathfinder.py`。
**CODEBASE.md 更新内容：** 新增 `PathFinder._astar()` 关于“禁止斜穿角”的算法说明。
**覆盖进度更新：** `tests/test_pathfinder.py` 新增 corner-cutting 回归测试，确保 `(1,1) -> (2,2)` 不会在两侧有障碍时斜穿过去。
**验证：** `python -m py_compile core\pathfinder.py tests\test_pathfinder.py` 通过；`python -m unittest tests.test_pathfinder tests.test_auto_navigator tests.test_path_utils tests.test_route_manager tests.test_motion_controller` 通过，35 个测试成功。
**修订的旧结论：** “导航进禁区”不一定全是墙体识别失败；A* 本身如果允许斜穿角，也会把合法障碍图走穿。

## [SYNC] 2026-05-21 - 绘图地图去灰块并显式渲染地面/禁区候选层

### A. SYNC 范围声明
**触发任务：** 用户反馈绘图模式里的全局地图不够清晰，墙体容易粘连，且游戏小地图中的蓝色地面/禁区信息没有被显式呈现。
**直接变更文件：**
- `core/stitcher_core.py`
- `core/navigation_core.py`
- `core/recognizer_optimized.py`
- `gui/modes/mapping_widget.py`
- `gui/widgets/scalable_map.py`
- `tests/test_stitcher_core.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：** 建图阶段不再优先把整块截图矩形写入 `explored_map`；若当前帧能提取出足够大的 `fog_mask`，则用其作为精确可见区域并同时维护 `fog_layer`。绘图模式和导航模式的全局地图显示都会新增蓝色地面/禁区候选层；地图缩放改为像素级显示，避免细线被平滑插值抹掉。

### C. SYNC 结果
**连带重读文件：** `core/stitcher_core.py`、`core/navigation_core.py`、`core/recognizer_optimized.py`、`gui/modes/mapping_widget.py`、`gui/widgets/scalable_map.py`。
**CODEBASE.md 更新内容：** 新增 `MapStitcher._merge_frame_weighted()`、`MapStitcher.get_enhanced_map()` 说明，并更新 `NavigationCore` 的地图显示职责。
**覆盖进度更新：** `MapStitcher` 新增 `use_precise_visibility_mask` / `precise_visibility_min_pixels`，开始真正维护 `fog_layer`；`mapping_widget.py` 的路径预览现在也会把 `explored_map` 传给 `PathFinder`；`ScalableMapWidget` 改成 `Qt.FastTransformation`；透明地图模式的墙体闭运算从 `kernel_medium` 收紧到 `kernel_small`，降低细墙粘连。
**验证：** `python -m py_compile core\stitcher_core.py core\navigation_core.py core\recognizer_optimized.py gui\modes\mapping_widget.py gui\widgets\scalable_map.py tests\test_stitcher_core.py` 通过；`python -m unittest tests.test_stitcher_core tests.test_pathfinder tests.test_auto_navigator tests.test_path_utils tests.test_route_manager tests.test_motion_controller` 通过，37 个测试成功。
**修订的旧结论：** 地图发糊的主因不是单纯 `draw_scale` 太小，而是旧逻辑把整块监视窗口都刷成 explored，再叠加平滑缩放显示，最终看起来像“大灰块 + 粗墙体”。

## [SYNC] 2026-05-21 - 隐藏蓝色地面层渲染

### A. SYNC 范围声明
**触发任务：** 用户确认地图绘制效果已改善，但不希望全局图显示蓝色背景层。
**直接变更文件：**
- `core/stitcher_core.py`
- `core/navigation_core.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：** `fog_layer` 继续在地图包内维护，用于后续禁区/地面分析，但绘图模式和导航模式的地图 UI 恢复为黑底/灰区/白墙，不再额外铺蓝色。

### C. SYNC 结果
**连带重读文件：** `core/stitcher_core.py`、`core/navigation_core.py`。
**CODEBASE.md 更新内容：** 修正 `NavigationCore` 和 `MapStitcher.get_enhanced_map()` 的显示说明，明确 `fog_layer` 默认不直接渲染。
**覆盖进度更新：** 仅调整显示层，不改内部 `fog_layer` 数据结构与持久化逻辑。
**验证：** `python -m py_compile core\stitcher_core.py core\navigation_core.py` 通过；`python -m unittest tests.test_stitcher_core tests.test_pathfinder tests.test_auto_navigator tests.test_path_utils tests.test_route_manager tests.test_motion_controller` 通过，37 个测试成功。

## [SYNC] 2026-05-21 - 降低事件/Boss 图标对导航定位的干扰

### A. SYNC 范围声明
**触发任务：** 用户明确说明受影响的是“游戏截图监控时，小地图里的额外事件/Boss 图标”，这些动态图标会污染导航定位与地图匹配。
**直接变更文件：**
- `core/recognizer_optimized.py`
- `core/navigation_core.py`
- `tests/test_recognizer_optimized.py`
- `tests/test_navigation_core.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：** `extract_combined()` 不再只把高饱和度彩色图标从 `wall_mask` 中剔除，而是同步从 `edges` 和 `fog_mask` 中剔除，并对该彩色区域做一次小核膨胀，连同轮廓一起去掉。导航时的 F2F 跟踪不再优先吃混合 `match_mask`，改为优先跟踪更稳定的 `wall_mask`，同时拒绝异常大的帧间位移并回退模板匹配。

### C. SYNC 结果
**连带重读文件：** `core/recognizer_optimized.py`、`core/navigation_core.py`。
**CODEBASE.md 更新内容：** 补充 `NavigationCore` 关于 F2F 跟踪策略的说明，并新增 `HSVRecognizer.extract_combined()` 的动态特效抑制算法描述。
**覆盖进度更新：** `Recognizer` 现在会把彩色动态图标和人物中心近身特效从 `wall_mask`/`edges`/`fog_mask` 同步剔除；`NavigationCore` 新增 `prev_wall_mask`，F2F 使用 `wall_mask` 估位移，降低战斗场景下 `edges` 污染带来的漂移。
**验证：** `python -m py_compile core\recognizer_optimized.py core\navigation_core.py tests\test_recognizer_optimized.py tests\test_navigation_core.py` 通过；`python -m unittest tests.test_recognizer_optimized tests.test_navigation_core tests.test_stitcher_core tests.test_pathfinder tests.test_auto_navigator tests.test_path_utils tests.test_route_manager tests.test_motion_controller` 通过，39 个测试成功。

## [SYNC] 2026-05-22 - 必经点改为路线阶段门而非直接目标覆盖

### A. SYNC 范围声明
**触发任务：** 用户指出经过第一个必经点后，系统会直接直线指向第二个必经点，忽略中间普通标记点和路线走廊，导致路线逻辑错误。
**直接变更文件：**
- `core/auto_navigator.py`
- `gui/modes/navigation_mode.py`
- `tests/test_auto_navigator.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：** 自动导航不再把未完成必经点无条件作为当前段目标；普通标记点继续承担路线骨架和 A* 分段目标，必经点只作为按路线进度触发的阶段门。覆盖层根据 `target_kind` 高亮真正当前目标，避免 UI 看起来仍然直指下一个必经点。

### C. SYNC 结果
**连带重读文件：** `core/auto_navigator.py`、`gui/modes/navigation_mode.py`、`tests/test_auto_navigator.py`。
**CODEBASE.md 更新内容：** 修正 `AutoNavigator` 与 `NavigationModeWidget` 的路线点语义，新增 `_select_segment_target()` 算法说明，并更新 `_align_route_to_current_position()` 不越过当前必经点进度的描述。
**覆盖进度更新：** `AutoNavigator` 新增 `current_target_kind`、`current_segment_target_kind()`、`_select_segment_target()`、`_route_progress_for_point()`、`_guide_index_limit_for_current_required()`；`_advance_segment()` 改为按当前目标类型推进，普通点到达不会误推进 `required_index`；`_align_route_to_current_position()` 允许在必经点前接入普通路线，但会截断到当前必经点之前；`NavigationModeWidget._render_route_overlay()` 使用 `target_kind` 高亮当前目标。
**验证：** `python -m py_compile core\auto_navigator.py gui\modes\navigation_mode.py tests\test_auto_navigator.py` 通过；`python -m unittest tests.test_recognizer_optimized tests.test_navigation_core tests.test_stitcher_core tests.test_pathfinder tests.test_auto_navigator tests.test_path_utils tests.test_route_manager tests.test_motion_controller` 通过，42 个测试成功。
**修订的旧结论：** “存在未完成必经点时应直接追当前必经点”会破坏路线骨架；正确语义是 `guide_points` 决定可行走路线形状，`required_points` 决定必须按顺序经过的阶段门。

## [SYNC] 2026-05-22 - 事件系统设计和传送门图标探针

### A. SYNC 范围声明
**触发任务：** 用户要求事件功能先做可行性验证，重点确认能否从游戏小地图中识别传送门事件图标，并保持后续事件类型模块化扩展。
**直接变更文件：**
- `docs/plans/2026-05-22-event-system-design.md`
- `utils/event_icon_probe.py`
- `assets/event_templates/portal/minimap/portal_minimap_01.png`
- `assets/event_templates/portal/minimap/portal_minimap_02.png`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：** 事件识别暂不接入导航主循环；当前只新增设计文档和独立探针。后续正式接入时应从 raw minimap frame 分层识别事件，而不是复用已做动态抑制的定位特征图。

### C. SYNC 结果
**连带重读文件：** `docs/plans/2026-05-22-event-system-design.md`、`utils/event_icon_probe.py`、`core/capture.py`。
**CODEBASE.md 更新内容：** 新增事件图标探针的目录职责、模块说明、`match_template()` / `merge_hits()` / `main()` 算法说明、事件探针数据流和外部集成注意事项。
**覆盖进度更新：** 事件系统设计确认 `EventMonitor` / `EventDetector` / `EventMemory` / `EventScheduler` / `EventHandler` / `EventConfig` 模块边界；传送门 v1 使用 raw minimap 多模板匹配作为第一阶段识别方式；`event_icon_probe.py` 支持可重复 `--template`，跨模板候选按中心距离去重，并在无 accepted hit 时输出每个模板的最佳候选用于诊断；已把可复用传送门模板移入 `assets/event_templates/portal/minimap/`。
**验证：** `D:\ACloud\.venv\Scripts\python.exe -m py_compile utils\event_icon_probe.py` 通过；管理员权限运行资产模板探针通过，`portal_minimap_01` 得分 `0.9652`、中心 `(45,61)`，`portal_minimap_02` 得分 `0.9172`、中心 `(68,87)`。
**修订的旧结论：** “识别传送门需要先训练 YOLO”不是第一阶段必要条件；当前小地图图标是固定 UI 小图标，多模板匹配已经足够支撑第一版事件发现探针。

## [SYNC] 2026-05-22 - 大画面传送门实体识别探针

### A. SYNC 范围声明
**触发任务：** 用户明确要求大地图/游戏屏幕也做一次探针，先验证能否识别整个游戏界面中的传送门实体，验证可行后只保存为技术资产，暂不接入事件架构。
**直接变更文件：**
- `utils/portal_screen_probe.py`
- `assets/event_detectors/portal/main_view/blue_glow_detector_v1.json`
- `assets/event_detectors/portal/main_view/README.md`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：** 当前不修改导航、事件主循环或点击逻辑；新增大画面二阶段确认探针。后续事件系统可在小地图传送门图标确认后，再用该主画面探针确认真实传送门实体是否在可点击视野内。

### C. SYNC 结果
**连带重读文件：** `utils/portal_screen_probe.py`、`core/capture.py`、`assets/event_detectors/portal/main_view/README.md`。
**CODEBASE.md 更新内容：** 新增大画面探针的目录职责、模块说明、`build_blue_glow_mask()` / `detect_portal_candidates()` / `is_strict_portal_candidate()` 算法说明、主画面探针数据流和风险登记。
**覆盖进度更新：** `portal_screen_probe.py` 支持枚举 `UnrealWindow` / `Torchlight` 游戏窗口、`--rect`、`--full-screen`、`--params` 参数资产；检测策略为 HSV 蓝/青/紫发光 mask + 轮廓面积/发光占比/圆度/宽高比评分 + 严格 accepted 过滤。`blue_glow_detector_v1.json` 固化当前阈值，README 记录复现命令和预期行为。
**验证：** `D:\ACloud\.venv\Scripts\python.exe -m py_compile utils\portal_screen_probe.py` 通过；管理员权限 `run_02` 中真实大传送门被唯一 accepted，得分 `0.9962`，screen center `(774,501)`，bbox `202x207`；后续 `--params` 复现时传送门已离开/被遮挡，输出 0 accepted，符合“实体不可见时不确认”的预期。
**修订的旧结论：** 大画面传送门不需要先训练 YOLO 才能验证可行性；在当前画面中，颜色+几何二阶段确认足以稳定识别可见的大传送门，但正式接入时必须受小地图事件发现约束，不能全图无条件触发。

## [SYNC] 2026-05-22 - 事件系统架构设计和实现计划

### A. SYNC 范围声明
**触发任务：** 用户审核确认采用完整事件包架构，TUI 只展示完整事件；需要先输出代码结构架构设计和可执行实现计划。
**直接变更文件：**
- `docs/plans/2026-05-22-event-system-architecture-design.md`
- `docs/plans/2026-05-22-event-system-implementation-plan.md`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：** 当前仅新增设计和计划文档，不修改运行代码。后续实现应按计划从 core event contracts 开始，逐步接入 portal 事件，不直接把 portal 逻辑写入 `NavigationModeWidget`。

### C. SYNC 结果
**连带重读文件：** `docs/plans/2026-05-22-event-system-design.md`、`docs/plans/2026-05-22-event-system-architecture-design.md`、`docs/plans/2026-05-22-event-system-implementation-plan.md`。
**CODEBASE.md 更新内容：** 补充两个事件系统文档的目录职责说明。
**覆盖进度更新：** 架构设计明确 `EventDefinition` 是事件包唯一外部入口，TUI 只展示 `portal` 等完整事件；实现计划拆成 7 个阶段 22 个 TDD 任务，覆盖核心模型、配置、memory、portal 检测/确认/handler、coordinator、导航接入、overlay 和 TUI options。
**验证：** 已确认两个计划文件存在并可读取；本次未修改运行代码，无需执行业务测试。
**修订的旧结论：** 事件系统不能只停留在“功能方案”；需要先固定代码结构和协议边界，避免后续把 detector/confirmer/handler 暴露给 TUI 或耦合进导航循环。

## [SYNC] 2026-05-22 - 实现事件系统核心和 portal 事件包

### A. SYNC 范围声明
**触发任务：** 用户要求不要继续规划，直接按 codebase skill 执行开发；同时不要浪费时间跑逻辑测试，只做启动/编译级检查，实际游戏行为由用户测试。
**直接变更文件：**
- `core/events/**`
- `core/motion_controller.py`
- `gui/modes/navigation_mode.py`
- `utils/event_icon_probe.py`
- `utils/portal_screen_probe.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：** 导航模式加载地图时初始化事件系统，导航循环在自动导航开启时允许事件动作优先于普通 auto move。`portal` 事件可从小地图 raw frame 识别传送门图标，靠近后用主画面 confirmer 二阶段确认并返回点击动作。

### C. SYNC 结果
**连带重读文件：** `gui/modes/navigation_mode.py`、`core/motion_controller.py`、`utils/event_icon_probe.py`、`utils/portal_screen_probe.py`。
**CODEBASE.md 更新内容：** 新增 `core/events` 核心模块、`portal` 事件包、探针复用核心算法、导航接入点和 `MotionController.click_screen_position()` 说明。
**覆盖进度更新：** 新增事件模型、配置、注册表、memory、monitor、scheduler、runner、coordinator、capture provider、action executor、overlay model、window finder；新增 `PortalEventDefinition`、小地图模板 detector、主画面蓝紫发光 confirmer、portal handler；探针脚本改为复用核心 matcher/confirmer；`NavigationModeWidget` 每帧构造 `EventTick` 并在自动导航开启时执行事件动作。
**验证：** 按用户要求未运行逻辑单测；执行 `D:\ACloud\.venv\Scripts\python.exe -m compileall -q core\events gui\modes\navigation_mode.py core\motion_controller.py utils\event_icon_probe.py utils\portal_screen_probe.py main.py` 通过。清理了 `core/events` 下编译产生的 `__pycache__`。
**当前限制：** 第一版事件动作只在自动导航开启时接管；portal handler 点击/按键后用保守等待完成，不做真实场景切换确认；未新增 GUI/TUI 配置页，只提供 `event_config.json` 和 TUI options 数据模型。
**修订的旧结论：** 探针不应长期保留独立算法实现；现在运行时 detector/confirmer 与探针共用核心代码，后续调参不会出现两套逻辑漂移。

## [SYNC] 2026-05-23 - Add event runtime logs
### A. SYNC scope
**Trigger:** User needs visible logs to test event detection and execution.
**Direct files expected:** core/events/debug.py, core/events/memory.py, core/events/runner.py, core/events/coordinator.py, core/events/types/portal/handler.py, core/events/types/portal/minimap_detector.py, core/events/types/portal/main_view_confirmer.py, core/events/action_executor.py, gui/modes/navigation_mode.py, CODEBASE.md, ITERATION_LOG.md.
**Impact:** Event detection, task lifecycle, scheduler/runner actions, portal confirmation, event action execution, and navigation status text become observable without running logic tests.

### C. SYNC result
**Files changed:** `core/events/debug.py`, `core/events/memory.py`, `core/events/runner.py`, `core/events/coordinator.py`, `core/events/monitor.py`, `core/events/action_executor.py`, `core/events/types/portal/handler.py`, `core/events/types/portal/minimap_detector.py`, `core/events/types/portal/main_view_confirmer.py`, `gui/modes/navigation_mode.py`, `CODEBASE.md`, `ITERATION_LOG.md`.

**Runtime visibility added:** Event logs now cover detector initialization, minimap observations, task creation/confirmation, scheduler selection, runner action output, executor callbacks, portal move/confirm/click/wait/complete/timeout phases, and navigation status-bar event summary.

**Behavior guard:** Event detection/memory still runs during normal navigation, but event handlers only advance when `auto_navigation_enabled` is true via `EventCoordinator.update(..., run_handlers=...)`. This prevents logs from reporting handler completion when actual event movement/click execution is disabled.

**Verification:** `D:\ACloud\.venv\Scripts\python.exe -m compileall -q core\events gui\modes\navigation_mode.py core\motion_controller.py utils\event_icon_probe.py utils\portal_screen_probe.py main.py` passed. No logic/unit tests were run per user instruction.

**CODEBASE.md updated:** Added Event Runtime Diagnostics section documenting the shared event logger and live-game testing output chain.


## [SYNC] 2026-05-23 - Event manager UI and map markers
### A. SYNC scope
**Trigger:** User approved independent event-management UI plus visible map markers for event detection/trigger status.
**Direct files expected:** gui/dialogs/event_manager_dialog.py, gui/modes/navigation_mode.py, core/events/config.py if needed, CODEBASE.md, ITERATION_LOG.md.
**Impact:** Event enablement and runtime task state become visible in UI; detected event tasks are drawn on the navigation map.

## [SYNC] 2026-05-23 事件管理 UI 与地图标记收口

### A. SYNC 范围声明
**触发任务：** 为事件系统补齐独立 UI 管理窗口、可见事件触发状态、地图事件标记与事件配置保存。
**直接变更文件：**
- `gui/dialogs/event_manager_dialog.py`
- `gui/modes/navigation_mode.py`
- `core/events/coordinator.py`

**预计连带影响：**
- `core/events/config.py`：事件选配模型与保存格式。
- `core/events/overlay_models.py`：地图事件标记的展示模型。
- `core/events/models.py`：事件任务状态、动作类型在 UI 中展示。

### C. SYNC 结果
**连带重读文件：** `core/events/config.py`、`core/events/overlay_models.py`、`core/events/models.py`、`core/events/scheduler.py`、`core/events/action_executor.py`、`core/events/capture_provider.py`、`core/motion_controller.py`。

**CODEBASE.md 更新内容：** 补充 `gui/dialogs/event_manager_dialog.py` 目录职责和模块说明；更新事件管理 UI/地图 marker 数据流；补充 `MotionController.press_key()`、`NavigationModeWidget._render_event_overlay()`、`EventManagerDialog.refresh()` 的函数说明；新增 Event Manager UI 运行说明。

**覆盖进度更新：** `EventManagerDialog` 现在作为独立非模态窗口，展示完整事件选配、任务状态和保存入口；`NavigationModeWidget` 增加“事件管理”按钮、事件 marker 绘制、event config 保存和事件按键执行回调；`EventCoordinator` 在全局禁用或单事件禁用时过滤调度、状态摘要和 overlay；`MotionController` 增加事件按键 `press_key()` 通道。

**验证：** 按用户要求未运行逻辑/单元测试；执行 `D:\ACloud\.venv\Scripts\python.exe -m compileall -q core\events gui\dialogs\event_manager_dialog.py gui\modes\navigation_mode.py core\motion_controller.py utils\event_icon_probe.py utils\portal_screen_probe.py main.py` 通过；执行 `D:\ACloud\.venv\Scripts\python.exe -c "from gui.dialogs.event_manager_dialog import EventManagerDialog; from gui.modes.navigation_mode import NavigationModeWidget; print('import ok')"` 通过。

**修订的旧结论：** 只靠控制台日志不够支持用户现场测试事件触发；现在事件检测结果同时进入独立 UI 窗口和地图 marker，控制台日志只作为诊断补充。
## [SYNC] 2026-05-23 传送门按键交互与防反复传送

### A. SYNC 范围声明
**触发任务：** 用户反馈传送门应在小地图识别后跑到附近按 D，并且传送门成对靠近时不能来回反复触发；当前实际存在不会按 D 和反复识别传送的问题。
**直接变更文件：**
- `core/events/config.py`
- `core/events/types/portal/config.py`
- `core/events/types/portal/handler.py`
- `core/events/memory.py`
- `gui/modes/navigation_mode.py`
- `map_data/A1/event_config.json`

**预计连带影响：**
- `core/events/models.py`：EventTick 可携带定位失败后的 raw minimap frame。
- `core/motion_controller.py`：事件按键执行通道继续复用 `press_key()`。
- `CODEBASE.md`：同步传送门事件新完成判定和冷却半径。

### C. SYNC 结果
**连带重读文件：** `core/events/config.py`、`core/events/types/portal/config.py`、`core/events/types/portal/handler.py`、`core/events/memory.py`、`core/events/runner.py`、`gui/modes/navigation_mode.py`、`core/motion_controller.py`、`map_data/A1/event_config.json`。

**CODEBASE.md 更新内容：** 更新 portal 默认交互为按 `D`；补充传送完成判定、冷却半径、同类型短冷却和附近 pending 任务抑制说明；新增 Portal Event Current Behavior。

**覆盖进度更新：** `PortalEventConfig` 默认 `interaction="key"`，并新增 `cooldown_radius/type_cooldown_ms/post_interact_wait_ms/teleport_timeout_ms/teleport_min_distance/environment_change_threshold`；`PortalEventHandler` 在 key 模式下到达附近直接按 D，随后用位置变化或小地图环境签名变化判断传送完成；`EventMemory` 支持完成后更大半径冷却和同类型短全局冷却；`EventRunner` 完成任务后忽略附近已存在的同类任务；A1 地图事件配置已改为 key。

**验证：** 按用户要求未运行逻辑/单元测试；执行 `D:\ACloud\.venv\Scripts\python.exe -m compileall -q core\events gui\dialogs\event_manager_dialog.py gui\modes\navigation_mode.py core\motion_controller.py utils\event_icon_probe.py utils\portal_screen_probe.py main.py` 通过；执行导入检查输出 `key` 和 `import ok`。

**修订的旧结论：** 传送门默认不应该依赖主画面确认后点击；用户当前目标是“跑到小地图识别的传送门附近按 D”。主画面确认保留给 click 模式，但 key 模式直接按键更符合游戏交互。
## [SYNC] 2026-05-23 传送门小地图误识别定位修正

### A. SYNC 范围声明
**触发任务：** 用户截图显示地图上识别出多个传送门 marker，但实际小地图只有两个固定蓝色传送门图标；需要先解决传送门定位错误。
**直接变更文件：**
- `core/events/config.py`
- `core/events/types/portal/config.py`
- `core/events/types/portal/minimap_detector.py`
- `map_data/A1/event_config.json`

**预计连带影响：**
- `CODEBASE.md`：同步 portal 小地图检测从纯模板匹配改为模板+颜色校验。
- 事件 UI/地图 marker：候选数量会从最多 8 个收敛到最多 2 个。

### C. SYNC 结果
**连带重读文件：** `core/events/detectors/template_matcher.py`、`core/events/types/portal/assets.py`、`core/events/projector.py`。

**CODEBASE.md 更新内容：** 更新 portal 小地图 detector 说明：传送门检测不再只依赖灰度/边缘模板匹配，而是模板命中后增加蓝/青图标颜色校验；补充 `max_candidates` 和 `min_blue_ratio` 配置字段。

**覆盖进度更新：** 根因确认为 `PortalMinimapDetector` 之前以灰度/边缘匹配为主，`top_k=8` 且阈值 0.60，容易把白色墙线和圆形地形误识别为传送门；不是 `minimap_local_to_global()` 投影公式本身造成。现改为默认阈值 0.74、单帧最多接受 2 个候选、候选 bbox 周围必须有足够蓝/青像素，且 detector 每帧使用最新 config。

**验证：** `D:\ACloud\.venv\Scripts\python.exe -m compileall -q core\events gui\dialogs\event_manager_dialog.py gui\modes\navigation_mode.py core\motion_controller.py utils\event_icon_probe.py utils\portal_screen_probe.py main.py` 通过；导入检查输出默认 `0.74 2 0.08` 和 `import ok`。未运行逻辑/单元测试，等待用户实测。

**修订的旧结论：** 传送门位置偏差不是优先从全局坐标投影修正；更直接的根因是 detector 产生了过多错误 local hit，投影只是把这些错误 local hit 映射到了地图上。

## [SYNC] 2026-05-23 - Event localization through wall registration
### A. SYNC scope
**Trigger:** User approved scheme B: every event should be detection -> localization -> trigger -> execution -> completion, and portal global position must come from wall registration plus multi-frame stabilization instead of the old single-frame offset projector.

**Direct files changed:**
- `docs/plans/2026-05-23-event-localization-stabilizer-design.md`
- `core/navigation_core.py`
- `core/events/models.py`
- `core/events/position_stabilizer.py`
- `core/events/coordinator.py`
- `core/events/memory.py`
- `core/events/config.py`
- `core/events/types/portal/minimap_detector.py`
- `core/events/types/portal/config.py`
- `core/events/types/portal/definition.py`
- `gui/modes/navigation_mode.py`
- `gui/dialogs/event_manager_dialog.py`
- `map_data/A1/event_config.json`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**Removed files:**
- `core/events/projector.py`

**Expected impact:** Portal detector now reports only local minimap icon candidates. `NavigationCore` exposes per-frame registration data. `EventPositionStabilizer` projects detections through that registration and only emits stable global observations after multi-frame clustering, so map markers/tasks should no longer be created from one bad local hit.

### C. SYNC result
**Carryover files reviewed:** `core/events/models.py`, `core/events/coordinator.py`, `core/events/memory.py`, `core/events/types/portal/minimap_detector.py`, `core/navigation_core.py`, `gui/modes/navigation_mode.py`.

**CODEBASE.md updated:** Replaced the old `projector.py` directory entry with `position_stabilizer.py`, added `FrameRegistration` and `EventDetection` to the event contracts, corrected portal current behavior, and added an Event Localization Contract section.

**Coverage update:** Event lifecycle is now split into local detection (`EventDetection`), wall-registration projection/stabilization (`EventPositionStabilizer`), stable global observation (`EventObservation`), memory task creation, and handler execution. `stable_frames` replaces portal task confirmation for localization; `memory_confirm_frames` remains as a post-stabilization memory gate.

**Verification:** `D:\ACloud\.venv\Scripts\python.exe -m compileall -q core\events core\navigation_core.py gui\modes\navigation_mode.py gui\dialogs\event_manager_dialog.py main.py` passed. `D:\ACloud\.venv\Scripts\python.exe -c "from gui.modes.navigation_mode import NavigationModeWidget; from core.events.types.portal.minimap_detector import PortalMinimapDetector; from core.events.position_stabilizer import EventPositionStabilizer; from core.navigation_core import NavigationCore; print('import ok')"` passed. No logic/unit tests were run per user preference.

**Revised old conclusion:** Portal localization errors should no longer be treated as a detector-only threshold problem. The stable contract is now: detector finds local icon, navigation registration anchors the frame to the wall map, and only repeated projections to the same global coordinate become actionable events.

## [SYNC] 2026-05-23 - Hide default console and fix garbled status text
### A. SYNC scope
**Trigger:** User reported that runtime opens a terminal and the printed content is garbled or `????`.

**Direct files changed:**
- `main.py`
- `gui/modes/navigation_mode.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**Expected impact:** Normal GUI launch should no longer show an extra console after UAC elevation. Runtime diagnostics are written to `logs/runtime.log` in UTF-8. If live console output is needed, set `MINIMAP_DEBUG_CONSOLE=1` before launching.

### C. SYNC result
**Root cause:** Admin relaunch used `sys.executable`; when launched from `python.exe`, UAC restarted another console Python process. Console encoding could also corrupt Chinese output, and several navigation status/debug strings had already been saved as literal `????`.

**Fix:** `main.py` now configures UTF-8 output, redirects default stdout/stderr to `logs/runtime.log`, uses `pythonw.exe` for default UAC relaunch, and only keeps console mirroring when `MINIMAP_DEBUG_CONSOLE=1`. Navigation status/debug strings that were literal `????` were restored to readable Chinese.

**Verification:** `D:\ACloud\.venv\Scripts\python.exe -m py_compile main.py gui\modes\navigation_mode.py` passed. `rg "????" main.py gui/modes/navigation_mode.py core/events` returned no matches.

## [SYNC] 2026-05-23 - Release console before admin relaunch
### A. SYNC scope
**Trigger:** User still sees a runtime terminal with garbled output.
**Direct files changed:** `main.py`, `CODEBASE.md`, `ITERATION_LOG.md`.
**Expected impact:** Default GUI startup releases any inherited console before the UAC/admin branch and continues writing diagnostics to UTF-8 `logs/runtime.log`. Explicit debug console remains available via `MINIMAP_DEBUG_CONSOLE=1`.

### C. SYNC result
**Root cause refinement:** `pythonw.exe` prevents the elevated GUI process from creating a new console, but a non-debug launch from `python.exe` or PowerShell can still inherit/show the initial console until it is explicitly released.
**Fix:** `hide_console_if_not_debugging()` now runs immediately after output redirection, before DPI/admin checks and before Qt import. The UAC call still uses normal show mode so the Qt main window is not hidden.
**Verification:** `D:\ACloud\.venv\Scripts\python.exe -m py_compile main.py` passed. No logic/unit tests were run per user preference.

## [SYNC] 2026-05-23 - Paired portal completion handling
### A. SYNC scope
**Trigger:** User showed paired portals where localization/markers jump between two nearby portal icons, and after teleport the exit portal should be marked completed to prevent reverse teleport loops.
**Direct files changed:** `core/events/models.py`, `core/events/position_stabilizer.py`, `core/events/memory.py`, `core/events/runner.py`, `core/events/config.py`, `core/events/types/portal/config.py`, `core/events/types/portal/handler.py`, `map_data/A1/event_config.json`, `CODEBASE.md`, `ITERATION_LOG.md`.
**Expected impact:** Two portals visible in the same minimap frame are kept as separate event clusters. When an entry portal completes, the player destination is used to mark the nearby exit portal completed/cooldown as well.

### C. SYNC result
**Root cause:** `localization_cluster_radius=110` let two close portal detections merge into one cluster, so the stable marker could bounce between them. Completion only applied to the executed entry task, so the exit-side task could remain pending and be selected immediately after teleport.
**Fix:** Reduced portal localization cluster radius to 56 and made `EventPositionStabilizer` refuse to merge multiple detections from the same frame into one cluster. `EventAction.complete()` now carries metadata; portal handler includes `entry_pos` and `exit_pos`; runner asks memory to mark a related exit task completed before suppressing nearby pending tasks. Added `exit_complete_radius=120` to defaults and A1 config.
**Verification:** `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\events\models.py core\events\position_stabilizer.py core\events\memory.py core\events\runner.py core\events\config.py core\events\types\portal\config.py core\events\types\portal\handler.py` passed. No logic/unit tests were run per user preference.

## [SYNC] 2026-05-23 - Split paired portal tasks in memory
### A. SYNC scope
**Trigger:** User reported paired portals still show as one marker jumping between two portal positions; execution logic should wait until recognition/localization is stable.
**Direct files changed:** `core/events/memory.py`, `core/events/config.py`, `core/events/types/portal/config.py`, `map_data/A1/event_config.json`, `CODEBASE.md`, `ITERATION_LOG.md`.
**Expected impact:** Stable observations at two nearby portal coordinates should become two separate tasks/markers instead of repeatedly updating one task position.

### C. SYNC result
**Root cause refinement:** Runtime logs showed detector and stabilizer already produced two stable portal positions, approximately `(3466,2275)` and `(3512,2327)`. The jump happened in `EventMemory._find_matching_task()` because the default dedupe radius was 80 and the two portals are roughly 69px apart.
**Fix:** Added portal `dedupe_radius=32` defaults and A1 config. `EventMemory.merge_observations()` now tracks task IDs touched during the current frame, so two observations from one frame cannot both merge into the same task.
**Verification:** `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\events\memory.py core\events\config.py core\events\types\portal\config.py` passed. No logic/unit tests were run per user preference.

## [SYNC] 2026-05-23 15:14 - Portal test pipeline refactor and quiet navigation logs
### A. SYNC scope
**Trigger:** User asked to remove noisy per-frame navigation localization prints, keep portal event operation logs, save a git baseline before refactor, and refactor portal manual test logic so test mode and real navigation use the same event movement pipeline.

**Direct files changed:**
- `gui/modes/navigation_mode.py`
- `gui/dialogs/event_manager_dialog.py`
- `core/events/path_mover.py`
- `gui/modes/event_test_controller.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**Expected impact:** Runtime logs should no longer be flooded by every-frame localization position/source output. Clicking the portal test button should enable the same portal event handler/action pipeline used during automatic navigation, while event-specific A* movement is owned by a reusable module instead of being embedded in `navigation_mode.py`.

### C. SYNC result
**Carryover files reviewed:** `gui/modes/navigation_mode.py`, `gui/dialogs/event_manager_dialog.py`, `core/events/path_mover.py`, `gui/modes/event_test_controller.py`.

**CODEBASE.md updated:** Added directory and module entries for `core/events/path_mover.py` and `gui/modes/event_test_controller.py`; updated `navigation_mode.py` and event-manager descriptions; added function index entries for manual portal test startup, event MOVE_TO execution, `EventPathMover.step()`, and `EventPathMover._plan_path()`; updated the event-management flow to state that manual portal testing runs the same event pipeline as automatic navigation.

**Coverage update:** `navigation_mode.py` now delegates event movement planning to `EventPathMover` and manual test button state to `ManualEventTestController`. `event_manager_dialog.py` now drops the Qt checked argument before emitting `test_portal_requested`. The removed per-frame navigation position/source print block is intentionally not replaced; portal/event operation logs remain through `event_log()`.

**Baseline commit:** `86046ce Save event navigation baseline before refactor` was created before this refactor.

**Verification:** Pending compile/import checks after documentation sync. No logic/unit tests will be run per user preference.

## [SYNC] 2026-05-23 15:55 - Separate event logs and harden portal cooldown
### A. SYNC scope
**Trigger:** User reported that `logs/runtime.log` is still flooded by localization-position lines and portal test event logs are hard to see; also showed a completed paired portal area creating a new portal task nearby.

**Direct files changed:**
- `main.py`
- `core/events/debug.py`
- `core/events/memory.py`
- `core/events/config.py`
- `map_data/A1/event_config.json`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**Expected impact:** Each GUI start rewrites `runtime.log` instead of appending old sessions; event diagnostics are also written to a dedicated `logs/event_runtime.log`. Completed/ignored nearby portal tasks participate in cooldown suppression, so icons detected near a just-handled portal pair should not immediately become new actionable tasks.

### C. SYNC result
**Root cause evidence:** Current `gui/modes/navigation_mode.py` no longer contains the per-frame `当前定位/位置来源/本帧定位位置` print block, while `runtime.log` still contained millions of bytes from earlier sessions. `[Event ...]` lines were present but buried inside the combined runtime log.

**Fix:** `main.py` now opens `logs/runtime.log` with `w` mode per process session. `core/events/debug.py::event_log()` writes every event diagnostic to `logs/event_runtime.log` and still mirrors to runtime output. `EventMemory` now gives ignored/suppressed tasks a cooldown timestamp and logs cooldown details (`matched_task`, cooldown kind, distance/radius, remaining_ms). Portal default and A1 cooldown are extended to `cooldown_ms=120000` and `type_cooldown_ms=10000`.

**Verification:** Pending compile/import checks. No logic/unit tests will be run per user preference.

## [SYNC] 2026-05-23 - Event manager editable portal parameters
### A. SYNC scope
**Trigger:** User reported portal manual test presses `D` before the in-game portal interaction prompt is available, and requested the range threshold be configurable and saved from the event manager UI.

**Direct files changed:**
- `gui/dialogs/event_manager_dialog.py`
- `core/events/types/portal/definition.py`
- `core/events/types/portal/config.py`
- `docs/plans/2026-05-23-event-config-panel-plan.md`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**Expected impact:** The event manager shows a schema-driven parameter editor for the selected complete event. For `portal`, `interact_radius` is now editable and saved to the current map's `event_config.json`; lowering it delays pressing `D` until the character is closer to the portal.

### C. SYNC result
**Fix:** Rebuilt `EventManagerDialog` with a parameter panel driven by each event's `config_schema()`. Parameter changes update the in-memory `EventSystemConfig` and the existing save button persists them through `NavigationModeWidget._save_event_config()`. `PortalEventDefinition.config_schema()` now exposes `interact_radius`, `cooldown_ms`, and `type_cooldown_ms`; `PortalEventConfig` defaults match the current longer cooldown values.

**Verification:** Pending final compile/import checks. No logic/unit tests will be run per user preference.

## [STRUCTURE AUDIT] 2026-05-23 - Round 1 core responsibility scan
### A. 本轮目标（阅读前声明）
**目标文件：**
- `gui/modes/navigation_mode.py`（原因：导航模式主类仍是最大 GUI 聚合点，需要确认 UI、路线、事件、输入、overlay、循环是否混杂）
- `gui/modes/mapping_widget.py`（原因：绘图模式可能同时承担采集、渲染、保存、参数同步）
- `gui/dialogs/*.py` 与 `gui/navigation_params.py`（原因：配置编辑、事件管理、导航参数边界需要确认）
- `core/navigation_core.py`、`core/stitcher_core.py`、`core/auto_navigator.py`、`core/motion_controller.py`、`core/pathfinder.py`、`core/path_utils.py`（原因：核心算法层是否混入 UI/输入/调试职责）
- `core/events/*` 与 `utils/*.py`（原因：事件包、输入/窗口/探针能力是否可复用且边界清晰）

**本轮想弄清楚：**
- 大文件、大类、大函数集中在哪里，哪些是低风险移动代码候选。
- GUI 主页面是否承担了可拆分的 overlay、路线编辑、地图加载、参数桥接、事件桥接、输入模式控制。
- Core 算法层是否存在 GUI 状态、窗口输入或配置编辑耦合。
- 事件系统各层 detector/localizer/memory/scheduler/runner/handler/action executor 的职责是否清晰。
- 第一批低风险重构应只移动哪些模块，并保留现有 import 入口。

### C. 本轮发现
**关键发现：**
- (verified) `gui/modes/navigation_mode.py` 约 1584 行，是当前最大职责混合点：UI 创建/信号、地图加载、路线编辑、路线 overlay、事件 overlay、事件配置桥接、事件 action 回调、捕获几何、屏幕幕布、校准、输入窗口置顶控制和导航循环都在同一个类。
- (verified) `gui/modes/mapping_widget.py` 约 500 行，承担绘图页 UI、区域/中心选择、截图循环、识别/拼接调用、地图显示渲染、路径预览、参数同步、保存地图和全局配置读写。
- (verified) `gui/dialogs/advanced_settings_dialog.py` 约 763 行，混合 tab 构建、参数默认值、预设、文件 IO 和对 recognizer/stitcher 的实时应用；`gui/dialogs/nav_params_dialog.py` 约 543 行，混合字段映射、配置替换、屏幕边界估算和 UI 同步。
- (verified) `core/stitcher_core.py`、`core/navigation_core.py`、`core/auto_navigator.py` 是算法敏感大文件。它们没有直接依赖 Qt，但含保存/加载、显示图生成、调试 print 或状态机辅助逻辑，拆分风险高于 GUI helper 移动。
- (verified) 事件系统核心边界相对清晰：`coordinator -> monitor -> position_stabilizer -> memory -> scheduler -> runner -> handler/action`。主要耦合点在 `NavigationModeWidget` 负责构造 `EventTick`、执行 event MOVE_TO、绘制 event overlay。
- (verified) `MotionController` 是输入控制聚合点，集中地图方向到屏幕点击、底部禁点防护、Win32 输入后端、pydirectinput 兜底、键盘事件和窗口诊断。它是后续输入控制模块化目标，但不适合作为第一批低风险拆分。

**修订的旧结论：**
- 原先 `navigation_mode.py` 已经把手动事件测试按钮和事件 MOVE_TO 路径规划拆出一部分，但它仍不是薄门面；事件桥接和 overlay 绘制仍在主类内。
- 事件系统本体暂不应作为第一批拆分对象；更低风险的是先从 GUI 主类移出展示/桥接代码。

**新增疑问：**
- `AdvancedSettingsDialog` 是否仍被频繁使用，且其参数文件保存到当前工作目录是否属于预期行为，需要后续单独确认后再移动 IO 路径。
- `ColorPickerDialog.update_preview()` 会写 debug 图片和日志到当前工作目录；这是既有行为，结构拆分时不应顺手改变输出位置。

**更新了 CODEBASE.md：**
- 新增 `## 15. Structural Audit Snapshot`，记录本轮结构热点、可复用能力、边界不清晰点和推荐重构顺序。

**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/modes/navigation_mode.py` | 已有事件重构记录 | (partial) | 1 | 读完类结构、route/event overlay、事件桥接、配置桥接、导航循环；尚未逐行索引所有函数体。 |
| `gui/modes/mapping_widget.py` | PENDING | (partial) | 1 | 读完主类职责、捕获循环、显示渲染、保存/加载配置；适合作为第二批 GUI 拆分目标。 |
| `gui/dialogs/event_manager_dialog.py` | 已有事件 UI 记录 | (partial) | 1 | 读完 schema 参数面板、事件表、任务表刷新；可拆参数控件工厂和表格刷新 helper。 |
| `gui/dialogs/nav_params_dialog.py` | PENDING | (partial) | 1 | 读完 UI 构建、widget_map、配置替换、自动估算点击半径；低风险 helper 候选。 |
| `gui/dialogs/advanced_settings_dialog.py` | PENDING | 浅读 | 1 | 确认大文件职责混杂和文件 IO/预设/UI 混合，未逐函数精读。 |
| `gui/dialogs/color_picker_dialog.py` | PENDING | 浅读 | 1 | 确认采样、HSV 计算、预览渲染、debug 文件输出混合，未逐函数精读。 |
| `gui/navigation_params.py` | 已有记录 | (partial) | 1 | 确认配置模型边界清晰，但解析/序列化可更健壮；暂不优先动。 |
| `core/navigation_core.py` | 已有记录 | (partial) | 1 | 读完定位主链路，确认算法敏感，不作为第一批移动对象。 |
| `core/stitcher_core.py` | 已有记录 | (partial) | 1 | 读完拼接/融合/保存/显示职责，建议后期拆分。 |
| `core/auto_navigator.py` | 已有记录 | (partial) | 1 | 读完状态机和路线 helper，建议先保持稳定。 |
| `core/motion_controller.py` | 已有输入记录 | (partial) | 1 | 读完输入聚合职责，后续拆输入后端/诊断，首批不动。 |
| `core/pathfinder.py` | 已有记录 | (partial) | 1 | A* 边界清晰，暂不拆。 |
| `core/path_utils.py` | 已有记录 | (partial) | 1 | 纯工具边界清晰，可复用，不需要首批重构。 |
| `core/events/*` | 已有事件记录 | (partial) | 1 | 读完主链路与 portal 包关键文件，边界总体清晰；GUI 桥接优先拆。 |
| `utils/*.py` | 已有探针记录 | 浅读 | 1 | 探针是独立 CLI，输入探针有和 MotionController 重复的输入诊断概念，暂不动。 |

**下一轮计划：**
- 等用户确认第一批低风险拆分计划后，先从 `gui/modes/navigation_mode.py` 中拆出纯 GUI 绘制/桥接模块：`gui/modes/navigation/route_overlay.py`、`event_overlay.py` 或 `event_adapter.py`、`map_runtime.py` 中最独立的一小块。
- 每批只移动少量代码，保留 `gui.modes.navigation_mode.NavigationModeWidget` 入口，执行 `python -m py_compile ...` 和必要 import 检查后再做下一批。

## [REFACTOR] 2026-05-23 - Navigation overlay split batch 1
### A. 变更范围声明（执行前）
**触发任务：** 用户确认执行第一批低风险结构拆分。

**直接计划变更文件：**
- `gui/modes/navigation_mode.py`
- `gui/modes/navigation/__init__.py`
- `gui/modes/navigation/route_overlay.py`
- `gui/modes/navigation/event_overlay.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：**
- `NavigationModeWidget` 保留 `_render_route_overlay()`、`_render_event_overlay()`、`_clear_route_overlay()`、`_clear_event_overlay()` 等原有内部入口，但方法体改为委托新 helper。
- 新 helper 只接收现有 `scene/nav_core/route_data/event_coordinator` 和 item 列表，不改变路线、事件、自动导航或点击行为。
- 最小验证范围为 `py_compile` 和 `NavigationModeWidget` import。

### C. 变更结果
**实际变更：**
- (verified) 新增 `gui/modes/navigation/` helper 包。
- (verified) 新增 `event_overlay.py`，承接事件 marker 清理、全局坐标到场景坐标转换、事件 overlay 绘制。
- (verified) 新增 `route_overlay.py`，承接路线 overlay 清理、出口/必经点/途经点/当前路径/subgoal 绘制。
- (verified) `NavigationModeWidget` 保留原 `_clear_route_overlay()`、`_clear_event_overlay()`、`_global_to_scene()`、`_render_event_overlay()`、`_render_route_overlay()`，方法体改为委托新 helper。
- (verified) `NavigationModeWidget._render_route_overlay()` 保留原来的 scene/nav_core 不可用时早退语义；未改变导航循环、事件调度、路线数据读写、点击行为或默认参数。

**CODEBASE.md 更新内容：**
- 更新目录结构图，新增 `gui/modes/navigation/__init__.py`、`event_overlay.py`、`route_overlay.py`。
- 更新 `gui/modes/navigation_mode.py` 模块说明，标明 overlay 绘制已拆出。
- 新增 `event_overlay.py` / `route_overlay.py` 模块详解。
- 更新 `NavigationModeWidget._render_event_overlay()` 函数索引，并新增 `render_route_overlay()`、`render_event_overlay()` 函数索引。
- 更新结构审计快照，记录第一批拆分结果。

**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/modes/navigation_mode.py` | (partial) | (partial) | 2 | 本轮重读并修改 overlay 方法，保留兼容入口，主类行数下降但仍承担导航循环/事件桥接/配置桥接。 |
| `gui/modes/navigation/__init__.py` | PENDING | 深度完整 | 1 | 新增空包入口，仅用于 helper 模块命名空间。 |
| `gui/modes/navigation/event_overlay.py` | PENDING | 深度完整 | 1 | 新增事件 overlay helper，只绘制/清理 QGraphicsItem，不读取业务配置。 |
| `gui/modes/navigation/route_overlay.py` | PENDING | 深度完整 | 1 | 新增路线 overlay helper，只消费传入 route/current 状态并绘制 QGraphicsItem。 |

**验证：**
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\modes\navigation_mode.py gui\modes\navigation\__init__.py gui\modes\navigation\event_overlay.py gui\modes\navigation\route_overlay.py` 待最终复跑。
- `D:\ACloud\.venv\Scripts\python.exe -c "from gui.modes.navigation_mode import NavigationModeWidget; ..."` 待最终复跑。

**下一轮计划：**
- 若本批通过，下一批建议继续拆 `navigation_mode.py` 的事件桥接：`EventTick` 构造、event action 判断、事件状态文字、event config dialog bridge 可进入 `gui/modes/navigation/event_adapter.py`，但仍保留原私有方法委托入口。

## [REFACTOR] 2026-05-23 - Navigation event adapter split batch 2
### A. 变更范围声明（执行前）
**触发任务：** 用户要求继续并由 agent 自主规划完成结构优化。

**直接计划变更文件：**
- `gui/modes/navigation_mode.py`
- `gui/modes/navigation/event_adapter.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：**
- 只移动事件桥接中纯构造/判断/展示 helper：registry 创建、事件启用摘要、`EventTick` 构造、action 是否接管导航、事件状态文案。
- 保留 `NavigationModeWidget._build_event_tick()`、`_should_event_action_take_control()`、`_event_status_text()` 原私有入口，避免改调用方。
- 不拆 `EventCoordinator`、`EventMemory`、`EventRunner`、`PortalEventHandler` 等事件核心模块。
- 不改变 `event_config.json` 保存、事件调度、移动点击或传送门行为。

### C. 变更结果
**实际变更：**
- (verified) 新增 `gui/modes/navigation/event_adapter.py`。
- (verified) `NavigationModeWidget.__init__()` 通过 `create_default_event_registry()` 创建默认事件 registry，仍注册同一个 `PortalEventDefinition`。
- (verified) 事件初始化/配置变更日志的事件开关摘要委托 `event_config_summary()`。
- (verified) `_find_game_window_rect()` 委托 `find_default_game_window_rect()`，仍查找 `Torchlight` / `UnrealWindow`。
- (verified) `_build_event_tick()` 委托 `build_event_tick()`，字段保持原 `EventTick` 契约。
- (verified) `_should_event_action_take_control()` 委托 `should_event_action_take_control()`；终止 action 判断改用 `is_terminal_event_action()`。
- (verified) `_event_status_text()` 委托 `event_status_text()`。

**CODEBASE.md 更新内容：**
- 新增目录结构和模块详解：`gui/modes/navigation/event_adapter.py`。
- 更新 `navigation_mode.py` 依赖和职责说明。
- 新增 `build_event_tick()`、`should_event_action_take_control()` 函数索引。
- 更新结构审计快照，记录第二批拆分结果。

**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/modes/navigation_mode.py` | (partial) | (partial) | 3 | 本轮重读事件桥接区域并改为 helper 委托；仍保留原私有入口。 |
| `gui/modes/navigation/event_adapter.py` | PENDING | 深度完整 | 1 | 新增事件桥接 helper，不推进事件系统状态，不执行输入。 |

**验证：**
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\modes\navigation_mode.py gui\modes\navigation\event_adapter.py gui\modes\navigation\event_overlay.py gui\modes\navigation\route_overlay.py` 待最终复跑。
- `D:\ACloud\.venv\Scripts\python.exe -c "from gui.modes.navigation_mode import NavigationModeWidget; from gui.modes.navigation.event_adapter import build_event_tick, create_default_event_registry; print('imports ok')"` 待最终复跑。

**下一轮计划：**
- 下一批优先拆 `navigation_mode.py` 的地图/配置运行时 helper：地图目录定位、地图列表读取、配置读写、capture geometry 或 game-view/monitor rect 计算，仍保持主类 UI 入口不变。

## [REFACTOR] 2026-05-23 - Navigation map runtime split batch 3
### A. 变更范围声明（执行前）
**触发任务：** 继续自主推进导航页面职责分离。

**直接计划变更文件：**
- `gui/modes/navigation_mode.py`
- `gui/modes/navigation/map_runtime.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：**
- 移出项目根目录/map_data 路径定位、地图列表读取、地图文件夹解析、`NavConfig` 加载/保存、DPR 物理中心换算、capture geometry 计算。
- 保留 `NavigationModeWidget.refresh_map_list()`、`load_map()`、`_build_capture_geometry()`、`_save_nav_config()` 等原入口；主类仍负责按钮状态、弹窗和状态栏。
- 不改变 config.json 字段、不改变默认参数、不改变截图矩形计算结果。

### C. 变更结果
**实际变更：**
- (verified) 新增 `gui/modes/navigation/map_runtime.py`。
- (verified) `refresh_map_list()` 通过 `list_map_names(__file__)` 获取地图名，缺失时仍显示原文案 `未找到 map_data 文件夹`。
- (verified) `load_map()` 通过 `resolve_map_folder()` 和 `load_nav_config()` 解析地图路径与配置；缺少配置仍使用默认 `NavConfig()` 并弹出原警告。
- (verified) 逻辑中心到物理中心换算委托 `physical_center_from_logical()`。
- (verified) `_build_capture_geometry()` 委托 `map_runtime.build_capture_geometry()`，保留 region 模式与 center 模式旧返回契约。
- (verified) `_save_nav_config()` 委托 `save_nav_config()` 写回当前地图 `config.json`，保存字段和格式保持 `NavConfig.to_dict()` + `indent=4` + `ensure_ascii=False`。
- (verified) 清理了 `navigation_mode.py` 中不再需要的 `os/json` import 和旧路径计算残留。

**CODEBASE.md 更新内容：**
- 新增目录结构和模块详解：`gui/modes/navigation/map_runtime.py`。
- 新增 `map_runtime.build_capture_geometry()` 函数索引。
- 更新结构审计快照，记录第三批拆分结果。

**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/modes/navigation_mode.py` | (partial) | (partial) | 4 | 本轮重读地图列表、配置读写、capture geometry 区域并改为 helper 委托。 |
| `gui/modes/navigation/map_runtime.py` | PENDING | 深度完整 | 1 | 新增地图运行时 helper，只做路径/配置/几何数据处理，不处理 UI。 |

**验证：**
- `D:\ACloud\.venv\Scripts\python.exe -c "from gui.modes.navigation.map_runtime import project_root_from_file, map_data_dir, list_map_names; ..."` 已确认 project root 为 `D:\ACloud\minimap_stitcher copy 13`，map_data 路径为项目内 `map_data`，当前识别到 17 个地图目录。
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\modes\navigation_mode.py gui\modes\navigation\map_runtime.py gui\modes\navigation\event_adapter.py gui\modes\navigation\event_overlay.py gui\modes\navigation\route_overlay.py` 待最终复跑。
- `D:\ACloud\.venv\Scripts\python.exe -c "from gui.modes.navigation_mode import NavigationModeWidget; from gui.modes.navigation.map_runtime import load_nav_config, save_nav_config, build_capture_geometry; print('imports ok')"` 待最终复跑。

**下一轮计划：**
- 下一批继续在导航 GUI 层内拆矩形/overlay runtime：`_update_monitor_rect()`、`_update_game_view_rect()` 和 overlay screen rect 逻辑可进入 `gui/modes/navigation/viewport_overlay.py`，降低主类绘图细节。

## [REFACTOR] 2026-05-23 - Navigation viewport overlay split batch 4
### A. 变更范围声明（执行前）
**触发任务：** 继续自主推进导航页面职责分离。

**直接计划变更文件：**
- `gui/modes/navigation_mode.py`
- `gui/modes/navigation/viewport_overlay.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：**
- 移出屏幕幕布逻辑坐标矩形计算、监控区域地图矩形计算、真实主画面地图矩形计算。
- 主类仍负责调用 `overlay.set_rect_and_show()` 和更新已有 QGraphicsRectItem，不改变颜色、zValue、可见性或触发时机。
- 不改变 `monitor_region` / `monitor_logical_center` / `game_view_map_size` 语义。

### C. 变更结果
**实际变更：**
- (verified) 新增 `gui/modes/navigation/viewport_overlay.py`。
- (verified) `_update_overlay_display()` 使用 `screen_overlay_geometry()` 计算逻辑坐标屏幕幕布 rect 和 anchor，仍由主类调用 `overlay.set_rect_and_show()`。
- (verified) `_update_monitor_rect()` 使用 `monitor_scene_rect()` 计算绿色截图范围框地图矩形，仍由主类更新已有 `monitor_rect_item`。
- (verified) `_update_game_view_rect()` 使用 `game_view_scene_rect()` 计算橙色主画面范围框地图矩形；尺寸无效时仍隐藏该 item。
- (verified) 不改变 QPen/QColor/zValue 创建逻辑，也不改变刷新触发时机。

**CODEBASE.md 更新内容：**
- 新增目录结构和模块详解：`gui/modes/navigation/viewport_overlay.py`。
- 新增 `viewport_overlay.monitor_scene_rect()` 和 `viewport_overlay.game_view_scene_rect()` 函数索引。
- 更新结构审计快照，记录第四批拆分结果。

**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/modes/navigation_mode.py` | (partial) | (partial) | 5 | 本轮重读屏幕幕布、绿色监控框、橙色主画面框更新逻辑并委托几何 helper。 |
| `gui/modes/navigation/viewport_overlay.py` | PENDING | 深度完整 | 1 | 新增矩形几何 helper，只返回数据，不创建 Qt item。 |

**验证：**
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\modes\navigation_mode.py gui\modes\navigation\viewport_overlay.py` 已通过初检，待最终全量轻量复跑。

**下一轮计划：**
- 导航页面低风险 helper 拆分已完成 4 批；下一步转向 `mapping_widget.py`，先拆 `gui/modes/mapping/save_load.py` 或 `params_adapter.py`，移动全局 config/map save/load 逻辑，保留 `MappingWidget` 入口。

## [REFACTOR] 2026-05-23 - Mapping save/load split batch 5
### A. 变更范围声明（执行前）
**触发任务：** 继续自主推进全项目结构优化，从导航页面转向绘图页面低风险拆分。

**直接计划变更文件：**
- `gui/modes/mapping_widget.py`
- `gui/modes/mapping/__init__.py`
- `gui/modes/mapping/save_load.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：**
- 移出项目根目录解析、全局 `config.json` 读写、地图保存配置 dict 构造、地图文件夹创建。
- `MappingWidget.save_map()`、`save_config()`、`load_saved_params()` 原入口保留，仍负责弹窗、UI 控件同步和调用 stitcher/recognizer。
- 不改变保存文件名、保存字段、默认值或 map_data 目录结构。

### C. 变更结果
**实际变更：**
- (verified) 新增 `gui/modes/mapping/` helper 包。
- (verified) 新增 `gui/modes/mapping/save_load.py`，承接项目根目录解析、`map_data/<name>` 创建、根级/地图级 `config.json` 读写和 mapping config dict 构造。
- (verified) `MappingWidget.save_map()` 保留原方法入口，仍负责地图名弹窗、调用 `stitcher.save_map_package()` 和成功提示；路径/配置写入委托 helper。
- (verified) `MappingWidget.save_config()` 保留原方法入口，委托 `build_mapping_config()` + `save_root_config()`。
- (verified) `MappingWidget.load_saved_params()` 保留原方法入口，委托 `load_root_config()`；根配置不存在仍直接返回，JSON/KeyError 仍由原 except 处理。
- (verified) 清理 `mapping_widget.py` 中本批不再需要的 `sys/os/ctypes/datetime` import；保留 `json` 仅用于原 `JSONDecodeError` except 契约。

**CODEBASE.md 更新内容：**
- 新增目录结构说明：`gui/modes/mapping/__init__.py`、`gui/modes/mapping/save_load.py`。
- 新增模块详解：`mapping_widget.py`、`mapping/__init__.py`、`mapping/save_load.py`。
- 新增函数索引：`build_mapping_config()`、`ensure_map_folder()`、`save_root_config()`、`load_root_config()`。
- 新增数据流：绘图模式地图保存和根配置加载。
- 更新结构审计快照，记录第五批拆分结果和 mapping 后续低风险候选。

**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/modes/mapping_widget.py` | 浅读 | (partial) | 2 | 本轮重读保存/加载区域并改为 helper 委托；捕获循环和渲染区域仍未深拆。 |
| `gui/modes/mapping/__init__.py` | PENDING | 深度完整 | 1 | 新增空包入口，确认无业务逻辑。 |
| `gui/modes/mapping/save_load.py` | PENDING | 深度完整 | 1 | 新增纯路径/JSON/config helper，不接触 Qt 控件和拼接算法生命周期。 |

**验证：**
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\modes\mapping_widget.py gui\modes\mapping\__init__.py gui\modes\mapping\save_load.py` 已通过。

**下一轮计划：**
- 继续在绘图页做低风险拆分：优先把 `update_displays()` / `_show_image()` 中的图像转 QPixmap、全局地图着色、路径线/视野框/当前位置绘制移动到 `gui/modes/mapping/map_renderer.py`，保留 `MappingWidget.update_displays()` 入口和 UI setPixmap 调用时机。

## [REFACTOR] 2026-05-23 - Mapping renderer split batch 6
### A. 变更范围声明（执行前）
**触发任务：** 继续自主推进绘图页面职责分离，优先移动纯渲染逻辑。

**直接计划变更文件：**
- `gui/modes/mapping_widget.py`
- `gui/modes/mapping/map_renderer.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：**
- 移出 OpenCV 全局地图着色、导航路径 polyline、视野框、当前位置圆点绘制和 BGR/RGB QPixmap 转换。
- `MappingWidget.update_displays()` 和 `_show_image()` 原入口保留，仍负责调用 stitcher、读取 UI/runtime 状态、写入 Qt label/map widget。
- 不改变颜色、线宽、crop offset、路径坐标换算、当前位姿显示或 fallback 逻辑。

### C. 变更结果
**实际变更：**
- (verified) 新增 `gui/modes/mapping/map_renderer.py`。
- (verified) `pixmap_from_bgr()` 承接 BGR -> RGB -> QImage -> QPixmap 转换，保留 `.copy()` 避免临时 numpy buffer 生命周期问题。
- (verified) `unpack_enhanced_map_result()` 保留旧 `get_enhanced_map()` tuple/fallback 解包契约。
- (verified) `render_global_map_pixmap()` 承接全局地图灰度转 BGR、路径线、绿色视野框、当前位置圆点绘制，颜色和线宽保持旧值。
- (verified) `MappingWidget.update_displays()` 保留入口，只负责取 stitcher 结果、保存 `map_crop_offset`、选择 fallback `capture_size/player_pos` 并设置 `global_map_widget`。
- (verified) `MappingWidget._show_image()` 保留入口，委托 `pixmap_from_bgr()` 后设置 label pixmap。
- (verified) 移除 `mapping_widget.py` 中不再需要的 `cv2/numpy/QImage/QPixmap` import。

**CODEBASE.md 更新内容：**
- 新增目录结构说明和模块详解：`gui/modes/mapping/map_renderer.py`。
- 更新 `mapping_widget.py` 职责说明，标明渲染细节已委托。
- 新增函数索引：`render_global_map_pixmap()`、`pixmap_from_bgr()`。
- 更新结构审计快照，记录第六批拆分结果。

**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/modes/mapping_widget.py` | (partial) | (partial) | 3 | 本轮重读 `update_displays()` / `_show_image()` 并改为渲染 helper 委托；捕获循环和参数控件同步仍未深拆。 |
| `gui/modes/mapping/map_renderer.py` | PENDING | 深度完整 | 1 | 新增纯图像渲染 helper，只返回 QPixmap，不读取 app_context、不设置 Qt 控件。 |

**验证：**
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\modes\mapping_widget.py gui\modes\mapping\map_renderer.py gui\modes\mapping\save_load.py gui\modes\mapping\__init__.py` 已通过。
- `D:\ACloud\.venv\Scripts\python.exe -c "from gui.modes.mapping_widget import MappingWidget; from gui.modes.mapping.map_renderer import render_global_map_pixmap, pixmap_from_bgr; print('mapping renderer imports ok')"` 已通过。

**下一轮计划：**
- 优先检查 `mapping_widget.py` 的参数控件同步区：HSV、feature、merge、advanced settings、load_saved_params UI 回填是否能拆成 `params_adapter.py`。若发现需要大范围信号阻断或默认参数调整，则暂缓，转向 dialog helper。

## [REFACTOR] 2026-05-23 - Mapping params adapter split batch 7
### A. 变更范围声明（执行前）
**触发任务：** 继续绘图页面低风险职责分离，拆出参数控件到运行时参数的轻量桥接。

**直接计划变更文件：**
- `gui/modes/mapping_widget.py`
- `gui/modes/mapping/params_adapter.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：**
- 移出 feature 参数 dict 构造、HSV 开关应用、merge weight 应用、已加载 recognizer/stitcher 参数写回控件。
- 保留 `MappingWidget.update_hsv_params()`、`update_feature_params()`、`update_merge_params()`、`load_saved_params()` 原入口。
- 不改变默认值、字段名、setChecked/setValue 顺序或信号触发行为；不新增信号阻断。

### C. 变更结果
**实际变更：**
- (verified) 新增 `gui/modes/mapping/params_adapter.py`。
- (verified) `apply_hsv_toggles()` 承接墙体/迷雾复选框到 recognizer 字段写入。
- (verified) `feature_params_from_widgets()` 承接 feature 控件到 `recognizer.set_params()` dict 的构造，字段名和默认读取来源保持不变。
- (verified) `apply_merge_weight()` 承接 merge weight spinbox 到 stitcher `weight_add` 字段写入。
- (verified) `sync_recognizer_widgets()` 和 `sync_stitcher_widgets()` 承接加载配置后的控件回填，默认值和 `setChecked/setValue` 顺序保持旧实现。
- (verified) `MappingWidget` 保留原更新方法入口，并仍负责调用 `recognizer.set_params()`、`stitcher.set_params()` 和 `save_config()`。

**CODEBASE.md 更新内容：**
- 新增目录结构说明和模块详解：`gui/modes/mapping/params_adapter.py`。
- 更新 `mapping_widget.py` 职责说明，标明参数控件桥接已委托。
- 新增函数索引：`feature_params_from_widgets()`、`sync_recognizer_widgets()`、`apply_hsv_toggles()`。
- 更新结构审计快照，记录第七批拆分结果。

**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/modes/mapping_widget.py` | (partial) | (partial) | 4 | 本轮重读 HSV/feature/merge 参数更新和加载回填区域，并改为 params adapter 委托。 |
| `gui/modes/mapping/params_adapter.py` | PENDING | 深度完整 | 1 | 新增参数控件桥接 helper，不保存配置、不阻断信号、不创建控件。 |

**验证：**
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\modes\mapping_widget.py gui\modes\mapping\params_adapter.py gui\modes\mapping\map_renderer.py gui\modes\mapping\save_load.py gui\modes\mapping\__init__.py` 已通过。
- `D:\ACloud\.venv\Scripts\python.exe -c "from gui.modes.mapping_widget import MappingWidget; from gui.modes.mapping.params_adapter import feature_params_from_widgets, sync_recognizer_widgets; print('mapping params imports ok')"` 已通过。

**下一轮计划：**
- 暂缓继续拆 `mapping_widget.py` 的捕获循环，因为会触及 screen_capture、tracker、recognizer、stitcher 的时序和 fallback 行为；下一步更稳妥的是转向 dialog 层，先审 `gui/dialogs/color_picker_dialog.py` 或 `advanced_settings_dialog.py` 中可纯拆的预设/参数映射。

## [REFACTOR] 2026-05-23 - Advanced settings params adapter split batch 8
### A. 变更范围声明（执行前）
**触发任务：** 转向 dialog 层低风险拆分，先处理高级参数弹窗中纯参数控件映射逻辑。

**直接计划变更文件：**
- `gui/dialogs/advanced_settings_dialog.py`
- `gui/dialogs/advanced_settings/__init__.py`
- `gui/dialogs/advanced_settings/params_adapter.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：**
- 移出高级参数弹窗的当前参数写入控件、控件采集成 dict、重置默认值、加载参数文件后回填控件、预设参数写入控件逻辑。
- 保留 `AdvancedSettingsDialog` 类、`get_params()`、`load_current_params()`、`apply_params()`、`reset_to_default()`、`apply_loaded_params()`、`apply_preset()` 原入口。
- 不改变默认值、字段名、控件写入顺序、文件 IO、实时应用 recognizer/stitcher 的时机或打印文案。

### C. 变更结果
**实际变更：**
- (verified) 新增 `gui/dialogs/advanced_settings/` helper 包。
- (verified) 新增 `params_adapter.py`，承接当前参数加载到控件、控件采集为参数 dict、默认重置、已加载参数回填和预设写入。
- (verified) `AdvancedSettingsDialog.load_current_params()`、`apply_params()`、`reset_to_default()`、`apply_loaded_params()`、`apply_preset()` 原入口保留，改为委托 helper。
- (verified) 文件保存/加载、JSON 格式、状态栏文案、`current_params` 更新、recognizer/stitcher 实时应用和 print 文案仍留在原 dialog 类。
- (verified) 修正 helper 设计，`reset_widgets_to_default()` 不额外写旧实现没有写的 `blur_strength_spin`；`load_params_to_widgets()` 仍保持旧加载当前参数时写 `blur_strength_spin=3`。

**CODEBASE.md 更新内容：**
- 新增目录结构说明：`gui/dialogs/advanced_settings_dialog.py`、`gui/dialogs/advanced_settings/__init__.py`、`gui/dialogs/advanced_settings/params_adapter.py`。
- 新增模块详解：高级参数弹窗主类和 params adapter。
- 新增函数索引：`collect_params_from_widgets()`、`load_params_to_widgets()`、`apply_preset_to_widgets()`。
- 更新结构审计快照，记录第八批 dialog 层拆分结果。

**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/dialogs/advanced_settings_dialog.py` | (partial) | (partial) | 2 | 本轮重读参数加载/应用/默认/预设/文件加载回填区域并改为 helper 委托；UI 构造仍未拆。 |
| `gui/dialogs/advanced_settings/__init__.py` | PENDING | 深度完整 | 1 | 新增空包入口，确认无业务逻辑。 |
| `gui/dialogs/advanced_settings/params_adapter.py` | PENDING | 深度完整 | 1 | 新增高级参数控件映射 helper，不做文件 IO、不调用 recognizer/stitcher。 |

**验证：**
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\dialogs\advanced_settings_dialog.py gui\dialogs\advanced_settings\__init__.py gui\dialogs\advanced_settings\params_adapter.py` 已通过。
- `D:\ACloud\.venv\Scripts\python.exe -c "from gui.dialogs.advanced_settings_dialog import AdvancedSettingsDialog; from gui.dialogs.advanced_settings.params_adapter import collect_params_from_widgets, load_params_to_widgets; print('advanced settings imports ok')"` 已通过。

**下一轮计划：**
- 继续 dialog 层审计但暂缓大拆 UI 构造；`color_picker_dialog.py` 的 HSV range 计算、预览渲染和 debug 输出可作为下一批候选，但要避免改变采样结果和日志文件。

## [REFACTOR] 2026-05-23 - Color picker helper split batch 9
### A. 变更范围声明（执行前）
**触发任务：** 继续 dialog 层低风险拆分，处理颜色选择弹窗中可复用的 HSV range 计算和图像转换 helper。

**直接计划变更文件：**
- `gui/dialogs/color_picker_dialog.py`
- `gui/dialogs/color_picker/__init__.py`
- `gui/dialogs/color_picker/hsv_ranges.py`
- `gui/dialogs/color_picker/image_renderer.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：**
- 移出 HSV 样本范围计算和 BGR/灰度图像到 QPixmap 的转换。
- 保留 `ColorPickerDialog.calculate_hsv_ranges()`、`_calculate_range()`、`_show_image()` 原入口。
- 不改变采样点记录、推荐关闭饱和度过滤的阈值、结果文案、preview 逻辑或 debug 文件输出。

### C. 变更结果
**实际变更：**
- (verified) 新增 `gui/dialogs/color_picker/` helper 包。
- (verified) 新增 `hsv_ranges.py`，承接 BGR->HSV 转换、采样点 HSV 提取、HSV 范围计算和平均饱和度计算。
- (verified) 新增 `image_renderer.py`，承接 OpenCV 图像转 QPixmap 和墙体/人物采样 marker 绘制。
- (verified) `ColorPickerDialog.calculate_hsv_ranges()`、`_calculate_range()`、`_show_image()` 原入口保留，改为委托 helper。
- (verified) `update_preview()` 保持在 dialog 内，mask、形态学、debug png/txt 输出和日志内容未迁移。
- (verified) 保留原图像转换语义：颜色选择弹窗仍使用 `QPixmap.fromImage(q_img)`，未引入 `.copy()` 行为差异。

**CODEBASE.md 更新内容：**
- 新增目录结构说明：`gui/dialogs/color_picker_dialog.py`、`gui/dialogs/color_picker/__init__.py`、`hsv_ranges.py`、`image_renderer.py`。
- 新增模块详解：颜色选择弹窗主类和两个 helper。
- 新增函数索引：`calculate_hsv_range()`、`pixmap_from_image()`、`draw_sample_markers()`。
- 更新结构审计快照，记录第九批 dialog 层拆分结果。

**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/dialogs/color_picker_dialog.py` | (partial) | (partial) | 2 | 本轮重读 HSV 范围计算和图像显示区域并改为 helper 委托；preview debug 输出仍保留原类内。 |
| `gui/dialogs/color_picker/__init__.py` | PENDING | 深度完整 | 1 | 新增空包入口，确认无业务逻辑。 |
| `gui/dialogs/color_picker/hsv_ranges.py` | PENDING | 深度完整 | 1 | 新增 HSV 采样/范围计算 helper，保持旧容差和边界算法。 |
| `gui/dialogs/color_picker/image_renderer.py` | PENDING | 深度完整 | 1 | 新增图像转 pixmap 和采样点 marker 绘制 helper，保持旧颜色/半径/缩放公式。 |

**验证：**
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\dialogs\color_picker_dialog.py gui\dialogs\color_picker\__init__.py gui\dialogs\color_picker\hsv_ranges.py gui\dialogs\color_picker\image_renderer.py` 已通过。
- `D:\ACloud\.venv\Scripts\python.exe -c "from gui.dialogs.color_picker_dialog import ColorPickerDialog; from gui.dialogs.color_picker.hsv_ranges import calculate_hsv_range; from gui.dialogs.color_picker.image_renderer import pixmap_from_image; print('color picker imports ok')"` 已通过。

**下一轮计划：**
- 本阶段已覆盖导航、绘图、advanced settings、color picker 的低风险 GUI 拆分；后续建议暂停大改，先由用户做一次 GUI smoke test。下一阶段可审 `nav_params_dialog.py` 字段映射或转向 core/stitching，但风险明显高于本批。
## [BUGFIX] 2026-05-23 - Event dialog live refresh scope
### A. SYNC 范围声明
**触发任务：** 修复传送门事件窗口可见时导航循环每帧完整刷新，导致刷新按钮/测试按钮交互被持续 UI 重建干扰的问题。
**直接计划变更文件：**
- `gui/dialogs/event_manager_dialog.py`
- `gui/modes/navigation_mode.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：**
- 保留 `EventManagerDialog.refresh()` 作为完整刷新入口，供手动刷新、上下文切换、配置变化、保存后使用。
- 新增任务表轻量刷新入口，导航循环只更新任务状态表，不重建事件列表、复选框、参数控件或测试按钮。
- 不修改事件检测、传送门测试开停逻辑、默认配置或任务调度行为。
### C. SYNC 结果
**根因确认：**
- (verified) `NavigationModeWidget.navigation_loop()` 在事件窗口可见时，每次 `EventCoordinator.update()` 后都调用 `event_dialog.refresh()`。
- (verified) `EventManagerDialog.refresh()` 会调用 `_refresh_events()`，清空并重建事件表、事件复选框、参数面板，再刷新任务表。
- (inferred) 高频完整刷新会在鼠标交互期间反复重建控件，使刷新/测试按钮表现为持续被选中或点击难以稳定注册。

**实际变更：**
- (verified) `EventManagerDialog.refresh()` 保持完整刷新语义不变。
- (verified) 新增 `EventManagerDialog.refresh_tasks()`，仅委托 `_refresh_tasks()` 更新任务表和状态摘要。
- (verified) `NavigationModeWidget.navigation_loop()` 的两个事件窗口实时刷新调用改为 `refresh_tasks()`，不再每帧重建事件选配表和参数控件。
- (verified) 未修改事件检测、传送门测试开停、事件配置保存、默认参数或地图数据。

**CODEBASE.md 更新内容：**
- 更新 `gui/dialogs/event_manager_dialog.py` 模块说明，区分完整刷新和运行中轻量任务刷新。
- 更新 `gui/modes/navigation_mode.py` 注意事项，说明导航循环只调用 `refresh_tasks()`。
- 新增 `EventManagerDialog.refresh_tasks(self) -> None` 函数索引，并修订事件管理 UI Flow。

**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/dialogs/event_manager_dialog.py` | (partial) | (partial) | 2 | 本轮重读 `refresh()`、`_refresh_events()`、`_refresh_tasks()`、测试按钮信号，新增轻量任务刷新入口。 |
| `gui/modes/navigation_mode.py` | (partial) | (partial) | 6 | 本轮重读导航循环事件 coordinator 更新分支，将可见事件窗口的高频刷新改为任务表刷新。 |
## [BUGFIX] 2026-05-23 - Portal bounce caused by duplicate GUI instances
### A. SYNC 范围声明
**触发任务：** 排查用户点击“测试传送门”后在两个传送门之间反复传送的问题。
**直接变更文件：**
- `main.py`
- `core/events/debug.py`
- `core/events/runner.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：**
- Windows 启动路径增加单实例保护，避免旧/新两个 GUI 进程同时控制游戏。
- 事件日志增加 PID，后续可直接判断是否多进程混写。
- 事件 runner 增加终态任务保护，不允许 completed/ignored task 被再次启动或继续执行。

### C. SYNC 结果
**根因确认：**
- (verified) `logs/event_runtime.log` 同一会话内出现 `portal:1 seen=258 state=running` 后又出现 `task created id=portal:1`，单个 `EventCoordinator` 不可能让 `_next_id` 回绕。
- (verified) 本机同时存在两组 `pythonw.exe` GUI 进程，每组都有一个主窗口进程，说明多个程序实例在同一时间识别和操作游戏。
- (inferred) 两个实例同时写入同一个事件日志并向游戏发送按键，表现为一个实例完成入口传送后，另一个实例继续接管出口/入口任务，导致来回传送。

**实际变更：**
- (verified) `main.py` 新增基于项目路径 hash 的 Win32 mutex 单实例锁；同项目第二个实例启动时直接退出。
- (verified) `main.py` 新增已有主窗口扫描，用于拦截已经运行但没有 mutex 的旧构建实例。
- (verified) `core/events/debug.py` 的 `event_log()` 输出加入 `pid=<pid>`，用于识别多进程日志交错。
- (verified) `core/events/runner.py` 在 `update()` 和 `_start_task()` 两处拒绝 `COMPLETED/IGNORED` 终态任务。

**CODEBASE.md 更新内容：**
- 更新 Windows 启动外部集成说明，记录管理员提权后的单实例锁和主窗口检测。
- 更新事件日志诊断说明，记录 PID 输出。
- 更新传送门事件当前行为，记录 runner 终态任务防护。

**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `main.py` | (partial) | (partial) | 2 | 本轮重读管理员提权和 GUI 启动前置路径，新增单实例锁和已有窗口检测。|
| `core/events/debug.py` | (partial) | (partial) | 2 | 本轮重读事件日志写入路径，新增 PID 字段以定位多进程混写。|
| `core/events/runner.py` | (partial) | (partial) | 2 | 本轮重读 handler 生命周期，新增终态任务拒绝保护。|

**验证：**
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile main.py core\events\debug.py core\events\runner.py` 已通过。

## [FEATURE] 2026-05-23 - Portal teleport session completion
### A. SYNC 范围声明
**触发任务：** 用户确认传送门事件完成标准：一次传送成功后，传入门和传出门都应标记完成，不需要反复传送；同时要覆盖出口在独立地图、未提前识别到出口门的情况。
**直接变更文件：**
- `core/events/types/portal/handler.py`
- `core/events/runner.py`
- `core/events/memory.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：**
- 传送门 COMPLETE action 从“单 task 完成”扩展为“teleport session 完成”。
- 入口 task 和出口 task 共享 `teleport_session_id`，后续不再进入调度。
- 出口门没提前识别时创建 synthetic completed exit task，用于独立地图传送完成闭环和冷却。

### C. SYNC 结果
**关键发现：**
- (verified) `PortalEventHandler` 原完成标准只返回 `entry_pos/exit_pos`，语义是当前 task 完成。
- (verified) `EventRunner` 原逻辑用 `mark_related_completed()` 根据 `exit_pos` 完成一个附近 task，但没有会话 ID，也会把已有出口 task 坐标改成人物落点。
- (verified) `EventScheduler` 只按 running/pending 选任务，不理解入口/出口属于同一次传送。

**实际变更：**
- (verified) `PortalEventHandler` 在 COMPLETE metadata 中加入 `completion_kind="teleport"` 和 `entry_task_id`。
- (verified) `EventRunner` 收到 teleport complete 后调用 `EventMemory.complete_teleport_session()`；非 teleport complete 保留原单 task 完成路径。
- (verified) `EventMemory.complete_teleport_session()` 生成 `teleport_session_id`，把入口标记 `teleport_role=entry` 并 completed。
- (verified) `EventMemory.complete_teleport_session()` 优先用传送后人物落点附近已有 active portal task 作为出口并 completed；找不到时创建 synthetic completed exit task。
- (verified) 完成 session 后分别对入口和出口调用 `suppress_nearby_pending()`，避免同一对门继续进入调度。

**CODEBASE.md 更新内容：**
- 更新 Portal Event Current Behavior，记录 teleport session 完成语义、entry/exit metadata、synthetic exit、冷却作为二级防护。

**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/events/types/portal/handler.py` | (partial) | (partial) | 3 | 本轮重读 wait_result 完成分支，新增 teleport completion metadata。|
| `core/events/runner.py` | (partial) | (partial) | 3 | 本轮重读 COMPLETE 分支，改为按 `completion_kind` 分派到 teleport session 或普通完成。|
| `core/events/memory.py` | (partial) | (partial) | 3 | 本轮重读 task lifecycle/cooldown，新增 `complete_teleport_session()` 和出口 task 查找。|

**验证：**
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\events\types\portal\handler.py core\events\runner.py core\events\memory.py` 已通过。

## [BUGFIX] 2026-05-23 - Close paired portal completion detection
### A. SYNC 范围声明
**触发任务：** 用户反馈按 `D` 后角色位置已经改变到另一个传送门附近，但传送门事件仍保持处理中并继续来回传送。
**直接变更文件：**
- `core/events/models.py`
- `core/events/coordinator.py`
- `core/events/types/portal/handler.py`
- `core/events/runner.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：**
- `EventTick` 增加当前事件任务快照，handler 可在不直接依赖 memory 的情况下判断其它已知事件点。
- 传送门完成判定除大位移和环境变化外，增加“落在另一个已知 portal 附近且明显更接近出口”的分支。
- 修正 `EventRunner` COMPLETE 分支缩进，保证 teleport complete 后才清理 runner，FAIL 分支保持独立。

### C. SYNC 结果
**根因确认：**
- (verified) `logs/event_runtime.log` 显示 `portal:1` 按 `D` 前玩家约在 `(3462,2278)`，之后约在 `(3526,2334)`，位移约 84px，低于 `teleport_min_distance=180`。
- (verified) 同一批日志里已提前识别出 `portal:2`，其位置约 `(3513,2326)`，传送后玩家离它约 16px，说明传送实际已经成功。
- (verified) 原 `PortalEventHandler._teleport_completed()` 只接受大位移或小地图环境差异，没有利用已知出口 task，因此近距离双门会超时失败并调度另一个门。

**实际变更：**
- (verified) `EventTick` 新增 `event_tasks` 字段，作为 coordinator 写入的 memory 快照。
- (verified) `EventCoordinator.update()` 在 `memory.merge_observations()` 之后写入 `tick.event_tasks = self.memory.tasks()`，确保 handler 看到本帧合并后的最新双门任务。
- (verified) `PortalEventHandler._teleport_completed()` 在小位移情况下调用 `_near_known_exit_portal()`，当玩家落在另一个 active portal 的 `exit_complete_radius` 内且明显比入口更近时直接完成传送。
- (verified) `_near_known_exit_portal()` 排除当前入口 task、completed/ignored task 和非 portal task，避免误把入口或终态任务当出口。
- (verified) `EventRunner.update()` 修正 COMPLETE/FAIL 分支缩进，避免 `_clear()` 脱离 COMPLETE 块造成语法错误或生命周期错乱。

**CODEBASE.md 更新内容：**
- 更新 `core/events/*` 注意事项，记录 `tick.event_tasks` 的写入时机。
- 更新 `build_event_tick()`、事件管理 flow、`exit_complete_radius`、Portal Event Current Behavior 和 Event Localization Contract。

**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/events/models.py` | (partial) | (partial) | 2 | 本轮重读 `EventTick` 契约，新增 `event_tasks` 运行时任务快照字段。 |
| `core/events/coordinator.py` | (partial) | (partial) | 2 | 本轮重读事件 detect/localize/memory/scheduler 顺序，确认快照应在 memory 合并后写入。 |
| `core/events/types/portal/handler.py` | (partial) | (partial) | 4 | 本轮重读 wait_result 和传送完成判定，新增已知出口门完成分支和入口距离防误判。 |
| `core/events/runner.py` | (partial) | (partial) | 4 | 本轮重读 COMPLETE/FAIL 生命周期，修正缩进并保留 terminal/requeue 保护。 |

**验证：**
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\events\runner.py core\events\models.py core\events\coordinator.py core\events\types\portal\handler.py core\events\memory.py` 已通过。

## [FEATURE] 2026-05-23 - Portal auto-navigation integration and reset button
### A. SYNC 范围声明
**触发任务：** 用户确认传送门事件基本可用，要求接入自动导航，并在事件管理中增加按钮刷新传送门状态，方便反复测试。
**直接变更文件：**
- `gui/dialogs/event_manager_dialog.py`
- `gui/modes/navigation_mode.py`
- `core/events/coordinator.py`
- `core/events/memory.py`
- `core/events/position_stabilizer.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：**
- 自动导航开启时，传送门事件与手动测试走同一套 detect/localize/schedule/MOVE_TO/PRESS_KEY/COMPLETE pipeline。
- 事件终态 action 也由导航循环消费，避免 COMPLETE/FAIL 帧同时推进普通路线导航。
- 新增 portal 运行时重置入口，清空任务和定位聚类但不改事件配置。

### C. SYNC 结果
**关键发现：**
- (verified) `navigation_loop()` 已用 `auto_navigation_enabled or portal_test_controller.active` 控制 `EventCoordinator.update(..., run_handlers=...)`，所以自动导航已有 handler 推进入口。
- (verified) 原逻辑只把 `MOVE_TO/CLICK_SCREEN/PRESS_KEY/WAIT` 视为事件接管；`COMPLETE/FAIL` 不进入事件执行分支，手动测试终态停止和自动导航收口不稳定。
- (verified) 事件窗口只有完整刷新和测试传送门按钮，没有运行时清空已完成/忽略 portal 任务和定位聚类的入口，导致同一对门反复测试需要重启或等待冷却。

**实际变更：**
- (verified) `NavigationModeWidget.navigation_loop()` 将事件 `COMPLETE/FAIL` 也纳入本帧事件占用，先由 `EventActionExecutor` 消费终态并清理 event path overlay；自动导航从下一帧恢复普通路线。
- (verified) `EventManagerDialog` 新增 `reset_portal_requested` 信号和“刷新传送门状态”按钮。
- (verified) `NavigationModeWidget._reset_portal_event_state()` 接收按钮事件，停止手动 portal 测试、调用 coordinator reset、清 overlay、刷新任务表并打印 `portal event state reset` 日志。
- (verified) `EventCoordinator.reset_event_type()` 清理当前同类型 handler、memory tasks、position clusters、last detections/observations、last selected task 和 last action。
- (verified) `EventMemory.clear_event_type()` 清空指定事件类型的任务和对应节流日志；`EventPositionStabilizer.clear_event_type()` 清空指定事件类型定位聚类。

**CODEBASE.md 更新内容：**
- 更新 `EventManagerDialog` 和 `NavigationModeWidget` 注意事项。
- 更新 `core/events/*` 运行时 reset 入口说明。
- 更新事件管理 UI Flow，加入“刷新传送门状态”和事件终态 action 收口。
- 更新 Event Manager UI 说明，记录“刷新传送门状态”按钮语义。

**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/dialogs/event_manager_dialog.py` | (partial) | (partial) | 3 | 本轮重读 footer 按钮和信号，新增 portal 状态重置信号和按钮。 |
| `gui/modes/navigation_mode.py` | (partial) | (partial) | 7 | 本轮重读自动导航事件接管和终态分支，接入 portal reset 并让 COMPLETE/FAIL 占用事件帧。 |
| `core/events/coordinator.py` | (partial) | (partial) | 3 | 本轮新增按事件类型清理 coordinator 运行时状态的入口。 |
| `core/events/memory.py` | (partial) | (partial) | 4 | 本轮新增指定事件类型任务清理入口，用于反复测试清除 completed/ignored 冷却状态。 |
| `core/events/position_stabilizer.py` | (partial) | (partial) | 2 | 本轮新增指定事件类型定位聚类清理入口，避免刷新后复用旧 portal 定位样本。 |

**验证：**
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\dialogs\event_manager_dialog.py gui\modes\navigation_mode.py core\events\coordinator.py core\events\memory.py core\events\position_stabilizer.py` 已通过。

## [BUGFIX] 2026-05-23 - Portal pre-interaction mapped point click
### A. SYNC 范围声明
**触发任务：** 用户反馈传送门事件有时已经进入交互半径但游戏没有触发交互，需要降低交互半径下限，并在按 `D` 前点击一次映射的传送门点。

**直接变更文件：**
- `core/motion_controller.py`
- `core/events/config.py`
- `core/events/types/portal/config.py`
- `core/events/types/portal/definition.py`
- `core/events/types/portal/handler.py`
- `core/events/models.py`
- `core/events/action_executor.py`
- `gui/modes/navigation_mode.py`
- `gui/dialogs/event_manager_dialog.py`
- `map_data/A1/event_config.json`
- `map_data/Aa/event_config.json`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：**
- 事件管理页允许把 `interact_radius` 调到 1，用于推迟按 `D` 直到更贴近传送门。
- 传送门 handler 进入交互阶段后先发出一次带 metadata 的强制映射点点击，再等待 `portal_point_click_wait_ms` 后按 `D`。
- 强制点击走事件专用映射，不使用正常移动的最小点击半径，避免把“点传送门”放大成“朝传送门方向走一步”。

### C. SYNC 结果
**根因确认：**
- (verified) `PortalEventDefinition.config_schema()` 原 `interact_radius` 下限为 5，无法继续缩小按 `D` 的距离阈值。
- (verified) `MotionController.move_to_map_target()` 在目标距离极近时会返回 `None`，且正常移动映射会应用 `movement_min_click_radius`，不适合作为“点击映射传送门点”。
- (verified) 事件 `MOVE_TO` 原本只传目标点，不能表达“这是一次强制交互点点击，不是寻路移动点击”。

**实际变更：**
- (verified) `PortalEventDefinition.config_schema()` 将 `interact_radius` 下限降到 1，并新增可配置 `portal_point_click_wait_ms`。
- (verified) `PortalEventConfig` 与默认事件配置新增 `portal_point_click_wait_ms=350`。
- (verified) `PortalEventHandler` 在进入 `interact_radius` 后先返回 `EventAction.move_to(..., metadata={"force_click_target": True})`，随后等待 `portal_point_click_wait_ms`，再发送 `D`。
- (verified) `EventAction.move_to()` 支持 metadata，`EventActionExecutor` 将 metadata 传给 GUI move callback。
- (verified) `NavigationModeWidget._execute_event_move_to()` 对 `force_click_target` 调用 `MotionController.click_map_target_once()`，并记录 `event forced target click` 日志。
- (verified) `MotionController.click_map_target_once()` 用地图距离和 `movement_scale_factor` 精确映射目标点，不应用 `movement_min_click_radius`；玩家与传送门重叠时点击 `game_screen_center`。
- (verified) A1/Aa 的 `event_config.json` 写入 `portal_point_click_wait_ms=350`，事件管理页摘要显示该参数。

**CODEBASE.md 更新内容：**
- 更新 Input Control Current Notes，记录 `click_map_target_once()` 的事件专用语义。
- 更新 Event Manager UI，记录 `interact_radius` 下限和 `portal_point_click_wait_ms`。
- 更新 Portal Event Current Behavior，记录“强制映射点点击 -> 等待 -> 按 D”的传送门交互顺序。

**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/motion_controller.py` | (partial) | (partial) | 2 | 本轮重读 map-to-screen 点击链路，新增事件专用映射点点击，避免正常移动最小半径影响交互点点击。 |
| `core/events/types/portal/handler.py` | (partial) | (partial) | 5 | 本轮重读进入交互半径后的状态机，新增 mapped point click 和点击后等待。 |
| `core/events/types/portal/definition.py` | (partial) | (partial) | 2 | 本轮重读 schema，降低 `interact_radius` 下限并新增等待参数。 |
| `gui/modes/navigation_mode.py` | (partial) | (partial) | 8 | 本轮重读事件 move callback，新增 metadata 分支以区分事件交互点击和普通事件寻路移动。 |
| `gui/dialogs/event_manager_dialog.py` | (partial) | (partial) | 4 | 本轮重读参数摘要字段，加入 `portal_point_click_wait_ms`。 |

**验证：**
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\motion_controller.py core\events\config.py core\events\types\portal\config.py core\events\types\portal\definition.py core\events\types\portal\handler.py gui\modes\navigation_mode.py gui\dialogs\event_manager_dialog.py` 已通过。

## [BUGFIX] 2026-05-23 - Portal final approach repeat click
### A. SYNC 范围声明
**触发任务：** 用户反馈 20:34 之后传送门测试到达附近但不会按 `D`；进一步确认当前距离仍大于 `interact_radius`，正确行为应继续点击进入目标点，而不是直接兜底按 `D`。

**直接变更文件：**
- `core/events/path_mover.py`
- `core/events/types/portal/handler.py`
- `gui/modes/navigation_mode.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：**
- 保留 `interact_radius` 的严格语义：只有 `distance <= interact_radius` 才进入“点击映射传送门点 -> 按 D”。
- 只在 portal 最终靠近阶段允许同 subgoal 重复真实点击，避免停在 7px 但不再点击。
- 移除中断前临时写入的 `interact_stall_radius/interact_stall_ms`，不引入额外半径兜底判断。

### C. SYNC 结果
**根因确认：**
- (verified) 日志显示目标 `(3401,2248)`，玩家最终停在 `(3398.22,2254.47)`，距离 `7.04`。
- (verified) 当时 `interact_radius=1`，因此 `PortalEventHandler` 正确地没有进入按 `D` 分支，而是持续返回 `approach portal interact radius`。
- (verified) `EventPathMover.step()` 旧逻辑要求 cooldown 到期且 subgoal 改变至少 8px、或偏差超过 48px 才继续点击；最终阶段 subgoal 仍是 `(3401,2248)`，所以 action 被执行但没有真实 `event move click`。

**实际变更：**
- (verified) 删除临时 `interact_stall_radius/interact_stall_ms` 配置、schema 和解析字段，避免和严格交互半径语义冲突。
- (verified) `EventPathMover.step()` 新增 `force_repeat_click=False` 参数；为 True 时保留 260ms 冷却，但绕过 subgoal 变化阈值。
- (verified) `PortalEventHandler` 在 `distance > interact_radius` 的最终靠近 action 上附加 `metadata={"force_repeat_click": True}`。
- (verified) `NavigationModeWidget._execute_event_move_to()` 将 metadata 转交给 `EventPathMover.step()`。

**CODEBASE.md 更新内容：**
- 更新 Portal Event Current Behavior，记录最终靠近阶段会重复同 subgoal 点击直到进入 `interact_radius`。
- 新增 Event Move Repeat Click 说明，明确该能力只绕过 subgoal 变化阈值，不绕过点击冷却，也不改变按 `D` 条件。

**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/events/path_mover.py` | (partial) | (partial) | 2 | 本轮重读 `step()` 点击节流条件，新增 `force_repeat_click` 以解决最终目标不变导致不再真实点击。 |
| `core/events/types/portal/handler.py` | (partial) | (partial) | 6 | 本轮重读最终靠近分支，保留严格 `interact_radius`，只给移动 action 标记重复点击。 |
| `gui/modes/navigation_mode.py` | (partial) | (partial) | 9 | 本轮重读事件 move callback，转发 `force_repeat_click` metadata 到 EventPathMover。 |

**验证：**
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\events\path_mover.py core\events\models.py core\events\action_executor.py core\events\config.py core\events\types\portal\config.py core\events\types\portal\definition.py core\events\types\portal\handler.py core\motion_controller.py gui\modes\navigation_mode.py gui\dialogs\event_manager_dialog.py` 已通过。
## [SYNC] 2026-05-23 21:33 - 传送门事件四阶段案例文档
### A. SYNC 范围声明
**触发任务：** 新增一份以传送门事件为例的事件方法论文档，体现“事件识别、导航触发、事件执行、事件结束”四阶段，并检查当前代码架构是否支持将第 1、2 阶段抽成通用能力。
**直接变更文件：** 待新增 `docs/plans/2026-05-23-portal-event-case-study.md`，并同步 `CODEBASE.md` / `ITERATION_LOG.md`。
**预计连带影响：** 需要重读 `core/events/types/portal/handler.py`、`core/events/types/portal/definition.py`、`core/events/types/portal/config.py`、`core/events/path_mover.py`、`core/events/coordinator.py`、`core/events/models.py`、`gui/modes/navigation_mode.py` 中事件接入点，确认事件生命周期和通用化边界。

### C. SYNC 结果
**关键发现：**
- (verified) 当前 `portal` 已经按完整事件包暴露：`PortalEventDefinition` 对外提供配置和 detector/handler 创建，事件管理 UI 只看到完整 `portal` 事件。
- (verified) 第 1 阶段已经基本通用：`PortalMinimapDetector` 只输出局部 `EventDetection`，`EventPositionStabilizer` 统一通过墙体配准投影到全局地图，`EventMemory` 只接受稳定 `EventObservation`。
- (verified) 第 2 阶段已经有通用核心：`PortalEventHandler` 只返回 `EventAction.move_to()`，`EventPathMover` 负责事件移动的 A*、lookahead、点击节流和 fallback probe。
- (partial) 第 2 阶段仍有 GUI 耦合：`NavigationModeWidget._execute_event_move_to()` 仍持有 `nav_core.wall_layer`、`PathFinder`、`MotionController` 和事件 path overlay 上下文；后续事件增多时应抽成独立事件移动执行桥。
- (verified) 第 3 阶段传送门较简单：靠近后点击映射传送门点、等待、按 `D`，触发和执行几乎合一。
- (verified) 第 4 阶段传送门已有明确 completion strategy：位置变化、环境变化或落在另一个已知 portal 附近，并通过 `complete_teleport_session()` 同时完成入口和出口，防止反复传送。
- (conflict) 旧 `CODEBASE.md` 仍写着 `interaction="click"` 会走主画面 confirmer；本轮重读 `PortalEventHandler` 确认当前实现会强制按键交互，已修正文档避免误导。

**新增文档：**
- `docs/plans/2026-05-23-portal-event-case-study.md`：按“事件识别/定位 -> 导航触发 -> 执行事件 -> 事件结束”四阶段拆解传送门案例，并标注可通用能力、事件特定能力和当前架构风险。

**CODEBASE.md 更新内容：**
- 在目录结构中新增传送门案例文档入口。
- 新增 `Event Four-Phase Methodology` 章节，记录四阶段方法论、1/2 阶段通用化边界和 `NavigationModeWidget._execute_event_move_to()` 的后续抽离风险。
- 修正旧 portal 说明中关于 `interaction="click"` 的过期描述：当前主流程强制按 `D`，大画面 confirmer 只是保留的技术资产/探针路径。

**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/events/types/portal/handler.py` | (partial) | (partial) | 7 | 本轮按四阶段重读状态机：靠近、最终贴近、映射点点击、按 D、等待传送完成。 |
| `core/events/types/portal/definition.py` | (partial) | (partial) | 3 | 本轮确认 `portal` 对外仍是完整事件包，TUI 不暴露内部 detector/handler。 |
| `core/events/types/portal/config.py` | (partial) | (partial) | 2 | 本轮确认识别、定位、靠近、交互、完成和冷却参数分布。 |
| `core/events/path_mover.py` | (partial) | (partial) | 3 | 本轮确认事件移动通用核心：A*、lookahead、fallback probe、repeat click。 |
| `core/events/coordinator.py` | (partial) | (partial) | 2 | 本轮确认事件主链路：detect -> stabilize -> memory -> scheduler -> runner。 |
| `core/events/models.py` | (partial) | (partial) | 2 | 本轮确认 `EventDetection`/`EventObservation`/`EventTask`/`EventAction` 对四阶段的承载关系。 |
| `gui/modes/navigation_mode.py` | (partial) | (partial) | 10 | 本轮确认第 2 阶段动作执行仍耦合在导航页面，是后续抽离风险。 |
| `docs/plans/2026-05-23-portal-event-case-study.md` | PENDING | 浅读 | 1 | 新增案例文档，供后续事件设计和架构检查引用。 |

**验证：**
- 本轮仅新增/更新 Markdown 文档，未运行代码逻辑测试。
## [SYNC] 2026-05-23 21:58 - 途经点改为软锚点并消除事件恢复回头
### A. SYNC 范围声明
**触发任务：** 用户修正导航/事件冲突需求：事件完成后恢复普通导航时不能回到原来的途经点；途经点不再是必须按顺序经过的目标，只作为普通导航和事件导航的 A* 辅助中间锚点。添加顺序仅用于撤销最后一个途经点。
**直接变更文件：** 预计修改 `core/auto_navigator.py`、`core/events/path_mover.py`、`gui/modes/navigation_mode.py`、`gui/modes/navigation/route_overlay.py`，并同步 `CODEBASE.md` / `ITERATION_LOG.md`。
**预计连带影响：** 自动导航目标选择、事件 `MOVE_TO` 路径规划、路线 overlay 当前目标显示、UI 文案和 CODEBASE 中关于 `guide_points` 的语义说明都需要同步；`required_points` 仍保留顺序阶段门语义。

### C. SYNC 结果
**根因确认：**
- (verified) `AutoNavigator._select_segment_target()` 旧逻辑会返回 `("guide", guide_point)`，并用 `guide_index` 按添加顺序推进途经点。
- (verified) 事件完成后普通导航从下一帧恢复时仍使用 `AutoNavigator` 当前 `guide_index`，因此可能回头追事件发生前的旧途经点。
- (verified) `EventPathMover` 原本只对事件目标直接 A*，无法复用路线中的辅助点；用户要求事件导航也可以借助这些点作为中间锚点。

**实际变更：**
- 新增 `core/anchor_path.py`，提供 `plan_path_with_optional_anchors()`：先尝试直接 A*；直接失败时才筛选方向合理的软锚点并搜索锚点组合；仍失败则返回空，让调用方走原 fallback。
- `AutoNavigator._select_segment_target()` 现在只返回当前必经点或出口；`guide_points` 不再成为 `current_target_kind="guide"`。
- `AutoNavigator._align_route_to_current_position()` 只推进已经靠近的必经点，不再根据途经点/路线段修改 `guide_index`。
- `AutoNavigator._plan_segment()` 通过 `plan_path_with_optional_anchors()` 把 `guide_points` 作为软锚点参与直接 A* 失败后的辅助规划。
- `EventPathMover.step()` 新增 `soft_anchors` 参数，事件移动同样可以在直接 A* 失败时借用途经点辅助规划。
- `NavigationModeWidget._execute_event_move_to()` 将当前路线 `guide_points` 传给事件移动器；事件完成后恢复普通导航时不会回头追途经点。
- `route_overlay.py` 将途经点显示为 `A1/A2/...` 辅助点，不再按 `current_guide_index` 显示已完成或当前目标。
- 导航 UI 文案改为“请在地图上点击A*辅助点；顺序仅用于撤销”。

**CODEBASE.md 更新内容：**
- 新增 `core/anchor_path.py` 目录和模块说明。
- 更新 `NavigationModeWidget`、`route_overlay.py`、`core/auto_navigator.py` 的职责/注意事项，明确 `guide_points` 是软锚点，不是顺序目标。
- 更新 `AutoNavigator.update()`、`_align_route_to_current_position()`、`_select_segment_target()` 函数说明，移除旧 `_candidate_index_from_nearest_route_segment()` 描述。
- 更新传送门案例文档，明确事件移动可复用软锚点，但事件完成恢复不能回头追途经点。

**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/auto_navigator.py` | (partial) | (partial) | 4 | 本轮重读目标选择、路线对齐、规划和推进逻辑，将途经点从顺序目标改为软锚点。 |
| `core/events/path_mover.py` | (partial) | (partial) | 4 | 本轮接入 `soft_anchors`，让事件 MOVE_TO 复用途经点辅助规划。 |
| `core/anchor_path.py` | PENDING | 浅读 | 1 | 新增通用软锚点路径规划 helper，直接 A* 失败后才尝试锚点组合。 |
| `gui/modes/navigation_mode.py` | (partial) | (partial) | 11 | 本轮重读事件 move callback 和路线 UI 文案，将路线 guide_points 传入事件移动器。 |
| `gui/modes/navigation/route_overlay.py` | (partial) | (partial) | 2 | 本轮重读途经点 overlay，改为 A* 辅助点显示，不再显示完成/当前状态。 |
| `docs/plans/2026-05-23-portal-event-case-study.md` | 浅读 | 浅读 | 2 | 补充事件移动阶段的软锚点语义。 |

**验证：**
- `python -m py_compile core\anchor_path.py core\auto_navigator.py core\events\path_mover.py gui\modes\navigation_mode.py gui\modes\navigation\route_overlay.py` 已通过。
- 未运行逻辑/单元测试，等待用户在游戏内实测导航恢复和传送门事件移动。

## [SYNC] 2026-05-23 22:11 - 软锚点参与规划而非失败兜底
### A. SYNC 范围声明
**触发任务：** 用户确认“都要借助锚点”：普通导航和事件导航都应把途经点作为路径规划候选中间节点，而不是只有直接 A* 失败时才尝试。
**直接变更文件：** `core/anchor_path.py`、`CODEBASE.md`、`ITERATION_LOG.md`、`docs/plans/2026-05-23-portal-event-case-study.md`。
**预计连带影响：** `core/auto_navigator.py` 和 `core/events/path_mover.py` 已统一调用 `plan_path_with_optional_anchors()`，因此只需要调整该共用规划器即可影响普通导航和事件移动；文档中所有“直接失败才用锚点”的旧表述必须同步修正。

### C. SYNC 结果
**关键发现：**
- (verified) 旧新增的 `plan_path_with_optional_anchors()` 会在 `direct_path` 存在时立即返回，导致 `guide_points` 仍只是失败兜底，没有真正参与规划。
- (verified) 普通导航和事件移动已经共用 `plan_path_with_optional_anchors()`，所以修正共用层即可同时覆盖自动导航和事件 `MOVE_TO`。

**实际变更：**
- `plan_path_with_optional_anchors()` 现在同时计算直接 A* 和锚点图路径，不再因直接 A* 成功提前跳过锚点。
- `_plan_anchor_graph()` 用状态 `(node_index, used_anchor)` 搜索，`require_anchor=True` 时要求到目标前至少经过一个合理锚点；锚点仍不按 UI 添加顺序强制经过。
- 如果锚点路径存在且长度不超过直接路径 `max_anchor_factor` 倍，则返回 `path_kind="anchor_planned"`；锚点不可达或绕远过多时回退直接路径。
- `CODEBASE.md` 和传送门案例文档已修正为“锚点参与规划但不作为顺序目标”。

**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/anchor_path.py` | 浅读 | (partial) | 2 | 本轮重读并修正软锚点策略：直接路径和锚点图路径并行评估，锚点不再只是失败兜底。 |
| `core/auto_navigator.py` | (partial) | (partial) | 5 | 本轮确认普通导航已通过共用规划器接收软锚点，无需重新引入 guide 目标。 |
| `core/events/path_mover.py` | (partial) | (partial) | 5 | 本轮确认事件 MOVE_TO 已通过共用规划器接收软锚点，传送门事件会同步受益。 |
| `docs/plans/2026-05-23-portal-event-case-study.md` | 浅读 | 浅读 | 3 | 修正阶段 2 中“直接 A* 失败才借助锚点”的旧描述。 |

**验证：**
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\anchor_path.py core\auto_navigator.py core\events\path_mover.py gui\modes\navigation_mode.py gui\modes\navigation\route_overlay.py` 已通过。
- 未运行逻辑/单元测试，等待用户在游戏内验证 `path_kind=anchor_planned` 时的实际路线表现。

## [BUGFIX] 2026-05-23 23:35 - 锚点分段 A* 不再直冲最终目标
### A. SYNC 范围声明
**触发任务：** 用户反馈自动导航仍然直线冲目标，完全忽视辅助锚点；正确语义是 A* 应通过中间锚点分段规划，锚点和 A* 不应是独立候选方案。
**直接变更文件：** `core/anchor_path.py`、`core/auto_navigator.py`、`core/events/path_mover.py`、`gui/modes/navigation_mode.py`、`CODEBASE.md`、`ITERATION_LOG.md`、`docs/plans/2026-05-23-portal-event-case-study.md`。
**预计连带影响：** 普通导航和事件 `MOVE_TO` 都会优先使用锚点分段图；锚点链断开时先走到当前可达的最远锚点或朝下一个锚点短探测，到达后重规划，而不是回退为长距离直冲最终目标。

### C. SYNC 结果
**根因确认：**
- (verified) 最近运行日志只有最终鼠标点击和 `map_delta`，没有打印规划层 `path_kind`，所以运行日志能看出一直朝最终目标方向点，但不能定位规划层原因。
- (verified) 离线探针使用 `map_data/Aa/route.json` 和 `map_data/Aa/map_data.npz` 复现：旧锚点图从起点到出口返回 `None`，随后运行时可能回退直接/局部目标方向。
- (verified) 具体断点包括 `(2908,2280) -> (3020,2383)` A* 判定无路，以及 `(3381,2226) -> (3471,2320)` 在 `explored_map` 约束下不可走。
- (verified) 旧 `_candidate_anchors()` 还会按“起点到最终目标的直线投影”过滤锚点，弯路锚点容易被筛掉；这和用户要求的“通过锚点往目标走”冲突。

**实际变更：**
- `plan_path_with_optional_anchors()` 改为优先构建锚点分段 A* 图；只有无可用锚点时才直接 A* 到真实目标。
- `_candidate_anchors()` 不再用起点到终点直线投影过滤，只保留“锚点距离目标有实际进展、离当前位置不过近、去重”的条件。
- `_plan_anchor_graph()` 支持返回 `anchor_planned`、`anchor_partial`、`anchor_probe`：
- `anchor_planned`：锚点链能连到真实目标。
- `anchor_partial`：只能先走到当前可达的最远锚点。
- `anchor_probe`：连第一段锚点 A* 都不可用时，先朝下一个合理锚点做短探测。
- `AutoNavigator` 新增 `current_path_goal/current_anchor_count`，当 `anchor_partial/anchor_probe` 到达当前路径终点时清空路径并重新规划下一段。
- `EventPathMover` 同样识别 `anchor_partial/anchor_probe` 当前段终点，到达后重新规划，避免传送门事件移动再次直冲事件点。
- 导航状态栏新增 `path:<path_kind>/A<count>`，便于实测时确认是否走了 `anchor_partial/anchor_planned`。

**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/anchor_path.py` | (partial) | (partial) | 3 | 本轮用 Aa 路线离线探针确认旧锚点图断点，改为锚点分段优先和 partial/probe 返回。 |
| `core/auto_navigator.py` | (partial) | (partial) | 6 | 本轮新增锚点段临时目标，到达锚点段终点后重规划，不再把最终目标作为唯一到达条件。 |
| `core/events/path_mover.py` | (partial) | (partial) | 6 | 本轮让事件移动也在锚点段终点后重规划，保持和普通导航一致。 |
| `gui/modes/navigation_mode.py` | (partial) | (partial) | 12 | 本轮状态栏增加 path_kind/anchor_count 诊断显示。 |

**验证：**
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\anchor_path.py core\auto_navigator.py core\events\path_mover.py gui\modes\navigation_mode.py gui\modes\navigation\route_overlay.py` 已通过。
- 离线探针：`Aa` 起点 `(2514,2666)` 到出口 `(3892,2032)` 现在返回 `anchor_partial/A3`，路径先到 `(2908,2280)`，不再直接返回最终出口路径。

## [SYNC] 2026-05-23 23:58 - 主目标仲裁与有序锚点走廊
### A. SYNC 范围声明
**触发任务：** 用户明确锚点、必经点、事件必须区分职责：锚点只作为路线塑形点，不能和必经点/事件抢主目标；事件应作为动态必经点参与距离仲裁，不能一识别就强制打断当前路线；事件执行时会中断普通导航。
**直接变更文件：** 预计涉及 `core/anchor_path.py`、`core/auto_navigator.py`、`core/events/path_mover.py`、`gui/modes/navigation_mode.py`、`CODEBASE.md`、`ITERATION_LOG.md`、必要时同步 `docs/plans/2026-05-23-portal-event-case-study.md`。
**预计连带影响：** 普通导航当前目标选择、事件执行入口、事件 MOVE_TO、路线 overlay/status 诊断、传送门案例文档中的阶段 2 导航语义。

### C. SYNC 结果
**根因确认：**
- (verified) `core/anchor_path.py` 上一版仍是“候选锚点图 + 最短路/Dijkstra”模型，会按距离和可达性跳过用户手工放置的中间锚点；这和“锚点是定制路径骨架”冲突。
- (verified) `NavigationModeWidget.navigation_loop()` 之前只要事件 handler 返回可接管 action，就直接阻断普通自动导航；事件没有作为“动态必经点”参与和当前普通主目标的距离仲裁。
- (verified) 事件检测/记忆本身可以继续运行，不应因为事件当前不执行就丢失 overlay 或任务表状态。

**实际变更：**
- `core/anchor_path.py` 重写为有序锚点走廊：`guide_points` 保留 UI 添加顺序，当前位置之前的锚点视为已路过，当前主目标投影之后的锚点会被过滤；有前方锚点时只规划到下一个锚点，返回 `anchor_step`。
- `anchor_probe` 只用于下一个锚点 A* 暂不可达时的短探测；没有前方锚点时才直接 A* 到当前主目标。
- `AutoNavigator` 新增 `segment_target_for_position()`，给事件仲裁预览当前普通目标，不推进真实 `required_index`。
- `AutoNavigator` 和 `EventPathMover` 都把 `anchor_step/anchor_probe` 当作临时段，抵达段终点后清空路径并重新规划。
- `EventCoordinator.update()` 增加 `allowed_task_ids`，事件检测、定位、memory、overlay 继续运行，但只有允许集合内的任务会推进 handler；active/running 任务继续执行到终态。
- `NavigationModeWidget._allowed_event_task_ids()` 实现主目标仲裁：手动测试不限制；普通自动导航时，事件任务距离不大于当前普通主目标距离才允许执行；已有 active 事件始终允许继续。
- `CODEBASE.md` 与传送门案例文档同步为“四阶段事件 + 动态必经点仲裁 + 有序锚点走廊”的当前语义。

**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/anchor_path.py` | (partial) | (partial) | 4 | 本轮废弃锚点图最短路模型，改为用户顺序锚点走廊和 `anchor_step` 分段推进。 |
| `core/auto_navigator.py` | (partial) | (partial) | 7 | 本轮新增无副作用主目标预览，并让 `anchor_step` 到达后重规划。 |
| `core/events/coordinator.py` | 浅读 | (partial) | 2 | 本轮新增 `allowed_task_ids` 运行过滤，检测/显示与 handler 执行解耦。 |
| `core/events/path_mover.py` | (partial) | (partial) | 7 | 本轮同步 `anchor_step` 作为事件移动临时段终点，避免停在锚点后不重规划。 |
| `gui/modes/navigation_mode.py` | (partial) | (partial) | 13 | 本轮新增事件/普通目标距离仲裁，事件作为动态必经点，不再一识别就抢控制。 |
| `docs/plans/2026-05-23-portal-event-case-study.md` | 浅读 | 浅读 | 4 | 同步阶段 2：事件接管前先参与主目标仲裁，锚点按有序走廊推进。 |
| `CODEBASE.md` | 浅读 | 浅读 | 6 | 同步新增函数、事件 flow、锚点语义和结构说明。 |

**验证：**
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\anchor_path.py core\auto_navigator.py core\events\coordinator.py core\events\path_mover.py gui\modes\navigation_mode.py` 已通过。
- 未运行逻辑/单元测试，等待游戏内验证普通导航、传送门事件触发顺序和锚点推进是否符合预期。

## [SYNC] 2026-05-24 00:40 - 导航卡住：路线进度与锚点探测修正
### A. SYNC 范围声明
**触发任务：** 用户反馈新锚点逻辑运行后卡住且日志逻辑混乱；已读运行日志确认事件未参与，问题集中在普通导航的必经点完成判断和不可达锚点探测。
**直接变更文件：** `core/anchor_path.py`、`core/auto_navigator.py`、`CODEBASE.md`、`ITERATION_LOG.md`，必要时涉及 `core/events/path_mover.py`。
**预计连带影响：** 普通导航不再回头追已经按锚点进度越过的必经点；`anchor_probe` 不再长距离点击不可达锚点；运行日志应能看到当前主目标、路径类型和锚点段。

### C. SYNC 结果
**根因确认：**
- (verified) 最新 `event_runtime.log` 只有事件系统初始化和 detector ready，没有 detection/task/action/arbitration，说明这次卡住不是传送门事件接管导致。
- (verified) `runtime.log` 中点击方向先右下、再右上、再左上，符合普通导航目标/锚点段切换，而不是输入点击失败。
- (verified) 离线探针确认：当位置已在后段锚点附近但早期必经点未按距离命中时，旧逻辑仍可能回头追早期必经点。
- (verified) 离线探针确认：`A10 -> A11`、`A15 -> A16` 在墙图/探索图约束下会触发 `anchor_probe`；旧 probe 直接点击不可达锚点，容易硬冲墙。

**实际变更：**
- `core/anchor_path.py` 新增 `anchor_route_progress()`，为自动导航提供按锚点折线的路线进度。
- `anchor_probe` 改为朝不可达锚点做约 84 像素短探测，不再直接点击不可达锚点坐标。
- `AutoNavigator` 新增单调 `route_progress`，只允许路线进度前进不后退。
- 必经点完成判断从“只看距离”升级为“距离命中或路线进度已越过”，防止人物已到后段后回头追旧必经点。
- `segment_target_for_position()` 也使用进度预览，但不推进真实 `required_index`，保证事件仲裁无副作用。
- 自动导航每次规划段写 `auto path planned` 日志，包含目标类型、目标坐标、路径类型、路径终点、锚点数、必经点 index 和路线进度。

**离线验证：**
- 从 `(3109,2353)`、`(2908,2280)`、`(3381,2226)` 预览路线，3 个必经点都会按进度视为已越过，当前目标变为出口。
- `A10 -> A11` probe 从直接点击 `(3020,2383)` 改为短探测点 `(2970,2337)`。
- `A15 -> A16` probe 从直接点击 `(3471,2320)` 改为短探测点 `(3439,2287)`。

**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/anchor_path.py` | (partial) | (partial) | 5 | 本轮新增锚点路线进度 helper，并把不可达锚点 probe 改为短探测。 |
| `core/auto_navigator.py` | (partial) | (partial) | 8 | 本轮用单调 route_progress 防止回头追旧必经点，并补自动导航规划日志。 |
| `CODEBASE.md` | 浅读 | 浅读 | 7 | 同步路线进度、短 probe 和 auto path planned 日志语义。 |

**验证：**
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\anchor_path.py core\auto_navigator.py core\events\path_mover.py gui\modes\navigation_mode.py` 已通过。
- 未运行逻辑/单元测试，等待用户游戏内验证；重点看 `logs/event_runtime.log` 中 `auto path planned` 是否仍出现旧必经点回头。
## [DESIGN] 2026-05-24 01:04 - 导航冲突方案 B/C 设计
### A. 本轮目标（阅读前声明）
**目标文件：**
- `core/auto_navigator.py`（原因：普通导航状态机、必经点推进、锚点段到达逻辑是当前冲突核心）
- `core/anchor_path.py`（原因：guide_points 走廊、锚点选择、路线进度投影定义了 B/C 两套方案的共同基础）
- `core/events/path_mover.py`（原因：事件移动复用锚点规划，但状态独立，需要确认复用边界）
- `core/events/coordinator.py`、`core/events/runner.py`、`core/events/scheduler.py`、`core/events/types/portal/handler.py`（原因：事件作为动态必经点/任务队列的现有实现依据）
- `gui/modes/navigation_mode.py`、`gui/modes/navigation/event_adapter.py`（原因：事件和普通导航的仲裁、执行入口、UI 集成在这里）
- `map_data/Aa/route.json`（原因：用实际 route 数据解释 B/C 方案如何处理 required_points、guide_points、exit）

**本轮想弄清楚：** 在不立即改代码的前提下，基于现有源码分别设计方案 B「统一路线进度模型」和方案 C「统一任务队列状态机」，明确改动范围、状态模型、数据流、风险和迁移顺序，写入本地文档供用户选择。
### C. 本轮发现
**关键发现：**
- (verified) `AutoNavigator` 当前同时承担普通导航定位状态、主目标选择、路径跟随和点击节流；`_select_segment_target()` 只会在当前 `required_points[required_index]` 与出口之间选择，不理解事件目标。
- (verified) `EventCoordinator` 当前负责检测、定位、memory、scheduler 和 runner；事件执行与普通导航之间的最终仲裁发生在 `NavigationModeWidget._allowed_event_task_ids()` 和 `event_blocks_auto_navigation`，不是在核心层统一完成。
- (verified) `EventPathMover` 和 `AutoNavigator` 都调用 `plan_path_with_optional_anchors()`，但两者各自维护 path/path_goal/click cooldown，因此共享规划算法但不共享“已消费锚点”的状态。
- (verified) `anchor_path._ordered_corridor_anchors()` 内部跳过锚点的半径约 8 像素，而 `AutoNavigator._follow_segment()` 用 `arrival_radius=26` 判断锚点段到达；这是 `(2577,2474)` 反复规划的直接设计缺口。

**产出文档：**
- `docs/plans/2026-05-24-navigation-route-progress-option-b-design.md`：方案 B，保留现有执行器，新增统一路线进度/锚点消费模型。
- `docs/plans/2026-05-24-navigation-task-queue-option-c-design.md`：方案 C，把 required、exit、event 全部抽象成统一 NavigationTask，由统一 controller 调度。

**更新了 CODEBASE.md：** §2 目录图新增两个设计文档；§17 新增 Navigation Conflict Design Options，记录 B/C 的源码依据、主要改动范围和推荐选择。

**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/auto_navigator.py` | (partial) | (partial) | 9 | 本轮确认其仍同时负责主目标选择与移动执行，是 B/C 方案拆分边界的核心依据。 |
| `core/anchor_path.py` | (partial) | (partial) | 6 | 本轮确认锚点跳过半径与导航到达半径不一致，且函数没有锚点消费状态。 |
| `core/events/path_mover.py` | (partial) | (partial) | 8 | 本轮确认事件 MOVE_TO 与普通导航复用锚点规划但运行时路径状态分离。 |
| `core/events/coordinator.py` | (partial) | (partial) | 3 | 本轮确认事件检测/记忆/执行入口目前仍由 allowed_task_ids 过滤运行，而非统一任务调度。 |
| `core/events/runner.py` | 浅读 | (partial) | 2 | 本轮确认 handler 生命周期和 COMPLETE/FAIL 更新 memory，可在方案 C 中由统一 controller 调用。 |
| `core/events/scheduler.py` | 浅读 | (partial) | 2 | 本轮确认事件内部 scheduler 只按 running/priority/distance 选事件，不理解普通路线。 |
| `core/events/memory.py` | (partial) | (partial) | 3 | 本轮确认事件 task 生命周期和传送门成对完成逻辑可作为 NavigationTask 的动态来源。 |
| `core/events/types/portal/handler.py` | (partial) | (partial) | 5 | 本轮确认传送门 handler 仍包含靠近、点击门点、按 D、等待完成四段，方案 C 后期可拆出靠近阶段。 |
| `gui/modes/navigation_mode.py` | (partial) | (partial) | 14 | 本轮确认 UI 层承担事件/普通导航仲裁、事件 MOVE_TO 执行和 overlay 刷新，是方案 C 最大迁移点。 |
| `gui/modes/navigation/event_adapter.py` | 浅读 | 浅读 | 2 | 本轮确认事件接管规则只按 EventAction 类型判断，未承载路线语义。 |
| `map_data/Aa/route.json` | 浅读 | 浅读 | 3 | 本轮使用 Aa 实际 required/guide/exit 数据说明方案 B 如何处理 `(2577,2474)` 卡点。 |
| `docs/plans/2026-05-24-navigation-route-progress-option-b-design.md` | PENDING | 浅读 | 1 | 本轮新增，记录保守统一路线进度方案和迁移步骤。 |
| `docs/plans/2026-05-24-navigation-task-queue-option-c-design.md` | PENDING | 浅读 | 1 | 本轮新增，记录统一任务队列状态机方案和迁移步骤。 |
## [PLAN] 2026-05-24 01:16 - 方案 C 统一任务队列实施计划
### A. 本轮目标（阅读前声明）
**目标文件：**
- `docs/plans/2026-05-24-navigation-task-queue-option-c-design.md`（原因：用户已选择方案 C，需要转成详细实施计划）
- `core/auto_navigator.py`（原因：当前普通导航状态机将被 facade/移动执行器化）
- `core/events/coordinator.py`、`core/events/runner.py`、`core/events/memory.py`（原因：事件检测/记忆保留，执行调度要接入统一任务控制器）
- `core/events/path_mover.py`（原因：事件移动逻辑将并入统一 MovementExecutor 或作为兼容壳）
- `gui/modes/navigation_mode.py`、`gui/modes/navigation/event_adapter.py`（原因：当前 UI 层仲裁需要被 NavigationTaskController 替代）

**本轮想弄清楚：** 将已选择的方案 C 拆成可执行、可分阶段验证的本地实施计划，明确每阶段文件范围、验证方式、回滚边界和用户手动测试点；本轮不修改运行逻辑。
### C. 本轮发现
**关键发现：**
- (verified) 方案 C 不能直接从 UI 主循环删除旧仲裁，否则会同时扰动普通导航、传送门事件和手动测试按钮；计划必须先做兼容层和影子模式。
- (verified) `EventPathMover` 是方案 C 最安全的第一个迁移点，因为它只服务事件 MOVE_TO，且可在不改 `_execute_event_move_to()` 外部调用的情况下委托新 `MovementExecutor`。
- (verified) `EventCoordinator.update()` 当前把 observe 和 run handler 混在一起；方案 C 实施前必须拆出 `observe()` 与 `run_task()`，并保留 `update()` 兼容旧调用。
- (verified) `NavigationModeWidget` 当前有两处真实鼠标移动执行入口：事件 `_execute_event_move_to()` 和普通 `auto_action` 消费；方案 C 必须最终统一成 `NavigationIntent` 消费。

**产出文档：**
- `docs/plans/2026-05-24-navigation-task-queue-option-c-implementation-plan.md`：方案 C 详细实施计划，包含阶段 0 到阶段 12、每阶段文件范围、验证命令、手动验收和回滚策略。

**更新了 CODEBASE.md：** §2 新增实施计划文档；§17 记录用户已选择方案 C，并说明 active implementation plan 和兼容层优先的执行策略。

**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `docs/plans/2026-05-24-navigation-task-queue-option-c-design.md` | 浅读 | 浅读 | 2 | 本轮将设计转为分阶段实施计划，明确先兼容后替换。 |
| `docs/plans/2026-05-24-navigation-task-queue-option-c-implementation-plan.md` | PENDING | 浅读 | 1 | 本轮新增，作为后续方案 C 开发的 active plan。 |
| `core/auto_navigator.py` | (partial) | (partial) | 10 | 本轮确认第一批不直接重写，先通过 facade/影子模式降低风险。 |
| `core/events/path_mover.py` | (partial) | (partial) | 9 | 本轮确认可作为 MovementExecutor 的首个兼容委托点。 |
| `core/events/coordinator.py` | (partial) | (partial) | 4 | 本轮确认必须拆 observe/run_task，保留 update 兼容。 |
| `gui/modes/navigation_mode.py` | (partial) | (partial) | 15 | 本轮确认 UI 接入需先 shadow mode，再切换 NavigationIntent，最后清理旧仲裁。 |

## [SYNC] 2026-05-24 09:05 — 方案 C 统一导航任务控制器收尾同步

### A. SYNC 范围声明
**触发任务：** 用户要求继续完成方案 C，并明确不保留旧兼容负担；本轮收尾文档同步、过期引用清理和轻量编译验证。

**直接变更文件：**
- `CODEBASE.md`（同步统一导航任务控制器、删除旧模块引用）
- `ITERATION_LOG.md`（记录 SYNC 范围和结果）

**预计连带影响：**
- `gui/modes/navigation_mode.py` 的统一主循环描述需要替换旧 `AutoNavigator`/事件独立执行描述。
- `core/events/coordinator.py` 的事件检测/执行拆分需要更新。
- `core/navigation_tasks/*` 的新任务模型、调度器和移动执行器需要加入目录、模块和 Flow 描述。
- 删除的 `core/auto_navigator.py`、`core/events/path_mover.py`、`core/events/action_executor.py`、`tests/test_auto_navigator.py` 不应再作为当前运行链路出现。

### C. SYNC 结果
**连带重读文件：**
- `core/events/coordinator.py`（确认旧 `update(... allowed_task_ids ...)` 已无人调用，并删除兼容入口）
- `gui/modes/navigation_mode.py`（确认 `_navigation_loop_unified()`、`_execute_navigation_intent()` 是当前唯一执行链路）
- `core/navigation_tasks/controller.py`、`scheduler.py`、`movement_executor.py`、`route_context.py`、`task_builder.py`、`models.py`（确认方案 C 当前调度、锚点、移动和 intent 协议）
- `core/anchor_path.py`（确认 guide_points 只作为有序软锚点走廊）

**CODEBASE.md 更新内容：** §4 更新事件系统和统一导航任务层说明；§5 修正 `build_event_tick()` 由 `observe()` 写入任务快照；§6 更新自动导航移动点击和事件管理 UI 数据流；§10/§11/§13/§15/§16/§17 清理旧普通导航器、旧事件移动器、旧事件动作执行器和 UI 旧仲裁描述。

**源码清理：** 删除 `EventCoordinator.update(... allowed_task_ids ...)` 和 `_runnable_tasks()` 旧兼容入口，当前事件执行只允许通过 `observe()` + `run_task()` 两段式协议进入统一 `NavigationTaskController`。

**验证命令：**
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile main.py gui\modes\navigation_mode.py gui\modes\navigation\route_overlay.py core\events\coordinator.py core\anchor_path.py core\navigation_tasks\__init__.py core\navigation_tasks\models.py core\navigation_tasks\route_context.py core\navigation_tasks\movement_executor.py core\navigation_tasks\task_builder.py core\navigation_tasks\scheduler.py core\navigation_tasks\controller.py core\navigation_tasks\debug.py utils\route_context_probe.py utils\navigation_task_probe.py`
- `D:\ACloud\.venv\Scripts\python.exe utils\route_context_probe.py --map Aa`
- `D:\ACloud\.venv\Scripts\python.exe utils\navigation_task_probe.py --map Aa`

**验证结果：** 编译通过；路线探针输出 required[0..2] 和 exit 的路线进度；任务探针输出 `required:0`、`required:1`、`required:2`、`exit:main`。

**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/events/coordinator.py` | (partial) | (partial) | 5 | 删除旧兼容 update 入口，事件系统仅保留 observe/run_task 两段式协议。 |
| `gui/modes/navigation_mode.py` | (partial) | (partial) | 16 | 确认统一循环负责定位、事件观察、任务控制器更新和 NavigationIntent 消费。 |
| `core/navigation_tasks/controller.py` | PENDING | 浅读 | 1 | 确认 selected task 切换会重置 MovementExecutor，event 任务通过 run_task 推进 handler。 |
| `core/navigation_tasks/scheduler.py` | PENDING | 浅读 | 1 | 确认 active lock 只保留 event，静态 required/exit 每帧参与重新仲裁。 |
| `core/navigation_tasks/movement_executor.py` | PENDING | 浅读 | 1 | 确认 required/exit/event MOVE_TO 共用 A*、guide-anchor 和点击节流。 |
| `core/navigation_tasks/route_context.py` | PENDING | 浅读 | 1 | 确认 guide_points 投影、路线进度和前方锚点过滤逻辑。 |
| `core/navigation_tasks/task_builder.py` | PENDING | 浅读 | 1 | 确认 route required/exit 和 EventMemory runnable tasks 被合并为 NavigationTask。 |
| `core/anchor_path.py` | PENDING | 浅读 | 1 | 确认锚点只作为有序软走廊，不作为独立完成目标。 |

**新增 Finding：** 当前源码已经完成方案 C 的“无旧兼容负担”边界；历史设计文档中仍保留旧方案描述，但权威当前状态文档 `CODEBASE.md` 和 Python 源码不再引用旧执行链路。


## [SYNC] 2026-05-24 09:31 — 导航卡住诊断日志增强

### A. SYNC 范围声明
**触发任务：** 用户反馈仍有必经点和辅助锚点冲突导致逻辑卡住，需要先观察日志确认问题。
**直接变更文件：** core/navigation_tasks/controller.py, core/navigation_tasks/movement_executor.py, core/anchor_path.py, ITERATION_LOG.md。
**预计连带影响：** 只增加诊断字段，不改变导航决策。

### C. SYNC 结果
**CODEBASE.md 更新内容：** 本次仅增加运行诊断日志，未改变架构契约，暂不更新 CODEBASE。
**诊断新增：** 
av required completed 现在记录 distance/player_progress/target_progress/progress_delta；
av task transition 记录 player/player_progress/target_progress/completed_required；
av movement planned 记录 next_anchor/anchor_count/direct_distance。
**验证命令：** D:\ACloud\.venv\Scripts\python.exe -m py_compile core\navigation_tasks\controller.py core\navigation_tasks\movement_executor.py core\anchor_path.py。
**验证结果：** 编译通过。


## [SYNC] 2026-05-24 09:50 — 必经点顺序和事件插队规则修正

### A. SYNC 范围声明
**触发任务：** 日志显示 required:0/1 被 by_progress 提前完成，且用户明确必经点必须按顺序走，事件只能作为动态必经点穿插在已满足顺序后。
**直接变更文件：** core/navigation_tasks/controller.py, core/navigation_tasks/scheduler.py, ITERATION_LOG.md。
**预计连带影响：** 必经点完成条件和事件候选过滤。

### C. SYNC 结果
**代码变化：** _update_required_progress() 只检查当前最小未完成 required，并且只按距离完成，不再按 route progress 自动完成；NavigationTaskScheduler._eligible_events() 在当前静态目标是 required 时，只允许 route_progress 不超过该 required 附近的事件插队。
**验证命令：** D:\ACloud\.venv\Scripts\python.exe -m py_compile core\navigation_tasks\controller.py core\navigation_tasks\scheduler.py; D:\ACloud\.venv\Scripts\python.exe utils\navigation_task_probe.py --map Aa; D:\ACloud\.venv\Scripts\python.exe utils\route_context_probe.py --map Aa。
**验证结果：** 编译通过；任务探针顺序仍为 required:0, required:1, required:2, exit:main。
**剩余观察点：** 09:44 日志中 
ext_anchor=(3020,2383) 进入 nchor_probe，说明该辅助锚点 A* 不可达或局部墙图误封，下一轮需要根据新日志判断是否引入不可达锚点跳过/降权机制。

## [SYNC] 2026-05-24 11:30 — 导航专用障碍层与高分辨率绘图参数

### A. SYNC 范围声明
**触发任务：** 用户要求从绘图侧改善墙体/地图清晰度，并为窄通道、玩家定位点压墙等 A* 失败场景提供保险方案；核心原则是原始 `wall_layer` 继续用于定位和事件配准，A* 使用派生后的宽容障碍层。

**直接变更文件：**
- `core/navigation_obstacles.py`
- `core/navigation_core.py`
- `core/pathfinder.py`
- `core/stitcher_core.py`
- `gui/navigation_params.py`
- `gui/dialogs/nav_params_dialog.py`
- `gui/modes/navigation_mode.py`
- `gui/modes/mapping_widget.py`
- `gui/modes/mapping/params_adapter.py`
- `core/recognizer_optimized.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：**
- 自动导航和事件 `MOVE_TO` 仍共用 `NavigationTaskController` / `MovementExecutor`，但传入的 `wall_map` 从原始 `wall_layer` 改为 `nav_core.nav_wall_layer`。
- 定位、事件图标投影和地图显示继续使用原始 `wall_layer`，避免墙体侵蚀影响匹配准确率。
- 绘图页新增/恢复的高分辨率参数会影响后续新地图或重置后的地图包坐标体系，因此 `draw_scale` 必须同时保存进 `map_data.npz` 和地图 `config.json`。

### C. SYNC 结果
**代码变化：**
- 新增 `derive_navigation_wall_layer()`，用阈值化 + 可配置 3x3 十字核腐蚀从原始墙图派生 A* 专用墙图。
- `NavigationCore` 加载地图包时保留原始 `wall_layer`，并维护 `nav_wall_layer`；`rebuild_navigation_wall_layer()` 支持参数面板即时重建导航障碍层。
- `NavigationModeWidget._navigation_loop_unified()` 调用 `NavigationTaskController.update(... wall_map=self.nav_core.nav_wall_layer ...)`，普通路线和事件移动都使用同一宽容障碍层。
- `PathFinder` 默认 `wall_shrink_iterations=0`，避免派生墙图和 pathfinder 内部重复侵蚀；新增 `start_clear_radius` 与 `walkable_snap_radius` 用于起点局部清空和起终点吸附。
- `NavConfig` 与导航参数 UI 新增 `nav_wall_erode_iterations`、`path_start_clear_radius`、`path_walkable_snap_radius`，并随地图配置保存。
- `MapStitcher.save_map_package()` 将 `draw_scale` 写入 `map_data.npz`；绘图页参数保存现在叠加 UI 中的 `draw_scale/canvas_size/player_clear_radius/wall_close_kernel_size`。

**CODEBASE.md 更新内容：**
- §2/§4 新增 `core/navigation_obstacles.py`，并修正 `NavigationCore` / `PathFinder` 的职责边界。
- §5 增加 `derive_navigation_wall_layer()`、`MappingWidget._build_mapping_config_with_ui_overrides()` 和 `PathFinder._clear_start_area()` 的函数说明。
- §6 修正自动导航 flow：A* 使用 `nav_core.nav_wall_layer`；绘图保存 flow 记录 `draw_scale` 进入地图包。
- §8 补充 `NavConfig` 的 A* 障碍层与容错参数字段。

**验证命令：**
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\navigation_obstacles.py core\navigation_core.py core\pathfinder.py gui\navigation_params.py gui\dialogs\nav_params_dialog.py gui\modes\navigation_mode.py gui\modes\mapping_widget.py gui\modes\mapping\params_adapter.py core\stitcher_core.py core\recognizer_optimized.py core\navigation_tasks\movement_executor.py`

**验证结果：** 编译通过；只做编译/启动级检查，未执行逻辑单元测试。

**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/navigation_obstacles.py` | PENDING | 浅读 | 1 | 新增 A* 专用障碍层派生函数，确认不会修改原始 `wall_layer`。 |
| `core/navigation_core.py` | (partial) | (partial) | 17 | 确认 `wall_layer` 用于定位/显示，`nav_wall_layer` 用于寻路。 |
| `core/pathfinder.py` | (partial) | (partial) | 2 | 确认默认不再内部侵蚀墙体，并新增起点清空/起终点吸附参数。 |
| `gui/modes/navigation_mode.py` | (partial) | (partial) | 18 | 确认统一导航循环向 task controller 传入 `nav_core.nav_wall_layer`。 |
| `gui/navigation_params.py` | 已有记录 | (partial) | 2 | 确认新增 A* 障碍层和容错参数纳入 config 序列化。 |
| `gui/dialogs/nav_params_dialog.py` | 已有记录 | (partial) | 2 | 确认新增参数控件进入 widget map，可从 UI 调整并保存。 |
| `gui/modes/mapping_widget.py` | (partial) | (partial) | 2 | 确认绘图几何/清晰度控件参与保存，并在空地图时可重建画布。 |
| `core/stitcher_core.py` | (partial) | (partial) | 2 | 确认地图包保存 `draw_scale`，供导航加载同一坐标缩放。 |

## [SYNC] 2026-05-24 11:45 — RecognizerParams 严格字段修正

### A. SYNC 范围声明
**触发任务：** 导航加载地图时报 `RecognizerParams.__init__() got an unexpected keyword argument 'player_clear_radius'`；用户明确不需要兼容旧地图，配置字段应与当前代码严格一致。
**直接变更文件：** `gui/navigation_params.py`, `CODEBASE.md`, `ITERATION_LOG.md`。
**预计连带影响：** 当前绘图页写入的 `player_clear_radius` 可被导航配置模型识别；未知 recognizer 字段仍会抛错，不做静默过滤。

### C. SYNC 结果
**代码变化：** `RecognizerParams` 新增 `player_clear_radius: int = 22`；保留 `NavPreferences(**nav_prefs_data)` 和 `RecognizerParams(**rec_params_data)` 严格构造。
**CODEBASE.md 更新内容：** 记录 `gui/navigation_params.py` 严格字段契约和 `player_clear_radius` 当前字段。
**验证命令：** `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\navigation_params.py gui\modes\navigation_mode.py gui\modes\mapping_widget.py`; `D:\ACloud\.venv\Scripts\python.exe -c "import json; from gui.navigation_params import NavConfig; data=json.load(open('config.json', encoding='utf-8')); cfg=NavConfig.from_dict(data); print(cfg.recognizer_params.player_clear_radius)"`
**验证结果：** 编译通过；当前 `config.json` 加载输出 `20`。

## [SYNC] 2026-05-24 12:20 — 锚点推进配置与导航参数分页

### A. SYNC 范围声明
**触发任务：** 用户确认调整方案：解决锚点规划成功但点击停住的问题，把锚点半径做成配置，把导航参数前端按功能分页，并新增“保存为默认配置”。
**直接变更文件：** `core/navigation_tasks/movement_executor.py`, `gui/navigation_params.py`, `gui/dialogs/nav_params_dialog.py`, `gui/modes/navigation/map_runtime.py`, `gui/modes/navigation_mode.py`, `CODEBASE.md`, `ITERATION_LOG.md`。
**预计连带影响：** 自动导航、事件 `MOVE_TO` 和手动传送门测试继续共用 `MovementExecutor`；新增配置字段写入地图 config，并可合并保存到项目根默认 config。

### C. SYNC 结果
**代码变化：**
- `MovementExecutor` 新增 `anchor_arrival_radius` 和 `force_replan`；锚点/探测/兜底路径目标未到达时，冷却结束后允许重复点击，不再被 `auto_min_click_target_delta` 卡住。
- 卡住恢复目标从最终任务目标改为当前 `path_goal`，避免“走锚点”和“恢复朝终点”互相打架；恢复次数耗尽后下一帧显式重规划。
- `NavConfig` 新增锚点半径、卡住判定间隔、最小有效进度、恢复尝试次数、路径偏离阈值字段，并接入 `_configure_navigation_task_controller()`。
- `NavParametersDialog` 改为 5 个功能页：定位识别、识别算法、移动点击、路径/A*、地图/调试；关键参数行增加可见说明和 tooltip。
- 新增“保存为默认配置”按钮，写入项目根 `config.json` 时保留绘图模式的 `stitcher_params` 等非导航字段；地图配置缺失时会读取根默认配置作为 fallback。

**CODEBASE.md 更新内容：** 更新 §2/§4 `nav_params_dialog.py` 与 `map_runtime.py` 职责，§6 导航参数保存加载流，§8 `NavConfig` 字段，§10 `MovementExecutor` 当前行为，§16 dialog 热点状态。

**验证命令：**
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\navigation_tasks\movement_executor.py gui\navigation_params.py gui\dialogs\nav_params_dialog.py gui\modes\navigation\map_runtime.py gui\modes\navigation_mode.py`
- `D:\ACloud\.venv\Scripts\python.exe -c "import sys; from PySide6.QtWidgets import QApplication; from gui.dialogs.nav_params_dialog import NavParametersDialog; from gui.navigation_params import NavConfig; app=QApplication.instance() or QApplication(sys.argv); d=NavParametersDialog(); d.set_config_to_ui(NavConfig(), (0,0)); print(d.nav_tabs.count(), d.nav_anchor_arrival_radius_spin.value(), d.nav_movement_progress_timeout_spin.value())"`
- `D:\ACloud\.venv\Scripts\python.exe -c "import json; from gui.navigation_params import NavConfig; data=json.load(open('config.json', encoding='utf-8')); cfg=NavConfig.from_dict(data); print(cfg.anchor_arrival_radius, cfg.movement_progress_timeout_ms, cfg.movement_min_progress_delta, cfg.movement_max_recover_attempts, cfg.movement_path_deviation_threshold)"`

**验证结果：** 编译通过；参数弹窗可实例化并显示 5 个分页；当前根配置加载新字段默认值输出 `26 1200 12.0 2 96.0`。

**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/navigation_tasks/movement_executor.py` | 浅读 | (partial) | 2 | 确认锚点路径点击抑制、卡住恢复目标和强制重规划行为已调整。 |
| `gui/navigation_params.py` | (partial) | (partial) | 3 | 确认新增移动执行器调参字段进入地图 config 序列化契约。 |
| `gui/dialogs/nav_params_dialog.py` | (partial) | (partial) | 3 | 确认导航参数 UI 已分页，新增锚点/卡住参数控件和默认保存信号。 |
| `gui/modes/navigation/map_runtime.py` | 深度完整 | (partial) | 2 | 确认新增根默认配置保存/缺省读取 helper，保留地图配置优先级。 |
| `gui/modes/navigation_mode.py` | (partial) | (partial) | 19 | 确认新增默认保存槽和 MovementExecutor 新参数下发。 |
## [SYNC] 2026-05-24 13:50 - 坐标失准独立诊断日志

### A. SYNC 范围声明
**触发任务：** 用户反馈现有日志没有打印坐标匹配不准确的关键证据，需要新增独立日志，并先构思识别坐标失准后重新匹配定位的方案。
**直接变更文件：** `core/navigation_tasks/coordinate_diagnostics.py`, `core/navigation_tasks/controller.py`, `gui/modes/navigation_mode.py`, `docs/plans/2026-05-24-coordinate-drift-diagnostics.md`, `CODEBASE.md`, `ITERATION_LOG.md`。
**预计连带影响：** 导航行为不变；`NavigationTaskController` 额外接收 `FrameRegistration` 并把 raw/trusted/control/target/route projection 写到独立日志，后续用这些证据决定是否启用强制全局重匹配。

### C. SYNC 结果
**代码变化：**
- 新增 `CoordinateDiagnostics`，文件只写 `logs/coordinate_diagnostics.log`，不打印到控制台，避免再次污染 `runtime.log`。
- `NavigationTaskController.update()` 接收 `frame_registration`，每帧在定位有效或无效时记录诊断候选，但不修改 `observe_localization()` 的接受规则。
- `_navigation_loop_unified()` 将 `nav_core.last_frame_registration` 传给任务控制器，使日志能看到 `reg_source/reg_conf/reg_origin/reg_local/reg_meta`。
- 新增方案文档，明确下一阶段重匹配应由连续 `route projection deviation`、`raw control gap`、`near target not completed` 等证据触发，而不是引入固定偏移参数。

**验证命令：** `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\navigation_tasks\coordinate_diagnostics.py core\navigation_tasks\controller.py gui\modes\navigation_mode.py`
**验证结果：** 编译通过；本轮未运行逻辑测试，等待真实游戏导航日志反馈。
**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/navigation_tasks/coordinate_diagnostics.py` | PENDING | 浅读 | 1 | 新增坐标失准诊断模块，记录 raw/control/target/route deviation/registration evidence。 |
| `core/navigation_tasks/controller.py` | (partial) | (partial) | 追加 | 确认统一任务控制器接入诊断采样但不改变任务选择和移动输出。 |
| `gui/modes/navigation_mode.py` | (partial) | (partial) | 追加 | 确认导航循环把当前帧配准契约传入任务控制器。 |
| `docs/plans/2026-05-24-coordinate-drift-diagnostics.md` | PENDING | 浅读 | 1 | 新增坐标漂移检测和未来强制全局重匹配方案记录。 |
## [SYNC] 2026-05-24 14:05 - 近锚点精确点击

### A. SYNC 范围声明
**触发任务：** 用户反馈快到下一个锚点时仍频繁普通点击，角色会绕锚点转圈；期望近锚点时点击锚点本身，到达后再规划下一个锚点。
**直接变更文件：** `core/navigation_tasks/models.py`, `core/navigation_tasks/movement_executor.py`, `core/navigation_tasks/controller.py`, `CODEBASE.md`, `ITERATION_LOG.md`。
**预计连带影响：** 普通 required/exit/event MOVE_TO 仍共用 `MovementExecutor`；只在 `anchor_step/anchor_probe` 当前 path_goal 的近距离阶段改变点击方式，避免 `movement_min_click_radius` 放大近锚点点击。

### C. SYNC 结果
**代码变化：**
- `MovementStep` 新增 `force_click_target`，用于把移动执行器的“精确点击目标”意图传到 UI 输入层。
- `MovementExecutor` 在当前路径为 `anchor_step/anchor_probe` 且人物接近 `path_goal` 但尚未进入 `anchor_arrival_radius` 时，将 `subgoal` 固定为 `path_goal`，并标记 `force_click_target=True`。
- 近锚点阶段点击冷却提升到至少 650ms，并在 2.2s 内抑制 stuck recovery，避免刚靠近锚点就左右探针造成绕圈；若仍未到达，恢复机制会重新接管。
- `NavigationTaskController` 把 `step.force_click_target` 放入 `NavigationIntent.metadata`，沿用现有 `_execute_navigation_intent()` 的 `click_map_target_once()` 分支，因此不会走普通移动最小半径。

**验证命令：** `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\navigation_tasks\coordinate_diagnostics.py core\navigation_tasks\models.py core\navigation_tasks\movement_executor.py core\navigation_tasks\controller.py gui\modes\navigation_mode.py`
**验证结果：** 编译通过；未运行逻辑测试，等待真实导航日志确认是否出现 `nav movement exact path-goal click` 且绕锚点现象减少。
**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/navigation_tasks/models.py` | 浅读 | 浅读 | 追加 | 新增 MovementStep.force_click_target 作为执行器到 UI 输入层的精确点击标志。 |
| `core/navigation_tasks/movement_executor.py` | (partial) | (partial) | 追加 | 近锚点阶段改为精确 path_goal 点击，并短暂抑制恢复探针。 |
| `core/navigation_tasks/controller.py` | (partial) | (partial) | 追加 | 将 force_click_target 透传到 NavigationIntent.metadata。 |

## [SYNC] 2026-05-24 18:25 - 坐标漂移自动重定位恢复

### A. SYNC 范围声明
**触发任务：** 用户确认核心问题是需要可靠界定定位偏移，并把“重新定位”作为特殊恢复事件触发一次，不能使用固定偏移参数。
**直接变更文件：** `core/navigation_tasks/coordinate_diagnostics.py`, `core/navigation_core.py`, `core/navigation_tasks/controller.py`, `gui/modes/navigation_mode.py`, `docs/plans/2026-05-24-coordinate-drift-diagnostics.md`, `CODEBASE.md`, `ITERATION_LOG.md`。
**预计连带影响：** 自动导航和传送门事件继续共用统一任务控制器；坐标恢复是导航内部机制，不进入 `EventCoordinator`，不会与 portal 等业务事件竞争调度。

### C. SYNC 结果
**代码变化：**
- `CoordinateDiagnostics` 从只记录日志升级为漂移恢复状态机：对 `reg_source=f2f` 的 `route_deviation`、`raw_control_gap`、`raw_jump`、`near_target_stall` 等信号按时间窗打分，达到阈值后生成 `CoordinateRelocalizationRequest`。
- `NavigationTaskController.update()` 消费恢复请求后返回 `WAIT` 意图并带 `metadata.force_relocalize=True`，本帧不输出移动点击；强制重定位成功帧使用 `force_snap=True` 把 `trusted/control` 硬重置到新坐标，并重置 `MovementExecutor`。
- `NavigationCore.request_global_relocalization()` 清空 F2F 跟踪状态；下一帧 `localize()` 跳过 F2F 和局部搜索，直接完整 `wall_layer` 模板匹配，并在 `FrameRegistration.metadata` 标记 `forced_global`。
- `NavigationModeWidget._navigation_loop_unified()` 收到强制重定位 intent 后调用导航核心、记录 `navigation forced global relocalization`，并在执行输入前返回，避免偏移状态继续点击。
- 方案文档更新为当前已实现流程，列出 `coordinate relocalization requested/forced/accepted/rejected` 等关键日志。

**CODEBASE.md 更新内容：** 更新 §2 目录结构、§4 `navigation_tasks` 与 `navigation_core` 边界、§5 `NavigationTaskController.update()` 行为、§18 坐标漂移诊断从“只诊断”改为“诊断 + 内部重定位恢复”。

**验证命令：** `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\navigation_tasks\coordinate_diagnostics.py core\navigation_core.py core\navigation_tasks\controller.py gui\modes\navigation_mode.py`
**验证结果：** 编译通过；未运行逻辑测试，等待真实游戏导航日志确认是否出现恢复链路日志并降低偏移。

**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/navigation_tasks/coordinate_diagnostics.py` | 浅读 | (partial) | 2 | 新增恢复请求状态机、信号打分、强制/接受/拒绝日志。 |
| `core/navigation_core.py` | (partial) | (partial) | 18 | 新增强制全局模板匹配入口，保留原始 wall_layer 定位体系。 |
| `core/navigation_tasks/controller.py` | (partial) | (partial) | 追加 | 坐标恢复请求转成 WAIT intent；强制匹配成功后硬重置 control/trusted。 |
| `gui/modes/navigation_mode.py` | (partial) | (partial) | 20 | 导航循环消费 force_relocalize intent，并在输入执行前返回。 |
| `docs/plans/2026-05-24-coordinate-drift-diagnostics.md` | 浅读 | 浅读 | 2 | 从未来方案更新为当前已实现恢复流程和日志说明。 |

## [Round] 2026-05-24 18:46 - Portal missing-detection probe task split

### A. 本轮目标（阅读前声明）
**目标文件：** core/events/types/portal/minimap_detector.py, core/events/detectors/template_matcher.py, utils/event_icon_probe.py, core/events/position_stabilizer.py, core/events/memory.py
**本轮想弄清楚：** 不可识别传送门到底是模板匹配失败、颜色过滤失败、定位投影失败、事件记忆/冷却过滤，还是日志/UI 缺少必要证据。

### C. 本轮发现
**关键发现：** (verified) `D:\ACloud\image` 下两张静态图已用于 `utils/event_icon_probe.py --image` 探针。`95705f16-9696-402c-b008-82f8f7d87651.png` 在原模板 `portal_minimap_01/02` 下无 accepted hit：最佳分数分别为 `0.5597` 和 `0.4444`，但 `_portal_color_check()` 均为 `color-ok`，说明失败发生在模板匹配分数层，不是蓝色过滤、定位投影、memory 冷却或同帧候选上限。`fd4615e6-a089-403f-b2aa-26fceeafc952.png` 在原模板下可识别两个传送门：`0.8398`、`0.7921`。

**修订的旧结论：** (verified) “同帧候选上限导致只能识别两个传送门”不是这两张图失败的原因；小图远距离/裁剪外观下原模板本身低分。`max_candidates` 仍可能影响同帧多事件数量，但这次静态探针没有证明它是根因。

**代码变化：** (verified) 新增正式小地图模板 `assets/event_templates/portal/minimap/portal_minimap_03.png` 和 `portal_minimap_04.png`，来自小图中上/下两个传送门的 32x32 裁剪；`core/events/types/portal/assets.py` 接入四模板列表。`core/events/types/portal/definition.py` 把 `max_candidates`、`min_blue_ratio` 暴露为事件管理 UI 可编辑参数；`gui/dialogs/event_manager_dialog.py` 在当前配置摘要中显示这两个值。

**验证结果：** (verified) 四模板回跑静态探针：小图命中 `portal_minimap_03=0.9901`、`portal_minimap_04=0.9881`；大图仍命中原模板 `portal_minimap_01=0.8398`、`portal_minimap_02=0.7921`，新增模板在大图中低于阈值，未抢占原模板。编译命令 `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\events\types\portal\assets.py core\events\types\portal\definition.py gui\dialogs\event_manager_dialog.py utils\event_icon_probe.py` 通过。

**新疑问：** (partial) 新增裁剪模板能覆盖这两张静态图，但真实运行仍需要观察 `logs/event_runtime.log` 中是否出现 `portal minimap hits` 且 task 能进入 localization stable；若仍漏检，下一步应保存 raw minimap frame 而不是用聊天截图继续调参。

**更新了 CODEBASE.md：** §2 新增 `portal_minimap_03/04` 资产说明；§4 更新 `utils/event_icon_probe.py` 静态图片探针能力；§6 更新事件图标探针 flow；§13 记录当前四模板传送门识别行为。

**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/events/types/portal/minimap_detector.py` | (partial) | (partial) | 追加 | 确认 detector 先做模板匹配，再做 `_portal_color_check()`；本次小图失败发生在模板分数阈值前。 |
| `core/events/detectors/template_matcher.py` | (partial) | (partial) | 追加 | 确认匹配分数为灰度/边缘组合，并支持 alpha mask；本次未改算法，只扩展模板资产。 |
| `utils/event_icon_probe.py` | (partial) | (partial) | 追加 | 静态 `--image` 探针可复用运行时 matcher 和 portal color check，能区分模板低分与颜色过滤。 |
| `core/events/position_stabilizer.py` | (partial) | (partial) | 追加 | 确认定位投影只消费 accepted `EventDetection`；静态小图原模板无 detection，因此未进入此层。 |
| `core/events/memory.py` | (partial) | (partial) | 追加 | 确认 memory/cooldown 只消费 stable observation；静态小图原模板无 detection，不是 memory 抑制。 |
| `core/events/types/portal/assets.py` | PENDING | 浅读 | 1 | 四个小地图模板资产路径集中定义，`PortalMinimapDetector` 初始化时按存在性加载。 |
| `core/events/types/portal/definition.py` | (partial) | (partial) | 追加 | 传送门事件 schema 新增 `max_candidates`、`min_blue_ratio`，避免关键识别参数只藏在代码里。 |
| `gui/dialogs/event_manager_dialog.py` | (partial) | (partial) | 追加 | 当前配置摘要新增候选数量和蓝色比例，方便测试时确认 UI/配置值。 |

## [SYNC] 2026-05-24 19:15 - Portal recognition algorithm feature redesign

### A. SYNC 范围声明
**触发任务：** 用户指出继续新增整块模板不可持续，要求优化匹配算法，最好把传送门本体抠出来再做特征匹配，避免每个传送门都要单独模板。
**直接变更文件：** 预计 `core/events/types/portal/minimap_feature_matcher.py`, `core/events/types/portal/minimap_detector.py`, `core/events/types/portal/config.py`, `core/events/types/portal/definition.py`, `core/events/config.py`, `gui/dialogs/event_manager_dialog.py`, `utils/event_icon_probe.py`, `CODEBASE.md`, `ITERATION_LOG.md`。
**预计连带影响：** 传送门事件仍输出 `EventDetection`，后续 `EventPositionStabilizer`、`EventMemory`、导航到事件点、传送门 handler 不变；识别层从整块模板匹配改为颜色候选/形状过滤/抠图特征确认。

### C. SYNC 结果
**根因闭环：** (verified) 上一轮静态探针证明小图原整块模板最佳分数只有 `0.5597/0.4444`，但蓝色过滤通过；本轮单独验证蓝色二值特征匹配，使用原始 `portal_minimap_01/02` 两个模板即可在小图和大图同时命中，说明稳定特征是传送门蓝色本体结构，而不是周围背景像素。

**代码变化：**
- 新增 `core/events/types/portal/minimap_feature_matcher.py`：从模板和 raw minimap 中提取 HSV 蓝/青二值 mask，做多尺度 `TM_CCOEFF_NORMED` 匹配，并用蓝色像素数量和 density score 过滤候选。
- `PortalMinimapDetector.detect()` 优先调用 feature matcher，只有 feature 无命中时才回退旧整块模板匹配；输出 metadata 增加 `detector`, `mask_score`, `density_score`, `feature_blue_pixels` 等诊断字段。
- `PortalMinimapDetector.detect()` 还新增节流 `portal minimap no hits` 诊断日志，打印 feature 模板数、raw frame 蓝色特征像素数量和当前 feature 阈值，避免“没识别”时没有证据。
- 删除上一轮临时新增的 `portal_minimap_03/04` 整块模板资产，运行时继续只依赖原始两个 canonical 模板，避免模板堆积。
- `PortalEventConfig`、`DEFAULT_EVENT_CONFIG` 和事件 UI schema 新增 `feature_hue_min/max`, `feature_sat_min`, `feature_val_min`, `feature_min_blue_pixels`, `feature_max_blue_pixels`，关键识别参数可在事件管理中调整。
- `utils/event_icon_probe.py` 新增 `--portal-feature-detector` 和对应 HSV/像素阈值参数，用于离线验证运行时 feature 算法。

**验证结果：**
- 编译通过：`D:\ACloud\.venv\Scripts\python.exe -m py_compile core\events\config.py core\events\types\portal\minimap_feature_matcher.py core\events\types\portal\minimap_detector.py core\events\types\portal\config.py core\events\types\portal\definition.py gui\dialogs\event_manager_dialog.py utils\event_icon_probe.py`
- 静态 feature 探针通过：`95705f16-9696-402c-b008-82f8f7d87651.png` 命中 `(54,83)` score `0.9017` 和 `(79,116)` score `0.7782`；`fd4615e6-a089-403f-b2aa-26fceeafc952.png` 命中 `(259,127)` score `0.9286` 和 `(281,153)` score `0.9088`。

**CODEBASE.md 更新内容：** §2 新增 `minimap_feature_matcher.py` 并移除临时 03/04 模板说明；§4 更新 portal 事件包和探针职责；§5 记录 feature matcher 与 detector 算法；§6 更新事件图标探针 flow；§8 更新 portal 识别参数；§13 更新当前 portal 行为。

**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/events/types/portal/minimap_feature_matcher.py` | PENDING | 浅读 | 1 | 新增蓝色本体二值特征匹配，避免整块背景模板低分漏检。 |
| `core/events/types/portal/minimap_detector.py` | (partial) | (partial) | 追加 | detector 识别链改为 feature first、template fallback，后续 EventDetection 契约不变。 |
| `core/events/types/portal/config.py` | (partial) | (partial) | 追加 | 新增 portal feature HSV/像素阈值配置，from_dict 保持旧配置兼容默认值。 |
| `core/events/types/portal/definition.py` | (partial) | (partial) | 追加 | 事件管理 schema 暴露 feature 识别参数。 |
| `core/events/config.py` | 浅读 | 浅读 | 追加 | 默认 event_config 合并新增 feature 参数，旧地图配置读取时自动补默认值。 |
| `gui/dialogs/event_manager_dialog.py` | (partial) | (partial) | 追加 | 当前配置摘要显示部分 feature 参数，便于测试时确认值。 |
| `utils/event_icon_probe.py` | (partial) | (partial) | 追加 | 新增 `--portal-feature-detector` 静态/实时探针模式，复用运行时 feature matcher。 |

## [SYNC] 2026-05-24 20:28 - Coordinate relocalization over-trigger diagnosis

### A. SYNC 范围声明
**触发任务：** 用户反馈最新导航日志中重新定位触发过于频繁，要求先看日志确认原因。
**直接变更文件：** `core/navigation_tasks/coordinate_diagnostics.py`, `CODEBASE.md`, `ITERATION_LOG.md`。
**预计连带影响：** `NavigationTaskController` 仍通过同一 `CoordinateRelocalizationRequest` 转成 `WAIT + force_relocalize` intent；`NavigationCore.request_global_relocalization()` 和 GUI 消费路径不变。

### C. SYNC 结果
**根因闭环：** (verified) `logs/coordinate_diagnostics.log` 中频繁请求主要来自 `route_deviation` 重复入队：例如 `20:13:35`, `20:13:39`, `20:13:52`, `20:13:59`, `20:14:06`, `20:14:14` 都是 `reason=route_deviation score=3 signals=(route_deviation,route_deviation,route_deviation)`。这说明诊断器把路线投影偏差/导航 fallback 当成坐标漂移证据，而不是定位匹配本身必然错误。另一个放大器是 `long_f2f_tracking` 每帧入队，日志中出现 `score=9` 和 `score=20` 的情况，实际只是同一上下文信号重复叠分。

**代码变化：**
- `CoordinateDiagnostics._register_recovery_signal()` 改为按唯一 signal name 取最大 severity 计分，避免同一 `route_deviation` 或 `long_f2f_tracking` 在 2.6 秒窗口内刷分。
- `long_f2f_tracking` 改为 severity 0，仅作为上下文，不再放大恢复分数。
- 新增 primary signal 策略：只有 `raw_jump` 或 `raw_control_gap` 这类真实坐标异常可以触发强制重定位；`route_deviation`、`near_target_stall` 没有 primary 时只记录 `coordinate relocalization suppressed`。
- `raw_jump` severity 提升到 3，可直接触发一次重定位；`raw_control_gap` 根据 gap 大小给 1/2 分，需要和上下文信号组合才触发。
- 强制重定位 accepted/rejected 后清空 `_signals` 和 `_near_target_since_ms`，避免旧的 near-target 计时在重定位后继续触发。

**验证结果：** `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\navigation_tasks\coordinate_diagnostics.py` 通过；未做逻辑测试，等待真实游戏导航日志确认 `coordinate relocalization suppressed` 增加、`navigation forced global relocalization` 降低。

**CODEBASE.md 更新内容：** §5 `NavigationTaskController.update()` 诊断步骤说明；§18 坐标漂移诊断恢复策略。

**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/navigation_tasks/coordinate_diagnostics.py` | (partial) | (partial) | 追加 | 确认过触发过频根因并改为唯一信号计分 + primary signal 门控。 |
| `CODEBASE.md` | 文档 | 文档 | 追加 | 更新坐标恢复策略描述，明确 route/near/f2f 不再单独强制重定位。 |
| `ITERATION_LOG.md` | 文档 | 文档 | 追加 | 记录本次日志根因、代码变更和编译结果。 |

## [SYNC] 2026-05-24 20:46 - Visual-consistency relocalization trigger

### A. SYNC 范围声明
**触发任务：** 用户要求废弃当前频繁触发的路线/锚点偏差重定位逻辑，改为“截图实际位置 A 与导航图人物位置 B 有稳定差异”才触发重定位。
**直接变更文件：** `core/navigation_core.py`, `core/navigation_tasks/coordinate_diagnostics.py`, `gui/navigation_params.py`, `gui/dialogs/nav_params_dialog.py`, `gui/modes/navigation_mode.py`, `CODEBASE.md`, `ITERATION_LOG.md`。
**预计连带影响：** `NavigationTaskController` 的 relocalization intent、`NavigationCore.request_global_relocalization()`、GUI 消费 `force_relocalize` 的路径不变；变化只在“何时请求重定位”的证据来源。

### C. SYNC 结果
**根因修正：** (verified) 之前的恢复逻辑把 `route_deviation`、`near_target_stall` 等导航规划现象当成重定位证据。新逻辑不再使用路线、锚点、A* fallback 作为强制重定位条件。

**代码变化：**
- `NavigationCore.localize()` 的 F2F 分支新增视觉一致性校验：定期把当前截图提取出的 `wall_mask` 放大到地图尺度，只在当前人物点附近的小窗口里做 `cv2.matchTemplate`，得到截图本帧最应该贴到大地图上的 `visual_player`。
- F2F 的 `FrameRegistration.metadata` 新增 `visual_check`, `visual_conf`, `visual_expected_score`, `visual_player`, `visual_delta`, `visual_delta_dist`, `visual_mismatch`，用于日志判断“截图位置 A”和“导航位置 B”是否稳定不同。
- `CoordinateDiagnostics` 删除路线偏差、近目标卡住、raw-control smoothing gap、long F2F duration 对重定位的触发作用；它们只写诊断日志。
- 新 primary signals 只剩 `visual_mismatch` 和 `raw_jump`。`visual_mismatch` 必须连续达到配置帧数才触发；`raw_jump` 保留为极端跳变保险。
- 导航参数新增并可保存：`coordinate_visual_check_interval_ms`, `coordinate_visual_check_margin`, `coordinate_visual_match_min_confidence`, `coordinate_visual_mismatch_threshold`, `coordinate_visual_mismatch_frames`。
- 参数面板“定位/运行”页新增视觉校验相关控件；`NavigationModeWidget._configure_navigation_task_controller()` 会把这些值同步到 `NavigationCore` 和 `CoordinateDiagnostics`。

**验证结果：** `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\navigation_core.py core\navigation_tasks\coordinate_diagnostics.py gui\navigation_params.py gui\dialogs\nav_params_dialog.py gui\modes\navigation_mode.py` 通过；未运行逻辑测试，等待真实游戏导航日志确认 `visual coordinate mismatch` 和 `coordinate relocalization requested reason=visual_mismatch` 是否符合肉眼偏移。

**CODEBASE.md 更新内容：** §5 `NavigationTaskController.update()` 诊断步骤；§8 `NavConfig` 新增视觉校验参数；§18 坐标漂移诊断改为视觉一致性触发。

**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/navigation_core.py` | (partial) | (partial) | 追加 | F2F 跟踪新增局部视觉模板校验，将截图最佳贴图位置写入 FrameRegistration metadata。 |
| `core/navigation_tasks/coordinate_diagnostics.py` | (partial) | (partial) | 追加 | 重定位触发源改为 visual_mismatch/raw_jump；路线偏差和近目标卡住只保留诊断。 |
| `gui/navigation_params.py` | (partial) | (partial) | 追加 | NavConfig 新增视觉校验阈值字段和 config.json 序列化。 |
| `gui/dialogs/nav_params_dialog.py` | (partial) | (partial) | 追加 | 参数面板新增视觉校验间隔、搜索边距、最低置信度、偏移阈值、连续帧数控件。 |
| `gui/modes/navigation_mode.py` | (partial) | (partial) | 追加 | 将视觉校验配置同步到 NavigationCore 和 CoordinateDiagnostics。 |

## [SYNC] 2026-05-24 21:30 - Portal-trigger relocalization and completion

### A. SYNC 范围声明
**触发任务：** 用户反馈传送门按下 `D` 后重定位卡住，且成对传送门传入/传出状态没有正确完成，事件绕回重复执行。
**直接变更文件：** 待调查后确定，预计涉及 `core/navigation_core.py`, `core/events/types/portal/handler.py`, `core/events/runner.py`, `core/events/memory.py`, `gui/modes/navigation_mode.py`。
**预计连带影响：** 复用开始导航同款全图定位路径；传送门事件在等待传送结果时应允许大跳变定位；事件完成时应同时关闭 entry/exit portal task。

### C. SYNC 结果
**根因确认：** (verified) 最新 `coordinate_diagnostics.log` 显示传送门按 `D` 后进入 `template_match_failed/jump_rejected` 循环；普通定位把传送后的合法大位移当成异常跳变拒绝，导致 `PortalEventHandler.wait_result` 一直拿不到新的有效 `player_global_pos`。
**代码变化：**
- `NavigationCore` 新增 `request_full_map_localization()`，`request_global_relocalization()` 作为兼容别名；强制重定位现在走与开始导航一致的全图模板匹配阈值，不再使用额外更高的 `force_global_min_confidence`。
- `PortalEventHandler` 在按 `D` 后等待传送完成阶段返回带 `force_relocalize=True` 的 WAIT action，请求下一帧全图定位；完成判断改为优先识别已知出口门，其次大距离位移，最后小地图环境变化。
- `EventAction.wait()` 支持 metadata；`NavigationTaskController._update_event_task()` 会把 WAIT metadata 透传给 GUI。
- `NavigationTaskController` 在 `forced_reason=portal_wait_result` 的强制定位成功后保留当前 active event，避免传送后调度器切到出口门或静态路线，保证原入口 handler 有机会完成 teleport session。
- `EventRunner` 和 `EventMemory.complete_teleport_session()` 增加 `exit_task_id` / `exit_player_pos` 传递，优先按已知出口 task id 标记出口完成，再 fallback 到坐标半径查找或 synthetic exit。
**验证结果：** `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\navigation_core.py core\events\models.py core\events\types\portal\handler.py core\events\runner.py core\events\memory.py core\navigation_tasks\controller.py gui\modes\navigation_mode.py` 通过。未做逻辑自动测试，等待真实游戏运行日志验证。
**CODEBASE.md 更新内容：** §4 `core/navigation_core.py`、§13 portal flow、§17 坐标诊断恢复说明，补充 full-map localization、portal wait-result recovery 和 exit task id 完成语义。
**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/navigation_core.py` | (partial) | (partial) | 追加 | 确认强制重定位现在复用开始导航的全图模板匹配阈值，并绕过普通 jump rejection。|
| `core/events/types/portal/handler.py` | (partial) | (partial) | 追加 | 确认传送门等待结果阶段会请求全图定位，完成 metadata 携带 known exit id/player pos。|
| `core/events/memory.py` | (partial) | (partial) | 追加 | 确认 teleport session 优先用 exit_task_id 标记出口，否则按坐标查找/创建 synthetic exit。|
| `core/navigation_tasks/controller.py` | (partial) | (partial) | 追加 | 确认 WAIT action metadata 透传，并在 portal_wait_result 重定位成功时保留 active event。|

## [SYNC] 2026-05-24 22:10 - Relocalization regression and portal false-positive guard

### A. SYNC 范围声明
**触发任务：** 用户反馈开始导航定位和重定位都失效，并怀疑是否与前面高清绘图/墙体逻辑改动有关；同时地图上出现三处不应存在的传送门标记。
**直接变更文件：** `core/navigation_core.py`, `core/stitcher_core.py`, `gui/navigation_params.py`, `gui/modes/navigation/map_runtime.py`, `gui/modes/navigation_mode.py`, `CODEBASE.md`, `ITERATION_LOG.md`。
**预计连带影响：** 定位匹配必须继续使用原始 `wall_layer`，A* 侵蚀只影响 `nav_wall_layer`；导航保存配置不能破坏建图参数；传送门误报应优先限制在识别层。

### C. SYNC 结果
**关键发现：** (verified) 最新日志对应 `map_data/大佬A`，该地图 `map_data.npz` 和 `config.json` 的 `draw_scale` 都是 3.0，因此不是当前这张图的简单倍率错配。A* 的 `nav_wall_erode_iterations` 只派生 `nav_wall_layer`，定位仍匹配原始 `wall_layer`，所以墙体侵蚀本身不应导致 `conf=0.14~0.16`。但导航保存配置此前会覆盖地图 `config.json`，丢失 `stitcher_params` 等建图专属参数；这会破坏“绘图环境与导航环境完全一致”的可追溯性。假传送门日志明确来自 `source=minimap_feature+wall_registration`，即蓝色 feature detector 误报，而不是定位投影阶段凭空生成。
**代码变化：**
- `NavigationCore` 记录 `map_draw_scale`，导航运行时以 `map_data.npz` 的 draw scale 为权威；`NavigationModeWidget._apply_config_to_core()` 发现配置倍率不一致时记录 `navigation draw_scale config mismatch` 并使用地图包值。
- `MapStitcher.save_map_package()` 新增保存 `wall_close_kernel_size`；`NavigationCore` 加载后用它作为 `wall_match_close_kernel_size`，让实时定位模板复现建图时的墙体闭运算。旧地图没有该字段时仍回退 3。
- `NavigationCore.localize()` 的模板匹配失败会节流打印 `Localization template match failed`，包含置信度、阈值、full_map/forced、draw_scale/map_draw_scale、mask 尺寸和特征数、搜索区域、闭运算核，便于下一次实测判断是截图窗口、识别参数还是地图墙层不一致。
- `save_nav_config()` 改为合并写回，保留现有地图配置里的 mapping-only 字段和已有 recognizer 字段，避免导航页保存把建图配置覆盖掉。
- 传送门 feature detector 已保持默认关闭，默认运行只走模板匹配 + 蓝色校验；feature detector 后续只能显式开启。
**验证结果：** `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\navigation_core.py core\stitcher_core.py gui\navigation_params.py gui\modes\navigation\map_runtime.py gui\modes\navigation_mode.py core\events\config.py core\events\types\portal\config.py core\events\types\portal\minimap_detector.py` 通过。实时截图探针在当前桌面没有抓到小地图特征，不能作为游戏内匹配结论；需要用户重新运行游戏内导航后看新增定位失败日志。
**CODEBASE.md 更新内容：** 更新 `core/navigation_core.py` 注意事项、portal 当前识别默认策略、地图保存流、导航 map_runtime 保存语义。
**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/navigation_core.py` | (partial) | (partial) | 追加 | 明确 draw_scale 来源、墙体闭运算复现、全图匹配失败诊断日志和 jump rejection 边界。 |
| `core/stitcher_core.py` | (partial) | (partial) | 追加 | 地图包新增保存 `wall_close_kernel_size`，支持导航复现建图墙体模板处理。 |
| `gui/modes/navigation/map_runtime.py` | (partial) | (partial) | 追加 | 导航保存配置改为 merge，防止丢失建图字段。 |
| `gui/modes/navigation_mode.py` | (partial) | (partial) | 追加 | `_apply_config_to_core()` 以地图包 draw_scale 为准，并记录倍率不一致。 |
| `core/events/types/portal/minimap_detector.py` | (partial) | (partial) | 追加 | 误报来源确认是 opt-in feature detector，默认模板路径保留。 |

## [SYNC] 2026-05-25 12:40 - Event approach stabilization gate

### A. SYNC 范围声明
**触发任务：** 用户确认先优化事件靠近逻辑：事件进入真实游戏视野后先用短距离 A* 收敛并停稳，再允许传送门 handler 点击/按 `D`。
**直接变更文件：** `core/navigation_tasks/event_approach.py`, `core/navigation_tasks/controller.py`, `core/navigation_tasks/movement_executor.py`, `gui/navigation_params.py`, `gui/dialogs/nav_params_dialog.py`, `gui/modes/navigation_mode.py`, `CODEBASE.md`, `ITERATION_LOG.md`。
**预计连带影响：** 自动导航和手动“测试传送门”都走同一个 `NavigationTaskController.update()`，因此同一套事件靠近/停稳门控会同时影响真实导航和事件测试；传送门 handler 本身不直接负责靠近策略。

### C. SYNC 结果
**关键发现：** (verified) 旧链路在 `_update_event_task()` 中先调用 `event_coordinator.run_task()`，所以 `PortalEventHandler` 可以在角色刚进入半径或还未停稳时推进到 `portal_point_click -> press D`。事件靠近属于导航层职责，放入 portal handler 会让后续随机事件重复造轮子。

**代码变化：**
- 新增 `core/navigation_tasks/event_approach.py`，提供 `EventApproachController` 和 `EventApproachConfig`。它在事件 handler 前执行：真实视野判定、远距离 A*+锚点、真实视野内短 lookahead A*、停靠半径、停稳时间、稳定帧数判断。
- `NavigationTaskController._update_event_task()` 在 `event_coordinator.run_task()` 前接入门控。任务未 released 时只返回移动/等待 intent；ready 后记录 `event approach released`，同一任务后续不再被门控打断，避免 portal `wait_result` 被重新拦截。
- `MovementExecutor.step()` 增加单次 `click_cooldown_ms` override，事件近距离阶段可以使用更慢点击节奏，不污染普通路线和锚点配置。
- `NavConfig` 新增事件靠近参数：`event_approach_enabled`, `event_visible_margin`, `event_approach_lookahead`, `event_approach_click_cooldown_ms`, `event_stop_radius`, `event_settle_ms`, `event_stable_frames`, `event_max_motion_per_frame`。
- `NavParametersDialog` 新增“事件靠近”页，把上述参数做成 UI 可调并可保存；`NavigationModeWidget._configure_navigation_task_controller()` 把配置同步给 `EventApproachController`。

**验证结果：** `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\navigation_tasks\event_approach.py core\navigation_tasks\movement_executor.py core\navigation_tasks\controller.py gui\navigation_params.py gui\dialogs\nav_params_dialog.py gui\modes\navigation_mode.py` 通过；`git diff --check` 无空白错误，仅有既有 CRLF 提示。未跑逻辑测试，等待游戏内通过 `event approach far/approach/settling/ready/released` 日志确认。

**CODEBASE.md 更新内容：** §15 事件四阶段方法论补充事件靠近门控；新增 §19 事件靠近停稳层，记录模块职责、执行链路、关键参数和风险。

**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/navigation_tasks/event_approach.py` | PENDING | (partial) | 1 | 新增事件靠近门控，确认远距离锚点导航、真实视野内直接 A*、停稳释放三个阶段。 |
| `core/navigation_tasks/controller.py` | (partial) | (partial) | 追加 | 事件 handler 前新增 approach gate，COMPLETE/FAIL 会清理 released 状态。 |
| `core/navigation_tasks/movement_executor.py` | (partial) | (partial) | 追加 | `step()` 新增 per-call 点击冷却 override，避免事件近距离节奏影响普通导航。 |
| `gui/navigation_params.py` | (partial) | (partial) | 追加 | NavConfig 新增事件靠近参数和 config.json 序列化。 |
| `gui/dialogs/nav_params_dialog.py` | (partial) | (partial) | 追加 | 参数面板新增“事件靠近”页，暴露真实视野边距、lookahead、冷却、停靠/停稳参数。 |
| `gui/modes/navigation_mode.py` | (partial) | (partial) | 追加 | `_configure_navigation_task_controller()` 同步事件靠近配置；事件测试重置会清空 approach runtime。 |
## [SYNC] 2026-05-25 20:45 - Portal minimap detection default

### A. SYNC scope
**Task:** Diagnose why portal minimap events no longer appear on the current map/session after recent navigation and event changes.
**Direct files changed:** `core/events/config.py`, `core/events/types/portal/config.py`, `core/events/types/portal/definition.py`, `CODEBASE.md`, `ITERATION_LOG.md`.
**Expected impact:** New maps without `event_config.json` now use the portal blue-body feature matcher by default; the old gray/edge full-template matcher remains the fallback. Existing saved configs with explicit `feature_detector_enabled=false` still keep that override.

### C. SYNC result
**Root cause:** (verified) Latest `logs/event_runtime.log` repeatedly showed `portal minimap no hits source=template feature_enabled=False` while `feature_blue_pixels` stayed in the configured valid range. A live probe on the same minimap frame showed the full-template path had best score `0.6021`, below runtime threshold `0.74`, but `--portal-feature-detector` found the portal at score `0.9206`.
**Code change:** `DEFAULT_EVENT_CONFIG["events"]["portal"]["feature_detector_enabled"]` and `PortalEventConfig.feature_detector_enabled` now default to `True`; `PortalEventConfig.from_dict()` also falls back to `True` when the key is absent. The event UI label is now `portal blue feature detector` instead of `experimental feature detector`.
**Verification:** `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\events\config.py core\events\types\portal\config.py core\events\types\portal\definition.py core\events\types\portal\minimap_detector.py core\events\types\portal\minimap_feature_matcher.py` passed. Live probe evidence: template path no accepted hit above `0.74`; feature path accepted hits at `0.9206` and `0.7511`.
**CODEBASE.md updated:** Portal minimap detection default now states feature-first, template-fallback, with UI kill switch for false positives.

## [SYNC] 2026-05-25 22:27 - Portal minimap shape+color probe

### A. SYNC scope
**Task:** User asked to replace the loose small-minimap event probe with a shape + color algorithm first, before changing runtime portal detection.
**Direct files changed:** `core/events/types/portal/minimap_shape_color_matcher.py`, `utils/event_icon_probe.py`, `CODEBASE.md`, `ITERATION_LOG.md`.
**Expected impact:** Adds a stricter probe path for portal minimap recognition. Runtime `PortalMinimapDetector` still uses the existing feature-first/template-fallback logic until the user approves integration.

### C. SYNC result
**Root cause context:** (verified) The current blue-body feature matcher can over-accept local blue patterns because its validation is mostly blue mask structure and blue-pixel density. A recent false portal around global `(4192,2800)` came from `source=minimap_feature+wall_registration`, so the next probe needs to verify not only blue color but also the portal's white/gray outer ring and combined icon shape.

**Code change:**
- Added `core/events/types/portal/minimap_shape_color_matcher.py`.
- Added `--portal-shape-color-detector` to `utils/event_icon_probe.py`.
- Added probe parameters for HSV blue core, white/gray outer ring, minimum blue/outer/combined shape scores, and minimum outer pixels.
- Probe output now saves `minimap_portal_shape_blue_mask_*`, `minimap_portal_shape_outer_mask_*`, `minimap_portal_shape_combined_mask_*`, a boxed debug image, and accepted/rejected candidate crops.
- Candidate scoring combines blue core, outer ring, combined shape, edge, and masked HSV color similarity. Candidate gates record reject reasons such as `score`, `blue_shape`, `outer_shape`, `combined_shape`, `blue_pixels_low/high`, and `outer_pixels_low`.
- Duplicate merge now sorts by `(accepted, score)` so an accepted candidate is not displaced by a same-location rejected candidate with a higher raw response.

**Verification:**
- Syntax check passed: `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\events\types\portal\minimap_shape_color_matcher.py utils\event_icon_probe.py`.
- Static probe command passed on `D:\ACloud\image\95705f16-9696-402c-b008-82f8f7d87651.png` and `D:\ACloud\image\fd4615e6-a089-403f-b2aa-26fceeafc952.png`.
- Shape+color result on image 1: accepted one real portal at center `(54,83)` score `0.7522`; rejected the old lower blue false-looking candidate at `(79,117)` score `0.6406` because total score was below threshold.
- Shape+color result on image 2: accepted two real portals at centers `(258,127)` score `0.8816` and `(281,153)` score `0.8610`; rejected unrelated blue candidates at `(66,68)` and `(54,45)`.
- Old `--portal-feature-detector` comparison on the same images accepted two candidates on image 1, including the lower blue object that shape+color rejected, confirming the stricter probe reduces this class of false positive.
- Live one-frame probe saved debug output but found no candidate; this is inconclusive because the current live minimap frame may not contain a portal.

**CODEBASE.md updated:** Added `minimap_shape_color_matcher.py`, updated `event_icon_probe.py` responsibilities, event icon probe flow, portal package notes, and reusable capability list.

**Coverage update:**
| File | Previous | Current | Reads | Note |
|------|----------|---------|-------|------|
| `core/events/types/portal/minimap_shape_color_matcher.py` | PENDING | (partial) | 1 | New strict portal minimap probe algorithm; not yet wired into runtime detector. |
| `utils/event_icon_probe.py` | (partial) | (partial) | appended | Added shape+color probe mode, static/live image support remains unchanged. |
| `core/events/types/portal/minimap_detector.py` | (partial) | unchanged | appended | Runtime detector intentionally not changed in this round. |

## [SYNC] 2026-05-25 22:40 - Portal detector mode selector

### A. SYNC scope
**Task:** User approved wiring shape+color into runtime, but explicitly asked not to replace existing algorithms. All current minimap portal algorithms should be selectable from the event manager panel for HITL comparison before convergence.
**Direct files changed:** `core/events/config.py`, `core/events/types/portal/config.py`, `core/events/types/portal/definition.py`, `core/events/types/portal/minimap_detector.py`, `gui/dialogs/event_manager_dialog.py`, `CODEBASE.md`, `ITERATION_LOG.md`.
**Expected impact:** Portal event detection can be switched between `template`, `feature`, `feature_then_template`, and `shape_color` without changing event memory, localization, navigation, or handler logic.

### C. SYNC result
**Code change:**
- `PortalEventConfig` now has `detector_mode`, defaulting to `feature_then_template`.
- `EventSystemConfig.from_dict()` preserves old saved-map behavior: if old config explicitly has `feature_detector_enabled=false` and no `detector_mode`, it maps to `detector_mode=template`; otherwise absent mode defaults to `feature_then_template`.
- `PortalEventDefinition.config_schema()` exposes `detector_mode` as a choice field in the event manager. `feature_detector_enabled` remains in config but is no longer editable in the UI.
- Added shape+color runtime parameters to the event schema: `shape_outer_sat_max`, `shape_outer_val_min`, `shape_min_blue_score`, `shape_min_outer_score`, `shape_min_shape_score`, and `shape_min_outer_pixels`.
- `PortalMinimapDetector.detect()` now dispatches by mode:
  - `template`: old full-image gray/edge template matching only.
  - `feature`: blue/cyan portal-body feature matcher only.
  - `feature_then_template`: feature first, then old template fallback.
  - `shape_color`: strict shape+color matcher only.
- Runtime logs now include `mode`, shape score fields, and `portal minimap shape-color rejected` when shape+color found candidates but rejected all of them.
- Event manager summary row now shows `detector_mode` and key shape thresholds.

**Verification:**
- Compile passed: `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\events\config.py core\events\types\portal\config.py core\events\types\portal\definition.py core\events\types\portal\minimap_detector.py core\events\types\portal\minimap_shape_color_matcher.py gui\dialogs\event_manager_dialog.py utils\event_icon_probe.py`.
- Config compatibility check passed:
  - empty config -> `feature_then_template`
  - old `feature_detector_enabled=false` -> `template`
  - old `feature_detector_enabled=true` -> `feature_then_template`
  - explicit `detector_mode=shape_color` wins even if legacy bool is false
- Offline detector dispatch on the two saved images passed:
  - `template`: misses the small image, accepts two portals on the large image.
  - `feature`: accepts two candidates on the small image including the lower blue false-looking candidate, accepts two portals on the large image.
  - `feature_then_template`: same as feature on these images because feature hits first.
  - `shape_color`: accepts one real portal on the small image and two real portals on the large image.

**CODEBASE.md updated:** Portal detector docs now describe selectable modes, shape+color runtime wiring, config compatibility, and new shape thresholds.

**Coverage update:**
| File | Previous | Current | Reads | Note |
|------|----------|---------|-------|------|
| `core/events/types/portal/minimap_detector.py` | (partial) | (partial) | appended | Runtime detector now supports four selectable minimap recognition modes. |
| `core/events/types/portal/config.py` | (partial) | (partial) | appended | Added `detector_mode` and shape+color threshold fields. |
| `core/events/config.py` | shallow | shallow | appended | Added default detector mode plus legacy config mapping. |
| `gui/dialogs/event_manager_dialog.py` | (partial) | (partial) | appended | Summary displays selected detector mode and shape thresholds. |

## [SYNC] 2026-05-25 23:05 - Event manager dialog visibility guard

### A. SYNC scope
**Task:** User reports that after clicking "测试传送门" and the event finishes, the event manager panel disappears and cannot be reopened from the main UI. Also requested an explanation of current portal recognition algorithms.
**Direct files changed:** `gui/dialogs/event_manager_dialog.py`, `gui/modes/navigation_mode.py`, `CODEBASE.md`, `ITERATION_LOG.md`.
**Expected impact:** Event manager can be reopened after manual event test, regardless of game-input window mode or previous close/hide state. No change to event detection, movement, or portal handler logic.

### C. SYNC result
**Root cause hypothesis:** (verified from code shape, not yet HITL confirmed) `EventManagerDialog` was constructed as a child dialog of `NavigationModeWidget`. Manual portal testing enables game-input window mode, removes topmost from the main window and lowers it. A child dialog can follow the parent window into a hidden/non-activatable layer; after that, `show/raise/activateWindow()` on the existing child object may not make it findable.

**Code change:**
- `EventManagerDialog` now uses `Qt.Tool` and `WA_DeleteOnClose=False`.
- `NavigationModeWidget` now creates the event dialog through `_ensure_event_dialog()` instead of assuming the original object is always valid.
- `_ensure_event_dialog()` reconnects signals and rebinds the manual portal test button when needed.
- `toggle_event_dialog()` ensures the dialog exists before refresh/show.
- `_show_owned_dialog()` restores minimized state, moves newly shown dialogs near the main window, then calls `show/raise/activateWindow`.

**Verification:** `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\dialogs\event_manager_dialog.py gui\modes\navigation_mode.py` passed. Needs user HITL confirmation after running a manual portal test and reopening "事件管理".

**Coverage update:**
| File | Previous | Current | Reads | Note |
|------|----------|---------|-------|------|
| `gui/dialogs/event_manager_dialog.py` | (partial) | (partial) | appended | Dialog is now a tool window and not deleted on close. |
| `gui/modes/navigation_mode.py` | (partial) | (partial) | appended | Event manager lifecycle now uses ensure/rebind/show guard. |

## [SYNC] 2026-06-03 17:07 - Loot ROI feature match probe

### A. SYNC scope
**Task:** User asked for an independent probe of ROI-internal shape similarity matching, similar to a lightweight CNN feature response, and to measure effect plus resource cost before runtime integration.
**Direct files changed:** `debug/loot_feature_match_probe.py`, `architecture_docs/zh-CN/core/events/types/loot/ARCHITECTURE.md`, `CODEBASE.md`, `ITERATION_LOG.md`.
**Expected impact:** Adds a standalone debug/probe entry only. Production `LootMinimapDetector` behavior is unchanged.

### C. SYNC result
**Code change:** Added `debug/loot_feature_match_probe.py`. The probe reuses loot template loading, alpha masks, center-player exclusion templates, and `loot_seed_bboxes()`, then searches fixed-size multi-anchor ROI windows with yellow-diamond/red-star/gold-triangle templates. Candidate scoring combines masked template similarity, edge overlap, Chamfer distance, 2x2 HOG-lite similarity, contour/Hu similarity, semantic shape gates, and low-weight color evidence. The probe defaults to shape templates only, scales `0.75,0.85,1.0`, and `top_k_per_template=2`.

**Verification:**
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile debug\loot_feature_match_probe.py` passed.
- Full dataset probe passed on `D:\ACloud\image\sample`: run `debug/loot_feature_match_probe/20260603_170739/`, TP=25, FP=0, FN=0, TN=52, precision=1.0000, recall=1.0000, FPR=0.0000, average total time 241.665ms, p95 449.336ms, max 666.978ms.
- `--workers 4` comparison reduced wall-clock only slightly but increased per-image latency, so runtime integration should prefer an async detector thread over per-frame multithreading.

**CODEBASE.md updated:** Added the new probe command, algorithm chain, latest metrics, and runtime integration caveat.

**Coverage update:**
| File | Previous | Current | Reads | Note |
|------|----------|---------|-------|------|
| `debug/loot_feature_match_probe.py` | PENDING | (partial) | 1 | New standalone probe for ROI sliding multi-feature loot shape matching; production detector not changed. |
| `architecture_docs/zh-CN/core/events/types/loot/ARCHITECTURE.md` | (partial) | (partial) | appended | Documented 2026-06-03 probe algorithm, metrics, and threading caveat in Chinese. |
| `CODEBASE.md` | (partial) | (partial) | appended | Added probe entry and latest dataset result to loot project intelligence section. |

## [SYNC] 2026-06-03 17:12 - Loot async perception implementation

### A. SYNC scope
**Task:** Implement the agreed decoupled multi-layer loot perception rule: cheap first-stage detection, heavy feature matching only when needed, async execution, memory dedupe, and no blocking of the navigation frame loop.
**Direct files expected:** `core/events/types/loot/*`, `core/events/types/loot/detection/*`, possibly `gui/modes/navigation/events/*` or event coordinator wiring if runtime integration requires it.
**Expected impact:** Production loot detection should stop running heavyweight recognition synchronously every frame; the navigation loop should consume cached/confirmed loot observations while an independent worker processes fresh minimap frames.

## [SYNC] 2026-06-03 17:42 - Loot async probe parity diagnosis

### A. SYNC scope
**Task:** Keep production loot default parameters identical to the successful feature-match probe, then diagnose why the async production integration missed several positive samples while the probe reached 25 TP / 0 FP / 0 FN / 52 TN.
**Direct files expected:** `core/events/types/loot/minimap_detector.py`, `core/events/types/loot/perception/*`, `core/events/types/loot/detection/feature_match/*`, `core/events/types/loot/config.py`, Chinese loot architecture docs, `CODEBASE.md`, `ITERATION_LOG.md`.
**Expected impact:** Runtime detector should use the same feature defaults as `debug/loot_feature_match_probe.py`, keep heavy matching off the frame loop, and avoid clearing fresh async detections before the caller can consume them.

### C. SYNC result
**Key finding:** Production `FeatureLootMatcher.detect()` already matches the probe on `D:/ACloud/image/sample`: TP=25, FP=0, FN=0, TN=52. The production async path also matches when the harness waits for the worker result instead of treating the first empty frame as final: TP=25, FP=0, FN=0, TN=52.

**Default parameter parity:** Confirmed from `map_data/A/event_config.json` and `LootEventConfig.from_dict()`:
- `detector_mode=async_feature_match`
- `feature_match_threshold=0.64`
- `feature_match_collect_threshold=0.38`
- `feature_match_top_k_per_template=2`
- `feature_match_max_candidates=5`
- `feature_match_search_padding=48`
- `feature_match_scales=0.75,0.85,1.0`

**Code change:** No feature threshold or matcher behavior changed in this sub-round. Documentation was corrected because the previous text still said the feature probe was not connected to runtime and described `weighted_blob` as the main default path.

**Verification:**
- Compile passed: `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\events\config_model.py core\events\types\loot\config.py core\events\types\loot\definition.py core\events\types\loot\minimap_detector.py core\events\types\loot\detection\feature_match\models.py core\events\types\loot\detection\feature_match\descriptors.py core\events\types\loot\detection\feature_match\semantics.py core\events\types\loot\detection\feature_match\matcher.py core\events\types\loot\perception\models.py core\events\types\loot\perception\projection.py core\events\types\loot\perception\async_worker.py`.
- Latest probe output: `debug/loot_feature_match_probe/20260603_174004/`, TP=25, FP=0, FN=0, TN=52, precision=1.0000, recall=1.0000, FPR=0.0000, avg=341.366ms, p95=664.686ms.
- Production async harness with valid `FrameRegistration`: TP=25, FP=0, FN=0, TN=52, elapsed wall time about 44.151s for 77 offline samples.

**CODEBASE.md updated:** Loot top-level section now states that `detection/feature_match/` is the production backend for `async_feature_match`, lists the probe-aligned defaults, and records sync/async parity verification.

**Coverage update:**
| File | Previous | Current | Reads | Note |
|------|----------|---------|-------|------|
| `core/events/types/loot/config.py` | (partial) | (partial) | appended | Rechecked feature defaults and map-config parity with probe defaults. |
| `core/events/types/loot/minimap_detector.py` | (partial) | (partial) | appended | Rechecked default async dispatch, sync feature mode, and weighted blob fallback. |
| `core/events/types/loot/perception/async_worker.py` | PENDING | (partial) | 1 | Rechecked worker submission, result merge, TTL, visibility update, and detection projection. |
| `core/events/types/loot/detection/feature_match/matcher.py` | PENDING | (partial) | 1 | Rechecked production matcher parity with probe on full sample set. |
| `architecture_docs/zh-CN/core/events/types/loot/ARCHITECTURE.md` | (partial) | (partial) | appended | Updated module tree and runtime algorithm description for async feature matching. |
| `CODEBASE.md` | (partial) | (partial) | appended | Updated loot summary and verification result. |

## [SYNC] 2026-06-03 18:05 - Loot async integration vs player localization diagnosis

### A. SYNC scope
**Task:** User reports latest runtime is no longer laggy, but player localization becomes inaccurate as soon as movement starts. Diagnose whether the new loot recognition / async feature matching path interferes with localization or navigation frame state.
**Direct files expected:** `gui/modes/navigation/runtime/*`, `core/localization/*`, `core/events/types/loot/*`, `core/events/coordinator/*`, `core/shared/frame_registration.py`, `CODEBASE.md`, `ITERATION_LOG.md`.
**Expected impact:** Identify whether loot detection mutates minimap frames, registration, localization state, or event/navigation targets; only change code if a concrete side effect or unsafe coupling is found.

## [SYNC] 2026-06-03 19:45 - Hook and event scheduler localization drift diagnosis

### A. SYNC scope
**Task:** Continue diagnosing whether player localization drift during movement is caused by hook key presses, event task scheduling, or event async observer load rather than direct loot frame mutation.
**Direct files expected:** `core/events/hooks/instances/key_press.py`, `core/events/hooks/runtime.py`, `core/navigation_tasks/event_task_runner.py`, `core/navigation_tasks/event_approach/*`, `gui/dialogs/event_manager/hooks/*`, recent `logs/event_runs/*`.
**Expected impact:** Confirm whether enabled hooks without event binding are skipped, whether visible/completed hooks are one-shot, whether repeated event tasks can influence movement/localization, and whether extra runtime probes are required.

## [SYNC] 2026-06-04 14:08 - Initial localization drift diagnosis probe

### A. SYNC scope
**Task:** User reports that initial global localization is already wrong before movement, so continue diagnosis with a reproducible first-frame localization probe and lightweight runtime coordinate sampling.
**Direct files expected:** `core/localization/*`, `core/navigation_tasks/coordinate/*`, `debug/navigation_localization_probe.py`, `map_data/A/config.json`, latest `debug/minimap_samples/A/*`.
**Expected impact:** Separate event/loot runtime effects from first-frame template matching behavior, preserve production localization code path, and produce artifacts that show raw minimap mask, map match patch, saved-position patch, and top candidate scores.

### C. SYNC result
**Key finding:** Current evidence does not support loot/event runtime as the direct cause of the reported initial wrong global localization. `capture_navigation_localization_tick()` localizes before event observation, the async event observer clones frames, recent event logs show `dropped=0`, and `map_data/A/config.json` has no git diff. The latest sample reproduces the wrong/contested point offline through first-frame `NavigationCore.localize()` alone.

**Probe result:** Added `debug/navigation_localization_probe.py` and ran it on `debug/minimap_samples/A/20260604_135548_439_A_minimap.png`. Latest output directory: `debug/navigation_localization_probe/20260604_142234_20260604_135548_439_A_minimap/`. Production settings used `draw_scale=3.0`, `wall_match_close_kernel_size=3`, template shape `600x600`, full-map search `7500x7500`.

**Observed localization:** Top candidate and `NavigationCore.localize()` result are both `(4211,3272)` with confidence `0.7744859457`, `frame_origin_global=(3911,2972)`. The saved map package `current_pos=(4792.48,3630.25)` scores `-0.02080567` on the same response map. Top candidate #2 is only `0.228927`, so the algorithm has a strong first choice, but it may still be the wrong gameplay location if the expected location is known.

**Differential check:** Executed the old `HEAD:core/recognizer_optimized.py` recognizer in-memory against the same sample and same `map_data/A/config.json` recognizer parameters. Old and current recognizers produced identical masks: `wall differing pixels=0`, `match differing pixels=0`; both matched `(4211,3272)` with confidence `0.7744859457`. This rules out the recognizer split and current `frame_matcher` extraction as the cause for this sample. If previous runtime was accurate, the remaining high-probability source is upstream input/map state: capture rectangle / player-local coordinate / live screenshot content / map package mismatch.

**Code change:** Added 500ms runtime localization sampling to `core/navigation_tasks/coordinate/localization.py` and exposed the interval in `CoordinateDiagnostics`. Fixed `coordinate/log.py` to write project-root `logs/coordinate_diagnostics.log`, and bridge coordinate diagnostics into current event session logs when available. Also preserved `drawing_saved_pos/last_pos` in `core/localization/navigation_core/state.py` so the saved map position remains visible to UI/debug after runtime state initialization; this does not automatically set `current_pos` or mark localization valid. Added `navigation capture geometry` event log in `gui/modes/navigation/runtime/localization_tick.py` whenever capture rectangle or player-local position changes.

**Verification:**
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\modes\navigation\runtime\localization_tick.py core\localization\navigation_core\state.py core\navigation_tasks\coordinate\log.py core\navigation_tasks\coordinate\diagnostics.py core\navigation_tasks\coordinate\localization.py debug\navigation_localization_probe.py` passed.
- Probe command passed and produced `report.json`, `wall_mask.png`, `match_mask.png`, `wall_mask_scaled.png`, `matched_map_patch.png`, `saved_pos_patch.png`, and `top_candidates_sheet.png`.

**Docs updated:** `CODEBASE.md`, `architecture_docs/zh-CN/core/ARCHITECTURE.md`, and `architecture_docs/zh-CN/core/navigation_tasks/ARCHITECTURE.md` now record the diagnostic probe, latest sample result, and coordinate sample logging behavior.

**Coverage update:**
| File | Previous | Current | Reads | Note |
|------|----------|---------|-------|------|
| `core/localization/localize_pipeline.py` | (partial) | (partial) | appended | Rechecked first-frame full-map template matching path and confirmed it reproduces without event runtime. |
| `core/localization/frame_matcher.py` | (partial) | (partial) | appended | Rechecked wall template scale/search-area helpers used by the probe. |
| `core/localization/map_package.py` | (partial) | (partial) | appended | Rechecked saved `current_pos`, draw scale, and wall close kernel loading. |
| `core/localization/navigation_core/state.py` | (partial) | (partial) | appended | Preserved saved drawing position for UI/debug while keeping initial localization untrusted. |
| `core/navigation_tasks/coordinate/localization.py` | (partial) | (partial) | appended | Added compact localization sample logging. |
| `gui/modes/navigation/runtime/localization_tick.py` | (partial) | (partial) | appended | Added capture geometry log to separate wrong screenshot region from matcher behavior. |
| `debug/navigation_localization_probe.py` | PENDING | (partial) | 1 | New standalone first-frame localization probe using production config and `NavigationCore`. |

## [SYNC] 2026-06-04 20:40 - Loot player mask UI and portal duplicate diagnosis

### A. SYNC scope
**Task:** User reports latest loot localization is acceptable, but the loot player erase/mask radius is too large and must be adjustable in the frontend/event panel. Portal recognition accuracy appears lower and portal events may be repeatedly recognized/localized; diagnose whether recent portal code changes or configuration caused it.
**Direct files expected:** `core/events/types/loot/definition.py`, `core/events/types/loot/config.py`, `gui/dialogs/event_manager_dialog.py`, `core/events/types/portal/*`, `core/events/position_stabilizer/*`, `core/events/memory/*`, `map_data/A/event_config.json`, recent `logs/event_runs/*`.
**Expected impact:** Make loot player-center mask radius clearly configurable from the GUI; identify portal detector mode / threshold / dedupe configuration or code-path causes for duplicate portal tasks; update Chinese architecture docs and CODEBASE if code changes are made.

### C. SYNC result
**Key findings:** The latest runtime log `logs/event_runs/20260604_201657_742_pid24360_navigation.log` started portal detection with `mode=feature_then_template`, while the current `map_data/A/event_config.json` has `portal.detector_mode="shape_color"`. That means the reported run used an older in-memory config or the file was saved after the run. Duplicate portal tasks in that log were not identical coordinates; they stabilized around nearby positions such as `(2983,1913)` and `(3032,1980)`, roughly 70-85 map pixels apart. The old portal defaults `localization_cluster_radius=56` and `dedupe_radius=32` were therefore too small to merge that duplicate/jitter band.

**Code changes:**
- `gui/dialogs/event_manager_dialog.py`: parameter rows now support schema `help` tooltips on both label and input widget.
- `core/events/types/loot/definition.py`: `player_center_mask_enabled` and `player_center_mask_radius` now have Chinese labels and help text; radius min lowered to 4 so the user can tune down an overly large center erase.
- `core/events/types/portal/config.py` and `core/events/config_model.py`: portal default `detector_mode` changed to `shape_color`; added `minimap_nms_radius=28`; default `localization_cluster_radius` and `dedupe_radius` changed to 96.
- `core/events/types/portal/definition.py`: exposed `minimap_nms_radius`, `dedupe_radius`, localization sample/TTL/emit parameters, cooldown radius, and exit completion radius in the event manager schema.
- `core/events/types/portal/minimap_detection/conversion.py`: accepted portal hits are now locally deduped by `minimap_nms_radius` before becoming `EventDetection`, preventing near duplicate template/scale hits from entering separate localization clusters.
- `map_data/A/event_config.json`: current map portal config now uses `max_candidates=2`, `minimap_nms_radius=28`, `localization_cluster_radius=96`, and `dedupe_radius=96`.

**Verification:**
- Compile passed: `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\dialogs\event_manager_dialog.py core\events\types\loot\definition.py core\events\types\portal\config.py core\events\types\portal\definition.py core\events\types\portal\minimap_detection\conversion.py core\events\config_model.py`.
- Local NMS harness passed: two dummy portal hits 20 local pixels apart with `minimap_nms_radius=28` produce `near 1`; hits 35 pixels apart produce `far 2`.
- Config reload check passed: `portal shape_color 2 28 96 96 700`; `loot_mask True 28`.

**Docs updated:** `CODEBASE.md`, `architecture_docs/zh-CN/core/events/types/portal/ARCHITECTURE.md`, and `architecture_docs/zh-CN/core/events/types/loot/ARCHITECTURE.md`.

**Coverage update:**
| File | Previous | Current | Reads | Note |
|------|----------|---------|-------|------|
| `core/events/types/loot/definition.py` | (partial) | (partial) | appended | Confirmed player center mask radius already existed, then made GUI label/help explicit. |
| `gui/dialogs/event_manager_dialog.py` | (partial) | (partial) | appended | Confirmed schema-driven param rendering and added tooltip support. |
| `core/events/types/portal/config.py` | (partial) | (partial) | appended | Updated defaults for detector mode, local NMS, cluster radius, and memory dedupe radius. |
| `core/events/types/portal/definition.py` | (partial) | (partial) | appended | Exposed portal duplicate-control and localization parameters in the event panel schema. |
| `core/events/types/portal/minimap_detection/conversion.py` | (partial) | (partial) | appended | Added accepted-hit local NMS before EventDetection conversion. |
| `core/events/position_stabilizer/clusters.py` | (partial) | (partial) | appended | Rechecked cluster merge behavior and confirmed old 56px radius caused nearby duplicate clusters. |
| `core/events/memory/lookup.py` | (partial) | (partial) | appended | Rechecked task dedupe behavior and confirmed old 32px radius allowed nearby duplicate tasks. |
| `map_data/A/event_config.json` | (partial) | (partial) | appended | Updated current map portal duplicate-control parameters. |
| `logs/event_runs/20260604_201657_742_pid24360_navigation.log` | PENDING | (partial) | 1 | Used as runtime evidence for feature_then_template mode and duplicate portal task distances. |

## [PLAN] 2026-06-08 - Event manager compact UI and navigation compact mode modularization

### A. Scope declaration before reading
**Task:** User wants a smaller, cleaner UI for testing events and navigation, with code organized as independent modular UI components for future optimization. Do not run the app yet; first produce a codebase-informed plan.
**Target files expected:** `gui/dialogs/event_manager_dialog.py`, `gui/dialogs/event_manager/*`, `gui/modes/navigation/ui/layout.py`, `gui/modes/navigation/widget.py`, `gui/modes/navigation/events/dialog_lifecycle.py`, `gui/modes/navigation/composition/lifecycles.py`, `architecture_docs/zh-CN/gui/dialogs/ARCHITECTURE.md`, `architecture_docs/zh-CN/gui/modes/navigation/ARCHITECTURE.md`.
**Expected impact:** Decide module boundaries for event manager compact/full modes and navigation compact layout before implementation; keep current full parameter editor intact while adding a small testing surface.

### C. Planning findings
**Key findings:** `EventManagerDialog` is already driven by event schemas and command signals, but its shell, event selector, parameter form, task table, footer actions, and hook panel are still assembled in one dialog class. `NavigationModeWidget` has been reduced to a composition root, but `gui/modes/navigation/ui/layout.py` still creates every navigation control in one horizontal toolbar and stores the map view as the main stretch widget. The current UI pain comes more from layout density and dialog size than from core algorithm coupling.

**Stable integration points to preserve:** `NavigationEventDialogLifecycle` and `ManualEventTestController` currently depend on `dialog.test_portal_button`; `connect_navigation_signals()` depends on stable `owner.btn_*`, `owner.params_button`, `owner.event_button`, `owner.sample_window_button`, and `owner.save_minimap_sample_button` attributes. The compact UI refactor should keep these attributes while moving construction and mode switching into focused UI modules.

**Planned module direction:** split event manager UI under `gui/dialogs/event_manager/` into dialog shell, shared state/context, schema form, task status view, footer actions, and compact/full page composition; split navigation UI under `gui/modes/navigation/ui/` into map view factory, primary toolbar, route-edit toolbar, secondary tools, status strip, and compact-mode controller. Keep existing public entry points (`EventManagerDialog`, `build_navigation_ui(owner)`, `connect_navigation_signals(owner)`) during the first implementation pass.

**Risk notes:** compact/full toggling must not create duplicate test buttons or reconnect signals repeatedly; event config mutation is in-place and should remain so for dict-backed event configs; route edit buttons must remain wired to `RoutePanelController`; map view size changes should affect presentation only and not alter capture geometry or localization parameters.

**Verification plan after implementation:** run `py_compile` on changed GUI modules first, then start the app only after user approval for runtime verification. Chinese architecture docs should be updated after code changes; English docs are not required for this UI pass unless `CODEBASE.md` must be synchronized.

**Coverage update:**
| File | Previous | Current | Reads | Note |
|------|----------|---------|-------|------|
| `gui/dialogs/event_manager_dialog.py` | (partial) | (partial) | appended | Confirmed schema-driven event config rendering, task table, command signals, hook panel integration, and fixed `test_portal_button` dependency. |
| `gui/dialogs/event_manager/hooks/panel.py` | (partial) | (partial) | appended | Confirmed hook table is already independent enough to keep as a full-mode tab or compact summary source. |
| `gui/modes/navigation/ui/layout.py` | (partial) | (partial) | appended | Confirmed one dense toolbar plus map view/status/route panel construction; suitable for UI package split. |
| `gui/modes/navigation/ui/signals.py` | (partial) | (partial) | appended | Confirmed signal wiring depends on stable owner button attributes, so compact modules must preserve those names. |
| `gui/modes/navigation/widget.py` | (partial) | (partial) | appended | Confirmed widget remains composition root and public wrapper surface, not the right place for compact layout logic. |
| `gui/modes/navigation/events/dialog_lifecycle.py` | (partial) | (partial) | appended | Confirmed event dialog lifecycle owns create/toggle/refresh and manual portal test button syncing. |
| `gui/modes/navigation/composition/lifecycles.py` | (partial) | (partial) | appended | Confirmed runtime initialization creates event dialog and manual test controller after UI construction. |
| `architecture_docs/zh-CN/gui/dialogs/ARCHITECTURE.md` | (partial) | (partial) | appended | Rechecked current dialog guidance and noted EventManager can become the compact/schema-form template. |
| `architecture_docs/zh-CN/gui/modes/navigation/ARCHITECTURE.md` | (partial) | (partial) | appended | Rechecked navigation UI boundaries, current public surface, and remaining optimization candidates. |

## [SYNC] 2026-06-08 - Event manager and navigation compact UI implementation

### A. SYNC scope
**Task:** Implement the approved compact/small-window UI plan. Split event manager and navigation UI construction into feature modules, keep stable public attributes/signals, add compact/full mode toggles, and update Chinese architecture docs after implementation.
**Direct files expected:** `gui/dialogs/event_manager_dialog.py`, new `gui/dialogs/event_manager/*` view modules, `gui/modes/navigation/ui/layout.py`, new `gui/modes/navigation/ui/*` component modules, `gui/modes/navigation/ui/signals.py`, `architecture_docs/zh-CN/gui/dialogs/ARCHITECTURE.md`, `architecture_docs/zh-CN/gui/modes/navigation/ARCHITECTURE.md`.
**Expected impact:** Presentation-only refactor. Core algorithms, event detection, capture geometry, navigation runtime, hook runtime, and map/session config should not change. Existing callers should continue to use `EventManagerDialog`, `build_navigation_ui(owner)`, and `connect_navigation_signals(owner)`.

### C. SYNC result
**Code changes:**
- `gui/dialogs/event_manager_dialog.py` is now a compatibility import shell; the real dialog moved to `gui/dialogs/event_manager/dialog.py`.
- Added `gui/dialogs/event_manager/layout.py`, `schema_form.py`, and `task_table.py`. The dialog now has a default compact page and a full tabs page. Both share the same event selector, global enable switch, command footer, config mutation path, and stable `test_portal_button` attribute.
- Compact event manager mode defaults to about `480x620`; full mode restores about `1040x780`. Compact mode shows event overview, common parameters, compact task state, and the existing save/refresh/test/reset actions.
- `gui/modes/navigation/ui/layout.py` is now a composition entry only. Toolbar construction moved to `components/toolbars.py`, map view creation to `components/map_view.py`, status label creation to `components/status.py`, and compact/full presentation policy to `compact/controller.py`.
- Navigation compact mode is enabled by default. Route editing tools are folded behind `路线工具`; map view maximum height is limited in compact mode and restored in full mode. Existing button attributes are still attached to `NavigationModeWidget`.

**Verification:**
- `py_compile` passed for all changed/new event-manager and navigation-UI modules.
- Import smoke check passed: old `gui.dialogs.event_manager_dialog.EventManagerDialog`, new `gui.dialogs.event_manager.EventManagerDialog`, `build_navigation_ui`, and `connect_navigation_signals` import successfully.
- Offscreen construction check passed for `EventManagerDialog`: compact/full mode toggles construct and preserve `test_portal_button` and `compact_task_table`.
- Offscreen fake-owner construction check passed for `build_navigation_ui(owner)`: all old button/view/status/route attributes exist; compact mode is true by default and route tools are hidden.

**Docs updated:** `architecture_docs/zh-CN/gui/dialogs/ARCHITECTURE.md` and `architecture_docs/zh-CN/gui/modes/navigation/ARCHITECTURE.md`. English docs intentionally not updated per user preference.

**Coverage update:**
| File | Previous | Current | Reads | Note |
|------|----------|---------|-------|------|
| `gui/dialogs/event_manager_dialog.py` | (partial) | (partial) | appended | Converted to compatibility shell while preserving old imports. |
| `gui/dialogs/event_manager/dialog.py` | PENDING | (partial) | 1 | New real event manager dialog shell with compact/full mode and stable command signals. |
| `gui/dialogs/event_manager/layout.py` | PENDING | (partial) | 1 | New event-manager UI composition module for header, compact page, full tabs, and footer. |
| `gui/dialogs/event_manager/schema_form.py` | PENDING | (partial) | 1 | New schema-to-widget factory and full/compact editor sync helper. |
| `gui/dialogs/event_manager/task_table.py` | PENDING | (partial) | 1 | New full/compact event task table renderer. |
| `gui/modes/navigation/ui/layout.py` | (partial) | (partial) | appended | Reduced to navigation UI composition entry with compact controller setup. |
| `gui/modes/navigation/ui/signals.py` | (partial) | (partial) | appended | Added compact-layout and route-tools button wiring. |
| `gui/modes/navigation/ui/components/toolbars.py` | PENDING | (partial) | 1 | New navigation toolbar builders preserving old owner button attributes. |
| `gui/modes/navigation/ui/components/map_view.py` | PENDING | (partial) | 1 | New map scene/view factory preserving scene item fields. |
| `gui/modes/navigation/ui/components/status.py` | PENDING | (partial) | 1 | New status-label factory. |
| `gui/modes/navigation/ui/compact/controller.py` | PENDING | (partial) | 1 | New presentation-only compact/full layout controller. |
| `architecture_docs/zh-CN/gui/dialogs/ARCHITECTURE.md` | (partial) | (partial) | appended | Updated EventManager modularization and compact/full mode rules. |
| `architecture_docs/zh-CN/gui/modes/navigation/ARCHITECTURE.md` | (partial) | (partial) | appended | Updated navigation UI component boundaries and compact mode behavior. |

## [SYNC] 2026-06-08 - Continue compact GUI development

### A. SYNC scope
**Task:** Continue GUI development after the first compact navigation/event-manager pass. Inspect remaining GUI surfaces that can still make the app cumbersome during gameplay testing, then implement the next low-risk modular UI improvement while preserving existing behaviour.
**Direct files expected:** `gui/main_window.py`, `gui/dialogs/nav_params_dialog.py`, `gui/dialogs/nav_params/*`, `gui/modes/navigation/ui/*`, `architecture_docs/zh-CN/gui/dialogs/ARCHITECTURE.md`, `architecture_docs/zh-CN/gui/modes/navigation/ARCHITECTURE.md`.
**Expected impact:** Presentation/modularization only unless inspection finds a direct blocker. Core algorithms, event runtime, capture geometry, and navigation task execution should remain unchanged.

### C. SYNC result
**Inspection finding:** The main window had no hard minimum size but started at `1400x900`, which is awkward on a single-screen gameplay setup. `NavParametersDialog` still put each tab's full content directly into a tab page, so parameter contents could force a large dialog instead of scrolling.

**Code changes:**
- Added `gui/dialogs/nav_params/layout_helpers.py` with `create_scrollable_tab()` and `apply_nav_params_window_mode()`.
- Updated `NavParametersDialog` so all six tabs are scrollable. The dialog now defaults to a compact `520x640` size and has a footer `完整模式/小窗模式` toggle that only changes sizing policy.
- Updated `MainWindow` default geometry from `1400x900` to `1100x760`, keeping manual resizing available.
- Updated `gui/modes/navigation/events/panel_adapter.py` to connect event-dialog signals once instead of disconnecting potentially unconnected slots. This removed PySide `RuntimeWarning` noise during offscreen window construction/close.

**Verification:**
- `py_compile` passed for `gui/main_window.py`, `gui/dialogs/nav_params_dialog.py`, `gui/dialogs/nav_params/layout_helpers.py`, and `gui/modes/navigation/events/panel_adapter.py`.
- Offscreen `NavParametersDialog` construction passed: six `QScrollArea` instances exist, compact toggle works, final compact size is `520x640`.
- Offscreen `MainWindow` construction/close passed: startup geometry is `1100x760`, navigation compact mode is true, and the previous event signal disconnect warnings are gone.

**Docs updated:** `architecture_docs/zh-CN/gui/dialogs/ARCHITECTURE.md` and `architecture_docs/zh-CN/gui/ARCHITECTURE.md`. English docs intentionally not updated.

**Coverage update:**
| File | Previous | Current | Reads | Note |
|------|----------|---------|-------|------|
| `gui/main_window.py` | (partial) | (partial) | appended | Reduced default startup geometry for single-screen testing. |
| `gui/dialogs/nav_params_dialog.py` | (partial) | (partial) | appended | Added scrollable tabs and compact/full sizing toggle while preserving config binding. |
| `gui/dialogs/nav_params/layout_helpers.py` | PENDING | (partial) | 1 | New nav parameter layout helper for scrollable tabs and sizing policy. |
| `gui/modes/navigation/events/panel_adapter.py` | (partial) | (partial) | appended | Removed noisy disconnect-first signal wiring by tracking connected dialog slots. |
| `architecture_docs/zh-CN/gui/dialogs/ARCHITECTURE.md` | (partial) | (partial) | appended | Updated NavParametersDialog modularization and small-window behavior. |
| `architecture_docs/zh-CN/gui/ARCHITECTURE.md` | (partial) | (partial) | appended | Recorded the smaller default main-window geometry. |

## [SYNC] 2026-06-08 - Nav parameters section builder extraction

### A. SYNC scope
**Task:** Continue GUI modularization by extracting the heaviest `NavParametersDialog` UI section construction into `gui/dialogs/nav_params/` modules. Preserve existing widget attribute names, config bindings, signals, labels, tooltips, and compact/full sizing behavior.
**Direct files expected:** `gui/dialogs/nav_params_dialog.py`, new or updated `gui/dialogs/nav_params/*`, `architecture_docs/zh-CN/gui/dialogs/ARCHITECTURE.md`, `ITERATION_LOG.md`.
**Expected impact:** Presentation-only refactor. `NavConfig` structure, `config_binding.py`, runtime config application, event runtime, localization, and navigation task behavior should not change.

### C. SYNC result
**Code changes:**
- Rewrote `gui/dialogs/nav_params_dialog.py` as a shell. It now owns only dialog lifecycle, Qt signals, `NavConfig` updates, click-radius estimation, compact/full size switching, and config write-back.
- Added `gui/dialogs/nav_params/sections.py`. It builds all six parameter tabs, section widgets, explanatory labels/tooltips, and the footer action bar while preserving every existing widget attribute name used by `field_specs.py` and `config_binding.py`.
- Kept `gui/dialogs/nav_params/layout_helpers.py` as the scrollable-tab and size-policy helper.

**Verification:**
- `py_compile` passed for `nav_params_dialog.py`, `nav_params/sections.py`, `nav_params/layout_helpers.py`, `nav_params/config_binding.py`, and `nav_params/field_specs.py`.
- Offscreen construction check passed: all `BOUND_FIELD_SPECS` widget attributes exist, `nav_tabs.count()==6`, six `QScrollArea` instances exist, and default compact size remains `520x640`.
- Offscreen `set_config_to_ui(NavConfig())` check passed: status becomes `参数已加载`, FPS writes as `10`, compact/full toggle returns to compact with button text `完整模式`.

**Docs updated:** `architecture_docs/zh-CN/gui/dialogs/ARCHITECTURE.md`.

**Coverage update:**
| File | Previous | Current | Reads | Note |
|------|----------|---------|-------|------|
| `gui/dialogs/nav_params_dialog.py` | (partial) | (partial) | appended | Converted to shell retaining signals/config update/write-back behaviour. |
| `gui/dialogs/nav_params/sections.py` | PENDING | (partial) | 1 | New section builders for all nav parameter tabs and action bar. |
| `gui/dialogs/nav_params/layout_helpers.py` | (partial) | (partial) | appended | Reused for scrollable tabs and compact/full sizing policy. |
| `gui/dialogs/nav_params/config_binding.py` | (partial) | (partial) | appended | Revalidated after section extraction; binding still resolves all widgets by stable attribute name. |
| `gui/dialogs/nav_params/field_specs.py` | (partial) | (partial) | appended | Revalidated `BOUND_FIELD_SPECS` against constructed dialog. |
| `architecture_docs/zh-CN/gui/dialogs/ARCHITECTURE.md` | (partial) | (partial) | appended | Updated NavParametersDialog section-builder architecture and remaining candidates. |

## [SYNC] 2026-06-08 - Mapping control panel scroll container

### A. SYNC scope
**Task:** Continue compact GUI work by making the mapping page control panel usable in smaller windows. Add a scroll container around the existing mapping controls while preserving all widget attributes, signal wiring, and mapping runtime behaviour.
**Direct files expected:** `gui/modes/mapping/ui/layout.py`, `architecture_docs/zh-CN/gui/modes/ARCHITECTURE.md`, `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`, `ITERATION_LOG.md`.
**Expected impact:** Presentation-only refactor. Mapping capture, recognition, stitching, config restore/save, runtime lifecycle, and parameter binding should not change.

### C. SYNC result
**Code changes:**
- Updated `gui/modes/mapping/ui/layout.py`: `create_mapping_control_panel()` now returns a `QScrollArea` and delegates existing control creation to `create_mapping_control_content()`.
- Added `owner.control_scroll_area` for explicit access/debug. All existing owner widget attributes and signal connections remain created inside the content panel.

**Verification:**
- `py_compile` passed for `gui/modes/mapping/ui/layout.py`, `gui/modes/mapping_widget.py`, and `gui/main_window.py`.
- Offscreen `MainWindow` construction/close passed: startup geometry remains `1100x760`, `mapping_widget.control_scroll_area` is a `QScrollArea`, and navigation compact mode remains enabled.

**Docs updated:** `architecture_docs/zh-CN/gui/modes/ARCHITECTURE.md` and `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`.

**Coverage update:**
| File | Previous | Current | Reads | Note |
|------|----------|---------|-------|------|
| `gui/modes/mapping/ui/layout.py` | (partial) | (partial) | appended | Added scrollable control panel wrapper while preserving control content and owner field names. |
| `gui/modes/mapping_widget.py` | (partial) | (partial) | appended | Revalidated construction through MainWindow after mapping UI wrapper change. |
| `gui/main_window.py` | (partial) | (partial) | appended | Revalidated small startup geometry and both mode construction after mapping scroll change. |
| `architecture_docs/zh-CN/gui/modes/ARCHITECTURE.md` | (partial) | (partial) | appended | Updated Mapping UI role to include scroll wrapper. |
| `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md` | (partial) | (partial) | appended | Updated mapping UI seam description and done checklist. |

## [SYNC] 2026-06-08 - Advanced settings dialog section extraction

### A. SYNC scope
**Task:** Continue GUI modularization by extracting `AdvancedSettingsDialog` tab/section UI construction into its `gui/dialogs/advanced_settings/` package. Preserve existing widget attribute names, button signals, presets/file IO helpers, and parent parameter application behavior.
**Direct files expected:** `gui/dialogs/advanced_settings_dialog.py`, new or updated `gui/dialogs/advanced_settings/*`, `architecture_docs/zh-CN/gui/dialogs/ARCHITECTURE.md`, `ITERATION_LOG.md`.
**Expected impact:** Presentation-only refactor unless a harmless signal/construct warning is found. Advanced settings JSON IO, presets, params adapter, recognizer/stitcher application, and config save/load semantics should not change.

### C. SYNC result
**Code changes:**
- Rewrote `gui/dialogs/advanced_settings_dialog.py` as a shell. It now owns dialog lifecycle, `apply_params_requested`, direct-apply compatibility, current params state, and save/load/preset behavior.
- Added `gui/dialogs/advanced_settings/tabs.py` with four scrollable tabs: image preprocessing, feature extraction, parameter management, and stitcher algorithm settings. It also builds the footer action buttons.
- Preserved all widget attribute names consumed by `params_adapter.py` and preset values.

**Verification:**
- `py_compile` passed for `advanced_settings_dialog.py`, `advanced_settings/tabs.py`, `params_adapter.py`, `file_io.py`, and `presets.py`.
- Offscreen construction check passed using a QWidget parent: required widget attributes exist, `tab_widget.count()==4`, four `QScrollArea` instances exist, and `collect_params_from_widgets()` returns 26 parameters.
- Preset application check passed using the combo item's actual text: high-contrast preset updates `clahe_clip` to `3.0` and `deepen_factor` to `1.5`. The PowerShell terminal displays Chinese preset text with encoding noise, but the Qt value path is correct.

**Docs updated:** `architecture_docs/zh-CN/gui/dialogs/ARCHITECTURE.md`.

**Coverage update:**
| File | Previous | Current | Reads | Note |
|------|----------|---------|-------|------|
| `gui/dialogs/advanced_settings_dialog.py` | (partial) | (partial) | appended | Converted to shell retaining apply/save/load/preset behavior and direct-apply compatibility. |
| `gui/dialogs/advanced_settings/tabs.py` | PENDING | (partial) | 1 | New scrollable tab/action UI builder preserving widget attributes. |
| `gui/dialogs/advanced_settings/params_adapter.py` | (partial) | (partial) | appended | Revalidated against new tabs; all required widget attrs still exist. |
| `gui/dialogs/advanced_settings/file_io.py` | (partial) | (partial) | appended | Rechecked unchanged save/load snapshot path used by shell. |
| `gui/dialogs/advanced_settings/presets.py` | (partial) | (partial) | appended | Rechecked preset names/value mapping used by tabs and adapter. |
| `architecture_docs/zh-CN/gui/dialogs/ARCHITECTURE.md` | (partial) | (partial) | appended | Updated advanced settings shell/tabs architecture and remaining direct-apply risk. |

## [SYNC] 2026-06-08 - Color picker dialog UI/preview boundary extraction

### A. SYNC scope
**Task:** Continue dialog modularization with `ColorPickerDialog`. Read the current dialog and helper modules, then extract a low-risk UI/preview boundary without changing HSV range calculation, mask generation semantics, accepted result shape, or optional debug output behavior.
**Direct files expected:** `gui/dialogs/color_picker_dialog.py`, new or updated `gui/dialogs/color_picker/*`, `architecture_docs/zh-CN/gui/dialogs/ARCHITECTURE.md`, `ITERATION_LOG.md`.
**Expected impact:** Presentation-only refactor unless a pure rendering helper extraction is obvious. Color sampling math, recognizer params, preview mask output, and debug artifact gating should remain unchanged.

### C. SYNC result
**Code changes:**
- Added `gui/dialogs/color_picker/layout.py` to build the help text, mode buttons, original-image panel, preview panel, result text, and footer buttons.
- Reduced `ColorPickerDialog.setup_ui()` to `build_color_picker_ui(self)`. The dialog still owns screenshot preprocessing, point sampling, HSV range calculation, preview refresh, reset, zoom state, and accepted result shape.
- Fixed the new layout module's relative import to `...widgets.clickable_label`.

**Verification:**
- `py_compile` passed for `color_picker_dialog.py`, `color_picker/layout.py`, `image_renderer.py`, `preview.py`, `debug_output.py`, and `hsv_ranges.py`.
- Offscreen construction with a dummy 64x64 BGR image passed: all expected controls exist, one `QScrollArea` exists, initial mode is `wall`, OK starts disabled, and zoom label is `100%`.
- Offscreen calculation path passed: simulated one wall click, `calculate_hsv_ranges()` produces a non-empty `wall_hsv` result, enables OK, and preserves saturation-filter recommendation behavior.

**Docs updated:** `architecture_docs/zh-CN/gui/dialogs/ARCHITECTURE.md`.

**Coverage update:**
| File | Previous | Current | Reads | Note |
|------|----------|---------|-------|------|
| `gui/dialogs/color_picker_dialog.py` | (partial) | (partial) | appended | Reduced setup_ui to layout delegation while preserving interaction/HSV/preview behavior. |
| `gui/dialogs/color_picker/layout.py` | PENDING | (partial) | 1 | New UI layout builder for color picker controls and panels. |
| `gui/dialogs/color_picker/image_renderer.py` | (partial) | (partial) | appended | Revalidated render path used by dialog after layout extraction. |
| `gui/dialogs/color_picker/preview.py` | (partial) | (partial) | appended | Revalidated preview mask path remains unchanged. |
| `gui/dialogs/color_picker/debug_output.py` | (partial) | (partial) | appended | Confirmed debug output remains gated by existing flag. |
| `gui/dialogs/color_picker/hsv_ranges.py` | (partial) | (partial) | appended | Revalidated HSV sampling/calculation path through simulated click. |
| `architecture_docs/zh-CN/gui/dialogs/ARCHITECTURE.md` | (partial) | (partial) | appended | Updated color picker layout/preview/helper architecture. |
## [P0] 2026-09-03 - Establish perception engine checkpoints

### A. Scope declaration

**Task:** Reframe the modularization around the missing game-agnostic perception engine, create a persistent recovery document, and write the ordered implementation plan before further runtime changes.

**Direct files:** `docs/PERCEPTION_ENGINE_CHECKPOINT.md`, `docs/plans/2026-09-03-perception-engine-implementation-plan.md`, `ITERATION_LOG.md`.

**Expected impact:** Documentation only. No existing Portal, Loot, minimap, navigation, input, or GUI runtime behavior should change in this round.

### C. Findings

- (verified) `core/perception/models.py`, `profiles.py`, `registry.py`, `color.py`, `template.py`, and `pipeline.py` provide a useful foundation.
- (verified) `PerceptionPipeline` currently combines detector creation, execution, confidence filtering, and spatial fusion in one module; it is not yet the requested named engine.
- (verified) Shape, Feature, and OCR are registered as unavailable extension points, not complete adapters.
- (verified) `gui/dialogs/perception/dialog.py` is a screenshot workbench, but it is not yet routed through an engine facade.
- (partial) Full test discovery has unrelated legacy import-path failures; the release audit will classify them after the new engine work.

### Coverage update

| File | Previous | Current | Reads | Note |
|---|---|---|---:|---|
| `docs/PERCEPTION_ENGINE_CHECKPOINT.md` | PENDING | partial | 1 | New recovery document with baseline, architecture contract, ordered queue, and audit notes. |
| `docs/plans/2026-09-03-perception-engine-implementation-plan.md` | PENDING | partial | 1 | Task-by-task implementation plan with test and commit gates. |
| `core/perception/pipeline.py` | partial | partial | 1 | Confirmed as compatibility pipeline pending decomposition behind a named engine. |
| `core/perception/registry.py` | partial | partial | 1 | Confirmed as algorithm catalog seam; provider registry still pending. |
| `gui/dialogs/perception/dialog.py` | partial | partial | 1 | Confirmed as UI test bench; direct algorithm construction must move behind engine public API. |

### Next task

Implement P1: `PerceptionEngine` facade and its contract tests. Write the failing test first, then add the smallest compatibility-backed implementation.

## [P1] 2026-09-03 - Add the perception engine facade

### A. Scope declaration

**Task:** Add a named, GUI-free `PerceptionEngine` entry point that registers and resolves profiles by game/scene/target and delegates one detection call to the current compatibility pipeline.

**Direct files:** `core/perception/engine.py`, `core/perception/__init__.py`, `tests/test_perception_engine.py`.

**Expected impact:** New core API only. Existing `PerceptionPipeline`, Portal/Loot, minimap, navigation, input, and GUI behavior must remain unchanged until the facade tests pass.

### B. Read target

- `core/perception/pipeline.py`: current detector creation, confidence filtering, and fusion implementation retained behind the facade.
- `core/perception/profiles.py`: immutable game/scene/target profile and copy contract.
- `core/perception/registry.py`: algorithm catalog and factory seam.

### C. Findings pending implementation

- The engine must own profile lookup and validation rather than expose detector classes to callers.
- Profile registration must store a defensive copy so later GUI edits cannot mutate the engine's active profile.
- Missing hierarchy keys should fail explicitly with `KeyError`; direct profile detection should preserve the pipeline's result and error behavior.

### Coverage update

| File | Previous | Current | Reads | Note |
|---|---|---|---:|---|
| `core/perception/engine.py` | PENDING | PENDING | 0 | New facade; test contract before implementation. |
| `core/perception/__init__.py` | partial | partial | 1 | Public export will add `PerceptionEngine`. |
| `tests/test_perception_engine.py` | PENDING | PENDING | 0 | New contract tests to be written first. |

### Next step

Create the failing P1 tests and record the initial failure before adding any implementation.

### C. P1 result

- Initial test result: failed as expected because `PerceptionEngine` was not exported from `core.perception`.
- Implementation: added `core/perception/engine.py` and exported `PerceptionEngine` from `core/perception/__init__.py`.
- Behavior: profile registration, defensive resolution, duplicate rejection, explicit missing-profile errors, and target-level detection are covered.
- Verification: `tests.test_perception_engine` passed 3/3; `compileall -q core/perception` passed.

### Coverage update

| File | Previous | Current | Reads | Note |
|---|---|---|---:|---|
| `core/perception/engine.py` | PENDING | partial | 1 | New facade with profile catalog and target-level detection contract. |
| `core/perception/__init__.py` | partial | partial | 1 | Exports `PerceptionEngine` without changing existing exports. |
| `tests/test_perception_engine.py` | PENDING | partial | 1 | Three contract tests cover detect, hierarchy lookup, defensive copy, and errors. |

### Next task

Start P2 by writing failing tests for separate detector runner, fusion, confirmation, and selection stages. Keep `PerceptionPipeline` as a compatibility shell while the engine adopts the new stages.

## [P2] 2026-09-03 - Split perception decision stages

### A. Scope declaration

**Task:** Add independent detector runner, candidate fusion, multi-frame confirmation, and candidate selection modules; update `PerceptionPipeline` to compose them without changing legacy one-frame behavior.

**Direct files:** `core/perception/stages/runner.py`, `fusion.py`, `confirmation.py`, `selection.py`, `core/perception/pipeline.py`, `core/perception/models.py`, `tests/test_perception_stages.py`, and affected perception tests.

**Expected impact:** Core perception execution only. No GUI, input, navigation, Portal, Loot, or minimap code should change in this task.

### B. Read target

- `core/perception/pipeline.py`: current inline execution, filtering, fusion, and error behavior.
- `core/perception/models.py`: stable `TargetDetection` and `PerceptionRunResult` data contracts.
- `core/perception/profiles.py`: `confirmation_frames`, `selection_strategy`, and `metadata.merge_radius` configuration already exist.

### C. Findings pending implementation

- Stage interfaces must be data-only and independently testable.
- `PerceptionRunResult` needs additive `selected` and `confirmed` fields so old callers reading `detections`, `by_algorithm`, and `errors` remain source-compatible.
- Confirmation state must be keyed by target profile and match candidates by target type, coordinate space, and spatial distance.

### Coverage update

| File | Previous | Current | Reads | Note |
|---|---|---|---:|---|
| `core/perception/stages/runner.py` | PENDING | PENDING | 0 | New detector execution stage. |
| `core/perception/stages/fusion.py` | PENDING | PENDING | 0 | New spatial candidate fusion stage. |
| `core/perception/stages/confirmation.py` | PENDING | PENDING | 0 | New multi-frame stability stage. |
| `core/perception/stages/selection.py` | PENDING | PENDING | 0 | New candidate selection policy stage. |
| `core/perception/pipeline.py` | partial | partial | 1 | Compatibility shell to compose stages. |
| `core/perception/models.py` | partial | partial | 1 | Additive run-result fields only. |
| `tests/test_perception_stages.py` | PENDING | PENDING | 0 | Failing stage contract tests to be written first. |

### Next step

Create the failing P2 stage tests and record the missing-module failure before implementation.
## [P2 review] 2026-09-03

### A. 本轮目标（阅读前声明）

**目标文件：**
- `core/perception/stages/runner.py`：确认算法实例隔离、结果契约与异常收集是否符合通用引擎边界。
- `core/perception/stages/fusion.py`：确认跨算法候选融合仅依据通用几何/置信度信息，不掺入游戏规则。
- `core/perception/stages/confirmation.py`：确认跨帧确认状态不会污染不同游戏、场景或目标。

**本轮要验证：** P2 的运行、融合、确认三段能独立组合；旧 `PerceptionPipeline` 兼容层没有把决策逻辑重新耦合进去；待确认的候选不会被误作为可执行结果。
### C. 本轮发现

**关键发现：** (verified) `DetectorRunner.run` 给每一个算法实例独立创建 detector、收集其输出，并把实例级异常转换为 `errors[instance_id]`；一次算法失败不会丢弃其它算法结果。`fuse_candidates` 只在 `target_type` 与 `coordinate_space` 一致且中心距离不大于半径时合并。`ConfirmationTracker.observe` 用调用方传入的 profile key 隔离轨迹，并在确认帧数大于 1 时只返回稳定轨迹。

**修订的旧结论：** 原先把 P2 理解为“所有候选经过固定全局确认后再输出”；现确认它是按 profile key 维护的短期确认状态，且每个候选有独立计数，能同时支持多个可见目标。

**新疑问：** `DetectorRunner.run` 当前信任 detector 返回的 `target_type`；需要在下一轮核查是否应该拒绝与 profile 目标不同的检测结果，避免错误配置跨目标污染。还需审查选择器与总装配层怎样处理“部分候选已确认”的情形。

**覆盖进度更新：**

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|---|---|---|---:|---|
| `core/perception/stages/runner.py` | 浅读 | 深度完整 | 1 | 验证了实例参数复制、异常隔离和输出类型检查。 |
| `core/perception/stages/fusion.py` | 浅读 | 深度完整 | 1 | 验证了同类型同坐标空间的贪心半径融合和证据保留。 |
| `core/perception/stages/confirmation.py` | 浅读 | 深度完整 | 1 | 验证了按 profile key 的稳定跟踪、空帧清除和单帧快捷路径。 |

**下一轮计划：** 阅读 `selection.py`、`pipeline.py`、`engine.py`，核实 P2 的装配边界、兼容层和未知策略错误契约。
## [P2 assembly review] 2026-09-03

### A. 本轮目标（阅读前声明）

**目标文件：**
- `core/perception/stages/selection.py`：确认选择规则是可配置的通用策略，不会触发点击或混入工作流语义。
- `core/perception/pipeline.py`：确认旧入口只做阶段编排与向后兼容，不重新实现 detector、融合或确认算法。
- `core/perception/engine.py`：确认公共引擎 API 只提供识别与 profile 管理，且以安全的 profile key 隔离确认状态。

**本轮要验证：** 选择、确认和结果组装对于“多目标、部分确认、未知策略、空结果、单算法错误”都有明确且可测试的行为；前端以后可以完全只依赖 `PerceptionEngine`。
### C. 本轮发现

**关键发现：** (verified) `PerceptionPipeline` 已只负责顺序编排：运行、置信度阈值、通用几何融合、按 `(game_id, scene_id, target_type)` 的时间确认、再选择一个候选。`select_candidate` 不产生输入副作用；`first` 保留上游顺序，`nearest` 有参考点时按距离，否则回退置信度，未知策略会明确抛出 `ValueError`。`PerceptionEngine` 校验公共输入类型、用深拷贝注册/返回 profile，并保持 GUI/输入/工作流依赖在外部。

**修订的旧结论：** 原先担心旧 `PerceptionPipeline` 仍重复实现融合与算法执行；现确认其具体实现已迁出至 stage，并且旧 `_fuse_candidates` 只是兼容包装。

**新疑问：** 替换一个已注册 profile 时，旧 profile 的 `ConfirmationTracker` 轨迹仍可能保留到新参数的第一帧；应在 `PerceptionEngine.register_profile(..., replace=True)` 成功替换后重置该 key 的确认状态。算法输出的 `target_type` 目前也未和 profile 做一致性校验，需由模型契约或 runner 明确处理。

**覆盖进度更新：**

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|---|---|---|---:|---|
| `core/perception/stages/selection.py` | 浅读 | 深度完整 | 1 | 验证了纯选择、nearest 回退和未知策略的失败契约。 |
| `core/perception/pipeline.py` | 浅读 | 深度完整 | 1 | 验证了 stage 编排、阈值过滤、profile-key 确认和兼容包装。 |
| `core/perception/engine.py` | 浅读 | 深度完整 | 1 | 验证了框架边界、输入检查、注册表防御拷贝及 key 约束。 |

**下一轮计划：** 阅读 P2 测试、结果模型、profile 模型；先以测试固定“替换 profile 清除确认状态”和“错误目标类型不能越过 profile 边界”，再以最小修改完成 P2。
## [P2 contract tests] 2026-09-03

### A. 本轮目标（阅读前声明）

**目标文件：**
- `tests/test_perception_stages.py`：确认现有 stage 行为覆盖了融合、确认、选择、错误隔离，并定义最小新增回归测试。
- `core/perception/models.py`：确认 `PerceptionRunResult` 及 `TargetDetection` 的不变量可承载确认/选择状态。
- `core/perception/profiles.py`：确认 target profile 是否在配置层校验选择策略和算法/目标契约。

**本轮要验证：** 先写失败测试，规定 profile 替换必须清空时间确认状态；并决定 detector 的 `target_type` 错配是在 runner 拒绝还是允许跨目标结果的唯一入口。
### C. 本轮发现

**关键发现：** (verified) `TargetDetection` 已强制非空目标名、二维中心与 0..1 置信度；`PerceptionRunResult` 能无损表达候选、按实例输出、错误、已选择结果、确认状态和每轨迹帧数。`TargetProfile` 只验证层级 ID、置信度、确认帧和实例 ID 唯一性，尚未验证选择策略。现有 stage 测试覆盖基本的异常隔离、融合、稳定确认和三种选择方式，但没有 profile 替换或目标类型错配的回归。

**修订的旧结论：** 原先把未知选择策略当作 pipeline 运行期才能发现的错误；现确认可以且应该在 `TargetProfile` 创建/加载时校验，从而让前端保存无效配置前就得到反馈。

**决定：** 统一算法实例一旦挂到 `TargetProfile(target_type=T)`，输出必须也为 `T`；这是 profile 作为“一个可操作目标”的边界。未来多类检测器要通过多个目标 profile 或上游 target selector 拆分，而不允许单次运行把其它目标混进结果。runner 会将错配作为该实例的受控错误。`selection_strategy` 只接受 `confidence`、`first`、`nearest`，并在 profile 构造时标准化小写。

**覆盖进度更新：**

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|---|---|---|---:|---|
| `tests/test_perception_stages.py` | 浅读 | 深度完整 | 1 | 识别了 P2 已覆盖行为和缺失的边界回归。 |
| `core/perception/models.py` | 浅读 | 深度完整 | 1 | 验证结果 DTO 的字段约束和确认/选择承载能力。 |
| `core/perception/profiles.py` | 浅读 | 深度完整 | 1 | 验证 profile 复制/序列化与缺失的选择策略校验。 |

**下一轮计划：** 先新增失败回归测试，再最小修改 runner、profile、engine；随后运行 P2 聚焦测试和编译检查。
## [P2 red tests] 2026-09-03

### A. 本轮目标（阅读前声明）

**目标文件：**
- `tests/test_perception_stages.py`：新增错配 `target_type` 与无效选择策略的失败测试。
- `tests/test_perception_engine.py`：新增替换 profile 后不能继承旧确认帧计数的失败测试。

**本轮要验证：** 先使现有实现因期望的通用安全契约而失败；测试只观察公共结果/异常，不依赖私有 `_tracks` 或 pipeline 内部数据结构。
### C. 本轮结果（红灯测试）

**失败证据：** 新增的 3 条公共契约测试均按预期失败：`TargetProfile(..., selection_strategy="random")` 未抛出；错误目标类型仍出现在 `DetectorRunner` 候选中；替换同 key profile 后第二帧被错误视为已确认。其余 7 条已有 stage/engine 测试通过，说明失败范围收敛在新定义的三个边界。

**同步记录：** `tests/test_perception_stages.py` 现在覆盖错误目标类型隔离和非法选择策略；`tests/test_perception_engine.py` 现在覆盖 profile 替换清除确认历史。这些测试只经公共 API 断言，允许后续内部实现继续拆分。

**覆盖进度更新：**

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|---|---|---|---:|---|
| `tests/test_perception_stages.py` | 深度完整 | 深度完整 | 2 | 新增两条红灯契约，用于约束 runner/profile 修改。 |
| `tests/test_perception_engine.py` | 浅读 | 深度完整 | 1 | 新增替换 profile 后不继承确认状态的红灯回归。 |

**下一轮计划：** 修改 `profiles.py`、`stages/runner.py`、`engine.py` 使三条失败契约转绿，再执行完整 P2 目标测试。
## [P2 contract fix] 2026-09-03

### A. 本轮目标（阅读前声明）

**目标文件：**
- `core/perception/profiles.py`：在 profile 构造点标准化并校验选择策略。
- `core/perception/stages/runner.py`：把目标类型错配转化为当前算法实例的受控错误。
- `core/perception/engine.py`：替换或删除 profile 时清除同 key 的确认状态。

**实现约束：** 不改变 `TargetDetection` 的算法通用性，不改输入/点击层，不让 GUI 参与判断；只让“profile 是一次单目标识别运行”的边界变得不可绕过。
### C. 本轮结果（P2 合同修复）

**实现结果：** `TargetProfile` 现在将选择策略标准化为小写，并仅接受 `confidence`、`first`、`nearest`；`DetectorRunner` 强制以 profile 的 `target_type` 创建算法参数，并将输出目标错配变为实例级 `errors`，不会污染候选；`PerceptionEngine` 在替换或注销 profile 时清除该 key 的跨帧确认状态。

**验证：** 感知核心聚焦集 15/15 通过：`tests.test_perception_stages`、`tests.test_perception_pipeline`、`tests.test_perception_engine`、`tests.test_perception_models`。`core/perception` 编译检查也通过。

**同步影响分析：** 调用方通过 `TargetProfile.from_dict()` 会更早得到无效选择策略的明确 `ValueError`；原本传入错误 `parameters.target_type` 的算法实例将按 profile 目标运行，符合单目标 profile 契约。engine 的注册/注销现在会清除内部短期状态，但不改变 profile 序列化或任何 GUI/输入 API。

**覆盖进度更新：**

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|---|---|---|---:|---|
| `core/perception/profiles.py` | 深度完整 | 深度完整 | 2 | 新增并验证选择策略白名单和规范化。 |
| `core/perception/stages/runner.py` | 深度完整 | 深度完整 | 2 | 新增并验证 profile 目标类型边界和实例级失败。 |
| `core/perception/engine.py` | 深度完整 | 深度完整 | 2 | 新增并验证 profile 生命周期清除确认轨迹。 |

**下一轮计划：** 审查并提交 P2 的所有未提交变更；随后进入 P3 provider seams，先定义帧、模板、OCR、特征后端的可替换资源边界与错误契约。
## [P2 completion review] 2026-09-03

### A. 本轮目标（阅读前声明）

**目标文件：**
- `core/perception/__init__.py`：确认公开导出无重复、无 GUI/输入依赖，并包含新的稳定 DTO/API。
- `docs/PERCEPTION_ENGINE_CHECKPOINT.md`：将 P2 的已验证范围、提交边界和 P3 前置条件写成可恢复的断点。
- `ITERATION_LOG.md`：核对本轮记录顺序、待办、测试证据，并归档 P2 完成状态。

**本轮要验证：** 只暂存感知架构及其文档/测试文件，严格排除用户已有的 `virtual_gamepad` 工作；检查 P2 diff 没有遗漏或意外 API 变动后创建一个独立提交。
### C. Completion-review finding

**关键发现：** (verified) 包导出无重复、未引入 GUI/输入依赖，P2 的 15 条聚焦测试与编译检查均通过；但默认 `PerceptionEngine.detect()` 仍委托给 `PerceptionPipeline.run()`，而 Pipeline 才持有 runner、confirmation 等状态。这样兼容类仍是运行时核心，和已确认的依赖方向“应用/GUI -> PerceptionEngine -> stages”冲突。

**修订的旧结论：** 先前把“存在 `PerceptionEngine` facade + 独立 stages”视为 P2 完成；现确认这只完成了 API 外观，尚未完成核心所有权反转。因此 P2 保持 `in progress`，不能在此状态提交为完成。

**决定：** 保持用户已确认的设计：`PerceptionEngine` 直接拥有 runner、fusion、confirmation、selection 编排与确认状态；`PerceptionPipeline` 仅持有一个 engine 并转发 `run/reset_confirmation`，作为旧 import 的兼容入口。不会改变 GUI、动作、旧游戏模块或 profile JSON 格式。

**覆盖进度更新：**

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|---|---|---|---:|---|
| `core/perception/__init__.py` | 浅读 | 深度完整 | 1 | 导出唯一、无 UI/输入依赖，RunResult 从 models 导出。 |
| `docs/PERCEPTION_ENGINE_CHECKPOINT.md` | 深度完整 | 深度完整 | 2 | 发现状态需保留 P2 in progress 并补充引擎所有权修复。 |
| `ITERATION_LOG.md` | 深度完整 | 深度完整 | 2 | 记录链已追加；后续需要整理本轮 Unicode 写入格式。 |

**下一轮计划：** 将该已批准的依赖反转设计写入计划/断点，写 red test 证明默认 engine 不再调用 pipeline，再以小步骤完成核心所有权反转。
## [P2 engine ownership plan] 2026-09-03

### A. 本轮目标（阅读前声明）

**目标文件：**
- `docs/plans/2026-09-03-perception-engine-implementation-plan.md`：复核原计划并追加经过确认的引擎所有权反转任务。
- `docs/PERCEPTION_ENGINE_CHECKPOINT.md`：写入 P2 未完成的准确原因和恢复入口。

**本轮要产出：** 一份 TDD 原子计划：先证实 engine 默认路径不再依赖 Pipeline，再把阶段状态移入 engine，最后把 Pipeline 降为无策略转发壳；每步有精确文件、验证命令和单独提交边界。
### C. 本轮计划发现

**关键发现：** (verified) 原计划把 P1 描述为“engine 委托兼容 pipeline”，且 P2 的目录路径误写成 `core/perception/pipeline/`；这正是当前所有权倒置的文档根源。checkpoint 的“明确缺失”也仍把已创建的 stage 文件列为缺失。

**修订的旧结论：** 原先认为 P2 的任务只是在 Pipeline 后面拆分 stages；现改为 P2 的完成条件是“默认 engine 自己持有 stages/确认状态，Pipeline 只转发”。

**TDD 原子计划：**

1. 在 `tests/test_perception_engine.py` 写失败测试，替换/监视 `PerceptionPipeline.run()` 并证明默认 engine 识别不走该方法；先运行该单项测试。
2. 在 `core/perception/engine.py` 移入运行、过滤、融合、确认、选择和 confirmation reset；保留显式注入 legacy pipeline 的兼容分支；使第 1 步测试转绿并提交。
3. 在 `tests/test_perception_pipeline.py` 写失败测试，断言 Pipeline 仍经 engine 公共检测 API 返回完全相同的 `PerceptionRunResult`；先运行该单项测试。
4. 在 `core/perception/pipeline.py` 删除所有策略状态，只转发 `run/reset_confirmation`；运行完整 P2 集、编译检查，更新 checkpoint 后提交。

**覆盖进度更新：**

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|---|---|---|---:|---|
| `docs/plans/2026-09-03-perception-engine-implementation-plan.md` | 深度完整 | 深度完整 | 2 | 定位到 P1 委托描述和 P2 错误目录，需追加精确反转步骤。 |
| `docs/PERCEPTION_ENGINE_CHECKPOINT.md` | 深度完整 | 深度完整 | 3 | 将更新为 stages 已存在、P2 所有权反转待完成。 |

**下一轮计划：** 保存详细设计/执行任务，接着为 engine 所有权写 red test；不接触 P3 provider 或 GUI。
### C. SYNC 结果（所有权设计与断点）

**已保存设计：** 新增 `docs/plans/2026-09-03-perception-engine-ownership-design.md`，记录所选方案、拒绝方案、默认引擎与兼容 Pipeline 的依赖图、四个 TDD 原子任务、精确测试命令、提交边界和非目标。

**更新断点：** 原实施计划已修正 P2 的真实 `stages/` 路径与“engine 直接执行”的完成条件；checkpoint 已将“stage 文件缺失”改为准确的“engine 所有权反转待完成”，并把恢复入口指向新设计文档。

**CODEBASE 同步：** 当前运行时结构未变，`CODEBASE.md` 保留并已准确记录 P2 所有权 defect；无需把尚未实现的设计伪写为当前事实。

**下一轮计划：** 按设计的 Task 1 在 engine 测试中写 red test，证明默认 engine 不会调用 `PerceptionPipeline.run()`；只有该测试失败后才移动执行所有权。
## [P2 engine ownership red test] 2026-09-03

### A. 本轮目标（阅读前声明）

**目标文件：**
- `tests/test_perception_engine.py`：以公共识别结果验证默认 engine 不经 `PerceptionPipeline.run()`。

**本轮要验证：** 在不改变运行时代码的前提下，替换 compatibility pipeline 的 `run` 为显式失败；默认 `PerceptionEngine().detect()` 应因此失败，证明目前存在待修正的依赖路径。测试不检查私有属性。
### C. 本轮结果（engine red test）

**失败证据：** 新测试失败于 `PerceptionEngine.detect()` 的 `self.pipeline.run(...)` 调用，且 mock 的 `AssertionError: compatibility path used` 被直接触发。这精确证明默认路径仍经 legacy Pipeline，没有其它算法、配置或环境噪声。

**同步记录：** `tests/test_perception_engine.py` 新增公共行为回归：默认 engine 即使 `PerceptionPipeline.run` 不可用，也必须完成颜色识别并产生已选择的 marker。测试本身不读取 engine 私有字段。

**覆盖进度更新：**

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|---|---|---|---:|---|
| `tests/test_perception_engine.py` | 深度完整 | 深度完整 | 2 | 新增精确依赖反转红灯测试并记录实际堆栈。 |

**下一轮计划：** 修改 `core/perception/engine.py` 直接编排已存在 stages，同时保留显式 legacy pipeline 注入分支；先使本测试转绿，再运行 engine/stage 聚焦集。
## [P2 direct engine execution] 2026-09-03

### A. 本轮目标（阅读前声明）

**目标文件：**
- `core/perception/engine.py`：让默认 engine 自己组合 runner、融合、确认、选择；保留显式 legacy pipeline 注入的向后兼容分支。

**实现约束：** 复用既有 `DetectorRunner`、`fuse_candidates`、`ConfirmationTracker`、`select_candidate`，不复制其算法；profile key、阈值、默认 merge 半径、RunResult 字段和 `reset_confirmation` 行为必须与当前 Pipeline 保持一致。
### C. SYNC 结果（默认引擎直接执行）

**实现结果：** `PerceptionEngine` 现在直接持有 `DetectorRunner` 和 `ConfirmationTracker`，并在私有 `_run_stages()` 中按既有顺序复用融合/选择 stage，返回原样的 `PerceptionRunResult`。显式传入 legacy pipeline 时仍走其 `run/reset_confirmation`，但默认构造路径不导入或构造 Pipeline。

**验证：** 新 red test 已转绿；`tests.test_perception_engine` 与 `tests.test_perception_stages` 共 11/11 通过，`compileall -q core/perception` 通过。

**影响分析：** profile 替换/注销现在通过 engine 自己的 `reset_confirmation` 清除状态；默认 detection 的阈值、半径、profile key、选择和错误字段与旧 Pipeline 行为一致。尚未修改 Pipeline，因此旧 `PerceptionPipeline` 仍暂时有自己的重复 stage 编排，下一轮将删去它。

**覆盖进度更新：**

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|---|---|---|---:|---|
| `core/perception/engine.py` | 深度完整 | 深度完整 | 3 | 默认路径已迁入 stage 组合和确认状态，legacy 注入分支保留。 |
| `tests/test_perception_engine.py` | 深度完整 | 深度完整 | 3 | 默认路径不调用 Pipeline 的 red/green 回归已通过。 |

**下一轮计划：** 为 `PerceptionPipeline` 写转发 red test，再将其降为只包含 registry、engine 和两项转发方法的兼容壳。
## [P2 pipeline forwarding red test] 2026-09-03

### A. 本轮目标（阅读前声明）

**目标文件：**
- `tests/test_perception_pipeline.py`：建立 compatibility Pipeline 只转发给其 engine 的公共测试，不依赖 runner/confirmation 私有实现。
- `core/perception/pipeline.py`：仅为理解当前重复编排而阅读；本轮先不修改。

**本轮要验证：** Pipeline 接收到 `run(frame, profile)` 时必须把相同 frame/profile 和显式 `reference=None` 交给其关联 engine 的 `detect`，并原样返回 engine 的结果；当前实现应因不存在关联 engine 而失败。
### C. 本轮结果（pipeline red test）

**失败证据：** 新的 compatibility 入口测试报出 `AttributeError: 'PerceptionPipeline' object has no attribute 'engine'`，精确证明它还不是转发壳，而仍持有自己的执行状态。

**同步记录：** `tests/test_perception_pipeline.py` 现在通过 Pipeline 的公开 `run()` 调用验证同一 frame/profile/reference 会转给关联 engine，且 engine 返回对象不被包装或修改。

**覆盖进度更新：**

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|---|---|---|---:|---|
| `tests/test_perception_pipeline.py` | 深度完整 | 深度完整 | 2 | 新增 pipeline 转发 red test；当前因缺少 engine 属性而失败。 |
| `core/perception/pipeline.py` | 深度完整 | 深度完整 | 2 | 确认其重复持有 runner/confirmation，是本轮唯一待删策略实现。 |

**下一轮计划：** 只修改 `pipeline.py`，通过局部导入避免循环依赖，创建默认 engine 并转发两个公开方法；保留 `_fuse_candidates` 旧私有导入包装。
## [P2 pipeline forwarding implementation] 2026-09-03

### A. 本轮目标（阅读前声明）

**目标文件：**
- `core/perception/pipeline.py`：将重复 stage 编排替换为一个 engine 实例和 `run/reset_confirmation` 转发；保留 `_fuse_candidates` 的旧导入兼容。

**实现约束：** 使用局部 import 解决 Engine/Pipeline 的单向运行时依赖；不改变 `PerceptionPipeline(registry)`、`run()`、`reset_confirmation()` 或 `_fuse_candidates()` 的调用签名；Pipeline 不再直接导入任何 stage 类。
### C. SYNC 结果（P2 兼容转发完成）

**实现结果：** `PerceptionPipeline` 现在只保存 registry 与一个默认 `PerceptionEngine`，用局部 import 避免循环导入，并将 `run(frame, profile, reference)`、`reset_confirmation(profile)` 原样转发。唯一保留的算法相关符号是 `_fuse_candidates()` 的旧私有导入兼容包装；它不参与 Pipeline 运行路径。

**验证：** P2 完整聚焦集 17/17 通过（stage、pipeline、engine、model）；感知包编译检查和公开包导入 smoke check 均通过。`git diff --check` 返回 0；仅报告仓库既有的 LF/CRLF 转换预警，没有空白错误。

**依赖结果：** 默认依赖方向已成为 `GUI/workflow -> PerceptionEngine -> stages`；旧调用为 `legacy caller -> PerceptionPipeline -> PerceptionEngine`。Pipeline 不再导入 runner、confirmation 或 selection，因此无法重新变成决策核心。

**覆盖进度更新：**

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|---|---|---|---:|---|
| `core/perception/pipeline.py` | 深度完整 | 深度完整 | 3 | 删除重复 stage 状态，保留兼容转发和 `_fuse_candidates`。 |
| `tests/test_perception_pipeline.py` | 深度完整 | 深度完整 | 3 | 转发 red/green 回归已通过，验证参数与返回对象保持不变。 |

**下一轮计划：** 复核感知 P2 全部 diff、更新 checkpoint/架构文档为完成状态，并只暂存这些文件创建 `feat: split perception decision stages` 提交。随后开始 P3 provider seams。
## [P2 final review and commit] 2026-09-03

### A. 本轮目标（阅读前声明）

**目标文件：**
- `docs/PERCEPTION_ENGINE_CHECKPOINT.md`：将 P2 完成条件、测试证据、P3 起点和仅感知文件的提交边界固化。
- `core/perception/__init__.py`：最终确认公开入口稳定、无 compatibility 循环问题。
- `core/perception/stages/__init__.py`：确认 package 文件只定义 stage 边界，不产生侧效应。

**本轮要验证：** 用路径白名单审查并暂存 P2 的 core、tests 和架构文档；绝不把 `virtual_gamepad/` 或任何其它用户现有修改带入提交。
### C. 最终审查发现

**关键发现：** (verified) `core/perception/__init__.py` 的公共导出无重复，公开 import smoke check 已通过；`stages/__init__.py` 仅重导出纯 stage API，没有创建 detector、确认状态或输入副作用。P2 白名单包含所有感知 core、tests、三份架构/断点文档；`virtual_gamepad/` 的修改均在白名单外。

**修订的旧结论：** checkpoint 仍将 P2 的 stage 所有权列为“明确缺失”；现已依据 17/17 测试和直接/兼容双路径验证改为 P2 complete，P3 才是下一项。

**提交白名单：** `CODEBASE.md`、`ITERATION_LOG.md`、`core/perception/{__init__,engine,models,pipeline,profiles}.py`、`core/perception/stages/`、三份 perception docs/plan、`tests/test_perception_{engine,pipeline,stages}.py`。不包含任意 `virtual_gamepad/` 文件。

**覆盖进度更新：**

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|---|---|---|---:|---|
| `core/perception/__init__.py` | 深度完整 | 深度完整 | 2 | 最终确认公共导出及循环导入 smoke check。 |
| `core/perception/stages/__init__.py` | 浅读 | 深度完整 | 1 | 仅公开纯 stage API，文档已改为 engine-owned。 |
| `docs/PERCEPTION_ENGINE_CHECKPOINT.md` | 深度完整 | 深度完整 | 4 | P2 状态、完成证据与 P3 起点已更新。 |

**下一轮计划：** 使用已声明的白名单暂存、复核 staged diff、创建 P2 提交；随后从 P3 的 provider 资源契约 red test 开始。
## [P3 template-resource discovery] 2026-09-03

### A. 本轮目标（阅读前声明）

**目标文件：**
- `core/perception/algorithms/template.py`：精读模板识别当前如何取得资源、如何处理路径/透明通道、以及哪些部分必须留在算法而非 provider。

**本轮要验证：** P3 的 template-resource provider 只负责资源定位/读取/明确错误，不改变模板匹配、缩放、掩码、NMS 或 `TargetDetection` 生成；识别算法仍应接收已解析的、可测试的资源输入。
### C. 本轮发现

**关键发现：** (verified) `TemplateDetector` 当前接收数组或路径：路径时直接 `cv2.imread(..., IMREAD_UNCHANGED)`，以 `FileNotFoundError` 表达不可读资源；读取后算法自行保留 alpha mask、颜色通道转换、多尺度、灰度/边缘匹配、NMS 和 `TargetDetection` 构建。provider 只能取代“由 resource_id 取得原始数组”的步骤，不能吸收这些匹配语义。

**修订的旧结论：** 原先把 template provider 视为能直接返回检测结果的候选方案；现确认它必须只返回带标识与元数据的原始资源，才能让模板、feature 等多个算法复用同一资源而输出仍由算法统一规范化。

**P3 设计结论：** 建立通用 `ProviderRegistry` 管理可用/实验/不可用 capability；建立类型化 `FrameSource`、`TemplateResourceProvider`、`OcrProvider`、`FeatureBackend` 合约和可序列化 DTO；`TemplateDetector` 保持兼容，P4 才通过 adapter 接入 provider。

**覆盖进度更新：**

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|---|---|---|---:|---|
| `core/perception/algorithms/template.py` | 深度完整 | 深度完整 | 2 | 精读路径读取、alpha/mask、多尺度、匹配和 NMS 边界。 |

**下一轮计划：** 阅读算法 descriptor/registry/builtins，确认 provider capability 状态与既有算法能力目录能共享的枚举和错误风格。
## [P3 capability-registry discovery] 2026-09-03

### A. 本轮目标（阅读前声明）

**目标文件：**
- `core/perception/algorithms/base.py`：确定算法 capability/status/参数描述的数据模式。
- `core/perception/registry.py`：确定可用、不可用、未知和 factory 失败的当前错误契约。
- `core/perception/builtins.py`：确定已有 color/template 与 shape/feature/OCR 未实现状态如何暴露给前端。

**本轮要验证：** provider registry 应复用算法目录的“descriptor + 可用性 + 受控错误”模式，但不能强迫具有不同输入/输出类型的 frame/template/OCR/feature provider 使用同一个不安全 factory 签名。
### C. 本轮发现

**关键发现：** (verified) `AlgorithmDescriptor` 已有 `available|experimental|unavailable` 三态及 GUI 参数元数据；`AlgorithmRegistry` 以 descriptor/factory 配对，未知 ID 为 `KeyError`，不可用/缺 factory 为 `RuntimeError`，并防御复制参数。builtins 把 shape/feature/OCR 正确标为不可用，但模板仍暴露 `template_path` 而非资源 ID。

**修订的旧结论：** 原先计划为每一种 provider 各写一个独立 registry；现确认应有一个通用 catalog/registration 容器，以 `ProviderDescriptor.capability` 区分类型，同时保留类型化 provider Protocol，才能同时满足前端发现能力与静态可读的调用契约。

**P3 contract：** `available` 和 `experimental` provider 必须注册实现；`unavailable` provider 只注册 descriptor；未知 provider、capability 不匹配、不可用 provider 分别抛出明确且不同的异常。Frame/Template/OCR/Feature 的 raw provider 输出在 adapters 中转为 `TargetDetection`，不能由 registry 伪装为一个统一 factory。

**覆盖进度更新：**

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|---|---|---|---:|---|
| `core/perception/algorithms/base.py` | 深度完整 | 深度完整 | 2 | 验证参数和三态 capability descriptor 模式。 |
| `core/perception/registry.py` | 深度完整 | 深度完整 | 2 | 验证 descriptor/factory、错误和防御复制契约。 |
| `core/perception/builtins.py` | 深度完整 | 深度完整 | 2 | 验证当前可用/不可用算法目录及模板路径耦合。 |

**下一轮计划：** 写 P3 provider DTO/registry 的详细计划与第一组 red tests：catalog 状态、未知/不可用/错误 capability 和不可变 descriptor 输出。
## [P3 provider-seams design] 2026-09-03

### A. 本轮目标（阅读前声明）

**目标文件：**
- `docs/plans/2026-09-03-perception-engine-implementation-plan.md`：将 P3 的泛化描述细化为可测试的 provider contract 步骤。
- `docs/PERCEPTION_ENGINE_CHECKPOINT.md`：确认 P3 是当前唯一进行项，且 P4 前不接入算法/GUI。

**本轮要产出：** provider 合约和 registry 的具体依赖图、DTO/异常边界、三态注册规则、四个 2–5 分钟 TDD 任务与验证命令；这些是后续 OCR/Feature/模板资源实现可替换而不绑定游戏的前提。
### C. 本轮计划结果

**关键发现：** (verified) P2 的提交已经落在 `6f60d12`，但 checkpoint 的 baseline hash 尚未前移；P3 在总计划中只有一段描述，缺少 provider 输出 DTO、错误分类与同 capability 多 provider 的解析规则，不能直接安全实现。

**确定设计：** 新建 `core/perception/providers/`：`contracts.py` 是无 OpenCV/GUI 依赖的数据、Protocol、错误；`registry.py` 是 descriptor+实现的 capability-safe catalog；`__init__.py` 是唯一公开 surface。Provider 原始结果与识别结果严格分层：`FrameContext` / `TemplateResource` / `OcrSpan` / `FeatureMatch` 不等于 `TargetDetection`。

**TDD 原子计划：**

1. contracts red/green：验证 descriptor 三态、模板/文字/特征 DTO 约束和 Protocol 导入不依赖可选 OCR/feature 包。
2. registry red/green：验证可用 provider 解析、未知 ID、capability 错配、不可用 descriptor、非可用但缺实现等不同错误。
3. public surface/default catalog red/green：验证只导出 contracts/registry，默认 catalog 使前端可发现尚未安装的 frame/template/OCR/feature capability，但不会伪称可执行。
4. P3 focused suite、compile/import audit、checkpoint/CODEBASE sync、独立提交；P4 才让 template/OCR/feature adapters 使用 registry。

**覆盖进度更新：**

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|---|---|---|---:|---|
| `docs/plans/2026-09-03-perception-engine-implementation-plan.md` | 深度完整 | 深度完整 | 3 | P3 需要独立细化计划，P2 记录正确。 |
| `docs/PERCEPTION_ENGINE_CHECKPOINT.md` | 深度完整 | 深度完整 | 5 | P2 已完成，P3 状态和基线需随新任务写入。 |

**下一轮计划：** 创建 provider seams 设计文档并更新 checkpoint；然后仅为 contracts 写第一组失败测试。
### C. SYNC 结果（P3 设计与断点）

**已保存设计：** 新增 `docs/plans/2026-09-03-perception-provider-seams-design.md`，明确定义 provider raw output、四类 Protocol、错误分类、可用性规则、四个 TDD 原子任务以及 P3 非目标。

**更新断点：** baseline 已更新为 `6f60d12`；P3 标记 `in progress`；实现计划引用新设计。P3 的“provider 不产出 TargetDetection、adapter 才产出”边界已记录，防止新算法重新高耦合资源获取与识别策略。

**CODEBASE 同步：** 当前运行时尚未增加 provider 源码，`CODEBASE.md` 不把设计文档误写成已实现结构；下一次源码实现后将新增 package 文件索引、调用链和风险登记。

**下一轮计划：** 建立 contracts 的 red test；确认新 provider package 在没有 OpenCV/OCR/feature 依赖时也可导入。
## [P3 provider contracts red test] 2026-09-03

### A. 本轮目标（阅读前声明）

**目标文件：**
- `tests/test_perception_providers.py`：新增 provider DTO、三态 descriptor、Protocol 可导入及无外部依赖的失败合同测试。

**本轮要验证：** 在 package 尚不存在时，测试必须因 `core.perception.providers` 缺失而失败；成功后才创建最小的 contracts 和公开 package surface。测试不实例化真实 OCR、特征或截屏实现。
### C. 本轮结果（provider contracts red test）

**失败证据：** `tests.test_perception_providers.ProviderContractTests` 在导入阶段按预期报出 `ModuleNotFoundError: No module named 'core.perception.providers'`。失败只证明 P3 package 尚不存在，未触及 OpenCV、OCR、特征或系统截屏环境。

**同步记录：** 新测试要求 descriptor 的防御性序列化、Template/OCR/Feature raw DTO、四个 Protocol 公共导入以及 ID/status/confidence 不变量；其断言明确禁止 OCR evidence 伪带 `target_type`。

**覆盖进度更新：**

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|---|---|---|---:|---|
| `tests/test_perception_providers.py` | PENDING | 深度完整 | 1 | 新增 contracts red test，当前失败为预期 package 缺失。 |

**下一轮计划：** 新建 `providers/__init__.py` 和 `providers/contracts.py`，以 stdlib typing/dataclasses 与已有 perception DTO 为唯一内部依赖，使本组测试转绿。
## [P3 provider contracts implementation] 2026-09-03

### A. 本轮目标（阅读前声明）

**目标文件：**
- `core/perception/providers/__init__.py`：建立唯一公开 package surface。
- `core/perception/providers/contracts.py`：实现 provider DTO、Protocol、三态 descriptor 和错误类型。
- `tests/test_perception_providers.py`：使已定义的 contracts red test 转绿。

**实现约束：** 只依赖 Python 标准库和既有 `core.perception.models`；不得 import OpenCV、PySide、平台捕获、OCR 或 ML 包；不引入 registry 或算法适配，避免超出 P3.1。
### C. SYNC 结果（provider contracts）

**实现结果：** 新增 `core/perception/providers/contracts.py` 与公开 `providers/__init__.py`。它们提供四类 raw provider Protocol、immutable descriptor/resource/evidence DTO，以及注册、未知、能力错配、不可用四类错误；没有 provider 直接产生 `TargetDetection`。

**验证：** contracts 聚焦测试 4/4 通过，provider package 编译通过。额外 import 检查显示 provider 模块本身没有 OCR/feature/capture 依赖；由于父包 `core.perception.__init__` 现有公开 imports 会加载 TemplateDetector，Python 进程仍已加载仓库既有的 `cv2`，这不是 provider contracts 新增依赖，P9 将统一审计 package import 延迟加载问题。

**影响分析：** 所有 DTO 使用已有 `FrameContext`、`BoundingBox`、`CoordinateSpace`，所以 OCR/Feature adapter 在 P4 能产出完整空间证据，但现在不修改任何算法、GUI、screen capture、输入或 legacy 模块。

**覆盖进度更新：**

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|---|---|---|---:|---|
| `core/perception/providers/contracts.py` | PENDING | 深度完整 | 1 | 新增 raw DTO、Protocol、descriptor 和明确错误层级。 |
| `core/perception/providers/__init__.py` | PENDING | 深度完整 | 1 | 新增稳定公开 exports，无运行时 provider 实例。 |
| `tests/test_perception_providers.py` | 深度完整 | 深度完整 | 2 | contracts red/green 4 条已通过。 |

**下一轮计划：** 为 `ProviderRegistry` 写 red tests，覆盖实现解析、capability 错配、未安装与注册规则；不接入任何真实 runtime provider。
## [P3 provider registry red test] 2026-09-03

### A. 本轮目标（阅读前声明）

**目标文件：**
- `tests/test_perception_providers.py`：为 registry 定义 provider 解析、capability 过滤、未知/错配/不可用错误和注册约束。

**本轮要验证：** 先在 `ProviderRegistry` 尚不存在时以 import failure 建立 API；一个 provider 只能按其 descriptor capability 被解析，registry 返回对象但绝不调用 provider 方法或处理 provider 输出。
### C. 本轮结果（provider registry red test）

**失败证据：** registry 测试在导入阶段按预期失败：`ProviderRegistry` 尚未从 `core.perception.providers` 暴露。contracts 原有测试未执行，表明失败范围是新 API 缺失而非 DTO 回归。

**同步记录：** 新测试固定了 registry 不能调用 provider、同 ID 必须按 capability 解析、discovery filter 保持 descriptor 对象顺序，以及四种明确失败路径。

**覆盖进度更新：**

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|---|---|---|---:|---|
| `tests/test_perception_providers.py` | 深度完整 | 深度完整 | 3 | 新增 registry red tests，当前失败为未实现 public registry。 |

**下一轮计划：** 新增 registry 模块并扩展公开 exports；只存储/解析 object provider，不实现具体 capture/OCR/template/feature provider。
## [P3 provider registry implementation] 2026-09-03

### A. 本轮目标（阅读前声明）

**目标文件：**
- `core/perception/providers/registry.py`：实现 descriptor 与 object provider 的 capability-safe 注册/解析。
- `core/perception/providers/__init__.py`：仅增加 registry 公开 exports。
- `tests/test_perception_providers.py`：使 registry contracts red tests 转绿。

**实现约束：** `register()` 不应调用 provider；`resolve()` 不应调用 provider；不做任何 `isinstance` Protocol 检查或输出转换；不允许可用/实验 descriptor 在没有 implementation 时登记。
### C. SYNC 结果（provider registry）

**实现结果：** 新增 `ProviderRegistry`。它按注册顺序保存 descriptor 与 provider object，注册时强制三态规则；解析时先校验 provider ID、再校验期望 capability、最后处理 unavailable，且从不调用 provider 或检查/转换其 raw output。

**验证：** providers 测试 6/6 通过，provider package 编译检查通过。可用 registry 返回完全相同的 object；未知、能力错配、不可用和非法注册均由不同异常类别表达。

**覆盖进度更新：**

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|---|---|---|---:|---|
| `core/perception/providers/registry.py` | PENDING | 深度完整 | 1 | 新增 capability-safe catalog、登记/发现/解析和失败分类。 |
| `core/perception/providers/__init__.py` | 深度完整 | 深度完整 | 2 | 扩展 registry 唯一公开 export。 |
| `tests/test_perception_providers.py` | 深度完整 | 深度完整 | 4 | registry red/green 2 条已通过，contracts 仍通过。 |

**下一轮计划：** 写 default provider catalog red test，使前端能发现四种尚未安装的 capability 且明确不可解析；不实现 OS/OCR/ML 后端。
## [P3 default catalog red test] 2026-09-03

### A. 本轮目标（阅读前声明）

**目标文件：**
- `tests/test_perception_providers.py`：定义默认 provider catalog 的发现/不可用契约。

**本轮要验证：** default catalog 应列出 `frame.screen`、`template.resource`、`ocr.default`、`feature.default` 四种 capability；每个均对前端可见但 `resolve` 明确失败，不创建现实后端。
### C. 本轮结果（default catalog red test）

**失败证据：** default catalog 测试按预期在 import 阶段失败：`create_default_provider_registry` 尚未公开。这一失败仅表示 discoverable catalog 未实现，没有触发任何 provider。

**同步记录：** 新测试锁定四个稳定 provider ID、对应 capability、全部 `unavailable` 状态，以及 OCR 解析会抛 `ProviderUnavailableError`；它防止未安装实现被前端错误展示为可运行。

**覆盖进度更新：**

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|---|---|---|---:|---|
| `tests/test_perception_providers.py` | 深度完整 | 深度完整 | 5 | default catalog red test 已加入，当前 API 缺失。 |

**下一轮计划：** 新增 provider builtins discovery catalog 并公开工厂；只登记 unavailable descriptor，不注册或执行任何实现。
## [P3 default catalog implementation] 2026-09-03

### A. 本轮目标（阅读前声明）

**目标文件：**
- `core/perception/providers/builtins.py`：创建仅供发现的四项 unavailable provider descriptor catalog。
- `core/perception/providers/__init__.py`：公开默认 catalog factory。
- `tests/test_perception_providers.py`：使 default catalog red test 转绿。

**实现约束：** catalog construction 不得访问 filesystem、桌面窗口、摄像头、网络、OCR/ML library 或 TemplateDetector；所有 descriptor 均无 implementation，解析行为仍由 `ProviderRegistry` 统一决定。
### C. SYNC 结果（default provider catalog）

**实现结果：** 新增 `providers/builtins.py` 的 `create_default_provider_registry()`。它只登记 `frame.screen`、`template.resource`、`ocr.default`、`feature.default` 四个 unavailable descriptor；没有实现 object、没有资源 I/O，也不会把可选后端列为 available。

**验证：** provider suite 7/7 通过，provider 编译检查通过，公开 factory smoke check 正确输出四个 stable ID。

**覆盖进度更新：**

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|---|---|---|---:|---|
| `core/perception/providers/builtins.py` | PENDING | 深度完整 | 1 | 新增可发现但未安装的默认 capability catalog。 |
| `core/perception/providers/__init__.py` | 深度完整 | 深度完整 | 3 | 公开 default catalog factory，未创建 runtime provider。 |
| `tests/test_perception_providers.py` | 深度完整 | 深度完整 | 6 | catalog red/green 已通过，总 provider suite 7 条通过。 |

**下一轮计划：** P3 final review：运行 provider + 既有 perception 全集，更新 checkpoint/CODEBASE 为 provider seams complete，只暂存 P3 白名单并独立提交。
## [P3 final review and commit] 2026-09-03

### A. 本轮目标（阅读前声明）

**目标文件：**
- `docs/PERCEPTION_ENGINE_CHECKPOINT.md`：将 P3 合约、错误、测试证据与 P4 前置条件固化。
- `core/perception/providers/__init__.py`：确认公开 exports 完整且不创建运行时 provider。
- `core/perception/providers/builtins.py`：确认默认 catalog 不触发外部 I/O。

**本轮要验证：** P3 provider tests 和既有 perception tests 一起通过；暂存仅 provider package、provider tests 与 perception docs，不混入 virtual_gamepad 用户修改。
### C. 最终审查结果

**验证：** provider 与既有 perception 聚焦集共 24/24 通过；`compileall -q core/perception` 和 `git diff --check` 均返回 0。diff check 只打印仓库既有 LF/CRLF 工作区预警，无 whitespace error。

**审查结论：** provider package 未修改 TemplateDetector、Engine、Pipeline、GUI、输入、Portal/Loot/minimap 或空间映射。其默认 catalog 无实现对象，因而不会意外调用 filesystem、Windows capture 或可选 OCR/ML backend。`core/events/window_finder.py` 和 `virtual_gamepad/` 均是白名单外用户修改，绝不暂存。

**CODEBASE 同步：** 已记录 contracts、registry、default catalog 的文件职责、算法边界和无 I/O 风险。checkpoint 标记 P3 complete，并把 P4 起点限定为“先做模板资源 provider adapter”。

**下一轮计划：** 仅暂存 P3 provider package、provider test 和 perception documentation，复核 staged diff 后提交 `feat: add perception provider seams`；再以 P4 模板资源 bridge 的 red test 继续。
## [P4 template-provider design discovery] 2026-09-04

### A. 本轮目标（阅读前声明）

**目标文件：**
- `core/perception/algorithms/template.py`：识别模板资源加载与匹配逻辑的精确分界。
- `core/perception/builtins.py`：识别 profile 参数到模板算法 factory 的兼容路径。
- `tests/test_perception_algorithms.py`：识别当前模板匹配兼容行为和可加入的 provider bridge 回归入口。

**本轮要澄清：** P4 的第一个适配器是否应以 `template_resource_id + TemplateResourceProvider` 替代文件路径读取，同时保持数组和 `template_path` 作为向后兼容入口；provider 输出不能越过算法层直接生成 `TargetDetection`。
### C. 本轮发现

**关键发现：** (verified) `TemplateDetector` 的“模板文件路径 -> 像素数组”读取与匹配算法当前同处一类；其 array 输入已经证明匹配逻辑可独立于文件资源。`_create_template()` 也只接受 array 或 `template_path`，还没有任何 `template_resource_id` 或 provider 注册表入口。现有模板测试覆盖多尺度、bbox、空间和算法 evidence，但未覆盖 provider 资源来源。

**修订的旧结论：** 原先把 P4 理解成替换 `TemplateDetector` 为一个 provider-aware detector；现确认最小且安全的方向是保留 detector 的数组/path 兼容构造器，新增一个 provider adapter/factory：先 `TemplateResourceProvider.load(resource_id)`，再把 `resource.image` 交给未变的 detector。这样不会把 provider 生命周期或资源 ID 侵入匹配循环。

**待确认设计选择：** provider 的绑定点可放在算法 registry factory、独立的 adapter 类，或同时允许二者；这会影响 P4 的公共 API 和 GUI 后续如何传入 composition context。

**覆盖进度更新：**

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|---|---|---|---:|---|
| `core/perception/algorithms/template.py` | 深度完整 | 深度完整 | 3 | 确认数组输入可复用，路径 I/O 是唯一待替换边界。 |
| `core/perception/builtins.py` | 深度完整 | 深度完整 | 3 | 确认当前 factory 无 provider/context 注入点。 |
| `tests/test_perception_algorithms.py` | 浅读 | 深度完整 | 1 | 当前只验证模板算法本身，缺少 provider bridge 回归。 |

**CODEBASE 同步：** 当前代码事实未改变；P4 的未决绑定点未写入 `CODEBASE.md`，防止把设计选择误记为已实现结构。
## [P4 template-resource adapter plan] 2026-09-04

### A. 本轮目标（阅读前声明）

**目标文件：**
- `docs/plans/2026-09-04-template-resource-adapter-design.md`：保存已确认的独立资源适配器设计和 TDD 任务。
- `docs/PERCEPTION_ENGINE_CHECKPOINT.md`：把用户确认的第 1 方案写入恢复点。
- `docs/plans/2026-09-03-perception-provider-seams-design.md`：核对 P3 provider contract 与 P4 adapter 的接口衔接。

**本轮要完成：** 不修改运行时代码，先把“`TemplateResourceProvider.load(resource_id)` → adapter → 现有 `TemplateDetector` 数组输入”的设计、兼容规则、测试命令和提交边界固化。
### C. 本轮结果

**设计决定：** 用户已确认独立资源适配器方案。新增设计文档将 provider 获取与模板匹配明确分层：provider 只返回 `TemplateResource`，adapter 只组装资源与算法，`TemplateDetector` 继续负责灰度/边缘、多尺度、alpha mask、阈值、NMS 和 `TargetDetection` 输出。

**兼容决定：** `template` 数组和 `template_path` 继续可用；只有 `template_resource_id` 才要求运行时注入 provider；同时提供多个资源来源时显式报配置错误；provider 对象不进入 profile JSON。

**文档同步：** 新增 `docs/plans/2026-09-04-template-resource-adapter-design.md`，更新总体实施计划与 checkpoint，P4 标记为 in progress。当前未修改任何运行时代码。

**覆盖进度更新：**

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|---|---|---|---:|---|
| `docs/plans/2026-09-04-template-resource-adapter-design.md` | PENDING | 深度完整 | 1 | 记录第 1 方案、API 边界、TDD 任务和兼容规则。 |
| `docs/PERCEPTION_ENGINE_CHECKPOINT.md` | 深度完整 | 深度完整 | 5 | 已记录用户选择、P4 起点和 provider 注入规则。 |
| `docs/plans/2026-09-03-perception-engine-implementation-plan.md` | 深度完整 | 深度完整 | 4 | 将 P4 首个切片指向模板资源 adapter。 |

**下一步：** 按计划 Task 1 编写 `ProviderBackedTemplateDetector` 的失败测试；本轮先不实现代码，待 red test 建立后再继续。
## [P4 Task 1 red test] 2026-09-04

### A. 本轮目标（阅读前声明）

**目标文件：**
- `tests/test_perception_template_adapter.py`：定义独立 `TemplateResourceProvider` 到现有模板算法数组输入的失败合同。

**本轮要验证：** 适配器在构造时只调用 provider 一次，要求返回 `TemplateResource`，把原始 `image` 交给 `TemplateDetector`，并保持目标类型、bbox、置信度和 source 输出；适配器缺失或空资源 ID 必须在边界处失败。
### C. 本轮结果（Task 1 red）

**失败证据：** 新测试在导入阶段按预期报出 `ModuleNotFoundError: core.perception.algorithms.template_adapter`。失败仅表示适配器尚未实现；测试 fixture 已将 provider 调用次数、资源 DTO、空 ID、provider 类型和 provider error 边界固定下来。

**覆盖进度更新：**

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|---|---|---|---:|---|
| `tests/test_perception_template_adapter.py` | PENDING | 深度完整 | 1 | 新增 provider-backed 模板适配器红灯合同。 |

**下一步：** 新建 `core/perception/algorithms/template_adapter.py`，只组合 `TemplateResourceProvider.load()` 与未修改的 `TemplateDetector`。
### C. 本轮结果（Task 1 green）

**实现结果：** 新增 `ProviderBackedTemplateDetector`。构造时校验非空 resource ID 和 `load()` 方法，调用 provider 一次并要求 `TemplateResource`，再把唯一的 `resource.image` 交给现有 `TemplateDetector`；`detect()` 只转发原有匹配结果，不复制任何匹配算法。

**验证：** `tests.test_perception_template_adapter` 3/3 通过；`compileall -q core/perception/algorithms` 通过。provider error 没有被路径 fallback 吞掉。

**覆盖进度更新：**

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|---|---|---|---:|---|
| `core/perception/algorithms/template_adapter.py` | PENDING | 深度完整 | 1 | 新增 resource provider 到 TemplateDetector 数组输入的组合适配器。 |
| `tests/test_perception_template_adapter.py` | 深度完整 | 深度完整 | 2 | provider 加载一次、类型/ID/error 边界和识别输出已通过。 |

**CODEBASE 同步：** 已在架构索引新增 adapter 职责、算法步骤、失败行为和调用关系。

**下一步：** 为 builtins factory 写失败测试，要求 runtime 显式传入 provider 才能使用 `template_resource_id`；保持原 `template` 和 `template_path` 参数兼容。
## [P4 Task 2 red test] 2026-09-04

### A. 本轮目标（阅读前声明）

**目标文件：**
- `tests/test_perception_template_adapter.py`：为 `create_template_detector(parameters, template_provider=None)` 定义资源 ID、provider、旧数组/路径兼容和歧义输入行为。

**本轮要验证：** factory 只负责构造/组合，不执行识别；provider 依赖是显式运行时参数，不写入 `TargetProfile`；缺 provider、缺资源字段、同时传多个资源来源都必须明确失败。
### C. 本轮结果（Task 2 red）

**失败证据：** factory 测试在导入阶段按预期失败：`core.perception.builtins` 尚未公开 `create_template_detector`。Task 1 的 3 条测试仍保留为绿色基线，当前失败只针对新的 factory 组合入口。

**覆盖进度更新：**

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|---|---|---|---:|---|
| `tests/test_perception_template_adapter.py` | 深度完整 | 深度完整 | 3 | 新增 factory 资源 ID/provider、旧兼容和歧义输入 red tests。 |

**下一步：** 在 `builtins.py` 增加显式 `create_template_detector()`，让 `_create_template()` 仅做兼容包装；不修改 AlgorithmRegistry 的 provider 无感知设计。
### C. 本轮结果（Task 2 green）

**实现结果：** `builtins.py` 新增 `create_template_detector(parameters, template_provider=None)`：明确区分 `template` 数组、`template_path` 和 `template_resource_id` 三种来源；资源 ID 必须有显式 provider；多来源和无来源会立即报 `ValueError`；`_create_template()` 保留为无 provider 的旧兼容包装。

**验证：** 模板适配器 + 现有算法测试共 8/8 通过；`compileall -q core/perception` 通过。数组入口实际使用 NumPy 数组，不触发数组 truth-value 异常；旧模板算法的多尺度/bbox 测试仍通过。

**覆盖进度更新：**

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|---|---|---|---:|---|
| `core/perception/builtins.py` | 深度完整 | 深度完整 | 4 | 新增显式资源来源 factory，旧 `_create_template` 继续兼容。 |
| `tests/test_perception_template_adapter.py` | 深度完整 | 深度完整 | 4 | factory red/green 与旧数组/路径/歧义行为已覆盖。 |

**CODEBASE 同步：** 已更新 `builtins.py` 与 template adapter 的职责和调用链说明。

**下一步：** Task 3 设计运行时 provider composition seam；先写失败测试验证 `PerceptionEngine` 可以注入 provider-aware template factory，同时默认 engine 不要求 provider，且 profile JSON 不序列化 provider object。
## [P4 Task 3 red test] 2026-09-04

### A. 本轮目标（阅读前声明）

**目标文件：**
- `tests/test_perception_template_adapter.py`：验证 provider-aware template factory 可以通过 `PerceptionEngine` 的显式运行时 composition hook 注入；默认 engine 在没有 provider 时仍保持明确错误。

**本轮要验证：** provider object 只存在于 runtime factory closure，不进入 `TargetProfile.to_dict()`；同一 profile 仍可在默认 engine 与 provider-aware engine 中复用。
### C. 本轮结果（Task 3 green）

**实现结果：** `PerceptionEngine` 新增可选 `algorithm_factories` runtime composition hook；`DetectorRunner` 对指定算法 ID 使用深拷贝参数调用 override factory，并先确认该 ID 在 registry 中有 descriptor。provider 对象可被外部 closure 捕获，但不进入 profile 或 JSON；显式注入 compatibility Pipeline 时禁止同时注入 overrides，避免两套执行语义。

**验证：** 模板 adapter + 现有算法测试共 10/10 通过；`compileall -q core/perception` 通过。测试确认 provider-backed engine 能输出 detection，默认 engine 对 resource ID 返回受控错误，profile JSON 只保留 resource ID。

**同步影响：** 算法 registry 仍不理解 provider；runtime composition 只替换指定 algorithm factory，未修改旧 color/template descriptor 或 Pipeline 行为。未知 override ID 会沿用 registry 的 descriptor 错误路径。

**覆盖进度更新：**

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|---|---|---|---:|---|
| `core/perception/stages/runner.py` | 深度完整 | 深度完整 | 3 | 新增深拷贝参数的 factory override 运行时 seam。 |
| `core/perception/engine.py` | 深度完整 | 深度完整 | 4 | 新增显式 algorithm factory 注入与 compatibility 冲突校验。 |
| `tests/test_perception_template_adapter.py` | 深度完整 | 深度完整 | 5 | engine runtime composition 和无 provider 错误契约已通过。 |

**下一步：** 进入 P4 Task 4：补充 `algorithms/__init__.py` / CODEBASE / checkpoint 的公开入口说明，运行完整 P4 聚焦集，确认没有循环导入和旧兼容回归后提交。
## [P4 template adapter public-surface red test] 2026-09-04

### A. 本轮目标（阅读前声明）

**目标文件：**
- `tests/test_perception_template_adapter.py`：锁定 `ProviderBackedTemplateDetector` 从 `core.perception.algorithms` 公共入口可导入。
- `core/perception/algorithms/__init__.py`：仅增加稳定导出，不改变算法构造或运行行为。

**本轮要验证：** 后续 GUI/应用可使用算法包公共入口而非深层文件路径；旧 `TemplateDetector`、ColorRegionDetector 和参数描述 exports 保持不变。
### C. 本轮结果（public-surface red）

**失败证据：** 公共入口测试按预期在导入阶段失败：`core.perception.algorithms` 尚未导出 `ProviderBackedTemplateDetector`。深层模块导入仍可用，说明只缺 package surface。

**覆盖进度更新：**

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|---|---|---|---:|---|
| `tests/test_perception_template_adapter.py` | 深度完整 | 深度完整 | 6 | 新增公共入口 red test，当前仅 package export 缺失。 |
| `core/perception/algorithms/__init__.py` | 浅读 | 深度完整 | 2 | 确认已有四项 exports，待增加 adapter。 |

**下一步：** 增加单一公共 export，运行 P4 模板 adapter 全集与原感知 suite。
### C. 本轮结果（template adapter slice）

**实现结果：** 第 1 方案已实际落地：`ProviderBackedTemplateDetector` 独立加载 `TemplateResource`，`create_template_detector()` 负责选择资源来源，`PerceptionEngine.algorithm_factories` 提供运行时注入。现有 `TemplateDetector` 不承载 provider，也未改变匹配算法。

**验证：** P4 当前切片全套测试 32/32 通过，包含 provider contracts、template adapter、现有 color/template、engine、pipeline、stage 和 model 测试；`compileall -q core/perception` 和公共 import smoke 通过。

**审查结论：** 未修改 GUI、输入、导航、Portal/Loot/minimap、坐标映射或 `virtual_gamepad`。provider 对象不会出现在 profile JSON；默认 engine 对 resource ID 无 provider 时返回实例级错误而不是 fallback。P4 总任务保持 in progress，后续仍需 OCR、Feature、Shape、Motion adapter。

**覆盖进度更新：**

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|---|---|---|---:|---|
| `core/perception/algorithms/template_adapter.py` | 深度完整 | 深度完整 | 2 | 已验证独立 provider 资源加载和算法委托。 |
| `core/perception/algorithms/__init__.py` | 深度完整 | 深度完整 | 3 | 已验证公共 adapter export。 |
| `core/perception/builtins.py` | 深度完整 | 深度完整 | 5 | 已验证三种资源来源选择、歧义和缺 provider 错误。 |
| `core/perception/stages/runner.py` | 深度完整 | 深度完整 | 4 | 已验证 runtime factory override 不破坏 descriptor/目标类型边界。 |
| `core/perception/engine.py` | 深度完整 | 深度完整 | 5 | 已验证 provider object 仅存在 runtime composition。 |
| `tests/test_perception_template_adapter.py` | 深度完整 | 深度完整 | 7 | 7 条 adapter/composition/public-surface 测试全部通过。 |

**下一步：** 仅暂存 P4 模板 adapter 相关源码、测试和文档，复核 staged diff 后提交；随后继续 P4 的 OCR provider adapter 设计，不接 GUI。
## [SYNC] 2026-09-04 - Template adapter typing polish

### A. SYNC 范围声明

**触发任务：** 将 `PerceptionEngine.algorithm_factories` 类型从具体 `dict` 放宽为只读语义更准确的 `Mapping`，不改变运行时行为。

**直接变更文件：** `core/perception/engine.py`。

**预期连带影响：** 仅静态 API 签名；模板 adapter、runner、profile、Pipeline 和 GUI 行为不变。

### C. SYNC 结果

**连带重读文件：** `core/perception/engine.py`，确认构造时仍复制 mapping、runner 仍接收 factory overrides，compatibility pipeline 冲突校验不变。

**验证：** 下一次 P4 staged 检查将覆盖 32 条聚焦测试与 compileall；此修改不引入新测试分支。
## [Virtual gamepad dual-input design discovery] 2026-09-04

### A. 本轮目标（阅读前声明）

**目标文件：**
- `virtual_gamepad/host/src/VirtualGamepadHost/Input/RawInputCapture.cs`：确认当前原始输入源识别、设备生命周期和事件模型。
- `virtual_gamepad/host/src/VirtualGamepadHost/Input/MappingConfig.cs`：确认现有绑定配置是否支持多个 source、同键多绑定和持久化。
- `virtual_gamepad/host/src/VirtualGamepadHost/Input/MappingEngine.cs`：确认映射合并、冲突、输出目标按键的当前规则。
- `virtual_gamepad/ui/virtual_gamepad_ui/main_window.py`、`models.py`：确认当前 UI 是否已有单/多 profile 结构、绑定编辑入口和状态刷新路径。
- `virtual_gamepad/ui/tests/`：确认既有测试覆盖，避免破坏用户当前修改。

**本轮要澄清：** 两个输入源是“两个独立物理手柄设备”还是“同一设备的两个逻辑通道”；两个界面应分别编辑 source A/source B，最终由一个合并层生成虚拟输出；同一目标按键允许多 source 同时绑定，并明确按下/释放引用计数规则。

## [P4 OCR provider adapter discovery] 2026-09-04

### A. Scope declaration
**Goal files:** `core/perception/providers/contracts.py`, `core/perception/algorithms/template_adapter.py`, `core/perception/builtins.py`, `core/perception/engine.py`, and focused perception tests.
**Question:** define a provider-backed OCR adapter that turns raw `OcrSpan` evidence into target-level `TargetDetection` while keeping provider objects out of profile JSON and retaining the provider-free registry boundary.
**Boundary:** this slice must not add an OCR engine, GUI path, screen capture, coordinate mapping, workflow call, or game-specific target rule.

### C. Findings
**Verified:** `OcrProvider.recognize(frame, parameters)` returns raw `OcrSpan` values that already carry text, bounding box, coordinate space, confidence, language, and raw metadata, while carrying no target semantics. `ProviderBackedTemplateDetector` establishes the correct precedent: validate the provider boundary and delegate/normalize without moving provider objects into profiles.
**Design decision:** `ProviderBackedOcrDetector` will execute the injected provider for each frame, require `OcrSpan` output, apply a configurable generic text predicate (`exact`, `contains`, or `regex`) and minimum OCR confidence, then produce one `TargetDetection` per matching span. It will preserve the span's geometry and coordinate space, place raw details in evidence, and allow provider/configuration errors to reach `DetectorRunner`'s existing per-instance isolation.
**Compatibility:** the default OCR descriptor stays discoverable but unavailable because no OCR backend is bundled. A runtime `PerceptionEngine.algorithm_factories["ocr"]` closure may make it executable without serializing provider objects or adding a mandatory OCR dependency.
**Next task:** document the adapter contract, create one red contract test, then implement the smallest adapter/factory/export slice.

### C. Slice 1 red result
**Failure evidence:** `tests.test_perception_ocr_adapter` fails at import time with `ModuleNotFoundError: core.perception.algorithms.ocr_adapter`, as expected. The test locks the first public behavior: one injected provider call per frame; exact case-insensitive query matching; confidence filtering; and geometry, timing, text, language, metadata, source, and target-type preservation in `TargetDetection`.
**Next task:** add only `ProviderBackedOcrDetector` to satisfy the first contract; do not change the algorithm registry, GUI, providers, engine, or profile model in this green step.

## [SYNC] 2026-09-04 - OCR provider adapter

### A. SYNC scope declaration
**Trigger:** P4 adds a provider-backed OCR algorithm adapter, its runtime factory, public algorithm export, editable descriptor parameters, focused tests, and design record.
**Directly changed files:** `core/perception/algorithms/ocr_adapter.py`, `core/perception/algorithms/__init__.py`, `core/perception/builtins.py`, `tests/test_perception_ocr_adapter.py`, and `docs/plans/2026-09-04-ocr-provider-adapter-design.md`.
**Dependency review:** `providers/contracts.py` remains the raw OcrSpan boundary; `PerceptionEngine` and `DetectorRunner` reuse their existing runtime-factory override seam; GUI, profile serialization, spatial mapping, capture, input, navigation, and workflows remain unaffected.

### C. SYNC result
**Implemented behavior:** `ProviderBackedOcrDetector` calls an explicit OCR provider once per frame, requires `OcrSpan` evidence, filters configured exact/contains/regex matches and confidence, preserves each selected span's geometry/coordinate space/text/timestamp, ranks candidates by confidence, and emits standard `TargetDetection` values. No bundled OCR engine, GUI route, or action behavior was added.
**Composition and compatibility:** `create_ocr_detector()` requires an explicit provider; the existing `PerceptionEngine.algorithm_factories` closure seam enables it while default registry OCR remains discoverable/unavailable. Existing color/template factory behavior, templates, profiles, providers, and pipeline APIs are unchanged.
**Verification:** 10/10 OCR adapter tests passed; 42/42 focused provider/template/OCR/algorithm/engine/stage/pipeline tests passed; `compileall -q core/perception` passed.
**CODEBASE.md synchronized:** updated C4 call path, OCR adapter/module/public-surface/factory/engine details, risk statement, and OCR regression contract. `docs/PERCEPTION_ENGINE_CHECKPOINT.md` records the completed OCR slice; the next P4 candidates are shape, feature, and motion adapters.
**Coverage update:** `core/perception/algorithms/ocr_adapter.py` and `tests/test_perception_ocr_adapter.py` are deeply read and documented; `algorithms/__init__.py`, `builtins.py`, engine/runner/provider contracts, and prior template adapter were re-read for dependency impact.

## [P4 shape adapter discovery] 2026-09-04

### A. Scope declaration
**Goal files:** `core/perception/algorithms/shape.py`, `core/perception/builtins.py`, `core/perception/algorithms/__init__.py`, and focused perception tests.
**Question:** add a deterministic OpenCV contour/geometry detector that accepts reusable shape parameters and emits `TargetDetection` without requiring a resource provider, ML model, game target name, GUI, coordinate mapper, or action layer.
**Boundary:** shape evidence derives only from the supplied `FrameContext`; it must not access desktop capture, templates, OCR, input, navigation, legacy minimap code, or workflows.

## [P4 fast OCR provider discovery] 2026-09-04

### A. Scope declaration
**User request:** select and implement a fast local OCR core that locates recognized text in an image, then test the provider-to-`OcrSpan` and adapter-to-`TargetDetection` paths.
**Read targets:** installed Python/ONNX/OCR capabilities, project dependency policy, `OcrProvider` contract, provider registry/catalog, and existing OCR adapter tests.
**Boundary:** the concrete backend must remain optional and lazily imported; importing `core.perception` must not download a model, initialize OCR, access a screen, or make Paddle/Tesseract/ONNX mandatory for unrelated users.

### C. Findings
**Verified:** generic perception has no shape implementation. Existing Portal/Loot contour routines are target-specific compatibility code and must remain untouched. Current dependencies already include OpenCV/NumPy, and `ColorRegionDetector` establishes the normalized contour-to-`TargetDetection` output pattern.
**Design decision:** create a provider-free `ShapeDetector` based on a thresholded grayscale frame, optional morphology, external contours, polygon approximation, and generic area/vertex/circularity/solidity filters. It will report bounded geometry metrics as evidence and rank surviving candidates by fill/solidity quality. The descriptor will be available because no optional backend is required.
**Next task:** document the behavior and add an isolated red test for circle/rectangle contour filtering before registering the detector or altering the existing unavailable `shape` descriptor.
## [SYNC] 2026-09-04 — RapidOCR 实际文字定位 Provider

### A. SYNC 范围声明

**触发任务：** 为通用感知引擎接入可选、延迟加载的 RapidOCR 后端，使整屏或 ROI 图像中的文字可输出统一位置标注；补足单元与真实后端冒烟测试。

**直接变更文件：** `core/perception/providers/rapidocr.py`、provider 导出/注册文件、`tests/test_perception_rapidocr_provider.py`、可选 OCR 依赖清单，以及对应设计、断点和代码库索引文档。

**预计连带影响：** `FrameContext -> OcrProvider -> OcrSpan -> ProviderBackedOcrDetector -> TargetDetection` 感知链；不修改输入、GUI、坐标映射和游戏工作流。
### C. SYNC 结果

**连带重读文件：** `core/perception/providers/contracts.py`、`core/perception/providers/__init__.py`、`core/perception/providers/builtins.py`、`core/perception/algorithms/ocr_adapter.py`、`core/perception/builtins.py`、`core/perception/engine.py`、现有 provider/OCR 相关测试与断点文档。

**实现结果：** 新增可选 `RapidOcrProvider`。它在第一次识别时才导入并创建 RapidOCR ONNX 模型，后续帧复用同一个引擎；将文字四边形转换为统一 `OcrSpan` bbox；支持全屏与可配置 ROI，并把 ROI 局部坐标恢复为原 `FrameContext.coordinate_space`。`ProviderBackedOcrDetector`、融合、确认、选择、坐标映射、GUI 与工作流边界保持不变。

**参数与性能结论：** profile 的 `provider_parameters` 可传 `roi`、语言结果标签和 RapidOCR `backend_options`；底层 `engine_options` 支持线程等模型初始化设置且只在首次构建时读取。当前机器生成的 900×260 英文图基准中，默认 warm inference 约 3.09s，`intra_op_num_threads=4`/`inter_op_num_threads=1` 约 0.72s；这是本机基准，实际游戏应结合 ROI 与 metadata 的 `elapsed_seconds` 调参。

**验证：** 红测试先按预期报 `ModuleNotFoundError: core.perception.providers.rapidocr`；实现后 RapidOCR 专项 6/6 通过，provider/catalog 联测 12/12 通过，完整 perception 测试集 68/68 通过，`compileall -q core/perception`、公共导入 smoke 与真实 ONNX 文本定位基准通过。真实结果识别出 `ENTER MAP`，bbox 为 `(72.0, 66.0, 549.0, 105.0)`。

**CODEBASE.md 同步：** 更新 C4 OCR 调用路径、provider 文件职责与导出、默认 catalog、RapidOCR 全部函数索引、完整数据流、外部集成/错误边界、数据契约、风险条目和回归测试索引；新增设计文档 `docs/plans/2026-09-04-rapidocr-provider-design.md`。

**下一步：** P4 仍待实现 feature 与 motion adapter；随后 P5 将标准 `TargetDetection` 接入运行时坐标映射和校准，P6 才让 GUI workbench 显式选择/配置该 provider。不要在这之前把流放之路特定 OCR 文本、点击或场景规则写进 `RapidOcrProvider`。
## [2026-09-04] OCR model resource switching

### A. This-round scope declaration (before reading)

**Goal:** Turn the verified Traditional-Chinese-capable RapidOCR recognition model into a generic, explicit model resource: a named manifest entry, verified local resolution, and a separate installer. Keep the existing `RapidOcrProvider` API and its unified `OcrSpan` / `TargetDetection` output intact.

**Planned target files:**

- `core/perception/providers/rapidocr_models.py` — model manifest and local-path/checksum resolver.
- `core/perception/providers/rapidocr.py` — inspect only to preserve provider compatibility; alter only if a small integration seam is necessary.
- `core/perception/providers/__init__.py` — public exports, if that is the project convention.
- `utils/install_perception_ocr_model.py` — explicit, atomic downloader and verifier.
- `tests/test_perception_rapidocr_models.py` — offline resolver and installer tests.
- `tests/test_perception_rapidocr_provider.py` — inspect existing OCR integration contract and add a local optional Traditional-Chinese smoke test only if it fits.
- `requirements-ocr.txt`, `.gitignore`, `CODEBASE.md`, `docs/PERCEPTION_ENGINE_CHECKPOINT.md`, and a focused design note — inspect/update only where the new resource contract requires it.

**Questions to answer:**

1. How is the current RapidOCR provider constructed and injected without import-time OCR dependencies?
2. What public configuration seam can select an installed model without binding to a game, scene, or target word?
3. Which test conventions and documentation sections must be updated to keep the perception architecture truthful?
### C. Findings after first focused read

**Key findings (verified):**

- `RapidOcrProvider` delays importing `rapidocr_onnxruntime` and constructing `RapidOCR` until its first `recognize` call. Its constructor already accepts a copied `engine_options` mapping, so a model resolver can return `rec_model_path` without changing frame recognition, ROI coordinate restoration, or unified `OcrSpan` output.
- `ProviderBackedOcrDetector` is exercised by the provider test and continues to consume only provider output. Model selection therefore belongs outside the detector and outside every game workflow.
- Provider-package public exports are explicit in `core/perception/providers/__init__.py`; the resolver should be exported there after implementation.
- The real RapidOCR test is optional and its default model only recognizes an ASCII image. A Traditional-Chinese smoke test must also remain optional and only run when the explicitly installed external model file exists.
- The worktree contains unrelated active `virtual_gamepad` and event changes. This OCR model-resource change will stage only its own exact files.

**Corrected prior conclusion:** Passing `rec_model_path` directly is enough for a one-off experiment, but it does not make a reusable model safely selectable. A manifest plus an explicit checksum-verified local resolver is needed so profiles/configuration can name a stable model ID rather than depend on an opaque local path.

**Next focused read:** inspect the existing OCR requirement, ignore rules, tests/helpers, and perception documentation to set installer location, asset exclusion, error conventions, and CODEBASE documentation scope before adding code.
### C. Findings after resource/documentation read

**Key findings (verified):**

- `requirements-ocr.txt` intentionally isolates `rapidocr-onnxruntime==1.4.4`; the new model registry must not add an automatic dependency or change base requirements.
- `.gitignore` has no perception-model asset rule. The installer destination must be ignored so downloaded ONNX binaries cannot be accidentally staged.
- The perception checkpoint defines an explicit provider/adapter boundary and P4 is still in progress. A model spec is provider composition data: it may produce backend options, but must not perform text matching, screen capture, coordinate mapping, or actions.
- The existing RapidOCR design already treats model initialization as a composition-time decision through `RapidOcrProvider(engine_options=...)`. The missing piece is a stable model ID, asset integrity validation, and operator-facing installation path.
- `CODEBASE.md` has an existing RapidOCR provider description and provider-test entry; it needs a targeted SYNC addition for the model manifest and installer after code changes, not a broad rewrite.

**Corrected prior conclusion:** A `language` value in per-call `provider_parameters` is only a result label. It does not select OCR recognition language or swap the loaded ONNX model; model selection must be supplied through the provider's construction options.

**Next focused read:** inspect utility CLI patterns and perception exception/testing conventions, then write a red offline contract test before the model manifest and installer implementation.
### C. Utility discovery update

**Key finding (verified):** The repository has no tracked `utils/` installer convention. Perception provider tests are all standard `unittest` modules under `tests/`, so the new installer will use a small standard-library CLI at `utils/install_perception_ocr_model.py` and its test will import the function-level implementation directly rather than spawn a process or access the network.

**Next action:** create offline red tests covering named model lookup, absent/corrupt assets, immutable engine option construction, and a downloader's temporary-file/atomic-replace behavior using a local fake URL opener.
### C. Installer CLI debugging record

**Reproduction (verified):** Running `python utils/install_perception_ocr_model.py --help` from the repository root exits with `ModuleNotFoundError: No module named 'core'`. The new direct-execution regression test reproduces the same failure.

**Pattern analysis (verified):** Existing executable utilities such as `utils/route_context_probe.py`, `utils/portal_screen_probe.py`, and `utils/input_probe.py` resolve the repository root from `__file__` and add it to `sys.path` before importing `core`.

**Hypothesis:** The installer needs the same project-root bootstrap before its `core.perception` imports. This is the only difference between it and working utility CLIs; adding that bootstrap will make direct invocation work without changing its package-import behavior.

**Next action:** apply that one bootstrap, rerun the isolated CLI test, then retry the explicit model installation.
## [SYNC] 2026-09-04  — Traditional-Chinese RapidOCR model resource

### A. SYNC scope declaration

**Triggering implementation:** Add a named PP-OCRv6 multilingual small model resource, integrity resolver, explicit atomic installer, public exports, and Traditional-Chinese position regression coverage.

**Directly changed source/test files:**

- `core/perception/providers/rapidocr_models.py`
- `core/perception/providers/__init__.py`
- `utils/install_perception_ocr_model.py`
- `tests/test_perception_rapidocr_models.py`
- `tests/test_perception_rapidocr_provider.py`

**Associated non-source updates:** `.gitignore`, `docs/PERCEPTION_ENGINE_CHECKPOINT.md`, `docs/plans/2026-09-04-rapidocr-multilingual-model-resource-design.md`, and `CODEBASE.md`.

**Impact analysis to confirm:** The resolver must remain a composition-only resource layer; `RapidOcrProvider`, `ProviderBackedOcrDetector`, profile JSON, GUI, coordinate mapping, and workflows must retain their existing boundaries. The new CLI must be executable both directly and as imported test code.
### C. SYNC result

**Coupled files reread:** `core/perception/providers/rapidocr_models.py`, `core/perception/providers/__init__.py`, `utils/install_perception_ocr_model.py`, `tests/test_perception_rapidocr_models.py`, and `tests/test_perception_rapidocr_provider.py`.

**Boundary verification (verified):**

- The named model catalog performs only metadata lookup, local SHA-256 checking, and defensive engine-option construction. It has no RapidOCR import, model download, OCR inference, target text, screen capture, GUI, coordinate mapping, or input dependency.
- `RapidOcrProvider` was not changed: it still owns lazy engine construction and emits raw `OcrSpan`; the existing OCR adapter remains the only component that applies a text predicate and converts provider evidence into `TargetDetection`.
- Provider composition remains runtime-only. Target profiles still need no model object and no raw model path; `rec_model_path` cannot be smuggled through resolver overrides.
- The downloader is explicit and direct-executable. It verifies a temporary same-directory file before `os.replace()`, and tests show that a corrupt replacement leaves an old final asset untouched.

**Verification:**

- `D:\ACloud\.venv\Scripts\python.exe -m unittest discover -s tests -p 'test_perception*.py'` — 76 passed.
- Real installed-model smoke test — passed: `開始儀式` and `進入異界地圖` were each recognized with original-image bounding boxes.
- `compileall -q core/perception utils/install_perception_ocr_model.py tests/test_perception_rapidocr_models.py tests/test_perception_rapidocr_provider.py` — passed.
- Public import smoke test — passed.
- Re-running the explicit installer against its verified local asset — passed without a re-download.
- `git diff --check` — passed; existing repository LF/CRLF warnings remain non-errors.

**CODEBASE.md synchronized:** provider public surface, new model-resource module, installer behavior, optional OCR integration flow, regression contracts, and the model-resolution latency risk are updated. `docs/PERCEPTION_ENGINE_CHECKPOINT.md` and the focused design record the handoff point.

**Next task:** wire the named provider/model selection into the P6 perception workbench/application-composition UI, keeping profiles serializable and model resources outside game workflows.
## [SYNC] 2026-09-04 — staged whitespace correction

### A. SYNC scope declaration

**Triggering change:** Remove one trailing blank line at EOF in `core/perception/providers/rapidocr_models.py` after staged `git diff --check` identified it.

**Impact assessment:** Formatting-only change; no signature, algorithm, runtime dependency, API, profile, provider, or flow behavior changes. Existing model-resource CODEBASE entries remain accurate.

### C. SYNC result

The EOF whitespace was removed, the model-resource source was re-staged, and the staged diff check is rerun before commit. No CODEBASE.md semantic update is needed for this formatting-only correction.
## [2026-09-04] Desktop OCR-to-action mapping proof

### A. This-round scope declaration (before reading)

**Goal:** Prove the new generic architecture across a real desktop action without adding game rules: capture the current desktop, find the literal target text `梦之形` through the existing OCR provider, map capture coordinates to physical screen coordinates, then drive a deliberately small mouse double-click action adapter. The proof must report every coordinate and mapping decision so accuracy can be checked.

**Planned target files:**

- Existing capture, coordinate, and input modules — inspect their current coordinate contracts and safe action seams before reuse.
- `core/spatial/` — extend only with a general source-frame-to-screen mapper if the existing calibration primitives cannot represent it.
- `core/perception/providers/` and OCR adapter — inspect only; recognition remains independent of this desktop proof.
- A new generic action package/module — no target word or desktop behavior inside it; it receives a mapped point plus an action request.
- A small desktop demonstration workflow/script and focused tests — compose capture, recognition, mapping, and action with the target `梦之形` only as demonstration configuration.
- `docs/`, `CODEBASE.md`, and this checkpoint log — record schema, safety behavior, and verification.

**Questions to answer:**

1. Which existing screen capture path exposes physical-pixel dimensions and how does it relate to Windows DPI?
2. Does the existing spatial model already represent an identity/affine capture-to-screen mapping, or is a minimal independent mapping DTO needed?
3. Which existing mouse backend can issue a correctly scoped double click without embedding action policy into perception or spatial modules?
4. How can the proof avoid acting if OCR finds zero, several ambiguous, or out-of-screen candidates?
### C. Capture/input boundary findings

**Key findings (verified):**

- `SquareScreenCapture.capture(x, y, width, height)` already documents physical-pixel input coordinates and returns BGR NumPy images. It provides a usable capture primitive but does not attach a `FrameContext`, a desktop rectangle, DPI evidence, or source-to-destination transform metadata.
- `core.spatial.models` currently supplies immutable points, anchor pairs, and a positive `WindowRect`, but no result object that says a detected source point has been mapped to a physical screen coordinate.
- `InputDriver` already has Win32 `GetSystemMetrics`, absolute `SetCursorPos`, `mouse_down`, `mouse_up`, and safe diagnostic helpers. Its existing `click()` is a device implementation detail, not an action contract; it should be wrapped instead of importing perception data into it.
- `screen_bounds.clamp_screen_pos()` is legacy tuple clamping. It should not silently correct a test pipeline point, because silently clamping would hide a bad mapping. The new mapper must reject out-of-bounds results explicitly.

**Corrected prior assumption:** The capture backend's comments say physical pixels, but that fact is not yet represented in the shared schema. The proof needs a `ScreenGeometry` provider/DTO that names the physical destination rectangle and DPI observation, rather than assuming `FULL_SCREEN` always means identity mapping.

**Next focused read:** inspect the existing affine calibration implementation and click execution composition, then choose the narrowest extension compatible with them.
### C. Calibration-model finding

**Key finding (verified):** `core.spatial.calibration.CoordinateMapper` already owns the right generic abstraction: transforms are explicitly keyed by `CoordinateSpace`, identity mapping is explicit when spaces match, and its `AffineTransform` supports source-to-target point conversion. The desktop proof should build on this module rather than introduce a parallel mapping engine.

**Required extension (inferred):** preserve `CoordinateMapper` as an unconcerned transform registry, then add a small desktop-facing mapper/geometry layer that derives a scale/translation transform from one captured frame and a current physical desktop rectangle, validates the mapped point against that rectangle, and returns diagnostic evidence. This avoids changing `CoordinateSpace` enum meanings before multi-display/window support is designed.

**Next focused read:** inspect the current click executor and input controller construction so the new device-agnostic action adapter wraps existing Win32 behavior rather than duplicating it.
### C. Action-adapter boundary findings

**Key findings (verified):**

- Existing `click_pipeline.execute_click()` is specifically coupled to movement navigation: it applies a bottom guard, optional clamping/focus behavior, and a `MotionController` diagnostics structure. Reusing it would incorrectly add navigation policy to a generic visual action proof.
- `click_executor.send_click()` is also a single-click implementation with fallback and optional confirm-click semantics. It is useful as backend reference but not the generic double-click action contract required here.
- `InputDriver` is the narrow reusable platform primitive. A new action adapter can depend on a minimal mouse protocol (`move_to`, `mouse_down`, `mouse_up`, optional `cursor_pos`) and produce a generic result without importing controller, perception, or navigation code.

**Architecture decision:** create a new `core/actions/` package for device-agnostic action DTOs plus a mouse adapter. Keep `core/input/` intact as a legacy/navigation implementation. The desktop proof will use an injected mouse adapter, so tests never touch the real cursor and a later controller/gamepad adapter can implement the same action request boundary.

**Next action:** write the approved TDD implementation plan with exact files and verification commands, then implement only that plan.
### C. Coordinate-space contract correction

**Key finding (verified):** `FrameContext` does not infer width/height from an image; a frame source must populate both explicitly. `TargetDetection` already carries a two-number center plus `CoordinateSpace`, while the shared enum has `FULL_SCREEN` but no way to distinguish a screenshot's image-pixel plane from the physical desktop input plane.

**Corrected architecture decision:** add `CoordinateSpace.PHYSICAL_SCREEN` as an additive, non-breaking destination space. A `FrameContext` captured from the desktop remains `FULL_SCREEN`; `DesktopCoordinateMapper` emits `PHYSICAL_SCREEN`. This makes it impossible for the generic mouse adapter to accidentally accept an unmapped screenshot point, while leaving all old `FULL_SCREEN` callers unchanged.

**Next action:** start the first TDD tracer bullet for `DesktopCoordinateMapper`: a source-frame center maps through an offset/scale desktop geometry to a physical-screen point with diagnostic evidence.
### C. Spatial/action tracer-bullet result

**Completed and verified:**

- `CoordinateSpace.PHYSICAL_SCREEN` now separates a captured `FULL_SCREEN` image plane from an input-injection destination without altering legacy coordinate values.
- `DesktopCoordinateMapper` uses the existing `AffineTransform` to derive an offset/scale mapping and produces immutable `MappedPoint` diagnostics. It rejects unknown spaces, source out-of-bounds points, and destination out-of-bounds results instead of silently clamping.
- `DesktopFrameSource` accepts injectable geometry and capture providers, produces a dimensioned `FrameContext(FULL_SCREEN)`, and has a Windows default that observes virtual desktop bounds with best-effort process DPI awareness. The test did not invoke the Windows backend.
- The new `core.actions` boundary accepts only a `MappedPoint(PHYSICAL_SCREEN)` and a generic `ActionRequest`; its fake-device test proves exact move/double-click ordering with no perception imports or real input.

**Verification:** 3 focused tests pass. No real capture, OCR, cursor move, click, or desktop state change has occurred.

**Next focused read:** locate workflow package conventions, then add an injected OCR-provider composition test that proves a unique text result maps to a dry-run report while ambiguous results produce no action request.
### C. Real desktop proof result

**Live verification (verified):**

- The real desktop capture reported `2560 × 1600`; the Win32 virtual desktop geometry reported the same physical rectangle and a DPI observation of `1.5 × 1.5`.
- The explicitly composed PP-OCRv6 provider found one exact `梦之形` label with `0.999948779741923` confidence. Its source center was `(633.5483703613281, 532.0513000488281)` and the mapper emitted the same physical-screen point because the capture and destination dimensions matched.
- The action adapter rounded only at the input boundary to `(634, 532)`, moved once, and sent exactly two left-button down/up pairs with a 100ms inter-click delay. Its report status was `executed`.
- A separate, read-only Win32 foreground-window query afterward found an `SDL_app` window, consistent with the requested desktop shortcut having opened. That independent diagnostic process was DPI-unaware and read cursor `(423, 355)` / metrics `1707 × 1067`; those are the physical result divided by 1.5, confirming why the capture/input host must establish DPI awareness before it creates its mouse backend.

**Corrected implementation constraint:** Physical coordinate agreement is process-level, not merely a mapper formula. The desktop proof is correct because `DesktopFrameSource()` establishes DPI awareness before `InputDriver()` is created in `build_live_proof()`. Future composition must retain this startup order or centralize the awareness bootstrap; legacy input behavior must not be silently changed in this slice.

**Next task:** run broader automated checks, make the CLI's diagnostic JSON encoding unambiguous on legacy Windows consoles, synchronize architecture documents, and create a narrowly scoped commit without staging unrelated virtual-gamepad/event work.
## [SYNC] 2026-09-04 — desktop OCR / mapping / mouse proof

### A. SYNC scope declaration

**Triggering implementation:** Add an explicit physical-screen coordinate space, pure desktop coordinate mapper, live desktop frame source, device-neutral mapped-point action DTOs, mouse double-click adapter, and a thin OCR proof workflow/CLI.

**Directly changed source files:**

- `core/perception/models.py`
- `core/spatial/desktop_mapping.py`, `core/spatial/__init__.py`
- `core/platform/desktop_frame_source.py`, `core/platform/__init__.py`
- `core/actions/models.py`, `core/actions/mouse.py`, `core/actions/__init__.py`
- `workflows/__init__.py`, `workflows/desktop_ocr_action_proof.py`
- `utils/run_desktop_ocr_action_proof.py`

**Directly changed tests/docs:** desktop mapper/frame/action/workflow tests and the design/implementation-plan documents.

**Impact expansion checked:** OCR provider and adapter remain unchanged; `CoordinateSpace` grows one additive destination value; legacy `core/input` navigation pipeline is not redirected; the new workflow creates the only link between perception, spatial mapping, and mouse action. Windows DPI awareness is process-scoped and therefore documented as composition order, not hidden as a change to legacy input behavior.
### C. SYNC spatial mapping read

**Verified implementation detail:** `DesktopCoordinateMapper` is a pure scale-plus-translation specialization of the existing `AffineTransform`; it computes independent x/y scales from a captured image extent and physical `ScreenGeometry`, requires the source to be `FULL_SCREEN`, uses half-open bounds in both planes, then emits a mapping-proof `MappedPoint(PHYSICAL_SCREEN)`. `ScreenGeometry` and `MappedPoint` defensively validate numbers/spaces and freeze diagnostics, so later action adapters cannot mutate transform evidence.

**CODEBASE.md update required:** add the new spatial file, model contracts, mapping algorithm, and a capture→OCR→mapping→action flow description.
### C. SYNC capture/action/workflow read

**Verified implementation detail:**

- `WindowsDesktopGeometryProvider` establishes best-effort per-monitor DPI awareness during construction, reads virtual-screen metrics, and reports a DPI observation; `DesktopFrameSource` passes exactly that rectangle to the existing capture backend, validates the resulting image shape, and writes source dimensions plus physical-geometry metadata into `FrameContext`.
- `ActionRequest` is restricted to generic action kind, mapped point, and timing. `MouseActionAdapter` accepts only `PHYSICAL_SCREEN`, rounds once at the device boundary, moves exactly once, then produces zero or two click pairs. It has no capture, OCR, selection, clamping, or window-focus policy.
- `DesktopOcrActionProof` is the single thin composition layer: it builds the existing provider-backed exact OCR detector, requires exactly one qualified candidate, maps the candidate center, and calls its injected adapter only under `execute=True`. Its report exposes all safety outcomes without mutating profiles or core providers.

**CODEBASE.md update required:** add platform/actions/workflow module entries, exact action/mapping/capture algorithms, external Win32/MSS integration constraints, full proof flow, and the DPI startup-order risk.
### C. SYNC result

**Coupled files reread:** `core/spatial/desktop_mapping.py`, `core/platform/desktop_frame_source.py`, `core/actions/models.py`, `core/actions/mouse.py`, and `workflows/desktop_ocr_action_proof.py`; existing capture, input, affine calibration, and OCR adapter seams were also compared before composition.

**Verification:**

- `D:\ACloud\.venv\Scripts\python.exe -m unittest discover -s tests -p 'test_perception*.py'` — 76 passed.
- New desktop mapper/frame/action/workflow regression suite — 5 passed.
- `compileall` for action, perception, platform, spatial, workflow and proof CLI modules — passed.
- Public import smoke check — passed.
- Real desktop dry-run after all code changes — passed: one exact `梦之形` detection at `(633.55, 532.05)`, `2560×1600` source/physical dimensions, identity physical mapping, and no action.
- One user-authorized real action run — passed: one move to `(634, 532)` plus exactly one double click; follow-up read-only window diagnostic found the opened SDL application.
- `git diff --check` — passed; existing repository LF/CRLF warnings are non-errors.

**CODEBASE.md synchronized:** added directory entries, spatial/capture/action/workflow/CLI contracts, complete desktop proof data flow, the external Win32/MSS/DPI integration behavior, and two concrete risks. `docs/PERCEPTION_ENGINE_CHECKPOINT.md` now marks P5 in progress with the completed desktop proof slice.

**Next task:** retain this proof as the P5 baseline, then extend mapping to specific game windows/viewports, runtime anchor calibration, and UI calibration preview; feature/motion recognition adapters remain independent P4 work.
## [2026-09-04] Cross-process input-work review

### A. This-round scope declaration (before reading)

**Goal:** Read the other active process's uncommitted input/virtual-gamepad work without editing it. Establish which behavior it implements, its public boundaries, and whether it overlaps with or can later become an adapter beneath the newly committed generic `core.actions` contract.

**Read-only target files:**

- `virtual_gamepad/` changed source, configuration, UI, host, tests, and documentation files as identified by Git.
- `core/events/window_finder.py` and `core/events/tests/` only to distinguish its related work from the perception/spatial/action mainline.
- Current Git status and diff summaries to identify ownership boundaries before any detailed file read.

**Questions to answer:**

1. Does the other process implement physical/virtual controller routing, mapping profiles, or an independent action abstraction?
2. Does it change the generic perception/spatial/action pipeline or only its own virtual-gamepad subsystem?
3. What future integration seam would allow a `GamepadActionAdapter` to consume `core.actions` requests without merging the subsystems prematurely?
### C. Cross-process first-read findings

**Key findings (verified):**

- The other process's design explicitly treats `virtual_gamepad/host` as a privileged, independent runtime and treats programmatic control as a Python named-pipe client. It proposes a future `core.actions.VirtualGamepadActionAdapter`, but the reviewed `virtual_gamepad_client.py` currently exposes raw controller operations (`button`, `set_axis`, `set_trigger`, `set_state`, `reset`, `pause`, `heartbeat`) rather than importing or implementing the newly committed `core.actions` contract.
- It supports two independently addressable controller slots (`controller=1|2`), per-call `source`, and optional TTL. That is a strong lower-level transport substrate for a future gamepad action adapter: workflow code should not call it directly once an adapter exists.
- The scope is not merely UI: it includes two ViGEm targets, shared physical input forwarding, controller-specific F7/F8 pause controls, global F9 reset, multiple named-pipe clients, profile editing, and host lifecycle/elevation safety.
- The other process currently has no tracked modifications under `core/perception`, `core/spatial`, or `core/actions`; direct code overlap with the generic OCR/mapping/mouse proof is therefore absent.

**Corrected prior description:** Saying the other task was simply “unrelated virtual gamepad work” was too coarse. It is separate in implementation ownership, but it is a future concrete input backend for the main automation architecture. It should remain isolated until its host/client contract and safety tests are stable, then be connected through one `GamepadActionAdapter` in `core.actions`—not through perception, spatial mapping, or workflow-specific named-pipe calls.

**Next focused read:** inspect the C# controller registry and mapping runtime to confirm slot/source/TTL ownership, and inspect host composition for the concurrent-client and lifecycle seam proposed by its design.
## [Review continuation] 2026-09-04

### A. Scope declaration (before source review)

**Task:** Read-only review of the concurrent `virtual_gamepad` implementation before deciding how it can connect to the reusable action layer.

**Files selected for this pass:**
- `virtual_gamepad/host/src/VirtualGamepadHost/Protocol/CommandRouter.cs` — establish command routing, validation, and controller targeting.
- `virtual_gamepad/host/src/VirtualGamepadHost/Protocol/NamedPipeServer.cs` — verify multi-client named-pipe behavior and shutdown/error handling.
- `virtual_gamepad/host/src/VirtualGamepadHost/State/SafetyController.cs` — establish TTL, reset, and fail-safe semantics.
- `virtual_gamepad/host/src/VirtualGamepadHost/Runtime/ControllerSlot.cs` — establish per-slot ownership and lifecycle boundaries.

**Questions to resolve:** whether simultaneous UI and automation clients are safely supported; how input sources collide or expire; whether controller-specific and global reset paths are sound; and the correct future adapter boundary under `core/actions`.
### C. Findings — command-routing pass

**Verified:** `CommandRouter.Handle()` dispatches every command through a selected `ControllerSlot`; omitted `controller` defaults to slot `1`, while `emergency_reset` intentionally reaches `ControllerRegistry.EmergencyResetAll()`.

**Verified:** raw actuator commands (`button`, `set_axis`, `set_trigger`, `set_state`, `heartbeat`) deserialize a `source` plus optional positive `ttl_ms`, pass their values to the selected slot's `StateStore`, and return the resolved controller number. Invalid payloads, values, and unsupported types are converted to protocol failures rather than escaping the pipe handler.

**Verified:** `start` alone checks virtual-device readiness; direct input-setting commands do not check that the slot is running or device-ready. The runtime/state classes remain the required next read to determine whether this is harmless queued state or a safety gap.

**Architecture conclusion:** this routing layer is a device-backend protocol boundary. A later `core.actions.VirtualGamepadActionAdapter` may call it through the Python named-pipe client, but perception, spatial mapping, and workflows must not call it directly.

**Coverage:** `CommandRouter.cs` — deeply reviewed for dispatch, validation, controller selection, and failure mapping; state mutation conflict/expiry behavior remains delegated to `StateStore` and `SafetyController`.

**Next pass:** read named-pipe connection lifetime plus per-slot safety/state classes, then verify concurrent clients, source collision policy, TTL expiry, and shutdown.
## [Review continuation] 2026-09-04 — transport and safety

### A. Scope declaration (before source review)

**Files selected for this pass:**
- `virtual_gamepad/host/src/VirtualGamepadHost/Protocol/NamedPipeServer.cs` — pipe connection concurrency, read/write ownership, cancellation, shutdown.
- `virtual_gamepad/host/src/VirtualGamepadHost/State/SafetyController.cs` — controller lifecycle and reset actions.
- `virtual_gamepad/host/src/VirtualGamepadHost/Runtime/ControllerSlot.cs` — per-controller state object composition.

**Questions:** can a UI status connection coexist with automation commands, and do lifecycle/reset semantics safely clear device state for each controller?
### C. Findings — transport and safety pass

**Verified:** `NamedPipeServer.RunAsync()` creates a new `NamedPipeServerStream` with `MaxAllowedServerInstances`, detaches each accepted connection to `ServeClientAsync()`, and resumes accepting immediately. A status/UI client and an automation client can therefore be live at the same time; each connection has its own sequential JSON-lines reader/writer loop.

**Verified:** host cancellation is shared with the listener and every client handler. Listener shutdown waits for the tracked client tasks and each handler disposes its own pipe stream; ordinary client disconnects are swallowed without terminating the host.

**Verified:** each `ControllerSlot` owns a separate `StateStore`, `SafetyController`, and `MappingEngine`. `SafetyController` is per-slot locked: `Pause`, `EmergencyReset`, and `Fail` clear/disable state; ordinary `Reset` preserves a pre-existing paused state; `Start` resumes the store.

**Important remaining uncertainty:** simultaneous messages are routed concurrently once they arrive on different pipe connections. Whether writes to the same controller/source are serialized and how expired values are removed depends on `StateStore`, which has not yet been reviewed. The current code permits mutation commands even before a slot is `Running`; backend submission behavior still needs confirmation.

**Coverage:** `NamedPipeServer.cs` — deeply reviewed for client lifecycle; `SafetyController.cs` — deeply reviewed for lifecycle transitions; `ControllerSlot.cs` — fully reviewed (record composition).

**Next pass:** read `StateStore` and registry/backend tick behavior, then validate source arbitration, expiration, inactive-slot output, and reset propagation.
## [Review continuation] 2026-09-04 — source state and output fan-out

### A. Scope declaration (before source review)

**Files selected for this pass:**
- `virtual_gamepad/host/src/VirtualGamepadHost/State/StateStore.cs` — source merge, TTL expiration, thread safety, and snapshot semantics.
- `virtual_gamepad/host/src/VirtualGamepadHost/Runtime/ControllerRegistry.cs` — two-slot creation, backend update loop, per-slot/global reset.
- `virtual_gamepad/host/src/VirtualGamepadHost/Runtime/HostComposition.cs` — physical-input broadcast and host-wide lifecycle wiring.

**Questions:** how two clients or mappings combine their input, whether an inactive controller can emit a stale state, and whether reset/pause reaches all concrete virtual devices.
### C. Findings — source state and output fan-out

**Verified:** `StateStore` serializes all source access behind one lock. It merges buttons by OR, triggers by maximum, and each axis by greatest absolute magnitude (then most-recent sequence on ties). Incremental actuator commands expire after an explicit TTL or the 500 ms default; expired entries are removed on `Snapshot()`.

**Verified risk:** `StateStore.SetState()` differs from incremental commands: an omitted TTL produces a non-expiring source. That is suitable only for an explicitly persistent/manual-state contract; an automation action adapter must always set a finite TTL or explicitly clear its source. Otherwise a client disconnect can leave an input asserted until reset.

**Verified risk:** the initial `SafetyController` state is `Ready`, but its `StateStore` starts unpaused. `CommandRouter` accepts raw state-changing commands without requiring `Running`, and `ControllerRegistry.SubmitAll()` submits every slot snapshot without checking `RunState`. Therefore a raw pipe client can produce virtual-controller output before `start`; `pause` does neutralize it. This is an observable lifecycle-contract gap, not yet a change request against the other process.

**Verified:** default composition constructs exactly two independent slots, maps each physical event into every currently `Running` slot, and globally suppresses a physical event if any running slot maps it. Thus one keyboard/mouse mapping can intentionally control two characters at once; it cannot currently provide per-slot native-pass-through when both slots disagree.

**Verified:** emergency reset clears and pauses both slots; disposal cancels loops, waits for them, resets both slots, disposes raw input, then stops/disposes the backend.

**Coverage:** `StateStore.cs`, `ControllerRegistry.cs`, and `HostComposition.cs` — deeply reviewed for source merge, two-slot output, physical-input broadcast, and shutdown. `ReportLoop` remains unreviewed, so actual output tick timing and output-error failure behavior are still open.

**Next pass:** review the report loop and Python client/UI host-manager integration to establish actual execution cadence, command serialization, reconnection behavior, and current UI exposure of two-controller state.
## [Review continuation] 2026-09-04 — execution cadence and client contract

### A. Scope declaration (before source review)

**Files selected for this pass:**
- `virtual_gamepad/host/src/VirtualGamepadHost/Runtime/ReportLoop.cs` — submission frequency and backend failure behavior.
- `virtual_gamepad/client/python/virtual_gamepad_client.py` — Python-side request lifecycle, serialization, and error behavior.
- `virtual_gamepad/ui/virtual_gamepad_ui/main_window.py` — whether the UI gives both controller slots clear, independent visibility and control.

**Questions:** actual backend cadence and error handling; whether concurrent callers on one Python client can cross responses; and whether the current UI fulfills the requested two-controller configuration/operation model.
### C. Findings — execution cadence and client/UI contract

**Verified:** `ReportLoop` submits snapshots every 8 ms (target 125 Hz). In the two-slot runtime it delegates to `ControllerRegistry.SubmitAll()`. The loop has no local exception-to-fail-safe conversion, so a backend exception would end the report task and thereby end `HostComposition.RunAsync()`; disposal will subsequently perform the global emergency reset.

**Verified:** `VirtualGamepadClient` serializes a request/write/read response pair with one Python lock, so concurrent callers sharing one client cannot receive each other's response. It can independently connect to the host pipe, matching the server's multi-client design. A broken connection becomes `VirtualGamepadError`; there is no transparent in-request retry, while the UI detects failure and reconnects on its next 50 ms refresh cycle.

**Verified:** the UI has one visual editor with an explicit Controller 1 / Controller 2 selector, two separate persistent profiles, two live status indicators, and selected-slot Start/Pause. It applies both saved profiles at initial connection and its emergency-reset/close actions reset both controllers. The same key may be bound in both profiles, so the host's broadcast behavior can drive two characters concurrently.

**UI limitation (not a defect):** it is a switchable single editor rather than two simultaneously visible configuration canvases. This matches the later “switch controller 1 / controller 2 on the page” requirement, but if the desired meaning of “two interfaces” is side-by-side editing, that remains a product/UI decision rather than a host limitation.

**Coverage:** `ReportLoop.cs`, `virtual_gamepad_client.py`, and `main_window.py` — deeply reviewed for cadence, request serialization/reconnection behavior, and two-controller UI exposure.

**Review result:** the parallel implementation is a viable independent virtual-input backend. It should remain outside the generic perception/spatial modules and be connected later only via a device-neutral `core.actions.VirtualGamepadActionAdapter`; before that connection, its lifecycle guard and persistent `set_state` TTL contract should be resolved and covered by host integration tests.
## [Documentation sync] 2026-09-04 — virtual gamepad review boundary

### A. Scope declaration (before documentation review)

**Goal:** inspect the existing action-layer architecture index and record only the verified integration boundary for the concurrently developed `virtual_gamepad` subsystem. No active virtual-gamepad source/configuration file will be edited.

**Files selected:**
- `CODEBASE.md` — find the existing generic action/spatial architecture section to update with the verified backend boundary.

**Intended result:** preserve the rule that workflows depend on `core.actions` contracts, while the named-pipe host/client remains an optional concrete execution backend.
### C. Documentation sync result

**Verified documentation update:** `CODEBASE.md` now records the inspected virtual-gamepad host/client/UI files and a clearly marked *reserved, not-yet-wired* action-to-gamepad flow. It preserves the current generic boundary: workflow → future device-neutral action adapter → Python pipe client → host → ViGEm.

**Risk registered:** before an adapter is added, resolve and test the raw-command lifecycle guard and the non-expiring no-TTL `set_state` behavior. The documented future adapter must supply a distinct source identity and a finite TTL for automation input.

**Files changed by this review only:** `CODEBASE.md` and this append-only `ITERATION_LOG.md`; no file belonging to the concurrently running virtual-gamepad implementation was changed, staged, reverted, or committed.
## [Status review] 2026-09-04 — modular foundation and mapping scope

### A. Scope declaration (before source/document review)

**Question:** which mainline modules remain, and does “map mapping” already exist?

**Files selected:**
- `docs/PERCEPTION_ENGINE_CHECKPOINT.md` — authoritative P0–P9 roadmap/status.
- `CODEBASE.md` — verified coordinate-mapping and legacy-navigation boundaries.
- `docs/plans/2026-09-04-desktop-ocr-action-mapping-proof-design.md` — distinguish the shipped full-desktop proof from window/viewport calibration work.

**Decision to make from evidence:** separate complete desktop screenshot → physical mouse mapping from unfinished game-window/viewport mapping and from the legacy minimap/world-navigation problem.
### C. Status-review findings

**Verified terminology correction:** “mapping is implemented” is true only for the tested whole-desktop path: a `FULL_SCREEN` screenshot target maps through an explicit affine transform to a `PHYSICAL_SCREEN` pointer coordinate and can drive the minimal mouse adapter. It is not yet a complete game-window/viewport calibration system, and it is separate from legacy minimap-to-world navigation.

**Verified remaining P4:** feature/keypoint matching and motion/frame-difference adapters remain absent; ML object detection is only a reserved provider/adapter seam. Color, template, shape, OCR adapter, optional RapidOCR backend, and a Traditional-Chinese model resource are present.

**Verified remaining P5:** game-window discovery/selection, client-area/viewport crop mapping, runtime anchor calibration, multi-display policy, and calibration UI preview are not implemented as the generic mapping path. Existing spatial primitives do not make those runtime composition choices.

**Verified mainline queue:** P6 engine-backed UI workbench; P7 legacy Portal/Loot/minimap bridges with regressions; P8 the configurable PoE event-chain state-machine workflows; P9 full dependency/error/regression audit. The action layer is intentionally still a proof slice (mouse move/double-click); keyboard and gamepad adapters have not joined it.

**Documentation:** no `CODEBASE.md` change is required for this read-only status check because the reviewed status and boundary are already recorded there. This log preserves the mapping distinction and next implementation sequence.
## [Architecture review] 2026-09-04 — full-screen mapping scope and frame preprocessing

### A. Scope declaration (before source review)

**Questions:** with a full-screen game, which P5 work is genuinely unnecessary versus still valuable; and is screenshot/image preprocessing already a standalone reusable core module?

**Files selected:**
- `core/spatial/desktop_mapping.py` — current full-screen transform contract.
- `core/perception/algorithms/color.py` — existing HSV/morphology preprocessing ownership.
- `core/perception/algorithms/template.py` — existing grayscale/edge/template preprocessing ownership.

**Review criteria:** distinguish generic, reusable operations from detector-private image preparation; identify the smallest independent preprocessing module that does not make all vision algorithms depend on OpenCV-specific policy.
### C. Findings — full-screen mapping and current preprocessing

**Verified mapping scope:** `DesktopCoordinateMapper` is deliberately restricted to `FULL_SCREEN → PHYSICAL_SCREEN`. It validates the source point and maps using independently observed width/height plus desktop left/top offset; a full-screen game on one display is exactly its intended current scope. Window discovery, client-area mapping, and anchor calibration are not prerequisites for that deployment mode.

**Verified remaining full-screen safeguards:** multi-monitor/virtual-desktop selection and focus validation are optional later policy choices, not a reason to delay the current pipeline. The mapper already carries virtual-desktop origin/scale evidence and rejects invalid/out-of-range results rather than guessing.

**Verified preprocessing gap:** there is no standalone preprocessing core API. `ColorRegionDetector.detect()` privately normalizes to BGR, converts to HSV, builds a hue-wrapping mask, and applies morphology; `TemplateDetector.detect()` privately normalizes to BGR, generates grayscale/Canny edges, and resizes templates. These are useful implementations but cannot currently be configured, cached, previewed, or shared as independent pipeline steps.

**Architecture direction:** add a new generic `core/perception/preprocessing/` layer before detectors, consisting of immutable preprocessing profiles/pipeline specifications, geometry-preserving frame artifacts, and OpenCV-backed operations. It must return source-coordinate metadata so crop/resize results can be mapped back; algorithms should consume either the original `FrameContext` or named preprocessing artifacts, never own global UI/game policy.

**Documentation:** no `CODEBASE.md` update yet; this is a proposed extraction, not an implemented module. The decision and verified existing ownership are recorded here for the next implementation task.
## [Legacy-chain architecture audit] 2026-09-04 — Torchlight map/navigation/events

### A. Scope declaration (before source review)

**Audit question:** confirm whether the existing small-minimap stitching, localization, routing, Portal, and Loot paths already use the new generic perception/spatial/action architecture.

**Initial discovery scope:**
- legacy navigation/minimap sources and their composition callers;
- Portal and Loot recognizer/handler sources and their callers;
- image-transformation helpers used outside `core/perception`.

**Required output:** a verified old-chain → new-core matrix, specifically identifying hard-coded scene/geometry assumptions, embedded preprocessing, result types, input calls, and absent compatibility bridges. The audit is read-only; virtual-gamepad work remains out of scope.
### C. Discovery findings — legacy chain inventory

**Verified inventory:** the legacy system is substantial and remains active under `core/vision`, `core/localization`, `core/navigation_tasks`, `core/events/types/portal`, and `core/events/types/loot`, with GUI composition under `gui/modes/navigation`. It is not a thin wrapper around `core/perception`.

**Important correction to the earlier simplification:** legacy HSV preprocessing is partly split already (`core/vision/hsv/preprocessing.py`, `masks.py`, `combined.py`, `params.py`), but it is a vision/minimap-local utility family rather than the new generic perception preprocessing contract. Portal and Loot additionally contain their own masks, ROI extraction, template preparation, scoring, and exclusion preprocessing under their event-type folders.

**Next review order:** first trace legacy minimap capture/localization/path routing; then read Portal and Loot entrypoints/pipelines; finally compare their result/action models to `PerceptionEngine`, `DesktopCoordinateMapper`, and `core.actions`.
## [Legacy-chain architecture audit] 2026-09-04 — localization algorithm

### A. Scope declaration (before source review)

**File selected:** `core/localization/localize_pipeline.py`.

**Reason:** this is the high-complexity bridge between minimap frames, map-package wall masks, template/feature matching, stateful position estimates, and the navigation runtime. It must be read alone to determine whether its image preparation/result contract is reusable or Torchlight/minimap-bound.

**Questions:** input coordinate assumptions, preprocessing ownership, output model, direct dependencies on `NavigationCore`, and whether it invokes the new perception/spatial/action layers.
### C. Findings — legacy minimap localization

**Verified:** `localize_frame(nav_core, minimap_img, player_pos=None)` is a stateful Torchlight/minimap localization pipeline, not an adapter to the new engine. It accepts a raw minimap array and a mutable `NavigationCore`, calls the legacy HSV recognizer itself, mutates localization/registration fields directly, and returns an untyped `(global_x, global_y, confidence)` tuple.

**Verified preprocessing coupling:** mask extraction (`nav_core.recognizer.extract_combined`), feature thresholds, wall-template scaling/closing, local/global search-area selection, and frame-to-frame displacement are all orchestrated inside the localization route. The source assumes a minimap center/player marker, `draw_scale`, a persisted wall-layer canvas, and navigator-owned confidence/jump policies.

**Verified new-architecture gap:** this path does not construct `FrameContext`, `TargetDetection`, `PerceptionRunResult`, `MappedPoint`, or `ActionRequest`; it imports neither `core.perception` nor `core.spatial` nor `core.actions`. It must be preserved behind a compatibility bridge rather than treated as already migrated.

**Next pass:** inspect the legacy HSV preprocessing package and `NavigationCore` composition boundary to distinguish reusable image primitives from minimap-specific wall/localization policy.
## [Legacy-chain architecture audit] 2026-09-04 — HSV preprocessing boundary

### A. Scope declaration (before source review)

**Files selected:**
- `core/vision/hsv/preprocessing.py` — image normalization/HSV preparation primitives.
- `core/vision/hsv/masks.py` — minimap mask construction and geometry suppression.
- `core/vision/hsv/combined.py` — public combined-mask composition used by legacy localization.

**Questions:** which operations are generic enough to migrate into the new preprocessing core, and which encode fixed player/minimap geometry or Torchlight-specific wall semantics.
### C. Findings — HSV preprocessing boundary

**Verified:** the old HSV code is split into helper files, but not into a generic module contract. Each function takes the mutable `recognizer` object and reads its internal flags, kernels, thresholds, color ranges, player geometry, and weights. It returns raw NumPy arrays with no profile schema, artifact identity, provenance, coordinate transform, cache boundary, or reusable pipeline API.

**Reusable primitives found:** gamma LUT, Gaussian/median blur, CLAHE, top-hat morphology, percentile normalization, brightness/contrast, HSV range masks, component-area filtering, Canny, morphology, dilation, and weighted mask composition. These can be re-homed as parameterized generic preprocessing operations.

**Minimap/Torchlight policy that must not be promoted unchanged:** wall/fog/player semantic masks; center-player fallback; erasing fixed circles around the player; saturation filtering only near that center; and the weighted wall+edge match mask. Those belong in a legacy minimap profile/adapter or a future target-specific configuration instance, not in universal preprocessing defaults.

**Confirmed answer so far:** the user is right that legacy preprocessing is only partially modularized within the old recognizer package; it has not been converted to the new configurable perception architecture.

**Next pass:** inspect Portal entrypoint/detector composition to verify whether it returns legacy event records and performs its own pre-processing/action sequence rather than standardized `TargetDetection` plus separate action execution.
## [Legacy-chain architecture audit] 2026-09-04 — Portal detection composition

### A. Scope declaration (before source review)

**File selected:** `core/events/types/portal/minimap_detector.py`.

**Reason:** this is the Portal recognition entrypoint that chooses legacy minimap detection modes and projects hits into navigation/event coordinates. It is the key proof point for whether Portal recognition already uses the generic `PerceptionEngine` result contract.

**Questions:** detector choices, preprocessing/result models, map-coordinate projection, and dependencies on legacy event/navigation state.
### C. Findings — Portal detection entrypoint

**Verified:** `PortalMinimapDetector` is a legacy `EventDetector`, not a generic perception adapter. It consumes `tick.raw_minimap_frame`, loads Portal-specific asset paths itself, chooses the Portal-specific `feature`, `shape_color`, template, or fallback mode, and returns `list[EventDetection]`.

**Verified coupling:** its constructor owns template resource loading, fixed scale candidates, logging, and Portal configuration. Its `detect()` owns fallback policy and passes raw arrays to dedicated Portal matchers; no `FrameContext`, `TargetProfile`, provider registry, `TargetDetection`, or `PerceptionEngine` is involved.

**Partial good news:** detection modes are already split into functions/packages, so their underlying algorithms can be harvested. But their current contracts are event-specific and their resource/preprocessing/fallback policy is embedded in the Portal feature.

**Next pass:** read Portal detection conversion/projection and runtime handler to confirm the old result reaches navigation and input through legacy event coordination rather than the new spatial/action contracts.
## [Legacy-chain architecture audit] 2026-09-04 — Portal result and action path

### A. Scope declaration (before source review)

**Files selected:**
- `core/events/types/portal/minimap_detection/conversion.py` — transform raw minimap hits into event detections.
- `core/events/types/portal/handler/runtime.py` — Portal event state/action orchestration.
- `core/events/types/portal/handler/interaction.py` — concrete Portal interaction action construction.

**Questions:** what coordinate/result schema crosses the old detection boundary, whether positions are projected through generic spatial mapping, and whether actions cross `core.actions` or remain legacy event commands.
### C. Findings — Portal result and action path

**Verified:** Portal conversion emits `EventDetection(event_type, local_minimap_pos, confidence, metadata)`, whose coordinate semantics are implicitly local-minimap pixels. It carries a raw bbox and many Portal scoring fields in metadata, but it is not `TargetDetection` and has no explicit `CoordinateSpace` contract.

**Verified:** Portal handling is already internally modular as a legacy event state machine (`move_near_event → align_on_portal → interact → wait_result`), but it uses `EventAction.move_to`, `EventAction.press_key("d")`, a global navigation task position, and a minimap environment signature. It does not use `MappedPoint`, `ActionRequest`, or a `core.actions` adapter.

**Important nuance:** the old Portal feature should not be discarded as a monolith. Its detector, conversion, movement, interaction, and completion code are useful legacy modules. Migration means wrapping/replacing the perception and coordinate boundaries while preserving its handler state machine and regression behavior.

**Next pass:** inspect the Loot detection entrypoint and its detection pipeline to confirm its own ROI/mask/template/exclusion preprocessing and identify which parts overlap the intended generic preprocessing core.
## [Legacy-chain architecture audit] 2026-09-04 — Loot detection entrypoint

### A. Scope declaration (before source review)

**File selected:** `core/events/types/loot/minimap_detector.py`.

**Reason:** determine whether Loot reuses generic perception or owns a separate minimap-specific recognition stack, and identify the result schema and coupling to event configuration/template assets.
### C. Findings — Loot detection entrypoint

**Verified:** `LootMinimapDetector` is a second, independent legacy perception stack. It owns Loot/minimap template assets, multi-scale prepared-template caches, player-marker exclusion templates, seed ROI detection, feature/blob mode switching, temporal presence confirmation, cached result reuse, async matching, and debug capture.

**Verified:** it consumes `tick.raw_minimap_frame` and produces `EventDetection` with `local_minimap_pos`; `AsyncLootPerception` is a Loot-specific temporal worker, not the new `PerceptionEngine` confirmation stage. No provider contract, `FrameContext`, `TargetProfile`, standardized `TargetDetection`, or generic action mapper is used.

**Migration implication:** the old Loot implementation is more than one recognizer to replace. Its seed generation, exclusion logic, feature matcher, temporal stabilization, and cluster-to-event projection must be split into reusable/raw layers and then bridged one behavior at a time, with the old path retained for regression comparison.

**Next pass:** read the Loot detection pipeline/ROI implementation and navigation composition boundary, then produce a complete old-chain/new-core coverage matrix and a safe migration order.
## [Legacy-chain architecture audit] 2026-09-04 — Loot recognition algorithm

### A. Scope declaration (before source review)

**File selected:** `core/events/types/loot/detection/pipeline.py`.

**Reason:** this high-complexity recognition pipeline decides how loot-specific preprocessing, seed ROIs, template/shape/color evidence, exclusions, clustering, and debug data compose. It is read separately to avoid mistaking its internal decomposition for generic-module integration.
### C. Findings — Loot recognition algorithm

**Verified:** the Loot pipeline contains a sophisticated but fully event-local image-processing chain: BGR conversion, small-frame padding/unpadding, candidate seed ROI extraction, grayscale/Canny generation, grayscale/edge/masked template responses, color scoring, NMS/duplicate merging, clustering, and a long list of minimap/game-artifact exclusions.

**Verified preprocessing duplication:** Canny thresholds, color/mask logic, template preparation, ROI origin offsets, and center-player exclusion all live in Loot detection modules. The ROI code correctly adds local crop offsets back to Loot candidate coordinates, but exposes no shared transform/provenance object for other algorithms or the new mapper.

**Verified domain assumptions:** fixed minimap center/player exclusion, named artifact classifiers (diamonds, sword, pile, triangle, red star, map ring), Loot templates, and Loot score weights are target/game policy. They must remain legacy profile/adapter behavior, not become generic preprocessing operations.

**Reusable candidates:** image normalization, padding/crop geometry, grayscale, Canny, template scaling/masks, response peak extraction/NMS, basic color masks, and connected-component ROIs are reusable primitives once separated from Loot scoring and exclusion policy.

**Next pass:** trace legacy localization → navigation task → input execution to establish the full old map-to-movement chain and confirm it bypasses `core.spatial` and `core.actions`.
## [Legacy-chain architecture audit] 2026-09-04 — navigation to movement action

### A. Scope declaration (before source review)

**File selected:** `core/navigation_tasks/movement_executor.py`.

**Reason:** this is the high-complexity navigation-side movement/action decision maker. Reading it alone establishes whether legacy global-map positions become new `ActionRequest` objects or flow through older click/input machinery.
### C. Findings — navigation movement facade

**Verified:** `MovementExecutor` is a reusable *legacy navigation* facade rather than a device/action adapter. It has substantial map-routing state (A* path, wall/explored maps, anchors, lookahead, click throttling, stuck detection, recovery probes) and delegates execution decisions to `movement_step()`.

**Scope clarification:** this is already a worthwhile generic global-map movement component, but its coordinate system is the persisted stitched-map/world plane, not the new full-screen physical-pointer plane. It needs an explicit bridge between navigation intent/subgoal and screen/action execution; it should not be moved wholesale into `core.spatial`.

**Next pass:** read the movement pipeline and navigation UI intent executor to find the exact old map-point → screen-click/input path and document the separation point needed for a compatibility adapter.
## [Legacy-chain architecture audit] 2026-09-04 — movement decision algorithm

### A. Scope declaration (before source review)

**File selected:** `core/navigation_tasks/movement/pipeline.py`.

**Reason:** this high-complexity pipeline turns global localization/path state into a `MovementStep`. It must be inspected separately to determine whether it already creates a neutral action intent or embeds Torchlight screen-click mapping/input assumptions.
### C. Findings — movement decision algorithm

**Verified:** `movement_step()` is free of direct device I/O. It computes an A* path lookahead/recovery subgoal in the stitched global-map plane and returns a `MovementStep(path, subgoal, should_click, force_click_target, …)`. This is a useful existing intent boundary, but it predates and does not use `core.actions`.

**Verified coupling below the surface:** its comments and final-goal rules explicitly rely on a later “screen minimum radius” and “mapped anchor point” stage. Therefore the next executor is where legacy global-map coordinates are transformed to screen clicks; that transform must be audited separately and eventually become the navigation compatibility bridge.

**Architecture conclusion:** pathfinding itself should remain an independent navigation capability. The migration target is not “replace A* with perception”; it is to have the legacy `MovementStep` translated by an explicit map-world → screen action adapter, while input execution is moved behind device-neutral actions.

**Next pass:** inspect the navigation intent executor and localization tick/composition to confirm the real coordinate conversion and old input driver calls.
## [Legacy-chain architecture audit] 2026-09-04 — runtime coordinate and input bridge

### A. Scope declaration (before source review)

**Files selected:**
- `gui/modes/navigation/input/intent_executor.py` — final navigation-intent to input dispatch.
- `gui/modes/navigation/runtime/localization_tick.py` — localization results into navigation runtime.
- `core/navigation_tasks/update_pipeline.py` — navigation controller update composition.

**Questions:** trace the old stitched-map/minimap coordinate flow, confirm where screen clicks and key presses are executed, and compare those seams to `core.spatial` / `core.actions`.
### C. Findings — runtime coordinate and input bridge

**Verified legacy flow:** `capture_navigation_localization_tick()` obtains a manually configured minimap capture rectangle, captures only that image, resolves a local player coordinate, and calls `NavigationCore.localize()`. `update_controller_context()` uses the resulting stitched-map position plus wall/explored maps to select tasks and create `NavigationIntent` values.

**Verified action boundary gap:** `execute_navigation_intent()` dispatches `MOVE_MAP`, `CLICK_SCREEN`, and `PRESS_KEY` directly to the GUI-owned `MotionController`. For map movement it calls `move_to_map_target(player_global, subgoal_global)` or `click_map_target_once(...)`, which owns the old global-map → screen-click conversion; there is no `core.spatial` mapper or `core.actions.ActionRequest` between the intent and device call.

**Important nuance:** `NavigationIntent` is already an application-level command seam and should become the compatibility bridge input. The safe migration is to introduce a translator/adapter below it, not to make the existing localization or path planner import mouse/gamepad code.

**Confirmed end-to-end result:** legacy map capture, HSV preprocessing, localization, world-map pathfinding, Portal/Loot events, map-to-screen conversion, and actual input remain a separate Torchlight-oriented chain. New perception/spatial/actions currently coexist beside it; they do not yet drive it.

**Next:** compile the audit matrix and a staged migration plan, including exactly what can be reused, what must stay target-specific, and what needs extraction first.
## [Legacy-chain architecture audit] 2026-09-04 — legacy event contracts

### A. Scope declaration (before source review)

**File selected:** `core/events/models.py`.

**Reason:** confirm the legacy `EventDetection` / `EventAction` schemas that Portal, Loot, navigation, and GUI currently exchange, so the migration boundary is based on actual contracts rather than filename inference.
### C. Findings — legacy event contracts

**Verified:** the old event domain has its own coherent coordinate model: `EventDetection.local_minimap_pos` → `EventObservation.global_pos` → `EventTask.global_pos` → `EventAction.target_global_pos` or `screen_pos`/`key`. This is distinct from the new `TargetDetection` / `MappedPoint` / `ActionRequest` model.

**Verified:** `EventAction` is a high-level legacy command schema with `MOVE_TO`, `CLICK_SCREEN`, `PRESS_KEY`, `WAIT`, `COMPLETE`, and `FAIL`; it is not a device-neutral execution request because it carries ambiguous raw screen tuples and a string key, with actual dispatch owned by the GUI `MotionController` path.

**Migration seam identified:** retain this old event state machine initially, then introduce explicit adapters at both ends: `EventDetection ↔ TargetDetection` for perception compatibility, and `EventAction/NavigationIntent → core.actions` for execution compatibility. The global-map position projection remains a separate navigation/spatial transform.

**Audit conclusion:** the user’s diagnosis is confirmed. Old Torchlight-adapted chains are internally decomposed but have not been migrated to, or driven by, the new architecture. This finding now drives the implementation order rather than treating new perception modules as integration-complete.
## [Documentation sync] 2026-09-04 — legacy/new architecture integration status

### A. Scope declaration (before documentation update)

**Trigger:** the completed read-only audit established a material correction to the mainline status: legacy Torchlight minimap/localization/navigation/Portal/Loot modules are internally decomposed but not connected to the new generic perception/spatial/action architecture.

**Documentation to update:**
- `docs/PERCEPTION_ENGINE_CHECKPOINT.md` — record the verified integration status and migration boundary.
- `CODEBASE.md` — register the legacy/new contract separation and bridge order as a current architectural risk.

**No source/config/test file will be changed.**
### C. Documentation sync result

**Checkpoint updated:** `docs/PERCEPTION_ENGINE_CHECKPOINT.md` now records the verified status of legacy minimap/localization/navigation/Portal/Loot paths, the true P7 bridge boundaries, and the preprocessing extraction prerequisite.

**Codebase updated:** `CODEBASE.md` now makes the old-chain/new-core separation explicit in its risk/seam register, including the GUI `MotionController` dispatch boundary.

**Files changed by this audit:** only `ITERATION_LOG.md`, `docs/PERCEPTION_ENGINE_CHECKPOINT.md`, and `CODEBASE.md`. No legacy source, test, configuration, virtual-gamepad, staging, or Git history was changed.
## [Legacy-chain architecture audit] 2026-09-04 — map stitching implementation

### A. Scope declaration (before source review)

**Question:** identify and inspect the legacy map-drawing/stitching implementation that feeds the persisted wall/explored map used by localization and routing.

**Discovery scope:** source files/classes containing `stitcher`, `stitch`, `wall_layer`, or map-frame merge logic, excluding generated data and tests until the runtime entrypoint is identified.

**Goal:** confirm whether map construction has an independent reusable core or is coupled to GUI/capture/Torchlight minimap assumptions, and add it to the old/new architecture matrix.
### C. Discovery findings — map stitching inventory

**Verified:** map construction has a genuine independent subsystem under `core/mapping/` (`MapStitcher`, frame preparation/pipeline, weighted merge, package I/O, rendering, performance). It is not only GUI code, and it persists canvas/wall/fog/explored layers for the later localization/routing chain.

**Current uncertainty:** this module may be more reusable than Portal/Loot because its public API already accepts masks and player position. Its actual state/config/capture assumptions still need inspection before assigning it a generic-core status.

**Next pass:** read `core/mapping/stitcher.py` alone, then identify which map-frame preparation call supplies its masks.
## [Legacy-chain architecture audit] 2026-09-04 — map stitcher core

### A. Scope declaration (before source review)

**File selected:** `core/mapping/stitcher.py`.

**Reason:** establish whether `MapStitcher` is a reusable map-domain core with injectable visual evidence, or whether its state and public API embed Torchlight/minimap recognition and GUI/capture concerns.
### C. Findings — map stitcher core

**Verified:** `core/mapping/MapStitcher` is already a meaningful non-GUI mapping core. It owns a canvas, wall/fog/explored/weight layers, keyframe and prior-frame registration, phase-displacement tracking, weighted merge, persisted map packages, and map rendering helpers. It is reusable for any sequence of aligned local masks, not merely a Portal/Loot feature.

**Verified boundary:** `MapStitcher.add_frame()` accepts caller-supplied `match_mask`, `save_mask`, `fog_mask`, and `player_pos`; it does not own screenshot capture or HSV recognition. However all values are untyped arrays/tuples and its public state is explicitly wall/fog/player/minimap-map oriented (`draw_scale`, wall-thickness closing, canvas-center world plane). It has no `FrameContext`, preprocessing artifact geometry, provider, profile, or standardized detection contract.

**Correct classification:** preserve `core/mapping` as the future reusable *map-domain* core. Do not duplicate it in `core/perception`. The required modernization is to introduce typed evidence/coordinate contracts at its input/output and replace the GUI/legacy HSV composition around it gradually.

**Next pass:** inspect the mapping runtime session and frame-preparation boundary to confirm how the old recognizer supplies masks and whether preprocessing is still hard-bound to the Torchlight minimap UI.
## [Legacy-chain architecture audit] 2026-09-04 — map-frame composition

### A. Scope declaration (before source review)

**Files selected:**
- `gui/modes/mapping/runtime/session.py` — GUI/runtime source-to-stitcher composition.
- `core/mapping/frame_preparation.py` — generic versus map-semantic scaling/mask preparation.
- `core/mapping/frame_pipeline.py` — caller-provided evidence into stitcher state transition.

**Questions:** establish the exact preprocessing/capture ownership on the map-building path, and which pieces can be retained or extracted without altering working map behavior.
### C. Findings — map-frame composition

**Verified full mapping path:** `MappingSession.tick()` captures a configured square/rectangle, defaults the player to the crop center or uses the old player tracker, invokes `HSVRecognizer.extract_combined()`, then sends raw arrays to `MapStitcher.add_frame()`. It also returns the old recognizer's preprocessed display image directly to the GUI.

**Verified composition coupling:** this capture → recognition → stitch path is currently assembled through GUI `app_context`; it has no `FrameContext`, typed preprocessing artifact, source-coordinate transform, or provider/engine composition. The same old HSV mask generation feeds both map construction and later localization.

**Verified `core/mapping` strength and limitations:** frame preparation and stitching are cleanly separated from the GUI. They implement scale/offset recovery, keyframe/f2f registration, visible-wall/fog weighted merge, duplicate suppression, and persisted world-map layers. But their values are naked masks/tuples and their default center-player/canvas/draw-scale semantics remain minimap-map specific.

**Final map-building classification:** the user’s previous mapping/stitching work is valuable reusable map-domain logic, but it is not yet an implementation of the new generic perception/spatial/action design. It should be retained and wrapped with typed evidence and coordinate adapters, not rewritten or claimed as P4/P5 complete.

**Next:** add this map-stitcher result to the checkpoint and codebase risk record, then deliver the complete old/new coverage matrix and staged bridge plan.
## [Documentation sync] 2026-09-04 — map-stitcher audit result

### A. Scope declaration (before documentation update)

**Trigger:** the audit confirmed that `core/mapping` is an independently useful legacy map-domain core, while its GUI/HSV composition and untyped mask contracts remain outside the new generic engine.

**Documentation to update:** the legacy audit entries in `docs/PERCEPTION_ENGINE_CHECKPOINT.md` and `CODEBASE.md`, preserving the distinction between retainable map-domain logic and unbridged perception/spatial/action integration.
### C. Documentation sync result

**Checkpoint and codebase updated:** both now distinguish the retainable `core/mapping/MapStitcher` core from the unbridged GUI capture/HSV composition feeding it.

**Audit status:** reviewed end-to-end legacy paths now cover map-frame capture/preprocessing/stitching, minimap localization, route/event movement intent, Portal detection/handler, Loot detection pipeline, and GUI input dispatch. The final report can state the current architecture with evidence rather than inference.

**Files changed by this final audit sync:** only `ITERATION_LOG.md`, `docs/PERCEPTION_ENGINE_CHECKPOINT.md`, and `CODEBASE.md`.
## [Architecture decomposition review] 2026-09-04 — bottom capabilities and top-level adapters

### A. Scope declaration (before source review)

**Question:** give a detailed, actionable classification of current modules: keep as a lower-level capability, extract/refactor into a reusable lower-level capability, or retain as a game/scene/workflow adapter.

**Files selected for final boundary verification:**
- `core/input/motion_mapping.py` — existing stitched-world → screen mapping algorithm.
- `core/events/coordinator/observation.py` — legacy event detection/stabilization/task composition.
- `core/routing/obstacles.py` — map-domain wall-layer derivation.

**Output:** a dependency-safe target hierarchy, concrete extraction candidates, explicit non-extraction rules, and a staged wrapper strategy that preserves current behavior.

## [Architecture audit follow-up] 2026-09-04

### A. Scope declared before reading

**Requested outcome:** provide a verified, detailed account of the present modular architecture; distinguish reusable low-level capabilities from Torchlight/minimap-specific policy and top-level orchestration.

**Files to verify in this pass:**

- `core/input/motion_mapping.py` — confirm the existing world-map-to-screen projection seam.
- `core/events/coordinator/observation.py` — confirm the event coordination boundary.
- `core/routing/obstacles.py` — confirm reusable map-domain obstacle derivation.

**Decision boundary:** this is an architecture audit and documentation checkpoint only. No legacy runtime, GUI, virtual-gamepad, Portal, or Loot code will be changed.

### C. Findings

- **(verified) World-to-view projection seam:** `calculate_movement_click()` and `calculate_mapped_target_click()` compute a normalized direction from global-map coordinates, project it from a supplied screen centre, and constrain the radial distance. That geometry is reusable below the game policy layer. `apply_bottom_click_guard()`, click-radius tuning, and the supplied game centre are game/UI policy and must remain configurable at the adapter/profile layer.
- **(verified) Event orchestration seam:** `observe_events()` executes detect → position stabilization → observation memory merge → task selection. It is a reusable event-domain coordinator, but its inputs/outputs still use the legacy event contracts; it should gain bridges on both sides instead of being rewritten into a workflow.
- **(verified) Map-domain image primitive:** `derive_navigation_wall_layer()` performs thresholding followed by optional cross-kernel erosion to create an A*-friendly obstacle layer without mutating the localization layer. It can remain a mapping/routing primitive; it is not a generic detector and should not move into `core.perception`.
- **Confirmed scope status:** no source runtime code was changed in this audit. The pre-existing dirty worktree, particularly `virtual_gamepad/`, remains untouched.

**Next design action, when authorised:** define a standalone preprocessing/artifact contract first; then introduce typed map evidence, legacy bridges, and action translation in small compatibility-preserving steps.

## [Generic core extraction plan] 2026-09-04

### A. Scope declared before reading

**Requested outcome:** extract currently reusable capabilities into generic low-level modules and optimise the legacy Torchlight/minimap chain by making it delegate to those modules where behaviour can be preserved. Do not build game-specific PoE workflows in this phase.

**Files to inspect for the first task batch:**

- `core/vision/hsv/preprocessing.py` — identify exact image operations and existing parameter dependencies.
- `core/vision/hsv/masks.py` — identify mask and connected-component primitives.
- `core/vision/hsv/combined.py` — identify composition and game-semantic portions that must remain legacy policy.

**Compatibility constraints:**

- Keep existing public legacy imports and call signatures working.
- Preserve Torchlight-specific wall/fog/player choices as legacy/profile policy.
- New generic modules must not import GUI, `HSVRecognizer`, Portal, Loot, events, or input controllers.
- Establish regression tests before redirecting legacy code to a new implementation.

### C. Findings

- **(verified) Direct extraction candidates:** percentile normalization, gamma LUT, Gaussian/median blur, LAB-CLAHE, top-hat, BGR channel scaling, HSV range masks, morphology, Canny, connected-component filtering, saturation masks, circle masking, and weighted mask fusion are implemented as recognizer-coupled helpers but have no inherent Torchlight dependency.
- **(verified) Legacy policy that must not move:** wall/fog/player HSV ranges, transparency score choice, player-centre fallback, player-clear radius, saturation exclusion region, and wall/edge weights are game/profile semantics. The existing `HSVRecognizer` facade must retain ownership of these choices.
- **(verified) First compatibility seam:** the legacy wrapper can construct generic operation parameter objects from its existing attributes and call a new preprocessing pipeline; `extract_combined_masks()` can keep its tuple return contract while delegating generic image operations.
- **Plan refinement:** begin with a small typed image-artifact geometry contract plus independently testable pure operations. Do not move a recognizer or map-stitcher in the first slice.

## [Generic core extraction plan — contracts] 2026-09-04

### A. Scope declared before reading

**Goal:** align the new preprocessing contract with existing perception models, coordinate-space conventions, and test conventions before writing the implementation plan.

**Files to inspect:**

- `core/perception/models.py` — current shared model conventions.
- `core/perception/coordinates.py` — current coordinate-space and geometry conventions.
- `tests` / `core/perception/tests` discovery — current test layout and runner conventions.

### C. Findings

- **(verified) Existing contract location:** `CoordinateSpace`, `BoundingBox`, and `FrameContext` are all defined in `core/perception/models.py`; there is no `core/perception/coordinates.py`. The new preprocessing contract should import those existing types rather than create a parallel coordinate enum.
- **(verified) Test location:** perception tests live under repository-level `tests/` and follow the `test_perception_*.py` naming convention. A preprocessing suite belongs at `tests/test_perception_preprocessing.py`.
- **Corrected plan:** preprocessing artifacts will use the existing `CoordinateSpace` and expose source-frame geometry explicitly. No duplicate coordinate contract will be added.

## [Generic core extraction plan — test and public API conventions] 2026-09-04

### A. Scope declared before reading

**Goal:** determine the exact public-export and testing conventions needed for a safe first generic preprocessing slice.

**Files to inspect:**

- `core/perception/__init__.py` — package-level public API convention.
- `tests/test_perception_models.py` — model contract test style.
- `tests/test_recognizer_optimized.py` — existing HSV-recognizer regression coverage that must remain valid.

### C. Findings

- **(verified) Public API convention:** `core.perception.__init__` explicitly re-exports stable generic types. The new artifact and transform types will be exported there after their tests pass.
- **(verified) Test convention:** the project uses standard-library `unittest`, with direct exact assertions for geometry and output contracts.
- **(verified) Existing regression seam:** `HSVRecognizer.extract_combined(...)` is already covered for saturated dynamic-icon removal. That test will remain unchanged and a new equivalence test will protect the delegated generic operation path.
- **First implementation slice confirmed:** add geometry-aware image-artifact models plus pure generic preprocessing operations first; retain all old HSV facade entrypoints and semantic orchestration in place.

## [Generic core extraction plan — mapping and action seams] 2026-09-04

### A. Scope declared before reading

**Goal:** establish exact existing contracts for typed map evidence and the general action layer so the implementation plan can preserve their public behaviour.

**Files to inspect:**

- `core/mapping/stitcher.py` — current `MapStitcher` input/output boundary.
- `core/actions/models.py` — current generic action contract.
- `core/actions/__init__.py` — current generic action public API.

### C. Findings

- **(verified) Map-stitcher compatibility boundary:** `MapStitcher.add_frame(img, match_mask, save_mask, fog_mask, raw_gray=None, player_pos=None)` is the exact legacy ingress. A new `add_evidence(evidence)` method can unpack a typed contract and delegate to it, leaving all existing callers untouched.
- **(verified) Existing action foundation is broader than the original proof:** package exports already include action contracts plus keyboard and virtual-gamepad adapters. `ActionRequest` itself remains intentionally limited to mapped pointer actions; no action-contract rewrite is required in this extraction phase.
- **Corrected scope:** this phase will add typed map evidence as a compatibility ingress but will not change action contracts. Legacy `NavigationIntent/EventAction → ActionCommand` translation remains a later integration task.

## [SYNC] 2026-09-04 — image artifact geometry contract

### A. SYNC scope declaration

**Triggering task:** add the first reusable preprocessing contract: `ImageGeometry` and `ImageArtifact`.

**Directly changed files:**

- `core/perception/preprocessing/models.py`
- `core/perception/preprocessing/__init__.py`
- `core/perception/__init__.py`
- `tests/test_perception_preprocessing.py`

**Expected impact:** generic perception callers can import the new types; no existing detector, legacy HSV facade, map stitcher, action adapter, GUI, or workflow has been redirected yet.

### C. SYNC result

**Re-read files:** `core/perception/preprocessing/models.py`, `core/perception/preprocessing/__init__.py`, `core/perception/__init__.py`.

**Verified contract:** `ImageGeometry` validates positive dimensions and an output-to-source 3×3 transform; it maps points and enclosing bounding boxes back to source-frame coordinates. `ImageArtifact` validates its image shape against the geometry and source frame. Package exports expose the types without importing legacy modules.

**No coupling introduced:** the new package imports only shared perception models. No existing call path has changed yet.

**Pending verification:** re-read the new test file and update the codebase index before closing this SYNC checkpoint.

## [SYNC] 2026-09-04 — image artifact geometry test/index closure

### A. SYNC scope declaration

**Goal:** verify the new regression test and update the existing perception architecture index with the new public contract.

**Files to inspect:**

- `tests/test_perception_preprocessing.py`
- `CODEBASE.md` sections covering `core/perception` and its public exports.

### C. SYNC result

**Verified test:** `ImageGeometryTests` asserts identity point/box backprojection and rejects an artifact whose output height differs from geometry. The initially missing-module test failed as expected; after the contract was added, the suite passed 2/2.

**CODEBASE.md updated:** added the preprocessing public package and models contract to the perception directory/file index; updated the public perception export description.

**Next task:** add crop/resize/pad operations that compose the same output-to-source geometry; only after their direct tests pass will legacy code be considered for delegation.

## [SYNC] 2026-09-04 — artifact geometry transforms

### A. SYNC scope declaration

**Triggering task:** add generic crop, resize, and pad operations with source-frame transform composition.

**Directly changed files:**

- `core/perception/preprocessing/geometry.py`
- `core/perception/preprocessing/__init__.py`
- `tests/test_perception_preprocessing.py`

**Expected impact:** generic callers can create transformed artifacts with precise source-coordinate recovery. No legacy caller has been redirected.

### C. SYNC result

**Re-read files:** `core/perception/preprocessing/geometry.py`, preprocessing public exports, and `tests/test_perception_preprocessing.py`.

**Verified behaviour:** crop composes a source translation, resize composes inverse x/y scaling, and pad composes inverse padding translation. The crop → resize → pad regression maps artifact point `(105, 57)` back to source point `(70, 35)`; the whole preprocessing suite passes 3/3.

**CODEBASE.md updated:** added the geometry-operation module, its composition rule, and its validation boundary.

**No legacy change:** `HSVRecognizer`, map stitching, navigation, GUI, Portal, and Loot still execute their former implementations.

## [SYNC] 2026-09-04 — generic image operations

### A. SYNC scope declaration

**Triggering task:** add reusable pixel enhancement and colour-space operations used by the legacy HSV path.

**Directly changed files:**

- `core/perception/preprocessing/image_ops.py`
- `core/perception/preprocessing/__init__.py`
- `tests/test_perception_preprocessing.py`

**Expected impact:** generic callers can perform validated image-only operations. No legacy facade is yet redirected.

### C. SYNC result

**Re-read files:** `core/perception/preprocessing/image_ops.py`, preprocessing public exports, and `tests/test_perception_preprocessing.py`.

**Verified operations:** gamma LUT, blur, L-channel CLAHE, top-hat, percentile normalization, intensity/channel scaling, gray/HSV conversion, and Canny are image-only functions with validated shapes/ranges. The direct test suite passes 7/7, including flat-image fallback, uint8/shape preservation, channel scaling, and a real Canny edge response.

**CODEBASE.md updated:** added the generic pixel-operation module and its no-game-semantics boundary.

**Next task:** add generic binary mask, morphology, connected-component, exclusion, and weighted-fusion functions. This remains a lower-level extraction; legacy wall/fog/player policy stays where it is.

## [SYNC] 2026-09-04 — generic mask operations

### A. SYNC scope declaration

**Triggering task:** add reusable HSV range, threshold, morphology, component filtering, saturation, circle, exclusion, and weighted mask-fusion operations.

**Directly changed files:**

- `core/perception/preprocessing/masks.py`
- `core/perception/preprocessing/__init__.py`
- `tests/test_perception_preprocessing.py`

**Expected impact:** generic visual algorithms can compose masks without a legacy recognizer. Existing legacy calls have not changed.

### C. SYNC result

**Re-read files:** `core/perception/preprocessing/masks.py`, preprocessing exports, and the preprocessing regression suite.

**Verified behaviour:** the new module provides HSV range selection, thresholding, all existing morphology modes, connected-component filtering, saturation selection, circle construction, exclusion, and weighted fusion with explicit validation. The 9-test suite verifies small-component removal and a colour → morphology → fusion → circle-exclusion chain.

**CODEBASE.md updated:** added the generic mask-operation module and its semantic boundary.

**Next task:** capture representative legacy HSV outputs and redirect its internal OpenCV primitive calls to the new generic functions without moving wall/fog/player policies.

## [Legacy HSV delegation] 2026-09-04

### A. Scope declared before reading

**Goal:** find the exact legacy facade, defaults, and private-wrapper boundaries needed to delegate image primitives without changing public recognizer behaviour.

**Files to inspect:**

- `core/recognizer_optimized.py` — active legacy recognizer facade and wrappers.
- `core/vision/hsv_recognizer.py` — alternate/public facade relationship.
- `core/vision/hsv/params.py` — parameter ownership and default compatibility constraints.

**Migration rule:** only replace internal primitive calls after a deterministic fixture locks current output. Keep recognizer parameter names and all public methods intact.

### C. Findings

- **(verified) Canonical facade:** `core/vision/hsv_recognizer.py::HSVRecognizer` is the active implementation. It owns all current defaults and preserves compatibility through private wrappers such as `_preprocess_for_wall()`, `_compute_transparency_score()`, and `_filter_small_components()`.
- **(verified) Policy boundary:** wall/fog/player ranges, transparency choice, clear radius, saturation settings, edge weights, and old parameter names are owned by the facade and parameter module; they must remain outside generic preprocessing.
- **Correction:** the `core.recognizer_optimized` import used by legacy tests resolves as a package rather than the assumed single `.py` file. Its package entry must be checked before adding compatibility fixtures.

## [Legacy HSV delegation — package and fixture baseline] 2026-09-04

### A. Scope declared before reading

**Goal:** confirm the compatibility import and capture a deterministic pre-migration output fingerprint for the public recognizer.

**Files/outputs to inspect:**

- `core/recognizer_optimized/` package entry.
- `core/vision/hsv/__init__.py` package surface.
- A fixed synthetic-image execution of public `HSVRecognizer` methods, recorded as fixture hashes before delegation.

### C. Findings

- **(verified) Public HSV helper surface:** `core/vision/hsv/__init__.py` exports the current helper functions and is the correct stable helper-import surface. The expected `core/recognizer_optimized` source path is absent from this worktree despite an older test import; compatibility will use the canonical `core.vision.hsv_recognizer.HSVRecognizer` and the old test will be run before migration.
- **(verified) Deterministic baseline captured:** for the fixed 96×96 synthetic fixture, public recognizer SHA-256/nonzero outputs are wall `b5bf2189…57a9af / 384`, fog `c4889bc7…cd7822 / 576`, combined match `bd013651…3c9e1e / 353`, combined wall `774fd936…e20803 / 235`, combined fog `2d07a41a…c087ae / 0`, and raw gray `cd285e5b…ec87c3 / 6395`.
- **Migration guard:** add these hashes as a canonical-facade regression before changing any legacy HSV implementation. The missing old test import is an existing repository issue to diagnose separately if its suite fails.

## [Compatibility-import diagnosis] 2026-09-04

### A. Scope declared before reading

**Symptom:** `tests/test_recognizer_optimized.py` fails before executing any test because `core.recognizer_optimized` is absent.

**Investigation targets:**

- all repository references to `recognizer_optimized`;
- Git history for the missing compatibility path;
- the canonical `HSVRecognizer` import path and any existing re-export pattern.

**Hypothesis to test only after evidence:** a legacy public compatibility re-export was removed while a still-tracked test/caller retained its import.

### C. Findings

- **(verified root cause) Intentional module removal with stale test:** Git commit `3fd3333` deleted `core/recognizer_optimized.py` during the migration to `core.vision`. Production GUI/localization imports now use `core.vision.HSVRecognizer`; the only executable stale reference found is `tests/test_recognizer_optimized.py`.
- **(verified working pattern):** `core.vision.hsv_recognizer.HSVRecognizer` is the canonical replacement and exposes the same recognition behaviour targeted by the stale test. Historical architecture notes still mentioning the deleted wrapper are records, not executable dependencies.
- **Hypothesis:** replacing only the stale test import with the canonical public import will restore the intended regression test without resurrecting a deliberately deleted compatibility module.

### C. Resolution

- **Minimal hypothesis test:** the stale test's exact assertions pass unchanged when executed against `core.vision.HSVRecognizer`.
- **Single root-cause fix:** `tests/test_recognizer_optimized.py` now imports the canonical public facade instead of the intentionally removed module.
- **Verification:** preprocessing, legacy-HSV compatibility, and recognizer regression suites pass 11/11. No compatibility module was restored and no production import changed.

## [Typed map evidence ingress] 2026-09-04

### A. Scope declared before reading

**Goal:** introduce a typed `MapFrameEvidence` contract and a compatibility-preserving `MapStitcher.add_evidence(...)` entry that delegates to existing `add_frame(...)`.

**Files to inspect:**

- `core/mapping/__init__.py` — mapping public-export convention.
- `tests/test_stitcher_core.py` — existing stitcher test conventions and constructor assumptions.

**Compatibility rule:** `MapStitcher.add_frame(img, match_mask, save_mask, fog_mask, raw_gray=None, player_pos=None)` must retain its signature and implementation path.

## [Input package import diagnosis] 2026-09-04

### A. Scope declared before reading

**Symptom:** importing the pure `core.input.motion_mapping` module raises `ModuleNotFoundError: pydirectinput` because Python executes `core.input.__init__` first.

**Investigation targets:**

- `core/input/__init__.py` public imports;
- `core/input/click_executor.py` optional-dependency boundary;
- dependency manifests and an existing test importing `core.input`.

**Hypothesis to test only after evidence:** a package-level eager import has accidentally made an optional real-input backend mandatory for pure coordinate math.

### C. Findings

- **(verified root cause):** `core/input/__init__.py` eagerly imports `click_executor`, which unconditionally imports `pydirectinput`; `pydirectinput` is absent from `requirements.txt` and the active environment. Thus importing any `core.input.*` submodule—including pure math—fails before use.
- **Dependency boundary failure:** `send_click()` uses pydirectinput only for its fallback backend, so it must not prevent import of `motion_mapping` or other Win32-backed paths.
- **Next evidence needed:** inspect the new action adapters' optional-device import pattern, then make one minimal lazy/guarded dependency change with a failing import regression test.

## [Input package import diagnosis — optional dependency pattern] 2026-09-04

### A. Scope declared before reading

**Goal:** compare the legacy click backend with the project’s current optional-device adapter pattern before selecting a minimal import-boundary fix.

**Files to inspect:**

- `core/actions/keyboard.py`
- `core/actions/mouse.py`
- `tests/test_keyboard_action_adapter.py`

### C. Findings

- **(verified working pattern):** `PyDirectInputKeyboardDevice` imports `pydirectinput` only in its production-device constructor; the generic `KeyboardActionAdapter` and `MouseActionAdapter` are import-safe and device-injected.
- **Confirmed hypothesis:** legacy `click_executor` violates this pattern by importing pydirectinput at module load time even though only its fallback calls need it.
- **Single fix selected:** replace the eager module import with a private lazy resolver used only by `send_click()` fallback and `fallback_pydirect_click()`. The current failing pure-motion import test is the regression case.

### C. First fix result

- **Verified partial resolution:** `click_executor` no longer imports pydirectinput at package load time.
- **New boundary revealed:** the same test now reaches `core.input.motion_controller.backend`, which has a separate eager `pydirectinput` import. This is a second occurrence of the same optional-dependency boundary violation, not a failure of the lazy fallback change.
- **Fix count:** 1. Return to root-cause inventory before making a second change.

## [Input package import diagnosis — full optional-backend inventory] 2026-09-04

### A. Scope declared before reading

**Goal:** inventory every `pydirectinput` import reachable from `core.input` and inspect the newly exposed backend before one bounded follow-up fix.

**Files/queries to inspect:**

- all executable `pydirectinput` imports;
- `core/input/motion_controller/backend.py`;
- `core/input/controller.py` composition path.

### C. Findings

- **(verified complete import inventory):** besides the now-lazy click fallback, the only eager pydirectinput imports under `core.input` are `motion_controller/backend.py` and `motion_controller/controls.py`. Both are loaded whenever package `core.input` exposes `MotionController`.
- **Refined root cause:** the package combines pure mapping exports and concrete motion-controller exports in one eager `__init__`; therefore every concrete backend must use the same lazy resolver.
- **Single second fix:** centralize the resolver in one internal module and use it at invocation time in click executor, backend, and controls. This removes all eager optional-backend imports in the package without changing controller methods or selected input backend behaviour.

## [Input package import diagnosis — controller call sites] 2026-09-04

### A. Scope declared before reading

**Goal:** inspect every pydirectinput use in controller controls before applying the shared lazy-resolver fix.

**Files to inspect:**

- `core/input/motion_controller/controls.py`
- `core/input/motion_controller/__init__.py`
- `core/input/click_pipeline.py`

### C. Findings

- **(verified call sites):** controller backend uses pydirectinput only for non-essential diagnostic size/position calls; controls uses it only when a real key press is requested. Click pipeline already handles click backend failures.
- **Verification after second fix:** all pydirectinput imports reachable from `core.input` are now lazy. Navigation projection, legacy motion mapping, typed map evidence, stitcher, and keyboard-adapter suites pass 11/11 without pydirectinput installed.
- **Full-suite audit:** 153 discovered tests ran with 7 errors and 2 skips. Six errors are stale test imports of intentionally deleted top-level core modules; one is a test loading a relative-import GUI module outside its package. These are existing migration-test issues, not image/map/action contract failures.

## [Full-suite migration-test audit] 2026-09-04

### A. Scope declared before reading

**Goal:** map the failing stale core test imports to current public package exports; preserve tests rather than resurrect deleted modules.

## [Legacy convergence — mapping session evidence migration] 2026-09-04

### A. Scope declared before reading

**Migration objective:** move the live mapping composition root from raw mask/tuple arguments to the already-implemented MapFrameEvidence → MapStitcher.add_evidence() ingress. The historical add_frame(...) path remains only as a compatibility method for external callers.

**Files to inspect:**

- gui/modes/mapping/runtime/session.py — current mapping capture and stitcher composition.
- gui/modes/mapping/runtime/__init__.py — runtime public import/lifecycle surface.
- tests/test_perception_workbench.py or mapping-session tests — existing test seams for UI-independent composition.

**Parity constraints:**

- keep the capture rectangle, frame rate, player-coordinate selection, masks, stitched layers, and GUI preview output unchanged;
- do not import Qt/GUI into core.mapping.evidence;
- first add a regression that proves the session passes exactly the current frame/masks/player position through its new evidence object.

### C. Findings

- **(verified migration seam):** MappingSession.tick() is the sole composition point that captures the minimap, chooses player coordinates, invokes recognizer.extract_combined(), obtains raw_gray, and calls stitcher.add_frame().
- **(verified parity boundary):** all values required by MapFrameEvidence already exist immediately before the legacy call: image, combined match mask, wall mask, fog mask, raw gray, and player position.
- **Implementation decision:** replace only the final raw-argument call with construction of MapFrameEvidence and add_evidence(). Capture, recognizer calls, MappingTickResult, player fallback, and GUI presentation remain byte-for-byte behaviourally equivalent.

**Files to inspect first:**

- `core/routing/__init__.py`
- `core/localization/__init__.py`
- `core/vision/__init__.py`
### C. Mapping-session migration completion findings

- **(verified):** `MappingSession.tick()` now creates one `MapFrameEvidence` using the same captured image, combined/wall/fog masks, raw grayscale image, and player position that the former `add_frame(...)` call received.
- **(verified):** center capture remains `monitor_size // 2`; region capture still uses `_detect_or_fallback_player_pos()`. No recognition parameter, frame crop, GUI preview value, or stitcher registration/merge algorithm moved.
- **(verified):** the new session regression checks object identity for all five image/mask values and confirms the existing `(width, height)` tick result, while `MapStitcher.add_evidence()` keeps the historical `add_frame(...)` ingress for external compatibility.

## [SYNC] 2026-09-04 — MappingSession typed-evidence composition

### A. SYNC scope declaration

**Trigger:** migrate the live mapping composition root from raw `MapStitcher.add_frame(...)` arguments to `MapFrameEvidence` plus `MapStitcher.add_evidence(...)`.

**Directly changed files:** `gui/modes/mapping/runtime/session.py`; `tests/test_mapping_session_evidence.py`.

**Affected boundary:** `MappingSession.tick()` → `MapFrameEvidence` → `MapStitcher.add_evidence()` → unchanged `MapStitcher.add_frame()`.

### C. SYNC result

**Re-read impact surface:** mapping session, typed evidence contract, stitcher typed ingress, focused regression, mapping implementation plan, current checkpoint and the MappingSession entry in `CODEBASE.md`.

**CODEBASE.md synchronized:** runtime-session responsibility/dependency/compatibility notes now describe the typed evidence composition boundary; the generic-vs-domain split remains explicit.

**Verification:** `python -m unittest tests.test_mapping_session_evidence tests.test_mapping_evidence tests.test_stitcher_core` passed 5/5; `python -m compileall -q core gui/modes/mapping/runtime` and scoped `git diff --check` passed.

**Next migration:** audit the localization result boundary and its navigation composition caller before introducing a tuple-compatible `LocalizationResult`; no Portal/Loot/action policy changes are included in that slice.

## [Legacy convergence — localization result boundary] 2026-09-04

### A. Scope declared before reading

**Migration objective:** identify the exact legacy localization result tuple/object, its state mutation, and the first navigation composition caller. Design a typed `LocalizationResult` compatibility bridge only if it can preserve current returned values, confidence semantics, and state updates.

**Files to inspect:**

- `core/localization/__init__.py` and its direct runtime implementation — find the exported localization contract and legacy value shape.
- `gui/modes/navigation/input/intent_executor.py` and its direct caller — identify where localization-derived navigation becomes a movement/input intent.
- focused localization/navigation regression tests — preserve the existing observable behavior before editing.

**Out of scope:** changing HSV/minimap detection parameters, path-finding policy, `MotionController`, physical input adapters, Portal/Loot logic, or any GUI layout. This slice only establishes a result schema and migrates one composition edge if a behavior-preserving caller exists.

### C. Findings

- **(verified):** `NavigationCore.localize()` delegates to `core.localization.localize_pipeline.localize_frame()` and still returns the historical three-value `(global_x, global_y, confidence)` tuple on every success and failure branch. The pipeline also mutates `NavigationCore` registration/tracking state as part of the same call.
- **(verified):** `capture_navigation_localization_tick()` is the first live caller. It immediately wraps that tuple in GUI-owned `NavigationLocalizationResult`, then passes it into the navigation-task context. This is the correct migration point; the input executor is downstream of task planning rather than a consumer of raw localization values.
- **(verified):** `core.localization.evidence.LocalizationEvidence` already models diagnostic registration evidence, but it is not a localization call result and must not be repurposed to carry GUI/runtime result semantics.
- **Corrected plan:** first introduce a core-owned result DTO plus a new typed `NavigationCore.localize_result(...)` facade that delegates exactly once to the unchanged tuple API. Keep `localize(...)` and `localize_frame(...)` untouched for external compatibility; migrate the runtime tick to the new facade and remove only its redundant GUI DTO conversion.

**Next reading round:** inspect `NavigationCore` public-method conventions and state fields, the existing diagnostic-evidence schema, `CoordinateSpace` values, and focused runtime test seams before specifying the immutable result contract.

## [Localization result contract — design read] 2026-09-04

### A. Scope declared before reading

**Goal:** choose the minimal reusable fields and compatibility protocol for a core-owned localization result without leaking GUI, input, or minimap-recognizer configuration into it.

**Files to inspect:**

- `core/localization/navigation_core/runtime.py` — current public localize facade and state-owner conventions.
- `core/localization/evidence/models.py` — distinguish diagnostic evidence from result data.
- `core/perception/models.py` — reuse the existing coordinate-space vocabulary if it correctly represents a stitched map.
- `tests/test_navigation_core.py` — protect the core caller's current tuple-unpacking behavior.

**Question:** whether typed callers can use a new method rather than changing the dynamic return type of `localize(...)`; this preserves the legacy method while making typed composition explicit.

### C. Findings

- **(verified):** `CoordinateSpace.GLOBAL_MAP` already names the exact output plane of the stitched-map position, so no new cross-cutting coordinate enum is necessary.
- **(verified):** the GUI's `NavigationLocalizationResult` duplicates only position, confidence and `is_localized`; it has no GUI-specific state. It should be replaced by a core DTO, rather than become another long-lived adapter model.
- **(verified):** `NavigationCore.localize()` is an intentionally thin facade over the stateful legacy algorithm, so a sibling `localize_result()` can call it exactly once and adapt its final tuple without duplicating or relocating HSV/template/F2F code.
- **Proposed contract:** immutable `LocalizationResult(position, confidence, coordinate_space=GLOBAL_MAP, source, metadata)`; `position=None` is the normalized non-localized state. `source`/metadata must be read from the already-written frame registration, not inferred from recognizer internals. `as_legacy_tuple()` preserves external tuple consumers.

**Next reading round:** inspect the existing frame-registration object and setter/clearer to determine its stable field names and whether failed states expose source/metadata safely for result construction.

## [Localization result contract — registration read] 2026-09-04

### A. Scope declared before reading

**Goal:** use the existing registration state as the only source of localization-result provenance; do not repeat or expose the legacy algorithm's internal decision branches.

**Files to inspect:** direct localization registration DTO and the `NavigationCore` registration facade/helper implementation.

**Decision gate:** if registration already has source, validity, confidence and metadata, `LocalizationResult` will snapshot those fields; otherwise the first adapter exposes only position/confidence/coordinate space and leaves provenance for a later compatible extension.

### C. Findings

- **(verified):** `FrameRegistration` has the required snapshot fields: `valid`, `confidence`, `player_global_pos`, `source`, `frame_size`, and mutable `metadata`. Both successful F2F/template paths and every failed `localize_frame()` branch write it through the same `NavigationCore` helper.
- **(verified):** a typed result can take `position` and `confidence` from the legacy tuple, then copy registration source/validity/metadata immediately after that single call. This adds provenance without re-evaluating or duplicating any HSV, template, F2F, rejection, or state-mutation logic.
- **Contract decision:** create `core.localization.result.LocalizationResult` with `position`, `confidence`, `coordinate_space=GLOBAL_MAP`, `source`, `registration_valid`, and copied metadata. It exposes `localized_pos`, `is_localized`, and `as_legacy_tuple()`. `NavigationCore.localize_result()` will be additive; existing `localize()` remains the tuple API.

## [Localization result contract — runtime-test read] 2026-09-04

### A. Scope declared before reading

**Goal:** write a small runtime composition regression proving that the capture tick requests the typed core facade exactly once and returns its object unchanged.

**Files to inspect:** `gui/modes/navigation/runtime/loop.py` for player-position resolution requirements and existing navigation runtime test files for the smallest UI-independent fixture convention.

**Out of scope:** editing the frame loop, intent consumer, input executor, or action adapters. The tick remains the sole live caller changed in this slice.

### C. Findings

- **(verified):** a center-capture runtime fixture needs only `screen_capture.capture(...)`, a capture geometry callback, a minimal config, and `nav_core.localize_result(...)`; no Qt, tracker, event coordinator, action adapter, or real image-recognition backend is required.
- **Test decision:** add one core-facade test that patches the unchanged tuple API and verifies one invocation plus copied registration provenance, and one runtime-tick test that verifies the typed result object passes through unchanged. Existing F2F coverage remains the behavior guard for the legacy algorithm.

## [SYNC] 2026-09-04 — LocalizationResult core facade and runtime migration

### A. SYNC scope declaration

**Trigger:** add a core-owned `LocalizationResult`, an additive `NavigationCore.localize_result(...)` facade, and migrate `capture_navigation_localization_tick(...)` from GUI result conversion to the typed core result.

**Directly changed files:** `core/localization/result.py`, `core/localization/__init__.py`, `core/localization/navigation_core/runtime.py`, `gui/modes/navigation/runtime/localization_tick.py`, `gui/modes/navigation/runtime/models.py`, `tests/test_localization_result.py`, `tests/test_navigation_localization_tick.py`.

**Expected impact chain:** `NavigationRuntimeFrameLoop.run()` → `capture_navigation_localization_tick()` → `NavigationCore.localize_result()` → unchanged `NavigationCore.localize()` / `localize_frame()`; downstream task context continues to read `localized_pos` and `confidence`.

### C. SYNC result

**Re-read impact surface:** localization tuple facade, `FrameRegistration`, navigation capture tick, downstream `localized_pos/confidence` consumer, legacy GUI compatibility DTO, focused core/runtime tests, and the corresponding CODEBASE/checkpoint sections.

**Verified behavior preservation:** `localize_result()` delegates to `localize()` exactly once. It snapshots the registration already produced by the legacy algorithm; it does not branch on image content, invoke recognizer methods, map coordinates, or emit input. The old tuple entry remains unchanged.

**Verification:** initial red tests failed only because `LocalizationResult` was intentionally absent. After implementation, `tests.test_localization_result`, `tests.test_navigation_localization_tick`, and `tests.test_navigation_core` passed 3/3; the full `test_navigation*.py` group passed 12/12; mapping evidence/stitcher regression passed 5/5; scoped compilation and `git diff --check` passed.

**CODEBASE.md synchronized:** directory map, new result module detail, runtime models/tick descriptions, function chain, navigation flow and localization-runtime migration note now show the core DTO and the retained compatibility tuple.

**Full-suite audit:** `python -m unittest discover -s tests` ran 170 tests: 166 passed, 2 skipped, and 4 failures remain outside this slice. One is a dynamic loose-file import in `tests/test_advanced_settings_file_io.py` that makes `advanced_settings/file_io.py` lose package-relative imports. Three are `PathFinder` behavior/specification conflicts: diagonal movement crosses a blocked corner, unexplored space is walkable, and a strict thin-wall expectation differs from current implementation. The migrated localization result/tick has no call-path overlap with those failures; they are recorded for their own diagnostic task rather than hidden.

**Next migration:** translate navigation intents to a device-neutral action command at the composition boundary, while leaving `MotionController` as the temporary backend adapter. Portal and Loot remain untouched until their perception/output bridge is independently regression-locked.

## [Legacy convergence — complete perception-to-action chain] 2026-09-04

### A. Scope declared before reading

**Objective:** finish the currently known Torchlight/minimap compatibility chain as a composed, testable path: legacy capture/recognition and localization → typed map/global result → navigation or event intent → device-neutral action command → mouse, keyboard, or gamepad backend. Bridge Portal and Loot perception outputs to the shared detection schema without moving their game-specific templates, filtering, temporal policy, or handler state machines into core generic modules.

**Initial files to inspect:**

- `core/actions/` public contracts and adapters — identify the actual device-neutral command vocabulary and backend capabilities.
- `gui/modes/navigation/input/intent_executor.py` plus its runtime caller — enumerate every live `NavigationIntent` to direct-input transition.
- `core/events/` public models/types and Portal/Loot detector boundaries — locate `EventDetection` production and conversion seams.
- focused navigation-intent, action, portal, and loot tests — freeze observable behavior before each bridge.

**Rules:** no GUI import may enter `core.actions`, perception, spatial, or event DTO modules; new generic contracts must not contain Torchlight resource IDs, HSV ranges, templates, pickup keys, portal policies, or route state. `MotionController` remains a compatibility backend until every current caller has migrated. Full-suite baseline failures remain separately tracked and must not be hidden.

### C. Initial chain findings

- **(verified):** `gui.modes.navigation.input.execute_navigation_intent()` is the single live transition from `NavigationIntent` to direct side effects. It directly invokes three `MotionController` families: map movement, physical screen click, and key press. `NavigationRuntimeFrameLoop` only supplies GUI callbacks and status presentation.
- **(verified):** `core.actions` already contains a broader device-neutral command vocabulary than the earlier mouse proof: pointer, keyboard, and virtual-gamepad targets plus concrete adapters. Its legacy `ActionRequest` is deliberately pointer-only and must not be expanded into a navigation/game-domain object.
- **(verified):** Portal/Loot handlers produce legacy `EventAction`, then the navigation task layer translates it to `NavigationIntent` before the GUI executor. Their detection output is `EventDetection(local_minimap_pos, ...)`, which the event position stabilizer projects through `FrameRegistration`.
- **Architecture decision:** retain the existing domain transitions (`EventAction → NavigationIntent`) and add a GUI composition adapter that turns only concrete screen/key intents into `core.actions.ActionCommand`. Map-movement intent remains a domain/spatial request for the existing `MotionController` while its mapping/execution split is audited separately. This avoids falsely treating a stitched-map target as a physical pointer command.

## [Complete chain — action contract read] 2026-09-04

### A. Scope declared before reading

**Goal:** verify `ActionCommand` target semantics and adapters, then define a navigation composition adapter that uses them without adding a GUI dependency to `core.actions` or losing current click/key behavior.

**Files to inspect:** `core/actions/contracts.py`, `core/actions/mouse.py`, `core/actions/keyboard.py`, and navigation intent/executor tests.

**Decision gate:** only introduce a `MotionController` backend adapter if the generic command target already carries enough information for physical pointer/key dispatch; map-space movement remains explicit and unmodified otherwise.

### C. Action-contract findings

- **(verified):** `ActionCommand` is a sound generic primitive contract. Pointer commands require an already-calibrated `MappedPoint` whose destination is `PHYSICAL_SCREEN`; keyboard and gamepad commands carry validated device targets. The adapters deliberately have no map/game/window awareness.
- **(verified):** the current `CLICK_SCREEN` navigation intent carries only a legacy `screen_pos`; it is not enough to fabricate a generic pointer action safely, because the contract must state whether it is a logical capture pixel, a game-window point, or a physical desktop point.
- **(verified):** `PRESS_KEY` can immediately become `ActionCommand(KEY_CHORD, KeyboardTarget(...))`, but replacing its concrete dispatch needs a composition-level keyboard device/backend that preserves current `MotionController.press_key()` behavior and its window-input policy.
- **Corrected implementation order:** before changing the executor, inspect the existing `MotionController` click/key coordinate and backend behavior plus the existing desktop mapping factory. Then add an explicit legacy-navigation action request/dispatcher at the GUI boundary. It will preserve `MOVE_MAP` as a map-domain command, map a declared screen coordinate to `PHYSICAL_SCREEN` before forming pointer commands, and dispatch only primitive commands through the generic adapters.

## [Complete chain — legacy input and spatial read] 2026-09-04

### A. Scope declared before reading

**Goal:** identify the precise source coordinate spaces and side effects of legacy navigation screen click/key/move operations, and reuse the existing desktop-mapping contract rather than treating raw tuples as physical coordinates.

**Files to inspect:** `core/input/controller.py` or its concrete `MotionController` methods, `core/spatial/desktop_mapping.py`, the desktop action composition/proof, and the `NavigationIntent` model.

**Decision gate:** if the legacy executor's `screen_pos` is already physical desktop space, add an explicit identity mapping adapter with validation; if not, compose through existing calibration. Do not change behavior merely to fit an action DTO.

### C. Legacy input/spatial findings

- **(verified):** map movement is semantically distinct from primitive pointer input: `MotionController.move_to_map_target()` applies global-map direction projection, click-radius policy, bottom-UI guard, and its own real-input pipeline. It must remain a domain/spatial action until that mapping boundary is separately decomposed.
- **(verified):** generic `ActionCommand` currently lacks a one-click kind, while legacy `CLICK_SCREEN` performs exactly one click. Adding `ActionKind.CLICK` is a genuine generic contract gap; overloading double-click would change behavior.
- **(verified):** legacy direct screen click and key press are routed through the same `MotionController` controls, which enforce `control_enabled` and preserve existing focus/backend policy. The correct first backend bridge is therefore an adapter over those existing methods, not a second independent OS input route.
- **Implementation decision:** add generic single-click support, an explicit validated physical-screen identity mapping helper, and an interim `MotionControllerActionAdapter` that executes primitive `ActionCommand`s through the old controller. At the navigation composition edge, translate `MOVE_MAP` into a typed map-movement request and `CLICK_SCREEN`/`PRESS_KEY` into generic primitive commands. This creates one complete typed chain without pretending map coordinates are desktop pixels.

## [Complete chain — input semantics and tests] 2026-09-04

### A. Scope declared before reading

**Goal:** freeze the observable single-click/key behavior and verify the source of legacy event screen coordinates before adding the generic action bridge.

**Files to inspect:** `core/input/motion_controller/controls.py`, Portal/Loot handler interaction modules that construct `EventAction.click_screen` or `EventAction.press_key`, and existing input/navigation test locations.

**Expected regression contract:** disabled control produces no physical action; enabled direct click remains one click at the same physical coordinates; enabled key press retains its existing duration/backend path; `MOVE_MAP` is not converted into a desktop-pointer command.

### C. Input-semantics findings

- **(verified):** the current Portal and Loot handlers emit `EventAction.press_key(...)` only: Portal uses `d`; Loot uses the configurable pickup key. They do not create a direct-screen-click action today. Their key/action policy remains in the handlers and is not moved into the generic action package.
- **(verified):** `MotionController.click_screen_position()` passes its integer tuple to the controller's physical click pipeline unchanged; `MotionController.press_key()` enforces `control_enabled`, normalizes a key and delegates to the existing lazy PyDirectInput backend. Both are suitable temporary backend methods for typed primitive commands.
- **(verified):** navigation event hooks separately call `MotionController.press_key()` and must use the same new primitive-command dispatcher; otherwise the old direct-input escape hatch would remain.
- **Plan:** implement the action bridge in three guarded layers: generic `CLICK` + physical-point constructor; `MotionControllerActionAdapter` as a compatibility action backend; navigation/hook composition translators. Then create a pure EventDetection↔TargetDetection adapter and wire Portal/Loot detector outputs through it at the event monitor boundary. This makes all presently active old paths observable through common schemas while preserving the event state machines.
## [Complete chain — primitive action slice] 2026-09-04

### A. Scope declared before reading

**Goal:** implement Tasks 1–2 of the approved complete-chain plan: generic single click, explicit physical point construction, and an interim `MotionController` backend adapter with no navigation/event imports.

**Files to inspect:** `core/spatial/__init__.py`, `core/spatial/models.py`, current generic action test files, and `core/input/__init__.py` export conventions.

**Compatibility rules:** `ActionRequest` retains its historical move/double-click restriction; `MouseActionAdapter` gains click behavior only through `ActionCommand`; `MotionControllerActionAdapter` delegates to old public controller methods and never imports GUI, navigation task, Portal, or Loot modules.

### C. Primitive-action implementation findings

- **(verified):** `MappedPoint` already carries both source and destination coordinate spaces, and `Point2D` is the only additional spatial DTO needed. A `physical_screen_point()` constructor can safely mark a pre-existing physical point as an explicit identity mapping without pretending it came from an image calibration.
- **(verified):** `ActionResult` supports successful and deliberately skipped dispatch (`executed=False`) with command/target metadata, so disabled legacy control can be represented without raising or changing existing `MotionController` behavior.
- **Test plan:** extend the generic action and mouse tests for one click, add physical-identity mapping coverage, and add a fake-controller backend test for click/key success, disabled skip, and command-kind rejection. The tests must fail until the new primitive and adapter exist.

## [SYNC] 2026-09-04 — primitive actions and MotionController backend

### A. SYNC scope declaration

**Trigger:** add generic `CLICK`, physical-screen identity mapping, and `MotionControllerActionAdapter` as the compatibility backend for physical click and one-key commands.

**Directly changed files:** `core/actions/contracts.py`, `core/actions/mouse.py`, `core/spatial/desktop_mapping.py`, `core/spatial/__init__.py`, `core/input/action_adapter.py`, `core/input/__init__.py`, and focused action/spatial/controller tests.

**Impact chain:** `ActionCommand(CLICK|KEY_CHORD)` → validated `PointerTarget`/`KeyboardTarget` → `MouseActionAdapter` or `MotionControllerActionAdapter` → existing device or `MotionController` control policy.

### C. SYNC result

**Re-read impact surface:** generic action validation, generic mouse dispatch, spatial mapped-point semantics, `core.input` public exports, existing MotionController direct click/key policy, and their focused regressions.

**Verified behavior:** `CLICK` is a new generic command only; legacy `ActionRequest` still rejects it. The direct physical-point helper is explicit identity mapping, never desktop-frame mapping. The compatibility backend calls the historical `MotionController` public methods and records a skipped result when those methods decline disabled input.

**Verification:** initial red tests failed because `CLICK`, `physical_screen_point`, and the backend adapter were absent. After implementation, action/spatial/controller suites passed 14/14; existing public-action, keyboard, and gamepad suites passed 8/8; compilation and scoped diff checks passed.

**CODEBASE.md synchronized:** input/action/spatial inventory and module details now describe the single-click primitive, declared physical coordinates, and temporary controller backend.

## [Complete chain — navigation action composition] 2026-09-04

### A. Scope declared before reading

**Goal:** implement Task 3: make the live navigation executor and event-key hooks translate intents to typed composition actions, dispatch primitive actions through `MotionControllerActionAdapter`, and retain map movement through its explicit legacy spatial backend.

**Files to inspect:** `gui/modes/navigation/hooks/registration.py`, `tests/test_navigation_compact_actions.py`, and navigation task event-action conversion code that creates `CLICK_SCREEN` / `PRESS_KEY` intents.

**Compatibility rules:** intent `message` remains the human/audit reason; map click selection and `record_intent_click()` timing remain unchanged; missing `screen_pos`/key stays a no-op; only `CLICK_SCREEN` is declared existing `PHYSICAL_SCREEN` input at this compatibility boundary.

### C. Navigation-composition findings

- **(verified):** `core.navigation_tasks.intent_factory` is the sole event-action conversion boundary. It preserves `EventAction` in metadata and passes raw `screen_pos`/key forward, so the GUI input adapter is the correct place to assign the legacy direct-click coordinate-space declaration without contaminating events.
- **(verified):** `NavigationHookRuntime._press_key_once()` has a separate direct key path, explicitly turns control on, and returns its backend result to the hook instance. It can use the same one-key `ActionCommand` bridge without changing core hook registration or event semantics.
- **Implementation decision:** add `gui.modes.navigation.input.actions` as the domain-to-composition translator. It has an explicit `MapMovementAction` for stitched-map intent and a `PrimitiveNavigationAction` wrapping an `ActionCommand`; it is not a generic core module. Update the executor/hook runtime to consume it and permit an injected adapter in tests.
- **Regression plan:** a pure translator test locks coordinate declaration and no-op behavior; executor tests lock map direct-method selection, click/key command shape/reason, and click-record timing; hook tests lock that key hooks use the common primitive backend.

## [SYNC] 2026-09-04 — navigation intent and hook action composition

### A. SYNC scope declaration

**Trigger:** add explicit navigation composition actions and migrate live `CLICK_SCREEN` / `PRESS_KEY` intent dispatch plus navigation key hooks to `ActionCommand` and `MotionControllerActionAdapter`.

**Directly changed files:** `gui/modes/navigation/input/actions.py`, `gui/modes/navigation/input/__init__.py`, `gui/modes/navigation/input/intent_executor.py`, `gui/modes/navigation/hooks/registration.py`, and focused navigation intent/hook tests.

**Impact chain:** `EventAction` → unchanged `NavigationIntent` → `translate_navigation_intent()` → `MapMovementAction` or `PrimitiveNavigationAction` → `MotionController` map policy or `MotionControllerActionAdapter` → legacy input backend.

### C. SYNC result

**Re-read impact surface:** navigation intent factory payload shape, executor map-click branch, Hook runtime key dispatch, generic primitive contract/backend, and focused non-GUI regressions.

**Verified behavior preservation:** the executor retains the legacy map movement methods, force-click selection, input enablement, click-record timing, status suffix, and absent payload no-op behavior. Click/key actions now receive explicit typed commands and route through the existing `MotionController` methods, so they keep legacy control-enable and platform policy. Key hooks use the same backend after their pre-existing explicit enablement.

**Verification:** initial translator/hook tests failed before the new composition module and injected adapter existed; after implementation, 6 focused tests passed. `compileall` and scoped diff checks passed.

**CODEBASE.md synchronized:** navigation input inventory, executor/hook responsibilities, full compatibility flow, and current-risk statement now distinguish map-space movement from physical primitive dispatch.

## [Complete chain — event perception schema bridge] 2026-09-04

### A. Scope declared before reading

**Goal:** implement Tasks 4–5: define a pure, reversible EventDetection ↔ TargetDetection bridge and identify the event monitor composition point that can run legacy Portal/Loot output through it without modifying detector algorithms or handler state machines.

**Files to inspect:** `core/events/models.py`, `core/events/monitor.py`, `core/events/types/portal/minimap_detection/conversion.py`, and `core/events/types/loot/detection/conversion.py`.

**Contract:** `EventDetection.local_minimap_pos` maps only to `TargetDetection(center, coordinate_space=MINIMAP)`; event type, confidence, timestamp and all existing metadata must survive a copied conversion. Generic detections in any other coordinate space must be rejected before event stabilization/projection.

## [Complete chain — event bridge implementation] 2026-09-04

### A. Scope declared before reading

**Goal:** finish the approved Portal/Loot perception-schema seam and run the full compatibility-chain audit. The bridge must pass each legacy `EventDetection` through the generic `TargetDetection` contract at the `EventMonitor` composition point, retain the legacy event returned to stabilization/memory/handlers, and expose a copied generic observation list for later UI/debug or new perception producers.

**Files to inspect:** `core/events/models.py`, `core/events/monitor.py`, Portal/Loot conversion modules, shared perception DTOs, and event-monitor tests.

**Acceptance rules:** the bridge is pure and reversible for minimap detections; coordinate-space mismatch is rejected explicitly; metadata has no shared mutable reference; detector algorithms, Portal/Loot configuration, handler state, and `EventPositionStabilizer` behavior are unchanged. After focused tests, run the complete suite and document any pre-existing failures separately from this work.

### C. Event-bridge findings and implementation result

- **(verified):** Portal and Loot detector outputs share a single live composition seam in `EventMonitor.detect()`. Normalizing there makes the shared perception contract active in both runtime paths without putting game templates, HSV rules, pickup keys, timing, or handler state into `core.perception` or the bridge.
- **(verified):** `EventDetection.local_minimap_pos` maps losslessly to `TargetDetection.center` in `MINIMAP`; event type is deliberately a required explicit input for the reverse direction, so an arbitrary generic target cannot silently enter an event state machine.
- **(verified):** deep-copied metadata protects both detector output and `EventMonitor.last_target_detections` from nested-mutation leaks. Valid legacy bbox/text are exposed through standardized fields while raw metadata stays intact for a round trip.
- **Corrected scope statement:** the completed bridge is a runtime-schema migration, not a replacement of Portal/Loot algorithms with `PerceptionEngine`. Their existing detector packages remain the tested compatibility implementations; a future provider-backed replacement can enter the same reverse bridge deliberately.
- **Regression result:** 43 focused mapping/localization/navigation/action/event tests pass. The full discovery suite now contains 197 tests: 191 pass, 2 skip, 3 `PathFinder` specification failures, and 1 advanced-settings loose-import error. The four failures match the pre-existing audit categories and do not import the new event bridge or action-composition modules.

## [SYNC] 2026-09-04 — complete legacy perception-to-action chain

### A. SYNC scope declaration

**Trigger:** introduce the reusable event-perception adapter and connect the last active Portal/Loot output seam after the previously completed mapping evidence, localization result, and navigation/action composition slices.

**Directly changed files:** `core/events/perception_adapter.py`, `core/events/monitor.py`, `core/events/__init__.py`, event-bridge tests, and the affected architecture/checkpoint documents. This final slice is composed with the already modified generic action, spatial, input, navigation input, and hook files in the approved plan.

**Impact chain:** legacy Portal/Loot detector → `EventDetection` → `TargetDetection(MINIMAP)` → independent `EventDetection` → unchanged `EventPositionStabilizer` → `EventMemory`/`EventTask` → `EventAction` → `NavigationIntent` → typed map request or `ActionCommand` → existing MotionController/device policy.

### C. SYNC result

**Re-read impact surface:** shared perception DTO coordinate rules, EventMonitor detector cache/output ordering, position stabilization, memory task creation, generic action backend, navigation intent execution, and hook key dispatch.

**CODEBASE.md synchronized:** directory inventory now lists the perception adapter; event module notes and function index specify both conversion contracts and the monitor composition step; the integration-flow/risk note now records that the schema bridge is complete rather than pending.

**Verification:** event bridge tests 5/5; end-to-end compatibility focus set 43/43; `compileall -q core gui tests` and `git diff --check` pass. Full discovery is 191 passed, 2 skipped, 3 known PathFinder failures, and 1 known advanced-settings loader error out of 197 tests.

**Next work is intentionally separate:** P4 feature/motion/ML provider adapters, P5 game-window/viewport calibration controls, P6 workbench GUI composition, P8 concrete workflows (including the later PoE scenario), and a dedicated diagnosis/fix decision for the four independent full-suite baseline failures.

## [Primary-monitor capture default] 2026-09-04

### A. Scope declared before implementation

**Goal:** make the application's screenshot-localization default capture only the Windows primary monitor and map recognition coordinates to that same monitor's physical rectangle. Preserve virtual-desktop capture only as an explicit reusable provider choice.

**Verified non-compliance:** `DesktopFrameSource()` currently defaults to `WindowsDesktopGeometryProvider`, whose `current_geometry()` reads `SM_X/Y/CX/CYVIRTUALSCREEN`; the OCR action proof therefore captures the full virtual desktop by default.

**Files in scope:** `core/platform/desktop_frame_source.py`, its focused frame-source tests, OCR-action composition coverage, and the perception checkpoint/codebase notes. The change must not affect minimap capture or any caller that explicitly injects a geometry provider.

### C. Primary-monitor default implementation result

- **(verified):** the prior no-argument composition selected `WindowsDesktopGeometryProvider`, which reads `SM_X/Y/CX/CYVIRTUALSCREEN`; this was the exact cause of the unintended multi-monitor capture.
- `WindowsPrimaryMonitorGeometryProvider` now reuses the established Windows DPI-awareness bootstrap and reads only `SM_CXSCREEN` / `SM_CYSCREEN`, returning the primary monitor's physical rectangle at `(0, 0)`.
- `DesktopFrameSource()` now uses that primary-monitor provider by default. It still accepts any injected `DesktopGeometryProvider`, and `WindowsDesktopGeometryProvider` remains exported as the intentional all-monitor option. No recognition algorithm, coordinate mapper, action adapter, minimap capture, or legacy navigation caller was changed.
- Regression coverage proves both the primary metrics/physical geometry and the no-argument composition choice. The pre-existing injected negative-origin virtual-desktop test remains intact, so the generic multi-monitor route is protected too.

## [SYNC] 2026-09-04 - primary-monitor capture default

### A. SYNC scope declaration

**Trigger:** screenshot localization must use the Windows primary monitor only, while preserving the reusable virtual-desktop provider for an explicitly selected multi-monitor workflow.

**Directly changed files:** `core/platform/desktop_frame_source.py`, `core/platform/__init__.py`, `tests/test_desktop_frame_source.py`, and the affected architecture/checkpoint records.

### C. SYNC result

**Impact chain:** `utils/run_desktop_ocr_action_proof.py` -> `DesktopFrameSource()` -> `WindowsPrimaryMonitorGeometryProvider` -> primary-monitor `ScreenGeometry` -> capture -> `FULL_SCREEN` detection -> `DesktopCoordinateMapper` -> `PHYSICAL_SCREEN` mouse action. An explicit `WindowsDesktopGeometryProvider()` remains the alternate all-monitor geometry source.

**Verification:** the focused source/mapping/OCR-workflow suite passes 7/7; `compileall -q core/platform core/spatial workflows utils`, public platform imports, and `git diff --check` pass. A read-only live `DesktopFrameSource().capture()` produced a `2560 × 1600` image with matching primary physical geometry `(0, 0, 2560, 1600)` at 150% DPI; it did not invoke OCR, mouse movement, or clicking.

**Full-suite audit:** `python -m unittest discover -s tests` ran 210 tests: 203 passed, 2 skipped, 3 pre-existing `PathFinder` policy assertion failures, and 2 unrelated test-loader errors. One loader error is the existing advanced-settings loose-module import; the other is `test_wall_version_storage`, which imports a map-editor version-storage module not present in this worktree. Neither failure imports the changed platform/frame-source files.

## [POE-MAP-DEVICE-PROBE] 2026-09-05

### A. Scope

Temporary, repository-external probe for the approved PoE flow: primary-screen
capture → RapidOCR target selection → fixed player anchor `(1335, 850)` →
short Xbox left-stick pulse → recapture/feedback → interaction gate → A.

### C. Result

- The probe now uses adaptive pulse timing, progress estimation, explicit stick
  neutralization, Y-axis inversion matching the host (`LeftY=+` is up), and a
  no-progress stop condition. Its target text matching handles both simplified
  and traditional `地图装置` output and removes OCR whitespace.
- Offline probe tests pass **4/4**: main-label selection over minimap duplicate,
  axis sign, progress/speed update, and dry-run action isolation.
- Live dry-run succeeded on the primary monitor (`2560×1600`): detected
  `地圖裝置` at approximately `(1721.94, 214.10)`, anchor delta
  `(386.94, -635.90)`, distance `744.37 px`, confidence `0.998978`; no input
  was sent.
- Live execution was intentionally not started because the named pipe rejected
  the non-elevated Python process (`Errno 5 Access Denied`). No joystick or A
  command was delivered. The probe now reports this as `input_unavailable` JSON.
- A later elevated run without `--start-controller` reached the action loop while
  Controller 1 was still paused; its commands were therefore neutralized by the
  host and must not be used as evidence that the game rejected joystick input.
  The first elevated run with temporary controller startup found no OCR target
  before the pulse, so it also sent no movement.
- The probe now holds maximum-strength stick values with periodic refreshes for
  the full pulse and explicitly neutralizes afterward; this behavior is covered
  by the offline tests.

The next checkpoint is to rerun the external probe from a terminal with the
same administrator level as the VirtualGamepad host, first with one short pulse
and then with the bounded full loop. The formal core and GUI remain unchanged.

## [POE-MAP-DEVICE-SMOOTH-MOTION] 2026-09-05

### A. Root-cause investigation

- Live trace completed six movement corrections in about 22 seconds. Each
  correction published a 150 ms full-strength pulse, then waited for the next
  full-screen capture/OCR cycle.
- Primary-screen capture took about 60-190 ms, while RapidOCR on the full
  2560x1600 frame took about 1.6-2.8 seconds. The previous 450 ms route TTL
  therefore expired during recognition and the host returned the stick to
  neutral between corrections. This explains the visible stop/start motion.

### C. Implementation and verification

- Added the device-neutral `core.actions.StickSlewLimiter`, which transitions
  two-axis stick values at a bounded rate and supports immediate neutral reset.
- The external PoE probe now uses the limiter for direction changes and runs a
  short stick lease refresher during capture/OCR. It leaves the current command
  active between frames, stops the lease before A or any exit path, and then
  neutralizes/resets the controller.
- Focused verification: gamepad motion tests 3/3, existing gamepad/action tests
  13/13, and external PoE probe tests 6/6. Python compilation and diff checks
  pass.
- Full discovery still reports the existing baseline issues: three Pathfinder
  policy assertion failures and one advanced-settings loose-import error; no
  failure imports the new motion module.

## [SYNC] 2026-09-18 - repository layout migration

### A. SYNC scope declaration

**Trigger:** reorganize the repository around bottom-up reusable layers, separating
Python source, UI, external adapters, independent services, resources, writable
data, tools, documentation, and packaging while preserving the verified runtime
behavior.

**Directly changed areas:** root `core/`, `gui/`, `virtual_gamepad/`,
`lan_input_sync/`, `distribution/`, `installer/`, `assets/`, `configs/`,
`map_data/`, `debug/`, `utils/`, `workflows/`, scattered root documentation,
tests that import moved modules, and the root bootstrap entry point.

**Expected propagation:** all Python imports must use the `auto_modules` package;
runtime resource/data lookup must use one path API; C# `ProjectReference` values,
launcher paths, installer payload paths, packaging manifests, test discovery, and
developer commands must follow the new layout. Real input and LAN synchronization
remain disabled during migration verification.

**Protected checkpoint:** annotated tag `pre-reorg/2026-09-18` points to
`be698389ac3ab640fb5f2a1b4324236cc24e5cb1`.

## [SYNC] 2026-09-18 - repository layout and adapter-boundary cleanup

### A. SYNC scope declaration

**Trigger:** continue the approved repository layout migration, correct remaining
imports and physical paths, and make the bottom-up generalization rule true in
the moved action/follow/Host code.

**Directly changed files:**

- `README.md`, `ARCHITECTURE_GUIDE.md`, `CODEBASE.md`
- `packaging/distribution/README.md`, `packaging/distribution/verify_install.ps1`, `packaging/installer/README.md`
- `services/virtual_gamepad/README.md`, `services/virtual_gamepad/docs/acceptance.md`, `services/lan_input_sync/README.md`
- `services/virtual_gamepad/launcher/src/VirtualGamepadLauncher/LauncherPaths.cs` and its tests
- `src/auto_modules/core/actions/keyboard.py`, `src/auto_modules/core/actions/__init__.py`
- `src/auto_modules/core/lan_follow/`, `src/auto_modules/adapters/input/`, `src/auto_modules/adapters/host/`, `src/auto_modules/adapters/virtual_gamepad/`
- `src/auto_modules/application/follow/`, `src/auto_modules/application/event_workbench/service.py`
- affected Python tests and `tools/virtual_gamepad/run-demo.ps1` / `live_gamepad_probe.py`

**Expected propagation:** production imports, C# launcher root calculations,
installer verification data directories, action/follow adapter boundaries,
CODEBASE current-path references, and current developer commands.

**Safety boundary:** no real Host process, keyboard/mouse/virtual-controller
input, or LAN synchronization was started.

### C. SYNC result

**Verified changes:**

- The independent launcher now derives `AutoModulesRoot` from
  `services/virtual_gamepad`, derives `SourceRoot` from that repository root,
  and retains `.venv`/workspace .NET lookup under the parent workspace. This
  removes the one-level path drift introduced by the service move.
- `PyDirectInputKeyboardDevice`, `ProgramGamepadOutput`, Host-compatible clock,
  and `FollowTransport` are concrete adapters. `core.actions` and
  `core.lan_follow` now expose only device-neutral contracts and algorithms.
- Follow service consumes `HotkeyTriggerSource`; it no longer reads Win32 key
  state directly. Host/LAN wire translation remains in adapters.
- Packaging docs and verification now use `packaging/...`, `services/...`, and
  writable `data/maps`; current README and Architecture Guide describe the
  actual `src/auto_modules` layout and import policy.
- `CODEBASE.md` now includes the physical-path mapping, new modules/contracts,
  startup/share/payload flows, external integration details, and migration
  risks. Historical logical references remain explicitly mapped instead of
  being mistaken for current root directories.

**Verification:**

- `python -m compileall -q src tests tools packaging`: passed.
- Focused migration/adapter/UI/path/distribution suite: **27 passed**.
- Full Python suite: **407 passed, 1 skipped, 10 subtests passed, 3 known
  Pathfinder policy failures** (`tests/test_pathfinder.py`); the three failures
  reproduce the pre-migration behavior and were not changed in this sync.
- Active-source old-import scan: zero `from/import core`, `gui`, `workflows`,
  or `logging_system` matches.
- Core upward-dependency scan: zero imports from `application`, `adapters`,
  `ui`, or `bootstrap`; concrete OS/device dependency scan: zero matches.
- `git diff --check`: passed (only repository line-ending normalization
  warnings).
- C# build/test: not run because this machine has .NET runtime 6.0.23 but no
  installed .NET SDK. Real input, Host, LAN, and game verification remain
  opt-in and were not run.

**Coverage update:**

| File/group | Previous | Current | Evidence |
|---|---|---|---|
| `src/auto_modules/paths.py` | migrated | verified | focused runtime-path tests and payload smoke path assertions |
| `src/auto_modules/core/actions/keyboard.py` | migrated | verified | generic adapter has no concrete PyDirectInput implementation |
| `src/auto_modules/adapters/input/keyboard_device.py` | new | verified | fake-module contract and compile/import checks |
| `src/auto_modules/adapters/virtual_gamepad/program_output.py` | new | verified | lease/TTL/slew tests pass without Host connection |
| `src/auto_modules/core/lan_follow/models.py` | new | verified | immutable position/event contract imports and worker tests |
| `src/auto_modules/adapters/host/follow_transport.py` | new | verified | TTL/IPC-delay/expired-event tests pass with fake client |
| `src/auto_modules/application/follow/service.py` | migrated | verified | follow service suite and adapter hotkey injection |
| `LauncherPaths.cs` + tests | migrated | static verified | source/test path assertions; SDK unavailable for compilation |
| `README.md`, `ARCHITECTURE_GUIDE.md`, `CODEBASE.md` | stale | synchronized | current physical layout, contracts, flows and risks added |

**Revised prior conclusion:** the initial migration audit treated all remaining
`core` action/follow files as generic after their move. Re-reading their bodies
showed that PyDirectInput, Win32 clock and Host/LAN wire calls were still concrete
side effects; those implementations now live in adapter modules while core
contracts remain reusable.

**Next work:** run the C# test matrix in a machine with .NET 8 SDK, then handle
the three independent Pathfinder policy failures in a separate behavior-focused
task. Do not use the migration tag as a substitute for that diagnosis.

## [SYNC] 2026-09-18 - post-reorg active-path audit

### A. SYNC scope declaration

**Trigger:** resume work from the completed layered repository layout before
planning the PoE2 live-terrain page. Confirm the current checkout is based on
`0c507ef`, audit active code/tool/ProjectReference/test/document paths, and do
not revive the pre-reorganization root layout.

**Baseline:** `HEAD` is `0c507ef` on `feat/offline-installer`; no pre-existing
working-tree changes were overwritten. The protected tag name
`pre-reorg/2026-09-18` remains untouched. The local tag currently resolves to
`c9e96c7891d029d9593f8fa9aa21a753ea56352e`, which differs from the handoff's
reported object `be698389`; this discrepancy is recorded without rewriting the
tag.

**Directly changed files:**

- `src/auto_modules/adapters/perception/rapidocr_models.py`
- `tools/probes/install_perception_ocr_model.py`
- `CODEBASE.md`
- `docs/PERCEPTION_ENGINE_CHECKPOINT.md`

The C# Host `ProjectReference` was checked against the filesystem and kept at
`../../../../lan_input_sync/...`, which correctly resolves to
`services/lan_input_sync/...` from the new `services/virtual_gamepad/...`
location; no source change was needed there.

### C. SYNC result

- Active production Python imports are `auto_modules.*`; no `from/import core`,
  `gui`, `workflows`, or `logging_system` imports remain in `src`, `services`,
  `tools`, or `tests`.
- The RapidOCR model error message and current checkpoint/CODEBASE entries now
  point to `tools/probes/install_perception_ocr_model.py` and
  `resources/assets/perception_models/`, matching the reorganization.
- Historical plans and archived architecture documents retain their original
  paths intentionally; they are historical records, not executable current
  instructions.
- CodeGraph confirms the current UI extension point remains
  `src/auto_modules/ui/main_window.py` -> `MainWindow.setup_ui()` /
  `QStackedWidget`, while offline map loading remains separate from the live
  PoE2 business adapter. The new feature must be planned against these current
  paths only.

**Verification:**

- `python -m compileall -q src tests tools packaging`: passed.
- `python -m pytest tests/test_perception_rapidocr_models.py -q`: **7 passed**.
- `python -m pytest tests/virtual_gamepad_scripts/test_start_virtual_gamepad.py tests/virtual_gamepad_scripts/test_live_gamepad_probe.py -q`: **6 passed**.
- `git diff --check`: passed; only existing LF/CRLF normalization warnings remain.
- No real Host process, game, input, or LAN synchronization was started.

## [SYNC] 2026-09-19 - PoE2 实时地形预览第一阶段

### A. SYNC 范围声明

**触发任务：** 按底层通用能力、上层业务组合的设计规则，完成 PoE2
实时地形的第一阶段：初始化、手动抓取、校验、内存转换和只读展示。

**边界：** 不改造离线绘图地图包，不接入自动跟随、玩家定位、路径规划、
动态障碍、Xbox/虚拟手柄、Host 或 LAN；真实游戏采集保持显式手动操作。

### B. 直接变更

- `src/auto_modules/adapters/poe2_live_terrain/`：正式运行时适配器，包含
  外部 `live_preview.py` 命令边界、native `yx` 网格转换、不可变快照契约和
  进程内存储。
- `tools/experiments/poe2_live_terrain/`：只保留到正式适配器的兼容导出，
  避免实验目录和运行时出现两套实现。
- `src/auto_modules/ui/modes/poe2_live_terrain/`：注入式页面、状态控制、
  metadata 展示和 `ScalableMapWidget` 只读渲染。
- `src/auto_modules/ui/main_window.py`：追加独立第 8 个页面，保持既有页面
  索引不变；关闭时只清理本页内存状态。
- 新增适配器契约、native grid、内存服务、presenter、页面和主窗口聚焦测试。

### C. 验证与安全边界

- `Poe2CaptureAdapter` 只接受 `tool=manual-live-terrain-capture` 的新 manifest，
  拒绝 checkpoint、失败命令、未变化旧 manifest，以及逃出 producer output 的
  NPZ 路径。
- NPZ 以 `allow_pickle=False` 读取，数组保持原生 `height x width` / `yx` 方向，
  进入 `TerrainSnapshot` 后复制并设为只读；失败抓取会先清除旧快照。
- 当前已通过 PoE2 页面、适配器、契约、转换、内存服务和主窗口聚焦测试；最终
  compileall、组合测试及 `git diff --check` 在本轮收尾时重新执行。
- 本轮未启动 PoE2、Host、LAN 或任何真实输入；真实游戏内效果仍需显式验收。

## [SYNC] 2026-09-19 - PoE2 手动测试运行链路与日志

### A. 本轮增量

- `logging_utils.py` 为 PoE2 边界建立独立日志文件：
  `data/logs/poe2_live_terrain.log`。
- 采集命令、会话状态、manifest 校验、NPZ 转换、内存替换、UI 操作、
  测试归档和异常均记录为带 `step=` 的日志事件。
- 新增显式 `TerrainDebugArchive`，主窗口临时注入到
  `data/poe2_live_terrain_test/`，保存转换后的 `latest.npz` 和
  `latest.json`；页面渲染仍只读取本次内存快照。
- 主窗口已经启动并保持运行，未自动触发 PoE2 初始化或采集。

### B. 验证

- `python -m compileall -q src tests tools packaging`：通过。
- PoE2 适配器、归档、页面、主窗口和既有地图页面组合测试：**20 passed**。
- Serena 诊断：新增服务和归档逻辑无业务类型错误；PySide6/NumPy 的提示是
  Serena 当前解释器未加载项目运行时依赖，实际测试环境已通过。
- 未启动 PoE2、Host、LAN 或真实输入；用户可在已启动窗口中手动验证完整链路。

## [SYNC] 2026-09-19 - 原生地形转旧绘图视觉格式

### A. 发现

实际 `latest.npz` 的 `known_mask/explored_map` 覆盖整个原生矩形，不能直接沿用
旧地图的“已探索区域”渲染，否则包围矩形会整块变成白色。原生契约中真正代表
地图形状的是 `cell_state == 1` 的可行走区域；`cell_state == 0` 同时包含内部
阻挡和区域外背景。

### B. 实现

- `presenter.py` 现在以已知可行走格作为深灰底面。
- 使用显式黑色 padding 的形态学边界生成白色轮廓，保留房间/通道内部边界，
  区域外和未知格保持黑色。
- 原始 `TerrainSnapshot`、内存快照和本地归档数组均不变，转换只发生在 UI
  展示适配器。

### C. 验证

- 使用当前 `data/poe2_live_terrain_test/latest.npz` 生成的预览已经呈现为图一
  的黑底、灰面、白色轮廓风格。
- presenter、页面、适配器、归档和会话测试：**18 passed**。
- `compileall`：通过；主窗口已重启并加载新 presenter。

## [SYNC] 2026-09-19 - PoE2 单人定位、独立监控与轨迹显示

### A. SYNC 范围声明

**触发任务：** 完成 PoE2 单人实时定位验证链路：从 native terrain 构建定位参考，
识别小地图人物真实局部坐标，首帧全局匹配、后续局部跟踪和恢复，在完整地图上
显示人物 marker/轨迹；同时落实 PoE2 独立监控配置边界。

**直接变更文件：**

- `src/auto_modules/core/localization/`：观测契约、全局/局部状态机和确认轨迹（前一批次已完成，本轮复核其调用边界）。
- `src/auto_modules/core/spatial/monitor_binding.py`、`src/auto_modules/core/spatial/__init__.py`：通用截图矩形契约。
- `src/auto_modules/adapters/poe2_live_terrain/monitor_config.py`、`monitor_source.py`、`__init__.py`：PoE2 独立配置与区域截图适配。
- `tools/experiments/poe2_live_terrain/terrain_reference.py`、`calibration.py`、`player_policy.py`、`runtime.py`、`__init__.py`：PoE2 业务组合和默认 HSV/模板适配。
- `src/auto_modules/ui/modes/poe2_live_terrain/page.py`、`presenter.py`、`monitor_dialog.py`：页面监控生命周期、预览、状态、marker/轨迹和独立配置窗口。
- `src/auto_modules/ui/main_window.py`：组合根注入 PoE2 runtime、截图源和配置存储。
- `tests/`：新增引擎、配置、运行时和 UI 聚焦覆盖。

**预计连带影响：** PoE2 主窗口第 8 页和关闭生命周期；`TerrainSnapshot` 捕获后新增
定位参考转换；不修改 `NavigationCore`、`NavConfig`、导航页、Gamepad/LAN、Host 或输入适配器。

### B. 影响扩散与本轮发现

- `(verified)` `build_reference()` 只消费 `TerrainSnapshot.cell_state/known_mask`，
  生成不可变 `walkable_mask/wall_layer/explored_map`；UI `QPixmap` 不进入定位链路。
- `(verified)` `select_single_player()` 对高于阈值的候选要求恰好一个；无候选或多候选
  都返回 `None`，因此不会以小地图中心伪造人物位置。
- `(verified)` `Poe2LocalizationRuntime.tick()` 的顺序是 capture -> observation ->
  单人选择 -> `MapLocalizer.update()` -> 仅 fresh 结果追加 `TrajectoryBuffer` -> 发布
  `Poe2LocalizationState`；失败原因包含 `player_not_detected`、`local_match_failed`、
  `global_match_failed` 等。
- `(verified)` 首帧 `_global_match()` 在完整 terrain reference 上匹配，后续 `_local_match()`
  只在预测人物附近的显式半径内匹配；`MapLocalizer` 在局部失败帧不偷偷全局 fallback，
  下一帧进入恢复全局匹配。
- `(verified)` `Poe2MonitorConfigStore` 只读写 PoE2 自己的 `monitor.json`，原子替换临时文件；
  不读取 `NavConfig`、`app_context.monitor_region` 或导航目录。
- `(partial)` 默认 wall/template 比例、Y 方向和 HSV 人物阈值仍需真实 PoE2 样本校准；
  默认 runtime 具备显式失败状态，但本轮没有运行中的 PoE2 进程，未宣称实机定位成功。

**修订的旧结论：** 原来断点写的是“页面尚无实时监控、人物定位或轨迹”；本轮已实现
代码和合成测试，状态改为“代码批次完成，等待真实 PoE2 小地图校准与实机验收”。

### C. 验证与安全边界

- `python -m pytest tests/test_localization_observations.py tests/test_map_localizer.py tests/test_localization_trajectory.py tests/test_localization_result.py tests/test_phase_tracker.py tests/test_local_matcher.py tests/test_monitor_binding.py tests/poe2_live_terrain tests/test_poe2_monitor_dialog.py tests/test_poe2_live_terrain_page.py tests/test_poe2_live_terrain_presenter.py tests/test_poe2_live_terrain_monitoring.py tests/test_main_window_poe2_terrain_page.py -q`：**50 passed**。
- `python -m compileall -q src tests tools packaging`：通过。
- `git diff --check`：通过；仅有工作区既有 LF/CRLF 规范化提示。
- Serena：新增纯 Python 引擎/配置文件无诊断；当前 Serena 语言服务器对 PySide6、numpy、cv2
  的 import 提示属于解释器环境提示，实际运行测试已加载依赖并通过。
- 未启动 PoE2、Host、LAN 或任何 Xbox/键盘/鼠标输入；未执行网络同步。真实验证仍由用户
  手动打开游戏、配置小地图矩形后进行。

完整回归结果为 `448 passed, 2 skipped, 4 failed, 10 subtests passed`。失败来自既有
`pydirectinput` distribution metadata 缺失和 `PathFinder` 三个行为断言；本轮没有修改
分发解析或路径规划模块，PoE2 focused suite 仍为 `50 passed`。

### D. 下一轮计划

1. 在真实 PoE2 中配置小地图矩形并记录截图尺寸、人物图标候选特征和 HSV 阈值。
2. 用实机样本校准 native terrain 与 minimap 的比例、X/Y 方向、Y 翻转和 marker offset。
3. 记录首帧 global、local tracking、recovery 的置信度与耗时，必要时只调整 PoE2 业务参数。
4. 继续保持路线规划、自动跟随、多人身份选择和真实输入为后续阶段，不把这些策略下沉到引擎。
## [SYNC] 2026-09-19 - 通用引擎与 Torchlight 业务域边界收敛

### A. 本轮范围声明

- 将 `core/events/follow_chain.py` 的可复用动作链运行时收敛为通用
  `core/events/automation/action_sequence.py`，保留仅用于迁移兼容的别名。
- 将 Torchlight 事件定义注册收口到 `features/torchlight/composition.py`，
  导航 UI 只依赖业务组合入口，不直接拥有 Portal/Loot 定义。
- 将 Follow UI 归入 `ui/modes/torchlight/follow/`，同步主窗口、事件工作台和
  现有测试引用。
- 复核并更新 `CODEBASE.md`、`ARCHITECTURE_GUIDE.md`、`src/auto_modules/ui/modes/ARCHITECTURE.md`
  中受影响的架构描述。

### B. 读取目标

- `src/auto_modules/core/events/follow_chain.py`
- `src/auto_modules/features/torchlight/{composition.py,follow/*}`
- `src/auto_modules/ui/modes/{follow/*,events/workbench.py,navigation/event_adapter.py}`
- `src/auto_modules/ui/main_window.py`
- 跟随、事件链和架构边界测试

### C. SYNC 结果

**直接变更：**

- Portal、Loot、Follow、FollowerPlanner、Follow replay/benchmark 已从通用层迁至
  `features/torchlight/`；PoE2 runtime/calibration/policy/reference 已从实验目录
  提升到 `features/poe2/live_terrain/`，旧实验包只保留兼容导出。
- `core/events/automation/action_sequence.py` 现承载通用、有界、tick 驱动的声明式
  动作序列；`features/torchlight/skills/follow_chain.py` 提供业务 facade，旧
  `core/events/follow_chain.py` 仅保留兼容别名。
- `features/torchlight/composition.py` 是 Portal/Loot 注册入口；`MainWindow` 将该工厂
  注入 `NavigationModeWidget`，导航模块在无注入时只创建空的通用 `EventRegistry`。
- Follow 页面和编辑器迁至 `ui/modes/torchlight/follow/`；主窗口、事件工作台和测试
  已同步导入路径。
- 修复 `features/torchlight/follow/__init__.py` 重复内容，恢复
  `core.events.automation` 原有 repository/router/execution 公共导出，避免扩大重构
  影响面。

**连带重读文件：**

- `core/events/{registry.py,event_lifecycle.py,automation/__init__.py}`
- `features/torchlight/follow/{config.py,workers.py,service.py}`
- `ui/{main_window.py,modes/navigation/widget.py,modes/events/workbench.py}`
- 跟随、事件、PoE2、路径和架构边界测试

**CodeGraph：** 已同步并验证调用面；`ActionSequenceDefinition` 的生产调用只来自
通用自动化导出、迁移兼容层、Torchlight skill facade 和编辑器验证；`FollowPage`
只由 Torchlight UI public API 和 `MainWindow` 使用。

**验证：**

- 架构边界与 Follow 聚焦：`42 passed`。
- PoE2、事件感知、路径聚焦：`46 passed`。
- 事件自动化聚焦：`81 passed`。
- `python -m compileall -q src tests tools packaging`：通过。
- 全量：`470 passed, 2 skipped, 4 failed, 10 subtests passed`。四个失败均与迁移前
  已知基线一致：一个为本机缺失 `pydirectinput` distribution metadata，三个为既有
  `PathFinder` 行为断言；本轮未改发布依赖选择或通用 Pathfinder。

**修订旧结论：** 先前文档将 Portal/Loot 描述为 `core.events.types` 的“通用事件类型”，
并将 PoE2 业务 runtime 描述为由 `tools/experiments` 承载。当前权威结论为：这些都是
游戏业务组合；通用层只保留可脱离游戏术语复用的感知、事件、定位、导航和动作能力。

**安全边界：** 本轮没有启动 Host、LAN、游戏进程或任何键盘、鼠标、Xbox 输出；只运行
静态编译、offscreen/单元/loopback 测试和 CodeGraph 索引。

## [SYNC] 2026-09-19 - 导航 UI 的游戏业务边界彻底收敛

### A. SYNC 范围声明

**触发任务：** 在 Portal、Loot、Follow 已迁入 `features/torchlight/` 的基础上，继续清理
通用导航 UI 中残留的 Torchlight 窗口名、Portal 手工测试状态机和 Loot 专用覆盖层，确保
通用层只消费显式注入的窗口查找器、事件调试能力和领域中立的可视化描述。

**直接变更文件（预计）：**

- `src/auto_modules/ui/modes/navigation/event_adapter.py`
- `src/auto_modules/ui/modes/navigation/events/`
- `src/auto_modules/ui/modes/navigation/presentation/event_overlay.py`
- `src/auto_modules/ui/modes/navigation/composition/lifecycles.py`
- `src/auto_modules/ui/modes/navigation/runtime/`
- `src/auto_modules/ui/modes/navigation/widget.py`
- `src/auto_modules/ui/main_window.py`
- `src/auto_modules/ui/modes/torchlight/` 与 `features/torchlight/` 中必要的业务适配入口
- `tests/test_architecture_boundaries.py` 及相关导航/事件聚焦测试

**预计连带影响：** 导航事件配置对话框、手工事件测试启停、导航帧循环的调试状态、
事件覆盖层绘制和主窗口组合注入；不改变识别、定位、路径规划、控制器输出、Host 或 LAN
协议，也不触发任何真实输入或网络同步。

### B. 第一轮边界复核结果

- `(verified)` `event_adapter.find_default_game_window_rect()` 在通用导航模块中写死
  `Torchlight/UnrealWindow`；窗口选择必须改为组合根注入。
- `(verified)` 通用导航生命周期、帧循环和 widget 仍以 `portal_test_controller`、
  `run_portal_manual_test` 等业务名称管理一套本质上可通用的“手工事件测试会话”。
- `(verified)` `presentation/event_overlay.py` 直接读取 `loot` 配置并绘制玩家中心排除圆，
  这是 Torchlight Loot 的调试策略，不应由通用导航展示层识别事件类型。
- `(verified)` `core` Python 源码中已无 Portal/Loot/Torchlight/PoE2 业务词；当前剩余
  泄漏集中在 UI 组合边界，而非底层引擎。

**修订的旧结论：** “导航 UI 已经完全不拥有 Torchlight 业务”仅对事件定义注册成立；
窗口识别、Portal 手工测试和 Loot 覆盖层仍需继续拆分。

**覆盖进度更新：** 本轮完整复核了 `navigation/event_adapter.py`、`events/lifecycle.py`、
`events/dialog_lifecycle.py`、`presentation/event_overlay.py`、`runtime/frame_loop.py`，并复核
`widget.py`、`composition/lifecycles.py`、`main_window.py` 的相关调用段。`CODEBASE.md` 将在
接口定型并通过测试后覆盖更新，避免写入即将废弃的临时边界。

### A. 第二轮目标（实现前声明）

**目标文件：** 事件管理对话框与信号适配、手工测试控制器、导航生命周期组合、事件覆盖
模型/协调器，以及 Torchlight Portal/Loot 定义。

**本轮想弄清楚：** 哪些现有 Portal 命名只是通用会话控制，哪些确属业务 UI；Loot 中心
遮罩能否通过领域中立 overlay 契约由业务定义提供，从而让通用展示层只画图元而不读取
业务配置。

### B. 第二轮契约复核结果

- `(verified)` `ManualEventTestController` 本身仅同步按钮与 active 状态，没有 Portal
  语义；Portal 只存在于调用方命名、日志和文案，因此应整体重命名为通用手工事件会话。
- `(verified)` `EventManagerDialog` 的配置表单生成是 schema 驱动的，但紧凑字段集合和
  摘要字段集合仍写死 Torchlight Portal/Loot 参数；应由业务 definition 的 schema 元数据
  标注 `compact`/`summary`，对话框只解释通用显示元数据。
- `(verified)` 当前 core `EventOverlayModel` 只描述任务点位；Loot 玩家中心遮罩不是任务，
  不应伪装为 core 事件任务。更合适的边界是导航 UI 接受可注入的领域中立 overlay
  provider，Torchlight UI provider 把 Loot 配置转换为圆形图元描述。
- `(verified)` 事件管理 footer 同时存在 `reset_portal_requested` 和
  `reset_events_requested`，但“刷新事件状态”按钮实际只发后者；前者已是无效兼容信号，
  可在同一批次删除。

**覆盖进度更新：** 完整复核了事件对话框 dialog/layout、panel adapter、手工测试控制器、
core overlay/coordinator presentation，以及 Loot definition 的配置 schema 和公开工厂行为。

### A. 第三轮目标（修改前声明）

**目标文件：** `schema_form.py`、Portal/Loot definition、导航 display/command 生命周期、
Torchlight UI 组合入口和主窗口注入点，以及现有对话框/导航测试。

**本轮想弄清楚：** 保持现有 UI 行为与测试兼容所需的最小公开契约，并把所有业务词从
`ui/modes/navigation` 与通用事件对话框中清除后再实施原子修改。

### C. 第三轮实现结果

- `(verified)` `NavigationModeWidget` 现在通过构造参数接收 `game_window_finder`、
  `event_registry_factory` 和 `event_overlay_providers`；缺省值分别为无窗口、空 registry
  和无附加图元，独立使用时不再隐式选择任何游戏。
- `(verified)` Portal 专用手工测试命名已收敛为通用 `manual_event_test` 会话；事件对话框、
  生命周期、命令生命周期和帧循环均不再出现具体事件名。
- `(verified)` 事件 schema 新增通用 `compact`/`summary` 显示提示；具体字段集合由
  Torchlight Portal/Loot definition 声明，通用对话框不再维护业务参数白名单。
- `(verified)` 通用导航新增 `EventOverlayContext`/`EventCircleOverlay` 与 provider 注入点；
  Loot 中心遮罩解释已移动到 `ui/modes/torchlight/navigation.py`。
- `(verified)` Torchlight UI 组合对象集中提供事件 registry 工厂、游戏窗口查找器和 Loot
  overlay provider；`MainWindow` 只在应用组合根展开这些依赖。

**验证：** 受影响模块 `compileall` 通过；架构边界、导航 UI、紧凑操作、导航 intent 与
hook 聚焦测试 **20 passed**。对 `core`、通用 navigation UI 和通用 event manager 的
业务词扫描无输出。

**覆盖进度更新：** 新增并复核 `core/events/config_schema.py`、
`ui/modes/torchlight/navigation.py`；重读并更新事件对话框、导航事件/显示/命令/帧循环和
Portal/Loot definition 的相关算法与调用边界。

### A. 第四轮目标（收尾检查前声明）

**目标文件/范围：** 旧导入路径、旧缓存目录、所有 Torchlight/PoE2 feature 公共导出、
相关测试导入、当前权威架构文档和完整工作区 diff。

**本轮想弄清楚：** 是否还存在“源码已迁移但兼容入口/测试/文档仍把实验或旧 core 路径
当权威入口”的残留，并在不覆盖用户其他修改的前提下完成清理和文档同步。

### C. 第四轮收尾结果

- `(verified)` 生产源码、测试和工具中已无旧 Portal/Loot/Follow import 路径；PoE2 正式
  测试已从 `tools.experiments` 兼容导出切换到 `features.poe2.live_terrain`。
- `(verified)` `core.routing` 公开 `LaggedTrajectoryTarget`；Follow 业务与测试改用稳定包入口。
- `(verified)` 旧 `core/diagnostics`、`application/follow`、`core/events/types/portal|loot`、
  `ui/modes/follow` 和 `core/lan_follow` 源码/缓存目录已清理；回退标签
  `pre-reorg/2026-09-18` 保持不变。
- `(verified)` `CODEBASE.md` 已同步目录图、模块边界、函数算法和事件管理数据流；Portal
  feature 文档不再把旧 core 路径描述为当前实现，历史 `docs/architecture` 明确标为快照。
- `(verified)` CodeGraph 已重新同步到 812 files / 9,470 nodes / 24,670 edges，并确认
  `TorchlightNavigationComposition -> NavigationModeWidget -> EventOverlayContext` 调用面。

**最终验证：**

- Follow/架构聚焦：**41 passed**。
- PoE2 聚焦：**35 passed**。
- Portal/Loot/Event 聚焦：**24 passed**；较宽 Portal/Loot/Navigation 组合为 **40 passed**。
- `python -m compileall -q src tests tools packaging`：通过。
- 全量：**487 passed, 2 skipped, 4 failed, 10 subtests passed**。四个失败与已知基线一致：
  本机缺少 `pydirectinput` distribution metadata，以及 `PathFinder` 的 blocked-corner、
  unexplored-area、strict thin-wall 三个既有断言；本轮没有修改其实现。
- `git diff --check`：通过，仅显示工作区既有 LF/CRLF 规范化提示。

**安全边界：** 未启动游戏、Host 或 LAN；未发送鼠标、键盘、虚拟手柄或网络同步输入。

**Git 边界：** 已保留可用基线标签。当前同一工作区还有通信重构及用户 PoE2/配置改动，
并且 `ui/main_window.py` 等文件存在重叠；本轮没有把这些不同所有权的修改混入一个新提交。

## [SYNC] 2026-09-19 — 通信运行时 UI 装配与接收隔离

### A. SYNC 范围声明

**触发任务：** 完成通信层重构的 UI 注入、共享接收和生命周期验证。
**直接变更文件：** `ui/composition/services.py`、`ui/composition/__init__.py`、`ui/main_window.py`、`ui/modes/torchlight/follow/page.py`、`ui/modes/events/workbench.py`、相关通信适配与测试。
**预计连带影响：** FollowService/EventWorkbenchService 调用方、Host bridge/transport 接收路径、manager 的 capability lease 与 dispatcher、窗口关闭时的 Host 资源所有权。

## [SYNC] 2026-09-20 — PoE2 独立监控 profile 与页面排版

### A. SYNC 范围声明

**触发任务：** 在不修改绘图模式的前提下，为 PoE2 页面独立增加圆形/正方形监控范围、中心点选择、本地多 profile 和绘图模式风格的地图/监控/人物位置布局。
**直接变更文件：** `core/spatial/capture_geometry.py`、PoE2 feature monitor config/profile store、PoE2 UI capture/config/page/composition、相关测试和设计计划。
**预计连带影响：** `MainWindow` 的 PoE2 composition 注入、PoE2 runtime 的 binding 来源、旧 `monitor.json` 兼容读取；`ui/modes/mapping*` 明确不在变更范围内。

### C. SYNC 结果

- `(verified)` 原绘图模式 `src/auto_modules/ui/modes/mapping*` 与 `mapping_widget.py` 没有本轮差异；PoE2 的画框、中心点和配置面板位于 `ui/modes/poe2_live_terrain/`，只参考既有交互实现。
- `(verified)` 新增的 `core/spatial/capture_geometry.py` 只提供矩形截图上的正方形/圆形布尔遮罩；圆形不改变底层截图数组。
- `(verified)` `Poe2MonitorConfig` 增加 profile 名称、选择模式、截图大小、形状和圆形半径；`Poe2MonitorProfileStore` 支持本地 profile 的新建、复制、重命名、激活、保存和删除，并兼容旧 `monitor.json`。
- `(verified)` PoE2 页面新增独立 profile toolbar、监控配置面板和左右分栏展示；右侧分别展示实时小地图、当前在线地图和人物定位状态。
- `(verified)` `MainWindow` 只有一处窄注入变更：向 PoE2 页面传入 profile store；没有修改绘图页面的运行时或配置逻辑。

**验证：** `65 passed`（PoE2、架构边界、页面、profile、选择器和遮罩聚焦测试）；相关源码 `compileall` 通过；`git diff --check` 通过（仅有既有 CRLF 提示）。

**修订旧结论：** 原计划曾把通用监控 UI 回接到绘图模式；根据用户确认改为 PoE2 侧独立复刻，绘图模式保持原实现不变。

**覆盖进度更新：** 已重读并同步 `capture_geometry.py`、PoE2 monitor config/profile store、PoE2 capture selector/config panel/profile toolbar/page/composition，以及 PoE2 当前状态文档和设计计划。

**下一轮计划：** 在实机前继续补充 profile 切换与页面展示的行为测试，并确认圆形遮罩真正接入识别 runtime；不修改绘图模式。

## [SYNC] 2026-09-20 — PoE2 圆形 profile 接入采集链路

### A. SYNC 范围声明

**触发任务：** 将 PoE2 profile 的正方形/圆形选择真正接入截图适配器，避免只保存 UI 参数而不影响识别帧。
**直接变更文件：** `features/poe2/live_terrain/monitor_source.py`、`ui/modes/poe2/composition.py`、PoE2 monitor source 测试和状态文档。
**预计连带影响：** PoE2 localization runtime 的输入帧内容；正方形兼容路径、2D/3D 截图数组和圆形半径校验；绘图模式无连带影响。

### C. SYNC 结果

- `(verified)` `MonitorFrameSource.capture()` 在 profile shape 为 `circle` 时生成矩形 bool mask，将圆外像素置零；2D/3D 帧均有测试覆盖。
- `(verified)` PoE2 composition 的 monitor frame closure 从 active profile 读取 `shape` 和 `circle_radius`，并传入 capture adapter；无 profile 时仍兼容旧 `monitor.json`。
- `(verified)` 相关 PoE2/UI 聚焦测试 **13 passed**；`compileall` 和 `git diff --check` 通过。

**覆盖进度更新：** 已更新 `CODEBASE.md`、`docs/POE2_LIVE_TERRAIN_CURRENT_STATE.md`，并确认 `ui/modes/mapping*` 仍无本轮差异。

## [SYNC] 2026-09-20 — PoE2 人物定位失败诊断与修复

### A. SYNC 范围声明

**触发任务：** 当前 PoE2 页面已经能获取并展示地图，但人物定位状态仍为 `failed/player_not_detected`；需要在不降低阈值猜测修复的前提下，补齐识别候选诊断，复现失败条件，并完成单人全局定位验证。
**直接变更文件：** PoE2 HSV 玩家识别器、定位 runtime 状态/诊断、PoE2 定位页面展示、对应测试与状态文档。
**预计连带影响：** PoE2 监控帧采集输出、全局匹配输入、人物 marker 绘制和 UI 定位状态；绘图模式、输入设备、Host/LAN 不在范围内。

### C. SYNC 结果

- `(verified)` `HSVPlayerObservationRecognizer.__call__()` 现在记录 HSV 上下界、mask 非零像素、轮廓总数/面积、面积过滤数、候选坐标/置信度和诊断原因；`Poe2LocalizationRuntime.tick()` 将这些信息汇总为 `recognition_diagnostics`，并在 `player_not_detected` 日志中输出关键字段。
- `(verified)` PoE2 页面在定位状态下显示候选数、通过数、最大面积、最大置信度、mask 像素、前三个候选坐标和失败原因，可以区分无轮廓与阈值/歧义失败，不再只显示 `player_not_detected`；停止监控时清空诊断显示。
- `(verified)` 证据显示单候选小轮廓面积约 10 时旧公式置信度约 `0.65`，被 `0.70` 门槛拒绝；PoE2 runtime 默认门槛调整为 `0.60`，公共 `HSVRecognizer` 默认色彩参数未修改，多候选仍 fail closed。新增测试覆盖小轮廓拒绝和有效小标记接受。
- `(verified)` `ui/modes/poe2/composition.py` 为实际 `HSVRecognizer` 复制参数创建 PoE2 专属实例，避免绘图模式对共享可变识别器的改动污染 PoE2；不具备 HSV 参数接口的测试替身保持兼容。
- `(verified)` PoE2 focused suite **55 passed**；`compileall` 通过；`git diff --check` 通过（仅保留工作区既有 CRLF 警告）。完整回归为 **515 passed, 1 skipped, 3 failed**，失败仍是未改动的既有 `PathFinder` 角点/未探索区/细墙断言。

**连带重读文件：** `features/poe2/live_terrain/runtime.py`、`ui/modes/poe2/composition.py`、`ui/modes/poe2_live_terrain/page.py`、`tests/poe2_live_terrain/test_localization_runtime.py`、`tests/test_architecture_boundaries.py`、`docs/POE2_LIVE_TERRAIN_CURRENT_STATE.md`、`CODEBASE.md`。
**CODEBASE.md 更新内容：** 更新 PoE2 runtime 数据流、识别诊断字段、专属 recognizer 组合方式和 P1 人物识别风险。
**下一轮计划：** 启动页面后用真实 PoE2 小地图观察诊断字段；若候选仍为 0，先按日志中的 HSV/mask 证据校准业务 profile 参数；若候选唯一但全局匹配失败，再单独校准比例、轴向和 wall layer，不把两个问题混在一起。

## [SYNC] 2026-09-20 — PoE2 中心模式与图像识别模式分流

### A. SYNC 范围声明

**触发任务：** 用户确认单人中心模式不需要人物图像识别，只使用配置中心；颜色/形状识别只用于区域/多人模式。修正当前 runtime 忽略 `selection_mode`、中心模式仍调用 HSV 的逻辑错误。
**直接变更文件：** `features/poe2/live_terrain/runtime.py`、PoE2 定位 runtime 测试、PoE2 当前状态文档和 CODEBASE 架构说明。
**预计连带影响：** 中心 profile 的首帧候选来源、识别诊断文本、后续全局/局部定位输入；绘图模式、公共 HSV 默认值、输入和网络边界不变。

### C. SYNC 结果

- `(verified)` `Poe2LocalizationRuntime.configure_monitor()` 现在读取 `selection_mode` 和 `MonitorBinding.player_marker_position`。
- `(verified)` `center` 模式通过 `_recognize_or_use_center()` 直接生成 `source="configured-center"`、置信度 `1.0` 的单一候选，不调用注入的 HSV/形状识别器；缺少 marker 时才按当前帧尺寸取几何中心并做边界裁剪。
- `(verified)` `region` 模式保持原有 HSV 多候选识别和单人唯一候选策略；中心模式诊断明确为 `center_configured`。
- `(verified)` 新增测试验证中心模式在识别器主动抛错时仍能完成全局定位，并把配置中心 `(160, 160)` 传入 matcher；相关 PoE2/UI focused tests **10 passed**，`compileall` 和 `git diff --check` 通过。

**修订旧结论：** 之前文档把“单人版本必须真正识别人物图标”写成统一规则；现在修订为：中心模式使用用户配置几何契约，区域/多人模式才使用图像识别。
**下一轮计划：** 重新启动页面验证当前默认中心 profile 的诊断显示为 `center_configured`，确认人物定位问题已经从 HSV 链路移除；随后单独处理整张地图显示范围/裁剪问题。

## [SYNC] 2026-09-20 — PoE2 地图方向校准与初始展示放大

### A. SYNC 范围声明

**触发任务：** 用户确认实时监控小地图与 native 地图展示方向不一致，且获取地图在页面中显示过小；要求校准方向并改善 PoE2 页面展示，不修改绘图模式。
**直接变更文件：** PoE2 live terrain orientation/config/runtime/presenter/page、独立配置面板、通用 `ScalableMapWidget` 的可配置适配倍数及相关测试。
**预计连带影响：** PoE2 profile 的方向字段、reference 与全局/局部匹配坐标、轨迹/人物 overlay、PoE2 初始地图缩放；公共地图控件默认行为保持不变。

### C. SYNC 结果

- `(verified)` 新增 `TerrainOrientation` 纯适配模块，统一处理 0/90/180/270 度顺时针旋转、水平/垂直翻转、数组 shape、点坐标和局部位移；旋转后 90/270 度会同步交换宽高。
- `(verified)` `Poe2MonitorConfig` 将地图方向作为可持久化 profile 字段；PoE2 独立配置面板增加旋转和镜像选项，旧 profile 缺省为原始方向，绘图模式没有改动。
- `(verified)` runtime 对 native snapshot 构建的 `TerrainReference` 应用相同方向，并在 profile 改变时从内存快照重建；局部人物位移也按同一方向变换，避免匹配结果与 overlay 使用不同坐标系。
- `(verified)` presenter 以同一方向渲染地图；`ScalableMapWidget` 新增 `fit_scale_multiplier`，默认仍为 `1.0`，PoE2 页面设置为 `1.35`，只放大初始适配视图，不裁剪定位用完整地图。
- `(verified)` PoE2 focused suite **47 passed**；源码 `compileall` 通过；`git diff --check` 通过（仅有既有 CRLF 提示）。

### 实机未决事项

方向目前由 profile 手动选择，尚未用真实 PoE2 小地图确认哪一个旋转/镜像组合正确；首次实机应逐项比较小地图墙体与地图展示方向，再固定 profile。自动方向候选比较暂不启用，避免对称地图误选。
## [SYNC] 2026-09-21 — PoE2 监控与绘图模式视觉匹配能力对齐

### A. SYNC 范围声明

**触发任务：** 用户实机确认 PoE2 页面只复刻了选区和展示外壳，缺少绘图模式已经具备的视觉匹配、颜色校准、识别结果预览和参数持久化细节，导致全局定位输入与绘图模式差异过大。
**直接变更文件（预期）：** PoE2 live terrain 配置模型、PoE2 独立配置/预览 UI、PoE2 composition/runtime 识别适配及对应测试；不修改绘图模式业务代码。
**预计连带影响：** 公共 `HSVRecognizer` 参数契约、截图 binding、墙体/雾区/人物 mask、全局匹配模板、PoE2 profile JSON、首帧定位诊断和 F-POE2-LOC 数据流。

**本轮目标文件：** 绘图模式配置入口、颜色校准对话框、实时识别预览/会话、识别参数持久化，以及 PoE2 当前配置和 composition。先确认完整参考链路与缺失清单，再进入测试和实现。

### C. 第一轮对照发现

**关键发现：**

- `(verified)` 绘图模式 `MappingWidget.open_color_picker()` 会从当前 binding 抓取真实帧，将完整 `HSVRecognizer.get_params()` 注入 `ColorPickerDialog`，允许分别采样墙体/人物 HSV，并在预处理图上即时展示二值墙体 mask；PoE2 配置页没有这条入口。
- `(verified)` 绘图模式每帧使用 `HSVRecognizer.extract_combined(frame, player_pos)`，其匹配层由 wall mask 与 Canny edge 按权重融合，并执行饱和度动态区排除及人物半径擦除；PoE2 `_wall_mask()` 只调用 `extract_walls()`，没有使用已经验证的 combined matching contract。
- `(verified)` 绘图模式配置完整保存 `recognizer.get_params()`，覆盖 HSV、CLAHE、颜色深化、Gamma、TopHat、透明模式、饱和度过滤、Canny、特征权重、形态学核和人物擦除半径；`Poe2MonitorConfig` 当前一个识别参数也不保存。
- `(verified)` 绘图模式实时窗口显示预处理后的 frame，颜色对话框同时显示原图采样与 wall mask 预览；PoE2 页面只显示 raw frame，无法判断真正送入 matcher 的特征层。
- `(verified)` `MainWindow.setup_ui()` 先创建 `MappingWidget` 并加载第一页配置，之后才创建 PoE2 composition；PoE2 只在创建时复制一次共享 recognizer 参数。它随后与绘图 recognizer 状态隔离，但 profile 没有独立参数，因此“独立配置”只完成了截图 binding，没有完成识别配置。

**修订旧结论：** 原记录认为 PoE2 已“独立复刻绘图模式监控配置”；现在确认只复刻了选区/profile 外壳，视觉识别校准和 matching evidence 契约并未复刻，属于 `(conflict)`，必须修正。

**覆盖进度更新：**

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|---|---|---:|---:|---|
| `ui/modes/mapping_widget.py` | 浅读 | 深度完整 | 2 | 完整核对选区、颜色采样、实时 session、参数应用/持久化和高级设置调用链。 |
| `ui/modes/mapping/ui/layout.py` | PENDING | 深度完整 | 1 | 完整核对绘图页所有监控、HSV、特征、几何、预览控件及信号连接。 |
| `ui/dialogs/color_picker_dialog.py` | 浅读 | 深度完整 | 2 | 确认预处理图采样、墙体/人物 HSV 范围计算、mask 预览、缩放和结果契约。 |
| `core/vision/hsv/combined.py` | 浅读 | 深度完整 | 2 | 确认 wall/edge 融合、动态色排除和人物半径清理是绘图匹配输入的关键步骤。 |
| `core/vision/hsv/params.py` | 浅读 | 深度完整 | 2 | 确认完整识别参数集合及 set/get 对称应用范围。 |
| `features/poe2/live_terrain/monitor_config.py` | 深度完整 | `(conflict)` | 3 | profile 缺少 recognizer params，和“完全独立配置”的既定要求冲突。 |
| `features/poe2/live_terrain/runtime.py` | 深度完整 | `(conflict)` | 4 | 当前 matcher 只用 wall mask，未复用绘图模式 combined match mask。 |
| `ui/modes/poe2_live_terrain/config_panel.py` | 深度完整 | `(conflict)` | 3 | 缺少颜色校准、识别参数编辑与匹配层预览入口。 |

**下一轮计划：** 先写失败测试固定 recognizer 参数 profile 往返、combined match mask 调用和 PoE2 校准入口，再修改 PoE2 独立配置/运行时；绘图模式保持只读参考。

## [SYNC] 2026-09-21 — PoE2 视觉校准契约实现

### A. SYNC 范围声明

**触发任务：** 根据上一轮已确认差异，为 PoE2 独立 profile 补齐绘图模式已有的识别参数、颜色校准和 combined matching evidence，同时把实际匹配层展示在 PoE2 页面。
**直接变更文件：** `features/poe2/live_terrain/monitor_config.py`、`runtime.py`，`ui/modes/poe2_live_terrain/config_panel.py`、`monitor_dialog.py`、`page.py`、`presenter.py`，以及 PoE2 focused tests。
**预计连带影响：** profile JSON 向后兼容、composition 创建的 dedicated recognizer、center/region 两种人物策略、全局/局部匹配模板、UI 帧缓存和日志诊断；原绘图模式只作为参考，不修改。

### C. SYNC 结果

**实现结果：**

- `(verified)` `Poe2MonitorConfig.recognizer_params` 现在深复制并随独立 profile JSON 往返；旧 profile 缺字段时仍按空字典加载，首次颜色/高级校准时以 PoE2 dedicated recognizer 的完整默认参数补齐。
- `(verified)` PoE2 配置面板新增“颜色校准”和“高级视觉参数”入口；颜色校准复用 `ColorPickerDialog` 的预处理采样、墙体/人物 HSV 范围与 wall-mask 预览，高级参数复用 `AdvancedSettingsDialog`，但只保留 `HSVRecognizer.get_params()` 支持的字段，不把 stitcher 参数写入 PoE2 profile。
- `(verified)` 校准截图通过 composition 的 `capture_preview_frame(config)` 使用对话框当前尚未保存的 binding、形状和圆形半径；不会读取或修改绘图模式 `AppContext`。
- `(verified)` `Poe2LocalizationRuntime` 新增 `Poe2VisualEvidence`，每帧在人物局部坐标确定后调用 `preprocess_image()` 和 `extract_combined(frame, player_pos)`；center 模式仍不做人物图像识别，但会执行墙体视觉处理。全局/局部 matcher 优先消费同一 `match_mask`，旧注入 recognizer 缺少 combined API 时才回退 wall mask。
- `(verified)` `Poe2LocalizationState` 发布 `processed_frame`、`match_mask`、`wall_mask` 和 `fog_mask`；页面并列显示预处理画面与定位器实际使用的匹配特征，停止时同步清空两块帧缓存。
- `(verified)` 原绘图模式业务文件未修改；PoE2 dedicated recognizer 和 profile 参数保持独立。

**验证：** PoE2 focused/UI/architecture suite `68 passed`；`python -m compileall -q src` 通过；`git diff --check` 通过（仅既有 CRLF 提示）。Serena 新增代码诊断已处理；`PySide6`、`numpy`、`cv2` 的 missing-import 提示来自语言服务器未使用项目 venv。

**仍未解决：** 真实 PoE2 小地图与 native terrain 的比例、最终旋转/镜像组合和匹配阈值仍需实机校准；自动方向候选尚未实现。本轮解决的是视觉输入契约和校准能力不一致，不宣称全局定位已经实机通过。

## [SYNC] 2026-09-21 — PoE2 截图监控与对比样本窗口

### A. SYNC 范围声明

**触发任务：** 为“数据采集测试”页增加独立截图监控窗口，并将同一帧的原图、预处理图、匹配特征和当前地形作为可回看的对比样本保存。
**直接变更文件：** `features/poe2/live_terrain/capture_samples.py`、`features/poe2/live_terrain/__init__.py`、`ui/modes/poe2_live_terrain/capture_monitor_window.py`、`capture_test_page.py`、`page.py`、`ui/modes/poe2/composition.py`、`ui/main_window.py` 及对应测试。
**预计连带影响：** PoE2 composition 依赖契约、测试页窗口生命周期、monitor profile 序列化、地形展示方向、应用关闭清理、`data/poe2_live_terrain_test/samples/` 文件副作用和相关 architecture/UI 回归。

### C. SYNC 结果

**关键发现：**

- `(verified)` `CaptureEvidence` 会复制并冻结同一帧派生出的 raw/processed/feature 数组和 config payload，刷新失败时窗口清除 evidence，旧帧不能继续保存。
- `(verified)` `CaptureSampleArchive.save()` 在隐藏临时目录完成三张必需 PNG、可选 terrain PNG 和 manifest 后再原子发布；编码/写盘失败会删除临时目录。图片 manifest 保存尺寸、通道、dtype 与编码字节 SHA-256。
- `(verified)` terrain 缺失时样本仍可保存三类视觉证据并显式记录 missing；历史浏览不会从其他样本补用 terrain。
- `(verified)` `Poe2CaptureMonitorWindow` 只调用一次截图 provider 生成当前证据，保存按钮不重新截图；窗口和落盘 terrain 使用同一个 profile 旋转/镜像契约。
- `(verified)` `Poe2CaptureTestPage.open_capture_monitor()` 只创建一个独立窗口实例，profile 更新通过 provider 读取最新 config，shutdown 关闭窗口并停止定时器。
- `(verified)` composition 新增独立 `capture_sample_archive`，写入 `data/poe2_live_terrain_test/samples/`；现有 `TerrainDebugArchive` 的地图 NPZ 保存链未修改。

**修订旧结论：** 此前认为用户点击“刷新截图”后可以从本地复查该帧；现在确认旧实现仅把 pixmap 放入 `QLabel`，没有保存截图证据。新窗口的“保存当前对比样本”才是可追溯的落盘入口。

**CODEBASE.md 更新内容：** PoE2 目录/文件职责、`capture_samples.py` 和 `capture_monitor_window.py` 模块详解与算法、F-POE2-CAPTURE-TEST 每跳数据流、同步 PNG 编码性能风险。

**覆盖进度更新：**

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|---|---|---:|---:|---|
| `features/poe2/live_terrain/capture_samples.py` | PENDING | 深度完整 | 1 | 核对 evidence 冻结、terrain 渲染、PNG 元数据、唯一目录、原子发布、失败清理和历史加载。 |
| `ui/modes/poe2_live_terrain/capture_monitor_window.py` | PENDING | 深度完整 | 2 | 核对一次截图派生三层证据、定时器/close 生命周期、保存、历史切换和同方向 terrain 展示。 |
| `ui/modes/poe2_live_terrain/capture_test_page.py` | 深度完整 | 深度完整 | 3 | 新增窗口按钮和单例所有权；确认原内嵌 preview 与地图显式归档仍独立。 |
| `ui/modes/poe2/composition.py` | 深度完整 | 深度完整 | 3 | 确认 sample archive、测试 service、地图 archive 和 dedicated recognizer 分别注入，不共享运行状态。 |
| `ui/modes/poe2_live_terrain/page.py` | 深度完整 | 深度完整 | 4 | 确认样本归档只向测试 tab 透传，定位 tab 的 runtime 与关闭流程不变。 |
| `ui/main_window.py` | 深度完整 | 深度完整 | 4 | 确认组合根新增一个依赖参数，页面索引、Host/LAN 生命周期和关闭顺序未改变。 |

**验证：** PoE2 focused/UI suite `70 passed`；全项目 `547 passed, 1 skipped, 3 failed, 10 subtests passed`。3 个失败仍为未修改的既有 `tests/test_pathfinder.py` 对角穿角、未探索区域和细墙语义。`compileall` 与 `git diff --check` 通过。Serena 的真实类型诊断已修复；剩余 `PySide6/cv2/numpy` missing-import 是语言服务器未使用项目 venv。

**下一轮计划：** 在 PoE2 开启且小地图可见时，从独立窗口保存至少两套样本；先对比 raw/processed/feature/terrain，再决定 45° 候选、比例搜索和方向细化算法。

## [SYNC] 2026-09-21 — 对比样本目录 Windows ACL 修复

### A. SYNC 范围声明

**触发任务：** 实机首次保存后，普通工作区会话无法进入样本目录，需定位并修复跨进程身份的目录权限继承。
**直接变更文件：** `features/poe2/live_terrain/capture_samples.py`、`tests/poe2_live_terrain/test_capture_samples.py`。
**预计连带影响：** 样本临时目录创建、原子目录发布、历史样本可读性；PNG、manifest 和既有地图 NPZ 数据契约不变。

### C. SYNC 结果

**关键发现：**

- `(verified)` 首次实机连续保存的四份样本中，一份可由当前用户读取，后三份均在目录枚举和 `icacls` 时返回 `Access is denied`；samples 父目录本身包含用户、`CodexSandboxUsers`、`Authenticated Users` 和 `Users` 的继承权限。
- `(verified)` 最小复现确认 `tempfile.mkdtemp()` 在 Windows 上创建 owner-only DACL；随后 `os.replace()` 只重命名目录，不会让最终样本重新继承父目录 ACL。普通 `Path.mkdir()` 创建的目录会继承 samples 根目录 ACL。
- `(verified)` `CaptureSampleArchive._create_temporary_directory()` 现使用 128-bit 随机 token 的隐藏目录和普通 `Path.mkdir()`，名称冲突最多重试 100 次；完整写入后仍由 `os.replace()` 原子发布，PNG/manifest 契约未改变。
- `(verified)` 新增 Windows 回归测试通过 `icacls` 断言最终样本目录包含继承标志 `(I)`；修复前该测试稳定失败，修复后通过。
- `(verified)` 可读实机样本 `20260921-075556-840709-MapFlotsam-F6A61E51` 包含 raw/processed/feature/terrain 和 manifest，截图为 `200 x 200`，地形为 `1864 x 2829`；后三份仍来自未重载修复代码的旧进程，未强制接管或修改其 ACL。

**修订旧结论：** 原先只确认“隐藏临时目录 + `os.replace()` 可避免半成品”；现在确认 Windows 目录原子发布还必须保留父目录可读 ACL，目录创建方式是归档契约的一部分。

**连带重读文件：** `features/poe2/live_terrain/capture_samples.py`、`tests/poe2_live_terrain/test_capture_samples.py`、`CODEBASE.md`、`docs/POE2_LIVE_TERRAIN_CURRENT_STATE.md`。

**CODEBASE.md 更新内容：** 更新 `CaptureSampleArchive.save()` 的临时目录算法和 `_create_temporary_directory()` 的 Windows ACL 风险/回归约束。

**覆盖进度更新：**

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|---|---|---:|---:|---|
| `features/poe2/live_terrain/capture_samples.py` | 深度完整 | 深度完整 | 2 | 重读保存、随机临时目录、失败清理和原子发布；确认普通 mkdir 继承父 ACL。 |
| `tests/poe2_live_terrain/test_capture_samples.py` | 深度完整 | 深度完整 | 2 | 新增 Windows `icacls (I)` 回归，覆盖跨进程身份样本不可读根因。 |

**下一轮计划：** 用户关闭旧进程并重新启动后再保存一份样本，先验证最终目录 ACL 可继承和四层证据可读，再基于 raw/feature/terrain 实现离线方向与比例候选探针；暂不接入实时定位循环。

## [SYNC] 2026-09-21 — PoE2 离线方向、比例与全局定位探针

### A. SYNC 范围声明

**触发任务：** 使用已经保存的 PoE2 原图、匹配特征和完整地形样本，在实验目录中先解决动态特征清理、随机方向、比例差异和全图位置搜索，再决定正式模块的算法调整。
**直接变更文件：** `tools/debug/poe2_live_terrain_localization_probe.py`、对应实验测试、使用说明和 PoE2 当前状态文档。
**预计连带影响：** 只新增离线实验入口和输出目录；读取 samples 中的 PNG/manifest，输出候选报告、清理后特征和叠加图。正式 PoE2 runtime、绘图模式、截图服务、输入设备、Host/LAN 均不修改。

**本轮要验证：**

- 当前生产 `TM_CCOEFF_NORMED` 失败是否主要由未搜索尺度与方向造成；
- 连通分量形状过滤能否去掉人物光环、标记和鼠标指针而保留触边地图轮廓；
- 多尺度双向 Chamfer 评分能否给出可审计的 Top-K 候选和显著性差距；
- 45° 粗搜索后是否需要小角度细化，以及结果能否映射回原生地形坐标。

### C. SYNC 结果

**关键发现：**

- `(verified)` 生产 `Poe2LocalizationRuntime._global_match()` 只在当前人工方向、原始比例上运行一次 `TM_CCOEFF_NORMED`；真实样本首选需要 feature 到 terrain 的 `225°` 逆时针旋转、水平镜像和 `0.35` 比例，因此旧实现的输入假设不成立。
- `(verified)` manifest 参数重放得到的 feature 非零支撑与保存图完全一致；`1339` 个非零像素经人物半径和连通分量清理后保留 `1113` 个，移除了紧凑的光环/标记/指针，地图主轮廓保留。
- `(verified)` 新探针执行 45° 旋转、镜像和多比例粗 Chamfer 搜索，再以 `±4°`、`±0.04` 比例和 48 像素邻域细化；小于 120 个边缘像素的候选拒绝，避免低比例小模板虚高。
- `(verified)` 人物种子侧局部可行走面与 native terrain 可行走面加入评分；实样本首选为人物 `(1318.35, 834.10)`、score `0.738386`、second `0.681727`、margin `0.056659`、walkable coverage `0.809882`，通过当前实验拒绝门槛。
- `(verified)` 参数敏感性检查中 component span `18/24/30` 与 clear radius `16/22` 保持同一候选；radius `30` 过度清理后 score `0.599810`、margin `0.001638`，被 fail closed。
- `(verified)` 合成测试覆盖动态紧凑分量清理、人物侧可行走面、`45° + 镜像 + 1.2` 比例和已知平移恢复，以及两个相同边界候选由可行走证据消歧。

**修订旧结论：** 此前把定位失败主要归因于颜色/combined 特征链不完整；现在实样本证明当前颜色链能稳定重建同一 feature，剩余主要矛盾是正式 matcher 没有方向、镜像、比例搜索，也没有可行走面和显著性拒绝契约。

**边界结论：** 探针 `accepted=true` 只是样本内置信规则通过，缺少独立真实全局坐标，不能宣称实机定位已验证；正式 runtime 本轮保持不变。

**验证：** 探针算法/PoE2 focused 回归 `77 passed`；迁移后架构边界与探针定向回归 `5 passed`；全项目 `552 passed, 1 skipped, 3 failed, 10 subtests passed`。3 个失败仍是未修改的既有 `tests/test_pathfinder.py` 穿角、未探索区和细墙语义。`compileall -q src tools tests` 和 `git diff --check` 通过（仅既有 CRLF 提示）。Serena 的 Optional 类型告警已修复；剩余 `cv2/numpy` missing-import 是语言服务器未使用项目 venv。

**CODEBASE.md 更新内容：** 增加实验 probe 模块/函数算法、目录文件注释、输出数据流和“单帧无 ground truth”P1 风险。

**覆盖进度更新：**

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|---|---|---:|---:|---|
| `tools/debug/poe2_live_terrain_localization_probe.py` | PENDING | 深度完整 | 2 | 核对参数重放、特征清理、局部可行走恢复、粗细 Chamfer 搜索、评分拒绝和全部输出副作用。 |
| `tools/debug/POE2_LIVE_TERRAIN_LOCALIZATION_PROBE.md` | PENDING | 深度完整 | 1 | 核对运行命令、图层颜色、输出目录和禁止直接接入生产的边界。 |
| `tests/poe2_live_terrain/test_localization_probe.py` | PENDING | 深度完整 | 2 | 覆盖清理、区域种子、已知变换恢复及相同边界的可行走消歧。 |

**下一轮计划：** 用修复后进程采集同一地图移动前后的多帧和至少一张不同地图；先在探针中验证变换/比例稳定与坐标位移连续性，再规划通用 matcher 下沉和 PoE2 runtime 组合，不直接复制整个实验脚本。

## [SYNC] 2026-09-21 — PoE2 启动局部地图拼接采集

### A. SYNC 范围声明

**触发任务：** 将现有 PoE2 数据采集测试窗口扩展为独立的绘图采集实验台；复用绘图模式底层的识别、关键帧/F2F 配准、质量门和加权拼接，先采集一段不重影的启动局部地图，供后续方向和全局位置匹配。
**直接变更文件：** 新增 PoE2 拼图会话适配层及其测试；扩展 `ui/modes/poe2_live_terrain/capture_monitor_window.py` 和对应 UI 测试；补充设计、实施计划及 PoE2 当前状态文档。
**预计连带影响：** `core/mapping/MapStitcher`、`MapFrameEvidence`、现有 capture evidence provider、测试页窗口生命周期、样本归档。原绘图页面、正式 PoE2 定位 runtime、完整地形采集、Xbox/键鼠、Host/LAN 不修改。

**本轮要验证：**

- 同一截图证据能否转换成绘图底层需要的 match/save/fog 图层，并保持单人中心点契约；
- 开始、暂停、重置后拼图会话状态是否隔离且可预测；
- 低质量、位移跳跃或失败帧是否由现有底层拒绝而不污染拼图；
- UI 能否同时展示实时小地图、匹配特征、拼接地图、人物位置和关键统计；
- 保存实验时能否把拼接地图、轨迹和统计与当前截图证据放在同一可追溯目录。

### C. SYNC 结果

**关键发现：**

- `(verified)` 绘图模式的真实输入契约不是一张 feature：combined 保留灰度权重用于帧间配准，wall mask 用于落图，fog mask 用于可见区域，raw gray 作为原始灰度证据。`CaptureEvidence` 已扩展为同帧携带这些可选层，拼图会话保持 distinct layer，不把它们重新折叠或二值化。
- `(verified)` `Poe2StitchingSession` 只组合通用 `MapStitcher`；idle/paused 不消费帧，start 继续当前会话，reset 创建全新 `3000 x 3000` stitcher 并清空轨迹。首帧或通过 match/quality gate 的新位置才进入轨迹，失败和低质量帧不写轨迹。
- `(verified)` 截图监控窗口仍然每周期只调用一次截图 provider；同一个 evidence 同时驱动 raw/processed/feature 预览和拼图，不为绘图再次截图。窗口关闭会停止定时器并暂停拼图，不自动保存或清空结果。
- `(verified)` UI 采用左侧四层同步证据、右侧大幅拼接地图、底部历史样本；增加开始、暂停、重置、保存和打开目录命令，并显示总帧、成功/失败、质量、匹配率、关键帧、低质量跳过和当前相对位置。离屏 `1500 x 920` 截图检查未发现控件重叠或裁切。
- `(verified)` `Poe2StitchingArchive` 只在显式保存时写 `stitched_map`、轨迹 overlay、raw/processed/feature/wall/fog、可选同实例 terrain 和 `session.json`；terrain 缺失时明确记录 missing。隐藏临时目录继承父 ACL，完整后原子发布。
- `(verified)` composition 为每个窗口创建独立 session，并把 archive 固定到 `data/poe2_live_terrain_test/stitching_sessions/`；正式 localization runtime、原绘图页面实例、Xbox/键鼠、Host/LAN 调用链未改变。

**修订旧结论：** 此前状态文档把 stitcher 归为 PoE2 有意不复用的绘图业务能力；本轮确认应区分“正式 native terrain/定位”与“数据采集实验”。正式链仍不依赖 stitcher，但实验页合理复用通用 mapping core 生成辨识度更高的启动局部图。

**连带重读文件：** `core/mapping/stitcher.py`、`core/mapping/frame_pipeline.py`、`core/mapping/weighted_merge.py`、`core/mapping/rendering.py`、`core/mapping/evidence.py`、绘图 `runtime/session.py`、map renderer、PoE2 capture window/test page/composition/page/MainWindow。

**CODEBASE.md 更新内容：** 更新 PoE2 页面职责和 `CaptureEvidence` 契约；新增 stitching session/archive 模块详解、完整算法、F-POE2-CAPTURE-TEST 拼图/归档跳和 P1 漂移/P2 内存风险；当前状态文档同步保存目录和未完成边界。

**覆盖进度更新：**

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|---|---|---:|---:|---|
| `features/poe2/live_terrain/capture_samples.py` | 深度完整 | 深度完整 | 3 | 扩展同帧 wall/fog/raw-gray 只读层并公开复用 terrain preview；原单帧归档格式保持。 |
| `features/poe2/live_terrain/stitching_session.py` | PENDING | 深度完整 | 2 | 核对生命周期、distinct layer 适配、统计差分、质量门轨迹和只读 crop snapshot。 |
| `features/poe2/live_terrain/stitching_archive.py` | PENDING | 深度完整 | 2 | 核对八类图片、terrain identity/missing、hash manifest、ACL 继承、原子发布和失败清理。 |
| `ui/modes/poe2_live_terrain/capture_monitor_window.py` | 深度完整 | 深度完整 | 4 | 核对单次截图、拼图控制/日志/统计、同帧消费、显式保存、close pause 和实际布局。 |
| `ui/modes/poe2_live_terrain/capture_test_page.py` | 深度完整 | 深度完整 | 4 | 核对窗口单例、独立 session factory、archive 注入与 shutdown 生命周期。 |
| `ui/modes/poe2/composition.py` | 深度完整 | 深度完整 | 4 | 核对 `stitching_sessions` 根、每窗口 session 隔离及正式 runtime 不共享状态。 |
| `core/mapping/frame_pipeline.py` | 深度完整 | 深度完整 | 既有+1 | 重读关键帧/F2F、跳变拒绝、quality gate、统计递增和落图调用顺序。 |
| `core/mapping/weighted_merge.py` | 深度完整 | 深度完整 | 既有+1 | 重读 wall/fog/explored 权重融合、重复帧拒绝和 precise visibility 语义。 |

**验证：** 新功能/PoE2/mapping/UI/architecture focused `104 passed`；全项目 `559 passed, 1 skipped, 3 failed, 10 subtests passed`。3 个失败仍为未修改的既有 `tests/test_pathfinder.py` 穿角、未探索区和细墙语义。`compileall -q src tools tests` 与 `git diff --check` 通过（仅既有 CRLF 提示）。Serena 未发现新增真实类型错误；剩余 `cv2/numpy/PySide6` missing-import 是语言服务器未使用项目 venv。

**下一轮计划：** 启动应用后在同一 PoE2 地图正常行走一段折线路径，观察实时拼图是否重影、轨迹是否连续、失败/低质量计数是否异常；显式保存一套 stitching session 后，再用局部拼图与同目录 terrain 开始方向、镜像、比例和全局平移联合匹配实验。

## [SYNC] 2026-09-21 — PoE2 绘图运行契约与第一页完整对齐

### A. SYNC 范围声明

**触发任务：** 修复 PoE2 内部绘图与第一页绘图效果不一致的问题；当前游戏地图墙体已改为蓝色，但颜色只作为独立 profile 的校准数据，不在通用识别层写死颜色策略。
**直接变更文件：** `core/mapping/stitcher.py`、PoE2 `monitor_config.py`、`stitching_session.py`、`capture_samples.py`，以及 PoE2 配置面板、监控对话框、截图监控窗口和页面初始化链路；同步对应 focused tests、`CODEBASE.md` 与当前状态文档。
**预计连带影响：** `MapStitcher` 参数创建/重置契约、PoE2 profile 旧数据兼容、运行中配置切换规则、颜色/高级参数编辑、同帧 wall/fog/raw-gray 诊断层、active profile 首次加载。原第一页绘图业务代码、正式 native terrain 数据、Xbox/键鼠、Host/LAN 不修改。

**本轮要验证：**

- 同一 recognizer/stitcher 参数下，PoE2 与第一页是否消费同一套视觉与拼接参数；
- 旧 profile 缺少 `stitcher_params` 时能否得到完整默认值并继续读取；
- 改变画布/比例/融合参数是否显式重建 PoE 拼图，而相同参数不清空当前会话；
- 页面首次构造时是否立即应用 active profile，而非必须手动保存一次；
- 监控窗口是否展示真正写入地图的 `wall_mask`，归档是否保留所有诊断图层；
- 蓝色墙体能否通过 profile 颜色校准保存，且底层不出现 PoE 或蓝色专用分支。

### C. SYNC 结果

**关键发现：**

- `(verified)` 同一旧样本的参数消融证明页面差异主要来自 `deepen_enabled`，而不是黄色/蓝色专用墙体逻辑；PoE 原实现只持久化 recognizer 参数且 session 硬编码 `3000 x 3000`，没有完整复刻第一页的 stitcher 参数恢复契约。
- `(verified)` `MapStitcher.default_params()` 现可无画布分配返回完整参数；`reset()` 会保留 canvas/draw scale/wall close、权重、质量门和精准可见区参数。
- `(verified)` `Poe2MonitorConfig` 对 recognizer/stitcher 两组参数都做防御性复制和 JSON round-trip；旧 profile 缺 stitcher 字段时自动补完整 `5000 x 5000` 默认契约，新建/复制/重命名继续走 `as_dict()/from_dict()`，不会掉字段。
- `(verified)` `Poe2StitchingSession.configure()` 对相同参数不清图，非 running 参数变化重建独立 stitcher 并回 idle，running 参数变化明确拒绝；reset 使用当前 profile 参数重建。
- `(verified)` PoE 高级窗口不再隐藏 stitcher tab；返回参数按 `HSVRecognizer` 和 `MapStitcher` 支持键拆分，未暴露在共享窗口控件中的 canvas/scale/quality 参数仍保留。
- `(verified)` `Poe2CaptureMonitorWindow` 同帧展示实际 `wall_mask`，样本归档可选写 wall/fog/raw-gray，历史下拉可读取这些层；旧样本仅有 raw/processed/feature 时继续加载。
- `(verified)` 页面构造、profile 切换、配置保存统一应用 monitor config；active profile 不再需要先手动保存一次才进入 runtime。
- `(verified)` 当前蓝色地图只改变 PoE profile 的颜色校准输入；core/recognizer/stitcher 没有新增 PoE、蓝色或具体地图分支。

**修订旧结论：** 上一轮把 PoE 视觉链标为“完整对齐”，但本轮逐项比较发现只对齐了 recognizer 输出，未对齐 stitcher 参数持久化、创建/重置和 wall 层诊断；现已按完整运行契约补齐。

**连带重读文件：** mapping config 保存/恢复与 advanced settings 参数适配器、PoE profile store/config panel/dialog/page、capture test window/session/archive、composition factory 和对应 focused tests。

**CODEBASE.md 更新内容：** 更新 PoE2 profile 双参数契约、页面首次应用、wall/fog/raw-gray 归档与 F-POE2-CAPTURE-TEST；补充 `MapStitcher.default_params()/reset()`、`Poe2StitchingSession.configure()` 行为和默认 5000 画布内存风险。

**覆盖进度更新：**

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|---|---|---:|---:|---|
| `core/mapping/stitcher.py` | 深度完整 | 深度完整 | 既有+1 | 新增无分配默认参数契约；reset 保留全部结构/融合参数。 |
| `features/poe2/live_terrain/monitor_config.py` | 深度完整 | 深度完整 | 既有+1 | recognizer/stitcher 双参数深复制、旧 profile 补默认和 profile CRUD 传递已核对。 |
| `features/poe2/live_terrain/stitching_session.py` | 深度完整 | 深度完整 | 3 | 核对 configure 等值/重建/running 拒绝、factory 注入和 reset 参数保持。 |
| `features/poe2/live_terrain/capture_samples.py` | 深度完整 | 深度完整 | 4 | 可选 wall/fog/raw-gray 原子归档与旧三层 manifest 兼容。 |
| `ui/modes/poe2_live_terrain/config_panel.py` | 深度完整 | 深度完整 | 既有+1 | 所有 current/selection/recognizer 更新路径保留 stitcher 参数。 |
| `ui/modes/poe2_live_terrain/monitor_dialog.py` | 深度完整 | 深度完整 | 既有+1 | 高级窗口双参数合并、按支持键拆分及 stitcher tab 保留。 |
| `ui/modes/poe2_live_terrain/capture_monitor_window.py` | 深度完整 | 深度完整 | 5 | 五层当前预览、可选历史层和 start 前 session configure 已核对。 |
| `ui/modes/poe2_live_terrain/page.py` | 深度完整 | 深度完整 | 既有+1 | 构造/切换/保存共用 `_apply_monitor_config()`，capture page 同步无重复。 |

**验证：** 新增测试先得到 13 个预期失败，再实现至 focused `35 passed`；PoE2/mapping/UI/architecture 扩展回归 `113 passed`；全项目 `567 passed, 1 skipped, 3 failed, 10 subtests passed`，3 个失败仍是未修改的既有 PathFinder 语义。`compileall -q src tests` 与 `git diff --check` 通过（仅既有 CRLF 提示）。1500×920 离屏抓图确认新增 3×2 证据区、拼接地图和历史区无重叠或裁切。

**下一轮计划：** 用户在蓝色地图下重新执行颜色校准并走一段连续路径；优先保存包含 wall/fog/raw-gray 的新样本和 stitching session。先检查 wall 层完整性，再检查 feature 稳定性及拼接重影；只有这三项通过后，才把启动局部图送入方向/镜像/比例/全局平移联合匹配。
## [SYNC] 2026-09-22 13:10 — PoE2 内存锚点局部注册实验

### A. SYNC 范围声明

**触发任务：** 在 PoE2 实验代码中实现首帧内存锚点局部注册，并让同步样本携带人物位置。

**直接变更文件：**

- `tools/debug/poe2_anchor_local_registration_probe.py`
- `tests/poe2_live_terrain/test_anchor_local_registration_probe.py`
- `src/auto_modules/features/poe2/live_terrain/capture_samples.py`
- `src/auto_modules/ui/modes/poe2_live_terrain/capture_monitor_window.py`
- `src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py`
- `tests/poe2_live_terrain/test_capture_samples.py`
- `tests/test_poe2_capture_monitor_window.py`
- `docs/plans/2026-09-22-poe2-anchor-local-registration.md`

**预计连带影响：** PoE2 手动样本归档 Flow、数据采集测试页到截图监控窗口的依赖注入、既有离线 Chamfer 搜索器、实验报告契约；不影响正式 runtime、core localization、绘图模式和输入/网络链路。

### C. 第一轮发现

**关键发现：**

- `(verified)` 新实验模块只组合既有 `search_candidates()`，没有复制 Chamfer、距离场或相似变换实现；职责集中在样本实例校验、锚点裁剪、候选先验和诊断落盘。
- `(verified)` terrain 与 player position 实例不一致时在加载边界 fail closed，不会读取根目录陈旧 `latest.npz`。
- `(verified)` 两阶段搜索先以 180 像素半径粗搜，再围绕最佳角度/镜像/比例在 130 像素半径细搜；坐标通过 crop 原点显式还原为完整 native-grid。
- `(verified)` 单帧状态只有 `anchored_candidate/ambiguous/rejected`，没有跨帧 confirmed；真实样本自动复现 `219°/flip/0.85`、锚点误差 `7.10`。

**修订旧结论：** 旧全局 probe 的 `0.72` 单一结构分门槛不能原样用于有内存锚点的局部搜索；新实验保留原始结构分和覆盖率门槛，同时显式加入锚点误差和候选分差，且仍不把单帧候选称为确认。

**CODEBASE.md 更新内容：** §2 新增实验文件；§4/§5 新增模块、所有公开/私有算法和失败行为；§9 新增单样本参数泛化风险。

**覆盖进度更新：**

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|---|---|---:|---:|---|
| `tools/debug/poe2_anchor_local_registration_probe.py` | 新增 | 深度完整 | 1 | 核对样本校验、crop 坐标还原、锚点加权、两阶段搜索、状态门和原子诊断输出。 |
| `tools/debug/poe2_live_terrain_localization_probe.py` | 深度完整 | 深度完整 | 既有+1 | 重核复用的 SearchCandidate、transform/search/overlay 契约，确认新模块未复制底层算法。 |
| `tests/poe2_live_terrain/test_anchor_local_registration_probe.py` | 新增 | 深度完整 | 1 | 覆盖实例不一致、边界裁剪不改输入、顶部/中心清理、已知旋转镜像比例恢复及诊断文件。 |

### A. 第二轮目标（阅读前声明）

**目标文件：** `capture_samples.py`、`capture_monitor_window.py`、`capture_test_page.py` 及对应三组测试。

**本轮想弄清楚：** 人物位置如何从一次地图抓取传到监控窗口保存动作，实例一致性在哪一层验证，缺位置时旧样本保存是否继续兼容，以及该变化如何更新 F-POE2-CAPTURE-TEST 数据流。

### C. 第二轮发现

**关键发现：**

- `(verified)` `Poe2CaptureTestPage.capture_map()` 在 terrain 成功后读取一次 `PlayerPositionSample` 并保存在页面；`open_capture_monitor()` 通过只读 provider 把该样本交给唯一监控窗口，不启动正式定位 runtime。
- `(verified)` `Poe2CaptureMonitorWindow.save_current_sample()` 只把当前 evidence、同周期 terrain 和 provider 返回的人物样本一起交给 `CaptureSampleArchive.save()`；点击保存不会重新截图或重新读取进程。
- `(verified)` 归档层校验 terrain/player area instance 一致；缺人物位置时继续写明确 `status=missing`，因此旧采样流程保持兼容。
- `(verified)` 非 identity profile 下，`terrain.png` 会旋转/翻转，所以 native `grid` 不能直接用于裁剪。manifest 现同时保存原生 `grid` 和与归档图一致的 `terrain_grid`，terrain 元数据同时记录 native/preview 尺寸、方向和 `coordinate_space=oriented-preview`。
- `(verified)` 审查发现既有搜索器按人物位置去重会吞掉同位置的不同方向候选；锚点探针现按多个角度/镜像 basin 分别细化并在合并后判 margin，对称方形测试稳定返回 `ambiguous`。
- `(verified)` 锚点约束原先在 Top-K 截断后才生效；`ProbeConfig` 现提供通用的可选人物位置 hint/radius，粗 Chamfer 图和原分辨率细搜图都会先把范围外位置设为无穷，再提取局部极小值。25 个重复结构测试证明近锚点真解不会被前 16 个外圈候选挤掉。

**修订旧结论：** 第一轮真实样本结果仍成立，但“只围绕最佳粗候选细化”不足以判断方向唯一性。当前实现会保留最多 4 个分数接近且角度/镜像不同的 basin；单帧仍只发布 `anchored_candidate`，对称方向必须发布 `ambiguous`。

**连带重读文件：** `capture_samples.py`、`capture_monitor_window.py`、`capture_test_page.py`、`orientation.py`、既有 localization probe 及对应 focused tests。

**CODEBASE.md 更新内容：** 更新人物位置 provider 调用链、双坐标空间归档契约、锚点前置搜索窗口、多 basin 细化和 F-POE2-CAPTURE-TEST。

**覆盖进度更新：**

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|---|---|---:|---:|---|
| `features/poe2/live_terrain/capture_samples.py` | 深度完整 | 深度完整 | 既有+1 | 核对实例门、native/oriented 双坐标、原子发布和缺位置兼容。 |
| `ui/modes/poe2_live_terrain/capture_monitor_window.py` | 深度完整 | 深度完整 | 既有+1 | 核对保存时 provider 只读取当前页面人物样本。 |
| `ui/modes/poe2_live_terrain/capture_test_page.py` | 深度完整 | 深度完整 | 既有+1 | 核对 capture 后单次读取、窗口依赖注入和失败不清 terrain。 |
| `tools/debug/poe2_live_terrain_localization_probe.py` | 深度完整 | 深度完整 | 既有+1 | 增加通用 hint/radius 搜索窗；不含 PoE 业务术语。 |
| `tools/debug/poe2_anchor_local_registration_probe.py` | 深度完整 | 深度完整 | 2 | 审查后补齐多 basin 判歧义和方向坐标契约。 |

**验证：** 三组核心实验/归档测试 `32 passed`；PoE2 terrain、采集窗口、composition 和主窗口扩大回归 `136 passed`；目标源码 `compileall` 与 `git diff --check` 通过（仅既有 CRLF 提示）。真实样本复跑仍为 `anchored_candidate`，最佳候选保持 `219°/flip/0.85`、锚点误差 `7.1032`，并输出到 `anchor-local-v2/`。
## [SYNC] 2026-09-22 — PoE2 混合实时定位设计与实施计划

### A. SYNC 范围声明

**触发任务：** 用户确认混合实时定位方案，需要落盘完整模块设计、首次定位/局部跟踪/丢失恢复调用链，并拆成可审核的 TDD 实施计划；本轮不编写功能代码。

**直接变更文件：**

- `docs/plans/2026-09-22-poe2-hybrid-localization-design.md`
- `docs/plans/2026-09-22-poe2-hybrid-localization-implementation-plan.md`
- `docs/POE2_LIVE_TERRAIN_CURRENT_STATE.md`
- `ITERATION_LOG.md`
- `CODEBASE.md`（只登记新增规划文档，不把未实现模块写成当前实现）

**预计连带影响：** 后续实施将涉及通用定位状态机、PoE2 内存锚点适配、锚点绝对注册、局部视觉跟踪、实验页 composition 和诊断展示；当前正式 runtime、第一页绘图模式、路径规划、Xbox、Host/LAN 行为均不变。

### C. SYNC 结果

**关键发现：**

- `(verified)` 现有 `MapLocalizer` 已具备 `NEED_GLOBAL -> LOCAL_TRACKING -> RECOVERY_REQUIRED` 的基本状态思想，但 global/recovery 分支会在每次 `update()` 调用 global matcher；不能直接把内存读取放进既有 `_global_match()`，否则失败状态会产生连续读取。
- `(verified)` 旧 `NavigationCore` 的定位顺序是帧间位移、局部模板匹配、失败后下一帧整图匹配；PoE 混合方案只替换绝对定位策略，不改局部成功路径的基本原则。
- `(verified)` 当前 PoE `_global_match()` 是整图 `cv2.matchTemplate()`；已验证的锚点局部注册尚未接 runtime，必须先从 CLI 拆为无文件系统副作用的 `AnchoredAbsoluteRegistrar`。
- `(verified)` `FrameRegistration` 只有 origin/scale，不能完整表达任意旋转、水平镜像、比例和平移；设计新增类型化 `SimilarityTransform2D`，运行必需变换不再藏在 metadata。
- `(design)` 每个 recovery revision 只允许一次内存读取；局部失败在下一帧触发单次恢复，恢复失败后等待显式 retry。首次和恢复调用同一 registrar，同实例 prior 允许锁定方向/镜像/比例只细化平移。

**修订旧结论：** “全局定位”不再定义为搜索整张地图，而定义为恢复可信的绝对地图坐标；PoE 的绝对定位实现采用一次内存锚点加局部视觉注册。

**连带重读文件：** `core/localization/map_localizer.py`、`core/localization/localize_pipeline.py`、`core/localization/navigation_core/relocalization.py`、`features/poe2/live_terrain/runtime.py`、`player_position.py` 及相关 tests。

**CODEBASE.md 更新内容：** 目录文档清单新增两份已批准但尚未实现的设计/实施计划，并明确不得视为当前 runtime 能力；源码架构章节未写入计划模块。

**覆盖进度更新：**

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|---|---|---:|---:|---|
| `core/localization/map_localizer.py` | 深度完整 | 深度完整 | 既有+1 | 重核 global/local/recovery 转移及失败后重复调用边界。 |
| `core/localization/localize_pipeline.py` | 深度完整 | 深度完整 | 既有+1 | 重核 F2F、局部模板和整图回退顺序。 |
| `features/poe2/live_terrain/runtime.py` | 深度完整 | 深度完整 | 既有+1 | 确认 PoE global/local matcher 当前均为模板匹配且未消费锚点。 |
| `features/poe2/live_terrain/player_position.py` | 深度完整 | 深度完整 | 既有+1 | 确认 read_once 每次重新解析地址、校验实例并返回当前 world/grid。 |

**产出：** 完整设计文档和 15 个按 TDD 排序的实施任务已落盘；本轮未修改功能代码、未运行游戏或任何输入/网络链路。

## [SYNC] 2026-09-22 — PoE2 混合实时定位实验实现

### A. 第一轮目标（阅读前声明）

**目标文件：** `models.py`、`contracts.py`、`recovery.py`、`controller.py`、`similarity_search.py`、`absolute_registrar.py`、`memory_anchor.py`、`local_tracker.py`。

**本轮想弄清楚：** 不可变数据契约、一次性恢复许可、锚点注册和有界局部跟踪是否满足已批准状态机；失败帧是否会污染轨迹；同一 recovery revision 是否可能重复读取内存。

### C. 第一轮发现

**关键发现：**

- `(verified)` `HybridLocalizationController` 只在 `NEED_ABSOLUTE/RECOVERY_PENDING` 消费当前 revision；恢复失败进入 `RECOVERY_REQUIRED` 后，普通 `update()` 不再访问 provider，只有显式 `retry_recovery()` 创建新 revision。
- `(verified)` 首次与恢复共用 `AnchoredAbsoluteRegistrar`；无 prior 时搜索旋转/镜像/比例/平移，有同实例 prior 时把角度、镜像和比例固定为一个组合，只重新估计平移。
- `(verified)` `VisualLocalTracker` 只调用 `LocalMapMatcher.match()` 的有界平移窗口，不包含整图回退；成功结果保留已确认 transform 的角度、镜像和比例。
- `(verified)` 相似变换 Chamfer 搜索已从 CLI 移到实验 feature 包，两个 debug CLI 只保留样本/诊断 I/O 和兼容导出，生产 `src` 不反向导入 `tools.debug`。

**修订旧结论：** 设计阶段把 `HybridFrame`/`HybridLocalizationState` 标为“按 §6 定义”，但原设计正文没有列出两者字段。实现将帧限制为同帧墙体证据、人物局部点和时间/帧号；状态显式区分本帧 `position` 与 `latest_confirmed_position`，失败帧不追加轨迹。

**覆盖进度更新：**

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|---|---|---:|---:|---|
| `experimental/hybrid_localization/models.py` | 新增 | 深度完整 | 1 | 核对有限值、只读数组、transform、registration、frame/state 快照和失败帧契约。 |
| `experimental/hybrid_localization/contracts.py` | 新增 | 深度完整 | 1 | 核对三个 runtime-checkable 协议及 terrain/frame/registration 参数边界。 |
| `experimental/hybrid_localization/recovery.py` | 新增 | 深度完整 | 1 | 核对 revision 创建、一次消费和旧 revision 拒绝规则。 |
| `experimental/hybrid_localization/controller.py` | 新增 | 深度完整 | 2 | 逐分支核对首次、局部成功、局部失败、恢复失败、显式 retry、stop/reset 和轨迹更新。 |
| `experimental/hybrid_localization/similarity_search.py` | 新增 | 深度完整 | 2 | 核对从 CLI 原样迁移的变换、粗搜、细搜、锚点前置窗口和候选去重数值逻辑。 |
| `experimental/hybrid_localization/absolute_registrar.py` | 新增 | 深度完整 | 2 | 核对 reference 转 terrain、两阶段锚点匹配、prior 锁定和 typed result 映射。 |
| `experimental/hybrid_localization/memory_anchor.py` | 新增 | 深度完整 | 1 | 核对单次 read、方向坐标变换、时间解析、失败传播和诊断计数。 |
| `experimental/hybrid_localization/local_tracker.py` | 新增 | 深度完整 | 1 | 核对固定 similarity transform、有界 matcher、global position 恢复和 fail closed。 |

### A. 第二轮目标（阅读前声明）

**目标文件：** `session.py`、实验 `composition.py`、UI composition、`capture_test_page.py`、`capture_monitor_window.py`、`page.py`、`main_window.py` 及新增集成/架构测试。

**本轮想弄清楚：** 每个 tick 是否只截图/构建一次证据，QTimer 和 session 是否只有一个 owner，实验依赖是否经过 composition 注入，以及 UI 关闭/失败时是否停止读取。

### C. 第二轮发现

**关键发现：**

- `(verified)` session 每 tick 只取一次 config、截图一次、构建一次 evidence，并把唯一 `HybridFrame` 交给 controller；session 不导入 Qt，QTimer 只由采集测试页持有。
- `(verified)` composition 从 snapshot/profile 创建定向 reference、memory anchor、absolute registrar、`MapRuntime + LocalMapMatcher`、controller 和 session；实验包不导入 UI、gamepad、Host 或 LAN。
- `(verified)` 采集测试页在有 terrain 后才允许启动，显示 mode/source/confidence/position/read count/revision；失败帧保留底图和旧轨迹但不画新点。独立监控窗口只镜像同一 session 的状态，不创建第二套读取链路。
- `(verified)` 五帧集成序列只读取两次内存；恢复失败后连续十帧 read count 不变，显式 retry 后只增加一次。

**修订旧结论：** 数据采集测试页不再“只负责截图/地图且绝不启动定位”；它现在可以启动独立的混合定位实验 session，但仍不接正式 `Poe2LocalizationRuntime`、路线规划或输入执行。

**CODEBASE.md 更新内容：** §2 新增实验包逐文件目录项；§4/§5 增加模型、状态机、算法、适配器、session/composition/UI 职责；§6 新增 F-POE2-HYBRID-LOCALIZATION；§8 增加状态和 transform 契约；§9 增加参数泛化、同步耗时和内存读取门风险。

**覆盖进度更新：**

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|---|---|---:|---:|---|
| `experimental/hybrid_localization/session.py` | 新增 | 深度完整 | 1 | 核对 active gate、单帧构建、listener、reset/retry 和无 Qt 边界。 |
| `experimental/hybrid_localization/composition.py` | 新增 | 深度完整 | 2 | 核对 reference 方向、matcher runtime、PoE evidence builder 和六组件装配。 |
| `ui/modes/poe2/composition.py` | 深度完整 | 深度完整 | 既有+1 | 增加只接 snapshot/config 的实验 factory，继续复制 dedicated recognizer 状态。 |
| `ui/modes/poe2_live_terrain/capture_test_page.py` | 深度完整 | 深度完整 | 既有+2 | 核对唯一 QTimer/session owner、按钮门、状态日志、overlay 和 shutdown。 |
| `ui/modes/poe2_live_terrain/capture_monitor_window.py` | 深度完整 | 深度完整 | 既有+1 | 只镜像 hybrid state/read count 和 terrain overlay，不读取内存。 |
| `tests/poe2_live_terrain/test_hybrid_localization_integration.py` | 新增 | 深度完整 | 1 | 覆盖五帧恢复成功链和十帧恢复失败 fence。 |
| `tests/test_architecture_boundaries.py` | 深度完整 | 深度完整 | 既有+1 | 增加实验包禁止 UI/PySide6/输入执行依赖规则。 |

**验证：** 混合定位与旧 CLI 聚焦回归通过；PoE2 terrain、采集 UI、composition、主窗口和架构完整相关回归 `187 passed`；`compileall` 与 `git diff --check` 通过。真实历史样本保持 `219°/flip/0.85`、锚点误差 `7.1032`。本轮未启动游戏、Xbox、键鼠、Host 或 LAN；实时连续轨迹仍待实机验收。

## [SYNC] 2026-09-22 16:10 — 修复 PoE2 混合定位粗搜索漏解

### A. SYNC 范围声明

**触发任务：** 实机首次绝对注册稳定失败；已用实时帧确认正确的 `219° / 水平镜像 / 0.85` 候选可达到 `0.616` 分、锚点误差 `3.69`，但默认粗搜索在全局截断时将其淘汰。

**直接变更文件：** `experimental/hybrid_localization/similarity_search.py`、`absolute_registrar.py`、`controller.py`、`capture_test_page.py` 及对应定位/UI 测试。

**预计连带影响：** `search_candidates()` 的粗候选保留契约、`AnchoredAbsoluteRegistrar.register()` 的失败诊断、`HybridLocalizationController._attempt_absolute()` 的失败状态、采集页状态文本，以及 `F-POE2-HYBRID-LOCALIZATION` 首帧/恢复调用链；不改正式 `Poe2LocalizationRuntime`，不触发输入、Host 或 LAN。

### C. SYNC 结果

**根因与修复：**

- `(verified)` 实机失败帧的地图实例、人物锚点、截图和墙体 mask 均有效；默认粗搜却让人物落在不可行走区的小比例候选占用全局 Top-K。`_coarse_search()` 现在在截断前按变换后人物点附近的 terrain walkable 排序，但容量允许时仍保留不可行走候选供后续评分/诊断。
- `(verified)` 正确 `225°/flip` 方向 basin 已进入粗候选，但旧 `_refine_seeds()` 只按角度/镜像去重，`scale=1.15` 会阻止 `scale=0.85` 进入精细搜索。现在最多选择 4 个方向 basin，并在 basin 内跳过比例半径重叠项、轮询保留最多 8 个比例分离种子；默认粗分差窗口从 `0.06` 调整为 `0.10`。
- `(verified)` 同一实时失败帧修复后输出 `215°/flip/0.91`、结构分 `0.650`、锚点误差 `4.26`、首二名 anchored margin `0.040`，不再落入 `absolute_registration_failed`。
- `(verified)` registrar 现在无论成功或失败都更新 `last_diagnostics`；controller 把失败诊断复制进 state，采集页显示/记录具体拒绝原因及最佳候选分数、覆盖率、角度、比例和锚点误差。

**修订旧结论：** 旧文档认为“最多 4 个角度/镜像 basin”足以代表细化空间；实时帧证明同一方向下存在多个相互分离的比例峰，按方向去重会在正确比例进入精搜前将其淘汰。现在方向盆地上限与总比例种子上限分离。

**连带重读文件：** `similarity_search.py`、`absolute_registrar.py`、`contracts.py`、`controller.py`、`capture_test_page.py` 及对应 registrar/controller/session/UI 测试。

**CODEBASE.md 更新内容：** §4/§5 更新粗 Top-K 可行走优先级、多比例峰种子选择、registrar 失败诊断和 UI 状态展示；§6 更新 `F-POE2-HYBRID-LOCALIZATION` 第 6/9 跳；§9 修订多地图参数风险。`docs/POE2_LIVE_TERRAIN_CURRENT_STATE.md` 新增实机漏解复现、修复证据和剩余验收边界。

**覆盖进度更新：**

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|---|---|---:|---:|---|
| `experimental/hybrid_localization/similarity_search.py` | 深度完整 | 深度完整 | 3 | 新增粗截断前人物可行走排序及邻域半径校验；保留非 walkable 候选以维持诊断契约。 |
| `experimental/hybrid_localization/absolute_registrar.py` | 深度完整 | 深度完整 | 3 | 将方向盆地与比例峰分开采样，并为成功/拒绝统一发布完整候选诊断。 |
| `experimental/hybrid_localization/contracts.py` | 深度完整 | 深度完整 | 2 | `AbsoluteRegistrar` 显式要求 `last_diagnostics`，失败返回 None 时仍可审计。 |
| `experimental/hybrid_localization/controller.py` | 深度完整 | 深度完整 | 3 | 绝对注册返回 None 时复制 registrar diagnostics，不改变一次性恢复读取门。 |
| `ui/modes/poe2_live_terrain/capture_test_page.py` | 深度完整 | 深度完整 | 既有+3 | 状态栏和日志新增拒绝原因、分数、覆盖率、角度、比例及锚点误差。 |
| `tests/poe2_live_terrain/test_hybrid_similarity_search.py` | 深度完整 | 深度完整 | 2 | 覆盖不可行走干扰候选不得抢占 coarse Top-K，同时保留既有双候选契约。 |
| `tests/poe2_live_terrain/test_hybrid_absolute_registrar.py` | 深度完整 | 深度完整 | 2 | 覆盖同方向分离比例峰和被拒注册的完整 diagnostics。 |
| `tests/poe2_live_terrain/test_hybrid_localization_controller.py` | 深度完整 | 深度完整 | 2 | 覆盖 registrar 失败诊断传播到状态。 |
| `tests/test_poe2_capture_test_page.py` | 深度完整 | 深度完整 | 既有+3 | 覆盖失败候选数值在 UI 状态文本中可见。 |

**验证：** 混合定位、PoE2 UI、composition 与架构相关回归 `197 passed`；`compileall` 和 `git diff --check` 通过。真实完整 tick 输出 `local_tracking / anchored_absolute / confidence=0.724 / position=(312.60,400.86) / reads=1`。未发送 Xbox、键鼠、Host 或 LAN 输入。连续移动、视觉丢失恢复和多地图仍待实机验收。
## [SYNC] 2026-09-22 16:54 — PoE2 混合定位实机整链路排查

### A. SYNC 范围声明
**触发任务：** 在游戏已运行的同一现场，获取第一帧截图、地形与人物内存锚点，复现实验并定位混合定位链路的真实故障，再以回归测试约束修复。
**直接变更文件：** 待根因确认后限定在 `src/auto_modules/features/poe2/live_terrain/experimental/` 的定位实验模块、对应测试，以及本断点文档。
**预计连带影响：** `Poe2CaptureTestPage.start_hybrid_localization()`、`Poe2HybridLocalizationSession.tick()`、`_Poe2EvidenceBuilder.build()`、`AnchoredAbsoluteRegistrar.register()`、`VisualLocalTracker.track()`、地图展示坐标映射及相关测试；不接正式运行时，不发送真实输入或网络同步。

### C. SYNC 结果

**关键发现：**

- `(verified)` 16:49 实机日志显示首帧 `anchored_absolute` 成功后，下一帧立即 `local_tracking_failed`；每次 5 秒恢复成功后下一帧仍失败，read count 最终从 1 增到 5。问题不在内存锚点读取或 QTimer。
- `(verified)` 局部 matcher 输入的是 filled blocked layer，实测候选为 `mean_wall_error_px=0.0/candidate_margin=0.0`。大面积零距离平原使任何局部平移都同分，`LocalMapMatcher` 按契约拒绝歧义候选。
- `(verified)` 同一 filled layer 也让绝对注册产生多个偶然方向；改用 walkable 薄边界后，首帧从 7 个跨方向候选收敛为 2 个同 basin 候选，最佳为 `221°/flip/0.79`，锚点误差从 `10.6150` 降为 `0.6635`。
- `(verified)` PoE2 独立 factory 现显式应用当前非空 profile 识别参数；绝对注册和局部 matcher 共用 `reference_boundary_layer()`；局部 matcher 仅在 PoE2 实验组合层使用实测 `max_error=4.0/min_margin=0.02`，通用默认值未改。
- `(verified)` 修复后实机 factory 连跑 12 帧全部成功：1 帧 `anchored_absolute`、11 帧 `visual_local`、内存读取总数 1、静止位置抖动不超过 1 像素。

**修订旧结论：** 上一轮把 `215°/flip/0.91` 单次成功视为粗搜索修复证据，但它没有覆盖下一帧。完整链路证明真正阻断持续定位的是 reference 墙层契约错误；filled blocked layer 同时降低首帧唯一性并让局部跟踪必然歧义。

**连带重读文件：** `absolute_registrar.py`、`composition.py`、`local_tracker.py`、`core/localization/local_matcher.py`、`core/localization/map_runtime.py`、`terrain_reference.py`、UI composition/capture test page 及对应测试。

**CODEBASE.md 更新内容：** §4/§5 更新薄边界派生、识别参数应用和 PoE2 局部阈值；§6 更新 F-POE2-HYBRID-LOCALIZATION 第 2/6/7 跳；§9 登记并关闭 filled wall layer 风险。`docs/POE2_LIVE_TERRAIN_CURRENT_STATE.md` 增加实机断点和证据目录。

**覆盖进度更新：**

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|---|---|---:|---:|---|
| `experimental/hybrid_localization/absolute_registrar.py` | 深度完整 | 深度完整 | 4 | 新增共同薄边界派生；绝对注册不再把 blocked interior 当墙线。 |
| `experimental/hybrid_localization/composition.py` | 深度完整 | 深度完整 | 3 | factory 应用 profile 参数，以边界 distance field 和 PoE2 实测容差装配 local matcher。 |
| `experimental/hybrid_localization/local_tracker.py` | 深度完整 | 深度完整 | 2 | 实机核对 transform top-left、transformed player 与 matcher origin 坐标契约一致。 |
| `core/localization/local_matcher.py` | 深度完整 | 深度完整 | 既有+1 | 确认失败来自输入 distance field 的零值平原，不修改通用算法/默认阈值。 |
| `features/poe2/live_terrain/terrain_reference.py` | 深度完整 | 深度完整 | 既有+1 | 保留 blocked/unknown 的通用 wall-layer 契约，由实验适配器派生视觉边界。 |
| `tests/poe2_live_terrain/test_hybrid_absolute_registrar.py` | 深度完整 | 深度完整 | 3 | 新增 blocked interior 排除和边界两侧像素契约测试。 |
| `tests/test_poe2_composition.py` | 深度完整 | 深度完整 | 既有+2 | 新增 profile 参数、薄边界 runtime 和 PoE2 local matcher 容差装配测试。 |

**验证：** 先以失败测试确认 `reference_boundary_layer` 缺失；实现后聚焦 `13 passed`，扩大 PoE2/混合定位/UI/架构回归 `197 passed`，`compileall`、`git diff --check` 通过。Serena composition 类型诊断已清零；仅外部包解析受其 Python 环境影响。实机报告位于 `live-fixed-chain-20260922-171832/report.json`。

## [SYNC] 2026-09-22 17:58 — PoE2 GUI 混合定位失败复现

### A. SYNC 范围声明

**触发任务：** 复现并定位 GUI 中混合定位持续进入 `recovery_required`、没有可信位置的问题；若证据证明本地 profile 参数错误，则直接修正配置并沿 GUI 同一路径验证。

**直接检查/可能变更文件：**
- `data/logs/poe2_live_terrain.log`（定位最新 GUI 会话的首个失败点）
- `data/poe2_live_terrain/monitor_profiles/a6ccb4c6767e.json`（核对并在证据充分时修正当前识别参数）
- `src/auto_modules/features/poe2/live_terrain/ui/capture_test_page.py`（核对页面配置应用、会话重建与 hybrid 状态展示）
- `src/auto_modules/features/poe2/live_terrain/experimental/hybrid_localization/composition.py`（核对 GUI factory 与已验证独立链装配是否一致）
- `src/auto_modules/features/poe2/live_terrain/experimental/hybrid_localization/controller.py`（核对恢复事件、diagnostics 和 revision 流转）
- `src/auto_modules/features/poe2/live_terrain/experimental/hybrid_localization/session.py`（核对截图与内存锚点的采样顺序）
- `src/auto_modules/features/poe2/live_terrain/experimental/hybrid_localization/contracts.py`（核对最小接口扩展边界）
- `src/auto_modules/ui/modes/poe2/composition.py`（用正式页面装配驱动实机 GUI 链验证）
- `tests/poe2_live_terrain/test_hybrid_localization_controller.py`、`tests/poe2_live_terrain/test_hybrid_localization_session.py`（先固化恢复时序与瞬时失败复现）

**预计连带影响：** profile toolbar 与页面激活配置、截图识别器全局参数、当前 terrain snapshot 生命周期、绝对锚定和局部 matcher 输入、GUI 日志与状态面板。只在根因确认后做单点修改；不接正式 runtime，不触发输入或网络行为。

### C. SYNC 结果

**关键发现：**

- `(verified)` GUI 最新会话首帧和连续局部链实际成功：`221°/flip/0.79` 后持续约 5.6 秒 `visual_local`，reads=1。截图只展示了后续失败状态，不能据此认定 profile 或首帧注册失败。
- `(verified)` `17:54:25` 局部丢失后，旧实现已先捕获 frame，随后人物内存读取耗时约 6 秒；恢复候选仍锁定正确方向，但新锚点相对旧截图误差 `19.0526`，超过门槛而拒绝。根因是跨组件采样错时，不是 HSV 参数。
- `(verified)` controller 新增 `prepare_capture()`，按 revision 读取并缓存一个待配对锚点；session 在锚点准备完成后才截图，`update()` 只消费缓存，不重复读取。正常局部帧不触发 provider，stop/reset/retry 清除待配对状态。
- `(verified)` 正式 UI composition 与实际 `Poe2LiveTerrainPage/Poe2CaptureTestPage` 链实机重跑：首帧 `anchored_absolute` 为 `219°/flip/0.75`、anchor error `2.13`，后续 12 帧全为 `visual_local`，reads 保持 1。当前 profile 参数有效，未修改 `a6ccb4c6767e.json`。

**修订旧结论：** 用户截图中的 `recovery_required` 是局部跟踪在成功运行后丢失、恢复采样错时造成的终态，不是 GUI 没有加载薄边界修复，也不是当前颜色参数错误。

**连带重读文件：** `controller.py`、`session.py`、`contracts.py`、`composition.py`、UI capture test page、当前 profile、最新 GUI 日志及两份对应测试。

**CODEBASE.md 更新内容：** §4/§5 更新 controller 待配对锚点与 session 采样顺序；§6 更新 F-POE2-HYBRID-LOCALIZATION 第 3-5 跳；§9 关闭截图/锚点错时风险。断点文档追加正式页面实机结果。

**覆盖进度更新：**

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|---|---:|---:|---:|---|
| `experimental/hybrid_localization/controller.py` | 深度完整 | 深度完整 | 4 | 新增按 revision 缓存/消费待配对锚点，核对所有清理和失败分支。 |
| `experimental/hybrid_localization/session.py` | 深度完整 | 深度完整 | 2 | 将锚点准备移到截图前，确认局部帧不读内存且失败准备不截图。 |
| `experimental/hybrid_localization/contracts.py` | 深度完整 | 深度完整 | 既有+1 | 确认 provider 协议无需扩展，采样编排保持在 controller/session。 |
| `ui/modes/poe2/composition.py` | 深度完整 | 深度完整 | 既有+1 | 以正式 composition 驱动页面实机链，确认 profile/recognizer/snapshot 传播一致。 |
| `tests/poe2_live_terrain/test_hybrid_localization_controller.py` | 深度完整 | 深度完整 | 3 | 新增 prepare 后 update 复用同一锚点且只读一次的回归。 |
| `tests/poe2_live_terrain/test_hybrid_localization_session.py` | 深度完整 | 深度完整 | 2 | 新增事件序列断言 `prepare -> capture -> update`。 |

**验证：** 两个新增约束先得到 2 个预期失败，实现后 controller `7 passed`、session `4 passed`；本轮第一次 PoE2 相关回归 `170 passed`，正式页面实机 1 次首帧 + 12 次局部帧全部成功；`compileall`、`git diff --check` 通过。全项目断言结果 `662 passed, 1 skipped, 10 subtests passed`，3 个既有 pathfinder 策略测试失败。独立复跑 capture-test page 时 9 条断言均通过，但 pytest 在最终 Qt GC 阶段发生 Windows heap `0xc0000374`，因此该次进程退出不记为通过。

## [设计探索] 2026-09-22 18:53 — PoE2 正式实时视觉位置跟踪

### A. 本轮目标（阅读前声明）

**目标文件：**
- `src/auto_modules/ui/modes/poe2_live_terrain/page.py`（确认正式 PoE2 页面当前按钮、timer、地图 overlay 和测试 tab 边界）
- `src/auto_modules/ui/modes/poe2/composition.py`（确认正式页面可注入的运行时与实验 hybrid factory）
- `src/auto_modules/features/poe2/live_terrain/runtime.py`（确认旧正式定位运行时职责，避免并存两个位置 owner）
- `src/auto_modules/features/poe2/live_terrain/experimental/hybrid_localization/controller.py`（确认“仅首帧内存”与当前恢复状态机的策略差异）
- `src/auto_modules/features/poe2/live_terrain/experimental/hybrid_localization/session.py`（确认持续视觉 tick 与 UI timer 的归属）
- `src/auto_modules/features/poe2/live_terrain/ui/presenter.py`（确认大地图当前位置/轨迹可视化可直接复用）

**本轮想弄清楚：** 正式页面应复用哪些已验证底层组件、谁拥有唯一实时定位 session/timer/state、数据采集 tab 如何退回纯实验工具，以及“视觉丢失后是否绝不再次读内存”的明确策略边界。设计获用户批准前不修改实现。

### C. 本轮发现

**关键发现：**

- `(verified)` 正式 `Poe2LiveTerrainPage` 已具备完整产品壳：初始化/抓图/开始与停止监控、唯一 `monitor_timer`、小地图 processed/match 预览、完整 terrain `ScalableMapWidget`，以及 `present_localization_overlay()` 对当前位置和轨迹的实时绘制。
- `(verified)` 正式页当前 timer 调用旧 `Poe2LocalizationRuntime.tick()`；已验证的 hybrid factory/session/controller 只注入内部 `Poe2CaptureTestPage`，由测试页另持一个 `hybrid_timer`。因此现在存在两个定位装配点，产品页没有消费 hybrid state。
- `(verified)` `present_localization_overlay()` 已同时兼容正式 state 与 `HybridLocalizationState` 的 `position/trajectory` 字段；大地图可视化无需复制或新建渲染算法。
- `(verified)` 当前 hybrid controller 的恢复策略会在局部视觉丢失后建立新 revision，并允许再次读一次内存；用户新要求“只第一帧读内存”会改变 controller policy，而不仅是把按钮从测试页挪到正式页。

**修订旧结论：** 不需要新建另一个正式页面或复制采集页布局。现有正式 live tab 就是产品入口；应替换其 runtime composition，并让测试 tab 只保留采集/算法诊断。

**新疑问：** 视觉局部匹配丢失后，是永久 fail closed 等待用户重新开始（严格首帧只读），还是允许用户手动点击一次“重新锚定”再读内存；两者决定状态机和产品操作边界。

**更新了 CODEBASE.md：** §3/§6 补充正式页与测试页当前双定位 owner，以及 overlay 已可复用的现状。

**覆盖进度更新：**

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|---|---:|---:|---:|---|
| `ui/modes/poe2_live_terrain/page.py` | 深度完整 | 深度完整 | 既有+1 | 正式页已有唯一 monitor timer 和大地图 overlay，但仍调用旧 runtime。 |
| `ui/modes/poe2/composition.py` | 深度完整 | 深度完整 | 既有+2 | 同时装配旧正式 runtime 与仅供测试页使用的 hybrid factory。 |
| `features/poe2/live_terrain/runtime.py` | 深度完整 | 深度完整 | 既有+1 | 旧 runtime 自有定位状态机，不能与 hybrid 同时作为产品位置 owner。 |
| `experimental/hybrid_localization/controller.py` | 深度完整 | 深度完整 | 5 | 当前局部失败会开启可再次读取内存的 recovery revision。 |
| `experimental/hybrid_localization/session.py` | 深度完整 | 深度完整 | 3 | session 无 Qt，适合由正式页 timer 唯一驱动。 |
| `ui/modes/poe2_live_terrain/presenter.py` | 深度完整 | 深度完整 | 既有+1 | overlay 已通过 position/trajectory 鸭子类型兼容 hybrid state。 |

**下一轮计划：** 用户确认视觉丢失后的内存读取策略后，给出 2-3 种正式接入方案及推荐设计；设计批准前不修改实现。

## [设计探索] 2026-09-22 18:56 — 对齐导航模式的事件触发全局恢复

### A. 本轮目标（阅读前声明）

**目标文件：**
- `src/auto_modules/core/localization/map_localizer.py`（核对通用局部失败转全局定位状态机）
- `src/auto_modules/ui/modes/navigation/runtime/localization_tick.py`（核对导航页面每帧截图与定位调用链）
- `src/auto_modules/core/navigation_tasks/controller_runtime/relocalization.py`（核对导航任务如何请求全局重定位）
- `src/auto_modules/ui/modes/navigation/runtime/` 中消费重定位 intent 的入口（确认请求与实际执行边界）
- `src/auto_modules/features/poe2/live_terrain/experimental/hybrid_localization/controller.py`（映射 PoE2 内存锚点恢复到通用导航语义）

**本轮想弄清楚：** 复用导航模式的触发语义与状态流，而不是复用其具体全图视觉搜索；确认 PoE2 应如何以一次内存锚点读取实现同等的 global relocalization，并保持正常帧纯视觉。

## [设计批准] 2026-09-22 — PoE2 正式实时视觉定位

### A. 决策

用户批准方案 1：参考导航模式的 `NEED_GLOBAL -> LOCAL_TRACKING -> RECOVERY_REQUIRED -> global recovery` 状态语义，但保留 PoE2 hybrid controller/session 作为具体实现。PoE2 的全局定位为“单次内存锚点读取 + 立即截图 + 锚点约束绝对注册”，正常帧为纯视觉局部跟踪；视觉丢失后自动开放一次恢复读取，恢复失败后不连续轮询内存。

### B. 正式接入边界

- `Poe2LiveTerrainPage.monitor_timer` 是唯一产品定位 timer。
- 正式页持有产品 runtime/state，并复用现有大地图 overlay。
- hybrid 算法仍位于 PoE2 实验模块，新增薄产品运行时适配器，不把 PoE2 内存语义放入通用 `MapLocalizer`。
- 嵌入正式页的数据采集 tab 不再获得活动 hybrid factory；截图、样本、拼图和独立算法诊断能力保留。
- 本阶段不执行输入、导航路线、Host 或网络同步。

### C. 文档

- `docs/plans/2026-09-22-poe2-production-visual-localization-design.md`
- `docs/plans/2026-09-22-poe2-production-visual-localization-implementation-plan.md`

下一阶段按实施计划以 TDD 接入正式 runtime、页面状态和唯一 owner，并同步 `CODEBASE.md` 与当前状态断点。

## [SYNC] 2026-09-22 — PoE2 正式实时视觉定位接入

### A. SYNC 范围声明

**触发任务：** 按已批准设计把 hybrid 定位接入正式 PoE2 实时地形页面，并重点验证局部视觉丢失必定触发一次全局恢复；正常视觉帧不得读取内存，恢复失败后不得连续轮询内存。

**直接变更文件：**
- `src/auto_modules/features/poe2/live_terrain/hybrid_product_runtime.py`（新增正式产品运行时适配器）
- `src/auto_modules/features/poe2/live_terrain/experimental/hybrid_localization/session.py`（暴露最近视觉帧/证据供正式页面展示）
- `src/auto_modules/features/poe2/live_terrain/__init__.py`（导出产品运行时契约）
- `src/auto_modules/ui/modes/poe2/composition.py`（正式页面改用 hybrid 产品运行时）
- `src/auto_modules/ui/modes/poe2_live_terrain/page.py`（正式页面消费 hybrid 状态并保持唯一 timer）
- `tests/poe2_live_terrain/test_hybrid_product_runtime.py`（新增产品运行时和恢复触发测试）
- `tests/poe2_live_terrain/test_hybrid_localization_session.py`（最近视觉帧生命周期测试）
- `tests/test_poe2_composition.py`、`tests/test_poe2_live_terrain_monitoring.py`、`tests/test_poe2_live_terrain_page.py`（composition/UI/唯一 owner 回归）

**预计连带影响：** `HybridLocalizationController` 的 `RECOVERY_PENDING` 自动恢复、`Poe2HybridLocalizationSession.tick()` 的锚点读取和截图顺序、正式页面 `capture_map/start_monitoring/_tick_runtime/handle_runtime_state`、大地图 overlay、嵌入数据采集页的 hybrid factory 所有权。不会修改第一页绘图模式，不触发真实输入、Host 或网络同步。

### C. SYNC 结果

**关键发现：**

- `(verified)` 新增 `Poe2HybridProductRuntime`，正式页面通过它管理 snapshot/config/experiment，页面 `monitor_timer` 是唯一产品定位驱动；运行时不拥有 Qt，也不实现匹配算法。
- `(verified)` session 在构造 visual evidence 后保存 `last_raw_frame/last_evidence/last_frame`，产品状态将其与 hybrid state 合并，正式页可继续显示预处理和 wall mask，而无需复制识别逻辑。
- `(verified)` 正式 PoE2 composition 已停止注入旧 `Poe2LocalizationRuntime`，改为注入 hybrid 产品 runtime；旧 runtime 模块保留，未破坏其独立测试。
- `(verified)` 嵌入正式页的数据采集 tab 的 `hybrid_localization_factory=None`，不会与正式页形成双 timer/双位置 owner；页面类的独立诊断能力仍保留。监控配置弹窗改用 composition 单独注入的 preview/recognizer 依赖，不依赖新 runtime 模拟旧私有接口。
- `(verified)` 使用真实 controller + session + 产品 runtime 的五帧测试得到 `anchored_absolute -> visual_local -> failed/RECOVERY_PENDING -> anchored_absolute -> visual_local`，锚点读取总数为 2。恢复失败后连续 5 tick 保持 `RECOVERY_REQUIRED` 且不增加读取，因此视觉丢失触发和单次读取门均有回归保护。

**修订旧结论：** 正式页不再驱动旧 `Poe2LocalizationRuntime`，hybrid 也不再只存在于采集测试页；当前正式产品链已经是唯一 `Poe2HybridProductRuntime -> Poe2HybridLocalizationSession`。

**连带重读文件：** `hybrid_product_runtime.py`、hybrid `session/controller/models/memory_anchor`、PoE2 composition、正式 page、presenter、capture test page 及对应 runtime/session/composition/UI/architecture tests。

**CODEBASE.md 更新内容：** §2 增加产品 runtime 文件；§3/§4 更新正式页唯一 owner 和新运行时职责；§5 记录 runtime/session 生命周期及视觉状态适配；§6 重写 F-POE2-HYBRID-LOCALIZATION 和 F-POE2-LOC 正式链；§9 关闭旧 runtime 与测试页双 owner 风险。

**覆盖进度更新：**

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|---|---:|---:|---:|---|
| `features/poe2/live_terrain/hybrid_product_runtime.py` | 新增 | 深度完整 | 1 | 核对 snapshot/config/experiment 生命周期、展示 DTO、读取计数和异常传播。 |
| `experimental/hybrid_localization/session.py` | 深度完整 | 深度完整 | 4 | 新增最近 raw/evidence/frame 所有权，确认锚点准备仍严格早于截图。 |
| `ui/modes/poe2/composition.py` | 深度完整 | 深度完整 | 既有+2 | 正式 runtime 替换为 hybrid 产品适配器，专用 recognizer 和 factory 仍隔离。 |
| `ui/modes/poe2_live_terrain/page.py` | 深度完整 | 深度完整 | 既有+2 | 消费 hybrid reason/revision/read count，保留失败 timer，并禁止嵌入采集 tab 持有 hybrid factory。 |
| `tests/poe2_live_terrain/test_hybrid_product_runtime.py` | 新增 | 深度完整 | 1 | 覆盖生命周期、视觉 DTO、自动恢复触发和失败后停止读取。 |
| `tests/test_architecture_boundaries.py` | 深度完整 | 深度完整 | 既有+1 | 架构契约更新为正式 hybrid runtime，继续验证 recognizer 独立副本。 |

**验证：** 首轮 runtime/session/composition `13 passed`；页面红测准确命中旧状态字段和双 owner；关键调用链 `32 passed`；差异审查额外发现并以红测修复监控配置预览依赖。扩大 PoE2/hybrid/composition/UI/config-dialog/main-window/architecture 回归最终 `199 passed`。`compileall`、`git diff --check` 通过。Serena 对产品 runtime/session/composition 无诊断；page 的两条提示仅为 Serena Python 环境无法解析已安装在项目虚拟环境中的 PySide6。

**下一步：** 启动新版工作台进行实机验收，先验证移动轨迹连续，再通过临时遮挡/丢帧观察一次 `RECOVERY_PENDING -> anchored_absolute`，确认 read count 只增加 1；随后换图验证随机方向。

## [SYNC] 2026-09-22 — PoE2 卡顿与恢复失败诊断

### A. SYNC 范围声明

**触发任务：** 用户实机反馈正式定位页面明显卡顿，疑似持续重定位；要求增强日志，并在定位失败时自动保存截图、地图和状态快照。

**直接变更文件：**
- `src/auto_modules/features/poe2/live_terrain/hybrid_product_runtime.py`（状态变化日志、失败快照去重、性能摘要）
- `src/auto_modules/features/poe2/live_terrain/hybrid_failure_archive.py`（新增失败视觉/terrain/state 归档适配器）
- `src/auto_modules/ui/modes/poe2/composition.py`（注入失败归档）
- `src/auto_modules/ui/modes/poe2_live_terrain/page.py`（终态暂停 timer、显式重新定位、overlay 去重、UI 性能日志）
- 对应 runtime/archive/page/composition 测试与项目状态文档。

**预计连带影响：** `RECOVERY_PENDING -> RECOVERY_REQUIRED` 页面生命周期、`CaptureSampleArchive` 显式文件输出、正式页按钮状态和大地图 presenter 调用频率。不会改变 matcher/registrar 阈值，不会增加内存读取次数，不触发输入、Host 或网络同步。

**根因证据：** 最新会话 `20:05:25` 以 33ms interval 启动，先有 128 帧 `LOCAL_TRACKING`；置信度从长期 `0.163` 降到 `0.109/0.081` 后在 `20:05:38.024` 进入 `RECOVERY_PENDING`。下一次自动读取使 read count `3 -> 4`，约 5.37 秒后以 `absolute_registration_failed` 进入 `RECOVERY_REQUIRED`。随后 12.6 秒内重复发布 271 个相同终态，read count 保持 4，证明不是连续内存重定位，而是终态 timer、日志和完整地图重绘空转。当前日志没有 registrar diagnostics，磁盘也没有对应失败帧归档。

## [SYNC] 2026-09-22 — 首帧匹配重复候选与锚点容差修复

### A. SYNC 范围声明

**触发任务：** 用户实机反馈首帧经常匹配失败，怀疑匹配逻辑重复执行；要求优先稳定匹配，暂不处理耗时/线程架构。

**直接变更文件：**
- `src/auto_modules/features/poe2/live_terrain/experimental/hybrid_localization/absolute_registrar.py`（锚点近邻容差、精搜候选去重、诊断字段）
- `tests/poe2_live_terrain/test_hybrid_absolute_registrar.py`（锚点容差和重复候选回归）
- `docs/POE2_NAVIGATION_COMPATIBLE_TRACKING_CURRENT_STATE.md`（实机排查断点）

**预计连带影响：** 首帧/恢复 `AnchoredAbsoluteRegistrar.register()` 的候选判定和 diagnostics；不改变 controller 的恢复次数、内存读取策略、正常视觉跟踪或第一页绘图模式。

### C. SYNC 结果

**关键发现：** (verified) 同一恢复版本内 `session.tick()` 只注册一次；失败后 controller 进入 `RECOVERY_REQUIRED`，页面停止 timer，日志中的多次匹配对应用户多次显式重试。真正的匹配问题是精搜不同 seed 产生完全相同的候选，原 `_result_status()` 把重复项当成第二名，分差为 0，从而错误返回 `ambiguous`。

**实现结果：**
- 新增 `_deduplicate_anchored_candidates()`，仅去除相同镜像、角度差不超过 `0.5°`、比例差不超过 `0.01`、人物全局位置差不超过 `2px` 的重复 refined candidate；不同角度/镜像即使中心相同仍保留，用于真实方向歧义判断。
- 当候选距可信内存锚点不超过 `8px`、人物位于 walkable terrain 且 coverage 不低于 `0.60` 时，允许略低于普通 `0.65` 的 forward coverage；普通候选仍使用原严格门槛。
- diagnostics 现在记录普通/锚点近邻 coverage 阈值和锚点接受半径，方便后续实机核对。

**实证验证：** 复用失败快照并以接近真实锚点 `(347, 406)` 复测，结果从 `ambiguous/rejected` 变为 `anchored_candidate`，最佳 `219° / horizontal reflection=true / scale=0.81`，锚点误差约 `3.14px`，`forward_coverage=0.6336`；聚焦测试 `14 passed`。这只证明候选判定修复，尚未证明实机首帧在所有地图稳定。

**下一步：** 用实际运行重新获取一帧，确认日志 `status=anchored_candidate`、不出现同候选重复项；再验证成功后人物移动的 `visual_f2f`。性能和异步化暂按用户要求留到后续。

### C. SYNC 结果

**连带重读文件：** `absolute_registrar.py` 的 `AnchoredRegistrationConfig`、`_deduplicate_anchored_candidates()`、`_result_status()`、`match_anchor_local()`、`register()`；`test_hybrid_absolute_registrar.py` 的注册器和状态门测试；CodeGraph 重新确认上述函数的调用方仅为 hybrid registrar 与对应测试。

**CODEBASE.md 更新内容：** 更新 PoE2 absolute registrar 的算法步骤和 P1 风险，记录 refine 重复候选去重、近锚点 coverage 容差、诊断字段及其尚未完成的多地图校准风险。

**验证：** 相关回归 `31 passed`；失败快照接近真实锚点复测为 `anchored_candidate`；`compileall` 通过；`git diff --check` 通过（仅提示现有文件的 LF/CRLF 转换，不是差异错误）。

**新增 Finding：** 当前修复解决了假 `ambiguous` 和单个实机失败样本的 coverage 边界，但真实锚点需下一次运行确认；没有改变重复 retry 的显式状态机语义，也没有处理注册线程/耗时问题。

## [SYNC] 2026-09-22 — PoE2 导航兼容连续跟踪

### A. SYNC 范围声明

**触发任务：** 用户确认采用方案 A：首帧/恢复使用内存锚点附近形状注册，正常跟踪复用导航模式的多帧位移预测，局部形状匹配只做纠偏和备用。

**直接变更文件：**
- `src/auto_modules/core/localization/canonical_wall.py`（新增视觉/terrain 墙体形状归一化）
- `src/auto_modules/core/localization/displacement.py`（新增相似变换位移转换）
- `src/auto_modules/core/localization/frame_displacement.py`（新增 phase displacement 质量门控）
- `src/auto_modules/core/localization/__init__.py`（导出新增通用能力）
- `src/auto_modules/features/poe2/live_terrain/experimental/hybrid_localization/absolute_registrar.py`（terrain boundary 改用 canonical 表示）
- `src/auto_modules/features/poe2/live_terrain/experimental/hybrid_localization/local_tracker.py`（位移优先、局部形状 fallback）
- `tests/test_canonical_wall.py`
- `tests/test_displacement.py`
- `tests/test_frame_displacement.py`
- `tests/poe2_live_terrain/test_hybrid_visual_local_tracker.py`
- `docs/POE2_NAVIGATION_COMPATIBLE_TRACKING_CURRENT_STATE.md`
- `docs/POE2_LIVE_TERRAIN_CURRENT_STATE.md`

**预计连带影响：** `LocalMapMatcher` 仍消费同一 `MapRuntime.distance_field`；hybrid controller/session 继续拥有前帧和一次性恢复状态；正式 PoE2 页面只消费来源从 `visual_local` 扩展出的 `visual_f2f`。首帧、恢复、内存读取策略和第一页绘图模式不变。

### C. SYNC 结果

**关键发现：** (verified) 原导航模式先用 `estimate_phase_displacement(prev_wall_mask, wall_mask)` 更新全局位置，只有位移失败才做模板匹配；原 PoE2 `VisualLocalTracker` 之前直接 `del previous_frame`，每帧做半径 `96px` 的局部 Chamfer 搜索，确实偏离了已验证导航链路。

**实现结果：**
- 新增 `canonical_wall_mask` 和 `canonical_boundary_from_walkable`，统一 wall mask 的二值形状契约；
- 新增 `transform_local_displacement`，明确 reflection -> rotation -> scale 的位移转换顺序；
- 新增 `estimate_bounded_displacement`，统一 `phase_failed/low_quality/large_shift/accepted` 结果；
- `VisualLocalTracker` 现在先计算 canonical 帧间位移，接受时输出 `visual_f2f`，位置使用 `previous_position - global_shift`；位移被拒绝才使用有界形状匹配；
- 首帧/同实例恢复继续由 `AnchoredAbsoluteRegistrar` 完成，没有引入全图搜索或额外内存读取。

**验证：** canonical/displacement/tracker/registrar 聚焦回归 `21 passed`，连续 tracker 回放 `5 passed`；PoE2 terrain、hybrid、composition、UI 和 architecture 回归 `204 passed`。连续真实移动、真实遮挡恢复和换图方向仍待实机验证。

**同步结果：** 已重读本轮新增通用模块、`absolute_registrar.py`、`local_tracker.py`、controller/session 调用方和对应测试；`CODEBASE.md` 已同步新增目录职责、三个通用算法模块、canonical terrain boundary 依赖和 tracker 的位移优先算法/调用关系。新增断点文档为 `docs/POE2_NAVIGATION_COMPATIBLE_TRACKING_CURRENT_STATE.md`。

**下一步：** 执行连续帧样本回放、compileall 和实机验收；重点记录 `shift/quality/global_shift/source/position/memory_read_count`，确认位移坐标方向、轨迹连续性和一次性恢复规则。

## [SYNC] 2026-09-22 — tracker 静态类型收紧

### A. SYNC 范围声明

**触发任务：** Serena 诊断发现 `VisualLocalTracker.track()` 对可空 `FrameDisplacement.shift` 的收窄不足。

**直接变更文件：** `src/auto_modules/features/poe2/live_terrain/experimental/hybrid_localization/local_tracker.py`。

**预计连带影响：** 仅影响 tracker 内部局部位移变量的类型收窄；不会改变位移公式、来源、恢复状态或 matcher 调用顺序。

### C. SYNC 结果

**连带重读文件：** `local_tracker.py` 的 `VisualLocalTracker.track()` 及其 tracker/phase 测试。

**结果：** Pyright 仍将 `LocalizationResult.position` 视为可空，已在 accepted displacement 分支增加显式 `None` fail-closed；位移公式和运行状态没有变化。相关 tracker/phase 测试 `7 passed`，compileall 和差异检查通过。外部 `cv2/numpy` unresolved 仍是 Serena 语言服务器未加载项目虚拟环境的既有提示。

## [SYNC] 2026-09-22 — PoE2 全局定位锚点消歧与自动方向展示

### A. SYNC 范围声明

**触发任务：** 用户反馈每次触发全局定位仍可能报错；要求使用已读取的人物内存位置消除候选歧义，并在方向确认后把大地图旋转到与小地图一致；同时恢复数据采集页的混合定位入口。

**直接变更文件：**
- `src/auto_modules/features/poe2/live_terrain/experimental/hybrid_localization/absolute_registrar.py`
- `src/auto_modules/features/poe2/live_terrain/orientation.py`
- `src/auto_modules/ui/modes/poe2_live_terrain/presenter.py`
- `src/auto_modules/ui/modes/poe2_live_terrain/page.py`
- `src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py`
- 相关 PoE2 hybrid/页面测试与 `CODEBASE.md`

**预计连带影响：** 仅影响 PoE2 实验定位候选判定、PoE2 两个页面的地图展示和数据采集页依赖注入；不改变第一页绘图模式、通用输入输出、内存读取次数或正常视觉跟踪状态机。

### C. SYNC 结果

**根因证据：** (verified) 复放 `20260922-144211-152568-MapFlotsam-1E44BF94` 时，视觉分最高候选 `215°/flip/0.89` 的锚点误差为 `7.30px`，第二候选 `182°/flip/1.25` 的锚点误差为 `2.40px`；旧逻辑按 anchored score 排序后两者分差不足，返回 `ambiguous`。用真实内存锚点作为优先空间约束后，结果稳定为 `anchored_candidate`。

**实现结果：**
- `absolute_registrar.py` 新增 `anchor_disambiguation_gap=2px` 和 `_prioritize_memory_anchor()`；候选通过 score/coverage/walkable 门后按锚点误差优先，近锚点候选的空间分离达到间隔时不再因视觉分差小而误报歧义。
- 有 prior 的恢复先做 translation-only；失败时自动在同一已读取锚点下做 `full_similarity_recovery`，diagnostics 增加 `attempt_count`，不增加额外内存读取。
- `presenter.py` 在 registration 成功后对“地图+marker+轨迹”整体执行逆角度/镜像变换，支持任意角度，页面元数据显示自动校准角度。
- `page.py` 把 hybrid factory 传给数据采集 tab；采集页独立创建 experiment/session/timer，可直接复测混合定位，不与正式 runtime 共享状态。
- 修复 `hybrid_failure_archive.py` 对 `SimilarityTransform2D.angle_degrees` 的错误字段访问，确保恢复失败后的完整快照不会因日志归档异常丢失。

**验证：** absolute registrar、页面、presenter、failure archive focused `21 passed`；hybrid product/integration/controller `16 passed`；PoE2 terrain/hybrid/UI/composition/architecture 回归 `195 passed`；采集页/监控窗口/正式页回归 `22 passed`；`compileall` 通过；失败样本重放为 `anchored_candidate`（`182°`, anchor error `2.40px`）。

**同步结果：** 已更新 `CODEBASE.md` 的 PoE2 页面职责、absolute registrar 算法、F-POE2-HYBRID-LOCALIZATION 链路和装配边界；已更新 `docs/POE2_NAVIGATION_COMPATIBLE_TRACKING_CURRENT_STATE.md`。本轮未发送 Xbox、键鼠、Host、LAN 或自动移动输入。

**下一步：** 用户启动新版页面后，先在“数据采集测试”页确认混合定位按钮可用；获取地图后启动混合定位，观察日志 `status/search_mode/best_angle/best_anchor_error/attempt_count`，再移动人物确认大地图随自动方向显示且恢复只增加一次内存读取。多地图随机方向仍需实机验证。

## [SYNC] 2026-09-22 — PoE2 展示诊断类型收紧

### A. SYNC 范围声明

**触发任务：** 复核上一轮自动方向/候选消歧改动后的 Serena 诊断，消除新增的可空诊断值和采集页人物样本类型告警。

**直接变更文件：**
- `src/auto_modules/ui/modes/poe2_live_terrain/page.py`
- `src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py`

**预计连带影响：** 仅影响 UI 诊断文本的数值门控和 `_player_position` 类型声明；不改变定位、地图变换或页面状态机。

### C. SYNC 结果

**关键发现：** (verified) UI 诊断字段来自动态 mapping，不能在缺字段时直接 `float(None)`；采集页的人物读取器是动态 provider，需要显式标注 `PlayerPositionSample | None` 才能保持 presenter 契约。

**实现结果：** 只有四个最佳候选字段全部为数值时才格式化分数/角度/锚点误差/coverage，否则显示候选数和原因；采集页为缓存人物位置和本地变量增加 `PlayerPositionSample | None` 类型。

**验证：** 页面/registrar/presenter `20 passed`；`compileall` 和 `git diff --check` 通过。Serena 剩余提示仅为项目语言服务器缺少 `cv2`、`numpy`、`PySide6` 依赖，以及既有 Protocol 的 `retry_recovery`/动态 Any 提示。

## [SYNC] 2026-09-22 — PoE2 首帧匹配窗口按截图覆盖尺度校准

### A. SYNC 范围声明

**触发任务：** 用户澄清“缩小范围”指以内存人物锚点为中心的 terrain 匹配窗口，且窗口应根据当前实际小地图截图覆盖范围选择近似比例，而不是缩小 UI 展示范围。

**直接变更文件：** 待证据确认后确定 `absolute_registrar.py`、相关测试与 PoE2 断点文档。

**预计连带影响：** 首帧/恢复的局部 terrain 裁剪、候选数量与方向/锚点消歧；不改变内存读取次数、第一页绘图模式或正式输入链路。

### B. 根因调查进行中

**当前假设：** 现有 `crop_radius=180/refine_crop_radius=130` 可能大于截图实际可见 terrain 尺度，导致首帧稀疏墙体在多个重复候选中竞争；需要先从样本确认截图像素、terrain 网格和人物锚点的比例关系，再决定默认窗口或分级 fallback。

**待验证证据：** `data/poe2_live_terrain_test/hybrid_failures/20260922-144211-152568-MapFlotsam-1E44BF94/` 的原始截图、wall mask、sample、失败诊断与 `latest.npz` 的锚点对应关系。

### C. SYNC 结果

**关键发现：** (verified) 当前真实样本的 minimap/wall mask 为 `200 x 200`，以人物锚点为中心的 `150/110` terrain 窗口仍保留有效墙体并将锚点误差降到 `0.18px`；`140/100` 已出现墙体裁切和低分拒绝，继续缩小不可取。现有 `180/130` 虽可通过，但搜索集合偏大且锚点误差为 `7.10px`。

**实现结果：** `AnchoredRegistrationConfig` 默认改为 `crop_radius=150`、`refine_crop_radius=110`，新增 `capture_reference_size=200`；`HybridFrame.from_evidence()` 记录真实 `capture_size`，registrar 在真实采集帧上按实际 wall mask 边长同比例调整两个半径，并将 `capture_size/crop_radius/refine_crop_radius` 写入 diagnostics。离线/手工 frame 没有该诊断时保持显式半径不变。探针 CLI 默认同步改为 `150/110`。

**验证：** absolute registrar/models/session focused `25 passed`；默认窗口样本复放为 `anchored_candidate`；`compileall` 和 `git diff --check` 通过。未修改第一页绘图模式，未增加内存读取，未发送任何输入或网络操作。

**覆盖进度更新：**

| 文件 | 前状态 | 现状态 | 备注 |
|---|---|---|---|
| `src/auto_modules/features/poe2/live_terrain/experimental/hybrid_localization/absolute_registrar.py` | 深度完整 | 深度完整 | 默认窗口、按真实截图尺寸缩放、诊断字段已同步。 |
| `src/auto_modules/features/poe2/live_terrain/experimental/hybrid_localization/models.py` | 深度完整 | 深度完整 | `HybridFrame.from_evidence()` 保存 capture size。 |
| `tools/debug/poe2_anchor_local_registration_probe.py` | 深度完整 | 深度完整 | CLI 默认窗口与实验默认一致。 |
| `tests/poe2_live_terrain/test_hybrid_absolute_registrar.py` | 深度完整 | 深度完整 | 增加默认标定、真实 frame 缩放和离线显式半径回归。 |
| `docs/POE2_NAVIGATION_COMPATIBLE_TRACKING_CURRENT_STATE.md` | 深度完整 | 深度完整 | 记录样本档位结果和当前参数。 |
| `docs/POE2_LIVE_TERRAIN_CURRENT_STATE.md` | 深度完整 | 深度完整 | 记录 terrain 匹配范围语义和日志字段。 |

**下一轮计划：** 启动实机采集页，核对日志中的三个窗口字段与实际截图尺寸；先验证首帧成功和地图方向，再验证连续移动，不在没有新样本前继续缩小窗口。

## [SYNC] 2026-09-23 — PoE2 地图显示放大与人物跟随

### A. SYNC 范围声明

**触发任务：** 用户反馈完整 native 地图按全图适配后有效地形和人物过小，要求放大或跟踪放大。

**直接变更文件：**
- `src/auto_modules/ui/widgets/scalable_map.py`
- `src/auto_modules/ui/modes/poe2_live_terrain/presenter.py`
- `src/auto_modules/ui/modes/poe2_live_terrain/page.py`
- `src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py`
- 相关 UI/presenter 测试与 PoE2 断点文档

**预计连带影响：** 仅影响地图展示缩放、视口滚动和人物标记可见性；不修改源地图坐标、匹配算法、定位状态机、内存读取或第一页绘图模式。

### B. 根因调查

**关键证据：** (verified) `ScalableMapWidget.fit_to_view()` 按完整 `2416 x 2277` pixmap 适配，黑色未探索区域也参与缩放；组件已有滚轮缩放，但 PoE2 页面没有根据定位点设置视口中心，因此人物落在小范围地形上时不可读。

### C. 实现结果

新增通用 `ScalableMapWidget.focus_on_point(point, zoom_multiplier)`：以未缩放 pixmap 坐标为输入，按当前 fit scale 放大并设置滚动条，使指定源坐标位于视口中心。PoE2 正式页和数据采集页默认使用 `2.4x` 跟随放大；有本帧位置时跟随本帧，失败时使用 `latest_confirmed_position` 保持视野；用户仍可拖拽和 Ctrl+滚轮微调。`localization_display_point()` 复用 presenter 的任意角度旋转/镜像矩阵，把定位坐标转换到已旋转 overlay 的显示坐标。运行时人物 marker 最小半径提高到 `9px`，增加半透明绿色填充。

**验证：** UI/presenter focused `20 passed`，新增 scalable map/presenter 回归后 `11 passed`；PoE2 页面/采集页相关回归 `20 passed`；`compileall` 和 `git diff --check` 通过。

**下一步计划：** 启动页面实机确认初始定位后人物是否保持在视口中心、地图细节是否足够清晰；若希望在“跟随”和“自由浏览”之间切换，再增加页面级跟随开关，不改变底层地图坐标。

### C. 本轮发现
**关键发现：** (verified) `SimilaritySearch.transform_feature()` 使用 OpenCV 图像坐标的正角度矩阵（局部右移经正角度后向图像下方旋转），而通用 `transform_local_displacement()` 使用数学笛卡尔坐标公式（同一正角度向图像上方旋转）。因此首帧形状匹配使用的方向与后续 `visual_f2f` 位移使用的方向相反，地图本身可以正确旋转，但人物移动轨迹会偏离真实通道。

**修订的旧结论：** 原来认为 presenter 对整张地图和轨迹同时做逆变换即可保证同步；现在确认这只能保证显示层同变换，不能修复 tracker 在全局坐标中已经使用错误旋转符号的问题。

**新疑问：** 需要将通用位移变换与图像坐标约定统一，并增加一个已知角度的帧间移动回归，验证 tracker 的 `global_shift` 与 `transform_feature` 对同一向量给出相同方向；随后再核对 UI 变换回归。

**下一轮计划：** 先新增失败测试锁定 OpenCV 图像坐标的正角度语义；再只修改 `transform_local_displacement()` 的旋转矩阵，运行 displacement/local tracker/presenter focused tests，最后更新 PoE2 断点文档和 CODEBASE SYNC。

## [SYNC] 2026-09-23 — 统一 PoE2 连续位移与首帧匹配的旋转坐标约定

### A. SYNC 范围声明
**触发任务：** 修复离线地图按匹配方向旋转展示后，人物连续移动轨迹仍按相反方向增长的问题。

**直接变更文件：**
- `src/auto_modules/core/localization/displacement.py`
- `tests/test_displacement.py`

**预计连带影响：** `VisualLocalTracker.track()` 的 `visual_f2f` 全局位移方向；PoE2 混合定位轨迹和地图展示；通用 localization displacement 契约及其测试。未改变内存读取频率、首帧注册、UI 地图旋转、输入设备或网络行为。

### B. 影响扩散分析
`transform_local_displacement()` 仅被 `VisualLocalTracker.track()` 和核心导出调用；tracker 已通过 focused tests 覆盖。新增测试同时核对 OpenCV feature point transform，确保旋转、水平镜像、缩放的顺序一致。

### C. SYNC 结果
**关键发现：** (verified) OpenCV 图像坐标的旋转矩阵为 `[[cos, sin], [-sin, cos]]`；旧实现使用笛卡尔矩阵 `[[cos, -sin], [sin, cos]]`，导致正角度在后续位移阶段反向。修复后连续轨迹与首帧匹配方向一致。

**实现结果：** `transform_local_displacement()` 明确声明并采用图像坐标语义；保留先水平镜像、后旋转、再缩放的既有顺序。测试增加 90° 方向回归和与 `transform_feature()` 的任意角度/镜像/缩放向量等价回归。

**验证：** `15 passed`（displacement、hybrid visual tracker、PoE2 presenter）；待执行完整 PoE2 回归、compileall、Serena diagnostics 和 git diff check。

### C. SYNC 结果
**连带重读文件：** `displacement.py`（Serena 复核函数体）、`local_tracker.py`、`similarity_search.py`、`presenter.py`、`orientation.py`、相关 tracker/presenter 测试。

**CODEBASE.md 更新内容：** 更新 `core/localization/displacement.py` 的目录职责、坐标约定、算法步骤和与 `transform_feature()` 的调用契约；记录 OpenCV 图像坐标矩阵及 `VisualLocalTracker` 影响。

**断点文档更新内容：** `docs/POE2_NAVIGATION_COMPATIBLE_TRACKING_CURRENT_STATE.md`、`docs/POE2_LIVE_TERRAIN_CURRENT_STATE.md` 新增本轮根因、修复和实机验收条件。

**覆盖进度更新：** `displacement.py`、`local_tracker.py`、`similarity_search.py`、`presenter.py`、`orientation.py`、`tests/test_displacement.py`、`tests/poe2_live_terrain/test_hybrid_visual_local_tracker.py`、`tests/test_poe2_live_terrain_presenter_position.py` 均已完成本轮变更后复读/验证。

**验证结果：** PoE2/混合定位相关回归 `189 passed`；`compileall` 通过；`git diff --check` 通过；Serena 源文件诊断为空。测试文件的 Serena 静态提示仅为当前语言服务器环境未解析 `pytest`/`numpy`，实际 pytest 运行正常。

## [第?轮] 2026-09-23 — PoE2 旋转地图与实时轨迹坐标链路根因调查

### A. 本轮目标（阅读前声明）
**目标文件：**
- `src/auto_modules/features/poe2/live_terrain/experimental/hybrid_localization/local_tracker.py`（确认帧间位移如何进入全局坐标）
- `src/auto_modules/core/localization/displacement.py`（确认局部位移的旋转/镜像/比例顺序）
- `src/auto_modules/core/localization/frame_displacement.py`（确认帧坐标到地图坐标的约定）
- `src/auto_modules/features/poe2/live_terrain/experimental/hybrid_localization/controller.py`（确认 position/trajectory 的坐标空间）
- `src/auto_modules/ui/modes/poe2_live_terrain/presenter.py`（确认地图和轨迹是否重复变换）
- 关联测试与导航模式参考实现（对照已工作的移动跟踪链路）

**本轮想弄清楚：** 离线地图只在展示层旋转，而人物移动轨迹没有同步旋转的具体断点；需要分清 native/reference、registration、display 三种坐标空间，并确认是否存在变换方向或重复变换。

## [第?轮] 2026-09-23 — 回归排查绝对注册失败与定位不准

### A. 本轮目标（阅读前声明）
**目标文件/证据：**
- 当前运行日志、失败归档和最新截图/样本（确认失败发生在首帧绝对注册还是连续视觉跟踪）
- `src/auto_modules/features/poe2/live_terrain/experimental/hybrid_localization/absolute_registrar.py`（核对 `score/coverage/anchor_error` 门槛和候选方向）
- `src/auto_modules/features/poe2/live_terrain/experimental/hybrid_localization/similarity_search.py`（核对本次候选的方向、比例、特征清理）
- `src/auto_modules/features/poe2/live_terrain/experimental/hybrid_localization/controller.py` 与页面状态链（确认失败是否被误显示为位置错误）
- 最近一次 displacement 改动的 focused 回归（确认它没有影响首帧绝对注册）

**本轮想弄清楚：** 截图中 `absolute_registration_failed`（最佳分 `0.49`、覆盖 `0.61`、锚点误差 `2.7`）为何拒绝，以及用户所说的“定位不准”是首帧没有可信位置，还是连续跟踪坐标偏移。

## [第?轮] 2026-09-23 — 恢复首帧全局定位稳定性与匹配参数回归

### A. 本轮目标（阅读前声明）
**目标证据：**
- `data/poe2_live_terrain_test/hybrid_failures/` 中当前失败样本与此前成功样本
- 当前 `AnchoredRegistrationConfig`、PoE2 profile 识别参数和 `HybridFrame` 诊断
- 首帧匹配探针在 `150/110`、墙体清理、分数/coverage 门槛变化下的结果

**本轮想弄清楚：** 用户确认此前首帧可以稳定定位，而当前截图再次进入 `absolute_registration_failed`；需要验证缩小窗口是否仍生效、墙体特征是否被文字/传送门/黄色过滤污染，以及哪个参数变化导致候选从可接受跌到拒绝，不能凭单个失败样本直接放宽门槛。

### C. 本轮发现
**关键发现：** (verified) 当前失败日志仍为 `capture_size=200/crop=150/refine=110`，缩小范围没有回退。失败候选 `score=0.492/coverage=0.609/scale=0.31` 由顶部动态文字/传送点残留造成；参数复放将 `top_exclusion_rows` 调到 `35~40` 后，候选恢复到约 `angle=219~221°/scale=0.75/score≈0.55/coverage≈0.75`。此前成功样本在 40 行下仍通过，锚点误差保持稳定。

**修订的旧结论：** 原来把本次失败归因于位移旋转修复后的坐标影响；现在确认状态尚未进入 `visual_f2f`，失败发生在首帧绝对注册，根因是动态顶部特征清理不足和参数门前候选变形。

**实现结果：** `AnchoredRegistrationConfig.top_exclusion_rows` 和 `tools/debug/poe2_anchor_local_registration_probe.py` 的 CLI 默认值均从 `25` 调整为 `40`；`absolute_registrar` diagnostics 新增 `top_exclusion_rows`、`player_clear_radius`，使截图、匹配窗口和特征清理参数同时可审计。未降低通用 score 门槛，未扩大/缩小 `150/110` terrain 窗口，未修改内存读取和输入链路。

**验证：** 新增默认参数回归；PoE2/混合定位/UI/位移相关测试 `190 passed`；compileall 通过。实机下一次需要确认日志实际打印 `top_exclusion_rows=40`，并观察首帧候选回到 `219°/0.75` 附近，再继续验证连续位移。

**CODEBASE/断点同步：** 更新 `CODEBASE.md` 的 absolute registrar 参数和 diagnostics 契约；更新 `docs/POE2_LIVE_TERRAIN_CURRENT_STATE.md`、`docs/POE2_NAVIGATION_COMPATIBLE_TRACKING_CURRENT_STATE.md` 记录失败证据、参数复放和验收条件。

### C. SYNC 结果
**直接变更：** `absolute_registrar.py`、`poe2_anchor_local_registration_probe.py`、`test_hybrid_absolute_registrar.py`；连带更新 `CODEBASE.md`、`docs/POE2_LIVE_TERRAIN_CURRENT_STATE.md`、`docs/POE2_NAVIGATION_COMPATIBLE_TRACKING_CURRENT_STATE.md`。

**验证结果：** PoE2/混合定位/UI/位移相关测试 `190 passed`；`compileall` 通过；`git diff --check` 通过。Serena 源文件无代码诊断，仍只有环境缺少 `cv2`/`numpy` 类型桩的既有静态提示。

**实机验收边界：** 当前工作区没有再次读取用户运行中的游戏，因此不能宣称实机已经恢复；下一次启动必须以日志中的 `top_exclusion_rows=40`、`crop_radius=150`、`refine_crop_radius=110` 为参数生效证据，再判断候选角度/比例和首帧位置。

## [第?轮] 2026-09-23 — 多帧稳定首帧定位方案设计

### A. 本轮目标（阅读前声明）
**目标文件：**
- `src/auto_modules/features/poe2/live_terrain/experimental/hybrid_localization/`（确认当前单帧绝对注册、连续跟踪和恢复状态机边界）
- `src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py`（确认测试台可复用的按钮、计时器、状态展示和样本保存入口）
- `src/auto_modules/features/poe2/live_terrain/hybrid_product_runtime.py`（确认正式页与实验页的隔离边界）
- `docs/POE2_LIVE_TERRAIN_CURRENT_STATE.md`、`docs/POE2_NAVIGATION_COMPATIBLE_TRACKING_CURRENT_STATE.md`（确认当前断点、已知风险和不变约束）

**本轮想弄清楚：** 如何在不改变正式页面和内存读取策略的前提下，在 PoE2 测试台新增“移动一段后用累计墙体定位”和“多帧联合定位”两种实验模式；需要明确停止条件、证据契约、可信区间计算和最终接入点。

### 2026-09-23 补充范围：完整链路设计
用户要求只编写本地逻辑/算法方案。沿用本轮已有阅读，补齐首次与恢复全局注册、正常跟踪、A/B 策略、有限局部拼图、滤波和导航消费契约；不编写实现代码。文档同步只登记设计入口，拟议模块不标为已有能力。

### C. 本轮发现
**关键发现：** (verified) 现有导航链路已经提供 F2F 位移优先、局部匹配备用和全局恢复入口；(inferred) 方案 A 的拼图融合可复用 MapStitcher 的识别/合并思想，但有界滚动存储、位姿修正和候选不确定性仍需独立设计；(verified) native 参考地形、视觉拼图和截图缓存必须分开管理，不能用全图零值数组模拟迷雾。

**修订的旧结论：** 原先将图片中的滤波理解为首帧定位本身的解决方案；现在明确它只在方向/镜像/比例已确定的候选内部融合位置和速度，首帧仍需锚点约束的形状注册或多帧共同注册。

**文档结果：** 新增 `docs/plans/2026-09-23-poe2-multiframe-localization-navigation-design.md`；更新 `docs/POE2_LIVE_TERRAIN_CURRENT_STATE.md` 与 `docs/POE2_NAVIGATION_COMPATIBLE_TRACKING_CURRENT_STATE.md` 的断点入口。没有修改 Python/C#/UI 实现，没有启动游戏、输入控制、网络同步或真实内存读取。

**下一轮计划：** 若进入实现，先把 P0 坐标/时间/证据契约拆成测试，再实现共享运动门控和有界证据窗口；不直接接正式 PoE2 页面。

## 2026-09-23 — 多帧定位实施计划

### A. 本轮目标
将已批准的全局定位、方案 A、方案 B、有限局部地图、时序估计和导航消费设计拆成 TDD 实施任务，明确每个任务的文件、接口、验证命令、提交 checkpoint 和正式链路隔离边界；本轮不修改运行代码。

### C. 本轮发现与结果
**关键发现：** (verified) 现有 `experimental/hybrid_localization` 已有 `HybridFrame`、锚点、一次性恢复、绝对注册和 F2F tracker，可作为首轮组合基础；(verified) `MapStitcher` 的画布默认是大数组，不能直接作为滚动局部地图的存储实现；(inferred) 需要先在 PoE2 实验目录实现有界 tile/关键帧窗口，再决定哪些模块下沉 `core/localization`。

**计划文件：** `docs/plans/2026-09-23-poe2-multiframe-localization-navigation-implementation-plan.md`。

**任务分层：** 数据契约 -> 运动门控 -> 有界 evidence window -> 滚动 submap -> 形状评分 -> A/B -> 不确定性 -> 状态机 -> session -> 实验台 -> composition -> 归档回放 -> 导航 observation -> 回归和文档同步。

**未执行：** 没有写 Python/C#/UI 实现，没有启动真实输入或网络同步；计划内代码片段是实施接口起点，不代表当前磁盘上已存在这些模块。

### 2026-09-23 补充：代码目录结构
实施计划新增 `Code Layout` 章节：`core` 保持通用定位/拼接能力，PoE2 地图获取、profile 和内存锚点留在 `features/poe2/live_terrain`，新 A/B 证据阶段与状态机放在 `experimental/multiframe_localization`，实验台展示放在 `ui/modes/poe2_live_terrain/multiframe_panel.py`。`hybrid_localization` 与新多帧包并列，二者不共享可变 session 状态；正式 `page.py` 首轮不接入。下沉到 `core` 需要先满足无 PoE2 词汇、独立可测且存在第二复用场景。

## 2026-09-23 — P0 多帧定位基础实现 SYNC

### A. SYNC 范围声明
**直接变更：** `experimental/multiframe_localization/{__init__,models,motion_gate,evidence_window}.py`、对应三组测试。
**连带影响：** 仅实验目录导出和测试；不改变 hybrid controller、正式 PoE2 页面、绘图模式、输入和网络链路。

### C. SYNC 结果
**实现：** 完成只读多帧数据契约、运动/关键帧门控和有界 segment-aware evidence window。静止、低质量和断链不会伪造位移或持续注册；窗口超限按帧数/时间裁剪，断链递增 version 并清空旧帧。
**验证：** `18 passed`（多帧新测试 + displacement/frame-displacement）；实验目录 `compileall` 通过；`git diff --check` 通过。补充 segment 切换测试，修复新 segment 到来后后续帧被重复清空的问题。
**新风险：** rolling submap 尚未实现，不能把当前 evidence window 当作可注册地图；PositionEstimate covariance 还没有来源校准，暂不能向导航声明统计置信度。
**下一步：** 有界 rolling submap -> 稳健形状评分 -> 方案 A/B；继续保持正式链路隔离。

## 2026-09-23 — P1-P4 多帧定位实现 SYNC

### A. SYNC 范围声明
**直接变更：** `multiframe_localization/{rolling_submap,shape_registration,strategy_a,strategy_b,state_estimator,coordinator,session,navigation_adapter,archive,composition}.py`、PoE2 composition/page/capture test page、对应 tests 和 debug probe。
**连带影响：** 实验测试台增加 factory 和多帧控制；正式 PoE2 `runtime`、绘图模式、输入、Host/LAN 不接入。

### C. SYNC 结果
**实现：** 已完成有界局部拼图、稳健形状评分、方案 A/B 候选策略、候选内部的状态估计、全局收集/跟踪/恢复状态机、session、归档/回放探针、导航 observation 适配器和实验台入口。
**验证：** 多帧新测试与 PoE2 页面/组合/displacement 回归共 `54 passed`；`compileall` 通过；`poe2_multiframe_localization_probe.py --help` 通过；`git diff --check` 通过。
**未完成验证：** 真实 native 地图多帧注册、A/B 收敛精度、实机内存读取次数、长时间内存和视觉性能尚未测量；不能宣称首帧实机稳定。
**下一步：** 端到端历史样本回放，修正真实 reference 注册适配和参数；随后用户开游戏做首次多帧实验，最后再评估是否下沉通用模块或接正式 runtime。
# 2026-09-23 - Complete PoE2 multiframe localization experiment

- Scope: close the remaining gaps in the approved multiframe localization plan inside the PoE2 experiment bench only.
- Boundaries: do not modify the drawing workbench or product hybrid-localization default; do not emit controller, keyboard, mouse, Host, or LAN input.
- Work: make A/B confirmation, native displacement tracking, bounded degraded/recovery transitions, one-shot recovery anchors, stale-result fencing, diagnostics, explicit archive, and end-to-end replay executable.
- Verification: focused multiframe/UI/PoE2 regression, architecture boundaries, compileall, and diff check. Real-game calibration remains a separate acceptance step.

## [SYNC] 2026-09-23 — 多帧定位完整实施最终审计

### A. SYNC 范围声明
**触发任务：** 按已批准方案完整实现并验证 PoE2 多帧全局定位实验链路，在全部计划项闭环后一次性汇报。

**直接变更文件：** `src/auto_modules/features/poe2/live_terrain/experimental/multiframe_localization/`、`src/auto_modules/ui/modes/poe2_live_terrain/{capture_test_page,multiframe_panel}.py`、`src/auto_modules/ui/modes/poe2/composition.py`、相关测试与离线探针。

**预计连带影响：** PoE2 数据采集实验台的定时采集、A/B 注册、连续视觉跟踪、一次性恢复锚点、展示和显式归档；正式 PoE2 hybrid runtime、第一页绘图模式、控制器/键鼠、Host/LAN 链路保持不变。重点复核 native 坐标交换契约、异步注册版本门、滚动地图边界、恢复读取次数和导航 observation 可执行门。

### C. SYNC 结果
**关键发现：** (verified) A/B、有限局部地图、异步注册、连续视觉位移、静止、降级/恢复、单次内存锚点、版本栅栏、原子归档和导航 fail-closed adapter 已形成可执行闭环；(verified) 多帧 composition 始终使用 native anchor/reference，profile 手工方向不会二次变换；(verified) 正式 hybrid runtime 和第一页绘图模式未被新实验链路替换。

**修订的旧结论：** 早期断点仍写“方案 A/B 待实现”或“P1-P4 只完成主要模块”；最终审计确认状态机、worker、UI、归档、navigation adapter 和端到端合成回放均已补齐。历史单帧 samples 缺新协议的 motion/segment/version，不能据此宣称真实多帧回放完成。

**验证：** 新增 native composition 契约 `2 passed`；完整 PoE2 多帧/UI/composition/位移/架构边界回归 `261 passed`；`compileall`、`poe2_multiframe_localization_probe.py --help`、`git diff --check` 均通过。Serena 的项目代码诊断为空；`numpy/PySide6` missing import 是其 Python 环境未加载项目 venv 的外部依赖提示。

**CODEBASE.md 更新内容：** 更新当前能力说明和目录树；在 §4 增加多帧源文件职责边界；在 §5 展开 session、coordinator、A/B 和 navigation adapter 算法；在 §6 增加完整实验链；在 §8 固化 native 坐标和版本 token；在 §9 登记真实阈值、B 角度、covariance 和 UI 线程性能风险。

**覆盖进度更新：**

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|---|---|---:|---:|---|
| `models.py` | partial | 深度完整 | 2 | 确认数组只读、候选/估计/version/native 字段契约。 |
| `motion_gate.py` | partial | 深度完整 | 2 | 确认 frame gap、质量、静止和 keyframe 距离分支。 |
| `evidence_window.py` | partial | 深度完整 | 2 | 确认帧数/时间界限和 segment 单次清空语义。 |
| `rolling_submap.py` | partial | 深度完整 | 2 | 确认 unknown/observed 分离、淘汰重建和最新视野裁剪。 |
| `shape_registration.py` | partial | 深度完整 | 2 | 确认 forward/reverse 距离场与 observed 投影范围。 |
| `strategy_a.py` | partial | 深度完整 | 2 | 确认结构门、独立 holdout 和同 version 去重。 |
| `strategy_b.py` | partial | 深度完整 | 2 | 确认 local offset 线性变换、共同候选和 basin 去重。 |
| `state_estimator.py` | partial | 深度完整 | 2 | 确认固定候选内预测、Mahalanobis 门和 covariance 输出。 |
| `coordinator.py` | partial | 深度完整 | 3 | 确认完整状态转换、四元 token、pending motion 补偿和恢复门。 |
| `session.py` | partial | 深度完整 | 3 | 确认单 worker、单 revision 锚点、停止/重置旧结果失效。 |
| `composition.py` | partial | 深度完整 | 2 | 确认 native 坐标不受 profile 手工方向影响。 |
| `archive.py` | partial | 深度完整 | 2 | 确认 raw/wall/observed/estimate/diagnostics 原子发布和失败清理。 |
| `navigation_adapter.py` | partial | 深度完整 | 2 | 确认 fresh/age/instance/version 门及安全半径公式。 |
| `multiframe_panel.py` | partial | 深度完整 | 2 | 确认 A/B 控制、状态、候选、性能和 submap 展示。 |
| `capture_test_page.py` | partial | 深度完整 | 3 | 确认独立 timer/session、transform 展示、显式归档和正式 runtime 隔离。 |

**新增 Finding：** P1 为真实多地图 A/B 阈值和错误确认率未校准；P2 为 B 初始 45 度 basin、covariance 未统计标定及 Qt 同步截图/识别性能。它们是实机验收边界，不是当前合成链路测试失败。

**下一轮计划：** 用户实机采集新 schema 多帧归档后，分别回放 A、B、A+B，统计确认率、错误确认率、native 位置误差 P50/P95、确认耗时/距离、峰值内存和每恢复 revision 的读取次数；在此之前不切正式 runtime。

## [Review] 2026-09-23 — 多帧方案完整性与方向所有权审计

### A. 本轮目标（阅读前声明）
**目标文件：** 多帧设计/实施计划、`experimental/multiframe_localization/` 全链路、正式 hybrid composition、PoE2 monitor config/UI、orientation/presenter/archive 和对应测试。

**本轮想弄清楚：** 逐项确认实施计划 1–15 是否真正闭环，找出合成测试掩盖的半成品；追踪 `map_rotation/map_flip_*` 从本地 profile 到 reference、anchor、显示和归档的所有消费者；设计并审批“用户不再手工控制方向，方向只能来自算法注册”的迁移方案，同时保留旧配置文件的可读兼容性且不破坏 native 坐标。

## [SYNC] 2026-09-23 — 自动方向与多帧定位链路补全实施

### A. SYNC 范围声明
**触发任务：** 对照已批准的自动方向设计和实施计划，彻底移除用户手工旋转/镜像，补齐多帧全局注册、连续跟踪纠偏、有界证据、加权子图和真实离线回放。

**直接变更文件：** `monitor_config.py`、PoE2 配置/页面/采集 UI、hybrid 与 multiframe composition、`experimental/multiframe_localization/` 算法和 session、离线 probe、对应测试及断点文档。

**预计连带影响：** profile JSON 契约、native reference/anchor 坐标、A/B 候选评分、跟踪状态机、异步发布、地图/人物/轨迹显示和显式诊断归档。第一页绘图模式、Xbox/键鼠/虚拟手柄、Host/LAN 不改动且不得产生真实输入。

**已批准边界：** 旧手工方向字段加载后直接忽略，旧方向归档不保留兼容；算法注册是 `L -> N` 的唯一方向事实源，显示层只能消费同一 registration version。

## [SYNC] 2026-09-23 — 自动方向与多帧链路最终文档及契约收口

### A. SYNC 范围声明
**触发任务：** 用户确认继续推进；对照完整设计/实施计划复审所有调用链，修正文档陈旧结论，并清除最后发现的静态契约问题。

**直接变更文件：** `registration_validator.py`、`state_estimator.py`、`archive.py`、`navigation_adapter.py` 及其回归测试；`CODEBASE.md`；`docs/POE2_LIVE_TERRAIN_CURRENT_STATE.md`；`docs/POE2_NAVIGATION_COMPATIBLE_TRACKING_CURRENT_STATE.md`。

**预计连带影响：** A/B 确认门、二维位置/位移类型边界、schema 3 离线回放、导航 age 门、自动方向展示版本栅栏和断点文档；不改变地图评分阈值、内存读取策略、正式 runtime、输入或 LAN。

### C. SYNC 结果
**根因调查：** Serena 诊断确认新增算法的运行时测试均通过，但四处边界使用了过宽的 `tuple[float, ...]`/`object` 类型：A/B peer 位置可选、状态估计器 ndarray 元组、归档 shift 任意长度、导航 diagnostics 时间戳任意对象。它们不会改变当前正常路径，却会让非法数据在静态分析中泄漏到核心契约。

**实现修复：** validator 在 A/B 比较前显式拒绝缺失位置；state estimator 在 reset/snapshot 边界收窄为二维浮点元组；archive load 要求 shift 恰有两个有限数；navigation adapter 对无效 captured timestamp 回退 `estimate.age_ms`。新增 malformed archive 和 invalid timestamp 回归。

**文档同步：** `CODEBASE.md` 已更新 §0/§2/§4/§5/§6/§8/§9，加入 `registration_validator.py`、`local_corrector.py`、schema 3 probe、generation 栅栏、加权 rolling submap、B 粗到细精化和不可变 presentation state；移除旧“oriented-preview/手工方向/B 仅 45°/probe 只打印”描述。两个 PoE2 断点文档追加自动方向与多帧链路的权威状态，并修订旧 `261 passed`/“待实现”表述。

**验证：** 新增 typed-boundary/回放聚焦 `12 passed`；包含全部 `tests/poe2_live_terrain`、PoE2 页面、组合、架构边界和位移回归的当前聚焦集合为 `282 passed`；`compileall` 通过；`poe2_multiframe_localization_probe.py --help` 通过；`git diff --check` 通过。全仓 `pytest -q` 为 `744 passed, 2 skipped, 4 failed`：`tests/test_distribution.py` 因当前 Python 环境缺少 `pydirectinput` distribution metadata 失败；`tests/test_pathfinder.py` 三项暴露既有路径规划行为与旧断言冲突。本轮未修改这两个无关边界。

**Serena 诊断：** 业务代码无新增类型错误；剩余提示全部是 Serena language server 未加载项目 venv 的 `numpy/cv2/PySide6` missing-import。没有真实游戏连接、内存读取、路线执行或任何输入/网络副作用。

**覆盖进度更新：**

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|---|---|---:|---:|---|
| `registration_validator.py` | 深度完整 | 深度完整 | 3 | 增加 peer 位置缺失的 fail-closed 类型边界。 |
| `state_estimator.py` | 深度完整 | 深度完整 | 3 | 明确 ndarray 到二维 tuple 的收窄点，保持 covariance 算法不变。 |
| `archive.py` | 深度完整 | 深度完整 | 3 | schema 3 load 增加二维有限 shift 校验和回放测试。 |
| `navigation_adapter.py` | 深度完整 | 深度完整 | 3 | 无效诊断时间回退 typed age，导航仍 fail closed。 |
| `CODEBASE.md` | partial | 深度完整 | 4 | §0/§2/§4/§5/§6/§8/§9 与当前自动方向实现一致。 |
| `POE2_LIVE_TERRAIN_CURRENT_STATE.md` | partial | 深度完整 | 4 | 追加最终自动方向、多帧回放和真实验收边界。 |
| `POE2_NAVIGATION_COMPATIBLE_TRACKING_CURRENT_STATE.md` | partial | 深度完整 | 4 | 修订验证数字、更新时间和正式/实验边界。 |

**修订的旧结论：** 旧文档把 B 描述为“45° 离散最终方向”、把 rolling submap 描述为简单 OR、把 probe 描述为只打印 manifest；当前实现已确认分别是 coarse-to-fine、可逆加权重建和 schema 3 A/B 真实回放。

**最终剩余风险：** 实机真实多地图错误确认率、native 误差 P50/P95、自动角度误差、确认距离/耗时、纠偏频率、恢复成功率、每 revision 内存读取次数、峰值内存和 Qt worker 耗时仍未测量；在这些数据完成前保持实验台隔离，不切换正式默认定位。

## [SYNC] 2026-09-23 — 完整性审查缺口修复

### A. SYNC 范围声明
**触发任务：** 对照已批准的多帧定位实施方案和真实操作链路，修复审查发现的未闭环功能，并在修复后重新进行文件级和流程级人工审查。

**直接变更文件：** `experimental/multiframe_localization/{coordinator,archive,session}.py`、`ui/modes/poe2_live_terrain/capture_test_page.py`、相关测试、`CODEBASE.md`、`docs/POE2_LIVE_TERRAIN_CURRENT_STATE.md`。

**预计连带影响：** A/B 注册统一确认门、schema 3 estimate 回放、归档按钮状态、session 重启和 evidence segment 生命周期；不改变正式 runtime、绘图模式、输入或网络副作用。

### C. 本轮目标（阅读后记录）
**根因调查先行：** 复核 A/B 汇合点、archive schema 3 load、UI 保存状态以及 session/recovery/evidence 边界，确认缺口后再逐项写失败测试和最小修复。

### C. 本轮发现与结果
**根因发现：**
- (verified) 方案 A 原先只通过自身结构/holdout 门，未经过 `RegistrationValidator`；只启用 A 时可绕过 native anchor、轨迹和实例确认。
- (verified) schema 3 `save()` 写入了 `estimate`，`load()` 却只重建 evidence/anchor/reference，回放 bundle 丢失候选、协方差、版本和状态。
- (verified) 多帧保存按钮在启动后立即开放，空证据或缺 anchor/reference 时只能在保存调用中失败。
- (verified) 重启同一 session 时，evidence builder 的累计 offset/segment 与 A/B 策略缓存没有清理；页面重新创建 experiment 掩盖了这个复用边界。
- (verified) 多帧 PoE2 composition 没有把 active profile 的 `recognizer_params` 应用到识别器，和 hybrid composition 的配置契约不一致。

**实现结果：**
- `StrategyResult` 携带 support/holdout 元数据；A 与 B 均经过同一 validator，双通过时按 validated confidence 选择较优结果，A 被 validator 拒绝时 UI 状态也标记 rejected。
- `MultiframeReplayBundle` 增加 typed `estimate`；load 重建 `CandidateRegion`、`SimilarityTransform2D`、协方差、版本、时效和 diagnostics；save 拒绝空 evidence。
- UI 只在 experiment、anchor、reference 和非空 evidence 同时存在时开放“保存实验”，tick 后动态更新；启动异常会关闭已创建 session 并恢复控件状态。
- session start/reset 清理 frame/previous/anchor revision、builder（若提供 reset）和策略缓存；A/B 增加显式 reset，PoE2 evidence builder 清零 offset/segment。
- PoE2 多帧 composition 在构造时应用 profile `recognizer_params`，保持独立识别器和绘图模式参数契约一致。

**新增/更新验证：** A validator fail-closed、A/B 质量选择、estimate archive round-trip、空 evidence、session restart、strategy reset、profile recognizer params 和 UI 保存门测试均通过；当前多帧/PoE2 聚焦集合 `244 passed`（含本轮新增测试）。Serena 诊断仅剩未加载项目 venv 导致的 numpy/PySide6 missing-import，非源码错误。

**人工链路复核结论：**
1. 测试页开始只创建一个 experiment/session/timer；截图、识别、motion gate 和 immutable evidence 进入 coordinator。
2. 每个 recovery revision 先一次 native memory anchor；A/B 共享冻结 window，后台结果受 generation + instance/recovery/evidence/segment token 双重门控。
3. A/B 统一 validator 通过后才进入 estimator/tracking；移动用 native 位移预测，静止不增长关键帧，局部纠偏失败先 degraded，连续失败才进入一次 recovery。
4. presentation 只消费同一 registration version，地图、人物、轨迹共同做 display transform；失败帧保持最后可信视野。
5. 保存是显式原子 schema 3 native archive，回放可重新加载原 estimate 但仍会独立重跑 A/B；导航 adapter fail closed，不执行路线或设备输入。

**修订的旧结论：** 旧文档中“方案 A/B 已统一确认”和“schema 3 可完整回放 estimate”在本轮之前并不成立；现已通过代码和回归测试补齐。旧的“实机多地图精度/性能已达标”仍不成立，必须保留为实机验收边界。

**覆盖进度更新：**

| 文件 | 前状态 | 现状态 | 阅读次数 | 本轮确认 |
|---|---|---|---:|---|
| `strategy_a.py` | 深度完整 | 深度完整 | 4 | StrategyResult 元数据、holdout 输出和 reset 生命周期。 |
| `strategy_b.py` | 深度完整 | 深度完整 | 3 | reset 清除跨 session 候选，coordinator 选择使用 validated confidence。 |
| `coordinator.py` | 深度完整 | 深度完整 | 4 | A/B 共用 validator、失败 reason 发布和双候选 arbitration。 |
| `session.py` | 深度完整 | 深度完整 | 4 | start/reset 清理 previous/frame/anchor revision/builder，停止后 worker 引用失效。 |
| `archive.py` | 深度完整 | 深度完整 | 4 | schema 3 estimate typed round-trip、空 evidence fail-closed。 |
| `composition.py` | 深度完整 | 深度完整 | 3 | active profile recognizer_params 在多帧 factory 创建时应用。 |
| `capture_test_page.py` | 深度完整 | 深度完整 | 4 | 归档可用门、启动异常清理和 tick 后状态更新。 |
| `CODEBASE.md` | 深度完整 | 深度完整 | 5 | 函数索引、Flow 和模块注意事项与本轮契约同步。 |
| `POE2_LIVE_TERRAIN_CURRENT_STATE.md` | 深度完整 | 深度完整 | 5 | 增加完整性审查结论、真实验收边界和修复状态。 |

**下一轮计划：** 实机 schema 3 多帧采集回放验收；若没有新实机证据，不再继续调阈值或扩大正式 runtime 范围。

**剩余风险：** 真实多地图错误确认率、native 位置误差 P50/P95、Qt 同步截图耗时、恢复读取次数和 covariance 校准仍未实机测量；本轮没有启动游戏、读取真实进程、发送输入或接入正式 runtime。

**下一轮计划：** 只进行用户实机 schema 3 多帧采集与回放验收；记录 A/B 选择、方向、位置误差、确认耗时/距离、恢复次数和 UI 帧耗时。若实机发现失败，先根据日志/归档定位具体边界，再单独修改，不把阈值调优混入架构修复。
# 2026-09-23 PoE2 A/B 控制弹窗与启动接线修复

## 根因

- 实机启动错误“请先获取地图并注入多帧实验工厂”来自 `MainWindow` 装配遗漏：composition 已创建 `multiframe_localization_factory`，但创建 `Poe2LiveTerrainPage` 时没有传入。
- 截图中的主采集页因此可以获取地图和人物网格坐标，但 A/B session 无法创建；这不是地图匹配器的拒绝。

## 实现

- `main_window.py` 传递 `multiframe_localization_factory`，并增加回归测试保护页面索引和工厂转发。
- 新增 `Poe2LocalizationControlDialog` 非模态控制窗口，默认同时启用方案 A/B；关闭窗口不停止 session，停止按钮才停止。
- 数据采集页移除混合定位和多帧控制区的可见布局，只保留截图、预处理、匹配特征、地图和状态展示；A/B 控件通过“定位控制”弹窗打开。
- 旧 Hybrid 控件对象暂留为不可见兼容层，避免影响已有监控窗口和历史测试；不再作为用户可见控制入口。

## 验证

- 失败测试先复现工厂未传递，再修复为通过。
- UI/PoE2 聚焦集合：`18 passed`（包含新控制弹窗、主窗口接线、数据采集页 A/B 回归）。
- 实机只读 smoke：使用当前 `latest.npz`、保存监控框、实际屏幕采集和当前 PoE2 内存锚点创建 A+B session；`session.start()` 成功，`memory reads=1`。
- 实机静止 6 帧均为 `collecting`，未产生关键帧和注册请求；这是 MotionGate 的预期行为，下一步需要用户移动后验证 A/B 注册和位置确认。

# 2026-09-23 多帧注册首步卡住根因修复

## 现象与证据

`data/logs/poe2_live_terrain.log` 在实机启动后持续记录 `phase=registering`、`pending=True`，但没有完成或失败事件；当时只有 1 个关键帧。根因是 coordinator 只要求 evidence 非空，直接提交了 Strategy B 的全图粗到细搜索。

## 修复

- 内置 A/B 策略声明最小关键帧要求，coordinator 在证据不足时继续 collecting；A+B 组合要求 5 个关键帧。
- Strategy B 使用内存锚点附近的局部 reference crop，并通过 origin 还原绝对 native 变换。
- B 粗搜跳过切向近邻和反向栅格化，最终 validator 仍保留严格确认门。
- session 增加完整注册生命周期日志和 10 秒超时；超时回到 collecting，晚到结果丢弃。

## 验证

- 多帧 coordinator/session/shape/strategy/end-to-end 聚焦回归通过。
- 真实样本基准：B 局部评估约 6.3 秒，A+B 五帧合成评估约 8.1 秒；此前完整地图搜索超过 30 秒未返回。
- 下一次实机重点看 `registration_deferred(required_frames=5)`、`registration_started`、`registration_finished`、`registration_published` 或 `registration_timeout`。

# 2026-09-23 全链路运行审查（第一轮）

## A. 本轮目标（阅读前声明）

**目标文件：**
- `src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py`：沿初始化、获取地图、预览、启动/停止多帧定位和窗口关闭链路核对 UI 生命周期。
- `src/auto_modules/features/poe2/live_terrain/experimental/multiframe_localization/session.py`：核对采帧、内存锚点、后台注册、超时、停止/重启并发边界。
- `src/auto_modules/features/poe2/live_terrain/experimental/multiframe_localization/coordinator.py`：核对状态机、证据门控、注册结果发布和跟踪恢复。
- `src/auto_modules/features/poe2/live_terrain/experimental/multiframe_localization/composition.py`：核对页面实际注入的截图、识别器、地图参考和内存锚点是否闭合。

**本轮想弄清楚：** 用户描述的“刚开始就卡住”是否仍由后台注册生命周期、页面定时器竞争或启动后状态未接线造成；重点模拟真实操作链路，不以静态测试通过代替运行证据。

### C. 本轮发现（阶段性）

- `(verified)` `MultiframeLocalizationSession._expire_registration_if_needed()` 超时后只把 coordinator 改回 `COLLECTING`，保留 `_registration_future`；后续 `_schedule_registration_if_ready()` 的第一行会因 future 非空直接返回，因此旧 worker 未结束前不会重新提交注册。仿真已复现：超时后连续 tick 的 job 数保持 1、`registration_pending=False` 但 future 仍存在。
- `(verified)` `Poe2CaptureTestPage.stop_multiframe_localization()` 关闭 session 后没有清空 `_multiframe_experiment`；`_multiframe_archive_ready()` 和保存入口仍可读取已关闭对象，异常 tick 后也会留下旧引用。
- `(verified)` `start_multiframe_localization()` 未检查 `monitor_config.binding`；实际第一帧才进入 `capture_preview_frame()` 抛出“请先画框选择区域或选择人物中心点”，导致用户看到“启动后卡住/无数据”而不是可操作的前置错误。
- `(verified)` `preview_timer` 与 `_multiframe_timer` 没有互斥。用户先点“开始截图监控”再启动多帧时，同一 `preview_provider`/recognizer 会在两个定时器中重复采样；截图监控窗口还可能有第三个 timer。这会放大 CPU/GPU/截图开销，且当前多帧 tick 没有把同一帧复用给预览 UI。
- `(partial)` `stop()` 对已运行的 future 只调用 `Future.cancel()`；运行中的 worker 无法被取消。需要专门测试 stop→start 后旧 worker 是否能修改新 coordinator/strategy 状态，不能只验证旧结果不发布。

**修订的旧结论：** 之前“增加超时后回到 collecting 即可解除卡住”的结论不完整；当前 future 引用仍阻断新注册，且页面生命周期和定时器并发还有独立缺口。

**下一步：** 先为四个 verified 缺口和 stop→start 并发风险写最小失败测试；然后单独修 session 生命周期，再修页面互斥/前置校验，最后用实际 composition 的 fake capture + fake anchor + 多帧证据跑完整状态流。

### C. 实现与验证结果

- `(fixed)` session 将注册评估放到 coordinator 的浅副本 + 策略深副本中；超时 worker 不再共享当前 coordinator/策略的可变状态。默认 executor 从单 worker 调整为 2 个并发槽，超时任务进入 retired 集合并由回调消费结果/异常。
- `(fixed)` 超时立即释放 active registration slot，下一次有新 evidence version 时可以重新提交；旧任务完成后只记录 retired 日志，不发布结果。
- `(fixed)` 多帧页面启动前拒绝缺失 `monitor_config.binding`，错误在启动按钮阶段展示；启动多帧时停止同页 preview timer 和独立截图监控窗口 timer。
- `(fixed)` 页面停止多帧后清空 experiment、状态、轨迹和归档可用状态，关闭的 session 不再被保存入口或下一次 tick 复用。
- `(verified)` 新失败用例先复现上述行为，修复后 session/page/end-to-end/composition 聚焦集合 `14 passed`，PoE2 全聚焦集合 `264 passed`。
- `(verified)` 实际 composition 的 fake capture smoke 能完成 anchor、帧构建和状态推进；静止/相似墙体被 MotionGate 正确判为无关键帧，未误触发昂贵 A/B 注册。这是预期门控，不是注册成功证明。

**修订的旧结论：** 之前文档把“超时回到 collecting”写成已解除卡住，但没有说明 worker 槽位和共享策略状态；现在已改为“超时可重试 + 旧 worker 隔离”。同时，页面启动链不再允许无绑定配置进入第一帧才失败。

**下一轮计划：** 用真实游戏进程或用户新采集的 schema 3 多帧样本验证：移动是否产生关键帧、达到 5 帧后 A/B 是否提交、超时后是否能再次提交、注册结果是否发布到统一地图/人物/轨迹版本。未有实机证据前不宣称定位稳定。

## [SYNC] 2026-09-23 — 多帧超时重试与页面采样生命周期修复

### A. SYNC 范围声明

**触发任务：** 全链路审查发现注册超时槽位、后台策略共享、页面旧实验引用、缺绑定前置校验和重复截图定时器。

**直接变更文件：**
- `src/auto_modules/features/poe2/live_terrain/experimental/multiframe_localization/session.py`
- `src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py`
- `tests/poe2_live_terrain/test_multiframe_session.py`
- `tests/test_poe2_capture_test_page_multiframe.py`

**预计连带影响：** 多帧 session 生命周期、A/B 注册策略状态、PoE2 测试页 Qt timer、归档保存门、页面启动前置契约和相关 Flow/风险条目。

### C. SYNC 结果

**连带重读文件：** `coordinator.py`、`strategy_a.py`、`strategy_b.py`、`composition.py`、`capture_monitor_window.py`、`multiframe_panel.py`、`localization_control_dialog.py`、PoE2 `page.py`；确认 composition 注入、A/B reset、窗口 timer 和页面 shutdown 与新 session 契约相容。

**CODEBASE.md 更新内容：** session 模块注意事项、测试页生命周期注意事项、`MultiframeLocalizationSession.tick()` 算法和失败行为已同步；新增 retired worker/隔离策略和 timer 互斥边界。

**新增 Finding：** 超时不能只把 phase 改回 collecting；active future 必须释放并隔离其可变策略上下文，否则长时间搜索会阻塞下一次真实注册并污染重启状态。

### D. 发布前验证

- `pytest -q tests/poe2_live_terrain tests/test_poe2_capture_test_page.py tests/test_poe2_live_terrain_page.py tests/test_main_window_poe2_terrain_page.py tests/test_poe2_live_terrain_monitoring.py tests/test_poe2_monitor_dialog.py tests/test_architecture_boundaries.py`：`264 passed`。
- 全仓 `pytest -q`：`759 passed, 1 skipped, 3 failed`；仅剩既有 `tests/test_pathfinder.py` 的三项路径策略冲突（阻塞角、未探索区、细墙），未触碰本轮 PoE2 链路。
- `compileall`：通过；`git diff --check`：通过。
- 实际 PoE2 进程/移动/注册成功未在本轮执行；没有发送输入、网络同步或自动移动。
- synthetic full-session trace：第 1~4 帧依次累积 1~4 个关键帧且保持 collecting；第 5 帧进入 registering 并提交 1 个 A/B job；强制超时后 active future 释放、retired=1；下一帧提交第 2 个 job 并回到 registering。说明证据门、超时重试和槽位隔离在真实 session 状态机中闭合。

## [2026-09-23] 实机 A/B 结果核对与性能归因

- A：达到 5 个关键帧，但 7 次注册均为 `strategy_a_status=rejected`，最终 `global_registration_ambiguous`，未进入 tracking。
- B：产生 12 个候选，但第一次任务因计算期间 segment 切换被版本门丢弃；后续任务仍为 ambiguous，未进入 tracking。候选数不等于定位成功。
- 多帧普通 tick（去掉首帧初始化）A 平均约 37.25ms、P95 48.57ms；B 平均约 34.69ms、P95 44.43ms。采帧本身约 20~45 FPS。
- 首帧初始化约 4.36~4.42s；全局注册约 3.26~8.90s（A）/6.55~8.78s（B），是主要体感延迟来源。绘图模式默认 10 FPS，而多帧实验使用 33ms/约 30 FPS 并叠加完整识别、证据与 UI 刷新。
- 未改代码；下一步先补齐 A/B validator/candidate 诊断并验证失败后的重试门控，再决定是否降低采样/UI 刷新频率。
## [SYNC] 2026-09-24 10:57 - PoE2 center capture resize and adaptive first-frame registration

### A. SYNC 范围声明
**触发任务：** 修复中心模式把截图大小改为 300 后实际绑定仍为 200x200，并让首帧定位跨截图尺寸自动搜索比例、过滤新增噪声后稳定通过 0.80 置信度门槛。

**直接变更文件：**
- `src/auto_modules/core/spatial/monitor_binding.py`
- `src/auto_modules/features/poe2/live_terrain/monitor_config.py`
- `src/auto_modules/features/poe2/live_terrain/experimental/hybrid_localization/similarity_search.py`
- `src/auto_modules/features/poe2/live_terrain/experimental/hybrid_localization/absolute_registrar.py`
- `src/auto_modules/ui/modes/poe2_live_terrain/capture/selection_controller.py`
- `src/auto_modules/ui/modes/poe2_live_terrain/config_panel.py`
- 相关聚焦测试文件

**预计连带影响：** PoE2 profile 加载、中心截图绑定、监控帧实际尺寸、首帧几何粗搜/精搜、内存锚点联合评分、正式页与数据采集页共享的定位工厂，以及 PoE2 定位断点文档。

### C. SYNC 结果

**关键发现：**
- `(verified)` 原 profile 的 `capture_size=300` 与 `binding=200x200/marker=(100,100)` 分裂，导致后端日志和实际帧始终为 200；配置模型现在加载即规范为 `300x300/marker=(150,150)`，物理人物锚点保持不动，region 画框保持原矩形。
- `(verified)` 现有算法原本已经在 `0.35..2.45` 粗搜、`0.02` 精搜中自动估计比例；真实 300px 样本仍稳定找到约 `0.77`，失败主因是扩大视野后新增顶部文字/底部画面噪声和评分中过高的局部 walkable-fill 权重。
- `(verified)` 顶部排除与真实 capture size 同比缩放、孤立紧凑组件清理、形状优先评分生效；精搜候选延迟到 memory-anchor 评分后再消歧，并只比较独立 angle/reflection/scale basin。
- `(verified)` 新实机端到端实际帧 `(300,300,3)`，状态 `local_tracking/anchored_absolute`，angle `221°`、flip `true`、scale `0.77`、anchor error `1.951`、confidence `0.81177`，仍使用 `minimum_confidence=0.80`。

**修订旧结论：** “截图大小改为 300 导致比例配置失效”修订为两层问题：首先是 300 没有进入 binding/截图链路；修复后比例自动搜索能正确找到 `0.77`，剩余拒绝来自新增非地图特征及候选过早去重，而不是需要为每台电脑手工保存固定比例。

**CODEBASE.md 更新内容：** §4/§5 的通用 monitor binding、PoE2 monitor config、similarity search、absolute registrar；§6 的 hybrid 首帧链路；风险说明保留多地图/多 UI scale 泛化边界。

**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/spatial/monitor_binding.py` | 深度完整 | 深度完整 | +1 | 新增保持物理 marker 的纯重设函数，保留 screen/space/DPI。 |
| `features/poe2/live_terrain/monitor_config.py` | 深度完整 | 深度完整 | +1 | center profile 构造和反序列化现在强制尺寸/binding/marker 一致。 |
| `hybrid_localization/similarity_search.py` | 深度完整 | 深度完整 | +1 | 评分权重成为显式、校验过的配置；通用默认保持兼容。 |
| `hybrid_localization/absolute_registrar.py` | 深度完整 | 深度完整 | +1 | capture-size 自适应排除、噪声清理、形状优先权重、basin-scale 消歧和真实 300px 结果已复核。 |
| `poe2_live_terrain/capture/selection_controller.py` | 深度完整 | 深度完整 | +1 | center size 更新委托通用空间函数，不写绘图模式状态。 |
| `poe2_live_terrain/config_panel.py` | 深度完整 | 深度完整 | +1 | spin 变化立即重建 center binding；region 模式不改画框。 |

**验证：** 首轮聚焦回归 `63 passed`；扩大到 PoE2 全实验包与相关页面/配置后为 `263 passed`，`compileall` 和 `git diff --check` 通过。Serena 对内部类型无新增诊断，现存诊断仅为其语言服务器环境未解析 `cv2/numpy/PySide6`；真实 PoE2 进程只读验证成功，没有发送键鼠、Xbox、Host、LAN 或自动移动输入。

**下一轮计划：** 收集至少两个不同地图和一个不同 UI scale/分辨率的首帧样本，比较自动比例峰、独立 basin margin、噪声清理后像素数和 confidence；在这些证据之前不把 `0.77` 固化为 profile，也不把 PoE2 清理策略下沉到通用 core。

## [2026-09-24] PoE2 后续跟踪漂移与 UI 性能根因排查

### A. 本轮目标（阅读前声明）
**目标文件：**
- `features/poe2/live_terrain/experimental/hybrid_localization/local_tracker.py`：确认首帧之后的位置更新模型，以及为什么移动数步后会漂移。
- `core/localization/frame_displacement.py`、`core/vision/phase_displacement.py`：确认帧间位移的质量门控是否能阻止累计误差。
- `ui/modes/poe2_live_terrain/page.py`、`ui/modes/poe2_live_terrain/presenter.py`、`ui/widgets/scalable_map.py`：确认每帧绘图/地图跟随的资源开销。
- `data/logs/poe2_live_terrain.log`：用真实运行数据区分定位计算耗时与 UI 渲染耗时。

**本轮想弄清楚：** 首帧已成功时，漂移究竟来自方向/比例、帧间位移累计，还是展示层阻塞造成的低帧率；同时确认后续修复是否应先改参数还是先改结构。

### C. 本轮发现
**关键发现：**
- `(verified)` `VisualLocalTracker.track()` 对前后墙体二值图调用 `phaseCorrelate()`。只要响应 `quality >= 0.20`、位移未越界，就按 `previous_position - global_shift` 直接累加，并把响应值作为 `visual_f2f` confidence；没有周期性局部形状校正，也没有累计误差衰减。
- `(verified)` 相位相关失败、低质量或大跳变才会调用 `LocalMapMatcher.match()`；所以“每帧都返回高质量、但长期慢慢漂移”不会触发校正，符合当前现象。`quality≈1.0` 只表示相位响应，不表示绝对位置准确。
- `(verified)` 实际日志中首帧绝对注册约 `6251~12979ms`；后续 runtime 约 `63.1~73.0ms/帧`，但 `ui.localization_performance` 平均绘制约 `192.4~240.9ms/帧`，峰值 `402.9ms`，高于 `33ms` timer 周期。
- `(verified)` `handle_runtime_state()` 每帧构造两个预览、复制大地图、重画轨迹/marker、对整张 pixmap 做逆旋转；`focus_on_point()` 每帧调用 `set_scale()`，触发 `QPixmap.scaled()` 重采样整张约 `3244x1725` 图片。绘图模式没有这组整图操作，因此两者流畅度差异有明确代码依据。
- `(partial)` 当前日志只记录状态签名变化和 30 帧性能摘要，没有连续记录每帧 `shift/global_shift/position_jump`，因此还不能从既有日志计算本次实机移动的具体累计误差；下一次移动样本必须补充这些诊断字段。

**修订的旧结论：** “后续不准主要是首帧方向/比例错误”修订为“当前首帧已有实机成功证据，漂移的第一嫌疑是帧间相位位移无限累计；展示层严重超时又会扩大帧间运动和错配概率”。

**CODEBASE.md 更新内容：** §5 `VisualLocalTracker.track()` 的长期累计风险；§6 `F-POE2-HYBRID-LOCALIZATION` 的预测/校正边界；§9 新增 P1 漂移风险和 P1/P2 UI 阻塞风险。

**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `features/poe2/live_terrain/experimental/hybrid_localization/local_tracker.py` | 深度完整 | 深度完整 | +1 | 确认 phase 位移优先、累计位置公式和局部 matcher 仅在失败时触发。 |
| `core/localization/frame_displacement.py` | 深度完整 | 深度完整 | +1 | 确认质量/距离门控不包含长期漂移校正。 |
| `core/vision/phase_displacement.py` | 深度完整 | 深度完整 | +1 | 确认 OpenCV response 的语义只是相位相关响应值。 |
| `ui/modes/poe2_live_terrain/page.py` | 深度完整 | 深度完整 | +1 | 确认同步 runtime + 全量 preview/map/focus 绘制均在 GUI tick 中。 |
| `ui/modes/poe2_live_terrain/presenter.py` | 深度完整 | 深度完整 | +1 | 确认每次 overlay 都会复制并旋转整张 pixmap。 |
| `ui/widgets/scalable_map.py` | 深度完整 | 深度完整 | +1 | 确认 focus 每帧重复 set_scale 并触发整图重采样。 |
| `data/logs/poe2_live_terrain.log` | 深度完整 | 深度完整 | +1 | 提取首帧、runtime、UI 三类真实耗时摘要。 |

**验证：** `tests/test_frame_displacement.py` 与 `tests/poe2_live_terrain/test_hybrid_visual_local_tracker.py` 共 `7 passed`。本轮没有修改 Python/C++/UI 算法，没有发送任何输入或启动网络同步；只追加诊断断点文档。

**下一轮计划：** 先增加可控的逐帧诊断或离线回放，记录连续移动的 shift/累计位置/校正触发；确认误差模型后，再以“帧间预测 + 有界局部形状校正”做单一算法改动，同时单独缓存/节流 UI 地图变换，避免把定位修复和渲染优化混成一次参数调整。

## [2026-09-24] PoE2 跟踪与展示性能优化实施

### A. 本轮目标（实施前声明）
**直接变更文件：**
- `src/auto_modules/features/poe2/live_terrain/experimental/hybrid_localization/local_tracker.py`
- `src/auto_modules/features/poe2/live_terrain/experimental/hybrid_localization/composition.py`
- `src/auto_modules/ui/modes/poe2_live_terrain/page.py`
- `src/auto_modules/ui/modes/poe2_live_terrain/presenter.py`
- `src/auto_modules/ui/widgets/scalable_map.py`
- 对应 tracker/UI 回归测试

**本轮目标：**
1. 给帧间相位位移增加可配置的时间/帧数/距离校正门，在不增加内存读取的前提下周期性调用已有有界局部 matcher；校正失败时保留短期预测但记录失败，不把低质量结果伪装为绝对校正。
2. 缓存 registration 方向变换后的基础地图，地图位置变化时只更新 overlay 和滚动条，避免每帧整图旋转/缩放。
3. 保持绘图模式、输入设备、Host/LAN 和地图数据契约不变。

**实现前需要复核的调用边界：** tracker 的 matcher 契约、PoE2 factory 的参数注入、页面 overlay signature 与 `ScalableMapWidget` 的缩放/滚动职责。

### C. SYNC 结果

**关键发现：**
- `(verified)` `VisualLocalTracker` 已加入帧数/距离/时间三种可配置校正门；PoE2 factory 注入 `12 frames / 24 native px / 1500ms`。静止帧不满足 motion dead-zone，不会触发局部 matcher；校正成功会替换预测 registration，失败保留短期预测并记录失败原因。
- `(verified)` `ScalableMapWidget` 新增独立 overlay label，位置、轨迹和候选 marker 不再通过 `set_image()` 重建底图；`focus_on_point()` 固定跟随基准缩放，重复定位只滚动视口。
- `(verified)` 正式页面缓存已按方向/镜像/地图实例区分的 registered base pixmap；只有地图、方向或镜像变化才执行整图逆旋转。位置变化只更新 overlay，显示坐标通过既有 `localization_display_point()` 转换。
- `(verified)` 受影响测试和新增测试全部通过；PoE2 集合首轮为 `258 passed, 1 failed`，失败来自未修改的 `test_multiframe_shape_registration.py::test_huber_trim_reduces_outlier_error_without_hiding_raw_coverage`，单独复跑通过；`compileall` 和 `git diff --check` 通过。
- `(partial)` 尚未真实移动验收，当前校正频率和 UI 实际耗时仍需用户在游戏中连续移动后用日志确认，不能提前宣称漂移已完全解决。

**修订的旧结论：** 由“后续帧无限累计、UI 每帧整图重建”修订为“后续帧具备有界周期形状校正，UI 底图与 marker 已分离；实机长距离稳定性仍待验证”。

**CODEBASE.md 更新内容：** 更新 `VisualLocalTracker` 的校正算法、PoE2 factory 参数、`Poe2LiveTerrainPage` 的 registered-map 缓存和 `ScalableMapWidget` overlay 职责；风险登记保留实机校正阈值和 Qt 预览频率待标定项。

**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `hybrid_localization/local_tracker.py` | 深度完整 | 深度完整 | +1 | 增加校正门、校正成功/失败诊断和短期预测降级。 |
| `hybrid_localization/composition.py` | 深度完整 | 深度完整 | +1 | 注入 PoE2 周期校正的初始生产参数。 |
| `ui/widgets/scalable_map.py` | 深度完整 | 深度完整 | +1 | 增加独立 overlay label、跟随缩放基准和静态底图复用。 |
| `ui/modes/poe2_live_terrain/page.py` | 深度完整 | 深度完整 | +1 | 方向/地图级缓存与显示坐标转换，不再每帧 set_image。 |
| `ui/modes/poe2_live_terrain/presenter.py` | 深度完整 | 深度完整 | +1 | 增加一次性 registered base map 准备入口。 |
| `tests/poe2_live_terrain/test_hybrid_visual_local_tracker.py` | 深度完整 | 深度完整 | +1 | 覆盖周期校正成功和静止帧不校正。 |
| `tests/test_poe2_live_terrain_page.py` | 深度完整 | 深度完整 | +1 | 断言从旧 overlay 重绘迁移到 registered map 缓存。 |

**下一轮计划：** 在真实游戏中连续移动，检查 `correction_attempted/correction_accepted/correction_distance/position_jump`，同时比较 `ui.localization_performance` 的平均/峰值渲染耗时；若校正失败率高，再基于样本调整 matcher 容差，不先改首帧门槛。

## [SYNC] 2026-09-24 - PoE2 参数与定位帧率实施

### A. SYNC 范围声明

**触发任务：** 将首帧质量门做成 PoE2 配置档参数，优化单帧预处理并把正式定位移出 GUI 阻塞链路。

**直接变更文件：** `monitor_config.py`、`hybrid_localization/composition.py`、`config_panel.py`、`monitor_dialog.py`、`hsv/combined.py`、`hsv_recognizer.py`、`page.py`、PoE2 worker/组合文件及聚焦测试。

**预计连带影响：** PoE2 正式页和实验页共用的 registrar 构造、profile 旧版兼容、截图后处理、Qt 定时器与 worker 生命周期；绘图和导航模式仅受通用识别 API 扩展影响，原有输出须保持一致。

## [2026-09-24] PoE2 首帧置信度门槛调整

### 目标

响应真实首帧候选已经有可信内存锚点、但总体置信度约 0.75 的样本，将 PoE2 业务组合的通过门槛降至 0.70。

### 变更

- `composition.py`：`minimum_confidence` 从 `0.75` 改为 `0.70`，并保留注释说明该策略只属于 PoE2 组合。
- `absolute_registrar.py`：通用字段注释不再写死某个 PoE2 业务数值。
- `tests/test_poe2_composition.py`：正式组合和 runtime 配置断言同步为 `0.70`。
- `minimum_score_when_anchored=0.35`、`minimum_forward_coverage_when_anchored=0.50`、锚点半径和通用默认值未改。

### 边界

置信度门降低不能绕过独立覆盖率门；`forward coverage < 0.50` 的样本仍会拒绝。当前只完成配置和回归验证，尚未用新的多地图实机样本证明跨环境准确率。

## [SYNC] 2026-09-24 - PoE2 参数、预处理与后台定位

### A. 本轮目标

为 PoE2 增加可保存的首帧质量门和 30 FPS 目标，复用同帧预处理，并解除正式定位对 GUI 主线程的阻塞。

### C. 本轮结果

- `(verified)` profile 保存 `0.70/0.35/0.45` 三个首帧门，以及定位 `30 FPS`、预览 `12 FPS`；旧 profile 自动补默认值，参数窗口可编辑和恢复默认值。
- `(verified)` PoE2 composition 将当前 profile 门注入 registrar；通用 registrar、绘图模式和导航模式默认值未改。
- `(verified)` HSV 证据组装支持一次墙体预处理复用；200px 样本约 `42ms -> 11ms`，300px 压力样本约 `73ms -> 24ms`，输出等价测试通过。
- `(verified)` 正式 hybrid runtime 使用串行后台 worker、单槽最新状态、线程本地 MSS 捕获；停止/恢复/旧结果丢弃/worker 不重入均有测试。
- `(verified)` 日志新增捕获、证据、定位分段耗时和实际 FPS。

**修订的旧结论：** 最新实机日志中的 UI 绘制已约 `2.7~5.1ms/帧`，主要成本是定位和重复证据预处理；当前先做预处理复用和后台运行，是否需要进程隔离留给分段耗时证据决定。

**验证：** 本轮聚焦回归 `89 passed`；仍需真实游戏连续移动验证实际 FPS、首帧稳定性、周期校正和长距离漂移。
## [SYNC] 2026-09-24 — PoE2 后台定位链路收尾修正

### A. SYNC 范围声明
**触发任务：** 继续完成 PoE2 定位性能优化，并修正实机测试中容易误判的预览与后台首帧边界。
**直接变更文件：**
- `src/auto_modules/ui/modes/poe2_live_terrain/page.py`
- `tests/test_poe2_live_terrain_monitoring.py`
**预计连带影响：** `Poe2LocalizationWorker` 的启动信号时序、正式 PoE2 页面状态消费、匹配特征预览显示和停止/重启生命周期。

### B. 影响分析与重读范围
- `Poe2LiveTerrainPage.start_monitoring`：后台 worker 启动前先标记页面 active，避免极快首帧信号被丢弃。
- `Poe2LiveTerrainPage._update_frame_previews`：仅在匹配帧为空时显示占位文字，成功帧保持 pixmap。
- `Poe2LocalizationWorker._run`、`stop`：确认后台定位仍为串行 tick、停止事件可唤醒恢复等待，旧 generation 由页面过滤。
- `Poe2HybridProductRuntime.tick`、`_adapt_state`：确认状态和 timing 字段仍能被页面消费。

### C. SYNC 结果
**连带重读文件：** `page.py`、`localization_worker.py`、`hybrid_product_runtime.py`、`tests/test_poe2_live_terrain_monitoring.py`。
**关键发现：** 成功匹配帧此前在页面层被无条件 `setText` 清除，已修正；后台启动状态时序已调整。
**CODEBASE.md 更新内容：** 更新 PoE2 页面性能链路、预览状态约定和 worker 启动时序说明。
**验证：** 聚焦监控/worker 测试 `6 passed`；性能相关回归 `272 passed`；架构边界回归 `22 passed`；`compileall` 与 `git diff --check` 通过。

### C. 全仓回归补充
- PoE2/识别/监控聚焦回归仍通过：`272 passed`（修正前）和新增链路 `6 passed`；架构边界 `22 passed`。
- 全仓 `pytest -q` 得到 `789 passed, 1 skipped, 10 subtests passed, 3 failed`。3 个失败均为既有 `tests/test_pathfinder.py` 的路径规划断言（对角穿角、未探索区、细墙阻断），本轮未修改 pathfinder 或其测试；已保留为独立基线问题，不把它误归因于 PoE2 性能改动。
- `compileall`、`git diff --check` 通过。

## [SYNC] 2026-10-01 — Qt 实时定位崩溃取证与边界稳定化

### A. SYNC 范围声明
**触发任务：** 用户反馈点击双人实时/移动实验后页面容易报错退出、卡死，要求查看日志并排查完整链路。
**直接变更文件：**
- `src/auto_modules/ui/modes/poe2_live_terrain/presenter.py`
- `src/auto_modules/ui/widgets/scalable_map.py`
- `src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py`
- `tests/test_poe2_live_terrain_presenter_position.py`
- `docs/POE2_LIVE_TERRAIN_CURRENT_STATE.md`
- `ARCHITECTURE_ITERATION_LOG.md`
**预计连带影响：** Qt 图像转换边界、地图跟随滚动、双人实时帧处理与日志，以及对应页面回归。

### B. 影响分析与重读范围
- `frame_pixmap`：检查 NumPy 视图布局、QImage 借用内存和脱离时机。
- `ScalableMapWidget.focus_on_point/set_scale`：检查实时跟随时滚动条与缩放是否重复触发。
- `Poe2CaptureTestPage._tick_dual_motion/_render_preview`：检查截图、识别、跟踪和 UI 更新是否重复计算。
- Windows Application Error：确认原生故障模块和异常码，不把 Qt 崩溃误判成定位算法失败。

### C. SYNC 结果
**连带重读文件：** `presenter.py`、`scalable_map.py`、`capture_test_page.py`、`dual_motion.py`、`page.py`、`capture_monitor_window.py`、相关聚焦测试。
**关键发现：** 实机日志显示首帧接受、约 600 帧持续 tracking、内存只读 1 次且无恢复风暴；Windows 事件明确为 `pythonw.exe -> Qt6Gui.dll -> 0xc0000005`。另外，`frame_pixmap` 对 `np.fliplr` 这类非连续视图可稳定复现 `BufferError: underlying buffer is not C-contiguous`，会被实时 tick 外层当作致命帧错误停止。
**实现结果：** Qt 边界统一 `uint8 + np.ascontiguousarray`，拒绝异常通道数并用 `QImage.copy()` 脱离源缓冲区；地图跟随跳过未变化的滚动目标；双人帧优先使用 `extract_combined_with_processed` 复用预处理，并记录截图/识别/跟踪/总耗时。
**CODEBASE.md 更新内容：** 补充 Qt 图像边界、双人实时呈现链路和 P1 风险记录。
**验证：** 聚焦回归 `37 passed`；PoE2/定位相关集合 `342 passed`；全仓 `865 passed, 1 skipped, 10 subtests passed, 1 failed`。唯一失败是既有 `tests/poe2_live_terrain/test_multiframe_shape_registration.py::test_huber_trim_reduces_outlier_error_without_hiding_raw_coverage`，断言 `trimmed.forward_coverage == untrimmed.forward_coverage` 与当前 shape scoring 行为不符，本轮未修改该算法。`compileall`、`git diff --check` 通过。Qt6Gui 原生访问冲突尚未再次实机复现，下一次实机需要保留 `dual_motion.timing` 与 Application Error 时间点。

## [SYNC] 2026-10-01 — PoE2 地图点击目标即时显示与坐标取证

### A. 本轮目标

用户要求点击定位地图后立即显示点击位置，并详细记录点击坐标经过旋转、镜像、比例和平移后的完整链路；点击本身不发送真实手柄输入。

### C. 本轮结果

- `ScalableMapWidget` 新增窄接口 `set_target()`，只更新目标十字标记，不覆盖人物、候选、轨迹和路线 overlay。
- PoE2 采集测试页新增独立的 source pixmap、native、display 三份点击状态；点击先记录原始坐标，再逆变换、边界校验、正向闭环，并立即显示目标。
- 日志事件固定为 `map_click.received`、`map_click.transformed`、`map_click.accepted`、`map_click.rejected` 和 `map_click.cleared`；记录模式、source/native/display、round-trip error、angle、镜像、scale、translation、地图尺寸及边界。
- 跟随/程序移动仍沿原有确认和 timer 门禁运行；未启动跟随时点击只显示目标并提示等待，不申请设备租约、不发送输入。停止跟随后清除目标标记，重置/换图路径保持清理。

### 验证

点击前显示、连续点击更新、停止清理和通用 overlay 保留回归通过；聚焦测试 `3 passed`，PoE2 页面/采集/地图集合 `31 passed`。本轮未启动真实输入、未启动 LAN；Serena MCP transport closed，改用 CodeGraph 和离线 Qt 验证。

## [第 2026-10-01-移动链路取证] 2026-10-01

### A. 本轮目标（阅读前声明）
**目标文件：**
- `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_follow/runtime.py`（确认目标、路径、到达状态和输入向量的实际流转）
- `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_follow/program_output.py`（确认手柄输出边界和向量变换调用时机）
- `src/auto_modules/features/poe2/live_terrain/movement.py`（核对 native、registration、local stick 三种向量坐标系）
- `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_localization/dual_motion.py`（确认实时位置反馈是否能证明人物真的移动）
- `src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py`（确认实验页面如何组装路线和移动状态）
- `tools/debug/poe2_route_probe.py`、`tools/debug/poe2_movement_probe.py`（找回此前真实 Xbox 移动实验的契约）

**本轮想弄清楚：** 用户反馈“人物会卡在墙边、坐标转换后方向不一致、手柄需要持续按住”，需要先确定是路径规划坐标、registration 逆变换、Xbox stick basis、到达判断还是输入租约生命周期的问题；先只补证据，不改变真实输入行为。

### C. 本轮发现

- `(verified)` 页面点击目标先由 `localization_source_point()` 逆注册到 `reference.wall_layer` 的坐标，`SimulatedFollowRuntime` 的 A*、墙体碰撞、到达距离和 overlay 路线都使用这套 reference/native 坐标；展示层才重新正向映射到旋转后的 pixmap。
- `(verified)` 程序输出链路是 `native route vector -> native_map_vector_to_local()` -> `ProgramGamepadOutput.write()` 的 `basis`；PoE2 页面工厂传入 `POE2_MAP_TO_STICK_BASIS`，所以输出方向依赖“registration 逆变换”和“本地小地图到摇杆的等距投影”两步的组合。现有测试分别验证两步，却没有组合方向/反向的验收测试。
- `(verified)` `tools/debug/poe2_route_probe.py` 当前第 130 行把 `vector = native_map_vector_to_local(...)` 缩进到了 `if distance < 1e-6: continue` 之后，非零路径段不会赋值；这是独立路线探针的确定性缺陷，不能用它证明真实路线输入成功。历史 `route.finished` 记录来自修改前运行，当前文件不能复现同一行为。
- `(verified)` 实机日志只记录了 Host 的摇杆状态，没有记录每一 tick 的 `target/current/distance/route/vector/local_vector/stick_vector`，因此无法区分“路线命中墙”“坐标映射方向错”“输入被游戏忽略”“视觉位置没有变化”四种情况。当前实时定位耗时约 50–100ms，定时器目标 30 FPS，但实际约 15 FPS，也会放大位置反馈滞后。
- `(inferred)` 用户所说“卡在墙边”优先怀疑输出方向和地图 reference 坐标的组合未被验证，而不是直接修改 A*；下一步先把组合变换和 runtime 运动证据补齐，再用一个无障碍近目标和一个墙后目标做离线/实机最小实验。

**修订的旧结论：** 之前仅凭 `program_probe` 的 Host `state` 认为程序移动链路已打通；现在只能确认租约和摇杆写入成功，不能确认游戏人物位移或路径方向正确。

**下一轮计划：**
1. 修复并测试路线探针的非零向量计算。
2. 在通用 follow observation / 页面日志中记录坐标、路线、局部向量和 Host 状态，补充停止原因。
3. 增加“reference/native → local → stick”组合变换测试，确认坐标契约后再修复实际方向或寻路。

## [SYNC] 2026-10-01 — 路线输入坐标边界修正

本轮确认上面的“native → local → stick”结论会把首帧 registration 二次应用到已经转换
完成的 canonical 路线。真实实例 `P2_7:54BE4D92` 的 `221° + mirror + 0.863` 与 Host
轴值形成证据，解释了人物朝墙移动。新增 `native_route_vector_for_program_output()`，
路线向量在 reference/native 坐标原样通过，只有 `ProgramGamepadOutput` 应用 PoE2 等距
`POE2_MAP_TO_STICK_BASIS`；页面组装点和路线探针均已切换。旧逆变换函数保留用于通用
几何，不再作为 PoE2 输入转换。移动/跟随/页面回归 `43 passed`；未发送真实输入，待
用户按“近距离无障碍 → 门/墙后”顺序复测并保留 native before/after。

## [SYNC] 2026-10-01 — Xbox 路线探针与移动证据链

### A. SYNC 范围声明
**触发任务：** 修复路线探针的路径向量计算，并让正式/实验移动日志记录统一转换坐标、手柄方向和停止原因。
**直接变更文件：**
- `tools/debug/poe2_route_probe.py`
- `src/auto_modules/adapters/virtual_gamepad/program_output.py`
- `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_follow/runtime.py`
- `src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py`
**预计连带影响：** 独立真实输入探针、ProgramGamepadOutput Host 诊断字段、跟随观察契约、PoE2 页面日志和相关单元测试。

### B. 影响分析与重读范围
- 路线探针路径段循环：非零段的局部向量计算恢复到循环主体，避免读取未赋值的 `vector`。
- `ProgramGamepadOutput.write/stop/diagnostics`：增加最后一次输入向量、basis 后向量、轴值和 TTL 的只读诊断，不改变 Host 请求协议。
- `SimulatedFollowRuntime._observation`：附加 reference/native 坐标空间、路线端点和点数，保持 FollowObservation 字段兼容。
- `Poe2CaptureTestPage._tick_program_move_probe/_tick_follow_experiment/stop_program_move_probe`：增加每 5 tick 的运动证据和明确停止事件，不改变输入门禁或 timer。

### C. SYNC 结果

（待受影响文件重读、测试和 CodeGraph 同步后填写。）

## [SYNC] 2026-10-01 — 路线 overlay 与输入幅度取证

跟随实验和程序移动实验现在把 native 起点、A* 中间点和 native 目标完整映射到小地图
展示层，路线与目标使用同一 `localization_display_point()`，用于直接区分路线坐标错误
和 Xbox 输出错误。`FollowObservation.diagnostics` 新增 `route_length`，页面日志新增
`route_detour_ratio`；程序输出诊断新增 `input_magnitude`、`basis_magnitude` 和
`axis_magnitude`。当前 PoE2 基底对单位 native 向量的轴幅度约为 `0.707`，这是待实机
确认的幅度校准点，本轮没有擅自改变基底或发送真实输入。

聚焦回归 `48 passed`，compileall 与 diff check 通过。下一次实机应同时观察地图路线线段、
`distance/route_length`、Host 轴值和人物 native before/after，再决定是否需要调整输入
幅度或目标距离控制。

## [第 2026-10-02-1 轮] 双人首帧与闭环导航根因调查

### A. 本轮目标（阅读前声明）
**目标文件/符号：**
- `experimental/multiplayer_localization/dual_first_frame.py::DualFirstFrameRegistrar`（确认双人首帧置信度公式、锚定接受门和歧义判定）。
- `experimental/hybrid_localization/absolute_registrar.py::AnchoredAbsoluteRegistrar.register`（确认形状覆盖率如何进入注册结果）。
- `core/routing/pathfinder/runtime.py` 与 `core/routing/vector_tracker.py`（确认当前路线是否只保证中心线，缺少 clearance/窄路代价）。
- `experimental/multiplayer_follow/runtime.py` 与 `core/routing` 相关状态模型（确认是否有真实位置反馈、卡墙检测和局部重规划）。
- `adapters/virtual_gamepad/program_output.py`（确认手柄幅度、TTL、slew 与输入边界）。

**本轮想弄清楚：**
1. 双人首帧失败是否是锚点错误，还是低墙体 coverage 被错误地当成整体置信度；
2. 路线规划为何会贴墙/进入窄路，以及现有输入运行时为何没有对无进度做闭环恢复；
3. 哪些能力应先留在 PoE2 实验层，哪些具有稳定通用契约可以下沉到通用 routing/localization。

### B. 已完成的根因证据收集
- CodeGraph 已追踪双人注册、锚定注册、PathFinder、VectorPathTracker、跟随 runtime 和程序输出的调用关系；当前确认双人首帧的 anchor/pair 几何可为近零误差，但 coverage 仍会把整体 confidence 压到 0.59–0.66。
- 当前 PathFinder 只生成 downsample 网格上的可行中心线，`safety_margin=0`；`VectorPathTracker` 只复核线段可通行，未对墙体 clearance、窄通道或死路出口评分。
- 当前 `SimulatedFollowRuntime` 有静态 route cache 和 `BLOCKED` 状态，但没有基于真实人物位置增量的连续 progress watchdog；程序输出侧已记录输入，但仍需把视觉位置反馈接入局部重规划。
- 当前实机日志显示 Host 写入成功而人物 native 位移几乎不变，说明“输入已写入”与“人物有效前进”之间仍缺少方向/幅度标定和卡墙闭环。

### C. 下一轮计划
1. 为双人首帧建立拆分评分：anchor identity、pair geometry、shape evidence、candidate margin；先补充低 coverage 的正负离线测试，再调整接受逻辑。
2. 设计通用 clearance costmap/inflation 接口，在 PoE2 实验层接入安全路由、转弯和窄通道惩罚。
3. 增加实时进度监视与局部重规划状态机，明确输入 TTL、视觉帧新鲜度和重规划冷却。
4. 执行聚焦测试与文档 SYNC，之后再决定是否需要真实手柄标定实验。

### C. 本轮发现与验证结果
- 双人评分已改为拆分证据：`anchor_quality*0.45 + pair_confidence*0.25 + shape_quality*0.20 + profile_consistency*0.10`。形状覆盖率不再作为 65% 的总置信度代理；锚点误差和配对几何仍独立参与接受门。低覆盖精确锚点回归通过。
- `PathFinder` 新增可选 clearance distance-transform 代价；PoE2 实验跟随/程序移动实例启用 `safety_margin=8`、`clearance_radius=20`、`clearance_weight=2`，原始 wall map 逐段碰撞检查仍保留。通用默认值仍为 0，未改变其他业务。
- `VectorPathTracker` 对同一条路线缓存逐段 walkable 校验；`SimulatedFollowRuntime` 增加连续无进度检测，达到 3 个新鲜位置 tick 时先尝试左右交替侧向恢复，失败才冷却进入 `BLOCKED`。诊断输出包含安全参数与恢复状态。
- 聚焦回归：`307 passed`（PoE2 实验集 + PathFinder），新增低覆盖首帧、软 clearance 和 stalled recovery 测试均通过。

### D. 仍未验证
- 没有在当前运行中的 PoE2 上重新发送手柄输入，因此不能宣称方向基底、幅度和真实位移已经实机校准；下一次实机应记录人物 native before/after、distance delta、no_progress_ticks 和 recovery_target。
- 没有足够的真实双人首帧带真值样本计算 90% 准确率；当前仅修复已证实的评分断层并保留候选歧义门。

**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `dual_first_frame.py` | 深度完整 | 深度完整 | 2 | 已核对 assignment、anchor/pair/shape 评分和接受分支，新增拆分评分 |
| `pathfinder/grid.py` | 深度完整 | 深度完整 | 2 | 新增 distance-transform clearance cost map |
| `pathfinder/astar.py` | 深度完整 | 深度完整 | 2 | 增加可选软代价，不改变障碍与 corner 规则 |
| `pathfinder/runtime.py` | 深度完整 | 深度完整 | 2 | 新增可选 clearance 参数并传入 A* |
| `vector_tracker.py` | 深度完整 | 深度完整 | 2 | 缓存静态路线碰撞校验 |
| `multiplayer_follow/runtime.py` | 深度完整 | 深度完整 | 2 | 新增安全路由参数、进度监视和侧向恢复 |

**下一轮计划：**
1. 让正式/实验页面日志同时记录 clearance 和 progress 字段，人工复核完整闭环。
2. 用真实双人样本重放并统计接受/拒绝、候选 margin 与方向稳定性。
3. 在用户明确要求实机输入测试后做短距离方向/幅度标定；在此之前保持输入禁用。

### E. 收尾修订
- 路线验证缓存仅对只读墙图启用；可写 NumPy 墙图每次重新验证，避免地图原地更新后复用过期的可行结论。PoE2 runtime 在构造后把归一化墙图设为只读，因此生产高频 tick 仍可使用缓存。
- 聚焦回归扩大为 `313 passed`（PoE2 实验、PathFinder、通用 follow navigation）；compileall、git diff check、ruff 均通过。
- 页面日志已接入 `route_safety_margin`、`route_clearance_radius`、`route_clearance_weight`、`no_progress_ticks`、`recovery_attempts` 与 `recovery_target`，页面聚焦测试 `39 passed`。
- 全仓回归 `872 passed, 2 skipped`，另有环境缺失 `pydirectinput` 的既有 `tests/test_distribution.py` 失败；该依赖问题与本轮修改无关。
## [第 2026-10-02-2 轮] 双人首帧、清距寻路与手柄闭环问题调查

**本轮目标：** 针对实机反馈的贴墙/撞墙、卡墙、手柄速度不匹配和双人首帧不稳定，先补齐根因证据与离线可复现用例，再实施最小修复。范围限定在通用 routing、PoE2 实验跟随组合和双人首帧诊断；不发送新的真实手柄或 LAN 输入。

**已确认的调查边界：**

- A* 允许八邻域，但 heuristic 仍是曼哈顿距离，启发值高估对角线代价，可能提前关闭更安全的候选路径。
- clearance 目前只作为栅格搜索软代价，原图路线复核只检查穿墙，不检查到墙的实际最小距离；终点追加也可能重新贴近墙。
- `ProgramGamepadOutput` 的默认 slew rate 为 `180000/s`。在实验页 100ms 控制周期下，第一次输出最多约 0.55 归一化轴值；快速换向时还会叠加滞后。Host 接受写入不等于游戏人物已经产生位移。
- 双人实时位置由视觉帧反馈；跟随 runtime 每个控制 tick 使用最新可用位置，但尚未把视觉帧年龄、位置是否真的变化和输入输出状态统一成进度闭环。

**本轮假设（逐项验证）：**

1. 将 heuristic 改为八邻域一致的 octile 距离，并增加清距/窄路约束后，路线会减少贴墙和无谓折返。
2. 在通用路径跟踪边界增加地图空间最小清距校验，能阻止“未穿墙但擦墙”的段落进入手柄输出。
3. 将 PoE2 输出的 slew/TTL 设为显式适配参数，并记录每次输出的目标轴、实际轴、TTL；可区分速度滞后与游戏未移动。
4. 双人首帧失败需由候选、实例、anchor/pair、shape、assignment margin 各自诊断；真实 90% 仍必须用带真值的多张实机样本统计。

**实施顺序：** 先补失败测试，再改一个通用能力，跑 routing/follow/双人聚焦回归；随后同步 CodeGraph/Serena 和断点文档，最后才考虑实机标定。
## [SYNC] 2026-10-02 — 清距路径、卡墙恢复与双人候选稳定性

### A. SYNC 范围声明
**触发任务：** 用户反馈路线贴墙/撞墙、窄路与死路、手柄卡墙和双人首帧不稳定；本轮完成离线根因修复并补齐日志契约。
**直接变更文件：**
- `src/auto_modules/core/routing/pathfinder/astar.py`
- `src/auto_modules/core/routing/pathfinder/grid.py`
- `src/auto_modules/core/routing/pathfinder/runtime.py`
- `src/auto_modules/core/routing/geometry.py`
- `src/auto_modules/core/routing/__init__.py`
- `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_follow/runtime.py`
- `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_localization/marker_candidates.py`
- `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_localization/dual_first_frame.py`
- `src/auto_modules/adapters/virtual_gamepad/program_output.py`
- `src/auto_modules/ui/main_window.py`
- `src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py`
- 相关 PathFinder、双人首帧、跟随和页面测试。
**预计连带影响：** A* 网格代价/启发、PoE2 实验路线验证和恢复状态、marker 候选排序、PoE2 Host 输出参数、页面跟随控制循环与日志字段。

### B. SYNC 影响分析与重读范围
- `PathFinder._astar` → `astar_path`：八邻域启发改为 octile，新增窄路拓扑软代价。
- `SimulatedFollowRuntime._plan_safe_route` → `_route_is_safe`：所有候选路线在原始 native 墙图上做穿墙和最小清距复核，并从多个 downsample 候选选择几何长度最短且清距更优者。
- `SimulatedFollowRuntime._tick_follower`：零向量暂不立即 BLOCKED，交给无进度 watchdog 侧向恢复；视觉位置仍由页面的真实采集时间戳控制新鲜度。
- `marker_candidates_from_observation` → `DualFirstFrameRegistrar.register`：候选先保证不同颜色/profile 的代表性，再由内存 anchor、pair geometry 和 shape evidence 做最终身份与方向判定。
- `ProgramGamepadOutput` → `main_window._create_poe2_program_output`：slew rate/TTL 变成显式 PoE2 适配参数，其他游戏保持默认值。

### C. 本轮补充修复与验证

- 双人候选在置信度排序前增加基于 bbox IoU/中心距离的轮廓非极大值抑制；同一人物的轮廓和核心只占一个候选名额，近距离不同人物仍保留。
- 程序移动回写 runtime 时保留最后真实视觉帧的 `captured_at_ms`，禁止用控制 tick 时间伪造新鲜位置；视觉冻结后会进入 TTL 停止保护。
- 多尺度安全路线在硬碰撞和最小清距通过后，使用 `route_length + clearance_weight * exposure` 选路，诊断新增 `plan_selected_route_score`。
- 形状注册参考距离场缓存持有原始数组，修复 NumPy 地址复用造成的跨地图距离场串用。
- 聚焦回归：`69 passed`（双人首帧、跟随 runtime、PathFinder、页面、多帧形状注册）。

### D. 尚未实机验证

- 双人首帧真实 90% 准确率、贴墙/窄门/门后路线、卡墙恢复、手柄方向/幅度与人物 native 位移仍需用户授权后实测。
- 正式定位页已使用 bounded latest-state worker；实验采集页双人截图/识别仍在 GUI timer 串行执行，下一轮需要接入同类 latest-frame worker，以免处理耗时超过 30 FPS 时处理旧帧。

### E. 后续闭环优化

- 对照 `features/torchlight/follow/planner.py` 后，PoE2 runtime 增加目标刷新带和路线偏离带：目标小幅移动时复用已验证安全路线，只有目标移动超过 16 native px（或 `2 * arrival_radius`）、人物偏离路线超过 12 native px、路线碰撞失效或卡墙恢复时才重规划。
- `FollowObservation.diagnostics` 增加 `planned_target`、`route_target_shift` 和 `route_deviation`；页面运动日志同步记录它们，可直接判断是“复用路线”还是“触发局部重规划”。新增复用路线回归。
- 本轮聚焦回归为 `43 passed`；全仓回归为 `877 passed, 2 skipped`，唯一失败仍是环境缺少 `pydirectinput` distribution metadata 的既有打包测试。

## [SYNC] 2026-10-02 任务：定位采样频率、双人首帧候选稳定性与角色碰撞半径

### A. SYNC 范围声明
**触发任务：** 根据实机反馈排查路线贴墙、手柄闭环和双人首帧兼容性；先落地可离线验证的采样频率和首帧候选稳定性修复，并为角色碰撞半径增加通用运行时契约。
**直接变更文件：**
- src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py
- src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_follow/runtime.py
- tests/test_poe2_capture_test_page.py
- tests/poe2_live_terrain/test_multiplayer_follow_runtime.py
**预计连带影响：** 双人实时定位定时器、首帧注册调用次数与候选选择、PoE2 实验跟随路线的碰撞检查、程序移动日志和相关页面测试。

### C. SYNC 结果

- (verified) Poe2CaptureTestPage._localization_interval() 现在按 localization_fps 计算周期，同时受旧 sample_interval_ms 上限约束；默认 30 FPS 从 100 ms 改为 33 ms。预览、hybrid、多帧和双人实时 timer 分开使用定位/预览周期。
- (verified) run_dual_first_frame_experiment() 只读取一次 memory anchors，最多保留三张截图，分别注册后按接受状态、pair confidence、shape quality 和 mean anchor error 选择最强候选；所有候选都失败时仍 fail closed。
- (verified) SimulatedFollowRuntime 新增 footprint_radius。PoE2 页面实验实例使用 6 native px；路径规划、VectorPathTracker、模拟步进和 route diagnostics 共用膨胀后的只读碰撞图，原始 wall map 继续用于 clearance 证据。
- 聚焦回归：43 passed；compileall 和 git diff --check 待本轮收尾执行。

### D. 本轮仍未实机确认

- 真实双人 90% 首帧准确率尚未由连续实机样本统计确认。
- 手柄方向/幅度与 native 位移闭环、贴墙恢复和门后路线仍需在用户明确进行真实输入测试时验证。
- GUI 实验页仍是同步截图/识别链路；30 FPS 是定时器目标，不等于识别处理已达到 30 FPS。

### E. 下一轮方案验证

- 参考 Nav2 Regulated Pure Pursuit、DWB/DWA 和 TEB：先在纯离线 runtime 增加短时程候选输入评估（碰撞、clearance、目标进度、路线偏离、振荡惩罚），再接入真实输出；不把 A* 路线通过当作人物已移动。
- 增加 visual frame age、observed displacement、command duration、native before/after 的闭环诊断；若视觉位置不前进则降低输入幅度并左右交替恢复，超过 TTL 立即 neutral/release。
- 将实验截图/识别迁移到 bounded latest-frame worker，GUI 只消费最新结果，旧帧丢弃；内存 anchor 仍仅在首帧和明确 recovery 时读取。

### 2026-10-02 局部闭环控制与双人候选恢复

根因证据：旧跟踪器只根据 A* 路线取前视点输出一个向量，没有使用真实 native 位移估计速度，也没有
对未来短时间内的碰撞做检查；因此手柄方向或速度略有误差时会持续压向同一面墙。新增通用
`core.routing.local_controller.LocalMotionController`，以路线方向为基准评估 0/-15/15/-30/30/-45/45/
-75/75/±90 度的短轨迹，按目标进度、墙体清距、路线偏离、转向变化和运动速度评分；若所有候选均
碰撞则返回零向量，交由 runtime 的侧向恢复逻辑处理。runtime 对视觉样本计算指数平滑的 native
速度，并把局部控制诊断、预测清距、候选数量和拒绝数量写入 `FollowObservation.diagnostics`。
PoE2 实验页的卡墙阈值改为 8 个定位 tick，并把短视窗参数显式写入日志。

双人首帧的根因之一是颜色候选 NMS 没有识别 profile：不同颜色且相互靠近的两名玩家可能被当成同一
轮廓删除。现在不同 profile/identity hint 永不互相去重；注册器允许额外紧凑候选，先过滤低置信候选，
再对所有有序两人组合求解，避免一个噪声轮廓使整帧失败。正式页面和产品 session 最多向注册器提供
6 个候选，仍由内存锚点、相对几何、形状和 assignment margin 共同判定。

## [SYNC] 2026-10-02 闭环导航续审

### A. 范围声明

本轮重读 `local_controller.py`、`multiplayer_follow/runtime.py`、`vector_tracker.py` 和双人首帧注册调用方，验证目标附近振荡、沿路绕墙进度、重复视觉样本的卡墙判断以及安全路径简化是否保留清距代价。更新 geometry 接口、运行时诊断和行为测试；保持原始绘图模式与真实设备输出边界。

当前离线门洞模拟仍存在绕路偏离和恢复循环，因此不能把基础单元测试通过等同于完成导航。90% 双人准确率必须以带真值的真实样本评估。

本轮新增局部控制与近距离 profile 回归，聚焦回归为 41 passed，导航/页面/手柄相关回归为 46 passed，
`compileall` 通过。真实手柄方向/速度闭环、窄门和门后路线、双人 90% 实机准确率仍需后续授权后的
真实样本确认；本轮没有发送真实输入。
## [第2026-10-02-导航稳定性审查] 2026-10-02

### A. 本轮目标（阅读前声明）
**目标文件：**
- `src/auto_modules/core/routing/pathfinder/astar.py`、`grid.py`、`runtime.py`：确认路线代价、清距膨胀、简化和重规划是否真的阻止贴墙、窄路和死路。
- `src/auto_modules/core/routing/local_controller.py`、`vector_tracker.py`：确认手柄输出与 native 位移闭环、卡墙检测和恢复是否在重复帧、低帧率、速度误差下成立。
- `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_follow/runtime.py`、`multiplayer_localization/*`：确认双人首帧失败是否发生在候选生成、方向/镜像、锚点配对或实时过渡层。
- `src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py`、`presenter.py`：确认 30 FPS 目标是否被同步截图/识别阻塞，以及最新帧是否丢弃。
- `tests/poe2_live_terrain/*` 与 `data/poe2_live_terrain_test/*`：批量复核已有离线样本和诊断字段，建立可重复的准确率、延迟与闭环指标。

**本轮想弄清楚：**
1. 路线规划是否把角色 footprint、平均清距、低清距暴露和死路惩罚统一纳入 A* 与简化，而不是只在输出端补救。
2. 卡墙时到底是路线错误、输入轴/速度映射错误、视觉样本过期，还是恢复状态机没有触发。
3. 双人首帧偶发失败的最小失败层，以及是否能从现有真实样本计算 90% 指标。
4. 实验页是否存在“定时器按时触发但处理串行排队”的帧堆积问题。

### C. 本轮发现

- (verified) `PathFinder.find_path()` 的硬碰撞图、A* 清距代价和 `_route_is_safe()` 都在 `reference_native` 坐标工作；但实验页创建的所有候选 finder 仍以固定 downsample ladder 竞争，且 `build_obstacle_map()` 使用整除网格尺寸，地图尾部不足一个 factor 的区域被截断。这会让边界目标或门洞在候选之间出现不一致。
- (verified) `SimulatedFollowRuntime` 已有 footprint 膨胀、原图清距复核、DWA 风格局部候选和重复视觉帧去重；但是 `observed_velocity` 只用于速度幅度和预测碰撞，没有记录“输出方向—实际位移方向”的闭环误差，因此手柄基准/轴方向不一致时只能表现为持续贴墙，无法快速判定输入映射问题。
- (verified) 双人首帧的精确两锚点变换在 `DualFirstFrameRegistrar._joint_similarity_estimates()` 中成立；偶发失败主要落在 marker 候选筛选、`AnchoredAbsoluteRegistrar` 的 coverage/margin 门控或 close-pair midpoint fallback，而不是内存锚点读取。现有历史 JSON 有 `best_anchor_error` 约 7–20、coverage 约 0.58–0.95 的被拒样本，但没有批量准确率真值。
- (verified) `Poe2CaptureTestPage._tick_dual_motion()` 在 Qt GUI timer 中同步完成截图、HSV/墙体预处理、marker contour 和 tracker；当总耗时超过 timer interval 时，Qt 不会丢弃旧调用，而是串行延迟下一帧。这解释了“前面顺、后面卡/慢”，当前实验页还没有 bounded latest-frame worker。
- (partial) 真实手柄撞墙的最终主因仍需实机闭环日志确认；当前代码已经记录 `vector_native/vector_input/axes/observed_speed/visual_age_ms/no_progress_ticks`，但未记录 command 与实际位移夹角，无法区分速度误差和 basis 方向错误。

**修订的旧结论：** 原来认为“路线安全已由局部控制器覆盖”即可；现在确认它只能保证地图几何候选安全，不能证明设备输出与人物位移同向。原来认为“30 FPS timer 已足够”也不成立：timer 频率只是调度目标，实验页同步处理仍会积压。

**更新了 CODEBASE.md：** 待完成代码修复后同步更新 §5（路径代价、闭环控制、双人候选）与 §6（实验页帧流）。

**覆盖进度更新：** 本轮已精读上述路径规划、局部控制、双人首帧和实验页函数；真实手柄和带真值的双人样本仍为 `(partial)`，不能宣称 90% 或实机通过。

**下一轮计划：** 先做三个可离线验证的最小修复：网格尺寸向上取整并保留边界；增加 command/observed 位移方向误差与卡墙恢复诊断；将实验页双人截图识别改为 bounded latest-frame worker，GUI 只消费最新完成状态。随后运行聚焦回归和离线压力基准，再决定是否需要调双人门控阈值。

### C. SYNC 结果（代码已完成）

- `core/routing/pathfinder/coordinates.py` 的 `grid_size_from_map_shape()` 改为 ceil，保留非整除地图的边缘格；新增边界回归。
- `SimulatedFollowRuntime.update_follower_position()` 增加 command/native 位移 cosine、夹角和连续方向失配计数；连续三帧低 alignment 走现有左右交替恢复，不改变输入/网络边界。
- 新增 `ui/modes/poe2_live_terrain/dual_motion_worker.py`。生产 monitor profile 的双人实时链路现在由 worker 完成截图、识别、tracker tick；GUI timer 仅 drain latest result，旧结果被替换并计入 `dropped_results`。无 `localization_fps` 的测试 dummy config 保留同步 hook，未改变测试契约。
- 聚焦验证：`64 passed`（新增 worker latest-only 回归）；`compileall` 通过；`git diff --check` 无 diff 错误（仅已有换行提示）。

### D. 尚未实机验证

- 双人分开/靠近/重叠的真实 90% 首帧准确率仍无独立真值统计；本轮没有调整门控阈值来掩盖失败。
- 真实手柄方向、速度、贴墙/窄门/门后恢复仍需用户明确授权后测试；新增 alignment 诊断可区分 basis 方向错误和无位移/过期帧，但不能替代实机。
- 双人实时 worker 已解决处理旧帧积压，但首帧/恢复注册仍在 GUI 线程；需要下一轮再迁移并验证 Qt 截图后端的线程安全。

### E. 下一轮计划

- 用现有双人保存样本和后续三类真实样本批量统计 `anchor_error`、`assignment_margin`、`pair_confidence`、`shape_quality`、角度和 scale，按分开/靠近/重叠分组报告准确率。
- 在不发送输入的前提下做路线压力回放：开阔、贴墙、窄门、门后，比较 route length、minimum/mean clearance、low-clearance fraction、footprint collision 和局部候选拒绝数。
- 用户授权后先做开阔地短距离真实手柄闭环，再做贴墙和窄门；每次只测试一个变量并保留 neutral/release 门禁。

## [SYNC] 2026-10-02 运动闭环实验版设计落地

### A. SYNC 范围声明

**触发任务：** 在 PoE2 实验页内实现局部区域复杂度判定、开阔/受限控制策略切换、输入响应在线校准和序贯恢复；先保持模块独立，实际运行时通过同一观测快照高效协作，稳定后再抽取到底层引擎。

**直接变更文件：** 预计新增/修改 `features/poe2/live_terrain/experimental/multiplayer_follow/` 下的运动观测、闭环校准、局部区域分类和控制编排文件，以及对应测试和 PoE2 实验页接线。

**预计连带影响：** `LocalMotionController`、`SimulatedFollowRuntime`、`ProgramFollowOutput`、双人实时 worker、PoE2 采集页诊断、`CODEBASE.md` 和 PoE2 断点文档。保持单人中心定位、双人首帧注册、绘图模式和真实 Host/LAN 输入边界不变；真实手柄实验仍需用户明确启动。

### C. SYNC 结果

- 新增 `motion_models.py`、`motion_snapshot.py`、`complexity.py`、`motion_calibration.py`、
  `sequential_motion.py` 和 `closed_loop_controller.py`，通过同一份只读快照把局部复杂度、序贯
  位移反馈、路线短视窗和 stick/native 在线校准串起来。
- 复杂度迟滞、校准状态和控制器估计均按 role 隔离；runtime 传入真实视觉采集时间，过期帧不会被
  控制 timer 伪装成新鲜观测；程序输出优先采用闭环命令的持续时间。
- 修复 response 更新后误把 `SequentialMotionUpdate` 当作 calibration state 的回归；新增闭环
  角色隔离、过期视觉帧、命令持续时间和开阔/门洞/过期帧回放测试。本轮未发送真实输入。

## [SYNC] 2026-10-02 — 移动失败根因与安全清距回退

复盘 `poe2_live_terrain.log` 后确认第一次移动的路线本身可行（碰撞段为 0），但旧进程使用
`footprint_radius=6.0`，起点清距约 `4.775` 被 `minimum_clearance=6.0` 拒绝；同时一次 UI 延迟把
闭环脉冲放大到 `667 ms`，造成后半段过冲和贴墙。当前代码要求重启后显式使用 `footprint_radius=2.0`，
闭环命令持续时间不再被 UI timer 覆盖。

runtime 现在在严格清距候选为空时，对有明确角色半径的控制实例执行第二层物理安全回退：碰撞膨胀图仍
必须全程可走，原始墙体清距不得低于 `max(footprint_radius+0.5, 2.0)`；通用 `footprint_radius=0` 调用
不启用回退。新增 `plan_relaxed_candidate_route_count`、`plan_selected_clearance_mode` 和逐倍率
`relaxed_reason`，页面运动日志同步记录这些字段。离线复现旧失败位置现得到 `relaxed_clearance`
路线，首个目标 tick 为 `previewing/route_ready`，不再是 `no_safe_route`。

验证：聚焦 `64 passed`，全仓 `929 passed, 1 skipped, 10 subtests passed`，compileall/diff check
通过。本轮未发送真实输入，实机尚未证明手柄速度和窄门通过；下一次测试必须先重启程序并检查
`plan_context` 中的实际半径与脉冲时长。

## [SYNC] 2026-10-02 — 真实目标离线回放与崩溃防护

使用本次日志的真实地图 `P2_7:54BE4D92`、起点 `(528.754,1166.560)` 和目标 `(615.176,1209.302)`
离线回放：人物半径 2 的碰撞图没有阻塞，原路线最低墙距 `2.739`；先前新增的回退门槛 `3.0` 仍然
过高，导致 `no_safe_route`。门槛改为 `max(footprint_radius+0.5, 2.0)`，同一数据现在得到
`relaxed_clearance` 三点路线，碰撞段为 0。

同时修正 `program_probe.plan_context` 中硬编码的 `footprint_radius=6.0` 取证错误，并让
`SquareScreenCapture.close/__del__` 对 mss 跨线程 thread-local 释放异常安全、幂等。聚焦回归 `64 passed`，
全仓回归 `929 passed, 1 skipped, 10 subtests passed`，compileall 通过。本轮没有发送真实输入。

双人实时 worker 的停止流程增加有界 join；后台线程在页面对象释放前完成退出，超时只写诊断而不会阻塞
或强制销毁线程。最终聚焦回归 `65 passed`，全仓回归仍为 `929 passed, 1 skipped, 10 subtests passed`。

## [SYNC] 2026-10-02 — 真实样本离线探针闭环

为 `tools/debug/poe2_route_probe.py` 增加 `--offline` 路线回放入口，并把实机探针的路线参数与
PoE2 实验页统一为 `safety_margin=2`、`minimum_clearance=6`、`footprint_radius=2`。使用本次真实
`P2_7:54BE4D92` 地图和失败点击的起终点回放成功：3 个路点、碰撞段 0、最小墙距 `2.739`，选择
`relaxed_clearance`；离线模式不访问游戏、不申请管理员权限、不发送输入。聚焦测试 `65 passed`，
`compileall` 和 `git diff --check` 通过。

## [SYNC] 2026-10-02 — PoE2 实验清距参数放宽

为减少真实地图中“碰撞图可通行但额外墙距偏好拒绝”的误报，PoE2 实验页和路线探针将
`minimum_clearance` 从 `6.0` 调整为 `4.0`，仍优先选择严格路线；回退硬下限调整为
`max(footprint_radius, 2.0)`。人物半径仍为 `2.0`，碰撞膨胀图仍是不可绕过的实体安全约束，
通用 PathFinder 默认参数未改变。本次真实地图离线回放仍为可用路线，聚焦回归 `65 passed`。

## [SYNC] 2026-10-02 — PoE2 窄通道中心线碰撞

根据窄门反馈，PoE2 实验页关闭人物 footprint 膨胀，使用原始中心线墙体图：
`inflate_collision=False`、`footprint_radius=0.0`、`safety_margin=0`、`minimum_clearance=0.0`。
开阔区域仍由 clearance soft cost 优先，窄口不再被硬膨胀封死；局部控制器负责短窗口左/右/斜向
避障，连续无位移后进入侧向恢复。真实地图离线回放得到 2 点路线、碰撞段 0；新增窄通道回归后
聚焦测试为 `66 passed`。

## [SYNC] 2026-10-02 — 双人实时崩溃防护

- WER 对照日志确认工作台 native 崩溃集中在双人实时截图线程及停止/切换生命周期，另有独立的
  PathOfExile.exe 崩溃；普通页面异常不是同一类问题。
- 双人 worker 在本线程显式释放 thread-local capture，停止最多等待 3 秒，超时保留退休 worker；
  capture 线程使用独立 recognizer，Qt 图像转换保留命名 contiguous buffer，预览渲染限制为 12 FPS。
- 聚焦 PoE2 测试 `386 passed`，compileall 和 git diff check 通过；尚需重启后实机验证 WER 不再产生新记录。

## [SYNC] 2026-10-02 — 门后提前停止与单人监控 worker 收尾

- 离线复现最新实测：`P2_7:54BE4D92` 从 `(559.6648703,1183.0890744)` 到
  `(607.2905711,1216.7751075)` 仍有安全路线；旧 `stalled_no_escape` 由单一侧向恢复点失败触发，
  不是地图或目标坐标不可达。
- `SimulatedFollowRuntime` 卡墙后先重新规划真实目标；若局部方向仍为零，再按左右/前向组合尝试多个
  短恢复点，只有所有候选失败才进入 blocked。新增候选检查和选择下标诊断；实验页 motion 日志同步记录。
- 正式单人定位页的 `Poe2LocalizationWorker` 现在 stop 后有界等待 3 秒；超时 worker 进入退休集合并由
  finished 回调释放，新的监控不会与退休 worker 并发，shutdown 不提前释放 runtime。
- 聚焦验证：跟随 runtime `43 passed`；单人页面/worker `6 passed`；同一真实样本离线路线探针
  `route_available=true`。本轮没有发送新的真实输入，实机门后继续移动和 WER 复测仍待重启后进行。
## [SYNC] 2026-10-02 — PoE2 墙边起点与人物真实位置一致性

### A. SYNC 范围声明
**触发任务：** 排查人物通过窄门后距离目标仍有约 42.6 native 单位就停止的问题，确认人物真实坐标是否被墙体栅格误判，并修复首帧边界起点恢复。
**直接变更文件：**
- `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_follow/runtime.py`
- `tests/poe2_live_terrain/test_multiplayer_follow_runtime.py`
**预计连带影响：** PoE2 实验跟随 runtime 的首个规划、局部控制器输入脉冲和页面 `program_probe.motion` 诊断；不改变通用 `PathFinder`、碰撞膨胀默认值或绘图模式。

### C. SYNC 结果
**根因证据（verified）：** `P2_7:54BE4D92` 的真实停止点 `(575.748,1178.894)` 四舍五入为 `(576,1179)`，该 native 栅格 `wall=255/collision=255`；相邻 `(576,1180)` 为 `wall=0/collision=0`。目标距离为 `42.5996`，停止原因是 `stalled_no_escape`/`no_safe_route`，不是 `arrival_radius=8`。

**实现结果：**
- PoE2 runtime 在普通规划前先检查当前 native 点是否落在墙/空地栅格边界；若局部存在可行走起点且可安全到达目标，发出有界 `wall_start_recovery` 脱困脉冲。
- 首次规划直接返回 `no_safe_route` 时也立即走边界恢复，不再等待 stalled watchdog 或进入失败冷却。
- 在新视觉帧仍落在同一墙边栅格期间，继续提供同一有界脉冲；不会因为局部控制器把墙内起点判为无候选而释放为零向量。
- 新增 `observed_position_metrics` 取证字段，区分真实观测点（可能是墙边栅格）与恢复路线使用的可行走起点。

**验证：** 新增墙边首个规划回归；跟随 runtime 聚焦测试通过，真实地图离线回放从首次 tick 即返回非零 `wall_start_recovery`，移动到可行走栅格后恢复 `route_ready`。未发送新的真实手柄输入。

**覆盖进度更新：** `runtime.py` 与 `test_multiplayer_follow_runtime.py` 已按本轮变更重读；`CODEBASE.md` 的 PoE2 跟随 runtime 算法和风险条目已同步。

## [SYNC] 2026-10-02 — 离线路线探针与恢复路线诊断对齐

### A. SYNC 范围声明
**触发任务：** 独立 `poe2_route_probe.py --offline` 仍直接调用 `_plan_safe_route()`，与页面边界恢复语义不一致；需要让离线证据准确反映人物真实观测格和临时恢复起点。
**直接变更文件：** `tools/debug/poe2_route_probe.py`、`src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_follow/runtime.py`。

### C. SYNC 结果
- 离线探针现在通过 `SimulatedFollowRuntime.tick()` 运行，与页面使用相同的 `wall_start_recovery` 契约；真实样本输出 `route_available=true`、`reason=wall_start_recovery`、恢复起点 `(576,1180)` 和非零向量。
- `FollowObservation.diagnostics` 新增 `planning_route_walkable` 与 `planning_route_collision_segments`，区分“从原始观测墙格开始的链”与“从临时可行走起点开始的计划链”；不会再把边界恢复的预期首段碰撞误报成路线穿墙。
- 离线探针仍不读取进程、不申请权限、不发送手柄输入。
- 相同墙边栅格和目标在连续帧中复用已验证的局部恢复路线，只重算归一化脉冲，不在每个 UI tick 重跑四级 A*；人物离开墙格或目标移动超过刷新带时自动失效缓存。
## [SYNC] 2026-10-02 — 小地图接触证据与撞墙恢复

### A. SYNC 范围声明
**触发任务：** 解决 PoE2 运行时在大地图判断可走、实际人物贴墙且不触发恢复的问题。
**直接变更文件：**
- `src/auto_modules/core/routing/contact_evidence.py`
- `src/auto_modules/core/routing/__init__.py`
- `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_localization/minimap_contact_adapter.py`
- `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_localization/__init__.py`
- `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_follow/runtime.py`
- `src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py`
- `tests/test_contact_evidence.py`
- `tests/test_poe2_minimap_contact.py`
- `tests/poe2_live_terrain/test_multiplayer_follow_runtime.py`
**预计连带影响：** 双人实时帧缓存、程序移动实验的控制 tick、局部恢复路径、运行时诊断日志和 PoE2 实验层导出接口。

### C. SYNC 结果
**根因证据：** 旧链路只校验 native 大地图路线，`DualVisualTracker` 没有把小地图墙体掩码交给跟随运行时；输入非零但人物位置无有效位移时，只有通用停滞计数，且最终由 30 秒超时停止。
**实现：** 新增坐标无关的 `ContactMonitor`，新增 PoE2 `inspect_minimap_contact()` 局部射线适配器；运行时接收局部墙体/左右可行走信息，连续无进展时优先局部脱困，两次局部脱困仍失败返回 `contact_relocalization_required`，UI 停止输入并请求已有双人恢复入口。
**连带重读文件：** `runtime.py`、`dual_motion_worker.py`、`capture_test_page.py`、`core/routing/__init__.py`、`multiplayer_localization/__init__.py`。
**CODEBASE.md 更新内容：** 增加接触证据模块、PoE2 小地图适配器、程序移动到局部恢复/重定位的调用链和风险记录。
**验证：** 目标测试 `73 passed`；`compileall` 通过。

**复读与扩散复核：** 重新读取 `ContactMonitor.observe()`、`inspect_minimap_contact()`、`SimulatedFollowRuntime.update_follower_position()`/`_tick_follower()`、`Poe2CaptureTestPage._tick_program_move_probe()`/`_update_program_probe_local_contact()`；确认输入输出边界仍为 `command -> native displacement -> minimap adapter -> runtime recovery`，没有把 PoE2 名称下沉到 core，也没有把真实输入放入识别模块。完整 PoE2 实验相关回归为 `365 passed`，`compileall` 和 `git diff --check` 通过。Serena 诊断仅保留仓库原有的 PySide6/NumPy/CV2 环境解析提示及既有类型提示，没有新增语法或运行时错误。
**下一步：** 进行一次真实短时程序移动测试；验收日志顺序应为 `program_probe.local_contact` → `contact_evidence`/`observed_displacement` → `contact_recovery`，若两次无效才出现 `contact_relocalization_required`，并确认恢复后没有重复高频读内存。

## [SYNC] 2026-10-02 — 墙角恢复分支被微脉冲覆盖（已修复）

- **实机证据：** 两次测试中 Host lease、设备连接和 `leftStickX/Y` 均正常；人物 native 坐标连续不变，
  `local_obstacle_ahead=true`，无进展计数从 73 增长到 132，但 `recovery_attempts=0`，每 tick 都是
  `reason=wall_start_recovery`，使用同一个约 `0.85 native` 的 escape origin。最终只因 PoE2 失去前台停止。
- **根因：** `_tick_follower()` 在接触证据达到恢复门后仍优先调用缓存的 `_wall_start_recovery_command()`，
  该早期 return 阻断了 `contact_recovery`、恢复候选和重定位门。
- **实现：** 接触恢复现在优先于墙边微脉冲；新增 `_contact_recovery_command()`，根据小地图左右空闲度在
  半径 12 native 内选择可行走起点并规划到真实目标，输出有界侧向向量。仍不改写观测位置、不启用人物膨胀；
  两次局部恢复无位移后仍走 `contact_relocalization_required`。
- **验证：** 新增墙角顺序回归；跟随 runtime `47 passed`，PoE2 接触/采集/实验集合 `387 passed`，
  compileall 通过。下一次实机验收重点看 `wall_start_recovery → contact_recovery` 的日志顺序。

## [SYNC] 2026-10-02 — 大位移方向错配被误判为撞墙（已修复）

- **证据：** 新一轮日志中人物由 `(513.771,1153.771)` 移动到 `(514.259,1145.056)`，位移
  `8.729 native`；对应 native 地图点和周边区域 `wall_layer=0`、clearance 约 `25`。输入 Host 正常，
  但上一条横向恢复命令与延迟生效的纵向移动夹角约 `97°`，接触证据仍把它标成 `no_progress`，随后触发
  `contact_relocalization_required`。
- **根因：** `ContactMonitor` 将低 alignment 与小位移并列作为撞墙条件，忽略了游戏手柄输入和视觉帧的
  时序延迟；方向错配是校准信号，不是当前位置无位移的证明。
- **实现：** 接触门现在只由“非零命令 + 位移低于 `0.25 native`”累积；alignment 仍保留诊断和闭环标定。
  有明显位移时，即便小地图上一帧前方有墙，也不会直接触发墙体重定位；只有再次连续无位移才恢复。
  新增大位移正交运动回归，并限制带局部墙证据时的方向错配不能单独升级恢复。
## [SYNC] 2026-10-03 00:20 — 连续撞墙防抖与双人重定位续跑

### A. SYNC 范围声明
**触发任务：** 实机通过门后仍因两帧无位移过快进入 `contact_relocalization_required`；现有页面停止输入后只重启视觉跟踪，没有强制读取双人内存锚点，也没有恢复原目标。
**直接变更文件：**
- `src/auto_modules/core/routing/contact_evidence.py`（仅由 runtime 注入可配置连续样本门，本文件算法契约不变）
- `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_follow/runtime.py`
- `src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py`
- `tests/test_contact_evidence.py`
- `tests/poe2_live_terrain/test_multiplayer_follow_runtime.py`
- `tests/test_poe2_capture_test_page.py`
**预计连带影响：** PoE2 程序移动/跟随 runtime 的接触恢复时序、双人首帧读取次数、worker 新帧派发、Host 输出释放和目标点击状态；不改变绘图模式、通用 PathFinder 默认值或双人人物 mask 规则。

### B. 影响扩散与重读
- `SimulatedFollowRuntime.__init__()` 新增 `contact_required_samples`，`add_follower()` 为每个角色显式创建独立 `ContactMonitor`；默认仍为 `2`，PoE2 页面真实实验组合传 `4`。
- `Poe2CaptureTestPage._tick_program_move_probe()` 在重定位请求时先保存 native target、actor identity、controller，释放旧 output 后进入 recovery context。
- `Poe2CaptureTestPage._start_dual_motion(recovery=True)` 不复用旧首帧，调用 `run_dual_first_frame_experiment(..., force_memory_read=True)`，完成一次新的双人内存锚点和当前小地图注册。
- `_drain_dual_motion_worker()` 与同步 `_tick_dual_motion()` 在收到新的 tracking 帧后调用 `_maybe_resume_program_probe_after_relocalization()`；只有新帧新鲜且角色可见才用原 target 自动重建程序移动 output。

### C. 本轮发现与结果
**根因证据（verified）：** 最新日志中人物已经移动约 `20.52 native` 并通过门；停止前 `wall_ahead=True`、`wall_distance=6.0`，但只累计 `consecutive_no_progress=2` 就触发重定位。原页面分支调用 `stop_program_move_probe()` 后的 `_start_dual_motion(recovery=True)` 会复用 `_last_dual_first_frame_result`，因此没有新增内存读取，也不会恢复目标。
**实现结果：**
- 接触门现在按运行时配置计数；PoE2 程序移动和跟随实验使用 `4` 个有效无进展视觉样本，通用 runtime/test 默认仍为 `2`。
- recovery 只在冷却窗口外触发一次；保存的目标/角色/控制器不丢失。重定位期间不发送真实输入。
- 强制 recovery 只做一次双人内存锚点读取和首帧几何注册；registration 成功后等待至少一帧新视觉结果，再自动以原目标恢复输入。失败则清理 recovery context，保持安全停止，不循环读取。
- 新日志步骤：`program_probe.relocalization_started`、`program_probe.relocalization_context_saved`、`program_probe.relocalization_registration_success`、`program_probe.relocalization_resumed`、`program_probe.relocalization_failed`。

**验证：** `75 passed`（接触证据、双人跟随 runtime、PoE2 采集页），`compileall` 通过，`git diff --check` 通过。尚未发送新的真实输入；下一次实机重点确认日志顺序为 `contact_recovery` → `relocalization_started` → `dual_first_frame.memory_success`（新增一次）→ `relocalization_resumed`，并确认原点击目标继续执行。

**修订的旧结论：** 旧记录称“页面请求已有双人恢复入口，但恢复完成后仍需人工重新 arm 输入”；现已改为页面保存并自动恢复原目标，只有内存/首帧注册失败才要求人工重新启动。

**下一轮计划：** 实机短路径穿门测试，核对四样本防抖、恢复读取次数与目标续跑；若仍误判，优先分析同一 captured_at_ms 的小地图接触证据和视觉位移，不再直接放宽墙体或人物半径。

## [SYNC] 2026-10-03 09:10 — wall_start_recovery 生命周期与无进展脱困

### A. SYNC 范围声明
**触发任务：** 实机人物通过门后仍停在可行走区域，日志持续 `wall_start_recovery`；需要修复恢复分支生命周期、无进展监视和程序会话报错的隔离。
**直接变更文件：** `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_follow/runtime.py`、`tests/poe2_live_terrain/test_multiplayer_follow_runtime.py`、`docs/POE2_LIVE_TERRAIN_CURRENT_STATE.md`、`ITERATION_LOG.md`。
**预计连带影响：** 运行时局部墙边恢复、接触证据升级、双人程序移动测试的停止/重定位入口；不改变地图数据和人物膨胀参数。

### B. 影响扩散与重读

本轮已重读 `SimulatedFollowRuntime._tick_follower()`、`_wall_start_recovery_command()`、`_wall_start_recovery()`、程序移动页面 tick 以及 Host lease 处理；先用离线复现确认后再修改。

## [SYNC] 2026-10-03 — 原始射线与真实接触分离

- **根因：** 人物通过障碍后，`wall_ahead` 仍可能由半径为 1 的局部 beam 命中旁侧墙体；旧接触证据又在视觉短暂停顿时继续生效，最终把“靠近墙/方向受阻”升级为“撞墙并重定位”。大地图当前位置仍为 `wall=0`、`collision=0`。
- **实现：** 小地图适配器增加中心线阻断、原始射线与窄道诊断；runtime 接收 `blocking_wall_ahead` 和 `escape_available`，不再把原始射线直接作为接触。通用 `ContactMonitor` 增加接触状态和脱离条件，出现有效位移或路线进展时清除旧证据；有出口时保留接触证据并继续局部脱困，没有出口且多次脱困失败才允许全局重定位。
- **边界：** 未启用人物 footprint 膨胀；墙体距离仍是诊断/软代价，PoE2 适配器不向 core 下沉游戏概念。
- **验证：** 小地图适配器、接触证据和双人跟随 runtime 相关测试 `61 passed`；新增“阻断但存在出口时持续局部脱困、不升级重定位”回归。尚未发送新的真实输入，待实机短路径验证日志中的 `raw_wall_ahead`、`blocking_wall_ahead`、`narrow_passage`、`escape_available` 和 `ContactState` 转换。

### C. 本轮发现与结果

**根因证据（verified）：** 08:54:52–08:54:56 的 65 个 tick 中人物 native 坐标完全不变，`local_obstacle_ahead=False`、`local_escape_available=True`，但每次仍由顶部 `_wall_start_recovery_command()` 提前返回；因为缓存位置随 tick 更新，恢复 episode 永远不会结束。另一次 `program_probe.write_failed` 的完整堆栈是 Host `Program session expired or was revoked`，它是 lease 过期后的安全失败，不是地图碰撞判定。

**实现结果：**
- 墙边恢复起点固定为 episode 起点；最多允许 3 个微脉冲，超过后交回停滞/局部恢复链路。
- 最新小地图已确认中心线开放时不再创建新的墙边脉冲；若之前已经落入墙格恢复，最多发出有限的 `stale_wall_raster_recovery` 过渡脉冲，避免 native 栅格滞后导致立即停止。
- 新增离线回归覆盖“开放小地图 + stale wall raster”和“位置长期不变时恢复有界”；runtime 聚焦测试 `53 passed`。

**验证与下一步：** 已通过聚焦 runtime 测试；尚未发送新的真实输入。实机应看到 `wall_start_recovery` 最多三次，随后是 `stale_wall_raster_recovery`/`contact_recovery`/`stalled_recovery` 或一次 `contact_relocalization_required`，不应再次出现无限重复。Host lease 过期仍保持显式失败和安全释放，不做隐式续租。

## [第审查轮] 2026-10-03 — PoE2 双人实验完整链路复核

### A. 本轮目标（阅读前声明）
**目标文件/符号：**
- `src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py`（核对点击目标、实时 worker、程序移动、重定位和停止清理的状态转移）
- `src/auto_modules/ui/modes/poe2_live_terrain/dual_motion_worker.py`（核对单帧异常是否终止实时定位线程）
- `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_localization/dual_motion.py`（核对双人 marker 丢失/歧义与 recovery 状态）
- `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_follow/runtime.py`（核对视觉时间戳、接触证据、路线和重定位门的交互）
- `src/auto_modules/adapters/virtual_gamepad/program_output.py`、`src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_follow/program_output.py`（核对 Host 租约、TTL、异常释放和输出生命周期）

**本轮想弄清楚：**
1. 单帧丢标记、截图异常或识别异常是否会错误停止整条链路；
2. tracker recovery 是否保留用户点击目标和程序控制上下文；
3. 地图显示坐标、canonical/native 路线坐标和手柄输入坐标是否在每一跳一致；
4. 手柄租约过期、线程停止超时、窗口失焦和异常清理是否会留下卡死或重复恢复；
5. 现有测试是否覆盖这些真实运行边界。

### C. 本轮发现
**关键发现（verified）：**
- `P1` `Poe2CaptureTestPage._tick_program_move_probe()` 在 `state is None` 或选中角色的 `state.players` 为 `None` 时立即调用 `stop_program_move_probe()`（约 1536–1559 行）。`DualVisualTracker._assign()` 在单帧丢标记、候选越界或身份歧义时合法返回空映射（`dual_motion.py::_assign()` 约 232–266 行），但 tracker 只把它发布为 `tracking/degraded`，没有给程序移动层一个等待窗口。因此一帧 marker 抖动会释放 lease，而不是等待恢复/重定位；现有测试只验证 tracker，不验证程序移动层。
- `P1` `Poe2CaptureTestPage._drain_dual_motion_worker()` 和同步 `_tick_dual_motion()` 在 `state.recovery_requested` 时调用无 `preserve_program_probe_recovery=True` 的 `stop_dual_motion()`（约 1150–1163、1240–1251 行）。该调用会先 `stop_program_move_probe()`，再 `stop_follow_experiment()`；后者清除点击目标和 follow runtime。程序移动自己的 contact 重定位分支会提前保存上下文，但视觉 tracker 独立触发 recovery 时没有保存，导致目标丢失且无法续跑。
- `P1` `Poe2DualMotionWorker._run()` 把 `_capture_one()` 的截图、识别、OpenCV、tracker 任一异常都包在一个总 `try` 中（约 171–190 行），一次瞬时异常就 emit `failed`，页面停止双人定位和程序输入。没有单帧丢弃/连续失败阈值；页面把线程失败显示为整个实验失败。
- `P1` `_start_dual_motion()` 的 recognizer clone 失败分支仍把 `worker_recognizer` 留为 GUI 线程的 `self.recognizer`（约 960–975 行），与“隔离 recognizer”的注释相反。若 `HSVRecognizer` 的 native CLAHE/内部缓存被 GUI 和 worker 并发使用，存在数据竞争或 native 崩溃风险。
- `P1` worker 停止等待超时后，`stop_dual_motion()` 仅把旧 worker 放进 `_retired_dual_motion_workers`，随后允许 `_start_dual_motion()` 创建新 worker（约 1038–1067、976–997 行）。新旧 worker 仍可能同时调用同一个 `preview_provider`；保留 Python 引用只能防止悬空回调，不能保证截图后端线程安全。
- `P1` 双人局部纠偏 frame 的 `local_player` 在 worker 和同步路径都固定为截图中心（`dual_motion_worker.py:153`、`capture_test_page.py:1209`），而 `DualVisualTracker.tick()` 会把该点传给 `transform_feature()` 后再做 `LocalMapMatcher.match()`（`dual_motion.py:159–172`）。首帧 registrar 会用主角色 marker 替换该点，但后续双人非中心视口的局部纠偏没有复用同一角色锚点/两人几何中心，可能把局部匹配 origin 错移，表现为后续漂移或反复 recovery；现有测试使用中心点构造 frame，未覆盖双人偏心视口。
- `P1` `Poe2DualPlayerPositionSource.read_many()` 为角色身份使用 `metadata + entity vector index`（`memory_anchors.py::_identity_for()`），没有稳定 entity id。实体列表重排或两名角色 metadata 相同而 index 改变时，恢复后的 identity 可能与保存的 program role 不同，`_maybe_resume_program_probe_after_relocalization()` 会因 combo 找不到角色而清除目标，表现为“重定位成功但不续跑”。这是基于实现的兼容性风险，需用同职业双人/实体顺序变化样本验证。
- `P2` `_update_program_probe_local_contact()` 只捕获 `TypeError/ValueError/AttributeError`（约 1759–1804 行）。`cv2.error`、`IndexError`、`RuntimeError` 或 mask shape/stride 异常会冒泡到 `_tick_program_move_probe()` 的总捕获，被错误记录成 `program_probe.write_failed` 并停止手柄输出。
- `P1` 当前 snapshot/instance identity 只在初始化、首帧内存读取和重定位时校验；实时 worker 不周期性验证 PoE2 area instance。切图/传送/死亡后如果视觉 mask 仍能产生可接受位移，旧 native map、旧 target 和旧 transform 可能继续被使用，runtime 的 map identity 检查无法发现，因为它只比较同一份旧 snapshot identity。

**已确认没有发现的断点（verified）：**
- 地图点击的显示坐标 → `localization_source_point()` → reference/native 目标 → overlay 显示坐标往返误差有明确日志和测试；当前没有证据表明这条转换本身是本轮卡墙的根因。
- `ProgramFollowOutput.apply()` 在停止状态先写中性再释放角色 output；`ProgramGamepadOutput.close()` 也执行 stop/release 后关闭 client，正常路径具备安全中性清理。Host `Program session expired or was revoked` 仍是租约边界失败，不应被解释为路线或碰撞成功。

**测试结果：**
- `python -m pytest tests/test_poe2_dual_motion_worker.py tests/test_poe2_capture_test_page.py tests/poe2_live_terrain/test_multiplayer_motion.py tests/poe2_live_terrain/test_multiplayer_follow_runtime.py -q`：`90 passed`。
- `python -m pytest tests/poe2_live_terrain -q`：`366 passed`。
- 本轮未修改业务源代码，未发送真实手柄、键盘、鼠标或网络输入；上述 P1/P2 仍是需修复或新增回归测试的审查结论。

**修订的旧结论：** 原断点文档把“tracker 已有 degraded/recovery”视为程序移动可以安全等待的保障；本轮确认页面层仍把 marker 缺失压成立即停止，二者状态契约并不一致。原文档还只记录了 worker 引用保留可以防止 Qt 回调悬空；本轮补充确认，停止超时后启动新 worker 仍有共享截图后端并行风险。

**下一轮计划：** 先在不改变算法参数的前提下新增/执行四类离线回归：单帧 marker 丢失的程序移动等待、tracker recovery 保留目标、worker 单帧异常继续采样、停止超时禁止并行 worker；随后单独校准双人局部纠偏的 `local_player` 语义和实体 identity 稳定键，再决定代码修复顺序。

## [第修复轮] 2026-10-03 — 双人实时链路异常隔离与资源生命周期

### A. 本轮目标（阅读前声明）
**直接变更文件候选：**
- `src/auto_modules/ui/modes/poe2_live_terrain/dual_motion_worker.py`（单帧异常隔离、失败计数、线程退出条件）
- `src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py`（marker 缺失等待、recovery 上下文、worker 停止互斥、recognizer 隔离、局部接触异常分类）
- `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_localization/dual_motion.py`（双人局部纠偏锚点契约）
- `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_localization/memory_anchors.py`（恢复身份稳定性边界）
- 相关 `tests/`（每个修复补最小回归）

**本轮先验证：**
1. 当前 worker、页面 timer 和 output lease 的真实异常传播路径；
2. 页面对象是否已有可复用的 recovery/等待状态字段；
3. `HybridFrame.local_player` 在 matcher 中的语义，避免用错误锚点修复漂移；
4. 修改是否会影响既有停止、重定位和测试页面生命周期。

### C. 本轮发现（根因确认，代码修改前）
**关键发现（verified）：**
- `Poe2DualMotionWorker._run()` 的总异常边界会把任意单帧截图、识别或 tracker 异常升级为线程终止；页面收到 `failed` 后立即停止双人实时和程序输出，瞬时后端抖动会表现为“程序崩溃/卡住”。
- `_start_dual_motion()` 的 clone 失败分支实际仍把页面 recognizer 交给后台线程；这会让 GUI 预览与后台 worker 共享带 native 状态的识别器，存在并发访问和原生崩溃风险。
- worker 停止超时后，旧实例仍可能使用截图后端，但 recovery 会继续创建新 worker；这会造成同一 capture provider 的并行调用。
- `DualVisualTracker._assign()` 合法返回空映射时，页面没有 dropout grace；同时 tracker 的局部 matcher 使用 `HybridFrame.local_player`，而 worker/同步路径固定填截图中心，双人偏心时会产生错误局部纠偏。
- `_update_program_probe_local_contact()` 的异常分类过窄，接触证据异常会冒泡到 `_tick_program_move_probe()`，被误记为 Host 写入失败并停止真实输入。

**修订的旧结论：** 之前将“tracker 已有 degraded/recovery 状态”和“worker 引用保留”视为足够的安全隔离；本轮确认页面层仍把 degraded marker 丢失压成终态，且保留引用不能阻止 stop timeout 后的并行 native capture。

**下一步：** 先为单帧异常继续采样、clone 失败同步回退、停止超时互斥、marker dropout grace 和偏心局部锚点补回归；再实现最小修复并重新同步 CODEBASE。

## [SYNC] 2026-10-03 — 双人实时异常隔离、恢复续跑与偏心锚点

### A. SYNC 范围声明
**触发任务：** 修复 PoE2 双人实验频繁报错、卡住、实时定位退出和资源占用异常；保持底层模块独立，不改变地图墙体或人物膨胀参数。
**直接变更文件：**
- `src/auto_modules/ui/modes/poe2_live_terrain/dual_motion_worker.py`
- `src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py`
- `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_localization/dual_motion.py`
- `tests/test_poe2_dual_motion_worker.py`
- `tests/test_poe2_capture_test_page.py`
- `tests/poe2_live_terrain/test_multiplayer_motion.py`
**预计连带影响：** 双人实时 worker 的异常传播、页面 recovery/跟随目标状态、marker dropout、局部匹配锚点；不改变正式绘图模式、地图数据契约、路线碰撞参数或真实输入安全门。

### B. 影响扩散与重读
- worker 新增 `frame_failed` 诊断信号、连续失败阈值和单帧丢弃；只有达到阈值才触发页面终止。
- 页面只在 recognizer 能复制配置并得到独立实例时创建后台 worker；克隆失败自动回同步 timer，避免共享 GUI/native 识别器。
- worker 停止超时后设置 pending restart，等待旧 worker `finished` 后才恢复，禁止同一截图 provider 并行调用。
- `DualVisualTracker` 保存首帧主角色局部锚点，marker 短时丢失使用有界预测位置；连续超时才请求 recovery。
- 视觉 recovery 前保存跟随目标/角色/模式，新鲜 tracking 帧到达后重建 follow runtime；局部接触采集捕获所有普通异常并分类为诊断缺帧。

### C. SYNC 结果
**实现结果（verified）：**
- worker 的一次截图、OpenCV、识别或 tracker 异常不再立即杀死线程；默认连续 3 次失败才发出 `failed`，中间通过 `frame_failed` 记录失败次数，成功帧会清零连续失败计数。
- clone 失败时 `worker_recognizer` 保持 `None`，页面使用同步路径；未把 `self.recognizer` 传入后台线程。
- stop timeout 后 recovery 被延迟到旧 worker 完成，新增 `dual_motion.restart_deferred/restart_resumed` 日志。
- marker 丢失默认允许 2 帧 grace，状态为 degraded 且保留预测 native 点；第三次仍无候选才请求一次 recovery。首帧主角色位置成为局部 matcher 锚点并跨视口平移更新。
- 视觉 recovery 保存并恢复点击目标和角色选择；局部接触异常只记录 `local_contact_failed`，不会伪装为 `program_probe.write_failed`。

**验证：** `python -m pytest tests/test_poe2_dual_motion_worker.py tests/poe2_live_terrain/test_multiplayer_motion.py tests/test_poe2_capture_test_page.py tests/poe2_live_terrain/test_multiplayer_follow_runtime.py tests/test_contact_evidence.py -q`：`101 passed`；`python -m pytest tests/poe2_live_terrain -q`：`368 passed`；`python -m compileall -q src/auto_modules`：通过。未发送真实手柄、键盘、鼠标或网络输入。

**剩余风险：** 实时 area instance 低频校验和 memory anchor 稳定 identity 尚未在本轮改动；首帧/恢复注册仍可能在 GUI 线程短暂占用。实机需观察 `frame_failed`、`restart_deferred`、`markers_missing_grace` 和 `follow_recovery_resumed` 日志。

## [SYNC] 2026-10-03 — 双人实时链路全面复审与生命周期收口

### A. SYNC 范围声明
**触发任务：** 用户要求再次全面检查双人实时定位实验，重点确认报错、卡住、崩溃、资源并行和恢复状态是否仍有缺口。
**直接变更文件候选：**
- `src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py`
- `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_localization/dual_motion.py`
- `tests/test_poe2_capture_test_page.py`
- `tests/poe2_live_terrain/test_multiplayer_motion.py`

**预计连带影响：** 双人 worker 启动/停止顺序、页面关闭和换图时的延迟恢复、单角色 marker 短时丢失、故障日志频率；不改变首帧几何算法、地图坐标契约或真实输入适配器。

### B. 根因取证前置结论
本轮先沿 `_start_dual_motion → stop_dual_motion → worker.finished → _on_dual_worker_finished`、
`DualVisualTracker.tick → _assign → _map_players` 和 worker `_run` 路径复核，并执行现有聚焦回归作为基线：`96 passed`。
已确认待验证的风险：旧 worker stop timeout 后 `_start_dual_motion` 会在检查 retired worker 之前执行首帧读图；单角色 marker 丢失会立即将另一角色输出为 `None`；页面延迟 restart 没有关闭/换图门控；frame_failed 信号可能按失败帧刷 UI 日志。

### C. SYNC 结果
**根因确认与修复：**
- `_start_dual_motion()` 现在在停止当前 worker、停止同页预览后，先检查所有 retired worker 的真实运行状态；只要仍有一个运行，就记录 `restart_deferred` 并返回，不执行新的首帧截图、内存锚点读取或新 worker 创建。
- `DualVisualTracker` 改为每个 identity 独立维护 marker dropout 计数。单角色短时丢失时保留共同位移后的预测 native 点，状态为 `markers_partial_grace/degraded`；只有该 identity 超过 grace 才请求 recovery，并把过期身份写入 diagnostics。
- 页面增加 dual session token 和 closing 门控；清图、换图、reset、shutdown 和主动 stop 都取消 pending restart。延迟回调必须通过 token、snapshot 和 closing 检查，避免窗口关闭后重新启动截图线程。
- retired worker 的运行状态同时兼容属性和可调用方法；frame_failed 日志在高阈值配置下限流并记录 suppressed 计数。日志侧栏仍受 500 行上限保护。

**验证：** 新增边界回归后，聚焦链路 `105 passed`；`compileall` 通过。此前 `96 passed` 基线中的原有行为仍通过；未发送真实输入或网络同步。

**仍需人工/实机验证的边界：** 实时 area instance 低频校验、memory entity identity 在实体重排时的稳定性、首帧/恢复注册的 GUI 线程耗时、真实 native capture 在 Windows 关闭时的退出时序。这些属于下一轮独立风险，不应伪称本轮已解决。

**C 补充：** 复审后又将 closing 状态加入 worker result/failed/frame_failed 的回调门控，并让主动 `stop_dual_motion()` 清除 pending restart；新增改动通过采集页、tracker、worker 聚焦回归 `48 passed`。CODEBASE §4/§5/§6/§9 和本断点文档已同步。

**最终验证：** `python -m pytest tests/poe2_live_terrain -q`：`369 passed`；`python -m compileall -q src/auto_modules` 与 `git diff --check` 通过。全量测试为 `963 passed, 2 skipped, 10 subtests passed, 1 failed`，唯一失败是环境缺少 `pydirectinput` 发行元数据的既有 `tests/test_distribution.py`，与本轮变更无关。

**修订的旧结论：** 原先把“有 retired worker 引用”视为足够的并行隔离，现确认必须在首帧读取前检查其运行状态；原先把“有候选即清零全局 dropout”视为合理，现改为 identity 级计数，避免丢失的控制角色立即失去位置。

## [SYNC] 2026-10-03 — 双人同目标移动实验

### A. SYNC 范围声明
**触发任务：** 在 PoE2 数据采集页新增独立的双人同目标移动测试场景。
**直接变更文件：** `src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py`、`tests/test_poe2_capture_test_page.py`、`docs/plans/2026-10-03-poe2-dual-target-move-design.md`、`docs/plans/2026-10-03-poe2-dual-target-move-implementation-plan.md`。
**预计连带影响：** 地图点击分发、双人视觉样本时间戳、`SimulatedFollowRuntime` 双角色规划、`ProgramFollowOutput` 各控制器 lease、双人 worker 恢复、页面停止与关闭、地图路线 overlay。下一步回读这些调用边界，再更新 CODEBASE 和断点。

### C. SYNC 结果
**关键发现（verified）：** 双人目标运行时在有效点击后分别用真实视觉时间戳更新两个 follower，独立规划并写入控制器 1/2；整体失效、异常及重定位释放两个 lease，角色到达或过期只释放本角色。人工沿地图点击、native 变换、规划、手柄输出、重定位恢复和停止路径逐跳核对。发现 overlay 原先在 `FollowObservation.route` 为空时仍从人物直连目标，误示可达路径；新增先失败的回归用例后，改为仅绘制真实路线，目标仍单独标记。
**修订的旧结论：** 原先认为“显示了人物到目标的线”即可代表规划结果；现确认路线为空时这条线由 UI 拼接生成，不能当作规划证据。
**CODEBASE.md 更新内容：** §6 F-POE2-DUAL-TARGET-MOVE 第 7 跳及 §5 页面双人同目标算法第 6 步，明确路线只来自 planner；当前断点同步无路径显示约束。

**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|---|---|---|---|---|
| `src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py` | 深度完整 | 深度完整 | 既有+1 | 本轮重读待命、地图点击、双角色 tick、overlay、重定位保存/续跑、输出释放及 worker 停止边界；修正无路径假直线。 |
| `tests/test_poe2_capture_test_page.py` | 深度完整 | 深度完整 | 既有+1 | 复核 17 个新场景假手柄用例，补充无路径 overlay 回归并消除新用例的可选属性诊断。 |
| `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_follow/program_output.py` | 深度完整 | 深度完整 | 既有+1 | 重读 arm/apply/release/close 的角色 lease 边界，确认停止状态先发中性向量再释放。 |

**验证：** 双人同目标测试 `17 passed`；采集页加 PoE2 专项回归 `416 passed`，`compileall` 与 `git diff --check` 通过。Serena 对新双人同目标方法及新增测试无剩余类型诊断；页面其他既有诊断和语言服务缺少环境依赖提示未在本任务中清理。自动测试全为假输出，未向游戏发送真实手柄输入，也未验证两名角色实机到达。实机仍需核对 UI 身份与 Host 控制器编号、游戏焦点和真实位移。

## [SYNC] 2026-10-03 — 双人同目标实机日志基线

### A. SYNC 范围声明
**触发任务：** 根据用户报告的双人同目标实机成功测试，核对持久日志并固化可防回归的成功条件。
**目标文件：** `data/logs/poe2_live_terrain.log`（限定 17:38-17:41 的实机时段）；`tests/test_poe2_capture_test_page.py`（页面契约回归）；`src/auto_modules/ui/modes/poe2_live_terrain/presenter.py` 与 `capture_test_page.py`（坐标变换及输出链）；`docs/POE2_LIVE_TERRAIN_CURRENT_STATE.md`、`CODEBASE.md`（结论同步）。
**本轮想弄清楚：** 首帧变换、点击到 native 的往返、两个角色的距离/输出/到达与释放是否都有日志证据；区分测试进程伪数据和 `P2_7:54BE4D92` 实机数据；保护通用算法契约但不硬编码本地图角度或比例。

### C. SYNC 结果
**关键发现（verified）：** `data/logs/poe2_live_terrain.log` 在 17:38:09-17:41:08 的 `P2_7:54BE4D92` 实机记录，与 17:32-17:35 的 `Area:hash` 假输出测试可按 map identity 清楚区分。实机先初始化/抓图；双人首帧仅一次内存锚点读取，300x300 的三张候选帧均检出两名 marker，三次注册均 accepted，最高配对分数 0.890253。实时定位长期记录两人可见且 tracking，无该时段 ERROR/WARNING。地图点击 source=(1039,2099) 经 221 度/水平镜像的显示变换回到 native=(606.168047,1204.908149)，round-trip error=0；`scale=0.874` 属注册参数，不应被地图点击再次应用。

**真实移动证据（verified）：** 两名角色均进入 `program_ready`，同一目标下各有独立路线；66+ 采样中 P1 距离从 139.49 降至最小 1.59，P2 从 147.51 降至最小 6.54。33 条 Host 诊断中控制器 1 有 6 条 acquired、控制器 2 有 32 条 acquired；P1 到达后控制器 1 释放，控制器 2 继续输出，用户最终点击停止。用户主观报告实验成功，与两角色实机靠近目标及独立控制吻合。

**验收边界（verified）：** 实机日志没有 `dual_target.both_arrived`；P2 只短暂一次进入 `arrived`，随后又处于 `program_ready`，最后一条距离约 10.09，`recovery_attempts` 升至 41。P1 最后一条约 3.19、仍 `arrived`。因此本次证据不能写成“双人稳定同时到达”；没有全局 `relocalization_requested`，也不能声称已实机验证重定位。P2 后段为何反复离开目标需要独立诊断，不在本轮擅自调控制参数。

**修订的旧结论：** 原断点写“尚未做双手柄实机验证”已不准确；现在确认两控制器均真实发出向量且两人显著靠近同一目标，但原先用户口述的“成功”不能直接等同于程序记录的 `both_arrived` 终态。

**防回归措施：** `test_dual_target_click_round_trip_matches_real_rotated_reflected_run` 固定本次坐标往返样本及“注册比例不二次应用”契约；`test_dual_target_experiment_stops_after_sequential_arrivals` 固定逐人到达/释放和最终双人停机的状态机契约，不硬编码 221 度或 0.874 为通用默认。仅新增测试，无运行时/参数改动。

**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|---|---|---|---|---|
| `data/logs/poe2_live_terrain.log` | 未归档实机窗口 | 已核对窗口 | 1 | 按 map instance 隔离假测试和实机记录，核对首帧、点击、各角色距离/lease、停止及缺少 both_arrived。 |
| `tests/test_poe2_capture_test_page.py` | 深度完整 | 深度完整 | 既有+1 | 在既有假手柄场景上增加实测旋转镜像坐标样本与先后到达状态机回归。 |
| `src/auto_modules/ui/modes/poe2_live_terrain/presenter.py` | 深度完整 | 深度完整 | 既有+1 | 回读显示旋转/镜像的正逆变换，确认 scale/translation 不在地图点击上重复应用。 |
| `src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py` | 深度完整 | 深度完整 | 既有+1 | 核对 source/native/display 点击日志与双角色观察、lease 生命周期，未改运行时代码。 |

**验证：** 新增两条回归 `2 passed`；采集页加 PoE2 专项 `418 passed`。下一轮如需改善 P2 停靠，应先做末段视觉轨迹/Host 向量/局部接触联合诊断，再决定是否调整控制器，不能把地图专用 221 度变换写成默认值。

## [SYNC] 2026-10-03 — 双人近目标体积碰撞说明

### A. SYNC 范围声明
**触发任务：** 用户补充实机观察：两名角色挤在同一个目标点附近时存在体积碰撞，末段未同时进入到达半径并非当前阶段的重要问题。
**目标文件：** `CODEBASE.md` 的双人目标风险条目、`docs/POE2_LIVE_TERRAIN_CURRENT_STATE.md` 的实机基线与本轮 `ITERATION_LOG.md` 结论。
**本轮想弄清楚：** 保留日志中缺少 `both_arrived` 的客观事实，同时把体积碰撞标为用户观察下的合理解释和低优先级边界，避免把它误记成已证实的定位/导航故障。此轮不改运行时或测试。

### C. SYNC 结果
**关键发现：** (verified) 实机日志仍只证明两人先后接近同一目标、未在同一 tick 同时 `ARRIVED`；(user-observed) 两名有体积的角色在同一个目标点附近发生碰撞，用户认为不影响本阶段实验成功。日志本身没有人物碰撞体或物理接触证据，不能把碰撞机制写成代码已验证事实。
**修订的旧结论：** 原先把 P2 末段反复离开到达半径列为 P1 稳定停靠/控制风险并建议立即独立定位；结合实机观察，该现象更适合作为同点目标的低优先级验收边界，不等同于定位或寻路故障。本阶段仍保留手动停止和双角色独立释放，不改参数。
**CODEBASE.md 更新内容：** §9 将 `_tick_dual_target_experiment_impl()` 风险从 P1 调整为 P2 的同点体积占用/程序终态差异，明确“碰撞为用户观察，日志仅证实未同时到达”。断点文档同步当前验收含义。
**覆盖进度更新：** 本轮只回读 `CODEBASE.md` §9、PoE2 当前断点相关段落及前一轮日志结论；没有源文件改动，原代码覆盖状态不变。
**下一轮计划：** 暂不处理该边界；只有产品需要无人值守地判定“双人完成”时，才设计共享目标区域或双人不同停靠点，并补实机验收。

## [SYNC] 2026-10-03 — PoE2 双人实时角色跟随与实验窗口缩放

### A. SYNC 范围声明
**触发任务：** 用户确认 P1/P2 双向实时角色跟随，要求实验人物半径默认 3 且可调，并修复实验窗口放大后小地图不随动、模块不能拖拽调整的问题。
**直接变更文件：** `experimental/multiplayer_follow/runtime.py`、`capture_test_page.py`、`capture_monitor_window.py`、`ui/widgets/scalable_map.py`、新增 `ui/widgets/aspect_preview.py` 及对应三个 Qt/运行器测试文件。
**预计连带影响：** `PositionSample` 目标时间契约、`ProgramFollowOutput` 的角色 lease、双人视觉 worker 的 `captured_at_ms`、定点点击实验、重定位恢复、地图 overlay 和截图预览尺寸同步。接下来按该范围回读代码与回归结果，再原位同步 `CODEBASE.md` 与 PoE2 当前断点。

### C. SYNC 结果
**关键发现：** (verified) 旧跟随实验只对地图点击目标做 tick 心跳，手动角色没有被作为实时目标；窗口放大后截图 QLabel 不重新缩放原图，`ScalableMapWidget.overlay_label` 的几何也不随内部 image label resize，导致底图与标记分离。新运行器 API 仅接受带真实采集时间和实例身份的 `PositionSample`；页面只给程序角色绑定/应用输出，并由 12/20 native 距离滞回控制停走。
**修订的旧结论：** “已有跟随实验可以直接拿来追角色”不成立；点击目标的伪心跳不能代表新视觉帧，且旧的输出遍历会把手动角色送入只有程序角色绑定的 `ProgramFollowOutput`。现已按目标来源分开，旧点击模式未改变目标刷新契约。
**连带重读文件：** `multiplayer_follow/models.py` 的 `PositionSample/FollowObservation`、`program_output.py` 的 arm/apply/release、`capture_test_page.py` 的双人帧消费与恢复、`capture_monitor_window.py` 的同帧预览、`scalable_map.py` 的 overlay/点击变换及相关 Qt 测试。
**CODEBASE.md 更新内容：** §2 新增 `aspect_preview.py` 职责；§4 补充两个实验窗口与通用预览/地图控件尺寸契约；§6 新增实时角色跟随五跳流转；§9 标出实机身份/控制器映射的剩余风险。PoE2 当前断点写明操作顺序、参数与未实机验收边界。
**覆盖进度更新：** 直接变更 4 个现有源文件、新增 1 个通用 widget、更新 4 个相关测试文件；重读目标样本、运行器到达门、页面输出/恢复及 Qt resize 路径。既有其他文件覆盖状态不变。
**验证：** 假手柄/页面/控件/回放聚焦测试 `129 passed`，PoE2 专项 `371 passed`，`compileall` 与 `git diff --check` 通过。未发送真实手柄、键盘、鼠标或网络输入。下一步由用户在游戏内分别实测两个跟随方向，记录新鲜目标、实际位移和 Host lease 后再判断实机效果。
## [SYNC] 2026-10-03 — 实验控制模式互斥

### A. SYNC 范围声明
**触发任务：** 实时跟随、半径 3 和可拖拽预览完成后的独立审查修复。
**直接变更文件：** `capture_test_page.py`、`test_poe2_capture_test_page.py`。
**预计连带影响：** 定点移动探针与实时跟随的启动/停止调用链、程序手柄输出所有权，以及实验页点击目标流程。

### C. SYNC 结果
**关键发现：** (verified) 两个实验原来可分别进入待点击或运行态，同一地图点击由 live follow 优先拦截，定点探针可能一直待命；两个输出还可能同时持有同一控制器。现于有效参数校验后、创建新输出前，调用另一实验已有的 stop 路径，实现双向互斥。
**修订的旧结论：** 单独验证实时跟随输出隔离不足以保证实验页手柄独占；必须把其它实验入口切换也纳入验收。
**连带重读文件：** `capture_test_page.py` 的 `start_program_move_probe()`、`stop_program_move_probe()`、`start_follow_experiment()`、`stop_follow_experiment()`、地图点击入口及相关 Qt 测试。
**CODEBASE.md 更新内容：** §6 实时角色跟随的启动跳增加定点探针停止/输出释放与反向切换说明。
**覆盖进度更新：** `capture_test_page.py` 的两个实验启动/停止链及 `test_poe2_capture_test_page.py` 的切换场景已重读；其余覆盖状态不变。
**验证：** 双向切换用例通过；PoE2 专项与采集页/窗口/地图控件合并回归 `436 passed`。独立审查未发现其它明确回归；仍无真实游戏输入。

## [SYNC] 2026-10-04 — 实验页 UI 优化与双人链路人工审查

### A. 本轮目标（阅读前声明）
**目标文件：** `capture_test_page.py`（主工作区/控制入口）、`capture_monitor_window.py`（截图窗口布局）、`aspect_preview.py`（预览缩放）。
**本轮想弄清楚：** 现有可拖动布局在不同窗口尺寸下是否仍有压缩、错位或操作入口混杂；确定最小 UI 改动范围。之后另开算法精读轮审查双人定位和跟随控制链。

### C. 本轮发现
**关键发现：** (verified) 原侧栏虽可拖动宽度，但采集、单人/双人定位、三种移动实验和日志串成单个长列表；停止程序移动的按钮可能随滚动离开视野。现改为三个可切换区域，固定停止按钮在标签页外；采集控制按地图/截图、单人定位、双人定位排序，地图与预览的既有 splitter 未改。
**修订的旧结论：** 可拖拽分隔条只能解决主画面尺寸，不能解决右栏操作查找和紧急停止可见性。
**覆盖进度更新：** `capture_test_page.py` 的 `_build_ui()`、`stop_all_program_motion()` 与切换测试已回读；`capture_monitor_window.py` 和 `aspect_preview.py` 保持原缩放契约，未改动。
**下一轮计划：** 单独精读双人视觉定位、跟随控制与输出释放链，检查实例、时间戳、身份和恢复状态是否一致。

### A2. 双人视觉定位链审查范围（阅读前声明）
**目标文件：** `experimental/multiplayer_localization/dual_first_frame.py`、`dual_motion.py`、`ui/modes/poe2_live_terrain/dual_motion_worker.py`。
**本轮想弄清楚：** 双人首帧身份锚定、帧时序、marker dropout、worker 取消及重定位触发是否能稳定传到页面。

### C2. 双人视觉定位链发现
**关键发现：** (verified) 首帧穷举两名 marker 与同实例内存锚点的有序配对，并对两点共用同一个旋转/镜像/比例变换；实时 tracker 按身份分别计数 marker dropout，超限才要求恢复；worker 在后台逐帧计算、UI 只提取最新结果，连续三次捕获异常才终止。
**风险：** (verified) `DualVisualTracker.tick()` 的首个 warmup 帧在墙体像素量级相似、但两名 marker 均未识别时仍返回 `tracking` 和首帧预测坐标；页面若把该帧当完全可信视觉目标，实时跟随可能短暂续期旧坐标。需审查页面消费门是否有额外可见性检查。
**下一轮计划：** 精读页面首帧/worker 结果/重定位回调，核实状态门、实例门和输出释放是否覆盖上述风险。

### A3. 页面双人链审查范围（阅读前声明）
**目标文件：** `ui/modes/poe2_live_terrain/capture_test_page.py` 中首帧、双人 worker 启停、帧消费与重定位方法。
**本轮想弄清楚：** worker generation、捕获时间戳、地图实例、角色可见性如何成为页面可信状态，跟随/双人定点输出何时被停止。

### C3. 页面双人链发现
**关键发现：** (verified) 页面在 stop/recovery 时先停止三种程序输出，再等待并保留旧 worker 引用；异步结果按 generation 过滤，恢复时重新读取同实例人物锚点。worker 新结果带采集时间进入 `_latest_dual_captured_at_ms`，跟随 timer 再消费。
**风险：** (verified) `stop_dual_motion()` 清除 `_latest_dual_state` 却未清除 `_latest_dual_captured_at_ms`；`_start_dual_motion()` 在启动 worker 前立刻发布首帧 `tracking` 状态并启用跟随按钮，但没有把时间戳同步为该首帧时间。快速重启并复用旧首帧时，旧状态与上一轮近期时间戳有短暂错配机会。需核查跟随启动门和真实输出时机。
**下一轮计划：** 精读跟随目标、程序输出适配与失效/恢复分支，判断上述两处状态窗口是否能实际发送输出，并检查其它断链。

### A4. 双人跟随控制链审查范围（阅读前声明）
**目标文件：** `capture_test_page.py` 的实时跟随启动/tick/恢复方法、`experimental/multiplayer_follow/runtime.py`、`program_output.py`。
**本轮想弄清楚：** 实际坐标样本何时被接受、手动角色是否绝不输出、过期/丢失/重定位是否能及时 neutral + release、目标跳变是否只追新位置。

### C4. 双人跟随控制链发现
**关键发现：** (verified) `set_target_sample()` 拒绝同时间/旧时间和跨实例目标；页面只为 `program_roles` 建手柄输出，手动角色仅提供 `PositionSample`。跟随 tick 在状态非 tracking、视觉超过 700ms、角色缺失或实例变化时释放/停止输出；恢复需新鲜双人帧。程序输出对 ARRIVED/WAITING/BLOCKED 等状态先发送中性帧，再释放 lease。
**问题 1：** (verified) warmup 双 marker 漏检仍可被 `start_follow_experiment()` 与 `_tick_follow_experiment_impl()` 当作 `tracking` 新视觉帧，程序角色可能在这单帧期间继续输出；消费侧没有检查 `visible_identities` 或 `warmup_assumed_stationary`。
**问题 2：** (verified) `single_p2_program` 启动条件总要求 P1 有效，但不要求 P2 有效；若 P1 有坐标、P2 未选择/缺失，构造 output 后 `players[p2_identity]` 可抛 `KeyError`，此处不在 output 构造的清理 try 内。此路径是旧实验模式，不属于新双人实时方向，但共享启动入口。
**问题 3：** (verified) 复用首帧与上一轮 `_latest_dual_captured_at_ms` 的短窗口可通过 live start 的 700ms 门；在新 worker 帧前可能用旧首帧位置作为本轮目标/跟随者观测。
**下一轮计划：** 检查双人同目标、程序移动探针与地图点击/输出互斥的最后一段，再完成 UI/相关链路回归与文档同步。

### A5. 双人目标与点击链审查范围（阅读前声明）
**目标文件：** `capture_test_page.py` 的 `start_dual_target_experiment()`、`_tick_dual_target_experiment_impl()`、`start_program_move_probe()`、`_on_follow_map_click()`。
**本轮想弄清楚：** 三类控制入口互斥是否完整；地图点击的显示/native 变换、双角色独立停止和失败释放是否有断点。

### C5. 双人目标与点击链发现
**关键发现：** (verified) 地图点击先逆变换到 native，再正向回投记录误差；双人同目标为两个角色分别规划、分别 arm/apply，位置/实例失效与输出异常会关闭会话。三种实验入口在启动前互斥；新增固定停止入口现在无条件清理所有运行态及待恢复上下文。
**剩余风险：** (verified) 双人同目标在 `degraded` 状态下仍按上次预测人物坐标 tick，缺失某个角色点时未立即 release 其输出，依赖该角色 700ms TTL 最终停止；单人移动探针也只检查角色点和帧龄，不检查 `state.status`。这允许短暂视觉不完整时继续控制，是有意的 dropout 宽限与输出保守性之间的取舍，尚未实机量化。
**修订的旧结论：** UI 停止按钮只释放当前活动输出还不够；恢复上下文也必须清空，避免用户停止后新帧使控制自动恢复。已通过无条件调用三个停止路径并补测试处理。
**下一轮计划：** 跑采集页/双人运行器/控件回归，核对 UI 在桌面尺寸的实际布局，并同步断点。

### C6. 验证与同步结果
**连带重读文件：** 双人首帧 `dual_first_frame.py`、逐帧 `dual_motion.py`、异步 `dual_motion_worker.py`、实验页首帧/恢复/跟随/双目标/点击入口、跟随 `runtime.py` 与 `program_output.py`。
**UI 结果：** 右栏三标签分区；固定停止按钮无条件清除三种实验的输出和恢复上下文；实时跟随半径只在两个 live 模式可编辑。Qt 离屏 1400×900 检查采集定位页与移动跟随页，预览、地图、侧栏无重叠；离屏中文字体缺失，不作为 Windows 文本渲染结论。
**CODEBASE.md 更新内容：** §6 更新页面 UI/输出停止链；§9 记录 marker warmup、旧帧时间、单人 P2 校验及 degraded 宽限风险。未修改双人定位/寻路/手柄控制算法。
**覆盖进度更新：** 上述 7 个核心文件由本轮方法级回读；新增 UI 停止与半径可用性测试。其它文件既有覆盖状态不变。
**验证：** PoE2 专项及采集页、监控窗口、地图控件、worker 相关回归 `443 passed`；`compileall`、`git diff --check` 通过。未发送真实游戏输入。审查指出的双人链风险仍需单独处理/实机量化，不视为本轮 UI 改动已修复。

## [SYNC] 2026-10-04 — 双人跟随审查问题修复

### A. 本轮范围（阅读前声明）
**目标文件：** `capture_test_page.py`、`dual_motion.py`、`test_poe2_capture_test_page.py`、`test_multiplayer_motion.py`。
**本轮想弄清楚：** 单人 P2 程序角色启动校验、双 marker 漏检 warmup 帧的程序输出门，以及停止/重启时首帧状态与采集时间戳的代际一致性。
**边界：** 不改已验收的双人定点移动规划策略，不发送真实游戏输入；用假输出和聚焦测试验证释放、拒绝及恢复时序。

### C. SYNC 结果
**关键发现：** (verified) 三条失败复现分别覆盖旧时间戳未清、单人 P2 缺失抛 `KeyError`、无 marker warmup 帧仍输出。现停止双人定位时同步清时间戳；tracker 保留墙体静止宽限但把无 marker 状态降级，页面启动/tick 再以 warmup 标记拒绝输出；跟随启动按实际 selected 身份校验，并把角色初始化纳入已创建输出的关闭边界。
**修订的旧结论：** 首帧配准成功可以立即展示地图，但不能仅凭复用首帧与旧时间戳允许本轮程序控制；墙层可用也不等于两个人物均有本帧视觉证据。
**连带重读文件：** `capture_test_page.py` 的双人停止/启动、worker 结果消费、跟随启动/tick；`dual_motion.py` 的 warmup、marker dropout；`program_output.py` 的 lease/关闭契约及相关测试。
**CODEBASE.md 更新内容：** §6 实时跟随链增加无 marker 降级与重启时间戳门；§9 三条已复现风险改为修复证据，保留 degraded 宽限待实机量化。
**覆盖进度更新：** 上述目标方法与假输出测试已回读；其它覆盖状态不变。
**验证：** 失败测试先得 `3 failed, 1 passed`，修复后双人/跟随聚焦 `131 passed`、PoE2 专项及相关页面/控件 `444 passed`；`compileall`、`git diff --check` 通过。没有向游戏发送真实输入，实机跟随仍待用户验收。

## [DIAG] 2026-10-04 — 双人标记与蓝色记录点重叠

### A. 本轮范围（阅读前声明）
**目标文件：** `experimental/multiplayer_localization/marker_candidates.py`、`dual_motion.py`、`capture_test_page.py` 相关消费链，以及本次 PoE2 实验日志。
**本轮想弄清楚：** 蓝色记录点与人物标记重叠时，候选检测、身份分配、视觉失效/恢复和跟随输出各层实际发生了什么；区分截图可见现象与日志可证明的故障。
**边界：** 本轮按用户要求先诊断和给出方案，不发送真实游戏输入，不在根因未确认前调整识别参数或算法。

### C. 诊断结果
**关键发现：** (verified) 2026-10-04 03:02:19 的日志中墙层质量约 `1.0`，`visible_identities` 仅有 P1，P2 连续漏检至 `marker_dropout_grace=2` 后进入 `markers_missing/recovery_required`；跟随侧输出 `live_role_follow.waiting`。截图显示蓝色人物与蓝色记录点重叠，但日志未记录原始局部截图、候选 bbox/HSV/面积，无法判定是蓝色轮廓合并、尺寸过滤还是错误候选抢占。
**独立缺口：** (verified) 当前 worker 用单槽 `_offer()` 覆盖旧结果，tracker 的 `recovery_requested=True` 仅在一个帧发出；页面只检查取到的最新帧的布尔值。实机会话 03:00:59 起持续记录 `recovery_required` 且 `recovery=False`，截至 03:06 无 `dual_motion.recovery`，`dropped_results` 在失效初期已达 287；这支持一次性恢复边沿丢失的机制，但原始丢失帧未保存，具体丢失时点仍为 (inferred)。之后也出现 `wall_and_local_match_failed`，不宜归因于蓝色标记单一原因。
**配置核对：** (verified) 本地 active profile 没有显式 `dual_marker_profiles`，加载时回落到预置黄色 HSV `5..38` 和蓝色 HSV `82..125`；蓝色范围是宽色相候选，当前检测只按颜色、面积 `8..55`、尺寸 `<=14` 筛选，再由 `_assign()` 按身份 hint 和预测距离分配，没有静态记录点判别。
**修订的旧结论：** “marker 超过 grace 就会自动重定位”只对 UI 收到那一帧成立；latest-only 结果槽可能让恢复请求没有交付。墙体质量高也不能证明人物身份可靠。
**覆盖进度更新：** `marker_candidates.py` 检测与候选筛选、`dual_motion.py` 身份 dropout/一次性恢复、`dual_motion_worker.py` 单槽发布、`capture_test_page.py` worker drain/跟随等待、`monitor_config.py` 默认 profile/加载路径已按相关方法回读；日志与截图只支持本轮结论范围。
**CODEBASE.md 更新内容：** §9 记录恢复事件丢失风险与同色静态地标的身份歧义风险；§6 双人 worker 链标记状态事件不能仅以可覆盖帧承载。
**下一轮计划：** 先加可复现的丢帧恢复请求测试并使恢复 revision 持久交付；再采集重叠前/中/后连续原始局部帧和候选诊断，验证蓝色轮廓失效机制，最后独立评估动态/静态候选消歧。不改墙体 mask。
## [SYNC] 2026-10-04 — 双人标记失明与恢复请求交付

### A. SYNC 范围声明
**触发任务：** 实现已批准的角色无关、短时观测丢失恢复；修复 latest-only 后台帧覆盖一次性重定位请求。
**直接变更文件（预计）：** 双人视觉 tracker、双人帧 worker、PoE2 实验页跟随组合、通用位置不确定性模块及其聚焦测试；另存设计与实施计划、更新 PoE2 断点。
**预计连带影响：** 双人首帧/实时定位的状态契约、跟随运行器的目标样本与输出释放、页面重定位触发、候选识别与诊断证据、CODEBASE 中定位及跟随 Flow。
**本轮想弄清楚：** 标记短暂丢失时各角色位置如何传到跟随输出；一次性 recovery 请求在哪一跳丢失；墙层与人物观测的置信边界如何分离。

### C. SYNC 结果
**连带重读文件：** `bounded_observation.py`、`dual_motion.py`、`dual_motion_worker.py`、`capture_test_page.py`、`multiplayer_follow/runtime.py`、`occlusion_archive.py`、`marker_candidates.py`、`monitor_config.py` 及对应回归测试。
**关键发现：** (verified) 每个 identity 的可用时间和 native 误差预算独立计数；marker 重现需落在预测门内并连续确认。墙层可靠时页面仅按新鲜截图和角色预算短时继续，估计样本不用于速度或卡墙校准。worker 将一次性 recovery revision 独立于 latest-only 图像保存，页面消费后先释放输出再重新注册。状态转换时最多归档 6 组局部证据，双人墙层不作人物擦除。
**修订的旧结论：** “超过 2 帧 marker 丢失就恢复”已改为时间/误差预算耗尽后恢复；“latest-only 会吞恢复请求”已有独立 revision 回归覆盖，不再作为当前已知故障。
**剩余风险：** (partial) 蓝色人物与同色静态记录点的轮廓合并/候选抢占分支，现有截图和日志仍不足以判别；短时估计也不是新的视觉位置，移动目标长期遮挡必须停止并重锚。
**CODEBASE.md 更新内容：** §2、§4、§5、§6、§9 同步新模块、算法边界、恢复交付和剩余风险。
**覆盖进度更新：** 新通用状态与归档模块按完整函数体回读；双人 tracker、worker、页面消费和跟随运行器按变更路径回读，其他文件既有覆盖状态不变。
**验证：** PoE2 专项及采集页/worker/通用状态测试 `448 passed`；尚未做实机重叠场景验收，未发送真实输入。

## [DIAG/SYNC] 2026-10-04 — 移动跟随页签切换导致双人实时定位取消

### A. 本轮范围（阅读前声明）
**目标文件：** `capture_test_page.py` 的移动跟随页签构造、切换回调、双人定位启动/停止；`dual_motion_worker.py` 的停止与失败信号；本次 PoE2 页面日志。
**本轮想弄清楚：** 切换“移动跟随”页签本身是否触发定位停止，或仅使启动/worker 的异常在 UI 中表现为卡住后取消；区分 UI 阻塞、主动 stop、worker 异常和旧线程退场。
**边界：** 不发送真实游戏输入，不改已验收的单人中心定位或双人首帧算法。

## [SYNC] 2026-10-04 — 命令辅助定位与主动恢复

### A. SYNC 范围声明
**触发任务：** 用户批准双人实时跟随中 marker 丢失后的命令里程预测、视觉纠偏及主动恢复方案。
**直接变更文件（预计）：** PoE2 实验跟随的独立角色估计器、程序输出回执、跟随运行器估计来源门、采集页组合与聚焦测试；设计和实施计划另存于 `docs/plans/`。
**预计连带影响：** `PositionStateEstimator`、视觉双人 tracker 状态、Host 输出 TTL、目标样本来源、撞墙/到达判定、现有重定位恢复链与 CODEBASE 跟随 Flow。
**本轮想弄清楚：** 有效控制输入的真实时间区间如何传入逐角色估计；延迟视觉帧如何纠偏；预测位置怎样参与规划而不污染实测反馈。
**边界：** 不修改单人中心定位与双人首帧配准，不自动发送真实输入；保留现有用户改动。

### C. SYNC 结果
**连带重读文件：** `program_output.py`、`command_role_tracker.py`、`state_estimator.py`、`bounded_observation.py`、`similarity_search.py`、`dual_motion.py`、`dual_motion_worker.py`、`capture_test_page.py`、`multiplayer_follow/runtime.py`、`reacquisition.py` 及各自聚焦测试。
**关键发现：** (verified) 原始方案只在页面侧预测；上游 `DualVisualTracker.tick()` 仍会在旧 2 秒预算耗尽后发出 `recovery_required`，且图标重现只围绕旧屏幕点分配。现在 PoE2 实验跟随把逐角色短时 native 预测与误差经 generation 受控的最新值邮箱交给 worker；tracker 用首帧同一旋转/镜像/比例的逆变换回投到屏幕，仅在 700ms 新鲜且误差不超过 12 native 格时参与分配/续存。重现候选即使旧预算过期也须在预测门内连续确认；无提示的正式双人定位沿用旧超时恢复。预测不刷新视觉时钟，不用于速度、接触或到达确认。停止跟随清空邮箱。
**修订的旧结论：** “页面命令预测足以跨过旧图标预算”不成立；必须把提示送到上游视觉分配与预算门。修复后相关测试通过，但真实 PoE2 角色遮挡的视觉身份仍未验收。
**剩余风险：** (partial) 同色静态记录点与人物长期重叠、手动领队静止不动时，有限连续帧和颜色/位置门不能从信息论上保证身份唯一；应查看 `occlusion_diagnostics` 的原图/候选轨迹，必要时低频重锚。高速度或错误速度增益可能使预测门拒绝真实重现，当前以误差上界和原有重锚 fail closed。
**CODEBASE.md 更新内容：** 双人 tracker、worker、通用观测、命令估计与页面 Flow 的职责和算法；新增遮挡身份风险。
**覆盖进度更新：** 本轮改动方法和调用上下游按截图→候选→worker→tracker→跟随估计→路线→输出回执→重锚链路回读；其他既有覆盖状态不变。
**验证：** PoE2 专项及相关页面、worker、通用观测和手柄假输出 `478 passed`；`compileall`、`git diff --check` 通过。没有发真实输入，实机遮挡与跟随稳定性待用户测试。

## [DIAG/FIX] 2026-10-04 — 实时跟随启动后卡住与重复重锚

### A. 根因调查
**用户现象：** 点击实时跟随后程序很卡、角色几乎不动，随后页面像崩溃一样反复停顿。
**日志证据：** `data/logs/poe2_live_terrain.log` 最新实机链路中，跟随启动后先产生一次 `command_duration_ms=160` 的 `program_ready` 输出；约 0.15–0.23 秒后同一角色视觉点仍是启动前位置，连续两次记录 `live_role_follow.visual_rejected ... reason=observation_rejected`，随后立即 `live_role_follow.reanchor reason=repeated_visual_innovation_rejected`。一次恢复从 `11:32:41.721` 到 `11:32:54.643` 约 13 秒，包含内存读取、3 次截图和 3 次几何注册；该过程释放手柄并重启 worker，形成“输出一次→拒绝两次→长恢复”的循环。日志没有证明 Host 写入失败；相反，`command_duration_ms=160` 和 `program_ready` 证明规划与输出链已到达写入边界。
**根因：** `CommandRoleTracker.observe()` 在调用方未提供视觉协方差时使用 `1 native²`；`PositionStateEstimator` 的预测协方差只有约 3–4，而游戏截图、Host 回执和游戏实际移动并不同步，启动延迟导致约 10 native 格创新被错误门拒绝。页面将两次这种正常启动延迟误判为身份/几何失配，触发昂贵的一次性重锚。

### C. 修复与验证
- 默认视觉测量协方差改为与现有状态估计器一致的 `9 native²`；调用方显式传入的小协方差仍保持严格 Mahalanobis 门，远距离异常跳变继续拒绝。
- 页面拒绝日志增加 `predicted`、`innovation`、`uncertainty`，下次实机可区分启动延迟、真正跳变和定位漂移。
- 新增命令跟踪器回归：160ms 输出后的首帧旧位置必须接受为视觉纠偏；显式 500 格跳变仍拒绝。
- 新增页面链路回归：首帧命令延迟不得触发 `repeated_visual_innovation_rejected`；现有大跳变重锚用例保持通过。

**验证：** 相关 PoE2/采集页/跟随/worker/观测/手柄回归 `480 passed`；`compileall` 和 `git diff --check` 通过。没有发送真实输入。**待实机确认：** 同一地图启动 P1→P2 跟随，检查是否连续出现 `follow_experiment.motion` 和 Host 输出，而不是两次 `visual_rejected` 后 `reanchor`；若仍卡住，保留新增的 predicted/innovation 日志。
## [DIAG/REVIEW] 2026-10-04 — 双人实时跟随执行链人工审查（恢复/输出/线程）

### A. 本轮目标（阅读前声明）
**目标文件：**
- `src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py`（原因：审查双人实时定位、跟随 tick、重定位恢复、停止和迟到回调的完整状态链）
- `src/auto_modules/ui/modes/poe2_live_terrain/dual_motion_worker.py`（原因：审查 latest-only 结果槽、recovery revision、线程异常和结束时序）
- `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_follow/command_role_tracker.py`（原因：审查输出里程预测与视觉纠偏门）
- `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_follow/runtime.py`（原因：审查跟随状态、到达/阻塞/重定位和局部接触证据）
- `src/auto_modules/adapters/virtual_gamepad/program_output.py`（原因：审查 Host lease、同步写入、诊断和释放边界）

**本轮想弄清楚：** 用户反馈跟随实验容易卡住、停止或崩溃时，是否还有状态重入、恢复循环、旧帧污染、同步阻塞和资源释放缺口；只做人工链路审查，不修改定位/导航/手柄参数，不发送真实输入。

### C. 本轮发现
**关键发现：**

1. **(verified) 恢复后的首帧相位门仍可能把正常启动延迟判成异常并再次重锚。** `CommandRoleTracker.observe()` 默认协方差虽已从 `1` 放宽到 `9 native²`，但实机日志 2026-10-04 11:32:41.721–11:32:54.643 显示：恢复注册成功后首个 `160ms` 程序脉冲发出，约 0.15–0.23 秒内角色视觉仍处旧点，连续两次 `visual_rejected`，随后 `reanchor(repeated_visual_innovation_rejected)`，一次恢复约 13 秒。根因不是 Host 写失败，而是恢复/启动阶段没有显式的输出—视觉相位宽限；9 的测量协方差仍不足以覆盖 80 native/s × 160ms 的相位差。
2. **(verified) 首帧/恢复注册仍同步执行在 Qt GUI 线程。** `_start_dual_motion(recovery=True)` 直接调用 `run_dual_first_frame_experiment(..., force_memory_read=True)`；日志同一恢复耗时约 13 秒，期间 GUI 定时器和停止操作无法及时响应。`stop_dual_motion()` 在 worker 未及时退出时还会 `wait(3000)` 同步阻塞 GUI。两者叠加可表现为“卡住”，但不等同于 worker 崩溃。
3. **(verified) 恢复首帧被拒绝时，双人跟随恢复上下文没有在同一出口清除。** `_start_dual_motion()` 在 `result is None/not accepted` 的 recovery 分支只调用 `_clear_program_probe_recovery()`，没有清除 `_dual_recovery_follow_*`。同一地图随后手动启动双人实时定位时，`_maybe_resume_dual_follow_after_relocalization()` 仍可能消费旧 context 并自动重建上一轮跟随，形成意外续跑/状态穿越风险。
4. **(verified) `start_follow_experiment()` 本身不是幂等入口。** 函数开头停止的是双人同目标实验，不会先停止已有实时跟随 runtime/timer/output。正常 UI 按钮禁用掩盖了这个问题，但恢复回调、快速双击或外部调用可覆盖 `_follow_runtime` 和 `_follow_program_output`，旧 lease/定时器只能依赖后续异常路径清理。
5. **(partial) Host 边界仍是 GUI 同步调用。** 每个控制 tick 的 `ProgramGamepadOutput.write()` 同步执行 `client.request("program.state")`；每 10 tick 的 `diagnostics()` 还同步请求 `client.status()` 与 `client.state()`。代码没有超时/耗时门，实机日志现有字段也没有拆出 request duration，因此不能断言是当前卡顿根因，但这是独立的事件循环阻塞风险。
6. **(verified) latest-only worker 与 revision 交付、generation/session token、停止释放的基本顺序是正确的。** 旧 worker 迟到结果会被 generation 丢弃；recovery revision 独立槽不会因图像覆盖丢失；停止会释放程序输出并等待/退休 worker。当前未发现“旧 worker 直接写入新 tracker”或“正常停止后自动重启”的确定性路径。

**修订的旧结论：** 之前把“默认视觉协方差放宽到 9”视为足以消除启动卡顿；本轮实机日志证明它只能降低一部分拒绝概率，不能替代启动/恢复相位宽限。之前把“recovery 失败会安全停止”视为完整收束；实际只清了 program probe context，follow context 仍可能残留。

**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `capture_test_page.py` | 深度完整 | 深度完整 | 2 | 逐段核对启动、worker drain、follow tick、reanchor、stop、恢复 context 和异常出口；确认相位门、GUI 同步注册、context 残留及非幂等入口 |
| `dual_motion_worker.py` | 深度完整 | 深度完整 | 2 | 核对单槽结果、recovery revision、连续失败、stop/wait、finished 信号和 generation 过滤；未发现确定性迟到回调写入新会话 |
| `command_role_tracker.py` | 深度完整 | 深度完整 | 2 | 核对输出 TTL 重放、默认协方差、Mahalanobis 门和视觉拒绝路径；确认 9 仍不足以覆盖启动相位差 |
| `multiplayer_follow/runtime.py` | 深度完整 | 深度完整 | 2 | 核对 freshness、prediction、arrival、contact/stall/relocalization 和 zero-vector 分支；未发现本轮新增确定性状态死循环 |
| `adapters/virtual_gamepad/program_output.py` | 深度完整 | 深度完整 | 2 | 核对 acquire/state/release、TTL 和 diagnostics；确认 Host 请求同步且缺少时延观测 |

**CODEBASE.md 更新内容：** §9 增加启动/恢复相位门、恢复 context 残留、非幂等启动和 GUI/Host 同步阻塞风险；保留已验证的 worker 代际与 revision 交付结论。

**下一轮计划：** 先为“恢复后首个视觉旧点”建立失败回归，再设计只在启动/恢复 episode 生效的相位宽限；随后清除 recovery 失败的全部 follow context，并让 `start_follow_experiment()` 显式幂等。最后独立测量 Host `program.state/status/state` 请求耗时，再决定是否异步化，避免把性能改动与定位参数混在一起。

## [SYNC] 2026-10-04 — 修复双人实时跟随执行链状态冲突

### A. SYNC 范围声明
**触发任务：** 根据人工审查修复启动/恢复相位误判、恢复失败状态残留、跟随重复启动和 Host 边界缺少耗时诊断。
**直接变更文件：**
- `src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py`
- `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_follow/command_role_tracker.py`
- `src/auto_modules/adapters/virtual_gamepad/program_output.py`
- 相关跟随/页面/适配器测试文件
**预计连带影响：** 双人实时定位 worker 交付、重定位恢复上下文、跟随 runtime 生命周期、Host lease/TTL 输出和页面停止链路。

### C. 本轮发现
**关键发现：**
- `(verified)` `CommandRoleTracker.observe()` 的默认视觉协方差只能覆盖稳定态的小误差；启动/恢复的输出—截图相位差需要一个按角色、按 episode 计时的有限宽限，而不能全局放宽跳变门。
- `(verified)` 页面启动跟随前没有释放旧 follow runtime/output；恢复失败出口只清理 program-probe context，双人跟随和双人同目标 context 可残留。
- `(verified)` Host `program.state`、`status`、`state` 调用都是同步边界；本轮先加入请求耗时和失败日志，保留当前 lease/TTL 顺序，不在没有实测耗时前贸然异步化。

**本轮实现：**
- `CommandRoleTracker` 增加 `arm_visual_phase()` / `visual_phase_active()`，仅在有限启动/恢复窗口使用较宽观测方差，窗口结束后恢复正常门限。
- `Poe2CaptureTestPage` 在 live follow 建立时为每个角色装载相位窗口；恢复失败原子清理 program-probe、follow、dual-target 三类 context；`start_follow_experiment()` 变为幂等入口。
- `ProgramGamepadOutput` 记录 Host 请求时延、诊断总时延，并对异常/慢请求输出日志。

**验证：** 聚焦跟随、命令跟踪器、手柄适配器测试 `81 passed`。尚未发送真实输入；仍需补充新行为回归和完整 PoE2 聚焦回归。

**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_follow/command_role_tracker.py` | 深度完整 | 深度完整 | 3 | 增加按角色相位宽限和过期恢复正常观测门，保持显式协方差调用不受影响 |
| `src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py` | 深度完整 | 深度完整 | 3 | 增加恢复上下文原子清理、跟随入口幂等和启动/恢复相位装载 |
| `src/auto_modules/adapters/virtual_gamepad/program_output.py` | 深度完整 | 深度完整 | 3 | 记录 program.state/diagnostics Host 边界耗时与失败日志，不改变控制协议 |

**修订的旧结论：** “把视觉协方差调到 9 就足够”修订为“稳定态仍用 9；启动/恢复必须使用有时限的 episode 宽限”。

**下一轮计划：** 增加相位窗口过期后仍拒绝跳变、恢复失败清理、重复启动释放旧输出、Host 时延字段的回归测试；随后更新 `CODEBASE.md` 受影响章节并运行完整相关测试。

### C. SYNC 结果
**连带重读文件：** `command_role_tracker.py`、`capture_test_page.py`、`program_output.py`、对应 tracker/page/adapter 测试，以及 `CODEBASE.md`、`docs/POE2_LIVE_TERRAIN_CURRENT_STATE.md`。
**CODEBASE.md 更新内容：** 更新命令—视觉相位窗口算法、Host 请求耗时诊断、跟随页面生命周期步骤和风险登记；首帧/恢复仍在 GUI 线程的剩余风险明确保留。
**覆盖进度更新：** 三个直接变更源文件维持“深度完整”，新增回归测试已阅读并纳入覆盖；文档风险条目从“待修复”改为“实验已修复/部分修复/待实机确认”。
**新增 Finding：** `stop_dual_motion()` 的长时间同步 join 已去除，但首帧/恢复注册的同步 GUI 风险仍独立存在；Host 协议目前只增加可观测性，没有未经实测的异步改造。
**验证结果：** `tests/poe2_live_terrain tests/test_poe2_capture_test_page.py tests/test_program_gamepad.py` 共 `468 passed`；本轮聚焦双人/跟随/手柄 `88 passed`；`compileall` 与 `git diff --check` 通过；未发送真实输入或网络同步。

## [SYNC] 2026-10-04 — 跟随启动日志补充

### A. SYNC 范围声明
**触发任务：** 将相位宽限参数写入跟随启动日志，便于实机确认实际 episode 配置。
**直接变更文件：** `src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py`。
**预计连带影响：** 仅 `follow_experiment.armed` 日志字段；不改变运行时状态、定位阈值或输入。

### C. SYNC 结果
**连带重读文件：** `capture_test_page.py` 跟随启动日志调用点。
**CODEBASE.md 更新内容：** 无算法/契约变化，仅新增日志字段，无需更新结构章节。
**新增 Finding：** 实机可直接核对 `visual_phase_grace_ms=750` 是否在 live follow 启动时生效。
**验证结果：** 前一轮 `468 passed`、聚焦 `88 passed`、`compileall` 和 `git diff --check` 已覆盖同一逻辑；本次仅日志格式改动，未发送真实输入。

## [SYNC] 2026-10-04 — 新增只读实机跟随链探针

### A. SYNC 范围声明
**触发任务：** 用户要求在已打开的 PoE2 进程上实验上一轮跟随逻辑与性能，但本轮禁止发送真实输入。
**直接变更文件：** `tools/debug/poe2_follow_readonly_probe.py`、`docs/POE2_LIVE_TERRAIN_CURRENT_STATE.md`。
**预计连带影响：** 只新增调试 CLI 和断点记录；复用双人 localization composition、monitor profile、terrain conversion 与只读内存 adapter，不改变正式页面、跟随 runtime 或输入适配器。

### C. SYNC 结果
**连带重读文件：** `tools/debug/poe2_follow_readonly_probe.py`、`src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_localization/composition.py`、`product_session.py`、`memory_anchors.py`、`src/auto_modules/features/poe2/live_terrain/native_grid.py`、`monitor_config.py`、断点文档。
**CODEBASE.md 更新内容：** 新增调试脚本职责、只读边界、输出契约和权限风险条目；保持正式业务链无变化。
**新增 Finding：** 普通 Python 能发现当前 `PathOfExile.exe`（PID 33984），但 `ProcessReader` 的 `PROCESS_VM_READ|PROCESS_QUERY_INFORMATION` 打开句柄返回 `PermissionError: [WinError 5]`；不能把缺少权限误判为首帧或视觉算法失败。管理员 UAC 未确认时不自动重试。
**验证结果：** 探针 `py_compile` 通过；普通权限实跑生成 `report.json` 且 `input_calls=0`，真实帧数为 0 并记录权限错误；未发送任何输入或网络同步。

## [SYNC] 2026-10-04 — 探针静态诊断收口

### A. SYNC 范围声明
**触发任务：** 消除新增只读探针的无用依赖和可修复的 Serena 类型诊断。
**直接变更文件：** `tools/debug/poe2_follow_readonly_probe.py`。
**预计连带影响：** 仅探针序列化 helper；不改变进程读取、截图顺序、帧上限或输入安全边界。

### C. SYNC 结果
**连带重读文件：** 新探针完整文件。
**CODEBASE.md 更新内容：** 无行为契约变化，既有模块条目继续适用。
**新增 Finding：** Serena 仍提示其分析环境缺少 `cv2`/`numpy` 类型包，但运行时 `.venv` 可导入；`dataclasses.asdict()` 的泛型诊断已用局部类型注释消除，无需改变序列化逻辑。
**验证结果：** `py_compile`、`git diff --check` 通过；普通权限实跑报告仍明确 `input_calls=0`、`frames=[]`、WinError 5。
## [SYNC] 2026-10-04 — 修复异步首帧 accepted 被误判为 rejected

### A. SYNC 范围声明
**触发任务：** 实机点击开始跟随后立即结束；日志显示双人恢复 worker 已 `status=accepted`，页面随后仍走 `first_frame_rejected`。
**直接变更文件：**
- `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_follow/command_role_tracker.py`
- `src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py`
- `tests/poe2_live_terrain/test_command_role_tracker.py`
- `tests/test_poe2_capture_test_page.py`
**预计连带影响：** 双人首帧异步结果消费、恢复重启、跟随恢复上下文、双人 motion worker 生命周期；不改变识别阈值、地图匹配或真实输入协议。

### C. 本轮发现
**关键发现：** `(verified)` `_on_dual_first_frame_worker_result()` 在 worker 返回 accepted 后调用 `_start_dual_motion(recovery=True, first_frame_ready=True)`；原实现仍执行 `result = None if recovery else self._last_dual_first_frame_result`。由于 `first_frame_ready=True` 会跳过重新计算，后续校验看到 `result is None`，于是错误记录 `program_probe.relocalization_failed` 并清理恢复上下文。实机日志 16:32:27.794–16:32:27.797 已直接证明 accepted→rejected 矛盾。

**修复：** `first_frame_ready` 现在消费 `_apply_dual_first_frame_bundle()` 写入的 accepted 缓存结果；恢复模式只有在未交付首帧时才强制重新计算。新增 `dual_motion.first_frame_context`、worker `accepted/recovery` 字段和 `follow_experiment.stopped` 生命周期日志，明确记录状态交接与停止时是否持有 timer/output。

**回归测试：** 新增 `test_dual_motion_recovery_consumes_accepted_async_first_frame`，覆盖 accepted 异步结果直接重启 tracker/timer，且不出现“首帧配准未通过”。三个聚焦测试通过；PoE2 双人定位/跟随/手柄整组 `473 passed`，编译和差异检查通过。

**修订的旧结论：** 原先把本次快速结束归因为“重定位失败/参数不稳定”是不准确的；当前已确认首帧注册实际成功，故障在页面恢复结果消费的状态契约错位。

**人工链路审查：** 启动跟随允许旧帧进入等待，不会直接释放；首次输出后的静态视觉帧累计三次创新拒绝才触发一次后台重锚；重锚 worker 读取内存、截图和配准成功后必须回到 tracker 初始化，而不是清理上下文。当前日志没有 Host 输出异常或 Qt 主线程同步重定位证据。

**下一轮计划：** 用当前修复重启程序实测同一地图实例；核对 `dual_first_frame.worker_result status=accepted` 后必须出现 `dual_motion.first_frame_context ... first_frame_ready=True`、`dual_motion.started recovery=True` 和新的 `dual_motion.tick`，不应再出现同一 generation 的 `first_frame_rejected`。若仍停止，再根据新日志区分 Host 输出异常、地图上下文变化和后续视觉失配。

## [AUDIT] 2026-10-04 — 双人跟随完整链路人工推导

### A. 审查范围声明
**目标：** 在不发送真实输入、不改算法的前提下，人工模拟双人首帧、motion worker、跟随启动、首次输出、视觉拒绝、恢复、重建、恢复跟随和停止链路，寻找状态缠绕、矛盾门限和性能瓶颈。
**覆盖文件：** `capture_test_page.py`、`dual_motion_worker.py`、`command_role_tracker.py`、`multiplayer_follow/runtime.py`、`multiplayer_follow/program_output.py`、`adapters/virtual_gamepad/program_output.py`、`ui/widgets/scalable_map.py`。

### C. 审查结果
**已确认正常：** generation/latest-only/recovery revision 的旧 worker 隔离、程序角色独立 lease、750ms 启动视觉宽限、accepted async 首帧消费、停止时输出释放和 deferred restart 栅栏均有明确路径。

**新增 Finding：**
- `(verified)` `_maybe_resume_dual_follow_after_relocalization()` 的 live 帧龄门为 700ms，而 `start_follow_experiment()` 的 live 启动门为 300ms；301–700ms 会被误记 runtime rebuild failure 并丢 recovery context。
- `(verified)` `_request_live_follow_reanchor()` 不经过 `_dual_last_recovery_at_ms` 的 10 秒 cooldown；跟随侧四类异常可以独立触发重复内存读取/后台注册。
- `(verified)` worker 采用“处理完成后再等待”的固定 cadence；已有实机单帧约 48ms、配置 30FPS，实际吞吐低于目标并产生 dropped results，可能制造 stale frame。
- `(verified)` `Poe2DualFirstFrameWorker` 结果信号后 cleanup 异常仍可发 failed，页面 failed slot 未验证当前 worker 是否已交付 accepted 结果；存在终态竞态。
- `(verified)` worker 丢弃 `processed`，页面预览再次执行 preprocess；Host write/diagnostics 同步发生在 Qt follow timer。

**修订的旧结论：** “accepted 误判修复后链路即可稳定”不成立；直接停止根因已修复，但恢复门限、reanchor 冷却和实际处理吞吐仍可能独立导致恢复丢失、重定位风暴和卡顿。

**本轮没有修改代码，也没有发送真实输入。** Findings 已写入 `docs/POE2_LIVE_TERRAIN_CURRENT_STATE.md` 的“双人跟随链路人工审查”断点，下一轮应先补状态回归和耗时观测，再实施 P1 修复。
## [SYNC] 2026-10-04 — 双人跟随链路逐步修复

### A. SYNC 范围声明
**触发任务：** 修复双人实时跟随的过期帧空转、首帧 worker 终态竞态、连续帧重复预处理、重复 overlay/UI 调度和 Host 诊断阻塞。
**直接变更文件：**
- `src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py`
- `src/auto_modules/ui/modes/poe2_live_terrain/dual_motion_worker.py`
- `tests/test_poe2_capture_test_page.py`
- `tests/test_poe2_dual_motion_worker.py`
- `docs/POE2_LIVE_TERRAIN_CURRENT_STATE.md`
**预计连带影响：** 双人 worker 结果契约、首帧 recovery 回调、跟随/双人同目标页面 timer、地图 overlay 渲染、预览处理和虚拟手柄诊断调用；不改变定位算法、路径规划算法或实际输出协议。

### C. SYNC 结果

**关键发现（verified）：**

- `_tick_follow_experiment_impl()` 的过期帧路径原先每个 100ms tick 都执行释放和 warning；现在有 `_follow_stale_since_ms`、单次释放和单次 `visual_frame_stalled` recovery 边沿。
- `Poe2DualFirstFrameWorker._run()` 原先 accepted 结果交付后 cleanup 异常仍可能发 `failed`；现在由 `result_delivered` 锁定一次性终态，页面也忽略已摘除 worker 的迟到失败。
- `DualMotionFrameResult` 现在保留 worker 已生成的 `processed`，Qt drain 不再重复 preprocess；follow/dual-target overlay 每个视觉结果只走一个 renderer。
- 连续 worker 的 Qt drain 为 33ms；控制输出节拍未改。跟随/双人同目标 Host diagnostics 最少 5 秒一次，首次 tick 仍取样；`write()` 仍同步，等待后续实机 `host_request_ms` 证据决定是否设计异步输出。

**修订的旧结论：** 原先把“processed 丢失、accepted cleanup 竞态、过期帧空转”登记为未修复风险；本轮已通过最小测试和代码链路核对解决，剩余风险只保留同步 Host write 与 native capture 不可强制中断两项。

**连带重读文件：**
- `src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py`：重读跟随启动/停止、worker drain、overlay、过期分支、diagnostics 调度和 recovery 回调。
- `src/auto_modules/ui/modes/poe2_live_terrain/dual_motion_worker.py`：重读 `DualMotionFrameResult`、`_capture_one()`、两个 worker 的 `_run()` 终态。
- `tests/test_poe2_capture_test_page.py`：重读 stale/recovery/overlay 相关回归。
- `tests/test_poe2_dual_motion_worker.py`：重读 worker latest-only、processed、cleanup failure 回归。

**CODEBASE.md 更新内容：** 更新 PoE2 页面、worker、测试模块说明；风险登记册标记 cleanup/processed/overlay/过期空转为 resolved，并保留 Host write/native capture 的精确风险。

**验证：**

```text
pytest -q tests/test_poe2_capture_test_page.py tests/test_poe2_dual_motion_worker.py \
  tests/poe2_live_terrain/test_closed_loop_controller.py \
  tests/poe2_live_terrain/test_multiplayer_follow_runtime.py \
  tests/poe2_live_terrain/test_command_role_tracker.py
159 passed in 39.22s
python -m compileall -q src/auto_modules       # passed
git diff --check                              # passed
```

没有发送真实手柄、键盘、鼠标或网络输入；没有修改定位匹配、方向/比例、路径规划或输入协议。
## [SYNC] 2026-10-04 — 实时跟随冷启动回归与双人同目标测试排查

### A. SYNC 范围声明
**触发任务：** 继续完成实时跟随冷启动修复，排查剩余回归失败并更新架构记录。
**直接变更文件：** `src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py`、`tests/test_poe2_capture_test_page.py`。
**预计连带影响：** 实时跟随启动/恢复状态机、双人同目标测试契约、PoE2 页面测试链路。

### C. 本轮根因调查结果（修复前）

- `(verified)` `test_switching_between_move_probe_and_follow_releases_previous_mode` 的断言仍假定实时跟随启动同一帧立即调用 `ProgramFollowOutput.start()`；新契约要求先进入 `cold_start` 并等待捕获时间严格递增的视觉帧，因此该断言与实现冲突。
- `(verified)` 两个双人同目标失败均发生在 `_tick_dual_target_experiment_impl()` 的实时帧 TTL 分支（700ms）之前；测试耗时导致 `_latest_dual_captured_at_ms` 过期，runtime.tick 尚未被调用，不能据此判断双人 runtime 的异常处理失效。
- `(verified)` stale-role 测试在过期帧分支提前清空 `_dual_target_observations`，不是 `SimulatedFollowRuntime` 丢失角色观察；测试需要刷新页面级捕获时间，同时保留 runtime 内 role-a 的过期 `PositionSample`，才能覆盖目标契约。

**单一假设：** 只修正测试前置时间/冷启动契约，不改变双人同目标生产代码；若三项失败消失，则根因是测试与时间状态机不同步。

### C. 本轮结果

- `(verified)` 已在切换测试中显式交付一帧 `captured_at_ms > baseline_captured_at_ms`，确认实时跟随冷启动阶段不会在同帧启动手柄，收到新帧后才进入输出路径。
- `(verified)` 双人同目标 runtime 异常测试在刷新页面级帧时间后命中 `runtime.tick` 的异常捕获，双方输出均释放；stale-role 测试在保持 role-a 运行时样本过期的前提下返回 `WAITING_POSITION`，role-b 继续运行。
- `(verified)` 双人同目标连续点击测试补充了第二次点击前的新鲜帧时间，避免 700ms 页面帧 TTL 造成与业务无关的时间竞态。
- **测试：** `pytest -q tests/test_poe2_capture_test_page.py` → `78 passed`；定向三项 → `3 passed`。

**修订的旧结论：** 旧记录把 3 个失败统称为“剩余代码问题”；现在确认 2 个是测试未刷新页面级帧时间，1 个是测试仍沿用旧的即时输出契约，生产代码无需为此放宽 TTL 或取消冷启动。

**CODEBASE.md 更新内容：** 更新 PoE2 页面测试契约和风险说明，记录实时跟随 `cold_start/recovery_sync/tracking` 的启动边界；双人同目标运行时代码标记为未改动。

**下一步：** 运行完整测试、编译检查与 diff 检查；随后更新 PoE2 当前状态断点文档并人工复核启动/恢复链路。

### C. 最终验证结果

- `(verified)` 相关闭环回归：`160 passed`（capture page、dual motion worker、closed-loop controller、multiplayer follow runtime、command role tracker）。
- `(verified)` `python -m compileall -q src` 通过；`git diff --check` 通过。
- `(environment)` 全量 `pytest -q` 为 `1050 passed, 2 skipped, 10 subtests passed, 1 failed`；唯一失败是 `tests/test_distribution.py::DistributionTests::test_dependency_selection_excludes_unrelated_editable_project`，运行环境缺少 `pydirectinput` distribution metadata（`PackageNotFoundError`），与本轮 PoE2 跟随改动无关。
- `(verified)` 已完成人工链路复核：同帧不输出 → 新鲜双人帧同步 → tracking 输出 → 稳态拒绝门 → recovery_sync；停止/异常路径仍幂等释放输入。

## [SYNC] 2026-10-05 — 跟随前台消费边界与预测到达回归

### A. SYNC 范围声明
**触发任务：** 排查“点击开始跟随后立即停止/反复重启”，验证 PoE2 不在前台时 Host 报告是否被游戏消费，并修复由此引出的预测漂移、同步 Host 日志异常和测试不稳定。
**直接变更文件：**
- `src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py`
- `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_follow/runtime.py`
- `src/auto_modules/adapters/virtual_gamepad/program_output.py`
- `tests/test_poe2_capture_test_page.py`
**预计连带影响：** 实时/点击跟随的前台门控、Program lease 生命周期、冷启动/恢复同步、预测到达状态和 Host 请求诊断；不改变双人首帧匹配、路径规划或输入轴变换协议。

### C. 本轮结果

**根因证据（verified）：**

- 实机日志 `data/logs/poe2_live_terrain.log` 在 `2026-10-04 23:51:51` 的 accepted 双人首帧之后记录了 `step=live_role_follow.waiting_game_foreground reason=poe2_not_foreground pid=33984 hwnd=134540`。这证明工作台按钮点击时 PoE2 不是前台窗口；Host 仍可能提交 ViGEm 报告，但不能证明游戏消费了输入。
- 同一类失败链路中，视觉角色保持原位置，`command_prediction` 持续推进，随后连续 `visual_rejected`、`repeated_visual_innovation_rejected` 和 recovery，造成按钮反复亮灭。该现象不是首帧匹配失败。

**代码修复（verified）：**

1. `Poe2CaptureTestPage._gate_live_follow_foreground()` 现在在实时跟随和点击目标跟随的所有程序输出前统一检查 PoE2 进程窗口和前台 PID；未在前台时只释放一次 lease、保持 worker/页面会话等待，不触发重定位；恢复前台后以最新完整帧重置视觉基线，再允许 arm/write。
2. `ProgramGamepadOutput.write()` 修正了日志变量先用后赋值的 `UnboundLocalError`，并保留 accepted axes/TTL/Host 请求耗时证据。
3. `SimulatedFollowRuntime._tick_follower()` 的预测接近目标分支改用 `ClosedLoopMotionController.constrained_duration_ms`（带兼容 fallback），不再访问不存在的 `command_duration_ms`；预测位置不能单独确认到达，仍发送有限靠近脉冲等待视觉确认。
4. 前台 gate 的重复 `release_all()` 改为边沿触发，降低 Qt timer/IPC/日志压力。

**回归验证（verified）：**

```text
pytest -q tests/test_program_gamepad.py → 7 passed
pytest -q tests/test_poe2_capture_test_page.py → 79 passed
pytest -q tests/poe2_live_terrain/test_multiplayer_follow_runtime.py \
  tests/poe2_live_terrain/test_command_role_tracker.py → 65 passed
```

新增页面回归覆盖：工作台前台时不 arm/不写入；重复 timer tick 不重复释放；PoE2 恢复前台且收到严格更新帧后才允许首个输出。测试通过显式 override 隔离宿主桌面前台状态，未发送真实输入。

**人工链路复核：**

```text
点击开始
→ 校验同实例/新鲜双人帧
→ 创建 runtime 和独立 program output
→ 前台 gate（失败：等待 PoE2，不重定位；成功：继续）
→ cold_start/recovery_sync 等待严格新帧
→ sync_ready 后 arm lease/write
→ Host accepted + axes/TTL 日志
→ 游戏实际消费（仍需实机前台测试证明）
→ 视觉更新/有限 command prediction
→ 视觉确认到达后停止；失配才进入一次性 recovery
```

**修订的旧结论：** 之前把“点击后立即停止”主要归因于预测位置提前到达；现在确认预测/视觉冲突是表现层原因，前台窗口未切换是导致游戏不消费输入的关键外部边界。两者必须同时处理，不能只调置信度或放宽重定位阈值。

**未完成验证：** 尚未在用户当前 PoE2 实机上验证“切回游戏后角色真实移动”；需要用户让 PoE2 保持前台后再测试，并核对 `foreground_resumed`、`program_output.acquired/accepted`、Host axes 和后续视觉位移四组日志。

## [SYNC] 2026-10-05 — 跟随启动 6 秒切窗缓冲

**需求：** 点击“开始跟随”后不要立即发送手柄，让用户有 6 秒切回 PoE2 窗口。

**根因边界：** 前台门只能判断 PoE2 当前是否可消费输入，不能代替启动后的人工切窗时间；地图点击回调曾直接调用 `ProgramFollowOutput.arm()`，会绕过任何统一等待。

**实现：** `Poe2CaptureTestPage` 在成功建立跟随会话时记录 `not_before_ms`。统一跟随 tick 在前台门之后、runtime/输出之前阻断 arm/write；每秒记录剩余时间，延迟结束后才进入原有同步、规划和输出链路。`_on_follow_map_click()` 只设置目标、启动 timer，不再直接 arm。停止、初始化和清图清理延迟字段；测试可用 `_follow_command_arm_delay_ms=0` 保持离线即时契约。

**验证：** 页面回归 80 passed；`test_program_gamepad.py`、双人 runtime/tracker 相关回归合计 72 passed；compileall、diff check 通过。新增测试验证“点击开始后和首次地图点击期间输出为空，延迟到期才 start/write”。未发送真实游戏输入。

**用户测试步骤：** 完成定位后点“开始跟随”，6 秒内切回 PoE2 并保持前台。看到 `step=follow_experiment.command_delay_elapsed` 后才会申请 Host lease；随后核对 `program_output.accepted` 和角色视觉位移。

## [SYNC] 2026-10-05 — 手动领队跳变误判根因修复

**实机证据：** 最新一次跟随在 `command_delay_elapsed` 后立即记录
`visual_rejected role=<手动 P1> innovation=57.156`，紧接着
`reanchor reason=manual_target_unobserved` 和 `follow_experiment.stopped`。因此停止点是领队视觉创新门，不是 6 秒门，也不是 Host 初始化。

**修复：** 实时跟随循环对手动领队直接接受新视觉位置、刷新 tracker anchor 并更新 remote target；只有程序控制角色继续使用 command prediction 与 innovation rejection。新增大位移日志和 stop context 日志，能区分手动目标移动、程序角色拒绝、前台等待、异常和显式停止。

**验证：** 新增手动领队大位移回归；`tests/test_poe2_capture_test_page.py` → 81 passed。未发送真实输入。

## [AUDIT] 2026-10-05 — 从 10 月 4 日重叠反馈回溯跟随回归

### A. 回溯范围
对照 2026-10-04 03:04 前后的 `poe2_live_terrain.log`、断点记录和跟随调用链，重点比较
`DualVisualTracker`、`CommandRoleTracker`、`Poe2CaptureTestPage._tick_follow_experiment_impl()`
以及重锚入口。没有发送真实输入。

### C. 结论（verified）

- 03:04 前的可运行链路只让程序控制角色进入命令里程预测；手动 P1 的视觉位置直接作为跟随目标。
  蓝色人物/记录点重叠时会出现 marker dropout 和等待，但不会因为 P1 的位置变化触发创新拒绝。
- 为处理重叠后的“失明”问题，10 月 4 日后加入了逐角色 `CommandRoleTracker`、预测提示回投、视觉创新门和重复拒绝重锚。
  当时实现把 `(leader, follower)` 一起送进 `observe()`，把手动 P1 的真实位移误当成程序摇杆预测残差。
- 03:26 实机日志把回归完整复现：`command_delay_elapsed` 已出现，随后第一条失败是
  `visual_rejected role=P1 innovation=57.156`，下一条就是
  `reanchor reason=manual_target_unobserved` 和 `follow_experiment.stopped`。因此启动门、Host 连接和首帧定位不是这次停止原因。
- 之后的 6 秒切窗、Host 耗时记录和 worker 恢复逻辑会放大现象或延长恢复时间，但不是最初停止的触发点。

### D. 当前修复与防回归

实时跟随现在只对程序控制角色执行命令创新拒绝；手动领队可见帧直接更新目标并刷新 tracker anchor，
不进入连续拒绝计数和跟随重锚。新增 `manual_leader_visual_accept` / `manual_leader_visual_move` 日志，
并把回归测试的视觉相位宽限设为 0，确保测试覆盖稳定态而不是只覆盖启动宽限。

聚焦验证：`tests/test_poe2_capture_test_page.py -k "manual_leader or repeated_visual_innovation"` → 3 passed；
`compileall` 和 `git diff --check` 通过。下次实机重启后，开始跟随成功链应出现
`command_delay_elapsed` → `manual_leader_visual_accept` → `follow_experiment.motion`，
不应再出现同一代的 `visual_rejected role=P1`。

## 2026-10-05 — 跟随停止问题的逐阶段诊断补齐

- 读取最新 `poe2_live_terrain.log` 后确认最近完整失败：P1 手动领队已接受，P2 输出已被 Host 接收，P2 连续三次视觉创新拒绝后触发重定位；恢复阶段另有多 PoE2 进程导致前台探测无法恢复。
- 仅新增只读诊断：跟随 tick 上下文、视觉输入、tracker 锚点/命令区间/预测、runtime 决策、输出回执、低频 Host 探针、异常和停止上下文。
- 为防止诊断影响控制节拍，完整 tracker/路径快照每 5 tick 记录，其他 tick 使用轻量记录；不改算法和参数。
- 停止日志改为在清理前捕获状态，保留真实停止来源和最后状态。
- 验证：PoE2 页面 81 passed；tracker/gamepad 13 passed；compileall、diff check 通过；未发送真实输入。

## 2026-10-05 — 强制断点纪律与跟随诊断证据锚点

- 将“每个任务必须维护断点文档；每个根因、结论、验证和未闭合风险及时记录；上下文压缩后先读断点再继续”写入仓库 `AGENTS.md`，作为后续所有任务的执行规则。
- 固化日志策略：每 tick 轻量关键指标；完整 diagnostics 每 5 tick；异常、视觉拒绝、输出失败、状态转换、重定位和停止立即记录；Host status/state 低频探针，避免诊断改变控制节拍。
- 当前真实证据锚点仍是 `2026-10-05 13:26:13`：P1 手动领队已接受，P2 输出被 Host 接收后，三次视觉创新拒绝（14.353、14.297、14.517）触发重定位。`13:50`/`14:04` 的 `role-a/role-b`、`Area:hash`、`900.0` 为离线测试数据，不得混入实机根因判断。
- 未闭合假设保持不变：预测速度、轴/旋转映射、Host 实际消费、截图/模拟时序。没有新的同一 session 实机证据前，不调参数、不宣称修复。

## 2026-10-05 — 确认“移动后停止”的日志格式运行时错误

- 混合日志中 `13:41`、`13:43`、`13:46`、`13:48`、`13:50` 的离线页面场景（`role-a/role-b`、`Area:hash`）重复出现：
  `dual_motion.recovery_claimed` 后，
  `_request_live_follow_reanchor()` 的 warning 日志抛 `TypeError: not enough arguments for format string`，
  随即 `follow_experiment.tick_failed error=not enough arguments for format string`，统一异常边界以
  `tick_exception:TypeError` 停止跟随。
- 根因是 reanchor 日志格式串需要 9 个值，调用只传了 8 个，漏掉
  `self._follow_last_visual_positions`。这解释了此前“重定位一触发就停止”，不是新的速度、首帧或路径算法问题。
- 已补齐参数；新增回归测试确保日志格式化不会中止 recovery，并验证 recovery context 保存和重启仍会执行。
- 验证：reanchor 聚焦测试 `2 passed`；`python -m compileall -q src` 通过；`git diff --check` 通过。
- 这些记录不是新的实机证据，但暴露了真实页面代码的确定缺陷。下一步仍需用户复测一次真实跟随，
  用同一 `session_id` 确认不再出现该 TypeError；若仍停止，按新的第一条异常继续定位。
## [SYNC] 2026-10-05 — 双人实时跟随运行一段后停止

### A. 本轮目标（阅读前声明）
**目标文件：**
- `src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py`（跟随启动、tick、视觉拒绝、重定位与停止链路）
- `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_follow/command_role_tracker.py`（命令预测与视觉校准）
- `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_follow/program_output.py`（输出生命周期与手柄报告）
- `data/logs/poe2_live_terrain.log`（session_id=1a10ae45e2c-179a6c1f7a0 的实机证据）

**本轮想弄清楚：** 跟随运行一段后停止是否由速度模型、方向/坐标变换、输出脉冲时序或视觉重定位门控造成；必须先对齐每次输出、预测位移、视觉位移、拒绝计数、停止原因与恢复状态，再决定单点修复。

### C. 本轮发现（根因确认，代码修改前）

- (verified) session `1a10ae45e2c-179a6c1f7a0` 中 P2 输出被 Host 接收，`controller=2/acquired=True`，且视觉位置持续更新；不是按钮启动、Host 租约或截图完全停滞。
- (verified) P2 的观测速度约 `10.205 native/s`，但 `CommandRoleTracker` 用 runtime 固定 `expected_speed=80` 回放输出 TTL；观测方向与命令方向仍有 `0.852` alignment，说明是速度/局部消费差异叠加，而非完全反向。
- (verified) 三次视觉拒绝的创新距离接近 `18–20 native px`，其间点相对上一可信视觉点仍是连续小步；页面只按“预测点创新”计数，未使用视觉连续性证据，于是触发 recovery。
- (verified) recovery 首帧 accepted；之后 `poe2_not_foreground` 只是恢复后的前台门控，不能当作本次首个停止根因。
- **修订旧结论：** 之前把“提高视觉相位宽限或调低 expected_speed”作为主要方向；现在确认仅调参数不够，根因是 tracker 缺少安全的连续视觉重基线分支，必须先修正数据融合契约，再重新校准速度。

**下一步：** 先为 `CommandRoleTracker` 增加显式的连续视觉重基线 API 和单元测试；页面只在单帧位移/时间/身份连续性满足边界时调用，异常大跳变仍拒绝并触发重定位。完成后执行 focused tests、compileall、diff check，再做离线回放验证。

### 追加发现：双人同目标为什么没有暴露同一问题

- (verified) `start_dual_target_experiment()` 每个 tick 直接用 `state.players` 视觉位置更新 follower，再调用 runtime；它不创建 `CommandRoleTracker`，也不以固定速度预测位置，所以当前“同目标成功”不能证明实时跟随的固定速度预测正确。
- (verified) 实时跟随的固定值链为 `_make_follow_runtime(speed_units_per_second=80.0)` → `ClosedLoopMotionController(expected_speed=80.0)` → `CommandRoleTracker(expected_speed=runtime.speed_units_per_second)`。
- (verified) `AdaptiveInputCalibrator` 确实有 `speed_gain = f(视觉位移/时间)`，但它依赖 runtime 先接受一个有效 `MotionResponse`；当前 P2 在首次校准前就被 tracker 的预测创新门拒绝，故动态速度没有机会生效。
- **修订旧结论：** 不能把“固定速度过高”简单改成低常数；正确方向是让跟踪器在视觉连续帧中计算实际速度，并在无样本阶段保守预测；双人同目标的直接视觉链路应作为行为参考。

**下一步计划：** 设计并实现 per-role 的视觉速度估计（位移/时间的鲁棒 EWMA、边界和置信度），让 tracker 记录输出只用于方向/TTL，预测速度采用已测估计；在预测拒绝但视觉点相对上一可信点连续时先更新速度并重基线，只有大跳变才恢复。补齐 tracker 与页面回归测试后再复测实机。

## [SYNC] 2026-10-05 — 实时跟随改为实测速度驱动

### A. SYNC 范围声明
**触发任务：** 修复实时跟随运行一段后因固定速度预测过快、视觉连续帧被拒绝而停止。
**直接变更文件：**
- `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_follow/command_role_tracker.py`
- `src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py`
- `tests/poe2_live_terrain/test_command_role_tracker.py`
- `tests/test_poe2_capture_test_page.py`
**预计连带影响：** 仅影响实时跟随的 per-role 预测与视觉校准；双人同目标、首帧定位、绘图模式和 Host 协议不改。输出仍只由现有 `ProgramFollowOutput` 发送。

### 2026-10-05 — 对照审查进入执行前状态

- 已完成 CodeGraph 调用链对照：双人同目标与实时角色跟随共用 runtime、路径规划、闭环控制和输出适配器；实时跟随额外插入 tracker 预测/创新门。
- 用户明确要求：速度不能长期固定，应按有效视觉位移/时间估计；固定值只作冷启动先验。
- 已更新断点文档，记录目标来源差异、共享底层边界和当前连续视觉重基线测试未触发的状态时间问题。
- 下一步：增加分支诊断日志并核对 per-role 捕获时间；修正 tracker/页面状态契约后，再统一运行跟随、同目标、输出和编译回归。

### 2026-10-05 — 连续视觉重基线分支的状态键修复

- 离线最小复现确认 `_sync_live_follow_from_fresh_frame()` 用 `actor_id` 写 `_follow_last_visual_positions`，tick 用 `RoleId.key` 读，导致 previous visual 永远为空，动态速度校准分支无法触发。
- 已按 `role.key` 写入；没有放宽创新阈值，也没有把速度改成另一个固定常数。
- 验证：连续视觉重基线 + tracker `8 passed`；`tests/test_poe2_capture_test_page.py` `83 passed`。
- 下一步：检查所有角色状态缓存和时间戳契约，补齐动态速度边界测试，并做同目标/实时跟随/编译回归。

## [SYNC] 2026-10-05 — 实时跟随角色键与视觉时间基线同步

### A. SYNC 范围声明
**触发任务：** 修复实时跟随连续视觉校正未触发，并确保速度从视觉位移/时间估计而非长期固定值驱动。
**直接变更文件：**
- `src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py`
- `tests/test_poe2_capture_test_page.py`
**预计连带影响：** `CommandRoleTracker` 的视觉校准调用方、实时跟随 tick、重定位上下文日志、双人同目标共享 runtime/output 对照链；不改变 Host 协议和绘图模式。

### C. SYNC 结果
**连带重读文件：** `capture_test_page.py` 的启动、实时 tick、同步基线和恢复日志；`runtime.py` 的 follower 更新/闭环控制边界；`program_output.py` 的 arm/apply/release；`command_role_tracker.py` 的速度估计与重基线；对应页面和 tracker 测试。
**CODEBASE.md 更新内容：** 更新采集页职责、双人同目标/实时跟随共享 runtime 边界、运动跟踪 Flow 第 6 跳和风险登记；记录 `RoleId.key` 缓存契约与视觉速度 EWMA。
**验证：** `tests/poe2_live_terrain/test_command_role_tracker.py tests/test_poe2_capture_test_page.py` 共 `90 passed`。
**新增 Finding：** 已修复同步基线 actor_id/RoleId.key 命名空间混用；未修改创新阈值、Host 协议或绘图模式。
**未闭合风险：** 尚未做新的实机 session 验证；需要确认实际视觉帧连续时速度估计和重基线能阻止误重定位，同时大跳变仍能恢复。

### C. SYNC 追加结果 — 速度校准边界

- `CommandRoleTracker.record_output()` 已修正为：无视觉样本时才使用有界 `speed_gain` 修正冷启动先验；已有视觉样本后直接使用视觉位移/时间 EWMA，避免校准倍率二次缩放实测速度。
- 新增 tracker 回归覆盖 `speed_gain=0.5` 仍保持实测 `10 native/s`；跟随页面 + tracker 回归共 `91 passed`。
- `CODEBASE.md` 已同步更新命令 tracker 算法、跟随 Flow 和风险登记。

### 2026-10-05 — 对照审查验证收口

- 调用链结论：双人同目标和实时角色跟随共用 `SimulatedFollowRuntime`、路径规划、闭环控制和 `ProgramFollowOutput`；实时跟随仅额外处理动态目标源、程序角色命令/视觉融合与恢复门。
- 已修复两处确定性问题：`actor_id`/`RoleId.key` 状态键混用；已学习视觉速度后重复乘 `speed_gain`。
- 验证：runtime/闭环/tracker/运动回归 `100 passed`；页面/程序输出/双人产品会话 `93 passed`；整个 `tests/poe2_live_terrain` `396 passed`；`compileall`、`git diff --check` 通过。
- 未发送真实输入。下一步实机只核对同一 session 的 `visual_continuity_check → visual_continuity_rebase` 与实测速度；若失败按第一条新异常继续，不重做旧排查。

### 2026-10-05 — session 1a10b5003ed-16b99485a90 后段停止诊断

- 排除固定测试时长：跟随在 17:05:55 启动，17:07:17 才同步并发出输出，没有总时长停止条件。
- 首个停止原因是双角色同时不可见：`markers_missing_grace` 连续 3 帧后转 `wall_and_local_match_failed`，触发 `recovery_required` 并释放输出。
- 证据帧 `1791191238009` 候选为空、原始截图均值约 4.99，正常帧均值约 19.49；属于整体暗帧/采集异常证据，不是单角色正常位移。
- 下一步只从该帧检查采集源和丢帧状态，评估短暂帧异常的保持/恢复策略；未修改代码和参数。

### 2026-10-06 — 恢复流程与用户停止生命周期分离

- 根因确认：视觉恢复分支复用了 `stop_dual_motion()`，间接调用 `stop_follow_experiment()`，产生 `follow_experiment.stopped` 并清空实时跟随状态；这发生在角色已经运行一段路之后。
- 修改：`stop_dual_motion(preserve_follow=True)` 只停止/重建视觉 worker，保留跟随 runtime、timer、输出会话和命令预测；恢复成功通过新鲜双人帧原地调用 `_sync_live_follow_from_fresh_frame()`，不再调用 `start_follow_experiment()`。
- 修改：恢复冷却、首帧拒绝和恢复 worker 异常均保持预测并安排重试；增加 `recovery_transition`、`recovery_resumed_in_place` 日志。
- 验证：页面/双人运动 `109 passed`，PoE2 focused `396 passed`，`compileall`、`git diff --check` 通过。尚未发送真实输入。

### 2026-10-05 — 恢复流程误用“停止”生命周期

- 用户确认本次真实运行已移动一段路；此前日志只覆盖恢复阶段尾部。
- 确认 `_on_dual_worker_result()` / `_request_live_follow_reanchor()` 的恢复分支复用 `stop_dual_motion()`，而 `stop_dual_motion()` 无条件调用 `stop_follow_experiment(_preserve_recovery=True)`，产生误导性的 `follow_experiment.stopped` 并清空活动跟随状态。
- 下一步拆分“恢复过渡”和“用户停止”：恢复只暂停当前视觉 worker/输出提交，保留会话与预测上下文，恢复后续接；终止入口仍仅限用户停止、页面关闭或地图实例失效。
## 2026-10-06 — 自动异常不再终止实时跟随

- 根因：跟随运行一段路后，视觉/截图恢复流程仍有漏网入口复用 `stop_follow_experiment()`；退休 worker 延迟重启还会丢失 `preserve_follow`，导致恢复后清空 runtime、timer、session 并记录 `follow_experiment.stopped`。
- 修改：`capture_test_page.py` 为实时跟随增加统一的可重试异常过渡；worker 失败、结果分发/同步 tick 异常、地图上下文暂时缺失、跟随 tick/程序输出异常均只释放当前输出并保留会话，恢复 worker 或下一 tick 继续。延迟重启传递 `preserve_follow`，自动 reanchor 不再设置 stop reason。
- 测试：`tests/test_poe2_capture_test_page.py` 86 passed；`tests/poe2_live_terrain` 396 passed；compileall、diff-check 通过。
- 未决：尚未做新的真实 PoE2 输入验收；实机应确认同一 session 出现 `recovery_deferred`/`recovery_transition` 后不再出现自动 `follow_experiment.stopped`，并在新鲜视觉帧到达后继续跟随。
- 追加：地图实例暂时不一致的 UI 也改为“等待重新定位（会话保留）”，避免把自动恢复显示成停止。
## 2026-10-06 — 同一视觉失配 episode 不再重复申请重定位

- 实机日志确认同一跟随角色的同一视觉失配在约 2 秒内重复进入 `recovery_cooldown` 和
  `reanchor_rejected`；`10,000ms` 冷却挡住了 worker，但没有挡住每 tick 的申请、输出释放、
  retry 调度和日志开销。
- 根因：页面只有时间冷却，没有实时跟随会话级的 recovery episode 锁。
- 下一步实现：首次实时跟随恢复申请设置 episode 锁；锁内不重复申请/释放/调度，成功新鲜帧重基线、
  接受新视觉或用户重新启动时清除；补 100 tick 单 episode 只申请一次的回归测试。

## [SYNC] 2026-10-06 — 跟随恢复 episode 去重

### A. SYNC 范围声明
**触发任务：** 降低同一视觉失配重复触发全局重定位的频率，保留恢复能力并避免跟随卡顿。
**直接变更文件：**
- `src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py`
- `tests/test_poe2_capture_test_page.py`
**预计连带影响：** 实时跟随 tick、双人视觉 worker 恢复分支、`CommandRoleTracker` 观测接受/重基线边界；
页面级全局恢复冷却和双人同目标路径需要回归确认。

### B. 影响扩散入口
- 页面 `start_follow_experiment` / `stop_follow_experiment` 拥有 episode 生命周期。
- `_tick_follow_experiment`、`_request_live_follow_reanchor` 和 `_continue_live_follow_after_dual_failure`
  共享 episode 锁，恢复成功由 `_sync_live_follow_from_fresh_frame` 清除。
- 双人 worker 的 recovery revision 分支也必须避免在活动 episode 内重新 claim。

### C. 本轮重读目标
- `capture_test_page.py`：恢复申请、worker 重启、视觉接受和 session 清理路径。
- `tests/test_poe2_capture_test_page.py`：现有冷却/恢复回归与新增 100 tick episode 测试。
- `CODEBASE.md`：跟随 Flow、风险登记和 capture page 职责同步。

### C. SYNC 结果
**连带重读文件：** `capture_test_page.py` 的 `_continue_live_follow_after_dual_failure`、双人 worker
recovery revision 两条分支、`_request_live_follow_reanchor`、`_sync_live_follow_from_fresh_frame`、
`start_follow_experiment`、`stop_follow_experiment`；`tests/test_poe2_capture_test_page.py` 的冷却、恢复、
视觉拒绝和新增 episode 回归；`CODEBASE.md` 的 PoE2 页面职责、运动 Flow 和风险登记。
**CODEBASE.md 更新内容：** 新增 episode 状态契约、完整恢复流和单 episode 风险边界；原先“跟随侧入口
可能绕过统一冷却并重复触发恢复”的风险标记为已修复。
**覆盖进度更新：** 页面恢复入口、worker 恢复入口和 tracker 观测接受边界均已复读并同步。
**新增 Finding：** 页面时间冷却不能代替活动会话 episode 去重；新增锁后同一 100 tick 失配最多一次
claim/restart，成功 fresh sync 后可重新申请独立恢复。
**验证：** `tests/test_poe2_capture_test_page.py` 与相关跟随/tracker 共 `178 passed`；`tests/poe2_live_terrain`
`396 passed`；`compileall` 与 `git diff --check` 通过。一次整页运行中的旧时间敏感测试已通过重跑确认，
并将该测试的 synthetic frame 改为显式 fresh，避免把 stale-frame 分支混入视觉拒绝断言。

## 2026-10-06 — 实机跟随不移动：重复失败视觉帧

- 证据：session `1a10da7b8fa-19d3f179850` 在前台恢复后 controller 2 已连续 `output_accepted`；同一 `captured_at_ms=1791230465873` 被每个 tick 重复送入 tracker，`rejected_count` 持续增长并触发 recovery。
- 根因：页面只对成功观测做时间推进，失败观测没有按时间戳去重；同一失败帧被误计为多帧连续失败。
- 边界：新增每角色最近评估帧时间戳，重复/旧帧只维持有界预测，不累计拒绝、不重复申请 recovery；保留新鲜帧的创新检测。
- 下一步：实现最小改动，补回归测试，运行 focused tests、compileall、diff check。

## 2026-10-06 — 修复重复视觉帧导致的跟随 recovery

- 实现：`capture_test_page.py` 以角色和 `captured_at_ms` 去重视觉观测；重复/旧帧继续使用有界命令预测，不增加拒绝次数。
- 实现：连续重基线的帧间隔放宽为独立 `3000ms`，当前帧新鲜度仍保持 `700ms`。
- 验证：新增两个页面回归；live-follow 21 passed；页面全量 74 passed；compileall/diff check 通过。
- 实机复测关注：跟随启动后是否持续 `output_accepted`，同一时间戳是否只出现一次 reject；若仍不移动，下一证据点是 Host 已接收但游戏消费/角色绑定，而不是重复 recovery。
### 2026-10-06 — 实机 session 1a10dbac8d6-15ea0f8d610 重定位证据分析（只读）

- 三次恢复原因已拆分：04:22:38 `repeated_visual_innovation_rejected` 为约 6.1 秒无新鲜视觉帧导致预测与旧 marker 偏离；04:23:11 `occluded_role_has_no_safe_candidate` 为角色坐标落在 `wall=255/collision=255` 的地图栅格，疑似坐标变换/墙体边界误判；04:24:11 `motion:markers_missing` 的失败帧 raw 实际是浏览器页面，属于截图前台窗口错误。
- 证据：`occlusion_diagnostics/1791231778856...`（第一次恢复后的最近帧）、`1791231791037...`、`1791231791137...`、`1791231849582...`、`1791231851519...`；最后两张 raw 明确为浏览器页面且 mask 为空。
- 双人恢复全局匹配耗时约 18.8-19.6 秒；本轮未改代码、未发送真实输入。后续先分别设计新鲜帧保护、坐标/墙体一致性校验、前台窗口校验，再讨论降低恢复频率和提速。

## 2026-10-06 — 降低误恢复与恢复重试风暴

- 基线提交：`8002892`（修复前工作区快照）。
- 根因边界：短暂视觉停滞、地图栅格边界误判、非游戏窗口截图和固定 1 秒恢复重试会把正常跟随误导入昂贵全局定位。
- 修复：停滞恢复门改为 8 秒；恢复重试 5 秒起步指数退避至 15 秒；无安全路线只有明确 recovery evidence 才触发；实时跟随校验 PoE2 前台帧；兼容 `contact_evidence=None`。
- 验证：页面及双人跟随/运动聚焦测试 `172 passed`；尚未发送真实输入。后续实机观察单 episode 去重、退避和前台帧过滤。
- 性能边界：前台窗口查询增加 250ms 缓存，worker drain 与 follow tick 共享结果，启动/停止清空缓存。
- 追加验证：同一聚焦测试仍为 `172 passed`，`compileall` 与 `git diff --check` 通过。

## 2026-10-06 — PoE2 实验代码 A0→C5 模块化任务启动

- 用户确认采用 A→B→C 渐进迁移路线，先兼容提取，再控制器组合，最后建立可脱离 Qt 的实验运行时。
- 已创建总任务断点：`docs/POE2_EXPERIMENT_REFACTOR_TASK.md`。
- 已创建实施计划：`docs/plans/2026-10-06-poe2-experiment-modularization-plan.md`。
- 已创建模块盘点：`docs/plans/2026-10-06-poe2-experiment-module-inventory.md`。
- A0 当前完成：页面约 6227 行、职责组、共享状态和副作用边界已盘点；待补齐逐符号调用路径、A1 失败测试和 A0 提交。
- 约束：实验代码不并入正式底层；每阶段更新文档、测试和 Git 检查点；不得发送真实输入。

## 2026-10-06 — A1/A2 状态与恢复模块提取

- A1 新增 Qt-free 状态模型：`experimental/application/models.py`、`experimental/follow/models.py`、`experimental/recovery/models.py`。
- A2 新增恢复决策模型和 episode/backoff 控制器：`experimental/recovery/controller.py`；页面恢复入口开始通过 controller 记录 episode、清理和 retry backoff，旧行为保持兼容。
- 新增模型与恢复控制器测试，页面聚焦回归 `95 passed`，`compileall` 与 `git diff --check` 通过。
- 下一步：提取双人视觉 worker/frame router，保持旧页面方法作为 façade。

## 2026-10-06 — A3/A4 与 B1～B4 首轮模块边界建立

- A3：新增 `experimental/multiplayer/controller.py`，统一 generation 过滤和双人帧事件；页面 worker 入口使用 `DualMotionController`，旧页面方法仍是 façade。
- A4：新增 `experimental/follow/target_sources.py` 与 `observation_fusion.py`；地图点击目标开始通过 `MutableTargetSource` 保存，视觉/预测融合有独立契约。
- B1：新增 `experimental/application/runtime.py`，跟随会话启动/停止接入统一生命周期 runtime。
- B2：新增 `experimental/motion/ports.py`、`decisions.py`，定义截图、内存、窗口、手柄和目标端口。
- B3：新增 `experimental/localization/service.py`，统一 `PositionEstimate` 与重定位服务边界。
- B4：新增 `experimental/diagnostics/events.py`，提供有界事件记录和耗时测量。
- C2 预备：新增 `experimental/composition.py` 与最小 `replay.py`，为后续完整装配和离线回放建立入口。
- 验证：实验新模块 + 页面回归 `108 passed`，`compileall` 和 `git diff --check` 通过；下一步继续把页面内算法实现迁移到这些控制器，不能停留在 façade。
# 2026-10-06 — 物理拆分回归修复与 A5 断点

- 发现：`dual_motion_mixin.py` 搬移方法体后遗漏 `QTimer`、`terrain_pixmap`、`prepare_localization_map` 导入，导致双人实时启动及 worker 重启路径失败。
- 修复：补齐三项显式导入，保持页面 façade 行为不变。
- 验证：`tests/test_poe2_capture_test_page.py` `89 passed`。
- 当前边界：页面探针逻辑仍直接编排 runtime、窗口和输出，下一步从 A5 开始接入 `experimental/probes` 控制器，并更新测试与文档。

# 2026-10-06 — A5 探针目标生命周期首轮接入

- 实现：新增 `FollowProbe`；点击移动、双人同目标、跟随目标分别由 `MoveProbe`、`DualTargetProbe`、`FollowProbe` 管理 arm/select/update/stop 生命周期。
- 组合：`Poe2ExperimentComposition` 统一装配三个探针；页面仍保留既有路径 runtime 和输出逻辑，避免重复实现移动算法。
- 验证：探针与页面聚焦回归 `92 passed`。
- 下一步：进入 B2 适配器边界，把窗口、截图、内存和 gamepad 副作用从页面 mixin 迁移到 ports/adapters。

# 2026-10-06 — B2 适配器边界与 C2/C3 离线运行时

- 新增：`experimental/adapters` 的 `AdapterBundle`、capture/memory/window/gamepad 协议及 `StaticMemory`、`StaticWindow`、`RecordingGamepad` 无副作用 fake。
- 装配：`build_experiment_composition` 接受显式 adapter bundle；双人 motion controller 使用注入的 capture port。
- 回放：`ReplayManifest`、`ReplaySource.at()` 和 `HeadlessExperiment` 支持无 Qt 的开始、帧摄入、恢复、停止事件序列。
- 验证：实验模块、页面回归、编译和差异检查通过，当前 `114 passed`。
- 下一步：补齐 C1 页面 façade 的剩余跟随编排，并进行 C4 全链路人工审查；禁止真实输入测试。
# [SYNC] 2026-10-06 — adapters、headless runner、probe lifecycle同步

### A. 本轮目标（阅读前声明）
**直接变更文件：**
- `experimental/adapters/ports.py`, `fakes.py`, `__init__.py`
- `experimental/application/headless.py`, `application/__init__.py`
- `experimental/composition.py`, `experimental/replay.py`
- `experimental/probes/controllers.py`, `ui/.../capture_test_page.py`, `ui/.../probe_mixin.py`

**预计连带影响：** composition 装配、页面目标点击/启停 façade、实验生命周期与回放测试。
**本轮想弄清楚：** 新增 adapter 是否保持 Qt-free，页面接入是否只改变生命周期而未改变移动 runtime；headless 状态转移是否可独立运行。

### C. SYNC 结果
**连带重读文件：** `adapters/ports.py`、`adapters/fakes.py`、`application/headless.py`、`composition.py`、`replay.py`、`capture_test_page.py` 的探针/跟随入口。
**CODEBASE.md 更新内容：** 增加 adapter、headless、replay、probe 模块职责、目标流和风险登记。
**覆盖进度更新：** 新增文件标记为 verified；跟随和双人目标页面编排仍为 partial，保留 C1 风险。
**关键发现：** adapter 与 headless runner 无 Qt/真实设备副作用；页面只在目标生命周期接入探针控制器，路径与输出算法仍在共享 runtime。
**修订旧结论：** 原先认为 A5 只有占位 controller；现在确认三种目标生命周期已实际接入页面，但副作用边界仍未完全替换。

# 2026-10-06 — C1 边界、C4 人工链路与 C5 候选评估

- C1：新增 Qt-free `FollowController`，目标刷新与 shared runtime tick 有明确边界；页面入口保留 façade，未复制路径算法。
- C4 人工审查：核对初始化→首帧→generation 帧路由→目标源→shared runtime→输出→视觉失效/恢复 episode→fresh frame resume→显式停止清理；确认旧 worker 丢弃、目标边界校验、恢复非终止和 stop 释放路径均有对应实现/回归。
- C5：候选仅列出 `TargetSource`/`FollowController`、`RecoveryController`、`PositionEstimate`、`ReplaySource`/`HeadlessExperiment`、`DiagnosticEvent`/`EventRecorder`；没有执行正式底层迁移。
- 验证：新增 follow controller 回归；下一步运行全量 PoE2 测试、编译、diff check，并提交最终检查点。

### C. 最终阶段验证
- PoE2 实验模块与页面聚焦回归：`115 passed`。
- `python -m compileall -q src`：通过。
- `git diff --check`：通过。
- 仓库全量 pytest：`1089 passed, 2 skipped, 1 failed`；唯一失败为环境缺少 `pydirectinput` distribution metadata 的既有 packaging 测试，与本次 PoE2 改动无关。
- 人工审查确认：所有真实设备动作仍只发生在 UI/Host adapter 边界；headless/fake/replay 测试不发送真实输入。
# 2026-10-06 — 04:25–04:30 会话根因复核（诊断阶段）

- 证据范围：`data/logs/poe2_live_terrain.log`，`2026-10-04 03:04:10–03:04:40`。
- `DexFourb` 长时间 `identity_dropout_failures` 增长，墙体质量仍可接近 1.0；状态持续 `recovery_required`，但 `recovery=False`，页面只进入 `live_role_follow.waiting`。
- 恢复闭环日志完全缺失：没有 `dual_motion.recovery`、`recovery_claimed`、双人首帧 worker 或 fresh resume。
- 代码追踪：`DualVisualTracker._failed()` 的 recovery 事件是一次性边沿；latest-only `Poe2DualMotionWorker` 通过 pending revision 传递该边沿；页面 `_drain_dual_motion_worker()` 只消费 pending/recovery_requested。当前风险是 recovery 边沿丢失或 tracker 已粘在 `recovery_emitted` 后，持续 recovery_required 不再触发页面重定位。
- 状态：未修改代码；下一步对照成功会话并添加最小回放测试，验证 pending revision、worker generation 和 tracker reset 顺序。

# 2026-10-06 — recovery_required 边沿丢失修复

- 修复 `capture_test_page`/`dual_motion_mixin`：按 tracker generation 保存已处理 recovery revision；当 latest-only worker 覆盖了 `recovery_requested=True` 的边沿，但仍收到更高 revision 的 `recovery_required` 状态时，页面兜底触发一次恢复。
- 新 tracker 启动时清零 revision；同一 revision 后续帧只进入等待/预测，不会重复触发昂贵重定位。
- 新增页面回归：`test_persistent_recovery_state_recovers_when_edge_flag_was_overwritten`。
- 验证：页面/PoE2 聚焦测试 `524 passed`；`compileall` 通过；`git diff --check` 通过。

# 2026-10-06 — 自动跟随完整逻辑文档化

### C. 本轮发现

- 已逐层核对页面入口、双人视觉 worker/tracker、冷启动同步、目标样本、命令预测、路径规划、局部控制、手柄输出、前台保护、局部脱困和全局重定位。
- 产出：[docs/POE2_AUTOFOLLOW_COMPLETE_LOGIC.md](docs/POE2_AUTOFOLLOW_COMPLETE_LOGIC.md)，按正常链路、异常链路、状态机、参数契约和日志阅读顺序描述当前实现。
- 明确记录的关键边界：预测位置不能单独确认到达；Host 提交不等于游戏消费；墙体质量和角色 marker 可见性独立；恢复是 episode + revision + cooldown，而不是每帧触发。
- CODEBASE.md 已增加文档入口，未修改运行代码。

### 覆盖进度更新

| 文件 | 前状态 | 现状态 | 本轮结论 |
|---|---|---|---|
| `capture_test_page.py` | 深度完整 | 深度完整 | 已核对启动、tick、目标样本、前台门控、输出、停止和恢复入口 |
| `dual_motion_mixin.py` | 深度完整 | 深度完整 | 已核对 worker、latest-only、generation、recovery revision 和恢复重启 |
| `dual_motion.py` | 深度完整 | 深度完整 | 已核对墙体匹配、marker assignment、保持窗口和 recovery 状态 |
| `multiplayer_follow/runtime.py` | 深度完整 | 深度完整 | 已核对 TTL、到达、A*、局部控制、接触恢复和 BLOCKED |
| `command_role_tracker.py` | 深度完整 | 深度完整 | 已核对视觉锚点、输出预测、创新判断、速度更新和 rebase |
| `program_output.py` | 深度完整 | 深度完整 | 已核对 arm/apply/neutral/release 的输入边界 |
| `POE2_AUTOFOLLOW_COMPLETE_LOGIC.md` | 新增 | 深度完整 | 当前自动跟随逻辑的文字权威说明 |

### 下一步

用户审阅文档后，按文档中的人工审查清单指出需要调整的状态、阈值或异常边界；在收到具体决策前不继续改运行代码。
# 2026-10-06 — 自动跟随完整逻辑文档化（阅读前声明）

### A. 本轮目标
**目标文件/符号：**
- `capture_test_page.py::start_follow_experiment/_tick_follow_experiment_impl`：确认自动跟随入口、目标源、状态和输出边界。
- `dual_motion_mixin.py::_start_dual_motion/_drain_dual_motion_worker`：确认双人视觉定位、恢复和 worker 路由。
- `experimental/multiplayer_localization/dual_motion.py`：确认视觉 tracker、角色丢失和恢复状态机。
- `experimental/motion/simulated_follow_runtime.py`、`core/routing/local_controller.py`：确认路径规划、局部控制、卡墙和到达判断。
- `program_output.py`、`command_role_tracker.py`：确认程序手柄输出、预测与视觉融合。

**本轮想弄清楚：** 当前 PoE 自动跟随从点击/启动到移动、视觉更新、异常恢复、重定位、停止的完整实际链路；文档只描述处理原理，不复述源码。

# 2026-10-06 — 全链路回归取证与待修复边界

- 运行 PoE2 聚焦测试和虚拟手柄 UI 测试；虚拟手柄套件独立通过，PoE2 套件在全量事件循环下有 3 个时序性失败，恢复测试单独运行通过。
- 已确认恢复函数在 fresh frame 后只同步 tracker，没有立即执行一次输出 tick；因此出现“恢复日志有了、输出 start 没有”的断点。
- 已确认 `frame_is_stale` 在 700ms 后直接释放跟随输出并返回，绕过命令预测和运动层接触证据；这是视觉延迟导致卡住/频繁重定位的真实风险。
- 双人同目标的过期帧保护本身正确；测试替换状态时未更新 `_latest_dual_captured_at_ms`，暴露出状态/时间戳必须作为原子帧契约传递。
- 下一步按系统化调试最小修改：恢复后一次受控 tick；视觉过期预测保持；新增回归后再检查 shutdown/timer/worker 生命周期。

# 2026-10-06 — 视觉间隙预测保持与恢复输出修复

- 修复 `_tick_follow_experiment_impl`：超过视觉 TTL 的帧进入 prediction hold，继续使用 `target_hold`/`command_prediction` 更新 runtime；不再仅因一帧延迟释放手柄。恢复阈值仍由视觉停滞计时器和运动层证据控制。
- 修复 `_maybe_resume_dual_follow_after_relocalization`：fresh frame 同步成功后立即执行一次受控 follow tick，确保恢复日志后出现 `output_armed/output_accepted`。
- 修复冷启动完整 marker 门槛：新鲜墙体可信但单个角色 marker 暂时缺失时，使用已确认首帧 seed 进入 `sync_degraded`，缺失角色走 bounded prediction，避免首次视觉延迟把跟随卡在冷启动。
- 新增页面生命周期 `suspend()`，宿主隐藏/延迟关闭时停止跟随、双人目标、截图 worker 和输出租约，避免后台 Qt timer 串扰其他页面；`shutdown()` 仍为终止清理。
- 为 preview/hybrid/program-probe/follow/dual-target/dual-motion/multiframe timer 增加顶层隐藏保护回调；无 parent 且未显示的实验页由真实 timer 自动 suspend，直接手动 tick 的离线测试仍保持可控。
- 为无时间戳视觉间隙增加本地时钟兜底，同时保留 stale 标志，避免 `int(None)` 崩溃或误当 fresh frame。
- 更新并新增回归：预测保持、缺失时间戳、恢复后重新 arm、创新拒绝与双人目标重置均通过。
- 下一步：完成 shutdown、singleShot recovery retry、retired worker 生命周期审查，并运行全量验证。

## [第C4补充审计] 2026-10-06

### A. 本轮目标（阅读前声明）
**目标文件：**
- `src/auto_modules/ui/modes/poe2_live_terrain/probe_mixin.py`：检查首帧恢复后跟随和双人同目标的状态门槛。
- `src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py`：对照恢复调用链、输出重新挂载和生命周期入口。
- `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_localization/dual_motion.py`：确认恢复后 `degraded` 帧的墙体可信度和角色估计契约。
- `tests/test_poe2_capture_test_page.py`：补齐恢复后 marker 暂缺的回归场景。

**本轮想弄清楚：** 除 `recovery_required` 边沿外，恢复首帧是否会因合法的 `degraded` 状态而永远不恢复；并检查初始化、输出、停止和页面隐藏路径是否存在同类终止或资源泄漏。

### C. 本轮发现
**关键发现：** (verified) `probe_mixin.py::_maybe_resume_dual_target_after_relocalization()` 与 `_maybe_resume_dual_follow_after_relocalization()` 原先只接受 `status == "tracking"`；`capture_test_page.py::_sync_live_follow_from_fresh_frame()` 对 `degraded` marker 只要 `visible=False` 就拒绝，即使墙体注册可信且角色仍有 `available=True` 的 bounded estimate。这会把合法的恢复首帧挂在 recovery context 上，阻断双人同目标和实时跟随恢复。

**修复：** 新增 `_recovery_frame_usable()`，仅在 `degraded + wall_trusted + 所需角色均有位置估计` 时放行；同步阶段将该状态下 `available=True` 的有界角色估计作为锚点。保留地图实例、角色位置、捕获时间和 `recovery_requested` 校验，没有把不可信帧当成恢复成功。

**验证：** 新增并通过两个恢复回归（同一 runtime 原地重锚、恢复重建首帧 degraded）；相关聚焦测试 `3 passed`（含既有原地重锚测试）。全仓此前结果为 `1091 passed, 2 skipped, 2 failed`：`pydirectinput` 缺 distribution metadata，以及虚拟手柄一个跨套件 Qt backoff 时序测试；虚拟手柄套件独立运行 `22 passed, 1 subtest passed`。

**修订旧结论：** 原来认为恢复只需等待 `tracking`；现在确认 `degraded` 只要墙体可信且角色估计有界，也属于可安全恢复的中间状态。

**追加发现：** (verified) 实时恢复入口原来用 700ms 判断“可恢复”，随后调用 `start_follow_experiment()` 又用 300ms 判断“可启动”，导致 301–700ms 的帧先进入恢复、再被启动入口拒绝，并消费掉恢复上下文。现已统一实时恢复使用 300ms；超龄帧保留 context 等下一帧。程序移动恢复也共用 degraded 安全帧门槛。

**追加发现 2：** (verified) `start_follow_experiment()` 原先在定位/角色/输出校验前就 arm `FollowProbe`；无效点击启动会留下过期目标源状态。现改为 runtime、角色和 output 全部构造成功后再 arm，并增加无定位上下文回归。

**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `src/auto_modules/ui/modes/poe2_live_terrain/probe_mixin.py` | 深度完整 | 深度完整 | 2 | 恢复门槛统一到 `_recovery_frame_usable()`，双人同目标和实时跟随共用安全放行条件。 |
| `src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py` | 深度完整 | 深度完整 | 2 | 跟随恢复同步接受墙体可信的有界 degraded marker 状态；仍保留新鲜度与输出边界。 |
| `src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_localization/dual_motion.py` | 深度完整 | 深度完整 | 2 | 确认 `available`/`wall_trusted` 的状态契约和恢复估计来源。 |
| `tests/test_poe2_capture_test_page.py` | 深度完整 | 深度完整 | 2 | 增加恢复首帧 degraded 的原地与重建回归。 |

**下一轮计划：** 运行完整 PoE2 聚焦回归、compileall、diff check；再做一次人工状态机审查，确认所有自动 recovery 只进入非终止状态，显式 stop/hide/shutdown 才释放输出。

## [SYNC] 2026-10-06 — 恢复状态与探针生命周期补全

### A. SYNC 范围声明
**触发任务：** 全面审查已知 recovery_required 问题之外的 PoE2 实验链路，补齐恢复状态和生命周期边界。
**直接变更文件：**
- `src/auto_modules/ui/modes/poe2_live_terrain/probe_mixin.py`
- `src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py`
- `tests/test_poe2_capture_test_page.py`
- `docs/POE2_EXPERIMENT_REFACTOR_TASK.md`
- `CODEBASE.md`
**预计连带影响：** 双人同目标/实时跟随/程序移动恢复门槛、角色 marker 暂缺时的同步、FollowProbe arm 生命周期、页面 recovery context 和相关回归。

### C. SYNC 结果
**连带重读文件：** `probe_mixin.py`、`capture_test_page.py`、`dual_motion.py`、`command_role_tracker.py`、`multiplayer_follow/runtime.py`、`program_output.py`、`dual_motion_mixin.py`。
**关键变更：**
- 新增 `_recovery_frame_usable()`，统一 `tracking` 与可信 bounded `degraded` 恢复门槛；双人同目标、实时跟随、程序移动共用该契约。
- 实时恢复统一 300ms 新鲜度；超龄帧保留 recovery context，不再被启动入口消费后丢失。
- degraded 同步只接受非领队角色的 `available` 有界估计；手动领队 marker 缺失继续使用 `target_hold`，不会把异常 `players` 坐标写成新目标。
- FollowProbe 延后到 runtime、角色和输出创建成功后 arm；无效启动不会留下 stale armed 状态。
**验证：** PoE2 页面与实验全套 `519 passed`；虚拟手柄 UI 独立套件 `47 passed, 1 subtest passed`；`python -m compileall -q src` 和 `git diff --check` 通过。
**全仓边界：** `pytest -q` 得到 `1096 passed, 2 skipped, 2 failed`。失败仍为环境缺少 `pydirectinput` distribution metadata，以及虚拟手柄一个跨套件 Qt backoff 时序测试；该套件单独运行稳定通过，非 PoE2 专项回归。
**人工审查：** 初始化无上下文不启动；旧 generation 帧丢弃；首帧/恢复每 revision 单次内存读取；视觉短暂丢失使用 prediction；恢复是非终止 episode；fresh frame 重新 arm；显式 stop、hide、shutdown 清理 timer/worker/output；单人、双人、同目标共用 `SimulatedFollowRuntime` 与 `ProgramFollowOutput`。
# 2026-10-06 — 自动跟随算法原理补充（阅读前声明）

### A. 本轮目标
**目标文件/符号：**
- `docs/POE2_AUTOFOLLOW_COMPLETE_LOGIC.md`：补充公式、评分函数、状态判定和算法输入输出。
- `dual_first_frame_experiment.py`、`dual_motion.py`：核对几何变换、墙体位移和 marker assignment 原理。
- `command_role_tracker.py`、`runtime.py`、`core/routing/local_controller.py`：核对预测、路径评分、局部控制和接触恢复的实际计算。

**本轮想弄清楚：** 上一版文档已经说明执行链，但需要把每个主要算法的“数据→计算→判定→输出”讲清楚，让用户可以不用读代码判断参数和逻辑是否合理。

## 2026-10-06 — 自动跟随算法原理补全（完成）

- 在 `docs/POE2_AUTOFOLLOW_COMPLETE_LOGIC.md` 新增 10A 原理章节。
- 逐项解释双人首帧相似变换、墙体位移、marker assignment、命令预测与视觉校正、A* 多尺度路线、局部方向评分、撞墙证据、到达/TTL、recovery episode、速度校准和参数耦合。
- 公式均按当前源码核对，特别说明：预测位置不能单独证明到达；视觉短暂丢失和 recovery 不是用户停止。
- 本轮没有修改运行代码，没有发送真实输入；需执行差异检查后交付文档。

## 2026-10-07 — 解释 `test_poe2_capture_test_page.py` 的职责和规模

- `(verified)` 通过 CodeGraph 和源码索引确认：该文件约 3,229 行、102 个 `test_` 用例，不是运行时模块，不会随程序启动执行。
- `(verified)` 文件集中覆盖采集页生命周期/保存、预览与地图、单/双人首帧与视觉 worker、单程序移动、实时角色跟随、预测与恢复、双人同目标以及页面关闭/输出清理。
- `(finding)` 长度主要来自单文件承载多个状态机的 Qt 集成测试、每个场景都要构造 fake service/archive/recognizer/output、以及大量历史回归边界；不是单个算法本身有 3,000 行。
- `(design debt)` 当前测试文件仍是页面职责拆分后的集中回归入口，适合后续按功能拆为多个测试模块并把 doubles/fixtures 提取到 `tests/poe2_live_terrain/fixtures.py`，但本轮未修改测试结构。

## [第 2026-10-06-5 轮] 2026-10-06 — 完整地图运行契约复核

### A. 本轮目标（阅读前声明）
**目标文件：**
- `src/auto_modules/ui/modes/poe2_live_terrain/probe_mixin.py`（确认程序移动没有第二个地图级总时长停止点）
- `src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py`（确认入口、计时器、停止原因只保留局部安全边界）
- `src/auto_modules/features/poe2/live_terrain/experimental`（搜索遗留 max duration / timeout 语义）

**本轮想弄清楚：** 上一轮移除了探针的 30 秒总时长门后，是否仍有配置、调用链或页面状态机在整张地图运行期间按 elapsed time 停止；验证“完整跑图直到目标/明确安全边界”的契约。

### C. 结果与证据

- `(verified)` CodeGraph 调用链确认 `_tick_program_move_probe()` 的运行时间只用于停止摘要 `elapsed_ms`；没有 elapsed/max-duration 分支，`_program_probe_max_duration_ms` 也不再被读取。
- `(verified)` 当前程序移动停止入口只对应前台失焦、定位/地图上下文失效、视觉帧超过单帧 TTL、Host 输出异常、运行状态明确完成/阻塞、用户操作和页面生命周期；这些均为局部安全或明确状态边界，不是地图级总时长限制。
- `(verified)` 全部遗留 duration/timeout 搜索未发现新的地图级运行时长门；10 秒值只用于用户确认后切回游戏窗口的输入前等待，Host TTL 只约束单次手柄报告。
- `(verified)` 回归：`tests/test_poe2_capture_test_page.py` `105 passed`；`tests/poe2_live_terrain` `422 passed`；`python -m compileall -q src` 通过；`ruff check --select F821 src/auto_modules/ui/modes/poe2_live_terrain` 通过；`git diff --check` 通过（仅 CRLF 转换提示）。
- `(verified)` 长运行回归仍覆盖 24 小时旧起始时间并注入遗留 duration 属性，tick 继续 apply、没有 elapsed stop；本轮没有发送真实游戏输入。

### D. 文档同步

- `docs/POE2_EXPERIMENT_REFACTOR_TASK.md` 已保留并确认“地图完整运行契约补充”；`CODEBASE.md` 已包含程序移动长运行边界和 mixin 依赖说明。

### E. 当前结论与下一步

- 当前代码满足“地图运行不因总时间自动停止”的要求。真实跑图仍会在到达、明确阻塞、失焦、定位/地图实例失效、Host 异常、用户停止或页面关闭时结束。
- 未授权且未执行实机输入；若用户进行实机长跑，重点观察 `step=program_probe.stop_summary reason=... elapsed_ms=...`，其中 `elapsed_ms` 是事后诊断字段，不是停止条件。

## [第 2026-10-06-6 轮] 2026-10-06 — 自动跟随逻辑文档与实现对照

### A. 本轮目标

**目标文件：**
- `docs/POE2_AUTOFOLLOW_COMPLETE_LOGIC.md`（核对算法原理、时间契约、状态机和停止语义）
- `src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py`（核对最近跟随/长运行修改的实际边界）
- `src/auto_modules/ui/modes/poe2_live_terrain/probe_mixin.py`（核对独立程序移动探针的停止语义）

**本轮想弄清楚：** 自动跟随说明是否仍准确反映当前代码，尤其是 6 秒跟随输入等待、10 秒前台/恢复等待、无地图级总时长限制，以及实时跟随与独立程序移动探针的不同终止边界。

### C. 结果与证据

- `(fixed)` 文档已明确记录：地图级运行没有总时长上限，`elapsed_ms` 只是停止摘要诊断字段；视觉帧龄、Host TTL、恢复 cooldown 和 worker join timeout 不是地图计时器。
- `(fixed)` 文档已将 6 秒跟随输出启动等待、独立程序移动探针 10 秒前台确认等待、恢复重定位 10 秒 cooldown 分开说明，避免把局部等待误读成地图时限。
- `(fixed)` 文档已区分实时跟随和独立程序移动探针：实时跟随的 `BLOCKED`/恢复通常释放输出并保留会话；独立探针对 `arrived`、`blocked`、`waiting_position`、`map_mismatch` 会结束本次探针，但同样没有总时长停止。
- `(verified)` 代码对照确认：`_FOLLOW_COMMAND_ARM_DELAY_MS=6000`；`_FOLLOW_FOREGROUND_WAIT_MS=10000`；`_DUAL_RECOVERY_COOLDOWN_MS=10000`；`_program_probe_started_at_ms` 仅用于停止摘要。
- `(verified)` `git diff --check` 通过；本轮只修正文档，没有修改运行代码、没有发送真实输入。

### D. 文档同步

- `docs/POE2_AUTOFOLLOW_COMPLETE_LOGIC.md` 已更新时间契约、输入延迟、BLOCKED 语义、状态图说明、停止含义和人工审查清单。
- 本轮无需修改 `CODEBASE.md`：源代码职责和调用链未变化。

### E. 下一步

- 若后续继续优化，优先用 `program_probe.stop_summary` 的明确 reason 区分探针状态结束和实时跟随会话恢复，避免再次把局部状态误解为地图级超时。
- `(verified)` 22:50 后两次真实跟随会话已完成异常审计；排除了 22:53 后 `Area/role-a/role-b` 回归桩日志。
- `(verified)` 发现局部路线短暂 blocked（约 1.8–2.9 秒自恢复）、短视觉遮挡（约 1.08–2.58 秒，不重定位）、角色长期/交替丢失（触发 recovery_required）。
- `(verified)` 会话 1 一次恢复 worker 14.337 秒、约 16.47 秒回到 tracking；用户停止发生在恢复期间。会话 2 一次恢复 worker 22.457 秒、约 23.43 秒 fresh_sync；最后一次候选 score 约 0.877、shape_quality 约 0.386，未完成可信 reanchor。
- `(verified)` 当前门槛：marker grace 2 帧、失败 3 次进入 recovery、hold 2,000 ms/uncertainty ≤10、最大 marker step 45 px、identity margin 2、recovery cooldown 10 s；墙体可信与角色可用性独立。
- `(finding)` 主要异常是角色颜色/遮挡造成 marker dropout，全局恢复成本是主要性能瓶颈；异步恢复回调与用户停止/session token 边界需后续审查。
- `(scope)` 本轮只读日志和 evidence.json/raw.png，不改运行时代码、不发送真实输入；详见 `docs/POE2_EXPERIMENT_REFACTOR_TASK.md` 的异常审计章节。

## [第 2026-10-06-8 轮] 2026-10-06 — marker 丢失继续跟随与恢复边界

- `(decision)` 图色丢失是观测降级，不是跟随终止；继续使用大地图最后可信坐标、命令位移和速度模型，视觉恢复后再校准。
- `(fixed)` 在 `dual_motion_mixin.py` 增加 marker-only recovery 判定；墙体可信且仅角色 marker 丢失时，不重启全局首帧 worker、不释放实时跟随输出。
- `(fixed)` 在 `capture_test_page.py` 放宽实时跟随状态门：marker-only `recovery_required` 允许进入跟随预测路径；地图/墙体失效和运动层恢复证据仍保持原恢复入口。
- `(fixed)` 兼容 `_failed()` 的恢复诊断：marker-only 状态有时没有 `wall_trusted` 字段，改用 `role_observations` 作为角色丢失证据，显式 `wall_trusted=false` 仍禁止续行。
- `(fixed)` 实时 reanchor 先走 `DualVisualTracker.request_local_correction()`；复用已确定的方向/比例和局部 matcher，运行时不再读内存、不再重做全局首帧。局部 matcher 明确失败后才允许升级。
- `(verified)` 新增局部重锚测试；双人运动与跟随恢复相关测试 `27 passed`，`compileall` 和 `git diff --check` 通过。
- `(verified)` 相关组合测试 127 passed；双人同目标一个时序用例组合运行时波动，单独重跑 passed。尚未发送真实输入。
- `(risk)` 全局重定位耗时的主要降低来自减少 marker-only recovery 触发；真正地图/墙体失效时仍可能需要 14–23 秒首帧恢复，后续再优化 worker 的局部重锚和异步结果合并。

## [第 2026-10-06-9 轮] 2026-10-06 — no_safe_route_cooldown 不再停止移动

- `(finding)` `no_safe_route_cooldown` 原本只是上一次路线规划失败的 1 秒缓存，却被直接映射成 `BLOCKED`，导致输出释放和人物停住；不能把栅格失败等同于现实无路。
- `(fixed)` 冷却期间改为 `no_safe_route_probe`：输出 100ms 有界侧向/前向探索脉冲，利用目标方向、上次输入和小地图左右空闲量，下一帧继续重规划。
- `(verified)` 跟随运行时测试 `60 passed`；新增冷却期非零输出用例；未发送真实输入。

## [第 2026-10-07-10 轮] 2026-10-07 — 人物不动路径全量审查

- `(finding)` 运行时会造成无输出的主要分支是首次 `no_safe_route`、冷却期 `no_safe_route_cooldown`、`stalled_no_escape`、`contact_relocalization_required`、零向量 `route_not_progressing`，以及位置/目标 TTL 过期。
- `(fixed)` 上述分支统一改为有界探索脉冲或低置信预测保持；只有未初始化目标、地图实例不一致、确认到达和页面/前台安全边界保留停止。
- `(verified)` 跟随运行时 `60 passed`，双人运动 `25 passed`，compileall 和 diff check 通过；capture page 仅剩一个已知双人同目标重启动作时序波动，单独运行通过。
- `(risk)` 真实游戏前台失焦仍会释放输出，这是安全边界；地图实例切换仍需重新初始化，不能用旧地图继续控制。
- 2026-10-07 — 00:22–00:23 实机异常只读取证：确认虚拟手柄 program session expired/revoked、候选存在但 assignment.options 为空、目标落在 wall/collision 栅格、worker 超周期丢帧和双 marker 长时丢失；证据与截图路径已写入 `docs/POE2_EXPERIMENT_REFACTOR_TASK.md`，未修改运行代码、未发送输入。
- 2026-10-07 — 跟随稳定性首批实现：新增动态 marker association、局部可行走目标投影、program session 单次 rearm 和 worker 自适应节流；关联/投影/跟随/双人/虚拟手柄聚焦测试通过，页面时序用例单独重跑通过。
- 2026-10-07 — PoE2 实验全量回归 `429 passed`；同步更新 stale visual replay 断言，确认视觉短暂过期继续使用有界预测输出。

## [第 2026-10-07-11 轮] 2026-10-07 — 三层稳定性方案收口

- `(implemented)` 双人 marker assignment 增加 pair geometry 软评分和诊断，避免颜色候选冲突导致身份整体拒绝。
- `(implemented)` 目标坐标投影增加局部开放比例/clearance 评分，中心栅格误差时选择局部更稳的可行走点。
- `(implemented)` no-safe-route 冷却与 stalled 分支改为六向局部自由空间评分脉冲，始终保持有界输出并下一帧重评估。
- `(verified)` 关联、投影、跟随 runtime、双人 motion `90 passed`；PoE2 专项 `431 passed`；页面专项单独运行 `105 passed`；compileall/diff-check 通过。
- `(finding)` 页面专项全量组合的 4 个 dual-target Qt 时序用例仍会偶发失败，但四个用例单独运行全部通过，未形成稳定回归；需在后续页面测试隔离中处理。
- `(next)` 等待用户明确授权后进行实机验证；记录 pair geometry、projection、probe、session rearm 和 worker EMA/drop 诊断。

## [第 2026-10-07-12 轮] 2026-10-07 — 最新实机异常只读审计

### A. 本轮目标
读取最新 PoE2 跟随日志、occlusion evidence 和 raw 截图，区分真实算法异常、前台保护和正常生命周期清理；本轮不改代码。

### C. 关键发现
- `(confirmed)` 首帧 accepted，前段双人 tracking 正常；前台切换导致约 59 次 `poe2_not_foreground` 采集忽略，之后恢复。
- `(confirmed)` 两个 marker 都存在但 pair/动态关联仍拒绝 Dex：单候选距离约 `33px`、pair error `36px`，导致 51 次 dropout；这是当前最明确的算法异常。
- `(confirmed)` 后段 StrDex 长时间 marker loss，`recovery_required` 重复诊断且 uncertainty 达约 `178 native px`，但没有重复全局恢复；需降低噪声并明确预测漂移升级边界。
- `(confirmed)` 目标附近 start/target 均被 native 栅格判为 wall/collision，四个 A* 尺度 no_path，probe 六向全部不可行走；与实际体验不完全一致，仍是坐标/局部栅格偏移风险。
- `(confirmed)` worker 单帧 `38–75ms`、`dropped_results=129`；latest-only 生效但延迟仍会扩大关联误差。
- `(not observed)` 未发现本次新的 session expired、异常堆栈或全局 recovery；末尾 deferred stop 与页面隐藏一致。

### D. 证据
- `data/poe2_live_terrain_test/occlusion_diagnostics/1791307748207-1791307748207-0f14d12c/evidence.json`
- `data/poe2_live_terrain_test/occlusion_diagnostics/1791307748207-1791307748207-0f14d12c/raw.png`
- `data/logs/poe2_live_terrain.log`，时间范围 `2026-10-07 01:27–01:29`

### E. 下一步
先与用户讨论三个取舍：pair 失配时的单角色保留策略、目标投影邻域扩展策略、recovery_required 重复日志降频与预测不确定度上限。

## [第 2026-10-07-13 轮] 2026-10-07 — 暂时失配与采样频率方案决策

### A. 本轮目标
根据最新实机证据讨论两件事：颜色干扰造成的暂时 marker 失配如何处理，以及提高采样频率是否能改善定位、热路径是否需要迁移到 C/Cython。

### C. 关键结论
- `(decision)` 暂时失配不能作为单帧失败；监控小地图中的干扰颜色要求颜色身份保持软约束。
- `(finding)` 当前单帧 `38–75ms`，提高采样频率前必须先降低单帧成本，否则会增加 dropped results。
- `(proposal)` 采用单角色保留、另一角色预测保持；pair geometry 只降低置信度，连续 2/3 帧确认后恢复完整关联。
- `(proposal)` marker 识别约 25–30Hz，墙体位移约 10–15Hz，局部重锚按需执行；队列继续只保留最新帧。
- `(proposal)` 优先优化 ROI、重复预处理、NumPy 复制和高频日志；只有 profiling 证明 Python 循环占主耗时时再迁移 Cython/C++。

## [第 2026-10-07-13 轮] 2026-10-07 — 用户决策与性能方案讨论

- `(decision)` 用户确认双人暂时失配时保留已确认的单角色；另一角色单独进入候选等待/预测，不拖垮整组 assignment。
- `(decision)` 用户确认扩大目标局部投影范围，继续保持小人物半径和不膨胀墙体。
- `(discussion)` 用户提出提高图色帧采样频率；当前日志 `38–75ms` 处理耗时高于 `33ms` 周期，需先优化/拆分识别阶段，避免高频采样只制造更多丢帧。

## [SYNC] 2026-10-07 — 稳定性模块代码库同步

### A. SYNC 范围声明
直接变更文件：`marker_association.py`、`target_projection.py`、`runtime.py` 及其纯测试；连带影响 `DualVisualTracker` 关联诊断、跟随规划诊断和页面 worker 消费链。同步更新 `CODEBASE.md` 的目录职责与模块说明。

### C. SYNC 结果
- 动态关联的 pair geometry、目标投影的状态契约、六向探针评分字段已与代码一致。
- 受影响调用链复核：`DualVisualTracker._assign()` → `MarkerAssociator.assign()`；`SimulatedFollowRuntime._plan_safe_route()` → `WalkableTargetProjector.project()`；`_cooldown_probe_command()` → `FollowObservation.vector` → `ProgramFollowOutput.apply()`。
- `CODEBASE.md` 已补充新增文件及算法边界；未改变正式定位/正式底层引擎。
## [第 2026-10-07-17 轮] 2026-10-07 — 回退负优化并进入只读对照审查

### A. 本轮目标

- 将代码恢复到 `a3070ea`，撤销首帧候选和连通域相关负优化。
- 对比正式绘图页、正式导航页与实验双人页的采集、处理、渲染、线程和恢复边界。
- 在形成根因和证据前不继续改运行代码。

### C. 当前结果

- `(verified)` HEAD 已回退到 `a3070ea`；`a618207`、`333d1d8`、`0e887e9` 不再位于当前工作树历史。
- `(finding)` 1:56 后的首帧耗时回归与候选数量/组合搜索边界相关；双人实时崩溃尚未从日志获得稳定 traceback，仍需对照正式链路。
- `(next)` 读取正式绘图页、正式导航页和实验 worker 的完整帧链路，建立只读性能对照表。

## [第 2026-10-07-18 轮] 2026-10-07 — 完成正式/实验链路对照（只读）

- `(confirmed)` 首帧手动入口仍在 Qt GUI 线程同步执行 3 次截图、识别和 `DualFirstFrameRegistrar`；候选上限 6 时为 `6P2=30` 组有序排列，叠加几何搜索，首帧几十秒/界面无响应是确定性结构问题。
- `(confirmed)` 正式绘图与导航均采用单帧流水线、上一帧回退、UI只消费结果；实验双人仅实时 worker latest-only，首帧和预览/证据归档边界仍不一致。
- `(decision)` 本轮不改运行代码、不继续调参数；后续先实现后台首帧任务边界、候选有界筛选和阶段耗时诊断，并以回归测试验证 worker generation/迟到 signal/失败清理。
- `(reference)` 记录 OpenCV video tracking、shape/contour 与 ROS2 image_transport/image_pipeline 的可借鉴边界到 `docs/POE2_FOLLOW_ROLLBACK_CHECKPOINT.md`。

## [第 2026-10-07-19 轮] 2026-10-07 — 用户确认单帧首帧与异常帧回退方向

- `(decision)` 首帧人物静止时只采一帧并注册一次，取消无收益的三帧共识。
- `(decision)` 实时链路以 latest-only 和有效处理频率为目标；单帧视觉失配沿用上一帧可信状态并结合速度/手柄方向短时预测，恢复后融合视觉观测。
- `(constraint)` 单帧异常不停止跟随、不立即全局重定位；只有预测不确定度或地图有效性越界才升级恢复。
- `(plan)` 先实施单线程固定节拍方案 A 并补阶段耗时/状态机回归，再依据 profiling 决定是否拆三级流水线方案 B。

## [第 2026-10-07-20 轮] 2026-10-07 — 首帧改为单次采样

- `(implemented)` `capture_test_page._compute_dual_first_frame()` 的手动/恢复首帧采样次数从 3 改为 1，移除无收益的帧间等待。
- `(verified)` 新增调用计数回归断言；目标页面测试通过（1 passed）。
- `(next)` 继续实现纯 tracker 的短时预测保持和恢复融合，仍不调颜色/面积/全局置信度参数。

## [第 2026-10-07-21 轮] 2026-10-07 — 双人 tracker 异常帧预测保持

- `(implemented)` `DualVisualTracker` 对静止/暂时不可测墙体复用上一变换；marker 或墙体短时异常返回最后可信角色地图位置，不再输出空人物集合。
- `(diagnostic)` 状态增加 `prediction_active`、`prediction_reason`、`prediction_age_ms`、`wall_prediction_hold`，便于区分视觉缺失与地图失效。
- `(verified)` `tests/poe2_live_terrain/test_multiplayer_motion.py`：25 passed。
- `(next)` 为 live worker 增加候选提取和总处理耗时字段，继续保持 latest-only。

## [第 2026-10-07-22 轮] 2026-10-07 — worker 阶段耗时与有效帧率诊断

- `(implemented)` `DualMotionFrameResult` 增加 `candidate_ms`、`total_worker_ms`；worker 增加 processing EMA、adaptive interval、effective FPS。
- `(implemented)` 双人 motion timing 日志现在区分 capture/recognition/candidate/tracking/total，并记录 dropped/completed。
- `(verified)` worker 测试 10 passed；页面双人专项 13 passed。
- `(next)` 继续隔离 UI 预览/evidence，补离线回放覆盖异常帧保持与恢复。

## [第 2026-10-07-23 轮] 2026-10-07 — UI 渲染节流与离线回放

- `(implemented)` 双人控制状态每个 latest result 都更新，预览和地图 overlay 限制到 12Hz，避免 Qt 场景绘制拖慢控制帧。
- `(implemented)` 新增 `tests/poe2_live_terrain/test_dual_follow_replay.py`，覆盖单帧 marker 失配、空墙体短时预测和视觉恢复。
- `(verified)` 页面全量 `105 passed`；双人 worker/motion/replay `37 passed`；首帧专项 `19 passed`。
- `(next)` 运行 compileall、diff check 和全量 PoE2 相关回归，确认没有破坏首帧/双人生命周期。

## [第 2026-10-07-24 轮] 2026-10-07 — 方案 A 完成专项验证

- `(verified)` `tests/poe2_live_terrain`、`tests/test_poe2_capture_test_page.py`、`tests/test_poe2_dual_motion_worker.py` 合计 548 passed。
- `(verified)` `python -m compileall -q src` 与 `git diff --check` 通过。
- `(boundary)` 本轮只完成离线/页面回归，没有真实游戏窗口或手柄输入验证。
- `(next)` 用户实机测试时重点查看首帧是否只采一帧、有效 FPS、candidate/total timing，以及异常帧是否保持预测而不立即停止。
