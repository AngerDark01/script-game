from auto_modules.features.poe2.live_terrain.experimental.diagnostics import (
    DiagnosticEvent,
    EventRecorder,
)


def test_event_recorder_keeps_bounded_history_and_serializes():
    recorder = EventRecorder(max_events=2)
    recorder.record(DiagnosticEvent("s", "one"))
    recorder.record(DiagnosticEvent("s", "two"))
    event = recorder.record(DiagnosticEvent("s", "three"))
    assert [item.kind for item in recorder.events] == ["two", "three"]
    assert event.as_dict()["session_id"] == "s"
