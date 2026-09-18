from __future__ import annotations

from .models import MovementStep
from .movement.path_maintenance import ensure_movement_path
from .movement.path_planner import (
    active_path_goal_pending,
    active_recovery_target,
    anchors_for_path,
    plan_movement_path,
    should_use_exact_path_goal_click,
)
from .movement.pipeline import movement_step
from .movement.recovery import is_movement_stuck, local_probe, recovery_probe
from .movement.utils import float_point, int_point


class MovementExecutor:
    """Shared A* lookahead mover for route and event map targets."""

    def __init__(
        self,
        *,
        click_cooldown_ms: int = 260,
        min_click_target_delta: float = 8.0,
        arrival_radius: float = 26.0,
        anchor_arrival_radius: float | None = None,
        route_anchor_target_margin: float = 36.0,
        exact_goal_click_enabled: bool = True,
        exact_goal_click_radius: float = 90.0,
        exact_goal_click_cooldown_ms: int = 260,
        exact_goal_recovery_suppress_ms: int = 1200,
        replan_throttle_ms: int = 260,
        fallback_replan_interval_ms: int = 650,
        path_deviation_threshold: float = 96.0,
        min_progress_delta: float = 12.0,
        progress_timeout_ms: int = 1800,
        max_recover_attempts: int = 2,
        local_probe_forward_distance: float = 84.0,
        local_probe_lateral_distance: float = 44.0,
        recovery_probe_forward_min: float = 36.0,
        recovery_probe_forward_max: float = 72.0,
        recovery_probe_forward_multiplier: float = 1.6,
        recovery_probe_lateral_distance: float = 58.0,
    ):
        self.click_cooldown_ms = int(click_cooldown_ms)
        self.min_click_target_delta = float(min_click_target_delta)
        self.arrival_radius = float(arrival_radius)
        self.anchor_arrival_radius = float(anchor_arrival_radius if anchor_arrival_radius is not None else arrival_radius)
        self.route_anchor_target_margin = float(route_anchor_target_margin)
        self.exact_goal_click_enabled = bool(exact_goal_click_enabled)
        self.exact_goal_click_radius = float(exact_goal_click_radius)
        self.exact_goal_click_cooldown_ms = int(exact_goal_click_cooldown_ms)
        self.exact_goal_recovery_suppress_ms = int(exact_goal_recovery_suppress_ms)
        self.replan_throttle_ms = int(replan_throttle_ms)
        self.fallback_replan_interval_ms = int(fallback_replan_interval_ms)
        self.path_deviation_threshold = float(path_deviation_threshold)
        self.min_progress_delta = float(min_progress_delta)
        self.progress_timeout_ms = int(progress_timeout_ms)
        self.max_recover_attempts = int(max_recover_attempts)
        self.local_probe_forward_distance = float(local_probe_forward_distance)
        self.local_probe_lateral_distance = float(local_probe_lateral_distance)
        self.recovery_probe_forward_min = float(recovery_probe_forward_min)
        self.recovery_probe_forward_max = float(recovery_probe_forward_max)
        self.recovery_probe_forward_multiplier = float(recovery_probe_forward_multiplier)
        self.recovery_probe_lateral_distance = float(recovery_probe_lateral_distance)
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
        goal_stop_radius: float | None = None,
    ) -> MovementStep | None:
        return movement_step(
            self,
            task_id=task_id,
            current_pos=current_pos,
            target_pos=target_pos,
            wall_map=wall_map,
            pathfinder=pathfinder,
            explored_map=explored_map,
            now_ms=now_ms,
            lookahead_distance=lookahead_distance,
            route_context=route_context,
            soft_anchors=soft_anchors,
            force_repeat_click=force_repeat_click,
            click_cooldown_ms=click_cooldown_ms,
            goal_stop_radius=goal_stop_radius,
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
        return ensure_movement_path(
            self,
            task_id=task_id,
            current_pos=current_pos,
            target_pos=target_pos,
            wall_map=wall_map,
            pathfinder=pathfinder,
            explored_map=explored_map,
            now_ms=now_ms,
            route_context=route_context,
            soft_anchors=soft_anchors,
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
        return plan_movement_path(
            self,
            current_pos,
            target_pos,
            wall_map,
            pathfinder,
            explored_map,
            route_context=route_context,
            soft_anchors=soft_anchors,
        )

    def _anchors_for_path(self, current_pos, target_pos, *, route_context=None, soft_anchors=None):
        return anchors_for_path(
            self,
            current_pos,
            target_pos,
            route_context=route_context,
            soft_anchors=soft_anchors,
        )

    def _active_path_goal_pending(self, current_pos) -> bool:
        return active_path_goal_pending(self, current_pos)

    def _should_use_exact_path_goal_click(self, current_pos, *, goal_stop_radius: float | None = None) -> bool:
        return should_use_exact_path_goal_click(self, current_pos, goal_stop_radius=goal_stop_radius)

    def _active_recovery_target(self, final_target):
        return active_recovery_target(self, final_target)

    def _local_probe(self, current_pos, target_pos):
        return local_probe(self, current_pos, target_pos)

    def _is_stuck(self, current_progress: float, now_ms: int) -> bool:
        return is_movement_stuck(self, current_progress, now_ms)

    def _recovery_probe(self, current_pos, target_pos, *, attempt: int):
        return recovery_probe(self, current_pos, target_pos, attempt=attempt)


def _float_point(point) -> tuple[float, float]:
    return float_point(point)


def _int_point(point) -> tuple[int, int]:
    return int_point(point)
