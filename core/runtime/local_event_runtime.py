"""Local event listener; emits non-exclusive event state to the Xbox host."""
from __future__ import annotations
import ctypes, json, os, threading, time
from types import SimpleNamespace
from pathlib import Path
from core.events.action_tracks import ActionTrack, TrackMode
from core.runtime.event_session import EventSession
from core.runtime_paths import data_root
from core.events.event_store import EventStore
from core.events.event_catalog import catalog_summary
from core.events.gamepad_output import state_from_inputs
from core.actions.program_gamepad import host_clock_ms


def _data_only_peers(status: dict) -> list[dict]:
    """Return only live event/position sessions, never controller sessions."""
    return [
        peer for peer in status.get('peers', [])
        if peer.get('connected') and peer.get('syncing') and peer.get('dataOnly')
    ]

def _event_log(message: str) -> None:
    try:
        path = Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'AutoModules' / 'Workbench' / 'logs' / 'event-runtime.log'
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('a', encoding='utf-8') as stream:
            stream.write(f'{time.strftime("%Y-%m-%d %H:%M:%S")} {message}\n')
    except Exception:
        pass

class LocalEventRuntime:
    def __init__(self, *, root: Path | None = None, client_factory=None):
        base = Path(root) if root is not None else data_root(Path(__file__).resolve().parents[2]) / 'configs' / 'events'
        self.root = base if base.name == 'events' else base / 'configs' / 'events'
        self.client_factory = client_factory; self.stop_event = threading.Event(); self.thread = None
        self.error = ''; self.trigger_count = 0; self.last_event = ''
    def start(self):
        if self.thread and self.thread.is_alive(): return
        self.stop_event.clear(); self.error = ''; self.trigger_count = 0
        self.thread = threading.Thread(target=self._run, name='LocalEventRuntime', daemon=True); self.thread.start()
    def stop(self):
        self.stop_event.set()
        if self.thread: self.thread.join(timeout=1.0)
    def _load(self):
        events = json.loads((self.root / 'events.json').read_text(encoding='utf-8'))
        routes = json.loads((self.root / 'routes.json').read_text(encoding='utf-8'))
        definitions = {}
        for event in events if isinstance(events, list) else []:
            tracks = []
            for item in event.get('tracks', ()):
                mode = TrackMode(item.get('mode', 'once'))
                tracks.append(ActionTrack(tuple(item.get('buttons', ())), mode=mode, hold_ms=int(item.get('hold_ms', 100)), interval_ms=item.get('interval_ms') if mode is not TrackMode.ONCE else None, end_ms=item.get('end_ms') if mode is not TrackMode.ONCE else None))
            definitions[event.get('name', '')] = SimpleNamespace(
                tracks=tuple(tracks), steps=tuple(event.get('steps', ())),
                max_runs=event.get('max_runs'), loop=bool(event.get('loop', False)),
                end_ms=event.get('end_ms')
            )
        local = {}
        remote = {}
        for route in routes if isinstance(routes, list) else []:
            source = str(route.get('source', '')).strip().lower()
            if source in ('', 'local', '本机', '鏈満', 'b', 'b端', 'b绔?') and route.get('trigger') and route.get('event'):
                value = (route['event'], route.get('controller', 'Controller 1'), route.get('target', '本机'))
                local[str(route['trigger']).upper()] = value
                if str(route.get('target', '')).strip() not in ('', '本机', 'local', '鏈満'):
                    remote[str(route['trigger']).upper()] = value
        return definitions, local, remote

    @staticmethod
    def _catalog_payload(store: EventStore, device_id: str) -> dict:
        return {"deviceId": device_id, "events": catalog_summary(store.local(), device_id).get("events", []), "definitions": store.local(), "catalogRevision": catalog_summary(store.local(), device_id).get("catalogRevision", 0), "catalogHash": catalog_summary(store.local(), device_id).get("catalogHash", "")}
    def _run(self):
        client = None
        try:
            _event_log('listener starting')
            if os.name != 'nt': raise RuntimeError('Local event listener requires Windows')
            definitions, routes, remote_routes = self._load()
            if not routes: raise RuntimeError('No local event routes are configured')
            from virtual_gamepad.client.python import VirtualGamepadClient
            client = (self.client_factory or VirtualGamepadClient)(); client.connect(timeout=2)
            _event_log('host pipe connected')
            _event_log(
                f'event routes loaded local={sorted(routes)} '
                f'remote={sorted(remote_routes)}'
            )
            sessions = {1: EventSession(definitions, clock_ms=lambda: int(time.monotonic() * 1000)), 2: EventSession(definitions, clock_ms=lambda: int(time.monotonic() * 1000))}
            device_status = client.request('sync.status').get('status', {})
            store = EventStore(self.root, str(device_status.get('deviceId', 'local')))
            keys = set()
            previous_state = {1: (0, 0, 0), 2: (0, 0, 0)}
            while not self.stop_event.is_set():
                for key, (name, _, target) in routes.items():
                    if not key.startswith('F') or not key[1:].isdigit(): continue
                    pressed = bool(ctypes.windll.user32.GetAsyncKeyState(0x70 + int(key[1:]) - 1) & 0x8000)
                    selected = routes[key][1]
                    targets_for_route = (1, 2) if selected == 'Controller 1 + 2' else (2,) if selected == 'Controller 2' else (1,)
                    if pressed and key not in keys:
                        if key in remote_routes:
                            try:
                                status = client.request('sync.status').get('status', {})
                                peers = _data_only_peers(status)
                                if not peers:
                                    raise RuntimeError('no connected shared-event peer')
                                _event_log(
                                    'remote event route status '
                                    f"peers={[(p.get('deviceId'), p.get('connected'), p.get('syncing'), p.get('dataOnly')) for p in status.get('peers', [])]}"
                                )
                                targets = [str(n) for n in targets_for_route]
                                record = store.by_name(name)
                                for peer in peers:
                                    # Catalog and event share the same ordered
                                    # data session.  This removes the startup
                                    # race where the event arrives before the
                                    # receiver has its read-only definition.
                                    try:
                                        client.request('sync.share.catalog', {
                                            'deviceId': peer.get('deviceId'),
                                            'catalog': self._catalog_payload(
                                                store, str(status.get('deviceId', 'local'))
                                            ),
                                        })
                                        _event_log(f'event catalog ensured device={peer.get("deviceId")}')
                                    except Exception as exc:
                                        _event_log(f'event catalog ensure error device={peer.get("deviceId")} error={exc!r}')
                                    reply = client.request('sync.share.event', {
                                        'deviceId': peer.get('deviceId'), 'name': name,
                                        'eventId': (record or {}).get('id', ''),
                                        'eventRevision': int((record or {}).get('revision', 0)),
                                        'targets': targets,
                                        'deadlineMs': host_clock_ms() + 500,
                                    })
                                    _event_log(
                                        f'remote event sent key={key} event={name} '
                                        f'eventId={(record or {}).get("id", "")} '
                                        f'device={peer.get("deviceId")} targets={targets} reply={reply}'
                                    )
                                self.trigger_count += 1; self.last_event = name
                            except Exception as exc:
                                _event_log(f'remote event send error key={key} event={name} error={exc!r}')
                        started = False if key in remote_routes else any(sessions[target].start(name) for target in targets_for_route)
                        if started:
                            self.trigger_count += 1; self.last_event = name
                            _event_log(f'trigger key={key} event={name} targets={targets_for_route}')
                    if pressed: keys.add(key)
                    else: keys.discard(key)
                for target, session in sessions.items():
                    state = state_from_inputs(session.tick())
                    buttons = state['buttons']
                    reply = client.request('event.state', {'controller': target, 'source': 'event:local', 'state': state, 'ttlMs': 120})
                    current = (buttons, state['leftStickX'], state['leftStickY'])
                    if current != previous_state[target]:
                        _event_log(f'轨道状态 controller={target} buttons={buttons} axes={current[1]},{current[2]} previous={previous_state[target]} reply={reply}')
                        previous_state[target] = current
                    if any(current):
                        _event_log(f'event.state sent controller={target} buttons={buttons} axes={current[1]},{current[2]} reply={reply}')
                self.stop_event.wait(0.02)
        except Exception as exc:
            self.error = str(exc); _event_log(f'listener error={exc!r}')
        finally:
            if client:
                for target in (1, 2):
                    try: client.request('event.clear', {'controller': target, 'source': 'event:local'})
                    except Exception: pass
                try: client.close()
                except Exception: pass
