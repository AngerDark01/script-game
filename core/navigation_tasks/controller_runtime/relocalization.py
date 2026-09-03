from __future__ import annotations

from core.navigation_tasks.controller_utils import int_point
from core.navigation_tasks.debug import nav_log
from core.navigation_tasks.models import NavigationIntent, NavigationIntentType


def consume_relocalization_intent(controller, now_ms: int, *, selected=None) -> NavigationIntent | None:
    request = controller.coordinate_diagnostics.consume_relocalization_request()
    if request is None:
        return None
    controller.movement.reset()
    nav_log(
        "nav coordinate relocalization requested",
        reason=request.reason,
        score=request.score,
        signals=",".join(request.signals),
        player=int_point(controller.control_pos),
        task=selected.id if selected else controller.active_task_id,
    )
    return NavigationIntent(
        type=NavigationIntentType.WAIT,
        task_id=selected.id if selected else controller.active_task_id,
        task_kind=selected.kind.value if selected else None,
        player_pos=controller.control_pos,
        target_pos=selected.target_pos if selected else None,
        message="coordinate relocalizing",
        metadata={
            "force_relocalize": True,
            "relocalize_reason": request.reason,
            "relocalize_score": request.score,
        },
    )
