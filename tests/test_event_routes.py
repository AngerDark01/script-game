import json

import pytest

from auto_modules.core.events.automation.routes import (
    EventRoute,
    EventRouteRepository,
    EventRouter,
)


def test_repository_normalizes_legacy_labels_and_round_trips(tmp_path):
    records = [
        {
            "source": "本机",
            "trigger": "f6",
            "event": "roll",
            "target": "本机",
            "controller": "Controller 1 + 2",
        },
        {
            "source": "local",
            "trigger": "F7",
            "event": "dash",
            "target": "paired",
            "controller": "Controller 2",
        },
    ]
    (tmp_path / "routes.json").write_text(json.dumps(records), encoding="utf-8")
    repository = EventRouteRepository(tmp_path)

    routes = repository.load()

    assert routes[0] == EventRoute("local", "F6", "roll", "local", (1, 2))
    assert routes[1] == EventRoute("local", "F7", "dash", "paired", (2,))
    repository.save(routes)
    persisted = json.loads((tmp_path / "routes.json").read_text(encoding="utf-8"))
    assert persisted[0]["source"] == "本机"
    assert persisted[0]["controller"] == "Controller 1 + 2"
    assert persisted[1]["target"] == "已配对设备"


def test_router_emits_domain_dispatches_without_performing_io():
    router = EventRouter((
        EventRoute("local", "F6", "roll", "local", (1, 2)),
        EventRoute("local", "F6", "dash", "paired", (2,)),
        EventRoute("paired", "F6", "ignored", "local", (1,)),
    ))

    dispatches = router.dispatches("f6")

    assert [(item.event_name, item.controllers, item.remote) for item in dispatches] == [
        ("roll", (1, 2), False),
        ("dash", (2,), True),
    ]
    assert router.triggers() == ("F6",)


@pytest.mark.parametrize(
    "record,message",
    [
        ({"source": "local", "trigger": "", "event": "roll", "target": "local"}, "trigger"),
        ({"source": "local", "trigger": "F6", "event": "", "target": "local"}, "event"),
        ({"source": "unknown", "trigger": "F6", "event": "roll", "target": "local"}, "source"),
        ({"source": "local", "trigger": "F6", "event": "roll", "target": "unknown"}, "target"),
        ({"source": "local", "trigger": "F6", "event": "roll", "target": "local", "controller": "Controller 3"}, "controller"),
    ],
)
def test_route_rejects_invalid_records(record, message):
    with pytest.raises(ValueError, match=message):
        EventRoute.from_record(record)
