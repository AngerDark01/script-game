import json
import tempfile
import unittest
from pathlib import Path

from auto_modules.core.events.event_store import EventStore


class EventStoreTests(unittest.TestCase):
    def test_legacy_local_event_id_is_persisted_and_stable(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "events.json").write_text(
                json.dumps([{"name": "legacy", "tracks": []}]),
                encoding="utf-8",
            )
            store = EventStore(root, "device-a")
            first = store.by_name("legacy")
            second = store.by_name("legacy")
            self.assertEqual(first["id"], second["id"])
            saved = json.loads((root / "events.json").read_text(encoding="utf-8"))
            self.assertEqual(saved[0]["id"], first["id"])

    def test_remote_catalog_is_read_only_and_revisioned(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            store = EventStore(root, "device-a")
            store.save_local([{"name": "local", "tracks": []}])
            self.assertEqual(store.apply_remote([{"id": "remote-1", "name": "remote", "owner_device_id": "device-b", "revision": 2, "tracks": []}]), 1)
            self.assertEqual(store.apply_remote([{"id": "remote-1", "name": "old", "owner_device_id": "device-b", "revision": 1, "tracks": []}]), 0)
            self.assertEqual(store.by_id("remote-1")["name"], "remote")
            self.assertEqual(len(json.loads((root / "remote_events.json").read_text(encoding="utf-8"))), 1)


if __name__ == "__main__":
    unittest.main()
