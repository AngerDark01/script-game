import unittest
import json
import tempfile
from pathlib import Path

from core.actions.program_gamepad import host_clock_ms
from core.runtime.local_event_runtime import _data_only_peers
from core.runtime.local_event_runtime import LocalEventRuntime
from core.runtime.remote_event_sender import RemoteEventSender
from core.runtime.remote_event_runtime import RemoteEventRuntime
from core.events.event_store import EventStore


class RemoteEventDeliveryTests(unittest.TestCase):
    def test_catalog_and_event_use_the_same_legacy_event_id(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "events.json").write_text(
                json.dumps([{"name": "roll", "tracks": []}]),
                encoding="utf-8",
            )
            store = EventStore(root, "sender")
            catalog = LocalEventRuntime._catalog_payload(store, "sender")
            record = store.by_name("roll")
            self.assertEqual(catalog["definitions"][0]["id"], record["id"])

    def test_remote_receiver_falls_back_to_name_for_legacy_id_mismatch(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "events.json").write_text(
                json.dumps([{"id": "stable", "name": "roll", "revision": 1, "tracks": []}]),
                encoding="utf-8",
            )
            store = EventStore(root, "receiver")
            item = {"name": "roll", "eventId": "stale-id", "eventRevision": 1}
            self.assertEqual(RemoteEventRuntime._resolve_event_name(store, item), "roll")

    def test_remote_receiver_drains_event_and_writes_nonzero_host_state(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "events.json").write_text(
                json.dumps([{
                    "id": "stable", "name": "roll", "revision": 1,
                    "tracks": [{"mode": "once", "buttons": ["B"], "hold_ms": 100}],
                }]),
                encoding="utf-8",
            )

            class Client:
                def __init__(self):
                    self.drained = False
                    self.states = []

                def connect(self, timeout):
                    pass

                def request(self, command, payload=None):
                    if command == "sync.status":
                        return {"status": {"deviceId": "receiver", "mode": "share", "receiveEvents": True, "peers": []}}
                    if command == "sync.share.drain":
                        if self.drained:
                            return {"events": [], "catalogs": []}
                        self.drained = True
                        return {"events": [{
                            "name": "roll", "eventId": "stable", "eventRevision": 1,
                            "targets": ["1"], "remainingMs": 400,
                        }], "catalogs": []}
                    if command == "event.state":
                        self.states.append(payload)
                        return {"accepted": True}
                    if command == "event.clear":
                        return {"accepted": True}
                    raise AssertionError(command)

                def close(self):
                    pass

            client = Client()
            runtime = RemoteEventRuntime(root=root, client_factory=lambda: client)
            runtime.start()
            deadline = __import__("time").monotonic() + 1
            while not client.states and __import__("time").monotonic() < deadline:
                __import__("time").sleep(0.01)
            runtime.stop()
            self.assertEqual(runtime.receive_count, 1)
            self.assertTrue(any(state["controller"] == 1 and state["state"]["buttons"] for state in client.states))

    def test_local_event_peer_selection_excludes_controller_sessions(self):
        status = {
            "peers": [
                {"deviceId": "controller", "connected": True, "syncing": True, "dataOnly": False},
                {"deviceId": "event", "connected": True, "syncing": True, "dataOnly": True},
                {"deviceId": "connecting", "connected": False, "syncing": True, "dataOnly": True},
            ]
        }
        self.assertEqual([peer["deviceId"] for peer in _data_only_peers(status)], ["event"])

    def test_direct_remote_event_uses_host_deadline_within_protocol_window(self):
        captured = {}

        class Client:
            def connect(self, timeout):
                pass

            def request(self, command, payload=None):
                if command == "sync.status":
                    return {"status": {"peers": [{"deviceId": "peer", "connected": True, "syncing": True, "dataOnly": True}]}}
                captured["command"] = command
                captured["payload"] = payload
                return {"ok": True}

            def close(self):
                pass

        sender = RemoteEventSender(client_factory=Client)
        sender.send("peer", "roll")
        deadline = captured["payload"]["deadlineMs"]
        now = host_clock_ms()
        self.assertEqual(captured["command"], "sync.share.event")
        self.assertTrue(0 < deadline - now <= 250)
