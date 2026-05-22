import unittest

import numpy as np

from core.path_utils import (
    build_cumulative_lengths,
    interpolate_by_distance,
    is_inside_exit_region,
    project_point_onto_path,
    remove_collinear_points,
    smooth_path,
)


class PathUtilsTest(unittest.TestCase):
    def test_remove_collinear_points_keeps_turns(self):
        path = [(0, 0), (1, 0), (2, 0), (2, 1), (2, 2)]
        simplified = remove_collinear_points(path)
        self.assertEqual(simplified, [(0, 0), (2, 0), (2, 2)])

    def test_is_inside_exit_region_uses_radius(self):
        region = {"center": [100, 100], "radius": 10}
        self.assertTrue(is_inside_exit_region((108, 104), region))
        self.assertFalse(is_inside_exit_region((120, 100), region))

    def test_project_and_interpolate_along_path(self):
        path = [(0, 0), (10, 0), (10, 10)]
        cumulative = build_cumulative_lengths(path)
        projection = project_point_onto_path((6, 2), path, cumulative)
        self.assertAlmostEqual(projection["distance"], 6.0, places=3)
        self.assertAlmostEqual(projection["distance_to_path"], 2.0, places=3)

        subgoal = interpolate_by_distance(path, cumulative, 14.0)
        self.assertAlmostEqual(subgoal[0], 10.0, places=3)
        self.assertAlmostEqual(subgoal[1], 4.0, places=3)

    def test_smooth_path_shortcuts_straight_visible_segment(self):
        wall_map = np.zeros((40, 40), dtype=np.uint8)
        path = [(1, 1), (5, 1), (10, 1), (20, 1)]
        smoothed = smooth_path(wall_map, path)
        self.assertEqual(smoothed, [(1, 1), (20, 1)])


if __name__ == "__main__":
    unittest.main()
