import numpy as np
from core.runtime.dual_follow_session import DualFollowSession
from core.runtime.follower_controller import FollowerController
from core.events.registry import EventRegistry
from core.events.follow_chain import FollowChainDefinition
from core.lan_follow.follow_transport import SharedEvent,SharedPosition


class Output:
    def __init__(self): self.values = []; self.running=False
    def start(self): self.running=True
    def stop(self): self.running=False
    def write(self, vector, **kw): self.values.append((vector,kw))


def test_remote_events_require_local_arming_and_preempt_only_selected_actor():
    clock = [100]
    controllers = {a:FollowerController(np.zeros((60,60)),actor_id=a,map_id='m',map_version='v') for a in ('A1','A2')}
    outputs = {a:Output() for a in controllers}
    registry = EventRegistry()
    registry.register(FollowChainDefinition('return',[dict(op='button',button='A',ms=100)],priority=10))
    session = DualFollowSession(controllers,outputs,event_registry=registry,leader_device='B',clock_ms=lambda:clock[0])
    session.receive(SharedEvent('B','first','follow.resume',('A1',),200))
    assert not outputs['A1'].running
    session.start('A1'); session.start('A2')
    local={a:SharedPosition('local',a,'m','v',(10,10),.9,100) for a in controllers}
    leader=SharedPosition('B','B','m','v',(30,30),.9,100)
    session.tick(local,(leader,))
    assert session.receive(SharedEvent('B','second','return',('A1',),200))
    session.tick(local,(leader,))
    assert outputs['A1'].values[-1][1]['buttons'] == 0x1000
    assert session.mode['A2'] == 'following'
    clock[0] = 201
    session.tick(local,(leader,))
    assert session.mode['A1'] == 'paused'
    assert not session.receive(SharedEvent('B','third','follow.resume',('A1',),200))
    session.close()
    assert all(not o.running for o in outputs.values())
