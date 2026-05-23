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
