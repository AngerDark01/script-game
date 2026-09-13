# 通用设备互联与事件执行：开发计划

## Goal

从已有实现提取可组合的设备互联能力，让 B 稳定连接并控制 A/C 的独立事件和 Controller 1/2，同时保持本机键鼠映射正常工作。

## Architecture Overview

依据：[2026-09-13 源码审查与能力拆分](2026-09-13-device-link-capability-architecture-review.md)。用户已认可拆分方向；本文件用于后续逐项开发。当前仅形成规划，未修改生产代码、启动联调或打包。

保留现有身份、配对认证、TLS/UDP、输入状态合并及 Xbox 后端。按以下依赖自底向上改造：

```text
身份 / 配对 / 安全传输
          ↓
每设备连接管理 + 能力授权 + 消息分发
          ↓
事件命令 / 目录同步 / 手柄同步 / 位置共享适配器
          ↓
事件仓库与编译 → 触发路由 → 统一执行 → 既有 Xbox 输出
          ↑
工作台装配与配置、状态、日志
```

连接与事件不得相互持有业务生命周期；事件创建者、触发者、执行设备分别建模。模块可以在同一进程中运行，不增加第二套驱动、网络引擎或宏执行器。

## Tech Stack

- Windows 10/11 x64；现有统一 EXE 启动入口。
- C# / .NET 8，当前项目 SDK `8.0.424`；通用互联库目标 `net8.0`，Windows Host 与相关测试沿用 `net8.0-windows`。
- LiteNetLib `2.1.4`、现有 TLS 和加密实现；保留 ProtectedData `8.0.0` 的 Windows 身份存储适配。
- Python `3.12.10`、PySide6 `6.10.1`；现有 Python 环境、依赖锁和 pytest/unittest。
- Xbox 沿用 Nefarius.ViGEm.Client `1.21.256` 和既有官方 ViGEmBus 安装流程。
- 离线包继续使用 `distribution/build.py` 与 Inno Setup，不在本次重构升级依赖。

## 1. 范围、默认策略与非目标

本次交付：多设备连接隔离、独立能力开关、双向目录共享、跨设备事件触发、多目标执行、事件时间语义一致、键鼠映射共存、逐阶段诊断与安装包。

位置共享仅保持已有适配器兼容与消息不被抢走；不开发新定位、跟随、碰撞恢复算法，不增加技能画面识别。既有 `core/events/ARCHITECTURE.md` 中感知/导航 EventCoordinator 体系保持其职责。

落地采用以下明确默认值，避免执行时临时猜测：

| 项目 | 本版策略 |
| --- | --- |
| 配对与权限 | 配对只建立信任；事件发送、接收、目录共享、手柄同步分别授权 |
| 连接 | 已连接再次连接返回现状；连接中再次请求复用任务；显式重连才替换会话 |
| 多设备 | 按稳定 deviceId 路由；广播展开为触发当刻已连接且已授权的设备，不为后来上线设备补发 |
| 事件所有权 | `(ownerDeviceId, eventId)` 是唯一键；本机编辑本机定义，远端只读；复制生成新身份 |
| 目录转发 | 只直接同步创建者自己的定义；B 触发 A 创建的事件可控制 A，B 自建事件也可控制 A；第三方目录转发不在本版范围 |
| 版本 | 一次请求指定 revision/hash；运行实例固定快照，更新不改变正在执行的动作 |
| 热键规则 | 只属于本机；共享事件不覆盖别台设备的热键；同键可路由多个事件/目标 |
| 重复触发 | 网络同 requestId 去重；用户再次按键产生新 requestId，默认只重启同一来源、同一规则、同一事件、同一目标的实例 |
| 停止 | 按 instanceId 或来源+规则范围停止；普通远端停止不能清空本机或第三方输入 |
| 断连 | 默认停止该远端会话的实例并释放其贡献；重连不自动恢复旧实例，需要新触发 |
| 循环 | 新版定义支持直到显式停止；可选次数/总时长上限，先达到者结束；工作台关闭和紧急停止仍能清理 |
| 间隔 | 频率为“按下到下次按下”；`wait` 为上一步结束后的空闲时长；界面明确标注 |
| 并行/顺序 | 支持顺序中并行、并行分支内顺序；组合深度有界，禁止引用环或无限递归 |
| 输入共存 | 默认沿用已有按钮 OR、轴合并规则；事件结束只移除自己的来源；不在本次暗改轴优先级 |
| 时钟 | 复用现有 remainingMs + challenge 新鲜度思路；事件专用新鲜度不再强制依赖 UDP；不直接比较跨机单调时钟 |
| 执行证据 | 队列成功≠远端接受≠驱动提交；本版不声称通过画面确认游戏动作 |

兼容注意：旧顶层 continuous 当前表现类似频率动作；旧定义迁移需保持历史输出节奏并标记为兼容语义。新版 continuous 才统一为持续按住。禁止静默改变用户已有宏。

### 1.1 一对多广播、多控制器与并发隔离：强制验收

用户追加约束：多设备连接、事件广播和同时控制 Controller 1/2 不能互相干扰，尤其不能因一个目标成功而短路掉其余目标。本节属于发布门槛，落实到 T04、T12–T14、T22–T24、T29、T31；保持原 32 个任务编号。

一次 B 广播到 A/C 的两个控制器，应形成以下四个目标，而不是一个含糊的“远端成功”：

| 请求 | 目标键 | 独立记录 |
| --- | --- | --- |
| request-001 | `(device-a, 1)` | 受理、实例、输入贡献、释放、回执 |
| request-001 | `(device-a, 2)` | 受理、实例、输入贡献、释放、回执 |
| request-001 | `(device-c, 1)` | 受理、实例、输入贡献、释放、回执 |
| request-001 | `(device-c, 2)` | 受理、实例、输入贡献、释放、回执 |

**目标展开与广播：**

- 目标键必须包含 deviceId 和 controllerId。A 的 Controller 1 与 C 的 Controller 1 是两个目标，不能用单个 controllerId 索引跨设备状态。
- 广播为发送端向已选设备逐一投递，接收端只执行发给本机的目标，不再次广播，也不把远端执行反向当成本机热键触发。禁止收到事件后形成 A↔B↔C 回声循环。
- 显式目标和广播中重复出现的同一目标，只在同一次请求内去重；不同用户触发请求不能因事件名称相同而被去重。
- 先登记全部目标，再独立入队、调度、汇总。禁止在有副作用的执行路径使用 `any(start(...))`、`all(start(...))` 或第一个成功后的 return。必须分别验证“1 成功”和“1 失败”时 2 都被处理。
- 设备之间使用独立有界队列和发送任务；不能等待 A 连接、超时或执行完成后才向 C 投递。同一设备的请求顺序单独维护，避免不受控并发造成启停乱序。
- 多目标采用逐目标完成语义，不做全有或全无事务。A 成功/C 失败时报告部分成功，不撤销 A、不漏报 C，也不重试已经成功的目标。
- 去重分成两层：同设备完整消息重复可复用已登记的结果；实际执行去重键包含来源会话、requestId、目标设备和 controllerId。Controller 1 完成登记不能把同请求的 Controller 2 当作重复丢弃；重试返回或继续已登记目标的状态，不重新启动成功实例。

**顺序、停止与输入合并：**

- 同一来源/规则/目标的 start、restart、stop 带可核对的代次。停止或重启后迟到的旧 start/state/clear 不能复活旧实例，也不能清掉新实例；取消标记与去重缓存有界且覆盖有效重试窗口。
- 停止使用原始请求的目标快照或明确 instanceId 列表，不重新按“当前在线广播列表”计算范围。已离线目标标注无法确认远端停止，接收端通过会话失效清理；重连不补发旧 start。
- 同一控制器允许本机映射与多个事件贡献状态，由既有合并模块统一提交，禁止每个事件直接覆盖整个控制器快照。事件 E1 松开 X 时，只要 E2 或本机仍按 X，最终 X 应保持按下；最后一个来源释放后才松开。
- Controller 1 与 2 的计时、取消、TTL 和贡献状态独立；暂停/异常/释放 1 不得清空 2。每个 report 的输入快照应一致，不允许状态合并与取消交错造成半更新。
- 相反方向/同一轴的多个输入无法物理同时满足，沿用并明确展示现有合并策略；补测等幅冲突时结果稳定，不依赖网络包到达先后反复跳变。如果现有策略不能满足此约束，先记录具体兼容影响再调整，不暗改用户手感。
- 同按钮重叠按住会合并为持续按住，不能声称游戏一定识别出两次独立点击。需要两次按下沿时，应由事件顺序和空闲间隔表达。
- 广播“同时控制”表示各目标独立及时启动；不承诺跨电脑在同一毫秒开始。记录四个目标的启动时间和偏差，任一设备抖动不得阻塞其余设备；严格跨机时钟同步不纳入本版。

专项验收矩阵：

| 编号 | 注入情形 | 必须观察到的结果 |
| --- | --- | --- |
| F01 | B→A/C，各 1+2 | 四个目标分别接受、执行并释放，没有目标缺失 |
| F02 | A1 正常 / A1 拒绝 / A1 抛出预期运行异常 | 三种情况下 A2、C1、C2 都继续处理 |
| F03 | A 握手卡住、发送队列满或断开 | C 独立投递；A 明确失败/忙碌；没有全局通道异常 |
| F04 | 完整消息重复、仅部分目标已启动、显式目标与广播重叠 | 成功实例不重复启动，未处理目标不被误判重复 |
| F05 | 同时触发两个不同事件，两者同按 X | 停止一个后 X 保持，最后一个释放后 X 才松开 |
| F06 | 同时控制 1/2，只停止或使 1 过期 | 2 的时间轴和按键/摇杆输出保持正常 |
| F07 | 快速 start→stop→start，插入旧包、旧回执和延迟 clear | 最后一次实例正常，旧实例不能复活或清除新实例 |
| F08 | A/C 都连回 B，收到广播事件 | 无反向自动转发、无自触发循环、无报文持续增长 |
| F09 | 本机按 W；远端移动/技能事件开始并结束 | 合并规则稳定，事件停止后 W/ABXY 映射仍有效 |
| F10 | 广播后目标离线、停止、重连 | 原实例按会话策略清理；重连不执行过期动作 |
| F11 | C1 输出后端提交失败 | C1 有失败回执，其他可用控制器仍继续；若后端整体不可用，准确标注受影响范围 |

T29 新增 `core/runtime/tests/test_event_fanout_isolation.py` 覆盖 F01–F08/F10 的路由与实例行为；在 `device_link/tests/DeviceLink.Tests/ThreePeerTests.cs` 覆盖真实连接排队/断连；在 `virtual_gamepad/host/tests/VirtualGamepadHost.Tests/EventCoexistenceTests.cs` 覆盖 F05/F06/F09/F11 的输出隔离。T31 在真实 A/C 上复核 F01/F03/F06/F09/F10。

聚焦命令：`& $planPython -m pytest -q core/runtime/tests/test_event_fanout_isolation.py`；预期每个场景断言完整目标集合及各目标的实际调用/输出，不能只断言“至少一个成功”。新增套件创建后执行；本轮尚未运行。

## 2. 工作方式和恢复记录

状态文件：[开发断点](2026-09-13-device-link-capability-development-progress.md)。任务状态仅使用 `TODO / DOING / VERIFIED / BLOCKED`；本文所有任务目前均为 TODO。

每个任务内按小步推进：写一个行为测试 → 确认失败原因 → 最小修复 → 聚焦验证 → 记录并提交。每个编辑或验证小步尽量 2–5 分钟；连接抽取、实机联调由多步组成，不承诺整个任务几分钟完成。

每次完成任务记录：改动文件、测试命令与结果、提交号、未解决问题、下一步。每阶段有独立 Git 回滚点。不要用 `git add .` 纳入无关用户修改；回滚使用明确提交的 revert，并遵循当时用户指令，不自动重置工作区或删除数据。

任务不要求每一步结束后向用户询问；开始实施后按依赖连续推进。实际配置冲突、必须改变已认可行为、或缺少实机访问条件时，记录具体阻塞；可继续的独立任务仍继续。规划本身不运行游戏输入、安装驱动或发送远端事件。

## 3. 统一命令与基线

以下命令以 `D:/ACloud/auto_modules` 为工作目录。该路径下的文件在任务中用仓库相对路径精确标识；新增路径标记“新增”。规划时已经验证 Python、SDK、Inno 编译器路径存在。命令预期是实施时的验收要求，不代表本轮已经运行通过。

```powershell
Set-Location D:/ACloud/auto_modules
$planPython = 'D:/ACloud/.venv/Scripts/python.exe'
$planDotnet = 'D:/ACloud/dotnet-sdk2/dotnet.exe'
```

| 验证编号 | 精确命令 | 预期 |
| --- | --- | --- |
| V-LAN | `& $planDotnet test lan_input_sync/tests/LanInputSync.Tests/LanInputSync.Tests.csproj --no-restore` | 已有配对/输入/目录 loopback 回归通过 |
| V-LINK | `& $planDotnet test device_link/tests/DeviceLink.Tests/DeviceLink.Tests.csproj --no-restore` | 新库创建、restore 后，独立连接与消息测试通过 |
| V-EVENT | `& $planPython -m pytest -q tests/test_event_lifecycle.py tests/test_event_session.py core/events/tests core/runtime/tests` | 事件数据、路由和时间语义通过 |
| V-HOST | `& $planDotnet test virtual_gamepad/host/tests/VirtualGamepadHost.Tests/VirtualGamepadHost.Tests.csproj --no-restore` | 输入、输出、释放、LAN 接入回归通过 |
| V-UI | `& $planPython -m pytest -q tests/test_event_workbench_ui.py virtual_gamepad/ui/tests/test_sync_panel.py` | 原有事件与局域网页回归通过 |
| V-PACK | `& $planPython -m pytest -q tests/test_distribution.py tests/test_runtime_paths.py` | 打包源与运行路径通过 |
| V-INSTALL | `& $planDotnet test installer/tests/Installer.Tests.csproj --no-restore` | 安装器路径、驱动策略、数据保护通过 |

新项目先 restore，现有项目若缺缓存也先 restore 再测试；不能把“依赖未恢复”当作预期业务失败。新增测试命令必须确认实际发现并执行了用例，0 tests 不算通过。

## 4. 里程碑与任务依赖

| 里程碑 | 任务 | 交付物 / 阶段门槛 |
| --- | --- | --- |
| M0 基线 | T01 | 生产基线、配置备份规则、开发断点可恢复 |
| M1 先稳定现有连接 | T02–T06 | 合法目录不拆连接；重复/批量连接不互相取消；错误不跨设备扩散 |
| M2 抽取通用互联 | T07–T11 | 不启用任何业务也能连接；身份不变；旧入口可兼容 |
| M3 独立能力与消息 | T12–T16 | 按能力分发、权限、目录分片、事件回执、手柄适配共存 |
| M4 统一事件链路 | T17–T24 | 所有权/版本/删除一致；本机远端同一执行器；双手柄与映射共存 |
| M5 工作台接入 | T25–T28 | 共享后台装配、分层状态、有效配置、端到端日志 |
| M6 联调与发布 | T29–T32 | 自动回归、三节点联调、真实设备结果、安装包与校验信息 |

依赖主线：`T01 → M1 → M2 → M3 → M4 → M5 → M6`。T17–T21 的纯事件工作在 M2/M3 期间可独立推进，但接入验收必须等待消息契约稳定；不因此创建重复框架。

### T01：记录基线和可恢复开发入口

文件：本计划、审查文档、开发断点文档。

步骤：检查 `git status --short` 与 HEAD；当前已知生产基线是 `afae064`。开始实施时只暂存这三份文档形成规划提交，并在断点中记录实际提交号。配置迁移前使用项目现有 mutable-data 路径解析器定位数据，备份到单独时间戳目录；配置备份不进 Git，不复制到发布默认数据。

验证：`git diff --check`，执行 V-LAN、V-EVENT、V-HOST 记录基线；已有失败单列，后续不得当作新修复证明。提交：`docs: record device link refactor baseline`。

### T02：固定目录深度失败并统一消息限制

修改：`lan_input_sync/src/LanInputSync/LanSyncService.Control.cs`、`lan_input_sync/src/LanInputSync/LanSyncService.SharedData.cs`、`lan_input_sync/tests/LanInputSync.Tests/LoopbackTests.cs`。
新增：`lan_input_sync/src/LanInputSync/ProtocolLimits.cs`。

先新增 `ParallelCatalogDoesNotDisconnectPeer`：通过真实配对、序列化、TLS 接收最小并行目录，随后发送另一条事件并断言同一会话还在线。先复现旧 `MaxDepth=8` 失败。下方代码是测试目录的完整最小样本：

```csharp
var catalog = new {
    definitions = new[] {
        new {
            steps = new[] {
                new {
                    op = "parallel",
                    ms = 1000,
                    tracks = new[] {
                        new { buttons = new[] { "A" }, mode = "once", hold_ms = 100 }
                    }
                }
            }
        }
    }
};
```

发送与接收共享字节/深度限制。保留当前单帧 8192 字节限制，JSON 深度采用 32 作为有界候选；用 T21 支持的最大合法动作树及超限树验证后定稿，不仅改为 9。业务内容非法返回明确错误；认证失败/帧边界不可信仍断开。

验证：`& $planDotnet test lan_input_sync/tests/LanInputSync.Tests/LanInputSync.Tests.csproj --filter FullyQualifiedName~ParallelCatalogDoesNotDisconnectPeer`，预期修复前失败、修复后通过；再 V-LAN。提交：`fix: align catalog framing and validation limits`。

### T03：连接请求幂等及旧任务状态隔离

修改：`lan_input_sync/src/LanInputSync/LanSyncService.cs`、`lan_input_sync/src/LanInputSync/LanSyncService.Control.cs`、`lan_input_sync/tests/LanInputSync.Tests/LoopbackTests.cs`。

先测同设备重复 start 在“连接中”和“已连接”两种情况；测试用受控握手屏障确保时序，不以随机 sleep 期待竞态。任务登记成功后再发布版本；复用进行中的任务，不关闭健康会话。catch/finally 都核对 ticket 与当前会话代次，旧任务不能改新状态。

验证：`& $planDotnet test lan_input_sync/tests/LanInputSync.Tests/LanInputSync.Tests.csproj --filter "FullyQualifiedName~RepeatedStart|FullyQualifiedName~StaleConnection"`，预期两个时序均保留一条有效会话、旧错误不覆盖新连接。提交：`fix: make peer connection requests idempotent`。

### T04：批量连接逐设备返回结果

修改：`lan_input_sync/src/LanInputSync/LanSyncService.cs`、`lan_input_sync/tests/LanInputSync.Tests/LoopbackTests.cs`。

先测 A 连接中/C 正常、A 不可达/C 正常、A 已连接/C 新连接。校验和调度按目标处理，返回逐设备 scheduled/already_connected/connecting/rejected；旧顶层 ok 保留“命令被受理”的含义，不代表所有设备已连接。单设备异常不退出整个 foreach。

验证：`& $planDotnet test lan_input_sync/tests/LanInputSync.Tests/LanInputSync.Tests.csproj --filter FullyQualifiedName~MultiPeerStart`，预期 C 始终继续处理，结果覆盖全部请求目标。提交：`fix: isolate batch connection results per peer`。

### T05：普通配置热更新

修改：`lan_input_sync/src/LanInputSync/LanSyncService.cs`、`lan_input_sync/src/LanInputSync/LanSyncService.Control.cs`、`lan_input_sync/tests/LanInputSync.Tests/LoopbackTests.cs`。

把名称、速率、权限与绑定地址/端口差异分类。先测只改名称和事件权限不改变 sessionId；只撤销对应能力。旧模式切换在兼容入口保留明确的转换规则，完全去除模式依赖在 T10/T11 完成。地址/端口变化才重建相关传输并报告原因。

验证：`& $planDotnet test lan_input_sync/tests/LanInputSync.Tests/LanInputSync.Tests.csproj --filter FullyQualifiedName~ConfigurationUpdate`，预期非网络配置不触发全局 EmergencyStop。提交：`fix: apply non-network settings without reconnecting peers`。

### T06：现有队列与异常的设备隔离

修改：`lan_input_sync/src/LanInputSync/LanSyncService.SharedData.cs`、`lan_input_sync/src/LanInputSync/LanSyncService.Transport.cs`、`lan_input_sync/src/LanInputSync/LanSyncService.Control.cs`、`lan_input_sync/tests/LanInputSync.Tests/LoopbackTests.cs`。

先验证 A 填满队列后 C 的消息不关闭 C；发送队列满返回 busy，目录更新可合并待发版本。区分单报文失败、单设备传输失败和真正监听器不可用。M1 做必要修复，T12 再集中为正式消息模块，不保留两套长期队列。

验证：`& $planDotnet test lan_input_sync/tests/LanInputSync.Tests/LanInputSync.Tests.csproj --filter "FullyQualifiedName~QueueIsolation|FullyQualifiedName~PeerFault"`；再 V-LAN。提交：`fix: contain shared message failures to their peer`。

### T07：建立通用库和窄接口

新增：`device_link/src/DeviceLink/DeviceLink.csproj`、`device_link/src/DeviceLink/Contracts.cs`、`device_link/tests/DeviceLink.Tests/DeviceLink.Tests.csproj`、`device_link/tests/DeviceLink.Tests/ArchitectureTests.cs`。
修改：`lan_input_sync/src/LanInputSync/LanInputSync.csproj`。

新库只接身份、连接、传输和消息，不引用 LanInputSync、Host、游戏、GUI、Controller。接口契约由下面的最小草案固定，内部实现随后迁移；不要建立第二套服务常驻监听。

```csharp
using System.Text.Json;

namespace DeviceLink;

public sealed record PeerResult(string DeviceId, string State, string? Error);
public sealed record SendResult(string RequestId, bool Queued, string? Error);
public sealed record ReceivedMessage(
    string PeerId, string SessionId, string Capability,
    string RequestId, int RemainingMs, JsonElement Payload);

public interface IDeviceLink : IAsyncDisposable
{
    Task<PeerResult> ConnectAsync(string deviceId, CancellationToken cancellation);
    Task DisconnectAsync(string deviceId, CancellationToken cancellation);
    SendResult TrySend(string deviceId, string capability, string requestId,
                       JsonElement payload, int validityMs);
    IDisposable Subscribe(string capability, Action<ReceivedMessage> handler);
}
```

这里只固定最小连接/投递接口；配对配置和状态快照使用独立接口，不把所有设置重新塞入一个 Handle。订阅回调不得在网络锁或输入线程执行，业务处理器唯一注册；诊断观察者另行订阅。

验证：`& $planDotnet restore device_link/tests/DeviceLink.Tests/DeviceLink.Tests.csproj`，再 V-LINK；ArchitectureTests 检查项目依赖方向。提交：`refactor: define independent device link contracts`。

### T08：迁移身份、发现与配对

迁移源：`lan_input_sync/src/LanInputSync/IdentityStore.cs`、`lan_input_sync/src/LanInputSync/LanSyncService.Control.cs`、`lan_input_sync/src/LanInputSync/LanSyncService.Transport.cs`。
新增：`device_link/src/DeviceLink/Identity/IdentityStore.cs`、`device_link/src/DeviceLink/Discovery/DiscoveryModule.cs`、`device_link/src/DeviceLink/Pairing/PairingModule.cs`、`device_link/tests/DeviceLink.Tests/IdentityCompatibilityTests.cs`、`device_link/tests/DeviceLink.Tests/PairingTests.cs`。

复用原实现，保留证书、DPAPI、文件布局与一次性配对码验证。使用临时身份夹具，证明同一身份重载 deviceId 不变、单方确认不建立信任、过期码不能成功。不读取或输出真实私钥。

验证：`& $planDotnet test device_link/tests/DeviceLink.Tests/DeviceLink.Tests.csproj --filter "FullyQualifiedName~IdentityCompatibility|FullyQualifiedName~Pairing"`。提交：`refactor: extract identity discovery and pairing`。

### T09：迁移安全传输，保留手柄编解码

修改源：`lan_input_sync/src/LanInputSync/LanSyncService.Control.cs`、`lan_input_sync/src/LanInputSync/LanSyncService.Transport.cs`、`lan_input_sync/src/LanInputSync/SecurePackets.cs`。
新增：`device_link/src/DeviceLink/Transport/ControlTransport.cs`、`device_link/src/DeviceLink/Transport/DatagramTransport.cs`、`device_link/src/DeviceLink/Transport/PacketSecurity.cs`、`device_link/src/DeviceLink/Transport/ProtocolLimits.cs`、`device_link/tests/DeviceLink.Tests/TransportTests.cs`。

通用库承接 TLS、帧、加密/重放保护；PadState 及按键 lane 业务编解码留在手柄同步模块，不随类名整体搬入基础库。迁移原协议测试到新接口，保留固定数据包测试向量。

验证：`& $planDotnet test device_link/tests/DeviceLink.Tests/DeviceLink.Tests.csproj --filter FullyQualifiedName~Transport` + V-LAN；预期旧数据包仍兼容，篡改与重放继续拒绝。提交：`refactor: extract secure transport from gamepad protocol`。

### T10：每设备连接状态机与双向拨号仲裁

修改：`lan_input_sync/src/LanInputSync/LanSyncService.cs`、`lan_input_sync/src/LanInputSync/LanSyncService.Control.cs`。
新增：`device_link/src/DeviceLink/Connections/ConnectionManager.cs`、`device_link/src/DeviceLink/Connections/PeerSession.cs`、`device_link/tests/DeviceLink.Tests/ConnectionTests.cs`。

将 T03–T05 已验证的行为迁入 ConnectionManager。状态为 disconnected/connecting/authenticating/connected/reconnecting/failed，配对信任单列。双方同时拨号时按稳定设备 ID 选择同一胜出方向，只取消输掉的任务；新旧 finally 必须按会话对象/代次关闭，不能按 deviceId 误杀替代会话。加入按设备退避、抖动、显式停止取消重试。事件 TLS 健康独立于输入 TTL，UDP 暂时不可用只降级相关能力。

验证：`& $planDotnet test device_link/tests/DeviceLink.Tests/DeviceLink.Tests.csproj --filter FullyQualifiedName~Connection`，覆盖零能力连接、同时拨号、重复请求、停止中重连、多设备单方失败。提交：`refactor: centralize peer connection lifecycle`。

### T11：旧命令兼容与 Host 装配分离

修改：`lan_input_sync/src/LanInputSync/LanSyncService.cs`、`lan_input_sync/src/LanInputSync/Contracts.cs`、`virtual_gamepad/host/src/VirtualGamepadHost/Runtime/HostComposition.cs`、`virtual_gamepad/host/src/VirtualGamepadHost/Protocol/CommandRouter.cs`、`virtual_gamepad/host/src/VirtualGamepadHost/Runtime/ControllerRegistry.cs`。
新增：`lan_input_sync/src/LanInputSync/Compatibility/LegacySyncCommands.cs`、`virtual_gamepad/host/tests/VirtualGamepadHost.Tests/DeviceLinkIntegrationTests.cs`。

同一 Host 装配唯一 DeviceLink 实例，旧 sync.* 调用翻译到该实例。新 link.* 管理指令直接路由到互联模块，不经过控制器输入锁。零驱动可连接/发事件，启动本机触发监听不激活映射；事件输出按需复用既有控制器，切换来源不销毁重建控制器。

验证：V-HOST、V-LAN；新增测试无驱动仍可连接、关闭事件不关闭链接、旧 sync.* 不额外监听端口。提交：`refactor: compose device links independently of controller routing`。

### T12：能力注册、授权与独立队列

新增：`device_link/src/DeviceLink/Messaging/CapabilityRegistry.cs`、`device_link/src/DeviceLink/Messaging/MessageDispatcher.cs`、`device_link/src/DeviceLink/Messaging/PeerMailbox.cs`、`device_link/tests/DeviceLink.Tests/CapabilityTests.cs`、`device_link/tests/DeviceLink.Tests/MailboxTests.cs`。
修改：`lan_input_sync/src/LanInputSync/LanSyncService.SharedData.cs`。

能力名固定为 `events.command`、`events.catalog`、`gamepad.state`、`positions.snapshot`；版本和方向单独协商。按 peer/capability 限定队列及预算，控制/授权消息保留独立容量。事件满队列返回 busy，目录合并最新版本，位置覆盖旧快照。入站消息携带认证 peerId/sessionId，负载不能伪造来源。只允许一个业务消费者，日志观察不抢消息。

验证：`& $planDotnet test device_link/tests/DeviceLink.Tests/DeviceLink.Tests.csproj --filter "FullyQualifiedName~Capability|FullyQualifiedName~Mailbox"`，覆盖撤权、重复订阅、A 拥塞不影响 C/控制队列。提交：`feat: add independently authorized capability channels`。

### T13：事件命令协议、有效期与去重

新增：`core/communication/__init__.py`、`core/communication/device_link_client.py`、`core/events/execution/__init__.py`、`core/events/execution/contracts.py`、`device_link/src/DeviceLink/Messaging/MessageEnvelope.cs`、`device_link/tests/DeviceLink.Tests/MessageEnvelopeTests.cs`、`core/runtime/tests/test_event_request_contract.py`。
修改：`virtual_gamepad/client/python/virtual_gamepad_client.py`。

本版请求外壳示例（示例 ID，非真实设备）：

```json
{
  "protocolVersion": 2,
  "capability": "events.command",
  "capabilityVersion": 1,
  "requestId": "request-unique-001",
  "validityMs": 500,
  "payload": {
    "operation": "start",
    "ruleId": "rule-b-f2",
    "event": {"ownerDeviceId": "device-b", "eventId": "roll", "revision": 3},
    "targets": [{"deviceId": "device-a", "controllers": [1, 2]}],
    "retriggerPolicy": "restart_same_rule"
  }
}
```

发送源从认证上下文获取。有效期需扣除本地排队和传输估计，复用 challenge 校验并让事件 TLS 自己更新 challenge。接收端的剩余时长再转本地 deadline。去重按认证来源+requestId+目标，保留有界结果缓存；不宣称跨崩溃 exactly-once。进程重启产生新会话且旧请求过期，不自动重播不确定执行。

验证：V-LINK 的 MessageEnvelopeTests；`& $planPython -m pytest -q core/runtime/tests/test_event_request_contract.py`，覆盖旧版/新版、过期、非法目标、重复请求、设备时钟不同。提交：`feat: define traceable remote event requests`。

### T14：按目标回执与可追踪投递

新增：`core/communication/receipts.py`、`core/runtime/tests/test_event_receipts.py`。
修改：`device_link/src/DeviceLink/Messaging/MessageDispatcher.cs`、`core/communication/device_link_client.py`、`core/events/execution/contracts.py`。

定义 queued/received/accepted/running/output_submitted/completed/cancelled/rejected；每条携带 requestId、目标和错误原因。output_submitted 仅在真实输出后端返回相应结果时产生；Null 后端不能报实际驱动提交。网络重试复用同一 requestId，只在剩余有效期内进行；缺失回执显示结果未知，不替用户无限重复执行。

验证：`& $planPython -m pytest -q core/runtime/tests/test_event_receipts.py`；测试 A 成功/C 拒绝、回执重发、超时未知、队列成功但远端拒绝的展示语义。提交：`feat: track per-target event delivery receipts`。

### T15：目录同步独立化与有界分片

修改：`core/runtime/event_catalog_runtime.py`、`lan_input_sync/src/LanInputSync/LanSyncService.SharedData.cs`。
新增：`core/communication/catalog_channel.py`、`core/runtime/tests/test_catalog_channel.py`。

直接对创建者同步摘要、版本与删除标记；不再每次按键都无条件先发整份目录。超出单帧的目录按有界块同步，默认原始块最多 4096 字节、总量/并发/超时有界；根据实际 envelope 序列化测试确保不超过 8192 字节。完整批次校验 hash 后一次应用，缺片保留旧版本。事件版本未就绪时预同步；触发当刻仍缺失则明确 catalog_pending/revision_missing，不能执行同名旧版本。

验证：`& $planPython -m pytest -q core/runtime/tests/test_catalog_channel.py core/runtime/tests/test_event_catalog_runtime.py`，覆盖分片、丢片、空目录、乱序、重复、超限、撤权和新旧端不兼容。提交：`feat: separate bounded event catalog synchronization`。

### T16：手柄与位置适配到共同连接

修改：`lan_input_sync/src/LanInputSync/LanSyncService.Transport.cs`、`lan_input_sync/src/LanInputSync/ReceiverSlot.cs`、`core/lan_follow/follow_transport.py`。
新增：`lan_input_sync/src/LanInputSync/GamepadSync/GamepadChannel.cs`、`core/communication/position_channel.py`、`core/runtime/tests/test_channel_dispatch.py`。

保留手柄可靠变化 lane、短按保证、独立控制器授权与过期释放，解除 DataOnly 的整会话互斥。位置仅迁移订阅，不实现新定位。FollowTransport 与远端事件不能再 drain 同一全局队列；兼容入口内部委托统一分发。

验证：V-LAN、V-HOST；`& $planPython -m pytest -q core/runtime/tests/test_channel_dispatch.py`，同一连接事件与手柄共存、关事件不关其他能力。提交：`refactor: adapt input and position channels to shared links`。

### T17：事件稳定身份与只写自己定义

修改：`core/events/event_catalog.py`、`core/events/event_store.py`、`core/events/tests/test_event_catalog.py`、`core/events/tests/test_event_store.py`。
新增：`core/events/catalog/__init__.py`、`core/events/catalog/keys.py`。

稳定键的完整基础实现：

```python
from dataclasses import dataclass


@dataclass(frozen=True, order=True)
class EventKey:
    owner_device_id: str
    event_id: str

    def __post_init__(self):
        if not self.owner_device_id.strip() or not self.event_id.strip():
            raise ValueError("event owner and id are required")
```

仓库、目录、路由、执行定义都用此键；name 仅显示。远端 apply 接收认证 peerId，拒绝改写他人 owner。旧文件缺 owner 的本机项按稳定本机身份迁移；无法归因的远端旧项请求权威目录，不按同名认领。

验证：`& $planPython -m pytest -q core/events/tests/test_event_store.py core/events/tests/test_event_catalog.py`；新增 A/B 同名、伪造 owner、同 ID 不同 owner、旧数据迁移。提交：`fix: preserve event ownership throughout catalog lookup`。

### T18：事件仓库单一写入口与变更通知

修改：`core/events/event_store.py`、`core/runtime/event_catalog_runtime.py`、`gui/modes/events/workbench.py`、`core/events/tests/test_event_store.py`。
新增：`core/events/catalog/repository.py`。

把仓库实现从现有 EventStore 收拢，旧类暂留兼容门面；create/update/copy/delete/apply_remote 全走同一写入口。每份文件使用同目录临时文件原子替换，写入锁覆盖 read-modify-write；发布 store revision 变更通知。copy 新 ID；delete 版本化 tombstone；读取可见列表和导出同步记录分开。不得以空目录忽略删除。

验证：`& $planPython -m pytest -q core/events/tests/test_event_store.py core/runtime/tests/test_event_catalog_runtime.py`，覆盖并发更新、写失败原文件完整、复制/删除/重启、缓存通知。提交：`refactor: centralize versioned event repository writes`。

### T19：统一定义校验与编译入口

修改：`core/events/action_tracks.py`、`core/events/event_lifecycle.py`、`core/runtime/local_event_runtime.py`、`core/runtime/remote_event_runtime.py`。
新增：`core/events/execution/compiler.py`、`core/events/tests/test_event_compiler.py`。

编译结果为不可变定义快照，含 key、revision、schemaVersion、动作树和限制。校验输入名、duration、interval、循环边界、组合深度和节点数；原始 JSON 不在每个 tick 重复校验。旧 tracks/steps 编译成相同内部表示，未知 op 明确拒绝。感知/导航 condition/retry/emit 只有对应已注册执行适配器时可用，不假装宏引擎支持。

验证：`& $planPython -m pytest -q core/events/tests/test_event_compiler.py tests/test_event_lifecycle.py`，旧合法定义兼容、新结构非法拒绝、UI 和远端得到一致校验错误。提交：`refactor: compile event definitions through one validator`。

### T20：统一时间轴、重复与结束释放

修改：`core/events/action_tracks.py`、`core/events/event_lifecycle.py`、`tests/test_event_lifecycle.py`、`tests/test_event_periodic_schedule.py`。

先固定顶层单次轨道重复两次的完整回归：

```python
from core.events.action_tracks import ActionTrack
from core.events.event_lifecycle import EventLifecycle


def test_once_track_runs_in_each_event_iteration():
    event = EventLifecycle(
        [ActionTrack(("X",), hold_ms=100)],
        max_runs=2,
        steps=({"op": "wait", "ms": 200},),
    )
    assert event.poll(0) == {"X"}
    assert event.poll(100) == set()
    assert event.poll(200) == {"X"}
    assert event.poll(300) == set()
    assert event.poll(400) == set()
    assert event.finished
```

统一每轮相对时间，次数作用于整个事件，顶层轨道与顺序分支使用同一轮长；分支提前结束后保持空闲到本轮末尾。保留旧版节奏兼容转换。新无限循环由显式停止、断连策略和应用退出中止，不再用巨大次数伪装循环。频率 hold 大于 interval 时新版要求用户明确持续模式，旧数据保持兼容。

验证：`& $planPython -m pytest -q tests/test_event_lifecycle.py tests/test_event_periodic_schedule.py`，覆盖边界时刻、重复两次、无限循环可停、结束后释放、旧连续轨道兼容。提交：`fix: unify event iteration and timed input semantics`。

### T21：有界顺序/并行组合与输入动作

修改：`core/events/execution/compiler.py`、`core/events/event_lifecycle.py`、`core/events/gamepad_output.py`、`tests/test_event_button_chords.py`、`tests/test_event_gamepad_output.py`。
新增：`core/events/tests/test_action_tree.py`。

复用现有 button/wait/parallel 和 LS_* 输入支持；增加 sequence 分支，容许并行分支内顺序。首版组合深度最多 4、总动作节点最多 256；持续时间与计时整数范围有界。无引用式递归，不引入动态脚本语言。编译后时间树由同一调度器求值，不每个节点开线程。精确定义按下到按下的间隔与 wait 差别，生成最大的合法结构作为 T02 跨语言序列化测试样本。

验证：`& $planPython -m pytest -q core/events/tests/test_action_tree.py tests/test_event_button_chords.py tests/test_event_gamepad_output.py`；再 V-LINK 的 TransportTests，验证深度/字节两端一致。提交：`feat: compose bounded sequential and parallel event actions`。

### T22：统一路由与所有目标执行

修改：`core/runtime/local_event_runtime.py`、`core/runtime/remote_event_runtime.py`、`core/runtime/remote_event_sender.py`、`core/runtime/event_session.py`。
新增：`core/events/triggers/__init__.py`、`core/events/triggers/router.py`、`core/runtime/tests/test_event_routing.py`。

路由记录独立 ruleId、EventKey、device/controller 目标集。一次输入展开全部规则与全部目标，去重目标后逐个启动并分别回执。先消除当前 any 短路，再把本地/远端/页面发送收为同一路由。以下调用模式必须保留“先执行全部，再聚合”的行为：

```python
def start_all_targets(sessions, event_key, targets):
    results = {}
    for controller in dict.fromkeys(targets):
        try:
            results[controller] = {"started": bool(sessions[controller].start(event_key))}
        except (KeyError, ValueError, RuntimeError) as error:
            results[controller] = {"started": False, "error": str(error)}
    return results
```

上面的函数只示范已就绪的本机控制器逐目标启动，不用于串行等待远端设备响应。跨设备投递使用独立任务/队列；正式路由还传 instanceId、版本及来源上下文，不能退回仅 name。本地与远端各只做输入适配器，不自行创建另一份 definitions。完整隔离规则以 1.1 节为准。

验证：`& $planPython -m pytest -q core/runtime/tests/test_event_routing.py core/runtime/tests/test_remote_event_delivery.py`，Controller 1+2 都启动、A/C 分别结果、同键多规则、缺版本拒绝而不按同名回退。提交：`refactor: route local and remote events through one executor`。

### T23：执行实例归属、去重与局部取消

修改：`core/runtime/event_session.py`、`core/runtime/remote_event_runtime.py`、`tests/test_event_session.py`、`core/events/execution/contracts.py`。
新增：`core/events/execution/runtime.py`、`core/runtime/tests/test_execution_ownership.py`。

由既有 EventSession 扩展实例管理，保存 source peer/session/rule/request、definition snapshot、controller。同名不同来源并存；重传返回既有结果；重复按键按 restart_same_rule 处理。断连、撤权、停止、异常、关闭应用进入同一个按范围取消路径。仓库更新不改变运行快照，下一次触发采用新 revision。

验证：`& $planPython -m pytest -q tests/test_event_session.py core/runtime/tests/test_execution_ownership.py`，远端 B 断开不停止 C/本地；断连取消循环；停止先到/重复停止幂等；旧 session 不能续期新实例。提交：`feat: scope event execution and cancellation by origin`。

### T24：复用 Host 输出与键鼠映射共存

修改：`virtual_gamepad/host/src/VirtualGamepadHost/Runtime/ControllerRegistry.cs`、`virtual_gamepad/host/src/VirtualGamepadHost/Runtime/ReportLoop.cs`、`virtual_gamepad/host/src/VirtualGamepadHost/Protocol/CommandRouter.cs`、`core/runtime/event_session.py`、`core/events/execution/runtime.py`、`virtual_gamepad/host/tests/VirtualGamepadHost.Tests/ControllerRegistryTests.cs`。
新增：`virtual_gamepad/host/tests/VirtualGamepadHost.Tests/EventCoexistenceTests.cs`。

输入来源包含执行设备内的稳定实例标识，由执行器管理合法来源；先检查现有 source 校验和 TTL 限制再扩展。保持既有合并算法，取消仅移除对应来源。Host 接受状态与实际 backend 提交分别记录，以来源状态版本和 report 序号关联 requestId；只有 SubmitAll/SubmitOnce 实际成功提交后才返回提交证据。120ms 等现有输入过期策略不因远端链路慢而盲目延长。不会因切换事件/映射重建控制器或释放其他来源。

验证：`& $planDotnet test virtual_gamepad/host/tests/VirtualGamepadHost.Tests/VirtualGamepadHost.Tests.csproj --filter FullyQualifiedName~EventCoexistence` + V-HOST；覆盖 W 按住再按/松 D、ABXY 事件叠加、两个来源同按 X、关 F7/事件再开 F7、Controller1/2 分离。提交：`fix: isolate event output from physical mapping lifecycle`。

### T25：唯一后台装配与消息消费入口

修改：`gui/main_window.py`、`gui/modes/events/workbench.py`、`gui/modes/lan/page.py`、`virtual_gamepad/ui/virtual_gamepad_ui/sync_panel.py`、`core/runtime/local_event_runtime.py`、`core/runtime/remote_event_runtime.py`、`core/runtime/event_catalog_runtime.py`。
新增：`core/runtime/workbench_runtime.py`、`gui/composition/automation.py`、`core/runtime/tests/test_workbench_runtime.py`。

应用装配唯一连接客户端、目录订阅、触发路由、执行器、状态和日志。页面只引用服务，不在构造函数创建重复 worker；旧 runtime 类保留兼容门面并删除重复实现。退出按作用域取消、释放、停止线程；切换页面不调用 sync.stop。发送触发监听与接收执行可分别启用，关闭本机热键监听不关闭远端接收。

验证：`& $planPython -m pytest -q core/runtime/tests/test_workbench_runtime.py` + V-UI；两页面引用同一状态源、切页无连接变更、关闭窗口无遗留续期。提交：`refactor: centralize workbench runtime composition`。

### T26：局域网页展示设备和能力状态

修改：`gui/modes/lan/page.py`、`virtual_gamepad/ui/virtual_gamepad_ui/sync_panel.py`、`virtual_gamepad/ui/tests/test_sync_panel.py`。

设备行显示名称、连接状态、最后成功通信、当前错误；展开显示目录/事件/手柄/位置能力方向与授权。连接、断开、重连、解除配对是独立动作；事件监控不标成“启动同步”。显示未授权/执行未启用/版本不支持的原因。沿用现有风格与控件，仅调整职责和布局，不重做主题。

验证：V-UI，增加 A/C 同时连接但能力不同、单设备错误、重置单设备、历史错误清除用例；人工窗口最小尺寸检查无压住按钮。提交：`feat: show separate device capability and executor states`。

### T27：事件编辑和触发规则接入统一模型

修改：`gui/modes/events/workbench.py`、`gui/modes/follow/editors.py`、`tests/test_event_workbench_ui.py`。
新增：`core/events/triggers/keys.py`、`core/runtime/tests/test_trigger_keys.py`。

编辑页只写本机仓库，远端显示创建者且只读，可复制到本机。按 EventKey 选事件、按 deviceId 多选目标、每设备选择 1/2/同时；广播独立可选。键盘下拉与触发监听复用同一键表，保留 F7/F8 等映射控制键并给冲突提示。编辑顺序/并行组使用 T21 模型；保存即时显示编译错误，不能吞掉未支持步骤。支持所有本地已有热键的迁移。

验证：V-UI；`& $planPython -m pytest -q core/runtime/tests/test_trigger_keys.py`；验证编辑→保存→重载→编译一致，远端选择不被同名替换，目标身份不因重命名改变。提交：`feat: bind event editor and trigger rules to shared contracts`。

### T28：本机远端统一日志和输出证据

新增：`core/runtime/event_diagnostics.py`、`core/runtime/tests/test_event_diagnostics.py`。
修改：`gui/modes/events/workbench.py`、`core/events/execution/runtime.py`、`core/communication/receipts.py`、`virtual_gamepad/host/src/VirtualGamepadHost/Runtime/ControllerRegistry.cs`、`virtual_gamepad/host/src/VirtualGamepadHost/Runtime/HostDiagnostics.cs`、`virtual_gamepad/host/src/VirtualGamepadHost/Driver/ViGEmXInputBackend.cs`。

按 requestId 关联触发、排队、收到、校验、实例启动、状态提交、驱动提交、结束释放；区分 definitionKey 与 instanceId。只记录状态变化和汇总心跳，不每 tick 写相同状态；日志滚动、有界，密钥和完整目录不入日志。面板在仅远端执行时也更新，逐设备逐手柄展示失败环节。

验证：`& $planPython -m pytest -q core/runtime/tests/test_event_diagnostics.py core/runtime/tests/test_event_receipts.py`；模拟拒绝/断连/输出失败都能定位第一处缺失。单一来源结束验证 Host 归零；多来源共存时验证该实例贡献已清除、其余输入仍保留，不能强求整体归零。提交：`feat: trace event execution across peers and controller output`。

### T29：跨模块回归与三节点本机联调

新增：`device_link/tests/DeviceLink.Tests/ThreePeerTests.cs`、`core/runtime/tests/test_multi_device_event_flow.py`、`core/runtime/tests/test_event_fanout_isolation.py`。
修改：`lan_input_sync/tests/LanInputSync.Tests/LoopbackTests.cs`、`virtual_gamepad/host/tests/VirtualGamepadHost.Tests/LanIntegrationTests.cs`、开发断点文档。

先建立三个独立身份/端口/临时数据目录的真实 loopback 节点，B→A/C 同时连接与目录/事件双向流转；Python 执行接真实 Host 命令适配但测试输出后端，不向用户游戏注入。覆盖其中一台断网、忙队列、重连、双控制器、版本更新、停止与映射叠加。原测试禁止为了通过而改成错误的旧语义；确需调整兼容契约时写明差异。

验证：V-LINK、V-LAN、V-EVENT、V-HOST、V-UI；`& $planPython -m pytest -q core/runtime/tests/test_multi_device_event_flow.py core/runtime/tests/test_event_fanout_isolation.py`。F01–F11 按 1.1 节验证完整目标与错误范围。记录实际发现/通过数，不使用固定虚构数字。提交：`test: verify multi-device event and mapping coexistence`。

### T30：旧数据与混合版本兼容验收

新增：`core/runtime/tests/test_event_config_migration.py`、`device_link/tests/DeviceLink.Tests/ProtocolCompatibilityTests.cs`。
修改：`core/events/catalog/repository.py`、`lan_input_sync/src/LanInputSync/Compatibility/LegacySyncCommands.cs`、`distribution/smoke_check.py`、`tests/test_distribution.py`。

用去标识的旧配置夹具验证 owner 补全、ID 保持、同名歧义阻止自动误配、copy/delete、热键和目标迁移；迁移失败保留原文件。保留 v1 可支持路径；v2 功能遇到旧对端明确 unavailable，不发送其无法解析的新负载。检查新 Python 包被现有构建白名单纳入，DeviceLink.dll 随 Host publish 输出。

验证：`& $planPython -m pytest -q core/runtime/tests/test_event_config_migration.py tests/test_distribution.py`；V-LINK 中 ProtocolCompatibilityTests。提交：`test: cover configuration and protocol migration`。

### T31：真实 B→A/C 与 Xbox 验收

新增：`docs/plans/2026-09-13-device-link-capability-verification.md`（实施阶段填写实际结果）。

执行时确认可访问的设备与运行版本，不能把本机截图视为远端状态。真实发送前使用用户已授权的测试事件与目标；若只能访问本机，记录“远端未实测”，不能标完成。

用例：B 不开手柄映射只开触发；A/C 开事件执行但不接收手柄同步；各控制器分别和同时执行 X→Y→RB。随后开启 A/C 本机键鼠映射并触发并行移动/技能事件，停止后验证 WASD、ABXY 均正常。A 断开时 C 继续；A 回来不补执行旧事件。两设备各自修改/删除自己的定义，对端目录更新且仍只读。

每次记录 requestId、发送结果、接收/执行回执、控制器状态和归零；游戏效果由现场观察记录。统计触发→接收、接收→输出的 p50/p95/max，局域网命令不逐帧往返控制宏。先测实际延迟再设产品预算，不预先承诺毫秒值。

通过标准：上述用例有真实结果且无粘键；未能观察游戏效果与传输失败必须分别记录。提交：`docs: record real multi-device event verification`。

### T32：沿用离线流程打包和交付

修改：`distribution/build.py`、`distribution/smoke_check.py`、`installer/AutoModules.iss`、`distribution/README.md`（仅实际必要改动）；开发断点和验证报告。

沿用官方驱动检查/触发安装，保留用户已有数据和独立身份。安装包内不得包含开发机配对身份、私钥、远端缓存、运行日志。模块重构建议版本 `0.3.0`；如果执行时已占用该版本，则用下一个未使用版本并记录。构建目录必须是新的，不覆盖旧包或运行中二进制。

```powershell
& $planPython -m distribution.build --output 'D:/ACloud/auto_modules/build/device-link-capabilities-0.3.0'
& 'D:/ACloud/auto_modules/build/device-link-capabilities-0.3.0/python/python.exe' -I -B 'D:/ACloud/auto_modules/build/device-link-capabilities-0.3.0/app/smoke_check.py'
& 'D:/ACloud/auto_modules/build/installer-tools/InnoSetup/ISCC.exe' '/DPayloadDir=D:/ACloud/auto_modules/build/device-link-capabilities-0.3.0' '/DOutputDir=D:/ACloud/auto_modules/dist' '/DAppVersion=0.3.0' installer/AutoModules.iss
Get-FileHash -Algorithm SHA256 'D:/ACloud/auto_modules/dist/AutoModules-Setup-0.3.0-win-x64.exe'
```

执行前 V-PACK、V-INSTALL；构建预期 PAYLOAD_READY、独立 runtime smoke 通过、编译器成功。新包装到隔离目录验证统一启动、升级保留配置、已装驱动不重复安装、新身份不克隆；最终包再跑关键 B→A/C 用例，不能只测源码工作区。无实机条件时可产生标明“待联调”的测试包，但不能称最终验收完成。

交付：安装包绝对路径、SHA256、版本/提交、已测矩阵、未测项、B 与 A/C 最少操作说明。提交：`build: release modular device link workbench`。

## 5. 完成定义与防止重复实现

- 生产代码仅存在一个设备连接管理实现、一个消息分发入口、一个事件仓库写入口和一个定时执行内核；兼容门面不保留独立状态副本。
- DeviceLink 可独立测试配对/连接，不能引用事件定义、Xbox PadState、图像识别或 GUI。
- 旧安全传输、ReceiverSlot、动作适配器、控制器合并和导航事件实现先复用再迁移；删除旧路径必须有对应新路径验收证据。
- 本机热键、页面按钮、远端触发执行同一编译结果；同名事件不会覆盖，双设备双手柄目标不会短路。
- 停止事件/撤销能力/断开设备/解除配对的影响范围符合表中策略，映射开关未开时不拦截键盘。
- 每条关键问题都有失败复现及修复后测试；真实远端不可观察时明确记录，不用 mock 或 loopback 替代实机结论。
- 最终包与测试提交一致，安装后的运行时不依赖开发环境，用户配置不被迁移或安装过程静默覆盖。

## 6. 首个开发断点

下一步为 T01：重新检查工作区、提交规划回滚点、记录基线测试。随后 T02 先固定“并行目录导致断连”的真实协议回归，按任务依赖推进。

本轮仅检查了计划依赖的路径、版本、源码与打包命令；没有执行本计划的生产变更或验收测试。
