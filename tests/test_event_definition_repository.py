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

    assert definitions["roll"].tracks[0].buttons == ("B",)
    assert definitions["dash"].tracks[0].mode is TrackMode.CONTINUOUS
    assert definitions["dash"].owner_device_id == "device-b"


def test_repository_catalog_and_lookup_share_stable_identity(tmp_path):
    _write(tmp_path / "events.json", [{"name": "roll", "tracks": []}])
    repository = EventDefinitionRepository(tmp_path, "device-a")

    payload = repository.catalog_payload()
    record = repository.by_name("roll")

    assert record is not None
    assert payload["definitions"][0]["id"] == record["id"]
    assert payload["deviceId"] == "device-a"


def test_repository_resolves_legacy_shared_identity_by_revision(tmp_path):
    _write(tmp_path / "events.json", [{
        "id": "stable",
        "name": "roll",
        "owner_device_id": "device-a",
        "revision": 3,
        "tracks": [],
    }])
    repository = EventDefinitionRepository(tmp_path, "device-a")

    assert repository.resolve_shared_name({
        "name": "roll",
        "eventId": "stale",
        "eventRevision": 2,
    }) == "roll"
    assert repository.resolve_shared_name({
        "name": "roll",
        "eventId": "stale",
        "eventRevision": 4,
    }) is None


def test_repository_rejects_duplicate_visible_names(tmp_path):
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

    try:
        repository.definitions()
    except ValueError as exc:
        assert "duplicate event name" in str(exc)
    else:
        raise AssertionError("duplicate names must not silently replace definitions")
