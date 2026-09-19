from __future__ import annotations

from auto_modules.ui.composition import create_communication_services


def test_external_runtime_stays_owned_by_caller_after_window_close(monkeypatch) -> None:
    import os
    from unittest.mock import Mock

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    from auto_modules.application.communication.manager import CommunicationManager
    from auto_modules.adapters.host.communication_adapter import HostCommunicationAdapter
    from auto_modules.ui.main_window import MainWindow
    from tests.gamepad_test_support import InertGamepadHostManager

    app = QApplication.instance() or QApplication([])
    adapter = HostCommunicationAdapter(FakeClient)
    manager = CommunicationManager(adapter.transport)
    manager.close = Mock(wraps=manager.close)
    adapter.close = Mock(wraps=adapter.close)
    window = MainWindow(
        gamepad_host_manager=InertGamepadHostManager(),
        communication_manager=manager,
        communication_adapter=adapter,
    )
    try:
        assert window.follow_page.communication_manager is manager
        assert window.event_workbench.service._communication_manager is manager
        window.close()
        app.processEvents()
        manager.close.assert_not_called()
        adapter.close.assert_not_called()
    finally:
        window.deleteLater()
        manager.close()
        adapter.close()


class FakeClient:
    def connect(self, timeout: float) -> None:
        return None

    def close(self) -> None:
        return None

    def request(self, command: str, payload=None) -> dict:
        if command == "sync.status":
            return {"status": {"deviceId": "local", "peers": []}}
        if command == "sync.share.drain":
            return {"events": [], "catalogs": [], "status": {"sharedPositions": []}}
        return {"ok": True}


def test_ui_composition_builds_one_shared_adapter_and_manager() -> None:
    services = create_communication_services(FakeClient)

    assert services.manager.transport.adapter is services.adapter
    services.manager.close()
    services.adapter.close()
