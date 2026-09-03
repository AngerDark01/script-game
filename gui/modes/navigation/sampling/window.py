from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)


class MinimapSampleCaptureWindow(QDialog):
    """Small floating window for collecting raw minimap detector samples."""

    save_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("小地图样本采集")
        self.setWindowFlags(self.windowFlags() | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setMinimumWidth(360)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self.map_label = QLabel("地图：未加载")
        layout.addWidget(self.map_label)

        self.status_label = QLabel("等待保存")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        button_row = QHBoxLayout()
        self.save_button = QPushButton("保存当前小地图")
        self.save_button.clicked.connect(self.save_requested.emit)
        button_row.addWidget(self.save_button, 1)

        self.topmost_check = QCheckBox("置顶")
        self.topmost_check.setChecked(True)
        self.topmost_check.toggled.connect(self._set_topmost)
        button_row.addWidget(self.topmost_check)
        layout.addLayout(button_row)

        self.close_button = QPushButton("关闭")
        self.close_button.clicked.connect(self.hide)
        layout.addWidget(self.close_button)

        self.set_ready(False, "")

    def set_ready(self, ready: bool, map_name: str) -> None:
        self.save_button.setEnabled(bool(ready))
        self.map_label.setText(f"地图：{map_name}" if map_name else "地图：未加载")
        if not ready:
            self.status_label.setText("请先在导航页加载地图")

    def show_result(self, result) -> None:
        if result is None:
            return
        if result.ok:
            self.status_label.setText(f"已保存：{_short_path(result.image_path)}")
            return
        self.status_label.setText(f"保存失败：{result.message}")

    def _set_topmost(self, enabled: bool) -> None:
        visible = self.isVisible()
        flags = self.windowFlags() | Qt.Tool
        if enabled:
            flags |= Qt.WindowStaysOnTopHint
        else:
            flags &= ~Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        if visible:
            self.show()
            if enabled:
                self.raise_()


def _short_path(path: str) -> str:
    if not path:
        return ""
    file_path = Path(path)
    parent = file_path.parent.name
    if parent:
        return f"{parent}\\{file_path.name}"
    return file_path.name
