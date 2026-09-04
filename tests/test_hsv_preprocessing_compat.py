import hashlib
import unittest

import cv2
import numpy as np

from core.vision.hsv_recognizer import HSVRecognizer


def fixture_image() -> np.ndarray:
    image = np.zeros((96, 96, 3), dtype=np.uint8)
    image[:, 12:16] = (255, 255, 255)
    fog_hsv = np.full((24, 24, 3), (100, 210, 220), dtype=np.uint8)
    image[40:64, 40:64] = cv2.cvtColor(fog_hsv, cv2.COLOR_HSV2BGR)
    image[70:82, 70:82] = (0, 0, 255)
    return image


def array_hash(value: np.ndarray) -> str:
    return hashlib.sha256(value.tobytes()).hexdigest()


class HsvPreprocessingCompatibilityTests(unittest.TestCase):
    def test_public_recognizer_output_matches_pre_extraction_fixture(self):
        recognizer = HSVRecognizer()
        image = fixture_image()
        match, combined_wall, combined_fog = recognizer.extract_combined(
            image,
            player_pos=(12, 80),
        )

        expected = {
            "wall": ("b5bf2189c1e409124ff2281afbd650cca9acb0c4f65ed19014d95e61c757a9af", 384),
            "fog": ("c4889bc71520b71f2fdb519ea777bdc610fe6a498f9a0d459c99e49d25cd7822", 576),
            "match": ("bd013651114adc6964eeac7cb73cd099e787266ad7caef2295d48a7ce93c9e1e", 353),
            "combined_wall": ("774fd9367305d5cd9a19ff355a0c5fc20297983fc679846f39413f5ee2e20803", 235),
            "combined_fog": ("2d07a41ae992770085117e9815300bfd0730745883e60b24aaad5e69dfc087ae", 0),
            "raw_gray": ("cd285e5bdf48a8df58d68f0378eace504b96bbba11541c57f72c9d0deaec87c3", 6395),
        }
        actual = {
            "wall": recognizer.extract_walls(image),
            "fog": recognizer.extract_fog(image),
            "match": match,
            "combined_wall": combined_wall,
            "combined_fog": combined_fog,
            "raw_gray": recognizer.get_raw_gray(image),
        }

        for name, value in actual.items():
            expected_hash, expected_nonzero = expected[name]
            self.assertEqual(expected_hash, array_hash(value), name)
            self.assertEqual(expected_nonzero, int(np.count_nonzero(value)), name)


if __name__ == "__main__":
    unittest.main()
