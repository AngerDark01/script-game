"""Bounded, pickle-safe evidence history; only the parent writes log records."""
from collections import deque
import time


class DiagnosticJournal:
    """Keep transitions and 1Hz samples across dropped latest-only snapshots."""

    def __init__(self, capacity=32):
        self._events = deque(maxlen=max(1, int(capacity)))
        self._last = {}
        self._sequence = 0

    def record(self, stage, role, reason, *, now_ms=None, **details):
        stamp = int(time.monotonic() * 1000) if now_ms is None else int(now_ms)
        key = (stage, role)
        previous = self._last.get(key)
        if previous is not None and previous[0] == reason and 0 <= stamp - previous[1] < 1000:
            return
        self._last[key] = (reason, stamp)
        self._sequence += 1
        self._events.append(dict(event_id=self._sequence, stage=stage, role=role,
                                 reason=reason, recorded_at_ms=stamp, details=details))

    def snapshot(self):
        return tuple(self._events)


class DiagnosticRelay:
    """Deduplicate per-worker-generation history and report evidence loss."""

    def __init__(self, logger):
        self.logger = logger
        self._last = {}

    def consume(self, stream, generation, events):
        # Only the current epoch of each stream is retained.
        old_generation, last_id = self._last.get(stream, (generation, 0))
        if old_generation != generation:
            last_id = 0
        for event in events:
            event_id = int(event["event_id"])
            if event_id <= last_id:
                continue
            if event_id > last_id + 1:
                self.logger.warning(
                    "step=follow_engine.diagnostic_gap stream=%s generation=%s dropped=%s",
                    stream, generation, event_id - last_id - 1,
                )
            self.logger.info(
                "step=follow_engine.evidence stream=%s generation=%s event_id=%s stage=%s role=%s reason=%s details=%s",
                stream, generation, event_id, event["stage"], event["role"], event["reason"], event["details"],
            )
            last_id = event_id
        self._last[stream] = (generation, last_id)
