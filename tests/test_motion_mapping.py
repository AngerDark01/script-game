import unittest

from auto_modules.adapters.input.motion_mapping import (
    calculate_mapped_target_click,
    calculate_movement_click,
)


class MotionMappingCompatibilityTests(unittest.TestCase):
    def test_normal_movement_keeps_existing_minimum_radius_projection(self):
        result = calculate_movement_click(
            player_global_pos=(0, 0),
            target_global_pos=(3, 4),
            game_screen_center=(100, 100),
            movement_scale_factor=10.0,
            movement_min_click_radius=60,
            movement_max_click_radius=100,
        )

        self.assertEqual((136, 148), result.screen_pos)
        self.assertEqual(50.0, result.click_info["raw_screen_radius"])
        self.assertEqual(60.0, result.click_info["screen_radius"])

    def test_precise_target_keeps_center_click_for_overlapping_positions(self):
        result = calculate_mapped_target_click(
            player_global_pos=(10, 20),
            target_global_pos=(10, 20),
            game_screen_center=(100, 100),
            movement_scale_factor=10.0,
            movement_precision_click_max_radius=100,
            reason="compatibility",
        )

        self.assertEqual((100, 100), result.screen_pos)
        self.assertEqual((0.0, 0.0), result.click_info["direction"])


if __name__ == "__main__":
    unittest.main()
