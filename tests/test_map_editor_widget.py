from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QScrollArea

from auto_modules.ui.modes.map_editor.widget import MapEditorWidget


class MapEditorWidgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_widget_erases_the_preview_to_black_and_confirms_a_new_navigation_version(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            map_root = Path(root) / "map_data"
            folder = map_root / "test-route"
            folder.mkdir(parents=True)
            base = np.zeros((50, 60), dtype=np.uint8)
            base[20, 20] = 255
            np.savez_compressed(folder / "map_data.npz", wall_layer=base)
            package_before = (folder / "map_data.npz").read_bytes()
            saved_folders: list[str] = []

            widget = MapEditorWidget(map_root=map_root)
            widget.map_saved.connect(saved_folders.append)
            try:
                self.assertTrue(widget.load_selected_map())
                self.assertIsNone(widget.controller.active_version_id)

                widget.erase_wall_button.setChecked(True)
                widget.canvas.stroke_started.emit((20, 20))
                widget.canvas.stroke_finished.emit()

                self.assertEqual(0, widget.controller.preview_wall_layer[20, 20])
                self.assertFalse(np.any(widget.canvas._erase_array))
                self.assertTrue(widget.save_current_map())
                self.assertEqual("v0001", widget.controller.active_version_id)
                self.assertEqual([str(folder)], saved_folders)
                self.assertTrue((folder / "wall_versions" / "v0001.npz").is_file())
                self.assertEqual(package_before, (folder / "map_data.npz").read_bytes())
                self.assertIn("当前导航版本", widget.active_version_label.text())
            finally:
                widget.deleteLater()
                self.app.processEvents()

    def test_compact_height_keeps_the_sidebar_readable_in_a_vertical_scroll_area(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            widget = MapEditorWidget(map_root=Path(root) / "map_data")
            try:
                widget.resize(920, 350)
                widget.show()
                self.app.processEvents()

                self.assertIsInstance(widget.sidebar_scroll, QScrollArea)
                self.assertGreater(widget.sidebar_scroll.verticalScrollBar().maximum(), 0)
                self.assertFalse(
                    widget.add_wall_button.geometry().intersects(
                        widget.erase_wall_button.geometry()
                    )
                )
            finally:
                widget.deleteLater()
                self.app.processEvents()


if __name__ == "__main__":
    unittest.main()
