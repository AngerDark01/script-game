from __future__ import annotations

from core.anchor_path import plan_path_with_optional_anchors
from core.path_utils import (
    build_cumulative_lengths,
    interpolate_by_distance,
    point_distance,
    project_point_onto_path,
    remove_collinear_points,
)

from .debug import nav_log
from .models import MovementStep


class MovementExecutor:
    """Shared A* lookahead mover for route and event map targets."""

    def __init__(
        self,
        *,
        click_cooldown_ms: int = 260,
        min_click_target_delta: float = 8.0,
        arrival_radius: float = 26.0,
        anchor_arrival_radius: float | None = None,
        path_deviation_threshold: float = 96.0,
        min_progress_delta: float = 12.0,
        progress_timeout_ms: int = 1800,
        max_recover_attempts: int = 2,
    ):
        self.click_cooldown_ms = int(click_cooldown_ms)
        self.min_click_target_delta = float(min_click_target_delta)
        self.arrival_radius = float(arrival_radius)
        self.anchor_arrival_radius = float(anchor_arrival_radius if anchor_arrival_radius is not None else arrival_radius)
        self.path_deviation_threshold = float(path_deviation_threshold)
        self.min_progress_delta = float(min_progress_delta)
        self.progress_timeout_ms = int(progress_timeout_ms)
        self.max_recover_attempts = int(max_recover_attempts)
        self.reset()

    def reset(self) -> None:
        self.path: list[tuple[float, float]] = []
        self.path_lengths: list[float] = []
        self.target: tuple[float, float] | None = None
        self.subgoal: tuple[float, float] | None = None
        self.path_goal: tuple[float, float] | None = None
        self.path_anchor_points: list[tuple[float, float]] = []
        self.path_kind = "none"
        self.last_plan_ms = 0
        self.last_click_ms = 0
        self.last_click_target: tuple[float, float] | None = None
        self.last_progress_value: float | None = None
        self.last_progress_ms = 0
        self.recover_attempts = 0
        self.probe_index = 0
        self.force_replan = False
        self.final_goal_key: tuple[int, int] | None = None
        self.final_goal_since_ms = 0

    def step(
        self,
        *,
        task_id: str,
        current_pos,
        target_pos,
        wall_map,
        pathfinder,
        explored_map,
        now_ms: int,
        lookahead_distance: float,
        route_context=None,
        soft_anchors=None,
        force_repeat_click: bool = False,
        click_cooldown_ms: int | None = None,
    ) -> MovementStep | None:
        current = _float_point(current_pos)
        target = _float_point(target_pos)
        self._ensure_path(
            task_id=task_id,
            current_pos=current,
            target_pos=target,
            wall_map=wall_map,
            pathfinder=pathfinder,
            explored_map=explored_map,
            now_ms=int(now_ms),
            route_context=route_context,
            soft_anchors=soft_anchors,
        )
        if not self.path or len(self.path) < 2:
            nav_log(
                "nav movement path unavailable",
                task=task_id,
                player=_int_point(current),
                target=_int_point(target),
            )
            return None

        projection = project_point_onto_path(current, self.path, self.path_lengths)
        if projection is None:
            self.last_plan_ms = 0
            nav_log(
                "nav movement projection failed",
                task=task_id,
                player=_int_point(current),
                target=_int_point(target),
            )
            return None

        subgoal = interpolate_by_distance(
            self.path,
            self.path_lengths,
            float(projection["distance"]) + float(lookahead_distance),
        )
        if subgoal is None:
            subgoal = self.path[-1]
        self.subgoal = _float_point(subgoal)

        deviation = float(projection["distance_to_path"])
        final_goal_click = self._should_use_exact_path_goal_click(current)
        base_click_cooldown_ms = (
            self.click_cooldown_ms
            if click_cooldown_ms is None
            else max(0, int(click_cooldown_ms))
        )
        if final_goal_click:
            self.subgoal = _float_point(self.path_goal)
            goal_key = _int_point(self.subgoal)
            if self.final_goal_key != goal_key:
                self.final_goal_key = goal_key
                self.final_goal_since_ms = int(now_ms)
            # Near an anchor, normal movement clicks are too large because the
            # screen min radius is applied later. Click the mapped anchor point
            # and give the character a short settle window before any recovery.
            effective_cooldown_ms = max(base_click_cooldown_ms, 650)
        else:
            self.final_goal_key = None
            self.final_goal_since_ms = 0
            effective_cooldown_ms = base_click_cooldown_ms

        cooldown_ready = self.last_click_ms == 0 or int(now_ms) - self.last_click_ms >= effective_cooldown_ms
        suppress_recovery = final_goal_click and int(now_ms) - int(self.final_goal_since_ms) < 2200
        stuck = False if suppress_recovery else self._is_stuck(float(projection["distance"]), int(now_ms))
        recovery_subgoal = None
        stuck_replan_requested = False
        if stuck and cooldown_ready and self.recover_attempts < self.max_recover_attempts:
            recovery_target = self._active_recovery_target(target)
            recovery_subgoal = self._recovery_probe(current, recovery_target, attempt=self.recover_attempts)
            self.subgoal = _float_point(recovery_subgoal)
            self.recover_attempts += 1
            nav_log(
                "nav movement stuck recovery",
                task=task_id,
                attempt=self.recover_attempts,
                player=_int_point(current),
                target=_int_point(target),
                recovery_target=_int_point(recovery_target),
                subgoal=_int_point(self.subgoal),
                path_kind=self.path_kind,
                progress=round(float(projection["distance"]), 1),
                deviation=round(float(deviation), 1),
            )
        elif stuck and cooldown_ready:
            self.force_replan = True
            self.last_progress_value = None
            self.last_progress_ms = int(now_ms)
            self.recover_attempts = 0
            stuck_replan_requested = True
            nav_log(
                "nav movement stuck replan",
                task=task_id,
                player=_int_point(current),
                target=_int_point(target),
                path_kind=self.path_kind,
                progress=round(float(projection["distance"]), 1),
                deviation=round(float(deviation), 1),
            )

        target_delta = (
            float("inf")
            if self.last_click_target is None
            else point_distance(self.last_click_target, self.subgoal)
        )
        active_goal_pending = self._active_path_goal_pending(current)
        can_use_regular_click = (
            not stuck_replan_requested
            and (
                bool(force_repeat_click)
                or final_goal_click
                or active_goal_pending
                or self.last_click_target is None
                or target_delta >= self.min_click_target_delta
                or deviation >= self.path_deviation_threshold * 0.5
            )
        )
        should_click = cooldown_ready and (
            recovery_subgoal is not None
            or can_use_regular_click
        )
        if final_goal_click and should_click:
            nav_log(
                "nav movement exact path-goal click",
                task=task_id,
                path_kind=self.path_kind,
                player=_int_point(current),
                path_goal=_int_point(self.path_goal),
                distance=round(float(point_distance(current, self.path_goal)), 1),
                arrival_radius=round(float(self.anchor_arrival_radius), 1),
                cooldown_ms=effective_cooldown_ms,
            )

        return MovementStep(
            path=list(self.path),
            subgoal=self.subgoal,
            path_kind=self.path_kind,
            should_click=bool(should_click),
            force_click_target=bool(final_goal_click and recovery_subgoal is None),
            deviation=deviation,
            reason="move along shared executor",
            task_id=str(task_id),
            target_pos=target,
        )

    def record_click(self, *, now_ms: int, subgoal) -> None:
        self.last_click_ms = int(now_ms)
        self.last_click_target = _float_point(subgoal)

    def _ensure_path(
        self,
        *,
        task_id: str,
        current_pos,
        target_pos,
        wall_map,
        pathfinder,
        explored_map,
        now_ms: int,
        route_context=None,
        soft_anchors=None,
    ) -> None:
        target = _float_point(target_pos)
        target_changed = self.target is None or point_distance(self.target, target) > 12.0
        needs_plan = self.force_replan or target_changed or not self.path or len(self.path) < 2

        if not needs_plan:
            if self.path_kind in {"anchor_step", "anchor_probe", "fallback"} and self.path_goal is not None:
                if point_distance(current_pos, self.path_goal) <= self.anchor_arrival_radius:
                    needs_plan = True
            projection = project_point_onto_path(current_pos, self.path, self.path_lengths)
            if not needs_plan and (projection is None or float(projection["distance_to_path"]) > self.path_deviation_threshold):
                needs_plan = True
            elif not needs_plan and self.path_kind == "fallback" and now_ms - self.last_plan_ms >= 650:
                needs_plan = True

        if not needs_plan:
            return
        if not target_changed and self.last_plan_ms and now_ms - self.last_plan_ms < 260:
            return

        path, lengths, path_kind = self._plan_path(
            current_pos,
            target,
            wall_map,
            pathfinder,
            explored_map,
            route_context=route_context,
            soft_anchors=soft_anchors,
        )
        self.path = path
        self.path_lengths = lengths
        self.target = target
        self.path_kind = path_kind
        self.path_goal = path[-1] if path else None
        self.last_plan_ms = int(now_ms)
        self.force_replan = False
        self.subgoal = None
        self.last_progress_value = None
        self.last_progress_ms = int(now_ms)
        self.recover_attempts = 0
        self.final_goal_key = None
        self.final_goal_since_ms = 0
        next_anchor = self.path_anchor_points[0] if getattr(self, "path_anchor_points", None) else None
        nav_log(
            "nav movement planned",
            task=task_id,
            target=_int_point(target),
            path_kind=path_kind,
            path_goal=_int_point(self.path_goal) if self.path_goal else None,
            next_anchor=_int_point(next_anchor) if next_anchor else None,
            anchor_count=len(getattr(self, "path_anchor_points", []) or []),
            path_points=len(path),
            player=_int_point(current_pos),
            direct_distance=round(float(point_distance(current_pos, target)), 1),
        )

    def _plan_path(
        self,
        current_pos,
        target_pos,
        wall_map,
        pathfinder,
        explored_map,
        *,
        route_context=None,
        soft_anchors=None,
    ):
        current = _int_point(current_pos)
        target = _int_point(target_pos)
        anchors = self._anchors_for_path(
            current_pos,
            target_pos,
            route_context=route_context,
            soft_anchors=soft_anchors,
        )

        path_result = None
        if wall_map is not None and pathfinder is not None:
            path_result = plan_path_with_optional_anchors(
                wall_map=wall_map,
                pathfinder=pathfinder,
                start_pos=current,
                target_pos=target,
                explored_map=explored_map,
                anchors=anchors,
            )

        if path_result and path_result.path:
            self.path_anchor_points = [_float_point(point) for point in path_result.anchor_points]
            path = [_float_point(point) for point in remove_collinear_points(path_result.path)]
            if len(path) == 1:
                path.append(_float_point(target_pos))
            return path, build_cumulative_lengths(path), path_result.path_kind

        raw_path = None
        if wall_map is not None and pathfinder is not None and not anchors:
            raw_path = pathfinder.find_path(
                wall_map,
                current,
                target,
                explored_map=explored_map,
            )

        if raw_path:
            self.path_anchor_points = []
            path = [_float_point(point) for point in remove_collinear_points(raw_path)]
            if len(path) == 1:
                path.append(_float_point(target_pos))
            return path, build_cumulative_lengths(path), "planned"

        self.path_anchor_points = []
        probe = self._local_probe(current_pos, target_pos)
        path = [_float_point(current_pos), _float_point(probe)]
        return path, build_cumulative_lengths(path), "fallback"

    def _anchors_for_path(self, current_pos, target_pos, *, route_context=None, soft_anchors=None):
        if route_context is not None:
            anchors = route_context.corridor_anchors(
                current_pos,
                target_pos,
                reached_radius=self.anchor_arrival_radius,
                target_margin=max(36.0, self.anchor_arrival_radius),
            )
            if anchors:
                return anchors
        return list(soft_anchors or [])

    def _active_path_goal_pending(self, current_pos) -> bool:
        if self.path_goal is None:
            return False
        if self.path_kind not in {"anchor_step", "anchor_probe", "fallback"}:
            return False
        return point_distance(current_pos, self.path_goal) > self.anchor_arrival_radius

    def _should_use_exact_path_goal_click(self, current_pos) -> bool:
        if self.path_goal is None:
            return False
        if self.path_kind not in {"anchor_step", "anchor_probe"}:
            return False
        distance = point_distance(current_pos, self.path_goal)
        if distance <= self.anchor_arrival_radius:
            return False
        exact_click_radius = max(self.anchor_arrival_radius * 3.0, self.anchor_arrival_radius + 36.0)
        return distance <= exact_click_radius

    def _active_recovery_target(self, final_target):
        if self.path_goal is not None and self.path_kind in {"anchor_step", "anchor_probe", "fallback"}:
            return self.path_goal
        return final_target

    def _local_probe(self, current_pos, target_pos):
        distance = point_distance(current_pos, target_pos)
        if distance <= 1e-6:
            return _float_point(target_pos)

        dx = float(target_pos[0]) - float(current_pos[0])
        dy = float(target_pos[1]) - float(current_pos[1])
        ux = dx / distance
        uy = dy / distance
        px = -uy
        py = ux
        side_pattern = (0.0, -1.0, 1.0)
        side = side_pattern[self.probe_index % len(side_pattern)]
        self.probe_index += 1
        forward = min(distance, 84.0)
        lateral = 44.0 if side else 0.0
        return (
            float(current_pos[0]) + ux * forward + px * side * lateral,
            float(current_pos[1]) + uy * forward + py * side * lateral,
        )

    def _is_stuck(self, current_progress: float, now_ms: int) -> bool:
        if self.last_progress_value is None or self.last_progress_ms <= 0:
            self.last_progress_value = float(current_progress)
            self.last_progress_ms = int(now_ms)
            return False

        if float(current_progress) - float(self.last_progress_value) >= self.min_progress_delta:
            self.last_progress_value = float(current_progress)
            self.last_progress_ms = int(now_ms)
            self.recover_attempts = 0
            return False

        return int(now_ms) - int(self.last_progress_ms) >= self.progress_timeout_ms

    def _recovery_probe(self, current_pos, target_pos, *, attempt: int):
        distance = point_distance(current_pos, target_pos)
        if distance <= 1e-6:
            return _float_point(target_pos)

        dx = float(target_pos[0]) - float(current_pos[0])
        dy = float(target_pos[1]) - float(current_pos[1])
        ux = dx / distance
        uy = dy / distance
        px = -uy
        py = ux
        side_pattern = (-1.0, 1.0, 0.0)
        side = side_pattern[int(attempt) % len(side_pattern)]
        forward = min(max(self.anchor_arrival_radius * 1.6, 36.0), 72.0)
        lateral = 58.0 if side else 0.0
        return (
            float(current_pos[0]) + ux * forward + px * side * lateral,
            float(current_pos[1]) + uy * forward + py * side * lateral,
        )


def _float_point(point) -> tuple[float, float]:
    return (float(point[0]), float(point[1]))


def _int_point(point) -> tuple[int, int]:
    return (int(round(float(point[0]))), int(round(float(point[1]))))
