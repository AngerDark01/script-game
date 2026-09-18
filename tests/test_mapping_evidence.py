import unittest
from unittest.mock import patch

import numpy as np

from auto_modules.core.mapping import MapStitcher
from auto_modules.core.mapping.evidence import MapFrameEvidence
from auto_modules.core.perception.models import CoordinateSpace


class MapFrameEvidenceTests(unittest.TestCase):
    def test_add_evidence_delegates_exactly_to_legacy_add_frame(self):
        image = np.zeros((12, 12, 3), dtype=np.uint8)
        match_mask = np.zeros((12, 12), dtype=np.uint8)
        save_mask = np.zeros((12, 12), dtype=np.uint8)
        fog_mask = np.zeros((12, 12), dtype=np.uint8)
        evidence = MapFrameEvidence(
            image=image,
            match_mask=match_mask,
            save_mask=save_mask,
            fog_mask=fog_mask,
            player_position=(5.0, 7.0),
            coordinate_space=CoordinateSpace.MINIMAP,
        )
        stitcher = MapStitcher(canvas_size=100)

        with patch.object(stitcher, "add_frame", return_value="added") as add_frame:
            result = stitcher.add_evidence(evidence)

        self.assertEqual("added", result)
        add_frame.assert_called_once_with(
            image,
            match_mask,
            save_mask,
            fog_mask,
            raw_gray=None,
            player_pos=(5.0, 7.0),
        )

    def test_evidence_rejects_masks_with_different_pixel_geometry(self):
        with self.assertRaises(ValueError):
            MapFrameEvidence(
                image=np.zeros((12, 12, 3), dtype=np.uint8),
                match_mask=np.zeros((12, 12), dtype=np.uint8),
                save_mask=np.zeros((11, 12), dtype=np.uint8),
                fog_mask=np.zeros((12, 12), dtype=np.uint8),
            )


if __name__ == "__main__":
    unittest.main()
