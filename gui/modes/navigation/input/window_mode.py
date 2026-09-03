from __future__ import annotations

from PySide6.QtCore import Qt


class GameInputWindowMode:
    """Keep the tool window from covering the game while automated input runs."""

    def __init__(self, main_window) -> None:
        self.main_window = main_window
        self.enabled = False
        self.main_window_was_topmost = False

    def set_enabled(self, enabled: bool) -> None:
        if not self.main_window:
            return

        if enabled:
            if not self.enabled:
                self.main_window_was_topmost = bool(
                    self.main_window.windowFlags() & Qt.WindowStaysOnTopHint
                )
                if self.main_window_was_topmost:
                    self.main_window.setWindowFlag(Qt.WindowStaysOnTopHint, False)
                    self.main_window.show()
                self.enabled = True
                print("DEBUG: Game input mode enabled; main window is no longer topmost.")
            self.main_window.lower()
            return

        if not self.enabled:
            return
        if self.main_window_was_topmost:
            self.main_window.setWindowFlag(Qt.WindowStaysOnTopHint, True)
            self.main_window.show()
        self.enabled = False
        print("DEBUG: Game input mode disabled; main window topmost state restored.")
