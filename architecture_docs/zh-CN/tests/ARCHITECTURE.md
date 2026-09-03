# 测试架构

## 系统角色

`tests` 应定义保护重构的行为契约。每个大文件拆分前，都应围绕待抽接口增加测试，然后再改源码。

## 现有测试区域

| 测试文件 | 覆盖区域 | 重构用途 |
| --- | --- | --- |
| `test_motion_controller.py` | 点击半径、bottom guard、execution options。 | 保护 input-system split。 |
| `test_advanced_settings_file_io.py` | 高级设置 JSON snapshot 保存/加载 helper。 | 保护 dialog file-IO 拆分和显式输出目录。 |
| `test_advanced_settings_presets.py` | 高级设置 preset 名称/数据和 adapter 应用。 | 保护 data-only preset 抽取。 |
| `test_navigation_params_compat.py` | 旧导航偏好字段配置往返。 | 保护隐藏旧 UI 字段同时保留配置兼容。 |
| `test_nav_params_screen_estimator.py` | 导航点击半径估算策略。 | 保护半径数学留在 Qt dialog 之外。 |
| `test_color_picker_debug_output.py` | 颜色选择器预览 debug artifact opt-in 开关。 | 保护旧 debug 输出清理。 |
| `test_navigation_core.py` | 定位 tracking 行为。 | 保护 localization split。 |
| `test_path_utils.py` | 几何工具。 | 保护 route utility extraction。 |
| `test_pathfinder.py` | A* movement 和 obstacle 行为。 | 保护 pathfinder/obstacle split。 |
| `test_phase_displacement.py` | 共享 phase-correlation 位移估计 helper。 | 保护建图/定位 displacement 抽取。 |
| `test_recognizer_optimized.py` | 识别过滤行为。 | 保护 recognizer pipeline split。 |
| `test_route_manager.py` | Route persistence 和 mutation。 | 保护 route repository split。 |
| `test_stitcher_core.py` | Visibility/merge 行为。 | 保护 stitching split。 |

## 已验证契约

### `test_advanced_settings_file_io.py`

保护行为：

- 保存 snapshot 时使用显式调用方目录，并清洗参数名里的文件名非法字符。
- JSON payload 保留原始展示名、ISO timestamp 和 `parameters` 对象。
- 加载时拒绝 `parameters` 不是 JSON object 的文件。
- 展示格式化保留非 ASCII 文本。

重构安全性：

- 保护 `gui.dialogs.advanced_settings.file_io`，但不导入完整 GUI package，避免测试时触发无关的 `MainWindow` / input 依赖。
- 足够保持 JSON file IO 在 `AdvancedSettingsDialog` 外；tab 拆分仍需要单独测试。

### `test_advanced_settings_presets.py`

保护行为：

- preset 选项名保持 combo box 现有用户可见顺序。
- preset value 字典保留每个非默认预设的旧控件值。
- `apply_preset_to_widgets()` 会按数据表应用 preset，默认 preset 仍委托完整 reset，未知名称仍返回 `False`。

重构安全性：

- 不构造 Qt dialog 即可保护 `advanced_settings/presets.py` 和 adapter 路径。
- 足够把 preset 定义留在 `AdvancedSettingsDialog` 外；剩余风险仍是基于 dialog attribute 的 widget adapter。

### `test_motion_controller.py`

保护行为：

- 短 map delta 使用 `movement_min_click_radius`。
- 长 map delta clamp 到 `movement_max_click_radius`。
- zero map delta 不返回 click target。
- `_execute_click()` 默认保留 out-of-screen requested coordinates，除非显式开启 `clamp_to_screen`。
- `_execute_click()` 记录 target window、foreground/cursor diagnostics、requested/final screen position、backend movement status。
- optional focus-before-click 会调用 fake driver。
- bottom click guard 会把向下点击缩短到屏幕底部 UI 区域之前。

重构安全性：

- 足够开始抽 movement mapping 和 click policy。
- 改 `press_key()` 或增加 input hook bus 前，要先补 key-command 和 hook-emission 测试。

### `test_navigation_params_compat.py`

保护行为：

- 旧 `nav_preferences.k_ratio/y_bias` 值仍可通过 `NavConfig.from_dict()` 加载。
- `NavConfig.to_dict()` 仍会原样写回这些字段。

重构安全性：

- 保护从 `NavParametersDialog` 移除无效 `k_ratio/y_bias` 控件时，旧 `config.json` 仍保持兼容。

### `test_nav_params_screen_estimator.py`

保护行为：

- 普通屏幕边界产生和旧 dialog 数学一致的 min/max click radii。
- 小屏幕会 clamp 到旧最小值。
- 大屏幕会把 max radius clamp 到 900。
- 中心点越界时返回 `None`。

重构安全性：

- 不导入完整 GUI package 即可保护 `gui.dialogs.nav_params.screen_estimator`。
- 足够保持 `_auto_estimate_click_radius()` 为 Qt adapter，并继续独立抽 `NavParametersDialog` binding。

### `test_color_picker_debug_output.py`

保护行为：

- 环境变量缺失时，颜色选择器预览 debug 输出默认关闭。
- `MINIMAP_COLOR_PICKER_DEBUG` 接受显式 truthy 值：`1`、`true`、`yes`、`on`。
- 非 truthy 值不会开启 artifact 写入。

重构安全性：

- 保护旧 debug 清理，避免 preview rendering 重新无条件写 png/txt。
- 不测试 OpenCV 文件写入；需要诊断时仍可通过生产 helper 路径手动验证。

### `test_pathfinder.py`

保护行为：

- A* 不能通过 blocked corner 斜穿。
- Wall shrinking 可以让 false thin wall 不再阻塞路线。
- 提供 `explored_map` 时，未知/未探索 cells 不可走。

重构安全性：

- 足够把 `pathfinder.py` 和 `navigation_obstacles.py` 移到 `core/routing/`，前提是机械更新 imports。

### `test_path_utils.py`

保护行为：

- Collinear path cleanup 保留 turns。
- Exit-region radius check 是圆形。
- Path projection/interpolation 正确使用 cumulative distance。
- Smoothing 会 shortcut 完全可见 straight segment。

重构安全性：

- 足够把 path geometry 移到 `core/routing/geometry.py`。
- 仍缺 `line_is_walkable()` 越界行为和 blocked Bresenham segments 的直接测试。

### `test_navigation_core.py`

保护行为：

- F2F tracking 使用 `wall_mask` 而不是 `match_mask` 来估计 displacement。
- 成功 F2F 会按 negative displacement 更新 global position，并返回 confidence。

重构安全性：

- 对 localization matching 是有用窄回归测试。
- 不足以整体拆 `NavigationCore`；还需 map package loading、forced global relocalization、local/global template-match thresholds、visual consistency rejection 测试。

### `test_phase_displacement.py`

保护行为：

- Identical images 会通过 dead-zone filter 归一为 zero shift。
- Invalid inputs 返回 `(None, 0.0)`，保留旧 `_estimate_displacement()` 失败契约。

重构安全性：

- 保护 `MapStitcher` 和 `NavigationCore` 现在共同使用的 `core.phase_displacement.estimate_phase_displacement()`。

### `test_stitcher_core.py`

保护行为：

- `_merge_frame_weighted()` 使用 fog/visibility mask shape，而不是总是把 full rectangle 标记为 explored。
- 很小的 fog mask fallback 到 full-rect visibility 行为。

重构安全性：

- 可作为抽 `WeightedMapMerger` 的第一道护栏。
- 拆 `add_frame()` 前，还应补 first-frame placement、keyframe vs previous-frame fallback、displacement rejection、package save/load 测试。

### `test_recognizer_optimized.py`

保护行为：

- Transparent mode 下，饱和动态 icon pixels 会从 match features 中移除，同时 wall pixels 保留。

重构安全性：

- 对抽 dynamic filtering 有用。
- 拆 recognizer pipeline 前，应补 preprocessing parameters、wall/fog/player mask extraction、player clear radius、combined weights 测试。

### `test_route_manager.py`

保护行为：

- route 文件缺失时返回 empty default main route。
- exit region、required points、guide points 可以 save/load round-trip。
- undo required point 只影响 required points。

重构安全性：

- 足够抽 route repository logic。
- route format 扩展时应补 schema migration/default tests。

## 需要新增的测试

拆大文件前先补：

- `NavigationModeWidget` orchestration 行为，尽量通过较小非 GUI functions 测。
- `NavigationTaskController` intent conversion 和 event bridge 行为。
- `EventCoordinator` lifecycle，用 fake detector/handler adapters。
- Portal handler state transitions，用 fake ticks 和 fake captures。
- Navigation 和 event settings 的 config round trips。
- `anchor_path.py` ordered-anchor filtering、reached-anchor skipping、direct fallback、probe fallback。
- `MappingSession.tick()` capture/recognize/stitch 行为，用 fake capture/recognizer/stitcher adapters。
- 如果保留 map click navigation，测 `ScalableMapWidget` click-coordinate mapping。
- 通过非 widget `field_specs` 层测 `NavParametersDialog` config binding。

## 当前状态

状态：partial。所有当前 test files 已阅读。测试套件保护了一些底层算法，但尚未保护 event lifecycle、portal handler state、mapping session orchestration 或 navigation GUI extraction。
