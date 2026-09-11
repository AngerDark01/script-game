import json
import tempfile
import unittest
from pathlib import Path

from core.events.event_store import EventStore


class EventStoreTests(unittest.TestCase):
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
