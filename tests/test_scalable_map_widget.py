import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSize
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication

from auto_modules.ui.widgets.scalable_map import ScalableMapWidget


def test_focus_on_point_zooms_and_centers_source_coordinate():
    app = QApplication.instance() or QApplication([])
    widget = ScalableMapWidget()
    widget.resize(320, 240)
    widget.show()
    pixmap = QPixmap(QSize(1000, 800))
    pixmap.fill()
    widget.set_image(pixmap)
    app.processEvents()

    widget.focus_on_point((700.0, 500.0), zoom_multiplier=2.0)

    assert widget.scale_factor > 0.0
    assert widget.current_pixmap.size().width() == int(round(1000 * widget.scale_factor))
    assert widget.scroll_area.horizontalScrollBar().value() >= 0
    assert widget.scroll_area.verticalScrollBar().value() >= 0
    widget.close()


def test_set_target_preserves_existing_overlay_markers():
    app = QApplication.instance() or QApplication([])
    widget = ScalableMapWidget()
    widget.set_image(QPixmap(QSize(100, 80)))
    widget.set_overlay(position=(10.0, 12.0), candidates=((20.0, 22.0),))

    widget.set_target((30.0, 32.0))

    assert widget.overlay_label._position == (10.0, 12.0)
    assert widget.overlay_label._candidates == ((20.0, 22.0),)
    assert widget.overlay_label._target == (30.0, 32.0)
    widget.close()


def test_overlay_geometry_tracks_image_label_resize():
    app = QApplication.instance() or QApplication([])
    widget = ScalableMapWidget()
    widget.resize(320, 240)
    widget.show()
    pixmap = QPixmap(QSize(100, 80))
    pixmap.fill()
    widget.set_image(pixmap)
    app.processEvents()

    widget.resize(620, 460)
    app.processEvents()

    assert widget.overlay_label.geometry() == widget.image_label.rect()
    widget.close()
