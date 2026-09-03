# GUI Dialogs 架构

## 系统角色

`gui/dialogs` 拥有交互式配置和诊断 UI。Dialogs 应把用户输入适配到 typed configuration objects 或 command requests，不应拥有 core algorithms。

## 当前大文件

| 文件 | 行数 | 重构关注点 |
| --- | ---: | --- |
| `nav_params_dialog.py` | 约 141 | 参数面板 shell：窗口、信号、NavConfig 更新、屏幕半径估算和配置写回。 |
| `nav_params/layout_helpers.py` | 约 30 | 参数面板滚动 tab 创建和小窗/完整尺寸策略。 |
| `nav_params/sections.py` | 约 380 | 参数面板六个 tab/section 的 widget 创建、说明文案、tooltip 和 footer action bar。 |
| `advanced_settings_dialog.py` | 约 107 | 高级参数 dialog shell：参数应用、保存/加载、预设调用和兼容 direct apply。 |
| `advanced_settings/tabs.py` | 约 400 | 高级参数四个滚动 tab、控件创建、说明文案和 footer action bar。 |
| `color_picker_dialog.py` | 约 245 | 颜色选择 dialog shell：截图预处理、点击采样、HSV 计算、预览刷新和结果返回。 |
| `color_picker/layout.py` | 约 110 | 颜色选择 UI 组合：说明、模式按钮、原图/预览区域、结果区和 footer。 |
| `event_manager_dialog.py` | 约 3 | 旧导入兼容壳，真实实现已迁入 `event_manager/dialog.py`。 |
| `event_manager/dialog.py` | 约 336 | 事件管理弹窗 shell：上下文、刷新、信号、schema 数据绑定和小窗/完整模式切换。 |
| `event_manager/layout.py` | 约 190 | 事件管理 UI 组合：公共 header、compact page、full tabs、footer actions。 |
| `event_manager/schema_form.py` | 约 126 | schema field 到 Qt 控件的工厂、清空、双视图同步。 |
| `event_manager/task_table.py` | 约 65 | 完整/小窗事件任务表头和行渲染。 |

## 目标 Dialog 拆分

### Navigation Parameters

```text
nav_params_dialog.py             # dialog shell, tabs, save/apply signals
nav_params/field_specs.py        # field metadata: label, help, range, type, config path
nav_params/widget_factory.py     # QSpinBox/QDoubleSpinBox/QCheckBox/QLineEdit creation from specs
nav_params/config_binding.py     # NavConfig <-> widgets, immutable dataclass replace
nav_params/screen_estimator.py   # click radius estimates from calibrated center and screen bounds
nav_params/layout_helpers.py     # scrollable tabs and compact/full dialog sizing
nav_params/sections.py           # six tab/section builders and action bar
```

已验证当前行为：

- `NavParametersDialog._init_ui()` 只创建 `QTabWidget`、调用 `nav_params/sections.py::build_navigation_parameter_tabs()`，再挂载 `build_action_bar()`。
- `nav_params/sections.py` 构建六个 tabs：positioning、recognition、movement、path、event、map/debug；每个 tab 通过 `nav_params/layout_helpers.py::create_scrollable_tab()` 包进 `QScrollArea`，允许参数面板缩小后滚动查看。
- `NavParametersDialog` 默认小窗尺寸约 `520x640`，底部 `完整模式/小窗模式` 按钮只切换对话框尺寸策略，不改变配置值或参数分组。
- `_connect_signals()` 通过 `nav_params/config_binding.py` 连接 `field_specs.py` 中的 widget attr 到 `(sub_config_name, attr_name)`，不再在 dialog 内维护大型 widget map。
- `_update_config_value()` 用 `dataclasses.replace()` 更新 `NavConfig` 或嵌套 dataclasses，并 emit `parameters_changed`。
- `_update_config_text_value()` 用 `ast.literal_eval()` 解析 HSV list text；输入不完整/非法时不 emit。
- `set_config_to_ui()` 用 `QSignalBlocker` 阻塞 child widget signals，同时把 `NavConfig` 写回 widgets。
- `_auto_estimate_click_radius()` 保留 Qt screen-bound 查询，并把半径数学委托给 `nav_params/screen_estimator.py`。
- 旧 `NavPreferences.k_ratio/y_bias` 仍通过 config 序列化往返，但当前 motion mapping 不使用它们，因此不再在 dialog 中可见或可编辑。

提取顺序：

1. 已完成：`screen_estimator.estimate_click_radii(center, screen_bounds)` 现在是纯半径策略。Qt screen enumeration 留在 dialog adapter，把 physical bounds 传给 helper 以便测试。
2. 已完成：围绕现有 widget attrs 抽 `field_specs.py` 和 `config_binding.py`。初期保留精确 widget names，避免 layout churn。
3. 已完成：`layout_helpers.py` 抽出可滚动 tab 和小窗/完整尺寸策略，解决参数内容撑大对话框的问题。
4. 已完成：widget 创建迁入 `sections.py`，按 positioning、recognition、movement、path、event、map/debug 拆成 section builders。
5. 下一步：如果继续细化，可把 `sections.py` 再拆成 `sections/positioning.py`、`sections/movement.py` 等包级模块，或引入真正的 widget factory 消除重复的 range/step 设置。

目标交互：

```text
NavParametersDialog
  ├─ field_specs grouped by section
  ├─ WidgetBinder writes NavConfig -> widgets
  ├─ WidgetBinder reads widget changes -> NavConfig
  ├─ Section builders create tabs/widgets and keep widget attr names stable
  ├─ Scrollable tab factory allows small-window testing
  ├─ ScreenClickEstimator returns suggested radii
  └─ emits parameters_changed/save_requested/save_default_requested
```

### Advanced Settings

现有 helper：

```text
advanced_settings_dialog.py      # shell and buttons
advanced_settings/params_adapter.py
advanced_settings/file_io.py     # JSON load/save target directory and errors
advanced_settings/presets.py     # preset names and widget-value data
advanced_settings/tabs.py        # scrollable tab and action construction
```

已验证当前行为：

- dialog 使用普通 `dict`，不是 `NavConfig` / `RecognizerParams`。
- 它保留兼容 direct apply：如果没有调用 `use_external_apply_handler()`，仍会尝试直接 reach into `parent.recognizer` 和 `parent.stitcher`，调用 `set_params()`。
- `advanced_settings/tabs.py` 构建图像预处理、特征提取、参数管理、拼接算法四个 tab；每个 tab 包进 `QScrollArea`，小窗口时可滚动。
- `AdvancedSettingsDialog.setup_ui()` 现在只委托 `build_advanced_settings_ui(self)`。
- `save_current_params()` 委托 `advanced_settings/file_io.py`，写入 `configs/advanced_settings/params_<safe_name>_<timestamp>.json`。
- `load_params_from_file()` 默认从 `configs/advanced_settings/` 打开，校验 JSON 顶层对象和 `parameters` 对象字段，并保存到 `temp_loaded_params`。
- `params_adapter.py` 集中 widget 读写，并把 preset 数据应用到控件；它仍是浅 adapter，因为依赖 dialog attribute names。
- `file_io.py` 集中 filename sanitization、目录创建、JSON payload shape、读取校验和展示格式化。
- `presets.py` 集中 preset 选项顺序和 widget-value 字典，可在不构造 GUI dialog 的情况下测试。

重构建议：

- 视为 legacy tuning surface。不要把新的 navigation/event settings 扩展进去。
- 如果继续演进，应逐步让调用方使用 `apply_params_requested`，最后关闭 direct parent mutation。
- 保持 JSON file IO 只在 `advanced_settings/file_io.py` 内，不再引入当前工作目录写入。
- 继续降低 `params_adapter.py` 对 dialog attribute 的耦合；preset 值已经改成纯数据。

### Color Picker

已有 helper：

- `color_picker/hsv_ranges.py`
- `color_picker/image_renderer.py`
- `color_picker/layout.py`

当前结构：

```text
color_picker_dialog.py          # shell and interactions
color_picker/layout.py           # UI construction
color_picker/preview.py          # mask/preview stats construction
color_picker/debug_output.py     # png/txt output
```

已验证当前行为：

- `ColorPickerDialog` 构造 `HSVRecognizer`，应用可选 recognizer params，预处理 screenshot，并保存 original/sample state。
- `ColorPickerDialog.setup_ui()` 现在只委托 `color_picker/layout.py::build_color_picker_ui(self)`，控件属性名保持不变。
- `hsv_ranges.py` 是纯 HSV math：BGR->HSV、point sampling、tolerance-based range calculation、mean saturation。
- `image_renderer.py` 是 Qt rendering adapter：OpenCV image -> pixmap、固定大小 sample markers。
- `layout.py` 构建模式按钮、缩放滑块、`ClickableImageLabel`、预览 QLabel、结果 QTextEdit 和确定/取消按钮。
- `calculate_hsv_ranges()` 采样 wall/player points；如果 wall saturation 高，则建议关闭 saturation filtering。
- `update_preview()` 仍结合 HSV mask generation、morphology、preview rendering；debug artifact 写入通过 `MINIMAP_COLOR_PICKER_DEBUG` 显式开启。

重构建议：

- 已完成：`build_wall_preview(image, hsv_range)` 返回 mask 和 stats。
- 保持 `write_wall_preview_debug(...)` 路径可控且 opt-in；不要重新引入无条件 preview artifact 写入。
- `ColorPickerDialog` 只保留 interaction state 和 result packaging：selected points、current mode、zoom、accepted ranges。

当前 artifact 状态：

- `preview_result_*.png`、`preview_before_morph_*.png`、`preview_log_*.txt` 只有启用 `MINIMAP_COLOR_PICKER_DEBUG` 时，才通过 `color_picker/debug_output.py` 写入 `debug/color_picker/`。

### Event Manager

已验证当前行为：

- `EventManagerDialog` 已迁入 `gui/dialogs/event_manager/dialog.py`，旧 `event_manager_dialog.py` 只保留导入壳。
- `build_tui_event_options(registry, config)` 提供 event rows、display names、descriptions、current values、editable parameter schema。
- `event_manager/schema_form.py` 把 schema types 映射到 Qt controls：float、int、bool、choice、str、read-only label fallback。
- `event_manager/layout.py` 负责搭建公共 header、compact page、full tabs 和 footer；dialog class 不再直接堆完整布局代码。
- 小窗模式默认启用，尺寸约 `480x620`；完整模式保留事件参数、触发状态、Hooks 三个 tabs，尺寸约 `1040x780`。
- 小窗模式保留事件下拉、当前事件启用、常用参数、简化任务表、保存/刷新/测试传送门/刷新传送门状态按钮。
- 它为 save、test portal、reset portal emit command-style signals。
- 它从 `coordinator.tasks()` 读取 live task rows，显示 event task state、confidence、map coordinate、attempts、last-seen timestamp。

当前约束：

- `dialog.test_portal_button` 必须继续存在，`ManualEventTestController` 依赖这个稳定属性同步按钮状态。
- 完整参数表和小窗常用参数表会渲染重复控件；`sync_param_widget_maps()` 负责同一字段在两个视图之间同步显示值。
- 统一 config mutation style。`EventManagerDialog` 原地修改 `config`，`NavParametersDialog` emit replaced dataclass。typed dataclasses 优先 immutable updates；mutable dict-backed config 可原地更新。

## Dialog-to-System 交互规则

- Dialogs 应 emit typed signals 或 command signals。
- Dialogs 不应直接调用 `recognizer.set_params()`、`stitcher.set_params()`、movement methods 或 event handlers。
- Dialogs 可以从 read-only query methods 渲染 live state，例如 `coordinator.tasks()`。
- Dialog field definitions 可放在 dialog package 附近，但 domain validation 应放在 `NavConfig`、event config schemas 或 core parameter dataclasses。

## 最高价值拆分顺序

1. `color_picker_dialog.py`：已完成 layout、preview mask/stats 和可选 debug output 拆分；后续只在预览交互继续扩展时再拆。
2. `advanced_settings_dialog.py`：UI tabs 已拆；如果继续使用，下一步是停止 direct parent mutation。
3. `nav_params_dialog.py`：已完成 shell、binding、section builders；后续只在需要时继续拆 `sections.py`。
4. `EventManagerDialog`：已完成小窗/完整模式拆分；后续只在其它 dialog 也需要 schema form 时，再上提为通用表单组件。

## 当前状态

状态：partial。`EventManagerDialog` 已模块化并加入小窗模式；`NavParametersDialog` 已拆出 binding、field specs、screen estimator、滚动/小窗 layout helper 和 section builders；`advanced_settings_dialog.py` 已拆出滚动 tabs 和 action bar；`color_picker_dialog.py` 已拆出 layout、preview、image renderer、HSV math 和 debug output helper。
