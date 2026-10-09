# 19:16 后跟随方案：纠偏与可观测性收口

## Goal
把已实现的双角色视觉纠偏接入可追溯的父进程日志，并修复页面观测故障；让下一次实测能够定位候选、融合、恢复、目标和输出边界。

## Architecture Overview
Vision/Control 通过已有 DTO 回传有界诊断，父 Relay 负责落盘并通过现有 logger 进入 UI。目标版本与 tick 是诊断元数据，不参与运动策略。正常事件采样、异常变化记录；不引入逐帧截图或同步文件 I/O 到子进程。

## Tech Stack
Python multiprocessing/spawn、dataclasses、Qt UI、现有 logging；解释器 D:/ACloud/.venv/Scripts/python.exe。

## 任务及验收

| ID | 目标 | 文件（均以仓库根为基准） | 验收 |
|---|---|---|---|
| E1 | 修正上轮证据等级，隔离 preview 异常，修复倒计时测试替身 | src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py；tests/poe2_live_terrain/test_follow_engine_page_startup.py | 渲染抛异常仍刷新 countdown/status；真实页面方法存在，不能把 SimpleNamespace 缺方法称为实机崩溃 |
| E2 | 父进程记录 Vision 候选/面积/确认/耗时 | follow_engine/engine.py；新增 follow_engine/diagnostic_events.py（完整前缀为 src/auto_modules/features/poe2/live_terrain/experimental/） | DTO 过队列后父 logger 能记录；正常采样，异常短事件保留有界历史 |
| E3 | 记录 visual fusion、local 与 memory 的角色/原因/结果 | follow_engine/control/follow_control_process.py；diagnostic_events.py | 日志包含帧号、角色、创新距离、门限、修正前后、submit 实际是否成功；不能只记录 policy 意图 |
| E4 | target revision→tick→intent→receipt 串联 | follow_engine/contracts.py；execution_feedback.py；control/follow_control_process.py；control/snapshot_output.py | 非零/hold/目标变化均能关联；元数据不改变向量、TTL 与积分；只声称 transport acceptance |
| E5 | 候选规则与纠偏端到端复核 | multiplayer_localization/marker_association.py；follow_engine/vision/local_roi_search.py；vision/dual_observation_processor.py；相关 focused tests | 明确单候选确认的作用域、角色身份、面积过滤是否在 ROI 生效、确认后是否被 Control 二次拒绝；发现遗漏立即记录和定向修复 |
| E6 | 文档同步与验证 | CODEBASE.md；ITERATION_LOG.md；docs/POE2_FOLLOW_ROLLBACK_CHECKPOINT.md；本文件 | focused checks + compile + diff-check，列出实机待验条件 |

执行顺序：E1→E2→E3→E4→E5→E6。每个目标先读调用链，新增定向失败用例，再改实现；不得用全量通过替代实机证据。

## 运行与验证命令
`D:/ACloud/.venv/Scripts/python.exe -m pytest -q tests/poe2_live_terrain/test_follow_engine_page_startup.py`

后续按变更运行 association/control/port/snapshot_output/vision focused 文件；`D:/ACloud/.venv/Scripts/python.exe -m compileall -q src tests` 与 `git diff --check`。

## 边界与待实测
父 Relay 在 UI timer 外运行，不要求本轮重写成进程直连。GlobalRecovery 未装配的状态须明示，不能因存在类就声明可用。真实 Host→游戏位移、FPS、地图滚动和长时间颜色污染待用户实测；没有时间硬停止。工作树有大量既有修改，保留它们，不整体回退或把全部修改提交到一个混合提交。

## 当前断点
E1 已完成，12 项通过。修订：旧失败为测试替身缺方法，并不证明真实页面启动失败；新增坏预览测试确认并修复渲染异常阻断状态更新。页面日志 sequence 字段已修正。
E2/E3 采用有界诊断历史随现有 DTO 传输、父进程去重落盘；latest-only 丢弃中间快照不会立即丢失短事件，超过容量须显示诊断 gap。下一步实现此通道。

## 实施结果

E1完成；E2/E3完成有界历史和父日志汇聚，Windows spawn事件携带诊断已验证。E4完成目标版本/tick/frame到receipt关联与后续视觉位移日志。E5补齐双角色独立确认、确认confidence与Control校正、ROI面积和身份过滤，并阻止pending经ROI绕过；重复时间戳和>1000ms间隔不构成两帧确认。E6 CODEBASE/断点同步。

组合验证111 passed；随后增加pending→ROI绕过与确认时间边界，相关33 passed；编译和diff-check通过。无真实游戏/Host输入。完整地图性能、身份hint默认配置、48阈值在不同缩放上的适用性待实测。

### 下次日志检索
搜索 `step=follow_engine.evidence`，按stream/generation/role筛选：stage=vision、fusion、position_correction、local、recovery、memory、target、output_receipt、receipt_consumed、observed_motion。日志reason解释分支，details包括帧号/坐标/门限/耗时/控制tick/目标版本。diagnostic_gap表示有界历史溢出；正常同原因每秒采样。control_decision_observed保留角色target/source/misses/intent；不再因duration每tick变化强制打印。

### 上轮结论校正
测试替身缺方法不是实机崩溃证据；父relay已经脱离UI timer，留在父进程不等于未解耦；全局恢复未装配须显示不可用，不能把已有类或policy意图当执行完成。本轮不另起大架构重写。
