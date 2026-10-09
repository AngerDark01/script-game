from __future__ import annotations

import time
import threading
from types import SimpleNamespace

from auto_modules.features.poe2.live_terrain.experimental.follow_engine.control.follow_control_process import FollowControlRuntime
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.generation import GenerationToken


def test_no_execution_receipt_means_no_command_displacement():
    runtime = FollowControlRuntime(GenerationToken(1, "a"), {"p2": 2})
    runtime.seed_position("p2", (0, 0), captured_at_ms=1000)
    runtime.update_target("p2", (1000, 0))
    try:
        for now in range(1000, 4001, 100):
            state = runtime.tick(now_ms=now)
        assert state.roles["p2"].position_native == (0, 0)
    finally:
        runtime.close()


def test_receipt_only_integrates_accepted_lease_once_and_rejects_stale_generation():
    from auto_modules.features.poe2.live_terrain.experimental.follow_engine.execution_feedback import ExecutionReceipt
    runtime = FollowControlRuntime(GenerationToken(1, "a"), {"p2": 2})
    runtime.seed_position("p2", (0, 0), captured_at_ms=1000)
    runtime.update_target("p2", (1000, 0))
    runtime.tick(now_ms=1000)
    assert not runtime.record_execution(ExecutionReceipt(2, 1, "p2", (1, 0), 1000, 100))
    assert runtime.record_execution(ExecutionReceipt(1, 1, "p2", (1, 0), 1000, 100))
    assert not runtime.record_execution(ExecutionReceipt(1, 1, "p2", (1, 0), 1000, 100))
    first = runtime.tick(now_ms=1100).roles["p2"].position_native
    assert first[0] > 0
    assert runtime.tick(now_ms=1300).roles["p2"].position_native == first
    runtime.close()


def test_live_async_output_does_not_block_ui_and_emits_only_actual_receipts():
    from auto_modules.features.poe2.live_terrain.experimental.follow_engine.control.async_output import AsyncSnapshotOutput
    from auto_modules.features.poe2.live_terrain.experimental.follow_engine.control.snapshot_output import SnapshotOutputAdapter
    entered, release = threading.Event(), threading.Event()

    class Output:
        def start(self): pass
        def heartbeat(self): return True
        def write(self, vector, *, elapsed_ms):
            entered.set()
            release.wait(2)
            return SimpleNamespace(accepted_at_ms=1000, effective_input_vector=vector, ttl_ms=80)
        def stop(self): pass
        def close(self): release.set()

    output = AsyncSnapshotOutput(SnapshotOutputAdapter({"p2": Output()}))
    runtime = FollowControlRuntime(GenerationToken(1, "a"), {"p2": 2})
    runtime.seed_position("p2", (0, 0), captured_at_ms=1000)
    runtime.update_target("p2", (1000, 0))
    output.start()
    try:
        started = time.monotonic()
        output.apply(runtime.tick(now_ms=1000))
        assert time.monotonic() - started < .1
        assert entered.wait(1)
        started = time.monotonic()
        output.diagnostics()
        assert time.monotonic() - started < .1
        assert output.poll_receipts() == ()
        release.set()
        deadline = time.monotonic() + 2
        receipts = ()
        while time.monotonic() < deadline and not receipts:
            receipts = output.poll_receipts()
            time.sleep(.01)
        assert receipts and receipts[0].vector[0] > 0
    finally:
        release.set()
        output.stop()
        runtime.close()
