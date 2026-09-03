import unittest

import cv2
import numpy as np

from core.perception.algorithms import ShapeDetector as PublicShapeDetector
from core.perception.algorithms.shape import ShapeDetector
from core.perception.builtins import create_default_algorithm_registry
from core.perception.models import CoordinateSpace, FrameContext


class ShapeAlgorithmTests(unittest.TestCase):
    def test_shape_is_available_from_public_surface_and_default_registry(self):
        registry = create_default_algorithm_registry()
        descriptor = registry.descriptor("shape")

        self.assertIs(ShapeDetector, PublicShapeDetector)
        self.assertEqual("available", descriptor.status)
        self.assertEqual(
            {"threshold", "threshold_mode", "morphology_kernel", "min_area", "max_area", "min_vertices", "max_vertices", "approximation_ratio", "min_circularity", "min_solidity", "max_results"},
            {parameter.name for parameter in descriptor.parameters},
        )
        self.assertIsInstance(registry.create("shape", {"target_type": "marker"}), ShapeDetector)

    def test_circle_contour_becomes_geometry_preserving_target_detection(self):
        image = np.zeros((140, 180, 3), dtype=np.uint8)
        cv2.circle(image, (90, 70), 24, (255, 255, 255), -1)
        frame = FrameContext(
            image=image,
            captured_at_ms=2468,
            coordinate_space=CoordinateSpace.GAME_WINDOW,
        )
        detector = ShapeDetector(
            target_type="trial_marker",
            parameters={"min_area": 500, "min_circularity": 0.7},
        )

        detections = detector.detect(frame)

        self.assertEqual(1, len(detections))
        detection = detections[0]
        self.assertEqual("trial_marker", detection.target_type)
        self.assertEqual("shape", detection.source)
        self.assertEqual(CoordinateSpace.GAME_WINDOW, detection.coordinate_space)
        self.assertEqual(2468, detection.detected_at_ms)
        self.assertIsNotNone(detection.bbox)
        self.assertAlmostEqual(90.0, detection.center[0], delta=1.5)
        self.assertAlmostEqual(70.0, detection.center[1], delta=1.5)
        self.assertGreaterEqual(detection.evidence[0].details["circularity"], 0.7)
        self.assertGreater(detection.evidence[0].details["area"], 500)

    def test_vertex_filter_keeps_rectangle_and_rejects_circle(self):
        image = np.zeros((150, 220, 3), dtype=np.uint8)
        cv2.circle(image, (55, 75), 24, (255, 255, 255), -1)
        cv2.rectangle(image, (140, 40), (190, 110), (255, 255, 255), -1)
        detector = ShapeDetector(
            target_type="rectangle_marker",
            parameters={"min_area": 500, "min_vertices": 4, "max_vertices": 4},
        )

        detections = detector.detect(FrameContext(image=image))

        self.assertEqual(1, len(detections))
        self.assertAlmostEqual(165.5, detections[0].center[0], delta=1.0)
        self.assertAlmostEqual(75.5, detections[0].center[1], delta=1.0)
        self.assertEqual(4, detections[0].evidence[0].details["vertices"])

    def test_invalid_shape_configuration_fails_before_frame_processing(self):
        with self.assertRaises(ValueError):
            ShapeDetector("shape", {"threshold_mode": "adaptive"})
        with self.assertRaises(ValueError):
            ShapeDetector("shape", {"min_circularity": 1.1})
        with self.assertRaises(ValueError):
            ShapeDetector("shape", {"approximation_ratio": 0})
        with self.assertRaises(ValueError):
            ShapeDetector("shape", {"min_area": float("nan")})


if __name__ == "__main__":
    unittest.main()
