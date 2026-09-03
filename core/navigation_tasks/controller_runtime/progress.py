from __future__ import annotations

from core.routing.geometry import point_distance

from core.navigation_tasks.controller_utils import float_point, int_point, round_float
from core.navigation_tasks.debug import nav_log


def update_required_progress(controller) -> None:
    if controller.control_pos is None or not controller.route:
        return
    required = controller.route.get("required_points", []) or []
    if not required:
        return
    projection = controller.route_context.project(controller.control_pos)
    player_progress = projection.progress if projection else None
    next_index = controller._next_required_index(required)
    if next_index is None:
        return

    target = float_point(required[next_index])
    distance = point_distance(controller.control_pos, target)
    reached_by_distance = distance <= controller.arrival_radius
    target_progress = controller.route_context.progress_of(target)
    progress_delta = None
    if player_progress is not None and target_progress is not None:
        progress_delta = float(player_progress) - float(target_progress)

    if reached_by_distance:
        controller.completed_required.add(next_index)
        nav_log(
            "nav required completed",
            index=next_index,
            target=int_point(target),
            player=int_point(controller.control_pos),
            by_distance=True,
            by_progress=False,
            distance=round(float(distance), 2),
            player_progress=round_float(player_progress),
            target_progress=round_float(target_progress),
            progress_delta=round_float(progress_delta),
        )
        controller.movement.reset()
        controller.active_task_id = None


def next_required_index(controller, required: list) -> int | None:
    for index in range(len(required)):
        if index not in controller.completed_required:
            return index
    return None
