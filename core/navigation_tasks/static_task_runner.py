from __future__ import annotations

from core.routing.geometry import is_inside_exit_region, point_distance

from core.navigation_tasks.controller_utils import int_point
from core.navigation_tasks.debug import nav_log
from core.navigation_tasks.intent_factory import movement_step_intent
from core.navigation_tasks.models import NavigationIntent, NavigationIntentType, NavigationTaskKind


def update_static_task(
    controller,
    task,
    wall_map,
    pathfinder,
    explored_map,
    now_ms: int,
    lookahead_distance: float,
) -> NavigationIntent:
    """Update a required/exit static navigation task."""
    if controller.control_pos is None:
        return NavigationIntent(type=NavigationIntentType.WAIT, task_id=task.id, message="waiting localization")

    if task.kind == NavigationTaskKind.EXIT and is_inside_exit_region(
        controller.control_pos,
        task.metadata.get("exit_region"),
    ):
        controller.active = False
        nav_log("nav task arrived exit", task=task.id, player=int_point(controller.control_pos))
        return NavigationIntent(
            type=NavigationIntentType.ARRIVED,
            task_id=task.id,
            task_kind=task.kind.value,
            player_pos=controller.control_pos,
            target_pos=task.target_pos,
            message="arrived exit",
        )

    if task.kind == NavigationTaskKind.REQUIRED and task.required_index is not None:
        if point_distance(controller.control_pos, task.target_pos) <= controller.arrival_radius:
            controller.completed_required.add(int(task.required_index))
            controller.active_task_id = None
            controller.movement.reset()
            nav_log("nav task reached required", task=task.id, player=int_point(controller.control_pos))
            return NavigationIntent(
                type=NavigationIntentType.WAIT,
                task_id=task.id,
                task_kind=task.kind.value,
                player_pos=controller.control_pos,
                target_pos=task.target_pos,
                required_index=task.required_index,
                message="required reached",
            )

    step = controller.movement.step(
        task_id=task.id,
        current_pos=controller.control_pos,
        target_pos=task.target_pos,
        wall_map=wall_map,
        pathfinder=pathfinder,
        explored_map=explored_map,
        now_ms=now_ms,
        lookahead_distance=lookahead_distance,
        route_context=controller.route_context,
    )
    return movement_step_intent(
        task=task,
        player_pos=controller.control_pos,
        step=step,
        unavailable_message="path unavailable",
        move_message="move static task",
        wait_message="hold static task",
    )
