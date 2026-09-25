import numpy as np
import pytest

from auto_modules.core.localization import LocalizationResult
from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.controller import (
    HybridLocalizationController,
)
from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.models import (
    AbsoluteRegistration,
    HybridFrame,
    HybridLocalizationMode,
    PositionAnchor,
    SimilarityTransform2D,
)


AREA = "Map:A1"


def make_frame(frame_id: int) -> HybridFrame:
    return HybridFrame(
        frame_id=frame_id,
        captured_at_ms=frame_id * 100,
        wall_mask=np.array([[0, 255], [255, 0]], dtype=np.uint8),
        local_player=(1.0, 1.0),
    )


def make_registration(position=(10.0, 20.0), source="anchored_absolute"):
    return AbsoluteRegistration(
        result=LocalizationResult(position, 0.9, source=source),
        transform=SimilarityTransform2D(45.0, False, 1.0, (9.0, 19.0)),
        anchor_error=0.5,
        area_instance=AREA,
    )


class AnchorFake:
    def __init__(self, *, error=None):
        self.error = error
        self.reads = 0

    def read_once(self, expected_instance_id):
        self.reads += 1
        if self.error is not None:
            raise self.error
        return PositionAnchor((10.0, 20.0), expected_instance_id, 100, "memory")


class RegistrarFake:
    def __init__(self, results, diagnostics=None):
        self.results = list(results)
        self.calls = []
        self.last_diagnostics = dict(diagnostics or {})

    def register(self, frame, *, reference, anchor, prior=None):
        self.calls.append((frame, reference, anchor, prior))
        return self.results.pop(0) if self.results else None


class TrackerFake:
    def __init__(self, results=()):
        self.results = list(results)
        self.calls = []

    def track(self, frame, *, reference, previous_frame, previous):
        self.calls.append((frame, reference, previous_frame, previous))
        return self.results.pop(0) if self.results else None


def make_controller(*, registrar_results, tracker_results=(), provider=None, registrar_diagnostics=None):
    provider = provider or AnchorFake()
    registrar = RegistrarFake(registrar_results, registrar_diagnostics)
    tracker = TrackerFake(tracker_results)
    controller = HybridLocalizationController(
        expected_instance_id=AREA,
        reference=object(),
        anchor_provider=provider,
        absolute_registrar=registrar,
        local_tracker=tracker,
    )
    return controller, provider, registrar, tracker


def test_first_update_reads_one_anchor_and_accepts_absolute():
    registration = make_registration()
    controller, provider, registrar, _ = make_controller(registrar_results=[registration])

    state = controller.update(make_frame(1))

    assert state.mode is HybridLocalizationMode.LOCAL_TRACKING
    assert state.position == registration.result.position
    assert state.latest_confirmed_position == registration.result.position
    assert state.trajectory == (registration.result.position,)
    assert state.recovery_revision == 1
    assert provider.reads == 1
    assert registrar.calls[0][3] is None


def test_prepare_capture_reads_anchor_before_frame_and_update_reuses_it():
    registration = make_registration()
    controller, provider, registrar, _ = make_controller(registrar_results=[registration])

    prepared = controller.prepare_capture()
    state = controller.update(make_frame(1))

    assert prepared is None
    assert state.mode is HybridLocalizationMode.LOCAL_TRACKING
    assert provider.reads == 1
    assert registrar.calls[0][2].position == (10.0, 20.0)


def test_local_success_then_failure_does_not_append_a_stale_point():
    first = make_registration()
    local = make_registration((11.0, 21.0), source="visual_local")
    controller, provider, _, tracker = make_controller(
        registrar_results=[first],
        tracker_results=[local, None],
    )

    controller.update(make_frame(1))
    second = controller.update(make_frame(2))
    failed = controller.update(make_frame(3))

    assert second.position == (11.0, 21.0)
    assert failed.mode is HybridLocalizationMode.RECOVERY_PENDING
    assert failed.position is None
    assert failed.latest_confirmed_position == (11.0, 21.0)
    assert failed.trajectory == ((10.0, 20.0), (11.0, 21.0))
    assert failed.reason == "local_tracking_failed"
    assert provider.reads == 1
    assert tracker.calls[0][2].frame_id == 1


def test_failed_recovery_does_not_read_again_until_explicit_retry():
    first = make_registration()
    controller, provider, registrar, _ = make_controller(
        registrar_results=[first, None, None],
        tracker_results=[None],
    )

    controller.update(make_frame(1))
    controller.update(make_frame(2))
    failed = controller.update(make_frame(3))
    held = [controller.update(make_frame(frame_id)) for frame_id in (4, 5, 6)]

    assert failed.mode is HybridLocalizationMode.RECOVERY_REQUIRED
    assert provider.reads == 2
    assert len(registrar.calls) == 2
    assert all(state.reason == "recovery_required" for state in held)

    controller.retry_recovery()
    retried = controller.update(make_frame(7))

    assert retried.mode is HybridLocalizationMode.RECOVERY_REQUIRED
    assert provider.reads == 3
    assert len(registrar.calls) == 3


def test_anchor_read_error_becomes_a_failed_one_shot_recovery():
    provider = AnchorFake(error=RuntimeError("read failed"))
    controller, _, registrar, tracker = make_controller(
        registrar_results=[],
        provider=provider,
    )

    state = controller.update(make_frame(1))

    assert state.mode is HybridLocalizationMode.RECOVERY_REQUIRED
    assert state.position is None
    assert state.reason == "anchor_read_failed"
    assert state.diagnostics["error"] == "read failed"
    assert provider.reads == 1
    assert not registrar.calls
    assert not tracker.calls


def test_absolute_failure_publishes_registrar_diagnostics():
    controller, _, _, _ = make_controller(
        registrar_results=[None],
        registrar_diagnostics={
            "status": "rejected",
            "reason": "best candidate score is below the anchored threshold",
            "best_score": 0.244,
            "best_angle": 327.0,
        },
    )

    state = controller.update(make_frame(1))

    assert state.reason == "absolute_registration_failed"
    assert state.diagnostics["status"] == "rejected"
    assert state.diagnostics["best_score"] == 0.244
    assert state.diagnostics["best_angle"] == 327.0


def test_stop_prevents_all_dependencies_from_being_called():
    controller, provider, registrar, tracker = make_controller(
        registrar_results=[make_registration()],
    )
    controller.stop()

    state = controller.update(make_frame(1))

    assert state.mode is HybridLocalizationMode.STOPPED
    assert state.reason == "stopped"
    assert provider.reads == 0
    assert not registrar.calls
    assert not tracker.calls
    with pytest.raises(RuntimeError, match="failed attempt"):
        controller.retry_recovery()
