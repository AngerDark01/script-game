from auto_modules.features.poe2.live_terrain.experimental.replay import (
    ReplayFrame, ReplayManifest, ReplaySource,
)


def test_replay_source_is_deterministic_and_read_only():
    source = ReplaySource(
        [ReplayFrame(1, "a"), ReplayFrame(2, "b")],
        manifest=ReplayManifest("r1", scenario="visual_loss", tags=("recovery",)),
    )
    assert tuple(source)[1].payload == "b"
    assert len(source) == 2
    assert source.at(0).captured_at_ms == 1
    assert source.manifest.as_dict()["scenario"] == "visual_loss"
