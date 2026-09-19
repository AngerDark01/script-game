"""Workbench-facing lifecycle; network I/O never runs on the GUI thread."""
import multiprocessing as mp
import threading
from queue import Queue, Empty, Full
from dataclasses import replace
from uuid import uuid4
import json
from auto_modules.paths import data_root
from auto_modules.features.torchlight.follow.workers import vision_worker,actor_worker,put_latest,latest,clock_ms
from auto_modules.adapters.host.follow_transport import FollowTransport
from auto_modules.adapters.virtual_gamepad import host_clock_ms
from auto_modules.adapters.windows.hotkeys import HotkeyTriggerSource
from auto_modules.core.communication import Capability, PeerId
from auto_modules.core.communication import SharedEvent


class FollowService:
    def __init__(self, config, *, client_factory=None, hotkey_source=None, communication_manager=None):
        config.validate(for_start=True)
        self.config=config
        if client_factory is None:
            from auto_modules.adapters.virtual_gamepad import VirtualGamepadClient
            client_factory=VirtualGamepadClient
        self.client_factory=client_factory
        self.communication_manager=communication_manager
        self.shared_transport=None
        self.context=mp.get_context('spawn')
        self.stop_event=self.context.Event()
        self.frames=self.context.Queue(maxsize=1)
        self.statuses={'vision':self.context.Queue(maxsize=1)}
        self.inputs={}; self.commands={}; self.processes=[]
        self.outbound=Queue(maxsize=32)
        self.network_status={}; self.snapshot={}; self.client=None; self.thread=None
        self.hotkey_source=hotkey_source or HotkeyTriggerSource()
        self._route_shortcuts={}
        self._route_controllers={}
        self._remote_events=set()
        try:
            route_path=data_root()/'events'/'routes.json'
            for route in json.loads(route_path.read_text(encoding='utf-8')):
                if route.get('source') in ('B端','B','本机','') and route.get('trigger') and route.get('event'):
                    self._route_shortcuts[route['trigger']]=route['event']
                    self._route_controllers[route['trigger']]=route.get('controller','Controller 1')
                elif route.get('event') and route.get('source'):
                    self._remote_events.add(route['event'])
        except (OSError, ValueError, TypeError):
            pass

    def start(self):
        if self.processes: raise RuntimeError('monitor already started')
        config=self.config
        recording_dir=None
        if config.record:
            recording_dir=str(data_root()/'logs'/'follow'/uuid4().hex)
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
        try: self.commands[actor].put_nowait(dict(kind=kind,requested_at_ms=host_clock_ms()))
        except Full:
            self.stop_event.set()
            raise RuntimeError('control queue full; stopped for safety')

    def _targets_for_controller(self, controller):
        targets=list(self.config.event_targets)
        if controller == 'Controller 1':
            selected=[a for a in targets if str(a).endswith('1')]
            return tuple(selected or targets[:1])
        if controller == 'Controller 2':
            selected=[a for a in targets if str(a).endswith('2')]
            return tuple(selected or targets[-1:])
        return tuple(targets)

    def send_event(self, name, *, controller=None):
        intent=(name,clock_ms()+250,host_clock_ms()+250,controller)
        try: self.outbound.put_nowait(intent)
        except Full:
            self.stop_event.set()
            raise RuntimeError('event queue full; stopped for safety')

    def _hotkeys(self):
        shortcuts=dict(self.config.shortcuts); shortcuts.update(self._route_shortcuts)
        for key in self.hotkey_source.poll(shortcuts):
            self.send_event(shortcuts[key], controller=self._route_controllers.get(key))

    def _network(self):
        if self.communication_manager is not None:
            self._network_shared()
            return
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
                    if self._remote_events and event.name not in self._remote_events:
                        continue
                    for actor in event.targets:
                        if actor in self.commands:
                            self.commands[actor].put_nowait(dict(kind='event',event=replace(event,targets=(actor,))))
                for _ in range(32):
                    try: name,deadline,host_deadline,controller=self.outbound.get_nowait()
                    except Empty: break
                    if clock_ms() >= deadline: continue
                    if self.config.role=='B':
                        if not self.config.recipient_device: raise ValueError('请配置接收事件的A端设备')
                        transport.send_event(self.config.recipient_device,name,
                            self._targets_for_controller(controller),host_deadline_ms=host_deadline)
                    else:
                        for actor in self._targets_for_controller(controller):
                            queue=self.commands.get(actor)
                            if queue is None: continue
                            queue.put_nowait(dict(kind='event',event=SharedEvent(self.config.leader_device,uuid4().hex,
                                name,(actor,),deadline)))
                self.network_status=dict(state='sharing',remote=[dict(actor=p.actor_id,position=p.position,age_ms=clock_ms()-p.captured_at_ms) for p in remote])
                self.stop_event.wait(.025)
        except Exception as exc:
            self.network_status=dict(error=str(exc))
            self.stop_event.set()
        finally:
            if self.client is not None: self.client.close()

    def _network_shared(self):
        """Run follow over the injected process-scoped communication manager."""
        local = {}
        manager = self.communication_manager
        if manager is None:
            raise RuntimeError("shared follow requires a communication manager")
        peer_id = str(self.config.recipient_device or self.config.leader_device or "").strip()
        leases = []
        try:
            if not peer_id:
                raise RuntimeError("shared follow requires a configured peer device")
            peer = PeerId(peer_id)
            leases.extend([
                manager.acquire(peer, Capability.POSITION_SUBSCRIBE),
                manager.acquire(peer, Capability.EVENT_SUBSCRIBE),
            ])
            if self.config.role == "B":
                leases.append(manager.acquire(peer, Capability.POSITION_PUBLISH))
            transport = FollowTransport(
                None,
                manager=manager,
                peer_id=peer_id,
            )
            self.shared_transport = transport
            while not self.stop_event.is_set():
                self._hotkeys()
                local = latest(self.frames, local)
                if self.config.role == "B":
                    for position in local.values():
                        transport.publish(position)
                remote, events = transport.poll()
                for actor, queue in self.inputs.items():
                    put_latest(queue, (local, remote))
                for event in events:
                    if self._remote_events and event.name not in self._remote_events:
                        continue
                    for actor in event.targets:
                        if actor in self.commands:
                            self.commands[actor].put_nowait(dict(kind="event", event=replace(event, targets=(actor,))))
                for _ in range(32):
                    try:
                        name, deadline, host_deadline, controller = self.outbound.get_nowait()
                    except Empty:
                        break
                    if clock_ms() >= deadline:
                        continue
                    if self.config.role == "B":
                        if not self.config.recipient_device:
                            raise ValueError("请配置接收事件的A端设备")
                        transport.send_event(
                            self.config.recipient_device,
                            name,
                            self._targets_for_controller(controller),
                            host_deadline_ms=host_deadline,
                        )
                    else:
                        for actor in self._targets_for_controller(controller):
                            queue = self.commands.get(actor)
                            if queue is not None:
                                queue.put_nowait(dict(kind="event", event=SharedEvent(peer_id, uuid4().hex, name, (actor,), deadline)))
                self.network_status = dict(
                    state="sharing",
                    remote=[dict(actor=p.actor_id, position=p.position, age_ms=clock_ms() - p.captured_at_ms) for p in remote],
                )
                self.stop_event.wait(0.025)
        except Exception as exc:
            self.network_status = dict(error=str(exc))
            self.stop_event.set()
        finally:
            if self.shared_transport is not None:
                self.shared_transport.close()
                self.shared_transport = None
            for lease in leases:
                lease.close()

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
        if self.shared_transport is not None: self.shared_transport.close()
        if self.thread is not None: self.thread.join(timeout=.3)
        for process in self.processes:
            if process.pid is None: continue
            process.join(timeout=.25)
            if process.is_alive():
                process.terminate()
                process.join(timeout=.25)
        for queue in [self.frames,*self.inputs.values(),*self.commands.values(),*self.statuses.values()]:
            queue.cancel_join_thread(); queue.close()
