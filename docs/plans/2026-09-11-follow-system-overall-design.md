# 自动跟随系统：总体需求与技术栈

## 目标

在局域网双机环境中，B 端由玩家手工操作并持续发布位置/事件；A 端运行两个独立跟随角色。A1、A2 分别定位、规划、处理卡住并通过 Controller 1/2 的虚拟 Xbox 手柄输出移动。

## 范围

- 共享 B 的位置、地图标识、版本和控制事件。
- A 端同一张小地图内识别 A1/A2，角色由颜色或 ID 区分。
- 小地图局部墙体与全局地图进行局部范围配准，不做常态全局搜索。
- 两个角色独立执行跟随目标生成、A*、局部路径跟踪和 Xbox 输出。
- 支持 start_follow、pause、return_home、emergency_stop 等事件。

## 技术栈

- Python：工作台集成、进程编排、配置、OpenCV 定位、现有 A* 与动作适配器复用。
- OpenCV/NumPy：颜色/ID 检测、墙体边缘、相位相关/模板匹配、ROI 处理。
- 现有 `core/localization`、`core/routing/pathfinder`、`core/actions/gamepad` 与虚拟手柄宿主。
- 现有 LAN 同步传输层：LiteNetLib/TLS/设备码配对；位置消息使用序号、时间戳和地图版本。
- 有界队列/最新值缓存：定位、规划、网络和 Xbox 输出解耦。

## 性能目标

- 小地图采集 20–30 Hz；双标记检测 20–30 Hz。
- Xbox 输出 60–125 Hz，不被 OCR、地图匹配或网络阻塞。
- 正常运行不进行全局地图搜索；局部重定位目标延迟 <100 ms。
- 定位丢失时安全回中摇杆；两个角色互不拖累。

## 主要模块

```text
minimap_capture → local_map_registration → dual_marker_detector
                                      ├→ follower_controller_1 → Controller 1
                                      └→ follower_controller_2 → Controller 2
                         B position/event transport
```

## 安全边界

- 地图 ID/版本、坐标尺度或配准置信度不一致时禁止自动移动。
- 网络位置过期、场景切换或定位连续失败时停止对应角色。
- 所有停止路径都必须回中摇杆并清除旧命令。
