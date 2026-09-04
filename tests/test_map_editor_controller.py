from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

import numpy as np

from gui.modes.map_editor.controller import MapEditorController


class MapEditorControllerTests(unittest.TestCase):
    def test_controller_tracks_dirty_state_and_restores_masks_across_undo_redo_and_save(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root)
            base = np.zeros((24, 24), dtype=np.uint8)
            np.savez_compressed(folder / "map_data.npz", wall_layer=base)
            controller = MapEditorController.load(folder)

            self.assertFalse(controller.is_dirty)
            self.assertTrue(controller.apply_brush((8, 8), radius=3, mode="add"))
            self.assertTrue(controller.is_dirty)
            self.assertTrue(np.any(controller.document.add_mask))

            self.assertTrue(controller.undo())
            self.assertFalse(np.any(controller.document.add_mask))
            self.assertFalse(controller.is_dirty)
            self.assertTrue(controller.redo())
            self.assertTrue(np.any(controller.document.add_mask))

            controller.save()
            self.assertFalse(controller.is_dirty)
            reloaded = MapEditorController.load(folder)
            np.testing.assert_array_equal(reloaded.document.add_mask, controller.document.add_mask)

    def test_loading_a_package_without_a_two_dimensional_wall_layer_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root)
            np.savez_compressed(folder / "map_data.npz", wall_layer=np.zeros((3, 3, 2), dtype=np.uint8))

            with self.assertRaisesRegex(ValueError, "two-dimensional"):
                MapEditorController.load(folder)

    def test_discard_clear_and_stroke_undo_never_rewrite_the_base_package(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root)
            base = np.zeros((30, 30), dtype=np.uint8)
            base[4, 4] = 255
            np.savez_compressed(folder / "map_data.npz", wall_layer=base, unrelated=np.array([3]))
            package_before = (folder / "map_data.npz").read_bytes()
            controller = MapEditorController.load(folder)

            controller.begin_stroke()
            controller.apply_brush((10, 10), radius=3, mode="add")
            controller.apply_brush((16, 10), radius=3, mode="add")
            controller.end_stroke()
            self.assertTrue(controller.can_undo)
            self.assertTrue(controller.undo())
            self.assertFalse(np.any(controller.document.add_mask))
            self.assertTrue(controller.redo())
            self.assertTrue(np.any(controller.document.add_mask))

            controller.save()
            controller.clear_overrides()
            self.assertTrue(controller.is_dirty)
            controller.discard_changes()
            self.assertTrue(np.any(controller.document.add_mask))
            self.assertEqual(package_before, (folder / "map_data.npz").read_bytes())


if __name__ == "__main__":
    unittest.main()
