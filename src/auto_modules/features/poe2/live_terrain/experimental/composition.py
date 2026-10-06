"""Explicit assembly for the headless PoE2 experiment runtime."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .application import ExperimentRuntime
from .diagnostics import EventRecorder
from .multiplayer import DualMotionController
from .recovery import RecoveryController


@dataclass(slots=True)
class Poe2ExperimentComposition:
    runtime: ExperimentRuntime
    motion: DualMotionController
    recovery: RecoveryController
    diagnostics: EventRecorder


def build_experiment_composition(*, capture: Any = None, tracker: Any = None) -> Poe2ExperimentComposition:
    return Poe2ExperimentComposition(
        runtime=ExperimentRuntime(),
        motion=DualMotionController(capture=capture, tracker=tracker),
        recovery=RecoveryController(),
        diagnostics=EventRecorder(),
    )
