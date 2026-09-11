import pytest

from core.events.action_tracks import ActionTrack, TrackMode
from core.events.event_lifecycle import EventLifecycle


def test_event_stops_at_first_limit_and_clears_tracks():
    event = EventLifecycle([ActionTrack(('A',), mode=TrackMode.CONTINUOUS, hold_ms=20, interval_ms=50)],
                           max_runs=2, end_ms=500)
    assert event.poll(0) == {'A'}
    assert event.poll(50) == {'A'}
    assert event.poll(100) == set()
    assert event.finished


def test_loop_requires_an_explicit_stop_limit():
    with pytest.raises(ValueError):
        EventLifecycle([], loop=True)


def test_ordered_steps_emit_one_button_at_a_time():
    event = EventLifecycle([], steps=(
        {'op': 'button', 'button': 'X', 'ms': 100},
        {'op': 'wait', 'ms': 500},
        {'op': 'button', 'button': 'Y', 'ms': 100},
        {'op': 'wait', 'ms': 500},
        {'op': 'button', 'button': 'RB', 'ms': 100},
    ))
    assert event.poll(0) == {'X'}
    assert event.poll(100) == set()
    assert event.poll(599) == set()
    assert event.poll(600) == {'Y'}
    assert event.poll(700) == set()
    assert event.poll(1200) == {'RB'}
    assert event.poll(1300) == set()
    assert event.finished
