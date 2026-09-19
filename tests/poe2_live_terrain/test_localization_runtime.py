from auto_modules.core.localization import LocalizationResult, MapLocalizer, ObservationCandidate
from auto_modules.features.poe2.live_terrain.runtime import Poe2LocalizationRuntime


class FakeCapture:
    def __init__(self, value="frame"):
        self.value = value

    def capture(self):
        return self.value


def _runtime(candidates):
    calls = []
    localizer = MapLocalizer(
        global_match=lambda frame: calls.append("global") or ((100.0, 80.0), 0.9),
        local_match=lambda frame, origin: calls.append("local") or ((101.0, 80.0), 0.8),
        phase_predict=lambda previous, current: (100.0, 80.0),
    )
    runtime = Poe2LocalizationRuntime(
        capture=FakeCapture(),
        recognize=lambda frame, now: candidates,
        localizer=localizer,
    )
    return runtime, calls


def test_first_runtime_tick_reports_global_position_and_updates_trail():
    runtime, calls = _runtime([ObservationCandidate((12, 14), 0.9)])
    state = runtime.tick(now_ms=100)
    assert state.localization.source == "global"
    assert state.position == (100.0, 80.0)
    assert state.trajectory == ((100.0, 80.0),)
    assert calls == ["global"]


def test_failed_player_detection_does_not_append_center_fallback():
    runtime, calls = _runtime([])
    state = runtime.tick(now_ms=100)
    assert state.position is None
    assert state.trajectory == ()
    assert state.failure_reason == "player_not_detected"
    assert calls == []


def test_local_failure_is_reported_without_adding_a_stale_point():
    localizer = MapLocalizer(
        global_match=lambda frame: ((10.0, 10.0), 0.9),
        local_match=lambda frame, origin: None,
        phase_predict=lambda previous, current: (10.0, 10.0),
    )
    runtime = Poe2LocalizationRuntime(
        capture=FakeCapture(),
        recognize=lambda frame, now: [ObservationCandidate((5, 5), 0.9)],
        localizer=localizer,
    )
    assert runtime.tick(now_ms=1).position == (10.0, 10.0)
    failed = runtime.tick(now_ms=2)
    assert failed.position is None
    assert failed.latest_confirmed_position == (10.0, 10.0)
    assert failed.trajectory == ((10.0, 10.0),)
