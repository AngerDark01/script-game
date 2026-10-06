from auto_modules.features.poe2.live_terrain.experimental.follow.target_sources import (
    MutableTargetSource,
    RoleTargetSource,
)


def test_click_target_source_keeps_latest_target():
    source = MutableTargetSource()
    assert source.latest() is None
    source.set((1, 2))
    assert source.latest() == (1.0, 2.0)


def test_role_target_source_replaces_target_without_runtime_policy():
    source = RoleTargetSource("p1")
    source.update((3, 4))
    source.update((5, 6))
    assert source.latest() == (5, 6)
