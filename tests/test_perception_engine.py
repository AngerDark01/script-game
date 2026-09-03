import unittest

import numpy as np

from core.perception import (
    AlgorithmProfile,
    FrameContext,
    PerceptionEngine,
    TargetProfile,
)


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


if __name__ == "__main__":
    unittest.main()
