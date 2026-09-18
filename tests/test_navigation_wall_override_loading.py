from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

import numpy as np

from auto_modules.core.localization import NavigationCore
from auto_modules.core.map_editing.models import WallOverrideDocument
from auto_modules.core.map_editing.storage import save_wall_overrides


class NavigationWallOverrideLoadingTests(unittest.TestCase):
    def test_navigation_core_composes_persisted_overrides_before_building_its_obstacle_layer(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root)
            base_wall = np.zeros((8, 8), dtype=np.uint8)
            base_wall[3, 3] = 255
            np.savez_compressed(
                folder / "map_data.npz",
                wall_layer=base_wall,
                nav_wall_layer=base_wall.copy(),
                explored_map=np.zeros_like(base_wall),
                fog_layer=np.zeros_like(base_wall),
                current_pos=np.array([4.0, 4.0]),
                canvas_size=8,
            )
            overrides = WallOverrideDocument.empty(base_wall.shape)
            overrides.erase_mask[3, 3] = 255
            overrides.add_mask[1, 1] = 255
            save_wall_overrides(folder, overrides)

            core = NavigationCore(str(folder), nav_wall_erode_iterations=0)

            self.assertTrue((folder / "wall_versions" / "v0001.npz").is_file())
            self.assertEqual(core.wall_layer[3, 3], 0)
            self.assertEqual(core.wall_layer[1, 1], 255)
            self.assertEqual(core.nav_wall_layer[3, 3], 0)
            self.assertEqual(core.nav_wall_layer[1, 1], 255)


if __name__ == "__main__":
    unittest.main()
