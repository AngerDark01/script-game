from __future__ import annotations

import time
from dataclasses import dataclass

from auto_modules.features.poe2.live_terrain.experimental.follow_engine.generation import GenerationClock
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.recovery.global_recovery import GlobalRecoveryBackend
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.recovery.local_recovery import LocalRecoveryBackend
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.recovery.memory_recovery import MemoryRecoveryBackend
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.vision.local_roi_matcher import RoiMatch


@dataclass(frozen=True)
class Sample:
    identity: str
    grid: tuple[float, float]
    area_instance: str


class Source:
    def read_many(self, expected_instance_id):
        return (Sample("p1", (1, 2), expected_instance_id), Sample("p2", (3, 4), expected_instance_id))


def test_memory_backend_reuses_transform_and_returns_generation():
    token = GenerationClock().begin("Area:1")
    backend = MemoryRecoveryBackend(Source(), transform=lambda point: (point[0] + 10, point[1] + 20), cooldown_ms=8000)
    result = backend.read(token, now_ms=10_000)
    assert result.generation == token.generation
    assert result.positions["p2"] == (13.0, 24.0)


def test_local_backend_tries_bounded_roi_and_returns_without_stop():
    calls = []

    def search(_frame, point, radius):
        calls.append(radius)
        return RoiMatch(radius >= 140, (point[0] + 1, point[1]), 0.8 if radius >= 140 else 0.1, radius, "ok")

    result = LocalRecoveryBackend().match(object(), (10, 20), search)
    assert result.valid is True
    assert calls == [80.0, 140.0]


def test_global_backend_single_flight_and_generation_checked_poll():
    backend = GlobalRecoveryBackend(lambda: ("registered",))
    token = GenerationClock().begin("map-a")
    assert backend.submit(token) is True
    assert backend.submit(token) is False
    deadline = time.monotonic() + 2
    result = None
    while time.monotonic() < deadline and result is None:
        result = backend.poll(token)
        time.sleep(0.01)
    try:
        assert result is not None and result.value == ("registered",)
    finally:
        backend.close()


def test_global_backend_does_not_resubmit_completed_unpolled_future():
    backend = GlobalRecoveryBackend(lambda: ("fast",))
    token = GenerationClock().begin("map-a")
    assert backend.submit(token) is True
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline and not backend._future.done():
        time.sleep(0.01)
    # The worker can finish before the control tick polls its result; the
    # completed future must still occupy the single-flight slot.
    assert backend.submit(token) is False
    result = backend.poll(token)
    assert result is not None and result.value == ("fast",)
    assert backend.submit(token) is True
    backend.close()


def test_global_backend_rejects_same_generation_from_different_map_instance():
    backend = GlobalRecoveryBackend(lambda: ("map-a",))
    token_a = GenerationClock().begin("map-a")
    assert backend.submit(token_a) is True
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline and not backend._future.done():
        time.sleep(0.005)
    token_b = type(token_a)(token_a.generation, "map-b")
    try:
        result = backend.poll(token_b)
        assert result is not None
        assert result.error == "stale_global_result"
    finally:
        backend.close()


def test_global_backend_backs_off_after_worker_failure():
    now = [0]

    def worker():
        raise RuntimeError("registration failed")

    backend = GlobalRecoveryBackend(
        worker,
        failure_cooldown_ms=100,
        max_failure_cooldown_ms=400,
        clock_ms=lambda: now[0],
    )
    token = GenerationClock().begin("map-a")
    assert backend.submit(token, now_ms=0) is True
    deadline = time.monotonic() + 2
    result = None
    while time.monotonic() < deadline and result is None:
        result = backend.poll(token)
        time.sleep(0.005)
    try:
        assert result is not None and result.error.startswith("RuntimeError")
        assert backend.cooldown_ready(now_ms=0) is False
        assert backend.submit(token, now_ms=0) is False
        assert backend.cooldown_ready(now_ms=100) is True
        assert backend.submit(token, now_ms=100) is True
    finally:
        backend.close()


def test_global_backend_worker_failure_uses_submit_clock_for_cooldown():
    """A caller-provided epoch clock must survive the async exception path.

    Runtime ticks use one explicit time domain.  The backend's default clock
    is monotonic, so omitting ``now_ms`` while polling would schedule the
    failure cooldown in a different domain and make it immediately ready.
    """
    now = [1_790_000_000_000]

    def worker():
        raise RuntimeError("registration failed")

    backend = GlobalRecoveryBackend(
        worker,
        failure_cooldown_ms=500,
        max_failure_cooldown_ms=2_000,
        # Deliberately use a different clock to prove explicit now_ms wins.
        clock_ms=lambda: 20_000,
    )
    token = GenerationClock().begin("map-a")
    assert backend.submit(token, now_ms=now[0]) is True
    deadline = time.monotonic() + 2
    result = None
    while time.monotonic() < deadline and result is None:
        result = backend.poll(token, now_ms=now[0])
        time.sleep(0.005)
    try:
        assert result is not None and result.error.startswith("RuntimeError")
        assert backend.cooldown_ready(now_ms=now[0]) is False
        now[0] += 500
        assert backend.cooldown_ready(now_ms=now[0]) is True
    finally:
        backend.close()


def test_global_backend_failure_poll_uses_submission_clock_when_supplied():
    def worker():
        raise RuntimeError("registration failed")

    backend = GlobalRecoveryBackend(worker, failure_cooldown_ms=100, clock_ms=lambda: 0)
    token = GenerationClock().begin("map-a")
    assert backend.submit(token, now_ms=100_000) is True
    deadline = time.monotonic() + 2
    result = None
    while time.monotonic() < deadline and result is None:
        result = backend.poll(token, now_ms=100_000)
        time.sleep(0.005)
    try:
        assert result is not None and result.error
        assert backend.cooldown_ready(now_ms=100_000) is False
        assert backend.cooldown_ready(now_ms=100_100) is True
    finally:
        backend.close()
