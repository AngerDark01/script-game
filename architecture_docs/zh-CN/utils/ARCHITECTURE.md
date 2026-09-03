# Probe 和 Diagnostics 架构

## 系统角色

`utils` 包含 standalone probes 和 diagnostics。它们应该是生产模块周围的验证 adapters，而不是生产算法的分叉实现。

## 当前模块

| 模块 | 当前角色 | 重构视角 |
| --- | --- | --- |
| `event_icon_probe.py` | Offline/live minimap event icon probe。 | 应调用生产 detector components，并输出可复现结果。 |
| `portal_screen_probe.py` | Live/main-view portal confirmer probe。 | 应调用生产 main-view confirmer logic。 |
| `input_probe.py` | Input/click diagnostics。 | 应测试 `InputDriver` 和 `MotionController` 行为，不复制 click policy。 |
| `route_context_probe.py` | Route projection/progress inspection。 | 应调用 `RouteContext` 行为。 |
| `navigation_task_probe.py` | Unified task list inspection。 | 应调用 task builder/scheduler contracts。 |

## 已验证 Probe 模式

### `input_probe.py`

当前角色：比较真实 mouse input strategies 是否被游戏接受，并打印 diagnostics。

已验证行为：

- 设置 process DPI awareness，使用 physical coordinates。
- 默认 dry-run；真实输入需要 `--execute`。
- 可用 `--restart-admin` 以管理员权限重启。
- 收集 target point、DPI awareness、admin status、pydirectinput size/position、Win32 cursor、clip cursor rectangle、target window、foreground window。
- 支持多种 input strategies：
  - direct `pydirectinput.click(x, y)`；
  - raw Win32 `SetCursorPos + mouse_event`；
  - `pydirectinput.moveTo + click`；
  - `pydirectinput` hold；
  - `InputDriver.move_to + pydirectinput`；
  - `InputDriver.click()`。

架构规则：

- 这个 probe 可以包含多种替代 input strategies，因为它的职责是 adapter discovery。
- 生产 navigation 不应复制这些分支；应通过 `MotionController` 和选中的 command sink 执行。

### `event_icon_probe.py`

当前角色：在 live captures 或 saved images 上验证 minimap event icon detection。

已验证行为：

- 从 `map_data/<map>/config.json` 读取 map capture config。
- 从 `monitor_region` 或 logical center + DPR 构建 capture geometry。
- 复用生产 detector pieces：
  - `core.events.detectors.template_matcher`
  - portal minimap feature matcher
  - portal shape/color matcher
  - portal color check
- 写 raw frames、annotated matches、shape/color masks、candidate crops。
- 打印 accepted/rejected candidate diagnostics，包括 scores 和 reasons。

架构规则：

- CLI parsing、debug drawing、artifact writing 留在 probe。
- Detector math 留在 `core/events/...`。

### `portal_screen_probe.py`

当前角色：验证 main-view portal confirmer logic。

已验证行为：

- 捕获 explicit rect、full screen 或根据 title/class 找到的 game window。
- 复用生产 window finder 和 portal main-view confirmer functions。
- 写 metadata、raw frames、masks、annotated candidate images。
- 打印 strict-acceptance diagnostics。

架构规则：

- Probe-specific threshold CLI 可以保留；如果某组 threshold 成为生产默认值，应保存为 config assets。

### `route_context_probe.py`

当前角色：检查一个地图的 guide anchors route progress。

已验证行为：

- 读取 `map_data/<map>/route.json`。
- 用 guide points 构建生产 `RouteContext`。
- 打印 guide anchor progress、required point progress、exit-region center progress。

架构规则：

- 形态很好：progress math 全在 `RouteContext`；probe 只加载 route data 和打印值。

### `navigation_task_probe.py`

当前角色：检查一个地图生成的 navigation tasks。

已验证行为：

- 读取 `map_data/<map>/route.json`。
- 构建生产 `RouteContext`。
- 调用 `NavigationTaskBuilder().build()`，传入 route data、空 event tasks、空 completed-required set。
- 打印 task id、kind、target、route progress。

架构规则：

- 保持为窄 task-builder adapter。
- 如果要加入 event tasks，使用生产 `EventTask` DTO 或 fixtures，不要 ad hoc dict。

## 重构规则

当 probe 中出现有用算法逻辑时，把算法移到 `core`，让 probe 只负责传参、写 debug files、打印结果。

## Probe-to-Hook 关系

probes 目前打印的数据，未来应通过 hooks 获得：

- Input hooks 应暴露 command、requested/final screen position、backend、target window、cursor before/after、skipped reason、fallback exception。
- Event detector hooks 应暴露 candidates、accepted/rejected state、score breakdown、debug artifact paths。
- Navigation task hooks 应暴露 selected task、generated intent、click suppression reason、route progress。

不要让 probes import GUI widgets。使用生产 core adapters，并写 standalone outputs。

## 当前状态

状态：partial。已阅读主要 input/event portal probes 和 route/task probes。Probe output formats 未做穷尽式文档，但生产依赖方向已映射。

