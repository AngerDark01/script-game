"""Aspect-preserving preview label that resizes from its original frame."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel, QSizePolicy


class AspectPreviewLabel(QLabel):
    def __init__(self, message: str, parent=None) -> None:
        super().__init__(message, parent)
        self._source_pixmap: QPixmap | None = None
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.setAlignment(Qt.AlignCenter)

    def set_source_pixmap(self, pixmap: QPixmap) -> None:
        self._source_pixmap = pixmap
        self._scale_source()

    def clear_source(self, message: str) -> None:
        self._source_pixmap = None
        self.clear()
        self.setText(message)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._scale_source()

    def _scale_source(self) -> None:
        if self._source_pixmap is not None and not self._source_pixmap.isNull():
            self.setPixmap(self._source_pixmap.scaled(
                self.size(), Qt.KeepAspectRatio, Qt.FastTransformation,
            ))


__all__ = ["AspectPreviewLabel"]
