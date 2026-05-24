from __future__ import annotations

from .debug import nav_log
from .models import NavigationTask, NavigationTaskKind, NavigationTaskState


class NavigationTaskScheduler:
    """Select one navigation task from route goals and dynamic events."""

    def __init__(self):
        self._last_selected_id: str | None = None

    def pick(
        self,
        *,
        tasks: list[NavigationTask],
        player_pos,
        route_context,
        active_task_id: str | None = None,
        manual_event_only: bool = False,
    ) -> NavigationTask | None:
        runnable = [task for task in tasks if task.state in (NavigationTaskState.PENDING, NavigationTaskState.MOVING, NavigationTaskState.EXECUTING)]
        if manual_event_only:
            runnable = [task for task in runnable if task.kind == NavigationTaskKind.EVENT]
        if not runnable:
            return None

        if active_task_id:
            for task in runnable:
                if task.id == active_task_id and task.kind == NavigationTaskKind.EVENT:
                    return self._log_selection(task, player_pos, reason="active_lock")

        if manual_event_only:
            return self._log_selection(_nearest(runnable, player_pos), player_pos, reason="manual_event")

        base_target = self._next_static_task(runnable)
        candidates = [base_target] if base_target is not None else []
        candidates.extend(self._eligible_events(runnable, player_pos, base_target, route_context))
        candidates = [task for task in candidates if task is not None]
        if not candidates:
            return None

        selected = self._nearest_by_route_progress(candidates, player_pos, route_context)
        reason = "dynamic_route_order" if selected and selected.kind == NavigationTaskKind.EVENT else "route_static"
        return self._log_selection(selected, player_pos, reason=reason)

    def _next_static_task(self, tasks: list[NavigationTask]) -> NavigationTask | None:
        required = sorted(
            [task for task in tasks if task.kind == NavigationTaskKind.REQUIRED],
            key=lambda task: int(task.required_index if task.required_index is not None else 9999),
        )
        if required:
            return required[0]
        exits = [task for task in tasks if task.kind == NavigationTaskKind.EXIT]
        return exits[0] if exits else None

    def _eligible_events(
        self,
        tasks: list[NavigationTask],
        player_pos,
        base_target: NavigationTask | None,
        route_context,
    ) -> list[NavigationTask]:
        events = [task for task in tasks if task.kind == NavigationTaskKind.EVENT]
        if not events or player_pos is None:
            return []
        if base_target is None:
            return events

        player_progress = None if route_context is None else route_context.progress_of(player_pos)
        target_progress = base_target.route_progress
        if player_progress is None or target_progress is None:
            return []

        lower = min(float(player_progress), float(target_progress)) - 24.0
        if base_target.kind == NavigationTaskKind.REQUIRED:
            upper = float(target_progress) + 12.0
        else:
            upper = max(float(player_progress), float(target_progress)) + 72.0
        return [
            task
            for task in events
            if task.route_progress is not None
            and lower <= float(task.route_progress) <= upper
        ]

    def _nearest_by_route_progress(self, tasks: list[NavigationTask], player_pos, route_context) -> NavigationTask | None:
        if not tasks:
            return None
        player_progress = None if route_context is None or player_pos is None else route_context.progress_of(player_pos)
        if player_progress is None:
            return _nearest(tasks, player_pos)
        return sorted(
            tasks,
            key=lambda task: (
                max(0.0, float(task.route_progress if task.route_progress is not None else player_progress) - float(player_progress)),
                -int(task.priority),
                _distance_sq(task.target_pos, player_pos),
                task.id,
            ),
        )[0]

    def _log_selection(self, task: NavigationTask | None, player_pos, *, reason: str) -> NavigationTask | None:
        if task is None:
            return None
        if task.id != self._last_selected_id:
            self._last_selected_id = task.id
            nav_log(
                "nav task selected",
                selected=task.id,
                kind=task.kind.value,
                reason=reason,
                target=_int_point(task.target_pos),
                player=_int_point(player_pos) if player_pos is not None else None,
                progress=round(float(task.route_progress), 1) if task.route_progress is not None else None,
            )
        return task


def _nearest(tasks: list[NavigationTask], player_pos) -> NavigationTask | None:
    if not tasks:
        return None
    if player_pos is None:
        return tasks[0]
    return sorted(
        tasks,
        key=lambda task: (
            -int(task.priority),
            _distance_sq(task.target_pos, player_pos),
            task.id,
        ),
    )[0]


def _distance_sq(point, player_pos) -> float:
    if point is None or player_pos is None:
        return 0.0
    return (
        (float(point[0]) - float(player_pos[0])) ** 2
        + (float(point[1]) - float(player_pos[1])) ** 2
    )


def _int_point(point) -> tuple[int, int] | None:
    if point is None:
        return None
    return (int(round(float(point[0]))), int(round(float(point[1]))))
