from __future__ import annotations

from core.routing.geometry import point_distance

from core.navigation_tasks.controller_utils import float_point
from core.navigation_tasks.debug import nav_log


def observe_localization(controller, pos, confidence: float, *, force_snap: bool = False) -> bool:
    controller.raw_pos = float_point(pos) if pos is not None else None
    if pos is None or float(confidence or 0.0) < controller.min_confidence:
        return False

    candidate = float_point(pos)
    if controller.trusted_pos is not None and not force_snap:
        jump = point_distance(candidate, controller.trusted_pos)
        if jump > controller.max_jump_distance and float(confidence or 0.0) < 0.9:
            nav_log("nav localization rejected jump", jump=round(float(jump), 2), confidence=float(confidence or 0.0))
            return False

    controller.trusted_pos = candidate
    if controller.control_pos is None or force_snap:
        controller.control_pos = candidate
    else:
        alpha = 0.5 if float(confidence or 0.0) >= 0.9 else controller.control_alpha
        controller.control_pos = (
            controller.control_pos[0] + (candidate[0] - controller.control_pos[0]) * alpha,
            controller.control_pos[1] + (candidate[1] - controller.control_pos[1]) * alpha,
        )
    projection = controller.route_context.project(controller.control_pos)
    if projection is not None:
        controller.route_progress = (
            projection.progress
            if controller.route_progress is None
            else max(controller.route_progress, projection.progress)
        )
    return True
