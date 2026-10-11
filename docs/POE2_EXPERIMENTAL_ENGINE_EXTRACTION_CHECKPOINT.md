# PoE2 实验能力抽取方案断点（2026-10-10）

## 任务边界

- 用户要求：先保存实验室代码的 Git 检查点，再参考正式项目源码与架构规范，产出模块功能拆解、底层能力抽取和逐层组合成当前业务的详细方案文档；本轮不修改源代码、不合入正式引擎。
- 基线：`65dff05` 保存实验实现；`5607475` 保存最新成功跟随的日志分析。用户确认 2026-10-09 22:06–22:09 正常前台跟随体验成功；尾部切换窗口后的超时不应算进前台跟随失败。
- 约束：保持已验证的角色识别、视觉纠偏、预测、规划和输出行为及参数；明确哪些能力才真正可下沉，哪些规则仍属 PoE2 跟随业务。规划时考虑性能、进程生命周期、输出会话及证据日志。

## 当前状态

- Git 检查点已提交。Serena 已激活 `auto_modules`；`initial_instructions` 在此服务端不可用，已继续用已启用的导航能力。CodeGraph 已读取现行实验引擎及正式能力符号。
- 正式 `ARCHITECTURE_GUIDE.md` 明确 `core→application→adapters/UI/feature` 依赖方向、PoE2 与 Torchlight 业务隔离、GUI只装配、真实输入仅适配器产生。现行 `core/localization`、`core/routing`、`core/mapping`、`core/perception` 与 `adapters/virtual_gamepad` 已有基础模块；方案必须先对照接口，避免重复下沉。
- 实验主链已有分离的 `vision`、`tracking`、`control`、`recovery`、`process_supervisor`、`output_scheduler`、`composition`，但它们仍位于 `features/poe2/.../experimental/follow_engine`。`LegacyDynamicFollowRouteController`调用既有实验跟随runtime；`OutputScheduler`依赖 `FusionSnapshot`，是值得规划抽象的边界。以上为初轮源码/目录发现，待精读定位真实依赖。
- 精读证实 `build_poe2_follow_engine_page_adapter` 将PoE2捕获/墙体提取、首帧seed、`LegacyDynamicFollowRouteController`、内存源与坐标旋转、`AsyncSnapshotOutput` 装配在 UI 所在模块；拟迁到PoE2 feature composition，UI只负责调用。`FollowControlRuntime.apply_visual` 将同帧证据、receipt回放/时间倒推、创新门、速度学习、leader target与局部/内存恢复聚合；目前它是关键状态拥有者，不能只按文件行数拆。`RecoveryPolicy` 的 L0–L3/阈值已属连续跟随策略，若下沉只能抽出通用恢复执行机制，不能把这些PoE2阈值当成通用默认。正式 `MultiMarkerLocalizer` 已保证同帧注册但语义与实验的持续视觉/命令融合不同，优先组合接口而非直接替换。
- 历史 `docs/architecture/` 明确是迁移前快照；只借鉴facade逐步抽取方法，不按旧根级路径建兼容壳。`Torchlight`跟随的 `FollowerPlanner` 复用 `core.routing.PathFinder`，为共享路径能力提供第二调用方；它的LaggedTrajectoryTarget/TTL/blocked语义与PoE2实时追当前点不同，不能合并业务策略。
- 三份设计稿已写：`docs/plans/2026-10-10-poe2-experiment-module-inventory.md`（真实链路/20类能力/重用边界）、`2026-10-10-poe2-layered-engine-design.md`（分层、契约、状态owner、包布局与A/B/C路线）、`2026-10-10-poe2-engine-extraction-roadmap.md`（P0–P6阶段、等价/性能/实机门槛与回退）。推荐B：契约先行的纵向切片；正式页接入放P5。未改源码，方案待用户评审。
- 计划交付：现状模块盘点、目标分层与契约、分阶段迁移与验收三份文档。仅文档，方案需用户审阅后才能实现。

## 下一步

1. 等待用户审阅三份文档，重点决定方案B与正式页接入阶段；根据反馈调整方案。
2. 得到设计认可后，才制定逐文件的实施任务并开始迁移。本轮禁止源代码改动和真实输入。

## 2026-10-11 首帧性能核对（只读）

- 用户询问首帧定位是否可提速及各环节耗时；本轮未改源码、未启动真实输入。
- 最新实测日志已有阶段计时：`memory_ms` 约 3647–4160ms，`capture_ms` 约 10–41ms，`recognition_ms` 约 11–101ms，`registration_ms` 约 2603–11151ms，`total_ms` 约 6552–15106ms；worker 总耗时通常再增加约 20–35ms。
- 当前主要瓶颈是内存适配器的进程/模块/layout/实体遍历，以及双角色绝对配准的候选排列、形状搜索和验证；截图与图色识别不是主瓶颈。
- 现有计时尚未细分内存读取内部阶段、单个 assignment/variant 耗时、形状搜索内部阶段、post-validation、worker 排队等待；不能在补齐这些计时前直接改阈值或宣称优化完成。
- 证据边界：`candidate_count=3`、`assignment_count=6`、`evaluated_variant_count=12` 时容易出现 `ambiguous`，常见 margin 约 0.022–0.030；不能仅降低 ambiguous 门槛换速度。
- 下一动作：如用户授权开发，先补内部阶段计时和离线基准，再逐项优化内存读取与配准搜索；保持双角色身份/旋转/镜像安全约束。
