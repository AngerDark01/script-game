import unittest

import numpy as np

from core.stitcher_core import MapStitcher


class MapStitcherTest(unittest.TestCase):
    def test_precise_visibility_mask_uses_fog_shape_instead_of_full_rect(self):
        stitcher = MapStitcher(canvas_size=60, draw_scale=1.0)
        save_mask = np.zeros((10, 10), dtype=np.uint8)
        save_mask[4:6, 4:6] = 255
        fog_mask = np.zeros((10, 10), dtype=np.uint8)
        fog_mask[2:8, 2:8] = 255

        stitcher._merge_frame_weighted(save_mask, fog_mask, 10, 10, 5, 5, force=True)

        self.assertEqual(stitcher.explored_map[25, 25], 0)
        self.assertEqual(stitcher.explored_map[27, 27], 255)
        self.assertEqual(stitcher.fog_layer[27, 27], 255)

    def test_visibility_falls_back_to_full_rect_when_fog_mask_is_too_small(self):
        stitcher = MapStitcher(canvas_size=60, draw_scale=1.0)
        save_mask = np.zeros((10, 10), dtype=np.uint8)
        save_mask[4:6, 4:6] = 255
        fog_mask = np.zeros((10, 10), dtype=np.uint8)
        fog_mask[5, 5] = 255

        stitcher._merge_frame_weighted(save_mask, fog_mask, 10, 10, 5, 5, force=True)

        self.assertEqual(stitcher.explored_map[25, 25], 255)
        self.assertEqual(stitcher.fog_layer[25, 25], 0)


if __name__ == "__main__":
    unittest.main()
