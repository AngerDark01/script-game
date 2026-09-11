"""Lifecycle limits around parallel button tracks."""

from dataclasses import dataclass


@dataclass
class EventLifecycle:
    tracks: list
    max_runs: int | None = None
    loop: bool = False
    end_ms: int | None = None

    def __post_init__(self):
        if self.max_runs is not None and (type(self.max_runs) is not int or self.max_runs <= 0):
            raise ValueError('max_runs must be positive')
        if self.end_ms is not None and (type(self.end_ms) is not int or self.end_ms <= 0):
            raise ValueError('end_ms must be positive')
        if self.loop and self.max_runs is None and self.end_ms is None:
            raise ValueError('loop requires max_runs or end_ms')
        self._cycle_ms = max((getattr(track, 'interval_ms', None) or track.hold_ms) for track in self.tracks) if self.tracks else 0
        self.finished = False
        self._runs = 0
        self._last_ms = None

    def poll(self, now_ms: int) -> set[str]:
        if type(now_ms) is not int or now_ms < 0:
            raise ValueError('now_ms must be nonnegative integer')
        if self._last_ms is not None and now_ms < self._last_ms:
            raise ValueError('monotonic clock required')
        self._last_ms = now_ms
        if self.finished:
            return set()
        if self.end_ms is not None and now_ms >= self.end_ms:
            self.finished = True
            return set()
        if self.max_runs is not None and self._cycle_ms and now_ms >= self.max_runs * self._cycle_ms:
            self.finished = True
            return set()
        buttons = set()
        for track in self.tracks:
            if track.active_at(now_ms):
                buttons.update(track.buttons)
        return buttons
