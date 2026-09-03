from __future__ import annotations

from .astar import astar_path, heuristic, reconstruct_path
from .coordinates import (
    grid_path_to_map_path,
    grid_size_from_map_shape,
    in_grid_bounds,
    map_to_grid,
)
from .grid import build_obstacle_map, clear_start_area
from .snap import find_nearest_walkable, walkable_snap_grid_radius


class PathFinder:
    """A* pathfinder optimized with a downsampled map grid."""

    def __init__(
        self,
        downsample_factor=10,
        safety_margin=0,
        wall_shrink_iterations=0,
        start_clear_radius=30,
        walkable_snap_radius=18,
    ):
        self.downsample_factor = downsample_factor
        self.safety_margin = max(0, int(safety_margin))
        self.wall_shrink_iterations = max(0, int(wall_shrink_iterations))
        self.start_clear_radius = max(0, int(start_clear_radius))
        self.walkable_snap_radius = max(0, int(walkable_snap_radius))

    def find_path(self, wall_map, start_pos, end_pos, explored_map=None):
        """Find a map-space path from start_pos to end_pos, or None if blocked."""
        grid_w, grid_h = grid_size_from_map_shape(wall_map.shape, self.downsample_factor)
        start_grid = map_to_grid(start_pos, self.downsample_factor)
        end_grid = map_to_grid(end_pos, self.downsample_factor)

        if not in_grid_bounds(start_grid, grid_w, grid_h):
            print(f"[PathFinder] 起点超出边界: {start_grid}")
            return None
        if not in_grid_bounds(end_grid, grid_w, grid_h):
            print(f"[PathFinder] 终点超出边界: {end_grid}")
            return None

        obstacle_map = self._build_obstacle_map(
            wall_map,
            grid_w,
            grid_h,
            explored_map=explored_map,
        )
        obstacle_map = self._clear_start_area(obstacle_map, start_grid)

        if obstacle_map[start_grid[1], start_grid[0]] > 0:
            print("[PathFinder] 起点在障碍物内，尝试寻找最近点...")
            start_grid = self._find_nearest_walkable(obstacle_map, start_grid)
            if start_grid is None:
                print("[PathFinder] 无法找到起点附近的空地")
                return None

        if obstacle_map[end_grid[1], end_grid[0]] > 0:
            print("[PathFinder] 终点在障碍物内，尝试寻找最近点...")
            end_grid = self._find_nearest_walkable(obstacle_map, end_grid)
            if end_grid is None:
                print("[PathFinder] 无法找到终点附近的空地")
                return None

        path_grid = self._astar(obstacle_map, start_grid, end_grid)
        if path_grid is None:
            return None

        return grid_path_to_map_path(path_grid, self.downsample_factor, end_pos)

    def _build_obstacle_map(self, wall_map, grid_w, grid_h, explored_map=None):
        return build_obstacle_map(
            wall_map,
            grid_w,
            grid_h,
            downsample_factor=self.downsample_factor,
            safety_margin=self.safety_margin,
            wall_shrink_iterations=self.wall_shrink_iterations,
            explored_map=explored_map,
        )

    def _clear_start_area(self, obstacle_map, start_grid):
        return clear_start_area(
            obstacle_map,
            start_grid,
            start_clear_radius=self.start_clear_radius,
            downsample_factor=self.downsample_factor,
        )

    def _astar(self, grid, start, end):
        return astar_path(grid, start, end)

    def _heuristic(self, a, b):
        return heuristic(a, b)

    def _reconstruct_path(self, came_from, current):
        return reconstruct_path(came_from, current)

    def _find_nearest_walkable(self, grid, pos, max_radius=None):
        if max_radius is None:
            max_radius = walkable_snap_grid_radius(
                self.walkable_snap_radius,
                self.downsample_factor,
            )
        return find_nearest_walkable(grid, pos, max_radius)
