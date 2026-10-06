from auto_modules.features.poe2.live_terrain.experimental.replay import ReplayFrame, ReplaySource


def test_replay_source_is_deterministic_and_read_only():
    source = ReplaySource([ReplayFrame(1, "a"), ReplayFrame(2, "b")])
    assert tuple(source)[1].payload == "b"
    assert len(source) == 2
