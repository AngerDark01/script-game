from types import SimpleNamespace

import numpy as np
import pytest

from auto_modules.features.poe2.live_terrain.capture_samples import CaptureEvidence
from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.models import (
    HybridLocalizationMode,
    HybridLocalizationState,
)
from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.session import (
    Poe2HybridLocalizationSession,
)


def state(position=(10.0, 20.0), source="anchored_absolute"):
    return HybridLocalizationState(
        mode=HybridLocalizationMode.LOCAL_TRACKING,
        position=position,
        latest_confirmed_position=position,
        trajectory=(position,),
        registration=None,
        source=source,
        confidence=0.9,
        reason="",
        recovery_revision=1,
    )


class FrameSourceFake:
    def __init__(self, events=None):
        self.calls = []
        self.events = events

    def capture(self, config):
        if self.events is not None:
            self.events.append("capture")
        self.calls.append(config)
        return np.full((20, 30, 3), 17, dtype=np.uint8)


class EvidenceBuilderFake:
    def __init__(self):
        self.calls = []

    def build(self, raw, config):
        self.calls.append((raw, config))
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


class ControllerFake:
    def __init__(self, states, events=None):
        self.states = list(states)
        self.events = events
        self.frames = []
        self.starts = 0
        self.stops = 0
        self.resets = 0
        self.retries = 0

    def prepare_capture(self):
        if self.events is not None:
            self.events.append("prepare")
        return None

    def start(self):
        self.starts += 1

    def stop(self):
        self.stops += 1

    def reset(self):
        self.resets += 1

    def retry_recovery(self):
        self.retries += 1

    def update(self, frame):
        if self.events is not None:
            self.events.append("update")
        self.frames.append(frame)
        return self.states.pop(0)


def test_tick_captures_and_builds_once_then_publishes_same_frame():
    frame_source = FrameSourceFake()
    builder = EvidenceBuilderFake()
    controller = ControllerFake([state()])
    config = SimpleNamespace(name="active")
    session = Poe2HybridLocalizationSession(
        frame_source=frame_source,
        evidence_builder=builder,
        config_provider=lambda: config,
        controller=controller,
        clock_ms=lambda: 1234,
    )
    published = []
    session.add_listener(published.append)
    session.start()

    result = session.tick()

    assert result is published[0]
    assert frame_source.calls == [config]
    assert len(builder.calls) == 1
    assert builder.calls[0][1] is config
    assert len(controller.frames) == 1
    assert controller.frames[0].frame_id == 1
    assert controller.frames[0].captured_at_ms == 1234
    assert controller.frames[0].local_player == (15.0, 10.0)
    assert controller.starts == 1
    assert session.last_raw_frame is builder.calls[0][0]
    assert session.last_evidence.wall_mask is not None
    assert session.last_frame is controller.frames[0]


def test_tick_prepares_memory_anchor_before_capturing_the_corresponding_frame():
    events = []
    frame_source = FrameSourceFake(events)
    controller = ControllerFake([state()], events)
    session = Poe2HybridLocalizationSession(
        frame_source=frame_source,
        evidence_builder=EvidenceBuilderFake(),
        config_provider=lambda: object(),
        controller=controller,
        clock_ms=lambda: 1234,
    )
    session.start()

    session.tick()

    assert events == ["prepare", "capture", "update"]


def test_stop_blocks_capture_and_lifecycle_methods_delegate():
    frame_source = FrameSourceFake()
    builder = EvidenceBuilderFake()
    controller = ControllerFake([state()])
    session = Poe2HybridLocalizationSession(
        frame_source=frame_source,
        evidence_builder=builder,
        config_provider=lambda: object(),
        controller=controller,
    )
    session.start()
    session.stop()

    with pytest.raises(RuntimeError, match="not running"):
        session.tick(now_ms=10)

    session.retry_recovery()
    session.reset()
    assert controller.stops == 1
    assert controller.retries == 1
    assert controller.resets == 1
    assert not frame_source.calls
    assert session.last_raw_frame is None
    assert session.last_evidence is None
    assert session.last_frame is None


def test_failed_state_is_published_without_substituting_last_position():
    failed = HybridLocalizationState(
        mode=HybridLocalizationMode.RECOVERY_PENDING,
        position=None,
        latest_confirmed_position=(10.0, 20.0),
        trajectory=((10.0, 20.0),),
        registration=None,
        source="failed",
        confidence=0.0,
        reason="local_tracking_failed",
        recovery_revision=2,
    )
    session = Poe2HybridLocalizationSession(
        frame_source=FrameSourceFake(),
        evidence_builder=EvidenceBuilderFake(),
        config_provider=lambda: object(),
        controller=ControllerFake([failed]),
    )
    published = []
    session.add_listener(published.append)
    session.start()

    result = session.tick(now_ms=10)

    assert result.position is None
    assert published[0].position is None
    assert published[0].latest_confirmed_position == (10.0, 20.0)
