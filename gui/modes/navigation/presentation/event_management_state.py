from __future__ import annotations

from PySide6.QtWidgets import QMessageBox


def warn_event_config_missing(parent) -> None:
    QMessageBox.warning(parent, "事件管理", "未加载地图或事件配置。")


def show_event_config_saved(parent) -> None:
    QMessageBox.information(parent, "事件管理", "事件配置已保存。")


def show_event_config_save_failed(parent) -> None:
    QMessageBox.critical(parent, "事件管理", "保存 event_config.json 失败。")


def warn_event_system_missing(parent) -> None:
    QMessageBox.warning(parent, "事件管理", "请先加载地图并初始化事件系统。")


def show_portal_event_state_reset(status_label, removed: int) -> None:
    status_label.setText(f"传送门状态已刷新，清理 {removed} 个任务；可重新识别测试")


def show_event_state_reset(status_label, removed: int) -> None:
    status_label.setText(f"事件状态已刷新，清理 {removed} 个任务；可重新识别测试")


def warn_portal_manual_test_missing_screen_center(parent) -> None:
    QMessageBox.warning(parent, "事件管理", "请先校准屏幕中心。")


def show_portal_manual_test_started(status_label) -> None:
    status_label.setText("传送门测试已启动：使用正式事件流程执行")


def show_portal_manual_test_stopped(status_label) -> None:
    status_label.setText("传送门测试已停止")
