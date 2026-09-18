import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
from PySide6.QtWidgets import QApplication

from auto_modules.core.perception.profile_store import load_target_profile, save_target_profile
from auto_modules.ui.dialogs.perception import PerceptionWorkbenchDialog


class PerceptionWorkbenchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_default_profile_is_data_driven_and_runs_on_full_frame(self):
        dialog = PerceptionWorkbenchDialog()
        image = np.zeros((80, 120, 3), dtype=np.uint8)
        image[:, :] = (40, 80, 160)
        dialog._image = image

        dialog.run_detection()

        profile = dialog._build_profile()
        self.assertEqual("default_game", profile.game_id)
        self.assertEqual("color", profile.algorithms[0].algorithm_id)
        self.assertEqual(1, len(dialog.preview._detections))
        dialog.close()

    def test_profile_editor_round_trip_preserves_instance_parameters(self):
        dialog = PerceptionWorkbenchDialog()
        dialog.game_edit.setText("poe2")
        dialog.scene_edit.setText("map")
        dialog.target_edit.setText("portal")
        dialog.merge_radius_spin.setValue(24.0)
        dialog.parameter_editor._fields["min_area"].setValue(18.0)
        profile = dialog._build_profile()

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "portal.json"
            save_target_profile(path, profile)
            restored = load_target_profile(path)

        self.assertEqual("poe2", restored.game_id)
        self.assertEqual("portal", restored.target_type)
        self.assertEqual(24.0, restored.metadata["merge_radius"])
        self.assertEqual(18.0, restored.algorithms[0].parameters["min_area"])
        dialog.close()

    def test_algorithm_selection_and_row_switch_keep_parameters_isolated(self):
        dialog = PerceptionWorkbenchDialog()
        dialog.add_algorithm()
        self.assertEqual(2, dialog.algorithm_list.count())
        dialog.algorithm_list.setCurrentRow(0)
        dialog.parameter_editor._fields["min_area"].setValue(18.0)
        dialog.algorithm_list.setCurrentRow(1)
        dialog.parameter_editor._fields["min_area"].setValue(42.0)
        dialog.algorithm_list.setCurrentRow(0)

        self.assertEqual(18.0, dialog._algorithm_profiles[0].parameters["min_area"])
        self.assertEqual(42.0, dialog._algorithm_profiles[1].parameters["min_area"])
        dialog.close()


if __name__ == "__main__":
    unittest.main()
