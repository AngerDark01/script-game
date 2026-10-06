"""Experimental shared-viewport tracking for two independent minimap markers."""

from __future__ import annotations

import itertools
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from auto_modules.core.localization import (
    BoundedRoleObservations,
    canonical_wall_mask,
    estimate_bounded_displacement,
    transform_local_displacement,
)
from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.models import (
    HybridFrame,
    SimilarityTransform2D,
)
from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.similarity_search import (
    inverse_transform_local_point,
    transform_feature,
    transform_local_point,
)

from .models import DualFirstFrameResult, PlayerMarkerCandidate
from .marker_association import MarkerAssociator


@dataclass(frozen=True)
class DualMotionState:
    status: str
    reason: str
    players: Mapping[str, tuple[float, float] | None]
    transform: SimilarityTransform2D | None
    screen_positions: Mapping[str, tuple[float, float] | None] = field(default_factory=dict)
    wall_quality: float = 0.0
    correction_attempted: bool = False
    recovery_requested: bool = False
    recovery_revision: int = 0
    diagnostics: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RolePredictionHint:
    native_position: tuple[float, float]
    uncertainty_native: float
    predicted_at_ms: int


class DualVisualTracker:
    """Track a common map transform while observing each identity separately.

    This class never reads process memory. The caller owns the one-shot
    recovery action when ``recovery_requested`` is emitted.
    """

    def __init__(
        self,
        matcher: Any | None = None,
        *,
        max_failures: int = 3,
        max_marker_step: float = 45.0,
        identity_margin: float = 2.0,
        correction_radius: float = 48.0,
        correction_frame_interval: int = 12,
        marker_dropout_grace: int = 2,
        marker_hold_ms: int = 2000,
        marker_max_uncertainty: float = 10.0,
    ) -> None:
        if (
            max_failures < 1
            or max_marker_step <= 0
            or correction_radius < 0
            or correction_frame_interval < 0
            or marker_dropout_grace < 0
            or marker_hold_ms < 1
            or marker_max_uncertainty <= 0
        ):
            raise ValueError("invalid dual tracking thresholds")
        self.matcher = matcher
        self.max_failures = int(max_failures)
        self.max_marker_step = float(max_marker_step)
        self.identity_margin = float(identity_margin)
        self.correction_radius = float(correction_radius)
        self.correction_frame_interval = int(correction_frame_interval)
        self.marker_dropout_grace = int(marker_dropout_grace)
        self.marker_hold_ms = int(marker_hold_ms)
        self.marker_max_uncertainty = float(marker_max_uncertainty)
        self._observations = BoundedRoleObservations(
            max_age_ms=marker_hold_ms,
            max_uncertainty=marker_max_uncertainty,
            reappearance_after_missing=max(1, marker_dropout_grace),
        )
        self._frame: HybridFrame | None = None
        self._transform: SimilarityTransform2D | None = None
        self._screen_positions: dict[str, tuple[float, float]] = {}
        self._identity_hints: dict[str, str] = {}
        self._failures = 0
        self._frames_since_correction = 0
        self._recovery_revision = 0
        self._recovery_emitted = False
        self._warmup_remaining = 0
        self._first_live_frame_pending = False
        self._marker_dropout_failures = 0
        self._identity_dropout_failures: dict[str, int] = {}
        self._local_player_identity: str | None = None
        self._local_player_hint: tuple[float, float] | None = None
        self._last_assignment: dict[str, Any] = {}
        self._local_correction_requested = False
        self._marker_associator = MarkerAssociator(
            base_gate=max_marker_step,
            max_gate=max(120.0, max_marker_step * 4.0),
            margin=identity_margin,
        )
        self._last_assignment_at_ms: dict[str, int] = {}
        self._screen_velocities: dict[str, tuple[float, float]] = {}

    def request_local_correction(self) -> None:
        """Schedule one local wall re-anchor using the existing transform.

        Runtime recovery already knows the map orientation and has a predicted
        native position.  This flag forces the next tracker tick through the
        bounded local matcher; it never reads process memory or starts a new
        global registration.  The caller may escalate only when that local
        match fails.
        """
        self._local_correction_requested = True

    def start(
        self,
        frame: HybridFrame,
        result: DualFirstFrameResult,
        initial_candidates: Sequence[PlayerMarkerCandidate] = (),
    ) -> DualMotionState:
        if not result.accepted or result.primary_registration is None or len(result.players) != 2:
            raise ValueError("accepted two-player registration is required")
        transform = result.primary_registration.transform
        self._frame = frame
        self._transform = transform
        self._screen_positions = {
            identity: player.screen_position for identity, player in result.players.items()
        }
        self._local_player_identity = next(iter(self._screen_positions), None)
        self._local_player_hint = (
            self._screen_positions.get(self._local_player_identity)
            if self._local_player_identity is not None
            else None
        )
        candidates_by_id = {candidate.candidate_id: candidate for candidate in initial_candidates}
        hints = {
            identity: str(candidates_by_id[player.candidate_id].color_features.get("identity_hint") or "")
            for identity, player in result.players.items()
            if player.candidate_id in candidates_by_id
        }
        self._identity_hints = hints if len(set(hints.values())) == 2 and all(hints.values()) else {}
        self._last_assignment = {}
        self._last_assignment_at_ms = {
            identity: int(frame.captured_at_ms) for identity in self._screen_positions
        }
        self._screen_velocities = {
            identity: (0.0, 0.0) for identity in self._screen_positions
        }
        self._failures = 0
        self._frames_since_correction = 0
        self._recovery_emitted = False
        self._local_correction_requested = False
        self._marker_dropout_failures = 0
        self._identity_dropout_failures = {
            identity: 0 for identity in self._screen_positions
        }
        for identity, position in self._map_players(self._screen_positions).items():
            assert position is not None
            self._observations.seed(identity, position, at_ms=frame.captured_at_ms)
        # The first timer tick is captured immediately after the manual
        # registration frame.  A transient overlay refresh can make phase
        # correlation return "no displacement" even while the actor is still
        # stationary.  Give one non-empty frame a bounded stationary grace;
        # a genuinely blank/invalid frame still follows the normal recovery
        # path.
        self._warmup_remaining = 1
        self._first_live_frame_pending = True
        return self._state("tracking", "first_frame", self._map_players(self._screen_positions))

    def tick(
        self,
        frame: HybridFrame,
        candidates: Sequence[PlayerMarkerCandidate],
        *,
        prediction_hints: Mapping[str, RolePredictionHint] | None = None,
    ) -> DualMotionState:
        if self._frame is None or self._transform is None:
            raise RuntimeError("start with an accepted dual first frame")
        if frame.wall_mask.shape != self._frame.wall_mask.shape:
            return self._failed("capture_size_changed", 0.0, frame)
        previous = canonical_wall_mask(self._frame.wall_mask)
        current = canonical_wall_mask(frame.wall_mask)
        displacement = estimate_bounded_displacement(previous, current)
        transform = self._transform
        shift = displacement.shift if displacement.accepted else None
        warmup_assumed_stationary = False
        if shift is None and self._warmup_remaining > 0:
            previous_pixels = int(np.count_nonzero(previous))
            current_pixels = int(np.count_nonzero(current))
            ratio = (
                current_pixels / max(previous_pixels, 1)
                if previous_pixels else 0.0
            )
            if previous_pixels > 0 and current_pixels > 0 and 0.15 <= ratio <= 6.0:
                shift = (0.0, 0.0)
                warmup_assumed_stationary = True
                self._warmup_remaining -= 1
        predicted = transform
        wall_prediction_hold = False
        if shift is not None:
            delta = transform_local_displacement(
                shift,
                angle_degrees=transform.angle_degrees,
                reflect_horizontal=transform.reflect_horizontal,
                scale=transform.scale,
            )
            predicted = SimilarityTransform2D(
                transform.angle_degrees,
                transform.reflect_horizontal,
                transform.scale,
                (transform.translation[0] - delta[0], transform.translation[1] - delta[1]),
            )
        elif self._wall_frame_can_be_held(previous, current):
            # A stationary or temporarily untrackable wall frame is still a
            # usable observation. Keep the last transform for this tick and
            # let marker association/role observations provide continuity.
            shift = (0.0, 0.0)
            wall_prediction_hold = True

        self._frames_since_correction += 1
        correction_due = self._local_correction_requested or shift is None or (
            self.matcher is not None
            and self.correction_frame_interval > 0
            and self._frames_since_correction >= self.correction_frame_interval
        )
        correction_attempted = False
        if correction_due and self.matcher is not None and not warmup_assumed_stationary:
            correction_attempted = True
            self._local_correction_requested = False
            transformed = transform_feature(
                current,
                self._local_player_hint or frame.local_player,
                angle=transform.angle_degrees,
                reflect_horizontal=transform.reflect_horizontal,
                scale=transform.scale,
            )
            match = self.matcher.match(
                transformed.mask,
                origin=predicted.translation,
                radius=self.correction_radius,
            )
            origin = getattr(match, "frame_origin_global", None)
            if bool(getattr(match, "valid", False)) and origin is not None:
                predicted = SimilarityTransform2D(
                    transform.angle_degrees,
                    transform.reflect_horizontal,
                    transform.scale,
                    (float(origin[0]), float(origin[1])),
                )
                if shift is None:
                    shift = self._screen_shift_from_translation(transform, predicted)
                self._frames_since_correction = 0
            elif shift is None:
                return self._failed("wall_and_local_match_failed", displacement.quality, frame, True)
        elif shift is None:
            return self._failed(displacement.reason, displacement.quality, frame)

        self._transform = predicted
        self._frame = frame
        self._failures = 0
        active_hints = {
            identity: hint for identity, hint in (prediction_hints or {}).items()
            if identity in self._screen_positions
            and 0 <= frame.captured_at_ms - hint.predicted_at_ms <= 700
            and 0 <= hint.uncertainty_native <= 12.0
            and all(math.isfinite(value) for value in hint.native_position)
        }
        screen_hints = {
            identity: inverse_transform_local_point(
                frame.wall_mask.shape, hint.native_position,
                angle=predicted.angle_degrees,
                reflect_horizontal=predicted.reflect_horizontal,
                scale=predicted.scale, translation=predicted.translation,
            )
            for identity, hint in active_hints.items()
        }
        assigned, ambiguous = self._assign(
            candidates, shift or (0.0, 0.0), screen_hints, frame.captured_at_ms,
        )
        first_live_frame = self._first_live_frame_pending
        self._first_live_frame_pending = False
        self._screen_positions = {
            identity: (point[0] + (shift or (0.0, 0.0))[0], point[1] + (shift or (0.0, 0.0))[1])
            for identity, point in self._screen_positions.items()
        }
        observations = {}
        accepted = {}
        for identity in self._screen_positions:
            candidate = assigned.get(identity)
            native_candidate = (
                transform_local_point(
                    frame.wall_mask.shape, candidate,
                    angle=predicted.angle_degrees,
                    reflect_horizontal=predicted.reflect_horizontal,
                    scale=predicted.scale,
                    translation=predicted.translation,
                )
                if candidate is not None else None
            )
            if first_live_frame and native_candidate is not None:
                # Registration may finish seconds after its screenshot. Only
                # a freshly matched live marker can renew that old anchor.
                self._observations.seed(
                    identity, native_candidate, at_ms=frame.captured_at_ms,
                )
            observation = self._observations.update(
                identity, at_ms=frame.captured_at_ms, candidate=native_candidate,
                reacquisition_reference=(
                    active_hints[identity].native_position if identity in active_hints else None
                ),
                reacquisition_radius=(
                    max(3.0, active_hints[identity].uncertainty_native * 1.5)
                    if identity in active_hints else None
                ),
            )
            observations[identity] = observation
            if observation.visible and candidate is not None:
                accepted[identity] = candidate
        self._screen_positions.update(accepted)
        self._screen_positions.update({
            identity: point for identity, point in screen_hints.items()
            if identity not in accepted
        })
        if self._local_player_identity in accepted:
            self._local_player_hint = accepted[self._local_player_identity]
        elif self._local_player_hint is not None:
            self._local_player_hint = (
                self._local_player_hint[0] + (shift or (0.0, 0.0))[0],
                self._local_player_hint[1] + (shift or (0.0, 0.0))[1],
            )
        for identity in self._screen_positions:
            if identity in accepted:
                self._identity_dropout_failures[identity] = 0
            else:
                self._identity_dropout_failures[identity] = (
                    self._identity_dropout_failures.get(identity, 0) + 1
                )
        self._marker_dropout_failures = max(
            self._identity_dropout_failures.values(), default=0
        )
        expired = tuple(
            identity for identity, item in observations.items()
            if not item.available and identity not in active_hints
        )
        if expired:
            self._failures = max(self._failures, self.max_failures - 1)
            return self._failed(
                "markers_ambiguous" if ambiguous else "markers_missing",
                displacement.quality,
                frame,
                correction_attempted,
                diagnostics={
                    "expired_marker_identities": expired,
                    "identity_dropout_failures": dict(self._identity_dropout_failures),
                    "role_observations": self._observation_diagnostics(observations),
                    "observation_bounds": {
                        "max_age_ms": self.marker_hold_ms,
                        "max_uncertainty_native": self.marker_max_uncertainty,
                    },
                    "assignment": self._last_assignment,
                },
            )
        # Keep predicted positions for identities that are briefly missing.
        # A partial observation must not turn the other role into ``None``:
        # callers may be controlling that role and need a bounded estimate
        # until its marker returns or the per-identity grace is exceeded.
        players = {
            identity: (
                active_hints[identity].native_position
                if not item.visible and identity in active_hints else item.position
            )
            for identity, item in observations.items()
        }
        if accepted and len(accepted) == len(self._screen_positions) and not ambiguous:
            reason = "visual"
            status = "tracking"
        elif accepted:
            reason = "markers_ambiguous" if ambiguous else "markers_partial_grace"
            status = "degraded"
        else:
            reason = "markers_ambiguous" if ambiguous else "markers_missing_grace"
            # Warmup preserves the map estimate, not a fresh player observation.
            # Program control must treat this frame as degraded.
            status = "degraded"
        return self._state(
            status, reason,
            players, displacement.quality, correction_attempted,
            {
                "wall_shift": shift,
                "wall_prediction_hold": wall_prediction_hold,
                "visible_identities": tuple(accepted),
                "prediction_active": any(not item.visible for item in observations.values()),
                "prediction_reason": "marker_observation_gap"
                if any(not item.visible for item in observations.values()) else "",
                "prediction_age_ms": {
                    identity: int(item.age_ms)
                    for identity, item in observations.items()
                    if not item.visible
                },
                "wall_trusted": True,
                "role_observations": self._observation_diagnostics(observations),
                "observation_bounds": {
                    "max_age_ms": self.marker_hold_ms,
                    "max_uncertainty_native": self.marker_max_uncertainty,
                },
                "assignment": self._last_assignment,
                "warmup_assumed_stationary": warmup_assumed_stationary,
                "marker_dropout_failures": self._marker_dropout_failures,
                "marker_dropout_grace": self.marker_dropout_grace,
                "identity_dropout_failures": dict(self._identity_dropout_failures),
                "missing_identities": tuple(
                    identity
                    for identity in self._screen_positions
                    if identity not in accepted
                ),
                "prediction_hint_identities": tuple(active_hints),
                "local_player_hint": self._local_player_hint,
            },
        )

    @staticmethod
    def _screen_shift_from_translation(
        previous: SimilarityTransform2D,
        current: SimilarityTransform2D,
    ) -> tuple[float, float]:
        axis_x = transform_local_displacement(
            (1.0, 0.0), angle_degrees=previous.angle_degrees,
            reflect_horizontal=previous.reflect_horizontal, scale=previous.scale,
        )
        axis_y = transform_local_displacement(
            (0.0, 1.0), angle_degrees=previous.angle_degrees,
            reflect_horizontal=previous.reflect_horizontal, scale=previous.scale,
        )
        determinant = axis_x[0] * axis_y[1] - axis_x[1] * axis_y[0]
        map_shift = (
            previous.translation[0] - current.translation[0],
            previous.translation[1] - current.translation[1],
        )
        return (
            (map_shift[0] * axis_y[1] - map_shift[1] * axis_y[0]) / determinant,
            (axis_x[0] * map_shift[1] - axis_x[1] * map_shift[0]) / determinant,
        )

    @staticmethod
    def _observation_diagnostics(observations: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
        return {
            identity: {
                "visible": item.visible,
                "available": item.available,
                "last_seen_at_ms": item.last_seen_at_ms,
                "age_ms": item.age_ms,
                "uncertainty_native": item.uncertainty,
            }
            for identity, item in observations.items()
        }

    def _assign(
        self,
        candidates: Sequence[PlayerMarkerCandidate],
        wall_shift: tuple[float, float],
        screen_hints: Mapping[str, tuple[float, float]] | None = None,
        captured_at_ms: int | None = None,
    ) -> tuple[dict[str, tuple[float, float]], bool]:
        predicted = {
            identity: (screen_hints[identity] if screen_hints and identity in screen_hints
                       else (point[0] + wall_shift[0], point[1] + wall_shift[1]))
            for identity, point in self._screen_positions.items()
        }
        now = int(captured_at_ms or 0)
        elapsed = {
            identity: max(0, now - self._last_assignment_at_ms.get(identity, now))
            for identity in predicted
        }
        result = self._marker_associator.assign(
            candidates,
            predicted,
            identity_hints=self._identity_hints,
            velocities=self._screen_velocities,
            elapsed_ms=elapsed,
            wall_shift=wall_shift,
        )
        self._last_assignment = dict(result.diagnostics)
        if result.assignment and now:
            for identity, point in result.assignment.items():
                previous = self._screen_positions.get(identity)
                if previous is not None:
                    dt = max(1, now - self._last_assignment_at_ms.get(identity, now)) / 1000.0
                    self._screen_velocities[identity] = (
                        (point[0] - previous[0] - wall_shift[0]) / dt,
                        (point[1] - previous[1] - wall_shift[1]) / dt,
                    )
                self._last_assignment_at_ms[identity] = now
        return dict(result.assignment), result.ambiguous

    def _map_players(
        self, visible: Mapping[str, tuple[float, float]]
    ) -> dict[str, tuple[float, float] | None]:
        assert self._frame is not None and self._transform is not None
        transform = self._transform
        return {
            identity: (
                transform_local_point(
                    self._frame.wall_mask.shape,
                    visible[identity],
                    angle=transform.angle_degrees,
                    reflect_horizontal=transform.reflect_horizontal,
                    scale=transform.scale,
                    translation=transform.translation,
                )
                if identity in visible else None
            )
            for identity in self._screen_positions
        }

    @staticmethod
    def _wall_frame_can_be_held(previous: np.ndarray, current: np.ndarray) -> bool:
        """Return whether a frame can safely reuse the previous transform."""
        previous_pixels = int(np.count_nonzero(previous))
        current_pixels = int(np.count_nonzero(current))
        if previous_pixels <= 0 or current_pixels <= 0:
            return False
        ratio = current_pixels / max(previous_pixels, 1)
        return 0.15 <= ratio <= 6.0

    def _fallback_players(self) -> dict[str, tuple[float, float] | None]:
        if self._frame is None or self._transform is None:
            return {identity: None for identity in self._screen_positions}
        return self._map_players(self._screen_positions)

    def _prediction_diagnostics(self, frame: HybridFrame, reason: str) -> dict[str, Any]:
        ages = {
            identity: max(0, int(frame.captured_at_ms) - int(last_seen))
            for identity, last_seen in self._last_assignment_at_ms.items()
        }
        return {
            "prediction_active": True,
            "prediction_reason": reason,
            "prediction_age_ms": ages,
        }

    def _failed(
        self,
        reason: str,
        quality: float,
        frame: HybridFrame,
        corrected: bool = False,
        diagnostics: Mapping[str, Any] | None = None,
    ) -> DualMotionState:
        self._failures += 1
        if self._failures < self.max_failures:
            players = self._fallback_players()
            payload = self._prediction_diagnostics(frame, reason)
            if diagnostics:
                payload.update(diagnostics)
            return self._state("degraded", reason, players, quality, corrected, payload)
        first_request = not self._recovery_emitted
        if first_request:
            self._recovery_revision += 1
            self._recovery_emitted = True
        players = self._fallback_players()
        payload = {
            "failed_frame_id": frame.frame_id,
            **self._prediction_diagnostics(frame, reason),
            **(diagnostics or {}),
        }
        return self._state(
            "recovery_required",
            reason,
            players,
            quality,
            corrected,
            payload,
            first_request,
        )

    def _state(
        self,
        status: str,
        reason: str,
        players: Mapping[str, tuple[float, float] | None],
        quality: float = 0.0,
        correction_attempted: bool = False,
        diagnostics: Mapping[str, Any] | None = None,
        recovery_requested: bool = False,
    ) -> DualMotionState:
        return DualMotionState(
            status, reason,
            {identity: players.get(identity) for identity in self._screen_positions},
            self._transform,
            {identity: self._screen_positions.get(identity) for identity in self._screen_positions},
            float(quality), correction_attempted, recovery_requested,
            self._recovery_revision,
            {"consecutive_wall_failures": self._failures, **(diagnostics or {})},
        )


__all__ = ["DualMotionState", "DualVisualTracker", "RolePredictionHint"]
