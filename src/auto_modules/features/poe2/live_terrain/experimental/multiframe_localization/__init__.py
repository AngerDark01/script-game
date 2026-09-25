"""Bounded multi-frame localization experiments for PoE2."""

from .models import CandidateRegion, MotionState, MultiFrameEvidence, PositionEstimate
from .local_corrector import LocalCorrection, LocalShapeCorrector
from .composition import MultiframeExperiment, build_multiframe_experiment, build_poe2_multiframe_experiment

__all__ = ["CandidateRegion", "LocalCorrection", "LocalShapeCorrector", "MotionState", "MultiFrameEvidence", "PositionEstimate", "MultiframeExperiment", "build_multiframe_experiment", "build_poe2_multiframe_experiment"]
