from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QEvent, QTimer, Qt
from PySide6.QtGui import QKeyEvent, QKeySequence
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from .controller_widget import ControllerWidget
from .models import BindingProfile, CONTROLS, StateSnapshot, UiStatus
from .profile_store import load_profile, save_profile


class MainWindow(QMainWindow):
    def __init__(self, client: Any, demo: bool = False, profile_path: Path | None = None) -> None:
        super().__init__()
        self.client = client
        self.demo = demo
        self.profile_path = profile_path or Path(__file__).resolve().parents[2] / "configs" / "default.json"
        self.profile = load_profile(self.profile_path)
        self._capture_mode = False
        self._connected = False
        self._last_status = UiStatus()
        self.setWindowTitle("Virtual Gamepad")
        self.resize(1120, 700)
        self._build_ui()
        self._install_capture_filter()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(50)
        self.refresh()

    def _build_ui(self) -> None:
        root = QWidget(self)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(14, 14, 14, 10)
        layout.setSpacing(10)

        top = QHBoxLayout()
        self.driver_label = QLabel("Driver: checking")
        self.device_label = QLabel("Device: checking")
        self.state_label = QLabel("State: Disconnected")
        self.message_label = QLabel("")
        top.addWidget(self.driver_label)
        top.addWidget(self.device_label)
        top.addWidget(self.state_label)
        top.addWidget(self.message_label, 1)
        self.start_button = QPushButton("Start / Resume")
        self.pause_button = QPushButton("Pause")
        self.reset_button = QPushButton("Emergency Reset")
        self.start_button.clicked.connect(self._start)
        self.pause_button.clicked.connect(self._pause)
        self.reset_button.clicked.connect(self._reset)
        top.addWidget(self.start_button)
        top.addWidget(self.pause_button)
        top.addWidget(self.reset_button)
        layout.addLayout(top)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.controller = ControllerWidget()
        self.controller.control_clicked.connect(self._select_control)
        splitter.addWidget(self.controller)

        side = QWidget()
        side_layout = QVBoxLayout(side)
        side_layout.addWidget(QLabel("Binding editor"))
        self.control_list = QListWidget()
        self.control_list.addItems(CONTROLS)
        self.control_list.currentTextChanged.connect(self._show_control)
        side_layout.addWidget(self.control_list, 1)
        form = QFormLayout()
        self.selected_label = QLabel("Select a control")
        self.binding_edit = QLineEdit()
        self.binding_edit.setPlaceholderText("keyboard:Space or mouse:left")
        form.addRow("Control", self.selected_label)
        form.addRow("Binding", self.binding_edit)
        side_layout.addLayout(form)
        capture_row = QHBoxLayout()
        self.capture_button = QPushButton("Capture next input")
        self.clear_button = QPushButton("Clear")
        self.capture_button.clicked.connect(self._capture)
        self.clear_button.clicked.connect(self._clear_binding)
        capture_row.addWidget(self.capture_button)
        capture_row.addWidget(self.clear_button)
        side_layout.addLayout(capture_row)
        profile_row = QHBoxLayout()
        self.profile_combo = QComboBox()
        self.profile_combo.addItem("default")
        self.save_button = QPushButton("Save profile")
        self.save_button.clicked.connect(self._save_profile)
        profile_row.addWidget(self.profile_combo, 1)
        profile_row.addWidget(self.save_button)
        side_layout.addLayout(profile_row)
        shortcut_label = QLabel(f"Start/Pause: {self.profile.start_pause}    Emergency reset: {self.profile.emergency_reset}")
        shortcut_label.setObjectName("shortcutLabel")
        side_layout.addWidget(shortcut_label)
        splitter.addWidget(side)
        splitter.setSizes([780, 300])
        layout.addWidget(splitter, 1)
        self.setCentralWidget(root)
        self.control_list.setCurrentRow(0)

    def _install_capture_filter(self) -> None:
        self._app = self.window().windowHandle()
        from PySide6.QtWidgets import QApplication

        QApplication.instance().installEventFilter(self)

    def refresh(self) -> None:
        try:
            if not self.demo and not self._connected:
                self.client.connect(timeout=0.05)
                self._connected = True
            payload = self.client.status()
            self._last_status = UiStatus.from_payload(payload)
            state = StateSnapshot.from_payload(self.client.state())
        except Exception as exc:
            self._connected = False if not self.demo else self._connected
            self._last_status = UiStatus(message=str(exc))
            state = StateSnapshot()
        self.driver_label.setText(f"Driver: {'ready' if self._last_status.driver_installed else 'missing'}")
        self.device_label.setText(f"Device: {'connected' if self._last_status.device_connected else 'unavailable'}")
        self.state_label.setText(f"State: {self._last_status.run_state}")
        self.message_label.setText(self._last_status.message)
        self.controller.set_snapshot(state)
        self.controller.set_profile(self.profile)

    def _select_control(self, control: str) -> None:
        matches = self.control_list.findItems(control, Qt.MatchFlag.MatchExactly)
        if matches:
            self.control_list.setCurrentItem(matches[0])

    def _show_control(self, control: str) -> None:
        self.selected_label.setText(control or "Select a control")
        self.binding_edit.setText(self.profile.label_for(control) if control else "")

    def _capture(self) -> None:
        self._capture_mode = True
        self.capture_button.setText("Press a key or mouse button...")
        self.capture_button.setEnabled(False)

    def _finish_capture(self, source: str) -> None:
        control = self.control_list.currentItem().text() if self.control_list.currentItem() else ""
        if control:
            self.profile.bindings[control] = [source]
            self.binding_edit.setText(source)
            self.controller.set_profile(self.profile)
        self._capture_mode = False
        self.capture_button.setEnabled(True)
        self.capture_button.setText("Capture next input")

    def eventFilter(self, _watched: object, event: QEvent) -> bool:
        if not self._capture_mode:
            return super().eventFilter(_watched, event)
        if event.type() == QEvent.Type.KeyPress and isinstance(event, QKeyEvent):
            key = QKeySequence(event.modifiers() | event.key()).toString() or str(event.key())
            self._finish_capture(f"keyboard:{key}")
            return True
        if event.type() == QEvent.Type.MouseButtonPress:
            self._finish_capture(f"mouse:{event.button().name.lower()}")
            return True
        return super().eventFilter(_watched, event)

    def _clear_binding(self) -> None:
        control = self.control_list.currentItem().text() if self.control_list.currentItem() else ""
        self.profile.bindings.pop(control, None)
        self._show_control(control)
        self.controller.set_profile(self.profile)

    def _save_profile(self) -> None:
        try:
            save_profile(self.profile_path, self.profile)
            try:
                self.client.request("set_config", self.profile.to_payload())
            except Exception:
                pass
            self.statusBar().showMessage(f"Saved {self.profile_path}", 3000)
        except Exception as exc:
            QMessageBox.critical(self, "Save failed", str(exc))

    def _start(self) -> None:
        try:
            self.client.start()
        except Exception as exc:
            self.statusBar().showMessage(str(exc), 4000)

    def _pause(self) -> None:
        try:
            self.client.pause()
        except Exception as exc:
            self.statusBar().showMessage(str(exc), 4000)

    def _reset(self) -> None:
        try:
            self.client.emergency_reset()
        except Exception as exc:
            self.statusBar().showMessage(str(exc), 4000)
