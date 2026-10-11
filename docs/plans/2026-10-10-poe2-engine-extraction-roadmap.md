# PoE2 实验能力进入正式分层：迁移顺序、验收和回退

状态：供用户审阅的执行方案；本轮不实施。上游文档：同日 `poe2-experiment-module-inventory.md`（现状）、`poe2-layered-engine-design.md`（目标）。代码基线 `65dff05`，最新成功实测记录 `5607475`。

## 0. 成功基线和禁止合并的变更

迁移前保存输入、输出和状态三个可对照的基线：相同截图/地图/首帧seed下的 `VisualObservation`；相同帧/目标/receipt时的 `FusionSnapshot`、`MotionIntent`、恢复理由；相同intent下的控制器轴/TTL/neutral/heartbeat时序。最近实测前台连续跟随约3分钟顺畅，seq1294的二帧P2确认使Control完成约69 native单位纠偏；后续版本至少应保有这条闭环。用户已说明会话末尾切走窗口，不能拿切走后的stall当作前台算法失败。

所有阶段遵守：不同时重写算法和搬文件；不调整已成功的角色面积门限、方向基底、碰撞/路径参数、输出时长与恢复阈值；不加入“固定运行时长自动停止”；无目标或已经靠近目标时继续订阅目标和维持会话；手柄与LAN真实动作仅用户显式实机阶段执行。

## 1. 阶段路线

| 阶段 | 交付和实际变化 | 完成门槛 | 回退单位 |
| --- | --- | --- | --- |
| P0 证据冻结 | 固定成功会话、基线commit、最小可回放样本；列出每项阈值和当前装配是否启用 | 输入帧/seed/目标/输出证据带实例、generation、时戳；确认global未装配等真实边界 | 无运行时代码 |
| P1 契约对照 | 在设计/测试中对齐正式 `LocalizationResult`、地图注册、PathFinder、程序输出与实验DTO，记录必要转换 | 不新增第二套通用A*、Host协议或地图源；每个坐标域和时间戳含义明确 | 新DTO/转换适配可独立撤回 |
| P2 底层纯能力 | 只把有稳定语义且确有复用场景的融合/命令积分/不确定度/关联几何纳入core，PoE2参数留上层 | 旧实验仍调用同样运算；输入输出逐项等价；Core import graph不含feature/adapters/UI | 每个纯模块独立回退 |
| P3 应用运行时 | 建立per-role tracking owner、navigation task、recovery request调度与有代次的worker transport；接口替换实验内适配 | worker restart仍持有正确位置/变换/目标；旧代帧/回执拒绝；UI和输出不被慢规划或内存I/O卡住 | 每个runtime边界以flag/工厂切回旧路径，仅迁移期间保留，切换稳定后删除 |
| P4 PoE2业务组合 | 将首帧seed转换、颜色/ROI、地图/内存/手柄映射、leader目标策略装进PoE2 feature composition；实验页调用这一组合 | 点击点、双角色目标、P1↔P2都使用同一导航任务接口；PoE2策略不进入Core/Application；target revision正确 | 一次装配入口切回旧factory |
| P5 正式页面接入 | 正式定位页从同一PoE2 composition获得状态/预览/操作，实验页仅保留探针参数和诊断 | 实验和正式页不能同时持有相同角色Controller lease；开始/停止、页面隐藏、崩溃恢复、手柄归零都有明确owner | 页面入口切回稳定实验/正式旧入口 |
| P6 清理旧链 | 移除不再被生产路径调用的legacy wrapper和实验重复实现；同步CODEBASE/架构文档 | `rg`与CodeGraph证明无生产导入旧入口；所有重点回放与真实手柄回归完成；用户确认正式页体验 | 上一个完整可启动commit |

P2之前不要“把所有文件移动到core”。P3/P4是主要行为风险段；阶段完成必须有可读的差异报告，不以能启动或unit test绿作为唯一通过条件。

## 2. 每层交接条件

### P0/P1：证明契约没有漏掉物理含义

1. 记录 `map_instance`、`generation`、`frame_sequence`、`coordinate_frame_id`、`captured_at_ms`、`accepted_at_ms` 的拥有者；确认截图、墙体位移、两个角色候选和local ROI查询属于同帧。
2. 写“当前功能→正式已有API→是否需新接口”矩阵：`core.localization`、`core.routing.PathFinder`、`core.spatial`、`core.perception`、`ProgramGamepadOutput`，并对Torchlight跟随的异同打标签。
3. 保存同一输入下的控制向量、时长、target revision、视觉接受/拒绝、恢复状态。日志采样只作诊断；等价比较需用独立离线回放录制全量状态。

### P2：纯函数提取

1. 每次只抽一个独立语义，例如 `integrate_command`；保留原调用签名或单一委托壳。禁止改speed标定方式、图色阈值、创新门公式。
2. 同帧及反例测试：颜色污染/大色块、两个角色靠近、角色交换、单候选二帧确认、重复/超时帧、墙体滑动、观察采样迟到。
3. 检查 `core` import/依赖图；纯模块不得导入 PoE2/Qt/Host/进程句柄；PoE2业务profile进入这些函数应通过参数而不是条件分支。

### P3：状态与并发迁移

1. 每角色只有一个position owner，receipt经Control owner裁剪、倒推、融合与重放；Visual worker只产证据；目标策略读取已接受的位置。
2. `VisionProcess`/`ControlProcess` 与 parent supervisor的代次和epoch分开：worker重建时传递可信native位置、最新地图变换、目标版本，舍弃旧屏幕锚点；旧worker队列按代次拒收。
3. 截图队列latest-only；worker忙时丢旧帧但保留同帧证据一致性；日志有界采样、队列丢弃与 `diagnostic_gap` 可见。
4. `MemoryRecovery`和全局恢复异步且有in-flight限制，memory冷却维持当前8000ms；一层不可用只标记不可用，不能无限重复“恢复中”。
5. Output拥有独立线程/Actor和每控制器lease；无移动命令时仍heartbeat；Host write失败只处理output session；stop确保neutral/release，且不能遗留游戏手柄状态。

### P4/P5：业务接入

1. 三种目标来源都生成同一 `NavigationTarget`：固定点击点、角色可信位置、远端同实例位置。远端目标晚到/丢帧须有新鲜度策略；远端人物即使不在本机小地图视角内，也不影响本机两个受控角色定位。
2. 角色位于靠近目标的范围内时输出neutral，但session、目标订阅和heartbeat继续；leader下一次移动时自动重新出发。只有用户显式停止关闭持续跟随。
3. UI只消费只读预览/状态/诊断，放大窗口时地图和marker共用同一缩放坐标；实验参数仍可调，但正式默认冻结成功值，切换配置需显式记录。
4. 页面切换/窗口失焦是独立生命周期条件。设计时不假设失焦会关闭游戏输入，也不将后台stall掩盖；要记录焦点变化、截图新鲜度、控制健康，再选择保持/中性/提示策略。

## 3. 性能预算与验收方法

前台成功会话的采样锚点：Vision `processing_ms` p50约53.74ms、p95约67.82ms；Control `total_ms` p50约6.23ms、p95约56ms；视觉年龄p50约64ms、p95约115ms。它们来自有界采样，并非完整分布。迁移验收首先要求“不比基线持续恶化”：在同一回放、相同主机和日志级别下对比中位数、p95、最大值、帧年龄、队列丢弃和每分钟局部/内存纠偏次数。数值门槛在P0测得完整回放基线后锁定；不能把30FPS设为已达到的事实。

控制worker不得把每帧完整A*、内存读取或Host命名管道请求放在同一长阻塞临界区。输出回执与视觉帧必须可按 `control_tick/target_revision/visual_sequence`串起来。对离线性能回归，目标是相同输入下target到输出的时延分布无显著上升；对真实前台回归，至少覆盖靠近、分开、过门、颜色遮挡、目标持续移动、仅靠预测短时继续、二帧纠偏、Host重arm、双角色同时移动。真实游戏结果需用户主观确认和日志同屏证据。

“暂时看不到图色”不能直接终止会话；“地图坐标落墙”也不能证明游戏中角色陷墙。控制可以依预测与局部自由空间继续，位置不确定度上升并按策略重锚。严格安全输出边界：用户Stop、进程关闭、Controller租约丢失时必须中性化。

## 4. 最需要审查的风险

| 风险 | 触发链 | 迁移阶段的保护 |
| --- | --- | --- |
| 把位置状态分裂到Vision/Control/UI | 三方互相覆盖导致P2越过P1或目标滞后 | P1/P2各一个Control owner；其他方只传证据/只读snapshot |
| 旧变换/旧帧混用 | worker重建、地图滚动、ROI从ring读到不同sequence | `map_instance + generation + captured_at + frame_id`全部校验，重建重算屏幕锚点 |
| 错误颜色被当成身份 | 颜色污染、候选排序变化、角色靠近 | 颜色软评分/几何/面积；远点二帧确认；ROI不能绕过确认 |
| 预测到达即停止 | 执行回执快于视觉，动态目标更新停止 | 到达只进hold，视觉确认保持位置，目标变化继续导航 |
| 输出/规划耦合 | Host慢写或A*阻塞Control和UI | Actor隔离Host；重规划预算与路由缓存；定量记录p95/max |
| 清理过早 | `LegacyDynamicFollowRouteController`仍被当前UI创建 | CodeGraph追调用方，先新接口接管，再删旧实现 |
| 误把历史文档路径当权威 | 旧文档有根级`core`/`gui`路径 | 当前`ARCHITECTURE_GUIDE.md`和源码优先，历史只参考方法 |
| 把切走窗口末尾异常算成前台退化 | 2026-10-09最后数秒Control stall | 标记前后台焦点区间分别度量，保留该异常作为生命周期用例 |

## 5. 每阶段审查包与最终交付

每阶段提交独立Git commit和四件证据：变更边界、调用/依赖图、离线等价/性能对照、未解决风险；同步`CODEBASE.md`与`ITERATION_LOG.md`。P3以后每次都模拟完整 `start→首帧seed→视觉/Control运行→目标变化→恢复→停止`，不能只验证进程活着。最后由用户测试正式页：点击目标、双人同目标、P1/P2互换跟随和长图连续运行；成功后才能标“正式引擎接入完成”。

本轮请用户重点审阅两个决策：是否采用“B：契约先行的纵向切片”；正式跟随页接入是否放在能力抽取完成后（本计划P5）。这是设计选择，并非在本轮启动改造。
