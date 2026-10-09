from __future__ import annotations

import threading
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


class FalseHeartbeatPort(FakePort):
    def heartbeat(self):
        self.heartbeats += 1
        return False


class BlockingStopPort(FakePort):
    def __init__(self):
        super().__init__()
        self.stop_started = threading.Event()
        self.allow_stop = threading.Event()

    def stop(self):
        self.stop_started.set()
        self.allow_stop.wait(timeout=2.0)
        super().stop()


class BlockingNeutralWritePort(FakePort):
    def __init__(self):
        super().__init__()
        self.neutral_started = threading.Event()
        self.allow_neutral = threading.Event()

    def write(self, vector, *, elapsed_ms):
        if vector == (0.0, 0.0):
            self.neutral_started.set()
            self.allow_neutral.wait(timeout=2.0)
        return super().write(vector, elapsed_ms=elapsed_ms)


class BlockingStartPort(FakePort):
    def __init__(self):
        super().__init__()
        self.start_started = threading.Event()
        self.allow_start = threading.Event()

    def start(self):
        self.start_started.set()
        self.allow_start.wait(timeout=2.0)
        super().start()


class BlockingRearmPort(FakePort):
    def __init__(self):
        super().__init__()
        self.rearm_started = threading.Event()
        self.allow_rearm = threading.Event()
        self.expire_once = False

    def write(self, vector, *, elapsed_ms):
        if self.expire_once:
            self.expire_once = False
            raise RuntimeError("Program session expired or was revoked")
        return super().write(vector, elapsed_ms=elapsed_ms)

    def rearm(self):
        self.rearm_started.set()
        self.allow_rearm.wait(timeout=2.0)
        super().rearm()


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


def test_false_heartbeat_rearms_the_output_lease():
    port = FalseHeartbeatPort()
    scheduler = OutputScheduler({"p2": port}, continuous_roles={"p2"}, heartbeat_interval_ms=20)
    scheduler.start()
    scheduler.apply(_snapshot())
    try:
        time.sleep(0.08)
        diagnostics = scheduler.diagnostics()
        assert port.started >= 2
        assert diagnostics["rearm_count"] >= 1
        assert diagnostics["heartbeat_failures"] >= 1
    finally:
        scheduler.stop(force=True)


def test_stop_does_not_hold_scheduler_lock_during_port_stop():
    port = BlockingStopPort()
    scheduler = OutputScheduler({"p2": port}, continuous_roles={"p2"})
    scheduler.apply(_snapshot())
    stop_thread = threading.Thread(target=scheduler.stop)
    diagnostics_done = threading.Event()
    diagnostics_result = {}

    def read_diagnostics():
        diagnostics_result["value"] = scheduler.diagnostics()
        diagnostics_done.set()

    stop_thread.start()
    assert port.stop_started.wait(timeout=1.0)
    diagnostics_thread = threading.Thread(target=read_diagnostics)
    diagnostics_thread.start()
    try:
        assert diagnostics_done.wait(timeout=0.5), (
            "diagnostics must remain responsive while a role's stop I/O is blocked"
        )
        assert "p2" in diagnostics_result["value"]["armed_roles"]
    finally:
        port.allow_stop.set()
        stop_thread.join(timeout=1.0)
        diagnostics_thread.join(timeout=1.0)
    assert not stop_thread.is_alive()
    assert port.stopped == 1


def test_blocked_role_stop_does_not_block_or_restart_other_role_output():
    blocked = BlockingStopPort()
    other = FakePort()
    scheduler = OutputScheduler({"p1": other, "p2": blocked})
    scheduler.apply(_snapshot())
    scheduler.apply(
        FusionSnapshot(
            generation=1,
            created_at_ms=10,
            roles={},
            recovery_state="tracking",
            recovery_reason="test",
            output_intents=(OutputIntent("p1", 1, (0.25, 0.0), 40),),
            session_active=True,
        )
    )
    stop_thread = threading.Thread(target=scheduler.stop)
    stop_thread.start()
    assert blocked.stop_started.wait(timeout=1.0)
    other_done = threading.Event()

    def apply_other_role():
        scheduler.apply(
            FusionSnapshot(
                generation=1,
                created_at_ms=10,
                roles={},
                recovery_state="tracking",
                recovery_reason="test",
                output_intents=(OutputIntent("p1", 1, (0.75, 0.0), 40),),
                session_active=True,
            )
        )
        other_done.set()

    apply_thread = threading.Thread(target=apply_other_role)
    apply_thread.start()
    try:
        assert other_done.wait(timeout=0.5), (
            "a blocked role stop must not hold the scheduler lock for other roles"
        )
        assert other.writes[-1][0] == (0.25, 0.0), (
            "a force stop must reject late writes for every role"
        )
    finally:
        blocked.allow_stop.set()
        stop_thread.join(timeout=1.0)
        apply_thread.join(timeout=1.0)
    assert not stop_thread.is_alive()
    assert not apply_thread.is_alive()


def test_neutralize_does_not_hold_scheduler_lock_during_neutral_write():
    port = BlockingNeutralWritePort()
    scheduler = OutputScheduler({"p2": port}, continuous_roles={"p2"})
    scheduler.apply(_snapshot())
    neutralize_thread = threading.Thread(target=scheduler.neutralize)
    diagnostics_done = threading.Event()
    diagnostics_result = {}

    def read_diagnostics():
        diagnostics_result["value"] = scheduler.diagnostics()
        diagnostics_done.set()

    neutralize_thread.start()
    assert port.neutral_started.wait(timeout=1.0)
    diagnostics_thread = threading.Thread(target=read_diagnostics)
    diagnostics_thread.start()
    try:
        assert diagnostics_done.wait(timeout=0.5), (
            "diagnostics must remain responsive while neutral output I/O is blocked"
        )
        assert "p2" in diagnostics_result["value"]["armed_roles"]
    finally:
        port.allow_neutral.set()
        neutralize_thread.join(timeout=1.0)
        diagnostics_thread.join(timeout=1.0)
    assert not neutralize_thread.is_alive()
    assert port.writes[-1][0] == (0.0, 0.0)


def test_stop_racing_first_apply_cannot_restart_a_stopped_role():
    port = BlockingStartPort()
    scheduler = OutputScheduler({"p2": port})
    apply_thread = threading.Thread(target=lambda: scheduler.apply(_snapshot()))
    apply_thread.start()
    assert port.start_started.wait(timeout=1.0)
    scheduler.stop(force=True)
    port.allow_start.set()
    apply_thread.join(timeout=1.0)
    assert not apply_thread.is_alive()
    assert port.started == 1
    assert port.stopped == 1
    assert port.writes == []


def test_stop_racing_heartbeat_does_not_call_stale_port():
    port = FakePort()
    scheduler = OutputScheduler({"p2": port}, continuous_roles={"p2"}, heartbeat_interval_ms=20)
    scheduler.apply(_snapshot())
    original = port.heartbeat
    entered = threading.Event()
    release = threading.Event()

    def blocked_heartbeat():
        entered.set()
        release.wait(timeout=2.0)
        return original()

    port.heartbeat = blocked_heartbeat
    scheduler.start()
    assert entered.wait(timeout=1.0)
    scheduler.stop(force=True)
    release.set()
    time.sleep(0.05)
    assert port.stopped == 1


def test_apply_after_force_stop_cannot_write_an_armed_role():
    blocked = BlockingStopPort()
    other = FakePort()
    scheduler = OutputScheduler({"p1": other, "p2": blocked})
    scheduler.apply(_snapshot())
    p1_snapshot = FusionSnapshot(
        generation=1, created_at_ms=10, roles={},
        recovery_state="tracking", recovery_reason="test",
        output_intents=(OutputIntent("p1", 1, (0.25, 0.0), 40),),
    )
    scheduler.apply(p1_snapshot)
    stop_thread = threading.Thread(target=scheduler.stop)
    stop_thread.start()
    assert blocked.stop_started.wait(timeout=1.0)
    try:
        scheduler.apply(p1_snapshot)
        assert len(other.writes) == 1
    finally:
        blocked.allow_stop.set()
        stop_thread.join(timeout=1.0)


def test_stop_during_false_heartbeat_does_not_rearm():
    port = FakePort()
    scheduler = OutputScheduler({"p2": port}, heartbeat_interval_ms=20)
    scheduler.apply(_snapshot())
    entered = threading.Event()
    release = threading.Event()

    def false_heartbeat():
        entered.set()
        release.wait(timeout=2.0)
        return False

    port.heartbeat = false_heartbeat
    scheduler.start()
    assert entered.wait(timeout=1.0)
    stop_thread = threading.Thread(target=scheduler.stop)
    stop_thread.start()
    assert scheduler._stop.wait(timeout=1.0)
    release.set()
    stop_thread.join(timeout=1.0)
    assert not stop_thread.is_alive()
    assert port.started == 1, "a stopped session cannot rearm after late heartbeat"
    assert port.stopped == 1


def test_stale_rearm_after_stop_does_not_emit_execution_receipt():
    port = BlockingRearmPort()
    receipts = []
    scheduler = OutputScheduler({"p2": port}, on_write=lambda intent, result: receipts.append(result))
    scheduler.apply(_snapshot())
    port.expire_once = True
    apply_thread = threading.Thread(target=lambda: scheduler.apply(_snapshot()))
    apply_thread.start()
    assert port.rearm_started.wait(timeout=1.0)
    stop_thread = threading.Thread(target=scheduler.stop)
    stop_thread.start()
    port.allow_rearm.set()
    apply_thread.join(timeout=1.0)
    stop_thread.join(timeout=1.0)
    assert not apply_thread.is_alive()
    assert not stop_thread.is_alive()
    assert len(receipts) == 1, "the stale post-stop write must not create a receipt"


def test_prime_neutral_arms_once_without_replacing_active_movement():
    port = FakePort()
    scheduler = OutputScheduler({"p2": port}, continuous_roles={"p2"})
    scheduler.prime_neutral(("p2",))
    assert port.started == 1
    assert port.writes == [((0.0, 0.0), 20)]
    scheduler.apply(_snapshot())
    scheduler.prime_neutral(("p2",))
    assert port.started == 1
    assert port.writes == [((0.0, 0.0), 20), ((0.5, 0.0), 40)]
    scheduler.stop()


def test_stop_racing_prime_neutral_cleans_up_without_writing():
    port = BlockingStartPort()
    scheduler = OutputScheduler({"p2": port})
    prime_thread = threading.Thread(target=lambda: scheduler.prime_neutral(("p2",)))
    prime_thread.start()
    assert port.start_started.wait(timeout=1.0)
    scheduler.stop()
    port.allow_start.set()
    prime_thread.join(timeout=1.0)
    assert not prime_thread.is_alive()
    assert port.started == port.stopped == 1
    assert port.writes == []
