from pathlib import Path
import time

from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication

from auto_modules.ui.virtual_gamepad.main_window import MainWindow


class DemoClient:
    def __init__(self):
        self.requests = []
        self.calls = []

    def status(self):
        return {
            "runState": "ready",
            "driverInstalled": True,
            "deviceConnected": True,
            "message": "",
        }

    def state(self):
        return {}

    def request(self, message_type, payload=None):
        self.requests.append((message_type, payload or {}))
        return {}

    def reset(self, controller=1, *, source=None, sequence=None):
        self.calls.append(("reset", controller, source, sequence))

    def pause(self, controller=1, *, source=None, sequence=None):
        self.calls.append(("pause", controller, source, sequence))

    def close(self):
        self.calls.append(("close", None, None, None))


def test_keyboard_dropdown_sets_j(tmp_path: Path):
    app = QApplication.instance() or QApplication([])
    client = DemoClient()
    window = MainWindow(client, demo=True, profile_path=tmp_path / "profile.json")
    window.profile.bindings = {}
    window._show_control("A")

    index = window.keyboard_combo.findData("keyboard:J")
    assert index >= 0
    window.keyboard_combo.setCurrentIndex(index)
    window._set_keyboard_binding()

    assert window.profile.bindings["A"] == ["keyboard:J"]
    assert window.binding_edit.text() == "keyboard:J"
    assert client.requests[-1] == ("set_config", window.profile.to_payload())

    window.close()
    app.processEvents()


def test_mouse_dropdown_updates_mouse_binding_and_keeps_keyboard(tmp_path: Path):
    app = QApplication.instance() or QApplication([])
    client = DemoClient()
    window = MainWindow(client, demo=True, profile_path=tmp_path / "profile.json")
    window.profile.bindings = {"A": ["keyboard:Space"]}
    window._show_control("A")

    index = window.mouse_combo.findData("mouse:right")
    assert index >= 0
    window.mouse_combo.setCurrentIndex(index)

    assert window.profile.bindings["A"] == ["keyboard:Space", "mouse:right"]
    assert window.binding_edit.text() == "keyboard:Space"
    assert client.requests[-1] == ("set_config", window.profile.to_payload())

    keyboard_index = window.keyboard_combo.findData("keyboard:F")
    assert keyboard_index >= 0
    window.keyboard_combo.setCurrentIndex(keyboard_index)
    window._set_keyboard_binding()
    assert window.profile.bindings["A"] == ["keyboard:F", "mouse:right"]
    assert window.mouse_combo.currentData() == "mouse:right"

    window.close()
    app.processEvents()


def test_closing_ui_pauses_the_host(tmp_path: Path):
    app = QApplication.instance() or QApplication([])
    client = DemoClient()
    cleanup_client = DemoClient()
    window = MainWindow(
        client,
        demo=True,
        profile_path=tmp_path / "profile.json",
        client_factory=lambda: cleanup_client,
    )

    event = QCloseEvent()
    window.closeEvent(event)
    deadline = time.monotonic() + 1
    while time.monotonic() < deadline and not window._close_approved:
        app.processEvents()
        time.sleep(0.005)

    assert not event.isAccepted()
    assert window._close_approved
    assert cleanup_client.calls[-1] == ("close", None, None, None)
    assert [call[:2] for call in cleanup_client.calls[:-1]] == [
        ("reset", 1),
        ("pause", 1),
        ("reset", 2),
        ("pause", 2),
    ]
    window.close()
    app.processEvents()
