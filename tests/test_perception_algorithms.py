import unittest

import cv2
import numpy as np

from auto_modules.core.perception.algorithms.color import ColorRegionDetector
from auto_modules.core.perception.algorithms.template import TemplateDetector
from auto_modules.core.perception.models import CoordinateSpace, FrameContext


class PerceptionAlgorithmsTests(unittest.TestCase):
    def test_color_detector_finds_full_screen_region(self):
        image = np.zeros((120, 180, 3), dtype=np.uint8)
        image[35:65, 70:110] = (0, 255, 0)
        frame = FrameContext(image=image, source="screen", coordinate_space=CoordinateSpace.FULL_SCREEN)
        detector = ColorRegionDetector(
            target_type="trial_marker",
            parameters={
                "hue_min": 45,
                "hue_max": 75,
                "saturation_min": 150,
                "value_min": 150,
                "min_area": 50,
            },
        )

        detections = detector.detect(frame)

        self.assertEqual(1, len(detections))
        self.assertEqual((90.0, 50.0), detections[0].center)
        self.assertEqual(CoordinateSpace.FULL_SCREEN, detections[0].coordinate_space)
        self.assertEqual("color", detections[0].source)

    def test_template_detector_supports_multiscale_matching_and_bbox(self):
        image = np.zeros((160, 220, 3), dtype=np.uint8)
        cv2.rectangle(image, (90, 60), (130, 100), (255, 255, 255), -1)
        template = image[60:101, 90:131].copy()
        frame = FrameContext(image=image, source="screen", coordinate_space=CoordinateSpace.GAME_WINDOW)
        detector = TemplateDetector(
            target_type="map_device",
            template=template,
            parameters={"scales": [1.0], "threshold": 0.85, "top_k": 1},
        )

        detections = detector.detect(frame)

        self.assertEqual(1, len(detections))
        self.assertAlmostEqual(110.0, detections[0].center[0], delta=2.0)
        self.assertAlmostEqual(80.0, detections[0].center[1], delta=2.0)
        self.assertEqual((41.0, 41.0), (detections[0].bbox.width, detections[0].bbox.height))
        self.assertEqual("template", detections[0].evidence[0].algorithm_id)

    def test_detectors_return_empty_for_missing_or_invalid_frames(self):
        detector = ColorRegionDetector("loot", parameters={})

        self.assertEqual([], detector.detect(FrameContext(image=None)))
        self.assertEqual([], detector.detect(FrameContext(image=np.zeros((0, 0, 3), dtype=np.uint8))))


if __name__ == "__main__":
    unittest.main()
