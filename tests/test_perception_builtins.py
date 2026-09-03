import unittest

from core.perception.algorithms.color import ColorRegionDetector
from core.perception.builtins import create_default_algorithm_registry


class PerceptionBuiltinsTests(unittest.TestCase):
    def test_default_registry_exposes_available_and_future_algorithms(self):
        registry = create_default_algorithm_registry()
        descriptors = {item.algorithm_id: item for item in registry.descriptors()}

        self.assertEqual("available", descriptors["color"].status)
        self.assertEqual("available", descriptors["template"].status)
        self.assertEqual("unavailable", descriptors["ocr"].status)
        self.assertIn("threshold", {item.name for item in descriptors["template"].parameters})

    def test_default_registry_creates_color_detector_with_target_type(self):
        registry = create_default_algorithm_registry()

        detector = registry.create("color", {"target_type": "loot", "min_area": 8})

        self.assertIsInstance(detector, ColorRegionDetector)
        self.assertEqual("loot", detector.target_type)
        self.assertEqual(8, detector.parameters["min_area"])


if __name__ == "__main__":
    unittest.main()
