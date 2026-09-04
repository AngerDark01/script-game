from __future__ import annotations

import os
import unittest

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QApplication

from gui.modes.map_editor.canvas import WallEditorCanvas


class WallEditorCanvasTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.canvas = WallEditorCanvas()
        self.canvas.resize(800, 600)
        base = np.zeros((100, 200), dtype=np.uint8)
        self.canvas.set_map_layers(base, np.zeros_like(base), np.zeros_like(base))

    def tearDown(self) -> None:
        self.canvas.deleteLater()
        self.app.processEvents()

    def test_canvas_maps_view_positions_to_original_map_coordinates_after_zoom(self) -> None:
        self.canvas.set_zoom(2.0)
        self.canvas.set_pan_offset(QPointF(30, 40))

        self.assertEqual((20, 15), self.canvas.map_point_from_view(QPointF(70, 70)))
        self.assertIsNone(self.canvas.map_point_from_view(QPointF(10, 10)))

    def test_drag_interpolation_never_leaves_more_than_half_radius_between_emitted_points(self) -> None:
        points: list[tuple[int, int]] = []
        self.canvas.stroke_extended.connect(points.append)
        self.canvas.set_tool("add", 8)

        self.canvas._emit_interpolated_points((0, 0), (20, 0))

        self.assertEqual([(4, 0), (8, 0), (12, 0), (16, 0), (20, 0)], points)


if __name__ == "__main__":
    unittest.main()
