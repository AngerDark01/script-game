import pytest

from auto_modules.features.poe2.live_terrain.experimental.application import (
    ExperimentPhase,
    HeadlessExperiment,
)


def test_headless_experiment_replays_frames_without_qt():
    experiment = HeadlessExperiment(session_id="s1")
    experiment.start(started_at_ms=10)
    tick = experiment.ingest(20, {"markers": []})
    assert tick.tick_id == 1
    assert experiment.runtime.state.phase is ExperimentPhase.RUNNING
    experiment.recover("marker_loss")
    assert experiment.runtime.state.phase is ExperimentPhase.RECOVERING
    experiment.stop()
    assert experiment.runtime.state.phase is ExperimentPhase.STOPPED
    assert [event.kind for event in experiment.diagnostics.events] == [
        "started", "frame_ingested", "recovering", "stopped",
    ]


def test_headless_experiment_rejects_frames_before_start():
    with pytest.raises(RuntimeError):
        HeadlessExperiment().ingest(1, None)
