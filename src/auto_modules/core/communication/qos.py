"""Named QoS profiles for common communication message classes."""

from __future__ import annotations

from dataclasses import dataclass

from .contracts import DeliveryMode, Topic


@dataclass(frozen=True, slots=True)
class QoSProfile:
    delivery: DeliveryMode
    latest_value: bool = False
    ordered: bool = False
    versioned: bool = False


LATEST_STATE = QoSProfile(DeliveryMode.LATEST, latest_value=True)
RELIABLE_EVENT = QoSProfile(DeliveryMode.RELIABLE_ORDERED, ordered=True)
VERSIONED_RESOURCE = QoSProfile(DeliveryMode.VERSIONED_RESOURCE, versioned=True)


def qos_for_topic(topic: Topic | str) -> QoSProfile:
    topic = Topic(topic)
    if topic in (Topic.INPUT, Topic.POSITION):
        return LATEST_STATE
    if topic in (Topic.EVENT, Topic.CATALOG):
        return RELIABLE_EVENT
    return VERSIONED_RESOURCE


QoS = QoSProfile

