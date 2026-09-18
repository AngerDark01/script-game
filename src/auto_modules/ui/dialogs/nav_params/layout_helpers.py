from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QScrollArea, QVBoxLayout, QWidget


def create_scrollable_tab() -> tuple[QWidget, QVBoxLayout]:
    """Create a tab page whose content can shrink behind scroll bars."""
    tab = QWidget()
    outer_layout = QVBoxLayout(tab)
    outer_layout.setContentsMargins(0, 0, 0, 0)

    scroll_area = QScrollArea()
    scroll_area.setWidgetResizable(True)
    scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

    content = QWidget()
    content_layout = QVBoxLayout(content)
    content_layout.setContentsMargins(8, 8, 8, 8)
    content_layout.setSpacing(8)
    scroll_area.setWidget(content)

    outer_layout.addWidget(scroll_area)
    return tab, content_layout


def apply_nav_params_window_mode(dialog, compact: bool, *, resize_window: bool = True) -> None:
    """Apply presentation-only compact/full sizing for the navigation parameter dialog."""
    dialog.nav_compact_mode_btn.setText("完整模式" if compact else "小窗模式")
    if compact:
        dialog.setMinimumSize(420, 360)
        if resize_window:
            dialog.resize(520, 640)
        return

    dialog.setMinimumSize(760, 560)
    if resize_window:
        dialog.resize(980, 760)
