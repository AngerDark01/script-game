"""PoE2 business composition for the two-player product session."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from auto_modules.core.localization.local_matcher import LocalMapMatcher
from auto_modules.core.localization.map_runtime import MapRuntime
from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.absolute_registrar import (
    AnchoredAbsoluteRegistrar,
    AnchoredRegistrationConfig,
    reference_boundary_layer,
)
from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.composition import (
    _Poe2EvidenceBuilder,
    _PreviewFrameSource,
)
from auto_modules.features.poe2.live_terrain.orientation import TerrainOrientation
from auto_modules.features.poe2.live_terrain.terrain_reference import build_reference

from .dual_first_frame import DualFirstFrameRegistrar
from .dual_motion import DualVisualTracker
from .experiment import DualFirstFrameExperiment
from .memory_anchors import Poe2DualMemoryAnchorProvider, Poe2DualPlayerPositionSource
from .product_session import Poe2DualLocalizationSession


class Poe2DualLocalizationExperiment:
    """Runtime dependencies owned by one formal dual-player session."""

    def __init__(
        self,
        *,
        session: Poe2DualLocalizationSession,
        anchor_provider: Poe2DualMemoryAnchorProvider,
        tracker: DualVisualTracker,
        reference: Any,
    ) -> None:
        self.session = session
        self.anchor_provider = anchor_provider
        self.tracker = tracker
        self.reference = reference


def build_poe2_dual_first_frame_registrar(config: Any) -> DualFirstFrameRegistrar:
    """Build the PoE2 dual registrar with the calibrated anchored policy.

    The generic dual registrar deliberately keeps all minimap evidence by
    default.  PoE2 still needs the product-level anchored coverage gate used by
    the single-player path; otherwise a close pair falls back to the generic
    ``0.60`` gate and rejects sparse but spatially exact frames.
    """
    registration_config = AnchoredRegistrationConfig(
        crop_radius=150,
        refine_crop_radius=110,
        capture_reference_size=200,
        top_exclusion_rows=0,
        player_clear_radius=0,
        max_anchor_error=80.0,
        anchor_weight=0.65,
        minimum_confidence=float(getattr(config, "first_frame_minimum_confidence", 0.70)),
        minimum_score=0.50,
        minimum_score_when_anchored=float(
            getattr(config, "first_frame_anchored_score", 0.35)
        ),
        minimum_forward_coverage=0.65,
        minimum_forward_coverage_when_anchored=float(
            getattr(config, "first_frame_anchored_coverage", 0.45)
        ),
        anchor_acceptance_radius=8.0,
        anchor_disambiguation_gap=1.0,
        minimum_margin=0.03,
    )
    return DualFirstFrameRegistrar(AnchoredAbsoluteRegistrar(registration_config))


def build_poe2_dual_localization_experiment(
    *,
    snapshot: Any,
    config_provider: Callable[[], Any],
    preview_capture: Callable[[Any], Any],
    recognizer: Any,
    dual_player_position_source: Poe2DualPlayerPositionSource,
    clock_ms: Callable[[], int] | None = None,
) -> Poe2DualLocalizationExperiment:
    config = config_provider()
    recognizer_params = getattr(config, "recognizer_params", None)
    set_recognizer_params = getattr(recognizer, "set_params", None)
    if isinstance(recognizer_params, Mapping) and recognizer_params and callable(set_recognizer_params):
        set_recognizer_params(dict(recognizer_params))

    orientation = TerrainOrientation()
    reference = build_reference(snapshot)
    anchor_provider = Poe2DualMemoryAnchorProvider(
        dual_player_position_source,
        orientation,
        (snapshot.metadata.height, snapshot.metadata.width),
        clock_ms=clock_ms,
    )
    first_frame = DualFirstFrameExperiment(
        anchor_provider,
        registrar=build_poe2_dual_first_frame_registrar(config),
    )
    matcher_runtime = MapRuntime.from_wall_layer(
        reference_boundary_layer(reference),
        map_id=snapshot.metadata.area_id,
        map_version=snapshot.metadata.instance_id,
    )
    tracker = DualVisualTracker(
        LocalMapMatcher(matcher_runtime, max_error=4.0, min_margin=0.02),
        max_failures=3,
        max_marker_step=45.0,
        correction_radius=48.0,
        # Wall displacement is cheap and runs every frame; the expensive
        # local geometric correction is only a periodic guard.  At 30 FPS a
        # 24-frame interval is ~0.8 s, which keeps the UI responsive while
        # still correcting drift well before the bounded match radius is
        # exceeded.
        correction_frame_interval=24,
    )
    session = Poe2DualLocalizationSession(
        frame_source=_PreviewFrameSource(preview_capture),
        evidence_builder=_Poe2EvidenceBuilder(recognizer),
        config_provider=config_provider,
        first_frame_experiment=first_frame,
        tracker=tracker,
        reference=reference,
        expected_instance_id=snapshot.metadata.instance_id,
        clock_ms=clock_ms,
    )
    return Poe2DualLocalizationExperiment(
        session=session,
        anchor_provider=anchor_provider,
        tracker=tracker,
        reference=reference,
    )


__all__ = [
    "Poe2DualLocalizationExperiment",
    "build_poe2_dual_first_frame_registrar",
    "build_poe2_dual_localization_experiment",
]
