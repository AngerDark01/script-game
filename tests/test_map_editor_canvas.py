from __future__ import annotations

import os
import unittest

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from auto_modules.ui.modes.map_editor.canvas import WallEditorCanvas


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

    def test_right_button_drag_pans_the_zoomed_map_without_emitting_a_brush_stroke(self) -> None:
        strokes: list[tuple[int, int]] = []
        self.canvas.stroke_started.connect(strokes.append)
        self.canvas.set_pan_offset(QPointF(30, 40))
        self.canvas.show()
        self.app.processEvents()

        self._send_mouse(QEvent.Type.MouseButtonPress, QPointF(300, 200), Qt.MouseButton.RightButton, Qt.MouseButton.RightButton)
        self._send_mouse(QEvent.Type.MouseMove, QPointF(345, 225), Qt.MouseButton.NoButton, Qt.MouseButton.RightButton)
        self._send_mouse(QEvent.Type.MouseButtonRelease, QPointF(345, 225), Qt.MouseButton.RightButton, Qt.MouseButton.NoButton)

        self.assertEqual(QPointF(75, 65), self.canvas.pan_offset)
        self.assertEqual([], strokes)

    def _send_mouse(
        self,
        event_type: QEvent.Type,
        position: QPointF,
        button: Qt.MouseButton,
        buttons: Qt.MouseButton,
    ) -> None:
        event = QMouseEvent(
            event_type,
            position,
            position,
            position,
            button,
            Qt.MouseButtons(buttons),
            Qt.KeyboardModifier.NoModifier,
        )
        QApplication.sendEvent(self.canvas, event)


if __name__ == "__main__":
    unittest.main()
