from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from gui.modes.map_editor.widget import MapEditorWidget


class MapEditorWidgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_widget_loads_draws_and_saves_one_map_without_rewriting_map_data(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            map_root = Path(root) / "map_data"
            folder = map_root / "test-route"
            folder.mkdir(parents=True)
            base = np.zeros((50, 60), dtype=np.uint8)
            np.savez_compressed(folder / "map_data.npz", wall_layer=base)
            package_before = (folder / "map_data.npz").read_bytes()
            saved_folders: list[str] = []

            widget = MapEditorWidget(map_root=map_root)
            widget.map_saved.connect(saved_folders.append)
            try:
                self.assertTrue(widget.load_selected_map())
                self.assertTrue(widget.canvas.isEnabled())

                widget.canvas.stroke_started.emit((20, 20))
                widget.canvas.stroke_extended.emit((25, 20))
                widget.canvas.stroke_finished.emit()

                self.assertTrue(widget.controller.is_dirty)
                self.assertTrue(widget.save_current_map())
                self.assertFalse(widget.controller.is_dirty)
                self.assertEqual([str(folder)], saved_folders)
                self.assertTrue((folder / "wall_overrides.npz").is_file())
                self.assertEqual(package_before, (folder / "map_data.npz").read_bytes())
                self.assertIn("重新加载此地图", widget.status_label.text())
            finally:
                widget.deleteLater()
                self.app.processEvents()


if __name__ == "__main__":
    unittest.main()
