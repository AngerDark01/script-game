from __future__ import annotations

from PySide6.QtWidgets import QLabel


def build_status_label(owner) -> QLabel:
    """Create the one-line navigation status label."""
    owner.status_label = QLabel("请选择并加载地图")
    owner.status_label.setWordWrap(False)
    return owner.status_label
