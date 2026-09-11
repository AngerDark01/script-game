# 自动跟随系统：局域网位置共享与事件链设计

## 目标

在同一局域网内共享 B 端领航位置、地图状态和控制事件。通信模块只负责可靠传输与授权，不直接决定寻路；A 端收到消息后由跟随状态机和事件链执行。

## 角色与连接

### B 端（领航端）

- 人工操作游戏，不启用虚拟手柄映射。
- 持续发布自己的大地图坐标、置信度、地图 ID/版本、时间戳和序号。
- 通过工作台开关发送行为事件。

### A 端（跟随端）

- 接收并校验 B 的位置和事件。
- 同一台电脑上的 A1/A2 使用各自定位、规划和 Controller 1/2。
- 位置过期、地图版本不一致或连接失效时进入安全停止。

## 位置消息

```json
{
  "type": "leader_position",
  "device_id": "B-001",
  "map_id": "map-01",
  "map_version": "v3",
  "x": 12540.2,
  "y": 8340.7,
  "confidence": 0.94,
  "timestamp": 1720000000000,
  "sequence": 1821
}
```

接收端按 `sequence` 丢弃旧包，按 `timestamp` 检查新鲜度；位置缓存只保留最新值。建议位置通道可靠、有序，普通状态通道可允许丢包但必须带序号。

## 行为事件

事件统一采用可扩展信封：

```json
{
  "type": "behavior_event",
  "event_id": "evt-1822",
  "name": "start_follow",
  "source": "B-001",
  "timestamp": 1720000000100,
  "payload": {},
  "sequence": 1822
}
```

第一版内置事件：

- `start_follow`：A1/A2 重新定位、生成目标并独立规划；
- `pause_follow`：停止输出并回中摇杆；
- `return_home`：停止跟随并执行配置化 Xbox 回城动作；
- `emergency_stop`：立即停止全部控制器；
- `resume_follow`：从当前位置重新定位后恢复，不能复用旧路径。

## 事件开关

B 端工作台为每个事件提供：

- 启用/禁用开关；
- 快捷键或 UI 按钮；
- 发送目标（指定 A 设备/全部已授权设备）；
- 是否需要二次确认；
- 重复触发策略（拒绝、覆盖、排队）；
- 发送后本地反馈和日志。

A 端为每个事件提供接收开关和安全策略。例如可以关闭 `pause_follow` 的远程控制，但 `emergency_stop` 默认不可关闭。

## 自定义事件与事件链

用户可在工作台创建自定义事件，并加入事件链：

```text
事件链：刷图完成
  1. stop_follow
  2. wait(300ms)
  3. return_home
  4. wait_scene("town", timeout=30s)
  5. notify("已回城")
```

事件链节点类型：

- `send_event`：发送一个行为事件；
- `wait`：等待固定时间；
- `wait_condition`：等待位置、场景、置信度或网络条件；
- `branch`：按条件选择分支；
- `repeat`：有限次数重试；
- `stop_controller` / `start_controller`：控制 A1/A2；
- `notify`：写入日志、更新 UI 或提示用户。

每条事件链具有唯一 ID、版本、启用状态和失败策略。失败策略可选停止链、跳过节点、重试或触发紧急停止。

## 事件优先级与冲突

```text
emergency_stop
  > network_timeout / localization_lost
  > return_home
  > pause_follow
  > resume/start_follow
  > custom_event
```

高优先级事件可取消低优先级链；同一事件重复发送使用 `event_id` 去重。回城期间拒绝新的普通跟随事件，除非用户明确执行 resume。

## 配置结构

```json
{
  "lan": {"role": "leader", "peer_device_id": "A-001"},
  "event_switches": {"start_follow": true, "return_home": true},
  "event_chains": [
    {"id": "map_finished", "version": 1, "enabled": true, "nodes": []}
  ]
}
```

配置由工作台编辑、校验、保存和版本化，不要求用户手动修改 JSON。

## 安全与故障处理

- 设备码配对后才接受位置和事件；未知设备全部拒绝。
- 地图 ID/版本不一致时显示告警并禁止自动移动。
- 超过位置 TTL 未收到新位置，A1/A2 回中并进入等待。
- 网络恢复后不自动沿用过期路径，必须重新定位和规划。
- 所有事件、确认、失败和恢复动作写入统一事件日志。
