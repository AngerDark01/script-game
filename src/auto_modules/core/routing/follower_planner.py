"""Follow-session path cache around the existing A* and geometry library."""
from math import isfinite
import numpy as np
from auto_modules.core.routing.pathfinder.runtime import PathFinder
from auto_modules.core.routing.geometry import line_is_walkable, smooth_path, point_distance, distance_to_path


class _PreparedPathFinder(PathFinder):
    """Reuse the existing A* while retaining its immutable obstacle grid."""
    def __init__(self, walls, factor):
        super().__init__(downsample_factor=factor,start_clear_radius=0,walkable_snap_radius=0,wall_shrink_iterations=0)
        self._prepared = None

    def _build_obstacle_map(self, wall_map, grid_w, grid_h, explored_map=None):
        if self._prepared is None:
            self._prepared = super()._build_obstacle_map(wall_map,grid_w,grid_h,explored_map)
            self._prepared.setflags(write=False)
        return self._prepared


class FollowerPlanner:
    def __init__(self, wall_layer, *, downsample_factor=8, target_threshold=3., deviation_threshold=10.):
        self.walls = np.where(np.asarray(wall_layer) > 0, 255, 0).astype(np.uint8)
        if self.walls.ndim != 2 or min(self.walls.shape) < downsample_factor or downsample_factor < 1:
            raise ValueError('invalid wall map or grid scale')
        self.walls.setflags(write=False)
        # Follow navigation must not erase real walls near the starting point.
        factors = []
        factor = downsample_factor
        while factor >= 1:
            factors.append(factor)
            if factor == 1: break
            factor = max(1, factor//2)
        self._planners = [_PreparedPathFinder(self.walls,f) for f in factors]
        self.pathfinder = self._planners[0]
        self.target_threshold, self.deviation_threshold = target_threshold, deviation_threshold
        self.path, self.goal, self.replans = (), None, 0

    def clear(self):
        self.path, self.goal = (), None

    def plan(self, start, goal, *, force=False):
        if (len(start) != 2 or len(goal) != 2 or not all(isfinite(v) for v in (*start, *goal))
                or not line_is_walkable(self.walls, start, start)
                or not line_is_walkable(self.walls, goal, goal)):
            self.clear()
            return ()
        if (not force and self.path and point_distance(goal, self.goal) <= self.target_threshold
                and distance_to_path(start, self.path) <= self.deviation_threshold):
            return self.path
        self.replans += 1
        # Fast coarse plan first; if quantization loses a corridor or clips a
        # wall, refine using the SAME A*. Never accept unvalidated coarse paths.
        for planner in self._planners:
            raw = planner.find_path(self.walls, start, goal)
            candidate = [tuple(start), *(raw or [])]
            if raw and all(line_is_walkable(self.walls, a, b, corner_safe=True) for a, b in zip(candidate, candidate[1:])):
                self.path = tuple(smooth_path(self.walls, candidate, corner_safe=True))
                self.goal = tuple(goal)
                return self.path
        self.clear()
        return ()
