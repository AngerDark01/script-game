from __future__ import annotations

from .debug import describe_action, describe_task, event_log
from .memory import EventMemory
from .monitor import EventMonitor
from .overlay_models import task_to_overlay
from .position_stabilizer import EventPositionStabilizer
from .runner import EventRunner
from .scheduler import EventScheduler


class EventCoordinator:
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

    def update(self, tick, run_handlers: bool = True):
        if not getattr(self.config, "enabled", True):
            if self._should_log(tick.now_ms, 3000):
                event_log("coordinator disabled")
            if self.runner.active_task is not None:
                self.runner.update(None, tick, self.config)
            self.last_action = None
            self.last_selected_task = None
            return None
        detections = self.monitor.detect(tick, self.config)
        self.last_detections = detections
        observations = self.position_stabilizer.update(
            detections,
            getattr(tick, "frame_registration", None),
            self.config,
            tick.now_ms,
        )
        self.last_observations = observations
        if detections and self._should_log(tick.now_ms, 750):
            event_log(
                "event detections",
                count=len(detections),
                best=max(float(item.confidence) for item in detections),
                events=",".join(sorted({item.event_type for item in detections})),
            )
        if observations and self._should_log(tick.now_ms, 750):
            event_log(
                "stable observations",
                count=len(observations),
                best=max(float(item.confidence) for item in observations),
                events=",".join(sorted({item.event_type for item in observations})),
            )
        self.memory.merge_observations(observations, self.config, tick.now_ms)
        task = self.scheduler.pick(self._enabled_active_tasks(), tick.player_global_pos)
        if task is not self.last_selected_task:
            event_log("scheduler selected", task=describe_task(task))
            self.last_selected_task = task
        if not run_handlers:
            if self.runner.active_task is not None:
                self.runner.update(None, tick, self.config)
            self.last_action = None
            return None
        action = self.runner.update(task, tick, self.config)
        self.last_action = action
        if action is not None and self._should_log(tick.now_ms, 750):
            event_log("coordinator action", task=describe_task(task), action=describe_action(action))
        return action

    def tasks(self):
        return self.memory.tasks()

    def overlays(self):
        if not getattr(self.config, "enabled", True):
            return []
        overlays = []
        for task in self._enabled_display_tasks():
            definition = self.registry.get(task.event_type)
            overlays.append(task_to_overlay(task, definition))
        return overlays

    def status_summary(self) -> str:
        if not getattr(self.config, "enabled", True):
            return ""
        task = self.last_selected_task
        if task is not None and not self._is_event_enabled(task.event_type):
            task = None
        if task is None:
            active = self._enabled_active_tasks()
            if not active:
                return ""
            task = active[0]
        action = describe_action(self.last_action).split(" ", 1)[0] if self.last_action else "idle"
        return (
            f"event:{task.event_type} {task.state.value} "
            f"seen={task.seen_count} act={action}"
        )

    def _should_log(self, now_ms: int, interval_ms: int) -> bool:
        if now_ms - self._last_log_ms < interval_ms:
            return False
        self._last_log_ms = int(now_ms)
        return True

    def _enabled_active_tasks(self) -> list:
        tasks = []
        for task in self.memory.active_tasks():
            if self._is_event_enabled(task.event_type):
                tasks.append(task)
        return tasks

    def _enabled_display_tasks(self) -> list:
        tasks = []
        for task in self.memory.tasks():
            if self._is_event_enabled(task.event_type):
                tasks.append(task)
        return tasks

    def _is_event_enabled(self, event_type: str) -> bool:
        event_config = self.config.event(event_type) if hasattr(self.config, "event") else {}
        return bool(event_config.get("enabled", True))
