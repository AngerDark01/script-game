"""Narrow adapter over the existing virtual-gamepad Host protocol."""

from __future__ import annotations

import time
from typing import Callable

from auto_modules.core.events.automation.execution import EventStateFrame
from auto_modules.core.communication import Capability, DeliveryMode, MessageEnvelope, PeerId, Topic


class HostEventBridge:
    def __init__(
        self,
        client_factory: Callable | None = None,
        *,
        manager=None,
        communication=None,
    ) -> None:
        self._client_factory = client_factory
        self._client = None
        self._manager = manager
        self._communication = communication or getattr(getattr(manager, "transport", None), "adapter", None)
        self._leases = {}

    @property
    def connected(self) -> bool:
        return self._communication.connected if self._communication is not None else self._client is not None

    def connect(self, timeout: float = 2.0) -> None:
        if self._communication is not None:
            self._communication.ensure_connected()
            return
        if self._client is not None:
            return
        if self._client_factory is None:
            from auto_modules.adapters.virtual_gamepad import VirtualGamepadClient

            factory = VirtualGamepadClient
        else:
            factory = self._client_factory
        client = factory()
        client.connect(timeout=timeout)
        self._client = client

    def status(self) -> dict:
        if self._communication is not None:
            return self._communication.status()
        return self._request("sync.status").get("status", {})

    def data_only_peers(self) -> tuple[dict, ...]:
        return tuple(
            peer
            for peer in self.status().get("peers", ())
            if peer.get("connected") and peer.get("syncing") and (
                peer.get("dataOnly")
                or any(str(value).startswith(("event.", "position.", "catalog.")) for value in peer.get("capabilities", ()))
            )
        )

    def drain_events(self) -> tuple[dict, ...]:
        if self._communication is not None:
            return self._communication.pop(Topic.EVENT)
        reply = self._request("sync.share.drain")
        return tuple(item for item in reply.get("events", ()) if isinstance(item, dict))

    def drain_catalogs(self) -> tuple[dict, ...]:
        if self._communication is not None:
            return self._communication.pop(Topic.CATALOG)
        reply = self._request("sync.share.catalog_drain")
        return tuple(item for item in reply.get("catalogs", ()) if isinstance(item, dict))

    def publish_catalog(self, peer_id: str, catalog: dict) -> dict:
        if self._manager is not None:
            self._lease(peer_id, Capability.CATALOG_PUBLISH).publish(
                MessageEnvelope(
                    message_id=f"catalog-{time.monotonic_ns()}",
                    topic=Topic.CATALOG,
                    payload={"catalog": catalog},
                    delivery=DeliveryMode.RELIABLE_ORDERED,
                    created_at_ms=int(time.monotonic() * 1000),
                )
            )
            return {"ok": True}
        return self._request(
            "sync.share.catalog",
            {"deviceId": str(peer_id), "catalog": catalog},
        )

    def send_event(self, peer_id: str, payload: dict) -> dict:
        if self._manager is not None:
            self._lease(peer_id, Capability.EVENT_PUBLISH).publish(
                MessageEnvelope(
                    message_id=str(payload.get("eventId") or f"event-{time.monotonic_ns()}"),
                    topic=Topic.EVENT,
                    payload={**payload, "deviceId": str(peer_id)},
                    delivery=DeliveryMode.RELIABLE_ORDERED,
                    created_at_ms=int(time.monotonic() * 1000),
                    deadline_ms=payload.get("deadlineMs"),
                )
            )
            return {"ok": True}
        return self._request(
            "sync.share.event",
            {**payload, "deviceId": str(peer_id)},
        )

    def write_state(self, frame: EventStateFrame, ttl_ms: int = 120) -> dict:
        if self._communication is not None:
            return self._communication.write_state(frame, ttl_ms)
        return self._request(
            "event.state",
            {
                "controller": frame.controller,
                "source": frame.source,
                "state": frame.state,
                "ttlMs": int(ttl_ms),
            },
        )

    def clear_source(self, controller: int, source: str) -> dict:
        if self._communication is not None:
            return self._communication.clear_source(controller, source)
        return self._request(
            "event.clear",
            {"controller": int(controller), "source": str(source)},
        )

    def close(self) -> None:
        for lease in tuple(self._leases.values()):
            lease.close()
        self._leases.clear()
        if self._communication is not None:
            return
        client, self._client = self._client, None
        if client is not None:
            client.close()

    def _request(self, command: str, payload: dict | None = None) -> dict:
        if self._client is None:
            raise RuntimeError("event Host bridge is not connected")
        return self._client.request(command, payload) if payload is not None else self._client.request(command)

    def _lease(self, peer_id: str, capability: Capability):
        key = (str(peer_id), capability)
        lease = self._leases.get(key)
        if lease is None or lease.closed:
            if self._manager is None:
                raise RuntimeError("communication manager is not configured")
            lease = self._manager.acquire(PeerId(str(peer_id)), capability)
            self._leases[key] = lease
        return lease
