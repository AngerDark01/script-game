from auto_modules.core.localization import LocalizationResult, MapLocalizer, ObservationCandidate
from auto_modules.core.spatial.monitor_binding import CaptureRect, MonitorBinding
from auto_modules.features.poe2.live_terrain.runtime import (
    HSVPlayerObservationRecognizer,
    Poe2LocalizationRuntime,
)
from auto_modules.features.poe2.live_terrain.monitor_config import Poe2MonitorConfig


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


def test_center_mode_uses_configured_marker_without_calling_recognizer():
    calls = []

    class FailingRecognizer:
        def __call__(self, *_args):
            calls.append("recognizer")
            raise AssertionError("center mode must not invoke image recognition")

    localizer = MapLocalizer(
        global_match=lambda frame: calls.append(("global", frame.selected.local_position))
        or ((100.0, 80.0), 0.9),
        local_match=lambda frame, origin: ((101.0, 80.0), 0.8),
    )
    runtime = Poe2LocalizationRuntime(
        capture=FakeCapture(),
        recognize=FailingRecognizer(),
        localizer=localizer,
    )
    runtime.configure_monitor(
        Poe2MonitorConfig(
            binding=MonitorBinding(
                rect=CaptureRect(0, 0, 320, 320),
                player_marker_position=(160, 160),
            ),
            selection_mode="center",
        )
    )

    state = runtime.tick(now_ms=100)

    assert state.position == (100.0, 80.0)
    assert state.local_position == (160, 160)
    assert state.observation.source == "configured-center"
    assert state.recognition_diagnostics["reason"] == "center_configured"
    assert calls == [("global", (160, 160))]


def test_failed_player_detection_does_not_append_center_fallback():
    runtime, calls = _runtime([])
    state = runtime.tick(now_ms=100)
    assert state.position is None
    assert state.trajectory == ()
    assert state.failure_reason == "player_not_detected"
    assert state.recognition_diagnostics["reason"] == "no_contour"
    assert calls == []


def test_failed_player_detection_still_publishes_visual_calibration_evidence():
    import numpy as np

    class Vision:
        player_hsv_min = np.array([40, 100, 100])
        player_hsv_max = np.array([80, 255, 255])

        def extract_player(self, frame):
            return np.zeros((4, 4), dtype=np.uint8)

        def preprocess_image(self, frame):
            return np.asarray(frame) + 2

        def extract_combined(self, frame, player_pos=None):
            assert player_pos is None
            match = np.array([[0, 60], [20, 0]], dtype=np.uint8)
            wall = np.array([[0, 255], [0, 0]], dtype=np.uint8)
            fog = np.zeros((2, 2), dtype=np.uint8)
            return match, wall, fog

    localizer_calls = []
    runtime = Poe2LocalizationRuntime(
        capture=FakeCapture(np.zeros((2, 2, 3), dtype=np.uint8)),
        recognize=HSVPlayerObservationRecognizer(Vision()),
        localizer=MapLocalizer(
            global_match=lambda frame: localizer_calls.append(frame),
            local_match=lambda frame, origin: None,
        ),
    )

    state = runtime.tick(now_ms=100)

    assert state.failure_reason == "player_not_detected"
    assert np.array_equal(state.processed_frame, np.full((2, 2, 3), 2, dtype=np.uint8))
    assert np.array_equal(state.match_mask, np.array([[0, 60], [20, 0]], dtype=np.uint8))
    assert localizer_calls == []


def test_small_player_contour_is_reported_as_below_confidence():
    import numpy as np

    class SmallMaskRecognizer:
        player_hsv_min = np.array([40, 100, 100])
        player_hsv_max = np.array([80, 255, 255])

        def extract_player(self, frame):
            mask = np.zeros((12, 12), dtype=np.uint8)
            mask[4:7, 4:7] = 255
            return mask

    recognizer = HSVPlayerObservationRecognizer(SmallMaskRecognizer(), min_area=3)
    runtime, calls = _runtime([])
    runtime.recognizer = recognizer
    state = runtime.tick(now_ms=100)

    assert state.position is None
    assert state.recognition_diagnostics["candidate_count"] == 1
    assert state.recognition_diagnostics["accepted_count"] == 0
    assert state.recognition_diagnostics["reason"] == "below_confidence"
    assert state.recognition_diagnostics["max_area"] == 4.0
    assert calls == []


def test_poe2_runtime_accepts_one_small_but_valid_player_marker():
    import numpy as np

    class PlayerMaskRecognizer:
        player_hsv_min = np.array([5, 234, 235])
        player_hsv_max = np.array([15, 255, 255])

        def extract_player(self, frame):
            mask = np.zeros((12, 12), dtype=np.uint8)
            mask[4:8, 4:8] = 255
            return mask

    recognizer = HSVPlayerObservationRecognizer(PlayerMaskRecognizer(), min_area=3)
    runtime, calls = _runtime([])
    runtime.recognizer = recognizer
    state = runtime.tick(now_ms=100)

    assert state.position == (100.0, 80.0)
    assert state.recognition_diagnostics["max_confidence"] == 0.64
    assert calls == ["global"]


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


def test_center_mode_builds_mapping_compatible_combined_visual_evidence():
    import numpy as np

    class CombinedVision:
        def __init__(self):
            self.params = {}
            self.calls = []

        def set_params(self, params):
            self.params.update(params)

        def get_params(self):
            return dict(self.params)

        def preprocess_image(self, frame):
            return np.asarray(frame) + 1

        def extract_combined(self, frame, player_pos=None):
            self.calls.append(player_pos)
            match = np.array([[0, 70], [30, 0]], dtype=np.uint8)
            wall = np.array([[0, 255], [0, 0]], dtype=np.uint8)
            fog = np.array([[0, 0], [255, 0]], dtype=np.uint8)
            return match, wall, fog

    vision = CombinedVision()
    observed = []
    localizer = MapLocalizer(
        global_match=lambda frame: observed.append(frame.visual) or ((3.0, 4.0), 0.9),
        local_match=lambda frame, origin: ((3.0, 4.0), 0.9),
    )
    runtime = Poe2LocalizationRuntime(
        capture=FakeCapture(np.zeros((2, 2, 3), dtype=np.uint8)),
        recognize=HSVPlayerObservationRecognizer(vision),
        localizer=localizer,
    )
    runtime.configure_monitor(
        Poe2MonitorConfig(
            binding=MonitorBinding(
                rect=CaptureRect(0, 0, 2, 2),
                player_marker_position=(1, 1),
            ),
            selection_mode="center",
            recognizer_params={"edge_low": 35},
        )
    )

    state = runtime.tick(now_ms=100)

    assert vision.params == {"edge_low": 35}
    assert vision.calls == [(1, 1)]
    assert observed[0] is not None
    assert np.array_equal(state.processed_frame, np.ones((2, 2, 3), dtype=np.uint8))
    assert np.array_equal(state.match_mask, np.array([[0, 70], [30, 0]], dtype=np.uint8))


def test_empty_profile_restores_dedicated_recognizer_defaults():
    class Vision:
        def __init__(self):
            self.params = {"edge_low": 50, "edge_high": 150}

        def get_params(self):
            return dict(self.params)

        def set_params(self, params):
            self.params = dict(params)

    vision = Vision()
    runtime = Poe2LocalizationRuntime(
        capture=FakeCapture(),
        recognize=HSVPlayerObservationRecognizer(vision),
    )

    runtime.configure_monitor(Poe2MonitorConfig(recognizer_params={"edge_low": 25}))
    assert vision.params == {"edge_low": 25}

    runtime.configure_monitor(Poe2MonitorConfig(recognizer_params={}))
    assert vision.params == {"edge_low": 50, "edge_high": 150}


def test_preview_capture_accepts_unsaved_monitor_config():
    expected = object()
    seen = []
    runtime = Poe2LocalizationRuntime(
        capture=FakeCapture("active-profile"),
        preview_capture=lambda config: seen.append(config) or expected,
    )
    config = Poe2MonitorConfig()

    assert runtime.capture_preview(config) is expected
    assert seen == [config]
