"""Immutable status and adapter contracts for the event service."""

from dataclasses import dataclass
from typing import Iterable, Protocol

from core.events.automation.execution import EventStateFrame


class EventTriggerSource(Protocol):
    def poll(self, keys: Iterable[str]) -> tuple[str, ...]: ...


class EventHostBridge(Protocol):
    def connect(self, timeout: float = 2.0) -> None: ...
    def status(self) -> dict: ...
    def drain_events(self) -> tuple[dict, ...]: ...
    def drain_catalogs(self) -> tuple[dict, ...]: ...
    def publish_catalog(self, peer_id: str, catalog: dict) -> dict: ...
    def send_event(self, peer_id: str, payload: dict) -> dict: ...
    def write_state(self, frame: EventStateFrame, ttl_ms: int = 120) -> dict: ...
    def clear_source(self, controller: int, source: str) -> dict: ...
    def close(self) -> None: ...


@dataclass(frozen=True)
class EventWorkbenchStatus:
    local_running: bool = False
    remote_running: bool = False
    connected: bool = False
    peer_count: int = 0
    trigger_count: int = 0
    receive_count: int = 0
    last_event: str = ""
    error: str = ""
    peer_errors: tuple[str, ...] = ()
