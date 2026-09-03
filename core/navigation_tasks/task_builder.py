from __future__ import annotations

from core.events.models import EventTaskState

from .models import NavigationTask, NavigationTaskKind, NavigationTaskState


class NavigationTaskBuilder:
    """Build static route goals and dynamic event tasks into one task list."""

    def __init__(self, *, required_arrival_radius: float = 26.0):
        self.required_arrival_radius = float(required_arrival_radius)

    def build(
        self,
        *,
        route: dict | None,
        event_tasks: list,
        route_context,
        completed_required: set[int],
    ) -> list[NavigationTask]:
        tasks: list[NavigationTask] = []
        main_route = route or {}

        for index, point in enumerate(main_route.get("required_points", []) or []):
            if index in completed_required:
                state = NavigationTaskState.COMPLETED
            else:
                state = NavigationTaskState.PENDING
            target = _float_point(point)
            tasks.append(
                NavigationTask(
                    id=f"required:{index}",
                    kind=NavigationTaskKind.REQUIRED,
                    target_pos=target,
                    state=state,
                    priority=50,
                    route_progress=_progress(route_context, target),
                    required_index=index,
                    radius=max(1.0, float(self.required_arrival_radius)),
                )
            )

        exit_region = main_route.get("exit_region")
        if exit_region and exit_region.get("center"):
            target = _float_point(exit_region["center"])
            tasks.append(
                NavigationTask(
                    id="exit:main",
                    kind=NavigationTaskKind.EXIT,
                    target_pos=target,
                    state=NavigationTaskState.PENDING,
                    priority=0,
                    route_progress=_progress(route_context, target),
                    radius=float(exit_region.get("radius", 28)),
                    metadata={"exit_region": exit_region},
                )
            )

        for event_task in event_tasks or []:
            if not _is_event_runnable(event_task):
                continue
            target = _float_point(getattr(event_task, "global_pos", None))
            event_radius = _event_radius(event_task)
            tasks.append(
                NavigationTask(
                    id=f"event:{getattr(event_task, 'id', '')}",
                    kind=NavigationTaskKind.EVENT,
                    target_pos=target,
                    state=NavigationTaskState.PENDING,
                    priority=int(getattr(event_task, "priority", 0)) + 100,
                    route_progress=_progress(route_context, target),
                    source_ref=event_task,
                    event_type=str(getattr(event_task, "event_type", "")),
                    radius=event_radius,
                    metadata={
                        "event_task_id": str(getattr(event_task, "id", "")),
                        "event_state": str(getattr(getattr(event_task, "state", None), "value", getattr(event_task, "state", ""))),
                        "event_stop_radius": event_radius,
                    },
                )
            )

        return tasks


def _is_event_runnable(task) -> bool:
    state = getattr(task, "state", None)
    return state in (EventTaskState.PENDING, EventTaskState.RUNNING)


def _progress(route_context, point) -> float | None:
    if route_context is None:
        return None
    return route_context.progress_of(point)


def _float_point(point) -> tuple[float, float]:
    return (float(point[0]), float(point[1]))


def _event_radius(event_task) -> float | None:
    metadata = getattr(event_task, "metadata", {}) or {}
    if str(getattr(event_task, "event_type", "")) == "loot":
        radius = metadata.get("pickup_radius")
        if radius is not None:
            return max(4.0, float(radius))
    return None
