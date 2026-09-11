"""Workbench-facing lifecycle; network I/O never runs on the GUI thread."""
import multiprocessing as mp
import threading
from queue import Queue, Empty, Full
from dataclasses import replace
from uuid import uuid4
import os
from core.runtime.follow_workers import vision_worker,actor_worker,put_latest,latest,clock_ms
from core.lan_follow.follow_transport import FollowTransport,SharedEvent


class FollowService:
    def __init__(self, config, *, client_factory=None):
        config.validate(for_start=True)
        self.config=config
        if client_factory is None:
            from virtual_gamepad.client.python import VirtualGamepadClient
            client_factory=VirtualGamepadClient
        self.client_factory=client_factory
        self.context=mp.get_context('spawn')
        self.stop_event=self.context.Event()
        self.frames=self.context.Queue(maxsize=1)
        self.statuses={'vision':self.context.Queue(maxsize=1)}
        self.inputs={}; self.commands={}; self.processes=[]
        self.outbound=Queue(maxsize=32)
        self.network_status={}; self.snapshot={}; self.client=None; self.thread=None
        self._keys=set()

    def start(self):
        if self.processes: raise RuntimeError('monitor already started')
        config=self.config
        recording_dir=None
        if config.record:
            from pathlib import Path
            from core.runtime_paths import data_root
            recording_dir=str(data_root(Path(__file__).resolve().parents[2])/'logs'/'follow'/uuid4().hex)
        self.recording_dir=recording_dir
        vision=self.context.Process(target=vision_worker,args=(config,self.stop_event,self.frames,self.statuses['vision'],recording_dir),name='FollowVision',daemon=True)
        self.processes.append(vision)
        if config.role=='A':
            for actor in config.actors:
                identity=actor['actor_id']
                self.inputs[identity]=self.context.Queue(maxsize=1)
                self.commands[identity]=self.context.Queue(maxsize=32)
                self.statuses[identity]=self.context.Queue(maxsize=1)
                self.processes.append(self.context.Process(target=actor_worker,args=(config,actor,self.stop_event,
                    self.inputs[identity],self.commands[identity],self.statuses[identity],recording_dir),name=f'Follow-{identity}',daemon=True))
        try:
            for process in self.processes: process.start()
            self.thread=threading.Thread(target=self._network,name='FollowNetwork',daemon=True)
            self.thread.start()
        except Exception:
            self.stop(); raise

    def command(self, actor, kind):
        if self.stop_event.is_set(): raise RuntimeError('monitor is stopped')
        from core.actions.program_gamepad import host_clock_ms
        try: self.commands[actor].put_nowait(dict(kind=kind,requested_at_ms=host_clock_ms()))
        except Full:
            self.stop_event.set()
            raise RuntimeError('control queue full; stopped for safety')

    def send_event(self, name):
        from core.actions.program_gamepad import host_clock_ms
        intent=(name,clock_ms()+250,host_clock_ms()+250)
        try: self.outbound.put_nowait(intent)
        except Full:
            self.stop_event.set()
            raise RuntimeError('event queue full; stopped for safety')

    def _hotkeys(self):
        if os.name!='nt': return
        import ctypes
        for key,name in self.config.shortcuts.items():
            pressed=bool(ctypes.windll.user32.GetAsyncKeyState(0x70+int(key[1:])-1)&0x8000)
            if pressed and key not in self._keys: self.send_event(name)
            if pressed: self._keys.add(key)
            else: self._keys.discard(key)

    def _network(self):
        local={}
        try:
            self.client=self.client_factory(); self.client.connect(timeout=2)
            transport=FollowTransport(self.client)
            status=self.client.request('sync.status').get('status',{})
            if status.get('mode')!='share':
                raise RuntimeError('请先在虚拟手柄 / 局域网页选择“位置与事件共享”模式并配对')
            while not self.stop_event.is_set():
                self._hotkeys()
                local=latest(self.frames,local)
                if self.config.role=='B':
                    for position in local.values(): transport.publish(position)
                remote,events=transport.poll()
                for actor,queue in self.inputs.items(): put_latest(queue,(local,remote))
                for event in events:
                    for actor in event.targets:
                        if actor in self.commands:
                            self.commands[actor].put_nowait(dict(kind='event',event=replace(event,targets=(actor,))))
                for _ in range(32):
                    try: name,deadline,host_deadline=self.outbound.get_nowait()
                    except Empty: break
                    if clock_ms() >= deadline: continue
                    if self.config.role=='B':
                        if not self.config.recipient_device: raise ValueError('请配置接收事件的A端设备')
                        transport.send_event(self.config.recipient_device,name,self.config.event_targets,host_deadline_ms=host_deadline)
                    else:
                        for actor,queue in self.commands.items():
                            queue.put_nowait(dict(kind='event',event=SharedEvent(self.config.leader_device,uuid4().hex,
                                name,(actor,),deadline)))
                self.network_status=dict(state='sharing',remote=[dict(actor=p.actor_id,position=p.position,age_ms=clock_ms()-p.captured_at_ms) for p in remote])
                self.stop_event.wait(.025)
        except Exception as exc:
            self.network_status=dict(error=str(exc))
            self.stop_event.set()
        finally:
            if self.client is not None: self.client.close()

    def status(self):
        for worker,queue in self.statuses.items():
            value=latest(queue)
            if value is not None: self.snapshot[worker]=value
        return dict(workers=dict(self.snapshot),network=dict(self.network_status),
            recording_dir=getattr(self,'recording_dir',None),
            running=not self.stop_event.is_set() and any(p.is_alive() for p in self.processes))

    def stop(self):
        self.stop_event.set()
        if self.client is not None: self.client.close()  # cancels blocked pipe reads
        if self.thread is not None: self.thread.join(timeout=.3)
        for process in self.processes:
            if process.pid is None: continue
            process.join(timeout=.25)
            if process.is_alive():
                process.terminate()
                process.join(timeout=.25)
        for queue in [self.frames,*self.inputs.values(),*self.commands.values(),*self.statuses.values()]:
            queue.cancel_join_thread(); queue.close()
