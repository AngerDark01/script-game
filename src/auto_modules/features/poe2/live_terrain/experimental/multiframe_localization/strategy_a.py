"""Strategy A: register a bounded stitched submap after evidence is sufficient."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Sequence

import numpy as np

from auto_modules.core.localization import transform_local_displacement
from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.models import HybridFrame, PositionAnchor

from .evidence_window import EvidenceWindow
from .models import MultiFrameEvidence
from .rolling_submap import RollingSubmap, SubmapSnapshot
from .shape_registration import score_shape


@dataclass(frozen=True)
class StrategyResult:
    status: str
    evidence_version: int
    candidate: Any | None = None
    reason: str = ""
    source: str = "strategy_a"
    holdout_error: float = 0.0
    support_frames: tuple[int, ...] = ()
    best_error: float = 0.0
    second_error: float | None = None

    @classmethod
    def insufficient(cls, version: int, reason: str) -> "StrategyResult":
        return cls("insufficient_evidence", version, reason=reason)

    @classmethod
    def rejected(cls, version: int, reason: str) -> "StrategyResult":
        return cls("rejected", version, reason=reason)

    @classmethod
    def confirmed(cls, version: int, candidate: Any) -> "StrategyResult":
        return cls("confirmed", version, candidate=candidate)


@dataclass(frozen=True)
class SubmapThresholds:
    min_frames: int = 4
    min_wall_pixels: int = 80
    min_span: float = 12.0

    def ready(self, snapshot: SubmapSnapshot, frames: Sequence[Any]) -> bool:
        if len(frames) < self.min_frames:
            return False
        if int((snapshot.wall_mask > 0).sum()) < self.min_wall_pixels or len(frames) < 2:
            return False
        xs = [float(item.local_offset[0]) for item in frames]
        ys = [float(item.local_offset[1]) for item in frames]
        return max(max(xs) - min(xs), max(ys) - min(ys)) >= self.min_span


class StitchThenRegister:
    def __init__(
        self,
        registrar: Any,
        *,
        thresholds: SubmapThresholds | None = None,
        validator: Any | None = None,
        require_holdout: bool = True,
        max_holdout_error: float = 2.5,
        min_holdout_coverage: float = 0.50,
    ) -> None:
        self.registrar = registrar
        self.thresholds = thresholds or SubmapThresholds()
        self.validator = validator
        self.require_holdout = bool(require_holdout)
        self.max_holdout_error = float(max_holdout_error)
        self.min_holdout_coverage = float(min_holdout_coverage)
        if self.max_holdout_error <= 0 or not 0 <= self.min_holdout_coverage <= 1:
            raise ValueError("invalid holdout thresholds")
        self._last_attempt_version = -1

    def reset(self) -> None:
        """Forget attempt fencing when a session starts a new evidence run."""
        self._last_attempt_version = -1

    @property
    def minimum_evidence_frames(self) -> int:
        """Return the keyframe count needed before registration is useful.

        A holdout frame is part of Strategy A's acceptance contract, so it is
        collected in addition to the training threshold.
        """
        return int(self.thresholds.min_frames) + (1 if self.require_holdout else 0)

    def evaluate(
        self,
        window: EvidenceWindow,
        submap: RollingSubmap,
        *,
        anchor: PositionAnchor,
        reference: Any,
    ) -> StrategyResult:
        frames = window.snapshot()
        if self.require_holdout and len(frames) <= self.thresholds.min_frames:
            return StrategyResult.insufficient(window.version, "holdout_frame_required")
        training = frames[:-1] if self.require_holdout else frames
        holdout_frame = frames[-1] if self.require_holdout else None
        snapshot = submap.rebuild(training)
        if not self.thresholds.ready(snapshot, training):
            return StrategyResult.insufficient(window.version, "structure_below_threshold")
        if window.version == self._last_attempt_version:
            return StrategyResult.rejected(window.version, "evidence_version_already_attempted")
        self._last_attempt_version = window.version
        register = getattr(self.registrar, "register_submap", None)
        if callable(register):
            candidate = register(snapshot, anchor=anchor, reference=reference)
        else:
            register_frame = getattr(self.registrar, "register", None)
            if not callable(register_frame) or not training:
                return StrategyResult.rejected(window.version, "registrar_missing_submap_contract")
            first = training[0]
            local_player = (
                first.frame.local_player[0] + first.local_offset[0] - snapshot.origin[0],
                first.frame.local_player[1] + first.local_offset[1] - snapshot.origin[1],
            )
            synthetic = HybridFrame(
                frame_id=first.frame.frame_id,
                captured_at_ms=first.frame.captured_at_ms,
                wall_mask=snapshot.wall_mask,
                local_player=local_player,
                diagnostics={"multiframe_submap_origin": snapshot.origin, "source_frames": snapshot.frame_ids},
            )
            candidate = register_frame(synthetic, reference=reference, anchor=anchor)
        if candidate is None:
            return StrategyResult.rejected(window.version, "registration_failed")
        holdout_error = 0.0
        if holdout_frame is not None:
            holdout_score = self._holdout_score(candidate, holdout_frame, snapshot, reference)
            holdout_error = float(holdout_score.forward_error)
            if not (
                holdout_score.usable_points > 0
                and holdout_score.forward_error <= self.max_holdout_error
                and holdout_score.forward_coverage >= self.min_holdout_coverage
            ):
                return StrategyResult.rejected(window.version, "holdout_failed")
        holdout = getattr(self.validator, "holdout", None)
        if callable(holdout) and not holdout(candidate, frames):
            return StrategyResult.rejected(window.version, "holdout_failed")
        return StrategyResult(
            "confirmed",
            window.version,
            candidate=candidate,
            holdout_error=holdout_error,
            support_frames=tuple(item.frame.frame_id for item in frames),
        )

    def _holdout_score(self, candidate: Any, holdout: MultiFrameEvidence, snapshot: SubmapSnapshot, reference: Any):
        transform = getattr(candidate, "transform", None)
        if transform is None:
            raise ValueError("registration candidate has no transform")
        local_offset = (
            holdout.local_offset[0] - snapshot.origin[0],
            holdout.local_offset[1] - snapshot.origin[1],
        )
        native_offset = transform_local_displacement(
            local_offset,
            angle_degrees=transform.angle_degrees,
            reflect_horizontal=transform.reflect_horizontal,
            scale=transform.scale,
        )
        shifted = replace(
            transform,
            translation=(transform.translation[0] + native_offset[0], transform.translation[1] + native_offset[1]),
        )
        boundary = getattr(reference, "wall_layer", reference)
        try:
            from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.absolute_registrar import reference_boundary_layer
            if hasattr(reference, "walkable_mask"):
                boundary = reference_boundary_layer(reference)
        except (ImportError, TypeError, ValueError):
            pass
        return score_shape(
            wall_mask=holdout.frame.wall_mask,
            observed_mask=holdout.observed_mask,
            reference_boundary=np.asarray(boundary),
            transform=shifted,
        )


__all__ = ["StitchThenRegister", "StrategyResult", "SubmapThresholds"]
