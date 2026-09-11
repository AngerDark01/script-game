"""Local event listener; emits non-exclusive event state to the Xbox host."""
from __future__ import annotations
import ctypes, json, os, threading, time
from types import SimpleNamespace
from pathlib import Path
from core.events.action_tracks import ActionTrack, TrackMode
from core.events.follow_chain import BUTTONS
from core.runtime.event_session import EventSession
from core.runtime_paths import data_root

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
            definitions[event.get('name', '')] = SimpleNamespace(tracks=tuple(tracks), max_runs=event.get('max_runs'), loop=bool(event.get('loop', False)), end_ms=event.get('end_ms'))
        local = {}
        for route in routes if isinstance(routes, list) else []:
            source = str(route.get('source', '')).strip().lower()
            if source in ('', 'local', '本机', '鏈満', 'b', 'b端', 'b绔?') and route.get('trigger') and route.get('event'):
                local[str(route['trigger']).upper()] = (route['event'], route.get('controller', 'Controller 1'))
        return definitions, local
    def _run(self):
        client = None
        try:
            if os.name != 'nt': raise RuntimeError('Local event listener requires Windows')
            definitions, routes = self._load()
            if not routes: raise RuntimeError('No local event routes are configured')
            from virtual_gamepad.client.python import VirtualGamepadClient
            client = (self.client_factory or VirtualGamepadClient)(); client.connect(timeout=2)
            sessions = {1: EventSession(definitions, clock_ms=lambda: int(time.monotonic() * 1000)), 2: EventSession(definitions, clock_ms=lambda: int(time.monotonic() * 1000))}
            keys = set()
            while not self.stop_event.is_set():
                for key, (name, _) in routes.items():
                    if not key.startswith('F') or not key[1:].isdigit(): continue
                    pressed = bool(ctypes.windll.user32.GetAsyncKeyState(0x70 + int(key[1:]) - 1) & 0x8000)
                    selected = routes[key][1]
                    targets_for_route = (1, 2) if selected == 'Controller 1 + 2' else (2,) if selected == 'Controller 2' else (1,)
                    if pressed and key not in keys:
                        started = any(sessions[target].start(name) for target in targets_for_route)
                        if started: self.trigger_count += 1; self.last_event = name
                    if pressed: keys.add(key)
                    else: keys.discard(key)
                for target, session in sessions.items():
                    buttons = 0
                    for button in session.tick(): buttons |= BUTTONS.get(button, 0)
                    state = dict(buttons=buttons, leftTrigger=0, rightTrigger=0, leftStickX=0, leftStickY=0, rightStickX=0, rightStickY=0)
                    client.request('event.state', {'controller': target, 'source': 'event:local', 'state': state, 'ttlMs': 120})
                self.stop_event.wait(0.02)
        except Exception as exc: self.error = str(exc)
        finally:
            if client:
                for target in (1, 2):
                    try: client.request('event.clear', {'controller': target, 'source': 'event:local'})
                    except Exception: pass
                try: client.close()
                except Exception: pass
