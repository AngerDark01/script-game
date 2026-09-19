"""PoE2 live terrain page; orchestration only, no capture implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from auto_modules.ui.widgets import ScalableMapWidget
from auto_modules.features.poe2.live_terrain import (
    Poe2MonitorConfig,
    Poe2MonitorConfigStore,
    get_terrain_logger,
)

from .monitor_dialog import Poe2MonitorConfigDialog
from .presenter import frame_pixmap, present_localization_overlay, present_snapshot

if TYPE_CHECKING:
    from auto_modules.features.poe2.live_terrain import TerrainSnapshot


class TerrainService(Protocol):
    state: Any

    def initialize(self) -> None: ...

    def capture(self) -> TerrainSnapshot: ...

    def reset(self) -> None: ...

    def snapshot(self) -> TerrainSnapshot | None: ...


class LocalizationRuntime(Protocol):
    def start(self) -> None: ...
    def stop(self) -> None: ...
    def tick(self, *, now_ms: int | None = None) -> Any: ...


class _UnavailableTerrainService:
    state = "new"

    def initialize(self) -> None:
        raise RuntimeError("PoE2 实验采集后端未注入")

    def capture(self):
        raise RuntimeError("PoE2 实验采集后端未注入")

    def reset(self) -> None:
        return None

    def snapshot(self):
        return None


class Poe2LiveTerrainPage(QWidget):
    def __init__(
        self,
        service: TerrainService | None = None,
        *,
        runtime: LocalizationRuntime | None = None,
        config_store: Poe2MonitorConfigStore | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.service = service or _UnavailableTerrainService()
        self.runtime = runtime
        self.config_store = config_store
        self.monitor_config = config_store.load() if config_store is not None else Poe2MonitorConfig()
        self.monitor_dialog = None
        self._terrain_display = None
        self._runtime_active = False
        self.monitor_timer = QTimer(self)
        self.monitor_timer.setInterval(self.monitor_config.sample_interval_ms)
        self.monitor_timer.timeout.connect(self._tick_runtime)
        self._logger = get_terrain_logger()
        self._build_ui()
        self._render_state("未初始化")

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        title = QLabel("PoE2 实时地形")
        title.setProperty("role", "heading")
        layout.addWidget(title)

        controls = QHBoxLayout()
        self.initialize_button = QPushButton("初始化")
        self.capture_button = QPushButton("获取当前地图")
        self.reset_button = QPushButton("清空当前地图")
        self.monitor_config_button = QPushButton("监控配置")
        self.start_monitor_button = QPushButton("开始监控")
        self.stop_monitor_button = QPushButton("停止监控")
        self.initialize_button.clicked.connect(self.initialize_session)
        self.capture_button.clicked.connect(self.capture_map)
        self.reset_button.clicked.connect(self.reset_session)
        self.monitor_config_button.clicked.connect(self.open_monitor_config)
        self.start_monitor_button.clicked.connect(self.start_monitoring)
        self.stop_monitor_button.clicked.connect(self.stop_monitoring)
        controls.addWidget(self.initialize_button)
        controls.addWidget(self.capture_button)
        controls.addWidget(self.reset_button)
        controls.addWidget(self.monitor_config_button)
        controls.addWidget(self.start_monitor_button)
        controls.addWidget(self.stop_monitor_button)
        controls.addStretch()
        layout.addLayout(controls)

        self.status_label = QLabel()
        self.error_label = QLabel()
        self.error_label.setWordWrap(True)
        self.metadata_label = QLabel("尚未获取地图")
        self.metadata_label.setWordWrap(True)
        self.localization_status = QLabel("定位：未启动")
        self.localization_status.setWordWrap(True)
        self.minimap_preview = QLabel("尚未开始监控")
        self.minimap_preview.setMinimumSize(180, 180)
        self.minimap_preview.setAlignment(Qt.AlignCenter)
        self.minimap_preview.setStyleSheet("background: #101318; border: 1px solid #39414d;")
        layout.addWidget(self.status_label)
        layout.addWidget(self.error_label)
        layout.addWidget(self.metadata_label)
        layout.addWidget(self.localization_status)
        layout.addWidget(self.minimap_preview)

        self.map_widget = ScalableMapWidget(self)
        layout.addWidget(self.map_widget, 1)
        self.stop_monitor_button.setEnabled(False)

    def initialize_session(self) -> None:
        self._logger.info("step=ui.initialize_clicked")
        self._busy(True)
        try:
            self.service.initialize()
        except Exception as exc:
            self._logger.exception("step=ui.initialize_failed error=%s", exc)
            self._show_error(exc)
        else:
            self.error_label.clear()
            self._render_state("可获取当前地图")
            self._logger.info("step=ui.initialize_rendered")
        finally:
            self._busy(False)

    def capture_map(self) -> None:
        self._logger.info("step=ui.capture_clicked")
        self._busy(True)
        try:
            snapshot = self.service.capture()
        except Exception as exc:
            self._logger.exception("step=ui.capture_failed error=%s", exc)
            self.map_widget.set_image(None)
            self.metadata_label.setText("尚未获取地图")
            self._show_error(exc)
        else:
            display = present_snapshot(snapshot)
            self._terrain_display = display
            self.map_widget.set_image(display.pixmap)
            if self.runtime is not None:
                configure = getattr(self.runtime, "configure_snapshot", None)
                if callable(configure):
                    configure(snapshot)
            self.metadata_label.setText("\n".join(display.metadata_lines))
            self.error_label.clear()
            self._render_state("已获取当前地图")
            self._logger.info("step=ui.capture_rendered")
        finally:
            self._busy(False)

    def reset_session(self) -> None:
        self._logger.info("step=ui.reset_clicked")
        self.stop_monitoring()
        self.service.reset()
        self._terrain_display = None
        self.map_widget.set_image(None)
        self.metadata_label.setText("尚未获取地图")
        self.error_label.clear()
        self._render_state("未初始化")

    def open_monitor_config(self) -> None:
        if self.monitor_dialog is None:
            self.monitor_dialog = Poe2MonitorConfigDialog(
                config=self.monitor_config,
                config_store=self.config_store,
                parent=self,
            )
            self.monitor_dialog.config_saved.connect(self._on_monitor_config_saved)
        self.monitor_dialog.set_editable(not self._runtime_active)
        self.monitor_dialog.show()
        self.monitor_dialog.raise_()
        self.monitor_dialog.activateWindow()

    def _on_monitor_config_saved(self, config: Poe2MonitorConfig) -> None:
        self.monitor_config = config
        self.monitor_timer.setInterval(config.sample_interval_ms)
        setter = getattr(self.runtime, "configure_monitor", None)
        if callable(setter):
            setter(config)
        self.error_label.clear()
        self._logger.info("step=ui.monitor_config_saved interval_ms=%s", config.sample_interval_ms)

    def start_monitoring(self) -> None:
        if self.runtime is None:
            self._show_error(RuntimeError("PoE2 定位运行时未注入"))
            return
        if self.service.snapshot() is None:
            self._show_error(RuntimeError("请先初始化并获取当前地图"))
            return
        if self.config_store is not None and self.monitor_config.binding is None:
            self._show_error(RuntimeError("请先配置 PoE2 小地图监控区域"))
            return
        try:
            configure = getattr(self.runtime, "configure_monitor", None)
            if callable(configure):
                configure(self.monitor_config)
            self.runtime.start()
            self.monitor_timer.setInterval(self.monitor_config.sample_interval_ms)
            self.monitor_timer.start()
            self.set_runtime_active(True)
            self.error_label.clear()
            self.localization_status.setText("定位：监控中，等待首帧全局定位")
            self._logger.info("step=ui.monitor_started interval_ms=%s", self.monitor_timer.interval())
        except Exception as exc:
            self._logger.exception("step=ui.monitor_start_failed error=%s", exc)
            self._show_error(exc)

    def stop_monitoring(self) -> None:
        self.monitor_timer.stop()
        if self.runtime is not None:
            stop = getattr(self.runtime, "stop", None)
            if callable(stop):
                stop()
            clear = getattr(self.runtime, "clear_frame", None)
            if callable(clear):
                clear()
        self.minimap_preview.clear()
        self.minimap_preview.setText("尚未开始监控")
        self.localization_status.setText("定位：未启动")
        self.set_runtime_active(False)
        self._logger.info("step=ui.monitor_stopped")

    def _tick_runtime(self) -> None:
        if self.runtime is None:
            return
        try:
            state = self.runtime.tick()
        except Exception as exc:
            self._logger.exception("step=ui.monitor_tick_failed error=%s", exc)
            self._show_error(exc)
            return
        self.handle_runtime_state(state)

    def handle_runtime_state(self, state) -> None:
        preview = frame_pixmap(getattr(state, "raw_frame", None))
        if not preview.isNull():
            preview = preview.scaled(self.minimap_preview.size(), Qt.KeepAspectRatio, Qt.FastTransformation)
            self.minimap_preview.setPixmap(preview)
        source = getattr(state, "source", "failed")
        confidence = float(getattr(state, "confidence", 0.0))
        position = getattr(state, "position", None)
        local_position = getattr(state, "local_position", None)
        failure = getattr(state, "failure_reason", "")
        self.localization_status.setText(
            f"定位：{source} | 模式：{getattr(state, 'mode', '')} | 置信度：{confidence:.2f} | "
            f"局部：{local_position or '-'} | 全局：{position or '-'} | "
            f"帧耗时：{float(getattr(state, 'frame_elapsed_ms', 0.0)):.1f} ms"
            + (f" | 原因：{failure}" if failure else "")
        )
        if self._terrain_display is not None:
            overlay = present_localization_overlay(self._terrain_display.pixmap, state)
            self.map_widget.set_image(overlay)

    def set_runtime_active(self, active: bool) -> None:
        self._runtime_active = bool(active)
        self.start_monitor_button.setEnabled(not active and self.runtime is not None)
        self.stop_monitor_button.setEnabled(active)
        self.monitor_config_button.setEnabled(not active)
        if self.monitor_dialog is not None:
            self.monitor_dialog.set_editable(not active)

    def hideEvent(self, event) -> None:
        self.stop_monitoring()
        super().hideEvent(event)

    def _busy(self, busy: bool) -> None:
        self.initialize_button.setEnabled(not busy)
        self.capture_button.setEnabled(not busy and self._can_capture())
        self.reset_button.setEnabled(not busy)
        self.monitor_config_button.setEnabled(not busy and not self._runtime_active)

    def _can_capture(self) -> bool:
        state = getattr(self.service, "state", "new")
        value = getattr(state, "value", state)
        return value in {"ready_to_capture", "captured"}

    def _render_state(self, text: str) -> None:
        self.status_label.setText(f"状态：{text}")
        self.capture_button.setEnabled(self._can_capture())
        self.start_monitor_button.setEnabled(self.runtime is not None and not self._runtime_active and self.service.snapshot() is not None)

    def _show_error(self, error: Exception) -> None:
        self.status_label.setText("状态：错误")
        self.error_label.setText(f"错误：{error}")
        self.capture_button.setEnabled(False)

    def stop_runtime(self) -> None:
        self.stop_monitoring()

    def shutdown(self) -> None:
        self.stop_monitoring()
        self.service.reset()
        self.map_widget.set_image(None)
        self._terrain_display = None
        self.metadata_label.setText("尚未获取地图")
        self.error_label.clear()
        self._render_state("未初始化")
