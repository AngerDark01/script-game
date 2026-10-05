import unittest

import numpy as np

from auto_modules.core.vision import HSVRecognizer


class RecognizerOptimizedTest(unittest.TestCase):
    def test_combined_with_processed_reuses_one_wall_preprocessing_pass(self):
        recognizer = HSVRecognizer()
        frame = np.random.default_rng(7).integers(0, 256, (96, 96, 3), dtype=np.uint8)
        expected_processed = recognizer.preprocess_image(frame)
        expected_masks = recognizer.extract_combined(frame, player_pos=(48, 48))
        expected_gray = recognizer.get_raw_gray(frame)
        original = recognizer._preprocess_for_wall
        calls = 0

        def counted(image):
            nonlocal calls
            calls += 1
            return original(image)

        recognizer._preprocess_for_wall = counted
        processed, masks = recognizer.extract_combined_with_processed(frame, player_pos=(48, 48))
        gray = recognizer.get_raw_gray(frame, processed=processed)

        self.assertEqual(calls, 1)
        np.testing.assert_array_equal(processed, expected_processed)
        for actual, expected in zip(masks, expected_masks):
            np.testing.assert_array_equal(actual, expected)
        np.testing.assert_array_equal(gray, expected_gray)

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

    def test_full_map_options_preserve_center_walls_for_dual_first_frame(self):
        recognizer = HSVRecognizer()
        recognizer.extract_walls = lambda _img, is_processed=False: np.full(
            (80, 80), 255, dtype=np.uint8
        )
        recognizer.extract_fog = lambda _img, is_processed=False: np.zeros(
            (80, 80), dtype=np.uint8
        )
        frame = np.zeros((80, 80, 3), dtype=np.uint8)

        masked, _wall, _fog = recognizer.extract_combined(frame)
        full, _wall, _fog = recognizer.extract_combined(
            frame,
            exclude_player=False,
            exclude_dynamic=False,
        )

        self.assertEqual(int(masked[40, 40]), 0)
        self.assertGreater(int(full[40, 40]), 0)


if __name__ == "__main__":
    unittest.main()
