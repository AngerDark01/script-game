from __future__ import annotations

from auto_modules.features.poe2.live_terrain.experimental.follow_engine.latest_frame_buffer import LatestFrameBuffer
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.shared_frame_ring import (
    SharedFrameRecord,
    SharedFrameRing,
)


def test_latest_frame_buffer_keeps_only_newest_sequence():
    buffer = LatestFrameBuffer[str]()
    assert buffer.publish(1, "one") is True
    assert buffer.publish(2, "two") is True
    assert buffer.publish(1, "old") is False
    latest = buffer.take(after_sequence=1)
    assert latest is not None and latest.sequence == 2 and latest.value == "two"
    assert buffer.dropped_count == 2


def test_shared_frame_ring_is_bounded_and_returns_latest_payload():
    ring = SharedFrameRing(capacity=2, slot_size=32, map_instance="map-a")
    try:
        assert ring.publish(SharedFrameRecord(1, 1, 10, "map-a", b"one")) is True
        assert ring.publish(SharedFrameRecord(1, 2, 20, "map-a", b"two")) is True
        assert ring.publish(SharedFrameRecord(1, 1, 15, "map-a", b"old")) is False
        latest = ring.read_latest()
        assert latest is not None
        assert latest.sequence == 2
        assert latest.map_instance == "map-a"
        assert latest.payload == b"two"
        assert ring.read_latest(after_sequence=2) is None
    finally:
        ring.close(unlink=True)


def test_shared_frame_ring_rejects_wrong_instance_and_reads_exact_sequence():
    ring = SharedFrameRing(capacity=2, slot_size=32, map_instance="map-a")
    try:
        assert ring.publish(SharedFrameRecord(1, 4, 40, "map-a", b"four")) is True
        assert ring.read(4) is not None
        assert ring.read(3) is None
        try:
            ring.publish(SharedFrameRecord(1, 5, 50, "map-b", b"wrong"))
        except ValueError as exc:
            assert "map instance" in str(exc)
        else:
            raise AssertionError("wrong map instance was accepted")
        ring.rebind_session(map_instance="map-b")
        assert ring.read_latest() is None
        assert ring.publish(SharedFrameRecord(2, 6, 60, "map-b", b"six")) is True
    finally:
        ring.close(unlink=True)
