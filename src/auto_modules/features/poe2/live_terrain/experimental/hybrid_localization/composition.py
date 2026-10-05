"""PoE2 adapters that compose the hybrid-localization experiment."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping

from auto_modules.core.localization.local_matcher import LocalMapMatcher
from auto_modules.core.localization.map_runtime import MapRuntime
from auto_modules.features.poe2.live_terrain.capture_samples import CaptureEvidence
from auto_modules.features.poe2.live_terrain.orientation import TerrainOrientation
from auto_modules.features.poe2.live_terrain.terrain_reference import (
    TerrainReference,
    build_reference,
)

from .absolute_registrar import (
    AnchoredAbsoluteRegistrar,
    AnchoredRegistrationConfig,
    reference_boundary_layer,
)
from .controller import HybridLocalizationController
from .local_tracker import VisualLocalTracker
from .memory_anchor import Poe2MemoryAnchorProvider
from .session import Poe2HybridLocalizationSession


class _PreviewFrameSource:
    def __init__(self, capture: Callable[[Any], Any]) -> None:
        self._capture = capture

    def capture(self, config: Any) -> Any:
        return self._capture(config)


class _Poe2EvidenceBuilder:
    def __init__(self, recognizer: Any) -> None:
        self.recognizer = recognizer

    @staticmethod
    def _config_payload(config: Any) -> Mapping[str, Any]:
        serializer = getattr(config, "as_dict", None)
        if not callable(serializer):
            serializer = getattr(config, "to_dict", None)
        if callable(serializer):
            payload = serializer()
            if not isinstance(payload, Mapping):
                raise TypeError("monitor config serializer must return a mapping")
            return dict(payload)
        if isinstance(config, Mapping):
            return dict(config)
        return dict(vars(config))

    def build(
        self,
        raw: Any,
        config: Any,
        *,
        exclude_player: bool = True,
        exclude_dynamic: bool = True,
    ) -> CaptureEvidence:
        marker = (
            getattr(getattr(config, "binding", None), "player_marker_position", None)
            if exclude_player else None
        )
        combined_with_processed = getattr(self.recognizer, "extract_combined_with_processed", None)
        if callable(combined_with_processed):
            try:
                processed, combined = combined_with_processed(
                    raw,
                    player_pos=marker,
                    exclude_player=exclude_player,
                    exclude_dynamic=exclude_dynamic,
                )
            except TypeError:
                processed, combined = combined_with_processed(raw, player_pos=marker)
        else:
            processed = self.recognizer.preprocess_image(raw)
            try:
                combined = self.recognizer.extract_combined(
                    raw,
                    player_pos=marker,
                    exclude_player=exclude_player,
                    exclude_dynamic=exclude_dynamic,
                )
            except TypeError:
                combined = self.recognizer.extract_combined(raw, player_pos=marker)
        if isinstance(combined, tuple):
            feature = combined[0]
            wall_mask = combined[1] if len(combined) > 1 else feature
            fog_mask = combined[2] if len(combined) > 2 else None
        else:
            feature = combined
            wall_mask = feature
            fog_mask = None
        raw_gray_provider = getattr(self.recognizer, "get_raw_gray", None)
        raw_gray = (
            raw_gray_provider(raw, processed=processed)
            if callable(combined_with_processed) and callable(raw_gray_provider)
            else raw_gray_provider(raw) if callable(raw_gray_provider) else None
        )
        return CaptureEvidence(
            captured_at=datetime.now(timezone.utc).isoformat(),
            raw=raw,
            processed=processed,
            feature=feature,
            wall_mask=wall_mask,
            fog_mask=fog_mask,
            raw_gray=raw_gray,
            monitor_config=self._config_payload(config),
        )


@dataclass(frozen=True)
class Poe2HybridLocalizationExperiment:
    session: Poe2HybridLocalizationSession
    controller: HybridLocalizationController
    anchor_provider: Poe2MemoryAnchorProvider
    registrar: AnchoredAbsoluteRegistrar
    tracker: VisualLocalTracker
    reference: TerrainReference


def _poe2_first_frame_registration_config(config: Any) -> AnchoredRegistrationConfig:
    """Return the experimentally calibrated PoE2 first-frame policy.

    The memory position is the trusted spatial anchor.  The minimap geometry
    chooses the orientation and scale basin, then the anchor breaks near-tie
    candidates.  Keep this policy explicit at the PoE2 composition boundary so
    a generic registrar default cannot silently change the live experiment.
    """
    return AnchoredRegistrationConfig(
        crop_radius=150,
        refine_crop_radius=110,
        capture_reference_size=200,
        top_exclusion_rows=40,
        player_clear_radius=22,
        max_anchor_error=80.0,
        anchor_weight=0.65,
        # PoE2 live terrain accepts a moderately noisy first frame once the
        # memory anchor and independent shape-quality gates have passed.
        minimum_confidence=float(getattr(config, "first_frame_minimum_confidence", 0.70)),
        minimum_score=0.50,
        minimum_score_when_anchored=float(getattr(config, "first_frame_anchored_score", 0.35)),
        minimum_forward_coverage=0.65,
        minimum_forward_coverage_when_anchored=float(getattr(config, "first_frame_anchored_coverage", 0.45)),
        anchor_acceptance_radius=8.0,
        anchor_disambiguation_gap=1.0,
        minimum_margin=0.03,
    )


def build_poe2_hybrid_localization_experiment(
    *,
    snapshot: Any,
    config_provider: Callable[[], Any],
    preview_capture: Callable[[Any], Any],
    recognizer: Any,
    player_position_source: Any,
    clock_ms: Callable[[], int] | None = None,
) -> Poe2HybridLocalizationExperiment:
    config = config_provider()
    recognizer_params = getattr(config, "recognizer_params", None)
    set_recognizer_params = getattr(recognizer, "set_params", None)
    if isinstance(recognizer_params, Mapping) and recognizer_params and callable(set_recognizer_params):
        set_recognizer_params(dict(recognizer_params))
    orientation = TerrainOrientation()
    reference = build_reference(snapshot)
    anchor_provider = Poe2MemoryAnchorProvider(
        player_position_source,
        orientation,
        (snapshot.metadata.height, snapshot.metadata.width),
        clock_ms=clock_ms,
    )
    registrar = AnchoredAbsoluteRegistrar(_poe2_first_frame_registration_config(config))
    matcher_runtime = MapRuntime.from_wall_layer(
        reference_boundary_layer(reference),
        map_id=snapshot.metadata.area_id,
        map_version=snapshot.metadata.instance_id,
    )
    tracker = VisualLocalTracker(
        LocalMapMatcher(matcher_runtime, max_error=4.0, min_margin=0.02),
        correction_frame_interval=12,
        correction_distance=24.0,
        correction_interval_ms=1500,
    )
    controller = HybridLocalizationController(
        expected_instance_id=snapshot.metadata.instance_id,
        reference=reference,
        anchor_provider=anchor_provider,
        absolute_registrar=registrar,
        local_tracker=tracker,
    )
    session = Poe2HybridLocalizationSession(
        frame_source=_PreviewFrameSource(preview_capture),
        evidence_builder=_Poe2EvidenceBuilder(recognizer),
        config_provider=config_provider,
        controller=controller,
        clock_ms=clock_ms,
    )
    return Poe2HybridLocalizationExperiment(
        session=session,
        controller=controller,
        anchor_provider=anchor_provider,
        registrar=registrar,
        tracker=tracker,
        reference=reference,
    )


__all__ = [
    "Poe2HybridLocalizationExperiment",
    "build_poe2_hybrid_localization_experiment",
]
