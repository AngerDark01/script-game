import os
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from core.localization import LocalizationResult, NavigationCore
from core.perception.models import CoordinateSpace
from core.shared.frame_registration import FrameRegistration


class LocalizationResultFacadeTests(unittest.TestCase):
    def test_typed_facade_delegates_once_and_snapshots_registration(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            np.savez_compressed(
                os.path.join(temp_dir, "map_data.npz"),
                wall_layer=np.zeros((40, 40), dtype=np.uint8),
                explored_map=np.zeros((40, 40), dtype=np.uint8),
                fog_layer=np.zeros((40, 40), dtype=np.uint8),
                current_pos=np.array([20.0, 20.0]),
                canvas_size=40,
            )
            core = NavigationCore(temp_dir)
            registration_metadata = {"forced_global": True}
            core.last_frame_registration = FrameRegistration(
                valid=True,
                confidence=0.8,
                player_global_pos=(12.5, 7.0),
                source="template_match",
                metadata=registration_metadata,
            )

            with patch.object(core, "localize", return_value=(12.5, 7.0, 0.8)) as localize:
                result = core.localize_result("frame", player_pos=(4, 5))

            localize.assert_called_once_with("frame", player_pos=(4, 5))
            self.assertEqual((12.5, 7.0), result.position)
            self.assertEqual((12.5, 7.0, 0.8), result.as_legacy_tuple())
            self.assertEqual(CoordinateSpace.GLOBAL_MAP, result.coordinate_space)
            self.assertTrue(result.is_localized)
            self.assertEqual("template_match", result.source)
            self.assertTrue(result.registration_valid)
            self.assertEqual({"forced_global": True}, result.metadata)

            registration_metadata["forced_global"] = False
            self.assertEqual({"forced_global": True}, result.metadata)


if __name__ == "__main__":
    unittest.main()
