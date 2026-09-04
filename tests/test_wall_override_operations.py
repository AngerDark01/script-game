from __future__ import annotations

import unittest

import numpy as np

from core.map_editing.models import WallOverrideDocument
from core.map_editing.operations import apply_circular_brush


class WallOverrideOperationTests(unittest.TestCase):
    def test_erase_clears_add_mask_at_same_pixels_and_patches_are_reversible(self) -> None:
        document = WallOverrideDocument.empty((20, 20))

        add_patch = apply_circular_brush(document, center=(10, 10), radius=2, mode="add")
        erase_patch = apply_circular_brush(document, center=(10, 10), radius=2, mode="erase")

        self.assertIsNotNone(add_patch)
        self.assertIsNotNone(erase_patch)
        self.assertTrue(np.any(document.erase_mask))
        self.assertFalse(np.any(document.add_mask))

        erase_patch.undo(document)
        self.assertTrue(np.any(document.add_mask))
        self.assertFalse(np.any(document.erase_mask))
        add_patch.undo(document)
        self.assertFalse(np.any(document.add_mask))
        self.assertFalse(np.any(document.erase_mask))

    def test_brush_clips_to_map_edges_and_rejects_unknown_modes(self) -> None:
        document = WallOverrideDocument.empty((4, 4))

        patch = apply_circular_brush(document, center=(0, 0), radius=2, mode="add")

        self.assertIsNotNone(patch)
        self.assertEqual(document.add_mask.shape, (4, 4))
        self.assertEqual(document.add_mask[0, 0], 255)
        with self.assertRaisesRegex(ValueError, "mode"):
            apply_circular_brush(document, center=(1, 1), radius=1, mode="unknown")


if __name__ == "__main__":
    unittest.main()
