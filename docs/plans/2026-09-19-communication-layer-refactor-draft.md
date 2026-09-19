# 通用通信层重构设计（已审核通过）

> 状态：已审核通过，作为通信层重构的设计基线。
>
> 目标：把位置、事件、地图、配置和手柄同步统一到一个可复用的通信基础设施中；一次设备配对后持久记忆信任关系，后续自动重连，不再让每个业务各自建立专用连接。

## 1. 背景与现状问题

当前通信功能由多个业务分别使用：

- `application/follow/FollowService` 自己创建 `VirtualGamepadClient` 和 `FollowTransport`。
- `application/event_workbench/EventWorkbenchService` 自己创建 `HostEventBridge`。
- `FollowTransport` 和 `HostEventBridge` 都直接调用 `sync.share.*`。
- LAN 服务以一个 peer 一个活动 session 管理连接，同一个 peer 的重复启动会互相冲突。
- `sync.share.drain` 具有消费语义，不同业务各自读取时可能互相消费消息。
- 当前 `off/send/receive/share` 是互斥模式，不能自然表达“手柄接收、位置共享、事件接收、地图同步同时开启”。
- 目前已有 `trusted.json` 持久化信任关系，但配对、活动连接、业务能力启停没有被清晰分离，UI 和业务仍容易把“配对”误认为“启动某个功能”。

当前问题不是单个业务的实现错误，而是通信生命周期和业务生命周期耦合。

## 2. 重构目标

### 2.1 必须达成

1. 一个进程对一个 Host 只有一个通信管理入口。
2. 一个 peer 只建立一个物理通信 session；事件、位置、地图和输入复用该 session。
3. 业务只申请和释放逻辑能力，不直接创建或销毁物理连接。
4. 首次配对需要人工确认；配对成功后持久保存信任关系，后续重启和断线重连不再要求配对码。
5. 连接断开后可以自动重连，并重新协商已启用的业务能力。
6. 一个通信接收循环统一接收消息，再按 topic 分发给多个业务订阅者。
7. 位置、事件、地图、输入使用不同的可靠性、顺序和过期策略。
8. 输入控制权仍然按 Controller 独占，不能因为通信复用而产生多个远程 owner。
9. 普通测试不启动真实输入、真实 Host 或真实 LAN；所有真实链路继续保持显式 opt-in。

### 2.2 不在本轮目标内

- 不改变跟随算法、路径规划算法或事件链 DSL 的业务语义。
- 不改变虚拟手柄的 ViGEm 驱动实现。
- 不把所有业务代码一次性重写成新业务目录。
- 不实现地图同步业务；只保留可插拔的 `map` 能力、topic 和版本化资源接口，使地图完成后可以接入而不改物理连接层。

## 3. 目标架构

```text
业务功能
  FollowFeature / EventFeature / MapFeature / InputFeature
          │ 申请能力、发布消息、订阅 topic
          ▼
通用通信运行时
  CommunicationManager
    ├── PeerConnectionPool
    ├── PeerSessionRegistry
    ├── CapabilityLeaseManager
    ├── MessageDispatcher
    └── ReconnectController
          │ 一个 peer 一个物理 session
          ▼
通信适配器
  HostCommunicationAdapter
    ├── Named Pipe client
    ├── Host protocol codec
    └── request/response + event stream
          ▼
VirtualGamepadHost / LanSyncService
  TLS control + encrypted UDP lanes
  identity / trust / session / capability enforcement
          ▼
其他设备
```

通信层的核心边界：

- `core/communication`：只放契约、消息模型、能力、topic、QoS 和端口接口。
- `application/communication`：放进程级通信运行时和生命周期管理。
- `adapters/host`：放 Named Pipe、Host JSON 协议和 C# Host 适配。
- `services/lan_input_sync`：放设备身份、配对、信任、TLS、UDP、session 和服务端安全策略。
- `features/*`：只放业务策略，不拥有连接。

## 4. 连接生命周期模型

通信生命周期必须拆成四层：

```text
设备身份
  ↓
持久信任（pairing / enrollment）
  ↓
活动连接（session）
  ↓
逻辑能力（capability leases）
  ↓
业务订阅和发布（topics）
```

### 4.1 设备身份

每台设备首次运行时生成稳定的 `deviceId` 和设备证书。身份跨程序重启保持不变。

### 4.2 首次配对

首次建立信任时：

1. 接收端打开一次性配对码。
2. 发送端通过 TLS 提交设备身份和配对码。
3. 双方交换 nonce，生成 fingerprint。
4. 两边人工确认 fingerprint 一致。
5. 双方保存 peer 的 `deviceId`、证书指纹、公钥摘要、显示名和最近地址。

配对码只用于第一次建立信任，不能成为日常连接凭证。

### 4.3 后续自动连接

后续启动或断线时：

1. 从持久化 trust store 查找已信任 peer。
2. 使用保存的地址、发现结果或最后成功地址尝试连接。
3. TLS 客户端严格校验证书指纹和 `deviceId`。
4. 校验通过后直接建立新 session，不再要求配对码。
5. 使用指数退避自动重连，建议间隔为 `1s, 2s, 5s, 15s, 30s`，上限可配置。
6. 每次重连生成新的 session id、UDP token 和方向密钥，不能复用旧 session 密钥。
7. 重连后恢复用户允许自动恢复的逻辑能力。

### 4.4 忘记和撤销

以下操作必须显式执行：

- 忘记设备：删除本地 trust record，并关闭相关 session。
- 撤销设备：加入本地拒绝列表，拒绝后续自动连接。
- 证书更换：必须显示“证书已变化”，要求重新人工确认，不能静默接受。
- 紧急停止：立即撤销输入能力并关闭活动 session，但默认不删除配对信任。

## 5. 能力模型

当前互斥 `off/send/receive/share` 改为“连接状态 + 能力集合”。

### 5.1 能力分类

```text
input.send                 发送本机手柄状态
input.receive              接收远程手柄状态
position.publish           发布本机位置
position.subscribe         订阅远程位置
event.publish              发布事件
event.subscribe            订阅事件
catalog.publish            发布事件/配置目录
catalog.subscribe          订阅事件/配置目录
map.publish                发布地图版本和地图块
map.subscribe              订阅地图版本和地图块
```

### 5.2 能力租约

业务只能申请租约：

```text
lease = communication.acquire(peer_id, capability)
subscription = lease.subscribe(topic, handler)
lease.publish(message)
lease.close()
```

释放某个业务租约时，只释放该业务的能力和订阅，不关闭其他业务正在使用的 peer session。

### 5.3 输入能力的特殊规则

位置、事件、地图可以被多个业务或多个观察者订阅；Controller 输入不能这样处理。

- 每个 Controller 同一时间最多一个远程 owner。
- 接收端必须明确允许 Controller 1 或 Controller 2。
- 断线、超时、撤销和急停立即清空远程状态并回中。
- 已授权的输入能力在普通断线和进程重启后自动恢复；用户手动断开、手动停止、忘记设备或急停会清除自动恢复资格，之后必须重新显式启用。

## 6. Topic 与 QoS 设计

### 6.1 实时状态类

适用：`position`、摇杆 snapshot、遥测。

- Sequenced 或 latest-value 语义。
- 新值覆盖旧值。
- 必须带 `capturedAt`、`ageMs`、`ttlMs`。
- 超过 TTL 直接丢弃。

### 6.2 有序事件类

适用：`event`、事件状态、生命周期命令。

- Reliable Ordered。
- 带 `eventId`、`revision`、`sequence`、`deadline`。
- 接收端去重，过期事件不执行。
- 一个事件不能被两个业务接收循环重复消费。

### 6.3 版本化资源类

适用：`map`、`catalog`、路线和配置。

- Reliable、版本化、可重复请求。
- 使用 manifest 描述版本、大小、hash 和块数量。
- 大数据按 chunk 传输。
- 支持缺块重试和取消。
- 完整性校验通过后再提交为当前版本。
- 不使用实时位置的 500ms TTL。

## 7. 持久化数据设计

建议统一放在 `data/communication/`，由 `data_root()` 定位：

```text
data/communication/
  identity.json              本机稳定 deviceId 的非敏感描述
  trusted_peers.json        已配对 peer、证书指纹、地址和能力偏好
  capability_preferences.json 用户希望自动恢复的能力
  revocations.json          显式撤销的设备
  diagnostics.jsonl         连接、重连和协议错误诊断
```

私钥和证书私密材料不应直接以明文写入普通 JSON。Windows 上优先使用 DPAPI 或系统证书存储；JSON 只保存可展示和可校验的元数据。

持久化“信任”和持久化“能力偏好”必须分开：

- 信任关系决定能否免配对连接。
- 能力偏好决定连接后是否尝试恢复某功能。
- 输入能力默认自动恢复；只有用户手动断开、手动停止、忘记设备或急停时才清除输入能力的自动恢复资格。

## 8. 目标模块布局

```text
src/auto_modules/core/communication/
  contracts.py          PeerId、SessionId、Capability、Topic
  messages.py           通用消息和 envelope
  qos.py                实时、有序、版本化传输策略
  ports.py              CommunicationTransport、Subscription 等接口

src/auto_modules/application/communication/
  manager.py            进程级 CommunicationManager
  sessions.py           一个 peer 一个逻辑 session
  leases.py             能力租约和 Controller 所有权
  dispatcher.py         单接收循环、多订阅分发
  reconnect.py          自动重连和 session generation
  trust_store.py        持久化信任元数据接口

src/auto_modules/adapters/host/
  communication_adapter.py  Host 命令和数据流适配
  follow_transport.py       迁移后只保留业务字段转换
  event_bridge.py            迁移后只保留事件业务适配

services/lan_input_sync/
  SessionCapabilities        能力集合，不再使用 DataOnly 二元标志
  PeerTrustStore             持久信任和撤销
  SessionMultiplexer         一个 peer session 的多路复用
  CapabilityRouter           能力授权和消息路由
```

业务最终只依赖通信接口：

```text
features/follow
  -> position.publish / position.subscribe / event.subscribe

features/event
  -> event.publish / event.subscribe / catalog.*

features/map
  -> map.publish / map.subscribe

features/input
  -> input.send / input.receive
```

## 9. 迁移阶段

### 阶段 0：建立可回退基线

- 保留 `pre-reorg/2026-09-18`。
- 为通信重构建立独立分支和新的工作基线提交。
- 记录当前 Python 回归结果和 C# 构建环境限制。

### 阶段 1：抽取通用通信契约

- 新增 `core/communication` 契约、topic、能力和 QoS 模型。
- `SharedPosition`、`SharedEvent` 迁移或兼容到通用通信契约。
- 不改变现有网络协议和业务行为。
- 为契约编写纯单元测试。

### 阶段 2：建立进程级 CommunicationManager

- 在 bootstrap/UI composition 中创建一个 manager。
- 将同一个 manager 注入 FollowService、EventWorkbenchService 和地图功能。
- 统一 Host 客户端和接收循环。
- 先兼容现有 `sync.share.*` 命令。
- 消除多个业务各自 drain 同一队列的问题。

### 阶段 3：引入持久信任和自动重连

- 抽取 trust store、revocation store 和 capability preferences。
- 配对只在首次信任或证书更换时发生。
- 已信任 peer 自动连接和自动重连。
- 为重连和证书变更增加状态展示及诊断。

### 阶段 4：C# session 能力化

- `Session.DataOnly` 改为能力集合。
- `start` 和 `start-data` 统一为能力协商。
- 输入、位置、事件可以在同一 peer session 并行。
- 保留旧命令一段过渡期，旧客户端映射到兼容能力集合。

### 阶段 5：预留地图同步扩展点

- 只定义 `map` capability、topic、QoS 类型和扩展接口，不实现地图传输业务。
- 为未来的 manifest、chunk、commit、request、cancel 保留协议版本空间。
- 加入“未知 map 消息不影响其他 topic”的兼容性测试。
- 地图完成后再单独立项实现，不改变位置、事件和输入通道。

### 阶段 6：迁移业务和删除旧入口

- FollowService 只申请跟随所需能力。
- EventWorkbenchService 只申请事件所需能力。
- 地图功能只申请地图能力。
- 删除业务自行创建 `VirtualGamepadClient`、自行维护 LAN session 的路径。
- 旧 `FollowTransport` 和 `HostEventBridge` 收敛为薄业务适配器或删除。

## 10. 验证计划

### 纯模块测试

- 能力租约申请、释放和重复申请。
- 多业务共享同一 peer session。
- 一个业务关闭不影响其他订阅者。
- topic 分发不会重复或丢失消息。
- 实时、可靠、有序、版本化 QoS 行为。
- trust store 序列化、撤销和证书指纹变化。

### Loopback 测试

- 首次配对需要配对码。
- 已配对设备重启后不需要配对码。
- 证书未变时自动重连成功。
- 证书变更时自动连接被拒绝并要求重新确认。
- A 同时向 B/C 发布事件、位置和地图版本。
- B/C 独立断开，其他 peer 不受影响。
- 事件和位置不会互相消费。
- 地图大块传输不会阻塞实时位置。

### 安全测试

- 未信任设备不能获取 session。
- 旧 session 的消息不能注入新 session。
- 撤销设备无法自动重连。
- 输入能力断线后回中。
- 旧的 Controller owner 不能通过重连重新夺权。

### 实机测试

只有明确请求时执行：

- 多设备真实配对和断线重连。
- A -> B/C 事件广播。
- 位置共享和跟随。
- 地图版本同步。
- Host 实际输入和游戏内效果。

## 11. 主要风险

1. **协议迁移风险**：C# 服务和 Python 客户端必须有兼容期，不能一次删除旧命令。
2. **队列消费风险**：必须由通信运行时统一读取，再向订阅者分发，业务不得直接 drain。
3. **输入安全风险**：能力复用不能改变 Controller 独占和急停语义。
4. **持久信任风险**：证书轮换不能自动信任，否则持久化连接会削弱安全边界。
5. **地图资源风险**：地图块必须限制大小、数量和总缓存，避免占满内存或磁盘。
6. **多进程风险**：Follow 的 actor worker 仍可能需要独立的本机程序输出客户端；这不等于它们可以各自创建 LAN session，二者必须区分。

## 12. 已确认决策

1. 采用“一台设备一个持久信任关系、一个 peer 一个物理 session、多个逻辑能力”的总模型。
2. 允许输入、位置、事件和未来地图能力在同一 peer session 中并行。
3. 普通断线和进程重启后自动恢复已授权能力；用户手动断开、手动停止、忘记设备或急停后不自动恢复。
4. 当前不实现地图同步，只保留可插拔扩展点，地图完成后可以快速接入。
5. 采用分阶段路线：先统一 Python 通信管理器，再升级 C# session 多路复用协议。

本设计已通过审核。下一步按独立实施计划执行；在实施计划确认前不修改生产代码。
