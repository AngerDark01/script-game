import unittest

from core.navigation.projection import project_world_target


class NavigationProjectionTests(unittest.TestCase):
    def test_projects_world_direction_with_minimum_radius(self):
        target = project_world_target(
            player_position=(0.0, 0.0),
            target_position=(3.0, 4.0),
            view_center=(100, 100),
            pixels_per_world_unit=10.0,
            minimum_radius=60.0,
            maximum_radius=100.0,
        )

        self.assertEqual((136, 148), target.point)
        self.assertEqual((0.6, 0.8), target.direction)
        self.assertEqual(5.0, target.world_distance)
        self.assertEqual(50.0, target.raw_radius)
        self.assertEqual(60.0, target.radius)

    def test_projects_coincident_target_to_view_center(self):
        target = project_world_target(
            player_position=(10.0, 20.0),
            target_position=(10.0, 20.0),
            view_center=(100, 100),
            pixels_per_world_unit=10.0,
            minimum_radius=0.0,
            maximum_radius=100.0,
        )

        self.assertEqual((100, 100), target.point)
        self.assertEqual((0.0, 0.0), target.direction)
        self.assertEqual(0.0, target.radius)


if __name__ == "__main__":
    unittest.main()
