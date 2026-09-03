import unittest
import os

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QWidget

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from gui.modes.navigation.ui.components.map_view import build_navigation_map_view
from gui.modes.navigation.presentation.map_presenter import cosmetic_pen
from gui.modes.navigation.presentation.route_overlay import route_pen


class NavigationOverlayStyleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_overlay_pens_keep_constant_screen_width(self):
        self.assertTrue(cosmetic_pen(QColor("red"), 2).isCosmetic())
        self.assertTrue(route_pen(QColor("yellow"), 3).isCosmetic())

    def test_map_legend_appears_after_map_item_is_attached(self):
        owner = QWidget()
        owner.load_map = lambda: None
        view = build_navigation_map_view(owner)
        view.resize(600, 400)
        view.show()
        view.set_map_item(view.scene().addRect(0, 0, 200, 100))
        self.app.processEvents()
        self.assertTrue(owner.map_legend.isVisible())
        view.close()


if __name__ == "__main__":
    unittest.main()
