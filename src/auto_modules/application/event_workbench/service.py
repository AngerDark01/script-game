"""Application service for event configuration and execution."""

from __future__ import annotations

import threading
import time
from collections import deque
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable

from auto_modules.adapters.virtual_gamepad import host_clock_ms
from auto_modules.core.events.automation.definitions import EventDefinitionRepository
from auto_modules.core.events.automation.execution import EventExecutionRuntime
from auto_modules.core.events.automation.routes import EventRouteRepository, EventRouter
from auto_modules.adapters.host.event_bridge import HostEventBridge
from auto_modules.adapters.windows.hotkeys import HotkeyTriggerSource

from .models import EventHostBridge, EventTriggerSource, EventWorkbenchStatus


LOCAL_SOURCE = "event:local"
REMOTE_SOURCE = "event:remote"


def _controllers(values: Iterable[int]) -> tuple[int, ...]:
    result = tuple(dict.fromkeys(int(value) for value in values))
    if not result or any(value not in (1, 2) for value in result):
        raise ValueError("controller must be either 1 or 2")
    return result


def _target_controllers(values) -> tuple[int, ...]:
    result: list[int] = []
    for value in values or ():
        text = str(value).lower()
        if "1" in text and 1 not in result:
            result.append(1)
        if "2" in text and 2 not in result:
            result.append(2)
    return tuple(result or (1,))


def _data_peers(status: dict) -> tuple[dict, ...]:
    return tuple(
        peer
        for peer in status.get("peers", ())
        if peer.get("connected") and peer.get("syncing") and peer.get("dataOnly")
    )


class EventWorkbenchService:
    """Own the action-event lifecycle without exposing platform details to UI."""

    def __init__(
        self,
        root: Path,
        *,
        bridge_factory: Callable[[], EventHostBridge] | None = None,
        client_factory: Callable | None = None,
        trigger_source: EventTriggerSource | None = None,
        clock_ms: Callable[[], int] | None = None,
        monotonic: Callable[[], float] | None = None,
        host_clock_ms_func: Callable[[], int] | None = None,
        communication_manager=None,
        communication_adapter=None,
        loop_interval: float = 0.02,
        catalog_interval: float = 2.0,
    ) -> None:
        self.root = Path(root)
        self._communication_manager = communication_manager
        self._communication_adapter = communication_adapter
        if bridge_factory is not None:
            self._bridge_factory = bridge_factory
        elif communication_manager is not None:
            self._bridge_factory = lambda: HostEventBridge(
                manager=communication_manager,
                communication=communication_adapter,
            )
        else:
            self._bridge_factory = lambda: HostEventBridge(client_factory=client_factory)
        self._trigger_source = trigger_source or HotkeyTriggerSource()
        self._clock_ms = clock_ms or (lambda: int(time.monotonic() * 1000))
        self._monotonic = monotonic or time.monotonic
        self._host_clock_ms = host_clock_ms_func or host_clock_ms
        self._loop_interval = max(0.005, float(loop_interval))
        self._catalog_interval = max(0.25, float(catalog_interval))

        self._definitions = EventDefinitionRepository(self.root, "local")
        self._routes = EventRouteRepository(self.root)
        self._router = EventRouter(self._routes.load())
        self._execution = EventExecutionRuntime(
            self._definitions.definitions(),
            clock_ms=self._clock_ms,
        )
        self._bridge: EventHostBridge | None = None
        self._active_device_id = "local"
        self._next_catalog_send = 0.0
        self._local_running = False
        self._remote_running = False
        self._connected = False
        self._peer_count = 0
        self._trigger_count = 0
        self._receive_count = 0
        self._last_event = ""
        self._error = ""
        self._peer_errors: tuple[str, ...] = ()
        self._recent_logs: deque[str] = deque(maxlen=200)
        self._pending_clears: set[str] = set()
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def execution(self) -> EventExecutionRuntime:
        return self._execution

    def start(self) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run,
                name="EventWorkbenchService",
                daemon=True,
            )
            self._thread.start()
            self._log("event service started")

    def set_local_running(self, enabled: bool) -> None:
        with self._lock:
            enabled = bool(enabled)
            if self._local_running and not enabled:
                self._execution.cancel_source(LOCAL_SOURCE)
                self._pending_clears.add(LOCAL_SOURCE)
            self._local_running = enabled
            self._log(f"local event monitoring {'enabled' if enabled else 'disabled'}")

    def set_remote_running(self, enabled: bool) -> None:
        with self._lock:
            enabled = bool(enabled)
            if self._remote_running and not enabled:
                self._execution.cancel_source(REMOTE_SOURCE)
                self._pending_clears.add(REMOTE_SOURCE)
            self._remote_running = enabled
            self._log(f"remote event monitoring {'enabled' if enabled else 'disabled'}")

    def load_local_events(self) -> list[dict]:
        with self._lock:
            return deepcopy(self._definitions.local_records())

    def load_remote_events(self) -> list[dict]:
        with self._lock:
            return deepcopy(self._definitions.remote_records())

    def load_routes(self) -> list[dict]:
        with self._lock:
            return [route.to_record() for route in self._routes.load()]

    def new_event_draft(self, source: dict | None = None) -> dict:
        with self._lock:
            return self._definitions.new_draft(source)

    def save(self, events: Iterable[dict], routes: Iterable[dict]) -> list[dict]:
        with self._lock:
            saved = self._definitions.save_local(events)
            self._routes.save(routes)
            self._reload_configuration()
            self._log(f"saved {len(saved)} local event definitions")
            return deepcopy(saved)

    def send_remote_event(
        self,
        device_id: str,
        event_name: str,
        controllers: Iterable[int],
    ) -> dict:
        target = str(device_id or "").strip()
        name = str(event_name or "").strip()
        if not target:
            raise ValueError("remote device id is required")
        if not name:
            raise ValueError("event name is required")
        controller_numbers = _controllers(controllers)
        bridge = self._bridge_factory()
        bridge.connect(timeout=2.0)
        try:
            status = bridge.status()
            peers = {str(peer.get("deviceId")): peer for peer in _data_peers(status)}
            if target not in peers:
                raise RuntimeError("target has no connected shared-event session")
            record = next(
                (
                    item for item in self._definitions.remote_records()
                    if str(item.get("owner_device_id")) == target
                    and str(item.get("name")) == name
                ),
                None,
            ) or self._definitions.local_by_name(name) or self._definitions.by_name(name)
            payload = {
                "name": name,
                "eventId": str((record or {}).get("id") or ""),
                "eventRevision": int((record or {}).get("revision") or 0),
                "targets": [str(value) for value in controller_numbers],
                "deadlineMs": self._host_clock_ms() + 250,
            }
            reply = bridge.send_event(target, payload)
            with self._lock:
                self._log(f"sent remote event {name} to {target}")
            return reply
        finally:
            bridge.close()

    def status(self) -> EventWorkbenchStatus:
        with self._lock:
            return EventWorkbenchStatus(
                local_running=self._local_running,
                remote_running=self._remote_running,
                connected=self._connected,
                peer_count=self._peer_count,
                trigger_count=self._trigger_count,
                receive_count=self._receive_count,
                last_event=self._last_event,
                error=self._error,
                peer_errors=self._peer_errors,
            )

    def recent_log_lines(self, limit: int = 80) -> list[str]:
        with self._lock:
            count = max(0, int(limit))
            return list(self._recent_logs)[-count:] if count else []

    def tick_once(self) -> None:
        with self._lock:
            if self._communication_manager is not None:
                self._communication_manager.pump()
            bridge = self._ensure_bridge()
            host_status = bridge.status()
            peers = _data_peers(host_status)
            self._connected = True
            self._peer_count = len(peers)
            device_id = str(host_status.get("deviceId") or "local")
            if device_id != self._active_device_id:
                self._active_device_id = device_id
                self._definitions.set_device_id(device_id)
                self._reload_definitions()

            self._sync_catalogs(bridge, peers)
            if self._local_running:
                self._dispatch_local_triggers(bridge, peers)
            if self._remote_running:
                self._receive_remote_events(bridge)
            self._flush_pending_clears(bridge)
            for frame in self._execution.tick():
                bridge.write_state(frame, ttl_ms=120)
            self._error = ""

    def shutdown(self) -> None:
        self._stop_event.set()
        thread = self._thread
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=2.0)
        with self._lock:
            self._thread = None
            self._local_running = False
            self._remote_running = False
            self._execution.cancel_source(LOCAL_SOURCE)
            self._execution.cancel_source(REMOTE_SOURCE)
            self._cleanup_bridge()
            self._log("event service stopped")

    def _run(self) -> None:
        try:
            while not self._stop_event.is_set():
                try:
                    self.tick_once()
                except Exception as exc:
                    with self._lock:
                        self._error = str(exc)
                        self._log(f"event service error: {exc}")
                        self._connected = False
                        self._cleanup_bridge()
                    if self._stop_event.wait(0.5):
                        break
                    continue
                self._stop_event.wait(self._loop_interval)
        finally:
            with self._lock:
                self._cleanup_bridge()

    def _ensure_bridge(self) -> EventHostBridge:
        if self._bridge is None:
            bridge = self._bridge_factory()
            bridge.connect(timeout=2.0)
            self._bridge = bridge
        return self._bridge

    def _reload_configuration(self) -> None:
        self._router = EventRouter(self._routes.load())
        self._reload_definitions()

    def _reload_definitions(self) -> None:
        self._execution.replace_definitions(self._definitions.definitions())

    def _sync_catalogs(self, bridge: EventHostBridge, peers: tuple[dict, ...]) -> None:
        errors: list[str] = []
        now = self._monotonic()
        if now >= self._next_catalog_send:
            catalog = self._definitions.catalog_payload()
            for peer in peers:
                peer_id = str(peer.get("deviceId") or "")
                try:
                    bridge.publish_catalog(peer_id, catalog)
                except Exception as exc:
                    errors.append(f"{peer_id}: {exc}")
            self._next_catalog_send = now + self._catalog_interval

        changed = 0
        for catalog in bridge.drain_catalogs():
            records = catalog.get("definitions", ())
            if isinstance(records, list) and records:
                changed += self._definitions.apply_remote(records)
        if changed:
            self._reload_definitions()
        self._peer_errors = tuple(errors)

    def _dispatch_local_triggers(
        self,
        bridge: EventHostBridge,
        peers: tuple[dict, ...],
    ) -> None:
        for trigger in self._trigger_source.poll(self._router.triggers()):
            for dispatch in self._router.dispatches(trigger):
                started = False
                if dispatch.remote:
                    started = self._broadcast(bridge, peers, dispatch)
                else:
                    key = self._definitions.local_key(dispatch.event_name)
                    started = bool(key) and self._execution.start(
                        LOCAL_SOURCE,
                        key,
                        dispatch.controllers,
                    )
                if started:
                    self._trigger_count += 1
                    self._last_event = dispatch.event_name
                    self._log(f"triggered local route {trigger}: {dispatch.event_name}")

    def _broadcast(self, bridge: EventHostBridge, peers: tuple[dict, ...], dispatch) -> bool:
        record = self._definitions.local_by_name(dispatch.event_name)
        if record is None:
            return False
        catalog = self._definitions.catalog_payload()
        payload = {
            "name": dispatch.event_name,
            "eventId": str(record.get("id") or ""),
            "eventRevision": int(record.get("revision") or 0),
            "targets": [str(value) for value in dispatch.controllers],
            "deadlineMs": self._host_clock_ms() + 500,
        }
        sent = False
        errors = list(self._peer_errors)
        for peer in peers:
            peer_id = str(peer.get("deviceId") or "")
            try:
                bridge.publish_catalog(peer_id, catalog)
                bridge.send_event(peer_id, payload)
                sent = True
            except Exception as exc:
                errors.append(f"{peer_id}: {exc}")
        self._peer_errors = tuple(errors)
        return sent

    def _receive_remote_events(self, bridge: EventHostBridge) -> None:
        for item in bridge.drain_events():
            if "remainingMs" in item and int(item.get("remainingMs") or 0) <= 0:
                continue
            key = self._definitions.resolve_shared_key(item)
            if key is None:
                continue
            instance_id = str(item.get("id") or item.get("eventId") or "") or None
            if self._execution.start(
                REMOTE_SOURCE,
                key,
                _target_controllers(item.get("targets")),
                instance_id=instance_id,
            ):
                self._receive_count += 1
                self._last_event = str(item.get("name") or "")
                self._log(f"received remote event {self._last_event}")

    def _flush_pending_clears(self, bridge: EventHostBridge) -> None:
        for source in sorted(self._pending_clears):
            for controller in (1, 2):
                bridge.clear_source(controller, source)
        self._pending_clears.clear()

    def _cleanup_bridge(self) -> None:
        bridge, self._bridge = self._bridge, None
        if bridge is None:
            return
        for source in (LOCAL_SOURCE, REMOTE_SOURCE):
            for controller in (1, 2):
                try:
                    bridge.clear_source(controller, source)
                except Exception:
                    pass
        try:
            bridge.close()
        finally:
            self._connected = False

    def _log(self, message: str) -> None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._recent_logs.append(f"{timestamp} {message}")
