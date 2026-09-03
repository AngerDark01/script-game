import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QWidget

from gui.modes.navigation.ui.components.status import build_status_label


class NavigationStatusHudTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_hud_keeps_legacy_text_api_and_exposes_structured_values(self):
        owner = QWidget()
        hud = build_status_label(owner)
        hud.setText("测试状态")
        self.assertEqual(hud.text(), "测试状态")
        hud.set_hud_values(
            map_name="A",
            localization="已定位",
            confidence=0.92,
            activity="导航中",
        )
        self.assertEqual(hud.map_value.text(), "A")
        self.assertEqual(hud.localization_value.text(), "已定位")
        self.assertEqual(hud.confidence_value.text(), "0.92")
        self.assertEqual(hud.activity_value.text(), "导航中")
        hud.update_runtime(localized_pos=(10, 20), confidence=0.87, activity="跟踪中")
        self.assertEqual(hud.localization_value.text(), "已定位")
        self.assertEqual(hud.confidence_value.text(), "0.87")
        hud.deleteLater()


if __name__ == "__main__":
    unittest.main()
