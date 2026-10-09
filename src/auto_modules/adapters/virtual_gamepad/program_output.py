"""Exclusive program output over the concrete virtual-gamepad Host protocol."""

from __future__ import annotations

import ctypes
import logging
import os
import threading
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
        heartbeat_interval_ms=None,
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
        self.heartbeat_interval_ms = int(
            heartbeat_interval_ms if heartbeat_interval_ms is not None
            else min(250, max(50, ttl_ms // 3))
        )
        if not 20 <= self.heartbeat_interval_ms <= 900:
            raise ValueError("heartbeat_interval_ms must be between 20 and 900")
        self._io_lock = threading.RLock()
        self._heartbeat_stop = threading.Event()
        self._heartbeat_thread = None
        self._heartbeat_count = 0
        self._heartbeat_failures = 0
        self._last_heartbeat_ms = 0.0
        self._session_expired = False
        self._heartbeat_mode = "command"
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
        with self._io_lock:
            self._start_locked(requested_at_ms=requested_at_ms)

    def _start_locked(self, *, requested_at_ms=None):
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
        self._session_expired = False
        self._heartbeat_mode = "command"
        self._heartbeat_stop.clear()
        self._start_heartbeat_thread_locked()
        _LOGGER.info(
            "program_output.acquired controller=%s token_present=%s requested_at_ms=%s heartbeat_interval_ms=%s",
            self.controller, self.token is not None, request_time,
            self.heartbeat_interval_ms,
        )

    def write(self, vector, *, elapsed_ms=20, valid_for_ms=None, buttons=0):
        if self.token is None:
            if self._session_expired:
                raise RuntimeError("Program session expired or was revoked")
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

    def heartbeat(self) -> bool:
        """Renew program ownership without changing the current stick state."""
        with self._io_lock:
            token = self.token
            if token is None:
                return False
            started = time.perf_counter()
            if self._heartbeat_mode == "state":
                return self._state_heartbeat_locked(token, started)
            try:
                response = self.client.request(
                    "program.heartbeat",
                    {"controller": self.controller, "token": token},
                )
            except Exception as exc:
                self._last_heartbeat_ms = (time.perf_counter() - started) * 1000.0
                if "unknown program command" in str(exc).lower():
                    self._heartbeat_mode = "state"
                    _LOGGER.info(
                        "program_output.heartbeat_fallback controller=%s mode=program.state",
                        self.controller,
                    )
                    return self._state_heartbeat_locked(token, started)
                self._heartbeat_failures += 1
                if _is_session_expired(exc):
                    self._session_expired = True
                    self.token = None
                _LOGGER.warning(
                    "program_output.heartbeat_failed controller=%s elapsed_ms=%.1f failures=%s error=%s",
                    self.controller, self._last_heartbeat_ms, self._heartbeat_failures, exc,
                )
                return False
            self._last_heartbeat_ms = (time.perf_counter() - started) * 1000.0
            self._heartbeat_count += 1
            if isinstance(response, dict) and response.get("accepted") is False:
                self._heartbeat_failures += 1
                return False
            if self._heartbeat_count <= 2 or self._heartbeat_count % 20 == 0:
                _LOGGER.info(
                    "program_output.heartbeat controller=%s count=%s elapsed_ms=%.1f",
                    self.controller, self._heartbeat_count, self._last_heartbeat_ms,
                )
            return True

    def _state_heartbeat_locked(self, token, started: float) -> bool:
        """Keep the lease alive using program.state on older Host builds."""
        command = self._last_command
        ttl = max(20, min(self.ttl_ms, int(command.get("ttl_ms", self.ttl_ms))))
        axes = tuple(int(value) for value in command.get("axes", (0, 0)))
        try:
            response = self.client.request(
                "program.state",
                {
                    "controller": self.controller,
                    "token": token,
                    "ttlMs": ttl,
                    "deadlineMs": host_clock_ms() + ttl,
                    "state": {
                        "buttons": 0,
                        "leftTrigger": 0,
                        "rightTrigger": 0,
                        "leftStickX": axes[0],
                        "leftStickY": axes[1],
                        "rightStickX": 0,
                        "rightStickY": 0,
                    },
                },
            )
        except Exception as exc:
            self._last_heartbeat_ms = (time.perf_counter() - started) * 1000.0
            self._heartbeat_failures += 1
            if _is_session_expired(exc):
                self._session_expired = True
                self.token = None
            _LOGGER.warning(
                "program_output.state_heartbeat_failed controller=%s elapsed_ms=%.1f failures=%s error=%s",
                self.controller, self._last_heartbeat_ms, self._heartbeat_failures, exc,
            )
            return False
        self._last_heartbeat_ms = (time.perf_counter() - started) * 1000.0
        if isinstance(response, dict) and response.get("accepted") is False:
            self._heartbeat_failures += 1
            return False
        self._heartbeat_count += 1
        if self._heartbeat_count <= 2 or self._heartbeat_count % 20 == 0:
            _LOGGER.info(
                "program_output.state_heartbeat controller=%s count=%s elapsed_ms=%.1f",
                self.controller, self._heartbeat_count, self._last_heartbeat_ms,
            )
        return True

    def _start_heartbeat_thread_locked(self):
        if self._heartbeat_thread is not None and self._heartbeat_thread.is_alive():
            return
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            name=f"program-heartbeat-{self.controller}",
            daemon=True,
        )
        self._heartbeat_thread.start()

    def _heartbeat_loop(self):
        wait_seconds = self.heartbeat_interval_ms / 1000.0
        while not self._heartbeat_stop.wait(wait_seconds):
            if self.heartbeat():
                continue
            with self._io_lock:
                if self._heartbeat_stop.is_set() or self.token is not None:
                    continue
                try:
                    # Recover an expired lease even when the main runtime is
                    # blocked and no further movement/neutral frame arrives.
                    self._start_locked()
                except Exception:
                    self._heartbeat_failures += 1
                    _LOGGER.exception(
                        "program_output.heartbeat_rearm_failed controller=%s",
                        self.controller,
                    )
            time.sleep(min(0.25, wait_seconds))

    def stop(self):
        with self._io_lock:
            self._heartbeat_stop.set()
            thread = self._heartbeat_thread
            self._heartbeat_thread = None
            token = self.token
            # Neutralize while the lease is still valid.  Releasing the token
            # alone leaves the last non-zero report visible until the Host
            # TTL expires, which is exactly the residual-controller symptom
            # seen when the application closes.
            last_axes = tuple(self._last_command.get("axes", (0, 0)))
            if token is not None and any(last_axes):
                try:
                    ttl = max(20, int(self.ttl_ms))
                    self.client.request(
                        "program.state",
                        {
                            "controller": self.controller,
                            "token": token,
                            "ttlMs": ttl,
                            "deadlineMs": host_clock_ms() + ttl,
                            "state": {
                                "buttons": 0,
                                "leftTrigger": 0,
                                "rightTrigger": 0,
                                "leftStickX": 0,
                                "leftStickY": 0,
                                "rightStickX": 0,
                                "rightStickY": 0,
                            },
                        },
                    )
                    _LOGGER.info("program_output.neutral controller=%s ttl_ms=%s previous_axes=%s", self.controller, ttl, last_axes)
                except Exception as exc:
                    # A revoked/expired lease cannot be neutralized through
                    # Host; still continue to release and close locally.
                    _LOGGER.warning("program_output.neutral_failed controller=%s error=%s", self.controller, exc)
            elif token is not None:
                _LOGGER.info("program_output.neutral_skipped controller=%s reason=already_zero", self.controller)
            self.token = None
            self._session_expired = False
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
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=max(0.2, self.heartbeat_interval_ms / 1000.0 * 2))
        if token is not None:
            try:
                self.client.request(
                    "program.release",
                    {"controller": self.controller, "token": token},
                )
                _LOGGER.info("program_output.released controller=%s", self.controller)
            except Exception:
                _LOGGER.exception("program_output.release_failed controller=%s", self.controller)

    def rearm(self, *, requested_at_ms=None):
        """Reacquire a lease whose Host token expired or was revoked.

        The old token is intentionally discarded without a release request:
        the Host has already invalidated it.  The next ``start`` performs the
        normal pause/fresh-acquire handshake.
        """
        with self._io_lock:
            self.token = None
            self._session_expired = False
            self.limiter.reset()
            self._start_locked(requested_at_ms=requested_at_ms)

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
            "heartbeat_interval_ms": self.heartbeat_interval_ms,
            "heartbeat_count": self._heartbeat_count,
            "heartbeat_failures": self._heartbeat_failures,
            "last_heartbeat_ms": self._last_heartbeat_ms,
            "session_expired": self._session_expired,
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
            "heartbeat_interval_ms": self.heartbeat_interval_ms,
            "heartbeat_count": self._heartbeat_count,
            "heartbeat_failures": self._heartbeat_failures,
            "last_heartbeat_ms": self._last_heartbeat_ms,
            "session_expired": self._session_expired,
        }

    def close(self):
        """Release the lease and close this output's dedicated Host client."""
        _LOGGER.info("program_output.close_begin controller=%s acquired=%s", self.controller, self.token is not None)
        try:
            self.stop()
        finally:
            close = getattr(self.client, "close", None)
            if callable(close):
                close()
            _LOGGER.info("program_output.close_finished controller=%s", self.controller)

    def cancel_pending_io(self):
        """Cancel an in-flight dedicated pipe request without waiting for _io_lock."""
        self._heartbeat_stop.set()
        close = getattr(self.client, "close", None)
        if callable(close):
            close()


def _is_session_expired(exc: BaseException) -> bool:
    message = str(exc).lower()
    return (
        "session expired" in message
        or ("session" in message and "revoked" in message)
        or "explicit start is required" in message
    )
