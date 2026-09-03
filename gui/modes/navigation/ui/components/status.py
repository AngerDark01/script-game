from __future__ import annotations

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy


class NavigationStatusHud(QFrame):
    """Compact status strip that keeps the legacy QLabel-like API."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setProperty("role", "status")
        self.map_value = self._value("未加载")
        self.localization_value = self._value("等待")
        self.confidence_value = self._value("--")
        self.activity_value = self._value("请选择并加载地图")
        self.message_label = QLabel("请选择并加载地图")
        self.message_label.setProperty("role", "muted")
        self.message_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(12)
        for label, value in (
            ("地图", self.map_value),
            ("定位", self.localization_value),
            ("置信度", self.confidence_value),
            ("状态", self.activity_value),
        ):
            layout.addWidget(self._field(label, value))
        layout.addWidget(self.message_label, 1)

    @staticmethod
    def _value(text: str) -> QLabel:
        label = QLabel(text)
        label.setProperty("role", "status-value")
        label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        return label

    @staticmethod
    def _field(caption: str, value: QLabel) -> QFrame:
        field = QFrame()
        field.setProperty("role", "status-field")
        layout = QHBoxLayout(field)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        title = QLabel(caption)
        title.setProperty("role", "muted")
        layout.addWidget(title)
        layout.addWidget(value)
        return field

    def setText(self, text: str) -> None:
        self.message_label.setText(str(text))
        compact = str(text)
        if len(compact) > 24:
            compact = compact[:23] + "…"
        self.activity_value.setText(compact)

    def text(self) -> str:
        return self.message_label.text()

    def set_hud_values(
        self,
        *,
        map_name: str,
        localization: str,
        confidence: float | None,
        activity: str,
    ) -> None:
        self.map_value.setText(map_name or "未加载")
        self.localization_value.setText(localization or "等待")
        self.confidence_value.setText("--" if confidence is None else f"{confidence:.2f}")
        self.setText(activity or "待命")

    def update_runtime(self, *, localized_pos, confidence: float, activity: str) -> None:
        localization = "已定位" if localized_pos is not None else "定位中"
        self.localization_value.setText(localization)
        self.confidence_value.setText(f"{confidence:.2f}")
        self.setText(activity or "跟踪中")


def build_status_label(owner) -> NavigationStatusHud:
    """Create the compact navigation status HUD."""
    owner.status_label = NavigationStatusHud(owner)
    return owner.status_label
