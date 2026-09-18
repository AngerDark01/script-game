import unittest

from auto_modules.core.perception.models import (
    BoundingBox,
    CoordinateSpace,
    DetectionEvidence,
    FrameContext,
    TargetDetection,
)


class PerceptionModelsTests(unittest.TestCase):
    def test_bounding_box_exposes_center_and_normalized_coordinates(self):
        box = BoundingBox(left=10, top=20, width=30, height=40)

        self.assertEqual((25.0, 40.0), box.center)
        self.assertEqual((0.1, 0.2, 0.3, 0.4), box.normalized(100, 100))

    def test_detection_keeps_coordinate_space_and_evidence(self):
        evidence = DetectionEvidence("template", 0.91, {"scale": 1.0})
        detection = TargetDetection(
            target_type="map_device",
            center=(100.0, 120.0),
            coordinate_space=CoordinateSpace.FULL_SCREEN,
            confidence=0.91,
            bbox=BoundingBox(90, 110, 20, 20),
            evidence=(evidence,),
        )

        self.assertEqual(CoordinateSpace.FULL_SCREEN, detection.coordinate_space)
        self.assertEqual("template", detection.evidence[0].algorithm_id)
        self.assertEqual((100.0, 120.0), detection.bbox.center)

    def test_frame_context_records_source_and_dimensions(self):
        frame = FrameContext(image=object(), captured_at_ms=123, source="screen", width=1920, height=1080)

        self.assertEqual("screen", frame.source)
        self.assertEqual((1920, 1080), frame.size)


if __name__ == "__main__":
    unittest.main()
