"""Experimental two-player localization for the PoE2 live-terrain lab."""

from .dual_first_frame import DualFirstFrameConfig, DualFirstFrameRegistrar
from .dual_motion import DualMotionState, DualVisualTracker
from .minimap_contact_adapter import MinimapContactObservation, inspect_minimap_contact
from .composition import (
    Poe2DualLocalizationExperiment,
    build_poe2_dual_first_frame_registrar,
    build_poe2_dual_localization_experiment,
)
from .product_session import DualProductLocalizationState, Poe2DualLocalizationSession
from .experiment import DualFirstFrameExperiment
from .marker_candidates import (
    detect_saturated_marker_observation,
    marker_candidates_from_observation,
)
from .memory_anchors import (
    Poe2DualMemoryAnchorProvider,
    Poe2DualPlayerPositionSource,
    Poe2EntityPositionSample,
)
from .models import (
    DualFirstFrameResult,
    MarkerColorProfile,
    PlayerLocalization,
    PlayerMarkerCandidate,
)

__all__ = [
    "DualFirstFrameConfig",
    "DualFirstFrameExperiment",
    "DualFirstFrameRegistrar",
    "DualFirstFrameResult",
    "DualMotionState",
    "DualVisualTracker",
    "MinimapContactObservation",
    "inspect_minimap_contact",
    "DualProductLocalizationState",
    "Poe2DualLocalizationSession",
    "Poe2DualLocalizationExperiment",
    "build_poe2_dual_first_frame_registrar",
    "build_poe2_dual_localization_experiment",
    "MarkerColorProfile",
    "PlayerLocalization",
    "PlayerMarkerCandidate",
    "Poe2DualMemoryAnchorProvider",
    "Poe2DualPlayerPositionSource",
    "Poe2EntityPositionSample",
    "detect_saturated_marker_observation",
    "marker_candidates_from_observation",
]
