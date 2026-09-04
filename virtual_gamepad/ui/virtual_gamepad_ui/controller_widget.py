from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Signal, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from .models import BindingProfile, CONTROLS, StateSnapshot


WORKBENCH_WINDOW = QColor("#0B1220")
WORKBENCH_SURFACE = QColor("#0F1A28")
WORKBENCH_BODY = QColor("#16263A")
WORKBENCH_PANEL = QColor("#101D2E")
WORKBENCH_BORDER = QColor("#2C4159")
WORKBENCH_MUTED = QColor("#91A4B8")
WORKBENCH_PRIMARY = QColor("#38BDF8")
WORKBENCH_SUCCESS = QColor("#22C55E")
WORKBENCH_SELECTED = QColor("#F8C04B")
CANVAS_WIDTH = 880.0
CANVAS_HEIGHT = 490.0

BUTTON_COLOURS = {
    "A": QColor("#3BCB75"),
    "B": QColor("#E65B63"),
    "X": QColor("#4D9BFF"),
    "Y": QColor("#F6C95B"),
}


class ControllerWidget(QWidget):
    """A compact Xbox-style controller canvas with clickable virtual controls."""

    control_clicked = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(620, 390)
        self.setMouseTracking(True)
        self._state = StateSnapshot()
        self._profile = BindingProfile()
        self._selected_control = "A"
        self._hitboxes: dict[str, QRectF] = {}
        self._scale = 1.0
        self._offset = QPointF(0, 0)

    def set_snapshot(self, state: StateSnapshot) -> None:
        self._state = state
        self.update()

    def set_profile(self, profile: BindingProfile) -> None:
        self._profile = profile
        self.update()

    def set_selected_control(self, control: str) -> None:
        if control in CONTROLS and self._selected_control != control:
            self._selected_control = control
            self.update()

    def _active(self, control: str) -> bool:
        if control in ("LeftStick", "RightStick"):
            x, y = self._state.axis(control)
            return abs(x) > 1500 or abs(y) > 1500
        if control == "LeftTrigger":
            return self._state.left_trigger > 8
        if control == "RightTrigger":
            return self._state.right_trigger > 8
        return self._state.is_pressed(control)

    @staticmethod
    def _truncate(text: str, limit: int = 24) -> str:
        return text if len(text) <= limit else f"{text[:limit - 1]}…"

    def _binding_text(self, control: str) -> str:
        sources = self._profile.bindings.get(control, [])
        if not sources:
            return "未绑定"
        readable: list[str] = []
        mouse_labels = {
            "mouse:left": "鼠标左键",
            "mouse:right": "鼠标右键",
            "mouse:middle": "鼠标中键",
            "mouse:x1": "鼠标侧键 1",
            "mouse:x2": "鼠标侧键 2",
            "mouse:move_x": "鼠标 X",
            "mouse:move_y": "鼠标 Y",
        }
        for source in sources:
            normalized = source.casefold()
            if normalized.startswith("keyboard:"):
                readable.append(source.split(":", 1)[1])
            else:
                readable.append(mouse_labels.get(normalized, source))
        return self._truncate(" + ".join(readable))

    def _group_text(self, entries: tuple[tuple[str, str], ...], limit: int = 30) -> str:
        parts = [f"{label} {self._binding_text(control)}" for label, control in entries]
        return self._truncate(" · ".join(parts), limit)

    def _control_colours(self, control: str, base: QColor | None = None) -> tuple[QColor, QColor, QColor]:
        active = self._active(control)
        selected = self._selected_control == control
        fill = QColor(base or WORKBENCH_BORDER)
        fill.setAlpha(205)
        if active:
            fill = QColor(WORKBENCH_PRIMARY)
        elif selected:
            fill = QColor("#17415D")
        border = WORKBENCH_SELECTED if selected else (WORKBENCH_SUCCESS if active else WORKBENCH_BORDER)
        text = WORKBENCH_WINDOW if active else QColor("#DDE8F3")
        return fill, border, text

    def _draw_control(
        self,
        painter: QPainter,
        control: str,
        rect: QRectF,
        label: str,
        *,
        shape: str = "round",
        base: QColor | None = None,
        font_size: int = 10,
    ) -> None:
        fill, border, text = self._control_colours(control, base)
        self._hitboxes[control] = rect
        painter.setPen(QPen(border, 3 if self._selected_control == control else 2))
        painter.setBrush(QBrush(fill))
        if shape == "ellipse":
            painter.drawEllipse(rect)
        else:
            radius = min(rect.width(), rect.height()) * 0.28
            painter.drawRoundedRect(rect, radius, radius)
        painter.setPen(QPen(text))
        painter.setFont(QFont("Segoe UI", font_size, QFont.Weight.Bold))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, label)

    def _draw_binding_pill(self, painter: QPainter, rect: QRectF, text: str) -> None:
        painter.setPen(QPen(QColor("#273D55"), 1))
        painter.setBrush(QBrush(QColor("#0B1624")))
        painter.drawRoundedRect(rect, rect.height() / 2, rect.height() / 2)
        painter.setPen(QPen(WORKBENCH_MUTED))
        painter.setFont(QFont("Segoe UI", 8))
        painter.drawText(rect.adjusted(8, 0, -8, 0), Qt.AlignmentFlag.AlignCenter, text)

    def _draw_stick(self, painter: QPainter, control: str, rect: QRectF, click_control: str, click_rect: QRectF) -> None:
        self._draw_control(painter, control, rect, "LS" if control == "LeftStick" else "RS", shape="ellipse", font_size=12)
        x, y = self._state.axis(control)
        displacement = min(rect.width() * 0.23, rect.width() * max(abs(x), abs(y)) / 32767.0 * 0.30)
        centre = rect.center()
        if displacement:
            magnitude = max(abs(x), abs(y), 1)
            centre += QPointF(displacement * x / magnitude, -displacement * y / magnitude)
        painter.setPen(QPen(QColor("#7DD3FC"), 1))
        painter.setBrush(QBrush(WORKBENCH_PRIMARY if self._active(control) else QColor("#35516E")))
        indicator = rect.width() * 0.15
        painter.drawEllipse(QRectF(centre.x() - indicator, centre.y() - indicator, indicator * 2, indicator * 2))
        self._draw_control(painter, click_control, click_rect, "L3" if click_control == "LeftStickClick" else "R3", font_size=8)

    def _draw_controller_body(self, painter: QPainter) -> None:
        outer = QPainterPath()
        outer.moveTo(272, 108)
        outer.cubicTo(203, 89, 125, 111, 88, 173)
        outer.cubicTo(49, 239, 62, 345, 127, 402)
        outer.cubicTo(183, 451, 258, 429, 320, 366)
        outer.cubicTo(364, 379, 516, 379, 560, 366)
        outer.cubicTo(622, 429, 697, 451, 753, 402)
        outer.cubicTo(818, 345, 831, 239, 792, 173)
        outer.cubicTo(755, 111, 677, 89, 608, 108)
        outer.cubicTo(538, 129, 342, 129, 272, 108)
        outer.closeSubpath()
        painter.setPen(QPen(WORKBENCH_BORDER, 4))
        painter.setBrush(QBrush(WORKBENCH_BODY))
        painter.drawPath(outer)

        inner = QPainterPath()
        inner.addRoundedRect(QRectF(270, 151, 340, 198), 82, 82)
        painter.setPen(QPen(QColor("#243B54"), 2))
        painter.setBrush(QBrush(WORKBENCH_PANEL))
        painter.drawPath(inner)

        painter.setPen(QPen(QColor("#3A556F"), 2))
        painter.drawLine(QPointF(260, 134), QPointF(620, 134))

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), WORKBENCH_SURFACE)
        self._hitboxes = {}
        scale = min(max(self.width(), 1) / CANVAS_WIDTH, max(self.height(), 1) / CANVAS_HEIGHT)
        self._scale = max(scale, 0.01)
        self._offset = QPointF(
            (self.width() - CANVAS_WIDTH * self._scale) / 2,
            (self.height() - CANVAS_HEIGHT * self._scale) / 2,
        )
        painter.save()
        painter.translate(self._offset)
        painter.scale(self._scale, self._scale)

        painter.setPen(QPen(QColor("#B8C7D9")))
        painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        painter.drawText(QRectF(48, 16, 280, 24), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "XBOX 360 · 映射预览")
        painter.setPen(QPen(WORKBENCH_MUTED))
        painter.setFont(QFont("Segoe UI", 9))
        painter.drawText(QRectF(540, 16, 290, 24), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, "点选控件以编辑其输入绑定")

        self._draw_controller_body(painter)
        self._draw_control(painter, "LeftTrigger", QRectF(204, 52, 126, 35), "LT", font_size=9)
        self._draw_control(painter, "RightTrigger", QRectF(550, 52, 126, 35), "RT", font_size=9)
        self._draw_control(painter, "LeftShoulder", QRectF(112, 92, 180, 40), "LB", font_size=10)
        self._draw_control(painter, "RightShoulder", QRectF(588, 92, 180, 40), "RB", font_size=10)
        self._draw_binding_pill(painter, QRectF(114, 141, 178, 24), self._group_text((("LT", "LeftTrigger"), ("LB", "LeftShoulder")), 25))
        self._draw_binding_pill(painter, QRectF(588, 141, 178, 24), self._group_text((("RT", "RightTrigger"), ("RB", "RightShoulder")), 25))

        self._draw_control(painter, "DPadUp", QRectF(159, 205, 48, 55), "↑", font_size=15)
        self._draw_control(painter, "DPadLeft", QRectF(108, 258, 55, 48), "←", font_size=15)
        self._draw_control(painter, "DPadRight", QRectF(203, 258, 55, 48), "→", font_size=15)
        self._draw_control(painter, "DPadDown", QRectF(159, 304, 48, 55), "↓", font_size=15)

        self._draw_stick(painter, "LeftStick", QRectF(296, 224, 112, 112), "LeftStickClick", QRectF(313, 346, 78, 27))
        self._draw_stick(painter, "RightStick", QRectF(478, 260, 112, 112), "RightStickClick", QRectF(495, 382, 78, 27))
        self._draw_control(painter, "Back", QRectF(398, 202, 50, 30), "VIEW", font_size=7)
        self._draw_control(painter, "Start", QRectF(456, 202, 50, 30), "MENU", font_size=7)

        self._draw_control(painter, "Y", QRectF(689, 203, 47, 47), "Y", shape="ellipse", base=BUTTON_COLOURS["Y"], font_size=12)
        self._draw_control(painter, "X", QRectF(637, 253, 47, 47), "X", shape="ellipse", base=BUTTON_COLOURS["X"], font_size=12)
        self._draw_control(painter, "B", QRectF(741, 253, 47, 47), "B", shape="ellipse", base=BUTTON_COLOURS["B"], font_size=12)
        self._draw_control(painter, "A", QRectF(689, 303, 47, 47), "A", shape="ellipse", base=BUTTON_COLOURS["A"], font_size=12)

        self._draw_binding_pill(
            painter,
            QRectF(89, 377, 180, 26),
            self._group_text((("↑", "DPadUp"), ("←", "DPadLeft"), ("↓", "DPadDown"), ("→", "DPadRight")), 27),
        )
        self._draw_binding_pill(
            painter,
            QRectF(276, 414, 150, 26),
            self._group_text((("LS", "LeftStick"), ("L3", "LeftStickClick")), 22),
        )
        self._draw_binding_pill(
            painter,
            QRectF(624, 377, 170, 26),
            self._group_text((("Y", "Y"), ("X", "X"), ("B", "B"), ("A", "A")), 25),
        )
        self._draw_binding_pill(
            painter,
            QRectF(461, 439, 150, 26),
            self._group_text((("RS", "RightStick"), ("R3", "RightStickClick")), 22),
        )

        painter.setPen(QPen(WORKBENCH_MUTED))
        painter.setFont(QFont("Segoe UI", 9))
        painter.drawText(QRectF(80, 466, 720, 18), Qt.AlignmentFlag.AlignCenter, "高亮边框表示当前正在编辑的虚拟控件")
        painter.restore()

    def mousePressEvent(self, event) -> None:
        if self._scale <= 0:
            return super().mousePressEvent(event)
        position = event.position()
        point = QPointF(
            (position.x() - self._offset.x()) / self._scale,
            (position.y() - self._offset.y()) / self._scale,
        )
        for control, rect in reversed(tuple(self._hitboxes.items())):
            if rect.contains(point):
                self.control_clicked.emit(control)
                return
        super().mousePressEvent(event)
