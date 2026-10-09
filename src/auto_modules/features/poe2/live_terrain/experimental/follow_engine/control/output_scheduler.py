"""Controller output lease and heartbeat scheduler."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Mapping
from typing import Protocol

from ..contracts import FusionSnapshot, OutputIntent
from ..timing import TimingWindow


_LOGGER = logging.getLogger(__name__)
_STALE_OUTPUT = object()


class OutputPort(Protocol):
    def start(self) -> None: ...

    def write(self, vector: tuple[float, float], *, elapsed_ms: int) -> object: ...

    def stop(self) -> None: ...

    def heartbeat(self) -> bool: ...


class OutputScheduler:
    """Keep controller leases alive independently of the control tick."""

    def __init__(
        self,
        outputs: Mapping[str, OutputPort],
        *,
        continuous_roles: set[str] | frozenset[str] = (),
        heartbeat_interval_ms: int = 100,
        on_write=None,
    ) -> None:
        if int(heartbeat_interval_ms) < 20:
            raise ValueError("heartbeat_interval_ms must be >= 20")
        self.outputs = dict(outputs)
        self.on_write = on_write
        self.continuous_roles = frozenset(str(role) for role in continuous_roles)
        self.heartbeat_interval_ms = int(heartbeat_interval_ms)
        self._armed: set[str] = set()
        self._stopping_roles: set[str] = set()
        self._lock = threading.RLock()
        self._io_locks: dict[str, threading.Lock] = {
            str(role): threading.Lock() for role in self.outputs
        }
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._heartbeat_count = 0
        self._heartbeat_failures = 0
        self._rearm_count = 0
        self._epoch = 0
        self._apply_timing = TimingWindow(256)
        self._heartbeat_timing = TimingWindow(256)
        self._last_io_duration_ms = 0.0

    def start(self) -> None:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._epoch += 1
            self._stop.clear()
            self._thread = threading.Thread(target=self._heartbeat_loop, name="follow-output-heartbeat", daemon=True)
            self._thread.start()

    def apply(self, snapshot: FusionSnapshot) -> None:
        for intent in snapshot.output_intents:
            with self._lock:
                port = self.outputs.get(intent.role_id)
                epoch = self._epoch
            if port is None:
                continue
            with self._role_io_lock(intent.role_id):
                with self._lock:
                    current_port = self.outputs.get(intent.role_id)
                    armed = intent.role_id in self._armed
                    if intent.role_id in self._stopping_roles or self._stop.is_set() or epoch != self._epoch:
                        continue
                if current_port is not port:
                    continue
                if not armed:
                    port.start()
                    reject_after_start = False
                    with self._lock:
                        if intent.role_id in self._stopping_roles or self._stop.is_set() or epoch != self._epoch:
                            reject_after_start = True
                        else:
                            self._armed.add(intent.role_id)
                    if reject_after_start:
                        # Do external I/O after releasing the scheduler lock;
                        # a concurrent stop may already be waiting for the
                        # role lock and must not deadlock here.
                        try:
                            port.stop()
                        finally:
                            continue
                with self._lock:
                    if intent.role_id in self._stopping_roles or self._stop.is_set() or epoch != self._epoch:
                        continue
                    if intent.role_id not in self._armed or self.outputs.get(intent.role_id) is not port:
                        continue
                result = self._write_locked(intent, port, epoch=epoch)
                self._apply_timing.add(self._last_io_duration_ms)
            if self.on_write is not None:
                if result is _STALE_OUTPUT:
                    continue
                self.on_write(intent, result)
        if not snapshot.session_active:
            self._stop_all(force=True)

    def register_outputs(self, outputs: Mapping[str, OutputPort]) -> None:
        """Atomically add lazily-created role outputs to the heartbeat map."""
        with self._lock:
            for role, output in outputs.items():
                normalized = str(role)
                self.outputs[normalized] = output
                self._io_locks.setdefault(normalized, threading.Lock())

    def prime_neutral(self, role_ids) -> None:
        """Arm selected outputs with one short neutral lease.

        The arm gate may need to establish Host ownership before allowing the
        first movement snapshot through.  This operation is idempotent for an
        already armed role and uses the same role lock/epoch checks as normal
        output, so a concurrent stop cannot leave a newly started lease alive.
        """
        for raw_role_id in role_ids:
            role_id = str(raw_role_id)
            with self._lock:
                port = self.outputs.get(role_id)
                epoch = self._epoch
                if port is None or role_id in self._armed or role_id in self._stopping_roles or self._stop.is_set():
                    continue
            with self._role_io_lock(role_id):
                with self._lock:
                    if (
                        self._stop.is_set()
                        or epoch != self._epoch
                        or role_id in self._stopping_roles
                        or role_id in self._armed
                        or self.outputs.get(role_id) is not port
                    ):
                        continue
                port.start()
                reject_after_start = False
                with self._lock:
                    if self._stop.is_set() or epoch != self._epoch or role_id in self._stopping_roles:
                        reject_after_start = True
                    else:
                        self._armed.add(role_id)
                if reject_after_start:
                    try:
                        port.stop()
                    finally:
                        continue
                try:
                    port.write((0.0, 0.0), elapsed_ms=20)
                except Exception:
                    # Do not leave an armed lease behind when the initial
                    # neutral handshake itself fails.
                    with self._lock:
                        self._armed.discard(role_id)
                    try:
                        port.stop()
                    except Exception:
                        _LOGGER.exception("follow output prime cleanup failed role=%s", role_id)
                    raise

    def _role_io_lock(self, role_id: str) -> threading.Lock:
        with self._lock:
            return self._io_locks.setdefault(str(role_id), threading.Lock())

    def stop(self, *, force: bool = True) -> None:
        with self._lock:
            self._epoch += 1
            self._stop.set()
        thread = self._thread
        if thread is not None:
            thread.join(timeout=max(0.2, self.heartbeat_interval_ms / 1000.0 * 2.0))
        self._thread = None
        # Snapshot armed roles under the scheduler lock, then perform each
        # potentially slow port operation under that role's I/O lock only.
        # Holding ``_lock`` across stop would block diagnostics, heartbeat
        # bookkeeping, and other roles while a Host/device call is pending.
        self._stop_all(force=force)

    def neutralize(self) -> None:
        """Send neutral state while retaining continuous leases."""
        # As with stop(), _stop_all snapshots scheduler state before entering
        # any external port I/O; continuous leases remain in _armed.
        self._stop_all(force=False)

    def diagnostics(self) -> dict[str, int | tuple[str, ...]]:
        with self._lock:
            return {
                "armed_roles": tuple(sorted(self._armed)),
                "heartbeat_count": self._heartbeat_count,
                "heartbeat_failures": self._heartbeat_failures,
                "rearm_count": self._rearm_count,
                "apply_timing": self._apply_timing.as_dict("apply_"),
                "heartbeat_timing": self._heartbeat_timing.as_dict("heartbeat_"),
            }

    def _arm_locked(self, role_id: str, port: OutputPort) -> None:
        if role_id in self._armed:
            return
        port.start()
        self._armed.add(role_id)

    def _write_locked(self, intent: OutputIntent, port: OutputPort, *, epoch: int) -> object:
        started = time.perf_counter()
        try:
            result = port.write(intent.vector, elapsed_ms=max(0, int(intent.duration_ms)))
            self._last_io_duration_ms = (time.perf_counter() - started) * 1000.0
            return result
        except Exception as exc:
            message = str(exc).lower()
            if "session" not in message and "explicit start" not in message and "revoked" not in message:
                raise
            rearm = getattr(port, "rearm", None)
            if not callable(rearm):
                raise
            with self._lock:
                if self._stop.is_set() or epoch != self._epoch or intent.role_id in self._stopping_roles:
                    return _STALE_OUTPUT
                self._rearm_count += 1
            rearm()
            with self._lock:
                if self._stop.is_set() or epoch != self._epoch or intent.role_id in self._stopping_roles:
                    return _STALE_OUTPUT
                self._armed.add(intent.role_id)
            result = port.write(intent.vector, elapsed_ms=max(0, int(intent.duration_ms)))
            self._last_io_duration_ms = (time.perf_counter() - started) * 1000.0
            return result

    def _heartbeat_loop(self) -> None:
        delay = self.heartbeat_interval_ms / 1000.0
        while not self._stop.wait(delay):
            with self._lock:
                armed = tuple((role_id, self.outputs.get(role_id)) for role_id in self._armed)
                epoch = self._epoch
            for role_id, port in armed:
                heartbeat = getattr(port, "heartbeat", None)
                if not callable(heartbeat):
                    continue
                try:
                    with self._role_io_lock(role_id):
                        with self._lock:
                            if self._stop.is_set() or role_id in self._stopping_roles or epoch != self._epoch:
                                continue
                            if role_id not in self._armed:
                                continue
                            if self.outputs.get(role_id) is not port:
                                continue
                        heartbeat_started = time.perf_counter()
                        healthy = heartbeat()
                        self._heartbeat_timing.add((time.perf_counter() - heartbeat_started) * 1000.0)
                        if healthy is False:
                            with self._lock:
                                if self._stop.is_set() or epoch != self._epoch or role_id in self._stopping_roles:
                                    continue
                            rearm = getattr(port, "rearm", None)
                            if callable(rearm):
                                rearm()
                                with self._lock:
                                    self._heartbeat_failures += 1
                                    self._rearm_count += 1
                                    if self._stop.is_set() or epoch != self._epoch or role_id in self._stopping_roles:
                                        continue
                                # Count a second successful heartbeat only after
                                # the lease has been rebuilt.
                                if heartbeat() is False:
                                    raise RuntimeError("heartbeat remained unhealthy after rearm")
                            else:
                                raise RuntimeError("heartbeat returned false and port cannot rearm")
                    with self._lock:
                        self._heartbeat_count += 1
                except Exception:
                    with self._lock:
                        self._heartbeat_failures += 1
                    _LOGGER.exception("follow output heartbeat failed role=%s", role_id)

    def _stop_all(self, *, force: bool) -> None:
        """Stop or neutralize all currently armed roles without holding _lock.

        The role set and port references are captured atomically.  Each port
        is then serialized with the role-specific I/O lock, while scheduler
        diagnostics and state updates can proceed concurrently.
        """
        first_error = None
        with self._lock:
            armed = tuple(role_id for role_id in self._armed if role_id not in self._stopping_roles)
            ports = {role_id: self.outputs.get(role_id) for role_id in armed}
            if force:
                # Claim every role before the first external I/O.  Otherwise
                # a slow role's stop call leaves later roles writable while a
                # force stop is already in progress.
                self._stopping_roles.update(armed)
        # Process roles in a stable reverse order.  A slow role can therefore
        # not hold the scheduler lock or prevent unrelated roles from making
        # progress while their own stop I/O is pending.
        for role_id in reversed(tuple(sorted(armed))):
            port = ports.get(role_id)
            if port is None:
                with self._lock:
                    self._armed.discard(role_id)
                    self._stopping_roles.discard(role_id)
                continue
            if not force and role_id in self.continuous_roles:
                with self._role_io_lock(role_id):
                    try:
                        port.write((0.0, 0.0), elapsed_ms=20)
                    except Exception:
                        with self._lock:
                            self._heartbeat_failures += 1
                continue
            try:
                with self._role_io_lock(role_id):
                    port.stop()
            except Exception as exc:
                first_error = first_error or exc
            finally:
                with self._lock:
                    self._armed.discard(role_id)
                    self._stopping_roles.discard(role_id)
        if first_error is not None:
            raise first_error
