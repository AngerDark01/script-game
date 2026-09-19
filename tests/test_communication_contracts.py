from __future__ import annotations

import pytest

from auto_modules.core.communication.contracts import (
    Capability,
    DeliveryMode,
    PeerId,
    SessionId,
    Topic,
)
from auto_modules.core.communication.messages import MessageEnvelope


def test_identifiers_are_immutable_and_reject_invalid_values() -> None:
    assert str(PeerId("peer-a")) == "peer-a"
    assert SessionId("session-a") == SessionId("session-a")
    with pytest.raises(ValueError):
        PeerId("")
    with pytest.raises(ValueError):
        SessionId(" ")


def test_capabilities_and_topics_are_device_neutral() -> None:
    assert Capability.POSITION_PUBLISH.value == "position.publish"
    assert Capability.MAP_SUBSCRIBE.value == "map.subscribe"
    assert Topic.POSITION.value == "position"
    assert DeliveryMode.RELIABLE_ORDERED.value == "reliable-ordered"


def test_envelope_validates_ttl_deadline_and_exposes_expiry() -> None:
    envelope = MessageEnvelope(
        message_id="m-1",
        topic=Topic.POSITION,
        payload={"x": 1},
        delivery=DeliveryMode.LATEST,
        created_at_ms=100,
        ttl_ms=500,
    )
    assert envelope.is_expired(599) is False
    assert envelope.is_expired(600) is True
    assert envelope.remaining_ms(250) == 350
    with pytest.raises(ValueError):
        MessageEnvelope("m-2", Topic.POSITION, {}, DeliveryMode.LATEST, 100, ttl_ms=0)
    with pytest.raises(ValueError):
        MessageEnvelope("m-3", Topic.EVENT, {}, DeliveryMode.RELIABLE_ORDERED, 100, deadline_ms=100)
    with pytest.raises(ValueError):
        MessageEnvelope("m-4", Topic.EVENT, {}, DeliveryMode.RELIABLE_ORDERED, 100, sequence=-1)


def test_compatibility_constructors_keep_shared_position_and_event_fields() -> None:
    class Position:
        device_id = "device-a"
        actor_id = "actor-1"
        map_id = "map"
        map_version = "v1"
        position = (12.0, 15.0)
        confidence = 0.8
        captured_at_ms = 900
        session_id = "session-a"

    class Event:
        device_id = "device-a"
        event_id = "event-1"
        name = "portal"
        targets = ("actor-1",)
        deadline_ms = 1_200
        session_id = "session-a"

    position = MessageEnvelope.from_shared_position(Position(), now_ms=1_000, message_id="p-1")
    event = MessageEnvelope.from_shared_event(Event(), now_ms=1_000, message_id="e-1")
    assert position.topic is Topic.POSITION
    assert position.payload["actorId"] == "actor-1"
    assert position.ttl_ms == 500
    assert event.topic is Topic.EVENT
    assert event.payload["eventId"] == "event-1"
    assert event.deadline_ms == 1_200
