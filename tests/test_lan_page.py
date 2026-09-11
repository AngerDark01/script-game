import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtWidgets import QApplication
from gui.modes.lan import LanPage


def test_lan_page_has_dedicated_sync_workspace():
    app = QApplication.instance() or QApplication([])
    page = LanPage(lambda: None)
    assert page.panel.mode.count() == 4
    assert page.panel.peer_code.placeholderText()
    assert page.panel.receive_events.text().startswith('允许')
    page.close()
