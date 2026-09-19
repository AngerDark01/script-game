from auto_modules.core.localization.trajectory import TrajectoryBuffer


def test_only_fresh_confirmed_positions_extend_the_trail():
    trail = TrajectoryBuffer(max_length=3)
    trail.append((10, 10), captured_at_ms=1, confidence=0.9, fresh=True)
    trail.append((11, 10), captured_at_ms=2, confidence=0.8, fresh=True)
    trail.append((99, 99), captured_at_ms=3, confidence=0.1, fresh=False)
    assert trail.points == ((10.0, 10.0), (11.0, 10.0))


def test_reset_clears_all_history():
    trail = TrajectoryBuffer()
    trail.append((1, 2), captured_at_ms=1, confidence=1.0, fresh=True)
    trail.reset()
    assert trail.points == ()
