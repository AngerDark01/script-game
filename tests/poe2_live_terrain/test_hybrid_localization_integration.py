import numpy as np

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


def frame(value: int) -> HybridFrame:
    mask = np.zeros((12, 12), dtype=np.uint8)
    mask[2:10, 5] = 255
    return HybridFrame(value, value * 100, mask, (6.0, 6.0))


def registration(position, source):
    return AbsoluteRegistration(
        result=LocalizationResult(position, 0.9, source=source),
        transform=SimilarityTransform2D(45.0, True, 1.2, (20.0, 30.0)),
        anchor_error=1.0,
        area_instance=AREA,
    )


class Anchors:
    def __init__(self):
        self.reads = 0

    def read_once(self, expected_instance_id):
        self.reads += 1
        return PositionAnchor((20.0, 30.0), expected_instance_id, self.reads, "memory")


class Registrar:
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


def controller(*, registrar_results, tracker_results):
    anchors = Anchors()
    value = HybridLocalizationController(
        expected_instance_id=AREA,
        reference=object(),
        anchor_provider=anchors,
        absolute_registrar=Registrar(registrar_results),
        local_tracker=Tracker(tracker_results),
    )
    return value, anchors


def test_full_hybrid_lifecycle_reads_memory_only_for_absolute_events():
    value, anchors = controller(
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

    states = [value.update(frame(index)) for index in range(1, 6)]

    assert [state.source for state in states] == [
        "anchored_absolute",
        "visual_local",
        "failed",
        "anchored_absolute",
        "visual_local",
    ]
    assert states[2].mode is HybridLocalizationMode.RECOVERY_PENDING
    assert states[2].position is None
    assert states[-1].trajectory == (
        (20.0, 30.0),
        (21.0, 31.0),
        (22.0, 32.0),
        (23.0, 33.0),
    )
    assert anchors.reads == 2


def test_failed_recovery_stays_fenced_across_ten_frames_until_retry():
    value, anchors = controller(
        registrar_results=[registration((20.0, 30.0), "anchored_absolute"), None, None],
        tracker_results=[None],
    )
    value.update(frame(1))
    value.update(frame(2))
    failed = value.update(frame(3))

    held = [value.update(frame(index)) for index in range(4, 14)]

    assert failed.mode is HybridLocalizationMode.RECOVERY_REQUIRED
    assert anchors.reads == 2
    assert all(item.position is None for item in held)
    assert all(item.reason == "recovery_required" for item in held)

    value.retry_recovery()
    value.update(frame(14))
    assert anchors.reads == 3
