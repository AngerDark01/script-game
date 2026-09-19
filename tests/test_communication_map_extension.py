from __future__ import annotations

import pytest

from auto_modules.application.communication.dispatcher import MessageDispatcher
from auto_modules.core.communication import Capability, DeliveryMode, MessageEnvelope, PeerId, Topic


def test_map_capabilities_and_versioned_resource_metadata_are_declarative_only() -> None:
    assert Capability.MAP_PUBLISH.value == "map.publish"
    envelope = MessageEnvelope(
        "map-1",
        Topic.MAP,
        {"bytes": 3},
        DeliveryMode.VERSIONED_RESOURCE,
        100,
        resource_type="map",
        resource_id="world-1",
        version="v1",
        manifest_hash="sha256:abc",
        chunk_index=0,
        chunk_count=1,
    )
    assert envelope.chunk_count == 1
    with pytest.raises(ValueError):
        MessageEnvelope("map-2", Topic.MAP, {}, DeliveryMode.VERSIONED_RESOURCE, 100, chunk_index=1, chunk_count=1)


def test_unknown_map_messages_do_not_affect_other_topic_dispatch() -> None:
    dispatcher = MessageDispatcher()
    seen: list[str] = []
    dispatcher.subscribe(PeerId("peer-a"), Topic.POSITION, lambda _: seen.append("position"))
    dispatcher.dispatch(
        PeerId("peer-a"),
        MessageEnvelope(
            "map-1", Topic.MAP, {}, DeliveryMode.VERSIONED_RESOURCE, 100,
            resource_type="map", resource_id="map", version="v1", manifest_hash="hash",
            chunk_index=0, chunk_count=1,
        ),
    )
    assert seen == []
