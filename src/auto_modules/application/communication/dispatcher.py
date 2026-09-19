"""Single-reader fan-out for logical communication topics."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from auto_modules.core.communication.contracts import PeerId, Topic
from auto_modules.core.communication.messages import MessageEnvelope


@dataclass(slots=True)
class _Subscription:
    dispatcher: "MessageDispatcher"
    token: str
    peer_id: PeerId
    topic: Topic
    callback: Callable[[MessageEnvelope], Any]
    closed: bool = False

    def close(self) -> None:
        if not self.closed:
            self.closed = True
            self.dispatcher._subscriptions.pop(self.token, None)


class MessageDispatcher:
    """Dispatch each inbound envelope to all matching logical subscribers."""

    def __init__(self) -> None:
        self._subscriptions: dict[str, _Subscription] = {}

    def subscribe(
        self,
        peer_id: PeerId,
        topic: Topic | str,
        callback: Callable[[MessageEnvelope], Any],
    ) -> _Subscription:
        subscription = _Subscription(self, uuid4().hex, PeerId(str(peer_id)), Topic(topic), callback)
        self._subscriptions[subscription.token] = subscription
        return subscription

    def dispatch(self, peer_id: PeerId, message: MessageEnvelope) -> None:
        peer_id = PeerId(str(peer_id))
        for subscription in tuple(self._subscriptions.values()):
            if (
                not subscription.closed
                and subscription.peer_id == peer_id
                and subscription.topic == message.topic
            ):
                subscription.callback(message)

    def close_peer(self, peer_id: PeerId) -> None:
        for subscription in tuple(self._subscriptions.values()):
            if subscription.peer_id == peer_id:
                subscription.close()

