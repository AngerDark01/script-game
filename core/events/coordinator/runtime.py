from __future__ import annotations

from core.events.memory import EventMemory
from core.events.monitor import EventMonitor
from core.events.position_stabilizer import EventPositionStabilizer
from core.events.runner import EventRunner
from core.events.scheduler import EventScheduler

from .filters import enabled_active_tasks, enabled_display_tasks, is_event_enabled, should_log
from .observation import apply_event_detections, detect_events, observe_events
from .presentation import build_overlays, status_summary
from .reset import reset_event_type
from .task_run import run_event_task, run_selected_task


class EventCoordinator:
    """Stateful facade for event detection, memory, scheduling, and handler running."""

    def __init__(self, registry, config, memory: EventMemory | None = None):
        self.registry = registry
        self.config = config
        self.memory = memory or EventMemory()
        self.monitor = EventMonitor(registry)
        self.position_stabilizer = EventPositionStabilizer()
        self.scheduler = EventScheduler()
        self.runner = EventRunner(registry, self.memory)
        self.last_detections = []
        self.last_observations = []
        self.last_action = None
        self.last_selected_task = None
        self._last_log_ms = 0

    def observe(self, tick) -> None:
        observe_events(self, tick)

    def detect(self, tick) -> list:
        return detect_events(self, tick)

    def apply_detections(self, tick, detections) -> None:
        apply_event_detections(self, tick, detections)

    def run_task(self, task_id: str | None, tick):
        return run_event_task(self, task_id, tick)

    def _run_selected_task(self, task, tick):
        return run_selected_task(self, task, tick)

    def tasks(self):
        return self.memory.tasks()

    def reset_event_type(self, event_type: str, now_ms: int | None = None) -> int:
        return reset_event_type(self, event_type, now_ms=now_ms)

    def overlays(self):
        return build_overlays(self)

    def status_summary(self) -> str:
        return status_summary(self)

    def _should_log(self, now_ms: int, interval_ms: int) -> bool:
        return should_log(self, now_ms, interval_ms)

    def _enabled_active_tasks(self) -> list:
        return enabled_active_tasks(self)

    def _enabled_display_tasks(self) -> list:
        return enabled_display_tasks(self)

    def _is_event_enabled(self, event_type: str) -> bool:
        return is_event_enabled(self, event_type)
