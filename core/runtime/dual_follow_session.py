"""Independent actor controllers composed with existing event definitions/hooks."""
from collections import deque
from uuid import uuid4
from core.events.models import EventTask, EventTick, EventActionType


class DualFollowSession:
    def __init__(self, controllers, outputs, *, event_registry, leader_device, leader_actor='B', clock_ms):
        if set(controllers) != set(outputs) or not controllers:
            raise ValueError('each actor needs its own controller/output')
        self.controllers, self.outputs, self.events = controllers, outputs, event_registry
        self.leader_device, self.leader_actor, self.clock = leader_device, leader_actor, clock_ms
        self.armed = {actor: False for actor in controllers}
        self.mode = {actor: 'paused' for actor in controllers}
        self.active = {}
        self.seen = deque(maxlen=256)
        self.last_tick = None
        self.errors = {}
        self.decisions = {}
        self._leader_session = None

    def start(self, actor, *, requested_at_ms=None):
        self.outputs[actor].start(**({'requested_at_ms':requested_at_ms} if requested_at_ms is not None else {}))
        self.controllers[actor].reset()
        self.armed[actor], self.mode[actor] = True, 'following'
        self.errors.pop(actor, None)

    def stop(self, actor):
        self.armed[actor], self.mode[actor] = False, 'paused'
        current = self.active.pop(actor, None)
        if current: current[1].reset()
        self.controllers[actor].reset()
        self.outputs[actor].stop()

    def close(self):
        for actor in self.controllers:
            try: self.stop(actor)
            except Exception as exc: self.errors[actor] = str(exc)

    def receive(self, event):
        if event.device_id != self.leader_device or self.clock() >= event.deadline_ms or event.event_id in self.seen:
            return False
        if event.session_id and event.session_id != self._leader_session:
            return False
        if len(event.targets) != len(set(event.targets)) or any(a not in self.controllers for a in event.targets):
            return False
        definition = self.events.get(event.name)
        if event.name not in ('follow.pause', 'follow.resume', 'follow.stop') and definition is None:
            return False
        self.seen.append(event.event_id)
        for actor in event.targets:
            if not self.armed[actor]: continue  # remote cannot arm a locally stopped actor
            try:
                if event.name == 'follow.stop':
                    self.stop(actor)
                elif event.name in ('follow.pause', 'follow.resume'):
                    current = self.active.pop(actor, None)
                    if current: current[1].reset()
                    self.outputs[actor].write((0.,0.))
                    self.controllers[actor].reset()
                    self.mode[actor] = 'paused' if event.name == 'follow.pause' else 'following'
                else:
                    current = self.active.get(actor)
                    if current and definition.priority <= current[0].priority: continue
                    if current: current[1].reset()
                    self.outputs[actor].write((0.,0.))
                    handler = definition.create_handler({})
                    task = EventTask(uuid4().hex, event.name, (0,0), self.clock(), self.clock(), metadata={'actor_id':actor})
                    handler.start(task)
                    self.active[actor] = (definition, handler, task, self._leader_session)
                    self.mode[actor] = 'event'
            except Exception as exc:
                self._fault(actor, exc)
        return True

    def _fault(self, actor, exc):
        self.errors[actor] = str(exc)
        try: self.stop(actor)
        except Exception: pass  # host TTL remains the independent last line of defence
        self.mode[actor] = 'error'

    def tick(self, local_positions, remote_positions):
        now = self.clock()
        elapsed = 20 if self.last_tick is None else max(0, now-self.last_tick)
        self.last_tick = now
        candidates = [p for p in remote_positions if p.device_id == self.leader_device and p.actor_id == self.leader_actor]
        leader = max(candidates, key=lambda p:p.captured_at_ms) if candidates else None
        self._leader_session = leader.session_id if leader else None
        for actor, controller in self.controllers.items():
            if not self.armed[actor]: continue
            try:
                if actor in self.active:
                    definition, handler, task, event_session = self.active[actor]
                    if (event_session != self._leader_session or not controller._fresh(local_positions.get(actor), now)
                            or not controller._fresh(leader, now)):
                        handler.reset()
                        self.active.pop(actor)
                        self.outputs[actor].write((0.,0.))
                        self.mode[actor] = 'paused'
                        self.errors[actor] = 'event_cancelled_position_or_connection_lost'
                        continue
                    task.metadata['conditions'] = {'localized': controller._fresh(local_positions.get(actor), now),
                                                    'leader_fresh': controller._fresh(leader, now)}
                    result = handler.update(EventTick(now), task)
                    if result.type in (EventActionType.COMPLETE, EventActionType.FAIL):
                        self.outputs[actor].write((0.,0.))
                        self.active.pop(actor)
                        controller.reset()
                        self.mode[actor] = 'following' if definition.resume and result.type == EventActionType.COMPLETE else 'paused'
                    else:
                        remaining=min(local_positions[actor].captured_at_ms, leader.captured_at_ms)+controller.ttl_ms-self.clock()
                        self.outputs[actor].write((0.,0.), buttons=result.metadata.get('buttons',0),
                            valid_for_ms=min(120, result.wait_ms or 1, remaining, definition.timeout_ms-(self.clock()-handler.started)))
                elif self.mode[actor] == 'following':
                    decision = controller.tick(local_positions.get(actor), leader, now_ms=now)
                    self.decisions[actor] = decision
                    # Planning may have blocked. Subtract its time before sending.
                    remaining = decision.valid_for_ms-(self.clock()-now)
                    self.outputs[actor].write(decision.vector if remaining > 0 else (0.,0.),
                        elapsed_ms=elapsed, valid_for_ms=remaining)
                else:
                    self.outputs[actor].write((0.,0.))
            except Exception as exc:
                self._fault(actor, exc)
