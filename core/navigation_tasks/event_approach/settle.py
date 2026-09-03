from __future__ import annotations

from core.routing.geometry import point_distance

from core.navigation_tasks.models import NavigationIntent, NavigationIntentType

from .geometry import int_point_or_none
from .models import EventApproachResult


def reset_settle(approach) -> None:
    approach._last_player_pos = None
    approach._stable_frames = 0
    approach._settle_started_ms = None


def settle_or_ready(
    approach,
    *,
    task,
    current,
    target,
    approach_target,
    now_ms: int,
    distance: float,
) -> EventApproachResult:
    task_id = str(getattr(task, "id", "") or "")
    task_kind = getattr(getattr(task, "kind", None), "value", None)
    motion = 0.0 if approach._last_player_pos is None else point_distance(current, approach._last_player_pos)
    approach._last_player_pos = current
    if motion <= float(approach.config.max_motion_per_frame):
        approach._stable_frames += 1
    else:
        approach._stable_frames = 0
        approach._settle_started_ms = int(now_ms)

    if approach._settle_started_ms is None:
        approach._settle_started_ms = int(now_ms)
    waited_ms = int(now_ms) - int(approach._settle_started_ms)
    ready = (
        waited_ms >= int(approach.config.settle_ms)
        and approach._stable_frames >= int(approach.config.stable_frames)
    )
    phase = "ready" if ready else "settling"
    approach._log_phase(
        now_ms,
        phase,
        task=task_id,
        player=int_point_or_none(current),
        target=int_point_or_none(target),
        approach_target=int_point_or_none(approach_target),
        distance=round(float(distance), 1),
        waited_ms=waited_ms,
        stable_frames=approach._stable_frames,
        motion=round(float(motion), 1),
    )
    if ready:
        return EventApproachResult(
            ready=True,
            phase="ready",
            approach_target=approach_target,
            reason="event approach ready",
        )
    return EventApproachResult(
        ready=False,
        phase="settling",
        approach_target=approach_target,
        reason="event approach settling",
        intent=NavigationIntent(
            type=NavigationIntentType.WAIT,
            task_id=task_id,
            task_kind=task_kind,
            player_pos=current,
            target_pos=target,
            subgoal=approach_target,
            path=[current, approach_target] if approach_target else [],
            path_kind="event_settle",
            message="event approach settling",
            metadata={
                "event_approach_phase": "settling",
                "event_approach_waited_ms": waited_ms,
                "event_approach_stable_frames": approach._stable_frames,
            },
        ),
    )
