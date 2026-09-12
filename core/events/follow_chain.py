"""Bounded, tick-driven action chains using existing EventHandler/Registry/hooks.

Remote peers send only a configured event name. They never send executable code
or a chain definition. Button output is declarative metadata for the existing
program output adapter; no device is accessed by this module.
"""
from copy import deepcopy

from core.events.base.handler import EventHandler
from core.events.base.definition import EventDefinition
from core.events.models import EventAction
from core.events.hooks.models import EventHookContext
from core.events.gamepad_output import BUTTON_MASKS, EVENT_INPUTS
from core.events.event_lifecycle import parallel_inputs_at, validate_parallel_step

BUTTONS = BUTTON_MASKS


def button_mask(step):
    """Translate legacy single buttons or chords using the shared Xbox table."""
    if 'button' in step and 'buttons' in step:
        raise ValueError('choose button or buttons, not both')
    names = step.get('buttons') if 'buttons' in step else [step.get('button')]
    if not isinstance(names, (list, tuple)) or not 1 <= len(names) <= 16:
        raise ValueError('one to sixteen Xbox buttons required')
    mask = 0
    for name in names:
        if not isinstance(name, str) or name not in EVENT_INPUTS:
            raise ValueError('unknown Xbox input')
        mask |= BUTTONS.get(name, 0)
    return mask


def inputs_mask(inputs):
    mask = 0
    for name in inputs:
        mask |= BUTTONS.get(name, 0)
    return mask


class FollowChainDefinition(EventDefinition):
    def __init__(self, name, steps, *, hooks=None, timeout_ms=30000, priority=0, resume=False):
        self.event_type, self.display_name = name, name
        if not name or len(steps) > 128 or not 1 <= timeout_ms <= 60000:
            raise ValueError('invalid chain bounds')
        self.steps = tuple(deepcopy(s) for s in steps)
        self.hooks, self.timeout_ms, self.priority, self.resume = hooks, timeout_ms, priority, resume
        for index, step in enumerate(self.steps):
            op = step.get('op')
            if op not in ('wait', 'button', 'parallel', 'condition', 'retry', 'emit'):
                raise ValueError(f'unknown chain operation: {op}')
            if op in ('wait', 'button') and not 0 <= int(step.get('ms', 100)) <= 5000:
                raise ValueError('step duration must be 0..5000ms')
            if op == 'button':
                button_mask(step)
                if 'buttons' in step:
                    step['buttons'] = tuple(step['buttons'])
            if op == 'parallel':
                validate_parallel_step(step)
                for track in step['tracks']:
                    track['buttons'] = tuple(track['buttons'])
            if op == 'retry' and not 1 <= int(step.get('count', 1)) <= 10:
                raise ValueError('retry count must be 1..10')
            for key in ('then', 'else', 'target'):
                if key in step and not 0 <= int(step[key]) <= len(self.steps):
                    raise ValueError('step branch outside chain')
            if op == 'condition' and not step.get('name'):
                raise ValueError('condition name required')
            if op == 'emit' and not step.get('name'):
                raise ValueError('hook name required')

    def default_config(self): return {'enabled': True}
    def config_schema(self): return {}
    def create_detector(self, config): return None
    def create_handler(self, config): return FollowChainHandler(self)


class FollowChainHandler(EventHandler):
    def __init__(self, definition):
        self.definition = definition
        self.reset()

    def reset(self):
        super().reset()
        self.index, self.started, self.step_started = 0, None, None
        self.retries = {}
        self.executed = 0

    def start(self, task):
        self.reset()
        super().start(task)

    def update(self, tick, task):
        now = tick.now_ms
        if self.started is None: self.started = now
        if now < self.started or now-self.started >= self.definition.timeout_ms:
            return EventAction.fail('chain_timeout')
        # Bound even condition-only cycles; never busy-loop the control worker.
        for _ in range(32):
            if self.index >= len(self.definition.steps): return EventAction.complete('chain_completed')
            if self.executed >= 512: return EventAction.fail('chain_instruction_limit')
            step = self.definition.steps[self.index]
            op = step['op']
            if self.step_started is None: self.step_started = now
            duration = int(step.get('ms', 100))
            if op in ('wait', 'button', 'parallel') and now-self.step_started < duration:
                inputs = parallel_inputs_at(step, now-self.step_started) if op == 'parallel' else ()
                return EventAction.wait(duration-(now-self.step_started), metadata={
                    'buttons': button_mask(step) if op == 'button' else inputs_mask(inputs),
                    'inputs': tuple(sorted(inputs)),
                })
            next_index = self.index+1
            if op == 'condition':
                condition = bool(task.metadata.get('conditions', {}).get(step['name'], False))
                next_index = int(step.get('then' if condition else 'else', next_index))
            elif op == 'retry':
                count = self.retries.get(self.index, 0)
                if count < int(step.get('count', 1)):
                    self.retries[self.index] = count+1
                    next_index = int(step.get('target', 0))
            elif op == 'emit' and self.definition.hooks is not None:
                self.definition.hooks.emit(EventHookContext(step['name'], now, event_task_id=task.id,
                    event_type=self.definition.event_type, metadata={'actor_id': task.metadata.get('actor_id')}))
            self.index, self.step_started = next_index, None
            self.executed += 1
        return EventAction.wait(1, metadata={'buttons': 0})
