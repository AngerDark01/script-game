import pytest

from auto_modules.features.poe2.live_terrain.experimental.probes import (
    DualTargetProbe,
    FollowProbe,
    MoveProbe,
)


def test_move_probe_requires_arm_before_selecting_target():
    probe = MoveProbe()
    with pytest.raises(RuntimeError):
        probe.select((1, 2))
    probe.arm()
    assert probe.select((1, 2)).source == "click"


def test_dual_target_probe_uses_same_target_contract():
    probe = DualTargetProbe()
    probe.arm()
    assert probe.select((3, 4)).source == "shared_target"


def test_follow_probe_accepts_source_updates_without_a_second_motion_engine():
    probe = FollowProbe()
    target = probe.update_from_source((5, 6))
    assert probe.armed
    assert target.position == (5.0, 6.0)
    assert target.source == "follow_source"
    assert probe.update_from_source((7, 8)).position == (7.0, 8.0)
