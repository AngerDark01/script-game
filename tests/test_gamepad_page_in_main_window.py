import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QApplication, QWidget

from gui.gamepad.host_manager import HostShutdownResult, HostStartResult
from gui.main_window import MainWindow


class _FakePage(QWidget):
    shutdown_finished = Signal(bool, str)

    def __init__(self, *_args, **_kwargs):
        super().__init__()
        self.shutdown_calls = 0

    def shutdown(self) -> None:
        self.shutdown_calls += 1
        self.shutdown_finished.emit(True, "")

    def show_host_error(self, _message: str) -> None:
        return None


class _FakeHostManager:
    def __init__(self):
        self.start_calls = 0
        self.shutdown_calls = 0

    def start(self) -> HostStartResult:
        self.start_calls += 1
        return HostStartResult(connected=True, owns_host=False)

    def create_client(self):
        return object()

    def shutdown(self) -> HostShutdownResult:
        self.shutdown_calls += 1
        return HostShutdownResult(succeeded=True)


class GamepadPageInMainWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_main_window_exposes_gamepad_as_the_third_page_and_safely_shuts_it_down(self):
        manager = _FakeHostManager()
        with patch("gui.main_window.GamepadPage", _FakePage):
            window = MainWindow(gamepad_host_manager=manager)
            self.assertEqual(1, manager.start_calls)
            self.assertEqual(4, window.stacked_widget.count())
            self.assertEqual(4, len(window.mode_buttons))

            window.switch_mode(2)
            self.assertIs(window.gamepad_page, window.stacked_widget.currentWidget())
            self.assertTrue(window.mode_btn_gamepad.isChecked())

            window.close()
            self.app.processEvents()

            self.assertEqual(1, window.gamepad_page.shutdown_calls)
            self.assertEqual(1, manager.shutdown_calls)
            window.deleteLater()


if __name__ == "__main__":
    unittest.main()
