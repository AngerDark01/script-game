from auto_modules.features.poe2.live_terrain.experimental.composition import (
    build_experiment_composition,
)


def test_composition_assembles_independent_runtime_components():
    composition = build_experiment_composition()
    assert composition.runtime.state.session_id is None
    assert composition.motion.running is False
    assert composition.recovery.state.active is False
    assert composition.diagnostics.events == []
