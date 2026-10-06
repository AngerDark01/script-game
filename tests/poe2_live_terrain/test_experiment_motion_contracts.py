from auto_modules.features.poe2.live_terrain.experimental.motion.decisions import MotionDecision


def test_motion_decision_is_data_only():
    decision = MotionDecision((0.5, -0.25), 120, "route_ready", target=(4, 5))
    assert decision.vector == (0.5, -0.25)
    assert decision.release_output is False
