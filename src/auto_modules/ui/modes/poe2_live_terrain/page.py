"""PoE2 live terrain page; orchestration only, no capture implementation."""

from __future__ import annotations

from time import perf_counter
from typing import TYPE_CHECKING, Any, Protocol

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QTabWidget,
    QWidget,
)

from auto_modules.ui.widgets import ScalableMapWidget
from auto_modules.features.poe2.live_terrain import (
    Poe2MonitorConfig,
    Poe2MonitorConfigStore,
    Poe2MonitorProfileStore,
    get_terrain_logger,
)
from auto_modules.features.poe2.live_terrain.orientation import TerrainOrientation

from .monitor_dialog import Poe2MonitorConfigDialog
from .localization_worker import Poe2LocalizationWorker
from .profile_toolbar import Poe2ProfileToolbar
from .capture_test_page import Poe2CaptureTestPage
from .presenter import (
    frame_pixmap,
    localization_display_point,
    prepare_localization_map,
    present_snapshot,
)

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
        profile_store: Poe2MonitorProfileStore | None = None,
        capture_test_service: Any | None = None,
        capture_test_archive: Any | None = None,
        capture_sample_archive: Any | None = None,
        capture_stitching_archive: Any | None = None,
        capture_stitching_session_factory: Any | None = None,
        capture_preview: Any | None = None,
        capture_recognizer: Any | None = None,
        player_position_source: Any | None = None,
        hybrid_localization_factory: Any | None = None,
        multiframe_localization_factory: Any | None = None,
        program_output_factory: Any | None = None,
        follow_engine_page_adapter_factory: Any | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.service = service or _UnavailableTerrainService()
        self.runtime = runtime
        self.config_store = config_store
        self.profile_store = profile_store
        self.capture_test_service = capture_test_service
        self.capture_test_archive = capture_test_archive
        self.capture_sample_archive = capture_sample_archive
        self.capture_stitching_archive = capture_stitching_archive
        self.capture_stitching_session_factory = capture_stitching_session_factory
        self.capture_preview = capture_preview
        self.capture_recognizer = capture_recognizer
        self.player_position_source = player_position_source
        self.hybrid_localization_factory = hybrid_localization_factory
        self.multiframe_localization_factory = multiframe_localization_factory
        self.program_output_factory = program_output_factory
        self.follow_engine_page_adapter_factory = follow_engine_page_adapter_factory
        active_profile = profile_store.active() if profile_store is not None else None
        self.monitor_config = active_profile or (
            config_store.load() if config_store is not None else Poe2MonitorConfig()
        )
        self.monitor_dialog = None
        self._terrain_display = None
        self._map_display_cache_signature = None
        self._map_display_pixmap = None
        self._runtime_active = False
        self._localization_worker: Poe2LocalizationWorker | None = None
        # A worker that outlives the bounded stop wait must stay strongly
        # referenced until its own finished signal arrives.  Releasing it
        # while MSS/Qt resources are still in use can corrupt native heaps.
        self._retired_localization_workers: list[Poe2LocalizationWorker] = []
        self._worker_generation = 0
        self._last_preview_at = 0.0
        self._ui_window_started = perf_counter()
        self._last_overlay_signature = None
        self.map_follow_zoom_multiplier = 2.4
        self._ui_frame_count = 0
        self._ui_render_total_ms = 0.0
        self._ui_render_max_ms = 0.0
        self.monitor_timer = QTimer(self)
        self.monitor_timer.setInterval(self.monitor_config.sample_interval_ms)
        self.monitor_timer.timeout.connect(self._tick_runtime)
        self._logger = get_terrain_logger()
        self._apply_monitor_config(self.monitor_config)
        self._build_ui()
        self._render_state("未初始化")

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        self.tabs = QTabWidget(self)
        live_tab = QWidget(self)
        layout = QHBoxLayout(live_tab)

        left_panel = QWidget(self)
        left_layout = QVBoxLayout(left_panel)

        self.profile_toolbar = None
        if self.profile_store is not None:
            self.profile_toolbar = Poe2ProfileToolbar(self.profile_store, parent=left_panel)
            self.profile_toolbar.profile_selected.connect(self._on_profile_selected)
            left_layout.addWidget(self.profile_toolbar)

        title = QLabel("PoE2 实时地形")
        title.setProperty("role", "heading")
        left_layout.addWidget(title)

        controls = QHBoxLayout()
        self.initialize_button = QPushButton("初始化")
        self.capture_button = QPushButton("获取当前地图")
        self.reset_button = QPushButton("清空当前地图")
        self.monitor_config_button = QPushButton("监控配置")
        self.start_monitor_button = QPushButton("开始监控")
        self.stop_monitor_button = QPushButton("停止监控")
        self.retry_localization_button = QPushButton("重新定位")
        self.initialize_button.clicked.connect(self.initialize_session)
        self.capture_button.clicked.connect(self.capture_map)
        self.reset_button.clicked.connect(self.reset_session)
        self.monitor_config_button.clicked.connect(self.open_monitor_config)
        self.start_monitor_button.clicked.connect(self.start_monitoring)
        self.stop_monitor_button.clicked.connect(self.stop_monitoring)
        self.retry_localization_button.clicked.connect(self.retry_localization)
        controls.addWidget(self.initialize_button)
        controls.addWidget(self.capture_button)
        controls.addWidget(self.reset_button)
        controls.addWidget(self.monitor_config_button)
        controls.addWidget(self.start_monitor_button)
        controls.addWidget(self.stop_monitor_button)
        controls.addWidget(self.retry_localization_button)
        controls.addStretch()
        left_layout.addLayout(controls)

        self.status_label = QLabel()
        self.error_label = QLabel()
        self.error_label.setWordWrap(True)
        self.metadata_label = QLabel("尚未获取地图")
        self.metadata_label.setWordWrap(True)
        self.localization_status = QLabel("定位：未启动")
        self.localization_status.setWordWrap(True)
        self.recognition_diagnostics_label = QLabel("识别诊断：未开始")
        self.recognition_diagnostics_label.setWordWrap(True)
        self.minimap_preview = QLabel("尚未开始监控")
        self.minimap_preview.setMinimumSize(180, 180)
        self.minimap_preview.setAlignment(Qt.AlignCenter)
        self.minimap_preview.setStyleSheet("background: #101318; border: 1px solid #39414d;")
        self.match_preview = QLabel("尚未生成匹配特征")
        self.match_preview.setMinimumSize(180, 180)
        self.match_preview.setAlignment(Qt.AlignCenter)
        self.match_preview.setStyleSheet("background: #101318; border: 1px solid #39414d;")
        left_layout.addWidget(self.status_label)
        left_layout.addWidget(self.error_label)
        left_layout.addWidget(self.metadata_label)
        left_layout.addStretch()
        layout.addWidget(left_panel, 1)

        right_panel = QWidget(self)
        right_layout = QVBoxLayout(right_panel)
        monitor_group = QGroupBox("实时监控小地图")
        monitor_layout = QHBoxLayout(monitor_group)
        processed_layout = QVBoxLayout()
        processed_layout.addWidget(QLabel("预处理画面"))
        processed_layout.addWidget(self.minimap_preview)
        match_layout = QVBoxLayout()
        match_layout.addWidget(QLabel("匹配特征"))
        match_layout.addWidget(self.match_preview)
        monitor_layout.addLayout(processed_layout)
        monitor_layout.addLayout(match_layout)
        monitor_group.setLayout(monitor_layout)
        right_layout.addWidget(monitor_group, 1)
        terrain_group = QGroupBox("当前获取的地图")
        terrain_layout = QVBoxLayout(terrain_group)
        self.map_widget = ScalableMapWidget(self)
        # Native terrain is much larger than the old hand-drawn canvas.  Keep
        # the full map for matching, but make the initial PoE2 presentation
        # easier to inspect without changing other pages' defaults.
        self.map_widget.fit_scale_multiplier = 1.35
        terrain_layout.addWidget(self.map_widget)
        terrain_group.setLayout(terrain_layout)
        right_layout.addWidget(terrain_group, 3)
        position_group = QGroupBox("人物位置与定位状态")
        position_layout = QVBoxLayout(position_group)
        position_layout.addWidget(self.localization_status)
        position_layout.addWidget(self.recognition_diagnostics_label)
        right_layout.addWidget(position_group)
        layout.addWidget(right_panel, 3)
        self.stop_monitor_button.setEnabled(False)
        self.retry_localization_button.setEnabled(False)
        root_layout.addWidget(self.tabs)
        self.tabs.addTab(live_tab, "实时地形定位")

        self.capture_test_page = None
        if self.capture_test_service is not None and self.capture_test_archive is not None:
            self.capture_test_page = Poe2CaptureTestPage(
                self.capture_test_service,
                archive=self.capture_test_archive,
                sample_archive=self.capture_sample_archive,
                stitching_session_factory=self.capture_stitching_session_factory,
                stitching_archive=self.capture_stitching_archive,
                monitor_config=self.monitor_config,
                preview_provider=self.capture_preview,
                recognizer=self.capture_recognizer,
                player_position_source=self.player_position_source,
                hybrid_localization_factory=self.hybrid_localization_factory,
                multiframe_localization_factory=self.multiframe_localization_factory,
                program_output_factory=self.program_output_factory,
                follow_engine_page_adapter_factory=self.follow_engine_page_adapter_factory,
                open_config=self.open_monitor_config,
                parent=self.tabs,
            )
            self.tabs.addTab(self.capture_test_page, "数据采集测试")

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
        if self._localization_worker is not None:
            self._show_error(RuntimeError("请先停止定位并等待当前帧结束"))
            return
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
            orientation = self._map_orientation()
            configure = getattr(self.runtime, "configure_monitor", None)
            if callable(configure):
                configure(self.monitor_config)
            display = present_snapshot(snapshot, orientation)
            self._terrain_display = display
            self._last_overlay_signature = None
            self.map_widget.set_image(display.pixmap)
            if self.runtime is not None:
                configure_snapshot = getattr(self.runtime, "configure_snapshot", None)
                if callable(configure_snapshot):
                    configure_snapshot(snapshot)
            self.metadata_label.setText("\n".join(display.metadata_lines))
            self.error_label.clear()
            self._render_state("已获取当前地图")
            self._logger.info("step=ui.capture_rendered")
        finally:
            self._busy(False)

    def reset_session(self) -> None:
        if self._localization_worker is not None:
            self.stop_monitoring()
            return
        self._logger.info("step=ui.reset_clicked")
        self.stop_monitoring()
        self.service.reset()
        self._terrain_display = None
        self._map_display_cache_signature = None
        self._map_display_pixmap = None
        self.map_widget.set_image(None)
        self.map_widget.clear_overlay()
        self.metadata_label.setText("尚未获取地图")
        self.error_label.clear()
        self._render_state("未初始化")

    def open_monitor_config(self) -> None:
        if self.monitor_dialog is None:
            preview_provider = self.capture_preview or getattr(
                self.runtime,
                "capture_preview",
                None,
            )
            recognizer_params_provider = getattr(
                self.capture_recognizer,
                "get_params",
                None,
            ) or getattr(self.runtime, "get_recognizer_params", None)
            self.monitor_dialog = Poe2MonitorConfigDialog(
                config=self.monitor_config,
                config_store=self.config_store,
                profile_store=self.profile_store,
                preview_provider=preview_provider,
                recognizer_params_provider=recognizer_params_provider,
                parent=self,
            )
            self.monitor_dialog.config_saved.connect(self._on_monitor_config_saved)
        self.monitor_dialog.set_editable(not self._runtime_active)
        self.monitor_dialog.show()
        self.monitor_dialog.raise_()
        self.monitor_dialog.activateWindow()

    def _on_profile_selected(self, config: Poe2MonitorConfig) -> None:
        if self._runtime_active:
            return
        self._apply_monitor_config(config)
        if self.monitor_dialog is not None:
            self.monitor_dialog.set_config(config)
        self.error_label.clear()
        self._refresh_map_display()
        self._logger.info("step=ui.profile_selected profile_id=%s", config.profile_id)

    def _on_monitor_config_saved(self, config: Poe2MonitorConfig) -> None:
        self._apply_monitor_config(config)
        self.error_label.clear()
        if self.profile_toolbar is not None:
            self.profile_toolbar.refresh(config.profile_id)
        self._refresh_map_display()
        self._logger.info("step=ui.monitor_config_saved interval_ms=%s", config.sample_interval_ms)

    def _apply_monitor_config(self, config: Poe2MonitorConfig) -> None:
        self.monitor_config = config
        self.monitor_timer.setInterval(config.sample_interval_ms)
        configure = getattr(self.runtime, "configure_monitor", None)
        if callable(configure):
            configure(config)
        capture_page = getattr(self, "capture_test_page", None)
        if capture_page is not None:
            capture_page.set_monitor_config(config)

    def start_monitoring(self) -> None:
        if self._localization_worker is not None:
            return
        self._retired_localization_workers = [
            worker
            for worker in self._retired_localization_workers
            if worker.is_running
        ]
        if self._retired_localization_workers:
            self._logger.warning(
                "step=ui.monitor_start_deferred retired_workers=%s",
                len(self._retired_localization_workers),
            )
            return
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
            self._last_overlay_signature = None
            self._last_preview_at = 0.0
            self._ui_frame_count = 0
            self._ui_render_total_ms = 0.0
            self._ui_render_max_ms = 0.0
            self._ui_window_started = perf_counter()
            self.retry_localization_button.setEnabled(False)
            if getattr(self.runtime, "run_in_background", False):
                self._worker_generation += 1
                cleanup = getattr(self.capture_preview, "close_current_thread", None)
                worker = Poe2LocalizationWorker(
                    self.runtime,
                    generation=self._worker_generation,
                    fps=self.monitor_config.localization_fps,
                    cleanup=cleanup if callable(cleanup) else None,
                )
                worker.state_available.connect(self._on_worker_state)
                worker.failed.connect(self._on_worker_error)
                worker.finished.connect(
                    lambda generation, worker=worker: self._on_worker_finished(
                        generation, worker
                    )
                )
                self._localization_worker = worker
                self.set_runtime_active(True)
                worker.start()
            else:
                self.runtime.start()
                self.monitor_timer.setInterval(self.monitor_config.sample_interval_ms)
                self.monitor_timer.start()
                self.set_runtime_active(True)
            self.error_label.clear()
            self.localization_status.setText("定位：监控中，等待首帧全局定位")
            self._logger.info(
                "step=ui.monitor_started localization_fps=%s interval_ms=%s background=%s",
                self.monitor_config.localization_fps,
                self.monitor_timer.interval(),
                self._localization_worker is not None,
            )
        except Exception as exc:
            self._logger.exception("step=ui.monitor_start_failed error=%s", exc)
            self._show_error(exc)

    def stop_monitoring(self) -> None:
        self.monitor_timer.stop()
        worker = self._localization_worker
        if worker is not None:
            worker.stop()
            completed = worker.wait(3000)
            if completed:
                self._localization_worker = None
                self._logger.info(
                    "step=ui.monitor_worker_stop_completed generation=%s",
                    worker.generation,
                )
            else:
                self._localization_worker = None
                if worker not in self._retired_localization_workers:
                    self._retired_localization_workers.append(worker)
                self._logger.warning(
                    "step=ui.monitor_worker_stop_timeout generation=%s retired=%s",
                    worker.generation,
                    len(self._retired_localization_workers),
                )
        elif self.runtime is not None:
            stop = getattr(self.runtime, "stop", None)
            if callable(stop):
                stop()
            clear = getattr(self.runtime, "clear_frame", None)
            if callable(clear):
                clear()
        self.minimap_preview.clear()
        self.minimap_preview.setText("尚未开始监控")
        self.match_preview.clear()
        self.match_preview.setText("尚未生成匹配特征")
        self.localization_status.setText("定位：未启动")
        self.recognition_diagnostics_label.setText("识别诊断：未开始")
        self.retry_localization_button.setEnabled(False)
        self._last_overlay_signature = None
        self.set_runtime_active(False)
        self._logger.info("step=ui.monitor_stopped")

    def _on_worker_state(self, generation: int) -> None:
        if generation != self._worker_generation or not self._runtime_active:
            return
        worker = self._localization_worker
        if worker is None:
            return
        state = worker.take_latest_state()
        if state is None:
            return
        render_started = perf_counter()
        self.handle_runtime_state(state)
        self._record_ui_performance(state, (perf_counter() - render_started) * 1000.0)

    def _on_worker_error(self, generation: int, error: Exception) -> None:
        if generation != self._worker_generation or not self._runtime_active:
            return
        self._logger.error("step=ui.monitor_worker_failed error=%s", error)
        self.stop_monitoring()
        self._show_error(error)

    def _on_worker_finished(
        self,
        generation: int,
        worker: Poe2LocalizationWorker | None = None,
    ) -> None:
        if worker is not None and worker in self._retired_localization_workers:
            self._retired_localization_workers.remove(worker)
            self._logger.info(
                "step=ui.retired_monitor_worker_released generation=%s retired=%s",
                generation,
                len(self._retired_localization_workers),
            )
        if generation != self._worker_generation:
            return
        if worker is not None and self._localization_worker not in (None, worker):
            return
        self._localization_worker = None
        self.set_runtime_active(False)
        self._logger.info("step=ui.monitor_worker_finished generation=%s", generation)

    def _tick_runtime(self) -> None:
        if self.runtime is None:
            return
        try:
            state = self.runtime.tick()
        except Exception as exc:
            self._logger.exception("step=ui.monitor_tick_failed error=%s", exc)
            self._show_error(exc)
            return
        render_started = perf_counter()
        self.handle_runtime_state(state)
        render_ms = (perf_counter() - render_started) * 1000.0
        self._record_ui_performance(state, render_ms)

    def retry_localization(self) -> None:
        if self.runtime is None:
            return
        try:
            if self._localization_worker is not None:
                self._localization_worker.retry_recovery()
            else:
                self.runtime.retry_recovery()
        except Exception as exc:
            self._logger.exception("step=ui.localization_retry_failed error=%s", exc)
            self._show_error(exc)
            return
        self.retry_localization_button.setEnabled(False)
        self.localization_status.setText("定位：正在重新定位，等待下一帧")
        if self._localization_worker is None:
            self.monitor_timer.setInterval(self.monitor_config.sample_interval_ms)
            self.monitor_timer.start()
        self._logger.info("step=ui.localization_retry_started")

    def handle_runtime_state(self, state) -> None:
        now = perf_counter()
        update_preview = (
            self._last_preview_at == 0.0
            or now - self._last_preview_at >= 1.0 / self.monitor_config.preview_fps
            or (
                getattr(state, "processed_frame", None) is None
                and getattr(state, "raw_frame", None) is None
            )
        )
        if update_preview:
            self._last_preview_at = now
            self._update_frame_previews(state)
        source = getattr(state, "source", "failed")
        confidence = float(getattr(state, "confidence", 0.0))
        position = getattr(state, "position", None)
        latest_position = getattr(state, "latest_confirmed_position", None)
        local_position = getattr(state, "local_position", None)
        mode = getattr(state, "mode", "")
        mode_name = getattr(mode, "value", mode)
        failure = str(
            getattr(state, "reason", "")
            or getattr(state, "failure_reason", "")
            or ""
        )
        revision = int(getattr(state, "recovery_revision", 0))
        read_count = int(getattr(state, "memory_read_count", 0))
        dual_players = dict(getattr(state, "dual_players", {}) or {})
        dual_trajectories = dict(getattr(state, "dual_trajectories", {}) or {})
        dual_status = getattr(state, "dual_status", None)
        dual_mode = dual_status is not None or bool(dual_players)
        recovery_note = " | 需要重新定位" if mode_name == "recovery_required" else ""
        dual_note = ""
        if dual_mode:
            visible = [
                f"{identity}:{point or '-'}"
                for identity, point in dual_players.items()
            ]
            dual_note = (
                f" | 双人状态：{dual_status or mode_name}"
                f" | 玩家：{'，'.join(visible) if visible else '-'}"
                f" | 墙体质量：{float(getattr(state, 'dual_wall_quality', 0.0)):.2f}"
            )
        self.localization_status.setText(
            f"定位：{source} | 模式：{mode_name} | 置信度：{confidence:.2f} | "
            f"局部：{local_position or '-'} | 本帧全局：{position or '-'} | "
            f"最后可信：{latest_position or '-'} | 恢复版本：{revision} | "
            f"内存读取：{read_count} | 帧耗时：{float(getattr(state, 'frame_elapsed_ms', 0.0)):.1f} ms"
            + (f" | 原因：{failure}" if failure else "")
            + dual_note
            + recovery_note
        )
        diagnostics = dict(
            getattr(state, "diagnostics", None)
            or getattr(state, "recognition_diagnostics", None)
            or {}
        )
        reason = diagnostics.get("reason", "-")
        positions = diagnostics.get("candidate_positions", [])
        status = str(diagnostics.get("status", ""))
        accepted_count = diagnostics.get(
            "accepted_count",
            1 if status == "anchored_candidate" else 0,
        )
        best_score = diagnostics.get("best_score")
        best_confidence = diagnostics.get("confidence", diagnostics.get("best_anchored_score"))
        best_angle = diagnostics.get("best_angle")
        best_scale = diagnostics.get("best_scale")
        best_anchor_error = diagnostics.get("best_anchor_error")
        best_coverage = diagnostics.get("best_forward_coverage")
        numeric_diagnostics = all(
            isinstance(value, (int, float))
            for value in (
                best_score,
                best_confidence,
                best_angle,
                best_scale,
                best_anchor_error,
                best_coverage,
            )
        )
        if numeric_diagnostics:
            details = (
                f"识别诊断：候选 {diagnostics.get('candidate_count', 0)} | "
                f"通过 {accepted_count} | "
                f"最佳分 {float(best_score):.2f} | "
                f"置信度 {float(best_confidence):.2f} | "
                f"角度 {float(best_angle):.1f}° | "
                f"比例 {float(best_scale):.2f} | "
                f"锚点误差 {float(best_anchor_error):.1f} | "
                f"覆盖 {float(best_coverage):.2f} | "
                f"原因：{reason}"
            )
        else:
            details = (
                "识别诊断："
                f"候选 {diagnostics.get('candidate_count', 0)} | "
                f"通过 {accepted_count} | "
                f"原因：{reason}"
            )
        self.recognition_diagnostics_label.setText(
            details + (f" | 候选坐标 {positions[:3]}" if positions else "")
        )
        if mode_name == "recovery_required":
            self.monitor_timer.stop()
            self.retry_localization_button.setEnabled(True)
            self._logger.warning(
                "step=ui.monitor_paused_for_recovery revision=%s read_count=%s reason=%s",
                revision,
                read_count,
                failure,
            )
        transform = getattr(getattr(state, "registration", None), "transform", None)
        overlay_signature = (
            position,
            latest_position,
            tuple(getattr(state, "trajectory", ()) or ()),
            tuple(sorted((identity, point) for identity, point in dual_players.items())),
            tuple(sorted((identity, tuple(points)) for identity, points in dual_trajectories.items())),
            dual_status,
            float(getattr(transform, "angle_degrees", 0.0)) if transform is not None else 0.0,
            bool(getattr(transform, "reflect_horizontal", False)) if transform is not None else False,
        )
        if self._terrain_display is not None and overlay_signature != self._last_overlay_signature:
            base_pixmap = self._terrain_display.pixmap
            transform_signature = (
                float(getattr(transform, "angle_degrees", 0.0)) if transform is not None else 0.0,
                bool(getattr(transform, "reflect_horizontal", False)) if transform is not None else False,
            )
            cache_signature = (
                id(self._terrain_display),
                base_pixmap.width(),
                base_pixmap.height(),
                transform_signature,
            )
            if cache_signature != self._map_display_cache_signature:
                self._map_display_pixmap = prepare_localization_map(base_pixmap, transform)
                self._map_display_cache_signature = cache_signature
                self.map_widget.set_image(self._map_display_pixmap)
            source_size = (base_pixmap.width(), base_pixmap.height())
            display_position = (
                localization_display_point(position, source_size=source_size, transform=transform)
                if position is not None
                else None
            )
            display_trajectory = tuple(
                localization_display_point(point, source_size=source_size, transform=transform)
                for point in tuple(getattr(state, "trajectory", ()) or ())
            )
            display_candidates = tuple(
                localization_display_point(candidate_position, source_size=source_size, transform=transform)
                for candidate in tuple(getattr(state, "candidate_regions", ()) or ())
                for candidate_position in (getattr(candidate, "position", None),)
                if candidate_position is not None
            )
            display_players = {
                identity: localization_display_point(
                    point,
                    source_size=source_size,
                    transform=transform,
                )
                for identity, point in dual_players.items()
                if point is not None
            }
            display_player_trajectories = {
                identity: tuple(
                    localization_display_point(
                        point,
                        source_size=source_size,
                        transform=transform,
                    )
                    for point in points
                )
                for identity, points in dual_trajectories.items()
            }
            self.map_widget.set_overlay(
                position=None if dual_mode else display_position,
                trajectory=display_trajectory,
                candidates=display_candidates,
                players=display_players,
                player_trajectories=display_player_trajectories,
            )
            self._focus_map_on_state(state, source_size=base_pixmap.size())
            self._last_overlay_signature = overlay_signature
        if transform is not None:
            lines = [
                line for line in self.metadata_label.text().splitlines()
                if not line.startswith("方向：")
            ]
            lines.append(
                f"方向：自动校准 {float(transform.angle_degrees):.1f}°"
                f"{'，水平镜像' if transform.reflect_horizontal else ''}"
            )
            self.metadata_label.setText("\n".join(lines))

    def _update_frame_previews(self, state: Any) -> None:
        preview = frame_pixmap(
            getattr(state, "processed_frame", None)
            if getattr(state, "processed_frame", None) is not None
            else getattr(state, "raw_frame", None)
        )
        if not preview.isNull():
            preview = preview.scaled(self.minimap_preview.size(), Qt.KeepAspectRatio, Qt.FastTransformation)
            self.minimap_preview.setPixmap(preview)
        else:
            self.minimap_preview.clear()
            self.minimap_preview.setText("本帧无画面")
        match_preview = frame_pixmap(getattr(state, "match_mask", None))
        if not match_preview.isNull():
            match_preview = match_preview.scaled(
                self.match_preview.size(),
                Qt.KeepAspectRatio,
                Qt.FastTransformation,
            )
            self.match_preview.setPixmap(match_preview)
        else:
            self.match_preview.clear()
            self.match_preview.setText("本帧无匹配特征")
    def _focus_map_on_state(self, state: Any, *, source_size) -> None:
        """Keep the enlarged map view centered on the latest trusted point."""
        position = getattr(state, "position", None)
        if position is None:
            position = getattr(state, "latest_confirmed_position", None)
        if position is None:
            return
        registration = getattr(state, "registration", None)
        transform = getattr(registration, "transform", None)
        point = localization_display_point(
            position,
            source_size=(source_size.width(), source_size.height()),
            transform=transform,
        )
        self.map_widget.focus_on_point(
            point,
            zoom_multiplier=self.map_follow_zoom_multiplier,
        )

    def _record_ui_performance(self, state: Any, render_ms: float) -> None:
        self._ui_frame_count += 1
        self._ui_render_total_ms += render_ms
        self._ui_render_max_ms = max(self._ui_render_max_ms, render_ms)
        if self._ui_frame_count < 30:
            return
        self._logger.info(
            "step=ui.localization_performance frames=%s average_render_ms=%.1f "
            "max_render_ms=%.1f actual_fps=%.1f skipped_display=%s mode=%s",
            self._ui_frame_count,
            self._ui_render_total_ms / self._ui_frame_count,
            self._ui_render_max_ms,
            self._ui_frame_count / max(0.001, perf_counter() - self._ui_window_started),
            self._localization_worker.skipped_display_states if self._localization_worker is not None else 0,
            getattr(getattr(state, "mode", ""), "value", getattr(state, "mode", "")),
        )
        self._ui_frame_count = 0
        self._ui_render_total_ms = 0.0
        self._ui_render_max_ms = 0.0
        self._ui_window_started = perf_counter()

    def set_runtime_active(self, active: bool) -> None:
        self._runtime_active = bool(active)
        self.start_monitor_button.setEnabled(not active and self.runtime is not None)
        self.stop_monitor_button.setEnabled(active)
        self.monitor_config_button.setEnabled(not active)
        if self.profile_toolbar is not None:
            self.profile_toolbar.setEnabled(not active)
        if self.monitor_dialog is not None:
            self.monitor_dialog.set_editable(not active)

    def hideEvent(self, event) -> None:
        self.stop_monitoring()
        if self.capture_test_page is not None:
            self.capture_test_page.suspend()
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

    def _map_orientation(self) -> TerrainOrientation:
        return TerrainOrientation()

    def _refresh_map_display(self) -> None:
        snapshot = self.service.snapshot()
        if snapshot is None:
            return
        self._terrain_display = present_snapshot(snapshot, self._map_orientation())
        self._map_display_cache_signature = None
        self._map_display_pixmap = None
        self.map_widget.set_image(self._terrain_display.pixmap)
        self.map_widget.clear_overlay()

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
        if self._localization_worker is not None or any(
            worker.is_running for worker in self._retired_localization_workers
        ):
            self._logger.error(
                "step=ui.shutdown_deferred active_monitor_workers=%s",
                int(self._localization_worker is not None)
                + sum(worker.is_running for worker in self._retired_localization_workers),
            )
            if self.capture_test_page is not None:
                self.capture_test_page.suspend()
            # The monitor worker is independent from the follow engine.  A
            # timeout must not skip follow/Host cleanup: doing so leaves the
            # modular child processes and gamepad lease alive when the main
            # window proceeds with shutdown.  Keep the retired worker tracked,
            # but always cross the capture page's terminal cleanup boundary.
            self._logger.warning("step=ui.shutdown_continue_follow_cleanup despite_monitor_worker=True")
        if self.capture_test_page is not None:
            self.capture_test_page.shutdown()
        self.service.reset()
        self.map_widget.set_image(None)
        self._terrain_display = None
        self.metadata_label.setText("尚未获取地图")
        self.error_label.clear()
        self._render_state("未初始化")
