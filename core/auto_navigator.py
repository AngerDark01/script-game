import copy
from collections import deque

from .path_utils import (
    build_cumulative_lengths,
    interpolate_by_distance,
    is_inside_exit_region,
    point_distance,
    project_point_onto_path,
    remove_collinear_points,
)


class AutoNavigator:
    """Runtime controller for segment-based click-to-move navigation."""

    def __init__(self):
        self.min_confidence = 0.58
        self.stable_confidence = 0.72
        self.required_stable_frames = 3
        self.acquire_radius = 8.0
        self.max_jump_distance = 160.0
        self.control_alpha = 0.35
        self.default_lookahead_distance = 72.0
        self.arrival_radius = 26.0
        self.path_deviation_threshold = 72.0
        self.click_cooldown_ms = 260
        self.min_click_target_delta = 8.0
        self.min_progress_delta = 12.0
        self.progress_timeout_ms = 1800
        self.replan_cooldown_ms = 1200
        self.short_lost_timeout_ms = 900
        self.max_recover_attempts = 2
        self.prefer_direct_guidance = False
        self.route_snap_max_distance = 240.0
        self.route_snap_segment_threshold = 0.25
        self.route_marker_arrival_factor = 1.25
        self.recovery_probe_distance = 54.0
        self.recovery_probe_side_distance = 58.0
        self.direct_fallback_distance = 96.0
        self.direct_fallback_side_distance = 42.0

        self.route = None
        self.paused = False
        self.pause_reason = None

        self.reset_runtime(keep_route=True)

    def configure(self, click_cooldown_ms=None, min_click_target_delta=None, prefer_direct_guidance=None):
        if click_cooldown_ms is not None:
            self.click_cooldown_ms = max(120, int(click_cooldown_ms))
        if min_click_target_delta is not None:
            self.min_click_target_delta = max(0.0, float(min_click_target_delta))
        if prefer_direct_guidance is not None:
            self.prefer_direct_guidance = bool(prefer_direct_guidance)

    def reset_runtime(self, keep_route: bool = True):
        if not keep_route:
            self.route = None
        self.active = False
        self.state = "IDLE"
        self.required_index = 0
        self.guide_index = 0
        self.acquire_window = deque(maxlen=5)
        self.raw_pos = None
        self.trusted_pos = None
        self.control_pos = None
        self.current_path = []
        self.current_path_lengths = []
        self.current_target = None
        self.current_target_kind = "none"
        self.last_click_ms = None
        self.last_click_target = None
        self.last_progress_value = None
        self.last_progress_ms = None
        self.last_replan_ms = None
        self.short_lost_since_ms = None
        self.segment_arrival_frames = 0
        self.recover_attempts = 0
        self.route_alignment_done = False
        self.current_path_kind = "none"
        self.direct_fallback_attempts = 0

    def load_route(self, route: dict | None):
        self.route = copy.deepcopy(route) if route else None
        self.reset_runtime(keep_route=True)

    def start(self) -> bool:
        if not self.has_valid_route():
            return False
        self.active = True
        self.state = "ACQUIRE"
        self.acquire_window.clear()
        self.short_lost_since_ms = None
        return True

    def stop(self):
        self.reset_runtime(keep_route=True)

    def pause(self, reason):
        self.paused = True
        self.pause_reason = reason

    def resume(self):
        self.paused = False
        self.pause_reason = None

    def notify_external_interrupt(self):
        self.pause("external_interrupt")

    def reset_with_current_position(self, position):
        if position is not None:
            self.raw_pos = tuple(position)
            self.trusted_pos = tuple(position)
            self.control_pos = tuple(position)
        self.acquire_window.clear()
        if self.active:
            self.state = "PLAN_SEGMENT"
            self.current_path = []
            self.current_path_lengths = []
            self.route_alignment_done = False
            self.current_path_kind = "none"
            self.current_target_kind = "none"

    def has_valid_route(self) -> bool:
        return bool(self.route and self.route.get("exit_region"))

    def required_points(self):
        if not self.route:
            return []
        return [
            (float(point[0]), float(point[1]))
            for point in self.route.get("required_points", [])
        ]

    def guide_points(self):
        if not self.route:
            return []
        return [
            (float(point[0]), float(point[1]))
            for point in self.route.get("guide_points", [])
        ]

    def has_pending_required_points(self) -> bool:
        return self.required_index < len(self.required_points())

    def route_points(self):
        if not self.has_valid_route():
            return []
        points = self.guide_points()
        center = self.route["exit_region"]["center"]
        points.append((float(center[0]), float(center[1])))
        return points

    def _exit_center(self):
        center = self.route["exit_region"]["center"]
        return (float(center[0]), float(center[1]))

    def _route_progress_for_point(self, point):
        points = self.route_points()
        if not points:
            return None

        lengths = build_cumulative_lengths(points)
        projection = project_point_onto_path(point, points, lengths)
        if projection is None:
            return None
        return float(projection["distance"])

    def _guide_progress(self, guide_index):
        guide_points = self.guide_points()
        if guide_index >= len(guide_points):
            return None

        lengths = build_cumulative_lengths(self.route_points())
        if guide_index >= len(lengths):
            return None
        return float(lengths[guide_index])

    def _guide_index_limit_for_current_required(self):
        if not self.has_pending_required_points():
            return len(self.guide_points())

        required = self.required_points()[self.required_index]
        required_progress = self._route_progress_for_point(required)
        if required_progress is None:
            return self.guide_index

        guide_points = self.guide_points()
        lengths = build_cumulative_lengths(self.route_points())
        for index in range(len(guide_points)):
            if index < len(lengths) and lengths[index] >= required_progress:
                return index
        return len(guide_points)

    def _select_segment_target(self):
        if not self.has_valid_route():
            return "none", None

        required_points = self.required_points()
        guide_points = self.guide_points()
        has_required = self.required_index < len(required_points)
        has_guide = self.guide_index < len(guide_points)

        if has_required and has_guide:
            required = required_points[self.required_index]
            guide = guide_points[self.guide_index]
            required_progress = self._route_progress_for_point(required)
            guide_progress = self._guide_progress(self.guide_index)
            if (
                required_progress is None
                or guide_progress is None
                or required_progress <= guide_progress
            ):
                return "required", required
            return "guide", guide

        if has_required:
            return "required", required_points[self.required_index]

        if has_guide:
            return "guide", guide_points[self.guide_index]

        return "exit", self._exit_center()

    def current_segment_target_kind(self):
        return self._select_segment_target()[0]

    def current_segment_target(self):
        return self._select_segment_target()[1]

    def current_segment_is_exit(self) -> bool:
        return self.current_segment_target_kind() == "exit"

    def _set_direct_segment_path(self, target):
        self.current_path = [
            (float(self.control_pos[0]), float(self.control_pos[1])),
            (float(target[0]), float(target[1])),
        ]
        self.current_path_kind = "direct"

    def _local_probe_towards_target(self, target, attempt: int = 0, forward_distance=None, side_distance=None):
        if self.control_pos is None:
            return target

        dx = float(target[0]) - float(self.control_pos[0])
        dy = float(target[1]) - float(self.control_pos[1])
        distance = point_distance(self.control_pos, target)
        if distance <= 1e-6:
            return target

        ux = dx / distance
        uy = dy / distance
        px = -uy
        py = ux
        pattern = (0.0, -1.0, 1.0)
        side = pattern[attempt % len(pattern)]
        forward = min(
            distance,
            float(forward_distance if forward_distance is not None else self.direct_fallback_distance),
        )
        lateral = float(side_distance if side_distance is not None else self.direct_fallback_side_distance)
        return (
            float(self.control_pos[0]) + ux * forward + px * side * lateral,
            float(self.control_pos[1]) + uy * forward + py * side * lateral,
        )

    def _set_local_fallback_path(self, target):
        probe = self._local_probe_towards_target(target, attempt=self.direct_fallback_attempts)
        self.direct_fallback_attempts += 1
        self.current_path = [
            (float(self.control_pos[0]), float(self.control_pos[1])),
            (float(probe[0]), float(probe[1])),
        ]
        self.current_path_kind = "local_fallback"

    def _align_route_to_current_position(self):
        """Attach to the nearest sensible route progress, then continue forward."""
        if self.route_alignment_done or self.control_pos is None:
            return False
        self.route_alignment_done = True

        guide_points = self.guide_points()
        points = self.route_points()
        if not points or not guide_points:
            return False

        arrival_distance = self.arrival_radius * self.route_marker_arrival_factor
        nearest_index = min(
            range(len(points)),
            key=lambda index: point_distance(self.control_pos, points[index]),
        )
        nearest_distance = point_distance(self.control_pos, points[nearest_index])
        candidate_index = nearest_index

        segment_candidate = self._candidate_index_from_nearest_route_segment(points)
        if segment_candidate is not None:
            candidate_index = segment_candidate

        if nearest_distance <= arrival_distance:
            candidate_index += 1

        candidate_index = min(candidate_index, self._guide_index_limit_for_current_required())
        candidate_index = min(max(candidate_index, 0), len(guide_points))
        if candidate_index > self.guide_index:
            self.guide_index = candidate_index
            self.current_path = []
            self.current_path_lengths = []
            self.current_target = None
            self.current_target_kind = "none"
            self.current_path_kind = "none"
            return True
        return False

    def _candidate_index_from_nearest_route_segment(self, points):
        if len(points) < 2 or self.control_pos is None:
            return None

        px, py = self.control_pos
        best = None
        for index in range(len(points) - 1):
            ax, ay = points[index]
            bx, by = points[index + 1]
            vx = bx - ax
            vy = by - ay
            length_sq = vx * vx + vy * vy
            if length_sq <= 1e-9:
                continue
            raw_t = ((px - ax) * vx + (py - ay) * vy) / length_sq
            t = max(0.0, min(1.0, raw_t))
            cx = ax + vx * t
            cy = ay + vy * t
            distance = point_distance((px, py), (cx, cy))
            if best is None or distance < best["distance"]:
                best = {"segment": index, "t": t, "distance": distance}

        if best is None or best["distance"] > self.route_snap_max_distance:
            return None
        if best["t"] <= self.route_snap_segment_threshold:
            return best["segment"]
        return best["segment"] + 1

    def observe_localization(self, pos, confidence: float) -> bool:
        self.raw_pos = tuple(pos) if pos is not None else None
        if pos is None or confidence < self.min_confidence:
            return False

        candidate = (float(pos[0]), float(pos[1]))
        if self.trusted_pos is not None:
            jump = point_distance(candidate, self.trusted_pos)
            if jump > self.max_jump_distance and confidence < 0.9:
                return False

        self.trusted_pos = candidate
        if self.control_pos is None:
            self.control_pos = candidate
        else:
            alpha = 0.5 if confidence >= 0.9 else self.control_alpha
            self.control_pos = (
                self.control_pos[0] + (candidate[0] - self.control_pos[0]) * alpha,
                self.control_pos[1] + (candidate[1] - self.control_pos[1]) * alpha,
            )

        if confidence >= self.stable_confidence:
            self.acquire_window.append(candidate)
        else:
            self.acquire_window.clear()
        return True

    def has_stable_lock(self) -> bool:
        if len(self.acquire_window) < self.required_stable_frames:
            return False

        xs = [point[0] for point in self.acquire_window]
        ys = [point[1] for point in self.acquire_window]
        return (max(xs) - min(xs)) <= self.acquire_radius and (max(ys) - min(ys)) <= self.acquire_radius

    def should_issue_click(self, now_ms: int, target=None, deviation: float = 0.0, force: bool = False) -> bool:
        if self.last_click_ms is not None and now_ms - self.last_click_ms < self.click_cooldown_ms:
            return False
        if force or target is None or self.last_click_target is None:
            return True

        target_delta = point_distance(target, self.last_click_target)
        return target_delta >= self.min_click_target_delta or deviation >= self.path_deviation_threshold * 0.6

    def is_stuck(self, current_progress: float, now_ms: int) -> bool:
        if self.last_progress_value is None or self.last_progress_ms is None:
            self.last_progress_value = current_progress
            self.last_progress_ms = now_ms
            return False

        if current_progress - self.last_progress_value >= self.min_progress_delta:
            self.last_progress_value = current_progress
            self.last_progress_ms = now_ms
            return False

        return now_ms - self.last_progress_ms >= self.progress_timeout_ms

    def _can_replan(self, now_ms: int) -> bool:
        return self.last_replan_ms is None or now_ms - self.last_replan_ms >= self.replan_cooldown_ms

    def _build_result(self, message="", move_target=None, subtype="status", issued_click: bool = False):
        return {
            "type": subtype,
            "state": self.state,
            "message": message,
            "path": list(self.current_path),
            "subgoal": move_target,
            "player_pos": self.control_pos,
            "target_pos": move_target,
            "segment_target": self.current_target,
            "target_kind": self.current_target_kind,
            "issued_click": bool(issued_click),
            "path_kind": self.current_path_kind,
            "required_index": self.required_index,
            "required_total": len(self.required_points()),
            "guide_index": self.guide_index,
            "guide_total": len(self.guide_points()),
        }

    def _handle_missing_localization(self, now_ms: int):
        if self.active and self.state in {"PLAN_SEGMENT", "FOLLOW_SEGMENT", "STUCK_RECOVER"}:
            if self.short_lost_since_ms is None:
                self.short_lost_since_ms = now_ms
            self.state = "SHORT_LOST"
            return self._build_result("定位短暂丢失，等待稳定恢复")
        return self._build_result("等待定位")

    def _advance_segment(self):
        target_kind = self.current_target_kind or self.current_segment_target_kind()
        if target_kind == "exit":
            self.state = "ARRIVED"
            self.active = False
            return self._build_result("已到达出口", subtype="arrived")

        if target_kind == "required":
            self.required_index += 1
            self.route_alignment_done = False
            message = "必经点已到达，规划下一个必经点"
            if not self.has_pending_required_points():
                message = "所有必经点已完成，继续后续路线"
        elif target_kind == "guide":
            self.guide_index += 1
            message = "途经点已到达，规划下一段"
        else:
            self.state = "FAILED"
            self.active = False
            return self._build_result("当前目标类型无效", subtype="failed")

        self.current_path = []
        self.current_path_lengths = []
        self.current_target = None
        self.current_target_kind = "none"
        self.current_path_kind = "none"
        self.segment_arrival_frames = 0
        self.direct_fallback_attempts = 0
        self.state = "PLAN_SEGMENT"
        return self._build_result(message)

    def _target_reached(self):
        if self.control_pos is None:
            self.segment_arrival_frames = 0
            return False

        if self.current_target_kind == "exit":
            if is_inside_exit_region(self.control_pos, self.route.get("exit_region")):
                self.segment_arrival_frames += 1
            else:
                self.segment_arrival_frames = 0
        else:
            target = self.current_target
            if point_distance(self.control_pos, target) <= self.arrival_radius:
                self.segment_arrival_frames += 1
            else:
                self.segment_arrival_frames = 0

        return self.segment_arrival_frames >= 2

    def _plan_segment(self, wall_map, explored_map, pathfinder, now_ms: int):
        route_aligned = self._align_route_to_current_position()
        target_kind, target = self._select_segment_target()
        if target is None:
            self.state = "FAILED"
            self.active = False
            return self._build_result("路线数据无效", subtype="failed")

        if self.control_pos is None:
            self.state = "FAILED"
            self.active = False
            return self._build_result("无法取得当前位置", subtype="failed")

        self.current_target = target
        self.current_target_kind = target_kind
        raw_path = None
        used_direct_fallback = False
        if self.prefer_direct_guidance:
            self._set_direct_segment_path(target)
        elif wall_map is not None and pathfinder is not None:
            raw_path = pathfinder.find_path(
                wall_map,
                (int(round(self.control_pos[0])), int(round(self.control_pos[1]))),
                (int(round(target[0])), int(round(target[1]))),
                explored_map=explored_map,
            )

        if not self.prefer_direct_guidance and raw_path:
            # Do not shortcut with only wall_map here. A shortcut can cross
            # unexplored space even though A* planned around it.
            self.current_path = [tuple(map(float, point)) for point in remove_collinear_points(raw_path)]
            if len(self.current_path) < 2:
                self.current_path = [tuple(map(float, raw_path[0])), tuple(map(float, raw_path[-1]))]
            self.current_path_kind = "planned"
            self.direct_fallback_attempts = 0
        elif not self.prefer_direct_guidance:
            # A* failure should not make us click the final target through walls.
            # Use a short local probe toward the target, then re-plan from there.
            used_direct_fallback = True
            self._set_local_fallback_path(target)

        self.current_path_lengths = build_cumulative_lengths(self.current_path)
        self.state = "FOLLOW_SEGMENT"
        self.last_replan_ms = now_ms
        self.last_progress_value = None
        self.last_progress_ms = now_ms
        self.recover_attempts = 0
        self.segment_arrival_frames = 0
        if route_aligned:
            return self._build_result(f"已按当前位置跳到路线点 {self.guide_index + 1}")
        if self.prefer_direct_guidance:
            return self._build_result("使用直线点击引导")
        if used_direct_fallback:
            return self._build_result("A*失败，改用局部脱困点")
        return self._build_result("路径规划完成")

    def _follow_segment(self, now_ms: int, lookahead_distance: float):
        if not self.current_path:
            self.state = "PLAN_SEGMENT"
            return self._build_result("缺少当前路径，重新规划")

        if self._target_reached():
            return self._advance_segment()

        if self.current_path_kind == "local_fallback":
            fallback_end = self.current_path[-1]
            if point_distance(self.control_pos, fallback_end) <= self.arrival_radius:
                self.current_path = []
                self.current_path_lengths = []
                self.current_path_kind = "none"
                self.state = "PLAN_SEGMENT"
                return self._build_result("临时脱困点已到达，重新规划")

        projection = project_point_onto_path(self.control_pos, self.current_path, self.current_path_lengths)
        if projection is None:
            self.state = "PLAN_SEGMENT"
            return self._build_result("路径投影失败，重新规划")

        progress = projection["distance"]
        deviation = projection["distance_to_path"]
        if deviation > self.path_deviation_threshold and self._can_replan(now_ms):
            self.state = "PLAN_SEGMENT"
            return self._build_result("偏离路径，重新规划")

        if self.is_stuck(progress, now_ms):
            if self.current_path_kind == "local_fallback" and self._can_replan(now_ms):
                self.current_path = []
                self.current_path_lengths = []
                self.current_path_kind = "none"
                self.state = "PLAN_SEGMENT"
                return self._build_result("临时脱困无进展，重新规划")
            if self.recover_attempts < self.max_recover_attempts:
                self.state = "STUCK_RECOVER"
                return self._build_result("进度停滞，尝试保守恢复")
            if self._can_replan(now_ms):
                self.state = "PLAN_SEGMENT"
                return self._build_result("进度停滞，重新规划")
            self.state = "FAILED"
            self.active = False
            return self._build_result("连续恢复失败", subtype="failed")

        subgoal = interpolate_by_distance(
            self.current_path,
            self.current_path_lengths,
            progress + lookahead_distance,
        )
        if subgoal is None:
            subgoal = self.current_target

        if self.should_issue_click(now_ms, target=subgoal, deviation=deviation):
            self.last_click_ms = now_ms
            self.last_click_target = subgoal
            return self._build_result("沿路径推进", move_target=subgoal, subtype="move", issued_click=True)

        return self._build_result("保持当前移动", move_target=subgoal, subtype="move")

    def _recovery_probe_subgoal(self):
        if self.control_pos is None or self.current_target is None:
            return self.current_target

        dx = float(self.current_target[0]) - float(self.control_pos[0])
        dy = float(self.current_target[1]) - float(self.control_pos[1])
        distance = point_distance(self.control_pos, self.current_target)
        if distance <= 1e-6:
            return self.current_target

        ux = dx / distance
        uy = dy / distance
        px = -uy
        py = ux
        pattern = (-1.0, 1.0, 0.0)
        side = pattern[self.recover_attempts % len(pattern)]
        forward = min(max(self.default_lookahead_distance * 0.5, 30.0), self.recovery_probe_distance)
        side_distance = self.recovery_probe_side_distance if side else 0.0
        return (
            float(self.control_pos[0]) + ux * forward + px * side * side_distance,
            float(self.control_pos[1]) + uy * forward + py * side * side_distance,
        )

    def _recover(self, now_ms: int, lookahead_distance: float):
        if not self.current_path:
            self.state = "PLAN_SEGMENT"
            return self._build_result("恢复时缺少路径，重新规划")

        subgoal = self._recovery_probe_subgoal()

        if self.should_issue_click(now_ms, target=subgoal, force=True):
            self.last_click_ms = now_ms
            self.last_click_target = subgoal
            self.recover_attempts += 1
            self.state = "FOLLOW_SEGMENT"
            return self._build_result("执行绕障试探点击", move_target=subgoal, subtype="move", issued_click=True)

        if self._can_replan(now_ms):
            self.state = "PLAN_SEGMENT"
            return self._build_result("恢复点击等待后重新规划")

        return self._build_result("等待恢复冷却")

    def update(self, localized_pos, confidence: float, wall_map, pathfinder, now_ms: int, lookahead_distance=None, explored_map=None):
        if self.paused:
            return self._build_result(f"已暂停: {self.pause_reason or 'unknown'}")

        if not self.active:
            return self._build_result("自动导航未启动")

        lookahead = float(lookahead_distance or self.default_lookahead_distance)
        accepted = self.observe_localization(localized_pos, confidence)
        if not accepted:
            return self._handle_missing_localization(now_ms)

        self.short_lost_since_ms = None

        if self.state in {"ACQUIRE", "SHORT_LOST"}:
            if not self.has_stable_lock():
                message = "等待稳定定位" if self.state == "ACQUIRE" else "等待定位恢复稳定"
                return self._build_result(message)
            self.state = "PLAN_SEGMENT"

        if self.state == "PLAN_SEGMENT":
            return self._plan_segment(wall_map, explored_map, pathfinder, now_ms)

        if self.state == "STUCK_RECOVER":
            return self._recover(now_ms, lookahead)

        if self.state == "FOLLOW_SEGMENT":
            return self._follow_segment(now_ms, lookahead)

        if self.state == "ARRIVED":
            return self._build_result("已到达出口", subtype="arrived")

        if self.state == "FAILED":
            return self._build_result("自动导航失败", subtype="failed")

        return self._build_result("等待开始")
