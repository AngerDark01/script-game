import os
from copy import deepcopy

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from auto_modules.application.event_workbench import EventWorkbenchStatus
from auto_modules.ui.modes.events import EventWorkbenchPage


class FakeEventWorkbenchService:
    def __init__(self):
        self.local_events = [{
            "id": "local-1",
            "name": "skill-a",
            "owner_device_id": "device-a",
            "revision": 3,
            "tracks": [{"mode": "once", "buttons": ["LB", "X"], "hold_ms": 80}],
        }]
        self.remote_events = [{
            "id": "remote-1",
            "name": "skill-b",
            "owner_device_id": "device-b",
            "revision": 2,
            "tracks": [],
        }]
        self.routes = []
        self.status_value = EventWorkbenchStatus()
        self.started = False
        self.stopped = False
        self.saved_events = []
        self.saved_routes = []
        self.sent = []

    def start(self):
        self.started = True

    def load_local_events(self):
        return deepcopy(self.local_events)

    def load_remote_events(self):
        return deepcopy(self.remote_events)

    def load_routes(self):
        return deepcopy(self.routes)

    def save(self, events, routes):
        self.saved_events = deepcopy(list(events))
        self.saved_routes = deepcopy(list(routes))
        self.local_events = deepcopy(self.saved_events)
        return deepcopy(self.local_events)

    def new_event_draft(self, source=None):
        source = deepcopy(source or {})
        for key in ("id", "owner_device_id", "revision", "updated_at", "deleted", "content_hash"):
            source.pop(key, None)
        return source

    def set_local_running(self, enabled):
        self.status_value = EventWorkbenchStatus(
            **{**self.status_value.__dict__, "local_running": bool(enabled)}
        )

    def set_remote_running(self, enabled):
        self.status_value = EventWorkbenchStatus(
            **{**self.status_value.__dict__, "remote_running": bool(enabled)}
        )

    def send_remote_event(self, device_id, event_name, controllers):
        self.sent.append((device_id, event_name, tuple(controllers)))
        return {"ok": True}

    def status(self):
        return self.status_value

    def recent_log_lines(self, limit=80):
        return ["event service ready"][-limit:]

    def shutdown(self):
        self.stopped = True


def test_event_workbench_is_a_service_only_ui_adapter(tmp_path):
    app = QApplication.instance() or QApplication([])
    service = FakeEventWorkbenchService()

    page = EventWorkbenchPage(root=tmp_path, service=service)

    assert service.started
    assert page.tabs.count() == 4
    assert [page.tabs.tabText(i) for i in range(4)] == [
        "事件库", "触发与路由", "运行监控", "远程发送",
    ]
    assert page.list.count() == 2
    assert page.track_table.item(0, 1).text() == "LB+X"

    page._add_route()
    page.routes.cellWidget(0, 1).setCurrentText("F6")
    page._save()

    assert service.saved_events[0]["id"] == "local-1"
    assert service.saved_routes[0]["trigger"] == "F6"
    assert list(tmp_path.iterdir()) == []

    page.list.setCurrentRow(0)
    page._copy()
    assert page.events[-1]["name"] == "skill-a \u526f\u672c"
    assert "id" not in page.events[-1]

    page._toggle_runtime()
    page._toggle_remote_runtime()
    assert service.status().local_running
    assert service.status().remote_running

    page.remote_device.setText("device-b")
    page.remote_event.setCurrentText("skill-a")
    page.remote_controller.setCurrentText("Controller 1 + 2")
    page._send_remote_event()
    assert service.sent == [("device-b", "skill-a", (1, 2))]

    page._poll_runtime()
    assert page.local_log.toPlainText() == "event service ready"

    page.shutdown()
    assert service.stopped
    page.deleteLater()
