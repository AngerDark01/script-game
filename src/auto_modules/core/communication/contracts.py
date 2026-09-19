"""Device-neutral contracts for multiplexed communication.

This module deliberately contains no Host, LAN, UI, or feature imports.  It
defines the vocabulary shared by those adapters and by business features.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


@dataclass(frozen=True, slots=True)
class PeerId:
    """Stable identifier for a remote device."""

    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or not self.value.strip():
            raise ValueError("peer id must be a non-empty string")
        if len(self.value) > 128:
            raise ValueError("peer id is too long")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class SessionId:
    """Identifier for one physical connection generation."""

    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or not self.value.strip():
            raise ValueError("session id must be a non-empty string")
        if len(self.value) > 128:
            raise ValueError("session id is too long")

    def __str__(self) -> str:
        return self.value


class Capability(StrEnum):
    """Logical abilities that may share one physical peer session."""

    INPUT_SEND = "input.send"
    INPUT_RECEIVE = "input.receive"
    POSITION_PUBLISH = "position.publish"
    POSITION_SUBSCRIBE = "position.subscribe"
    EVENT_PUBLISH = "event.publish"
    EVENT_SUBSCRIBE = "event.subscribe"
    CATALOG_PUBLISH = "catalog.publish"
    CATALOG_SUBSCRIBE = "catalog.subscribe"
    MAP_PUBLISH = "map.publish"
    MAP_SUBSCRIBE = "map.subscribe"


class Topic(StrEnum):
    """Coarse topic lanes used by the generic dispatcher."""

    INPUT = "input"
    POSITION = "position"
    EVENT = "event"
    CATALOG = "catalog"
    MAP = "map"


class DeliveryMode(StrEnum):
    """Transport semantics requested by a message producer."""

    LATEST = "latest"
    RELIABLE_ORDERED = "reliable-ordered"
    VERSIONED_RESOURCE = "versioned-resource"


def capability_topic(capability: Capability) -> Topic:
    """Return the topic lane governed by a capability."""

    return Topic(capability.value.split(".", 1)[0])

