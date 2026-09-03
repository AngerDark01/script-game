from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from PySide6.QtWidgets import QApplication

from .window import MinimapSampleCaptureWindow


@dataclass(frozen=True)
class NavigationSampleCaptureLifecycleTargets:
    parent: object
    main_window: object
    status_label: object
    get_map_name: Callable[[], str]
    is_ready: Callable[[], bool]
    capture_sample: Callable[[], object]


class NavigationSampleCaptureLifecycle:
    """Own the floating sample capture window and non-modal save feedback."""

    def __init__(self, targets: NavigationSampleCaptureLifecycleTargets) -> None:
        self.targets = targets
        self.window: MinimapSampleCaptureWindow | None = None

    def ensure_window(self) -> MinimapSampleCaptureWindow:
        if self.window is not None:
            return self.window
        parent = self.targets.main_window or self.targets.parent
        self.window = MinimapSampleCaptureWindow(parent)
        self.window.save_requested.connect(self.save_sample)
        self.update_ready_state()
        return self.window

    def toggle_window(self) -> None:
        window = self.ensure_window()
        self.update_ready_state()
        if window.isVisible() and window.isActiveWindow():
            window.hide()
            return
        if not window.isVisible():
            self._move_to_default_corner(window)
        window.show()
        window.raise_()

    def update_ready_state(self) -> None:
        if self.window is None:
            return
        self.window.set_ready(self.targets.is_ready(), self.targets.get_map_name())

    def show_result(self, result) -> None:
        if self.window is not None:
            self.window.show_result(result)

    def save_sample(self) -> None:
        result = self.targets.capture_sample()
        self.show_result(result)
        if result is None:
            return
        self.targets.status_label.setText(result.message)

    @staticmethod
    def _move_to_default_corner(window: MinimapSampleCaptureWindow) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        geometry = screen.availableGeometry()
        window.adjustSize()
        x = max(geometry.left(), geometry.right() - window.width() - 24)
        y = max(geometry.top(), geometry.bottom() - window.height() - 72)
        window.move(x, y)
