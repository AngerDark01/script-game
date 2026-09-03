from __future__ import annotations

from PySide6.QtWidgets import QMessageBox


def show_initial_hint_set(status_label, global_x: float, global_y: float) -> None:
    status_label.setText(f"初始位置提示已设置：({int(global_x)}, {int(global_y)})。")


def show_hint_mode_status(status_label, active: bool) -> None:
    status_label.setText("请在地图上点击您当前的大致位置..." if active else "取消设置初始位置")


def show_screen_center_calibrated(parent, screen_center) -> None:
    QMessageBox.information(parent, "校准完成", f"屏幕中心已校准为：{screen_center}")
