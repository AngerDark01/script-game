# 2026-10-09 03:07–03:08 两次跟随失败：日志诊断

## 范围与结论

本轮只诊断用户反馈时对应的两次会话：03:07:53.211、03:08:31.879。未修改运行代码、重启进程或发送游戏输入。后续03:10会话不混入这次分析。

两次都成功启动并收到首个视觉观测、控制快照。共同故障位于运行阶段的worker进展/恢复链：第一次替换worker三轮，第二次一轮。首个导致进展中断的worker及其原始异常没有持久记录，目前不能宣称已经查出底层根因。

## 首帧和接管前状态

- 地图实例：`P2_7:54BE4D92`。
- 03:07:45.798首帧accepted，配准confidence=0.909898，平均anchor误差0.340701 native。
- 变换：angle=221°，reflect_horizontal=True，scale=0.903。
- 内存读取2508.296ms、配准1079.356ms、首帧计算总3790.718ms。
- 接管前双人视觉约21.8–22.1FPS，两角色均可见，wall quality=1，dropped_results=0。
- 旧视觉worker的stop_deferred在03:07:52.467出现，但03:07:52.470已finished；不能据此声称两个视觉worker持续互相干扰。

## 两次时间线

| 项目 | 第一次 | 第二次 |
| --- | --- | --- |
| 启动请求 | 03:07:52.469 | 03:08:31.314 |
| 启动完成 | 03:07:53.211，742.734ms | 03:08:31.879，563.959ms |
| 首控制快照 | 03:07:53.404，约188ms | 03:08:32.011，约140ms |
| 首视觉观测 | 03:07:53.775，约563ms | 03:08:32.385，约515ms |
| 第1轮旧Vision dispose→新Vision start | 03:07:57.714→03:07:58.442 | 03:08:40.308→03:08:40.991 |
| 第2轮 | 03:08:00.994→03:08:01.609 | 无 |
| 第3轮 | 03:08:07.791→03:08:08.449 | 无 |
| 页面stop完成 | 03:08:21.041，reason=requested | 03:08:45.235，reason=requested |

dispose→start间隔约615–728ms，只包含可见生命周期边界，不是全部中断耗时。首帧和初始化没有在这两次运行中被反复执行。

## 手柄证据

只读Host日志：`C:/Users/12074/AppData/Local/AutoModules/Workbench/logs/virtual-gamepad-host.log`。

- 第一次运行窗口：没有controller=2的非零左摇杆/按钮SubmitReport记录。零输入不会被该日志打印，不能说从未建立会话或从未提交零报告。
- 第二次：03:08:37.883首个P2报告，axes=(14121,5234)；03:08:40.353最后一个SubmitReport，03:08:40.354对应提交完成，约2.47秒、157个SubmitReport，backendConnected=True。
- 第二次首个非零输入距启动约6秒，符合已配置输出闸门。其末段与03:08:40.308 worker重建相邻；异步回中允许少量报告在请求后才完成，现有证据不足以判定为迟到写入缺陷。
- 第二次末段出现约(±2969,±2315)的相反方向小输入。缺角色位置/目标/intents/receipt关联记录，无法判断是正常路线调整、恢复试探还是控制振荡；不将其认定为根因。
- Host提交不等于游戏消费，报告没有当前跟随session/generation标识，不能单凭Host数据证明真实人物位移。
- 03:07 GUI session的runtime.log没有此前的heartbeat错误风暴。03:10会话的session expired属于另一次运行，不能套用。

## 源码确认的处理链与缺口

`FollowEnginePort.poll()`刷新liveness/stall并读取Vision和Control事件。worker error事件包含error/traceback_text，但poll只存last_error，没有把原始error/traceback持久化。

`_check_worker_stall()`：首snapshot前使用10秒启动门，首snapshot后使用2秒无进展门；任一worker进展时间戳超时会标记stalled。原始last_error仅在包含queue_closed时保留，其他原始故障可被worker_stall覆盖。

触发后先`_neutralize_output()`，再后台`_rebuild_components()`停止并dispose两个worker，重新构造并启动Control/Vision，重放目标，重置进展时间戳。正常重建没有记录触发worker、原始原因、进展年龄或exitcode。因此Vision dispose既不是首帧拒绝，也不能证明Vision是故障起点。

最大重建次数为3，成功重建未重置累计attempts。第一次已观察到三轮；若此后再stall，就可能进入worker_rebuild_budget_exhausted。但本次没有持久记录该状态，不能说确实发生了预算耗尽。

页面`_poll_modular_follow_engine()`只在没有snapshot时显示diagnostics.last_error；有snapshot时优先显示snapshot.recovery_state/reason。诊断last_error没有落盘，旧snapshot也可能遮住新的worker故障状态。

当前证据链：

```text
启动成功、收到首结果
    → worker进展被判异常（原始触发未记录）
    → 主控请求手柄回中
    → 停止/替换Vision与Control
    → 恢复结果产出或再次无进展
    → 第一轮测试重复三次，第二轮重复一次
```

这里的worker替换和视觉配准重定位是两类操作。不能把dispose日志解释为频繁全局地图匹配。

## 需要优先补足的证据与修复边界

1. 原始worker error/traceback及PID/exitcode，必须在写last_error前记录，保留first_fault，不能被stall摘要覆盖。
2. stall分类记录每个worker的last_progress年龄、sequence、tick阶段/耗时、是否活着、parent poll间隔；区分worker异常、长计算、IPC结果缺失和父侧转发延迟。
3. rebuild begin/success/failure/budget-exhausted记录同一session、epoch、attempt与句柄身份，区分故障组件与被连带替换组件。
4. 输出按intent→actor→Host receipt关联，记录回中与恢复非零输出，避免用first_output_apply冒充真实执行。
5. 状态改变立即持久记录；常态timing抽样，不每33ms打印全文，以免日志再次造成卡顿。

在这些证据补齐前，直接降低定位阈值、延长启动等待或归因于窗口焦点，都不能解释当前反复worker替换。下一步应先抓住最初进展中断的真实原因，再决定修运行逻辑还是进展判定/恢复策略。

## 证据索引

- `data/logs/poe2_live_terrain.log`，818132–818220行覆盖首帧和两次会话。
- `data/logs/runtime.log`，12428–12460行对应GUI PID38484。
- `experimental/follow_engine/engine.py`：poll、_check_worker_stall、_rebuild_components、_refresh_worker_liveness。
- `ui/modes/poe2_live_terrain/capture_test_page.py`：_poll_modular_follow_engine。
- `services/virtual_gamepad/host/src/VirtualGamepadHost/Driver/ViGEmXInputBackend.cs`：Submit，只打印非零buttons/left axes。
- 未找到这两次测试的异常截图；已有occlusion数据最后更新10月7日，不能作为本次画面。
