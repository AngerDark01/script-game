from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from auto_modules.adapters.host.communication_adapter import HostCommunicationAdapter
from auto_modules.adapters.host.event_bridge import HostEventBridge
from auto_modules.adapters.host.follow_transport import FollowTransport
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


def test_pump_reads_shared_drain_once_and_bridge_receives_subscription() -> None:
    client = FakeClient()
    adapter = HostCommunicationAdapter(lambda: client)
    manager = CommunicationManager(adapter.transport)
    lease = manager.acquire(PeerId("peer-a"), Capability.EVENT_SUBSCRIBE)
    seen = []
    lease.subscribe(Topic.EVENT, lambda message: seen.append(message.payload["name"]))
    bridge = HostEventBridge(manager=manager, communication=adapter)
    bridge.connect()
    bridge.status()
    assert manager.pump() == 1
    assert bridge.drain_events()[0]["name"] == "roll"
    assert seen == ["roll"]
    assert [command for command, _ in client.requests].count("sync.share.drain") == 1
    bridge.close()
    lease.close()


def test_follow_and_event_consumers_each_receive_one_drained_event() -> None:
    client = FakeClient()
    adapter = HostCommunicationAdapter(lambda: client)
    manager = CommunicationManager(adapter.transport)
    follow = FollowTransport(None, manager=manager, peer_id="peer-a")
    bridge = HostEventBridge(manager=manager, communication=adapter)
    bridge.connect()
    bridge.status()

    _, follow_events = follow.poll()
    event_events = bridge.drain_events()

    assert [item.name for item in follow_events] == ["roll"]
    assert [item["name"] for item in event_events] == ["roll"]
    assert [command for command, _ in client.requests].count("sync.share.drain") == 1
    follow.close()
    bridge.close()


def test_pump_fans_out_position_and_catalog_without_consuming_events() -> None:
    client = FakeClient()
    client.request = lambda command, payload=None: {
        "events": [{"deviceId": "peer-a", "id": "event-1", "name": "roll", "targets": ["1"]}],
        "catalogs": [{"deviceId": "peer-a", "messageId": "cat-1", "catalog": {"events": []}}],
        "status": {"sharedPositions": [{"deviceId": "peer-a", "sessionId": "session-1", "ageMs": 2,
            "position": {"actorId": "actor", "mapId": "map", "mapVersion": "v1", "x": 4, "y": 5, "confidence": .9}}]},
    }
    manager = CommunicationManager(HostCommunicationAdapter(lambda: client).transport)
    received = []
    leases = []
    for capability, topic in ((Capability.POSITION_SUBSCRIBE, Topic.POSITION),
                              (Capability.CATALOG_SUBSCRIBE, Topic.CATALOG),
                              (Capability.EVENT_SUBSCRIBE, Topic.EVENT)):
        for _ in range(2):
            lease = manager.acquire("peer-a", capability)
            lease.subscribe(topic, lambda message, topic=topic: received.append(topic))
            leases.append(lease)
    assert manager.pump() == 3
    assert received.count(Topic.POSITION) == 2
    assert received.count(Topic.CATALOG) == 2
    assert received.count(Topic.EVENT) == 2
    for lease in leases:
        lease.close()


def test_adapter_connect_is_single_flight_across_parallel_peers() -> None:
    client = FakeClient()
    adapter = HostCommunicationAdapter(lambda: client)
    barrier = Barrier(8)

    def open_peer(index: int) -> None:
        barrier.wait()
        adapter.transport.connect(PeerId(f"peer-{index}"))

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(open_peer, range(8)))
    assert client.connect_calls == 1
    adapter.close()
    assert client.close_calls == 1


def test_adapter_closes_failed_connection_and_exposes_dispatch_errors() -> None:
    class FailedClient(FakeClient):
        def connect(self, timeout: float) -> None:
            raise OSError("Host unavailable")

    failed = FailedClient()
    with pytest.raises(OSError, match="Host unavailable"):
        HostCommunicationAdapter(lambda: failed).ensure_connected()
    assert failed.close_calls == 1

    client = FakeClient()
    manager = CommunicationManager(HostCommunicationAdapter(lambda: client).transport)
    lease = manager.acquire("peer-a", Capability.EVENT_SUBSCRIBE)
    lease.subscribe(Topic.EVENT, lambda message: (_ for _ in ()).throw(ValueError("consumer failed")))
    with pytest.raises(ValueError, match="consumer failed"):
        manager.pump()
    lease.close()
