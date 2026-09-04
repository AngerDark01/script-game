import unittest

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from virtual_gamepad_ui.controller_widget import ControllerWidget
from virtual_gamepad_ui.models import CONTROLS


class ControllerWidgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_controller_exposes_a_clickable_hitbox_for_every_virtual_control(self) -> None:
        widget = ControllerWidget()
        self.addCleanup(widget.deleteLater)
        widget.resize(880, 490)
        clicked: list[str] = []
        widget.control_clicked.connect(clicked.append)
        widget.show()
        self.app.processEvents()

        self.assertEqual(set(widget._hitboxes), set(CONTROLS))
        a_rect = widget._hitboxes["A"]
        a_position = QPoint(
            round(widget._offset.x() + (a_rect.center().x() * widget._scale)),
            round(widget._offset.y() + (a_rect.center().y() * widget._scale)),
        )
        QTest.mouseClick(widget, Qt.MouseButton.LeftButton, pos=a_position)

        self.assertEqual(clicked, ["A"])


if __name__ == "__main__":
    unittest.main()
