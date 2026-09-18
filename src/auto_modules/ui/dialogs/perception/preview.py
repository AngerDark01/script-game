from __future__ import annotations

from typing import Iterable

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget

from auto_modules.core.perception.models import TargetDetection


class DetectionPreview(QWidget):
    """Pixmap canvas that renders normalized detection boxes without owning detection logic."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pixmap = QPixmap()
        self._source_size = (0, 0)
        self._detections: tuple[TargetDetection, ...] = ()
        self.setMinimumSize(420, 300)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)

    def set_image(self, pixmap: QPixmap, source_size: tuple[int, int] | None = None) -> None:
        self._pixmap = pixmap
        if source_size:
            self._source_size = source_size
        elif not pixmap.isNull():
            self._source_size = (pixmap.width(), pixmap.height())
        self.update()

    def set_detections(self, detections: Iterable[TargetDetection]) -> None:
        self._detections = tuple(detections)
        self.update()

    def clear(self) -> None:
        self._pixmap = QPixmap()
        self._source_size = (0, 0)
        self._detections = ()
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#071019"))
        if self._pixmap.isNull():
            painter.setPen(QColor("#91A4B8"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Load an image to test a profile")
            return

        target = self._pixmap.size()
        target.scale(self.size(), Qt.AspectRatioMode.KeepAspectRatio)
        x = (self.width() - target.width()) / 2.0
        y = (self.height() - target.height()) / 2.0
        dest = QRectF(x, y, target.width(), target.height())
        painter.drawPixmap(dest, self._pixmap, self._pixmap.rect())

        source_width, source_height = self._source_size
        if source_width <= 0 or source_height <= 0:
            return
        scale_x = target.width() / source_width
        scale_y = target.height() / source_height
        painter.setFont(painter.font())
        for index, detection in enumerate(self._detections, start=1):
            bbox = detection.bbox
            if bbox is None:
                continue
            rect = QRectF(
                x + bbox.left * scale_x,
                y + bbox.top * scale_y,
                bbox.width * scale_x,
                bbox.height * scale_y,
            )
            color = QColor("#38BDF8") if detection.source != "fused" else QColor("#22C55E")
            painter.setPen(QPen(color, 2))
            painter.drawRect(rect)
            painter.drawText(rect.adjusted(4, 16, -4, -4), f"#{index} {detection.confidence:.2f}")
