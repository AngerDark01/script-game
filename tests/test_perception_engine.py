import unittest
from unittest.mock import patch

import numpy as np

from auto_modules.core.perception import (
    AlgorithmProfile,
    FrameContext,
    PerceptionEngine,
    TargetProfile,
)
from auto_modules.core.perception.pipeline import PerceptionPipeline


class PerceptionEngineTests(unittest.TestCase):
    def test_detect_uses_one_target_level_entry_point(self):
        engine = PerceptionEngine()
        profile = TargetProfile(
            game_id="game",
            scene_id="scene",
            target_type="marker",
            algorithms=(
                AlgorithmProfile(
                    instance_id="marker-color",
                    algorithm_id="color",
                    parameters={
                        "hue_min": 0,
                        "hue_max": 10,
                        "saturation_min": 100,
                        "value_min": 100,
                    },
                ),
            ),
        )
        image = np.zeros((12, 12, 3), dtype=np.uint8)
        image[:, :] = (0, 0, 255)
        frame = FrameContext(
            image=image,
            width=12,
            height=12,
        )

        result = engine.detect(frame, profile)

        self.assertEqual(1, len(result.detections))
        self.assertEqual("marker", result.detections[0].target_type)

    def test_registered_profiles_are_resolved_by_game_scene_target(self):
        engine = PerceptionEngine()
        profile = TargetProfile("game", "scene", "loot")

        key = engine.register_profile(profile)
        resolved = engine.resolve_profile("game", "scene", "loot")

        self.assertEqual(("game", "scene", "loot"), key)
        self.assertEqual(profile.to_dict(), resolved.to_dict())
        self.assertIsNot(profile, resolved)

    def test_profile_registration_rejects_duplicates_and_missing_keys_are_explicit(self):
        engine = PerceptionEngine()
        profile = TargetProfile("game", "scene", "portal")
        engine.register_profile(profile)

        with self.assertRaises(ValueError):
            engine.register_profile(profile)
        with self.assertRaises(KeyError):
            engine.resolve_profile("game", "scene", "missing")

    def test_replacing_profile_clears_existing_confirmation_history(self):
        engine = PerceptionEngine()
        image = np.zeros((12, 12, 3), dtype=np.uint8)
        image[:, :] = (0, 0, 255)
        frame = FrameContext(image=image, width=12, height=12)
        color_algorithm = AlgorithmProfile(
            instance_id="marker-color",
            algorithm_id="color",
            parameters={
                "hue_min": 0,
                "hue_max": 10,
                "saturation_min": 100,
                "value_min": 100,
            },
        )
        first = TargetProfile("game", "scene", "marker", (color_algorithm,), confirmation_frames=2)
        replacement = TargetProfile("game", "scene", "marker", (color_algorithm,), confirmation_frames=2)
        engine.register_profile(first)

        pending = engine.detect_target(frame, game_id="game", scene_id="scene", target_type="marker")
        engine.register_profile(replacement, replace=True)
        after_replacement = engine.detect_target(frame, game_id="game", scene_id="scene", target_type="marker")

        self.assertFalse(pending.confirmed)
        self.assertFalse(after_replacement.confirmed)
        self.assertEqual((1,), after_replacement.confirmation_counts)

    def test_default_engine_executes_stages_without_calling_compatibility_pipeline(self):
        engine = PerceptionEngine()
        image = np.zeros((12, 12, 3), dtype=np.uint8)
        image[:, :] = (0, 0, 255)
        frame = FrameContext(image=image, width=12, height=12)
        profile = TargetProfile(
            "game",
            "scene",
            "marker",
            (
                AlgorithmProfile(
                    "marker-color",
                    "color",
                    parameters={
                        "hue_min": 0,
                        "hue_max": 10,
                        "saturation_min": 100,
                        "value_min": 100,
                    },
                ),
            ),
        )

        with patch.object(PerceptionPipeline, "run", side_effect=AssertionError("compatibility path used")):
            result = engine.detect(frame, profile)

        self.assertTrue(result.confirmed)
        self.assertIsNotNone(result.selected)
        self.assertEqual("marker", result.selected.target_type)


if __name__ == "__main__":
    unittest.main()
