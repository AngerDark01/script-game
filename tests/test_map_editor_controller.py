from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

import numpy as np

from auto_modules.core.map_editing.models import WallOverrideDocument
from auto_modules.core.map_editing.storage import save_wall_overrides
from auto_modules.ui.modes.map_editor.controller import MapEditorController


class MapEditorControllerTests(unittest.TestCase):
    def test_load_migrates_legacy_state_and_erase_updates_the_preview_wall_directly(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root)
            base = np.zeros((24, 24), dtype=np.uint8)
            base[8, 8] = 255
            np.savez_compressed(folder / "map_data.npz", wall_layer=base)
            legacy = WallOverrideDocument.empty(base.shape)
            legacy.add_mask[12, 12] = 255
            save_wall_overrides(folder, legacy)

            controller = MapEditorController.load(folder)

            self.assertEqual("v0001", controller.active_version_id)
            self.assertEqual(255, controller.preview_wall_layer[8, 8])
            self.assertEqual(255, controller.preview_wall_layer[12, 12])
            self.assertTrue(controller.apply_brush((8, 8), radius=1, mode="erase"))
            self.assertEqual(0, controller.preview_wall_layer[8, 8])
            self.assertTrue(controller.is_dirty)

    def test_confirm_creates_a_new_active_version_and_old_snapshot_is_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root)
            base = np.zeros((24, 24), dtype=np.uint8)
            base[8, 8] = 255
            np.savez_compressed(folder / "map_data.npz", wall_layer=base)
            controller = MapEditorController.load(folder)

            controller.apply_brush((8, 8), radius=1, mode="erase")
            first = controller.confirm_as_new_version()
            first_path = folder / first.file
            first_bytes = first_path.read_bytes()
            controller.apply_brush((12, 12), radius=1, mode="add")
            second = controller.confirm_as_new_version()

            self.assertEqual("v0001", first.id)
            self.assertEqual("v0002", second.id)
            self.assertEqual(second.id, controller.active_version_id)
            self.assertFalse(controller.is_dirty)
            self.assertEqual(first_bytes, first_path.read_bytes())
            self.assertEqual(0, controller.preview_wall_layer[8, 8])

    def test_checkout_and_activate_an_older_version_does_not_modify_any_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root)
            base = np.zeros((12, 12), dtype=np.uint8)
            base[4, 4] = 255
            np.savez_compressed(folder / "map_data.npz", wall_layer=base)
            controller = MapEditorController.load(folder)
            controller.confirm_as_new_version()
            controller.apply_brush((4, 4), radius=1, mode="erase")
            controller.confirm_as_new_version()
            second_path = folder / "wall_versions" / "v0002.npz"
            second_bytes = second_path.read_bytes()

            controller.checkout_version("v0001")
            controller.activate_checked_out_version()

            self.assertEqual("v0001", controller.active_version_id)
            self.assertEqual(255, controller.preview_wall_layer[4, 4])
            self.assertEqual(second_bytes, second_path.read_bytes())

    def test_loading_a_package_without_a_two_dimensional_wall_layer_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root)
            np.savez_compressed(folder / "map_data.npz", wall_layer=np.zeros((3, 3, 2), dtype=np.uint8))
            with self.assertRaisesRegex(ValueError, "two-dimensional"):
                MapEditorController.load(folder)


if __name__ == "__main__":
    unittest.main()
