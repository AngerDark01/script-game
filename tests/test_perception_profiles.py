import json
import tempfile
import unittest
from pathlib import Path

from auto_modules.core.perception.profile_store import load_target_profile, save_target_profile
from auto_modules.core.perception.profiles import AlgorithmProfile, TargetProfile


class PerceptionProfilesTests(unittest.TestCase):
    def test_profile_round_trip_preserves_hierarchy_and_metadata(self):
        profile = TargetProfile(
            game_id="game-a",
            scene_id="map-select",
            target_type="map-entry",
            algorithms=(
                AlgorithmProfile(
                    instance_id="map-card-template",
                    algorithm_id="template",
                    parameters={"threshold": 0.78},
                ),
                AlgorithmProfile(
                    instance_id="map-name-ocr",
                    algorithm_id="ocr",
                    enabled=False,
                    parameters={"language": "eng"},
                ),
            ),
            confirmation_frames=2,
            metadata={"owner": "ui"},
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "map-entry.json"
            save_target_profile(path, profile)
            loaded = load_target_profile(path)

        self.assertEqual(profile, loaded)
        self.assertEqual("ui", loaded.metadata["owner"])

    def test_profile_copy_does_not_share_parameter_dicts(self):
        original = TargetProfile(
            game_id="game-a",
            scene_id="scene",
            target_type="loot",
            algorithms=(AlgorithmProfile("color", "color", {"min_area": 4}),),
        )

        copied = original.copy()
        copied_algorithms = list(copied.algorithms)
        copied_algorithms[0].parameters["min_area"] = 12

        self.assertEqual(4, original.algorithms[0].parameters["min_area"])

    def test_invalid_profiles_are_rejected(self):
        with self.assertRaises(ValueError):
            TargetProfile("", "scene", "loot", ())
        with self.assertRaises(ValueError):
            TargetProfile(
                "game",
                "scene",
                "loot",
                (
                    AlgorithmProfile("same", "color"),
                    AlgorithmProfile("same", "shape"),
                ),
            )

    def test_json_contains_explicit_schema_version(self):
        profile = TargetProfile("game", "scene", "loot", ())

        payload = profile.to_dict()

        self.assertEqual(1, payload["schema_version"])
        self.assertEqual("loot", payload["target_type"])
        self.assertEqual([], payload["algorithms"])
        json.dumps(payload)


if __name__ == "__main__":
    unittest.main()
