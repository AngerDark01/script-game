from __future__ import annotations

import time

from auto_modules.features.poe2.live_terrain.experimental.follow_engine.contracts import FusionSnapshot, OutputIntent
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.control.output_scheduler import OutputScheduler


class FakePort:
    def __init__(self):
        self.started = 0
        self.stopped = 0
        self.writes = []
        self.heartbeats = 0
        self.expire_once = False

    def start(self):
        self.started += 1

    def write(self, vector, *, elapsed_ms):
        if self.expire_once:
            self.expire_once = False
            raise RuntimeError("Program session expired or was revoked")
        self.writes.append((vector, elapsed_ms))

    def rearm(self):
        self.started += 1

    def stop(self):
        self.stopped += 1

    def heartbeat(self):
        self.heartbeats += 1
        return True


def _snapshot(*, active=True, vector=(0.5, 0.0)):
    return FusionSnapshot(
        generation=1,
        created_at_ms=10,
        roles={},
        recovery_state="tracking",
        recovery_reason="test",
        output_intents=(OutputIntent("p2", 2, vector, 40, neutral=vector == (0.0, 0.0)),),
        session_active=active,
    )


def test_scheduler_rearms_expired_session_and_keeps_heartbeat_independent():
    port = FakePort()
    port.expire_once = True
    scheduler = OutputScheduler({"p2": port}, continuous_roles={"p2"}, heartbeat_interval_ms=20)
    scheduler.start()
    try:
        scheduler.apply(_snapshot())
        time.sleep(0.08)
        diagnostics = scheduler.diagnostics()
        assert port.started == 2
        assert port.writes[-1][0] == (0.5, 0.0)
        assert diagnostics["rearm_count"] == 1
        assert diagnostics["heartbeat_count"] >= 1
    finally:
        scheduler.stop(force=True)
    assert port.stopped == 1


def test_continuous_role_neutralizes_without_releasing_when_requested():
    port = FakePort()
    scheduler = OutputScheduler({"p2": port}, continuous_roles={"p2"})
    scheduler.start()
    scheduler.apply(_snapshot())
    scheduler.stop(force=False)
    assert port.stopped == 0
    assert port.writes[-1][0] == (0.0, 0.0)
