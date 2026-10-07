"""Controller output lease and heartbeat scheduler."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Mapping
from typing import Protocol

from ..contracts import FusionSnapshot, OutputIntent


_LOGGER = logging.getLogger(__name__)


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
    ) -> None:
        if int(heartbeat_interval_ms) < 20:
            raise ValueError("heartbeat_interval_ms must be >= 20")
        self.outputs = dict(outputs)
        self.continuous_roles = frozenset(str(role) for role in continuous_roles)
        self.heartbeat_interval_ms = int(heartbeat_interval_ms)
        self._armed: set[str] = set()
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._heartbeat_count = 0
        self._heartbeat_failures = 0
        self._rearm_count = 0

    def start(self) -> None:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop.clear()
            self._thread = threading.Thread(target=self._heartbeat_loop, name="follow-output-heartbeat", daemon=True)
            self._thread.start()

    def apply(self, snapshot: FusionSnapshot) -> None:
        with self._lock:
            for intent in snapshot.output_intents:
                port = self.outputs.get(intent.role_id)
                if port is None:
                    continue
                self._arm_locked(intent.role_id, port)
                self._write_locked(intent, port)
            if not snapshot.session_active:
                self._stop_all_locked(force=True)

    def stop(self, *, force: bool = True) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None:
            thread.join(timeout=max(0.2, self.heartbeat_interval_ms / 1000.0 * 2.0))
        self._thread = None
        with self._lock:
            self._stop_all_locked(force=force)

    def diagnostics(self) -> dict[str, int | tuple[str, ...]]:
        with self._lock:
            return {
                "armed_roles": tuple(sorted(self._armed)),
                "heartbeat_count": self._heartbeat_count,
                "heartbeat_failures": self._heartbeat_failures,
                "rearm_count": self._rearm_count,
            }

    def _arm_locked(self, role_id: str, port: OutputPort) -> None:
        if role_id in self._armed:
            return
        port.start()
        self._armed.add(role_id)

    def _write_locked(self, intent: OutputIntent, port: OutputPort) -> None:
        try:
            port.write(intent.vector, elapsed_ms=max(0, int(intent.duration_ms)))
        except Exception as exc:
            message = str(exc).lower()
            if "session" not in message and "explicit start" not in message and "revoked" not in message:
                raise
            rearm = getattr(port, "rearm", None)
            if not callable(rearm):
                raise
            self._rearm_count += 1
            rearm()
            self._armed.add(intent.role_id)
            port.write(intent.vector, elapsed_ms=max(0, int(intent.duration_ms)))

    def _heartbeat_loop(self) -> None:
        delay = self.heartbeat_interval_ms / 1000.0
        while not self._stop.wait(delay):
            with self._lock:
                for role_id in tuple(self._armed):
                    port = self.outputs.get(role_id)
                    heartbeat = getattr(port, "heartbeat", None)
                    if not callable(heartbeat):
                        continue
                    try:
                        heartbeat()
                        self._heartbeat_count += 1
                    except Exception:
                        self._heartbeat_failures += 1
                        _LOGGER.exception("follow output heartbeat failed role=%s", role_id)

    def _stop_all_locked(self, *, force: bool) -> None:
        for role_id in tuple(self._armed):
            port = self.outputs.get(role_id)
            if port is None:
                self._armed.discard(role_id)
                continue
            if not force and role_id in self.continuous_roles:
                try:
                    port.write((0.0, 0.0), elapsed_ms=20)
                except Exception:
                    self._heartbeat_failures += 1
                continue
            try:
                port.stop()
            finally:
                self._armed.discard(role_id)
