"""Composition root for the PoE2 multi-frame experiment."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

import numpy as np
from auto_modules.core.spatial.capture_geometry import build_capture_mask

from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.models import HybridFrame

from .coordinator import MultiframeLocalizationCoordinator
from .archive import MultiframeArchive
from .evidence_window import EvidenceWindow
from .local_corrector import LocalShapeCorrector
from .motion_gate import MotionGate
from .models import MultiFrameEvidence
from .navigation_adapter import NavigationLocalizationAdapter
from .rolling_submap import RollingSubmap
from .session import MultiframeLocalizationSession
from .state_estimator import PositionStateEstimator
from .strategy_a import StitchThenRegister, SubmapThresholds
from .strategy_b import JointCandidateStrategy


@dataclass(frozen=True)
class MultiframeExperiment:
    session: MultiframeLocalizationSession
    coordinator: MultiframeLocalizationCoordinator
    window: EvidenceWindow
    submap: RollingSubmap
    navigation_adapter: NavigationLocalizationAdapter
    anchor_provider: Any
    archive: MultiframeArchive


class _Poe2EvidenceBuilder:
    def __init__(self, recognizer: Any, gate: MotionGate, clock_ms) -> None:
        self.recognizer = recognizer
        self.gate = gate
        self._offset = np.zeros(2, dtype=np.float64)
        self._segment = 0
        self.clock_ms = clock_ms

    def reset(self) -> None:
        """Clear accumulated local coordinates before a new capture run."""
        self._offset.fill(0.0)
        self._segment = 0

    def build(self, raw: Any, config: Any, *, frame_id: int, previous: MultiFrameEvidence | None) -> MultiFrameEvidence:
        processed = self.recognizer.preprocess_image(raw)
        marker = getattr(getattr(config, "binding", None), "player_marker_position", None)
        combined = self.recognizer.extract_combined(raw, player_pos=marker)
        feature = combined[0] if isinstance(combined, tuple) else combined
        wall = combined[1] if isinstance(combined, tuple) and len(combined) > 1 else feature
        now_ms = int(self.clock_ms())
        frame = HybridFrame(
            frame_id,
            now_ms,
            wall,
            marker or (wall.shape[1] / 2.0, wall.shape[0] / 2.0),
            diagnostics={"capture_size": max(wall.shape), "processed_shape": tuple(processed.shape)},
        )
        if previous is None:
            from auto_modules.core.localization.frame_displacement import FrameDisplacement
            motion = FrameDisplacement((0.0, 0.0), 1.0, 0.0, True, "initial")
            observed = build_capture_mask(
                wall.shape[1], wall.shape[0], getattr(config, "shape", "square"),
                radius=getattr(config, "circle_radius", None),
            )
            return MultiFrameEvidence(frame, motion, tuple(self._offset), False, self._segment, observed, raw)
        decision = self.gate.decide(previous.frame, frame, elapsed_ms=max(0, now_ms - previous.frame.captured_at_ms))
        displacement = decision.displacement
        if decision.state.value == "moving" and displacement.shift is not None:
            self._offset -= np.asarray(displacement.shift, dtype=np.float64)
        if decision.state.value == "unknown":
            self._segment += 1
        observed = build_capture_mask(
            wall.shape[1], wall.shape[0], getattr(config, "shape", "square"),
            radius=getattr(config, "circle_radius", None),
        )
        return MultiFrameEvidence(frame, displacement, tuple(self._offset), decision.should_capture_keyframe, self._segment, observed, raw)


def build_multiframe_experiment(*, instance_id, frame_source, evidence_builder, config_provider, anchor_provider, clock_ms, reference=None, strategy_a=None, strategy_b=None):
    window = EvidenceWindow()
    submap = RollingSubmap()
    coordinator = MultiframeLocalizationCoordinator(
        instance_id=instance_id,
        window=window,
        submap=submap,
        estimator=PositionStateEstimator(),
        strategy_a=strategy_a,
        strategy_b=strategy_b,
        reference=reference,
        local_corrector=LocalShapeCorrector(),
    )
    session = MultiframeLocalizationSession(frame_source=frame_source, evidence_builder=evidence_builder, config_provider=config_provider, coordinator=coordinator, anchor_provider=anchor_provider, clock_ms=clock_ms)
    return MultiframeExperiment(
        session,
        coordinator,
        window,
        submap,
        NavigationLocalizationAdapter(),
        anchor_provider,
        MultiframeArchive(),
    )


def build_poe2_multiframe_experiment(*, snapshot, config_provider, preview_capture, recognizer, player_position_source, clock_ms=None):
    """Compose PoE2 capture, recognition and memory anchor for the test bench only."""
    from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.memory_anchor import Poe2MemoryAnchorProvider
    from auto_modules.features.poe2.live_terrain.orientation import TerrainOrientation

    # The multiframe experiment exchanges native terrain coordinates. Display
    # orientation is applied only by the presentation adapter after registration.
    orientation = TerrainOrientation()
    anchor_provider = Poe2MemoryAnchorProvider(player_position_source, orientation, (snapshot.metadata.height, snapshot.metadata.width), clock_ms=clock_ms)
    effective_clock = clock_ms or (lambda: int(datetime.now(timezone.utc).timestamp() * 1000))
    gate = MotionGate()
    builder = _Poe2EvidenceBuilder(recognizer, gate, effective_clock)
    from auto_modules.features.poe2.live_terrain.terrain_reference import build_reference
    from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.absolute_registrar import AnchoredAbsoluteRegistrar
    reference = build_reference(snapshot)
    initial_config = config_provider()
    recognizer_params = getattr(initial_config, "recognizer_params", None)
    set_recognizer_params = getattr(recognizer, "set_params", None)
    if isinstance(recognizer_params, Mapping) and recognizer_params and callable(set_recognizer_params):
        set_recognizer_params(dict(recognizer_params))
    registrar = AnchoredAbsoluteRegistrar()
    strategy_a = StitchThenRegister(registrar, thresholds=SubmapThresholds(min_frames=4, min_wall_pixels=80, min_span=12.0))
    strategy_b = JointCandidateStrategy()
    experiment = build_multiframe_experiment(
        instance_id=snapshot.metadata.instance_id,
        frame_source=type("PreviewSource", (), {"capture": staticmethod(preview_capture)})(),
        evidence_builder=builder,
        config_provider=config_provider,
        anchor_provider=anchor_provider,
        clock_ms=effective_clock,
        reference=reference,
        strategy_a=strategy_a,
        strategy_b=strategy_b,
    )
    return experiment


__all__ = ["MultiframeExperiment", "build_multiframe_experiment", "build_poe2_multiframe_experiment"]
