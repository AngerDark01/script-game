from dataclasses import dataclass

import pytest

from auto_modules.features.poe2.live_terrain.experimental.multiplayer_follow.recovery.memory_fast_reanchor import MemoryFastReanchor


@dataclass(frozen=True)
class Sample:
    identity: str
    grid: tuple[float, float]
    area_instance: str


class Source:
    def __init__(self):
        self.calls = 0
        self.area = None

    def read_many(self, expected_instance_id):
        self.calls += 1
        area = self.area or expected_instance_id
        return (Sample("p1", (1, 2), area), Sample("p2", (3, 4), area))


def test_fast_reanchor_reads_both_roles_and_applies_transform_once():
    source = Source()
    fast = MemoryFastReanchor(source, transform=lambda point: (point[0] + 10, point[1] + 20), cooldown_ms=8000)
    result = fast.read(expected_instance_id="Area:1", now_ms=10_000)
    assert result.positions == {"p1": (11.0, 22.0), "p2": (13.0, 24.0)}
    assert source.calls == 1


def test_fast_reanchor_cooldown_and_instance_mismatch():
    source = Source()
    fast = MemoryFastReanchor(source, transform=lambda point: point, cooldown_ms=8000)
    fast.read(expected_instance_id="Area:1", now_ms=10_000)
    with pytest.raises(RuntimeError, match="cooldown"):
        fast.read(expected_instance_id="Area:1", now_ms=10_100)
    source.area = "Area:wrong"
    with pytest.raises(RuntimeError, match="instance"):
        fast.read(expected_instance_id="Area:2", now_ms=20_000)


def test_fast_reanchor_requires_two_players():
    source = Source()
    source.read_many = lambda _instance: (Sample("p1", (1, 2), "Area:1"),)
    fast = MemoryFastReanchor(source, transform=lambda point: point)
    with pytest.raises(RuntimeError, match="expected 2 players"):
        fast.read(expected_instance_id="Area:1", now_ms=10_000)
