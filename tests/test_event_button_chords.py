import pytest

from auto_modules.core.events.follow_chain import FollowChainDefinition, button_mask
from auto_modules.core.events.models import EventTask, EventTick, EventActionType


def test_single_and_chord_use_existing_masks():
    assert button_mask({'button': 'A'}) == 0x1000
    assert button_mask({'buttons': ['A', 'RB']}) == 0x1200
    assert button_mask({'buttons': ['A', 'A']}) == 0x1000


@pytest.mark.parametrize('step', [
    {}, {'buttons': []}, {'buttons': 'A'}, {'buttons': ['LT']},
    {'buttons': [None]}, {'button': 'A', 'buttons': ['B']},
])
def test_invalid_or_ambiguous_chord_is_rejected(step):
    with pytest.raises(ValueError):
        button_mask(step)


def test_chord_releases_before_next_button_without_localization():
    definition = FollowChainDefinition('skill', [
        {'op': 'button', 'buttons': ['A', 'RB'], 'ms': 80},
        {'op': 'wait', 'ms': 20},
        {'op': 'button', 'button': 'X', 'ms': 60},
    ])
    handler = definition.create_handler({})
    task = EventTask('one', 'skill', (0, 0), 0, 0)
    handler.start(task)
    assert handler.update(EventTick(0), task).metadata['buttons'] == 0x1200
    assert handler.update(EventTick(79), task).metadata['buttons'] == 0x1200
    assert handler.update(EventTick(80), task).metadata['buttons'] == 0
    assert handler.update(EventTick(100), task).metadata['buttons'] == 0x4000
    assert handler.update(EventTick(160), task).type == EventActionType.COMPLETE


def test_running_chord_does_not_change_when_source_configuration_is_edited():
    buttons = ['A', 'RB']
    definition = FollowChainDefinition('skill', [
        {'op': 'button', 'buttons': buttons, 'ms': 80},
    ])
    buttons[:] = ['X']
    handler = definition.create_handler({})
    task = EventTask('one', 'skill', (0, 0), 0, 0)
    handler.start(task)
    assert handler.update(EventTick(0), task).metadata['buttons'] == 0x1200
