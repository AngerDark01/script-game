import unittest

import numpy as np

from auto_modules.core.routing import PathFinder
from auto_modules.core.routing.pathfinder.astar import heuristic
from auto_modules.core.routing.pathfinder.coordinates import grid_size_from_map_shape


class PathFinderTest(unittest.TestCase):
    def test_diagonal_move_cannot_cut_through_blocked_corner(self):
        wall_map = np.full((3, 3), 255, dtype=np.uint8)
        wall_map[1, 1] = 0
        wall_map[1, 2] = 255
        wall_map[2, 1] = 255
        wall_map[2, 2] = 0

        pathfinder = PathFinder(
            downsample_factor=1, safety_margin=0, wall_shrink_iterations=0,
            start_clear_radius=0,
        )

        self.assertIsNone(pathfinder.find_path(wall_map, (1, 1), (2, 2)))

    def test_wall_shrink_keeps_false_thin_wall_from_blocking_route(self):
        wall_map = np.zeros((50, 50), dtype=np.uint8)
        wall_map[:, 25] = 255

        strict_pathfinder = PathFinder(
            downsample_factor=1, safety_margin=0, wall_shrink_iterations=0,
            start_clear_radius=0,
        )
        relaxed_pathfinder = PathFinder(
            downsample_factor=1, safety_margin=0, wall_shrink_iterations=1,
            start_clear_radius=0,
        )

        self.assertIsNone(strict_pathfinder.find_path(wall_map, (10, 25), (40, 25)))

        relaxed_path = relaxed_pathfinder.find_path(wall_map, (10, 25), (40, 25))
        self.assertIsNotNone(relaxed_path)
        self.assertEqual(relaxed_path[0], (10, 25))
        self.assertEqual(relaxed_path[-1], (40, 25))

    def test_unexplored_area_is_not_walkable(self):
        wall_map = np.zeros((60, 60), dtype=np.uint8)
        explored_map = np.zeros((60, 60), dtype=np.uint8)
        explored_map[20:41, 5:26] = 255
        explored_map[20:41, 34:56] = 255

        pathfinder = PathFinder(
            downsample_factor=1, safety_margin=0, wall_shrink_iterations=1,
            start_clear_radius=0,
        )

        self.assertIsNone(
            pathfinder.find_path(
                wall_map,
                (10, 30),
                (50, 30),
                explored_map=explored_map,
            )
        )

        explored_map[28:33, 25:35] = 255
        path = pathfinder.find_path(
            wall_map,
            (10, 30),
            (50, 30),
            explored_map=explored_map,
        )

        self.assertIsNotNone(path)
        self.assertTrue(all(explored_map[y, x] > 0 for x, y in path))

    def test_clearance_cost_prefers_route_with_more_wall_distance(self):
        wall_map = np.zeros((40, 60), dtype=np.uint8)
        wall_map[8:32, 28] = 255
        plain = PathFinder(downsample_factor=1, start_clear_radius=0)
        safe = PathFinder(
            downsample_factor=1,
            start_clear_radius=0,
            clearance_radius=8,
            clearance_weight=4,
        )
        plain_path = plain.find_path(wall_map, (8, 20), (52, 20))
        safe_path = safe.find_path(wall_map, (8, 20), (52, 20))
        self.assertIsNotNone(plain_path)
        self.assertIsNotNone(safe_path)
        self.assertGreaterEqual(len(safe_path), len(plain_path))

    def test_octile_heuristic_matches_eight_neighbor_lower_bound(self):
        self.assertAlmostEqual(heuristic((0, 0), (3, 2)), 3.828, places=3)

    def test_grid_size_keeps_non_divisible_map_border(self):
        self.assertEqual(grid_size_from_map_shape((17, 25), 8), (4, 3))


if __name__ == "__main__":
    unittest.main()
