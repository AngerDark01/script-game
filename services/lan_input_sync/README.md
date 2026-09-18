# 局域网手柄同步模块

独立 C#/.NET 8 类库，固定使用 LiteNetLib 2.1.4。只依赖标准 Xbox 状态契约，不引用手柄宿主、ViGEm、键鼠捕获、Python、UI 或游戏。现有宿主负责调用本库，并把 `Consume` 的结果提交到虚拟手柄。

```
本机有效手柄报告 → Publish → TLS 配对 / 加密 UDP → Consume → 接收机手柄后端
工作台面板       → 本机管道 → Handle(sync.*)
```

## 实现范围

- 一台发送设备连接多台接收设备；每个接收设备可独立选择 Controller 1/2。
- 固定端口上的 UDP 广播发现；未发现时使用局域网 IPv4 地址配对。默认 TCP/UDP 45873，绑定面板选择的具体 IPv4 网卡地址。
- 8 位一次性配对码（5 分钟）及双方人工确认同一校验指纹。校验指纹绑定两张证书和本次双方随机挑战。
- 首次确认后固定证书指纹；后续 TLS 连接校验证书。TLS 只处理配对、会话和权限，不能访问宿主的任意动作命令。
- 每个会话使用新随机标识及双向独立 AES-256-GCM 密钥；实时消息认证后检查通道序号。
- 摇杆/扳机快照使用 Sequenced，按钮变化使用独立 ReliableOrdered 通道。快速按下/松开各占用至少一次 `Consume` 输出报告。
- 接收端两个槽位独立授权；本地暂停/恢复旋转槽位授权令牌，旧网络包不能重新开启输出。F9、断线和超时撤销会话。
- 状态、源报告、可靠按钮积压及挑战/回应均采用单调时钟超时。默认 200ms；输出路径自身也检查超时，网络线程停顿时仍能归零。
- 按钮、配对、设备发现、待确认消息和磁盘写入均设上限。磁盘保存使用独立串行线程，不阻塞网络轮询或宿主报告。

LiteNetLib 的 `Unreliable` 不保留独立通道编号，因此健康探测使用两个独立 Sequenced 通道。按钮接收确认会在后续健康回应中累计携带，单次确认包丢失不会造成永久积压。

## 宿主接口

```csharp
using var sync = new LanSyncService();
sync.Publish(1, new PadState(LeftStickY: short.MaxValue), enabled: true);
// 实际宿主需在每次报告中重复 Publish，不能只在状态变化时调用。
if (sync.OwnsController(1))
    backend.Submit(sync.Consume(1)); // 每个槽位每个实际输出周期仅调用一次
```

`OwnsController` 表示接收模式预留槽位；`IsRemoteEnabled` 表示本机允许接收；`IsRemoteActive` 表示收到有效、已启用的源报告。中立值也可处于 Active，不能按摇杆是否非零判断是否正在同步。

`Peek` 是不消耗按钮队列的只读方法。宿主也可缓存上一份 `Consume` 结果供 UI 展示。接收模式下应停用该槽位本地键鼠映射拦截，本库自身不会安装键盘或鼠标钩子。

启动默认 `off`，历史配对和偏好可保留，但接收许可及运行会话不持久化。界面应等到 `status.networkReady == true` 才发起配对或开始。

## 面板管理协议

返回值为 `{ok:true,status:{...}}` 或 `{ok:false,error:"...",status:{...}}`。连接和保存操作后台执行，异步失败见 `status.error` / `peers[].error`。

| 命令 | 参数 | 行为 |
|---|---|---|
| `sync.status` | `{}` | 查询状态，不消耗输入 |
| `sync.configure` | `mode,name,bindAddress,port,controllers,rateHz` | mode 为 off/send/receive；controllers 为 [1]、[2] 或 [1,2]；rateHz 为 60 或 125。重新配置会先停止会话 |
| `sync.pairing` | `{}` | 开放一次限时配对，显示设备码 |
| `sync.pair` | `address,port,code` | 从发送端发起配对 |
| `sync.confirm` | `requestId,allow` | 两端分别核对指纹后确认；allow=false 拒绝 |
| `sync.start` | 发送端 `deviceId,controllers`；接收端 `controllers` | 接收端先授权，发送端再开始 |
| `sync.stop` | 可选 `deviceId` | 停止指定设备或全部同步；接收端同时撤销本地接收许可 |
| `sync.forget` | `deviceId` | 先停止会话，再删除信任记录 |

状态包含 `mode,networkReady,deviceId,name,bindAddress,addresses,port,rateHz,pairingCode,pairingExpiresUtc,controllers,remoteEnabled,peers,discovered,pending,error`。

- peers: `{deviceId,name,address,port,connected,syncing,connecting,controllers,rttMs,error}`。
- discovered: `{deviceId,name,address,port}`。
- pending: `{requestId,deviceId,name,fingerprint,incoming,confirmed}`。

## 存储和部署

默认每台电脑、每个 Windows 用户独立保存到 `%LOCALAPPDATA%/AutoModules/LanInputSync`：`identity.dpapi`、`preferences.json` 和 `trusted.json`。身份私钥由当前用户的 Windows DPAPI 保护；Schannel 使用临时导入的用户密钥容器。不要将该目录复制到其他电脑，也不要随安装包发布。

工作台统一启动现有宿主，宿主通过项目引用自动携带类库及 LiteNetLib。防火墙应只允许所选程序/端口的专用网络和本地子网；此类库不会自行创建防火墙规则。两端默认使用相同端口便于广播发现。访客 Wi-Fi 隔离、网卡变化和禁止广播的网络需要先解决网络可达性，或使用手动地址入口。本机网卡列表在宿主启动时缓存，网卡改变后需要重启宿主；已配对设备的 DHCP 地址改变后，当前版本需要用新地址重新配对以更新保存的地址。

## 验证

```powershell
& D:/ACloud/dotnet-sdk2/dotnet.exe test D:/ACloud/auto_modules/services/lan_input_sync/tests/LanInputSync.Tests/LanInputSync.Tests.csproj
```

当前 19 个测试通过，覆盖同机真实 TLS / LiteNetLib 双实例及三实例回环、多目标独立槽位、短按、发送端/接收端暂停、F9、源进程退出、错误设备码、单边确认不授信、证书替换、认证篡改/重放、旧 epoch、状态失联、源报告线程停顿、接收网络线程停顿、可靠按钮积压超时、全新会话恢复、配置与紧急停止竞态。多接收端测试同时验证一台停顿时另一台仍可更新，以及停止/移除指定设备不会取消其他设备正在建立的连接。

这些是同机进程内多实例网络测试，不代表两台实体电脑上的游戏测试已完成。实体局域网自动发现、防火墙体验、有线/Wi-Fi 延迟分位数、随机物理丢包/重传、四接收端和长时间运行仍需在实际设备验证。未宣称单向延迟、p95 或游戏内短按采样达标。网络故障注入目前是确定性消息抑制/线程停顿，而非完整链路损伤模拟器。
