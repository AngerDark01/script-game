import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QWidget

from gui.modes.navigation.ui.components.map_view import NavigationMapGraphicsView, build_navigation_map_view


class NavigationEmptyStateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_empty_state_is_visible_until_map_is_attached(self):
        class Owner(QWidget):
            def load_map(self):
                pass

        owner = Owner()
        view = build_navigation_map_view(owner)
        view.resize(600, 400)
        view.show()
        self.app.processEvents()
        self.assertTrue(owner.empty_state.isVisible())
        owner.empty_state.set_message("测试标题", "测试说明")
        self.assertEqual(owner.empty_state.title_label.text(), "测试标题")
        owner.empty_state.set_visible_for_map(True)
        self.assertFalse(owner.empty_state.isVisible())
        view.close()


if __name__ == "__main__":
    unittest.main()
