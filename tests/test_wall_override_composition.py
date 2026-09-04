from __future__ import annotations

import unittest

import numpy as np

from core.map_editing.composition import compose_effective_wall_layer
from core.map_editing.models import WallOverrideDocument


class WallOverrideCompositionTests(unittest.TestCase):
    def test_erase_and_add_masks_override_the_base_wall_without_mutating_it(self) -> None:
        base = np.array([[0, 255], [255, 0]], dtype=np.uint8)
        overrides = WallOverrideDocument.empty(base.shape)
        overrides.erase_mask[1, 0] = 255
        overrides.add_mask[1, 1] = 255

        effective = compose_effective_wall_layer(base, overrides)

        np.testing.assert_array_equal(base, [[0, 255], [255, 0]])
        np.testing.assert_array_equal(effective, [[0, 255], [0, 255]])

    def test_mismatched_override_shape_is_rejected(self) -> None:
        base = np.zeros((4, 4), dtype=np.uint8)
        overrides = WallOverrideDocument.empty((3, 4))

        with self.assertRaisesRegex(ValueError, "shape"):
            compose_effective_wall_layer(base, overrides)


if __name__ == "__main__":
    unittest.main()
