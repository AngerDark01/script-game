import pytest

from auto_modules.core.events.action_tracks import ActionTrack, TrackMode
from auto_modules.core.events.event_lifecycle import EventLifecycle, validate_parallel_step


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


def test_parallel_step_merges_movement_delayed_button_and_frequency_input():
    event = EventLifecycle([], steps=(
        {
            'op': 'parallel',
            'ms': 1000,
            'tracks': [
                {'buttons': ['LS_RIGHT'], 'mode': 'continuous', 'delay_ms': 0},
                {'buttons': ['RB'], 'mode': 'once', 'delay_ms': 200, 'hold_ms': 100},
                {'buttons': ['X'], 'mode': 'frequency', 'delay_ms': 100,
                 'hold_ms': 50, 'interval_ms': 250, 'end_ms': 800},
            ],
        },
        {'op': 'button', 'button': 'Y', 'ms': 100},
    ))

    assert event.poll(0) == {'LS_RIGHT'}
    assert event.poll(100) == {'LS_RIGHT', 'X'}
    assert event.poll(200) == {'LS_RIGHT', 'RB'}
    assert event.poll(350) == {'LS_RIGHT', 'X'}
    assert event.poll(800) == {'LS_RIGHT'}
    assert event.poll(999) == {'LS_RIGHT'}
    assert event.poll(1000) == {'Y'}
    assert event.poll(1100) == set()
    assert event.finished


def test_parallel_step_restarts_with_ordered_sequence_loop():
    event = EventLifecycle([], max_runs=2, steps=(
        {'op': 'parallel', 'ms': 100, 'tracks': [
            {'buttons': ['A'], 'mode': 'once', 'delay_ms': 20, 'hold_ms': 20},
        ]},
    ))

    assert event.poll(0) == set()
    assert event.poll(20) == {'A'}
    assert event.poll(100) == set()
    assert event.poll(120) == {'A'}
    assert event.poll(200) == set()
    assert event.finished


@pytest.mark.parametrize('step', [
    {'op': 'parallel', 'ms': 100, 'tracks': []},
    {'op': 'parallel', 'ms': 100, 'tracks': [
        {'buttons': ['A'], 'mode': 'parallel'},
    ]},
    {'op': 'parallel', 'ms': 100, 'tracks': [
        {'op': 'parallel', 'buttons': ['A'], 'mode': 'once'},
    ]},
    {'op': 'parallel', 'ms': 100, 'tracks': [
        {'buttons': ['NOT_A_BUTTON'], 'mode': 'once'},
    ]},
])
def test_parallel_step_rejects_invalid_or_nested_tracks(step):
    with pytest.raises(ValueError):
        validate_parallel_step(step)
