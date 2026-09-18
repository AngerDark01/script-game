"""Narrow adapter over the existing virtual-gamepad Host protocol."""

from __future__ import annotations

from typing import Callable

from core.events.automation.execution import EventStateFrame


class HostEventBridge:
    def __init__(self, client_factory: Callable | None = None) -> None:
        self._client_factory = client_factory
        self._client = None

    @property
    def connected(self) -> bool:
        return self._client is not None

    def connect(self, timeout: float = 2.0) -> None:
        if self._client is not None:
            return
        if self._client_factory is None:
            from virtual_gamepad.client.python import VirtualGamepadClient

            factory = VirtualGamepadClient
        else:
            factory = self._client_factory
        client = factory()
        client.connect(timeout=timeout)
        self._client = client

    def status(self) -> dict:
        return self._request("sync.status").get("status", {})

    def data_only_peers(self) -> tuple[dict, ...]:
        return tuple(
            peer
            for peer in self.status().get("peers", ())
            if peer.get("connected") and peer.get("syncing") and peer.get("dataOnly")
        )

    def drain_events(self) -> tuple[dict, ...]:
        reply = self._request("sync.share.drain")
        return tuple(item for item in reply.get("events", ()) if isinstance(item, dict))

    def drain_catalogs(self) -> tuple[dict, ...]:
        reply = self._request("sync.share.catalog_drain")
        return tuple(item for item in reply.get("catalogs", ()) if isinstance(item, dict))

    def publish_catalog(self, peer_id: str, catalog: dict) -> dict:
        return self._request(
            "sync.share.catalog",
            {"deviceId": str(peer_id), "catalog": catalog},
        )

    def send_event(self, peer_id: str, payload: dict) -> dict:
        return self._request(
            "sync.share.event",
            {**payload, "deviceId": str(peer_id)},
        )

    def write_state(self, frame: EventStateFrame, ttl_ms: int = 120) -> dict:
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
        return self._request(
            "event.clear",
            {"controller": int(controller), "source": str(source)},
        )

    def close(self) -> None:
        client, self._client = self._client, None
        if client is not None:
            client.close()

    def _request(self, command: str, payload: dict | None = None) -> dict:
        if self._client is None:
            raise RuntimeError("event Host bridge is not connected")
        return self._client.request(command, payload) if payload is not None else self._client.request(command)
