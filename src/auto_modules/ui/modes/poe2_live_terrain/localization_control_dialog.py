"""Non-modal controls for the PoE2 multi-frame localization experiment."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QLabel, QVBoxLayout

from .multiframe_panel import Poe2MultiframePanel


class Poe2LocalizationControlDialog(QDialog):
    """Own only the experiment controls; matching remains in the session."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("PoE2 定位控制")
        self.setModal(False)
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self.resize(560, 420)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("方案 A/B 多帧定位实验"))
        self.panel = Poe2MultiframePanel(self)
        layout.addWidget(self.panel)
        self._ready = False
        self.set_ready(False)

    def set_ready(self, ready: bool) -> None:
        self._ready = bool(ready)
        if not self._ready:
            self.panel.start_button.setEnabled(False)
            return
        self.panel.set_running(self.panel.stop_button.isEnabled())

    def show_non_modal(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()


__all__ = ["Poe2LocalizationControlDialog"]
