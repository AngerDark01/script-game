import unittest

from auto_modules.core.events.event_catalog import EventRecord, catalog_summary, migrate_events


class EventCatalogTests(unittest.TestCase):
    def test_migration_assigns_stable_identity_and_owner(self):
        value = migrate_events([{"name": "翻滚", "tracks": [{"buttons": ["A"]}]}], "device-a")
        self.assertEqual(value[0]["owner_device_id"], "device-a")
        self.assertTrue(value[0]["id"])
        self.assertEqual(value[0]["revision"], 1)

    def test_update_increments_revision_and_owner_is_preserved(self):
        record = EventRecord.from_dict({"id": "e1", "name": "A", "tracks": []}, default_owner="a")
        updated = record.updated({"name": "A2", "tracks": [{"buttons": ["B"]}]})
        self.assertEqual(updated.owner_device_id, "a")
        self.assertEqual(updated.revision, 2)
        self.assertEqual(updated.name, "A2")

    def test_summary_contains_read_only_metadata(self):
        value = catalog_summary([{"id": "e1", "name": "A", "tracks": []}], "a")
        self.assertEqual(value["events"][0]["ownerDeviceId"], "a")
        self.assertEqual(value["events"][0]["revision"], 1)


if __name__ == "__main__":
    unittest.main()
