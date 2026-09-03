from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from virtual_gamepad_ui.controller_widget import ControllerWidget


def test_controller_hitbox_accounts_for_widget_transform():
    app = QApplication.instance() or QApplication([])
    widget = ControllerWidget()
    widget.resize(820, 460)
    clicked: list[str] = []
    widget.control_clicked.connect(clicked.append)
    widget.show()
    app.processEvents()

    QTest.mouseClick(widget, Qt.LeftButton, pos=QPoint(670, 240))

    assert clicked == ["A"]
