# Iteration Log

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
