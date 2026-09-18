from core.events.automation.definitions import parse_event_definition
from core.events.automation.execution import EventExecutionRuntime


def _definition(name, button, hold_ms=100):
    return parse_event_definition({
        "id": name,
        "name": name,
        "owner_device_id": "local",
        "revision": 1,
        "tracks": [{"mode": "once", "buttons": [button], "hold_ms": hold_ms}],
    })


def _frames_by_key(frames):
    return {(frame.source, frame.controller): frame.state for frame in frames}


def test_local_and_remote_dispatch_share_one_runtime_but_keep_sources_separate():
    now = [1000]
    runtime = EventExecutionRuntime(
        {"roll": _definition("roll", "B")},
        clock_ms=lambda: now[0],
    )

    assert runtime.start("event:local", "roll", (1,))
    assert runtime.start("event:remote", "roll", (2,))
    states = _frames_by_key(runtime.tick())

    assert states[("event:local", 1)]["buttons"] == 0x2000
    assert states[("event:remote", 2)]["buttons"] == 0x2000
    assert ("event:local", 2) not in states
    assert ("event:remote", 1) not in states


def test_replacing_definitions_does_not_mutate_an_active_lifecycle():
    now = [0]
    runtime = EventExecutionRuntime(
        {"skill": _definition("skill", "B", hold_ms=100)},
        clock_ms=lambda: now[0],
    )
    runtime.start("local", "skill", (1,))
    runtime.replace_definitions({"skill": _definition("skill", "A", hold_ms=100)})

    active = _frames_by_key(runtime.tick())[("event:local", 1)]
    assert active["buttons"] == 0x2000

    now[0] = 150
    assert _frames_by_key(runtime.tick())[("event:local", 1)]["buttons"] == 0
    runtime.start("local", "skill", (1,))
    assert _frames_by_key(runtime.tick())[("event:local", 1)]["buttons"] == 0x1000


def test_cancel_source_preserves_other_sources_and_emits_neutral_frame():
    runtime = EventExecutionRuntime(
        {"roll": _definition("roll", "B")},
        clock_ms=lambda: 0,
    )
    runtime.start("local", "roll", (1,))
    runtime.start("remote", "roll", (1,))

    neutralized = runtime.cancel_source("remote")
    states = _frames_by_key(runtime.tick())

    assert [(frame.source, frame.controller, frame.state["buttons"]) for frame in neutralized] == [
        ("event:remote", 1, 0),
    ]
    assert states[("event:local", 1)]["buttons"] == 0x2000
    assert ("event:remote", 1) not in states


def test_invalid_controller_and_unknown_definition_are_rejected():
    runtime = EventExecutionRuntime({}, clock_ms=lambda: 0)

    assert not runtime.start("local", "missing", (1,))
    try:
        runtime.start("local", "missing", (3,))
    except ValueError as exc:
        assert "controller" in str(exc)
    else:
        raise AssertionError("invalid controller must be rejected")
