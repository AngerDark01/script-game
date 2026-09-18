from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtWidgets import QMessageBox


def populate_map_combo(combo, map_names: Iterable[str], missing_label: str) -> None:
    combo.clear()
    names = list(map_names)
    if names:
        combo.addItems(names)
    else:
        combo.addItem(missing_label)


def apply_map_loaded_ui(
    *,
    start_button,
    hint_button,
    route_panel,
    status_label,
    map_name: str,
) -> None:
    start_button.setEnabled(True)
    hint_button.setEnabled(True)
    route_panel.set_buttons_enabled(True)
    status_label.setText(f"地图 '{map_name}' 加载成功。请设置初始位置或直接开始导航。")


def warn_map_config_missing(parent) -> None:
    QMessageBox.warning(parent, "警告", "未找到 config.json，将使用默认参数。")


def show_map_load_failed(parent, error: Exception) -> None:
    QMessageBox.critical(parent, "错误", f"加载地图失败：{str(error)}")


def warn_overlay_map_config_incomplete(parent) -> None:
    QMessageBox.warning(parent, "警告", "地图配置不完整，无法显示幕布。")
