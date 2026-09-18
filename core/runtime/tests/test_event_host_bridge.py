import pytest

from core.events.automation.execution import EventStateFrame
from core.runtime.event_service.host_bridge import HostEventBridge


class FakeClient:
    def __init__(self):
        self.connected_with = None
        self.closed = False
        self.requests = []

    def connect(self, timeout):
        self.connected_with = timeout

    def request(self, command, payload=None):
        self.requests.append((command, payload))
        if command == "sync.status":
            return {"status": {
                "deviceId": "device-a",
                "peers": [
                    {"deviceId": "data", "connected": True, "syncing": True, "dataOnly": True},
                    {"deviceId": "controller", "connected": True, "syncing": True, "dataOnly": False},
                    {"deviceId": "offline", "connected": False, "syncing": True, "dataOnly": True},
                ],
            }}
        if command == "sync.share.drain":
            return {"events": [{"name": "roll"}], "catalogs": [{"ignored": True}]}
        if command == "sync.share.catalog_drain":
            return {"catalogs": [{"definitions": []}]}
        return {"ok": True}

    def close(self):
        self.closed = True


def test_bridge_uses_exact_host_commands_and_filters_data_peers():
    client = FakeClient()
    bridge = HostEventBridge(client_factory=lambda: client)
    bridge.connect(timeout=1.5)

    assert bridge.status()["deviceId"] == "device-a"
    assert [item["deviceId"] for item in bridge.data_only_peers()] == ["data"]
    assert bridge.drain_events() == ({"name": "roll"},)
    assert bridge.drain_catalogs() == ({"definitions": []},)
    assert ("sync.share.drain", None) in client.requests
    assert ("sync.share.catalog_drain", None) in client.requests
    assert client.connected_with == 1.5


def test_bridge_writes_and_clears_only_the_frame_source():
    client = FakeClient()
    bridge = HostEventBridge(client_factory=lambda: client)
    bridge.connect()
    frame = EventStateFrame(
        source="event:remote",
        controller=2,
        state={"buttons": 0x2000, "leftStickX": 0, "leftStickY": 0},
    )

    bridge.write_state(frame, ttl_ms=120)
    bridge.clear_source(2, "event:remote")

    assert client.requests[-2:] == [
        ("event.state", {
            "controller": 2,
            "source": "event:remote",
            "state": frame.state,
            "ttlMs": 120,
        }),
        ("event.clear", {"controller": 2, "source": "event:remote"}),
    ]


def test_bridge_exposes_catalog_and_event_transport_without_policy():
    client = FakeClient()
    bridge = HostEventBridge(client_factory=lambda: client)
    bridge.connect()

    bridge.publish_catalog("peer", {"definitions": []})
    bridge.send_event("peer", {"name": "roll", "targets": ["1"]})

    assert client.requests[-2:] == [
        ("sync.share.catalog", {"deviceId": "peer", "catalog": {"definitions": []}}),
        ("sync.share.event", {"name": "roll", "targets": ["1"], "deviceId": "peer"}),
    ]


def test_bridge_requires_connection_and_closes_idempotently():
    client = FakeClient()
    bridge = HostEventBridge(client_factory=lambda: client)

    with pytest.raises(RuntimeError, match="not connected"):
        bridge.status()
    bridge.connect()
    bridge.close()
    bridge.close()

    assert client.closed
