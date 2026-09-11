"""No sockets here: reuse the existing host's authenticated share sessions.

All deadlines are translated conservatively to the caller's local clock before
blocking IPC, never by comparing B's monotonic timestamp with A's clock.
"""
from dataclasses import dataclass
from math import isfinite
from typing import Callable
import time


@dataclass(frozen=True)
class SharedPosition:
    device_id: str
    actor_id: str
    map_id: str
    map_version: str
    position: tuple[float, float]
    confidence: float
    captured_at_ms: int
    session_id: str = ""


@dataclass(frozen=True)
class SharedEvent:
    device_id: str
    event_id: str
    name: str
    targets: tuple[str, ...]
    deadline_ms: int
    session_id: str = ''


class FollowTransport:
    def __init__(self, client, *, clock_ms: Callable[[], int] | None = None):
        self.client = client
        self.clock = clock_ms or (lambda: int(time.monotonic()*1000))

    def publish(self, position: SharedPosition):
        from core.actions.program_gamepad import host_clock_ms
        age = self.clock()-position.captured_at_ms
        if not 0 <= age < 500:
            return False
        self.client.request('sync.share.position', dict(actorId=position.actor_id,
            mapId=position.map_id, mapVersion=position.map_version,
            x=position.position[0], y=position.position[1], confidence=position.confidence, ageMs=age,
            deadlineMs=host_clock_ms()+500-age))
        return True

    def send_event(self, device_id, name, targets, *, host_deadline_ms=None):
        from core.actions.program_gamepad import host_clock_ms
        deadline=host_clock_ms()+250 if host_deadline_ms is None else host_deadline_ms
        if host_clock_ms() >= deadline: return False
        return self.client.request('sync.share.event', dict(deviceId=device_id, name=name, targets=list(targets),deadlineMs=deadline))

    def poll(self):
        started = self.clock()
        reply = self.client.request('sync.share.drain')
        now = self.clock()
        positions, events = [], []
        for item in reply.get('status', {}).get('sharedPositions', []):
            try:
                p = item['position']
                age = float(item['ageMs'])
                x, y, confidence = float(p['x']), float(p['y']), float(p['confidence'])
                if not all(isfinite(v) for v in (age, x, y, confidence)) or not 0 <= confidence <= 1:
                    continue
                stamp = int(started-age)
                if not 0 <= age < 500 or not 0 <= now-stamp < 500:
                    continue
                positions.append(SharedPosition(item['deviceId'], p['actorId'], p['mapId'], p['mapVersion'],
                    (x, y), confidence, stamp, item['sessionId']))
            except (KeyError, TypeError, ValueError):
                continue
        for item in reply.get('events', []):
            try:
                remaining = int(item['remainingMs'])
                deadline = started+remaining
                if not 0 < remaining <= 500 or now >= deadline:
                    continue
                events.append(SharedEvent(item['deviceId'], item['id'], item['name'], tuple(item['targets']), deadline, item['sessionId']))
            except (KeyError, TypeError, ValueError):
                continue
        return tuple(positions), tuple(events)
