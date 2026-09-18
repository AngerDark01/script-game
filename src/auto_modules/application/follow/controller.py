"""One actor's planning/progress/recovery state. Never shares a path with A2."""
from dataclasses import dataclass
from math import isfinite
from auto_modules.core.routing.follow_target import FollowTargetGenerator
from auto_modules.core.routing.follower_planner import FollowerPlanner
from auto_modules.core.routing.vector_tracker import VectorPathTracker
from auto_modules.core.routing.stuck_recovery import ProgressWatchdog, escape_targets
from auto_modules.core.routing.geometry import point_distance


@dataclass(frozen=True)
class MotionDecision:
    vector: tuple[float, float] = (0., 0.)
    valid_for_ms: int = 0
    state: str = 'waiting'
    path: tuple = ()


class FollowerController:
    def __init__(self, walls, *, actor_id, map_id, map_version, lag_distance=15.,
                 ttl_ms=250, downsample_factor=8, arrival_radius=3., recovery_limit=3):
        if not isfinite(lag_distance) or lag_distance < 0 or not 1 <= ttl_ms <= 500 or recovery_limit < 1:
            raise ValueError('invalid follow parameters')
        self.actor_id, self.map_id, self.map_version = actor_id, map_id, map_version
        self.lag_distance, self.ttl_ms, self.recovery_limit = lag_distance, ttl_ms, recovery_limit
        self.planner = FollowerPlanner(walls, downsample_factor=downsample_factor)
        self.tracker = VectorPathTracker(arrival_radius=arrival_radius)
        self.history = FollowTargetGenerator()
        self.progress = ProgressWatchdog()
        self.reset()

    def reset(self):
        self.planner.clear()
        self.history.reset()
        self.progress.reset()
        self.recovery_target = None
        self.recovery_deadline = 0
        self.attempts = 0
        self.recovery_anchor = None
        self.previous_vector = (0., 0.)
        self._leader_session = None

    def _fresh(self, observation, now_ms):
        return (observation is not None and observation.map_id == self.map_id
                and observation.map_version == self.map_version
                and len(observation.position) == 2
                and all(isfinite(v) for v in (*observation.position, observation.confidence, observation.captured_at_ms))
                and .5 <= observation.confidence <= 1
                and 0 <= now_ms-observation.captured_at_ms < self.ttl_ms)

    def tick(self, local, leader, *, now_ms, enabled=True):
        if not enabled:
            self.reset()
            return MotionDecision(state='paused')
        if not self._fresh(local, now_ms) or local.actor_id != self.actor_id or not self._fresh(leader, now_ms):
            self.progress.reset()
            self.previous_vector = (0., 0.)
            self.recovery_target = None
            return MotionDecision(state='waiting_position')
        ttl = int(min(local.captured_at_ms, leader.captured_at_ms)+self.ttl_ms-now_ms)
        if leader.session_id != self._leader_session:
            self.reset()
            self._leader_session = leader.session_id
        self.history.observe(leader.position, leader.captured_at_ms)
        goal = self.history.target(self.lag_distance)
        if self.recovery_anchor is not None and point_distance(local.position, self.recovery_anchor) >= 12:
            self.attempts = 0
            self.recovery_anchor = None
        if self.attempts >= self.recovery_limit and self.recovery_target is None:
            return MotionDecision(state='blocked')
        moving = self.previous_vector != (0., 0.)
        stuck = self.progress.update(local.position, now_ms=now_ms, moving=moving)
        if self.recovery_target is not None and (now_ms >= self.recovery_deadline or point_distance(local.position, self.recovery_target) <= 2):
            self.recovery_target = None
            self.planner.clear()
            self.progress.reset()
        if stuck:
            if self.recovery_anchor is None: self.recovery_anchor = local.position
            choices = escape_targets(local.position, self.previous_vector, self.planner.walls)
            self.recovery_target = choices[self.attempts % len(choices)] if choices else None
            self.attempts += 1
            self.recovery_deadline = now_ms+350
            self.planner.clear()
            self.progress.reset()
            self.previous_vector = (0., 0.)
            return MotionDecision(valid_for_ms=ttl, state='recover_neutral')
        target = self.recovery_target or goal
        path = self.planner.plan(local.position, target)
        vector = self.tracker.command(local.position, path, walls=self.planner.walls,
            confidence=min(local.confidence, leader.confidence))
        # A cached path can be near yet separated by a wall: retry once from
        # the actual position when its direct tracking command is blocked.
        if vector == (0., 0.) and point_distance(local.position, target) > self.tracker.arrival_radius:
            path = self.planner.plan(local.position, target, force=True)
            vector = self.tracker.command(local.position, path, walls=self.planner.walls,
                confidence=min(local.confidence, leader.confidence))
        self.previous_vector = vector
        state = 'recovering' if self.recovery_target is not None else 'following' if vector != (0., 0.) else 'arrived' if path else 'no_path'
        return MotionDecision(vector, ttl, state, path)
