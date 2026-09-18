from __future__ import annotations

from PySide6.QtWidgets import QMessageBox


def show_route_command_status(status_label, status_text: str | None) -> None:
    if status_text:
        status_label.setText(status_text)


def warn_route_save_failed(parent) -> None:
    QMessageBox.warning(parent, "警告", "保存路线失败")


def warn_move_target_requires_localization(parent) -> None:
    QMessageBox.warning(parent, "警告", "请先完成定位后再点击移动目标。")


def show_move_target_set(status_label, pos) -> None:
    status_label.setText(f"移动目标: ({pos.x():.1f}, {pos.y():.1f})")
