from __future__ import annotations

import time


class PerformanceMonitor:
    """Small rolling timing collector used by MapStitcher."""

    def __init__(self):
        self.timings = {}
        self.frame_timings = []

    def record(self, name, duration_ms):
        if name not in self.timings:
            self.timings[name] = []
        self.timings[name].append(duration_ms)
        if len(self.timings[name]) > 100:
            self.timings[name].pop(0)


class Timer:
    """Context manager that records elapsed milliseconds into a PerformanceMonitor."""

    def __init__(self, monitor, name):
        self.monitor = monitor
        self.name = name
        self.start_time = None

    def __enter__(self):
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.monitor:
            duration_ms = (time.perf_counter() - self.start_time) * 1000
            self.monitor.record(self.name, duration_ms)
