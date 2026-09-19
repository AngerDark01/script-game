"""Capability leases that scope business access to a shared peer session."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from auto_modules.core.communication.contracts import Capability, Topic
from auto_modules.core.communication.messages import MessageEnvelope

if TYPE_CHECKING:
    from .dispatcher import _Subscription
    from .manager import CommunicationManager


class CapabilityLease:
    def __init__(
        self,
        manager: "CommunicationManager",
        peer_id: Any,
        token: str,
        capability: Capability,
        generation: int,
    ) -> None:
        self._manager = manager
        self.peer_id = peer_id
        self.token = token
        self.capability = capability
        self.generation = generation
        self._closed = False
        self._subscriptions: list[_Subscription] = []

    @property
    def closed(self) -> bool:
        return self._closed

    def publish(self, message: MessageEnvelope) -> None:
        self._ensure_open()
        self._manager.publish(self, message)

    def subscribe(
        self,
        topic: Topic | str,
        callback: Callable[[MessageEnvelope], Any],
    ) -> "_Subscription":
        self._ensure_open()
        subscription = self._manager.subscribe(self, topic, callback)
        self._subscriptions.append(subscription)
        return subscription

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        for subscription in tuple(self._subscriptions):
            subscription.close()
        self._subscriptions.clear()
        self._manager.release(self)

    def _invalidate(self) -> None:
        self._closed = True
        for subscription in tuple(self._subscriptions):
            subscription.close()
        self._subscriptions.clear()

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("capability lease is closed")

