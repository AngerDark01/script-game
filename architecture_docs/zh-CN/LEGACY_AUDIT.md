# 旧内容审计记录

本文件只记录“疑似旧内容/历史包袱”的引用状态和处理建议。当前轮次不删除不确定内容。

## 已审计项目

| 项目 | 引用状态 | 判断 | 建议 |
| --- | --- | --- | --- |
| `gui/widgets_fixed.py` | 严格引用审计只发现文档和自身引用，源码入口使用 `gui/widgets/*.py`。 | 已确认是旧合并备份/修复版文件，且与当前拆分版本行为不同。 | 已删除，避免后续误导维护者或被误导入。 |
| `AdvancedSettingsDialog` | `gui/modes/mapping_widget.py` 仍导入并通过“高级参数调节”按钮打开。 | 仍是活动入口，不能删。 | 暂时保留；后续可以标 legacy，并逐步改成 command signal，不直接修改 parent recognizer/stitcher。 |
| `NavPreferences.k_ratio/y_bias` | 只保留在 `navigation_params.py` 的兼容读写中。 | 兼容旧配置字段，目前不参与主要 motion 映射。 | 已从 `nav_params_dialog.py` 可见 UI 和信号绑定中移除；保留 `config.json` 读写兼容，并补 `tests/test_navigation_params_compat.py`。 |
| `ColorPickerDialog.update_preview()` preview debug 输出 | 已优化。 | 原先会写 `preview_result_*.png`、`preview_before_morph_*.png`、`preview_log_*.txt` 到进程当前目录，后来移到 `debug/color_picker/` 但仍可能每次 preview 落盘。 | 已抽为 `color_picker/debug_output.py`，默认不落盘；仅 `MINIMAP_COLOR_PICKER_DEBUG=1` 时输出到 `debug/color_picker/`。 |
| `AdvancedSettingsDialog.save_current_params()` 当前目录参数输出 | 已优化。 | 原先把 `params_<name>_<timestamp>.json` 写到进程当前目录，容易污染运行目录且难以复用测试。 | 已抽为 `advanced_settings/file_io.py`，默认输出到 `configs/advanced_settings/`，并补 `tests/test_advanced_settings_file_io.py`。 |
| `AdvancedSettingsDialog` presets if/else | 已优化。 | 原先预设名称和控件赋值直接写在 `params_adapter.apply_preset_to_widgets()` 的多段 if/else 中。 | 已抽为 `advanced_settings/presets.py` 数据表，并补 `tests/test_advanced_settings_presets.py`。 |

## 本轮已完成优化

- 新增 `gui/dialogs/color_picker/debug_output.py`。
- `ColorPickerDialog.update_preview()` 不再直接写当前工作目录。
- Debug 文件仍保留，路径为显式 `debug/color_picker/`，并通过 `MINIMAP_COLOR_PICKER_DEBUG` opt-in 开启。
- 新增 `tests/test_color_picker_debug_output.py`，覆盖 preview debug 输出默认关闭、truthy 开启和非 truthy 拒绝。
- 新增 `gui/dialogs/advanced_settings/file_io.py`。
- `AdvancedSettingsDialog.save_current_params()` / `load_params_from_file()` 不再直接处理 JSON 文件读写，参数文件默认落到 `configs/advanced_settings/`。
- 新增 `tests/test_advanced_settings_file_io.py`，覆盖显式目录、文件名清洗、JSON payload 和加载校验。
- 删除 `gui/widgets_fixed.py`。严格审计确认运行时代码使用 `gui/widgets/clickable_label.py`、`gui/widgets/scalable_map.py`、`gui/widgets/collapsible_group.py`，旧合并文件无源码 import。
- 新增 `gui/dialogs/advanced_settings/presets.py`。
- `AdvancedSettingsDialog` 的 preset 下拉选项和非默认预设值改由数据表提供；`params_adapter.py` 只负责把数据写入控件。
- 新增 `tests/test_advanced_settings_presets.py`，覆盖 preset 顺序、旧控件值、默认 reset 和未知 preset 返回值。
- 从导航参数面板移除 `k_ratio/y_bias` 兼容旧控件和绑定；`NavPreferences` 数据模型保留，旧配置仍可读写。
- 新增 `tests/test_navigation_params_compat.py`，覆盖旧 `nav_preferences` 字段 round-trip。

## 后续低风险清理建议

1. 给 `AdvancedSettingsDialog` 加 legacy 注释和文档说明，但先不删入口。
2. 继续拆 `AdvancedSettingsDialog` 的 tabs；下一步优先把 tab 构建或 widget spec 数据化，减少 dialog 主类体积。
3. 后续如果要彻底删除 `NavPreferences.k_ratio/y_bias`，需先提供 config migration；当前只隐藏 UI，不破坏旧配置。
