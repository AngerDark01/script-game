from types import SimpleNamespace

import numpy as np

from auto_modules.core.localization import LocalizationResult
from auto_modules.features.poe2.live_terrain.capture_samples import CaptureEvidence
from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.models import (
    AbsoluteRegistration,
    SimilarityTransform2D,
)
from auto_modules.features.poe2.live_terrain.experimental.multiplayer_localization.dual_motion import (
    DualMotionState,
)
from auto_modules.features.poe2.live_terrain.experimental.multiplayer_localization.models import (
    DualFirstFrameResult,
    PlayerLocalization,
)
from auto_modules.features.poe2.live_terrain.experimental.multiplayer_localization.product_session import (
    Poe2DualLocalizationSession,
)
from auto_modules.features.poe2.live_terrain.hybrid_product_runtime import (
    Poe2HybridProductRuntime,
)

AREA = "MapTest:A1"


def _registration() -> AbsoluteRegistration:
    return AbsoluteRegistration(
        result=LocalizationResult((30.0, 40.0), 0.92, source="dual_first_frame"),
        transform=SimilarityTransform2D(45.0, True, 1.2, (20.0, 30.0)),
        anchor_error=1.0,
        area_instance=AREA,
    )


def _result() -> DualFirstFrameResult:
    registration = _registration()
    players = {
        identity: PlayerLocalization(
            identity=identity,
            candidate_id=f"candidate-{identity}",
            screen_position=screen,
            memory_position=memory,
            mapped_position=memory,
            anchor_error=1.0,
            confidence=0.92,
            accepted=True,
        )
        for identity, screen, memory in (
            ("p1", (20.0, 20.0), (30.0, 40.0)),
            ("p2", (40.0, 20.0), (45.0, 40.0)),
        )
    }
    return DualFirstFrameResult("accepted", "ok", registration, players)


class _FrameSource:
    def __init__(self):
        self.count = 0

    def capture(self, config):
        del config
        self.count += 1
        return np.zeros((40, 40, 3), dtype=np.uint8)


class _EvidenceBuilder:
    def build(self, raw, config, **kwargs):
        del config, kwargs
        mask = np.zeros(raw.shape[:2], dtype=np.uint8)
        mask[8:12, 8:32] = 255
        return CaptureEvidence(
            captured_at="2026-09-26T00:00:00+00:00",
            raw=raw,
            processed=raw,
            feature=mask,
            wall_mask=mask,
            monitor_config={},
        )


class _FirstFrame:
    def __init__(self):
        self.reads = 0

    def read_anchors(self, expected_instance_id):
        assert expected_instance_id == AREA
        self.reads += 1
        return {"p1": object(), "p2": object()}

    def register(self, frame, *, reference, anchors, observation):
        del frame, reference, anchors, observation
        return _result()


class _Tracker:
    def __init__(self):
        self.ticks = 0

    def start(self, frame, result, candidates):
        del frame, result, candidates
        return DualMotionState(
            status="tracking",
            reason="first_frame",
            players={"p1": (30.0, 40.0), "p2": (45.0, 40.0)},
            transform=_registration().transform,
        )

    def tick(self, frame, candidates):
        del frame, candidates
        self.ticks += 1
        return DualMotionState(
            status="tracking",
            reason="visual",
            players={"p1": (31.0, 40.0), "p2": (46.0, 40.0)},
            transform=_registration().transform,
            wall_quality=0.9,
        )


def _session(first_frame=None, tracker=None):
    return Poe2DualLocalizationSession(
        frame_source=_FrameSource(),
        evidence_builder=_EvidenceBuilder(),
        config_provider=lambda: SimpleNamespace(dual_marker_profiles=()),
        first_frame_experiment=first_frame or _FirstFrame(),
        tracker=tracker or _Tracker(),
        reference=object(),
        expected_instance_id=AREA,
        clock_ms=lambda: 1000,
    )


def test_dual_product_session_reads_memory_only_for_first_frame():
    first = _FirstFrame()
    session = _session(first_frame=first)
    session.start()

    first_state = session.tick()
    second_state = session.tick()

    assert first.reads == 1
    assert first_state.status == "tracking"
    assert first_state.players["p1"] == (30.0, 40.0)
    assert second_state.source == "dual_visual"


def test_dual_product_session_retry_is_one_new_memory_read():
    first = _FirstFrame()
    tracker = _Tracker()
    session = _session(first_frame=first, tracker=tracker)
    session.start()
    session.tick()
    session._recovery_required = True

    held = session.tick()
    assert held.status == "recovery_required"
    assert first.reads == 1

    session.retry_recovery()
    recovered = session.tick()
    assert recovered.status == "tracking"
    assert first.reads == 2


def test_product_runtime_adapts_dual_players_without_overwriting_single_fields():
    dual_state = SimpleNamespace(
        status="tracking",
        reason="visual",
        players={"p1": (30.0, 40.0), "p2": (45.0, 40.0)},
        screen_positions={"p1": (20.0, 20.0), "p2": (40.0, 20.0)},
        trajectories={"p1": ((30.0, 40.0),), "p2": ((45.0, 40.0),)},
        registration=_registration(),
        source="dual_visual",
        confidence=0.88,
        wall_quality=0.90,
        recovery_revision=1,
        diagnostics={},
    )
    session = SimpleNamespace(
        last_evidence=SimpleNamespace(processed=np.zeros((2, 2)), wall_mask=np.zeros((2, 2))),
        last_frame=SimpleNamespace(local_player=(20.0, 20.0)),
        last_raw_frame=None,
        last_timing_ms={},
    )
    experiment = SimpleNamespace(session=session, anchor_provider=SimpleNamespace(read_count=1))

    state = Poe2HybridProductRuntime._adapt_state(experiment, dual_state, elapsed_ms=1.0)

    assert state.mode == "tracking"
    assert state.position == (30.0, 40.0)
    assert state.dual_players["p2"] == (45.0, 40.0)
    assert state.dual_screen_positions["p1"] == (20.0, 20.0)
