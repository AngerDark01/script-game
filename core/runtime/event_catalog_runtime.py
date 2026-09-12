"""Background synchronization of read-only event catalogs.

Catalog exchange is deliberately independent from local/remote event execution.
It may run as soon as the LAN data session is available and never emits
``event.state`` or consumes the shared-event queue.
"""
from __future__ import annotations

import os
import threading
import time
from pathlib import Path

from core.events.event_catalog import catalog_summary
from core.events.event_store import EventStore


def _event_log(message: str) -> None:
    try:
        path = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "AutoModules" / "Workbench" / "logs" / "event-runtime.log"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as stream:
            stream.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}\n")
    except Exception:
        pass


def _data_only_peers(status: dict) -> list[dict]:
    return [
        peer for peer in status.get("peers", [])
        if peer.get("connected") and peer.get("syncing") and peer.get("dataOnly")
    ]


class EventCatalogRuntime:
    """Keep the local read-only event cache current while a share session runs."""

    def __init__(self, *, root: Path, client_factory=None, interval: float = 2.0):
        self.root = Path(root)
        self.client_factory = client_factory
        self.interval = max(0.25, float(interval))
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.error = ""
        self.last_sent = 0.0
        self.last_applied = 0.0
        self.last_peer_count = 0
        self.applied_count = 0

    @staticmethod
    def _catalog_payload(store: EventStore, device_id: str) -> dict:
        definitions = store.local()
        summary = catalog_summary(definitions, device_id)
        return {**summary, "definitions": definitions}

    def start(self) -> None:
        if self.thread and self.thread.is_alive():
            return
        self.stop_event.clear()
        self.error = ""
        self.thread = threading.Thread(target=self._run, name="EventCatalogRuntime", daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=2.0)

    def _run(self) -> None:
        client = None
        store: EventStore | None = None
        device_id = "local"
        next_send = 0.0
        _event_log("event catalog runtime starting")
        try:
            from virtual_gamepad.client.python import VirtualGamepadClient

            while not self.stop_event.is_set():
                if client is None:
                    try:
                        client = (self.client_factory or VirtualGamepadClient)()
                        client.connect(timeout=1.0)
                        _event_log("event catalog host pipe connected")
                        next_send = 0.0
                    except Exception as exc:
                        self.error = str(exc)
                        if client is not None:
                            try:
                                client.close()
                            except Exception:
                                pass
                        client = None
                        self.stop_event.wait(1.0)
                        continue

                try:
                    status = client.request("sync.status").get("status", {})
                    device_id = str(status.get("deviceId") or device_id)
                    if store is None or store.device_id != device_id:
                        store = EventStore(self.root, device_id)
                    peers = _data_only_peers(status)
                    self.last_peer_count = len(peers)

                    now = time.monotonic()
                    if now >= next_send:
                        catalog = self._catalog_payload(store, device_id)
                        for peer in peers:
                            peer_id = peer.get("deviceId")
                            try:
                                client.request(
                                    "sync.share.catalog",
                                    {"deviceId": peer_id, "catalog": catalog},
                                )
                                _event_log(
                                    f"event catalog sent device={peer_id} "
                                    f"count={len(catalog['definitions'])}"
                                )
                                self.last_sent = time.time()
                            except Exception as exc:
                                _event_log(
                                    f"event catalog send error device={peer_id} error={exc!r}"
                                )
                        next_send = now + self.interval

                    # This command drains catalogs only.  In particular, it
                    # cannot steal a pending shared event from RemoteEventRuntime.
                    try:
                        reply = client.request("sync.share.catalog_drain")
                    except Exception as exc:
                        _event_log(f"event catalog drain error={exc!r}")
                        reply = {}
                    for catalog_item in reply.get("catalogs", []):
                        if not isinstance(catalog_item, dict):
                            continue
                        definitions = catalog_item.get("definitions", [])
                        if not isinstance(definitions, list) or not definitions:
                            continue
                        changed = store.apply_remote(definitions)
                        if changed:
                            self.applied_count += changed
                            self.last_applied = time.time()
                            _event_log(
                                f"event catalog applied owner={catalog_item.get('deviceId')} "
                                f"changed={changed}"
                            )
                    self.error = ""
                    self.stop_event.wait(0.25)
                except Exception as exc:
                    self.error = str(exc)
                    _event_log(f"event catalog runtime error={exc!r}")
                    try:
                        client.close()
                    except Exception:
                        pass
                    client = None
                    self.stop_event.wait(0.5)
        finally:
            if client is not None:
                try:
                    client.close()
                except Exception:
                    pass
            _event_log("event catalog runtime stopped")
