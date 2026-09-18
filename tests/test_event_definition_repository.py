import json

from core.events.action_tracks import TrackMode
from core.events.automation.definitions import EventDefinitionRepository


def _write(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")


def test_repository_uses_one_parser_for_local_and_remote_records(tmp_path):
    local = [{
        "id": "l1",
        "name": "roll",
        "owner_device_id": "device-a",
        "revision": 1,
        "tracks": [{"mode": "once", "buttons": ["B"], "hold_ms": 80}],
    }]
    remote = [{
        "id": "r1",
        "name": "dash",
        "owner_device_id": "device-b",
        "revision": 2,
        "tracks": [{
            "mode": "continuous",
            "buttons": ["LS_RIGHT"],
            "hold_ms": 50,
            "interval_ms": 100,
            "end_ms": 500,
        }],
    }]
    _write(tmp_path / "events.json", local)
    _write(tmp_path / "remote_events.json", remote)

    repository = EventDefinitionRepository(tmp_path, "device-a")
    definitions = repository.definitions()
    local[0]["tracks"][0]["buttons"][0] = "A"

    assert definitions["l1"].tracks[0].buttons == ("B",)
    assert definitions["r1"].tracks[0].mode is TrackMode.CONTINUOUS
    assert definitions["r1"].owner_device_id == "device-b"


def test_repository_catalog_and_lookup_share_stable_identity(tmp_path):
    _write(tmp_path / "events.json", [{"name": "roll", "tracks": []}])
    repository = EventDefinitionRepository(tmp_path, "device-a")

    payload = repository.catalog_payload()
    record = repository.by_name("roll")

    assert record is not None
    assert payload["definitions"][0]["id"] == record["id"]
    assert payload["deviceId"] == "device-a"


def test_repository_save_versions_only_changed_existing_records(tmp_path):
    _write(tmp_path / "events.json", [{
        "id": "stable",
        "name": "roll",
        "owner_device_id": "device-a",
        "revision": 3,
        "tracks": [{"mode": "once", "buttons": ["B"], "hold_ms": 80}],
    }])
    repository = EventDefinitionRepository(tmp_path, "device-a")
    original = repository.local_records()[0]

    unchanged = repository.save_local([original])[0]
    changed_draft = dict(unchanged)
    changed_draft["tracks"] = [{"mode": "once", "buttons": ["A"], "hold_ms": 80}]
    changed = repository.save_local([changed_draft])[0]
    created = repository.save_local([changed, {"name": "dash", "tracks": []}])[1]

    assert unchanged["revision"] == 3
    assert changed["revision"] == 4
    assert changed["owner_device_id"] == "device-a"
    assert created["id"]
    assert created["revision"] == 1


def test_repository_creates_identity_free_draft_from_existing_record(tmp_path):
    repository = EventDefinitionRepository(tmp_path, "device-a")
    source = {
        "id": "stable",
        "name": "roll",
        "owner_device_id": "device-a",
        "revision": 3,
        "updated_at": "2026-09-18T00:00:00Z",
        "deleted": False,
        "content_hash": "hash",
        "tracks": [{"mode": "once", "buttons": ["B"], "hold_ms": 80}],
    }

    draft = repository.new_draft(source)
    draft["tracks"][0]["buttons"][0] = "A"

    assert draft["name"] == "roll"
    assert set(draft).isdisjoint({
        "id", "owner_device_id", "revision", "updated_at", "deleted", "content_hash",
    })
    assert source["tracks"][0]["buttons"] == ["B"]


def test_repository_resolves_shared_execution_key_by_identity_or_legacy_revision(tmp_path):
    _write(tmp_path / "events.json", [{
        "id": "stable",
        "name": "roll",
        "owner_device_id": "device-a",
        "revision": 3,
        "tracks": [],
    }])
    repository = EventDefinitionRepository(tmp_path, "device-a")

    assert repository.resolve_shared_key({
        "name": "roll",
        "eventId": "stable",
        "eventRevision": 3,
    }) == "stable"
    assert repository.resolve_shared_key({
        "name": "roll",
        "eventId": "stale",
        "eventRevision": 2,
    }) == "stable"
    assert repository.resolve_shared_key({
        "name": "roll",
        "eventId": "stale",
        "eventRevision": 4,
    }) is None


def test_repository_keeps_duplicate_names_isolated_by_stable_id(tmp_path):
    _write(tmp_path / "events.json", [{
        "id": "local",
        "name": "roll",
        "owner_device_id": "device-a",
        "revision": 1,
        "tracks": [],
    }])
    _write(tmp_path / "remote_events.json", [{
        "id": "remote",
        "name": "roll",
        "owner_device_id": "device-b",
        "revision": 1,
        "tracks": [],
    }])

    repository = EventDefinitionRepository(tmp_path, "device-a")

    definitions = repository.definitions()

    assert set(definitions) == {"local", "remote"}
    assert repository.local_key("roll") == "local"
