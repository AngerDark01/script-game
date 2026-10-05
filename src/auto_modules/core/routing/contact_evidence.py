"""Game-neutral evidence for detecting commanded motion without progress.

The module deliberately knows nothing about a game, screen colours, or a
controller transport.  Callers provide vectors in one common coordinate
space and may optionally provide a local-obstacle observation from a sensor.
It turns those samples into a small, stable contract that a navigation
runtime can use to enter local recovery or relocalisation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Any


def _vector(value: Any, name: str) -> tuple[float, float]:
    if value is None or len(value) != 2:
        raise ValueError(f"{name} must contain two values")
    result = (float(value[0]), float(value[1]))
    if not all(math.isfinite(item) for item in result):
        raise ValueError(f"{name} must contain finite values")
    return result


def _norm(value: tuple[float, float]) -> float:
    return math.hypot(value[0], value[1])


class ContactState(str, Enum):
    """Generic movement/contact state independent of any device or game."""

    CLEAR = "clear"
    APPROACHING = "approaching"
    CONTACT_CANDIDATE = "contact_candidate"
    RECOVERY = "recovery"
    ESCAPED = "escaped"


@dataclass(frozen=True, slots=True)
class ContactEvidence:
    """One command/observation pair in the same coordinate space."""

    command: tuple[float, float]
    displacement: tuple[float, float]
    elapsed_ms: int
    alignment: float | None
    no_progress: bool
    local_obstacle_ahead: bool | None = None
    local_obstacle_distance: float | None = None
    consecutive_no_progress: int = 0
    recovery_required: bool = False
    reason: str = ""
    state: ContactState = ContactState.CLEAR
    escape_available: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "command", _vector(self.command, "command"))
        object.__setattr__(self, "displacement", _vector(self.displacement, "displacement"))
        elapsed = int(self.elapsed_ms)
        if elapsed <= 0:
            raise ValueError("elapsed_ms must be positive")
        object.__setattr__(self, "elapsed_ms", elapsed)
        if self.alignment is not None:
            alignment = float(self.alignment)
            if not math.isfinite(alignment) or not -1.0 <= alignment <= 1.0:
                raise ValueError("alignment must be between -1 and 1")
            object.__setattr__(self, "alignment", alignment)
        if self.local_obstacle_distance is not None:
            distance = float(self.local_obstacle_distance)
            if not math.isfinite(distance) or distance < 0.0:
                raise ValueError("local_obstacle_distance must be non-negative")
            object.__setattr__(self, "local_obstacle_distance", distance)
        object.__setattr__(self, "consecutive_no_progress", max(0, int(self.consecutive_no_progress)))
        object.__setattr__(self, "state", ContactState(self.state))
        object.__setattr__(self, "escape_available", bool(self.escape_available))


class ContactMonitor:
    """Accumulate bounded no-progress evidence for one controlled actor."""

    def __init__(
        self,
        *,
        command_threshold: float = 0.20,
        displacement_threshold: float = 0.25,
        alignment_threshold: float = 0.20,
        required_samples: int = 2,
    ) -> None:
        if command_threshold <= 0 or displacement_threshold < 0:
            raise ValueError("contact thresholds must be non-negative")
        if not -1.0 <= alignment_threshold <= 1.0 or required_samples < 1:
            raise ValueError("invalid contact monitor thresholds")
        self.command_threshold = float(command_threshold)
        self.displacement_threshold = float(displacement_threshold)
        self.alignment_threshold = float(alignment_threshold)
        self.required_samples = int(required_samples)
        self.consecutive_no_progress = 0
        self.last: ContactEvidence | None = None
        self.state = ContactState.CLEAR

    def reset(self) -> None:
        self.consecutive_no_progress = 0
        self.last = None
        self.state = ContactState.CLEAR

    def observe(
        self,
        command: tuple[float, float],
        displacement: tuple[float, float],
        *,
        elapsed_ms: int,
        local_obstacle_ahead: bool | None = None,
        local_obstacle_distance: float | None = None,
        blocking_obstacle_ahead: bool | None = None,
        escape_available: bool = False,
        route_progress: float = 0.0,
    ) -> ContactEvidence:
        command = _vector(command, "command")
        displacement = _vector(displacement, "displacement")
        command_norm = _norm(command)
        displacement_norm = _norm(displacement)
        route_progress = float(route_progress)
        if not math.isfinite(route_progress) or route_progress < 0.0:
            raise ValueError("route_progress must be non-negative")
        escape_available = bool(escape_available)
        if blocking_obstacle_ahead is None:
            blocking_obstacle_ahead = local_obstacle_ahead
        if blocking_obstacle_ahead is not None:
            blocking_obstacle_ahead = bool(blocking_obstacle_ahead)
        # The evidence contract exposes the semantic blocking result.  Raw
        # sensor rays remain a caller-side diagnostic and must not leak back
        # into the generic contact decision.
        local_obstacle_ahead = blocking_obstacle_ahead
        alignment: float | None = None
        if command_norm > 1e-6 and displacement_norm > 1e-6:
            alignment = max(
                -1.0,
                min(1.0, (command[0] * displacement[0] + command[1] * displacement[1])
                    / (command_norm * displacement_norm)),
            )
        # A substantial observed displacement proves that the actor is moving,
        # even when it is the delayed response to an earlier stick command or
        # the command/native basis is temporarily misaligned.  Treating every
        # low alignment sample as a collision falsely escalates normal motion
        # into wall recovery.  Keep alignment as diagnostic evidence; only a
        # genuinely small displacement can establish contact.
        no_progress = command_norm >= self.command_threshold and (
            displacement_norm < self.displacement_threshold
        )
        made_progress = displacement_norm >= self.displacement_threshold or route_progress > 0.0
        was_contact = self.state in {
            ContactState.CONTACT_CANDIDATE,
            ContactState.RECOVERY,
        }
        # A known open centreline or actual motion invalidates the previous
        # contact sample.  An available escape direction does *not* clear
        # contact: it tells the runtime to keep trying local recovery instead
        # of escalating to global relocalisation.
        if blocking_obstacle_ahead is False or made_progress:
            self.consecutive_no_progress = 0
            self.state = ContactState.ESCAPED if was_contact else ContactState.CLEAR
        elif no_progress:
            self.consecutive_no_progress += 1
            self.state = (
                ContactState.RECOVERY
                if self.consecutive_no_progress >= self.required_samples
                else ContactState.CONTACT_CANDIDATE
            )
        else:
            self.consecutive_no_progress = max(0, self.consecutive_no_progress - 1)
            self.state = (
                ContactState.APPROACHING
                if blocking_obstacle_ahead is True
                else ContactState.CLEAR
            )
        recovery_required = (
            self.consecutive_no_progress >= self.required_samples
            and blocking_obstacle_ahead is True
        )
        if recovery_required and blocking_obstacle_ahead is True:
            reason = "local_obstacle_no_progress"
        elif recovery_required and alignment is not None and alignment < self.alignment_threshold:
            reason = "command_displacement_mismatch"
        elif recovery_required:
            reason = "command_without_progress"
        elif local_obstacle_ahead is True and command_norm >= self.command_threshold:
            reason = "local_obstacle_ahead"
        else:
            reason = "progress_observed" if not no_progress else "progress_pending"
        self.last = ContactEvidence(
            command,
            displacement,
            int(elapsed_ms),
            alignment,
            no_progress,
            local_obstacle_ahead,
            local_obstacle_distance,
            self.consecutive_no_progress,
            recovery_required,
            reason,
            self.state,
            escape_available,
        )
        return self.last


__all__ = ["ContactEvidence", "ContactMonitor", "ContactState"]
