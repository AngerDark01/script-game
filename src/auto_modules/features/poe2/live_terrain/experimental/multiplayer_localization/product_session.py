"""Worker-friendly product session for the validated two-player tracker."""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from time import perf_counter
from types import MappingProxyType
from typing import Any

from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.models import (
    HybridFrame,
)

from .dual_motion import DualMotionState, DualVisualTracker
from .experiment import DualFirstFrameExperiment
from .marker_candidates import (
    detect_saturated_marker_observation,
    marker_candidates_from_observation,
)
from .models import PlayerMarkerCandidate


@dataclass(frozen=True)
class DualProductLocalizationState:
    """Immutable state consumed by the formal PoE2 product adapter."""

    status: str
    reason: str
    players: Mapping[str, tuple[float, float] | None] = field(default_factory=dict)
    screen_positions: Mapping[str, tuple[float, float] | None] = field(default_factory=dict)
    trajectories: Mapping[str, tuple[tuple[float, float], ...]] = field(default_factory=dict)
    registration: Any | None = None
    source: str = "dual_failed"
    confidence: float = 0.0
    wall_quality: float = 0.0
    recovery_revision: int = 0
    recovery_requested: bool = False
    diagnostics: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "players", MappingProxyType(dict(self.players)))
        object.__setattr__(self, "screen_positions", MappingProxyType(dict(self.screen_positions)))
        object.__setattr__(
            self,
            "trajectories",
            MappingProxyType({key: tuple(value) for key, value in self.trajectories.items()}),
        )
        object.__setattr__(self, "diagnostics", MappingProxyType(dict(self.diagnostics)))


class Poe2DualLocalizationSession:
    """Capture and run dual localization without touching the GUI thread."""

    def __init__(
        self,
        *,
        frame_source: Any,
        evidence_builder: Any,
        config_provider: Callable[[], Any],
        first_frame_experiment: DualFirstFrameExperiment,
        tracker: DualVisualTracker,
        reference: Any,
        expected_instance_id: str,
        clock_ms: Callable[[], int] | None = None,
    ) -> None:
        self.frame_source = frame_source
        self.evidence_builder = evidence_builder
        self.config_provider = config_provider
        self.first_frame_experiment = first_frame_experiment
        self.tracker = tracker
        self.reference = reference
        self.expected_instance_id = str(expected_instance_id)
        self.clock_ms = clock_ms or (lambda: int(time.time() * 1000))
        self.active = False
        self._need_absolute = True
        self._recovery_required = False
        self._frame_id = 0
        self._recovery_revision = 0
        self._registration: Any | None = None
        self._last_observation: Any | None = None
        self._trajectories: dict[str, list[tuple[float, float]]] = {}
        self.last_raw_frame: Any | None = None
        self.last_evidence: Any | None = None
        self.last_frame: HybridFrame | None = None
        self.last_timing_ms: dict[str, float] = {}

    @property
    def recovery_revision(self) -> int:
        return self._recovery_revision

    def start(self) -> None:
        if self.active:
            return
        self.active = True
        self._need_absolute = True
        self._recovery_required = False
        self._frame_id = 0
        self._recovery_revision = 1
        self._registration = None
        self._trajectories = {}

    def stop(self) -> None:
        self.active = False
        self._recovery_required = False

    def reset(self) -> None:
        self.stop()
        self._need_absolute = True
        self._frame_id = 0
        self._recovery_revision = 0
        self._registration = None
        self._trajectories = {}
        self.last_raw_frame = None
        self.last_evidence = None
        self.last_frame = None
        self.last_timing_ms = {}

    def retry_recovery(self) -> None:
        if not self._recovery_required:
            raise RuntimeError("dual recovery retry is only valid after a failed attempt")
        self._need_absolute = True
        self._recovery_required = False
        self._recovery_revision += 1
        self._registration = None
        self._trajectories = {}

    def tick(self, *, now_ms: int | None = None) -> DualProductLocalizationState:
        if not self.active:
            return self._state("stopped", "stopped", source="dual_stopped")
        if self._recovery_required:
            return self._state(
                "recovery_required",
                "recovery_required",
                source="dual_failed",
                recovery_requested=True,
            )
        if self._need_absolute:
            return self._tick_absolute(now_ms=now_ms)
        return self._tick_visual(now_ms=now_ms)

    def _tick_absolute(self, *, now_ms: int | None) -> DualProductLocalizationState:
        started = perf_counter()
        try:
            anchors = self.first_frame_experiment.read_anchors(self.expected_instance_id)
        except Exception as exc:  # noqa: BLE001 - the worker must convert adapter failures to state
            return self._fail("dual_anchor_read_failed", exc, started)
        try:
            frame, candidates = self._capture_frame(now_ms=now_ms)
            result = self.first_frame_experiment.register(
                frame,
                reference=self.reference,
                anchors=anchors,
                observation=self._last_observation,
            )
        except Exception as exc:  # noqa: BLE001 - the worker must convert adapter failures to state
            return self._fail("dual_first_frame_error", exc, started)
        if not result.accepted or result.primary_registration is None:
            diagnostics = dict(getattr(result, "diagnostics", {}) or {})
            diagnostics["registration_reason"] = str(getattr(result, "reason", "registration rejected"))
            return self._fail(
                "dual_first_frame_failed",
                started=started,
                diagnostics=diagnostics,
            )
        try:
            motion = self.tracker.start(frame, result, candidates)
        except Exception as exc:  # noqa: BLE001 - the worker must convert adapter failures to state
            return self._fail("dual_tracker_start_failed", exc, started)
        self._need_absolute = False
        self._registration = result.primary_registration
        self._record_players(motion.players)
        return self._from_motion(motion, started=started, source="dual_first_frame")

    def _tick_visual(self, *, now_ms: int | None) -> DualProductLocalizationState:
        started = perf_counter()
        try:
            frame, candidates = self._capture_frame(now_ms=now_ms)
            motion = self.tracker.tick(frame, candidates)
        except Exception as exc:  # noqa: BLE001 - the worker must convert adapter failures to state
            return self._fail("dual_visual_tracking_error", exc, started)
        if motion.recovery_requested:
            self._recovery_required = True
        if motion.transform is not None and self._registration is not None:
            self._registration = self._registration.__class__(
                result=self._registration.result,
                transform=motion.transform,
                anchor_error=self._registration.anchor_error,
                area_instance=self._registration.area_instance,
                diagnostics={**dict(self._registration.diagnostics), **dict(motion.diagnostics)},
            )
        self._record_players(motion.players)
        return self._from_motion(motion, started=started, source="dual_visual")

    def _capture_frame(self, *, now_ms: int | None) -> tuple[HybridFrame, tuple[PlayerMarkerCandidate, ...]]:
        config = self.config_provider()
        capture_started = perf_counter()
        raw = self.frame_source.capture(config)
        capture_ended = perf_counter()
        stamp = int(self.clock_ms() if now_ms is None else now_ms)
        evidence = self.evidence_builder.build(
            raw,
            config,
            exclude_player=False,
            exclude_dynamic=False,
        )
        evidence_ended = perf_counter()
        self._frame_id += 1
        profiles = tuple(
            self._profile(item)
            for item in getattr(config, "dual_marker_profiles", ())
        )
        self._last_observation = detect_saturated_marker_observation(
            raw,
            stamp,
            profiles=profiles or None,
        )
        candidates = marker_candidates_from_observation(self._last_observation, max_candidates=6)
        if candidates:
            local_player = (
                sum(item.local_position[0] for item in candidates) / len(candidates),
                sum(item.local_position[1] for item in candidates) / len(candidates),
            )
        else:
            local_player = (
                float(evidence.wall_mask.shape[1]) / 2.0,
                float(evidence.wall_mask.shape[0]) / 2.0,
            )
        frame = HybridFrame(
            frame_id=self._frame_id,
            captured_at_ms=stamp,
            wall_mask=evidence.wall_mask if evidence.wall_mask is not None else evidence.feature,
            local_player=local_player,
            diagnostics={"marker_candidates": len(candidates)},
        )
        self.last_raw_frame = raw
        self.last_evidence = evidence
        self.last_frame = frame
        self.last_timing_ms = {
            "capture_ms": (capture_ended - capture_started) * 1000.0,
            "evidence_ms": (evidence_ended - capture_ended) * 1000.0,
        }
        return frame, candidates

    @staticmethod
    def _profile(value: Any) -> Any:
        from .models import MarkerColorProfile

        return value if isinstance(value, MarkerColorProfile) else MarkerColorProfile.from_dict(value)

    def _record_players(self, players: Mapping[str, tuple[float, float] | None]) -> None:
        for identity, point in players.items():
            if point is not None:
                self._trajectories.setdefault(identity, []).append(
                    (float(point[0]), float(point[1]))
                )

    def _from_motion(
        self,
        motion: DualMotionState,
        *,
        started: float,
        source: str,
    ) -> DualProductLocalizationState:
        self.last_timing_ms["localization_ms"] = (perf_counter() - started) * 1000.0
        confidence = float(motion.wall_quality)
        if motion.players:
            confidence = max(confidence, 0.80 if any(point is not None for point in motion.players.values()) else 0.0)
        return self._state(
            motion.status,
            motion.reason,
            players=motion.players,
            screen_positions=getattr(motion, "screen_positions", {}),
            trajectories=self._trajectories,
            source=source,
            confidence=confidence,
            wall_quality=motion.wall_quality,
            recovery_requested=motion.recovery_requested,
            diagnostics=dict(motion.diagnostics),
        )

    def _fail(
        self,
        reason: str,
        error: Any = None,
        started: float | None = None,
        diagnostics: Mapping[str, Any] | None = None,
    ) -> DualProductLocalizationState:
        self._recovery_required = True
        payload = dict(diagnostics or {})
        if error is not None:
            payload.update({"error": str(error), "error_type": type(error).__name__})
        if started is not None:
            self.last_timing_ms["localization_ms"] = (perf_counter() - started) * 1000.0
        return self._state(
            "recovery_required",
            reason,
            source="dual_failed",
            confidence=0.0,
            recovery_requested=True,
            diagnostics=payload,
        )

    def _state(self, status: str, reason: str, **kwargs: Any) -> DualProductLocalizationState:
        return DualProductLocalizationState(
            status=status,
            reason=reason,
            recovery_revision=self._recovery_revision,
            **kwargs,
        )


__all__ = ["DualProductLocalizationState", "Poe2DualLocalizationSession"]
