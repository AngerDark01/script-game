# PoE2 双通道跟随引擎验收清单

更新时间：2026-10-07  
当前代码基线：`ca56dd9 docs(follow-engine): record final offline verification`

## 1. 当前交付边界

本阶段已经完成 M0–M7 的离线引擎基础设施：

- latest-only 视觉帧通道和 Windows spawn-safe VisionProcess；
- worker supervisor 的 generation 隔离、有界重启和退避终态；
- 独立控制进程、预测/融合、路径输出和 Host heartbeat 调度；
- 新帧优先的局部 ROI 恢复；
- 带 generation、地图实例和冷却的异步内存快速重锚；
- 单 generation 全局恢复 single-flight；
- 动态跟随异常只进入预测/保持/恢复，不自动释放 session；
- `FollowEnginePort`、页面 adapter、阶段耗时和离线 replay runner；
- 页面 adapter 的显式迁移桥接和控制进程 `runtime_factory` 注入；
- 当前 PoE2/页面离线聚焦测试 `618 passed`。

当前明确未完成：

1. `capture_test_page.py` 默认入口仍使用旧页面编排；新入口已具备注入式 feature flag，但未默认开启；
2. 真实 PoE2 内存 source 尚未注入新 `MemoryRecoveryBackend`；
3. 真实 VirtualGamepad/Host 尚未由新 port 接管；
4. 本文之外不允许把离线通过描述成实机通过。

## 2. 离线验收门槛

每次提交后必须执行：

```text
pytest -q tests/poe2_live_terrain
python -m compileall -q src/auto_modules/features/poe2/live_terrain/experimental/follow_engine
git diff --check
```

必须满足：

- 全部测试通过；
- latest-only 槽容量固定，无无界图片队列；
- 视觉暂失、局部失败、内存失败、全局失败、Host session 失效和地图变化均不自动 stop；
- 只有显式 `FollowEnginePort.stop(reason="user")` 释放动态输出租约；
- 迟到 generation、逆序 sequence、旧 map instance 结果不能覆盖新会话；
- 全局恢复同一 generation 在结果被 poll 前最多一个任务；
- `StageTiming` 的所有阶段值有限、非负，且控制 tick 不等待 memory/global future；
- replay manifest `real_input_allowed=false`，离线 runner 不连接游戏、内存或 Host。

## 3. 真实输入 opt-in 前检查

真实 PoE2 测试必须由用户明确开启，并逐项确认：

1. 游戏窗口和 controller ownership 已确认；
2. Host 支持当前 `program.heartbeat` 和 session rearm 协议；
3. 当前地图实例、首帧 transform、角色身份均已记录；
4. 新旧输出链只有一个拥有 controller lease；
5. 页面 adapter 已由 fake composition 通过；注入式 feature flag 已隔离旧入口，但真实 composition 尚未接入；
6. 日志包含 capture、wall、marker、association、local、prediction、memory、global、route、output、heartbeat、UI drain、total 各阶段耗时；
7. 用户知道测试期间可能发送手柄输入，并在游戏内准备安全位置。

## 4. 实机分级顺序

不允许直接从完整地图开始。按以下顺序逐级通过：

| 级别 | 场景 | 通过条件 |
|---|---|---|
| R1 | 双人静止、角色分离 | 首帧身份/地图一致，session 保持 |
| R2 | P1 单方向移动 | P2 跟随，视觉正常时不触发恢复 |
| R3 | P1 转向、短暂停留 | 目标变化不释放 session，进入范围只中立保持 |
| R4 | 单帧/短时视觉失配 | 最新帧局部重捕获优先，下一帧恢复 |
| R5 | 颜色污染/角色靠近 | 几何关联不交换身份，预测只作短时补充 |
| R6 | 内存快速重锚 | 只读一次双人位置，复用 transform，控制 tick 不阻塞 |
| R7 | Host session 失效 | heartbeat/rearm 恢复当前 controller，不重新创建跟随任务 |
| R8 | 门/窄道/复杂墙体 | 路径不因单次 `no_safe_route` 停机，能进入恢复/探索 |
| R9 | 地图实例变化 | 旧结果丢弃，异步全局恢复单飞，完成后原地恢复 |
| R10 | 完整地图 | 无时间硬限制；只有用户停止才结束 |

每一级都要保存：session id、generation、map instance、阶段耗时、恢复层级、视觉年龄、不确定度、Host 状态和 evidence 图片。

## 5. 回滚边界

- M0–M3：回滚到 `527d946` 不影响旧页面；
- M4：回滚到 `f858d84` 可去掉恢复 backend 接入，但保留旧策略测试；
- M5：默认页面切换前必须保留 feature flag，旧页面和新 port 不得同时拥有 output lease；
- M6–M7：只回滚代码，不删除用户运行 evidence；
- 任何真实输入异常先停止用户侧实验，再保留日志和 evidence，禁止用运行时文件覆盖代码判断。

## 6. 本次审计结论

离线引擎链路和页面的可回滚桥接已通过测试；真实 capture/memory/Host composition 以及默认切换仍是下一项独立工作，不能在没有用户明确启动测试的情况下自动进行。
