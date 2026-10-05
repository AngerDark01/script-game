"""Explicit program-output gate for the experimental follow runtime.

This adapter is deliberately separate from planning and localization. It does
not acquire a gamepad by itself; callers must bind an already-created
``ProgramGamepadOutput`` and explicitly arm each role.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from .models import FollowObservation, FollowState, RoleId


@dataclass
class _Binding:
    role: RoleId
    output: object


class ProgramFollowOutput:
    """Map per-role follow observations to independently leased outputs."""

    _STOP_STATES = frozenset(
        {
            FollowState.ARRIVED,
            FollowState.WAITING_POSITION,
            FollowState.BLOCKED,
            FollowState.MAP_MISMATCH,
            FollowState.MANUAL,
        }
    )

    def __init__(
        self,
        outputs: Mapping[RoleId, object],
        *,
        vector_transform: Callable[[tuple[float, float]], tuple[float, float]] | None = None,
    ) -> None:
        self._bindings = {role.key: _Binding(role, output) for role, output in outputs.items()}
        self._armed: set[str] = set()
        if vector_transform is not None and not callable(vector_transform):
            raise TypeError("vector_transform must be callable or None")
        self._vector_transform = vector_transform

    def arm(self, role: RoleId) -> None:
        binding = self._require(role)
        if role.key in self._armed:
            return
        binding.output.start()
        self._armed.add(role.key)

    def apply(self, observation: FollowObservation, *, elapsed_ms: int = 20):
        binding = self._require(observation.follower)
        if observation.follower.key not in self._armed:
            return
        if observation.state is FollowState.PROGRAM_READY and observation.vector != (0.0, 0.0):
            vector = observation.vector
            if self._vector_transform is not None:
                vector = self._vector_transform(vector)
            command_duration = observation.diagnostics.get("command_duration_ms")
            if isinstance(command_duration, (int, float)) and command_duration > 0:
                # Closed-loop pulses carry their own bounded duration.  The
                # UI timer is only a scheduling cadence and can be different
                # from the pulse that was selected by the controller.
                elapsed_ms = max(1, min(300, int(round(command_duration))))
            return binding.output.write(vector, elapsed_ms=elapsed_ms)
        # Send a neutral frame before a hard stop releases the lease, so a
        # stale stick value cannot survive a localization or map failure.
        binding.output.write((0.0, 0.0), elapsed_ms=elapsed_ms)
        if observation.state in self._STOP_STATES:
            self.release(observation.follower)

    def release(self, role: RoleId) -> None:
        binding = self._require(role)
        if role.key in self._armed:
            binding.output.stop()
            self._armed.discard(role.key)

    def release_all(self) -> None:
        for key in tuple(self._armed):
            self.release(self._bindings[key].role)

    def close_all(self) -> None:
        """Release every role and close only outputs owned by this session."""
        first_error: Exception | None = None
        try:
            self.release_all()
        except Exception as exc:
            first_error = exc
        finally:
            for binding in self._bindings.values():
                close = getattr(binding.output, "close", None)
                if callable(close):
                    try:
                        close()
                    except Exception as exc:
                        first_error = first_error or exc
        if first_error is not None:
            raise first_error

    def is_armed(self, role: RoleId) -> bool:
        self._require(role)
        return role.key in self._armed

    def diagnostics(self) -> dict[str, dict]:
        """Read output-boundary state for the currently armed roles."""
        result: dict[str, dict] = {}
        for binding in self._bindings.values():
            reader = getattr(binding.output, "diagnostics", None)
            if callable(reader):
                result[binding.role.key] = reader()
            else:
                result[binding.role.key] = {
                    "controller": getattr(binding.output, "controller", None),
                    "acquired": binding.role.key in self._armed,
                }
        return result

    def snapshot(self) -> dict[str, dict]:
        """Return per-role local output state without querying the Host."""
        result: dict[str, dict] = {}
        for binding in self._bindings.values():
            reader = getattr(binding.output, "snapshot", None)
            if callable(reader):
                result[binding.role.key] = reader()
            else:
                result[binding.role.key] = {
                    "controller": getattr(binding.output, "controller", None),
                    "acquired": binding.role.key in self._armed,
                }
            result[binding.role.key]["armed"] = binding.role.key in self._armed
        return result

    def _require(self, role: RoleId) -> _Binding:
        try:
            return self._bindings[role.key]
        except KeyError as exc:
            raise KeyError(role.key) from exc


__all__ = ["ProgramFollowOutput"]
