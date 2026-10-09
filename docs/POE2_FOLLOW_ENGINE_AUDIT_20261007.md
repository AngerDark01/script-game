# PoE2 Follow Engine 全面审查报告

审查日期：2026-10-07  
范围：最新双通道 follow-engine 重构、页面桥接、视觉/预测/恢复/输出链路、导入依赖和离线测试。  
安全边界：本轮只读审查和离线小实验；未启动游戏、未读取实时内存、未发送手柄/键鼠输入。

## 1. 结论摘要

当前代码可以作为离线架构原型继续开发，但不能称为“已完成实机迁移”。新引擎的契约、代际门控、latest-only 帧结构、控制进程骨架、恢复策略和页面 opt-in 桥接已经存在；真实 PoE2 截图、首帧注册、内存快速锚定、Host 输出和地图寻路仍未装配到新 port，页面默认入口仍是旧链路。

本次审查发现两个已经可以离线复现的行为缺陷：

1. 视觉候选被融合器拒绝后，控制 tick 仍可能把该候选当成 fresh/visible，清零 miss 并回到 `tracking`。
2. 预测位置先进入到达半径时，直线路由会发送中立意图，即使视觉从未确认人物真正到达。

这两个缺陷正好对应历史上的“位置漂移后仍继续执行”和“跑一段后停住”。必须在接入真实页面前修复并加回归测试。

## 2. 按优先级的问题清单

### P0：阻塞正式实机使用

| 编号 | 证据位置 | 问题与触发 | 影响 | 建议 |
|---|---|---|---|---|
| P0-1 | 已修复部分：`vision/vision_process.py::VisionProcessEvent`、`engine.py::FollowEnginePort.poll`、`control/follow_control_process.py::send_visual` | VisionProcess 现在将同一序列的 `CapturedFrame` 传到 control runtime，局部搜索不再必然拿到 observation 假对象；但 payload 仍经 Queue pickle，尚未切换 `SharedFrameRing`，真实 local matcher 也未装配。 | 真实帧断链已关闭；大帧/高频处理仍有复制延迟，实机 ROI 成功仍未证明。 | 下一步让 event 只携带 slot metadata，control 通过 shared ring 读取最新 bytes，并接入 PoE2 local matcher。 |
| P0-2 | `control/route_controller.py:16-41`、`follow_control_process.py:30,339-350` | 实际路由是 `StraightLineRouteController`，只算目标直线，没有墙体、门、窄道、局部 steering。 | 无法满足正式导航避障、绕墙和通过窄门的要求；离线“能移动”不等于可导航。 | 注入地图感知 PathFinder/steering 接口；先纯函数验证目标投影、可行走邻域和短脉冲脱困，再接控制进程。 |
| P0-3 | `ui/modes/poe2_live_terrain/capture_test_page.py:1555-1593`、`experimental/follow_engine` 各 port | 页面新入口只有显式注入时启用；真实 capture、首帧 transform seed、warm memory source、真实 Host output 尚未组合。 | 现有实机测试仍主要验证 legacy 链路；不能用离线通过结果替代用户可用性。 | 完成 spawn-safe composition factory，默认仍保持旧入口，按 R1 静止双人→R2 单帧→R3 视觉丢失→R4 内存锚点逐级 opt-in。 |

### P1：高概率造成漂移、卡住、崩溃或资源泄漏

| 编号 | 证据位置 | 问题与触发 | 影响 | 建议 |
|---|---|---|---|---|
| P1-1 | `control/follow_control_process.py:130-157,277-284` | `fuse_observation` 拒绝候选时不更新 evidence；但 `tick` 仍用 `visual_item.visible` + 旧 evidence age 计算 `visible`。 | 被拒绝的远跳候选可清零 miss 并报告 `tracking/visual_match`，压制 local/memory recovery。 | 在 observation 中显式记录 `accepted`/innovation；拒绝候选不得刷新健康状态，状态年龄必须来自最近 accepted evidence。 |
| P1-2 | `follow_control_process.py:255-275,339-350`、`route_controller.py:29-41` | 命令里程计以固定 `magnitude*100` 预测，路由再按预测位置判断到达；没有视觉确认门。 | 预测先到达会发中立脉冲；真实角色未到达时停止输出，形成历史 `target_arrival_unconfirmed`。 | 动态跟随禁止“预测即 arrived”；至少需要新鲜可信视觉/内存确认或连续稳定窗口；未确认时保持低幅校正，不释放 session。速度应来自校准器而非常量。 |
| P1-3 | `vision/vision_process.py:64-67` | stale sequence 直接 `continue`，跳过 interval wait。 | 重复 sequence provider 时视觉 worker CPU busy-loop。 | stale 也必须执行统一节拍；最好统计丢弃计数并在 provider 连续重复时降频/告警。 |
| P1-4 | `vision/vision_process.py:97-103, VisionProcessHandle.stop():153-163`、`capture_adapter.py:89-95` | worker finally 和 handle stop 没有调用 `capture.close()`/`processor.close()`。 | MSS/句柄/线程局部资源可能泄漏，重启后卡死或占用升高。 | 明确 owner；worker finally 关闭子进程资源，父侧仅关闭未启动/启动失败对象，增加 close 幂等测试。 |
| P1-5 | `follow_control_process.py:396-398`、`recovery/memory_recovery.py:87-89`、`recovery/global_recovery.py:78-80` | runtime stop 只改 session 标志，不关闭 recovery executor。 | 全局/内存任务可在旧 session 后继续运行，阻塞退出或污染下次会话。 | `FollowControlRuntime.close()` 关闭 backend；stop/异常/进程 finally 都调用且 generation 校验结果。 |
| P1-6 | `VisionProcessHandle.start()`、`FollowControlProcessHandle.start()`、事件/命令队列 | 同一个 handle 重启不清空队列，也不 reset processor/runtime；旧 error/stop/sequence 可留在新会话。 | 重启后立即停止、旧事件覆盖新 snapshot、旧帧被 sequence gate 拒绝。 | start 前 drain queues、重新构造 spawn-safe capture/processor/runtime；或强制每次新建 handle，禁止复用。 |
| P1-7 | `follow_control_process.py:552-560` | 队列满时只丢一次，再次 `put_nowait` 仍可能 `queue.Full`；visual/target/stop 共用队列。 | 高负载下 UI 抛异常；目标更新可能被视觉帧挤掉，stop 也可能丢失。 | 采用分类型 latest-only 槽：visual/target 合并，stop 使用独立可靠通道；put 失败需结构化诊断而不是向 Qt 抛。 |
| P1-8 | `control/output_scheduler.py:108-122` | `heartbeat()` 返回 `False` 被计为成功；异常只计数，不 rearm；apply 与 heartbeat 共用锁。 | Host lease 失效但调度器认为心跳正常；慢 write/恢复会阻塞租约续期。 | 明确 `False` 为失败，独立保活线程/端口 lease；失败进入 bounded rearm，不释放动态跟随 session。 |
| P1-9 | `engine.py:116-151`、`process_supervisor.py:73-93` | port 现在暴露 vision/control `worker_state`，control error/stopped 不再重复提交旧 snapshot；但 supervisor 无事件时仍不检查 `is_alive()`，也未自动组合到 page port。 | native crash/静默退出仍可能只停留在诊断状态，页面不会自动重启 worker。 | 让 supervisor 接管 port 生命周期；poll 无事件也检查存活，按 generation 发布 terminal/restart 状态。 |
| P1-10 | `control_process_entry:454-464`、`FollowEnginePort.start():84-97` | 缺字段命令会抛异常杀 control worker；start 回滚中某个 stop 抛错可能遮蔽原始异常/中断后续清理。 | malformed/迟到消息导致跟随突然结束，启动失败留下半活跃资源。 | command DTO 校验、未知/非法命令变成 error event 不杀进程；启动回滚使用逐项 finally 并保留原始异常。 |
| P1-11 | `follow_control_process.py:178-205,286-337` | memory/global 成功标记是本 tick 全局布尔值；一个角色成功可令另一个角色走 recovered 分支；map/transform signal 在 tick 末尾直接 reset。 | 双人一人恢复时另一人状态被错误改善；地图失效信号可能只持续一个 tick。 | 恢复结果按 role 绑定，signal 直到对应新证据确认后清除；snapshot 携带 instance/transform generation。 |
| P1-12 | `vision/dual_observation_processor.py` | transform 缺省时隐式 screen→native；首帧未初始化 wall shape/time；shape mismatch 仍继续用旧 transform 转 marker；missing 角色不累计 wall shift；native velocity 再 forward transform；不确定度未按 scale 换算。 | 非 1 比例、相机位移、地图形状变化时关联门和速度估计会漂移。 | 首帧必须显式 seed；shape mismatch 只输出降级 observation；统一 screen/native 正逆变换和 uncertainty 单位。 |

### P2：性能、可维护性和测试覆盖风险

| 编号 | 证据 | 影响/建议 |
|---|---|---|
| P2-1 | `capture_adapter.py:69-87`、`dual_observation_processor.py:154-176` | 同一 VisionProcess 内 BGR→PNG/JPEG→decode，增加 CPU 和延迟。若共享内存槽可行，优先传只读 frame slot；编码只用于跨进程边界或回放。 |
| P2-2 | Vision interval 在处理结束后等待固定间隔 | 实际周期为处理耗时+33ms，无法达到 30 FPS；应使用 deadline scheduling，并丢弃旧帧而不是排队。 |
| P2-3 | `wall_extractor` 默认 bright-gray 阈值 | 会把颜色标记/高亮区域混入墙 mask；必须接入 PoE2 combined wall mask，并单测颜色污染、窄道和门。 |
| P2-4 | 现有压力测试只验证结构与 fake observation | `503/516/518/523` 等离线通过不能代表真实截图耗时、Host lease、游戏消费手柄；补 stage timing 分布、drop ratio、p95/p99 和长时 soak。 |
| P2-5 | `pyproject.toml` 无运行时依赖声明，根依赖在 `requirements.txt`，打包根闭包在 lock | 裸环境 `import auto_modules` 需 `PYTHONPATH=src;.`；打包测试还要求已安装 `PyDirectInput`/OCR。发布前应明确安装入口或让测试按 lock 创建隔离环境，不要把 `pip check` 当项目依赖完整性证明。 |

## 3. 已完成但边界明确的能力

- M0–M1：离线 replay、不可变 DTO、generation/sequence/map-instance 校验、命令里程计、融合和恢复策略。
- M2：latest-only 帧结构、spawn-safe VisionProcess、墙体/marker/双人关联/ROI 组件和组合器。
- M3–M6：控制进程骨架、输出调度器、页面 adapter、阶段计时、压力和重复启停回归、bounded supervisor。
- M7–M8：离线回放验收文档和 R1–R10 实机验收边界。
- 页面桥接是显式 opt-in，默认旧链路仍在；这是当前安全边界，不是遗漏的默认迁移。

## 4. 尚未实现的功能

1. 真实 PoE2 screenshot provider → capture adapter → VisionProcess → `VisualObservation` 的正式组合。
2. 首帧 native transform/墙体 seed、双人真实 marker profile 和地图实例切换处理。
3. P1/P2 真实 Host output、lease 心跳和游戏实际消费的证据链。
4. 地图感知 PathFinder、目标点可行走投影、门/窄道 steering、卡墙后的短脉冲脱困。
5. 视觉/预测独立通道的真实并行融合；当前控制侧仍在 tick 中顺序执行恢复与路由。
6. 局部 ROI 结果在跨进程链路中的真实帧来源和 score 反馈闭环。

## 5. 推荐修复顺序

### 批次 A：先修离线可复现的正确性

- 增加 observation acceptance/innovation 字段，修复 rejected candidate 健康误判。
- 动态跟随移除预测到达终止语义，改为 confirmed hold；静态定点另设明确到达策略。
- 速度由注入的校准器/实际位移更新，不再写死 `magnitude * 100`。
- command/target/visual DTO 加 generation/sequence，队列改成分类型 latest-only。

### 批次 B：生命周期和输出可靠性

- 资源 close、recovery executor close、重启队列清空和 fresh handle 策略。
- heartbeat `False`/异常统一 rearm，worker error/stopped 可见并触发 bounded restart。
- 为 malformed command、stale result、半启动回滚补回归测试。

### 批次 C：真实视觉和地图组合

- 共享帧槽/ROI result 契约；PoE2 combined wall mask；首帧 seed；地图感知路径与局部 steering。
- 完成离线历史图像回放的 p50/p95/p99 和长时间丢帧测试。

### 批次 D：用户授权的实机验收

R1 静止双人首帧 → R2 小步移动 → R3 单角色短时失配 → R4 局部 ROI → R5 内存低频锚点 → R6 Host session 失效重建 → R7 门/窄道 → R8 长图 soak。每阶段只开启一项新能力并保留 legacy 回滚开关。

## 6. 验证记录

- 全仓静态导入枚举：541 个模块，无导入异常（使用 `PYTHONPATH=src;.`）。
- `pip check`：通过；但它只检查当前已安装发行包，不检查项目 requirements 和打包 lock 的一致性。
- 全量回归此前出现 `2 failed, 1209 passed, 2 skipped, 10 subtests passed`；失败包括本机未安装 `pydirectinput` 的打包闭包测试和一个单独重跑可通过的时间敏感 Qt 用例。随后 follow-engine 修复后的 PoE2 专项为 `528 passed`，计数随新增测试变化；这仍是离线契约/回放结果，不是实机验收。
- 本轮单独重跑 `test_profile_apply_failure_retries_on_backoff_and_clears_after_full_success`：1 passed。
- compileall/diff check：此前均通过。
- 本轮未修改运行源码、未启动游戏、未读实时内存、未发送真实输入。
