import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from gui.main_window import MainWindow


class NavigationCompactActionsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_low_frequency_actions_move_to_more_menu(self):
        window = MainWindow()
        window.switch_mode(1)
        window.show()
        self.app.processEvents()
        nav = window.nav_widget
        self.assertTrue(nav.compact_more_button.isVisible())
        self.assertFalse(nav.event_button.isVisible())
        self.assertFalse(nav.params_button.isVisible())
        self.assertFalse(nav.map_fit_button.isVisible())
        labels = [action.text() for action in nav.compact_more_button.menu().actions()]
        self.assertIn("事件管理", labels)
        self.assertIn("适应地图", labels)
        nav.navigation_compact_controller.set_compact_mode(False)
        self.assertFalse(nav.compact_more_button.isVisible())
        self.assertTrue(nav.event_button.isVisible())
        self.assertTrue(nav.map_fit_button.isVisible())
        window.close()


if __name__ == "__main__":
    unittest.main()
