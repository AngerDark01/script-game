"""Local execution of authorized timed events, independent of localization."""

from core.events.event_lifecycle import EventLifecycle


class EventSession:
    def __init__(self, definitions, *, clock_ms):
        self.definitions = definitions
        self.clock = clock_ms
        self.active = {}
        self.last_buttons = set()

    def start(self, name, *, instance_id=None):
        definition = self.definitions.get(name)
        if definition is None:
            return False
        key = instance_id or name
        self.active[key] = (name, self.clock(), EventLifecycle(
            definition.tracks,
            max_runs=definition.max_runs,
            loop=definition.loop,
            end_ms=definition.end_ms,
            steps=getattr(definition, 'steps', ()),
        ))
        return True

    def stop(self, instance_id):
        return self.active.pop(instance_id, None) is not None

    def tick(self):
        now = self.clock()
        merged = set()
        finished = []
        for key, (_, started, lifecycle) in self.active.items():
            buttons = lifecycle.poll(now - started)
            merged.update(buttons)
            if lifecycle.finished:
                finished.append(key)
        for key in finished:
            self.active.pop(key, None)
        self.last_buttons = merged
        return frozenset(merged)

    def receive_remote(self, event):
        """Start/stop an already-authorized event from SharedEvent-like data."""
        if event.name.startswith('stop:'):
            return self.stop(event.name[5:])
        if event.deadline_ms <= self.clock():
            return False
        return self.start(event.name, instance_id=event.event_id)
