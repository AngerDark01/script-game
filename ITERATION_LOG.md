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
