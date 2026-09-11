"""Standalone LAN event receiver; independent of localization/follow services."""
from __future__ import annotations
import json, threading, time
from pathlib import Path
from types import SimpleNamespace
from core.events.action_tracks import ActionTrack, TrackMode
from core.events.follow_chain import BUTTONS
from core.runtime.event_session import EventSession

class RemoteEventRuntime:
    def __init__(self, *, root: Path, client_factory=None):
        self.root=Path(root); self.client_factory=client_factory
        self.stop_event=threading.Event(); self.thread=None; self.error=''; self.last_event=''; self.receive_count=0

    def _definitions(self):
        data=json.loads((self.root/'events.json').read_text(encoding='utf-8'))
        out={}
        for event in data if isinstance(data,list) else []:
            tracks=[ActionTrack(tuple(t.get('buttons',())), mode=TrackMode(t.get('mode','once')), hold_ms=int(t.get('hold_ms',100)), interval_ms=t.get('interval_ms') if t.get('mode','once') != 'once' else None, end_ms=t.get('end_ms') if t.get('mode','once') != 'once' else None) for t in event.get('tracks',())]
            out[event.get('name','')]=SimpleNamespace(tracks=tuple(tracks), max_runs=event.get('max_runs'), loop=bool(event.get('loop',False)), end_ms=event.get('end_ms'))
        return out

    def start(self):
        if self.thread and self.thread.is_alive(): return
        self.stop_event.clear(); self.error=''; self.thread=threading.Thread(target=self._run, name='RemoteEventRuntime', daemon=True); self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.thread: self.thread.join(timeout=1)

    @staticmethod
    def _controllers(targets):
        result=[]
        for target in targets:
            text=str(target).lower()
            if '2' in text and 2 not in result: result.append(2)
            elif ('1' in text or not result) and 1 not in result: result.append(1)
        return tuple(result or (1,))

    def _run(self):
        client=None
        try:
            from virtual_gamepad.client.python import VirtualGamepadClient
            client=(self.client_factory or VirtualGamepadClient)(); client.connect(timeout=2)
            definitions=self._definitions(); sessions={1:EventSession(definitions),2:EventSession(definitions)}
            while not self.stop_event.is_set():
                reply=client.request('sync.share.drain')
                for item in reply.get('events',[]):
                    name=str(item.get('name',''))
                    for controller in self._controllers(item.get('targets',())):
                        sessions[controller].start(name)
                    self.receive_count+=1; self.last_event=name
                for controller,session in sessions.items():
                    buttons=0
                    for button in session.tick(): buttons |= BUTTONS.get(button,0)
                    client.request('event.state', {'controller':controller,'source':'event:remote','state':{'buttons':buttons,'leftTrigger':0,'rightTrigger':0,'leftStickX':0,'leftStickY':0,'rightStickX':0,'rightStickY':0},'ttlMs':120})
                self.stop_event.wait(.025)
        except Exception as exc: self.error=str(exc)
        finally:
            if client:
                for controller in (1,2):
                    try: client.request('event.clear', {'controller':controller,'source':'event:remote'})
                    except Exception: pass
                client.close()
