from __future__ import annotations

import threading
import time
from types import SimpleNamespace

import pytest

from auto_modules.features.poe2.live_terrain.experimental.follow_engine.shared_frame_ring import SharedFrameRing
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.control.follow_control_process import FollowControlProcessHandle
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.control.snapshot_output import SnapshotOutputAdapter
from auto_modules.features.poe2.live_terrain.experimental.follow_engine import composition as module


def test_ring_lock_wait_is_bounded_and_poisoned_ring_is_not_reused():
    ring = SharedFrameRing(slot_size=64)
    ring._lock.acquire()
    timer = threading.Timer(0.5, ring._lock.release)
    timer.start()
    try:
        started = time.monotonic()
        with pytest.raises(TimeoutError):
            ring.read_latest()
        assert time.monotonic() - started < 0.3
        timer.join(1)
        with pytest.raises(TimeoutError):
            ring.rebind_session(map_instance="new")
    finally:
        timer.join(1)
        ring.close(unlink=True)


def test_constructor_failure_disposes_allocated_ring(monkeypatch):
    made = []
    original = module.SharedFrameRing

    def create(**kwargs):
        ring = original(**kwargs)
        made.append(ring)
        return ring

    monkeypatch.setattr(module, "SharedFrameRing", create)
    seed = module.FollowSeedBundle(map_instance="a", roles={"p1": 1}, initial_positions_native={"p1": (1, 1)})
    try:
        with pytest.raises(ValueError):
            module.build_follow_engine_composition(seed=seed, capture=object(), output=object(),
                                                  ring_slot_size=64, memory_source=object())
        assert all(r._shm is None for r in made)
    finally:
        for ring in made:
            ring.close(unlink=True)


def test_unstarted_process_stop_clears_reference_without_join():
    handle = FollowControlProcessHandle({"p1": 1})
    process = handle.context.Process(target=time.time)
    handle.process = process
    try:
        handle.stop(timeout=0)
        assert handle.process is None
    finally:
        for channel in (handle.commands, handle.events):
            channel.cancel_join_thread()
            channel.close()


class Output:
    def __init__(self, fail=False):
        self.fail = fail
        self.stops = self.closes = 0

    def start(self): pass
    def write(self, vector, *, elapsed_ms): pass
    def heartbeat(self): return True
    def stop(self):
        self.stops += 1
        if self.fail: raise RuntimeError("offline stop error")
    def close(self): self.closes += 1


def test_output_cleanup_error_does_not_skip_other_roles_or_close():
    outputs = {"p1": Output(True), "p2": Output()}
    adapter = SnapshotOutputAdapter(outputs)
    adapter.start()
    snapshot = SimpleNamespace(session_active=True, output_intents=tuple(
        SimpleNamespace(role_id=role, controller=index + 1, vector=(0.1, 0), duration_ms=20)
        for index, role in enumerate(outputs)))
    adapter.apply(snapshot)
    try:
        with pytest.raises(RuntimeError, match="offline stop error"):
            adapter.stop()
        assert all(o.stops == 1 and o.closes == 1 for o in outputs.values())
        assert adapter.diagnostics()["roles"] == ()
    finally:
        if adapter.started:
            outputs["p1"].fail = False
            adapter.stop()
