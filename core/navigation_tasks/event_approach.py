from __future__ import annotations

from dataclasses import dataclass

from core.path_utils import build_cumulative_lengths, interpolate_by_distance, point_distance

from .debug import nav_log
from .models import NavigationIntent, NavigationIntentType


@dataclass
class EventApproachConfig:
    enabled: bool = True
    game_view_map_size: int = 520
    visible_margin: int = 30
    approach_lookahead: float = 36.0
    click_cooldown_ms: int = 800
    stop_radius: float = 18.0
    settle_ms: int = 800
    stable_frames: int = 2
    max_motion_per_frame: float = 8.0


@dataclass
class EventApproachResult:
    ready: bool = False
    intent: NavigationIntent | None = None
    phase: str = "far"
    approach_target: tuple[float, float] | None = None
    reason: str = ""


class EventApproachController:
    """Navigation-layer gate before an event handler is allowed to trigger."""

    def __init__(self):
        self.config = EventApproachConfig()
        self._task_id: str | None = None
        self._released: set[str] = set()
        self._phase = "idle"
        self._last_player_pos: tuple[float, float] | None = None
        self._stable_frames = 0
        self._settle_started_ms: int | None = None
        self._last_log_ms = 0

    def configure(self, **kwargs) -> None:
        values = self.config.__dict__.copy()
        values.update(kwargs)
        self.config = EventApproachConfig(**values)

    def reset(self) -> None:
        self._task_id = None
        self._released.clear()
        self._phase = "idle"
        self._last_player_pos = None
        self._stable_frames = 0
        self._settle_started_ms = None
        self._last_log_ms = 0

    def reset_active(self) -> None:
        self._task_id = None
        self._phase = "idle"
        self._last_player_pos = None
        self._stable_frames = 0
        self._settle_started_ms = None
        self._last_log_ms = 0

    def finish_task(self, task_id: str | None) -> None:
        if task_id:
            self._released.discard(str(task_id))
        if self._task_id == task_id:
            self.reset_active()

    def is_released(self, task_id: str | None) -> bool:
        return bool(task_id and str(task_id) in self._released)

    def release_task(self, task_id: str | None) -> None:
        if not task_id:
            return
        self._released.add(str(task_id))
        self.reset_active()

    def update(
        self,
        *,
        task,
        current_pos,
        wall_map,
        pathfinder,
        explored_map,
        now_ms: int,
        lookahead_distance: float,
        route_context,
        movement,
    ) -> EventApproachResult:
        task_id = str(getattr(task, "id", "") or "")
        target = _float_point(getattr(task, "target_pos", None))
        if not self.config.enabled:
            return EventApproachResult(ready=True, phase="disabled", reason="event approach disabled")
        if current_pos is None or target is None:
            return EventApproachResult(
                ready=False,
                phase="waiting_localization",
                reason="waiting localization",
                intent=NavigationIntent(
                    type=NavigationIntentType.WAIT,
                    task_id=task_id,
                    task_kind=getattr(getattr(task, "kind", None), "value", None),
                    target_pos=target,
                    message="event approach waiting localization",
                ),
            )

        if self._task_id != task_id:
            self.reset_active()
            self._task_id = task_id

        current = _float_point(current_pos)
        visible = self._is_event_in_real_view(current, target)
        if not visible:
            self._reset_settle()
            if self._phase != "far":
                movement.force_replan = True
            result = self._move_toward_event(
                task=task,
                current=current,
                target=target,
                wall_map=wall_map,
                pathfinder=pathfinder,
                explored_map=explored_map,
                now_ms=now_ms,
                lookahead_distance=lookahead_distance,
                route_context=route_context,
                movement=movement,
                phase="far",
                click_cooldown_ms=None,
            )
            self._log_phase(
                now_ms,
                "far",
                task=task_id,
                player=_int_point(current),
                target=_int_point(target),
                visible=False,
            )
            return result

        distance_to_event = point_distance(current, target)
        if distance_to_event <= float(self.config.stop_radius):
            return self._settle_or_ready(
                task=task,
                current=current,
                target=target,
                approach_target=target,
                now_ms=now_ms,
                distance=distance_to_event,
            )

        if self._phase not in {"approach", "settling", "ready"}:
            movement.force_replan = True
        move_result = self._move_toward_event(
            task=task,
            current=current,
            target=target,
            wall_map=wall_map,
            pathfinder=pathfinder,
            explored_map=explored_map,
            now_ms=now_ms,
            lookahead_distance=float(self.config.approach_lookahead),
            route_context=None,
            movement=movement,
            phase="approach",
            click_cooldown_ms=int(self.config.click_cooldown_ms),
        )
        step_path = move_result.intent.path if move_result.intent else []
        approach_target = self._approach_target_from_path(step_path, target)
        distance_to_approach = (
            point_distance(current, approach_target)
            if approach_target is not None
            else distance_to_event
        )
        arrival_distance = min(distance_to_event, distance_to_approach)
        if arrival_distance <= float(self.config.stop_radius):
            return self._settle_or_ready(
                task=task,
                current=current,
                target=target,
                approach_target=approach_target or target,
                now_ms=now_ms,
                distance=arrival_distance,
            )

        self._reset_settle()
        self._log_phase(
            now_ms,
            "approach",
            task=task_id,
            player=_int_point(current),
            target=_int_point(target),
            approach_target=_int_point(approach_target),
            distance=round(float(distance_to_event), 1),
            visible=True,
        )
        return move_result

    def _move_toward_event(
        self,
        *,
        task,
        current,
        target,
        wall_map,
        pathfinder,
        explored_map,
        now_ms: int,
        lookahead_distance: float,
        route_context,
        movement,
        phase: str,
        click_cooldown_ms: int | None,
    ) -> EventApproachResult:
        task_id = str(getattr(task, "id", "") or "")
        task_kind = getattr(getattr(task, "kind", None), "value", None)
        step = movement.step(
            task_id=task_id,
            current_pos=current,
            target_pos=target,
            wall_map=wall_map,
            pathfinder=pathfinder,
            explored_map=explored_map,
            now_ms=now_ms,
            lookahead_distance=lookahead_distance,
            route_context=route_context,
            click_cooldown_ms=click_cooldown_ms,
        )
        if step is None:
            nav_log(
                "event approach path unavailable",
                task=task_id,
                phase=phase,
                player=_int_point(current),
                target=_int_point(target),
            )
            return EventApproachResult(
                ready=False,
                phase=phase,
                reason="path unavailable",
                intent=NavigationIntent(
                    type=NavigationIntentType.WAIT,
                    task_id=task_id,
                    task_kind=task_kind,
                    player_pos=current,
                    target_pos=target,
                    message="event approach path unavailable",
                ),
            )

        intent_type = NavigationIntentType.MOVE_MAP if step.should_click and step.subgoal else NavigationIntentType.WAIT
        return EventApproachResult(
            ready=False,
            phase=phase,
            reason="moving to event",
            intent=NavigationIntent(
                type=intent_type,
                task_id=task_id,
                task_kind=task_kind,
                player_pos=current,
                target_pos=target,
                subgoal=step.subgoal,
                path=step.path,
                path_kind=step.path_kind,
                message="event approach move" if intent_type == NavigationIntentType.MOVE_MAP else "event approach hold",
                metadata={
                    "deviation": step.deviation,
                    "force_click_target": step.force_click_target,
                    "event_approach_phase": phase,
                },
            ),
        )

    def _settle_or_ready(
        self,
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
        motion = 0.0 if self._last_player_pos is None else point_distance(current, self._last_player_pos)
        self._last_player_pos = current
        if motion <= float(self.config.max_motion_per_frame):
            self._stable_frames += 1
        else:
            self._stable_frames = 0
            self._settle_started_ms = int(now_ms)

        if self._settle_started_ms is None:
            self._settle_started_ms = int(now_ms)
        waited_ms = int(now_ms) - int(self._settle_started_ms)
        ready = (
            waited_ms >= int(self.config.settle_ms)
            and self._stable_frames >= int(self.config.stable_frames)
        )
        phase = "ready" if ready else "settling"
        self._log_phase(
            now_ms,
            phase,
            task=task_id,
            player=_int_point(current),
            target=_int_point(target),
            approach_target=_int_point(approach_target),
            distance=round(float(distance), 1),
            waited_ms=waited_ms,
            stable_frames=self._stable_frames,
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
                    "event_approach_stable_frames": self._stable_frames,
                },
            ),
        )

    def _is_event_in_real_view(self, player, target) -> bool:
        half = max(1.0, float(self.config.game_view_map_size) * 0.5)
        margin = max(0.0, float(self.config.visible_margin))
        return (
            float(player[0]) - half - margin <= float(target[0]) <= float(player[0]) + half + margin
            and float(player[1]) - half - margin <= float(target[1]) <= float(player[1]) + half + margin
        )

    def _approach_target_from_path(self, path, target) -> tuple[float, float] | None:
        if not path:
            return target
        clean_path = [_float_point(point) for point in path]
        if len(clean_path) < 2:
            return clean_path[0]
        lengths = build_cumulative_lengths(clean_path)
        total = lengths[-1] if lengths else 0.0
        stop_distance = max(8.0, float(self.config.stop_radius))
        if total <= stop_distance:
            return clean_path[-1]
        return interpolate_by_distance(clean_path, lengths, total - stop_distance) or clean_path[-1]

    def _reset_settle(self) -> None:
        self._last_player_pos = None
        self._stable_frames = 0
        self._settle_started_ms = None

    def _log_phase(self, now_ms: int, phase: str, **fields) -> None:
        if phase == self._phase and int(now_ms) - self._last_log_ms < 1000:
            return
        self._phase = phase
        self._last_log_ms = int(now_ms)
        nav_log(f"event approach {phase}", **fields)


def _float_point(point) -> tuple[float, float] | None:
    if point is None:
        return None
    return (float(point[0]), float(point[1]))


def _int_point(point) -> tuple[int, int] | None:
    if point is None:
        return None
    return (int(round(float(point[0]))), int(round(float(point[1]))))
