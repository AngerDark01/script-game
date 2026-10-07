"""Explicit program-output gate for the experimental follow runtime.

This adapter is deliberately separate from planning and localization. It does
not acquire a gamepad by itself; callers must bind an already-created
``ProgramGamepadOutput`` and explicitly arm each role.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import logging
import time

from .models import FollowObservation, FollowState, RoleId


_LOGGER = logging.getLogger(__name__)


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
        continuous_roles: set[RoleId] | frozenset[RoleId] | tuple[RoleId, ...] = (),
    ) -> None:
        self._bindings = {role.key: _Binding(role, output) for role, output in outputs.items()}
        self._armed: set[str] = set()
        self._continuous_roles = frozenset(role.key for role in continuous_roles)
        if vector_transform is not None and not callable(vector_transform):
            raise TypeError("vector_transform must be callable or None")
        self._vector_transform = vector_transform
        self._rearm_counts: dict[str, int] = {}
        self._last_rearm_at: dict[str, float] = {}
        self._last_timing: dict[str, float] = {
            "arm_ms": 0.0, "write_ms": 0.0, "neutral_write_ms": 0.0,
            "rearm_ms": 0.0, "release_ms": 0.0,
        }

    def arm(self, role: RoleId) -> None:
        started = time.perf_counter()
        binding = self._require(role)
        if role.key in self._armed:
            return
        binding.output.start()
        self._armed.add(role.key)
        self._last_timing["arm_ms"] = (time.perf_counter() - started) * 1000.0

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
            started = time.perf_counter()
            result = self._write(binding, vector, elapsed_ms=elapsed_ms)
            self._last_timing["write_ms"] = (time.perf_counter() - started) * 1000.0
            return result
        # Send a neutral frame before a hard stop releases the lease, so a
        # stale stick value cannot survive a localization or map failure.
        started = time.perf_counter()
        self._write(binding, (0.0, 0.0), elapsed_ms=elapsed_ms)
        self._last_timing["neutral_write_ms"] = (time.perf_counter() - started) * 1000.0
        if (
            observation.state in self._STOP_STATES
            and observation.follower.key not in self._continuous_roles
        ):
            self.release(observation.follower)

    def release(self, role: RoleId) -> None:
        started = time.perf_counter()
        binding = self._require(role)
        if role.key in self._armed:
            binding.output.stop()
            self._armed.discard(role.key)
        self._rearm_counts.pop(role.key, None)
        self._last_rearm_at.pop(role.key, None)
        self._last_timing["release_ms"] = (time.perf_counter() - started) * 1000.0

    def release_all(self, *, force: bool = False) -> None:
        """Neutralize active outputs, releasing only non-continuous roles.

        A live-follow session owns a continuous role until the user stops it.
        Recovery, foreground gates, and transient runtime faults therefore
        send a neutral frame while retaining that role's lease. ``close_all``
        passes ``force=True`` for the explicit session shutdown path.
        """
        for key in tuple(self._armed):
            binding = self._bindings[key]
            if not force and key in self._continuous_roles:
                self._write(binding, (0.0, 0.0), elapsed_ms=20)
            else:
                self.release(binding.role)

    def close_all(self) -> None:
        """Release every role and close only outputs owned by this session."""
        first_error: Exception | None = None
        try:
            self.release_all(force=True)
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
            result[binding.role.key]["timing_ms"] = dict(self._last_timing)
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
            result[binding.role.key]["timing_ms"] = dict(self._last_timing)
        return result

    def _write(self, binding: _Binding, vector: tuple[float, float], *, elapsed_ms: int):
        """Write a pulse and transparently re-arm one expired Host session."""
        try:
            return binding.output.write(vector, elapsed_ms=elapsed_ms)
        except Exception as exc:
            message = str(exc).lower()
            session_expired = (
                "session expired" in message
                or "session" in message and "revoked" in message
                or "explicit start is required" in message
            )
            if not session_expired:
                raise
            key = binding.role.key
            rearm = getattr(binding.output, "rearm", None)
            if not callable(rearm):
                raise
            now = time.monotonic()
            last = self._last_rearm_at.get(key, 0.0)
            if now - last < 0.5:
                # The independent output heartbeat may already be rebuilding
                # the lease. Do not hammer Host or write the stale token.
                return None
            self._last_rearm_at[key] = now
            self._rearm_counts[key] = self._rearm_counts.get(key, 0) + 1
            rearm_started = time.perf_counter()
            try:
                rearm()
            except Exception:
                _LOGGER.exception("program_output.rearm_failed role=%s", key)
                return None
            self._last_timing["rearm_ms"] = (time.perf_counter() - rearm_started) * 1000.0
            return binding.output.write(vector, elapsed_ms=elapsed_ms)

    def _require(self, role: RoleId) -> _Binding:
        try:
            return self._bindings[role.key]
        except KeyError as exc:
            raise KeyError(role.key) from exc


__all__ = ["ProgramFollowOutput"]
