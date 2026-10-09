# 双线并发跟随：联合审查与监督清单

## 任务与边界

用户授权跨会话讨论、双方独立审查与后续15分钟监督；此轮不修改运行代码、不输入游戏、不重启。对方会话01a11cef-6c24-7c12-885b-50020981713f；本会话01a1107c-2234-7b02-beae-97ed0415ed3a。

核心：只改变模块组合/并发和视觉-预测-内存融合；保持旧版已验证的寻路、局部避障、路径跟踪、脉冲和手柄策略。明确bug单独修复，不能借重构替换积木。同函数但参数、dt、输入坐标、输出时序不同，也可能违背行为契约。

## 当前推进断点

已确认对方最新任务完成且idle，已发送首轮讨论消息，要求只读审查并维护其独立文件POE2_FOLLOW_PEER_REVIEW_20261009.md；允许按用户授权回复本会话。尚未收到回复，不称讨论完成。正在阅读全文可见历史并核对源码。

## 待处理清单（初版，证据来源须区分）

| ID | 优先级 | 问题/行动 | 证据状态 | 完成条件 |
| --- | --- | --- | --- | --- |
| J01 | P0 | wall_quality原始响应与[0,1]契约不一致 | 对方最新日志诊断+离线修复报告，待独立源码复核 | adapter正确映射且接受判断语义未变，无实机重复故障 |
| J02 | P0 | 新版绕过LocalMotionController/VectorPathTracker，规划与脉冲参数改变 | 对方已确认差异，待具体场景旧配置对照 | 相同输入/状态下旧版决策与新适配器等价；不重新写策略 |
| J03 | P0 | Vision故障后预测继续、P2越过P1 | 实测现象，具体贡献未全部证实 | 对齐真实/融合位置、target age、输出duration/receipt时间解释因果 |
| J04 | P0 | 父侧Qt poll仍是观测/输出/回执relay | 源码确认 | 核心闭环脱离UI节拍，明确单一运行owner |
| J05 | P0 | watchdog父侧消费进度不等于child健康 | 源码确认；先drain顺序已修 | 分离alive、child progress、IPC age、parent gap，真实stale不漏检 |
| J06 | P0 | 确定性fault抑制重建后可能无视觉恢复出口 | 新修复风险，待推导 | 有显式故障/重新启用出口及低频兜底，不能永久盲预测 |
| J07 | P0 | 延迟视觉融合、预测双重积分、旧观测覆盖 | 待人工场景检查 | 按观测时刻校正后推进，receipt去重，单owner/版本过滤 |
| J08 | P1 | transform与图片/位置跨帧或跨代混用 | 先前离线复现修复，仍需当前源码检查 | 同帧元数据、exact slot、当前平移、首帧旋转/尺度闭合 |
| J09 | P1 | stop/start/rebuild共享资源与迟到回调 | 已有修复及剩余边界待查 | owner清楚，旧代无回写/幽灵输入，partial rebuild保留目标 |
| J10 | P1 | 单目标、双目标、动态follow走不同runtime | 源码确认 | 同一旧版移动组件与配置契约，只替换目标源 |
| J11 | P1 | 恢复预算、ROI/A*、Queue积压拖慢控制 | 待最新实测量化 | latest-only观测/目标，receipt适当FIFO，异步single-flight恢复 |
| J12 | P1 | R0指标口径错误与重复warning | 前次源码确认 | entry gap/poll duration分离、稳定异常降频、真实阶段age |
| J13 | P1 | Host lease心跳/重arm/实际输入消费 | 已有独立心跳，端到端待查 | heartbeat、指令更新、游戏位移分别有证据 |
| J14 | P1 | 内存兜底触发与过频/缺失 | 待量化策略核对 | 新帧局部纠偏优先；两线失败才升级、限频single-flight |
| J15 | P1 | 到达hold、冷启动、人手动停止语义 | 既有用户契约 | 10s非零闸门；靠近只neutral hold，动态session不因到达释放 |
| J16 | P2 | 并发机制选型 | 方案待讨论 | 线程/原生计算/进程按真实耗时、IPC及生命周期比较 |

## 每次监督检查

读取对方最新完成轮次/变更/断点，记录是否涉及寻路、手柄策略及参数；任何策略差异先列证据并讨论，不由监督方同时改代码。记录发现→修复→独立复核→离线验证→实机待验状态，不将测试通过等同于游戏验收。

下一动作：完成3点后可见对话范围索引，独立核对J01/J02/J06，等待对方审查结果；之后综合双方问题清单和分歧并更新15分钟监督提示。

## 3点后对话阅读索引（北京时间2026-10-09）

read_thread最新10轮覆盖了所有可见03:00之后历史轮次，上一更早轮次始于00:53:45。记录顺序：03:15:12失败测试分析；03:27:19旧版/计划/实际架构对照；03:29:52历史计划恢复；03:31:15实现偏离与验收过度判断；03:33:40新总规范；03:38:33 R0日志补强；03:53:40最新wall_quality与策略替换诊断。用户相同要求的早先重复轮次在当前返回列表中未单独出现，不假称所有不可见正文已恢复。00:53长轮次可能跨3点，已同时阅读其最终交接结论作为背景。

变化应合并而非覆盖：早期watchdog假阳性为风险假设；最新03:44运行有wall_quality明确异常，不能以早期假设取代。先drain/10s启动窗是本会话已修事实，与历史6s描述区别。32个focused checks是对方离线报告，不代表新版游戏通过。

## 本方独立源码审查第一轮

- J01：process_wall实际对导出quality做min/max范围映射，estimate_bounded_displacement原始accepted仍保留；这是契约适配，非统计意义的置信度校准。非有限响应如何处理仍须确认，不应把无效响应变成高可信。
- J02：MapAwareRouteController默认downsample=4、clearance/dead_end惩罚均为0、fixed magnitude=.65和duration=80；该路由决策直接取路径前瞻点或无路直达fallback，缺少旧版局部避障/动态脉冲组件。旧Git a3070ea页面工厂dynamic arrival=12、resume=20，fixed-target arrival=8；旧downsample=8、clearance_radius=20、weight=2、dead_end=.75、prediction_horizon=.25。不能把新版arrival=12本身当动态跟随回归，也不能将core LocalMotionController默认值当页面实际注入值。
- J06：_check_worker_stall将任意非空first_fault字符串放入重复fault抑制判断，并非已证明该error确定性；命中过往signature后只标failed并保持session，注释要求下次显式session。其逻辑可能将一次瞬时旧故障扩大成后续不恢复，且无法保证视觉通道再启动。应按worker/generation/当前重复故障计数分类，明确恢复出口。
- 新增J17：FollowControlProcessHandle._send的priority Queue(maxsize=8)满时，execution/recovery非target命令直接return，执行回执可以静默丢失。不能把“优先级队列未被视觉挤占”等同于“不丢执行回执”。若回执驱动odometry，需决定可靠FIFO或可证明等价的累计回执，而非随意latest-only。用户手动stop另有event，不能据此证明receipt可靠。

讨论请求已被对方接受，轮次01a11d22-ec21-7ed1-acae-e4733d9aea22进行中；对方明确本轮不改代码，独立审查后回复。下一动作：接收同行文件、逐项核对并发送本方新增J17证据与参数纠正，保留未证实标记。

## 第一轮同行结果与第二轮反馈

对方已完成01a11d22轮次，全文读取其独立同行文档。双方共识：新版策略绕过旧组件是边界偏移；wall_quality故障与watchdog风险分开；Control tick/Output heartbeat独立不等于闭环独立；fault抑制须恢复出口；两目标模式需统一旧策略契约。

已发送第二轮具体纠正（不改运行代码）：旧动态follow参数按真实工厂验证；J17 receipt静默丢失；first_fault不应永久控制后续故障分类；local新帧纠偏不等待uncertainty超限；Qt暂停验收必须覆盖新观测/新指令/回执，非仅tick心跳；receipt≠游戏真实位移；独立relay actor与worker直连均可评估。

J17列为P0。必须逐receipt确认是否包含增量或累计区间，再选可靠队列或语义合并；未证明之前不能任意增加队列容量当彻底解决。

状态：第二轮反馈待答，联合方案尚未最终收口。15分钟automation已改为持续监督，不再在初次讨论后自动终止。监督仅读取完成轮次/源码并指出越界；不同时写对方运行文件。

### 第二轮收口（01a11d26完成）

对方确认全部七项反馈并修订独立文档；本方全文复读。讨论/双方独立审查完成，实施与实机验收未完成。没有实质方向分歧；并发机制和内存具体阈值仍须证据定量，不能虚构已确定。

对方文档正文已改，但第7节仍留两句旧摘要：P0写“uncertainty超限才memory/local”，P1验收仍只写tick/heartbeat。执行时以本清单/正文新契约为准：local下一新帧优先，memory单独升级；Qt暂停验收覆盖新视觉、新方向、receipt全过程。监督时要求该摘要同步，不允许旧摘要驱动实现。

补充receipt合并约束：first/last tick+总时长+最后vector不足以重建期间转向位移。若采用累计回执，必须保留可积分的分段方向/时长或有明确坐标口径的累计控制积分、幂等区间和失败/neutral边界，禁止把整个区间按最后方向积分。Host应用证据仍不是游戏真实位移。

最终优先顺序：J01/J02/J17/J06/J07为阻断项，继而J04/J05/J08/J09/J10/J11/J13/J14/J15，最后以真实吞吐决定J16。J12诊断质量随对应修复同步完成。旧成功策略的实测效能与新版实机均未在本轮验证。

持续监督：已有automation每15分钟读取完成进展，检查策略边界和以上残留文本，维护J项状态；不自动实施运行代码，重大方案变化需回到用户讨论。

## 人工运行场景核对矩阵

| 场景 | 必须人工沿源码推导的结果 | 禁止的行为/验收误区 |
| --- | --- | --- |
| 启动且P1/P2贴近 | 10s输入闸门、neutral lease保活；靠近保持hold，leader移动触发旧策略 | 到达释放session；首snapshot证明闭环通过 |
| P1快速移动或位移 | target最新时序、位置年龄与不确定度更新；旧路线规则决定重规划 | 旧target回写、仅凭计划位移确认到达 |
| 一帧颜色污染 | 预测持续；下一新帧ROI立即准备，按预算执行 | 直接全局恢复或停止；等待漫长blind预算 |
| 数帧连续失配 | 两线互助，搜索范围由不确定度决定；无法恢复才量化限频内存 | 纯预测长期当真值，内存每tick读取 |
| 视觉延迟而结果有效 | 同帧图片/transform；观测时刻融合再重放已执行运动到现在 | 旧坐标直接覆盖当前，运动积分两次 |
| 回执Queue满 | 区间连续/幂等，丢失可见，融合不虚构运动 | 静默return后自称actual execution完整 |
| 页面卡顿3s | 新观测、新输出和回执仍流转；UI恢复只读最新状态 | 仅tick/heartbeat前进就认为端到端独立 |
| Vision contract错误 | 保留原始fault；限制同故障重启，独立纠偏有恢复出口 | 无限重启；抑制后永久盲预测 |
| stop与rebuild交错 | token/epoch/owner阻止旧bundle写入；手动stop无幽灵输出 | 迟到重启、关闭旧queue影响新worker |
| Host过期/断开 | 本controller重arm/明确故障，receipt如实反映应用情况 | Host fault触发地图全局重建；接受报告当真实位移 |
| 窄门、贴墙、近目标 | 复用旧PathFinder/Tracker/LocalMotionController及场景配置 | 换固定向量fallback/脉冲，新增膨胀改变可走区域 |
| P1/P2互换与双目标 | 每role状态独立、旧运动契约共享，仅target来源不同 | 写错controller、角色间状态覆盖 |

## 推荐实施次序与监督门槛

1. 固化成功Git的真实配置/调用链和策略差异表，J01契约bug先独立修；标记不可变规划/输出模块。
2. 恢复旧运动组件的组合与参数，并审查receipt可靠性、预测积分、target新鲜度；适配器不复制/改写策略。
3. 建立预测/视觉并发的状态契约与唯一owner，再选择独立relay或直接通道；不要边实现边更换模型。
4. 校正健康/生命周期及局部→内存恢复出口，避免同时大改多个边界造成归因困难。
5. 按上述矩阵推导，focused离线证据与真实页面/游戏证据分层；用户要求完整地图无硬时限。

每项更新列出：基线、修改符号/参数、为什么仍符合边界、实际消息路径、失败证据、离线验证、实机待验。若无法证明策略等价，先停该项实施并讨论，不把它包装成性能优化。

### 2026-10-09 05:50 heartbeat：J07边界证据增加，核心三项仍阻断

对方01a11d71完成且idle：重复/错generation receipt测试及视觉generation/exact frame过滤共14项通过；明确承认J02完整旧新replay、J06 repair_pending恢复出口、J07 delayed captured_at replay仍未完成。

已派发三项收口任务：J02可执行fixture六场景和真实composition装配；J06按worker/epoch/signature去重并在ready/有效观测后清除；J07观测时刻纠偏→实际receipt推进→去重及下一帧local恢复时序。仍不可实测。

### 2026-10-09 06:05 heartbeat：J06闭合，J02仅fixture证据，J07唯一明确阻断

对方01a11d7f完成且idle：J06 signature已绑定worker/stale set/epoch/generation/fault，valid Vision observation清除并允许新repair；J02有六场景动态fixture和per-role证据（33 focused passed），但明确不能冒充a3070ea checkout replay。J07延迟captured_at/local-first完整时序仍未实现。

已派发优先J07实现/回归任务，并要求以git show旧调用结果或明确源码等价边界补J02证据。当前J01/J02（证据等级）/J04/J05/J07等仍open，可实测门未满足。

### 2026-10-09 06:20 heartbeat：J07核心时序完成，局部纠偏/transform与J02证据仍开放

对方01a11d8d完成：迟到视觉按captured_at回退receipt分段后融合，13项focused通过；未完成下一帧local ROI优先、连续失败后memory升级、transform失配拒绝及J02独立a3070ea证据。已派发最后边界与全量J项人工复核任务，仍不可实测。

### 2026-10-09 22:35 heartbeat：J07边界批次完成，推进父侧relay/watchdog

对方01a11d9a已空闲并报告：J07增加错误frame元数据拒绝与当前transform绑定，J02薄适配器已装配并明确为`contract_equivalent`；focused control/adapter 17项通过，compileall与diff-check通过。该证据不包含完整 degraded→下一帧local→连续失败→memory 回放，也不包含独立a3070ea checkout 的动作序列重放或真实游戏验收。

仍开放的最高风险是 J04/J05：父侧 `engine.poll()` 仍承担 Vision→Control→Output→receipt relay，watchdog健康时间戳主要来自父侧消费，UI/Qt停顿与子进程停顿尚未可区分。下一派发要求先做父侧 relay 解耦边界与独立健康证据的 focused 失败/恢复场景；同时补 J07 local-first escalation replay。不得修改 PathFinder、VectorPathTracker、LocalMotionController、脉冲参数或动态配置，也不得启动真实输入。

本轮实际结果：对方只增加 `FollowEnginePort.diagnostics()` 的父侧/child进度字段，port focused 18项通过；没有改变relay所有权，也没有完成J07/J14回放。已再次派发窄范围实施任务：真实multiprocessing Queue的父侧暂停/child继续与child真停两场景；visual miss→下一帧local→连续失败才memory的完整replay。未满足可实测门。

后续轮次再次出现“只诊断不实现”：对方补充了03:44旧Vision fault与P2越过P1证据边界，但没有新增J07/J14或J04/J05 replay。已明确要求直接新增可执行三类测试：local-first降级回放、父侧暂停/child真停spawn场景、J02动作语义不变量；未完成前不得继续以假设替代证据。

最新离线复核：新增 replay/process/port/control/legacy 集合 `41 passed`。J07/J14 的 local-first、receipt去重、memory cooldown 与 J02 contract fixture 有离线证据；J04/J05 仍阻断，因为暂停测试仅证明 child→Queue 写入，FollowEngine 的 Vision→Control→Output→receipt 仍由 UI `poll()` 调度。下一派发要求在 engine 内建立非Qt relay actor/loop，并用端到端暂停与真实child停顿场景验收；旧移动组件和参数不可变。

RelayLoop首版已落地并有25项relay/port focused通过，证明UI暂停时fake Control/Output仍推进；独立源码复核发现新的竞态：RelayLoop与`poll()`在首snapshot为空时都可调用`_poll_once()`，缺少串行保护。该问题可能导致重复消费、receipt/重建交错，已派发锁/唯一调用者修复与并发竞态测试；J04/J05仍未关闭。

锁修复后独立重跑发现并发测试的停止边界断言不稳定（reader停止时生产者可能已多生成一帧，`max(seen)`暂落后一 tick），而非运行时重复应用。已派发测试同步修正，要求保留`output.applies == produced_tick`、无relay_error等有效断言；在修正前不把26项报告视为稳定通过。

测试同步已修正；独立连续运行并发竞态5次全部通过。UI relay竞态可暂记离线闭合。仍开放J04/J05真实spawn handle的child停止→单次fault/rebuild→新generation交接；已派发该具体实现和迟到旧事件拒绝测试。

J04/J05后续复核确认现有真实 FollowEnginePort 生命周期测试覆盖 stall预算、原子rebuild、旧代隔离、stop→start、relay锁和首读语义，port/replay 26项通过；但没有强制终止真实Vision/Control child后的完整重建，故保留“离线闭合、实机未验收”。下一派发转向J10，盘点并统一单目标、双目标、动态跟随的旧移动组件契约。

J10复核：共享`LegacyFollowMotionContract`已接入页面/动态构造，路线/控制底层仍复用旧三组件，相关集合27项通过；旧页面生命周期仍是`SimulatedFollowRuntime`，不能称全runtime统一。下一派发J11/J12，补阶段耗时、队列年龄、drop与p95诊断/离线基准，实机吞吐仍待验。

J11/J12派发过程中，执行方源码对照发现新的P0策略偏离证据：`LegacyDynamicFollowRouteController`当前固定`duration_ms=80`/`magnitude=1.0`，而a3070ea动态运行时按控制周期和每role状态计算脉冲，并包含arrival/resume、无进展、贴墙/门口恢复等语义。该差异可能直接导致P2越过P1，故暂停性能优化，转回J02/J03完成旧策略动作契约提取与等输入对照；不得用视觉阈值掩盖。

旧策略适配器已改为委托`SimulatedFollowRuntime(continuous_follow=True)`，但独立复跑发现一个遗留测试仍断言近目标`arrived=True`和固定80ms，实际返回`follow_hold_within_radius`且duration由旧状态机决定。已派发测试契约修正与等输入对照；该失败不能用删断言掩盖，须验证持续hold和目标重新移动恢复。

测试契约已修正并独立复跑：相关集合 `56 passed`；近目标保持、目标移动恢复、目标停止后neutral和逐tick动态duration均与旧runtime对照。P0策略偏离离线闭合，实机仍未验收。J11/J12性能计时与p95基准现重新派发，前提是不得改变已恢复策略。

J11/J12阶段计时实现已独立复跑相关集合`63 passed`，覆盖Vision/Control/Relay/Output/receipt/latest-only的p50/p95/max与queue age/drop。剩余小缺口仅是local/memory/rebuild整链路aggregate p95，已派发补充；不把离线吞吐当真实25–30Hz。

恢复/重建aggregate计时已补齐，focused恢复/控制/输出/视觉集合52项通过；但发现一个旧测试仍断言UI parent poll直接消费fake event，与relay唯一消费者契约冲突。已派发将测试改为观察relay-owned progress/snapshot/diagnostics并连续重跑，不能回退relay。

旧relay测试已按新契约修正，独立连续10次通过；J11/J12相关集合57项通过。下一派发进入J13/J15：虚拟手柄lease/session失效重arm与10秒冷启动、动态hold/恢复语义；实机Host/game仍未验收。

J13/J15复核完成：独立相关集合53项通过，覆盖neutral heartbeat、session rearm、10s gate、continuous hold/resume；真实Host/Game仍未验收。现派发J01–J17最终逐项审计，要求证据等级和剩余阻断明确，不再扩展运行策略。

最终审计结果：最小相关集合`106 passed`，compileall与diff-check通过。J01–J15均有offline_verified/contract_equivalent结论；J16为partial（缺真实IPC/GIL/Qt/Host/game吞吐）。当前达到“可进入受控用户实测”门槛，但不等于完整地图稳定通过。必须在实测中重点观察P2长距离是否越过P1、Host receipt到实际位移、真实child rebuild、地图滚动transform和Qt暂停持续性。

## 最新用户授权：持续推进至可实测

用户明确要求持续监督并发送后续任务，让对方实施修复直到双方独立审查、人工推导符合基本规则且无阻断问题，可以进入用户实测。此授权取代此前“本轮仅讨论、不得自动进入实现”的限制：允许向指定对方会话下达清单内实现/修复任务，不必每阶段重新请求用户许可。监督方仍不与执行方并行改共享运行文件，不自动启动真实输入/网络/重启。

调度保持15分钟。对方运行中先记录问题、不打断；空闲后读取完成结果、独立检查diff和源码，将未解决的最高优先问题组成下一条具体任务发送。失败或偏离边界必须指出证据、预期行为、相关符号及验收场景，不能只发泛泛“继续”。记录每次派发对应的J项、目标轮次、已检查结果以防重复。对方当前01a11d29仍在进行文档收口，尚未发送新实施指令；下一次空闲后发送用户最新实施授权并从J02/J17/J06/J07推进。

终止门：J01-J17全部有结论（已修/已验证/有证据无需改），两方分别按真实源码审查12场景及新增故障场景，策略等价、通信完整、生命周期、纠偏优先级、性能预算无遗留阻断；相关focused检查通过，真实输入尚未验收明确标注。可以用户实测≠游戏已稳定通过，不能承诺不存在任何bug。满足此门后向用户报告可测试，并结束本轮推进监督；未满足不得因对方停下、测试数量或任务时间结束监督。

首批实施指令已发送：确认01a11d29完成且idle后，明确最新用户授权实施，要求先J02/J17并检查J06/J07，顺序小目标/每步人工推导与focused证据，复用旧策略，回复监督会话。对方01a11d29已纠正同行文档第7节两个旧摘要与receipt分段规则。下一动作：15分钟检查该首批新轮次完成进展，未完成不重复派发；完成后独立审查并下达下一任务。

### 2026-10-09 04:20 heartbeat

恢复读取清单/审查断点与迭代。read_thread确认首批实施轮次01a11d2b-da00-7f32-8022-ddf430e5557a仍inProgress，已明确接受J02/J17实施和J06/J07检查，尚无完成结果。遵守不打断：未重复发指令、未审查正在变化的实现为完成品。下一次15分钟检查该轮次；若完成，读取其证据和diff独立审查；若仍执行，继续等待。当前仍不满足可实测门槛。

### 2026-10-09 04:35 heartbeat：J17独立复核未通过

对方01a11d2b已完成且idle：新增256项pending FIFO、focused26 passed（迭代写25，有报告口径差异），J02仍未实施。本方CodeGraph精读_send/_flush_pending_executions并read-only离线复现竞态：旧seq1 flush满返回→consumer释放槽→新seq2直接put成功→后续旧seq1补发，实际delivery=[2,1]。child priority gate可拒绝旧seq1，故J17未闭合。相同通道recovery_signal插队也会使旧receipt序号过期。256满仍丢，仅打印日志，且recovery满仍直接return，需显式证据缺口/恢复规则。

已发送具体修正与继续实施任务：先修pending不得绕过/同priority顺序/overflow可见状态/恢复信号可靠交付及日志节流，失败回归覆盖精确满→空交错；随后继续J02真实旧策略组件复用与J06/J07边界。未改运行代码、未重复运行对方focused suite、未真实输入。下一次15分钟读取新轮次完成结果并独立复核，J17/J02保持open。

### 2026-10-09 04:50 heartbeat：FIFO竞态修复通过，溢出出口未接入

对方01a11d3b完成且idle：priority spill统一execution/recovery FIFO，日志debug化，focused10 passed。独立CodeGraph核对并重跑原满→空调度诊断，delivery=[1,2]，具体FIFO绕过问题已修。J17总体仍open：_priority_overflow只初始化/赋值，全follow_engine/tests无读取，256溢出拒绝receipt未传到Control，无法影响证据质量或定位纠偏。不能把私有标记当实际融合可见状态。

已发送下一实施指令：窄边界接通evidence/transport gap消费，不虚构运动、不停止session；同时必须实现尚未开始的J02旧策略薄适配器实际装配，覆盖hold→leader移动/转向窄门/角色互换、旧新相同输入决策对照。不是再次请求计划或许可；用户持续授权已明确。下一15分钟读取新结果，J02/J06/J07等仍阻断，可实测门未满足。

### 2026-10-09 05:05 heartbeat：J17 gap消费完成，顺序边界仍待闭合

对方01a11d49完成且idle：overflow现在生成execution_gap，Control消费并提高uncertainty/source=execution_gap，不停止session；focused10 passed。独立源码复核发现_pending_execution_gaps未参与_send的“pending存在”判断，gap→新priority命令仍可能跨边界；gap先flush也可能与priority已有项形成边界问题，需明确sequence/range并补测试。J02仍未实施。

已派发下一任务：闭合gap与所有priority命令的统一顺序语义、准确role/sequence/range、下一帧local纠偏证据；开始旧版动态运动组件薄适配器实际装配及hold/移动/转向/窄门/角色互换replay。J17/J02/J06/J07继续open。

### 2026-10-09 05:20 heartbeat：J17/J02首版完成，证据尚不足

对方01a11d56完成且idle：gap统一FIFO及交错测试已报告通过；J02新增LegacyDynamicFollowRouteController，实际复用PathFinder/VectorPathTracker/LocalMotionController并注入动态配置（12/20/80/8/24/.25）。独立门槛仍未满足：没有旧版→新版动作序列replay，未完全证明适配器在Control实际调用链装配；J06/J07未处理。

已派发证据/继续实施任务：补J17实际投递单调与坏gap验证，J02覆盖hold/移动/减速转向/窄门/角色互换旧新vector-duration-arrival-route对照，推进J06 fault去重恢复出口和J07时间戳纠偏/防重复积分。J17/J02/J06/J07仍open，可实测门未满足。

### 2026-10-09 05:35 heartbeat：J17输入边界通过，J02 replay/J06/J07仍开放

对方01a11d64完成且idle：J17 gap role/sequence/初始化校验及J02 adapter contract共13项通过。独立门槛仍未满足：J02缺a3070ea旧→新完整replay（近目标减速、转向、门、贴墙、角色互换及每role动作序列），J06 fault恢复出口、J07 captured_at纠偏/重复积分均未实现。

已派发下一任务，要求可执行旧版fixture与composition装配证据，并按阻断时序补J06/J07 focused失败用例。J01/J02/J06/J07等仍open。

### 2026-10-09 replay 与进程边界批次

- 新增 `test_follow_engine_replay_contracts.py`，6 项通过：local-first、captured_at receipt 单次积分、memory 单飞/cooldown、坏 generation/transform/重复 receipt、spawn child progress/stall、J02 legacy route contract。
- J04/J05 证据仅覆盖真实 spawn child 与 Queue 的 parent pause/child progress 和 child stop；它证明健康时间戳可以独立观察，但没有声称 Qt 父侧 relay 已经解耦。
- J02 目前仍为 `contract_equivalent`，不能替代独立 `a3070ea` checkout 的完整动作序列 replay。旧规划和手柄模块未改。
- 实测门仍未满足：需 fresh-process 验证 Vision wall-quality 修复、补完整 target→route→intent→receipt 关联日志，并继续审查 parent relay ownership。

### 2026-10-09 J04/J05 RelayLoop

- `FollowEnginePort` 已增加独立 `RelayLoop` thread；UI `poll()` 不再驱动 Vision/Control/Output 的传输。
- 7 项 replay/process 测试扩展为 7 passed，组合 focused 集合 42 passed；新增端到端 fake-port 场景证明 UI 3 秒不 poll 时 Control/Output 仍推进并可恢复读取最新 snapshot。
- 该证据仍是 spawn-safe fake-port，不等于真实 Qt/Host/game 验收；child 真停止后的真实 handle→single rebuild 场景仍开放。

### 2026-10-09 Relay race correction

- `_poll_once` 已由 `_poll_lock` 保护为单一消费者；UI 首次 `poll` 使用 snapshot event 等待，不再与 relay 并发驱动队列。
- 新增并发 reader/relay 回归，port/replay focused 总计 26 passed；真实 child rebuild 和游戏消费仍开放。
- 测试停止边界已改为 `max(seen) <= produced_ticks`，并保留 output apply 与 relay error 断言；竞态测试连续 5 次通过，未发现运行代码重复消费证据。
- 现有 port 生命周期测试已覆盖异步 stall budget、RebuildBundle 原子 commit、旧 future 在 stop→start 后 dispose、旧 handle 不写新 session；因此没有新增裸 Queue 假证据。真实 VisionProcessHandle/Host/Qt/game 仍是明确未覆盖边界。

### 2026-10-09 J10 unified follow contract

- 统一契约已下沉到 `experimental/follow_contract.py`，所有 click/single/dual/dynamic composition 的核心参数固定为 `12/20/80/8/24/.25`。
- 模块化动态路径走 FollowEnginePort/LegacyDynamicFollowRouteController/OutputScheduler；旧页面 click-to-move 与 dual-target 仍走 SimulatedFollowRuntime，但复用同一旧 route/steering/output 组件。
- 新契约 focused test 加入；旧页面迁移到 FollowEnginePort 不在本批强行完成，避免混合生命周期和真实输入边界。
## Final J01–J17 audit (2026-10-09)

`offline_verified`: J01, J02/J03 contract-equivalent, J04/J05, J06/J07/J14, J08/J09, J10, J11/J12, J13/J15. `partial`: J16 (offline relay/control timing only). The combined minimal collection is `106 passed`; compileall and diff-check pass. No real input was used.

Open evidence boundaries are real Vision/Control child termination and rebuild, Qt pause with real workers, Host receipt-to-game-motion correlation, P2-over-P1 long-run behavior, map-scroll replacement continuity, and real IPC/GIL/throughput. These are explicit blockers to a game-consumed/full-map stability claim; they are not hidden by test counts.
