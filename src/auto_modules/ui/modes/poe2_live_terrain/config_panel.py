"""PoE2-local monitor configuration controls, styled after mapping mode."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
    QApplication,
)

from auto_modules.core.spatial.capture_geometry import CaptureShape
from auto_modules.core.vision import HSVRecognizer
from auto_modules.features.poe2.live_terrain import Poe2MonitorConfig

from .capture import Poe2CaptureSelectionController, Poe2CaptureSelectionResult


class Poe2MonitorConfigPanel(QWidget):
    """Independent PoE2 monitor editor; it never writes mapping-mode state."""

    config_changed = Signal(object)
    color_calibration_requested = Signal()
    advanced_visual_requested = Signal()

    def __init__(self, config: Poe2MonitorConfig | None = None, *, parent=None) -> None:
        super().__init__(parent)
        self._config = config or Poe2MonitorConfig()
        self._default_recognizer_params = HSVRecognizer().get_params()
        self._loading = False
        self._editable = True
        self.selection_controller = Poe2CaptureSelectionController(
            compute_scale=self._compute_scale,
        )
        self._build_ui()
        self.set_config(self._config)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        region_group = QGroupBox("1. 监控区域")
        region_layout = QVBoxLayout(region_group)
        self.select_region_button = QPushButton("🖱️ 画框选择区域")
        self.select_region_button.clicked.connect(self.start_region_selection)
        self.select_center_button = QPushButton("🎯 选择人物中心点")
        self.select_center_button.clicked.connect(self.start_center_selection)
        region_layout.addWidget(self.select_region_button)
        region_layout.addWidget(self.select_center_button)

        form = QFormLayout()
        self.shape_combo = QComboBox()
        self.shape_combo.addItem("正方形", CaptureShape.SQUARE.value)
        self.shape_combo.addItem("圆形", CaptureShape.CIRCLE.value)
        self.shape_combo.currentIndexChanged.connect(self._shape_changed)
        form.addRow("有效区域", self.shape_combo)
        self.capture_size_spin = QSpinBox()
        self.capture_size_spin.setRange(100, 2000)
        self.capture_size_spin.setValue(320)
        self.capture_size_spin.valueChanged.connect(self._size_changed)
        form.addRow("截图大小", self.capture_size_spin)
        self.circle_radius_spin = QDoubleSpinBox()
        self.circle_radius_spin.setRange(1.0, 2000.0)
        self.circle_radius_spin.setDecimals(1)
        self.circle_radius_spin.setValue(160.0)
        form.addRow("圆形半径", self.circle_radius_spin)
        region_layout.addLayout(form)
        self.binding_label = QLabel("未选择区域")
        self.binding_label.setWordWrap(True)
        region_layout.addWidget(self.binding_label)
        root.addWidget(region_group)

        recognition_group = QGroupBox("2. 识别参数")
        recognition_form = QFormLayout(recognition_group)
        self.search_radius_spin = QSpinBox()
        self.search_radius_spin.setRange(1, 5000)
        recognition_form.addRow("局部搜索半径", self.search_radius_spin)
        self.match_threshold_spin = QDoubleSpinBox()
        self.match_threshold_spin.setRange(0.0, 1.0)
        self.match_threshold_spin.setSingleStep(0.01)
        self.match_threshold_spin.setDecimals(2)
        recognition_form.addRow("匹配阈值", self.match_threshold_spin)
        self.sample_interval_spin = QSpinBox()
        self.sample_interval_spin.setRange(10, 5000)
        recognition_form.addRow("采样间隔（毫秒）", self.sample_interval_spin)
        self.enable_wall_check = QCheckBox("墙壁识别")
        self.enable_fog_check = QCheckBox("迷雾识别")
        self.clahe_enabled_check = QCheckBox("启用 CLAHE 增强")
        self.deepen_enabled_check = QCheckBox("启用颜色深化")
        recognition_form.addRow("识别层", self.enable_wall_check)
        recognition_form.addRow("", self.enable_fog_check)
        recognition_form.addRow("预处理", self.clahe_enabled_check)
        recognition_form.addRow("", self.deepen_enabled_check)
        self.wall_weight_spin = QSpinBox()
        self.wall_weight_spin.setRange(0, 100)
        recognition_form.addRow("墙壁权重", self.wall_weight_spin)
        self.edge_weight_spin = QSpinBox()
        self.edge_weight_spin.setRange(0, 100)
        recognition_form.addRow("边缘权重", self.edge_weight_spin)
        self.canny_low_spin = QSpinBox()
        self.canny_low_spin.setRange(0, 255)
        recognition_form.addRow("Canny 低阈值", self.canny_low_spin)
        self.canny_high_spin = QSpinBox()
        self.canny_high_spin.setRange(0, 255)
        recognition_form.addRow("Canny 高阈值", self.canny_high_spin)
        self.player_clear_radius_spin = QSpinBox()
        self.player_clear_radius_spin.setRange(0, 120)
        self.player_clear_radius_spin.setSingleStep(2)
        recognition_form.addRow("人物动态擦除半径", self.player_clear_radius_spin)
        for control in (
            self.enable_wall_check,
            self.enable_fog_check,
            self.clahe_enabled_check,
            self.deepen_enabled_check,
        ):
            control.toggled.connect(self._visual_control_changed)
        for control in (
            self.wall_weight_spin,
            self.edge_weight_spin,
            self.canny_low_spin,
            self.canny_high_spin,
            self.player_clear_radius_spin,
        ):
            control.valueChanged.connect(self._visual_control_changed)
        self.color_calibration_button = QPushButton("颜色校准")
        self.color_calibration_button.clicked.connect(self.color_calibration_requested.emit)
        recognition_form.addRow("视觉采样", self.color_calibration_button)
        self.advanced_visual_button = QPushButton("高级视觉参数")
        self.advanced_visual_button.clicked.connect(self.advanced_visual_requested.emit)
        recognition_form.addRow("图像处理", self.advanced_visual_button)
        root.addWidget(recognition_group)

        localization_group = QGroupBox("3. 定位与性能")
        localization_form = QFormLayout(localization_group)
        self.first_frame_confidence_spin = QDoubleSpinBox()
        self.anchored_score_spin = QDoubleSpinBox()
        self.anchored_coverage_spin = QDoubleSpinBox()
        for control in (
            self.first_frame_confidence_spin,
            self.anchored_score_spin,
            self.anchored_coverage_spin,
        ):
            control.setRange(0.0, 1.0)
            control.setDecimals(2)
            control.setSingleStep(0.01)
            control.valueChanged.connect(self._emit_config_changed)
        self.anchored_coverage_spin.setMinimum(0.01)
        localization_form.addRow("首帧置信度", self.first_frame_confidence_spin)
        localization_form.addRow("锚定形状分", self.anchored_score_spin)
        localization_form.addRow("锚定覆盖率", self.anchored_coverage_spin)
        self.localization_fps_spin = QSpinBox()
        self.localization_fps_spin.setRange(1, 60)
        self.localization_fps_spin.valueChanged.connect(self._localization_rate_changed)
        localization_form.addRow("定位目标 FPS", self.localization_fps_spin)
        self.preview_fps_spin = QSpinBox()
        self.preview_fps_spin.setRange(1, 30)
        self.preview_fps_spin.valueChanged.connect(self._emit_config_changed)
        localization_form.addRow("截图预览 FPS", self.preview_fps_spin)
        self.reset_localization_button = QPushButton("恢复定位默认值")
        self.reset_localization_button.clicked.connect(self.reset_localization_policy)
        localization_form.addRow("", self.reset_localization_button)
        root.addWidget(localization_group)

        root.addStretch()

    @staticmethod
    def _compute_scale() -> tuple[float, float]:
        screen = QApplication.primaryScreen()
        if screen is None:
            return 1.0, 1.0
        scale = float(screen.devicePixelRatio())
        return scale, scale

    def set_config(self, config: Poe2MonitorConfig) -> None:
        self._loading = True
        try:
            if config.selection_mode == "center" and config.binding is not None:
                payload = config.as_dict()
                payload["binding"] = self.selection_controller.resize_center_binding(
                    config.binding,
                    config.capture_size,
                ).as_dict()
                config = Poe2MonitorConfig.from_dict(payload)
            self._config = config
            self.search_radius_spin.setValue(config.search_radius)
            self.match_threshold_spin.setValue(config.match_threshold)
            self.sample_interval_spin.setValue(config.sample_interval_ms)
            self.first_frame_confidence_spin.setValue(config.first_frame_minimum_confidence)
            self.anchored_score_spin.setValue(config.first_frame_anchored_score)
            self.anchored_coverage_spin.setValue(config.first_frame_anchored_coverage)
            self.localization_fps_spin.setValue(config.localization_fps)
            self.preview_fps_spin.setValue(config.preview_fps)
            self.capture_size_spin.setValue(config.capture_size)
            self.circle_radius_spin.setValue(config.circle_radius or config.capture_size / 2.0)
            index = self.shape_combo.findData(config.shape.value)
            if index >= 0:
                self.shape_combo.setCurrentIndex(index)
            self._set_visual_controls(self._complete_recognizer_params(config.recognizer_params))
            self.binding_label.setText(
                "未选择区域" if config.binding is None else str(config.binding.rect.as_dict())
            )
        finally:
            self._loading = False
        self._refresh_action_states()

    def current_config(self) -> Poe2MonitorConfig:
        return Poe2MonitorConfig(
            binding=self._config.binding,
            search_radius=self.search_radius_spin.value(),
            match_threshold=self.match_threshold_spin.value(),
            sample_interval_ms=self.sample_interval_spin.value(),
            first_frame_minimum_confidence=self.first_frame_confidence_spin.value(),
            first_frame_anchored_score=self.anchored_score_spin.value(),
            first_frame_anchored_coverage=self.anchored_coverage_spin.value(),
            localization_fps=self.localization_fps_spin.value(),
            preview_fps=self.preview_fps_spin.value(),
            profile_id=self._config.profile_id,
            profile_name=self._config.profile_name,
            selection_mode=self._config.selection_mode,
            capture_size=self.capture_size_spin.value(),
            shape=CaptureShape.coerce(self.shape_combo.currentData()),
            circle_radius=self.circle_radius_spin.value(),
            recognizer_params=self.recognizer_params(),
            stitcher_params=self.stored_stitcher_params(),
        )

    def set_recognizer_params(self, params: dict, *, emit: bool = True) -> None:
        current = self.current_config()
        payload = current.as_dict()
        payload["recognizer_params"] = self._complete_recognizer_params(params)
        self._config = Poe2MonitorConfig.from_dict(payload)
        self._loading = True
        try:
            self._set_visual_controls(self._config.recognizer_params)
        finally:
            self._loading = False
        if emit:
            self.config_changed.emit(self.current_config())

    def recognizer_params(self) -> dict:
        params = self._complete_recognizer_params(self._config.recognizer_params)
        params.update(
            {
                "enable_wall": self.enable_wall_check.isChecked(),
                "enable_fog": self.enable_fog_check.isChecked(),
                "clahe_enabled": self.clahe_enabled_check.isChecked(),
                "deepen_enabled": self.deepen_enabled_check.isChecked(),
                "wall_weight": self.wall_weight_spin.value(),
                "edge_weight": self.edge_weight_spin.value(),
                "edge_low": self.canny_low_spin.value(),
                "edge_high": self.canny_high_spin.value(),
                "player_clear_radius": self.player_clear_radius_spin.value(),
            }
        )
        return params

    def stored_recognizer_params(self) -> dict:
        return dict(self._config.recognizer_params)

    def set_stitcher_params(self, params: dict, *, emit: bool = True) -> None:
        current = self.current_config()
        payload = current.as_dict()
        payload["stitcher_params"] = dict(params)
        self._config = Poe2MonitorConfig.from_dict(payload)
        if emit:
            self.config_changed.emit(self.current_config())

    def stored_stitcher_params(self) -> dict:
        return dict(self._config.stitcher_params)

    def _complete_recognizer_params(self, params: dict | None = None) -> dict:
        complete = dict(self._default_recognizer_params)
        complete.update(dict(params or {}))
        return complete

    def _set_visual_controls(self, params: dict) -> None:
        self.enable_wall_check.setChecked(bool(params["enable_wall"]))
        self.enable_fog_check.setChecked(bool(params["enable_fog"]))
        self.clahe_enabled_check.setChecked(bool(params["clahe_enabled"]))
        self.deepen_enabled_check.setChecked(bool(params["deepen_enabled"]))
        self.wall_weight_spin.setValue(int(params["wall_weight"]))
        self.edge_weight_spin.setValue(int(params["edge_weight"]))
        self.canny_low_spin.setValue(int(params["edge_low"]))
        self.canny_high_spin.setValue(int(params["edge_high"]))
        self.player_clear_radius_spin.setValue(int(params["player_clear_radius"]))

    def _visual_control_changed(self, *_args) -> None:
        if self._loading:
            return
        current = self.current_config()
        self._config = current
        self.config_changed.emit(current)

    def _emit_config_changed(self, *_args) -> None:
        if not self._loading:
            self.config_changed.emit(self.current_config())

    def _localization_rate_changed(self, value: int) -> None:
        if self.preview_fps_spin.value() > value:
            self.preview_fps_spin.setValue(value)
        self._emit_config_changed()

    def reset_localization_policy(self) -> None:
        defaults = Poe2MonitorConfig()
        payload = self.current_config().as_dict()
        for name in (
            "first_frame_minimum_confidence",
            "first_frame_anchored_score",
            "first_frame_anchored_coverage",
            "localization_fps",
            "preview_fps",
        ):
            payload[name] = getattr(defaults, name)
        self.set_config(Poe2MonitorConfig.from_dict(payload))
        self._emit_config_changed()

    def start_region_selection(self) -> None:
        self.selection_controller.start_region_selection(self._apply_selection)

    def start_center_selection(self) -> None:
        self.selection_controller.start_center_selection(
            self.capture_size_spin.value(), self._apply_selection
        )

    def _apply_selection(self, result: Poe2CaptureSelectionResult) -> None:
        current = self.current_config()
        capture_size = (
            result.capture_size if result.mode == "center" else current.capture_size
        )
        payload = current.as_dict()
        payload.update(
            binding=result.binding.as_dict(),
            selection_mode=result.mode,
            capture_size=capture_size,
        )
        self._config = Poe2MonitorConfig.from_dict(payload)
        if result.mode == "center":
            self.capture_size_spin.setValue(result.capture_size)
        self.binding_label.setText(result.label_text)
        self._refresh_action_states()
        self.config_changed.emit(self.current_config())

    def _shape_changed(self, _index: int) -> None:
        self._emit_config_changed()

    def _size_changed(self, value: int) -> None:
        if self._loading:
            return
        if self.shape_combo.currentData() == CaptureShape.CIRCLE.value:
            self.circle_radius_spin.setValue(float(value) / 2.0)
        current = self.current_config()
        if current.selection_mode == "center" and current.binding is not None:
            payload = current.as_dict()
            resized = self.selection_controller.resize_center_binding(
                current.binding,
                value,
            )
            payload["binding"] = resized.as_dict()
            self._config = Poe2MonitorConfig.from_dict(payload)
            self.binding_label.setText(str(resized.rect.as_dict()))
            current = self._config
        self.config_changed.emit(current)

    def set_editable(self, enabled: bool) -> None:
        for widget in (
            self.select_region_button,
            self.select_center_button,
            self.shape_combo,
            self.capture_size_spin,
            self.circle_radius_spin,
            self.search_radius_spin,
            self.match_threshold_spin,
            self.sample_interval_spin,
            self.first_frame_confidence_spin,
            self.anchored_score_spin,
            self.anchored_coverage_spin,
            self.localization_fps_spin,
            self.preview_fps_spin,
            self.reset_localization_button,
            self.enable_wall_check,
            self.enable_fog_check,
            self.clahe_enabled_check,
            self.deepen_enabled_check,
            self.wall_weight_spin,
            self.edge_weight_spin,
            self.canny_low_spin,
            self.canny_high_spin,
            self.player_clear_radius_spin,
            self.color_calibration_button,
            self.advanced_visual_button,
        ):
            widget.setEnabled(bool(enabled))
        self._editable = bool(enabled)
        self._refresh_action_states()

    def _refresh_action_states(self) -> None:
        self.color_calibration_button.setEnabled(
            self._editable and self._config.binding is not None
        )


__all__ = ["Poe2MonitorConfigPanel"]
