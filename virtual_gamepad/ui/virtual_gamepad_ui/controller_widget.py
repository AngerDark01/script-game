from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Signal, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget

from .models import BindingProfile, CONTROLS, StateSnapshot


class ControllerWidget(QWidget):
    control_clicked = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(700, 410)
        self.setMouseTracking(True)
        self._state = StateSnapshot()
        self._profile = BindingProfile()
        self._hitboxes: dict[str, QRectF] = {}
        self._scale = 1.0
        self._offset = QPointF(0, 0)

    def set_snapshot(self, state: StateSnapshot) -> None:
        self._state = state
        self.update()

    def set_profile(self, profile: BindingProfile) -> None:
        self._profile = profile
        self.update()

    def _active(self, control: str) -> bool:
        if control in CONTROLS:
            if control in ("LeftStick", "RightStick"):
                x, y = self._state.axis(control)
                return abs(x) > 1500 or abs(y) > 1500
            if control == "LeftTrigger":
                return self._state.left_trigger > 8
            if control == "RightTrigger":
                return self._state.right_trigger > 8
            return self._state.is_pressed(control)
        return False

    def _control(self, painter: QPainter, name: str, rect: QRectF, label: str | None = None) -> None:
        active = self._active(name)
        self._hitboxes[name] = rect
        painter.setPen(QPen(QColor("#17202a"), 2))
        painter.setBrush(QBrush(QColor("#19a974") if active else QColor("#d9e0e6")))
        painter.drawEllipse(rect)
        painter.setPen(QPen(QColor("#ffffff") if active else QColor("#17202a")))
        painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, label or name)
        binding = self._profile.label_for(name)
        painter.setPen(QPen(QColor("#52616b")))
        painter.setFont(QFont("Segoe UI", 8))
        painter.drawText(QRectF(rect.left() - 35, rect.bottom() + 4, rect.width() + 70, 18), Qt.AlignmentFlag.AlignCenter, binding)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#f5f7f9"))
        self._hitboxes = {}
        scale = min(self.width() / 820.0, self.height() / 460.0)
        self._scale = scale
        self._offset = QPointF((self.width() - 820 * scale) / 2, (self.height() - 460 * scale) / 2)
        painter.save()
        painter.translate(self._offset)
        painter.scale(scale, scale)

        painter.setPen(QPen(QColor("#17202a"), 3))
        painter.setBrush(QBrush(QColor("#ffffff")))
        painter.drawRoundedRect(QRectF(58, 65, 704, 310), 74, 74)
        painter.setBrush(QBrush(QColor("#eef2f5")))
        painter.drawRoundedRect(QRectF(235, 80, 350, 280), 105, 105)

        self._control(painter, "LeftShoulder", QRectF(135, 40, 110, 36), "LB")
        self._control(painter, "RightShoulder", QRectF(575, 40, 110, 36), "RB")
        self._control(painter, "LeftTrigger", QRectF(250, 25, 120, 35), "LT")
        self._control(painter, "RightTrigger", QRectF(450, 25, 120, 35), "RT")

        for name, x, y, label in (("DPadUp", 158, 162, "U"), ("DPadDown", 158, 230, "D"), ("DPadLeft", 124, 196, "L"), ("DPadRight", 192, 196, "R")):
            self._control(painter, name, QRectF(x, y, 34, 34), label)
        self._control(painter, "LeftStick", QRectF(270, 205, 84, 84), "LS")
        self._control(painter, "RightStick", QRectF(466, 205, 84, 84), "RS")

        self._control(painter, "Y", QRectF(650, 140, 40, 40), "Y")
        self._control(painter, "X", QRectF(610, 180, 40, 40), "X")
        self._control(painter, "B", QRectF(690, 180, 40, 40), "B")
        self._control(painter, "A", QRectF(650, 220, 40, 40), "A")
        self._control(painter, "Back", QRectF(365, 155, 38, 28), "Back")
        self._control(painter, "Start", QRectF(417, 155, 38, 28), "Start")

        painter.setPen(QPen(QColor("#52616b")))
        painter.setFont(QFont("Segoe UI", 9))
        painter.drawText(QRectF(80, 405, 660, 22), Qt.AlignmentFlag.AlignCenter, "Click a control to edit its binding")
        painter.restore()

    def mousePressEvent(self, event) -> None:
        position = event.position()
        point = QPointF(
            (position.x() - self._offset.x()) / self._scale,
            (position.y() - self._offset.y()) / self._scale,
        )
        for control, rect in self._hitboxes.items():
            if rect.contains(point):
                self.control_clicked.emit(control)
                return
        super().mousePressEvent(event)
