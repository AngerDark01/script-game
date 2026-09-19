from __future__ import annotations

from auto_modules.adapters.host.communication_adapter import HostCommunicationAdapter
from auto_modules.application.event_workbench.service import EventWorkbenchService
from auto_modules.application.communication.manager import CommunicationManager
from auto_modules.features.torchlight.follow.config import FollowConfig
from auto_modules.features.torchlight.follow.service import FollowService


class Client:
    def connect(self, timeout: float) -> None:
        pass

    def request(self, command: str, payload=None):
        if command == "sync.status":
            return {"status": {"deviceId": "local", "peers": []}}
        if command == "sync.share.drain":
            return {"events": [], "catalogs": [], "status": {"sharedPositions": []}}
        return {"ok": True}

    def close(self) -> None:
        pass


def test_event_workbench_uses_injected_manager_and_adapter(tmp_path) -> None:
    adapter = HostCommunicationAdapter(lambda: Client())
    manager = CommunicationManager(adapter.transport)
    service = EventWorkbenchService(
        tmp_path,
        communication_manager=manager,
        communication_adapter=adapter,
    )
    bridge = service._ensure_bridge()
    assert bridge._manager is manager
    assert bridge._communication is adapter
    service.shutdown()


def test_follow_service_accepts_the_same_process_scoped_manager(tmp_path) -> None:
    map_path = tmp_path / "map.npz"
    map_path.touch()
    config = FollowConfig(map_path=str(map_path), map_id="map", leader_device="peer-a")
    for index, actor in enumerate(config.actors):
        actor["parameters"] = {"hue_min": 40 + index * 20, "hue_max": 60 + index * 20, "max_area": 100}
    manager = CommunicationManager(HostCommunicationAdapter(lambda: Client()).transport)
    service = FollowService(config, communication_manager=manager)
    assert service.communication_manager is manager
