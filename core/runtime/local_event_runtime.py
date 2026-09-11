"""Local keyboard-to-event runner, independent from follow/navigation."""
from __future__ import annotations

import ctypes
import json
import os
import threading
import time
from types import SimpleNamespace
from pathlib import Path

from core.events.action_tracks import ActionTrack, TrackMode
from core.events.follow_chain import BUTTONS
from core.runtime.event_session import EventSession
from core.runtime_paths import data_root


class LocalEventRuntime:
    """Runs local event routes without installing a keyboard hook or swallowing keys."""

    def __init__(self, *, root: Path | None = None, client_factory=None):
        base = Path(root) if root is not None else data_root(Path(__file__).resolve().parents[2]) / "configs" / "events"
        self.root = base if base.name == "events" else base / "configs" / "events"
        self.client_factory = client_factory
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.error = ""
        self.trigger_count = 0

    def start(self) -> None:
        if self.thread and self.thread.is_alive():
            return
        self.stop_event.clear()
        self.error = ""
        self.thread = threading.Thread(target=self._run, name="LocalEventRuntime", daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=1.0)

    def _load(self):
        events = json.loads((self.root / "events.json").read_text(encoding="utf-8"))
        routes = json.loads((self.root / "routes.json").read_text(encoding="utf-8"))
        definitions = {}
        for event in events if isinstance(events, list) else []:
            tracks = tuple(ActionTrack(tuple(item.get("buttons", ())), mode=TrackMode(item.get("mode", "once")),
                hold_ms=int(item.get("hold_ms", 100)), interval_ms=item.get("interval_ms"), end_ms=item.get("end_ms"))
                for item in event.get("tracks", ()))
            definitions[event.get("name", "")] = SimpleNamespace(tracks=tracks,
                max_runs=event.get("max_runs"), loop=bool(event.get("loop", False)), end_ms=event.get("end_ms"))
        local = {}
        for route in routes if isinstance(routes, list) else []:
            if route.get("source") in ("本机", "B", "B端", "") and route.get("trigger") and route.get("event"):
                local[route["trigger"].upper()] = (route["event"], route.get("controller", "Controller 1"))
        return definitions, local

    def _run(self):
        output = None
        try:
            if os.name != "nt":
                raise RuntimeError("本机事件运行器只支持 Windows 键盘输入")
            definitions, routes = self._load()
            if not routes:
                raise RuntimeError("没有找到来源为“本机”的事件路由")
            from virtual_gamepad.client.python import VirtualGamepadClient
            client = (self.client_factory or VirtualGamepadClient)()
            client.connect(timeout=2)
            controller = 1
            for _, selected in routes.values():
                if selected == "Controller 2": controller = 2; break
            from core.actions.program_gamepad import ProgramGamepadOutput
            output = ProgramGamepadOutput(client, controller=controller)
            output.start()
            session = EventSession(definitions, clock_ms=lambda: int(time.monotonic() * 1000))
            keys = set()
            while not self.stop_event.is_set():
                for key, (name, _) in routes.items():
                    if not key.startswith("F") or not key[1:].isdigit():
                        continue
                    vk = 0x70 + int(key[1:]) - 1
                    pressed = bool(ctypes.windll.user32.GetAsyncKeyState(vk) & 0x8000)
                    if pressed and key not in keys:
                        session.start(name)
                        self.trigger_count += 1
                    if pressed: keys.add(key)
                    else: keys.discard(key)
                buttons = 0
                for button in session.tick(): buttons |= BUTTONS.get(button, 0)
                output.write((0, 0), buttons=buttons, valid_for_ms=100)
                self.stop_event.wait(0.02)
        except Exception as exc:
            self.error = str(exc)
        finally:
            if output:
                try: output.stop()
                except Exception: pass
