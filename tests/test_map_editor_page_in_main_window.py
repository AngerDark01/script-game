from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from auto_modules.ui.main_window import MainWindow
from tests.gamepad_test_support import InertGamepadHostManager


class MapEditorPageInMainWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_main_window_exposes_map_editor_as_the_fourth_embedded_mode(self) -> None:
        window = MainWindow(gamepad_host_manager=InertGamepadHostManager())
        try:
            self.assertEqual(3, window.stacked_widget.indexOf(window.map_editor_widget))
            self.assertIn(window.mode_btn_map_editor, window.mode_buttons)
            self.assertTrue(window.mode_btn_map_editor.isCheckable())

            window.switch_mode(3)

            self.assertIs(window.map_editor_widget, window.stacked_widget.currentWidget())
            self.assertTrue(window.mode_btn_map_editor.isChecked())
        finally:
            window.close()
            window.deleteLater()
            self.app.processEvents()


if __name__ == "__main__":
    unittest.main()
