"""Explicit assembly for the headless PoE2 experiment runtime."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .application import ExperimentRuntime
from .adapters import AdapterBundle
from .diagnostics import EventRecorder
from .multiplayer import DualMotionController
from .probes import DualTargetProbe, FollowProbe, MoveProbe
from .recovery import RecoveryController


@dataclass(slots=True)
class Poe2ExperimentComposition:
    adapters: AdapterBundle
    runtime: ExperimentRuntime
    motion: DualMotionController
    recovery: RecoveryController
    diagnostics: EventRecorder
    move_probe: MoveProbe
    dual_target_probe: DualTargetProbe
    follow_probe: FollowProbe


def build_experiment_composition(
    *, capture: Any = None, tracker: Any = None, adapters: AdapterBundle | None = None,
) -> Poe2ExperimentComposition:
    adapters = adapters or AdapterBundle(capture=capture)
    return Poe2ExperimentComposition(
        adapters=adapters,
        runtime=ExperimentRuntime(),
        motion=DualMotionController(capture=adapters.capture, tracker=tracker),
        recovery=RecoveryController(),
        diagnostics=EventRecorder(),
        move_probe=MoveProbe(),
        dual_target_probe=DualTargetProbe(),
        follow_probe=FollowProbe(),
    )
