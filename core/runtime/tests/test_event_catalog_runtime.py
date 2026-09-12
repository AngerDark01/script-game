import json
import tempfile
import time
import unittest
from pathlib import Path

from core.runtime.event_catalog_runtime import EventCatalogRuntime


class _CatalogClient:
    def __init__(self):
        self.commands = []
        self.sent_catalogs = []
        self.drained = False

    def connect(self, timeout):
        return None

    def request(self, command, payload=None):
        self.commands.append(command)
        if command == "sync.status":
            return {"status": {
                "deviceId": "receiver",
                "peers": [{"deviceId": "sender", "connected": True, "syncing": True, "dataOnly": True}],
            }}
        if command == "sync.share.catalog":
            self.sent_catalogs.append(payload)
            return {"ok": True}
        if command == "sync.share.catalog_drain":
            if self.drained:
                return {"catalogs": []}
            self.drained = True
            return {"catalogs": [{
                "deviceId": "sender",
                "definitions": [{
                    "id": "remote-roll", "name": "remote roll", "owner_device_id": "sender",
                    "revision": 1, "tracks": [],
                }],
            }]}
        if command == "event.state":
            raise AssertionError("catalog runtime must never emit event.state")
        if command == "sync.share.drain":
            raise AssertionError("catalog runtime must never consume shared events")
        raise AssertionError(command)

    def close(self):
        return None


class EventCatalogRuntimeTests(unittest.TestCase):
    def test_catalog_runtime_publishes_and_applies_without_event_drain(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "events.json").write_text(json.dumps([{
                "id": "local-roll", "name": "local roll", "revision": 1, "tracks": [],
            }]), encoding="utf-8")
            client = _CatalogClient()
            runtime = EventCatalogRuntime(root=root, client_factory=lambda: client, interval=60)
            runtime.start()
            deadline = time.monotonic() + 1.0
            while not (root / "remote_events.json").exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            runtime.stop()

            remote = json.loads((root / "remote_events.json").read_text(encoding="utf-8"))
            self.assertEqual(["remote-roll"], [item["id"] for item in remote])
            self.assertTrue(client.sent_catalogs)
            self.assertIn("sync.share.catalog_drain", client.commands)
            self.assertNotIn("sync.share.drain", client.commands)
            self.assertNotIn("event.state", client.commands)


if __name__ == "__main__":
    unittest.main()
