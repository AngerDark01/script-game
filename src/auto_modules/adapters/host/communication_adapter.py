"""Shared Host connection and protocol adapter for the communication runtime.

The adapter owns one Named Pipe client for the process.  Peer capabilities are
represented by ``CommunicationManager`` leases; this module only translates
generic envelopes to the existing Host command names and performs the single
shared drain operation during ``pump``.
"""

from __future__ import annotations

from typing import Any, Callable
from threading import Lock

from auto_modules.core.communication import (
    DeliveryMode,
    MessageEnvelope,
    PeerId,
    Topic,
)
from auto_modules.application.communication.manager import StaleSessionError


class HostPeerConnection:
    def __init__(self, adapter: "HostCommunicationAdapter", peer_id: PeerId) -> None:
        self.adapter = adapter
        self.peer_id = peer_id
        self.closed = False

    def send(self, message: MessageEnvelope) -> None:
        if self.closed:
            raise RuntimeError("Host peer connection is closed")
        self.adapter.send_message(self.peer_id, message)

    def close(self) -> None:
        self.closed = True


class HostPeerTransport:
    """Transport port used by ``CommunicationManager`` for Host peers."""

    def __init__(self, adapter: "HostCommunicationAdapter") -> None:
        self.adapter = adapter

    def connect(self, peer_id: PeerId) -> HostPeerConnection:
        self.adapter.ensure_connected()
        return HostPeerConnection(self.adapter, peer_id)

    def pump(self, manager) -> int:
        return self.adapter.pump(manager)


class HostCommunicationAdapter:
    """Own the local Host client and expose generic peer transport semantics."""

    def __init__(
        self,
        client_factory: Callable[[], Any] | None = None,
        *,
        connect_timeout: float = 2.0,
    ) -> None:
        self._client_factory = client_factory
        self._connect_timeout = float(connect_timeout)
        self._client: Any | None = None
        self._connect_lock = Lock()

    @property
    def connected(self) -> bool:
        return self._client is not None

    @property
    def transport(self) -> HostPeerTransport:
        return HostPeerTransport(self)

    def ensure_connected(self) -> None:
        if self._client is not None:
            return
        with self._connect_lock:
            if self._client is not None:
                return
            if self._client_factory is None:
                from auto_modules.adapters.virtual_gamepad import VirtualGamepadClient

                factory = VirtualGamepadClient
            else:
                factory = self._client_factory
            client = factory()
            try:
                client.connect(timeout=self._connect_timeout)
            except Exception:
                client.close()
                raise
            self._client = client

    def request(self, command: str, payload: dict | None = None) -> dict:
        self.ensure_connected()
        if self._client is None:  # pragma: no cover - defensive for custom clients
            raise RuntimeError("Host communication is not connected")
        return self._client.request(command, payload) if payload is not None else self._client.request(command)

    def status(self) -> dict:
        return self.request("sync.status").get("status", {})

    def send_message(self, peer_id: PeerId, message: MessageEnvelope) -> None:
        payload = dict(message.payload)
        payload.setdefault("deviceId", str(peer_id))
        if message.topic is Topic.POSITION:
            command = "sync.share.position"
        elif message.topic is Topic.EVENT:
            command = "sync.share.event"
        elif message.topic is Topic.CATALOG:
            command = "sync.share.catalog"
            payload.setdefault("catalog", payload.pop("value", {}))
        else:
            topic_name = getattr(message.topic, "value", str(message.topic))
            raise PermissionError(f"Host adapter does not publish topic {topic_name}")
        if message.deadline_ms is not None:
            payload.setdefault("deadlineMs", message.deadline_ms)
        self.request(command, payload)

    def pump(self, manager) -> int:
        """Read the legacy drain endpoint once and fan messages out through manager."""

        reply = self.request("sync.share.drain")
        count = 0
        status = reply.get("status", {}) if isinstance(reply, dict) else {}
        for item in status.get("sharedPositions", ()):
            if not isinstance(item, dict) or not isinstance(item.get("position"), dict):
                continue
            peer = PeerId(str(item.get("deviceId") or "unknown"))
            position = dict(item["position"])
            envelope = MessageEnvelope(
                message_id=f"position-{peer}-{position.get('actorId', 'unknown')}",
                topic=Topic.POSITION,
                payload={"deviceId": str(peer), **item},
                delivery=DeliveryMode.LATEST,
                created_at_ms=0,
                ttl_ms=500,
            )
            try:
                manager.dispatch_incoming(peer, envelope)
            except StaleSessionError:
                continue
            count += 1
        for item in reply.get("events", ()):
            if not isinstance(item, dict):
                continue
            peer = PeerId(str(item.get("deviceId") or "unknown"))
            envelope = MessageEnvelope(
                message_id=str(item.get("id") or "event"),
                topic=Topic.EVENT,
                payload=dict(item),
                delivery=DeliveryMode.RELIABLE_ORDERED,
                created_at_ms=0,
                deadline_ms=max(1, int(item.get("deadlineMs") or 1)),
                sequence=int(item.get("sequence") or 0),
            )
            try:
                manager.dispatch_incoming(peer, envelope)
            except StaleSessionError:
                continue
            count += 1
        for item in reply.get("catalogs", ()):
            if not isinstance(item, dict):
                continue
            peer = PeerId(str(item.get("deviceId") or "unknown"))
            envelope = MessageEnvelope(
                message_id=str(item.get("messageId") or "catalog"),
                topic=Topic.CATALOG,
                payload=dict(item),
                delivery=DeliveryMode.RELIABLE_ORDERED,
                created_at_ms=0,
            )
            try:
                manager.dispatch_incoming(peer, envelope)
            except StaleSessionError:
                continue
            count += 1
        return count

    def write_state(self, frame, ttl_ms: int = 120) -> dict:
        return self.request(
            "event.state",
            {
                "controller": frame.controller,
                "source": frame.source,
                "state": frame.state,
                "ttlMs": int(ttl_ms),
            },
        )

    def clear_source(self, controller: int, source: str) -> dict:
        return self.request("event.clear", {"controller": int(controller), "source": str(source)})

    def close(self) -> None:
        client, self._client = self._client, None
        if client is not None:
            client.close()
