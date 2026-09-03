from __future__ import annotations

from PySide6.QtCore import QTimer


class NavigationCompactUiController:
    """Own presentation-only compact/full layout switching for navigation mode."""

    def __init__(self, owner, *, route_tools_bar) -> None:
        self.owner = owner
        self.route_tools_bar = route_tools_bar
        self.compact = True

    def set_compact_mode(self, compact: bool) -> None:
        self.compact = bool(compact)
        self.owner.compact_mode_button.setText("完整布局" if self.compact else "小窗布局")
        self.owner.route_tools_button.setVisible(self.compact)

        if self.compact:
            self.owner.view.setMinimumHeight(220)
            self.owner.view.setMaximumHeight(380)
            self.route_tools_bar.setVisible(self.owner.route_tools_button.isChecked())
            self._refit_map_after_layout_change()
            return

        self.owner.view.setMinimumHeight(320)
        self.owner.view.setMaximumHeight(16777215)
        self.route_tools_bar.setVisible(True)
        self._refit_map_after_layout_change()

    def toggle_compact_mode(self) -> None:
        self.set_compact_mode(not self.compact)

    def toggle_route_tools(self) -> None:
        if not self.compact:
            self.route_tools_bar.setVisible(True)
            return
        self.route_tools_bar.setVisible(self.owner.route_tools_button.isChecked())
        self._refit_map_after_layout_change()

    def _refit_map_after_layout_change(self) -> None:
        if hasattr(self.owner.view, "fit_map"):
            QTimer.singleShot(0, self.owner.view.fit_map)
