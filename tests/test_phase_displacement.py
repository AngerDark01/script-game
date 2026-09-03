import unittest

import numpy as np

from core.phase_displacement import estimate_phase_displacement


class PhaseDisplacementTest(unittest.TestCase):
    def test_identical_images_are_normalized_to_zero_shift(self):
        image = np.zeros((16, 16), dtype=np.uint8)
        image[4:8, 5:9] = 255

        shift, response = estimate_phase_displacement(image, image)

        self.assertEqual(shift, (0.0, 0.0))
        self.assertGreaterEqual(float(response), 0.0)

    def test_invalid_input_matches_existing_failure_contract(self):
        shift, response = estimate_phase_displacement(None, None)

        self.assertIsNone(shift)
        self.assertEqual(response, 0.0)


if __name__ == "__main__":
    unittest.main()
