from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from auto_modules.core.map_editing.models import WallOverrideDocument
from auto_modules.core.map_editing.storage import load_wall_overrides, save_wall_overrides


class WallOverrideStorageTests(unittest.TestCase):
    def test_save_round_trips_masks_and_preserves_unrelated_config_fields(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root)
            (folder / "config.json").write_text(
                json.dumps({"fps": 30, "recognizer_params": {"enable_wall": True}}),
                encoding="utf-8",
            )
            document = WallOverrideDocument.empty((4, 5))
            document.add_mask[1, 2] = 255
            document.erase_mask[3, 4] = 255

            saved_path = save_wall_overrides(folder, document)
            saved_config = json.loads((folder / "config.json").read_text(encoding="utf-8"))
            loaded = load_wall_overrides(folder, (4, 5))

            self.assertEqual(saved_path, folder / "wall_overrides.npz")
            self.assertEqual(saved_config["fps"], 30)
            self.assertTrue(saved_config["recognizer_params"]["enable_wall"])
            self.assertEqual(saved_config["wall_overrides"]["file"], "wall_overrides.npz")
            np.testing.assert_array_equal(loaded.add_mask, document.add_mask)
            np.testing.assert_array_equal(loaded.erase_mask, document.erase_mask)

    def test_missing_metadata_returns_an_empty_document_but_declared_missing_file_is_an_error(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root)
            loaded = load_wall_overrides(folder, (3, 3))
            self.assertFalse(np.any(loaded.add_mask))

            (folder / "config.json").write_text(
                json.dumps({"wall_overrides": {"enabled": True, "file": "wall_overrides.npz", "format_version": 1}}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "missing"):
                load_wall_overrides(folder, (3, 3))


if __name__ == "__main__":
    unittest.main()
