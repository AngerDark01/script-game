from auto_modules.core.events.follow_chain import FollowChainDefinition
from auto_modules.core.events.models import EventTask, EventTick, EventActionType
from auto_modules.core.events.hooks.registry import EventHookRegistry
import pytest


def test_chain_button_wait_condition_hook_and_complete():
    hooks = EventHookRegistry()
    seen = []
    hooks.register('done', lambda c: seen.append(c.event_type))
    definition = FollowChainDefinition('return', [dict(op='button', button='A', ms=100),
        dict(op='wait', ms=50), dict(op='condition', name='ok', then=3, **{'else':4}),
        dict(op='emit',name='done')], hooks=hooks)
    h = definition.create_handler({})
    task = EventTask('t','return',(0,0),0,0,metadata={'conditions':{'ok':True}})
    h.start(task)
    assert h.update(EventTick(0),task).metadata['buttons'] == 0x1000
    assert h.update(EventTick(100),task).metadata['buttons'] == 0
    assert h.update(EventTick(150),task).type == EventActionType.COMPLETE
    assert seen == ['return']


def test_loop_is_bounded_and_cancel_clears_progress():
    h = FollowChainDefinition('loop',[dict(op='condition',name='missing',**{'else':0})]).create_handler({})
    task = EventTask('t','loop',(0,0),0,0)
    h.start(task)
    for stamp in range(20): result = h.update(EventTick(stamp),task)
    assert result.type == EventActionType.FAIL
    h.reset()
    assert h.executed == 0


def test_chain_definition_accepts_a_bounded_parallel_step():
    definition = FollowChainDefinition('combo', [{
        'op': 'parallel', 'ms': 1000,
        'tracks': [
            {'buttons': ['LS_RIGHT'], 'mode': 'continuous', 'delay_ms': 0},
            {'buttons': ['RB'], 'mode': 'once', 'delay_ms': 200, 'hold_ms': 100},
        ],
    }])
    assert definition.steps[0]['tracks'][1]['buttons'] == ('RB',)


def test_chain_definition_rejects_nested_parallel_step():
    with pytest.raises(ValueError):
        FollowChainDefinition('nested', [{
            'op': 'parallel', 'ms': 100,
            'tracks': [{'op': 'parallel', 'buttons': ['A'], 'mode': 'once'}],
        }])
