from __future__ import annotations

import cv2
import multiprocessing as mp
import numpy as np
import pytest
import time

from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.models import (
    SimilarityTransform2D,
)
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.contracts import (
    ObservationSource,
)
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.vision.capture_adapter import (
    CapturedFrame,
)
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.vision.dual_observation_processor import (
    DualObservationProcessor,
)
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.vision.vision_process import (
    VisionProcessHandle,
)


def _frame(sequence: int, *, shift_x: int = 0, markers: bool = True, generation: int = 1, instance: str = "map-a") -> CapturedFrame:
    image = np.zeros((120, 120, 3), dtype=np.uint8)
    cv2.rectangle(image, (8 + shift_x, 8), (108 + shift_x, 108), (255, 255, 255), 2)
    if markers:
        cv2.circle(image, (30 + shift_x, 40), 3, (0, 0, 255), -1)
        cv2.circle(image, (82 + shift_x, 72), 3, (0, 255, 255), -1)
    ok, encoded = cv2.imencode(".png", image)
    assert ok
    return CapturedFrame(generation, sequence, sequence * 33, instance, encoded.tobytes())


def _processor() -> DualObservationProcessor:
    return DualObservationProcessor(
        generation=1,
        map_instance="map-a",
        role_ids=("p1", "p2"),
        initial_positions_native={"p1": (30.0, 40.0), "p2": (82.0, 72.0)},
        max_candidates=6,
    )


def test_confirmed_far_visual_corrects_control_target_without_learning_jump_speed():
    from auto_modules.features.poe2.live_terrain.experimental.follow_engine.control.follow_control_process import FollowControlRuntime
    from auto_modules.features.poe2.live_terrain.experimental.follow_engine.generation import GenerationToken
    from auto_modules.features.poe2.live_terrain.experimental.follow_engine.contracts import VisualObservation
    processor = _processor()
    processor.process(_frame(0))
    diagnostics = {"confirmed_roles": ("p1",), "gates": {"p1": 45}}
    roles, _ = processor._build_roles(1000, {"p1": (100, 40)}, diagnostics,
        {"p1": (30, 40), "p2": (82, 72)}, None, (120, 120))
    assert roles["p1"].confidence >= 0.85
    assert roles["p1"].velocity_native == (0, 0)
    runtime = FollowControlRuntime(GenerationToken(1, "map-a"), {"p2": 2},
        observation_role_ids=("p1", "p2"), live_target_source="p1", live_target_roles=("p2",))
    runtime.seed_position("p1", (30, 40), captured_at_ms=900)
    runtime.seed_position("p2", (82, 72), captured_at_ms=900)
    speed = runtime._roles["p1"].speed_calibrator.speed
    runtime.apply_visual(VisualObservation(1, 1, 1000, "map-a", roles, association_diagnostics=diagnostics))
    assert runtime._roles["p1"].state.position_native == (100, 40)
    assert runtime._roles["p2"].target == (100, 40)
    assert runtime._roles["p1"].speed_calibrator.speed == speed

    # A first-frame pending candidate must not bypass confirmation via ROI.
    from dataclasses import replace
    pending = VisualObservation(1, 2, 1033, "map-a", {key: replace(value, visible=False) for key, value in roles.items()},
        association_diagnostics={"pending_roles": ("p1",)})
    runtime.apply_visual(pending)
    runtime._latest_frame = object()
    runtime.local_search = lambda *args: (_ for _ in ()).throw(AssertionError("ROI bypassed confirmation"))
    runtime.local_recovery = type("Backend", (), {"match": lambda _, frame, point, search: search(frame, point, 80)})()
    assert runtime._run_local_recovery("p1", now_ms=1033) == (False, 0.0)


def test_composes_first_frame_into_native_dual_observation():
    result = _processor().process(_frame(1))

    assert result.source is ObservationSource.VISUAL
    assert set(result.roles) == {"p1", "p2"}
    assert all(item.visible for item in result.roles.values())
    assert result.roles["p1"].position_native == pytest.approx((30.0, 40.0), abs=2.0)
    assert result.roles["p2"].position_native == pytest.approx((82.0, 72.0), abs=2.0)
    assert result.timing.total_ms >= result.timing.marker_ms >= 0.0
    assert result.timing.wall_ms >= 0.0


def test_wall_shift_and_marker_motion_are_processed_without_re_registration():
    processor = _processor()
    first = processor.process(_frame(1))
    second = processor.process(_frame(2, shift_x=2))

    assert first.source is ObservationSource.VISUAL
    assert second.source is ObservationSource.VISUAL
    assert second.wall_shift is not None
    assert second.roles["p1"].visible is True
    assert second.roles["p2"].visible is True


def test_observation_carries_latest_transform_for_worker_handover():
    initial = SimilarityTransform2D(0.0, False, 1.0, (10.0, 20.0))
    processor = DualObservationProcessor(
        generation=1,
        map_instance="map-a",
        role_ids=("p1", "p2"),
        initial_positions_native={"p1": (30.0, 40.0), "p2": (82.0, 72.0)},
        transform=initial,
    )

    first = processor.process(_frame(1))
    second = processor.process(_frame(2, shift_x=2))

    assert first.transform == initial
    assert second.transform == processor._transform
    assert second.transform is not initial


def test_missing_markers_is_degraded_observation_and_retains_last_position():
    processor = _processor()
    processor.process(_frame(1))
    result = processor.process(_frame(2, markers=False))

    assert result.source is ObservationSource.NONE
    assert all(not item.visible for item in result.roles.values())
    assert result.roles["p1"].position_native == pytest.approx((30.0, 40.0), abs=2.0)
    assert result.roles["p2"].position_native == pytest.approx((82.0, 72.0), abs=2.0)
    assert all(item.uncertainty_native > 0.0 for item in result.roles.values())


def test_generation_map_and_sequence_are_strictly_gated():
    processor = _processor()
    processor.process(_frame(1))
    with pytest.raises(ValueError, match="generation or map instance"):
        processor.process(_frame(2, generation=2))
    with pytest.raises(ValueError, match="strictly increasing"):
        processor.process(_frame(1))


def test_malformed_payload_is_rejected_at_vision_boundary():
    processor = _processor()
    bad = CapturedFrame(1, 1, 33, "map-a", b"not-an-image")
    with pytest.raises(ValueError, match="decodable color image"):
        processor.process(bad)


class _EncodedImageCapture:
    def __init__(self):
        self.sequence = 0
        frame = _frame(1)
        self.payload = frame.payload

    def capture(self):
        self.sequence += 1
        return CapturedFrame(1, self.sequence, self.sequence * 33, "map-a", self.payload)


def test_real_processor_composes_inside_spawned_vision_process():
    handle = VisionProcessHandle(
        _EncodedImageCapture(),
        _processor(),
        interval_ms=10,
        context=mp.get_context("spawn"),
    )
    handle.start(generation=1, map_instance="map-a")
    deadline = time.monotonic() + 5.0
    event = None
    while time.monotonic() < deadline and event is None:
        candidate = handle.poll_latest()
        if candidate is not None and candidate.kind == "observation":
            event = candidate
        time.sleep(0.01)
    try:
        assert event is not None
        assert event.observation is not None
        assert event.observation.source is ObservationSource.VISUAL
        assert set(event.observation.roles) == {"p1", "p2"}
    finally:
        handle.stop()
