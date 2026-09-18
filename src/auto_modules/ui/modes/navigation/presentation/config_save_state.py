from __future__ import annotations

from PySide6.QtWidgets import QMessageBox


def mark_nav_params_dirty(status_label) -> None:
    status_label.setText("有未保存的修改")


def warn_nav_config_missing_map(parent) -> None:
    QMessageBox.warning(parent, "错误", "没有加载地图，无法保存参数。")


def show_nav_config_saved(parent, status_label) -> None:
    status_label.setText("参数已保存并应用")
    QMessageBox.information(parent, "成功", "参数已保存并成功应用到当前导航。")


def show_nav_config_save_failed(parent, status_label, error: Exception) -> None:
    QMessageBox.critical(parent, "保存失败", f"无法写入 config.json: {error}")
    status_label.setText("保存失败!")


def warn_default_nav_config_missing(parent) -> None:
    QMessageBox.warning(parent, "错误", "没有可保存的导航参数。")


def show_default_nav_config_saved(parent, status_label, path) -> None:
    status_label.setText("已保存为默认配置")
    QMessageBox.information(parent, "成功", f"默认导航配置已保存到：{path}")


def show_default_nav_config_save_failed(parent, status_label, error: Exception) -> None:
    QMessageBox.critical(parent, "保存失败", f"无法写入默认 config.json: {error}")
    status_label.setText("默认配置保存失败!")
