from types import SimpleNamespace

import numpy as np
import pytest

from auto_modules.core.localization import LocalizationResult
from auto_modules.features.poe2.live_terrain.capture_samples import CaptureEvidence
from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.controller import (
    HybridLocalizationController,
)
from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.models import (
    AbsoluteRegistration,
    HybridLocalizationMode,
    PositionAnchor,
    SimilarityTransform2D,
)
from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.session import (
    Poe2HybridLocalizationSession,
)
from auto_modules.features.poe2.live_terrain.hybrid_product_runtime import (
    Poe2HybridProductRuntime,
)


AREA = "MapTest:A1"


class FakeSession:
    def __init__(self, result):
        self.result = result
        self.events = []
        self.last_raw_frame = np.full((4, 5, 3), 7, dtype=np.uint8)
        self.last_evidence = SimpleNamespace(
            processed=np.full((4, 5, 3), 9, dtype=np.uint8),
            wall_mask=np.full((4, 5), 255, dtype=np.uint8),
        )
        self.last_frame = SimpleNamespace(local_player=(2.0, 3.0))

    def start(self):
        self.events.append("start")

    def stop(self):
        self.events.append("stop")

    def tick(self, *, now_ms=None):
        self.events.append(("tick", now_ms))
        return self.result

    def retry_recovery(self):
        self.events.append("retry")


class SequencedFactory:
    def __init__(self, *experiments):
        self.experiments = list(experiments)
        self.snapshots = []
        self.providers = []

    def __call__(self, snapshot, config_provider):
        self.snapshots.append(snapshot)
        self.providers.append(config_provider)
        return self.experiments.pop(0)


def hybrid_state(*, mode="local_tracking", source="visual_local", reason=""):
    return SimpleNamespace(
        mode=mode,
        position=(12.0, 18.0),
        latest_confirmed_position=(12.0, 18.0),
        trajectory=((10.0, 16.0), (12.0, 18.0)),
        registration=None,
        source=source,
        confidence=0.91,
        reason=reason,
        recovery_revision=2,
        diagnostics={"reason": reason},
    )


def experiment(session, *, read_count=1):
    return SimpleNamespace(
        session=session,
        anchor_provider=SimpleNamespace(read_count=read_count),
    )


class RecordingLogger:
    def __init__(self):
        self.info_calls = []
        self.warning_calls = []
        self.exception_calls = []

    def info(self, message, *args):
        self.info_calls.append((message, args))

    def warning(self, message, *args):
        self.warning_calls.append((message, args))

    def exception(self, message, *args):
        self.exception_calls.append((message, args))


class FailureRecorder:
    def __init__(self):
        self.calls = []

    def record(self, *, experiment, state, snapshot):
        self.calls.append((experiment, state, snapshot))
        return "failure-dir"


def registration(position, source):
    return AbsoluteRegistration(
        result=LocalizationResult(position, 0.9, source=source),
        transform=SimilarityTransform2D(45.0, True, 1.2, (20.0, 30.0)),
        anchor_error=1.0,
        area_instance=AREA,
    )


class Anchors:
    def __init__(self):
        self.read_count = 0

    def read_once(self, expected_instance_id):
        self.read_count += 1
        return PositionAnchor((20.0, 30.0), expected_instance_id, self.read_count, "memory")


class Registrar:
    last_diagnostics = {}

    def __init__(self, results):
        self.results = list(results)

    def register(self, frame, *, reference, anchor, prior=None):
        del frame, reference, anchor, prior
        return self.results.pop(0)


class Tracker:
    def __init__(self, results):
        self.results = list(results)

    def track(self, frame, *, reference, previous_frame, previous):
        del frame, reference, previous_frame, previous
        return self.results.pop(0)


class FrameSource:
    def __init__(self):
        self.captures = 0

    def capture(self, config):
        del config
        self.captures += 1
        return np.full((20, 30, 3), self.captures, dtype=np.uint8)


class EvidenceBuilder:
    def build(self, raw, config):
        del config
        mask = np.zeros(raw.shape[:2], dtype=np.uint8)
        mask[4:8, 6:20] = 255
        return CaptureEvidence(
            captured_at="2026-09-22T00:00:00+00:00",
            raw=raw,
            processed=raw,
            feature=mask,
            wall_mask=mask,
            monitor_config={"binding": {"player_marker_position": [15, 10]}},
        )


def hybrid_runtime(*, registrar_results, tracker_results):
    anchors = Anchors()
    controller = HybridLocalizationController(
        expected_instance_id=AREA,
        reference=object(),
        anchor_provider=anchors,
        absolute_registrar=Registrar(registrar_results),
        local_tracker=Tracker(tracker_results),
    )
    session = Poe2HybridLocalizationSession(
        frame_source=FrameSource(),
        evidence_builder=EvidenceBuilder(),
        config_provider=lambda: object(),
        controller=controller,
        clock_ms=lambda: 1234,
    )
    value = Poe2HybridProductRuntime(
        lambda snapshot, config_provider: SimpleNamespace(
            session=session,
            controller=controller,
            anchor_provider=anchors,
        ),
        initial_config=object(),
    )
    value.configure_snapshot(object())
    value.start()
    return value, anchors


def test_runtime_requires_snapshot_before_start():
    runtime = Poe2HybridProductRuntime(
        lambda snapshot, config_provider: None,
        initial_config=object(),
    )

    with pytest.raises(RuntimeError, match="请先获取当前地图"):
        runtime.start()


def test_configure_snapshot_builds_experiment_and_tick_adapts_visual_state():
    config = object()
    state = hybrid_state()
    session = FakeSession(state)
    factory = SequencedFactory(experiment(session, read_count=1))
    runtime = Poe2HybridProductRuntime(factory, initial_config=config)
    snapshot = object()

    runtime.configure_snapshot(snapshot)
    runtime.start()
    result = runtime.tick(now_ms=123)

    assert factory.snapshots == [snapshot]
    assert factory.providers[0]() is config
    assert session.events == ["start", ("tick", 123)]
    assert result.position == state.position
    assert result.local_position == (2.0, 3.0)
    assert result.memory_read_count == 1
    assert result.raw_frame is session.last_raw_frame
    assert result.processed_frame is session.last_evidence.processed
    assert result.match_mask is session.last_evidence.wall_mask


def test_replacing_snapshot_stops_previous_session():
    first = FakeSession(hybrid_state())
    second = FakeSession(hybrid_state())
    runtime = Poe2HybridProductRuntime(
        SequencedFactory(experiment(first), experiment(second)),
        initial_config=object(),
    )

    runtime.configure_snapshot(object())
    runtime.start()
    runtime.configure_snapshot(object())

    assert first.events == ["start", "stop"]
    assert second.events == []


def test_retry_recovery_delegates_without_starting_memory_polling():
    session = FakeSession(hybrid_state(mode="recovery_required"))
    runtime = Poe2HybridProductRuntime(
        SequencedFactory(experiment(session, read_count=2)),
        initial_config=object(),
    )
    runtime.configure_snapshot(object())

    runtime.retry_recovery()

    assert session.events == ["retry"]


def test_visual_loss_triggers_one_automatic_absolute_recovery_on_next_tick():
    runtime, anchors = hybrid_runtime(
        registrar_results=[
            registration((20.0, 30.0), "anchored_absolute"),
            registration((22.0, 32.0), "anchored_absolute"),
        ],
        tracker_results=[
            registration((21.0, 31.0), "visual_local"),
            None,
            registration((23.0, 33.0), "visual_local"),
        ],
    )

    states = [runtime.tick() for _ in range(5)]

    assert [state.source for state in states] == [
        "anchored_absolute",
        "visual_local",
        "failed",
        "anchored_absolute",
        "visual_local",
    ]
    assert states[2].mode is HybridLocalizationMode.RECOVERY_PENDING
    assert states[3].mode is HybridLocalizationMode.LOCAL_TRACKING
    assert anchors.read_count == 2


def test_failed_automatic_recovery_does_not_poll_memory_again():
    runtime, anchors = hybrid_runtime(
        registrar_results=[registration((20.0, 30.0), "anchored_absolute"), None],
        tracker_results=[None],
    )

    runtime.tick()
    lost = runtime.tick()
    failed = runtime.tick()
    held = [runtime.tick() for _ in range(5)]

    assert lost.mode is HybridLocalizationMode.RECOVERY_PENDING
    assert failed.mode is HybridLocalizationMode.RECOVERY_REQUIRED
    assert all(state.mode is HybridLocalizationMode.RECOVERY_REQUIRED for state in held)
    assert anchors.read_count == 2


def test_repeated_failure_state_is_logged_and_archived_once():
    logger = RecordingLogger()
    recorder = FailureRecorder()
    state = hybrid_state(
        mode="recovery_required",
        source="failed",
        reason="absolute_registration_failed",
    )
    session = FakeSession(state)
    runtime = Poe2HybridProductRuntime(
        SequencedFactory(experiment(session, read_count=2)),
        initial_config=object(),
        logger=logger,
        failure_recorder=recorder,
    )
    snapshot = object()
    runtime.configure_snapshot(snapshot)
    runtime.start()

    runtime.tick()
    runtime.tick()

    state_warnings = [call for call in logger.warning_calls if "state_changed" in call[0]]
    assert len(state_warnings) == 1
    assert len(recorder.calls) == 1
    assert recorder.calls[0][2] is snapshot
