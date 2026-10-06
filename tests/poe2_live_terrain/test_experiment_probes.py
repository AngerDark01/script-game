import pytest

from auto_modules.features.poe2.live_terrain.experimental.probes import DualTargetProbe, MoveProbe


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
