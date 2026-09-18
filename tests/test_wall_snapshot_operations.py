from __future__ import annotations

import unittest

import numpy as np

from auto_modules.core.map_editing.snapshot_operations import WallLayerPatch, apply_wall_brush


class WallSnapshotOperationTests(unittest.TestCase):
    def test_erase_changes_the_final_layer_to_black_and_patch_restores_it(self) -> None:
        layer = np.zeros((20, 20), dtype=np.uint8)
        layer[10, 10] = 255

        patch = apply_wall_brush(layer, center=(10, 10), radius=1, mode="erase")

        self.assertIsInstance(patch, WallLayerPatch)
        self.assertEqual(0, layer[10, 10])
        patch.undo(layer)
        self.assertEqual(255, layer[10, 10])
        patch.redo(layer)
        self.assertEqual(0, layer[10, 10])

    def test_add_clips_at_edges_and_unknown_mode_is_rejected(self) -> None:
        layer = np.zeros((5, 5), dtype=np.uint8)

        patch = apply_wall_brush(layer, center=(0, 0), radius=2, mode="add")

        self.assertIsNotNone(patch)
        self.assertEqual(255, layer[0, 0])
        self.assertEqual(255, layer[1, 0])
        self.assertEqual(0, layer[4, 4])
        with self.assertRaisesRegex(ValueError, "unknown"):
            apply_wall_brush(layer, center=(0, 0), radius=1, mode="invalid")


if __name__ == "__main__":
    unittest.main()
