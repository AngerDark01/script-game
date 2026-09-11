"""Pure timed Xbox button tracks; no capture, localization or device I/O."""

from dataclasses import dataclass
from enum import Enum


class TrackMode(str, Enum):
    ONCE = 'once'
    CONTINUOUS = 'continuous'
    FREQUENCY = 'frequency'


@dataclass(frozen=True)
class ActionTrack:
    buttons: tuple[str, ...]
    mode: TrackMode = TrackMode.ONCE
    hold_ms: int = 100
    interval_ms: int | None = None
    end_ms: int | None = None

    def __post_init__(self):
        if not self.buttons or len(set(self.buttons)) != len(self.buttons):
            raise ValueError('track needs unique buttons')
        if type(self.hold_ms) is not int or self.hold_ms <= 0:
            raise ValueError('hold_ms must be positive')
        if self.mode is TrackMode.ONCE:
            if self.interval_ms is not None or self.end_ms is not None:
                raise ValueError('once track cannot repeat')
        else:
            if type(self.interval_ms) is not int or self.interval_ms <= 0:
                raise ValueError('repeating track needs positive interval_ms')
            if self.end_ms is not None and (type(self.end_ms) is not int or self.end_ms < 0):
                raise ValueError('end_ms must be nonnegative')
            if self.end_ms is not None and self.end_ms < self.hold_ms:
                raise ValueError('end_ms must include first hold')

    def active_at(self, elapsed_ms: int) -> bool:
        if type(elapsed_ms) is not int or elapsed_ms < 0:
            raise ValueError('elapsed_ms must be nonnegative integer')
        if self.end_ms is not None and elapsed_ms >= self.end_ms:
            return False
        if self.mode is TrackMode.ONCE:
            return elapsed_ms < self.hold_ms
        return elapsed_ms % self.interval_ms < self.hold_ms

    @staticmethod
    def buttons_at(tracks, elapsed_ms: int) -> set[str]:
        result = set()
        for track in tracks:
            if track.active_at(elapsed_ms):
                result.update(track.buttons)
        return result
