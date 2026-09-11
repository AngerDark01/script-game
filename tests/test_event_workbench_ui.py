import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtWidgets import QApplication
from gui.modes.events import EventWorkbenchPage


def test_event_workbench_has_separate_edit_route_and_monitor_tabs(tmp_path):
    app = QApplication.instance() or QApplication([])
    page = EventWorkbenchPage(root=tmp_path)
    assert page.tabs.count() == 3
    assert [page.tabs.tabText(i) for i in range(3)] == ['事件库 / 编排', '触发与路由', '运行监控']
    page.events.append({'name': '技能A', 'tracks': [{'mode': 'once', 'buttons': ['LB', 'X'], 'hold_ms': 80}]})
    page._refresh()
    assert page.list.count() == 1
    assert page.track_table.item(0, 1).text() == 'LB+X'
    page._save()
    assert (tmp_path / 'events.json').is_file()
    page.close()
