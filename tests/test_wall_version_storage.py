from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from auto_modules.core.map_editing.models import WallOverrideDocument
from auto_modules.core.map_editing.storage import save_wall_overrides
from auto_modules.core.map_editing.version_storage import (
    activate_wall_version,
    load_wall_version_catalog,
    migrate_legacy_wall_overrides,
    save_new_wall_version,
)


class WallVersionStorageTests(unittest.TestCase):
    def test_no_version_metadata_uses_a_copy_of_the_original_wall_layer(self) -> None:
        base = np.zeros((3, 4), dtype=np.uint8)
        base[1, 2] = 255
        with tempfile.TemporaryDirectory() as root:
            catalog = load_wall_version_catalog(Path(root), base)

        self.assertIsNone(catalog.active_version)
        np.testing.assert_array_equal(base, catalog.active_wall_layer)
        self.assertIsNot(base, catalog.active_wall_layer)

    def test_save_new_version_keeps_prior_snapshot_and_makes_new_version_active(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root)
            (folder / "config.json").write_text(json.dumps({"fps": 30}), encoding="utf-8")
            first_layer = np.zeros((4, 5), dtype=np.uint8)
            first_layer[1, 1] = 255
            first = save_new_wall_version(folder, first_layer, parent_version=None)
            first_bytes = (folder / first.file).read_bytes()

            second_layer = first_layer.copy()
            second_layer[2, 3] = 255
            second = save_new_wall_version(folder, second_layer, parent_version=first.id)
            catalog = load_wall_version_catalog(folder, first_layer)
            config = json.loads((folder / "config.json").read_text(encoding="utf-8"))

            self.assertEqual("v0001", first.id)
            self.assertEqual("v0002", second.id)
            self.assertEqual(first.id, second.parent_version)
            self.assertEqual(second.id, catalog.active_version)
            np.testing.assert_array_equal(second_layer, catalog.active_wall_layer)
            self.assertEqual(first_bytes, (folder / first.file).read_bytes())
            self.assertEqual(30, config["fps"])

            activated = activate_wall_version(folder, first.id, first_layer.shape)
            self.assertEqual(first.id, activated.id)
            self.assertEqual(first.id, load_wall_version_catalog(folder, first_layer).active_version)

    def test_migrate_legacy_masks_creates_v0001_without_changing_base_or_legacy_file(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root)
            base = np.zeros((5, 5), dtype=np.uint8)
            base[1, 1] = 255
            base_before = base.copy()
            overrides = WallOverrideDocument.empty(base.shape)
            overrides.erase_mask[1, 1] = 255
            overrides.add_mask[3, 3] = 255
            legacy_path = save_wall_overrides(folder, overrides)
            legacy_bytes = legacy_path.read_bytes()

            migrated = migrate_legacy_wall_overrides(folder, base)
            catalog = load_wall_version_catalog(folder, base)

            self.assertIsNotNone(migrated)
            self.assertEqual("v0001", migrated.id)
            self.assertEqual(migrated.id, catalog.active_version)
            self.assertEqual(0, catalog.active_wall_layer[1, 1])
            self.assertEqual(255, catalog.active_wall_layer[3, 3])
            np.testing.assert_array_equal(base_before, base)
            self.assertEqual(legacy_bytes, legacy_path.read_bytes())


if __name__ == "__main__":
    unittest.main()
