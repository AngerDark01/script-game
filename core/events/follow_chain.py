"""Bounded, tick-driven action chains using existing EventHandler/Registry/hooks.

Remote peers send only a configured event name. They never send executable code
or a chain definition. Button output is declarative metadata for the existing
program output adapter; no device is accessed by this module.
"""
from core.events.base.handler import EventHandler
from core.events.base.definition import EventDefinition
from core.events.models import EventAction
from core.events.hooks.models import EventHookContext

BUTTONS = {'A': 0x1000, 'B': 0x2000, 'X': 0x4000, 'Y': 0x8000,
    'LB': 0x100, 'RB': 0x200, 'BACK': 0x20, 'START': 0x10,
    'LS': 0x40, 'RS': 0x80, 'UP': 1, 'DOWN': 2, 'LEFT': 4, 'RIGHT': 8}


class FollowChainDefinition(EventDefinition):
    def __init__(self, name, steps, *, hooks=None, timeout_ms=30000, priority=0, resume=False):
        self.event_type, self.display_name = name, name
        if not name or len(steps) > 128 or not 1 <= timeout_ms <= 60000:
            raise ValueError('invalid chain bounds')
        self.steps = tuple(dict(s) for s in steps)
        self.hooks, self.timeout_ms, self.priority, self.resume = hooks, timeout_ms, priority, resume
        for index, step in enumerate(self.steps):
            op = step.get('op')
            if op not in ('wait', 'button', 'condition', 'retry', 'emit'):
                raise ValueError(f'unknown chain operation: {op}')
            if op in ('wait', 'button') and not 0 <= int(step.get('ms', 100)) <= 5000:
                raise ValueError('step duration must be 0..5000ms')
            if op == 'button' and step.get('button') not in BUTTONS:
                raise ValueError('unknown Xbox button')
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
            if op in ('wait', 'button') and now-self.step_started < duration:
                return EventAction.wait(duration-(now-self.step_started), metadata={
                    'buttons': BUTTONS[step['button']] if op == 'button' else 0})
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
