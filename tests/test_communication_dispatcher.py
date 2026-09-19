from __future__ import annotations

from auto_modules.application.communication.dispatcher import MessageDispatcher
from auto_modules.core.communication.contracts import PeerId, Topic, DeliveryMode
from auto_modules.core.communication.messages import MessageEnvelope


def test_subscription_can_be_closed_without_affecting_other_subscribers() -> None:
    dispatcher = MessageDispatcher()
    peer = PeerId("peer-a")
    seen: list[str] = []
    first = dispatcher.subscribe(peer, Topic.EVENT, lambda _: seen.append("first"))
    dispatcher.subscribe(peer, Topic.EVENT, lambda _: seen.append("second"))
    first.close()
    dispatcher.dispatch(peer, MessageEnvelope("m", Topic.EVENT, {}, DeliveryMode.RELIABLE_ORDERED, 1))
    assert seen == ["second"]


def test_unknown_topic_is_isolated() -> None:
    dispatcher = MessageDispatcher()
    peer = PeerId("peer-a")
    seen: list[str] = []
    dispatcher.subscribe(peer, Topic.POSITION, lambda _: seen.append("position"))
    dispatcher.dispatch(peer, MessageEnvelope("m", Topic.MAP, {}, DeliveryMode.VERSIONED_RESOURCE, 1))
    assert seen == []
