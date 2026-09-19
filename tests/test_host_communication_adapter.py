from __future__ import annotations

from auto_modules.adapters.host.communication_adapter import HostCommunicationAdapter
from auto_modules.adapters.host.event_bridge import HostEventBridge
from auto_modules.application.communication.manager import CommunicationManager
from auto_modules.core.communication import Capability, DeliveryMode, MessageEnvelope, PeerId, Topic


class FakeClient:
    def __init__(self) -> None:
        self.connect_calls = 0
        self.close_calls = 0
        self.requests: list[tuple[str, dict | None]] = []

    def connect(self, timeout: float) -> None:
        self.connect_calls += 1

    def request(self, command: str, payload=None):
        self.requests.append((command, payload))
        if command == "sync.share.drain":
            return {
                "events": [{"deviceId": "peer-a", "id": "event-1", "name": "roll", "targets": ["1"], "remainingMs": 200}],
                "catalogs": [],
                "status": {"sharedPositions": []},
            }
        if command == "sync.status":
            return {"status": {"peers": [{"deviceId": "peer-a", "connected": True, "syncing": True, "dataOnly": True}]}}
        return {"ok": True}

    def close(self) -> None:
        self.close_calls += 1


def test_adapter_owns_one_client_while_manager_shares_peer_sessions() -> None:
    client = FakeClient()
    adapter = HostCommunicationAdapter(lambda: client)
    manager = CommunicationManager(adapter.transport)
    first = manager.acquire(PeerId("peer-a"), Capability.EVENT_PUBLISH)
    second = manager.acquire(PeerId("peer-a"), Capability.CATALOG_PUBLISH)
    envelope = MessageEnvelope("event-1", Topic.EVENT, {"name": "roll", "targets": ["1"]}, DeliveryMode.RELIABLE_ORDERED, 100)
    first.publish(envelope)
    second.publish(MessageEnvelope("catalog-1", Topic.CATALOG, {"catalog": {}}, DeliveryMode.RELIABLE_ORDERED, 100))
    assert client.connect_calls == 1
    assert [command for command, _ in client.requests] == ["sync.share.event", "sync.share.catalog"]


def test_pump_reads_shared_drain_once_and_bridge_consumes_adapter_queue() -> None:
    client = FakeClient()
    adapter = HostCommunicationAdapter(lambda: client)
    manager = CommunicationManager(adapter.transport)
    lease = manager.acquire(PeerId("peer-a"), Capability.EVENT_SUBSCRIBE)
    seen = []
    lease.subscribe(Topic.EVENT, lambda message: seen.append(message.payload["name"]))
    assert manager.pump() == 1
    bridge = HostEventBridge(manager=manager, communication=adapter)
    assert bridge.drain_events()[0]["name"] == "roll"
    assert seen == ["roll"]
    assert [command for command, _ in client.requests].count("sync.share.drain") == 1
