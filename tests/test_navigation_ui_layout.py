import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from gui.main_window import MainWindow


class NavigationUiLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = MainWindow()
        self.window.switch_mode(1)
        self.nav = self.window.nav_widget

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()

    def test_compact_rows_do_not_absorb_vertical_space(self):
        self.window.resize(1600, 1000)
        self.window.show()
        self.app.processEvents()
        for bar in (
            self.nav.map_selector_bar,
            self.nav.navigation_actions_bar,
            self.nav.utility_bar,
            self.nav.status_label,
        ):
            self.assertLessEqual(bar.height(), 56)
        self.assertGreater(self.nav.view.height(), 500)

    def test_compact_window_has_a_realistic_minimum_width(self):
        self.window.resize(500, 700)
        self.window.show()
        self.app.processEvents()
        self.assertLessEqual(self.window.width(), 520)


if __name__ == "__main__":
    unittest.main()
