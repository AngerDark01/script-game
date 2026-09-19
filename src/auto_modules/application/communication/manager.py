"""Process-scoped communication manager with shared peer sessions."""

from __future__ import annotations

from collections.abc import Callable
from threading import Lock, RLock
from typing import Any
from uuid import uuid4

from auto_modules.core.communication.contracts import (
    Capability,
    PeerId,
    Topic,
    capability_topic,
)
from auto_modules.core.communication.messages import MessageEnvelope

from .dispatcher import MessageDispatcher
from .leases import CapabilityLease
from .reconnect import ReconnectController
from .sessions import PeerSession
from .trust_store import FileTrustStore


class CapabilityConflict(RuntimeError):
    """A capability has an exclusive owner on this peer session."""


class StaleSessionError(RuntimeError):
    """An operation referenced a closed or superseded session generation."""


class CommunicationManager:
    """Own one physical connection per peer and multiplex logical leases."""

    def __init__(self, transport: Any, *, trust_store: FileTrustStore | None = None) -> None:
        self.transport = transport
        self.trust_store = trust_store
        self.dispatcher = MessageDispatcher()
        self.reconnect = ReconnectController()
        self._sessions: dict[PeerId, PeerSession] = {}
        self._leases: dict[str, CapabilityLease] = {}
        self._lock = RLock()
        self._pump_lock = Lock()

    def acquire(self, peer_id: PeerId | str, capability: Capability) -> CapabilityLease:
        peer_id = PeerId(str(peer_id))
        capability = Capability(capability)
        with self._lock:
            session = self._sessions.get(peer_id)
            if session is None or not session.active:
                connection = self.transport.connect(peer_id)
                session = PeerSession(peer_id, connection, self.reconnect.new_session(peer_id))
                self._sessions[peer_id] = session
            if capability is Capability.INPUT_RECEIVE and Capability.INPUT_RECEIVE in session.capabilities:
                raise CapabilityConflict(f"input.receive already has an owner for {peer_id}")
            token = uuid4().hex
            lease = CapabilityLease(self, peer_id, token, capability, session.generation)
            session.add_lease(token, capability)
            self._leases[token] = lease
            return lease

    def publish(self, lease: CapabilityLease, message: MessageEnvelope) -> None:
        with self._lock:
            session = self._require_lease_session(lease)
            expected_topic = capability_topic(lease.capability)
            if message.topic != expected_topic or ".publish" not in lease.capability.value:
                topic_name = getattr(message.topic, "value", str(message.topic))
                raise PermissionError(f"{lease.capability.value} cannot publish {topic_name}")
            session.connection.send(message)

    def subscribe(
        self,
        owner: CapabilityLease | PeerId | str,
        topic: Topic | str,
        callback: Callable[[MessageEnvelope], Any],
    ):
        with self._lock:
            if isinstance(owner, CapabilityLease):
                self._require_lease_session(owner)
                if ".subscribe" not in owner.capability.value:
                    raise PermissionError(f"{owner.capability.value} cannot subscribe")
                peer_id = owner.peer_id
                if Topic(topic) != capability_topic(owner.capability):
                    raise PermissionError(f"{owner.capability.value} cannot subscribe to {topic}")
            else:
                peer_id = PeerId(str(owner))
                if peer_id not in self._sessions:
                    raise StaleSessionError(f"no active session for {peer_id}")
            return self.dispatcher.subscribe(peer_id, topic, callback)

    def dispatch_incoming(
        self,
        peer_id: PeerId | str,
        message: MessageEnvelope,
        *,
        generation: int | None = None,
    ) -> None:
        peer_id = PeerId(str(peer_id))
        with self._lock:
            session = self._sessions.get(peer_id)
            if session is None or not session.active:
                raise StaleSessionError(f"no active session for {peer_id}")
            if generation is not None and generation != session.generation:
                raise StaleSessionError(f"stale session generation for {peer_id}")
            self.dispatcher.dispatch(peer_id, message)

    def session_generation(self, peer_id: PeerId | str) -> int:
        peer_id = PeerId(str(peer_id))
        with self._lock:
            session = self._sessions.get(peer_id)
            return session.generation if session is not None else self.reconnect.generation(peer_id)

    def disconnect(
        self,
        peer_id: PeerId | str,
        *,
        manual: bool = False,
        emergency: bool = False,
        forget: bool = False,
    ) -> None:
        peer_id = PeerId(str(peer_id))
        with self._lock:
            session = self._sessions.pop(peer_id, None)
            if session is not None:
                session.active = False
                for token in tuple(session.leases):
                    lease = self._leases.pop(token, None)
                    if lease is not None:
                        lease._invalidate()
                self.dispatcher.close_peer(peer_id)
                session.connection.close()
            block_recovery = manual or emergency or forget
            self.reconnect.fence(peer_id, block_recovery=block_recovery)
            if self.trust_store is not None and block_recovery:
                if forget:
                    self.trust_store.forget(peer_id)
                else:
                    self.trust_store.clear_recovery(peer_id)

    def release(self, lease: CapabilityLease) -> None:
        with self._lock:
            self._leases.pop(lease.token, None)
            session = self._sessions.get(lease.peer_id)
            if session is None:
                return
            session.remove_lease(lease.token)
            if not session.leases:
                self.disconnect(lease.peer_id)

    def mark_disconnected(self, peer_id: PeerId | str) -> None:
        """Fence a lost connection while preserving trust and recovery preferences."""

        self.disconnect(peer_id, manual=False)

    def close(self) -> None:
        with self._lock:
            for peer_id in tuple(self._sessions):
                self.disconnect(peer_id)

    def pump(self) -> int:
        """Let a transport perform its single inbound read and fan-out pass."""

        pump = getattr(self.transport, "pump", None)
        if pump is None:
            return 0
        with self._pump_lock:
            return int(pump(self) or 0)

    def active_peers(self) -> tuple[PeerId, ...]:
        with self._lock:
            return tuple(peer_id for peer_id, session in self._sessions.items() if session.active)

    def recover(self) -> dict[PeerId, tuple[CapabilityLease, ...]]:
        """Reconnect trusted peers and restore only their persisted capabilities."""

        recovered: dict[PeerId, tuple[CapabilityLease, ...]] = {}
        if self.trust_store is None:
            return recovered
        for record in self.trust_store.list_trusted():
            if self.trust_store.is_revoked(record.peer_id):
                continue
            leases: list[CapabilityLease] = []
            try:
                for capability in sorted(
                    self.trust_store.get_recovery_capabilities(record.peer_id),
                    key=lambda item: item.value,
                ):
                    leases.append(self.acquire(record.peer_id, capability))
            except Exception:
                for lease in leases:
                    lease.close()
                continue
            if leases:
                recovered[record.peer_id] = tuple(leases)
        return recovered

    def _require_lease_session(self, lease: CapabilityLease) -> PeerSession:
        session = self._sessions.get(lease.peer_id)
        if (
            session is None
            or not session.active
            or session.generation != lease.generation
            or self._leases.get(lease.token) is not lease
        ):
            raise StaleSessionError(f"stale capability lease for {lease.peer_id}")
        return session
