from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

import numpy as np

from auto_modules.core.localization import NavigationCore
from auto_modules.core.map_editing.models import WallOverrideDocument
from auto_modules.core.map_editing.storage import save_wall_overrides
from auto_modules.core.map_editing.version_storage import save_new_wall_version


class NavigationWallVersionLoadingTests(unittest.TestCase):
    def test_navigation_uses_active_complete_snapshot_without_applying_legacy_masks(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root)
            base_wall = np.zeros((8, 8), dtype=np.uint8)
            base_wall[3, 3] = 255
            np.savez_compressed(
                folder / "map_data.npz",
                wall_layer=base_wall,
                explored_map=np.zeros_like(base_wall),
                fog_layer=np.zeros_like(base_wall),
                current_pos=np.array([4.0, 4.0]),
                canvas_size=8,
            )
            legacy = WallOverrideDocument.empty(base_wall.shape)
            legacy.erase_mask[3, 3] = 255
            legacy.add_mask[1, 1] = 255
            save_wall_overrides(folder, legacy)

            version_layer = np.zeros_like(base_wall)
            version_layer[3, 3] = 255
            version_layer[6, 6] = 255
            version = save_new_wall_version(folder, version_layer, parent_version=None)
            core = NavigationCore(str(folder), nav_wall_erode_iterations=0)

            self.assertEqual("v0001", version.id)
            self.assertEqual(255, core.wall_layer[3, 3])
            self.assertEqual(0, core.wall_layer[1, 1])
            self.assertEqual(255, core.wall_layer[6, 6])
            self.assertEqual(255, core.nav_wall_layer[6, 6])


if __name__ == "__main__":
    unittest.main()
