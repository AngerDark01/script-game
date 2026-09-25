"""Composable PoE2 hybrid-localization experiment."""

from .contracts import AbsoluteRegistrar, AnchorProvider, LocalTracker
from .controller import HybridLocalizationController
from .composition import (
    Poe2HybridLocalizationExperiment,
    build_poe2_hybrid_localization_experiment,
)
from .memory_anchor import Poe2MemoryAnchorProvider
from .local_tracker import VisualLocalTracker
from .models import (
    AbsoluteRegistration,
    HybridFrame,
    HybridLocalizationMode,
    HybridLocalizationState,
    PositionAnchor,
    SimilarityTransform2D,
)
from .recovery import OneShotRecoveryPolicy
from .session import Poe2HybridLocalizationSession

__all__ = [
    "AbsoluteRegistrar",
    "AbsoluteRegistration",
    "AnchorProvider",
    "HybridFrame",
    "HybridLocalizationController",
    "HybridLocalizationMode",
    "HybridLocalizationState",
    "LocalTracker",
    "OneShotRecoveryPolicy",
    "Poe2MemoryAnchorProvider",
    "Poe2HybridLocalizationSession",
    "Poe2HybridLocalizationExperiment",
    "PositionAnchor",
    "SimilarityTransform2D",
    "VisualLocalTracker",
    "build_poe2_hybrid_localization_experiment",
]
