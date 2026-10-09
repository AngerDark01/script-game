from __future__ import annotations

from auto_modules.features.poe2.live_terrain.experimental.follow_engine.control.snapshot_output import (
    SnapshotOutputAdapter,
)
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.contracts import (
    FusionSnapshot,
    OutputIntent,
    RoleFusedState,
)


class FakeOutput:
    def __init__(self, *, fail_once: str | None = None):
        self.fail_once = fail_once
        self.started = 0
        self.writes = []
        self.heartbeats = 0
        self.stopped = 0
        self.closed = 0
        self.rearms = 0

    def start(self):
        self.started += 1

    def write(self, vector, *, elapsed_ms):
        if self.fail_once == "write":
            self.fail_once = None
            raise RuntimeError("Program session expired or was revoked")
        self.writes.append((tuple(vector), int(elapsed_ms)))

    def heartbeat(self):
        self.heartbeats += 1
        return True

    def rearm(self):
        self.rearms += 1

    def stop(self):
        self.stopped += 1

    def close(self):
        self.closed += 1

    def snapshot(self):
        return {"started": self.started, "writes": len(self.writes)}


def _snapshot(*, active=True, role="p2", controller=2, vector=(0.5, 0.0)):
    return FusionSnapshot(
        generation=1,
        created_at_ms=1,
        roles={
            role: RoleFusedState(
                role,
                (10.0, 10.0),
                (0.0, 0.0),
                1.0,
                "visual",
                0.0,
            )
        },
        recovery_state="follow_hold",
        recovery_reason="test",
        output_intents=(
            OutputIntent(role, controller, vector, 80, neutral=vector == (0.0, 0.0)),
        ),
        session_active=active,
    )


def test_output_receipt_keeps_control_and_target_correlation():
    from dataclasses import replace
    adapter = SnapshotOutputAdapter(outputs={"p2": FakeOutput()}, continuous_roles={"p2"})
    original = _snapshot()
    intent = replace(original.output_intents[0], control_tick=81, target_revision=12, visual_sequence=79)
    adapter.start()
    try:
        adapter.apply(replace(original, output_intents=(intent,)))
        receipt, = adapter.poll_receipts()
        assert (receipt.control_tick, receipt.target_revision, receipt.visual_sequence) == (81, 12, 79)
        assert receipt.vector == intent.vector
        assert receipt.valid_for_ms == intent.duration_ms
    finally:
        adapter.stop()


def test_snapshot_adapter_lazily_creates_and_rearms_expired_output():
    created = {}

    def factory(role, controller):
        output = FakeOutput(fail_once="write")
        created[(role, controller)] = output
        return output

    adapter = SnapshotOutputAdapter(output_factory=factory, continuous_roles={"p2"})
    adapter.start()
    adapter.apply(_snapshot())
    output = created[("p2", 2)]
    assert output.started == 1
    assert output.rearms == 1
    adapter.stop()
    assert output.stopped == 1
    assert output.closed == 1


def test_snapshot_adapter_gates_host_lease_until_arm_delay_without_blocking_control():
    now = [1000]
    created = []

    def factory(_role_id, _controller):
        output = FakeOutput()
        created.append(output)
        return output

    adapter = SnapshotOutputAdapter(
        output_factory=factory,
        continuous_roles={"p2"},
        arm_delay_ms=10000,
        clock_ms=lambda: now[0],
    )
    adapter.start()
    try:
        adapter.apply(_snapshot(role="p2", vector=(1.0, 0.0)))
        # The arm gate suppresses movement, but it must still establish a
        # neutral lease immediately.  Otherwise the first real command pays
        # both the configured focus handoff and Host session startup latency.
        assert len(created) == 1
        assert created[0].started == 1
        assert created[0].writes == [((0.0, 0.0), 20)]
        assert adapter.diagnostics()["arm_gate_remaining_ms"] == 10000

        now[0] += 9999
        adapter.apply(_snapshot(role="p2", vector=(1.0, 0.0)))
        assert all(vector == (0.0, 0.0) for vector, _duration in created[0].writes)
        assert adapter.poll_receipts() == ()
        now[0] += 1
        adapter.apply(_snapshot(role="p2", vector=(1.0, 0.0)))
        assert len(created) == 1
        assert created[0].started == 1
        assert created[0].writes
        assert created[0].writes[-1][0] == (1.0, 0.0)
    finally:
        adapter.stop()


def test_snapshot_adapter_neutralizes_without_releasing_continuous_role():
    output = FakeOutput()
    adapter = SnapshotOutputAdapter(outputs={"p2": output}, continuous_roles={"p2"})
    adapter.start()
    adapter.apply(_snapshot(active=True, vector=(0.0, 0.0)))
    adapter.stop(force=False)
    assert output.writes[-1][0] == (0.0, 0.0)
    assert output.stopped == 0
    assert output.closed == 1
