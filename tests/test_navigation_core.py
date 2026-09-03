import os
import tempfile
import unittest

import numpy as np

from core.navigation_core import NavigationCore


class _FakeRecognizer:
    def __init__(self, match_mask, wall_mask, fog_mask):
        self._result = (match_mask, wall_mask, fog_mask)

    def extract_combined(self, minimap_img, player_pos=None):
        return self._result


class NavigationCoreTest(unittest.TestCase):
    def test_f2f_tracking_uses_wall_mask_instead_of_match_mask(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            np.savez_compressed(
                os.path.join(temp_dir, "map_data.npz"),
                wall_layer=np.zeros((40, 40), dtype=np.uint8),
                explored_map=np.zeros((40, 40), dtype=np.uint8),
                fog_layer=np.zeros((40, 40), dtype=np.uint8),
                current_pos=np.array([20.0, 20.0]),
                canvas_size=40,
            )

            core = NavigationCore(temp_dir)
            core.draw_scale = 1.0
            core.min_match_features = 1
            core.min_wall_features = 1
            core.is_localized = True
            core.current_pos = (20.0, 20.0)
            core.last_good_pos = (20.0, 20.0)

            wall_mask = np.zeros((12, 12), dtype=np.uint8)
            wall_mask[:, 5:7] = 255
            match_mask = np.full((12, 12), 255, dtype=np.uint8)
            fog_mask = np.zeros((12, 12), dtype=np.uint8)

            core.prev_wall_mask = wall_mask.copy()
            core.prev_mask = np.zeros_like(match_mask)
            core.recognizer = _FakeRecognizer(match_mask, wall_mask, fog_mask)

            calls = []

            def fake_estimate(img1, img2):
                calls.append((img1.copy(), img2.copy()))
                return (1.0, 0.0), 0.5

            core._estimate_displacement = fake_estimate

            x, y, conf = core.localize(np.zeros((12, 12, 3), dtype=np.uint8), player_pos=(6, 6))

            self.assertEqual(conf, 0.5)
            self.assertEqual((x, y), (19.0, 20.0))
            self.assertEqual(len(calls), 1)
            self.assertTrue(np.array_equal(calls[0][0], wall_mask))
            self.assertTrue(np.array_equal(calls[0][1], wall_mask))


if __name__ == "__main__":
    unittest.main()
