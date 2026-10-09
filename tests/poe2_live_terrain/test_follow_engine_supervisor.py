from __future__ import annotations

from types import SimpleNamespace

from auto_modules.features.poe2.live_terrain.experimental.follow_engine.generation import GenerationClock
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.process_supervisor import ProcessSupervisor, SupervisorState


class FakeWorker:
    def __init__(self, events):
        self.events = list(events)
        self.started = []
        self.stopped = 0

    def start(self, *, generation, map_instance):
        self.started.append((generation, map_instance))

    def poll_latest(self):
        return self.events.pop(0) if self.events else None

    def stop(self):
        self.stopped += 1


def test_supervisor_filters_late_generation_and_restarts_with_backoff():
    now = [0]
    workers = []

    def factory():
        worker = FakeWorker([
            SimpleNamespace(kind="error", generation=1, error="boom"),
        ] if not workers else [])
        workers.append(worker)
        return worker

    supervisor = ProcessSupervisor(factory, max_restarts=1, backoff_ms=(10,), clock_ms=lambda: now[0])
    token = GenerationClock().begin("map-a")
    supervisor.start(token)
    event = supervisor.poll(now_ms=0)
    assert event is not None and supervisor.status.state is SupervisorState.BACKOFF
    assert supervisor.status.restart_count == 1
    assert supervisor.poll(now_ms=5) is None
    supervisor.poll(now_ms=10)
    assert supervisor.status.state is SupervisorState.RUNNING
    assert len(workers) == 2

    # A late event from an old generation cannot change supervisor state.
    workers[-1].events.append(SimpleNamespace(kind="error", generation=999, error="late"))
    assert supervisor.poll(now_ms=11) is None
    assert supervisor.status.state is SupervisorState.RUNNING
    supervisor.stop()


def test_supervisor_enters_failed_after_restart_budget_and_stop_is_terminal():
    workers = []

    def factory():
        worker = FakeWorker([SimpleNamespace(kind="stopped", generation=1)])
        workers.append(worker)
        return worker

    supervisor = ProcessSupervisor(factory, max_restarts=1, backoff_ms=(0,))
    token = GenerationClock().begin("map-a")
    supervisor.start(token)
    supervisor.poll(now_ms=0)
    supervisor.poll(now_ms=0)
    assert supervisor.status.state is SupervisorState.FAILED
    supervisor.stop()
    assert supervisor.status.state is SupervisorState.STOPPED


def test_supervisor_clears_token_even_when_worker_stop_reports_error():
    class FailingWorker(FakeWorker):
        def stop(self):
            raise RuntimeError("worker stop failed")

    worker = FailingWorker([])
    supervisor = ProcessSupervisor(lambda: worker)
    token = GenerationClock().begin("map-a")
    supervisor.start(token)
    try:
        supervisor.stop()
    except RuntimeError as exc:
        assert str(exc) == "worker stop failed"
    assert supervisor.status.state is SupervisorState.STOPPED
    assert supervisor.status.generation is None


def test_supervisor_restarts_worker_that_exits_without_publishing_event():
    class DeadProcess:
        def is_alive(self):
            return False

    class SilentDeadWorker(FakeWorker):
        def __init__(self):
            super().__init__([])
            self.process = DeadProcess()

    workers = []

    def factory():
        worker = SilentDeadWorker()
        workers.append(worker)
        return worker

    supervisor = ProcessSupervisor(factory, max_restarts=0, backoff_ms=(0,))
    token = GenerationClock().begin("map-a")
    supervisor.start(token)
    assert supervisor.poll(now_ms=0) is None
    assert supervisor.status.state is SupervisorState.FAILED
    assert supervisor.status.last_error == "worker_exited_without_event"
    assert workers[0].stopped == 1
    supervisor.stop()
