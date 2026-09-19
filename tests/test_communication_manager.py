from __future__ import annotations

from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest

from auto_modules.application.communication.manager import (
    CapabilityConflict,
    CommunicationManager,
    StaleSessionError,
)
from auto_modules.core.communication.contracts import Capability, PeerId, Topic
from auto_modules.core.communication.messages import MessageEnvelope
from auto_modules.core.communication.contracts import DeliveryMode
from auto_modules.application.communication.trust_store import FileTrustStore, TrustRecord


@dataclass
class FakeConnection:
    sent: list[MessageEnvelope] = field(default_factory=list)
    closed: bool = False

    def send(self, message: MessageEnvelope) -> None:
        self.sent.append(message)

    def close(self) -> None:
        self.closed = True


class FakeTransport:
    def __init__(self) -> None:
        self.connections: dict[str, FakeConnection] = {}
        self.connect_calls: list[str] = []

    def connect(self, peer_id: PeerId) -> FakeConnection:
        key = str(peer_id)
        self.connect_calls.append(key)
        connection = FakeConnection()
        self.connections[key] = connection
        return connection


def message(topic: Topic, value: int = 1) -> MessageEnvelope:
    return MessageEnvelope(
        message_id=f"m-{value}",
        topic=topic,
        payload={"value": value},
        delivery=DeliveryMode.LATEST,
        created_at_ms=100,
    )


def test_two_features_share_one_physical_session_and_release_independently() -> None:
    transport = FakeTransport()
    manager = CommunicationManager(transport)
    peer = PeerId("peer-a")
    first = manager.acquire(peer, Capability.POSITION_PUBLISH)
    second = manager.acquire(peer, Capability.EVENT_PUBLISH)
    assert transport.connect_calls == ["peer-a"]
    first.publish(message(Topic.POSITION))
    second.publish(message(Topic.EVENT, 2))
    assert len(transport.connections["peer-a"].sent) == 2
    first.close()
    assert transport.connections["peer-a"].closed is False
    second.close()
    assert transport.connections["peer-a"].closed is True


def test_dispatcher_fans_out_to_multiple_subscribers_without_shared_drain() -> None:
    transport = FakeTransport()
    manager = CommunicationManager(transport)
    peer = PeerId("peer-a")
    lease = manager.acquire(peer, Capability.EVENT_SUBSCRIBE)
    received: list[tuple[str, int]] = []
    lease.subscribe(Topic.EVENT, lambda item: received.append(("a", item.payload["value"])))
    manager.subscribe(peer, Topic.EVENT, lambda item: received.append(("b", item.payload["value"])))
    manager.dispatch_incoming(peer, message(Topic.EVENT, 3))
    assert received == [("a", 3), ("b", 3)]


def test_input_receive_is_exclusive() -> None:
    manager = CommunicationManager(FakeTransport())
    peer = PeerId("peer-a")
    manager.acquire(peer, Capability.INPUT_RECEIVE)
    with pytest.raises(CapabilityConflict):
        manager.acquire(peer, Capability.INPUT_RECEIVE)


def test_stale_generation_cannot_dispatch_after_manual_disconnect() -> None:
    transport = FakeTransport()
    manager = CommunicationManager(transport)
    peer = PeerId("peer-a")
    lease = manager.acquire(peer, Capability.EVENT_SUBSCRIBE)
    received: list[int] = []
    lease.subscribe(Topic.EVENT, lambda item: received.append(item.payload["value"]))
    generation = manager.session_generation(peer)
    manager.disconnect(peer, manual=True)
    with pytest.raises(StaleSessionError):
        manager.dispatch_incoming(peer, message(Topic.EVENT, 4), generation=generation)
    assert received == []


def test_recover_restores_persisted_capabilities_but_skips_revoked_peers(tmp_path) -> None:
    store = FileTrustStore(tmp_path)
    store.save(TrustRecord(PeerId("peer-a"), "device-a", "fp", "127.0.0.1", 45873))
    store.set_recovery_capabilities(PeerId("peer-a"), [Capability.EVENT_SUBSCRIBE])
    manager = CommunicationManager(FakeTransport(), trust_store=store)
    recovered = manager.recover()
    assert list(recovered) == [PeerId("peer-a")]
    assert manager.transport.connect_calls == ["peer-a"]
    manager.disconnect(PeerId("peer-a"), manual=True)
    assert store.get_recovery_capabilities(PeerId("peer-a")) == set()


def test_process_shutdown_preserves_trusted_recovery_preferences(tmp_path) -> None:
    store = FileTrustStore(tmp_path)
    peer = PeerId("peer-a")
    store.save(TrustRecord(peer, "device-a", "fp", "127.0.0.1", 45873))
    store.set_recovery_capabilities(peer, [Capability.EVENT_SUBSCRIBE])
    manager = CommunicationManager(FakeTransport(), trust_store=store)
    manager.acquire(peer, Capability.EVENT_SUBSCRIBE)

    manager.close()

    assert store.get_recovery_capabilities(peer) == {Capability.EVENT_SUBSCRIBE}


def test_concurrent_capability_requests_open_one_peer_connection() -> None:
    entered = Event()
    release = Event()
    duplicate_connect = Event()

    class SlowTransport(FakeTransport):
        attempts = 0

        def connect(self, peer_id: PeerId) -> FakeConnection:
            self.attempts += 1
            if self.attempts > 1:
                duplicate_connect.set()
            entered.set()
            assert release.wait(2)
            return super().connect(peer_id)

    transport = SlowTransport()
    manager = CommunicationManager(transport)
    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(manager.acquire, "peer-a", Capability.EVENT_SUBSCRIBE)
        assert entered.wait(2)
        second = executor.submit(manager.acquire, "peer-a", Capability.POSITION_SUBSCRIBE)
        try:
            assert not duplicate_connect.wait(0.1)
        finally:
            release.set()
        leases = (first.result(timeout=2), second.result(timeout=2))

    assert transport.connect_calls == ["peer-a"]
    for lease in leases:
        lease.close()
