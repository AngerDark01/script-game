"""Independent gates for accepting a multi-frame absolute registration."""

from __future__ import annotations

from dataclasses import dataclass
import math
from types import MappingProxyType
from typing import Mapping, Sequence

import numpy as np

from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.models import (
    AbsoluteRegistration,
    PositionAnchor,
)

from .models import MultiFrameEvidence
from .shape_registration import transform_points


@dataclass(frozen=True)
class RegistrationDecision:
    confirmed: bool
    reason: str
    candidate: AbsoluteRegistration | None
    diagnostics: Mapping[str, float]

    def __post_init__(self) -> None:
        object.__setattr__(self, "diagnostics", MappingProxyType(dict(self.diagnostics)))


class RegistrationValidator:
    def __init__(
        self,
        *,
        min_support_frames: int = 3,
        max_anchor_error: float = 8.0,
        max_holdout_error: float = 2.5,
        min_candidate_margin: float = 0.05,
        max_trajectory_error: float = 3.0,
        max_peer_position_delta: float = 8.0,
        max_peer_angle_delta: float = 8.0,
    ) -> None:
        if min_support_frames < 1:
            raise ValueError("min_support_frames must be positive")
        limits = (
            max_anchor_error,
            max_holdout_error,
            max_trajectory_error,
            max_peer_position_delta,
            max_peer_angle_delta,
        )
        if any(float(value) <= 0 for value in limits) or min_candidate_margin < 0:
            raise ValueError("registration validation limits are invalid")
        self.min_support_frames = int(min_support_frames)
        self.max_anchor_error = float(max_anchor_error)
        self.max_holdout_error = float(max_holdout_error)
        self.min_candidate_margin = float(min_candidate_margin)
        self.max_trajectory_error = float(max_trajectory_error)
        self.max_peer_position_delta = float(max_peer_position_delta)
        self.max_peer_angle_delta = float(max_peer_angle_delta)

    def validate(
        self,
        candidate: AbsoluteRegistration,
        *,
        anchor: PositionAnchor,
        frames: Sequence[MultiFrameEvidence],
        support_frames: Sequence[int],
        holdout_error: float,
        best_error: float,
        second_error: float | None = None,
        peer: AbsoluteRegistration | None = None,
    ) -> RegistrationDecision:
        diagnostics: dict[str, float] = {}
        if candidate.area_instance != anchor.area_instance:
            return RegistrationDecision(False, "instance_mismatch", None, diagnostics)
        if len(set(int(value) for value in support_frames)) < self.min_support_frames:
            return RegistrationDecision(False, "insufficient_support", None, diagnostics)
        if not frames:
            return RegistrationDecision(False, "insufficient_support", None, diagnostics)

        first = frames[0]
        local_player = np.array(
            [[
                first.frame.local_player[0] + first.local_offset[0],
                first.frame.local_player[1] + first.local_offset[1],
            ]],
            dtype=np.float64,
        )
        mapped_anchor = transform_points(local_player, candidate.transform)[0]
        anchor_error = float(np.linalg.norm(mapped_anchor - np.asarray(anchor.position)))
        if candidate.result.position is not None:
            anchor_error = max(
                anchor_error,
                float(math.dist(candidate.result.position, anchor.position)),
            )
        diagnostics["anchor_error"] = anchor_error
        allowed_anchor_error = self.max_anchor_error * max(0.5, 2.0 - anchor.confidence)
        if anchor_error > allowed_anchor_error:
            return RegistrationDecision(False, "anchor_uncertainty", None, diagnostics)

        trajectory_errors: list[float] = []
        for previous, current in zip(frames, frames[1:]):
            if current.motion.shift is None:
                continue
            actual = np.asarray(current.local_offset) - np.asarray(previous.local_offset)
            expected = -np.asarray(current.motion.shift, dtype=np.float64)
            trajectory_errors.append(float(np.linalg.norm(actual - expected)) * candidate.transform.scale)
        trajectory_error = max(trajectory_errors, default=0.0)
        diagnostics["trajectory_error"] = trajectory_error
        if trajectory_error > self.max_trajectory_error:
            return RegistrationDecision(False, "trajectory_error", None, diagnostics)

        diagnostics["holdout_error"] = float(holdout_error)
        if not math.isfinite(float(holdout_error)) or holdout_error > self.max_holdout_error:
            return RegistrationDecision(False, "holdout_error", None, diagnostics)

        margin = float("inf") if second_error is None else float(second_error) - float(best_error)
        diagnostics["candidate_margin"] = margin
        if second_error is not None and margin < self.min_candidate_margin:
            return RegistrationDecision(False, "candidate_ambiguous", None, diagnostics)

        if peer is not None:
            candidate_position = candidate.result.position
            peer_position = peer.result.position
            if candidate_position is None or peer_position is None:
                return RegistrationDecision(False, "strategy_missing_position", None, diagnostics)
            position_delta = math.dist(candidate_position, peer_position)
            angle_delta = abs(
                (candidate.transform.angle_degrees - peer.transform.angle_degrees + 180.0)
                % 360.0
                - 180.0
            )
            diagnostics["peer_position_delta"] = position_delta
            diagnostics["peer_angle_delta"] = angle_delta
            if (
                candidate.transform.reflect_horizontal != peer.transform.reflect_horizontal
                or position_delta > self.max_peer_position_delta
                or angle_delta > self.max_peer_angle_delta
            ):
                return RegistrationDecision(False, "strategy_conflict", None, diagnostics)

        return RegistrationDecision(True, "confirmed", candidate, diagnostics)


__all__ = ["RegistrationDecision", "RegistrationValidator"]
