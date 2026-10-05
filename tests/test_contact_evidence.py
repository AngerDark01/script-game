from auto_modules.core.routing.contact_evidence import ContactMonitor, ContactState


def test_contact_monitor_requires_two_non_progress_samples():
    monitor = ContactMonitor(required_samples=2)
    first = monitor.observe((1.0, 0.0), (0.1, 0.0), elapsed_ms=100)
    second = monitor.observe((1.0, 0.0), (0.0, 0.0), elapsed_ms=100, local_obstacle_ahead=True)

    assert first.recovery_required is False
    assert second.recovery_required is True
    assert second.reason == "local_obstacle_no_progress"


def test_contact_monitor_clears_after_progress():
    monitor = ContactMonitor(required_samples=2)
    monitor.observe((1.0, 0.0), (0.0, 0.0), elapsed_ms=100)
    monitor.observe((1.0, 0.0), (0.0, 0.0), elapsed_ms=100)
    recovered = monitor.observe((1.0, 0.0), (2.0, 0.0), elapsed_ms=100)

    assert recovered.recovery_required is False
    assert recovered.consecutive_no_progress == 0


def test_contact_monitor_treats_large_orthogonal_motion_as_progress():
    """Delayed gamepad frames must not turn real movement into wall contact."""
    monitor = ContactMonitor(required_samples=2)
    first = monitor.observe((0.65, 0.04), (0.5, -8.8), elapsed_ms=160, local_obstacle_ahead=True)
    second = monitor.observe((0.65, 0.04), (0.4, -8.7), elapsed_ms=160, local_obstacle_ahead=True)

    assert first.no_progress is False
    assert second.no_progress is False
    assert second.recovery_required is False
    assert second.consecutive_no_progress == 0


def test_contact_monitor_can_use_a_conservative_recovery_window():
    monitor = ContactMonitor(required_samples=4)

    evidence = None
    for index in range(4):
        evidence = monitor.observe(
            (1.0, 0.0),
            (0.0, 0.0),
            elapsed_ms=50,
            local_obstacle_ahead=True,
        )
        if index < 3:
            assert evidence.recovery_required is False
    assert evidence is not None
    assert evidence.consecutive_no_progress == 4
    assert evidence.recovery_required is True


def test_contact_monitor_clears_stale_contact_after_escape_progress():
    monitor = ContactMonitor(required_samples=2)
    monitor.observe(
        (1.0, 0.0), (0.0, 0.0), elapsed_ms=100,
        blocking_obstacle_ahead=True,
    )
    contact = monitor.observe(
        (1.0, 0.0), (0.0, 0.0), elapsed_ms=100,
        blocking_obstacle_ahead=True,
    )
    assert contact.recovery_required is True

    escaped = monitor.observe(
        (1.0, 0.0), (0.0, 1.5), elapsed_ms=100,
        blocking_obstacle_ahead=True,
        escape_available=True,
    )

    assert escaped.recovery_required is False
    assert escaped.consecutive_no_progress == 0
    assert escaped.state is ContactState.ESCAPED


def test_contact_monitor_keeps_recovery_evidence_but_marks_exit_available():
    monitor = ContactMonitor(required_samples=2)
    for _ in range(4):
        evidence = monitor.observe(
            (1.0, 0.0), (0.0, 0.0), elapsed_ms=100,
            blocking_obstacle_ahead=True,
            escape_available=True,
        )

    assert evidence.recovery_required is True
    assert evidence.consecutive_no_progress == 4
    assert evidence.state is ContactState.RECOVERY
    assert evidence.escape_available is True
