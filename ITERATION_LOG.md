# Iteration Log

## [SYNC] 2026-09-19 — 通信层重构任务 1-9

### A. SYNC 范围声明
**触发任务：** 按已审核通信层设计落地通用契约、共享 Host session、持久信任、能力集合和地图扩展点。
**直接变更文件：** `src/auto_modules/core/communication/*`、`src/auto_modules/application/communication/*`、`src/auto_modules/adapters/host/*`、`src/auto_modules/features/torchlight/follow/service.py`、`src/auto_modules/application/event_workbench/service.py`、`services/lan_input_sync/src/LanInputSync/*`、通信测试和协议文档。
**预计连带影响：** Follow/Event Workbench 的 Host 生命周期、`sync.share.*` drain 消费路径、C# LAN `Session` 能力授权、重连 fencing、CODEBASE 架构和协议说明。

### C. SYNC 结果
**连带重读文件：** `core/communication/*`、`application/communication/*`、`adapters/host/*`、
`application/event_workbench/service.py`、`features/torchlight/follow/service.py`、
`services/lan_input_sync/src/LanInputSync/{IdentityStore,PeerTrustStore,SessionCapabilities,LanSyncService*}.cs`。
**CODEBASE.md 更新内容：** 新增通信运行时模块职责、Follow/Event 数据流、C# 能力集合和风险登记。
**ARCHITECTURE_GUIDE.md / README.md / protocol-v1.md 更新内容：** 明确一个 peer 一个物理
session、多 capability 复用、持久信任/自动恢复 fence、旧命令兼容期和 map 扩展点边界。
**覆盖进度更新：** 本轮新增通信文件已完成针对性深读；C# 生产编译因当前机器无 .NET SDK
保持 `(partial)`，已通过源码审查和 Python fake/loopback 测试替代验证。
**修订的旧结论：** 原来 `DataOnly` 被视为 session 类型；现在确认它只是 capability 集合
在兼容期的派生视图，输入、位置和事件可以共享同一物理 session。
**新增 Finding：** P1 风险已记录在 CODEBASE.md：Host drain 字段兼容和 C# lane 前缀复用
需要后续协议版本收敛。

**本轮收尾复核（2026-09-19）：** 补读 `LanSyncService.Control.cs::RunControlsAsync`、
`LanSyncService.cs::Handle/ConfigureLocked/CloseLocked/Dispose`、`LanSyncService.Transport.cs::ReceivePacket`、
`IdentityStore.cs::Preferences`、`communication_adapter.py::pump/ensure_connected` 和对应 loopback/fake tests。
已修订“无 .NET SDK”的旧结论：系统默认 `dotnet` 不可用，但 `D:\ACloud\dotnet-sdk2\dotnet.exe`
可用，LAN 31 项和 Host 57 项全部通过。数据会话可在不换 sessionId 的情况下增加/移除输入；
无接收授权时返回拒绝并保留数据会话。正常进程重启恢复已信任 session，手动 stop 不恢复；
首轮恢复连接失败后继续退避，远端重新上线后自动连回；旧输入 watchdog 断线中立化契约
仍由全套 LAN 测试验证。权威 LAN 信任文件为
`trusted.json`/`preferences.json`，不是尚未接入运行时的 `PeerTrustStore`。
通信 Python 聚焦测试通过；全量 pytest 492 passed、2 skipped、4 failed，失败为缺少
`pydirectinput` 发布依赖和 3 项独立 Pathfinder 测试，不纳入本轮通信变更。
**覆盖状态：** 本轮上述函数体和失败分支已深读；未重读的项目其余文件仍保持原有覆盖状态。


## [SYNC] 2026-09-19 19:32 — 离线可信节点持续重连

### A. SYNC 范围声明
**触发任务：** 通信线程完成后遗留的离线可信节点重连修复收尾。
**直接变更文件：** `LanSyncService.Control.cs`、`LanSyncService.cs`、`LoopbackTests.cs`、`CODEBASE.md`。
**预计连带影响：** 出站连接失败后的退避调度、成功连接后的退避复位、可信节点恢复 Flow 及 LAN loopback 测试。

### C. SYNC 结果
**连带重读文件：** `LanSyncService.Control.cs`、`LanSyncService.cs`、`LoopbackTests.cs`、`CODEBASE.md`。
**CODEBASE.md 更新内容：** §5 补全 `RunControlsAsync()` 与持续重连算法、失败行为和副作用；可信节点恢复 Flow 明确失败重调度与成功复位退避。
**覆盖进度更新：** 上述变更函数和新增 loopback 测试已重读；LAN 测试使用私有 .NET 8 SDK 验证为 `31 passed`。
**新增 Finding：** 离线节点首次重连失败后必须保留恢复资格并再次进入有界退避；延迟回调还需以 generation、startVersion 和 `_connecting` 三重栅栏防止过期连接复活。

## [Round 1] 2026-05-19

### A. 本轮目标（阅读前声明）
**目标文件：**
- `README.md`（原因：确认项目运行方式和整体目标）
- `main.py`（原因：确认应用入口、共享上下文初始化）
- `gui/app_context.py`（原因：确认跨模块共享服务，尤其 PathFinder、截图、追踪器）
- `gui/main_window.py`（原因：确认模式切换入口）
- `gui/navigation_params.py`（原因：确认导航参数模型，后续移动映射参数需要落在这里）
- `gui/dialogs/nav_params_dialog.py`（原因：确认参数 UI 如何读写 NavConfig）
- `gui/modes/navigation_mode.py`（原因：当前自动导航、监控框、点击触发主链路所在文件）
- `core/auto_navigator.py`（原因：确认自动导航何时请求移动点击）
- `core/motion_controller.py`（原因：当前地图向量到屏幕点击坐标的转换实现）
- `core/navigation_core.py`（原因：确认定位输出坐标和 draw_scale/crop_offset 关系）
- `core/pathfinder.py`（原因：确认 A* 输出路径坐标体系）
- `core/stitcher_core.py`（原因：确认建图 draw_scale/坐标体系来源）

**本轮想弄清楚：**
- 自动导航点击链路中，哪些坐标是地图全局坐标，哪些坐标是屏幕物理像素。
- 当前“地图距离线性映射到屏幕点击距离”的参数来源，以及为什么会导致点击距离太短。
- 新增“人物真实可见/可交互范围框”和点击半径参数应放在哪些模块，避免污染定位一致性。

### Coverage
| 文件 | 状态 | 阅读次数 | 备注 |
|------|------|---------|------|
| `README.md` | PENDING | 0 | 项目概览与运行方式待确认 |
| `main.py` | PENDING | 0 | 应用入口待确认 |
| `gui/app_context.py` | PENDING | 0 | 共享上下文待确认 |
| `gui/main_window.py` | PENDING | 0 | 模式切换待确认 |
| `gui/navigation_params.py` | PENDING | 0 | 导航参数模型待确认 |
| `gui/dialogs/nav_params_dialog.py` | PENDING | 0 | 参数 UI 待读 |
| `gui/modes/navigation_mode.py` | PENDING | 0 | 导航主链路待读 |
| `gui/modes/mapping_widget.py` | PENDING | 0 | 建图 UI 后续如需对齐时再读 |
| `core/auto_navigator.py` | PENDING | 0 | 自动导航状态机待读 |
| `core/motion_controller.py` | PENDING | 0 | 鼠标点击映射待读 |
| `core/navigation_core.py` | PENDING | 0 | 定位坐标系待读 |
| `core/pathfinder.py` | PENDING | 0 | 路径输出坐标系待读 |
| `core/stitcher_core.py` | PENDING | 0 | 建图坐标系待读 |
| `core/path_utils.py` | PENDING | 0 | 路径平滑/投影工具后续如需再读 |
| `core/route_manager.py` | PENDING | 0 | 路线持久化后续如需再读 |
| `tests/test_auto_navigator.py` | PENDING | 0 | 自动导航测试后续同步 |
| `tests/test_path_utils.py` | PENDING | 0 | 路径工具测试后续同步 |
| `tests/test_route_manager.py` | PENDING | 0 | 路线管理测试后续同步 |

### C. 本轮发现
**关键发现：** (verified) 导航系统有三套必须分离的坐标概念：小地图截图范围用于定位，地图全局坐标用于路线/A*，真实主画面点击范围用于鼠标控制。原 `MotionController._calculate_target_screen_position()` 直接执行 `screen_delta = map_delta * movement_scale_factor`，当自动导航子目标较近时会把点击落在人物脚下附近，导致“点击了但不走”或移动过短。

**修订的旧结论：** 原来把 `movement_scale_factor` 当作唯一移动映射参数；现在确认它不足以同时表达“方向”和“最低点击触发距离”。新增最小/最大点击半径后，`movement_scale_factor` 只负责原始距离估算，最终屏幕点击距离会被夹到可交互半径范围内。

**新疑问：** (partial) 默认 `game_view_map_size=520`、`movement_min_click_radius=180`、`movement_max_click_radius=360` 需要用户在真实游戏内通过橙色框和日志 `click r` 校准。

**更新了 CODEBASE.md：** §1、§2、§3、§4、§5、§6、§8、§9。

**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `README.md` | PENDING | 浅读 | 1 | 确认项目是 PySide6 + OpenCV 小地图拼接/导航工具，README 文字存在编码显示问题 |
| `main.py` | PENDING | 浅读 | 1 | 确认入口仅创建 QApplication 和 MainWindow |
| `gui/app_context.py` | PENDING | 浅读 | 1 | 确认共享 ScreenCapture、MapStitcher、PlayerTracker、PathFinder |
| `gui/main_window.py` | PENDING | 浅读 | 1 | 确认 MappingWidget 与 NavigationModeWidget 共享 AppContext |
| `gui/navigation_params.py` | PENDING | 深度完整 | 1 | 确认 NavConfig 是地图 config.json 的导航契约，已新增真实可见框和点击半径参数 |
| `gui/dialogs/nav_params_dialog.py` | PENDING | (partial) | 1 | 确认参数 UI 的 widget_map/dataclasses.replace 流程，已接入新增参数；全量 UI 细节未覆盖 |
| `gui/modes/navigation_mode.py` | PENDING | (partial) | 1 | 确认自动导航主循环、监控框、鼠标点击触发链路，已新增橙色真实可见框；文件很大仍需后续继续清理编码文本 |
| `core/auto_navigator.py` | PENDING | 深度完整 | 1 | 确认状态机只输出 map-space 子目标和 issued_click，不直接处理屏幕点击距离 |
| `core/motion_controller.py` | PENDING | 深度完整 | 1 | 已从线性距离映射改为方向归一化 + 最小/最大屏幕点击半径夹紧 |
| `core/navigation_core.py` | PENDING | (partial) | 1 | 确认定位输出为 draw_scale 下的地图全局坐标，定位逻辑不应承担主画面点击映射 |
| `core/pathfinder.py` | PENDING | 深度完整 | 1 | 确认 A* 输入输出都是地图全局坐标 |
| `core/stitcher_core.py` | PENDING | (partial) | 1 | 确认建图保存 wall_layer/current_pos/canvas_size，draw_scale 是地图坐标基准 |
| `core/path_utils.py` | PENDING | 浅读 | 1 | 确认路径投影/插值用于 AutoNavigator 子目标选择 |
| `tests/test_auto_navigator.py` | PENDING | 浅读 | 1 | 确认 issued_click/cooldown 行为已有测试 |
| `tests/test_motion_controller.py` | 新增 | 深度完整 | 1 | 新增点击半径夹紧测试，覆盖短距离、长距离、零距离 |

**下一轮计划：** 如果真实测试仍出现“点了不走”，下一轮优先读取 `core/input_driver.py` 和 `pydirectinput` 调用环境，判断是点击坐标问题还是游戏窗口未接收点击。

## [SYNC] 2026-05-19 - 自动导航点击映射和真实可见框

### A. SYNC 范围声明
**触发任务：** 用户指出自动导航鼠标点击映射太短，需要整体理解项目后正确修改。

**直接变更文件：**
- `gui/navigation_params.py`
- `gui/dialogs/nav_params_dialog.py`
- `gui/modes/navigation_mode.py`
- `core/motion_controller.py`
- `tests/test_motion_controller.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：** `NavigationModeWidget._apply_config_to_core()` 将新增参数传入 `MotionController.set_params()`；`navigation_loop()` 每次定位后更新绿色小地图截图框和橙色真实可见框；`MotionController.move_to_map_target()` 的点击坐标从线性短距离映射变为方向点击半径夹紧。

### C. SYNC 结果
**连带重读文件：** `gui/navigation_params.py`、`gui/dialogs/nav_params_dialog.py`、`gui/modes/navigation_mode.py`、`core/motion_controller.py`、`core/auto_navigator.py`。

**CODEBASE.md 更新内容：** 补充导航/移动控制架构、关键函数算法、数据流、NavConfig 新契约和风险登记。

**覆盖进度更新：** `core/motion_controller.py`、`gui/navigation_params.py`、`tests/test_motion_controller.py` 达到本任务深度完整；`navigation_mode.py` 和参数对话框为本次影响范围完整、全文件仍标 partial。

**新增 Finding：** P1 风险 `MotionController._calculate_target_screen_position()` 的半径默认值需要真实游戏校准，否则可能仍点得过近或过远。

## [SYNC] 2026-05-19 - 橙色真实可见框即时刷新

### A. SYNC 范围声明
**触发任务：** 用户反馈修改 `真实可见范围(地图像素)` 后导航页面橙色框没有马上变化，仍显示旧的 520。

**直接变更文件：**
- `gui/modes/navigation_mode.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：** 参数面板发出 `parameters_changed` 后，导航页不仅更新内存配置和幕布，还会立即刷新橙色真实可见框；保存配置后也会刷新橙色框，避免重新应用配置后显示旧尺寸。

### C. SYNC 结果
**连带重读文件：** `gui/modes/navigation_mode.py`、`gui/dialogs/nav_params_dialog.py`、`gui/navigation_params.py`。

**CODEBASE.md 更新内容：** 补充 `_refresh_game_view_rect_from_known_position()` 的即时刷新职责；更新参数保存/加载 Flow。

**覆盖进度更新：** `gui/modes/navigation_mode.py` 对橙色框刷新链路已深读，整文件仍保持 partial。

**修订的旧结论：** 原以为调参不生效可能是配置字段未更新；现在确认字段会进入内存配置，但旧代码只在导航循环中刷新橙色框，因此导航未跑或下一帧未到时会停在旧矩形。

## [SYNC] 2026-05-19 - 自动估算点击半径

### A. SYNC 范围声明
**触发任务：** 用户反馈 2K 屏幕下 `movement_scale_factor=10` 仍然点击很短，需要自动检测/对比大小。

**直接变更文件：**
- `gui/dialogs/nav_params_dialog.py`
- `gui/modes/navigation_mode.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：** 参数面板新增“自动估算点击半径”按钮；根据已校准的 `game_screen_center` 和所在屏幕物理边界估算最小/最大点击半径。自动导航状态栏显示 `click r/raw`，便于判断点击是否被最大半径夹住。

### C. SYNC 结果
**连带重读文件：** `gui/dialogs/nav_params_dialog.py`、`gui/modes/navigation_mode.py`、`gui/navigation_params.py`。

**CODEBASE.md 更新内容：** 补充 `NavParametersDialog._auto_estimate_click_radius()` 和状态栏 click radius 诊断。

**覆盖进度更新：** `gui/dialogs/nav_params_dialog.py` 对运动控制参数区域已深读；全文件仍保持 partial。

**修订的旧结论：** 运动映射系数调到 10 仍很小不是比例没生效，而是 `movement_max_click_radius=120` 把最终点击半径限制住了。

## [SYNC] 2026-05-19 - 自动导航点击窗口焦点修复

### A. SYNC 范围声明
**触发任务：** 用户观察到鼠标已经移动/点击，但鼠标图标是普通系统光标，说明点击落在工具窗口或非游戏窗口，而不是游戏窗口。
**直接变更文件：**
- `core/input_driver.py`
- `core/motion_controller.py`
- `gui/modes/navigation_mode.py`
- `tests/test_motion_controller.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：** 自动导航点击前主窗口不再保持置顶并会下沉；运动控制优先使用 Win32 输入驱动激活点击坐标下的窗口并执行按下/抬起点击；点击坐标会被夹到物理屏幕范围内。

### C. SYNC 结果
**连带重读文件：** `core/input_driver.py`、`core/motion_controller.py`、`gui/main_window.py`、`gui/selection/indicator_overlay.py`、`gui/modes/navigation_mode.py`。
**CODEBASE.md 更新内容：** 新增 Input Control Current Notes，记录 `InputDriver`、`MotionController` 和 `_set_game_input_window_mode()` 当前职责。
**覆盖进度更新：** `core/input_driver.py` 已纳入自动导航点击链路；`core/motion_controller.py` 增加屏幕边界夹取、窗口聚焦和 InputDriver 优先点击；`gui/modes/navigation_mode.py` 增加自动导航期间主窗口取消置顶/下沉/恢复逻辑。
**修订的旧结论：** 之前认为“点击无效”主要可能是点击后端不被游戏接收；现在根据鼠标图标证据确认关键根因还包括 PySide 主窗口 `WindowStaysOnTopHint` 遮挡游戏窗口，导致点击目标窗口错误。

## [SYNC] 2026-05-20 - 点击后端回归修正

### A. SYNC 范围声明
**触发任务：** 用户反馈上一版修改后鼠标不再移动，说明把真实点击主后端切到 `InputDriver` 引入了新回归。
**直接变更文件：**
- `core/motion_controller.py`
- `gui/modes/navigation_mode.py`
- `tests/test_motion_controller.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：** 恢复 `pydirectinput` 为主移动/点击后端；`InputDriver` 只负责窗口聚焦、屏幕尺寸读取和失败后的兜底点击；自动导航只在启停时调整主窗口置顶状态，不再每次点击前重复下沉主窗口。

### C. SYNC 结果
**连带重读文件：** `core/motion_controller.py`、`tests/test_motion_controller.py`、`gui/modes/navigation_mode.py`。
**CODEBASE.md 更新内容：** 修正 Input Control Current Notes，明确 `pydirectinput` 是主后端，`InputDriver.click()` 只作为 fallback。
**覆盖进度更新：** `core/motion_controller.py` 的真实点击链路已恢复到已验证可移动鼠标的后端；测试改为断言 `InputDriver` 只聚焦窗口、不执行主点击。
**修订的旧结论：** 上一轮把“点击不在游戏窗口”的修复和“替换点击后端”绑定在一起是错误耦合；当前方案拆开处理：后端保持已验证可移动，窗口遮挡另行处理。

## [SYNC] 2026-05-20 - 恢复原始 pydirectinput 点击与信号警告修复

### A. SYNC 范围声明
**触发任务：** 用户反馈手动地图点击和自动寻路都不再移动鼠标，同时启动日志出现 PySide `disconnect` RuntimeWarning。
**直接变更文件：**
- `core/motion_controller.py`
- `tests/test_motion_controller.py`
- `gui/dialogs/nav_params_dialog.py`
- `ITERATION_LOG.md`

**预计连带影响：** 鼠标执行链路恢复为原始 `pydirectinput.click(x, y)`；窗口聚焦默认关闭，仅保留为可选能力；参数面板信号连接只建立一次，程序写 UI 值时用 `QSignalBlocker` 阻断信号，避免无效 disconnect 警告。

### C. SYNC 结果
**连带重读文件：** `core/motion_controller.py`、`tests/test_motion_controller.py`、`gui/dialogs/nav_params_dialog.py`。
**CODEBASE.md 更新内容：** 上一轮已记录 Input Control Current Notes；本轮以迭代日志修正：真实点击执行必须保持 `pydirectinput.click(x, y)`，不要替换为 moveTo/down/up 组合。
**覆盖进度更新：** `tests/test_motion_controller.py` 增加默认不聚焦窗口、可选聚焦窗口两个分支；`nav_params_dialog.py` 的重复 set_config_to_ui 已用 RuntimeWarning-as-error 脚本验证。
**修订的旧结论：** `pydirectinput.moveTo + mouseDown/mouseUp` 在用户环境中不能等价替代 `pydirectinput.click(x, y)`；恢复原始调用是当前稳定基线。

## [SYNC] 2026-05-20 - 运动点击确认阶段

### A. SYNC 范围声明
**触发任务：** 用户反馈鼠标能移动、图层正确，但游戏没有执行点击移动。
**直接变更文件：**
- `core/motion_controller.py`
- `tests/test_motion_controller.py`
- `ITERATION_LOG.md`

**预计连带影响：** 保留原始 `pydirectinput.click(x, y)` 作为第一阶段移动/点击，随后在当前鼠标位置补一次 `mouseDown/mouseUp` 确认点击；不改变地图到屏幕的映射算法。

### C. SYNC 结果
**连带重读文件：** `core/motion_controller.py`、`tests/test_motion_controller.py`。
**CODEBASE.md 更新内容：** 本轮以迭代日志补充：运动点击现在是两阶段，第一阶段定位到屏幕点，第二阶段确认按下/抬起。
**覆盖进度更新：** `tests/test_motion_controller.py` 覆盖默认确认点击和可选聚焦窗口两个分支。
**新发现：** 当前问题不在坐标映射，而在点击事件被游戏接收的可靠性；确认点击是最小侵入修复。
## [Investigation] 2026-05-20 - 鼠标移动/点击回归根因审查

### A. 本轮目标声明
**目标文件：**
- `core/motion_controller.py`：确认地图目标到屏幕点击的最终执行链路。
- `core/input_driver.py`：确认屏幕尺寸、窗口聚焦、Win32 点击是否影响坐标和鼠标移动。
- `gui/modes/navigation_mode.py`：确认手动地图点击和自动寻路如何触发 `MotionController`。
- `core/auto_navigator.py`：确认自动寻路是否真的发出 `issued_click=True`。
- `gui/navigation_params.py` 与地图 `config.json`：确认坐标参数、点击半径、屏幕中心是否存在逻辑/物理像素混用。
- `gui/dialogs/nav_params_dialog.py`：确认参数 UI 是否把移动参数实时写入运行时配置。

**本轮想弄清楚：**
- 为什么“原来鼠标会移动”变成“现在不移动/不点击”。
- 当前实现里是否存在 DPI 缩放、屏幕尺寸夹取、窗口下沉、自动导航状态、点击后端之间的矛盾。
- 联网核对 `pydirectinput` 和 Windows 输入/焦点的关键细节后，再给出修复方案。

### C. 本轮发现
**关键发现：** (verified) 当前进程里 `pydirectinput.size()`、`GetSystemMetrics(0/1)` 和 Qt 主屏幕逻辑尺寸均为 `1707x1067`，但 Qt `devicePixelRatio()` 为 `1.5`。这说明导航 UI/输入层看到的是逻辑坐标，截图层仍需要物理坐标。

**关键发现：** (verified/conflict) `NavigationModeWidget._on_screen_center_selected()` 把中心选择器返回的 Qt 逻辑坐标乘以 DPR 后保存到 `NavConfig.game_screen_center`，而 `MotionController._execute_click()` 又把该值直接传给 `pydirectinput.click(x, y)`。`pydirectinput` 内部用 `GetSystemMetrics()` 的逻辑尺寸把坐标归一化到 `SendInput`，因此当前链路存在“物理中心坐标传入逻辑输入 API”的坐标系冲突。

**关键发现：** (verified/conflict) `MotionController._clamp_screen_pos()` 用 `InputDriver.screen_width/screen_height` 把点击点夹到 `1707x1067` 内；但此前用户日志中已出现 `screen=(1987, 1476)` 这类超过逻辑边界的目标点。新增 clamp 会把这类点强行压到屏幕边缘，例如 `(1987,569)->(1704,569)`、`(1559,1469)->(1559,1064)`，改变原有鼠标移动轨迹。

**关键发现：** (verified) 自动寻路链路已经通过 `issued_click=True` 限制重复点击，手动地图点击和自动点击最终都调用同一个 `MotionController.move_to_map_target()`。因此“手动点击不移动”和“自动寻路不移动”的共同故障点在 `MotionController`/输入坐标层，不在 `AutoNavigator` 规划层。

**关键发现：** (verified) `pydirectinput.click(x, y)` 的实现是先 `moveTo(x,y)`，再发 `SendInput` 点击事件；`moveTo` 内部使用 `size()` 做绝对坐标归一化。后来新增的 `confirm_after_click` 只是补一次当前位置 down/up，不能修正坐标系错误；如果第一次移动位置错误，确认点击只会强化错误位置。

**修订的旧结论：** 之前把问题判断为“点击事件被游戏接收不可靠”不完整。当前更准确的结论是：先有坐标系/边界夹取回归导致移动目标错误或被夹到边缘；在此基础上再讨论窗口焦点和双击确认才有意义。

**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/motion_controller.py` | (partial) | (conflict) | 2 | 已确认 clamp、confirm、pydirectinput 坐标归一化之间存在冲突。 |
| `gui/modes/navigation_mode.py` | (partial) | (conflict) | 2 | 已确认校准中心保存为物理坐标，但点击执行使用逻辑输入 API。 |
| `gui/dialogs/nav_params_dialog.py` | (partial) | (conflict) | 1 | 自动估算点击半径当前按物理边界推导，不适合直接服务 `pydirectinput` 输入坐标。 |
| `core/input_driver.py` | (partial) | (conflict) | 1 | `GetSystemMetrics` 返回当前进程逻辑屏幕尺寸，被用于 clamp 后会改变物理/逻辑混用坐标。 |

**下一轮计划：** 修复顺序应先恢复单一坐标系和最小点击基线：`pydirectinput` 输入坐标统一使用 Qt 逻辑坐标；截图坐标继续使用物理坐标；禁用或重写 clamp/确认点击，等鼠标移动恢复后再处理游戏窗口焦点与点击接收。

## [SYNC] 2026-05-20 - 恢复鼠标移动基线并增加点击诊断

### A. SYNC 范围声明
**触发任务：** 用户要求先恢复正确鼠标移动，同时允许在点击链路打印诊断信息用于后续 debug。
**直接变更文件：**
- `core/motion_controller.py`
- `core/input_driver.py`
- `tests/test_motion_controller.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：** 默认执行链路恢复为单次 `pydirectinput.click(x, y)`，不再默认进行屏幕边界夹取和确认点击；保留可选 clamp/focus/confirm 能力；点击前后输出 pydirectinput 屏幕尺寸、鼠标位置、目标窗口信息和是否发生坐标夹取。

### C. SYNC 结果
**连带重读文件：** `core/motion_controller.py`、`core/input_driver.py`、`tests/test_motion_controller.py`。
**CODEBASE.md 更新内容：** 更新 Input Control Current Notes，明确默认移动基线是单次 `pydirectinput.click(x, y)`；clamp/focus/confirm 仅保留为显式调试开关；新增点击诊断日志说明。
**覆盖进度更新：** `core/motion_controller.py` 默认关闭 `clamp_to_screen` 和 `confirm_after_click`；`core/input_driver.py` 新增 `describe_window_at()` 输出 hwnd/pid/class/title；`tests/test_motion_controller.py` 覆盖默认不夹取、显式夹取、可选聚焦三条路径。
**验证：** `python -m py_compile core\motion_controller.py core\input_driver.py gui\modes\navigation_mode.py` 通过；`python -m unittest tests.test_route_manager tests.test_path_utils tests.test_auto_navigator tests.test_motion_controller` 通过，18 个测试成功。
**修订的旧结论：** 点击问题需要在移动基线恢复后再判断。当前代码不再默认改变目标坐标，也不默认追加第二次点击，因此下一次真实测试日志可以直接区分坐标映射问题和窗口接收问题。

## [SYNC] 2026-05-20 - 游戏窗口激活态鼠标捕获诊断

### A. SYNC 范围声明
**触发任务：** 用户日志显示目标点下方已经是 UnrealWindow，但 `cursor_after` 没有到达 `screen`，且点击切换到游戏窗口后移动/点击失效。
**直接变更文件：**
- `core/input_driver.py`
- `core/motion_controller.py`
- `tests/test_motion_controller.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：** 点击链路从 `pydirectinput.click(x, y)` 改为“Win32 `SetCursorPos` 放置鼠标 + `pydirectinput.click()` 当前点点击”；诊断日志增加前台窗口、ClipCursor 限制矩形、Win32 光标前后位置，用于判断 Unreal 激活后是否捕获/锁定鼠标。

### C. SYNC 结果
**连带重读文件：** `core/input_driver.py`、`core/motion_controller.py`、`tests/test_motion_controller.py`。
**CODEBASE.md 更新内容：** 更新 Input Control Current Notes，记录当前后端为 `setcursor+pydirectinput`，并记录新增 foreground/ClipCursor/Win32 cursor 诊断。
**覆盖进度更新：** `core/input_driver.py` 新增 `cursor_pos()`、`clip_cursor_rect()`、`foreground_window()`、`describe_window()`；`core/motion_controller.py` 先用 `InputDriver.move_to()` 放置鼠标，再用 `pydirectinput.click()` 当前点点击；`tests/test_motion_controller.py` 更新为断言 Win32 放置和当前点点击。
**验证：** `python -m py_compile core\motion_controller.py core\input_driver.py gui\modes\navigation_mode.py` 通过；`python -m unittest tests.test_route_manager tests.test_path_utils tests.test_auto_navigator tests.test_motion_controller` 通过，18 个测试成功。
**修订的旧结论：** 仅恢复单次 `pydirectinput.click(x, y)` 不足以诊断游戏激活态问题；当 UnrealWindow 成为目标/前台后，需要区分 `pydirectinput` 绝对移动失败、Win32 `SetCursorPos` 被 ClipCursor/游戏捕获改写、以及点击事件被游戏忽略三种情况。

## [SYNC] 2026-05-20 - 独立输入探针替代主流程试验

### A. SYNC 范围声明
**触发任务：** 用户指出应先用探针确认点击能真实作用到游戏，再修改项目主流程。
**直接变更文件：**
- `core/motion_controller.py`
- `core/input_driver.py`
- `tests/test_motion_controller.py`
- `utils/input_probe.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：** 主流程恢复为保守的 `pydirectinput.click(x, y)` 基线；新增 `utils/input_probe.py` 用于独立测试 `pydirectinput`、`SetCursorPos`、Win32 click、hold click 等策略。探针默认 dry-run，只有带 `--execute` 才会真实移动/点击。

### C. SYNC 结果
**连带重读文件：** `core/motion_controller.py`、`core/input_driver.py`、`utils/input_probe.py`、`tests/test_motion_controller.py`。
**CODEBASE.md 更新内容：** 修正主流程 backend 说明为 `pydirectinput.click(x, y)`；新增 Standalone Input Probe 章节。
**覆盖进度更新：** `core/motion_controller.py` 不再默认使用 `SetCursorPos`；`utils/input_probe.py` 提供 6 种可手动执行的输入策略；`core/input_driver.py` 保留窗口/ClipCursor/前台窗口诊断能力。
**验证：** `python -m py_compile core\motion_controller.py core\input_driver.py utils\input_probe.py tests\test_motion_controller.py` 通过；`python utils\input_probe.py --list-modes` 通过；`python utils\input_probe.py --x 100 --y 100` dry-run 通过；`python -m unittest tests.test_motion_controller` 通过。
**修订的旧结论：** `setcursor+pydirectinput` 不应直接进入主流程；它现在只是探针模式之一，等真实游戏验证后再决定是否集成。

## [SYNC] 2026-05-20 - 导航主程序管理员提权与 Win32 点击后端

### A. SYNC 范围声明
**触发任务：** 用户确认旧脚本必须管理员模式才可以真实点击游戏窗口，要求导航模式自动提权后执行点击。
**直接变更文件：**
- `main.py`
- `core/motion_controller.py`
- `tests/test_motion_controller.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：** 程序启动时先设置 DPI awareness；Windows 下非管理员启动会通过 UAC 重新拉起当前 Python/脚本并退出原进程；运动控制主后端切为旧脚本验证过的 Win32 `SetCursorPos + mouse_event`，`pydirectinput` 只作为失败兜底。

### C. SYNC 结果
**连带重读文件：** `main.py`、`core/motion_controller.py`、`tests/test_motion_controller.py`。
**CODEBASE.md 更新内容：** 更新外部集成和 Input Control Current Notes，记录管理员提权、DPI awareness、`win32_mouse_event` 主后端。
**覆盖进度更新：** `main.py` 新增启动前 DPI awareness 和 UAC relaunch；`core/motion_controller.py` 默认 `input_backend="win32_mouse_event"` 并调用 `InputDriver.click()`；`tests/test_motion_controller.py` 改为断言 Win32 driver click 是主路径。
**验证：** `python -m py_compile main.py core\motion_controller.py core\input_driver.py gui\modes\navigation_mode.py tests\test_motion_controller.py utils\input_probe.py` 通过；`python -m unittest tests.test_route_manager tests.test_path_utils tests.test_auto_navigator tests.test_motion_controller` 通过，18 个测试成功。
**修订的旧结论：** 主流程不再使用 `pydirectinput.click(x, y)` 作为首选真实点击；根据用户实测，管理员进程 + Win32 `mouse_event` 是当前应集成的点击基线。

## [SYNC] 2026-05-20 - A* 障碍失败时仍直接点击目标方向

### A. SYNC 范围声明
**触发任务：** 用户反馈 `[PathFinder] 起点在障碍物内` 不应阻止自动导航；游戏自身会越过/绕过障碍，只要程序持续点击正确方向即可。
**直接变更文件：**
- `core/auto_navigator.py`
- `tests/test_auto_navigator.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：** `AutoNavigator._plan_segment()` 在 A* 缺失/失败时不再进入 `FAILED`，而是构造 `[control_pos, segment_target]` 的直线路径继续 `FOLLOW_SEGMENT`；后续 `MotionController` 仍负责把直线子目标转为游戏画面点击半径。

### C. SYNC 结果
**连带重读文件：** `core/auto_navigator.py`、`tests/test_auto_navigator.py`。
**CODEBASE.md 更新内容：** 更新 `AutoNavigator.update()` 算法步骤，记录 A* 失败时直线点击引导 fallback。
**覆盖进度更新：** `core/auto_navigator.py` 的 `_plan_segment()` 不再因 `pathfinder.find_path()` 返回空而失败；`tests/test_auto_navigator.py` 新增 A* 失败时保持 active、进入 FOLLOW_SEGMENT、随后发出 move click 的覆盖。
**验证：** `python -m py_compile core\auto_navigator.py gui\modes\navigation_mode.py core\motion_controller.py main.py` 通过；`python -m unittest tests.test_route_manager tests.test_path_utils tests.test_auto_navigator tests.test_motion_controller` 通过，19 个测试成功。
**修订的旧结论：** 障碍物图层不能作为自动导航的硬失败条件；当前阶段以“持续点击正确方向”为主，A* 只作为路径辅助。

## [SYNC] 2026-05-20 - 提高自动导航点击频率并默认直线分段

### A. SYNC 范围声明
**触发任务：** 用户反馈自动导航点击频率不够快，同时窄路会被错误障碍图误判；阶段 1 应优先保证无干扰时稳定走到出口。
**直接变更文件：**
- `core/auto_navigator.py`
- `core/motion_controller.py`
- `gui/navigation_params.py`
- `gui/dialogs/nav_params_dialog.py`
- `gui/modes/navigation_mode.py`
- `tests/test_auto_navigator.py`
- `tests/test_motion_controller.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：** 自动导航默认不再调用 A* 规划，直接按当前位置到途经点/出口构造直线段；点击冷却默认从 550ms 降到 260ms，目标变化阈值从 24 降到 8；Win32 点击 hold/move delay 从 0.08/0.05 缩短为 0.05/0.02。

### C. SYNC 结果
**连带重读文件：** `core/auto_navigator.py`、`core/motion_controller.py`、`gui/navigation_params.py`、`gui/dialogs/nav_params_dialog.py`、`gui/modes/navigation_mode.py`、`tests/test_auto_navigator.py`、`tests/test_motion_controller.py`。
**CODEBASE.md 更新内容：** 更新架构图、自动导航算法、自动导航点击数据流、`NavConfig` 契约、Input Control Current Notes。
**覆盖进度更新：** `AutoNavigator.configure()` 新增运行时点击节奏配置；`AutoNavigator._plan_segment()` 默认 `prefer_direct_guidance=True` 时跳过 `PathFinder`；参数面板新增自动点击冷却和目标变化阈值控件；导航模式在配置应用/参数变化时调用 `auto_navigator.configure()`。
**验证：** `python -m py_compile core\auto_navigator.py core\motion_controller.py gui\navigation_params.py gui\dialogs\nav_params_dialog.py gui\modes\navigation_mode.py tests\test_auto_navigator.py tests\test_motion_controller.py` 通过；`python -m unittest tests.test_route_manager tests.test_path_utils tests.test_auto_navigator tests.test_motion_controller` 通过，21 个测试成功。
**修订的旧结论：** 当前慢速主要不是计算瓶颈，而是主动限频和点击执行延迟；第一阶段将障碍图从默认规划链路移除，点击频率通过配置项控制。

## [SYNC] 2026-05-20 - 底部 UI 禁点区安全回退

### A. SYNC 范围声明
**触发任务：** 用户截图指出屏幕下方技能栏/聊天区域容易被自动移动点击误触；要求不要直接改坐标参数，而是在触碰该区域时回退一点或采取遮罩方案。
**直接变更文件：**
- `core/motion_controller.py`
- `gui/navigation_params.py`
- `gui/dialogs/nav_params_dialog.py`
- `gui/modes/navigation_mode.py`
- `tests/test_motion_controller.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：** 运动控制仍先按现有比例和半径计算屏幕点击点；若最终点进入底部禁点区，则沿人物中心到目标点的方向缩短到安全线，不改变 `movement_scale_factor`、最小/最大点击半径等正常映射参数。

### C. SYNC 结果
**连带重读文件：** `core/motion_controller.py`、`gui/navigation_params.py`、`gui/dialogs/nav_params_dialog.py`、`gui/modes/navigation_mode.py`、`tests/test_motion_controller.py`。
**CODEBASE.md 更新内容：** 新增 `MotionController._apply_bottom_click_guard()` 算法说明，更新自动导航点击流和 `NavConfig.bottom_click_guard_pixels` 契约。
**覆盖进度更新：** `NavConfig` 新增 `bottom_click_guard_pixels`，参数面板新增“底部禁点区域(px)”；`NavigationModeWidget` 将该配置传入 `MotionController.set_params()`；`MotionController._execute_click()` 在 clamp 和真实点击前执行底部安全回退，并记录 `bottom_guard` 诊断信息。
**验证：** `python -m py_compile core\motion_controller.py gui\navigation_params.py gui\dialogs\nav_params_dialog.py gui\modes\navigation_mode.py tests\test_motion_controller.py` 通过；`python -m unittest tests.test_motion_controller tests.test_auto_navigator tests.test_route_manager tests.test_path_utils` 通过，22 个测试成功。
**修订的旧结论：** 底部 UI 误触不应通过缩小全局点击半径解决；它是屏幕安全区问题，应在最终点击落点层做条件性回退。

## [SYNC] 2026-05-21 - A* 规划优先并让墙体变薄

### A. SYNC 范围声明
**触发任务：** 用户指出障碍处理不应长期走直线；正确逻辑应该能沿地图通路规划，墙体可以适当变薄，人工锚点只是辅助，不应导致跨障碍直线。
**直接变更文件：**
- `core/pathfinder.py`
- `core/auto_navigator.py`
- `gui/modes/navigation_mode.py`
- `tests/test_auto_navigator.py`
- `tests/test_pathfinder.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：** 自动导航默认回到 A* 规划优先；`PathFinder` 默认先腐蚀墙体、取消安全膨胀，减少窄路被误封；`AutoNavigator` 启动后按当前位置跳过已在身后的途经点，避免从 6 附近启动却回点 1；直线点击只保留为 A* 失败兜底或显式 direct 模式。

### C. SYNC 结果
**连带重读文件：** `core/pathfinder.py`、`core/auto_navigator.py`、`gui/modes/navigation_mode.py`、`tests/test_auto_navigator.py`。
**CODEBASE.md 更新内容：** 更新 `AutoNavigator.update()` 算法、`PathFinder._build_obstacle_map()` 算法、自动导航点击数据流和 Input Control Current Notes。
**覆盖进度更新：** `PathFinder.__init__()` 新增 `safety_margin=0`、`wall_shrink_iterations=1` 默认；`PathFinder.find_path()` 改为经 `_build_obstacle_map()` 使用变薄墙图；`AutoNavigator.prefer_direct_guidance` 默认恢复为 `False`；导航模式配置应用时传入 `prefer_direct_guidance=False`；新增路线进度对齐和绕障试探点击测试；新增 `tests/test_pathfinder.py` 验证薄墙误判被消除。
**验证：** `python -m py_compile core\pathfinder.py core\auto_navigator.py gui\modes\navigation_mode.py tests\test_auto_navigator.py tests\test_pathfinder.py` 通过；`python -m unittest tests.test_pathfinder tests.test_auto_navigator tests.test_path_utils tests.test_route_manager tests.test_motion_controller` 通过，25 个测试成功。
**修订的旧结论：** “默认直线分段”只能作为短期止血；正确的一阶段策略是规划优先、墙图软化、失败才 fallback。

## [SYNC] 2026-05-21 - A* 失败 fallback 改为局部脱困点

### A. SYNC 范围声明
**触发任务：** 用户指出“直线点击”不应走向下一个目标，而应该只靠近下一个目标方向、越过当前障碍后重新规划。
**直接变更文件：**
- `core/auto_navigator.py`
- `tests/test_auto_navigator.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：** A* 失败时不再构造 `[control_pos, segment_target]` 的长直线路径；改为生成当前人物附近的短距离局部脱困点，点击后进入 `local_fallback` 路径，抵达临时点或无进展时回到 `PLAN_SEGMENT` 重新 A*。

### C. SYNC 结果
**连带重读文件：** `core/auto_navigator.py`、`tests/test_auto_navigator.py`。
**CODEBASE.md 更新内容：** 更新 `AutoNavigator.update()` 算法步骤，新增 `_set_local_fallback_path()` 说明，并修正自动导航点击数据流和 Input Control Current Notes。
**覆盖进度更新：** `AutoNavigator` 新增 `direct_fallback_distance`、`direct_fallback_side_distance`、`current_path_kind`、`direct_fallback_attempts`；`_plan_segment()` 在 A* 失败时调用 `_set_local_fallback_path()`；`_follow_segment()` 对 `local_fallback` 到达/无进展后重新规划；`tests/test_auto_navigator.py` 验证 fallback 终点不是 segment target，且到达临时点后回到 PLAN_SEGMENT。
**验证：** `python -m py_compile core\auto_navigator.py tests\test_auto_navigator.py` 通过；`python -m unittest tests.test_auto_navigator tests.test_pathfinder tests.test_path_utils tests.test_route_manager tests.test_motion_controller` 通过，25 个测试成功。
**修订的旧结论：** “A* 失败后直线到下一目标”仍可能穿墙卡住；fallback 的职责只应是局部脱困，不应替代全局路径规划。

## [SYNC] 2026-05-21 - A* 禁止穿过未探索黑区

### A. SYNC 范围声明
**触发任务：** 用户截图显示黄色规划线穿过地图外/未探索黑区，说明 A* 把没有墙像素的未知区域当成可走区域。
**直接变更文件：**
- `core/pathfinder.py`
- `core/auto_navigator.py`
- `gui/modes/navigation_mode.py`
- `tests/test_pathfinder.py`
- `tests/test_auto_navigator.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：** `PathFinder` 不再只看 `wall_layer`，而是把 `explored_map==0` 当作不可走区域；`NavigationModeWidget.navigation_loop()` 将 `nav_core.explored_map` 传给自动导航；自动导航规划路径不再用只看墙图的 shortcut 平滑，避免后处理把路径重新拉直穿过未知区域。

### C. SYNC 结果
**连带重读文件：** `core/pathfinder.py`、`core/auto_navigator.py`、`gui/modes/navigation_mode.py`、`tests/test_pathfinder.py`。
**CODEBASE.md 更新内容：** 更新 `PathFinder` 职责、`_build_obstacle_map()` 算法、`AutoNavigator.update()` 算法和自动导航点击数据流。
**覆盖进度更新：** `PathFinder.find_path()` 新增 `explored_map=None` 参数；`_build_obstacle_map()` 将未知区域并入障碍图；`AutoNavigator.update()` 新增 `explored_map` 参数并传给 `_plan_segment()`；规划路径后处理从 `smooth_path(wall_map, raw_path)` 改为 `remove_collinear_points(raw_path)`，避免只基于墙图跨 unknown 捷径；新增 pathfinder 测试验证未知区域不可走。
**验证：** `python -m py_compile core\pathfinder.py core\auto_navigator.py gui\modes\navigation_mode.py tests\test_pathfinder.py tests\test_auto_navigator.py` 通过；`python -m unittest tests.test_pathfinder tests.test_auto_navigator tests.test_path_utils tests.test_route_manager tests.test_motion_controller` 通过，26 个测试成功。
**修订的旧结论：** “墙体变薄”只解决窄路误封；A* 的可走域必须由 `explored_map` 限定，否则地图外黑区会被误判为空地。

## [SYNC] 2026-05-21 - 自动导航按最近标记点接入路线

### A. SYNC 范围声明
**触发任务：** 用户指出自动移动时应该追寻最近的标记点并继续往终点走，而不是每次都从第一个标记点开始。
**直接变更文件：**
- `core/auto_navigator.py`
- `tests/test_auto_navigator.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：** 自动导航启动或重定位后的第一次规划会在 `guide_points + exit` 中选择离当前位置最近的标记作为当前目标；如果已经贴近该标记，则直接推进到下一个标记。之后仍按路线顺序往出口走。

### C. SYNC 结果
**连带重读文件：** `core/auto_navigator.py`、`tests/test_auto_navigator.py`。
**CODEBASE.md 更新内容：** 更新 `AutoNavigator.update()` 算法步骤，并新增 `_align_route_to_current_position()` 算法说明。
**覆盖进度更新：** `_align_route_to_current_position()` 从线段投影对齐改为最近标记点对齐；新增 `route_marker_arrival_factor` 控制贴近标记时是否跳到下一个；删除未使用的旧线段投影对齐函数；新增测试覆盖“远离路线线段但最近某个标记”和“已经贴近某标记应追踪下一个标记”。
**验证：** `python -m py_compile core\auto_navigator.py tests\test_auto_navigator.py` 通过；`python -m unittest tests.test_auto_navigator tests.test_pathfinder tests.test_path_utils tests.test_route_manager tests.test_motion_controller` 通过，28 个测试成功。
**修订的旧结论：** 自动导航的路线接入不应依赖“起点是第一个标记”的假设；应从当前定位动态接入最近的路线标记，再沿标记序列向出口推进。

## [SYNC] 2026-05-21 - 路线附近按线段方向接入下一标记

### A. SYNC 范围声明
**触发任务：** 继续完善最近标记点逻辑，避免人在两个标记之间时因为离上一个点更近而回头。
**直接变更文件：**
- `core/auto_navigator.py`
- `tests/test_auto_navigator.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：** 自动导航启动时如果当前位置贴近某条路线段，会接入该线段并追踪下一个标记；只有偏离路线较远时才单纯按最近标记点接入。

### C. SYNC 结果
**连带重读文件：** `core/auto_navigator.py`、`tests/test_auto_navigator.py`。
**CODEBASE.md 更新内容：** 更新 `_align_route_to_current_position()` 算法说明，新增 `_candidate_index_from_nearest_route_segment()` 说明。
**覆盖进度更新：** `_align_route_to_current_position()` 现在先计算最近标记，再用路线段投影覆盖候选目标；新增测试验证人在第 1 和第 2 标记之间且更靠近第 1 标记时，仍追踪第 2 标记。
**验证：** `python -m py_compile core\auto_navigator.py tests\test_auto_navigator.py` 通过；`python -m unittest tests.test_auto_navigator tests.test_pathfinder tests.test_path_utils tests.test_route_manager tests.test_motion_controller` 通过，29 个测试成功。
**修订的旧结论：** “最近标记点”不能机械地选欧氏距离最近点；在路线附近时应按路线方向追下一个标记，才能保证持续往出口走。

## [SYNC] 2026-05-21 - 新增严格顺序的必经点

### A. SYNC 范围声明
**触发任务：** 用户要求把路线点拆成两种机制：`required_points` 必须按顺序先完成，`guide_points` 作为普通辅助点；并且完成过的必经点不能被再次追踪。
**直接变更文件：**
- `core/auto_navigator.py`
- `gui/modes/navigation_mode.py`
- `tests/test_auto_navigator.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：** 自动导航在存在未完成 `required_points` 时，不再执行“最近路线点接入”来跳过它们；地图编辑 UI 新增“添加/撤销必经点”；路线覆盖层用独立颜色和 `R1/R2/...` 标签区分必经点与普通途经点。

### C. SYNC 结果
**连带重读文件：** `core/auto_navigator.py`、`gui/modes/navigation_mode.py`、`tests/test_auto_navigator.py`、`core/route_manager.py`。
**CODEBASE.md 更新内容：** 更新项目概览、`NavigationModeWidget`/`RouteManager`/`AutoNavigator` 模块职责，并修正 `AutoNavigator.update()`、`_align_route_to_current_position()` 的算法描述。
**覆盖进度更新：** `AutoNavigator` 新增 `required_index`、`required_points()`、`has_pending_required_points()`；`current_segment_target()` 和 `_advance_segment()` 现在先处理必经点，再处理普通途经点/出口；`navigation_mode.py` 新增必经点编辑按钮、点击模式和紫色 `R*` 覆盖层标记；新增测试覆盖“必经点优先”“必经点不可被路线接入跳过”“完成必经点后恢复 guide 对齐”。
**验证：** `python -m py_compile core\route_manager.py core\auto_navigator.py gui\modes\navigation_mode.py tests\test_route_manager.py tests\test_auto_navigator.py` 通过；`python -m unittest tests.test_route_manager tests.test_auto_navigator tests.test_pathfinder tests.test_path_utils tests.test_motion_controller` 通过，34 个测试成功。
**修订的旧结论：** 之前把所有路线点都放进同一套“最近路线点接入”逻辑，会导致严格 checkpoint 被自动跳过；必经点必须在状态机层与普通途经点分治。

## [SYNC] 2026-05-21 - 禁止 A* 斜向穿角

### A. SYNC 范围声明
**触发任务：** 用户反馈自动导航会进入地图禁区。排查后确认 `PathFinder` 的 8 方向 A* 允许从两个障碍角之间斜着挤过去，这会制造“明明有墙但路径还是穿进去”的假象。
**直接变更文件：**
- `core/pathfinder.py`
- `tests/test_pathfinder.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：** A* 仍然保留 8 方向移动，但任何对角步在执行前都必须检查两侧正交邻格；只要有一侧是障碍，就禁止该对角步，避免 corner cutting。

### C. SYNC 结果
**连带重读文件：** `core/pathfinder.py`、`core/stitcher_core.py`、`tests/test_pathfinder.py`。
**CODEBASE.md 更新内容：** 新增 `PathFinder._astar()` 关于“禁止斜穿角”的算法说明。
**覆盖进度更新：** `tests/test_pathfinder.py` 新增 corner-cutting 回归测试，确保 `(1,1) -> (2,2)` 不会在两侧有障碍时斜穿过去。
**验证：** `python -m py_compile core\pathfinder.py tests\test_pathfinder.py` 通过；`python -m unittest tests.test_pathfinder tests.test_auto_navigator tests.test_path_utils tests.test_route_manager tests.test_motion_controller` 通过，35 个测试成功。
**修订的旧结论：** “导航进禁区”不一定全是墙体识别失败；A* 本身如果允许斜穿角，也会把合法障碍图走穿。

## [SYNC] 2026-05-21 - 绘图地图去灰块并显式渲染地面/禁区候选层

### A. SYNC 范围声明
**触发任务：** 用户反馈绘图模式里的全局地图不够清晰，墙体容易粘连，且游戏小地图中的蓝色地面/禁区信息没有被显式呈现。
**直接变更文件：**
- `core/stitcher_core.py`
- `core/navigation_core.py`
- `core/recognizer_optimized.py`
- `gui/modes/mapping_widget.py`
- `gui/widgets/scalable_map.py`
- `tests/test_stitcher_core.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：** 建图阶段不再优先把整块截图矩形写入 `explored_map`；若当前帧能提取出足够大的 `fog_mask`，则用其作为精确可见区域并同时维护 `fog_layer`。绘图模式和导航模式的全局地图显示都会新增蓝色地面/禁区候选层；地图缩放改为像素级显示，避免细线被平滑插值抹掉。

### C. SYNC 结果
**连带重读文件：** `core/stitcher_core.py`、`core/navigation_core.py`、`core/recognizer_optimized.py`、`gui/modes/mapping_widget.py`、`gui/widgets/scalable_map.py`。
**CODEBASE.md 更新内容：** 新增 `MapStitcher._merge_frame_weighted()`、`MapStitcher.get_enhanced_map()` 说明，并更新 `NavigationCore` 的地图显示职责。
**覆盖进度更新：** `MapStitcher` 新增 `use_precise_visibility_mask` / `precise_visibility_min_pixels`，开始真正维护 `fog_layer`；`mapping_widget.py` 的路径预览现在也会把 `explored_map` 传给 `PathFinder`；`ScalableMapWidget` 改成 `Qt.FastTransformation`；透明地图模式的墙体闭运算从 `kernel_medium` 收紧到 `kernel_small`，降低细墙粘连。
**验证：** `python -m py_compile core\stitcher_core.py core\navigation_core.py core\recognizer_optimized.py gui\modes\mapping_widget.py gui\widgets\scalable_map.py tests\test_stitcher_core.py` 通过；`python -m unittest tests.test_stitcher_core tests.test_pathfinder tests.test_auto_navigator tests.test_path_utils tests.test_route_manager tests.test_motion_controller` 通过，37 个测试成功。
**修订的旧结论：** 地图发糊的主因不是单纯 `draw_scale` 太小，而是旧逻辑把整块监视窗口都刷成 explored，再叠加平滑缩放显示，最终看起来像“大灰块 + 粗墙体”。

## [SYNC] 2026-05-21 - 隐藏蓝色地面层渲染

### A. SYNC 范围声明
**触发任务：** 用户确认地图绘制效果已改善，但不希望全局图显示蓝色背景层。
**直接变更文件：**
- `core/stitcher_core.py`
- `core/navigation_core.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：** `fog_layer` 继续在地图包内维护，用于后续禁区/地面分析，但绘图模式和导航模式的地图 UI 恢复为黑底/灰区/白墙，不再额外铺蓝色。

### C. SYNC 结果
**连带重读文件：** `core/stitcher_core.py`、`core/navigation_core.py`。
**CODEBASE.md 更新内容：** 修正 `NavigationCore` 和 `MapStitcher.get_enhanced_map()` 的显示说明，明确 `fog_layer` 默认不直接渲染。
**覆盖进度更新：** 仅调整显示层，不改内部 `fog_layer` 数据结构与持久化逻辑。
**验证：** `python -m py_compile core\stitcher_core.py core\navigation_core.py` 通过；`python -m unittest tests.test_stitcher_core tests.test_pathfinder tests.test_auto_navigator tests.test_path_utils tests.test_route_manager tests.test_motion_controller` 通过，37 个测试成功。

## [SYNC] 2026-05-21 - 降低事件/Boss 图标对导航定位的干扰

### A. SYNC 范围声明
**触发任务：** 用户明确说明受影响的是“游戏截图监控时，小地图里的额外事件/Boss 图标”，这些动态图标会污染导航定位与地图匹配。
**直接变更文件：**
- `core/recognizer_optimized.py`
- `core/navigation_core.py`
- `tests/test_recognizer_optimized.py`
- `tests/test_navigation_core.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：** `extract_combined()` 不再只把高饱和度彩色图标从 `wall_mask` 中剔除，而是同步从 `edges` 和 `fog_mask` 中剔除，并对该彩色区域做一次小核膨胀，连同轮廓一起去掉。导航时的 F2F 跟踪不再优先吃混合 `match_mask`，改为优先跟踪更稳定的 `wall_mask`，同时拒绝异常大的帧间位移并回退模板匹配。

### C. SYNC 结果
**连带重读文件：** `core/recognizer_optimized.py`、`core/navigation_core.py`。
**CODEBASE.md 更新内容：** 补充 `NavigationCore` 关于 F2F 跟踪策略的说明，并新增 `HSVRecognizer.extract_combined()` 的动态特效抑制算法描述。
**覆盖进度更新：** `Recognizer` 现在会把彩色动态图标和人物中心近身特效从 `wall_mask`/`edges`/`fog_mask` 同步剔除；`NavigationCore` 新增 `prev_wall_mask`，F2F 使用 `wall_mask` 估位移，降低战斗场景下 `edges` 污染带来的漂移。
**验证：** `python -m py_compile core\recognizer_optimized.py core\navigation_core.py tests\test_recognizer_optimized.py tests\test_navigation_core.py` 通过；`python -m unittest tests.test_recognizer_optimized tests.test_navigation_core tests.test_stitcher_core tests.test_pathfinder tests.test_auto_navigator tests.test_path_utils tests.test_route_manager tests.test_motion_controller` 通过，39 个测试成功。

## [SYNC] 2026-05-22 - 必经点改为路线阶段门而非直接目标覆盖

### A. SYNC 范围声明
**触发任务：** 用户指出经过第一个必经点后，系统会直接直线指向第二个必经点，忽略中间普通标记点和路线走廊，导致路线逻辑错误。
**直接变更文件：**
- `core/auto_navigator.py`
- `gui/modes/navigation_mode.py`
- `tests/test_auto_navigator.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：** 自动导航不再把未完成必经点无条件作为当前段目标；普通标记点继续承担路线骨架和 A* 分段目标，必经点只作为按路线进度触发的阶段门。覆盖层根据 `target_kind` 高亮真正当前目标，避免 UI 看起来仍然直指下一个必经点。

### C. SYNC 结果
**连带重读文件：** `core/auto_navigator.py`、`gui/modes/navigation_mode.py`、`tests/test_auto_navigator.py`。
**CODEBASE.md 更新内容：** 修正 `AutoNavigator` 与 `NavigationModeWidget` 的路线点语义，新增 `_select_segment_target()` 算法说明，并更新 `_align_route_to_current_position()` 不越过当前必经点进度的描述。
**覆盖进度更新：** `AutoNavigator` 新增 `current_target_kind`、`current_segment_target_kind()`、`_select_segment_target()`、`_route_progress_for_point()`、`_guide_index_limit_for_current_required()`；`_advance_segment()` 改为按当前目标类型推进，普通点到达不会误推进 `required_index`；`_align_route_to_current_position()` 允许在必经点前接入普通路线，但会截断到当前必经点之前；`NavigationModeWidget._render_route_overlay()` 使用 `target_kind` 高亮当前目标。
**验证：** `python -m py_compile core\auto_navigator.py gui\modes\navigation_mode.py tests\test_auto_navigator.py` 通过；`python -m unittest tests.test_recognizer_optimized tests.test_navigation_core tests.test_stitcher_core tests.test_pathfinder tests.test_auto_navigator tests.test_path_utils tests.test_route_manager tests.test_motion_controller` 通过，42 个测试成功。
**修订的旧结论：** “存在未完成必经点时应直接追当前必经点”会破坏路线骨架；正确语义是 `guide_points` 决定可行走路线形状，`required_points` 决定必须按顺序经过的阶段门。

## [SYNC] 2026-05-22 - 事件系统设计和传送门图标探针

### A. SYNC 范围声明
**触发任务：** 用户要求事件功能先做可行性验证，重点确认能否从游戏小地图中识别传送门事件图标，并保持后续事件类型模块化扩展。
**直接变更文件：**
- `docs/plans/2026-05-22-event-system-design.md`
- `utils/event_icon_probe.py`
- `assets/event_templates/portal/minimap/portal_minimap_01.png`
- `assets/event_templates/portal/minimap/portal_minimap_02.png`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：** 事件识别暂不接入导航主循环；当前只新增设计文档和独立探针。后续正式接入时应从 raw minimap frame 分层识别事件，而不是复用已做动态抑制的定位特征图。

### C. SYNC 结果
**连带重读文件：** `docs/plans/2026-05-22-event-system-design.md`、`utils/event_icon_probe.py`、`core/capture.py`。
**CODEBASE.md 更新内容：** 新增事件图标探针的目录职责、模块说明、`match_template()` / `merge_hits()` / `main()` 算法说明、事件探针数据流和外部集成注意事项。
**覆盖进度更新：** 事件系统设计确认 `EventMonitor` / `EventDetector` / `EventMemory` / `EventScheduler` / `EventHandler` / `EventConfig` 模块边界；传送门 v1 使用 raw minimap 多模板匹配作为第一阶段识别方式；`event_icon_probe.py` 支持可重复 `--template`，跨模板候选按中心距离去重，并在无 accepted hit 时输出每个模板的最佳候选用于诊断；已把可复用传送门模板移入 `assets/event_templates/portal/minimap/`。
**验证：** `D:\ACloud\.venv\Scripts\python.exe -m py_compile utils\event_icon_probe.py` 通过；管理员权限运行资产模板探针通过，`portal_minimap_01` 得分 `0.9652`、中心 `(45,61)`，`portal_minimap_02` 得分 `0.9172`、中心 `(68,87)`。
**修订的旧结论：** “识别传送门需要先训练 YOLO”不是第一阶段必要条件；当前小地图图标是固定 UI 小图标，多模板匹配已经足够支撑第一版事件发现探针。

## [SYNC] 2026-05-22 - 大画面传送门实体识别探针

### A. SYNC 范围声明
**触发任务：** 用户明确要求大地图/游戏屏幕也做一次探针，先验证能否识别整个游戏界面中的传送门实体，验证可行后只保存为技术资产，暂不接入事件架构。
**直接变更文件：**
- `utils/portal_screen_probe.py`
- `assets/event_detectors/portal/main_view/blue_glow_detector_v1.json`
- `assets/event_detectors/portal/main_view/README.md`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：** 当前不修改导航、事件主循环或点击逻辑；新增大画面二阶段确认探针。后续事件系统可在小地图传送门图标确认后，再用该主画面探针确认真实传送门实体是否在可点击视野内。

### C. SYNC 结果
**连带重读文件：** `utils/portal_screen_probe.py`、`core/capture.py`、`assets/event_detectors/portal/main_view/README.md`。
**CODEBASE.md 更新内容：** 新增大画面探针的目录职责、模块说明、`build_blue_glow_mask()` / `detect_portal_candidates()` / `is_strict_portal_candidate()` 算法说明、主画面探针数据流和风险登记。
**覆盖进度更新：** `portal_screen_probe.py` 支持枚举 `UnrealWindow` / `Torchlight` 游戏窗口、`--rect`、`--full-screen`、`--params` 参数资产；检测策略为 HSV 蓝/青/紫发光 mask + 轮廓面积/发光占比/圆度/宽高比评分 + 严格 accepted 过滤。`blue_glow_detector_v1.json` 固化当前阈值，README 记录复现命令和预期行为。
**验证：** `D:\ACloud\.venv\Scripts\python.exe -m py_compile utils\portal_screen_probe.py` 通过；管理员权限 `run_02` 中真实大传送门被唯一 accepted，得分 `0.9962`，screen center `(774,501)`，bbox `202x207`；后续 `--params` 复现时传送门已离开/被遮挡，输出 0 accepted，符合“实体不可见时不确认”的预期。
**修订的旧结论：** 大画面传送门不需要先训练 YOLO 才能验证可行性；在当前画面中，颜色+几何二阶段确认足以稳定识别可见的大传送门，但正式接入时必须受小地图事件发现约束，不能全图无条件触发。

## [SYNC] 2026-05-22 - 事件系统架构设计和实现计划

### A. SYNC 范围声明
**触发任务：** 用户审核确认采用完整事件包架构，TUI 只展示完整事件；需要先输出代码结构架构设计和可执行实现计划。
**直接变更文件：**
- `docs/plans/2026-05-22-event-system-architecture-design.md`
- `docs/plans/2026-05-22-event-system-implementation-plan.md`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：** 当前仅新增设计和计划文档，不修改运行代码。后续实现应按计划从 core event contracts 开始，逐步接入 portal 事件，不直接把 portal 逻辑写入 `NavigationModeWidget`。

### C. SYNC 结果
**连带重读文件：** `docs/plans/2026-05-22-event-system-design.md`、`docs/plans/2026-05-22-event-system-architecture-design.md`、`docs/plans/2026-05-22-event-system-implementation-plan.md`。
**CODEBASE.md 更新内容：** 补充两个事件系统文档的目录职责说明。
**覆盖进度更新：** 架构设计明确 `EventDefinition` 是事件包唯一外部入口，TUI 只展示 `portal` 等完整事件；实现计划拆成 7 个阶段 22 个 TDD 任务，覆盖核心模型、配置、memory、portal 检测/确认/handler、coordinator、导航接入、overlay 和 TUI options。
**验证：** 已确认两个计划文件存在并可读取；本次未修改运行代码，无需执行业务测试。
**修订的旧结论：** 事件系统不能只停留在“功能方案”；需要先固定代码结构和协议边界，避免后续把 detector/confirmer/handler 暴露给 TUI 或耦合进导航循环。

## [SYNC] 2026-05-22 - 实现事件系统核心和 portal 事件包

### A. SYNC 范围声明
**触发任务：** 用户要求不要继续规划，直接按 codebase skill 执行开发；同时不要浪费时间跑逻辑测试，只做启动/编译级检查，实际游戏行为由用户测试。
**直接变更文件：**
- `core/events/**`
- `core/motion_controller.py`
- `gui/modes/navigation_mode.py`
- `utils/event_icon_probe.py`
- `utils/portal_screen_probe.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：** 导航模式加载地图时初始化事件系统，导航循环在自动导航开启时允许事件动作优先于普通 auto move。`portal` 事件可从小地图 raw frame 识别传送门图标，靠近后用主画面 confirmer 二阶段确认并返回点击动作。

### C. SYNC 结果
**连带重读文件：** `gui/modes/navigation_mode.py`、`core/motion_controller.py`、`utils/event_icon_probe.py`、`utils/portal_screen_probe.py`。
**CODEBASE.md 更新内容：** 新增 `core/events` 核心模块、`portal` 事件包、探针复用核心算法、导航接入点和 `MotionController.click_screen_position()` 说明。
**覆盖进度更新：** 新增事件模型、配置、注册表、memory、monitor、scheduler、runner、coordinator、capture provider、action executor、overlay model、window finder；新增 `PortalEventDefinition`、小地图模板 detector、主画面蓝紫发光 confirmer、portal handler；探针脚本改为复用核心 matcher/confirmer；`NavigationModeWidget` 每帧构造 `EventTick` 并在自动导航开启时执行事件动作。
**验证：** 按用户要求未运行逻辑单测；执行 `D:\ACloud\.venv\Scripts\python.exe -m compileall -q core\events gui\modes\navigation_mode.py core\motion_controller.py utils\event_icon_probe.py utils\portal_screen_probe.py main.py` 通过。清理了 `core/events` 下编译产生的 `__pycache__`。
**当前限制：** 第一版事件动作只在自动导航开启时接管；portal handler 点击/按键后用保守等待完成，不做真实场景切换确认；未新增 GUI/TUI 配置页，只提供 `event_config.json` 和 TUI options 数据模型。
**修订的旧结论：** 探针不应长期保留独立算法实现；现在运行时 detector/confirmer 与探针共用核心代码，后续调参不会出现两套逻辑漂移。

## [SYNC] 2026-05-23 - Add event runtime logs
### A. SYNC scope
**Trigger:** User needs visible logs to test event detection and execution.
**Direct files expected:** core/events/debug.py, core/events/memory.py, core/events/runner.py, core/events/coordinator.py, core/events/types/portal/handler.py, core/events/types/portal/minimap_detector.py, core/events/types/portal/main_view_confirmer.py, core/events/action_executor.py, gui/modes/navigation_mode.py, CODEBASE.md, ITERATION_LOG.md.
**Impact:** Event detection, task lifecycle, scheduler/runner actions, portal confirmation, event action execution, and navigation status text become observable without running logic tests.

### C. SYNC result
**Files changed:** `core/events/debug.py`, `core/events/memory.py`, `core/events/runner.py`, `core/events/coordinator.py`, `core/events/monitor.py`, `core/events/action_executor.py`, `core/events/types/portal/handler.py`, `core/events/types/portal/minimap_detector.py`, `core/events/types/portal/main_view_confirmer.py`, `gui/modes/navigation_mode.py`, `CODEBASE.md`, `ITERATION_LOG.md`.

**Runtime visibility added:** Event logs now cover detector initialization, minimap observations, task creation/confirmation, scheduler selection, runner action output, executor callbacks, portal move/confirm/click/wait/complete/timeout phases, and navigation status-bar event summary.

**Behavior guard:** Event detection/memory still runs during normal navigation, but event handlers only advance when `auto_navigation_enabled` is true via `EventCoordinator.update(..., run_handlers=...)`. This prevents logs from reporting handler completion when actual event movement/click execution is disabled.

**Verification:** `D:\ACloud\.venv\Scripts\python.exe -m compileall -q core\events gui\modes\navigation_mode.py core\motion_controller.py utils\event_icon_probe.py utils\portal_screen_probe.py main.py` passed. No logic/unit tests were run per user instruction.

**CODEBASE.md updated:** Added Event Runtime Diagnostics section documenting the shared event logger and live-game testing output chain.


## [SYNC] 2026-05-23 - Event manager UI and map markers
### A. SYNC scope
**Trigger:** User approved independent event-management UI plus visible map markers for event detection/trigger status.
**Direct files expected:** gui/dialogs/event_manager_dialog.py, gui/modes/navigation_mode.py, core/events/config.py if needed, CODEBASE.md, ITERATION_LOG.md.
**Impact:** Event enablement and runtime task state become visible in UI; detected event tasks are drawn on the navigation map.

## [SYNC] 2026-05-23 事件管理 UI 与地图标记收口

### A. SYNC 范围声明
**触发任务：** 为事件系统补齐独立 UI 管理窗口、可见事件触发状态、地图事件标记与事件配置保存。
**直接变更文件：**
- `gui/dialogs/event_manager_dialog.py`
- `gui/modes/navigation_mode.py`
- `core/events/coordinator.py`

**预计连带影响：**
- `core/events/config.py`：事件选配模型与保存格式。
- `core/events/overlay_models.py`：地图事件标记的展示模型。
- `core/events/models.py`：事件任务状态、动作类型在 UI 中展示。

### C. SYNC 结果
**连带重读文件：** `core/events/config.py`、`core/events/overlay_models.py`、`core/events/models.py`、`core/events/scheduler.py`、`core/events/action_executor.py`、`core/events/capture_provider.py`、`core/motion_controller.py`。

**CODEBASE.md 更新内容：** 补充 `gui/dialogs/event_manager_dialog.py` 目录职责和模块说明；更新事件管理 UI/地图 marker 数据流；补充 `MotionController.press_key()`、`NavigationModeWidget._render_event_overlay()`、`EventManagerDialog.refresh()` 的函数说明；新增 Event Manager UI 运行说明。

**覆盖进度更新：** `EventManagerDialog` 现在作为独立非模态窗口，展示完整事件选配、任务状态和保存入口；`NavigationModeWidget` 增加“事件管理”按钮、事件 marker 绘制、event config 保存和事件按键执行回调；`EventCoordinator` 在全局禁用或单事件禁用时过滤调度、状态摘要和 overlay；`MotionController` 增加事件按键 `press_key()` 通道。

**验证：** 按用户要求未运行逻辑/单元测试；执行 `D:\ACloud\.venv\Scripts\python.exe -m compileall -q core\events gui\dialogs\event_manager_dialog.py gui\modes\navigation_mode.py core\motion_controller.py utils\event_icon_probe.py utils\portal_screen_probe.py main.py` 通过；执行 `D:\ACloud\.venv\Scripts\python.exe -c "from gui.dialogs.event_manager_dialog import EventManagerDialog; from gui.modes.navigation_mode import NavigationModeWidget; print('import ok')"` 通过。

**修订的旧结论：** 只靠控制台日志不够支持用户现场测试事件触发；现在事件检测结果同时进入独立 UI 窗口和地图 marker，控制台日志只作为诊断补充。
## [SYNC] 2026-05-23 传送门按键交互与防反复传送

### A. SYNC 范围声明
**触发任务：** 用户反馈传送门应在小地图识别后跑到附近按 D，并且传送门成对靠近时不能来回反复触发；当前实际存在不会按 D 和反复识别传送的问题。
**直接变更文件：**
- `core/events/config.py`
- `core/events/types/portal/config.py`
- `core/events/types/portal/handler.py`
- `core/events/memory.py`
- `gui/modes/navigation_mode.py`
- `map_data/A1/event_config.json`

**预计连带影响：**
- `core/events/models.py`：EventTick 可携带定位失败后的 raw minimap frame。
- `core/motion_controller.py`：事件按键执行通道继续复用 `press_key()`。
- `CODEBASE.md`：同步传送门事件新完成判定和冷却半径。

### C. SYNC 结果
**连带重读文件：** `core/events/config.py`、`core/events/types/portal/config.py`、`core/events/types/portal/handler.py`、`core/events/memory.py`、`core/events/runner.py`、`gui/modes/navigation_mode.py`、`core/motion_controller.py`、`map_data/A1/event_config.json`。

**CODEBASE.md 更新内容：** 更新 portal 默认交互为按 `D`；补充传送完成判定、冷却半径、同类型短冷却和附近 pending 任务抑制说明；新增 Portal Event Current Behavior。

**覆盖进度更新：** `PortalEventConfig` 默认 `interaction="key"`，并新增 `cooldown_radius/type_cooldown_ms/post_interact_wait_ms/teleport_timeout_ms/teleport_min_distance/environment_change_threshold`；`PortalEventHandler` 在 key 模式下到达附近直接按 D，随后用位置变化或小地图环境签名变化判断传送完成；`EventMemory` 支持完成后更大半径冷却和同类型短全局冷却；`EventRunner` 完成任务后忽略附近已存在的同类任务；A1 地图事件配置已改为 key。

**验证：** 按用户要求未运行逻辑/单元测试；执行 `D:\ACloud\.venv\Scripts\python.exe -m compileall -q core\events gui\dialogs\event_manager_dialog.py gui\modes\navigation_mode.py core\motion_controller.py utils\event_icon_probe.py utils\portal_screen_probe.py main.py` 通过；执行导入检查输出 `key` 和 `import ok`。

**修订的旧结论：** 传送门默认不应该依赖主画面确认后点击；用户当前目标是“跑到小地图识别的传送门附近按 D”。主画面确认保留给 click 模式，但 key 模式直接按键更符合游戏交互。
## [SYNC] 2026-05-23 传送门小地图误识别定位修正

### A. SYNC 范围声明
**触发任务：** 用户截图显示地图上识别出多个传送门 marker，但实际小地图只有两个固定蓝色传送门图标；需要先解决传送门定位错误。
**直接变更文件：**
- `core/events/config.py`
- `core/events/types/portal/config.py`
- `core/events/types/portal/minimap_detector.py`
- `map_data/A1/event_config.json`

**预计连带影响：**
- `CODEBASE.md`：同步 portal 小地图检测从纯模板匹配改为模板+颜色校验。
- 事件 UI/地图 marker：候选数量会从最多 8 个收敛到最多 2 个。

### C. SYNC 结果
**连带重读文件：** `core/events/detectors/template_matcher.py`、`core/events/types/portal/assets.py`、`core/events/projector.py`。

**CODEBASE.md 更新内容：** 更新 portal 小地图 detector 说明：传送门检测不再只依赖灰度/边缘模板匹配，而是模板命中后增加蓝/青图标颜色校验；补充 `max_candidates` 和 `min_blue_ratio` 配置字段。

**覆盖进度更新：** 根因确认为 `PortalMinimapDetector` 之前以灰度/边缘匹配为主，`top_k=8` 且阈值 0.60，容易把白色墙线和圆形地形误识别为传送门；不是 `minimap_local_to_global()` 投影公式本身造成。现改为默认阈值 0.74、单帧最多接受 2 个候选、候选 bbox 周围必须有足够蓝/青像素，且 detector 每帧使用最新 config。

**验证：** `D:\ACloud\.venv\Scripts\python.exe -m compileall -q core\events gui\dialogs\event_manager_dialog.py gui\modes\navigation_mode.py core\motion_controller.py utils\event_icon_probe.py utils\portal_screen_probe.py main.py` 通过；导入检查输出默认 `0.74 2 0.08` 和 `import ok`。未运行逻辑/单元测试，等待用户实测。

**修订的旧结论：** 传送门位置偏差不是优先从全局坐标投影修正；更直接的根因是 detector 产生了过多错误 local hit，投影只是把这些错误 local hit 映射到了地图上。

## [SYNC] 2026-05-23 - Event localization through wall registration
### A. SYNC scope
**Trigger:** User approved scheme B: every event should be detection -> localization -> trigger -> execution -> completion, and portal global position must come from wall registration plus multi-frame stabilization instead of the old single-frame offset projector.

**Direct files changed:**
- `docs/plans/2026-05-23-event-localization-stabilizer-design.md`
- `core/navigation_core.py`
- `core/events/models.py`
- `core/events/position_stabilizer.py`
- `core/events/coordinator.py`
- `core/events/memory.py`
- `core/events/config.py`
- `core/events/types/portal/minimap_detector.py`
- `core/events/types/portal/config.py`
- `core/events/types/portal/definition.py`
- `gui/modes/navigation_mode.py`
- `gui/dialogs/event_manager_dialog.py`
- `map_data/A1/event_config.json`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**Removed files:**
- `core/events/projector.py`

**Expected impact:** Portal detector now reports only local minimap icon candidates. `NavigationCore` exposes per-frame registration data. `EventPositionStabilizer` projects detections through that registration and only emits stable global observations after multi-frame clustering, so map markers/tasks should no longer be created from one bad local hit.

### C. SYNC result
**Carryover files reviewed:** `core/events/models.py`, `core/events/coordinator.py`, `core/events/memory.py`, `core/events/types/portal/minimap_detector.py`, `core/navigation_core.py`, `gui/modes/navigation_mode.py`.

**CODEBASE.md updated:** Replaced the old `projector.py` directory entry with `position_stabilizer.py`, added `FrameRegistration` and `EventDetection` to the event contracts, corrected portal current behavior, and added an Event Localization Contract section.

**Coverage update:** Event lifecycle is now split into local detection (`EventDetection`), wall-registration projection/stabilization (`EventPositionStabilizer`), stable global observation (`EventObservation`), memory task creation, and handler execution. `stable_frames` replaces portal task confirmation for localization; `memory_confirm_frames` remains as a post-stabilization memory gate.

**Verification:** `D:\ACloud\.venv\Scripts\python.exe -m compileall -q core\events core\navigation_core.py gui\modes\navigation_mode.py gui\dialogs\event_manager_dialog.py main.py` passed. `D:\ACloud\.venv\Scripts\python.exe -c "from gui.modes.navigation_mode import NavigationModeWidget; from core.events.types.portal.minimap_detector import PortalMinimapDetector; from core.events.position_stabilizer import EventPositionStabilizer; from core.navigation_core import NavigationCore; print('import ok')"` passed. No logic/unit tests were run per user preference.

**Revised old conclusion:** Portal localization errors should no longer be treated as a detector-only threshold problem. The stable contract is now: detector finds local icon, navigation registration anchors the frame to the wall map, and only repeated projections to the same global coordinate become actionable events.

## [SYNC] 2026-05-23 - Hide default console and fix garbled status text
### A. SYNC scope
**Trigger:** User reported that runtime opens a terminal and the printed content is garbled or `????`.

**Direct files changed:**
- `main.py`
- `gui/modes/navigation_mode.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**Expected impact:** Normal GUI launch should no longer show an extra console after UAC elevation. Runtime diagnostics are written to `logs/runtime.log` in UTF-8. If live console output is needed, set `MINIMAP_DEBUG_CONSOLE=1` before launching.

### C. SYNC result
**Root cause:** Admin relaunch used `sys.executable`; when launched from `python.exe`, UAC restarted another console Python process. Console encoding could also corrupt Chinese output, and several navigation status/debug strings had already been saved as literal `????`.

**Fix:** `main.py` now configures UTF-8 output, redirects default stdout/stderr to `logs/runtime.log`, uses `pythonw.exe` for default UAC relaunch, and only keeps console mirroring when `MINIMAP_DEBUG_CONSOLE=1`. Navigation status/debug strings that were literal `????` were restored to readable Chinese.

**Verification:** `D:\ACloud\.venv\Scripts\python.exe -m py_compile main.py gui\modes\navigation_mode.py` passed. `rg "????" main.py gui/modes/navigation_mode.py core/events` returned no matches.

## [SYNC] 2026-05-23 - Release console before admin relaunch
### A. SYNC scope
**Trigger:** User still sees a runtime terminal with garbled output.
**Direct files changed:** `main.py`, `CODEBASE.md`, `ITERATION_LOG.md`.
**Expected impact:** Default GUI startup releases any inherited console before the UAC/admin branch and continues writing diagnostics to UTF-8 `logs/runtime.log`. Explicit debug console remains available via `MINIMAP_DEBUG_CONSOLE=1`.

### C. SYNC result
**Root cause refinement:** `pythonw.exe` prevents the elevated GUI process from creating a new console, but a non-debug launch from `python.exe` or PowerShell can still inherit/show the initial console until it is explicitly released.
**Fix:** `hide_console_if_not_debugging()` now runs immediately after output redirection, before DPI/admin checks and before Qt import. The UAC call still uses normal show mode so the Qt main window is not hidden.
**Verification:** `D:\ACloud\.venv\Scripts\python.exe -m py_compile main.py` passed. No logic/unit tests were run per user preference.

## [SYNC] 2026-05-23 - Paired portal completion handling
### A. SYNC scope
**Trigger:** User showed paired portals where localization/markers jump between two nearby portal icons, and after teleport the exit portal should be marked completed to prevent reverse teleport loops.
**Direct files changed:** `core/events/models.py`, `core/events/position_stabilizer.py`, `core/events/memory.py`, `core/events/runner.py`, `core/events/config.py`, `core/events/types/portal/config.py`, `core/events/types/portal/handler.py`, `map_data/A1/event_config.json`, `CODEBASE.md`, `ITERATION_LOG.md`.
**Expected impact:** Two portals visible in the same minimap frame are kept as separate event clusters. When an entry portal completes, the player destination is used to mark the nearby exit portal completed/cooldown as well.

### C. SYNC result
**Root cause:** `localization_cluster_radius=110` let two close portal detections merge into one cluster, so the stable marker could bounce between them. Completion only applied to the executed entry task, so the exit-side task could remain pending and be selected immediately after teleport.
**Fix:** Reduced portal localization cluster radius to 56 and made `EventPositionStabilizer` refuse to merge multiple detections from the same frame into one cluster. `EventAction.complete()` now carries metadata; portal handler includes `entry_pos` and `exit_pos`; runner asks memory to mark a related exit task completed before suppressing nearby pending tasks. Added `exit_complete_radius=120` to defaults and A1 config.
**Verification:** `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\events\models.py core\events\position_stabilizer.py core\events\memory.py core\events\runner.py core\events\config.py core\events\types\portal\config.py core\events\types\portal\handler.py` passed. No logic/unit tests were run per user preference.

## [SYNC] 2026-05-23 - Split paired portal tasks in memory
### A. SYNC scope
**Trigger:** User reported paired portals still show as one marker jumping between two portal positions; execution logic should wait until recognition/localization is stable.
**Direct files changed:** `core/events/memory.py`, `core/events/config.py`, `core/events/types/portal/config.py`, `map_data/A1/event_config.json`, `CODEBASE.md`, `ITERATION_LOG.md`.
**Expected impact:** Stable observations at two nearby portal coordinates should become two separate tasks/markers instead of repeatedly updating one task position.

### C. SYNC result
**Root cause refinement:** Runtime logs showed detector and stabilizer already produced two stable portal positions, approximately `(3466,2275)` and `(3512,2327)`. The jump happened in `EventMemory._find_matching_task()` because the default dedupe radius was 80 and the two portals are roughly 69px apart.
**Fix:** Added portal `dedupe_radius=32` defaults and A1 config. `EventMemory.merge_observations()` now tracks task IDs touched during the current frame, so two observations from one frame cannot both merge into the same task.
**Verification:** `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\events\memory.py core\events\config.py core\events\types\portal\config.py` passed. No logic/unit tests were run per user preference.

## [SYNC] 2026-05-23 15:14 - Portal test pipeline refactor and quiet navigation logs
### A. SYNC scope
**Trigger:** User asked to remove noisy per-frame navigation localization prints, keep portal event operation logs, save a git baseline before refactor, and refactor portal manual test logic so test mode and real navigation use the same event movement pipeline.

**Direct files changed:**
- `gui/modes/navigation_mode.py`
- `gui/dialogs/event_manager_dialog.py`
- `core/events/path_mover.py`
- `gui/modes/event_test_controller.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**Expected impact:** Runtime logs should no longer be flooded by every-frame localization position/source output. Clicking the portal test button should enable the same portal event handler/action pipeline used during automatic navigation, while event-specific A* movement is owned by a reusable module instead of being embedded in `navigation_mode.py`.

### C. SYNC result
**Carryover files reviewed:** `gui/modes/navigation_mode.py`, `gui/dialogs/event_manager_dialog.py`, `core/events/path_mover.py`, `gui/modes/event_test_controller.py`.

**CODEBASE.md updated:** Added directory and module entries for `core/events/path_mover.py` and `gui/modes/event_test_controller.py`; updated `navigation_mode.py` and event-manager descriptions; added function index entries for manual portal test startup, event MOVE_TO execution, `EventPathMover.step()`, and `EventPathMover._plan_path()`; updated the event-management flow to state that manual portal testing runs the same event pipeline as automatic navigation.

**Coverage update:** `navigation_mode.py` now delegates event movement planning to `EventPathMover` and manual test button state to `ManualEventTestController`. `event_manager_dialog.py` now drops the Qt checked argument before emitting `test_portal_requested`. The removed per-frame navigation position/source print block is intentionally not replaced; portal/event operation logs remain through `event_log()`.

**Baseline commit:** `86046ce Save event navigation baseline before refactor` was created before this refactor.

**Verification:** Pending compile/import checks after documentation sync. No logic/unit tests will be run per user preference.

## [SYNC] 2026-05-23 15:55 - Separate event logs and harden portal cooldown
### A. SYNC scope
**Trigger:** User reported that `logs/runtime.log` is still flooded by localization-position lines and portal test event logs are hard to see; also showed a completed paired portal area creating a new portal task nearby.

**Direct files changed:**
- `main.py`
- `core/events/debug.py`
- `core/events/memory.py`
- `core/events/config.py`
- `map_data/A1/event_config.json`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**Expected impact:** Each GUI start rewrites `runtime.log` instead of appending old sessions; event diagnostics are also written to a dedicated `logs/event_runtime.log`. Completed/ignored nearby portal tasks participate in cooldown suppression, so icons detected near a just-handled portal pair should not immediately become new actionable tasks.

### C. SYNC result
**Root cause evidence:** Current `gui/modes/navigation_mode.py` no longer contains the per-frame `当前定位/位置来源/本帧定位位置` print block, while `runtime.log` still contained millions of bytes from earlier sessions. `[Event ...]` lines were present but buried inside the combined runtime log.

**Fix:** `main.py` now opens `logs/runtime.log` with `w` mode per process session. `core/events/debug.py::event_log()` writes every event diagnostic to `logs/event_runtime.log` and still mirrors to runtime output. `EventMemory` now gives ignored/suppressed tasks a cooldown timestamp and logs cooldown details (`matched_task`, cooldown kind, distance/radius, remaining_ms). Portal default and A1 cooldown are extended to `cooldown_ms=120000` and `type_cooldown_ms=10000`.

**Verification:** Pending compile/import checks. No logic/unit tests will be run per user preference.

## [SYNC] 2026-05-23 - Event manager editable portal parameters
### A. SYNC scope
**Trigger:** User reported portal manual test presses `D` before the in-game portal interaction prompt is available, and requested the range threshold be configurable and saved from the event manager UI.

**Direct files changed:**
- `gui/dialogs/event_manager_dialog.py`
- `core/events/types/portal/definition.py`
- `core/events/types/portal/config.py`
- `docs/plans/2026-05-23-event-config-panel-plan.md`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**Expected impact:** The event manager shows a schema-driven parameter editor for the selected complete event. For `portal`, `interact_radius` is now editable and saved to the current map's `event_config.json`; lowering it delays pressing `D` until the character is closer to the portal.

### C. SYNC result
**Fix:** Rebuilt `EventManagerDialog` with a parameter panel driven by each event's `config_schema()`. Parameter changes update the in-memory `EventSystemConfig` and the existing save button persists them through `NavigationModeWidget._save_event_config()`. `PortalEventDefinition.config_schema()` now exposes `interact_radius`, `cooldown_ms`, and `type_cooldown_ms`; `PortalEventConfig` defaults match the current longer cooldown values.

**Verification:** Pending final compile/import checks. No logic/unit tests will be run per user preference.

## [STRUCTURE AUDIT] 2026-05-23 - Round 1 core responsibility scan
### A. 本轮目标（阅读前声明）
**目标文件：**
- `gui/modes/navigation_mode.py`（原因：导航模式主类仍是最大 GUI 聚合点，需要确认 UI、路线、事件、输入、overlay、循环是否混杂）
- `gui/modes/mapping_widget.py`（原因：绘图模式可能同时承担采集、渲染、保存、参数同步）
- `gui/dialogs/*.py` 与 `gui/navigation_params.py`（原因：配置编辑、事件管理、导航参数边界需要确认）
- `core/navigation_core.py`、`core/stitcher_core.py`、`core/auto_navigator.py`、`core/motion_controller.py`、`core/pathfinder.py`、`core/path_utils.py`（原因：核心算法层是否混入 UI/输入/调试职责）
- `core/events/*` 与 `utils/*.py`（原因：事件包、输入/窗口/探针能力是否可复用且边界清晰）

**本轮想弄清楚：**
- 大文件、大类、大函数集中在哪里，哪些是低风险移动代码候选。
- GUI 主页面是否承担了可拆分的 overlay、路线编辑、地图加载、参数桥接、事件桥接、输入模式控制。
- Core 算法层是否存在 GUI 状态、窗口输入或配置编辑耦合。
- 事件系统各层 detector/localizer/memory/scheduler/runner/handler/action executor 的职责是否清晰。
- 第一批低风险重构应只移动哪些模块，并保留现有 import 入口。

### C. 本轮发现
**关键发现：**
- (verified) `gui/modes/navigation_mode.py` 约 1584 行，是当前最大职责混合点：UI 创建/信号、地图加载、路线编辑、路线 overlay、事件 overlay、事件配置桥接、事件 action 回调、捕获几何、屏幕幕布、校准、输入窗口置顶控制和导航循环都在同一个类。
- (verified) `gui/modes/mapping_widget.py` 约 500 行，承担绘图页 UI、区域/中心选择、截图循环、识别/拼接调用、地图显示渲染、路径预览、参数同步、保存地图和全局配置读写。
- (verified) `gui/dialogs/advanced_settings_dialog.py` 约 763 行，混合 tab 构建、参数默认值、预设、文件 IO 和对 recognizer/stitcher 的实时应用；`gui/dialogs/nav_params_dialog.py` 约 543 行，混合字段映射、配置替换、屏幕边界估算和 UI 同步。
- (verified) `core/stitcher_core.py`、`core/navigation_core.py`、`core/auto_navigator.py` 是算法敏感大文件。它们没有直接依赖 Qt，但含保存/加载、显示图生成、调试 print 或状态机辅助逻辑，拆分风险高于 GUI helper 移动。
- (verified) 事件系统核心边界相对清晰：`coordinator -> monitor -> position_stabilizer -> memory -> scheduler -> runner -> handler/action`。主要耦合点在 `NavigationModeWidget` 负责构造 `EventTick`、执行 event MOVE_TO、绘制 event overlay。
- (verified) `MotionController` 是输入控制聚合点，集中地图方向到屏幕点击、底部禁点防护、Win32 输入后端、pydirectinput 兜底、键盘事件和窗口诊断。它是后续输入控制模块化目标，但不适合作为第一批低风险拆分。

**修订的旧结论：**
- 原先 `navigation_mode.py` 已经把手动事件测试按钮和事件 MOVE_TO 路径规划拆出一部分，但它仍不是薄门面；事件桥接和 overlay 绘制仍在主类内。
- 事件系统本体暂不应作为第一批拆分对象；更低风险的是先从 GUI 主类移出展示/桥接代码。

**新增疑问：**
- `AdvancedSettingsDialog` 是否仍被频繁使用，且其参数文件保存到当前工作目录是否属于预期行为，需要后续单独确认后再移动 IO 路径。
- `ColorPickerDialog.update_preview()` 会写 debug 图片和日志到当前工作目录；这是既有行为，结构拆分时不应顺手改变输出位置。

**更新了 CODEBASE.md：**
- 新增 `## 15. Structural Audit Snapshot`，记录本轮结构热点、可复用能力、边界不清晰点和推荐重构顺序。

**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/modes/navigation_mode.py` | 已有事件重构记录 | (partial) | 1 | 读完类结构、route/event overlay、事件桥接、配置桥接、导航循环；尚未逐行索引所有函数体。 |
| `gui/modes/mapping_widget.py` | PENDING | (partial) | 1 | 读完主类职责、捕获循环、显示渲染、保存/加载配置；适合作为第二批 GUI 拆分目标。 |
| `gui/dialogs/event_manager_dialog.py` | 已有事件 UI 记录 | (partial) | 1 | 读完 schema 参数面板、事件表、任务表刷新；可拆参数控件工厂和表格刷新 helper。 |
| `gui/dialogs/nav_params_dialog.py` | PENDING | (partial) | 1 | 读完 UI 构建、widget_map、配置替换、自动估算点击半径；低风险 helper 候选。 |
| `gui/dialogs/advanced_settings_dialog.py` | PENDING | 浅读 | 1 | 确认大文件职责混杂和文件 IO/预设/UI 混合，未逐函数精读。 |
| `gui/dialogs/color_picker_dialog.py` | PENDING | 浅读 | 1 | 确认采样、HSV 计算、预览渲染、debug 文件输出混合，未逐函数精读。 |
| `gui/navigation_params.py` | 已有记录 | (partial) | 1 | 确认配置模型边界清晰，但解析/序列化可更健壮；暂不优先动。 |
| `core/navigation_core.py` | 已有记录 | (partial) | 1 | 读完定位主链路，确认算法敏感，不作为第一批移动对象。 |
| `core/stitcher_core.py` | 已有记录 | (partial) | 1 | 读完拼接/融合/保存/显示职责，建议后期拆分。 |
| `core/auto_navigator.py` | 已有记录 | (partial) | 1 | 读完状态机和路线 helper，建议先保持稳定。 |
| `core/motion_controller.py` | 已有输入记录 | (partial) | 1 | 读完输入聚合职责，后续拆输入后端/诊断，首批不动。 |
| `core/pathfinder.py` | 已有记录 | (partial) | 1 | A* 边界清晰，暂不拆。 |
| `core/path_utils.py` | 已有记录 | (partial) | 1 | 纯工具边界清晰，可复用，不需要首批重构。 |
| `core/events/*` | 已有事件记录 | (partial) | 1 | 读完主链路与 portal 包关键文件，边界总体清晰；GUI 桥接优先拆。 |
| `utils/*.py` | 已有探针记录 | 浅读 | 1 | 探针是独立 CLI，输入探针有和 MotionController 重复的输入诊断概念，暂不动。 |

**下一轮计划：**
- 等用户确认第一批低风险拆分计划后，先从 `gui/modes/navigation_mode.py` 中拆出纯 GUI 绘制/桥接模块：`gui/modes/navigation/route_overlay.py`、`event_overlay.py` 或 `event_adapter.py`、`map_runtime.py` 中最独立的一小块。
- 每批只移动少量代码，保留 `gui.modes.navigation_mode.NavigationModeWidget` 入口，执行 `python -m py_compile ...` 和必要 import 检查后再做下一批。

## [REFACTOR] 2026-05-23 - Navigation overlay split batch 1
### A. 变更范围声明（执行前）
**触发任务：** 用户确认执行第一批低风险结构拆分。

**直接计划变更文件：**
- `gui/modes/navigation_mode.py`
- `gui/modes/navigation/__init__.py`
- `gui/modes/navigation/route_overlay.py`
- `gui/modes/navigation/event_overlay.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：**
- `NavigationModeWidget` 保留 `_render_route_overlay()`、`_render_event_overlay()`、`_clear_route_overlay()`、`_clear_event_overlay()` 等原有内部入口，但方法体改为委托新 helper。
- 新 helper 只接收现有 `scene/nav_core/route_data/event_coordinator` 和 item 列表，不改变路线、事件、自动导航或点击行为。
- 最小验证范围为 `py_compile` 和 `NavigationModeWidget` import。

### C. 变更结果
**实际变更：**
- (verified) 新增 `gui/modes/navigation/` helper 包。
- (verified) 新增 `event_overlay.py`，承接事件 marker 清理、全局坐标到场景坐标转换、事件 overlay 绘制。
- (verified) 新增 `route_overlay.py`，承接路线 overlay 清理、出口/必经点/途经点/当前路径/subgoal 绘制。
- (verified) `NavigationModeWidget` 保留原 `_clear_route_overlay()`、`_clear_event_overlay()`、`_global_to_scene()`、`_render_event_overlay()`、`_render_route_overlay()`，方法体改为委托新 helper。
- (verified) `NavigationModeWidget._render_route_overlay()` 保留原来的 scene/nav_core 不可用时早退语义；未改变导航循环、事件调度、路线数据读写、点击行为或默认参数。

**CODEBASE.md 更新内容：**
- 更新目录结构图，新增 `gui/modes/navigation/__init__.py`、`event_overlay.py`、`route_overlay.py`。
- 更新 `gui/modes/navigation_mode.py` 模块说明，标明 overlay 绘制已拆出。
- 新增 `event_overlay.py` / `route_overlay.py` 模块详解。
- 更新 `NavigationModeWidget._render_event_overlay()` 函数索引，并新增 `render_route_overlay()`、`render_event_overlay()` 函数索引。
- 更新结构审计快照，记录第一批拆分结果。

**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/modes/navigation_mode.py` | (partial) | (partial) | 2 | 本轮重读并修改 overlay 方法，保留兼容入口，主类行数下降但仍承担导航循环/事件桥接/配置桥接。 |
| `gui/modes/navigation/__init__.py` | PENDING | 深度完整 | 1 | 新增空包入口，仅用于 helper 模块命名空间。 |
| `gui/modes/navigation/event_overlay.py` | PENDING | 深度完整 | 1 | 新增事件 overlay helper，只绘制/清理 QGraphicsItem，不读取业务配置。 |
| `gui/modes/navigation/route_overlay.py` | PENDING | 深度完整 | 1 | 新增路线 overlay helper，只消费传入 route/current 状态并绘制 QGraphicsItem。 |

**验证：**
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\modes\navigation_mode.py gui\modes\navigation\__init__.py gui\modes\navigation\event_overlay.py gui\modes\navigation\route_overlay.py` 待最终复跑。
- `D:\ACloud\.venv\Scripts\python.exe -c "from gui.modes.navigation_mode import NavigationModeWidget; ..."` 待最终复跑。

**下一轮计划：**
- 若本批通过，下一批建议继续拆 `navigation_mode.py` 的事件桥接：`EventTick` 构造、event action 判断、事件状态文字、event config dialog bridge 可进入 `gui/modes/navigation/event_adapter.py`，但仍保留原私有方法委托入口。

## [REFACTOR] 2026-05-23 - Navigation event adapter split batch 2
### A. 变更范围声明（执行前）
**触发任务：** 用户要求继续并由 agent 自主规划完成结构优化。

**直接计划变更文件：**
- `gui/modes/navigation_mode.py`
- `gui/modes/navigation/event_adapter.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：**
- 只移动事件桥接中纯构造/判断/展示 helper：registry 创建、事件启用摘要、`EventTick` 构造、action 是否接管导航、事件状态文案。
- 保留 `NavigationModeWidget._build_event_tick()`、`_should_event_action_take_control()`、`_event_status_text()` 原私有入口，避免改调用方。
- 不拆 `EventCoordinator`、`EventMemory`、`EventRunner`、`PortalEventHandler` 等事件核心模块。
- 不改变 `event_config.json` 保存、事件调度、移动点击或传送门行为。

### C. 变更结果
**实际变更：**
- (verified) 新增 `gui/modes/navigation/event_adapter.py`。
- (verified) `NavigationModeWidget.__init__()` 通过 `create_default_event_registry()` 创建默认事件 registry，仍注册同一个 `PortalEventDefinition`。
- (verified) 事件初始化/配置变更日志的事件开关摘要委托 `event_config_summary()`。
- (verified) `_find_game_window_rect()` 委托 `find_default_game_window_rect()`，仍查找 `Torchlight` / `UnrealWindow`。
- (verified) `_build_event_tick()` 委托 `build_event_tick()`，字段保持原 `EventTick` 契约。
- (verified) `_should_event_action_take_control()` 委托 `should_event_action_take_control()`；终止 action 判断改用 `is_terminal_event_action()`。
- (verified) `_event_status_text()` 委托 `event_status_text()`。

**CODEBASE.md 更新内容：**
- 新增目录结构和模块详解：`gui/modes/navigation/event_adapter.py`。
- 更新 `navigation_mode.py` 依赖和职责说明。
- 新增 `build_event_tick()`、`should_event_action_take_control()` 函数索引。
- 更新结构审计快照，记录第二批拆分结果。

**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/modes/navigation_mode.py` | (partial) | (partial) | 3 | 本轮重读事件桥接区域并改为 helper 委托；仍保留原私有入口。 |
| `gui/modes/navigation/event_adapter.py` | PENDING | 深度完整 | 1 | 新增事件桥接 helper，不推进事件系统状态，不执行输入。 |

**验证：**
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\modes\navigation_mode.py gui\modes\navigation\event_adapter.py gui\modes\navigation\event_overlay.py gui\modes\navigation\route_overlay.py` 待最终复跑。
- `D:\ACloud\.venv\Scripts\python.exe -c "from gui.modes.navigation_mode import NavigationModeWidget; from gui.modes.navigation.event_adapter import build_event_tick, create_default_event_registry; print('imports ok')"` 待最终复跑。

**下一轮计划：**
- 下一批优先拆 `navigation_mode.py` 的地图/配置运行时 helper：地图目录定位、地图列表读取、配置读写、capture geometry 或 game-view/monitor rect 计算，仍保持主类 UI 入口不变。

## [REFACTOR] 2026-05-23 - Navigation map runtime split batch 3
### A. 变更范围声明（执行前）
**触发任务：** 继续自主推进导航页面职责分离。

**直接计划变更文件：**
- `gui/modes/navigation_mode.py`
- `gui/modes/navigation/map_runtime.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：**
- 移出项目根目录/map_data 路径定位、地图列表读取、地图文件夹解析、`NavConfig` 加载/保存、DPR 物理中心换算、capture geometry 计算。
- 保留 `NavigationModeWidget.refresh_map_list()`、`load_map()`、`_build_capture_geometry()`、`_save_nav_config()` 等原入口；主类仍负责按钮状态、弹窗和状态栏。
- 不改变 config.json 字段、不改变默认参数、不改变截图矩形计算结果。

### C. 变更结果
**实际变更：**
- (verified) 新增 `gui/modes/navigation/map_runtime.py`。
- (verified) `refresh_map_list()` 通过 `list_map_names(__file__)` 获取地图名，缺失时仍显示原文案 `未找到 map_data 文件夹`。
- (verified) `load_map()` 通过 `resolve_map_folder()` 和 `load_nav_config()` 解析地图路径与配置；缺少配置仍使用默认 `NavConfig()` 并弹出原警告。
- (verified) 逻辑中心到物理中心换算委托 `physical_center_from_logical()`。
- (verified) `_build_capture_geometry()` 委托 `map_runtime.build_capture_geometry()`，保留 region 模式与 center 模式旧返回契约。
- (verified) `_save_nav_config()` 委托 `save_nav_config()` 写回当前地图 `config.json`，保存字段和格式保持 `NavConfig.to_dict()` + `indent=4` + `ensure_ascii=False`。
- (verified) 清理了 `navigation_mode.py` 中不再需要的 `os/json` import 和旧路径计算残留。

**CODEBASE.md 更新内容：**
- 新增目录结构和模块详解：`gui/modes/navigation/map_runtime.py`。
- 新增 `map_runtime.build_capture_geometry()` 函数索引。
- 更新结构审计快照，记录第三批拆分结果。

**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/modes/navigation_mode.py` | (partial) | (partial) | 4 | 本轮重读地图列表、配置读写、capture geometry 区域并改为 helper 委托。 |
| `gui/modes/navigation/map_runtime.py` | PENDING | 深度完整 | 1 | 新增地图运行时 helper，只做路径/配置/几何数据处理，不处理 UI。 |

**验证：**
- `D:\ACloud\.venv\Scripts\python.exe -c "from gui.modes.navigation.map_runtime import project_root_from_file, map_data_dir, list_map_names; ..."` 已确认 project root 为 `D:\ACloud\minimap_stitcher copy 13`，map_data 路径为项目内 `map_data`，当前识别到 17 个地图目录。
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\modes\navigation_mode.py gui\modes\navigation\map_runtime.py gui\modes\navigation\event_adapter.py gui\modes\navigation\event_overlay.py gui\modes\navigation\route_overlay.py` 待最终复跑。
- `D:\ACloud\.venv\Scripts\python.exe -c "from gui.modes.navigation_mode import NavigationModeWidget; from gui.modes.navigation.map_runtime import load_nav_config, save_nav_config, build_capture_geometry; print('imports ok')"` 待最终复跑。

**下一轮计划：**
- 下一批继续在导航 GUI 层内拆矩形/overlay runtime：`_update_monitor_rect()`、`_update_game_view_rect()` 和 overlay screen rect 逻辑可进入 `gui/modes/navigation/viewport_overlay.py`，降低主类绘图细节。

## [REFACTOR] 2026-05-23 - Navigation viewport overlay split batch 4
### A. 变更范围声明（执行前）
**触发任务：** 继续自主推进导航页面职责分离。

**直接计划变更文件：**
- `gui/modes/navigation_mode.py`
- `gui/modes/navigation/viewport_overlay.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：**
- 移出屏幕幕布逻辑坐标矩形计算、监控区域地图矩形计算、真实主画面地图矩形计算。
- 主类仍负责调用 `overlay.set_rect_and_show()` 和更新已有 QGraphicsRectItem，不改变颜色、zValue、可见性或触发时机。
- 不改变 `monitor_region` / `monitor_logical_center` / `game_view_map_size` 语义。

### C. 变更结果
**实际变更：**
- (verified) 新增 `gui/modes/navigation/viewport_overlay.py`。
- (verified) `_update_overlay_display()` 使用 `screen_overlay_geometry()` 计算逻辑坐标屏幕幕布 rect 和 anchor，仍由主类调用 `overlay.set_rect_and_show()`。
- (verified) `_update_monitor_rect()` 使用 `monitor_scene_rect()` 计算绿色截图范围框地图矩形，仍由主类更新已有 `monitor_rect_item`。
- (verified) `_update_game_view_rect()` 使用 `game_view_scene_rect()` 计算橙色主画面范围框地图矩形；尺寸无效时仍隐藏该 item。
- (verified) 不改变 QPen/QColor/zValue 创建逻辑，也不改变刷新触发时机。

**CODEBASE.md 更新内容：**
- 新增目录结构和模块详解：`gui/modes/navigation/viewport_overlay.py`。
- 新增 `viewport_overlay.monitor_scene_rect()` 和 `viewport_overlay.game_view_scene_rect()` 函数索引。
- 更新结构审计快照，记录第四批拆分结果。

**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/modes/navigation_mode.py` | (partial) | (partial) | 5 | 本轮重读屏幕幕布、绿色监控框、橙色主画面框更新逻辑并委托几何 helper。 |
| `gui/modes/navigation/viewport_overlay.py` | PENDING | 深度完整 | 1 | 新增矩形几何 helper，只返回数据，不创建 Qt item。 |

**验证：**
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\modes\navigation_mode.py gui\modes\navigation\viewport_overlay.py` 已通过初检，待最终全量轻量复跑。

**下一轮计划：**
- 导航页面低风险 helper 拆分已完成 4 批；下一步转向 `mapping_widget.py`，先拆 `gui/modes/mapping/save_load.py` 或 `params_adapter.py`，移动全局 config/map save/load 逻辑，保留 `MappingWidget` 入口。

## [REFACTOR] 2026-05-23 - Mapping save/load split batch 5
### A. 变更范围声明（执行前）
**触发任务：** 继续自主推进全项目结构优化，从导航页面转向绘图页面低风险拆分。

**直接计划变更文件：**
- `gui/modes/mapping_widget.py`
- `gui/modes/mapping/__init__.py`
- `gui/modes/mapping/save_load.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：**
- 移出项目根目录解析、全局 `config.json` 读写、地图保存配置 dict 构造、地图文件夹创建。
- `MappingWidget.save_map()`、`save_config()`、`load_saved_params()` 原入口保留，仍负责弹窗、UI 控件同步和调用 stitcher/recognizer。
- 不改变保存文件名、保存字段、默认值或 map_data 目录结构。

### C. 变更结果
**实际变更：**
- (verified) 新增 `gui/modes/mapping/` helper 包。
- (verified) 新增 `gui/modes/mapping/save_load.py`，承接项目根目录解析、`map_data/<name>` 创建、根级/地图级 `config.json` 读写和 mapping config dict 构造。
- (verified) `MappingWidget.save_map()` 保留原方法入口，仍负责地图名弹窗、调用 `stitcher.save_map_package()` 和成功提示；路径/配置写入委托 helper。
- (verified) `MappingWidget.save_config()` 保留原方法入口，委托 `build_mapping_config()` + `save_root_config()`。
- (verified) `MappingWidget.load_saved_params()` 保留原方法入口，委托 `load_root_config()`；根配置不存在仍直接返回，JSON/KeyError 仍由原 except 处理。
- (verified) 清理 `mapping_widget.py` 中本批不再需要的 `sys/os/ctypes/datetime` import；保留 `json` 仅用于原 `JSONDecodeError` except 契约。

**CODEBASE.md 更新内容：**
- 新增目录结构说明：`gui/modes/mapping/__init__.py`、`gui/modes/mapping/save_load.py`。
- 新增模块详解：`mapping_widget.py`、`mapping/__init__.py`、`mapping/save_load.py`。
- 新增函数索引：`build_mapping_config()`、`ensure_map_folder()`、`save_root_config()`、`load_root_config()`。
- 新增数据流：绘图模式地图保存和根配置加载。
- 更新结构审计快照，记录第五批拆分结果和 mapping 后续低风险候选。

**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/modes/mapping_widget.py` | 浅读 | (partial) | 2 | 本轮重读保存/加载区域并改为 helper 委托；捕获循环和渲染区域仍未深拆。 |
| `gui/modes/mapping/__init__.py` | PENDING | 深度完整 | 1 | 新增空包入口，确认无业务逻辑。 |
| `gui/modes/mapping/save_load.py` | PENDING | 深度完整 | 1 | 新增纯路径/JSON/config helper，不接触 Qt 控件和拼接算法生命周期。 |

**验证：**
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\modes\mapping_widget.py gui\modes\mapping\__init__.py gui\modes\mapping\save_load.py` 已通过。

**下一轮计划：**
- 继续在绘图页做低风险拆分：优先把 `update_displays()` / `_show_image()` 中的图像转 QPixmap、全局地图着色、路径线/视野框/当前位置绘制移动到 `gui/modes/mapping/map_renderer.py`，保留 `MappingWidget.update_displays()` 入口和 UI setPixmap 调用时机。

## [REFACTOR] 2026-05-23 - Mapping renderer split batch 6
### A. 变更范围声明（执行前）
**触发任务：** 继续自主推进绘图页面职责分离，优先移动纯渲染逻辑。

**直接计划变更文件：**
- `gui/modes/mapping_widget.py`
- `gui/modes/mapping/map_renderer.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：**
- 移出 OpenCV 全局地图着色、导航路径 polyline、视野框、当前位置圆点绘制和 BGR/RGB QPixmap 转换。
- `MappingWidget.update_displays()` 和 `_show_image()` 原入口保留，仍负责调用 stitcher、读取 UI/runtime 状态、写入 Qt label/map widget。
- 不改变颜色、线宽、crop offset、路径坐标换算、当前位姿显示或 fallback 逻辑。

### C. 变更结果
**实际变更：**
- (verified) 新增 `gui/modes/mapping/map_renderer.py`。
- (verified) `pixmap_from_bgr()` 承接 BGR -> RGB -> QImage -> QPixmap 转换，保留 `.copy()` 避免临时 numpy buffer 生命周期问题。
- (verified) `unpack_enhanced_map_result()` 保留旧 `get_enhanced_map()` tuple/fallback 解包契约。
- (verified) `render_global_map_pixmap()` 承接全局地图灰度转 BGR、路径线、绿色视野框、当前位置圆点绘制，颜色和线宽保持旧值。
- (verified) `MappingWidget.update_displays()` 保留入口，只负责取 stitcher 结果、保存 `map_crop_offset`、选择 fallback `capture_size/player_pos` 并设置 `global_map_widget`。
- (verified) `MappingWidget._show_image()` 保留入口，委托 `pixmap_from_bgr()` 后设置 label pixmap。
- (verified) 移除 `mapping_widget.py` 中不再需要的 `cv2/numpy/QImage/QPixmap` import。

**CODEBASE.md 更新内容：**
- 新增目录结构说明和模块详解：`gui/modes/mapping/map_renderer.py`。
- 更新 `mapping_widget.py` 职责说明，标明渲染细节已委托。
- 新增函数索引：`render_global_map_pixmap()`、`pixmap_from_bgr()`。
- 更新结构审计快照，记录第六批拆分结果。

**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/modes/mapping_widget.py` | (partial) | (partial) | 3 | 本轮重读 `update_displays()` / `_show_image()` 并改为渲染 helper 委托；捕获循环和参数控件同步仍未深拆。 |
| `gui/modes/mapping/map_renderer.py` | PENDING | 深度完整 | 1 | 新增纯图像渲染 helper，只返回 QPixmap，不读取 app_context、不设置 Qt 控件。 |

**验证：**
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\modes\mapping_widget.py gui\modes\mapping\map_renderer.py gui\modes\mapping\save_load.py gui\modes\mapping\__init__.py` 已通过。
- `D:\ACloud\.venv\Scripts\python.exe -c "from gui.modes.mapping_widget import MappingWidget; from gui.modes.mapping.map_renderer import render_global_map_pixmap, pixmap_from_bgr; print('mapping renderer imports ok')"` 已通过。

**下一轮计划：**
- 优先检查 `mapping_widget.py` 的参数控件同步区：HSV、feature、merge、advanced settings、load_saved_params UI 回填是否能拆成 `params_adapter.py`。若发现需要大范围信号阻断或默认参数调整，则暂缓，转向 dialog helper。

## [REFACTOR] 2026-05-23 - Mapping params adapter split batch 7
### A. 变更范围声明（执行前）
**触发任务：** 继续绘图页面低风险职责分离，拆出参数控件到运行时参数的轻量桥接。

**直接计划变更文件：**
- `gui/modes/mapping_widget.py`
- `gui/modes/mapping/params_adapter.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：**
- 移出 feature 参数 dict 构造、HSV 开关应用、merge weight 应用、已加载 recognizer/stitcher 参数写回控件。
- 保留 `MappingWidget.update_hsv_params()`、`update_feature_params()`、`update_merge_params()`、`load_saved_params()` 原入口。
- 不改变默认值、字段名、setChecked/setValue 顺序或信号触发行为；不新增信号阻断。

### C. 变更结果
**实际变更：**
- (verified) 新增 `gui/modes/mapping/params_adapter.py`。
- (verified) `apply_hsv_toggles()` 承接墙体/迷雾复选框到 recognizer 字段写入。
- (verified) `feature_params_from_widgets()` 承接 feature 控件到 `recognizer.set_params()` dict 的构造，字段名和默认读取来源保持不变。
- (verified) `apply_merge_weight()` 承接 merge weight spinbox 到 stitcher `weight_add` 字段写入。
- (verified) `sync_recognizer_widgets()` 和 `sync_stitcher_widgets()` 承接加载配置后的控件回填，默认值和 `setChecked/setValue` 顺序保持旧实现。
- (verified) `MappingWidget` 保留原更新方法入口，并仍负责调用 `recognizer.set_params()`、`stitcher.set_params()` 和 `save_config()`。

**CODEBASE.md 更新内容：**
- 新增目录结构说明和模块详解：`gui/modes/mapping/params_adapter.py`。
- 更新 `mapping_widget.py` 职责说明，标明参数控件桥接已委托。
- 新增函数索引：`feature_params_from_widgets()`、`sync_recognizer_widgets()`、`apply_hsv_toggles()`。
- 更新结构审计快照，记录第七批拆分结果。

**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/modes/mapping_widget.py` | (partial) | (partial) | 4 | 本轮重读 HSV/feature/merge 参数更新和加载回填区域，并改为 params adapter 委托。 |
| `gui/modes/mapping/params_adapter.py` | PENDING | 深度完整 | 1 | 新增参数控件桥接 helper，不保存配置、不阻断信号、不创建控件。 |

**验证：**
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\modes\mapping_widget.py gui\modes\mapping\params_adapter.py gui\modes\mapping\map_renderer.py gui\modes\mapping\save_load.py gui\modes\mapping\__init__.py` 已通过。
- `D:\ACloud\.venv\Scripts\python.exe -c "from gui.modes.mapping_widget import MappingWidget; from gui.modes.mapping.params_adapter import feature_params_from_widgets, sync_recognizer_widgets; print('mapping params imports ok')"` 已通过。

**下一轮计划：**
- 暂缓继续拆 `mapping_widget.py` 的捕获循环，因为会触及 screen_capture、tracker、recognizer、stitcher 的时序和 fallback 行为；下一步更稳妥的是转向 dialog 层，先审 `gui/dialogs/color_picker_dialog.py` 或 `advanced_settings_dialog.py` 中可纯拆的预设/参数映射。

## [REFACTOR] 2026-05-23 - Advanced settings params adapter split batch 8
### A. 变更范围声明（执行前）
**触发任务：** 转向 dialog 层低风险拆分，先处理高级参数弹窗中纯参数控件映射逻辑。

**直接计划变更文件：**
- `gui/dialogs/advanced_settings_dialog.py`
- `gui/dialogs/advanced_settings/__init__.py`
- `gui/dialogs/advanced_settings/params_adapter.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：**
- 移出高级参数弹窗的当前参数写入控件、控件采集成 dict、重置默认值、加载参数文件后回填控件、预设参数写入控件逻辑。
- 保留 `AdvancedSettingsDialog` 类、`get_params()`、`load_current_params()`、`apply_params()`、`reset_to_default()`、`apply_loaded_params()`、`apply_preset()` 原入口。
- 不改变默认值、字段名、控件写入顺序、文件 IO、实时应用 recognizer/stitcher 的时机或打印文案。

### C. 变更结果
**实际变更：**
- (verified) 新增 `gui/dialogs/advanced_settings/` helper 包。
- (verified) 新增 `params_adapter.py`，承接当前参数加载到控件、控件采集为参数 dict、默认重置、已加载参数回填和预设写入。
- (verified) `AdvancedSettingsDialog.load_current_params()`、`apply_params()`、`reset_to_default()`、`apply_loaded_params()`、`apply_preset()` 原入口保留，改为委托 helper。
- (verified) 文件保存/加载、JSON 格式、状态栏文案、`current_params` 更新、recognizer/stitcher 实时应用和 print 文案仍留在原 dialog 类。
- (verified) 修正 helper 设计，`reset_widgets_to_default()` 不额外写旧实现没有写的 `blur_strength_spin`；`load_params_to_widgets()` 仍保持旧加载当前参数时写 `blur_strength_spin=3`。

**CODEBASE.md 更新内容：**
- 新增目录结构说明：`gui/dialogs/advanced_settings_dialog.py`、`gui/dialogs/advanced_settings/__init__.py`、`gui/dialogs/advanced_settings/params_adapter.py`。
- 新增模块详解：高级参数弹窗主类和 params adapter。
- 新增函数索引：`collect_params_from_widgets()`、`load_params_to_widgets()`、`apply_preset_to_widgets()`。
- 更新结构审计快照，记录第八批 dialog 层拆分结果。

**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/dialogs/advanced_settings_dialog.py` | (partial) | (partial) | 2 | 本轮重读参数加载/应用/默认/预设/文件加载回填区域并改为 helper 委托；UI 构造仍未拆。 |
| `gui/dialogs/advanced_settings/__init__.py` | PENDING | 深度完整 | 1 | 新增空包入口，确认无业务逻辑。 |
| `gui/dialogs/advanced_settings/params_adapter.py` | PENDING | 深度完整 | 1 | 新增高级参数控件映射 helper，不做文件 IO、不调用 recognizer/stitcher。 |

**验证：**
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\dialogs\advanced_settings_dialog.py gui\dialogs\advanced_settings\__init__.py gui\dialogs\advanced_settings\params_adapter.py` 已通过。
- `D:\ACloud\.venv\Scripts\python.exe -c "from gui.dialogs.advanced_settings_dialog import AdvancedSettingsDialog; from gui.dialogs.advanced_settings.params_adapter import collect_params_from_widgets, load_params_to_widgets; print('advanced settings imports ok')"` 已通过。

**下一轮计划：**
- 继续 dialog 层审计但暂缓大拆 UI 构造；`color_picker_dialog.py` 的 HSV range 计算、预览渲染和 debug 输出可作为下一批候选，但要避免改变采样结果和日志文件。

## [REFACTOR] 2026-05-23 - Color picker helper split batch 9
### A. 变更范围声明（执行前）
**触发任务：** 继续 dialog 层低风险拆分，处理颜色选择弹窗中可复用的 HSV range 计算和图像转换 helper。

**直接计划变更文件：**
- `gui/dialogs/color_picker_dialog.py`
- `gui/dialogs/color_picker/__init__.py`
- `gui/dialogs/color_picker/hsv_ranges.py`
- `gui/dialogs/color_picker/image_renderer.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：**
- 移出 HSV 样本范围计算和 BGR/灰度图像到 QPixmap 的转换。
- 保留 `ColorPickerDialog.calculate_hsv_ranges()`、`_calculate_range()`、`_show_image()` 原入口。
- 不改变采样点记录、推荐关闭饱和度过滤的阈值、结果文案、preview 逻辑或 debug 文件输出。

### C. 变更结果
**实际变更：**
- (verified) 新增 `gui/dialogs/color_picker/` helper 包。
- (verified) 新增 `hsv_ranges.py`，承接 BGR->HSV 转换、采样点 HSV 提取、HSV 范围计算和平均饱和度计算。
- (verified) 新增 `image_renderer.py`，承接 OpenCV 图像转 QPixmap 和墙体/人物采样 marker 绘制。
- (verified) `ColorPickerDialog.calculate_hsv_ranges()`、`_calculate_range()`、`_show_image()` 原入口保留，改为委托 helper。
- (verified) `update_preview()` 保持在 dialog 内，mask、形态学、debug png/txt 输出和日志内容未迁移。
- (verified) 保留原图像转换语义：颜色选择弹窗仍使用 `QPixmap.fromImage(q_img)`，未引入 `.copy()` 行为差异。

**CODEBASE.md 更新内容：**
- 新增目录结构说明：`gui/dialogs/color_picker_dialog.py`、`gui/dialogs/color_picker/__init__.py`、`hsv_ranges.py`、`image_renderer.py`。
- 新增模块详解：颜色选择弹窗主类和两个 helper。
- 新增函数索引：`calculate_hsv_range()`、`pixmap_from_image()`、`draw_sample_markers()`。
- 更新结构审计快照，记录第九批 dialog 层拆分结果。

**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/dialogs/color_picker_dialog.py` | (partial) | (partial) | 2 | 本轮重读 HSV 范围计算和图像显示区域并改为 helper 委托；preview debug 输出仍保留原类内。 |
| `gui/dialogs/color_picker/__init__.py` | PENDING | 深度完整 | 1 | 新增空包入口，确认无业务逻辑。 |
| `gui/dialogs/color_picker/hsv_ranges.py` | PENDING | 深度完整 | 1 | 新增 HSV 采样/范围计算 helper，保持旧容差和边界算法。 |
| `gui/dialogs/color_picker/image_renderer.py` | PENDING | 深度完整 | 1 | 新增图像转 pixmap 和采样点 marker 绘制 helper，保持旧颜色/半径/缩放公式。 |

**验证：**
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\dialogs\color_picker_dialog.py gui\dialogs\color_picker\__init__.py gui\dialogs\color_picker\hsv_ranges.py gui\dialogs\color_picker\image_renderer.py` 已通过。
- `D:\ACloud\.venv\Scripts\python.exe -c "from gui.dialogs.color_picker_dialog import ColorPickerDialog; from gui.dialogs.color_picker.hsv_ranges import calculate_hsv_range; from gui.dialogs.color_picker.image_renderer import pixmap_from_image; print('color picker imports ok')"` 已通过。

**下一轮计划：**
- 本阶段已覆盖导航、绘图、advanced settings、color picker 的低风险 GUI 拆分；后续建议暂停大改，先由用户做一次 GUI smoke test。下一阶段可审 `nav_params_dialog.py` 字段映射或转向 core/stitching，但风险明显高于本批。
## [BUGFIX] 2026-05-23 - Event dialog live refresh scope
### A. SYNC 范围声明
**触发任务：** 修复传送门事件窗口可见时导航循环每帧完整刷新，导致刷新按钮/测试按钮交互被持续 UI 重建干扰的问题。
**直接计划变更文件：**
- `gui/dialogs/event_manager_dialog.py`
- `gui/modes/navigation_mode.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：**
- 保留 `EventManagerDialog.refresh()` 作为完整刷新入口，供手动刷新、上下文切换、配置变化、保存后使用。
- 新增任务表轻量刷新入口，导航循环只更新任务状态表，不重建事件列表、复选框、参数控件或测试按钮。
- 不修改事件检测、传送门测试开停逻辑、默认配置或任务调度行为。
### C. SYNC 结果
**根因确认：**
- (verified) `NavigationModeWidget.navigation_loop()` 在事件窗口可见时，每次 `EventCoordinator.update()` 后都调用 `event_dialog.refresh()`。
- (verified) `EventManagerDialog.refresh()` 会调用 `_refresh_events()`，清空并重建事件表、事件复选框、参数面板，再刷新任务表。
- (inferred) 高频完整刷新会在鼠标交互期间反复重建控件，使刷新/测试按钮表现为持续被选中或点击难以稳定注册。

**实际变更：**
- (verified) `EventManagerDialog.refresh()` 保持完整刷新语义不变。
- (verified) 新增 `EventManagerDialog.refresh_tasks()`，仅委托 `_refresh_tasks()` 更新任务表和状态摘要。
- (verified) `NavigationModeWidget.navigation_loop()` 的两个事件窗口实时刷新调用改为 `refresh_tasks()`，不再每帧重建事件选配表和参数控件。
- (verified) 未修改事件检测、传送门测试开停、事件配置保存、默认参数或地图数据。

**CODEBASE.md 更新内容：**
- 更新 `gui/dialogs/event_manager_dialog.py` 模块说明，区分完整刷新和运行中轻量任务刷新。
- 更新 `gui/modes/navigation_mode.py` 注意事项，说明导航循环只调用 `refresh_tasks()`。
- 新增 `EventManagerDialog.refresh_tasks(self) -> None` 函数索引，并修订事件管理 UI Flow。

**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/dialogs/event_manager_dialog.py` | (partial) | (partial) | 2 | 本轮重读 `refresh()`、`_refresh_events()`、`_refresh_tasks()`、测试按钮信号，新增轻量任务刷新入口。 |
| `gui/modes/navigation_mode.py` | (partial) | (partial) | 6 | 本轮重读导航循环事件 coordinator 更新分支，将可见事件窗口的高频刷新改为任务表刷新。 |
## [BUGFIX] 2026-05-23 - Portal bounce caused by duplicate GUI instances
### A. SYNC 范围声明
**触发任务：** 排查用户点击“测试传送门”后在两个传送门之间反复传送的问题。
**直接变更文件：**
- `main.py`
- `core/events/debug.py`
- `core/events/runner.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：**
- Windows 启动路径增加单实例保护，避免旧/新两个 GUI 进程同时控制游戏。
- 事件日志增加 PID，后续可直接判断是否多进程混写。
- 事件 runner 增加终态任务保护，不允许 completed/ignored task 被再次启动或继续执行。

### C. SYNC 结果
**根因确认：**
- (verified) `logs/event_runtime.log` 同一会话内出现 `portal:1 seen=258 state=running` 后又出现 `task created id=portal:1`，单个 `EventCoordinator` 不可能让 `_next_id` 回绕。
- (verified) 本机同时存在两组 `pythonw.exe` GUI 进程，每组都有一个主窗口进程，说明多个程序实例在同一时间识别和操作游戏。
- (inferred) 两个实例同时写入同一个事件日志并向游戏发送按键，表现为一个实例完成入口传送后，另一个实例继续接管出口/入口任务，导致来回传送。

**实际变更：**
- (verified) `main.py` 新增基于项目路径 hash 的 Win32 mutex 单实例锁；同项目第二个实例启动时直接退出。
- (verified) `main.py` 新增已有主窗口扫描，用于拦截已经运行但没有 mutex 的旧构建实例。
- (verified) `core/events/debug.py` 的 `event_log()` 输出加入 `pid=<pid>`，用于识别多进程日志交错。
- (verified) `core/events/runner.py` 在 `update()` 和 `_start_task()` 两处拒绝 `COMPLETED/IGNORED` 终态任务。

**CODEBASE.md 更新内容：**
- 更新 Windows 启动外部集成说明，记录管理员提权后的单实例锁和主窗口检测。
- 更新事件日志诊断说明，记录 PID 输出。
- 更新传送门事件当前行为，记录 runner 终态任务防护。

**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `main.py` | (partial) | (partial) | 2 | 本轮重读管理员提权和 GUI 启动前置路径，新增单实例锁和已有窗口检测。|
| `core/events/debug.py` | (partial) | (partial) | 2 | 本轮重读事件日志写入路径，新增 PID 字段以定位多进程混写。|
| `core/events/runner.py` | (partial) | (partial) | 2 | 本轮重读 handler 生命周期，新增终态任务拒绝保护。|

**验证：**
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile main.py core\events\debug.py core\events\runner.py` 已通过。

## [FEATURE] 2026-05-23 - Portal teleport session completion
### A. SYNC 范围声明
**触发任务：** 用户确认传送门事件完成标准：一次传送成功后，传入门和传出门都应标记完成，不需要反复传送；同时要覆盖出口在独立地图、未提前识别到出口门的情况。
**直接变更文件：**
- `core/events/types/portal/handler.py`
- `core/events/runner.py`
- `core/events/memory.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：**
- 传送门 COMPLETE action 从“单 task 完成”扩展为“teleport session 完成”。
- 入口 task 和出口 task 共享 `teleport_session_id`，后续不再进入调度。
- 出口门没提前识别时创建 synthetic completed exit task，用于独立地图传送完成闭环和冷却。

### C. SYNC 结果
**关键发现：**
- (verified) `PortalEventHandler` 原完成标准只返回 `entry_pos/exit_pos`，语义是当前 task 完成。
- (verified) `EventRunner` 原逻辑用 `mark_related_completed()` 根据 `exit_pos` 完成一个附近 task，但没有会话 ID，也会把已有出口 task 坐标改成人物落点。
- (verified) `EventScheduler` 只按 running/pending 选任务，不理解入口/出口属于同一次传送。

**实际变更：**
- (verified) `PortalEventHandler` 在 COMPLETE metadata 中加入 `completion_kind="teleport"` 和 `entry_task_id`。
- (verified) `EventRunner` 收到 teleport complete 后调用 `EventMemory.complete_teleport_session()`；非 teleport complete 保留原单 task 完成路径。
- (verified) `EventMemory.complete_teleport_session()` 生成 `teleport_session_id`，把入口标记 `teleport_role=entry` 并 completed。
- (verified) `EventMemory.complete_teleport_session()` 优先用传送后人物落点附近已有 active portal task 作为出口并 completed；找不到时创建 synthetic completed exit task。
- (verified) 完成 session 后分别对入口和出口调用 `suppress_nearby_pending()`，避免同一对门继续进入调度。

**CODEBASE.md 更新内容：**
- 更新 Portal Event Current Behavior，记录 teleport session 完成语义、entry/exit metadata、synthetic exit、冷却作为二级防护。

**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/events/types/portal/handler.py` | (partial) | (partial) | 3 | 本轮重读 wait_result 完成分支，新增 teleport completion metadata。|
| `core/events/runner.py` | (partial) | (partial) | 3 | 本轮重读 COMPLETE 分支，改为按 `completion_kind` 分派到 teleport session 或普通完成。|
| `core/events/memory.py` | (partial) | (partial) | 3 | 本轮重读 task lifecycle/cooldown，新增 `complete_teleport_session()` 和出口 task 查找。|

**验证：**
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\events\types\portal\handler.py core\events\runner.py core\events\memory.py` 已通过。

## [BUGFIX] 2026-05-23 - Close paired portal completion detection
### A. SYNC 范围声明
**触发任务：** 用户反馈按 `D` 后角色位置已经改变到另一个传送门附近，但传送门事件仍保持处理中并继续来回传送。
**直接变更文件：**
- `core/events/models.py`
- `core/events/coordinator.py`
- `core/events/types/portal/handler.py`
- `core/events/runner.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：**
- `EventTick` 增加当前事件任务快照，handler 可在不直接依赖 memory 的情况下判断其它已知事件点。
- 传送门完成判定除大位移和环境变化外，增加“落在另一个已知 portal 附近且明显更接近出口”的分支。
- 修正 `EventRunner` COMPLETE 分支缩进，保证 teleport complete 后才清理 runner，FAIL 分支保持独立。

### C. SYNC 结果
**根因确认：**
- (verified) `logs/event_runtime.log` 显示 `portal:1` 按 `D` 前玩家约在 `(3462,2278)`，之后约在 `(3526,2334)`，位移约 84px，低于 `teleport_min_distance=180`。
- (verified) 同一批日志里已提前识别出 `portal:2`，其位置约 `(3513,2326)`，传送后玩家离它约 16px，说明传送实际已经成功。
- (verified) 原 `PortalEventHandler._teleport_completed()` 只接受大位移或小地图环境差异，没有利用已知出口 task，因此近距离双门会超时失败并调度另一个门。

**实际变更：**
- (verified) `EventTick` 新增 `event_tasks` 字段，作为 coordinator 写入的 memory 快照。
- (verified) `EventCoordinator.update()` 在 `memory.merge_observations()` 之后写入 `tick.event_tasks = self.memory.tasks()`，确保 handler 看到本帧合并后的最新双门任务。
- (verified) `PortalEventHandler._teleport_completed()` 在小位移情况下调用 `_near_known_exit_portal()`，当玩家落在另一个 active portal 的 `exit_complete_radius` 内且明显比入口更近时直接完成传送。
- (verified) `_near_known_exit_portal()` 排除当前入口 task、completed/ignored task 和非 portal task，避免误把入口或终态任务当出口。
- (verified) `EventRunner.update()` 修正 COMPLETE/FAIL 分支缩进，避免 `_clear()` 脱离 COMPLETE 块造成语法错误或生命周期错乱。

**CODEBASE.md 更新内容：**
- 更新 `core/events/*` 注意事项，记录 `tick.event_tasks` 的写入时机。
- 更新 `build_event_tick()`、事件管理 flow、`exit_complete_radius`、Portal Event Current Behavior 和 Event Localization Contract。

**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/events/models.py` | (partial) | (partial) | 2 | 本轮重读 `EventTick` 契约，新增 `event_tasks` 运行时任务快照字段。 |
| `core/events/coordinator.py` | (partial) | (partial) | 2 | 本轮重读事件 detect/localize/memory/scheduler 顺序，确认快照应在 memory 合并后写入。 |
| `core/events/types/portal/handler.py` | (partial) | (partial) | 4 | 本轮重读 wait_result 和传送完成判定，新增已知出口门完成分支和入口距离防误判。 |
| `core/events/runner.py` | (partial) | (partial) | 4 | 本轮重读 COMPLETE/FAIL 生命周期，修正缩进并保留 terminal/requeue 保护。 |

**验证：**
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\events\runner.py core\events\models.py core\events\coordinator.py core\events\types\portal\handler.py core\events\memory.py` 已通过。

## [FEATURE] 2026-05-23 - Portal auto-navigation integration and reset button
### A. SYNC 范围声明
**触发任务：** 用户确认传送门事件基本可用，要求接入自动导航，并在事件管理中增加按钮刷新传送门状态，方便反复测试。
**直接变更文件：**
- `gui/dialogs/event_manager_dialog.py`
- `gui/modes/navigation_mode.py`
- `core/events/coordinator.py`
- `core/events/memory.py`
- `core/events/position_stabilizer.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：**
- 自动导航开启时，传送门事件与手动测试走同一套 detect/localize/schedule/MOVE_TO/PRESS_KEY/COMPLETE pipeline。
- 事件终态 action 也由导航循环消费，避免 COMPLETE/FAIL 帧同时推进普通路线导航。
- 新增 portal 运行时重置入口，清空任务和定位聚类但不改事件配置。

### C. SYNC 结果
**关键发现：**
- (verified) `navigation_loop()` 已用 `auto_navigation_enabled or portal_test_controller.active` 控制 `EventCoordinator.update(..., run_handlers=...)`，所以自动导航已有 handler 推进入口。
- (verified) 原逻辑只把 `MOVE_TO/CLICK_SCREEN/PRESS_KEY/WAIT` 视为事件接管；`COMPLETE/FAIL` 不进入事件执行分支，手动测试终态停止和自动导航收口不稳定。
- (verified) 事件窗口只有完整刷新和测试传送门按钮，没有运行时清空已完成/忽略 portal 任务和定位聚类的入口，导致同一对门反复测试需要重启或等待冷却。

**实际变更：**
- (verified) `NavigationModeWidget.navigation_loop()` 将事件 `COMPLETE/FAIL` 也纳入本帧事件占用，先由 `EventActionExecutor` 消费终态并清理 event path overlay；自动导航从下一帧恢复普通路线。
- (verified) `EventManagerDialog` 新增 `reset_portal_requested` 信号和“刷新传送门状态”按钮。
- (verified) `NavigationModeWidget._reset_portal_event_state()` 接收按钮事件，停止手动 portal 测试、调用 coordinator reset、清 overlay、刷新任务表并打印 `portal event state reset` 日志。
- (verified) `EventCoordinator.reset_event_type()` 清理当前同类型 handler、memory tasks、position clusters、last detections/observations、last selected task 和 last action。
- (verified) `EventMemory.clear_event_type()` 清空指定事件类型的任务和对应节流日志；`EventPositionStabilizer.clear_event_type()` 清空指定事件类型定位聚类。

**CODEBASE.md 更新内容：**
- 更新 `EventManagerDialog` 和 `NavigationModeWidget` 注意事项。
- 更新 `core/events/*` 运行时 reset 入口说明。
- 更新事件管理 UI Flow，加入“刷新传送门状态”和事件终态 action 收口。
- 更新 Event Manager UI 说明，记录“刷新传送门状态”按钮语义。

**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `gui/dialogs/event_manager_dialog.py` | (partial) | (partial) | 3 | 本轮重读 footer 按钮和信号，新增 portal 状态重置信号和按钮。 |
| `gui/modes/navigation_mode.py` | (partial) | (partial) | 7 | 本轮重读自动导航事件接管和终态分支，接入 portal reset 并让 COMPLETE/FAIL 占用事件帧。 |
| `core/events/coordinator.py` | (partial) | (partial) | 3 | 本轮新增按事件类型清理 coordinator 运行时状态的入口。 |
| `core/events/memory.py` | (partial) | (partial) | 4 | 本轮新增指定事件类型任务清理入口，用于反复测试清除 completed/ignored 冷却状态。 |
| `core/events/position_stabilizer.py` | (partial) | (partial) | 2 | 本轮新增指定事件类型定位聚类清理入口，避免刷新后复用旧 portal 定位样本。 |

**验证：**
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\dialogs\event_manager_dialog.py gui\modes\navigation_mode.py core\events\coordinator.py core\events\memory.py core\events\position_stabilizer.py` 已通过。

## [BUGFIX] 2026-05-23 - Portal pre-interaction mapped point click
### A. SYNC 范围声明
**触发任务：** 用户反馈传送门事件有时已经进入交互半径但游戏没有触发交互，需要降低交互半径下限，并在按 `D` 前点击一次映射的传送门点。

**直接变更文件：**
- `core/motion_controller.py`
- `core/events/config.py`
- `core/events/types/portal/config.py`
- `core/events/types/portal/definition.py`
- `core/events/types/portal/handler.py`
- `core/events/models.py`
- `core/events/action_executor.py`
- `gui/modes/navigation_mode.py`
- `gui/dialogs/event_manager_dialog.py`
- `map_data/A1/event_config.json`
- `map_data/Aa/event_config.json`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：**
- 事件管理页允许把 `interact_radius` 调到 1，用于推迟按 `D` 直到更贴近传送门。
- 传送门 handler 进入交互阶段后先发出一次带 metadata 的强制映射点点击，再等待 `portal_point_click_wait_ms` 后按 `D`。
- 强制点击走事件专用映射，不使用正常移动的最小点击半径，避免把“点传送门”放大成“朝传送门方向走一步”。

### C. SYNC 结果
**根因确认：**
- (verified) `PortalEventDefinition.config_schema()` 原 `interact_radius` 下限为 5，无法继续缩小按 `D` 的距离阈值。
- (verified) `MotionController.move_to_map_target()` 在目标距离极近时会返回 `None`，且正常移动映射会应用 `movement_min_click_radius`，不适合作为“点击映射传送门点”。
- (verified) 事件 `MOVE_TO` 原本只传目标点，不能表达“这是一次强制交互点点击，不是寻路移动点击”。

**实际变更：**
- (verified) `PortalEventDefinition.config_schema()` 将 `interact_radius` 下限降到 1，并新增可配置 `portal_point_click_wait_ms`。
- (verified) `PortalEventConfig` 与默认事件配置新增 `portal_point_click_wait_ms=350`。
- (verified) `PortalEventHandler` 在进入 `interact_radius` 后先返回 `EventAction.move_to(..., metadata={"force_click_target": True})`，随后等待 `portal_point_click_wait_ms`，再发送 `D`。
- (verified) `EventAction.move_to()` 支持 metadata，`EventActionExecutor` 将 metadata 传给 GUI move callback。
- (verified) `NavigationModeWidget._execute_event_move_to()` 对 `force_click_target` 调用 `MotionController.click_map_target_once()`，并记录 `event forced target click` 日志。
- (verified) `MotionController.click_map_target_once()` 用地图距离和 `movement_scale_factor` 精确映射目标点，不应用 `movement_min_click_radius`；玩家与传送门重叠时点击 `game_screen_center`。
- (verified) A1/Aa 的 `event_config.json` 写入 `portal_point_click_wait_ms=350`，事件管理页摘要显示该参数。

**CODEBASE.md 更新内容：**
- 更新 Input Control Current Notes，记录 `click_map_target_once()` 的事件专用语义。
- 更新 Event Manager UI，记录 `interact_radius` 下限和 `portal_point_click_wait_ms`。
- 更新 Portal Event Current Behavior，记录“强制映射点点击 -> 等待 -> 按 D”的传送门交互顺序。

**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/motion_controller.py` | (partial) | (partial) | 2 | 本轮重读 map-to-screen 点击链路，新增事件专用映射点点击，避免正常移动最小半径影响交互点点击。 |
| `core/events/types/portal/handler.py` | (partial) | (partial) | 5 | 本轮重读进入交互半径后的状态机，新增 mapped point click 和点击后等待。 |
| `core/events/types/portal/definition.py` | (partial) | (partial) | 2 | 本轮重读 schema，降低 `interact_radius` 下限并新增等待参数。 |
| `gui/modes/navigation_mode.py` | (partial) | (partial) | 8 | 本轮重读事件 move callback，新增 metadata 分支以区分事件交互点击和普通事件寻路移动。 |
| `gui/dialogs/event_manager_dialog.py` | (partial) | (partial) | 4 | 本轮重读参数摘要字段，加入 `portal_point_click_wait_ms`。 |

**验证：**
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\motion_controller.py core\events\config.py core\events\types\portal\config.py core\events\types\portal\definition.py core\events\types\portal\handler.py gui\modes\navigation_mode.py gui\dialogs\event_manager_dialog.py` 已通过。

## [BUGFIX] 2026-05-23 - Portal final approach repeat click
### A. SYNC 范围声明
**触发任务：** 用户反馈 20:34 之后传送门测试到达附近但不会按 `D`；进一步确认当前距离仍大于 `interact_radius`，正确行为应继续点击进入目标点，而不是直接兜底按 `D`。

**直接变更文件：**
- `core/events/path_mover.py`
- `core/events/types/portal/handler.py`
- `gui/modes/navigation_mode.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：**
- 保留 `interact_radius` 的严格语义：只有 `distance <= interact_radius` 才进入“点击映射传送门点 -> 按 D”。
- 只在 portal 最终靠近阶段允许同 subgoal 重复真实点击，避免停在 7px 但不再点击。
- 移除中断前临时写入的 `interact_stall_radius/interact_stall_ms`，不引入额外半径兜底判断。

### C. SYNC 结果
**根因确认：**
- (verified) 日志显示目标 `(3401,2248)`，玩家最终停在 `(3398.22,2254.47)`，距离 `7.04`。
- (verified) 当时 `interact_radius=1`，因此 `PortalEventHandler` 正确地没有进入按 `D` 分支，而是持续返回 `approach portal interact radius`。
- (verified) `EventPathMover.step()` 旧逻辑要求 cooldown 到期且 subgoal 改变至少 8px、或偏差超过 48px 才继续点击；最终阶段 subgoal 仍是 `(3401,2248)`，所以 action 被执行但没有真实 `event move click`。

**实际变更：**
- (verified) 删除临时 `interact_stall_radius/interact_stall_ms` 配置、schema 和解析字段，避免和严格交互半径语义冲突。
- (verified) `EventPathMover.step()` 新增 `force_repeat_click=False` 参数；为 True 时保留 260ms 冷却，但绕过 subgoal 变化阈值。
- (verified) `PortalEventHandler` 在 `distance > interact_radius` 的最终靠近 action 上附加 `metadata={"force_repeat_click": True}`。
- (verified) `NavigationModeWidget._execute_event_move_to()` 将 metadata 转交给 `EventPathMover.step()`。

**CODEBASE.md 更新内容：**
- 更新 Portal Event Current Behavior，记录最终靠近阶段会重复同 subgoal 点击直到进入 `interact_radius`。
- 新增 Event Move Repeat Click 说明，明确该能力只绕过 subgoal 变化阈值，不绕过点击冷却，也不改变按 `D` 条件。

**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/events/path_mover.py` | (partial) | (partial) | 2 | 本轮重读 `step()` 点击节流条件，新增 `force_repeat_click` 以解决最终目标不变导致不再真实点击。 |
| `core/events/types/portal/handler.py` | (partial) | (partial) | 6 | 本轮重读最终靠近分支，保留严格 `interact_radius`，只给移动 action 标记重复点击。 |
| `gui/modes/navigation_mode.py` | (partial) | (partial) | 9 | 本轮重读事件 move callback，转发 `force_repeat_click` metadata 到 EventPathMover。 |

**验证：**
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\events\path_mover.py core\events\models.py core\events\action_executor.py core\events\config.py core\events\types\portal\config.py core\events\types\portal\definition.py core\events\types\portal\handler.py core\motion_controller.py gui\modes\navigation_mode.py gui\dialogs\event_manager_dialog.py` 已通过。
## [SYNC] 2026-05-23 21:33 - 传送门事件四阶段案例文档
### A. SYNC 范围声明
**触发任务：** 新增一份以传送门事件为例的事件方法论文档，体现“事件识别、导航触发、事件执行、事件结束”四阶段，并检查当前代码架构是否支持将第 1、2 阶段抽成通用能力。
**直接变更文件：** 待新增 `docs/plans/2026-05-23-portal-event-case-study.md`，并同步 `CODEBASE.md` / `ITERATION_LOG.md`。
**预计连带影响：** 需要重读 `core/events/types/portal/handler.py`、`core/events/types/portal/definition.py`、`core/events/types/portal/config.py`、`core/events/path_mover.py`、`core/events/coordinator.py`、`core/events/models.py`、`gui/modes/navigation_mode.py` 中事件接入点，确认事件生命周期和通用化边界。

### C. SYNC 结果
**关键发现：**
- (verified) 当前 `portal` 已经按完整事件包暴露：`PortalEventDefinition` 对外提供配置和 detector/handler 创建，事件管理 UI 只看到完整 `portal` 事件。
- (verified) 第 1 阶段已经基本通用：`PortalMinimapDetector` 只输出局部 `EventDetection`，`EventPositionStabilizer` 统一通过墙体配准投影到全局地图，`EventMemory` 只接受稳定 `EventObservation`。
- (verified) 第 2 阶段已经有通用核心：`PortalEventHandler` 只返回 `EventAction.move_to()`，`EventPathMover` 负责事件移动的 A*、lookahead、点击节流和 fallback probe。
- (partial) 第 2 阶段仍有 GUI 耦合：`NavigationModeWidget._execute_event_move_to()` 仍持有 `nav_core.wall_layer`、`PathFinder`、`MotionController` 和事件 path overlay 上下文；后续事件增多时应抽成独立事件移动执行桥。
- (verified) 第 3 阶段传送门较简单：靠近后点击映射传送门点、等待、按 `D`，触发和执行几乎合一。
- (verified) 第 4 阶段传送门已有明确 completion strategy：位置变化、环境变化或落在另一个已知 portal 附近，并通过 `complete_teleport_session()` 同时完成入口和出口，防止反复传送。
- (conflict) 旧 `CODEBASE.md` 仍写着 `interaction="click"` 会走主画面 confirmer；本轮重读 `PortalEventHandler` 确认当前实现会强制按键交互，已修正文档避免误导。

**新增文档：**
- `docs/plans/2026-05-23-portal-event-case-study.md`：按“事件识别/定位 -> 导航触发 -> 执行事件 -> 事件结束”四阶段拆解传送门案例，并标注可通用能力、事件特定能力和当前架构风险。

**CODEBASE.md 更新内容：**
- 在目录结构中新增传送门案例文档入口。
- 新增 `Event Four-Phase Methodology` 章节，记录四阶段方法论、1/2 阶段通用化边界和 `NavigationModeWidget._execute_event_move_to()` 的后续抽离风险。
- 修正旧 portal 说明中关于 `interaction="click"` 的过期描述：当前主流程强制按 `D`，大画面 confirmer 只是保留的技术资产/探针路径。

**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/events/types/portal/handler.py` | (partial) | (partial) | 7 | 本轮按四阶段重读状态机：靠近、最终贴近、映射点点击、按 D、等待传送完成。 |
| `core/events/types/portal/definition.py` | (partial) | (partial) | 3 | 本轮确认 `portal` 对外仍是完整事件包，TUI 不暴露内部 detector/handler。 |
| `core/events/types/portal/config.py` | (partial) | (partial) | 2 | 本轮确认识别、定位、靠近、交互、完成和冷却参数分布。 |
| `core/events/path_mover.py` | (partial) | (partial) | 3 | 本轮确认事件移动通用核心：A*、lookahead、fallback probe、repeat click。 |
| `core/events/coordinator.py` | (partial) | (partial) | 2 | 本轮确认事件主链路：detect -> stabilize -> memory -> scheduler -> runner。 |
| `core/events/models.py` | (partial) | (partial) | 2 | 本轮确认 `EventDetection`/`EventObservation`/`EventTask`/`EventAction` 对四阶段的承载关系。 |
| `gui/modes/navigation_mode.py` | (partial) | (partial) | 10 | 本轮确认第 2 阶段动作执行仍耦合在导航页面，是后续抽离风险。 |
| `docs/plans/2026-05-23-portal-event-case-study.md` | PENDING | 浅读 | 1 | 新增案例文档，供后续事件设计和架构检查引用。 |

**验证：**
- 本轮仅新增/更新 Markdown 文档，未运行代码逻辑测试。
## [SYNC] 2026-05-23 21:58 - 途经点改为软锚点并消除事件恢复回头
### A. SYNC 范围声明
**触发任务：** 用户修正导航/事件冲突需求：事件完成后恢复普通导航时不能回到原来的途经点；途经点不再是必须按顺序经过的目标，只作为普通导航和事件导航的 A* 辅助中间锚点。添加顺序仅用于撤销最后一个途经点。
**直接变更文件：** 预计修改 `core/auto_navigator.py`、`core/events/path_mover.py`、`gui/modes/navigation_mode.py`、`gui/modes/navigation/route_overlay.py`，并同步 `CODEBASE.md` / `ITERATION_LOG.md`。
**预计连带影响：** 自动导航目标选择、事件 `MOVE_TO` 路径规划、路线 overlay 当前目标显示、UI 文案和 CODEBASE 中关于 `guide_points` 的语义说明都需要同步；`required_points` 仍保留顺序阶段门语义。

### C. SYNC 结果
**根因确认：**
- (verified) `AutoNavigator._select_segment_target()` 旧逻辑会返回 `("guide", guide_point)`，并用 `guide_index` 按添加顺序推进途经点。
- (verified) 事件完成后普通导航从下一帧恢复时仍使用 `AutoNavigator` 当前 `guide_index`，因此可能回头追事件发生前的旧途经点。
- (verified) `EventPathMover` 原本只对事件目标直接 A*，无法复用路线中的辅助点；用户要求事件导航也可以借助这些点作为中间锚点。

**实际变更：**
- 新增 `core/anchor_path.py`，提供 `plan_path_with_optional_anchors()`：先尝试直接 A*；直接失败时才筛选方向合理的软锚点并搜索锚点组合；仍失败则返回空，让调用方走原 fallback。
- `AutoNavigator._select_segment_target()` 现在只返回当前必经点或出口；`guide_points` 不再成为 `current_target_kind="guide"`。
- `AutoNavigator._align_route_to_current_position()` 只推进已经靠近的必经点，不再根据途经点/路线段修改 `guide_index`。
- `AutoNavigator._plan_segment()` 通过 `plan_path_with_optional_anchors()` 把 `guide_points` 作为软锚点参与直接 A* 失败后的辅助规划。
- `EventPathMover.step()` 新增 `soft_anchors` 参数，事件移动同样可以在直接 A* 失败时借用途经点辅助规划。
- `NavigationModeWidget._execute_event_move_to()` 将当前路线 `guide_points` 传给事件移动器；事件完成后恢复普通导航时不会回头追途经点。
- `route_overlay.py` 将途经点显示为 `A1/A2/...` 辅助点，不再按 `current_guide_index` 显示已完成或当前目标。
- 导航 UI 文案改为“请在地图上点击A*辅助点；顺序仅用于撤销”。

**CODEBASE.md 更新内容：**
- 新增 `core/anchor_path.py` 目录和模块说明。
- 更新 `NavigationModeWidget`、`route_overlay.py`、`core/auto_navigator.py` 的职责/注意事项，明确 `guide_points` 是软锚点，不是顺序目标。
- 更新 `AutoNavigator.update()`、`_align_route_to_current_position()`、`_select_segment_target()` 函数说明，移除旧 `_candidate_index_from_nearest_route_segment()` 描述。
- 更新传送门案例文档，明确事件移动可复用软锚点，但事件完成恢复不能回头追途经点。

**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/auto_navigator.py` | (partial) | (partial) | 4 | 本轮重读目标选择、路线对齐、规划和推进逻辑，将途经点从顺序目标改为软锚点。 |
| `core/events/path_mover.py` | (partial) | (partial) | 4 | 本轮接入 `soft_anchors`，让事件 MOVE_TO 复用途经点辅助规划。 |
| `core/anchor_path.py` | PENDING | 浅读 | 1 | 新增通用软锚点路径规划 helper，直接 A* 失败后才尝试锚点组合。 |
| `gui/modes/navigation_mode.py` | (partial) | (partial) | 11 | 本轮重读事件 move callback 和路线 UI 文案，将路线 guide_points 传入事件移动器。 |
| `gui/modes/navigation/route_overlay.py` | (partial) | (partial) | 2 | 本轮重读途经点 overlay，改为 A* 辅助点显示，不再显示完成/当前状态。 |
| `docs/plans/2026-05-23-portal-event-case-study.md` | 浅读 | 浅读 | 2 | 补充事件移动阶段的软锚点语义。 |

**验证：**
- `python -m py_compile core\anchor_path.py core\auto_navigator.py core\events\path_mover.py gui\modes\navigation_mode.py gui\modes\navigation\route_overlay.py` 已通过。
- 未运行逻辑/单元测试，等待用户在游戏内实测导航恢复和传送门事件移动。

## [SYNC] 2026-05-23 22:11 - 软锚点参与规划而非失败兜底
### A. SYNC 范围声明
**触发任务：** 用户确认“都要借助锚点”：普通导航和事件导航都应把途经点作为路径规划候选中间节点，而不是只有直接 A* 失败时才尝试。
**直接变更文件：** `core/anchor_path.py`、`CODEBASE.md`、`ITERATION_LOG.md`、`docs/plans/2026-05-23-portal-event-case-study.md`。
**预计连带影响：** `core/auto_navigator.py` 和 `core/events/path_mover.py` 已统一调用 `plan_path_with_optional_anchors()`，因此只需要调整该共用规划器即可影响普通导航和事件移动；文档中所有“直接失败才用锚点”的旧表述必须同步修正。

### C. SYNC 结果
**关键发现：**
- (verified) 旧新增的 `plan_path_with_optional_anchors()` 会在 `direct_path` 存在时立即返回，导致 `guide_points` 仍只是失败兜底，没有真正参与规划。
- (verified) 普通导航和事件移动已经共用 `plan_path_with_optional_anchors()`，所以修正共用层即可同时覆盖自动导航和事件 `MOVE_TO`。

**实际变更：**
- `plan_path_with_optional_anchors()` 现在同时计算直接 A* 和锚点图路径，不再因直接 A* 成功提前跳过锚点。
- `_plan_anchor_graph()` 用状态 `(node_index, used_anchor)` 搜索，`require_anchor=True` 时要求到目标前至少经过一个合理锚点；锚点仍不按 UI 添加顺序强制经过。
- 如果锚点路径存在且长度不超过直接路径 `max_anchor_factor` 倍，则返回 `path_kind="anchor_planned"`；锚点不可达或绕远过多时回退直接路径。
- `CODEBASE.md` 和传送门案例文档已修正为“锚点参与规划但不作为顺序目标”。

**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/anchor_path.py` | 浅读 | (partial) | 2 | 本轮重读并修正软锚点策略：直接路径和锚点图路径并行评估，锚点不再只是失败兜底。 |
| `core/auto_navigator.py` | (partial) | (partial) | 5 | 本轮确认普通导航已通过共用规划器接收软锚点，无需重新引入 guide 目标。 |
| `core/events/path_mover.py` | (partial) | (partial) | 5 | 本轮确认事件 MOVE_TO 已通过共用规划器接收软锚点，传送门事件会同步受益。 |
| `docs/plans/2026-05-23-portal-event-case-study.md` | 浅读 | 浅读 | 3 | 修正阶段 2 中“直接 A* 失败才借助锚点”的旧描述。 |

**验证：**
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\anchor_path.py core\auto_navigator.py core\events\path_mover.py gui\modes\navigation_mode.py gui\modes\navigation\route_overlay.py` 已通过。
- 未运行逻辑/单元测试，等待用户在游戏内验证 `path_kind=anchor_planned` 时的实际路线表现。

## [BUGFIX] 2026-05-23 23:35 - 锚点分段 A* 不再直冲最终目标
### A. SYNC 范围声明
**触发任务：** 用户反馈自动导航仍然直线冲目标，完全忽视辅助锚点；正确语义是 A* 应通过中间锚点分段规划，锚点和 A* 不应是独立候选方案。
**直接变更文件：** `core/anchor_path.py`、`core/auto_navigator.py`、`core/events/path_mover.py`、`gui/modes/navigation_mode.py`、`CODEBASE.md`、`ITERATION_LOG.md`、`docs/plans/2026-05-23-portal-event-case-study.md`。
**预计连带影响：** 普通导航和事件 `MOVE_TO` 都会优先使用锚点分段图；锚点链断开时先走到当前可达的最远锚点或朝下一个锚点短探测，到达后重规划，而不是回退为长距离直冲最终目标。

### C. SYNC 结果
**根因确认：**
- (verified) 最近运行日志只有最终鼠标点击和 `map_delta`，没有打印规划层 `path_kind`，所以运行日志能看出一直朝最终目标方向点，但不能定位规划层原因。
- (verified) 离线探针使用 `map_data/Aa/route.json` 和 `map_data/Aa/map_data.npz` 复现：旧锚点图从起点到出口返回 `None`，随后运行时可能回退直接/局部目标方向。
- (verified) 具体断点包括 `(2908,2280) -> (3020,2383)` A* 判定无路，以及 `(3381,2226) -> (3471,2320)` 在 `explored_map` 约束下不可走。
- (verified) 旧 `_candidate_anchors()` 还会按“起点到最终目标的直线投影”过滤锚点，弯路锚点容易被筛掉；这和用户要求的“通过锚点往目标走”冲突。

**实际变更：**
- `plan_path_with_optional_anchors()` 改为优先构建锚点分段 A* 图；只有无可用锚点时才直接 A* 到真实目标。
- `_candidate_anchors()` 不再用起点到终点直线投影过滤，只保留“锚点距离目标有实际进展、离当前位置不过近、去重”的条件。
- `_plan_anchor_graph()` 支持返回 `anchor_planned`、`anchor_partial`、`anchor_probe`：
- `anchor_planned`：锚点链能连到真实目标。
- `anchor_partial`：只能先走到当前可达的最远锚点。
- `anchor_probe`：连第一段锚点 A* 都不可用时，先朝下一个合理锚点做短探测。
- `AutoNavigator` 新增 `current_path_goal/current_anchor_count`，当 `anchor_partial/anchor_probe` 到达当前路径终点时清空路径并重新规划下一段。
- `EventPathMover` 同样识别 `anchor_partial/anchor_probe` 当前段终点，到达后重新规划，避免传送门事件移动再次直冲事件点。
- 导航状态栏新增 `path:<path_kind>/A<count>`，便于实测时确认是否走了 `anchor_partial/anchor_planned`。

**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/anchor_path.py` | (partial) | (partial) | 3 | 本轮用 Aa 路线离线探针确认旧锚点图断点，改为锚点分段优先和 partial/probe 返回。 |
| `core/auto_navigator.py` | (partial) | (partial) | 6 | 本轮新增锚点段临时目标，到达锚点段终点后重规划，不再把最终目标作为唯一到达条件。 |
| `core/events/path_mover.py` | (partial) | (partial) | 6 | 本轮让事件移动也在锚点段终点后重规划，保持和普通导航一致。 |
| `gui/modes/navigation_mode.py` | (partial) | (partial) | 12 | 本轮状态栏增加 path_kind/anchor_count 诊断显示。 |

**验证：**
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\anchor_path.py core\auto_navigator.py core\events\path_mover.py gui\modes\navigation_mode.py gui\modes\navigation\route_overlay.py` 已通过。
- 离线探针：`Aa` 起点 `(2514,2666)` 到出口 `(3892,2032)` 现在返回 `anchor_partial/A3`，路径先到 `(2908,2280)`，不再直接返回最终出口路径。

## [SYNC] 2026-05-23 23:58 - 主目标仲裁与有序锚点走廊
### A. SYNC 范围声明
**触发任务：** 用户明确锚点、必经点、事件必须区分职责：锚点只作为路线塑形点，不能和必经点/事件抢主目标；事件应作为动态必经点参与距离仲裁，不能一识别就强制打断当前路线；事件执行时会中断普通导航。
**直接变更文件：** 预计涉及 `core/anchor_path.py`、`core/auto_navigator.py`、`core/events/path_mover.py`、`gui/modes/navigation_mode.py`、`CODEBASE.md`、`ITERATION_LOG.md`、必要时同步 `docs/plans/2026-05-23-portal-event-case-study.md`。
**预计连带影响：** 普通导航当前目标选择、事件执行入口、事件 MOVE_TO、路线 overlay/status 诊断、传送门案例文档中的阶段 2 导航语义。

### C. SYNC 结果
**根因确认：**
- (verified) `core/anchor_path.py` 上一版仍是“候选锚点图 + 最短路/Dijkstra”模型，会按距离和可达性跳过用户手工放置的中间锚点；这和“锚点是定制路径骨架”冲突。
- (verified) `NavigationModeWidget.navigation_loop()` 之前只要事件 handler 返回可接管 action，就直接阻断普通自动导航；事件没有作为“动态必经点”参与和当前普通主目标的距离仲裁。
- (verified) 事件检测/记忆本身可以继续运行，不应因为事件当前不执行就丢失 overlay 或任务表状态。

**实际变更：**
- `core/anchor_path.py` 重写为有序锚点走廊：`guide_points` 保留 UI 添加顺序，当前位置之前的锚点视为已路过，当前主目标投影之后的锚点会被过滤；有前方锚点时只规划到下一个锚点，返回 `anchor_step`。
- `anchor_probe` 只用于下一个锚点 A* 暂不可达时的短探测；没有前方锚点时才直接 A* 到当前主目标。
- `AutoNavigator` 新增 `segment_target_for_position()`，给事件仲裁预览当前普通目标，不推进真实 `required_index`。
- `AutoNavigator` 和 `EventPathMover` 都把 `anchor_step/anchor_probe` 当作临时段，抵达段终点后清空路径并重新规划。
- `EventCoordinator.update()` 增加 `allowed_task_ids`，事件检测、定位、memory、overlay 继续运行，但只有允许集合内的任务会推进 handler；active/running 任务继续执行到终态。
- `NavigationModeWidget._allowed_event_task_ids()` 实现主目标仲裁：手动测试不限制；普通自动导航时，事件任务距离不大于当前普通主目标距离才允许执行；已有 active 事件始终允许继续。
- `CODEBASE.md` 与传送门案例文档同步为“四阶段事件 + 动态必经点仲裁 + 有序锚点走廊”的当前语义。

**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/anchor_path.py` | (partial) | (partial) | 4 | 本轮废弃锚点图最短路模型，改为用户顺序锚点走廊和 `anchor_step` 分段推进。 |
| `core/auto_navigator.py` | (partial) | (partial) | 7 | 本轮新增无副作用主目标预览，并让 `anchor_step` 到达后重规划。 |
| `core/events/coordinator.py` | 浅读 | (partial) | 2 | 本轮新增 `allowed_task_ids` 运行过滤，检测/显示与 handler 执行解耦。 |
| `core/events/path_mover.py` | (partial) | (partial) | 7 | 本轮同步 `anchor_step` 作为事件移动临时段终点，避免停在锚点后不重规划。 |
| `gui/modes/navigation_mode.py` | (partial) | (partial) | 13 | 本轮新增事件/普通目标距离仲裁，事件作为动态必经点，不再一识别就抢控制。 |
| `docs/plans/2026-05-23-portal-event-case-study.md` | 浅读 | 浅读 | 4 | 同步阶段 2：事件接管前先参与主目标仲裁，锚点按有序走廊推进。 |
| `CODEBASE.md` | 浅读 | 浅读 | 6 | 同步新增函数、事件 flow、锚点语义和结构说明。 |

**验证：**
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\anchor_path.py core\auto_navigator.py core\events\coordinator.py core\events\path_mover.py gui\modes\navigation_mode.py` 已通过。
- 未运行逻辑/单元测试，等待游戏内验证普通导航、传送门事件触发顺序和锚点推进是否符合预期。

## [SYNC] 2026-05-24 00:40 - 导航卡住：路线进度与锚点探测修正
### A. SYNC 范围声明
**触发任务：** 用户反馈新锚点逻辑运行后卡住且日志逻辑混乱；已读运行日志确认事件未参与，问题集中在普通导航的必经点完成判断和不可达锚点探测。
**直接变更文件：** `core/anchor_path.py`、`core/auto_navigator.py`、`CODEBASE.md`、`ITERATION_LOG.md`，必要时涉及 `core/events/path_mover.py`。
**预计连带影响：** 普通导航不再回头追已经按锚点进度越过的必经点；`anchor_probe` 不再长距离点击不可达锚点；运行日志应能看到当前主目标、路径类型和锚点段。

### C. SYNC 结果
**根因确认：**
- (verified) 最新 `event_runtime.log` 只有事件系统初始化和 detector ready，没有 detection/task/action/arbitration，说明这次卡住不是传送门事件接管导致。
- (verified) `runtime.log` 中点击方向先右下、再右上、再左上，符合普通导航目标/锚点段切换，而不是输入点击失败。
- (verified) 离线探针确认：当位置已在后段锚点附近但早期必经点未按距离命中时，旧逻辑仍可能回头追早期必经点。
- (verified) 离线探针确认：`A10 -> A11`、`A15 -> A16` 在墙图/探索图约束下会触发 `anchor_probe`；旧 probe 直接点击不可达锚点，容易硬冲墙。

**实际变更：**
- `core/anchor_path.py` 新增 `anchor_route_progress()`，为自动导航提供按锚点折线的路线进度。
- `anchor_probe` 改为朝不可达锚点做约 84 像素短探测，不再直接点击不可达锚点坐标。
- `AutoNavigator` 新增单调 `route_progress`，只允许路线进度前进不后退。
- 必经点完成判断从“只看距离”升级为“距离命中或路线进度已越过”，防止人物已到后段后回头追旧必经点。
- `segment_target_for_position()` 也使用进度预览，但不推进真实 `required_index`，保证事件仲裁无副作用。
- 自动导航每次规划段写 `auto path planned` 日志，包含目标类型、目标坐标、路径类型、路径终点、锚点数、必经点 index 和路线进度。

**离线验证：**
- 从 `(3109,2353)`、`(2908,2280)`、`(3381,2226)` 预览路线，3 个必经点都会按进度视为已越过，当前目标变为出口。
- `A10 -> A11` probe 从直接点击 `(3020,2383)` 改为短探测点 `(2970,2337)`。
- `A15 -> A16` probe 从直接点击 `(3471,2320)` 改为短探测点 `(3439,2287)`。

**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/anchor_path.py` | (partial) | (partial) | 5 | 本轮新增锚点路线进度 helper，并把不可达锚点 probe 改为短探测。 |
| `core/auto_navigator.py` | (partial) | (partial) | 8 | 本轮用单调 route_progress 防止回头追旧必经点，并补自动导航规划日志。 |
| `CODEBASE.md` | 浅读 | 浅读 | 7 | 同步路线进度、短 probe 和 auto path planned 日志语义。 |

**验证：**
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\anchor_path.py core\auto_navigator.py core\events\path_mover.py gui\modes\navigation_mode.py` 已通过。
- 未运行逻辑/单元测试，等待用户游戏内验证；重点看 `logs/event_runtime.log` 中 `auto path planned` 是否仍出现旧必经点回头。
## [DESIGN] 2026-05-24 01:04 - 导航冲突方案 B/C 设计
### A. 本轮目标（阅读前声明）
**目标文件：**
- `core/auto_navigator.py`（原因：普通导航状态机、必经点推进、锚点段到达逻辑是当前冲突核心）
- `core/anchor_path.py`（原因：guide_points 走廊、锚点选择、路线进度投影定义了 B/C 两套方案的共同基础）
- `core/events/path_mover.py`（原因：事件移动复用锚点规划，但状态独立，需要确认复用边界）
- `core/events/coordinator.py`、`core/events/runner.py`、`core/events/scheduler.py`、`core/events/types/portal/handler.py`（原因：事件作为动态必经点/任务队列的现有实现依据）
- `gui/modes/navigation_mode.py`、`gui/modes/navigation/event_adapter.py`（原因：事件和普通导航的仲裁、执行入口、UI 集成在这里）
- `map_data/Aa/route.json`（原因：用实际 route 数据解释 B/C 方案如何处理 required_points、guide_points、exit）

**本轮想弄清楚：** 在不立即改代码的前提下，基于现有源码分别设计方案 B「统一路线进度模型」和方案 C「统一任务队列状态机」，明确改动范围、状态模型、数据流、风险和迁移顺序，写入本地文档供用户选择。
### C. 本轮发现
**关键发现：**
- (verified) `AutoNavigator` 当前同时承担普通导航定位状态、主目标选择、路径跟随和点击节流；`_select_segment_target()` 只会在当前 `required_points[required_index]` 与出口之间选择，不理解事件目标。
- (verified) `EventCoordinator` 当前负责检测、定位、memory、scheduler 和 runner；事件执行与普通导航之间的最终仲裁发生在 `NavigationModeWidget._allowed_event_task_ids()` 和 `event_blocks_auto_navigation`，不是在核心层统一完成。
- (verified) `EventPathMover` 和 `AutoNavigator` 都调用 `plan_path_with_optional_anchors()`，但两者各自维护 path/path_goal/click cooldown，因此共享规划算法但不共享“已消费锚点”的状态。
- (verified) `anchor_path._ordered_corridor_anchors()` 内部跳过锚点的半径约 8 像素，而 `AutoNavigator._follow_segment()` 用 `arrival_radius=26` 判断锚点段到达；这是 `(2577,2474)` 反复规划的直接设计缺口。

**产出文档：**
- `docs/plans/2026-05-24-navigation-route-progress-option-b-design.md`：方案 B，保留现有执行器，新增统一路线进度/锚点消费模型。
- `docs/plans/2026-05-24-navigation-task-queue-option-c-design.md`：方案 C，把 required、exit、event 全部抽象成统一 NavigationTask，由统一 controller 调度。

**更新了 CODEBASE.md：** §2 目录图新增两个设计文档；§17 新增 Navigation Conflict Design Options，记录 B/C 的源码依据、主要改动范围和推荐选择。

**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/auto_navigator.py` | (partial) | (partial) | 9 | 本轮确认其仍同时负责主目标选择与移动执行，是 B/C 方案拆分边界的核心依据。 |
| `core/anchor_path.py` | (partial) | (partial) | 6 | 本轮确认锚点跳过半径与导航到达半径不一致，且函数没有锚点消费状态。 |
| `core/events/path_mover.py` | (partial) | (partial) | 8 | 本轮确认事件 MOVE_TO 与普通导航复用锚点规划但运行时路径状态分离。 |
| `core/events/coordinator.py` | (partial) | (partial) | 3 | 本轮确认事件检测/记忆/执行入口目前仍由 allowed_task_ids 过滤运行，而非统一任务调度。 |
| `core/events/runner.py` | 浅读 | (partial) | 2 | 本轮确认 handler 生命周期和 COMPLETE/FAIL 更新 memory，可在方案 C 中由统一 controller 调用。 |
| `core/events/scheduler.py` | 浅读 | (partial) | 2 | 本轮确认事件内部 scheduler 只按 running/priority/distance 选事件，不理解普通路线。 |
| `core/events/memory.py` | (partial) | (partial) | 3 | 本轮确认事件 task 生命周期和传送门成对完成逻辑可作为 NavigationTask 的动态来源。 |
| `core/events/types/portal/handler.py` | (partial) | (partial) | 5 | 本轮确认传送门 handler 仍包含靠近、点击门点、按 D、等待完成四段，方案 C 后期可拆出靠近阶段。 |
| `gui/modes/navigation_mode.py` | (partial) | (partial) | 14 | 本轮确认 UI 层承担事件/普通导航仲裁、事件 MOVE_TO 执行和 overlay 刷新，是方案 C 最大迁移点。 |
| `gui/modes/navigation/event_adapter.py` | 浅读 | 浅读 | 2 | 本轮确认事件接管规则只按 EventAction 类型判断，未承载路线语义。 |
| `map_data/Aa/route.json` | 浅读 | 浅读 | 3 | 本轮使用 Aa 实际 required/guide/exit 数据说明方案 B 如何处理 `(2577,2474)` 卡点。 |
| `docs/plans/2026-05-24-navigation-route-progress-option-b-design.md` | PENDING | 浅读 | 1 | 本轮新增，记录保守统一路线进度方案和迁移步骤。 |
| `docs/plans/2026-05-24-navigation-task-queue-option-c-design.md` | PENDING | 浅读 | 1 | 本轮新增，记录统一任务队列状态机方案和迁移步骤。 |
## [PLAN] 2026-05-24 01:16 - 方案 C 统一任务队列实施计划
### A. 本轮目标（阅读前声明）
**目标文件：**
- `docs/plans/2026-05-24-navigation-task-queue-option-c-design.md`（原因：用户已选择方案 C，需要转成详细实施计划）
- `core/auto_navigator.py`（原因：当前普通导航状态机将被 facade/移动执行器化）
- `core/events/coordinator.py`、`core/events/runner.py`、`core/events/memory.py`（原因：事件检测/记忆保留，执行调度要接入统一任务控制器）
- `core/events/path_mover.py`（原因：事件移动逻辑将并入统一 MovementExecutor 或作为兼容壳）
- `gui/modes/navigation_mode.py`、`gui/modes/navigation/event_adapter.py`（原因：当前 UI 层仲裁需要被 NavigationTaskController 替代）

**本轮想弄清楚：** 将已选择的方案 C 拆成可执行、可分阶段验证的本地实施计划，明确每阶段文件范围、验证方式、回滚边界和用户手动测试点；本轮不修改运行逻辑。
### C. 本轮发现
**关键发现：**
- (verified) 方案 C 不能直接从 UI 主循环删除旧仲裁，否则会同时扰动普通导航、传送门事件和手动测试按钮；计划必须先做兼容层和影子模式。
- (verified) `EventPathMover` 是方案 C 最安全的第一个迁移点，因为它只服务事件 MOVE_TO，且可在不改 `_execute_event_move_to()` 外部调用的情况下委托新 `MovementExecutor`。
- (verified) `EventCoordinator.update()` 当前把 observe 和 run handler 混在一起；方案 C 实施前必须拆出 `observe()` 与 `run_task()`，并保留 `update()` 兼容旧调用。
- (verified) `NavigationModeWidget` 当前有两处真实鼠标移动执行入口：事件 `_execute_event_move_to()` 和普通 `auto_action` 消费；方案 C 必须最终统一成 `NavigationIntent` 消费。

**产出文档：**
- `docs/plans/2026-05-24-navigation-task-queue-option-c-implementation-plan.md`：方案 C 详细实施计划，包含阶段 0 到阶段 12、每阶段文件范围、验证命令、手动验收和回滚策略。

**更新了 CODEBASE.md：** §2 新增实施计划文档；§17 记录用户已选择方案 C，并说明 active implementation plan 和兼容层优先的执行策略。

**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `docs/plans/2026-05-24-navigation-task-queue-option-c-design.md` | 浅读 | 浅读 | 2 | 本轮将设计转为分阶段实施计划，明确先兼容后替换。 |
| `docs/plans/2026-05-24-navigation-task-queue-option-c-implementation-plan.md` | PENDING | 浅读 | 1 | 本轮新增，作为后续方案 C 开发的 active plan。 |
| `core/auto_navigator.py` | (partial) | (partial) | 10 | 本轮确认第一批不直接重写，先通过 facade/影子模式降低风险。 |
| `core/events/path_mover.py` | (partial) | (partial) | 9 | 本轮确认可作为 MovementExecutor 的首个兼容委托点。 |
| `core/events/coordinator.py` | (partial) | (partial) | 4 | 本轮确认必须拆 observe/run_task，保留 update 兼容。 |
| `gui/modes/navigation_mode.py` | (partial) | (partial) | 15 | 本轮确认 UI 接入需先 shadow mode，再切换 NavigationIntent，最后清理旧仲裁。 |

## [SYNC] 2026-05-24 09:05 — 方案 C 统一导航任务控制器收尾同步

### A. SYNC 范围声明
**触发任务：** 用户要求继续完成方案 C，并明确不保留旧兼容负担；本轮收尾文档同步、过期引用清理和轻量编译验证。

**直接变更文件：**
- `CODEBASE.md`（同步统一导航任务控制器、删除旧模块引用）
- `ITERATION_LOG.md`（记录 SYNC 范围和结果）

**预计连带影响：**
- `gui/modes/navigation_mode.py` 的统一主循环描述需要替换旧 `AutoNavigator`/事件独立执行描述。
- `core/events/coordinator.py` 的事件检测/执行拆分需要更新。
- `core/navigation_tasks/*` 的新任务模型、调度器和移动执行器需要加入目录、模块和 Flow 描述。
- 删除的 `core/auto_navigator.py`、`core/events/path_mover.py`、`core/events/action_executor.py`、`tests/test_auto_navigator.py` 不应再作为当前运行链路出现。

### C. SYNC 结果
**连带重读文件：**
- `core/events/coordinator.py`（确认旧 `update(... allowed_task_ids ...)` 已无人调用，并删除兼容入口）
- `gui/modes/navigation_mode.py`（确认 `_navigation_loop_unified()`、`_execute_navigation_intent()` 是当前唯一执行链路）
- `core/navigation_tasks/controller.py`、`scheduler.py`、`movement_executor.py`、`route_context.py`、`task_builder.py`、`models.py`（确认方案 C 当前调度、锚点、移动和 intent 协议）
- `core/anchor_path.py`（确认 guide_points 只作为有序软锚点走廊）

**CODEBASE.md 更新内容：** §4 更新事件系统和统一导航任务层说明；§5 修正 `build_event_tick()` 由 `observe()` 写入任务快照；§6 更新自动导航移动点击和事件管理 UI 数据流；§10/§11/§13/§15/§16/§17 清理旧普通导航器、旧事件移动器、旧事件动作执行器和 UI 旧仲裁描述。

**源码清理：** 删除 `EventCoordinator.update(... allowed_task_ids ...)` 和 `_runnable_tasks()` 旧兼容入口，当前事件执行只允许通过 `observe()` + `run_task()` 两段式协议进入统一 `NavigationTaskController`。

**验证命令：**
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile main.py gui\modes\navigation_mode.py gui\modes\navigation\route_overlay.py core\events\coordinator.py core\anchor_path.py core\navigation_tasks\__init__.py core\navigation_tasks\models.py core\navigation_tasks\route_context.py core\navigation_tasks\movement_executor.py core\navigation_tasks\task_builder.py core\navigation_tasks\scheduler.py core\navigation_tasks\controller.py core\navigation_tasks\debug.py utils\route_context_probe.py utils\navigation_task_probe.py`
- `D:\ACloud\.venv\Scripts\python.exe utils\route_context_probe.py --map Aa`
- `D:\ACloud\.venv\Scripts\python.exe utils\navigation_task_probe.py --map Aa`

**验证结果：** 编译通过；路线探针输出 required[0..2] 和 exit 的路线进度；任务探针输出 `required:0`、`required:1`、`required:2`、`exit:main`。

**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/events/coordinator.py` | (partial) | (partial) | 5 | 删除旧兼容 update 入口，事件系统仅保留 observe/run_task 两段式协议。 |
| `gui/modes/navigation_mode.py` | (partial) | (partial) | 16 | 确认统一循环负责定位、事件观察、任务控制器更新和 NavigationIntent 消费。 |
| `core/navigation_tasks/controller.py` | PENDING | 浅读 | 1 | 确认 selected task 切换会重置 MovementExecutor，event 任务通过 run_task 推进 handler。 |
| `core/navigation_tasks/scheduler.py` | PENDING | 浅读 | 1 | 确认 active lock 只保留 event，静态 required/exit 每帧参与重新仲裁。 |
| `core/navigation_tasks/movement_executor.py` | PENDING | 浅读 | 1 | 确认 required/exit/event MOVE_TO 共用 A*、guide-anchor 和点击节流。 |
| `core/navigation_tasks/route_context.py` | PENDING | 浅读 | 1 | 确认 guide_points 投影、路线进度和前方锚点过滤逻辑。 |
| `core/navigation_tasks/task_builder.py` | PENDING | 浅读 | 1 | 确认 route required/exit 和 EventMemory runnable tasks 被合并为 NavigationTask。 |
| `core/anchor_path.py` | PENDING | 浅读 | 1 | 确认锚点只作为有序软走廊，不作为独立完成目标。 |

**新增 Finding：** 当前源码已经完成方案 C 的“无旧兼容负担”边界；历史设计文档中仍保留旧方案描述，但权威当前状态文档 `CODEBASE.md` 和 Python 源码不再引用旧执行链路。


## [SYNC] 2026-05-24 09:31 — 导航卡住诊断日志增强

### A. SYNC 范围声明
**触发任务：** 用户反馈仍有必经点和辅助锚点冲突导致逻辑卡住，需要先观察日志确认问题。
**直接变更文件：** core/navigation_tasks/controller.py, core/navigation_tasks/movement_executor.py, core/anchor_path.py, ITERATION_LOG.md。
**预计连带影响：** 只增加诊断字段，不改变导航决策。

### C. SYNC 结果
**CODEBASE.md 更新内容：** 本次仅增加运行诊断日志，未改变架构契约，暂不更新 CODEBASE。
**诊断新增：** 
av required completed 现在记录 distance/player_progress/target_progress/progress_delta；
av task transition 记录 player/player_progress/target_progress/completed_required；
av movement planned 记录 next_anchor/anchor_count/direct_distance。
**验证命令：** D:\ACloud\.venv\Scripts\python.exe -m py_compile core\navigation_tasks\controller.py core\navigation_tasks\movement_executor.py core\anchor_path.py。
**验证结果：** 编译通过。


## [SYNC] 2026-05-24 09:50 — 必经点顺序和事件插队规则修正

### A. SYNC 范围声明
**触发任务：** 日志显示 required:0/1 被 by_progress 提前完成，且用户明确必经点必须按顺序走，事件只能作为动态必经点穿插在已满足顺序后。
**直接变更文件：** core/navigation_tasks/controller.py, core/navigation_tasks/scheduler.py, ITERATION_LOG.md。
**预计连带影响：** 必经点完成条件和事件候选过滤。

### C. SYNC 结果
**代码变化：** _update_required_progress() 只检查当前最小未完成 required，并且只按距离完成，不再按 route progress 自动完成；NavigationTaskScheduler._eligible_events() 在当前静态目标是 required 时，只允许 route_progress 不超过该 required 附近的事件插队。
**验证命令：** D:\ACloud\.venv\Scripts\python.exe -m py_compile core\navigation_tasks\controller.py core\navigation_tasks\scheduler.py; D:\ACloud\.venv\Scripts\python.exe utils\navigation_task_probe.py --map Aa; D:\ACloud\.venv\Scripts\python.exe utils\route_context_probe.py --map Aa。
**验证结果：** 编译通过；任务探针顺序仍为 required:0, required:1, required:2, exit:main。
**剩余观察点：** 09:44 日志中 
ext_anchor=(3020,2383) 进入 nchor_probe，说明该辅助锚点 A* 不可达或局部墙图误封，下一轮需要根据新日志判断是否引入不可达锚点跳过/降权机制。

## [SYNC] 2026-05-24 11:30 — 导航专用障碍层与高分辨率绘图参数

### A. SYNC 范围声明
**触发任务：** 用户要求从绘图侧改善墙体/地图清晰度，并为窄通道、玩家定位点压墙等 A* 失败场景提供保险方案；核心原则是原始 `wall_layer` 继续用于定位和事件配准，A* 使用派生后的宽容障碍层。

**直接变更文件：**
- `core/navigation_obstacles.py`
- `core/navigation_core.py`
- `core/pathfinder.py`
- `core/stitcher_core.py`
- `gui/navigation_params.py`
- `gui/dialogs/nav_params_dialog.py`
- `gui/modes/navigation_mode.py`
- `gui/modes/mapping_widget.py`
- `gui/modes/mapping/params_adapter.py`
- `core/recognizer_optimized.py`
- `CODEBASE.md`
- `ITERATION_LOG.md`

**预计连带影响：**
- 自动导航和事件 `MOVE_TO` 仍共用 `NavigationTaskController` / `MovementExecutor`，但传入的 `wall_map` 从原始 `wall_layer` 改为 `nav_core.nav_wall_layer`。
- 定位、事件图标投影和地图显示继续使用原始 `wall_layer`，避免墙体侵蚀影响匹配准确率。
- 绘图页新增/恢复的高分辨率参数会影响后续新地图或重置后的地图包坐标体系，因此 `draw_scale` 必须同时保存进 `map_data.npz` 和地图 `config.json`。

### C. SYNC 结果
**代码变化：**
- 新增 `derive_navigation_wall_layer()`，用阈值化 + 可配置 3x3 十字核腐蚀从原始墙图派生 A* 专用墙图。
- `NavigationCore` 加载地图包时保留原始 `wall_layer`，并维护 `nav_wall_layer`；`rebuild_navigation_wall_layer()` 支持参数面板即时重建导航障碍层。
- `NavigationModeWidget._navigation_loop_unified()` 调用 `NavigationTaskController.update(... wall_map=self.nav_core.nav_wall_layer ...)`，普通路线和事件移动都使用同一宽容障碍层。
- `PathFinder` 默认 `wall_shrink_iterations=0`，避免派生墙图和 pathfinder 内部重复侵蚀；新增 `start_clear_radius` 与 `walkable_snap_radius` 用于起点局部清空和起终点吸附。
- `NavConfig` 与导航参数 UI 新增 `nav_wall_erode_iterations`、`path_start_clear_radius`、`path_walkable_snap_radius`，并随地图配置保存。
- `MapStitcher.save_map_package()` 将 `draw_scale` 写入 `map_data.npz`；绘图页参数保存现在叠加 UI 中的 `draw_scale/canvas_size/player_clear_radius/wall_close_kernel_size`。

**CODEBASE.md 更新内容：**
- §2/§4 新增 `core/navigation_obstacles.py`，并修正 `NavigationCore` / `PathFinder` 的职责边界。
- §5 增加 `derive_navigation_wall_layer()`、`MappingWidget._build_mapping_config_with_ui_overrides()` 和 `PathFinder._clear_start_area()` 的函数说明。
- §6 修正自动导航 flow：A* 使用 `nav_core.nav_wall_layer`；绘图保存 flow 记录 `draw_scale` 进入地图包。
- §8 补充 `NavConfig` 的 A* 障碍层与容错参数字段。

**验证命令：**
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\navigation_obstacles.py core\navigation_core.py core\pathfinder.py gui\navigation_params.py gui\dialogs\nav_params_dialog.py gui\modes\navigation_mode.py gui\modes\mapping_widget.py gui\modes\mapping\params_adapter.py core\stitcher_core.py core\recognizer_optimized.py core\navigation_tasks\movement_executor.py`

**验证结果：** 编译通过；只做编译/启动级检查，未执行逻辑单元测试。

**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/navigation_obstacles.py` | PENDING | 浅读 | 1 | 新增 A* 专用障碍层派生函数，确认不会修改原始 `wall_layer`。 |
| `core/navigation_core.py` | (partial) | (partial) | 17 | 确认 `wall_layer` 用于定位/显示，`nav_wall_layer` 用于寻路。 |
| `core/pathfinder.py` | (partial) | (partial) | 2 | 确认默认不再内部侵蚀墙体，并新增起点清空/起终点吸附参数。 |
| `gui/modes/navigation_mode.py` | (partial) | (partial) | 18 | 确认统一导航循环向 task controller 传入 `nav_core.nav_wall_layer`。 |
| `gui/navigation_params.py` | 已有记录 | (partial) | 2 | 确认新增 A* 障碍层和容错参数纳入 config 序列化。 |
| `gui/dialogs/nav_params_dialog.py` | 已有记录 | (partial) | 2 | 确认新增参数控件进入 widget map，可从 UI 调整并保存。 |
| `gui/modes/mapping_widget.py` | (partial) | (partial) | 2 | 确认绘图几何/清晰度控件参与保存，并在空地图时可重建画布。 |
| `core/stitcher_core.py` | (partial) | (partial) | 2 | 确认地图包保存 `draw_scale`，供导航加载同一坐标缩放。 |

## [SYNC] 2026-05-24 11:45 — RecognizerParams 严格字段修正

### A. SYNC 范围声明
**触发任务：** 导航加载地图时报 `RecognizerParams.__init__() got an unexpected keyword argument 'player_clear_radius'`；用户明确不需要兼容旧地图，配置字段应与当前代码严格一致。
**直接变更文件：** `gui/navigation_params.py`, `CODEBASE.md`, `ITERATION_LOG.md`。
**预计连带影响：** 当前绘图页写入的 `player_clear_radius` 可被导航配置模型识别；未知 recognizer 字段仍会抛错，不做静默过滤。

### C. SYNC 结果
**代码变化：** `RecognizerParams` 新增 `player_clear_radius: int = 22`；保留 `NavPreferences(**nav_prefs_data)` 和 `RecognizerParams(**rec_params_data)` 严格构造。
**CODEBASE.md 更新内容：** 记录 `gui/navigation_params.py` 严格字段契约和 `player_clear_radius` 当前字段。
**验证命令：** `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\navigation_params.py gui\modes\navigation_mode.py gui\modes\mapping_widget.py`; `D:\ACloud\.venv\Scripts\python.exe -c "import json; from gui.navigation_params import NavConfig; data=json.load(open('config.json', encoding='utf-8')); cfg=NavConfig.from_dict(data); print(cfg.recognizer_params.player_clear_radius)"`
**验证结果：** 编译通过；当前 `config.json` 加载输出 `20`。

## [SYNC] 2026-05-24 12:20 — 锚点推进配置与导航参数分页

### A. SYNC 范围声明
**触发任务：** 用户确认调整方案：解决锚点规划成功但点击停住的问题，把锚点半径做成配置，把导航参数前端按功能分页，并新增“保存为默认配置”。
**直接变更文件：** `core/navigation_tasks/movement_executor.py`, `gui/navigation_params.py`, `gui/dialogs/nav_params_dialog.py`, `gui/modes/navigation/map_runtime.py`, `gui/modes/navigation_mode.py`, `CODEBASE.md`, `ITERATION_LOG.md`。
**预计连带影响：** 自动导航、事件 `MOVE_TO` 和手动传送门测试继续共用 `MovementExecutor`；新增配置字段写入地图 config，并可合并保存到项目根默认 config。

### C. SYNC 结果
**代码变化：**
- `MovementExecutor` 新增 `anchor_arrival_radius` 和 `force_replan`；锚点/探测/兜底路径目标未到达时，冷却结束后允许重复点击，不再被 `auto_min_click_target_delta` 卡住。
- 卡住恢复目标从最终任务目标改为当前 `path_goal`，避免“走锚点”和“恢复朝终点”互相打架；恢复次数耗尽后下一帧显式重规划。
- `NavConfig` 新增锚点半径、卡住判定间隔、最小有效进度、恢复尝试次数、路径偏离阈值字段，并接入 `_configure_navigation_task_controller()`。
- `NavParametersDialog` 改为 5 个功能页：定位识别、识别算法、移动点击、路径/A*、地图/调试；关键参数行增加可见说明和 tooltip。
- 新增“保存为默认配置”按钮，写入项目根 `config.json` 时保留绘图模式的 `stitcher_params` 等非导航字段；地图配置缺失时会读取根默认配置作为 fallback。

**CODEBASE.md 更新内容：** 更新 §2/§4 `nav_params_dialog.py` 与 `map_runtime.py` 职责，§6 导航参数保存加载流，§8 `NavConfig` 字段，§10 `MovementExecutor` 当前行为，§16 dialog 热点状态。

**验证命令：**
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\navigation_tasks\movement_executor.py gui\navigation_params.py gui\dialogs\nav_params_dialog.py gui\modes\navigation\map_runtime.py gui\modes\navigation_mode.py`
- `D:\ACloud\.venv\Scripts\python.exe -c "import sys; from PySide6.QtWidgets import QApplication; from gui.dialogs.nav_params_dialog import NavParametersDialog; from gui.navigation_params import NavConfig; app=QApplication.instance() or QApplication(sys.argv); d=NavParametersDialog(); d.set_config_to_ui(NavConfig(), (0,0)); print(d.nav_tabs.count(), d.nav_anchor_arrival_radius_spin.value(), d.nav_movement_progress_timeout_spin.value())"`
- `D:\ACloud\.venv\Scripts\python.exe -c "import json; from gui.navigation_params import NavConfig; data=json.load(open('config.json', encoding='utf-8')); cfg=NavConfig.from_dict(data); print(cfg.anchor_arrival_radius, cfg.movement_progress_timeout_ms, cfg.movement_min_progress_delta, cfg.movement_max_recover_attempts, cfg.movement_path_deviation_threshold)"`

**验证结果：** 编译通过；参数弹窗可实例化并显示 5 个分页；当前根配置加载新字段默认值输出 `26 1200 12.0 2 96.0`。

**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/navigation_tasks/movement_executor.py` | 浅读 | (partial) | 2 | 确认锚点路径点击抑制、卡住恢复目标和强制重规划行为已调整。 |
| `gui/navigation_params.py` | (partial) | (partial) | 3 | 确认新增移动执行器调参字段进入地图 config 序列化契约。 |
| `gui/dialogs/nav_params_dialog.py` | (partial) | (partial) | 3 | 确认导航参数 UI 已分页，新增锚点/卡住参数控件和默认保存信号。 |
| `gui/modes/navigation/map_runtime.py` | 深度完整 | (partial) | 2 | 确认新增根默认配置保存/缺省读取 helper，保留地图配置优先级。 |
| `gui/modes/navigation_mode.py` | (partial) | (partial) | 19 | 确认新增默认保存槽和 MovementExecutor 新参数下发。 |
## [SYNC] 2026-05-24 13:50 - 坐标失准独立诊断日志

### A. SYNC 范围声明
**触发任务：** 用户反馈现有日志没有打印坐标匹配不准确的关键证据，需要新增独立日志，并先构思识别坐标失准后重新匹配定位的方案。
**直接变更文件：** `core/navigation_tasks/coordinate_diagnostics.py`, `core/navigation_tasks/controller.py`, `gui/modes/navigation_mode.py`, `docs/plans/2026-05-24-coordinate-drift-diagnostics.md`, `CODEBASE.md`, `ITERATION_LOG.md`。
**预计连带影响：** 导航行为不变；`NavigationTaskController` 额外接收 `FrameRegistration` 并把 raw/trusted/control/target/route projection 写到独立日志，后续用这些证据决定是否启用强制全局重匹配。

### C. SYNC 结果
**代码变化：**
- 新增 `CoordinateDiagnostics`，文件只写 `logs/coordinate_diagnostics.log`，不打印到控制台，避免再次污染 `runtime.log`。
- `NavigationTaskController.update()` 接收 `frame_registration`，每帧在定位有效或无效时记录诊断候选，但不修改 `observe_localization()` 的接受规则。
- `_navigation_loop_unified()` 将 `nav_core.last_frame_registration` 传给任务控制器，使日志能看到 `reg_source/reg_conf/reg_origin/reg_local/reg_meta`。
- 新增方案文档，明确下一阶段重匹配应由连续 `route projection deviation`、`raw control gap`、`near target not completed` 等证据触发，而不是引入固定偏移参数。

**验证命令：** `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\navigation_tasks\coordinate_diagnostics.py core\navigation_tasks\controller.py gui\modes\navigation_mode.py`
**验证结果：** 编译通过；本轮未运行逻辑测试，等待真实游戏导航日志反馈。
**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/navigation_tasks/coordinate_diagnostics.py` | PENDING | 浅读 | 1 | 新增坐标失准诊断模块，记录 raw/control/target/route deviation/registration evidence。 |
| `core/navigation_tasks/controller.py` | (partial) | (partial) | 追加 | 确认统一任务控制器接入诊断采样但不改变任务选择和移动输出。 |
| `gui/modes/navigation_mode.py` | (partial) | (partial) | 追加 | 确认导航循环把当前帧配准契约传入任务控制器。 |
| `docs/plans/2026-05-24-coordinate-drift-diagnostics.md` | PENDING | 浅读 | 1 | 新增坐标漂移检测和未来强制全局重匹配方案记录。 |
## [SYNC] 2026-05-24 14:05 - 近锚点精确点击

### A. SYNC 范围声明
**触发任务：** 用户反馈快到下一个锚点时仍频繁普通点击，角色会绕锚点转圈；期望近锚点时点击锚点本身，到达后再规划下一个锚点。
**直接变更文件：** `core/navigation_tasks/models.py`, `core/navigation_tasks/movement_executor.py`, `core/navigation_tasks/controller.py`, `CODEBASE.md`, `ITERATION_LOG.md`。
**预计连带影响：** 普通 required/exit/event MOVE_TO 仍共用 `MovementExecutor`；只在 `anchor_step/anchor_probe` 当前 path_goal 的近距离阶段改变点击方式，避免 `movement_min_click_radius` 放大近锚点点击。

### C. SYNC 结果
**代码变化：**
- `MovementStep` 新增 `force_click_target`，用于把移动执行器的“精确点击目标”意图传到 UI 输入层。
- `MovementExecutor` 在当前路径为 `anchor_step/anchor_probe` 且人物接近 `path_goal` 但尚未进入 `anchor_arrival_radius` 时，将 `subgoal` 固定为 `path_goal`，并标记 `force_click_target=True`。
- 近锚点阶段点击冷却提升到至少 650ms，并在 2.2s 内抑制 stuck recovery，避免刚靠近锚点就左右探针造成绕圈；若仍未到达，恢复机制会重新接管。
- `NavigationTaskController` 把 `step.force_click_target` 放入 `NavigationIntent.metadata`，沿用现有 `_execute_navigation_intent()` 的 `click_map_target_once()` 分支，因此不会走普通移动最小半径。

**验证命令：** `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\navigation_tasks\coordinate_diagnostics.py core\navigation_tasks\models.py core\navigation_tasks\movement_executor.py core\navigation_tasks\controller.py gui\modes\navigation_mode.py`
**验证结果：** 编译通过；未运行逻辑测试，等待真实导航日志确认是否出现 `nav movement exact path-goal click` 且绕锚点现象减少。
**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/navigation_tasks/models.py` | 浅读 | 浅读 | 追加 | 新增 MovementStep.force_click_target 作为执行器到 UI 输入层的精确点击标志。 |
| `core/navigation_tasks/movement_executor.py` | (partial) | (partial) | 追加 | 近锚点阶段改为精确 path_goal 点击，并短暂抑制恢复探针。 |
| `core/navigation_tasks/controller.py` | (partial) | (partial) | 追加 | 将 force_click_target 透传到 NavigationIntent.metadata。 |

## [SYNC] 2026-05-24 18:25 - 坐标漂移自动重定位恢复

### A. SYNC 范围声明
**触发任务：** 用户确认核心问题是需要可靠界定定位偏移，并把“重新定位”作为特殊恢复事件触发一次，不能使用固定偏移参数。
**直接变更文件：** `core/navigation_tasks/coordinate_diagnostics.py`, `core/navigation_core.py`, `core/navigation_tasks/controller.py`, `gui/modes/navigation_mode.py`, `docs/plans/2026-05-24-coordinate-drift-diagnostics.md`, `CODEBASE.md`, `ITERATION_LOG.md`。
**预计连带影响：** 自动导航和传送门事件继续共用统一任务控制器；坐标恢复是导航内部机制，不进入 `EventCoordinator`，不会与 portal 等业务事件竞争调度。

### C. SYNC 结果
**代码变化：**
- `CoordinateDiagnostics` 从只记录日志升级为漂移恢复状态机：对 `reg_source=f2f` 的 `route_deviation`、`raw_control_gap`、`raw_jump`、`near_target_stall` 等信号按时间窗打分，达到阈值后生成 `CoordinateRelocalizationRequest`。
- `NavigationTaskController.update()` 消费恢复请求后返回 `WAIT` 意图并带 `metadata.force_relocalize=True`，本帧不输出移动点击；强制重定位成功帧使用 `force_snap=True` 把 `trusted/control` 硬重置到新坐标，并重置 `MovementExecutor`。
- `NavigationCore.request_global_relocalization()` 清空 F2F 跟踪状态；下一帧 `localize()` 跳过 F2F 和局部搜索，直接完整 `wall_layer` 模板匹配，并在 `FrameRegistration.metadata` 标记 `forced_global`。
- `NavigationModeWidget._navigation_loop_unified()` 收到强制重定位 intent 后调用导航核心、记录 `navigation forced global relocalization`，并在执行输入前返回，避免偏移状态继续点击。
- 方案文档更新为当前已实现流程，列出 `coordinate relocalization requested/forced/accepted/rejected` 等关键日志。

**CODEBASE.md 更新内容：** 更新 §2 目录结构、§4 `navigation_tasks` 与 `navigation_core` 边界、§5 `NavigationTaskController.update()` 行为、§18 坐标漂移诊断从“只诊断”改为“诊断 + 内部重定位恢复”。

**验证命令：** `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\navigation_tasks\coordinate_diagnostics.py core\navigation_core.py core\navigation_tasks\controller.py gui\modes\navigation_mode.py`
**验证结果：** 编译通过；未运行逻辑测试，等待真实游戏导航日志确认是否出现恢复链路日志并降低偏移。

**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/navigation_tasks/coordinate_diagnostics.py` | 浅读 | (partial) | 2 | 新增恢复请求状态机、信号打分、强制/接受/拒绝日志。 |
| `core/navigation_core.py` | (partial) | (partial) | 18 | 新增强制全局模板匹配入口，保留原始 wall_layer 定位体系。 |
| `core/navigation_tasks/controller.py` | (partial) | (partial) | 追加 | 坐标恢复请求转成 WAIT intent；强制匹配成功后硬重置 control/trusted。 |
| `gui/modes/navigation_mode.py` | (partial) | (partial) | 20 | 导航循环消费 force_relocalize intent，并在输入执行前返回。 |
| `docs/plans/2026-05-24-coordinate-drift-diagnostics.md` | 浅读 | 浅读 | 2 | 从未来方案更新为当前已实现恢复流程和日志说明。 |

## [Round] 2026-05-24 18:46 - Portal missing-detection probe task split

### A. 本轮目标（阅读前声明）
**目标文件：** core/events/types/portal/minimap_detector.py, core/events/detectors/template_matcher.py, utils/event_icon_probe.py, core/events/position_stabilizer.py, core/events/memory.py
**本轮想弄清楚：** 不可识别传送门到底是模板匹配失败、颜色过滤失败、定位投影失败、事件记忆/冷却过滤，还是日志/UI 缺少必要证据。

### C. 本轮发现
**关键发现：** (verified) `D:\ACloud\image` 下两张静态图已用于 `utils/event_icon_probe.py --image` 探针。`95705f16-9696-402c-b008-82f8f7d87651.png` 在原模板 `portal_minimap_01/02` 下无 accepted hit：最佳分数分别为 `0.5597` 和 `0.4444`，但 `_portal_color_check()` 均为 `color-ok`，说明失败发生在模板匹配分数层，不是蓝色过滤、定位投影、memory 冷却或同帧候选上限。`fd4615e6-a089-403f-b2aa-26fceeafc952.png` 在原模板下可识别两个传送门：`0.8398`、`0.7921`。

**修订的旧结论：** (verified) “同帧候选上限导致只能识别两个传送门”不是这两张图失败的原因；小图远距离/裁剪外观下原模板本身低分。`max_candidates` 仍可能影响同帧多事件数量，但这次静态探针没有证明它是根因。

**代码变化：** (verified) 新增正式小地图模板 `assets/event_templates/portal/minimap/portal_minimap_03.png` 和 `portal_minimap_04.png`，来自小图中上/下两个传送门的 32x32 裁剪；`core/events/types/portal/assets.py` 接入四模板列表。`core/events/types/portal/definition.py` 把 `max_candidates`、`min_blue_ratio` 暴露为事件管理 UI 可编辑参数；`gui/dialogs/event_manager_dialog.py` 在当前配置摘要中显示这两个值。

**验证结果：** (verified) 四模板回跑静态探针：小图命中 `portal_minimap_03=0.9901`、`portal_minimap_04=0.9881`；大图仍命中原模板 `portal_minimap_01=0.8398`、`portal_minimap_02=0.7921`，新增模板在大图中低于阈值，未抢占原模板。编译命令 `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\events\types\portal\assets.py core\events\types\portal\definition.py gui\dialogs\event_manager_dialog.py utils\event_icon_probe.py` 通过。

**新疑问：** (partial) 新增裁剪模板能覆盖这两张静态图，但真实运行仍需要观察 `logs/event_runtime.log` 中是否出现 `portal minimap hits` 且 task 能进入 localization stable；若仍漏检，下一步应保存 raw minimap frame 而不是用聊天截图继续调参。

**更新了 CODEBASE.md：** §2 新增 `portal_minimap_03/04` 资产说明；§4 更新 `utils/event_icon_probe.py` 静态图片探针能力；§6 更新事件图标探针 flow；§13 记录当前四模板传送门识别行为。

**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/events/types/portal/minimap_detector.py` | (partial) | (partial) | 追加 | 确认 detector 先做模板匹配，再做 `_portal_color_check()`；本次小图失败发生在模板分数阈值前。 |
| `core/events/detectors/template_matcher.py` | (partial) | (partial) | 追加 | 确认匹配分数为灰度/边缘组合，并支持 alpha mask；本次未改算法，只扩展模板资产。 |
| `utils/event_icon_probe.py` | (partial) | (partial) | 追加 | 静态 `--image` 探针可复用运行时 matcher 和 portal color check，能区分模板低分与颜色过滤。 |
| `core/events/position_stabilizer.py` | (partial) | (partial) | 追加 | 确认定位投影只消费 accepted `EventDetection`；静态小图原模板无 detection，因此未进入此层。 |
| `core/events/memory.py` | (partial) | (partial) | 追加 | 确认 memory/cooldown 只消费 stable observation；静态小图原模板无 detection，不是 memory 抑制。 |
| `core/events/types/portal/assets.py` | PENDING | 浅读 | 1 | 四个小地图模板资产路径集中定义，`PortalMinimapDetector` 初始化时按存在性加载。 |
| `core/events/types/portal/definition.py` | (partial) | (partial) | 追加 | 传送门事件 schema 新增 `max_candidates`、`min_blue_ratio`，避免关键识别参数只藏在代码里。 |
| `gui/dialogs/event_manager_dialog.py` | (partial) | (partial) | 追加 | 当前配置摘要新增候选数量和蓝色比例，方便测试时确认 UI/配置值。 |

## [SYNC] 2026-05-24 19:15 - Portal recognition algorithm feature redesign

### A. SYNC 范围声明
**触发任务：** 用户指出继续新增整块模板不可持续，要求优化匹配算法，最好把传送门本体抠出来再做特征匹配，避免每个传送门都要单独模板。
**直接变更文件：** 预计 `core/events/types/portal/minimap_feature_matcher.py`, `core/events/types/portal/minimap_detector.py`, `core/events/types/portal/config.py`, `core/events/types/portal/definition.py`, `core/events/config.py`, `gui/dialogs/event_manager_dialog.py`, `utils/event_icon_probe.py`, `CODEBASE.md`, `ITERATION_LOG.md`。
**预计连带影响：** 传送门事件仍输出 `EventDetection`，后续 `EventPositionStabilizer`、`EventMemory`、导航到事件点、传送门 handler 不变；识别层从整块模板匹配改为颜色候选/形状过滤/抠图特征确认。

### C. SYNC 结果
**根因闭环：** (verified) 上一轮静态探针证明小图原整块模板最佳分数只有 `0.5597/0.4444`，但蓝色过滤通过；本轮单独验证蓝色二值特征匹配，使用原始 `portal_minimap_01/02` 两个模板即可在小图和大图同时命中，说明稳定特征是传送门蓝色本体结构，而不是周围背景像素。

**代码变化：**
- 新增 `core/events/types/portal/minimap_feature_matcher.py`：从模板和 raw minimap 中提取 HSV 蓝/青二值 mask，做多尺度 `TM_CCOEFF_NORMED` 匹配，并用蓝色像素数量和 density score 过滤候选。
- `PortalMinimapDetector.detect()` 优先调用 feature matcher，只有 feature 无命中时才回退旧整块模板匹配；输出 metadata 增加 `detector`, `mask_score`, `density_score`, `feature_blue_pixels` 等诊断字段。
- `PortalMinimapDetector.detect()` 还新增节流 `portal minimap no hits` 诊断日志，打印 feature 模板数、raw frame 蓝色特征像素数量和当前 feature 阈值，避免“没识别”时没有证据。
- 删除上一轮临时新增的 `portal_minimap_03/04` 整块模板资产，运行时继续只依赖原始两个 canonical 模板，避免模板堆积。
- `PortalEventConfig`、`DEFAULT_EVENT_CONFIG` 和事件 UI schema 新增 `feature_hue_min/max`, `feature_sat_min`, `feature_val_min`, `feature_min_blue_pixels`, `feature_max_blue_pixels`，关键识别参数可在事件管理中调整。
- `utils/event_icon_probe.py` 新增 `--portal-feature-detector` 和对应 HSV/像素阈值参数，用于离线验证运行时 feature 算法。

**验证结果：**
- 编译通过：`D:\ACloud\.venv\Scripts\python.exe -m py_compile core\events\config.py core\events\types\portal\minimap_feature_matcher.py core\events\types\portal\minimap_detector.py core\events\types\portal\config.py core\events\types\portal\definition.py gui\dialogs\event_manager_dialog.py utils\event_icon_probe.py`
- 静态 feature 探针通过：`95705f16-9696-402c-b008-82f8f7d87651.png` 命中 `(54,83)` score `0.9017` 和 `(79,116)` score `0.7782`；`fd4615e6-a089-403f-b2aa-26fceeafc952.png` 命中 `(259,127)` score `0.9286` 和 `(281,153)` score `0.9088`。

**CODEBASE.md 更新内容：** §2 新增 `minimap_feature_matcher.py` 并移除临时 03/04 模板说明；§4 更新 portal 事件包和探针职责；§5 记录 feature matcher 与 detector 算法；§6 更新事件图标探针 flow；§8 更新 portal 识别参数；§13 更新当前 portal 行为。

**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/events/types/portal/minimap_feature_matcher.py` | PENDING | 浅读 | 1 | 新增蓝色本体二值特征匹配，避免整块背景模板低分漏检。 |
| `core/events/types/portal/minimap_detector.py` | (partial) | (partial) | 追加 | detector 识别链改为 feature first、template fallback，后续 EventDetection 契约不变。 |
| `core/events/types/portal/config.py` | (partial) | (partial) | 追加 | 新增 portal feature HSV/像素阈值配置，from_dict 保持旧配置兼容默认值。 |
| `core/events/types/portal/definition.py` | (partial) | (partial) | 追加 | 事件管理 schema 暴露 feature 识别参数。 |
| `core/events/config.py` | 浅读 | 浅读 | 追加 | 默认 event_config 合并新增 feature 参数，旧地图配置读取时自动补默认值。 |
| `gui/dialogs/event_manager_dialog.py` | (partial) | (partial) | 追加 | 当前配置摘要显示部分 feature 参数，便于测试时确认值。 |
| `utils/event_icon_probe.py` | (partial) | (partial) | 追加 | 新增 `--portal-feature-detector` 静态/实时探针模式，复用运行时 feature matcher。 |

## [SYNC] 2026-05-24 20:28 - Coordinate relocalization over-trigger diagnosis

### A. SYNC 范围声明
**触发任务：** 用户反馈最新导航日志中重新定位触发过于频繁，要求先看日志确认原因。
**直接变更文件：** `core/navigation_tasks/coordinate_diagnostics.py`, `CODEBASE.md`, `ITERATION_LOG.md`。
**预计连带影响：** `NavigationTaskController` 仍通过同一 `CoordinateRelocalizationRequest` 转成 `WAIT + force_relocalize` intent；`NavigationCore.request_global_relocalization()` 和 GUI 消费路径不变。

### C. SYNC 结果
**根因闭环：** (verified) `logs/coordinate_diagnostics.log` 中频繁请求主要来自 `route_deviation` 重复入队：例如 `20:13:35`, `20:13:39`, `20:13:52`, `20:13:59`, `20:14:06`, `20:14:14` 都是 `reason=route_deviation score=3 signals=(route_deviation,route_deviation,route_deviation)`。这说明诊断器把路线投影偏差/导航 fallback 当成坐标漂移证据，而不是定位匹配本身必然错误。另一个放大器是 `long_f2f_tracking` 每帧入队，日志中出现 `score=9` 和 `score=20` 的情况，实际只是同一上下文信号重复叠分。

**代码变化：**
- `CoordinateDiagnostics._register_recovery_signal()` 改为按唯一 signal name 取最大 severity 计分，避免同一 `route_deviation` 或 `long_f2f_tracking` 在 2.6 秒窗口内刷分。
- `long_f2f_tracking` 改为 severity 0，仅作为上下文，不再放大恢复分数。
- 新增 primary signal 策略：只有 `raw_jump` 或 `raw_control_gap` 这类真实坐标异常可以触发强制重定位；`route_deviation`、`near_target_stall` 没有 primary 时只记录 `coordinate relocalization suppressed`。
- `raw_jump` severity 提升到 3，可直接触发一次重定位；`raw_control_gap` 根据 gap 大小给 1/2 分，需要和上下文信号组合才触发。
- 强制重定位 accepted/rejected 后清空 `_signals` 和 `_near_target_since_ms`，避免旧的 near-target 计时在重定位后继续触发。

**验证结果：** `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\navigation_tasks\coordinate_diagnostics.py` 通过；未做逻辑测试，等待真实游戏导航日志确认 `coordinate relocalization suppressed` 增加、`navigation forced global relocalization` 降低。

**CODEBASE.md 更新内容：** §5 `NavigationTaskController.update()` 诊断步骤说明；§18 坐标漂移诊断恢复策略。

**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/navigation_tasks/coordinate_diagnostics.py` | (partial) | (partial) | 追加 | 确认过触发过频根因并改为唯一信号计分 + primary signal 门控。 |
| `CODEBASE.md` | 文档 | 文档 | 追加 | 更新坐标恢复策略描述，明确 route/near/f2f 不再单独强制重定位。 |
| `ITERATION_LOG.md` | 文档 | 文档 | 追加 | 记录本次日志根因、代码变更和编译结果。 |

## [SYNC] 2026-05-24 20:46 - Visual-consistency relocalization trigger

### A. SYNC 范围声明
**触发任务：** 用户要求废弃当前频繁触发的路线/锚点偏差重定位逻辑，改为“截图实际位置 A 与导航图人物位置 B 有稳定差异”才触发重定位。
**直接变更文件：** `core/navigation_core.py`, `core/navigation_tasks/coordinate_diagnostics.py`, `gui/navigation_params.py`, `gui/dialogs/nav_params_dialog.py`, `gui/modes/navigation_mode.py`, `CODEBASE.md`, `ITERATION_LOG.md`。
**预计连带影响：** `NavigationTaskController` 的 relocalization intent、`NavigationCore.request_global_relocalization()`、GUI 消费 `force_relocalize` 的路径不变；变化只在“何时请求重定位”的证据来源。

### C. SYNC 结果
**根因修正：** (verified) 之前的恢复逻辑把 `route_deviation`、`near_target_stall` 等导航规划现象当成重定位证据。新逻辑不再使用路线、锚点、A* fallback 作为强制重定位条件。

**代码变化：**
- `NavigationCore.localize()` 的 F2F 分支新增视觉一致性校验：定期把当前截图提取出的 `wall_mask` 放大到地图尺度，只在当前人物点附近的小窗口里做 `cv2.matchTemplate`，得到截图本帧最应该贴到大地图上的 `visual_player`。
- F2F 的 `FrameRegistration.metadata` 新增 `visual_check`, `visual_conf`, `visual_expected_score`, `visual_player`, `visual_delta`, `visual_delta_dist`, `visual_mismatch`，用于日志判断“截图位置 A”和“导航位置 B”是否稳定不同。
- `CoordinateDiagnostics` 删除路线偏差、近目标卡住、raw-control smoothing gap、long F2F duration 对重定位的触发作用；它们只写诊断日志。
- 新 primary signals 只剩 `visual_mismatch` 和 `raw_jump`。`visual_mismatch` 必须连续达到配置帧数才触发；`raw_jump` 保留为极端跳变保险。
- 导航参数新增并可保存：`coordinate_visual_check_interval_ms`, `coordinate_visual_check_margin`, `coordinate_visual_match_min_confidence`, `coordinate_visual_mismatch_threshold`, `coordinate_visual_mismatch_frames`。
- 参数面板“定位/运行”页新增视觉校验相关控件；`NavigationModeWidget._configure_navigation_task_controller()` 会把这些值同步到 `NavigationCore` 和 `CoordinateDiagnostics`。

**验证结果：** `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\navigation_core.py core\navigation_tasks\coordinate_diagnostics.py gui\navigation_params.py gui\dialogs\nav_params_dialog.py gui\modes\navigation_mode.py` 通过；未运行逻辑测试，等待真实游戏导航日志确认 `visual coordinate mismatch` 和 `coordinate relocalization requested reason=visual_mismatch` 是否符合肉眼偏移。

**CODEBASE.md 更新内容：** §5 `NavigationTaskController.update()` 诊断步骤；§8 `NavConfig` 新增视觉校验参数；§18 坐标漂移诊断改为视觉一致性触发。

**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/navigation_core.py` | (partial) | (partial) | 追加 | F2F 跟踪新增局部视觉模板校验，将截图最佳贴图位置写入 FrameRegistration metadata。 |
| `core/navigation_tasks/coordinate_diagnostics.py` | (partial) | (partial) | 追加 | 重定位触发源改为 visual_mismatch/raw_jump；路线偏差和近目标卡住只保留诊断。 |
| `gui/navigation_params.py` | (partial) | (partial) | 追加 | NavConfig 新增视觉校验阈值字段和 config.json 序列化。 |
| `gui/dialogs/nav_params_dialog.py` | (partial) | (partial) | 追加 | 参数面板新增视觉校验间隔、搜索边距、最低置信度、偏移阈值、连续帧数控件。 |
| `gui/modes/navigation_mode.py` | (partial) | (partial) | 追加 | 将视觉校验配置同步到 NavigationCore 和 CoordinateDiagnostics。 |

## [SYNC] 2026-05-24 21:30 - Portal-trigger relocalization and completion

### A. SYNC 范围声明
**触发任务：** 用户反馈传送门按下 `D` 后重定位卡住，且成对传送门传入/传出状态没有正确完成，事件绕回重复执行。
**直接变更文件：** 待调查后确定，预计涉及 `core/navigation_core.py`, `core/events/types/portal/handler.py`, `core/events/runner.py`, `core/events/memory.py`, `gui/modes/navigation_mode.py`。
**预计连带影响：** 复用开始导航同款全图定位路径；传送门事件在等待传送结果时应允许大跳变定位；事件完成时应同时关闭 entry/exit portal task。

### C. SYNC 结果
**根因确认：** (verified) 最新 `coordinate_diagnostics.log` 显示传送门按 `D` 后进入 `template_match_failed/jump_rejected` 循环；普通定位把传送后的合法大位移当成异常跳变拒绝，导致 `PortalEventHandler.wait_result` 一直拿不到新的有效 `player_global_pos`。
**代码变化：**
- `NavigationCore` 新增 `request_full_map_localization()`，`request_global_relocalization()` 作为兼容别名；强制重定位现在走与开始导航一致的全图模板匹配阈值，不再使用额外更高的 `force_global_min_confidence`。
- `PortalEventHandler` 在按 `D` 后等待传送完成阶段返回带 `force_relocalize=True` 的 WAIT action，请求下一帧全图定位；完成判断改为优先识别已知出口门，其次大距离位移，最后小地图环境变化。
- `EventAction.wait()` 支持 metadata；`NavigationTaskController._update_event_task()` 会把 WAIT metadata 透传给 GUI。
- `NavigationTaskController` 在 `forced_reason=portal_wait_result` 的强制定位成功后保留当前 active event，避免传送后调度器切到出口门或静态路线，保证原入口 handler 有机会完成 teleport session。
- `EventRunner` 和 `EventMemory.complete_teleport_session()` 增加 `exit_task_id` / `exit_player_pos` 传递，优先按已知出口 task id 标记出口完成，再 fallback 到坐标半径查找或 synthetic exit。
**验证结果：** `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\navigation_core.py core\events\models.py core\events\types\portal\handler.py core\events\runner.py core\events\memory.py core\navigation_tasks\controller.py gui\modes\navigation_mode.py` 通过。未做逻辑自动测试，等待真实游戏运行日志验证。
**CODEBASE.md 更新内容：** §4 `core/navigation_core.py`、§13 portal flow、§17 坐标诊断恢复说明，补充 full-map localization、portal wait-result recovery 和 exit task id 完成语义。
**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/navigation_core.py` | (partial) | (partial) | 追加 | 确认强制重定位现在复用开始导航的全图模板匹配阈值，并绕过普通 jump rejection。|
| `core/events/types/portal/handler.py` | (partial) | (partial) | 追加 | 确认传送门等待结果阶段会请求全图定位，完成 metadata 携带 known exit id/player pos。|
| `core/events/memory.py` | (partial) | (partial) | 追加 | 确认 teleport session 优先用 exit_task_id 标记出口，否则按坐标查找/创建 synthetic exit。|
| `core/navigation_tasks/controller.py` | (partial) | (partial) | 追加 | 确认 WAIT action metadata 透传，并在 portal_wait_result 重定位成功时保留 active event。|

## [SYNC] 2026-05-24 22:10 - Relocalization regression and portal false-positive guard

### A. SYNC 范围声明
**触发任务：** 用户反馈开始导航定位和重定位都失效，并怀疑是否与前面高清绘图/墙体逻辑改动有关；同时地图上出现三处不应存在的传送门标记。
**直接变更文件：** `core/navigation_core.py`, `core/stitcher_core.py`, `gui/navigation_params.py`, `gui/modes/navigation/map_runtime.py`, `gui/modes/navigation_mode.py`, `CODEBASE.md`, `ITERATION_LOG.md`。
**预计连带影响：** 定位匹配必须继续使用原始 `wall_layer`，A* 侵蚀只影响 `nav_wall_layer`；导航保存配置不能破坏建图参数；传送门误报应优先限制在识别层。

### C. SYNC 结果
**关键发现：** (verified) 最新日志对应 `map_data/大佬A`，该地图 `map_data.npz` 和 `config.json` 的 `draw_scale` 都是 3.0，因此不是当前这张图的简单倍率错配。A* 的 `nav_wall_erode_iterations` 只派生 `nav_wall_layer`，定位仍匹配原始 `wall_layer`，所以墙体侵蚀本身不应导致 `conf=0.14~0.16`。但导航保存配置此前会覆盖地图 `config.json`，丢失 `stitcher_params` 等建图专属参数；这会破坏“绘图环境与导航环境完全一致”的可追溯性。假传送门日志明确来自 `source=minimap_feature+wall_registration`，即蓝色 feature detector 误报，而不是定位投影阶段凭空生成。
**代码变化：**
- `NavigationCore` 记录 `map_draw_scale`，导航运行时以 `map_data.npz` 的 draw scale 为权威；`NavigationModeWidget._apply_config_to_core()` 发现配置倍率不一致时记录 `navigation draw_scale config mismatch` 并使用地图包值。
- `MapStitcher.save_map_package()` 新增保存 `wall_close_kernel_size`；`NavigationCore` 加载后用它作为 `wall_match_close_kernel_size`，让实时定位模板复现建图时的墙体闭运算。旧地图没有该字段时仍回退 3。
- `NavigationCore.localize()` 的模板匹配失败会节流打印 `Localization template match failed`，包含置信度、阈值、full_map/forced、draw_scale/map_draw_scale、mask 尺寸和特征数、搜索区域、闭运算核，便于下一次实测判断是截图窗口、识别参数还是地图墙层不一致。
- `save_nav_config()` 改为合并写回，保留现有地图配置里的 mapping-only 字段和已有 recognizer 字段，避免导航页保存把建图配置覆盖掉。
- 传送门 feature detector 已保持默认关闭，默认运行只走模板匹配 + 蓝色校验；feature detector 后续只能显式开启。
**验证结果：** `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\navigation_core.py core\stitcher_core.py gui\navigation_params.py gui\modes\navigation\map_runtime.py gui\modes\navigation_mode.py core\events\config.py core\events\types\portal\config.py core\events\types\portal\minimap_detector.py` 通过。实时截图探针在当前桌面没有抓到小地图特征，不能作为游戏内匹配结论；需要用户重新运行游戏内导航后看新增定位失败日志。
**CODEBASE.md 更新内容：** 更新 `core/navigation_core.py` 注意事项、portal 当前识别默认策略、地图保存流、导航 map_runtime 保存语义。
**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/navigation_core.py` | (partial) | (partial) | 追加 | 明确 draw_scale 来源、墙体闭运算复现、全图匹配失败诊断日志和 jump rejection 边界。 |
| `core/stitcher_core.py` | (partial) | (partial) | 追加 | 地图包新增保存 `wall_close_kernel_size`，支持导航复现建图墙体模板处理。 |
| `gui/modes/navigation/map_runtime.py` | (partial) | (partial) | 追加 | 导航保存配置改为 merge，防止丢失建图字段。 |
| `gui/modes/navigation_mode.py` | (partial) | (partial) | 追加 | `_apply_config_to_core()` 以地图包 draw_scale 为准，并记录倍率不一致。 |
| `core/events/types/portal/minimap_detector.py` | (partial) | (partial) | 追加 | 误报来源确认是 opt-in feature detector，默认模板路径保留。 |

## [SYNC] 2026-05-25 12:40 - Event approach stabilization gate

### A. SYNC 范围声明
**触发任务：** 用户确认先优化事件靠近逻辑：事件进入真实游戏视野后先用短距离 A* 收敛并停稳，再允许传送门 handler 点击/按 `D`。
**直接变更文件：** `core/navigation_tasks/event_approach.py`, `core/navigation_tasks/controller.py`, `core/navigation_tasks/movement_executor.py`, `gui/navigation_params.py`, `gui/dialogs/nav_params_dialog.py`, `gui/modes/navigation_mode.py`, `CODEBASE.md`, `ITERATION_LOG.md`。
**预计连带影响：** 自动导航和手动“测试传送门”都走同一个 `NavigationTaskController.update()`，因此同一套事件靠近/停稳门控会同时影响真实导航和事件测试；传送门 handler 本身不直接负责靠近策略。

### C. SYNC 结果
**关键发现：** (verified) 旧链路在 `_update_event_task()` 中先调用 `event_coordinator.run_task()`，所以 `PortalEventHandler` 可以在角色刚进入半径或还未停稳时推进到 `portal_point_click -> press D`。事件靠近属于导航层职责，放入 portal handler 会让后续随机事件重复造轮子。

**代码变化：**
- 新增 `core/navigation_tasks/event_approach.py`，提供 `EventApproachController` 和 `EventApproachConfig`。它在事件 handler 前执行：真实视野判定、远距离 A*+锚点、真实视野内短 lookahead A*、停靠半径、停稳时间、稳定帧数判断。
- `NavigationTaskController._update_event_task()` 在 `event_coordinator.run_task()` 前接入门控。任务未 released 时只返回移动/等待 intent；ready 后记录 `event approach released`，同一任务后续不再被门控打断，避免 portal `wait_result` 被重新拦截。
- `MovementExecutor.step()` 增加单次 `click_cooldown_ms` override，事件近距离阶段可以使用更慢点击节奏，不污染普通路线和锚点配置。
- `NavConfig` 新增事件靠近参数：`event_approach_enabled`, `event_visible_margin`, `event_approach_lookahead`, `event_approach_click_cooldown_ms`, `event_stop_radius`, `event_settle_ms`, `event_stable_frames`, `event_max_motion_per_frame`。
- `NavParametersDialog` 新增“事件靠近”页，把上述参数做成 UI 可调并可保存；`NavigationModeWidget._configure_navigation_task_controller()` 把配置同步给 `EventApproachController`。

**验证结果：** `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\navigation_tasks\event_approach.py core\navigation_tasks\movement_executor.py core\navigation_tasks\controller.py gui\navigation_params.py gui\dialogs\nav_params_dialog.py gui\modes\navigation_mode.py` 通过；`git diff --check` 无空白错误，仅有既有 CRLF 提示。未跑逻辑测试，等待游戏内通过 `event approach far/approach/settling/ready/released` 日志确认。

**CODEBASE.md 更新内容：** §15 事件四阶段方法论补充事件靠近门控；新增 §19 事件靠近停稳层，记录模块职责、执行链路、关键参数和风险。

**覆盖进度更新：**
| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|------|-------|-------|---------|------|
| `core/navigation_tasks/event_approach.py` | PENDING | (partial) | 1 | 新增事件靠近门控，确认远距离锚点导航、真实视野内直接 A*、停稳释放三个阶段。 |
| `core/navigation_tasks/controller.py` | (partial) | (partial) | 追加 | 事件 handler 前新增 approach gate，COMPLETE/FAIL 会清理 released 状态。 |
| `core/navigation_tasks/movement_executor.py` | (partial) | (partial) | 追加 | `step()` 新增 per-call 点击冷却 override，避免事件近距离节奏影响普通导航。 |
| `gui/navigation_params.py` | (partial) | (partial) | 追加 | NavConfig 新增事件靠近参数和 config.json 序列化。 |
| `gui/dialogs/nav_params_dialog.py` | (partial) | (partial) | 追加 | 参数面板新增“事件靠近”页，暴露真实视野边距、lookahead、冷却、停靠/停稳参数。 |
| `gui/modes/navigation_mode.py` | (partial) | (partial) | 追加 | `_configure_navigation_task_controller()` 同步事件靠近配置；事件测试重置会清空 approach runtime。 |
## [SYNC] 2026-05-25 20:45 - Portal minimap detection default

### A. SYNC scope
**Task:** Diagnose why portal minimap events no longer appear on the current map/session after recent navigation and event changes.
**Direct files changed:** `core/events/config.py`, `core/events/types/portal/config.py`, `core/events/types/portal/definition.py`, `CODEBASE.md`, `ITERATION_LOG.md`.
**Expected impact:** New maps without `event_config.json` now use the portal blue-body feature matcher by default; the old gray/edge full-template matcher remains the fallback. Existing saved configs with explicit `feature_detector_enabled=false` still keep that override.

### C. SYNC result
**Root cause:** (verified) Latest `logs/event_runtime.log` repeatedly showed `portal minimap no hits source=template feature_enabled=False` while `feature_blue_pixels` stayed in the configured valid range. A live probe on the same minimap frame showed the full-template path had best score `0.6021`, below runtime threshold `0.74`, but `--portal-feature-detector` found the portal at score `0.9206`.
**Code change:** `DEFAULT_EVENT_CONFIG["events"]["portal"]["feature_detector_enabled"]` and `PortalEventConfig.feature_detector_enabled` now default to `True`; `PortalEventConfig.from_dict()` also falls back to `True` when the key is absent. The event UI label is now `portal blue feature detector` instead of `experimental feature detector`.
**Verification:** `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\events\config.py core\events\types\portal\config.py core\events\types\portal\definition.py core\events\types\portal\minimap_detector.py core\events\types\portal\minimap_feature_matcher.py` passed. Live probe evidence: template path no accepted hit above `0.74`; feature path accepted hits at `0.9206` and `0.7511`.
**CODEBASE.md updated:** Portal minimap detection default now states feature-first, template-fallback, with UI kill switch for false positives.

## [SYNC] 2026-05-25 22:27 - Portal minimap shape+color probe

### A. SYNC scope
**Task:** User asked to replace the loose small-minimap event probe with a shape + color algorithm first, before changing runtime portal detection.
**Direct files changed:** `core/events/types/portal/minimap_shape_color_matcher.py`, `utils/event_icon_probe.py`, `CODEBASE.md`, `ITERATION_LOG.md`.
**Expected impact:** Adds a stricter probe path for portal minimap recognition. Runtime `PortalMinimapDetector` still uses the existing feature-first/template-fallback logic until the user approves integration.

### C. SYNC result
**Root cause context:** (verified) The current blue-body feature matcher can over-accept local blue patterns because its validation is mostly blue mask structure and blue-pixel density. A recent false portal around global `(4192,2800)` came from `source=minimap_feature+wall_registration`, so the next probe needs to verify not only blue color but also the portal's white/gray outer ring and combined icon shape.

**Code change:**
- Added `core/events/types/portal/minimap_shape_color_matcher.py`.
- Added `--portal-shape-color-detector` to `utils/event_icon_probe.py`.
- Added probe parameters for HSV blue core, white/gray outer ring, minimum blue/outer/combined shape scores, and minimum outer pixels.
- Probe output now saves `minimap_portal_shape_blue_mask_*`, `minimap_portal_shape_outer_mask_*`, `minimap_portal_shape_combined_mask_*`, a boxed debug image, and accepted/rejected candidate crops.
- Candidate scoring combines blue core, outer ring, combined shape, edge, and masked HSV color similarity. Candidate gates record reject reasons such as `score`, `blue_shape`, `outer_shape`, `combined_shape`, `blue_pixels_low/high`, and `outer_pixels_low`.
- Duplicate merge now sorts by `(accepted, score)` so an accepted candidate is not displaced by a same-location rejected candidate with a higher raw response.

**Verification:**
- Syntax check passed: `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\events\types\portal\minimap_shape_color_matcher.py utils\event_icon_probe.py`.
- Static probe command passed on `D:\ACloud\image\95705f16-9696-402c-b008-82f8f7d87651.png` and `D:\ACloud\image\fd4615e6-a089-403f-b2aa-26fceeafc952.png`.
- Shape+color result on image 1: accepted one real portal at center `(54,83)` score `0.7522`; rejected the old lower blue false-looking candidate at `(79,117)` score `0.6406` because total score was below threshold.
- Shape+color result on image 2: accepted two real portals at centers `(258,127)` score `0.8816` and `(281,153)` score `0.8610`; rejected unrelated blue candidates at `(66,68)` and `(54,45)`.
- Old `--portal-feature-detector` comparison on the same images accepted two candidates on image 1, including the lower blue object that shape+color rejected, confirming the stricter probe reduces this class of false positive.
- Live one-frame probe saved debug output but found no candidate; this is inconclusive because the current live minimap frame may not contain a portal.

**CODEBASE.md updated:** Added `minimap_shape_color_matcher.py`, updated `event_icon_probe.py` responsibilities, event icon probe flow, portal package notes, and reusable capability list.

**Coverage update:**
| File | Previous | Current | Reads | Note |
|------|----------|---------|-------|------|
| `core/events/types/portal/minimap_shape_color_matcher.py` | PENDING | (partial) | 1 | New strict portal minimap probe algorithm; not yet wired into runtime detector. |
| `utils/event_icon_probe.py` | (partial) | (partial) | appended | Added shape+color probe mode, static/live image support remains unchanged. |
| `core/events/types/portal/minimap_detector.py` | (partial) | unchanged | appended | Runtime detector intentionally not changed in this round. |

## [SYNC] 2026-05-25 22:40 - Portal detector mode selector

### A. SYNC scope
**Task:** User approved wiring shape+color into runtime, but explicitly asked not to replace existing algorithms. All current minimap portal algorithms should be selectable from the event manager panel for HITL comparison before convergence.
**Direct files changed:** `core/events/config.py`, `core/events/types/portal/config.py`, `core/events/types/portal/definition.py`, `core/events/types/portal/minimap_detector.py`, `gui/dialogs/event_manager_dialog.py`, `CODEBASE.md`, `ITERATION_LOG.md`.
**Expected impact:** Portal event detection can be switched between `template`, `feature`, `feature_then_template`, and `shape_color` without changing event memory, localization, navigation, or handler logic.

### C. SYNC result
**Code change:**
- `PortalEventConfig` now has `detector_mode`, defaulting to `feature_then_template`.
- `EventSystemConfig.from_dict()` preserves old saved-map behavior: if old config explicitly has `feature_detector_enabled=false` and no `detector_mode`, it maps to `detector_mode=template`; otherwise absent mode defaults to `feature_then_template`.
- `PortalEventDefinition.config_schema()` exposes `detector_mode` as a choice field in the event manager. `feature_detector_enabled` remains in config but is no longer editable in the UI.
- Added shape+color runtime parameters to the event schema: `shape_outer_sat_max`, `shape_outer_val_min`, `shape_min_blue_score`, `shape_min_outer_score`, `shape_min_shape_score`, and `shape_min_outer_pixels`.
- `PortalMinimapDetector.detect()` now dispatches by mode:
  - `template`: old full-image gray/edge template matching only.
  - `feature`: blue/cyan portal-body feature matcher only.
  - `feature_then_template`: feature first, then old template fallback.
  - `shape_color`: strict shape+color matcher only.
- Runtime logs now include `mode`, shape score fields, and `portal minimap shape-color rejected` when shape+color found candidates but rejected all of them.
- Event manager summary row now shows `detector_mode` and key shape thresholds.

**Verification:**
- Compile passed: `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\events\config.py core\events\types\portal\config.py core\events\types\portal\definition.py core\events\types\portal\minimap_detector.py core\events\types\portal\minimap_shape_color_matcher.py gui\dialogs\event_manager_dialog.py utils\event_icon_probe.py`.
- Config compatibility check passed:
  - empty config -> `feature_then_template`
  - old `feature_detector_enabled=false` -> `template`
  - old `feature_detector_enabled=true` -> `feature_then_template`
  - explicit `detector_mode=shape_color` wins even if legacy bool is false
- Offline detector dispatch on the two saved images passed:
  - `template`: misses the small image, accepts two portals on the large image.
  - `feature`: accepts two candidates on the small image including the lower blue false-looking candidate, accepts two portals on the large image.
  - `feature_then_template`: same as feature on these images because feature hits first.
  - `shape_color`: accepts one real portal on the small image and two real portals on the large image.

**CODEBASE.md updated:** Portal detector docs now describe selectable modes, shape+color runtime wiring, config compatibility, and new shape thresholds.

**Coverage update:**
| File | Previous | Current | Reads | Note |
|------|----------|---------|-------|------|
| `core/events/types/portal/minimap_detector.py` | (partial) | (partial) | appended | Runtime detector now supports four selectable minimap recognition modes. |
| `core/events/types/portal/config.py` | (partial) | (partial) | appended | Added `detector_mode` and shape+color threshold fields. |
| `core/events/config.py` | shallow | shallow | appended | Added default detector mode plus legacy config mapping. |
| `gui/dialogs/event_manager_dialog.py` | (partial) | (partial) | appended | Summary displays selected detector mode and shape thresholds. |

## [SYNC] 2026-05-25 23:05 - Event manager dialog visibility guard

### A. SYNC scope
**Task:** User reports that after clicking "测试传送门" and the event finishes, the event manager panel disappears and cannot be reopened from the main UI. Also requested an explanation of current portal recognition algorithms.
**Direct files changed:** `gui/dialogs/event_manager_dialog.py`, `gui/modes/navigation_mode.py`, `CODEBASE.md`, `ITERATION_LOG.md`.
**Expected impact:** Event manager can be reopened after manual event test, regardless of game-input window mode or previous close/hide state. No change to event detection, movement, or portal handler logic.

### C. SYNC result
**Root cause hypothesis:** (verified from code shape, not yet HITL confirmed) `EventManagerDialog` was constructed as a child dialog of `NavigationModeWidget`. Manual portal testing enables game-input window mode, removes topmost from the main window and lowers it. A child dialog can follow the parent window into a hidden/non-activatable layer; after that, `show/raise/activateWindow()` on the existing child object may not make it findable.

**Code change:**
- `EventManagerDialog` now uses `Qt.Tool` and `WA_DeleteOnClose=False`.
- `NavigationModeWidget` now creates the event dialog through `_ensure_event_dialog()` instead of assuming the original object is always valid.
- `_ensure_event_dialog()` reconnects signals and rebinds the manual portal test button when needed.
- `toggle_event_dialog()` ensures the dialog exists before refresh/show.
- `_show_owned_dialog()` restores minimized state, moves newly shown dialogs near the main window, then calls `show/raise/activateWindow`.

**Verification:** `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\dialogs\event_manager_dialog.py gui\modes\navigation_mode.py` passed. Needs user HITL confirmation after running a manual portal test and reopening "事件管理".

**Coverage update:**
| File | Previous | Current | Reads | Note |
|------|----------|---------|-------|------|
| `gui/dialogs/event_manager_dialog.py` | (partial) | (partial) | appended | Dialog is now a tool window and not deleted on close. |
| `gui/modes/navigation_mode.py` | (partial) | (partial) | appended | Event manager lifecycle now uses ensure/rebind/show guard. |

## [SYNC] 2026-06-03 17:07 - Loot ROI feature match probe

### A. SYNC scope
**Task:** User asked for an independent probe of ROI-internal shape similarity matching, similar to a lightweight CNN feature response, and to measure effect plus resource cost before runtime integration.
**Direct files changed:** `debug/loot_feature_match_probe.py`, `architecture_docs/zh-CN/core/events/types/loot/ARCHITECTURE.md`, `CODEBASE.md`, `ITERATION_LOG.md`.
**Expected impact:** Adds a standalone debug/probe entry only. Production `LootMinimapDetector` behavior is unchanged.

### C. SYNC result
**Code change:** Added `debug/loot_feature_match_probe.py`. The probe reuses loot template loading, alpha masks, center-player exclusion templates, and `loot_seed_bboxes()`, then searches fixed-size multi-anchor ROI windows with yellow-diamond/red-star/gold-triangle templates. Candidate scoring combines masked template similarity, edge overlap, Chamfer distance, 2x2 HOG-lite similarity, contour/Hu similarity, semantic shape gates, and low-weight color evidence. The probe defaults to shape templates only, scales `0.75,0.85,1.0`, and `top_k_per_template=2`.

**Verification:**
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile debug\loot_feature_match_probe.py` passed.
- Full dataset probe passed on `D:\ACloud\image\sample`: run `debug/loot_feature_match_probe/20260603_170739/`, TP=25, FP=0, FN=0, TN=52, precision=1.0000, recall=1.0000, FPR=0.0000, average total time 241.665ms, p95 449.336ms, max 666.978ms.
- `--workers 4` comparison reduced wall-clock only slightly but increased per-image latency, so runtime integration should prefer an async detector thread over per-frame multithreading.

**CODEBASE.md updated:** Added the new probe command, algorithm chain, latest metrics, and runtime integration caveat.

**Coverage update:**
| File | Previous | Current | Reads | Note |
|------|----------|---------|-------|------|
| `debug/loot_feature_match_probe.py` | PENDING | (partial) | 1 | New standalone probe for ROI sliding multi-feature loot shape matching; production detector not changed. |
| `architecture_docs/zh-CN/core/events/types/loot/ARCHITECTURE.md` | (partial) | (partial) | appended | Documented 2026-06-03 probe algorithm, metrics, and threading caveat in Chinese. |
| `CODEBASE.md` | (partial) | (partial) | appended | Added probe entry and latest dataset result to loot project intelligence section. |

## [SYNC] 2026-06-03 17:12 - Loot async perception implementation

### A. SYNC scope
**Task:** Implement the agreed decoupled multi-layer loot perception rule: cheap first-stage detection, heavy feature matching only when needed, async execution, memory dedupe, and no blocking of the navigation frame loop.
**Direct files expected:** `core/events/types/loot/*`, `core/events/types/loot/detection/*`, possibly `gui/modes/navigation/events/*` or event coordinator wiring if runtime integration requires it.
**Expected impact:** Production loot detection should stop running heavyweight recognition synchronously every frame; the navigation loop should consume cached/confirmed loot observations while an independent worker processes fresh minimap frames.

## [SYNC] 2026-06-03 17:42 - Loot async probe parity diagnosis

### A. SYNC scope
**Task:** Keep production loot default parameters identical to the successful feature-match probe, then diagnose why the async production integration missed several positive samples while the probe reached 25 TP / 0 FP / 0 FN / 52 TN.
**Direct files expected:** `core/events/types/loot/minimap_detector.py`, `core/events/types/loot/perception/*`, `core/events/types/loot/detection/feature_match/*`, `core/events/types/loot/config.py`, Chinese loot architecture docs, `CODEBASE.md`, `ITERATION_LOG.md`.
**Expected impact:** Runtime detector should use the same feature defaults as `debug/loot_feature_match_probe.py`, keep heavy matching off the frame loop, and avoid clearing fresh async detections before the caller can consume them.

### C. SYNC result
**Key finding:** Production `FeatureLootMatcher.detect()` already matches the probe on `D:/ACloud/image/sample`: TP=25, FP=0, FN=0, TN=52. The production async path also matches when the harness waits for the worker result instead of treating the first empty frame as final: TP=25, FP=0, FN=0, TN=52.

**Default parameter parity:** Confirmed from `map_data/A/event_config.json` and `LootEventConfig.from_dict()`:
- `detector_mode=async_feature_match`
- `feature_match_threshold=0.64`
- `feature_match_collect_threshold=0.38`
- `feature_match_top_k_per_template=2`
- `feature_match_max_candidates=5`
- `feature_match_search_padding=48`
- `feature_match_scales=0.75,0.85,1.0`

**Code change:** No feature threshold or matcher behavior changed in this sub-round. Documentation was corrected because the previous text still said the feature probe was not connected to runtime and described `weighted_blob` as the main default path.

**Verification:**
- Compile passed: `D:\ACloud\.venv\Scripts\python.exe -m py_compile core\events\config_model.py core\events\types\loot\config.py core\events\types\loot\definition.py core\events\types\loot\minimap_detector.py core\events\types\loot\detection\feature_match\models.py core\events\types\loot\detection\feature_match\descriptors.py core\events\types\loot\detection\feature_match\semantics.py core\events\types\loot\detection\feature_match\matcher.py core\events\types\loot\perception\models.py core\events\types\loot\perception\projection.py core\events\types\loot\perception\async_worker.py`.
- Latest probe output: `debug/loot_feature_match_probe/20260603_174004/`, TP=25, FP=0, FN=0, TN=52, precision=1.0000, recall=1.0000, FPR=0.0000, avg=341.366ms, p95=664.686ms.
- Production async harness with valid `FrameRegistration`: TP=25, FP=0, FN=0, TN=52, elapsed wall time about 44.151s for 77 offline samples.

**CODEBASE.md updated:** Loot top-level section now states that `detection/feature_match/` is the production backend for `async_feature_match`, lists the probe-aligned defaults, and records sync/async parity verification.

**Coverage update:**
| File | Previous | Current | Reads | Note |
|------|----------|---------|-------|------|
| `core/events/types/loot/config.py` | (partial) | (partial) | appended | Rechecked feature defaults and map-config parity with probe defaults. |
| `core/events/types/loot/minimap_detector.py` | (partial) | (partial) | appended | Rechecked default async dispatch, sync feature mode, and weighted blob fallback. |
| `core/events/types/loot/perception/async_worker.py` | PENDING | (partial) | 1 | Rechecked worker submission, result merge, TTL, visibility update, and detection projection. |
| `core/events/types/loot/detection/feature_match/matcher.py` | PENDING | (partial) | 1 | Rechecked production matcher parity with probe on full sample set. |
| `architecture_docs/zh-CN/core/events/types/loot/ARCHITECTURE.md` | (partial) | (partial) | appended | Updated module tree and runtime algorithm description for async feature matching. |
| `CODEBASE.md` | (partial) | (partial) | appended | Updated loot summary and verification result. |

## [SYNC] 2026-06-03 18:05 - Loot async integration vs player localization diagnosis

### A. SYNC scope
**Task:** User reports latest runtime is no longer laggy, but player localization becomes inaccurate as soon as movement starts. Diagnose whether the new loot recognition / async feature matching path interferes with localization or navigation frame state.
**Direct files expected:** `gui/modes/navigation/runtime/*`, `core/localization/*`, `core/events/types/loot/*`, `core/events/coordinator/*`, `core/shared/frame_registration.py`, `CODEBASE.md`, `ITERATION_LOG.md`.
**Expected impact:** Identify whether loot detection mutates minimap frames, registration, localization state, or event/navigation targets; only change code if a concrete side effect or unsafe coupling is found.

## [SYNC] 2026-06-03 19:45 - Hook and event scheduler localization drift diagnosis

### A. SYNC scope
**Task:** Continue diagnosing whether player localization drift during movement is caused by hook key presses, event task scheduling, or event async observer load rather than direct loot frame mutation.
**Direct files expected:** `core/events/hooks/instances/key_press.py`, `core/events/hooks/runtime.py`, `core/navigation_tasks/event_task_runner.py`, `core/navigation_tasks/event_approach/*`, `gui/dialogs/event_manager/hooks/*`, recent `logs/event_runs/*`.
**Expected impact:** Confirm whether enabled hooks without event binding are skipped, whether visible/completed hooks are one-shot, whether repeated event tasks can influence movement/localization, and whether extra runtime probes are required.

## [SYNC] 2026-06-04 14:08 - Initial localization drift diagnosis probe

### A. SYNC scope
**Task:** User reports that initial global localization is already wrong before movement, so continue diagnosis with a reproducible first-frame localization probe and lightweight runtime coordinate sampling.
**Direct files expected:** `core/localization/*`, `core/navigation_tasks/coordinate/*`, `debug/navigation_localization_probe.py`, `map_data/A/config.json`, latest `debug/minimap_samples/A/*`.
**Expected impact:** Separate event/loot runtime effects from first-frame template matching behavior, preserve production localization code path, and produce artifacts that show raw minimap mask, map match patch, saved-position patch, and top candidate scores.

### C. SYNC result
**Key finding:** Current evidence does not support loot/event runtime as the direct cause of the reported initial wrong global localization. `capture_navigation_localization_tick()` localizes before event observation, the async event observer clones frames, recent event logs show `dropped=0`, and `map_data/A/config.json` has no git diff. The latest sample reproduces the wrong/contested point offline through first-frame `NavigationCore.localize()` alone.

**Probe result:** Added `debug/navigation_localization_probe.py` and ran it on `debug/minimap_samples/A/20260604_135548_439_A_minimap.png`. Latest output directory: `debug/navigation_localization_probe/20260604_142234_20260604_135548_439_A_minimap/`. Production settings used `draw_scale=3.0`, `wall_match_close_kernel_size=3`, template shape `600x600`, full-map search `7500x7500`.

**Observed localization:** Top candidate and `NavigationCore.localize()` result are both `(4211,3272)` with confidence `0.7744859457`, `frame_origin_global=(3911,2972)`. The saved map package `current_pos=(4792.48,3630.25)` scores `-0.02080567` on the same response map. Top candidate #2 is only `0.228927`, so the algorithm has a strong first choice, but it may still be the wrong gameplay location if the expected location is known.

**Differential check:** Executed the old `HEAD:core/recognizer_optimized.py` recognizer in-memory against the same sample and same `map_data/A/config.json` recognizer parameters. Old and current recognizers produced identical masks: `wall differing pixels=0`, `match differing pixels=0`; both matched `(4211,3272)` with confidence `0.7744859457`. This rules out the recognizer split and current `frame_matcher` extraction as the cause for this sample. If previous runtime was accurate, the remaining high-probability source is upstream input/map state: capture rectangle / player-local coordinate / live screenshot content / map package mismatch.

**Code change:** Added 500ms runtime localization sampling to `core/navigation_tasks/coordinate/localization.py` and exposed the interval in `CoordinateDiagnostics`. Fixed `coordinate/log.py` to write project-root `logs/coordinate_diagnostics.log`, and bridge coordinate diagnostics into current event session logs when available. Also preserved `drawing_saved_pos/last_pos` in `core/localization/navigation_core/state.py` so the saved map position remains visible to UI/debug after runtime state initialization; this does not automatically set `current_pos` or mark localization valid. Added `navigation capture geometry` event log in `gui/modes/navigation/runtime/localization_tick.py` whenever capture rectangle or player-local position changes.

**Verification:**
- `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\modes\navigation\runtime\localization_tick.py core\localization\navigation_core\state.py core\navigation_tasks\coordinate\log.py core\navigation_tasks\coordinate\diagnostics.py core\navigation_tasks\coordinate\localization.py debug\navigation_localization_probe.py` passed.
- Probe command passed and produced `report.json`, `wall_mask.png`, `match_mask.png`, `wall_mask_scaled.png`, `matched_map_patch.png`, `saved_pos_patch.png`, and `top_candidates_sheet.png`.

**Docs updated:** `CODEBASE.md`, `architecture_docs/zh-CN/core/ARCHITECTURE.md`, and `architecture_docs/zh-CN/core/navigation_tasks/ARCHITECTURE.md` now record the diagnostic probe, latest sample result, and coordinate sample logging behavior.

**Coverage update:**
| File | Previous | Current | Reads | Note |
|------|----------|---------|-------|------|
| `core/localization/localize_pipeline.py` | (partial) | (partial) | appended | Rechecked first-frame full-map template matching path and confirmed it reproduces without event runtime. |
| `core/localization/frame_matcher.py` | (partial) | (partial) | appended | Rechecked wall template scale/search-area helpers used by the probe. |
| `core/localization/map_package.py` | (partial) | (partial) | appended | Rechecked saved `current_pos`, draw scale, and wall close kernel loading. |
| `core/localization/navigation_core/state.py` | (partial) | (partial) | appended | Preserved saved drawing position for UI/debug while keeping initial localization untrusted. |
| `core/navigation_tasks/coordinate/localization.py` | (partial) | (partial) | appended | Added compact localization sample logging. |
| `gui/modes/navigation/runtime/localization_tick.py` | (partial) | (partial) | appended | Added capture geometry log to separate wrong screenshot region from matcher behavior. |
| `debug/navigation_localization_probe.py` | PENDING | (partial) | 1 | New standalone first-frame localization probe using production config and `NavigationCore`. |

## [SYNC] 2026-06-04 20:40 - Loot player mask UI and portal duplicate diagnosis

### A. SYNC scope
**Task:** User reports latest loot localization is acceptable, but the loot player erase/mask radius is too large and must be adjustable in the frontend/event panel. Portal recognition accuracy appears lower and portal events may be repeatedly recognized/localized; diagnose whether recent portal code changes or configuration caused it.
**Direct files expected:** `core/events/types/loot/definition.py`, `core/events/types/loot/config.py`, `gui/dialogs/event_manager_dialog.py`, `core/events/types/portal/*`, `core/events/position_stabilizer/*`, `core/events/memory/*`, `map_data/A/event_config.json`, recent `logs/event_runs/*`.
**Expected impact:** Make loot player-center mask radius clearly configurable from the GUI; identify portal detector mode / threshold / dedupe configuration or code-path causes for duplicate portal tasks; update Chinese architecture docs and CODEBASE if code changes are made.

### C. SYNC result
**Key findings:** The latest runtime log `logs/event_runs/20260604_201657_742_pid24360_navigation.log` started portal detection with `mode=feature_then_template`, while the current `map_data/A/event_config.json` has `portal.detector_mode="shape_color"`. That means the reported run used an older in-memory config or the file was saved after the run. Duplicate portal tasks in that log were not identical coordinates; they stabilized around nearby positions such as `(2983,1913)` and `(3032,1980)`, roughly 70-85 map pixels apart. The old portal defaults `localization_cluster_radius=56` and `dedupe_radius=32` were therefore too small to merge that duplicate/jitter band.

**Code changes:**
- `gui/dialogs/event_manager_dialog.py`: parameter rows now support schema `help` tooltips on both label and input widget.
- `core/events/types/loot/definition.py`: `player_center_mask_enabled` and `player_center_mask_radius` now have Chinese labels and help text; radius min lowered to 4 so the user can tune down an overly large center erase.
- `core/events/types/portal/config.py` and `core/events/config_model.py`: portal default `detector_mode` changed to `shape_color`; added `minimap_nms_radius=28`; default `localization_cluster_radius` and `dedupe_radius` changed to 96.
- `core/events/types/portal/definition.py`: exposed `minimap_nms_radius`, `dedupe_radius`, localization sample/TTL/emit parameters, cooldown radius, and exit completion radius in the event manager schema.
- `core/events/types/portal/minimap_detection/conversion.py`: accepted portal hits are now locally deduped by `minimap_nms_radius` before becoming `EventDetection`, preventing near duplicate template/scale hits from entering separate localization clusters.
- `map_data/A/event_config.json`: current map portal config now uses `max_candidates=2`, `minimap_nms_radius=28`, `localization_cluster_radius=96`, and `dedupe_radius=96`.

**Verification:**
- Compile passed: `D:\ACloud\.venv\Scripts\python.exe -m py_compile gui\dialogs\event_manager_dialog.py core\events\types\loot\definition.py core\events\types\portal\config.py core\events\types\portal\definition.py core\events\types\portal\minimap_detection\conversion.py core\events\config_model.py`.
- Local NMS harness passed: two dummy portal hits 20 local pixels apart with `minimap_nms_radius=28` produce `near 1`; hits 35 pixels apart produce `far 2`.
- Config reload check passed: `portal shape_color 2 28 96 96 700`; `loot_mask True 28`.

**Docs updated:** `CODEBASE.md`, `architecture_docs/zh-CN/core/events/types/portal/ARCHITECTURE.md`, and `architecture_docs/zh-CN/core/events/types/loot/ARCHITECTURE.md`.

**Coverage update:**
| File | Previous | Current | Reads | Note |
|------|----------|---------|-------|------|
| `core/events/types/loot/definition.py` | (partial) | (partial) | appended | Confirmed player center mask radius already existed, then made GUI label/help explicit. |
| `gui/dialogs/event_manager_dialog.py` | (partial) | (partial) | appended | Confirmed schema-driven param rendering and added tooltip support. |
| `core/events/types/portal/config.py` | (partial) | (partial) | appended | Updated defaults for detector mode, local NMS, cluster radius, and memory dedupe radius. |
| `core/events/types/portal/definition.py` | (partial) | (partial) | appended | Exposed portal duplicate-control and localization parameters in the event panel schema. |
| `core/events/types/portal/minimap_detection/conversion.py` | (partial) | (partial) | appended | Added accepted-hit local NMS before EventDetection conversion. |
| `core/events/position_stabilizer/clusters.py` | (partial) | (partial) | appended | Rechecked cluster merge behavior and confirmed old 56px radius caused nearby duplicate clusters. |
| `core/events/memory/lookup.py` | (partial) | (partial) | appended | Rechecked task dedupe behavior and confirmed old 32px radius allowed nearby duplicate tasks. |
| `map_data/A/event_config.json` | (partial) | (partial) | appended | Updated current map portal duplicate-control parameters. |
| `logs/event_runs/20260604_201657_742_pid24360_navigation.log` | PENDING | (partial) | 1 | Used as runtime evidence for feature_then_template mode and duplicate portal task distances. |

## [PLAN] 2026-06-08 - Event manager compact UI and navigation compact mode modularization

### A. Scope declaration before reading
**Task:** User wants a smaller, cleaner UI for testing events and navigation, with code organized as independent modular UI components for future optimization. Do not run the app yet; first produce a codebase-informed plan.
**Target files expected:** `gui/dialogs/event_manager_dialog.py`, `gui/dialogs/event_manager/*`, `gui/modes/navigation/ui/layout.py`, `gui/modes/navigation/widget.py`, `gui/modes/navigation/events/dialog_lifecycle.py`, `gui/modes/navigation/composition/lifecycles.py`, `architecture_docs/zh-CN/gui/dialogs/ARCHITECTURE.md`, `architecture_docs/zh-CN/gui/modes/navigation/ARCHITECTURE.md`.
**Expected impact:** Decide module boundaries for event manager compact/full modes and navigation compact layout before implementation; keep current full parameter editor intact while adding a small testing surface.

### C. Planning findings
**Key findings:** `EventManagerDialog` is already driven by event schemas and command signals, but its shell, event selector, parameter form, task table, footer actions, and hook panel are still assembled in one dialog class. `NavigationModeWidget` has been reduced to a composition root, but `gui/modes/navigation/ui/layout.py` still creates every navigation control in one horizontal toolbar and stores the map view as the main stretch widget. The current UI pain comes more from layout density and dialog size than from core algorithm coupling.

**Stable integration points to preserve:** `NavigationEventDialogLifecycle` and `ManualEventTestController` currently depend on `dialog.test_portal_button`; `connect_navigation_signals()` depends on stable `owner.btn_*`, `owner.params_button`, `owner.event_button`, `owner.sample_window_button`, and `owner.save_minimap_sample_button` attributes. The compact UI refactor should keep these attributes while moving construction and mode switching into focused UI modules.

**Planned module direction:** split event manager UI under `gui/dialogs/event_manager/` into dialog shell, shared state/context, schema form, task status view, footer actions, and compact/full page composition; split navigation UI under `gui/modes/navigation/ui/` into map view factory, primary toolbar, route-edit toolbar, secondary tools, status strip, and compact-mode controller. Keep existing public entry points (`EventManagerDialog`, `build_navigation_ui(owner)`, `connect_navigation_signals(owner)`) during the first implementation pass.

**Risk notes:** compact/full toggling must not create duplicate test buttons or reconnect signals repeatedly; event config mutation is in-place and should remain so for dict-backed event configs; route edit buttons must remain wired to `RoutePanelController`; map view size changes should affect presentation only and not alter capture geometry or localization parameters.

**Verification plan after implementation:** run `py_compile` on changed GUI modules first, then start the app only after user approval for runtime verification. Chinese architecture docs should be updated after code changes; English docs are not required for this UI pass unless `CODEBASE.md` must be synchronized.

**Coverage update:**
| File | Previous | Current | Reads | Note |
|------|----------|---------|-------|------|
| `gui/dialogs/event_manager_dialog.py` | (partial) | (partial) | appended | Confirmed schema-driven event config rendering, task table, command signals, hook panel integration, and fixed `test_portal_button` dependency. |
| `gui/dialogs/event_manager/hooks/panel.py` | (partial) | (partial) | appended | Confirmed hook table is already independent enough to keep as a full-mode tab or compact summary source. |
| `gui/modes/navigation/ui/layout.py` | (partial) | (partial) | appended | Confirmed one dense toolbar plus map view/status/route panel construction; suitable for UI package split. |
| `gui/modes/navigation/ui/signals.py` | (partial) | (partial) | appended | Confirmed signal wiring depends on stable owner button attributes, so compact modules must preserve those names. |
| `gui/modes/navigation/widget.py` | (partial) | (partial) | appended | Confirmed widget remains composition root and public wrapper surface, not the right place for compact layout logic. |
| `gui/modes/navigation/events/dialog_lifecycle.py` | (partial) | (partial) | appended | Confirmed event dialog lifecycle owns create/toggle/refresh and manual portal test button syncing. |
| `gui/modes/navigation/composition/lifecycles.py` | (partial) | (partial) | appended | Confirmed runtime initialization creates event dialog and manual test controller after UI construction. |
| `architecture_docs/zh-CN/gui/dialogs/ARCHITECTURE.md` | (partial) | (partial) | appended | Rechecked current dialog guidance and noted EventManager can become the compact/schema-form template. |
| `architecture_docs/zh-CN/gui/modes/navigation/ARCHITECTURE.md` | (partial) | (partial) | appended | Rechecked navigation UI boundaries, current public surface, and remaining optimization candidates. |

## [SYNC] 2026-06-08 - Event manager and navigation compact UI implementation

### A. SYNC scope
**Task:** Implement the approved compact/small-window UI plan. Split event manager and navigation UI construction into feature modules, keep stable public attributes/signals, add compact/full mode toggles, and update Chinese architecture docs after implementation.
**Direct files expected:** `gui/dialogs/event_manager_dialog.py`, new `gui/dialogs/event_manager/*` view modules, `gui/modes/navigation/ui/layout.py`, new `gui/modes/navigation/ui/*` component modules, `gui/modes/navigation/ui/signals.py`, `architecture_docs/zh-CN/gui/dialogs/ARCHITECTURE.md`, `architecture_docs/zh-CN/gui/modes/navigation/ARCHITECTURE.md`.
**Expected impact:** Presentation-only refactor. Core algorithms, event detection, capture geometry, navigation runtime, hook runtime, and map/session config should not change. Existing callers should continue to use `EventManagerDialog`, `build_navigation_ui(owner)`, and `connect_navigation_signals(owner)`.

### C. SYNC result
**Code changes:**
- `gui/dialogs/event_manager_dialog.py` is now a compatibility import shell; the real dialog moved to `gui/dialogs/event_manager/dialog.py`.
- Added `gui/dialogs/event_manager/layout.py`, `schema_form.py`, and `task_table.py`. The dialog now has a default compact page and a full tabs page. Both share the same event selector, global enable switch, command footer, config mutation path, and stable `test_portal_button` attribute.
- Compact event manager mode defaults to about `480x620`; full mode restores about `1040x780`. Compact mode shows event overview, common parameters, compact task state, and the existing save/refresh/test/reset actions.
- `gui/modes/navigation/ui/layout.py` is now a composition entry only. Toolbar construction moved to `components/toolbars.py`, map view creation to `components/map_view.py`, status label creation to `components/status.py`, and compact/full presentation policy to `compact/controller.py`.
- Navigation compact mode is enabled by default. Route editing tools are folded behind `路线工具`; map view maximum height is limited in compact mode and restored in full mode. Existing button attributes are still attached to `NavigationModeWidget`.

**Verification:**
- `py_compile` passed for all changed/new event-manager and navigation-UI modules.
- Import smoke check passed: old `gui.dialogs.event_manager_dialog.EventManagerDialog`, new `gui.dialogs.event_manager.EventManagerDialog`, `build_navigation_ui`, and `connect_navigation_signals` import successfully.
- Offscreen construction check passed for `EventManagerDialog`: compact/full mode toggles construct and preserve `test_portal_button` and `compact_task_table`.
- Offscreen fake-owner construction check passed for `build_navigation_ui(owner)`: all old button/view/status/route attributes exist; compact mode is true by default and route tools are hidden.

**Docs updated:** `architecture_docs/zh-CN/gui/dialogs/ARCHITECTURE.md` and `architecture_docs/zh-CN/gui/modes/navigation/ARCHITECTURE.md`. English docs intentionally not updated per user preference.

**Coverage update:**
| File | Previous | Current | Reads | Note |
|------|----------|---------|-------|------|
| `gui/dialogs/event_manager_dialog.py` | (partial) | (partial) | appended | Converted to compatibility shell while preserving old imports. |
| `gui/dialogs/event_manager/dialog.py` | PENDING | (partial) | 1 | New real event manager dialog shell with compact/full mode and stable command signals. |
| `gui/dialogs/event_manager/layout.py` | PENDING | (partial) | 1 | New event-manager UI composition module for header, compact page, full tabs, and footer. |
| `gui/dialogs/event_manager/schema_form.py` | PENDING | (partial) | 1 | New schema-to-widget factory and full/compact editor sync helper. |
| `gui/dialogs/event_manager/task_table.py` | PENDING | (partial) | 1 | New full/compact event task table renderer. |
| `gui/modes/navigation/ui/layout.py` | (partial) | (partial) | appended | Reduced to navigation UI composition entry with compact controller setup. |
| `gui/modes/navigation/ui/signals.py` | (partial) | (partial) | appended | Added compact-layout and route-tools button wiring. |
| `gui/modes/navigation/ui/components/toolbars.py` | PENDING | (partial) | 1 | New navigation toolbar builders preserving old owner button attributes. |
| `gui/modes/navigation/ui/components/map_view.py` | PENDING | (partial) | 1 | New map scene/view factory preserving scene item fields. |
| `gui/modes/navigation/ui/components/status.py` | PENDING | (partial) | 1 | New status-label factory. |
| `gui/modes/navigation/ui/compact/controller.py` | PENDING | (partial) | 1 | New presentation-only compact/full layout controller. |
| `architecture_docs/zh-CN/gui/dialogs/ARCHITECTURE.md` | (partial) | (partial) | appended | Updated EventManager modularization and compact/full mode rules. |
| `architecture_docs/zh-CN/gui/modes/navigation/ARCHITECTURE.md` | (partial) | (partial) | appended | Updated navigation UI component boundaries and compact mode behavior. |

## [SYNC] 2026-06-08 - Continue compact GUI development

### A. SYNC scope
**Task:** Continue GUI development after the first compact navigation/event-manager pass. Inspect remaining GUI surfaces that can still make the app cumbersome during gameplay testing, then implement the next low-risk modular UI improvement while preserving existing behaviour.
**Direct files expected:** `gui/main_window.py`, `gui/dialogs/nav_params_dialog.py`, `gui/dialogs/nav_params/*`, `gui/modes/navigation/ui/*`, `architecture_docs/zh-CN/gui/dialogs/ARCHITECTURE.md`, `architecture_docs/zh-CN/gui/modes/navigation/ARCHITECTURE.md`.
**Expected impact:** Presentation/modularization only unless inspection finds a direct blocker. Core algorithms, event runtime, capture geometry, and navigation task execution should remain unchanged.

### C. SYNC result
**Inspection finding:** The main window had no hard minimum size but started at `1400x900`, which is awkward on a single-screen gameplay setup. `NavParametersDialog` still put each tab's full content directly into a tab page, so parameter contents could force a large dialog instead of scrolling.

**Code changes:**
- Added `gui/dialogs/nav_params/layout_helpers.py` with `create_scrollable_tab()` and `apply_nav_params_window_mode()`.
- Updated `NavParametersDialog` so all six tabs are scrollable. The dialog now defaults to a compact `520x640` size and has a footer `完整模式/小窗模式` toggle that only changes sizing policy.
- Updated `MainWindow` default geometry from `1400x900` to `1100x760`, keeping manual resizing available.
- Updated `gui/modes/navigation/events/panel_adapter.py` to connect event-dialog signals once instead of disconnecting potentially unconnected slots. This removed PySide `RuntimeWarning` noise during offscreen window construction/close.

**Verification:**
- `py_compile` passed for `gui/main_window.py`, `gui/dialogs/nav_params_dialog.py`, `gui/dialogs/nav_params/layout_helpers.py`, and `gui/modes/navigation/events/panel_adapter.py`.
- Offscreen `NavParametersDialog` construction passed: six `QScrollArea` instances exist, compact toggle works, final compact size is `520x640`.
- Offscreen `MainWindow` construction/close passed: startup geometry is `1100x760`, navigation compact mode is true, and the previous event signal disconnect warnings are gone.

**Docs updated:** `architecture_docs/zh-CN/gui/dialogs/ARCHITECTURE.md` and `architecture_docs/zh-CN/gui/ARCHITECTURE.md`. English docs intentionally not updated.

**Coverage update:**
| File | Previous | Current | Reads | Note |
|------|----------|---------|-------|------|
| `gui/main_window.py` | (partial) | (partial) | appended | Reduced default startup geometry for single-screen testing. |
| `gui/dialogs/nav_params_dialog.py` | (partial) | (partial) | appended | Added scrollable tabs and compact/full sizing toggle while preserving config binding. |
| `gui/dialogs/nav_params/layout_helpers.py` | PENDING | (partial) | 1 | New nav parameter layout helper for scrollable tabs and sizing policy. |
| `gui/modes/navigation/events/panel_adapter.py` | (partial) | (partial) | appended | Removed noisy disconnect-first signal wiring by tracking connected dialog slots. |
| `architecture_docs/zh-CN/gui/dialogs/ARCHITECTURE.md` | (partial) | (partial) | appended | Updated NavParametersDialog modularization and small-window behavior. |
| `architecture_docs/zh-CN/gui/ARCHITECTURE.md` | (partial) | (partial) | appended | Recorded the smaller default main-window geometry. |

## [SYNC] 2026-06-08 - Nav parameters section builder extraction

### A. SYNC scope
**Task:** Continue GUI modularization by extracting the heaviest `NavParametersDialog` UI section construction into `gui/dialogs/nav_params/` modules. Preserve existing widget attribute names, config bindings, signals, labels, tooltips, and compact/full sizing behavior.
**Direct files expected:** `gui/dialogs/nav_params_dialog.py`, new or updated `gui/dialogs/nav_params/*`, `architecture_docs/zh-CN/gui/dialogs/ARCHITECTURE.md`, `ITERATION_LOG.md`.
**Expected impact:** Presentation-only refactor. `NavConfig` structure, `config_binding.py`, runtime config application, event runtime, localization, and navigation task behavior should not change.

### C. SYNC result
**Code changes:**
- Rewrote `gui/dialogs/nav_params_dialog.py` as a shell. It now owns only dialog lifecycle, Qt signals, `NavConfig` updates, click-radius estimation, compact/full size switching, and config write-back.
- Added `gui/dialogs/nav_params/sections.py`. It builds all six parameter tabs, section widgets, explanatory labels/tooltips, and the footer action bar while preserving every existing widget attribute name used by `field_specs.py` and `config_binding.py`.
- Kept `gui/dialogs/nav_params/layout_helpers.py` as the scrollable-tab and size-policy helper.

**Verification:**
- `py_compile` passed for `nav_params_dialog.py`, `nav_params/sections.py`, `nav_params/layout_helpers.py`, `nav_params/config_binding.py`, and `nav_params/field_specs.py`.
- Offscreen construction check passed: all `BOUND_FIELD_SPECS` widget attributes exist, `nav_tabs.count()==6`, six `QScrollArea` instances exist, and default compact size remains `520x640`.
- Offscreen `set_config_to_ui(NavConfig())` check passed: status becomes `参数已加载`, FPS writes as `10`, compact/full toggle returns to compact with button text `完整模式`.

**Docs updated:** `architecture_docs/zh-CN/gui/dialogs/ARCHITECTURE.md`.

**Coverage update:**
| File | Previous | Current | Reads | Note |
|------|----------|---------|-------|------|
| `gui/dialogs/nav_params_dialog.py` | (partial) | (partial) | appended | Converted to shell retaining signals/config update/write-back behaviour. |
| `gui/dialogs/nav_params/sections.py` | PENDING | (partial) | 1 | New section builders for all nav parameter tabs and action bar. |
| `gui/dialogs/nav_params/layout_helpers.py` | (partial) | (partial) | appended | Reused for scrollable tabs and compact/full sizing policy. |
| `gui/dialogs/nav_params/config_binding.py` | (partial) | (partial) | appended | Revalidated after section extraction; binding still resolves all widgets by stable attribute name. |
| `gui/dialogs/nav_params/field_specs.py` | (partial) | (partial) | appended | Revalidated `BOUND_FIELD_SPECS` against constructed dialog. |
| `architecture_docs/zh-CN/gui/dialogs/ARCHITECTURE.md` | (partial) | (partial) | appended | Updated NavParametersDialog section-builder architecture and remaining candidates. |

## [SYNC] 2026-06-08 - Mapping control panel scroll container

### A. SYNC scope
**Task:** Continue compact GUI work by making the mapping page control panel usable in smaller windows. Add a scroll container around the existing mapping controls while preserving all widget attributes, signal wiring, and mapping runtime behaviour.
**Direct files expected:** `gui/modes/mapping/ui/layout.py`, `architecture_docs/zh-CN/gui/modes/ARCHITECTURE.md`, `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`, `ITERATION_LOG.md`.
**Expected impact:** Presentation-only refactor. Mapping capture, recognition, stitching, config restore/save, runtime lifecycle, and parameter binding should not change.

### C. SYNC result
**Code changes:**
- Updated `gui/modes/mapping/ui/layout.py`: `create_mapping_control_panel()` now returns a `QScrollArea` and delegates existing control creation to `create_mapping_control_content()`.
- Added `owner.control_scroll_area` for explicit access/debug. All existing owner widget attributes and signal connections remain created inside the content panel.

**Verification:**
- `py_compile` passed for `gui/modes/mapping/ui/layout.py`, `gui/modes/mapping_widget.py`, and `gui/main_window.py`.
- Offscreen `MainWindow` construction/close passed: startup geometry remains `1100x760`, `mapping_widget.control_scroll_area` is a `QScrollArea`, and navigation compact mode remains enabled.

**Docs updated:** `architecture_docs/zh-CN/gui/modes/ARCHITECTURE.md` and `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md`.

**Coverage update:**
| File | Previous | Current | Reads | Note |
|------|----------|---------|-------|------|
| `gui/modes/mapping/ui/layout.py` | (partial) | (partial) | appended | Added scrollable control panel wrapper while preserving control content and owner field names. |
| `gui/modes/mapping_widget.py` | (partial) | (partial) | appended | Revalidated construction through MainWindow after mapping UI wrapper change. |
| `gui/main_window.py` | (partial) | (partial) | appended | Revalidated small startup geometry and both mode construction after mapping scroll change. |
| `architecture_docs/zh-CN/gui/modes/ARCHITECTURE.md` | (partial) | (partial) | appended | Updated Mapping UI role to include scroll wrapper. |
| `architecture_docs/zh-CN/gui/GUI_FULL_FILE_OPTIMIZATION_PLAN.md` | (partial) | (partial) | appended | Updated mapping UI seam description and done checklist. |

## [SYNC] 2026-06-08 - Advanced settings dialog section extraction

### A. SYNC scope
**Task:** Continue GUI modularization by extracting `AdvancedSettingsDialog` tab/section UI construction into its `gui/dialogs/advanced_settings/` package. Preserve existing widget attribute names, button signals, presets/file IO helpers, and parent parameter application behavior.
**Direct files expected:** `gui/dialogs/advanced_settings_dialog.py`, new or updated `gui/dialogs/advanced_settings/*`, `architecture_docs/zh-CN/gui/dialogs/ARCHITECTURE.md`, `ITERATION_LOG.md`.
**Expected impact:** Presentation-only refactor unless a harmless signal/construct warning is found. Advanced settings JSON IO, presets, params adapter, recognizer/stitcher application, and config save/load semantics should not change.

### C. SYNC result
**Code changes:**
- Rewrote `gui/dialogs/advanced_settings_dialog.py` as a shell. It now owns dialog lifecycle, `apply_params_requested`, direct-apply compatibility, current params state, and save/load/preset behavior.
- Added `gui/dialogs/advanced_settings/tabs.py` with four scrollable tabs: image preprocessing, feature extraction, parameter management, and stitcher algorithm settings. It also builds the footer action buttons.
- Preserved all widget attribute names consumed by `params_adapter.py` and preset values.

**Verification:**
- `py_compile` passed for `advanced_settings_dialog.py`, `advanced_settings/tabs.py`, `params_adapter.py`, `file_io.py`, and `presets.py`.
- Offscreen construction check passed using a QWidget parent: required widget attributes exist, `tab_widget.count()==4`, four `QScrollArea` instances exist, and `collect_params_from_widgets()` returns 26 parameters.
- Preset application check passed using the combo item's actual text: high-contrast preset updates `clahe_clip` to `3.0` and `deepen_factor` to `1.5`. The PowerShell terminal displays Chinese preset text with encoding noise, but the Qt value path is correct.

**Docs updated:** `architecture_docs/zh-CN/gui/dialogs/ARCHITECTURE.md`.

**Coverage update:**
| File | Previous | Current | Reads | Note |
|------|----------|---------|-------|------|
| `gui/dialogs/advanced_settings_dialog.py` | (partial) | (partial) | appended | Converted to shell retaining apply/save/load/preset behavior and direct-apply compatibility. |
| `gui/dialogs/advanced_settings/tabs.py` | PENDING | (partial) | 1 | New scrollable tab/action UI builder preserving widget attributes. |
| `gui/dialogs/advanced_settings/params_adapter.py` | (partial) | (partial) | appended | Revalidated against new tabs; all required widget attrs still exist. |
| `gui/dialogs/advanced_settings/file_io.py` | (partial) | (partial) | appended | Rechecked unchanged save/load snapshot path used by shell. |
| `gui/dialogs/advanced_settings/presets.py` | (partial) | (partial) | appended | Rechecked preset names/value mapping used by tabs and adapter. |
| `architecture_docs/zh-CN/gui/dialogs/ARCHITECTURE.md` | (partial) | (partial) | appended | Updated advanced settings shell/tabs architecture and remaining direct-apply risk. |

## [SYNC] 2026-06-08 - Color picker dialog UI/preview boundary extraction

### A. SYNC scope
**Task:** Continue dialog modularization with `ColorPickerDialog`. Read the current dialog and helper modules, then extract a low-risk UI/preview boundary without changing HSV range calculation, mask generation semantics, accepted result shape, or optional debug output behavior.
**Direct files expected:** `gui/dialogs/color_picker_dialog.py`, new or updated `gui/dialogs/color_picker/*`, `architecture_docs/zh-CN/gui/dialogs/ARCHITECTURE.md`, `ITERATION_LOG.md`.
**Expected impact:** Presentation-only refactor unless a pure rendering helper extraction is obvious. Color sampling math, recognizer params, preview mask output, and debug artifact gating should remain unchanged.

### C. SYNC result
**Code changes:**
- Added `gui/dialogs/color_picker/layout.py` to build the help text, mode buttons, original-image panel, preview panel, result text, and footer buttons.
- Reduced `ColorPickerDialog.setup_ui()` to `build_color_picker_ui(self)`. The dialog still owns screenshot preprocessing, point sampling, HSV range calculation, preview refresh, reset, zoom state, and accepted result shape.
- Fixed the new layout module's relative import to `...widgets.clickable_label`.

**Verification:**
- `py_compile` passed for `color_picker_dialog.py`, `color_picker/layout.py`, `image_renderer.py`, `preview.py`, `debug_output.py`, and `hsv_ranges.py`.
- Offscreen construction with a dummy 64x64 BGR image passed: all expected controls exist, one `QScrollArea` exists, initial mode is `wall`, OK starts disabled, and zoom label is `100%`.
- Offscreen calculation path passed: simulated one wall click, `calculate_hsv_ranges()` produces a non-empty `wall_hsv` result, enables OK, and preserves saturation-filter recommendation behavior.

**Docs updated:** `architecture_docs/zh-CN/gui/dialogs/ARCHITECTURE.md`.

**Coverage update:**
| File | Previous | Current | Reads | Note |
|------|----------|---------|-------|------|
| `gui/dialogs/color_picker_dialog.py` | (partial) | (partial) | appended | Reduced setup_ui to layout delegation while preserving interaction/HSV/preview behavior. |
| `gui/dialogs/color_picker/layout.py` | PENDING | (partial) | 1 | New UI layout builder for color picker controls and panels. |
| `gui/dialogs/color_picker/image_renderer.py` | (partial) | (partial) | appended | Revalidated render path used by dialog after layout extraction. |
| `gui/dialogs/color_picker/preview.py` | (partial) | (partial) | appended | Revalidated preview mask path remains unchanged. |
| `gui/dialogs/color_picker/debug_output.py` | (partial) | (partial) | appended | Confirmed debug output remains gated by existing flag. |
| `gui/dialogs/color_picker/hsv_ranges.py` | (partial) | (partial) | appended | Revalidated HSV sampling/calculation path through simulated click. |
| `architecture_docs/zh-CN/gui/dialogs/ARCHITECTURE.md` | (partial) | (partial) | appended | Updated color picker layout/preview/helper architecture. |
## [P0] 2026-09-03 - Establish perception engine checkpoints

### A. Scope declaration

**Task:** Reframe the modularization around the missing game-agnostic perception engine, create a persistent recovery document, and write the ordered implementation plan before further runtime changes.

**Direct files:** `docs/PERCEPTION_ENGINE_CHECKPOINT.md`, `docs/plans/2026-09-03-perception-engine-implementation-plan.md`, `ITERATION_LOG.md`.

**Expected impact:** Documentation only. No existing Portal, Loot, minimap, navigation, input, or GUI runtime behavior should change in this round.

### C. Findings

- (verified) `core/perception/models.py`, `profiles.py`, `registry.py`, `color.py`, `template.py`, and `pipeline.py` provide a useful foundation.
- (verified) `PerceptionPipeline` currently combines detector creation, execution, confidence filtering, and spatial fusion in one module; it is not yet the requested named engine.
- (verified) Shape, Feature, and OCR are registered as unavailable extension points, not complete adapters.
- (verified) `gui/dialogs/perception/dialog.py` is a screenshot workbench, but it is not yet routed through an engine facade.
- (partial) Full test discovery has unrelated legacy import-path failures; the release audit will classify them after the new engine work.

### Coverage update

| File | Previous | Current | Reads | Note |
|---|---|---|---:|---|
| `docs/PERCEPTION_ENGINE_CHECKPOINT.md` | PENDING | partial | 1 | New recovery document with baseline, architecture contract, ordered queue, and audit notes. |
| `docs/plans/2026-09-03-perception-engine-implementation-plan.md` | PENDING | partial | 1 | Task-by-task implementation plan with test and commit gates. |
| `core/perception/pipeline.py` | partial | partial | 1 | Confirmed as compatibility pipeline pending decomposition behind a named engine. |
| `core/perception/registry.py` | partial | partial | 1 | Confirmed as algorithm catalog seam; provider registry still pending. |
| `gui/dialogs/perception/dialog.py` | partial | partial | 1 | Confirmed as UI test bench; direct algorithm construction must move behind engine public API. |

### Next task

Implement P1: `PerceptionEngine` facade and its contract tests. Write the failing test first, then add the smallest compatibility-backed implementation.

## [P1] 2026-09-03 - Add the perception engine facade

### A. Scope declaration

**Task:** Add a named, GUI-free `PerceptionEngine` entry point that registers and resolves profiles by game/scene/target and delegates one detection call to the current compatibility pipeline.

**Direct files:** `core/perception/engine.py`, `core/perception/__init__.py`, `tests/test_perception_engine.py`.

**Expected impact:** New core API only. Existing `PerceptionPipeline`, Portal/Loot, minimap, navigation, input, and GUI behavior must remain unchanged until the facade tests pass.

### B. Read target

- `core/perception/pipeline.py`: current detector creation, confidence filtering, and fusion implementation retained behind the facade.
- `core/perception/profiles.py`: immutable game/scene/target profile and copy contract.
- `core/perception/registry.py`: algorithm catalog and factory seam.

### C. Findings pending implementation

- The engine must own profile lookup and validation rather than expose detector classes to callers.
- Profile registration must store a defensive copy so later GUI edits cannot mutate the engine's active profile.
- Missing hierarchy keys should fail explicitly with `KeyError`; direct profile detection should preserve the pipeline's result and error behavior.

### Coverage update

| File | Previous | Current | Reads | Note |
|---|---|---|---:|---|
| `core/perception/engine.py` | PENDING | PENDING | 0 | New facade; test contract before implementation. |
| `core/perception/__init__.py` | partial | partial | 1 | Public export will add `PerceptionEngine`. |
| `tests/test_perception_engine.py` | PENDING | PENDING | 0 | New contract tests to be written first. |

### Next step

Create the failing P1 tests and record the initial failure before adding any implementation.

### C. P1 result

- Initial test result: failed as expected because `PerceptionEngine` was not exported from `core.perception`.
- Implementation: added `core/perception/engine.py` and exported `PerceptionEngine` from `core/perception/__init__.py`.
- Behavior: profile registration, defensive resolution, duplicate rejection, explicit missing-profile errors, and target-level detection are covered.
- Verification: `tests.test_perception_engine` passed 3/3; `compileall -q core/perception` passed.

### Coverage update

| File | Previous | Current | Reads | Note |
|---|---|---|---:|---|
| `core/perception/engine.py` | PENDING | partial | 1 | New facade with profile catalog and target-level detection contract. |
| `core/perception/__init__.py` | partial | partial | 1 | Exports `PerceptionEngine` without changing existing exports. |
| `tests/test_perception_engine.py` | PENDING | partial | 1 | Three contract tests cover detect, hierarchy lookup, defensive copy, and errors. |

### Next task

Start P2 by writing failing tests for separate detector runner, fusion, confirmation, and selection stages. Keep `PerceptionPipeline` as a compatibility shell while the engine adopts the new stages.

## [P2] 2026-09-03 - Split perception decision stages

### A. Scope declaration

**Task:** Add independent detector runner, candidate fusion, multi-frame confirmation, and candidate selection modules; update `PerceptionPipeline` to compose them without changing legacy one-frame behavior.

**Direct files:** `core/perception/stages/runner.py`, `fusion.py`, `confirmation.py`, `selection.py`, `core/perception/pipeline.py`, `core/perception/models.py`, `tests/test_perception_stages.py`, and affected perception tests.

**Expected impact:** Core perception execution only. No GUI, input, navigation, Portal, Loot, or minimap code should change in this task.

### B. Read target

- `core/perception/pipeline.py`: current inline execution, filtering, fusion, and error behavior.
- `core/perception/models.py`: stable `TargetDetection` and `PerceptionRunResult` data contracts.
- `core/perception/profiles.py`: `confirmation_frames`, `selection_strategy`, and `metadata.merge_radius` configuration already exist.

### C. Findings pending implementation

- Stage interfaces must be data-only and independently testable.
- `PerceptionRunResult` needs additive `selected` and `confirmed` fields so old callers reading `detections`, `by_algorithm`, and `errors` remain source-compatible.
- Confirmation state must be keyed by target profile and match candidates by target type, coordinate space, and spatial distance.

### Coverage update

| File | Previous | Current | Reads | Note |
|---|---|---|---:|---|
| `core/perception/stages/runner.py` | PENDING | PENDING | 0 | New detector execution stage. |
| `core/perception/stages/fusion.py` | PENDING | PENDING | 0 | New spatial candidate fusion stage. |
| `core/perception/stages/confirmation.py` | PENDING | PENDING | 0 | New multi-frame stability stage. |
| `core/perception/stages/selection.py` | PENDING | PENDING | 0 | New candidate selection policy stage. |
| `core/perception/pipeline.py` | partial | partial | 1 | Compatibility shell to compose stages. |
| `core/perception/models.py` | partial | partial | 1 | Additive run-result fields only. |
| `tests/test_perception_stages.py` | PENDING | PENDING | 0 | Failing stage contract tests to be written first. |

### Next step

Create the failing P2 stage tests and record the missing-module failure before implementation.
## [P2 review] 2026-09-03

### A. 本轮目标（阅读前声明）

**目标文件：**
- `core/perception/stages/runner.py`：确认算法实例隔离、结果契约与异常收集是否符合通用引擎边界。
- `core/perception/stages/fusion.py`：确认跨算法候选融合仅依据通用几何/置信度信息，不掺入游戏规则。
- `core/perception/stages/confirmation.py`：确认跨帧确认状态不会污染不同游戏、场景或目标。

**本轮要验证：** P2 的运行、融合、确认三段能独立组合；旧 `PerceptionPipeline` 兼容层没有把决策逻辑重新耦合进去；待确认的候选不会被误作为可执行结果。
### C. 本轮发现

**关键发现：** (verified) `DetectorRunner.run` 给每一个算法实例独立创建 detector、收集其输出，并把实例级异常转换为 `errors[instance_id]`；一次算法失败不会丢弃其它算法结果。`fuse_candidates` 只在 `target_type` 与 `coordinate_space` 一致且中心距离不大于半径时合并。`ConfirmationTracker.observe` 用调用方传入的 profile key 隔离轨迹，并在确认帧数大于 1 时只返回稳定轨迹。

**修订的旧结论：** 原先把 P2 理解为“所有候选经过固定全局确认后再输出”；现确认它是按 profile key 维护的短期确认状态，且每个候选有独立计数，能同时支持多个可见目标。

**新疑问：** `DetectorRunner.run` 当前信任 detector 返回的 `target_type`；需要在下一轮核查是否应该拒绝与 profile 目标不同的检测结果，避免错误配置跨目标污染。还需审查选择器与总装配层怎样处理“部分候选已确认”的情形。

**覆盖进度更新：**

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|---|---|---|---:|---|
| `core/perception/stages/runner.py` | 浅读 | 深度完整 | 1 | 验证了实例参数复制、异常隔离和输出类型检查。 |
| `core/perception/stages/fusion.py` | 浅读 | 深度完整 | 1 | 验证了同类型同坐标空间的贪心半径融合和证据保留。 |
| `core/perception/stages/confirmation.py` | 浅读 | 深度完整 | 1 | 验证了按 profile key 的稳定跟踪、空帧清除和单帧快捷路径。 |

**下一轮计划：** 阅读 `selection.py`、`pipeline.py`、`engine.py`，核实 P2 的装配边界、兼容层和未知策略错误契约。
## [P2 assembly review] 2026-09-03

### A. 本轮目标（阅读前声明）

**目标文件：**
- `core/perception/stages/selection.py`：确认选择规则是可配置的通用策略，不会触发点击或混入工作流语义。
- `core/perception/pipeline.py`：确认旧入口只做阶段编排与向后兼容，不重新实现 detector、融合或确认算法。
- `core/perception/engine.py`：确认公共引擎 API 只提供识别与 profile 管理，且以安全的 profile key 隔离确认状态。

**本轮要验证：** 选择、确认和结果组装对于“多目标、部分确认、未知策略、空结果、单算法错误”都有明确且可测试的行为；前端以后可以完全只依赖 `PerceptionEngine`。
### C. 本轮发现

**关键发现：** (verified) `PerceptionPipeline` 已只负责顺序编排：运行、置信度阈值、通用几何融合、按 `(game_id, scene_id, target_type)` 的时间确认、再选择一个候选。`select_candidate` 不产生输入副作用；`first` 保留上游顺序，`nearest` 有参考点时按距离，否则回退置信度，未知策略会明确抛出 `ValueError`。`PerceptionEngine` 校验公共输入类型、用深拷贝注册/返回 profile，并保持 GUI/输入/工作流依赖在外部。

**修订的旧结论：** 原先担心旧 `PerceptionPipeline` 仍重复实现融合与算法执行；现确认其具体实现已迁出至 stage，并且旧 `_fuse_candidates` 只是兼容包装。

**新疑问：** 替换一个已注册 profile 时，旧 profile 的 `ConfirmationTracker` 轨迹仍可能保留到新参数的第一帧；应在 `PerceptionEngine.register_profile(..., replace=True)` 成功替换后重置该 key 的确认状态。算法输出的 `target_type` 目前也未和 profile 做一致性校验，需由模型契约或 runner 明确处理。

**覆盖进度更新：**

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|---|---|---|---:|---|
| `core/perception/stages/selection.py` | 浅读 | 深度完整 | 1 | 验证了纯选择、nearest 回退和未知策略的失败契约。 |
| `core/perception/pipeline.py` | 浅读 | 深度完整 | 1 | 验证了 stage 编排、阈值过滤、profile-key 确认和兼容包装。 |
| `core/perception/engine.py` | 浅读 | 深度完整 | 1 | 验证了框架边界、输入检查、注册表防御拷贝及 key 约束。 |

**下一轮计划：** 阅读 P2 测试、结果模型、profile 模型；先以测试固定“替换 profile 清除确认状态”和“错误目标类型不能越过 profile 边界”，再以最小修改完成 P2。
## [P2 contract tests] 2026-09-03

### A. 本轮目标（阅读前声明）

**目标文件：**
- `tests/test_perception_stages.py`：确认现有 stage 行为覆盖了融合、确认、选择、错误隔离，并定义最小新增回归测试。
- `core/perception/models.py`：确认 `PerceptionRunResult` 及 `TargetDetection` 的不变量可承载确认/选择状态。
- `core/perception/profiles.py`：确认 target profile 是否在配置层校验选择策略和算法/目标契约。

**本轮要验证：** 先写失败测试，规定 profile 替换必须清空时间确认状态；并决定 detector 的 `target_type` 错配是在 runner 拒绝还是允许跨目标结果的唯一入口。
### C. 本轮发现

**关键发现：** (verified) `TargetDetection` 已强制非空目标名、二维中心与 0..1 置信度；`PerceptionRunResult` 能无损表达候选、按实例输出、错误、已选择结果、确认状态和每轨迹帧数。`TargetProfile` 只验证层级 ID、置信度、确认帧和实例 ID 唯一性，尚未验证选择策略。现有 stage 测试覆盖基本的异常隔离、融合、稳定确认和三种选择方式，但没有 profile 替换或目标类型错配的回归。

**修订的旧结论：** 原先把未知选择策略当作 pipeline 运行期才能发现的错误；现确认可以且应该在 `TargetProfile` 创建/加载时校验，从而让前端保存无效配置前就得到反馈。

**决定：** 统一算法实例一旦挂到 `TargetProfile(target_type=T)`，输出必须也为 `T`；这是 profile 作为“一个可操作目标”的边界。未来多类检测器要通过多个目标 profile 或上游 target selector 拆分，而不允许单次运行把其它目标混进结果。runner 会将错配作为该实例的受控错误。`selection_strategy` 只接受 `confidence`、`first`、`nearest`，并在 profile 构造时标准化小写。

**覆盖进度更新：**

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|---|---|---|---:|---|
| `tests/test_perception_stages.py` | 浅读 | 深度完整 | 1 | 识别了 P2 已覆盖行为和缺失的边界回归。 |
| `core/perception/models.py` | 浅读 | 深度完整 | 1 | 验证结果 DTO 的字段约束和确认/选择承载能力。 |
| `core/perception/profiles.py` | 浅读 | 深度完整 | 1 | 验证 profile 复制/序列化与缺失的选择策略校验。 |

**下一轮计划：** 先新增失败回归测试，再最小修改 runner、profile、engine；随后运行 P2 聚焦测试和编译检查。
## [P2 red tests] 2026-09-03

### A. 本轮目标（阅读前声明）

**目标文件：**
- `tests/test_perception_stages.py`：新增错配 `target_type` 与无效选择策略的失败测试。
- `tests/test_perception_engine.py`：新增替换 profile 后不能继承旧确认帧计数的失败测试。

**本轮要验证：** 先使现有实现因期望的通用安全契约而失败；测试只观察公共结果/异常，不依赖私有 `_tracks` 或 pipeline 内部数据结构。
### C. 本轮结果（红灯测试）

**失败证据：** 新增的 3 条公共契约测试均按预期失败：`TargetProfile(..., selection_strategy="random")` 未抛出；错误目标类型仍出现在 `DetectorRunner` 候选中；替换同 key profile 后第二帧被错误视为已确认。其余 7 条已有 stage/engine 测试通过，说明失败范围收敛在新定义的三个边界。

**同步记录：** `tests/test_perception_stages.py` 现在覆盖错误目标类型隔离和非法选择策略；`tests/test_perception_engine.py` 现在覆盖 profile 替换清除确认历史。这些测试只经公共 API 断言，允许后续内部实现继续拆分。

**覆盖进度更新：**

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|---|---|---|---:|---|
| `tests/test_perception_stages.py` | 深度完整 | 深度完整 | 2 | 新增两条红灯契约，用于约束 runner/profile 修改。 |
| `tests/test_perception_engine.py` | 浅读 | 深度完整 | 1 | 新增替换 profile 后不继承确认状态的红灯回归。 |

**下一轮计划：** 修改 `profiles.py`、`stages/runner.py`、`engine.py` 使三条失败契约转绿，再执行完整 P2 目标测试。
## [P2 contract fix] 2026-09-03

### A. 本轮目标（阅读前声明）

**目标文件：**
- `core/perception/profiles.py`：在 profile 构造点标准化并校验选择策略。
- `core/perception/stages/runner.py`：把目标类型错配转化为当前算法实例的受控错误。
- `core/perception/engine.py`：替换或删除 profile 时清除同 key 的确认状态。

**实现约束：** 不改变 `TargetDetection` 的算法通用性，不改输入/点击层，不让 GUI 参与判断；只让“profile 是一次单目标识别运行”的边界变得不可绕过。
### C. 本轮结果（P2 合同修复）

**实现结果：** `TargetProfile` 现在将选择策略标准化为小写，并仅接受 `confidence`、`first`、`nearest`；`DetectorRunner` 强制以 profile 的 `target_type` 创建算法参数，并将输出目标错配变为实例级 `errors`，不会污染候选；`PerceptionEngine` 在替换或注销 profile 时清除该 key 的跨帧确认状态。

**验证：** 感知核心聚焦集 15/15 通过：`tests.test_perception_stages`、`tests.test_perception_pipeline`、`tests.test_perception_engine`、`tests.test_perception_models`。`core/perception` 编译检查也通过。

**同步影响分析：** 调用方通过 `TargetProfile.from_dict()` 会更早得到无效选择策略的明确 `ValueError`；原本传入错误 `parameters.target_type` 的算法实例将按 profile 目标运行，符合单目标 profile 契约。engine 的注册/注销现在会清除内部短期状态，但不改变 profile 序列化或任何 GUI/输入 API。

**覆盖进度更新：**

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|---|---|---|---:|---|
| `core/perception/profiles.py` | 深度完整 | 深度完整 | 2 | 新增并验证选择策略白名单和规范化。 |
| `core/perception/stages/runner.py` | 深度完整 | 深度完整 | 2 | 新增并验证 profile 目标类型边界和实例级失败。 |
| `core/perception/engine.py` | 深度完整 | 深度完整 | 2 | 新增并验证 profile 生命周期清除确认轨迹。 |

**下一轮计划：** 审查并提交 P2 的所有未提交变更；随后进入 P3 provider seams，先定义帧、模板、OCR、特征后端的可替换资源边界与错误契约。
## [P2 completion review] 2026-09-03

### A. 本轮目标（阅读前声明）

**目标文件：**
- `core/perception/__init__.py`：确认公开导出无重复、无 GUI/输入依赖，并包含新的稳定 DTO/API。
- `docs/PERCEPTION_ENGINE_CHECKPOINT.md`：将 P2 的已验证范围、提交边界和 P3 前置条件写成可恢复的断点。
- `ITERATION_LOG.md`：核对本轮记录顺序、待办、测试证据，并归档 P2 完成状态。

**本轮要验证：** 只暂存感知架构及其文档/测试文件，严格排除用户已有的 `virtual_gamepad` 工作；检查 P2 diff 没有遗漏或意外 API 变动后创建一个独立提交。
### C. Completion-review finding

**关键发现：** (verified) 包导出无重复、未引入 GUI/输入依赖，P2 的 15 条聚焦测试与编译检查均通过；但默认 `PerceptionEngine.detect()` 仍委托给 `PerceptionPipeline.run()`，而 Pipeline 才持有 runner、confirmation 等状态。这样兼容类仍是运行时核心，和已确认的依赖方向“应用/GUI -> PerceptionEngine -> stages”冲突。

**修订的旧结论：** 先前把“存在 `PerceptionEngine` facade + 独立 stages”视为 P2 完成；现确认这只完成了 API 外观，尚未完成核心所有权反转。因此 P2 保持 `in progress`，不能在此状态提交为完成。

**决定：** 保持用户已确认的设计：`PerceptionEngine` 直接拥有 runner、fusion、confirmation、selection 编排与确认状态；`PerceptionPipeline` 仅持有一个 engine 并转发 `run/reset_confirmation`，作为旧 import 的兼容入口。不会改变 GUI、动作、旧游戏模块或 profile JSON 格式。

**覆盖进度更新：**

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|---|---|---|---:|---|
| `core/perception/__init__.py` | 浅读 | 深度完整 | 1 | 导出唯一、无 UI/输入依赖，RunResult 从 models 导出。 |
| `docs/PERCEPTION_ENGINE_CHECKPOINT.md` | 深度完整 | 深度完整 | 2 | 发现状态需保留 P2 in progress 并补充引擎所有权修复。 |
| `ITERATION_LOG.md` | 深度完整 | 深度完整 | 2 | 记录链已追加；后续需要整理本轮 Unicode 写入格式。 |

**下一轮计划：** 将该已批准的依赖反转设计写入计划/断点，写 red test 证明默认 engine 不再调用 pipeline，再以小步骤完成核心所有权反转。
## [P2 engine ownership plan] 2026-09-03

### A. 本轮目标（阅读前声明）

**目标文件：**
- `docs/plans/2026-09-03-perception-engine-implementation-plan.md`：复核原计划并追加经过确认的引擎所有权反转任务。
- `docs/PERCEPTION_ENGINE_CHECKPOINT.md`：写入 P2 未完成的准确原因和恢复入口。

**本轮要产出：** 一份 TDD 原子计划：先证实 engine 默认路径不再依赖 Pipeline，再把阶段状态移入 engine，最后把 Pipeline 降为无策略转发壳；每步有精确文件、验证命令和单独提交边界。
### C. 本轮计划发现

**关键发现：** (verified) 原计划把 P1 描述为“engine 委托兼容 pipeline”，且 P2 的目录路径误写成 `core/perception/pipeline/`；这正是当前所有权倒置的文档根源。checkpoint 的“明确缺失”也仍把已创建的 stage 文件列为缺失。

**修订的旧结论：** 原先认为 P2 的任务只是在 Pipeline 后面拆分 stages；现改为 P2 的完成条件是“默认 engine 自己持有 stages/确认状态，Pipeline 只转发”。

**TDD 原子计划：**

1. 在 `tests/test_perception_engine.py` 写失败测试，替换/监视 `PerceptionPipeline.run()` 并证明默认 engine 识别不走该方法；先运行该单项测试。
2. 在 `core/perception/engine.py` 移入运行、过滤、融合、确认、选择和 confirmation reset；保留显式注入 legacy pipeline 的兼容分支；使第 1 步测试转绿并提交。
3. 在 `tests/test_perception_pipeline.py` 写失败测试，断言 Pipeline 仍经 engine 公共检测 API 返回完全相同的 `PerceptionRunResult`；先运行该单项测试。
4. 在 `core/perception/pipeline.py` 删除所有策略状态，只转发 `run/reset_confirmation`；运行完整 P2 集、编译检查，更新 checkpoint 后提交。

**覆盖进度更新：**

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|---|---|---|---:|---|
| `docs/plans/2026-09-03-perception-engine-implementation-plan.md` | 深度完整 | 深度完整 | 2 | 定位到 P1 委托描述和 P2 错误目录，需追加精确反转步骤。 |
| `docs/PERCEPTION_ENGINE_CHECKPOINT.md` | 深度完整 | 深度完整 | 3 | 将更新为 stages 已存在、P2 所有权反转待完成。 |

**下一轮计划：** 保存详细设计/执行任务，接着为 engine 所有权写 red test；不接触 P3 provider 或 GUI。
### C. SYNC 结果（所有权设计与断点）

**已保存设计：** 新增 `docs/plans/2026-09-03-perception-engine-ownership-design.md`，记录所选方案、拒绝方案、默认引擎与兼容 Pipeline 的依赖图、四个 TDD 原子任务、精确测试命令、提交边界和非目标。

**更新断点：** 原实施计划已修正 P2 的真实 `stages/` 路径与“engine 直接执行”的完成条件；checkpoint 已将“stage 文件缺失”改为准确的“engine 所有权反转待完成”，并把恢复入口指向新设计文档。

**CODEBASE 同步：** 当前运行时结构未变，`CODEBASE.md` 保留并已准确记录 P2 所有权 defect；无需把尚未实现的设计伪写为当前事实。

**下一轮计划：** 按设计的 Task 1 在 engine 测试中写 red test，证明默认 engine 不会调用 `PerceptionPipeline.run()`；只有该测试失败后才移动执行所有权。
## [P2 engine ownership red test] 2026-09-03

### A. 本轮目标（阅读前声明）

**目标文件：**
- `tests/test_perception_engine.py`：以公共识别结果验证默认 engine 不经 `PerceptionPipeline.run()`。

**本轮要验证：** 在不改变运行时代码的前提下，替换 compatibility pipeline 的 `run` 为显式失败；默认 `PerceptionEngine().detect()` 应因此失败，证明目前存在待修正的依赖路径。测试不检查私有属性。
### C. 本轮结果（engine red test）

**失败证据：** 新测试失败于 `PerceptionEngine.detect()` 的 `self.pipeline.run(...)` 调用，且 mock 的 `AssertionError: compatibility path used` 被直接触发。这精确证明默认路径仍经 legacy Pipeline，没有其它算法、配置或环境噪声。

**同步记录：** `tests/test_perception_engine.py` 新增公共行为回归：默认 engine 即使 `PerceptionPipeline.run` 不可用，也必须完成颜色识别并产生已选择的 marker。测试本身不读取 engine 私有字段。

**覆盖进度更新：**

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|---|---|---|---:|---|
| `tests/test_perception_engine.py` | 深度完整 | 深度完整 | 2 | 新增精确依赖反转红灯测试并记录实际堆栈。 |

**下一轮计划：** 修改 `core/perception/engine.py` 直接编排已存在 stages，同时保留显式 legacy pipeline 注入分支；先使本测试转绿，再运行 engine/stage 聚焦集。
## [P2 direct engine execution] 2026-09-03

### A. 本轮目标（阅读前声明）

**目标文件：**
- `core/perception/engine.py`：让默认 engine 自己组合 runner、融合、确认、选择；保留显式 legacy pipeline 注入的向后兼容分支。

**实现约束：** 复用既有 `DetectorRunner`、`fuse_candidates`、`ConfirmationTracker`、`select_candidate`，不复制其算法；profile key、阈值、默认 merge 半径、RunResult 字段和 `reset_confirmation` 行为必须与当前 Pipeline 保持一致。
### C. SYNC 结果（默认引擎直接执行）

**实现结果：** `PerceptionEngine` 现在直接持有 `DetectorRunner` 和 `ConfirmationTracker`，并在私有 `_run_stages()` 中按既有顺序复用融合/选择 stage，返回原样的 `PerceptionRunResult`。显式传入 legacy pipeline 时仍走其 `run/reset_confirmation`，但默认构造路径不导入或构造 Pipeline。

**验证：** 新 red test 已转绿；`tests.test_perception_engine` 与 `tests.test_perception_stages` 共 11/11 通过，`compileall -q core/perception` 通过。

**影响分析：** profile 替换/注销现在通过 engine 自己的 `reset_confirmation` 清除状态；默认 detection 的阈值、半径、profile key、选择和错误字段与旧 Pipeline 行为一致。尚未修改 Pipeline，因此旧 `PerceptionPipeline` 仍暂时有自己的重复 stage 编排，下一轮将删去它。

**覆盖进度更新：**

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|---|---|---|---:|---|
| `core/perception/engine.py` | 深度完整 | 深度完整 | 3 | 默认路径已迁入 stage 组合和确认状态，legacy 注入分支保留。 |
| `tests/test_perception_engine.py` | 深度完整 | 深度完整 | 3 | 默认路径不调用 Pipeline 的 red/green 回归已通过。 |

**下一轮计划：** 为 `PerceptionPipeline` 写转发 red test，再将其降为只包含 registry、engine 和两项转发方法的兼容壳。
## [P2 pipeline forwarding red test] 2026-09-03

### A. 本轮目标（阅读前声明）

**目标文件：**
- `tests/test_perception_pipeline.py`：建立 compatibility Pipeline 只转发给其 engine 的公共测试，不依赖 runner/confirmation 私有实现。
- `core/perception/pipeline.py`：仅为理解当前重复编排而阅读；本轮先不修改。

**本轮要验证：** Pipeline 接收到 `run(frame, profile)` 时必须把相同 frame/profile 和显式 `reference=None` 交给其关联 engine 的 `detect`，并原样返回 engine 的结果；当前实现应因不存在关联 engine 而失败。
### C. 本轮结果（pipeline red test）

**失败证据：** 新的 compatibility 入口测试报出 `AttributeError: 'PerceptionPipeline' object has no attribute 'engine'`，精确证明它还不是转发壳，而仍持有自己的执行状态。

**同步记录：** `tests/test_perception_pipeline.py` 现在通过 Pipeline 的公开 `run()` 调用验证同一 frame/profile/reference 会转给关联 engine，且 engine 返回对象不被包装或修改。

**覆盖进度更新：**

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|---|---|---|---:|---|
| `tests/test_perception_pipeline.py` | 深度完整 | 深度完整 | 2 | 新增 pipeline 转发 red test；当前因缺少 engine 属性而失败。 |
| `core/perception/pipeline.py` | 深度完整 | 深度完整 | 2 | 确认其重复持有 runner/confirmation，是本轮唯一待删策略实现。 |

**下一轮计划：** 只修改 `pipeline.py`，通过局部导入避免循环依赖，创建默认 engine 并转发两个公开方法；保留 `_fuse_candidates` 旧私有导入包装。
## [P2 pipeline forwarding implementation] 2026-09-03

### A. 本轮目标（阅读前声明）

**目标文件：**
- `core/perception/pipeline.py`：将重复 stage 编排替换为一个 engine 实例和 `run/reset_confirmation` 转发；保留 `_fuse_candidates` 的旧导入兼容。

**实现约束：** 使用局部 import 解决 Engine/Pipeline 的单向运行时依赖；不改变 `PerceptionPipeline(registry)`、`run()`、`reset_confirmation()` 或 `_fuse_candidates()` 的调用签名；Pipeline 不再直接导入任何 stage 类。
### C. SYNC 结果（P2 兼容转发完成）

**实现结果：** `PerceptionPipeline` 现在只保存 registry 与一个默认 `PerceptionEngine`，用局部 import 避免循环导入，并将 `run(frame, profile, reference)`、`reset_confirmation(profile)` 原样转发。唯一保留的算法相关符号是 `_fuse_candidates()` 的旧私有导入兼容包装；它不参与 Pipeline 运行路径。

**验证：** P2 完整聚焦集 17/17 通过（stage、pipeline、engine、model）；感知包编译检查和公开包导入 smoke check 均通过。`git diff --check` 返回 0；仅报告仓库既有的 LF/CRLF 转换预警，没有空白错误。

**依赖结果：** 默认依赖方向已成为 `GUI/workflow -> PerceptionEngine -> stages`；旧调用为 `legacy caller -> PerceptionPipeline -> PerceptionEngine`。Pipeline 不再导入 runner、confirmation 或 selection，因此无法重新变成决策核心。

**覆盖进度更新：**

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|---|---|---|---:|---|
| `core/perception/pipeline.py` | 深度完整 | 深度完整 | 3 | 删除重复 stage 状态，保留兼容转发和 `_fuse_candidates`。 |
| `tests/test_perception_pipeline.py` | 深度完整 | 深度完整 | 3 | 转发 red/green 回归已通过，验证参数与返回对象保持不变。 |

**下一轮计划：** 复核感知 P2 全部 diff、更新 checkpoint/架构文档为完成状态，并只暂存这些文件创建 `feat: split perception decision stages` 提交。随后开始 P3 provider seams。
## [P2 final review and commit] 2026-09-03

### A. 本轮目标（阅读前声明）

**目标文件：**
- `docs/PERCEPTION_ENGINE_CHECKPOINT.md`：将 P2 完成条件、测试证据、P3 起点和仅感知文件的提交边界固化。
- `core/perception/__init__.py`：最终确认公开入口稳定、无 compatibility 循环问题。
- `core/perception/stages/__init__.py`：确认 package 文件只定义 stage 边界，不产生侧效应。

**本轮要验证：** 用路径白名单审查并暂存 P2 的 core、tests 和架构文档；绝不把 `virtual_gamepad/` 或任何其它用户现有修改带入提交。
### C. 最终审查发现

**关键发现：** (verified) `core/perception/__init__.py` 的公共导出无重复，公开 import smoke check 已通过；`stages/__init__.py` 仅重导出纯 stage API，没有创建 detector、确认状态或输入副作用。P2 白名单包含所有感知 core、tests、三份架构/断点文档；`virtual_gamepad/` 的修改均在白名单外。

**修订的旧结论：** checkpoint 仍将 P2 的 stage 所有权列为“明确缺失”；现已依据 17/17 测试和直接/兼容双路径验证改为 P2 complete，P3 才是下一项。

**提交白名单：** `CODEBASE.md`、`ITERATION_LOG.md`、`core/perception/{__init__,engine,models,pipeline,profiles}.py`、`core/perception/stages/`、三份 perception docs/plan、`tests/test_perception_{engine,pipeline,stages}.py`。不包含任意 `virtual_gamepad/` 文件。

**覆盖进度更新：**

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|---|---|---|---:|---|
| `core/perception/__init__.py` | 深度完整 | 深度完整 | 2 | 最终确认公共导出及循环导入 smoke check。 |
| `core/perception/stages/__init__.py` | 浅读 | 深度完整 | 1 | 仅公开纯 stage API，文档已改为 engine-owned。 |
| `docs/PERCEPTION_ENGINE_CHECKPOINT.md` | 深度完整 | 深度完整 | 4 | P2 状态、完成证据与 P3 起点已更新。 |

**下一轮计划：** 使用已声明的白名单暂存、复核 staged diff、创建 P2 提交；随后从 P3 的 provider 资源契约 red test 开始。
## [P3 template-resource discovery] 2026-09-03

### A. 本轮目标（阅读前声明）

**目标文件：**
- `core/perception/algorithms/template.py`：精读模板识别当前如何取得资源、如何处理路径/透明通道、以及哪些部分必须留在算法而非 provider。

**本轮要验证：** P3 的 template-resource provider 只负责资源定位/读取/明确错误，不改变模板匹配、缩放、掩码、NMS 或 `TargetDetection` 生成；识别算法仍应接收已解析的、可测试的资源输入。
### C. 本轮发现

**关键发现：** (verified) `TemplateDetector` 当前接收数组或路径：路径时直接 `cv2.imread(..., IMREAD_UNCHANGED)`，以 `FileNotFoundError` 表达不可读资源；读取后算法自行保留 alpha mask、颜色通道转换、多尺度、灰度/边缘匹配、NMS 和 `TargetDetection` 构建。provider 只能取代“由 resource_id 取得原始数组”的步骤，不能吸收这些匹配语义。

**修订的旧结论：** 原先把 template provider 视为能直接返回检测结果的候选方案；现确认它必须只返回带标识与元数据的原始资源，才能让模板、feature 等多个算法复用同一资源而输出仍由算法统一规范化。

**P3 设计结论：** 建立通用 `ProviderRegistry` 管理可用/实验/不可用 capability；建立类型化 `FrameSource`、`TemplateResourceProvider`、`OcrProvider`、`FeatureBackend` 合约和可序列化 DTO；`TemplateDetector` 保持兼容，P4 才通过 adapter 接入 provider。

**覆盖进度更新：**

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|---|---|---|---:|---|
| `core/perception/algorithms/template.py` | 深度完整 | 深度完整 | 2 | 精读路径读取、alpha/mask、多尺度、匹配和 NMS 边界。 |

**下一轮计划：** 阅读算法 descriptor/registry/builtins，确认 provider capability 状态与既有算法能力目录能共享的枚举和错误风格。
## [P3 capability-registry discovery] 2026-09-03

### A. 本轮目标（阅读前声明）

**目标文件：**
- `core/perception/algorithms/base.py`：确定算法 capability/status/参数描述的数据模式。
- `core/perception/registry.py`：确定可用、不可用、未知和 factory 失败的当前错误契约。
- `core/perception/builtins.py`：确定已有 color/template 与 shape/feature/OCR 未实现状态如何暴露给前端。

**本轮要验证：** provider registry 应复用算法目录的“descriptor + 可用性 + 受控错误”模式，但不能强迫具有不同输入/输出类型的 frame/template/OCR/feature provider 使用同一个不安全 factory 签名。
### C. 本轮发现

**关键发现：** (verified) `AlgorithmDescriptor` 已有 `available|experimental|unavailable` 三态及 GUI 参数元数据；`AlgorithmRegistry` 以 descriptor/factory 配对，未知 ID 为 `KeyError`，不可用/缺 factory 为 `RuntimeError`，并防御复制参数。builtins 把 shape/feature/OCR 正确标为不可用，但模板仍暴露 `template_path` 而非资源 ID。

**修订的旧结论：** 原先计划为每一种 provider 各写一个独立 registry；现确认应有一个通用 catalog/registration 容器，以 `ProviderDescriptor.capability` 区分类型，同时保留类型化 provider Protocol，才能同时满足前端发现能力与静态可读的调用契约。

**P3 contract：** `available` 和 `experimental` provider 必须注册实现；`unavailable` provider 只注册 descriptor；未知 provider、capability 不匹配、不可用 provider 分别抛出明确且不同的异常。Frame/Template/OCR/Feature 的 raw provider 输出在 adapters 中转为 `TargetDetection`，不能由 registry 伪装为一个统一 factory。

**覆盖进度更新：**

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|---|---|---|---:|---|
| `core/perception/algorithms/base.py` | 深度完整 | 深度完整 | 2 | 验证参数和三态 capability descriptor 模式。 |
| `core/perception/registry.py` | 深度完整 | 深度完整 | 2 | 验证 descriptor/factory、错误和防御复制契约。 |
| `core/perception/builtins.py` | 深度完整 | 深度完整 | 2 | 验证当前可用/不可用算法目录及模板路径耦合。 |

**下一轮计划：** 写 P3 provider DTO/registry 的详细计划与第一组 red tests：catalog 状态、未知/不可用/错误 capability 和不可变 descriptor 输出。
## [P3 provider-seams design] 2026-09-03

### A. 本轮目标（阅读前声明）

**目标文件：**
- `docs/plans/2026-09-03-perception-engine-implementation-plan.md`：将 P3 的泛化描述细化为可测试的 provider contract 步骤。
- `docs/PERCEPTION_ENGINE_CHECKPOINT.md`：确认 P3 是当前唯一进行项，且 P4 前不接入算法/GUI。

**本轮要产出：** provider 合约和 registry 的具体依赖图、DTO/异常边界、三态注册规则、四个 2–5 分钟 TDD 任务与验证命令；这些是后续 OCR/Feature/模板资源实现可替换而不绑定游戏的前提。
### C. 本轮计划结果

**关键发现：** (verified) P2 的提交已经落在 `6f60d12`，但 checkpoint 的 baseline hash 尚未前移；P3 在总计划中只有一段描述，缺少 provider 输出 DTO、错误分类与同 capability 多 provider 的解析规则，不能直接安全实现。

**确定设计：** 新建 `core/perception/providers/`：`contracts.py` 是无 OpenCV/GUI 依赖的数据、Protocol、错误；`registry.py` 是 descriptor+实现的 capability-safe catalog；`__init__.py` 是唯一公开 surface。Provider 原始结果与识别结果严格分层：`FrameContext` / `TemplateResource` / `OcrSpan` / `FeatureMatch` 不等于 `TargetDetection`。

**TDD 原子计划：**

1. contracts red/green：验证 descriptor 三态、模板/文字/特征 DTO 约束和 Protocol 导入不依赖可选 OCR/feature 包。
2. registry red/green：验证可用 provider 解析、未知 ID、capability 错配、不可用 descriptor、非可用但缺实现等不同错误。
3. public surface/default catalog red/green：验证只导出 contracts/registry，默认 catalog 使前端可发现尚未安装的 frame/template/OCR/feature capability，但不会伪称可执行。
4. P3 focused suite、compile/import audit、checkpoint/CODEBASE sync、独立提交；P4 才让 template/OCR/feature adapters 使用 registry。

**覆盖进度更新：**

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|---|---|---|---:|---|
| `docs/plans/2026-09-03-perception-engine-implementation-plan.md` | 深度完整 | 深度完整 | 3 | P3 需要独立细化计划，P2 记录正确。 |
| `docs/PERCEPTION_ENGINE_CHECKPOINT.md` | 深度完整 | 深度完整 | 5 | P2 已完成，P3 状态和基线需随新任务写入。 |

**下一轮计划：** 创建 provider seams 设计文档并更新 checkpoint；然后仅为 contracts 写第一组失败测试。
### C. SYNC 结果（P3 设计与断点）

**已保存设计：** 新增 `docs/plans/2026-09-03-perception-provider-seams-design.md`，明确定义 provider raw output、四类 Protocol、错误分类、可用性规则、四个 TDD 原子任务以及 P3 非目标。

**更新断点：** baseline 已更新为 `6f60d12`；P3 标记 `in progress`；实现计划引用新设计。P3 的“provider 不产出 TargetDetection、adapter 才产出”边界已记录，防止新算法重新高耦合资源获取与识别策略。

**CODEBASE 同步：** 当前运行时尚未增加 provider 源码，`CODEBASE.md` 不把设计文档误写成已实现结构；下一次源码实现后将新增 package 文件索引、调用链和风险登记。

**下一轮计划：** 建立 contracts 的 red test；确认新 provider package 在没有 OpenCV/OCR/feature 依赖时也可导入。
## [P3 provider contracts red test] 2026-09-03

### A. 本轮目标（阅读前声明）

**目标文件：**
- `tests/test_perception_providers.py`：新增 provider DTO、三态 descriptor、Protocol 可导入及无外部依赖的失败合同测试。

**本轮要验证：** 在 package 尚不存在时，测试必须因 `core.perception.providers` 缺失而失败；成功后才创建最小的 contracts 和公开 package surface。测试不实例化真实 OCR、特征或截屏实现。
### C. 本轮结果（provider contracts red test）

**失败证据：** `tests.test_perception_providers.ProviderContractTests` 在导入阶段按预期报出 `ModuleNotFoundError: No module named 'core.perception.providers'`。失败只证明 P3 package 尚不存在，未触及 OpenCV、OCR、特征或系统截屏环境。

**同步记录：** 新测试要求 descriptor 的防御性序列化、Template/OCR/Feature raw DTO、四个 Protocol 公共导入以及 ID/status/confidence 不变量；其断言明确禁止 OCR evidence 伪带 `target_type`。

**覆盖进度更新：**

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|---|---|---|---:|---|
| `tests/test_perception_providers.py` | PENDING | 深度完整 | 1 | 新增 contracts red test，当前失败为预期 package 缺失。 |

**下一轮计划：** 新建 `providers/__init__.py` 和 `providers/contracts.py`，以 stdlib typing/dataclasses 与已有 perception DTO 为唯一内部依赖，使本组测试转绿。
## [P3 provider contracts implementation] 2026-09-03

### A. 本轮目标（阅读前声明）

**目标文件：**
- `core/perception/providers/__init__.py`：建立唯一公开 package surface。
- `core/perception/providers/contracts.py`：实现 provider DTO、Protocol、三态 descriptor 和错误类型。
- `tests/test_perception_providers.py`：使已定义的 contracts red test 转绿。

**实现约束：** 只依赖 Python 标准库和既有 `core.perception.models`；不得 import OpenCV、PySide、平台捕获、OCR 或 ML 包；不引入 registry 或算法适配，避免超出 P3.1。
### C. SYNC 结果（provider contracts）

**实现结果：** 新增 `core/perception/providers/contracts.py` 与公开 `providers/__init__.py`。它们提供四类 raw provider Protocol、immutable descriptor/resource/evidence DTO，以及注册、未知、能力错配、不可用四类错误；没有 provider 直接产生 `TargetDetection`。

**验证：** contracts 聚焦测试 4/4 通过，provider package 编译通过。额外 import 检查显示 provider 模块本身没有 OCR/feature/capture 依赖；由于父包 `core.perception.__init__` 现有公开 imports 会加载 TemplateDetector，Python 进程仍已加载仓库既有的 `cv2`，这不是 provider contracts 新增依赖，P9 将统一审计 package import 延迟加载问题。

**影响分析：** 所有 DTO 使用已有 `FrameContext`、`BoundingBox`、`CoordinateSpace`，所以 OCR/Feature adapter 在 P4 能产出完整空间证据，但现在不修改任何算法、GUI、screen capture、输入或 legacy 模块。

**覆盖进度更新：**

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|---|---|---|---:|---|
| `core/perception/providers/contracts.py` | PENDING | 深度完整 | 1 | 新增 raw DTO、Protocol、descriptor 和明确错误层级。 |
| `core/perception/providers/__init__.py` | PENDING | 深度完整 | 1 | 新增稳定公开 exports，无运行时 provider 实例。 |
| `tests/test_perception_providers.py` | 深度完整 | 深度完整 | 2 | contracts red/green 4 条已通过。 |

**下一轮计划：** 为 `ProviderRegistry` 写 red tests，覆盖实现解析、capability 错配、未安装与注册规则；不接入任何真实 runtime provider。
## [P3 provider registry red test] 2026-09-03

### A. 本轮目标（阅读前声明）

**目标文件：**
- `tests/test_perception_providers.py`：为 registry 定义 provider 解析、capability 过滤、未知/错配/不可用错误和注册约束。

**本轮要验证：** 先在 `ProviderRegistry` 尚不存在时以 import failure 建立 API；一个 provider 只能按其 descriptor capability 被解析，registry 返回对象但绝不调用 provider 方法或处理 provider 输出。
### C. 本轮结果（provider registry red test）

**失败证据：** registry 测试在导入阶段按预期失败：`ProviderRegistry` 尚未从 `core.perception.providers` 暴露。contracts 原有测试未执行，表明失败范围是新 API 缺失而非 DTO 回归。

**同步记录：** 新测试固定了 registry 不能调用 provider、同 ID 必须按 capability 解析、discovery filter 保持 descriptor 对象顺序，以及四种明确失败路径。

**覆盖进度更新：**

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|---|---|---|---:|---|
| `tests/test_perception_providers.py` | 深度完整 | 深度完整 | 3 | 新增 registry red tests，当前失败为未实现 public registry。 |

**下一轮计划：** 新增 registry 模块并扩展公开 exports；只存储/解析 object provider，不实现具体 capture/OCR/template/feature provider。
## [P3 provider registry implementation] 2026-09-03

### A. 本轮目标（阅读前声明）

**目标文件：**
- `core/perception/providers/registry.py`：实现 descriptor 与 object provider 的 capability-safe 注册/解析。
- `core/perception/providers/__init__.py`：仅增加 registry 公开 exports。
- `tests/test_perception_providers.py`：使 registry contracts red tests 转绿。

**实现约束：** `register()` 不应调用 provider；`resolve()` 不应调用 provider；不做任何 `isinstance` Protocol 检查或输出转换；不允许可用/实验 descriptor 在没有 implementation 时登记。
### C. SYNC 结果（provider registry）

**实现结果：** 新增 `ProviderRegistry`。它按注册顺序保存 descriptor 与 provider object，注册时强制三态规则；解析时先校验 provider ID、再校验期望 capability、最后处理 unavailable，且从不调用 provider 或检查/转换其 raw output。

**验证：** providers 测试 6/6 通过，provider package 编译检查通过。可用 registry 返回完全相同的 object；未知、能力错配、不可用和非法注册均由不同异常类别表达。

**覆盖进度更新：**

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|---|---|---|---:|---|
| `core/perception/providers/registry.py` | PENDING | 深度完整 | 1 | 新增 capability-safe catalog、登记/发现/解析和失败分类。 |
| `core/perception/providers/__init__.py` | 深度完整 | 深度完整 | 2 | 扩展 registry 唯一公开 export。 |
| `tests/test_perception_providers.py` | 深度完整 | 深度完整 | 4 | registry red/green 2 条已通过，contracts 仍通过。 |

**下一轮计划：** 写 default provider catalog red test，使前端能发现四种尚未安装的 capability 且明确不可解析；不实现 OS/OCR/ML 后端。
## [P3 default catalog red test] 2026-09-03

### A. 本轮目标（阅读前声明）

**目标文件：**
- `tests/test_perception_providers.py`：定义默认 provider catalog 的发现/不可用契约。

**本轮要验证：** default catalog 应列出 `frame.screen`、`template.resource`、`ocr.default`、`feature.default` 四种 capability；每个均对前端可见但 `resolve` 明确失败，不创建现实后端。
### C. 本轮结果（default catalog red test）

**失败证据：** default catalog 测试按预期在 import 阶段失败：`create_default_provider_registry` 尚未公开。这一失败仅表示 discoverable catalog 未实现，没有触发任何 provider。

**同步记录：** 新测试锁定四个稳定 provider ID、对应 capability、全部 `unavailable` 状态，以及 OCR 解析会抛 `ProviderUnavailableError`；它防止未安装实现被前端错误展示为可运行。

**覆盖进度更新：**

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|---|---|---|---:|---|
| `tests/test_perception_providers.py` | 深度完整 | 深度完整 | 5 | default catalog red test 已加入，当前 API 缺失。 |

**下一轮计划：** 新增 provider builtins discovery catalog 并公开工厂；只登记 unavailable descriptor，不注册或执行任何实现。
## [P3 default catalog implementation] 2026-09-03

### A. 本轮目标（阅读前声明）

**目标文件：**
- `core/perception/providers/builtins.py`：创建仅供发现的四项 unavailable provider descriptor catalog。
- `core/perception/providers/__init__.py`：公开默认 catalog factory。
- `tests/test_perception_providers.py`：使 default catalog red test 转绿。

**实现约束：** catalog construction 不得访问 filesystem、桌面窗口、摄像头、网络、OCR/ML library 或 TemplateDetector；所有 descriptor 均无 implementation，解析行为仍由 `ProviderRegistry` 统一决定。
### C. SYNC 结果（default provider catalog）

**实现结果：** 新增 `providers/builtins.py` 的 `create_default_provider_registry()`。它只登记 `frame.screen`、`template.resource`、`ocr.default`、`feature.default` 四个 unavailable descriptor；没有实现 object、没有资源 I/O，也不会把可选后端列为 available。

**验证：** provider suite 7/7 通过，provider 编译检查通过，公开 factory smoke check 正确输出四个 stable ID。

**覆盖进度更新：**

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|---|---|---|---:|---|
| `core/perception/providers/builtins.py` | PENDING | 深度完整 | 1 | 新增可发现但未安装的默认 capability catalog。 |
| `core/perception/providers/__init__.py` | 深度完整 | 深度完整 | 3 | 公开 default catalog factory，未创建 runtime provider。 |
| `tests/test_perception_providers.py` | 深度完整 | 深度完整 | 6 | catalog red/green 已通过，总 provider suite 7 条通过。 |

**下一轮计划：** P3 final review：运行 provider + 既有 perception 全集，更新 checkpoint/CODEBASE 为 provider seams complete，只暂存 P3 白名单并独立提交。
## [P3 final review and commit] 2026-09-03

### A. 本轮目标（阅读前声明）

**目标文件：**
- `docs/PERCEPTION_ENGINE_CHECKPOINT.md`：将 P3 合约、错误、测试证据与 P4 前置条件固化。
- `core/perception/providers/__init__.py`：确认公开 exports 完整且不创建运行时 provider。
- `core/perception/providers/builtins.py`：确认默认 catalog 不触发外部 I/O。

**本轮要验证：** P3 provider tests 和既有 perception tests 一起通过；暂存仅 provider package、provider tests 与 perception docs，不混入 virtual_gamepad 用户修改。
### C. 最终审查结果

**验证：** provider 与既有 perception 聚焦集共 24/24 通过；`compileall -q core/perception` 和 `git diff --check` 均返回 0。diff check 只打印仓库既有 LF/CRLF 工作区预警，无 whitespace error。

**审查结论：** provider package 未修改 TemplateDetector、Engine、Pipeline、GUI、输入、Portal/Loot/minimap 或空间映射。其默认 catalog 无实现对象，因而不会意外调用 filesystem、Windows capture 或可选 OCR/ML backend。`core/events/window_finder.py` 和 `virtual_gamepad/` 均是白名单外用户修改，绝不暂存。

**CODEBASE 同步：** 已记录 contracts、registry、default catalog 的文件职责、算法边界和无 I/O 风险。checkpoint 标记 P3 complete，并把 P4 起点限定为“先做模板资源 provider adapter”。

**下一轮计划：** 仅暂存 P3 provider package、provider test 和 perception documentation，复核 staged diff 后提交 `feat: add perception provider seams`；再以 P4 模板资源 bridge 的 red test 继续。
## [P4 template-provider design discovery] 2026-09-04

### A. 本轮目标（阅读前声明）

**目标文件：**
- `core/perception/algorithms/template.py`：识别模板资源加载与匹配逻辑的精确分界。
- `core/perception/builtins.py`：识别 profile 参数到模板算法 factory 的兼容路径。
- `tests/test_perception_algorithms.py`：识别当前模板匹配兼容行为和可加入的 provider bridge 回归入口。

**本轮要澄清：** P4 的第一个适配器是否应以 `template_resource_id + TemplateResourceProvider` 替代文件路径读取，同时保持数组和 `template_path` 作为向后兼容入口；provider 输出不能越过算法层直接生成 `TargetDetection`。
### C. 本轮发现

**关键发现：** (verified) `TemplateDetector` 的“模板文件路径 -> 像素数组”读取与匹配算法当前同处一类；其 array 输入已经证明匹配逻辑可独立于文件资源。`_create_template()` 也只接受 array 或 `template_path`，还没有任何 `template_resource_id` 或 provider 注册表入口。现有模板测试覆盖多尺度、bbox、空间和算法 evidence，但未覆盖 provider 资源来源。

**修订的旧结论：** 原先把 P4 理解成替换 `TemplateDetector` 为一个 provider-aware detector；现确认最小且安全的方向是保留 detector 的数组/path 兼容构造器，新增一个 provider adapter/factory：先 `TemplateResourceProvider.load(resource_id)`，再把 `resource.image` 交给未变的 detector。这样不会把 provider 生命周期或资源 ID 侵入匹配循环。

**待确认设计选择：** provider 的绑定点可放在算法 registry factory、独立的 adapter 类，或同时允许二者；这会影响 P4 的公共 API 和 GUI 后续如何传入 composition context。

**覆盖进度更新：**

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|---|---|---|---:|---|
| `core/perception/algorithms/template.py` | 深度完整 | 深度完整 | 3 | 确认数组输入可复用，路径 I/O 是唯一待替换边界。 |
| `core/perception/builtins.py` | 深度完整 | 深度完整 | 3 | 确认当前 factory 无 provider/context 注入点。 |
| `tests/test_perception_algorithms.py` | 浅读 | 深度完整 | 1 | 当前只验证模板算法本身，缺少 provider bridge 回归。 |

**CODEBASE 同步：** 当前代码事实未改变；P4 的未决绑定点未写入 `CODEBASE.md`，防止把设计选择误记为已实现结构。
## [P4 template-resource adapter plan] 2026-09-04

### A. 本轮目标（阅读前声明）

**目标文件：**
- `docs/plans/2026-09-04-template-resource-adapter-design.md`：保存已确认的独立资源适配器设计和 TDD 任务。
- `docs/PERCEPTION_ENGINE_CHECKPOINT.md`：把用户确认的第 1 方案写入恢复点。
- `docs/plans/2026-09-03-perception-provider-seams-design.md`：核对 P3 provider contract 与 P4 adapter 的接口衔接。

**本轮要完成：** 不修改运行时代码，先把“`TemplateResourceProvider.load(resource_id)` → adapter → 现有 `TemplateDetector` 数组输入”的设计、兼容规则、测试命令和提交边界固化。
### C. 本轮结果

**设计决定：** 用户已确认独立资源适配器方案。新增设计文档将 provider 获取与模板匹配明确分层：provider 只返回 `TemplateResource`，adapter 只组装资源与算法，`TemplateDetector` 继续负责灰度/边缘、多尺度、alpha mask、阈值、NMS 和 `TargetDetection` 输出。

**兼容决定：** `template` 数组和 `template_path` 继续可用；只有 `template_resource_id` 才要求运行时注入 provider；同时提供多个资源来源时显式报配置错误；provider 对象不进入 profile JSON。

**文档同步：** 新增 `docs/plans/2026-09-04-template-resource-adapter-design.md`，更新总体实施计划与 checkpoint，P4 标记为 in progress。当前未修改任何运行时代码。

**覆盖进度更新：**

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|---|---|---|---:|---|
| `docs/plans/2026-09-04-template-resource-adapter-design.md` | PENDING | 深度完整 | 1 | 记录第 1 方案、API 边界、TDD 任务和兼容规则。 |
| `docs/PERCEPTION_ENGINE_CHECKPOINT.md` | 深度完整 | 深度完整 | 5 | 已记录用户选择、P4 起点和 provider 注入规则。 |
| `docs/plans/2026-09-03-perception-engine-implementation-plan.md` | 深度完整 | 深度完整 | 4 | 将 P4 首个切片指向模板资源 adapter。 |

**下一步：** 按计划 Task 1 编写 `ProviderBackedTemplateDetector` 的失败测试；本轮先不实现代码，待 red test 建立后再继续。
## [P4 Task 1 red test] 2026-09-04

### A. 本轮目标（阅读前声明）

**目标文件：**
- `tests/test_perception_template_adapter.py`：定义独立 `TemplateResourceProvider` 到现有模板算法数组输入的失败合同。

**本轮要验证：** 适配器在构造时只调用 provider 一次，要求返回 `TemplateResource`，把原始 `image` 交给 `TemplateDetector`，并保持目标类型、bbox、置信度和 source 输出；适配器缺失或空资源 ID 必须在边界处失败。
### C. 本轮结果（Task 1 red）

**失败证据：** 新测试在导入阶段按预期报出 `ModuleNotFoundError: core.perception.algorithms.template_adapter`。失败仅表示适配器尚未实现；测试 fixture 已将 provider 调用次数、资源 DTO、空 ID、provider 类型和 provider error 边界固定下来。

**覆盖进度更新：**

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|---|---|---|---:|---|
| `tests/test_perception_template_adapter.py` | PENDING | 深度完整 | 1 | 新增 provider-backed 模板适配器红灯合同。 |

**下一步：** 新建 `core/perception/algorithms/template_adapter.py`，只组合 `TemplateResourceProvider.load()` 与未修改的 `TemplateDetector`。
### C. 本轮结果（Task 1 green）

**实现结果：** 新增 `ProviderBackedTemplateDetector`。构造时校验非空 resource ID 和 `load()` 方法，调用 provider 一次并要求 `TemplateResource`，再把唯一的 `resource.image` 交给现有 `TemplateDetector`；`detect()` 只转发原有匹配结果，不复制任何匹配算法。

**验证：** `tests.test_perception_template_adapter` 3/3 通过；`compileall -q core/perception/algorithms` 通过。provider error 没有被路径 fallback 吞掉。

**覆盖进度更新：**

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|---|---|---|---:|---|
| `core/perception/algorithms/template_adapter.py` | PENDING | 深度完整 | 1 | 新增 resource provider 到 TemplateDetector 数组输入的组合适配器。 |
| `tests/test_perception_template_adapter.py` | 深度完整 | 深度完整 | 2 | provider 加载一次、类型/ID/error 边界和识别输出已通过。 |

**CODEBASE 同步：** 已在架构索引新增 adapter 职责、算法步骤、失败行为和调用关系。

**下一步：** 为 builtins factory 写失败测试，要求 runtime 显式传入 provider 才能使用 `template_resource_id`；保持原 `template` 和 `template_path` 参数兼容。
## [P4 Task 2 red test] 2026-09-04

### A. 本轮目标（阅读前声明）

**目标文件：**
- `tests/test_perception_template_adapter.py`：为 `create_template_detector(parameters, template_provider=None)` 定义资源 ID、provider、旧数组/路径兼容和歧义输入行为。

**本轮要验证：** factory 只负责构造/组合，不执行识别；provider 依赖是显式运行时参数，不写入 `TargetProfile`；缺 provider、缺资源字段、同时传多个资源来源都必须明确失败。
### C. 本轮结果（Task 2 red）

**失败证据：** factory 测试在导入阶段按预期失败：`core.perception.builtins` 尚未公开 `create_template_detector`。Task 1 的 3 条测试仍保留为绿色基线，当前失败只针对新的 factory 组合入口。

**覆盖进度更新：**

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|---|---|---|---:|---|
| `tests/test_perception_template_adapter.py` | 深度完整 | 深度完整 | 3 | 新增 factory 资源 ID/provider、旧兼容和歧义输入 red tests。 |

**下一步：** 在 `builtins.py` 增加显式 `create_template_detector()`，让 `_create_template()` 仅做兼容包装；不修改 AlgorithmRegistry 的 provider 无感知设计。
### C. 本轮结果（Task 2 green）

**实现结果：** `builtins.py` 新增 `create_template_detector(parameters, template_provider=None)`：明确区分 `template` 数组、`template_path` 和 `template_resource_id` 三种来源；资源 ID 必须有显式 provider；多来源和无来源会立即报 `ValueError`；`_create_template()` 保留为无 provider 的旧兼容包装。

**验证：** 模板适配器 + 现有算法测试共 8/8 通过；`compileall -q core/perception` 通过。数组入口实际使用 NumPy 数组，不触发数组 truth-value 异常；旧模板算法的多尺度/bbox 测试仍通过。

**覆盖进度更新：**

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|---|---|---|---:|---|
| `core/perception/builtins.py` | 深度完整 | 深度完整 | 4 | 新增显式资源来源 factory，旧 `_create_template` 继续兼容。 |
| `tests/test_perception_template_adapter.py` | 深度完整 | 深度完整 | 4 | factory red/green 与旧数组/路径/歧义行为已覆盖。 |

**CODEBASE 同步：** 已更新 `builtins.py` 与 template adapter 的职责和调用链说明。

**下一步：** Task 3 设计运行时 provider composition seam；先写失败测试验证 `PerceptionEngine` 可以注入 provider-aware template factory，同时默认 engine 不要求 provider，且 profile JSON 不序列化 provider object。
## [P4 Task 3 red test] 2026-09-04

### A. 本轮目标（阅读前声明）

**目标文件：**
- `tests/test_perception_template_adapter.py`：验证 provider-aware template factory 可以通过 `PerceptionEngine` 的显式运行时 composition hook 注入；默认 engine 在没有 provider 时仍保持明确错误。

**本轮要验证：** provider object 只存在于 runtime factory closure，不进入 `TargetProfile.to_dict()`；同一 profile 仍可在默认 engine 与 provider-aware engine 中复用。
### C. 本轮结果（Task 3 green）

**实现结果：** `PerceptionEngine` 新增可选 `algorithm_factories` runtime composition hook；`DetectorRunner` 对指定算法 ID 使用深拷贝参数调用 override factory，并先确认该 ID 在 registry 中有 descriptor。provider 对象可被外部 closure 捕获，但不进入 profile 或 JSON；显式注入 compatibility Pipeline 时禁止同时注入 overrides，避免两套执行语义。

**验证：** 模板 adapter + 现有算法测试共 10/10 通过；`compileall -q core/perception` 通过。测试确认 provider-backed engine 能输出 detection，默认 engine 对 resource ID 返回受控错误，profile JSON 只保留 resource ID。

**同步影响：** 算法 registry 仍不理解 provider；runtime composition 只替换指定 algorithm factory，未修改旧 color/template descriptor 或 Pipeline 行为。未知 override ID 会沿用 registry 的 descriptor 错误路径。

**覆盖进度更新：**

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|---|---|---|---:|---|
| `core/perception/stages/runner.py` | 深度完整 | 深度完整 | 3 | 新增深拷贝参数的 factory override 运行时 seam。 |
| `core/perception/engine.py` | 深度完整 | 深度完整 | 4 | 新增显式 algorithm factory 注入与 compatibility 冲突校验。 |
| `tests/test_perception_template_adapter.py` | 深度完整 | 深度完整 | 5 | engine runtime composition 和无 provider 错误契约已通过。 |

**下一步：** 进入 P4 Task 4：补充 `algorithms/__init__.py` / CODEBASE / checkpoint 的公开入口说明，运行完整 P4 聚焦集，确认没有循环导入和旧兼容回归后提交。
## [P4 template adapter public-surface red test] 2026-09-04

### A. 本轮目标（阅读前声明）

**目标文件：**
- `tests/test_perception_template_adapter.py`：锁定 `ProviderBackedTemplateDetector` 从 `core.perception.algorithms` 公共入口可导入。
- `core/perception/algorithms/__init__.py`：仅增加稳定导出，不改变算法构造或运行行为。

**本轮要验证：** 后续 GUI/应用可使用算法包公共入口而非深层文件路径；旧 `TemplateDetector`、ColorRegionDetector 和参数描述 exports 保持不变。
### C. 本轮结果（public-surface red）

**失败证据：** 公共入口测试按预期在导入阶段失败：`core.perception.algorithms` 尚未导出 `ProviderBackedTemplateDetector`。深层模块导入仍可用，说明只缺 package surface。

**覆盖进度更新：**

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|---|---|---|---:|---|
| `tests/test_perception_template_adapter.py` | 深度完整 | 深度完整 | 6 | 新增公共入口 red test，当前仅 package export 缺失。 |
| `core/perception/algorithms/__init__.py` | 浅读 | 深度完整 | 2 | 确认已有四项 exports，待增加 adapter。 |

**下一步：** 增加单一公共 export，运行 P4 模板 adapter 全集与原感知 suite。
### C. 本轮结果（template adapter slice）

**实现结果：** 第 1 方案已实际落地：`ProviderBackedTemplateDetector` 独立加载 `TemplateResource`，`create_template_detector()` 负责选择资源来源，`PerceptionEngine.algorithm_factories` 提供运行时注入。现有 `TemplateDetector` 不承载 provider，也未改变匹配算法。

**验证：** P4 当前切片全套测试 32/32 通过，包含 provider contracts、template adapter、现有 color/template、engine、pipeline、stage 和 model 测试；`compileall -q core/perception` 和公共 import smoke 通过。

**审查结论：** 未修改 GUI、输入、导航、Portal/Loot/minimap、坐标映射或 `virtual_gamepad`。provider 对象不会出现在 profile JSON；默认 engine 对 resource ID 无 provider 时返回实例级错误而不是 fallback。P4 总任务保持 in progress，后续仍需 OCR、Feature、Shape、Motion adapter。

**覆盖进度更新：**

| 文件 | 前状态 | 现状态 | 阅读次数 | 备注 |
|---|---|---|---:|---|
| `core/perception/algorithms/template_adapter.py` | 深度完整 | 深度完整 | 2 | 已验证独立 provider 资源加载和算法委托。 |
| `core/perception/algorithms/__init__.py` | 深度完整 | 深度完整 | 3 | 已验证公共 adapter export。 |
| `core/perception/builtins.py` | 深度完整 | 深度完整 | 5 | 已验证三种资源来源选择、歧义和缺 provider 错误。 |
| `core/perception/stages/runner.py` | 深度完整 | 深度完整 | 4 | 已验证 runtime factory override 不破坏 descriptor/目标类型边界。 |
| `core/perception/engine.py` | 深度完整 | 深度完整 | 5 | 已验证 provider object 仅存在 runtime composition。 |
| `tests/test_perception_template_adapter.py` | 深度完整 | 深度完整 | 7 | 7 条 adapter/composition/public-surface 测试全部通过。 |

**下一步：** 仅暂存 P4 模板 adapter 相关源码、测试和文档，复核 staged diff 后提交；随后继续 P4 的 OCR provider adapter 设计，不接 GUI。
## [SYNC] 2026-09-04 - Template adapter typing polish

### A. SYNC 范围声明

**触发任务：** 将 `PerceptionEngine.algorithm_factories` 类型从具体 `dict` 放宽为只读语义更准确的 `Mapping`，不改变运行时行为。

**直接变更文件：** `core/perception/engine.py`。

**预期连带影响：** 仅静态 API 签名；模板 adapter、runner、profile、Pipeline 和 GUI 行为不变。

### C. SYNC 结果

**连带重读文件：** `core/perception/engine.py`，确认构造时仍复制 mapping、runner 仍接收 factory overrides，compatibility pipeline 冲突校验不变。

**验证：** 下一次 P4 staged 检查将覆盖 32 条聚焦测试与 compileall；此修改不引入新测试分支。
## [Virtual gamepad dual-input design discovery] 2026-09-04

### A. 本轮目标（阅读前声明）

**目标文件：**
- `virtual_gamepad/host/src/VirtualGamepadHost/Input/RawInputCapture.cs`：确认当前原始输入源识别、设备生命周期和事件模型。
- `virtual_gamepad/host/src/VirtualGamepadHost/Input/MappingConfig.cs`：确认现有绑定配置是否支持多个 source、同键多绑定和持久化。
- `virtual_gamepad/host/src/VirtualGamepadHost/Input/MappingEngine.cs`：确认映射合并、冲突、输出目标按键的当前规则。
- `virtual_gamepad/ui/virtual_gamepad_ui/main_window.py`、`models.py`：确认当前 UI 是否已有单/多 profile 结构、绑定编辑入口和状态刷新路径。
- `virtual_gamepad/ui/tests/`：确认既有测试覆盖，避免破坏用户当前修改。

**本轮要澄清：** 两个输入源是“两个独立物理手柄设备”还是“同一设备的两个逻辑通道”；两个界面应分别编辑 source A/source B，最终由一个合并层生成虚拟输出；同一目标按键允许多 source 同时绑定，并明确按下/释放引用计数规则。

## [P4 OCR provider adapter discovery] 2026-09-04

### A. Scope declaration
**Goal files:** `core/perception/providers/contracts.py`, `core/perception/algorithms/template_adapter.py`, `core/perception/builtins.py`, `core/perception/engine.py`, and focused perception tests.
**Question:** define a provider-backed OCR adapter that turns raw `OcrSpan` evidence into target-level `TargetDetection` while keeping provider objects out of profile JSON and retaining the provider-free registry boundary.
**Boundary:** this slice must not add an OCR engine, GUI path, screen capture, coordinate mapping, workflow call, or game-specific target rule.

### C. Findings
**Verified:** `OcrProvider.recognize(frame, parameters)` returns raw `OcrSpan` values that already carry text, bounding box, coordinate space, confidence, language, and raw metadata, while carrying no target semantics. `ProviderBackedTemplateDetector` establishes the correct precedent: validate the provider boundary and delegate/normalize without moving provider objects into profiles.
**Design decision:** `ProviderBackedOcrDetector` will execute the injected provider for each frame, require `OcrSpan` output, apply a configurable generic text predicate (`exact`, `contains`, or `regex`) and minimum OCR confidence, then produce one `TargetDetection` per matching span. It will preserve the span's geometry and coordinate space, place raw details in evidence, and allow provider/configuration errors to reach `DetectorRunner`'s existing per-instance isolation.
**Compatibility:** the default OCR descriptor stays discoverable but unavailable because no OCR backend is bundled. A runtime `PerceptionEngine.algorithm_factories["ocr"]` closure may make it executable without serializing provider objects or adding a mandatory OCR dependency.
**Next task:** document the adapter contract, create one red contract test, then implement the smallest adapter/factory/export slice.

### C. Slice 1 red result
**Failure evidence:** `tests.test_perception_ocr_adapter` fails at import time with `ModuleNotFoundError: core.perception.algorithms.ocr_adapter`, as expected. The test locks the first public behavior: one injected provider call per frame; exact case-insensitive query matching; confidence filtering; and geometry, timing, text, language, metadata, source, and target-type preservation in `TargetDetection`.
**Next task:** add only `ProviderBackedOcrDetector` to satisfy the first contract; do not change the algorithm registry, GUI, providers, engine, or profile model in this green step.

## [SYNC] 2026-09-04 - OCR provider adapter

### A. SYNC scope declaration
**Trigger:** P4 adds a provider-backed OCR algorithm adapter, its runtime factory, public algorithm export, editable descriptor parameters, focused tests, and design record.
**Directly changed files:** `core/perception/algorithms/ocr_adapter.py`, `core/perception/algorithms/__init__.py`, `core/perception/builtins.py`, `tests/test_perception_ocr_adapter.py`, and `docs/plans/2026-09-04-ocr-provider-adapter-design.md`.
**Dependency review:** `providers/contracts.py` remains the raw OcrSpan boundary; `PerceptionEngine` and `DetectorRunner` reuse their existing runtime-factory override seam; GUI, profile serialization, spatial mapping, capture, input, navigation, and workflows remain unaffected.

### C. SYNC result
**Implemented behavior:** `ProviderBackedOcrDetector` calls an explicit OCR provider once per frame, requires `OcrSpan` evidence, filters configured exact/contains/regex matches and confidence, preserves each selected span's geometry/coordinate space/text/timestamp, ranks candidates by confidence, and emits standard `TargetDetection` values. No bundled OCR engine, GUI route, or action behavior was added.
**Composition and compatibility:** `create_ocr_detector()` requires an explicit provider; the existing `PerceptionEngine.algorithm_factories` closure seam enables it while default registry OCR remains discoverable/unavailable. Existing color/template factory behavior, templates, profiles, providers, and pipeline APIs are unchanged.
**Verification:** 10/10 OCR adapter tests passed; 42/42 focused provider/template/OCR/algorithm/engine/stage/pipeline tests passed; `compileall -q core/perception` passed.
**CODEBASE.md synchronized:** updated C4 call path, OCR adapter/module/public-surface/factory/engine details, risk statement, and OCR regression contract. `docs/PERCEPTION_ENGINE_CHECKPOINT.md` records the completed OCR slice; the next P4 candidates are shape, feature, and motion adapters.
**Coverage update:** `core/perception/algorithms/ocr_adapter.py` and `tests/test_perception_ocr_adapter.py` are deeply read and documented; `algorithms/__init__.py`, `builtins.py`, engine/runner/provider contracts, and prior template adapter were re-read for dependency impact.

## [P4 shape adapter discovery] 2026-09-04

### A. Scope declaration
**Goal files:** `core/perception/algorithms/shape.py`, `core/perception/builtins.py`, `core/perception/algorithms/__init__.py`, and focused perception tests.
**Question:** add a deterministic OpenCV contour/geometry detector that accepts reusable shape parameters and emits `TargetDetection` without requiring a resource provider, ML model, game target name, GUI, coordinate mapper, or action layer.
**Boundary:** shape evidence derives only from the supplied `FrameContext`; it must not access desktop capture, templates, OCR, input, navigation, legacy minimap code, or workflows.

## [P4 fast OCR provider discovery] 2026-09-04

### A. Scope declaration
**User request:** select and implement a fast local OCR core that locates recognized text in an image, then test the provider-to-`OcrSpan` and adapter-to-`TargetDetection` paths.
**Read targets:** installed Python/ONNX/OCR capabilities, project dependency policy, `OcrProvider` contract, provider registry/catalog, and existing OCR adapter tests.
**Boundary:** the concrete backend must remain optional and lazily imported; importing `core.perception` must not download a model, initialize OCR, access a screen, or make Paddle/Tesseract/ONNX mandatory for unrelated users.

### C. Findings
**Verified:** generic perception has no shape implementation. Existing Portal/Loot contour routines are target-specific compatibility code and must remain untouched. Current dependencies already include OpenCV/NumPy, and `ColorRegionDetector` establishes the normalized contour-to-`TargetDetection` output pattern.
**Design decision:** create a provider-free `ShapeDetector` based on a thresholded grayscale frame, optional morphology, external contours, polygon approximation, and generic area/vertex/circularity/solidity filters. It will report bounded geometry metrics as evidence and rank surviving candidates by fill/solidity quality. The descriptor will be available because no optional backend is required.
**Next task:** document the behavior and add an isolated red test for circle/rectangle contour filtering before registering the detector or altering the existing unavailable `shape` descriptor.
## [SYNC] 2026-09-04 — RapidOCR 实际文字定位 Provider

### A. SYNC 范围声明

**触发任务：** 为通用感知引擎接入可选、延迟加载的 RapidOCR 后端，使整屏或 ROI 图像中的文字可输出统一位置标注；补足单元与真实后端冒烟测试。

**直接变更文件：** `core/perception/providers/rapidocr.py`、provider 导出/注册文件、`tests/test_perception_rapidocr_provider.py`、可选 OCR 依赖清单，以及对应设计、断点和代码库索引文档。

**预计连带影响：** `FrameContext -> OcrProvider -> OcrSpan -> ProviderBackedOcrDetector -> TargetDetection` 感知链；不修改输入、GUI、坐标映射和游戏工作流。
### C. SYNC 结果

**连带重读文件：** `core/perception/providers/contracts.py`、`core/perception/providers/__init__.py`、`core/perception/providers/builtins.py`、`core/perception/algorithms/ocr_adapter.py`、`core/perception/builtins.py`、`core/perception/engine.py`、现有 provider/OCR 相关测试与断点文档。

**实现结果：** 新增可选 `RapidOcrProvider`。它在第一次识别时才导入并创建 RapidOCR ONNX 模型，后续帧复用同一个引擎；将文字四边形转换为统一 `OcrSpan` bbox；支持全屏与可配置 ROI，并把 ROI 局部坐标恢复为原 `FrameContext.coordinate_space`。`ProviderBackedOcrDetector`、融合、确认、选择、坐标映射、GUI 与工作流边界保持不变。

**参数与性能结论：** profile 的 `provider_parameters` 可传 `roi`、语言结果标签和 RapidOCR `backend_options`；底层 `engine_options` 支持线程等模型初始化设置且只在首次构建时读取。当前机器生成的 900×260 英文图基准中，默认 warm inference 约 3.09s，`intra_op_num_threads=4`/`inter_op_num_threads=1` 约 0.72s；这是本机基准，实际游戏应结合 ROI 与 metadata 的 `elapsed_seconds` 调参。

**验证：** 红测试先按预期报 `ModuleNotFoundError: core.perception.providers.rapidocr`；实现后 RapidOCR 专项 6/6 通过，provider/catalog 联测 12/12 通过，完整 perception 测试集 68/68 通过，`compileall -q core/perception`、公共导入 smoke 与真实 ONNX 文本定位基准通过。真实结果识别出 `ENTER MAP`，bbox 为 `(72.0, 66.0, 549.0, 105.0)`。

**CODEBASE.md 同步：** 更新 C4 OCR 调用路径、provider 文件职责与导出、默认 catalog、RapidOCR 全部函数索引、完整数据流、外部集成/错误边界、数据契约、风险条目和回归测试索引；新增设计文档 `docs/plans/2026-09-04-rapidocr-provider-design.md`。

**下一步：** P4 仍待实现 feature 与 motion adapter；随后 P5 将标准 `TargetDetection` 接入运行时坐标映射和校准，P6 才让 GUI workbench 显式选择/配置该 provider。不要在这之前把流放之路特定 OCR 文本、点击或场景规则写进 `RapidOcrProvider`。
## [2026-09-04] OCR model resource switching

### A. This-round scope declaration (before reading)

**Goal:** Turn the verified Traditional-Chinese-capable RapidOCR recognition model into a generic, explicit model resource: a named manifest entry, verified local resolution, and a separate installer. Keep the existing `RapidOcrProvider` API and its unified `OcrSpan` / `TargetDetection` output intact.

**Planned target files:**

- `core/perception/providers/rapidocr_models.py` — model manifest and local-path/checksum resolver.
- `core/perception/providers/rapidocr.py` — inspect only to preserve provider compatibility; alter only if a small integration seam is necessary.
- `core/perception/providers/__init__.py` — public exports, if that is the project convention.
- `utils/install_perception_ocr_model.py` — explicit, atomic downloader and verifier.
- `tests/test_perception_rapidocr_models.py` — offline resolver and installer tests.
- `tests/test_perception_rapidocr_provider.py` — inspect existing OCR integration contract and add a local optional Traditional-Chinese smoke test only if it fits.
- `requirements-ocr.txt`, `.gitignore`, `CODEBASE.md`, `docs/PERCEPTION_ENGINE_CHECKPOINT.md`, and a focused design note — inspect/update only where the new resource contract requires it.

**Questions to answer:**

1. How is the current RapidOCR provider constructed and injected without import-time OCR dependencies?
2. What public configuration seam can select an installed model without binding to a game, scene, or target word?
3. Which test conventions and documentation sections must be updated to keep the perception architecture truthful?
### C. Findings after first focused read

**Key findings (verified):**

- `RapidOcrProvider` delays importing `rapidocr_onnxruntime` and constructing `RapidOCR` until its first `recognize` call. Its constructor already accepts a copied `engine_options` mapping, so a model resolver can return `rec_model_path` without changing frame recognition, ROI coordinate restoration, or unified `OcrSpan` output.
- `ProviderBackedOcrDetector` is exercised by the provider test and continues to consume only provider output. Model selection therefore belongs outside the detector and outside every game workflow.
- Provider-package public exports are explicit in `core/perception/providers/__init__.py`; the resolver should be exported there after implementation.
- The real RapidOCR test is optional and its default model only recognizes an ASCII image. A Traditional-Chinese smoke test must also remain optional and only run when the explicitly installed external model file exists.
- The worktree contains unrelated active `virtual_gamepad` and event changes. This OCR model-resource change will stage only its own exact files.

**Corrected prior conclusion:** Passing `rec_model_path` directly is enough for a one-off experiment, but it does not make a reusable model safely selectable. A manifest plus an explicit checksum-verified local resolver is needed so profiles/configuration can name a stable model ID rather than depend on an opaque local path.

**Next focused read:** inspect the existing OCR requirement, ignore rules, tests/helpers, and perception documentation to set installer location, asset exclusion, error conventions, and CODEBASE documentation scope before adding code.
### C. Findings after resource/documentation read

**Key findings (verified):**

- `requirements-ocr.txt` intentionally isolates `rapidocr-onnxruntime==1.4.4`; the new model registry must not add an automatic dependency or change base requirements.
- `.gitignore` has no perception-model asset rule. The installer destination must be ignored so downloaded ONNX binaries cannot be accidentally staged.
- The perception checkpoint defines an explicit provider/adapter boundary and P4 is still in progress. A model spec is provider composition data: it may produce backend options, but must not perform text matching, screen capture, coordinate mapping, or actions.
- The existing RapidOCR design already treats model initialization as a composition-time decision through `RapidOcrProvider(engine_options=...)`. The missing piece is a stable model ID, asset integrity validation, and operator-facing installation path.
- `CODEBASE.md` has an existing RapidOCR provider description and provider-test entry; it needs a targeted SYNC addition for the model manifest and installer after code changes, not a broad rewrite.

**Corrected prior conclusion:** A `language` value in per-call `provider_parameters` is only a result label. It does not select OCR recognition language or swap the loaded ONNX model; model selection must be supplied through the provider's construction options.

**Next focused read:** inspect utility CLI patterns and perception exception/testing conventions, then write a red offline contract test before the model manifest and installer implementation.
### C. Utility discovery update

**Key finding (verified):** The repository has no tracked `utils/` installer convention. Perception provider tests are all standard `unittest` modules under `tests/`, so the new installer will use a small standard-library CLI at `utils/install_perception_ocr_model.py` and its test will import the function-level implementation directly rather than spawn a process or access the network.

**Next action:** create offline red tests covering named model lookup, absent/corrupt assets, immutable engine option construction, and a downloader's temporary-file/atomic-replace behavior using a local fake URL opener.
### C. Installer CLI debugging record

**Reproduction (verified):** Running `python utils/install_perception_ocr_model.py --help` from the repository root exits with `ModuleNotFoundError: No module named 'core'`. The new direct-execution regression test reproduces the same failure.

**Pattern analysis (verified):** Existing executable utilities such as `utils/route_context_probe.py`, `utils/portal_screen_probe.py`, and `utils/input_probe.py` resolve the repository root from `__file__` and add it to `sys.path` before importing `core`.

**Hypothesis:** The installer needs the same project-root bootstrap before its `core.perception` imports. This is the only difference between it and working utility CLIs; adding that bootstrap will make direct invocation work without changing its package-import behavior.

**Next action:** apply that one bootstrap, rerun the isolated CLI test, then retry the explicit model installation.
## [SYNC] 2026-09-04  — Traditional-Chinese RapidOCR model resource

### A. SYNC scope declaration

**Triggering implementation:** Add a named PP-OCRv6 multilingual small model resource, integrity resolver, explicit atomic installer, public exports, and Traditional-Chinese position regression coverage.

**Directly changed source/test files:**

- `core/perception/providers/rapidocr_models.py`
- `core/perception/providers/__init__.py`
- `utils/install_perception_ocr_model.py`
- `tests/test_perception_rapidocr_models.py`
- `tests/test_perception_rapidocr_provider.py`

**Associated non-source updates:** `.gitignore`, `docs/PERCEPTION_ENGINE_CHECKPOINT.md`, `docs/plans/2026-09-04-rapidocr-multilingual-model-resource-design.md`, and `CODEBASE.md`.

**Impact analysis to confirm:** The resolver must remain a composition-only resource layer; `RapidOcrProvider`, `ProviderBackedOcrDetector`, profile JSON, GUI, coordinate mapping, and workflows must retain their existing boundaries. The new CLI must be executable both directly and as imported test code.
### C. SYNC result

**Coupled files reread:** `core/perception/providers/rapidocr_models.py`, `core/perception/providers/__init__.py`, `utils/install_perception_ocr_model.py`, `tests/test_perception_rapidocr_models.py`, and `tests/test_perception_rapidocr_provider.py`.

**Boundary verification (verified):**

- The named model catalog performs only metadata lookup, local SHA-256 checking, and defensive engine-option construction. It has no RapidOCR import, model download, OCR inference, target text, screen capture, GUI, coordinate mapping, or input dependency.
- `RapidOcrProvider` was not changed: it still owns lazy engine construction and emits raw `OcrSpan`; the existing OCR adapter remains the only component that applies a text predicate and converts provider evidence into `TargetDetection`.
- Provider composition remains runtime-only. Target profiles still need no model object and no raw model path; `rec_model_path` cannot be smuggled through resolver overrides.
- The downloader is explicit and direct-executable. It verifies a temporary same-directory file before `os.replace()`, and tests show that a corrupt replacement leaves an old final asset untouched.

**Verification:**

- `D:\ACloud\.venv\Scripts\python.exe -m unittest discover -s tests -p 'test_perception*.py'` — 76 passed.
- Real installed-model smoke test — passed: `開始儀式` and `進入異界地圖` were each recognized with original-image bounding boxes.
- `compileall -q core/perception utils/install_perception_ocr_model.py tests/test_perception_rapidocr_models.py tests/test_perception_rapidocr_provider.py` — passed.
- Public import smoke test — passed.
- Re-running the explicit installer against its verified local asset — passed without a re-download.
- `git diff --check` — passed; existing repository LF/CRLF warnings remain non-errors.

**CODEBASE.md synchronized:** provider public surface, new model-resource module, installer behavior, optional OCR integration flow, regression contracts, and the model-resolution latency risk are updated. `docs/PERCEPTION_ENGINE_CHECKPOINT.md` and the focused design record the handoff point.

**Next task:** wire the named provider/model selection into the P6 perception workbench/application-composition UI, keeping profiles serializable and model resources outside game workflows.
## [SYNC] 2026-09-04 — staged whitespace correction

### A. SYNC scope declaration

**Triggering change:** Remove one trailing blank line at EOF in `core/perception/providers/rapidocr_models.py` after staged `git diff --check` identified it.

**Impact assessment:** Formatting-only change; no signature, algorithm, runtime dependency, API, profile, provider, or flow behavior changes. Existing model-resource CODEBASE entries remain accurate.

### C. SYNC result

The EOF whitespace was removed, the model-resource source was re-staged, and the staged diff check is rerun before commit. No CODEBASE.md semantic update is needed for this formatting-only correction.
## [2026-09-04] Desktop OCR-to-action mapping proof

### A. This-round scope declaration (before reading)

**Goal:** Prove the new generic architecture across a real desktop action without adding game rules: capture the current desktop, find the literal target text `梦之形` through the existing OCR provider, map capture coordinates to physical screen coordinates, then drive a deliberately small mouse double-click action adapter. The proof must report every coordinate and mapping decision so accuracy can be checked.

**Planned target files:**

- Existing capture, coordinate, and input modules — inspect their current coordinate contracts and safe action seams before reuse.
- `core/spatial/` — extend only with a general source-frame-to-screen mapper if the existing calibration primitives cannot represent it.
- `core/perception/providers/` and OCR adapter — inspect only; recognition remains independent of this desktop proof.
- A new generic action package/module — no target word or desktop behavior inside it; it receives a mapped point plus an action request.
- A small desktop demonstration workflow/script and focused tests — compose capture, recognition, mapping, and action with the target `梦之形` only as demonstration configuration.
- `docs/`, `CODEBASE.md`, and this checkpoint log — record schema, safety behavior, and verification.

**Questions to answer:**

1. Which existing screen capture path exposes physical-pixel dimensions and how does it relate to Windows DPI?
2. Does the existing spatial model already represent an identity/affine capture-to-screen mapping, or is a minimal independent mapping DTO needed?
3. Which existing mouse backend can issue a correctly scoped double click without embedding action policy into perception or spatial modules?
4. How can the proof avoid acting if OCR finds zero, several ambiguous, or out-of-screen candidates?
### C. Capture/input boundary findings

**Key findings (verified):**

- `SquareScreenCapture.capture(x, y, width, height)` already documents physical-pixel input coordinates and returns BGR NumPy images. It provides a usable capture primitive but does not attach a `FrameContext`, a desktop rectangle, DPI evidence, or source-to-destination transform metadata.
- `core.spatial.models` currently supplies immutable points, anchor pairs, and a positive `WindowRect`, but no result object that says a detected source point has been mapped to a physical screen coordinate.
- `InputDriver` already has Win32 `GetSystemMetrics`, absolute `SetCursorPos`, `mouse_down`, `mouse_up`, and safe diagnostic helpers. Its existing `click()` is a device implementation detail, not an action contract; it should be wrapped instead of importing perception data into it.
- `screen_bounds.clamp_screen_pos()` is legacy tuple clamping. It should not silently correct a test pipeline point, because silently clamping would hide a bad mapping. The new mapper must reject out-of-bounds results explicitly.

**Corrected prior assumption:** The capture backend's comments say physical pixels, but that fact is not yet represented in the shared schema. The proof needs a `ScreenGeometry` provider/DTO that names the physical destination rectangle and DPI observation, rather than assuming `FULL_SCREEN` always means identity mapping.

**Next focused read:** inspect the existing affine calibration implementation and click execution composition, then choose the narrowest extension compatible with them.
### C. Calibration-model finding

**Key finding (verified):** `core.spatial.calibration.CoordinateMapper` already owns the right generic abstraction: transforms are explicitly keyed by `CoordinateSpace`, identity mapping is explicit when spaces match, and its `AffineTransform` supports source-to-target point conversion. The desktop proof should build on this module rather than introduce a parallel mapping engine.

**Required extension (inferred):** preserve `CoordinateMapper` as an unconcerned transform registry, then add a small desktop-facing mapper/geometry layer that derives a scale/translation transform from one captured frame and a current physical desktop rectangle, validates the mapped point against that rectangle, and returns diagnostic evidence. This avoids changing `CoordinateSpace` enum meanings before multi-display/window support is designed.

**Next focused read:** inspect the current click executor and input controller construction so the new device-agnostic action adapter wraps existing Win32 behavior rather than duplicating it.
### C. Action-adapter boundary findings

**Key findings (verified):**

- Existing `click_pipeline.execute_click()` is specifically coupled to movement navigation: it applies a bottom guard, optional clamping/focus behavior, and a `MotionController` diagnostics structure. Reusing it would incorrectly add navigation policy to a generic visual action proof.
- `click_executor.send_click()` is also a single-click implementation with fallback and optional confirm-click semantics. It is useful as backend reference but not the generic double-click action contract required here.
- `InputDriver` is the narrow reusable platform primitive. A new action adapter can depend on a minimal mouse protocol (`move_to`, `mouse_down`, `mouse_up`, optional `cursor_pos`) and produce a generic result without importing controller, perception, or navigation code.

**Architecture decision:** create a new `core/actions/` package for device-agnostic action DTOs plus a mouse adapter. Keep `core/input/` intact as a legacy/navigation implementation. The desktop proof will use an injected mouse adapter, so tests never touch the real cursor and a later controller/gamepad adapter can implement the same action request boundary.

**Next action:** write the approved TDD implementation plan with exact files and verification commands, then implement only that plan.
### C. Coordinate-space contract correction

**Key finding (verified):** `FrameContext` does not infer width/height from an image; a frame source must populate both explicitly. `TargetDetection` already carries a two-number center plus `CoordinateSpace`, while the shared enum has `FULL_SCREEN` but no way to distinguish a screenshot's image-pixel plane from the physical desktop input plane.

**Corrected architecture decision:** add `CoordinateSpace.PHYSICAL_SCREEN` as an additive, non-breaking destination space. A `FrameContext` captured from the desktop remains `FULL_SCREEN`; `DesktopCoordinateMapper` emits `PHYSICAL_SCREEN`. This makes it impossible for the generic mouse adapter to accidentally accept an unmapped screenshot point, while leaving all old `FULL_SCREEN` callers unchanged.

**Next action:** start the first TDD tracer bullet for `DesktopCoordinateMapper`: a source-frame center maps through an offset/scale desktop geometry to a physical-screen point with diagnostic evidence.
### C. Spatial/action tracer-bullet result

**Completed and verified:**

- `CoordinateSpace.PHYSICAL_SCREEN` now separates a captured `FULL_SCREEN` image plane from an input-injection destination without altering legacy coordinate values.
- `DesktopCoordinateMapper` uses the existing `AffineTransform` to derive an offset/scale mapping and produces immutable `MappedPoint` diagnostics. It rejects unknown spaces, source out-of-bounds points, and destination out-of-bounds results instead of silently clamping.
- `DesktopFrameSource` accepts injectable geometry and capture providers, produces a dimensioned `FrameContext(FULL_SCREEN)`, and has a Windows default that observes virtual desktop bounds with best-effort process DPI awareness. The test did not invoke the Windows backend.
- The new `core.actions` boundary accepts only a `MappedPoint(PHYSICAL_SCREEN)` and a generic `ActionRequest`; its fake-device test proves exact move/double-click ordering with no perception imports or real input.

**Verification:** 3 focused tests pass. No real capture, OCR, cursor move, click, or desktop state change has occurred.

**Next focused read:** locate workflow package conventions, then add an injected OCR-provider composition test that proves a unique text result maps to a dry-run report while ambiguous results produce no action request.
### C. Real desktop proof result

**Live verification (verified):**

- The real desktop capture reported `2560 × 1600`; the Win32 virtual desktop geometry reported the same physical rectangle and a DPI observation of `1.5 × 1.5`.
- The explicitly composed PP-OCRv6 provider found one exact `梦之形` label with `0.999948779741923` confidence. Its source center was `(633.5483703613281, 532.0513000488281)` and the mapper emitted the same physical-screen point because the capture and destination dimensions matched.
- The action adapter rounded only at the input boundary to `(634, 532)`, moved once, and sent exactly two left-button down/up pairs with a 100ms inter-click delay. Its report status was `executed`.
- A separate, read-only Win32 foreground-window query afterward found an `SDL_app` window, consistent with the requested desktop shortcut having opened. That independent diagnostic process was DPI-unaware and read cursor `(423, 355)` / metrics `1707 × 1067`; those are the physical result divided by 1.5, confirming why the capture/input host must establish DPI awareness before it creates its mouse backend.

**Corrected implementation constraint:** Physical coordinate agreement is process-level, not merely a mapper formula. The desktop proof is correct because `DesktopFrameSource()` establishes DPI awareness before `InputDriver()` is created in `build_live_proof()`. Future composition must retain this startup order or centralize the awareness bootstrap; legacy input behavior must not be silently changed in this slice.

**Next task:** run broader automated checks, make the CLI's diagnostic JSON encoding unambiguous on legacy Windows consoles, synchronize architecture documents, and create a narrowly scoped commit without staging unrelated virtual-gamepad/event work.
## [SYNC] 2026-09-04 — desktop OCR / mapping / mouse proof

### A. SYNC scope declaration

**Triggering implementation:** Add an explicit physical-screen coordinate space, pure desktop coordinate mapper, live desktop frame source, device-neutral mapped-point action DTOs, mouse double-click adapter, and a thin OCR proof workflow/CLI.

**Directly changed source files:**

- `core/perception/models.py`
- `core/spatial/desktop_mapping.py`, `core/spatial/__init__.py`
- `core/platform/desktop_frame_source.py`, `core/platform/__init__.py`
- `core/actions/models.py`, `core/actions/mouse.py`, `core/actions/__init__.py`
- `workflows/__init__.py`, `workflows/desktop_ocr_action_proof.py`
- `utils/run_desktop_ocr_action_proof.py`

**Directly changed tests/docs:** desktop mapper/frame/action/workflow tests and the design/implementation-plan documents.

**Impact expansion checked:** OCR provider and adapter remain unchanged; `CoordinateSpace` grows one additive destination value; legacy `core/input` navigation pipeline is not redirected; the new workflow creates the only link between perception, spatial mapping, and mouse action. Windows DPI awareness is process-scoped and therefore documented as composition order, not hidden as a change to legacy input behavior.
### C. SYNC spatial mapping read

**Verified implementation detail:** `DesktopCoordinateMapper` is a pure scale-plus-translation specialization of the existing `AffineTransform`; it computes independent x/y scales from a captured image extent and physical `ScreenGeometry`, requires the source to be `FULL_SCREEN`, uses half-open bounds in both planes, then emits a mapping-proof `MappedPoint(PHYSICAL_SCREEN)`. `ScreenGeometry` and `MappedPoint` defensively validate numbers/spaces and freeze diagnostics, so later action adapters cannot mutate transform evidence.

**CODEBASE.md update required:** add the new spatial file, model contracts, mapping algorithm, and a capture→OCR→mapping→action flow description.
### C. SYNC capture/action/workflow read

**Verified implementation detail:**

- `WindowsDesktopGeometryProvider` establishes best-effort per-monitor DPI awareness during construction, reads virtual-screen metrics, and reports a DPI observation; `DesktopFrameSource` passes exactly that rectangle to the existing capture backend, validates the resulting image shape, and writes source dimensions plus physical-geometry metadata into `FrameContext`.
- `ActionRequest` is restricted to generic action kind, mapped point, and timing. `MouseActionAdapter` accepts only `PHYSICAL_SCREEN`, rounds once at the device boundary, moves exactly once, then produces zero or two click pairs. It has no capture, OCR, selection, clamping, or window-focus policy.
- `DesktopOcrActionProof` is the single thin composition layer: it builds the existing provider-backed exact OCR detector, requires exactly one qualified candidate, maps the candidate center, and calls its injected adapter only under `execute=True`. Its report exposes all safety outcomes without mutating profiles or core providers.

**CODEBASE.md update required:** add platform/actions/workflow module entries, exact action/mapping/capture algorithms, external Win32/MSS integration constraints, full proof flow, and the DPI startup-order risk.
### C. SYNC result

**Coupled files reread:** `core/spatial/desktop_mapping.py`, `core/platform/desktop_frame_source.py`, `core/actions/models.py`, `core/actions/mouse.py`, and `workflows/desktop_ocr_action_proof.py`; existing capture, input, affine calibration, and OCR adapter seams were also compared before composition.

**Verification:**

- `D:\ACloud\.venv\Scripts\python.exe -m unittest discover -s tests -p 'test_perception*.py'` — 76 passed.
- New desktop mapper/frame/action/workflow regression suite — 5 passed.
- `compileall` for action, perception, platform, spatial, workflow and proof CLI modules — passed.
- Public import smoke check — passed.
- Real desktop dry-run after all code changes — passed: one exact `梦之形` detection at `(633.55, 532.05)`, `2560×1600` source/physical dimensions, identity physical mapping, and no action.
- One user-authorized real action run — passed: one move to `(634, 532)` plus exactly one double click; follow-up read-only window diagnostic found the opened SDL application.
- `git diff --check` — passed; existing repository LF/CRLF warnings are non-errors.

**CODEBASE.md synchronized:** added directory entries, spatial/capture/action/workflow/CLI contracts, complete desktop proof data flow, the external Win32/MSS/DPI integration behavior, and two concrete risks. `docs/PERCEPTION_ENGINE_CHECKPOINT.md` now marks P5 in progress with the completed desktop proof slice.

**Next task:** retain this proof as the P5 baseline, then extend mapping to specific game windows/viewports, runtime anchor calibration, and UI calibration preview; feature/motion recognition adapters remain independent P4 work.
## [2026-09-04] Cross-process input-work review

### A. This-round scope declaration (before reading)

**Goal:** Read the other active process's uncommitted input/virtual-gamepad work without editing it. Establish which behavior it implements, its public boundaries, and whether it overlaps with or can later become an adapter beneath the newly committed generic `core.actions` contract.

**Read-only target files:**

- `virtual_gamepad/` changed source, configuration, UI, host, tests, and documentation files as identified by Git.
- `core/events/window_finder.py` and `core/events/tests/` only to distinguish its related work from the perception/spatial/action mainline.
- Current Git status and diff summaries to identify ownership boundaries before any detailed file read.

**Questions to answer:**

1. Does the other process implement physical/virtual controller routing, mapping profiles, or an independent action abstraction?
2. Does it change the generic perception/spatial/action pipeline or only its own virtual-gamepad subsystem?
3. What future integration seam would allow a `GamepadActionAdapter` to consume `core.actions` requests without merging the subsystems prematurely?
### C. Cross-process first-read findings

**Key findings (verified):**

- The other process's design explicitly treats `virtual_gamepad/host` as a privileged, independent runtime and treats programmatic control as a Python named-pipe client. It proposes a future `core.actions.VirtualGamepadActionAdapter`, but the reviewed `virtual_gamepad_client.py` currently exposes raw controller operations (`button`, `set_axis`, `set_trigger`, `set_state`, `reset`, `pause`, `heartbeat`) rather than importing or implementing the newly committed `core.actions` contract.
- It supports two independently addressable controller slots (`controller=1|2`), per-call `source`, and optional TTL. That is a strong lower-level transport substrate for a future gamepad action adapter: workflow code should not call it directly once an adapter exists.
- The scope is not merely UI: it includes two ViGEm targets, shared physical input forwarding, controller-specific F7/F8 pause controls, global F9 reset, multiple named-pipe clients, profile editing, and host lifecycle/elevation safety.
- The other process currently has no tracked modifications under `core/perception`, `core/spatial`, or `core/actions`; direct code overlap with the generic OCR/mapping/mouse proof is therefore absent.

**Corrected prior description:** Saying the other task was simply “unrelated virtual gamepad work” was too coarse. It is separate in implementation ownership, but it is a future concrete input backend for the main automation architecture. It should remain isolated until its host/client contract and safety tests are stable, then be connected through one `GamepadActionAdapter` in `core.actions`—not through perception, spatial mapping, or workflow-specific named-pipe calls.

**Next focused read:** inspect the C# controller registry and mapping runtime to confirm slot/source/TTL ownership, and inspect host composition for the concurrent-client and lifecycle seam proposed by its design.
## [Review continuation] 2026-09-04

### A. Scope declaration (before source review)

**Task:** Read-only review of the concurrent `virtual_gamepad` implementation before deciding how it can connect to the reusable action layer.

**Files selected for this pass:**
- `virtual_gamepad/host/src/VirtualGamepadHost/Protocol/CommandRouter.cs` — establish command routing, validation, and controller targeting.
- `virtual_gamepad/host/src/VirtualGamepadHost/Protocol/NamedPipeServer.cs` — verify multi-client named-pipe behavior and shutdown/error handling.
- `virtual_gamepad/host/src/VirtualGamepadHost/State/SafetyController.cs` — establish TTL, reset, and fail-safe semantics.
- `virtual_gamepad/host/src/VirtualGamepadHost/Runtime/ControllerSlot.cs` — establish per-slot ownership and lifecycle boundaries.

**Questions to resolve:** whether simultaneous UI and automation clients are safely supported; how input sources collide or expire; whether controller-specific and global reset paths are sound; and the correct future adapter boundary under `core/actions`.
### C. Findings — command-routing pass

**Verified:** `CommandRouter.Handle()` dispatches every command through a selected `ControllerSlot`; omitted `controller` defaults to slot `1`, while `emergency_reset` intentionally reaches `ControllerRegistry.EmergencyResetAll()`.

**Verified:** raw actuator commands (`button`, `set_axis`, `set_trigger`, `set_state`, `heartbeat`) deserialize a `source` plus optional positive `ttl_ms`, pass their values to the selected slot's `StateStore`, and return the resolved controller number. Invalid payloads, values, and unsupported types are converted to protocol failures rather than escaping the pipe handler.

**Verified:** `start` alone checks virtual-device readiness; direct input-setting commands do not check that the slot is running or device-ready. The runtime/state classes remain the required next read to determine whether this is harmless queued state or a safety gap.

**Architecture conclusion:** this routing layer is a device-backend protocol boundary. A later `core.actions.VirtualGamepadActionAdapter` may call it through the Python named-pipe client, but perception, spatial mapping, and workflows must not call it directly.

**Coverage:** `CommandRouter.cs` — deeply reviewed for dispatch, validation, controller selection, and failure mapping; state mutation conflict/expiry behavior remains delegated to `StateStore` and `SafetyController`.

**Next pass:** read named-pipe connection lifetime plus per-slot safety/state classes, then verify concurrent clients, source collision policy, TTL expiry, and shutdown.
## [Review continuation] 2026-09-04 — transport and safety

### A. Scope declaration (before source review)

**Files selected for this pass:**
- `virtual_gamepad/host/src/VirtualGamepadHost/Protocol/NamedPipeServer.cs` — pipe connection concurrency, read/write ownership, cancellation, shutdown.
- `virtual_gamepad/host/src/VirtualGamepadHost/State/SafetyController.cs` — controller lifecycle and reset actions.
- `virtual_gamepad/host/src/VirtualGamepadHost/Runtime/ControllerSlot.cs` — per-controller state object composition.

**Questions:** can a UI status connection coexist with automation commands, and do lifecycle/reset semantics safely clear device state for each controller?
### C. Findings — transport and safety pass

**Verified:** `NamedPipeServer.RunAsync()` creates a new `NamedPipeServerStream` with `MaxAllowedServerInstances`, detaches each accepted connection to `ServeClientAsync()`, and resumes accepting immediately. A status/UI client and an automation client can therefore be live at the same time; each connection has its own sequential JSON-lines reader/writer loop.

**Verified:** host cancellation is shared with the listener and every client handler. Listener shutdown waits for the tracked client tasks and each handler disposes its own pipe stream; ordinary client disconnects are swallowed without terminating the host.

**Verified:** each `ControllerSlot` owns a separate `StateStore`, `SafetyController`, and `MappingEngine`. `SafetyController` is per-slot locked: `Pause`, `EmergencyReset`, and `Fail` clear/disable state; ordinary `Reset` preserves a pre-existing paused state; `Start` resumes the store.

**Important remaining uncertainty:** simultaneous messages are routed concurrently once they arrive on different pipe connections. Whether writes to the same controller/source are serialized and how expired values are removed depends on `StateStore`, which has not yet been reviewed. The current code permits mutation commands even before a slot is `Running`; backend submission behavior still needs confirmation.

**Coverage:** `NamedPipeServer.cs` — deeply reviewed for client lifecycle; `SafetyController.cs` — deeply reviewed for lifecycle transitions; `ControllerSlot.cs` — fully reviewed (record composition).

**Next pass:** read `StateStore` and registry/backend tick behavior, then validate source arbitration, expiration, inactive-slot output, and reset propagation.
## [Review continuation] 2026-09-04 — source state and output fan-out

### A. Scope declaration (before source review)

**Files selected for this pass:**
- `virtual_gamepad/host/src/VirtualGamepadHost/State/StateStore.cs` — source merge, TTL expiration, thread safety, and snapshot semantics.
- `virtual_gamepad/host/src/VirtualGamepadHost/Runtime/ControllerRegistry.cs` — two-slot creation, backend update loop, per-slot/global reset.
- `virtual_gamepad/host/src/VirtualGamepadHost/Runtime/HostComposition.cs` — physical-input broadcast and host-wide lifecycle wiring.

**Questions:** how two clients or mappings combine their input, whether an inactive controller can emit a stale state, and whether reset/pause reaches all concrete virtual devices.
### C. Findings — source state and output fan-out

**Verified:** `StateStore` serializes all source access behind one lock. It merges buttons by OR, triggers by maximum, and each axis by greatest absolute magnitude (then most-recent sequence on ties). Incremental actuator commands expire after an explicit TTL or the 500 ms default; expired entries are removed on `Snapshot()`.

**Verified risk:** `StateStore.SetState()` differs from incremental commands: an omitted TTL produces a non-expiring source. That is suitable only for an explicitly persistent/manual-state contract; an automation action adapter must always set a finite TTL or explicitly clear its source. Otherwise a client disconnect can leave an input asserted until reset.

**Verified risk:** the initial `SafetyController` state is `Ready`, but its `StateStore` starts unpaused. `CommandRouter` accepts raw state-changing commands without requiring `Running`, and `ControllerRegistry.SubmitAll()` submits every slot snapshot without checking `RunState`. Therefore a raw pipe client can produce virtual-controller output before `start`; `pause` does neutralize it. This is an observable lifecycle-contract gap, not yet a change request against the other process.

**Verified:** default composition constructs exactly two independent slots, maps each physical event into every currently `Running` slot, and globally suppresses a physical event if any running slot maps it. Thus one keyboard/mouse mapping can intentionally control two characters at once; it cannot currently provide per-slot native-pass-through when both slots disagree.

**Verified:** emergency reset clears and pauses both slots; disposal cancels loops, waits for them, resets both slots, disposes raw input, then stops/disposes the backend.

**Coverage:** `StateStore.cs`, `ControllerRegistry.cs`, and `HostComposition.cs` — deeply reviewed for source merge, two-slot output, physical-input broadcast, and shutdown. `ReportLoop` remains unreviewed, so actual output tick timing and output-error failure behavior are still open.

**Next pass:** review the report loop and Python client/UI host-manager integration to establish actual execution cadence, command serialization, reconnection behavior, and current UI exposure of two-controller state.
## [Review continuation] 2026-09-04 — execution cadence and client contract

### A. Scope declaration (before source review)

**Files selected for this pass:**
- `virtual_gamepad/host/src/VirtualGamepadHost/Runtime/ReportLoop.cs` — submission frequency and backend failure behavior.
- `virtual_gamepad/client/python/virtual_gamepad_client.py` — Python-side request lifecycle, serialization, and error behavior.
- `virtual_gamepad/ui/virtual_gamepad_ui/main_window.py` — whether the UI gives both controller slots clear, independent visibility and control.

**Questions:** actual backend cadence and error handling; whether concurrent callers on one Python client can cross responses; and whether the current UI fulfills the requested two-controller configuration/operation model.
### C. Findings — execution cadence and client/UI contract

**Verified:** `ReportLoop` submits snapshots every 8 ms (target 125 Hz). In the two-slot runtime it delegates to `ControllerRegistry.SubmitAll()`. The loop has no local exception-to-fail-safe conversion, so a backend exception would end the report task and thereby end `HostComposition.RunAsync()`; disposal will subsequently perform the global emergency reset.

**Verified:** `VirtualGamepadClient` serializes a request/write/read response pair with one Python lock, so concurrent callers sharing one client cannot receive each other's response. It can independently connect to the host pipe, matching the server's multi-client design. A broken connection becomes `VirtualGamepadError`; there is no transparent in-request retry, while the UI detects failure and reconnects on its next 50 ms refresh cycle.

**Verified:** the UI has one visual editor with an explicit Controller 1 / Controller 2 selector, two separate persistent profiles, two live status indicators, and selected-slot Start/Pause. It applies both saved profiles at initial connection and its emergency-reset/close actions reset both controllers. The same key may be bound in both profiles, so the host's broadcast behavior can drive two characters concurrently.

**UI limitation (not a defect):** it is a switchable single editor rather than two simultaneously visible configuration canvases. This matches the later “switch controller 1 / controller 2 on the page” requirement, but if the desired meaning of “two interfaces” is side-by-side editing, that remains a product/UI decision rather than a host limitation.

**Coverage:** `ReportLoop.cs`, `virtual_gamepad_client.py`, and `main_window.py` — deeply reviewed for cadence, request serialization/reconnection behavior, and two-controller UI exposure.

**Review result:** the parallel implementation is a viable independent virtual-input backend. It should remain outside the generic perception/spatial modules and be connected later only via a device-neutral `core.actions.VirtualGamepadActionAdapter`; before that connection, its lifecycle guard and persistent `set_state` TTL contract should be resolved and covered by host integration tests.
## [Documentation sync] 2026-09-04 — virtual gamepad review boundary

### A. Scope declaration (before documentation review)

**Goal:** inspect the existing action-layer architecture index and record only the verified integration boundary for the concurrently developed `virtual_gamepad` subsystem. No active virtual-gamepad source/configuration file will be edited.

**Files selected:**
- `CODEBASE.md` — find the existing generic action/spatial architecture section to update with the verified backend boundary.

**Intended result:** preserve the rule that workflows depend on `core.actions` contracts, while the named-pipe host/client remains an optional concrete execution backend.
### C. Documentation sync result

**Verified documentation update:** `CODEBASE.md` now records the inspected virtual-gamepad host/client/UI files and a clearly marked *reserved, not-yet-wired* action-to-gamepad flow. It preserves the current generic boundary: workflow → future device-neutral action adapter → Python pipe client → host → ViGEm.

**Risk registered:** before an adapter is added, resolve and test the raw-command lifecycle guard and the non-expiring no-TTL `set_state` behavior. The documented future adapter must supply a distinct source identity and a finite TTL for automation input.

**Files changed by this review only:** `CODEBASE.md` and this append-only `ITERATION_LOG.md`; no file belonging to the concurrently running virtual-gamepad implementation was changed, staged, reverted, or committed.
## [Status review] 2026-09-04 — modular foundation and mapping scope

### A. Scope declaration (before source/document review)

**Question:** which mainline modules remain, and does “map mapping” already exist?

**Files selected:**
- `docs/PERCEPTION_ENGINE_CHECKPOINT.md` — authoritative P0–P9 roadmap/status.
- `CODEBASE.md` — verified coordinate-mapping and legacy-navigation boundaries.
- `docs/plans/2026-09-04-desktop-ocr-action-mapping-proof-design.md` — distinguish the shipped full-desktop proof from window/viewport calibration work.

**Decision to make from evidence:** separate complete desktop screenshot → physical mouse mapping from unfinished game-window/viewport mapping and from the legacy minimap/world-navigation problem.
### C. Status-review findings

**Verified terminology correction:** “mapping is implemented” is true only for the tested whole-desktop path: a `FULL_SCREEN` screenshot target maps through an explicit affine transform to a `PHYSICAL_SCREEN` pointer coordinate and can drive the minimal mouse adapter. It is not yet a complete game-window/viewport calibration system, and it is separate from legacy minimap-to-world navigation.

**Verified remaining P4:** feature/keypoint matching and motion/frame-difference adapters remain absent; ML object detection is only a reserved provider/adapter seam. Color, template, shape, OCR adapter, optional RapidOCR backend, and a Traditional-Chinese model resource are present.

**Verified remaining P5:** game-window discovery/selection, client-area/viewport crop mapping, runtime anchor calibration, multi-display policy, and calibration UI preview are not implemented as the generic mapping path. Existing spatial primitives do not make those runtime composition choices.

**Verified mainline queue:** P6 engine-backed UI workbench; P7 legacy Portal/Loot/minimap bridges with regressions; P8 the configurable PoE event-chain state-machine workflows; P9 full dependency/error/regression audit. The action layer is intentionally still a proof slice (mouse move/double-click); keyboard and gamepad adapters have not joined it.

**Documentation:** no `CODEBASE.md` change is required for this read-only status check because the reviewed status and boundary are already recorded there. This log preserves the mapping distinction and next implementation sequence.
## [Architecture review] 2026-09-04 — full-screen mapping scope and frame preprocessing

### A. Scope declaration (before source review)

**Questions:** with a full-screen game, which P5 work is genuinely unnecessary versus still valuable; and is screenshot/image preprocessing already a standalone reusable core module?

**Files selected:**
- `core/spatial/desktop_mapping.py` — current full-screen transform contract.
- `core/perception/algorithms/color.py` — existing HSV/morphology preprocessing ownership.
- `core/perception/algorithms/template.py` — existing grayscale/edge/template preprocessing ownership.

**Review criteria:** distinguish generic, reusable operations from detector-private image preparation; identify the smallest independent preprocessing module that does not make all vision algorithms depend on OpenCV-specific policy.
### C. Findings — full-screen mapping and current preprocessing

**Verified mapping scope:** `DesktopCoordinateMapper` is deliberately restricted to `FULL_SCREEN → PHYSICAL_SCREEN`. It validates the source point and maps using independently observed width/height plus desktop left/top offset; a full-screen game on one display is exactly its intended current scope. Window discovery, client-area mapping, and anchor calibration are not prerequisites for that deployment mode.

**Verified remaining full-screen safeguards:** multi-monitor/virtual-desktop selection and focus validation are optional later policy choices, not a reason to delay the current pipeline. The mapper already carries virtual-desktop origin/scale evidence and rejects invalid/out-of-range results rather than guessing.

**Verified preprocessing gap:** there is no standalone preprocessing core API. `ColorRegionDetector.detect()` privately normalizes to BGR, converts to HSV, builds a hue-wrapping mask, and applies morphology; `TemplateDetector.detect()` privately normalizes to BGR, generates grayscale/Canny edges, and resizes templates. These are useful implementations but cannot currently be configured, cached, previewed, or shared as independent pipeline steps.

**Architecture direction:** add a new generic `core/perception/preprocessing/` layer before detectors, consisting of immutable preprocessing profiles/pipeline specifications, geometry-preserving frame artifacts, and OpenCV-backed operations. It must return source-coordinate metadata so crop/resize results can be mapped back; algorithms should consume either the original `FrameContext` or named preprocessing artifacts, never own global UI/game policy.

**Documentation:** no `CODEBASE.md` update yet; this is a proposed extraction, not an implemented module. The decision and verified existing ownership are recorded here for the next implementation task.
## [Legacy-chain architecture audit] 2026-09-04 — Torchlight map/navigation/events

### A. Scope declaration (before source review)

**Audit question:** confirm whether the existing small-minimap stitching, localization, routing, Portal, and Loot paths already use the new generic perception/spatial/action architecture.

**Initial discovery scope:**
- legacy navigation/minimap sources and their composition callers;
- Portal and Loot recognizer/handler sources and their callers;
- image-transformation helpers used outside `core/perception`.

**Required output:** a verified old-chain → new-core matrix, specifically identifying hard-coded scene/geometry assumptions, embedded preprocessing, result types, input calls, and absent compatibility bridges. The audit is read-only; virtual-gamepad work remains out of scope.
### C. Discovery findings — legacy chain inventory

**Verified inventory:** the legacy system is substantial and remains active under `core/vision`, `core/localization`, `core/navigation_tasks`, `core/events/types/portal`, and `core/events/types/loot`, with GUI composition under `gui/modes/navigation`. It is not a thin wrapper around `core/perception`.

**Important correction to the earlier simplification:** legacy HSV preprocessing is partly split already (`core/vision/hsv/preprocessing.py`, `masks.py`, `combined.py`, `params.py`), but it is a vision/minimap-local utility family rather than the new generic perception preprocessing contract. Portal and Loot additionally contain their own masks, ROI extraction, template preparation, scoring, and exclusion preprocessing under their event-type folders.

**Next review order:** first trace legacy minimap capture/localization/path routing; then read Portal and Loot entrypoints/pipelines; finally compare their result/action models to `PerceptionEngine`, `DesktopCoordinateMapper`, and `core.actions`.
## [Legacy-chain architecture audit] 2026-09-04 — localization algorithm

### A. Scope declaration (before source review)

**File selected:** `core/localization/localize_pipeline.py`.

**Reason:** this is the high-complexity bridge between minimap frames, map-package wall masks, template/feature matching, stateful position estimates, and the navigation runtime. It must be read alone to determine whether its image preparation/result contract is reusable or Torchlight/minimap-bound.

**Questions:** input coordinate assumptions, preprocessing ownership, output model, direct dependencies on `NavigationCore`, and whether it invokes the new perception/spatial/action layers.
### C. Findings — legacy minimap localization

**Verified:** `localize_frame(nav_core, minimap_img, player_pos=None)` is a stateful Torchlight/minimap localization pipeline, not an adapter to the new engine. It accepts a raw minimap array and a mutable `NavigationCore`, calls the legacy HSV recognizer itself, mutates localization/registration fields directly, and returns an untyped `(global_x, global_y, confidence)` tuple.

**Verified preprocessing coupling:** mask extraction (`nav_core.recognizer.extract_combined`), feature thresholds, wall-template scaling/closing, local/global search-area selection, and frame-to-frame displacement are all orchestrated inside the localization route. The source assumes a minimap center/player marker, `draw_scale`, a persisted wall-layer canvas, and navigator-owned confidence/jump policies.

**Verified new-architecture gap:** this path does not construct `FrameContext`, `TargetDetection`, `PerceptionRunResult`, `MappedPoint`, or `ActionRequest`; it imports neither `core.perception` nor `core.spatial` nor `core.actions`. It must be preserved behind a compatibility bridge rather than treated as already migrated.

**Next pass:** inspect the legacy HSV preprocessing package and `NavigationCore` composition boundary to distinguish reusable image primitives from minimap-specific wall/localization policy.
## [Legacy-chain architecture audit] 2026-09-04 — HSV preprocessing boundary

### A. Scope declaration (before source review)

**Files selected:**
- `core/vision/hsv/preprocessing.py` — image normalization/HSV preparation primitives.
- `core/vision/hsv/masks.py` — minimap mask construction and geometry suppression.
- `core/vision/hsv/combined.py` — public combined-mask composition used by legacy localization.

**Questions:** which operations are generic enough to migrate into the new preprocessing core, and which encode fixed player/minimap geometry or Torchlight-specific wall semantics.
### C. Findings — HSV preprocessing boundary

**Verified:** the old HSV code is split into helper files, but not into a generic module contract. Each function takes the mutable `recognizer` object and reads its internal flags, kernels, thresholds, color ranges, player geometry, and weights. It returns raw NumPy arrays with no profile schema, artifact identity, provenance, coordinate transform, cache boundary, or reusable pipeline API.

**Reusable primitives found:** gamma LUT, Gaussian/median blur, CLAHE, top-hat morphology, percentile normalization, brightness/contrast, HSV range masks, component-area filtering, Canny, morphology, dilation, and weighted mask composition. These can be re-homed as parameterized generic preprocessing operations.

**Minimap/Torchlight policy that must not be promoted unchanged:** wall/fog/player semantic masks; center-player fallback; erasing fixed circles around the player; saturation filtering only near that center; and the weighted wall+edge match mask. Those belong in a legacy minimap profile/adapter or a future target-specific configuration instance, not in universal preprocessing defaults.

**Confirmed answer so far:** the user is right that legacy preprocessing is only partially modularized within the old recognizer package; it has not been converted to the new configurable perception architecture.

**Next pass:** inspect Portal entrypoint/detector composition to verify whether it returns legacy event records and performs its own pre-processing/action sequence rather than standardized `TargetDetection` plus separate action execution.
## [Legacy-chain architecture audit] 2026-09-04 — Portal detection composition

### A. Scope declaration (before source review)

**File selected:** `core/events/types/portal/minimap_detector.py`.

**Reason:** this is the Portal recognition entrypoint that chooses legacy minimap detection modes and projects hits into navigation/event coordinates. It is the key proof point for whether Portal recognition already uses the generic `PerceptionEngine` result contract.

**Questions:** detector choices, preprocessing/result models, map-coordinate projection, and dependencies on legacy event/navigation state.
### C. Findings — Portal detection entrypoint

**Verified:** `PortalMinimapDetector` is a legacy `EventDetector`, not a generic perception adapter. It consumes `tick.raw_minimap_frame`, loads Portal-specific asset paths itself, chooses the Portal-specific `feature`, `shape_color`, template, or fallback mode, and returns `list[EventDetection]`.

**Verified coupling:** its constructor owns template resource loading, fixed scale candidates, logging, and Portal configuration. Its `detect()` owns fallback policy and passes raw arrays to dedicated Portal matchers; no `FrameContext`, `TargetProfile`, provider registry, `TargetDetection`, or `PerceptionEngine` is involved.

**Partial good news:** detection modes are already split into functions/packages, so their underlying algorithms can be harvested. But their current contracts are event-specific and their resource/preprocessing/fallback policy is embedded in the Portal feature.

**Next pass:** read Portal detection conversion/projection and runtime handler to confirm the old result reaches navigation and input through legacy event coordination rather than the new spatial/action contracts.
## [Legacy-chain architecture audit] 2026-09-04 — Portal result and action path

### A. Scope declaration (before source review)

**Files selected:**
- `core/events/types/portal/minimap_detection/conversion.py` — transform raw minimap hits into event detections.
- `core/events/types/portal/handler/runtime.py` — Portal event state/action orchestration.
- `core/events/types/portal/handler/interaction.py` — concrete Portal interaction action construction.

**Questions:** what coordinate/result schema crosses the old detection boundary, whether positions are projected through generic spatial mapping, and whether actions cross `core.actions` or remain legacy event commands.
### C. Findings — Portal result and action path

**Verified:** Portal conversion emits `EventDetection(event_type, local_minimap_pos, confidence, metadata)`, whose coordinate semantics are implicitly local-minimap pixels. It carries a raw bbox and many Portal scoring fields in metadata, but it is not `TargetDetection` and has no explicit `CoordinateSpace` contract.

**Verified:** Portal handling is already internally modular as a legacy event state machine (`move_near_event → align_on_portal → interact → wait_result`), but it uses `EventAction.move_to`, `EventAction.press_key("d")`, a global navigation task position, and a minimap environment signature. It does not use `MappedPoint`, `ActionRequest`, or a `core.actions` adapter.

**Important nuance:** the old Portal feature should not be discarded as a monolith. Its detector, conversion, movement, interaction, and completion code are useful legacy modules. Migration means wrapping/replacing the perception and coordinate boundaries while preserving its handler state machine and regression behavior.

**Next pass:** inspect the Loot detection entrypoint and its detection pipeline to confirm its own ROI/mask/template/exclusion preprocessing and identify which parts overlap the intended generic preprocessing core.
## [Legacy-chain architecture audit] 2026-09-04 — Loot detection entrypoint

### A. Scope declaration (before source review)

**File selected:** `core/events/types/loot/minimap_detector.py`.

**Reason:** determine whether Loot reuses generic perception or owns a separate minimap-specific recognition stack, and identify the result schema and coupling to event configuration/template assets.
### C. Findings — Loot detection entrypoint

**Verified:** `LootMinimapDetector` is a second, independent legacy perception stack. It owns Loot/minimap template assets, multi-scale prepared-template caches, player-marker exclusion templates, seed ROI detection, feature/blob mode switching, temporal presence confirmation, cached result reuse, async matching, and debug capture.

**Verified:** it consumes `tick.raw_minimap_frame` and produces `EventDetection` with `local_minimap_pos`; `AsyncLootPerception` is a Loot-specific temporal worker, not the new `PerceptionEngine` confirmation stage. No provider contract, `FrameContext`, `TargetProfile`, standardized `TargetDetection`, or generic action mapper is used.

**Migration implication:** the old Loot implementation is more than one recognizer to replace. Its seed generation, exclusion logic, feature matcher, temporal stabilization, and cluster-to-event projection must be split into reusable/raw layers and then bridged one behavior at a time, with the old path retained for regression comparison.

**Next pass:** read the Loot detection pipeline/ROI implementation and navigation composition boundary, then produce a complete old-chain/new-core coverage matrix and a safe migration order.
## [Legacy-chain architecture audit] 2026-09-04 — Loot recognition algorithm

### A. Scope declaration (before source review)

**File selected:** `core/events/types/loot/detection/pipeline.py`.

**Reason:** this high-complexity recognition pipeline decides how loot-specific preprocessing, seed ROIs, template/shape/color evidence, exclusions, clustering, and debug data compose. It is read separately to avoid mistaking its internal decomposition for generic-module integration.
### C. Findings — Loot recognition algorithm

**Verified:** the Loot pipeline contains a sophisticated but fully event-local image-processing chain: BGR conversion, small-frame padding/unpadding, candidate seed ROI extraction, grayscale/Canny generation, grayscale/edge/masked template responses, color scoring, NMS/duplicate merging, clustering, and a long list of minimap/game-artifact exclusions.

**Verified preprocessing duplication:** Canny thresholds, color/mask logic, template preparation, ROI origin offsets, and center-player exclusion all live in Loot detection modules. The ROI code correctly adds local crop offsets back to Loot candidate coordinates, but exposes no shared transform/provenance object for other algorithms or the new mapper.

**Verified domain assumptions:** fixed minimap center/player exclusion, named artifact classifiers (diamonds, sword, pile, triangle, red star, map ring), Loot templates, and Loot score weights are target/game policy. They must remain legacy profile/adapter behavior, not become generic preprocessing operations.

**Reusable candidates:** image normalization, padding/crop geometry, grayscale, Canny, template scaling/masks, response peak extraction/NMS, basic color masks, and connected-component ROIs are reusable primitives once separated from Loot scoring and exclusion policy.

**Next pass:** trace legacy localization → navigation task → input execution to establish the full old map-to-movement chain and confirm it bypasses `core.spatial` and `core.actions`.
## [Legacy-chain architecture audit] 2026-09-04 — navigation to movement action

### A. Scope declaration (before source review)

**File selected:** `core/navigation_tasks/movement_executor.py`.

**Reason:** this is the high-complexity navigation-side movement/action decision maker. Reading it alone establishes whether legacy global-map positions become new `ActionRequest` objects or flow through older click/input machinery.
### C. Findings — navigation movement facade

**Verified:** `MovementExecutor` is a reusable *legacy navigation* facade rather than a device/action adapter. It has substantial map-routing state (A* path, wall/explored maps, anchors, lookahead, click throttling, stuck detection, recovery probes) and delegates execution decisions to `movement_step()`.

**Scope clarification:** this is already a worthwhile generic global-map movement component, but its coordinate system is the persisted stitched-map/world plane, not the new full-screen physical-pointer plane. It needs an explicit bridge between navigation intent/subgoal and screen/action execution; it should not be moved wholesale into `core.spatial`.

**Next pass:** read the movement pipeline and navigation UI intent executor to find the exact old map-point → screen-click/input path and document the separation point needed for a compatibility adapter.
## [Legacy-chain architecture audit] 2026-09-04 — movement decision algorithm

### A. Scope declaration (before source review)

**File selected:** `core/navigation_tasks/movement/pipeline.py`.

**Reason:** this high-complexity pipeline turns global localization/path state into a `MovementStep`. It must be inspected separately to determine whether it already creates a neutral action intent or embeds Torchlight screen-click mapping/input assumptions.
### C. Findings — movement decision algorithm

**Verified:** `movement_step()` is free of direct device I/O. It computes an A* path lookahead/recovery subgoal in the stitched global-map plane and returns a `MovementStep(path, subgoal, should_click, force_click_target, …)`. This is a useful existing intent boundary, but it predates and does not use `core.actions`.

**Verified coupling below the surface:** its comments and final-goal rules explicitly rely on a later “screen minimum radius” and “mapped anchor point” stage. Therefore the next executor is where legacy global-map coordinates are transformed to screen clicks; that transform must be audited separately and eventually become the navigation compatibility bridge.

**Architecture conclusion:** pathfinding itself should remain an independent navigation capability. The migration target is not “replace A* with perception”; it is to have the legacy `MovementStep` translated by an explicit map-world → screen action adapter, while input execution is moved behind device-neutral actions.

**Next pass:** inspect the navigation intent executor and localization tick/composition to confirm the real coordinate conversion and old input driver calls.
## [Legacy-chain architecture audit] 2026-09-04 — runtime coordinate and input bridge

### A. Scope declaration (before source review)

**Files selected:**
- `gui/modes/navigation/input/intent_executor.py` — final navigation-intent to input dispatch.
- `gui/modes/navigation/runtime/localization_tick.py` — localization results into navigation runtime.
- `core/navigation_tasks/update_pipeline.py` — navigation controller update composition.

**Questions:** trace the old stitched-map/minimap coordinate flow, confirm where screen clicks and key presses are executed, and compare those seams to `core.spatial` / `core.actions`.
### C. Findings — runtime coordinate and input bridge

**Verified legacy flow:** `capture_navigation_localization_tick()` obtains a manually configured minimap capture rectangle, captures only that image, resolves a local player coordinate, and calls `NavigationCore.localize()`. `update_controller_context()` uses the resulting stitched-map position plus wall/explored maps to select tasks and create `NavigationIntent` values.

**Verified action boundary gap:** `execute_navigation_intent()` dispatches `MOVE_MAP`, `CLICK_SCREEN`, and `PRESS_KEY` directly to the GUI-owned `MotionController`. For map movement it calls `move_to_map_target(player_global, subgoal_global)` or `click_map_target_once(...)`, which owns the old global-map → screen-click conversion; there is no `core.spatial` mapper or `core.actions.ActionRequest` between the intent and device call.

**Important nuance:** `NavigationIntent` is already an application-level command seam and should become the compatibility bridge input. The safe migration is to introduce a translator/adapter below it, not to make the existing localization or path planner import mouse/gamepad code.

**Confirmed end-to-end result:** legacy map capture, HSV preprocessing, localization, world-map pathfinding, Portal/Loot events, map-to-screen conversion, and actual input remain a separate Torchlight-oriented chain. New perception/spatial/actions currently coexist beside it; they do not yet drive it.

**Next:** compile the audit matrix and a staged migration plan, including exactly what can be reused, what must stay target-specific, and what needs extraction first.
## [Legacy-chain architecture audit] 2026-09-04 — legacy event contracts

### A. Scope declaration (before source review)

**File selected:** `core/events/models.py`.

**Reason:** confirm the legacy `EventDetection` / `EventAction` schemas that Portal, Loot, navigation, and GUI currently exchange, so the migration boundary is based on actual contracts rather than filename inference.
### C. Findings — legacy event contracts

**Verified:** the old event domain has its own coherent coordinate model: `EventDetection.local_minimap_pos` → `EventObservation.global_pos` → `EventTask.global_pos` → `EventAction.target_global_pos` or `screen_pos`/`key`. This is distinct from the new `TargetDetection` / `MappedPoint` / `ActionRequest` model.

**Verified:** `EventAction` is a high-level legacy command schema with `MOVE_TO`, `CLICK_SCREEN`, `PRESS_KEY`, `WAIT`, `COMPLETE`, and `FAIL`; it is not a device-neutral execution request because it carries ambiguous raw screen tuples and a string key, with actual dispatch owned by the GUI `MotionController` path.

**Migration seam identified:** retain this old event state machine initially, then introduce explicit adapters at both ends: `EventDetection ↔ TargetDetection` for perception compatibility, and `EventAction/NavigationIntent → core.actions` for execution compatibility. The global-map position projection remains a separate navigation/spatial transform.

**Audit conclusion:** the user’s diagnosis is confirmed. Old Torchlight-adapted chains are internally decomposed but have not been migrated to, or driven by, the new architecture. This finding now drives the implementation order rather than treating new perception modules as integration-complete.
## [Documentation sync] 2026-09-04 — legacy/new architecture integration status

### A. Scope declaration (before documentation update)

**Trigger:** the completed read-only audit established a material correction to the mainline status: legacy Torchlight minimap/localization/navigation/Portal/Loot modules are internally decomposed but not connected to the new generic perception/spatial/action architecture.

**Documentation to update:**
- `docs/PERCEPTION_ENGINE_CHECKPOINT.md` — record the verified integration status and migration boundary.
- `CODEBASE.md` — register the legacy/new contract separation and bridge order as a current architectural risk.

**No source/config/test file will be changed.**
### C. Documentation sync result

**Checkpoint updated:** `docs/PERCEPTION_ENGINE_CHECKPOINT.md` now records the verified status of legacy minimap/localization/navigation/Portal/Loot paths, the true P7 bridge boundaries, and the preprocessing extraction prerequisite.

**Codebase updated:** `CODEBASE.md` now makes the old-chain/new-core separation explicit in its risk/seam register, including the GUI `MotionController` dispatch boundary.

**Files changed by this audit:** only `ITERATION_LOG.md`, `docs/PERCEPTION_ENGINE_CHECKPOINT.md`, and `CODEBASE.md`. No legacy source, test, configuration, virtual-gamepad, staging, or Git history was changed.
## [Legacy-chain architecture audit] 2026-09-04 — map stitching implementation

### A. Scope declaration (before source review)

**Question:** identify and inspect the legacy map-drawing/stitching implementation that feeds the persisted wall/explored map used by localization and routing.

**Discovery scope:** source files/classes containing `stitcher`, `stitch`, `wall_layer`, or map-frame merge logic, excluding generated data and tests until the runtime entrypoint is identified.

**Goal:** confirm whether map construction has an independent reusable core or is coupled to GUI/capture/Torchlight minimap assumptions, and add it to the old/new architecture matrix.
### C. Discovery findings — map stitching inventory

**Verified:** map construction has a genuine independent subsystem under `core/mapping/` (`MapStitcher`, frame preparation/pipeline, weighted merge, package I/O, rendering, performance). It is not only GUI code, and it persists canvas/wall/fog/explored layers for the later localization/routing chain.

**Current uncertainty:** this module may be more reusable than Portal/Loot because its public API already accepts masks and player position. Its actual state/config/capture assumptions still need inspection before assigning it a generic-core status.

**Next pass:** read `core/mapping/stitcher.py` alone, then identify which map-frame preparation call supplies its masks.
## [Legacy-chain architecture audit] 2026-09-04 — map stitcher core

### A. Scope declaration (before source review)

**File selected:** `core/mapping/stitcher.py`.

**Reason:** establish whether `MapStitcher` is a reusable map-domain core with injectable visual evidence, or whether its state and public API embed Torchlight/minimap recognition and GUI/capture concerns.
### C. Findings — map stitcher core

**Verified:** `core/mapping/MapStitcher` is already a meaningful non-GUI mapping core. It owns a canvas, wall/fog/explored/weight layers, keyframe and prior-frame registration, phase-displacement tracking, weighted merge, persisted map packages, and map rendering helpers. It is reusable for any sequence of aligned local masks, not merely a Portal/Loot feature.

**Verified boundary:** `MapStitcher.add_frame()` accepts caller-supplied `match_mask`, `save_mask`, `fog_mask`, and `player_pos`; it does not own screenshot capture or HSV recognition. However all values are untyped arrays/tuples and its public state is explicitly wall/fog/player/minimap-map oriented (`draw_scale`, wall-thickness closing, canvas-center world plane). It has no `FrameContext`, preprocessing artifact geometry, provider, profile, or standardized detection contract.

**Correct classification:** preserve `core/mapping` as the future reusable *map-domain* core. Do not duplicate it in `core/perception`. The required modernization is to introduce typed evidence/coordinate contracts at its input/output and replace the GUI/legacy HSV composition around it gradually.

**Next pass:** inspect the mapping runtime session and frame-preparation boundary to confirm how the old recognizer supplies masks and whether preprocessing is still hard-bound to the Torchlight minimap UI.
## [Legacy-chain architecture audit] 2026-09-04 — map-frame composition

### A. Scope declaration (before source review)

**Files selected:**
- `gui/modes/mapping/runtime/session.py` — GUI/runtime source-to-stitcher composition.
- `core/mapping/frame_preparation.py` — generic versus map-semantic scaling/mask preparation.
- `core/mapping/frame_pipeline.py` — caller-provided evidence into stitcher state transition.

**Questions:** establish the exact preprocessing/capture ownership on the map-building path, and which pieces can be retained or extracted without altering working map behavior.
### C. Findings — map-frame composition

**Verified full mapping path:** `MappingSession.tick()` captures a configured square/rectangle, defaults the player to the crop center or uses the old player tracker, invokes `HSVRecognizer.extract_combined()`, then sends raw arrays to `MapStitcher.add_frame()`. It also returns the old recognizer's preprocessed display image directly to the GUI.

**Verified composition coupling:** this capture → recognition → stitch path is currently assembled through GUI `app_context`; it has no `FrameContext`, typed preprocessing artifact, source-coordinate transform, or provider/engine composition. The same old HSV mask generation feeds both map construction and later localization.

**Verified `core/mapping` strength and limitations:** frame preparation and stitching are cleanly separated from the GUI. They implement scale/offset recovery, keyframe/f2f registration, visible-wall/fog weighted merge, duplicate suppression, and persisted world-map layers. But their values are naked masks/tuples and their default center-player/canvas/draw-scale semantics remain minimap-map specific.

**Final map-building classification:** the user’s previous mapping/stitching work is valuable reusable map-domain logic, but it is not yet an implementation of the new generic perception/spatial/action design. It should be retained and wrapped with typed evidence and coordinate adapters, not rewritten or claimed as P4/P5 complete.

**Next:** add this map-stitcher result to the checkpoint and codebase risk record, then deliver the complete old/new coverage matrix and staged bridge plan.
## [Documentation sync] 2026-09-04 — map-stitcher audit result

### A. Scope declaration (before documentation update)

**Trigger:** the audit confirmed that `core/mapping` is an independently useful legacy map-domain core, while its GUI/HSV composition and untyped mask contracts remain outside the new generic engine.

**Documentation to update:** the legacy audit entries in `docs/PERCEPTION_ENGINE_CHECKPOINT.md` and `CODEBASE.md`, preserving the distinction between retainable map-domain logic and unbridged perception/spatial/action integration.
### C. Documentation sync result

**Checkpoint and codebase updated:** both now distinguish the retainable `core/mapping/MapStitcher` core from the unbridged GUI capture/HSV composition feeding it.

**Audit status:** reviewed end-to-end legacy paths now cover map-frame capture/preprocessing/stitching, minimap localization, route/event movement intent, Portal detection/handler, Loot detection pipeline, and GUI input dispatch. The final report can state the current architecture with evidence rather than inference.

**Files changed by this final audit sync:** only `ITERATION_LOG.md`, `docs/PERCEPTION_ENGINE_CHECKPOINT.md`, and `CODEBASE.md`.
## [Architecture decomposition review] 2026-09-04 — bottom capabilities and top-level adapters

### A. Scope declaration (before source review)

**Question:** give a detailed, actionable classification of current modules: keep as a lower-level capability, extract/refactor into a reusable lower-level capability, or retain as a game/scene/workflow adapter.

**Files selected for final boundary verification:**
- `core/input/motion_mapping.py` — existing stitched-world → screen mapping algorithm.
- `core/events/coordinator/observation.py` — legacy event detection/stabilization/task composition.
- `core/routing/obstacles.py` — map-domain wall-layer derivation.

**Output:** a dependency-safe target hierarchy, concrete extraction candidates, explicit non-extraction rules, and a staged wrapper strategy that preserves current behavior.

## [Architecture audit follow-up] 2026-09-04

### A. Scope declared before reading

**Requested outcome:** provide a verified, detailed account of the present modular architecture; distinguish reusable low-level capabilities from Torchlight/minimap-specific policy and top-level orchestration.

**Files to verify in this pass:**

- `core/input/motion_mapping.py` — confirm the existing world-map-to-screen projection seam.
- `core/events/coordinator/observation.py` — confirm the event coordination boundary.
- `core/routing/obstacles.py` — confirm reusable map-domain obstacle derivation.

**Decision boundary:** this is an architecture audit and documentation checkpoint only. No legacy runtime, GUI, virtual-gamepad, Portal, or Loot code will be changed.

### C. Findings

- **(verified) World-to-view projection seam:** `calculate_movement_click()` and `calculate_mapped_target_click()` compute a normalized direction from global-map coordinates, project it from a supplied screen centre, and constrain the radial distance. That geometry is reusable below the game policy layer. `apply_bottom_click_guard()`, click-radius tuning, and the supplied game centre are game/UI policy and must remain configurable at the adapter/profile layer.
- **(verified) Event orchestration seam:** `observe_events()` executes detect → position stabilization → observation memory merge → task selection. It is a reusable event-domain coordinator, but its inputs/outputs still use the legacy event contracts; it should gain bridges on both sides instead of being rewritten into a workflow.
- **(verified) Map-domain image primitive:** `derive_navigation_wall_layer()` performs thresholding followed by optional cross-kernel erosion to create an A*-friendly obstacle layer without mutating the localization layer. It can remain a mapping/routing primitive; it is not a generic detector and should not move into `core.perception`.
- **Confirmed scope status:** no source runtime code was changed in this audit. The pre-existing dirty worktree, particularly `virtual_gamepad/`, remains untouched.

**Next design action, when authorised:** define a standalone preprocessing/artifact contract first; then introduce typed map evidence, legacy bridges, and action translation in small compatibility-preserving steps.

## [Generic core extraction plan] 2026-09-04

### A. Scope declared before reading

**Requested outcome:** extract currently reusable capabilities into generic low-level modules and optimise the legacy Torchlight/minimap chain by making it delegate to those modules where behaviour can be preserved. Do not build game-specific PoE workflows in this phase.

**Files to inspect for the first task batch:**

- `core/vision/hsv/preprocessing.py` — identify exact image operations and existing parameter dependencies.
- `core/vision/hsv/masks.py` — identify mask and connected-component primitives.
- `core/vision/hsv/combined.py` — identify composition and game-semantic portions that must remain legacy policy.

**Compatibility constraints:**

- Keep existing public legacy imports and call signatures working.
- Preserve Torchlight-specific wall/fog/player choices as legacy/profile policy.
- New generic modules must not import GUI, `HSVRecognizer`, Portal, Loot, events, or input controllers.
- Establish regression tests before redirecting legacy code to a new implementation.

### C. Findings

- **(verified) Direct extraction candidates:** percentile normalization, gamma LUT, Gaussian/median blur, LAB-CLAHE, top-hat, BGR channel scaling, HSV range masks, morphology, Canny, connected-component filtering, saturation masks, circle masking, and weighted mask fusion are implemented as recognizer-coupled helpers but have no inherent Torchlight dependency.
- **(verified) Legacy policy that must not move:** wall/fog/player HSV ranges, transparency score choice, player-centre fallback, player-clear radius, saturation exclusion region, and wall/edge weights are game/profile semantics. The existing `HSVRecognizer` facade must retain ownership of these choices.
- **(verified) First compatibility seam:** the legacy wrapper can construct generic operation parameter objects from its existing attributes and call a new preprocessing pipeline; `extract_combined_masks()` can keep its tuple return contract while delegating generic image operations.
- **Plan refinement:** begin with a small typed image-artifact geometry contract plus independently testable pure operations. Do not move a recognizer or map-stitcher in the first slice.

## [Generic core extraction plan — contracts] 2026-09-04

### A. Scope declared before reading

**Goal:** align the new preprocessing contract with existing perception models, coordinate-space conventions, and test conventions before writing the implementation plan.

**Files to inspect:**

- `core/perception/models.py` — current shared model conventions.
- `core/perception/coordinates.py` — current coordinate-space and geometry conventions.
- `tests` / `core/perception/tests` discovery — current test layout and runner conventions.

### C. Findings

- **(verified) Existing contract location:** `CoordinateSpace`, `BoundingBox`, and `FrameContext` are all defined in `core/perception/models.py`; there is no `core/perception/coordinates.py`. The new preprocessing contract should import those existing types rather than create a parallel coordinate enum.
- **(verified) Test location:** perception tests live under repository-level `tests/` and follow the `test_perception_*.py` naming convention. A preprocessing suite belongs at `tests/test_perception_preprocessing.py`.
- **Corrected plan:** preprocessing artifacts will use the existing `CoordinateSpace` and expose source-frame geometry explicitly. No duplicate coordinate contract will be added.

## [Generic core extraction plan — test and public API conventions] 2026-09-04

### A. Scope declared before reading

**Goal:** determine the exact public-export and testing conventions needed for a safe first generic preprocessing slice.

**Files to inspect:**

- `core/perception/__init__.py` — package-level public API convention.
- `tests/test_perception_models.py` — model contract test style.
- `tests/test_recognizer_optimized.py` — existing HSV-recognizer regression coverage that must remain valid.

### C. Findings

- **(verified) Public API convention:** `core.perception.__init__` explicitly re-exports stable generic types. The new artifact and transform types will be exported there after their tests pass.
- **(verified) Test convention:** the project uses standard-library `unittest`, with direct exact assertions for geometry and output contracts.
- **(verified) Existing regression seam:** `HSVRecognizer.extract_combined(...)` is already covered for saturated dynamic-icon removal. That test will remain unchanged and a new equivalence test will protect the delegated generic operation path.
- **First implementation slice confirmed:** add geometry-aware image-artifact models plus pure generic preprocessing operations first; retain all old HSV facade entrypoints and semantic orchestration in place.

## [Generic core extraction plan — mapping and action seams] 2026-09-04

### A. Scope declared before reading

**Goal:** establish exact existing contracts for typed map evidence and the general action layer so the implementation plan can preserve their public behaviour.

**Files to inspect:**

- `core/mapping/stitcher.py` — current `MapStitcher` input/output boundary.
- `core/actions/models.py` — current generic action contract.
- `core/actions/__init__.py` — current generic action public API.

### C. Findings

- **(verified) Map-stitcher compatibility boundary:** `MapStitcher.add_frame(img, match_mask, save_mask, fog_mask, raw_gray=None, player_pos=None)` is the exact legacy ingress. A new `add_evidence(evidence)` method can unpack a typed contract and delegate to it, leaving all existing callers untouched.
- **(verified) Existing action foundation is broader than the original proof:** package exports already include action contracts plus keyboard and virtual-gamepad adapters. `ActionRequest` itself remains intentionally limited to mapped pointer actions; no action-contract rewrite is required in this extraction phase.
- **Corrected scope:** this phase will add typed map evidence as a compatibility ingress but will not change action contracts. Legacy `NavigationIntent/EventAction → ActionCommand` translation remains a later integration task.

## [SYNC] 2026-09-04 — image artifact geometry contract

### A. SYNC scope declaration

**Triggering task:** add the first reusable preprocessing contract: `ImageGeometry` and `ImageArtifact`.

**Directly changed files:**

- `core/perception/preprocessing/models.py`
- `core/perception/preprocessing/__init__.py`
- `core/perception/__init__.py`
- `tests/test_perception_preprocessing.py`

**Expected impact:** generic perception callers can import the new types; no existing detector, legacy HSV facade, map stitcher, action adapter, GUI, or workflow has been redirected yet.

### C. SYNC result

**Re-read files:** `core/perception/preprocessing/models.py`, `core/perception/preprocessing/__init__.py`, `core/perception/__init__.py`.

**Verified contract:** `ImageGeometry` validates positive dimensions and an output-to-source 3×3 transform; it maps points and enclosing bounding boxes back to source-frame coordinates. `ImageArtifact` validates its image shape against the geometry and source frame. Package exports expose the types without importing legacy modules.

**No coupling introduced:** the new package imports only shared perception models. No existing call path has changed yet.

**Pending verification:** re-read the new test file and update the codebase index before closing this SYNC checkpoint.

## [SYNC] 2026-09-04 — image artifact geometry test/index closure

### A. SYNC scope declaration

**Goal:** verify the new regression test and update the existing perception architecture index with the new public contract.

**Files to inspect:**

- `tests/test_perception_preprocessing.py`
- `CODEBASE.md` sections covering `core/perception` and its public exports.

### C. SYNC result

**Verified test:** `ImageGeometryTests` asserts identity point/box backprojection and rejects an artifact whose output height differs from geometry. The initially missing-module test failed as expected; after the contract was added, the suite passed 2/2.

**CODEBASE.md updated:** added the preprocessing public package and models contract to the perception directory/file index; updated the public perception export description.

**Next task:** add crop/resize/pad operations that compose the same output-to-source geometry; only after their direct tests pass will legacy code be considered for delegation.

## [SYNC] 2026-09-04 — artifact geometry transforms

### A. SYNC scope declaration

**Triggering task:** add generic crop, resize, and pad operations with source-frame transform composition.

**Directly changed files:**

- `core/perception/preprocessing/geometry.py`
- `core/perception/preprocessing/__init__.py`
- `tests/test_perception_preprocessing.py`

**Expected impact:** generic callers can create transformed artifacts with precise source-coordinate recovery. No legacy caller has been redirected.

### C. SYNC result

**Re-read files:** `core/perception/preprocessing/geometry.py`, preprocessing public exports, and `tests/test_perception_preprocessing.py`.

**Verified behaviour:** crop composes a source translation, resize composes inverse x/y scaling, and pad composes inverse padding translation. The crop → resize → pad regression maps artifact point `(105, 57)` back to source point `(70, 35)`; the whole preprocessing suite passes 3/3.

**CODEBASE.md updated:** added the geometry-operation module, its composition rule, and its validation boundary.

**No legacy change:** `HSVRecognizer`, map stitching, navigation, GUI, Portal, and Loot still execute their former implementations.

## [SYNC] 2026-09-04 — generic image operations

### A. SYNC scope declaration

**Triggering task:** add reusable pixel enhancement and colour-space operations used by the legacy HSV path.

**Directly changed files:**

- `core/perception/preprocessing/image_ops.py`
- `core/perception/preprocessing/__init__.py`
- `tests/test_perception_preprocessing.py`

**Expected impact:** generic callers can perform validated image-only operations. No legacy facade is yet redirected.

### C. SYNC result

**Re-read files:** `core/perception/preprocessing/image_ops.py`, preprocessing public exports, and `tests/test_perception_preprocessing.py`.

**Verified operations:** gamma LUT, blur, L-channel CLAHE, top-hat, percentile normalization, intensity/channel scaling, gray/HSV conversion, and Canny are image-only functions with validated shapes/ranges. The direct test suite passes 7/7, including flat-image fallback, uint8/shape preservation, channel scaling, and a real Canny edge response.

**CODEBASE.md updated:** added the generic pixel-operation module and its no-game-semantics boundary.

**Next task:** add generic binary mask, morphology, connected-component, exclusion, and weighted-fusion functions. This remains a lower-level extraction; legacy wall/fog/player policy stays where it is.

## [SYNC] 2026-09-04 — generic mask operations

### A. SYNC scope declaration

**Triggering task:** add reusable HSV range, threshold, morphology, component filtering, saturation, circle, exclusion, and weighted mask-fusion operations.

**Directly changed files:**

- `core/perception/preprocessing/masks.py`
- `core/perception/preprocessing/__init__.py`
- `tests/test_perception_preprocessing.py`

**Expected impact:** generic visual algorithms can compose masks without a legacy recognizer. Existing legacy calls have not changed.

### C. SYNC result

**Re-read files:** `core/perception/preprocessing/masks.py`, preprocessing exports, and the preprocessing regression suite.

**Verified behaviour:** the new module provides HSV range selection, thresholding, all existing morphology modes, connected-component filtering, saturation selection, circle construction, exclusion, and weighted fusion with explicit validation. The 9-test suite verifies small-component removal and a colour → morphology → fusion → circle-exclusion chain.

**CODEBASE.md updated:** added the generic mask-operation module and its semantic boundary.

**Next task:** capture representative legacy HSV outputs and redirect its internal OpenCV primitive calls to the new generic functions without moving wall/fog/player policies.

## [Legacy HSV delegation] 2026-09-04

### A. Scope declared before reading

**Goal:** find the exact legacy facade, defaults, and private-wrapper boundaries needed to delegate image primitives without changing public recognizer behaviour.

**Files to inspect:**

- `core/recognizer_optimized.py` — active legacy recognizer facade and wrappers.
- `core/vision/hsv_recognizer.py` — alternate/public facade relationship.
- `core/vision/hsv/params.py` — parameter ownership and default compatibility constraints.

**Migration rule:** only replace internal primitive calls after a deterministic fixture locks current output. Keep recognizer parameter names and all public methods intact.

### C. Findings

- **(verified) Canonical facade:** `core/vision/hsv_recognizer.py::HSVRecognizer` is the active implementation. It owns all current defaults and preserves compatibility through private wrappers such as `_preprocess_for_wall()`, `_compute_transparency_score()`, and `_filter_small_components()`.
- **(verified) Policy boundary:** wall/fog/player ranges, transparency choice, clear radius, saturation settings, edge weights, and old parameter names are owned by the facade and parameter module; they must remain outside generic preprocessing.
- **Correction:** the `core.recognizer_optimized` import used by legacy tests resolves as a package rather than the assumed single `.py` file. Its package entry must be checked before adding compatibility fixtures.

## [Legacy HSV delegation — package and fixture baseline] 2026-09-04

### A. Scope declared before reading

**Goal:** confirm the compatibility import and capture a deterministic pre-migration output fingerprint for the public recognizer.

**Files/outputs to inspect:**

- `core/recognizer_optimized/` package entry.
- `core/vision/hsv/__init__.py` package surface.
- A fixed synthetic-image execution of public `HSVRecognizer` methods, recorded as fixture hashes before delegation.

### C. Findings

- **(verified) Public HSV helper surface:** `core/vision/hsv/__init__.py` exports the current helper functions and is the correct stable helper-import surface. The expected `core/recognizer_optimized` source path is absent from this worktree despite an older test import; compatibility will use the canonical `core.vision.hsv_recognizer.HSVRecognizer` and the old test will be run before migration.
- **(verified) Deterministic baseline captured:** for the fixed 96×96 synthetic fixture, public recognizer SHA-256/nonzero outputs are wall `b5bf2189…57a9af / 384`, fog `c4889bc7…cd7822 / 576`, combined match `bd013651…3c9e1e / 353`, combined wall `774fd936…e20803 / 235`, combined fog `2d07a41a…c087ae / 0`, and raw gray `cd285e5b…ec87c3 / 6395`.
- **Migration guard:** add these hashes as a canonical-facade regression before changing any legacy HSV implementation. The missing old test import is an existing repository issue to diagnose separately if its suite fails.

## [Compatibility-import diagnosis] 2026-09-04

### A. Scope declared before reading

**Symptom:** `tests/test_recognizer_optimized.py` fails before executing any test because `core.recognizer_optimized` is absent.

**Investigation targets:**

- all repository references to `recognizer_optimized`;
- Git history for the missing compatibility path;
- the canonical `HSVRecognizer` import path and any existing re-export pattern.

**Hypothesis to test only after evidence:** a legacy public compatibility re-export was removed while a still-tracked test/caller retained its import.

### C. Findings

- **(verified root cause) Intentional module removal with stale test:** Git commit `3fd3333` deleted `core/recognizer_optimized.py` during the migration to `core.vision`. Production GUI/localization imports now use `core.vision.HSVRecognizer`; the only executable stale reference found is `tests/test_recognizer_optimized.py`.
- **(verified working pattern):** `core.vision.hsv_recognizer.HSVRecognizer` is the canonical replacement and exposes the same recognition behaviour targeted by the stale test. Historical architecture notes still mentioning the deleted wrapper are records, not executable dependencies.
- **Hypothesis:** replacing only the stale test import with the canonical public import will restore the intended regression test without resurrecting a deliberately deleted compatibility module.

### C. Resolution

- **Minimal hypothesis test:** the stale test's exact assertions pass unchanged when executed against `core.vision.HSVRecognizer`.
- **Single root-cause fix:** `tests/test_recognizer_optimized.py` now imports the canonical public facade instead of the intentionally removed module.
- **Verification:** preprocessing, legacy-HSV compatibility, and recognizer regression suites pass 11/11. No compatibility module was restored and no production import changed.

## [Typed map evidence ingress] 2026-09-04

### A. Scope declared before reading

**Goal:** introduce a typed `MapFrameEvidence` contract and a compatibility-preserving `MapStitcher.add_evidence(...)` entry that delegates to existing `add_frame(...)`.

**Files to inspect:**

- `core/mapping/__init__.py` — mapping public-export convention.
- `tests/test_stitcher_core.py` — existing stitcher test conventions and constructor assumptions.

**Compatibility rule:** `MapStitcher.add_frame(img, match_mask, save_mask, fog_mask, raw_gray=None, player_pos=None)` must retain its signature and implementation path.

## [Input package import diagnosis] 2026-09-04

### A. Scope declared before reading

**Symptom:** importing the pure `core.input.motion_mapping` module raises `ModuleNotFoundError: pydirectinput` because Python executes `core.input.__init__` first.

**Investigation targets:**

- `core/input/__init__.py` public imports;
- `core/input/click_executor.py` optional-dependency boundary;
- dependency manifests and an existing test importing `core.input`.

**Hypothesis to test only after evidence:** a package-level eager import has accidentally made an optional real-input backend mandatory for pure coordinate math.

### C. Findings

- **(verified root cause):** `core/input/__init__.py` eagerly imports `click_executor`, which unconditionally imports `pydirectinput`; `pydirectinput` is absent from `requirements.txt` and the active environment. Thus importing any `core.input.*` submodule—including pure math—fails before use.
- **Dependency boundary failure:** `send_click()` uses pydirectinput only for its fallback backend, so it must not prevent import of `motion_mapping` or other Win32-backed paths.
- **Next evidence needed:** inspect the new action adapters' optional-device import pattern, then make one minimal lazy/guarded dependency change with a failing import regression test.

## [Input package import diagnosis — optional dependency pattern] 2026-09-04

### A. Scope declared before reading

**Goal:** compare the legacy click backend with the project’s current optional-device adapter pattern before selecting a minimal import-boundary fix.

**Files to inspect:**

- `core/actions/keyboard.py`
- `core/actions/mouse.py`
- `tests/test_keyboard_action_adapter.py`

### C. Findings

- **(verified working pattern):** `PyDirectInputKeyboardDevice` imports `pydirectinput` only in its production-device constructor; the generic `KeyboardActionAdapter` and `MouseActionAdapter` are import-safe and device-injected.
- **Confirmed hypothesis:** legacy `click_executor` violates this pattern by importing pydirectinput at module load time even though only its fallback calls need it.
- **Single fix selected:** replace the eager module import with a private lazy resolver used only by `send_click()` fallback and `fallback_pydirect_click()`. The current failing pure-motion import test is the regression case.

### C. First fix result

- **Verified partial resolution:** `click_executor` no longer imports pydirectinput at package load time.
- **New boundary revealed:** the same test now reaches `core.input.motion_controller.backend`, which has a separate eager `pydirectinput` import. This is a second occurrence of the same optional-dependency boundary violation, not a failure of the lazy fallback change.
- **Fix count:** 1. Return to root-cause inventory before making a second change.

## [Input package import diagnosis — full optional-backend inventory] 2026-09-04

### A. Scope declared before reading

**Goal:** inventory every `pydirectinput` import reachable from `core.input` and inspect the newly exposed backend before one bounded follow-up fix.

**Files/queries to inspect:**

- all executable `pydirectinput` imports;
- `core/input/motion_controller/backend.py`;
- `core/input/controller.py` composition path.

### C. Findings

- **(verified complete import inventory):** besides the now-lazy click fallback, the only eager pydirectinput imports under `core.input` are `motion_controller/backend.py` and `motion_controller/controls.py`. Both are loaded whenever package `core.input` exposes `MotionController`.
- **Refined root cause:** the package combines pure mapping exports and concrete motion-controller exports in one eager `__init__`; therefore every concrete backend must use the same lazy resolver.
- **Single second fix:** centralize the resolver in one internal module and use it at invocation time in click executor, backend, and controls. This removes all eager optional-backend imports in the package without changing controller methods or selected input backend behaviour.

## [Input package import diagnosis — controller call sites] 2026-09-04

### A. Scope declared before reading

**Goal:** inspect every pydirectinput use in controller controls before applying the shared lazy-resolver fix.

**Files to inspect:**

- `core/input/motion_controller/controls.py`
- `core/input/motion_controller/__init__.py`
- `core/input/click_pipeline.py`

### C. Findings

- **(verified call sites):** controller backend uses pydirectinput only for non-essential diagnostic size/position calls; controls uses it only when a real key press is requested. Click pipeline already handles click backend failures.
- **Verification after second fix:** all pydirectinput imports reachable from `core.input` are now lazy. Navigation projection, legacy motion mapping, typed map evidence, stitcher, and keyboard-adapter suites pass 11/11 without pydirectinput installed.
- **Full-suite audit:** 153 discovered tests ran with 7 errors and 2 skips. Six errors are stale test imports of intentionally deleted top-level core modules; one is a test loading a relative-import GUI module outside its package. These are existing migration-test issues, not image/map/action contract failures.

## [Full-suite migration-test audit] 2026-09-04

### A. Scope declared before reading

**Goal:** map the failing stale core test imports to current public package exports; preserve tests rather than resurrect deleted modules.

## [Legacy convergence — mapping session evidence migration] 2026-09-04

### A. Scope declared before reading

**Migration objective:** move the live mapping composition root from raw mask/tuple arguments to the already-implemented MapFrameEvidence → MapStitcher.add_evidence() ingress. The historical add_frame(...) path remains only as a compatibility method for external callers.

**Files to inspect:**

- gui/modes/mapping/runtime/session.py — current mapping capture and stitcher composition.
- gui/modes/mapping/runtime/__init__.py — runtime public import/lifecycle surface.
- tests/test_perception_workbench.py or mapping-session tests — existing test seams for UI-independent composition.

**Parity constraints:**

- keep the capture rectangle, frame rate, player-coordinate selection, masks, stitched layers, and GUI preview output unchanged;
- do not import Qt/GUI into core.mapping.evidence;
- first add a regression that proves the session passes exactly the current frame/masks/player position through its new evidence object.

### C. Findings

- **(verified migration seam):** MappingSession.tick() is the sole composition point that captures the minimap, chooses player coordinates, invokes recognizer.extract_combined(), obtains raw_gray, and calls stitcher.add_frame().
- **(verified parity boundary):** all values required by MapFrameEvidence already exist immediately before the legacy call: image, combined match mask, wall mask, fog mask, raw gray, and player position.
- **Implementation decision:** replace only the final raw-argument call with construction of MapFrameEvidence and add_evidence(). Capture, recognizer calls, MappingTickResult, player fallback, and GUI presentation remain byte-for-byte behaviourally equivalent.

**Files to inspect first:**

- `core/routing/__init__.py`
- `core/localization/__init__.py`
- `core/vision/__init__.py`
### C. Mapping-session migration completion findings

- **(verified):** `MappingSession.tick()` now creates one `MapFrameEvidence` using the same captured image, combined/wall/fog masks, raw grayscale image, and player position that the former `add_frame(...)` call received.
- **(verified):** center capture remains `monitor_size // 2`; region capture still uses `_detect_or_fallback_player_pos()`. No recognition parameter, frame crop, GUI preview value, or stitcher registration/merge algorithm moved.
- **(verified):** the new session regression checks object identity for all five image/mask values and confirms the existing `(width, height)` tick result, while `MapStitcher.add_evidence()` keeps the historical `add_frame(...)` ingress for external compatibility.

## [SYNC] 2026-09-04 — MappingSession typed-evidence composition

### A. SYNC scope declaration

**Trigger:** migrate the live mapping composition root from raw `MapStitcher.add_frame(...)` arguments to `MapFrameEvidence` plus `MapStitcher.add_evidence(...)`.

**Directly changed files:** `gui/modes/mapping/runtime/session.py`; `tests/test_mapping_session_evidence.py`.

**Affected boundary:** `MappingSession.tick()` → `MapFrameEvidence` → `MapStitcher.add_evidence()` → unchanged `MapStitcher.add_frame()`.

### C. SYNC result

**Re-read impact surface:** mapping session, typed evidence contract, stitcher typed ingress, focused regression, mapping implementation plan, current checkpoint and the MappingSession entry in `CODEBASE.md`.

**CODEBASE.md synchronized:** runtime-session responsibility/dependency/compatibility notes now describe the typed evidence composition boundary; the generic-vs-domain split remains explicit.

**Verification:** `python -m unittest tests.test_mapping_session_evidence tests.test_mapping_evidence tests.test_stitcher_core` passed 5/5; `python -m compileall -q core gui/modes/mapping/runtime` and scoped `git diff --check` passed.

**Next migration:** audit the localization result boundary and its navigation composition caller before introducing a tuple-compatible `LocalizationResult`; no Portal/Loot/action policy changes are included in that slice.

## [Legacy convergence — localization result boundary] 2026-09-04

### A. Scope declared before reading

**Migration objective:** identify the exact legacy localization result tuple/object, its state mutation, and the first navigation composition caller. Design a typed `LocalizationResult` compatibility bridge only if it can preserve current returned values, confidence semantics, and state updates.

**Files to inspect:**

- `core/localization/__init__.py` and its direct runtime implementation — find the exported localization contract and legacy value shape.
- `gui/modes/navigation/input/intent_executor.py` and its direct caller — identify where localization-derived navigation becomes a movement/input intent.
- focused localization/navigation regression tests — preserve the existing observable behavior before editing.

**Out of scope:** changing HSV/minimap detection parameters, path-finding policy, `MotionController`, physical input adapters, Portal/Loot logic, or any GUI layout. This slice only establishes a result schema and migrates one composition edge if a behavior-preserving caller exists.

### C. Findings

- **(verified):** `NavigationCore.localize()` delegates to `core.localization.localize_pipeline.localize_frame()` and still returns the historical three-value `(global_x, global_y, confidence)` tuple on every success and failure branch. The pipeline also mutates `NavigationCore` registration/tracking state as part of the same call.
- **(verified):** `capture_navigation_localization_tick()` is the first live caller. It immediately wraps that tuple in GUI-owned `NavigationLocalizationResult`, then passes it into the navigation-task context. This is the correct migration point; the input executor is downstream of task planning rather than a consumer of raw localization values.
- **(verified):** `core.localization.evidence.LocalizationEvidence` already models diagnostic registration evidence, but it is not a localization call result and must not be repurposed to carry GUI/runtime result semantics.
- **Corrected plan:** first introduce a core-owned result DTO plus a new typed `NavigationCore.localize_result(...)` facade that delegates exactly once to the unchanged tuple API. Keep `localize(...)` and `localize_frame(...)` untouched for external compatibility; migrate the runtime tick to the new facade and remove only its redundant GUI DTO conversion.

**Next reading round:** inspect `NavigationCore` public-method conventions and state fields, the existing diagnostic-evidence schema, `CoordinateSpace` values, and focused runtime test seams before specifying the immutable result contract.

## [Localization result contract — design read] 2026-09-04

### A. Scope declared before reading

**Goal:** choose the minimal reusable fields and compatibility protocol for a core-owned localization result without leaking GUI, input, or minimap-recognizer configuration into it.

**Files to inspect:**

- `core/localization/navigation_core/runtime.py` — current public localize facade and state-owner conventions.
- `core/localization/evidence/models.py` — distinguish diagnostic evidence from result data.
- `core/perception/models.py` — reuse the existing coordinate-space vocabulary if it correctly represents a stitched map.
- `tests/test_navigation_core.py` — protect the core caller's current tuple-unpacking behavior.

**Question:** whether typed callers can use a new method rather than changing the dynamic return type of `localize(...)`; this preserves the legacy method while making typed composition explicit.

### C. Findings

- **(verified):** `CoordinateSpace.GLOBAL_MAP` already names the exact output plane of the stitched-map position, so no new cross-cutting coordinate enum is necessary.
- **(verified):** the GUI's `NavigationLocalizationResult` duplicates only position, confidence and `is_localized`; it has no GUI-specific state. It should be replaced by a core DTO, rather than become another long-lived adapter model.
- **(verified):** `NavigationCore.localize()` is an intentionally thin facade over the stateful legacy algorithm, so a sibling `localize_result()` can call it exactly once and adapt its final tuple without duplicating or relocating HSV/template/F2F code.
- **Proposed contract:** immutable `LocalizationResult(position, confidence, coordinate_space=GLOBAL_MAP, source, metadata)`; `position=None` is the normalized non-localized state. `source`/metadata must be read from the already-written frame registration, not inferred from recognizer internals. `as_legacy_tuple()` preserves external tuple consumers.

**Next reading round:** inspect the existing frame-registration object and setter/clearer to determine its stable field names and whether failed states expose source/metadata safely for result construction.

## [Localization result contract — registration read] 2026-09-04

### A. Scope declared before reading

**Goal:** use the existing registration state as the only source of localization-result provenance; do not repeat or expose the legacy algorithm's internal decision branches.

**Files to inspect:** direct localization registration DTO and the `NavigationCore` registration facade/helper implementation.

**Decision gate:** if registration already has source, validity, confidence and metadata, `LocalizationResult` will snapshot those fields; otherwise the first adapter exposes only position/confidence/coordinate space and leaves provenance for a later compatible extension.

### C. Findings

- **(verified):** `FrameRegistration` has the required snapshot fields: `valid`, `confidence`, `player_global_pos`, `source`, `frame_size`, and mutable `metadata`. Both successful F2F/template paths and every failed `localize_frame()` branch write it through the same `NavigationCore` helper.
- **(verified):** a typed result can take `position` and `confidence` from the legacy tuple, then copy registration source/validity/metadata immediately after that single call. This adds provenance without re-evaluating or duplicating any HSV, template, F2F, rejection, or state-mutation logic.
- **Contract decision:** create `core.localization.result.LocalizationResult` with `position`, `confidence`, `coordinate_space=GLOBAL_MAP`, `source`, `registration_valid`, and copied metadata. It exposes `localized_pos`, `is_localized`, and `as_legacy_tuple()`. `NavigationCore.localize_result()` will be additive; existing `localize()` remains the tuple API.

## [Localization result contract — runtime-test read] 2026-09-04

### A. Scope declared before reading

**Goal:** write a small runtime composition regression proving that the capture tick requests the typed core facade exactly once and returns its object unchanged.

**Files to inspect:** `gui/modes/navigation/runtime/loop.py` for player-position resolution requirements and existing navigation runtime test files for the smallest UI-independent fixture convention.

**Out of scope:** editing the frame loop, intent consumer, input executor, or action adapters. The tick remains the sole live caller changed in this slice.

### C. Findings

- **(verified):** a center-capture runtime fixture needs only `screen_capture.capture(...)`, a capture geometry callback, a minimal config, and `nav_core.localize_result(...)`; no Qt, tracker, event coordinator, action adapter, or real image-recognition backend is required.
- **Test decision:** add one core-facade test that patches the unchanged tuple API and verifies one invocation plus copied registration provenance, and one runtime-tick test that verifies the typed result object passes through unchanged. Existing F2F coverage remains the behavior guard for the legacy algorithm.

## [SYNC] 2026-09-04 — LocalizationResult core facade and runtime migration

### A. SYNC scope declaration

**Trigger:** add a core-owned `LocalizationResult`, an additive `NavigationCore.localize_result(...)` facade, and migrate `capture_navigation_localization_tick(...)` from GUI result conversion to the typed core result.

**Directly changed files:** `core/localization/result.py`, `core/localization/__init__.py`, `core/localization/navigation_core/runtime.py`, `gui/modes/navigation/runtime/localization_tick.py`, `gui/modes/navigation/runtime/models.py`, `tests/test_localization_result.py`, `tests/test_navigation_localization_tick.py`.

**Expected impact chain:** `NavigationRuntimeFrameLoop.run()` → `capture_navigation_localization_tick()` → `NavigationCore.localize_result()` → unchanged `NavigationCore.localize()` / `localize_frame()`; downstream task context continues to read `localized_pos` and `confidence`.

### C. SYNC result

**Re-read impact surface:** localization tuple facade, `FrameRegistration`, navigation capture tick, downstream `localized_pos/confidence` consumer, legacy GUI compatibility DTO, focused core/runtime tests, and the corresponding CODEBASE/checkpoint sections.

**Verified behavior preservation:** `localize_result()` delegates to `localize()` exactly once. It snapshots the registration already produced by the legacy algorithm; it does not branch on image content, invoke recognizer methods, map coordinates, or emit input. The old tuple entry remains unchanged.

**Verification:** initial red tests failed only because `LocalizationResult` was intentionally absent. After implementation, `tests.test_localization_result`, `tests.test_navigation_localization_tick`, and `tests.test_navigation_core` passed 3/3; the full `test_navigation*.py` group passed 12/12; mapping evidence/stitcher regression passed 5/5; scoped compilation and `git diff --check` passed.

**CODEBASE.md synchronized:** directory map, new result module detail, runtime models/tick descriptions, function chain, navigation flow and localization-runtime migration note now show the core DTO and the retained compatibility tuple.

**Full-suite audit:** `python -m unittest discover -s tests` ran 170 tests: 166 passed, 2 skipped, and 4 failures remain outside this slice. One is a dynamic loose-file import in `tests/test_advanced_settings_file_io.py` that makes `advanced_settings/file_io.py` lose package-relative imports. Three are `PathFinder` behavior/specification conflicts: diagonal movement crosses a blocked corner, unexplored space is walkable, and a strict thin-wall expectation differs from current implementation. The migrated localization result/tick has no call-path overlap with those failures; they are recorded for their own diagnostic task rather than hidden.

**Next migration:** translate navigation intents to a device-neutral action command at the composition boundary, while leaving `MotionController` as the temporary backend adapter. Portal and Loot remain untouched until their perception/output bridge is independently regression-locked.

## [Legacy convergence — complete perception-to-action chain] 2026-09-04

### A. Scope declared before reading

**Objective:** finish the currently known Torchlight/minimap compatibility chain as a composed, testable path: legacy capture/recognition and localization → typed map/global result → navigation or event intent → device-neutral action command → mouse, keyboard, or gamepad backend. Bridge Portal and Loot perception outputs to the shared detection schema without moving their game-specific templates, filtering, temporal policy, or handler state machines into core generic modules.

**Initial files to inspect:**

- `core/actions/` public contracts and adapters — identify the actual device-neutral command vocabulary and backend capabilities.
- `gui/modes/navigation/input/intent_executor.py` plus its runtime caller — enumerate every live `NavigationIntent` to direct-input transition.
- `core/events/` public models/types and Portal/Loot detector boundaries — locate `EventDetection` production and conversion seams.
- focused navigation-intent, action, portal, and loot tests — freeze observable behavior before each bridge.

**Rules:** no GUI import may enter `core.actions`, perception, spatial, or event DTO modules; new generic contracts must not contain Torchlight resource IDs, HSV ranges, templates, pickup keys, portal policies, or route state. `MotionController` remains a compatibility backend until every current caller has migrated. Full-suite baseline failures remain separately tracked and must not be hidden.

### C. Initial chain findings

- **(verified):** `gui.modes.navigation.input.execute_navigation_intent()` is the single live transition from `NavigationIntent` to direct side effects. It directly invokes three `MotionController` families: map movement, physical screen click, and key press. `NavigationRuntimeFrameLoop` only supplies GUI callbacks and status presentation.
- **(verified):** `core.actions` already contains a broader device-neutral command vocabulary than the earlier mouse proof: pointer, keyboard, and virtual-gamepad targets plus concrete adapters. Its legacy `ActionRequest` is deliberately pointer-only and must not be expanded into a navigation/game-domain object.
- **(verified):** Portal/Loot handlers produce legacy `EventAction`, then the navigation task layer translates it to `NavigationIntent` before the GUI executor. Their detection output is `EventDetection(local_minimap_pos, ...)`, which the event position stabilizer projects through `FrameRegistration`.
- **Architecture decision:** retain the existing domain transitions (`EventAction → NavigationIntent`) and add a GUI composition adapter that turns only concrete screen/key intents into `core.actions.ActionCommand`. Map-movement intent remains a domain/spatial request for the existing `MotionController` while its mapping/execution split is audited separately. This avoids falsely treating a stitched-map target as a physical pointer command.

## [Complete chain — action contract read] 2026-09-04

### A. Scope declared before reading

**Goal:** verify `ActionCommand` target semantics and adapters, then define a navigation composition adapter that uses them without adding a GUI dependency to `core.actions` or losing current click/key behavior.

**Files to inspect:** `core/actions/contracts.py`, `core/actions/mouse.py`, `core/actions/keyboard.py`, and navigation intent/executor tests.

**Decision gate:** only introduce a `MotionController` backend adapter if the generic command target already carries enough information for physical pointer/key dispatch; map-space movement remains explicit and unmodified otherwise.

### C. Action-contract findings

- **(verified):** `ActionCommand` is a sound generic primitive contract. Pointer commands require an already-calibrated `MappedPoint` whose destination is `PHYSICAL_SCREEN`; keyboard and gamepad commands carry validated device targets. The adapters deliberately have no map/game/window awareness.
- **(verified):** the current `CLICK_SCREEN` navigation intent carries only a legacy `screen_pos`; it is not enough to fabricate a generic pointer action safely, because the contract must state whether it is a logical capture pixel, a game-window point, or a physical desktop point.
- **(verified):** `PRESS_KEY` can immediately become `ActionCommand(KEY_CHORD, KeyboardTarget(...))`, but replacing its concrete dispatch needs a composition-level keyboard device/backend that preserves current `MotionController.press_key()` behavior and its window-input policy.
- **Corrected implementation order:** before changing the executor, inspect the existing `MotionController` click/key coordinate and backend behavior plus the existing desktop mapping factory. Then add an explicit legacy-navigation action request/dispatcher at the GUI boundary. It will preserve `MOVE_MAP` as a map-domain command, map a declared screen coordinate to `PHYSICAL_SCREEN` before forming pointer commands, and dispatch only primitive commands through the generic adapters.

## [Complete chain — legacy input and spatial read] 2026-09-04

### A. Scope declared before reading

**Goal:** identify the precise source coordinate spaces and side effects of legacy navigation screen click/key/move operations, and reuse the existing desktop-mapping contract rather than treating raw tuples as physical coordinates.

**Files to inspect:** `core/input/controller.py` or its concrete `MotionController` methods, `core/spatial/desktop_mapping.py`, the desktop action composition/proof, and the `NavigationIntent` model.

**Decision gate:** if the legacy executor's `screen_pos` is already physical desktop space, add an explicit identity mapping adapter with validation; if not, compose through existing calibration. Do not change behavior merely to fit an action DTO.

### C. Legacy input/spatial findings

- **(verified):** map movement is semantically distinct from primitive pointer input: `MotionController.move_to_map_target()` applies global-map direction projection, click-radius policy, bottom-UI guard, and its own real-input pipeline. It must remain a domain/spatial action until that mapping boundary is separately decomposed.
- **(verified):** generic `ActionCommand` currently lacks a one-click kind, while legacy `CLICK_SCREEN` performs exactly one click. Adding `ActionKind.CLICK` is a genuine generic contract gap; overloading double-click would change behavior.
- **(verified):** legacy direct screen click and key press are routed through the same `MotionController` controls, which enforce `control_enabled` and preserve existing focus/backend policy. The correct first backend bridge is therefore an adapter over those existing methods, not a second independent OS input route.
- **Implementation decision:** add generic single-click support, an explicit validated physical-screen identity mapping helper, and an interim `MotionControllerActionAdapter` that executes primitive `ActionCommand`s through the old controller. At the navigation composition edge, translate `MOVE_MAP` into a typed map-movement request and `CLICK_SCREEN`/`PRESS_KEY` into generic primitive commands. This creates one complete typed chain without pretending map coordinates are desktop pixels.

## [Complete chain — input semantics and tests] 2026-09-04

### A. Scope declared before reading

**Goal:** freeze the observable single-click/key behavior and verify the source of legacy event screen coordinates before adding the generic action bridge.

**Files to inspect:** `core/input/motion_controller/controls.py`, Portal/Loot handler interaction modules that construct `EventAction.click_screen` or `EventAction.press_key`, and existing input/navigation test locations.

**Expected regression contract:** disabled control produces no physical action; enabled direct click remains one click at the same physical coordinates; enabled key press retains its existing duration/backend path; `MOVE_MAP` is not converted into a desktop-pointer command.

### C. Input-semantics findings

- **(verified):** the current Portal and Loot handlers emit `EventAction.press_key(...)` only: Portal uses `d`; Loot uses the configurable pickup key. They do not create a direct-screen-click action today. Their key/action policy remains in the handlers and is not moved into the generic action package.
- **(verified):** `MotionController.click_screen_position()` passes its integer tuple to the controller's physical click pipeline unchanged; `MotionController.press_key()` enforces `control_enabled`, normalizes a key and delegates to the existing lazy PyDirectInput backend. Both are suitable temporary backend methods for typed primitive commands.
- **(verified):** navigation event hooks separately call `MotionController.press_key()` and must use the same new primitive-command dispatcher; otherwise the old direct-input escape hatch would remain.
- **Plan:** implement the action bridge in three guarded layers: generic `CLICK` + physical-point constructor; `MotionControllerActionAdapter` as a compatibility action backend; navigation/hook composition translators. Then create a pure EventDetection↔TargetDetection adapter and wire Portal/Loot detector outputs through it at the event monitor boundary. This makes all presently active old paths observable through common schemas while preserving the event state machines.
## [Complete chain — primitive action slice] 2026-09-04

### A. Scope declared before reading

**Goal:** implement Tasks 1–2 of the approved complete-chain plan: generic single click, explicit physical point construction, and an interim `MotionController` backend adapter with no navigation/event imports.

**Files to inspect:** `core/spatial/__init__.py`, `core/spatial/models.py`, current generic action test files, and `core/input/__init__.py` export conventions.

**Compatibility rules:** `ActionRequest` retains its historical move/double-click restriction; `MouseActionAdapter` gains click behavior only through `ActionCommand`; `MotionControllerActionAdapter` delegates to old public controller methods and never imports GUI, navigation task, Portal, or Loot modules.

### C. Primitive-action implementation findings

- **(verified):** `MappedPoint` already carries both source and destination coordinate spaces, and `Point2D` is the only additional spatial DTO needed. A `physical_screen_point()` constructor can safely mark a pre-existing physical point as an explicit identity mapping without pretending it came from an image calibration.
- **(verified):** `ActionResult` supports successful and deliberately skipped dispatch (`executed=False`) with command/target metadata, so disabled legacy control can be represented without raising or changing existing `MotionController` behavior.
- **Test plan:** extend the generic action and mouse tests for one click, add physical-identity mapping coverage, and add a fake-controller backend test for click/key success, disabled skip, and command-kind rejection. The tests must fail until the new primitive and adapter exist.

## [SYNC] 2026-09-04 — primitive actions and MotionController backend

### A. SYNC scope declaration

**Trigger:** add generic `CLICK`, physical-screen identity mapping, and `MotionControllerActionAdapter` as the compatibility backend for physical click and one-key commands.

**Directly changed files:** `core/actions/contracts.py`, `core/actions/mouse.py`, `core/spatial/desktop_mapping.py`, `core/spatial/__init__.py`, `core/input/action_adapter.py`, `core/input/__init__.py`, and focused action/spatial/controller tests.

**Impact chain:** `ActionCommand(CLICK|KEY_CHORD)` → validated `PointerTarget`/`KeyboardTarget` → `MouseActionAdapter` or `MotionControllerActionAdapter` → existing device or `MotionController` control policy.

### C. SYNC result

**Re-read impact surface:** generic action validation, generic mouse dispatch, spatial mapped-point semantics, `core.input` public exports, existing MotionController direct click/key policy, and their focused regressions.

**Verified behavior:** `CLICK` is a new generic command only; legacy `ActionRequest` still rejects it. The direct physical-point helper is explicit identity mapping, never desktop-frame mapping. The compatibility backend calls the historical `MotionController` public methods and records a skipped result when those methods decline disabled input.

**Verification:** initial red tests failed because `CLICK`, `physical_screen_point`, and the backend adapter were absent. After implementation, action/spatial/controller suites passed 14/14; existing public-action, keyboard, and gamepad suites passed 8/8; compilation and scoped diff checks passed.

**CODEBASE.md synchronized:** input/action/spatial inventory and module details now describe the single-click primitive, declared physical coordinates, and temporary controller backend.

## [Complete chain — navigation action composition] 2026-09-04

### A. Scope declared before reading

**Goal:** implement Task 3: make the live navigation executor and event-key hooks translate intents to typed composition actions, dispatch primitive actions through `MotionControllerActionAdapter`, and retain map movement through its explicit legacy spatial backend.

**Files to inspect:** `gui/modes/navigation/hooks/registration.py`, `tests/test_navigation_compact_actions.py`, and navigation task event-action conversion code that creates `CLICK_SCREEN` / `PRESS_KEY` intents.

**Compatibility rules:** intent `message` remains the human/audit reason; map click selection and `record_intent_click()` timing remain unchanged; missing `screen_pos`/key stays a no-op; only `CLICK_SCREEN` is declared existing `PHYSICAL_SCREEN` input at this compatibility boundary.

### C. Navigation-composition findings

- **(verified):** `core.navigation_tasks.intent_factory` is the sole event-action conversion boundary. It preserves `EventAction` in metadata and passes raw `screen_pos`/key forward, so the GUI input adapter is the correct place to assign the legacy direct-click coordinate-space declaration without contaminating events.
- **(verified):** `NavigationHookRuntime._press_key_once()` has a separate direct key path, explicitly turns control on, and returns its backend result to the hook instance. It can use the same one-key `ActionCommand` bridge without changing core hook registration or event semantics.
- **Implementation decision:** add `gui.modes.navigation.input.actions` as the domain-to-composition translator. It has an explicit `MapMovementAction` for stitched-map intent and a `PrimitiveNavigationAction` wrapping an `ActionCommand`; it is not a generic core module. Update the executor/hook runtime to consume it and permit an injected adapter in tests.
- **Regression plan:** a pure translator test locks coordinate declaration and no-op behavior; executor tests lock map direct-method selection, click/key command shape/reason, and click-record timing; hook tests lock that key hooks use the common primitive backend.

## [SYNC] 2026-09-04 — navigation intent and hook action composition

### A. SYNC scope declaration

**Trigger:** add explicit navigation composition actions and migrate live `CLICK_SCREEN` / `PRESS_KEY` intent dispatch plus navigation key hooks to `ActionCommand` and `MotionControllerActionAdapter`.

**Directly changed files:** `gui/modes/navigation/input/actions.py`, `gui/modes/navigation/input/__init__.py`, `gui/modes/navigation/input/intent_executor.py`, `gui/modes/navigation/hooks/registration.py`, and focused navigation intent/hook tests.

**Impact chain:** `EventAction` → unchanged `NavigationIntent` → `translate_navigation_intent()` → `MapMovementAction` or `PrimitiveNavigationAction` → `MotionController` map policy or `MotionControllerActionAdapter` → legacy input backend.

### C. SYNC result

**Re-read impact surface:** navigation intent factory payload shape, executor map-click branch, Hook runtime key dispatch, generic primitive contract/backend, and focused non-GUI regressions.

**Verified behavior preservation:** the executor retains the legacy map movement methods, force-click selection, input enablement, click-record timing, status suffix, and absent payload no-op behavior. Click/key actions now receive explicit typed commands and route through the existing `MotionController` methods, so they keep legacy control-enable and platform policy. Key hooks use the same backend after their pre-existing explicit enablement.

**Verification:** initial translator/hook tests failed before the new composition module and injected adapter existed; after implementation, 6 focused tests passed. `compileall` and scoped diff checks passed.

**CODEBASE.md synchronized:** navigation input inventory, executor/hook responsibilities, full compatibility flow, and current-risk statement now distinguish map-space movement from physical primitive dispatch.

## [Complete chain — event perception schema bridge] 2026-09-04

### A. Scope declared before reading

**Goal:** implement Tasks 4–5: define a pure, reversible EventDetection ↔ TargetDetection bridge and identify the event monitor composition point that can run legacy Portal/Loot output through it without modifying detector algorithms or handler state machines.

**Files to inspect:** `core/events/models.py`, `core/events/monitor.py`, `core/events/types/portal/minimap_detection/conversion.py`, and `core/events/types/loot/detection/conversion.py`.

**Contract:** `EventDetection.local_minimap_pos` maps only to `TargetDetection(center, coordinate_space=MINIMAP)`; event type, confidence, timestamp and all existing metadata must survive a copied conversion. Generic detections in any other coordinate space must be rejected before event stabilization/projection.

## [Complete chain — event bridge implementation] 2026-09-04

### A. Scope declared before reading

**Goal:** finish the approved Portal/Loot perception-schema seam and run the full compatibility-chain audit. The bridge must pass each legacy `EventDetection` through the generic `TargetDetection` contract at the `EventMonitor` composition point, retain the legacy event returned to stabilization/memory/handlers, and expose a copied generic observation list for later UI/debug or new perception producers.

**Files to inspect:** `core/events/models.py`, `core/events/monitor.py`, Portal/Loot conversion modules, shared perception DTOs, and event-monitor tests.

**Acceptance rules:** the bridge is pure and reversible for minimap detections; coordinate-space mismatch is rejected explicitly; metadata has no shared mutable reference; detector algorithms, Portal/Loot configuration, handler state, and `EventPositionStabilizer` behavior are unchanged. After focused tests, run the complete suite and document any pre-existing failures separately from this work.

### C. Event-bridge findings and implementation result

- **(verified):** Portal and Loot detector outputs share a single live composition seam in `EventMonitor.detect()`. Normalizing there makes the shared perception contract active in both runtime paths without putting game templates, HSV rules, pickup keys, timing, or handler state into `core.perception` or the bridge.
- **(verified):** `EventDetection.local_minimap_pos` maps losslessly to `TargetDetection.center` in `MINIMAP`; event type is deliberately a required explicit input for the reverse direction, so an arbitrary generic target cannot silently enter an event state machine.
- **(verified):** deep-copied metadata protects both detector output and `EventMonitor.last_target_detections` from nested-mutation leaks. Valid legacy bbox/text are exposed through standardized fields while raw metadata stays intact for a round trip.
- **Corrected scope statement:** the completed bridge is a runtime-schema migration, not a replacement of Portal/Loot algorithms with `PerceptionEngine`. Their existing detector packages remain the tested compatibility implementations; a future provider-backed replacement can enter the same reverse bridge deliberately.
- **Regression result:** 43 focused mapping/localization/navigation/action/event tests pass. The full discovery suite now contains 197 tests: 191 pass, 2 skip, 3 `PathFinder` specification failures, and 1 advanced-settings loose-import error. The four failures match the pre-existing audit categories and do not import the new event bridge or action-composition modules.

## [SYNC] 2026-09-04 — complete legacy perception-to-action chain

### A. SYNC scope declaration

**Trigger:** introduce the reusable event-perception adapter and connect the last active Portal/Loot output seam after the previously completed mapping evidence, localization result, and navigation/action composition slices.

**Directly changed files:** `core/events/perception_adapter.py`, `core/events/monitor.py`, `core/events/__init__.py`, event-bridge tests, and the affected architecture/checkpoint documents. This final slice is composed with the already modified generic action, spatial, input, navigation input, and hook files in the approved plan.

**Impact chain:** legacy Portal/Loot detector → `EventDetection` → `TargetDetection(MINIMAP)` → independent `EventDetection` → unchanged `EventPositionStabilizer` → `EventMemory`/`EventTask` → `EventAction` → `NavigationIntent` → typed map request or `ActionCommand` → existing MotionController/device policy.

### C. SYNC result

**Re-read impact surface:** shared perception DTO coordinate rules, EventMonitor detector cache/output ordering, position stabilization, memory task creation, generic action backend, navigation intent execution, and hook key dispatch.

**CODEBASE.md synchronized:** directory inventory now lists the perception adapter; event module notes and function index specify both conversion contracts and the monitor composition step; the integration-flow/risk note now records that the schema bridge is complete rather than pending.

**Verification:** event bridge tests 5/5; end-to-end compatibility focus set 43/43; `compileall -q core gui tests` and `git diff --check` pass. Full discovery is 191 passed, 2 skipped, 3 known PathFinder failures, and 1 known advanced-settings loader error out of 197 tests.

**Next work is intentionally separate:** P4 feature/motion/ML provider adapters, P5 game-window/viewport calibration controls, P6 workbench GUI composition, P8 concrete workflows (including the later PoE scenario), and a dedicated diagnosis/fix decision for the four independent full-suite baseline failures.

## [Primary-monitor capture default] 2026-09-04

### A. Scope declared before implementation

**Goal:** make the application's screenshot-localization default capture only the Windows primary monitor and map recognition coordinates to that same monitor's physical rectangle. Preserve virtual-desktop capture only as an explicit reusable provider choice.

**Verified non-compliance:** `DesktopFrameSource()` currently defaults to `WindowsDesktopGeometryProvider`, whose `current_geometry()` reads `SM_X/Y/CX/CYVIRTUALSCREEN`; the OCR action proof therefore captures the full virtual desktop by default.

**Files in scope:** `core/platform/desktop_frame_source.py`, its focused frame-source tests, OCR-action composition coverage, and the perception checkpoint/codebase notes. The change must not affect minimap capture or any caller that explicitly injects a geometry provider.

### C. Primary-monitor default implementation result

- **(verified):** the prior no-argument composition selected `WindowsDesktopGeometryProvider`, which reads `SM_X/Y/CX/CYVIRTUALSCREEN`; this was the exact cause of the unintended multi-monitor capture.
- `WindowsPrimaryMonitorGeometryProvider` now reuses the established Windows DPI-awareness bootstrap and reads only `SM_CXSCREEN` / `SM_CYSCREEN`, returning the primary monitor's physical rectangle at `(0, 0)`.
- `DesktopFrameSource()` now uses that primary-monitor provider by default. It still accepts any injected `DesktopGeometryProvider`, and `WindowsDesktopGeometryProvider` remains exported as the intentional all-monitor option. No recognition algorithm, coordinate mapper, action adapter, minimap capture, or legacy navigation caller was changed.
- Regression coverage proves both the primary metrics/physical geometry and the no-argument composition choice. The pre-existing injected negative-origin virtual-desktop test remains intact, so the generic multi-monitor route is protected too.

## [SYNC] 2026-09-04 - primary-monitor capture default

### A. SYNC scope declaration

**Trigger:** screenshot localization must use the Windows primary monitor only, while preserving the reusable virtual-desktop provider for an explicitly selected multi-monitor workflow.

**Directly changed files:** `core/platform/desktop_frame_source.py`, `core/platform/__init__.py`, `tests/test_desktop_frame_source.py`, and the affected architecture/checkpoint records.

### C. SYNC result

**Impact chain:** `utils/run_desktop_ocr_action_proof.py` -> `DesktopFrameSource()` -> `WindowsPrimaryMonitorGeometryProvider` -> primary-monitor `ScreenGeometry` -> capture -> `FULL_SCREEN` detection -> `DesktopCoordinateMapper` -> `PHYSICAL_SCREEN` mouse action. An explicit `WindowsDesktopGeometryProvider()` remains the alternate all-monitor geometry source.

**Verification:** the focused source/mapping/OCR-workflow suite passes 7/7; `compileall -q core/platform core/spatial workflows utils`, public platform imports, and `git diff --check` pass. A read-only live `DesktopFrameSource().capture()` produced a `2560 × 1600` image with matching primary physical geometry `(0, 0, 2560, 1600)` at 150% DPI; it did not invoke OCR, mouse movement, or clicking.

**Full-suite audit:** `python -m unittest discover -s tests` ran 210 tests: 203 passed, 2 skipped, 3 pre-existing `PathFinder` policy assertion failures, and 2 unrelated test-loader errors. One loader error is the existing advanced-settings loose-module import; the other is `test_wall_version_storage`, which imports a map-editor version-storage module not present in this worktree. Neither failure imports the changed platform/frame-source files.

## [POE-MAP-DEVICE-PROBE] 2026-09-05

### A. Scope

Temporary, repository-external probe for the approved PoE flow: primary-screen
capture → RapidOCR target selection → fixed player anchor `(1335, 850)` →
short Xbox left-stick pulse → recapture/feedback → interaction gate → A.

### C. Result

- The probe now uses adaptive pulse timing, progress estimation, explicit stick
  neutralization, Y-axis inversion matching the host (`LeftY=+` is up), and a
  no-progress stop condition. Its target text matching handles both simplified
  and traditional `地图装置` output and removes OCR whitespace.
- Offline probe tests pass **4/4**: main-label selection over minimap duplicate,
  axis sign, progress/speed update, and dry-run action isolation.
- Live dry-run succeeded on the primary monitor (`2560×1600`): detected
  `地圖裝置` at approximately `(1721.94, 214.10)`, anchor delta
  `(386.94, -635.90)`, distance `744.37 px`, confidence `0.998978`; no input
  was sent.
- Live execution was intentionally not started because the named pipe rejected
  the non-elevated Python process (`Errno 5 Access Denied`). No joystick or A
  command was delivered. The probe now reports this as `input_unavailable` JSON.
- A later elevated run without `--start-controller` reached the action loop while
  Controller 1 was still paused; its commands were therefore neutralized by the
  host and must not be used as evidence that the game rejected joystick input.
  The first elevated run with temporary controller startup found no OCR target
  before the pulse, so it also sent no movement.
- The probe now holds maximum-strength stick values with periodic refreshes for
  the full pulse and explicitly neutralizes afterward; this behavior is covered
  by the offline tests.

The next checkpoint is to rerun the external probe from a terminal with the
same administrator level as the VirtualGamepad host, first with one short pulse
and then with the bounded full loop. The formal core and GUI remain unchanged.

## [POE-MAP-DEVICE-SMOOTH-MOTION] 2026-09-05

### A. Root-cause investigation

- Live trace completed six movement corrections in about 22 seconds. Each
  correction published a 150 ms full-strength pulse, then waited for the next
  full-screen capture/OCR cycle.
- Primary-screen capture took about 60-190 ms, while RapidOCR on the full
  2560x1600 frame took about 1.6-2.8 seconds. The previous 450 ms route TTL
  therefore expired during recognition and the host returned the stick to
  neutral between corrections. This explains the visible stop/start motion.

### C. Implementation and verification

- Added the device-neutral `core.actions.StickSlewLimiter`, which transitions
  two-axis stick values at a bounded rate and supports immediate neutral reset.
- The external PoE probe now uses the limiter for direction changes and runs a
  short stick lease refresher during capture/OCR. It leaves the current command
  active between frames, stops the lease before A or any exit path, and then
  neutralizes/resets the controller.
- Focused verification: gamepad motion tests 3/3, existing gamepad/action tests
  13/13, and external PoE probe tests 6/6. Python compilation and diff checks
  pass.
- Full discovery still reports the existing baseline issues: three Pathfinder
  policy assertion failures and one advanced-settings loose-import error; no
  failure imports the new motion module.

## [SYNC] 2026-09-18 - repository layout migration

### A. SYNC scope declaration

**Trigger:** reorganize the repository around bottom-up reusable layers, separating
Python source, UI, external adapters, independent services, resources, writable
data, tools, documentation, and packaging while preserving the verified runtime
behavior.

**Directly changed areas:** root `core/`, `gui/`, `virtual_gamepad/`,
`lan_input_sync/`, `distribution/`, `installer/`, `assets/`, `configs/`,
`map_data/`, `debug/`, `utils/`, `workflows/`, scattered root documentation,
tests that import moved modules, and the root bootstrap entry point.

**Expected propagation:** all Python imports must use the `auto_modules` package;
runtime resource/data lookup must use one path API; C# `ProjectReference` values,
launcher paths, installer payload paths, packaging manifests, test discovery, and
developer commands must follow the new layout. Real input and LAN synchronization
remain disabled during migration verification.

**Protected checkpoint:** annotated tag `pre-reorg/2026-09-18` points to
`be698389ac3ab640fb5f2a1b4324236cc24e5cb1`.

## [SYNC] 2026-09-18 - repository layout and adapter-boundary cleanup

### A. SYNC scope declaration

**Trigger:** continue the approved repository layout migration, correct remaining
imports and physical paths, and make the bottom-up generalization rule true in
the moved action/follow/Host code.

**Directly changed files:**

- `README.md`, `ARCHITECTURE_GUIDE.md`, `CODEBASE.md`
- `packaging/distribution/README.md`, `packaging/distribution/verify_install.ps1`, `packaging/installer/README.md`
- `services/virtual_gamepad/README.md`, `services/virtual_gamepad/docs/acceptance.md`, `services/lan_input_sync/README.md`
- `services/virtual_gamepad/launcher/src/VirtualGamepadLauncher/LauncherPaths.cs` and its tests
- `src/auto_modules/core/actions/keyboard.py`, `src/auto_modules/core/actions/__init__.py`
- `src/auto_modules/core/lan_follow/`, `src/auto_modules/adapters/input/`, `src/auto_modules/adapters/host/`, `src/auto_modules/adapters/virtual_gamepad/`
- `src/auto_modules/application/follow/`, `src/auto_modules/application/event_workbench/service.py`
- affected Python tests and `tools/virtual_gamepad/run-demo.ps1` / `live_gamepad_probe.py`

**Expected propagation:** production imports, C# launcher root calculations,
installer verification data directories, action/follow adapter boundaries,
CODEBASE current-path references, and current developer commands.

**Safety boundary:** no real Host process, keyboard/mouse/virtual-controller
input, or LAN synchronization was started.

### C. SYNC result

**Verified changes:**

- The independent launcher now derives `AutoModulesRoot` from
  `services/virtual_gamepad`, derives `SourceRoot` from that repository root,
  and retains `.venv`/workspace .NET lookup under the parent workspace. This
  removes the one-level path drift introduced by the service move.
- `PyDirectInputKeyboardDevice`, `ProgramGamepadOutput`, Host-compatible clock,
  and `FollowTransport` are concrete adapters. `core.actions` and
  `core.lan_follow` now expose only device-neutral contracts and algorithms.
- Follow service consumes `HotkeyTriggerSource`; it no longer reads Win32 key
  state directly. Host/LAN wire translation remains in adapters.
- Packaging docs and verification now use `packaging/...`, `services/...`, and
  writable `data/maps`; current README and Architecture Guide describe the
  actual `src/auto_modules` layout and import policy.
- `CODEBASE.md` now includes the physical-path mapping, new modules/contracts,
  startup/share/payload flows, external integration details, and migration
  risks. Historical logical references remain explicitly mapped instead of
  being mistaken for current root directories.

**Verification:**

- `python -m compileall -q src tests tools packaging`: passed.
- Focused migration/adapter/UI/path/distribution suite: **27 passed**.
- Full Python suite: **407 passed, 1 skipped, 10 subtests passed, 3 known
  Pathfinder policy failures** (`tests/test_pathfinder.py`); the three failures
  reproduce the pre-migration behavior and were not changed in this sync.
- Active-source old-import scan: zero `from/import core`, `gui`, `workflows`,
  or `logging_system` matches.
- Core upward-dependency scan: zero imports from `application`, `adapters`,
  `ui`, or `bootstrap`; concrete OS/device dependency scan: zero matches.
- `git diff --check`: passed (only repository line-ending normalization
  warnings).
- C# build/test: not run because this machine has .NET runtime 6.0.23 but no
  installed .NET SDK. Real input, Host, LAN, and game verification remain
  opt-in and were not run.

**Coverage update:**

| File/group | Previous | Current | Evidence |
|---|---|---|---|
| `src/auto_modules/paths.py` | migrated | verified | focused runtime-path tests and payload smoke path assertions |
| `src/auto_modules/core/actions/keyboard.py` | migrated | verified | generic adapter has no concrete PyDirectInput implementation |
| `src/auto_modules/adapters/input/keyboard_device.py` | new | verified | fake-module contract and compile/import checks |
| `src/auto_modules/adapters/virtual_gamepad/program_output.py` | new | verified | lease/TTL/slew tests pass without Host connection |
| `src/auto_modules/core/lan_follow/models.py` | new | verified | immutable position/event contract imports and worker tests |
| `src/auto_modules/adapters/host/follow_transport.py` | new | verified | TTL/IPC-delay/expired-event tests pass with fake client |
| `src/auto_modules/application/follow/service.py` | migrated | verified | follow service suite and adapter hotkey injection |
| `LauncherPaths.cs` + tests | migrated | static verified | source/test path assertions; SDK unavailable for compilation |
| `README.md`, `ARCHITECTURE_GUIDE.md`, `CODEBASE.md` | stale | synchronized | current physical layout, contracts, flows and risks added |

**Revised prior conclusion:** the initial migration audit treated all remaining
`core` action/follow files as generic after their move. Re-reading their bodies
showed that PyDirectInput, Win32 clock and Host/LAN wire calls were still concrete
side effects; those implementations now live in adapter modules while core
contracts remain reusable.

**Next work:** run the C# test matrix in a machine with .NET 8 SDK, then handle
the three independent Pathfinder policy failures in a separate behavior-focused
task. Do not use the migration tag as a substitute for that diagnosis.

## [SYNC] 2026-09-18 - post-reorg active-path audit

### A. SYNC scope declaration

**Trigger:** resume work from the completed layered repository layout before
planning the PoE2 live-terrain page. Confirm the current checkout is based on
`0c507ef`, audit active code/tool/ProjectReference/test/document paths, and do
not revive the pre-reorganization root layout.

**Baseline:** `HEAD` is `0c507ef` on `feat/offline-installer`; no pre-existing
working-tree changes were overwritten. The protected tag name
`pre-reorg/2026-09-18` remains untouched. The local tag currently resolves to
`c9e96c7891d029d9593f8fa9aa21a753ea56352e`, which differs from the handoff's
reported object `be698389`; this discrepancy is recorded without rewriting the
tag.

**Directly changed files:**

- `src/auto_modules/adapters/perception/rapidocr_models.py`
- `tools/probes/install_perception_ocr_model.py`
- `CODEBASE.md`
- `docs/PERCEPTION_ENGINE_CHECKPOINT.md`

The C# Host `ProjectReference` was checked against the filesystem and kept at
`../../../../lan_input_sync/...`, which correctly resolves to
`services/lan_input_sync/...` from the new `services/virtual_gamepad/...`
location; no source change was needed there.

### C. SYNC result

- Active production Python imports are `auto_modules.*`; no `from/import core`,
  `gui`, `workflows`, or `logging_system` imports remain in `src`, `services`,
  `tools`, or `tests`.
- The RapidOCR model error message and current checkpoint/CODEBASE entries now
  point to `tools/probes/install_perception_ocr_model.py` and
  `resources/assets/perception_models/`, matching the reorganization.
- Historical plans and archived architecture documents retain their original
  paths intentionally; they are historical records, not executable current
  instructions.
- CodeGraph confirms the current UI extension point remains
  `src/auto_modules/ui/main_window.py` -> `MainWindow.setup_ui()` /
  `QStackedWidget`, while offline map loading remains separate from the live
  PoE2 business adapter. The new feature must be planned against these current
  paths only.

**Verification:**

- `python -m compileall -q src tests tools packaging`: passed.
- `python -m pytest tests/test_perception_rapidocr_models.py -q`: **7 passed**.
- `python -m pytest tests/virtual_gamepad_scripts/test_start_virtual_gamepad.py tests/virtual_gamepad_scripts/test_live_gamepad_probe.py -q`: **6 passed**.
- `git diff --check`: passed; only existing LF/CRLF normalization warnings remain.
- No real Host process, game, input, or LAN synchronization was started.

## [SYNC] 2026-09-19 - PoE2 实时地形预览第一阶段

### A. SYNC 范围声明

**触发任务：** 按底层通用能力、上层业务组合的设计规则，完成 PoE2
实时地形的第一阶段：初始化、手动抓取、校验、内存转换和只读展示。

**边界：** 不改造离线绘图地图包，不接入自动跟随、玩家定位、路径规划、
动态障碍、Xbox/虚拟手柄、Host 或 LAN；真实游戏采集保持显式手动操作。

### B. 直接变更

- `src/auto_modules/adapters/poe2_live_terrain/`：正式运行时适配器，包含
  外部 `live_preview.py` 命令边界、native `yx` 网格转换、不可变快照契约和
  进程内存储。
- `tools/experiments/poe2_live_terrain/`：只保留到正式适配器的兼容导出，
  避免实验目录和运行时出现两套实现。
- `src/auto_modules/ui/modes/poe2_live_terrain/`：注入式页面、状态控制、
  metadata 展示和 `ScalableMapWidget` 只读渲染。
- `src/auto_modules/ui/main_window.py`：追加独立第 8 个页面，保持既有页面
  索引不变；关闭时只清理本页内存状态。
- 新增适配器契约、native grid、内存服务、presenter、页面和主窗口聚焦测试。

### C. 验证与安全边界

- `Poe2CaptureAdapter` 只接受 `tool=manual-live-terrain-capture` 的新 manifest，
  拒绝 checkpoint、失败命令、未变化旧 manifest，以及逃出 producer output 的
  NPZ 路径。
- NPZ 以 `allow_pickle=False` 读取，数组保持原生 `height x width` / `yx` 方向，
  进入 `TerrainSnapshot` 后复制并设为只读；失败抓取会先清除旧快照。
- 当前已通过 PoE2 页面、适配器、契约、转换、内存服务和主窗口聚焦测试；最终
  compileall、组合测试及 `git diff --check` 在本轮收尾时重新执行。
- 本轮未启动 PoE2、Host、LAN 或任何真实输入；真实游戏内效果仍需显式验收。

## [SYNC] 2026-09-19 - PoE2 手动测试运行链路与日志

### A. 本轮增量

- `logging_utils.py` 为 PoE2 边界建立独立日志文件：
  `data/logs/poe2_live_terrain.log`。
- 采集命令、会话状态、manifest 校验、NPZ 转换、内存替换、UI 操作、
  测试归档和异常均记录为带 `step=` 的日志事件。
- 新增显式 `TerrainDebugArchive`，主窗口临时注入到
  `data/poe2_live_terrain_test/`，保存转换后的 `latest.npz` 和
  `latest.json`；页面渲染仍只读取本次内存快照。
- 主窗口已经启动并保持运行，未自动触发 PoE2 初始化或采集。

### B. 验证

- `python -m compileall -q src tests tools packaging`：通过。
- PoE2 适配器、归档、页面、主窗口和既有地图页面组合测试：**20 passed**。
- Serena 诊断：新增服务和归档逻辑无业务类型错误；PySide6/NumPy 的提示是
  Serena 当前解释器未加载项目运行时依赖，实际测试环境已通过。
- 未启动 PoE2、Host、LAN 或真实输入；用户可在已启动窗口中手动验证完整链路。

## [SYNC] 2026-09-19 - 原生地形转旧绘图视觉格式

### A. 发现

实际 `latest.npz` 的 `known_mask/explored_map` 覆盖整个原生矩形，不能直接沿用
旧地图的“已探索区域”渲染，否则包围矩形会整块变成白色。原生契约中真正代表
地图形状的是 `cell_state == 1` 的可行走区域；`cell_state == 0` 同时包含内部
阻挡和区域外背景。

### B. 实现

- `presenter.py` 现在以已知可行走格作为深灰底面。
- 使用显式黑色 padding 的形态学边界生成白色轮廓，保留房间/通道内部边界，
  区域外和未知格保持黑色。
- 原始 `TerrainSnapshot`、内存快照和本地归档数组均不变，转换只发生在 UI
  展示适配器。

### C. 验证

- 使用当前 `data/poe2_live_terrain_test/latest.npz` 生成的预览已经呈现为图一
  的黑底、灰面、白色轮廓风格。
- presenter、页面、适配器、归档和会话测试：**18 passed**。
- `compileall`：通过；主窗口已重启并加载新 presenter。

## [SYNC] 2026-09-19 - PoE2 单人定位、独立监控与轨迹显示

### A. SYNC 范围声明

**触发任务：** 完成 PoE2 单人实时定位验证链路：从 native terrain 构建定位参考，
识别小地图人物真实局部坐标，首帧全局匹配、后续局部跟踪和恢复，在完整地图上
显示人物 marker/轨迹；同时落实 PoE2 独立监控配置边界。

**直接变更文件：**

- `src/auto_modules/core/localization/`：观测契约、全局/局部状态机和确认轨迹（前一批次已完成，本轮复核其调用边界）。
- `src/auto_modules/core/spatial/monitor_binding.py`、`src/auto_modules/core/spatial/__init__.py`：通用截图矩形契约。
- `src/auto_modules/adapters/poe2_live_terrain/monitor_config.py`、`monitor_source.py`、`__init__.py`：PoE2 独立配置与区域截图适配。
- `tools/experiments/poe2_live_terrain/terrain_reference.py`、`calibration.py`、`player_policy.py`、`runtime.py`、`__init__.py`：PoE2 业务组合和默认 HSV/模板适配。
- `src/auto_modules/ui/modes/poe2_live_terrain/page.py`、`presenter.py`、`monitor_dialog.py`：页面监控生命周期、预览、状态、marker/轨迹和独立配置窗口。
- `src/auto_modules/ui/main_window.py`：组合根注入 PoE2 runtime、截图源和配置存储。
- `tests/`：新增引擎、配置、运行时和 UI 聚焦覆盖。

**预计连带影响：** PoE2 主窗口第 8 页和关闭生命周期；`TerrainSnapshot` 捕获后新增
定位参考转换；不修改 `NavigationCore`、`NavConfig`、导航页、Gamepad/LAN、Host 或输入适配器。

### B. 影响扩散与本轮发现

- `(verified)` `build_reference()` 只消费 `TerrainSnapshot.cell_state/known_mask`，
  生成不可变 `walkable_mask/wall_layer/explored_map`；UI `QPixmap` 不进入定位链路。
- `(verified)` `select_single_player()` 对高于阈值的候选要求恰好一个；无候选或多候选
  都返回 `None`，因此不会以小地图中心伪造人物位置。
- `(verified)` `Poe2LocalizationRuntime.tick()` 的顺序是 capture -> observation ->
  单人选择 -> `MapLocalizer.update()` -> 仅 fresh 结果追加 `TrajectoryBuffer` -> 发布
  `Poe2LocalizationState`；失败原因包含 `player_not_detected`、`local_match_failed`、
  `global_match_failed` 等。
- `(verified)` 首帧 `_global_match()` 在完整 terrain reference 上匹配，后续 `_local_match()`
  只在预测人物附近的显式半径内匹配；`MapLocalizer` 在局部失败帧不偷偷全局 fallback，
  下一帧进入恢复全局匹配。
- `(verified)` `Poe2MonitorConfigStore` 只读写 PoE2 自己的 `monitor.json`，原子替换临时文件；
  不读取 `NavConfig`、`app_context.monitor_region` 或导航目录。
- `(partial)` 默认 wall/template 比例、Y 方向和 HSV 人物阈值仍需真实 PoE2 样本校准；
  默认 runtime 具备显式失败状态，但本轮没有运行中的 PoE2 进程，未宣称实机定位成功。

**修订的旧结论：** 原来断点写的是“页面尚无实时监控、人物定位或轨迹”；本轮已实现
代码和合成测试，状态改为“代码批次完成，等待真实 PoE2 小地图校准与实机验收”。

### C. 验证与安全边界

- `python -m pytest tests/test_localization_observations.py tests/test_map_localizer.py tests/test_localization_trajectory.py tests/test_localization_result.py tests/test_phase_tracker.py tests/test_local_matcher.py tests/test_monitor_binding.py tests/poe2_live_terrain tests/test_poe2_monitor_dialog.py tests/test_poe2_live_terrain_page.py tests/test_poe2_live_terrain_presenter.py tests/test_poe2_live_terrain_monitoring.py tests/test_main_window_poe2_terrain_page.py -q`：**50 passed**。
- `python -m compileall -q src tests tools packaging`：通过。
- `git diff --check`：通过；仅有工作区既有 LF/CRLF 规范化提示。
- Serena：新增纯 Python 引擎/配置文件无诊断；当前 Serena 语言服务器对 PySide6、numpy、cv2
  的 import 提示属于解释器环境提示，实际运行测试已加载依赖并通过。
- 未启动 PoE2、Host、LAN 或任何 Xbox/键盘/鼠标输入；未执行网络同步。真实验证仍由用户
  手动打开游戏、配置小地图矩形后进行。

完整回归结果为 `448 passed, 2 skipped, 4 failed, 10 subtests passed`。失败来自既有
`pydirectinput` distribution metadata 缺失和 `PathFinder` 三个行为断言；本轮没有修改
分发解析或路径规划模块，PoE2 focused suite 仍为 `50 passed`。

### D. 下一轮计划

1. 在真实 PoE2 中配置小地图矩形并记录截图尺寸、人物图标候选特征和 HSV 阈值。
2. 用实机样本校准 native terrain 与 minimap 的比例、X/Y 方向、Y 翻转和 marker offset。
3. 记录首帧 global、local tracking、recovery 的置信度与耗时，必要时只调整 PoE2 业务参数。
4. 继续保持路线规划、自动跟随、多人身份选择和真实输入为后续阶段，不把这些策略下沉到引擎。
## [SYNC] 2026-09-19 - 通用引擎与 Torchlight 业务域边界收敛

### A. 本轮范围声明

- 将 `core/events/follow_chain.py` 的可复用动作链运行时收敛为通用
  `core/events/automation/action_sequence.py`，保留仅用于迁移兼容的别名。
- 将 Torchlight 事件定义注册收口到 `features/torchlight/composition.py`，
  导航 UI 只依赖业务组合入口，不直接拥有 Portal/Loot 定义。
- 将 Follow UI 归入 `ui/modes/torchlight/follow/`，同步主窗口、事件工作台和
  现有测试引用。
- 复核并更新 `CODEBASE.md`、`ARCHITECTURE_GUIDE.md`、`src/auto_modules/ui/modes/ARCHITECTURE.md`
  中受影响的架构描述。

### B. 读取目标

- `src/auto_modules/core/events/follow_chain.py`
- `src/auto_modules/features/torchlight/{composition.py,follow/*}`
- `src/auto_modules/ui/modes/{follow/*,events/workbench.py,navigation/event_adapter.py}`
- `src/auto_modules/ui/main_window.py`
- 跟随、事件链和架构边界测试

### C. SYNC 结果

**直接变更：**

- Portal、Loot、Follow、FollowerPlanner、Follow replay/benchmark 已从通用层迁至
  `features/torchlight/`；PoE2 runtime/calibration/policy/reference 已从实验目录
  提升到 `features/poe2/live_terrain/`，旧实验包只保留兼容导出。
- `core/events/automation/action_sequence.py` 现承载通用、有界、tick 驱动的声明式
  动作序列；`features/torchlight/skills/follow_chain.py` 提供业务 facade，旧
  `core/events/follow_chain.py` 仅保留兼容别名。
- `features/torchlight/composition.py` 是 Portal/Loot 注册入口；`MainWindow` 将该工厂
  注入 `NavigationModeWidget`，导航模块在无注入时只创建空的通用 `EventRegistry`。
- Follow 页面和编辑器迁至 `ui/modes/torchlight/follow/`；主窗口、事件工作台和测试
  已同步导入路径。
- 修复 `features/torchlight/follow/__init__.py` 重复内容，恢复
  `core.events.automation` 原有 repository/router/execution 公共导出，避免扩大重构
  影响面。

**连带重读文件：**

- `core/events/{registry.py,event_lifecycle.py,automation/__init__.py}`
- `features/torchlight/follow/{config.py,workers.py,service.py}`
- `ui/{main_window.py,modes/navigation/widget.py,modes/events/workbench.py}`
- 跟随、事件、PoE2、路径和架构边界测试

**CodeGraph：** 已同步并验证调用面；`ActionSequenceDefinition` 的生产调用只来自
通用自动化导出、迁移兼容层、Torchlight skill facade 和编辑器验证；`FollowPage`
只由 Torchlight UI public API 和 `MainWindow` 使用。

**验证：**

- 架构边界与 Follow 聚焦：`42 passed`。
- PoE2、事件感知、路径聚焦：`46 passed`。
- 事件自动化聚焦：`81 passed`。
- `python -m compileall -q src tests tools packaging`：通过。
- 全量：`470 passed, 2 skipped, 4 failed, 10 subtests passed`。四个失败均与迁移前
  已知基线一致：一个为本机缺失 `pydirectinput` distribution metadata，三个为既有
  `PathFinder` 行为断言；本轮未改发布依赖选择或通用 Pathfinder。

**修订旧结论：** 先前文档将 Portal/Loot 描述为 `core.events.types` 的“通用事件类型”，
并将 PoE2 业务 runtime 描述为由 `tools/experiments` 承载。当前权威结论为：这些都是
游戏业务组合；通用层只保留可脱离游戏术语复用的感知、事件、定位、导航和动作能力。

**安全边界：** 本轮没有启动 Host、LAN、游戏进程或任何键盘、鼠标、Xbox 输出；只运行
静态编译、offscreen/单元/loopback 测试和 CodeGraph 索引。

## [SYNC] 2026-09-19 - 导航 UI 的游戏业务边界彻底收敛

### A. SYNC 范围声明

**触发任务：** 在 Portal、Loot、Follow 已迁入 `features/torchlight/` 的基础上，继续清理
通用导航 UI 中残留的 Torchlight 窗口名、Portal 手工测试状态机和 Loot 专用覆盖层，确保
通用层只消费显式注入的窗口查找器、事件调试能力和领域中立的可视化描述。

**直接变更文件（预计）：**

- `src/auto_modules/ui/modes/navigation/event_adapter.py`
- `src/auto_modules/ui/modes/navigation/events/`
- `src/auto_modules/ui/modes/navigation/presentation/event_overlay.py`
- `src/auto_modules/ui/modes/navigation/composition/lifecycles.py`
- `src/auto_modules/ui/modes/navigation/runtime/`
- `src/auto_modules/ui/modes/navigation/widget.py`
- `src/auto_modules/ui/main_window.py`
- `src/auto_modules/ui/modes/torchlight/` 与 `features/torchlight/` 中必要的业务适配入口
- `tests/test_architecture_boundaries.py` 及相关导航/事件聚焦测试

**预计连带影响：** 导航事件配置对话框、手工事件测试启停、导航帧循环的调试状态、
事件覆盖层绘制和主窗口组合注入；不改变识别、定位、路径规划、控制器输出、Host 或 LAN
协议，也不触发任何真实输入或网络同步。

### B. 第一轮边界复核结果

- `(verified)` `event_adapter.find_default_game_window_rect()` 在通用导航模块中写死
  `Torchlight/UnrealWindow`；窗口选择必须改为组合根注入。
- `(verified)` 通用导航生命周期、帧循环和 widget 仍以 `portal_test_controller`、
  `run_portal_manual_test` 等业务名称管理一套本质上可通用的“手工事件测试会话”。
- `(verified)` `presentation/event_overlay.py` 直接读取 `loot` 配置并绘制玩家中心排除圆，
  这是 Torchlight Loot 的调试策略，不应由通用导航展示层识别事件类型。
- `(verified)` `core` Python 源码中已无 Portal/Loot/Torchlight/PoE2 业务词；当前剩余
  泄漏集中在 UI 组合边界，而非底层引擎。

**修订的旧结论：** “导航 UI 已经完全不拥有 Torchlight 业务”仅对事件定义注册成立；
窗口识别、Portal 手工测试和 Loot 覆盖层仍需继续拆分。

**覆盖进度更新：** 本轮完整复核了 `navigation/event_adapter.py`、`events/lifecycle.py`、
`events/dialog_lifecycle.py`、`presentation/event_overlay.py`、`runtime/frame_loop.py`，并复核
`widget.py`、`composition/lifecycles.py`、`main_window.py` 的相关调用段。`CODEBASE.md` 将在
接口定型并通过测试后覆盖更新，避免写入即将废弃的临时边界。

### A. 第二轮目标（实现前声明）

**目标文件：** 事件管理对话框与信号适配、手工测试控制器、导航生命周期组合、事件覆盖
模型/协调器，以及 Torchlight Portal/Loot 定义。

**本轮想弄清楚：** 哪些现有 Portal 命名只是通用会话控制，哪些确属业务 UI；Loot 中心
遮罩能否通过领域中立 overlay 契约由业务定义提供，从而让通用展示层只画图元而不读取
业务配置。

### B. 第二轮契约复核结果

- `(verified)` `ManualEventTestController` 本身仅同步按钮与 active 状态，没有 Portal
  语义；Portal 只存在于调用方命名、日志和文案，因此应整体重命名为通用手工事件会话。
- `(verified)` `EventManagerDialog` 的配置表单生成是 schema 驱动的，但紧凑字段集合和
  摘要字段集合仍写死 Torchlight Portal/Loot 参数；应由业务 definition 的 schema 元数据
  标注 `compact`/`summary`，对话框只解释通用显示元数据。
- `(verified)` 当前 core `EventOverlayModel` 只描述任务点位；Loot 玩家中心遮罩不是任务，
  不应伪装为 core 事件任务。更合适的边界是导航 UI 接受可注入的领域中立 overlay
  provider，Torchlight UI provider 把 Loot 配置转换为圆形图元描述。
- `(verified)` 事件管理 footer 同时存在 `reset_portal_requested` 和
  `reset_events_requested`，但“刷新事件状态”按钮实际只发后者；前者已是无效兼容信号，
  可在同一批次删除。

**覆盖进度更新：** 完整复核了事件对话框 dialog/layout、panel adapter、手工测试控制器、
core overlay/coordinator presentation，以及 Loot definition 的配置 schema 和公开工厂行为。

### A. 第三轮目标（修改前声明）

**目标文件：** `schema_form.py`、Portal/Loot definition、导航 display/command 生命周期、
Torchlight UI 组合入口和主窗口注入点，以及现有对话框/导航测试。

**本轮想弄清楚：** 保持现有 UI 行为与测试兼容所需的最小公开契约，并把所有业务词从
`ui/modes/navigation` 与通用事件对话框中清除后再实施原子修改。

### C. 第三轮实现结果

- `(verified)` `NavigationModeWidget` 现在通过构造参数接收 `game_window_finder`、
  `event_registry_factory` 和 `event_overlay_providers`；缺省值分别为无窗口、空 registry
  和无附加图元，独立使用时不再隐式选择任何游戏。
- `(verified)` Portal 专用手工测试命名已收敛为通用 `manual_event_test` 会话；事件对话框、
  生命周期、命令生命周期和帧循环均不再出现具体事件名。
- `(verified)` 事件 schema 新增通用 `compact`/`summary` 显示提示；具体字段集合由
  Torchlight Portal/Loot definition 声明，通用对话框不再维护业务参数白名单。
- `(verified)` 通用导航新增 `EventOverlayContext`/`EventCircleOverlay` 与 provider 注入点；
  Loot 中心遮罩解释已移动到 `ui/modes/torchlight/navigation.py`。
- `(verified)` Torchlight UI 组合对象集中提供事件 registry 工厂、游戏窗口查找器和 Loot
  overlay provider；`MainWindow` 只在应用组合根展开这些依赖。

**验证：** 受影响模块 `compileall` 通过；架构边界、导航 UI、紧凑操作、导航 intent 与
hook 聚焦测试 **20 passed**。对 `core`、通用 navigation UI 和通用 event manager 的
业务词扫描无输出。

**覆盖进度更新：** 新增并复核 `core/events/config_schema.py`、
`ui/modes/torchlight/navigation.py`；重读并更新事件对话框、导航事件/显示/命令/帧循环和
Portal/Loot definition 的相关算法与调用边界。

### A. 第四轮目标（收尾检查前声明）

**目标文件/范围：** 旧导入路径、旧缓存目录、所有 Torchlight/PoE2 feature 公共导出、
相关测试导入、当前权威架构文档和完整工作区 diff。

**本轮想弄清楚：** 是否还存在“源码已迁移但兼容入口/测试/文档仍把实验或旧 core 路径
当权威入口”的残留，并在不覆盖用户其他修改的前提下完成清理和文档同步。

### C. 第四轮收尾结果

- `(verified)` 生产源码、测试和工具中已无旧 Portal/Loot/Follow import 路径；PoE2 正式
  测试已从 `tools.experiments` 兼容导出切换到 `features.poe2.live_terrain`。
- `(verified)` `core.routing` 公开 `LaggedTrajectoryTarget`；Follow 业务与测试改用稳定包入口。
- `(verified)` 旧 `core/diagnostics`、`application/follow`、`core/events/types/portal|loot`、
  `ui/modes/follow` 和 `core/lan_follow` 源码/缓存目录已清理；回退标签
  `pre-reorg/2026-09-18` 保持不变。
- `(verified)` `CODEBASE.md` 已同步目录图、模块边界、函数算法和事件管理数据流；Portal
  feature 文档不再把旧 core 路径描述为当前实现，历史 `docs/architecture` 明确标为快照。
- `(verified)` CodeGraph 已重新同步到 812 files / 9,470 nodes / 24,670 edges，并确认
  `TorchlightNavigationComposition -> NavigationModeWidget -> EventOverlayContext` 调用面。

**最终验证：**

- Follow/架构聚焦：**41 passed**。
- PoE2 聚焦：**35 passed**。
- Portal/Loot/Event 聚焦：**24 passed**；较宽 Portal/Loot/Navigation 组合为 **40 passed**。
- `python -m compileall -q src tests tools packaging`：通过。
- 全量：**487 passed, 2 skipped, 4 failed, 10 subtests passed**。四个失败与已知基线一致：
  本机缺少 `pydirectinput` distribution metadata，以及 `PathFinder` 的 blocked-corner、
  unexplored-area、strict thin-wall 三个既有断言；本轮没有修改其实现。
- `git diff --check`：通过，仅显示工作区既有 LF/CRLF 规范化提示。

**安全边界：** 未启动游戏、Host 或 LAN；未发送鼠标、键盘、虚拟手柄或网络同步输入。

**Git 边界：** 已保留可用基线标签。当前同一工作区还有通信重构及用户 PoE2/配置改动，
并且 `ui/main_window.py` 等文件存在重叠；本轮没有把这些不同所有权的修改混入一个新提交。

## [SYNC] 2026-09-19 — 通信运行时 UI 装配与接收隔离

### A. SYNC 范围声明

**触发任务：** 完成通信层重构的 UI 注入、共享接收和生命周期验证。
**直接变更文件：** `ui/composition/services.py`、`ui/composition/__init__.py`、`ui/main_window.py`、`ui/modes/torchlight/follow/page.py`、`ui/modes/events/workbench.py`、相关通信适配与测试。
**预计连带影响：** FollowService/EventWorkbenchService 调用方、Host bridge/transport 接收路径、manager 的 capability lease 与 dispatcher、窗口关闭时的 Host 资源所有权。
