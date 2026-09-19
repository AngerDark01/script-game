"""Independent PoE2 monitor configuration dialog."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QDoubleSpinBox,
    QVBoxLayout,
)

from auto_modules.features.poe2.live_terrain import (
    Poe2MonitorConfig,
    Poe2MonitorConfigStore,
)
from auto_modules.core.spatial.monitor_binding import CaptureRect, MonitorBinding


class Poe2MonitorConfigDialog(QDialog):
    config_saved = Signal(object)

    def __init__(
        self,
        *,
        config: Poe2MonitorConfig | None = None,
        config_store: Poe2MonitorConfigStore | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("PoE2 监控配置")
        self.config_store = config_store
        self.config = config or (config_store.load() if config_store is not None else Poe2MonitorConfig())
        self._binding = self.config.binding
        self._build_ui()
        self._load_config(self.config)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.addWidget(QLabel("PoE2 小地图监控区域与定位参数"))

        region_group = QGroupBox("监控区域（物理桌面像素）")
        region_form = QFormLayout(region_group)
        self.left_spin = self._integer_spin(-100000, 100000)
        self.top_spin = self._integer_spin(-100000, 100000)
        self.width_spin = self._integer_spin(1, 10000)
        self.height_spin = self._integer_spin(1, 10000)
        region_form.addRow("左", self.left_spin)
        region_form.addRow("上", self.top_spin)
        region_form.addRow("宽", self.width_spin)
        region_form.addRow("高", self.height_spin)
        self.binding_label = QLabel("未绑定")
        region_form.addRow("状态", self.binding_label)
        root.addWidget(region_group)

        self.search_radius_spin = self._integer_spin(1, 5000)
        self.match_threshold_spin = QDoubleSpinBox()
        self.match_threshold_spin.setRange(0.0, 1.0)
        self.match_threshold_spin.setSingleStep(0.01)
        self.match_threshold_spin.setDecimals(2)
        self.sample_interval_spin = self._integer_spin(10, 5000)
        form = QFormLayout()
        form.addRow("局部搜索半径", self.search_radius_spin)
        form.addRow("匹配阈值", self.match_threshold_spin)
        form.addRow("采样间隔（毫秒）", self.sample_interval_spin)
        root.addLayout(form)

        actions = QHBoxLayout()
        self.bind_button = QPushButton("应用区域")
        self.bind_button.clicked.connect(self.apply_region)
        actions.addWidget(self.bind_button)
        actions.addStretch()
        root.addLayout(actions)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.save)
        self.buttons.rejected.connect(self.reject)
        root.addWidget(self.buttons)

    @staticmethod
    def _integer_spin(minimum: int, maximum: int) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(minimum, maximum)
        return spin

    def _load_config(self, config: Poe2MonitorConfig) -> None:
        self.search_radius_spin.setValue(config.search_radius)
        self.match_threshold_spin.setValue(config.match_threshold)
        self.sample_interval_spin.setValue(config.sample_interval_ms)
        if config.binding is not None:
            rect = config.binding.rect
            self.left_spin.setValue(rect.left)
            self.top_spin.setValue(rect.top)
            self.width_spin.setValue(rect.width)
            self.height_spin.setValue(rect.height)
            self._update_binding_label(config.binding)

    def apply_region(self) -> None:
        self._binding = MonitorBinding(
            CaptureRect(
                self.left_spin.value(),
                self.top_spin.value(),
                self.width_spin.value(),
                self.height_spin.value(),
            )
        )
        self._update_binding_label(self._binding)

    def set_binding(self, binding: MonitorBinding | None) -> None:
        self._binding = binding
        if binding is not None:
            rect = binding.rect
            self.left_spin.setValue(rect.left)
            self.top_spin.setValue(rect.top)
            self.width_spin.setValue(rect.width)
            self.height_spin.setValue(rect.height)
        self._update_binding_label(binding)

    def _update_binding_label(self, binding: MonitorBinding | None) -> None:
        self.binding_label.setText(
            "未绑定" if binding is None else str(binding.rect.as_dict())
        )

    def current_config(self) -> Poe2MonitorConfig:
        return Poe2MonitorConfig(
            binding=self._binding,
            search_radius=self.search_radius_spin.value(),
            match_threshold=self.match_threshold_spin.value(),
            sample_interval_ms=self.sample_interval_spin.value(),
        )

    def save(self) -> None:
        self.config = self.current_config()
        if self.config_store is not None:
            self.config_store.save(self.config)
        self.config_saved.emit(self.config)
        self.accept()

    def set_editable(self, enabled: bool) -> None:
        for widget in (
            self.left_spin,
            self.top_spin,
            self.width_spin,
            self.height_spin,
            self.search_radius_spin,
            self.match_threshold_spin,
            self.sample_interval_spin,
            self.bind_button,
        ):
            widget.setEnabled(bool(enabled))
        self.buttons.button(QDialogButtonBox.Save).setEnabled(bool(enabled))


__all__ = ["Poe2MonitorConfigDialog"]
