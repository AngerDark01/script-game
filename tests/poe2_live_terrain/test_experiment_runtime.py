from auto_modules.features.poe2.live_terrain.experimental.application import (
    ExperimentPhase,
    ExperimentRuntime,
)


def test_runtime_rejects_events_from_other_session():
    runtime = ExperimentRuntime()
    runtime.start("s1")
    assert runtime.accepts("s1") is True
    assert runtime.accepts("s2") is False


def test_runtime_stop_is_terminal_for_current_session():
    runtime = ExperimentRuntime()
    runtime.start("s1")
    runtime.stop()
    assert runtime.state.phase is ExperimentPhase.STOPPED
