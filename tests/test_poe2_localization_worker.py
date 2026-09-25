from __future__ import annotations

import threading
import time
from types import SimpleNamespace

from auto_modules.ui.modes.poe2_live_terrain.localization_worker import Poe2LocalizationWorker


def test_worker_serializes_ticks_and_waits_for_explicit_recovery() -> None:
    class Runtime:
        def __init__(self):
            self.active = 0
            self.max_active = 0
            self.ticks = 0
            self.retries = 0
            self.started = False
            self.stopped = False
            self.ready = threading.Event()

        def start(self):
            self.started = True

        def tick(self):
            self.active += 1
            self.max_active = max(self.max_active, self.active)
            self.ticks += 1
            self.active -= 1
            self.ready.set()
            mode = "recovery_required" if self.ticks == 1 else "local_tracking"
            return SimpleNamespace(mode=mode)

        def retry_recovery(self):
            self.retries += 1

        def stop(self):
            self.stopped = True

    runtime = Runtime()
    worker = Poe2LocalizationWorker(runtime, generation=3, fps=30)
    worker.start()
    assert runtime.ready.wait(1.0)
    time.sleep(0.08)
    assert runtime.ticks == 1
    worker.retry_recovery()
    deadline = time.perf_counter() + 1.0
    while runtime.ticks < 2 and time.perf_counter() < deadline:
        time.sleep(0.01)
    worker.stop()
    worker._thread.join(2.0)
    assert runtime.started and runtime.stopped
    assert runtime.retries == 1
    assert runtime.ticks >= 2
    assert runtime.max_active == 1


def test_worker_keeps_only_latest_pending_display_state() -> None:
    runtime = SimpleNamespace(start=lambda: None, tick=lambda: None, stop=lambda: None)
    worker = Poe2LocalizationWorker(runtime, generation=1, fps=30)
    notifications = []
    worker.state_available.connect(notifications.append)

    worker._offer_state("first")
    worker._offer_state("second")

    assert notifications == [1]
    assert worker.skipped_display_states == 1
    assert worker.take_latest_state() == "second"
    assert worker.take_latest_state() is None
