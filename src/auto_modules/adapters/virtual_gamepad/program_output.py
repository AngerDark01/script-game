"""Exclusive program output over the concrete virtual-gamepad Host protocol."""

from __future__ import annotations

import ctypes
import logging
import os
import time
from dataclasses import dataclass
from math import hypot, isfinite

from auto_modules.core.actions.gamepad_motion import StickSlewLimiter


_LOGGER = logging.getLogger(__name__)


def host_clock_ms() -> int:
    """Return the Host-compatible same-machine monotonic clock."""
    if os.name == "nt":
        get_ticks = ctypes.windll.kernel32.GetTickCount64
        get_ticks.restype = ctypes.c_ulonglong
        return int(get_ticks())
    return int(time.monotonic() * 1000)


def _host_tick_after_local_stop() -> int:
    """Return a Host clock tick strictly after the preceding pause response.

    The Host fences ``program.acquire`` against the timestamp recorded when
    ``pause`` revokes a previous lease.  Both calls can complete in the same
    millisecond, so returning the current tick immediately can be rejected as
    stale even though the request was issued after the pause response.
    """
    observed = host_clock_ms()
    deadline = time.monotonic() + 0.05
    while True:
        current = host_clock_ms()
        if current > observed or time.monotonic() >= deadline:
            return current
        time.sleep(0.001)


@dataclass(frozen=True, slots=True)
class AppliedProgramState:
    accepted_at_ms: int
    effective_input_vector: tuple[float, float]
    effective_axes: tuple[int, int]
    ttl_ms: int


class ProgramGamepadOutput:
    """Own one explicit program-output lease without changing user mappings."""

    def __init__(
        self,
        client,
        *,
        controller,
        basis=(1.0, 0.0, 0.0, -1.0),
        ttl_ms=120,
        slew_rate=180_000.0,
    ):
        if controller not in (1, 2) or not 1 <= ttl_ms <= 300:
            raise ValueError("invalid controller or TTL")
        if not isfinite(float(slew_rate)) or float(slew_rate) <= 0.0:
            raise ValueError("slew_rate must be positive and finite")
        if (
            len(basis) != 4
            or not all(isfinite(value) for value in basis)
            or abs(basis[0] * basis[3] - basis[1] * basis[2]) < 1e-9
        ):
            raise ValueError("non-singular finite map-to-stick basis required")
        self.client = client
        self.controller = controller
        self.basis = basis
        self.ttl_ms = ttl_ms
        self.slew_rate = float(slew_rate)
        self.token = None
        self.limiter = StickSlewLimiter(max_delta_per_second=self.slew_rate)
        self._last_host_request_ms = 0.0
        self._last_diagnostics_ms = 0.0
        self._write_count = 0
        self._last_command = {
            "input_vector": (0.0, 0.0),
            "input_magnitude": 0.0,
            "basis_vector": (0.0, 0.0),
            "basis_magnitude": 0.0,
            "axes": (0, 0),
            "axis_magnitude": 0.0,
            "ttl_ms": self.ttl_ms,
            "slew_rate": self.slew_rate,
            "host_request_ms": 0.0,
        }

    def start(self, *, requested_at_ms=None):
        if self.token is not None:
            raise RuntimeError("program output is already acquired")
        # The Host deliberately rejects a program lease while the normal
        # controller lifecycle is running.  Pause first at the adapter
        # boundary so every caller gets the same explicit, fail-closed handoff
        # from manual mapping to program ownership.
        pause = getattr(self.client, "pause", None)
        if callable(pause):
            pause(self.controller)
        request_time = (
            _host_tick_after_local_stop()
            if requested_at_ms is None
            else requested_at_ms
        )
        self.token = self.client.request(
            "program.acquire",
            {
                "controller": self.controller,
                "requestedAtMs": request_time,
            },
        )["token"]
        self.limiter.reset()
        _LOGGER.info(
            "program_output.acquired controller=%s token_present=%s requested_at_ms=%s",
            self.controller, self.token is not None, request_time,
        )

    def write(self, vector, *, elapsed_ms=20, valid_for_ms=None, buttons=0):
        if self.token is None:
            raise RuntimeError("program output is not acquired")
        if len(vector) != 2 or not all(isfinite(value) for value in vector):
            raise ValueError("finite movement vector required")
        a, b, c, d = self.basis
        x = a * vector[0] + b * vector[1]
        y = c * vector[0] + d * vector[1]
        norm = max(1.0, hypot(x, y))
        if x == y == 0:
            axes = self.limiter.reset()
        else:
            axes = self.limiter.update(
                round(x / norm * 32767),
                round(y / norm * 32767),
                elapsed_ms=min(50, max(0, int(elapsed_ms))),
            )
        ttl = self.ttl_ms if valid_for_ms is None else min(self.ttl_ms, int(valid_for_ms))
        if ttl <= 0:
            axes, buttons, ttl = self.limiter.reset(), 0, self.ttl_ms
        command = {
            "input_vector": (float(vector[0]), float(vector[1])),
            "input_magnitude": float(hypot(vector[0], vector[1])),
            "basis_vector": (float(x), float(y)),
            "basis_magnitude": float(hypot(x, y)),
            "axes": tuple(int(value) for value in axes),
            "axis_magnitude": float(hypot(axes[0], axes[1]) / 32767.0),
            "ttl_ms": int(ttl),
            "slew_rate": self.slew_rate,
            "host_request_ms": 0.0,
        }
        deadline_ms = host_clock_ms() + ttl
        request_started = time.perf_counter()
        try:
            response = self.client.request(
                "program.state",
                {
                    "controller": self.controller,
                    "token": self.token,
                    "ttlMs": ttl,
                    "deadlineMs": deadline_ms,
                    "state": {
                        "buttons": buttons,
                        "leftTrigger": 0,
                        "rightTrigger": 0,
                        "leftStickX": axes[0],
                        "leftStickY": axes[1],
                        "rightStickX": 0,
                        "rightStickY": 0,
                    },
                },
            )
        except Exception:
            self._last_host_request_ms = (time.perf_counter() - request_started) * 1000.0
            _LOGGER.exception(
                "program_output.host_request_failed controller=%s elapsed_ms=%.1f",
                self.controller, self._last_host_request_ms,
            )
            raise
        self._last_host_request_ms = (time.perf_counter() - request_started) * 1000.0
        if self._last_host_request_ms >= 50.0:
            _LOGGER.warning(
                "program_output.host_request_slow controller=%s elapsed_ms=%.1f ttl_ms=%s",
                self.controller, self._last_host_request_ms, ttl,
            )
        if isinstance(response, dict) and response.get("accepted") is False:
            raise RuntimeError("Host rejected program state")
        command["host_request_ms"] = round(self._last_host_request_ms, 3)
        self._last_command = command
        self._write_count += 1
        # The Host TTL starts before its response arrives. Count only the
        # remaining lease time, never the requested pulse duration.
        remaining_ms = max(0, deadline_ms - host_clock_ms())
        if self._write_count <= 3 or self._write_count % 20 == 0:
            _LOGGER.info(
                "program_output.accepted controller=%s count=%s axes=%s ttl_ms=%s "
                "remaining_ms=%s host_request_ms=%.1f",
                self.controller, self._write_count, command["axes"], ttl,
                remaining_ms, self._last_host_request_ms,
            )
        accepted_at_ms = int(time.time() * 1000)
        axis_x, axis_y = axes[0] / 32767.0, axes[1] / 32767.0
        determinant = a * d - b * c
        return AppliedProgramState(
            accepted_at_ms,
            ((d * axis_x - b * axis_y) / determinant,
             (-c * axis_x + a * axis_y) / determinant),
            (int(axes[0]), int(axes[1])), remaining_ms,
        )

    def stop(self):
        token, self.token = self.token, None
        self.limiter.reset()
        self._write_count = 0
        self._last_command = {
            "input_vector": (0.0, 0.0),
            "input_magnitude": 0.0,
            "basis_vector": (0.0, 0.0),
            "basis_magnitude": 0.0,
            "axes": (0, 0),
            "axis_magnitude": 0.0,
            "ttl_ms": self.ttl_ms,
            "slew_rate": self.slew_rate,
            "host_request_ms": 0.0,
        }
        if token is not None:
            _LOGGER.info("program_output.released controller=%s", self.controller)
            self.client.request(
                "program.release",
                {"controller": self.controller, "token": token},
            )

    def diagnostics(self) -> dict:
        """Return a read-only snapshot of the Host boundary for diagnostics.

        The request is intentionally explicit and infrequent.  Callers use it
        to distinguish a planner that produced a vector from a Host/backend
        that actually accepted the current program lease and state.
        """
        started = time.perf_counter()
        try:
            status = self.client.status()
            state = self.client.state(self.controller)
        finally:
            self._last_diagnostics_ms = (time.perf_counter() - started) * 1000.0
        if self._last_diagnostics_ms >= 50.0:
            _LOGGER.warning(
                "program_output.diagnostics_slow controller=%s elapsed_ms=%.1f",
                self.controller, self._last_diagnostics_ms,
            )
        return {
            "controller": self.controller,
            "acquired": self.token is not None,
            "basis": tuple(float(value) for value in self.basis),
            "last_command": dict(self._last_command),
            "last_host_request_ms": self._last_host_request_ms,
            "diagnostics_elapsed_ms": self._last_diagnostics_ms,
            "status": status,
            "state": state,
        }

    def snapshot(self) -> dict:
        """Return local output state without an IPC round trip.

        Follow ticks use this lightweight snapshot for per-tick diagnostics.
        ``diagnostics()`` remains the explicit, infrequent Host status probe.
        """
        return {
            "controller": self.controller,
            "acquired": self.token is not None,
            "write_count": self._write_count,
            "last_command": dict(self._last_command),
            "last_host_request_ms": self._last_host_request_ms,
            "ttl_ms": self.ttl_ms,
            "slew_rate": self.slew_rate,
        }

    def close(self):
        """Release the lease and close this output's dedicated Host client."""
        try:
            self.stop()
        finally:
            close = getattr(self.client, "close", None)
            if callable(close):
                close()
