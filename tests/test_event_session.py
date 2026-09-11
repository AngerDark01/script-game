from dataclasses import dataclass

from core.events.action_tracks import ActionTrack, TrackMode
from core.runtime.event_session import EventSession


@dataclass(frozen=True)
class Definition:
    tracks: tuple
    max_runs: int | None = None
    loop: bool = False
    end_ms: int | None = None


@dataclass(frozen=True)
class Remote:
    name: str
    event_id: str
    deadline_ms: int


def test_remote_event_runs_without_localization():
    now = [1000]
    session = EventSession({'skill': Definition((ActionTrack(('A',), TrackMode.ONCE, 50),))}, clock_ms=lambda: now[0])
    assert session.receive_remote(Remote('skill', 'i1', 1100))
    assert session.tick() == {'A'}
    now[0] = 1050
    assert session.tick() == frozenset()
    assert not session.active


def test_expired_remote_event_is_not_started():
    session = EventSession({}, clock_ms=lambda: 1000)
    assert not session.receive_remote(Remote('missing', 'i1', 999))
