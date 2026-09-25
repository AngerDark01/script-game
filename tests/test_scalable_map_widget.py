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
