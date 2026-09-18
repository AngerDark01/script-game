import json

from auto_modules.application.event_workbench.service import EventWorkbenchService


class TriggerSource:
    def __init__(self, *batches):
        self.batches = list(batches)

    def poll(self, keys):
        return self.batches.pop(0) if self.batches else ()


class FakeBridge:
    def __init__(self, *, events=(), catalogs=(), peers=()):
        self.events = list(events)
        self.catalogs = list(catalogs)
        self.peers = list(peers)
        self.connected = False
        self.closed = False
        self.states = []
        self.clears = []
        self.sent_events = []
        self.sent_catalogs = []
        self.failed_peers = set()

    def connect(self, timeout=2.0):
        self.connected = True

    def status(self):
        return {"deviceId": "device-a", "peers": self.peers}

    def drain_events(self):
        items, self.events = tuple(self.events), []
        return items

    def drain_catalogs(self):
        items, self.catalogs = tuple(self.catalogs), []
        return items

    def publish_catalog(self, peer_id, catalog):
        if peer_id in self.failed_peers:
            raise RuntimeError("peer disconnected")
        self.sent_catalogs.append((peer_id, catalog))
        return {"ok": True}

    def send_event(self, peer_id, payload):
        if peer_id in self.failed_peers:
            raise RuntimeError("peer disconnected")
        self.sent_events.append((peer_id, payload))
        return {"ok": True}

    def write_state(self, frame, ttl_ms=120):
        self.states.append((frame, ttl_ms))
        return {"accepted": True}

    def clear_source(self, controller, source):
        self.clears.append((controller, source))
        return {"accepted": True}

    def close(self):
        self.closed = True


def _write_events(root, records, *, remote=False):
    name = "remote_events.json" if remote else "events.json"
    (root / name).write_text(json.dumps(records), encoding="utf-8")


def _event(event_id="roll-id", name="roll", button="B", owner="device-a"):
    return {
        "id": event_id,
        "name": name,
        "owner_device_id": owner,
        "revision": 1,
        "tracks": [{"mode": "once", "buttons": [button], "hold_ms": 100}],
    }


def _peer(device_id):
    return {"deviceId": device_id, "connected": True, "syncing": True, "dataOnly": True}


def test_local_and_remote_dispatch_share_execution_but_preserve_sources(tmp_path):
    _write_events(tmp_path, [_event()])
    _write_events(tmp_path, [_event("remote-id", "dash", "A", "device-b")], remote=True)
    (tmp_path / "routes.json").write_text(json.dumps([{
        "source": "本机", "trigger": "F6", "event": "roll",
        "target": "本机", "controller": "Controller 1",
    }]), encoding="utf-8")
    bridge = FakeBridge(events=[{
        "id": "dispatch-1", "name": "dash", "eventId": "remote-id",
        "eventRevision": 1, "targets": ["2"], "remainingMs": 400,
    }])
    service = EventWorkbenchService(
        tmp_path,
        bridge_factory=lambda: bridge,
        trigger_source=TriggerSource(("F6",)),
        clock_ms=lambda: 0,
        monotonic=lambda: 0.0,
        host_clock_ms_func=lambda: 1000,
    )
    service.set_local_running(True)
    service.set_remote_running(True)

    service.tick_once()

    frames = {(item.source, item.controller): item.state for item, _ in bridge.states}
    assert frames[("event:local", 1)]["buttons"] == 0x2000
    assert frames[("event:remote", 2)]["buttons"] == 0x1000
    status = service.status()
    assert status.trigger_count == 1
    assert status.receive_count == 1


def test_catalog_drain_updates_remote_definitions_before_remote_dispatch(tmp_path):
    _write_events(tmp_path, [])
    bridge = FakeBridge(
        catalogs=[{"deviceId": "device-b", "definitions": [_event("r1", "dash", "A", "device-b")]}],
        events=[{"id": "dispatch", "name": "dash", "eventId": "r1", "eventRevision": 1,
                 "targets": ["1"], "remainingMs": 400}],
    )
    service = EventWorkbenchService(
        tmp_path,
        bridge_factory=lambda: bridge,
        trigger_source=TriggerSource(),
        clock_ms=lambda: 0,
        monotonic=lambda: 0.0,
    )
    service.set_remote_running(True)

    service.tick_once()

    assert service.status().receive_count == 1
    assert bridge.states[-1][0].state["buttons"] == 0x1000
    assert service.load_remote_events()[0]["id"] == "r1"


def test_remote_route_isolates_failed_peer_and_continues_fanout(tmp_path):
    _write_events(tmp_path, [_event()])
    (tmp_path / "routes.json").write_text(json.dumps([{
        "source": "本机", "trigger": "F6", "event": "roll",
        "target": "已配对设备", "controller": "Controller 1 + 2",
    }]), encoding="utf-8")
    bridge = FakeBridge(peers=[_peer("bad"), _peer("good")])
    bridge.failed_peers.add("bad")
    service = EventWorkbenchService(
        tmp_path,
        bridge_factory=lambda: bridge,
        trigger_source=TriggerSource(("F6",)),
        clock_ms=lambda: 0,
        monotonic=lambda: 0.0,
        host_clock_ms_func=lambda: 1000,
    )
    service.set_local_running(True)

    service.tick_once()

    assert [peer for peer, _ in bridge.sent_events] == ["good"]
    assert bridge.sent_events[0][1]["targets"] == ["1", "2"]
    assert bridge.sent_events[0][1]["eventId"] == "roll-id"
    assert service.status().trigger_count == 1


def test_disabling_one_source_clears_it_without_canceling_the_other(tmp_path):
    _write_events(tmp_path, [_event()])
    bridge = FakeBridge()
    service = EventWorkbenchService(
        tmp_path,
        bridge_factory=lambda: bridge,
        trigger_source=TriggerSource(),
        clock_ms=lambda: 0,
        monotonic=lambda: 0.0,
    )
    service.set_local_running(True)
    service.execution.start("local", "roll-id", (1,))
    service.set_remote_running(True)
    service.execution.start("remote", "roll-id", (1,))
    service.set_remote_running(False)

    service.tick_once()

    assert (1, "event:remote") in bridge.clears
    assert (1, "event:local") not in bridge.clears
    assert any(frame.source == "event:local" and frame.state["buttons"] for frame, _ in bridge.states)


def test_direct_send_uses_host_deadline_and_shutdown_is_idempotent(tmp_path):
    _write_events(tmp_path, [_event()])
    bridges = []

    def bridge_factory():
        bridge = FakeBridge(peers=[_peer("peer")])
        bridges.append(bridge)
        return bridge

    service = EventWorkbenchService(
        tmp_path,
        bridge_factory=bridge_factory,
        trigger_source=TriggerSource(),
        clock_ms=lambda: 0,
        monotonic=lambda: 0.0,
        host_clock_ms_func=lambda: 5000,
    )

    reply = service.send_remote_event("peer", "roll", (2,))
    service.tick_once()
    service.shutdown()
    service.shutdown()

    assert reply == {"ok": True}
    payload = bridges[0].sent_events[0][1]
    assert payload["deadlineMs"] == 5250
    assert payload["targets"] == ["2"]
    assert bridges[0].closed
    assert bridges[1].closed


def test_service_exposes_identity_free_drafts_and_bounded_runtime_logs(tmp_path):
    _write_events(tmp_path, [_event()])
    service = EventWorkbenchService(
        tmp_path,
        bridge_factory=FakeBridge,
        trigger_source=TriggerSource(),
    )

    draft = service.new_event_draft(service.load_local_events()[0])
    service.set_local_running(True)
    service.set_local_running(False)

    assert draft["name"] == "roll"
    assert "id" not in draft
    assert "revision" not in draft
    assert len(service.recent_log_lines(limit=1)) == 1
    assert "disabled" in service.recent_log_lines(limit=1)[0]
