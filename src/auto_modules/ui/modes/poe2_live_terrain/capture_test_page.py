"""PoE2 capture-only test page used to inspect live evidence and terrain data."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, Callable, Mapping, cast

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from auto_modules.features.poe2.live_terrain import get_terrain_logger
from auto_modules.ui.widgets import ScalableMapWidget
from auto_modules.features.poe2.live_terrain.orientation import TerrainOrientation

from .presenter import (
    build_localization_presentation,
    frame_pixmap,
    localization_display_point,
    present_localization_overlay,
    present_snapshot,
    terrain_pixmap,
)
from .capture_monitor_window import Poe2CaptureMonitorWindow
from .localization_control_dialog import Poe2LocalizationControlDialog
from .multiframe_panel import Poe2MultiframePanel

if TYPE_CHECKING:
    from auto_modules.features.poe2.live_terrain.player_position import PlayerPositionSample


class Poe2CaptureTestPage(QWidget):
    """Capture screenshots and native terrain without starting localization."""

    def __init__(
        self,
        service: Any,
        *,
        archive: Any,
        sample_archive: Any | None = None,
        stitching_session_factory: Callable[[], Any] | None = None,
        stitching_archive: Any | None = None,
        monitor_config: Any,
        preview_provider: Callable[[Any], Any] | None,
        recognizer: Any | None = None,
        player_position_source: Any | None = None,
        hybrid_localization_factory: Callable[[Any, Callable[[], Any]], Any] | None = None,
        multiframe_localization_factory: Callable[[Any, Callable[[], Any]], Any] | None = None,
        open_config: Callable[[], None] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.service = service
        self.archive = archive
        self.sample_archive = sample_archive
        self.stitching_session_factory = stitching_session_factory
        self.stitching_archive = stitching_archive
        self.monitor_config = monitor_config
        self.preview_provider = preview_provider
        self.recognizer = recognizer
        self.player_position_source = player_position_source
        self.hybrid_localization_factory = hybrid_localization_factory
        self.multiframe_localization_factory = multiframe_localization_factory
        self.open_config_callback = open_config
        self.capture_monitor_window = None
        self._logger = get_terrain_logger()
        self.preview_timer = QTimer(self)
        self.preview_timer.setInterval(self._sample_interval())
        self.preview_timer.timeout.connect(self.refresh_preview)
        self.hybrid_timer = QTimer(self)
        self.hybrid_timer.setInterval(self._sample_interval())
        self.hybrid_timer.timeout.connect(self._tick_hybrid_localization)
        self._snapshot = None
        self._player_position: PlayerPositionSample | None = None
        self._terrain_base_pixmap = None
        self.map_follow_zoom_multiplier = 2.4
        self._hybrid_experiment = None
        self._last_hybrid_state = None
        self._multiframe_experiment = None
        self._last_multiframe_state = None
        self._multiframe_trajectory: list[tuple[float, float]] = []
        self._multiframe_trajectory_version = 0
        self._multiframe_timer = QTimer(self)
        self._multiframe_timer.setInterval(self._sample_interval())
        self._multiframe_timer.timeout.connect(self._tick_multiframe)
        self.localization_control_dialog = Poe2LocalizationControlDialog(self)
        self.multiframe_panel = self.localization_control_dialog.panel
        self._build_ui()
        self._render_state("未初始化")

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        controls = QHBoxLayout()
        self.monitor_config_button = QPushButton("监控配置")
        self.capture_monitor_button = QPushButton("打开截图监控窗口")
        self.refresh_preview_button = QPushButton("刷新截图")
        self.start_preview_button = QPushButton("开始截图监控")
        self.stop_preview_button = QPushButton("停止截图监控")
        self.initialize_button = QPushButton("初始化")
        self.capture_button = QPushButton("获取当前地图")
        self.save_button = QPushButton("保存当前地图")
        self.reset_button = QPushButton("清空测试状态")
        self.start_single_frame_button = QPushButton("开始首帧定位")
        self.stop_single_frame_button = QPushButton("停止首帧定位")
        self.localization_control_button = QPushButton("定位控制")
        self.monitor_config_button.clicked.connect(self._open_config)
        self.capture_monitor_button.clicked.connect(self.open_capture_monitor)
        self.refresh_preview_button.clicked.connect(self.refresh_preview)
        self.start_preview_button.clicked.connect(self.start_preview)
        self.stop_preview_button.clicked.connect(self.stop_preview)
        self.initialize_button.clicked.connect(self.initialize_session)
        self.capture_button.clicked.connect(self.capture_map)
        self.save_button.clicked.connect(self.save_map)
        self.reset_button.clicked.connect(self.reset_session)
        self.start_single_frame_button.clicked.connect(self.start_hybrid_localization)
        self.stop_single_frame_button.clicked.connect(self.stop_hybrid_localization)
        self.localization_control_button.clicked.connect(self.open_localization_control)
        for button in (
            self.monitor_config_button,
            self.capture_monitor_button,
            self.refresh_preview_button,
            self.start_preview_button,
            self.stop_preview_button,
            self.initialize_button,
            self.capture_button,
            self.save_button,
            self.reset_button,
            self.start_single_frame_button,
            self.stop_single_frame_button,
            self.localization_control_button,
        ):
            controls.addWidget(button)
        controls.addStretch()
        root.addLayout(controls)

        self.status_label = QLabel()
        self.error_label = QLabel()
        self.error_label.setWordWrap(True)
        self.archive_label = QLabel("尚未保存地图")
        self.archive_label.setWordWrap(True)
        self.metadata_label = QLabel("尚未获取地图")
        self.metadata_label.setWordWrap(True)
        self.player_position_label = QLabel("人物位置：未读取")
        self.player_position_label.setWordWrap(True)
        root.addWidget(self.status_label)
        root.addWidget(self.error_label)
        root.addWidget(self.archive_label)
        root.addWidget(self.metadata_label)
        root.addWidget(self.player_position_label)
        self.single_frame_status_label = QLabel("首帧定位：未启动")
        self.single_frame_status_label.setWordWrap(True)
        root.addWidget(self.single_frame_status_label)

        hybrid_group = QGroupBox("混合定位实验")
        self._legacy_hybrid_group = hybrid_group
        hybrid_layout = QVBoxLayout(hybrid_group)
        hybrid_controls = QHBoxLayout()
        self.start_hybrid_button = QPushButton("开始混合定位")
        self.stop_hybrid_button = QPushButton("停止")
        self.retry_hybrid_button = QPushButton("重新恢复一次")
        self.start_hybrid_button.clicked.connect(self.start_hybrid_localization)
        self.stop_hybrid_button.clicked.connect(self.stop_hybrid_localization)
        self.retry_hybrid_button.clicked.connect(self.retry_hybrid_recovery)
        hybrid_controls.addWidget(self.start_hybrid_button)
        hybrid_controls.addWidget(self.stop_hybrid_button)
        hybrid_controls.addWidget(self.retry_hybrid_button)
        hybrid_controls.addStretch()
        hybrid_layout.addLayout(hybrid_controls)
        self.hybrid_status_label = QLabel("混合定位：未启动")
        self.hybrid_status_label.setWordWrap(True)
        self.hybrid_position_label = QLabel("实时位置：暂无")
        hybrid_layout.addWidget(self.hybrid_status_label)
        hybrid_layout.addWidget(self.hybrid_position_label)
        hybrid_group.setVisible(False)

        self.multiframe_panel.start_requested.connect(self.start_multiframe_localization)
        self.multiframe_panel.stop_requested.connect(self.stop_multiframe_localization)
        self.multiframe_panel.reset_requested.connect(self.reset_multiframe_localization)
        self.multiframe_panel.save_requested.connect(self.save_multiframe_experiment)
        self.start_multiframe_button = self.multiframe_panel.start_button
        self.stop_multiframe_button = self.multiframe_panel.stop_button
        self.multiframe_status_label = self.multiframe_panel.status_label
        self.multiframe_position_label = self.multiframe_panel.position_label

        preview_group = QGroupBox("小地图截图与视觉特征")
        preview_layout = QHBoxLayout(preview_group)
        self.frame_preview_layout, self.frame_preview = self._make_preview("当前截图")
        self.processed_preview_layout, self.processed_preview = self._make_preview("预处理画面")
        self.feature_preview_layout, self.feature_preview = self._make_preview("匹配特征")
        preview_layout.addLayout(self.frame_preview_layout)
        preview_layout.addLayout(self.processed_preview_layout)
        preview_layout.addLayout(self.feature_preview_layout)
        root.addWidget(preview_group, 1)

        map_group = QGroupBox("当前获取的地图")
        map_layout = QVBoxLayout(map_group)
        self.map_widget = ScalableMapWidget(self)
        self.map_widget.fit_scale_multiplier = 1.35
        map_layout.addWidget(self.map_widget)
        root.addWidget(map_group, 2)
        self.stop_preview_button.setEnabled(False)
        self.stop_single_frame_button.setEnabled(False)
        self.start_hybrid_button.setEnabled(False)
        self.stop_hybrid_button.setEnabled(False)
        self.retry_hybrid_button.setEnabled(False)
        self.start_multiframe_button.setEnabled(False)
        self.stop_multiframe_button.setEnabled(False)

    @staticmethod
    def _make_preview(title: str):
        layout = QVBoxLayout()
        layout.addWidget(QLabel(title))
        label = QLabel("尚未截图")
        label.setMinimumSize(180, 180)
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("background: #101318; border: 1px solid #39414d;")
        layout.addWidget(label)
        return layout, label

    def set_monitor_config(self, config: Any) -> None:
        self.monitor_config = config
        self.preview_timer.setInterval(self._sample_interval())
        if self.capture_monitor_window is not None:
            self.capture_monitor_window.preview_timer.setInterval(self._sample_interval())

    def open_capture_monitor(self) -> None:
        if (
            self.sample_archive is None
            or self.stitching_session_factory is None
            or self.stitching_archive is None
            or self.preview_provider is None
            or self.recognizer is None
        ):
            self._show_error(RuntimeError("截图监控窗口依赖未完整注入"))
            return
        if self.capture_monitor_window is None:
            self.capture_monitor_window = Poe2CaptureMonitorWindow(
                preview_provider=self.preview_provider,
                recognizer=self.recognizer,
                monitor_config_provider=lambda: self.monitor_config,
                terrain_snapshot_provider=self.service.snapshot,
                sample_archive=self.sample_archive,
                stitching_session=self.stitching_session_factory(),
                stitching_archive=self.stitching_archive,
                player_position_provider=lambda: self._player_position,
                parent=self,
            )
            if self._last_hybrid_state is not None:
                self.capture_monitor_window.handle_hybrid_state(
                    self._last_hybrid_state,
                    read_count=self._hybrid_read_count(),
                )
        self.capture_monitor_window.show()
        self.capture_monitor_window.raise_()
        self.capture_monitor_window.activateWindow()

    def _sample_interval(self) -> int:
        return max(20, int(getattr(self.monitor_config, "sample_interval_ms", 100)))

    def _open_config(self) -> None:
        if self.open_config_callback is None:
            self._show_error(RuntimeError("PoE2 监控配置入口未注入"))
            return
        self.open_config_callback()

    def open_localization_control(self) -> None:
        """Show experiment controls without shrinking the capture/map workspace."""
        self.localization_control_dialog.set_ready(
            self._snapshot is not None and self.multiframe_localization_factory is not None
        )
        self.localization_control_dialog.show_non_modal()

    def initialize_session(self) -> None:
        self._logger.info("step=test_page.initialize_clicked")
        self._clear_map_state()
        try:
            self.service.initialize()
        except Exception as exc:
            self._logger.exception("step=test_page.initialize_failed error=%s", exc)
            self._show_error(exc)
            return
        self.error_label.clear()
        self._render_state("可获取当前地图")
        self._logger.info("step=test_page.initialize_success")

    def capture_map(self) -> None:
        self._logger.info("step=test_page.capture_clicked")
        self.stop_hybrid_localization()
        self.stop_multiframe_localization()
        self._hybrid_experiment = None
        self._last_hybrid_state = None
        try:
            snapshot = self.service.capture()
        except Exception as exc:
            self._logger.exception("step=test_page.capture_failed error=%s", exc)
            self._clear_map_state()
            self._show_error(exc)
            return
        self._snapshot = snapshot
        player_position: PlayerPositionSample | None = None
        position_error = None
        if self.player_position_source is not None:
            self._logger.info("step=test_page.player_position_start instance=%s", snapshot.metadata.instance_id)
            try:
                reader = getattr(self.player_position_source, "read_once", None)
                if not callable(reader):
                    raise RuntimeError("人物位置读取器未提供 read_once")
                sample = reader(snapshot.metadata.instance_id)
                grid = getattr(sample, "grid", None)
                if grid is None or len(grid) != 2:
                    raise RuntimeError("人物位置读取器返回了无效坐标")
                player_position = cast("PlayerPositionSample", sample)
            except Exception as exc:
                position_error = exc
                self._logger.exception("step=test_page.player_position_failed error=%s", exc)
            else:
                self._logger.info(
                    "step=test_page.player_position_success grid=(%.2f, %.2f)",
                    grid[0],
                    grid[1],
                )
        self._player_position = player_position
        display = present_snapshot(
            snapshot,
            orientation=self._map_orientation(),
            player_position=player_position,
        )
        self._terrain_base_pixmap = display.pixmap
        self.map_widget.set_image(display.pixmap)
        if player_position is not None:
            orientation = self._map_orientation()
            point = orientation.transform_point(
                player_position.grid,
                (snapshot.metadata.height, snapshot.metadata.width),
            )
            point = localization_display_point(
                point,
                source_size=(display.pixmap.width(), display.pixmap.height()),
            )
            self.map_widget.focus_on_point(
                point,
                zoom_multiplier=self.map_follow_zoom_multiplier,
            )
        self.metadata_label.setText("\n".join(display.metadata_lines))
        if player_position is not None:
            self.player_position_label.setText(
                f"人物位置：网格 ({player_position.grid[0]:.2f}, {player_position.grid[1]:.2f})"
            )
        elif self.player_position_source is None:
            self.player_position_label.setText("人物位置：未注入读取器")
        else:
            self.player_position_label.setText("人物位置：读取失败")
        if position_error is None:
            self.error_label.clear()
            self._render_state("已获取当前地图")
        else:
            self.error_label.setText(f"人物定位错误（地图仍已获取）：{position_error}")
            self._render_state("已获取当前地图，人物定位失败")
        self._logger.info("step=test_page.capture_success instance=%s", snapshot.metadata.instance_id)

    def start_hybrid_localization(self) -> None:
        if self._snapshot is None:
            self._show_error(RuntimeError("请先获取当前地图"))
            return
        if self.hybrid_localization_factory is None:
            self._show_error(RuntimeError("混合定位实验工厂未注入"))
            return
        self.stop_hybrid_localization()
        self.stop_multiframe_localization()
        self.stop_preview()
        if self.capture_monitor_window is not None:
            stop_monitoring = getattr(self.capture_monitor_window, "stop_monitoring", None)
            if callable(stop_monitoring):
                stop_monitoring()
        try:
            experiment = self.hybrid_localization_factory(
                self._snapshot,
                lambda: self.monitor_config,
            )
            experiment.session.add_listener(self.handle_hybrid_state)
            experiment.session.start()
            self._hybrid_experiment = experiment
            self.hybrid_timer.setInterval(self._sample_interval())
            self.hybrid_timer.start()
            self._tick_hybrid_localization()
        except Exception as exc:
            self.hybrid_timer.stop()
            self._hybrid_experiment = None
            self._logger.exception("step=hybrid.start_failed error=%s", exc)
            self._show_error(exc)
            return
        self.start_hybrid_button.setEnabled(False)
        self.stop_hybrid_button.setEnabled(True)
        self.start_single_frame_button.setEnabled(False)
        self.stop_single_frame_button.setEnabled(True)
        self._logger.info("step=hybrid.started interval_ms=%s", self.hybrid_timer.interval())

    def start_multiframe_localization(self) -> None:
        if self._snapshot is None or self.multiframe_localization_factory is None:
            self._show_error(RuntimeError("请先获取地图并注入多帧实验工厂"))
            return
        binding = getattr(self.monitor_config, "binding", None)
        if binding is None:
            self._show_error(RuntimeError("请先配置 PoE2 小地图监控区域"))
            self._logger.warning("step=multiframe.start_rejected reason=missing_monitor_binding")
            return
        self.stop_multiframe_localization()
        # The preview and detached monitor use the same capture/recognizer
        # resources.  Keep one sampling loop active for deterministic timing.
        self.stop_preview()
        if self.capture_monitor_window is not None:
            stop_monitoring = getattr(self.capture_monitor_window, "stop_monitoring", None)
            if callable(stop_monitoring):
                stop_monitoring()
        experiment = None
        try:
            experiment = self.multiframe_localization_factory(self._snapshot, lambda: self.monitor_config)
            strategy_a, strategy_b = self.multiframe_panel.selected_strategies()
            experiment.coordinator.set_strategies_enabled(strategy_a=strategy_a, strategy_b=strategy_b)
            experiment.session.start()
            self._multiframe_experiment = experiment
            self._multiframe_trajectory.clear()
            self._multiframe_trajectory_version = 0
            self._multiframe_timer.setInterval(self._sample_interval())
            self._multiframe_timer.start()
            self._tick_multiframe()
        except Exception as exc:
            self._multiframe_timer.stop()
            if experiment is not None:
                close = getattr(experiment.session, "close", None)
                if callable(close):
                    close()
            self._multiframe_experiment = None
            self.multiframe_panel.set_running(False)
            self.multiframe_panel.set_archive_available(False)
            self._logger.exception("step=multiframe.start_failed error=%s", exc)
            self._show_error(exc)
            return
        self.start_multiframe_button.setEnabled(False)
        self.stop_multiframe_button.setEnabled(True)
        self.multiframe_panel.set_running(True)
        self.multiframe_panel.set_archive_available(False)
        self._logger.info("step=multiframe.started interval_ms=%s", self._multiframe_timer.interval())

    def stop_multiframe_localization(self) -> None:
        self._multiframe_timer.stop()
        experiment = self._multiframe_experiment
        if experiment is not None:
            close = getattr(experiment.session, "close", None)
            if callable(close):
                close()
            else:
                experiment.session.stop()
        self._multiframe_experiment = None
        self._last_multiframe_state = None
        self._multiframe_trajectory.clear()
        self._multiframe_trajectory_version = 0
        self.start_multiframe_button.setEnabled(self.multiframe_localization_factory is not None and self._snapshot is not None)
        self.stop_multiframe_button.setEnabled(False)
        self.multiframe_panel.set_running(False)
        self.multiframe_panel.set_archive_available(False)

    def reset_multiframe_localization(self) -> None:
        self.stop_multiframe_localization()
        self._multiframe_experiment = None
        self._last_multiframe_state = None
        self._multiframe_trajectory.clear()
        self._multiframe_trajectory_version = 0
        self.multiframe_status_label.setText("多帧定位：未启动")
        self.multiframe_position_label.setText("多帧位置：暂无")
        self.multiframe_panel.set_submap(None)
        self.multiframe_panel.set_archive_available(False)

    def save_multiframe_experiment(self) -> None:
        experiment = self._multiframe_experiment
        if experiment is None:
            self._show_error(RuntimeError("多帧定位实验尚未启动"))
            return
        if not self._multiframe_archive_ready():
            self._show_error(RuntimeError("多帧实验尚未形成可归档的锚点、参考地图和证据"))
            return
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        target = Path("data/poe2_live_terrain_test/multiframe_sessions") / timestamp
        try:
            saved = experiment.archive.save(
                target,
                evidence=experiment.window.snapshot(),
                anchor=experiment.coordinator.anchor,
                instance_id=experiment.coordinator.instance_id,
                reference=experiment.coordinator.reference,
                estimate=self._last_multiframe_state,
                diagnostics={
                    "recovery_revision": experiment.coordinator.recovery_revision,
                    "memory_read_count": int(getattr(experiment.anchor_provider, "read_count", 0)),
                    "phase": experiment.coordinator.phase.value,
                },
            )
        except Exception as exc:
            self._logger.exception("step=multiframe.archive_failed error=%s", exc)
            self._show_error(exc)
            return
        self._logger.info("step=multiframe.archive_saved path=%s", saved)
        self.multiframe_status_label.setText(f"多帧实验已保存：{saved}")

    def _multiframe_archive_ready(self) -> bool:
        experiment = self._multiframe_experiment
        if experiment is None:
            return False
        coordinator = getattr(experiment, "coordinator", None)
        window = getattr(experiment, "window", None)
        return bool(
            getattr(coordinator, "anchor", None) is not None
            and getattr(coordinator, "reference", None) is not None
            and window is not None
            and tuple(window.snapshot())
        )

    def _tick_multiframe(self) -> None:
        experiment = self._multiframe_experiment
        if experiment is None:
            return
        try:
            state = experiment.session.tick()
        except Exception as exc:
            self._logger.exception("step=multiframe.tick_failed error=%s", exc)
            self.stop_multiframe_localization()
            self._show_error(exc)
            return
        self._last_multiframe_state = state
        candidates = tuple(getattr(state, "candidate_regions", ()) or ())
        keyframes = len(experiment.window.snapshot())
        reads = int(getattr(experiment.anchor_provider, "read_count", 0))
        evidence_bytes = int(getattr(experiment.window, "estimated_bytes", 0))
        registration_version = int(getattr(state, "registration_version", 0))
        if registration_version != self._multiframe_trajectory_version:
            self._multiframe_trajectory.clear()
            self._multiframe_trajectory_version = registration_version
        if state.position is not None and state.fresh:
            self._multiframe_trajectory.append(tuple(state.position))
            self._multiframe_trajectory = self._multiframe_trajectory[-200:]
        self.multiframe_status_label.setText(
            f"多帧定位：{state.status} | evidence {state.evidence_version} | "
            f"候选 {len(candidates)} | 关键帧 {keyframes} | 内存读取 {reads} | "
            f"恢复版本 {experiment.coordinator.recovery_revision} | {state.reason}"
        )
        self.multiframe_position_label.setText(f"多帧位置：{state.position if state.position is not None else '暂无'}")
        self.multiframe_panel.set_state(
            status=state.status,
            evidence_version=state.evidence_version,
            recovery_revision=experiment.coordinator.recovery_revision,
            reason=state.reason,
            position=state.position,
            keyframes=keyframes,
            candidates=len(candidates),
            memory_reads=reads,
            registration_pending=experiment.session.registration_pending,
            strategy_a_status=getattr(experiment.coordinator.last_strategy_a_result, "status", None),
            best_candidate=getattr(experiment.coordinator.last_strategy_b_result, "best", None),
            evidence_bytes=evidence_bytes,
            tick_elapsed_ms=float(getattr(experiment.session, "last_tick_elapsed_ms", 0.0)),
            registration_elapsed_ms=float(getattr(experiment.session, "last_registration_elapsed_ms", 0.0)),
        )
        submap = experiment.submap.rebuild(experiment.window.snapshot())
        self.multiframe_panel.set_submap(submap.wall_mask)
        self.multiframe_panel.set_archive_available(self._multiframe_archive_ready())
        if self._snapshot is not None:
            native_pixmap = terrain_pixmap(self._snapshot)
            overlay_state = build_localization_presentation(
                state,
                registration=experiment.coordinator.registration,
                coordinator_registration_version=int(
                    getattr(experiment.coordinator, "registration_version", registration_version)
                ),
                trajectory=self._multiframe_trajectory,
                candidates=candidates,
            )
            overlay = present_localization_overlay(native_pixmap, overlay_state)
            self.map_widget.set_image(overlay)
            self._focus_map_on_state(overlay_state, source_size=native_pixmap.size())
            transform = getattr(experiment.coordinator.registration, "transform", None)
            lines = [line for line in self.metadata_label.text().splitlines() if not line.startswith("方向：")]
            if transform is not None and overlay_state.registration is not None:
                lines.append(
                    f"方向：多帧自动校准 {float(transform.angle_degrees):.1f}°"
                    f"{'，水平镜像' if transform.reflect_horizontal else ''}"
                )
            else:
                lines.append("方向：等待自动校准（native）")
            self.metadata_label.setText("\n".join(lines))
        self._logger.info(
            "step=multiframe.state phase=%s status=%s source=%s position=%s evidence=%s keyframes=%s evidence_bytes=%s candidates=%s reads=%s pending=%s tick_ms=%.2f registration_ms=%.2f reason=%s diagnostics=%s",
            experiment.coordinator.phase.value,
            state.status,
            state.source,
            state.position,
            state.evidence_version,
            keyframes,
            evidence_bytes,
            len(candidates),
            reads,
            experiment.session.registration_pending,
            float(getattr(experiment.session, "last_tick_elapsed_ms", 0.0)),
            float(getattr(experiment.session, "last_registration_elapsed_ms", 0.0)),
            state.reason,
            dict(getattr(state, "diagnostics", {}) or {}),
        )

    def stop_hybrid_localization(self) -> None:
        self.hybrid_timer.stop()
        experiment = self._hybrid_experiment
        if experiment is not None:
            experiment.session.stop()
        self.start_hybrid_button.setEnabled(
            self.hybrid_localization_factory is not None and self._snapshot is not None
        )
        self.stop_hybrid_button.setEnabled(False)
        self.retry_hybrid_button.setEnabled(False)
        self.stop_single_frame_button.setEnabled(False)
        self.start_single_frame_button.setEnabled(
            self.hybrid_localization_factory is not None and self._snapshot is not None
        )

    def retry_hybrid_recovery(self) -> None:
        if self._hybrid_experiment is None:
            self._show_error(RuntimeError("混合定位尚未启动"))
            return
        try:
            self._hybrid_experiment.session.retry_recovery()
        except Exception as exc:
            self._logger.exception("step=hybrid.retry_failed error=%s", exc)
            self._show_error(exc)
            return
        self.retry_hybrid_button.setEnabled(False)
        self.hybrid_status_label.setText("混合定位：已允许单次恢复，等待下一帧")
        self._logger.info("step=hybrid.retry_requested")

    def _tick_hybrid_localization(self) -> None:
        if self._hybrid_experiment is None:
            return
        try:
            self._hybrid_experiment.session.tick()
        except Exception as exc:
            self.hybrid_timer.stop()
            self.stop_hybrid_button.setEnabled(False)
            self.start_hybrid_button.setEnabled(self._snapshot is not None)
            self._logger.exception("step=hybrid.tick_failed error=%s", exc)
            self._show_error(exc)

    def _hybrid_read_count(self) -> int:
        provider = getattr(self._hybrid_experiment, "anchor_provider", None)
        return int(getattr(provider, "read_count", 0))

    def _map_orientation(self) -> TerrainOrientation:
        return TerrainOrientation()

    def handle_hybrid_state(self, state: Any) -> None:
        self._last_hybrid_state = state
        mode = getattr(getattr(state, "mode", "unknown"), "value", getattr(state, "mode", "unknown"))
        source = str(getattr(state, "source", "failed"))
        confidence = float(getattr(state, "confidence", 0.0))
        revision = int(getattr(state, "recovery_revision", 0))
        reason = str(getattr(state, "reason", "") or "")
        reads = self._hybrid_read_count()
        details = (
            f"混合定位：{mode} | 来源 {source} | 置信度 {confidence:.3f} | "
            f"内存读取 {reads} 次 | 恢复版本 {revision}"
        )
        if reason:
            details += f" | {reason}"
        diagnostics = getattr(state, "diagnostics", {})
        if isinstance(diagnostics, Mapping):
            registration_reason = str(diagnostics.get("reason", "") or "")
            if registration_reason and registration_reason != reason:
                details += f" | {registration_reason}"
            numeric_details = (
                ("best_score", "候选分", 3),
                ("best_forward_coverage", "覆盖", 3),
                ("best_angle", "角度", 1),
                ("best_scale", "比例", 3),
                ("best_anchor_error", "锚点误差", 2),
            )
            for key, label, precision in numeric_details:
                value = diagnostics.get(key)
                if isinstance(value, (int, float)):
                    suffix = "°" if key == "best_angle" else ""
                    details += f" | {label} {float(value):.{precision}f}{suffix}"
        self.hybrid_status_label.setText(details)
        self.single_frame_status_label.setText(details.replace("混合定位：", "首帧定位：", 1))
        position = getattr(state, "position", None)
        if position is None:
            self.hybrid_position_label.setText("实时位置：本帧无可信位置")
        else:
            self.hybrid_position_label.setText(
                f"实时位置：({float(position[0]):.2f}, {float(position[1]):.2f})"
            )
        mode_name = str(mode)
        self.retry_hybrid_button.setEnabled(mode_name == "recovery_required")
        if self._terrain_base_pixmap is not None:
            base_pixmap = self._terrain_base_pixmap
            overlay = present_localization_overlay(base_pixmap, state)
            self.map_widget.set_image(overlay)
            self._focus_map_on_state(state, source_size=base_pixmap.size())
        transform = getattr(getattr(state, "registration", None), "transform", None)
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
        if self.capture_monitor_window is not None:
            self.capture_monitor_window.handle_hybrid_state(state, read_count=reads)
        self._logger.info(
            "step=hybrid.state mode=%s source=%s confidence=%.3f position=%s reads=%s revision=%s reason=%s diagnostics=%s",
            mode,
            source,
            confidence,
            position,
            reads,
            revision,
            reason,
            dict(diagnostics) if isinstance(diagnostics, Mapping) else {},
        )

    def _focus_map_on_state(self, state: Any, *, source_size) -> None:
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

    def save_map(self) -> None:
        self._logger.info("step=test_page.save_clicked")
        snapshot = self.service.snapshot() or self._snapshot
        if snapshot is None:
            self._show_error(RuntimeError("请先获取当前地图"))
            return
        try:
            path = self.archive.save(snapshot)
        except Exception as exc:
            self._logger.exception("step=test_page.save_failed error=%s", exc)
            self._show_error(exc)
            return
        self.archive_label.setText(f"已保存地图：{path}")
        self.error_label.clear()
        self._logger.info("step=test_page.save_success path=%s", path)

    def refresh_preview(self) -> None:
        self._logger.info("step=test_page.preview_clicked")
        if self.preview_provider is None:
            self._clear_preview("截图预览后端未注入")
            return
        try:
            frame = self.preview_provider(self.monitor_config)
            if frame is None:
                raise RuntimeError("截图后端返回空帧")
            self._render_preview(frame)
        except Exception as exc:
            self._logger.exception("step=test_page.preview_failed error=%s", exc)
            self._clear_preview(str(exc))
            return
        self.error_label.clear()
        self._logger.info("step=test_page.preview_success")

    def _render_preview(self, frame) -> None:
        self._set_preview(self.frame_preview, frame)
        if self.recognizer is None:
            self._clear_label(self.processed_preview, "未注入预处理器")
            self._clear_label(self.feature_preview, "未注入特征提取器")
            return
        processed = self.recognizer.preprocess_image(frame)
        marker = getattr(getattr(self.monitor_config, "binding", None), "player_marker_position", None)
        combined = self.recognizer.extract_combined(frame, player_pos=marker)
        feature = combined[0] if isinstance(combined, tuple) else combined
        self._set_preview(self.processed_preview, processed)
        self._set_preview(self.feature_preview, feature)

    def _set_preview(self, label: QLabel, frame) -> None:
        pixmap = frame_pixmap(frame)
        if pixmap.isNull():
            self._clear_label(label, "本帧无画面")
            return
        label.setPixmap(pixmap.scaled(label.size(), Qt.KeepAspectRatio, Qt.FastTransformation))

    @staticmethod
    def _clear_label(label: QLabel, message: str) -> None:
        label.clear()
        label.setText(message)

    def _clear_preview(self, error: str) -> None:
        self._clear_label(self.frame_preview, "本帧无画面")
        self._clear_label(self.processed_preview, "本帧无画面")
        self._clear_label(self.feature_preview, "本帧无特征")
        self._show_error(RuntimeError(error))

    def start_preview(self) -> None:
        self.preview_timer.setInterval(self._sample_interval())
        self.preview_timer.start()
        self.refresh_preview()
        self.start_preview_button.setEnabled(False)
        self.stop_preview_button.setEnabled(True)
        self._logger.info("step=test_page.preview_started interval_ms=%s", self.preview_timer.interval())

    def stop_preview(self) -> None:
        self.preview_timer.stop()
        self.start_preview_button.setEnabled(True)
        self.stop_preview_button.setEnabled(False)
        self._logger.info("step=test_page.preview_stopped")

    def reset_session(self) -> None:
        self._logger.info("step=test_page.reset")
        self.stop_preview()
        self.stop_hybrid_localization()
        self.stop_multiframe_localization()
        self.service.reset()
        self._snapshot = None
        self._clear_map_state()
        self.archive_label.setText("尚未保存地图")
        self._clear_preview("尚未截图")
        self.error_label.clear()
        self._render_state("未初始化")

    def _clear_map_state(self) -> None:
        self.stop_hybrid_localization()
        self.stop_multiframe_localization()
        self._snapshot = None
        self._player_position = None
        self._terrain_base_pixmap = None
        self._hybrid_experiment = None
        self._last_hybrid_state = None
        self.map_widget.set_image(None)
        self.metadata_label.setText("尚未获取地图")
        self.player_position_label.setText("人物位置：未读取")
        self.save_button.setEnabled(False)
        self.hybrid_status_label.setText("混合定位：未启动")
        self.hybrid_position_label.setText("实时位置：暂无")
        self.single_frame_status_label.setText("首帧定位：未启动")
        self.multiframe_status_label.setText("多帧定位：未启动")
        self.multiframe_position_label.setText("多帧位置：暂无")
        self._multiframe_experiment = None
        self._last_multiframe_state = None
        self._multiframe_trajectory.clear()
        self._multiframe_trajectory_version = 0
        self.multiframe_panel.set_submap(None)
        self.multiframe_panel.set_archive_available(False)

    def _render_state(self, text: str) -> None:
        value = getattr(getattr(self.service, "state", "new"), "value", getattr(self.service, "state", "new"))
        has_snapshot = self.service.snapshot() is not None or self._snapshot is not None
        self.status_label.setText(f"状态：{text}（会话：{value}）")
        self.capture_button.setEnabled(value in {"ready_to_capture", "captured"})
        self.save_button.setEnabled(has_snapshot)
        self.refresh_preview_button.setEnabled(self.preview_provider is not None)
        self.start_hybrid_button.setEnabled(
            has_snapshot
            and self.hybrid_localization_factory is not None
            and not self.hybrid_timer.isActive()
        )
        self.start_single_frame_button.setEnabled(
            has_snapshot
            and self.hybrid_localization_factory is not None
            and not self.hybrid_timer.isActive()
        )
        self.start_multiframe_button.setEnabled(
            has_snapshot
            and self.multiframe_localization_factory is not None
            and not self._multiframe_timer.isActive()
        )
        self.localization_control_dialog.set_ready(
            has_snapshot and self.multiframe_localization_factory is not None
        )

    def _show_error(self, error: Exception) -> None:
        self.status_label.setText("状态：错误")
        self.error_label.setText(f"错误：{error}")

    def shutdown(self) -> None:
        self.stop_preview()
        self.stop_hybrid_localization()
        self.stop_multiframe_localization()
        if self.capture_monitor_window is not None:
            self.capture_monitor_window.close()
        self.localization_control_dialog.close()
        self.service.reset()


__all__ = ["Poe2CaptureTestPage"]
