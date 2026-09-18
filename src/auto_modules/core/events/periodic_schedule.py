"""Local fixed-cadence scheduling independent of devices and localization."""


class PeriodicSchedule:
    """Caller-owned monotonic milliseconds; no threads, I/O or catch-up queue.

    The caller owns execution and supplies ``busy`` while a previous run is
    active. Lifecycle, cancellation and finite repetition counts live above
    this time calculation, not in a second action runner.
    """

    def __init__(self, interval_ms, *, first_due_ms):
        if type(interval_ms) is not int or interval_ms <= 0:
            raise ValueError('positive integer interval required')
        if type(first_due_ms) is not int or first_due_ms < 0:
            raise ValueError('nonnegative integer deadline required')
        self.interval_ms = interval_ms
        self.next_due_ms = first_due_ms
        self.last_poll_ms = None

    def poll(self, now_ms, *, busy=False):
        if type(now_ms) is not int or now_ms < 0:
            raise ValueError('nonnegative integer timestamp required')
        if self.last_poll_ms is not None and now_ms < self.last_poll_ms:
            raise ValueError('monotonic clock required')
        self.last_poll_ms = now_ms
        if now_ms < self.next_due_ms:
            return False
        skipped = (now_ms - self.next_due_ms) // self.interval_ms
        self.next_due_ms += (skipped + 1) * self.interval_ms
        return not busy
