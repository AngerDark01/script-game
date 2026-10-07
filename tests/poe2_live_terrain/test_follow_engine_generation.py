from __future__ import annotations

from dataclasses import dataclass

from auto_modules.features.poe2.live_terrain.experimental.follow_engine.generation import (
    GenerationClock,
    SequenceGate,
)


@dataclass(frozen=True)
class Message:
    generation: int
    sequence: int
    map_instance: str


def test_generation_clock_invalidates_old_workers_and_increments_tokens():
    clock = GenerationClock()
    first = clock.begin("map-a")
    assert first.generation == 1
    assert clock.is_current(1, "map-a")
    clock.stop()
    assert clock.active is None
    assert not clock.is_current(1, "map-a")
    second = clock.begin("map-a")
    assert second.generation == 2
    assert second != first


def test_sequence_gate_accepts_only_fresh_messages_for_current_map():
    token = GenerationClock().begin("map-a")
    gate = SequenceGate(token)
    assert gate.accept(Message(token.generation, 1, "map-a")) is True
    assert gate.accept(Message(token.generation, 1, "map-a")) is False
    assert gate.accept(Message(token.generation, 0, "map-a")) is False
    assert gate.accept(Message(token.generation, 2, "map-b")) is False
    assert gate.accept(Message(token.generation - 1, 3, "map-a")) is False
    assert gate.accept(Message(token.generation, 2, "map-a")) is True
    assert gate.last_sequence == 2
    assert gate.stale_count == 4
