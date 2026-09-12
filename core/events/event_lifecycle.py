"""Lifecycle limits around parallel tracks and ordered event steps."""

from dataclasses import dataclass

from core.events.gamepad_output import EVENT_INPUTS


PARALLEL_MODES = frozenset(('once', 'continuous', 'frequency'))


def validate_parallel_step(step: dict) -> None:
    """Validate one bounded, non-recursive parallel sequence step."""
    if not isinstance(step, dict) or step.get('op') != 'parallel':
        raise ValueError('parallel step required')
    duration = step.get('ms')
    if type(duration) is not int or not 1 <= duration <= 60000:
        raise ValueError('parallel step duration must be 1..60000ms')
    tracks = step.get('tracks')
    if not isinstance(tracks, (list, tuple)) or not 1 <= len(tracks) <= 32:
        raise ValueError('parallel step needs one to thirty-two tracks')
    for track in tracks:
        if not isinstance(track, dict) or 'op' in track:
            raise ValueError('nested parallel operations are not supported')
        names = track.get('buttons')
        if not isinstance(names, (list, tuple)) or not 1 <= len(names) <= 16:
            raise ValueError('parallel track needs one to sixteen Xbox inputs')
        if len(set(names)) != len(names) or any(name not in EVENT_INPUTS for name in names):
            raise ValueError('parallel track has unknown or duplicate Xbox input')
        mode = track.get('mode', 'once')
        if mode not in PARALLEL_MODES:
            raise ValueError('unknown parallel track mode')
        delay = track.get('delay_ms', 0)
        if type(delay) is not int or not 0 <= delay <= duration:
            raise ValueError('parallel track delay must be within group duration')
        hold = track.get('hold_ms', 100)
        if type(hold) is not int or hold <= 0:
            raise ValueError('parallel track hold_ms must be positive')
        interval = track.get('interval_ms')
        if mode == 'frequency':
            if type(interval) is not int or interval <= 0:
                raise ValueError('frequency track needs positive interval_ms')
        elif interval is not None:
            raise ValueError('only frequency tracks use interval_ms')
        end = track.get('end_ms')
        if end is not None and (type(end) is not int or not delay <= end <= duration):
            raise ValueError('parallel track end_ms must be within its group')


def parallel_inputs_at(step: dict, elapsed_ms: int) -> set[str]:
    """Return all declarative inputs active at a parallel step timestamp."""
    validate_parallel_step(step)
    if type(elapsed_ms) is not int or elapsed_ms < 0:
        raise ValueError('elapsed_ms must be nonnegative integer')
    if elapsed_ms >= step['ms']:
        return set()
    active = set()
    for track in step['tracks']:
        delay = track.get('delay_ms', 0)
        end = track.get('end_ms', step['ms'])
        if elapsed_ms < delay or elapsed_ms >= end:
            continue
        local_ms = elapsed_ms - delay
        mode = track.get('mode', 'once')
        if mode == 'continuous':
            enabled = True
        elif mode == 'once':
            enabled = local_ms < track.get('hold_ms', 100)
        else:
            enabled = local_ms % track['interval_ms'] < track.get('hold_ms', 100)
        if enabled:
            active.update(track['buttons'])
    return active


@dataclass
class EventLifecycle:
    tracks: list
    max_runs: int | None = None
    loop: bool = False
    end_ms: int | None = None
    steps: tuple = ()

    def __post_init__(self):
        if self.max_runs is not None and (type(self.max_runs) is not int or self.max_runs <= 0):
            raise ValueError('max_runs must be positive')
        if self.end_ms is not None and (type(self.end_ms) is not int or self.end_ms <= 0):
            raise ValueError('end_ms must be positive')
        if self.loop and self.max_runs is None and self.end_ms is None:
            raise ValueError('loop requires max_runs or end_ms')
        for step in self.steps:
            if step.get('op') == 'parallel':
                validate_parallel_step(step)
        self._step_durations = tuple(max(0, int(step.get('ms', 100))) for step in self.steps)
        self._step_cycle_ms = sum(self._step_durations)
        track_cycle_ms = max((getattr(track, 'interval_ms', None) or track.hold_ms) for track in self.tracks) if self.tracks else 0
        self._cycle_ms = max(track_cycle_ms, self._step_cycle_ms)
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
        if not self.loop and self.max_runs is None and self.end_ms is None and self._cycle_ms and now_ms >= self._cycle_ms:
            self.finished = True
            return set()
        buttons = set()
        for track in self.tracks:
            if track.active_at(now_ms):
                buttons.update(track.buttons)
        if self.steps and self._step_cycle_ms:
            repeats = self.loop or self.max_runs is not None
            sequence_ms = now_ms % self._step_cycle_ms if repeats else now_ms
            elapsed = 0
            for step, duration in zip(self.steps, self._step_durations):
                if sequence_ms < elapsed + duration:
                    if step.get('op') == 'button':
                        names = step.get('buttons', step.get('button', ()))
                        if isinstance(names, str):
                            names = (names,)
                        buttons.update(str(name) for name in names)
                    elif step.get('op') == 'parallel':
                        buttons.update(parallel_inputs_at(step, sequence_ms - elapsed))
                    break
                elapsed += duration
        return buttons
