from __future__ import annotations

from dataclasses import dataclass

from core.path_utils import (
    build_cumulative_lengths,
    interpolate_by_distance,
    point_distance,
    project_point_onto_path,
    remove_collinear_points,
)

from .debug import event_log


@dataclass
class EventMoveStep:
    path: list[tuple[float, float]]
    subgoal: tuple[float, float] | None
    path_kind: str
    should_click: bool
    deviation: float = 0.0


class EventPathMover:
    """Reusable A* lookahead mover for map-position event actions."""

    def __init__(self):
        self.reset()

    def reset(self) -> None:
        self.path: list[tuple[float, float]] = []
        self.path_lengths: list[float] = []
        self.target: tuple[float, float] | None = None
        self.subgoal: tuple[float, float] | None = None
        self.path_kind = "none"
        self.last_plan_ms = 0
        self.last_click_ms = 0
        self.last_click_target: tuple[float, float] | None = None
        self.probe_index = 0

    def step(
        self,
        *,
        current_pos,
        target_pos,
        wall_map,
        pathfinder,
        explored_map,
        now_ms: int,
        lookahead_distance: float,
        force_repeat_click: bool = False,
    ) -> EventMoveStep | None:
        current = (float(current_pos[0]), float(current_pos[1]))
        target = (float(target_pos[0]), float(target_pos[1]))
        self._ensure_path(current, target, wall_map, pathfinder, explored_map, int(now_ms))
        if not self.path or len(self.path) < 2:
            event_log(
                "event move path unavailable",
                player=(int(round(current[0])), int(round(current[1]))),
                target=(int(round(target[0])), int(round(target[1]))),
            )
            return None

        projection = project_point_onto_path(current, self.path, self.path_lengths)
        if projection is None:
            self.last_plan_ms = 0
            event_log(
                "event move projection failed",
                player=(int(round(current[0])), int(round(current[1]))),
                target=(int(round(target[0])), int(round(target[1]))),
            )
            return None

        subgoal = interpolate_by_distance(
            self.path,
            self.path_lengths,
            float(projection["distance"]) + float(lookahead_distance),
        )
        if subgoal is None:
            subgoal = self.path[-1]
        self.subgoal = (float(subgoal[0]), float(subgoal[1]))

        deviation = float(projection["distance_to_path"])
        target_delta = (
            float("inf")
            if self.last_click_target is None
            else point_distance(self.last_click_target, self.subgoal)
        )
        cooldown_ready = self.last_click_ms == 0 or int(now_ms) - self.last_click_ms >= 260
        should_click = cooldown_ready and (
            bool(force_repeat_click)
            or
            self.last_click_target is None
            or target_delta >= 8.0
            or deviation >= 48.0
        )

        return EventMoveStep(
            path=list(self.path),
            subgoal=self.subgoal,
            path_kind=self.path_kind,
            should_click=bool(should_click),
            deviation=deviation,
        )

    def record_click(self, *, now_ms: int, current_pos, target_pos, subgoal, deviation: float) -> None:
        self.last_click_ms = int(now_ms)
        self.last_click_target = (float(subgoal[0]), float(subgoal[1]))
        event_log(
            "event move click",
            player=(int(round(float(current_pos[0]))), int(round(float(current_pos[1])))),
            target=(int(round(float(target_pos[0]))), int(round(float(target_pos[1])))),
            subgoal=(int(round(float(subgoal[0]))), int(round(float(subgoal[1])))),
            path_kind=self.path_kind,
            deviation=round(float(deviation), 2),
            path_points=len(self.path),
        )

    def _ensure_path(self, current_pos, target_pos, wall_map, pathfinder, explored_map, now_ms: int) -> None:
        target = (float(target_pos[0]), float(target_pos[1]))
        target_changed = self.target is None or point_distance(self.target, target) > 12.0
        needs_plan = target_changed or not self.path or len(self.path) < 2

        if not needs_plan:
            projection = project_point_onto_path(current_pos, self.path, self.path_lengths)
            if projection is None or float(projection["distance_to_path"]) > 96.0:
                needs_plan = True
            elif self.path_kind == "fallback" and now_ms - self.last_plan_ms >= 650:
                needs_plan = True

        if not needs_plan:
            return

        if not target_changed and self.last_plan_ms and now_ms - self.last_plan_ms < 280:
            return

        path, lengths, path_kind = self._plan_path(current_pos, target, wall_map, pathfinder, explored_map)
        self.path = path
        self.path_lengths = lengths
        self.target = target
        self.path_kind = path_kind
        self.last_plan_ms = int(now_ms)
        self.subgoal = None
        event_log(
            "event path planned",
            target=(int(round(target[0])), int(round(target[1]))),
            path_kind=path_kind,
            path_points=len(path),
            player=(int(round(float(current_pos[0]))), int(round(float(current_pos[1])))),
        )

    def _plan_path(self, current_pos, target_pos, wall_map, pathfinder, explored_map):
        current = (int(round(current_pos[0])), int(round(current_pos[1])))
        target = (int(round(target_pos[0])), int(round(target_pos[1])))
        raw_path = None
        if wall_map is not None and pathfinder is not None:
            raw_path = pathfinder.find_path(
                wall_map,
                current,
                target,
                explored_map=explored_map,
            )

        if raw_path:
            path = [tuple(map(float, point)) for point in remove_collinear_points(raw_path)]
            if len(path) == 1:
                path.append((float(target_pos[0]), float(target_pos[1])))
            return path, build_cumulative_lengths(path), "planned"

        probe = self._local_probe(current_pos, target_pos)
        path = [
            (float(current_pos[0]), float(current_pos[1])),
            (float(probe[0]), float(probe[1])),
        ]
        return path, build_cumulative_lengths(path), "fallback"

    def _local_probe(self, current_pos, target_pos):
        distance = point_distance(current_pos, target_pos)
        if distance <= 1e-6:
            return (float(target_pos[0]), float(target_pos[1]))

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
