import unittest

import numpy as np

from core.recognizer_optimized import HSVRecognizer


class RecognizerOptimizedTest(unittest.TestCase):
    def test_saturated_dynamic_icon_is_removed_from_match_features(self):
        recognizer = HSVRecognizer()
        recognizer.transparent_mode = True
        recognizer.enable_fog = False
        recognizer.sat_filter_enabled = True
        recognizer.sat_filter_thresh = 40

        img = np.zeros((80, 80, 3), dtype=np.uint8)
        img[:, 10:14] = (255, 255, 255)
        img[48:60, 48:60] = (0, 0, 255)

        match_mask, wall_mask, _ = recognizer.extract_combined(img, player_pos=(10, 70))

        self.assertGreater(np.count_nonzero(wall_mask[:, 10:14]), 0)
        self.assertEqual(np.count_nonzero(match_mask[46:62, 46:62]), 0)


if __name__ == "__main__":
    unittest.main()
