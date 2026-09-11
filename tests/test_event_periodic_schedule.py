import pytest

from core.events.periodic_schedule import PeriodicSchedule


def test_fixed_cadence_skips_missed_ticks_and_busy_cycles():
    schedule = PeriodicSchedule(500, first_due_ms=0)
    assert schedule.poll(0)
    assert not schedule.poll(499)
    assert not schedule.poll(500, busy=True)
    assert not schedule.poll(501)
    assert schedule.poll(1600)
    assert schedule.next_due_ms == 2000
    assert not schedule.poll(1600)
    assert schedule.poll(2000)


def test_delayed_first_run_and_backwards_clock():
    schedule = PeriodicSchedule(100, first_due_ms=100)
    assert not schedule.poll(99)
    assert schedule.poll(100)
    with pytest.raises(ValueError):
        schedule.poll(99)


@pytest.mark.parametrize('interval', [0, -1, 1.5, True])
def test_rejects_invalid_interval(interval):
    with pytest.raises(ValueError):
        PeriodicSchedule(interval, first_due_ms=0)


@pytest.mark.parametrize('stamp', [-1, 0.5, True, float('nan')])
def test_rejects_invalid_timestamps_without_advancing_schedule(stamp):
    with pytest.raises(ValueError):
        PeriodicSchedule(100, first_due_ms=stamp)
    schedule = PeriodicSchedule(100, first_due_ms=0)
    with pytest.raises(ValueError):
        schedule.poll(stamp)
    assert schedule.poll(0)
