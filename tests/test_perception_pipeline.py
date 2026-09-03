import unittest

from core.perception.algorithms.base import AlgorithmDescriptor
from core.perception.models import CoordinateSpace, DetectionEvidence, FrameContext, TargetDetection
from core.perception.pipeline import PerceptionPipeline
from core.perception.profiles import AlgorithmProfile, TargetProfile
from core.perception.registry import AlgorithmRegistry


class PerceptionPipelineTests(unittest.TestCase):
    def test_pipeline_runs_enabled_algorithms_and_fuses_nearby_results(self):
        registry = AlgorithmRegistry()
        registry.register(AlgorithmDescriptor("first", "First"), lambda _: _FakeDetector(0.72, 100, 100, "first"))
        registry.register(AlgorithmDescriptor("second", "Second"), lambda _: _FakeDetector(0.81, 104, 101, "second"))
        registry.register(AlgorithmDescriptor("disabled", "Disabled"), lambda _: _FakeDetector(0.99, 100, 100, "disabled"))
        profile = TargetProfile(
            "game",
            "scene",
            "map_device",
            (
                AlgorithmProfile("a", "first"),
                AlgorithmProfile("b", "second"),
                AlgorithmProfile("c", "disabled", enabled=False),
            ),
        )

        result = PerceptionPipeline(registry).run(FrameContext(image=object()), profile)

        self.assertEqual(2, len(result.by_algorithm))
        self.assertEqual(1, len(result.detections))
        self.assertEqual({"first", "second"}, {item.algorithm_id for item in result.detections[0].evidence})
        self.assertAlmostEqual(0.81, result.detections[0].confidence)

    def test_pipeline_filters_results_below_profile_threshold(self):
        registry = AlgorithmRegistry()
        registry.register(AlgorithmDescriptor("fake", "Fake"), lambda _: _FakeDetector(0.4, 10, 20, "fake"))
        profile = TargetProfile("game", "scene", "loot", (AlgorithmProfile("a", "fake"),), min_confidence=0.5)

        result = PerceptionPipeline(registry).run(FrameContext(image=object()), profile)

        self.assertEqual((), result.detections)


class _FakeDetector:
    def __init__(self, confidence, x, y, algorithm_id):
        self.confidence = confidence
        self.x = x
        self.y = y
        self.algorithm_id = algorithm_id

    def detect(self, frame):
        return [
            TargetDetection(
                target_type="map_device",
                center=(self.x, self.y),
                coordinate_space=CoordinateSpace.FULL_SCREEN,
                confidence=self.confidence,
                source=self.algorithm_id,
                evidence=(DetectionEvidence(self.algorithm_id, self.confidence),),
            )
        ]


if __name__ == "__main__":
    unittest.main()
