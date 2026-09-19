"""Spawn real planning processes; the output recorder never accesses a device."""
import multiprocessing as mp
from functools import partial
from queue import Empty
import time
import numpy as np
from auto_modules.features.torchlight.follow.config import FollowConfig
from auto_modules.features.torchlight.follow.resources import load_follow_maps
from auto_modules.features.torchlight.follow.workers import actor_worker,clock_ms,put_latest,latest
from auto_modules.adapters.virtual_gamepad import host_clock_ms
from auto_modules.core.communication import SharedPosition


class RecordingClient:
    def __init__(self,records): self.records=records
    def connect(self,**kw):pass
    def close(self):pass
    def request(self,name,payload):
        self.records.put((name,payload))
        return {'token':'offline-test'}


def test_two_spawned_actors_plan_and_output_independently_without_driver(tmp_path):
    source=tmp_path/'map_data.npz'; np.savez(source,wall_layer=np.zeros((100,100),np.uint8))
    config=FollowConfig(map_path=str(source),map_id='map',leader_device='B',clearance=0)
    reference,_=load_follow_maps(config)
    ctx=mp.get_context('spawn'); stop=ctx.Event(); records=ctx.Queue(); processes=[]; inputs={}; commands={}; statuses={}
    try:
        for actor in config.actors:
            identity=actor['actor_id']; inputs[identity]=ctx.Queue(maxsize=1); commands[identity]=ctx.Queue(maxsize=32); statuses[identity]=ctx.Queue(maxsize=1)
            p=ctx.Process(target=actor_worker,args=(config,actor,stop,inputs[identity],commands[identity],statuses[identity],None,partial(RecordingClient,records)))
            p.start(); processes.append(p)
        ready=set(); deadline=time.monotonic()+8
        while time.monotonic()<deadline and len(ready)<2:
            for actor,queue in statuses.items():
                status=latest(queue)
                if status is not None:
                    assert not status.get('error'),status
                    ready.add(actor)
            time.sleep(.02)
        assert len(ready)==2
        for queue in commands.values(): queue.put(dict(kind='start',requested_at_ms=host_clock_ms()))
        outputs={}; deadline=time.monotonic()+3
        while time.monotonic()<deadline and len(outputs)<2:
            stamp=clock_ms()
            def pos(actor,xy,device='local'):
                return SharedPosition(device,actor,'map',reference.map_version,xy,.9,stamp,'session')
            local={'A1':pos('A1',(10,40)),'A2':pos('A2',(70,80))}
            leader=pos('B',(70,40),'B')
            for queue in inputs.values():put_latest(queue,(local,(leader,)))
            while True:
                try:name,payload=records.get_nowait()
                except Empty:break
                if name=='program.state' and (payload['state']['leftStickX'] or payload['state']['leftStickY']):
                    outputs[payload['controller']]=payload['state']
            time.sleep(.02)
        assert outputs[1]['leftStickX']>0
        assert outputs[2]['leftStickY']>0
    finally:
        stop.set()
        for p in processes:
            p.join(timeout=2)
            if p.is_alive():p.terminate();p.join(timeout=1)
        for q in [records,*inputs.values(),*commands.values(),*statuses.values()]:q.cancel_join_thread();q.close()
