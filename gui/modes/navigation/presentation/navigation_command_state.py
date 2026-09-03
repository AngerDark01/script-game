from __future__ import annotations

from PySide6.QtWidgets import QMessageBox


def warn_auto_navigation_unavailable(parent, message: str) -> None:
    QMessageBox.warning(parent, "警告", message)


def warn_auto_navigation_invalid_route(parent) -> None:
    QMessageBox.warning(parent, "警告", "路线数据无效，无法启动自动导航")


def show_auto_navigation_started(status_label) -> None:
    status_label.setText("自动导航已启动，等待稳定定位")


def show_auto_navigation_stopped(status_label) -> None:
    status_label.setText("自动导航已停止")


def warn_navigation_missing_screen_center(parent) -> None:
    QMessageBox.warning(parent, "警告", "请先点击'校准屏幕中心'进行设置！")


def warn_navigation_map_config_incomplete(parent) -> None:
    QMessageBox.warning(parent, "警告", "地图配置不完整，缺少监控中心或大小！")


def show_navigation_started(status_label) -> None:
    status_label.setText("导航已开始...")


def show_navigation_paused(status_label) -> None:
    status_label.setText("导航暂停")
