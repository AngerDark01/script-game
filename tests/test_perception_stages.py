import unittest

from auto_modules.core.perception.algorithms.base import AlgorithmDescriptor
from auto_modules.core.perception.models import CoordinateSpace, DetectionEvidence, TargetDetection
from auto_modules.core.perception.profiles import AlgorithmProfile, TargetProfile
from auto_modules.core.perception.registry import AlgorithmRegistry
from auto_modules.core.perception.stages.confirmation import ConfirmationTracker
from auto_modules.core.perception.stages.fusion import fuse_candidates
from auto_modules.core.perception.stages.runner import DetectorRunner
from auto_modules.core.perception.stages.selection import select_candidate


class PerceptionStageTests(unittest.TestCase):
    def test_runner_executes_enabled_profiles_and_records_errors(self):
        registry = AlgorithmRegistry()
        registry.register(AlgorithmDescriptor("ok", "OK"), lambda _: _FakeDetector("ok", 0.8, 10, 10))
        registry.register(AlgorithmDescriptor("broken", "Broken"), lambda _: _BrokenDetector())
        profile = TargetProfile(
            "game",
            "scene",
            "target",
            (
                AlgorithmProfile("ok-1", "ok"),
                AlgorithmProfile("broken-1", "broken"),
                AlgorithmProfile("off", "ok", enabled=False),
            ),
        )

        result = DetectorRunner(registry).run(frame=object(), profile=profile)

        self.assertIn("ok-1", result.by_algorithm)
        self.assertIn("broken-1", result.errors)
        self.assertEqual(1, len(result.candidates))

    def test_fusion_keeps_primary_and_combines_evidence(self):
        first = _detection("color", 0.72, 100, 100)
        second = _detection("template", 0.91, 104, 101)

        fused = fuse_candidates([first, second], merge_radius=12)

        self.assertEqual(1, len(fused))
        self.assertAlmostEqual(0.91, fused[0].confidence)
        self.assertEqual({"color", "template"}, {item.algorithm_id for item in fused[0].evidence})
        self.assertEqual("fused", fused[0].source)

    def test_confirmation_requires_spatially_stable_frames(self):
        tracker = ConfirmationTracker()
        first = (_detection("color", 0.8, 20, 20),)
        second = (_detection("color", 0.85, 22, 21),)

        pending = tracker.observe(("game", "scene", "target"), first, required_frames=2, match_radius=8)
        confirmed = tracker.observe(("game", "scene", "target"), second, required_frames=2, match_radius=8)

        self.assertFalse(pending.confirmed)
        self.assertEqual((), pending.detections)
        self.assertTrue(confirmed.confirmed)
        self.assertEqual(1, len(confirmed.detections))

    def test_selection_supports_confidence_first_and_nearest(self):
        candidates = (_detection("color", 0.7, 100, 100), _detection("template", 0.9, 180, 180))

        self.assertEqual(180, select_candidate(candidates, "confidence").center[0])
        self.assertEqual(100, select_candidate(candidates, "first").center[0])
        self.assertEqual(100, select_candidate(candidates, "nearest", reference=(90, 90)).center[0])

    def test_runner_rejects_detection_for_a_different_profile_target(self):
        registry = AlgorithmRegistry()
        registry.register(AlgorithmDescriptor("wrong-target", "Wrong target"), lambda _: _FakeDetector("color", 0.8, 10, 10))
        profile = TargetProfile(
            "game",
            "scene",
            "expected-target",
            (AlgorithmProfile("wrong-target-1", "wrong-target"),),
        )

        result = DetectorRunner(registry).run(frame=object(), profile=profile)

        self.assertEqual((), result.candidates)
        self.assertIn("wrong-target-1", result.errors)
        self.assertIn("target_type", result.errors["wrong-target-1"])

    def test_profile_rejects_unknown_selection_strategy(self):
        with self.assertRaises(ValueError):
            TargetProfile("game", "scene", "target", selection_strategy="random")


def _detection(source, confidence, x, y):
    return TargetDetection(
        target_type="target",
        center=(x, y),
        coordinate_space=CoordinateSpace.FULL_SCREEN,
        confidence=confidence,
        source=source,
        evidence=(DetectionEvidence(source, confidence),),
    )


class _FakeDetector:
    def __init__(self, source, confidence, x, y):
        self.source = source
        self.confidence = confidence
        self.x = x
        self.y = y

    def detect(self, _frame):
        return [_detection(self.source, self.confidence, self.x, self.y)]


class _BrokenDetector:
    def detect(self, _frame):
        raise RuntimeError("boom")


if __name__ == "__main__":
    unittest.main()
