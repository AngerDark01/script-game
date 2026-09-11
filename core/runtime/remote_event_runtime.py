"""Standalone LAN event receiver; independent of localization/follow services."""
from __future__ import annotations
import json, threading, time
import os
from pathlib import Path
from types import SimpleNamespace
from core.events.action_tracks import ActionTrack, TrackMode
from core.events.follow_chain import BUTTONS
from core.runtime.event_session import EventSession
from core.events.event_store import EventStore
from core.events.event_catalog import catalog_summary

def _event_log(message: str) -> None:
    try:
        path = Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'AutoModules' / 'Workbench' / 'logs' / 'event-runtime.log'
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('a', encoding='utf-8') as stream:
            stream.write(f'{time.strftime("%Y-%m-%d %H:%M:%S")} {message}\n')
    except Exception:
        pass

class RemoteEventRuntime:
    def __init__(self, *, root: Path, client_factory=None):
        self.root=Path(root); self.client_factory=client_factory
        self.stop_event=threading.Event(); self.thread=None; self.error=''; self.last_event=''; self.receive_count=0

    def _definitions(self, store=None):
        if store is not None:
            data = store.all_visible()
        else:
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

    @staticmethod
    def _resolve_event_name(store, item):
        """Resolve a shared event without losing compatibility with old IDs."""
        name = str(item.get('name', ''))
        event_id = str(item.get('eventId') or '')
        if not event_id:
            return name
        record = store.by_id(event_id)
        if record is not None:
            return str(record.get('name') or name)

        # Older senders could generate a fresh UUID for legacy events on each
        # read.  A paired receiver may still safely use the name when its
        # catalog has the same-or-newer revision.
        fallback = store.by_name(name)
        sent_revision = int(item.get('eventRevision') or 0)
        if fallback is not None and int(fallback.get('revision', 0)) >= sent_revision:
            _event_log(
                f'remote event id fallback id={event_id} name={name} '
                f'revision={fallback.get("revision", 0)}'
            )
            return str(fallback.get('name') or name)
        reason = 'catalog_pending' if fallback is not None else 'event_not_found'
        _event_log(f'remote event rejected id={event_id} reason={reason}')
        return None

    def _run(self):
        client=None
        try:
            _event_log('remote listener starting')
            from virtual_gamepad.client.python import VirtualGamepadClient
            client=(self.client_factory or VirtualGamepadClient)(); client.connect(timeout=2)
            _event_log('remote listener host pipe connected')
            status = client.request('sync.status').get('status', {})
            _event_log(
                'remote listener sync status '
                f"mode={status.get('mode')} receiveEvents={status.get('receiveEvents')} "
                f"peers={[(p.get('deviceId'), p.get('connected'), p.get('syncing'), p.get('dataOnly')) for p in status.get('peers', [])]}"
            )
            store = EventStore(self.root, str(status.get('deviceId', 'local')))
            definitions=self._definitions(store); sessions={1:EventSession(definitions, clock_ms=lambda: int(time.monotonic() * 1000)),2:EventSession(definitions, clock_ms=lambda: int(time.monotonic() * 1000))}
            last_catalog = 0.0
            while not self.stop_event.is_set():
                if time.monotonic() - last_catalog >= 2.0:
                    status = client.request('sync.status').get('status', {})
                    summary = catalog_summary(store.local(), str(status.get('deviceId', 'local')))
                    catalog = {**summary, 'definitions': store.local()}
                    for peer in status.get('peers', []):
                        if peer.get('connected') and peer.get('syncing') and peer.get('dataOnly'):
                            try:
                                client.request('sync.share.catalog', {'deviceId': peer.get('deviceId'), 'catalog': catalog})
                            except Exception as exc:
                                _event_log(f'event catalog send error device={peer.get("deviceId")} error={exc!r}')
                    last_catalog = time.monotonic()
                reply=client.request('sync.share.drain')
                if reply.get('events') or reply.get('catalogs'):
                    _event_log(
                        f"remote drain events={len(reply.get('events', []))} "
                        f"catalogs={len(reply.get('catalogs', []))}"
                    )
                for catalog in reply.get('catalogs', []):
                    definitions_list = catalog.get('definitions', []) if isinstance(catalog, dict) else []
                    if definitions_list:
                        changed = store.apply_remote(definitions_list)
                        if changed:
                            definitions.clear(); definitions.update(self._definitions(store))
                            _event_log(f'event catalog applied owner={catalog.get("deviceId")} changed={changed}')
                for item in reply.get('events',[]):
                    name = self._resolve_event_name(store, item)
                    if name is None:
                        continue
                    for controller in self._controllers(item.get('targets',())):
                        if not sessions[controller].start(name):
                            _event_log(
                                f'remote event rejected name={name} '
                                f'controller={controller} reason=definition_not_found'
                            )
                            continue
                        _event_log(f'remote event session started name={name} controller={controller}')
                    self.receive_count+=1; self.last_event=name
                    _event_log(
                        f'remote event received name={name} id={item.get("eventId", "")} '
                        f'targets={item.get("targets", ())}'
                    )
                for controller,session in sessions.items():
                    buttons=0
                    for button in session.tick(): buttons |= BUTTONS.get(button,0)
                    state_reply = client.request('event.state', {'controller':controller,'source':'event:remote','state':{'buttons':buttons,'leftTrigger':0,'rightTrigger':0,'leftStickX':0,'leftStickY':0,'rightStickX':0,'rightStickY':0},'ttlMs':120})
                    if buttons:
                        _event_log(f'remote event.state sent controller={controller} buttons={buttons} reply={state_reply}')
                self.stop_event.wait(.025)
        except Exception as exc:
            self.error=str(exc); _event_log(f'remote listener error={exc!r}')
        finally:
            if client:
                for controller in (1,2):
                    try: client.request('event.clear', {'controller':controller,'source':'event:remote'})
                    except Exception: pass
                client.close()
