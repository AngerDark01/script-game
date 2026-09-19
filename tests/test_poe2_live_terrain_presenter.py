import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
from PySide6.QtWidgets import QApplication

from auto_modules.ui.modes.poe2_live_terrain.presenter import present_snapshot
from auto_modules.features.poe2.live_terrain.contracts import CaptureMetadata, TerrainSnapshot


def test_presenter_preserves_yx_dimensions_and_cell_colors():
    app = QApplication.instance() or QApplication([])
    metadata = CaptureMetadata("A", "h", "A:h", 2, 2, "2026-09-19T00:00:00+00:00")
    snapshot = TerrainSnapshot(
        metadata,
        np.zeros((2, 2), dtype=np.uint8),
        np.array([[1, 0], [-1, 1]], dtype=np.int8),
        np.array([[255, 255], [0, 255]], dtype=np.uint8),
        np.array([[0, 255], [255, 0]], dtype=np.uint8),
        np.array([[255, 255], [0, 255]], dtype=np.uint8),
    )
    display = present_snapshot(snapshot)
    assert display.pixmap.size().width() == 2
    assert display.pixmap.size().height() == 2
    image = display.pixmap.toImage()
    assert image.pixelColor(0, 0).red() == 235
    assert image.pixelColor(1, 0).red() == 235
    assert image.pixelColor(0, 1).red() == 235


def test_presenter_keeps_unknown_wall_layer_pixels_black():
    app = QApplication.instance() or QApplication([])
    metadata = CaptureMetadata("A", "h", "A:h", 2, 1, "2026-09-19T00:00:00+00:00")
    snapshot = TerrainSnapshot(
        metadata,
        np.zeros((1, 2), dtype=np.uint8),
        np.array([[-1, 0]], dtype=np.int8),
        np.zeros((1, 2), dtype=np.uint8),
        np.array([[255, 255]], dtype=np.uint8),
        np.array([[0, 255]], dtype=np.uint8),
    )
    image = present_snapshot(snapshot).pixmap.toImage()
    assert image.pixelColor(0, 0).red() == 0
    assert image.pixelColor(1, 0).red() == 0


def test_presenter_fills_walkable_interior_with_legacy_gray():
    app = QApplication.instance() or QApplication([])
    metadata = CaptureMetadata("A", "h", "A:h", 3, 3, "2026-09-19T00:00:00+00:00")
    snapshot = TerrainSnapshot(
        metadata,
        np.zeros((3, 3), dtype=np.uint8),
        np.ones((3, 3), dtype=np.int8),
        np.full((3, 3), 255, dtype=np.uint8),
        np.zeros((3, 3), dtype=np.uint8),
        np.full((3, 3), 255, dtype=np.uint8),
    )
    image = present_snapshot(snapshot).pixmap.toImage()
    assert image.pixelColor(1, 1).red() == 60
    assert image.pixelColor(0, 0).red() == 235
