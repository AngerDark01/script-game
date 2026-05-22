import unittest

import numpy as np

from core.pathfinder import PathFinder


class PathFinderTest(unittest.TestCase):
    def test_diagonal_move_cannot_cut_through_blocked_corner(self):
        wall_map = np.full((3, 3), 255, dtype=np.uint8)
        wall_map[1, 1] = 0
        wall_map[1, 2] = 255
        wall_map[2, 1] = 255
        wall_map[2, 2] = 0

        pathfinder = PathFinder(downsample_factor=1, safety_margin=0, wall_shrink_iterations=0)

        self.assertIsNone(pathfinder.find_path(wall_map, (1, 1), (2, 2)))

    def test_wall_shrink_keeps_false_thin_wall_from_blocking_route(self):
        wall_map = np.zeros((50, 50), dtype=np.uint8)
        wall_map[:, 25] = 255

        strict_pathfinder = PathFinder(downsample_factor=1, safety_margin=0, wall_shrink_iterations=0)
        relaxed_pathfinder = PathFinder(downsample_factor=1, safety_margin=0, wall_shrink_iterations=1)

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

        pathfinder = PathFinder(downsample_factor=1, safety_margin=0, wall_shrink_iterations=1)

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


if __name__ == "__main__":
    unittest.main()
